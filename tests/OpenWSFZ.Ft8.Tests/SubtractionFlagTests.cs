using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the sub-feas-native-subtraction config flag wiring in
/// <see cref="Ft8Decoder.SetSubtractionEnabled"/> / <see cref="Ft8Decoder.DecodeAsync(float[],CancellationToken)"/>
/// (design.md Decision 6, tasks.md 5.2/6.1/6.2).
///
/// <para>
/// Uses the REAL native <see cref="Ft8LibInterop.EncodeMessage"/> (via
/// <see cref="SequencedInterop"/>'s own delegation) so payload-level dedup inside
/// <see cref="OpenWSFZ.Ft8.Subfeas.SubtractionPass"/> behaves exactly as it would in
/// production; only <c>DecodeAll</c>/<c>SubfeasComputeAnalytic</c>/<c>SubfeasFitSignal</c>
/// are faked.
/// </para>
/// </summary>
public sealed class SubtractionFlagTests
{
    [Fact(DisplayName = "6.1: Flag OFF (default) — SubfeasComputeAnalytic is never called, decode output unaffected")]
    public async Task FlagOff_Default_NeverCallsSubfeasComputeAnalytic()
    {
        var interop = new SequencedInterop(
            pass0: [MakeResult("Q1ABC Q1XYZ JO33")],
            residual: [MakeResult("Q1DEF Q1UVW EN37")]); // would be "new" if the pass ran
        var decoder = BuildDecoder(interop); // flag never set -- defaults to false

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().ContainSingle().Which.Message.Should().Be("Q1ABC Q1XYZ JO33");
        interop.ComputeAnalyticCalled.Should().BeFalse(
            "with the flag off, decode output must be byte-identical to pre-change behaviour — " +
            "no subtraction-path native call may be made at all");
        interop.DecodeAllCallCount.Should().Be(1, "only pass-0's own DecodeAll call, no residual pass");
    }

    [Fact(DisplayName = "6.2: Flag ON — takes effect on the next cycle, no rebuild, and a genuinely new residual decode is appended")]
    public async Task FlagOn_NextCycle_AppendsGenuinelyNewResidualDecode()
    {
        var interop = new SequencedInterop(
            pass0: [MakeResult("Q1ABC Q1XYZ JO33")],
            residual: [MakeResult("Q1DEF Q1UVW EN37")]);
        var decoder = BuildDecoder(interop);
        decoder.SetSubtractionEnabled(true);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Select(r => r.Message).Should().BeEquivalentTo(["Q1ABC Q1XYZ JO33", "Q1DEF Q1UVW EN37"]);
        interop.ComputeAnalyticCalled.Should().BeTrue();
        interop.DecodeAllCallCount.Should().Be(2, "pass-0's call plus the residual-pass call");
    }

    [Fact(DisplayName = "Flag ON — a residual decode that's the same QSO as pass-0 is not duplicated")]
    public async Task FlagOn_ResidualRefindsSameQso_NotDuplicated()
    {
        var interop = new SequencedInterop(
            pass0: [MakeResult("Q1ABC Q1XYZ JO33")],
            residual: [MakeResult("Q1ABC Q1XYZ JO33")]); // same QSO re-decoded from the residual
        var decoder = BuildDecoder(interop);
        decoder.SetSubtractionEnabled(true);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().ContainSingle(
            "a re-decoded ghost of the same QSO already in pass-0 must not be reported twice");
    }

    [Fact(DisplayName = "Flag ON — an access violation during the per-signal fit still returns pass-0's own results (not empty)")]
    public async Task FlagOn_AccessViolationDuringFit_StillReturnsPass0Results()
    {
        var interop = new SequencedInterop(
            pass0: [MakeResult("Q1ABC Q1XYZ JO33")],
            residual: [MakeResult("Q1DEF Q1UVW EN37")])
        {
            FitSignalThrows = true,
        };
        var decoder = BuildDecoder(interop);
        decoder.SetSubtractionEnabled(true);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().ContainSingle().Which.Message.Should().Be("Q1ABC Q1XYZ JO33");
        interop.DecodeAllCallCount.Should().Be(1,
            "an AV during fitting must abandon the whole residual pass BEFORE the residual decode call is reached");
    }

    [Fact(DisplayName = "Flag ON with no pass-0 decodes — subtraction path is skipped entirely")]
    public async Task FlagOn_NoPass0Decodes_SkipsSubtractionPath()
    {
        var interop = new SequencedInterop(pass0: [], residual: [MakeResult("Q1DEF Q1UVW EN37")]);
        var decoder = BuildDecoder(interop);
        decoder.SetSubtractionEnabled(true);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().BeEmpty();
        interop.ComputeAnalyticCalled.Should().BeFalse("nothing to fit when pass-0 found no decodes");
        interop.DecodeAllCallCount.Should().Be(1);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static Ft8NativeResult MakeResult(string message, int freqHz = 1500, float dt = 0.2f, int snr = -10)
        => new() { FreqHz = freqHz, Dt = dt, Snr = snr, Message = message };

    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++) pcm[i] = 0.1f;
        return pcm;
    }

    private static Ft8Decoder BuildDecoder(IFt8NativeInterop interop)
        => new(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), logger: null, interop: interop);

    /// <summary>
    /// Fake that returns <paramref name="pass0"/> from the FIRST <c>DecodeAll</c> call and
    /// <paramref name="residual"/> from the second (the residual-pass call) — so a single
    /// fake can drive a full <see cref="Ft8Decoder.DecodeAsync(float[],CancellationToken)"/>
    /// round trip through both passes. EncodeMessage delegates to the real native encoder.
    /// </summary>
    internal sealed class SequencedInterop(Ft8NativeResult[] pass0, Ft8NativeResult[] residual) : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;
        public bool ComputeAnalyticCalled { get; private set; }
        public int DecodeAllCallCount { get; private set; }
        public bool FitSignalThrows { get; init; }

        /// <summary>Sleeps this long inside every fit (a slow residual pass), for the two-stage tests.</summary>
        public int FitDelayMs { get; init; }

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            DecodeAllCallCount++;
            return DecodeAllCallCount == 1 ? pass0 : residual;
        }

        public byte[] EncodeMessage(string message)
        {
            var tones = new byte[79];
            Ft8LibInterop.EncodeMessage(message, tones);
            return tones;
        }

        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        {
            ComputeAnalyticCalled = true;
            return (new float[pcm.Length], new float[pcm.Length]);
        }

        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        {
            if (FitSignalThrows) throw new NativeAccessViolationException();
            if (FitDelayMs > 0) Thread.Sleep(FitDelayMs);
            return (0, new float[180_000]);
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
}
