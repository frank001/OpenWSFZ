namespace OpenWSFZ.Daemon;

/// <summary>
/// Writes the bootstrap <c>"[OpenWSFZ] Config: {source} → {path}"</c> line directly to stderr,
/// before the config store or logging pipeline exist — this is the earliest possible point in
/// startup, so there is no logger yet for it to go through instead.
/// </summary>
internal static class ConfigPathAnnouncer
{
    /// <summary>
    /// Writes the config-path line to stderr, unless <paramref name="isBackgroundWorker"/> is
    /// <see langword="true"/> (daemon-background-mode, design.md Decision 6): a background
    /// worker has already detached from its inherited console by the time this would run
    /// (<c>Program.cs</c> calls <see cref="ConsoleDetacher.Detach"/> first), so a direct
    /// <see cref="Console.Error"/> write here could throw against an invalid handle on
    /// Windows. Its Information-level logged equivalent (<c>daemon-host</c>'s existing
    /// "Resolved config path logged at startup" requirement) reaches the file sink once the
    /// logger exists a few lines later in <c>Program.cs</c>, so nothing is lost by skipping it.
    /// Defaults to <see langword="false"/> so existing callers/tests are unaffected.
    /// </summary>
    public static void Announce(string configSource, string configPath, bool isBackgroundWorker = false)
    {
        if (isBackgroundWorker)
            return;

        Console.Error.WriteLine($"[OpenWSFZ] Config: {configSource} → {configPath}");
    }
}
