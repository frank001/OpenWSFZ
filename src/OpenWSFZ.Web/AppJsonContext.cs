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
[JsonSerializable(typeof(TxRole))]
[JsonSerializable(typeof(CallerPartnerSelectMode))]
[JsonSerializable(typeof(AudioOffsetPayload))]
[JsonSerializable(typeof(WsAudioOffsetMessage))]
[JsonSerializable(typeof(AudioOffsetRequest))]
[JsonSerializable(typeof(AnswerCqRequest))]
[JsonSerializable(typeof(RemoteAccessConfig))]
[JsonSerializable(typeof(DecoderConfig))]
[JsonSerializable(typeof(WsAuthFrame))]
[JsonSerializable(typeof(SelectResponderRequest))]
[JsonSerializable(typeof(CallerPartnerSelectRequest))]
[JsonSerializable(typeof(PropModeEntry))]
[JsonSerializable(typeof(List<PropModeEntry>))]
[JsonSerializable(typeof(LogQsoRequest))]
[JsonSerializable(typeof(LogQsoResponse))]
[JsonSerializable(typeof(WsQsoReviewMessage))]
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
/// <para>
/// Wire format (answerer): <c>{"type":"txState","role":"answerer","state":"TxAnswer",
/// "partner":"Q1TST","autoAnswerEnabled":true,"abortReason":null}</c>
/// </para>
/// <para>
/// Wire format (caller): <c>{"type":"txState","role":"caller","state":"TxCq",
/// "partner":null,"autoAnswerEnabled":true}</c>
/// </para>
/// <para>
/// <c>abortReason</c> is non-null only when transitioning to Idle due to an abnormal
/// termination (watchdog, operator abort, retry exhaustion, partner misbehaviour).
/// It is null on normal QSO completion and on routine Idle state pushes.
/// </para>
/// </summary>
internal sealed record WsTxStateMessage(
    string  Type,
    string  Role,
    string  State,
    string? Partner,
    bool    AutoAnswerEnabled,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? AbortReason = null);

/// <summary>
/// Response body for <c>GET /api/v1/tx/status</c>, <c>POST /api/v1/tx/enable</c>,
/// <c>POST /api/v1/tx/disable</c>, <c>POST /api/v1/tx/select-responder</c>,
/// and <c>POST /api/v1/tx/caller-partner-select</c> (FR-047, FR-PILEUP-001).
/// Wire format: <c>{"state":"Idle","partner":null,"autoAnswerEnabled":false,"role":"answerer","callerPartnerSelect":"First"}</c>
/// </summary>
public sealed record TxStatusResponse(
    string  State,
    string? Partner,
    bool    AutoAnswerEnabled,
    string  Role                = "answerer",
    string  CallerPartnerSelect = "First");

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

/// <summary>
/// First-frame WebSocket authentication message sent by the browser client for
/// non-loopback connections (SEC-002B).
/// Wire format: <c>{"type":"auth","key":"passphrase"}</c>
/// </summary>
internal sealed record WsAuthFrame(
    string? Type,
    string? Key);

/// <summary>
/// Request body for <c>POST /api/v1/tx/select-responder</c> (qso-caller).
/// Wire format: <c>{"callsign":"Q1ABC","frequencyHz":1500.0,"responseCycleStartUtc":"2026-06-25T14:29:15Z"}</c>
/// </summary>
internal sealed record SelectResponderRequest(
    string Callsign,
    double FrequencyHz,
    string ResponseCycleStartUtc);   // ISO 8601 UTC

/// <summary>
/// Request body for <c>POST /api/v1/tx/caller-partner-select</c> (FR-PILEUP-001).
/// Wire format: <c>{"mode":"First"}</c> or <c>{"mode":"None"}</c>
/// </summary>
internal sealed record CallerPartnerSelectRequest(string Mode);

/// <summary>
/// Request body for <c>POST /api/v1/tx/log-qso</c> (qso-log-dialog).
/// Carries the complete QSO record (from the <c>qsoReview</c> WS event) plus
/// optional enrichment fields and retain flags.
/// </summary>
public sealed record LogQsoRequest(
    string  Callsign,
    string? Grid,
    string  RstSent,
    string  RstRcvd,
    string  StartUtc,
    string  EndUtc,
    // Explicit JsonPropertyName to avoid ambiguity: STJ camelCase of "FreqMHz" produces
    // "freqMHz" but some source-gen versions may differ on mixed-acronym identifiers.
    [property: System.Text.Json.Serialization.JsonPropertyName("freqMHz")]
    double  FreqMHz,
    string  OperatorCallsign,
    string? Name,
    string? TxPower,
    string? Comment,
    string? PropMode,
    string? ExchSent,
    string? ExchRcvd,
    bool    RetainTxPower,
    bool    RetainComment,
    bool    RetainPropMode);

/// <summary>Response body for <c>POST /api/v1/tx/log-qso</c> (qso-log-dialog).</summary>
internal sealed record LogQsoResponse(bool Logged);

/// <summary>
/// WebSocket <c>qsoReview</c> event (qso-log-dialog).
/// Pushed when the state machine enters <c>Tx73</c> (answerer) or <c>TxRr73</c> (caller)
/// and <c>tx.qsoConfirmation = true</c>.  The browser opens the confirmation dialog on receipt.
/// Wire format:
/// <code>
/// {
///   "type": "qsoReview",
///   "callsign": "Q1TST", "grid": "JO22", "rstSent": "+00", "rstRcvd": "+05",
///   "startUtc": "2026-06-27T14:29:15Z", "endUtc": "2026-06-27T14:30:00Z",
///   "freqMHz": 14.074, "operatorCallsign": "Q2OPR",
///   "retainedTxPower": "100", "retainedComment": "", "retainedPropMode": "TR"
/// }
/// </code>
/// </summary>
internal sealed record WsQsoReviewMessage(
    string  Type,
    string  Callsign,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? Grid,
    string  RstSent,
    string  RstRcvd,
    string  StartUtc,
    string  EndUtc,
    [property: JsonPropertyName("freqMHz")]
    double  FreqMHz,
    string  OperatorCallsign,
    string  RetainedTxPower,
    string  RetainedComment,
    string  RetainedPropMode);
