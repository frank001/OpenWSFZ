using System.Threading.Channels;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// decode-early-batch-panel task 4.2 (FR-083): the framer's optional EARLY window. Every test feeds a source that ends,
/// so the framer returns by itself and the outputs can be read afterwards: no delay, no polling, no clock race.
/// The existing framer tests and both oracle tests are untouched (they pass no provider and no early output).
/// </summary>
public sealed class CycleFramerEarlyTests
{
    private const int SamplesPerCycle = 12_000 * 15;                 // 180 000
    private const int Chunk           = 4_096;                       // does not divide 156 000: the trigger is overshot

    private static readonly DateTime Boundary = new(2026, 10, 3, 15, 30, 0, DateTimeKind.Utc);

    private sealed record Run(
        List<(float[] Pcm, DateTime CycleStart, double? Dial)> Windows,
        List<(float[] Pcm, DateTime CycleStart, double? Dial)> Early,
        int                                                    ProviderCalls);

    /// <summary>Runs the framer over <paramref name="cycles"/> cycles of a running-index ramp (sample i holds i+1).</summary>
    private static async Task<Run> RunFramerAsync(
        int cycles, Func<int, (bool Enabled, double CutSeconds)>? provider, bool passEarlyOutput = true, double? dial = 7.074)
    {
        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var early  = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        int calls  = 0;

        Func<(bool, double)>? wrapped = provider is null ? null : () => provider(calls++);
        var framer = new CycleFramer(source.Reader, new FakeClock(Boundary),
                                     dialFreqProvider: () => dial, earlyDecodeProvider: wrapped);

        long next = 0;
        // A fixed clock makes every lazy resync after the first window ask for a correction of up to one chunk, so a later
        // window consumes up to 4 096 extra samples: feed generously and assert only over the FIRST `cycles` windows.
        long total = (long)(SamplesPerCycle + Chunk) * cycles;
        while (next < total)
        {
            int take  = (int)Math.Min(Chunk, total - next);
            var chunk = new float[take];
            for (int i = 0; i < take; i++) chunk[i] = next + i + 1;
            await source.Writer.WriteAsync(chunk);
            next += take;
        }
        source.Writer.Complete();

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));   // a hang guard, never a wait
        await framer.RunAsync(output.Writer, passEarlyOutput ? early.Writer : null, cts.Token);

        var windows = new List<(float[], DateTime, double?)>();
        while (output.Reader.TryRead(out var w)) windows.Add(w);
        var earlies = new List<(float[], DateTime, double?)>();
        while (early.Reader.TryRead(out var e)) earlies.Add(e);
        return new Run(windows, earlies, calls);
    }

    [Fact(DisplayName = "FR-083: 4.2a the early window is exactly the trigger length with a zero tail, even when a chunk overshoots the trigger")]
    public async Task EarlyWindow_IsExactlyTheTriggerLength_ZeroFilled()
    {
        var run = await RunFramerAsync(1, _ => (true, 2.0));

        run.Early.Should().NotBeEmpty();
        var early = run.Early[0].Pcm;
        early.Should().HaveCount(SamplesPerCycle);

        const int trigger = 156_000;                                  // 180 000 - 12 000 x 2.0
        CycleFramer.EarlyTriggerSamples(2.0).Should().Be(trigger);
        // 38 chunks of 4 096 = 155 648 < 156 000 <= 39 chunks = 159 744: the window held 159 744 samples when it fired.
        early.Take(trigger).Select((v, i) => v == i + 1).Should().AllBeEquivalentTo(true, "the head is the real audio, sample for sample");
        early.Skip(trigger).Should().AllBeEquivalentTo(0f, "everything after the trigger is zero, not the overshoot of the last chunk");
    }

    [Fact(DisplayName = "FR-083: 4.2b the full window is untouched by the early window")]
    public async Task FullWindow_IsUnchanged_ByTheEarlyWindow()
    {
        var run = await RunFramerAsync(1, _ => (true, 2.0));

        run.Windows.Should().NotBeEmpty();
        run.Windows[0].Pcm.Select((v, i) => v == i + 1).Should().AllBeEquivalentTo(true);
        ReferenceEquals(run.Windows[0].Pcm, run.Early[0].Pcm).Should().BeFalse("the early window is a copy");
    }

    [Fact(DisplayName = "FR-083: 4.2c one early window per cycle, carrying the cycle start and the dial frequency of the window it was cut from")]
    public async Task EarlyWindow_OncePerCycle_WithTheWindowsCycleStartAndDial()
    {
        var run = await RunFramerAsync(3, _ => (true, 2.0), dial: 14.074);

        run.Windows.Should().HaveCountGreaterOrEqualTo(3);
        run.Early.Should().HaveCountGreaterOrEqualTo(3);
        for (int i = 0; i < 3; i++)
        {
            run.Early[i].CycleStart.Should().Be(run.Windows[i].CycleStart);
            run.Early[i].Dial.Should().Be(14.074);
        }
    }

    [Fact(DisplayName = "FR-083: 4.2d no early window when the provider is null, the early output is null, or the provider reports disabled")]
    public async Task NoEarlyWindow_WhenOff()
    {
        (await RunFramerAsync(2, provider: null)).Early.Should().BeEmpty("no provider");
        (await RunFramerAsync(2, _ => (true, 2.0), passEarlyOutput: false)).Early.Should().BeEmpty("no early output");
        (await RunFramerAsync(2, _ => (false, 2.0))).Early.Should().BeEmpty("disabled");

        // And the ordinary windows are the same in every case.
        var off = await RunFramerAsync(2, provider: null);
        var on  = await RunFramerAsync(2, _ => (true, 2.0));
        off.Windows.Select(w => w.Pcm.Length).Should().Equal(on.Windows.Select(w => w.Pcm.Length));
        off.Windows.Select(w => w.CycleStart).Should().Equal(on.Windows.Select(w => w.CycleStart));
        for (int i = 0; i < off.Windows.Count; i++)
            off.Windows[i].Pcm.Should().Equal(on.Windows[i].Pcm, "an early window changes nothing about the ordinary windows");
    }

    [Fact(DisplayName = "FR-083: 4.2e the provider is read once per window, so the flag can change between windows")]
    public async Task Provider_IsReadOncePerWindow()
    {
        // Window 0 enabled, window 1 disabled, window 2 enabled.
        var run = await RunFramerAsync(3, call => (call % 2 == 0, 2.0));

        // One read per window started: the completed windows, plus at most the one still filling when the source ended.
        (run.ProviderCalls - run.Windows.Count).Should().BeInRange(0, 1);

        // Over the completed windows: an early window exists exactly for the windows whose read said enabled (0, 2, 4, ...).
        var completed = run.Windows.Select(w => w.CycleStart).ToList();
        var earlyOfCompleted = run.Early.Select(e => e.CycleStart).Where(completed.Contains).ToList();
        var expected = completed.Where((_, i) => i % 2 == 0).ToList();
        earlyOfCompleted.Should().Equal(expected);
    }

    [Theory(DisplayName = "FR-083: 4.2f the cut is clamped to 0.5 to 3.0 seconds")]
    [InlineData(2.0, 156_000)]
    [InlineData(0.5, 174_000)]
    [InlineData(3.0, 144_000)]
    [InlineData(0.0, 174_000)]
    [InlineData(10.0, 144_000)]
    public void EarlyTriggerSamples_ClampsTheCut(double cutSeconds, int expected)
        => CycleFramer.EarlyTriggerSamples(cutSeconds).Should().Be(expected);
}
