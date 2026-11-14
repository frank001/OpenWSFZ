using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// XC-BUILD (FR-105): a batch-6 template row (<see cref="DecodeResult.PathTemplate"/>) NEVER starts an exchange with a new station: the answerer in Idle does not answer a CQ that only the template stage found,
/// the caller in WaitAnswer does not engage a station that only the template stage found, and both log <c>ignored-template</c>. A template row may still advance an exchange already in progress (WaitReport,
/// WaitRr73). The same message in any other batch behaves as before. Fake clock, synthetic Q-prefix callsigns (NFR-021), every wait on a positive condition (the rigs).
/// </summary>
[Trait("Category", "Unit")]
public sealed class XcTemplateBatchQsoTests
{
    private const string Ours = QsoRigBase.Ours, Partner = QsoRigBase.Partner, PartnerGrid = QsoRigBase.PartnerGrid;
    private const string Noise = "CQ Q2NOISE IO91";
    private const string OtherCq = "CQ Q1OTH FN20";
    private const int TemplateBatchNumber = 6;
    private static readonly string Report = $"{Ours} {Partner} +05";

    private static DecodeResult R(string message, bool template = false)
    {
        var r = QsoRigBase.Make(message, -5);
        return template ? r with { Path = DecodeResult.PathTemplate } : r;
    }

    private static Task Feed(QsoRigBase rig, int cycle, int batchNumber, DateTimeOffset processedAt, params DecodeResult[] rows)
        => rig.FeedAsync(processedAt, new DecodeBatch(Cy.At(cycle), rows.ToList(), batchNumber));

    private static int CountLate(QsoRigBase rig, int batchNumber, string token)
        => rig.LateLines.Count(l => l.Contains($"late batch {batchNumber} {token}"));

    private static DeferredTx? Deferred(QsoRigBase rig) => Peek.Field<DeferredTx?>(rig is AnswererRig a ? a.Sut : ((CallerRig)rig).Sut, "_deferred");

    // ── the token and the enum ─────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD: the late outcome IgnoredTemplate has the token 'ignored-template', and no existing token changed")]
    public void Token_IsPinned_AndTheOthersAreUnchanged()
    {
        LateBatch.Token(LateOutcome.IgnoredTemplate).Should().Be("ignored-template");
        LateBatch.Token(LateOutcome.AppliedImmediate).Should().Be("applied-immediate");
        LateBatch.Token(LateOutcome.AppliedDeferred).Should().Be("applied-deferred");
        LateBatch.Token(LateOutcome.Superseded).Should().Be("superseded");
        LateBatch.Token(LateOutcome.IgnoredStale).Should().Be("ignored-stale");
        LateBatch.Token(LateOutcome.IgnoredAnswered).Should().Be("ignored-answered");
        LateBatch.Token(LateOutcome.NoMatch).Should().Be("no-match");
        Enum.GetValues<LateOutcome>().Select(LateBatch.Token).Should().OnlyHaveUniqueItems();
    }

    // ── answerer, Idle ─────────────────────────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-105: XC-BUILD Q1: a CQ present only in a batch-6 template row starts NOTHING (no transmission, no held answer, still Idle) and logs ignored-template, with time to spare (immediate case) and without (deferred case)")]
    [InlineData(1)]    // S + 1 s: would be answered at once
    [InlineData(5)]    // S + 5 s: too late to start whole, would be held
    public async Task Answerer_TemplateOnlyCq_StartsNothing(int secondsIntoSlot)
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.Batch1Async(0);
        await Feed(rig, 0, TemplateBatchNumber, Cy.At(1).AddSeconds(secondsIntoSlot), R($"CQ {Partner} {PartnerGrid}", template: true));

        rig.Tx.Should().BeEmpty();
        rig.Sut.State.Should().Be(QsoState.Idle);
        rig.Sut.Partner.Should().BeNull();
        Deferred(rig).Should().BeNull("no answer is held");
        CountLate(rig, TemplateBatchNumber, "ignored-template").Should().Be(1);
        CountLate(rig, TemplateBatchNumber, "applied-immediate").Should().Be(0);
        CountLate(rig, TemplateBatchNumber, "applied-deferred").Should().Be(0);

