using System.Text;

namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Unpacks a 77-bit FT8 message payload into a human-readable string.
///
/// Supported message types (Franke &amp; Taylor 2019):
///   Type 1  (i3=0, n3=0–3) — Standard QSO: callsign + callsign + report/grid
///   Type 2  (i3=0, n3=4)   — EU VHF Contest (decoded as hex in v1)
///   Type 3  (i3=0, n3=5)   — RTTY Roundup (decoded as hex in v1)
///   Type 4  (i3=4)          — Non-standard callsigns (decoded as hex in v1)
///   Type 5  (i3=5)          — Free text ≤13 chars
///   Others                  — hex fallback
/// </summary>
internal static class MessageUnpacker
{
    // ── Callsign base-37 alphabet ─────────────────────────────────────────────
    private const string CallAlphabet = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

    // ── Grid-square alphabet (A-R for the two letters, 0-9 for digits) ────────
    private const string GridLetters = "ABCDEFGHIJKLMNOPQR";

    // ── Free-text alphabet (printable subset, 42 characters) ─────────────────
    private const string FreeAlphabet = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ+-./?";

    /// <summary>
    /// Unpacks a 77-bit message.
    /// </summary>
    /// <param name="bits">Array of at least 77 bytes, each 0 or 1 (MSB-first).</param>
    /// <returns>Human-readable message string.</returns>
    public static string Unpack(ReadOnlySpan<byte> bits)
    {
        if (bits.Length < 77)
            return HexFallback(bits, Math.Min(bits.Length, 77));

        // i3: bits 74–76 (3 bits, MSB-first)
        int i3 = (bits[74] << 2) | (bits[75] << 1) | bits[76];

        return i3 switch
        {
            0 => UnpackType1Or2(bits),   // n3 sub-type
            1 => UnpackType1(bits),      // n3 not used (legacy)
            5 => UnpackFreeText(bits),
            _ => HexFallback(bits, 77),
        };
    }

    /// <summary>
    /// Attempts to unpack a 77-bit FT8 message payload into a human-readable string.
    /// Returns <c>null</c> for message types that are not yet implemented (i3 ∉ {0, 1, 5},
    /// or i3=0 with n3 ∈ {4, 5}) so that callers can skip rather than display a raw
    /// hex fallback.
    /// </summary>
    /// <param name="bits">Array of at least 77 bytes, each 0 or 1 (MSB-first).</param>
    /// <returns>
    /// Decoded message string, or <c>null</c> if the message type is not supported.
    /// </returns>
    public static string? TryUnpack(ReadOnlySpan<byte> bits)
    {
        if (bits.Length < 77) return null;

        // i3: bits 74–76 (3 bits, MSB-first)
        int i3 = (bits[74] << 2) | (bits[75] << 1) | bits[76];

        // i3=1 is the legacy Standard QSO format — same callsign + callsign + extra layout
        // as i3=0, so apply the same extra-field validation to plug the false-positive bypass.
        if (i3 == 1)
        {
            ulong rg = ReadBits(bits, 56, 15);
            if (!IsValidExtra15(rg)) return null;
        }

        return i3 switch
        {
            0 => UnpackType1Or2OrNull(bits),
            1 => UnpackType1(bits),
            5 => UnpackFreeText(bits),
            _ => null,                      // i3=2,3,4,6,7 — not yet implemented
        };
    }

    // ── Type 1: Standard QSO ──────────────────────────────────────────────────

    private static string UnpackType1Or2(ReadOnlySpan<byte> bits)
    {
        // n3: bits 71–73 (3 bits)
        int n3 = (bits[71] << 2) | (bits[72] << 1) | bits[73];
        return n3 <= 3 ? UnpackType1(bits) : HexFallback(bits, 77);
    }

