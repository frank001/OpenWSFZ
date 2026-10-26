using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Daemon.Tests.PskReporter;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// issue #266 (change <c>one-pipeline-owner-266</c>): the capture pipeline has one owner. Every test drives the real
/// <see cref="PipelineController"/> with a fake capture, a fake framer factory that counts live framers and keeps an ordered event
/// log, and a fake configuration store. Waits are positive polls (<see cref="Poll"/>), never fixed delays; no audio device, no clock.
/// Every test except T8 also asserts that the R4 defence Warning count is 0 (K4).
/// </summary>
public sealed class PipelineControllerTests
{
    private const string DeviceA = "dev-A";
    private const string DeviceB = "dev-B";
    private const string DefenceWarning = "Pipeline start found a framer still running; stopped it first";

    /// <summary>The fakes and the controller under test.</summary>
    private sealed class Rig
    {
        public readonly List<string> Events = [];
        public readonly FakeConfigStore Store;
        public readonly CapturingLogger<PipelineController> Log = new();
        public readonly PipelineController Controller;

        private int _nextFramerId;
        private int _live;
        private int _maxLive;
        private int _monitorResets;

        /// <summary>When set, <c>stopCapture</c> waits on it, holding the controller's semaphore (the test's gate).</summary>
        public TaskCompletionSource? StopGate;
        private volatile bool _stopEntered;

        public Rig(string? device, bool decoding)
        {
            Store = new FakeConfigStore(new AppConfig { AudioDeviceId = device, DecodingEnabled = decoding });
            Controller = new PipelineController(
                Store,
                startCapture:  d => Record($"capture-start:{d}"),
                stopCapture:   async () =>
                {
                    Record("capture-stop");
                    var gate = StopGate;
                    if (gate is not null)
                    {
                        _stopEntered = true;
                        await gate.Task;
                    }
                },
                framerFactory: () => new FakeFramer(this, Interlocked.Increment(ref _nextFramerId)),
                resetMonitors: () => { Interlocked.Increment(ref _monitorResets); Record("monitors-reset"); },
                logger:        Log);
        }

        public int Live => Volatile.Read(ref _live);
        public int MaxLive => Volatile.Read(ref _maxLive);
        public int MonitorResets => Volatile.Read(ref _monitorResets);
        public bool StopEntered => _stopEntered;

        public void Record(string evt) { lock (Events) Events.Add(evt); }
        public List<string> Snapshot() { lock (Events) return [.. Events]; }
        public int Count(string prefix) => Snapshot().Count(e => e.StartsWith(prefix, StringComparison.Ordinal));
        public int WarningCount => Log.Count(LogLevel.Warning);

        public Task SetAsync(string? device, bool decoding)
            => Store.SaveAsync(Store.Current with { AudioDeviceId = device, DecodingEnabled = decoding });

        public int LogCount(string startsWith)
            => Log.Entries.Count(e => e.Level == LogLevel.Information && e.Message.StartsWith(startsWith, StringComparison.Ordinal));

        public void FramerStarted(int id)
        {
            Record($"framer-start:{id}");
            int now = Interlocked.Increment(ref _live);
            int max;
            do { max = Volatile.Read(ref _maxLive); } while (now > max && Interlocked.CompareExchange(ref _maxLive, now, max) != max);
        }

        public void FramerStopped(int id)
        {
            Record($"framer-stop:{id}");
            Interlocked.Decrement(ref _live);
        }

        /// <summary>A framer that is alive (counted) without the controller having started it: the pre-seeded slot of T8.</summary>
        public FakeFramer SeedLiveFramer()
        {
            var f = new FakeFramer(this, Interlocked.Increment(ref _nextFramerId));
            f.Start();
            Controller.FramerSlot = f;
            return f;
        }
    }

    private sealed class FakeFramer(Rig rig, int id) : IPipelineFramer
    {
        private int _state;   // 0 new, 1 running, 2 stopped
        public int Id => id;

        public void Start()
        {
            if (Interlocked.CompareExchange(ref _state, 1, 0) != 0) throw new InvalidOperationException("started twice");
            rig.FramerStarted(id);
        }

        public Task StopAsync()
        {
            if (Interlocked.CompareExchange(ref _state, 2, 1) == 1) rig.FramerStopped(id);
            return Task.CompletedTask;
        }
    }

