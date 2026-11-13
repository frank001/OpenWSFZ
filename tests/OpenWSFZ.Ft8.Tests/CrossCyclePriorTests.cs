using System.Collections.Concurrent;
using System.Reflection;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Dsp;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// XC-BUILD (FR-105): the prior store (R2, R3), the stage runner (R6, R8) and the decoder wiring (R1, R4, R7, R9 to R13), with the native decode calls faked and the template stage run for real on synthetic
/// cycle audio (QA's xorshift32 noise plus a phase-continuous 8-FSK message at a known position), so "found inside the window, missed outside it" is an assertion on a real detection. Every test must be able
/// to fail (QA mutates). TESTING_STRATEGY section 11: no fixed sleeps (the budget is a manual clock or a counting predicate), no wall-clock assertion, no randomness (every buffer is derived from a fixed seed).
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, positions and the published rows of a fake.</para>
/// </summary>
public sealed class CrossCyclePriorTests
{
    private static readonly DateTime T0 = new(2026, 11, 13, 12, 0, 0, DateTimeKind.Utc);
    private static DateTime At(int seconds) => T0.AddSeconds(seconds);

    private const string M = "Q1ABC Q1XYZ JO33";            // the message that repeats
    private const string Other = "Q1GHI Q1JKL FN20";         // a decoy decoded by pass 0 so a residual buffer exists
    private const string Other2 = "Q1MNO Q1PQR IO91";
    private const int MFreq = 1500;
    private const float MDt = 0.30f;
    private const double TestThreshold = 4.0;               // between noise (S_E* about 1.2) and a clean signal (about 7.5)

    private static byte[] Tones(string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        return tones;
    }

    private static Ft8NativeResult Msg(string message, int freqHz = MFreq, float dt = MDt)
        => new() { FreqHz = freqHz, Dt = dt, Snr = -12, Message = message };

    /// <summary>One cycle's audio: seeded noise plus any number of known messages at known positions (the true position, in the published dt convention).</summary>
    private static float[] Audio(uint seed, params (string Text, double FreqHz, double Dt)[] messages)
    {
        var x = XcSynth.Noise(seed, 1.0);
        foreach (var m in messages) XcSynth.AddMessage(x, Tones(m.Text), m.FreqHz, m.Dt, 0.5);
        return XcSynth.ToFloat(x);
    }

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
        public List<string> XcLines => Lines.Where(l => l.StartsWith("Cross-cycle prior:")).ToList();
        public string LastXc => XcLines.Last();
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => _q.Enqueue(formatter(state, exception));

