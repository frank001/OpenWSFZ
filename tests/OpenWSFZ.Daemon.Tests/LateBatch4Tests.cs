using System.Threading.Channels;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// COH-FALLBACK step 4, R14 (spec section 14): the coherent fallback's own batch (4 on Deep) must reach the QSO services and the panel.
/// (1) The QSO queue carries up to 4 batches per cycle with the flag ON, and is EXACTLY the old bounded DropOldest channel of 8 with the flag
/// OFF (R13). (2) Batch 4 is handled by the answerer and the caller exactly as any late batch: same latest-whole-signal guard, same deferral,
/// same log tokens, same order. (3) The pump hands the staged entry's batch 4 to the panel, ALL.TXT, filter admission, external reporting
/// and both QSO channels, numbered 4; and on the Normal depth the staged entry is used when the fallback flag is on.
///
/// <para>Fake clock, synthetic Q-prefix callsigns (NFR-021). Every wait is on a positive condition (the batch PROCESSED, via the rigs).</para>
/// </summary>
[Trait("Category", "Unit")]
public sealed class LateBatch4Tests
{
    private const string Ours = QsoRigBase.Ours, Partner = QsoRigBase.Partner, PartnerGrid = QsoRigBase.PartnerGrid;
    private static readonly string Report = $"{Ours} {Partner} +05";
    private const string Noise = "CQ Q2NOISE IO91";

    private static DecodeResult R(string message, int snr = -5) => QsoRigBase.Make(message, snr);

    private static Task Late(QsoRigBase rig, int cycle, int batchNumber, DateTimeOffset processedAt, params string[] messages)
        => rig.FeedAsync(processedAt, new DecodeBatch(Cy.At(cycle), messages.Select(m => R(m)).ToList(), batchNumber));

    private static int CountLate(QsoRigBase rig, int batchNumber, string token)
        => rig.LateLines.Count(l => l.Contains($"late batch {batchNumber} {token}"));

    private static DeferredTx? Deferred(QsoRigBase rig)
        => Peek.Field<DeferredTx?>(rig is AnswererRig a ? a.Sut : ((CallerRig)rig).Sut, "_deferred");

    // ═══ the capacity arithmetic ═════════════════════════════════════════════════════════════════════════════

    [Fact(DisplayName = "R14: capacity arithmetic - batches x 2 cycles + 2 spare: 3 batches = 8 (flag OFF, unchanged), 4 batches = 10 (flag ON)")]
    public void Capacity_Arithmetic()
    {
        LateBatch.QsoCapacityFor(LateBatch.BatchesPerCycleFallbackOff).Should().Be(8).And.Be(LateBatch.QsoChannelCapacity);
        LateBatch.QsoCapacityFor(LateBatch.BatchesPerCycleFallbackOn).Should().Be(10).And.Be(LateBatch.QsoChannelCapacityFallbackOn);
        (LateBatch.BatchesPerCycleFallbackOff, LateBatch.BatchesPerCycleFallbackOn, LateBatch.QsoCyclesQueued, LateBatch.QsoChannelSpare).Should().Be((3, 4, 2, 2));
    }

    // ═══ the queue ═══════════════════════════════════════════════════════════════════════════════════════════

    private static DecodeBatch B(int cycle, int batch) => new(Cy.At(cycle), [], batch);

    private static string Tag(DecodeBatch b) => $"{(int)((b.CycleStart - Cy.T0).TotalSeconds / 15)}.{b.BatchNumber}";

    private static List<string> ReadAll(ChannelReader<DecodeBatch> r)
    {
        var l = new List<string>();
        while (r.TryRead(out var b)) l.Add(Tag(b));
        return l;
    }

