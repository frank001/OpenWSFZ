using System.Collections.Concurrent;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// The optional third decode pass, "Deep" (#240 step 1, requirements B1 to B10): one more incremental
/// subtract-and-decode round on the residual buffer, published as batch 3 through
/// <see cref="Ft8Decoder.DecodeStagedAsync"/>. The decode and fit calls are faked (scripted per call); the payload
/// de-duplication uses the real native encoder, as in <see cref="TwoStageDecodeTests"/>.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, order and identity.</para>
/// </summary>
public sealed class ThirdPassDeepTests
{
    private static readonly DateTime CycleStart = new(2026, 10, 18, 12, 0, 0, DateTimeKind.Utc);

    /// <summary>What the fake fit subtracts at sample 0, so the buffer handed to each stage is identifiable.</summary>
    private const float ShatMarker = 0.25f;

    private static Ft8NativeResult Msg(string message, int freqHz = 1500, float dt = 0.2f, int snr = -10)
        => new() { FreqHz = freqHz, Dt = dt, Snr = snr, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private enum FitMode { Ok, DeadlineRc, Throw }

    /// <summary>
    /// DecodeAll answers by call number (1 = pass 0, 2 = residual, 3 = third pass). The analytic-signal call count tells the
    /// fit which stage it belongs to (1 = residual pass, 2 = third pass), and records what each stage worked on.
    /// </summary>
    private sealed class StagedInterop(params Ft8NativeResult[][] decodes) : IFt8NativeInterop
    {
        private readonly object _gate = new();
        public int MaxDecodePasses => 2;
        public int DecodeAllCallCount { get; private set; }
        public int AnalyticCallCount { get; private set; }

        /// <summary>Sample 0 of the buffer each DecodeAll call received (1-based call number to value).</summary>
        public Dictionary<int, float> DecodeAllSample0 { get; } = new();

        /// <summary>Sample 0 of the buffer each analytic-signal call received (1-based).</summary>
        public Dictionary<int, float> AnalyticSample0 { get; } = new();

        /// <summary>Fit calls per stage (stage 1 = residual pass, stage 2 = third pass).</summary>
        public Dictionary<int, int> FitCalls { get; } = new();

        public FitMode ResidualFit { get; init; } = FitMode.Ok;
        public FitMode ThirdFit    { get; init; } = FitMode.Ok;

        /// <summary>Invoked at the start of every DecodeAll call (for the order-of-delivery test).</summary>
        public Action<int>? OnDecodeAll { get; init; }

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            int n;
            lock (_gate) { n = ++DecodeAllCallCount; DecodeAllSample0[n] = pcm[0]; }
            OnDecodeAll?.Invoke(n);
            return n <= decodes.Length ? decodes[n - 1] : [];
        }

        public byte[] EncodeMessage(string message)
        {
            var tones = new byte[79];
            Ft8LibInterop.EncodeMessage(message, tones);
            return tones;
        }

        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        {
            lock (_gate) { AnalyticCallCount++; AnalyticSample0[AnalyticCallCount] = pcm[0]; }
            return (new float[pcm.Length], new float[pcm.Length]);
        }

        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        {
            int stage;
            lock (_gate) { stage = AnalyticCallCount; FitCalls[stage] = FitCalls.GetValueOrDefault(stage) + 1; }
            var mode = stage == 1 ? ResidualFit : ThirdFit;
            if (mode == FitMode.Throw) throw new NativeAccessViolationException();
            var shat = new float[180_000];
            shat[0] = ShatMarker;
            return (mode == FitMode.DeadlineRc ? Ft8LibInterop.SubfeasRcCancelled : 0, shat);
        }

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

    private static Ft8Decoder Build(IFt8NativeInterop interop, DecodingDepth depth, ILogger<Ft8Decoder>? log = null)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop: interop);
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(depth);
        return d;
    }

    /// <summary>Runs one cycle through <see cref="Ft8Decoder.DecodeStagedAsync"/> and records (batch number, messages) in delivery order.</summary>
    private static async Task<List<(int Batch, string[] Messages)>> RunStaged(Ft8Decoder decoder)
    {
        var got = new List<(int, string[])>();
        await decoder.DecodeStagedAsync(LoudPcm(), CycleStart, null, (n, b) =>
        {
            got.Add((n, b.Select(r => r.Message).ToArray()));
            return Task.CompletedTask;
        });
        return got;
    }

    private static readonly Ft8NativeResult[] Pass0 = [Msg("Q1ABC Q1XYZ JO33"), Msg("Q1GHI Q1JKL FN20", 1800)];
    private static readonly Ft8NativeResult[] Resid = [Msg("Q1DEF Q1UVW EN37", 2100)];
    private static readonly Ft8NativeResult[] Third = [Msg("Q1MNO Q1PQR IO91", 2400)];

    // ── B1 / B2: the default, and Normal is inert ───────────────────────────────────────────────────────────

    [Fact(DisplayName = "B1: decoder.decodingDepth defaults to Deep in the config record (the 2026-10-19 flip) while a bare decoder stays Normal")]
    public void Config_DefaultsToDeep_BareDecoderStaysNormal()
    {
        new DecoderConfig().DecodingDepth.Should().Be(DecodingDepth.Deep);
        new Ft8Decoder(new FakeClock(CycleStart), null, interop: new StagedInterop()).DecodingDepth
            .Should().Be(DecodingDepth.Normal, "a decoder that was never told anything is Normal");

    }

    [Fact(DisplayName = "B2: Normal is inert — DecodeStagedAsync delivers exactly batch 1 and batch 2 as DecodeTwoStageAsync does, no third pass, no counters, no third-pass line")]
    public async Task Normal_IsInert()
    {
        var log = new LineLog();
        var interop = new StagedInterop(Pass0, Resid, Third);
        var normal = Build(interop, DecodingDepth.Normal, log);

        var staged = await RunStaged(normal);

        // The reference: the existing two-stage entry on an identically scripted interop.
        IReadOnlyList<DecodeResult>? ref1 = null;
        var ref2 = await Build(new StagedInterop(Pass0, Resid, Third), DecodingDepth.Normal)
            .DecodeTwoStageAsync(LoudPcm(), CycleStart, null, b => { ref1 = b; return Task.CompletedTask; });

        staged.Select(s => s.Batch).Should().Equal(1, 2);
        staged[0].Messages.Should().Equal(ref1!.Select(r => r.Message));
        staged[1].Messages.Should().Equal(ref2.Select(r => r.Message));
        interop.DecodeAllCallCount.Should().Be(2, "pass 0 and the residual decode only: the third decode never ran");
        interop.AnalyticCallCount.Should().Be(1);
        normal.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Normal", 0, 0, 0, 0, 0, 0));
        log.Lines.Should().NotContain(l => l.StartsWith("Third pass:"));
    }

    [Fact(DisplayName = "B2: Deep set but the caller is the plain two-stage entry — no third pass can be delivered, so none runs")]
    public async Task Deep_WithPlainTwoStageEntry_RunsNoThirdPass()
    {
        var interop = new StagedInterop(Pass0, Resid, Third);
        var deep = Build(interop, DecodingDepth.Deep);

        var batch2 = await deep.DecodeTwoStageAsync(LoudPcm(), CycleStart, null, _ => Task.CompletedTask);

        batch2.Select(r => r.Message).Should().Equal("Q1DEF Q1UVW EN37");
        interop.DecodeAllCallCount.Should().Be(2);
        deep.GetThirdPassStatus().Runs.Should().Be(0);
    }

    // ── B3 / B5: additive, batch 3 ─────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "B3+B5: Deep — batches 1 and 2 equal Normal's, batch 3 is the new third-pass decode, delivered 1, 2, 3")]
    public async Task Deep_AdditiveOnly_Batch3Appended()
    {
        var normal = await RunStaged(Build(new StagedInterop(Pass0, Resid, Third), DecodingDepth.Normal));
        var deep   = await RunStaged(Build(new StagedInterop(Pass0, Resid, Third), DecodingDepth.Deep));

        deep.Select(s => s.Batch).Should().Equal(1, 2, 3);
        deep[0].Messages.Should().Equal(normal[0].Messages, "pass 0 is untouched");
        deep[1].Messages.Should().Equal(normal[1].Messages, "the residual pass is untouched");
        deep[2].Messages.Should().Equal("Q1MNO Q1PQR IO91");
    }

    [Fact(DisplayName = "B5: batch 2 is delivered BEFORE the third pass starts (the third decode has not run when batch 2 leaves)")]
    public async Task Batch2_LeavesBeforeThirdPassStarts()
    {
        int decodeAllAtBatch2 = -1;
        StagedInterop? interop = null;
        interop = new StagedInterop(Pass0, Resid, Third);
        var deep = Build(interop, DecodingDepth.Deep);

        await deep.DecodeStagedAsync(LoudPcm(), CycleStart, null, (n, _) =>
        {
            if (n == 2) decodeAllAtBatch2 = interop.DecodeAllCallCount;
            return Task.CompletedTask;
        });

        decodeAllAtBatch2.Should().Be(2, "only pass 0 and the residual decode had run when batch 2 was handed over");
        interop.DecodeAllCallCount.Should().Be(3);
    }

    [Fact(DisplayName = "Incremental: the third pass fits ONLY the residual pass's new signals, from the residual buffer, and decodes the buffer with them subtracted")]
    public async Task ThirdPass_IsIncremental()
    {
        var interop = new StagedInterop(Pass0, Resid, Third);
        await RunStaged(Build(interop, DecodingDepth.Deep));

        interop.FitCalls[1].Should().Be(2, "the residual pass fits each of the two pass-0 signals");
        interop.FitCalls[2].Should().Be(1, "the third pass fits only the residual pass's ONE new signal: pass-0 signals are not refitted");

        float norm = interop.DecodeAllSample0[1];                 // the normalised PCM, sample 0
        interop.AnalyticSample0[1].Should().Be(norm, "the residual pass analyses the normalised PCM");
        interop.AnalyticSample0[2].Should().BeApproximately(norm - 2 * ShatMarker, 1e-6f,
            "the third pass starts from the residual buffer (both pass-0 signals already subtracted), not from the normalised PCM");
        interop.DecodeAllSample0[2].Should().BeApproximately(norm - 2 * ShatMarker, 1e-6f);
        interop.DecodeAllSample0[3].Should().BeApproximately(norm - 3 * ShatMarker, 1e-6f,
            "the third decode runs on the residual with the new signal subtracted too");
    }

    [Fact(DisplayName = "Dedup: a third-pass decode of a pass-0 or residual-pass message is not new; only the genuinely new one is batch 3")]
    public async Task ThirdPass_DedupsAgainstPass0AndResidual()
    {
        Ft8NativeResult[] third = [Msg("Q1ABC Q1XYZ JO33"), Msg("Q1DEF Q1UVW EN37", 2100), Msg("Q1MNO Q1PQR IO91", 2400)];
        var deep = Build(new StagedInterop(Pass0, Resid, third), DecodingDepth.Deep);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1, 2, 3);
        got[2].Messages.Should().Equal("Q1MNO Q1PQR IO91");
        deep.GetThirdPassStatus().Decodes.Should().Be(1);
    }

    [Fact(DisplayName = "Dedup: when the third pass finds nothing new, batch 3 is not delivered (a run, with 0 decodes)")]
    public async Task ThirdPass_NothingNew_NoBatch3()
    {
        var deep = Build(new StagedInterop(Pass0, Resid, [Msg("Q1ABC Q1XYZ JO33")]), DecodingDepth.Deep);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1, 2);
        deep.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Deep", 1, 0, 0, 0, 0, 0));
    }

    // ── Skip rules ──────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "Skip rule: the residual pass returned no new decode -> skipped-no-new, no third decode, one line, counter")]
    public async Task Skip_NoNew()
    {
        var log = new LineLog();
        var interop = new StagedInterop(Pass0, [Msg("Q1ABC Q1XYZ JO33")], Third);   // the residual only re-finds a pass-0 message
        var deep = Build(interop, DecodingDepth.Deep, log);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1);
        interop.DecodeAllCallCount.Should().Be(2, "no third decode");
        deep.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Deep", 0, 1, 0, 0, 0, 0));
        log.Lines.Single(l => l.StartsWith("Third pass:")).Should().Be(
            "Third pass: newDecodes=0 elapsedMs=0 outcome=skipped-no-new fittedSignals=0");
    }

    [Fact(DisplayName = "Skip rule: the residual pass was abandoned (budget) -> skipped-abandoned, nothing published for 2 or 3")]
    public async Task Skip_ResidualAbandoned()
    {
        var log = new LineLog();
        var interop = new StagedInterop(Pass0, Resid, Third) { ResidualFit = FitMode.DeadlineRc };
        var deep = Build(interop, DecodingDepth.Deep, log);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1);
        interop.DecodeAllCallCount.Should().Be(1, "the abandoned residual pass never decoded");
        deep.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Deep", 0, 0, 1, 0, 0, 0));
        log.Lines.Single(l => l.StartsWith("Third pass:")).Should().Be(
            "Third pass: newDecodes=0 elapsedMs=0 outcome=skipped-abandoned fittedSignals=0");
    }

    [Fact(DisplayName = "Skip rule: the residual pass failed (contained exception) -> skipped-abandoned as well")]
    public async Task Skip_ResidualFailed()
    {
        var interop = new StagedInterop(Pass0, Resid, Third) { ResidualFit = FitMode.Throw };
        var deep = Build(interop, DecodingDepth.Deep);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1);
        deep.GetThirdPassStatus().SkippedAbandoned.Should().Be(1);
    }

    // ── B4: all-or-nothing ─────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "B4: the third pass abandoned on the budget publishes nothing and keeps batches 1 and 2")]
    public async Task ThirdPass_Abandoned_PublishesNothing_KeepsBatches1And2()
    {
        var log = new LineLog();
        var interop = new StagedInterop(Pass0, Resid, Third) { ThirdFit = FitMode.DeadlineRc };
        var deep = Build(interop, DecodingDepth.Deep, log);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1, 2);
        got[1].Messages.Should().Equal("Q1DEF Q1UVW EN37");
        interop.DecodeAllCallCount.Should().Be(2, "an abandoned third pass never reaches its decode");
        deep.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Deep", 1, 0, 0, 1, 0, 0));
        log.Lines.Single(l => l.StartsWith("Third pass:")).Should().MatchRegex(
            @"^Third pass: newDecodes=0 elapsedMs=\d+ outcome=abandoned fittedSignals=1$");
    }

    [Fact(DisplayName = "B4: a third pass that fails (contained exception) publishes nothing and keeps batches 1 and 2")]
    public async Task ThirdPass_Failed_PublishesNothing_KeepsBatches1And2()
    {
        var log = new LineLog();
        var interop = new StagedInterop(Pass0, Resid, Third) { ThirdFit = FitMode.Throw };
        var deep = Build(interop, DecodingDepth.Deep, log);

        var got = await RunStaged(deep);

        got.Select(s => s.Batch).Should().Equal(1, 2);
        deep.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Deep", 1, 0, 0, 0, 1, 0));
        log.Lines.Single(l => l.StartsWith("Third pass:")).Should().Contain("outcome=failed");
    }

    // ── B6 / B7: counters and the log line ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "B6+B7: a Deep cycle that runs reports the decodes in the counters and writes one aggregates-only line")]
    public async Task Ran_CountersAndLogLine()
    {
        var log = new LineLog();
        var deep = Build(new StagedInterop(Pass0, Resid, Third), DecodingDepth.Deep, log);

        await RunStaged(deep);

        deep.GetThirdPassStatus().Should().Be(new ThirdPassStatus("Deep", 1, 0, 0, 0, 0, 1));
        var line = log.Lines.Single(l => l.StartsWith("Third pass:"));
        line.Should().MatchRegex(@"^Third pass: newDecodes=1 elapsedMs=\d+ outcome=ran fittedSignals=1$");
        line.Should().NotContain("Q1", "HK-037: aggregates only, no message text");
    }

    [Fact(DisplayName = "B6: the counters accumulate across cycles and the depth read-back follows SetDecodingDepth")]
    public async Task Counters_AccumulateAcrossCycles_AndDepthReadBack()
    {
        var interop = new StagedInterop(Pass0, Resid, Third);
        var deep = Build(interop, DecodingDepth.Deep);
        await RunStaged(deep);
        deep.GetThirdPassStatus().DecodingDepth.Should().Be("Deep");

        deep.SetDecodingDepth(DecodingDepth.Normal);
        deep.GetThirdPassStatus().DecodingDepth.Should().Be("Normal", "the value the decoder is using, not the value it was built with");
        deep.GetThirdPassStatus().Runs.Should().Be(1, "counters are process-lifetime: switching back does not clear them");
    }

    [Fact(DisplayName = "Silent cycle / no pass-0 decodes: Deep adds nothing — one (empty) batch 1, no residual, no third pass")]
    public async Task SilentOrEmpty_NoThirdPass()
    {
        var deep = Build(new StagedInterop([], Resid, Third), DecodingDepth.Deep);

        var got = await RunStaged(deep);

        got.Should().ContainSingle().Which.Batch.Should().Be(1);
        deep.GetThirdPassStatus().Runs.Should().Be(0);
    }

    [Fact(DisplayName = "Flag OFF: Deep has no effect — the single-batch decode, residual pass and third pass never touched")]
    public async Task SubtractionOff_DeepHasNoEffect()
    {
        var interop = new StagedInterop(Pass0, Resid, Third);
        var d = Build(interop, DecodingDepth.Deep);
        d.SetSubtractionEnabled(false);

        var got = await RunStaged(d);

        got.Should().ContainSingle().Which.Batch.Should().Be(1);
        interop.DecodeAllCallCount.Should().Be(1);
        interop.AnalyticCallCount.Should().Be(0);
    }
}
