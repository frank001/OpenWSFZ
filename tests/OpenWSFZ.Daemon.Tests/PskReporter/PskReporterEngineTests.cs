using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Daemon.PskReporter;
using Xunit;
using static OpenWSFZ.Daemon.Tests.PskReporter.PskTestSupport;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>
/// The decision logic of the PSK Reporter upload under a fake clock (issue #262): FR-088 identity guard, FR-090/091 inputs,
/// FR-092 dedup, templates, sequence and cadence, FR-093 failure and the log line. No sockets, timers or threads; Q-prefix calls only.
/// </summary>
public sealed class PskReporterEngineTests
{
    private const double Dial40m = 7.074;
    private const double Dial20m = 14.074;
    private const uint Session = 0xA1B2C3D4;

    private sealed class Rig
    {
        public readonly CapturingLogger<PskReporterEngine> Log = new();
        public PskIdentity Id = Identity();
        public readonly PskReporterEngine Engine;
        public DateTime Now = T0;

        public Rig(TimeSpan? offset = null)
        {
            Engine = new PskReporterEngine(() => Id, Log, Session);
            Engine.Activate(Now, offset ?? TimeSpan.Zero);
        }

        public void Ingest(double? dial, params string[] messages)
            => Engine.Ingest(Batch(Now, dial, messages.Select(m => Decode(m)).ToArray()), Now);

        /// <summary>Prepares and completes as sent; returns the datagram or null.</summary>
        public PskDatagram? Send(bool succeed = true)
        {
            var d = Engine.Prepare(Now);
            if (d is not null) Engine.Complete(d, succeed, Now, succeed ? null : new IOException());
            return d;
        }
    }

    private static string Cq(int i) => $"CQ Q{1 + i % 9}A{(char)('A' + i / 26 % 26)}{(char)('A' + i % 26)} JO22";

    // ── FR-092: T2 templates cadence ─────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-092: T2: templates are in datagrams 1 to 3, absent in 4 and 5, and present again after one hour")]
    public void T2_TemplatesCadence()
    {
        var rig = new Rig();
        var flags = new List<bool>();
        for (int i = 0; i < 5; i++)
        {
            rig.Ingest(Dial20m, Cq(i));
            var d = rig.Send();
            d.Should().NotBeNull($"datagram {i + 1}");
            flags.Add(d!.IncludesTemplates);
            HasTemplates(d.Bytes).Should().Be(d.IncludesTemplates);
            rig.Now += PskReporterEngine.SendWindow;
        }
        flags.Should().Equal(true, true, true, false, false);

        rig.Now += TimeSpan.FromMinutes(61);
        rig.Ingest(Dial20m, Cq(50));
        rig.Send()!.IncludesTemplates.Should().BeTrue("an hour has passed since the templates last went");
    }