    [Theory(DisplayName = "R13/R14: flag OFF - the queue behaves exactly as the old bounded DropOldest channel of 8, for many seeded write/read schedules (overflow included)")]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(5)]
    [InlineData(6)]
    public void FlagOff_IsExactlyTheOldChannel(int seed)
    {
        var old = LateBatch.CreateQsoChannel();
        var queue = LateBatch.CreateQsoQueue(() => false);
        var rng = new Random(seed);
        var seenOld = new List<string>();
        var seenNew = new List<string>();
        for (int step = 0; step < 400; step++)
        {
            var b = B(step, 1 + rng.Next(0, 4));   // batch numbers 1..4 are all just batches to the queue
            var wOld = old.Writer.TryWrite(b);
            var wNew = queue.Writer.TryWrite(b);
            wNew.Should().Be(wOld);
            int reads = rng.Next(0, 12) == 0 ? rng.Next(1, 12) : 0;   // mostly writes, now and then a drain of some depth
            for (int i = 0; i < reads; i++)
            {
                var gotOld = old.Reader.TryRead(out var ro);
                var gotNew = queue.Reader.TryRead(out var rn);
                gotNew.Should().Be(gotOld);
                if (gotOld) { seenOld.Add(Tag(ro!)); seenNew.Add(Tag(rn!)); }
            }
            queue.Reader.Count.Should().Be(old.Reader.Count, "same depth after every step (seed {0}, step {1})", seed, step);
        }
        seenNew.Should().Equal(seenOld, "the same batches, in the same order, with the same drops");
        ReadAll(queue.Reader).Should().Equal(ReadAll(old.Reader));
        queue.EffectiveCapacity.Should().Be(8);
    }

    [Fact(DisplayName = "R14: flag ON - a service blocked in transmissions while 4 batches a cycle arrive for 4 cycles loses no batch 1; every batch read is in write order")]
    public void FlagOn_FourBatchesPerCycle_DropsNoBatch1()
    {
        var queue = LateBatch.CreateQsoQueue(() => true);
        var read = new List<DecodeBatch>();
        for (int cycle = 0; cycle < 4; cycle++)
        {
            for (int n = 1; n <= 4; n++) queue.Writer.TryWrite(B(cycle, n));
            // blocked in its transmission during every own slot (every other cycle); it reads only when that ends
            if (cycle % 2 == 1)
                while (queue.Reader.TryRead(out var b)) read.Add(b);
        }

        read.Where(b => b.BatchNumber == 1).Select(b => (int)((b.CycleStart - Cy.T0).TotalSeconds / 15)).Should().Equal(0, 1, 2, 3);
        read.Count.Should().Be(16, "no batch of any number was dropped");
        read.Select(Tag).Should().Equal(Enumerable.Range(0, 4).SelectMany(c => Enumerable.Range(1, 4).Select(n => $"{c}.{n}")), "write order kept");
    }

    [Fact(DisplayName = "R14: control - with 4 batches a cycle, two cycles queued fill the flag-OFF capacity of 8 exactly: the next cycle's batch 1 drops cycle 0's batch 1 at 8, not at 10 (why the capacity follows the flag)")]
    public void FourBatchesPerCycle_TwoCyclesFillEight_NoSpare()
    {
        List<string> Run(bool flagOn)
        {
            var queue = LateBatch.CreateQsoQueue(() => flagOn);
            for (int cycle = 0; cycle < 2; cycle++)
                for (int n = 1; n <= 4; n++) queue.Writer.TryWrite(B(cycle, n));
            queue.Writer.TryWrite(B(2, 1));   // the service is still blocked in its transmission when the next cycle's batch 1 arrives
            return ReadAll(queue.Reader);
        }

        Run(flagOn: false).Should().NotContain("0.1", "at 8 the oldest batch 1 is gone");
        Run(flagOn: true).Should().Contain("0.1").And.HaveCount(9, "at 10 the spare slots absorb it");
    }

    [Fact(DisplayName = "R14: the effective capacity follows the flag at run time - ON holds 10, the 11th write drops the OLDEST; OFF again trims to 8 on the next write")]
    public void Capacity_FollowsTheFlag()
    {
        bool on = true;
        var queue = LateBatch.CreateQsoQueue(() => on);
        for (int i = 0; i < 10; i++) queue.Writer.TryWrite(B(i, 1));
        queue.Reader.Count.Should().Be(10);
        queue.Writer.TryWrite(B(10, 1));
        queue.Reader.Count.Should().Be(10);
        queue.Reader.TryPeek(out var oldest).Should().BeTrue();
        Tag(oldest!).Should().Be("1.1", "the oldest (cycle 0) was dropped");

        on = false;
        queue.Writer.TryWrite(B(11, 1));
        queue.Reader.Count.Should().Be(8, "flag OFF: the old capacity is back as soon as the next batch is written");
        ReadAll(queue.Reader).Should().Equal(Enumerable.Range(4, 8).Select(c => $"{c}.1"), "the newest 8 survive, in order");
    }

    [Fact(DisplayName = "R14: the queue's writer completes the channel and reports readiness like a channel writer")]
    public async Task Writer_CompleteAndWaitToWrite()
    {
        var queue = LateBatch.CreateQsoQueue(() => false);
        (await queue.Writer.WaitToWriteAsync()).Should().BeTrue();
        queue.Writer.TryComplete().Should().BeTrue();
        (await queue.Reader.WaitToReadAsync()).Should().BeFalse("completed and empty");
    }

    // ═══ the QSO services: batch 4 exactly as any late batch ═════════════════════════════════════════════════

    [Fact(DisplayName = "R14: answerer - a report in batch 4 after the retry: state advances now, the R-report is held and sent in slot N+3, logged once as 'late batch 4 applied-deferred'")]
    public async Task Answerer_Batch4_DeferredReply()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));
        await Late(rig, 2, 4, Cy.At(3).AddSeconds(14.5), Report);

        rig.Tx.Should().HaveCount(2, "the late batch transmits nothing");
        rig.Sut.State.Should().Be(QsoState.WaitRr73);
        Deferred(rig).Should().NotBeNull().And.Match<DeferredTx>(d => d.Kind == DeferredKind.Report && d.BatchNumber == 4);
        CountLate(rig, 4, "applied-deferred").Should().Be(1);

        await rig.Batch1Async(3);
        rig.Tx.Should().HaveCount(2);
        await rig.Batch1Async(4, R(Noise));
        rig.Tx.Should().HaveCount(3);
        rig.Tx[2].Message.Should().StartWith($"{Partner} {Ours} R");
        rig.RetryCount.Should().Be(0);
        Deferred(rig).Should().BeNull();
    }

    [Fact(DisplayName = "R14: answerer - batch 4 at S + 2.36 s is transmitted at once, untruncated; at S + 2.37 s it is deferred (the guard is the same as for batches 2 and 3)")]
    public async Task Answerer_Batch4_GuardBoundary()
    {
        await using (var rig = await AnswererRig.CreateAsync())
        {
            await rig.ReachWaitReportAsync();
            await Late(rig, 1, 4, Cy.At(2) + TimeSpan.FromMilliseconds(2360), Report);
            rig.Tx.Should().HaveCount(2);
            rig.Tx[1].Message.Should().StartWith($"{Partner} {Ours} R");
            rig.Sut.State.Should().Be(QsoState.WaitRr73);
            CountLate(rig, 4, "applied-immediate").Should().Be(1);
        }
        await using (var rig = await AnswererRig.CreateAsync())
        {
            await rig.ReachWaitReportAsync();
            await Late(rig, 1, 4, Cy.At(2) + TimeSpan.FromMilliseconds(2370), Report);
            rig.Tx.Should().HaveCount(1);
            Deferred(rig).Should().NotBeNull();
            CountLate(rig, 4, "applied-deferred").Should().Be(1);
        }
    }

    [Fact(DisplayName = "R14: answerer - batch 4 with no match changes nothing (retry count, skip guard, watchdog, TX) and counts as 'no-match' once")]
    public async Task Answerer_Batch4_NoMatch_ChangesNothing()
    {
        await using var rig = await AnswererRig.CreateAsync();
        await rig.ReachWaitReportAsync();
        await rig.Batch1Async(2, R(Noise));
        var (retry, skip, cts, tx) = (rig.RetryCount, rig.SkipNextRetry, rig.TxCts, rig.Tx.Count);

        await Late(rig, 2, 4, Cy.At(3).AddSeconds(14.8), "CQ Q2OTHER FN20");

        rig.RetryCount.Should().Be(retry);
        rig.SkipNextRetry.Should().Be(skip);
        rig.TxCts.Should().BeSameAs(cts);
        rig.Tx.Count.Should().Be(tx);
        Deferred(rig).Should().BeNull();
        CountLate(rig, 4, "no-match").Should().Be(1);
    }

    [Fact(DisplayName = "R14: caller - an answer in batch 4 after the CQ repeat: held, sent in slot N+3; at S + 2.36 s immediate, at S + 2.37 s deferred")]
    public async Task Caller_Batch4_Deferral_And_Guard()
    {
        await using (var rig = await CallerRig.CreateAsync())
        {
            await rig.ReachWaitAnswerAsync();
            await rig.Batch1Async(2, R(Noise));
            await Late(rig, 2, 4, Cy.At(3).AddSeconds(14.5), $"{Ours} {Partner} {PartnerGrid}");
            rig.Tx.Should().HaveCount(2);
            rig.Sut.State.Should().Be(QsoState.WaitRr73);
            Deferred(rig).Should().NotBeNull().And.Match<DeferredTx>(d => d.BatchNumber == 4);
            await rig.Batch1Async(3);
            await rig.Batch1Async(4, R(Noise));
            rig.Tx.Should().HaveCount(3);
            rig.Tx[2].Message.Should().Be($"{Partner} {Ours} -05");
        }
        await using (var rig = await CallerRig.CreateAsync())
        {
            await rig.ReachWaitAnswerAsync();
            await Late(rig, 1, 4, Cy.At(2) + TimeSpan.FromMilliseconds(2360), $"{Ours} {Partner} {PartnerGrid}");
            rig.Tx.Should().HaveCount(2);
            CountLate(rig, 4, "applied-immediate").Should().Be(1);
        }
        await using (var rig = await CallerRig.CreateAsync())
        {
            await rig.ReachWaitAnswerAsync();
            await Late(rig, 1, 4, Cy.At(2) + TimeSpan.FromMilliseconds(2370), $"{Ours} {Partner} {PartnerGrid}");
            rig.Tx.Should().HaveCount(1);
            Deferred(rig).Should().NotBeNull();
        }
    }

    // ═══ the pump: batch 4 reaches every sink, numbered 4 ════════════════════════════════════════════════════

    private static readonly DateTime Cycle1 = new(2026, 9, 30, 12, 0, 0, DateTimeKind.Utc);

    private static DecodeResult Rs(string message, int freq = 1500)
        => new(Time: "12:00:00", Snr: -10, Dt: 0.2, FreqHz: freq, Message: message);

    private sealed class PumpRig
    {
        public readonly List<IReadOnlyList<DecodeResult>> Panel = [];
        public readonly List<IReadOnlyList<DecodeResult>> AllTxt = [];
        public readonly List<string> Admitted = [];
        public readonly Channel<DecodeBatch> Answerer = Channel.CreateUnbounded<DecodeBatch>();
        public readonly Channel<DecodeBatch> Caller = Channel.CreateUnbounded<DecodeBatch>();
        public readonly Channel<DecodeBatch> External = Channel.CreateUnbounded<DecodeBatch>();
        public bool Deep, FallbackOn, HasFallbackDelegate = true;
        public int StagedCalls, TwoStageCalls;
        public Func<Func<int, IReadOnlyList<DecodeResult>, Task>, Task>? Staged;

        public DecodePump Build() => new(new DecodePumpDependencies(
            CurrentDialFrequency:     () => 14.074,
            FallbackDialFrequency:    () => 0.0,
            DeriveBand:               _ => "20m",
            SubtractionEnabled:       () => true,
            DecodeSingleBatch:        (_, _, _, _) => Task.FromResult<IReadOnlyList<DecodeResult>>([]),
            DecodeTwoStage:           async (_, _, _, publishFirst, _) =>
            {
                TwoStageCalls++;
                await publishFirst([Rs("CQ Q1ABC JO33")]);
                return [];
            },
            ApplyNoiseSuppression:    r => r,
            PublishToPanel:           r => { lock (Panel) Panel.Add(r); return Task.CompletedTask; },
            AppendAllTxt:             (_, _, r) => { lock (AllTxt) AllTxt.Add(r); return Task.CompletedTask; },
            EnqueueArchive:           (_, _, _, _, _) => { },
            AdmitNewValues:           r => { lock (Admitted) Admitted.Add(r.Message); return null; },
            PublishFilterState:       _ => { },
            AnswererChannel:          Answerer.Writer,
            CallerChannel:            Caller.Writer,
            ExternalReportingChannel: External.Writer,
            Logger:                   Microsoft.Extensions.Logging.Abstractions.NullLogger.Instance)
        {
            DecodeStaged = async (_, _, _, publishBatch, _) => { StagedCalls++; await Staged!(publishBatch); },
            DecodingDeep = () => Deep,
            CoherentFallbackOn = HasFallbackDelegate ? () => FallbackOn : null,
        });

        public static async IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> Windows(params DateTime[] cycles)
        {
            foreach (var c in cycles) yield return (new float[180_000], c, 14.074);
            await Task.CompletedTask;
        }

        public static List<DecodeBatch> Drain(Channel<DecodeBatch> ch)
        {
            var l = new List<DecodeBatch>();
            while (ch.Reader.TryRead(out var b)) l.Add(b);
            return l;
        }
    }

    [Fact(DisplayName = "R14: Deep - the staged entry's batch 4 reaches the panel, ALL.TXT, filter admission, external reporting and both QSO channels, numbered 4, in order after batch 3")]
    public async Task Pump_Batch4_ReachesEverySink()
    {
        var rig = new PumpRig { Deep = true, FallbackOn = true };
        rig.Staged = async publish =>
        {
            await publish(1, [Rs("CQ Q1ABC JO33")]);
            await publish(2, [Rs("CQ Q1DEF EN37", 2100)]);
            await publish(3, [Rs("CQ Q1GHI IO91", 2400)]);
            await publish(4, [Rs("CQ Q1JKL FN20", 2700)]);
        };

        await rig.Build().RunAsync(PumpRig.Windows(Cycle1), CancellationToken.None);

        var answerer = PumpRig.Drain(rig.Answerer);
        var caller = PumpRig.Drain(rig.Caller);
        var external = PumpRig.Drain(rig.External);
        answerer.Select(b => b.BatchNumber).Should().Equal(1, 2, 3, 4);
        caller.Select(b => b.BatchNumber).Should().Equal(1, 2, 3, 4);
        external.Select(b => b.BatchNumber).Should().Equal(1, 2, 3, 4);
        answerer[3].Results.Select(r => r.Message).Should().Equal("CQ Q1JKL FN20");
        answerer.Select(b => b.CycleStart).Distinct().Should().ContainSingle("all four are batches of the same cycle");
        rig.Panel.Select(p => p.Count).Should().Equal(1, 1, 1, 1);
        rig.AllTxt.Select(p => p.Single().Message).Should().Equal("CQ Q1ABC JO33", "CQ Q1DEF EN37", "CQ Q1GHI IO91", "CQ Q1JKL FN20");
        rig.Admitted.Should().Contain("CQ Q1JKL FN20");
    }

    [Fact(DisplayName = "R14: Normal depth with the fallback flag ON - the staged entry is used (so batch 3, the fallback's, can leave); flag OFF - the two-stage entry as ever")]
    public async Task Pump_Normal_UsesStagedOnlyWhileTheFlagIsOn()
    {
        var on = new PumpRig { Deep = false, FallbackOn = true };
        on.Staged = async publish =>
        {
            await publish(1, [Rs("CQ Q1ABC JO33")]);
            await publish(2, [Rs("CQ Q1DEF EN37", 2100)]);
            await publish(3, [Rs("CQ Q1JKL FN20", 2700)]);
        };
        await on.Build().RunAsync(PumpRig.Windows(Cycle1), CancellationToken.None);
        (on.StagedCalls, on.TwoStageCalls).Should().Be((1, 0));
        PumpRig.Drain(on.Answerer).Select(b => b.BatchNumber).Should().Equal(1, 2, 3);

        var off = new PumpRig { Deep = false, FallbackOn = false };
        off.Staged = _ => throw new InvalidOperationException("the staged entry must not be used");
        await off.Build().RunAsync(PumpRig.Windows(Cycle1), CancellationToken.None);
        (off.StagedCalls, off.TwoStageCalls).Should().Be((0, 1));

        var none = new PumpRig { Deep = false, FallbackOn = true, HasFallbackDelegate = false };
        none.Staged = _ => throw new InvalidOperationException("the staged entry must not be used");
        await none.Build().RunAsync(PumpRig.Windows(Cycle1), CancellationToken.None);
        (none.StagedCalls, none.TwoStageCalls).Should().Be((0, 1), "no CoherentFallbackOn delegate: the pump is the pre-change pump");
    }
}
