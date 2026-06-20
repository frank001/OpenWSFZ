using FluentAssertions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Integration tests for H6 directed AP decode efficacy (D-001).
///
/// <para>
/// These tests use the <b>real native decoder</b> and a <b>synthetic co-channel
/// fixture generated in memory</b> from natively-encoded FT8 tone sequences.
/// Two equal-amplitude FT8 signals are superimposed at the same audio frequency;
/// the combined LLRs are ambiguous for blind decode, but directed AP constraints
/// (mycall/hiscall hard-anchored to ±40.0) assist LDPC convergence for the target
/// message.
/// </para>
///
/// <para>
/// Fixture construction:
/// <list type="bullet">
///   <item>Signal A — <c>"Q1OFZ Q9XYZ JO33"</c> at 1500 Hz (mycall=Q1OFZ, hiscall=Q9XYZ)</item>
///   <item>Signal B — <c>"Q9XYZ Q1OFZ RR73"</c> at 1500 Hz (swapped pair — AP bits wrong for B)</item>
///   <item>Equal amplitude (0.35 each); no added noise (interference itself causes LDPC failure blind)</item>
/// </list>
/// </para>
///
/// <para>
/// Both tests MUST pass for the branch to be merged (handoff acceptance criterion).
/// </para>
/// </summary>
/// <remarks>
/// <para>
/// <b>Coverage limitation (shim 20260025):</b>
/// <c>osd_decode</c> was also wired into <c>ftx_decode_candidate_ap</c> in
/// shim 20260025.  The combined AP+OSD path — where AP constraints are provided,
/// BP still fails despite them, and OSD recovers the message — is not exercised
/// by any test in this class.
/// </para>
/// <para>
/// Engineering a deterministic fixture for this path is not currently feasible:
/// with ±40.0 hard constraints on 56 bits (the H6 standard constraint strength),
/// BP reliably converges and OSD never fires.  A scenario where AP constraints are
/// provided but insufficient for BP convergence would require either a weaker
/// constraint strength (not supported by the current C# API) or a more destructive
/// interference geometry (e.g., 3-stack equal-SNR, which defeats both BP and OSD).
/// </para>
/// <para>
/// Risk assessment: LOW.  <c>osd_decode</c> is validated by
/// <c>D001OsdDecodeTests</c>.  The OSD wiring in <c>ftx_decode_candidate_ap</c>
/// is an exact structural copy of the wiring in <c>ftx_decode_candidate</c>; any
/// defect in the copy would be a trivially detectable compile or logic error.
/// This gap is recorded in <c>traceability-debt.md</c>.
/// </para>
/// </remarks>
[Trait("Category", "Integration")]
public sealed class D001H6ApDecodeTests
{
    // ── Fixture callsigns (Q-prefix, NFR-021) ─────────────────────────────────
    private const string Mycall  = "Q1OFZ";
    private const string Hiscall = "Q9XYZ";

    // Messages used in the co-channel fixture:
    // Signal A: hiscall answers mycall's CQ → decoded if AP succeeds
    // Signal B: mycall finishes QSO with hiscall → AP bits are WRONG for B (callsigns swapped)
    private const string MessageA = "Q1OFZ Q9XYZ JO33";
    private const string MessageB = "Q9XYZ Q1OFZ RR73";

    private const double AudioFreqHz    = 1500.0;
    private const float  SignalAmplitude = 0.35f;
    private const int    TotalSamples   = 180_000;

