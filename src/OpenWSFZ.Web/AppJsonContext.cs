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
internal sealed partial class AppJsonContext : JsonSerializerContext { }

/// <summary>Envelope for <c>status</c> WebSocket text frames.</summary>
internal sealed record WsMessage(string Type, DaemonStatus? Payload = null);

/// <summary>
/// Envelope for <c>heartbeat</c> WebSocket text frames (FR-020).
/// Wire format: <c>{"type":"heartbeat","payload":{"audioActive":true}}</c>
/// </summary>
internal sealed record WsHeartbeatMessage(string Type, HeartbeatPayload Payload);

/// <summary>Payload for <c>heartbeat</c> WebSocket text frames (FR-020).</summary>
internal sealed record HeartbeatPayload(bool AudioActive);

/// <summary>Envelope for <c>decode</c> WebSocket text frames.</summary>
internal sealed record WsDecodeMessage(string Type, List<DecodeResult> Payload);
