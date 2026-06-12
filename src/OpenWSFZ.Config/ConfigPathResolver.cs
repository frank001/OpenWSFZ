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
    private const string EnvVar      = "OPENWSFZ_CONFIG";
    private const string AppDirName  = "OpenWSFZ";
    private const string ConfigFile  = "config.json";

    /// <summary>
    /// Resolves the config file path and returns both the resolved path and its source
    /// (for logging at startup).
    /// Windows environment-variable placeholders (e.g. <c>%APPDATA%</c>) in the CLI
    /// override and the <c>OPENWSFZ_CONFIG</c> environment variable are expanded so that
    /// values from <c>launchSettings.json</c> work correctly in both IDE and
    /// <c>dotnet run</c> contexts.
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

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static string PlatformDefault()
    {
        // Environment.GetFolderPath returns:
        //   Windows  → %APPDATA%                              (e.g. C:\Users\<user>\AppData\Roaming)
        //   Linux    → $XDG_CONFIG_HOME or ~/.config
        //   macOS    → ~/Library/Application Support
        var appData = Environment.GetFolderPath(
            Environment.SpecialFolder.ApplicationData,
            Environment.SpecialFolderOption.DoNotVerify);

        return Path.Combine(appData, AppDirName, ConfigFile);
    }
}
