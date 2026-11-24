using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Daemon.PskReporter;
using OpenWSFZ.Daemon.Tests.PskReporter;
using Xunit;
using static OpenWSFZ.Daemon.Tests.PskReporter.PskTestSupport;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// XC-BUILD (FR-105): the two consumers downstream of the decoder that a sixth batch (the template stage's batch 6, <see cref="DecodeResult.PathTemplate"/>) needs ready.
/// D1: the QSO queues hold two full cycles of six batches (14), and OFF stays at 8. D2: PSK Reporter never uploads a template decode and counts it under <c>template=</c>, while the panel, ALL.TXT, the QSO channels and
/// external reporting still get batch 6. Q-prefix callsigns only (NFR-021); no sleeps.
/// </summary>
public sealed class XcBatch6ConsumerTests
{
    private const double Dial = 14.074;
    private static readonly DateTimeOffset Cycle0 = new(DateTime.SpecifyKind(T0, DateTimeKind.Utc));

    private static DecodeBatch B(int cycle, int batch) => new(Cycle0.AddSeconds(15 * cycle), [], batch);
    private static string Tag(DecodeBatch b) => $"{(int)((b.CycleStart - Cycle0).TotalSeconds / 15)}.{b.BatchNumber}";

    private static DecodeResult Template(string message, int freqHz = 1500)
        => Decode(message, freqHz) with { Path = DecodeResult.PathTemplate };

    // ── D1 ─────────────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD D1: the QSO queue holds two full cycles of six batches (14) while the service is blocked and drops nothing; a third cycle drops the OLDEST; the flag-OFF capacity is still 8")]
    public void QsoQueue_HoldsTwoSixBatchCycles_ThirdDropsOldest()
    {
        LateBatch.BatchesPerCycleFallbackOn.Should().Be(6, "batches 1 to 5 and the template stage's batch 6");
        LateBatch.QsoChannelCapacityFallbackOn.Should().Be(14).And.Be(6 * 2 + 2);
        LateBatch.QsoChannelCapacity.Should().Be(8, "flag OFF: unchanged");

        var queue = LateBatch.CreateQsoQueue(() => true);   // the service is blocked: nothing reads
        for (int cycle = 0; cycle < 2; cycle++)
            for (int n = 1; n <= 6; n++) queue.Writer.TryWrite(B(cycle, n));
        queue.Reader.Count.Should().Be(12, "two full cycles of six batches: nothing dropped");

        for (int n = 1; n <= 6; n++) queue.Writer.TryWrite(B(2, n));   // the third cycle
        queue.Reader.Count.Should().Be(14, "the channel holds exactly 14");
        var read = new List<string>();
        while (queue.Reader.TryRead(out var b)) read.Add(Tag(b));
        read.Should().Equal(new[] { "0.5", "0.6" }.Concat(Enumerable.Range(1, 2).SelectMany(c => Enumerable.Range(1, 6).Select(n => $"{c}.{n}"))),
            "the four OLDEST (cycle 0's batches 1 to 4) were dropped, the rest kept in order");

        var off = LateBatch.CreateQsoQueue(() => false);
        for (int i = 0; i < 20; i++) off.Writer.TryWrite(B(i, 1));
        off.Reader.Count.Should().Be(8, "flag OFF holds 8");
    }

    // ── D2 ─────────────────────────────────────────────────────────────────────────────────────────────────────

    private static (PskReporterEngine Engine, CapturingLogger<PskReporterEngine> Log) NewEngine()
    {
        var log = new CapturingLogger<PskReporterEngine>();
        var engine = new PskReporterEngine(() => Identity(), log, 0xA1B2C3D4);
        engine.Activate(T0, TimeSpan.Zero);
        return (engine, log);
    }

    private static PskDatagram? Send(PskReporterEngine e, DateTime now)
    {
        var d = e.Prepare(now);
        if (d is not null) e.Complete(d, sent: true, now);
        return d;
    }

