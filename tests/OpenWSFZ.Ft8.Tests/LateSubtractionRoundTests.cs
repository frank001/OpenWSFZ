using System.Collections.Concurrent;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// LATE-SUB L1' (FR-102): <c>decoder.lateSubtractionRound</c>, default OFF. After the coherent fallback's batch (Deep only, fallback on, a residual
/// buffer from <c>CohFallbackAudioSelector.Select</c>) one more <c>SubtractionPass.RunThirdPassAsync</c> runs on that buffer, subtracting the natives
/// behind the decodes PUBLISHED in batches 3 and 4, and its new decodes leave as batch 5 through the fallback's own delegate. Order is asserted from a
/// recorded event list and time from a <see cref="TimeProvider"/> the test owns - never from a sleep. The native calls are faked (scripted per call
/// number), as in <see cref="CoherentFallbackWiringTests"/> and <see cref="ThirdPassDeepTests"/>.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, order, identity and aggregates.</para>
/// </summary>
public sealed class LateSubtractionRoundTests
{
    private static readonly DateTime CycleStart = new(2026, 10, 30, 12, 0, 0, DateTimeKind.Utc);

    private const string P0A = "Q1ABC Q1XYZ JO33";
    private const string P0B = "Q1GHI Q1JKL FN20";
    private const string ResidMsg = "Q1DEF Q1UVW EN37";
    private const string ThirdMsg = "Q1MNO Q1PQR IO91";
    private const string FbMsg = "Q1CCC Q1DDD RR73";
    private const string LateMsg = "Q1LAA Q1LBB IO91";