    // Null-returning variant used by TryUnpack — returns null for n3=4,5 instead of
    // calling HexFallback, so callers can distinguish "decoded" from "unsupported".
    // Also filters out false positives whose report/grid extra field contains an
    // impossible value for a real FT8 signal.  (p11 Part 1)
    private static string? UnpackType1Or2OrNull(ReadOnlySpan<byte> bits)
    {
        int n3 = (bits[71] << 2) | (bits[72] << 1) | bits[73];
        if (n3 > 3) return null;

        ulong rg = ReadBits(bits, 56, 15);
        if (!IsValidExtra15(rg)) return null;

        return UnpackType1(bits);
    }

    private static string UnpackType1(ReadOnlySpan<byte> bits)
    {
        // Bit layout (FT8 spec):
        //   Callsign 1 : bits  0–27  (28 bits, base-37 encoded, 6 chars)
        //   Callsign 2 : bits 28–55  (28 bits, base-37 encoded, 6 chars)
        //   Report/grid: bits 56–70  (15 bits)
        //   n3         : bits 71–73  (3 bits)
        //   i3         : bits 74–76  (3 bits)

        ulong c1 = ReadBits(bits, 0,  28);
        ulong c2 = ReadBits(bits, 28, 28);
        ulong rg = ReadBits(bits, 56, 15);

        string call1 = DecodeCallsign28(c1);
        string call2 = DecodeCallsign28(c2);
        string extra = DecodeReport15(rg);

        return $"{call1} {call2} {extra}".Trim();
    }

    // ── Type 5: Free text ─────────────────────────────────────────────────────

    private static string UnpackFreeText(ReadOnlySpan<byte> bits)
    {
        // 71 bits encode up to 13 characters from a 42-char alphabet.
        // Value = sum(char_i * 42^i) packed MSB-first.
        ulong value = 0;
        for (int i = 0; i < 71; i++)
            value = (value << 1) | bits[i];

        var sb = new StringBuilder(13);
        for (int i = 0; i < 13; i++)
        {
            int idx = (int)(value % 42);
            sb.Insert(0, FreeAlphabet[idx]);
            value /= 42;
        }

        return sb.ToString().TrimEnd();
    }

    // ── Callsign decoding ─────────────────────────────────────────────────────

    private static string DecodeCallsign28(ulong packed)
    {
        // Special packed values for CQ, DE, QRZ, etc.
        if (packed <= 2)
            return packed switch { 0 => "DE", 1 => "QRZ", _ => "CQ" };

        // FT8 standard mixed-radix callsign decoding (Franke & Taylor 2019;
        // kgoba/ft8_lib unpack.c).
        //
        // The 28-bit field stores a 6-character callsign using positional alphabets:
        //   pos 5, 4, 3 : {space, A-Z}            (27 options each, space=0 A=1…Z=26)
        //   pos 2       : {0-9}                    (10 options — digit only)
        //   pos 1, 0    : {space, 0-9, A-Z}        (37 options, space=0 '0'=1…'9'=10 A=11…Z=36)
        //
        // Decode from LSBs upward, then Trim both ends to remove padding spaces.
        ulong n = packed - 3;

        Span<char> c = stackalloc char[6];

        for (int i = 5; i >= 3; i--)
        {
            ulong v = n % 27; n /= 27;
            c[i] = v == 0 ? ' ' : (char)('A' + v - 1);
        }

        c[2] = (char)('0' + (n % 10)); n /= 10;

        for (int i = 1; i >= 0; i--)
        {
            ulong v = n % 37; n /= 37;
            c[i] = v == 0 ? ' ' : v <= 10 ? (char)('0' + v - 1) : (char)('A' + v - 11);
        }

        return new string(c).Trim();
    }

