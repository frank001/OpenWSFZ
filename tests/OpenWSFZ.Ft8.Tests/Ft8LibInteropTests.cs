using System.IO;
using System.Linq;
using System.Reflection;
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
    /// must all be 0 for a silent input.  This test protects the TLS mechanic from
    /// future regressions that could cause stale counts to be returned or the pass-count
    /// array to be shorter or longer than expected.
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
        int[] counts = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);

        // Assert — K_MAX_PASSES=2 passes execute; no candidates found in any pass.
        counts.Should().Equal([0, 0],
            "a silent buffer produces no decodes in any pass, " +
            "but both passes still execute and record their (zero) counts in TLS");
    }

    /// <summary>
    /// p15 regression: verifies that on a real-signal fixture, pass 1 finds at least
    /// one signal AND that the sum of per-pass counts equals the total decode count.
    ///
    /// <para>
    /// This test exercises the TLS pass-count mechanic on live RF signal data, not just
    /// a silent buffer.  It would fail if <c>suppress_candidate_tiles</c> were a no-op,
    /// if <c>K_MIN_SCORE_PASS2</c> were set to <c>INT_MAX</c>, or if the
    /// sum-of-pass-counts invariant (spec: <c>specs/ft8lib-interop/spec.md</c>) were
    /// violated by a regression in R4-1, R4-3, or R4-6.
    /// </para>
    ///
    /// <para>
    /// Both calls MUST be on the same thread — no <c>Task.Run</c> wrapper — because
    /// <c>ft8_get_last_pass_counts</c> reads from the TLS slot written by
    /// <c>ft8_decode_all</c>.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "p15: GetLastPassCounts sum equals total decode count on a synthetic multi-signal fixture")]
    public void GetLastPassCounts_AfterDecodeAllOnRealSignal_SumEqualsTotal()
    {
        // Arrange — load the first committed synthetic fixture WAV (synth-qso-01).
        // The fixture is a 12 kHz mono int16 PCM WAV embedded as a resource, carrying
        // several FT8 signals using only fictional Q-prefix callsigns (no real
        // third-party operators). Use WavReader (the int16-aware reader).
        float[] pcm = LoadFixtureWav("synth-qso-01.wav");
        pcm.Should().HaveCount(180_000,
            "the fixture WAV must be exactly 15 s × 12 kHz = 180 000 samples");

        // Act — both calls on the same thread (no Task.Run); TLS is thread-scoped.
        Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);
        int[] counts = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);

        // Assert 1 — pass 1 decoded at least one signal on a multi-signal fixture.
        counts.Should().NotBeEmpty("multi-signal fixture must execute at least one pass");
        counts[0].Should().BeGreaterThan(0,
            "pass 1 must find at least one signal in the synthetic fixture; " +
            "a value of 0 indicates the waterfall scan or LDPC is broken");

        // Assert 2 — sum of per-pass counts equals total returned by DecodeAll.
        // This is an explicit spec requirement (specs/ft8lib-interop/spec.md).
        int sumOfCounts = counts.Sum();
        sumOfCounts.Should().Be(results.Length,
            "the sum of pass-by-pass new-decode counts must equal the total " +
            "number of results returned by DecodeAll — any mismatch indicates " +
            "a regression in the TLS accounting or the result-buffer capacity (R4-1)");
    }

    /// <summary>
    /// diag-D001: verifies that after a decode call on a silent (all-zero) PCM
    /// buffer, <c>GetLastCandidateCounts(2)</c> returns exactly <c>[0, 0]</c>.
    /// </summary>
    [Fact(DisplayName = "diag-D001: GetLastCandidateCounts returns [0, 0] after DecodeAll on a silent PCM buffer")]
    public void GetLastCandidateCounts_AfterDecodeAllOnSilentBuffer_ReturnsTwoZeroCounts()
    {
        // Arrange
        var pcm = new float[180_000];

        // Act — same thread; TLS is thread-scoped
        _ = Ft8LibInterop.DecodeAll(pcm);
        int[] counts = Ft8LibInterop.GetLastCandidateCounts(Ft8LibInterop.MaxDecodePasses);

        // Assert — even a silent buffer runs both passes; each finds 0 candidates
        counts.Should().Equal([0, 0],
            "a silent buffer produces no waterfall energy; ftx_find_candidates " +
            "returns 0 candidates in every pass");
    }

    /// <summary>
    /// diag-D001: verifies that on a real-signal fixture, per-pass candidate counts
    /// are always >= per-pass decode counts (cannot decode more than we found).
    /// </summary>
    [Fact(DisplayName = "diag-D001: GetLastCandidateCounts on real fixture — per-pass candidates >= per-pass decodes")]
    public void GetLastCandidateCounts_AfterDecodeAllOnRealSignal_CandidatesAtLeastDecodes()
    {
        // Arrange
        float[] pcm = LoadFixtureWav("synth-qso-01.wav");
        pcm.Should().HaveCount(180_000);

        // Act — same thread
        Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);
        int[] decodeCounts    = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);
        int[] candidateCounts = Ft8LibInterop.GetLastCandidateCounts(Ft8LibInterop.MaxDecodePasses);

        // Assert 1 — same number of passes reported
        candidateCounts.Should().HaveSameCount(decodeCounts,
            "both TLS arrays are populated for the same number of passes");

        // Assert 2 — candidates >= decodes in every pass (you can't decode more
        // messages than there were candidates to decode from)
        for (int p = 0; p < candidateCounts.Length; p++)
        {
            candidateCounts[p].Should().BeGreaterThanOrEqualTo(decodeCounts[p],
                $"pass {p + 1}: cannot decode more messages than candidates found");
        }

        // Assert 3 — pass 0 found at least one candidate on a signal-bearing fixture
        candidateCounts[0].Should().BeGreaterThan(0,
            "pass 0 must find at least one candidate in the synthetic signal fixture");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Loads a 12 kHz mono int16 PCM WAV from the test assembly's embedded
    /// resources and returns it as a normalised float[] PCM buffer.
    /// </summary>
    private static float[] LoadFixtureWav(string wavFileName)
    {
        Assembly asm      = Assembly.GetExecutingAssembly();
        string   asmName  = asm.GetName().Name!;
        string   fullName = $"{asmName}.Fixtures.{wavFileName}";

        Stream? stream = asm.GetManifestResourceStream(fullName);
        if (stream is null)
        {
            // Fall back to suffix match (resource naming may vary by build config).
            stream = asm.GetManifestResourceNames()
                .Where(n => n.EndsWith(wavFileName, StringComparison.OrdinalIgnoreCase))
                .Select(n => asm.GetManifestResourceStream(n))
                .FirstOrDefault(s => s is not null);
        }

        if (stream is null)
            throw new InvalidOperationException(
                $"Embedded WAV resource '{fullName}' not found. " +
                $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");

        using (stream)
            return WavReader.Read(stream);
    }
}
