using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Tests for <see cref="LanModeValidator"/> — the SEC-001 startup guard.
/// </summary>
[Trait("Category", "Unit")]
public sealed class LanModeValidatorTests
{
    [Fact(DisplayName = "SEC-001: DaemonStartup_LanModeWithoutPassphrase_RefusesToStart")]
    public void IsValid_LanEnabledNullPassphrase_ReturnsFalseWithMessage()
    {
        var config = new RemoteAccessConfig(enabled: true, passphrase: null);

        var result = LanModeValidator.IsValid(config, out var error);

        result.Should().BeFalse("LAN mode without a passphrase must be rejected");
        error.Should().NotBeNullOrWhiteSpace("a human-readable error message must be provided");
        error!.ToLowerInvariant().Should().Contain("passphrase",
            "the error message must name the missing field");
    }

    [Fact(DisplayName = "SEC-001: DaemonStartup_LanModeWithEmptyPassphrase_RefusesToStart")]
    public void IsValid_LanEnabledEmptyPassphrase_ReturnsFalseWithMessage()
    {
        var config = new RemoteAccessConfig(enabled: true, passphrase: "");

        var result = LanModeValidator.IsValid(config, out var error);

        result.Should().BeFalse("LAN mode with an empty passphrase must be rejected");
        error.Should().NotBeNullOrWhiteSpace();
    }

    [Fact(DisplayName = "SEC-001: DaemonStartup_LanModeWithWhitespacePassphrase_RefusesToStart")]
    public void IsValid_LanEnabledWhitespacePassphrase_ReturnsFalseWithMessage()
    {
        var config = new RemoteAccessConfig(enabled: true, passphrase: "   ");

        var result = LanModeValidator.IsValid(config, out var error);

        result.Should().BeFalse("LAN mode with a whitespace-only passphrase must be rejected");
        error.Should().NotBeNullOrWhiteSpace();
    }

    [Fact(DisplayName = "SEC-001: DaemonStartup_LanModeWithPassphrase_Proceeds")]
    public void IsValid_LanEnabledNonEmptyPassphrase_ReturnsTrue()
    {
        var config = new RemoteAccessConfig(enabled: true, passphrase: "correcthorsebatterystaple");

        var result = LanModeValidator.IsValid(config, out var error);

        result.Should().BeTrue("a configured passphrase must allow LAN mode to start");
        error.Should().BeNull("no error message when config is valid");
    }

    [Fact(DisplayName = "SEC-001: DaemonStartup_LoopbackModeWithoutPassphrase_Proceeds")]
    public void IsValid_LanDisabledNullPassphrase_ReturnsTrue()
    {
        // Default configuration: RemoteAccess.Enabled = false, Passphrase = null.
        // The daemon must start normally regardless of passphrase when LAN mode is off.
        var config = new RemoteAccessConfig(enabled: false, passphrase: null);

        var result = LanModeValidator.IsValid(config, out var error);

        result.Should().BeTrue("loopback-only mode must start without any passphrase");
        error.Should().BeNull();
    }

    [Fact(DisplayName = "SEC-001: DaemonStartup_LoopbackModeWithPassphrase_Proceeds")]
    public void IsValid_LanDisabledWithPassphrase_ReturnsTrue()
    {
        var config = new RemoteAccessConfig(enabled: false, passphrase: "somekey");

        var result = LanModeValidator.IsValid(config, out var error);

        result.Should().BeTrue("loopback-only mode with a passphrase is valid");
        error.Should().BeNull();
    }
}
