using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Unit tests for <see cref="ConfigPathResolver"/> priority resolution and
/// the default <see cref="AppConfig"/> field values.
/// </summary>
public sealed class ConfigPathResolverTests
{
    private const string EnvVar = "OPENWSFZ_CONFIG";

    // ── Task 8.4 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-005: ConfigPathResolver returns CLI flag path when provided")]
    public void Resolve_ReturnsFlagPath_WhenCliOverrideProvided()
    {
        var (resolvedPath, source) = ConfigPathResolver.Resolve("/custom/override/config.json");

        resolvedPath.Should().Be("/custom/override/config.json");
        source.Should().Be("--config flag");
    }

    // ── Task 8.5 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-005: ConfigPathResolver falls back to OPENWSFZ_CONFIG env var")]
    public void Resolve_ReturnsEnvVarPath_WhenNoCliOverride()
    {
        var original = Environment.GetEnvironmentVariable(EnvVar);
        try
        {
            Environment.SetEnvironmentVariable(EnvVar, "/env/var/config.json");

            var (resolvedPath, source) = ConfigPathResolver.Resolve(null);

            resolvedPath.Should().Be("/env/var/config.json");
            source.Should().Contain(EnvVar);
        }
        finally
        {
            Environment.SetEnvironmentVariable(EnvVar, original);
        }
    }

    // ── Task 8.6 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-005: ConfigPathResolver returns platform default when no override")]
    public void Resolve_ReturnsPlatformDefault_WhenNoOverrideAndNoEnvVar()
    {
        var original = Environment.GetEnvironmentVariable(EnvVar);
        try
        {
            // Ensure no env var is set.
            Environment.SetEnvironmentVariable(EnvVar, null);

            var (resolvedPath, _) = ConfigPathResolver.Resolve(null);

            resolvedPath.Should().EndWith(
                Path.Combine("OpenWSFZ", "config.json"),
                "the platform default must point to AppData/OpenWSFZ/config.json");
        }
        finally
        {
            Environment.SetEnvironmentVariable(EnvVar, original);
        }
    }

    // ── Environment-variable expansion ───────────────────────────────────────

    [Fact(DisplayName = "ConfigPathResolver expands OS env-var placeholders in the OPENWSFZ_CONFIG value")]
    public void Resolve_ExpandsPlaceholders_InEnvVarPath()
    {
        // %TEMP% exists on Windows; $TMPDIR or /tmp on macOS/Linux.
        // Environment.ExpandEnvironmentVariables handles both conventions.
        var original = Environment.GetEnvironmentVariable(EnvVar);
        try
        {
            var rawPath  = Path.Combine("%TEMP%", "owsfz-test", "config.json");
            var expected = Path.Combine(
                Environment.ExpandEnvironmentVariables("%TEMP%"), "owsfz-test", "config.json");

            Environment.SetEnvironmentVariable(EnvVar, rawPath);

            var (resolvedPath, source) = ConfigPathResolver.Resolve(null);

            resolvedPath.Should().Be(expected,
                "the resolver must expand OS environment-variable placeholders in OPENWSFZ_CONFIG " +
                "so that values such as %APPDATA%\\OpenWSFZ\\config.json in launchSettings.json " +
                "are resolved to real paths at runtime");
            source.Should().Contain(EnvVar);
        }
        finally
        {
            Environment.SetEnvironmentVariable(EnvVar, original);
        }
    }

    [Fact(DisplayName = "ConfigPathResolver expands OS env-var placeholders in the --config CLI override")]
    public void Resolve_ExpandsPlaceholders_InCliOverride()
    {
        var rawPath  = Path.Combine("%TEMP%", "owsfz-cli", "config.json");
        var expected = Path.Combine(
            Environment.ExpandEnvironmentVariables("%TEMP%"), "owsfz-cli", "config.json");

        var (resolvedPath, source) = ConfigPathResolver.Resolve(rawPath);

        resolvedPath.Should().Be(expected,
            "the resolver must expand OS environment-variable placeholders in the --config flag value");
        source.Should().Be("--config flag");
    }

    [Fact(DisplayName = "ConfigPathResolver leaves plain paths unchanged (no placeholders)")]
    public void Resolve_LeavesPlainPaths_Unchanged()
    {
        var (resolvedPath, source) = ConfigPathResolver.Resolve("/plain/path/config.json");

        resolvedPath.Should().Be("/plain/path/config.json",
            "a path without placeholders must pass through unmodified");
        source.Should().Be("--config flag");
    }

    // ── Task 8.7 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-006: Default config contains expected fields")]
    public void DefaultAppConfig_HasExpectedFieldValues()
    {
        var config = new AppConfig();

        config.AudioDeviceId.Should().BeNull(
            "no audio device is selected by default");
        config.Port.Should().Be(8080,
            "the default HTTP port is 8080");
    }
}
