using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit and integration tests for the advisory callsign region lookup
/// (<c>f-002-callsign-structure-region-lookup</c>, <c>region-lookup</c> capability) — resolved
/// server-side and attached to <see cref="DecodeResult.Region"/> (design.md Decision 4).
///
/// <para>
/// Region resolution is advisory only: a lookup miss, a missing/malformed region file, or a
/// resolution exception must never withhold or alter the underlying decode — only degrade
/// <see cref="DecodeResult.Region"/> to <c>null</c> ("Unknown").
/// </para>
/// </summary>
public sealed class RegionLookupTests
{
    // ── ExtractPrimaryCallsignToken ────────────────────────────────────────────

    [Theory(DisplayName = "f-002 3.1: ExtractPrimaryCallsignToken finds the CQ caller's own callsign")]
    [InlineData("CQ Q1ABC FN42",    "Q1ABC", "standard 3-token CQ")]
    [InlineData("CQ DX Q1AW FN42",  "Q1AW",  "4-token CQ with modifier")]
    [InlineData("CQ Q1ABC",         "Q1ABC", "2-token CQ, no grid")]
    public void ExtractPrimaryCallsignToken_CqMessages_ReturnsCallerCallsign(string text, string expected, string reason)
        => Ft8Decoder.ExtractPrimaryCallsignToken(text).Should().Be(expected,
               $"'{text}' should resolve to the CQ caller's callsign ({reason})");

    [Theory(DisplayName = "f-002 3.1: ExtractPrimaryCallsignToken finds the sender ('from') token in Standard QSO messages")]
    [InlineData("Q1AW Q1ABC -10",      "Q1ABC", "3-token Standard QSO — token 1 is the sender")]
    [InlineData("Q1AW Q1ABC RR73",     "Q1ABC", "terminal RR73 form")]
    [InlineData("<...> Q9XYZ RR73",    "Q9XYZ", "hash addressee — sender token 1 still resolved")]
    [InlineData("Q1ABC <...>",         "Q1ABC", "hash sender position — falls back to token 0")]
    public void ExtractPrimaryCallsignToken_StandardQso_ReturnsSenderCallsign(string text, string expected, string reason)
        => Ft8Decoder.ExtractPrimaryCallsignToken(text).Should().Be(expected,
               $"'{text}' should resolve to the sender/caller-identification token ({reason})");

    [Theory(DisplayName = "f-002 3.1: ExtractPrimaryCallsignToken strips a portable suffix before returning the token")]
    [InlineData("CQ Q1ABC/P FN42",     "Q1ABC")]
    [InlineData("Q1AW Q1ABC/QRP -10",  "Q1ABC")]
    public void ExtractPrimaryCallsignToken_PortableSuffix_ReturnsBaseCallsign(string text, string expected)
        => Ft8Decoder.ExtractPrimaryCallsignToken(text).Should().Be(expected,
               $"'{text}' should resolve to the base callsign, portable suffix stripped");

    // ── CallsignRegionStore-equivalent lookup semantics (via the fixed test double) ──

    [Fact(DisplayName = "f-002: recognised prefix resolves continent and entity")]
    public void TryGetRegion_RecognisedPrefix_ResolvesContinentAndEntity()
    {
        var store = new FixedCallsignRegionStore([
            new CallsignRegionEntry("3A", "3A", "Monaco", "EU", null, null),
        ]);

        var region = store.TryGetRegion("3A2XYZ");

        region.Should().NotBeNull();
        region!.Continent.Should().Be("EU");
        region.Entity.Should().Be("Monaco");
        region.Synthetic.Should().BeFalse();
    }

    [Fact(DisplayName = "f-002 5.4: unmatched prefix resolves to null (Unknown)")]
    public void TryGetRegion_UnmatchedPrefix_ReturnsNull()
    {
        var store = new FixedCallsignRegionStore([
            new CallsignRegionEntry("3A", "3A", "Monaco", "EU", null, null),
        ]);

        store.TryGetRegion("ZZ1XYZ").Should().BeNull(
            "an unmatched prefix must resolve to null (rendered as \"Unknown\" by the frontend)");
    }

    [Fact(DisplayName = "f-002: synthetic Q-prefix callsign resolves to the distinct synthetic region")]
    public void TryGetRegion_SyntheticQPrefix_ResolvesSyntheticRegion()
    {
        var store = new FixedCallsignRegionStore([
            new CallsignRegionEntry("Q", "Q", "Synthetic (R&R Study)", null, null, null, Synthetic: true),
        ]);

        var region = store.TryGetRegion("Q1ABC");

        region.Should().NotBeNull();
        region!.Synthetic.Should().BeTrue();
        region.Entity.Should().Be("Synthetic (R&R Study)");
        region.Continent.Should().BeNull();
    }

    // ── End-to-end: DecodeAsync attaches Region to the decode payload ─────────

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

    [Fact(DisplayName = "f-002 3.2: DecodeAsync attaches a resolved region to the decode payload")]
    public async Task DecodeAsync_RecognisedCallsign_AttachesRegionToPayload()
    {
        var regionStore = new FixedCallsignRegionStore([
            new CallsignRegionEntry("Q", "Q", "Synthetic (R&R Study)", null, null, null, Synthetic: true),
        ]);
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            regionStore: regionStore);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1);
        results[0].Region.Should().NotBeNull();
        results[0].Region!.Synthetic.Should().BeTrue();
        results[0].Region!.Entity.Should().Be("Synthetic (R&R Study)");
    }

    [Fact(DisplayName = "f-002 3.2/5.4: DecodeAsync resolves an unmatched prefix to a null Region without affecting acceptance")]
    public async Task DecodeAsync_UnmatchedCallsign_ResolvesNullRegion_StillAccepted()
    {
        var regionStore = new FixedCallsignRegionStore([
            new CallsignRegionEntry("Q", "Q", "Synthetic (R&R Study)", null, null, null, Synthetic: true),
        ]);
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ ZZ1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            regionStore: regionStore);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1, "an unmatched region must never withhold the decode");
        results[0].Region.Should().BeNull("an unmatched prefix resolves to null, rendered as \"Unknown\" by the frontend");
    }

    [Fact(DisplayName = "f-002 3.3: DecodeAsync degrades to a null Region when the region store throws, without affecting acceptance")]
    public async Task DecodeAsync_RegionStoreThrows_DegradesToNullRegion_StillAccepted()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop,
            grammarStore: FixedCallsignGrammarStore.Default,
            regionStore: new ThrowingCallsignRegionStore());

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1, "a region-resolution exception must never withhold the decode");
        results[0].Region.Should().BeNull("a region-resolution exception must degrade to null (\"Unknown\"), not propagate");
    }

    [Fact(DisplayName = "f-002: DecodeAsync leaves Region null when no region store is supplied")]
    public async Task DecodeAsync_NoRegionStoreSupplied_RegionStaysNull()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = 5, Message = "CQ Q1ABC FN42" });

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 4, 10, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(1);
        results[0].Region.Should().BeNull("callers that do not wire up a region store keep today's behaviour (Region always null)");
    }
}
