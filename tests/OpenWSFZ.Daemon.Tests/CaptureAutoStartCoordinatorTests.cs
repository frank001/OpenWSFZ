using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CaptureAutoStartCoordinator"/> — the two landmines the dev-task's
/// handoff calls out by name (capture-device-reresolution #187, design.md Decision 3): no double
/// restart per adoption, and no deadlock. Also covers the outcome→action mapping (design D1's
/// table) and the guards (decoding disabled, already capturing).
/// </summary>
public sealed class CaptureAutoStartCoordinatorTests
{
    // ── Test doubles ─────────────────────────────────────────────────────────

    /// <summary>
    /// Synchronously invokes <c>OnSaved</c> on every save, exactly like the real
    /// <c>JsonConfigStore</c> (and every existing config-store test double in this test suite,
    /// e.g. <c>QsoAnswererServiceTests.MutableConfigStore</c>).
    /// </summary>
    private sealed class MutableConfigStore(AppConfig initial) : IConfigStore
    {
        private AppConfig _current = initial;
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            _current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    /// <summary>Returns a caller-controlled device list, or throws when <c>throwOnNextCall</c> is set.</summary>
    private sealed class FakeAudioDeviceProvider : IAudioDeviceProvider
    {
        public IReadOnlyList<AudioDeviceInfo> Devices { get; set; } = [];
        public bool ThrowOnNextCall { get; set; }
        public int CallCount { get; private set; }

        public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        {
            CallCount++;
            if (ThrowOnNextCall)
            {
                ThrowOnNextCall = false;
                throw new InvalidOperationException("Simulated enumeration failure");
            }
            return Task.FromResult(Devices);
        }
    }

    private static AppConfig ConfigWith(string? deviceId, string? friendlyName, bool decodingEnabled = true)
        => new AppConfig() with
        {
            AudioDeviceId             = deviceId,
            AudioDeviceFriendlyName   = friendlyName,
            DecodingEnabled           = decodingEnabled,
        };

    private static CaptureAutoStartCoordinator BuildSut(
        IConfigStore configStore,
        FakeAudioDeviceProvider deviceProvider,
        CaptureRecoveryState recoveryState,
        out List<string> startCalls,
        Func<bool>? isCapturing = null,
        Func<TimeSpan, CancellationToken, Task>? delayAsync = null)
    {
        var calls = new List<string>();
        startCalls = calls;
        return new CaptureAutoStartCoordinator(
            configStore,
            deviceProvider,
            recoveryState,
            isCapturing: isCapturing ?? (() => false),
            startCaptureAsync: (id, _) => { calls.Add(id); return Task.CompletedTask; },
            logger: NullLogger.Instance,
            delayAsync: delayAsync);
    }

    // ── Outcome → action mapping (design D1's table) ────────────────────────

    [Fact(DisplayName = "FR-070: UseConfigured starts capture with the configured ID, does not touch config.json")]
    public async Task RunAsync_UseConfigured_StartsWithConfiguredId_NoSave()
    {
        var store = new MutableConfigStore(ConfigWith("id-1", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-1", "Mic")] };
        var recovery = new CaptureRecoveryState();
        var savedConfigs = 0;
        store.OnSaved += _ => savedConfigs++;

        var sut = BuildSut(store, provider, recovery, out var startCalls);
        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().Equal("id-1");
        savedConfigs.Should().Be(0, "UseConfigured never touches config.json");
    }

    [Fact(DisplayName = "FR-070: CannotResolve (empty enumeration) starts with the configured ID unchanged")]
    public async Task RunAsync_CannotResolve_EmptyEnumeration_StartsWithConfiguredIdUnchanged()
    {
        var store = new MutableConfigStore(ConfigWith("id-1", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [] };
        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var startCalls);

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().Equal("id-1");
    }

    [Fact(DisplayName = "FR-070: enumeration throwing is treated the same as CannotResolve — attempts the configured ID unchanged")]
    public async Task RunAsync_EnumerationThrows_TreatedAsCannotResolve()
    {
        var store = new MutableConfigStore(ConfigWith("id-1", "Mic"));
        var provider = new FakeAudioDeviceProvider { ThrowOnNextCall = true };
        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var startCalls);

        var act = async () => await sut.RunAsync(applyBackoffDelay: false);

        await act.Should().NotThrowAsync("an enumeration failure must not propagate out of RunAsync");
        startCalls.Should().Equal("id-1");
    }

    [Fact(DisplayName = "FR-070/design D3: Adopt persists exactly the new ID, friendly name unchanged, and does NOT itself call startCaptureAsync (no double restart)")]
    public async Task RunAsync_Adopt_SavesNewId_DoesNotCallStartDirectly()
    {
        var store = new MutableConfigStore(ConfigWith("{OLD}", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("{NEW}", "Mic")] };
        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var startCalls);

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().BeEmpty(
            "the coordinator must let OnSaved's device-change branch perform the one restart — " +
            "calling startCaptureAsync itself here would be the double-restart landmine");
        store.Current.AudioDeviceId.Should().Be("{NEW}");
        store.Current.AudioDeviceFriendlyName.Should().Be("Mic", "the friendly name must be unchanged");
    }

