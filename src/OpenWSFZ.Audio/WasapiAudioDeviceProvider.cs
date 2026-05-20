using System.Runtime.Versioning;
using NAudio.CoreAudioApi;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Enumerates WASAPI capture endpoints on Windows using NAudio's
/// <see cref="MMDeviceEnumerator"/>. COM initialisation is handled internally
/// by NAudio.Wasapi.
/// </summary>
[SupportedOSPlatform("windows")]
internal sealed class WasapiAudioDeviceProvider : IAudioDeviceProvider
{
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
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

        return Task.FromResult<IReadOnlyList<AudioDeviceInfo>>(devices);
    }
}
