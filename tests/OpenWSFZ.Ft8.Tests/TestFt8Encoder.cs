using OpenWSFZ.Ft8.Dsp;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Minimal FT8 encoder for generating deterministic synthetic test fixtures.
///
/// Supports Type 1 standard messages ("CQ CALLSIGN GRID").  Not a general-purpose
/// FT8 encoder — only the subset required for the decoder integration test (D6).
/// </summary>
internal static class TestFt8Encoder
{
    // ── FT8 constants ─────────────────────────────────────────────────────────

    private const int    SampleRate       = 12_000;
    private const int    SymbolCount      = 79;
    private const int    SamplesPerSymbol = 1_920;   // 12000 / 6.25
    private const double ToneSpacing      = 6.25;    // Hz

    private const int    TotalPcmSamples  = 180_000; // 15 s × 12 kHz

    // ── Public API ────────────────────────────────────────────────────────────

    /// <summary>
    /// Packs a Type 1 (i3=0, n3=0) standard QSO message into 77 bits.
    /// Use <see cref="EncodeCallsign28"/> and <see cref="EncodeReport15Grid"/> to
    /// convert human-readable values to the packed field integers.
    /// </summary>
    /// <param name="c1">28-bit packed callsign 1 (e.g. 2 for "CQ").</param>
    /// <param name="c2">28-bit packed callsign 2.</param>
    /// <param name="rg">15-bit packed report/grid.</param>
    /// <param name="n3">3-bit sub-type indicator (0 for standard grid/report).</param>
    /// <param name="i3">3-bit message type (0 for standard Type 1).</param>
    public static byte[] PackType1(ulong c1, ulong c2, ulong rg, int n3 = 0, int i3 = 0)
    {
        var bits = new byte[77];
        PackBitsInto(bits,  0, 28, c1);
        PackBitsInto(bits, 28, 28, c2);
        PackBitsInto(bits, 56, 15, rg);
        PackBitsInto(bits, 71,  3, (ulong)n3);
        PackBitsInto(bits, 74,  3, (ulong)i3);
        return bits;
    }

    /// <summary>
    /// Encodes a callsign string into a 28-bit packed integer.
    /// Special values: 0="DE", 1="QRZ", 2="CQ".
    /// For a regular callsign: right-pads to 6 chars, base-37 encodes, adds 3.
    /// </summary>
    public static ulong EncodeCallsign28(string callsign)
    {
        // Special cases.
        if (callsign.Equals("DE",  StringComparison.OrdinalIgnoreCase)) return 0;
        if (callsign.Equals("QRZ", StringComparison.OrdinalIgnoreCase)) return 1;
        if (callsign.Equals("CQ",  StringComparison.OrdinalIgnoreCase)) return 2;

        const string alpha = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        // Left-pad to 6 chars (base-37 standard callsign form).
        var padded = callsign.ToUpperInvariant().PadLeft(6, ' ');
        if (padded.Length > 6) padded = padded[^6..];

        ulong packed = 0;
        foreach (char ch in padded)
        {
            int idx = alpha.IndexOf(ch);
            if (idx < 0) idx = 0; // unknown → space
            packed = packed * 37 + (ulong)idx;
        }

        return packed + 3; // offset for special values 0-2
    }

    /// <summary>
    /// Encodes a 4-character Maidenhead grid square (e.g. "FN31") as a 15-bit packed integer.
    /// </summary>
    public static ulong EncodeReport15Grid(string grid)
    {
        const string letters = "ABCDEFGHIJKLMNOPQR";
        if (grid.Length < 4) return 0;
        int r1 = letters.IndexOf(char.ToUpper(grid[0]));
        int r2 = letters.IndexOf(char.ToUpper(grid[1]));
        int r3 = grid[2] - '0';
        int r4 = grid[3] - '0';
        if (r1 < 0 || r2 < 0 || r3 < 0 || r4 < 0) return 0;
        return (ulong)(r1 * 1800 + r2 * 100 + r3 * 10 + r4);
    }

    /// <summary>
    /// Appends a 14-bit CRC to the 77 message bits, returning a 91-bit information vector.
    /// </summary>
    public static byte[] AppendCrc14(byte[] msgBits)
    {
        var info = new byte[91];
        Array.Copy(msgBits, info, 77);
        uint crc = Crc14.Compute(info, 77);
        for (int i = 0; i < 14; i++)
            info[77 + i] = (byte)((crc >> (13 - i)) & 1);
        return info;
    }

