namespace OpenWSFZ.Web;

/// <summary>
/// Belt-and-suspenders watchdog for audio capture silence (S6).
///
/// Called once per heartbeat window (every 5 seconds) with the activity flag
/// already consumed by <c>AudioActivityMonitor.ConsumeAndReset()</c> in the
/// heartbeat loop. Do NOT call ConsumeAndReset inside this class — the window
/// has already been consumed and a second call would always return false.
///
/// Triggers a pipeline restart when <see cref="_threshold"/> consecutive silent
/// windows occur while <see cref="_isCapturing"/> returns true. Covers silent-stop
/// scenarios that no WASAPI event handler can detect (e.g. driver bugs, VM
/// audio pass-through).
/// </summary>
internal sealed class AudioWatchdog
{
    private readonly Func<bool> _isCapturing;
    private readonly Func<Task> _onRestart;
    private readonly int        _threshold;
    private int                 _silentWindows;
    private int                 _restartCount;

    /// <summary>
    /// Process-lifetime count of times the watchdog's threshold has fired and a restart was
    /// invoked (design.md Decision 7, capture-stall-detection-unattended #188). Counts fired
    /// triggers, not successful reconnects — a restart that itself fails to reconnect still
    /// counts, since the ticker has attempted one restart either way. Incremented at the moment
    /// the threshold is reached, before <c>_onRestart</c> is awaited, so a caller can read the
    /// updated count immediately after <see cref="TickAsync"/> returns without racing a
    /// slow-to-complete restart action.
    /// </summary>
    public int RestartCount => Volatile.Read(ref _restartCount);

    /// <param name="isCapturing">
    /// Returns true while the capture pipeline is active.
    /// The watchdog does not trigger when this returns false — a stopped
    /// pipeline is not a malfunction.
    /// </param>
    /// <param name="onRestart">
    /// Async action to restart the pipeline. Must catch its own exceptions and
    /// log them; any exception that escapes will be silently swallowed by the
    /// discarded ValueTask at the call site.
    /// </param>
    /// <param name="threshold">
    /// Number of consecutive silent windows before triggering a restart.
    /// Default design: 3 × 5 s = 15 s, which survives the 12.64-second FT8
    /// transmission gap.
    /// </param>
    public AudioWatchdog(
        Func<bool> isCapturing,
        Func<Task> onRestart,
        int        threshold)
    {
        _isCapturing   = isCapturing;
        _onRestart     = onRestart;
        _threshold     = threshold;
        _silentWindows = 0;
    }

    /// <summary>
    /// Advances the watchdog state for one heartbeat window.
    /// </summary>
    /// <param name="dataWasFlowing">
    /// The value returned by <c>DataFlowMonitor.ConsumeAndReset()</c> in the
    /// heartbeat loop for this window. Any chunk receipt — regardless of
    /// amplitude — counts as data flowing. This correctly distinguishes a
    /// genuine WASAPI silent-stall (no buffers delivered) from a quiet radio
    /// frequency (buffers delivered but samples below the FT8 signal threshold).
    /// </param>
    public async ValueTask TickAsync(bool dataWasFlowing)
    {
        if (dataWasFlowing || !_isCapturing())
        {
            _silentWindows = 0;
            return;
        }

        if (++_silentWindows >= _threshold)
        {
            _silentWindows = 0;
            Interlocked.Increment(ref _restartCount);
            await _onRestart();
        }
    }
}
