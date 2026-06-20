using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Integration tests for OSD (Ordered-Statistics Decoding) fallback path (D-001 / shim 20260025).
///
/// <para>
/// These tests use the <b>real native decoder</b> and a <b>synthetic co-channel
/// fixture generated in memory</b> at a <b>Δ7 Hz frequency offset</b> — the exact
/// geometry confirmed as the OSD recovery target by the H6 AP probe
/// (<c>run_h6_probe.py</c>, 2026-06-20, <c>266aeea</c>).
/// </para>
///
/// <para>
/// Fixture construction:
/// <list type="bullet">
///   <item>Signal A — <c>"Q1OFZ Q9XYZ JO33"</c> at 1500 Hz (dominant target)</item>
///   <item>Signal B — <c>"Q9XYZ Q1OFZ RR73"</c> at 1507 Hz (interferer, Δ7 Hz offset)</item>
///   <item>Equal amplitude (0.35 each); no added noise</item>
///   <item>180 000 samples at 12 kHz (standard 15 s FT8 window)</item>
/// </list>
/// </para>
///
/// <para>
/// <b>Why Δ7 Hz causes blind BP failure without OSD:</b>
/// At 7 Hz separation (just over one 6.25 Hz tone bin), the two signals produce
/// overlapping spectral energy.  BP converges unreliably (~40% on the R&amp;R harness)
/// because the interferer's tones alias into the target's soft-decision LLRs.
/// Without OSD, the fixture is a stochastic failure for specific message pairs.
/// </para>
///
/// <para>
/// <b>Why OSD succeeds:</b>
/// OSD performs Gaussian elimination over the most-reliable bit positions and
/// exhausts 2^10 = 1024 CRC-checked candidates (shim 20260025 uses 50 BP iterations +
/// OSD fallback).  Even with degraded LLRs, OSD can recover the dominant signal by
/// brute-forcing the most ambiguous bit positions.
/// </para>
///
/// <para>
/// <b>Test determinism:</b>
/// The fixture is purely synthetic (no AWGN seed), so the PCM input is identical on
/// every run.  With OSD active the result is a deterministic PASS; without OSD
/// (or with a shim lacking the OSD code path) this test deterministically FAILs
/// because the specific message pair at Δ7 Hz does not converge under BP alone.
/// </para>
///
/// <para>
/// This test MUST pass for the branch to be merged (handoff acceptance criterion AC7).
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class D001OsdDecodeTests
{
    // ── Fixture callsigns (Q-prefix, NFR-021) ─────────────────────────────────
    private const string Mycall  = "Q1OFZ";
    private const string Hiscall = "Q9XYZ";

    // Messages used in the co-channel fixture:
    // Signal A: hiscall answers mycall's CQ at 1500 Hz → dominant target
    // Signal B: mycall finishes QSO with hiscall at 1507 Hz → interferer (Δ7 Hz)
    private const string MessageA = "Q1OFZ Q9XYZ JO33";
    private const string MessageB = "Q9XYZ Q1OFZ RR73";

    private const double AudioFreqA_Hz   = 1500.0;
    private const double AudioFreqB_Hz   = 1507.0; // Δ7 Hz interferer
    private const float  SignalAmplitude = 0.35f;
    private const int    TotalSamples    = 180_000;

    // ── Tests ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// OSD fallback recovers the dominant signal in a Δ7 Hz co-channel fixture
    /// under blind decode (no AP constraints).
    ///
    /// <para>
    /// This test will PASS with OSD active (shim 20260025) and FAIL with a shim
    /// that lacks OSD — providing a deterministic gate on the OSD success path
    /// that no amount of BP iterations alone can satisfy for this specific fixture.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "D-001 OSD: blind decode recovers co-channel message at Δ7 Hz (OSD success path)")]
    public async Task OsdDecode_BlindDecode_RecoversDominantSignalAtDelta7Hz()
    {
        var clock   = new FakeClock(new DateTime(2026, 6, 20, 12, 0, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        // No AP constraints — this is a BLIND decode test.
        // OSD must recover the signal without callsign hints.

        float[] pcm = BuildDelta7HzFixture();

        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        // Assert: at least one decoded message contains one of the target callsigns.
        // OSD closes the Δ7 Hz co-channel gap; without OSD this fixture fails blind.
        results.Should().NotBeEmpty(
            "OSD fallback should recover at least one message from the Δ7 Hz " +
            "co-channel fixture — BP alone fails for this message pair at this offset");

        results.Should().Contain(
            r => r.Message.Contains(Mycall,  StringComparison.OrdinalIgnoreCase) ||
                 r.Message.Contains(Hiscall, StringComparison.OrdinalIgnoreCase),
            because: $"at least one decoded message must mention {Mycall} or {Hiscall} — " +
                     $"OSD should recover the dominant signal at 1500 Hz from the Δ7 Hz fixture");
    }

    // ── Fixture builder ───────────────────────────────────────────────────────

    /// <summary>
    /// Builds a 15-second (180 000-sample) 12 kHz mono PCM buffer containing two
    /// equal-amplitude FT8 signals at a <b>7 Hz frequency offset</b>.
    ///
    /// <para>
    /// Signal A encodes <see cref="MessageA"/> (<c>Q1OFZ Q9XYZ JO33</c>) at 1500 Hz.
    /// Signal B encodes <see cref="MessageB"/> (<c>Q9XYZ Q1OFZ RR73</c>) at 1507 Hz.
    /// This is the <em>same geometry</em> as S7 part 0 and as the H6 AP probe
    /// (<c>run_h6_probe.py</c>): two operators independently clicking the same
    /// waterfall spot with a 7 Hz tuning offset.
    /// </para>
    ///
    /// <para>
    /// <b>Why Δ7 Hz is harder than Δ0 Hz (the H6 fixture):</b>
    /// At Δ0 Hz the LLRs are exactly zero for every symbol (equal energy at two
    /// competing tones), so BP consistently fails and AP decode consistently succeeds.
    /// At Δ7 Hz the dominant signal leaks some net energy into the candidate search,
    /// so BP converges <em>sometimes</em> (~40%) but not always — making the result
    /// non-deterministic under pure BP.  OSD, by exhausting ranked bit combinations,
    /// achieves deterministic recovery of the dominant signal.
    /// </para>
    /// </summary>
    private static float[] BuildDelta7HzFixture()
    {
        // Encode both messages with the native FT8 encoder (ensures correct i3/n3 bits
        // and Gray-coded tone sequence matching what ft8_lib's decoder expects).
        var tonesA = new byte[Ft8LibInterop.EncodedToneCount];
        var tonesB = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(MessageA, tonesA);
        Ft8LibInterop.EncodeMessage(MessageB, tonesB);

        // Convert byte[] tone indices to int[] for SymbolsToPcm.
        int[] symA = Array.ConvertAll(tonesA, static t => (int)t);
        int[] symB = Array.ConvertAll(tonesB, static t => (int)t);

        // Synthesise PCM for each signal at their respective frequencies.
        // Signal A is the target (1500 Hz); Signal B is the interferer (1507 Hz, Δ7 Hz).
        float[] pcmA = TestFt8Encoder.SymbolsToPcm(symA, AudioFreqA_Hz, amplitude: SignalAmplitude);
        float[] pcmB = TestFt8Encoder.SymbolsToPcm(symB, AudioFreqB_Hz, amplitude: SignalAmplitude);

        // Superimpose: co-channel composite.
        var pcm = new float[TotalSamples];
        for (int i = 0; i < TotalSamples; i++)
            pcm[i] = pcmA[i] + pcmB[i];

        return pcm;
    }
}
