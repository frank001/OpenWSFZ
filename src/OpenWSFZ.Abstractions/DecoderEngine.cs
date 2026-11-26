namespace OpenWSFZ.Abstractions;

/// <summary>
/// Which decoder engine runs each cycle (<c>decoder.engine</c>, DR-2 step 2a, FR-108). <see cref="Classic"/> is the multi-pass decoder and is the
/// default: an absent key, a missing <c>decoder</c> section and any value that is not recognised all read <see cref="Classic"/>. <see cref="Lean"/> is
/// the rebuilt single-call engine (<c>ftz_decode_cycle</c>); in step 2a it decodes what the classic primary pass decodes, tier A only.
/// </summary>
public enum DecoderEngine
{
    /// <summary>The classic decoder: every pass, every fallback, exactly as before the setting existed. The default.</summary>
    Classic = 0,

    /// <summary>The lean engine: one native call per cycle (spectrogram, candidates, tier A). Experimental in step 2a.</summary>
    Lean = 1,
}

/// <summary>Parsing and naming for <see cref="DecoderEngine"/>; the config file carries the engine as a string.</summary>
public static class DecoderEngineNames
{
    /// <summary>The config-file spelling of <see cref="DecoderEngine.Classic"/>.</summary>
    public const string Classic = "classic";

    /// <summary>The config-file spelling of <see cref="DecoderEngine.Lean"/>.</summary>
    public const string Lean = "lean";

    /// <summary>
    /// Reads the config string. <c>"lean"</c> (any case, surrounding white space ignored) is <see cref="DecoderEngine.Lean"/>; everything else,
    /// including <c>null</c>, an empty string and an unknown word, is <see cref="DecoderEngine.Classic"/>.
    /// </summary>
    public static DecoderEngine Parse(string? value)
        => string.Equals(value?.Trim(), Lean, StringComparison.OrdinalIgnoreCase) ? DecoderEngine.Lean : DecoderEngine.Classic;
}

/// <summary>
/// How much work the lean engine does per cycle (<c>decoder.effort</c>, DR-2 step 2d, FR-108). <see cref="Normal"/> is the default (tier B on, up to three
/// subtract-and-retry rounds); <see cref="Fast"/> runs no tier B and one round. It applies only with <see cref="DecoderEngine.Lean"/>; with the classic
/// engine it has no effect. An absent key and any value that is not recognised read <see cref="Normal"/>.
/// </summary>
public enum DecoderEffort
{
    /// <summary>Tier B on, up to three rounds of subtract-and-retry. The default.</summary>
    Normal = 0,

    /// <summary>No tier B and one round of subtract-and-retry; CQ-AP and the cross-cycle stage are unchanged.</summary>
    Fast = 1,
}

/// <summary>Parsing and naming for <see cref="DecoderEffort"/>; the config file carries the effort as a string.</summary>
public static class DecoderEffortNames
{
    /// <summary>The config-file spelling of <see cref="DecoderEffort.Normal"/>.</summary>
    public const string Normal = "normal";

    /// <summary>The config-file spelling of <see cref="DecoderEffort.Fast"/>.</summary>
    public const string Fast = "fast";

    /// <summary>
    /// Reads the config string. <c>"fast"</c> (any case, surrounding white space ignored) is <see cref="DecoderEffort.Fast"/>; everything else,
    /// including <c>null</c>, an empty string and an unknown word, is <see cref="DecoderEffort.Normal"/>.
    /// </summary>
    public static DecoderEffort Parse(string? value)
        => string.Equals(value?.Trim(), Fast, StringComparison.OrdinalIgnoreCase) ? DecoderEffort.Fast : DecoderEffort.Normal;
}
