namespace OpenWSFZ.Abstractions;

/// <summary>
/// Thrown by <see cref="IAudioSource"/> implementations when a device cannot
/// be opened or capture fails unrecoverably.
/// </summary>
public sealed class AudioCaptureException : Exception
{
    /// <summary>The device ID that could not be opened.</summary>
    public string DeviceId { get; }

    /// <summary>Human-readable explanation of the failure.</summary>
    public string Reason { get; }

    public AudioCaptureException(string deviceId, string reason)
        : base($"Cannot capture from device '{deviceId}': {reason}")
    {
        DeviceId = deviceId;
        Reason   = reason;
    }
}
