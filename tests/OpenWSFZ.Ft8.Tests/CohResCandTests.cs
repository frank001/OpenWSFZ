using System.Collections.Concurrent;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-RES-CAND (FR-103, #272): <c>decoder.coherentFallbackResidualCandidates</c>, default OFF. With it ON the coherent fallback's run that reads a residual
/// buffer is handed the candidate snapshot taken right after the <c>DecodeAll</c> of THAT buffer (R2: the residual pass's, R3: the third pass's); the run
/// that reads the original audio keeps the original snapshot. The native calls are faked: every <c>DecodeAll</c> gets a number, a snapshot is the one
/// byte "number of the DecodeAll it was taken after", and every fallback run records the (buffer, snapshot) it was handed. So "the residual run got the
/// snapshot of the buffer Select returned" is an assertion on a recorded pair, never on timing.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, identity and aggregates.</para>
/// </summary>
public sealed class CohResCandTests
{
    private static readonly DateTime CycleStart = new(2026, 11, 8, 12, 0, 0, DateTimeKind.Utc);

    private const string P0A = "Q1ABC Q1XYZ JO33";
    private const string P0B = "Q1GHI Q1JKL FN20";
    private const string ResidMsg = "Q1DEF Q1UVW EN37";
    private const string ThirdMsg = "Q1MNO Q1PQR IO91";
    private const string FbR3 = "Q1CCC Q1DDD RR73";     // what the run given snapshot 3 (the third pass's) finds
    private const string FbR2 = "Q1EEE Q1FFF RR73";     // snapshot 2 (the residual pass's)
    private const string FbOrig = "Q1GGG Q1HHH RR73";   // snapshot 1 (pass 0's, the original list)

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

    private static CohFallbackRow Row(int id)
    {
        var payload = new byte[12];
        payload[0] = (byte)id;
        float freq = 1000f + 100f * id;
        return new CohFallbackRow(freq, 0.3f, freq + 0.3f, 0.31f, 0, false, CohFallbackState.NewGated, -21, 12.0, payload);
    }

    /// <summary>A run result with one publishable row per id; its Eligible count is the number of ids.</summary>
    private static CohFallbackRunResult RunOf(params int[] ids)
        => new(new CohFallbackStats(ids.Length + 5, 5, 0, ids.Length, ids.Length, ids.Length, ids.Length, ids.Length, ids.Length, 0, 0, 1, 2, 3, 123.4),
               ids.Select(Row).ToArray()) { Workers = 4 };

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

    /// <summary>DecodeAll answers by call number (1 = pass 0, 2 = residual, 3 = third pass). The snapshot is one byte: the number of the last DecodeAll.</summary>
    private sealed class ResCandInterop(Ft8NativeResult[][] decodes) : IFt8NativeInterop
    {
        private readonly object _gate = new();
        private int _lastDecode;
        public int MaxDecodePasses => 2;
        public int SnapshotCalls { get; private set; }
        public List<float[]> DecodePcms { get; } = [];
        public List<(float[] Pcm, byte Snapshot)> Runs { get; } = [];
        public SnapshotMode MissingMode { get; init; } = SnapshotMode.Ok;   // what the snapshot call after DecodeAll number MissingAt does
        public int MissingAt { get; init; } = 2;
        public int EligibleCountAnswer { get; init; } = -1;
        public int EligibleCountCalls { get; private set; }
        public TimeProvider? Clock { get; init; }
        public TimeSpan AdvanceInFirstRun { get; init; }

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

        public int CohFallbackEligibleCount(byte[] snapshot)
        {
            lock (_gate) EligibleCountCalls++;
            return EligibleCountAnswer;
        }

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
            => CohFallbackRun(pcm, snapshot, budgetMs, workers, ct);

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        {
            bool first;
            lock (_gate) { first = Runs.Count == 0; Runs.Add((pcm, snapshot[0])); }
            if (first && Clock is ManualTimeProvider m && AdvanceInFirstRun > TimeSpan.Zero) m.Advance(AdvanceInFirstRun);
            return snapshot[0] switch
            {
                3 => RunOf(3),
                2 => RunOf(5),
                1 => RunOf(6, 7),
                _ => null,
            };
        }

        public string? CohFallbackUnpack(byte[] payload) => payload[0] switch
        {
            3 => FbR3,
            5 => FbR2,
            6 => FbOrig,
            7 => P0A,   // a text batch 1 already published: the per-cycle de-duplication must keep it out
            _ => null,
        };

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
                                    ILogger<Ft8Decoder>? log = null, TimeProvider? time = null)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop: interop, timeProvider: time);
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(DecodingDepth.Deep);
        d.SetCoherentFallbackEnabled(true);
        d.SetCoherentFallbackAudio(audio);
        d.SetCoherentFallbackResidualCandidates(resCand);
        return d;
    }

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

    private static readonly Ft8NativeResult[] Pass0 = [Msg(P0A), Msg(P0B, 1800)];
    private static readonly Ft8NativeResult[] Resid = [Msg(ResidMsg, 2100)];
    private static readonly Ft8NativeResult[] Third = [Msg(ThirdMsg, 2400, 0.35f)];

    /// <summary>R3 cycle: the residual pass and the third pass both decode something (so the third pass runs and Select returns its buffer).</summary>
    private static ResCandInterop R3Cycle(SnapshotMode missing = SnapshotMode.Ok, int missingAt = 2, int eligible = -1, TimeProvider? clock = null, TimeSpan advance = default)
        => new([Pass0, Resid, Third]) { MissingMode = missing, MissingAt = missingAt, EligibleCountAnswer = eligible, Clock = clock, AdvanceInFirstRun = advance };

    /// <summary>R2 cycle: the residual pass decodes nothing new, so the third pass is skipped and Select returns the residual pass's buffer.</summary>
    private static ResCandInterop R2Cycle(SnapshotMode missing = SnapshotMode.Ok) => new([Pass0, []]) { MissingMode = missing, MissingAt = 2 };

    // ── the setting ──────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: COH-RES-CAND: the setting defaults to false (config record and bare decoder) and the setter and getter round-trip")]
    public void Setting_DefaultsOff_RoundTrips()
    {
        new DecoderConfig().CoherentFallbackResidualCandidates.Should().BeFalse();
        new DecoderConfig { CoherentFallbackResidualCandidates = true }.CoherentFallbackResidualCandidates.Should().BeTrue();
        var d = Build(R2Cycle(), resCand: false);
        d.CoherentFallbackResidualCandidates.Should().BeFalse();
        d.SetCoherentFallbackResidualCandidates(true);
        d.CoherentFallbackResidualCandidates.Should().BeTrue();
    }

    // ── OFF is today's code ──────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: COH-RES-CAND: OFF is a no-op - exactly one snapshot (pass 0's), both runs get it, no resCand field, no counters")]
    public async Task Off_IsNoOp()
    {
        var log = new LineLog();
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: false, log: log);

        await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(1, "only pass 0's snapshot: the residual and third-pass buffers are not snapshotted");
        interop.Runs.Select(r => r.Snapshot).Should().Equal([1, 1]);
        log.FallbackLine.Should().NotContain("resCand").And.NotContain("resEligible").And.NotContain("origEligible");
        decoder.GetResidualCandidatesCounters().Should().Be(new Ft8Decoder.ResidualCandidatesCounters(0, 0, 0));
    }

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON in Original mode has no effect - one snapshot, one run on the original list, no resCand field")]
    public async Task On_OriginalMode_NoEffect()
    {
        var log = new LineLog();
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true, CoherentFallbackAudio.Original, log);

        await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(1);
        interop.Runs.Select(r => r.Snapshot).Should().Equal([1]);
        log.FallbackLine.Should().NotContain("resCand");
    }

    // ── ON: the right snapshot with the right buffer ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON, R3 - the residual run reads the third pass's buffer with the third pass's snapshot; the original run keeps pass 0's")]
    public async Task On_R3_ResidualRunGetsThirdPassSnapshot_OriginalRunKeepsOriginal()
    {
        var log = new LineLog();
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(3, "pass 0, the residual pass and the third pass each took one, on their own DecodeAll");
        interop.Runs.Should().HaveCount(2);
        interop.Runs[0].Snapshot.Should().Be(3);
        interop.Runs[0].Pcm.Should().BeSameAs(interop.DecodePcms[2], "the residual run reads the buffer the third pass decoded, and its snapshot is that decode's");
        interop.Runs[1].Snapshot.Should().Be(1, "the original run keeps cohSnapshot");
        interop.Runs[1].Pcm.Should().BeSameAs(interop.DecodePcms[0], "and reads the original audio");
        got.Last().Messages.Should().Contain(FbR3, "a candidate only the third pass's list offered is published");
        log.FallbackLine.Should().Contain("resCand=residual-R3").And.Contain("resEligible=1").And.Contain("origEligible=2");
        decoder.GetResidualCandidatesCounters().Should().Be(new Ft8Decoder.ResidualCandidatesCounters(0, 1, 0));
    }

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON, R2 - the residual run reads the residual pass's buffer with the residual pass's snapshot; the original run keeps pass 0's")]
    public async Task On_R2_ResidualRunGetsResidualPassSnapshot()
    {
        var log = new LineLog();
        var interop = R2Cycle();
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        interop.SnapshotCalls.Should().Be(2);
        interop.Runs.Select(r => r.Snapshot).Should().Equal([2, 1]);
        interop.Runs[0].Pcm.Should().BeSameAs(interop.DecodePcms[1]);
        got.Last().Messages.Should().Contain(FbR2);
        log.FallbackLine.Should().Contain("resCand=residual-R2");
        decoder.GetResidualCandidatesCounters().Should().Be(new Ft8Decoder.ResidualCandidatesCounters(1, 0, 0));
    }

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON in Residual mode - the single run reads the residual buffer with its own snapshot")]
    public async Task On_ResidualMode_SingleRunGetsResidualSnapshot()
    {
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true, CoherentFallbackAudio.Residual);

        await RunStaged(decoder);

        interop.Runs.Select(r => r.Snapshot).Should().Equal([3]);
    }

    // ── ON: a missing snapshot never costs the cycle ─────────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-103: COH-RES-CAND: ON, the snapshot of the chosen buffer is missing (null or the call throws) - fallback-orig, both runs use pass 0's snapshot, nothing throws")]
    [InlineData(SnapshotMode.Null, false)]
    [InlineData(SnapshotMode.Throw, false)]
    [InlineData(SnapshotMode.Null, true)]
    [InlineData(SnapshotMode.Throw, true)]
    public async Task On_MissingSnapshotOfChosenBuffer_FallsBackToOriginal(SnapshotMode mode, bool thirdPassBuffer)
    {
        var log = new LineLog();
        // R2 buffer chosen: the residual pass's snapshot (decode 2) is the missing one. R3 buffer chosen: the third pass's (decode 3).
        var interop = thirdPassBuffer ? R3Cycle(mode, missingAt: 3) : R2Cycle(mode);
        var decoder = Build(interop, resCand: true, log: log);

        var got = await RunStaged(decoder);

        interop.Runs.Select(r => r.Snapshot).Should().Equal([1, 1], "the run falls back to cohSnapshot; the original run always had it");
        log.FallbackLine.Should().Contain("resCand=fallback-orig");
        decoder.GetResidualCandidatesCounters().Should().Be(new Ft8Decoder.ResidualCandidatesCounters(0, 0, 1));
        if (thirdPassBuffer) got.Select(b => b.Batch).Should().Contain(3, "a failed snapshot does not cost the third pass its decodes");
    }

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON, the residual pass's own snapshot fails but the chosen (third-pass) buffer's is there - the residual pass keeps its decodes and R3 is used")]
    public async Task On_ResidualPassSnapshotFails_PassKeepsDecodes()
    {
        var interop = R3Cycle(SnapshotMode.Throw, missingAt: 2);
        var decoder = Build(interop, resCand: true);

        var got = await RunStaged(decoder);

        got.Select(b => b.Batch).Should().Contain(2, "the residual pass's decodes are published");
        interop.Runs.Select(r => r.Snapshot).Should().Equal([3, 1]);
    }

    // ── ON: publication is unchanged ─────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON - no text is published twice in a cycle (a fallback row whose text batch 1 already published is dropped)")]
    public async Task On_NoDuplicateText()
    {
        var interop = R3Cycle();
        var decoder = Build(interop, resCand: true);

        var got = await RunStaged(decoder);

        var all = got.SelectMany(b => b.Messages).ToList();
        all.Should().OnlyHaveUniqueItems();
        all.Count(m => m == P0A).Should().Be(1, "the original run's second row decodes P0A again; the per-cycle text de-duplication keeps it out");
        all.Should().Contain(FbOrig, "the original run's other row is still offered and published");
    }

    // ── ON: the counts in the log line ───────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: COH-RES-CAND: ON - a run that never started (shared budget spent) counts the ORIGINAL snapshot's eligible candidates, from the interop's own count")]
    public async Task On_OriginalRunNotStarted_UsesOriginalEligibleCount()
    {
        var log = new LineLog();
        var clock = new ManualTimeProvider();
        var interop = R3Cycle(eligible: 7, clock: clock, advance: TimeSpan.FromSeconds(14));
        var decoder = Build(interop, resCand: true, log: log, time: clock);

        await RunStaged(decoder);

        interop.Runs.Should().HaveCount(1, "the residual run used the whole budget; the original run was not started");
        interop.EligibleCountCalls.Should().BeGreaterThan(0);
        log.FallbackLine.Should().Contain("resCand=residual-R3").And.Contain("resEligible=1").And.Contain("origEligible=7").And.Contain("abandoned=7");
    }
}
