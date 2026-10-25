using System.Net;
using System.Net.Sockets;
using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Daemon.PskReporter;
using OpenWSFZ.TestSupport;
using Xunit;
using static OpenWSFZ.Daemon.Tests.PskReporter.PskTestSupport;

namespace OpenWSFZ.Daemon.Tests.PskReporter;

/// <summary>
/// The hosted service (issue #262): inert when disabled, one socket per enabled period, failure isolation, the real UDP transport, the
/// pump's own queue and the four batches. Timing is controlled by a fake clock and by positive polls, never by fixed delays.
/// Q-prefix callsigns only (NFR-021).
/// </summary>
public sealed class PskReporterServiceTests
{
    private const double Dial = 14.074;

    private sealed class Rig : IAsyncDisposable
    {
        public readonly FakeClock Clock = new();
        public readonly FakeConfigStore Store;
        public readonly Channel<DecodeBatch> Queue = Channel.CreateUnbounded<DecodeBatch>();
        public readonly List<FakeTransport> Transports = [];
        public readonly List<(string Host, int Port)> FactoryCalls = [];
        public readonly CapturingLogger<PskReporterService> Log = new();
        public PskIdentity Id = Identity();
        public readonly PskReporterService Service;

        public Rig(bool enabled, Func<TimeSpan>? offset = null)
        {
            Store = new FakeConfigStore(new AppConfig { PskReporter = new PskReporterConfig(enabled: enabled, host: "test.invalid", port: 14739) });
            Service = new PskReporterService(
                Queue.Reader, Store, Clock,
                (host, port) => { var t = new FakeTransport(); lock (Transports) { Transports.Add(t); FactoryCalls.Add((host, port)); } return t; },
                () => Id, Log, firstSendOffset: offset ?? (() => TimeSpan.Zero), tickInterval: TimeSpan.FromHours(1));   // a long tick: the test drives FlushAsync by hand
        }

        public Task StartAsync() => Service.StartAsync(CancellationToken.None);
        public Task SetEnabledAsync(bool enabled) => Store.SaveAsync(Store.Current with { PskReporter = Store.Current.PskReporter with { Enabled = enabled } });
        public void Write(DateTime cycle, params string[] messages) => Queue.Writer.TryWrite(Batch(cycle, Dial, messages.Select(m => Decode(m)).ToArray()));
        public int Factory { get { lock (Transports) return FactoryCalls.Count; } }

        public async ValueTask DisposeAsync()
        {
            await Service.StopAsync(CancellationToken.None);
            Service.Dispose();
        }
    }

    // ── FR-088: T8 inert ─────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-088: T8: disabled through a full run of batches - the socket factory is not called, nothing is queued; enabling later starts from nothing")]
    public async Task T8_Disabled_IsInert()
    {
        await using var rig = new Rig(enabled: false);
        await rig.StartAsync();
        for (int i = 0; i < 20; i++) rig.Write(T0.AddSeconds(15 * i), $"CQ Q1A{(char)('A' + i)}B JO22");

        // Positive wait: the reader loop has consumed every batch (it handles them in order, discarding while disabled).
        await Poll.UntilAsync(() => rig.Queue.Reader.Count == 0);
        rig.Service.IsActive.Should().BeFalse();
        rig.Factory.Should().Be(0, "no socket, and so no DNS, while disabled");
        rig.Service.Engine.PendingCount.Should().Be(0);

        // Enabling afterwards: only batches arriving from now on count (the 20 above were discarded unread).
        await rig.SetEnabledAsync(true);
        rig.Service.IsActive.Should().BeTrue();
        rig.Write(T0.AddMinutes(10), "CQ Q2ZZZ JO22");
        await Poll.UntilAsync(() => rig.Service.Engine.PendingCount + (rig.Transports.Sum(t => t.SentCount)) >= 1);
        rig.Factory.Should().Be(1);
        (rig.Service.Engine.Sequence + (uint)rig.Service.Engine.PendingCount).Should().Be(1u, "exactly the one batch that arrived while enabled");
    }

    // ── FR-092: the first-send offset is taken from the delegate, once per enabled period ───────────────────────────

