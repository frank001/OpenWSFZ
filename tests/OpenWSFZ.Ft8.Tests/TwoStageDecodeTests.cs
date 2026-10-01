using System.Collections.Concurrent;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// <see cref="Ft8Decoder.DecodeTwoStageAsync"/> (sub-feas-speed-redesign two-stage publish, design.md D9): pass-0 is
/// published as batch 1 BEFORE the residual pass starts, the residual pass's new decodes come back as batch 2, and
/// with the flag OFF it is the ordinary single batch. Uses the real native encoder (via
/// <see cref="SubtractionFlagTests.SequencedInterop"/>) so the payload de-dup behaves as in production; the decode and
/// fit calls are faked. This is the entry a test or replay harness uses WITHOUT the daemon pump.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages only; assertions on counts, order and timings.</para>
/// </summary>
public sealed class TwoStageDecodeTests
{
    private static readonly DateTime CycleStart = new(2026, 9, 30, 12, 0, 0, DateTimeKind.Utc);

    private static Ft8NativeResult Msg(string message, int freqHz = 1500, float dt = 0.2f, int snr = -10)
        => new() { FreqHz = freqHz, Dt = dt, Snr = snr, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static Ft8Decoder Build(IFt8NativeInterop interop, ILogger<Ft8Decoder>? log = null, bool flagOn = true)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart), log, interop: interop);
        d.SetSubtractionEnabled(flagOn);
        return d;
    }

    [Fact(DisplayName = "Two-stage: batch 1 is handed over BEFORE the residual pass starts, batch 2 is the new residual decode")]
    public async Task Batch1BeforeResidualPass_Batch2IsTheNewDecode()
    {
        var interop = new SubtractionFlagTests.SequencedInterop(
            pass0: [Msg("Q1ABC Q1XYZ JO33")], residual: [Msg("Q1DEF Q1UVW EN37")]);
        var decoder = Build(interop);
        IReadOnlyList<DecodeResult>? batch1 = null;
        int decodeAllAtHandOver = -1; bool analyticAtHandOver = true;

        var batch2 = await decoder.DecodeTwoStageAsync(LoudPcm(), CycleStart, null, b =>
        {
            batch1 = b;
            decodeAllAtHandOver = interop.DecodeAllCallCount;   // only pass-0's own call so far
            analyticAtHandOver  = interop.ComputeAnalyticCalled; // the residual pass has not begun
            return Task.CompletedTask;
        });

        batch1.Should().NotBeNull();
        batch1!.Select(r => r.Message).Should().Equal("Q1ABC Q1XYZ JO33");
        decodeAllAtHandOver.Should().Be(1, "batch 1 leaves after pass 0 and before the residual DecodeAll");
        analyticAtHandOver.Should().BeFalse("the residual pass must not have started when batch 1 is handed over");
        batch2.Select(r => r.Message).Should().Equal("Q1DEF Q1UVW EN37");
        interop.DecodeAllCallCount.Should().Be(2);
    }

    [Fact(DisplayName = "Two-stage: batch 1 and batch 2 carry the same cycle time and the same mapping (time, band, fields)")]
    public async Task BothBatches_MappedIdentically()
    {
        var interop = new SubtractionFlagTests.SequencedInterop(
            pass0: [Msg("Q1ABC Q1XYZ JO33", 1200, 0.24f, -8)], residual: [Msg("Q1DEF Q1UVW EN37", 2100, 0.31f, -19)]);
        var decoder = Build(interop);
        IReadOnlyList<DecodeResult>? batch1 = null;

        var batch2 = await decoder.DecodeTwoStageAsync(LoudPcm(), CycleStart, "20m", b => { batch1 = b; return Task.CompletedTask; });

        batch1!.Single().Time.Should().Be("12:00:00");
        batch2.Single().Time.Should().Be("12:00:00", "both batches belong to the same cycle");
        batch1!.Single().Band.Should().Be("20m");
        batch2.Single().Band.Should().Be("20m");
        (batch2.Single().FreqHz, batch2.Single().Snr, batch2.Single().Dt).Should().Be((2100, -19, 0.3));
    }

    [Fact(DisplayName = "Two-stage: the union of the batches equals what the single-batch DecodeAsync returns (nothing lost, nothing duplicated)")]
    public async Task UnionEqualsSingleBatchOutput()
    {
        Ft8NativeResult[] p0 = [Msg("Q1ABC Q1XYZ JO33"), Msg("Q1GHI Q1JKL FN20", 1800)];
        Ft8NativeResult[] rs = [Msg("Q1DEF Q1UVW EN37", 2100), Msg("Q1ABC Q1XYZ JO33")]; // second is a re-find: filtered

        var single = await Build(new SubtractionFlagTests.SequencedInterop(p0, rs))
            .DecodeAsync(LoudPcm(), CycleStart, currentBand: null, CancellationToken.None);

        IReadOnlyList<DecodeResult>? b1 = null;
        var b2 = await Build(new SubtractionFlagTests.SequencedInterop(p0, rs))
            .DecodeTwoStageAsync(LoudPcm(), CycleStart, null, b => { b1 = b; return Task.CompletedTask; });

        b1!.Select(r => r.Message).Concat(b2.Select(r => r.Message)).Should().Equal(single.Select(r => r.Message));
        b1!.Concat(b2).Select(r => r.Message).Should().OnlyHaveUniqueItems("no text appears twice in a cycle");
    }

    [Fact(DisplayName = "Two-stage: residual finds nothing new, or the pass is abandoned -> batch 2 is empty (nothing to publish)")]
    public async Task NothingNew_OrAbandoned_Batch2Empty()
    {
        var refind = new SubtractionFlagTests.SequencedInterop([Msg("Q1ABC Q1XYZ JO33")], [Msg("Q1ABC Q1XYZ JO33")]);
        (await Build(refind).DecodeTwoStageAsync(LoudPcm(), CycleStart, null, _ => Task.CompletedTask)).Should().BeEmpty();

        var av = new SubtractionFlagTests.SequencedInterop([Msg("Q1ABC Q1XYZ JO33")], [Msg("Q1DEF Q1UVW EN37")]) { FitSignalThrows = true };
        int calls = 0;
        (await Build(av).DecodeTwoStageAsync(LoudPcm(), CycleStart, null, _ => { calls++; return Task.CompletedTask; }))
            .Should().BeEmpty("an access violation in a fit abandons the pass: pass-0's batch 1 stands, no batch 2");
        calls.Should().Be(1, "batch 1 was still published exactly once");
    }

    [Fact(DisplayName = "Two-stage flag OFF: exactly one batch, the ordinary single-batch output, residual pass never touched (P-9)")]
    public async Task FlagOff_OneBatch_Identical()
    {
        var interop = new SubtractionFlagTests.SequencedInterop([Msg("Q1ABC Q1XYZ JO33")], [Msg("Q1DEF Q1UVW EN37")]);
        var decoder = Build(interop, flagOn: false);
        var batches = new List<IReadOnlyList<DecodeResult>>();

        var second = await decoder.DecodeTwoStageAsync(LoudPcm(), CycleStart, null, b => { batches.Add(b); return Task.CompletedTask; });

        second.Should().BeEmpty();
        batches.Should().ContainSingle();
        batches[0].Select(r => r.Message).Should().Equal("Q1ABC Q1XYZ JO33");
        interop.ComputeAnalyticCalled.Should().BeFalse();
        interop.DecodeAllCallCount.Should().Be(1);

        var plain = await Build(new SubtractionFlagTests.SequencedInterop([Msg("Q1ABC Q1XYZ JO33")], [Msg("Q1DEF Q1UVW EN37")]), flagOn: false)
            .DecodeAsync(LoudPcm(), CycleStart, currentBand: null, CancellationToken.None);
        batches[0].Should().BeEquivalentTo(plain, "the flag-OFF batch is byte for byte what DecodeAsync returns");
    }

    [Fact(DisplayName = "Two-stage: a silent cycle is still ONE (empty) batch 1: the answerer, caller and ALL.TXT count it")]
    public async Task SilentCycle_OneEmptyBatch()
    {
        var interop = new SubtractionFlagTests.SequencedInterop([Msg("Q1ABC Q1XYZ JO33")], []);
        var batches = new List<IReadOnlyList<DecodeResult>>();

        var second = await Build(interop).DecodeTwoStageAsync(new float[180_000], CycleStart, null,
            b => { batches.Add(b); return Task.CompletedTask; });

        second.Should().BeEmpty();
        batches.Should().ContainSingle().Which.Should().BeEmpty();
        interop.DecodeAllCallCount.Should().Be(0);
    }

    [Fact(DisplayName = "Two-stage: no pass-0 decodes -> batch 1 only (empty), the residual pass is skipped")]
    public async Task NoPass0Decodes_ResidualSkipped()
    {
        var interop = new SubtractionFlagTests.SequencedInterop([], [Msg("Q1DEF Q1UVW EN37")]);
        var batches = new List<IReadOnlyList<DecodeResult>>();

        var second = await Build(interop).DecodeTwoStageAsync(LoudPcm(), CycleStart, null, b => { batches.Add(b); return Task.CompletedTask; });

        second.Should().BeEmpty();
        batches.Should().ContainSingle().Which.Should().BeEmpty();
        interop.ComputeAnalyticCalled.Should().BeFalse();
    }

    [Fact(DisplayName = "Two-stage: the per-cycle elapsed line reports time to BATCH 1, not the whole residual pass (P-8)")]
    public async Task ElapsedLine_IsTimeToBatch1()
    {
        var log = new LineLog();
        // A slow residual pass: one fit sleeps 600 ms. Time to batch 1 is a few ms; the pass takes over 600 ms.
        var interop = new SubtractionFlagTests.SequencedInterop([Msg("Q1ABC Q1XYZ JO33")], [Msg("Q1DEF Q1UVW EN37")]) { FitDelayMs = 600 };

        await Build(interop, log).DecodeTwoStageAsync(LoudPcm(), CycleStart, null, _ => Task.CompletedTask);

        var elapsed = log.Lines.Single(l => l.StartsWith("Cycle 12:00:00: ") && l.Contains("decode(s) found, elapsed="));
        long ms = long.Parse(elapsed.Split("elapsed=")[1].Split(' ')[0]);
        ms.Should().BeLessThan(500, "flag ON reports the time to batch 1, which is what the operator experiences");
        var pass = log.Lines.Single(l => l.StartsWith("Sub-feas residual pass: residualDecodes="));
        long passMs = long.Parse(pass.Split("elapsedMs=")[1].Split(' ')[0]);
        passMs.Should().BeGreaterThan(500, "the residual pass line is unchanged and still times the whole pass");
    }

    [Fact(DisplayName = "Two-stage: SubtractionEnabled reflects the flag; the callback is required")]
    public async Task FlagProperty_AndNullCallback()
    {
        var d = Build(new SubtractionFlagTests.SequencedInterop([], []), flagOn: false);
        d.SubtractionEnabled.Should().BeFalse();
        d.SetSubtractionEnabled(true);
        d.SubtractionEnabled.Should().BeTrue();
        var act = () => d.DecodeTwoStageAsync(LoudPcm(), CycleStart, null, null!);
        await act.Should().ThrowAsync<ArgumentNullException>();
    }

    private sealed class LineLog : ILogger<Ft8Decoder>
    {
        public ConcurrentQueue<string> Queue { get; } = new();
        public List<string> Lines => Queue.ToList();
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => Queue.Enqueue(formatter(state, exception));
    }
}
