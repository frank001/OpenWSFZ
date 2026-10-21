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
/// <c>decoder.coherentFallbackEnabled</c> (default false). Requirements R6-triple-prime / R7-triple-prime (the fallback starts only after the
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
                if (n == 1) DecodeAllThreadId = Environment.CurrentManagedThreadId;
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

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        {
            lock (_gate) { RunCalls++; Calls.Add("run"); RunBudgetMs = budgetMs; RunWorkers = workers; RunPcm = pcm; OrdinaryActiveAtRun = _ordinaryActive; }
            if (RunThrows is not null) throw RunThrows;
            return run;
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
            => (0, new float[180_000]);

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

    private static async Task<List<Delivered>> RunStaged(Ft8Decoder decoder, FallbackInterop? interop = null, Action<int>? onBatch = null)
    {
        var got = new List<Delivered>();
        await decoder.DecodeStagedAsync(LoudPcm(), CycleStart, null, (n, b) =>
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

    // ── R10: the flag ─────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "R10: decoder.coherentFallbackEnabled defaults to false in the config record, a bare decoder, and an absent key")]
    public void Flag_DefaultsToFalse()
    {
        new DecoderConfig().CoherentFallbackEnabled.Should().BeFalse();
        new Ft8Decoder(new FakeClock(CycleStart), null, interop: new FallbackInterop([], null)).CoherentFallbackEnabled.Should().BeFalse();
        System.Text.Json.JsonSerializer.Deserialize<DecoderConfig>("""{"kMinScorePass2":10}""")!
            .CoherentFallbackEnabled.Should().BeFalse("a config written before the key existed loads false");
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
        @"workers=4, fbStartMs=(\d+), fbWallMs=(\d+), batch=(\d), batch4Published=([01]), batch4PublishMs=(-?\d+)\.$", RegexOptions.CultureInvariant);

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
        line.Should().Contain("published=0,").And.Contain("batch=4, batch4Published=0, batch4PublishMs=-1.");
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
}