        public static int Field(string line, string name)
        {
            var m = Regex.Match(line, name + @"=(-?\d+)");
            m.Success.Should().BeTrue($"the line has {name}=: {line}");
            return int.Parse(m.Groups[1].Value);
        }
    }

    private sealed class RecordingProbe : ICrossCyclePriorProbe
    {
        public ConcurrentQueue<CrossCycleTestRecord> Seen { get; } = new();
        public List<CrossCycleTestRecord> Records => Seen.ToList();
        public bool Throw { get; init; }
        public void Clear() { while (Seen.TryDequeue(out _)) { } }
        public void OnTemplateTested(in CrossCycleTestRecord record)
        {
            Seen.Enqueue(record);
            if (Throw) throw new InvalidOperationException("the sink threw (test double)");
        }
    }

    /// <summary>
    /// DecodeAll answers by call number within the cycle (1 = pass 0, 2 = the residual pass); the fallback finds nothing; the fits subtract nothing, so the residual buffer is a copy of the cycle audio.
    /// <see cref="AdvanceInFallback"/> moves the manual clock during the fallback run (a stand-in for a slow cycle).
    /// </summary>
    private sealed class XcInterop : IFt8NativeInterop
    {
        private readonly object _gate = new();
        private int _call;
        private Ft8NativeResult[][] _script = [];
        public ManualTimeProvider? Clock { get; init; }
        public TimeSpan AdvanceInFallback { get; init; }
        public int MaxDecodePasses => 2;

        public void NextCycle(params Ft8NativeResult[][] decodes) { lock (_gate) { _script = decodes; _call = 0; } }

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            int n;
            lock (_gate) n = ++_call;
            return n <= _script.Length ? _script[n - 1] : [];
        }

        public byte[]? CohFallbackSnapshot() => [1];

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, CancellationToken ct)
            => CohFallbackRun(pcm, snapshot, budgetMs, workers, ct);

        public CohFallbackRunResult? CohFallbackRun(float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
        {
            if (Clock is not null && AdvanceInFallback > TimeSpan.Zero) Clock.Advance(AdvanceInFallback);
            return new CohFallbackRunResult(new CohFallbackStats(5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 123.4), []) { Workers = 1 };
        }

        public string? CohFallbackUnpack(byte[] payload) => null;
        public byte[] EncodeMessage(string message) => Tones(message);
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => (new float[pcm.Length], new float[pcm.Length]);
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
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
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => (Array.Empty<float>(), Array.Empty<float>());
    }

    private static Ft8Decoder Build(XcInterop io, bool xc, bool shadow = false, double threshold = TestThreshold, ILogger<Ft8Decoder>? log = null,
                                    TimeProvider? time = null, bool late = false, ICrossCyclePriorProbe? probe = null)
    {
        var d = new Ft8Decoder(new FakeClock(T0), log, interop: io, timeProvider: time ?? io.Clock ?? new ManualTimeProvider());
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(DecodingDepth.Deep);
        d.SetCoherentFallbackEnabled(true);
        d.SetCoherentFallbackAudio(CoherentFallbackAudio.Both);
        d.SetLateSubtractionRound(late);
        d.SetCrossCyclePrior(xc);
        d.SetCrossCyclePriorShadow(shadow);
        d.SetCrossCyclePriorThreshold(threshold);
        d.CrossCyclePriorProbe = probe;
        return d;
    }

    private sealed record Published(int Batch, string Message, int FreqHz, int Snr, double Dt, int Path);

    private static async Task<List<Published>> Cycle(Ft8Decoder d, XcInterop io, DateTime start, float[] audio, string? band = null, params Ft8NativeResult[][] script)
    {
        io.NextCycle(script);
        var got = new List<Published>();
        await d.DecodeStagedAsync(audio, start, band, (n, b) =>
        {
            got.AddRange(b.Select(r => new Published(n, r.Message, r.FreqHz, r.Snr, r.Dt, r.Path)));
            return Task.CompletedTask;
        });
        return got;
    }

    /// <summary>Pass 0 decodes the given messages; the residual pass finds nothing new (so a residual buffer, the R2 one, exists).</summary>
    private static Ft8NativeResult[][] Pass0(params Ft8NativeResult[] decodes) => [decodes, []];

    // ── R1: the settings ───────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R1/R6: both flags default to false (config record and bare decoder), the setters and read-backs round-trip, and T_E is a shipped +infinity placeholder that replay can set")]
    public void Settings_Default_RoundTrip_AndThreshold()
    {
        new DecoderConfig().CrossCyclePrior.Should().BeFalse();
        new DecoderConfig().CrossCyclePriorShadow.Should().BeFalse();
        new DecoderConfig { CrossCyclePrior = true, CrossCyclePriorShadow = true }.CrossCyclePriorShadow.Should().BeTrue();

        var bare = new Ft8Decoder(new FakeClock(T0));
        bare.CrossCyclePrior.Should().BeFalse("the decoder object starts false");
        bare.CrossCyclePriorShadow.Should().BeFalse();
        bare.CrossCyclePriorThreshold.Should().Be(double.PositiveInfinity, "the shipped placeholder: QA's TRAIN arm measures the real value");
        Ft8Decoder.CrossCyclePriorThresholdDefault.Should().Be(double.PositiveInfinity);
        bare.CrossCyclePriorProbe.Should().BeNull("the shipped build has no subscriber");

        bare.SetCrossCyclePrior(true); bare.SetCrossCyclePriorShadow(true); bare.SetCrossCyclePriorThreshold(3.25);
        bare.CrossCyclePrior.Should().BeTrue();
        bare.CrossCyclePriorShadow.Should().BeTrue();
        bare.CrossCyclePriorThreshold.Should().Be(3.25);
        bare.SetCrossCyclePrior(false);
        bare.CrossCyclePrior.Should().BeFalse();
    }

    // ── R11: OFF is unchanged ──────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R11: OFF writes nothing (no store write, no log line, no batch 6) and every published row equals the ON run with T_E = +infinity")]
    public async Task Off_WritesNothing_AndRowsEqualOnWithInfiniteThreshold()
    {
        async Task<(List<Published> Rows, LineLog Log, Ft8Decoder D)> Run(bool xc)
        {
            var log = new LineLog();
            var io = new XcInterop();
            var d = Build(io, xc, shadow: xc, threshold: double.PositiveInfinity, log: log);
            var rows = new List<Published>();
            rows.AddRange(await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800))));
            rows.AddRange(await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100))));
            return (rows, log, d);
        }

        var off = await Run(false);
        var on = await Run(true);

        off.D.CrossCyclePriorStoreCount.Should().Be(0, "OFF: not one store write");
        off.Log.XcLines.Should().BeEmpty("OFF: no log line");
        off.Rows.Should().NotContain(p => p.Batch >= Ft8Decoder.TemplateBatch, "OFF: no batch 6");
        off.Rows.Should().NotBeEmpty();
        on.D.CrossCyclePriorStoreCount.Should().BeGreaterThan(0, "ON writes the store (a control: the OFF assertion above can fail)");
        on.Log.XcLines.Should().HaveCount(2, "one line per staged cycle while ON");
        on.Rows.Should().Equal(off.Rows, "ON with T_E = +infinity publishes the rows OFF publishes: the stage adds nothing and changes no existing batch");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R1/R11: with the stage ON, a call without the staged callbacks (DecodeAsync) and the early decode write nothing: no store write, no line")]
    public async Task NonStagedEntries_NeverTouchTheStore()
    {
        var log = new LineLog();
        var io = new XcInterop();
        var d = Build(io, xc: true, log: log);

        io.NextCycle(Pass0(Msg(M)));
        await d.DecodeAsync(Audio(3), At(0), currentBand: null);
        io.NextCycle(Pass0(Msg(M)));
        await d.DecodeEarlyAsync(Audio(4), At(15), currentBand: null);

        d.CrossCyclePriorStoreCount.Should().Be(0, "the early decode and the single-batch path never read or write the store");
        log.XcLines.Should().BeEmpty();
    }

    // ── R4, R5, R7: found inside the window, published as batch 6 ──────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R5/R7: a message published 30 s earlier is found at its place on the residual and published as batch 6 with PathTemplate, its own position and a coherent SNR; the cycle's batches 1 to 5 are unchanged")]
    public async Task KnownMessage_FoundInsideWindow_PublishedAsBatch6()
    {
        var log = new LineLog();
        var io = new XcInterop();
        var d = Build(io, xc: true, log: log);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800)));

        var audio = Audio(2, (M, MFreq, MDt));
        var rows = await Cycle(d, io, At(30), audio, null, Pass0(Msg(Other2, 2100)));

        var b6 = rows.Where(p => p.Batch == Ft8Decoder.TemplateBatch).ToList();
        b6.Should().ContainSingle();
        b6[0].Message.Should().Be(M);
        b6[0].Path.Should().Be(Ft8Decoder.PathTemplate).And.Be(3);
        b6[0].FreqHz.Should().Be(MFreq, "the argmax frequency, rounded to the published integer Hz");
        b6[0].Dt.Should().BeApproximately(MDt, 0.051, "the argmax dt, rounded to 0.1 s as every batch is");
        int expectedSnr = CrossCycleTemplateDetector.CoherentSnrDb(audio, MFreq, MDt, Tones(M));
        b6[0].Snr.Should().BeInRange(expectedSnr - 1, expectedSnr + 1, "the managed cf_snr_db at the argmax (scale-free, so the cycle's RMS normalisation does not change it)");
        rows.Where(p => p.Batch < Ft8Decoder.TemplateBatch).Select(p => p.Message).Should().Equal(new[] { Other2 }, "batches 1 to 5 hold what pass 0 decoded and nothing else");

        var line = log.LastXc;
        line.Should().Contain("outcome=ran");
        LineLog.Field(line, "priorsLive").Should().Be(2, "M and the decoy were published 30 s earlier");
        LineLog.Field(line, "testedLive").Should().Be(2);
        LineLog.Field(line, "detected").Should().Be(1);
        LineLog.Field(line, "published").Should().Be(1);
        line.Should().Contain("batch=6");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R5: the same prior is MISSED when its position is outside the window (12 Hz, or 0.4 s, away from where the message really is)")]
    public async Task KnownMessage_MissedOutsideWindow()
    {
        foreach (var (priorFreq, priorDt) in new[] { (MFreq + 12, MDt), (MFreq, MDt + 0.40f) })
        {
            var log = new LineLog();
            var io = new XcInterop();
            var d = Build(io, xc: true, log: log);
            await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M, priorFreq, priorDt), Msg(Other, 1800)));   // the prior was published at a different position than the true one

            var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

            rows.Should().NotContain(p => p.Batch == Ft8Decoder.TemplateBatch, $"prior at {priorFreq} Hz / {priorDt} s: the message is outside the +-3 Hz x +-0.12 s window");
            LineLog.Field(log.LastXc, "detected").Should().Be(0);
            LineLog.Field(log.LastXc, "testedLive").Should().Be(2, "it was tested, and missed");
        }
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R4: a cycle with no residual buffer (pass 0 decoded nothing) skips the stage, counted: outcome=skipped-no-residual, nothing tested or published")]
    public async Task NoResidual_SkipsAndCounts()
    {
        var log = new LineLog();
        var io = new XcInterop();
        var d = Build(io, xc: true, log: log);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M)));

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, [[], []]);

        rows.Should().BeEmpty();
        var line = log.LastXc;
        line.Should().Contain("outcome=skipped-no-residual");
        LineLog.Field(line, "priorsLive").Should().Be(1);
        LineLog.Field(line, "testedLive").Should().Be(0);
        LineLog.Field(line, "published").Should().Be(0);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R7/R8: with the late round ON the template batch is the last batch of the cycle (after batches 1 to 5), and still only when non-empty")]
    public async Task LateRoundOn_Batch6IsLast()
    {
        var io = new XcInterop();
        var d = Build(io, xc: true, late: true);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800)));

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

        rows.Select(p => p.Batch).Should().Equal(1, Ft8Decoder.TemplateBatch);
        rows.Last().Message.Should().Be(M);
    }

    // ── R2: the store ──────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R2: a batch-6 publish never enters the store (no chaining): the store holds exactly what batches 1 to 5 published")]
    public async Task Batch6_NeverEntersTheStore()
    {
        var log = new LineLog();
        var probe = new RecordingProbe();
        var io = new XcInterop();
        var d = Build(io, xc: true, log: log, probe: probe);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800)));
        d.CrossCyclePriorStoreCount.Should().Be(2);

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

        rows.Should().Contain(p => p.Batch == Ft8Decoder.TemplateBatch && p.Message == M, "control: batch 6 DID publish M");
        d.CrossCyclePriorStoreCount.Should().Be(3, "2 from t0 and 1 (the decoy) from t0 + 30 s; the batch-6 M is not stored");

        // The consequence: at t0 + 60, age 2 is the t0 + 30 cycle, which published only Other2 in batch 1; M is a prior only through t0's batch 1 (age 4). Were the batch-6 M stored, M would be at age 2.
        probe.Clear();
        await Cycle(d, io, At(60), Audio(3, (M, MFreq, MDt)), null, Pass0(Msg(Other, 1800)));
        LineLog.Field(log.LastXc, "priorsLive").Should().Be(3, "Other2 (age 2), and M and Other (age 4)");
        probe.Records.Select(r => r.AgeCycles).Should().Equal(new[] { 2, 4 }, "tested: Other2 (age 2) and M (age 4, from t0), never M at age 2 (the batch-6 publish); Other is excluded, this cycle decodes it itself");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R2/R3: priors count only at exactly -30, -60 and -90 s; a prior 45 s back, or beyond 90 s, is not live (the gap rule), and the ages the probe reports are 2, 4 and 6")]
    public async Task GapRule_OnlyExactAges_AndProbeAges()
    {
        var log = new LineLog();
        var probe = new RecordingProbe();
        var io = new XcInterop();
        var d = Build(io, xc: true, threshold: double.PositiveInfinity, log: log, probe: probe);

        // t0, t0 + 30 and t0 + 60 each publish one distinct message, at three different places; t0 + 15 and t0 + 45 are missing (a gap of one cycle between each).
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg("Q1AAA Q1BBB JO33", 1000)));
        await Cycle(d, io, At(30), Audio(2), null, Pass0(Msg("Q1CCC Q1DDD JO33", 1100)));
        await Cycle(d, io, At(60), Audio(3), null, Pass0(Msg("Q1EEE Q1FFF JO33", 1200)));
        probe.Clear();

        // t0 + 90 sees the three at ages 2, 4, 6.
        await Cycle(d, io, At(90), Audio(4), null, Pass0(Msg(Other, 1800)));
        probe.Records.Where(r => r.Kind == CrossCycleKind.Live).Select(r => r.AgeCycles).Should().Equal(2, 4, 6);
        LineLog.Field(log.LastXc, "priorsLive").Should().Be(3);

        // t0 + 105 (the t0 + 15 cycle is missing): age 1, 3, 5 are the opposite parity; the live ages 2, 4, 6 are t0 + 75 (missing), t0 + 45 (missing), t0 + 15 (missing) -> none.
        await Cycle(d, io, At(105), Audio(5), null, Pass0(Msg(Other, 1800)));
        LineLog.Field(log.LastXc, "priorsLive").Should().Be(0, "no cycle exists at exactly -30, -60 or -90 s of t0 + 105");

        // t0 + 150 is 90 s after t0 + 60 (age 6) and 120 s after t0 + 30 (age 8: gone).
        probe.Clear();
        await Cycle(d, io, At(150), Audio(6), null, Pass0(Msg(Other2, 2100)));
        LineLog.Field(log.LastXc, "priorsLive").Should().Be(2, "t0 + 90 (its decoy) is exactly -60 s and t0 + 60 is exactly -90 s; t0 + 30 is 120 s back and has aged out of the 90 s the store keeps");
        probe.Records.Where(r => r.Kind == CrossCycleKind.Live).Select(r => r.AgeCycles).Should().Equal(4, 6);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R2: a band change clears the store; the same band, and null on both cycles, keep it")]
    public async Task BandChange_ClearsTheStore()
    {
        foreach (var (first, second, expectedPriors) in new (string?, string?, int)[] { ("20m", "20m", 1), (null, null, 1), ("20m", "40m", 0), ("20m", null, 0), (null, "20m", 0) })
        {
            var log = new LineLog();
            var io = new XcInterop();
            var d = Build(io, xc: true, threshold: double.PositiveInfinity, log: log);
            await Cycle(d, io, At(0), Audio(1), first, Pass0(Msg(M)));

            await Cycle(d, io, At(30), Audio(2), second, Pass0(Msg(Other, 1800)));

            LineLog.Field(log.LastXc, "priorsLive").Should().Be(expectedPriors, $"bands '{first}' then '{second}'");
        }
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R3: texts already published in batches 1 to 5 of the cycle, and hashed texts, are excluded and counted separately and never tested")]
    public async Task Exclusions_AlreadyDecoded_AndHashed_AreCounted()
    {
        var log = new LineLog();
        var io = new XcInterop();
        var d = Build(io, xc: true, log: log);
        const string Hashed = "<Q1AAA> Q1BBB RR73";
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800), Msg(Hashed, 2000)));
        d.CrossCyclePriorStoreCount.Should().Be(3, "control: the hashed text passed the plausibility filter and was stored");

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(M), Msg(Other2, 2100)));   // pass 0 decodes M itself this cycle

        var line = log.LastXc;
        LineLog.Field(line, "priorsLive").Should().Be(3);
        LineLog.Field(line, "excludedDecoded").Should().Be(1, "M is already published in batch 1 of this cycle");
        LineLog.Field(line, "excludedHashed").Should().Be(1);
        LineLog.Field(line, "testedLive").Should().Be(1, "only the decoy remains");
        rows.Should().NotContain(p => p.Batch == Ft8Decoder.TemplateBatch);
    }

    // ── R9, R13: the shadow null and the sink ──────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R9: the shadow tests the opposite-parity priors (15, 45, 75 s) against this cycle's buffer, counts and logs its detections, and publishes nothing and stores nothing")]
    public async Task Shadow_CountsDetections_PublishesNothing_StoresNothing()
    {
        var log = new LineLog();
        var probe = new RecordingProbe();
        var io = new XcInterop();
        var d = Build(io, xc: true, shadow: true, log: log, probe: probe);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M)));
        int storeBefore = d.CrossCyclePriorStoreCount;

        var rows = await Cycle(d, io, At(15), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

        rows.Should().NotContain(p => p.Batch == Ft8Decoder.TemplateBatch, "a shadow detection is never published");
        var line = log.LastXc;
        LineLog.Field(line, "priorsLive").Should().Be(0, "nothing is 30, 60 or 90 s back");
        LineLog.Field(line, "priorsShadow").Should().Be(1);
        LineLog.Field(line, "testedShadow").Should().Be(1);
        LineLog.Field(line, "shadowDetected").Should().Be(1);
        LineLog.Field(line, "detected").Should().Be(0);
        d.CrossCyclePriorStoreCount.Should().Be(storeBefore + 1, "only the decoy this cycle published in batch 2; the shadow detection is not stored");
        var rec = probe.Records.Should().ContainSingle(r => r.Kind == CrossCycleKind.Shadow).Subject;
        rec.AgeCycles.Should().Be(1);
        rec.SStar.Should().BeGreaterThan(TestThreshold);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R9: with the shadow flag OFF the shadow priors are not even counted; the shadow flag does nothing while the main flag is OFF")]
    public async Task ShadowOff_AndMainOff()
    {
        var log = new LineLog();
        var probe = new RecordingProbe();
        var io = new XcInterop();
        var d = Build(io, xc: true, shadow: false, log: log, probe: probe);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M)));
        await Cycle(d, io, At(15), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));
        LineLog.Field(log.LastXc, "priorsShadow").Should().Be(0);
        LineLog.Field(log.LastXc, "testedShadow").Should().Be(0);
        probe.Records.Should().NotContain(r => r.Kind == CrossCycleKind.Shadow);

        var io2 = new XcInterop();
        var log2 = new LineLog();
        var d2 = Build(io2, xc: false, shadow: true, log: log2);
        await Cycle(d2, io2, At(0), Audio(1), null, Pass0(Msg(M)));
        await Cycle(d2, io2, At(15), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));
        d2.CrossCyclePriorStoreCount.Should().Be(0);
        log2.XcLines.Should().BeEmpty("the shadow flag has no effect without the main flag");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R13: the sink gets one numbers-only record per tested template (kind, S_E*, age, offsets, stamp), a throwing sink loses no decode, and the record type holds no text")]
    public async Task Probe_NumbersOnly_OnePerTest_AndASinkThatThrowsCostsNothing()
    {
        var probe = new RecordingProbe { Throw = true };
        var io = new XcInterop();
        var d = Build(io, xc: true, probe: probe);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800)));

        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

        rows.Should().Contain(p => p.Batch == Ft8Decoder.TemplateBatch, "the sink threw on every call and the batch still went out");
        var records = probe.Records;
        records.Should().HaveCount(2, "one per tested template");
        records.Should().OnlyContain(r => r.Kind == CrossCycleKind.Live && r.AgeCycles == 2 && r.CycleStart == At(30));
        var hit = records.Single(r => r.SStar > TestThreshold);
        hit.OffsetHz.Should().BeApproximately(0.0, 1e-9);
        hit.OffsetS.Should().BeApproximately(0.0, 1e-9);
        records.Single(r => r.SStar <= TestThreshold).SStar.Should().BeGreaterThan(0.9, "the decoy is not in the audio: noise-level S_E*");

        typeof(CrossCycleTestRecord).GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Select(p => p.PropertyType).Should().OnlyContain(t => t == typeof(double) || t == typeof(int) || t == typeof(DateTime) || t == typeof(CrossCycleKind),
                "numbers only: no string, no array, no payload (HK-037, NFR-021)");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R10: the log line carries counts and numbers only: no message text, no callsign")]
    public async Task LogLine_HasNoTextOrCallsign()
    {
        var log = new LineLog();
        var io = new XcInterop();
        var d = Build(io, xc: true, shadow: true, log: log);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800)));
        await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

        foreach (var line in log.XcLines)
        {
            line.Should().NotContain("Q1").And.NotContain("JO33").And.NotContain("FN20").And.NotContain("<");
            foreach (var name in new[] { "priorsLive", "priorsShadow", "excludedDecoded", "excludedHashed", "testedLive", "testedShadow", "detected", "shadowDetected", "abandoned", "published" })
                LineLog.Field(line, name);
            line.Should().MatchRegex(@"stageMs=\d+").And.MatchRegex(@"batch6PublishMs=-?\d+");
        }
    }

    // ── R8: the budget ─────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R8: templates stop STARTING at the cycle budget less the publish reserve: with the budget gone no template starts, all are counted abandoned and nothing is published")]
    public async Task Budget_Spent_NothingStarts_AllAbandoned()
    {
        var clock = new ManualTimeProvider();
        var log = new LineLog();
        var io = new XcInterop { Clock = clock, AdvanceInFallback = TimeSpan.FromSeconds(13) };   // the fallback "takes" the whole 13 s budget, every cycle
        var d = Build(io, xc: true, log: log, time: clock);
        await Cycle(d, io, At(0), Audio(1), null, Pass0(Msg(M), Msg(Other, 1800)));
        var rows = await Cycle(d, io, At(30), Audio(2, (M, MFreq, MDt)), null, Pass0(Msg(Other2, 2100)));

        rows.Should().NotContain(p => p.Batch == Ft8Decoder.TemplateBatch);
        var line = log.LastXc;
        LineLog.Field(line, "testedLive").Should().Be(0);
        LineLog.Field(line, "abandoned").Should().Be(2, "both templates were dropped, counted");
        LineLog.Field(line, "detected").Should().Be(0);
    }

    // ── the store, alone ───────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD R2/R3: the store keeps 6 cycles back, offers distinct texts nearest first with the NEAREST position, and a cycle start with millisecond jitter lands on the same slot")]
    public void Store_Ages_Order_NearestPosition_AndSlotJitter()
    {
        var store = new CrossCyclePriorStore();
        void Publish(int seconds, params CrossCyclePriorStore.Prior[] priors)
        {
            store.BeginCycle(At(seconds), null);
            foreach (var p in priors) store.Record(p);
        }
        static CrossCyclePriorStore.Prior P(string text, double freq, double dt, int batch) => new(text, freq, dt, batch);
        Publish(0, P("A", 1000, 0.1, 1), P("C", 1300, 0.1, 1));              // age 6 from t0 + 90
        Publish(15, P("S", 1900, 0.9, 1));                                    // age 5
        Publish(30, P("B", 1100, 0.2, 2));                                    // age 4
        Publish(60, P("A", 1002, 0.3, 4), P("B", 1101, 0.4, 4));              // age 2: A and B again, at other positions
        store.BeginCycle(At(90).AddMilliseconds(180), null);                  // framing jitter: still the 90 s slot

        var live = store.Candidates(shadow: false);
        live.Select(c => (c.Prior.Text, c.AgeCycles)).Should().Equal(("A", 2), ("B", 2), ("C", 6));
        live.Single(c => c.Prior.Text == "A").Prior.FreqHz.Should().Be(1002, "where a text has several priors the most recent one's position is used");
        live.Single(c => c.Prior.Text == "B").Prior.Dt.Should().Be(0.4);
        store.Candidates(shadow: true).Select(c => (c.Prior.Text, c.AgeCycles)).Should().Equal(("S", 5));

        store.BeginCycle(At(105), null);                                      // t0 and t0 + 15 are now 7 and 6 cycles back (a 6-cycle store drops the 7th)
        store.CountAt(7).Should().Be(0, "older than 90 s is dropped");
        store.Candidates(shadow: false).Select(c => c.Prior.Text).Should().NotContain("C", "C was published 105 s ago");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R2: the store drops a cycle that is decoded again (replaced, not doubled), ignores a record made outside an open cycle, and a clock that jumps back drops the future")]
    public void Store_Replace_AndClockJump()
    {
        var store = new CrossCyclePriorStore();
        store.Record(new("X", 1, 0, 1));
        store.TotalCount.Should().Be(0, "no cycle is open");
        store.BeginCycle(At(0), null);
        store.Record(new("A", 1000, 0, 1));
        store.BeginCycle(At(0), null);
        store.Record(new("B", 1100, 0, 1));
        store.CountAt(0).Should().Be(1, "the second pass over the same cycle replaced the first");

        store.BeginCycle(At(60), null);
        store.BeginCycle(At(-3000), null);                                    // the clock jumped back: the entries from the future are dropped
        store.TotalCount.Should().Be(0);
    }

    // ── the stage runner, alone ────────────────────────────────────────────────────────────────────────────────────

    private static CrossCycleTemplateStage.Template Tpl(string text, double freq, double dt, int age, byte[]? tones = null) => new(text, tones ?? Tones(M), freq, dt, age);

    [Fact(DisplayName = "FR-105: XC-BUILD R8: templates are tried nearest-prior-first: when the budget runs out after k starts, exactly the k nearest were tested and the older ones are the abandoned (one worker, a counting predicate, no clock)")]
    public void Run_ShortBudget_DropsTheOldest()
    {
        var pcm = Audio(7);
        var templates = new[] { Tpl("n2", 1000, 0.3, 2), Tpl("n4", 1100, 0.3, 4), Tpl("n6", 1200, 0.3, 6), Tpl("n6b", 1300, 0.3, 6) };
        int polls = 0;

        var r = CrossCycleTemplateStage.Run(templates, pcm, double.PositiveInfinity, workers: 1, () => ++polls > 2, CancellationToken.None);

        r.Tested.Should().Be(2);
        r.Abandoned.Should().Be(2);
        r.Outcomes.Select(o => o.Tested).Should().Equal(new[] { true, true, false, false }, "the nearest two ran; the oldest priors were dropped");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R8: the parallel run gives exactly the single-worker run's outcomes (templates are independent: no shared state between workers)")]
    public void Run_Parallel_EqualsSingleWorker()
    {
        var pcm = Audio(8, (M, 1500, 0.3));
        var templates = Enumerable.Range(0, 12).Select(i => Tpl("t" + i, 1480 + i * 3, 0.28 + 0.01 * (i % 4), 2 + 2 * (i % 3))).ToList();

        var one = CrossCycleTemplateStage.Run(templates, pcm, 4.0, 1, () => false, CancellationToken.None);
        var four = CrossCycleTemplateStage.Run(templates, pcm, 4.0, 4, () => false, CancellationToken.None);

        four.Outcomes.Should().Equal(one.Outcomes);
        one.Tested.Should().Be(12);
        one.Detected.Should().BeGreaterThan(0, "control: some of these are within the window of the message at 1500 Hz");
        one.Detected.Should().BeLessThan(12, "control: and some are not");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R6: detected means S_E* >= T_E exactly: T_E equal to the score detects, a hair above does not, +infinity detects nothing")]
    public void Run_Threshold_IsInclusive_AndInfinityDetectsNothing()
    {
        var pcm = Audio(9, (M, 1500, 0.3));
        var tpl = new[] { Tpl("t", 1500, 0.3, 2) };
        double s = CrossCycleTemplateStage.Run(tpl, pcm, double.PositiveInfinity, 1, () => false, CancellationToken.None).Outcomes[0].SStar;

        CrossCycleTemplateStage.Run(tpl, pcm, s, 1, () => false, CancellationToken.None).Detected.Should().Be(1);
        CrossCycleTemplateStage.Run(tpl, pcm, Math.BitIncrement(s), 1, () => false, CancellationToken.None).Detected.Should().Be(0);
        CrossCycleTemplateStage.Run(tpl, pcm, double.PositiveInfinity, 1, () => false, CancellationToken.None).Detected.Should().Be(0);
        s.Should().BeGreaterThan(7.0);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R3: BuildTemplates excludes and counts separately: already decoded, hashed, and refused by the encoder (a throw, or a wrong tone count); order is kept")]
    public void BuildTemplates_Exclusions_AreCounted_OrderKept()
    {
        var candidates = new[]
        {
            "Q1AAA Q1BBB JO33", "Q1CCC Q1DDD JO33", "<Q1EEE> Q1FFF RR73", "BAD ONE", "SHORT", "Q1GGG Q1HHH JO33",
        }.Select((t, i) => new CrossCyclePriorStore.Candidate(new CrossCyclePriorStore.Prior(t, 1000 + i, 0.1 * i, 1), 2)).ToList();
        byte[] Encode(string t) => t switch
        {
            "BAD ONE" => throw new InvalidOperationException("refused"),
            "SHORT" => new byte[10],
            _ => new byte[79],
        };

        var built = CrossCycleTemplateStage.BuildTemplates(candidates, new HashSet<string> { "Q1CCC Q1DDD JO33" }, Encode, out var ex);

        built.Select(t => t.Text).Should().Equal("Q1AAA Q1BBB JO33", "Q1GGG Q1HHH JO33");
        ex.AlreadyDecoded.Should().Be(1);
        ex.Hashed.Should().Be(1);
        ex.Refused.Should().Be(2);
    }
}