    // ── FR-098: T1 the #266 repro ───────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-098: T1: with decoding off a saved device starts nothing (0 framers, no capture); then decoding on gives exactly 1 framer, on that device")]
    public async Task T1_DecodingOff_DeviceSavedOnly_ThenStartGivesOneFramer()
    {
        var rig = new Rig(null, decoding: false);

        await rig.SetAsync(DeviceA, decoding: false);
        await rig.Controller.ReconcileAsync("config");
        rig.Live.Should().Be(0);
        rig.Snapshot().Should().BeEmpty("a device change while decoding is off is saved only (D1)");
        rig.Controller.RunningDevice.Should().BeNull();

        await rig.SetAsync(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("config");

        rig.Live.Should().Be(1);
        rig.MaxLive.Should().Be(1);
        rig.Controller.RunningDevice.Should().Be(DeviceA);
        rig.Count("capture-start:").Should().Be(1);
        rig.Snapshot().Should().Contain($"capture-start:{DeviceA}");
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T2 never more than one framer ───────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T2: 50 off/on alternations while running never leave more than one framer alive, and end with one")]
    public async Task T2_Alternations_NeverMoreThanOneFramer()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");
        rig.Live.Should().Be(1);

        for (int i = 0; i < 50; i++)
        {
            await rig.SetAsync(DeviceA, decoding: false);
            await rig.Controller.ReconcileAsync("config");
            rig.Live.Should().Be(0);
            await rig.SetAsync(DeviceA, decoding: true);
            await rig.Controller.ReconcileAsync("config");
            rig.Live.Should().Be(1);
        }

        rig.MaxLive.Should().Be(1);
        rig.Live.Should().Be(1);
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T3 order does not matter (F3, kills m3) ─────────────────────────────────────────────────────────────

    private static readonly (string? Device, bool On)[] ConfigPalette =
        [(DeviceA, true), (DeviceB, true), (DeviceA, false), (DeviceB, false), (null, true)];

    [Theory(DisplayName = "FR-097: T3: calls queued behind the held semaphore, with the configuration changed again while they wait, converge on the LAST configuration, never above one framer")]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(5)]
    [InlineData(6)]
    [InlineData(7)]
    [InlineData(8)]
    public async Task T3_QueuedCalls_FollowTheLastConfiguration(int seed)
    {
        var rng = new Random(seed);
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");

        // Hold the semaphore from the test: a device change whose stop blocks on the gate.
        rig.StopGate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        await rig.SetAsync(DeviceB, decoding: true);
        var holder = rig.Controller.ReconcileAsync("hold");
        await Poll.UntilAsync(() => rig.StopEntered, timeoutMessage: () => "the holding reconcile never reached the gate");

        // Queue calls in a seeded random order, changing the configuration again between triggers and AFTER the last one.
        var calls = new List<Task>();
        for (int i = 0; i < 6; i++)
        {
            var (device, on) = ConfigPalette[rng.Next(ConfigPalette.Length)];
            await rig.SetAsync(device, on);
            calls.Add(rig.Controller.ReconcileAsync(i % 2 == 0 ? "config" : "capture-retry", forceRestart: i % 3 == 0));
        }
        var (lastDevice, lastOn) = ConfigPalette[rng.Next(ConfigPalette.Length)];
        await rig.SetAsync(lastDevice, lastOn);   // changed again after every call was triggered

        rig.StopGate.SetResult();
        await Task.WhenAll(calls.Append(holder));

        string? expected = lastOn ? lastDevice : null;
        rig.Controller.RunningDevice.Should().Be(expected, "the end state follows the last configuration, not the one at trigger time");
        rig.Live.Should().Be(expected is null ? 0 : 1);
        rig.MaxLive.Should().BeLessThanOrEqualTo(1);
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T4 device change / unchanged save ───────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T4: a device change while running is one stop and one start on the new device; the same device saved again does nothing")]
    public async Task T4_DeviceChange_OneStopOneStart_SameDeviceNoAction()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");
        var before = rig.Snapshot().Count;

        await rig.SetAsync(DeviceB, decoding: true);
        await rig.Controller.ReconcileAsync("config");

        var delta = rig.Snapshot().Skip(before).ToList();
        delta.Should().Equal("framer-stop:1", "capture-stop", "monitors-reset", $"capture-start:{DeviceB}", "framer-start:2");
        rig.Live.Should().Be(1);
        rig.Controller.RunningDevice.Should().Be(DeviceB);

        before = rig.Snapshot().Count;
        await rig.SetAsync(DeviceB, decoding: true);   // the same device saved again
        await rig.Controller.ReconcileAsync("config");
        await rig.Controller.ReconcileAsync("start");  // and a Start while running
        rig.Snapshot().Skip(before).Should().BeEmpty("converged means no action");
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T5 forceRestart and the standing record ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T5: forceRestart while running is one stop then one start; while decoding is off it does nothing")]
    public async Task T5_ForceRestart()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");
        var before = rig.Snapshot().Count;

        await rig.Controller.ReconcileAsync("capture-retry", forceRestart: true);

        rig.Snapshot().Skip(before).Should().Equal("framer-stop:1", "capture-stop", "monitors-reset", $"capture-start:{DeviceA}", "framer-start:2");
        rig.Live.Should().Be(1);

        await rig.SetAsync(DeviceA, decoding: false);
        await rig.Controller.ReconcileAsync("config");
        before = rig.Snapshot().Count;
        await rig.Controller.ReconcileAsync("capture-retry", forceRestart: true);
        rig.Snapshot().Skip(before).Should().BeEmpty("forceRestart while decoding is off does nothing");
        rig.WarningCount.Should().Be(0);
    }

    [Fact(DisplayName = "FR-097: T5: a dead capture with the record standing is still running: a save of another key causes no start")]
    public async Task T5_DeadCapture_RecordStands()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");
        var before = rig.Snapshot().Count;

        // The capture dies (CaptureFailed): the controller is not told; its record stands. An unrelated save asks it to reconcile.
        await rig.Store.SaveAsync(rig.Store.Current with { ShowCycleCountdown = !rig.Store.Current.ShowCycleCountdown });
        await rig.Controller.ReconcileAsync("config");

        rig.Snapshot().Skip(before).Should().BeEmpty();
        rig.Controller.RunningDevice.Should().Be(DeviceA);
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-098: T6 decoding off means off ───────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-098: T6: with decoding off no path (device change, adoption, retry, watchdog retry, repeated saves) starts capture or a framer or logs a pipeline start")]
    public async Task T6_DecodingOff_NothingStarts()
    {
        var rig = new Rig(DeviceA, decoding: false);

        await rig.Controller.ReconcileAsync("config");                                   // startup / save
        await rig.SetAsync(DeviceB, decoding: false);
        await rig.Controller.ReconcileAsync("config");                                   // device change
        await rig.SetAsync("dev-adopted", decoding: false);
        await rig.Controller.ReconcileAsync("config");                                   // adoption
        await rig.Controller.ReconcileAsync("capture-retry", forceRestart: true);        // coordinator retry
        await rig.Controller.ReconcileAsync("capture-retry", forceRestart: true);        // watchdog retry

        rig.Snapshot().Should().BeEmpty();
        rig.Live.Should().Be(0);
        rig.MaxLive.Should().Be(0);
        rig.LogCount("Pipeline started").Should().Be(0);
        rig.LogCount("Starting FT8 pipeline").Should().Be(0);
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T7 shutdown ─────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T7: shutdown while running leaves 0 framers and stops in today's order (health monitor, framer, decoder dispose, capture stop, capture dispose); later reconciles do nothing")]
    public async Task T7_Shutdown_Order()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");

        await rig.Controller.ShutdownAsync(
            stopHealthMonitor: () => { rig.Record("health-monitor-stop"); return Task.CompletedTask; },
            disposeDecoder:    () => rig.Record("decoder-dispose"),
            disposeCapture:    () => { rig.Record("capture-dispose"); return Task.CompletedTask; });

        rig.Snapshot().SkipWhile(e => e != "health-monitor-stop").Should().Equal(
            "health-monitor-stop", "framer-stop:1", "decoder-dispose", "capture-stop", "capture-dispose");
        rig.Live.Should().Be(0);
        rig.Controller.RunningDevice.Should().BeNull();

        var before = rig.Snapshot().Count;
        await rig.Controller.ReconcileAsync("config", forceRestart: true);
        rig.Snapshot().Skip(before).Should().BeEmpty("a reconcile after shutdown must not start a pipeline");
        rig.WarningCount.Should().Be(0);
    }

    [Fact(DisplayName = "FR-097: T7: shutdown racing a reconcile waits for it and leaves 0 framers")]
    public async Task T7_Shutdown_WaitsForReconcile()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");

        rig.StopGate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        await rig.SetAsync(DeviceB, decoding: true);
        var reconcile = rig.Controller.ReconcileAsync("config");
        await Poll.UntilAsync(() => rig.StopEntered);

        var shutdown = rig.Controller.ShutdownAsync(() => Task.CompletedTask, () => { }, () => Task.CompletedTask);
        shutdown.IsCompleted.Should().BeFalse("the semaphore is held by the in-progress reconcile, so shutdown must wait for it");

        rig.StopGate.SetResult();
        await Task.WhenAll(reconcile, shutdown);

        rig.Live.Should().Be(0);
        rig.Controller.RunningDevice.Should().BeNull();
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T8 the defence (kills m1 and m5) ────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T8: a live framer found in the slot is stopped BEFORE the new one starts, and exactly one Warning is logged (no callsign)")]
    public async Task T8_StartStep_StopsFoundFramerFirst_WithOneWarning()
    {
        var rig = new Rig(DeviceA, decoding: true);
        var seeded = rig.SeedLiveFramer();
        rig.Live.Should().Be(1);

        await rig.Controller.ReconcileAsync("config");

        var events = rig.Snapshot();
        int stopSeeded = events.IndexOf($"framer-stop:{seeded.Id}");
        int startNew   = events.FindIndex(e => e.StartsWith("framer-start:", StringComparison.Ordinal) && e != $"framer-start:{seeded.Id}");
        stopSeeded.Should().BeGreaterThanOrEqualTo(0, "the found framer was stopped");
        startNew.Should().BeGreaterThan(stopSeeded, "stop-before-start, from the ordered event log");
        rig.Live.Should().Be(1);
        rig.MaxLive.Should().Be(1, "never two live framers at once, even in the defence");

        var warnings = rig.Log.Entries.Where(e => e.Level == LogLevel.Warning).ToList();
        warnings.Should().HaveCount(1);
        warnings[0].Message.Should().Be("Pipeline start found a framer still running; stopped it first (reason: config).");
    }

    // ── FR-097: T9 adoption ─────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T9: an adoption save while decoding is on (the stored device id replaced) is exactly one start on the new id")]
    public async Task T9_Adoption_ExactlyOneStart()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");
        var startsBefore = rig.Count("capture-start:");

        await rig.SetAsync("dev-A-rotated", decoding: true);   // what CaptureAutoStartCoordinator's Adopt saves
        await rig.Controller.ReconcileAsync("config");

        (rig.Count("capture-start:") - startsBefore).Should().Be(1);
        rig.Snapshot().Should().Contain("capture-start:dev-A-rotated");
        rig.Live.Should().Be(1);
        rig.Controller.RunningDevice.Should().Be("dev-A-rotated");
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T10 device removed ──────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T10: AudioDeviceId set to null while running stops the pipeline and starts nothing")]
    public async Task T10_DeviceNull_StopsNoStart()
    {
        var rig = new Rig(DeviceA, decoding: true);
        await rig.Controller.ReconcileAsync("start");
        var before = rig.Snapshot().Count;

        await rig.SetAsync(null, decoding: true);
        await rig.Controller.ReconcileAsync("config");

        rig.Snapshot().Skip(before).Should().Equal("framer-stop:1", "capture-stop");
        rig.Live.Should().Be(0);
        rig.Controller.RunningDevice.Should().BeNull();
        rig.WarningCount.Should().Be(0);
    }

    // ── FR-097: T11 observable by log ───────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-097: T11: one 'Pipeline started' and one 'Pipeline stopped' line per transition with its reason; starts minus stops equals the live framer count")]
    public async Task T11_LogLines_StartsMinusStops_EqualsLiveFramers()
    {
        var rig = new Rig(DeviceA, decoding: true);
        var script = new (string? Device, bool On, string Reason, bool Force)[]
        {
            (DeviceA, true,  "start",         false),
            (DeviceB, true,  "config",        false),
            (DeviceB, false, "config",        false),
            (DeviceB, false, "capture-retry", true),
            (DeviceA, true,  "config",        false),
            (DeviceA, true,  "capture-retry", true),
            (null,    true,  "config",        false),
        };
        foreach (var (device, on, reason, force) in script)
        {
            await rig.SetAsync(device, on);
            await rig.Controller.ReconcileAsync(reason, force);
            (rig.LogCount("Pipeline started") - rig.LogCount("Pipeline stopped")).Should().Be(rig.Live);
            rig.Live.Should().BeInRange(0, 1);
        }

        rig.LogCount("Pipeline started").Should().Be(4);
        rig.LogCount("Pipeline stopped").Should().Be(4);
        var started = rig.Log.Entries.Where(e => e.Message.StartsWith("Pipeline started", StringComparison.Ordinal)).Select(e => e.Message).ToList();
        started[0].Should().Be($"Pipeline started on '{DeviceA}' (reason: start).");
        started[1].Should().Be($"Pipeline started on '{DeviceB}' (reason: config).");
        started[3].Should().Be($"Pipeline started on '{DeviceA}' (reason: capture-retry).");
        rig.Log.Entries.Should().Contain(e => e.Message == "Pipeline stopped (reason: config).");
        rig.WarningCount.Should().Be(0);
    }
}
