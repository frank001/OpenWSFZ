using System.Collections.Concurrent;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-FALLBACK (A' step 3) Stage 2 as amended by step 4 (spec section 14): the product wiring, behind
/// <c>decoder.coherentFallbackEnabled</c> (default true since 2026-10-22; a bare Ft8Decoder is still OFF until the daemon sets it). Requirements R6-triple-prime / R7-triple-prime (the fallback starts only after the
/// cycle's last ordinary batch has been handed off and publishes as a batch of its own: 4 on Deep, 3 on Normal, only if non-empty; shared
/// budget; abandon never queue), R6'' (one output per payload, non-edge first), R12' (the log line and its step 4 fields), R11 (the path
/// tag), R13 (flag OFF = nothing changes), R9 (the early decode never runs it). Order is asserted from a recorded event list, never from
/// timing. The native calls are faked (scripted per cycle) exactly as in <see cref="ThirdPassDeepTests"/>; the fallback's own numerical work
/// is covered by the native self-test and <see cref="CoherentFallbackStage2NativeTests"/>, the parallel scheduling by
/// <see cref="CoherentFallbackParallelRunnerTests"/>.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, order, identity and aggregates.</para>
/// </summary>
public sealed class CoherentFallbackWiringTests
{
    private static readonly DateTime CycleStart = new(2026, 10, 20, 12, 0, 0, DateTimeKind.Utc);

    private static Ft8NativeResult Msg(string message, int freqHz = 1500, float dt = 0.2f, int snr = -10)
        => new() { FreqHz = freqHz, Dt = dt, Snr = snr, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    /// <summary>A scripted fallback row: <paramref name="id"/> is the payload (and the key into <see cref="FallbackInterop.Texts"/>).</summary>
    private static CohFallbackRow Row(int id, CohFallbackState state = CohFallbackState.NewGated, bool edge = false,
                                      float freq = 1000f, int snr = -21)
    {
        var payload = new byte[12];
        payload[0] = (byte)id;
        return new CohFallbackRow(freq, 0.3f, freq + 0.3f, 0.31f, 0, edge, state, snr, state >= CohFallbackState.GatedOut ? 12.0 : double.NaN, payload);
    }

    private static CohFallbackStats Stats(int eligible, int attempted, int crcOk, int f1b, int gated, int abandoned, int edge = 0, double totalMs = 123.4)
        => new(eligible + 5, 5, 0, eligible, attempted, crcOk, crcOk, f1b, gated, abandoned, edge, 1, 2, 3, totalMs);

    /// <summary>
    /// A scripted native interop. DecodeAll answers by call number (1 = pass 0, 2 = residual, 3 = third pass); the fallback methods are
    /// scripted per cycle and every call is recorded, in order, together with the batches the test's callback receives.
    /// </summary>
    private sealed class FallbackInterop(Ft8NativeResult[][] decodes, CohFallbackRunResult? run) : IFt8NativeInterop
    {
        private readonly object _gate = new();
        private int _ordinaryActive;
        public int MaxDecodePasses => 2;
        public int DecodeAllCallCount { get; private set; }
        public int AnalyticCallCount { get; private set; }

        public List<string> Calls { get; } = [];
        public int SnapshotCalls, RunCalls, UnpackCalls;
        public int DecodeAllThreadId = -1, SnapshotThreadId = -1;
        public double? RunBudgetMs;
        public int? RunWorkers;
        public float[]? RunPcm;

        /// <summary>COH-FB-AUDIO: the PCM of every fallback run, in call order.</summary>
        public List<float[]> RunPcms { get; } = [];

        /// <summary>COH-FB-AUDIO: the array pass 0 decoded, which is the cycle's normalised audio (the one the original-audio fallback must be handed).</summary>
        public float[]? FirstDecodePcm;

        /// <summary>COH-FB-AUDIO: when set, the result of the n-th fallback run (1-based) instead of <c>run</c>.</summary>
        public Func<int, CohFallbackRunResult?>? RunByCall { get; init; }

        /// <summary>How many ordinary native calls (decode, analytic, fit) were in flight when the fallback run was called.</summary>
        public int OrdinaryActiveAtRun = -1;

        public Exception? RunThrows { get; init; }

        /// <summary>payload id (first byte) to message text for the unpack; a missing id does not decode.</summary>
        public Dictionary<int, string> Texts { get; init; } = new();

        /// <summary>Records a non-native event (a delivered batch) in <see cref="Calls"/>, in order with the native calls.</summary>
        public void Note(string what) { lock (_gate) Calls.Add(what); }

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            int n;
            lock (_gate) { n = ++DecodeAllCallCount; Calls.Add("decode" + n); _ordinaryActive++; }
            try
            {
                if (n == 1) { DecodeAllThreadId = Environment.CurrentManagedThreadId; FirstDecodePcm = pcm; }
                return n <= decodes.Length ? decodes[n - 1] : [];
            }
            finally { lock (_gate) _ordinaryActive--; }
        }

        public byte[]? CohFallbackSnapshot()
        {
            lock (_gate) { SnapshotCalls++; Calls.Add("snapshot"); }
            SnapshotThreadId = Environment.CurrentManagedThreadId;
            return [1, 2, 3, 4];
        }

        /// <summary>COH-MULTISET: the once-per-cycle flag value the decoder passed, one entry per run.</summary>
        public List<bool> MultiSetArgs { get; } = [];

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
        {
            lock (_gate) MultiSetArgs.Add(multiSet);
            return CohFallbackRun(pcm, snapshot, budgetMs, workers, ct);
        }

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        {
            lock (_gate) { RunCalls++; Calls.Add("run"); RunBudgetMs = budgetMs; RunWorkers = workers; RunPcm = pcm; RunPcms.Add(pcm); OrdinaryActiveAtRun = _ordinaryActive; }
            if (RunThrows is not null) throw RunThrows;
            return RunByCall is { } byCall ? byCall(RunCalls) : run;
        }

        public string? CohFallbackUnpack(byte[] payload)
        {
            lock (_gate) { UnpackCalls++; Calls.Add("unpack"); }
            return Texts.TryGetValue(payload[0], out var t) ? t : null;
        }

        public byte[] EncodeMessage(string message)
        {
            var tones = new byte[79];
            Ft8LibInterop.EncodeMessage(message, tones);
            return tones;
        }

        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        {
            lock (_gate) { AnalyticCallCount++; Calls.Add("analytic"); }
            return (new float[pcm.Length], new float[pcm.Length]);
        }

        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        {
            var shat = new float[180_000];
            if (ShatValue != 0f) Array.Fill(shat, ShatValue);
            return (0, shat);
        }

        /// <summary>coh-fb-residual: the constant every fitted signal's subtraction buffer holds (0 = the residual equals the input).</summary>
        public float ShatValue { get; init; }

        public int[] GetLastPassCounts(int maxPasses) => new int[maxPasses];
        public int[] GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float GetLastNoiseFloorDb() => 0f;
        public int GetHashTableRejectCount() => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount() => 0;
        public int GetH12DivergentCount() => 0;
        public int GetH12SuppressedCount() => 0;

        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);

        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];

        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
            => (Array.Empty<float>(), Array.Empty<float>());
    }

    private sealed class LineLog : ILogger<Ft8Decoder>
    {
        private readonly ConcurrentQueue<string> _q = new();
        public List<string> Lines => _q.ToList();
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => _q.Enqueue(formatter(state, exception));
    }

    private static Ft8Decoder Build(IFt8NativeInterop interop, DecodingDepth depth, bool fallback, ILogger<Ft8Decoder>? log = null,
                                    bool subtraction = true)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop: interop);
        d.SetSubtractionEnabled(subtraction);
        d.SetDecodingDepth(depth);
        d.SetCoherentFallbackEnabled(fallback);
        return d;
    }

    private sealed record Delivered(int Batch, DecodeResult[] Results)
    {
        public string[] Messages => Results.Select(r => r.Message).ToArray();
    }

    private static async Task<List<Delivered>> RunStaged(Ft8Decoder decoder, FallbackInterop? interop = null, Action<int>? onBatch = null, float[]? pcm = null)
    {
        var got = new List<Delivered>();
        await decoder.DecodeStagedAsync(pcm ?? LoudPcm(), CycleStart, null, (n, b) =>
        {
            got.Add(new Delivered(n, b.ToArray()));
            interop?.Note("batch" + n);
            onBatch?.Invoke(n);
            return Task.CompletedTask;
        });
        return got;
    }

    private static readonly Ft8NativeResult[] Pass0 = [Msg("Q1ABC Q1XYZ JO33"), Msg("Q1GHI Q1JKL FN20", 1800)];
    private static readonly Ft8NativeResult[] Resid = [Msg("Q1DEF Q1UVW EN37", 2100)];
    private static readonly Ft8NativeResult[] Third = [Msg("Q1MNO Q1PQR IO91", 2400)];

    private static CohFallbackRunResult OneNew(int id = 1) => new(Stats(1, 1, 1, 1, 1, 0), [Row(id)]) { Workers = 4 };

    // ── COH-FB-AUDIO: which audio the fallback reads (decoder.coherentFallbackAudio) ──────────────────────────────

    private static Ft8Decoder BuildWithAudio(IFt8NativeInterop interop, DecodingDepth depth, CoherentFallbackAudio? mode, ILogger<Ft8Decoder>? log = null)
    {
        var d = Build(interop, depth, true, log);
        if (mode is { } m) d.SetCoherentFallbackAudio(m);
        return d;
    }

    private static float[] Normalised() => Ft8Decoder.NormalisePcm(LoudPcm(), 0.20f /* Ft8Decoder.PcmNormalisationTargetRms */);

    private static string AudioField(LineLog log)
        => Regex.Match(log.Lines.Single(l => l.StartsWith("Coherent fallback:")), @"audio=([a-z0-9()\-]+)(?:,|\.)").Groups[1].Value;

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: a bare decoder starts at Original; the setter and getter round-trip all three values")]
    public void Audio_BareDecoderOriginal_RoundTrips()
    {
        var d = Build(new FallbackInterop([Pass0], OneNew()), DecodingDepth.Deep, true);
        d.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Original);
        foreach (var m in Enum.GetValues<CoherentFallbackAudio>())
        {
            d.SetCoherentFallbackAudio(m);
            d.CoherentFallbackAudio.Should().Be(m);
        }
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Original - the fallback is handed the SAME reference as the cycle's normalised audio, the line says audio=original and has no counts")]
    public async Task Audio_Original_SameReference()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Deep, CoherentFallbackAudio.Original, log));

        interop.RunPcms.Should().HaveCount(1);
        interop.FirstDecodePcm.Should().NotBeNull();
        interop.RunPcms[0].Should().BeSameAs(interop.FirstDecodePcm, "pass 0 decodes normalisedPcm, and Original hands the fallback that very array");
        var line = log.Lines.Single(l => l.StartsWith("Coherent fallback:"));
        line.Should().EndWith(", audio=original.");
        line.Should().NotContain("fromOriginal");
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Original reads the same values as the cycle's normalised audio on a loud buffer")]
    public async Task Audio_Original_Values()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Deep, CoherentFallbackAudio.Original));
        interop.RunPcms.Single().Should().Equal(Normalised());
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Residual, third pass ran - the fallback reads the THIRD pass's buffer (audio=residual3)")]
    public async Task Audio_Residual_ThirdPassRan_ReadsThirdPassBuffer()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Deep, CoherentFallbackAudio.Residual, log));

        AudioField(log).Should().Be("residual3");
        // pass 0 had 2 signals (residual buffer = x - 0.02); the third pass fits the residual pass's 1 new signal: x - 0.03.
        var orig = Normalised();
        interop.RunPcms.Single()[100].Should().BeApproximately(orig[100] - 0.03f, 1e-5f);
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Residual, third pass skipped (residual pass found nothing new) - the fallback reads the RESIDUAL pass's buffer (audio=residual2)")]
    public async Task Audio_Residual_ThirdPassSkipped_ReadsResidualPassBuffer()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, []], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Deep, CoherentFallbackAudio.Residual, log));

        AudioField(log).Should().Be("residual2");
        interop.RunPcms.Single()[100].Should().BeApproximately(Normalised()[100] - 0.02f, 1e-5f, "pass 0's two signals subtracted, nothing more");
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Residual on Normal depth - residual-unavailable, original audio, Normal path unchanged")]
    public async Task Audio_Residual_Normal_Unavailable()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Normal, CoherentFallbackAudio.Residual, log));

        AudioField(log).Should().Be("residual-unavailable");
        interop.RunPcms.Single().Should().Equal(Normalised());
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Residual and pass 0 decoded nothing (no residual pass) - residual-unavailable")]
    public async Task Audio_Residual_NothingDecoded_Unavailable()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([[]], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Deep, CoherentFallbackAudio.Residual, log));

        AudioField(log).Should().Be("residual-unavailable");
        interop.RunPcms.Single().Should().Equal(Normalised());
    }

    private static CohFallbackRunResult RunOf(params CohFallbackRow[] rows)
        => new(Stats(rows.Length, rows.Length, rows.Length, rows.Length, rows.Length, 0), rows) { Workers = 4 };

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO: Both - the fallback runs ONCE on each audio (residual first, then original), the results are merged by payload (residual row kept), one batch 4, counts logged")]
    public async Task Audio_Both_RunsOnBoth_MergesByPayload()
    {
        var log = new LineLog();
        // residual run finds payloads 1 and 2; original run finds 2 and 3.
        var interop = new FallbackInterop([Pass0, Resid], null)
        {
            Texts = { [1] = "Q1AAA Q1BBB RR73", [2] = "Q1CCC Q1DDD RR73", [3] = "Q1EEE Q1FFF RR73" },
            ShatValue = 0.01f,
            RunByCall = n => n == 1 ? RunOf(Row(1), Row(2, freq: 1100f, snr: -18)) : RunOf(Row(2, freq: 1100f, snr: -25), Row(3, freq: 1200f)),
        };
        var delivered = await RunStaged(BuildWithAudio(interop, DecodingDepth.Deep, CoherentFallbackAudio.Both, log));

        interop.RunCalls.Should().Be(2);
        var orig = Normalised();
        interop.RunPcms[0][100].Should().BeApproximately(orig[100] - 0.03f, 1e-5f, "the first run reads the third pass's buffer");
        interop.RunPcms[1].Should().Equal(orig, "the second run reads the original audio");
        var batch4 = delivered.Single(b => b.Batch == 4);
        batch4.Results.Should().HaveCount(3, "one row per payload: 1, 2 and 3");
        batch4.Results.Select(r => r.Snr).Should().Contain(-18).And.NotContain(-25, "where both found payload 2 the residual row is kept");
        var line = log.Lines.Single(l => l.StartsWith("Coherent fallback:"));
        line.Should().EndWith(", audio=both(residual3), fromOriginal=1, fromResidual=1, inBoth=1.");
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO: Both with no usable residual buffer - the original audio is run ONCE (never twice) and the line says both(unavailable)")]
    public async Task Audio_Both_ResidualUnavailable_RunsOnce()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" }, ShatValue = 0.01f };
        await RunStaged(BuildWithAudio(interop, DecodingDepth.Normal, CoherentFallbackAudio.Both, log));

        interop.RunCalls.Should().Be(1);
        interop.RunPcms.Single().Should().Equal(Normalised());
        log.Lines.Single(l => l.StartsWith("Coherent fallback:"))
            .Should().EndWith(", audio=both(unavailable), fromOriginal=1, fromResidual=0, inBoth=0.");
    }

    // ── COH-MULTISET: the flag reaches the run once per cycle, and the line reports it ─────────────────────────────

    private static CohFallbackRow WonBy(int id, int provenance) => Row(id) with { Provenance = provenance };

    [Fact(DisplayName = "COH-MULTISET: decoder.coherentFallbackMultiSet defaults to true in the config record (the bare decoder object still starts false; the daemon sets it from the config); the setter and getter round-trip")]
    public void MultiSet_ConfigDefaultsToTrue_BareDecoderFalse_AndRoundTrips()
    {
        var cfg = new DecoderConfig();
        cfg.CoherentFallbackMultiSet.Should().BeTrue();
        var d = Build(new FallbackInterop([Pass0], OneNew()), DecodingDepth.Deep, true);
        d.CoherentFallbackMultiSet.Should().BeFalse("the object's own value at construction; the configured default reaches it through the setter");
        d.SetCoherentFallbackMultiSet(cfg.CoherentFallbackMultiSet);   // the daemon's wiring (Program.cs)
        d.CoherentFallbackMultiSet.Should().BeTrue("an absent key: the daemon's decoder reads true");
        d.SetCoherentFallbackMultiSet(new DecoderConfig { CoherentFallbackMultiSet = false }.CoherentFallbackMultiSet);
        d.CoherentFallbackMultiSet.Should().BeFalse("an explicit false: the daemon's decoder reads false");
        d.SetCoherentFallbackMultiSet(true);
        d.CoherentFallbackMultiSet.Should().BeTrue();
        d.SetCoherentFallbackMultiSet(false);
        d.CoherentFallbackMultiSet.Should().BeFalse();
    }

    [Fact(DisplayName = "COH-MULTISET: the run gets the flag exactly once per cycle (false by default, true when set) and the line says sets=off / sets=on")]
    public async Task MultiSet_IsPassedOncePerCycle_AndLogged()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var d = Build(interop, DecodingDepth.Deep, true, log);

        await RunStaged(d);
        d.SetCoherentFallbackMultiSet(true);
        await RunStaged(d);

        interop.MultiSetArgs.Should().Equal(false, true);
        var lines = log.Lines.Where(l => l.StartsWith("Coherent fallback:")).ToList();
        lines[0].Should().Contain("sets=off, walkEntered=0, crcC1=0, crcJ2=0, crcJ3=0, crcN1=0, audio=original.");
        lines[1].Should().Contain("sets=on, ");
    }

    [Fact(DisplayName = "COH-MULTISET: the line carries the walk-entry count and the CRC-valid counts per set, from the run's own counters and rows, and no message text")]
    public async Task MultiSet_LineCarriesTheCounters()
    {
        var log = new LineLog();
        var rows = new[] { WonBy(1, 3), WonBy(2, 3), WonBy(3, 2), WonBy(4, 0), Row(5, CohFallbackState.NoCrc) with { Provenance = -1 } };
        var run = new CohFallbackRunResult(Stats(5, 5, 4, 4, 4, 0) with { WalkEntered = 4 }, rows) { Workers = 4 };
        var interop = new FallbackInterop([Pass0, Resid], run)
        {
            Texts = { [1] = "Q1AAA Q1BBB RR73", [2] = "Q1CCC Q1DDD RR73", [3] = "Q1EEE Q1FFF RR73", [4] = "Q1GGG Q1HHH RR73" },
        };
        var d = Build(interop, DecodingDepth.Deep, true, log);
        d.SetCoherentFallbackMultiSet(true);

        await RunStaged(d);

        var line = log.Lines.Single(l => l.StartsWith("Coherent fallback:"));
        line.Should().Contain("sets=on, walkEntered=4, crcC1=0, crcJ2=1, crcJ3=2, crcN1=0, audio=original.");
        line.Should().NotContain("Q1AAA");
    }

    [Fact(DisplayName = "COH-MULTISET: the flag is read ONCE per cycle - changing it while the cycle runs does not change that cycle's value, the next cycle sees it")]
    public async Task MultiSet_IsReadOnce_PerCycle()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var d = Build(interop, DecodingDepth.Deep, true);
        d.SetCoherentFallbackMultiSet(true);

        await RunStaged(d, interop, onBatch: n => { if (n == 1) d.SetCoherentFallbackMultiSet(false); });
        await RunStaged(d, interop);

        interop.MultiSetArgs.Should().Equal(true, false);
    }

    [Fact(DisplayName = "COH-MULTISET: the flag acts only while the fallback is on - with the fallback OFF there is no run and no line, whatever the flag says")]
    public async Task MultiSet_NeedsTheFallback()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew());
        var d = Build(interop, DecodingDepth.Deep, fallback: false, log);
        d.SetCoherentFallbackMultiSet(true);

        await RunStaged(d);

        interop.RunCalls.Should().Be(0);
        interop.MultiSetArgs.Should().BeEmpty();
        log.Lines.Should().NotContain(l => l.StartsWith("Coherent fallback:"));
    }

    // ── R10: the flag ─────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "Default ON: decoder.coherentFallbackEnabled is true in the config record and for an absent key, false stays false; a bare Ft8Decoder is OFF until the daemon sets it")]
    public void Flag_DefaultsToTrue_InConfig_BareDecoderOff()
    {
        new DecoderConfig().CoherentFallbackEnabled.Should().BeTrue();
        new Ft8Decoder(new FakeClock(CycleStart), null, interop: new FallbackInterop([], null)).CoherentFallbackEnabled.Should().BeFalse(
            "the decoder class has no config: the daemon applies decoder.coherentFallbackEnabled at start-up and on every save");
        System.Text.Json.JsonSerializer.Deserialize<DecoderConfig>("""{"kMinScorePass2":10}""")!
            .CoherentFallbackEnabled.Should().BeTrue("a config written before the key existed loads true");
        System.Text.Json.JsonSerializer.Deserialize<DecoderConfig>("""{"coherentFallbackEnabled":false}""", new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true })!
            .CoherentFallbackEnabled.Should().BeFalse("an explicit false stays false");
    }

    [Fact(DisplayName = "R10: the setter and getter on Ft8Decoder round-trip (the replay harness reads the flag back)")]
    public void Flag_SetterGetterRoundTrip()
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), null, interop: new FallbackInterop([], null));
        d.SetCoherentFallbackEnabled(true);
        d.CoherentFallbackEnabled.Should().BeTrue();
        d.SetCoherentFallbackEnabled(false);
        d.CoherentFallbackEnabled.Should().BeFalse();
    }

    // ── R6''' : the batch of its own ─────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "R6''': Deep - batches 1, 2 and 3 equal flag-OFF's, the fallback is batch 4 on its own (no text of it in batch 3)")]
    public async Task Deep_FallbackIsBatch4()
    {
        var off = await RunStaged(Build(new FallbackInterop([Pass0, Resid, Third], null), DecodingDepth.Deep, fallback: false));
        var interop = new FallbackInterop([Pass0, Resid, Third], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, fallback: true), interop);

        on.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        for (int i = 0; i < 3; i++)
            on[i].Messages.Should().Equal(off[i].Messages, "batch {0} is untouched by the flag", i + 1);
        on[3].Messages.Should().Equal("Q1AAA Q1BBB RR73");
        off.Select(b => b.Batch).Should().Equal(1, 2, 3);
    }

    [Fact(DisplayName = "R6''': Normal - batch 2 is the residual pass's decodes alone, the fallback is batch 3 on its own")]
    public async Task Normal_FallbackIsBatch3()
    {
        var interop = new FallbackInterop([Pass0, Resid, Third], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Normal, fallback: true), interop);

        on.Select(b => b.Batch).Should().Equal(1, 2, 3);
        on[1].Messages.Should().Equal("Q1DEF Q1UVW EN37");
        on[2].Messages.Should().Equal("Q1AAA Q1BBB RR73");
        interop.DecodeAllCallCount.Should().Be(2, "Normal never runs the third pass");
    }

    [Fact(DisplayName = "R6''': Normal, residual pass found nothing - the fallback is batch 3 and there is no batch 2")]
    public async Task Normal_NoResidual_FallbackIsBatch3()
    {
        var interop = new FallbackInterop([Pass0], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Normal, fallback: true), interop);
        on.Select(b => b.Batch).Should().Equal(1, 3);
        on[1].Messages.Should().Equal("Q1AAA Q1BBB RR73");
    }

    [Fact(DisplayName = "R6''': the two-stage entry has no callback for a batch of its own, so the flag has no effect there: the pre-change batch 2, no fallback call")]
    public async Task TwoStageEntry_FlagHasNoEffect()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var second = await Build(interop, DecodingDepth.Normal, fallback: true)
            .DecodeTwoStageAsync(LoudPcm(), CycleStart, null, _ => Task.CompletedTask);

        second.Select(r => r.Message).Should().Equal("Q1DEF Q1UVW EN37");
        (interop.SnapshotCalls, interop.RunCalls, interop.UnpackCalls).Should().Be((0, 0, 0));
    }

    [Fact(DisplayName = "R6''': Deep, the residual pass found nothing (third pass skipped) - the fallback is still batch 4, after batch 1 only")]
    public async Task Deep_ThirdPassSkipped_FallbackStillBatch4()
    {
        var interop = new FallbackInterop([Pass0], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, fallback: true), interop);

        on.Select(b => b.Batch).Should().Equal(1, 4);
        on[1].Messages.Should().Equal("Q1AAA Q1BBB RR73");
    }

    [Fact(DisplayName = "R6''': pass 0 decoded nothing - the fallback still runs, as batch 4 on Deep and batch 3 on Normal; batch 1 stays the (empty) pass-0 batch")]
    public async Task NothingDecoded_FallbackStillHasItsBatch()
    {
        var deepInterop = new FallbackInterop([[]], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var deep = await RunStaged(Build(deepInterop, DecodingDepth.Deep, true), deepInterop);
        deep.Select(b => b.Batch).Should().Equal(1, 4);
        deep[0].Messages.Should().BeEmpty();
        deep[1].Messages.Should().Equal("Q1AAA Q1BBB RR73");

        var normalInterop = new FallbackInterop([[]], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var normal = await RunStaged(Build(normalInterop, DecodingDepth.Normal, true), normalInterop);
        normal.Select(b => b.Batch).Should().Equal(1, 3);
        normal[1].Messages.Should().Equal("Q1AAA Q1BBB RR73");
    }

    [Fact(DisplayName = "R6''': a fallback text already published in ANY earlier batch of the cycle is not published again; batch 4 carries only the genuinely new text")]
    public async Task Dedup_AgainstEveryEarlierBatch()
    {
        var run = new CohFallbackRunResult(Stats(4, 4, 4, 4, 4, 0), [Row(1), Row(2), Row(3), Row(4)]);
        var interop = new FallbackInterop([Pass0, Resid, Third], run)
        {
            Texts = { [1] = "Q1ABC Q1XYZ JO33", [2] = "Q1DEF Q1UVW EN37", [3] = "Q1MNO Q1PQR IO91", [4] = "Q1NEW Q1ONE RR73" },
        };
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, true), interop);

        on.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        on[2].Messages.Should().Equal("Q1MNO Q1PQR IO91");
        on[3].Messages.Should().Equal("Q1NEW Q1ONE RR73");   // texts of batches 1, 2 and 3 are not repeated

        // nothing new at all: batch 4 is not delivered
        var run2 = new CohFallbackRunResult(Stats(1, 1, 1, 1, 1, 0), [Row(1)]);
        var interop2 = new FallbackInterop([Pass0, Resid], run2) { Texts = { [1] = "Q1DEF Q1UVW EN37" } };
        var on2 = await RunStaged(Build(interop2, DecodingDepth.Deep, true), interop2);
        on2.Select(b => b.Batch).Should().Equal(1, 2);
    }

    [Fact(DisplayName = "R6''': the fallback's output goes through the same plausibility filter (an implausible text is dropped)")]
    public async Task PlausibilityFilter_Applies()
    {
        var run = new CohFallbackRunResult(Stats(2, 2, 2, 2, 2, 0), [Row(1), Row(2)]);
        var interop = new FallbackInterop([Pass0], run) { Texts = { [1] = "Q1AAA Q1BBB ZA99", [2] = "Q1CCC Q1DDD RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Normal, true), interop);
        on.Single(b => b.Batch == 3).Messages.Should().Equal("Q1CCC Q1DDD RR73");
    }

    // ── R7''': when it starts (recorded order, no timing) ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "R7''': Deep - the fallback starts only after batch 3 has been handed off, and nothing of it ran during the ordinary passes")]
    public async Task Deep_StartsAfterBatch3_RecordedOrder()
    {
        var interop = new FallbackInterop([Pass0, Resid, Third], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Deep, true), interop);

        var order = interop.Calls.Where(c => c != "analytic").ToList();
        order.Should().Equal("decode1", "snapshot", "batch1", "decode2", "batch2", "decode3", "batch3", "run", "unpack", "batch4");
        interop.OrdinaryActiveAtRun.Should().Be(0, "no ordinary native call was in flight when the fallback ran");
    }

    [Fact(DisplayName = "R7''': Deep - a third pass that found nothing (no batch 3) still comes before the fallback")]
    public async Task Deep_NoBatch3_FallbackStillAfterThirdPass()
    {
        var interop = new FallbackInterop([Pass0, Resid, []], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, true), interop);

        on.Select(b => b.Batch).Should().Equal(1, 2, 4);
        interop.Calls.Where(c => c != "analytic").Should().Equal("decode1", "snapshot", "batch1", "decode2", "batch2", "decode3", "run", "unpack", "batch4");
    }

    [Fact(DisplayName = "R7''': Normal - the fallback starts only after batch 2 has been handed off")]
    public async Task Normal_StartsAfterBatch2_RecordedOrder()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Normal, true), interop);

        interop.Calls.Where(c => c != "analytic").Should().Equal("decode1", "snapshot", "batch1", "decode2", "batch2", "run", "unpack", "batch3");
        interop.OrdinaryActiveAtRun.Should().Be(0);
    }

    [Fact(DisplayName = "R7''': pass 0 decoded nothing - the fallback starts right after batch 1 (there is no later ordinary batch)")]
    public async Task NothingDecoded_StartsAfterBatch1()
    {
        var interop = new FallbackInterop([[]], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Deep, true), interop);

        interop.Calls.Should().Equal("decode1", "snapshot", "batch1", "run", "unpack", "batch4");
    }

    [Fact(DisplayName = "R15: the snapshot is taken on the thread that ran the ordinary decode, right after the pass-0 call, and is the array every worker reads")]
    public async Task SnapshotOnDecodeThread()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Normal, true));

        interop.SnapshotThreadId.Should().Be(interop.DecodeAllThreadId, "the retained candidate list is thread-local to the decode's thread");
        interop.Calls.IndexOf("snapshot").Should().Be(interop.Calls.IndexOf("decode1") + 1, "taken right after the pass-0 call, before the residual decode");
    }

    [Fact(DisplayName = "R7''': the run gets the shared budget (13 s minus what the ordinary work used, minus the 250 ms reserve), EffectiveSubtractionThreads workers, and the ordinary decode's normalised buffer")]
    public async Task RunGets_BudgetWorkersAndBuffer()
    {
        var interop = new FallbackInterop([Pass0], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var d = Build(interop, DecodingDepth.Normal, true);
        await RunStaged(d);

        interop.RunBudgetMs.Should().NotBeNull();
        interop.RunBudgetMs!.Value.Should().BeInRange(1.0, 13_000.0 - 250.0, "13 s less the 250 ms publish reserve, less what the cycle used before the fallback started");
        interop.RunWorkers.Should().Be(d.EffectiveSubtractionThreads);
        interop.RunPcm.Should().NotBeNull().And.HaveCount(180_000);
    }

    [Fact(DisplayName = "R7''': abandoned candidates publish nothing and are counted per cycle; the next cycle starts clean (never queued)")]
    public async Task Abandoned_CountedNotPublishedNotQueued()
    {
        var log = new LineLog();
        var run = new CohFallbackRunResult(Stats(4, 2, 1, 1, 1, 2), [
            Row(1), Row(0, CohFallbackState.NoCrc), Row(0, CohFallbackState.Abandoned), Row(2, CohFallbackState.Abandoned)]);
        var interop = new FallbackInterop([Pass0], run) { Texts = { [1] = "Q1AAA Q1BBB RR73", [2] = "Q1CCC Q1DDD RR73" } };
        var d = Build(interop, DecodingDepth.Normal, true, log);

        var first = await RunStaged(d);
        first.Single(b => b.Batch == 3).Messages.Should().Equal("Q1AAA Q1BBB RR73");   // an abandoned row (even one carrying a payload) is never published
        log.Lines.Single(l => l.StartsWith("Coherent fallback:")).Should().Contain("abandoned=2");

        interop.RunCalls.Should().Be(1);
        await RunStaged(d);
        interop.RunCalls.Should().Be(2, "one run per cycle: nothing from cycle 1 was queued into cycle 2");
        interop.UnpackCalls.Should().Be(2, "one selected payload per cycle: the abandoned work left nothing behind");
    }

    [Fact(DisplayName = "R7''': a fallback that fails (native exception) loses nothing: batches 1, 2 and 3 are the flag-OFF batches, one warning")]
    public async Task FallbackFailure_IsContained()
    {
        var log = new LineLog();
        var off = await RunStaged(Build(new FallbackInterop([Pass0, Resid, Third], null), DecodingDepth.Deep, false));
        var interop = new FallbackInterop([Pass0, Resid, Third], null) { RunThrows = new NativeAccessViolationException() };
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, true, log));

        on.Select(b => (b.Batch, string.Join("|", b.Messages))).Should().Equal(off.Select(b => (b.Batch, string.Join("|", b.Messages))));
        log.Lines.Should().Contain(l => l.Contains("coherent fallback failed"));
        log.Lines.Should().NotContain(l => l.StartsWith("Coherent fallback:"), "no R12' line for a cycle whose fallback faulted");
    }

    // ── R12' / R6'': the line, the edge preference ─────────────────────────────────────────────────────────────

    private static readonly Regex LineShape = new(
        @"^Coherent fallback: eligible=7, attempted=6, crcOk=3, f1bComputed=2, gated=1, published=1, abandoned=1, elapsedMs=457, publishedEdge=1, path=2, " +
        @"workers=4, fbStartMs=(\d+), fbWallMs=(\d+), batch=(\d), batch4Published=([01]), batch4PublishMs=(-?\d+), " +
        @"sets=(on|off), walkEntered=(\d+), crcC1=(\d+), crcJ2=(\d+), crcJ3=(\d+), crcN1=(\d+), audio=(original|residual3|residual2|residual-unavailable)\.$", RegexOptions.CultureInvariant);

    [Fact(DisplayName = "R12': ONE aggregates-only line per cycle, with the documented fields (workers, fbStartMs, fbWallMs, batch, batch4Published, batch4PublishMs) and no message text")]
    public async Task Log_OneLinePerCycle_WithTheFields()
    {
        var log = new LineLog();
        var run = new CohFallbackRunResult(Stats(eligible: 7, attempted: 6, crcOk: 3, f1b: 2, gated: 1, abandoned: 1, edge: 1, totalMs: 456.7), [Row(1, edge: true)]) { Workers = 4 };
        var interop = new FallbackInterop([Pass0, Resid], run) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var d = Build(interop, DecodingDepth.Deep, true, log);

        await RunStaged(d);
        await RunStaged(d);

        var lines = log.Lines.Where(l => l.StartsWith("Coherent fallback:")).ToList();
        lines.Should().HaveCount(2, "one line per cycle");
        var m = LineShape.Match(lines[0]);
        m.Success.Should().BeTrue("the line is: {0}", lines[0]);
        m.Groups[3].Value.Should().Be("4", "the fallback's batch on Deep");
        m.Groups[4].Value.Should().Be("1", "a batch was published");
        int startMs = int.Parse(m.Groups[1].Value), publishMs = int.Parse(m.Groups[5].Value);
        publishMs.Should().BeGreaterThanOrEqualTo(startMs, "the batch is handed off after the fallback started (same clock, from the decode's start)");
        lines[0].Should().NotContain("Q1AAA");
    }

    [Fact(DisplayName = "R12': a cycle whose fallback published nothing logs batch4Published=0 and batch4PublishMs=-1 (an explicit flag, never an averaged time)")]
    public async Task Log_NothingPublished_FlagAndMinusOne()
    {
        var log = new LineLog();
        var run = new CohFallbackRunResult(Stats(eligible: 7, attempted: 6, crcOk: 3, f1b: 2, gated: 1, abandoned: 1, edge: 1, totalMs: 456.7), []) { Workers = 4 };
        var interop = new FallbackInterop([Pass0, Resid], run);
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, true, log), interop);

        on.Select(b => b.Batch).Should().Equal(new[] { 1, 2 }, "no batch 4");
        var line = log.Lines.Single(l => l.StartsWith("Coherent fallback:"));
        line.Should().Contain("published=0,").And.Contain("batch=4, batch4Published=0, batch4PublishMs=-1, ");
    }

    [Fact(DisplayName = "R12': a publish callback that throws still leaves the cycle's line (written in a finally), with batch4Published=1")]
    public async Task Log_WrittenEvenWhenThePublishThrows()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var d = Build(interop, DecodingDepth.Deep, true, log);

        Func<Task> act = () => d.DecodeStagedAsync(LoudPcm(), CycleStart, null,
            (n, _) => n == 4 ? throw new InvalidOperationException("sink failed") : Task.CompletedTask);

        await act.Should().ThrowAsync<InvalidOperationException>();
        log.Lines.Single(l => l.StartsWith("Coherent fallback:")).Should().Contain("batch=4, batch4Published=1,");
    }

    [Fact(DisplayName = "R12': on Normal the line names batch=3")]
    public async Task Log_Normal_NamesBatch3()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Normal, true, log), interop);

        log.Lines.Single(l => l.StartsWith("Coherent fallback:")).Should().Contain("batch=3, batch4Published=1,");
    }

    [Fact(DisplayName = "R12': published counts the texts that reach the batch (after the cross-batch dedup), publishedEdge those at the window edge")]
    public async Task Log_PublishedIsAfterDedup()
    {
        var log = new LineLog();
        var run = new CohFallbackRunResult(Stats(2, 2, 2, 2, 2, 0, edge: 1), [Row(1, edge: true), Row(2)]);
        var interop = new FallbackInterop([Pass0, Resid], run) { Texts = { [1] = "Q1DEF Q1UVW EN37", [2] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Deep, true, log));

        log.Lines.Single(l => l.StartsWith("Coherent fallback:")).Should().Contain("published=1,").And.Contain("publishedEdge=0,");
    }

    [Fact(DisplayName = "R6'': two candidates with the same payload publish ONCE, and it is the first non-edge one")]
    public async Task SamePayload_PublishedOnce_NonEdgePreferred()
    {
        var run = new CohFallbackRunResult(Stats(3, 3, 3, 3, 3, 0, edge: 1), [
            Row(1, edge: true, freq: 1000f), Row(1, edge: false, freq: 1002f), Row(1, edge: false, freq: 1004f)]);
        var interop = new FallbackInterop([Pass0], run) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Normal, true));

        var fb = on.Single(b => b.Batch == 3);
        fb.Results.Should().ContainSingle();
        fb.Results[0].FreqHz.Should().Be(1002, "the first non-edge member (anchor 1002 Hz, estimate +0.3 Hz rounded)");
        interop.UnpackCalls.Should().Be(1);
    }

    [Fact(DisplayName = "R6'': the selector - first non-edge per payload, the first edge one when all are edge, candidate order, only NewGated rows")]
    public void Selector_Rules()
    {
        // same payload: edge, edge, non-edge, non-edge -> the third
        CoherentFallbackSelector.Select([Row(1, edge: true), Row(1, edge: true), Row(1), Row(1)])
            .Select(r => r.Edge).Should().Equal(false);
        CoherentFallbackSelector.Select([Row(1, edge: true, freq: 1f), Row(1, edge: true, freq: 2f), Row(1), Row(1, freq: 9f)])
            .Single().FreqHz.Should().Be(1000f, "the third row, the first non-edge");

        // all edge: the first of them
        CoherentFallbackSelector.Select([Row(1, edge: true, freq: 5f), Row(1, edge: true, freq: 6f)])
            .Single().FreqHz.Should().Be(5f);

        // two payloads keep candidate order, each decided on its own
        var two = CoherentFallbackSelector.Select([Row(2, freq: 10f), Row(1, edge: true, freq: 20f), Row(2, freq: 30f), Row(1, freq: 40f)]);
        two.Select(r => r.FreqHz).Should().Equal(new[] { 10f, 40f });   // payload 2's first non-edge is row 0, payload 1's is row 3; order = candidate order of the chosen rows

        // rows that do not publish never take part
        CoherentFallbackSelector.Select([
            Row(1, CohFallbackState.Abandoned), Row(1, CohFallbackState.NoCrc), Row(1, CohFallbackState.Known),
            Row(1, CohFallbackState.GatedOut), Row(1, edge: true, freq: 7f)])
            .Single().FreqHz.Should().Be(7f, "an ungated non-edge row of the same payload does not displace the published edge one");

        CoherentFallbackSelector.Select([]).Should().BeEmpty();
    }

    [Fact(DisplayName = "R6'': deterministic - the same rows give the same selection every time")]
    public void Selector_IsDeterministic()
    {
        var rows = new List<CohFallbackRow>();
        for (int i = 0; i < 40; i++) rows.Add(Row(i % 5, edge: i % 3 == 0, freq: 1000f + i));
        var first = CoherentFallbackSelector.Select(rows).Select(r => r.FreqHz).ToArray();
        for (int k = 0; k < 20; k++)
            CoherentFallbackSelector.Select(rows).Select(r => r.FreqHz).Should().Equal(first);
    }

    // ── R11: the path tag ────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "R11: every decode carries its path - 0 ordinary, 1 residual and third pass, 2 fallback (batch 4)")]
    public async Task PathTag()
    {
        var interop = new FallbackInterop([Pass0, Resid, Third], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var on = await RunStaged(Build(interop, DecodingDepth.Deep, true));

        on[0].Results.Select(r => r.Path).Should().AllBeEquivalentTo(0);
        on[1].Results.Select(r => r.Path).Should().AllBeEquivalentTo(1);
        on[2].Results.Select(r => r.Path).Should().AllBeEquivalentTo(1);
        on[3].Results.Select(r => r.Path).Should().AllBeEquivalentTo(2);
    }

    [Fact(DisplayName = "R11: the tag is not serialised - the decode panel / UDP / ALL.TXT formats are unchanged")]
    public void PathTag_IsNotSerialised()
    {
        var r = new DecodeResult("12:00:00", -12, 0.2, 1500, "Q1ABC Q1XYZ JO33") { Path = 2 };
        System.Text.Json.JsonSerializer.Serialize(r).Should().NotContain("ath").And.Contain("Message");
    }

    // ── R13: flag OFF changes nothing ─────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "R13: flag OFF - not one fallback native call (snapshot, run, unpack), and the batches and call order are the pre-change ones")]
    public async Task FlagOff_NoNativeFallbackCalls()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid, Third], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var off = await RunStaged(Build(interop, DecodingDepth.Deep, false, log), interop);

        (interop.SnapshotCalls, interop.RunCalls, interop.UnpackCalls).Should().Be((0, 0, 0));
        interop.Calls.Where(c => c != "analytic").Should().Equal("decode1", "batch1", "decode2", "batch2", "decode3", "batch3");
        off.Select(b => b.Batch).Should().Equal(1, 2, 3);
        off[2].Messages.Should().Equal("Q1MNO Q1PQR IO91");
        log.Lines.Should().NotContain(l => l.StartsWith("Coherent fallback:"));
    }

    [Fact(DisplayName = "R13: flag OFF on Normal - batches 1 and 2 only, as before, and the same native call order")]
    public async Task FlagOff_Normal_PreChangeBatches()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var off = await RunStaged(Build(interop, DecodingDepth.Normal, false), interop);

        off.Select(b => b.Batch).Should().Equal(1, 2);
        off[1].Messages.Should().Equal("Q1DEF Q1UVW EN37");
        interop.Calls.Where(c => c != "analytic").Should().Equal("decode1", "batch1", "decode2", "batch2");   // batch 2 is delivered after the core returns
        (interop.SnapshotCalls, interop.RunCalls, interop.UnpackCalls).Should().Be((0, 0, 0));
    }

    [Fact(DisplayName = "R13/R9: the single-batch entry, the early decode and a cycle with the residual pass OFF never touch the fallback, whatever the flag says")]
    public async Task FlagOn_ButNotAStagedCycle_NeverRuns()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        var d = Build(interop, DecodingDepth.Deep, true);

        await d.DecodeAsync(LoudPcm(), CycleStart, null);                                  // single batch
        await d.DecodeEarlyAsync(LoudPcm(), CycleStart, null);                             // the early decode (R9)
        d.SetSubtractionEnabled(false);
        await RunStaged(d);                                                                // staged entry, residual pass OFF

        (interop.SnapshotCalls, interop.RunCalls, interop.UnpackCalls).Should().Be((0, 0, 0));
    }

    [Fact(DisplayName = "R8: the residual pass is not fed the fallback's decodes - it fits the pass-0 signals only")]
    public async Task ResidualPass_NotFedByFallback()
    {
        var interop = new FallbackInterop([Pass0, Resid], OneNew()) { Texts = { [1] = "Q1AAA Q1BBB RR73" } };
        await RunStaged(Build(interop, DecodingDepth.Normal, true));
        var offInterop = new FallbackInterop([Pass0, Resid], null);
        await RunStaged(Build(offInterop, DecodingDepth.Normal, false));

        interop.AnalyticCallCount.Should().Be(offInterop.AnalyticCallCount);
        interop.DecodeAllCallCount.Should().Be(offInterop.DecodeAllCallCount);
    }

    // ── COH-FB-AUDIO N-1: the shared-budget guard of Both (Ft8Decoder, "leftMs"), and the runner's claim guard ─────
    //
    // The clock is a TimeProvider the test owns (the internal seam): it moves only when the stub's fallback run says so, by arithmetic -
    // no Task.Delay, no Thread.Sleep, no wall-clock read. Workers = 1 wherever a count is asserted exactly.

    /// <summary>A time source that moves only when a test advances it (1 tick = 100 ns, as <see cref="TimeSpan"/>).</summary>
    private sealed class ManualTimeProvider : TimeProvider
    {
        private long _ticks;
        public override long TimestampFrequency => TimeSpan.TicksPerSecond;
        public override long GetTimestamp() => Interlocked.Read(ref _ticks);
        public void Advance(TimeSpan by) => Interlocked.Add(ref _ticks, by.Ticks);
        public TimeSpan Elapsed => TimeSpan.FromTicks(Interlocked.Read(ref _ticks));
    }

    /// <summary>A fallback backend of <c>n</c> eligible candidates (payload ids from <c>firstId</c>); every candidate costs <c>costPerCandidate</c> of the manual clock.</summary>
    private sealed class TickingBackend(int n, int firstId, ManualTimeProvider time, TimeSpan costPerCandidate) : ICohFallbackBackend
    {
        public int ProcessCalls;
        private readonly int _firstId = firstId;
        private readonly ManualTimeProvider _time = time;
        private readonly TimeSpan _cost = costPerCandidate;

        public CohFallbackPlan? Plan(byte[] snapshot)
            => new(Stats(n, 0, 0, 0, 0, 0), Enumerable.Range(0, n).Select(e => 2 * e + 1).ToList(),
                   Enumerable.Range(0, n).Select(e => Row(_firstId + e, CohFallbackState.Abandoned)).ToList());

        public ICohFallbackWorker CreateWorker() => new Worker(this);

        private sealed class Worker(TickingBackend owner) : ICohFallbackWorker
        {
            private int _attempted;
            public CohFallbackRow Process(float[] pcm, byte[] snapshot, int candidateIndex)
            {
                Interlocked.Increment(ref owner.ProcessCalls);
                _attempted++;
                owner._time.Advance(owner._cost);   // the candidate's cost, by arithmetic
                return Row(owner._firstId + (candidateIndex - 1) / 2);
            }
            public CohFallbackStats Accumulated => new(0, 0, 0, 0, _attempted, _attempted, _attempted, _attempted, _attempted, 0, 0, 0, 0, 0, 0);
            public void Dispose() { }
        }
    }

    private static string TextOf(int id) => $"Q1{(char)('A' + id / 26)}{(char)('A' + id % 26)}A Q1BBB RR73";

    private static Dictionary<int, string> TextsFor(int count) => Enumerable.Range(1, count).ToDictionary(i => i, TextOf);

    private static Ft8Decoder BuildTimed(IFt8NativeInterop interop, ManualTimeProvider time, ILogger<Ft8Decoder> log)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop, timeProvider: time);
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(DecodingDepth.Deep);
        d.SetCoherentFallbackEnabled(true);
        d.SetCoherentFallbackAudio(CoherentFallbackAudio.Both);
        return d;
    }

    /// <summary>What production gives the first run: the shared 13 s budget less the publish reserve, when the fallback starts at clock 0.</summary>
    private static readonly double FirstRunBudgetMs = (Ft8Decoder.SubtractionCycleBudget - Ft8Decoder.CoherentFallbackPublishReserve).TotalMilliseconds;

    private static int IntField(LineLog log, string name)
        => int.Parse(Regex.Match(log.Lines.Single(l => l.StartsWith("Coherent fallback:")), name + @"=(\d+)").Groups[1].Value);

    [Theory(DisplayName = "FR-100: COH-FB-AUDIO N-1(a): Both, leftMs <= 0 - the second run is never called, its eligible candidates are counted abandoned, the first run's rows still publish")]
    [InlineData(0.0)]      // the first run spends exactly the whole budget: leftMs == 0, and the guard is "> 0"
    [InlineData(500.0)]    // it overruns by 500 ms: leftMs < 0
    public async Task Both_BudgetSpentByFirstRun_SecondRunNotStarted(double overrunMs)
    {
        const int EligibleInFirstRun = 2;
        var time = new ManualTimeProvider();
        var log = new LineLog();
        FallbackInterop? interop = null;
        interop = new FallbackInterop([Pass0, Resid], null)
        {
            Texts = TextsFor(EligibleInFirstRun),
            ShatValue = 0.01f,
            RunByCall = _ =>
            {
                time.Advance(TimeSpan.FromMilliseconds(interop!.RunBudgetMs!.Value + overrunMs));   // the first run spends the budget (no sleeping)
                return RunOf(Row(1), Row(2, freq: 1100f));
            },
        };

        var delivered = await RunStaged(BuildTimed(interop, time, log));

        interop.RunBudgetMs.Should().Be(FirstRunBudgetMs, "the fallback started at clock 0, so the first run gets the 13 s budget less the reserve");
        interop.RunCalls.Should().Be(1, "the second run's backend is never called once nothing is left of the shared budget");
        IntField(log, "abandoned").Should().Be(EligibleInFirstRun, "the second run's eligible candidates are counted abandoned (same snapshot, so as many as the first run's eligible)");
        IntField(log, "attempted").Should().Be(EligibleInFirstRun, "only the first run attempted anything");
        delivered.Single(b => b.Batch == 4).Messages.Should().BeEquivalentTo(new[] { TextOf(1), TextOf(2) }, "the first run's rows still publish, as one batch 4");
        log.Lines.Single(l => l.StartsWith("Coherent fallback:")).Should().EndWith(", audio=both(residual3), fromOriginal=0, fromResidual=2, inBoth=0.");
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO N-1(b): Both, 0 < leftMs < one run's wall time - the second run starts on leftMs, stops claiming at its budget, the rest are abandoned, the first run's rows still publish")]
    public async Task Both_BudgetShortForSecondRun_StopsClaimingAtItsBudget()
    {
        const int EligiblePerRun = 10;
        const int WorkersForExactCount = 1;   // one worker: how many candidates are claimed is then exact, not scheduling-dependent
        var costPerCandidate = TimeSpan.FromSeconds(1);
        double allowanceMs = costPerCandidate.TotalMilliseconds;   // the one candidate in flight when the budget is reached is always finished

        var time = new ManualTimeProvider();
        var log = new LineLog();
        FallbackInterop? interop = null;
        TickingBackend? firstBackend = null, secondBackend = null;
        interop = new FallbackInterop([Pass0, Resid], null)
        {
            Texts = TextsFor(2 * EligiblePerRun),
            ShatValue = 0.01f,
            // The REAL runner, on a stub backend and the manual clock: the budget it is handed is the one the decoder computed.
            RunByCall = call =>
            {
                var backend = call == 1
                    ? firstBackend = new TickingBackend(EligiblePerRun, 1, time, costPerCandidate)
                    : secondBackend = new TickingBackend(EligiblePerRun, 1 + EligiblePerRun, time, costPerCandidate);
                return CohFallbackParallelRunner.Run(backend, interop!.RunPcm!, [1, 2, 3, 4], interop.RunBudgetMs!.Value, WorkersForExactCount,
                                                     CancellationToken.None, timeProvider: time);
            },
        };

        var delivered = await RunStaged(BuildTimed(interop, time, log));

        double firstRunMs = EligiblePerRun * costPerCandidate.TotalMilliseconds;
        double leftMs = FirstRunBudgetMs - firstRunMs;
        leftMs.Should().BeGreaterThan(0).And.BeLessThan(firstRunMs, "the scenario: something is left, but less than one run needs");
        int expectedSecondRun = (int)Math.Ceiling(leftMs / costPerCandidate.TotalMilliseconds);   // it claims while elapsed < leftMs: ceil(leftMs / cost)

        interop.RunCalls.Should().Be(2);
        interop.RunBudgetMs.Should().BeApproximately(leftMs, 1e-6, "the second run is handed what the first left of the shared budget");
        firstBackend!.ProcessCalls.Should().Be(EligiblePerRun, "the first run finished all its candidates");
        secondBackend!.ProcessCalls.Should().Be(expectedSecondRun).And.BeLessThan(EligiblePerRun, "the second run stopped claiming at its budget").And.BeGreaterThan(0);
        IntField(log, "abandoned").Should().Be(EligiblePerRun - expectedSecondRun, "the unclaimed rest of the second run is counted abandoned");
        IntField(log, "attempted").Should().Be(EligiblePerRun + expectedSecondRun);
        var messages = delivered.Single(b => b.Batch == 4).Messages;
        messages.Should().Contain(Enumerable.Range(1, EligiblePerRun).Select(TextOf), "the first run's rows still publish");
        messages.Should().HaveCount(EligiblePerRun + expectedSecondRun, "one row per candidate that ran, in both runs (distinct payloads)");
        time.Elapsed.TotalMilliseconds.Should().BeLessThanOrEqualTo(FirstRunBudgetMs + allowanceMs,
            "the fallback ends within SubtractionCycleBudget - CoherentFallbackPublishReserve plus the one candidate in flight at the budget");
    }

    // ── COH-GATE-G R-F4: decoder.coherentFallbackResidualUngated (the residual run's GatedOut rows) ─────────────────

    private static Ft8Decoder BuildUngated(IFt8NativeInterop interop, DecodingDepth depth, CoherentFallbackAudio mode, bool ungated, ILogger<Ft8Decoder> log)
    {
        var d = BuildWithAudio(interop, depth, mode, log);
        d.SetCoherentFallbackResidualUngated(ungated);
        return d;
    }

    private static string FallbackLine(LineLog log) => log.Lines.Single(l => l.StartsWith("Coherent fallback:"));

    // residual run (call 1): 1 GatedOut, 2 GatedOut (SNR -18); original run (call 2): 2 NewGated (SNR -25), 3 GatedOut, 4 NewGated.
    private static FallbackInterop MixedStatesInterop() => new([Pass0, Resid], null)
    {
        Texts = TextsFor(4),
        ShatValue = 0.01f,
        RunByCall = n => n == 1
            ? RunOf(Row(1, CohFallbackState.GatedOut), Row(2, CohFallbackState.GatedOut, freq: 1100f, snr: -18))
            : RunOf(Row(2, freq: 1100f, snr: -25), Row(3, CohFallbackState.GatedOut, freq: 1150f), Row(4, freq: 1200f)),
    };

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4: a bare decoder starts OFF; the setter and getter round-trip")]
    public void Ungated_BareDecoderOff_RoundTrips()
    {
        var d = Build(new FallbackInterop([Pass0], OneNew()), DecodingDepth.Deep, true);
        d.CoherentFallbackResidualUngated.Should().BeFalse();
        d.SetCoherentFallbackResidualUngated(true);
        d.CoherentFallbackResidualUngated.Should().BeTrue();
        d.SetCoherentFallbackResidualUngated(false);
        d.CoherentFallbackResidualUngated.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4: Both, ON - residual GatedOut rows publish (residual row kept over the original's), an original GatedOut row does not, the line carries ungated=N and the counts of admitted rows")]
    public async Task Ungated_Both_On_PublishesResidualGatedOut()
    {
        var log = new LineLog();
        var interop = MixedStatesInterop();
        var delivered = await RunStaged(BuildUngated(interop, DecodingDepth.Deep, CoherentFallbackAudio.Both, true, log));

        var batch4 = delivered.Single(b => b.Batch == 4);
        batch4.Messages.Should().BeEquivalentTo(new[] { TextOf(1), TextOf(2), TextOf(4) }, "payload 3 is a GatedOut row of the original run: not admitted");
        batch4.Results.Select(r => r.Snr).Should().Contain(-18).And.NotContain(-25, "the admitted residual row displaced the original NewGated row");
        FallbackLine(log).Should().EndWith(", audio=both(residual3), fromOriginal=1, fromResidual=1, inBoth=1, ungated=2.");
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4: Both, OFF - the same rows publish what the build before this change did and the line has no ungated= field")]
    public async Task Ungated_Both_Off_AsBefore()
    {
        var log = new LineLog();
        var interop = MixedStatesInterop();
        var delivered = await RunStaged(BuildUngated(interop, DecodingDepth.Deep, CoherentFallbackAudio.Both, false, log));

        var batch4 = delivered.Single(b => b.Batch == 4);
        batch4.Messages.Should().BeEquivalentTo(new[] { TextOf(2), TextOf(4) });
        batch4.Results.Select(r => r.Snr).Should().Contain(-25);
        FallbackLine(log).Should().EndWith(", audio=both(residual3), fromOriginal=2, fromResidual=0, inBoth=0.");
        FallbackLine(log).Should().NotContain("ungated=");
    }

    [Theory(DisplayName = "FR-101: COH-GATE-G R-F4: Original and Residual modes ignore the setting - no GatedOut row is admitted and the line has no ungated= field")]
    [InlineData(CoherentFallbackAudio.Original)]
    [InlineData(CoherentFallbackAudio.Residual)]
    public async Task Ungated_NotBothModes_Ignored(CoherentFallbackAudio mode)
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], RunOf(Row(1, CohFallbackState.GatedOut), Row(2)))
        {
            Texts = TextsFor(2),
            ShatValue = 0.01f,
        };
        var delivered = await RunStaged(BuildUngated(interop, DecodingDepth.Deep, mode, true, log));

        interop.RunCalls.Should().Be(1);
        delivered.Single(b => b.Batch == 4).Messages.Should().Equal(TextOf(2));
        FallbackLine(log).Should().NotContain("ungated=");
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4 (b): a lone original-audio run (both(unavailable)) admits nothing over T1, the setting ON")]
    public async Task Ungated_LoneOriginalRun_NothingAdmitted()
    {
        var log = new LineLog();
        var interop = new FallbackInterop([Pass0, Resid], RunOf(Row(1, CohFallbackState.GatedOut), Row(2)))
        {
            Texts = TextsFor(2),
            ShatValue = 0.01f,
        };
        var delivered = await RunStaged(BuildUngated(interop, DecodingDepth.Normal, CoherentFallbackAudio.Both, true, log));

        interop.RunCalls.Should().Be(1, "no usable residual buffer: the original audio is run once");
        delivered.Single(b => b.Batch == 3).Messages.Should().BeEquivalentTo(new[] { TextOf(2) }, "the GatedOut row of the original run stays out");
        FallbackLine(log).Should().EndWith(", audio=both(unavailable), fromOriginal=1, fromResidual=0, inBoth=0, ungated=0.");
    }

    [Theory(DisplayName = "FR-101: COH-GATE-G R-F4 (a): residual run complete, original run NotRun (budget spent, BudgetClock/TimeProvider seam) - the residual GatedOut rows are admitted and published")]
    [InlineData(0.0)]
    [InlineData(500.0)]
    public async Task Ungated_ResidualComplete_OriginalNotRun_StillAdmitted(double overrunMs)
    {
        const int EligibleInFirstRun = 2;
        var time = new ManualTimeProvider();
        var log = new LineLog();
        FallbackInterop? interop = null;
        interop = new FallbackInterop([Pass0, Resid], null)
        {
            Texts = TextsFor(EligibleInFirstRun),
            ShatValue = 0.01f,
            RunByCall = _ =>
            {
                time.Advance(TimeSpan.FromMilliseconds(interop!.RunBudgetMs!.Value + overrunMs));   // the residual run spends the whole budget (no sleeping)
                return RunOf(Row(1, CohFallbackState.GatedOut), Row(2, CohFallbackState.GatedOut, freq: 1100f));
            },
        };
        var decoder = BuildTimed(interop, time, log);
        decoder.SetCoherentFallbackResidualUngated(true);

        var delivered = await RunStaged(decoder);

        interop.RunCalls.Should().Be(1, "the original run is never started");
        IntField(log, "abandoned").Should().Be(EligibleInFirstRun, "the unchanged budget guard counts the NotRun run's eligible candidates abandoned");
        delivered.Single(b => b.Batch == 4).Messages.Should().BeEquivalentTo(new[] { TextOf(1), TextOf(2) }, "the residual run's GatedOut rows are admitted");
        FallbackLine(log).Should().EndWith(", audio=both(residual3), fromOriginal=0, fromResidual=2, inBoth=0, ungated=2.");
    }
}
