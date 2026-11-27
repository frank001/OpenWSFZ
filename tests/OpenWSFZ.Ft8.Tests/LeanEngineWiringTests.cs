using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2a (FR-108), the managed side of <c>decoder.engine</c> (D4) and the lean cycle's log line (D5), against a fake native layer so every case
/// is exact: <c>lean</c> reaches <c>ftz_decode_cycle</c> and never the classic path; <c>classic</c> and an absent key never reach the lean call and equal
/// the base build's recording; a native error code and an exception are logged and the next cycle runs; the log line carries counts and times only.
/// Q-prefix calls only (NFR-021). No delay anywhere: every decode is awaited, never slept on.
/// </summary>
public sealed class LeanEngineWiringTests
{
    private static Ft8NativeResult Native(string message, int freq = 1500, float dt = 0.2f, int snr = -12)
        => new() { FreqHz = freq, Dt = dt, Snr = snr, Message = message };

    private static LeanCycleStats Stats(int error = 0, int results = 0, int threads = 2, bool abandoned = false)
        => new(error, Candidates: 40, TierADecodes: results, Results: results, Threads: threads, Abandoned: abandoned,
               SpectrogramWallUs: 11_000, SpectrogramCpuUs: 10_000, CandidatesWallUs: 2_000, CandidatesCpuUs: 2_000,
               TierAWallUs: 30_000, TierACpuUs: 55_000, UnpackWallUs: 500, UnpackCpuUs: 400, TotalWallUs: 44_000, TotalCpuUs: 67_400)
        {
            TierBEligible = 7, TierBAttempted = 6, TierBCrcValid = 3, TierBF1b = 2, TierBGated = 1, TierBPublished = 1, TierBEdge = 1, TierBSkipped = 1,
            CqApAttempts = 4, CqApDecodes = 1, TierBWallUs = 40_000, TierBCpuUs = 70_000, CqApWallUs = 3_000, CqApCpuUs = 5_000,
        };

