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

    // ── Task 8.7 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-006: Default config contains expected fields")]
    public void DefaultAppConfig_HasExpectedFieldValues()
    {
        var config = new AppConfig();

        config.AudioDeviceName.Should().BeNull(
            "no audio device is selected by default");
        config.Port.Should().Be(8080,
            "the default HTTP port is 8080");
    }
}
