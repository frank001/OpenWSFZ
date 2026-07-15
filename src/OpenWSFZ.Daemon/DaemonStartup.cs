using System.Net;
using System.Net.Sockets;
using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Bind-retry helper used only when this instance was launched with
/// <c>--relaunched-from &lt;pid&gt;</c> (remote-daemon-restart, design.md Decision 4). An
/// ordinary cold start never calls this — it calls <c>app.StartAsync()</c>/<c>RunAsync()</c>
/// directly and fails immediately on a bind conflict, exactly as before this change.
/// </summary>
/// <remarks>
/// Retries a cheap raw TCP-socket bind probe on the configured port, then calls the real host
/// start step (<paramref name="startAsync"/> in <see cref="StartWithBindRetryAsync"/>) exactly
/// once the probe succeeds — <em>not</em> a literal repeated call to <c>app.StartAsync()</c>.
/// Kestrel's <c>KestrelServerImpl</c> marks its host "started" on the very first
/// <c>StartAsync()</c> call regardless of whether the underlying bind actually succeeded;
/// calling <c>StartAsync()</c> a second time on the same, already-attempted
/// <c>WebApplication</c> instance throws <c>InvalidOperationException("Server has already
/// started.")</c> instead of retrying the bind (confirmed empirically while building this
/// class's test suite — see <c>DaemonStartupTests</c>). A raw probe-then-single-real-start
/// achieves the same observable behaviour as every acceptance scenario in the
/// <c>remote-daemon-restart</c> spec (retries while the port is held; gives up after the
/// budget; a normal cold start is completely unaffected; no startup work repeats) without
/// depending on repeatable <c>StartAsync()</c> semantics ASP.NET Core does not provide.
/// </remarks>
internal static class DaemonStartup
{
    /// <summary>
    /// Retry interval between bind-probe attempts, in milliseconds.
    /// </summary>
    internal const int DefaultRetryIntervalMs = 500;

    /// <summary>
    /// Total bind-retry budget, in milliseconds. Matches this codebase's existing
    /// failsafe-window convention (<c>PttConfig.WatchdogTimeoutMs</c>'s default of 20000,
    /// cat-tx-ptt) — comfortably covers realistic teardown time (WebSocket abort, WASAPI
    /// capture stop, log flush) without leaving an operator staring at a "reconnecting…" UI
    /// indefinitely if something is genuinely wrong.
    /// </summary>
    internal const int DefaultTotalBudgetMs = 20000;

    /// <summary>
    /// Polls <paramref name="port"/> with a cheap, throwaway TCP bind probe until it appears
    /// free, then invokes <paramref name="startAsync"/> (the host's real, single start
    /// attempt) exactly once. Only the probe repeats — nothing before or after it re-runs, so
    /// no side-effecting startup work (audio device enumeration, native decoder construction,
    /// serial port objects) is ever double-initiated.
    /// </summary>
    /// <param name="startAsync">
    /// The host's real start step, e.g. <c>() =&gt; app.StartAsync()</c>. Invoked at most once.
    /// </param>
    /// <param name="port">The port the host is configured to bind.</param>
    /// <param name="logger">Logger for Debug-level probe attempts and a final Error on giving up.</param>
    /// <param name="retryIntervalMs">Delay between probe attempts. Defaults to <see cref="DefaultRetryIntervalMs"/>.</param>
    /// <param name="totalBudgetMs">Total time budget before giving up. Defaults to <see cref="DefaultTotalBudgetMs"/>.</param>
    /// <returns>
    /// <c>true</c> if the port was found free and the real start succeeded; <c>false</c> if the
    /// budget was exhausted, or the real start still failed despite a successful probe
    /// (already logged at Error — the caller should exit non-zero, matching the existing
    /// "abnormal exit uses non-zero code" daemon-host convention).
    /// </returns>
    internal static async Task<bool> StartWithBindRetryAsync(
        Func<Task> startAsync,
        int        port,
        ILogger    logger,
        int        retryIntervalMs = DefaultRetryIntervalMs,
        int        totalBudgetMs   = DefaultTotalBudgetMs)
    {
        var deadline = DateTime.UtcNow.AddMilliseconds(totalBudgetMs);
        var attempt  = 0;

        while (!CanBindPort(port))
        {
            attempt++;
            if (DateTime.UtcNow >= deadline)
            {
                logger.LogError(
                    "Relaunched instance found port {Port} still held after the {BudgetMs} ms " +
                    "retry budget ({Attempts} probe attempt(s)) — giving up.",
                    port, totalBudgetMs, attempt);
                return false;
            }

            logger.LogDebug(
                "Relaunched instance's bind probe #{Attempt} on port {Port} found it still " +
                "held (likely by the instance being replaced) — retrying in {IntervalMs} ms.",
                attempt, port, retryIntervalMs);
            await Task.Delay(retryIntervalMs).ConfigureAwait(false);
        }

        try
        {
            await startAsync().ConfigureAwait(false);
            return true;
        }
        catch (IOException ex)
        {
            logger.LogError(ex,
                "Relaunched instance's bind probe on port {Port} found it free, but the real " +
                "host start still failed — giving up.", port);
            return false;
        }
    }

    /// <summary>
    /// Cheap, throwaway probe: <c>true</c> if a TCP listener can currently bind
    /// <paramref name="port"/> on loopback (immediately released afterwards).
    /// </summary>
    private static bool CanBindPort(int port)
    {
        try
        {
            var probe = new TcpListener(IPAddress.Loopback, port);
            probe.Start();
            probe.Stop();
            return true;
        }
        catch (SocketException)
        {
            return false;
        }
    }
}
