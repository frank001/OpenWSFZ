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
    public const int CheckCount  = 83;   // rows in H (83 linearly-independent check equations)
    public const int MaxIterations = 50;

    // ── Parity-check matrix H (83 × 174) ────────────────────────────────────
    //
    // Each sub-array lists the 0-indexed column positions of the non-zero entries
    // in that check row.
    // Source: kgoba/ft8_lib, ft8/constants.c, kFTX_LDPC_Nm (1-indexed), converted
    // to 0-indexed and stripped of zero-padding.  Public-domain constant table.
    //
    // The LDPC(174,91) code has 87 check equations, of which 83 are linearly
    // independent.  Using the 83 independent rows is sufficient for correct
    // parity-check decoding and guarantees the encoder parity sub-system is
    // full-rank (no free variables).
    // internal so TestFt8Encoder (in the test project) can perform LDPC encoding.
    internal static readonly int[][] H = new int[][]
    {
        // Row  0
        [3,30,58,90,91,95,152],
        // Row  1
        [4,31,59,92,114,145],
        // Row  2
        [5,23,60,93,121,150],
        // Row  3
        [6,32,61,94,95,142],
        // Row  4
        [7,24,62,82,92,95,147],
        // Row  5
        [5,31,63,96,125,137],
        // Row  6
        [4,33,64,77,97,106,153],
        // Row  7
        [8,34,65,98,138,145],
        // Row  8
        [9,35,66,99,106,125],
        // Row  9
        [10,36,66,86,100,138,157],
        // Row 10
        [11,37,67,101,104,154],
        // Row 11
        [12,38,68,102,148,161],
        // Row 12
        [7,39,69,81,103,113,144],
        // Row 13
        [13,40,70,87,101,122,155],
        // Row 14
        [14,41,58,105,122,158],
        // Row 15
        [0,32,71,105,106,156],
        // Row 16
        [15,42,72,107,140,159],
        // Row 17
        [16,36,73,80,108,130,153],
        // Row 18
        [10,43,74,109,120,165],
        // Row 19
        [44,54,63,110,129,160,172],
        // Row 20
        [7,45,70,111,118,165],
        // Row 21
        [17,35,75,88,112,113,142],
        // Row 22
        [18,37,76,103,115,162],
        // Row 23
        [19,46,69,91,137,164],
        // Row 24
        [1,47,73,112,127,159],
        // Row 25
        [20,44,77,82,116,120,150],
        // Row 26
        [21,46,57,117,126,163],
        // Row 27
        [15,38,61,111,133,157],
        // Row 28
        [22,42,78,119,130,144],
        // Row 29
        [18,34,58,72,109,124,160],
        // Row 30
        [19,35,62,93,135,160],
        // Row 31
        [13,30,78,97,131,163],
        // Row 32
        [2,43,79,123,126,168],
        // Row 33
        [18,45,80,116,134,166],
        // Row 34
        [6,48,57,89,99,104,167],
        // Row 35
        [11,49,60,117,118,143],
        // Row 36
        [12,50,63,113,117,156],
        // Row 37
        [23,51,75,128,147,148],
        // Row 38
        [24,52,68,89,100,129,155],
        // Row 39
        [19,45,64,79,119,139,169],
        // Row 40
        [20,53,76,99,139,170],
        // Row 41
        [34,81,132,141,170,173],
        // Row 42
        [13,29,82,112,124,169],
        // Row 43
        [3,28,67,119,133,172],
        // Row 44
        [0,3,51,56,85,135,151],
        // Row 45
        [25,50,55,90,121,136,167],
        // Row 46
        [51,83,109,114,144,167],
        // Row 47
        [6,49,80,98,131,172],
        // Row 48
        [22,54,66,94,171,173],
        // Row 49
        [25,40,76,108,140,147],
        // Row 50
        [1,26,40,60,61,114,132],
        // Row 51
        [26,39,55,123,124,125],
        // Row 52
        [17,48,54,123,140,166],
        // Row 53
        [5,32,84,107,115,155],
        // Row 54
        [27,47,69,84,104,128,157],
        // Row 55
        [8,53,62,130,146,154],
        // Row 56
        [21,52,67,108,120,173],
        // Row 57
        [2,12,47,77,94,122],
        // Row 58
        [30,68,132,149,154,168],
        // Row 59
        [11,42,65,88,96,134,158],
        // Row 60
        [4,38,74,101,135,166],
        // Row 61
        [1,53,85,100,134,163],
        // Row 62
        [14,55,86,107,118,170],
        // Row 63
        [9,43,81,90,110,143,148],
        // Row 64
        [22,33,70,93,126,152],
        // Row 65
        [10,48,87,91,141,156],
        // Row 66
        [28,33,86,96,146,161],
        // Row 67
        [29,49,59,85,136,141,161],
        // Row 68
        [9,52,65,83,111,127,164],
        // Row 69
        [21,56,84,92,139,158],
        // Row 70
        [27,31,71,102,131,165],
        // Row 71
        [27,28,83,87,116,142,149],
        // Row 72
        [0,25,44,79,127,146],
        // Row 73
        [16,26,88,102,115,152],
        // Row 74
        [50,56,97,162,164,171],
        // Row 75
        [20,36,72,137,151,168],
        // Row 76
        [15,46,75,129,136,153],
        // Row 77
        [2,23,29,71,103,138],
        // Row 78
        [8,39,89,105,133,150],
        // Row 79
        [14,57,59,73,110,149,162],
        // Row 80
        [17,41,78,143,145,151],
        // Row 81
        [24,37,64,98,121,159],
        // Row 82
        [16,41,74,128,169,171],
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