    [Fact(DisplayName = "FR-092: T10: the first send follows the 0-60 s offset (nothing at 41 s, the datagram at 42 s) and a disable-then-enable takes a fresh offset")]
    public async Task T10_FirstSendOffset_IsUsed_AndFreshPerEnable()
    {
        var offsets = new Queue<TimeSpan>([TimeSpan.FromSeconds(42), TimeSpan.FromSeconds(17)]);
        await using var rig = new Rig(enabled: true, offset: () => offsets.Dequeue());
        await rig.StartAsync();
        offsets.Count.Should().Be(1, "one offset was taken for this enabled period");

        void Ingest(string msg) => rig.Service.Engine.Ingest(Batch(rig.Clock.UtcNow, Dial, Decode(msg)), rig.Clock.UtcNow);
        Ingest("CQ Q1ABC JO22");

        rig.Clock.Advance(TimeSpan.FromSeconds(41));
        await rig.Service.FlushAsync(CancellationToken.None);
        rig.Transports[0].SentCount.Should().Be(0, "41 s is before the 42 s offset");

        rig.Clock.Advance(TimeSpan.FromSeconds(1));
        await rig.Service.FlushAsync(CancellationToken.None);
        rig.Transports[0].SentCount.Should().Be(1, "the first window falls at the offset");

        await rig.SetEnabledAsync(false);
        await rig.SetEnabledAsync(true);
        offsets.Count.Should().Be(0, "a new enabled period takes a fresh offset from the delegate");
        Ingest("CQ Q2DEF JO22");
        rig.Clock.Advance(TimeSpan.FromSeconds(16));
        await rig.Service.FlushAsync(CancellationToken.None);
        rig.Transports[1].SentCount.Should().Be(0, "16 s is before the new 17 s offset");
        rig.Clock.Advance(TimeSpan.FromSeconds(1));
        await rig.Service.FlushAsync(CancellationToken.None);
        rig.Transports[1].SentCount.Should().Be(1);
    }

    // ── FR-092: T15 one source port ──────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-092: T15: several datagrams in one enabled period use ONE socket (factory called once); enabled false then true creates a new one")]
    public async Task T15_OneSocketPerEnabledPeriod()
    {
        await using var rig = new Rig(enabled: true);
        await rig.StartAsync();
        rig.Factory.Should().Be(1);

        for (int i = 0; i < 3; i++)
        {
            rig.Service.Engine.Ingest(Batch(rig.Clock.UtcNow, Dial, Decode($"CQ Q1A{(char)('A' + i)}B JO22")), rig.Clock.UtcNow);
            await rig.Service.FlushAsync(CancellationToken.None);
            rig.Clock.Advance(PskReporterEngine.SendWindow);
        }
        rig.Transports.Should().ContainSingle();
        rig.Transports[0].SentCount.Should().Be(3, "every datagram of the period went through the one socket");
        rig.Factory.Should().Be(1, "never one socket per window");

        await rig.SetEnabledAsync(false);
        rig.Transports[0].Disposed.Should().BeTrue();
        rig.Service.IsActive.Should().BeFalse();
        await rig.SetEnabledAsync(true);
        rig.Factory.Should().Be(2, "a new enabled period is a new socket");
        rig.Service.Engine.Sequence.Should().Be(3u, "the sequence belongs to the process, not to the socket");
    }

    // ── FR-093: T9 failure isolation ─────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-093: T9: a socket that throws on send never reaches the caller, logs one Warning per window, and the next window retries")]
    public async Task T9_SocketThrows_IsContained_AndRetried()
    {
        await using var rig = new Rig(enabled: true);
        await rig.StartAsync();
        rig.Transports[0].Throw = true;

        rig.Service.Engine.Ingest(Batch(rig.Clock.UtcNow, Dial, Decode("CQ Q1ABC JO22")), rig.Clock.UtcNow);
        await rig.Service.FlushAsync(CancellationToken.None);            // does not throw
        await rig.Service.FlushAsync(CancellationToken.None);            // same window: no second attempt, no second Warning
        rig.Log.Count(LogLevel.Warning).Should().Be(1);
        rig.Transports[0].SentCount.Should().Be(0);
        rig.Service.Engine.PendingCount.Should().Be(1, "the record is kept for the retry");

        rig.Transports[0].Throw = false;
        rig.Clock.Advance(PskReporterEngine.SendWindow);
        await rig.Service.FlushAsync(CancellationToken.None);
        rig.Transports[0].SentCount.Should().Be(1, "the next window retried and succeeded");
        rig.Service.Engine.PendingCount.Should().Be(0);
    }