    [Fact(DisplayName = "FR-105: XC-BUILD D2: a mixed batch (one ordinary row, one template row, both otherwise uploadable) uploads ONLY the ordinary row and counts template=1 on both accounting lines and in the status; Path 0 and 2 rows still upload")]
    public void MixedBatch_UploadsOnlyTheOrdinaryRow()
    {
        var (engine, log) = NewEngine();
        engine.Ingest(Batch(T0, Dial,
            Decode("CQ Q1ABC JO22"),
            Template("CQ Q2DEF JO22"),
            Decode("CQ Q3GHI JO22") with { Path = 2 },
            Decode("CQ Q4JKL JO22") with { Path = 1 }), T0);

        var d = Send(engine, T0);
        d.Should().NotBeNull();
        ParseSpots(d!.Bytes).Select(s => s.Call).Should().BeEquivalentTo(["Q1ABC", "Q3GHI", "Q4JKL"]).And.NotContain("Q2DEF", "a template decode is never a public spot");

        var status = engine.GetStatus().Window;
        (status.Seen, status.Reported, status.Template).Should().Be((4, 3, 1));

        var datagramLine = log.Entries.Single(e => e.Level == LogLevel.Information && e.Message.Contains("datagram sent")).Message;
        datagramLine.Should().Contain("template=1");
        Send(engine, T0 + PskReporterEngine.SendWindow);   // the window is due: it closes and logs
        log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.StartsWith("PSK Reporter:", StringComparison.Ordinal))
            .Select(e => e.Message).Should().Contain("PSK Reporter: 4 decodes seen, 3 reported: region=0, no-dial=0, identity=0, hashed=0, own-call=0, dedup=0, ap=0, template=1");
        foreach (var (_, message) in log.Entries) message.Should().NotContain("Q2DEF", "counts only, never a call");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD D2: a template row that would also be excluded for another reason (unknown region) is counted under template only; an AP template row is counted under ap (the AP rule is first)")]
    public void TemplateRow_CountedUnderTemplateOnly_AfterAp_BeforeRegion()
    {
        var (engine, _) = NewEngine();
        engine.Ingest(Batch(T0, Dial,
            Template("CQ Q1ABC JO22") with { Region = null },
            Template("CQ Q2DEF JO22") with { ApKind = ApKind.Cq },
            Decode("CQ Q3GHI JO22")), T0);

        var w = engine.GetStatus().Window;
        w.Template.Should().Be(1, "the unknown-region template row");
        w.Region.Should().Be(0, "the template rule comes before the region rule");
        w.Ap.Should().Be(1, "the AP rule comes first");
        w.Reported.Should().Be(1);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD D2: the constant the daemon uses for 'template' (DecodeResult.PathTemplate, Abstractions) is 3, and a Path-3 row is the only one excluded")]
    public void PathTemplate_IsThree()
    {
        DecodeResult.PathTemplate.Should().Be(3);
        var (engine, _) = NewEngine();
        engine.Ingest(Batch(T0, Dial, Decode("CQ Q1ABC JO22") with { Path = 2 }, Decode("CQ Q2DEF JO22") with { Path = 4 }), T0);
        engine.GetStatus().Window.Template.Should().Be(0);
        engine.GetStatus().Window.Reported.Should().Be(2);
    }

    // ── D2 is not a filter for the other consumers ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-105: XC-BUILD D2: a mixed batch 6 (an ordinary row and a template row) reaches the panel, ALL.TXT, both QSO channels, external reporting and the PSK Reporter queue with BOTH rows: only the PSK engine excludes it")]
    public async Task Pump_DeliversBothRows_ToEveryConsumer()
    {
        var panel = new List<DecodeResult>();
        var allTxt = new List<DecodeResult>();
        var answerer = Channel.CreateUnbounded<DecodeBatch>();
        var caller = Channel.CreateUnbounded<DecodeBatch>();
        var external = Channel.CreateUnbounded<DecodeBatch>();
        var psk = LateBatch.CreateQsoQueue(() => true);
        var rows = new[] { Decode("CQ Q1ABC JO22"), Template("CQ Q2DEF JO22") };

        var pump = new DecodePump(new DecodePumpDependencies(
            CurrentDialFrequency:     () => Dial,
            FallbackDialFrequency:    () => 0.0,
            DeriveBand:               _ => "20m",
            SubtractionEnabled:       () => true,
            DecodeSingleBatch:        (_, _, _, _) => Task.FromResult<IReadOnlyList<DecodeResult>>([]),
            DecodeTwoStage:           (_, _, _, _, _) => Task.FromResult<IReadOnlyList<DecodeResult>>([]),
            ApplyNoiseSuppression:    r => r,
            PublishToPanel:           r => { lock (panel) panel.AddRange(r); return Task.CompletedTask; },
            AppendAllTxt:             (_, _, r) => { lock (allTxt) allTxt.AddRange(r); return Task.CompletedTask; },
            EnqueueArchive:           (_, _, _, _, _) => { },
            AdmitNewValues:           _ => null,
            PublishFilterState:       _ => { },
            AnswererChannel:          answerer.Writer,
            CallerChannel:            caller.Writer,
            ExternalReportingChannel: external.Writer,
            Logger:                   Microsoft.Extensions.Logging.Abstractions.NullLogger.Instance)
        {
            DecodeStaged       = (_, _, _, publish, _) => publish(6, rows),
            DecodingDeep       = () => true,
            CoherentFallbackOn = () => true,
            PskReporterChannel = psk.Writer,
        });

        await pump.RunAsync(OneWindow(), CancellationToken.None);

        // The pump hands batch 6 to the sinks generically (it is not batch 1, so it takes the supplementary path).
        panel.Select(r => r.Message).Should().Equal(rows.Select(r => r.Message));
        allTxt.Select(r => r.Message).Should().Equal(rows.Select(r => r.Message));
        foreach (var channel in new[] { answerer, caller, external })
        {
            channel.Reader.TryRead(out var b).Should().BeTrue();
            b!.BatchNumber.Should().Be(6);
            b.Results.Select(r => r.Message).Should().Equal(rows.Select(r => r.Message));
        }
        psk.Reader.TryRead(out var pb).Should().BeTrue();
        pb!.Results.Should().HaveCount(2, "the exclusion lives in the PSK engine, not in the queue");
    }

    private static async IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> OneWindow()
    {
        yield return (new float[180_000], T0, Dial);
        await Task.CompletedTask;
    }

    [Fact(DisplayName = "FR-105: XC-BUILD D2: the per-datagram template count restarts after each datagram: a template row in the first datagram and none in the second gives template=1 then template=0")]
    public void DatagramLine_TemplateCount_RestartsAfterEachDatagram()
    {
        var (engine, log) = NewEngine();
        engine.Ingest(Batch(T0, Dial, Decode("CQ Q1ABC JO22"), Template("CQ Q2DEF JO22")), T0);
        Send(engine, T0);
        var later = T0 + PskReporterEngine.SendWindow;
        engine.Ingest(Batch(later, Dial, Decode("CQ Q4JKL JO22")), later);
        Send(engine, later);

        var lines = log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.Contains("datagram sent")).Select(e => e.Message).ToList();
        lines.Should().HaveCount(2);
        lines[0].Should().Contain("template=1");
        lines[1].Should().Contain("template=0");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD D2: ending an enabled period clears the template count: after a template row, Deactivate and Activate, the next datagram line and the status show template=0")]
    public void Reset_ClearsTheTemplateCount()
    {
        var (engine, log) = NewEngine();
        engine.Ingest(Batch(T0, Dial, Template("CQ Q2DEF JO22")), T0);
        engine.GetStatus().Window.Template.Should().Be(1, "the control: it was counted");

        engine.Deactivate();
        engine.Activate(T0, TimeSpan.Zero);
        engine.GetStatus().Window.Template.Should().Be(0, "the window restarted");

        engine.Ingest(Batch(T0, Dial, Decode("CQ Q4JKL JO22")), T0);
        Send(engine, T0).Should().NotBeNull();
        log.Entries.Single(e => e.Level == LogLevel.Information && e.Message.Contains("datagram sent")).Message
            .Should().Contain("template=0", "the since-last-datagram counter was reset with the period");
    }

}
