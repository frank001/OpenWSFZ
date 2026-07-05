namespace OpenWSFZ.Ft8;

/// <summary>
/// FT8 §3.1 — 28-bit standard callsign packing (N28) matching the canonical
/// ft8_lib (kgoba/ft8_lib v2) <c>pack_basecall</c> / <c>pack28</c> functions in
/// <c>ft8/message.c</c>.
///
/// <para>
/// A standard FT8 callsign is normalised to a 6-character form and encoded as a
/// mixed-radix integer using the character-set tables from <c>ft8/text.h</c>:
/// <list type="table">
///   <item><term>Position 0</term><description>
///     <c>FT8_CHAR_TABLE_ALPHANUM_SPACE</c>: " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
///     (37 values; space=0, '0'=1…'9'=10, 'A'=11…'Z'=36)
///   </description></item>
///   <item><term>Position 1</term><description>
///     <c>FT8_CHAR_TABLE_ALPHANUM</c>: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
///     (36 values; '0'=0…'9'=9, 'A'=10…'Z'=35  — NO space)
///   </description></item>
///   <item><term>Position 2</term><description>
///     <c>FT8_CHAR_TABLE_NUMERIC</c>: "0123456789" (10 values)
///   </description></item>
///   <item><term>Positions 3–5</term><description>
///     <c>FT8_CHAR_TABLE_LETTERS_SPACE</c>: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
///     (27 values; space=0, 'A'=1…'Z'=26)
///   </description></item>
/// </list>
/// </para>
///
/// <para>
/// The mixed-radix formula is:
/// <code>
/// n = ((((n0 * 36 + n1) * 10 + n2) * 27 + n3) * 27 + n4) * 27 + n5
/// N28 = NTOKENS + MAX22 + n   (= 2,063,592 + 4,194,304 + n = 6,257,896 + n)
/// </code>
/// where NTOKENS=2,063,592 and MAX22=4,194,304 are the ft8_lib constants that
/// separate standard callsigns from special tokens and 22-bit hashed callsigns.
/// </para>
///
/// <para>
/// The resulting N28 is packed MSB-first into 4 bytes using bits 27..0:
/// <code>
/// byte[0] = (N28 >> 20) &amp; 0xFF   // bits 27..20
/// byte[1] = (N28 >> 12) &amp; 0xFF   // bits 19..12
/// byte[2] = (N28 >>  4) &amp; 0xFF   // bits 11..4
/// byte[3] = (N28 &lt;&lt;  4) &amp; 0xF0  // bits 3..0 in high nibble
/// </code>
/// This layout is consumed by the native shim's AP injection loop (shim 20260021),
/// which reads bits MSB-first (i=0 → byte[0] bit 7 → N28 bit 27).
/// </para>
///
/// <para>
/// The two standard normalization patterns:
/// <list type="bullet">
///   <item>AB0XYZ (digit at callsign index 2, length ≤ 6): c6 = callsign right-padded to 6</item>
///   <item>A0XYZ  (digit at callsign index 1, length ≤ 5): c6 = " " + callsign right-padded to 6</item>
/// </list>
/// are packed into the standard-callsign N28 sub-range (<c>n28 ≥ NTOKENS + MAX22</c>), unchanged
/// since this class's introduction.
/// </para>
///
/// <para>
/// <b>Extended encoding (f-003-ap-assist-nonstandard-callsigns).</b> <see cref="Pack28"/> also
/// packs two further <c>c28</c> sub-ranges so that AP-assisted decode need not be disabled for
/// them:
/// <list type="bullet">
///   <item>Special tokens <c>"CQ"</c>, <c>"DE"</c>, <c>"QRZ"</c>, and a 3-digit numeral-suffixed
///     CQ (<c>"CQ nnn"</c>, <c>nnn</c> = <c>000</c>–<c>999</c>) into the special-token sub-range
///     (<c>n28 &lt; NTOKENS</c>).</item>
///   <item>Any nonstandard/compound callsign (3–11 characters, not matching either standard
///     pattern above) into the 22-bit hashed-callsign sub-range
///     (<c>NTOKENS ≤ n28 &lt; NTOKENS + MAX22</c>) via the published <c>ihashcall</c> algorithm
///     (see <see cref="Ihashcall"/>).</item>
/// </list>
/// A directed CQ with a non-numeric suffix (e.g. <c>"CQ DX"</c>, <c>"CQ POTA"</c>) and any
/// malformed input (empty/whitespace-only, or longer than 11 characters after the checks above)
/// remain unsupported; <see cref="Pack28"/> returns an empty array for those. Callers treat an
/// empty return as an unambiguous "disable AP for this input" signal.
/// </para>
/// </summary>
public static class Ft8CallsignPacker
{
    // ft8_lib NTOKENS + MAX22 — base offset for standard callsign N28 values.
    private const long NTokens = 2_063_592L;         // special tokens + CQ nnn variants
    private const long Max22   = 4_194_304L;         // 2^22 — non-standard 22-bit hashed callsign space
    private const long Offset28 = NTokens + Max22;   // = 6,257,896 — standard callsign N28 base

