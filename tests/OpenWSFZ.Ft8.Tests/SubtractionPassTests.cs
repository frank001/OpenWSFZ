using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for <see cref="SubtractionPass"/> (sub-feas-native-subtraction, tasks.md 2.4/2.5).
///
/// <para>
/// <see cref="FakeInterop"/> uses the REAL native <see cref="Ft8LibInterop.EncodeMessage"/>
/// for tone encoding (already-tested, unrelated to what this change adds) but fakes
/// <see cref="IFt8NativeInterop.SubfeasComputeAnalytic"/>, <see cref="IFt8NativeInterop.SubfeasFitSignal"/>
/// and <see cref="IFt8NativeInterop.DecodeAll"/> — the actual new/expensive native calls this
/// orchestrator drives — so these tests exercise <see cref="SubtractionPass"/>'s own control
/// flow (which signals get fit, how failures propagate, the payload dedup decision) without
/// depending on a real fit or a real residual decode.
/// </para>
/// </summary>
public sealed class SubtractionPassTests
{
    private const int PcmLength = 180_000;

    [Fact(DisplayName = "No re-encodable pass-0 signals: returns empty without calling ComputeAnalytic/DecodeAll")]
    public async Task NoReencodableSignals_ReturnsEmpty_SkipsNativeCalls()
    {
        var pass0 = new[] { MakeResult("<...> Q1XYZ RR73"), MakeResult("CQ") };
        var interop = new FakeInterop();

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().BeEmpty();
        interop.ComputeAnalyticCalled.Should().BeFalse("no signal was re-encodable, so no fit work should be attempted");
        interop.DecodeAllCalled.Should().BeFalse();
    }

    [Fact(DisplayName = "Residual decode finds nothing new: returns empty")]
    public async Task ResidualDecodeFindsNothing_ReturnsEmpty()
    {
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ JO33") };
        var interop = new FakeInterop { ResidualDecodeResults = [] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().BeEmpty();
        interop.FitSignalCallCount.Should().Be(1, "exactly one pass-0 signal was re-encodable");
    }

    [Fact(DisplayName = "Residual decode re-finds the same QSO it was subtracted from: filtered out, not reported as new")]
    public async Task ResidualDecodeRefindsSameSignal_IsFiltered()
    {
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ JO33") };
        var interop = new FakeInterop { ResidualDecodeResults = [MakeResult("Q1ABC Q1XYZ JO33")] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().BeEmpty("a re-decoded ghost of the same QSO already in pass-0 is not new information");
    }

    [Fact(DisplayName = "Residual decode finds a genuinely different QSO: reported as new")]
    public async Task ResidualDecodeFindsDifferentQso_IsReportedAsNew()
    {
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ JO33") };
        var newDecode = MakeResult("Q1DEF Q1UVW EN37");
        var interop = new FakeInterop { ResidualDecodeResults = [newDecode] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().ContainSingle();
        result[0].Message.TrimEnd().Should().Be("Q1DEF Q1UVW EN37");
    }

    [Fact(DisplayName = "Residual decode re-finds the RR73 QSO with the on-air sentinel: filtered out (the asymmetry this pass exists for)")]
    public async Task ResidualDecodeRefindsRr73WithOnAirRendering_IsFiltered()
    {
        // Both our own re-encoded RR73 and a genuine on-air RR73 decode RENDER as the same
        // text ("...RR73", board 2026-09-27 interop-rendering verification) -- this test
        // exercises the payload-level path via the SAME text, which is the common case; the
        // bit-level asymmetry itself is covered directly in SubfeasPayloadTests.
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ RR73") };
        var interop = new FakeInterop { ResidualDecodeResults = [MakeResult("Q1ABC Q1XYZ RR73")] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().BeEmpty();
    }

    [Fact(DisplayName = "Access violation during a per-signal fit abandons the WHOLE residual pass (Decision 4 contract)")]
    public async Task AccessViolationDuringFit_AbandonsWholeCycle()
    {
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ JO33"), MakeResult("Q1DEF Q1UVW EN37") };
        var interop = new FakeInterop
        {
            FitSignalThrowsAvForTones = tones => true, // every fit call throws
            ResidualDecodeResults = [MakeResult("Q1GHI Q1JKL FN20")], // would be "new" if reached
        };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().BeEmpty("an AV on any one signal's fit must abandon the whole residual pass, not just that signal");
        interop.DecodeAllCalled.Should().BeFalse("the residual decode must never be reached after an AV during fitting");
    }

    [Fact(DisplayName = "Access violation during the residual decode itself: treated as no new decodes")]
    public async Task AccessViolationDuringResidualDecode_ReturnsEmpty()
    {
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ JO33") };
        var interop = new FakeInterop { ResidualDecodeThrowsAv = true };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().BeEmpty();
    }

    [Fact(DisplayName = "A -3 (off-edge) fit contributes nothing and does not abort the cycle")]
    public async Task OffEdgeFit_DoesNotAbortCycle_OtherSignalsStillProcessed()
    {
        var pass0 = new[] { MakeResult("Q1ABC Q1XYZ JO33"), MakeResult("Q1DEF Q1UVW EN37") };
        var interop = new FakeInterop
        {
            FitSignalReturnCode = -3, // every fit "runs off the buffer edge" -- a normal outcome
            ResidualDecodeResults = [MakeResult("Q1GHI Q1JKL FN20")],
        };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 2, logger: null);

        result.Should().ContainSingle("a -3 fit result is a normal per-signal outcome, not a cycle-wide failure");
        interop.DecodeAllCalled.Should().BeTrue();
    }

    [Fact(DisplayName = "Wrong-length PCM buffer throws ArgumentException")]
    public async Task WrongLengthPcm_Throws()
    {
        var interop = new FakeInterop();
        var act = () => SubtractionPass.RunAsync(interop, new float[100], [], maxDegreeOfParallelism: 2, logger: null);
        await act.Should().ThrowAsync<ArgumentException>();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static Ft8NativeResult MakeResult(string message, int freqHz = 1500, float dt = 0.2f, int snr = -10)
        => new() { FreqHz = freqHz, Dt = dt, Snr = snr, Message = message };

    /// <summary>
    /// Fakes only the native calls <see cref="SubtractionPass"/> itself drives
    /// (ComputeAnalytic/FitSignal/DecodeAll); EncodeMessage delegates to the real native
    /// encoder (already-tested, unrelated to this change) so payload comparisons behave
    /// exactly as they would in production.
    /// </summary>
    private sealed class FakeInterop : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public bool ComputeAnalyticCalled { get; private set; }
        public bool DecodeAllCalled { get; private set; }
        public int FitSignalCallCount { get; private set; }

        public Ft8NativeResult[] ResidualDecodeResults { get; init; } = [];
        public bool ResidualDecodeThrowsAv { get; init; }
        public Func<byte[], bool>? FitSignalThrowsAvForTones { get; init; }
        public int FitSignalReturnCode { get; init; } = 0;

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
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz)
        {
            Interlocked.Increment(ref _fitCallCount);
            FitSignalCallCount = _fitCallCount;
            if (FitSignalThrowsAvForTones?.Invoke(tones) == true)
                throw new NativeAccessViolationException();
            return (FitSignalReturnCode, new float[PcmLength]);
        }
        private int _fitCallCount;

        public Ft8NativeResult[] DecodeAll(float[] pcm)
        {
            DecodeAllCalled = true;
            if (ResidualDecodeThrowsAv) throw new NativeAccessViolationException();
            return ResidualDecodeResults;
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
