namespace OpenWSFZ.Daemon;

/// <summary>
/// CLI-derived launch options parsed before host construction.
/// </summary>
internal sealed record LaunchOptions(
    int? Port = null, string? ConfigPath = null, int? RelaunchedFromPid = null,
    bool Background = false, bool IsBackgroundWorker = false)
{
    /// <summary>
    /// Parses <paramref name="args"/> and returns a <see cref="LaunchOptions"/> instance.
    /// Recognised arguments:
    /// <list type="bullet">
    ///   <item><c>--port &lt;n&gt;</c> — bind port override (when absent, the persisted config value is used)</item>
    ///   <item><c>--config &lt;path&gt;</c> — override config file path (default: platform/env-var resolution)</item>
    ///   <item><c>--relaunched-from &lt;pid&gt;</c> — identifies this instance as having been
    ///     spawned to replace another instance as part of an API-initiated restart
    ///     (remote-daemon-restart). Absence means an ordinary cold start, exactly as before
    ///     this flag existed. A build that predates this flag silently ignores it (unknown
    ///     arguments are already ignored below), so it is safe to pass unconditionally.</item>
    ///   <item><c>--background</c> — operator-facing (daemon-background-mode). Present at what
    ///     is otherwise an ordinary cold start: spawn a detached replacement of this instance
    ///     (with <c>--background-worker</c> appended) and exit once that spawn is confirmed.
    ///     A plain boolean presence flag — takes no value.</item>
    ///   <item><c>--background-worker</c> — internal marker (daemon-background-mode) identifying
    ///     that this instance IS the detached worker (spawned by <c>--background</c>, or by a
    ///     restart of an already-background instance): detach from the inherited console/
    ///     controlling terminal before any other startup work, and never spawn another child.
    ///     A plain boolean presence flag — takes no value.</item>
    /// </list>
    /// Unknown arguments are silently ignored (forward-compatible).
    /// </summary>
    public static LaunchOptions Parse(string[] args)
    {
        int?    port               = null;
        string? configPath         = null;
        int?    relaunchedFromPid  = null;
        bool    background         = false;
        bool    isBackgroundWorker = false;

        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--port" && i + 1 < args.Length &&
                int.TryParse(args[i + 1], out var p) && p is > 0 and < 65536)
            {
                port = p;
                i++;
            }
            else if (args[i] == "--config" && i + 1 < args.Length && !string.IsNullOrWhiteSpace(args[i + 1]))
            {
                configPath = args[i + 1];
                i++;
            }
            else if (args[i] == "--relaunched-from" && i + 1 < args.Length &&
                     int.TryParse(args[i + 1], out var pid))
            {
                relaunchedFromPid = pid;
                i++;
            }
            else if (args[i] == "--background")
            {
                background = true;
            }
            else if (args[i] == "--background-worker")
            {
                isBackgroundWorker = true;
            }
        }

        return new LaunchOptions(
            Port: port, ConfigPath: configPath, RelaunchedFromPid: relaunchedFromPid,
            Background: background, IsBackgroundWorker: isBackgroundWorker);
    }
}