    /// <summary>
    /// A fake whose CLASSIC members all throw: a lean cycle that touches any of them fails the test, which is how "the classic code path is not entered" is
    /// proved. The lean members record the threads they were given and replay a queue of outcomes (or throw).
    /// </summary>
    private sealed class LeanFake : IFt8NativeInterop
    {
        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request, Action<LeanRound0>? onRound0)
        {
            var outcome = DecodeLeanCycle(pcm, request);
            if (onRound0 is not null)
            {
                var idx = Enumerable.Range(0, outcome.Results.Length).Where(i => i >= outcome.Rounds.Length || outcome.Rounds[i] == 0).ToArray();
                onRound0(new LeanRound0(idx.Select(i => outcome.Results[i]).ToArray(), idx.Select(i => i < outcome.Tiers.Length ? outcome.Tiers[i] : LeanTier.A).ToArray()));
            }
            return outcome;
        }
        public LeanCycleOutcome DecodeLeanXcRound(float[] pcm, LeanCycleParams request, float[] residual, IReadOnlyList<LeanXcDetection> detections) => throw new NotSupportedException("Not modelled by this fake.");
        public void LeanShutdown() { }
        public List<int> ThreadsSeen { get; } = [];
        public List<LeanCycleParams> Requests { get; } = [];
        public Queue<Func<LeanCycleOutcome>> Outcomes { get; } = new();

        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request)
        {
            ThreadsSeen.Add(request.Threads);
            Requests.Add(request);
            return Outcomes.Count > 0 ? Outcomes.Dequeue()() : new LeanCycleOutcome([], Stats());
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
        public void SetCqApEnabled(bool enabled) => Classic<int>();
        public (int Attempts, int Decodes, int OsdEntries) GetLastCqApStats() => Classic<(int, int, int)>();
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* configuration only: not a decode */ }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => Classic<(float, float, float, int, int)>();
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => Classic<float[]>();
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => Classic<(float[], float[])>();
        public byte[] EncodeMessage(string message) => Classic<byte[]>();
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => Classic<(float[], float[])>();
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag) => Classic<(int, float[])>();
    }

    private sealed class CapturingLogger : ILogger<Ft8Decoder>
    {
        public List<(LogLevel Level, string Message)> Entries { get; } = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
            => Entries.Add((logLevel, formatter(state, exception)));
    }

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static readonly DateTime Start = new(2026, 11, 24, 12, 0, 0, DateTimeKind.Utc);

    private static (Ft8Decoder Decoder, CapturingLogger Log) Build(IFt8NativeInterop interop, DecoderEngine engine = DecoderEngine.Lean)
    {
        var log = new CapturingLogger();
        var decoder = new Ft8Decoder(new FakeClock(Start), log, interop);
        decoder.SetEngine(engine);
        return (decoder, log);
    }

    private static IEnumerable<string> LeanLines(CapturingLogger log)
        => log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.Contains("lean:")).Select(e => e.Message);

    // ── the switch ───────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-109: DR-3: the config default and an unknown value read lean, only the word classic reads classic; a bare decoder object starts classic until the daemon sets the engine from the config at start")]
    public void Engine_ConfigDefaultIsLean()
    {
        var decoder = new Ft8Decoder(new FakeClock(Start), new CapturingLogger(), new LeanFake());
        decoder.Engine.Should().Be(DecoderEngine.Classic, "the object is configured by the daemon at start (Program.cs SetEngine), exactly as for every other setting");
        new DecoderConfig().GetEngineKind().Should().Be(DecoderEngine.Lean);
        DecoderEngineNames.Parse(null).Should().Be(DecoderEngine.Lean);
        DecoderEngineNames.Parse("").Should().Be(DecoderEngine.Lean);
        DecoderEngineNames.Parse("turbo").Should().Be(DecoderEngine.Lean);
        DecoderEngineNames.Parse("classic").Should().Be(DecoderEngine.Classic);
        DecoderEngineNames.Parse(" Classic ").Should().Be(DecoderEngine.Classic);
        DecoderEngineNames.Parse("lean").Should().Be(DecoderEngine.Lean);
        DecoderEngineNames.Parse(" Lean ").Should().Be(DecoderEngine.Lean);
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: with engine lean the cycle goes through ftz_decode_cycle once and the classic path is not entered (every classic native member of the fake throws)")]
    public async Task Lean_RoutesToTheNativeCall_AndNotTheClassicPath()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22", 1200), Native("Q2DEF Q3GHI -07", 1800)], Stats(results: 2)));
        var (decoder, _) = Build(fake);

        var results = await decoder.DecodeAsync(LoudPcm(), Start, "20m");

        fake.ThreadsSeen.Should().HaveCount(1);
        results.Select(r => r.Message).Should().Equal("CQ Q1ABC JO22", "Q2DEF Q3GHI -07");
        results.Should().OnlyContain(r => r.Path == Ft8Decoder.PathOrdinary && r.ApKind == ApKind.None && r.Time == "12:00:00" && r.Band == "20m");
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: the staged entry points publish the lean results as ONE batch 1 (no batch 2)")]
    public async Task Lean_StagedEntries_PublishOneBatch()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22")], Stats(results: 1)));
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22")], Stats(results: 1)));
        var (decoder, _) = Build(fake);
        decoder.SetSubtractionEnabled(true);   // the classic flags are irrelevant to the lean engine

        var batches = new List<(int Number, string[] Texts)>();
        await decoder.DecodeStagedAsync(LoudPcm(), Start, null, (n, b) => { batches.Add((n, b.Select(r => r.Message).ToArray())); return Task.CompletedTask; });
        batches.Should().ContainSingle();
        batches[0].Number.Should().Be(1);
        batches[0].Texts.Should().Equal("CQ Q1ABC JO22");

        var firstBatches = new List<string[]>();
        var second = await decoder.DecodeTwoStageAsync(LoudPcm(), Start, null, b => { firstBatches.Add(b.Select(r => r.Message).ToArray()); return Task.CompletedTask; });
        firstBatches.Should().ContainSingle();
        second.Should().BeEmpty();
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: with engine classic, set explicitly, the native calls, batches and log lines equal the base build's recording")]
    public async Task ExplicitClassic_EqualsTheBaseRecording()
    {
        string actual = await ClassicEngineGoldenTests.RecordAsync(d => d.SetEngine(DecoderEngine.Classic));
        actual.Should().Be(ClassicEngineGoldenTests.GoldenText);
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: with engine classic the lean native call is never made")]
    public async Task Classic_NeverCallsTheLeanEntry()
    {
        var log = new CapturingLogger();
        var decoder = new Ft8Decoder(new FakeClock(Start), log, new NoLeanFake());
        await decoder.DecodeAsync(LoudPcm(), Start, null);   // NoLeanFake.DecodeLeanCycle throws
        decoder.SetEngine(DecoderEngine.Classic);
        await decoder.DecodeAsync(LoudPcm(), Start, null);
    }

    private sealed class NoLeanFake : IFt8NativeInterop
    {
        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request, Action<LeanRound0>? onRound0) => throw new NotSupportedException("Not modelled by this fake.");
        public LeanCycleOutcome DecodeLeanXcRound(float[] pcm, LeanCycleParams request, float[] residual, IReadOnlyList<LeanXcDetection> detections) => throw new NotSupportedException("Not modelled by this fake.");
        public void LeanShutdown() { }
        public int MaxDecodePasses => 2;
        public Ft8NativeResult[] DecodeAll(float[] pcm) => [Native("CQ Q1ABC JO22")];
        public int[] GetLastPassCounts(int maxPasses) => [1, 0];
        public int[] GetLastCandidateCounts(int maxPasses) => [1, 0];
        public float GetLastNoiseFloorDb() => -70.0f;
        public int GetHashTableRejectCount() => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount() => 0;
        public int GetH12DivergentCount() => 0;
        public int GetH12SuppressedCount() => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses) => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => ([], []);
        public byte[] EncodeMessage(string message) => new byte[79];
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => (new float[180_000], new float[180_000]);
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag) => (0, new float[180_000]);
        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request) => throw new InvalidOperationException("the lean entry was called with engine classic");
    }

    // ── D2: threads ──────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 D2: the lean engine's worker count defaults to 2, follows a change on the next cycle and is clamped to 1 to 16")]
    public async Task Threads_Default2_FollowsChange_Clamped()
    {
        var fake = new LeanFake();
        var (decoder, _) = Build(fake);

        await decoder.DecodeAsync(LoudPcm(), Start, null);
        decoder.SetLeanThreads(4);
        await decoder.DecodeAsync(LoudPcm(), Start, null);
        decoder.SetLeanThreads(0);
        await decoder.DecodeAsync(LoudPcm(), Start, null);
        decoder.SetLeanThreads(99);
        await decoder.DecodeAsync(LoudPcm(), Start, null);

        fake.ThreadsSeen.Should().Equal(DecoderConfig.ResolveThreads(DecoderConfig.AutoThreads, Environment.ProcessorCount), 4, 1, 16);   // an unconfigured decoder is automatic
        new DecoderConfig { Threads = 99 }.ResolveThreads(64).Should().Be(16);
        new DecoderConfig().Threads.Should().Be(DecoderConfig.AutoThreads);
    }

    // ── D3: errors ───────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 D3: a native error code is logged, what the call had already written is published, and the next cycle runs")]
    public async Task NativeErrorCode_IsLogged_PartialPublished_NextCycleRuns()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22")], Stats(error: LeanCycleStats.ErrFault, results: 1)));
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("Q2DEF Q3GHI -07")], Stats(results: 1)));
        var (decoder, log) = Build(fake);

        var first = await decoder.DecodeAsync(LoudPcm(), Start, null);
        var second = await decoder.DecodeAsync(LoudPcm(), Start.AddSeconds(15), null);

        first.Select(r => r.Message).Should().Equal("CQ Q1ABC JO22");
        second.Select(r => r.Message).Should().Equal("Q2DEF Q3GHI -07");
        fake.ThreadsSeen.Should().HaveCount(2);
        log.Entries.Should().Contain(e => e.Level == LogLevel.Warning && e.Message.Contains("lean native error -3"));
        LeanLines(log).Should().HaveCount(2).And.Contain(l => l.Contains("error=-3")).And.Contain(l => l.Contains("error=0"));
    }

    [Fact(DisplayName = "FR-108: DR-2 D3: an exception around the native call is logged as an error, the cycle yields nothing, and the next cycle runs")]
    public async Task ExceptionAroundTheCall_IsLogged_NextCycleRuns()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => throw new EntryPointNotFoundException("ftz_decode_cycle"));
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22")], Stats(results: 1)));
        var (decoder, log) = Build(fake);

        var first = await decoder.DecodeAsync(LoudPcm(), Start, null);
        var second = await decoder.DecodeAsync(LoudPcm(), Start.AddSeconds(15), null);

        first.Should().BeEmpty();
        second.Select(r => r.Message).Should().Equal("CQ Q1ABC JO22");
        log.Entries.Should().Contain(e => e.Level == LogLevel.Error && e.Message.Contains("lean decode failed"));
        LeanLines(log).Should().Contain(l => l.Contains($"error={Ft8Decoder.LeanErrManaged}"));
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: the lean cycle keeps the text de-duplication and the plausibility filter of every classic batch")]
    public async Task Lean_KeepsDedupAndPlausibility()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome(
            [Native("CQ Q1ABC JO22", 1200), Native("CQ Q1ABC JO22", 1900), Native("Q2DEF Q3GHI RR73 EXTRA WORDS HERE", 800)], Stats(results: 3)));
        var (decoder, _) = Build(fake);

        var results = await decoder.DecodeAsync(LoudPcm(), Start, null);

        results.Select(r => r.Message).Should().Equal("CQ Q1ABC JO22");
        results[0].FreqHz.Should().Be(1200, "the first occurrence, in the native (sorted) order, is the one kept");
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: under engine lean the early decode returns nothing and does not call the native layer")]
    public async Task Lean_EarlyDecode_ReturnsNothing()
    {
        var fake = new LeanFake();
        var (decoder, _) = Build(fake);

        var early = await decoder.DecodeEarlyAsync(LoudPcm(), Start, null);

        early.Should().BeEmpty();
        fake.ThreadsSeen.Should().BeEmpty();
    }

    // ── step 2b: the request, the tiers ──────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b D7: the decoder hands the native call the CQ-AP setting (read once per cycle) and what is left of the 13 s budget less the publish reserve")]
    public async Task Request_CarriesCqApAndTheBudget()
    {
        var fake = new LeanFake();
        var (decoder, _) = Build(fake);

        await decoder.DecodeAsync(LoudPcm(), Start, null);
        decoder.SetCqApEnabled(true);
        await decoder.DecodeAsync(LoudPcm(), Start, null);

        fake.Requests.Select(r => r.CqAp).Should().Equal(false, true);
        foreach (var r in fake.Requests)
        {
            r.BudgetMs.Should().NotBeNull();
            r.BudgetMs!.Value.Should().BeInRange(12_000, 12_750, "13 s less the 250 ms publish reserve, less what this decode has used");
        }
    }

    [Fact(DisplayName = "FR-108: DR-2 2b D6: a tier-B row carries the fallback's provenance tag, a CQ-AP row the cq tag, a tier-A row neither")]
    public async Task Tiers_MapToTheClassicProvenanceTags()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome(
            [Native("CQ Q1ABC JO22", 1200), Native("Q2DEF Q3GHI -07", 1800), Native("CQ Q4JKL JO22", 2400)], Stats(results: 3))
        { Tiers = [LeanTier.A, LeanTier.B, LeanTier.CqAp] });
        var (decoder, _) = Build(fake);

        var results = await decoder.DecodeAsync(LoudPcm(), Start, null);

        results.Select(r => (r.Path, r.ApKind)).Should().Equal(
            (Ft8Decoder.PathOrdinary, ApKind.None), (Ft8Decoder.PathFallback, ApKind.None), (Ft8Decoder.PathOrdinary, ApKind.Cq));
    }

    // ── D5 / test 5: the log line ────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 test 5: the lean log line is one Information line per cycle, carries counts and times only, and no message text or callsign appears in any log line")]
    public async Task LogLine_OnePerCycle_CountsAndTimesOnly()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22", 1200), Native("Q2DEF Q3GHI -07", 1800)], Stats(results: 2)));
        var (decoder, log) = Build(fake);

        await decoder.DecodeAsync(LoudPcm(), Start, null);

        var lines = LeanLines(log).ToList();
        lines.Should().ContainSingle();
        lines[0].Should().Be(
            "Cycle 12:00:00: lean: candidates=40 tierA=2 results=2 threads=2 abandoned=0 error=0 " +
            "tierB: eligible=7 attempted=6 crc=3 f1b=2 gated=1 published=1 edge=1 skipped=1 " +
            "cqAp: attempts=4 decodes=1 " +
            "wall_ms spectrogram=11.0 candidates=2.0 tierA=30.0 tierB=40.0 cqAp=3.0 unpack=0.5 total=44.0 " +
            "cpu_ms spectrogram=10.0 candidates=2.0 tierA=55.0 tierB=70.0 cqAp=5.0 unpack=0.4 total=67.4 " +
            "s3: rounds=0 ungated=0 fitSkipped=0 wall_ms=0.0 cpu_ms=0.0 fitCpu_ms=0.0 searchCpu_ms=0.0 decodeCpu_ms=0.0 otherCpu_ms=0.0 " +
            "effort=normal batches: b1=0 b2=0 b3=0 xc=off xcDetected=0.");
        foreach (var (_, message) in log.Entries)
            foreach (var token in new[] { "Q1ABC", "Q2DEF", "Q3GHI", "JO22", "-07", "CQ " })
                message.Should().NotContain(token, "counts and times only, never a callsign or a message (HK-037)");
    }

    [Fact(DisplayName = "FR-108: DR-2 2c D7: the log line shows each round, and the fit CPU and the search CPU separately, as counts and times only")]
    public async Task LogLine_ShowsEachRound_FitAndSearchCpuSeparately()
    {
        var round0 = new LeanRoundStats(0, 0, 0, 40, 40, 2, 2, 0, 0, 0, 0, 11_000, 10_000, 2_000, 2_000, 30_000, 55_000);
        var round1 = new LeanRoundStats(2, 1, 1, 30, 4, 1, 1, 0, 800_000, 1_500_000, 6_000, 12_000, 11_000, 3_000, 2_500, 25_000, 41_000);
        var round2 = new LeanRoundStats(1, 1, 0, 25, 2, 0, 0, 0, 400_000, 700_000, 3_000, 12_000, 11_000, 3_000, 2_500, 9_000, 15_000);
        var withRounds = Stats(results: 3) with { RoundsRun = 2, Ungated = 0, Rounds = [round0, round1, round2, default] };
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22", 1200), Native("Q2DEF Q3GHI -07", 1800)], withRounds));
        var (decoder, log) = Build(fake);

        await decoder.DecodeAsync(LoudPcm(), Start, null);

        var line = LeanLines(log).Single();
        line.Should().Contain("s3: rounds=2 ungated=0 fitSkipped=0 wall_ms=1264.0");           // 800+12+3+25 and 400+12+3+9 ms: every stage of both rounds
        line.Should().Contain("fitCpu_ms=2200.0 searchCpu_ms=5.0 decodeCpu_ms=56.0 otherCpu_ms=31.0");   // fits 1500+700; search 2.5+2.5; decode 41+15; sum 6+3 and spec 11+11
        line.Should().Contain(" r1[fits=2 skipped=0 subtracted=1 fitNone=1 found=30 kept=4 tierA=1 results=1 ungated=0 wall_ms sub=800.0 spec=12.0 search=3.0 decode=25.0 cpu_ms fit=1500.0 sum=6.0 spec=11.0 search=2.5 decode=41.0]");
        line.Should().Contain(" r2[fits=1 skipped=0 subtracted=1 fitNone=0 found=25 kept=2 tierA=0 results=0 ungated=0 ");
        line.Should().NotContain(" r3[", "a round that never started is not written");
        line.Should().NotContain(" r0[", "round 0 is the line's own first part");
        foreach (var token in new[] { "Q1ABC", "Q2DEF", "Q3GHI", "JO22", "-07", "CQ " })
            line.Should().NotContain(token);
    }

    [Fact(DisplayName = "FR-108: DR-2 2c D1: the lean cycle asks for the loop, and carries the residual settings only in Both mode")]
    public async Task Request_AsksForTheLoop_AndTheResidualSettingsFollowTheAudioMode()
    {
        var fake = new LeanFake();
        var (decoder, _) = Build(fake);
        decoder.SetCoherentFallbackResidualUngated(true);
        decoder.SetCoherentFallbackResidualCandidates(true);

        decoder.SetCoherentFallbackAudio(CoherentFallbackAudio.Both);
        await decoder.DecodeAsync(LoudPcm(), Start, null);
        decoder.SetCoherentFallbackAudio(CoherentFallbackAudio.Original);
        await decoder.DecodeAsync(LoudPcm(), Start, null);

        fake.Requests.Should().HaveCount(2);
        fake.Requests[0].Rounds.Should().BeTrue();
        fake.Requests[0].ResidualUngated.Should().BeTrue();
        fake.Requests[0].ResidualCandidates.Should().BeTrue();
        fake.Requests[1].Rounds.Should().BeTrue("the loop does not depend on the fallback audio mode");
        fake.Requests[1].ResidualUngated.Should().BeFalse("the ungating acts only in Both mode, as in the classic path");
        fake.Requests[1].ResidualCandidates.Should().BeFalse("the residual-candidates rule acts only in Both mode, as in the classic path");
    }

    [Fact(DisplayName = "FR-108: DR-2 D5: a lean cycle still writes the ordinary 'decode(s) found' cycle line that log parsers read")]
    public async Task Lean_StillWritesTheOrdinaryCycleLine()
    {
        var fake = new LeanFake();
        fake.Outcomes.Enqueue(() => new LeanCycleOutcome([Native("CQ Q1ABC JO22")], Stats(results: 1)));
        var (decoder, log) = Build(fake);

        await decoder.DecodeAsync(LoudPcm(), Start, null);

        log.Entries.Should().ContainSingle(e => e.Level == LogLevel.Information && e.Message.StartsWith("Cycle 12:00:00: 1 decode(s) found, elapsed="));
    }
}
