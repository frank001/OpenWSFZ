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
/// <c>{ "entries": [...], "isSeedData": bool }</c> — mirrors <c>FrequenciesFile</c>.
/// </summary>
internal sealed class CallsignRegionsFile
{
    public List<CallsignRegionEntry> Entries { get; set; } = [];

    /// <summary>
    /// Persisted provenance marker (engagement-target-validation, dev-task
    /// 2026-07-17-engagement-target-validation-qa-review-findings, Finding E):
    /// <c>true</c> when this file was written by <see cref="CallsignRegionStore.LoadAsync"/>'s
    /// file-absent seed-write branch; <c>false</c> when written by
    /// <see cref="CallsignRegionStore.SaveAsync"/> (an operator-triggered refresh). Without this
    /// marker, the mere <em>existence</em> of the file on a second daemon launch was
    /// indistinguishable from a genuine refresh — every restart after the very first run silently
    /// flipped <see cref="ICallsignRegionStore.IsSeedData"/> to <c>false</c> regardless of whether
    /// an operator had ever refreshed. A pre-existing file from before this marker existed
    /// deserialises this as <c>false</c> (the JSON default for a missing property) — deliberately:
    /// see <see cref="CallsignRegionStore.LoadAsync"/>'s remarks for the migration reasoning.
    /// </summary>
    public bool IsSeedData { get; set; }
}
