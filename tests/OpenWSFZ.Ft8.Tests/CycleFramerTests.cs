using System.Threading.Channels;
using FluentAssertions;
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

    // ── P16-Cat: dialFreqProvider tests (defect: dial-freq-snapshot) ─────────

    [Fact(DisplayName = "P16-Cat: dialFreqProvider=null emits null DialFrequencyMHz in every window")]
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

    [Fact(DisplayName = "P16-Cat: dialFreqProvider value is carried in emitted tuple")]
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

    [Fact(DisplayName = "P16-Cat: dial frequency is snapshotted at window-open time, not window-close time")]
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
