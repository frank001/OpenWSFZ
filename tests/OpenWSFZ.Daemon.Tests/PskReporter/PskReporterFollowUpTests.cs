using System.Text;
using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Daemon.PskReporter;
using Xunit;
using static OpenWSFZ.Daemon.Tests.PskReporter.PskTestSupport;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>
/// The #262 follow-up round (Architect Amendment 2, A2.3): T17 the per-window accounting line (F-a), T18 the status counters (F-b),
/// T19 the 6-character receiver locator choice (F-d) and the no-retrieve-query rule (F-e). Fake clock, no sockets, no fixed delays.
/// Q-prefix callsigns only (NFR-021).
/// </summary>
public sealed class PskReporterFollowUpTests
{
    private const double Dial20m = 14.074;
    private const uint Session = 0xA1B2C3D4;

    private sealed class Rig
    {
        public readonly CapturingLogger<PskReporterEngine> Log = new();
        public PskIdentity Id = Identity();
        public readonly PskReporterEngine Engine;
        public DateTime Now = T0;

        public Rig()
        {
            Engine = new PskReporterEngine(() => Id, Log, Session);
            Engine.Activate(Now, TimeSpan.Zero);
        }

        public void Ingest(double? dial, params DecodeResult[] results) => Engine.Ingest(Batch(Now, dial, results), Now);

        public void Ingest(double? dial, params string[] messages) => Ingest(dial, messages.Select(m => Decode(m)).ToArray());

        /// <summary>Prepares (which closes a due window) and completes as sent; returns the datagram or null.</summary>
        public PskDatagram? Send()
        {
            var d = Engine.Prepare(Now);
            if (d is not null) Engine.Complete(d, sent: true, Now);
            return d;
        }

        public void NextWindow() => Now += PskReporterEngine.SendWindow;

