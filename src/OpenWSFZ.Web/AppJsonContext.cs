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
/// Wire format: <c>{"type":"txState","state":"TxAnswer","partner":"Q1TST"}</c>
/// </summary>
internal sealed record WsTxStateMessage(string Type, string State, string? Partner);

/// <summary>
/// Response body for <c>GET /api/v1/tx/status</c> (FR-047).
/// Wire format: <c>{"state":"Idle","partner":null}</c>
/// </summary>
public sealed record TxStatusResponse(string State, string? Partner);