    [Fact(DisplayName = "FR-093: T9: an exception in a send path never escapes into the queue reader - the service keeps consuming batches")]
    public async Task T9_ReaderLoopSurvives()
    {
        await using var rig = new Rig(enabled: true);
        await rig.StartAsync();
        rig.Transports[0].Throw = true;

        rig.Write(T0, "CQ Q1ABC JO22");
        await Poll.UntilAsync(() => rig.Service.Engine.PendingCount >= 1 || rig.Log.Count(LogLevel.Warning) >= 1);
        rig.Write(T0.AddSeconds(15), "CQ Q2DEF JO22");
        await Poll.UntilAsync(() => rig.Service.Engine.PendingCount >= 2, timeoutMessage: () => "the second batch was not consumed after a send failure");
    }

    // ── FR-091: T11 the service's own queue holds all four batches ───────────────────────────────────────────────────

    [Fact(DisplayName = "FR-091: T11: the service's own queue has the QSO sizing - 10 batches with the coherent fallback on, 8 off, DropOldest - and is not the capacity-2 channel")]
    public void T11_QueueSizing()
    {
        bool fallbackOn = true;
        var queue = LateBatch.CreateQsoQueue(() => fallbackOn);

        for (int i = 1; i <= 10; i++) queue.Writer.TryWrite(new DecodeBatch(new DateTimeOffset(T0, TimeSpan.Zero), [], BatchNumber: 1 + (i - 1) % 4));
        queue.Reader.Count.Should().Be(10, "two cycles of four batches plus two spare: nothing dropped");

        queue.Writer.TryWrite(new DecodeBatch(new DateTimeOffset(T0, TimeSpan.Zero), [], BatchNumber: 4));
        queue.Reader.Count.Should().Be(10, "the 11th drops the oldest (DropOldest)");

        fallbackOn = false;
        queue.Writer.TryWrite(new DecodeBatch(new DateTimeOffset(T0, TimeSpan.Zero), [], BatchNumber: 1));
        queue.Reader.Count.Should().Be(8, "the capacity in force is 8 with the fallback off");
        LateBatch.QsoChannelCapacityFallbackOn.Should().Be(10);
        LateBatch.QsoChannelCapacity.Should().Be(8);
        LateBatch.QsoChannelCapacity.Should().BeGreaterThan(2, "not the capacity-2 external-reporting channel, which would drop batch 1 under later batches");
    }

    // ── FR-091: the pump feeds the queue: all four batches, the dial at capture, never early rows ────────────────────

    [Fact(DisplayName = "FR-091: T11: a fallback-on Deep cycle publishes batches 1 to 4 to the PSK Reporter queue, each carrying the dial frequency at capture")]
    public async Task T11_PumpFeedsAllFourBatches_WithDialAtCapture()
    {
        var psk = LateBatch.CreateQsoQueue(() => true);
        var staged = new Func<Func<int, IReadOnlyList<DecodeResult>, Task>, Task>(async publish =>
        {
            await publish(1, [Decode("CQ Q1ABC JO33")]);
            await publish(2, [Decode("CQ Q1DEF EN37")]);
            await publish(3, [Decode("CQ Q1GHI IO91")]);
            await publish(4, [Decode("CQ Q1JKL FN20")]);
        });
        var pump = BuildPump(psk.Writer, staged);

        await pump.RunAsync(Windows(T0), CancellationToken.None);

        var got = new List<DecodeBatch>();
        while (psk.Reader.TryRead(out var b)) got.Add(b);
        got.Select(b => b.BatchNumber).Should().Equal(1, 2, 3, 4);
        got.Should().OnlyContain(b => b.DialFrequencyMHz == Dial);
    }

    [Fact(DisplayName = "FR-091: a pump without the PSK Reporter writer behaves as before (the property is optional), and the dial is null when the pump had none")]
    public async Task Pump_WithoutWriter_IsUnchanged_AndNoDialIsNull()
    {
        var noWriter = BuildPump(null, publish => publish(1, [Decode("CQ Q1ABC JO33")]));
        await noWriter.RunAsync(Windows(T0), CancellationToken.None);   // must not throw

        var psk = LateBatch.CreateQsoQueue(() => true);
        var noDial = BuildPump(psk.Writer, publish => publish(1, [Decode("CQ Q1ABC JO33")]), currentDial: null, fallbackDial: 0.0, windowDial: null);
        await noDial.RunAsync(WindowsWith(T0, null), CancellationToken.None);
        psk.Reader.TryRead(out var b).Should().BeTrue();
        b!.DialFrequencyMHz.Should().BeNull("no CAT dial and no configured fallback: nothing to report against");
    }

