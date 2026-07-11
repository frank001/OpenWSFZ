using System.Buffers.Binary;
using System.Net;
using System.Net.Sockets;
using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Integration tests for <see cref="ExternalReportingService"/> (gridtracker-udp-reporting,
/// tasks 3.7 and 4.6). Uses real loopback <see cref="UdpClient"/>s — both as fake targets
/// (outbound assertions) and as synthetic inbound senders — per
/// <c>specs/external-reporting/spec.md</c>'s scenarios.
/// </summary>
[Trait("Category", "Integration")]
public sealed class ExternalReportingServiceTests
{
    private sealed class MutableConfigStore : IConfigStore
    {
        private AppConfig _current;
        public MutableConfigStore(AppConfig initial) => _current = initial;
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            _current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    private static int GetFreeUdpPort()
    {
        using var probe = new UdpClient(0, AddressFamily.InterNetwork);
        return ((IPEndPoint)probe.Client.LocalEndPoint!).Port;
    }

    private static IServiceProvider BuildServiceProvider(
        IQsoController? qso = null, IExternalReplyTarget? reply = null)
    {
        var services = new ServiceCollection();
        if (qso   is not null) services.AddSingleton(qso);
        if (reply is not null) services.AddSingleton(reply);
        return services.BuildServiceProvider();
    }

    private static ExternalReportingService CreateSut(
        IConfigStore configStore, ChannelReader<DecodeBatch> channelReader,
        IServiceProvider? serviceProvider = null,
        TimeSpan? heartbeatInterval = null, TimeSpan? statusPollInterval = null)
        => new(
            channelReader,
            configStore,
            serviceProvider ?? BuildServiceProvider(),
            NullLogger<ExternalReportingService>.Instance,
            catState: null,
            heartbeatInterval:  heartbeatInterval  ?? TimeSpan.FromSeconds(30),
            statusPollInterval: statusPollInterval ?? TimeSpan.FromMilliseconds(50));

    /// <summary>Receives up to <paramref name="maxDatagrams"/> datagrams within the timeout, or fewer if it elapses.</summary>
    private static async Task<List<byte[]>> ReceiveAllAsync(
        UdpClient listener, int maxDatagrams, TimeSpan timeout)
    {
        var received = new List<byte[]>();
        var deadline = DateTime.UtcNow + timeout;
        while (received.Count < maxDatagrams && DateTime.UtcNow < deadline)
        {
            using var cts = new CancellationTokenSource(deadline - DateTime.UtcNow);
            try
            {
                var result = await listener.ReceiveAsync(cts.Token).ConfigureAwait(false);
                received.Add(result.Buffer);
            }
            catch (OperationCanceledException) { break; }
        }
        return received;
    }

    private static WsjtxDatagram.MessageType ReadMessageType(byte[] datagram)
        => (WsjtxDatagram.MessageType)BinaryPrimitives.ReadUInt32BigEndian(datagram.AsSpan(8, 4));

    // ── Outbound: two simultaneous targets (task 3.7) ───────────────────────

    [Fact(DisplayName = "FR-053: Two enabled targets both receive a Decode datagram")]
    public async Task TwoEnabledTargets_BothReceiveDecode()
    {
        var port1 = GetFreeUdpPort();
        var port2 = GetFreeUdpPort();
        using var listener1 = new UdpClient(port1);
        using var listener2 = new UdpClient(port2);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets:
                [
                    new ExternalReportingTarget("A", "127.0.0.1", port1, true),
                    new ExternalReportingTarget("B", "127.0.0.1", port2, true),
                ])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q1TST JO22")]));

            // The timer loop also fires an immediate Heartbeat+Status burst on start (heartbeat
            // interval is 30 s in CreateSut, but the FIRST tick always fires since
            // _lastHeartbeatSentUtc starts at DateTimeOffset.MinValue) — capture enough
            // datagrams to see past that burst to the Clear+Decode pair.
            var recv1 = await ReceiveAllAsync(listener1, 4, TimeSpan.FromSeconds(3));
            var recv2 = await ReceiveAllAsync(listener2, 4, TimeSpan.FromSeconds(3));

            recv1.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Decode);
            recv2.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Decode);
            recv1.Should().Contain(d => Encoding_UTF8_Contains(d, "Q1TST"));
            recv2.Should().Contain(d => Encoding_UTF8_Contains(d, "Q1TST"));
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    private static bool Encoding_UTF8_Contains(byte[] datagram, string needle)
        => System.Text.Encoding.UTF8.GetString(datagram).Contains(needle);

    [Fact(DisplayName = "FR-053: Disabled target never receives a datagram")]
    public async Task DisabledTarget_NeverReceives()
    {
        var enabledPort  = GetFreeUdpPort();
        var disabledPort = GetFreeUdpPort();
        using var enabledListener  = new UdpClient(enabledPort);
        using var disabledListener = new UdpClient(disabledPort);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets:
                [
                    new ExternalReportingTarget("Enabled",  "127.0.0.1", enabledPort,  true),
                    new ExternalReportingTarget("Disabled", "127.0.0.1", disabledPort, false),
                ])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q1TST JO22")]));

            var enabledRecv  = await ReceiveAllAsync(enabledListener, 2, TimeSpan.FromSeconds(3));
            var disabledRecv = await ReceiveAllAsync(disabledListener, 1, TimeSpan.FromMilliseconds(500));

            enabledRecv.Should().NotBeEmpty();
            disabledRecv.Should().BeEmpty("a disabled target must receive no datagram of any type");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    // ── Outbound: QSOLogged (task 3.5/3.7) ──────────────────────────────────

    [Fact(DisplayName = "FR-053: NotifyQsoLogged sends a QSOLogged datagram to the enabled target")]
    public async Task NotifyQsoLogged_SendsQsoLoggedDatagram()
    {
        var port = GetFreeUdpPort();
        using var listener = new UdpClient(port);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            sut.NotifyQsoLogged(new QsoRecord
            {
                PartnerCallsign  = "Q1TST",
                PartnerGrid      = "JO22",
                RstSent          = "+05",
                RstRcvd          = "-03",
                QsoStartUtc      = new DateTime(2026, 7, 12, 14, 29, 15, DateTimeKind.Utc),
                QsoEndUtc        = new DateTime(2026, 7, 12, 14, 30, 0, DateTimeKind.Utc),
                OperatorCallsign = "Q1OFZ",
                OperatorGrid     = "JO33",
                DialFrequencyMHz = 14.074,
            });

            // The timer loop also fires an immediate Heartbeat+Status burst on start — capture
            // enough datagrams to see past it to the QSOLogged datagram.
            var recv = await ReceiveAllAsync(listener, 3, TimeSpan.FromSeconds(3));

            recv.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.QsoLogged);
            recv.Should().Contain(d => Encoding_UTF8_Contains(d, "Q1TST"));
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    // ── Outbound: Close on shutdown (task 3.6) ──────────────────────────────

    [Fact(DisplayName = "FR-053: StopAsync sends a Close datagram before closing sockets")]
    public async Task StopAsync_SendsCloseDatagram()
    {
        var port = GetFreeUdpPort();
        using var listener = new UdpClient(port);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);

        await sut.StopAsync(CancellationToken.None);

        // A Heartbeat/Status may or may not have raced ahead of the immediate StopAsync (timer
        // loop scheduling is not deterministic) — assert Close is present, not that it's the
        // only datagram.
        var recv = await ReceiveAllAsync(listener, 3, TimeSpan.FromSeconds(3));
        recv.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Close);
    }

    // ── Enable/disable posture (spec: "ExternalReportingService is inert by default") ──

    [Fact(DisplayName = "Disabled config opens no outbound socket — nothing is sent")]
    public async Task Disabled_OpensNoSocket()
    {
        var port = GetFreeUdpPort();
        using var listener = new UdpClient(port);

        var config = new AppConfig(); // ExternalReporting defaults: Enabled=false
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q1TST JO22")]));

            var recv = await ReceiveAllAsync(listener, 1, TimeSpan.FromMilliseconds(500));
            recv.Should().BeEmpty("externalReporting.enabled=false must open no sockets and send nothing");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    // ── Inbound: malformed datagram resilience (tasks 2.4/4.1/4.6) ──────────

    [Fact(DisplayName = "FR-054: Inbound listener discards a malformed datagram and keeps accepting well-formed ones")]
    public async Task InboundListener_DiscardsMalformed_ContinuesAccepting()
    {
        var port = GetFreeUdpPort();

        var qso = Substitute.For<IQsoController>();
        qso.AbortAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, BuildServiceProvider(qso: qso));

        using var cts    = new CancellationTokenSource();
        using var sender = new UdpClient();
        await sut.StartAsync(cts.Token);
        try
        {
            await Task.Delay(200); // let Reconcile bind the inbound socket

            // 1) Garbage — must not crash the listener.
            var garbage = new byte[] { 0x01, 0x02, 0x03 };
            await sender.SendAsync(garbage, garbage.Length, "127.0.0.1", port);
            await Task.Delay(200);

            // 2) A well-formed Halt Tx afterward must still be processed.
            var haltTx = new byte[16];
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(0), WsjtxDatagram.Magic);
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(4), WsjtxDatagram.SchemaVersion);
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(8), (uint)WsjtxDatagram.MessageType.HaltTx);
            // Id string: length=0 (empty).
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(12), 0);
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);

            await Task.Delay(500);
            await qso.Received(1).AbortAsync(Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    // ── Inbound: Halt Tx always honoured regardless of honourInboundCommands ──

    [Theory(DisplayName = "FR-054: Halt Tx aborts regardless of honourInboundCommands")]
    [InlineData(false)]
    [InlineData(true)]
    public async Task HaltTx_AlwaysHonoured(bool honourInboundCommands)
    {
        var port = GetFreeUdpPort();
        var qso  = Substitute.For<IQsoController>();
        qso.AbortAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)],
                honourInboundCommands: honourInboundCommands)
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, BuildServiceProvider(qso: qso));

        using var cts    = new CancellationTokenSource();
        using var sender = new UdpClient();
        await sut.StartAsync(cts.Token);
        try
        {
            await Task.Delay(200);

            var haltTx = BuildHaltTxDatagram();
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);

            await Task.Delay(500);
            await qso.Received(1).AbortAsync(Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    private static byte[] BuildHaltTxDatagram()
    {
        var buf = new byte[17];
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(0), WsjtxDatagram.Magic);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(4), WsjtxDatagram.SchemaVersion);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(8), (uint)WsjtxDatagram.MessageType.HaltTx);
        BinaryPrimitives.WriteUInt32BigEndian(buf.AsSpan(12), 0); // Id: empty string
        buf[16] = 1; // AutoTxOnly = true
        return buf;
    }

    // ── Inbound: Reply gated by honourInboundCommands ───────────────────────

    [Fact(DisplayName = "FR-054: Reply is ignored when honourInboundCommands is disabled")]
    public async Task Reply_IgnoredWhenOptedOut()
    {
        var port  = GetFreeUdpPort();
        var reply = Substitute.For<IExternalReplyTarget>();
        reply.TryEngageAsync(Arg.Any<string>(), Arg.Any<CancellationToken>()).Returns(Task.FromResult(true));

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)],
                honourInboundCommands: false)
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, BuildServiceProvider(reply: reply));

        using var cts    = new CancellationTokenSource();
        using var sender = new UdpClient();
        await sut.StartAsync(cts.Token);
        try
        {
            await Task.Delay(200);

            var datagram = BuildReplyDatagram("CQ Q1TST JO22");
            await sender.SendAsync(datagram, datagram.Length, "127.0.0.1", port);

            await Task.Delay(500);
            await reply.DidNotReceive().TryEngageAsync(Arg.Any<string>(), Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    [Fact(DisplayName = "Reply engages the named callsign when honourInboundCommands is enabled")]
    public async Task Reply_EngagesWhenOptedIn()
    {
        var port  = GetFreeUdpPort();
        var reply = Substitute.For<IExternalReplyTarget>();
        reply.TryEngageAsync(Arg.Any<string>(), Arg.Any<CancellationToken>()).Returns(Task.FromResult(true));

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)],
                honourInboundCommands: true)
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, BuildServiceProvider(reply: reply));

        using var cts    = new CancellationTokenSource();
        using var sender = new UdpClient();
        await sut.StartAsync(cts.Token);
        try
        {
            await Task.Delay(200);

            var datagram = BuildReplyDatagram("CQ Q1TST JO22");
            await sender.SendAsync(datagram, datagram.Length, "127.0.0.1", port);

            await Task.Delay(500);
            await reply.Received(1).TryEngageAsync("Q1TST", Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    private static byte[] BuildReplyDatagram(string message)
    {
        var buf = new List<byte>();
        void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
        void I32(int v)  => U32(unchecked((uint)v));
        void Str(string s) { var bytes = System.Text.Encoding.UTF8.GetBytes(s); U32((uint)bytes.Length); buf.AddRange(bytes); }
        void Dbl(double v) { Span<byte> b = stackalloc byte[8]; BinaryPrimitives.WriteInt64BigEndian(b, BitConverter.DoubleToInt64Bits(v)); buf.AddRange(b.ToArray()); }

        U32(WsjtxDatagram.Magic);
        U32(WsjtxDatagram.SchemaVersion);
        U32((uint)WsjtxDatagram.MessageType.Reply);
        Str(""); // Id
        buf.Add(1);           // New
        U32(51300);           // Time
        I32(-10);              // SNR
        Dbl(0.1);              // DeltaTime
        U32(1500);              // DeltaFrequency
        Str("~");               // Mode
        Str(message);            // Message
        buf.Add(0);               // LowConfidence
        return buf.ToArray();
    }

    // ── Inbound: Free Text gated and a no-op ────────────────────────────────

    [Fact(DisplayName = "Free Text is stored when honourInboundCommands is enabled but has no transmission effect")]
    public async Task FreeText_StoredWhenOptedIn_NoTransmissionEffect()
    {
        var port = GetFreeUdpPort();
        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)],
                honourInboundCommands: true)
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts    = new CancellationTokenSource();
        using var sender = new UdpClient();
        await sut.StartAsync(cts.Token);
        try
        {
            await Task.Delay(200);

            var buf = new List<byte>();
            void U32(uint v) { Span<byte> b = stackalloc byte[4]; BinaryPrimitives.WriteUInt32BigEndian(b, v); buf.AddRange(b.ToArray()); }
            void Str(string s) { var bytes = System.Text.Encoding.UTF8.GetBytes(s); U32((uint)bytes.Length); buf.AddRange(bytes); }
            U32(WsjtxDatagram.Magic);
            U32(WsjtxDatagram.SchemaVersion);
            U32((uint)WsjtxDatagram.MessageType.FreeText);
            Str("");
            Str("TEST MSG");
            buf.Add(1);
            await sender.SendAsync(buf.ToArray(), buf.Count, "127.0.0.1", port);

            await Task.Delay(500);
            sut.LastFreeText.Should().Be("TEST MSG");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    // ── Inbound: Close is logged only, never terminates the daemon ─────────

    [Fact(DisplayName = "FR-054: Inbound Close is logged only and the listener keeps running afterward")]
    public async Task InboundClose_DoesNotStopListener()
    {
        var port = GetFreeUdpPort();
        var qso  = Substitute.For<IQsoController>();
        qso.AbortAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, BuildServiceProvider(qso: qso));

        using var cts    = new CancellationTokenSource();
        using var sender = new UdpClient();
        await sut.StartAsync(cts.Token);
        try
        {
            await Task.Delay(200);

            var closeDatagram = WsjtxDatagram.EncodeClose("GridTracker2");
            await sender.SendAsync(closeDatagram, closeDatagram.Length, "127.0.0.1", port);
            await Task.Delay(300);

            // The listener must still be alive: a subsequent Halt Tx is still processed.
            var haltTx = BuildHaltTxDatagram();
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);
            await Task.Delay(500);

            await qso.Received(1).AbortAsync(Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }
}
