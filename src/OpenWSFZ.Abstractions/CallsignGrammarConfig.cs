namespace OpenWSFZ.Abstractions;

/// <summary>
/// A single reserved/never-allocated callsign prefix series, with an optional
/// synthetic-use carve-out (NFR-021).
/// </summary>
/// <param name="Prefix">
/// The prefix series this entry applies to (e.g. <c>"Q"</c>), matched against the
/// grammar-parsed prefix component of a callsign-position token (case-insensitive).
/// </param>
/// <param name="SyntheticCarveOut">
/// When <c>true</c>, a token matching <paramref name="Prefix"/> is treated as
/// shape-valid despite the prefix being reserved/never-allocated — this project's
/// own synthetic-callsign convention (NFR-021) uses the <c>Q</c>-series this way.
/// When <c>false</c>, a token matching <paramref name="Prefix"/> is rejected as
/// shape-invalid (the prefix is reserved for other uses and was never allocated to
/// any administration as a station-callsign prefix).
/// </param>
/// <param name="Note">Optional human-readable justification, carried through to the JSON file for operator/maintainer context.</param>
public sealed record CallsignPrefixExclusion(
    string  Prefix,
    bool    SyntheticCarveOut,
    string? Note = null);

/// <summary>
/// Configurable callsign shape-grammar parameters (<c>callsign-grammar.json</c>),
/// replacing the length-only D9-R3 oversized-callsign guard with an ITU Radio
/// Regulations Article 19 §19.68–19.69-derived structural check.
/// </summary>
/// <param name="DigitRunMax">
/// Maximum length of the contiguous digit-run immediately preceding a callsign's
/// suffix (the mandatory call-area numeral, or a wider special-event/commemorative
/// numeral convention). Default 3.
/// </param>
/// <param name="TotalLengthMax">
/// Maximum total length of the base callsign (before any portable suffix), matching
/// the Type 4 <c>pack58</c> charset width. Default 11 (unchanged from D-011).
/// </param>
/// <param name="SuffixLengthMax">
/// Maximum length of the letters-only suffix component (the portion of the base
/// callsign after the digit-run). Default 6.
/// </param>
/// <param name="ReservedPrefixExclusions">
/// Short list of prefix series ITU has never allocated for station-callsign use,
/// with any synthetic-use carve-outs (see <see cref="CallsignPrefixExclusion"/>).
/// This is an <em>exclusion</em> list, not a positive allow-list: a prefix absent
/// from this list is never rejected on that basis alone.
/// </param>
public sealed record CallsignGrammarConfig(
    int DigitRunMax,
    int TotalLengthMax,
    int SuffixLengthMax,
    IReadOnlyList<CallsignPrefixExclusion> ReservedPrefixExclusions)
{
    /// <summary>
    /// Compiled-in default grammar, used when <c>callsign-grammar.json</c> is absent
    /// or malformed, and as the fallback for callers that do not inject an
    /// <see cref="ICallsignGrammarStore"/> (e.g. pre-existing test call sites).
    ///
    /// <para>
    /// Source note (task 0.1, <c>f-002-callsign-structure-region-lookup</c>): ITU Radio
    /// Regulations Article 19 §19.68 gives the amateur-station call sign as either
    /// (a) one letter from {B,F,G,I,K,M,N,R,W} + one numeral (0/1 permitted for amateur
    /// stations per §19.69) + a group of ≤4 characters ending in a letter, or (b) two
    /// characters + one numeral + the same ≤4-character suffix. Confirmed independently
    /// this session via two secondary sources (a WebSearch snippet quoting the clause
    /// language directly, and a Wikipedia cross-check) — the primary ITU PDF
    /// (<c>itu.int/.../fxm-art19-sec3.pdf</c>) could not be machine-extracted in either
    /// research pass (compressed PDF content stream). This is the standard/permanent
    /// shape; the digit-run (3) and suffix-length (6) caps below are deliberately wider
    /// than that standard case (single numeral, ≤4-char suffix) to admit genuine Type 4
    /// nonstandard/special-event literals (D-011) and are backstopped by the mandatory
    /// S5 false-positive-rate re-run rather than by a verified primary citation for the
    /// widened caps specifically.
    /// </para>
    /// </summary>
    public static CallsignGrammarConfig BuiltInDefault { get; } = new(
        DigitRunMax:      3,
        TotalLengthMax:   11,
        SuffixLengthMax:  6,
        ReservedPrefixExclusions:
        [
            new CallsignPrefixExclusion(
                Prefix:            "Q",
                SyntheticCarveOut: true,
                Note: "The Q-series is reserved for Q-codes (ITU Radio Regulations) and has " +
                      "never been allocated as a station-callsign prefix to any administration. " +
                      "Carved out here for this project's synthetic test-callsign convention " +
                      "(NFR-021, R&R Study traffic) — a Q-prefix token is shape-valid despite the " +
                      "series being otherwise reserved.")
        ]);
}
