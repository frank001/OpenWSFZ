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
    public static StageProbeInterop? Self;
    public StageProbeInterop(IFt8NativeInterop inner) { _i = inner; Self = this; }

    // ── per-cycle counters (the decoder runs one cycle at a time in this harness) ───────────────────────────────
    public static readonly List<string> Runs = new();       // one entry per CohFallbackRun call, in call order
    public static int UnpackCalls, UnpackNonEmpty, UnpackThrew;
    public static bool Gate;                           // --gate-record: also record every GATED_OUT / NEW_GATED row (COH-GATE-G)
    private static readonly List<byte[]> Pending = new();
    public static StreamWriter? Dump;   // --stage-dump (scratch only): R = NEW_GATED row of run n (payload, out freq, snr), U = unpack (payload -> text)
    private static void D(string line) { var w = Dump; if (w is null) return; lock (w) w.WriteLine(line); }
    public static bool Reset_() { lock (Pending) Pending.Clear(); Runs.Clear(); UnpackCalls = UnpackNonEmpty = UnpackThrew = 0; lock (CapLock) { CapCalls.Clear(); CapFShas.Clear(); CapFLens.Clear(); CapSnapshot = null; LsRuns.Clear(); LsArmSnaps.Clear(); } return true; }

    private static CohFallbackRunResult? Record(CohFallbackRunResult? r, float[] pcm)
    {
        if (r is null) { Runs.Add("null"); return r; }
        int newGated = 0, known = 0, gatedOut = 0, abandoned = 0;
        var distinct = new HashSet<string>(StringComparer.Ordinal);
        int rowIx = -1;
        foreach (var row in r.Rows)
        {
            rowIx++;
            if (Gate && (row.State == CohFallbackState.GatedOut || row.State == CohFallbackState.NewGated))
            {
                var p = row.Payload;
                int Bit(int k) => (p[k >> 3] >> (7 - (k & 7))) & 1;
                int i3 = (Bit(74) << 2) | (Bit(75) << 1) | Bit(76), n3 = (Bit(71) << 2) | (Bit(72) << 1) | Bit(73);
                string hex = Convert.ToHexString(p, 0, 10);
                D(string.Join("	", Program.CurStamp, "G", Runs.Count.ToString(CultureInfo.InvariantCulture), row.State == CohFallbackState.NewGated ? "N" : "G",
                    row.F1bDb.ToString("R", CultureInfo.InvariantCulture), row.SnrDb.ToString(CultureInfo.InvariantCulture), row.Edge ? "1" : "0",
                    row.Provenance.ToString(CultureInfo.InvariantCulture), (row.OutFreqHz - row.FreqHz).ToString("R", CultureInfo.InvariantCulture),
                    (row.OutDtS - row.DtS).ToString("R", CultureInfo.InvariantCulture), row.Pass.ToString(CultureInfo.InvariantCulture),
                    row.FreqHz.ToString("R", CultureInfo.InvariantCulture), hex, i3, n3, row.DtS.ToString("R", CultureInfo.InvariantCulture), rowIx.ToString(CultureInfo.InvariantCulture)));
                if (row.State == CohFallbackState.GatedOut) lock (Pending) Pending.Add(p.AsSpan(0, 10).ToArray());
            }
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

    /// <summary>COH-GATE-G: after the cycle, unpack the GATED_OUT payloads to text. The unpack may add callsigns to the session hash table, so the
    /// table is saved before and restored after: later cycles see exactly the state the product would have had. Nothing decodes at this moment
    /// (the staged decode has returned).</summary>
    public static void FlushExtras()
    {
        var self = Self; if (self is null || !Gate) return;
        List<byte[]> todo; lock (Pending) { todo = Pending.ToList(); Pending.Clear(); }
        if (todo.Count == 0) return;
        int size = self._i.HashStateSize();
        var buf = new byte[size];
        self._i.HashStateSave(buf);
        try
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var pl in todo)
            {
                string hex = Convert.ToHexString(pl, 0, 10);
                if (!seen.Add(hex)) continue;
                string t;
                try { t = (self._i.CohFallbackUnpack(pl) ?? "").TrimEnd(); } catch { t = ""; }
                D(string.Join("	", Program.CurStamp, "X", hex, Ft8Decoder.IsPlausibleMessage(t, null) ? "1" : "0", t));
            }
        }
        finally { self._i.HashStateRestore(buf); }
    }

    // ── GAP-RESIDUAL capture (QA-owned; qa/ only; NO change under src/ or native/) ──────────────────────────────────────
    // Pass-through: every captured value is a COPY made before/after the inner call; the inner call's result is returned unchanged (ROW 0b checks this).
    // Per cycle: the DecodeAll calls in order (index 0 = O the normalised original, 1 = R2 the residual pass, 2 = R3 the third pass), each with a copy of its PCM,
    // the native results it returned and the hash state saved just BEFORE the call; and the CohFallbackRun calls (PCM SHA-256 + the snapshot bytes).
    // Message text lives only in the --cap-dir files under _qa-scratch (HK-037); the index file holds hashes and counts.
    public static string? CapDir;
    private static readonly object CapLock = new();
    internal sealed class CapCall { public float[] Pcm = Array.Empty<float>(); public Ft8NativeResult[] Res = Array.Empty<Ft8NativeResult>(); public byte[] Hash = Array.Empty<byte>(); public byte[]? Snap; }
    internal static readonly List<CapCall> CapCalls = new();
    // LATE-SUB: LsOn captures what the arm work needs even without --cap-dir (per-call PCM copy, natives, hash state before the call, and the snapshot taken on the DecodeAll thread right after it);
    // LsMode 1 = arm work in progress: DecodeAll only records the snapshot of the decode it ran (LsArmSnaps) and does not touch CapCalls.
    public static bool LsOn; public static int LsMode;
    internal static readonly List<byte[]?> LsArmSnaps = new();
    internal sealed class LsRun { public float[] Pcm = Array.Empty<float>(); public CohFallbackRunResult? Result; public byte[] Hash = Array.Empty<byte>(); }
    internal static readonly List<LsRun> LsRuns = new();
    internal IFt8NativeInterop Inner => _i;
    private static readonly List<string> CapFShas = new();
    private static readonly List<int> CapFLens = new();
    private static byte[]? CapSnapshot;

    private static string Sha(float[] pcm) => Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Runtime.InteropServices.MemoryMarshal.AsBytes(pcm.AsSpan())));

    private void CapFallback(float[] pcm, byte[] snapshot)
    {
        if (CapDir is null) return;
        lock (CapLock) { CapFShas.Add(Sha(pcm)); CapFLens.Add(pcm.Length); CapSnapshot ??= (byte[])snapshot.Clone(); }
    }

    /// <summary>End of cycle: write the buffers, natives, hash states, the eligible-candidate plan of the snapshot and ONE index line (hashes and counts only).</summary>
    public static void CapFlush(string stamp)
    {
        var dir = CapDir; if (dir is null) return;
        lock (CapLock)
        {
            Directory.CreateDirectory(Path.Combine(dir, "buffers")); Directory.CreateDirectory(Path.Combine(dir, "native"));
            Directory.CreateDirectory(Path.Combine(dir, "hash")); Directory.CreateDirectory(Path.Combine(dir, "plan"));
            string[] kinds = { "O", "R2", "R3" };
            var shas = new List<string>(); var lens = new List<int>(); var nres = new List<int>();
            using (var nw = new StreamWriter(Path.Combine(dir, "native", stamp + ".tsv"), false, new System.Text.UTF8Encoding(false)))
            {
                for (int k = 0; k < CapCalls.Count; k++)
                {
                    var c = CapCalls[k]; string kind = k < kinds.Length ? kinds[k] : "X" + k;
                    File.WriteAllBytes(Path.Combine(dir, "buffers", stamp + "_" + kind + ".f32"), System.Runtime.InteropServices.MemoryMarshal.AsBytes(c.Pcm.AsSpan()).ToArray());
                    File.WriteAllBytes(Path.Combine(dir, "hash", stamp + "_" + kind + ".bin"), c.Hash);
                    shas.Add(Sha(c.Pcm)); lens.Add(c.Pcm.Length); nres.Add(c.Res.Length);
                    foreach (var r in c.Res)
                        nw.WriteLine(string.Join("\t", kind, r.FreqHz.ToString(CultureInfo.InvariantCulture), r.Dt.ToString("R", CultureInfo.InvariantCulture),
                            r.Snr.ToString(CultureInfo.InvariantCulture), (r.Message ?? "").TrimEnd()));
                }
            }
            string plan = "none";
            if (CapSnapshot is not null)
            {
                try
                {
                    var p = Ft8LibInterop.CohFallbackMakePlan(CapSnapshot);
                    using var pw = new StreamWriter(Path.Combine(dir, "plan", stamp + ".tsv"), false, new System.Text.UTF8Encoding(false));
                    foreach (var row in p.Rows)
                        pw.WriteLine(row.FreqHz.ToString("R", CultureInfo.InvariantCulture) + "\t" + row.DtS.ToString("R", CultureInfo.InvariantCulture));
                    plan = p.Rows.Count.ToString(CultureInfo.InvariantCulture);
                }
                catch (Exception ex) { plan = "ERR:" + ex.GetType().Name; }
            }
            string F(int i) => i < shas.Count ? shas[i] : "-";
            string level = CapFShas.Count == 0 ? "none"
                : (shas.Count > 2 && CapFShas[0] == shas[2]) ? "R3" : (shas.Count > 1 && CapFShas[0] == shas[1]) ? "R2" : (shas.Count > 0 && CapFShas[0] == shas[0]) ? "O" : "other";
            string second = CapFShas.Count < 2 ? "-" : (shas.Count > 0 && CapFShas[1] == shas[0]) ? "O" : "other";
            using (var iw = new StreamWriter(Path.Combine(dir, "capture_index.tsv"), true, new System.Text.UTF8Encoding(false)))
                iw.WriteLine(string.Join("\t", stamp, CapCalls.Count, string.Join("|", lens), string.Join("|", nres), F(0), F(1), F(2),
                    CapFShas.Count, string.Join("|", CapFLens), level, second, plan));
            CapCalls.Clear(); CapFShas.Clear(); CapFLens.Clear(); CapSnapshot = null;
        }
    }

    /// <summary>ROW 0c(iii) (separate process, after the arm): restore the hash state saved before each captured DecodeAll, decode the captured buffer again, compare
    /// freq / dt / SNR / count / text with what that call returned. Text is compared INSIDE this function only (the hash state is restored, so it is deterministic); the
    /// output holds counts and ok flags. Exact; one line per cycle.</summary>
    public static int Recheck(string dir, IFt8NativeInterop inner, int kMinScorePass2, float osdCorr, int nhard)
    {
        inner.SetDecodeParams(kMinScorePass2, osdCorr, nhard);
        inner.SetOsdSignFix(1);
        int bad = 0, cycles = 0;
        using var ow = new StreamWriter(Path.Combine(dir, "recheck.tsv"), false, new System.Text.UTF8Encoding(false));
        ow.WriteLine("stamp\tkind\texpected_n\tgot_n\tok");
        foreach (var f in Directory.GetFiles(Path.Combine(dir, "native"), "*.tsv").OrderBy(x => x, StringComparer.Ordinal))
        {
            string stamp = Path.GetFileNameWithoutExtension(f);
            var exp = File.ReadAllLines(f).Where(l => l.Length > 0).Select(l => l.Split('\t')).GroupBy(p => p[0]).ToDictionary(g => g.Key, g => g.ToList());
            foreach (var kind in new[] { "O", "R2", "R3" })
            {
                string bp = Path.Combine(dir, "buffers", stamp + "_" + kind + ".f32");
                if (!File.Exists(bp)) continue;
                var raw = File.ReadAllBytes(bp); var pcm = new float[raw.Length / 4]; Buffer.BlockCopy(raw, 0, pcm, 0, raw.Length);
                inner.HashStateRestore(File.ReadAllBytes(Path.Combine(dir, "hash", stamp + "_" + kind + ".bin")));
                inner.SetApBits(Array.Empty<byte>(), Array.Empty<byte>());
                inner.SetDiagnosticsEnabled(kind == "O");
                var got = inner.DecodeAll(pcm);
                inner.SetDiagnosticsEnabled(true);
                var e = exp.TryGetValue(kind, out var l) ? l : new List<string[]>();
                bool ok = e.Count == got.Length;
                for (int i = 0; ok && i < got.Length; i++)
                    ok = e[i][1] == got[i].FreqHz.ToString(CultureInfo.InvariantCulture) && e[i][2] == got[i].Dt.ToString("R", CultureInfo.InvariantCulture)
                        && e[i][3] == got[i].Snr.ToString(CultureInfo.InvariantCulture) && e[i][4] == (got[i].Message ?? "").TrimEnd();
                if (!ok) bad++;
                ow.WriteLine(string.Join("\t", stamp, kind, e.Count, got.Length, ok ? 1 : 0));
            }
            cycles++;
        }
        Console.WriteLine("recheck cycles=" + cycles + " mismatching_calls=" + bad);
        return bad == 0 ? 0 : 1;
    }

    // ── forwarding ─────────────────────────────────────────────────────────────────────────────────────────────────
    public int MaxDecodePasses => _i.MaxDecodePasses;
    public Ft8NativeResult[] DecodeAll(float[] pcm)
    {
        if (LsMode == 1)
        {
            var r0 = _i.DecodeAll(pcm);
            var sn = _i.CohFallbackSnapshot();                  // same thread, no native decode between
            lock (CapLock) LsArmSnaps.Add(sn == null ? null : (byte[])sn.Clone());
            return r0;
        }
        if (CapDir is null && !LsOn) return _i.DecodeAll(pcm);
        var copy = (float[])pcm.Clone();
        var hs = new byte[_i.HashStateSize()];
        _i.HashStateSave(hs);                                   // the hash state at the capture point: just before this call
        var res = _i.DecodeAll(pcm);
        byte[]? snap = null;
        if (LsOn) { var sn = _i.CohFallbackSnapshot(); snap = sn == null ? null : (byte[])sn.Clone(); }   // LATE-SUB: snap(B), on the DecodeAll thread
        lock (CapLock) CapCalls.Add(new CapCall { Pcm = copy, Res = (Ft8NativeResult[])res.Clone(), Hash = hs, Snap = snap });
        return res;
    }
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
    { CapFallback(pcm, snapshot); return LsRecord(pcm, () => Record(_i.CohFallbackRun(pcm, snapshot, budgetMs, workers, ct), pcm)); }
    public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
    { CapFallback(pcm, snapshot); return LsRecord(pcm, () => Record(_i.CohFallbackRun(pcm, snapshot, budgetMs, workers, multiSet, ct), pcm)); }
    private CohFallbackRunResult? LsRecord(float[] pcm, Func<CohFallbackRunResult?> run)
    {
        if (!LsOn) return run();
        var hs = new byte[_i.HashStateSize()]; _i.HashStateSave(hs);          // state before the run == state at the later unpack (runs do not touch the table)
        var r = run();
        lock (CapLock) LsRuns.Add(new LsRun { Pcm = pcm, Result = r, Hash = hs });
        return r;
    }
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
