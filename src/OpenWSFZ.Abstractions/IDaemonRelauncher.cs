namespace OpenWSFZ.Abstractions;

/// <summary>
/// Spawns a replacement daemon process as part of an API-initiated restart
/// (remote-daemon-restart). Implemented by <c>DaemonRelauncher</c> in the Daemon assembly;
/// injected into the web layer via DI so <c>POST /api/v1/system/restart</c> can trigger a
/// self re-exec without depending on the Daemon assembly (mirrors <see cref="ICatController"/>'s
/// existing narrow-seam pattern).
/// </summary>
public interface IDaemonRelauncher
{
    /// <summary>
    /// Resolves and spawns a new instance of the current process — same executable and CLI
    /// arguments, plus a marker identifying it as a relaunch — so it can begin binding the
    /// listening port before the current instance stops. Logs the resolved command at
    /// Information before spawning.
    /// </summary>
    /// <returns>
    /// <c>true</c> if the child process was confirmed to start; <c>false</c> if the spawn
    /// itself failed (already logged) — the caller MUST NOT stop the current instance in that
    /// case, since nothing would be left running to serve requests.
    /// </returns>
    bool TrySpawnReplacement();
}
