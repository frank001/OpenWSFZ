using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2d (FR-108): the lean engine's three batches (batch 1 = round 0, delivered before round 1 starts; batch 2 = rounds 1 to 3; batch 3 = the cross-cycle
/// stage on the final residual), <c>decoder.effort</c>, and the residual buffer. The managed cases run against a scripted lean interop (every outcome exact, the
/// template stage run for real on synthetic audio as in <c>CrossCyclePriorTests</c>); the native cases (<see cref="LeanEngineBatchesNativeTests"/>) run the REAL
/// library on the step 2c fixture. Synthetic Q-prefix content only (NFR-021). No delay anywhere: ordering is proved by blocking the native call on an event the
/// publisher sets, never by timing (TESTING_STRATEGY section 11).
/// </summary>
public sealed class LeanEngineBatchesTests
{
    private static readonly DateTime T0 = new(2026, 11, 25, 12, 0, 0, DateTimeKind.Utc);
    private static DateTime At(int seconds) => T0.AddSeconds(seconds);

    private const string M = "Q1ABC Q1XYZ JO33";            // the message that repeats
    private const string Other = "Q1GHI Q1JKL FN20";
    private const string Other2 = "Q1MNO Q1PQR IO91";
    private const string OtherStation = "Q1AAA Q1BBB RR73";
    private const int MFreq = 1500;
    private const float MDt = 0.30f;
    private const double TestThreshold = 4.0;

    private static byte[] Tones(string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        return tones;
    }

    private static Ft8NativeResult Msg(string message, int freqHz = MFreq, float dt = MDt)
        => new() { FreqHz = freqHz, Dt = dt, Snr = -12, Message = message };

    private static float[] Audio(uint seed, params (string Text, double FreqHz, double Dt)[] messages)
    {
        var x = XcSynth.Noise(seed, 1.0);
        foreach (var m in messages) XcSynth.AddMessage(x, Tones(m.Text), m.FreqHz, m.Dt - CrossCycleTemplateStage.PublishedMinusWsjtxDtS, 0.5);
        return XcSynth.ToFloat(x);
    }

    /// <summary>One scripted lean cycle: round-0 results, the later rounds' results, and whether the native call returns a residual.</summary>
    private sealed record Script(Ft8NativeResult[] Round0, Ft8NativeResult[] Later, bool Residual = true, int Error = 0, bool FireCallback = true, byte[]? LaterTiers = null);

    /// <summary>A lean interop that replays <see cref="Script"/>s; every classic member throws, so a lean cycle that touches one fails the test.</summary>
    private sealed class ScriptedLean : IFt8NativeInterop
    {
        private readonly Queue<Script> _scripts = new();
        public List<LeanCycleParams> Requests { get; } = [];
        public List<string> Events { get; } = [];
        /// <summary>When set, the native call waits on it right after the round-0 hand-off (until the test releases it).</summary>
        public ManualResetEventSlim? Hold { get; set; }
        public volatile bool NativeDone;
        public void Enqueue(Script s) => _scripts.Enqueue(s);

        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request, Action<LeanRound0>? onRound0)
        {
            Requests.Add(request);
            var s = _scripts.Dequeue();
            var results = s.Round0.Concat(s.Later).ToArray();
            var rounds = s.Round0.Select(_ => (byte)0).Concat(s.Later.Select(_ => (byte)1)).ToArray();
            var tiers = s.Round0.Select(_ => LeanTier.A).Concat(s.Later.Select((_, i) => s.LaterTiers is null ? LeanTier.A : s.LaterTiers[i])).ToArray();
            if (s.FireCallback && onRound0 is not null)
            {
                Events.Add("callback");
                onRound0(new LeanRound0(s.Round0, s.Round0.Select(_ => LeanTier.A).ToArray()));
            }
            Hold?.Wait(TimeSpan.FromSeconds(60));
            NativeDone = true;
            Events.Add("native-returns");
            var stats = LeanCycleStats.None(s.Error) with { };
            return new LeanCycleOutcome(results, stats) { Tiers = tiers, Rounds = rounds, Residual = s.Residual && request.WantResidual ? (float[])pcm.Clone() : null };
        }