    [Fact(DisplayName = "FR-070/design D3: Adopt triggers exactly one start via OnSaved (simulating Program.cs's device-change branch)")]
    public async Task RunAsync_Adopt_TriggersExactlyOneStart_ViaOnSaved()
    {
        // Mirrors Program.cs's real OnSaved device-change branch: newDevice != runningDevice ->
        // exactly one start. This proves the FULL adoption contract end-to-end, not just the
        // coordinator's own half of it.
        var store = new MutableConfigStore(ConfigWith("{OLD}", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("{NEW}", "Mic")] };
        var runningDevice = "{OLD}";
        var onSavedStartCount = 0;
        store.OnSaved += cfg =>
        {
            if (cfg.AudioDeviceId != runningDevice)
            {
                runningDevice = cfg.AudioDeviceId;
                onSavedStartCount++;
            }
        };

        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var coordinatorStartCalls);
        await sut.RunAsync(applyBackoffDelay: false);

        (coordinatorStartCalls.Count + onSavedStartCount).Should().Be(1,
            "exactly one capture start must result from one adoption, from either source combined");
        onSavedStartCount.Should().Be(1);
        coordinatorStartCalls.Should().BeEmpty();
    }

    [Fact(DisplayName = "Scenario \"Ambiguous name is never guessed\": no start, no save, recorded as a failed DeviceUnavailable attempt")]
    public async Task RunAsync_Ambiguous_NoStartNoSave_RecordsDeviceUnavailable()
    {
        var store = new MutableConfigStore(ConfigWith("{GONE}", "Mic"));
        var provider = new FakeAudioDeviceProvider
        {
            Devices = [new AudioDeviceInfo("id-1", "Mic"), new AudioDeviceInfo("id-2", "Mic")],
        };
        var savedConfigs = 0;
        store.OnSaved += _ => savedConfigs++;
        var recovery = new CaptureRecoveryState();

        var sut = BuildSut(store, provider, recovery, out var startCalls,
            delayAsync: (_, _) => Task.CompletedTask); // avoid the self-rescheduled retry's real delay

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().BeEmpty();
        savedConfigs.Should().Be(0);
        recovery.ConsecutiveCaptureFailures.Should().Be(1);
        recovery.LastCaptureError.Should().Contain("ambiguous").And.Contain("2");
        recovery.DeriveCaptureState(deviceConfiguredAndDecodingEnabled: true, isCapturing: false)
            .Should().Be("DeviceUnavailable");
    }

