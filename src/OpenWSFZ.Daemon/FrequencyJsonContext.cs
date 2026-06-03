using System.Collections.Generic;
using System.Text.Json.Serialization;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Source-generated JSON serialisation context for <c>frequencies.json</c> file I/O.
/// Uses camelCase to match the wire format of the REST API.
/// </summary>
[JsonSourceGenerationOptions(
    PropertyNamingPolicy   = JsonKnownNamingPolicy.CamelCase,
    WriteIndented          = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.Never)]
[JsonSerializable(typeof(FrequenciesFile))]
[JsonSerializable(typeof(List<FrequencyEntry>))]
[JsonSerializable(typeof(FrequencyEntry))]
internal sealed partial class FrequencyJsonContext : JsonSerializerContext { }

/// <summary>
/// DTO representing the on-disk <c>frequencies.json</c> format:
/// <c>{ "entries": [...] }</c>.
/// </summary>
internal sealed class FrequenciesFile
{
    public List<FrequencyEntry> Entries { get; set; } = [];
}
