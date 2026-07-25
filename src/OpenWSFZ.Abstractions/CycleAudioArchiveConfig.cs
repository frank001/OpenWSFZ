using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Operator-controlled mode for the cycle audio archive (<c>cycle-audio-archive</c> capability,
/// design.md Decision 8). <c>Off</c> is the default and results in no directory being created and
/// no measurable work on the decode path beyond a single configuration test.
/// </summary>
/// <remarks>
/// Serialised via <see cref="JsonStringEnumConverter{TEnum}"/> (the generic form — the
/// non-generic one is not AOT-safe) with an explicit <see cref="JsonStringEnumMemberNameAttribute"/>
/// pinning each member's wire value to lowerCamelCase. <c>WorkedBeforeState.cs</c> documents the
/// exact failure mode of skipping this: without the explicit names, <c>JsonStringEnumConverter</c>
/// serialises the bare PascalCase member name instead, and this project's <c>AppJsonContext</c>/
/// <c>ConfigJsonContext</c> <c>CamelCase</c> naming policy does not help — that option renames JSON
/// *properties*, never enum *values*.
/// </remarks>
[JsonConverter(typeof(JsonStringEnumConverter<CycleAudioArchiveMode>))]
public enum CycleAudioArchiveMode
{
    /// <summary>No cycle is archived. The default.</summary>
    [JsonStringEnumMemberName("off")]
    Off,

    /// <summary>Every framed window is archived, regardless of decode outcome.</summary>
    [JsonStringEnumMemberName("all")]
    All,

    /// <summary>Only windows that produced at least one decode are archived.</summary>
    [JsonStringEnumMemberName("decoded")]
    Decoded,

    /// <summary>
    /// Only windows that produced no decodes are archived — the failure population that this
    /// project's own D-001 investigation needs (proposal.md "Why").
    /// </summary>
    [JsonStringEnumMemberName("noDecodes")]
    NoDecodes,
}

/// <summary>
/// Operator-controlled, persisted configuration for the cycle audio archive
/// (<c>cycle-audio-archive</c> capability). Modelled on <see cref="DecodeLogConfig"/> and
/// <see cref="DecodeNoiseSuppressionConfig"/>.
/// </summary>
public sealed record CycleAudioArchiveConfig
{
    // ── Deserialization note (Lesson 6 / D-WFC-001 pattern, mirrors DecodeNoiseSuppressionConfig)
    //
    // MaxSizeMb (2048), MaxAgeHours (168) and WriteManifest (true) all have non-CLR-zero defaults.
    // A JSON object that omits these keys would otherwise deserialise them to 0/0/false under STJ
    // source generation. The explicit [JsonConstructor] with matching parameter defaults is
    // required — see DecodeNoiseSuppressionConfig.cs for the same pattern and its rationale.
    // ─────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context. Parameter defaults
    /// ensure a field absent from an older/partial config object loads with the documented
    /// default rather than a CLR zero-value (Lesson 6 / D-WFC-001 pattern).
    /// </summary>
    [JsonConstructor]
    public CycleAudioArchiveConfig(
        CycleAudioArchiveMode mode          = CycleAudioArchiveMode.Off,
        string?               directory     = null,
        int                   maxSizeMb     = 2048,
        int                   maxAgeHours   = 168,
        bool                  writeManifest = true)
    {
        Mode          = mode;
        Directory     = directory;
        MaxSizeMb     = maxSizeMb;
        MaxAgeHours   = maxAgeHours;
        WriteManifest = writeManifest;
    }

    /// <summary>Archiving mode. Defaults to <see cref="CycleAudioArchiveMode.Off"/>.</summary>
    public CycleAudioArchiveMode Mode { get; init; } = CycleAudioArchiveMode.Off;

    /// <summary>
    /// Archive directory. <c>null</c> (the default) resolves to the platform per-user
    /// application-data directory via <c>ConfigPathResolver.ResolveDefaultCycleAudioDirectory()</c>
    /// — never the repository or the executable directory (NFR-021: recordings contain real
    /// off-air audio and real third-party callsigns).
    /// </summary>
    public string? Directory { get; init; } = null;

    /// <summary>Maximum total archive size in megabytes before oldest-first deletion. Default 2048 (2 GB).</summary>
    public int MaxSizeMb { get; init; } = 2048;

    /// <summary>Maximum age of an archived file in hours before deletion. Default 168 (7 days).</summary>
    public int MaxAgeHours { get; init; } = 168;

    /// <summary>Whether to maintain the <c>cycle-archive.csv</c> sidecar manifest. Default true.</summary>
    public bool WriteManifest { get; init; } = true;
}
