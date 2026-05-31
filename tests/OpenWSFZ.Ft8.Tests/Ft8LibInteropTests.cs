using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="Ft8LibInterop"/> — the P/Invoke binding layer.
///
/// <para>
/// These tests exercise the native shim directly, bypassing the silence guard in
/// <see cref="Ft8Decoder.DecodeAsync"/> that short-circuits before any P/Invoke call
/// on all-zero input.  Calling <see cref="Ft8LibInterop.DecodeAll"/> directly ensures
/// that the two-pass decode loop and the thread-local storage (TLS) per-pass stats
/// mechanism are both exercised and queryable via <see cref="Ft8LibInterop.GetLastPassCounts"/>.
/// </para>
/// </summary>
public sealed class Ft8LibInteropTests
{
    /// <summary>
    /// p15 regression: verifies that after a decode call on a silent (all-zero) PCM
    /// buffer, <c>GetLastPassCounts(2)</c> returns exactly <c>[0, 0]</c>.
    ///
    /// <para>
    /// The native shim always executes <c>K_MAX_PASSES</c> (= 2) full passes even when
    /// no candidates are found; the per-pass new-decode counts are stored in TLS and
    /// must both be 0 for a silent input.  This test protects the TLS mechanic from
    /// future regressions that could cause stale counts to be returned or the pass-count
    /// array to be shorter than expected.
    /// </para>
    ///
    /// <para>
    /// Both calls MUST be on the same thread — no <c>Task.Run</c> wrapper — because
    /// <c>ft8_get_last_pass_counts</c> reads from the same TLS slot written by
    /// <c>ft8_decode_all</c>.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "p15: GetLastPassCounts returns [0, 0] after DecodeAll on a silent PCM buffer")]
    public void GetLastPassCounts_AfterDecodeAllOnSilentBuffer_ReturnsTwoZeroCounts()
    {
        // Arrange — 180 000 zeroed samples (15 s × 12 kHz, all zero amplitude).
        var pcm = new float[180_000]; // default-initialised to 0.0f

        // Act — both calls on the same thread (no Task.Run); TLS is thread-scoped.
        _ = Ft8LibInterop.DecodeAll(pcm);
        int[] counts = Ft8LibInterop.GetLastPassCounts(2);

        // Assert — K_MAX_PASSES=2 passes execute; no candidates found in either pass.
        counts.Should().Equal([0, 0],
            "a silent buffer produces no decodes in either pass, " +
            "but both passes still execute and record their (zero) counts in TLS");
    }
}