        private static T Classic<T>() => throw new InvalidOperationException("the classic path was entered");
        public int MaxDecodePasses => Classic<int>();
        public Ft8NativeResult[] DecodeAll(float[] pcm) => Classic<Ft8NativeResult[]>();
        public int[] GetLastPassCounts(int maxPasses) => Classic<int[]>();
        public int[] GetLastCandidateCounts(int maxPasses) => Classic<int[]>();
        public float GetLastNoiseFloorDb() => Classic<float>();
        public int GetHashTableRejectCount() => Classic<int>();
        public int GetH12DisplayingCount() => Classic<int>();
        public int GetH12AmbiguousCount() => Classic<int>();
        public int GetH12DivergentCount() => Classic<int>();
        public int GetH12SuppressedCount() => Classic<int>();
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses) => Classic<(float[], float[], int[])>();
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) => Classic<int>();
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => Classic<(float, float, float, int, int)>();
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => Classic<float[]>();
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => Classic<(float[], float[])>();
        public byte[] EncodeMessage(string message) => Tones(message);   // the template stage's only native call
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => Classic<(float[], float[])>();
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag) => Classic<(int, float[])>();
    }

    private sealed class LineLog : ILogger<Ft8Decoder>
    {
        private readonly ConcurrentQueue<string> _q = new();
        public List<string> Lines => _q.ToList();
        public List<string> XcLines => Lines.Where(l => l.StartsWith("Cross-cycle prior:")).ToList();
        public string LastXc => XcLines.Last();
        public string LastLean => Lines.Last(l => l.Contains("lean:"));
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter) => _q.Enqueue(formatter(state, exception));
        public static int Field(string line, string name)
        {
            var m = Regex.Match(line, name + @"=(-?\d+)");
            m.Success.Should().BeTrue($"the line has {name}=: {line}");
            return int.Parse(m.Groups[1].Value);
        }
    }

    private sealed record Published(int Batch, string Message, int FreqHz, double Dt, int Path);

    private static Ft8Decoder Build(ScriptedLean io, bool xc = false, bool shadow = false, ILogger<Ft8Decoder>? log = null, bool veto = true)
    {
        var d = new Ft8Decoder(new FakeClock(T0), log, interop: io);
        d.SetEngine(DecoderEngine.Lean);
        d.SetCrossCyclePrior(xc);
        d.SetCrossCyclePriorShadow(shadow);
        d.SetCrossCyclePriorThreshold(TestThreshold);
        d.SetCrossCyclePriorColocationVeto(veto);
        return d;
    }

    private static async Task<List<Published>> Cycle(Ft8Decoder d, ScriptedLean io, DateTime start, float[] audio, Script script)
    {
        io.Enqueue(script);
        var got = new List<Published>();
        await d.DecodeStagedAsync(audio, start, null, (n, b) =>
        {
            got.AddRange(b.Select(r => new Published(n, r.Message, r.FreqHz, r.Dt, r.Path)));
            if (b.Count == 0) got.Add(new Published(n, "", 0, 0, -1));   // an empty batch: only batch 1 may be empty
            return Task.CompletedTask;
        });
        return got;
    }

    // ── test 2: an empty batch 1 is still delivered once ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2d test 2: a cycle with nothing decoded delivers batch 1 exactly once, empty, and nothing else")]
    public async Task NothingDecoded_DeliversAnEmptyBatch1Once()
    {
        var io = new ScriptedLean();
        var d = Build(io);
        var rows = await Cycle(d, io, At(0), Audio(1), new Script([], []));
        rows.Should().Equal([new Published(1, "", 0, 0, -1)]);
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 2: a native error with nothing written, and a hand-off that never came, still deliver batch 1 exactly once")]
    public async Task NativeError_StillDeliversBatch1Once()
    {
        var io = new ScriptedLean();
        var d = Build(io);
        var errorRows = await Cycle(d, io, At(0), Audio(1), new Script([], [], Error: LeanCycleStats.ErrFault, FireCallback: false));
        errorRows.Should().Equal([new Published(1, "", 0, 0, -1)], "no results, no hand-off: batch 1 empty, once");

        // The hand-off never came but the call returned results (a failure after the callback would look the same to the caller): batch 1 = round 0, batch 2 = the rest.
        var rows = await Cycle(d, io, At(15), Audio(2), new Script([Msg(M)], [Msg(Other, 1800)], Error: LeanCycleStats.ErrNoMem, FireCallback: false));
        rows.Select(r => (r.Batch, r.Message)).Should().Equal((1, M), (2, Other));
    }

    // ── 2e D5: a publisher exception propagates, and the native call is always awaited ─────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2e D5: an exception from the batch-1 publisher propagates (as in classic) and the native call is awaited first: the decode does not finish until the native call has")]
    public async Task PublisherException_Propagates_AfterTheNativeCallIsAwaited()
    {
        var io = new ScriptedLean();
        var hold = new ManualResetEventSlim(false);
        io.Hold = hold;
        io.Enqueue(new Script([Msg(M)], [Msg(Other, 1800)]));
        var d = Build(io);
        var publisherThrew = new ManualResetEventSlim(false);

        var decode = d.DecodeStagedAsync(Audio(1), At(0), null, (n, b) =>
        {
            publisherThrew.Set();
            throw new InvalidOperationException("publisher failed (test double)");
        });

        publisherThrew.Wait(TimeSpan.FromSeconds(60)).Should().BeTrue("the publisher was reached while the native call was held after round 0");
        decode.IsCompleted.Should().BeFalse("the native task is awaited before the publisher's exception goes on");
        hold.Set();
        var act = async () => await decode;
        await act.Should().ThrowAsync<InvalidOperationException>().WithMessage("publisher failed*");
        io.NativeDone.Should().BeTrue("the native call ran to its end first");
    }

    // ── test 3: one text, once per cycle across the batches ──────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2d test 3: a text found in round 0 and again in a later round is published in batch 1 only")]
    public async Task OneTextOncePerCycle_AcrossBatches()
    {
        var io = new ScriptedLean();
        var d = Build(io);
        var rows = await Cycle(d, io, At(0), Audio(1), new Script([Msg(M), Msg(Other, 1800)], [Msg(M, 1503), Msg(Other2, 2100)]));
        rows.Select(r => (r.Batch, r.Message)).Should().Equal((1, M), (1, Other), (2, Other2));
    }

    [Fact(DisplayName = "FR-108: DR-2 2d D1: batch 2 is delivered only when non-empty, batch 3 only when non-empty, and the provenance tags are the classic ones")]
    public async Task EmptyBatches_AreNotDelivered_AndTagsAreClassic()
    {
        var io = new ScriptedLean();
        var d = Build(io, xc: true);
        var rows = await Cycle(d, io, At(0), Audio(1), new Script([Msg(M)], []));
        rows.Select(r => r.Batch).Should().Equal(1);

        var rows2 = await Cycle(d, io, At(15), Audio(2), new Script([Msg(Other)], [Msg(Other2, 2100)], LaterTiers: [LeanTier.B]));
        rows2.Select(r => (r.Batch, r.Message, r.Path)).Should().Equal((1, Other, Ft8Decoder.PathOrdinary), (2, Other2, Ft8Decoder.PathFallback));
    }

    // ── test 4: priors ───────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2d test 4: the prior store holds the batch-1 and batch-2 messages and a batch-3 detection never enters it")]
    public async Task Priors_AreBatches1And2_NeverBatch3()
    {
        var io = new ScriptedLean();
        var d = Build(io, xc: true);
        await Cycle(d, io, At(0), Audio(1), new Script([Msg(M), Msg(Other, 1800)], [Msg(Other2, 2100)]));
        d.CrossCyclePriorStoreCount.Should().Be(3, "two from batch 1 and one from batch 2");

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), new Script([Msg(OtherStation, 800)], []));
        rows.Should().Contain(p => p.Batch == Ft8Decoder.LeanBatchXc && p.Message == M, "control: batch 3 DID publish M");
        d.CrossCyclePriorStoreCount.Should().Be(4, "3 from t0 and the one batch-1 message of t0 + 30 s; the batch-3 M is not stored (no chaining)");
    }

    // ── test 5: XC on the lean residual ──────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2d test 5: a message published 30 s earlier and present in this cycle's audio is found on the lean residual and published as batch 3 with PathTemplate")]
    public async Task Xc_FindsAPriorOnTheLeanResidual_AsBatch3()
    {
        var log = new LineLog();
        var io = new ScriptedLean();
        var d = Build(io, xc: true, log: log);
        await Cycle(d, io, At(0), Audio(1), new Script([Msg(M), Msg(Other, 1800)], []));

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), new Script([Msg(Other2, 2100)], []));

        var b3 = rows.Where(p => p.Batch == Ft8Decoder.LeanBatchXc).ToList();
        b3.Should().ContainSingle();
        b3[0].Message.Should().Be(M);
        b3[0].Path.Should().Be(Ft8Decoder.PathTemplate);
        b3[0].FreqHz.Should().Be(MFreq);
        rows.Where(p => p.Batch < Ft8Decoder.LeanBatchXc).Select(p => p.Message).Should().Equal(new[] { Other2 });
        var line = log.LastXc;
        line.Should().Contain("outcome=ran").And.Contain("batch=3");
        LineLog.Field(line, "published").Should().Be(1);
        log.LastLean.Should().Contain("xc=ran xcDetected=1").And.Contain("b1=1 b2=0 b3=1");
        io.Requests.Last().WantResidual.Should().BeTrue("the residual is asked for only while the stage is on");
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 5: a cycle in which nothing was subtracted has no residual, and the stage is a counted, logged skip")]
    public async Task Xc_NoResidual_IsACountedSkip()
    {
        var log = new LineLog();
        var io = new ScriptedLean();
        var d = Build(io, xc: true, log: log);
        await Cycle(d, io, At(0), Audio(1), new Script([Msg(M)], []));

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), new Script([], [], Residual: false));

        rows.Select(r => r.Batch).Should().Equal(1);
        log.LastXc.Should().Contain("outcome=skipped-no-residual");
        LineLog.Field(log.LastXc, "priorsLive").Should().Be(1);
        LineLog.Field(log.LastXc, "testedLive").Should().Be(0);
        log.LastLean.Should().Contain("xc=skipped-no-residual xcDetected=0");
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 5: the co-location veto reads the lean cycle's decodes (a different text next to the detection vetoes it), and with the veto off the detection is published")]
    public async Task Xc_Veto_ReadsTheLeanCyclesDecodes()
    {
        async Task<(List<Published> Rows, LineLog Log)> Go(bool veto)
        {
            var log = new LineLog();
            var io = new ScriptedLean();
            var d = Build(io, xc: true, log: log, veto: veto);
            await Cycle(d, io, At(0), Audio(1), new Script([Msg(M), Msg(Other, 1800)], []));
            // Cycle t: M's signal is at its place and the lean cycle decodes ANOTHER message 1 Hz and 0.05 s away, in round 1 (batch 2).
            var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), new Script([], [Msg(OtherStation, MFreq + 1, MDt + 0.05f)]));
            return (rows, log);
        }

        var vetoed = await Go(true);
        vetoed.Rows.Should().NotContain(p => p.Batch == Ft8Decoder.LeanBatchXc);
        LineLog.Field(vetoed.Log.LastXc, "vetoedColocated").Should().Be(1);

        var off = await Go(false);
        off.Rows.Should().Contain(p => p.Batch == Ft8Decoder.LeanBatchXc && p.Message == M);
        LineLog.Field(off.Log.LastXc, "vetoedColocated").Should().Be(0);
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 5: the shadow null runs on the lean residual, counts its detections, and publishes and stores nothing")]
    public async Task Xc_Shadow_RunsOnTheLeanResidual()
    {
        var log = new LineLog();
        var io = new ScriptedLean();
        var d = Build(io, xc: true, shadow: true, log: log);
        await Cycle(d, io, At(0), Audio(1), new Script([Msg(M)], []));
        int before = d.CrossCyclePriorStoreCount;

        var rows = await Cycle(d, io, At(15), Audio(2, (M, MFreq, MDt)), new Script([Msg(Other2, 2100)], []));

        rows.Should().NotContain(p => p.Batch == Ft8Decoder.LeanBatchXc, "a shadow detection is never published");
        LineLog.Field(log.LastXc, "shadowDetected").Should().Be(1);
        LineLog.Field(log.LastXc, "detected").Should().Be(0);
        d.CrossCyclePriorStoreCount.Should().Be(before + 1, "only this cycle's batch-1 message; the shadow detection is not stored");
    }

    [Fact(DisplayName = "FR-108: DR-2 2d D3: with the stage off nothing is asked for, written or stored, and the single-batch entry still returns every result as one list")]
    public async Task XcOff_AndTheSingleBatchEntry()
    {
        var log = new LineLog();
        var io = new ScriptedLean();
        var d = Build(io, xc: false, log: log);
        var rows = await Cycle(d, io, At(0), Audio(1), new Script([Msg(M)], [Msg(Other, 1800)]));
        rows.Select(r => r.Batch).Should().Equal(1, 2);
        io.Requests[0].WantResidual.Should().BeFalse();
        log.XcLines.Should().BeEmpty();
        d.CrossCyclePriorStoreCount.Should().Be(0);

        io.Enqueue(new Script([Msg(M)], [Msg(Other, 1800)]));
        var all = await d.DecodeAsync(Audio(2), At(15), null);
        all.Select(r => r.Message).Should().Equal(M, Other);
    }

    // ── test 6: effort ───────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2d test 6: effort fast asks for no tier B and one round, normal for neither, and the setting is read once per cycle")]
    public async Task Effort_IsReadOncePerCycle()
    {
        var log = new LineLog();
        var io = new ScriptedLean();
        var d = Build(io, log: log);
        d.Effort.Should().Be(DecoderEffort.Normal, "the default");

        d.SetEffort(DecoderEffort.Fast);
        await Cycle(d, io, At(0), Audio(1), new Script([], []));
        d.SetEffort(DecoderEffort.Normal);
        await Cycle(d, io, At(15), Audio(2), new Script([], []));

        io.Requests[0].Should().Match<LeanCycleParams>(r => r.NoTierB && r.MaxRounds == 1 && r.Rounds);
        io.Requests[1].Should().Match<LeanCycleParams>(r => !r.NoTierB && r.MaxRounds == 0 && r.Rounds);
        log.Lines.Where(l => l.Contains("lean:")).Select(l => Regex.Match(l, @"effort=(\w+)").Groups[1].Value).Should().Equal("fast", "normal");
    }

    [Theory(DisplayName = "FR-108: DR-2 2d test 6: an absent, empty or unknown effort reads normal; only the word fast (any case) reads fast")]
    [InlineData(null, DecoderEffort.Normal)]
    [InlineData("", DecoderEffort.Normal)]
    [InlineData("normal", DecoderEffort.Normal)]
    [InlineData("turbo", DecoderEffort.Normal)]
    [InlineData("fastest", DecoderEffort.Normal)]
    [InlineData("fast", DecoderEffort.Fast)]
    [InlineData(" FAST ", DecoderEffort.Fast)]
    public void Effort_UnknownReadsNormal(string? value, DecoderEffort expected)
    {
        DecoderEffortNames.Parse(value).Should().Be(expected);
        new DecoderConfig { Effort = value ?? DecoderEffortNames.Normal }.GetEffortKind().Should().Be(expected);
    }
}

