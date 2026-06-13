using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.Cat;
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
        await Task.Delay(150);  // let the loop tick once
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
        await Task.Delay(150);
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
        await Task.Delay(200);   // let the service attempt connection and suspend

        var callsAtSuspend = connection.ReceivedCalls()
            .Count(c => c.GetMethodInfo().Name == nameof(IRadioConnection.ConnectAsync));

        await Task.Delay(300);   // wait; suspension means no further calls should occur

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
        await Task.Delay(150);   // first attempt fails → suspended

        // Simulate operator changing the serial port in config (clears suspension).
        await store.SaveAsync(
            store.Current with
            {
                Cat = store.Current.Cat! with { SerialPort = "COM7" }
            });

        await Task.Delay(300);   // second attempt should now succeed
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
        await Task.Delay(150);   // first attempt fails → suspended

        // Signal a manual retry (ICatController) — no config change required.
        svc.TriggerRetry();

        await Task.Delay(300);   // second attempt should now succeed
        await svc.StopAsync(CancellationToken.None);

        state.Status.Should().Be(CatConnectionStatus.Connected,
            "TriggerRetry must clear the failure suspension so the poll loop reconnects");
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
