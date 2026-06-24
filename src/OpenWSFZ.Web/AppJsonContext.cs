using System.Collections.Generic;
using System.Text.Json.Serialization;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Source-generated JSON serialisation context — required for AOT compatibility.
/// Uses camelCase property names so the wire format matches the REST/WebSocket API contract.
/// </summary>
[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
[JsonSerializable(typeof(DaemonStatus))]
[JsonSerializable(typeof(WsMessage))]
[JsonSerializable(typeof(WsHeartbeatMessage))]
[JsonSerializable(typeof(HeartbeatPayload))]
[JsonSerializable(typeof(WsDecodeMessage))]
[JsonSerializable(typeof(AudioDeviceInfo))]
[JsonSerializable(typeof(List<AudioDeviceInfo>))]
[JsonSerializable(typeof(AppConfig))]
[JsonSerializable(typeof(DecodeResult))]
[JsonSerializable(typeof(List<DecodeResult>))]
[JsonSerializable(typeof(WsSpectrumMessage))]
[JsonSerializable(typeof(int[]))]
[JsonSerializable(typeof(string[]))]
[JsonSerializable(typeof(LoggingConfig))]
[JsonSerializable(typeof(DecodeLogConfig))]
[JsonSerializable(typeof(CatConfig))]
[JsonSerializable(typeof(CatConnectionStatus))]
[JsonSerializable(typeof(WsCatStatusMessage))]
[JsonSerializable(typeof(CatStatusPayload))]
[JsonSerializable(typeof(FrequencyEntry))]
[JsonSerializable(typeof(List<FrequencyEntry>))]
[JsonSerializable(typeof(TuneRequest))]
[JsonSerializable(typeof(TuneResponse))]
[JsonSerializable(typeof(WsTxStateMessage))]
[JsonSerializable(typeof(TxStatusResponse))]
[JsonSerializable(typeof(QsoState))]
[JsonSerializable(typeof(AudioOffsetPayload))]
[JsonSerializable(typeof(WsAudioOffsetMessage))]
[JsonSerializable(typeof(AudioOffsetRequest))]
[JsonSerializable(typeof(AnswerCqRequest))]
[JsonSerializable(typeof(RemoteAccessConfig))]
[JsonSerializable(typeof(DecoderConfig))]
internal sealed partial class AppJsonContext : JsonSerializerContext { }

/// <summary>Envelope for <c>status</c> WebSocket text frames.</summary>
internal sealed record WsMessage(string Type, DaemonStatus? Payload = null);

/// <summary>
/// Envelope for <c>heartbeat</c> WebSocket text frames (FR-020).
/// Wire format: <c>{"type":"heartbeat","payload":{"audioActive":true}}</c>
/// </summary>
internal sealed record WsHeartbeatMessage(string Type, HeartbeatPayload Payload);

/// <summary>Payload for <c>heartbeat</c> WebSocket text frames (FR-020).</summary>
internal sealed record HeartbeatPayload(bool AudioActive, bool CaptureActive);

/// <summary>Envelope for <c>decode</c> WebSocket text frames.</summary>
internal sealed record WsDecodeMessage(string Type, List<DecodeResult> Payload);

/// <summary>Envelope for <c>spectrum</c> WebSocket text frames.</summary>
internal sealed record WsSpectrumMessage(string Type, int[] Payload);

/// <summary>
/// Envelope for <c>cat_status</c> WebSocket text frames (FR-033).
/// Wire format: <c>{"type":"cat_status","payload":{"status":"Connected","dialFrequencyMHz":14.074}}</c>
/// </summary>
internal sealed record WsCatStatusMessage(string Type, CatStatusPayload Payload);

/// <summary>Payload for <c>cat_status</c> WebSocket text frames (FR-033).</summary>
internal sealed record CatStatusPayload(string Status, double? DialFrequencyMHz);

/// <summary>Request body for <c>POST /api/v1/tune</c> (FR-045).</summary>
internal sealed record TuneRequest(double? FrequencyMHz);

/// <summary>Response body for <c>POST /api/v1/tune</c> (FR-045).</summary>
internal sealed record TuneResponse(double EffectiveFrequencyMHz);

/// <summary>
/// Envelope for <c>txState</c> WebSocket text frames (FR-047).
/// Wire format: <c>{"type":"txState","state":"TxAnswer","partner":"Q1TST","autoAnswerEnabled":true}</c>
/// </summary>
internal sealed record WsTxStateMessage(string Type, string State, string? Partner, bool AutoAnswerEnabled);

/// <summary>
/// Response body for <c>GET /api/v1/tx/status</c>, <c>POST /api/v1/tx/enable</c>,
/// and <c>POST /api/v1/tx/disable</c> (FR-047).
/// Wire format: <c>{"state":"Idle","partner":null,"autoAnswerEnabled":false}</c>
/// </summary>
public sealed record TxStatusResponse(string State, string? Partner, bool AutoAnswerEnabled);

/// <summary>
/// Payload for <c>audioOffset</c> WebSocket push events.
/// Wire format: <c>{"rxHz":900,"txHz":1500,"holdTxFreq":false}</c>
/// </summary>
internal sealed record AudioOffsetPayload(int RxHz, int TxHz, bool HoldTxFreq);

/// <summary>
/// Envelope for <c>audioOffset</c> WebSocket text frames.
/// Pushed when audio offset state changes via <c>POST /api/v1/audio-offset</c> or
/// when the QSO answerer auto-updates the TX cursor (Hold TX = OFF, CQ answered).
/// </summary>
internal sealed record WsAudioOffsetMessage(string Type, AudioOffsetPayload Payload);

/// <summary>
/// Request body for <c>POST /api/v1/audio-offset</c>.
/// Wire format: <c>{"rxHz":900,"txHz":1500,"holdTxFreq":false}</c>
/// </summary>
internal sealed record AudioOffsetRequest(int RxHz, int TxHz, bool HoldTxFreq);

/// <summary>
/// Request body for <c>POST /api/v1/tx/answer-cq</c> (TX-D01).
/// Wire format: <c>{"callsign":"Q1TST","frequencyHz":897.0,"cqCycleStartUtc":"2026-06-22T17:29:15Z"}</c>
/// </summary>
internal sealed record AnswerCqRequest(
    string Callsign,
    double FrequencyHz,
    string CqCycleStartUtc);    // ISO 8601 UTC, e.g. "2026-06-22T17:29:15Z"
