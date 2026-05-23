namespace OpenWSFZ.Web;

/// <summary>
/// Tracks whether any audio chunk has been received from the capture pipeline
/// since the last heartbeat-window reset.
///
/// Unlike <see cref="AudioActivityMonitor"/>, this does not inspect sample
/// amplitude — any chunk receipt (including near-silence below the FT8 signal
/// threshold) counts as data flowing. This makes it the correct signal source
/// for <see cref="AudioWatchdog"/>: a working WASAPI device always delivers
/// buffers even when the radio frequency is quiet, so a dry window indicates
/// a genuine driver-level silent stall rather than a quiet transmission band.
/// </summary>
public sealed class DataFlowMonitor
{
    private volatile bool _flowing;

    /// <summary>
    /// Called from the capture thread for every chunk received, regardless of amplitude.
    /// Thread-safe; may be called concurrently with <see cref="ConsumeAndReset"/>.
    /// </summary>
    public void OnChunkReceived() => _flowing = true;

    /// <summary>
    /// Returns <c>true</c> if any chunk was received since the last reset, then
    /// atomically resets the flag for the next heartbeat window.
    /// </summary>
    public bool ConsumeAndReset()
    {
        var value = _flowing;
        _flowing  = false;
        return value;
    }

    /// <summary>
    /// Clears the flowing flag. Call whenever the capture pipeline is restarted
    /// so stale flow state from the previous session does not carry over.
    /// </summary>
    public void Reset() => _flowing = false;
}