    /// <summary>
    /// LDPC-encodes 91 information bits to a 174-bit codeword using Gaussian
    /// elimination over GF(2) on the FT8 (174,91) parity-check matrix.
    ///
    /// The 91 systematic bits (info) occupy codeword positions 0–90; the 83
    /// computed parity bits occupy positions 91–173.
    /// </summary>
    public static byte[] LdpcEncode(byte[] infoBits)
    {
        // Step 1: compute right-hand side of each check equation using only info bits.
        var rhs = new byte[87];
        for (int r = 0; r < 87; r++)
        {
            byte sum = 0;
            foreach (int j in LdpcDecoder.H[r])
                if (j < 91) sum ^= infoBits[j];
            rhs[r] = sum;
        }

        // Step 2: build augmented matrix A[87 rows × 84 cols].
        //   Columns 0..82  = H_parity (columns 91..173 of H)
        //   Column 83      = rhs
        var A = new byte[87, 84];
        for (int r = 0; r < 87; r++)
        {
            foreach (int j in LdpcDecoder.H[r])
                if (j >= 91) A[r, j - 91] = 1;
            A[r, 83] = rhs[r];
        }

        // Step 3: GF(2) Gaussian elimination (fully reduced row echelon form).
        var rowOfPivot = new int[83];
        Array.Fill(rowOfPivot, -1);
        int pivotRow = 0;

        for (int col = 0; col < 83 && pivotRow < 87; col++)
        {
            // Find a pivot row with a 1 in this column.
            int found = -1;
            for (int r = pivotRow; r < 87; r++)
                if (A[r, col] == 1) { found = r; break; }
            if (found < 0) continue; // linearly dependent column — skip

            // Swap with current pivot row.
            if (found != pivotRow)
                for (int c = 0; c < 84; c++)
                    (A[pivotRow, c], A[found, c]) = (A[found, c], A[pivotRow, c]);

            rowOfPivot[col] = pivotRow;

            // Eliminate this column from every other row.
            for (int r = 0; r < 87; r++)
                if (r != pivotRow && A[r, col] == 1)
                    for (int c = 0; c < 84; c++)
                        A[r, c] ^= A[pivotRow, c];

            pivotRow++;
        }

        // Step 4: read parity bits from the augmented column of each pivot row.
        var parity = new byte[83];
        for (int col = 0; col < 83; col++)
        {
            int pr = rowOfPivot[col];
            if (pr >= 0) parity[col] = A[pr, 83];
            // else: free variable — value is 0 (valid for a systematic code)
        }

        // Step 5: assemble the 174-bit codeword.
        var codeword = new byte[174];
        Array.Copy(infoBits, codeword, 91);
        Array.Copy(parity, 0, codeword, 91, 83);
        return codeword;
    }

    /// <summary>
    /// Converts 174 codeword bits into 79 FT8 symbol indices.
    ///
    /// The three Costas arrays are inserted at symbol positions 0–6, 36–42, and
    /// 72–78.  Each of the 58 data symbols is Gray-coded from 3 consecutive bits.
    /// </summary>
    public static int[] BitsToSymbols(byte[] codeword)
    {
        var symbols = new int[SymbolCount];

        // Costas arrays (FT8 spec: [3,1,4,0,6,5,2]).
        ReadOnlySpan<int> costas    = [3, 1, 4, 0, 6, 5, 2];
        ReadOnlySpan<int> costasPos = [0, 36, 72];
        foreach (int pos in costasPos)
            for (int i = 0; i < 7; i++)
                symbols[pos + i] = costas[i];

        // Collect data symbol positions (all non-Costas slots).
        var dataPos = new List<int>(58);
        for (int s = 0; s < SymbolCount; s++)
        {
            bool isCostas = s < 7 || (s >= 36 && s < 43) || (s >= 72 && s < 79);
            if (!isCostas) dataPos.Add(s);
        }

        // Map 3-bit groups to Gray-coded tone indices.
        // Gray(n) = n ^ (n >> 1) produces the 8-FSK tone for bits (b2, b1, b0).
        for (int di = 0; di < 58; di++)
        {
            int b2     = codeword[di * 3];
            int b1     = codeword[di * 3 + 1];
            int b0     = codeword[di * 3 + 2];
            int binary = (b2 << 2) | (b1 << 1) | b0;
            symbols[dataPos[di]] = binary ^ (binary >> 1); // Gray code
        }

        return symbols;
    }

    /// <summary>
    /// Generates a 180 000-sample (15 s at 12 kHz) mono float-32 PCM buffer
    /// containing a single FT8 frame starting at <paramref name="startSample"/>.
    /// </summary>
    /// <param name="symbols">79 symbol indices from <see cref="BitsToSymbols"/>.</param>
    /// <param name="baseFreqHz">Frequency of tone 0, in Hz.</param>
    /// <param name="startSample">First sample of the first FT8 symbol (default 0).</param>
    /// <param name="amplitude">Peak amplitude (default 0.5).</param>
    public static float[] SymbolsToPcm(
        int[]  symbols,
        double baseFreqHz,
        int    startSample = 0,
        float  amplitude   = 0.5f)
    {
        var pcm = new float[TotalPcmSamples];

        for (int sym = 0; sym < SymbolCount; sym++)
        {
            double toneHz = baseFreqHz + symbols[sym] * ToneSpacing;
            int    offset = startSample + sym * SamplesPerSymbol;

            for (int s = 0; s < SamplesPerSymbol; s++)
            {
                int idx = offset + s;
                if ((uint)idx < (uint)TotalPcmSamples)
                    pcm[idx] = amplitude
                        * (float)Math.Sin(2.0 * Math.PI * toneHz * s / SampleRate);
            }
        }

        return pcm;
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private static void PackBitsInto(byte[] bits, int start, int count, ulong value)
    {
        for (int i = count - 1; i >= 0; i--)
        {
            bits[start + i] = (byte)(value & 1);
            value >>= 1;
        }
    }
}