/// <summary>
/// DR-2 step 2d against the REAL native library on the step 2c masked-signal fixture: batch 1 leaves before round 1 (proved by blocking the native call on an event
/// the publisher sets), an empty batch 1, the effort flags, and determinism including the residual buffer.
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineBatchesNativeTests(ITestOutputHelper output) : IDisposable
{
    private static readonly DateTime T0 = new(2026, 11, 25, 12, 0, 0, DateTimeKind.Utc);
    private const string StrongMessage = "CQ Q1ABC JO22";
    private const string WeakMessage = "Q2DEF Q3GHI -07";

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    /// <summary>The real lean entry with two seams: the round-0 callback may be wrapped (to block the native call) and a hook runs when the native call has returned.</summary>
    private sealed class RealLean : IFt8NativeInterop
    {
        public Func<Action<LeanRound0>, Action<LeanRound0>>? WrapCallback { get; init; }
        public Action? AfterNative { get; init; }
        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request, Action<LeanRound0>? onRound0)
        {
            var wrapped = onRound0 is not null && WrapCallback is not null ? WrapCallback(onRound0) : onRound0;
            var outcome = Ft8LibInterop.DecodeLeanCycle(pcm, request, wrapped);
            AfterNative?.Invoke();
            return outcome;
        }
        private static T Classic<T>() => throw new InvalidOperationException("the classic path was entered");
        public int MaxDecodePasses => Classic<int>();
        public Ft8NativeResult[] DecodeAll(float[] pcm) => Classic<Ft8NativeResult[]>();
        public int[] GetLastPassCounts(int maxPasses) => Classic<int[]>();
        public int[] GetLastCandidateCounts(int maxPasses) => Classic<int[]>();
        public float GetLastNoiseFloorDb() => Classic<float>();
        public int GetHashTableRejectCount() => Classic<int>();
        public int GetH12DisplayingCount() => Classic<int>();
        public int GetH12AmbiguousCount() => Classic<int>();
        public int GetH12DivergentCount() => Classic<int>();
        public int GetH12SuppressedCount() => Classic<int>();
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses) => Classic<(float[], float[], int[])>();
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) => Classic<int>();
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => Classic<(float, float, float, int, int)>();
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => Classic<float[]>();
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => Classic<(float[], float[])>();
        public byte[] EncodeMessage(string message) { var t = new byte[79]; Ft8LibInterop.EncodeMessage(message, t); return t; }
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => Classic<(float[], float[])>();
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag) => Classic<(int, float[])>();
    }

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 1: batch 1 (the strong signal) is delivered while the native call is still inside round 0's hand-off, before round 1 exists; batch 2 holds the masked one; batch 3 is not delivered")]
    public async Task Batch1_LeavesBeforeRound1()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();
        var batch1Seen = new ManualResetEventSlim(false);
        bool handOffTimedOut = false, nativeReturned = false;
        var io = new RealLean
        {
            // The native call is held INSIDE the round-0 hand-off until the publisher has batch 1: if batch 1 could only leave after the call, this would time out.
            WrapCallback = cb => r0 => { cb(r0); if (!batch1Seen.Wait(TimeSpan.FromSeconds(120))) handOffTimedOut = true; },
            AfterNative = () => nativeReturned = true,
        };
        var d = new Ft8Decoder(new FakeClock(T0), null, interop: io);
        d.SetEngine(DecoderEngine.Lean);
        var seenAt = new List<(int Batch, string[] Texts, bool NativeAlreadyReturned)>();

        await d.DecodeStagedAsync(pcm, T0, null, (n, b) =>
        {
            seenAt.Add((n, b.Select(r => r.Message).ToArray(), nativeReturned));
            if (n == 1) batch1Seen.Set();
            return Task.CompletedTask;
        });
        Ft8LibInterop.HashStateRestore(start);

        handOffTimedOut.Should().BeFalse("batch 1 reached the publisher while the native call was held inside round 0's hand-off");
        seenAt.Select(s => s.Batch).Should().Equal([1, 2], "batch 3 is empty (the stage is off) and not delivered");
        seenAt[0].Texts.Should().Equal([StrongMessage]);
        seenAt[0].NativeAlreadyReturned.Should().BeFalse("batch 1 was published before the native call returned");
        seenAt[1].Texts.Should().Equal([WeakMessage], "round 1 found the masked signal");
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 2: real audio with nothing decodable delivers one empty batch 1 and nothing else")]
    public async Task RealNoise_DeliversOneEmptyBatch1()
    {
        var rng = new Random(5);
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++) pcm[i] = (float)((rng.NextDouble() - 0.5) * 0.2);
        byte[] start = SaveHashState();
        var d = new Ft8Decoder(new FakeClock(T0), null, interop: new RealLean());
        d.SetEngine(DecoderEngine.Lean);
        var seen = new List<(int Batch, int Count)>();

        await d.DecodeStagedAsync(pcm, T0, null, (n, b) => { seen.Add((n, b.Count)); return Task.CompletedTask; });
        Ft8LibInterop.HashStateRestore(start);

        seen.Should().Equal([(1, 0)]);
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 6: with effort fast the native call runs no tier B and at most one round; with normal it attempts tier B and the masked signal is found in the same round")]
    public void Effort_Fast_RunsNoTierB_AndOneRound()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();

        var normal = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true));
        Ft8LibInterop.HashStateRestore(start);
        var fast = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, MaxRounds: 1, NoTierB: true));
        Ft8LibInterop.HashStateRestore(start);

        normal.Stats.TierBAttempted.Should().BeGreaterThan(0, "precondition: normal effort runs tier B on the candidates that failed tier A");
        fast.Stats.TierBEligible.Should().Be(0);
        fast.Stats.TierBAttempted.Should().Be(0);
        fast.Stats.RoundsRun.Should().BeLessThanOrEqualTo(1);
        fast.Results.Select(r => r.Message.TrimEnd()).Should().Contain(StrongMessage).And.Contain(WeakMessage, "round 1 is kept in fast");
        normal.Stats.RoundsRun.Should().BeGreaterThanOrEqualTo(1);
        output.WriteLine($"tier B attempted normal={normal.Stats.TierBAttempted} fast={fast.Stats.TierBAttempted}; rounds normal={normal.Stats.RoundsRun} fast={fast.Stats.RoundsRun}");
    }

    [Fact(DisplayName = "FR-108: DR-2 2d test 8: the same audio and starting hash state give byte-identical results, tiers, rounds and residual bytes at 1, 2 and 4 threads; the round-0 hand-off equals round 0 of the result")]
    public void Deterministic_IncludingTheResidual()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();
        var runs = new List<(string Text, byte[] Residual)>();
        foreach (int threads in new[] { 1, 2, 4, 8, 16 })
        {
            Ft8LibInterop.HashStateRestore(start);
            LeanRound0? handOff = null;
            var o = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, Rounds: true, WantResidual: true), r0 => handOff = r0);
            o.Stats.Error.Should().Be(LeanCycleStats.Ok);
            o.Residual.Should().NotBeNull("a signal was subtracted");
            handOff.Should().NotBeNull();
            var round0 = o.Results.Where((_, i) => o.Rounds[i] == 0).ToArray();
            handOff!.Results.Select(r => r.Message).Should().Equal(round0.Select(r => r.Message));
            handOff.Results.Select(r => r.FreqHz).Should().Equal(round0.Select(r => r.FreqHz));
            string text = string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{o.Tiers[i]}|{o.Rounds[i]}"));
            runs.Add((text, MemoryMarshal.AsBytes(o.Residual.AsSpan()).ToArray()));
        }
        Ft8LibInterop.HashStateRestore(start);

        runs.Select(r => r.Text).Distinct().Should().ContainSingle("byte-identical results, tiers and rounds");
        runs[1].Residual.AsSpan().SequenceEqual(runs[0].Residual).Should().BeTrue("the residual buffer is the same bytes at 2 threads as at 1");
        runs[2].Residual.AsSpan().SequenceEqual(runs[0].Residual).Should().BeTrue("and at 4");
        runs[0].Residual.AsSpan().SequenceEqual(MemoryMarshal.AsBytes(pcm.AsSpan())).Should().BeFalse("the residual is not the original audio");
    }
}
