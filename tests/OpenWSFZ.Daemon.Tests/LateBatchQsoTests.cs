using System.Threading.Channels;
using System.Text.RegularExpressions;
using FluentAssertions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// late-batches-in-qso (the Captain, 2026-10-19: batch 2/3 decodes "should be treated as valid decodes and used in a QSO"),
/// AC2-AC11 of dev-tasks/2026-10-19-late-batches-in-qso.md. AC1 (no supplementary batches = today's behaviour) is
/// <see cref="LateBatchReplayTests"/> plus every pre-existing answerer, caller and pump test. Fake clock, mocked PTT, synthetic
/// Q-prefix callsigns (NFR-021). Every wait is on a positive condition (the batch PROCESSED, via <c>ObservedDecodeChannel</c>).
/// <para>
/// Timeline used throughout: cycle <c>n</c> starts at <c>Cy.At(n)</c>; the slot after it, S = <c>Cy.At(n+1)</c>; a batch 1 is
/// processed at S + 1 s. A late batch is fed with the clock at the time the SERVICE processes it (R3).
/// </para>
/// </summary>
[Trait("Category", "Unit")]
public sealed class LateBatchQsoTests
{
    private const string Ours = QsoRigBase.Ours, Partner = QsoRigBase.Partner, PartnerGrid = QsoRigBase.PartnerGrid;
    private static readonly string Report  = $"{Ours} {Partner} +05";
    private static readonly string Rr73    = $"{Ours} {Partner} RR73";
    private static readonly string Busy    = $"Q1ZZZ {Partner} -10";
    private const string Noise = "CQ Q2NOISE IO91";

    /// <summary>The samples of one whole FT8 transmission: 79 symbols x 160 ms at 48 kHz.</summary>
    private static readonly int FullTxSamples = 79 * (Ft8AudioSynthesiser.SampleRateHz * 160 / 1000);

    private static DecodeResult R(string message, int snr = -5) => QsoRigBase.Make(message, snr);

    private static Task Late(QsoRigBase rig, int cycle, int batchNumber, DateTimeOffset processedAt, params string[] messages)
        => rig.FeedAsync(processedAt, new DecodeBatch(Cy.At(cycle), messages.Select(m => R(m)).ToList(), batchNumber));

    private static string LateLine(int batchNumber, string token) => $"late batch {batchNumber} {token}";

    private static int CountLate(QsoRigBase rig, int batchNumber, string token)
        => rig.LateLines.Count(l => l.Contains(LateLine(batchNumber, token)));

    private static DeferredTx? Deferred(QsoRigBase rig) => Peek.Field<DeferredTx?>(rig is AnswererRig a ? a.Sut : ((CallerRig)rig).Sut, "_deferred");

