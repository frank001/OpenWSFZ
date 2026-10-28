#if HAS_INTERNALS
// GAP-RELOCATE item 1 (QA-owned instrument; NO change under src/ or native/).
// This file only compiles when the harness is built with -p:HasInternals=true, which also sets AssemblyName=Ft8.FitProbe:
// OpenWSFZ.Ft8 already declares [InternalsVisibleTo("Ft8.FitProbe")], so the harness may construct Ft8Decoder through its
// internal constructor with a PASS-THROUGH wrapper around the production interop. The wrapper forwards every member
// (including the ones with default interface bodies, which would otherwise silently revert to their defaults) and only
// COUNTS: rows by state per fallback run, distinct NEW_GATED payloads, text unpack calls and non-empty results.
// Counts only; no message text is read here (HK-037).
using System.Globalization;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;

internal sealed class StageProbeInterop : IFt8NativeInterop
{
    private readonly IFt8NativeInterop _i;
    public StageProbeInterop(IFt8NativeInterop inner) { _i = inner; }

    // ── per-cycle counters (the decoder runs one cycle at a time in this harness) ───────────────────────────────
    public static readonly List<string> Runs = new();       // one entry per CohFallbackRun call, in call order
    public static int UnpackCalls, UnpackNonEmpty, UnpackThrew;
    public static StreamWriter? Dump;   // --stage-dump (scratch only): R = NEW_GATED row of run n (payload, out freq, snr), U = unpack (payload -> text)
    private static void D(string line) { var w = Dump; if (w is null) return; lock (w) w.WriteLine(line); }
    public static bool Reset_() { Runs.Clear(); UnpackCalls = UnpackNonEmpty = UnpackThrew = 0; return true; }

    private static CohFallbackRunResult? Record(CohFallbackRunResult? r, float[] pcm)
    {
        if (r is null) { Runs.Add("null"); return r; }
        int newGated = 0, known = 0, gatedOut = 0, abandoned = 0;
        var distinct = new HashSet<string>(StringComparer.Ordinal);
        foreach (var row in r.Rows)
        {
            if (row.State == CohFallbackState.NewGated)
            {
                newGated++; distinct.Add(Convert.ToHexString(row.Payload, 0, 10));
                D(string.Join("	", Program.CurStamp, "R", Runs.Count.ToString(CultureInfo.InvariantCulture), Convert.ToHexString(row.Payload, 0, 10),
                    ((int)Math.Round(row.OutFreqHz)).ToString(CultureInfo.InvariantCulture), row.SnrDb.ToString(CultureInfo.InvariantCulture), row.Edge ? "1" : "0"));
            }
            else if (row.State == CohFallbackState.Known) known++;
            else if (row.State == CohFallbackState.GatedOut) gatedOut++;
            else if (row.State == CohFallbackState.Abandoned) abandoned++;
        }
        Runs.Add(string.Join(":", pcm.Length.ToString(CultureInfo.InvariantCulture), r.Rows.Count, newGated, distinct.Count, known, gatedOut, abandoned));
        return r;
    }

    public static string Line()   // runs;unpackCalls;nonEmpty;threw
        => (Runs.Count == 0 ? "-" : string.Join("|", Runs)) + "," + UnpackCalls + "," + UnpackNonEmpty + "," + UnpackThrew;

    // ── forwarding ─────────────────────────────────────────────────────────────────────────────────────────────────
    public int MaxDecodePasses => _i.MaxDecodePasses;
    public Ft8NativeResult[] DecodeAll(float[] pcm) => _i.DecodeAll(pcm);
    public int[] GetLastPassCounts(int maxPasses) => _i.GetLastPassCounts(maxPasses);
    public int[] GetLastCandidateCounts(int maxPasses) => _i.GetLastCandidateCounts(maxPasses);
    public float GetLastNoiseFloorDb() => _i.GetLastNoiseFloorDb();
    public int GetHashTableRejectCount() => _i.GetHashTableRejectCount();
    public int GetH12DisplayingCount() => _i.GetH12DisplayingCount();
    public int GetH12AmbiguousCount() => _i.GetH12AmbiguousCount();
    public int GetH12DivergentCount() => _i.GetH12DivergentCount();
    public int GetH12SuppressedCount() => _i.GetH12SuppressedCount();
    public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses) => _i.GetLastLlrStats(maxPasses);
    public void SetApBits(byte[] mycallBits, byte[] hiscallBits) => _i.SetApBits(mycallBits, hiscallBits);
    public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) => _i.SetDecodeParams(kMinScorePass2, osdCorrThreshold, osdNhardMax);
    public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(float[] pcm, int coarseFreqHz, float coarseTimeOffsetS)
        => _i.RefineCandidate(pcm, coarseFreqHz, coarseTimeOffsetS);
    public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => _i.CoherentLlrAt(pcm, freqHz, timeOffsetS);
    public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => _i.GetLastSnrTerms(maxDecoded);
    public byte[] EncodeMessage(string message) => _i.EncodeMessage(message);
    public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => _i.SubfeasComputeAnalytic(pcm);
    public (int ReturnCode, float[] Shat) SubfeasFitSignal(float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        => _i.SubfeasFitSignal(xARe, xAIm, tones, decodedDtS, decodedFreqHz, cancelFlag);
    public void SubfeasPoolConfigure(int bound) => _i.SubfeasPoolConfigure(bound);
    public void SubfeasPoolShutdown() => _i.SubfeasPoolShutdown();
    public void SetDiagnosticsEnabled(bool enabled) => _i.SetDiagnosticsEnabled(enabled);
    public int HashStateSize() => _i.HashStateSize();
    public void HashStateSave(byte[] buffer) => _i.HashStateSave(buffer);
    public void HashStateRestore(byte[] buffer) => _i.HashStateRestore(buffer);
    public byte[]? CohFallbackSnapshot() => _i.CohFallbackSnapshot();
    public ICohFallbackBackend? CohFallbackBackend => _i.CohFallbackBackend;
    public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        => Record(_i.CohFallbackRun(pcm, snapshot, budgetMs, workers, ct), pcm);
    public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
        => Record(_i.CohFallbackRun(pcm, snapshot, budgetMs, workers, multiSet, ct), pcm);
    public string? CohFallbackUnpack(byte[] payload)
    {
        UnpackCalls++;
        try
        {
            string? t = _i.CohFallbackUnpack(payload);
            if (!string.IsNullOrWhiteSpace(t)) UnpackNonEmpty++;
            D(string.Join("	", Program.CurStamp, "U", Convert.ToHexString(payload, 0, 10), (t ?? "").TrimEnd()));
            return t;
        }
        catch { UnpackThrew++; throw; }
    }
    public void SetOsdSignFix(int enabled) => _i.SetOsdSignFix(enabled);
    public int GetOsdSignFix() => _i.GetOsdSignFix();
    public (int[] Nhard, float[] CorrNorm, int[] Depth, int[] Batch, int TotalAccepts, int[] RejectNhard, int[] RejectCorr) GetLastOsdDiag(int passCapacity)
        => _i.GetLastOsdDiag(passCapacity);
}
#endif
