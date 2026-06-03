using FluentAssertions;
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
        var state  = new CatState();
        var store  = new StubConfigStore(new AppConfig() with
                         { Cat = cat ?? new CatConfig { Enabled = false } });
        var bus    = new CatEventBus(Guid.NewGuid());
        var logger = NullLogger<CatPollingService>.Instance;
        var svc    = new CatPollingService(state, store, bus, logger);
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
}