    private static string DecodeReport15(ulong packed)
    {
        // Bit 14: 0 = grid square, 1 = signal report / RRR / RR73 / 73.
        bool isReport = (packed & 0x4000UL) != 0;
        ulong val     = packed & 0x3FFFUL;

        if (!isReport)
        {
            // Grid square: 2 letters + 2 digits (4 chars from 18²×10² = 32 400 combos).
            // R-prefix contest serials (val ≥ 32 400) are not supported: after the 14-bit
            // mask, val is at most 16 383 < 32 400, so R-prefix messages are silently
            // mis-decoded as standard grids.  Correct handling requires the full 15-bit
            // value; this is deferred pending spec clarification.
            int r1 = (int)(val / 1800);
            int r2 = (int)((val % 1800) / 100);
            int r3 = (int)((val % 100) / 10);
            int r4 = (int)(val % 10);
            return $"{GridLetters[r1]}{GridLetters[r2]}{r3}{r4}";
        }
        else
        {
            // Signal report encoding (ft8_lib / WSJT-X convention):
            //   val 1 = RRR, 2 = RR73, 3 = 73
            //   val 4–63:  plain SNR,  display as +DD or -DD  (SNR = val − 35)
            //   val 64–127: R-prefix,  display as R+DD or R-DD (SNR = val − 64 − 35)
            if (val == 1) return "RRR";
            if (val == 2) return "RR73";
            if (val == 3) return "73";

            if (val >= 64)
            {
                // R-prefix — "roger, your signal is X dB"
                int snr = (int)(val - 64) - 35;
                return snr >= 0 ? $"R+{snr:D2}" : $"R{snr:D2}";
            }

            // Plain SNR report (val 4–63 → SNR −31 to +28 dB).
            int snrPlain = (int)val - 35;
            return snrPlain >= 0 ? $"+{snrPlain:D2}" : $"{snrPlain:D2}";
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static ulong ReadBits(ReadOnlySpan<byte> bits, int start, int count)
    {
        ulong val = 0;
        for (int i = 0; i < count; i++)
            val = (val << 1) | bits[start + i];
        return val;
    }

    /// <summary>
    /// Returns <c>true</c> if the 15-bit extra field is within the documented FT8 encoding range.
    ///
    /// <para>Report field (bit 14 = 1) encoding (ft8_lib / WSJT-X convention):
    /// <list type="bullet">
    ///   <item>val 1 = RRR, val 2 = RR73, val 3 = 73 (special)</item>
    ///   <item>val 4–63: plain SNR report (SNR = val − 35, range −31 to +28 dB)</item>
    ///   <item>val 64–127: R-prefix report — "roger + SNR" (SNR = val − 64 − 35)</item>
    /// </list>
    /// Maximum valid val = 127.  Values 128–16383 have no defined FT8 meaning and
    /// are strong indicators of a false-positive LDPC convergence.
    /// </para>
    ///
    /// <para>Grid squares (bit 14 = 0): after the 14-bit mask, val is at most 16 383,
    /// always within the standard 4-char grid range (0–32 399) — no filtering
    /// is possible until the 15-bit mask ambiguity is resolved.</para>
    /// </summary>
    private static bool IsValidExtra15(ulong packed)
    {
        bool isReport = (packed & 0x4000UL) != 0;
        ulong val     = packed & 0x3FFFUL;

        return isReport
            ? val >= 1 && val <= 127  // specials (1–3), plain SNR (4–63), R+SNR (64–127)
            : true;                   // 14-bit mask → val ≤ 16383, always a valid grid
    }

    /// <summary>Returns the first <paramref name="bitCount"/> bits as a hex string.</summary>
    private static string HexFallback(ReadOnlySpan<byte> bits, int bitCount)
    {
        // Pack the bits into bytes then hex-encode.
        int byteCount = (bitCount + 7) / 8;
        Span<byte> packed = stackalloc byte[byteCount];
        for (int i = 0; i < bitCount; i++)
        {
            int b = i / 8;
            int pos = 7 - (i % 8);
            packed[b] |= (byte)(bits[i] << pos);
        }

        return Convert.ToHexString(packed)[..Math.Min(20, byteCount * 2)];
    }
}