    // ── FR-092: T3 sequence ──────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-092: T3: datagrams of 2, 0 (none sent) and 5 sender records carry sequence s, s+2 and s+7, from 0; the receiver record is not counted")]
    public void T3_SequenceCountsSenderRecords()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Cq(1), Cq(2));
        var d1 = rig.Send()!;
        Sequence(d1.Bytes).Should().Be(0u, "s starts at 0 for the process");
        rig.Engine.Sequence.Should().Be(2u);

        rig.Now += PskReporterEngine.SendWindow;
        rig.Send().Should().BeNull("an empty window sends nothing");
        rig.Engine.Sequence.Should().Be(2u, "no datagram, no advance");

        rig.Now += PskReporterEngine.SendWindow;
        rig.Ingest(Dial20m, Cq(3), Cq(4), Cq(5), Cq(6), Cq(7));
        var d3 = rig.Send()!;
        Sequence(d3.Bytes).Should().Be(2u, "s+2");
        rig.Engine.Sequence.Should().Be(7u, "s+7 for the next datagram");
    }

    [Fact(DisplayName = "FR-092: T3: a datagram that was not sent does not advance the sequence; a new process starts at 0 with its own session id")]
    public void T3_UnsentDoesNotAdvance_NewProcessStartsAtZero()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Cq(1), Cq(2), Cq(3));
        rig.Send(succeed: false);
        rig.Engine.Sequence.Should().Be(0u);

        var other = new PskReporterEngine(() => Identity(), new CapturingLogger<PskReporterEngine>(), 0x01020304);
        other.Activate(T0, TimeSpan.Zero);
        other.Ingest(Batch(T0, Dial20m, Decode(Cq(1))), T0);
        var d = other.Prepare(T0)!;
        Sequence(d.Bytes).Should().Be(0u);
        SessionId(d.Bytes).Should().Be(0x01020304u);
    }

    // ── FR-091: T5 exclusions, T7 dial at capture ────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-091: T5: synthetic and unknown-region decodes are never encoded and are counted by reason")]
    public void T5_Exclusions_AreNeverEncoded_AndCounted()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m,
            Decode("CQ Q1ABC JO22"),
            Decode("CQ Q2DEF JO22", region: new OpenWSFZ.Abstractions.RegionInfo("EU", "Synthetic", true)),
            Decode("CQ Q3GHI JO22", unknownRegion: true)), T0);

        var d = rig.Send()!;
        ParseSpots(d.Bytes).Select(s => s.Call).Should().Equal("Q1ABC");
        rig.Log.Entries.Single(e => e.Level == LogLevel.Information).Message.Should().Contain("region=2");
    }

    [Fact(DisplayName = "FR-091: T7: the record frequency is the dial at capture plus the audio offset, whatever the radio does afterwards; no dial frequency reports nothing and is counted")]
    public void T7_DialAtCapture()
    {
        var rig = new Rig();
        // Captured at 7.074 MHz; the engine never asks anyone for the CURRENT dial, so a later retune cannot move the record.
        rig.Engine.Ingest(Batch(T0, Dial40m, Decode("CQ Q1ABC JO22", freqHz: 1234)), T0);
        rig.Engine.Ingest(Batch(T0, null,    Decode("CQ Q2DEF JO22")), T0);
        rig.Engine.Ingest(Batch(T0, 0.0,     Decode("CQ Q3GHI JO22")), T0);

        var d = rig.Send()!;
        var spot = ParseSpots(d.Bytes).Single();
        spot.Call.Should().Be("Q1ABC");
        spot.Freq.Should().Be(7_074_000u + 1234u);
        rig.Log.Entries.Single(e => e.Level == LogLevel.Information).Message.Should().Contain("no-dial-frequency=2");
    }

    [Fact(DisplayName = "FR-091: T7: a dial frequency outside the band table reports nothing and is counted as no-dial-frequency (N-3: there is no 'unknown' band)")]
    public void T7_OutOfBandDial_ReportsNothing_AndIsCounted()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, 3.0, Decode("CQ Q1ABC JO22")), T0);          // 3.000 MHz is between 160 m and 80 m
        rig.Engine.Ingest(Batch(T0, Dial20m, Decode("CQ Q2DEF JO22")), T0);
        rig.Engine.PendingCount.Should().Be(1, "only the in-band decode is queued");

        var d = rig.Send()!;
        ParseSpots(d.Bytes).Select(s => s.Call).Should().Equal("Q2DEF");
        rig.Log.Entries.Single(e => e.Level == LogLevel.Information).Message.Should().Contain("no-dial-frequency=1");
    }

    // ── FR-092: T6 dedup ─────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-092: T6: the same call 3 times in 4 minutes on one band gives 1 record; at 6 minutes on the same band 0; at 61 minutes 1; at 7 minutes on another band 1")]
    public void T6_Dedup()
    {
        var rig = new Rig();
        void At(int minutes, double dial)
        {
            rig.Now = T0.AddMinutes(minutes);
            rig.Engine.Ingest(Batch(rig.Now, dial, Decode("CQ Q1ABC JO22")), rig.Now);
        }
        At(0, Dial20m); At(2, Dial20m); At(4, Dial20m);
        rig.Engine.PendingCount.Should().Be(1, "three decodes inside 5 minutes");

        At(6, Dial20m);
        rig.Engine.PendingCount.Should().Be(1, "6 minutes on the same band: the per-(call, band) hour still holds");

        At(7, Dial40m);
        rig.Engine.PendingCount.Should().Be(2, "another band is a new key and 7 minutes respects the 5-minute minimum");

        At(61, Dial20m);
        rig.Engine.PendingCount.Should().Be(3, "61 minutes on the same band");
    }

    [Fact(DisplayName = "FR-092: T6: a band change inside 5 minutes still respects the per-call 5-minute minimum")]
    public void T6_BandChangeRespectsFiveMinutes()
    {
        var rig = new Rig();
        rig.Engine.Ingest(Batch(T0, Dial20m, Decode("CQ Q1ABC JO22")), T0);
        rig.Engine.Ingest(Batch(T0.AddMinutes(3), Dial40m, Decode("CQ Q1ABC JO22")), T0.AddMinutes(3));
        rig.Engine.PendingCount.Should().Be(1);
    }

    // ── FR-092: T10 cadence ──────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-092: T10: 20 minutes of batches give at most one datagram per 5 minutes; the first send follows the 0-60 s offset; an empty window sends nothing")]
    public void T10_Cadence_20Minutes()
    {
        var rig = new Rig(offset: TimeSpan.FromSeconds(37));
        var sends = new List<TimeSpan>();
        int n = 0;
        for (int s = 0; s <= 20 * 60; s += 5)
        {
            rig.Now = T0.AddSeconds(s);
            if (s % 60 == 5) rig.Ingest(Dial20m, Cq(n++));
            var d = rig.Send();
            if (d is not null) { sends.Add(TimeSpan.FromSeconds(s)); d.Bytes.Length.Should().BeLessThanOrEqualTo(1400); }
        }

        sends.Should().NotBeEmpty();
        sends[0].Should().BeGreaterThanOrEqualTo(TimeSpan.FromSeconds(37), "the first window falls after the offset");
        sends[0].Should().BeLessThan(TimeSpan.FromSeconds(37 + 10), "...and the send is not delayed beyond the first poll after it");
        for (int i = 1; i < sends.Count; i++)
            (sends[i] - sends[i - 1]).Should().BeGreaterThanOrEqualTo(PskReporterEngine.SendWindow, "at most one datagram per 5 minutes");
        sends.Should().HaveCount(4, "windows at ~0:37, 5:37, 10:37 and 15:37 each held records");
        (sends[0].TotalSeconds % 300).Should().NotBe(0, "the timer is not aligned to the clock");
    }

    [Fact(DisplayName = "FR-092: T10: a full datagram goes at once, the remainder waits for its window, and every datagram is at most 1,400 bytes")]
    public void T10_FullDatagramGoesAtOnce()
    {
        var rig = new Rig(offset: TimeSpan.FromMinutes(1));
        rig.Ingest(Dial20m, Enumerable.Range(0, 300).Select(Cq).ToArray());   // far more than one datagram's worth, before the first window

        var sent = new List<PskDatagram>();
        PskDatagram? d;
        while ((d = rig.Send()) is not null) sent.Add(d);

        sent.Should().NotBeEmpty("a full datagram does not wait for the window");
        sent.Should().OnlyContain(x => x.Bytes.Length <= 1400);
        sent.Should().OnlyContain(x => !x.FromWindow, "none of these is the window's datagram: the window is a minute away");
        rig.Engine.PendingCount.Should().BeGreaterThan(0).And.BeLessThan(300);

        rig.Now = T0.AddMinutes(1);
        var window = rig.Send();
        window.Should().NotBeNull("at the window the rest goes");
        window!.FromWindow.Should().BeTrue();
        rig.Engine.PendingCount.Should().Be(0, "300 records in total: each datagram took what fits, then the window sent the remainder");
    }

    // ── FR-088: T14 identity guard ───────────────────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-088: T14: a Q-prefix or empty receiver call, or an empty locator, sends nothing and logs one count-only Warning per window")]
    [InlineData("Q1OFZ", "JO33")]
    [InlineData("Q9ZZZ", "JO33")]
    [InlineData("",      "JO33")]
    [InlineData("W9XYZ", "")]
    public void T14_IdentityGuard(string call, string grid)
    {
        var rig = new Rig { Id = Identity(call, grid) };
        rig.Ingest(Dial20m, Cq(1), Cq(2), Cq(3));
        rig.Engine.PendingCount.Should().Be(0, "nothing is queued under a placeholder identity");
        rig.Send().Should().BeNull();

        var warnings = rig.Log.Entries.Where(e => e.Level == LogLevel.Warning).ToList();
        warnings.Should().HaveCount(1, "one Warning per window");
        warnings[0].Message.Should().Contain("3 decode(s) refused").And.NotContain("Q1A").And.NotContain("JO22");

        rig.Send().Should().BeNull();
        rig.Log.Count(LogLevel.Warning).Should().Be(1, "not again inside the same window");
        rig.Log.Count(LogLevel.Information).Should().Be(0);
    }

    // ── FR-093: T9 failure and the log line ──────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-093: T9: a failed send keeps the records, logs one Warning per window and the next window retries and succeeds")]
    public void T9_FailureRetriesNextWindow()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Cq(1), Cq(2));
        rig.Send(succeed: false).Should().NotBeNull();
        rig.Engine.PendingCount.Should().Be(2, "the records are back in the queue");
        rig.Log.Count(LogLevel.Warning).Should().Be(1);

        rig.Send().Should().BeNull("a full or due datagram is not retried every tick; the next window retries");
        rig.Now += PskReporterEngine.SendWindow;
        var retry = rig.Send(succeed: true);
        retry.Should().NotBeNull();
        rig.Engine.PendingCount.Should().Be(0);
        rig.Engine.Sequence.Should().Be(2u);
        rig.Log.Count(LogLevel.Warning).Should().Be(1, "a recovery adds no Warning");
    }

    [Fact(DisplayName = "FR-093: T9: a queue held across failures is bounded: the oldest records are dropped and counted")]
    public void T9_QueueIsBounded_OldestDropped()
    {
        var rig = new Rig();
        for (int i = 0; i < 12; i++)
            rig.Engine.Ingest(Batch(T0, Dial20m, Enumerable.Range(i * 100, 100).Select(k => Decode(Cq(k))).ToArray()), T0);   // many unique calls
        rig.Engine.PendingCount.Should().BeLessThanOrEqualTo(PskReporterEngine.MaxPendingRecords);

        var d = rig.Engine.Prepare(T0)!;
        rig.Engine.Complete(d, sent: false, T0, new IOException());
        rig.Engine.PendingCount.Should().BeLessThanOrEqualTo(PskReporterEngine.MaxPendingRecords);

        rig.Now += PskReporterEngine.SendWindow;
        PskDatagram? sent;
        while ((sent = rig.Send()) is not null) { /* drain */ }
        rig.Log.Entries.Where(e => e.Level == LogLevel.Information).Any(e => !e.Message.Contains("queue-dropped=0")).Should().BeTrue("the dropped records were counted");
    }

    [Fact(DisplayName = "FR-093: each datagram logs one Information line (UTC time, records, exclusions by reason, sequence after) and no callsign appears in any line at any level")]
    public void LogLine_HasCounts_NeverCalls()
    {
        var rig = new Rig { Id = Identity("W9XYZ") };
        rig.Engine.Ingest(Batch(T0, Dial20m,
            Decode("CQ Q1ABC JO22"), Decode("CQ Q1ABC JO22"),                 // dedup
            Decode("W9XYZ Q2DEF -05"), Decode("CQ W9XYZ JO33"),               // own call as a sender (the second)
            Decode("Q4JKL <...> -12"), Decode("TNX 73"),
            Decode("CQ Q5MNO JO22", unknownRegion: true)), T0);
        rig.Engine.Ingest(Batch(T0, null, Decode("CQ Q6PQR JO22")), T0);
        rig.Send().Should().NotBeNull();

        var info = rig.Log.Entries.Single(e => e.Level == LogLevel.Information).Message;
        info.Should().Contain("2 record(s)").And.Contain("region=1").And.Contain("hashed=1").And.Contain("unparseable=1")
            .And.Contain("own-call=1").And.Contain("no-dial-frequency=1").And.Contain("dedup=1").And.Contain("sequence after=2");
        info.Should().MatchRegex(@"datagram sent at \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}");

        foreach (var (_, message) in rig.Log.Entries)
            foreach (var call in new[] { "Q1ABC", "Q2DEF", "Q4JKL", "Q5MNO", "Q6PQR", "W9XYZ", "JO22", "JO33" })
                message.Should().NotContain(call, "the service logs counts, never calls or locators");
    }
}
