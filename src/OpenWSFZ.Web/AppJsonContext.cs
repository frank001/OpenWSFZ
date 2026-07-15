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
[JsonSerializable(typeof(RegionInfo))]
[JsonSerializable(typeof(WorkedBeforeInfo))]
[JsonSerializable(typeof(WorkedBeforeState))]
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
[JsonSerializable(typeof(DecodeNoiseSuppressionConfig))]
[JsonSerializable(typeof(WsAuthFrame))]
[JsonSerializable(typeof(SelectResponderRequest))]
[JsonSerializable(typeof(EngageDecodeRequest))]
[JsonSerializable(typeof(CallerPartnerSelectRequest))]
[JsonSerializable(typeof(PropModeEntry))]
[JsonSerializable(typeof(List<PropModeEntry>))]
[JsonSerializable(typeof(LogQsoRequest))]
[JsonSerializable(typeof(LogQsoResponse))]
[JsonSerializable(typeof(WsQsoReviewMessage))]
[JsonSerializable(typeof(LogTailResponse))]
[JsonSerializable(typeof(RegionRefreshResponse))]
[JsonSerializable(typeof(RegionDataStatusResponse))]
[JsonSerializable(typeof(RegionLookupResponse))]
[JsonSerializable(typeof(DecodeFilterState))]
[JsonSerializable(typeof(WsDecodeFilterMessage))]
[JsonSerializable(typeof(ExternalReportingConfig))]
[JsonSerializable(typeof(ExternalReportingTarget))]
[JsonSerializable(typeof(List<ExternalReportingTarget>))]
[JsonSerializable(typeof(PttTestResponse))]
[JsonSerializable(typeof(SystemRestartResponse))]
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
/// "partner":"Q1TST","autoAnswerEnabled":true,"keying":true,"abortReason":null}</c>
/// </para>
/// <para>
/// Wire format (caller): <c>{"type":"txState","role":"caller","state":"TxCq",
/// "partner":null,"autoAnswerEnabled":true,"keying":false}</c>
/// </para>
/// <para>
/// <c>abortReason</c> is non-null only when transitioning to Idle due to an abnormal
/// termination (watchdog, operator abort, retry exhaustion, partner misbehaviour).
/// It is null on normal QSO completion and on routine Idle state pushes.
/// </para>
/// <para>
/// <c>keying</c> (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A)
/// mirrors <c>IQsoController.Keying</c> — true only while the publishing controller is
/// inside <c>TransmitAsync</c>'s <c>KeyDownAsync</c> call. This supersedes Decision 2 in
/// <c>tx-state-indicators/spec.md</c> ("derived entirely from existing txState payload
/// fields... with no additional server-side signal"): <c>keying</c> IS that additional
/// signal, added deliberately on the Captain's instruction because the <c>state</c>-prefix
/// derivation under-reported real transmission windows whenever a TX call site retransmitted
/// without re-broadcasting a <c>Tx*</c> sub-state first.
/// </para>
/// </summary>
internal sealed record WsTxStateMessage(
    string  Type,
    string  Role,
    string  State,
    string? Partner,
    bool    AutoAnswerEnabled,
    bool    Keying,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? AbortReason = null);

/// <summary>
/// Response body for <c>GET /api/v1/tx/status</c>, <c>POST /api/v1/tx/enable</c>,
/// <c>POST /api/v1/tx/disable</c>, <c>POST /api/v1/tx/select-responder</c>,
/// and <c>POST /api/v1/tx/caller-partner-select</c> (FR-047, FR-PILEUP-001).
/// Wire format: <c>{"state":"Idle","partner":null,"autoAnswerEnabled":false,"role":"answerer","callerPartnerSelect":"First","keying":false}</c>
/// <c>keying</c> mirrors <c>IQsoController.Keying</c> so a freshly-loaded or reconnected tab
/// gets the correct current value immediately rather than only on the next <c>txState</c>
/// WS transition (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A).
/// </summary>
public sealed record TxStatusResponse(
    string  State,
    string? Partner,
    bool    AutoAnswerEnabled,
    string  Role                = "answerer",
    string  CallerPartnerSelect = "First",
    bool    Keying              = false);

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
/// Request body for <c>POST /api/v1/tx/engage-decode</c> (D-CALLER-012).
/// Wire format: <c>{"message":"PD2FZ W1ABC -07","frequencyHz":1234.0,"cycleStartUtc":"2026-06-27T10:00:15Z"}</c>
/// </summary>
internal sealed record EngageDecodeRequest(
    string Message,
    double FrequencyHz,
    string CycleStartUtc);

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
/// <summary>
/// Response body for <c>GET /api/v1/logs/tail</c> (log-viewer).
/// Wire format: <c>{"lines":["2026-07-05 12:00:00 [INF] ...", "..."]}</c>
/// </summary>
internal sealed record LogTailResponse(string[] Lines);

