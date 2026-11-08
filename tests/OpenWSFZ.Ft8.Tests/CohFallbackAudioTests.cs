using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-FB-AUDIO: the pure audio selector (the step-down), the log label and the <see cref="CoherentFallbackAudio.Both"/> merge. The decoder-level
/// wiring is in <see cref="CoherentFallbackWiringTests"/>. Deterministic: no timing, no I/O. 🔒 NFR-021: payload bytes only, no message text.
/// </summary>
public sealed class CohFallbackAudioTests
{
    private static readonly float[] Original = new float[180_000];
    private static readonly float[] ResidualBuf = new float[180_000];
    private static readonly float[] ThirdBuf = new float[180_000];

    private static SubtractionPass.ResidualPassReport Report(
        float[]? residual = null, int fitted = 2, bool abandoned = false, bool contained = false)
        => new() { Residual = residual ?? ResidualBuf, FittedSignals = fitted, DeadlineAbandoned = abandoned, ContainedException = contained };

    private static SubtractionPass.ThirdPassResult Third(string outcome, float[]? buffer = null)
        => new([], outcome, 1, outcome == SubtractionPass.ThirdPassOutcome.Ran ? 1 : 0, buffer);

    [Theory(DisplayName = "FR-099: COH-FB-AUDIO: Original - the SAME reference as the original audio, level original, whatever the report holds")]
    [InlineData(true)]
    [InlineData(false)]
    public void Original_ReturnsOriginalReference(bool deep)
    {
        var c = CohFallbackAudioSelector.Select(CoherentFallbackAudio.Original, Original, deep, Report(), Third(SubtractionPass.ThirdPassOutcome.Ran, ThirdBuf));
        c.Pcm.Should().BeSameAs(Original);
        c.Level.Should().Be("original");
        c.IsResidual.Should().BeFalse();
    }

    [Theory(DisplayName = "FR-100: COH-FB-AUDIO: Residual and Both step down identically - third pass ran: its own buffer (residual3)")]
    [InlineData(CoherentFallbackAudio.Residual)]
    [InlineData(CoherentFallbackAudio.Both)]
    public void ThirdRan_ThirdBuffer(CoherentFallbackAudio mode)
    {
        var c = CohFallbackAudioSelector.Select(mode, Original, true, Report(), Third(SubtractionPass.ThirdPassOutcome.Ran, ThirdBuf));
        c.Pcm.Should().BeSameAs(ThirdBuf);
        c.Level.Should().Be("residual3");
        c.IsResidual.Should().BeTrue();
    }