    // Special-token n28 assignments (source: Franke/Somerville/Taylor, QEX 2020, §III-A Table I;
    // cross-referenced against qa/rr-study/synth/packing.py's independent implementation).
    private const long N28De         = 0L;
    private const long N28Qrz        = 1L;
    private const long N28Cq         = 2L;
    private const long N28CqNnnBase  = 3L;            // CQ 000 = 3, CQ 001 = 4, ..., CQ 999 = 1002

    // ihashcall (WSJT-X packjt77.f90, reproduced identically in ft8_lib) — see Ihashcall's doc
    // comment for the formula and f-001-hashed-callsign-resolution/design.md's Context section
    // for provenance.
    private const string HashAlphabet = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"; // 38 characters
    private const ulong HashMultConst = 47_055_833_459UL;
    private const int HashFieldChars = 11;

    /// <summary>
    /// Packs a standard FT8 callsign into the 4-byte MSB-first representation of
    /// the 28-bit N28 value used in the FT8 message payload (bits 0–27 for call_to
    /// or bits 29–56 for call_de in a standard i3=1 message).
    /// </summary>
    /// <param name="callsign">
    /// The callsign string (case-insensitive, leading/trailing whitespace stripped).
    /// Must conform to one of the two standard normalisation patterns (digit at
    /// index 1 or 2 of the callsign).
    /// </param>
    /// <returns>
    /// A 4-byte array [byte0, byte1, byte2, byte3] representing N28 MSB-first,
    /// or an empty array if the callsign cannot be encoded as a standard callsign.
    /// Callers treat an empty return as "AP disabled for this callsign".
    /// </returns>
    public static byte[] Pack28(string callsign)
    {
        if (string.IsNullOrWhiteSpace(callsign)) return [];
        string cs = callsign.Trim().ToUpperInvariant();

        // ── Special tokens (n28 < NTOKENS) ──────────────────────────────────
        if (cs == "DE") return PackBytes(N28De);
        if (cs == "QRZ") return PackBytes(N28Qrz);
        if (cs == "CQ") return PackBytes(N28Cq);

        if (cs.StartsWith("CQ ", StringComparison.Ordinal))
        {
            string suffix = cs["CQ ".Length..];
            if (suffix.Length == 3 && suffix.All(char.IsAsciiDigit))
                return PackBytes(N28CqNnnBase + int.Parse(suffix));

            // Directed "CQ ABCD" form (non-numeric 2–4 character suffix) — exact c28 encoding
            // not yet confirmed (design D3); tracked as a follow-up, not guessed at here.
            return [];
        }

        // ── Standard basecall (n28 ≥ NTOKENS + MAX22) — unchanged existing path ──
        string? norm = Normalise(callsign);
        if (norm is not null)
        {
            int n0 = IndexAlphanumSpace(norm[0]);  // FT8_CHAR_TABLE_ALPHANUM_SPACE (37)
            int n1 = IndexAlphanum(norm[1]);        // FT8_CHAR_TABLE_ALPHANUM (36, no space)
            int n2 = IndexNumeric(norm[2]);          // FT8_CHAR_TABLE_NUMERIC (10)
            int n3 = IndexLettersSpace(norm[3]);     // FT8_CHAR_TABLE_LETTERS_SPACE (27)
            int n4 = IndexLettersSpace(norm[4]);
            int n5 = IndexLettersSpace(norm[5]);

            if (n0 >= 0 && n1 >= 0 && n2 >= 0 && n3 >= 0 && n4 >= 0 && n5 >= 0)
            {
                long n = n0;
                n = n * 36 + n1;
                n = n * 10 + n2;
                n = n * 27 + n3;
                n = n * 27 + n4;
                n = n * 27 + n5;
                return PackBytes(n + Offset28);
            }
        }

        // ── Nonstandard/compound callsign (NTOKENS ≤ n28 < NTOKENS + MAX22) ──
        // 3–11 characters, drawn from the 38-character hash alphabet, that didn't match a
        // standard pattern above — hash it instead of giving up (f-003 Gap B).
        if (cs.Length >= 3 && cs.Length <= HashFieldChars && IsHashAlphabet(cs))
            return PackBytes(NTokens + Ihashcall(cs, bits: 22));

        return [];
    }

