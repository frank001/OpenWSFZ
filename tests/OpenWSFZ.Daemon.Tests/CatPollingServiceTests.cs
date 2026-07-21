using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.Cat;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CatPollingService"/> (FR-032, FR-034).
/// Uses a mock <see cref="IRadioConnection"/> so no real hardware is required.
/// </summary>
[Trait("Category", "Unit")]
public sealed class CatPollingServiceTests
{
    // ── Helpers ───────────────────────────────────────────────────────────────

    private static (CatPollingService svc, CatState state, IConfigStore store)
        MakeService(CatConfig? cat = null)
    {
        var state      = new CatState();
        var store      = new StubConfigStore(new AppConfig() with
                             { Cat = cat ?? new CatConfig { Enabled = false } });
        var bus        = new CatEventBus(Guid.NewGuid());
        var logger     = NullLogger<CatPollingService>.Instance;
        var logFactory = NullLoggerFactory.Instance;
        var svc        = new CatPollingService(state, store, bus, logger, logFactory);
        return (svc, state, store);
    }

    // ── Disabled path ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-034: CatPollingService stays Disabled when cat.enabled is false")]
    public async Task StartAsync_DisabledConfig_StatusRemainsDisabled()
    {
        var (svc, state, _) = MakeService(new CatConfig { Enabled = false });

        await svc.StartAsync(CancellationToken.None);
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Disabled,
            timeout: TimeSpan.FromSeconds(5));
        await svc.StopAsync(CancellationToken.None);

