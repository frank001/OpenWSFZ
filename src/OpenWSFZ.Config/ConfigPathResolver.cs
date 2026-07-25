namespace OpenWSFZ.Config;

/// <summary>
/// Resolves the configuration file path using the following precedence
/// (highest wins):
/// <list type="number">
///   <item>Explicit <paramref name="cliOverride"/> (from <c>--config</c> flag)</item>
///   <item><c>OPENWSFZ_CONFIG</c> environment variable</item>
///   <item>Platform default path under the OS application-data directory</item>
/// </list>
/// </summary>
public static class ConfigPathResolver
{
    private const string EnvVar         = "OPENWSFZ_CONFIG";
    private const string AppDirName     = "OpenWSFZ";
    private const string ConfigFile     = "config.json";
    private const string CycleAudioDir  = "cycle-audio";

    /// <summary>
    /// Resolves the config file path and returns both the resolved path and its source
    /// (for logging at startup).
    /// Windows environment-variable placeholders (e.g. <c>%APPDATA%</c>) in the CLI
    /// override and the <c>OPENWSFZ_CONFIG</c> environment variable are expanded, so
    /// that operators may supply Windows-style paths on the command line or in the
    /// environment without needing shell pre-expansion.
    /// The platform-default path is resolved directly via
    /// <see cref="Environment.GetFolderPath"/> and is never subject to string expansion.
    /// </summary>
    public static (string ResolvedPath, string Source) Resolve(string? cliOverride = null)
    {
        if (!string.IsNullOrWhiteSpace(cliOverride))
            return (Environment.ExpandEnvironmentVariables(cliOverride), "--config flag");

        var envValue = Environment.GetEnvironmentVariable(EnvVar);
        if (!string.IsNullOrWhiteSpace(envValue))
            return (Environment.ExpandEnvironmentVariables(envValue), $"${EnvVar} environment variable");

        return (PlatformDefault(), "platform default");
    }

    /// <summary>Returns only the resolved path (convenience overload).</summary>
    public static string ResolvePath(string? cliOverride = null) =>
        Resolve(cliOverride).ResolvedPath;

    /// <summary>
    /// Resolves the default directory for the cycle audio archive
    /// (<c>cycle-audio-archive</c> capability, design.md Decision 8) when no directory is
    /// explicitly configured. Uses the same platform-appropriate per-user application-data root
    /// as the config file itself (<c>%AppData%\OpenWSFZ\cycle-audio\</c> on Windows,
    /// <c>~/.config/OpenWSFZ/cycle-audio/</c> on Linux/macOS) — never the repository or the
    /// executable directory, because recordings contain real off-air audio and real
    /// third-party callsigns (NFR-021).
    /// </summary>
    public static string ResolveDefaultCycleAudioDirectory() =>
        Path.Combine(PlatformAppDataRoot(), AppDirName, CycleAudioDir);

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static string PlatformDefault() =>
        Path.Combine(PlatformAppDataRoot(), AppDirName, ConfigFile);

    private static string PlatformAppDataRoot()
    {
        // Environment.GetFolderPath returns:
        //   Windows  → %APPDATA%                              (e.g. C:\Users\<user>\AppData\Roaming)
        //   Linux    → $XDG_CONFIG_HOME or ~/.config
        //   macOS    → ~/Library/Application Support
        return Environment.GetFolderPath(
            Environment.SpecialFolder.ApplicationData,
            Environment.SpecialFolderOption.DoNotVerify);
    }
}
