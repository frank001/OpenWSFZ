namespace OpenWSFZ.Abstractions;

/// <summary>
/// Process-lifetime counters of audio lost on the capture path (capture-loss-instrument).
/// Surfaced on <c>GET /api/v1/status</c> and the WebSocket <c>status</c> event.  A zero in every
/// field does NOT prove no audio was lost on its own (a loss point that is not instrumented stays
/// invisible); the framer's per-window <c>wanted</c> log line is the loss-agnostic cross-check.
/// </summary>
/// <param name="OverrunCount">
/// <c>arecord</c> "overrun" reports on stderr (Linux only; 0 on other platforms).
/// </param>
/// <param name="ChannelDroppedChunks">
/// Chunks the capture manager's bounded DropOldest channel discarded because the consumer
/// fell behind (2 048 samples, about 170.7 ms each).
/// </param>
public readonly record struct CaptureLossSnapshot(
    long OverrunCount,
    long ChannelDroppedChunks);
