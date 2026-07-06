using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Integration tests for D-005 — ft8_lib trailing-space message padding.
///
/// <para>
/// <c>ft8_lib</c> pads <c>FT8Result.message</c> to 36 bytes with trailing spaces
/// before the null terminator.  A Type 4 hash message such as
/// <c>&lt;HASH&gt; CALLSIGN</c> marshals to <c>"&lt;HASH&gt; CALLSIGN "</c> (trailing
/// space), which <see cref="Ft8Decoder.IsPlausibleMessage"/> incorrectly rejects
/// because it sees two spaces and enters the three-token branch with an empty
/// last field.
/// </para>
///
/// <para>
/// Fix: <c>msg = nr.Message.TrimEnd()</c> applied before deduplication and
/// plausibility checking in <see cref="Ft8Decoder.DecodeAsync"/>.
/// </para>
///
/// <para>
/// Tests use the <see cref="IFt8NativeInterop"/> injection seam so the native
/// DLL is never loaded.  All callsigns are ITU-unallocated Q-prefix per NFR-021.
/// </para>
/// </summary>
public sealed class D005MessageTrimTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>
    /// Fake interop that returns a fixed set of <see cref="Ft8NativeResult"/>s,
    /// allowing precise control over the message strings returned to <see cref="Ft8Decoder"/>.
    /// </summary>
    private sealed class FixedResultInterop(params Ft8NativeResult[] results) : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => results;

        public int[]  GetLastPassCounts(int maxPasses)      => [results.Length, 0];
        public int[]  GetLastCandidateCounts(int maxPasses) => [results.Length, 0];
        public float  GetLastNoiseFloorDb()                  => -70.0f;
        public int    GetHashTableRejectCount()              => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Returns a 180 000-sample PCM buffer well above the silence guard (1e-6 RMS).
    /// </summary>
    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++)
            pcm[i] = 0.1f;
        return pcm;
    }

    private static Ft8Decoder BuildDecoder(IFt8NativeInterop interop)
        => new(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)),
               logger: null,
               interop: interop);

    // ── Tests ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// A Type 4 hash message padded with a trailing space by ft8_lib must appear
    /// in the results — not be filtered — and the stored message must have the
    /// trailing space removed.
    /// </summary>
    [Fact(DisplayName = "D-005: 2-field hash message with trailing space is accepted and trimmed")]
    public async Task DecodeAsync_HashMessageWithTrailingSpace_IsAcceptedAndTrimmed()
    {
        // "<Q1ABC> Q2DEF " — trailing space creates an apparent empty third token
        // that was incorrectly filtered before the D-005 fix.
        var interop = new FixedResultInterop(new Ft8NativeResult
        {
            FreqHz = 1234,
            Dt     = 0.2f,
            Snr    = 5,
            Message = "<Q1ABC> Q2DEF "       // trailing space: the D-005 pattern
        });
        var decoder = BuildDecoder(interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().ContainSingle(
            "the trailing-space hash message must not be filtered by IsPlausibleMessage");

        results[0].Message.Should().Be("<Q1ABC> Q2DEF",
            "TrimEnd() must remove ft8_lib padding before the message is stored");
    }

    /// <summary>
    /// A plain 2-field message (no hash notation) padded with a trailing space
    /// must likewise be accepted and stored trimmed.
    /// </summary>
    [Fact(DisplayName = "D-005: 2-field plain message with trailing space is accepted and trimmed")]
    public async Task DecodeAsync_PlainTwoFieldMessageWithTrailingSpace_IsAcceptedAndTrimmed()
    {
        var interop = new FixedResultInterop(new Ft8NativeResult
        {
            FreqHz = 800,
            Dt     = 0.1f,
            Snr    = -3,
            Message = "Q1ABC Q2DEF "         // trailing space: same D-005 pattern, no hash
        });
        var decoder = BuildDecoder(interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().ContainSingle(
            "a 2-field plain message with trailing space must reach the caller");

        results[0].Message.Should().Be("Q1ABC Q2DEF",
            "trailing space must be stripped before storage");
    }

    /// <summary>
    /// When the native shim returns both a trailing-space variant and the same
    /// message without trailing space (e.g. from two decode candidates), they
    /// must be deduplicated to a single result — not both appear.
    /// </summary>
    [Fact(DisplayName = "D-005: trailing-space and trimmed variants of the same message are deduplicated")]
    public async Task DecodeAsync_TrailingSpaceAndTrimmedVariants_AreDeduplicatedToOne()
    {
        var interop = new FixedResultInterop(
            // Two candidates for the same message: one padded, one clean.
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.1f, Snr = 5,  Message = "<Q1ABC> Q2DEF " },
            new Ft8NativeResult { FreqHz = 1002, Dt = 0.2f, Snr = 4,  Message = "<Q1ABC> Q2DEF"  }
        );
        var decoder = BuildDecoder(interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().ContainSingle(
            "the padded and unpadded variants represent the same message and must be deduplicated");

        results[0].Message.Should().Be("<Q1ABC> Q2DEF");
    }

    /// <summary>
    /// A genuinely implausible 3-token message (impossible Maidenhead grid) must
    /// still be filtered after the D-005 fix — trimming must not break the
    /// existing R4 false-positive guard.
    /// </summary>
    [Fact(DisplayName = "D-005: R4 plausibility filter still rejects impossible Maidenhead grids after trim fix")]
    public async Task DecodeAsync_ImpossibleGrid_IsStillFilteredAfterTrimFix()
    {
        // "SN31" has first letter 'S' > 'R' — impossible Maidenhead encoding.
        var interop = new FixedResultInterop(new Ft8NativeResult
        {
            FreqHz = 1500,
            Dt     = 0.3f,
            Snr    = 8,
            Message = "Q1ABC Q2DEF SN31"     // no trailing space; R4 filter must reject
        });
        var decoder = BuildDecoder(interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().BeEmpty(
            "an impossible Maidenhead grid value must still be caught by the R4 filter");
    }
}
