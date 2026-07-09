using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// End-to-end tests verifying <see cref="Ft8Decoder"/> attaches <see cref="DecodeResult.WorkedBefore"/>
/// (<c>qso-confirmation</c> capability, task 2.6) — mirrors <see cref="RegionLookupTests"/>'s
/// structure for the analogous <c>Region</c> bycatch.
///
/// <para>
/// Worked-before resolution is advisory only: an index failure or a missing index must never
/// withhold or alter the underlying decode — only degrade <see cref="DecodeResult.WorkedBefore"/>
/// to <c>null</c> (every checkbox unchecked).
/// </para>
/// </summary>
public sealed class WorkedBeforeLookupTests
{
    private sealed class FixedResultInterop(params Ft8NativeResult[] results) : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => results;

        public int[] GetLastPassCounts(int maxPasses)      => [results.Length, 0];
        public int[] GetLastCandidateCounts(int maxPasses) => [results.Length, 0];
        public float GetLastNoiseFloorDb()                  => -70.0f;
        public int   GetHashTableRejectCount()              => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
    }

    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++) pcm[i] = 0.1f;
        return pcm;
    }

    [Fact(DisplayName = "2.6: DecodeAsync attaches a resolved WorkedBefore to the decode payload")]
    public async Task DecodeAsync_MatchingDecode_AttachesWorkedBeforeToPayload()
    {
        var index = new FixedWorkedBeforeIndex(new WorkedBeforeInfo(
            Contact: WorkedBeforeState.ThisBand,
            Country: WorkedBeforeState.ThisBand,
            Continent: WorkedBeforeState.ThisBand,
            CqZone: WorkedBeforeState.ThisBand,
            ItuZone: WorkedBeforeState.ThisBand));
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            workedBeforeIndex: index);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1);
        results[0].WorkedBefore.Should().NotBeNull();
        results[0].WorkedBefore!.Contact.Should().Be(WorkedBeforeState.ThisBand);
        results[0].WorkedBefore!.Country.Should().Be(WorkedBeforeState.ThisBand);
        results[0].WorkedBefore!.Continent.Should().Be(WorkedBeforeState.ThisBand);
        results[0].WorkedBefore!.CqZone.Should().Be(WorkedBeforeState.ThisBand);
        results[0].WorkedBefore!.ItuZone.Should().Be(WorkedBeforeState.ThisBand);
    }

    [Fact(DisplayName = "2.6: DecodeAsync degrades WorkedBefore to null when the index throws, without affecting acceptance")]
    public async Task DecodeAsync_IndexThrows_DegradesToNullWorkedBefore_StillAccepted()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            workedBeforeIndex: new ThrowingWorkedBeforeIndex());

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1, "a worked-before resolution exception must never withhold the decode");
        results[0].WorkedBefore.Should().BeNull(
            "a worked-before resolution exception must degrade to null (every checkbox unchecked), not propagate");
    }

    [Fact(DisplayName = "4.2: DecodeAsync threads currentBand through to IWorkedBeforeIndex.Resolve")]
    public async Task DecodeAsync_CurrentBandSupplied_ThreadedToResolve()
    {
        var index = new CapturingWorkedBeforeIndex();
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            workedBeforeIndex: index);

        await decoder.DecodeAsync(BuildLoudPcm(), new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc), "20m");

        index.ResolvedBands.Should().ContainSingle().Which.Should().Be("20m");
    }

    [Fact(DisplayName = "DecodeAsync attaches currentBand to DecodeResult.Band verbatim (decode-table Band column)")]
    public async Task DecodeAsync_CurrentBandSupplied_AttachesToDecodeResultBand()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default);

        var results = await decoder.DecodeAsync(
            BuildLoudPcm(), new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc), "20m");

        results.Should().HaveCount(1);
        results[0].Band.Should().Be("20m",
            "the decode-table Band column must show exactly the current band used for worked-before resolution");
    }

    [Fact(DisplayName = "DecodeAsync leaves DecodeResult.Band null when currentBand is unresolvable")]
    public async Task DecodeAsync_CurrentBandNull_DecodeResultBandNull()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1);
        results[0].Band.Should().BeNull("pre-existing call sites that don't pass currentBand must render an empty Band cell");
    }

    [Fact(DisplayName = "4.4: the 3-arg (pcm, cycleStart, ct) overload still compiles and resolves currentBand: null")]
    public async Task DecodeAsync_ThreeArgOverload_ResolvesNullBand()
    {
        var index = new CapturingWorkedBeforeIndex();
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            workedBeforeIndex: index);

        await decoder.DecodeAsync(BuildLoudPcm(), new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc), CancellationToken.None);

        index.ResolvedBands.Should().ContainSingle().Which.Should().BeNull(
            "pre-existing call sites that don't pass currentBand must keep degrading to null, never throw or change shape");
    }

    [Fact(DisplayName = "2.6: DecodeAsync leaves WorkedBefore null when no index is supplied")]
    public async Task DecodeAsync_NoIndexSupplied_WorkedBeforeStaysNull()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1);
        results[0].WorkedBefore.Should().BeNull(
            "callers that do not wire up a worked-before index keep today's behaviour (WorkedBefore always null)");
    }
}
