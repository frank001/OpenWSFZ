namespace OpenWSFZ.Ft8.Subfeas;

/// <summary>
/// 77-bit standard-message field extraction and the RR73 on-air-sentinel-aware payload
/// comparison, ported for the sub-feas-native-subtraction residual-pass merge/dedup
/// (design.md Decision 1 step 5, tasks.md 2.5).
///
/// <para>
/// PROVENANCE: bit boundaries mirror <c>qa/rr-study/gap-locate/pack77_fields.py</c>'s own
/// mirror of the vendored <c>native/ft8_lib_vendor/ft8/message.c</c> layout (that file's own
/// header cites exact line numbers: call1 = bits [0,29), call2 = bits [29,58),
/// report_or_grid = bits [58,74) split into ir (bit 58) + igrid4 (bits [59,74)), flags/i3 =
/// bits [74,77)). The RR73 asymmetry comparison mirrors
/// <c>qa/rr-study/gap-locate/comparator.py</c>'s <c>payload_match</c> and
/// <c>qa/rr-study/sub-feas/stage2.py</c>'s <c>_same_qso</c>/<c>_is_rr73_std</c> — see this
/// file's own module docstring for why: a REFERENCE payload (from re-encoding OUR OWN logged
/// text) always carries our own re-encoded RR73 sentinel, while a genuinely on-air RR73
/// decode may legitimately carry a different sentinel value. Using a naive bit-exact or
/// single-sentinel comparison silently misses or double-counts genuine on-air RR73 reports
/// — exactly the defect this port exists to avoid repeating.
/// </para>
///
/// <para>
/// Payload extraction (79 tones -&gt; 77-bit payload) is NOT itself mirrored from any Python
/// reference (the offline harness gets payload77 from its own Python encoder's internal
/// state, not by decoding tones back to bits) — it is derived directly from this project's
/// own already-established protocol constants (Costas sync positions, Gray-code tone
/// mapping) and the systematic-LDPC convention this codebase's own
/// <c>ft8_ldpc_decode_llrs</c>/<c>out_a91</c> contract already documents (91 systematic bits
/// = payload77+crc14, first in codeword order). 79 tones deterministically encode the full
/// 174-bit LDPC codeword; the 58 non-Costas (data) symbols carry it 3 bits each, MSB-first,
/// in temporal order — decoding the first 77 of those 174 bits recovers payload77 exactly.
/// </para>
/// </summary>
internal static class SubfeasPayload
{
    /// <summary>Total tone count per FT8 transmission (58 data + 21 Costas sync).</summary>
    public const int ToneCount = 79;

    /// <summary>Standard-layout 77-bit payload field boundaries (message.c, mirrored via pack77_fields.py).</summary>
    public readonly record struct StdFields(int I3, ulong Call1, ulong Call2, bool Ir, int Igrid4);

    // Costas 7x7 array occupies symbol indices [0,7), [36,43), [72,79) -- the remaining
    // 58 indices, in increasing order, are the data symbols (constants.py's
    // COSTAS_START_INDICES/COSTAS_LEN, NUM_DATA_SYMBOLS=58).
    private static readonly (int Start, int Len)[] CostasBlocks = [(0, 7), (36, 7), (72, 7)];

    // GRAY_MAP: tone = GRAY_MAP[3-bit value]. Decoding needs the inverse: value = index of
    // `tone` in GRAY_MAP. constants.py: GRAY_MAP = (0, 1, 3, 2, 5, 6, 4, 7).
    private static readonly int[] GrayMap = [0, 1, 3, 2, 5, 6, 4, 7];
    private static readonly int[] InverseGrayMap = BuildInverseGrayMap();

    private static int[] BuildInverseGrayMap()
    {
        var inv = new int[8];
        for (int value = 0; value < 8; value++) inv[GrayMap[value]] = value;
        return inv;
    }

    private static bool IsCostas(int symbolIndex)
    {
        foreach (var (start, len) in CostasBlocks)
            if (symbolIndex >= start && symbolIndex < start + len) return true;
        return false;
    }

