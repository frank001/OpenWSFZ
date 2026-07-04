using System.Collections.Generic;
using System.Text.Json.Serialization;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Source-generated JSON serialisation context for <c>callsign-grammar.json</c> and
/// <c>callsign-regions.json</c> file I/O. Uses camelCase to match the wire format
/// convention established by <see cref="FrequencyJsonContext"/>.
/// </summary>
[JsonSourceGenerationOptions(
    PropertyNamingPolicy   = JsonKnownNamingPolicy.CamelCase,
    WriteIndented          = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.Never)]
[JsonSerializable(typeof(CallsignGrammarConfig))]
[JsonSerializable(typeof(CallsignPrefixExclusion))]
[JsonSerializable(typeof(List<CallsignPrefixExclusion>))]
[JsonSerializable(typeof(CallsignRegionsFile))]
[JsonSerializable(typeof(CallsignRegionEntry))]
[JsonSerializable(typeof(List<CallsignRegionEntry>))]
internal sealed partial class CallsignJsonContext : JsonSerializerContext { }

/// <summary>
/// DTO representing the on-disk <c>callsign-regions.json</c> format:
/// <c>{ "entries": [...] }</c> — mirrors <c>FrequenciesFile</c>.
/// </summary>
internal sealed class CallsignRegionsFile
{
    public List<CallsignRegionEntry> Entries { get; set; } = [];
}
