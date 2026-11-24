using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.PskReporter;
using Xunit;
using static OpenWSFZ.Daemon.Tests.PskReporter.PskTestSupport;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>
/// CQ-AP D7: a decode the CQ a-priori attempt made (<see cref="ApKind.Cq"/>) is never uploaded to PSK Reporter. It is a counted exclusion
/// reason, <c>ap=</c>, on both accounting lines (the per-window line and the per-datagram line) and in the status counters. Q-prefix calls only (NFR-021).
/// </summary>
public sealed class PskReporterCqApTests
{
    private const double Dial20m = 14.074;
    private const uint Session = 0xA1B2C3D4;

    private sealed class Rig
    {
        public readonly CapturingLogger<PskReporterEngine> Log = new();
        public readonly PskReporterEngine Engine;
        public DateTime Now = T0;

        public Rig()
        {
            Engine = new PskReporterEngine(() => Identity(), Log, Session);
            Engine.Activate(Now, TimeSpan.Zero);
        }

        public PskDatagram? Send()
        {
            var d = Engine.Prepare(Now);
            if (d is not null) Engine.Complete(d, sent: true, Now);
            return d;
        }

        public IEnumerable<string> WindowLines()
            => Log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.StartsWith("PSK Reporter:", StringComparison.Ordinal)).Select(e => e.Message);
    }

    private static DecodeResult Cq(string message, ApKind kind)
        => Decode(message) with { ApKind = kind };

    [Fact(DisplayName = "FR-103: CQ-AP D7: an ApKind.Cq decode is not uploaded and is counted under ap=; ordinary decodes in the same batch still go")]
    public void ApDecodes_AreNotUploaded_AndCounted()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m,
            Cq("CQ Q1ABC JO22", ApKind.Cq),
            Cq("CQ Q2DEF JO22", ApKind.None),
            Cq("CQ Q3GHI JO22", ApKind.Cq)), T0);

        var d = rig.Send();
        d.Should().NotBeNull("the ordinary decode is still reported");
        var spots = ParseSpots(d!.Bytes);
        spots.Select(s => s.Call).Should().Equal("Q2DEF");
        spots.Select(s => s.Call).Should().NotContain(["Q1ABC", "Q3GHI"], "an unconfirmed AP decode must never become a public spot");

        var status = rig.Engine.GetStatus().Window;
        status.Seen.Should().Be(3);
        status.Reported.Should().Be(1);
        status.Ap.Should().Be(2);
    }

    [Fact(DisplayName = "FR-103: CQ-AP D7: a window of only ApKind.Cq decodes sends nothing and is not 'refused' (ap is a count, not a refusal reason)")]
    public void OnlyApDecodes_SendNothing_AndAreNotRefused()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m, Cq("CQ Q1ABC JO22", ApKind.Cq)), T0);

        rig.Send().Should().BeNull();
        var status = rig.Engine.GetStatus();
        status.Window.Ap.Should().Be(1);
        status.Reason.Should().BeNull("the refusal reasons are identity, no-dial and region only");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D7: the per-window line ends 'dedup=N, ap=N' and the per-datagram line carries ap=N; neither names a call")]
    public void BothAccountingLines_CarryAp()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m,
            Cq("CQ Q1ABC JO22", ApKind.Cq), Cq("CQ Q3GHI JO22", ApKind.Cq), Cq("CQ Q2DEF JO22", ApKind.None)), T0);
        rig.Send().Should().NotBeNull();   // closes nothing yet: the window is not due; the datagram line is written by Complete

        var datagramLine = rig.Log.Entries.Single(e => e.Level == LogLevel.Information && e.Message.Contains("datagram sent")).Message;
        datagramLine.Should().Contain("dedup=0 ap=2 template=0 queue-dropped=0");

        rig.Now += PskReporterEngine.SendWindow;
        rig.Send();   // due: closes the window and logs its accounting line
        rig.WindowLines().Should().Contain(
            "PSK Reporter: 3 decodes seen, 1 reported: region=0, no-dial=0, identity=0, hashed=0, own-call=0, dedup=0, ap=2, template=0");

        foreach (var (_, message) in rig.Log.Entries)
            foreach (var call in new[] { "Q1ABC", "Q2DEF", "Q3GHI" })
                message.Should().NotContain(call, "counts only, never a call");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D7: the per-datagram ap count restarts after each datagram")]
    public void DatagramLine_ApCount_RestartsAfterEachDatagram()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m, Cq("CQ Q1ABC JO22", ApKind.Cq), Cq("CQ Q2DEF JO22", ApKind.None)), T0);
        rig.Send();
        rig.Now += PskReporterEngine.SendWindow;
        rig.Engine.Ingest(Batch(rig.Now, Dial20m, Cq("CQ Q4JKL JO22", ApKind.None)), rig.Now);
        rig.Send();

        var lines = rig.Log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.Contains("datagram sent")).Select(e => e.Message).ToList();
        lines.Should().HaveCount(2);
        lines[0].Should().Contain("ap=1");
        lines[1].Should().Contain("ap=0");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D7: with no ApKind.Cq decodes ap is 0 everywhere (the exclusion changes nothing it does not apply to)")]
    public void NoApDecodes_ApIsZero()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m, Decode("CQ Q1ABC JO22"), Decode("CQ Q2DEF JO22")), T0);
        var d = rig.Send();
        ParseSpots(d!.Bytes).Select(s => s.Call).Should().Equal("Q1ABC", "Q2DEF");
        rig.Engine.GetStatus().Window.Ap.Should().Be(0);
    }
}
