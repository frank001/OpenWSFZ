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

    // ── Type 1: Standard QSO ──────────────────────────────────────────────────

    private static string UnpackType1Or2(ReadOnlySpan<byte> bits)
    {
        // n3: bits 71–73 (3 bits)
        int n3 = (bits[71] << 2) | (bits[72] << 1) | bits[73];
        return n3 <= 3 ? UnpackType1(bits) : HexFallback(bits, 77);
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

        // Remove CQ variant prefix space.
        packed -= 3;

        // 6-character base-37 callsign.
        var chars = new char[6];
        for (int i = 5; i >= 0; i--)
        {
            chars[i] = CallAlphabet[(int)(packed % 37)];
            packed /= 37;
        }

        return new string(chars).TrimStart(' ');
    }

    private static string DecodeReport15(ulong packed)
    {
        // Bit 0: 0 = grid, 1 = signal report or RRR/73 etc.
        bool isReport = (packed & 0x4000UL) != 0;
        ulong val     = packed & 0x3FFFUL;

        if (!isReport)
        {
            // Grid square: 2 letters + 2 digits (4 chars from 18²×10² = 32400 combos).
            if (val >= 32400) return $"R{val - 32400}";
            int r1 = (int)(val / 1800);
            int r2 = (int)((val % 1800) / 100);
            int r3 = (int)((val % 100) / 10);
            int r4 = (int)(val % 10);
            return $"{GridLetters[r1]}{GridLetters[r2]}{r3}{r4}";
        }
        else
        {
            // Signal report: offset integer dB.
            if (val == 1) return "RRR";
            if (val == 2) return "RR73";
            if (val == 3) return "73";
            int snr = (int)val - 35; // range -35 to +49
            return snr >= 0 ? $"+{snr:D2}" : $"{snr:D3}";
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
