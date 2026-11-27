using System.Collections.Concurrent;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// XC-ROUND (FR-108), the managed side in <c>DecodeLeanAsync</c>, against a scripted lean interop (the seam is the interop's <c>DecodeLeanXcRound</c>; the cross-cycle template
/// stage runs for real on synthetic audio, as in <c>LeanEngineBatchesTests</c>): the round is NOT called with the stage off, with no batch-3 detection, with no residual, or
/// on Fast; with a detection it is called ONCE with exactly the published batch-3 detections (frequency, dt, the 79 tones of the template) and the cycle's own buffers, its
/// results are published as batch 4 AFTER batch 3 and only when non-empty, a text already published earlier in the cycle is not published again, they are stored as priors like
/// batch 2, and a failure of the round costs the cycle only its batch 4. Synthetic Q-prefix content only (NFR-021). No delay anywhere (TESTING_STRATEGY section 11).
/// </summary>
public sealed class LeanEngineXcRoundManagedTests
{
    private static readonly DateTime T0 = new(2026, 11, 27, 12, 0, 0, DateTimeKind.Utc);
    private static DateTime At(int seconds) => T0.AddSeconds(seconds);

    private const string M = "Q1ABC Q1XYZ JO33";            // the message that repeats: the cross-cycle detection
    private const string Other = "Q1GHI Q1JKL FN20";
    private const string Other2 = "Q1MNO Q1PQR IO91";
    private const string Fresh = "Q1AAA Q1BBB RR73";         // what the extra round finds
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

    private sealed record XcCall(float[] Pcm, LeanCycleParams Request, float[] Residual, IReadOnlyList<LeanXcDetection> Detections);

    /// <summary>A scripted lean interop: the cycle's results per call, and what the extra round returns (or throws). Every classic member throws.</summary>
    private sealed class ScriptedLean : IFt8NativeInterop
    {
        private readonly Queue<(Ft8NativeResult[] Round0, Ft8NativeResult[] Later, bool Residual)> _cycles = new();
        public List<LeanCycleParams> Requests { get; } = [];
        public List<XcCall> XcCalls { get; } = [];
        public Ft8NativeResult[] XcResults { get; set; } = [];
        public Exception? XcThrows { get; set; }
        public void Enqueue(Ft8NativeResult[] round0, Ft8NativeResult[] later, bool residual = true) => _cycles.Enqueue((round0, later, residual));

        public LeanCycleOutcome DecodeLeanCycle(float[] pcm, LeanCycleParams request, Action<LeanRound0>? onRound0)
        {
            Requests.Add(request);
            var s = _cycles.Dequeue();
            var results = s.Round0.Concat(s.Later).ToArray();
            var rounds = s.Round0.Select(_ => (byte)0).Concat(s.Later.Select(_ => (byte)1)).ToArray();
            onRound0?.Invoke(new LeanRound0(s.Round0, s.Round0.Select(_ => LeanTier.A).ToArray()));
            return new LeanCycleOutcome(results, LeanCycleStats.None()) { Tiers = results.Select(_ => LeanTier.A).ToArray(), Rounds = rounds, Residual = s.Residual && request.WantResidual ? (float[])pcm.Clone() : null };
        }

        public LeanCycleOutcome DecodeLeanXcRound(float[] pcm, LeanCycleParams request, float[] residual, IReadOnlyList<LeanXcDetection> detections)
        {
            XcCalls.Add(new XcCall(pcm, request, residual, detections));
            if (XcThrows is not null) throw XcThrows;
            return new LeanCycleOutcome(XcResults, LeanCycleStats.None())
            {
                Tiers = XcResults.Select(_ => LeanTier.A).ToArray(),
                Rounds = XcResults.Select(_ => (byte)LeanProbe.XcRound).ToArray(),
            };
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
        public string LastLean => Lines.Last(l => l.Contains("lean:"));
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter) => _q.Enqueue(formatter(state, exception));
        public static int Field(string text, string name)
        {
            var m = Regex.Match(text, name + @"=(-?\d+)");
            m.Success.Should().BeTrue($"the text has {name}=: {text}");
            return int.Parse(m.Groups[1].Value);
        }
    }

    private sealed record Published(int Batch, string Message, int FreqHz, double Dt);

    private static Ft8Decoder Build(ScriptedLean io, bool xc = true, ILogger<Ft8Decoder>? log = null, DecoderEffort effort = DecoderEffort.Normal)
    {
        var d = new Ft8Decoder(new FakeClock(T0), log, interop: io);
        d.SetEngine(DecoderEngine.Lean);
        d.SetCrossCyclePrior(xc);
        d.SetCrossCyclePriorThreshold(TestThreshold);
        d.SetEffort(effort);
        return d;
    }

    private static async Task<List<Published>> Cycle(Ft8Decoder d, DateTime start, float[] audio)
    {
        var got = new List<Published>();
        await d.DecodeStagedAsync(audio, start, null, (n, b) =>
        {
            got.AddRange(b.Select(r => new Published(n, r.Message, r.FreqHz, r.Dt)));
            return Task.CompletedTask;
        });
        return got;
    }