    private static IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> Windows(DateTime c) => WindowsWith(c, Dial);

    private static async IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> WindowsWith(DateTime c, double? dial)
    {
        yield return (new float[180_000], c, dial);
        await Task.CompletedTask;
    }

    private static DecodePump BuildPump(
        ChannelWriter<DecodeBatch>? psk, Func<Func<int, IReadOnlyList<DecodeResult>, Task>, Task> staged,
        double? currentDial = Dial, double fallbackDial = 0.0, double? windowDial = Dial)
    {
        var unbounded = Channel.CreateUnbounded<DecodeBatch>();
        return new DecodePump(new DecodePumpDependencies(
            CurrentDialFrequency:     () => currentDial,
            FallbackDialFrequency:    () => fallbackDial,
            DeriveBand:               _ => "20m",
            SubtractionEnabled:       () => true,
            DecodeSingleBatch:        (_, _, _, _) => Task.FromResult<IReadOnlyList<DecodeResult>>([]),
            DecodeTwoStage:           (_, _, _, _, _) => Task.FromResult<IReadOnlyList<DecodeResult>>([]),
            ApplyNoiseSuppression:    r => r,
            PublishToPanel:           _ => Task.CompletedTask,
            AppendAllTxt:             (_, _, _) => Task.CompletedTask,
            EnqueueArchive:           (_, _, _, _, _) => { },
            AdmitNewValues:           _ => null,
            PublishFilterState:       _ => { },
            AnswererChannel:          unbounded.Writer,
            CallerChannel:            unbounded.Writer,
            ExternalReportingChannel: unbounded.Writer,
            Logger:                   Microsoft.Extensions.Logging.Abstractions.NullLogger.Instance)
        {
            DecodeStaged       = (_, _, _, publishBatch, _) => staged(publishBatch),
            DecodingDeep       = () => true,
            CoherentFallbackOn = () => true,
            PskReporterChannel = psk,
        });
    }

    // ── FR-092: T15 the real transport ───────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-092: T15: the real transport sends from one IPv4 socket that is not bound to 4739 - two datagrams arrive from the same source endpoint")]
    public async Task T15_RealTransport_OneIPv4SourcePort_NotBoundTo4739()
    {
        using var listener = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
        int port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;
        var resolved = new List<string>();
        using var transport = new UdpPskTransport("collector.test", port, (host, _) => { resolved.Add(host); return Task.FromResult(new[] { IPAddress.IPv6Loopback, IPAddress.Loopback }); });
        transport.LocalEndPoint.Should().BeNull("nothing is bound, and nothing resolved, before the first send");
        resolved.Should().BeEmpty();

        await transport.SendAsync([1, 2, 3, 4], CancellationToken.None);
        await transport.SendAsync([5, 6, 7, 8], CancellationToken.None);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var first  = await listener.ReceiveAsync(cts.Token);
        var second = await listener.ReceiveAsync(cts.Token);
        first.RemoteEndPoint.Should().Be(second.RemoteEndPoint, "one source port for the life of the socket");
        first.RemoteEndPoint.AddressFamily.Should().Be(AddressFamily.InterNetwork);
        first.RemoteEndPoint.Port.Should().NotBe(4739);
        transport.LocalEndPoint!.Port.Should().NotBe(4739);
        first.Buffer.Should().Equal(1, 2, 3, 4);
    }

    [Fact(DisplayName = "FR-093: T9: a host that does not resolve to an IPv4 address makes the real transport throw (the service contains it)")]
    public async Task T9_RealTransport_NoIPv4_Throws()
    {
        using var transport = new UdpPskTransport("collector.test", 4739, (_, _) => Task.FromResult(new[] { IPAddress.IPv6Loopback }));
        Func<Task> act = () => transport.SendAsync([1], CancellationToken.None);
        await act.Should().ThrowAsync<SocketException>();
    }
}
