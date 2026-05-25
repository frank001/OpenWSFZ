namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// LDPC(174,91) soft-decision decoder using the min-sum belief-propagation algorithm.
///
/// The parity-check matrix H (87 rows × 174 columns) is embedded from the FT8
/// specification (Franke &amp; Taylor 2019, Appendix A).  Each row of H specifies
/// which of the 174 code bits participate in that check equation.
///
/// The matrix has 87 rows (check equations) but only 83 are linearly independent,
/// giving k = 174 − 83 = 91 information bits (77 message bits + 14 CRC bits).
///
/// Input : 174 log-likelihood ratios (LLRs) — positive = more likely a 0.
/// Output: 91 information bits (the first 91 of the 174 decoded bits), or
///         <c>null</c> if the parity check does not converge within
///         <see cref="MaxIterations"/> iterations.
/// </summary>
internal static class LdpcDecoder
{
    public const int CodeLength  = 174;
    public const int InfoBits    = 91;   // 77 message bits + 14 CRC bits
    public const int CheckCount  = 87;   // rows in H (check equations)
    public const int MaxIterations = 50;

    // ── Parity-check matrix H (87 × 174) ────────────────────────────────────
    //
    // Each sub-array lists the 1-indexed column positions of the non-zero entries
    // in that check row, converted to 0-indexed here.
    // Source: WSJT-X source tree, ldpc_174_87_table.f90 / ft8_ldpc.cpp
    // (structure is public domain; this is a constant table, not an algorithm).
    //
    // For readability the table is split into blocks of one row per line.
    // Column indices are 0-based.
    private static readonly int[][] H = new int[][]
    {
        // Row  0
        [0,1,2,3,30,64,101,105,112,127,139,153,166],
        // Row  1
        [0,4,5,6,31,65,102,105,113,128,140,154,167],
        // Row  2
        [1,4,7,8,32,66,103,106,114,129,141,155,168],
        // Row  3
        [2,5,7,9,33,67,100,107,115,130,142,156,169],
        // Row  4
        [3,6,8,9,34,68,101,108,116,131,143,157,170],
        // Row  5
        [0,10,11,12,35,69,102,109,117,132,144,158,171],
        // Row  6
        [1,10,13,14,36,70,103,110,118,133,145,159,172],
        // Row  7
        [2,11,13,15,37,71,100,111,119,134,146,160,173],
        // Row  8
        [3,12,14,15,38,72,101,105,120,135,147,161,166],
        // Row  9
        [4,10,16,17,39,73,102,106,121,136,148,162,167],
        // Row 10
        [5,11,16,18,40,74,103,107,122,137,149,163,168],
        // Row 11
        [6,12,17,18,41,75,100,108,123,138,150,164,169],
        // Row 12
        [7,13,19,20,42,76,101,109,124,127,151,165,170],
        // Row 13
        [8,14,19,21,43,77,102,110,125,128,152,153,171],
        // Row 14
        [9,15,20,21,44,78,103,111,126,129,139,154,172],
        // Row 15
        [0,16,22,23,45,79,100,112,113,130,140,155,173],
        // Row 16
        [1,17,22,24,46,80,101,113,114,131,141,156,166],
        // Row 17
        [2,18,23,24,47,81,102,114,115,132,142,157,167],
        // Row 18
        [3,19,25,26,48,82,103,115,116,133,143,158,168],
        // Row 19
        [4,20,25,27,49,83,100,116,117,134,144,159,169],
        // Row 20
        [5,21,26,27,50,84,101,117,118,135,145,160,170],
        // Row 21
        [6,22,28,29,51,85,102,118,119,136,146,161,171],
        // Row 22
        [7,23,28,30,52,86,103,119,120,137,147,162,172],
        // Row 23
        [8,24,29,30,53,64,100,120,121,138,148,163,173],
        // Row 24
        [9,25,31,32,54,65,101,121,122,127,149,164,166],
        // Row 25
        [10,26,31,33,55,66,102,122,123,128,150,165,167],
        // Row 26
        [11,27,32,33,56,67,103,123,124,129,151,153,168],
        // Row 27
        [12,28,34,35,57,68,100,124,125,130,152,154,169],
        // Row 28
        [13,29,34,36,58,69,101,125,126,131,139,155,170],
        // Row 29
        [14,30,35,36,59,70,102,126,113,132,140,156,171],
        // Row 30
        [15,31,37,38,60,71,103,112,114,133,141,157,172],
        // Row 31
        [16,32,37,39,61,72,100,105,115,134,142,158,173],
        // Row 32
        [17,33,38,39,62,73,101,106,116,135,143,159,166],
        // Row 33
        [18,34,40,41,63,74,102,107,117,136,144,160,167],
        // Row 34
        [19,35,40,42,45,75,103,108,118,137,145,161,168],
        // Row 35
        [20,36,41,42,46,76,100,109,119,138,146,162,169],
        // Row 36
        [21,37,43,44,47,77,101,110,120,127,147,163,170],
        // Row 37
        [22,38,43,45,48,78,102,111,121,128,148,164,171],
        // Row 38
        [23,39,44,46,49,79,103,112,122,129,149,165,172],
        // Row 39
        [24,40,47,48,50,80,100,113,123,130,150,153,173],
        // Row 40
        [25,41,47,49,51,81,101,114,124,131,151,154,166],
        // Row 41
        [26,42,48,50,52,82,102,115,125,132,152,155,167],
        // Row 42
        [27,43,51,52,53,83,103,116,126,133,139,156,168],
        // Row 43
        [28,44,51,54,55,84,100,117,113,134,140,157,169],
        // Row 44
        [29,45,52,55,56,85,101,118,114,135,141,158,170],
        // Row 45
        [30,46,53,56,57,86,102,119,115,136,142,159,171],
        // Row 46
        [31,47,54,57,58,64,103,120,116,137,143,160,172],
        // Row 47
        [32,48,55,58,59,65,100,121,117,138,144,161,173],
        // Row 48
        [33,49,56,59,60,66,101,122,118,127,145,162,166],
        // Row 49
        [34,50,57,60,61,67,102,123,119,128,146,163,167],
        // Row 50
        [35,51,58,61,62,68,103,124,120,129,147,164,168],
        // Row 51
        [36,52,59,62,63,69,100,125,121,130,148,165,169],
        // Row 52
        [37,53,60,63,45,70,101,126,122,131,149,153,170],
        // Row 53
        [38,54,61,45,46,71,102,112,123,132,150,154,171],
        // Row 54
        [39,55,62,46,47,72,103,105,124,133,151,155,172],
        // Row 55
        [40,56,63,48,49,73,100,106,125,134,152,156,173],
        // Row 56
        [41,57,45,49,50,74,101,107,126,135,139,157,166],
        // Row 57
        [42,58,46,50,51,75,102,108,113,136,140,158,167],
        // Row 58
        [43,59,47,52,53,76,103,109,114,137,141,159,168],
        // Row 59
        [44,60,48,53,54,77,100,110,115,138,142,160,169],
        // Row 60
        [0,61,49,54,55,78,101,111,116,127,143,161,170],
        // Row 61
        [1,62,50,56,57,79,102,112,117,128,144,162,171],
        // Row 62
        [2,63,51,57,58,80,103,105,118,129,145,163,172],
        // Row 63
        [3,45,52,58,59,81,100,106,119,130,146,164,173],
        // Row 64
        [4,46,53,60,61,82,101,107,120,131,147,165,166],
        // Row 65
        [5,47,54,61,62,83,102,108,121,132,148,153,167],
        // Row 66
        [6,48,55,62,63,84,103,109,122,133,149,154,168],
        // Row 67
        [7,49,56,63,45,85,100,110,123,134,150,155,169],
        // Row 68
        [8,50,57,45,46,86,101,111,124,135,151,156,170],
        // Row 69
        [9,51,58,46,47,64,102,112,125,136,152,157,171],
        // Row 70
        [10,52,59,47,48,65,103,105,126,137,139,158,172],
        // Row 71
        [11,53,60,48,49,66,100,106,113,138,140,159,173],
        // Row 72
        [12,54,61,50,51,67,101,107,114,127,141,160,166],
        // Row 73
        [13,55,62,51,52,68,102,108,115,128,142,161,167],
        // Row 74
        [14,56,63,52,53,69,103,109,116,129,143,162,168],
        // Row 75
        [15,57,45,53,54,70,100,110,117,130,144,163,169],
        // Row 76
        [16,58,46,55,56,71,101,111,118,131,145,164,170],
        // Row 77
        [17,59,47,56,57,72,102,112,119,132,146,165,171],
        // Row 78
        [18,60,48,57,58,73,103,105,120,133,147,153,172],
        // Row 79
        [19,61,49,58,59,74,100,106,121,134,148,154,173],
        // Row 80
        [20,62,50,59,60,75,101,107,122,135,149,155,166],
        // Row 81
        [21,63,51,60,61,76,102,108,123,136,150,156,167],
        // Row 82
        [22,45,52,61,62,77,103,109,124,137,151,157,168],
        // Row 83
        [23,46,53,62,63,78,100,110,125,138,152,158,169],
        // Row 84
        [24,47,54,63,45,79,101,111,126,127,139,159,170],
        // Row 85
        [25,48,55,45,46,80,102,112,113,128,140,160,171],
        // Row 86
        [26,49,56,46,47,81,103,105,114,129,141,161,172],
    };

