using System.Collections.Generic;
using System.Text.Json.Serialization;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Source-generated JSON serialisation context for <c>prop-modes.json</c> file I/O (qso-log-dialog).
/// Uses camelCase to match the wire format of the REST API.
/// </summary>
[JsonSourceGenerationOptions(
    PropertyNamingPolicy   = JsonKnownNamingPolicy.CamelCase,
    WriteIndented          = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.Never)]
[JsonSerializable(typeof(List<PropModeEntry>))]
[JsonSerializable(typeof(PropModeEntry))]
internal sealed partial class PropModeJsonContext : JsonSerializerContext { }