        public List<string> WindowLines()
            => Log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.StartsWith("PSK Reporter:", StringComparison.Ordinal))
                          .Select(e => e.Message).ToList();
    }

    private static string Cq(int i) => $"CQ Q{1 + i % 9}A{(char)('A' + i / 26 % 26)}{(char)('A' + i % 26)} JO22";

    private static string Line(int seen, int reported, int region = 0, int noDial = 0, int identity = 0, int hashed = 0, int own = 0, int dedup = 0)
        => $"PSK Reporter: {seen} decodes seen, {reported} reported: region={region}, no-dial={noDial}, identity={identity}, hashed={hashed}, own-call={own}, dedup={dedup}";

    // ── FR-095: T17 the accounting line, sent or not ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-095: T17: a window of 30 decodes all of unknown region logs '30 decodes seen, 0 reported: region=30' and sends no datagram")]
    public void T17_AllExcluded_LogsTheLine_AndSendsNothing()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Enumerable.Range(0, 30).Select(i => Decode(Cq(i), unknownRegion: true)).ToArray());

        rig.Send().Should().BeNull("every decode was excluded, so nothing is queued");

        rig.WindowLines().Should().Equal(Line(30, 0, region: 30));
    }

    [Fact(DisplayName = "FR-095: T17: a window with no batch logs '0 decodes seen'")]
    public void T17_EmptyWindow_LogsZeroDecodesSeen()
    {
        var rig = new Rig();
        rig.Send().Should().BeNull();
        rig.WindowLines().Should().Equal(Line(0, 0));
    }

    [Fact(DisplayName = "FR-095: T17: the counters restart at zero in the next window")]
    public void T17_CountersRestartEachWindow()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Enumerable.Range(0, 30).Select(i => Decode(Cq(i), unknownRegion: true)).ToArray());
        rig.Send();
        rig.NextWindow();
        rig.Ingest(Dial20m, Decode(Cq(100), unknownRegion: true), Decode(Cq(101), unknownRegion: true), Decode(Cq(102), unknownRegion: true));
        rig.Send();
        rig.NextWindow();
        rig.Send();

        rig.WindowLines().Should().Equal(Line(30, 0, region: 30), Line(3, 0, region: 3), Line(0, 0));
    }

    [Fact(DisplayName = "FR-095: T17: a window in which a datagram IS sent logs the same line with the records reported")]
    public void T17_SentWindow_LogsReported()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Cq(1), Cq(2), Cq(3));
        rig.Send().Should().NotBeNull();
        rig.WindowLines().Should().Equal(Line(3, 3));
    }

    public static IEnumerable<object[]> ReasonRows()
    {
        yield return ["region",   Line(2, 0, region: 2)];
        yield return ["no-dial",  Line(2, 0, noDial: 2)];
        yield return ["identity", Line(2, 0, identity: 2)];
        yield return ["hashed",   Line(2, 0, hashed: 2)];
        yield return ["own-call", Line(2, 0, own: 2)];
        yield return ["dedup",    Line(2, 1, dedup: 1)];
    }

    [Theory(DisplayName = "FR-095: T17: each exclusion reason moves only its own counter in the window line")]
    [MemberData(nameof(ReasonRows))]
    public void T17_EachReasonMovesOnlyItsOwnCounter(string reason, string expectedLine)
    {
        var rig = new Rig();
        switch (reason)
        {
            case "region":   rig.Ingest(Dial20m, Decode(Cq(1), unknownRegion: true), Decode(Cq(2), unknownRegion: true)); break;
            case "no-dial":  rig.Ingest(null, Cq(1), Cq(2)); break;
            case "identity": rig.Id = Identity("Q1OFZ"); rig.Ingest(Dial20m, Cq(1), Cq(2)); break;
            case "hashed":   rig.Ingest(Dial20m, "Q4JKL <...> -12", "Q5MNO <...> -08"); break;
            case "own-call": rig.Ingest(Dial20m, "CQ W9XYZ JO33", "CQ W9XYZ JO33"); break;
            case "dedup":    rig.Ingest(Dial20m, "CQ Q1ABC JO22", "CQ Q1ABC JO22"); break;
        }
        rig.Send();
        rig.WindowLines().Should().Equal(expectedLine);
    }

    [Fact(DisplayName = "FR-095: T17: the window line never contains a callsign or a locator, at any level")]
    public void T17_WindowLine_HasNoCallsign()
    {
        var rig = new Rig { Id = Identity("W9XYZ", "JO33", locator: "JO33ED") };
        rig.Ingest(Dial20m, "CQ Q1ABC JO22", "CQ Q1ABC JO22", "CQ W9XYZ JO33", "Q4JKL <...> -12", "TNX 73");
        rig.Send();
        rig.NextWindow();
        rig.Id = Identity("W9XYZ", "JO33", locator: "JO22AB");   // a mismatching locator: the Warning must not carry a call either
        rig.Send();

        rig.WindowLines().Should().HaveCount(2);
        foreach (var (_, message) in rig.Log.Entries)
            foreach (var text in new[] { "Q1ABC", "Q4JKL", "W9XYZ", "JO22", "JO33ED", "JO22AB" })
                message.Should().NotContain(text, "the service logs counts, never calls or locators");
    }

    // ── FR-095: T18 one counter set, two readers ─────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-095: T18: the status and the window line are built from the same counters: moving one counter moves both")]
    public void T18_StatusAndWindowLine_ShareTheCounters()
    {
        var rig = new Rig { Id = Identity("Q1OFZ") };
        rig.Engine.GetStatus().Window.Identity.Should().Be(0);

        rig.Ingest(Dial20m, Cq(1), Cq(2), Cq(3));
        rig.Engine.GetStatus().Window.Identity.Should().Be(3);
        rig.Ingest(Dial20m, Cq(4), Cq(5));
        rig.Engine.GetStatus().Window.Identity.Should().Be(5, "the status moves with the counter");

        rig.Send();
        rig.WindowLines().Should().Equal(Line(5, 0, identity: 5));
        rig.Engine.GetStatus().Window.Identity.Should().Be(5, "the closed window is still what the status reads, from the same counters");
        rig.Engine.GetStatus().Window.Seen.Should().Be(5);
    }

    [Fact(DisplayName = "FR-095: T18: waiting after enabling, sending with the last datagram's time and record count, refused with the dominant reason")]
    public void T18_States()
    {
        var rig = new Rig();
        var s0 = rig.Engine.GetStatus();
        s0.State.Should().Be(PskReporterStates.Waiting);
        s0.LastDatagramUtc.Should().BeNull();

        rig.Ingest(Dial20m, Enumerable.Range(0, 40).Select(Cq).ToArray());
        rig.Send().Should().NotBeNull();
        var s1 = rig.Engine.GetStatus();
        s1.State.Should().Be(PskReporterStates.Sending);
        s1.LastDatagramUtc.Should().Be(rig.Now);
        s1.LastDatagramRecords.Should().Be(40);
        s1.Reason.Should().BeNull();
    }

    [Theory(DisplayName = "FR-095: T18: with decodes arriving and nothing reported the status is refused and names whichever of identity, no-dial, region dominates")]
    [InlineData("identity")]
    [InlineData("no-dial")]
    [InlineData("region")]
    public void T18_Refused_NamesTheDominantReason(string dominant)
    {
        var rig = new Rig();
        switch (dominant)
        {
            case "identity":
                rig.Id = Identity("Q1OFZ");
                rig.Ingest(Dial20m, Cq(1), Cq(2), Cq(3));
                break;
            case "no-dial":
                rig.Ingest(null, Cq(1), Cq(2), Cq(3));
                rig.Ingest(Dial20m, Decode(Cq(9), unknownRegion: true));
                break;
            default:
                rig.Ingest(Dial20m, Decode(Cq(1), unknownRegion: true), Decode(Cq(2), unknownRegion: true), Decode(Cq(3), unknownRegion: true));
                rig.Ingest(null, Cq(9));
                break;
        }

        var status = rig.Engine.GetStatus();
        status.State.Should().Be(PskReporterStates.Refused);
        status.Reason.Should().Be(dominant);
    }

    [Fact(DisplayName = "FR-095: T18: a reason that is not the largest does not win; a window with records reported is not refused; after Deactivate the status is off")]
    public void T18_NotRefusedWhenReporting_OffWhenInactive()
    {
        var rig = new Rig();
        rig.Ingest(Dial20m, Decode(Cq(1)), Decode(Cq(2)), Decode(Cq(3), unknownRegion: true));
        rig.Engine.GetStatus().State.Should().Be(PskReporterStates.Waiting, "two records were queued, so nothing is being refused");

        rig.Engine.Deactivate();
        var off = rig.Engine.GetStatus();
        off.State.Should().Be(PskReporterStates.Off);
        off.Window.Seen.Should().Be(0);
    }

    // ── FR-096: T19 the locator choice ───────────────────────────────────────────────────────────────────────────────

    private static bool Contains(byte[] haystack, byte[] needle)
    {
        for (int i = 0; i + needle.Length <= haystack.Length; i++)
            if (haystack.AsSpan(i, needle.Length).SequenceEqual(needle)) return true;
        return false;
    }

    /// <summary>The receiver record's locator as it appears on the wire: a length byte then the ASCII text.</summary>
    private static byte[] Wire(string locator) => [(byte)locator.Length, .. Encoding.ASCII.GetBytes(locator)];

    private static byte[] FirstDatagram(string grid, string locator, out Rig rig)
    {
        rig = new Rig { Id = Identity("W9XYZ", grid, locator: locator) };
        rig.Ingest(Dial20m, "CQ Q1ABC JO44");
        var d = rig.Send();
        d.Should().NotBeNull();
        return d!.Bytes;
    }

    [Fact(DisplayName = "FR-096: T19: tx.grid JO33 with locator jo33ED sends the receiver locator JO33ed (first 4 upper, last 2 lower)")]
    public void T19_ValidMatching_IsSentNormalised()
    {
        var bytes = FirstDatagram("JO33", "jo33ED", out var rig);
        Contains(bytes, Wire("JO33ed")).Should().BeTrue();
        Contains(bytes, Wire("jo33ED")).Should().BeFalse("the stored text is not what goes on the wire");
        rig.Log.Count(LogLevel.Warning).Should().Be(0);
    }

    [Fact(DisplayName = "FR-096: T19: an empty locator sends tx.grid exactly as before, with no Warning")]
    public void T19_Empty_SendsTxGrid()
    {
        var bytes = FirstDatagram("JO33", "", out var rig);
        Contains(bytes, Wire("JO33")).Should().BeTrue();
        Contains(bytes, Wire("JO33ed")).Should().BeFalse();
        rig.Log.Count(LogLevel.Warning).Should().Be(0);
    }

    [Theory(DisplayName = "FR-096: T19: a mismatching (JO22AB), 5-character (JO33E), out-of-range (JO33ZZ) or malformed (ZZ33ab) locator sends tx.grid with exactly one Warning naming the reason")]
    [InlineData("JO22AB", "mismatch")]
    [InlineData("JO33E",  "invalid")]
    [InlineData("JO33ZZ", "invalid")]
    [InlineData("ZZ33ab", "invalid")]
    public void T19_NotUsable_SendsTxGrid_WithOneWarning(string locator, string reason)
    {
        var bytes = FirstDatagram("JO33", locator, out var rig);
        Contains(bytes, Wire("JO33")).Should().BeTrue();
        Contains(bytes, Wire(locator)).Should().BeFalse();
        Contains(bytes, Wire("JO33ed")).Should().BeFalse();

        var warnings = rig.Log.Entries.Where(e => e.Level == LogLevel.Warning).ToList();
        warnings.Should().HaveCount(1);
        warnings[0].Message.Should().Contain(reason).And.NotContain("W9XYZ").And.NotContain("Q1ABC").And.NotContain(locator);
    }

    [Fact(DisplayName = "FR-096: T19: the Warning is once per window however many datagrams the window holds, and again in the next window")]
    public void T19_WarningOncePerWindow()
    {
        var rig = new Rig { Id = Identity("W9XYZ", "JO33", locator: "JO22AB") };
        for (int i = 0; i < 3; i++)
        {
            rig.Ingest(Dial20m, Cq(i));
            rig.Send();                      // each tick of the window may send; only the first Prepare of a window closes it
        }
        rig.Log.Count(LogLevel.Warning).Should().Be(1);

        rig.NextWindow();
        rig.Ingest(Dial20m, Cq(50));
        rig.Send();
        rig.Log.Count(LogLevel.Warning).Should().Be(2, "one per window");
    }

    [Fact(DisplayName = "FR-096: T19: an empty tx.grid still sends nothing even with a valid locator (the identity guard is unchanged)")]
    public void T19_EmptyGrid_StillSendsNothing()
    {
        var rig = new Rig { Id = Identity("W9XYZ", "", locator: "JO33ED") };
        rig.Ingest(Dial20m, Cq(1));
        rig.Engine.PendingCount.Should().Be(0);
        rig.Send().Should().BeNull();
    }

    [Fact(DisplayName = "FR-096: T19: the encoder with receiver locator JO33ed equals QA's fixture t1_receiver_locator6 byte for byte")]
    public void T19_EncoderFixture_Locator6()
    {
        const uint dialHz = 14_074_000;
        uint Unix(int y, int mo, int d, int h, int mi, int s) => (uint)new DateTimeOffset(y, mo, d, h, mi, s, TimeSpan.Zero).ToUnixTimeSeconds();
        uint cycle = Unix(2026, 10, 25, 11, 34, 45);
        PskSpot[] spots = [new("Q2DEF", null, dialHz + 987, -5, cycle), new("Q1ABC", "JO22", dialHz + 1500, -12, cycle)];
        var bytes = PskReporterEncoder.Encode(new PskReceiver("Q1OFZ", "JO33ed", "OpenWSFZ 0.63", ""), spots,
            Unix(2026, 10, 25, 11, 35, 0), 7, Session, includeTemplates: true);

        using var s = typeof(PskReporterFollowUpTests).Assembly.GetManifestResourceStream("PskReporter.Fixtures.t1_receiver_locator6.hex")
                      ?? throw new InvalidOperationException("fixture t1_receiver_locator6 not embedded");
        using var r = new StreamReader(s);
        var expected = Convert.FromHexString(string.Concat(r.ReadToEnd().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)));
        Convert.ToHexString(bytes).Should().Be(Convert.ToHexString(expected));
    }

    // ── FR-093: 1.24 the product never queries PSK Reporter ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-093: the service's only network activity over a full fake-clock session is the injected transport; no HTTP client or retrieve address exists in its code")]
    public async Task NoRetrieveQuery_OnlyTheInjectedTransport()
    {
        var clock     = new FakeClock();
        var store     = new FakeConfigStore(new AppConfig { PskReporter = new PskReporterConfig(enabled: true, host: "test.invalid", port: 14739) });
        var queue     = Channel.CreateUnbounded<DecodeBatch>();
        var transport = new FakeTransport();
        int factoryCalls = 0;
        using var service = new PskReporterService(queue.Reader, store, clock, (_, _) => { factoryCalls++; return transport; },
            () => Identity(), new CapturingLogger<PskReporterService>(), firstSendOffset: () => TimeSpan.Zero, tickInterval: TimeSpan.FromHours(1));
        await service.StartAsync(CancellationToken.None);

        for (int i = 0; i < 8; i++)
        {
            service.Engine.Ingest(Batch(clock.UtcNow, Dial20m, Decode(Cq(i))), clock.UtcNow);
            await service.FlushAsync(CancellationToken.None);
            clock.Advance(PskReporterEngine.SendWindow);
        }
        await service.StopAsync(CancellationToken.None);

        factoryCalls.Should().Be(1, "one socket for the whole enabled period; the service reaches the network only through it");
        transport.SentCount.Should().BeGreaterThan(0, "datagrams were sent through the injected transport");

        // Static half: the upload's sources name no HTTP type and no read interface.
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "OpenWSFZ.slnx"))) dir = dir.Parent;
        dir.Should().NotBeNull("the repository root is above the test binaries");
        var folder = Path.Combine(dir!.FullName, "src", "OpenWSFZ.Daemon", "PskReporter");
        var sources = Directory.GetFiles(folder, "*.cs");
        sources.Should().NotBeEmpty();
        foreach (var file in sources)
        {
            var text = File.ReadAllText(file);
            foreach (var forbidden in new[] { "HttpClient", "System.Net.Http", "WebClient", "WebRequest", "retrieve.pskreporter", "pskreporter.info/cgi-bin" })
                text.Should().NotContain(forbidden, $"{Path.GetFileName(file)}: the daemon never queries the retrieve interface");
        }
    }
}