    /// <summary>Cycle 1 publishes M (so it is a prior); cycle 2, 30 s later, has M's signal in its audio, so the stage detects it as batch 3. Returns cycle 2's rows.</summary>
    private static async Task<List<Published>> TwoCycles(ScriptedLean io, Ft8Decoder d, Ft8NativeResult[]? cycle2Round0 = null, bool cycle2HasM = true, bool residual = true)
    {
        io.Enqueue([Msg(M), Msg(Other, 1800)], []);
        await Cycle(d, At(0), Audio(1));
        io.Enqueue(cycle2Round0 ?? [Msg(Other2, 2100)], [], residual);
        return await Cycle(d, At(30), cycle2HasM ? Audio(2, (M, MFreq, MDt)) : Audio(2));
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (c): with the cross-cycle stage off the round is not called")]
    public async Task StageOff_NoRound()
    {
        var io = new ScriptedLean { XcResults = [Msg(Fresh, 1900)] };
        var d = Build(io, xc: false);
        var rows = await TwoCycles(io, d);
        io.XcCalls.Should().BeEmpty();
        rows.Select(r => r.Batch).Should().Equal(1);
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (c): with no batch-3 detection the round is not called and the lean line has no b4")]
    public async Task NoDetection_NoRound()
    {
        var log = new LineLog();
        var io = new ScriptedLean { XcResults = [Msg(Fresh, 1900)] };
        var d = Build(io, log: log);
        var rows = await TwoCycles(io, d, cycle2HasM: false);
        io.XcCalls.Should().BeEmpty();
        rows.Select(r => r.Batch).Should().Equal(1);
        log.LastLean.Should().NotContain("b4=").And.NotContain("xcRound");
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (c): on Fast, and with no residual, the round is not called even with a batch-3 detection")]
    public async Task Fast_AndNoResidual_NoRound()
    {
        var io = new ScriptedLean { XcResults = [Msg(Fresh, 1900)] };
        var fast = await TwoCycles(io, Build(io, effort: DecoderEffort.Fast));
        io.XcCalls.Should().BeEmpty("Fast");
        fast.Should().Contain(r => r.Batch == Ft8Decoder.LeanBatchXc, "control: the stage did detect M, so only the effort kept the round away");

        var io2 = new ScriptedLean { XcResults = [Msg(Fresh, 1900)] };
        var noResidual = await TwoCycles(io2, Build(io2), residual: false);
        io2.XcCalls.Should().BeEmpty("no residual");
        noResidual.Select(r => r.Batch).Should().Equal(1);
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (c): with a detection the round is called once with the published detections and the cycle's buffers; batch 4 follows batch 3, repeats of earlier texts are dropped, and the decodes are stored as priors like batch 2")]
    public async Task Detection_CallsTheRoundOnce_AndPublishesBatch4AfterBatch3()
    {
        var log = new LineLog();
        var io = new ScriptedLean { XcResults = [Msg(Other2, 2100), Msg(Fresh, 1900), Msg(M, 1503)] };   // Other2: batch 1; M: batch 3; only Fresh is new
        var d = Build(io, log: log);
        io.Enqueue([Msg(M), Msg(Other, 1800)], []);
        await Cycle(d, At(0), Audio(1));
        io.Enqueue([Msg(Other2, 2100)], []);
        var rows = new List<Published>();
        await d.DecodeStagedAsync(Audio(2, (M, MFreq, MDt)), At(30), null, (n, b) => { rows.AddRange(b.Select(r => new Published(n, r.Message, r.FreqHz, r.Dt))); return Task.CompletedTask; });

        // batch 4 comes after batch 3 and carries only the text not published earlier in the cycle
        rows.Select(r => (r.Batch, r.Message)).Should().Equal([(1, Other2), (Ft8Decoder.LeanBatchXc, M), (Ft8Decoder.LeanBatchXcRound, Fresh)]);

        io.XcCalls.Should().ContainSingle();
        var call = io.XcCalls[0];
        call.Detections.Should().ContainSingle();
        call.Detections[0].FreqHz.Should().Be(MFreq);
        call.Detections[0].Dt.Should().BeApproximately(MDt, 0.1f);
        call.Detections[0].Tones.Should().Equal(Tones(M), "the template's own 79 tones");
        call.Residual.Should().HaveCount(180_000);
        call.Pcm.Should().HaveCount(180_000);
        call.Request.WantResidual.Should().BeFalse();
        call.Request.BudgetMs.Should().NotBeNull();
        call.Request.NoTierB.Should().BeFalse();

        d.CrossCyclePriorStoreCount.Should().Be(4, "cycle 1: M and Other; cycle 2: Other2 (batch 1) and Fresh (batch 4, like batch 2); the batch-3 M is never stored");
        var line = log.LastLean;
        line.Should().Contain("b1=1 b2=0 b3=1").And.Contain("xc=ran xcDetected=1").And.Contain("b4=1").And.Contain("xcRound[detections=1");
        LineLog.Field(line.Substring(line.IndexOf("xcRound[", StringComparison.Ordinal)), "decodes").Should().Be(1);
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (c): a round that finds nothing publishes no batch 4 (b4=0); a round that throws costs the cycle only its batch 4")]
    public async Task EmptyAndFailedRounds_PublishNoBatch4()
    {
        var log = new LineLog();
        var io = new ScriptedLean { XcResults = [] };
        var rows = await TwoCycles(io, Build(io, log: log));
        io.XcCalls.Should().ContainSingle();
        rows.Select(r => r.Batch).Should().Equal(1, Ft8Decoder.LeanBatchXc);
        log.LastLean.Should().Contain("b4=0").And.Contain("xcRound[detections=1");

        var io2 = new ScriptedLean { XcThrows = new InvalidOperationException("the round failed (test double)") };
        var rows2 = await TwoCycles(io2, Build(io2));
        io2.XcCalls.Should().ContainSingle();
        rows2.Select(r => r.Batch).Should().Equal(new[] { 1, Ft8Decoder.LeanBatchXc }, "batches 1 and 3 are out; the failed round is only a lost batch 4");
    }
}
