using System.Runtime.CompilerServices;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Points the daemon's config location at a throwaway temp file for the whole Web.Tests process,
/// before any test can start <c>Program</c>.
/// <para>
/// Why: every <c>WebApplicationFactory&lt;Program&gt;</c> run executes the daemon's top-level
/// start-up, which resolves the config path and runs <c>new JsonConfigStore(path)</c> at once,
/// BEFORE the test factories swap <c>IConfigStore</c> for an in-memory double. With no override the
/// path is the machine's real per-user config (<c>%APPDATA%\OpenWSFZ\config.json</c>; on the
/// station that is the live config), which the store loads, migrates and rewrites, and the
/// frequency / prop-mode / callsign state files are created beside it. Setting the resolver's
/// second-priority variable <c>OPENWSFZ_CONFIG</c> (see <c>ConfigPathResolver</c>) redirects all of
/// it to a temp directory. The temp directory is deleted at process exit.
/// </para>
/// <para>
/// The factories set no config path of their own, and no test here asserts on the platform default
/// path or relies on <c>OPENWSFZ_CONFIG</c> being unset (checked 2026-10-02).
/// </para>
/// </summary>
internal static class IsolatedConfigModule
{
    /// <summary>The environment variable <c>ConfigPathResolver</c> consults after the <c>--config</c> flag.</summary>
    internal const string ConfigEnvVar = "OPENWSFZ_CONFIG";

    /// <summary>The isolated temp directory holding the config file and the state files beside it.</summary>
    internal static string TempDirectory { get; } = Path.Combine(
        Path.GetTempPath(), "openwsfz-web-tests-" + Path.GetRandomFileName());

    /// <summary>The isolated config file path (not created here; the daemon's store creates it on first load).</summary>
    internal static string ConfigPath => Path.Combine(TempDirectory, "config.json");

#pragma warning disable CA2255 // The module initializer is deliberate: it must run before any test can start Program.
    [ModuleInitializer]
    internal static void Initialize()
    {
        Directory.CreateDirectory(TempDirectory);
        Environment.SetEnvironmentVariable(ConfigEnvVar, ConfigPath);

        // Seed the config and the state files once, sequentially, so every later Program start-up
        // (several test classes start one concurrently) only READS existing files. Against an empty
        // directory they would race to create them (the stores' temp-file renames fail with
        // IOException / UnauthorizedAccessException).
        _ = new OpenWSFZ.Config.JsonConfigStore(ConfigPath);
        new OpenWSFZ.Daemon.FrequencyStore(Path.Combine(TempDirectory, "frequencies.json")).LoadAsync().GetAwaiter().GetResult();
        new OpenWSFZ.Daemon.PropModeStore(Path.Combine(TempDirectory, "prop-modes.json")).LoadAsync().GetAwaiter().GetResult();
        new OpenWSFZ.Daemon.CallsignGrammarStore(Path.Combine(TempDirectory, "callsign-grammar.json")).LoadAsync().GetAwaiter().GetResult();
        new OpenWSFZ.Daemon.CallsignRegionStore(Path.Combine(TempDirectory, "callsign-regions.json")).LoadAsync().GetAwaiter().GetResult();

        AppDomain.CurrentDomain.ProcessExit += (_, _) =>
        {
            try { Directory.Delete(TempDirectory, recursive: true); } catch { /* best-effort */ }
        };
    }
#pragma warning restore CA2255
}
