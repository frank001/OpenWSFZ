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
using OpenWSFZ.TestSupport;
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

    /// <summary>
    /// Fully-controllable <see cref="ICallsignRegionStore"/> test double for the absolute-
    /// exclusion (Tier 2) tests — an unmapped callsign resolves to <c>null</c> ("unknown region"),
    /// matching <see cref="CallsignRegionStore"/>'s own lookup-miss contract.
    /// </summary>
    private sealed class FakeCallsignRegionStore : ICallsignRegionStore
    {
        private readonly Dictionary<string, RegionInfo?> _map = new(StringComparer.OrdinalIgnoreCase);
        public IReadOnlyList<CallsignRegionEntry> Entries => [];
        public bool IsSeedData => false;
        public void Set(string callsign, RegionInfo? region) => _map[callsign] = region;
        public RegionInfo? TryGetRegion(string callsignToken)
            => _map.TryGetValue(callsignToken, out var region) ? region : null;
        public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
            => TryGetRegion(callsignToken) is { } region ? new CallsignRegionMatch(region, 0) : null;
        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken ct = default)
            => Task.CompletedTask;
    }

    /// <summary>
    /// Probes for a free UDP port by binding, reading the assigned port back, and releasing it —
    /// only safe to use where the returned number is never re-bound by a listener in this process
    /// (a real, observed CI flake: releasing then re-binding by number races anything else on the
    /// box that might claim the same just-freed ephemeral port in between). Test methods that need
    /// to actually receive on the port must NOT use this — bind directly to port 0 and read
    /// <c>LocalEndPoint</c> off that same live socket instead (see e.g. <c>StopAsync_SendsCloseDatagram</c>),
    /// so there is no release-then-rebind gap at all. The remaining <c>GetFreeUdpPort()</c> call
    /// sites below hand the number to the SUT as a target/config port with no test-side bind of
    /// their own (or, for the D-014 port-contention tests, are deliberately racing a fake peer on
    /// purpose — that's the scenario under test, not a bug).
    /// </summary>
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
        ICallsignRegionStore? regionStore = null,
        TimeSpan? heartbeatInterval = null, TimeSpan? statusPollInterval = null)
        => new(
            channelReader,
            configStore,
            serviceProvider ?? BuildServiceProvider(),
            NullLogger<ExternalReportingService>.Instance,
            catState: null,
            regionStore: regionStore,
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
        using var listener1 = new UdpClient(0, AddressFamily.InterNetwork);
        var port1 = ((IPEndPoint)listener1.Client.LocalEndPoint!).Port;
        using var listener2 = new UdpClient(0, AddressFamily.InterNetwork);
        var port2 = ((IPEndPoint)listener2.Client.LocalEndPoint!).Port;

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
            // Region set to a resolvable, non-synthetic entry — this test is about delivery
            // mechanics (two targets), not the absolute exclusion filter; an unset (null) Region
            // would now be unconditionally suppressed as "unknown region" (see the dedicated
            // exclusion tests below) and never reach either target.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q1TST JO22",
                    Region: new RegionInfo(Continent: "EU", Entity: "TestLand", Synthetic: false))]));

            // The timer loop also fires an immediate Heartbeat+Status burst on start (heartbeat
            // interval is 30 s in CreateSut, but the FIRST tick always fires since
            // _lastHeartbeatSentUtc starts at DateTimeOffset.MinValue) — capture enough
            // datagrams to see past that burst to the Decode datagram (no Clear is sent per cycle;
            // see fix-external-reporting-clear-and-reply-filter). margin: 3 = Heartbeat + Status +
            // Decode, the current maximum for this path — bump this if DecodeLoopAsync ever sends
            // one more datagram type ahead of Decode (see tools/check_udp_capture_margin.py).
            var recv1 = await ReceiveAllAsync(listener1, 3, TimeSpan.FromSeconds(3));
            var recv2 = await ReceiveAllAsync(listener2, 3, TimeSpan.FromSeconds(3));

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
        using var enabledListener  = new UdpClient(0, AddressFamily.InterNetwork);
        var enabledPort = ((IPEndPoint)enabledListener.Client.LocalEndPoint!).Port;
        using var disabledListener = new UdpClient(0, AddressFamily.InterNetwork);
        var disabledPort = ((IPEndPoint)disabledListener.Client.LocalEndPoint!).Port;

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

    // ── D-014: inbound bind coexists with a peer already on the target port ─

    /// <summary>
    /// Binds a "fake peer" <see cref="UdpClient"/> to <paramref name="port"/> with
    /// <c>ReuseAddress</c> set — mirroring the real WSJT-X-protocol reference behaviour (Qt's
    /// <c>ShareAddress | ReuseAddressHint</c> bind option, which every WSJT-X-protocol client
    /// including GridTracker2 uses) so this test double is a faithful stand-in for "GridTracker2
    /// is already running and bound to this port before OpenWSFZ starts" — the realistic
    /// real-world startup order D-014 was found against.
    /// </summary>
    private static UdpClient CreateFakePeer(int port)
    {
        var client = new UdpClient(AddressFamily.InterNetwork);
        client.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
        client.Client.Bind(new IPEndPoint(IPAddress.Any, port));
        return client;
    }

    /// <summary>
    /// Reads the private <c>_inboundClient</c> field via reflection to assert the bind's own
    /// success/failure directly, independent of the OS's delivery semantics for a shared port
    /// (see the class-level remarks on the two D-014 tests below for why delivery itself is not
    /// asserted while a peer remains bound to the same port).
    /// </summary>
    private static UdpClient? GetInboundClient(ExternalReportingService sut)
    {
        var field = typeof(ExternalReportingService).GetField(
            "_inboundClient", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        return (UdpClient?)field!.GetValue(sut);
    }

    /// <summary>
    /// Polls until <c>Reconcile</c> has bound the inbound UDP socket, replacing the fixed
    /// "let Reconcile attempt the bind" delays that used to precede sending an inbound datagram
    /// (fix-flaky-test-delay-synchronization). Sending before the socket is bound would silently
    /// drop the datagram; the bound <c>_inboundClient</c> is the real, observable barrier.
    /// </summary>
    private static Task WaitForInboundBoundAsync(ExternalReportingService sut)
        => Poll.UntilAsync(() => GetInboundClient(sut) is not null, timeout: TimeSpan.FromSeconds(5),
            timeoutMessage: () => "inbound UDP socket was never bound by Reconcile");

    /// <remarks>
    /// <para>
    /// <strong>Windows platform note:</strong> empirically probed while writing this test (see
    /// dev-tasks/2026-07-12-gridtracker-udp-reporting-review-fixes.md §3 for the review that
    /// found D-014): when two <see cref="UdpClient"/>s share one local port via
    /// <c>SO_REUSEADDR</c>, Windows delivers an incoming unicast datagram to only the
    /// <em>first-bound</em> socket — never both, and (unlike Linux <c>SO_REUSEPORT</c>) with no
    /// load-balancing fan-out. This is a real, pre-existing OS/platform limitation, not something
    /// this fix's `ReuseAddress` call can or is scoped to solve — true concurrent multi-listener
    /// delivery on one port on one machine would need UDP multicast, which design.md's own "Open
    /// Questions" section already defers as unimplemented, out of scope here.
    /// </para>
    /// <para>
    /// What D-014 Part A actually fixes, and what this test actually proves, is narrower and
    /// still the entire point of the defect: before the fix, the bind <em>throws</em> when a peer
    /// already owns the port, the exception is swallowed, and <c>_inboundClient</c> stays
    /// permanently <c>null</c> — no message of any kind, from any sender, at any later time,
    /// would ever reach the daemon, because nothing ever retries the bind outside of a config
    /// save. This test proves the bind no longer fails that way: it binds successfully (directly
    /// verified via <c>_inboundClient</c>) despite a peer having already claimed the port at
    /// daemon-startup time, and a Halt Tx sent after that peer disconnects <em>is</em> received —
    /// which could only happen if the original bind actually succeeded, since <c>Reconcile</c> is
    /// never called again in this test to retry it.
    /// </para>
    /// </remarks>
    [Fact(DisplayName = "D-014 AC-1: inbound listener binds successfully when a peer already owns the target port at startup")]
    public async Task InboundBind_SucceedsWhenTargetPortAlreadyBoundByPeer()
    {
        var port = GetFreeUdpPort();

        var qso = Substitute.For<IQsoController>();
        qso.AbortAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("GridTracker2", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, BuildServiceProvider(qso: qso));

        using var cts = new CancellationTokenSource();

        // The peer (e.g. GridTracker2) is already running and bound to this port BEFORE the
        // daemon starts — the normal real-world case D-014 was found against. Pre-fix, this
        // alone was enough to leave the daemon's inbound listener permanently unbound.
        var fakePeer = CreateFakePeer(port);
        try
        {
            await sut.StartAsync(cts.Token);
            await WaitForInboundBoundAsync(sut);

            GetInboundClient(sut).Should().NotBeNull(
                "the bind must succeed (via ReuseAddress) even though a peer already owns the port " +
                "at daemon-startup time — D-014's exact defect was this staying permanently null");
        }
        finally
        {
            fakePeer.Dispose(); // release the port so the reply step below is unambiguous (see remarks)
        }

        try
        {
            using var sender = new UdpClient();
            var haltTx = BuildHaltTxDatagram();
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);

            await Poll.WaitForCallAsync(() => qso.ReceivedCalls(), nameof(IQsoController.AbortAsync),
                timeout: TimeSpan.FromSeconds(5));
            await qso.Received(1).AbortAsync(Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    /// <remarks>
    /// <strong>Linux platform note (2026-07-12 CI failure fix):</strong> this test originally
    /// proved the point by racing a second socket (<c>fakePeer</c>) bound to the same shared port
    /// to receive the daemon's own outbound send over the wire — reasoning that, per the Windows
    /// finding documented on <see cref="InboundBind_SucceedsWhenTargetPortAlreadyBoundByPeer"/>,
    /// the first-bound socket wins delivery. That does not generalise: on Linux, unicast delivery
    /// to a <c>SO_REUSEADDR</c>-shared UDP port has historically gone to the <em>last</em>-bound
    /// socket, not the first — and in this test the daemon's own <c>_inboundClient</c> binds
    /// second (inside <c>Reconcile</c>, after <c>fakePeer</c>). If that Linux behaviour applies,
    /// the daemon's own outbound send back to <c>127.0.0.1:port</c> is delivered to the daemon's
    /// own <c>_inboundClient</c>/<c>InboundLoopAsync</c> rather than to <c>fakePeer</c>, which is
    /// exactly what made this test time out on <c>ubuntu-latest</c> (see
    /// dev-tasks/2026-07-12-gridtracker-udp-reporting-linux-ci-failure.md and design.md Decision 7's
    /// Linux addendum). Racing OS-specific same-host delivery arbitration is inherently unportable,
    /// so this test now asserts the *sending* socket's own local port directly instead — deterministic
    /// on every platform, and still exactly what AC-2 requires: proof that the primary target's
    /// outbound sends originate from the shared bound inbound port, since
    /// <see cref="ExternalReportingService"/>'s own <c>SendToAllEnabledAsync</c> resolves the
    /// primary target's client as <c>_inboundClient ?? _primaryFallbackClient</c> — a bound,
    /// non-null <c>_inboundClient</c> on the target's port is exactly the condition under which
    /// that fallback expression selects the shared socket.
    /// </remarks>
    [Fact(DisplayName = "D-014 AC-2: outbound sends to the primary target originate from the shared inbound port")]
    public async Task OutboundToPrimaryTarget_UsesSharedInboundPort()
    {
        var port = GetFreeUdpPort();

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("GridTracker2", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        // A peer (e.g. GridTracker2) already bound to the port before the daemon starts — the
        // realistic startup order D-014 targets. It is never used to observe delivery here (see
        // the remarks above for why that's no longer safe); it exists only so the shared-bind
        // assertion below is exercised under the same contended-port condition as production.
        using var fakePeer = CreateFakePeer(port);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            await WaitForInboundBoundAsync(sut);

            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q1TST JO22")]));

            // Assert the SENDING socket's own local port directly, rather than inferring it by
            // racing a second socket to receive the packet over the wire (platform-dependent —
            // see the remarks above). A bound _inboundClient on the target's port is exactly the
            // condition under which SendToAllEnabledAsync's own `_inboundClient ??
            // _primaryFallbackClient` resolution picks the shared socket for the primary target.
            var inboundClient = GetInboundClient(sut);
            inboundClient.Should().NotBeNull(
                "the shared inbound socket must be bound so the primary target's outbound sends " +
                "route through it — D-014 Part B's entire point");
            ((IPEndPoint)inboundClient!.Client.LocalEndPoint!).Port.Should().Be(port,
                "the primary target's outbound sends must originate from the shared bound inbound " +
                "port, not a separate ephemeral socket, so a peer's reply-to-sender-port semantics " +
                "(e.g. GridTracker2 replying to whatever port it last saw traffic from) reach us");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    // ── Absolute exclusion of synthetic/unknown-region traffic (no exceptions) ──
    //
    // dev-tasks/2026-07-12-gridtracker-udp-reporting-review-fixes.md §4. Every test in this
    // section runs with DecodeNoiseSuppressionConfig.SuppressUnknownRegion=false AND
    // SuppressSynthetic=false — the exact condition that lets unknown/synthetic decodes reach
    // this service's inbound channel today — to prove the exclusion inside
    // ExternalReportingService itself is unconditional and does not depend on that operator
    // setting remaining on.

    [Fact(DisplayName = "AC-3: unknown-region and synthetic decodes are never sent, even with suppression off")]
    public async Task Decode_UnknownRegionAndSynthetic_NeverSentEvenWithSuppressionOff()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)]),
            DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig
            {
                SuppressUnknownRegion = false,
                SuppressSynthetic     = false,
            },
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [
                new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q1NORM JO22",
                    Region: new RegionInfo(Continent: "EU", Entity: "TestLand", Synthetic: false)),
                new DecodeResult(Time: "12:00:00", Snr: -6, Dt: 0.1, FreqHz: 1600, Message: "CQ Q9UNK JO22",
                    Region: null),
                new DecodeResult(Time: "12:00:00", Snr: -7, Dt: 0.1, FreqHz: 1700, Message: "CQ Q1SYN JO22",
                    Region: new RegionInfo(Continent: null, Entity: "Synthetic (R&R Study)", Synthetic: true)),
            ]));

            var recv = await ReceiveAllAsync(listener, 4, TimeSpan.FromSeconds(3));

            var decodeDatagrams = recv.Where(d => ReadMessageType(d) == WsjtxDatagram.MessageType.Decode).ToList();
            decodeDatagrams.Should().HaveCount(1, "only the normal (resolvable, non-synthetic) decode may be sent");
            Encoding_UTF8_Contains(decodeDatagrams[0], "Q1NORM").Should().BeTrue();
            recv.Should().NotContain(d => Encoding_UTF8_Contains(d, "Q9UNK"));
            recv.Should().NotContain(d => Encoding_UTF8_Contains(d, "Q1SYN"));
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    [Fact(DisplayName = "fix-external-reporting-clear-and-reply-filter: no Clear is ever sent from the decode loop")]
    public async Task Decode_AllResultsSuppressed_NeverSendsClear()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)]),
            DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig
            {
                SuppressUnknownRegion = false,
                SuppressSynthetic     = false,
            },
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [
                new DecodeResult(Time: "12:00:00", Snr: -6, Dt: 0.1, FreqHz: 1600, Message: "CQ Q9UNK JO22", Region: null),
                new DecodeResult(Time: "12:00:00", Snr: -7, Dt: 0.1, FreqHz: 1700, Message: "CQ Q1SYN JO22",
                    Region: new RegionInfo(Continent: null, Entity: "Synthetic (R&R Study)", Synthetic: true)),
            ]));

            // No Clear datagram is ever sent from the decode loop (fix-external-reporting-clear-
            // and-reply-filter) — only the initial Heartbeat+Status burst is expected here, so a
            // short timeout requesting more datagrams than will ever arrive is deliberate: it
            // proves absence rather than timing out waiting for a message that will never come.
            var recv = await ReceiveAllAsync(listener, 3, TimeSpan.FromSeconds(1));

            recv.Should().NotContain(d => ReadMessageType(d) == WsjtxDatagram.MessageType.Clear,
                "Clear must never be sent from the per-cycle decode loop, regardless of how many " +
                "decodes the exclusion filter removes — real WSJT-X only sends Clear on an operator " +
                "erase action or graceful shutdown");
            recv.Should().NotContain(d => ReadMessageType(d) == WsjtxDatagram.MessageType.Decode,
                "every decode in this batch is unknown-region or synthetic — none may be sent");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    [Fact(DisplayName = "fix-external-reporting-clear-and-reply-filter: StopAsync sends Clear to every enabled target")]
    public async Task StopAsync_SendsClearToEveryEnabledTarget()
    {
        using var listener1 = new UdpClient(0, AddressFamily.InterNetwork);
        var port1 = ((IPEndPoint)listener1.Client.LocalEndPoint!).Port;
        using var listener2 = new UdpClient(0, AddressFamily.InterNetwork);
        var port2 = ((IPEndPoint)listener2.Client.LocalEndPoint!).Port;

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

        // Wait for the initial Heartbeat+Status burst to actually be sent (proving the send loop
        // initialized) before stopping, rather than a blind fixed delay. Consuming these datagrams
        // from listener1 is safe — the assertions below only require Clear+Close, and listener2's
        // own buffered burst is untouched.
        (await ReceiveAllAsync(listener1, 2, TimeSpan.FromSeconds(3)))
            .Should().NotBeEmpty("the initial Heartbeat+Status burst must be sent before stop");
        await sut.StopAsync(CancellationToken.None);

        // Capture ONE generous batch spanning any residual initial-burst datagrams and the
        // stop-time Clear/Close, and assert with Should().Contain — robust to extra noise, matching
        // every other test in this file (e.g. TwoEnabledTargets_BothReceiveDecode above). Not a
        // drain-to-an-exact-count (that was flaky: a slow/delayed leftover burst datagram could
        // arrive just after an exact-count drain "finished," then crowd Close out of the receive's
        // own exact cap). margin: 6 requested against a maximum of 4 ever sent (Heartbeat, Status,
        // Clear, Close) — 2 slots of deliberate headroom.
        var recv1 = await ReceiveAllAsync(listener1, 6, TimeSpan.FromSeconds(3));
        var recv2 = await ReceiveAllAsync(listener2, 6, TimeSpan.FromSeconds(3));

        recv1.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Clear,
            "graceful shutdown SHALL send Clear to every enabled target");
        recv1.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Close,
            "graceful shutdown SHALL send Close alongside Clear, as before");
        recv2.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Clear,
            "graceful shutdown SHALL send Clear to every enabled target");
        recv2.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Close,
            "graceful shutdown SHALL send Close alongside Clear, as before");
    }

    [Fact(DisplayName = "AC-4: Status blanks DxCall/DxGrid for a synthetic active partner")]
    public async Task Status_SyntheticPartner_DxCallAndGridBlanked()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var qso = Substitute.For<IQsoController>();
        qso.Partner.Returns("Q1SYN");
        qso.Keying.Returns(true);

        var regionStore = new FakeCallsignRegionStore();
        regionStore.Set("Q1SYN", new RegionInfo(Continent: null, Entity: "Synthetic (R&R Study)", Synthetic: true));

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)]),
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader,
            BuildServiceProvider(qso: qso), regionStore: regionStore,
            heartbeatInterval: TimeSpan.FromSeconds(30), statusPollInterval: TimeSpan.FromMilliseconds(50));

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            var recv = await ReceiveAllAsync(listener, 2, TimeSpan.FromSeconds(3));

            var statusDatagrams = recv.Where(d => ReadMessageType(d) == WsjtxDatagram.MessageType.Status).ToList();
            statusDatagrams.Should().NotBeEmpty();
            statusDatagrams.Should().NotContain(d => Encoding_UTF8_Contains(d, "Q1SYN"),
                "DxCall must never name a synthetic partner, even while an active QSO with it is in progress");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    [Fact(DisplayName = "AC-4 regression: Status still populates DxCall for a normal, resolvable partner")]
    public async Task Status_NormalPartner_DxCallPopulated()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var qso = Substitute.For<IQsoController>();
        qso.Partner.Returns("Q1NORM");
        qso.Keying.Returns(false);

        var regionStore = new FakeCallsignRegionStore();
        regionStore.Set("Q1NORM", new RegionInfo(Continent: "EU", Entity: "TestLand", Synthetic: false));

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)]),
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader,
            BuildServiceProvider(qso: qso), regionStore: regionStore,
            heartbeatInterval: TimeSpan.FromSeconds(30), statusPollInterval: TimeSpan.FromMilliseconds(50));

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            var recv = await ReceiveAllAsync(listener, 2, TimeSpan.FromSeconds(3));

            var statusDatagrams = recv.Where(d => ReadMessageType(d) == WsjtxDatagram.MessageType.Status).ToList();
            statusDatagrams.Should().Contain(d => Encoding_UTF8_Contains(d, "Q1NORM"),
                "a real, resolvable partner callsign must still appear in DxCall as before");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    [Fact(DisplayName = "AC-4: NotifyQsoLogged never sends for a synthetic or unknown-region partner")]
    public async Task NotifyQsoLogged_SyntheticOrUnknownPartner_NeverSent()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var regionStore = new FakeCallsignRegionStore();
        regionStore.Set("Q1SYN", new RegionInfo(Continent: null, Entity: "Synthetic (R&R Study)", Synthetic: true));
        // "Q9UNK" left unmapped — resolves to null ("unknown region"), matching a lookup miss.

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)]),
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, regionStore: regionStore);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            QsoRecord MakeRecord(string partner) => new()
            {
                PartnerCallsign  = partner,
                PartnerGrid      = "JO22",
                RstSent          = "+05",
                RstRcvd          = "-03",
                QsoStartUtc      = new DateTime(2026, 7, 12, 14, 29, 15, DateTimeKind.Utc),
                QsoEndUtc        = new DateTime(2026, 7, 12, 14, 30, 0, DateTimeKind.Utc),
                OperatorCallsign = "Q1OFZ",
                OperatorGrid     = "JO33",
                DialFrequencyMHz = 14.074,
            };

            sut.NotifyQsoLogged(MakeRecord("Q1SYN"));
            sut.NotifyQsoLogged(MakeRecord("Q9UNK"));

            // Give both sends a chance to arrive if they were (incorrectly) not suppressed.
            var recv = await ReceiveAllAsync(listener, 4, TimeSpan.FromMilliseconds(800));

            recv.Should().NotContain(d => ReadMessageType(d) == WsjtxDatagram.MessageType.QsoLogged,
                "no QSOLogged datagram may ever be sent for a synthetic or unknown-region partner");
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }

    [Fact(DisplayName = "AC-4 regression: NotifyQsoLogged still sends for a normal, resolvable partner")]
    public async Task NotifyQsoLogged_NormalPartner_StillSent()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var regionStore = new FakeCallsignRegionStore();
        regionStore.Set("Q1NORM", new RegionInfo(Continent: "EU", Entity: "TestLand", Synthetic: false));

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)]),
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        var sut     = CreateSut(store, channel.Reader, regionStore: regionStore);

        using var cts = new CancellationTokenSource();
        await sut.StartAsync(cts.Token);
        try
        {
            sut.NotifyQsoLogged(new QsoRecord
            {
                PartnerCallsign  = "Q1NORM",
                PartnerGrid      = "JO22",
                RstSent          = "+05",
                RstRcvd          = "-03",
                QsoStartUtc      = new DateTime(2026, 7, 12, 14, 29, 15, DateTimeKind.Utc),
                QsoEndUtc        = new DateTime(2026, 7, 12, 14, 30, 0, DateTimeKind.Utc),
                OperatorCallsign = "Q1OFZ",
                OperatorGrid     = "JO33",
                DialFrequencyMHz = 14.074,
            });

            // margin: 3 = Heartbeat + Status + QsoLogged, the current maximum for this path
            // (StopAsync is never called here, so no Clear/Close compete for the capture window).
            var recv = await ReceiveAllAsync(listener, 3, TimeSpan.FromSeconds(3));

            recv.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.QsoLogged);
            recv.Should().Contain(d => Encoding_UTF8_Contains(d, "Q1NORM"));
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
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

        var config = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets: [new ExternalReportingTarget("A", "127.0.0.1", port, true)])
        };
        var store   = new MutableConfigStore(config);
        var channel = Channel.CreateBounded<DecodeBatch>(2);
        // Region store resolves the partner to a non-synthetic entity — this test is about
        // delivery mechanics, not the absolute exclusion filter; an unmapped (null-resolving)
        // partner would now be unconditionally suppressed (see the dedicated exclusion tests
        // below).
        var regionStore = new FakeCallsignRegionStore();
        regionStore.Set("Q1TST", new RegionInfo(Continent: "EU", Entity: "TestLand", Synthetic: false));
        var sut = CreateSut(store, channel.Reader, regionStore: regionStore);

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
            // enough datagrams to see past it to the QSOLogged datagram. margin: 3 = Heartbeat +
            // Status + QsoLogged, the current maximum for this path (no StopAsync call here).
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
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

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
        // loop scheduling is not deterministic), and StopAsync itself now sends Clear ahead of
        // Close (fix-external-reporting-clear-and-reply-filter, task 1.2) — so up to 4 datagrams
        // (Heartbeat, Status, Clear, Close) may arrive. Capturing exactly 3 here previously
        // truncated Close off the end on a slower/differently-scheduled runner (observed on
        // ubuntu-latest CI, fixed in PR #91 by bumping to 4 — still zero headroom against that
        // same maximum, so widened again here). margin: 6 requested against a maximum of 4 —
        // matching StopAsync_SendsClearToEveryEnabledTarget's own established headroom above, so
        // one more datagram type added to StopAsync doesn't immediately re-break this test too;
        // assert Close is present, not that it's the only or the Nth datagram.
        var recv = await ReceiveAllAsync(listener, 6, TimeSpan.FromSeconds(3));
        recv.Select(ReadMessageType).Should().Contain(WsjtxDatagram.MessageType.Close);
    }

    // ── Enable/disable posture (spec: "ExternalReportingService is inert by default") ──

    [Fact(DisplayName = "Disabled config opens no outbound socket — nothing is sent")]
    public async Task Disabled_OpensNoSocket()
    {
        using var listener = new UdpClient(0, AddressFamily.InterNetwork);
        var port = ((IPEndPoint)listener.Client.LocalEndPoint!).Port;

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
            await WaitForInboundBoundAsync(sut);

            // 1) Garbage — must not crash the listener.
            var garbage = new byte[] { 0x01, 0x02, 0x03 };
            await sender.SendAsync(garbage, garbage.Length, "127.0.0.1", port);

            // 2) A well-formed Halt Tx afterward must still be processed. FIFO delivery on the
            // single inbound socket means it is read after the garbage above with no pacing delay;
            // the final AbortAsync barrier proves the listener survived the garbage and processed it.
            var haltTx = new byte[16];
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(0), WsjtxDatagram.Magic);
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(4), WsjtxDatagram.SchemaVersion);
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(8), (uint)WsjtxDatagram.MessageType.HaltTx);
            // Id string: length=0 (empty).
            BinaryPrimitives.WriteUInt32BigEndian(haltTx.AsSpan(12), 0);
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);

            await Poll.WaitForCallAsync(() => qso.ReceivedCalls(), nameof(IQsoController.AbortAsync),
                timeout: TimeSpan.FromSeconds(5));
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
            await WaitForInboundBoundAsync(sut);

            var haltTx = BuildHaltTxDatagram();
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);

            await Poll.WaitForCallAsync(() => qso.ReceivedCalls(), nameof(IQsoController.AbortAsync),
                timeout: TimeSpan.FromSeconds(5));
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
            await WaitForInboundBoundAsync(sut);

            var datagram = BuildReplyDatagram("CQ Q1TST JO22");
            await sender.SendAsync(datagram, datagram.Length, "127.0.0.1", port);

            // Poll for the (forbidden) engage and require it never happens within the window,
            // instead of a bare fixed delay — the datagram is delivered on loopback well inside it.
            var engaged = async () => await Poll.WaitForCallAsync(() => reply.ReceivedCalls(),
                nameof(IExternalReplyTarget.TryEngageAsync), timeout: TimeSpan.FromMilliseconds(500));
            await engaged.Should().ThrowAsync<TimeoutException>();
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
            await WaitForInboundBoundAsync(sut);

            var datagram = BuildReplyDatagram("CQ Q1TST JO22");
            await sender.SendAsync(datagram, datagram.Length, "127.0.0.1", port);

            await Poll.WaitForCallAsync(() => reply.ReceivedCalls(),
                nameof(IExternalReplyTarget.TryEngageAsync), timeout: TimeSpan.FromSeconds(5));
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
            await WaitForInboundBoundAsync(sut);

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

            await Poll.WaitForEqualAsync(() => sut.LastFreeText, "TEST MSG",
                timeout: TimeSpan.FromSeconds(5));
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
            await WaitForInboundBoundAsync(sut);

            var closeDatagram = WsjtxDatagram.EncodeClose("GridTracker2");
            await sender.SendAsync(closeDatagram, closeDatagram.Length, "127.0.0.1", port);

            // The listener must still be alive: a subsequent Halt Tx is still processed. FIFO
            // delivery means the Halt Tx below is read after this Close with no pacing delay.
            var haltTx = BuildHaltTxDatagram();
            await sender.SendAsync(haltTx, haltTx.Length, "127.0.0.1", port);
            await Poll.WaitForCallAsync(() => qso.ReceivedCalls(), nameof(IQsoController.AbortAsync),
                timeout: TimeSpan.FromSeconds(5));

            await qso.Received(1).AbortAsync(Arg.Any<CancellationToken>());
        }
        finally
        {
            await sut.StopAsync(CancellationToken.None);
        }
    }
}
