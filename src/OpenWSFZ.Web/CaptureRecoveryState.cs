namespace OpenWSFZ.Web;

/// <summary>
/// Returned by <see cref="CaptureRecoveryState.RecordChunkReceived"/> only when a chunk arrives
/// while a failure streak was active — i.e. a genuine recovery just happened. <see langword="null"/>
/// on every other (already-healthy) call, so a caller can log the recovery Warning (design.md
/// Decision 6) exactly once per streak rather than once per chunk.
/// </summary>
/// <param name="Attempts">How many consecutive automatic attempts failed during the streak.</param>
/// <param name="Downtime">Wall-clock time between the first failure of the streak and this chunk.</param>
public sealed record CaptureRecoveryInfo(int Attempts, TimeSpan Downtime);

/// <summary>
/// Accumulates the capture-recovery counters exposed on <c>GET /api/v1/status</c> and the initial
/// WebSocket <c>status</c> event (capture-device-reresolution #187, design.md Decisions 4–5;
/// FR-071/FR-072). Thread-safe: <see cref="RecordFailedAttempt"/> is called from whichever
/// automatic-restart path (startup, <c>CaptureFailed</c>, watchdog) detects a failure, concurrently
/// with <see cref="RecordChunkReceived"/> being called from the capture thread.
///
/// <para>
/// Deliberately does not itself derive the full four-value <c>captureState</c> string — that also
/// needs two inputs this class has no access to: whether a device is configured and decoding is
/// enabled (config), and whether a capture session is currently running
/// (<c>CaptureManager.IsCapturing</c>). <see cref="DeriveCaptureState"/> takes both as parameters
/// rather than this class holding a reference to either.
/// </para>
/// </summary>
public sealed class CaptureRecoveryState
{
    private const int MaxErrorLength = 500;

    private readonly TimeProvider _timeProvider;
    private readonly object       _streakLock = new();

    private int      _captureRestartCount;
    private int      _consecutiveCaptureFailures;
    private volatile string? _lastCaptureError;
    private volatile bool    _lastResolutionWasDeviceUnavailable;
    private DateTimeOffset?  _failureStreakStartedAt;

    /// <param name="timeProvider">
    /// Clock used only to time a failure streak for the recovery log line's "seconds without
    /// audio" (design D6). Defaults to <see cref="TimeProvider.System"/>; unit tests pass a fake
    /// provider so downtime can be asserted deterministically without a real sleep.
    /// </param>
    public CaptureRecoveryState(TimeProvider? timeProvider = null)
        => _timeProvider = timeProvider ?? TimeProvider.System;

    /// <summary>Automatic restart attempts since process start (FR-072).</summary>
    public int CaptureRestartCount => Volatile.Read(ref _captureRestartCount);

    /// <summary>The current consecutive-failure count — also the input to <c>CaptureBackoffSchedule.DelayFor</c>.</summary>
    public int ConsecutiveCaptureFailures => Volatile.Read(ref _consecutiveCaptureFailures);

    /// <summary>
    /// The most recent capture failure or failed-resolution message, truncated to 500 characters,
    /// or <see langword="null"/> if neither has occurred since process start. Deliberately never
    /// cleared on recovery (design D5) — read this alongside <see cref="ConsecutiveCaptureFailures"/>
    /// (0 once healthy) to tell "recovered, but here's the last failure" from "currently failing".
    /// </summary>
    public string? LastCaptureError => _lastCaptureError;

    /// <summary>
    /// Records one failed automatic attempt (design D4): increments both
    /// <see cref="CaptureRestartCount"/> and <see cref="ConsecutiveCaptureFailures"/>, and sets
    /// <see cref="LastCaptureError"/>. Called for every kind of failure this change tracks: a real
    /// capture exception, a watchdog-detected stall, or a <c>NotFound</c>/<c>Ambiguous</c>
    /// resolution outcome (design D4: the last of these counts as a failed attempt even though no
    /// capture session was ever opened).
    /// </summary>
    /// <param name="errorMessage">
    /// The triggering exception's message, or — for a resolution failure, where there is no
    /// exception — a synthesised message naming the configured friendly name and the match count.
    /// </param>
    /// <param name="deviceUnavailable">
    /// <see langword="true"/> only for a <c>NotFound</c>/<c>Ambiguous</c> resolution outcome — this
    /// is what <see cref="DeriveCaptureState"/> uses to tell <c>DeviceUnavailable</c> apart from
    /// <c>Recovering</c> at the same failure count.
    /// </param>
    public void RecordFailedAttempt(string errorMessage, bool deviceUnavailable)
    {
        Interlocked.Increment(ref _captureRestartCount);
        var newCount = Interlocked.Increment(ref _consecutiveCaptureFailures);
        _lastCaptureError = errorMessage.Length > MaxErrorLength
            ? errorMessage[..MaxErrorLength]
            : errorMessage;
        _lastResolutionWasDeviceUnavailable = deviceUnavailable;

        lock (_streakLock)
        {
            if (newCount == 1)
                _failureStreakStartedAt = _timeProvider.GetUtcNow();
        }
    }

    /// <summary>
    /// Called on every chunk received from the capture pipeline. Resets
    /// <see cref="ConsecutiveCaptureFailures"/> to 0.
    /// </summary>
    /// <remarks>
    /// Design D4 phrases the reset condition as "a restarted session delivers its <em>first</em>
    /// chunk". Calling this on <em>every</em> chunk (not just detectably-the-first-one) is
    /// equivalent and simpler: once healthy, the count is already 0, so repeated calls are
    /// idempotent no-ops; the next genuine failure starts counting again from 1 regardless of how
    /// many healthy chunks preceded it. No "was this the first chunk since the last restart"
    /// bookkeeping is needed.
    /// </remarks>
    /// <returns>
    /// A <see cref="CaptureRecoveryInfo"/> describing the just-ended failure streak (for the
    /// design D6 recovery Warning), or <see langword="null"/> when there was no active streak to
    /// end (the overwhelmingly common case — chunks arriving while already healthy).
    /// </returns>
    public CaptureRecoveryInfo? RecordChunkReceived()
    {
        _lastResolutionWasDeviceUnavailable = false;

        DateTimeOffset? streakStart;
        lock (_streakLock)
        {
            streakStart = _failureStreakStartedAt;
            _failureStreakStartedAt = null;
        }

        var previousCount = Interlocked.Exchange(ref _consecutiveCaptureFailures, 0);
        if (previousCount == 0 || streakStart is null)
            return null;

        return new CaptureRecoveryInfo(previousCount, _timeProvider.GetUtcNow() - streakStart.Value);
    }

    /// <summary>
    /// Derives the four-value <c>captureState</c> string (design D5's table; FR-072) from this
    /// instance's counters plus the two external inputs the table also depends on.
    /// </summary>
    /// <param name="deviceConfiguredAndDecodingEnabled">
    /// <see langword="false"/> when no device is configured, or decoding is disabled — either
    /// unconditionally means <c>"Idle"</c>, regardless of any counter here.
    /// </param>
    /// <param name="isCapturing"><c>CaptureManager.IsCapturing</c> at read time.</param>
    public string DeriveCaptureState(bool deviceConfiguredAndDecodingEnabled, bool isCapturing)
    {
        if (!deviceConfiguredAndDecodingEnabled)
            return "Idle";

        if (isCapturing && ConsecutiveCaptureFailures == 0)
            return "Capturing";

        return _lastResolutionWasDeviceUnavailable ? "DeviceUnavailable" : "Recovering";
    }
}
