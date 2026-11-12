using System.Collections.Concurrent;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-RES-CAND v2 (FR-104): <c>decoder.coherentFallbackResidualCandidates</c>, default OFF. With it ON, in <c>Both</c> mode with a residual buffer, a THIRD, last
/// fallback run reads the residual audio with the snapshot taken right after the <c>DecodeAll</c> of THAT buffer; the two runs of today are unchanged. Its F1b-passed,
/// new-text rows are kept only at a published integer frequency of at most 1097 Hz; R-F4 never ungates them. The native calls are faked: every <c>DecodeAll</c> gets
/// a number, a snapshot is the one byte "number of the DecodeAll it was taken after", and every fallback run records the (buffer, snapshot, budget) it was handed.
/// So "the third run got the snapshot of the buffer Select returned" is an assertion on a recorded pair, and the budgets come from a manual clock: no timing, no sleeps
/// (TESTING_STRATEGY §11).
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, identity and aggregates.</para>
/// </summary>
public sealed class CohResCandV2Tests
{
    private static readonly DateTime CycleStart = new(2026, 11, 12, 12, 0, 0, DateTimeKind.Utc);

    private const string P0A = "Q1ABC Q1XYZ JO33";
    private const string P0B = "Q1GHI Q1JKL FN20";
    private const string ResidMsg = "Q1DEF Q1UVW EN37";
    private const string ThirdMsg = "Q1MNO Q1PQR IO91";

    // Payload id (first payload byte) -> the text its unpack gives.
    private static readonly Dictionary<int, string> TextOfId = new()
    {
        [3] = "Q1CCC Q1DDD RR73",
        [4] = "Q1AAA Q1BBB RR73",
        [5] = "Q1EEE Q1FFF RR73",
        [6] = "Q1GGG Q1HHH RR73",
        [7] = P0A,                      // a text batch 1 already published
        [8] = "Q1III Q1JJJ RR73",
        [9] = "Q1KKK Q1LLL RR73",
        [10] = "Q1MMM Q1NNN RR73",
        [11] = "Q1RRR Q1SSS RR73",
        [12] = P0B,                     // a text batch 1 published, under a payload the first two runs do not publish
        [13] = ResidMsg,                // a text batch 2 published
        [14] = ThirdMsg,                // a text batch 3 published
    };

