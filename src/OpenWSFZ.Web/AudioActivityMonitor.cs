namespace OpenWSFZ.Web;

/// <summary>
/// Tracks whether any audio sample with absolute value greater than 1×10⁻⁶
/// has been received since the last heartbeat-window reset (FR-020).
///
/// <para>
/// The threshold (1e-6f) matches the RMS silence guard in
/// <c>Ft8Decoder.DecodeAsync</c>. Keep both values in sync if the guard changes.
/// </para>
///
/// <para>
/// Thread-safety: <see cref="ObserveSamples"/> may be called from any thread
/// (e.g. the audio capture thread).  The <c>volatile bool _active</c> flag
/// ensures visibility without a lock; at most one spurious false-negative per
/// heartbeat interval is possible and is acceptable per the spec.
/// </para>
/// </summary>
public sealed class AudioActivityMonitor
{
    /// <summary>
    /// Threshold matching the RMS silence guard in <c>Ft8Decoder</c> (1×10⁻⁶).
    /// </summary>
    private const float Threshold = 1e-6f;

    private volatile bool _active;

    /// <summary>
    /// Scans <paramref name="chunk"/> for any sample whose absolute value exceeds
    /// <see cref="Threshold"/>.  Short-circuits as soon as one is found.
    /// Safe to call from any thread.
    /// </summary>
    public void ObserveSamples(float[] chunk)
    {
        if (_active) return; // short-circuit: already flagged for this window
        foreach (var s in chunk)
        {
            if (MathF.Abs(s) > Threshold)
            {
                _active = true;
                return;
            }
        }
    }

    /// <summary>
    /// Returns the current activity state WITHOUT resetting the window.
    /// Used for the initial <c>status</c> event (reflects all activity since
    /// application start or the last pipeline restart).
    /// </summary>
    public bool IsActive => _active;

    /// <summary>
    /// Returns the current activity state and atomically resets the window
    /// for the next heartbeat interval.
    /// Called at each 5-second heartbeat emission.
    /// </summary>
    public bool ConsumeAndReset()
    {
        var value = _active;
        _active   = false;
        return value;
    }

    /// <summary>
    /// Resets the activity window.  Call on pipeline restart so the new capture
    /// session starts fresh without inheriting stale activity.
    /// </summary>
    public void Reset() => _active = false;
}