    /// <summary>
    /// Extracts the 77-bit standard payload from 79 tone indices (each in [0,7]).
    /// </summary>
    /// <exception cref="ArgumentException">
    /// Thrown when <paramref name="tones"/> is not exactly 79 elements or contains a value
    /// outside [0,7].
    /// </exception>
    public static bool[] ExtractPayload77(byte[] tones)
    {
        if (tones.Length != ToneCount)
            throw new ArgumentException($"tones must contain exactly {ToneCount} elements; got {tones.Length}.", nameof(tones));

        var codeword = new bool[174];
        int bitPos = 0;
        for (int sym = 0; sym < ToneCount && bitPos < 174; sym++)
        {
            if (IsCostas(sym)) continue;
            byte tone = tones[sym];
            if (tone > 7)
                throw new ArgumentException($"tone index at position {sym} is {tone}, must be in [0,7].", nameof(tones));
            int value = InverseGrayMap[tone]; // 3-bit value, MSB-first below
            codeword[bitPos++] = (value & 0b100) != 0;
            codeword[bitPos++] = (value & 0b010) != 0;
            codeword[bitPos++] = (value & 0b001) != 0;
        }

        var payload77 = new bool[77];
        Array.Copy(codeword, payload77, 77);
        return payload77;
    }

    /// <summary>Splits a 77-bit payload (MSB-first) into its standard-message fields.</summary>
    public static StdFields ExtractStdFields(bool[] payload77)
    {
        if (payload77.Length != 77)
            throw new ArgumentException($"payload77 must be exactly 77 bits; got {payload77.Length}.", nameof(payload77));

        return new StdFields(
            I3: PackBits(payload77, 74, 77),
            Call1: PackBitsUlong(payload77, 0, 29),
            Call2: PackBitsUlong(payload77, 29, 58),
            Ir: payload77[58],
            Igrid4: PackBits(payload77, 59, 74));
    }

    private static int PackBits(bool[] bits, int lo, int hi)
    {
        int v = 0;
        for (int i = lo; i < hi; i++)
        {
            v <<= 1;
            if (bits[i]) v |= 1;
        }
        return v;
    }

    private static ulong PackBitsUlong(bool[] bits, int lo, int hi)
    {
        ulong v = 0;
        for (int i = lo; i < hi; i++)
        {
            v <<= 1;
            if (bits[i]) v |= 1UL;
        }
        return v;
    }

    // message.c: MAXGRID4 = 32400. RR73_STD = (ir=0, igrid4=MAXGRID4+3=32403) -- this
    // codebase's own encoder's RR73 sentinel (comparator.py's RR73_STD).
    private const int MaxGrid4 = 32_400;
    private static readonly (bool Ir, int Igrid4) Rr73Std = (false, MaxGrid4 + 3);

    // The value a genuine ON-AIR RR73 report's igrid4 field carries (GAP-LOCATE finding,
    // corpus.py's RR73_ONAIR_IGRID4 = 32373; board 2026-09-27, "interop rendering VERIFIED").
    private const int Rr73OnAirIgrid4 = 32_373;

    private static bool IsRr73Std(StdFields f) => f.I3 == 1 && f.Ir == Rr73Std.Ir && f.Igrid4 == Rr73Std.Igrid4;

    /// <summary>
    /// True if <paramref name="candidate"/> (from a real LDPC decode of the residual pass)
    /// is the SAME transmission as <paramref name="reference"/> (from re-encoding a pass-0
    /// decode's logged text): exact bit match, or <paramref name="reference"/> is our own
    /// RR73-standard encoding and <paramref name="candidate"/> carries the on-air RR73
    /// sentinel with matching call1/call2 (stage2.py's <c>_same_qso</c>).
    /// </summary>
    public static bool SameQso(bool[] reference, bool[] candidate)
    {
        if (reference.Length != 77 || candidate.Length != 77)
            throw new ArgumentException("both payloads must be exactly 77 bits.");

        if (BitsEqual(reference, candidate)) return true;

        var refFields = ExtractStdFields(reference);
        if (!IsRr73Std(refFields)) return false;

        var candFields = ExtractStdFields(candidate);
        return candFields.I3 == 1
            && candFields.Call1 == refFields.Call1
            && candFields.Call2 == refFields.Call2
            && candFields.Ir == false
            && candFields.Igrid4 == Rr73OnAirIgrid4;
    }

    private static bool BitsEqual(bool[] a, bool[] b)
    {
        for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
        return true;
    }
}