    /// <summary>Answerer: WaitReport, batch 1 of cycle 2 misses the report (retry in slot 3), then the report arrives in batch 2 of cycle 2 AFTER the retry.</summary>
    private static async Task<AnswererRig> AnswererDeferredReportAsync(int lateBatchNumber = 2)
    {
        var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));                       // no match -> retry in slot 3
        // The retry occupied slot 3 (S = At(3)); the late batch is read when it ends, 13.7 s into the slot.
        await Late(rig, 2, lateBatchNumber, Cy.At(3).AddSeconds(13.7), Report);
        return rig;
    }

    // ═══ AC2: a late batch with no match changes nothing ═══════════════════════════════════════════════════

    [Fact(DisplayName = "AC2: answerer WaitReport — batch 2 and 3 with no match leave retry count, skip guard, watchdog and TX untouched")]
    public async Task Ac2_Answerer_WaitReport_NoMatch_ChangesNothing()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));                      // retry 1; skip guard re-armed
        var (retry, skip, cts, tx) = (rig.RetryCount, rig.SkipNextRetry, rig.TxCts, rig.Tx.Count);
        retry.Should().Be(1); skip.Should().BeTrue();

        await Late(rig, 2, 2, Cy.At(3).AddSeconds(13.7), Noise);
        await Late(rig, 2, 3, Cy.At(3).AddSeconds(14.2), "CQ Q2OTHER FN20");

        rig.RetryCount.Should().Be(retry);
        rig.SkipNextRetry.Should().Be(skip, "a late batch never consumes the first-empty-cycle guard");
        rig.TxCts.Should().BeSameAs(cts, "a late batch never resets the watchdog");
        rig.Tx.Count.Should().Be(tx);
        rig.Sut.State.Should().Be(QsoState.WaitReport);
        Deferred(rig).Should().BeNull();
        CountLate(rig, 2, "no-match").Should().Be(1);
        CountLate(rig, 3, "no-match").Should().Be(1);
    }

    [Fact(DisplayName = "AC2: answerer WaitRr73 — batch 2 and 3 with no match leave retry count, skip guard, watchdog and TX untouched")]
    public async Task Ac2_Answerer_WaitRr73_NoMatch_ChangesNothing()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Report));                     // -> WaitRr73 (R-report sent)
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        var (retry, skip, cts, tx) = (rig.RetryCount, rig.SkipNextRetry, rig.TxCts, rig.Tx.Count);

        await Late(rig, 3, 2, Cy.At(4).AddSeconds(5), Noise);
        await Late(rig, 3, 3, Cy.At(4).AddSeconds(6.5), Noise);

        rig.RetryCount.Should().Be(retry);
        rig.SkipNextRetry.Should().Be(skip);
        rig.TxCts.Should().BeSameAs(cts);
        rig.Tx.Count.Should().Be(tx);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        CountLate(rig, 2, "no-match").Should().Be(1);
        CountLate(rig, 3, "no-match").Should().Be(1);
    }

    [Fact(DisplayName = "AC2: caller WaitAnswer — batch 2 and 3 with no match leave the CQ-repeat count, skip guard, watchdog and TX untouched")]
    public async Task Ac2_Caller_WaitAnswer_NoMatch_ChangesNothing()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));                      // CQ repeat 1; skip guard re-armed
        var (retry, skip, cts, tx) = (rig.RetryCount, rig.SkipNextRetry, rig.TxCts, rig.Tx.Count);
        retry.Should().Be(1); skip.Should().BeTrue();

        await Late(rig, 2, 2, Cy.At(3).AddSeconds(13.7), Noise);
        await Late(rig, 2, 3, Cy.At(3).AddSeconds(14.2), Noise);

        rig.RetryCount.Should().Be(retry);
        rig.SkipNextRetry.Should().Be(skip);
        rig.TxCts.Should().BeSameAs(cts);
        rig.Tx.Count.Should().Be(tx);
        rig.Sut.State.Should().Be(QsoState.WaitReport /* the caller's WaitAnswer */);
        CountLate(rig, 2, "no-match").Should().Be(1);
        CountLate(rig, 3, "no-match").Should().Be(1);
    }

    [Fact(DisplayName = "AC2: caller WaitRr73 — batch 2 and 3 with no match leave retry count, skip guard, watchdog and TX untouched")]
    public async Task Ac2_Caller_WaitRr73_NoMatch_ChangesNothing()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R($"{Ours} {Partner} {PartnerGrid}"));   // answer -> report sent -> WaitRr73
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        var (retry, skip, cts, tx) = (rig.RetryCount, rig.SkipNextRetry, rig.TxCts, rig.Tx.Count);

        await Late(rig, 3, 2, Cy.At(4).AddSeconds(5), Noise);
        await Late(rig, 3, 3, Cy.At(4).AddSeconds(6.5), Noise);

        rig.RetryCount.Should().Be(retry);
        rig.SkipNextRetry.Should().Be(skip);
        rig.TxCts.Should().BeSameAs(cts);
        rig.Tx.Count.Should().Be(tx);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
    }

    // ═══ AC3: the deferred reply ═══════════════════════════════════════════════════════════════════════════

    [Fact(DisplayName = "AC3: answerer — report in batch 2 after the retry: state advances now, nothing in N+1 or N+2, the R-report starts in N+3, retry 0, not a retry")]
    public async Task Ac3_Answerer_DeferredReply_SentInSlotNPlus3()
    {
        await using var rig = await AnswererDeferredReportAsync();

        rig.Tx.Should().HaveCount(2, "answer + the retry in slot N+1; the late batch transmits nothing");
        rig.Sut.State.Should().Be(QsoState.WaitRr73, "the transition is made NOW");
        rig.RetryCount.Should().Be(0, "a matching decode resets the retry count");
        Deferred(rig).Should().NotBeNull().And.Match<DeferredTx>(d => d.Kind == DeferredKind.Report);
        CountLate(rig, 2, "applied-deferred").Should().Be(1);

        await rig.Batch1Async(3);                                // batch 1 of N+1 = our own slot: not a missed response
        rig.Tx.Should().HaveCount(2, "nothing in the rest of N+1");
        rig.RetryCount.Should().Be(0, "a batch 1 of the other parity is not a missed response while a reply is held");
        Deferred(rig).Should().NotBeNull();

        await rig.Batch1Async(4, R(Noise));                      // batch 1 of N+2: the first of the reply's parity
        rig.Tx.Should().HaveCount(3);
        rig.Tx[2].Message.Should().StartWith($"{Partner} {Ours} R", "the R-report held from the late batch");
        rig.Tx[2].At.Should().Be(Cy.Batch1Time(4), "sent when batch 1 of N+2 is processed, i.e. in slot N+3 (starting " + Cy.At(5) + ")");
        rig.RetryCount.Should().Be(0, "sending a held reply is not a retry");
        rig.SkipNextRetry.Should().BeTrue("re-armed after any transmission");
        Deferred(rig).Should().BeNull();
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
    }

    [Fact(DisplayName = "AC3: caller — answer to our CQ in batch 2 after the CQ repeat: report held, sent in slot N+3, retry 0, not a retry")]
    public async Task Ac3_Caller_DeferredReply_SentInSlotNPlus3()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));                      // no answer heard -> CQ repeat in slot 3
        await Late(rig, 2, 2, Cy.At(3).AddSeconds(13.7), $"{Ours} {Partner} {PartnerGrid}");

        rig.Tx.Should().HaveCount(2);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        rig.Sut.Partner.Should().Be(Partner);
        rig.RetryCount.Should().Be(0);
        CountLate(rig, 2, "applied-deferred").Should().Be(1);

        await rig.Batch1Async(3);
        rig.Tx.Should().HaveCount(2);
        await rig.Batch1Async(4, R(Noise));
        rig.Tx.Should().HaveCount(3);
        rig.Tx[2].Message.Should().Be($"{Partner} {Ours} -05");
        rig.RetryCount.Should().Be(0);
        rig.SkipNextRetry.Should().BeTrue();
    }

    // ═══ AC4: immediate reply, and the 2.36 s boundary ═════════════════════════════════════════════════════

    [Fact(DisplayName = "AC4: answerer — batch 2 processed exactly S + 2.36 s on the right parity: transmitted at once, untruncated")]
    public async Task Ac4_Answerer_AtBoundary_Immediate_Untruncated()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();                        // answer sent; skip guard consumed by cycle 1's batch 1
        var s = Cy.At(2);                                        // the slot after cycle 1

        await Late(rig, 1, 2, s + TimeSpan.FromMilliseconds(2360), Report);

        rig.Tx.Should().HaveCount(2);
        rig.Tx[1].Message.Should().StartWith($"{Partner} {Ours} R");
        rig.Tx[1].At.Should().Be(s + TimeSpan.FromMilliseconds(2360));
        rig.AudioLengths[^1].Should().Be(FullTxSamples, "starting at S + 2.36 s still fits a whole signal in the slot");
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        Deferred(rig).Should().BeNull();
        CountLate(rig, 2, "applied-immediate").Should().Be(1);
    }

    [Fact(DisplayName = "AC4: answerer — the same batch 2 at S + 2.37 s is deferred (state advances, no transmission)")]
    public async Task Ac4_Answerer_PastBoundary_Deferred()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        var s = Cy.At(2);

        await Late(rig, 1, 2, s + TimeSpan.FromMilliseconds(2370), Report);

        rig.Tx.Should().HaveCount(1, "only the first answer: nothing is sent past the guard");
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        Deferred(rig).Should().NotBeNull();
        CountLate(rig, 2, "applied-deferred").Should().Be(1);
    }

    [Fact(DisplayName = "AC4: caller — batch 2 at S + 2.36 s: the report is transmitted at once, untruncated; at S + 2.37 s it is deferred")]
    public async Task Ac4_Caller_Boundary_Pair()
    {
        await using (var rig = await CallerRig.CreateAsync())
        {
            await rig.ReachWaitAnswerAsync();
            await Late(rig, 1, 2, Cy.At(2) + TimeSpan.FromMilliseconds(2360), $"{Ours} {Partner} {PartnerGrid}");
            rig.Tx.Should().HaveCount(2);
            rig.AudioLengths[^1].Should().Be(FullTxSamples);
            rig.Sut.State.Should().Be(QsoState.WaitRr73);
            CountLate(rig, 2, "applied-immediate").Should().Be(1);
        }
        await using (var rig = await CallerRig.CreateAsync())
        {
            await rig.ReachWaitAnswerAsync();
            await Late(rig, 1, 2, Cy.At(2) + TimeSpan.FromMilliseconds(2370), $"{Ours} {Partner} {PartnerGrid}");
            rig.Tx.Should().HaveCount(1);
            rig.Sut.State.Should().Be(QsoState.WaitRr73);
            Deferred(rig).Should().NotBeNull();
        }
    }

    // ═══ AC5: a newer message-driven transition supersedes the held reply ══════════════════════════════════

    [Fact(DisplayName = "AC5: answerer — while the R-report is held, batch 1 of N+2 brings RR73: that transition wins, the held R-report is never transmitted")]
    public async Task Ac5_Answerer_Supersede()
    {
        await using var rig = await AnswererDeferredReportAsync();
        await rig.Batch1Async(3);
        await rig.Batch1Async(4, R(Rr73));

        rig.Tx.Should().HaveCount(3);
        rig.Tx[2].Message.Should().Be($"{Partner} {Ours} 73");
        rig.TxMessages.Where(m => m.StartsWith($"{Partner} {Ours} R")).Should().BeEmpty("the held R-report was never sent");
        rig.Sut.State.Should().Be(QsoState.Idle, "RR73 -> 73 -> QSO complete");
        Deferred(rig).Should().BeNull();
        CountLate(rig, 2, "superseded").Should().Be(1);
    }

    [Fact(DisplayName = "AC5: caller — while the report is held, batch 1 of N+2 brings the roger report: RR73 goes out, the held report is never transmitted")]
    public async Task Ac5_Caller_Supersede()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));
        await Late(rig, 2, 2, Cy.At(3).AddSeconds(13.7), $"{Ours} {Partner} {PartnerGrid}");
        await rig.Batch1Async(3);
        await rig.Batch1Async(4, R($"{Ours} {Partner} R-07"));

        rig.Tx.Should().HaveCount(3);
        rig.Tx[2].Message.Should().Be($"{Partner} {Ours} RR73");
        rig.TxMessages.Should().NotContain($"{Partner} {Ours} -05", "the held report was never sent");
        rig.Sut.State.Should().Be(QsoState.Idle);
        CountLate(rig, 2, "superseded").Should().Be(1);
    }

    // ═══ AC6: a CQ found only in a late batch ══════════════════════════════════════════════════════════

    private static async Task<AnswererRig> AnswererLateCqHeldAsync()
    {
        var rig = await AnswererRig.CreateAsync();
        await rig.Batch1Async(0);                                // Idle, nothing heard in the first pass
        var busBefore = rig.Bus.ReceivedCalls().Count();
        await Late(rig, 0, 2, Cy.At(1).AddSeconds(5), $"CQ {Partner} {PartnerGrid}");   // 5 s into the slot: too late to start whole
        rig.Tx.Should().BeEmpty();
        rig.Sut.State.Should().Be(QsoState.Idle, "R2: no state change until the answer is sent");
        rig.Sut.Partner.Should().BeNull();
        rig.Bus.ReceivedCalls().Count().Should().Be(busBefore, "and nothing is broadcast: the UI keeps showing Idle");
        Deferred(rig).Should().NotBeNull().And.Match<DeferredTx>(d => d.Kind == DeferredKind.Answer);
        return rig;
    }

    [Fact(DisplayName = "AC6: answerer, auto-answer on — a CQ only in batch 2 is held (Idle untouched, nothing broadcast) and answered by the first batch 1 of the right parity")]
    public async Task Ac6_Answerer_LateCq_AnsweredInSlotNPlus3()
    {
        await using var rig = await AnswererLateCqHeldAsync();
        await rig.Batch1Async(1);                                // wrong parity: not yet
        rig.Tx.Should().BeEmpty();
        rig.Sut.State.Should().Be(QsoState.Idle);

        await rig.Batch1Async(2);                                // right parity
        rig.Tx.Should().ContainSingle().Which.Message.Should().Be($"{Partner} {Ours} JO33");
        rig.Sut.State.Should().Be(QsoState.WaitReport);
        rig.Sut.Partner.Should().Be(Partner);
        Deferred(rig).Should().BeNull();
        CountLate(rig, 2, "applied-deferred").Should().Be(1);
    }

    [Fact(DisplayName = "AC6: answerer — a CQ only in batch 2 with time to spare (S + 1 s) is answered at once")]
    public async Task Ac6_Answerer_LateCq_Immediate()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.Batch1Async(0);
        await Late(rig, 0, 2, Cy.At(1).AddSeconds(1), $"CQ {Partner} {PartnerGrid}");
        rig.Tx.Should().ContainSingle().Which.Message.Should().Be($"{Partner} {Ours} JO33");
        rig.Sut.State.Should().Be(QsoState.WaitReport);
        CountLate(rig, 2, "applied-immediate").Should().Be(1);
    }

    [Fact(DisplayName = "AC6: answerer — the held late-CQ answer is dropped when an intervening batch shows the CQ station sending to someone else; the service stays Idle")]
    public async Task Ac6_Answerer_LateCq_DroppedWhenStationBusy()
    {
        await using var rig = await AnswererLateCqHeldAsync();
        await rig.Batch1Async(1, R(Busy));                       // Q1TST is calling Q1ZZZ
        Deferred(rig).Should().BeNull();
        CountLate(rig, 2, "superseded").Should().Be(1);

        await rig.Batch1Async(2);
        rig.Tx.Should().BeEmpty();
        rig.Sut.State.Should().Be(QsoState.Idle, "a drop leaves Idle untouched");
    }

    [Fact(DisplayName = "AC6: answerer — an operator-armed pending target that fires first wins; the held late-CQ answer is dropped")]
    public async Task Ac6_Answerer_LateCq_OperatorWins()
    {
        await using var rig = await AnswererLateCqHeldAsync();
        var gate = Peek.Field<object>(rig.Sut, "_stateLock");
        lock (gate)
        {
            // Armed for the B phase, which is the phase of the slot after cycle 2 (:45) — what the held answer was waiting for too.
            SetField(rig.Sut, "_pendingTargetCallsign", "Q1ABC");
            SetField(rig.Sut, "_pendingTargetFrequencyHz", 1200.0);
            SetField(rig.Sut, "_pendingTargetIsAPhase", false);
            SetField(rig.Sut, "_pendingTargetSetAt", DateTimeOffset.UtcNow);
        }

        await rig.Batch1Async(2);

        rig.Tx.Should().ContainSingle().Which.Message.Should().Be($"Q1ABC {Ours} JO33", "the operator's target, not the late CQ");
        rig.Sut.Partner.Should().Be("Q1ABC");
        CountLate(rig, 2, "superseded").Should().Be(1);
    }

    private static void SetField(object target, string name, object value)
        => target.GetType().GetField(name, System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!
                 .SetValue(target, value);

    // ═══ AC7: the partner working someone else, heard in a late batch ═════════════════════════════════════

    [Fact(DisplayName = "AC7: answerer WaitReport — the partner sending to another station in batch 2 aborts exactly as from batch 1")]
    public async Task Ac7_Answerer_WaitReport_Abort()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await Late(rig, 2, 2, Cy.At(3).AddSeconds(5), Busy);
        rig.Sut.State.Should().Be(QsoState.Idle);
        rig.Tx.Should().HaveCount(1);
        CountLate(rig, 2, "applied-immediate").Should().Be(1);
    }

    [Fact(DisplayName = "AC7: answerer WaitRr73 — the same in batch 3")]
    public async Task Ac7_Answerer_WaitRr73_Abort()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Report));
        await Late(rig, 3, 3, Cy.At(4).AddSeconds(6), Busy);
        rig.Sut.State.Should().Be(QsoState.Idle);
        CountLate(rig, 3, "applied-immediate").Should().Be(1);
    }

    [Fact(DisplayName = "AC7: caller WaitRr73 — the partner sending to another station in batch 2 aborts exactly as from batch 1")]
    public async Task Ac7_Caller_WaitRr73_Abort()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R($"{Ours} {Partner} {PartnerGrid}"));
        await Late(rig, 3, 2, Cy.At(4).AddSeconds(5), Busy);
        rig.Sut.State.Should().Be(QsoState.Idle);
        CountLate(rig, 2, "applied-immediate").Should().Be(1);
    }

    // ═══ AC8: the stale and already-answered guards, and the channel ═══════════════════════════════════════

    [Fact(DisplayName = "AC8: answerer — a batch 2 of cycle N read after the batch 1 of N+1 is ignored (ignored-stale)")]
    public async Task Ac8_Answerer_Stale()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));                      // retry 1
        await rig.Batch1Async(3);                                // batch 1 of the later cycle has been processed

        await Late(rig, 2, 2, Cy.At(4).AddSeconds(2), Report);

        rig.Sut.State.Should().Be(QsoState.WaitReport, "the stale report changes nothing");
        rig.RetryCount.Should().Be(1);
        rig.Tx.Should().HaveCount(2);
        CountLate(rig, 2, "ignored-stale").Should().Be(1);
    }

    [Fact(DisplayName = "AC8: answerer — a batch 2 of cycle N after batch 1 of N already caused a transition is ignored (ignored-answered)")]
    public async Task Ac8_Answerer_AlreadyAnswered()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Report));                     // batch 1 found it: R-report sent, WaitRr73
        rig.Tx.Should().HaveCount(2);

        await Late(rig, 2, 2, Cy.At(3).AddSeconds(3), Rr73);     // would be a transition, but the partner sends one message per cycle

        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        rig.Tx.Should().HaveCount(2);
        CountLate(rig, 2, "ignored-answered").Should().Be(1);
    }

    [Fact(DisplayName = "AC8: caller — stale and already-answered guards")]
    public async Task Ac8_Caller_Stale_And_AlreadyAnswered()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R($"{Ours} {Partner} {PartnerGrid}"));   // answered by batch 1
        await Late(rig, 2, 2, Cy.At(3).AddSeconds(3), $"{Ours} {Partner} R-07");
        CountLate(rig, 2, "ignored-answered").Should().Be(1);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);

        await rig.Batch1Async(3);
        await Late(rig, 2, 3, Cy.At(4).AddSeconds(3), $"{Ours} {Partner} R-07");
        CountLate(rig, 3, "ignored-stale").Should().Be(1);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
    }

    /// <summary>The production channel: 3 batches per cycle, the service blocked for a transmission of every own slot.</summary>
    private static (int Dropped, List<int> Batch1CyclesRead) RunChannel(Channel<DecodeBatch> ch, int cycles)
    {
        var read = new List<int>();
        for (var cycle = 0; cycle < cycles; cycle++)
        {
            ch.Writer.TryWrite(new DecodeBatch(Cy.At(cycle), [], 1));
            ch.Writer.TryWrite(new DecodeBatch(Cy.At(cycle), [], 2));
            ch.Writer.TryWrite(new DecodeBatch(Cy.At(cycle), [], 3));
            // The service is blocked in its transmission during every own slot (every other cycle); it reads only when it ends.
            if (cycle % 2 == 1)
                while (ch.Reader.TryRead(out var b))
                    if (b.BatchNumber == 1) read.Add((int)((b.CycleStart - Cy.T0).TotalSeconds / 15));
        }
        return (cycles - read.Count, read);
    }

    [Fact(DisplayName = "AC8: channel — capacity 8 (3 batches x 2 cycles + 2) for the answerer and caller; 3 batches a cycle for 4 cycles with a blocking transmission each own slot drops no batch 1")]
    public void Ac8_Channel_Capacity8_DropsNoBatch1()
    {
        LateBatch.QsoChannelCapacity.Should().Be(8);
        LateBatch.QsoChannelCapacity.Should().BeGreaterThanOrEqualTo(3 * 2 + 2, "two cycles of three batches queue while one transmission blocks the service, plus two spare");

        var (_, batch1s) = RunChannel(LateBatch.CreateQsoChannel(), cycles: 4);

        batch1s.Should().Equal([0, 1, 2, 3], "every cycle's batch 1 reached the service");
    }

    [Fact(DisplayName = "AC8: channel — control: at the old capacity of 2 the same schedule loses batch 1s")]
    public void Ac8_Channel_OldCapacity2_LosesBatch1()
    {
        var old = Channel.CreateBounded<DecodeBatch>(new BoundedChannelOptions(2)
        {
            FullMode = BoundedChannelFullMode.DropOldest, SingleWriter = true, SingleReader = true,
        });

        var (dropped, _) = RunChannel(old, cycles: 4);

        dropped.Should().BeGreaterThan(0, "this is why the capacity was raised");
    }

    // ═══ AC9: the answerer's one-cycle snapshot ════════════════════════════════════════════════════════════

    private static IReadOnlyList<string> SnapshotMessages(AnswererRig rig)
        => Peek.Field<DecodeBatch?>(rig.Sut, "_lastIdleDecodeBatch")?.Results.Select(r => r.Message).ToList() ?? [];

    [Fact(DisplayName = "AC9: answerer snapshot — batch 2 of the same cycle appends, a newer batch 1 replaces, a batch 2 of an older cycle is dropped")]
    public async Task Ac9_Snapshot_Merge_Replace_Drop()
    {
        await using var rig = await AnswererRig.CreateAsync(autoAnswer: false);
        await rig.Batch1Async(0, R("CQ Q1ABC IO91"));
        await Late(rig, 0, 2, Cy.At(1).AddSeconds(4), "CQ Q1DEF FN20");
        await Late(rig, 0, 3, Cy.At(1).AddSeconds(5.5), "CQ Q1GHI EM12");
        SnapshotMessages(rig).Should().Equal("CQ Q1ABC IO91", "CQ Q1DEF FN20", "CQ Q1GHI EM12");

        await rig.Batch1Async(1, R("CQ Q1JKL JN58"));
        SnapshotMessages(rig).Should().Equal(["CQ Q1JKL JN58"], "a batch 1 of a newer cycle replaces the snapshot");

        await Late(rig, 0, 2, Cy.At(2).AddSeconds(4), "CQ Q1MNO IO70");
        SnapshotMessages(rig).Should().Equal(["CQ Q1JKL JN58"], "a batch 2 of an OLDER cycle does not change it");
        CountLate(rig, 2, "ignored-stale").Should().Be(1);
    }

    [Fact(DisplayName = "AC9: TryEngageExternal accepts a reply naming a station found only in batch 2 (and one in batch 1)")]
    public async Task Ac9_TryEngageExternal_AcceptsBatch2Station()
    {
        await using var rig = await AnswererRig.CreateAsync(autoAnswer: false);
        await rig.Batch1Async(0, R("CQ Q1ABC IO91"));
        await Late(rig, 0, 2, Cy.At(1).AddSeconds(4), "CQ Q1DEF FN20");

        (await rig.Sut.TryEngageExternal("Q1DEF")).Should().BeTrue("a station heard only in the residual pass is a valid decode");
        rig.Sut._wakeupChannel.Reader.TryRead(out _);
    }

    [Fact(DisplayName = "AC9: TryEngageExternal still accepts the batch-1 station after batch 2 was merged")]
    public async Task Ac9_TryEngageExternal_AcceptsBatch1StationToo()
    {
        await using var rig = await AnswererRig.CreateAsync(autoAnswer: false);
        await rig.Batch1Async(0, R("CQ Q1ABC IO91"));
        await Late(rig, 0, 2, Cy.At(1).AddSeconds(4), "CQ Q1DEF FN20");

        (await rig.Sut.TryEngageExternal("Q1ABC")).Should().BeTrue();
        rig.Sut._wakeupChannel.Reader.TryRead(out _);
    }

    // ═══ AC10: one log line per decision, one token, no message text, no callsign ═════════════════════════

    private static readonly Regex LateLineShape = new(@"late batch (?<n>[23]) (?<t>applied-immediate|applied-deferred|superseded|ignored-stale|ignored-answered|no-match)\.$");

    private static void ExactlyOneLine(QsoRigBase rig, int batchNumber, string token)
    {
        var lines = rig.LateLines.Where(l => l.Contains(LateLine(batchNumber, token))).ToList();
        lines.Should().ContainSingle($"exactly one '{LateLine(batchNumber, token)}' line");
        LateLineShape.IsMatch(lines[0]).Should().BeTrue("the line is the batch number plus one token and nothing else");
        lines[0].Should().NotContain("Q1", "no callsign in an AC10 line (HK-037 / NFR-021)");
        lines[0].Should().NotContain("CQ").And.NotContain("RR73", "no message text in an AC10 line");
    }

    [Fact(DisplayName = "AC10: token applied-immediate is logged once with its batch number")]
    public async Task Ac10_AppliedImmediate()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await Late(rig, 1, 3, Cy.At(2).AddSeconds(1), Report);
        ExactlyOneLine(rig, 3, "applied-immediate");
    }

    [Fact(DisplayName = "AC10: token applied-deferred is logged once with its batch number")]
    public async Task Ac10_AppliedDeferred()
    {
        await using var rig = await AnswererDeferredReportAsync(lateBatchNumber: 3);
        ExactlyOneLine(rig, 3, "applied-deferred");
    }

    [Fact(DisplayName = "AC10: token superseded is logged once, against the batch that created the held reply")]
    public async Task Ac10_Superseded()
    {
        await using var rig = await AnswererDeferredReportAsync();
        await rig.Batch1Async(3);
        await rig.Batch1Async(4, R(Rr73));
        ExactlyOneLine(rig, 2, "superseded");
    }

    [Fact(DisplayName = "AC10: token ignored-stale is logged once with its batch number")]
    public async Task Ac10_IgnoredStale()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));
        await rig.Batch1Async(3);
        await Late(rig, 2, 3, Cy.At(4).AddSeconds(2), Report);
        ExactlyOneLine(rig, 3, "ignored-stale");
    }

    [Fact(DisplayName = "AC10: token ignored-answered is logged once with its batch number")]
    public async Task Ac10_IgnoredAnswered()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Report));
        await Late(rig, 2, 3, Cy.At(3).AddSeconds(3), Rr73);
        ExactlyOneLine(rig, 3, "ignored-answered");
    }

    [Fact(DisplayName = "AC10: token no-match is logged once with its batch number")]
    public async Task Ac10_NoMatch()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await Late(rig, 1, 2, Cy.At(2).AddSeconds(4), Noise);
        ExactlyOneLine(rig, 2, "no-match");
    }

    [Fact(DisplayName = "AC10: every late batch yields exactly one decision line (plus one per superseded held reply), in both services")]
    public async Task Ac10_EveryLateBatch_OneLine()
    {
        await using var a = await AnswererRig.CreateAsync();
        await a.ReachWaitReportAsync();                          // WaitReport
        await Late(a, 1, 2, Cy.At(2).AddSeconds(4), Noise);      // no-match
        await Late(a, 1, 3, Cy.At(2).AddSeconds(5), Report);     // applied-deferred
        a.LateLines.Should().HaveCount(2);

        await using var c = await CallerRig.CreateAsync();
        await c.ReachWaitAnswerAsync();
        await Late(c, 1, 2, Cy.At(2).AddSeconds(4), Noise);      // no-match
        await Late(c, 1, 3, Cy.At(2).AddSeconds(5), $"{Ours} {Partner} {PartnerGrid}");   // applied-deferred
        c.LateLines.Should().HaveCount(2);
        c.LateLines.Should().OnlyContain(l => LateLineShape.IsMatch(l));
    }

    // ═══ AC11: the partner repeats the identical report in N+2 ═════════════════════════════════════════════

    [Fact(DisplayName = "AC11 (R1): answerer — late transition on the partner's report, the partner repeats the identical report in N+2: exactly ONE R-report, in N+3, retry count 0")]
    public async Task Ac11_Answerer_RepeatedReport_OneTransmission()
    {
        await using var rig = await AnswererDeferredReportAsync();
        await rig.Batch1Async(3);
        await rig.Batch1Async(4, R(Report));                     // the same report again

        rig.TxMessages.Where(m => m.StartsWith($"{Partner} {Ours} R")).Should().ContainSingle("exactly one R-report");
        rig.Tx.Should().HaveCount(3);
        rig.Tx[2].At.Should().Be(Cy.Batch1Time(4));
        rig.RetryCount.Should().Be(0);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        CountLate(rig, 2, "superseded").Should().Be(0, "a repeat that causes no transition does not supersede the held reply");
    }

    [Fact(DisplayName = "AC11 (R1): caller — the responder repeats its answer in N+2: exactly ONE report, in N+3, retry count 0")]
    public async Task Ac11_Caller_RepeatedAnswer_OneTransmission()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R(Noise));
        await Late(rig, 2, 2, Cy.At(3).AddSeconds(13.7), $"{Ours} {Partner} {PartnerGrid}");
        await rig.Batch1Async(3);
        await rig.Batch1Async(4, R($"{Ours} {Partner} {PartnerGrid}"));

        rig.TxMessages.Where(m => m == $"{Partner} {Ours} -05").Should().ContainSingle();
        rig.Tx.Should().HaveCount(3);
        rig.RetryCount.Should().Be(0);
    }

    // ═══ Closing messages (RR73 / 73) found only in a late batch ═══════════════════════════════════════════

    [Fact(DisplayName = "Late RR73: answerer WaitRr73 — RR73 in a late batch past the guard is held; the next batch 1 of its parity sends 73 and the QSO completes")]
    public async Task LateClosing_Answerer_Deferred73()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Report));                     // R-report sent, WaitRr73
        await rig.Batch1Async(3);                                // our own slot
        await rig.Batch1Async(4, R(Noise));                      // the partner's RR73 was missed: R-report retried in slot 5
        await Late(rig, 4, 2, Cy.At(5).AddSeconds(13.7), Rr73); // found in batch 2 once the retry ended
        rig.Tx.Should().HaveCount(3);
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        CountLate(rig, 2, "applied-deferred").Should().Be(1);

        await rig.Batch1Async(5);                                // our own slot again: not the reply's parity
        rig.Tx.Should().HaveCount(3);

        await rig.Batch1Async(6, R(Noise));
        rig.TxMessages[^1].Should().Be($"{Partner} {Ours} 73");
        rig.Tx.Should().HaveCount(4);
        rig.Sut.State.Should().Be(QsoState.Idle, "73 sent: QSO complete");
    }

    [Fact(DisplayName = "Late RR73: caller WaitRr73 — the roger report in an immediate late batch sends RR73 at once and completes the QSO")]
    public async Task LateClosing_Caller_ImmediateRr73()
    {
        await using var rig = await CallerRig.CreateAsync();
        await rig.ReachWaitAnswerAsync();
        await rig.Batch1Async(2, R($"{Ours} {Partner} {PartnerGrid}"));   // report sent, WaitRr73
        await rig.Batch1Async(3);
        await Late(rig, 4, 2, Cy.At(5).AddSeconds(1.5), $"{Ours} {Partner} R-07");
        rig.TxMessages[^1].Should().Be($"{Partner} {Ours} RR73");
        rig.Sut.State.Should().Be(QsoState.Idle);
        CountLate(rig, 2, "applied-immediate").Should().Be(1);
    }

    // ═══ Pump → services: the numbered batches reach them ═════════════════════════════════════════════════

    [Fact(DisplayName = "DecodeBatch: BatchNumber defaults to 1, so every existing constructor call is a batch 1")]
    public void DecodeBatch_DefaultsToBatch1()
        => new DecodeBatch(Cy.T0, []).BatchNumber.Should().Be(1);

    [Fact(DisplayName = "LateBatch: the guard is exactly 15 s - 12.64 s = 2.36 s")]
    public void LateBatch_Guard_IsExactly2360Ms()
    {
        LateBatch.LatestWholeStart.Should().Be(TimeSpan.FromMilliseconds(2360));
        LateBatch.CanStartWhole(Cy.At(1).AddMilliseconds(2360), Cy.At(0)).Should().BeTrue();
        LateBatch.CanStartWhole(Cy.At(1).AddMilliseconds(2361), Cy.At(0)).Should().BeFalse();
    }
}