    [Fact(DisplayName = "Scenario \"Disabled-only match is not adopted\": NotFound, recorded as a failed DeviceUnavailable attempt")]
    public async Task RunAsync_NotFound_RecordsDeviceUnavailable()
    {
        var store = new MutableConfigStore(ConfigWith("{GONE}", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-1", "Mic", Available: false)] };
        var recovery = new CaptureRecoveryState();

        var sut = BuildSut(store, provider, recovery, out var startCalls,
            delayAsync: (_, _) => Task.CompletedTask);

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().BeEmpty();
        recovery.ConsecutiveCaptureFailures.Should().Be(1);
        recovery.LastCaptureError.Should().Contain("0 matches");
    }

    // ── Self-rescheduling retry loop (design D4) ────────────────────────────

    [Fact(DisplayName = "FR-071: a NotFound outcome self-schedules another attempt, which succeeds once the device becomes resolvable")]
    public async Task RunAsync_NotFound_SelfReschedules_AndSucceedsOnceDeviceAppears()
    {
        // delayAsync is a no-op here — the schedule's own exact durations are
        // CaptureBackoffScheduleTests' concern; this test proves the LOOP LOGIC (record failure,
        // retry, eventually resolve) without waiting out any real delay (gate G10 spirit).
        var store = new MutableConfigStore(ConfigWith("{GONE}", "Mic"));
        // Non-empty but no name match -> NotFound (an EMPTY list would be CannotResolve instead,
        // which falls straight through to "attempt the configured ID unchanged" — a different
        // branch than the one this test exercises).
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-x", "Some Other Mic")] };
        var recovery = new CaptureRecoveryState();
        var sut = BuildSut(store, provider, recovery, out var startCalls,
            delayAsync: (_, _) => Task.CompletedTask);

        await sut.RunAsync(applyBackoffDelay: false);
        recovery.ConsecutiveCaptureFailures.Should().Be(1, "first attempt found nothing");

        // The device appears; the self-scheduled retry (a fire-and-forget Task.Run) needs a
        // moment to run — poll briefly rather than a fixed delay.
        provider.Devices = [new AudioDeviceInfo("{GONE}", "Mic")]; // now resolvable via UseConfigured
        await Poll.UntilAsync(() => startCalls.Count > 0,
            timeoutMessage: () => "self-scheduled retry never called startCaptureAsync");

        startCalls.Should().Equal("{GONE}");
        // The coordinator itself never resets ConsecutiveCaptureFailures — only a real chunk
        // arriving does that (CaptureRecoveryState.RecordChunkReceived, wired to
        // CaptureManager.ChunkReceived in production, not simulated by this fake startCaptureAsync).
        recovery.ConsecutiveCaptureFailures.Should().Be(1,
            "resetting the streak is RecordChunkReceived's job, driven by a real chunk arriving — not this coordinator's");
    }

    // ── Guards ───────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-070: DecodingEnabled = false short-circuits before any enumeration")]
    public async Task RunAsync_DecodingDisabled_DoesNothing()
    {
        var store = new MutableConfigStore(ConfigWith("id-1", "Mic", decodingEnabled: false));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-1", "Mic")] };
        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var startCalls);

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().BeEmpty();
        provider.CallCount.Should().Be(0, "decoding disabled must short-circuit before any enumeration");
    }

    [Fact(DisplayName = "FR-070: already capturing short-circuits (another path already recovered)")]
    public async Task RunAsync_AlreadyCapturing_DoesNothing()
    {
        var store = new MutableConfigStore(ConfigWith("id-1", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-1", "Mic")] };
        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var startCalls,
            isCapturing: () => true);

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().BeEmpty();
        provider.CallCount.Should().Be(0);
    }

    [Fact(DisplayName = "FR-070: nothing configured at all (both ID and name null) does nothing")]
    public async Task RunAsync_NothingConfigured_DoesNothing()
    {
        var store = new MutableConfigStore(ConfigWith(null, null));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-1", "Mic")] };
        var sut = BuildSut(store, provider, new CaptureRecoveryState(), out var startCalls);

        await sut.RunAsync(applyBackoffDelay: false);

        startCalls.Should().BeEmpty();
        provider.CallCount.Should().Be(0, "there is nothing to resolve without either an ID or a name");
    }

    // ── No deadlock ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "design D3: resolution+start from inside an automatic retry path completes under a timeout (no deadlock) even when startCaptureAsync itself serialises via a semaphore")]
    public async Task RunAsync_CompletesUnderTimeout_EvenWhenStartCaptureAsyncSerialisesViaSemaphore()
    {
        // Mirrors production's RestartPipelineAsync, which acquires restartSemaphore. The
        // coordinator itself must never hold anything while calling startCaptureAsync — if it
        // did, a semaphore-based startCaptureAsync would deadlock against itself.
        var semaphore = new SemaphoreSlim(1, 1);
        var store = new MutableConfigStore(ConfigWith("id-1", "Mic"));
        var provider = new FakeAudioDeviceProvider { Devices = [new AudioDeviceInfo("id-1", "Mic")] };

        var sut = new CaptureAutoStartCoordinator(
            store, provider, new CaptureRecoveryState(),
            isCapturing: () => false,
            startCaptureAsync: async (_, ct) =>
            {
                await semaphore.WaitAsync(ct);
                try { await Task.Yield(); } // a real async suspension point inside the "critical section"
                finally { semaphore.Release(); }
            },
            logger: NullLogger.Instance);

        var act = async () => await sut.RunAsync(applyBackoffDelay: false).WaitAsync(TimeSpan.FromSeconds(5));

        await act.Should().NotThrowAsync("no deadlock — the coordinator holds nothing while startCaptureAsync serialises its own work");
    }
}
