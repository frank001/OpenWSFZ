// SUB-FEAS §8.1 real-band runtime replay harness (QA-owned, no src/ change).
//
// Replays captured endurance cycles through the SAME public decode entry the daemon uses
// (Ft8Decoder.DecodeAsync, so the deadline logic in Ft8Decoder/SubtractionPass is included), one
// cycle at a time, serially, and records wall-clock per decode call.
//
// 🔒 HK-037 / NFR-021: decoded message text exists in memory (it is real third-party traffic) but is
// never written anywhere. Only counts and timings are recorded. The logger writes ONLY:
//   - rendered lines whose template is on a fixed allow-list of aggregate-only templates, and
//   - for Warning/Error lines, the ORIGINAL TEMPLATE (never the rendered text) and the exception TYPE.
// Debug/Trace and any other Information line are dropped (counted only).
//
// Modes:
//   --stratum pilot|M|H   decode each selected cycle; --mode off  => flag not touched (R0 builds have no flag)
//                                                      --mode alt  => OFF and ON, order alternated by cycle index parity
//   --stratum R6          synthetic stress: sum each selected pair, assert peak, decode ON only
//   offline flag-OFF/ON replay (spec 2026-10-01-1935): --mode two0 = flag OFF, DecodeTwoStageAsync, ONE call per cycle,
//                         the SAME call and the SAME Test B scoring as --mode two1 (flag ON); the two arms differ only in
//                         the flag. --wav-dir overrides the per-run WAV directory (the on-air night's cycle-audio).
//                         Both modes log a "# readback" line (flag, thread count, nhard, decode params) at start and end.
// Resume: rows already present in --out (stamp|flag) are skipped, so a crashed process can be restarted.

using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;

internal static class Program
{
    private const int PcmSamples = 180_000;
    private const int SampleRateHz = 12_000;
    // KMIN-OSD-RECAL (spec A1.1): the two pass-1 settings are per-process values. Defaults = the previous constants (10 and 0.10), so every earlier arm reproduces;
    // --kmin <int 5..30> and --osd-corr <float 0..1> set them, and the "# readback" lines print what SetDecodeParams was given.
    private const int DefaultKMinScorePass2 = 10;
    private const float DefaultOsdCorrThreshold = 0.10f;
    private static int KMinScorePass2 = DefaultKMinScorePass2;
    private static float OsdCorrThreshold = DefaultOsdCorrThreshold;
    // NHARD-REP (spec 2026-10-06-1430, section 3): the OSD nhard cap is a REQUIRED --nhard argument, 40 or 60 only, and the
    // "# readback" lines log the value the decoder object was actually given. (Was a hard-coded const 40.)
    private static int OsdNhardMax;
#if HAS_OSDSIGNFIX
    private static int OsdSignFix;
    private static int ParseSignFix(string v) =>
        int.TryParse(v, NumberStyles.Integer, CultureInfo.InvariantCulture, out int n) && (n == 0 || n == 1) ? n : throw new ArgumentException("--osd-sign-fix must be 0 or 1");
#endif
    // NHARD-REP Amendment 3 (OSD-OFF): 0 is admitted as the third setting. At nhard 0 the OSD gate rejects every codeword, so OSD is effectively off. The managed
    // SetDecodeParams path passes the value through with no range check (only the config layer enforces 30-100, and this harness bypasses it).
    // OSD-FIX (ruling 2026-10-08-1545, A4): the whitelist is gone so the calibration grid {0, 24, 30, 40, 50, 60} (and any later extension) needs no harness change;
    // --nhard accepts any integer in [0, 174] (174 = the codeword length, the largest meaningful Hamming distance). The value is read back at the start and end of every arm.
    private const int NhardMin = 0;
    private const int NhardMax = 174;
    private const float R6PeakCeiling = 0.99f;

    private static int Main(string[] args)
    {
        try { return RunAsync(args).GetAwaiter().GetResult(); }
        catch (Exception ex)
        {
            Console.Error.WriteLine("FATAL " + ex.GetType().Name);   // type only, never text
            if (Environment.GetEnvironmentVariable("QA_FATAL_DETAIL") == "1") Console.Error.WriteLine("DETAIL (startup debugging only, never in a run that reads text): " + ex.Message.Split((char)10)[0] + " @ " + (ex.StackTrace ?? "").Split((char)10).FirstOrDefault());
            return 3;
        }
    }

    private static async Task<int> RunAsync(string[] args)
    {
        var a = ParseArgs(args);
#if HAS_THIRDPASS
        if (a.ContainsKey("selftest-batch3")) return SelfTestBatch3();
#if HAS_XCPRIOR
        if (a.ContainsKey("xc-verify")) return XcVerify(a["xc-verify"], a["xc-verify-out"]);
#endif
#endif
#if HAS_INTERNALS
        // GAP-RESIDUAL ROW 0c(iii): separate process, after the arm. --cap-recheck <capdir> [--k-min-score-pass2 10] [--osd-corr 0.10] [--nhard 24]
        if (a.TryGetValue("cap-recheck", out var rcDir))
        {
            if (!rcDir.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--cap-recheck must be under _qa-scratch (HK-037)");
            return StageProbeInterop.Recheck(rcDir, new OpenWSFZ.Ft8.Interop.Ft8NativeInteropAdapter(), 10, 0.10f, 24);
        }
        if (a.TryGetValue("late-sub-dir", out var lsDir))
        {
            if (!lsDir.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--late-sub-dir must be under _qa-scratch (HK-037)");
            Directory.CreateDirectory(lsDir);
            LateSub.Dir = lsDir;
            string lsModeArg = a.TryGetValue("late-sub-mode", out var lsModeV) ? lsModeV : "full";
            if (lsModeArg != "full" && lsModeArg != "l1p") throw new ArgumentException("--late-sub-mode must be full or l1p");
            LateSub.L1pOnly = lsModeArg == "l1p";
            StageProbeInterop.LsOn = true;
            LateSub.Workers = a.TryGetValue("threads", out var lsThr) && int.TryParse(lsThr, out var lsThn) ? lsThn : 8;
        }
        if (a.TryGetValue("cap-dir", out var capDir))
        {
            if (!capDir.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--cap-dir must be under _qa-scratch (HK-037)");
            Directory.CreateDirectory(capDir);
            StageProbeInterop.CapDir = capDir;
        }
#endif
        string selectionPath = Req(a, "selection"), run = Req(a, "run"), stratum = Req(a, "stratum");
        string wavRoot = Req(a, "wav-root"), outCsv = Req(a, "out"), logPath = Req(a, "log");
        OsdNhardMax = ParseNhard(Req(a, "nhard"));
        if (a.TryGetValue("kmin", out var kminArg))
            KMinScorePass2 = int.TryParse(kminArg, NumberStyles.Integer, CultureInfo.InvariantCulture, out int kmin) && kmin >= 5 && kmin <= 30 ? kmin : throw new ArgumentException("--kmin must be an integer in [5, 30]");
        if (a.TryGetValue("osd-corr", out var osdArg))
            OsdCorrThreshold = float.TryParse(osdArg, NumberStyles.Float, CultureInfo.InvariantCulture, out float osd) && osd >= 0f && osd <= 1f ? osd : throw new ArgumentException("--osd-corr must be a number in [0, 1]");
        string mode = a.TryGetValue("mode", out var m) ? m : "off";
        string label = a.TryGetValue("label", out var l) ? l : "unlabelled";

        using var selDoc = JsonDocument.Parse(File.ReadAllBytes(selectionPath));
        var root = selDoc.RootElement;
        string WavDirFor(string r) => a.TryGetValue("wav-dir", out var wd)
            ? wd
            : Path.Combine(wavRoot, $"{r}_endurance_run-gathered", "owsfz", "wav");

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outCsv))!);
        using var log = new ReplayLog(logPath);
        var logger = new ReplayLogger<Ft8Decoder>(log);
#if HAS_INTERNALS
        // GAP-RELOCATE item 1: pass-through counting wrapper (StageProbe.cs); built only with -p:HasInternals=true.
        // --clock system|frozen (optional; default system = the production clock, so every older arm is unchanged). "frozen" gives the decoder's BudgetClock a TimeProvider that never advances: the
        // 13 s cycle budget (late round, fallback, template stage) never expires, so a host slower than the station cannot abandon work the station would finish. QA harness only, no src/ change.
        ClockMode = a.TryGetValue("clock", out var clockArg) ? clockArg : "system";
        if (ClockMode != "system" && ClockMode != "frozen") throw new ArgumentException("--clock must be system or frozen");
        var decoder = new Ft8Decoder(new WallClock(), logger, new StageProbeInterop(new OpenWSFZ.Ft8.Interop.Ft8NativeInteropAdapter()),
                                     timeProvider: ClockMode == "frozen" ? new FrozenTimeProvider() : null);
#else
        if (a.TryGetValue("clock", out var clockArgNoInt) && clockArgNoInt != "system") throw new ArgumentException("--clock frozen needs a build with -p:HasInternals=true");
        var decoder = new Ft8Decoder(new WallClock(), logger);
#endif
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, OsdNhardMax);
#if HAS_OSDSIGNFIX
        // OSD-FIX (ruling 2026-10-08-1545, A4): the sign switch is REQUIRED so an arm never inherits the library default by accident; read back at start and end (Readback).
        OsdSignFix = ParseSignFix(Req(a, "osd-sign-fix"));
        decoder.SetOsdSignFix(OsdSignFix);
#endif
        // sub-feas-speed-redesign: the ONLY change to this harness for the speed acceptance is the new config key
        // decoder.subtractionMaxThreads (0 = auto). Absent --threads leaves the decoder at its default (auto).
        // Only the candidate build has the setter (-p:HasMaxThreads=true); the base build cannot be asked for it.
        string threadsNote = "default";
        if (a.TryGetValue("threads", out var thr))
        {
#if HAS_MAXTHREADS
            decoder.SetSubtractionMaxThreads(int.Parse(thr, CultureInfo.InvariantCulture));
            threadsNote = thr;
#else
            throw new InvalidOperationException("this build has no subtractionMaxThreads setter");
#endif
        }
        log.Raw($"# harness label={label} run={run} stratum={stratum} mode={mode} threads={threadsNote} shim={Ft8Decoder.LoadedShimVersion}");

