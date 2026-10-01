using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for <see cref="SubfeasPayload"/> (sub-feas-native-subtraction, tasks.md 2.5).
///
/// <para>
/// Deliberately cross-checks <see cref="SubfeasPayload.ExtractPayload77"/> against the REAL
/// native <see cref="Ft8LibInterop.EncodeMessage"/> (loads the actual native DLL, not a fake)
/// — this is the strongest available correctness signal for the bit-layout port: if the
/// extracted fields for a known message type don't match what the real encoder actually
/// produced, that is a genuine bug, not a divergence between two independent guesses at the
/// same layout.
/// </para>
/// </summary>
public sealed class SubfeasPayloadTests
{
    [Fact(DisplayName = "ExtractPayload77: a real RR73 message's fields match message.c's own layout (i3=1, RR73 sentinel)")]
    public void ExtractPayload77_RealRr73Message_HasExpectedStdFields()
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ RR73", tones);

        bool[] payload77 = SubfeasPayload.ExtractPayload77(tones);
        payload77.Should().HaveCount(77);

        var fields = SubfeasPayload.ExtractStdFields(payload77);
        fields.I3.Should().Be(1, "a Standard QSO message must use the i3=1 layout");
        fields.Ir.Should().BeFalse("this repo's own encoder's RR73 sentinel has ir=0");
        fields.Igrid4.Should().Be(32_403, "MAXGRID4(32400)+3 — this repo's own encoder's RR73 sentinel (message.c)");
    }

    [Fact(DisplayName = "ExtractPayload77: a real 73 (not RR73) report is NOT read as the RR73 sentinel")]
    public void ExtractPayload77_RealReportMessage_IsNotRr73Sentinel()
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ +05", tones);

        bool[] payload77 = SubfeasPayload.ExtractPayload77(tones);
        var fields = SubfeasPayload.ExtractStdFields(payload77);

        (fields.Ir, fields.Igrid4).Should().NotBe((false, 32_403),
            "a dB-report message must not be mistaken for the RR73 sentinel");
    }

    [Fact(DisplayName = "ExtractPayload77: two different messages produce different payloads")]
    public void ExtractPayload77_DifferentMessages_ProduceDifferentPayloads()
    {
        var tonesA = new byte[79];
        var tonesB = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO33", tonesA);
        Ft8LibInterop.EncodeMessage("Q1DEF Q1UVW EN37", tonesB);

        var a = SubfeasPayload.ExtractPayload77(tonesA);
        var b = SubfeasPayload.ExtractPayload77(tonesB);

        a.Should().NotBeEquivalentTo(b, options => options.WithStrictOrdering());
    }

    [Fact(DisplayName = "ExtractPayload77: the same message re-encoded produces an identical payload")]
    public void ExtractPayload77_SameMessageTwice_ProducesIdenticalPayload()
    {
        var tones1 = new byte[79];
        var tones2 = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO33", tones1);
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO33", tones2);

        var a = SubfeasPayload.ExtractPayload77(tones1);
        var b = SubfeasPayload.ExtractPayload77(tones2);

        a.Should().BeEquivalentTo(b, options => options.WithStrictOrdering());
    }

    [Fact(DisplayName = "SameQso: exact bit match is always the same QSO")]
    public void SameQso_ExactMatch_ReturnsTrue()
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO33", tones);
        var payload = SubfeasPayload.ExtractPayload77(tones);

        SubfeasPayload.SameQso(payload, payload).Should().BeTrue();
    }

    [Fact(DisplayName = "SameQso: a non-RR73 message with any bit difference is NOT the same QSO (no asymmetry leniency)")]
    public void SameQso_NonRr73DifferentPayload_ReturnsFalse()
    {
        var tonesA = new byte[79];
        var tonesB = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO33", tonesA);
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO34", tonesB); // one grid character different

        var a = SubfeasPayload.ExtractPayload77(tonesA);
        var b = SubfeasPayload.ExtractPayload77(tonesB);

        SubfeasPayload.SameQso(a, b).Should().BeFalse();
    }

    [Fact(DisplayName = "SameQso: RR73 reference matches an on-air-sentinel candidate with the same calls (the asymmetry this port exists for)")]
    public void SameQso_Rr73Reference_MatchesOnAirSentinelCandidate()
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ RR73", tones);
        bool[] reference = SubfeasPayload.ExtractPayload77(tones);

        // Simulate what a genuine on-air RR73 decode's payload looks like: identical to our
        // own re-encoded reference except igrid4 carries the on-air sentinel (32373) instead
        // of our own encoder's (32403) — exactly the asymmetry stage2.py's _same_qso exists
        // for (board 2026-09-27 GAP-LOCATE finding). ir stays 0; only igrid4's 15 bits change.
        bool[] onAirCandidate = (bool[])reference.Clone();
        WriteIgrid4(onAirCandidate, 32_373);

        SubfeasPayload.SameQso(reference, onAirCandidate).Should().BeTrue(
            "a genuine on-air RR73 decode must be recognised as the same QSO as our own " +
            "re-encoded RR73 reference, even though the igrid4 sentinel value differs");
    }

    [Fact(DisplayName = "SameQso: RR73 asymmetry leniency does NOT apply when call1/call2 differ")]
    public void SameQso_Rr73Reference_DoesNotMatchOnAirSentinelWithDifferentCalls()
    {
        var tonesRef = new byte[79];
        var tonesOther = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ RR73", tonesRef);
        Ft8LibInterop.EncodeMessage("Q1DEF Q1UVW RR73", tonesOther);

        bool[] reference = SubfeasPayload.ExtractPayload77(tonesRef);
        bool[] otherOnAir = SubfeasPayload.ExtractPayload77(tonesOther);
        WriteIgrid4(otherOnAir, 32_373);

        SubfeasPayload.SameQso(reference, otherOnAir).Should().BeFalse(
            "the RR73 asymmetry leniency only forgives the igrid4 sentinel value, never call1/call2");
    }

    [Fact(DisplayName = "SameQso: a non-RR73 reference never gets asymmetry leniency, even if the candidate has the on-air sentinel value")]
    public void SameQso_NonRr73Reference_NoAsymmetryLeniency()
    {
        var tonesRef = new byte[79];
        Ft8LibInterop.EncodeMessage("Q1ABC Q1XYZ JO33", tonesRef); // NOT an RR73 message
        bool[] reference = SubfeasPayload.ExtractPayload77(tonesRef);

        bool[] candidate = (bool[])reference.Clone();
        WriteIgrid4(candidate, 32_373); // coincidentally matches the on-air RR73 sentinel value

        SubfeasPayload.SameQso(reference, candidate).Should().BeFalse(
            "the RR73 asymmetry check only fires when the REFERENCE is our own RR73-standard encoding");
    }

    [Fact(DisplayName = "ExtractPayload77: rejects a tones array of the wrong length")]
    public void ExtractPayload77_WrongLength_Throws()
    {
        var act = () => SubfeasPayload.ExtractPayload77(new byte[10]);
        act.Should().Throw<ArgumentException>();
    }

    [Fact(DisplayName = "ExtractPayload77: rejects a tone index outside [0,7]")]
    public void ExtractPayload77_ToneOutOfRange_Throws()
    {
        var tones = new byte[79];
        tones[10] = 8; // out of range
        var act = () => SubfeasPayload.ExtractPayload77(tones);
        act.Should().Throw<ArgumentException>();
    }

    /// <summary>Overwrites payload77's igrid4 field (bits [59,74), MSB-first) with <paramref name="value"/>.</summary>
    private static void WriteIgrid4(bool[] payload77, int value)
    {
        for (int i = 0; i < 15; i++)
            payload77[59 + i] = ((value >> (14 - i)) & 1) != 0;
    }
}
