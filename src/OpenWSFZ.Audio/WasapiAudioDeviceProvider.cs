#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using NAudio.CoreAudioApi;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Enumerates WASAPI capture endpoints on Windows using NAudio's
/// <see cref="MMDeviceEnumerator"/>. All COM work is dispatched to a dedicated
/// STA background thread via <see cref="StaThread"/> to satisfy WASAPI's
/// apartment-threading requirement.
/// </summary>
[SupportedOSPlatform("windows")]
internal sealed class WasapiAudioDeviceProvider : IAudioDeviceProvider
{
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => StaThread.Run(EnumerateDevices);

    private static IReadOnlyList<AudioDeviceInfo> EnumerateDevices()
    {
        var devices = new List<AudioDeviceInfo>();

        try
        {
            using var enumerator = new MMDeviceEnumerator();
            var endpoints = enumerator.EnumerateAudioEndPoints(
                DataFlow.Capture, DeviceState.Active);

            foreach (var ep in endpoints)
            {
                devices.Add(new AudioDeviceInfo(
                    Id:   ep.ID,
                    Name: ep.FriendlyName));
            }
        }
        catch
        {
            // Return whatever we collected; never throw.
        }

        return devices;
    }
}
#endif