    [Theory(DisplayName = "FR-099: COH-FB-AUDIO: third pass absent / skipped / abandoned / failed - the residual pass's buffer (residual2)")]
    [InlineData(null)]
    [InlineData(SubtractionPass.ThirdPassOutcome.SkippedNoNew)]
    [InlineData(SubtractionPass.ThirdPassOutcome.SkippedAbandoned)]
    [InlineData(SubtractionPass.ThirdPassOutcome.Abandoned)]
    [InlineData(SubtractionPass.ThirdPassOutcome.Failed)]
    public void ThirdDidNotSubtract_ResidualPassBuffer(string? thirdOutcome)
    {
        var third = thirdOutcome is null ? null : Third(thirdOutcome, ThirdBuf);
        var c = CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, true, Report(), third);
        c.Pcm.Should().BeSameAs(ResidualBuf);
        c.Level.Should().Be("residual2");
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: third pass ran but exposes no buffer - falls back to the residual pass's buffer, never null")]
    public void ThirdRanWithoutBuffer_ResidualPassBuffer()
    {
        var c = CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, true, Report(), Third(SubtractionPass.ThirdPassOutcome.Ran, null));
        c.Pcm.Should().BeSameAs(ResidualBuf);
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Normal depth - original audio, unavailable")]
    public void Normal_Unavailable()
        => AssertUnavailable(CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, false, Report(), null));

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: Deep, no report - original audio, unavailable")]
    public void NoReport_Unavailable()
        => AssertUnavailable(CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, true, null, null));

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: residual pass abandoned on the deadline - unavailable although its buffer was assigned")]
    public void Abandoned_Unavailable()
        => AssertUnavailable(CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, true, Report(abandoned: true), null));

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: residual pass failed with a contained exception - unavailable")]
    public void ContainedException_Unavailable()
        => AssertUnavailable(CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, true, Report(contained: true), null));

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: residual buffer never built - unavailable")]
    public void NoBuffer_Unavailable()
        => AssertUnavailable(CohFallbackAudioSelector.Select(CoherentFallbackAudio.Residual, Original, true,
            new SubtractionPass.ResidualPassReport { FittedSignals = 2 }, null));

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: nothing subtracted (zero fitted signals) - unavailable even if a third result is present")]
    public void ZeroFitted_Unavailable()
        => AssertUnavailable(CohFallbackAudioSelector.Select(CoherentFallbackAudio.Both, Original, true, Report(fitted: 0),
            Third(SubtractionPass.ThirdPassOutcome.Ran, ThirdBuf)));

    private static void AssertUnavailable(CohFallbackAudioSelector.Choice c)
    {
        c.Pcm.Should().BeSameAs(Original);
        c.Level.Should().Be("unavailable");
        c.IsResidual.Should().BeFalse();
    }

    [Theory(DisplayName = "FR-099: COH-FB-AUDIO: the audio= label for each mode and level")]
    [InlineData(CoherentFallbackAudio.Original, "original", "original")]
    [InlineData(CoherentFallbackAudio.Residual, "residual3", "residual3")]
    [InlineData(CoherentFallbackAudio.Residual, "residual2", "residual2")]
    [InlineData(CoherentFallbackAudio.Residual, "unavailable", "residual-unavailable")]
    [InlineData(CoherentFallbackAudio.Both, "residual3", "both(residual3)")]
    [InlineData(CoherentFallbackAudio.Both, "residual2", "both(residual2)")]
    [InlineData(CoherentFallbackAudio.Both, "unavailable", "both(unavailable)")]
    public void Label_PerModeAndLevel(CoherentFallbackAudio mode, string level, string expected)
        => CohFallbackAudioSelector.Label(mode, level).Should().Be(expected);

    // ── the Both merge ──────────────────────────────────────────────────────────────────────────────────────

    private static CohFallbackRow Row(int id, float snr = -20f, bool edge = false, CohFallbackState state = CohFallbackState.NewGated)
    {
        var payload = new byte[12];
        payload[0] = (byte)id;
        return new CohFallbackRow(1000f, 0.3f, 1000.3f, 0.31f, 0, edge, state, (int)snr, 12.0, payload);
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO merge: one row per payload, the residual row where both found it, counts only/only/both")]
    public void Merge_ResidualWins_CountsCorrect()
    {
        var original = new[] { Row(2, -25), Row(3, -22), Row(5, state: CohFallbackState.Known) };
        var residual = new[] { Row(1, -19), Row(2, -18), Row(6, state: CohFallbackState.GatedOut) };

        var m = CohFallbackAudioSelector.Merge(original, residual);

        m.FromOriginal.Should().Be(1, "payload 3 only");
        m.FromResidual.Should().Be(1, "payload 1 only");
        m.InBoth.Should().Be(1, "payload 2");
        var published = CoherentFallbackSelector.Select(m.Rows);
        published.Select(r => r.Payload[0]).Should().BeEquivalentTo(new byte[] { 1, 2, 3 });
        published.Single(r => r.Payload[0] == 2).SnrDb.Should().Be(-18, "the residual row wins");
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO merge: a payload the residual run gated out (not NewGated) is still published from the original run, as fromOriginal")]
    public void Merge_ResidualGatedOut_OriginalPublishes()
    {
        var m = CohFallbackAudioSelector.Merge([Row(4, -24)], [Row(4, state: CohFallbackState.GatedOut)]);
        m.FromOriginal.Should().Be(1);
        m.InBoth.Should().Be(0);
        CoherentFallbackSelector.Select(m.Rows).Single().SnrDb.Should().Be(-24);
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO merge: empty and null inputs")]
    public void Merge_EmptyAndNull()
    {
        var empty = CohFallbackAudioSelector.Merge([], []);
        empty.Rows.Should().BeEmpty();
        (empty.FromOriginal, empty.FromResidual, empty.InBoth).Should().Be((0, 0, 0));

        var onlyOriginal = CohFallbackAudioSelector.Merge([Row(1), Row(2)], null);
        (onlyOriginal.FromOriginal, onlyOriginal.FromResidual, onlyOriginal.InBoth).Should().Be((2, 0, 0));
        CoherentFallbackSelector.Select(onlyOriginal.Rows).Should().HaveCount(2);

        var onlyResidual = CohFallbackAudioSelector.Merge(null, [Row(1)]);
        (onlyResidual.FromOriginal, onlyResidual.FromResidual, onlyResidual.InBoth).Should().Be((0, 1, 0));
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO merge: the same payload twice inside one run still publishes once (edge rule of the selector applies to the merged set)")]
    public void Merge_DuplicateWithinRun_OnePublished()
    {
        var residual = new[] { Row(7, -20, edge: true), Row(7, -21, edge: false) };
        var m = CohFallbackAudioSelector.Merge([Row(7, -30)], residual);
        m.InBoth.Should().Be(1);
        var published = CoherentFallbackSelector.Select(m.Rows);
        published.Should().ContainSingle();
        published[0].Edge.Should().BeFalse("the first non-edge member wins, as in a single run");
        published[0].SnrDb.Should().Be(-21, "and it is the residual one");
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO merge: deterministic - the same inputs give the same rows in the same order, residual before original at one position")]
    public void Merge_Deterministic()
    {
        var o = new[] { Row(1), Row(2) };
        var r = new[] { Row(3), Row(4) };
        var a = CohFallbackAudioSelector.Merge(o, r).Rows.Select(x => x.Payload[0]).ToArray();
        var b = CohFallbackAudioSelector.Merge(o, r).Rows.Select(x => x.Payload[0]).ToArray();
        a.Should().Equal(b);
        a.Should().Equal(new byte[] { 3, 1, 4, 2 });
    }

    [Fact(DisplayName = "FR-100: COH-FB-AUDIO: CombineStats sums the work and times and keeps the candidate counts once; NotRun counts every eligible candidate abandoned")]
    public void Stats_CombineAndNotRun()
    {
        var a = new CohFallbackStats(10, 3, 0, 7, 6, 3, 3, 2, 1, 1, 1, 1.0, 2.0, 3.0, 100.0) { WalkEntered = 4 };
        var b = new CohFallbackStats(10, 3, 0, 7, 7, 4, 4, 3, 2, 0, 0, 1.0, 2.0, 3.0, 50.0) { WalkEntered = 5 };
        var c = CohFallbackAudioSelector.CombineStats(a, b);
        c.Eligible.Should().Be(7);
        c.Candidates.Should().Be(10);
        c.Attempted.Should().Be(13);
        c.Abandoned.Should().Be(1);
        c.TotalMs.Should().Be(150.0);
        c.WalkEntered.Should().Be(9);

        var n = CohFallbackAudioSelector.NotRun(a);
        n.Eligible.Should().Be(7);
        n.Abandoned.Should().Be(7);
        n.Attempted.Should().Be(0);
    }

    // ── COH-GATE-G R-F4: admitting the residual run's GatedOut rows ─────────────────────────────────────────

    private static byte[] Payloads(IEnumerable<CohFallbackRow> rows) => rows.Select(r => r.Payload[0]).ToArray();

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4 merge: setting OFF - a residual GatedOut row is not admitted (the merge is exactly the old one)")]
    public void Merge_Ungated_Off_NothingAdmitted()
    {
        var m = CohFallbackAudioSelector.Merge([Row(2)], [Row(1, state: CohFallbackState.GatedOut), Row(2, state: CohFallbackState.GatedOut)]);

        (m.FromOriginal, m.FromResidual, m.InBoth).Should().Be((1, 0, 0));
        Payloads(CoherentFallbackSelector.Select(m.Rows)).Should().Equal(new byte[] { 2 });
        m.Rows.Should().OnlyContain(r => !r.Admitted);
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4 merge: setting ON - residual GatedOut rows are admitted, keep their true state, and are counted as found by the residual run")]
    public void Merge_Ungated_On_ResidualGatedOutAdmitted_KeepsState()
    {
        var residualIn = new[] { Row(1, -19, state: CohFallbackState.GatedOut), Row(2, -18) };
        var m = CohFallbackAudioSelector.Merge([Row(3, -22)], residualIn, admitResidualGatedOut: true);

        (m.FromOriginal, m.FromResidual, m.InBoth).Should().Be((1, 2, 0));
        var published = CoherentFallbackSelector.Select(m.Rows);
        Payloads(published).OrderBy(b => b).Should().Equal(new byte[] { 1, 2, 3 });
        var admitted = published.Single(r => r.Payload[0] == 1);
        admitted.State.Should().Be(CohFallbackState.GatedOut, "the row is never relabelled NewGated");
        admitted.Admitted.Should().BeTrue();
        published.Single(r => r.Payload[0] == 2).Admitted.Should().BeFalse("a NewGated row is not an admitted one");
        residualIn[0].Admitted.Should().BeFalse("the caller's row is not mutated");
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4 merge: a GatedOut row of the ORIGINAL run is never admitted, and with no residual run nothing is")]
    public void Merge_Ungated_On_OriginalGatedOutNeverAdmitted()
    {
        var m = CohFallbackAudioSelector.Merge([Row(1, state: CohFallbackState.GatedOut), Row(2)], [Row(3)], admitResidualGatedOut: true);
        Payloads(CoherentFallbackSelector.Select(m.Rows)).OrderBy(b => b).Should().Equal(new byte[] { 2, 3 });

        var lone = CohFallbackAudioSelector.Merge([Row(1, state: CohFallbackState.GatedOut), Row(2)], null, admitResidualGatedOut: true);
        Payloads(CoherentFallbackSelector.Select(lone.Rows)).Should().Equal(new byte[] { 2 });
        (lone.FromOriginal, lone.FromResidual, lone.InBoth).Should().Be((1, 0, 0));
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4 merge: an admitted residual row displaces a NewGated original row with the same payload (counted inBoth, residual SNR kept)")]
    public void Merge_Ungated_On_AdmittedResidualDisplacesOriginal()
    {
        var m = CohFallbackAudioSelector.Merge([Row(4, -30)], [Row(4, -17, state: CohFallbackState.GatedOut)], admitResidualGatedOut: true);

        (m.FromOriginal, m.FromResidual, m.InBoth).Should().Be((0, 0, 1));
        var published = CoherentFallbackSelector.Select(m.Rows);
        published.Should().ContainSingle();
        published[0].SnrDb.Should().Be(-17, "the residual row is the one published");
        published[0].State.Should().Be(CohFallbackState.GatedOut);

        // OFF: the old behaviour for the same rows - the original row publishes.
        var off = CohFallbackAudioSelector.Merge([Row(4, -30)], [Row(4, -17, state: CohFallbackState.GatedOut)]);
        CoherentFallbackSelector.Select(off.Rows).Single().SnrDb.Should().Be(-30);
    }

    [Theory(DisplayName = "FR-101: COH-GATE-G R-F4 merge: the edge rule applies across mixed states - the first non-edge member wins")]
    [InlineData(true, true)]
    [InlineData(true, false)]
    [InlineData(false, true)]
    public void Merge_Ungated_On_EdgeRuleAcrossMixedStates(bool firstGatedOut, bool secondGatedOut)
    {
        var first = firstGatedOut ? CohFallbackState.GatedOut : CohFallbackState.NewGated;
        var second = secondGatedOut ? CohFallbackState.GatedOut : CohFallbackState.NewGated;
        var residual = new[] { Row(7, -20, edge: true, state: first), Row(7, -21, edge: false, state: second) };
        var m = CohFallbackAudioSelector.Merge([Row(7, -30)], residual, admitResidualGatedOut: true);

        var published = CoherentFallbackSelector.Select(m.Rows);
        published.Should().ContainSingle();
        published[0].Edge.Should().BeFalse();
        published[0].SnrDb.Should().Be(-21);
        published[0].State.Should().Be(second);
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4 merge: candidate order is by index within the run, residual before original, admitted rows included")]
    public void Merge_Ungated_On_CandidateOrder()
    {
        var m = CohFallbackAudioSelector.Merge([Row(1), Row(2)], [Row(3, state: CohFallbackState.GatedOut), Row(4, state: CohFallbackState.GatedOut)], admitResidualGatedOut: true);
        Payloads(m.Rows).Should().Equal(new byte[] { 3, 1, 4, 2 });
    }
}