/// <summary>
/// Response body for <c>POST /api/v1/region-data/refresh</c> (region-lookup-data-refresh).
/// Wire format: <c>{"success":true,"entryCount":29006,"releaseVersion":"20260629"}</c>.
/// <c>releaseVersion</c> is <c>null</c> when the release's <c>VERyyyymmdd</c> marker entry
/// (see <c>cty-dat-format</c>'s version-tracking convention) was not present or recognised —
/// this is informational only and never fails the refresh.
/// </summary>
public sealed record RegionRefreshResponse(bool Success, int EntryCount, string? ReleaseVersion);

/// <summary>
/// Response body for <c>GET /api/v1/region-data/status</c> (region-lookup-data-refresh, GUI
/// operator status view). <c>EntryCount</c> always reflects <c>regionStore.Entries.Count</c>,
/// regardless of whether a refresh has ever run this session — seed data or a previously-saved
/// <c>callsign-regions.json</c> both count. The remaining fields describe <em>this daemon
/// session's</em> refresh history only (no new persistence; they reset on restart, consistent
/// with "refresh is never automatic").
/// Wire format: <c>{"entryCount":38,"hasRefreshedThisSession":false,"lastRefreshUtc":null,
/// "lastRefreshSucceeded":null,"lastReleaseVersion":null,"lastErrorMessage":null,
/// "effectiveSuppressUnknownRegion":true}</c>.
/// </summary>
/// <param name="EffectiveSuppressUnknownRegion">
/// The live-resolved effective value of
/// <c>DecodeNoiseSuppressionConfig.SuppressUnknownRegion</c> (<c>decode-noise-suppression</c>
/// capability, design.md Decision 3/task 3.4) — the persisted value when the operator has made an
/// explicit choice, otherwise computed from <c>EntryCount &gt; 0</c>. The settings page displays
/// this rather than the raw persisted field so the operator always sees what's actually being
/// applied, including the auto-computed default.
/// </param>
public sealed record RegionDataStatusResponse(
    int             EntryCount,
    bool            HasRefreshedThisSession,
    DateTimeOffset? LastRefreshUtc,
    bool?           LastRefreshSucceeded,
    string?         LastReleaseVersion,
    string?         LastErrorMessage,
    bool            EffectiveSuppressUnknownRegion);

/// <summary>
/// Response body for <c>GET /api/v1/region-data/lookup?callsign={token}</c>
/// (region-lookup-data-refresh, GUI operator diagnostic lookup). Mirrors the decode pipeline's
/// own longest-prefix-match logic (<see cref="ICallsignRegionStore.TryGetRegion"/>) so an
/// operator can confirm how a specific callsign currently resolves without decoding a live
/// signal. A lookup miss reports <c>Matched: false</c> with every other field
/// <c>null</c>/<c>false</c> — the diagnostic equivalent of the decode pipeline's "Unknown".
/// Wire format: <c>{"matched":true,"entity":"Monaco","continent":"EU","cqZone":14,"ituZone":27,
/// "synthetic":false}</c>.
/// </summary>
public sealed record RegionLookupResponse(
    bool    Matched,
    string? Entity,
    string? Continent,
    int?    CqZone,
    int?    ItuZone,
    bool    Synthetic);

/// <summary>
/// Envelope for <c>decodeFilterChanged</c> WebSocket text frames
/// (<c>decode-panel-filtering</c> capability). Pushed on every
/// <c>POST /api/v1/decode-filter</c> so all connected clients' popups and rendered tables
/// update immediately, including the client that issued the POST.
/// Wire format: <c>{"type":"decodeFilterChanged","payload":{"allowedEntities":null,...}}</c>
/// </summary>
internal sealed record WsDecodeFilterMessage(string Type, DecodeFilterState Payload);

/// <summary>
/// Response body for <c>POST /api/v1/ptt/test</c> (cat-tx-ptt, task 17.3, FR-057).
/// <c>Result</c> is <c>"pass"</c> when the assert/release commands were accepted without
/// throwing (a real CAT ACK or a real RTS/DTR line toggle happened) — this confirms only
/// that the <em>command</em> was accepted, never that the rig physically keyed, since
/// <see cref="OpenWSFZ.Abstractions.IRadioConnection.SetPttAsync"/> defines no read-back.
/// <c>Result</c> is <c>"error"</c> with a non-null <c>Message</c> when the pulse itself threw
/// (e.g. a CAT write failure, a serial port error) — always returned with HTTP 200, since this
/// is an expected, handleable outcome, not a server error. The 409-Conflict cases (a real QSO
/// is currently keying; the running method is <c>AudioVox</c>) are surfaced as HTTP 409
/// ProblemDetails responses instead, not through this record.
/// Wire format: <c>{"result":"pass","message":null}</c> or
/// <c>{"result":"error","message":"port in use"}</c>.
/// </summary>
public sealed record PttTestResponse(string Result, string? Message = null);

/// <summary>
/// Response body for <c>POST /api/v1/system/restart</c> (remote-daemon-restart). Returned with
/// HTTP 202 immediately, before the actual spawn-and-stop sequence runs on a short delay
/// (design.md Decision 3) — the operator-facing "reconnecting…" UX is driven by the frontend
/// polling <c>GET /api/v1/status</c>, not by this body's contents.
/// Wire format: <c>{"status":"restarting"}</c>.
/// </summary>
public sealed record SystemRestartResponse(string Status);

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
