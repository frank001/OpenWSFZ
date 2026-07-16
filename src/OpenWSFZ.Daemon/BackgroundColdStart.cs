using System.Diagnostics;
using System.Net.Http;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Implements the <c>--background</c> cold-start path (daemon-background-mode, design.md
/// Decisions 2 and 5): spawn a detached <c>--background-worker</c> replacement of this process,
/// confirm it started via a bounded poll of its <c>GET /api/v1/status</c> endpoint, then report
/// and return an exit code — <c>Program.cs</c> returns immediately once this completes, without
/// doing any of the real startup work (audio capture, decode pipeline, web host) below that
/// point; the spawned replacement does that instead.
/// </summary>
internal static class BackgroundColdStart
{
    /// <summary>Default confirmation poll budget (design.md Decision 5).</summary>
    public static readonly TimeSpan DefaultConfirmationBudget = TimeSpan.FromSeconds(5);

    /// <summary>Default confirmation poll interval (design.md Decision 5).</summary>
    public static readonly TimeSpan DefaultPollInterval = TimeSpan.FromMilliseconds(500);

    /// <param name="SpawnSucceeded">
    /// <see langword="false"/> only when spawning the child process itself failed (e.g. the
    /// resolved executable does not exist) — never for a slow-but-eventually-successful spawn,
    /// which is reported via <see cref="ExitCode"/> = 0 with a caveat message instead.
    /// </param>
    /// <param name="ExitCode">The process exit code the caller (<c>Program.cs</c>) should return.</param>
    /// <param name="Message">A human-readable line for the caller to print.</param>
    internal readonly record struct SpawnResult(bool SpawnSucceeded, int ExitCode, string Message);

    /// <summary>
    /// Spawns <paramref name="fileName"/> <paramref name="arguments"/> (the already-resolved
    /// relaunch command, e.g. from <see cref="DaemonRelaunch.ResolveCommand"/> with
    /// <c>propagateBackgroundWorker: true</c>) via the same <see cref="Process.Start"/> pattern
    /// <see cref="DaemonRelauncher"/> already uses, then polls <paramref name="statusProbe"/>
    /// (defaulting to a real <c>GET /api/v1/status</c> request against <paramref name="port"/>)
    /// for up to <paramref name="confirmationBudget"/> at <paramref name="pollInterval"/>
    /// intervals before returning.
    /// </summary>
    public static async Task<SpawnResult> SpawnAndConfirmAsync(
        string fileName,
        string[] arguments,
        int port,
        string logDirectory,
        Func<int, CancellationToken, Task<bool>>? statusProbe = null,
        TimeSpan? confirmationBudget = null,
        TimeSpan? pollInterval = null)
    {
        Process child;
        try
        {
            var psi = new ProcessStartInfo(fileName) { UseShellExecute = false };
            foreach (var arg in arguments)
                psi.ArgumentList.Add(arg);

            child = Process.Start(psi)
                ?? throw new InvalidOperationException("Process.Start returned null.");
        }
        catch (Exception ex)
        {
            // Spawn failure aborts before touching anything else (mirrors remote-daemon-restart's
            // existing DaemonRelauncher.TrySpawnReplacement precedent) — never report a
            // successful background launch when the child was never actually created.
            return new SpawnResult(
                SpawnSucceeded: false, ExitCode: 1,
                Message: $"Failed to spawn background daemon: {ex.Message}");
        }

        var probe    = statusProbe ?? DefaultStatusProbeAsync;
        var budget   = confirmationBudget ?? DefaultConfirmationBudget;
        var interval = pollInterval ?? DefaultPollInterval;

        var confirmed = await PollAsync(port, probe, budget, interval).ConfigureAwait(false);

        var message = confirmed
            ? $"Spawned background daemon (pid {child.Id}), confirmed listening on " +
              $"http://127.0.0.1:{port}. Log directory: {logDirectory}"
            : $"Spawned background daemon (pid {child.Id}) but could not confirm it is " +
              $"listening yet within {budget.TotalSeconds:0.#}s — check the log directory: {logDirectory}";

        // The spawn itself already succeeded — a slow-to-confirm child still exits 0
        // (design.md Decision 5): an unconfirmed silent exit would be exactly the
        // unobservability Decision 4 exists to avoid, but a slow-but-fine startup is not a
        // failure either.
        return new SpawnResult(SpawnSucceeded: true, ExitCode: 0, Message: message);
    }

    private static async Task<bool> PollAsync(
        int port, Func<int, CancellationToken, Task<bool>> probe, TimeSpan budget, TimeSpan interval)
    {
        var deadline = DateTime.UtcNow + budget;

        while (DateTime.UtcNow < deadline)
        {
            try
            {
                if (await probe(port, CancellationToken.None).ConfigureAwait(false))
                    return true;
            }
            catch
            {
                // Connection refused / not listening yet / transient fault — keep polling
                // until the budget is exhausted.
            }

            var remaining = deadline - DateTime.UtcNow;
            if (remaining <= TimeSpan.Zero)
                break;

            await Task.Delay(remaining < interval ? remaining : interval).ConfigureAwait(false);
        }

        return false;
    }

    private static async Task<bool> DefaultStatusProbeAsync(int port, CancellationToken ct)
    {
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
        var response = await http.GetAsync($"http://127.0.0.1:{port}/api/v1/status", ct)
            .ConfigureAwait(false);
        return response.IsSuccessStatusCode;
    }
}