    /// <summary>
    /// Computes the published <c>ihashcall</c> callsign hash (WSJT-X's <c>packjt77.f90</c>,
    /// reproduced identically in <c>ft8_lib</c>; formula documented in
    /// <c>f-001-hashed-callsign-resolution/design.md</c>'s Context section):
    /// <code>
    /// n8 = 0
    /// for each of up to 11 characters (charset: space, 0-9, A-Z, /):
    ///     n8 = 38 * n8 + char_index
    /// hash = (47055833459 * n8) >> (64 - m)     // keep the top m bits
    /// </code>
    /// The callsign is right-padded with spaces to the full 11-character field (space is index 0
    /// in the hash alphabet, so padding contributes zero to n8) — this is what makes the hash
    /// depend only on the callsign's own characters, left-aligned in the field, regardless of
    /// length.
    /// </summary>
    /// <remarks>
    /// The reference multiplication overflows 64 bits (the full product needs ~94 bits for an
    /// 11-character input) — but because the result only ever keeps bits <c>42..63</c> of the
    /// product (<c>&gt;&gt; 42</c> then a 22-bit mask), those bits are identical whether computed
    /// from the full product or from the product truncated to its low 64 bits. A plain
    /// <see cref="ulong"/> multiply (wraps mod 2^64, matching the native/Fortran integer overflow
    /// this formula relies on) is therefore exact — no <see cref="System.Numerics.BigInteger"/>
    /// needed. This is an independent C# port (design D2), not a P/Invoke into the native shim.
    /// </remarks>
    /// <param name="callsign">The callsign string to hash (case-insensitive).</param>
    /// <param name="bits">
    /// Which published hash width to return: 22 (the standard-message <c>c28</c> sub-range this
    /// packer uses), 12, or 10 (narrower Type-4 widths — always the top bits of the 22-bit hash).
    /// </param>
    /// <returns>The hash value in <c>[0, 2^bits)</c>.</returns>
    /// <exception cref="ArgumentOutOfRangeException"><paramref name="bits"/> is not 22, 12, or 10.</exception>
    /// <exception cref="ArgumentException">
    /// <paramref name="callsign"/> is longer than 11 characters, or contains a character outside
    /// the 38-character hash alphabet.
    /// </exception>
    internal static int Ihashcall(string callsign, int bits = 22)
    {
        if (bits != 22 && bits != 12 && bits != 10)
            throw new ArgumentOutOfRangeException(nameof(bits), bits, "ihashcall: bits must be 22, 12, or 10.");

        string call = callsign.Trim().ToUpperInvariant();
        if (call.Length > HashFieldChars)
            throw new ArgumentException($"ihashcall: callsign '{call}' exceeds {HashFieldChars} characters.", nameof(callsign));

        string padded = call.PadRight(HashFieldChars);

        ulong n8 = 0;
        foreach (char ch in padded)
        {
            int idx = HashAlphabet.IndexOf(ch);
            if (idx < 0)
                throw new ArgumentException($"ihashcall: character '{ch}' in '{call}' is not in the 38-character hash alphabet.", nameof(callsign));
            n8 = 38UL * n8 + (ulong)idx;
        }

        ulong full22 = unchecked(HashMultConst * n8) >> (64 - 22);
        full22 &= (1UL << 22) - 1;
        return bits == 22 ? (int)full22 : (int)(full22 >> (22 - bits));
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private static bool IsHashAlphabet(string s)
    {
        foreach (char c in s)
            if (HashAlphabet.IndexOf(c) < 0) return false;
        return true;
    }

    private static byte[] PackBytes(long n28) =>
    [
        (byte)((n28 >> 20) & 0xFF),
        (byte)((n28 >> 12) & 0xFF),
        (byte)((n28 >>  4) & 0xFF),
        (byte)((n28 <<  4) & 0xF0),
    ];

    /// <summary>
    /// Normalises a callsign to the 6-character form expected by pack_basecall,
    /// mirroring the two pattern checks in ft8_lib message.c:
    ///   is_digit(cs[2]) &amp;&amp; length ≤ 6  → AB0XYZ pattern, right-pad to 6
    ///   is_digit(cs[1]) &amp;&amp; length ≤ 5  → A0XYZ  pattern, left-pad with space then right-pad
    /// Returns null if neither pattern applies (callsign cannot be a standard basecall).
    /// </summary>
    private static string? Normalise(string callsign)
    {
        if (string.IsNullOrWhiteSpace(callsign)) return null;
        string cs = callsign.ToUpperInvariant().Trim();

        string norm;
        if (cs.Length >= 3 && cs.Length <= 6 && char.IsAsciiDigit(cs[2]))
        {
            // AB0XYZ pattern: district digit at index 2, copy as-is, right-pad to 6.
            norm = cs.PadRight(6);
        }
        else if (cs.Length >= 2 && cs.Length <= 5 && char.IsAsciiDigit(cs[1]))
        {
            // A0XYZ pattern: district digit at index 1, left-pad with one space.
            norm = (" " + cs).PadRight(6);
        }
        else
        {
            return null; // Does not match either standard callsign pattern.
        }

        if (norm.Length != 6) return null;
        if (!IsValidNormalisedForm(norm)) return null;
        return norm;
    }

    private static bool IsValidNormalisedForm(string s)
        => IndexAlphanumSpace(s[0]) >= 0
            && IndexAlphanum(s[1]) >= 0
            && char.IsAsciiDigit(s[2])
            && IndexLettersSpace(s[3]) >= 0
            && IndexLettersSpace(s[4]) >= 0
            && IndexLettersSpace(s[5]) >= 0;

    // FT8_CHAR_TABLE_ALPHANUM_SPACE: " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    // space=0, '0'=1, '1'=2, ..., '9'=10, 'A'=11, 'B'=12, ..., 'Z'=36
    private static int IndexAlphanumSpace(char c)
    {
        if (c == ' ') return 0;
        if (c >= '0' && c <= '9') return c - '0' + 1;
        if (c >= 'A' && c <= 'Z') return c - 'A' + 11;
        return -1;
    }

    // FT8_CHAR_TABLE_ALPHANUM: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    // '0'=0, '1'=1, ..., '9'=9, 'A'=10, 'B'=11, ..., 'Z'=35  (no space)
    private static int IndexAlphanum(char c)
    {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'A' && c <= 'Z') return c - 'A' + 10;
        return -1;
    }

    // FT8_CHAR_TABLE_NUMERIC: "0123456789"
    // '0'=0, ..., '9'=9
    private static int IndexNumeric(char c)
    {
        if (c >= '0' && c <= '9') return c - '0';
        return -1;
    }

    // FT8_CHAR_TABLE_LETTERS_SPACE: " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    // space=0, 'A'=1, 'B'=2, ..., 'Z'=26
    private static int IndexLettersSpace(char c)
    {
        if (c == ' ') return 0;
        if (c >= 'A' && c <= 'Z') return c - 'A' + 1;
        return -1;
    }
}
