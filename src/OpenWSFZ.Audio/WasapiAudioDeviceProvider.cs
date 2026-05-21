#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
using NAudio.CoreAudioApi;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

// NOTE: NAudio's MMDeviceEnumerator uses [ComImport] COM activation, which is incompatible
// with NativeAOT (BuiltInComInterop.IsSupported=false). The AOT-published binary therefore
// cannot enumerate or capture WASAPI devices. Development and testing use dotnet run (JIT,
// no RID), where COM interop is available. Resolution: replace [ComImport] usage with
// ComWrappers. Tracked as a Phase 6 item.

/// <summary>
/// Enumerates WASAPI capture endpoints on Windows using NAudio's
/// <see cref="MMDeviceEnumerator"/>. All COM work is dispatched to a dedicated
/// STA background thread via <see cref="StaThread"/> to satisfy WASAPI's
/// apartment-threading requirement.
/// </summary>
[SupportedOSPlatform("windows")]
internal sealed class WasapiAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly ILogger<WasapiAudioDeviceProvider> _log;

    /// <summary>
    /// Optional test seam — replaces the real NAudio enumeration call when set.
    /// The delegate may throw to simulate COM / NAudio failures; the catch block
    /// will handle it and log a warning exactly as it would for a real failure.
    /// </summary>
    private readonly Func<IReadOnlyList<AudioDeviceInfo>>? _enumerateOverride;

    public WasapiAudioDeviceProvider(ILogger<WasapiAudioDeviceProvider> log)
        => _log = log;

    /// <summary>Test-only constructor — injects a delegate in place of the NAudio call.</summary>
    internal WasapiAudioDeviceProvider(
        ILogger<WasapiAudioDeviceProvider>    log,
        Func<IReadOnlyList<AudioDeviceInfo>>  enumerateOverride)
        => (_log, _enumerateOverride) = (log, enumerateOverride);

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => StaThread.Run(EnumerateDevices);

    private IReadOnlyList<AudioDeviceInfo> EnumerateDevices()
    {
        var devices = new List<AudioDeviceInfo>();

        try
        {
            // Test hook — bypass NAudio when a seam has been injected.
            if (_enumerateOverride is not null)
                return _enumerateOverride(); // may throw; the catch below handles it

            using var enumerator = new MMDeviceEnumerator();

            // Include DeviceState.Disabled so that devices present but disabled in
            // Windows Sound Settings still appear in the list.  DeviceState.Active
            // alone was the original filter, but it prevented the user from seeing
            // (and re-enabling) a device that had been turned off.
            var endpoints = enumerator.EnumerateAudioEndPoints(
                DataFlow.Capture, DeviceState.Active | DeviceState.Disabled);

            foreach (var ep in endpoints)
            {
                devices.Add(new AudioDeviceInfo(
                    Id:   ep.ID,
                    Name: ep.FriendlyName));
            }
        }
        catch (Exception ex)
        {
            // Never silently swallow — log a warning so that COM errors, Windows Audio
            // service failures, and NAudio internals are visible in the application log.
            _log.LogWarning(ex,
                "WASAPI device enumeration failed; returning {Count} device(s) collected before the error.",
                devices.Count);
        }

        return devices;
    }
}
#endif
