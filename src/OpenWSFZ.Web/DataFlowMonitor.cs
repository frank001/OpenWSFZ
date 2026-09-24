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
    // Sentinel for "no chunk received yet this process" — long.MinValue is never a value
    // TimeProvider.GetTimestamp() (Stopwatch-style monotonic ticks, always non-negative in
    // practice) would ever return, so it is safe as an unambiguous "unset" marker.
    private const long NoChunkSentinel = long.MinValue;

    private readonly TimeProvider _timeProvider;
    private volatile bool         _flowing;
    private long                  _lastChunkTimestampRaw = NoChunkSentinel;

    /// <param name="timeProvider">
    /// Clock used to timestamp chunk arrivals for <see cref="LastChunkAgeMs"/> (design.md
    /// Decision 2, capture-stall-detection-unattended #188). Defaults to
    /// <see cref="TimeProvider.System"/>; unit tests pass a fake provider so the age can be
    /// advanced deterministically without a real sleep (design D2, U4).
    /// </param>
    public DataFlowMonitor(TimeProvider? timeProvider = null)
    {
        _timeProvider = timeProvider ?? TimeProvider.System;
    }

    /// <summary>
    /// Called from the capture thread for every chunk received, regardless of amplitude.
    /// Thread-safe; may be called concurrently with <see cref="ConsumeAndReset"/>.
    /// Also stamps the monotonic arrival time consumed by <see cref="LastChunkAgeMs"/>.
    /// </summary>
    public void OnChunkReceived()
    {
        _flowing = true;
        Interlocked.Exchange(ref _lastChunkTimestampRaw, _timeProvider.GetTimestamp());
    }

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
    /// <remarks>
    /// 🔴 Deliberately does NOT clear <see cref="LastChunkAgeMs"/>'s underlying timestamp
    /// (design.md Decision 2, capture-stall-detection-unattended #188). A restart that then
    /// fails to deliver anything must keep ageing from the last real chunk, not read back as
    /// "unknown" — clearing it here would hide exactly the #187 failure mode (a restart loop
    /// against a dead device) from an HTTP-only poller.
    /// </remarks>
    public void Reset() => _flowing = false;

    /// <summary>
    /// Milliseconds elapsed since the most recent chunk was received, computed fresh at call
    /// time from the injected monotonic clock — not stored, so it is correct to the millisecond
    /// at the moment of the read (design.md Decision 2). <c>null</c> only before the first chunk
    /// of the process; a pipeline restart (<see cref="Reset"/>) does not affect it.
    /// </summary>
    public int? LastChunkAgeMs
    {
        get
        {
            var timestamp = Interlocked.Read(ref _lastChunkTimestampRaw);
            if (timestamp == NoChunkSentinel) return null;

            var elapsedMs = _timeProvider.GetElapsedTime(timestamp).TotalMilliseconds;
            // Defensive clamp: a fake TimeProvider driven backwards in a test, or sub-tick
            // rounding, must never surface as a negative age.
            return elapsedMs < 0 ? 0 : (int)Math.Min(elapsedMs, int.MaxValue);
        }
    }
}
