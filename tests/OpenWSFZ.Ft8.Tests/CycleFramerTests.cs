using System.Threading.Channels;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: CycleFramerTests
/// </summary>
public sealed class CycleFramerTests
{
    private const int SamplesPerCycle = 12_000 * 15; // 180 000

    // ── Task 9.2: Two complete windows from a clean boundary ─────────────────

    [Fact]
    public async Task RunAsync_StartingAtBoundary_EmitsTwoCompleteWindows()
    {
        // Clock starts exactly at second 0 of a cycle → no leading silence.
        var clock = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));

        var (sourceWriter, framer, outputReader) = CreateFramer(clock);

        // Feed > 30 s worth of samples (2.5 cycles), each in 4096-sample chunks.
        var producerTask = FeedSamples(sourceWriter, totalSamples: SamplesPerCycle * 3, chunkSize: 4096);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = framer.RunAsync(outputReader.Item2, cts.Token);

        await producerTask;

        // Drain two windows.
        var windows = new List<float[]>();
        await foreach (var (pcm, _, _) in outputReader.Item1.ReadAllAsync(cts.Token))
        {
            windows.Add(pcm);
            if (windows.Count >= 2) break;
        }

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        windows.Should().HaveCountGreaterOrEqualTo(2, "feeding 3 cycles should emit at least 2 windows");
        windows.Should().AllSatisfy(w => w.Should().HaveCount(SamplesPerCycle,
            "every window must be exactly 180 000 samples"));
    }

    // ── Task 9.3: Leading silence when starting mid-cycle ────────────────────

    [Fact]
    public void ComputeLeadingSamples_StartAt7Seconds_Returns84000()
    {
        // 7 s into a cycle (cycle boundary at 0, 15, 30, 45...) → 7 * 12000 = 84 000 samples.
        var utc     = new DateTime(2026, 5, 21, 15, 30, 7, 0, DateTimeKind.Utc);
        int leading = CycleFramer.ComputeLeadingSamples(utc);

        leading.Should().Be(7 * 12_000, "starting 7 s into the cycle needs 84 000 leading silence samples");
    }

    [Fact]
    public async Task RunAsync_StartingMidCycle_FirstWindowHasLeadingSilence()
    {
        // Clock starts 7 s into cycle → 84 000 leading zero samples.
        var clock = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 7, 0, DateTimeKind.Utc));

        var (sourceWriter, framer, outputReader) = CreateFramer(clock);

        // Feed enough samples to complete the first window (15-7=8 s = 96 000 samples).
        float sentinel = 0.5f;
        var producer = FeedSamples(sourceWriter, totalSamples: SamplesPerCycle, chunkSize: 4096,
                                   fillValue: sentinel);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = framer.RunAsync(outputReader.Item2, cts.Token);

        await producer;

        float[]? window = null;
        await foreach (var (pcm, _, _) in outputReader.Item1.ReadAllAsync(cts.Token))
        {
            window = pcm;
            break;
        }

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        window.Should().NotBeNull();
        window!.Should().HaveCount(SamplesPerCycle);

        // First 84 000 samples should be silence.
        window![..84_000].Should().AllSatisfy(s => s.Should().BeApproximately(0f, 1e-9f),
            "leading samples should be zero-padded silence");

        // Remaining samples should carry the sentinel value.
        window![84_000..].Should().AllSatisfy(s => s.Should().BeApproximately(sentinel, 1e-6f),
            "trailing samples should be the fed audio");
    }

    // ── Task 9.4: Cancellation mid-accumulation ───────────────────────────────

    [Fact]
    public async Task RunAsync_Cancelled_ReturnsCleanly()
    {
        var clock  = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var (sourceWriter, framer, outputReader) = CreateFramer(clock);

        using var cts = new CancellationTokenSource();

        var framerTask = framer.RunAsync(outputReader.Item2, cts.Token);

        // Feed a few chunks but cancel before a full window is assembled.
        await sourceWriter.Item1.WriteAsync(new float[4096]);
        await sourceWriter.Item1.WriteAsync(new float[4096]);

        cts.Cancel();

        // RunAsync should complete without throwing.
        var act = async () => await framerTask;
        await act.Should().NotThrowAsync("cancellation should be handled gracefully");
    }

    // ── T1: ComputeLeadingSamples with offsetSecs == 0 but Millisecond > 0 ─────

    [Fact]
    public void ComputeLeadingSamples_AtBoundaryWithNonZeroMilliseconds_IncludesSubSecondOffset()
    {
        // Daemon starts exactly at a 15-second UTC boundary (Second % 15 == 0) but
        // 750 ms past it.  The old code returned 0 immediately; the fix must include
        // the millisecond component: 0 * 12000 + round(0.75 * 12000) = 9000 samples.
        var utc     = new DateTime(2026, 5, 21, 15, 30, 15, 750, DateTimeKind.Utc);
        int leading = CycleFramer.ComputeLeadingSamples(utc);

        leading.Should().Be(9_000,
            "750 ms into a cycle boundary = 0.75 × 12 000 = 9 000 leading silence samples");
    }

    // ── T2: Natural source-end must NOT complete the output channel ───────────

    [Fact(DisplayName = "FR-017: Natural source-end does not complete output channel (decode pump survives device-failure restart)")]
    public async Task RunAsync_SourceEndsNaturally_DoesNotCompleteOutputChannel()
    {
        var clock  = new FakeClock(new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource();
        var runTask   = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        // Complete the source without cancelling the framer — simulates a device failure.
        source.Writer.Complete();
        await runTask;

        // The output channel must remain writable so the next StartPipeline call's
        // framer can deliver windows to the existing decode pump.
        output.Writer.TryWrite((new float[180_000], DateTime.UtcNow, null)).Should().BeTrue(
            "a natural source-end (device failure) must not complete the output channel; " +
            "the decode pump must survive to accept windows from the next StartPipeline call");
    }

    // ── FR-017: Cancellation must not permanently kill the output channel ─────

    [Fact(DisplayName = "FR-017: CycleFramer cancellation does not complete the output channel")]
    public async Task RunAsync_Cancelled_DoesNotCompleteOutputChannel()
    {
        var clock  = new FakeClock(new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource();
        var runTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        cts.Cancel();
        await runTask;

        // Output channel must still be writable — the decode pump should survive a restart.
        output.Writer.TryWrite((new float[180_000], DateTime.UtcNow, null)).Should().BeTrue(
            "cancelling the framer for a device restart must not complete the output channel");
    }

    // ── R3: CycleFramer emits correct cycle-start timestamp ──────────────────

    [Fact(DisplayName = "R3: CycleFramer emits cycle-start timestamp aligned to the 15-second UTC boundary")]
    public async Task RunAsync_StartingAtBoundary_EmitsCycleStartAlignedToUtcBoundary()
    {
        // Clock starts exactly at a 15-second boundary — no leading silence.
        var startTime = new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc);
        var clock     = new FakeClock(startTime);

        var (sourceWriter, framer, outputReader) = CreateFramer(clock);

        var producerTask = FeedSamples(sourceWriter, totalSamples: SamplesPerCycle, chunkSize: 4096);

        using var cts      = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask     = framer.RunAsync(outputReader.Item2, cts.Token);

        await producerTask;

        DateTime? emittedCycleStart = null;
        await foreach (var (_, cycleStart, _) in outputReader.Item1.ReadAllAsync(cts.Token))
        {
            emittedCycleStart = cycleStart;
            break;
        }

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        emittedCycleStart.Should().NotBeNull();
        emittedCycleStart!.Value.Should().Be(startTime,
            "when CycleFramer starts exactly at a 15-second boundary the emitted " +
            "CycleStart must equal the startup time");
    }

    [Fact(DisplayName = "R3: CycleFramer emits cycle-start timestamp aligned to boundary when starting mid-cycle")]
    public async Task RunAsync_StartingMidCycle_EmitsCycleStartAlignedToBoundary()
    {
        // Clock starts 7 s into a cycle → cycle started at HH:mm:00 (the :00 boundary).
        var startUtc        = new DateTime(2026, 5, 21, 15, 30, 7, 0, DateTimeKind.Utc);
        var expectedCycleStart = new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc);
        var clock           = new FakeClock(startUtc);

        var (sourceWriter, framer, outputReader) = CreateFramer(clock);

        var producerTask = FeedSamples(sourceWriter, totalSamples: SamplesPerCycle, chunkSize: 4096);

        using var cts      = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask     = framer.RunAsync(outputReader.Item2, cts.Token);

        await producerTask;

        DateTime? emittedCycleStart = null;
        await foreach (var (_, cycleStart, _) in outputReader.Item1.ReadAllAsync(cts.Token))
        {
            emittedCycleStart = cycleStart;
            break;
        }

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        emittedCycleStart.Should().NotBeNull();
        emittedCycleStart!.Value.Should().Be(expectedCycleStart,
            "when starting 7 s into a cycle, CycleStart must be the :00 boundary (not :07)");
    }

    // ── FR-032: dialFreqProvider tests (defect: dial-freq-snapshot) ─────────

    [Fact(DisplayName = "FR-032: dialFreqProvider=null emits null DialFrequencyMHz in every window")]
    public async Task RunAsync_NullProvider_EmitsNullDialFrequency()
    {
        var clock  = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        // No dialFreqProvider supplied.
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        _ = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        await FeedSamples((source.Writer, source.Reader), SamplesPerCycle, 4096);

        bool    got          = false;
        double? emittedFreq  = null;
        await foreach (var (_, _, dialFreq) in output.Reader.ReadAllAsync(cts.Token))
        {
            got         = true;
            emittedFreq = dialFreq;
            break;
        }

        cts.Cancel();

        got.Should().BeTrue("framer should have emitted at least one window");
        emittedFreq.Should().BeNull("null dialFreqProvider must emit null DialFrequencyMHz");
    }

    [Fact(DisplayName = "FR-032: dialFreqProvider value is carried in emitted tuple")]
    public async Task RunAsync_WithProvider_EmitsSuppliedDialFrequency()
    {
        var clock  = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock, dialFreqProvider: () => 14.074);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        _ = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        await FeedSamples((source.Writer, source.Reader), SamplesPerCycle, 4096);

        bool    got         = false;
        double? emittedFreq = null;
        await foreach (var (_, _, dialFreq) in output.Reader.ReadAllAsync(cts.Token))
        {
            got         = true;
            emittedFreq = dialFreq;
            break;
        }

        cts.Cancel();

        got.Should().BeTrue("framer should have emitted at least one window");
        emittedFreq.Should().Be(14.074, "provider value must be carried in the emitted tuple");
    }

    [Fact(DisplayName = "FR-032: dial frequency is snapshotted at window-open time, not window-close time")]
    public async Task RunAsync_FrequencyChangesAfterWindowOpen_SnapshotIsWindowOpenValue()
    {
        // Provider: call 1 (startup = window-0 open) returns 14.074,
        //           call 2 (window-1 open, after first emission) returns 7.074.
        // If the snapshot were taken at window-CLOSE (wrong), the first emitted tuple would
        // carry 14.074 from call 1 — but the second tuple would still carry 14.074 (wrong)
        // because call 2 would fire at window-1 close, not open.  The correct behaviour is:
        // window-0 → 14.074 (call 1), window-1 → 7.074 (call 2).
        int callCount = 0;
        double? Provider() => ++callCount == 1 ? 14.074 : 7.074;

        var clock  = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock, dialFreqProvider: Provider);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        _ = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        // Feed two full windows worth of samples.
        await FeedSamples((source.Writer, source.Reader), SamplesPerCycle * 2, 4096);

        var emitted = new List<double?>();
        await foreach (var (_, _, dialFreq) in output.Reader.ReadAllAsync(cts.Token))
        {
            emitted.Add(dialFreq);
            if (emitted.Count >= 2) break;
        }

        cts.Cancel();

        emitted.Should().HaveCount(2, "two full windows of samples must produce two emissions");
        emitted[0].Should().Be(14.074,
            "window-0 must carry the frequency snapshotted at startup (window-0 open time)");
        emitted[1].Should().Be(7.074,
            "window-1 must carry the frequency snapshotted immediately after window-0 was emitted (window-1 open time)");
    }

    // ── fix-cycle-boundary-clock-drift ───────────────────────────────────────
    //
    // CycleFramer reads IClock.UtcNow exactly once at startup and once per
    // completed window (for the drift check). Rather than racing a mutable
    // FakeClock's Advance() calls on the test thread against RunAsync's
    // internal async scheduling (non-deterministic — RunAsync's startup read
    // and each boundary read happen synchronously inside the framer's own
    // execution, with no synchronization point the test can reliably hook),
    // these tests use small deterministic IClock doubles below whose UtcNow
    // advances by a fixed amount purely as a function of how many times it has
    // been read. This models a constant-rate clock (or a clock with one
    // permanent step) with zero test/production race, matching how a real
    // capture device's constant ppm-scale clock-rate error behaves in
    // production without needing wall-clock-synchronized test scaffolding.

    /// <summary>
    /// Deterministic <see cref="IClock"/>: UtcNow advances by exactly
    /// <c>perRead</c> on every read, starting from <c>start</c> on the first
    /// (0th) read.
    /// </summary>
    private sealed class RateClock : IClock
    {
        private readonly DateTime _start;
        private readonly TimeSpan _perRead;
        private int _reads;

        public RateClock(DateTime start, TimeSpan perRead)
        {
            _start   = start;
            _perRead = perRead;
        }

        public DateTime UtcNow
        {
            get
            {
                var now = _start + TimeSpan.FromTicks(_perRead.Ticks * _reads);
                _reads++;
                return now;
            }
        }
    }

    /// <summary>
    /// Like <see cref="RateClock"/>, but applies one additional, permanent
    /// offset from the read at index <c>stepAtRead</c> onward — models a
    /// one-off host system clock step (operator changes system time, NTP
    /// client steps the clock) rather than gradual device drift.
    /// </summary>
    private sealed class StepClock : IClock
    {
        private readonly DateTime _start;
        private readonly TimeSpan _perRead;
        private readonly int      _stepAtRead;
        private readonly TimeSpan _step;
        private int _reads;

        public StepClock(DateTime start, TimeSpan perRead, int stepAtRead, TimeSpan step)
        {
            _start      = start;
            _perRead    = perRead;
            _stepAtRead = stepAtRead;
            _step       = step;
        }

        public DateTime UtcNow
        {
            get
            {
                var now = _start + TimeSpan.FromTicks(_perRead.Ticks * _reads);
                if (_reads >= _stepAtRead) now += _step;
                _reads++;
                return now;
            }
        }
    }

    /// <summary>
    /// Deterministic <see cref="IClock"/> that replays a fixed sequence of
    /// per-check deviations (as <see cref="TimeSpan"/> offsets from the nominal
    /// arithmetic cycle-boundary sequence), holding the last entry once
    /// exhausted. Models a recurring, non-monotonic pipeline latency (WASAPI
    /// callback jitter, Channel&lt;float[]&gt; backpressure, thread-pool
    /// contention with concurrent native decode work) rather than genuine
    /// device drift — the offsets bounce around instead of accumulating.
    /// Index 0 (the framer's one-time startup read) always gets zero offset;
    /// subsequent reads (one per completed window's drift check) draw from
    /// <c>offsets</c> in order.
    /// </summary>
    private sealed class BouncingClock : IClock
    {
        private readonly DateTime  _start;
        private readonly TimeSpan[] _offsets;
        private int _reads;

        public BouncingClock(DateTime start, TimeSpan[] offsets)
        {
            _start   = start;
            _offsets = offsets;
        }

        public DateTime UtcNow
        {
            get
            {
                var offset = _reads == 0
                    ? TimeSpan.Zero
                    : _offsets[Math.Min(_reads - 1, _offsets.Length - 1)];
                var now = _start + TimeSpan.FromSeconds(CycleDurationSecs * _reads) + offset;
                _reads++;
                return now;
            }
        }
    }

    private const int CycleDurationSecs = 15;

    // Mirrors CycleFramer's private DriftThresholdSamples/CorrectionSanityCeilingSamples/
    // RequiredConsecutiveReadings constants (24 samples @ 12 kHz / one full cycle
    // (180 000 samples) / 3 checks) — kept in sync manually since those have no
    // public accessor. See CycleFramer.cs for the derivation rationale
    // (design.md Decisions 3-5).
    private const int DriftThresholdSamples          = 24;
    private const int CorrectionSanityCeilingSamples = SamplesPerCycle;
    private const int RequiredConsecutiveReadings    = 3;

    // Small feed margin for tests whose expected correction magnitude is
    // modest (well below CorrectionSanityCeilingSamples) — just needs to cover
    // a "lengthen"/discard correction's extra raw samples per event so the
    // last window in the test isn't starved.
    private const int SmallCorrectionFeedMarginSamples = 256;

    private static async Task FeedExactSamples(
        ChannelWriter<float[]> writer, int totalSamples, int chunkSize = 4096, float fillValue = 0.5f)
    {
        int sent = 0;
        while (sent < totalSamples)
        {
            int take  = Math.Min(chunkSize, totalSamples - sent);
            var chunk = new float[take];
            Array.Fill(chunk, fillValue);
            await writer.WriteAsync(chunk);
            sent += take;
        }
    }

    [Fact(DisplayName = "fix-cycle-boundary-clock-drift: no correction fires when IClock advances in exact lock-step with the nominal boundary sequence")]
    public async Task RunAsync_ClockInLockStep_NoCorrectionFires()
    {
        var startTime = new DateTime(2026, 7, 23, 12, 0, 0, DateTimeKind.Utc);
        var clock  = new RateClock(startTime, TimeSpan.FromSeconds(CycleDurationSecs));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        const int windowCount = 5;
        var feedTask = FeedExactSamples(source.Writer, SamplesPerCycle * windowCount);

        var windows = new List<(float[] Pcm, DateTime CycleStart)>();
        for (int i = 0; i < windowCount; i++)
        {
            var (pcm, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
            windows.Add((pcm, cycleStart));
        }
        await feedTask;

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        windows.Should().AllSatisfy(w => w.Pcm.Should().HaveCount(SamplesPerCycle,
            "no clock deviation must leave every window at exactly SamplesPerCycle samples"));
        windows[0].CycleStart.Should().Be(startTime, "first window starts exactly at startup time (boundary-aligned)");
        for (int i = 1; i < windows.Count; i++)
        {
            (windows[i].CycleStart - windows[i - 1].CycleStart).Should().Be(TimeSpan.FromSeconds(CycleDurationSecs),
                "with no clock deviation, cycleStart must advance by exactly 15 s every window, never re-anchored");
        }
    }

    [Fact(DisplayName = "fix-cycle-boundary-clock-drift: bounded correction fires once accumulated deviation persists above threshold for several consecutive checks")]
    public async Task RunAsync_ConstantRateOffset_BoundedCorrectionFiresAtThreshold()
    {
        var startTime = new DateTime(2026, 7, 23, 12, 0, 0, DateTimeKind.Utc);
        // 1 ms/cycle offset from nominal 15 s -> 12 samples/cycle deviation @ 12 kHz
        // (simulates a constant-rate capture device clock error): this grows every
        // check by the same amount in the same direction, so it crosses the
        // 24-sample threshold at check 2 (24 samples) and then satisfies the
        // RequiredConsecutiveReadings(3) persistence gate at check 4 (48 samples)
        // — checks 2 and 3 are threshold-crossing but not yet persistent, so no
        // correction fires there (design.md Decision 4).
        var clock  = new RateClock(startTime, TimeSpan.FromSeconds(CycleDurationSecs) + TimeSpan.FromMilliseconds(1));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        // Feed generously — a "lengthen" correction needs a few extra raw
        // samples beyond SamplesPerCycle for the corrected window.
        const int windowCount = 5;
        var feedTask = FeedExactSamples(source.Writer, SamplesPerCycle * windowCount + SmallCorrectionFeedMarginSamples * windowCount);

        var windows = new List<(float[] Pcm, DateTime CycleStart)>();
        for (int i = 0; i < windowCount; i++)
        {
            var (pcm, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
            windows.Add((pcm, cycleStart));
        }
        await feedTask;

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        windows[0].CycleStart.Should().Be(startTime);

        // Windows 0->1->2->3: deviation crosses the 24-sample threshold at check 2
        // (window 1->2) and check 3 (window 2->3), but the persistence gate has not
        // yet reached RequiredConsecutiveReadings(3) — no correction fires for any
        // of these transitions, unlike the pre-fix behaviour that reacted to the
        // very first threshold-crossing reading.
        for (int i = 1; i <= 3; i++)
        {
            (windows[i].CycleStart - windows[i - 1].CycleStart).Should().Be(TimeSpan.FromSeconds(CycleDurationSecs),
                $"window {i - 1}->{i}: threshold may be crossed, but the persistence gate has not yet been satisfied");
        }

        // Window 3 -> 4: the 3rd consecutive same-sign, non-decreasing
        // threshold-crossing reading (48 samples) satisfies the persistence gate,
        // firing a correction sized to the full confirmed deviation (design.md
        // Decision 5 — no longer capped to a small fixed quantum) and re-anchoring
        // cycleStart away from the pure arithmetic +15 s sequence.
        var naiveWindow4Start = windows[3].CycleStart.AddSeconds(CycleDurationSecs);
        windows[4].CycleStart.Should().NotBe(naiveWindow4Start,
            "a correction should have fired once the persistence gate was satisfied, re-anchoring cycleStart");
        double actualCorrectionSamples = (windows[4].CycleStart - naiveWindow4Start).TotalSeconds * 12_000;
        actualCorrectionSamples.Should().BeApproximately(48, 0.01,
            "the correction magnitude should fully absorb the accumulated deviation (48 samples) confirmed at the moment the persistence gate fires — not a smaller fixed quantum");

        windows.Should().AllSatisfy(w => w.Pcm.Should().HaveCount(SamplesPerCycle,
            "a correction adjusts which raw samples land in a window, never the emitted window's length"));
    }

    [Fact(DisplayName = "fix-cycle-boundary-clock-drift: a single implausibly large clock deviation is bounded by the sanity ceiling, not fully absorbed")]
    public async Task RunAsync_OneOffLargeClockStep_CorrectionStaysWithinSanityCeiling()
    {
        var startTime = new DateTime(2026, 7, 23, 12, 0, 0, DateTimeKind.Utc);
        // Perfect lock-step cadence, except a permanent +5 minute step applied
        // from the very first boundary check onward — simulates an
        // operator/NTP host clock step, not gradual device drift. The step is
        // permanent (not decaying), so every check reports the same ~5-minute
        // (3,600,000-sample) deviation: that satisfies the persistence gate's
        // "same sign, non-decreasing" test on the 3rd consecutive check
        // (design.md Decision 4), so the correction now fires one check later
        // than before the persistence gate existed. Per Decision 5 the
        // correction is no longer capped to a small fixed quantum, but a
        // 5-minute deviation still vastly exceeds even the much larger
        // CorrectionSanityCeilingSamples (one full 15 s cycle) backstop, so it
        // must still land within that ceiling rather than jumping the full
        // 5 minutes in one event.
        var clock  = new StepClock(startTime, TimeSpan.FromSeconds(CycleDurationSecs),
            stepAtRead: 1, step: TimeSpan.FromMinutes(5));
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        const int windowCount = 4;
        var feedTask = FeedExactSamples(source.Writer, SamplesPerCycle * windowCount + CorrectionSanityCeilingSamples * windowCount);

        var windows = new List<(float[] Pcm, DateTime CycleStart)>();
        for (int i = 0; i < windowCount; i++)
        {
            var (pcm, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
            windows.Add((pcm, cycleStart));
        }
        await feedTask;

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        // Windows 0->1->2: the persistence gate has not yet reached
        // RequiredConsecutiveReadings(3) — no correction fires for these
        // transitions even though every check is already far past threshold.
        for (int i = 1; i <= 2; i++)
        {
            (windows[i].CycleStart - windows[i - 1].CycleStart).Should().Be(TimeSpan.FromSeconds(CycleDurationSecs),
                $"window {i - 1}->{i}: the persistence gate has not yet been satisfied");
        }

        // Window 2 -> 3: the persistence gate is satisfied (3rd consecutive
        // same-sign, non-decreasing reading) and a correction fires — Decision 5
        // means it is no longer capped to a small fixed quantum, but a genuinely
        // pathological 5-minute deviation must still be bounded by the sanity
        // ceiling, nowhere close to the full 5-minute step.
        var naiveWindow3Start  = windows[2].CycleStart.AddSeconds(CycleDurationSecs);
        var actualShift        = (windows[3].CycleStart - naiveWindow3Start).Duration();
        var ceilingAsTimeSpan  = TimeSpan.FromSeconds(CorrectionSanityCeilingSamples / 12_000.0) + TimeSpan.FromTicks(10);

        actualShift.Should().BeLessOrEqualTo(ceilingAsTimeSpan,
            "a single implausibly large IClock deviation (a 5-minute host clock step) must not " +
            "produce a correction beyond the documented sanity ceiling — nowhere close to 5 minutes");

        windows.Should().AllSatisfy(w => w.Pcm.Should().HaveCount(SamplesPerCycle,
            "the correction bounds which raw samples land in a window, never the emitted window's length"));
    }

    [Fact(DisplayName = "fix-cycle-boundary-clock-drift live-evidence: recurring, non-monotonic pipeline-latency-style deviation never fires a correction")]
    public async Task RunAsync_RecurringNonMonotonicDeviation_NeverFiresCorrection()
    {
        // Reproduces dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md's
        // second logged live-run session verbatim (samples, in order):
        //   1162.5, 814.1, 1326.1, 1181.4, 772.2, 547.7, 1016.1
        // Every reading is positive and vastly exceeds DriftThresholdSamples (24) — under the
        // pre-fix implementation every one of these fired a correction (the reported defect:
        // the mechanism engaged every single cycle in production instead of the rare event it
        // was designed to be). None of these bounce values sustain a same-sign, non-decreasing
        // streak of RequiredConsecutiveReadings(3) — this models the constant/recurring
        // pipeline-scheduling-latency this fix targets, not genuine device clock-rate drift.
        var startTime = new DateTime(2026, 7, 23, 12, 0, 0, DateTimeKind.Utc);
        var offsets = new[]
        {
            TimeSpan.FromSeconds(1162.5 / 12_000.0),
            TimeSpan.FromSeconds(814.1  / 12_000.0),
            TimeSpan.FromSeconds(1326.1 / 12_000.0),
            TimeSpan.FromSeconds(1181.4 / 12_000.0),
            TimeSpan.FromSeconds(772.2  / 12_000.0),
            TimeSpan.FromSeconds(547.7  / 12_000.0),
            TimeSpan.FromSeconds(1016.1 / 12_000.0),
        };
        var clock  = new BouncingClock(startTime, offsets);
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        int windowCount = offsets.Length;
        var feedTask = FeedExactSamples(source.Writer, SamplesPerCycle * windowCount + SmallCorrectionFeedMarginSamples * windowCount);

        var windows = new List<(float[] Pcm, DateTime CycleStart)>();
        for (int i = 0; i < windowCount; i++)
        {
            var (pcm, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
            windows.Add((pcm, cycleStart));
        }
        await feedTask;

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        windows[0].CycleStart.Should().Be(startTime);
        for (int i = 1; i < windows.Count; i++)
        {
            (windows[i].CycleStart - windows[i - 1].CycleStart).Should().Be(TimeSpan.FromSeconds(CycleDurationSecs),
                $"window {i - 1}->{i}: none of the logged live-evidence bounce readings sustain a " +
                "non-decreasing streak long enough to satisfy the persistence gate, so cycleStart " +
                "must keep advancing by exactly 15 s, never re-anchored");
        }

        windows.Should().AllSatisfy(w => w.Pcm.Should().HaveCount(SamplesPerCycle,
            "with the persistence gate never satisfied, every window remains exactly SamplesPerCycle samples"));
    }

    [Fact(DisplayName = "fix-cycle-boundary-clock-drift sizing fix: residual deviation stays bounded near the noise floor across many corrections, never growing session-over-session")]
    public async Task RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections()
    {
        // Regression test for the sizing defect a live 7h54m endurance run found
        // (qa/endurance/2026-07-24-ce13e30/report.md): the old fixed 48-sample cap
        // only ever chipped away a small fraction of each confirmed deviation, so
        // residual drift grew essentially unbounded, correction after correction,
        // over a long session — unit tests never caught it because the earlier
        // tests above only exercise a handful of cycles around a single correction
        // event, not a long session with many repeated firings.
        //
        // Uses an exaggerated 5 ms/cycle offset (60 samples/cycle @ 12 kHz) —
        // not tied to the measured ~42 ppm real-world rate — purely so this test
        // exercises roughly a dozen correction events over a manageable number of
        // simulated windows rather than needing an impractically long simulated
        // session to reach the same number of firings.
        var startTime  = new DateTime(2026, 7, 23, 12, 0, 0, DateTimeKind.Utc);
        var perRead     = TimeSpan.FromSeconds(CycleDurationSecs) + TimeSpan.FromMilliseconds(5);
        var clock       = new RateClock(startTime, perRead);
        var source      = Channel.CreateUnbounded<float[]>();
        var output      = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer      = new CycleFramer(source.Reader, clock);

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        // ~60 samples/cycle deviation crosses DriftThresholdSamples(24) on check 1
        // and satisfies RequiredConsecutiveReadings(3) every 3 checks thereafter
        // (streak resets after each firing) — windowCount(24) yields roughly 8
        // correction events, comfortably "well beyond a handful of cycles around a
        // single correction event."
        const int windowCount = 24;
        var feedTask = FeedExactSamples(
            source.Writer, SamplesPerCycle * windowCount + SmallCorrectionFeedMarginSamples * windowCount);

        var windows = new List<(float[] Pcm, DateTime CycleStart)>();
        for (int i = 0; i < windowCount; i++)
        {
            var (pcm, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
            windows.Add((pcm, cycleStart));
        }
        await feedTask;

        cts.Cancel();
        try { await framerTask; } catch { /* cancelled */ }

        // The clock's own deterministic formula (see RateClock) is exactly what a
        // correctly-tracking cycleStart sequence should match at each window's
        // boundary check (read index == window index, since one read happens per
        // completed window transition). Residual = how far cycleStart has drifted
        // from that true reading at each window.
        var residualsSamples = new List<double>();
        for (int i = 1; i < windows.Count; i++)
        {
            var expectedTrueUtc = startTime + TimeSpan.FromTicks(perRead.Ticks * i);
            double residualSamples = (windows[i].CycleStart - expectedTrueUtc).TotalSeconds * 12_000;
            residualsSamples.Add(Math.Abs(residualSamples));
        }

        // Under the old fixed-cap bug, residual grew roughly linearly with every
        // correction (each firing only removed a small fraction of what had
        // accumulated) — by window 24 it would already be many hundreds of
        // samples and still climbing. With the sizing fix, each firing fully
        // absorbs the confirmed deviation, so residual should never exceed
        // roughly one persistence-gate cycle's worth of accumulation (3 checks x
        // 60 samples/check = 180 samples) plus a small margin, for the entire
        // session — not just for the first correction.
        const double maxExpectedResidualSamples = 220;
        residualsSamples.Should().AllSatisfy(r => r.Should().BeLessOrEqualTo(maxExpectedResidualSamples),
            "residual deviation must stay bounded near the noise floor after every correction, " +
            "not grow session-over-session as more corrections fire");

        // Explicitly guard against a "still bounded but silently growing" trend:
        // the last correction cycle's peak residual should not be materially
        // larger than an early correction cycle's peak residual.
        int sampleCount = residualsSamples.Count;
        double earlyPeak = residualsSamples.Take(Math.Min(3, sampleCount)).Max();
        double latePeak  = residualsSamples.Skip(Math.Max(0, sampleCount - 3)).Max();
        latePeak.Should().BeLessOrEqualTo(earlyPeak + 30,
            "peak residual late in the session must not be meaningfully larger than peak residual " +
            "early in the session — the defining symptom of the sizing bug this test guards against");

        windows.Should().AllSatisfy(w => w.Pcm.Should().HaveCount(SamplesPerCycle,
            "a correction adjusts which raw samples land in a window, never the emitted window's length"));
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static (
        (ChannelWriter<float[]> Writer, ChannelReader<float[]> Reader) Source,
        CycleFramer Framer,
        (ChannelReader<(float[], DateTime, double?)> Reader, ChannelWriter<(float[], DateTime, double?)> Writer) Output)
        CreateFramer(FakeClock clock)
    {
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);
        return ((source.Writer, source.Reader), framer, (output.Reader, output.Writer));
    }

    private static async Task FeedSamples(
        (ChannelWriter<float[]> Writer, ChannelReader<float[]> _) source,
        int totalSamples,
        int chunkSize,
        float fillValue = 0.5f)
    {
        int sent = 0;
        while (sent < totalSamples)
        {
            int take  = Math.Min(chunkSize, totalSamples - sent);
            var chunk = new float[take];
            Array.Fill(chunk, fillValue);
            await source.Writer.WriteAsync(chunk);
            sent += take;
        }
        source.Writer.Complete();
    }
}
