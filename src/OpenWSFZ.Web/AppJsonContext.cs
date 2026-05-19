using System.Text.Json.Serialization;

namespace OpenWSFZ.Web;

/// <summary>
/// Source-generated JSON serialisation context — required for AOT compatibility.
/// Uses camelCase property names so the wire format matches the REST/WebSocket API contract.
/// </summary>
[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
[JsonSerializable(typeof(DaemonStatus))]
[JsonSerializable(typeof(WsMessage))]
internal sealed partial class AppJsonContext : JsonSerializerContext { }

/// <summary>Envelope for WebSocket text frames.</summary>
internal sealed record WsMessage(string Type, DaemonStatus? Payload = null);
