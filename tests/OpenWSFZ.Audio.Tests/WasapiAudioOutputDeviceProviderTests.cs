using System.Runtime.Versioning;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

// ── Task 8.2 — SubprocessAudioOutputDeviceProvider stub ──────────────────────

public sealed class SubprocessAudioOutputDeviceProviderTests
{
    [Fact(DisplayName = "FR-NEW: SubprocessAudioOutputDeviceProvider returns empty list without throwing")]
    public async Task GetDevicesAsync_ReturnsEmptyList_WithoutThrowing()
    {
        // Arrange
        var provider = new SubprocessAudioOutputDeviceProvider(
            NullLogger<SubprocessAudioOutputDeviceProvider>.Instance);

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert
        devices.Should().BeEmpty(
            "the Linux/macOS stub must return an empty list without throwing");
    }
}

#if WASAPI_SUPPORTED

// ── Task 8.1 — WasapiAudioOutputDeviceProvider ───────────────────────────────

[SupportedOSPlatform("windows")]
public sealed class WasapiAudioOutputDeviceProviderTests
{
    [Fact(DisplayName = "FR-NEW: WasapiAudioOutputDeviceProvider returns device list via enumerate override")]
    public async Task GetDevicesAsync_ReturnsDevices_WhenEnumerateOverrideSucceeds()
    {
        // Arrange: inject the test seam with a known list of render devices.
        var expected = new List<AudioDeviceInfo>
        {
            new("{render-guid-1}", "Speakers (Realtek)"),
            new("{render-guid-2}", "Headphones (USB Audio)"),
        };

        var provider = new WasapiAudioOutputDeviceProvider(
            NullLogger<WasapiAudioOutputDeviceProvider>.Instance,
            () => expected);

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert
        devices.Should().HaveCount(2);
        devices[0].Id.Should().Be("{render-guid-1}");
        devices[0].Name.Should().Be("Speakers (Realtek)");
        devices[1].Id.Should().Be("{render-guid-2}");
        devices[1].Name.Should().Be("Headphones (USB Audio)");
    }

    [Fact(DisplayName = "FR-NEW: WasapiAudioOutputDeviceProvider returns empty list and does not throw when enumerate override throws")]
    public async Task GetDevicesAsync_ReturnsEmptyList_WhenEnumerateOverrideThrows()
    {
        // Arrange: seam throws to simulate COM / Windows Audio service failure.
        var provider = new WasapiAudioOutputDeviceProvider(
            NullLogger<WasapiAudioOutputDeviceProvider>.Instance,
            () => throw new InvalidOperationException("Simulated WASAPI failure"));

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert: must return an empty list — never throw.
        devices.Should().BeEmpty(
            "a WASAPI failure must produce an empty list, not an exception");
    }
}

#endif
