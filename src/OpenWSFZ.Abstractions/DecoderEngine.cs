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