        var done = LoadDone(outCsv);
        bool newFile = !File.Exists(outCsv);
        await using var csv = new StreamWriter(outCsv, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        // sub-feas-speed-redesign two-stage acceptance: modes "two"/"two1" write an 11-column CSV (tb1_ms = time to
        // batch 1, b1_n, b2_n); every row in such a file is written 11 columns wide.
        _wide = mode is "two" or "two1" or "two0";
        // third-pass-deep (#240): modes three0 (decoding depth Normal) / three1 (Deep) write a 12-column CSV with b3_n added.
        _wide3 = mode is "three0" or "three1";
#if !HAS_THIRDPASS
        if (_wide3) throw new InvalidOperationException("this build has no decoding-depth setter (build with -p:HasThirdPass=true)");
#endif
        if (newFile)
            csv.WriteLine(_wide3 ? "run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n,b3_n"
#if HAS_COHFB
                                   + ",tb2_ms,tb3_ms"
#endif
#if HAS_COHFB4
                                   + ",b4_n,tb4_ms"
#endif
#if HAS_LATEROUND
                                   + ",b5_n,tb5_ms"   // L1' build (spec 1322 section 7 F5): batch 5, the late subtraction round; absent in builds without it, so older output is byte-identical
#endif
#if HAS_XCPRIOR
                                   + ",b6_n,tb6_ms"   // XC-BUILD: batch 6, the cross-cycle template stage; absent in builds without it, so older output is byte-identical
#endif
                          : _wide ? "run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n"
                                  : "run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception");
        // Optional outcome keys (S1): per decode only NUMERIC fields plus an 8-hex-digit hash of the message text; the
        // text itself never leaves the function that reads it (HK-037 / NFR-021). Written to a gitignored artefact.
        // HK-037 clarification (Architect, 2026-09-30): a text-DERIVED hash counts as message identity. So the per-decode
        // text hash is OFF by default and only written when the explicit flag --outcome-text-hash true is given, which no
        // standard run sets. Default outcome lines are numeric only: stamp,kind,idx,freqHz,dt,snr.
        _outcomeTextHash = a.TryGetValue("outcome-text-hash", out var oth) && oth == "true";
        if (a.TryGetValue("fb-dump", out var fbd) && !fbd.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--fb-dump must be under _qa-scratch (HK-037)");
        if (a.TryGetValue("fb-dump", out var fbd2)) _fbDump = new StreamWriter(fbd2, false, new UTF8Encoding(false)) { AutoFlush = true };
        // COH-FALLBACK step 4 (U'): working file of EVERY scored decode (all batches, all paths) with its Test-B match flag and text, for the tone-presence instrument. Scratch only (HK-037 amendment 2026-10-10).
        if (a.TryGetValue("nc-dump", out var ncd) && !ncd.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--nc-dump must be under _qa-scratch (HK-037)");
        if (a.TryGetValue("nc-dump", out var ncd2)) _ncDump = new StreamWriter(ncd2, false, new UTF8Encoding(false)) { AutoFlush = true };
        // GAP-RELOCATE: --impl-dump <path> (scratch only; Debug 'filtered implausible message' events WITH text + batch markers) and --stage-out <path> (counts only).
        if (a.TryGetValue("impl-dump", out var imd) && !imd.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--impl-dump must be under _qa-scratch (HK-037)");
        if (a.TryGetValue("impl-dump", out var imd2)) _implDump = new StreamWriter(imd2, false, new UTF8Encoding(false)) { AutoFlush = true };
        if (a.TryGetValue("stage-out", out var sto))
        {
#if HAS_INTERNALS
            _stageOut = new StreamWriter(sto, false, new UTF8Encoding(false)) { AutoFlush = true };
            if (a.ContainsKey("gate-record")) StageProbeInterop.Gate = true;
            if (a.TryGetValue("stage-dump", out var sdp))
            {
                if (!sdp.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--stage-dump must be under _qa-scratch (HK-037)");
                StageProbeInterop.Dump = new StreamWriter(sdp, false, new UTF8Encoding(false)) { AutoFlush = true };
            }
            _stageOut.WriteLine("stamp,runs(pcmLen:rows:newGatedRows:distinctNewGated:known:gatedOut:abandoned|...),unpackCalls,unpackNonEmpty,unpackThrew");
#else
            throw new ArgumentException("--stage-out needs a build with -p:HasInternals=true");
#endif
        }
        // Test B (WSJT-X corroboration, Architect's HK-037 ruling): the match is done INSIDE this process, where the decoded
        // text lives in memory, against WSJT-X's ALL.TXT read here; only COUNTS and stamps are written. Needs mode two1.
        if (a.TryGetValue("wsjtx-alltxt", out var wsPath))
        {
            LoadWsjtx(wsPath);
            var tb = Req(a, "testb-out");
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(tb))!);
            bool fresh = !File.Exists(tb);
            _testB = new StreamWriter(tb, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (fresh) _testB.WriteLine("run,stamp,kind,band,n,corroborated");
        }
        // NHARD-REP Amendment 2 (V2'): --probe-vectors <json> --probe-out <csv> probe the native OSD gate in THIS process.
        if (a.TryGetValue("probe-vectors", out var probeJson))
            LoadProbe(probeJson, Req(a, "probe-out"));
        // COH-GAIN Amendment 3 (V4'): for every WSJT-X line the replay matched, WHICH batch matched it (1 = pass-0, 2 = the residual pass). Numeric only.
        if (a.TryGetValue("matched-batch-out", out var matchedBatchPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(matchedBatchPath))!);
            bool freshMb = !File.Exists(matchedBatchPath);
            _matchedBatch = new StreamWriter(matchedBatchPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (freshMb) _matchedBatch.WriteLine("stamp,wsjtx_idx_batch");
        }
        // NHARD-REP: numeric indices (into the cycle's WSJT-X lines, in ALL.TXT order) of the WSJT-X decodes this arm matched.
        // An index is not message text and not text-derived (HK-037); it lets K and G be computed across two processes.
        if (a.TryGetValue("matched-out", out var matchedPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(matchedPath))!);
            bool freshM = !File.Exists(matchedPath);
            _matched = new StreamWriter(matchedPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (freshM) _matched.WriteLine("stamp,wsjtx_idx");
        }
        if (a.TryGetValue("abandon-out", out var abandonPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(abandonPath))!);
            bool freshAb = !File.Exists(abandonPath);
            _abandon = new StreamWriter(abandonPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (freshAb) _abandon.WriteLine("stamp,ran,abandoned,contained");
        }
        // third-pass-deep (#240): per-cycle third-pass outcome (numeric + a fixed category word): stamp,outcome,newDecodes,elapsedMs,fittedSignals.
        if (a.TryGetValue("third-out", out var thirdPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(thirdPath))!);
            bool freshTh = !File.Exists(thirdPath);
            _third = new StreamWriter(thirdPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (freshTh) _third.WriteLine("stamp,outcome,newDecodes,elapsedMs,fittedSignals");
        }
#if HAS_LATEROUND
        // B-TOOL-2: --late-out: one row per cycle with every field of the round's R6 log line (aggregates only).
        if (a.TryGetValue("late-out", out var latePath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(latePath))!);
            bool freshLate = !File.Exists(latePath);
            _lateOut = new StreamWriter(latePath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (freshLate) _lateOut.WriteLine("stamp,outcome,lines,buffer,fit,refused,new,published,fbEndMs,startMs,elapsedMs,endMs,batch,batch5PublishMs,unmatched");
        }
#endif
        if (a.TryGetValue("outcomes", out var outcomesPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outcomesPath))!);
            _outcomes = new StreamWriter(outcomesPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        }
        // #225 phase 2 (QA, 2026-10-19): optional working file with the TEXT of every type-0.1 DXpedition decode (5 tokens, token 1 "RR73;").
        // HK-037 as amended 2026-10-10: a per-message working file is allowed ONLY in D:\Projects\claude\_qa-scratch\<job>\ (outside git),
        // read by code only and deleted at job close; the analysis that reads it publishes aggregates only. Off unless --dxped-dump is given.
        if (a.TryGetValue("dxped-dump", out var dxpedPath))
        {
            if (!Path.GetFullPath(dxpedPath).StartsWith(@"D:\Projects\claude\_qa-scratch\", StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("--dxped-dump must be inside the _qa-scratch folder (HK-037)");
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(dxpedPath))!);
            _dxped = new StreamWriter(dxpedPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        }

        // ---- warm-up: one discarded cycle per process start, through the full path ----
        string warm = root.GetProperty("runs").GetProperty(run).GetProperty("warmup").GetString()!;
        var warmPcm = ReadWav(Path.Combine(WavDirFor(run), warm + ".wav"));
        SetFlag(decoder, mode is "alt" or "two" or "on" or "two1" or "three0" or "three1");
        await decoder.DecodeAsync(warmPcm, StampToUtc(warm));
        log.Raw("# warm-up cycle decoded and discarded");
        // V2' first probe point: after SetDecodeParams and the warm-up. A miss stops THIS arm before any cycle is decoded (exit 5).
        if (_probe is not null && !RunProbe("start", log))
        {
            log.Raw("# V2-prime FAIL at the start probe: the native OSD gate does not hold the value this arm was given");
            return 5;
        }

        if (stratum == "R6")
        {
            SetFlag(decoder, true);
            int seq = 0;
            foreach (var pair in root.GetProperty("R6_pairs").EnumerateArray())
            {
                string sa = pair.GetProperty("a").GetString()!, sb = pair.GetProperty("b").GetString()!;
                string ra = pair.GetProperty("a_run").GetString()!, rb = pair.GetProperty("b_run").GetString()!;
                string id = sa + "+" + sb;
                if (done.Contains(id + "|ON")) { seq++; continue; }
                var pa = ReadWav(Path.Combine(WavDirFor(ra), sa + ".wav"));
                var pb = ReadWav(Path.Combine(WavDirFor(rb), sb + ".wav"));
                var sum = new float[PcmSamples];
                float peak = 0f;
                for (int i = 0; i < PcmSamples; i++) { sum[i] = pa[i] + pb[i]; peak = MathF.Max(peak, MathF.Abs(sum[i])); }
                if (peak > R6PeakCeiling)
                {
                    float scale = R6PeakCeiling / peak;
                    for (int i = 0; i < PcmSamples; i++) sum[i] *= scale;
                }
                float peakAfter = 0f;
                for (int i = 0; i < PcmSamples; i++) peakAfter = MathF.Max(peakAfter, MathF.Abs(sum[i]));
                if (peakAfter > R6PeakCeiling + 1e-6f) throw new InvalidOperationException("R6 peak assertion failed");
                await Decode1(decoder, sum, StampToUtc(sa), csv, run: "R6", stratum: "R6", id, seq++, "ON");
            }
            return 0;
        }

        var cycles = root.GetProperty("runs").GetProperty(run).GetProperty(stratum).EnumerateArray()
                         .Select(e => e.GetString()!).ToList();
#if HAS_TWOSTAGE
        // Offline flag-OFF/ON replay: the arm's flag is set ONCE here and read back from the decoder object (spec V2).
        if (mode is "two0" or "two1") { SetFlag(decoder, mode == "two1"); Readback(decoder, log, "start", threadsNote); }
#endif
#if HAS_THIRDPASS
        // third-pass-deep: subtraction ON and the depth set ONCE here, read back from the decoder object (spec V0).
        if (mode is "three0" or "three1")
        {
            SetFlag(decoder, true);
            decoder.SetDecodingDepth(mode == "three1" ? DecodingDepth.Deep : DecodingDepth.Normal);
#if HAS_COHFB
            // COH-FALLBACK Stage 2 (spec section 8): the flag is REQUIRED (--cohfb 0|1), set ONCE per process and read back at start and end.
            _cohfb = Req(a, "cohfb") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--cohfb must be 0 or 1") };
            decoder.SetCoherentFallbackEnabled(_cohfb);
#if HAS_COHMS
            // COH-MULTISET-BUILD (spec section 6.2): decoder.coherentFallbackMultiSet is REQUIRED (--cohms 0|1), set ONCE per process and read back at start and end.
            _cohms = Req(a, "cohms") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--cohms must be 0 or 1") };
            decoder.SetCoherentFallbackMultiSet(_cohms);
#endif
#if HAS_COHAUDIO
            // COH-FB-AUDIO (scratch patch for the Developer's R0; QA to adopt): --cohaudio Original|Residual|Both is REQUIRED.
            decoder.SetCoherentFallbackAudio(Enum.Parse<OpenWSFZ.Abstractions.CoherentFallbackAudio>(Req(a, "cohaudio"), ignoreCase: true));
#endif
#if HAS_UNGATED
            // COH-GATE-G R-F4 acceptance: --ungated 0|1 sets decoder.coherentFallbackResidualUngated; ABSENT leaves the decoder at its start value (false = the key absent).
            if (a.TryGetValue("ungated", out var ung)) decoder.SetCoherentFallbackResidualUngated(ung switch { "0" => false, "1" => true, _ => throw new ArgumentException("--ungated must be 0 or 1") });
            LateSub.Ungated = decoder.CoherentFallbackResidualUngated;   // LATE-SUB: the configuration the new residual-audio runs apply (T1 when false, ungated when true)
#endif
#if HAS_LATEROUND
            // LATE-SUB L1' acceptance (build commit b1d8a06e): --late-round 0|1 sets decoder.lateSubtractionRound; ABSENT leaves the decoder at its start value (false = the key absent). Read back at start and end.
            if (a.TryGetValue("late-round", out var lr)) decoder.SetLateSubtractionRound(lr switch { "0" => false, "1" => true, _ => throw new ArgumentException("--late-round must be 0 or 1") });
#endif
#if HAS_CQAP
            // CQ-AP (build 7ca00264): --cq-ap 0|1 is REQUIRED on this build and read back at start and end (the arm's one change: OFF = 0, ON = 1).
            decoder.SetCqApEnabled(Req(a, "cq-ap") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--cq-ap must be 0 or 1") });
#endif
#if HAS_COHRESCAND
            // COH-RES-CAND (#272, build b0d01f4f): --cohrescand 0|1 is REQUIRED on this build and read back at start and end (the arm's one change: A = 0, B = 1).
            decoder.SetCoherentFallbackResidualCandidates(Req(a, "cohrescand") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--cohrescand must be 0 or 1") });
#endif
#if HAS_LRFULL
            // LR-FULL (dev task 2026-11-18-lr-full-diagnostic-switches, build 80bbd74b): --lr-x1 0|1 (X1: the third run without the 1097 Hz gate) and --lr-x2 0|1 (X2: a fallback run on the late round's residual) are REQUIRED on this build and read back at start and end.
            // OFF arm: 0 0; ON arm: 1 1. The tag sink records which step published each row (nc-dump trailing column: 0 none, 1 v2 at or below the gate, 2 X1 above the gate, 3 late-round primary, 4 X2 F1b-passed, 5 X2 admitted-only).
            decoder.SetDiagThirdRunUngated(Req(a, "lr-x1") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--lr-x1 must be 0 or 1") });
            decoder.SetDiagLateFallbackOnResidual(Req(a, "lr-x2") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--lr-x2 must be 0 or 1") });
            decoder.DiagRowTagSink = (_, text, step) => _lrStep[text.TrimEnd()] = (int)step;
#endif
#if HAS_LRBUILD
            // LR-BUILD (dev task 2026-11-20-lr-build-x1-x2-product-settings, build c23aa7e9): --lr-x1 0|1 (X1 = decoder.coherentFallbackResidualCandidatesUngated) and --lr-x2 0|1 (X2 = decoder.lateRoundFallback), the PRODUCT setters,
            // REQUIRED and read back at start and end. Provenance is the row's own Path (nc-dump column 10): 4 = X1 above the gate, 5 = X2.
            decoder.SetCoherentFallbackResidualCandidatesUngated(Req(a, "lr-x1") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--lr-x1 must be 0 or 1") });
            decoder.SetLateRoundFallback(Req(a, "lr-x2") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--lr-x2 must be 0 or 1") });
#endif
#if HAS_XCPRIOR
            // XC-BUILD (dev task 2026-11-13-xc-template-build): --xc-prior 0|1, --xc-shadow 0|1 and --xc-te <double|inf> are REQUIRED on this build and read back at start and end.
            // TR: --xc-prior 1 --xc-shadow 1 --xc-te inf (nothing published); OFF: 0 0 inf; ON: 1 1 <the frozen T_E>.  --xc-probe-out: the per-test numbers sink (numbers only).
            decoder.SetCrossCyclePrior(Req(a, "xc-prior") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--xc-prior must be 0 or 1") });
            decoder.SetCrossCyclePriorShadow(Req(a, "xc-shadow") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--xc-shadow must be 0 or 1") });
            // --xc-defaults 1 (the shipped-defaults check, spec 'freeze the thresholds'): the three setters below are NOT called, so the product's own defaults for T_E, T_P and the veto are in force and read back
            // as xcte=, xctp= and xcveto=. The other XC options (xc-prior, xc-shadow) are still required. Any other value, or absent: the setters are required as before.
            bool xcDefaults = a.TryGetValue("xc-defaults", out var xcDefaultsArg) && xcDefaultsArg == "1";
            if (!xcDefaults)
            {
                string xcTe = Req(a, "xc-te");
                decoder.SetCrossCyclePriorThreshold(xcTe == "inf" ? double.PositiveInfinity : double.TryParse(xcTe, NumberStyles.Float, CultureInfo.InvariantCulture, out double xcTeV) && xcTeV > 0 ? xcTeV : throw new ArgumentException("--xc-te must be inf or a positive number"));
#if HAS_XCREMEDY
                // XC-BUILD remedy (Amendment 6): --xc-veto 0|1 (R14; 0 only in TR2) and --xc-tp <double> (R15; 0 in TR2 and the OFF arms) are REQUIRED on this build and read back as xcveto= and xctp=.
                decoder.SetCrossCyclePriorColocationVeto(Req(a, "xc-veto") switch { "0" => false, "1" => true, _ => throw new ArgumentException("--xc-veto must be 0 or 1") });
                string xcTp = Req(a, "xc-tp");
                decoder.SetCrossCyclePriorParityThreshold(double.TryParse(xcTp, NumberStyles.Float, CultureInfo.InvariantCulture, out double xcTpV) && xcTpV >= 0 ? xcTpV : throw new ArgumentException("--xc-tp must be a number >= 0"));
#endif
            }
            if (a.TryGetValue("xc-out", out var xcOutPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(xcOutPath))!);
                _xcOut = new StreamWriter(xcOutPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            }
            if (a.TryGetValue("xc-probe-out", out var xcProbePath))
            {
                if (!xcProbePath.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--xc-probe-out must be under _qa-scratch (HK-037)");
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(xcProbePath))!);
                _xcProbe = new StreamWriter(xcProbePath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
#if HAS_XCREMEDY
                if (new FileInfo(xcProbePath).Length == 0) _xcProbe.WriteLine("stamp,kind,s_e_star,s_p,prior_age_cycles,prior_freq_hz,prior_dt_s,prior_batch,vetoed,argmax_df_hz,argmax_dt_s");   // = xc_tp.py COLUMNS
#else
                if (new FileInfo(xcProbePath).Length == 0) _xcProbe.WriteLine("stamp,kind,s_e_star,prior_age_cycles,argmax_df_hz,argmax_dt_s");
#endif
                decoder.CrossCyclePriorProbe = new XcProbeSink();
            }
#endif
            if (a.TryGetValue("cohfb-out", out var cohPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(cohPath))!);
                _cohOut = new StreamWriter(cohPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
#if HAS_COHFB4
                if (new FileInfo(cohPath).Length == 0) _cohOut.WriteLine("stamp,seen,eligible,attempted,crc_ok,f1b_computed,gated,published,abandoned,elapsed_ms,published_edge,workers,fb_start_ms,fb_wall_ms,batch,batch4_published,batch4_publish_ms"
#if HAS_COHMS
                    + ",sets,walk_entered,crc_c1,crc_j2,crc_j3,crc_n1"
#if HAS_COHRESCAND
                    + ",resrun,rescand,reselig,resnew,resnewgated,resnewkept,resabandoned,reswallms"
#endif
#endif
                    );
#else
                if (new FileInfo(cohPath).Length == 0) _cohOut.WriteLine("stamp,seen,eligible,attempted,crc_ok,f1b_computed,gated,published,abandoned,elapsed_ms,published_edge");
#endif
            }
#endif
#if HAS_LEAN
            // DR-2 step 2d (the lean decoder replay): --engine classic|lean is REQUIRED on this build and read back at start and end. With lean the classic keys the arm still
            // passes (cohfb, late-round, subtraction threads, xc-defaults) are accepted and ignored by the decoder (spec section 2.5); the lean engine reads the audio mode, the
            // ungated and residual-candidates flags, cq-ap and the cross-cycle settings. --lean-threads (default 2 = decoder.threads) and --effort normal|fast apply to lean only.
            {
                string eng = Req(a, "engine");
                if (eng is not ("classic" or "lean")) throw new ArgumentException("--engine must be classic or lean");
                _engine = eng;
                decoder.SetEngine(eng == "lean" ? DecoderEngine.Lean : DecoderEngine.Classic);
                _leanThreads = a.TryGetValue("lean-threads", out var lt) ? int.Parse(lt, CultureInfo.InvariantCulture) : DecoderConfig.DefaultThreads;
                decoder.SetLeanThreads(_leanThreads);
#if HAS_FINEGRID
                // FINE-GRID: --lean-thin 0|1, --lean-time-osr and --lean-freq-osr (0, 2 or 4; 0 = today's 2). Logged at the start so a run records what it ran with.
                LeanThin = a.TryGetValue("lean-thin", out var lth) && lth == "1";
                LeanTimeOsr = a.TryGetValue("lean-time-osr", out var lto) ? int.Parse(lto, CultureInfo.InvariantCulture) : 0;
                LeanFreqOsr = a.TryGetValue("lean-freq-osr", out var lfo) ? int.Parse(lfo, CultureInfo.InvariantCulture) : 0;
                log.Line("INFO", "lean grid: thin=" + (LeanThin ? 1 : 0) + " time_osr=" + LeanTimeOsr + " freq_osr=" + LeanFreqOsr);
#endif
                _effort = a.TryGetValue("effort", out var ef) ? ef : DecoderEffortNames.Normal;
                if (_effort is not ("normal" or "fast")) throw new ArgumentException("--effort must be normal or fast");
                decoder.SetEffort(DecoderEffortNames.Parse(_effort));
                if (a.TryGetValue("lean-out", out var leanPath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(leanPath))!);
                    _leanOut = new StreamWriter(leanPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
                    if (new FileInfo(leanPath).Length == 0) _leanOut.WriteLine("stamp,abandoned,error,results,rounds,ungated,s3_wall_ms,s3_cpu_ms,fit_cpu_ms,search_cpu_ms,decode_cpu_ms,other_cpu_ms,effort,b1,b2,b3,xc,xc_detected,fit_skipped"
#if HAS_XCROUND
                        + ",b4,xr_detections,xr_fits,xr_subtracted,xr_fitnone,xr_found,xr_kept,xr_results,xr_decodes,xr_error,xr_abandoned,xr_wall_ms,xr_cpu_ms,xr_acands,xr_aerased"
#endif
                        );
                }
#if HAS_PROBE
                // SUB-PROBE: --lean-probe 1 --probe-out <path under _qa-scratch>: one TSV row per probe row (numbers only, no text); an overflowed cycle writes an OVERFLOW row.
                if (a.TryGetValue("lean-probe", out var lp) && lp == "1")
                {
                    if (!a.TryGetValue("probe-out", out var probePath)) throw new ArgumentException("--lean-probe 1 needs --probe-out <path>");
                    if (!probePath.Replace((char)92, '/').Contains("/_qa-scratch/")) throw new ArgumentException("--probe-out must be under _qa-scratch");
                    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(probePath))!);
                    _probeOut = new StreamWriter(probePath, append: false, new UTF8Encoding(false)) { AutoFlush = true };
                    _probeOut.WriteLine("stamp\tkind\tround\tfreq_hz\ttime_s\tamp\tsupp_db\tscore\tkept\toutcome\tgate\ta_code\ta_unsat\tb_code\tb_unsat\tcq_code\tcq_unsat"
#if HAS_FINEGRID
                        + "\ttime_sub\tfreq_sub"
#endif
                        );
                }
#endif
            }
#endif
            Readback(decoder, log, "start", threadsNote);
        }
#endif
        for (int idx = 0; idx < cycles.Count; idx++)
        {
            string stamp = cycles[idx];
            var pcm = ReadWav(Path.Combine(WavDirFor(run), stamp + ".wav"));
            var cyc = StampToUtc(stamp);
            if (mode == "off")
            {
                if (!done.Contains(stamp + "|NA"))
                    await Decode1(decoder, pcm, cyc, csv, run, stratum, stamp, idx, "NA");
                continue;
            }
            // "on": flag ON, single-batch DecodeAsync, ONE call per cycle (the S1 reference; same native call sequence
            // as "two1", so the process-global callsign hash table has the same history in both).
            if (mode == "on")
            {
                if (done.Contains(stamp + "|ON")) continue;
                SetFlag(decoder, true);
                await Decode1(decoder, pcm, cyc, csv, run, stratum, stamp, idx, "ON");
                continue;
            }
#if HAS_THIRDPASS
            // "three0" / "three1": subtraction ON, DecodeStagedAsync, ONE call per cycle; decoding depth Normal / Deep. Both arms use the same
            // entry (Normal delivers exactly what DecodeTwoStageAsync does), batch 3 is its own kind in every output.
            if (mode is "three0" or "three1")
            {
                string tflag = mode == "three1" ? "DEEP" : "NORMAL";
                if (done.Contains(stamp + "|" + tflag)) continue;
                await DecodeThree(decoder, pcm, cyc, csv, run, stratum, stamp, idx, tflag);
                continue;
            }
#endif
#if HAS_TWOSTAGE
            // "two0": flag OFF, DecodeTwoStageAsync, ONE call per cycle: the OFF arm of the offline replay. Same call,
            // same scoring as "two1"; with the flag OFF the decoder publishes batch 1 only and returns an empty batch 2.
            if (mode == "two0")
            {
                if (done.Contains(stamp + "|OFF")) continue;
                SetFlag(decoder, false);
                await DecodeTwo(decoder, pcm, cyc, csv, run, stratum, stamp, idx, "OFF");
                continue;
            }
            // "two1": flag ON, DecodeTwoStageAsync, ONE call per cycle.
            if (mode == "two1")
            {
                if (done.Contains(stamp + "|ON")) continue;
                SetFlag(decoder, true);
                await DecodeTwo(decoder, pcm, cyc, csv, run, stratum, stamp, idx);
                continue;
            }
#endif
            // alt / two: OFF then ON on even index, ON then OFF on odd index (spreads drift). "two" makes the ON call
            // the two-stage one and records the time to batch 1.
            string[] order = idx % 2 == 0 ? ["OFF", "ON"] : ["ON", "OFF"];
            foreach (var flag in order)
            {
                if (done.Contains(stamp + "|" + flag)) continue;
                SetFlag(decoder, flag == "ON");
#if HAS_TWOSTAGE
                if (mode == "two" && flag == "ON")
                {
                    await DecodeTwo(decoder, pcm, cyc, csv, run, stratum, stamp, idx);
                    continue;
                }
#endif
                await Decode1(decoder, pcm, cyc, csv, run, stratum, stamp, idx, flag);
            }
        }
#if HAS_TWOSTAGE
        if (mode is "two0" or "two1") Readback(decoder, log, "end", threadsNote);
#endif
#if HAS_THIRDPASS
        if (mode is "three0" or "three1") Readback(decoder, log, "end", threadsNote);
#endif
        // V2' second probe point: after the last cycle. Recorded; row V2' is judged afterwards by nhard_rep_rows.py.
        if (_probe is not null && !RunProbe("end", log))
            log.Raw("# V2-prime FAIL at the end probe");
#if HAS_DXPED
        // #225 phase 2 (shim 20260064): the measure-only (i3, n3) counts of CRC-passing candidates dropped as an unsupported type,
        // process-lifetime cumulative, cell = i3 * 8 + n3. Counted per decode ATTEMPT (a payload seen again in a later pass counts again).
        // Numeric only. Written next to --out.
        {
            var cells = decoder.GetUnsupportedTypeCounts();
            File.WriteAllText(Path.ChangeExtension(Path.GetFullPath(outCsv), ".unsupported.json"),
                "{\"cells_i3_times_8_plus_n3\":[" + string.Join(",", cells) + "],\"total\":" + cells.Sum() + ",\"i0n3_7\":" + cells[7] + "}");
        }
#endif
        return 0;
    }

    private static async Task Decode1(Ft8Decoder d, float[] pcm, DateTime cycleStart, StreamWriter csv,
                                      string run, string stratum, string stamp, int seq, string flag)
    {
        string exc = "";
        int n = -1;
        var sw = Stopwatch.StartNew();
        try
        {
            var res = await d.DecodeAsync(pcm, cycleStart);
            n = res.Count;
            WriteOutcomes(stamp, flag == "ON" ? "single_on" : "single_off", res);
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        csv.WriteLine(string.Join(",", run, stratum, stamp, seq.ToString(CultureInfo.InvariantCulture), flag,
            sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture),
            n.ToString(CultureInfo.InvariantCulture), exc) + (_wide ? ",,," : ""));
    }

    /// <summary>Whether the residual pass ran for the cycle being decoded, and whether it was deadline-abandoned or contained
    /// an exception. One decode at a time, so plain volatile fields are enough.</summary>
    private static class SubfeasProbe
    {
        public static volatile bool Ran, Abandoned, Contained;
        public static void Reset() { Ran = false; Abandoned = false; Contained = false; }
        public static void Set(bool abandoned, bool contained) { Ran = true; Abandoned = abandoned; Contained = contained; }
    }

    // ---- V2' probe: ft8_ldpc_decode_llrs through the already-loaded libft8.dll (no product binding; qa/ code) -----------------
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int LdpcDecodeLlrsFn(float[] llr174, int maxIters, int osdDepth, byte[] outA91,
                                          out int outLdpcErrors, out int outPath, out int outCrcOk);

    private sealed record ProbeVector(string Name, float[] Llr, byte[] ExpectedA91, int NhardTrue);

    private sealed class ProbeSet
    {
        public required LdpcDecodeLlrsFn Fn;
        public required int MaxIters, OsdDepth, PayloadBits;
        public required List<ProbeVector> Vectors;
        public required StreamWriter Out;
    }

    private static ProbeSet? _probe;

    private static void LoadProbe(string jsonPath, string outPath)
    {
        using var doc = JsonDocument.Parse(File.ReadAllBytes(jsonPath));
        var r = doc.RootElement;
        var vecs = new List<ProbeVector>();
        int payloadBits = 0;
        foreach (var name in new[] { "P_lo", "P_hi" })
        {
            var v = r.GetProperty("vectors").GetProperty(name);
            var llr = v.GetProperty("llr").EnumerateArray().Select(e => (float)e.GetDouble()).ToArray();
            if (llr.Length != 174) throw new InvalidDataException("probe vector length");
            payloadBits = v.GetProperty("payload_bits").GetInt32();
            vecs.Add(new ProbeVector(name, llr, Convert.FromHexString(v.GetProperty("expected_a91_hex").GetString()!), v.GetProperty("nhard_true").GetInt32()));
        }
        // the same module the managed decoder loaded (same path => same handle): the process-global s_osd_nhard_max is shared
        IntPtr lib = NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, "libft8.dll"));
        var fn = Marshal.GetDelegateForFunctionPointer<LdpcDecodeLlrsFn>(NativeLibrary.GetExport(lib, "ft8_ldpc_decode_llrs"));
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        bool fresh = !File.Exists(outPath);
        var w = new StreamWriter(outPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        if (fresh) w.WriteLine("when,vec,rc,path,crc_ok,payload_match,expected");
        _probe = new ProbeSet { Fn = fn, MaxIters = r.GetProperty("max_iters").GetInt32(), OsdDepth = r.GetProperty("osd_depth").GetInt32(),
                                PayloadBits = payloadBits, Vectors = vecs, Out = w };
    }

    /// <summary>One probe point. Expected (V2'): P_lo accepted (path 1, CRC 1, payload equal) in every arm; P_hi accepted iff
    /// this arm's nhard is 60, otherwise rejected (path -1). Writes one numeric row per vector; returns whether every row met it.</summary>
    private static bool RunProbe(string when, ReplayLog log)
    {
        var p = _probe!;
        bool all = true;
        foreach (var v in p.Vectors)
        {
            var a91 = new byte[12];
            int rc = p.Fn(v.Llr, p.MaxIters, p.OsdDepth, a91, out _, out int path, out int crc);
            bool accepted = rc == 0 && path == 1 && crc == 1;
            // payload = the first PayloadBits bits of a91 (bits 77..90 are the zeroed CRC region, not compared)
            bool match = accepted && PayloadEqual(a91, v.ExpectedA91, p.PayloadBits);
            // The gate accepts iff nhard_true <= the cap (calibrated by full scan: P_lo 26, P_hi 52). Cap 40: P_lo accepted, P_hi rejected; cap 60: both accepted;
            // cap 0 (OSD-OFF): both REJECTED, which is V2'' (the setting reached the gate).
            bool expectAccepted = v.NhardTrue <= OsdNhardMax;
            bool met = expectAccepted ? (accepted && match) : (rc == 0 && path == -1);
            all &= met;
            p.Out.WriteLine(string.Join(",", when, v.Name, rc.ToString(CultureInfo.InvariantCulture), path.ToString(CultureInfo.InvariantCulture),
                crc.ToString(CultureInfo.InvariantCulture), match ? "1" : "0", expectAccepted ? "accept" : "reject"));
        }
        log.Raw($"# probe {when} nhard={OsdNhardMax} met={all}");
        return all;
    }

    private static bool PayloadEqual(byte[] a, byte[] b, int bits)
    {
        for (int i = 0; i < bits; i++)
        {
            int m = 0x80 >> (i % 8);
            if ((a[i / 8] & m) != (b[i / 8] & m)) return false;
        }
        return true;
    }

    private static StreamWriter? _matchedBatch;   // --matched-batch-out: stamp,idx:batch;idx:batch (matched WSJT-X line index and the batch of its match)
    private static StreamWriter? _matched;   // --matched-out: stamp,idx;idx;... (matched WSJT-X line indices, numeric)
#if HAS_LEAN
    private static string _engine = "classic";      // --engine classic|lean (REQUIRED on the HAS_LEAN build)
    private static int _leanThreads;                 // --lean-threads (default decoder.threads)
    private static string _effort = "normal";        // --effort normal|fast (lean only)
    private static StreamWriter? _leanOut;           // --lean-out: one aggregate row per lean cycle, parsed from the decoder's own 'lean:' line (counts and ms only)
#endif
    private static StreamWriter? _abandon;   // --abandon-out: stamp,ran,abandoned,contained (numeric flags, 0/1)

    private static bool _wide;
#if HAS_COHFB
    private static bool _cohfb;                    // --cohfb 0|1: decoder.coherentFallbackEnabled, read back at start and end
#if HAS_COHMS
    private static bool _cohms;                    // --cohms 0|1: decoder.coherentFallbackMultiSet (COH-MULTISET-BUILD), read back at start and end
#endif
    private static StreamWriter? _cohOut;          // --cohfb-out: one aggregate line per cycle (the R12' counters)
#endif
    private static bool _wide3;                    // three0 / three1: 12-column CSV with b3_n
    private static StreamWriter? _third;           // --third-out: stamp,outcome,newDecodes,elapsedMs,fittedSignals
#if HAS_LATEROUND
    private static StreamWriter? _lateOut;         // --late-out (B-TOOL-2): the LATE-SUB round's R6 line, one row per cycle
#endif
    private static StreamWriter? _outcomes;
    private static StreamWriter? _dxped;   // #225 phase 2: type-0.1 texts, scratch only (see --dxped-dump)
    private static StreamWriter? _ncDump;   // --nc-dump <path>: stamp,kind,matched,freq,dt,snr,same_any,min_df,wcount,path,text for every scored decode (scratch only)
    private static StreamWriter? _implDump;   // --impl-dump: stamp,event[,text] (scratch only; events D = implausible drop WITH text, M = info marker, H = batch hand-off)
    private static StreamWriter? _stageOut;   // --stage-out: per-cycle counts of the fallback stages (HasInternals build only)
    private static volatile string _curStamp = "";
#if HAS_LRFULL
    // LR-FULL D4: the decoder's diagnostic tag sink fills this (message text -> Ft8Decoder.DiagRowStep as int) during a cycle; cleared at each cycle's start, read when the cycle's nc-dump rows are written. Text stays in memory (HK-037).
    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, int> _lrStep = new(StringComparer.Ordinal);
#endif
#if HAS_LEAN
    private static readonly System.Text.RegularExpressions.Regex LeanLineRx = new(
        @"results=(\d+) threads=\d+ abandoned=(\d+) error=(-?\d+).*?s3: rounds=(\d+) ungated=(\d+) (?:fitSkipped=(\d+) )?wall_ms=([\d.,]+) cpu_ms=([\d.,]+) fitCpu_ms=([\d.,]+) searchCpu_ms=([\d.,]+) decodeCpu_ms=([\d.,]+) otherCpu_ms=([\d.,]+).*?effort=(\w+) batches: b1=(\d) b2=(\d) b3=(\d) xc=(\S+) xcDetected=(\d+)(?: b4=(\d) xcRound\[detections=(\d+) fits=(\d+) subtracted=(\d+) fitNone=(\d+) found=(\d+) kept=(\d+) tierA=(\d+) results=(\d+) (?:aCands=(?<ac>\d+) aErased=(?<ae>\d+) )?decodes=(\d+) error=(-?\d+) abandoned=(\d+) wall_ms sub=[\d.,]+ spec=[\d.,]+ search=[\d.,]+ decode=[\d.,]+ total=([\d.,]+) cpu_ms fit=[\d.,]+ sum=[\d.,]+ spec=[\d.,]+ search=[\d.,]+ decode=[\d.,]+ total=([\d.,]+)\])?",
        System.Text.RegularExpressions.RegexOptions.Compiled | System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    /// <summary>One row per lean cycle into --lean-out, parsed from the decoder's own aggregate-only 'lean:' line (decimal commas normalised). A line that does not parse is written as a row of "parse-failed" so a format drift cannot pass silently.</summary>
    private static void LeanRow(string rendered)
    {
        var w = _leanOut; if (w is null) return;
        var m = LeanLineRx.Match(rendered);
        lock (w)
        {
            if (!m.Success) { w.WriteLine(_curStamp + ",parse-failed"); return; }
            var g = m.Groups;
            string N(int i) => g[i].Value.Replace(',', '.');
            string skipped = g[6].Success ? g[6].Value : "0";
            w.WriteLine(string.Join(",", _curStamp, g[2].Value, g[3].Value, g[1].Value, g[4].Value, g[5].Value, N(7), N(8), N(9), N(10), N(11), N(12), g[13].Value, g[14].Value, g[15].Value, g[16].Value, g[17].Value, g[18].Value, skipped
#if HAS_XCROUND
                , g[19].Success ? g[19].Value : "0", g[19].Success ? g[20].Value : "0", g[19].Success ? g[21].Value : "0", g[19].Success ? g[22].Value : "0", g[19].Success ? g[23].Value : "0", g[19].Success ? g[24].Value : "0"
                , g[19].Success ? g[25].Value : "0", g[19].Success ? g[27].Value : "0", g[19].Success ? g[28].Value : "0", g[19].Success ? g[29].Value : "0", g[19].Success ? g[30].Value : "0", g[19].Success ? N(31) : "0", g[19].Success ? N(32) : "0", g["ac"].Success ? g["ac"].Value : "0", g["ae"].Success ? g["ae"].Value : "0"
#endif
                ));
        }
    }
#endif
#if HAS_PROBE
    private static StreamWriter? _probeOut;               // --lean-probe 1 --probe-out: SUB-PROBE rows, numbers only
    internal static bool ProbeOn => _probeOut is not null;
#if HAS_FINEGRID
    internal static bool LeanThin;
    internal static int LeanTimeOsr, LeanFreqOsr;
#endif
    internal static void WriteProbe(OpenWSFZ.Ft8.Interop.LeanProbeRow[] rows, bool overflow)
    {
        var w = _probeOut; if (w is null) return;
        var ci = CultureInfo.InvariantCulture;
        lock (w)
        {
            foreach (var r in rows)
                w.WriteLine(string.Join("\t", _curStamp, r.Kind.ToString(ci), r.Round.ToString(ci), r.FreqHz.ToString("F2", ci), r.TimeS.ToString("F3", ci), r.Amp.ToString("F4", ci), r.SuppDb.ToString("F2", ci),
                    r.Score.ToString(ci), r.Kept.ToString(ci), r.Outcome.ToString(ci), r.Gate.ToString(ci), r.ACode.ToString(ci), r.AUnsat.ToString(ci), r.BCode.ToString(ci), r.BUnsat.ToString(ci), r.CqCode.ToString(ci), r.CqUnsat.ToString(ci)
#if HAS_FINEGRID
                    , r.TimeSub.ToString(ci), r.FreqSub.ToString(ci)
#endif
                    ));
            if (overflow) w.WriteLine(_curStamp + "\tOVERFLOW");
        }
    }
#endif
    internal static string CurStamp => _curStamp;
    internal static void ImplEvent(string ev, string text = "")
    {
        var w = _implDump; if (w is null) return;
        lock (w) w.WriteLine(_curStamp + "	" + ev + (text.Length > 0 ? "	" + text : ""));
    }
    private static StreamWriter? _fbDump;   // --fb-dump <path>: working file of fallback outputs with text (scratch only)
    // CQ-AP (build 7ca00264): the decode's apKind (0 none, 1 cq) for the nc-dump's trailing column; 0 on builds without it, so older output is byte-identical.
    private static int ApKindOf(DecodeResult r)
    {
#if HAS_CQAP
        return (int)r.ApKind;
#else
        return 0;
#endif
    }
    private static int DecodePath(DecodeResult r)
    {
#if HAS_COHFB
        return r.Path;
#else
        return 0;
#endif
    }
    private static bool _outcomeTextHash;   // default OFF (HK-037: a text-derived hash is message identity)

    // ---- Test B: in-process WSJT-X corroboration (counts only) -----------------------------------------------
    private static StreamWriter? _testB;
    private static readonly Dictionary<string, List<(int Snr, int Freq, string Msg)>> _wsjtx = new();
    private const int CorroborationDeltaHz = 10;   // Amendment-1 / Stage 2 convention (|df| <= 10 Hz)

    /// <summary>
    /// Pre-registered SNR bands of the OpenWSFZ decode, for the per-band report (a pooled rate would hide whether
    /// uncorroborated decodes cluster at the weak end, where false positives live): A >= 0, B -10..-1, C -15..-11, D <= -16 dB.
    /// </summary>
    private static int ParseNhard(string v)
    {
        if (!int.TryParse(v, NumberStyles.Integer, CultureInfo.InvariantCulture, out int n) || n < NhardMin || n > NhardMax)
            throw new ArgumentException($"--nhard must be an integer in [{NhardMin}, {NhardMax}]");
        return n;
    }

    /// <summary>The replay clock mode read back in every "# readback" line: system (default) or frozen (the decoder's cycle budget never expires).
    /// STANDING GUARD (Architect, 2026-11-13): a frozen-clock arm measures the decoder with NO budget, so its NET, ABANDON and LATE are never cited as station figures; every row from one names "clock: frozen" beside the host and the libft8 SHA-256.</summary>
    private static string ClockMode = "system";

    /// <summary>A TimeProvider whose timestamp never advances: every elapsed time the decoder's BudgetClock reads is zero, so no budget check can fire.</summary>
    private sealed class FrozenTimeProvider : TimeProvider
    {
        public override long GetTimestamp() => 0;
        public override long TimestampFrequency => global::System.Diagnostics.Stopwatch.Frequency;
    }

    private static string BandOf(int snr) => snr >= 0 ? "A" : snr >= -10 ? "B" : snr >= -15 ? "C" : "D";

    private static void LoadWsjtx(string path)
    {
        // Same line convention as corpus.py _load_all_txt: field 3 "Rx", field 4 "FT8", snr, dt, freq, then the message.
        // The message text stays in this dictionary in memory; it is never written anywhere.
        foreach (var line in File.ReadLines(path))
        {
            var f = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (f.Length < 8 || f[2] != "Rx" || f[3] != "FT8") continue;
            if (!int.TryParse(f[4], out int snr) || !int.TryParse(f[6], out int freq)) continue;
            if (!_wsjtx.TryGetValue(f[0], out var l)) _wsjtx[f[0]] = l = new();
            l.Add((snr, freq, string.Join(" ", f.Skip(7)).Trim()));
        }
    }

    /// <summary>
    /// Scores one cycle: each OpenWSFZ decode (batch 1 = pass-0, batch 2 = the residual decodes) is corroborated iff
    /// WSJT-X decoded the same message text in the same cycle within 10 Hz, paired ONE-TO-ONE nearest-first across both
    /// batches (a WSJT-X decode corroborates at most one OpenWSFZ decode). Emits COUNTS per (kind, SNR band); text never leaves.
    /// </summary>
    private static void ScoreTestB(string run, string stamp, IReadOnlyList<DecodeResult> b1, IReadOnlyList<DecodeResult> b2,
                                   IReadOnlyList<DecodeResult>? b3 = null, IReadOnlyList<DecodeResult>? b4 = null, IReadOnlyList<DecodeResult>? b5 = null, IReadOnlyList<DecodeResult>? b6 = null)
    {
        if (_testB is null) return;
        var w = _wsjtx.TryGetValue(stamp, out var l) ? l : new List<(int Snr, int Freq, string Msg)>();
        var ows = new List<(int Kind, int Snr, int Freq, string Msg, double Dt, int Path, int Ap)>();
        foreach (var r in b1) ows.Add((1, r.Snr, r.FreqHz, r.Message.TrimEnd(), r.Dt, DecodePath(r), ApKindOf(r)));
        foreach (var r in b2) ows.Add((2, r.Snr, r.FreqHz, r.Message.TrimEnd(), r.Dt, DecodePath(r), ApKindOf(r)));
        // third-pass-deep (#240): batch 3 is its OWN kind, never folded into 1 or 2. b3 == null (every older mode) leaves the output exactly as it was.
        if (b3 is not null) foreach (var r in b3) ows.Add((3, r.Snr, r.FreqHz, r.Message.TrimEnd(), r.Dt, DecodePath(r), ApKindOf(r)));
        // COH-FALLBACK step 4: the fallback's own batch (4 on Deep) is its OWN kind, never folded into 1-3. b4 == null leaves the output exactly as it was.
        if (b4 is not null) foreach (var r in b4) ows.Add((4, r.Snr, r.FreqHz, r.Message.TrimEnd(), r.Dt, DecodePath(r), ApKindOf(r)));
        // L1' build (F5): the late subtraction round's own batch (5) is its OWN kind, never folded into 1-4. b5 == null leaves the output exactly as it was.
        if (b5 is not null) foreach (var r in b5) ows.Add((5, r.Snr, r.FreqHz, r.Message.TrimEnd(), r.Dt, DecodePath(r), ApKindOf(r)));
        // XC-BUILD: the cross-cycle template stage's own batch (6) is its OWN kind, never folded into 1-5. b6 == null leaves the output exactly as it was.
        if (b6 is not null) foreach (var r in b6) ows.Add((6, r.Snr, r.FreqHz, r.Message.TrimEnd(), r.Dt, DecodePath(r), ApKindOf(r)));
        var cands = new List<(int Df, int Oi, int Wi)>();
        for (int i = 0; i < ows.Count; i++)
            for (int j = 0; j < w.Count; j++)
            {
                int df = Math.Abs(ows[i].Freq - w[j].Freq);
                if (df <= CorroborationDeltaHz && string.Equals(ows[i].Msg, w[j].Msg, StringComparison.Ordinal))
                    cands.Add((df, i, j));
            }
        cands.Sort((x, y) => x.Df != y.Df ? x.Df.CompareTo(y.Df) : x.Oi != y.Oi ? x.Oi.CompareTo(y.Oi) : x.Wi.CompareTo(y.Wi));
        var usedO = new bool[ows.Count];
        var usedW = new bool[w.Count];
        var matchBatch = new int[w.Count];     // the Kind (1, 2 or 3) of the OpenWSFZ decode that matched each WSJT-X line; 0 = unmatched
        foreach (var (_, oi, wi) in cands)
        {
            if (usedO[oi] || usedW[wi]) continue;
            usedO[oi] = true;
            usedW[wi] = true;
            matchBatch[wi] = ows[oi].Kind;
        }
        // WORKING FILE (HK-037 amendment 2026-10-10): per-output message text, ONLY under D:\Projects\claude\_qa-scratch\<job>\, read by code only, deleted at job close. Fallback (path 2) outputs only.
        if (_ncDump is not null)
            for (int i = 0; i < ows.Count; i++)
            {
                bool sameTextAnyFreq = w.Any(x => string.Equals(x.Msg, ows[i].Msg, StringComparison.Ordinal));
                int minDf = w.Where(x => string.Equals(x.Msg, ows[i].Msg, StringComparison.Ordinal)).Select(x => Math.Abs(x.Freq - ows[i].Freq)).DefaultIfEmpty(-1).Min();
                _ncDump.WriteLine(string.Join("	", stamp, ows[i].Kind, usedO[i] ? 1 : 0, ows[i].Freq, ows[i].Dt.ToString("F2", CultureInfo.InvariantCulture), ows[i].Snr,
                    sameTextAnyFreq ? 1 : 0, minDf, w.Count, ows[i].Path, ows[i].Msg
#if HAS_CQAP
                    , ows[i].Ap   // CQ-AP: trailing column after the text (older consumers read fixed positions up to the text)
#endif
#if HAS_LRFULL
                    , _lrStep.TryGetValue(ows[i].Msg, out int lrStep) ? lrStep : 0   // LR-FULL: the step that published the row (trailing column after the apKind)
#endif
                    ));
            }
        if (_fbDump is not null)
            for (int i = 0; i < ows.Count; i++)
                if (ows[i].Path == 2)
                {
                    bool sameTextAnyFreq = w.Any(x => string.Equals(x.Msg, ows[i].Msg, StringComparison.Ordinal));
                    int minDf = w.Where(x => string.Equals(x.Msg, ows[i].Msg, StringComparison.Ordinal)).Select(x => Math.Abs(x.Freq - ows[i].Freq)).DefaultIfEmpty(-1).Min();
                    _fbDump.WriteLine(string.Join("	", stamp, ows[i].Kind, usedO[i] ? 1 : 0, ows[i].Freq, ows[i].Dt.ToString("F2", CultureInfo.InvariantCulture), ows[i].Snr,
                        sameTextAnyFreq ? 1 : 0, minDf, w.Count, ows[i].Msg));
                }
        foreach (int kind in b6 is not null ? new[] { 1, 2, 3, 4, 5, 6 } : b5 is not null ? new[] { 1, 2, 3, 4, 5 } : b4 is not null ? new[] { 1, 2, 3, 4 } : b3 is null ? new[] { 1, 2 } : new[] { 1, 2, 3 })
            foreach (var band in new[] { "A", "B", "C", "D" })
            {
                int n = 0, c = 0;
                for (int i = 0; i < ows.Count; i++)
                    if (ows[i].Kind == kind && BandOf(ows[i].Snr) == band) { n++; if (usedO[i]) c++; }
                _testB.WriteLine(string.Join(",", run, stamp, kind == 1 ? "b1" : kind == 2 ? "b2" : kind == 3 ? "b3" : kind == 4 ? "b4" : kind == 5 ? "b5" : "b6", band,
                    n.ToString(CultureInfo.InvariantCulture), c.ToString(CultureInfo.InvariantCulture)));
            }
        _matched?.WriteLine(stamp + "," + string.Join(";", Enumerable.Range(0, usedW.Length).Where(j => usedW[j])));
        _matchedBatch?.WriteLine(stamp + "," + string.Join(";", Enumerable.Range(0, usedW.Length).Where(j => usedW[j]).Select(j => j.ToString(CultureInfo.InvariantCulture) + ":" + matchBatch[j].ToString(CultureInfo.InvariantCulture))));
        _testB.WriteLine(string.Join(",", run, stamp, "ws", "ALL", w.Count.ToString(CultureInfo.InvariantCulture),
            usedW.Count(x => x).ToString(CultureInfo.InvariantCulture)));
    }

    /// <summary>
    /// One line per decode: <c>stamp,kind,idx,freqHz,dt,snr</c> (numeric only). The 7th field, an 8-hex-digit hash of the
    /// message text, is written ONLY when <c>--outcome-text-hash true</c> is given (default off, HK-037: a text-derived
    /// hash is message identity); the text itself is never written anywhere.
    /// </summary>
    private static void WriteOutcomes(string stamp, string kind, IReadOnlyList<DecodeResult> list)
    {
        if (_outcomes is null) return;
        for (int i = 0; i < list.Count; i++)
        {
            var r = list[i];
            var fields = new List<string> { stamp, kind, i.ToString(CultureInfo.InvariantCulture),
                r.FreqHz.ToString(CultureInfo.InvariantCulture), r.Dt.ToString("F1", CultureInfo.InvariantCulture),
                r.Snr.ToString(CultureInfo.InvariantCulture) };
#if HAS_COHFB
            fields.Add(r.Path.ToString(CultureInfo.InvariantCulture));       // R11 provenance: 0 ordinary, 1 residual + third, 2 fallback (7th field; the text hash, if asked for, is the 8th)
#endif
            if (_outcomeTextHash)
                fields.Add(Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(r.Message.TrimEnd())))[..8]);
            _outcomes.WriteLine(string.Join(",", fields));
            if (_dxped is not null)
            {
                var t = r.Message.TrimEnd();
                var tk = t.Split(' ');
                if (tk.Length == 5 && tk[1] == "RR73;")
                    _dxped.WriteLine(string.Join("	", stamp, kind, r.FreqHz.ToString(CultureInfo.InvariantCulture),
                        r.Dt.ToString("F1", CultureInfo.InvariantCulture), r.Snr.ToString(CultureInfo.InvariantCulture), t));
            }
        }
    }

#if HAS_THIRDPASS
    /// <summary>
    /// third-pass-deep (#240): the staged decode (Ft8Decoder.DecodeStagedAsync). Collects batch 1, 2 and 3 as they are delivered
    /// (2 and 3 only when non-empty), writes each as its own kind, scores all three against WSJT-X, and records the third-pass
    /// outcome the decoder logged for this cycle. Columns: ...,tb1_ms,b1_n,b2_n,b3_n.
    /// </summary>
    private static async Task DecodeThree(Ft8Decoder d, float[] pcm, DateTime cycleStart, StreamWriter csv,
                                          string run, string stratum, string stamp, int seq, string flag)
    {
        string exc = "";
        int n1 = -1, n2 = 0, n3 = 0;
        IReadOnlyList<DecodeResult>? lsB1 = null, lsB2 = null, lsB3 = null, lsB4 = null;   // LATE-SUB: the product's published batches, handed to the arm work after the cycle
        double tb1 = -1;
#if HAS_COHFB
        double tb2 = -1, tb3 = -1;
        CohProbe.Reset();
#endif
#if HAS_COHFB4
        int n4 = 0;
        double tb4 = -1;
#endif
#if HAS_LATEROUND
        int n5 = 0;
        double tb5 = -1;
#endif
#if HAS_XCPRIOR
        int n6 = 0;
        double tb6 = -1;
        XcProbe.Reset();
#endif
        SubfeasProbe.Reset();
        ThirdProbe.Reset();
#if HAS_LATEROUND
        LateProbe.Reset();
        LateProbe.Unmatched = 0;
#endif
        _curStamp = stamp;
#if HAS_LRFULL
        _lrStep.Clear();
#endif
#if HAS_INTERNALS
        StageProbeInterop.Reset_();
#endif
        var sw = Stopwatch.StartNew();
        try
        {
            IReadOnlyList<DecodeResult>? b1 = null, b2 = null, b3 = null, b4 = null, b5 = null, b6 = null;
            await d.DecodeStagedAsync(pcm, cycleStart, null, (n, batch) =>
            {
                ImplEvent("H	" + n + "	" + batch.Count);
                if (n == 1) { tb1 = sw.Elapsed.TotalMilliseconds; b1 = batch; }
                else if (n == 2)
                {
                    b2 = batch;
#if HAS_COHFB
                    tb2 = sw.Elapsed.TotalMilliseconds;
#endif
                }
                else if (n == 3)
                {
                    b3 = batch;
#if HAS_COHFB
                    tb3 = sw.Elapsed.TotalMilliseconds;
#endif
                }
#if HAS_COHFB4
                else if (n == 4) { b4 = batch; tb4 = sw.Elapsed.TotalMilliseconds; }   // step 4: the fallback's own batch on Deep
#endif
#if HAS_LATEROUND
                else if (n == 5) { b5 = batch; tb5 = sw.Elapsed.TotalMilliseconds; }   // L1' build: the late subtraction round's own batch
#endif
#if HAS_XCPRIOR
                else if (n == 6) { b6 = batch; tb6 = sw.Elapsed.TotalMilliseconds; }   // XC-BUILD: the cross-cycle template stage's own batch
#endif
                else throw new InvalidOperationException("unexpected batch number");
                return Task.CompletedTask;
            });
            IReadOnlyList<DecodeResult> none = Array.Empty<DecodeResult>();
            lsB1 = b1; lsB2 = b2; lsB3 = b3; lsB4 = b4;
            n1 = b1?.Count ?? -1;
            n2 = b2?.Count ?? 0;
            n3 = b3?.Count ?? 0;
#if HAS_COHFB4
            n4 = b4?.Count ?? 0;
#endif
#if HAS_LATEROUND
            n5 = b5?.Count ?? 0;
#endif
#if HAS_XCPRIOR
            n6 = b6?.Count ?? 0;
#endif
            if (b1 is not null) WriteOutcomes(stamp, "b1", b1);
            WriteOutcomes(stamp, "b2", b2 ?? none);
            WriteOutcomes(stamp, "b3", b3 ?? none);
#if HAS_COHFB4
            WriteOutcomes(stamp, "b4", b4 ?? none);
#if HAS_LATEROUND
            WriteOutcomes(stamp, "b5", b5 ?? none);
#if HAS_XCPRIOR
            WriteOutcomes(stamp, "b6", b6 ?? none);
            if (b1 is not null) ScoreTestB(run, stamp, b1, b2 ?? none, b3 ?? none, b4 ?? none, b5 ?? none, b6 ?? none);
#else
            if (b1 is not null) ScoreTestB(run, stamp, b1, b2 ?? none, b3 ?? none, b4 ?? none, b5 ?? none);
#endif
#else
            if (b1 is not null) ScoreTestB(run, stamp, b1, b2 ?? none, b3 ?? none, b4 ?? none);
#endif
#else
            if (b1 is not null) ScoreTestB(run, stamp, b1, b2 ?? none, b3 ?? none);
#endif
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        _abandon?.WriteLine(string.Join(",", stamp, SubfeasProbe.Ran ? "1" : "0", SubfeasProbe.Abandoned ? "1" : "0",
            SubfeasProbe.Contained ? "1" : "0"));
        _third?.WriteLine(string.Join(",", stamp, ThirdProbe.Seen ? ThirdProbe.Outcome : "no-line",
            ThirdProbe.NewDecodes.ToString(CultureInfo.InvariantCulture), ThirdProbe.ElapsedMs.ToString(CultureInfo.InvariantCulture),
            ThirdProbe.Fitted.ToString(CultureInfo.InvariantCulture)));
#if HAS_LATEROUND
        _lateOut?.WriteLine(stamp + "," + LateProbe.Row());
#endif
#if HAS_XCPRIOR
        _xcOut?.WriteLine(stamp + "," + XcProbe.Row());
#endif
        csv.WriteLine(string.Join(",", run, stratum, stamp, seq.ToString(CultureInfo.InvariantCulture), flag,
            sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture),
            (n1 < 0 ? -1 : n1 + n2 + n3
#if HAS_COHFB4
                + n4
#endif
#if HAS_LATEROUND
                + n5
#endif
#if HAS_XCPRIOR
                + n6
#endif
            ).ToString(CultureInfo.InvariantCulture), exc,
            tb1.ToString("F1", CultureInfo.InvariantCulture),
            n1.ToString(CultureInfo.InvariantCulture), n2.ToString(CultureInfo.InvariantCulture), n3.ToString(CultureInfo.InvariantCulture)
#if HAS_COHFB
            , tb2.ToString("F1", CultureInfo.InvariantCulture), tb3.ToString("F1", CultureInfo.InvariantCulture)
#endif
#if HAS_COHFB4
            , n4.ToString(CultureInfo.InvariantCulture), tb4.ToString("F1", CultureInfo.InvariantCulture)
#endif
#if HAS_LATEROUND
            , n5.ToString(CultureInfo.InvariantCulture), tb5.ToString("F1", CultureInfo.InvariantCulture)
#endif
#if HAS_XCPRIOR
            , n6.ToString(CultureInfo.InvariantCulture), tb6.ToString("F1", CultureInfo.InvariantCulture)
#endif
            ));
#if HAS_COHFB
        _cohOut?.WriteLine(stamp + "," + CohProbe.Line());
#endif
#if HAS_INTERNALS
        await LateSub.RunCycle(stamp, lsB1, lsB2, lsB3, lsB4);   // LATE-SUB arms C and L (no-op without --late-sub-dir); bracketed by the hash state
        StageProbeInterop.FlushExtras();
        StageProbeInterop.CapFlush(stamp);   // GAP-RESIDUAL capture (no-op without --cap-dir)
        _stageOut?.WriteLine(stamp + "," + StageProbeInterop.Line());
#endif
    }

#if HAS_COHFB
    /// <summary>COH-FALLBACK Stage 2: the R12' line the decoder logged for the cycle being decoded (aggregates only: counts and ms, no text).</summary>
    private static class CohProbe
    {
        private static volatile bool _seen;
        private static string _vals = "";
        private static readonly System.Text.RegularExpressions.Regex Rx = new(
            @"^Coherent fallback: eligible=(\d+), attempted=(\d+), crcOk=(\d+), f1bComputed=(\d+), gated=(\d+), published=(\d+), abandoned=(\d+), elapsedMs=(\d+), publishedEdge=(\d+), path=(\d+)(?:, workers=(\d+), fbStartMs=(-?\d+), fbWallMs=(-?\d+), batch=(\d+), batch4Published=([01]), batch4PublishMs=(-?\d+)(?:, sets=(on|off), walkEntered=(\d+), crcC1=(\d+), crcJ2=(\d+), crcJ3=(\d+), crcN1=(\d+)(?:, audio=[a-z0-9()-]+(?:, fromOriginal=\d+, fromResidual=\d+, inBoth=\d+(?:, ungated=\d+)?)?(?:, resCand=(residual-R2|residual-R3|fallback-orig), resEligible=(-?\d+), origEligible=(-?\d+))?(?:, resRun=([a-z-]+), resCand=(residual-R2|residual-R3|none), resEligible=(-?\d+), resNew=(\d+), resNewGated=(\d+), resNewKept=(\d+), resAbandoned=(\d+), resWallMs=(\d+))?)?)?)?\.$");
        public static void Reset()
        {
            _seen = false; _vals = "";
#if HAS_COHRESCAND
            _res = ",,,,,,,";
#endif
        }
#if HAS_COHRESCAND
        // COH-RES-CAND v2: the third run's ON-only fields (resRun, resCand, resEligible, resNew, resNewGated, resNewKept, resAbandoned, resWallMs), appended as the LAST eight coh.csv columns; blank when the line has none.
        private static string _res = ",,,,,,,";
        public static string ResTail() => "," + _res;
#endif
        public static void Set(string rendered)
        {
            var m = Rx.Match(rendered);
            if (!m.Success) return;
            _vals = string.Join(",", m.Groups[1].Value, m.Groups[2].Value, m.Groups[3].Value, m.Groups[4].Value, m.Groups[5].Value, m.Groups[6].Value, m.Groups[7].Value, m.Groups[8].Value, m.Groups[9].Value);
#if HAS_COHFB4
            // step 4: the tail is REQUIRED on this build (a line without it is a harness/decoder mismatch, not a cycle to skip silently).
            if (!m.Groups[11].Success) throw new InvalidOperationException("step-4 build logged a fallback line without the workers/batch tail");
            _vals += "," + string.Join(",", m.Groups[11].Value, m.Groups[12].Value, m.Groups[13].Value, m.Groups[14].Value, m.Groups[15].Value, m.Groups[16].Value);
#if HAS_COHMS
            // COH-MULTISET-BUILD: the multi-set tail is REQUIRED on this build (R10).
            if (!m.Groups[17].Success) throw new InvalidOperationException("multi-set build logged a fallback line without the sets/walkEntered tail");
            _vals += "," + string.Join(",", m.Groups[17].Value, m.Groups[18].Value, m.Groups[19].Value, m.Groups[20].Value, m.Groups[21].Value, m.Groups[22].Value);
#endif
#endif
#if HAS_COHRESCAND
            _res = m.Groups[26].Success ? string.Join(",", m.Groups[26].Value, m.Groups[27].Value, m.Groups[28].Value, m.Groups[29].Value, m.Groups[30].Value, m.Groups[31].Value, m.Groups[32].Value, m.Groups[33].Value) : ",,,,,,,";
#endif
            _seen = true;
        }
        #if HAS_COHMS
        public static string Line() => (_seen ? "1," + _vals : "0,,,,,,,,,,,,,,,,,,,,,")
#if HAS_COHRESCAND
            + ResTail()
#endif
            ;
#elif HAS_COHFB4
        public static string Line() => _seen ? "1," + _vals : "0,,,,,,,,,,,,,,,";
#else
        public static string Line() => _seen ? "1," + _vals : "0,,,,,,,,,";
#endif
    }
#endif

#if HAS_XCPRIOR
    /// <summary>XC-BUILD R10: the stage's counts-only log line, one per cycle with the stage ON: kept as written (the format is the Developer's; stored raw so no field is lost). Numbers only.</summary>
    private static class XcProbe
    {
        public const string Prefix = "Cross-cycle prior";
        public static int Lines;
        private static string _raw = "";
        public static void Reset() { Lines = 0; _raw = ""; }
        public static bool Set(string rendered)
        {
            if (!rendered.StartsWith(Prefix, StringComparison.Ordinal)) return false;
            Lines++;
            _raw = rendered.Substring(Prefix.Length).Trim().TrimEnd('.').Replace(' ', '|').Replace(",", "");   // "k=v|k=v": no commas, no spaces, so the row stays one CSV field
            return true;
        }
        public static string Row() => Lines == 0 ? "0,no-line" : Lines.ToString(CultureInfo.InvariantCulture) + "," + _raw;
    }

    /// <summary>XC-BUILD R13: the diagnostic sink the decoder calls once per tested template (numbers only: kind, S_E*, the prior's age in cycles, the argmax offsets). Written to --xc-probe-out under _qa-scratch.</summary>
    private sealed class XcProbeSink : ICrossCyclePriorProbe
    {
        public void OnTemplateTested(in CrossCycleTestRecord r)
        {
            var w = _xcProbe; if (w is null) return;
#if HAS_XCREMEDY
            lock (w) w.WriteLine(string.Join(",", r.CycleStart.ToString("yyMMdd_HHmmss", CultureInfo.InvariantCulture), r.Kind == CrossCycleKind.Live ? "live" : "shadow", r.SStar.ToString("R", CultureInfo.InvariantCulture),
                r.SP.ToString("R", CultureInfo.InvariantCulture), r.AgeCycles.ToString(CultureInfo.InvariantCulture), r.PriorFreqHz.ToString("R", CultureInfo.InvariantCulture), r.PriorDt.ToString("R", CultureInfo.InvariantCulture),
                r.PriorBatch.ToString(CultureInfo.InvariantCulture), r.Vetoed ? "1" : "0", r.OffsetHz.ToString("R", CultureInfo.InvariantCulture), r.OffsetS.ToString("R", CultureInfo.InvariantCulture)));
#else
            lock (w) w.WriteLine(string.Join(",", r.CycleStart.ToString("yyMMdd_HHmmss", CultureInfo.InvariantCulture), r.Kind == CrossCycleKind.Live ? "live" : "shadow", r.SStar.ToString("R", CultureInfo.InvariantCulture),
                r.AgeCycles.ToString(CultureInfo.InvariantCulture), r.OffsetHz.ToString("R", CultureInfo.InvariantCulture), r.OffsetS.ToString("R", CultureInfo.InvariantCulture)));
#endif
        }
    }
    private static StreamWriter? _xcOut, _xcProbe;
#endif

#if HAS_LATEROUND
    /// <summary>B-TOOL-2: the LATE-SUB round's R6 log line ("Late subtraction round: ..."), one per cycle with the setting ON. Aggregates only. Counts lines so a cycle with 0 or 2 is visible.</summary>
    private static class LateProbe
    {
        public static int Lines;
        public static string Outcome = "no-line", Buffer = "-", Fit = "", Refused = "", New = "", Published = "", FbEndMs = "", StartMs = "", ElapsedMs = "", EndMs = "", Batch = "", PublishMs = "";
        public static void Reset() { Lines = 0; Outcome = "no-line"; Buffer = "-"; Fit = Refused = New = Published = FbEndMs = StartMs = ElapsedMs = EndMs = Batch = PublishMs = ""; }
        private static readonly System.Text.RegularExpressions.Regex Rx = new(
            @"^Late subtraction round: outcome=([a-z0-9-]+), buffer=(\S+), fit=(\d+), refused=(-?\d+), new=(\d+), published=(\d+), fbEndMs=(-?\d+), startMs=(-?\d+), elapsedMs=(-?\d+), endMs=(-?\d+), batch=(\d+), batch5PublishMs=(-?\d+)\.$");
        public static bool Set(string rendered)
        {
            var m = Rx.Match(rendered);
            if (!m.Success) return false;            // the writer still counts it as a line seen only when it matches; a non-matching R6 line is reported by Unmatched
            Lines++;
            Outcome = m.Groups[1].Value; Buffer = m.Groups[2].Value; Fit = m.Groups[3].Value; Refused = m.Groups[4].Value; New = m.Groups[5].Value;
            Published = m.Groups[6].Value; FbEndMs = m.Groups[7].Value; StartMs = m.Groups[8].Value; ElapsedMs = m.Groups[9].Value; EndMs = m.Groups[10].Value;
            Batch = m.Groups[11].Value; PublishMs = m.Groups[12].Value;
            return true;
        }
        public static int Unmatched;
        public static string Row() => string.Join(",", Lines == 0 ? "no-line" : Outcome, Lines.ToString(CultureInfo.InvariantCulture), Buffer, Fit, Refused, New, Published, FbEndMs, StartMs, ElapsedMs, EndMs, Batch, PublishMs, Unmatched.ToString(CultureInfo.InvariantCulture));
    }
#endif

    /// <summary>The third-pass line the decoder logged for the cycle being decoded (one line per cycle in which pass 0 had decodes).</summary>
    private static class ThirdProbe
    {
        public static volatile bool Seen;
        public static string Outcome = "no-line";
        public static int NewDecodes, Fitted;
        public static long ElapsedMs;
        public static void Reset() { Seen = false; Outcome = "no-line"; NewDecodes = 0; Fitted = 0; ElapsedMs = 0; }
        private static readonly System.Text.RegularExpressions.Regex Rx = new(
            @"^Third pass: newDecodes=(\d+) elapsedMs=(\d+) outcome=(ran|skipped-no-new|skipped-abandoned|abandoned|failed) fittedSignals=(\d+)$");
        public static void Set(string rendered)
        {
            var m = Rx.Match(rendered);
            if (!m.Success) return;                  // anything else is not recorded (and never the text of a decode)
            // B-TOOL-2 (Architect ruling 73dc9036 s4): the FIRST line of the cycle is the third pass proper; with the LATE-SUB round ON a second
            // "Third pass:" line follows the fallback (the round's inner pass), and last-line-wins misread it as the third pass (log order R T F T C).
            if (Seen) return;
            NewDecodes = int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
            ElapsedMs = long.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture);
            Outcome = m.Groups[3].Value;
            Fitted = int.Parse(m.Groups[4].Value, CultureInfo.InvariantCulture);
            Seen = true;
        }
    }

    /// <summary>
    /// Spec amendment A4 (2026-10-18): proof, before any Deep-ON data is read, that the harness counts a batch-3 row as batch 3
    /// and never as batch 1 or 2. Synthetic decodes and synthetic WSJT-X lines; no decoder. Prints SELFTEST lines and returns 0 on PASS.
    /// </summary>
    private static List<string> ReadLinesShared(string path)
    {
        // The writers stay open (AutoFlush), so read with a share mode that tolerates them.
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        using var sr = new StreamReader(fs, Encoding.UTF8);
        var l = new List<string>();
        for (string? line; (line = sr.ReadLine()) is not null;) l.Add(line);
        return l;
    }

#if HAS_XCPRIOR
    /// <summary>XC-BUILD review: the Developer's managed detector on tasks written by QA's Python (CSV: path-to-f32-buffer, centre Hz, centre dt in WSJT-X's convention, 79 tones separated by spaces); writes S_E*, argmax Hz, argmax dt. Numbers only.</summary>
    private static int XcVerify(string tasks, string outPath)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        using var w = new StreamWriter(outPath, false, new UTF8Encoding(false));
        w.WriteLine("row,s_e_star,argmax_hz,argmax_dt");
        int row = 0;
        foreach (var line in File.ReadLines(tasks))
        {
            var p = line.Split(',');
            if (p.Length < 4) continue;
            var raw = File.ReadAllBytes(p[0]);
            var pcm = new float[raw.Length / 4];
            Buffer.BlockCopy(raw, 0, pcm, 0, raw.Length);
            var tones = p[3].Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(x => byte.Parse(x, CultureInfo.InvariantCulture)).ToArray();
            var r = OpenWSFZ.Ft8.Dsp.CrossCycleTemplateDetector.Search(pcm, double.Parse(p[1], CultureInfo.InvariantCulture), double.Parse(p[2], CultureInfo.InvariantCulture), tones);
            w.WriteLine(string.Join(",", row++, r.SStar.ToString("R", CultureInfo.InvariantCulture), r.FreqHz.ToString("R", CultureInfo.InvariantCulture), r.Dt.ToString("R", CultureInfo.InvariantCulture)));
        }
        Console.WriteLine("xc-verify rows=" + row);
        return 0;
    }
#endif

    private static int SelfTestBatch3()
    {
        string dir = Path.Combine(Path.GetTempPath(), "r81_selftest_batch3_" + Environment.ProcessId);
        Directory.CreateDirectory(dir);
        try
        {
            string tb = Path.Combine(dir, "testb.csv"), mb = Path.Combine(dir, "matchedbatch.csv"), mo = Path.Combine(dir, "matched.csv");
            _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            _matchedBatch = new StreamWriter(mb, false, new UTF8Encoding(false)) { AutoFlush = true };
            _matched = new StreamWriter(mo, false, new UTF8Encoding(false)) { AutoFlush = true };
            const string S = "261001_000000";
            // WSJT-X heard four messages in this synthetic cycle; OWS has one per batch plus one OWS-only third-pass row.
            _wsjtx[S] = new() { (-10, 1000, "AAA BBB CC11"), (-12, 1500, "DDD EEE FF22"), (-18, 2000, "GGG HHH JJ33"), (-5, 2500, "ZZZ ZZZ ZZ99") };
            DecodeResult R(int snr, int f, string m) => new("000000", snr, 0.1, f, m);
            var b1 = new[] { R(-10, 1000, "AAA BBB CC11") };
            var b2 = new[] { R(-12, 1500, "DDD EEE FF22") };
            var b3 = new[] { R(-18, 2000, "GGG HHH JJ33"), R(-20, 3000, "QQQ RRR SS44") };   // 1 matched, 1 OWS-only
            ScoreTestB("selftest", S, b1, b2, b3);
            var tbl = ReadLinesShared(tb).ToList();
            bool ok = true;
            void Check(string what, bool cond) { Console.WriteLine("SELFTEST " + (cond ? "PASS" : "FAIL") + " " + what); ok &= cond; }
            // rows: run,stamp,kind,band,n,corroborated. Band of snr: -10 -> B, -12 -> C, -18 -> D, -20 -> D.
            Check("b1 row B: n=1 corroborated=1", tbl.Contains("selftest," + S + ",b1,B,1,1"));
            Check("b2 row C: n=1 corroborated=1", tbl.Contains("selftest," + S + ",b2,C,1,1"));
            Check("b3 row D: n=2 corroborated=1 (one matched, one OWS-only)", tbl.Contains("selftest," + S + ",b3,D,2,1"));
            Check("batch 3 never appears under b1 or b2 in band D", tbl.Contains("selftest," + S + ",b1,D,0,0") && tbl.Contains("selftest," + S + ",b2,D,0,0"));
            string mbl = ReadLinesShared(mb).Last();
            Check("matched-batch-out tags the WSJT-X lines 0:1, 1:2, 2:3 (the third-pass match is 3)", mbl == S + ",0:1;1:2;2:3");
            Check("the unmatched WSJT-X line (index 3) is absent from matched-batch-out", !mbl.Contains("3:"));
            Check("matched-out lists the three matched WSJT-X lines", ReadLinesShared(mo).Last() == S + ",0;1;2");
            // Old modes: b3 absent => exactly the old 2-kind output (no b3 row at all).
            _testB.Dispose(); _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            ScoreTestB("selftest", S, b1, b2);
            Check("without a batch 3 (older modes) no b3 row is written", !ReadLinesShared(tb).Any(x => x.Contains(",b3,")));
            // Normal arm: an EMPTY batch 3 writes b3 rows with n=0 and never a match.
            _testB.Dispose(); _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            ScoreTestB("selftest", S, b1, b2, Array.Empty<DecodeResult>());
            var b3rows = ReadLinesShared(tb).Where(x => x.Contains(",b3,")).ToList();
            Check("an EMPTY batch 3 (Normal / skipped) writes b3 rows with n=0 and corroborated=0", b3rows.Count == 4 && b3rows.All(x => x.EndsWith(",0,0")));
            // L1' build (F5): batch 5 is its OWN kind (b5), never folded into b1-b4, and tagged 5 in matched-batch-out.
            _testB.Dispose(); _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            _matchedBatch.Dispose(); _matchedBatch = new StreamWriter(mb, false, new UTF8Encoding(false)) { AutoFlush = true };
            var b4e = Array.Empty<DecodeResult>();
            var b5 = new[] { R(-14, 2500, "ZZZ ZZZ ZZ99"), R(-16, 3500, "UUU VVV WW55") };   // 1 matched (the last WSJT-X line), 1 OWS-only
            ScoreTestB("selftest", S, b1, b2, b3, b4e, b5);
            var tb5 = ReadLinesShared(tb).ToList();
            Check("a batch 5 writes b5 rows: band C n=1 corroborated=1, band D n=1 corroborated=0", tb5.Contains("selftest," + S + ",b5,C,1,1") && tb5.Contains("selftest," + S + ",b5,D,1,0"));
            Check("batch 5 never appears under b1-b4 (b4 rows empty)", tb5.Contains("selftest," + S + ",b4,A,0,0") && tb5.Count(x => x.Contains(",b4,")) == 4);
            Check("matched-batch-out tags the batch-5 match as 5", ReadLinesShared(mb).Last().Contains("3:5"));
            _testB.Dispose(); _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            ScoreTestB("selftest", S, b1, b2, b3, b4e);
            Check("without a batch 5 no b5 row is written (older output byte-identical)", !ReadLinesShared(tb).Any(x => x.Contains(",b5,")));
            // XC-BUILD: batch 6 (the cross-cycle template stage) is its OWN kind (b6), never folded into b1-b5, and tagged 6 in matched-batch-out.
            _testB.Dispose(); _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            _matchedBatch.Dispose(); _matchedBatch = new StreamWriter(mb, false, new UTF8Encoding(false)) { AutoFlush = true };
            var b6 = new[] { R(-14, 2500, "ZZZ ZZZ ZZ99"), R(-16, 3500, "UUU VVV WW55") };   // 1 matched (the last WSJT-X line), 1 OWS-only
            ScoreTestB("selftest", S, b1, b2, b3, b4e, b5Empty(), b6);
            var tb6 = ReadLinesShared(tb).ToList();
            Check("a batch 6 writes b6 rows: band C n=1 corroborated=1, band D n=1 corroborated=0", tb6.Contains("selftest," + S + ",b6,C,1,1") && tb6.Contains("selftest," + S + ",b6,D,1,0"));
            Check("batch 6 never appears under b1-b5 (b5 rows empty)", tb6.Contains("selftest," + S + ",b5,A,0,0") && tb6.Count(x => x.Contains(",b5,")) == 4);
            Check("matched-batch-out tags the batch-6 match as 6", ReadLinesShared(mb).Last().Contains("3:6"));
            _testB.Dispose(); _testB = new StreamWriter(tb, false, new UTF8Encoding(false)) { AutoFlush = true };
            ScoreTestB("selftest", S, b1, b2, b3, b4e, b5Empty());
            Check("without a batch 6 no b6 row is written (older output byte-identical)", !ReadLinesShared(tb).Any(x => x.Contains(",b6,")));
            static IReadOnlyList<DecodeResult> b5Empty() => Array.Empty<DecodeResult>();
            // The third-pass log-line parser.
            ThirdProbe.Reset();
            ThirdProbe.Set("Third pass: newDecodes=2 elapsedMs=1234 outcome=ran fittedSignals=3");
            Check("third-pass line parsed", ThirdProbe.Seen && ThirdProbe.Outcome == "ran" && ThirdProbe.NewDecodes == 2 && ThirdProbe.ElapsedMs == 1234 && ThirdProbe.Fitted == 3);
            ThirdProbe.Reset();
            ThirdProbe.Set("Third pass: newDecodes=0 elapsedMs=0 outcome=skipped-no-new fittedSignals=0");
            Check("third-pass skip line parsed", ThirdProbe.Seen && ThirdProbe.Outcome == "skipped-no-new");
            ThirdProbe.Reset();
            ThirdProbe.Set("Third pass: something else entirely");
            Check("a non-matching line is ignored", !ThirdProbe.Seen);
            // B-TOOL-2: the cycle's FIRST Third pass line wins; a second (the round's inner) line must not overwrite it.
            ThirdProbe.Reset();
            ThirdProbe.Set("Third pass: newDecodes=2 elapsedMs=1234 outcome=ran fittedSignals=3");
            ThirdProbe.Set("Third pass: newDecodes=9 elapsedMs=99 outcome=abandoned fittedSignals=8");
            Check("the first third-pass line of a cycle wins (the round's inner line is ignored)", ThirdProbe.Outcome == "ran" && ThirdProbe.NewDecodes == 2 && ThirdProbe.Fitted == 3 && ThirdProbe.ElapsedMs == 1234);
#if HAS_LATEROUND
            LateProbe.Reset();
            bool lateOk = LateProbe.Set("Late subtraction round: outcome=ran, buffer=R3, fit=12, refused=1, new=3, published=2, fbEndMs=2100, startMs=2200, elapsedMs=690, endMs=2890, batch=5, batch5PublishMs=3010.");
            Check("the round's R6 line is parsed, every field", lateOk && LateProbe.Lines == 1 && LateProbe.Outcome == "ran" && LateProbe.Buffer == "R3" && LateProbe.Fit == "12" && LateProbe.Refused == "1" && LateProbe.New == "3" && LateProbe.Published == "2" && LateProbe.FbEndMs == "2100" && LateProbe.StartMs == "2200" && LateProbe.ElapsedMs == "690" && LateProbe.EndMs == "2890" && LateProbe.Batch == "5" && LateProbe.PublishMs == "3010");
            LateProbe.Reset();
            Check("a skipped round line (buffer -, fbEndMs, publish -1) is parsed", LateProbe.Set("Late subtraction round: outcome=skipped-normal-depth, buffer=-, fit=0, refused=0, new=0, published=0, fbEndMs=2100, startMs=2100, elapsedMs=0, endMs=2100, batch=5, batch5PublishMs=-1.") && LateProbe.Outcome == "skipped-normal-depth");
            LateProbe.Reset();
            Check("a non-matching R6 line is not recorded", !LateProbe.Set("Late subtraction round: something else") && LateProbe.Lines == 0 && LateProbe.Row().StartsWith("no-line,0,"));
#endif
            Console.WriteLine("SELFTEST " + (ok ? "ALL PASS" : "FAILED"));
            return ok ? 0 : 1;
        }
        finally
        {
            _testB?.Dispose(); _matchedBatch?.Dispose(); _matched?.Dispose(); _fbDump?.Dispose(); _ncDump?.Dispose(); _implDump?.Dispose(); _stageOut?.Dispose();
            try { Directory.Delete(dir, true); } catch (IOException) { }
        }
    }
#endif

#if HAS_TWOSTAGE
    /// <summary>
    /// Two-stage decode (Ft8Decoder.DecodeTwoStageAsync): records the time to batch 1 (from just before the call to
    /// the moment the decoder hands batch 1 to the publish callback: the hand-off S2 measures), the whole-call time
    /// (batch 2 available), and both batches' counts.
    /// </summary>
    private static async Task DecodeTwo(Ft8Decoder d, float[] pcm, DateTime cycleStart, StreamWriter csv,
                                        string run, string stratum, string stamp, int seq, string flag = "ON")
    {
        string exc = "";
        int n1 = -1, n2 = -1;
        double tb1 = -1;
        SubfeasProbe.Reset();
        var sw = Stopwatch.StartNew();
        try
        {
            IReadOnlyList<DecodeResult>? b1 = null;
            var b2 = await d.DecodeTwoStageAsync(pcm, cycleStart, null, batch =>
            {
                tb1 = sw.Elapsed.TotalMilliseconds;
                b1 = batch;
                return Task.CompletedTask;
            });
            n1 = b1?.Count ?? -1;
            n2 = b2.Count;
            if (b1 is not null) WriteOutcomes(stamp, "b1", b1);
            WriteOutcomes(stamp, "b2", b2);
            if (b1 is not null) ScoreTestB(run, stamp, b1, b2);
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        // Written BEFORE the run-csv row, so a crash between the two leaves an orphan the orchestrator's repair drops.
        _abandon?.WriteLine(string.Join(",", stamp, SubfeasProbe.Ran ? "1" : "0", SubfeasProbe.Abandoned ? "1" : "0",
            SubfeasProbe.Contained ? "1" : "0"));
        csv.WriteLine(string.Join(",", run, stratum, stamp, seq.ToString(CultureInfo.InvariantCulture), flag,
            sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture),
            (n1 < 0 ? -1 : n1 + Math.Max(0, n2)).ToString(CultureInfo.InvariantCulture), exc,
            tb1.ToString("F1", CultureInfo.InvariantCulture),
            n1.ToString(CultureInfo.InvariantCulture), n2.ToString(CultureInfo.InvariantCulture)));
    }

    /// <summary>
    /// One log line the offline replay's row V2 reads: the flag and the settings AS THE DECODER OBJECT HOLDS THEM (the
    /// flag is the public <c>SubtractionEnabled</c> getter; the thread count is the configured value and what
    /// <c>SubtractionThreads.Resolve</c> makes of it on this machine), not merely as passed on the command line.
    /// </summary>
    private static void Readback(Ft8Decoder d, ReplayLog log, string tag, string threadsNote)
    {
        string resolved = "n/a";
#if HAS_MAXTHREADS
        if (int.TryParse(threadsNote, NumberStyles.Integer, CultureInfo.InvariantCulture, out int t))
            resolved = SubtractionThreads.Resolve(t, Environment.ProcessorCount, out _).ToString(CultureInfo.InvariantCulture);
#endif
        log.Raw($"# readback {tag} subtractionEnabled={d.SubtractionEnabled} threadsConfigured={threadsNote} " +
                $"threadsResolved={resolved} cores={Environment.ProcessorCount} clock={ClockMode} nhard={OsdNhardMax} " +
                $"kMinScorePass2={KMinScorePass2} osdCorrThreshold={OsdCorrThreshold.ToString("F2", CultureInfo.InvariantCulture)} " +
                $"shim={Ft8Decoder.LoadedShimVersion}"
#if HAS_OSDSIGNFIX
                + $" osdSignFixSet={OsdSignFix} osdSignFixRead={d.GetOsdSignFix()}"
#endif
#if HAS_THIRDPASS
                + $" decodingDepth={d.DecodingDepth}"
#endif
#if HAS_COHFB
                + $" cohfb={d.CoherentFallbackEnabled}"
#endif
#if HAS_COHMS
                + $" cohms={d.CoherentFallbackMultiSet}"
#endif
#if HAS_COHAUDIO
                + $" cohaudio={d.CoherentFallbackAudio}"
#endif
#if HAS_UNGATED
                + $" ungated={d.CoherentFallbackResidualUngated}"
#endif
#if HAS_LATEROUND
                + $" lateround={d.LateSubtractionRound}"
#endif
#if HAS_CQAP
                + $" cqap={d.CqApEnabled}"
#endif
#if HAS_COHRESCAND
                + $" cohrescand={d.CoherentFallbackResidualCandidates}"
#if HAS_XCPRIOR
                + $" xcprior={d.CrossCyclePrior} xcshadow={d.CrossCyclePriorShadow} xcte={d.CrossCyclePriorThreshold.ToString("R", CultureInfo.InvariantCulture)}"
#if HAS_XCREMEDY
                + $" xcveto={d.CrossCyclePriorColocationVeto} xctp={d.CrossCyclePriorParityThreshold.ToString("R", CultureInfo.InvariantCulture)}"
#endif
#endif
#endif
#if HAS_LRFULL
                + $" lrx1={d.DiagThirdRunUngated} lrx2={d.DiagLateFallbackOnResidual}"
#endif
#if HAS_LRBUILD
                + $" lrx1={d.CoherentFallbackResidualCandidatesUngated} lrx2={d.LateRoundFallback}"
#endif
#if HAS_LEAN
                + $" engine={d.Engine} leanThreads={d.LeanThreads} effort={d.Effort}"
#endif
                );
    }
#endif

    private static void SetFlag(Ft8Decoder d, bool on)
    {
#if HAS_SUBFEAS
        d.SetSubtractionEnabled(on);
#else
        if (on) throw new InvalidOperationException("this build has no subtraction flag");
#endif
    }

    private static HashSet<string> LoadDone(string csvPath)
    {
        var s = new HashSet<string>();
        if (!File.Exists(csvPath)) return s;
        foreach (var line in File.ReadLines(csvPath).Skip(1))
        {
            var p = line.Split(',');
            if (p.Length >= 5) s.Add(p[2] + "|" + p[4]);
        }
        return s;
    }

    private static float[] ReadWav(string path)
    {
        byte[] b = File.ReadAllBytes(path);
        if (b.Length < 44 || Encoding.ASCII.GetString(b, 0, 4) != "RIFF" || Encoding.ASCII.GetString(b, 8, 4) != "WAVE")
            throw new InvalidDataException("not a RIFF/WAVE file");
        int pos = 12, channels = 0, rate = 0, bits = 0, dataOff = -1, dataLen = 0;
        while (pos + 8 <= b.Length)
        {
            string id = Encoding.ASCII.GetString(b, pos, 4);
            int len = BitConverter.ToInt32(b, pos + 4);
            if (id == "fmt ")
            {
                channels = BitConverter.ToInt16(b, pos + 10);
                rate = BitConverter.ToInt32(b, pos + 12);
                bits = BitConverter.ToInt16(b, pos + 22);
            }
            else if (id == "data") { dataOff = pos + 8; dataLen = len; break; }
            pos += 8 + len + (len & 1);
        }
        // per-file assertions (spec R0): 12 kHz mono 16-bit, exactly 180 000 samples
        if (channels != 1 || rate != SampleRateHz || bits != 16 || dataOff < 0 || dataLen / 2 != PcmSamples)
            throw new InvalidDataException($"WAV assertion failed (ch={channels} rate={rate} bits={bits} samples={dataLen / 2})");
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++)
            pcm[i] = BitConverter.ToInt16(b, dataOff + 2 * i) / 32768f;
        return pcm;
    }

    private static DateTime StampToUtc(string stamp) =>
        DateTime.SpecifyKind(DateTime.ParseExact(stamp, "yyMMdd_HHmmss", CultureInfo.InvariantCulture), DateTimeKind.Utc);

    private static Dictionary<string, string> ParseArgs(string[] args)
    {
        var d = new Dictionary<string, string>();
        for (int i = 0; i + 1 < args.Length; i += 2)
        {
            if (!args[i].StartsWith("--")) throw new ArgumentException("bad arg");
            d[args[i][2..]] = args[i + 1];
        }
        return d;
    }

    private static string Req(Dictionary<string, string> a, string k) =>
        a.TryGetValue(k, out var v) ? v : throw new ArgumentException("missing --" + k);

    private sealed class WallClock : IClock { public DateTime UtcNow => DateTime.UtcNow; }

    // ---------------------------------------------------------------- text-safe log sink
    private sealed class ReplayLog : IDisposable
    {
        private readonly StreamWriter _w;
        private readonly object _lock = new();
        public ReplayLog(string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
            _w = new StreamWriter(path, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        }
        public void Raw(string s) { lock (_lock) _w.WriteLine(s); }
        public void Line(string level, string s) { lock (_lock) _w.WriteLine(DateTime.UtcNow.ToString("O") + " [" + level + "] " + s); }
        public void Dispose() { lock (_lock) _w.Dispose(); }
    }

    private sealed class ReplayLogger<T> : ILogger<T>
    {
        // Rendered text is only ever written for these two templates: both carry aggregates only.
        private const string SubfeasPrefix = "Sub-feas residual pass: residualDecodes=";
        private const string CyclePrefix = "Cycle {Time}: {Count} decode(s) found";
        private const string ThirdPrefix = "Third pass: newDecodes=";
        private readonly ReplayLog _log;
        public ReplayLogger(ReplayLog log) { _log = log; }
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Information || (logLevel == LogLevel.Debug && _implDump is not null);

        public void Log<TState>(LogLevel level, EventId eventId, TState state, Exception? exception,
                                Func<TState, Exception?, string> formatter)
        {
            if (level < LogLevel.Information)
            {
                // GAP-RELOCATE: ONLY the plausibility-drop Debug line is read, and only when --impl-dump (a scratch file) is given.
                if (_implDump is not null && level == LogLevel.Debug && state is IReadOnlyList<KeyValuePair<string, object?>> dkv)
                {
                    string tpl = "", msg = "";
                    foreach (var p in dkv) { if (p.Key == "{OriginalFormat}") tpl = p.Value?.ToString() ?? ""; else if (p.Key == "Message") msg = p.Value?.ToString() ?? ""; }
                    if (tpl.StartsWith("Cycle {Time}: filtered implausible message", StringComparison.Ordinal)) ImplEvent("D", msg.Replace('	', ' '));
                }
                return;
            }
            string template = "";
            if (state is IReadOnlyList<KeyValuePair<string, object?>> kv)
                foreach (var p in kv) if (p.Key == "{OriginalFormat}") template = p.Value?.ToString() ?? "";

            // Per-cycle residual-pass state for the offline replay's row V6 (Amendment 1): the aggregate line says whether
            // THIS cycle's pass was deadline-abandoned; DecodeTwo resets the probe before a call and reads it after.
            if (template.StartsWith(SubfeasPrefix, StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string t = formatter(state, exception);
                SubfeasProbe.Set(t.Contains("deadlineAbandoned=True", StringComparison.OrdinalIgnoreCase),
                                 t.Contains("containedException=True", StringComparison.OrdinalIgnoreCase));
                ImplEvent("M	S");
            }
#if HAS_THIRDPASS
            if (template.StartsWith(ThirdPrefix, StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string rendered = formatter(state, exception);
                ThirdProbe.Set(rendered);
                ImplEvent("M	T");
                _log.Line(level.ToString(), rendered);   // aggregate-only template: counts, ms, a fixed outcome word
                return;
            }
#endif
#if HAS_XCPRIOR
            // XC-BUILD R10: the cross-cycle stage's counts-only line (no text, no callsign)
            if (template.StartsWith(XcProbe.Prefix, StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string rendered = formatter(state, exception);
                XcProbe.Set(rendered);
                ImplEvent("M\tX");
                _log.Line(level.ToString(), rendered);
                return;
            }
#endif
#if HAS_LATEROUND
            // B-TOOL-2: the LATE-SUB round's R6 line (aggregates only: a fixed outcome word, a buffer label, counts and ms)
            if (template.StartsWith("Late subtraction round: outcome=", StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string rendered = formatter(state, exception);
                if (!LateProbe.Set(rendered)) LateProbe.Unmatched++;
                ImplEvent("M	L");
                _log.Line(level.ToString(), rendered);
                return;
            }
#endif
#if HAS_COHFB
            if (template.StartsWith("Coherent fallback: eligible=", StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string rendered = formatter(state, exception);
                CohProbe.Set(rendered);
                ImplEvent("M	C");
                _log.Line(level.ToString(), rendered);   // aggregate-only template: counts and ms
                return;
            }
#endif
#if HAS_CQAP
            // CQ-AP: the per-cycle 'cq-ap: attempts=N decodes=M' line (counts only; the decoder writes it only while the flag is ON).
            if (template.StartsWith("Cycle {Time}: cq-ap:", StringComparison.Ordinal) && level == LogLevel.Information)
            {
                _log.Line(level.ToString(), formatter(state, exception));
                return;
            }
#endif
#if HAS_LRFULL
            // LR-FULL: the two per-cycle 'Diagnostic X1 / X2' lines (counts only, the decoder writes them only while its switch is ON).
            if ((template.StartsWith("Diagnostic X1 ", StringComparison.Ordinal) || template.StartsWith("Diagnostic X2 ", StringComparison.Ordinal)) && level == LogLevel.Information)
            {
                _log.Line(level.ToString(), formatter(state, exception));
                return;
            }
#endif
#if HAS_LRBUILD
            // LR-BUILD D6: the per-cycle counts-only 'Late provenance:' line (written only while either key is ON).
            if (template.StartsWith("Late provenance: ", StringComparison.Ordinal) && level == LogLevel.Information)
            {
                _log.Line(level.ToString(), formatter(state, exception));
                return;
            }
#endif
#if HAS_LEAN
            // DR-2 step 2d: the lean engine's per-cycle 'lean:' line (counts and milliseconds only, HK-037); one row per cycle goes to --lean-out.
            if (template.StartsWith("Cycle {Time}: lean:", StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string rendered = formatter(state, exception);
                LeanRow(rendered);
                _log.Line(level.ToString(), rendered);
                return;
            }
#endif
            if (template.StartsWith(SubfeasPrefix, StringComparison.Ordinal) && level == LogLevel.Information
                || template.StartsWith(CyclePrefix, StringComparison.Ordinal))
            {
                _log.Line(level.ToString(), formatter(state, exception));
                return;
            }
            if (level >= LogLevel.Warning)
            {
                // Template only (placeholders unfilled) + exception TYPE. Never the rendered text.
                _log.Line(level.ToString(), "WARN-TEMPLATE " + template + (exception is null ? "" : " exc=" + exception.GetType().Name));
            }
            // other Information lines: dropped
        }
    }
}
