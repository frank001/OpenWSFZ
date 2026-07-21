using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon.Cat;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for the FR-039 persistence behaviour in <see cref="CatPollingService"/>:
/// last-polled frequency is written to the config store when it changes by ≥ 1 Hz.
/// </summary>
[Trait("Category", "Unit")]
public sealed class CatPollingServiceFreqPersistTests
{
    // ── Scenario: Frequency changes by ≥ 1 Hz — store must be saved ──────────

    [Fact(DisplayName = "FR-039: SaveAsync is called when polled frequency differs from stored by ≥ 1 Hz")]
    public async Task PollSucceeds_FreqChanged_SaveAsyncCalled()
    {
        // Arrange
        var initialConfig = new AppConfig() with
        {
            AudioDeviceId = "test-audio-device",
            Cat           = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = 14.073,   // stored value
            }
        };
        var store      = new SpyConfigStore(initialConfig);
        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(false);
        connection.ConnectAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        // Return 14.074 MHz — exactly 1 Hz change from stored 14.073
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>()).Returns(14.074);

        var (svc, _) = MakeService(store, connection);

        // Act
        await svc.StartAsync(CancellationToken.None);
        // Wait for the ≥ 1 Hz change to be persisted rather than guessing a fixed poll window.
        await Poll.UntilAsync(() => store.SaveCount >= 1, timeout: TimeSpan.FromSeconds(5));
        await svc.StopAsync(CancellationToken.None);

        // Assert
        store.SaveCount.Should().BeGreaterThanOrEqualTo(1,
            "SaveAsync must be called when the frequency changes by ≥ 1 Hz");
        store.LastSavedConfig!.Cat!.LastPolledFrequencyMHz
            .Should().BeApproximately(14.074, 1e-9,
                "the persisted value must match the polled frequency");
    }

    // ── Scenario: Frequency within 1 Hz — no redundant save ──────────────────

    [Fact(DisplayName = "FR-039: SaveAsync is NOT called when polled frequency is within 1 Hz of stored")]
    public async Task PollSucceeds_FreqWithinOneHz_SaveAsyncNotCalled()
    {
        // Arrange — stored and polled frequency differ by < 1 Hz (0.5 Hz)
        const double storedMHz = 14.074000;
        const double polledMHz = 14.074000 + 0.0000005; // 0.5 Hz change

        var initialConfig = new AppConfig() with
        {
            AudioDeviceId = "test-audio-device",
            Cat           = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = storedMHz,
            }
        };
        var store      = new SpyConfigStore(initialConfig);
        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(false);
        connection.ConnectAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>()).Returns(polledMHz);

        var (svc, state) = MakeService(store, connection);

        // Act
        await svc.StartAsync(CancellationToken.None);
        // Wait for evidence at least one poll completed (status → Connected). The within-1 Hz
        // change means SaveAsync is never invoked, so there is no positive save signal to await —
        // a completed poll is the strongest available proof the save branch was evaluated.
        await Poll.WaitForEqualAsync(() => state.Status, CatConnectionStatus.Connected,
            timeout: TimeSpan.FromSeconds(5));
        await svc.StopAsync(CancellationToken.None);

        // Assert — save must NOT have been called; no churn
        store.SaveCount.Should().Be(0,
            "SaveAsync must not be called when the frequency change is below the 1 Hz threshold");
    }

    // ── Scenario: SaveAsync failure is logged at Warning and does not stop loop ─

    [Fact(DisplayName = "FR-039: A SaveAsync failure is logged at Warning and does not stop the poll loop")]
    public async Task PollSucceeds_SaveAsyncFails_LogsWarningAndContinues()
    {
        // Arrange
        var initialConfig = new AppConfig() with
        {
            AudioDeviceId = "test-audio-device",
            Cat           = new CatConfig
            {
                Enabled                = true,
                RigModel               = "SerialCat",
                LastPolledFrequencyMHz = null,
            }
        };
        var store      = new FailingConfigStore(initialConfig);
        var connection = Substitute.For<IRadioConnection>();
        connection.IsConnected.Returns(false);
        connection.ConnectAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        connection.GetDialFrequencyMhzAsync(Arg.Any<CancellationToken>()).Returns(14.074);

        var logger     = new SpyLogger<CatPollingService>();
        var state      = new CatState();
        var bus        = new CatEventBus(Guid.NewGuid());
        var logFactory = NullLoggerFactory.Instance;
        var svc        = new TestableCatPollingService(state, store, bus, logger, logFactory, connection);

        // Act — the service must continue running even after the save fails.
        await svc.StartAsync(CancellationToken.None);
        // Wait for the failing save to be attempted and logged at Warning, rather than
        // guessing a fixed settle window.
        await Poll.UntilAsync(() => logger.WarningCount >= 1, timeout: TimeSpan.FromSeconds(5));
        await svc.StopAsync(CancellationToken.None);

        // Assert — the loop kept running (state reflects latest poll).
        state.Status.Should().Be(CatConnectionStatus.Connected,
            "the poll loop must continue even when SaveAsync throws");

        // A Warning must have been logged for the failed save.
        logger.WarningCount.Should().BeGreaterThanOrEqualTo(1,
            "a failing SaveAsync must be logged at Warning level");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static (TestableCatPollingService svc, CatState state) MakeService(
        IConfigStore store,
        IRadioConnection connection)
    {
        var state      = new CatState();
        var bus        = new CatEventBus(Guid.NewGuid());
        var logger     = NullLogger<CatPollingService>.Instance;
        var logFactory = NullLoggerFactory.Instance;
        var svc        = new TestableCatPollingService(state, store, bus, logger, logFactory, connection);
        return (svc, state);
    }

    // ── Test-specific helpers ─────────────────────────────────────────────────

    /// <summary>
    /// Subclass of <see cref="CatPollingService"/> that overrides
    /// <see cref="CatPollingService.CreateConnection"/> to return a mock.
    /// </summary>
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

    private sealed class SpyConfigStore : IConfigStore
    {
        private AppConfig _current;
        public int        SaveCount       { get; private set; }
        public AppConfig? LastSavedConfig { get; private set; }

        public SpyConfigStore(AppConfig initial) => _current = initial;

        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;

        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            SaveCount++;
            LastSavedConfig = config;
            _current        = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    private sealed class FailingConfigStore : IConfigStore
    {
        private readonly AppConfig _current;
        public FailingConfigStore(AppConfig initial) => _current = initial;
        public AppConfig Current => _current;
#pragma warning disable CS0067 // event is part of the interface contract
        public event Action<AppConfig>? OnSaved;
#pragma warning restore CS0067
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
            => Task.FromException(new IOException("Simulated disk failure"));
    }

    private sealed class SpyLogger<T> : ILogger<T>
    {
        public int WarningCount { get; private set; }

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            if (logLevel == LogLevel.Warning)
                WarningCount++;
        }
    }
}