        // and it stays that way: the next batch 1 of the right parity transmits nothing either
        await rig.Batch1Async(2);
        rig.Tx.Should().BeEmpty();
    }

    [Theory(DisplayName = "FR-105: XC-BUILD Q1: the SAME CQ in any other batch still starts the answer (immediate in batch 2, 3, 4 and 5; deferred past the boundary in batch 4): the rule is about the template path, not about late batches")]
    [InlineData(2, 1)]
    [InlineData(3, 1)]
    [InlineData(4, 1)]
    [InlineData(5, 1)]
    [InlineData(4, 5)]
    public async Task Answerer_SameCq_InAnotherLateBatch_StillAnswers(int batchNumber, int secondsIntoSlot)
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.Batch1Async(0);
        await Feed(rig, 0, batchNumber, Cy.At(1).AddSeconds(secondsIntoSlot), R($"CQ {Partner} {PartnerGrid}"));

        if (secondsIntoSlot == 1)
        {
            rig.Tx.Should().ContainSingle().Which.Message.Should().Be($"{Partner} {Ours} JO33");
            CountLate(rig, batchNumber, "applied-immediate").Should().Be(1);
        }
        else
        {
            rig.Tx.Should().BeEmpty();
            Deferred(rig).Should().NotBeNull().And.Match<DeferredTx>(d => d.Kind == DeferredKind.Answer);
            CountLate(rig, batchNumber, "applied-deferred").Should().Be(1);
        }
        CountLate(rig, batchNumber, "ignored-template").Should().Be(0);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD Q1: the same CQ in batch 1 still starts the answer")]
    public async Task Answerer_SameCq_InBatch1_StillAnswers()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.Batch1Async(0, R($"CQ {Partner} {PartnerGrid}"));
        rig.Tx.Should().ContainSingle().Which.Message.Should().Be($"{Partner} {Ours} JO33");
        rig.Sut.State.Should().Be(QsoState.WaitReport);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD Q1: a batch-6 batch with a template CQ and an ordinary CQ (different callsigns), in either order: the answer goes to the ordinary one, and no ignored-template is logged")]
    public async Task Answerer_MixedBatch_AnswersTheNonTemplateRow()
    {
        foreach (bool templateFirst in new[] { true, false })
        {
            await using var rig = await AnswererRig.CreateAsync();
            await rig.Batch1Async(0);
            var template = R($"CQ {Partner} {PartnerGrid}", template: true);
            var ordinary = R(OtherCq);
            await Feed(rig, 0, TemplateBatchNumber, Cy.At(1).AddSeconds(1), templateFirst ? [template, ordinary] : [ordinary, template]);

            rig.Tx.Should().ContainSingle().Which.Message.Should().Be($"Q1OTH {Ours} JO33", "the non-template CQ is answered, whatever its position in the batch");
            rig.Sut.Partner.Should().Be("Q1OTH");
            CountLate(rig, TemplateBatchNumber, "applied-immediate").Should().Be(1);
            CountLate(rig, TemplateBatchNumber, "ignored-template").Should().Be(0);
        }
    }

    // ── answerer, WaitReport: unchanged ────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD Q3: answerer WaitReport: the partner's report present only in a batch-6 template row is handled as in any late batch: the exchange advances (state WaitRr73, the R-report held)")]
    public async Task Answerer_WaitReport_ReportOnlyInBatch6_Advances()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));
        await Feed(rig, 2, TemplateBatchNumber, Cy.At(3).AddSeconds(13.7), R(Report, template: true));

        rig.Sut.State.Should().Be(QsoState.WaitRr73, "a template row advances an exchange already in progress");
        Deferred(rig).Should().NotBeNull().And.Match<DeferredTx>(d => d.Kind == DeferredKind.Report);
        CountLate(rig, TemplateBatchNumber, "applied-deferred").Should().Be(1);
        CountLate(rig, TemplateBatchNumber, "ignored-template").Should().Be(0);
    }

    // ── caller, WaitAnswer ─────────────────────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-105: XC-BUILD Q2: caller WaitAnswer: a reply to our CQ present only in a batch-6 template row does NOT engage the station (no transmission, still waiting, nothing held) and logs ignored-template")]
    [InlineData(1)]
    [InlineData(13)]
    public async Task Caller_TemplateOnlyReply_StartsNothing(int secondsIntoSlot)
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));                         // no answer: CQ repeat in slot 3
        var txBefore = rig.Tx.Count;
        await Feed(rig, 2, TemplateBatchNumber, Cy.At(3).AddSeconds(secondsIntoSlot), R($"{Ours} {Partner} {PartnerGrid}", template: true));

        rig.Tx.Count.Should().Be(txBefore, "nothing transmitted for it");
        rig.Sut.State.Should().Be(QsoState.WaitReport /* the caller's WaitAnswer */);
        rig.Sut.Partner.Should().BeNull();
        Deferred(rig).Should().BeNull();
        CountLate(rig, TemplateBatchNumber, "ignored-template").Should().Be(1);
        CountLate(rig, TemplateBatchNumber, "applied-immediate").Should().Be(0);
        CountLate(rig, TemplateBatchNumber, "applied-deferred").Should().Be(0);
    }

    [Theory(DisplayName = "FR-105: XC-BUILD Q2: caller WaitAnswer: the same reply in batch 4 or 5 (deferred) still engages the station")]
    [InlineData(4)]
    [InlineData(5)]
    public async Task Caller_SameReply_InBatch4Or5_StillEngages(int batchNumber)
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));
        await Feed(rig, 2, batchNumber, Cy.At(3).AddSeconds(13.7), R($"{Ours} {Partner} {PartnerGrid}"));

        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        rig.Sut.Partner.Should().Be(Partner);
        CountLate(rig, batchNumber, "applied-deferred").Should().Be(1);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD Q2: caller: the same reply in batch 1 still engages the station")]
    public async Task Caller_SameReply_InBatch1_StillEngages()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R($"{Ours} {Partner} {PartnerGrid}"));
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        rig.Sut.Partner.Should().Be(Partner);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD Q2: caller: a batch-6 batch with a template reply and an ordinary reply from another station: the ordinary one is engaged")]
    public async Task Caller_MixedBatch_EngagesTheNonTemplateRow()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));
        await Feed(rig, 2, TemplateBatchNumber, Cy.At(3).AddSeconds(13.7),
            R($"{Ours} {Partner} {PartnerGrid}", template: true), R($"{Ours} Q1OTH FN20"));

        rig.Sut.Partner.Should().Be("Q1OTH");
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        CountLate(rig, TemplateBatchNumber, "ignored-template").Should().Be(0);
    }

    // ── the snapshot: the only consumer is the operator-initiated external reply ──────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD: the answerer's idle snapshot (_lastIdleDecodeBatch) still holds a batch-6 CQ, and its ONLY reader is the operator-initiated external Reply, which can engage it (an automatic consumer would have to exclude template rows; there is none)")]
    public async Task Snapshot_KeepsTheTemplateRow_ForTheOperatorsExternalReply()
    {
        await using var rig = await AnswererRig.CreateAsync(autoAnswer: false);
        await rig.Batch1Async(0);
        await Feed(rig, 0, TemplateBatchNumber, Cy.At(1).AddSeconds(1), R("CQ Q1DEF FN20", template: true));

        Peek.Field<DecodeBatch?>(rig.Sut, "_lastIdleDecodeBatch")!.Results.Select(r => r.Message).Should().Contain("CQ Q1DEF FN20");
        (await rig.Sut.TryEngageExternal("Q1DEF")).Should().BeTrue("the operator picked this callsign: that is operator-initiated, unchanged");
        rig.Sut._wakeupChannel.Reader.TryRead(out _);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD: a template CQ in the snapshot is not answered automatically by a later batch 1 either (the auto-answer scan reads batch 1's own rows, never the snapshot)")]
    public async Task Snapshot_TemplateCq_IsNotAutoAnswered_ByALaterBatch1()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.Batch1Async(0);
        await Feed(rig, 0, TemplateBatchNumber, Cy.At(1).AddSeconds(5), R($"CQ {Partner} {PartnerGrid}", template: true));
        await rig.Batch1Async(1);
        await rig.Batch1Async(2);
        rig.Tx.Should().BeEmpty();
        rig.Sut.State.Should().Be(QsoState.Idle);
    }
}
