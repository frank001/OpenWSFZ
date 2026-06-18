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
/// Only the two standard normalization patterns are supported:
/// <list type="bullet">
///   <item>AB0XYZ (digit at callsign index 2, length ≤ 6): c6 = callsign right-padded to 6</item>
///   <item>A0XYZ  (digit at callsign index 1, length ≤ 5): c6 = " " + callsign right-padded to 6</item>
/// </list>
/// Special tokens (CQ, DE, QRZ), /P and /R suffixes, and non-standard (>6-char)
/// callsigns are not handled; <see cref="Pack28"/> returns an empty array for those.
/// </para>
/// </summary>
public static class Ft8CallsignPacker
{
    // ft8_lib NTOKENS + MAX22 — base offset for standard callsign N28 values.
    // NTOKENS = 2,063,592 (special tokens + CQ variants).
    // MAX22   = 4,194,304 (2^22, non-standard 22-bit hashed callsign space).
    // Standard callsign N28 = NTOKENS + MAX22 + pack_basecall_result.
    private const long Offset28 = 2_063_592L + 4_194_304L; // = 6,257,896

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
        string? norm = Normalise(callsign);
        if (norm is null) return [];

        int n0 = IndexAlphanumSpace(norm[0]);  // FT8_CHAR_TABLE_ALPHANUM_SPACE (37)
        int n1 = IndexAlphanum(norm[1]);        // FT8_CHAR_TABLE_ALPHANUM (36, no space)
        int n2 = IndexNumeric(norm[2]);          // FT8_CHAR_TABLE_NUMERIC (10)
        int n3 = IndexLettersSpace(norm[3]);     // FT8_CHAR_TABLE_LETTERS_SPACE (27)
        int n4 = IndexLettersSpace(norm[4]);
        int n5 = IndexLettersSpace(norm[5]);

        if (n0 < 0 || n1 < 0 || n2 < 0 || n3 < 0 || n4 < 0 || n5 < 0)
            return [];

        long n = n0;
        n = n * 36 + n1;
        n = n * 10 + n2;
        n = n * 27 + n3;
        n = n * 27 + n4;
        n = n * 27 + n5;
        long N28 = n + Offset28;

        return [
            (byte)((N28 >> 20) & 0xFF),
            (byte)((N28 >> 12) & 0xFF),
            (byte)((N28 >>  4) & 0xFF),
            (byte)((N28 <<  4) & 0xF0),
        ];
    }

    // ── Private helpers ───────────────────────────────────────────────────────

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