    private static Ft8NativeResult Msg(string message, int freqHz = 1500, float dt = 0.2f)
        => new() { FreqHz = freqHz, Dt = dt, Snr = -10, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static byte[] Tones(string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        return tones;
    }

    /// <summary>A fallback row for payload id <paramref name="id"/> published at <paramref name="outFreqHz"/> (the unrounded value the native side reports).</summary>
    private static CohFallbackRow Row(int id, float outFreqHz, CohFallbackState state = CohFallbackState.NewGated)
    {
        var payload = new byte[12];
        payload[0] = (byte)id;
        return new CohFallbackRow(outFreqHz - 0.3f, 0.3f, outFreqHz, 0.31f, 0, false, state, -21, 12.0, payload);
    }

    private static CohFallbackRunResult RunOf(params CohFallbackRow[] rows) => RunOfAbandoned(0, rows);

    private static CohFallbackRunResult RunOfAbandoned(int abandoned, params CohFallbackRow[] rows)
        => new(new CohFallbackStats(rows.Length + 5, 5, 0, rows.Length, rows.Length, rows.Length, rows.Length, rows.Length, 0, abandoned, 0, 1, 2, 3, 123.4),
               rows) { Workers = 4 };

    private sealed class ManualTimeProvider : TimeProvider
    {
        private long _ticks;
        public override long TimestampFrequency => TimeSpan.TicksPerSecond;
        public override long GetTimestamp() => Interlocked.Read(ref _ticks);
        public void Advance(TimeSpan by) => Interlocked.Add(ref _ticks, by.Ticks);
    }

    private sealed class LineLog : ILogger<Ft8Decoder>
    {
        private readonly ConcurrentQueue<string> _q = new();
        public List<string> Lines => _q.ToList();
        public string FallbackLine => Lines.Single(l => l.StartsWith("Coherent fallback:"));
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => _q.Enqueue(formatter(state, exception));
    }

    public enum SnapshotMode { Ok, Null, Throw }

    /// <summary>One recorded <c>CohFallbackRun</c> call.</summary>
    private sealed record RunCall(float[] Pcm, byte Snapshot, double BudgetMs);

    /// <summary>
    /// DecodeAll answers by call number (1 = pass 0, 2 = residual, 3 = third pass). A snapshot is one byte: the number of the last DecodeAll. The fallback runs
    /// are answered by call index: 0 and 1 are the two runs of today (<see cref="FirstTwoRows"/>), 2 is the third run (<see cref="ThirdRows"/>).
    /// </summary>
    private sealed class V2Interop(Ft8NativeResult[][] decodes) : IFt8NativeInterop
    {
        private readonly object _gate = new();
        private int _lastDecode;
        public int MaxDecodePasses => 2;
        public int SnapshotCalls { get; private set; }
        public List<float[]> DecodePcms { get; } = [];
        public List<RunCall> Runs { get; } = [];
        public SnapshotMode MissingMode { get; init; } = SnapshotMode.Ok;   // what the snapshot call after DecodeAll number MissingAt does
        public int MissingAt { get; init; } = 2;
        public TimeProvider? Clock { get; init; }
        public int AdvanceAtRun { get; init; } = -1;                        // the run index during which the manual clock advances
        public TimeSpan Advance { get; init; }
        public int Advance2AtRun { get; init; } = -1;                       // a second run index during which the manual clock advances, by Advance2
        public TimeSpan Advance2 { get; init; }
        public int ThirdAbandoned { get; init; }                            // the third run's Stats.Abandoned
        public int NullRunIndex { get; init; } = -1;                        // the run index whose result is null (the run "failed")
        public CohFallbackRow[] FirstTwoRows { get; init; } = [Row(6, 1300f), Row(7, 1400f)];
        public CohFallbackRow[] ThirdRows { get; init; } = [Row(3, 900f)];

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            int n;
            lock (_gate) { n = ++_lastDecode; DecodePcms.Add(pcm); }
            return n <= decodes.Length ? decodes[n - 1] : [];
        }

        public byte[]? CohFallbackSnapshot()
        {
            int n;
            lock (_gate) { SnapshotCalls++; n = _lastDecode; }
            if (n == MissingAt && MissingMode == SnapshotMode.Null) return null;
            if (n == MissingAt && MissingMode == SnapshotMode.Throw) throw new InvalidOperationException("snapshot failed (test double)");
            return [(byte)n];
        }

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
            => CohFallbackRun(pcm, snapshot, budgetMs, workers, ct);

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        {
            int index;
            lock (_gate) { index = Runs.Count; Runs.Add(new RunCall(pcm, snapshot[0], budgetMs)); }
            if (index == AdvanceAtRun && Clock is ManualTimeProvider m && Advance > TimeSpan.Zero) m.Advance(Advance);
            if (index == Advance2AtRun && Clock is ManualTimeProvider m2 && Advance2 > TimeSpan.Zero) m2.Advance(Advance2);
            if (index == NullRunIndex) return null;
            return index < 2 ? RunOf(FirstTwoRows) : RunOfAbandoned(ThirdAbandoned, ThirdRows);
        }

        public string? CohFallbackUnpack(byte[] payload) => TextOfId.GetValueOrDefault(payload[0]);

        public byte[] EncodeMessage(string message) => Tones(message);
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => (new float[pcm.Length], new float[pcm.Length]);

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

    private static Ft8Decoder Build(IFt8NativeInterop interop, bool resCand, CoherentFallbackAudio audio = CoherentFallbackAudio.Both,
                                    ILogger<Ft8Decoder>? log = null, TimeProvider? time = null, bool ungated = false)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop: interop, timeProvider: time ?? new ManualTimeProvider());
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(DecodingDepth.Deep);
        d.SetCoherentFallbackEnabled(true);
        d.SetCoherentFallbackAudio(audio);
        d.SetCoherentFallbackResidualUngated(ungated);
        d.SetCoherentFallbackResidualCandidates(resCand);
        return d;
    }

    private sealed record Published(int Batch, string Message, int FreqHz);

    private static async Task<List<Published>> RunStaged(Ft8Decoder decoder)
    {
        var got = new List<Published>();
        await decoder.DecodeStagedAsync(LoudPcm(), CycleStart, null, (n, b) =>
        {
            got.AddRange(b.Select(r => new Published(n, r.Message, r.FreqHz)));
            return Task.CompletedTask;
        });
        return got;
    }

    private static readonly Ft8NativeResult[] Pass0 = [Msg(P0A), Msg(P0B, 1800)];
    private static readonly Ft8NativeResult[] Resid = [Msg(ResidMsg, 2100)];
    private static readonly Ft8NativeResult[] Third = [Msg(ThirdMsg, 2400, 0.35f)];

    /// <summary>R3 cycle: the residual pass and the third pass both decode something (so the third pass runs and Select returns its buffer).</summary>
    private static V2Interop R3Cycle(Action<V2Builder>? configure = null) => Make([Pass0, Resid, Third], configure);

    /// <summary>R2 cycle: the residual pass decodes nothing new, so the third pass is skipped and Select returns the residual pass's buffer.</summary>
    private static V2Interop R2Cycle(Action<V2Builder>? configure = null) => Make([Pass0, []], configure);

    /// <summary>No residual buffer: pass 0 decodes nothing, so nothing is fitted and Select hands back the original audio.</summary>
    private static V2Interop NoResidualCycle(Action<V2Builder>? configure = null) => Make([[], []], configure);

    private sealed class V2Builder
    {
        public SnapshotMode MissingMode = SnapshotMode.Ok;
        public int MissingAt = 2;
        public TimeProvider? Clock;
        public int AdvanceAtRun = -1;
        public TimeSpan Advance;
        public int Advance2AtRun = -1;
        public TimeSpan Advance2;
        public int ThirdAbandoned;
        public int NullRunIndex = -1;
        public CohFallbackRow[]? FirstTwoRows;
        public CohFallbackRow[]? ThirdRows;
    }

    private static V2Interop Make(Ft8NativeResult[][] decodes, Action<V2Builder>? configure)
    {
        var b = new V2Builder();
        configure?.Invoke(b);
        return new V2Interop(decodes)
        {
            MissingMode = b.MissingMode, MissingAt = b.MissingAt, Clock = b.Clock, AdvanceAtRun = b.AdvanceAtRun, Advance = b.Advance, NullRunIndex = b.NullRunIndex,
            Advance2AtRun = b.Advance2AtRun, Advance2 = b.Advance2, ThirdAbandoned = b.ThirdAbandoned,
            FirstTwoRows = b.FirstTwoRows ?? [Row(6, 1300f), Row(7, 1400f)],
            ThirdRows = b.ThirdRows ?? [Row(3, 900f)],
        };
    }

    // ── the setting ──────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: the setting defaults to false (config record and bare decoder) and the setter and getter round-trip")]
    public void Setting_DefaultsOff_RoundTrips()
    {
        new DecoderConfig().CoherentFallbackResidualCandidates.Should().BeFalse();
        new DecoderConfig { CoherentFallbackResidualCandidates = true }.CoherentFallbackResidualCandidates.Should().BeTrue();
        new Ft8Decoder(new FakeClock(CycleStart)).CoherentFallbackResidualCandidates.Should().BeFalse("the decoder object starts false");
        var d = Build(R2Cycle(), resCand: false);
        d.CoherentFallbackResidualCandidates.Should().BeFalse();
        d.SetCoherentFallbackResidualCandidates(true);
        d.CoherentFallbackResidualCandidates.Should().BeTrue();
    }

    // ── OFF is today's code ──────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: OFF is a no-op - exactly one snapshot (pass 0's), exactly two runs both on it, and a log line with no res field")]
    public async Task Off_IsNoOp()
    {
        var log = new LineLog();
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: false, log: log);

        await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(1, "only pass 0's snapshot: the residual and third-pass buffers are not snapshotted");
        interop.Runs.Select(r => r.Snapshot).Should().Equal([1, 1], "two runs of today, no third");
        log.FallbackLine.Should().NotMatchRegex(@"resRun|resCand|resEligible|resNew|resAbandoned|resWallMs", "the new fields are written only while the setting is effective");
        Regex.IsMatch(log.FallbackLine, @"crcN1=\d+, audio=both\(residual3\), fromOriginal=\d+, fromResidual=\d+, inBoth=\d+\.$").Should().BeTrue(
            "the line ends exactly as it did before this change: " + Regex.Replace(log.FallbackLine, @"^.*crcN1", "crcN1"));
    }

    [Theory(DisplayName = "FR-104: COH-RES-CAND v2: ON in Original or Residual mode has no effect - one snapshot, no third run, no res field")]
    [InlineData(CoherentFallbackAudio.Original, 1)]
    [InlineData(CoherentFallbackAudio.Residual, 1)]
    public async Task On_NotBothMode_NoEffect(CoherentFallbackAudio mode, int runs)
    {
        var log = new LineLog();
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true, mode, log);

        await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(1);
        interop.Runs.Should().HaveCount(runs);
        log.FallbackLine.Should().NotContain("resRun");
    }

    // ── ON: the right snapshot with the right buffer, and the first two runs untouched ──────────────────────────

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON, R3 - the third run reads the third pass's buffer with the third pass's snapshot; the first two runs keep pass 0's snapshot and their budgets")]
    public async Task On_R3_ThirdRunGetsThirdPassSnapshot_FirstTwoUnchanged()
    {
        var clock = new ManualTimeProvider();
        var offInterop = R3Cycle();
        await RunStaged(Build(offInterop, resCand: false, time: clock));

        var log = new LineLog();
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true, log: log, time: new ManualTimeProvider());

        var got = await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(3, "pass 0, the residual pass and the third pass each took one, on their own DecodeAll");
        interop.Runs.Should().HaveCount(3);
        interop.Runs.Select(r => r.Snapshot).Should().Equal([1, 1, 3], "runs 0 and 1 keep cohSnapshot; the third gets the snapshot of the buffer Select returned");
        interop.Runs[0].Pcm.Should().BeSameAs(interop.DecodePcms[2], "the first run still reads the third pass's buffer");
        interop.Runs[1].Pcm.Should().BeSameAs(interop.DecodePcms[0], "the second run still reads the original audio");
        interop.Runs[2].Pcm.Should().BeSameAs(interop.DecodePcms[2], "the third run reads the buffer whose own snapshot it holds");
        interop.Runs[0].BudgetMs.Should().Be(offInterop.Runs[0].BudgetMs, "the first run's budget arithmetic is unchanged");
        interop.Runs[1].BudgetMs.Should().Be(offInterop.Runs[1].BudgetMs, "the second run's budget arithmetic is unchanged");
        got.Select(p => p.Message).Should().Contain(TextOfId[3], "a candidate only the third run's list offered is published");
        log.FallbackLine.Should().Contain("resRun=ran").And.Contain("resCand=residual-R3").And.Contain("resEligible=1")
            .And.Contain("resNew=1").And.Contain("resNewGated=0").And.Contain("resNewKept=1").And.Contain("resAbandoned=0, resWallMs=").And.MatchRegex(@"resWallMs=\d+\.$");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON, R2 - the third run reads the residual pass's buffer with the residual pass's snapshot; the first two keep pass 0's")]
    public async Task On_R2_ThirdRunGetsResidualPassSnapshot()
    {
        var log = new LineLog();
        var interop = R2Cycle();
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(2);
        interop.Runs.Select(r => r.Snapshot).Should().Equal([1, 1, 2]);
        interop.Runs[2].Pcm.Should().BeSameAs(interop.DecodePcms[1]);
        got.Select(p => p.Message).Should().Contain(TextOfId[3]);
        log.FallbackLine.Should().Contain("resRun=ran").And.Contain("resCand=residual-R2");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON - everything the first two runs publish is still published, in the same order, with the third run's rows after them (add, do not replace)")]
    public async Task On_AddDoNotReplace_FirstTwoRunsRowsKeptInOrder()
    {
        var off = await RunStaged(Build(R3Cycle(b => b.FirstTwoRows = [Row(6, 1300f), Row(8, 1500f), Row(9, 1600f)]), resCand: false));
        var on = await RunStaged(Build(R3Cycle(b => b.FirstTwoRows = [Row(6, 1300f), Row(8, 1500f), Row(9, 1600f)]), resCand: true));

        var offBatch4 = off.Where(p => p.Batch == 4).ToList();
        var onBatch4 = on.Where(p => p.Batch == 4).ToList();
        offBatch4.Should().HaveCount(3);
        onBatch4.Take(offBatch4.Count).Should().Equal(offBatch4, "every row of today's runs, same text, same frequency, same position");
        onBatch4.Skip(offBatch4.Count).Select(p => p.Message).Should().Equal([TextOfId[3]]);
        on.Where(p => p.Batch != 4).Should().Equal(off.Where(p => p.Batch != 4), "batches 1 to 3 are untouched");
    }

    // ── ON: a missing snapshot, no budget, no residual, a failed run: reachable, nothing throws ──────────────────

    [Theory(DisplayName = "FR-104: COH-RES-CAND v2: ON, the chosen buffer's snapshot is missing (null or the call throws) - resRun=no-snapshot, only the two runs of today, the cycle is untouched")]
    [InlineData(SnapshotMode.Null, false)]
    [InlineData(SnapshotMode.Throw, false)]
    [InlineData(SnapshotMode.Null, true)]
    [InlineData(SnapshotMode.Throw, true)]
    public async Task On_MissingSnapshotOfChosenBuffer_NoThirdRun(SnapshotMode mode, bool thirdPassBuffer)
    {
        var log = new LineLog();
        // R2 buffer chosen: the residual pass's snapshot (decode 2) is the missing one. R3 buffer chosen: the third pass's (decode 3).
        var interop = thirdPassBuffer ? R3Cycle(b => { b.MissingMode = mode; b.MissingAt = 3; }) : R2Cycle(b => { b.MissingMode = mode; b.MissingAt = 2; });
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        interop.Runs.Select(r => r.Snapshot).Should().Equal([1, 1], "the third run is not started");
        log.FallbackLine.Should().Contain("resRun=no-snapshot").And.Contain(thirdPassBuffer ? "resCand=residual-R3" : "resCand=residual-R2")
            .And.Contain("resEligible=0").And.Contain("resNew=0").And.Contain("resNewKept=0");
        got.Select(p => p.Message).Should().NotContain(TextOfId[3]);
        got.Should().Contain(p => p.Batch == 4, "the first two runs' rows are published as without the setting");
        if (thirdPassBuffer) got.Select(p => p.Batch).Should().Contain(3, "a failed snapshot does not cost the third pass its decodes");
    }

    [Theory(DisplayName = "FR-104: COH-RES-CAND v2: ON, the budget is spent after the first run or after the second - resRun=skipped-budget, no third run, nothing throws")]
    [InlineData(0, 1)]
    [InlineData(1, 2)]
    public async Task On_BudgetSpent_SkippedBudget(int advanceAtRun, int expectedRuns)
    {
        var clock = new ManualTimeProvider();
        var log = new LineLog();
        var interop = R3Cycle(b => { b.Clock = clock; b.AdvanceAtRun = advanceAtRun; b.Advance = TimeSpan.FromSeconds(14); });
        var decoder = Build(interop, resCand: true, log: log, time: clock);

        await RunStaged(decoder);

        interop.Runs.Should().HaveCount(expectedRuns, "the run that follows the spent budget (the second, or the third) is not started");
        log.FallbackLine.Should().Contain("resRun=skipped-budget").And.Contain("resCand=residual-R3").And.Contain("resNew=0");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON with no residual buffer - resRun=no-residual, resCand=none, one run on the original audio, no snapshot of a residual buffer")]
    public async Task On_NoResidualBuffer_NoResidual()
    {
        var log = new LineLog();
        var interop = NoResidualCycle();
        var decoder = Build(interop, resCand: true, log: log);

        await RunStaged(decoder);

        interop.Runs.Should().HaveCount(1, "with no usable residual buffer the original audio is run once, never twice");
        log.FallbackLine.Should().Contain("resRun=no-residual").And.Contain("resCand=none");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON, the first run failed (null) - nothing throws, no third run, no fallback batch (as without the setting)")]
    public async Task On_FirstRunFailed_ThirdRunNotStarted()
    {
        var interop = R3Cycle(b => b.NullRunIndex = 0);
        var decoder = Build(interop, resCand: true);

        List<Published>? got = null;
        var act = async () => got = await RunStaged(decoder);

        await act.Should().NotThrowAsync();
        interop.Runs.Should().HaveCount(1);
        got!.Should().NotContain(p => p.Batch == 4);
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON, the third run itself failed (null) - resRun=failed, the first two runs' rows are still published, nothing throws")]
    public async Task On_ThirdRunFailed_FirstTwoStillPublished()
    {
        var log = new LineLog();
        var interop = R3Cycle(b => b.NullRunIndex = 2);
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        interop.Runs.Should().HaveCount(3);
        log.FallbackLine.Should().Contain("resRun=failed");
        got.Select(p => p.Message).Should().Contain(TextOfId[6]).And.NotContain(TextOfId[3]);
    }

    // ── The gate ─────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: the gate keeps a new-text row at 1097 Hz and drops one at 1098 Hz, both sides of the boundary, through the whole decode")]
    public async Task Gate_Boundary_1097Kept_1098Dropped()
    {
        var log = new LineLog();
        var interop = R3Cycle(b => b.ThirdRows = [Row(3, 1097f), Row(4, 1098f), Row(5, 1000f), Row(8, 1500f)]);
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        var thirdRunRows = got.Where(p => p.Batch == 4 && new[] { TextOfId[3], TextOfId[4], TextOfId[5], TextOfId[8] }.Contains(p.Message)).ToList();
        thirdRunRows.Select(p => p.Message).Should().BeEquivalentTo([TextOfId[3], TextOfId[5]], "1097 and 1000 Hz are kept; 1098 and 1500 Hz are dropped");
        thirdRunRows.Single(p => p.Message == TextOfId[3]).FreqHz.Should().Be(1097);
        log.FallbackLine.Should().Contain("resNew=4").And.Contain("resNewGated=2").And.Contain("resNewKept=2");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: the gate compares the PUBLISHED integer Hz, not the unrounded value (1097.4 publishes as 1097 and is kept; 1097.6 and 1097.5 publish as 1098 and are dropped)")]
    public async Task Gate_UsesPublishedIntegerHz_NotUnrounded()
    {
        var interop = R3Cycle(b => b.ThirdRows = [Row(3, 1097.4f), Row(4, 1097.6f), Row(5, 1097.5f)]);
        var decoder = Build(interop, resCand: true);

        var got = await RunStaged(decoder);

        var kept = got.Where(p => p.Message == TextOfId[3] || p.Message == TextOfId[4] || p.Message == TextOfId[5]).ToList();
        kept.Should().ContainSingle("an unrounded comparison (1097.4 > 1097) would drop it and keep nothing");
        kept[0].Message.Should().Be(TextOfId[3]);
        kept[0].FreqHz.Should().Be(1097, "the value the row is published with is the value the gate read");
    }

    [Theory(DisplayName = "FR-104: COH-RES-CAND v2: PublishedFreqHz is the integer the row is published with, and PassesResidualRunGate is <= 1097")]
    [InlineData(1097.0f, 1097, true)]
    [InlineData(1097.4f, 1097, true)]
    [InlineData(1097.5f, 1098, false)]
    [InlineData(1098.0f, 1098, false)]
    [InlineData(300.2f, 300, true)]
    public void GateFunctions_AgreeWithPublishedValue(float outFreq, int publishedHz, bool kept)
    {
        CohFallbackAudioSelector.ResidualRunMaxFreqHz.Should().Be(1097);
        CohFallbackAudioSelector.PublishedFreqHz(Row(3, outFreq)).Should().Be(publishedHz);
        CohFallbackAudioSelector.PassesResidualRunGate(publishedHz).Should().Be(kept);
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: the gate applies only to the third run - a first-run row above 1097 Hz is published as before")]
    public async Task Gate_DoesNotTouchTheFirstTwoRuns()
    {
        var interop = R3Cycle(b => b.FirstTwoRows = [Row(6, 1900f), Row(8, 2400f)]);
        var decoder = Build(interop, resCand: true);

        var got = await RunStaged(decoder);

        got.Select(p => p.Message).Should().Contain(TextOfId[6]).And.Contain(TextOfId[8]);
    }

    // ── R-F4 ─────────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: R-F4 ON ungates the first residual run's above-T1 row but never the third run's - an above-T1 third-run row is not published and not counted")]
    public async Task RF4_On_DoesNotUngateThirdRunRows()
    {
        var log = new LineLog();
        var interop = R3Cycle(b =>
        {
            b.FirstTwoRows = [Row(6, 1300f), Row(8, 1500f, CohFallbackState.GatedOut)];
            b.ThirdRows = [Row(3, 900f), Row(9, 900f, CohFallbackState.GatedOut)];
        });
        var decoder = Build(interop, resCand: true, log: log, ungated: true);

        var got = await RunStaged(decoder);

        var texts = got.Select(p => p.Message).ToList();
        texts.Should().Contain(TextOfId[8], "R-F4 still admits the first residual run's GatedOut row (the control: the setting is really on)");
        texts.Should().Contain(TextOfId[3], "an F1b-passed third-run row below the gate is published");
        texts.Should().NotContain(TextOfId[9], "a GatedOut row of the third run is never admitted, though R-F4 is on");
        log.FallbackLine.Should().Contain("resNew=1").And.Contain("resNewKept=1").And.Contain("ungated=1");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ThirdRunCandidates takes F1b-passed rows only, whatever the Admitted flag says")]
    public void ThirdRunCandidates_NewGatedOnly_IgnoresAdmittedFlag()
    {
        var gatedOutAdmitted = Row(9, 900f, CohFallbackState.GatedOut) with { Admitted = true };
        var rows = new[] { Row(3, 900f), gatedOutAdmitted, Row(4, 950f, CohFallbackState.NoCrc), Row(5, 960f, CohFallbackState.Known), Row(8, 970f) };

        var taken = CohFallbackAudioSelector.ThirdRunCandidates(rows);

        taken.Select(r => (int)r.Payload[0]).Should().Equal([3, 8]);
        CohFallbackAudioSelector.ThirdRunCandidates(null).Should().BeEmpty();
        CohFallbackAudioSelector.ThirdRunCandidates([]).Should().BeEmpty();
    }

    // ── Publication: no text twice, new text only ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON - a third-run row whose text is already published in the cycle (batch 1, or the first two runs) is not new: not counted, not gated, not published twice")]
    public async Task On_TextAlreadyPublished_NotNew_NoDuplicate()
    {
        var log = new LineLog();
        // id 7 is P0A (batch 1); id 6 is a text the first two runs publish; id 3 is genuinely new; all three at 2000 Hz, above the gate.
        var interop = R3Cycle(b => b.ThirdRows = [Row(7, 2000f), Row(6, 2000f), Row(3, 2000f)]);
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        var all = got.Select(p => p.Message).ToList();
        all.Should().OnlyHaveUniqueItems("no text twice in a cycle");
        all.Count(m => m == P0A).Should().Be(1);
        log.FallbackLine.Should().Contain("resNew=1", "only the new text is counted before the gate").And.Contain("resNewGated=1").And.Contain("resNewKept=0");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON - the kept third-run rows are tagged as fallback rows and published in batch 4 only")]
    public async Task On_KeptRows_AreBatch4()
    {
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true);

        var got = await RunStaged(decoder);

        got.Where(p => p.Message == TextOfId[3]).Select(p => p.Batch).Should().Equal([Ft8Decoder.FallbackBatchDeep]);
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON - a third-run row whose payload the first two runs did NOT publish but whose text batch 1, 2 or 3 did is not new text, above or below 1097 Hz (pins the `seen` guard)")]
    public async Task On_TextPublishedInBatches1To3_UnderANewPayload_NotNew()
    {
        var log = new LineLog();
        // ids 12, 13, 14 carry the texts of batches 1, 2, 3 under payloads no first-two row has; each appears below and above the gate. id 3 is genuinely new, below the gate.
        var interop = R3Cycle(b => b.ThirdRows = [Row(12, 900f), Row(13, 2000f), Row(14, 900f), Row(12, 2100f), Row(3, 900f)]);
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        var all = got.Select(p => p.Message).ToList();
        all.Should().OnlyHaveUniqueItems("no text twice in a cycle");
        log.FallbackLine.Should().Contain("resNew=1", "a text already published in batches 1 to 3 is not new, whatever its payload").And.Contain("resNewGated=0").And.Contain("resNewKept=1");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON - the third run's budget is the budget left after the second run (budgetMs minus the fallback time already spent), smaller than the second run's")]
    public async Task On_ThirdRunBudget_IsWhatIsLeftAfterTheSecondRun()
    {
        var clock = new ManualTimeProvider();
        var interop = R3Cycle(b =>
        {
            b.Clock = clock;
            b.AdvanceAtRun = 0; b.Advance = TimeSpan.FromSeconds(3);
            b.Advance2AtRun = 1; b.Advance2 = TimeSpan.FromSeconds(2);
        });
        var decoder = Build(interop, resCand: true, time: clock);

        await RunStaged(decoder);

        interop.Runs.Should().HaveCount(3);
        double budget = interop.Runs[0].BudgetMs;
        interop.Runs[1].BudgetMs.Should().BeApproximately(budget - 3000.0, 0.5, "the second run gets what the first left (unchanged)");
        interop.Runs[2].BudgetMs.Should().BeApproximately(budget - 5000.0, 0.5, "the third run gets what both left");
        interop.Runs[2].BudgetMs.Should().BeLessThan(interop.Runs[1].BudgetMs);
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: ON - resAbandoned is the third run's own abandoned count (0 when it did not run); with the setting OFF the line has no such field")]
    public async Task On_ResAbandoned_IsTheThirdRunsCount()
    {
        var ran = new LineLog();
        await RunStaged(Build(R3Cycle(b => b.ThirdAbandoned = 4), resCand: true, log: ran));
        ran.FallbackLine.Should().Contain("resRun=ran").And.Contain("resAbandoned=4, resWallMs=").And.Contain(", abandoned=0,", "the combined abandoned= field still counts the first two runs only");

        var skipped = new LineLog();
        var clock = new ManualTimeProvider();
        await RunStaged(Build(R3Cycle(b => { b.Clock = clock; b.AdvanceAtRun = 1; b.Advance = TimeSpan.FromSeconds(14); b.ThirdAbandoned = 4; }), resCand: true, log: skipped, time: clock));
        skipped.FallbackLine.Should().Contain("resRun=skipped-budget").And.Contain("resAbandoned=0, resWallMs=");

        var off = new LineLog();
        await RunStaged(Build(R3Cycle(b => b.ThirdAbandoned = 4), resCand: false, log: off));
        off.FallbackLine.Should().NotContain("resAbandoned");
    }
}
