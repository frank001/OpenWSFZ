using System.Linq;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

/// <summary>
/// FR-073 (capture-device-reresolution #187, tasks.md 1.4): the real NAudio enumeration path
/// itself is untestable off real hardware, so these tests exercise the provider's internal
/// test-only <c>enumerateOverride</c> seam instead — the same seam <c>WasapiAudioDeviceProviderTests</c>
/// (in <c>CaptureManagerTests.cs</c>) already uses to simulate NAudio/COM failures — to confirm
/// <see cref="AudioDeviceInfo.Available"/> flows through
/// <see cref="WasapiAudioDeviceProvider.GetDevicesAsync"/> unmodified. Windows-only at runtime,
/// mirroring that sibling class's own guard style (not an assembly-wide <c>#if</c>, so the file
/// still compiles on non-Windows CI).
/// </summary>
public sealed class WasapiAudioDeviceProviderAvailabilityTests
{
    [Fact(DisplayName = "FR-073: a disabled WASAPI endpoint is listed with Available: false")]
    public async Task GetDevicesAsync_ReportsAvailableFalse_ForDisabledEndpoint()
    {
        if (!OperatingSystem.IsWindows())
            return; // WASAPI is not available on non-Windows platforms — skip silently.

#if WASAPI_SUPPORTED
        var provider = new WasapiAudioDeviceProvider(
            NullLogger<WasapiAudioDeviceProvider>.Instance,
            enumerateOverride: () => [new AudioDeviceInfo("id-1", "Disabled Mic", Available: false)]);

        var devices = await provider.GetDevicesAsync();

        devices.Should().ContainSingle().Which.Available.Should().BeFalse(
            "a WASAPI endpoint whose DeviceState is not Active must report Available = false");
#endif
    }

    [Fact(DisplayName = "FR-073: an active WASAPI endpoint is listed with Available: true")]
    public async Task GetDevicesAsync_ReportsAvailableTrue_ForActiveEndpoint()
    {
        if (!OperatingSystem.IsWindows())
            return;

#if WASAPI_SUPPORTED
        var provider = new WasapiAudioDeviceProvider(
            NullLogger<WasapiAudioDeviceProvider>.Instance,
            enumerateOverride: () => [new AudioDeviceInfo("id-2", "Active Mic", Available: true)]);

        var devices = await provider.GetDevicesAsync();

        devices.Should().ContainSingle().Which.Available.Should().BeTrue();
#endif
    }

    [Fact(DisplayName = "FR-073: mixed active/disabled endpoints each report their own availability independently")]
    public async Task GetDevicesAsync_ReportsIndependentAvailability_ForMixedEndpoints()
    {
        if (!OperatingSystem.IsWindows())
            return;

#if WASAPI_SUPPORTED
        var provider = new WasapiAudioDeviceProvider(
            NullLogger<WasapiAudioDeviceProvider>.Instance,
            enumerateOverride: () =>
            [
                new AudioDeviceInfo("id-active",   "Active Mic",   Available: true),
                new AudioDeviceInfo("id-disabled", "Disabled Mic", Available: false),
            ]);

        var devices = await provider.GetDevicesAsync();

        devices.Should().HaveCount(2);
        devices.Single(d => d.Id == "id-active").Available.Should().BeTrue();
        devices.Single(d => d.Id == "id-disabled").Available.Should().BeFalse();
#endif
    }
}