    // ── Tests ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "D-001 H6: AP decode recovers co-channel message when AP bits are correct")]
    public async Task ApDecode_WithCorrectBits_RecoversCoChannelMessage()
    {
        var clock   = new FakeClock(new DateTime(2026, 6, 18, 12, 0, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        // Arm AP constraints — mycall=Q1OFZ, hiscall=Q9XYZ.
        byte[] mycallBits  = Ft8CallsignPacker.Pack28(Mycall);
        byte[] hiscallBits = Ft8CallsignPacker.Pack28(Hiscall);
        mycallBits.Should().HaveCount(4, "Pack28(Q1OFZ) must succeed");
        hiscallBits.Should().HaveCount(4, "Pack28(Q9XYZ) must succeed");

        decoder.SetApConstraints(new Ft8ApConstraints(mycallBits, hiscallBits));

        // Build the co-channel fixture PCM.
        float[] pcm = BuildCoChannelFixture();

        // Decode with AP constraints.
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        // Assert: at least one decoded message contains one of our callsigns.
        // AP decode injects the correct callsign bits; LDPC should converge for signal A.
        results.Should().NotBeEmpty(
            "AP decode with correct mycall/hiscall bits should recover at least " +
            "one co-channel message — LDPC receives 56 hard-constrained bits that " +
            "match signal A's callsign fields (H6 hypothesis)");

        results.Should().Contain(
            r => r.Message.Contains(Mycall, StringComparison.OrdinalIgnoreCase) ||
                 r.Message.Contains(Hiscall, StringComparison.OrdinalIgnoreCase),
            because: $"at least one decoded message must mention {Mycall} or {Hiscall}");
    }

    /// <summary>
    /// Guards the baseline: without AP bits, the Δ0 Hz co-channel fixture must produce
    /// no decoded messages and must not recover either target callsign.
    /// </summary>
    /// <remarks>
    /// <para>
    /// At Δ0 Hz, the two signals produce <b>near-zero LLRs across all 174 bits</b>
    /// (equal energy at competing tones for every symbol).  Belief-propagation (BP)
    /// fails because neither message achieves LDPC convergence from coin-flip soft
    /// decisions.
    /// </para>
    /// <para>
    /// With OSD active (shim 20260025+), <c>osd_decode</c> runs 529 CRC trials per
    /// candidate using coin-flip hard decisions.  The probability of OSD accidentally
    /// reconstructing a CRC-valid codeword that encodes Q1OFZ or Q9XYZ is negligible
    /// (≈ 1/2^63 per trial), so the <c>NotContain</c> assertion remains valid and
    /// the test is not flaky.
    /// </para>
    /// <para>
    /// OSD <em>may</em> produce occasional spurious decoded messages that encode neither
    /// callsign (a random CRC collision on near-zero-LLR bit patterns).  The secondary
    /// <c>BeEmpty</c> assertion catches this: any non-empty result from this fixture
    /// would indicate a spurious CRC false-positive and is a product defect worth
    /// investigating.  If <c>BeEmpty</c> proves flaky in CI, report to QA before
    /// relaxing it back to <c>NotContain</c>.
    /// </para>
    /// </remarks>
    [Fact(DisplayName = "D-001 H6: blind decode fails on co-channel fixture (baseline regression guard)")]
    public async Task BlindDecode_WithoutApBits_FailsOnCoChannel()
    {
        var clock   = new FakeClock(new DateTime(2026, 6, 18, 12, 0, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        // No AP constraints — shim clears TLS state (SetApBits([], []) path).
        // _apConstraints = null is the default.

        float[] pcm = BuildCoChannelFixture();

        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        // Primary gate: no target callsign may be decoded blind.
        results.Should().NotContain(
            r => r.Message.Contains(Mycall,  StringComparison.OrdinalIgnoreCase) ||
                 r.Message.Contains(Hiscall, StringComparison.OrdinalIgnoreCase),
            because: "blind decode of a Δ0 Hz co-channel fixture must not recover " +
                     "the target callsign pair — coin-flip LLRs make OSD's chances of " +
                     "hitting Q1OFZ or Q9XYZ negligible (≈1/2^63 per trial)");

        // Secondary gate: the result set must be empty.
        // At Δ0 Hz, OSD is exploring random bit patterns; any non-empty result would
        // indicate a spurious CRC false-positive from the decoder. A genuine false
        // positive at this fixture would be a product defect worth investigating.
        results.Should().BeEmpty(
            because: "blind decode of a Δ0 Hz co-channel fixture should produce zero " +
                     "decoded messages — near-zero LLRs should cause both BP and OSD " +
                     "to fail for every candidate");
    }

    // ── Fixture builder ───────────────────────────────────────────────────────

    /// <summary>
    /// Builds a 15-second (180 000-sample) 12 kHz mono PCM buffer containing two
    /// equal-amplitude FT8 signals superimposed at the same audio frequency.
    ///
    /// <para>
    /// Signal A encodes <see cref="MessageA"/> (<c>Q1OFZ Q9XYZ JO33</c>).
    /// Signal B encodes <see cref="MessageB"/> (<c>Q9XYZ Q1OFZ RR73</c>).
    /// Both are placed at <see cref="AudioFreqHz"/> Hz (1500 Hz) with tone indices
    /// synthesised from the native ft8_encode_message entry point, ensuring the
    /// bit pattern exactly matches what ft8_lib's decoder expects.
    /// </para>
    ///
    /// <para>
    /// <b>Why this causes blind decode failure:</b>
    /// Signal A and B carry different bit patterns → different Gray-coded tone
    /// sequences → in any given symbol period, A and B usually select different
    /// tones.  The composite spectrogram shows equal energy at tone(A) and tone(B)
    /// for each such symbol → ambiguous LLR ≈ 0 → LDPC cannot converge → 0 decodes.
    /// </para>
    ///
    /// <para>
    /// <b>Why AP decode succeeds:</b>
    /// The AP constraints fix the 56 callsign-field bits of signal A to the correct
    /// values (±40.0 LLR), regardless of the waterfall ambiguity.  With 56/91
    /// information bits strongly anchored, LDPC can determine the remaining 35
    /// information bits from parity constraints even with near-zero soft LLRs.
    /// </para>
    /// </summary>
    private static float[] BuildCoChannelFixture()
    {
        // Encode both messages with the native FT8 encoder (ensures correct i3/n3 bits).
        var tonesA = new byte[Ft8LibInterop.EncodedToneCount];
        var tonesB = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(MessageA, tonesA);
        Ft8LibInterop.EncodeMessage(MessageB, tonesB);

        // Convert byte[] tone indices to int[] for SymbolsToPcm.
        int[] symA = Array.ConvertAll(tonesA, static t => (int)t);
        int[] symB = Array.ConvertAll(tonesB, static t => (int)t);

        // Synthesise PCM for each signal at the same base frequency, equal amplitude.
        // SymbolsToPcm generates CP-FSK (continuous-phase sine per symbol), which the
        // ft8_lib spectrogram-based candidate detector correctly demodulates.
        float[] pcmA = TestFt8Encoder.SymbolsToPcm(symA, AudioFreqHz, amplitude: SignalAmplitude);
        float[] pcmB = TestFt8Encoder.SymbolsToPcm(symB, AudioFreqHz, amplitude: SignalAmplitude);

        // Superimpose: co-channel composite.
        var pcm = new float[TotalSamples];
        for (int i = 0; i < TotalSamples; i++)
            pcm[i] = pcmA[i] + pcmB[i];

        return pcm;
    }
}