    private static Ft8NativeResult Msg(string message, int freqHz = 1500, float dt = 0.2f, int snr = -10)
        => new() { FreqHz = freqHz, Dt = dt, Snr = snr, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static float[] Normalised() => Ft8Decoder.NormalisePcm(LoudPcm(), 0.20f /* Ft8Decoder.PcmNormalisationTargetRms */);

    private static byte[] Tones(string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        return tones;
    }

    private static CohFallbackRow Row(int id, float freq = 1000f)
    {
        var payload = new byte[12];
        payload[0] = (byte)id;
        return new CohFallbackRow(freq, 0.3f, freq + 0.3f, 0.31f, 0, false, CohFallbackState.NewGated, -21, 12.0, payload);
    }

    private static CohFallbackStats Stats(int n)
        => new(n + 5, 5, 0, n, n, n, n, n, n, 0, 0, 1, 2, 3, 123.4);

    private static CohFallbackRunResult RunOf(params int[] ids)
        => new(Stats(ids.Length), ids.Select(i => Row(i, 1000f + 100f * i)).ToArray()) { Workers = 4 };

    private enum FitMode { Ok, DeadlineRc, Throw }

    /// <summary>
    /// DecodeAll answers by call number (1 = pass 0, 2 = residual, 3 = third pass, 4 = the late round - or 3 when the third pass was skipped). The
    /// analytic-signal call count tells a fit which stage it belongs to (1 = residual pass, 2 = third pass, 3 = late round); the fits of every
    /// stage are recorded with the tones they were asked to subtract.
    /// </summary>
    private sealed class LateInterop(Ft8NativeResult[][] decodes, CohFallbackRunResult? run) : IFt8NativeInterop
    {
        private readonly object _gate = new();
        public int MaxDecodePasses => 2;
        public int DecodeAllCallCount { get; private set; }
        public int AnalyticCallCount { get; private set; }
        public int RunCalls { get; private set; }

        /// <summary>Every native call and every delivered batch, in order (the "analytic" calls are filtered by the tests that do not care).</summary>
        public List<string> Calls { get; } = [];

        /// <summary>The array each DecodeAll call received, in call order.</summary>
        public List<float[]> DecodePcms { get; } = [];

        /// <summary>The PCM each fallback run was handed, in call order.</summary>
        public List<float[]> RunPcms { get; } = [];

        /// <summary>stage (analytic call count) to the (Dt, Freq, tones) of every signal fitted in it.</summary>
        public Dictionary<int, List<(float Dt, float Freq, byte[] Tones)>> FitsByStage { get; } = new();

        public Dictionary<int, string> Texts { get; init; } = new();
        public float ShatValue { get; init; }
        public FitMode ResidualFit { get; init; } = FitMode.Ok;
        public FitMode LateFit { get; init; } = FitMode.Ok;

        /// <summary>The analytic call number of the late round (3 normally; 2 when the third pass is skipped).</summary>
        public int LateStage { get; init; } = 3;

        /// <summary>Messages the encoder cannot encode (the pass skips them as it does a real unencodable text).</summary>
        public HashSet<string> Unencodable { get; init; } = [];

        /// <summary>From the n-th call for a text on, the encoder answers with another message's tones (a stand-in for a payload the dedup cannot match).</summary>
        public Dictionary<string, (int FromCall, string As)> EncodeAlias { get; init; } = new();

        private readonly Dictionary<string, int> _encodeCalls = new();

        public Action<int>? OnDecodeAll { get; init; }

        public void Note(string what) { lock (_gate) Calls.Add(what); }

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            int n;
            lock (_gate) { n = ++DecodeAllCallCount; Calls.Add("decode" + n); DecodePcms.Add(pcm); }
            OnDecodeAll?.Invoke(n);
            return n <= decodes.Length ? decodes[n - 1] : [];
        }

        public byte[] EncodeMessage(string message)
        {
            int nth;
            lock (_gate) { _encodeCalls[message] = nth = _encodeCalls.GetValueOrDefault(message) + 1; }
            if (Unencodable.Contains(message)) throw new InvalidOperationException("not encodable (test double)");
            if (EncodeAlias.TryGetValue(message, out var alias) && nth >= alias.FromCall) return Tones(alias.As);
            return Tones(message);
        }

        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        {
            lock (_gate) { AnalyticCallCount++; Calls.Add("analytic"); }
            return (new float[pcm.Length], new float[pcm.Length]);
        }

        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        {
            int stage;
            lock (_gate)
            {
                stage = AnalyticCallCount;
                if (!FitsByStage.TryGetValue(stage, out var list)) FitsByStage[stage] = list = [];
                list.Add((decodedDtS, decodedFreqHz, tones));
            }
            var mode = stage == 1 ? ResidualFit : stage == LateStage ? LateFit : FitMode.Ok;
            if (mode == FitMode.Throw) throw new NativeAccessViolationException();
            var shat = new float[180_000];
            if (ShatValue != 0f) Array.Fill(shat, ShatValue);
            return (mode == FitMode.DeadlineRc ? Ft8LibInterop.SubfeasRcCancelled : 0, shat);
        }

        public byte[]? CohFallbackSnapshot()
        {
            lock (_gate) Calls.Add("snapshot");
            return [1, 2, 3, 4];
        }

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
            => CohFallbackRun(pcm, snapshot, budgetMs, workers, ct);

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        {
            lock (_gate) { RunCalls++; Calls.Add("run"); RunPcms.Add(pcm); }
            return run;
        }

        public string? CohFallbackUnpack(byte[] payload)
        {
            lock (_gate) Calls.Add("unpack");
            return Texts.TryGetValue(payload[0], out var t) ? t : null;
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

    /// <summary>A time source that moves only when a test advances it (1 tick = 100 ns).</summary>
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
        public string? LateLine => Lines.SingleOrDefault(l => l.StartsWith("Late subtraction round:"));
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => _q.Enqueue(formatter(state, exception));
    }

    private static Ft8Decoder Build(IFt8NativeInterop interop, DecodingDepth depth = DecodingDepth.Deep, bool fallback = true, bool late = true,
                                    CoherentFallbackAudio audio = CoherentFallbackAudio.Residual, ILogger<Ft8Decoder>? log = null,
                                    TimeProvider? time = null)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop: interop, timeProvider: time);
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(depth);
        d.SetCoherentFallbackEnabled(fallback);
        d.SetCoherentFallbackAudio(audio);
        d.SetLateSubtractionRound(late);
        return d;
    }

    private sealed record Delivered(int Batch, DecodeResult[] Results)
    {
        public string[] Messages => Results.Select(r => r.Message).ToArray();
    }

    private static async Task<List<Delivered>> RunStaged(Ft8Decoder decoder, LateInterop interop, Action<int>? onBatch = null)
    {
        var got = new List<Delivered>();
        await decoder.DecodeStagedAsync(LoudPcm(), CycleStart, null, (n, b) =>
        {
            got.Add(new Delivered(n, b.ToArray()));
            interop.Note("batch" + n);
            onBatch?.Invoke(n);
            return Task.CompletedTask;
        });
        return got;
    }

    private static readonly Ft8NativeResult[] Pass0 = [Msg(P0A), Msg(P0B, 1800)];
    private static readonly Ft8NativeResult[] Resid = [Msg(ResidMsg, 2100)];
    private static readonly Ft8NativeResult[] Third = [Msg(ThirdMsg, 2400, 0.35f)];
    private static readonly Ft8NativeResult[] Late = [Msg(LateMsg, 1200)];

    /// <summary>The usual Deep cycle: batches 1 to 3 from the scripted decodes, batch 4 (FbMsg) from the fallback, then the late round's decode.</summary>
    private static LateInterop Standard(Ft8NativeResult[]? late = null, FitMode lateFit = FitMode.Ok, float shat = 0.01f)
        => new([Pass0, Resid, Third, late ?? Late], RunOf(3)) { Texts = { [3] = FbMsg }, ShatValue = shat, LateFit = lateFit };

    private static string[] Order(LateInterop i) => i.Calls.Where(c => c != "analytic").ToArray();

    // ── the setting ──────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the setting defaults to false (config record and bare decoder) and the setter and getter round-trip")]
    public void Setting_DefaultsOff_RoundTrips()
    {
        new DecoderConfig().LateSubtractionRound.Should().BeFalse();
        new DecoderConfig { LateSubtractionRound = true }.LateSubtractionRound.Should().BeTrue();
        var d = Build(Standard(), late: false);
        d.LateSubtractionRound.Should().BeFalse();
        d.SetLateSubtractionRound(true);
        d.LateSubtractionRound.Should().BeTrue();
        d.SetLateSubtractionRound(false);
        d.LateSubtractionRound.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': OFF is a no-op - batches 1 to 4 and the native call order are today's, no extra decode, no log line, no counters")]
    public async Task Off_IsNoOp()
    {
        var log = new LineLog();
        var interop = Standard();
        var decoder = Build(interop, late: false, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        Order(interop).Should().Equal("decode1", "snapshot", "batch1", "decode2", "batch2", "decode3", "batch3", "run", "unpack", "batch4");
        interop.DecodeAllCallCount.Should().Be(3);
        log.Lines.Should().NotContain(l => l.Contains("Late subtraction round"));
        decoder.GetLateRoundCounters().Should().Be(new Ft8Decoder.LateRoundCounters(0, 0, 0, 0, 0, 0));
    }

    // ── the round ───────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-102: LATE-SUB L1': ON on Deep with the fallback - one extra decode after batch 4, new decodes leave as batch 5 (residual path), batches 1 to 4 unchanged")]
    public async Task On_PublishesBatch5_AfterBatch4()
    {
        var interop = Standard();
        var decoder = Build(interop);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4, 5);
        got[0].Messages.Should().Equal(P0A, P0B);
        got[1].Messages.Should().Equal(ResidMsg);
        got[2].Messages.Should().Equal(ThirdMsg);
        got[3].Messages.Should().Equal(FbMsg);
        got[4].Messages.Should().Equal(LateMsg);
        got[4].Results.Single().Path.Should().Be(Ft8Decoder.PathResidual, "R5: mapped by MapNative(..., PathResidual)");
        Ft8Decoder.LateRoundBatch.Should().Be(5);
        interop.DecodeAllCallCount.Should().Be(4);
        decoder.GetLateRoundCounters().Should().Be(new Ft8Decoder.LateRoundCounters(1, 0, 0, 0, 0, 1));
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': ordering - batches 1 to 4 and their native calls come first; the round's decode (the cycle's last hash-table access) follows the fallback's unpack and precedes batch 5, all inside the staged call")]
    public async Task On_HashTableOrdering_LateDecodeAfterFallbackUnpack()
    {
        var interop = Standard();
        var decoder = Build(interop);

        await RunStaged(decoder, interop);   // returns only when the whole staged decode has: the pump holds the decode gate across exactly this call

        var order = Order(interop);
        order.Should().Equal("decode1", "snapshot", "batch1", "decode2", "batch2", "decode3", "batch3", "run", "unpack", "batch4", "decode4", "batch5");
        order.LastIndexOf("unpack").Should().BeLessThan(order.IndexOf("decode4"), "the fallback's text unpack is done before the round's native decode starts");
        order.IndexOf("decode4").Should().BeLessThan(order.IndexOf("batch5"));
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the round reads the buffer the fallback was handed (R3), does not mutate it, and subtracts the published batch-3 and batch-4 signals from a copy")]
    public async Task On_BufferIsR3_NotMutated_SubtractsFitList()
    {
        var log = new LineLog();
        var interop = Standard();
        var decoder = Build(interop, log: log);

        await RunStaged(decoder, interop);

        var orig = Normalised();
        // pass 0: 2 signals (x - 0.02); the third pass fits the residual pass's 1 new signal (x - 0.03); the late round fits batch 3 + batch 4 (2 signals): x - 0.05.
        interop.RunPcms.Single()[100].Should().BeApproximately(orig[100] - 0.03f, 1e-5f,
            "the fallback read the third pass's buffer, and it still holds that after the round (SubtractionPass.cs:425 clones its input)");
        interop.DecodePcms[3][100].Should().BeApproximately(orig[100] - 0.05f, 1e-5f, "the round decoded a further-subtracted copy");
        log.LateLine.Should().Contain("buffer=R3");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the fit list is the natives behind the PUBLISHED batch-3 and batch-4 decodes: FreqHz rounded, Dt unrounded, batches 1 and 2 not re-fitted")]
    public async Task FitList_PublishedBatch3And4_UnroundedDt()
    {
        var interop = Standard();
        await RunStaged(Build(interop), interop);

        var fits = interop.FitsByStage[3];
        fits.Should().HaveCount(2);
        var third = fits.Single(f => f.Tones.SequenceEqual(Tones(ThirdMsg)));
        third.Freq.Should().Be(2400f);
        third.Dt.Should().Be(0.35f, "batch 3's native, Dt as the pass produced it");
        var fb = fits.Single(f => f.Tones.SequenceEqual(Tones(FbMsg)));
        fb.Freq.Should().Be(1300f, "round(OutFreqHz = 1300.3) as the fallback builds the native");
        fb.Dt.Should().Be(0.31f, "OutDtS unrounded, not Math.Round(Dt, 1)");
        fits.Should().NotContain(f => f.Tones.SequenceEqual(Tones(P0A)) || f.Tones.SequenceEqual(Tones(ResidMsg)),
            "batch-1 and batch-2 decodes are known to the dedup but not re-fitted");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1' (F1): a batch-3 text that repeats a batch-1 text, an implausible batch-3 text, a batch-4 text that repeats batch 3 and an implausible batch-4 text are NOT in the fit list")]
    public async Task FitList_ExcludesWhatMapNativeDidNotPublish()
    {
        const string implausible3 = "Q1EEE Q1FFF ZA99";
        const string implausible4 = "Q1AAA Q1BBB ZA99";
        var log = new LineLog();
        var interop = new LateInterop(
            [Pass0, Resid, [Msg(P0A, 1500), Msg(implausible3, 1600), Msg(ThirdMsg, 2400, 0.35f)], Late],
            new CohFallbackRunResult(Stats(3), [Row(1, 1100f), Row(2, 1200f), Row(3, 1300f)]) { Workers = 4 })
        {
            Texts = { [1] = ThirdMsg, [2] = implausible4, [3] = FbMsg },
            ShatValue = 0.01f,
            // The pass dedups on the payload, so let two of the repeats through it (a payload it cannot match), leaving MapNative's per-cycle rules to drop them.
            EncodeAlias = { [P0A] = (3, "Q1ABC Q1XYZ JO34"), [implausible3] = (1, "Q1EEE Q1FFF IO91") },
        };

        var got = await RunStaged(Build(interop, log: log), interop);

        got.Single(b => b.Batch == 3).Messages.Should().Equal(ThirdMsg);   // the repeat of a batch-1 text and the implausible text are dropped by MapNative
        got.Single(b => b.Batch == 4).Messages.Should().Equal(FbMsg);   // the repeat of batch 3's text and the implausible text are dropped by MapNative
        var fits = interop.FitsByStage[3];
        fits.Should().HaveCount(2);
        fits.Should().Contain(f => f.Tones.SequenceEqual(Tones(ThirdMsg)));
        fits.Should().Contain(f => f.Tones.SequenceEqual(Tones(FbMsg)));
        log.LateLine.Should().Contain("fit=2, refused=0");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the refusal count - a published fit entry the encoder cannot encode is skipped as in the third pass and counted in the log line")]
    public async Task RefusalCount_InLogLine()
    {
        var log = new LineLog();
        var withRefusal = new LateInterop([Pass0, Resid, Third, Late], RunOf(3)) { Texts = { [3] = FbMsg }, ShatValue = 0.01f, Unencodable = { FbMsg } };

        var got = await RunStaged(Build(withRefusal, log: log), withRefusal);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4, 5);
        log.LateLine.Should().Contain("fit=2, refused=1");
        withRefusal.FitsByStage[3].Should().ContainSingle("only the encodable entry was fitted");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the third pass skipped - the round runs on the residual pass's buffer (R2) with batch 4 alone in the fit list")]
    public async Task On_ThirdPassSkipped_UsesR2()
    {
        var log = new LineLog();
        var interop = new LateInterop([Pass0, [], Late], RunOf(3)) { Texts = { [3] = FbMsg }, ShatValue = 0.01f, LateStage = 2 };

        var got = await RunStaged(Build(interop, log: log), interop);

        got.Select(b => b.Batch).Should().Equal(1, 4, 5);   // (the residual pass found nothing: no batch 2; no third pass: no batch 3)
        interop.FitsByStage[2].Should().ContainSingle().Which.Tones.Should().Equal(Tones(FbMsg));
        interop.DecodePcms[2][100].Should().BeApproximately(Normalised()[100] - 0.03f, 1e-5f, "R2 = x - 0.02, then the one batch-4 signal");
        log.LateLine.Should().Contain("buffer=R2").And.Contain("fit=1");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': Both mode - the round reads the residual buffer the fallback's first run read")]
    public async Task On_BothMode_UsesResidualBuffer()
    {
        var log = new LineLog();
        var interop = Standard();
        await RunStaged(Build(interop, audio: CoherentFallbackAudio.Both, log: log), interop);

        interop.RunPcms.Should().HaveCount(2, "Both runs the fallback on the residual buffer, then on the original");
        log.LateLine.Should().Contain("outcome=ran").And.Contain("buffer=R3");
        interop.DecodePcms[3][100].Should().BeApproximately(Normalised()[100] - 0.05f, 1e-5f);
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': a late decode that repeats an already-published text publishes nothing and the outcome is ran with new=0")]
    public async Task RanWithNothingNew_PublishesNothing()
    {
        var log = new LineLog();
        var interop = Standard(late: [Msg(ThirdMsg, 2400)]);   // already fitted: the pass's payload dedup drops it

        var got = await RunStaged(Build(interop, log: log), interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        log.LateLine.Should().Contain("outcome=ran").And.Contain("new=0, published=0").And.Contain("batch5PublishMs=-1");
    }

    // ── skips: each is counted and logged ────────────────────────────────────────────────────────────────────

    private static void ExpectSkip(LineLog log, Ft8Decoder decoder, string reason)
    {
        log.LateLine.Should().StartWith($"Late subtraction round: outcome={reason},");
        decoder.GetLateRoundCounters().Should().Be(new Ft8Decoder.LateRoundCounters(0, 1, 0, 0, 0, 0));
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': Normal depth - the setting has no effect: skipped-normal-depth, no batch 5, no extra decode")]
    public async Task Skip_NormalDepth()
    {
        var log = new LineLog();
        var interop = Standard();
        var decoder = Build(interop, DecodingDepth.Normal, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3);   // on Normal the fallback is batch 3
        interop.DecodeAllCallCount.Should().Be(2);
        ExpectSkip(log, decoder, "skipped-normal-depth");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the fallback did not run (disabled) - skipped-fallback-not-run, no batch 5")]
    public async Task Skip_FallbackNotRun()
    {
        var log = new LineLog();
        var interop = Standard();
        var decoder = Build(interop, fallback: false, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3);
        interop.RunCalls.Should().Be(0);
        interop.DecodeAllCallCount.Should().Be(3);
        ExpectSkip(log, decoder, "skipped-fallback-not-run");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': Select hands the fallback the original audio (mode Original) - skipped-no-residual, the fallback itself unchanged")]
    public async Task Skip_NoResidual_OriginalAudioMode()
    {
        var log = new LineLog();
        var interop = Standard();
        var decoder = Build(interop, audio: CoherentFallbackAudio.Original, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        interop.RunCalls.Should().Be(1);
        interop.DecodeAllCallCount.Should().Be(3);
        ExpectSkip(log, decoder, "skipped-no-residual");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the residual pass was abandoned (Select steps down to the original audio) - skipped-no-residual")]
    public async Task Skip_NoResidual_ResidualPassAbandoned()
    {
        var log = new LineLog();
        var interop = new LateInterop([Pass0, Resid, Third, Late], RunOf(3)) { Texts = { [3] = FbMsg }, ResidualFit = FitMode.DeadlineRc };
        var decoder = Build(interop, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 4);
        interop.DecodeAllCallCount.Should().Be(1, "an abandoned residual pass never reaches its decode, and the round is skipped");
        ExpectSkip(log, decoder, "skipped-no-residual");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': pass 0 decoded nothing - the round does not run: skipped-nothing-decoded")]
    public async Task Skip_NothingDecodedInPass0()
    {
        var log = new LineLog();
        var interop = new LateInterop([[], Resid, Third, Late], RunOf(3)) { Texts = { [3] = FbMsg } };
        var decoder = Build(interop, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 4);
        interop.DecodeAllCallCount.Should().Be(1);
        ExpectSkip(log, decoder, "skipped-nothing-decoded");
    }

    // ── all-or-nothing ───────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-102: LATE-SUB L1': a round abandoned on the budget publishes nothing, does not throw, keeps batches 1 to 4 and is counted")]
    public async Task Abandoned_PublishesNothing()
    {
        var log = new LineLog();
        var interop = Standard(lateFit: FitMode.DeadlineRc);
        var decoder = Build(interop, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        interop.DecodeAllCallCount.Should().Be(3, "an abandoned pass never reaches its decode");
        decoder.GetLateRoundCounters().Should().Be(new Ft8Decoder.LateRoundCounters(1, 0, 0, 1, 0, 0));
        log.LateLine.Should().StartWith("Late subtraction round: outcome=abandoned,").And.Contain("new=0, published=0").And.Contain("batch5PublishMs=-1");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': a round that fails (contained exception) publishes nothing, does not throw, keeps batches 1 to 4 and is counted")]
    public async Task Failed_PublishesNothing()
    {
        var log = new LineLog();
        var interop = Standard(lateFit: FitMode.Throw);
        var decoder = Build(interop, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1, 2, 3, 4);
        decoder.GetLateRoundCounters().Should().Be(new Ft8Decoder.LateRoundCounters(1, 0, 0, 0, 1, 0));
        log.LateLine.Should().StartWith("Late subtraction round: outcome=failed,").And.Contain("published=0");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': nothing in the fit list (no published batch 3 or 4) - no-new, no decode, no batch 5")]
    public async Task EmptyFitList_NoNew()
    {
        var log = new LineLog();
        var interop = new LateInterop([Pass0, [], Late], RunOf(3)) { Texts = { }, ShatValue = 0.01f, LateStage = 2 };   // the fallback's payload has no text: nothing published
        var decoder = Build(interop, log: log);

        var got = await RunStaged(decoder, interop);

        got.Select(b => b.Batch).Should().Equal(1);
        interop.DecodeAllCallCount.Should().Be(2, "pass 0 and the residual pass only: the round never reached a decode");
        decoder.GetLateRoundCounters().Should().Be(new Ft8Decoder.LateRoundCounters(0, 0, 1, 0, 0, 0));
        log.LateLine.Should().StartWith("Late subtraction round: outcome=no-new, buffer=R2, fit=0,");
    }

    // ── the log line, with the clock under the test's control ────────────────────────────────────────────────

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the log line carries fbEndMs, startMs, elapsedMs, endMs, batch=5 and batch5PublishMs on the decode's own clock (a manual TimeProvider, no sleeps)")]
    public async Task LogLine_FieldsOnTheDecodesOwnClock()
    {
        var time = new ManualTimeProvider();
        var log = new LineLog();
        var interop = new LateInterop([Pass0, Resid, Third, Late], RunOf(3))
        {
            Texts = { [3] = FbMsg },
            ShatValue = 0.01f,
            OnDecodeAll = n => { if (n == 4) time.Advance(TimeSpan.FromMilliseconds(700)); },   // the round's own work
        };
        var decoder = Build(interop, log: log, time: time);

        await RunStaged(decoder, interop, onBatch: n => { if (n == 4) time.Advance(TimeSpan.FromMilliseconds(500)); });   // the fallback's hand-off takes 500 ms

        log.LateLine.Should().Be(
            "Late subtraction round: outcome=ran, buffer=R3, fit=2, refused=0, new=1, published=1, " +
            "fbEndMs=500, startMs=500, elapsedMs=700, endMs=1200, batch=5, batch5PublishMs=1200.");
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': one line per Deep cycle while ON, in the documented field order, aggregates only (no message text)")]
    public async Task LogLine_FieldOrder_NoMessageText()
    {
        var log = new LineLog();
        var interop = Standard();
        await RunStaged(Build(interop, log: log), interop);

        log.Lines.Count(l => l.StartsWith("Late subtraction round:")).Should().Be(1);
        log.LateLine.Should().MatchRegex(
            @"^Late subtraction round: outcome=ran, buffer=R3, fit=2, refused=0, new=1, published=1, fbEndMs=\d+, startMs=\d+, elapsedMs=\d+, endMs=\d+, batch=5, batch5PublishMs=\d+\.$");
        Regex.IsMatch(log.LateLine!, @"Q1[A-Z]{3}").Should().BeFalse("HK-037: the line never carries message text");
    }
}