        state.Status.Should().Be(CatConnectionStatus.Disabled);
        state.DialFrequencyMHz.Should().BeNull();
    }

    // ── Stop behaviour ────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-032: CatPollingService StopAsync completes within 3 seconds")]
    public async Task StopAsync_CompletesWithinThreeSeconds()
    {
        var (svc, _, _) = MakeService(new CatConfig { Enabled = false });

        await svc.StartAsync(CancellationToken.None);
        var sw = System.Diagnostics.Stopwatch.StartNew();
        await svc.StopAsync(CancellationToken.None);
        sw.Stop();

        sw.Elapsed.Should().BeLessThan(TimeSpan.FromSeconds(3));
    }

    // ── Unknown rigModel ──────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-034: CatPollingService sets Disabled for unrecognised rigModel")]
    public async Task RunAsync_UnknownRigModel_SetsDisabled()
    {
        var cat = new CatConfig { Enabled = true, RigModel = "UnknownRig2000" };
        var (svc, state, _) = MakeService(cat);

        await svc.StartAsync(CancellationToken.None);
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Disabled,
            timeout: TimeSpan.FromSeconds(5));
        await svc.StopAsync(CancellationToken.None);

        state.Status.Should().Be(CatConnectionStatus.Disabled);
    }

    // ── Failure suspension ────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-034: CatPollingService suspends polling after a connect failure — no further attempts until config changes")]
    public async Task ConnectAsync_Fails_PollingIsSuspendedAndNotRetried()
    {
        // Arrange — connection always times out (radio off / not present).
        var cat   = new CatConfig { Enabled = true, RigModel = "SerialCat" };
        var store = new StubConfigStore(new AppConfig() with
        {
            AudioDeviceId = "test-audio-device",
            Cat           = cat,
        });

        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(false);
        connection.ConnectAsync(Arg.Any<CancellationToken>())
                  .Throws(new TimeoutException("Serial CAT: no response to FA; within 500 ms."));

        var state = new CatState();
        var bus   = new CatEventBus(Guid.NewGuid());
        var svc   = new TestableCatPollingService(
                        state, store, bus,
                        NullLogger<CatPollingService>.Instance,
                        NullLoggerFactory.Instance,
                        connection);

        // Act
        await svc.StartAsync(CancellationToken.None);
        // Wait for the connect attempt to fail and polling to suspend (status → Error).
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Error,
            timeout: TimeSpan.FromSeconds(5));

        var callsAtSuspend = connection.ReceivedCalls()
            .Count(c => c.GetMethodInfo().Name == nameof(IRadioConnection.ConnectAsync));

        // Suspension must hold: poll for a (forbidden) second connect attempt and require it
        // never lands within the window, instead of a bare fixed delay. A broken suspension
        // would retry within ~2 idle ticks (200 ms each), well inside this window.
        var secondAttempt = async () => await Poll.UntilAsync(
            () => connection.ReceivedCalls()
                .Count(c => c.GetMethodInfo().Name == nameof(IRadioConnection.ConnectAsync)) > callsAtSuspend,
            timeout: TimeSpan.FromMilliseconds(500));
        await secondAttempt.Should().ThrowAsync<TimeoutException>();

        await svc.StopAsync(CancellationToken.None);

        // Assert
        var totalCalls = connection.ReceivedCalls()
            .Count(c => c.GetMethodInfo().Name == nameof(IRadioConnection.ConnectAsync));

        state.Status.Should().Be(CatConnectionStatus.Error,
            "the service must set Error status when the radio is unreachable");
        callsAtSuspend.Should().Be(1,
            "exactly one connect attempt should occur before suspension");
        totalCalls.Should().Be(callsAtSuspend,
            "no further ConnectAsync calls should be made after polling is suspended");
    }

    [Fact(DisplayName = "FR-034: CatPollingService resumes polling after a CAT config change clears the suspension")]
    public async Task ConnectAsync_Fails_ThenConfigChanges_ResumesPolling()
    {
        // Arrange — connection fails initially, then succeeds after config change.
        var cat   = new CatConfig { Enabled = true, RigModel = "SerialCat", SerialPort = "COM6" };
        var store = new StubConfigStore(new AppConfig() with
        {
            AudioDeviceId = "test-audio-device",
            Cat           = cat,
        });

        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(false);

        var callCount = 0;
        connection.ConnectAsync(Arg.Any<CancellationToken>())
                  .Returns(_ =>
                  {
                      if (++callCount == 1)
                          throw new TimeoutException("Serial CAT: no response to FA; within 500 ms.");
                      return Task.CompletedTask;
                  });
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>()).Returns(14.074);

        var state = new CatState();
        var bus   = new CatEventBus(Guid.NewGuid());
        var svc   = new TestableCatPollingService(
                        state, store, bus,
                        NullLogger<CatPollingService>.Instance,
                        NullLoggerFactory.Instance,
                        connection);

        await svc.StartAsync(CancellationToken.None);
        // First attempt fails → suspended (status → Error).
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Error,
            timeout: TimeSpan.FromSeconds(5));

        // Simulate operator changing the serial port in config (clears suspension).
        await store.SaveAsync(
            store.Current with
            {
                Cat = store.Current.Cat! with { SerialPort = "COM7" }
            });

        // Poll for Connected — avoids a hard-coded delay that can fail on slow CI runners.
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Connected,
            timeout: TimeSpan.FromSeconds(1));

        await svc.StopAsync(CancellationToken.None);

        state.Status.Should().Be(CatConnectionStatus.Connected,
            "after the config change clears the suspension the service should connect");
    }

    // ── Manual retry ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-034: TriggerRetry clears the failure suspension and triggers an immediate reconnect")]
    public async Task TriggerRetry_WhenSuspended_AttemptsReconnect()
    {
        // Arrange — connection fails initially, then succeeds after TriggerRetry().
        var cat   = new CatConfig { Enabled = true, RigModel = "SerialCat", SerialPort = "COM6" };
        var store = new StubConfigStore(new AppConfig() with
        {
            AudioDeviceId = "test-audio-device",
            Cat           = cat,
        });

        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(false);

        var callCount = 0;
        connection.ConnectAsync(Arg.Any<CancellationToken>())
                  .Returns(_ =>
                  {
                      if (++callCount == 1)
                          throw new TimeoutException("Serial CAT: no response to FA; within 500 ms.");
                      return Task.CompletedTask;
                  });
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>()).Returns(14.074);

        var state = new CatState();
        var bus   = new CatEventBus(Guid.NewGuid());
        var svc   = new TestableCatPollingService(
                        state, store, bus,
                        NullLogger<CatPollingService>.Instance,
                        NullLoggerFactory.Instance,
                        connection);

        await svc.StartAsync(CancellationToken.None);
        // First attempt fails → suspended (status → Error).
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Error,
            timeout: TimeSpan.FromSeconds(5));

        // Signal a manual retry (ICatController) — no config change required.
        svc.TriggerRetry();

        // Poll for the reconnect rather than a fixed delay. Assert BEFORE StopAsync — StopAsync
        // cancels the poll loop, which can race with the final Connected status update (a
        // cancelled-token delay throws OCE mid-connect, leaving status as Connecting).
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Connected,
            timeout: TimeSpan.FromSeconds(2), what: "CAT status after TriggerRetry");

        state.Status.Should().Be(CatConnectionStatus.Connected,
            "TriggerRetry must clear the failure suspension so the poll loop reconnects");

        await svc.StopAsync(CancellationToken.None);
    }

    // ── ICatPttGate (FR-056, task 12.3) ───────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: ICatPttGate.SetPttAsync throws InvalidOperationException when CAT is disabled")]
    public async Task SetPttAsync_CatDisabled_Throws()
    {
        var (svc, _, _) = MakeService(new CatConfig { Enabled = false });
        ICatPttGate gate = svc;

        var act = () => gate.SetPttAsync(true);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*disabled*");
    }

    [Fact(DisplayName = "CatTx-Ptt: ICatPttGate.SetPttAsync throws InvalidOperationException when no connection has ever been established")]
    public async Task SetPttAsync_NoActiveConnection_Throws()
    {
        // Enabled but the poll loop was never started — _activeConnection stays null.
        var (svc, _, _) = MakeService(new CatConfig { Enabled = true });
        ICatPttGate gate = svc;

        var act = () => gate.SetPttAsync(true);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*not yet connected*");
    }

    [Fact(DisplayName = "CatTx-Ptt: ICatPttGate.SetPttAsync dispatches to the active IRadioConnection once connected")]
    public async Task SetPttAsync_Connected_CallsConnectionSetPtt()
    {
        var cat   = new CatConfig { Enabled = true, RigModel = "SerialCat" };
        var store = new StubConfigStore(new AppConfig() with { Cat = cat });

        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(true);
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>()).Returns(14.074);

        var state = new CatState();
        var bus   = new CatEventBus(Guid.NewGuid());
        var svc   = new TestableCatPollingService(
                        state, store, bus,
                        NullLogger<CatPollingService>.Instance,
                        NullLoggerFactory.Instance,
                        connection);
        ICatPttGate gate = svc;

        await svc.StartAsync(CancellationToken.None);

        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Connected,
            timeout: TimeSpan.FromSeconds(1));

        await gate.SetPttAsync(true);

        await svc.StopAsync(CancellationToken.None);

        await connection.Received(1).SetPttAsync(true, Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "CatTx-Ptt: poll loop reads and SetPttAsync commands never overlap on the shared connection")]
    public async Task SetPttAsync_ConcurrentWithPoll_NeverInterleaves()
    {
        // A re-entrancy guard on the mock connection: any overlapping call (poll vs. PTT,
        // or PTT vs. PTT) increments past 1 and flags a violation — proving the
        // _connectionLock gate genuinely serialises every call, not just by coincidence
        // of timing (design.md Decision 1).
        var cat   = new CatConfig { Enabled = true, RigModel = "SerialCat", PollIntervalSeconds = 1 };
        var store = new StubConfigStore(new AppConfig() with { Cat = cat });

        var reentrancyGuard = 0;
        var violation       = false;

        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(true);
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>())
            .Returns(async _ =>
            {
                if (Interlocked.Increment(ref reentrancyGuard) != 1) violation = true;
                await Task.Delay(50);
                Interlocked.Decrement(ref reentrancyGuard);
                return 14.074;
            });
        connection.SetPttAsync(Arg.Any<bool>(), Arg.Any<CancellationToken>())
            .Returns(async _ =>
            {
                if (Interlocked.Increment(ref reentrancyGuard) != 1) violation = true;
                await Task.Delay(50);
                Interlocked.Decrement(ref reentrancyGuard);
            });

        var state = new CatState();
        var bus   = new CatEventBus(Guid.NewGuid());
        var svc   = new TestableCatPollingService(
                        state, store, bus,
                        NullLogger<CatPollingService>.Instance,
                        NullLoggerFactory.Instance,
                        connection);
        ICatPttGate gate = svc;

        await svc.StartAsync(CancellationToken.None);

        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Connected,
            timeout: TimeSpan.FromSeconds(1));

        // Fire several concurrent PTT calls while the poll loop is also ticking
        // (PollIntervalSeconds = 1, so a poll is likely mid-flight during this window).
        var pttTasks = Enumerable.Range(0, 5).Select(_ => gate.SetPttAsync(true)).ToArray();
        await Task.WhenAll(pttTasks);

        // Let at least one more poll cycle run (and be overlap-checked by the re-entrancy guard)
        // after the PTT burst — wait for the next completed poll read rather than a blind delay.
        var readsAfterBurst = connection.ReceivedCalls()
            .Count(c => c.GetMethodInfo().Name == nameof(IRadioConnection.GetDialFrequencyMhzAsync));
        await Poll.WaitForCallCountAsync(() => connection.ReceivedCalls(),
            nameof(IRadioConnection.GetDialFrequencyMhzAsync), readsAfterBurst + 1,
            timeout: TimeSpan.FromSeconds(2));

        await svc.StopAsync(CancellationToken.None);

        violation.Should().BeFalse(
            "the connection lock must prevent any overlap between poll reads and PTT commands");
    }

    // ── Stub IConfigStore ─────────────────────────────────────────────────────

    private sealed class StubConfigStore : IConfigStore
    {
        private AppConfig _current;
        public StubConfigStore(AppConfig config) => _current = config;
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            _current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    // ── TestableCatPollingService ─────────────────────────────────────────────

    private sealed class TestableCatPollingService : CatPollingService
    {
        private readonly IRadioConnection _injected;

        public TestableCatPollingService(
            CatState                   catState,
            IConfigStore               configStore,
            CatEventBus                catEventBus,
            ILogger<CatPollingService> logger,
            ILoggerFactory             loggerFactory,
            IRadioConnection           injectedConnection)
            : base(catState, configStore, catEventBus, logger, loggerFactory)
        {
            _injected = injectedConnection;
        }

        // Eliminate the post-connect settle delay so unit tests run without
        // artificial latency and timing assertions remain deterministic.
        protected override TimeSpan PostConnectSettleDelay => TimeSpan.Zero;

        protected override IRadioConnection? CreateConnection(CatConfig config)
            => _injected;
    }
}