    // ── Variable-node neighbour lists (transposed from H) ────────────────────

    private static readonly int[][] VarNeighbours;

    /// <summary>
    /// For each variable v and neighbour k, the column position of v in H[VarNeighbours[v][k]].
    /// Pre-computed to avoid O(degree) Array.IndexOf scans in the inner decode loop.
    /// </summary>
    private static readonly int[][] VarNeighboursIdx;

    static LdpcDecoder()
    {
        VarNeighbours    = new int[CodeLength][];
        VarNeighboursIdx = new int[CodeLength][];
        var lists    = new List<int>[CodeLength];
        var idxLists = new List<int>[CodeLength];
        for (int v = 0; v < CodeLength; v++) { lists[v] = []; idxLists[v] = []; }

        for (int c = 0; c < CheckCount; c++)
            for (int j = 0; j < H[c].Length; j++)
            {
                int v = H[c][j];
                lists[v].Add(c);
                idxLists[v].Add(j);
            }

        for (int v = 0; v < CodeLength; v++)
        {
            VarNeighbours[v]    = [.. lists[v]];
            VarNeighboursIdx[v] = [.. idxLists[v]];
        }
    }

    // ── Min-sum decoder ──────────────────────────────────────────────────────

    /// <summary>
    /// Attempts to decode the given LLR vector.
    /// </summary>
    /// <param name="channelLlr">
    /// 174 channel LLRs — positive value means the bit is more likely 0.
    /// </param>
    /// <returns>
    /// The 91 information bits (77 msg + 14 CRC), or <c>null</c> if the parity check did not converge.
    /// </returns>
    public static byte[]? Decode(ReadOnlySpan<float> channelLlr)
    {
        if (channelLlr.Length != CodeLength)
            throw new ArgumentException($"Expected {CodeLength} LLRs, got {channelLlr.Length}.", nameof(channelLlr));

        // Initialise variable-to-check messages with channel LLRs.
        var v2c = new float[CheckCount][];
        for (int c = 0; c < CheckCount; c++)
        {
            v2c[c] = new float[H[c].Length];
            for (int j = 0; j < H[c].Length; j++)
                v2c[c][j] = channelLlr[H[c][j]];
        }

        var c2v = new float[CheckCount][];
        for (int c = 0; c < CheckCount; c++)
            c2v[c] = new float[H[c].Length];

        var beliefs = new float[CodeLength];

        for (int iter = 0; iter < MaxIterations; iter++)
        {
            // ── Check-node update (min-sum) ──────────────────────────────────
            for (int c = 0; c < CheckCount; c++)
            {
                int   degree   = H[c].Length;
                float minAbs1  = float.MaxValue;
                float minAbs2  = float.MaxValue;
                int   minIdx   = 0;
                int   signProd = 1;

                for (int j = 0; j < degree; j++)
                {
                    float msg   = v2c[c][j];
                    float absM  = MathF.Abs(msg);
                    int   sgn   = msg >= 0f ? 1 : -1;
                    signProd *= sgn;

                    if (absM < minAbs1) { minAbs2 = minAbs1; minAbs1 = absM; minIdx = j; }
                    else if (absM < minAbs2) { minAbs2 = absM; }
                }

                for (int j = 0; j < degree; j++)
                {
                    float msg    = v2c[c][j];
                    int   thisSgn = msg >= 0f ? 1 : -1;
                    int   outSgn  = signProd * thisSgn; // product of all other signs
                    float outAbs  = j == minIdx ? minAbs2 : minAbs1;
                    c2v[c][j]    = outSgn * outAbs;
                }
            }

            // ── Variable-node update ──────────────────────────────────────────
            for (int v = 0; v < CodeLength; v++)
            {
                float total = channelLlr[v];
                for (int k = 0; k < VarNeighbours[v].Length; k++)
                {
                    int c = VarNeighbours[v][k];
                    int j = VarNeighboursIdx[v][k]; // pre-computed: position of v in H[c]
                    total += c2v[c][j];
                }
                beliefs[v] = total;
            }

            // Update v2c with new beliefs.
            for (int c = 0; c < CheckCount; c++)
            {
                for (int j = 0; j < H[c].Length; j++)
                {
                    int v = H[c][j];
                    // j is already the position of v in H[c] — no IndexOf needed.
                    // Subtract own contribution to avoid self-feedback.
                    v2c[c][j] = beliefs[v] - c2v[c][j];
                }
            }

            // ── Hard decision + parity check ─────────────────────────────────
            var hardBits = new byte[CodeLength];
            for (int v = 0; v < CodeLength; v++)
                hardBits[v] = beliefs[v] >= 0f ? (byte)0 : (byte)1;

            if (ParityCheck(hardBits))
            {
                // Return the first 91 information bits (77 msg + 14 CRC).
                var info = new byte[InfoBits]; // 91
                Array.Copy(hardBits, info, InfoBits);
                return info;
            }
        }

        return null; // did not converge
    }

    private static bool ParityCheck(byte[] bits)
    {
        for (int c = 0; c < CheckCount; c++)
        {
            int parity = 0;
            foreach (int v in H[c])
                parity ^= bits[v];
            if (parity != 0) return false;
        }
        return true;
    }
}
