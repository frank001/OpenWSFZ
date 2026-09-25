namespace OpenWSFZ.Web;

/// <summary>
/// Returned by <c>GET /api/v1/status</c> and pushed as the first WebSocket event payload.
/// </summary>
public sealed record DaemonStatus(
    string  State,
    string  Version,
    string? AudioDevice    = null,
    bool    CaptureActive  = false,
    /// <summary>
    /// The <c>dataFlowing</c> value of the most recently completed 5-second capture-health
    /// window — <c>true</c> if at least one audio chunk (of any amplitude) was received during
    /// that window (FR-020, amended by capture-stall-detection-unattended #188; FR-069). Does
    /// not latch: always reflects the last completed window, and carries the same value as
    /// <see cref="DataFlowing"/> and as the initial WebSocket <c>status</c> event and every
    /// WebSocket <c>heartbeat</c> frame.
    /// </summary>
    bool    AudioActive    = false,
    /// <summary>
    /// Whether the FT8 decode pipeline is currently enabled (FR-017).
    /// Reflects <c>AppConfig.DecodingEnabled</c> — the authoritative persisted state.
    /// </summary>
    bool    DecodingEnabled = false,
    /// <summary>
    /// Effective dial frequency in MHz using the CAT precedence rule (FR-032):
    /// <c>ICatState.DialFrequencyMHz ?? AppConfig.DecodeLog.DialFrequencyMHz</c>.
    /// </summary>
    double  DialFrequencyMHz = 0.0,
    /// <summary>
    /// Current CAT connection state as a string (FR-033): <c>"Disabled"</c>, <c>"Connecting"</c>,
    /// <c>"Connected"</c>, or <c>"Error"</c>.  Defaults to <c>"Disabled"</c> when CAT is not wired up.
    /// </summary>
    string  CatConnectionStatus = "Disabled",
    /// <summary>
    /// Current RX audio frequency cursor position in Hz (0–3000).
    /// Included in the initial <c>status</c> WebSocket event so newly-connected clients
    /// can initialise their waterfall cursor without waiting for an <c>audioOffset</c> event.
    /// </summary>
    int     RxAudioOffsetHz = 1500,
    /// <summary>
    /// Current TX audio frequency cursor position in Hz (0–3000).
    /// </summary>
    int     TxAudioOffsetHz = 1500,
    /// <summary>
    /// Whether the QSO answerer is locked to the operator-set TX frequency.
    /// </summary>
    bool    HoldTxFreq = false,
    /// <summary>
    /// The native FT8 decoder shim's actual loaded ABI version
    /// (f-004-operator-visibility-improvements, daemon-status-visibility). Stable for the
    /// process lifetime once the native library has been initialised. Defaults to 0 for
    /// callers that do not wire up the native shim (e.g. minimal test fixtures).
    /// </summary>
    int     ShimVersion = 0,
    /// <summary>
    /// Process-lifetime count of Type 4 callsign announcements the native decoder discarded
    /// because its session-scoped callsign hash table was already at its 4096-slot capacity
    /// (f-005-hash-table-saturation-diagnostic, D2). A non-zero value indicates the table
    /// saturated during this session. Read live per request; resets to 0 only on daemon
    /// restart. Defaults to 0 for callers that do not wire up the native shim.
    /// </summary>
    int     HashTableRejectCount = 0,
    /// <summary>
    /// Process-lifetime count of decode-cycle windows dropped by the cycle audio archive because
    /// its internal queue was at capacity (<c>cycle-audio-archive</c> capability). Always 0 when
    /// the archive is disabled (<c>Off</c>, the default) or under normal operation — a nonzero
    /// value indicates the archive's dedicated writer task cannot keep up with the configured
    /// mode. Read live per request; resets to 0 only on daemon restart. Defaults to 0 for callers
    /// that do not wire up the archive.
    /// </summary>
    long    CycleArchiveDroppedCycles = 0,
    /// <summary>
    /// Whether at least one audio chunk (of any amplitude) was received during the most
    /// recently completed 5-second capture-health window (FR-068, capture-stall-detection-
    /// unattended #188). <c>false</c> before the first window completes or while no capture
    /// session is running. Does not latch — always reflects the last completed window.
    /// </summary>
    bool    DataFlowing = false,
    /// <summary>
    /// Milliseconds elapsed since the most recent audio chunk was received, computed at the
    /// moment this response is built from a monotonic clock (FR-068). <c>null</c> only before
    /// the first chunk of the process. A pipeline restart does NOT reset it — a restart that
    /// delivers nothing keeps ageing rather than reading back as newly healthy.
    /// </summary>
    int?    LastChunkAgeMs = null,
    /// <summary>
    /// Process-lifetime count of times the capture watchdog has triggered a pipeline restart
    /// (FR-068). Counts fired triggers, not successful reconnects.
    /// </summary>
    int     WatchdogRestartCount = 0,
    /// <summary>
    /// Capture recovery state (FR-072, capture-device-reresolution #187): <c>"Idle"</c> (no device
    /// configured, or decoding disabled), <c>"Capturing"</c> (a session is running with zero
    /// consecutive failures), <c>"Recovering"</c> (one or more consecutive failures, and the last
    /// resolution identified a usable device or could not resolve), or <c>"DeviceUnavailable"</c>
    /// (the last resolution found no uniquely matching available device).
    /// </summary>
    string  CaptureState = "Idle",
    /// <summary>
    /// Automatic capture-restart attempts since process start (FR-072). Includes attempts whose
    /// resolution found no uniquely matching device (no capture session was ever opened for
    /// those), not only attempts that opened a session and then failed.
    /// </summary>
    int     CaptureRestartCount = 0,
    /// <summary>
    /// The current consecutive-failure count (FR-072) — 0 while healthy. Drives the automatic
    /// restart backoff schedule (<c>CaptureBackoffSchedule.DelayFor</c>); resets to 0 the moment a
    /// restarted session delivers its first audio chunk.
    /// </summary>
    int     ConsecutiveCaptureFailures = 0,
    /// <summary>
    /// The message of the most recent capture failure or failed resolution, truncated to 500
    /// characters, or <c>null</c> if neither has occurred since process start (FR-072). A failed
    /// resolution's message names the configured friendly name and the match count (0 or ≥2).
    /// Deliberately NOT cleared on recovery — the last failure stays visible after the fact; read
    /// alongside <see cref="ConsecutiveCaptureFailures"/> (0 once healthy) to distinguish "recovered,
    /// but here's the last failure" from "currently failing".
    /// </summary>
    string? LastCaptureError = null);
