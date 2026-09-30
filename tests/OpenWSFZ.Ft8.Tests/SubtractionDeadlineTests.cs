using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.InteropServices;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// sub-feas-speed-redesign, managed half (tasks.md 8.3, 8.4, 8.5, 8.9 and the A3/M2 call-shape checks):
/// the hard deadline (A5), the thread-count configuration (A4), the pool sizing per cycle (A3), the diagnostics-off
/// residual decode (M2) and the Debug-log guards (M3). Uses <see cref="SubtractionPassTests.FakeInterop"/>, which
/// fakes only the native calls the orchestrator drives; the native side is covered by
/// <c>SubfeasNativeSpeedTests</c> against the real DLL.
///
/// <para>🔒 NFR-021 / HK-037: only synthetic Q-prefix messages; assertions are on counts, flags and timings.</para>
/// </summary>
public sealed class SubtractionDeadlineTests
{
    private const int PcmLength = 180_000;

    // ── 8.3: a deadline during the fits is a DEADLINE, never an exception ─────────────────────────────

    [Fact(DisplayName = "8.3: SubtractionPass_DeadlineDuringFits_AbandonsAsDeadlineNotException")]
    public async Task DeadlineDuringFits_AbandonsAsDeadlineNotException()
    {
        var log = new CapturingLogger();
        // A "slow fit" that honours the cancel flag exactly like the native one: runs until the flag is set, then -4.
        var interop = new SubtractionPassTests.FakeInterop
        {
            FitBehaviour = flag => SpinUntilFlagThenCancel(flag, guard: TimeSpan.FromSeconds(10)),
            ResidualDecodeResults = [Msg("Q1GHI Q1JKL FN20")], // would be "new" if the pass were not abandoned
        };
        var budget = TimeSpan.FromMilliseconds(2000);
        var sw = Stopwatch.StartNew();

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log,
            deadline: budget);
        sw.Stop();

        result.Should().BeEmpty("the cycle keeps its pass-0 results; the residual pass adds nothing");
        interop.DecodeAllCalled.Should().BeFalse("the residual decode must not start after the deadline");
        var line = log.PassLines().Should().ContainSingle().Subject;
        line.Should().Contain("deadlineAbandoned=True").And.Contain("containedException=False");
        line.Should().StartWith("Sub-feas residual pass: residualDecodes=0 ");
        sw.Elapsed.Should().BeLessThan(budget, "the whole call must stay inside the budget");
        sw.Elapsed.Should().BeGreaterThan(budget - SubtractionPass.SubtractionResidualDecodeReserve - TimeSpan.FromMilliseconds(100),
            "the flag is not set before budget - reserve");
    }

    [Fact(DisplayName = "8.3b: a fit that returns -4 with no deadline configured is still a deadline outcome, not a contained exception")]
    public async Task FitReturnsMinus4_IsDeadlineNotException()
    {
        var log = new CapturingLogger();
        var interop = new SubtractionPassTests.FakeInterop { FitSignalReturnCode = Ft8LibInterop.SubfeasRcCancelled };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log);

        result.Should().BeEmpty();
        interop.DecodeAllCalled.Should().BeFalse();
        log.PassLines().Should().ContainSingle().Which
            .Should().Contain("deadlineAbandoned=True").And.Contain("containedException=False");
    }

    [Fact(DisplayName = "8.3c: the cancel flag is a live, writable int for the whole fit, and starts at 0")]
    public async Task CancelFlag_StartsAtZero_AndIsWritableMemory()
    {
        int? seenAtStart = null;
        var interop = new SubtractionPassTests.FakeInterop
        {
            FitBehaviour = flag =>
            {
                flag.Should().NotBe(IntPtr.Zero, "a real pointer is always passed so the deadline can be honoured");
                seenAtStart = Marshal.ReadInt32(flag);
                return (0, new float[PcmLength]);
            },
        };

        await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, logger: null,
            deadline: TimeSpan.FromSeconds(13));

        seenAtStart.Should().Be(0);
    }

    // ── 8.4: not enough time left for the residual decode ────────────────────────────────────────────

    [Fact(DisplayName = "8.4: SubtractionPass_LessThanReserveLeft_SkipsResidualDecode (budget already under the reserve)")]
    public async Task LessThanReserveAtStart_SkipsFitsAndResidualDecode()
    {
        var log = new CapturingLogger();
        var interop = new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [Msg("Q1GHI Q1JKL FN20")] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log,
            deadline: SubtractionPass.SubtractionResidualDecodeReserve - TimeSpan.FromMilliseconds(1));

        result.Should().BeEmpty();
        interop.FitSignalCallCount.Should().Be(0, "no fit may start when the flag would already be due");
        interop.DecodeAllCalled.Should().BeFalse();
        log.PassLines().Should().ContainSingle().Which.Should().Contain("deadlineAbandoned=True");
    }

    [Fact(DisplayName = "8.4b: fits that finish only after budget - reserve leave the residual decode unstarted")]
    public async Task FitsFinishInsideTheReserve_ResidualDecodeNotStarted()
    {
        var log = new CapturingLogger();
        var budget = TimeSpan.FromMilliseconds(2200);
        var flagDue = budget - SubtractionPass.SubtractionResidualDecodeReserve;
        // A fit that ignores the flag and finishes 150 ms after it was due: the fits end inside the reserve.
        var interop = new SubtractionPassTests.FakeInterop
        {
            FitBehaviour = _ =>
            {
                Thread.Sleep(flagDue + TimeSpan.FromMilliseconds(150));
                return (0, new float[PcmLength]);
            },
            ResidualDecodeResults = [Msg("Q1GHI Q1JKL FN20")],
        };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log,
            deadline: budget);

        result.Should().BeEmpty();
        interop.DecodeAllCalled.Should().BeFalse("with less than the reserve left the residual decode must not start");
        log.PassLines().Should().ContainSingle().Which
            .Should().Contain("deadlineAbandoned=True").And.Contain("containedException=False");
    }

    [Fact(DisplayName = "8.4c: with time to spare the residual decode runs (control for 8.4/8.4b)")]
    public async Task PlentyOfTime_ResidualDecodeRuns()
    {
        var interop = new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [Msg("Q1DEF Q1UVW EN37")] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, logger: null,
            deadline: TimeSpan.FromSeconds(13));

        result.Should().ContainSingle();
        interop.DecodeAllCalled.Should().BeTrue();
    }

    [Fact(DisplayName = "8.4d: the reserve is the Architect's 1 500 ms (Amendment 1), a named constant")]
    public void ReserveIs1500ms()
        => SubtractionPass.SubtractionResidualDecodeReserve.Should().Be(TimeSpan.FromMilliseconds(1500));

    // ── A3: the pool is sized at the cycle boundary; M2: the residual decode has diagnostics off ─────

    [Fact(DisplayName = "A3: the native workspace pool is sized to the parallelism before the fits, once per cycle")]
    public async Task PoolConfiguredToParallelism_BeforeFits()
    {
        var interop = new SubtractionPassTests.FakeInterop();

        await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 3, logger: null);

        interop.PoolConfigureCalls.Should().Equal([3]);
    }

    [Fact(DisplayName = "A3: parallelism above the native pool cap is clamped to it (a lease beyond the bound would be refused)")]
    public async Task PoolBoundClampedToNativeCap()
    {
        var interop = new SubtractionPassTests.FakeInterop();

        await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 500, logger: null);

        interop.PoolConfigureCalls.Should().Equal([SubtractionPass.SubfeasPoolMaxBound]);
    }

    [Fact(DisplayName = "M2: the residual decode runs with diagnostics off, and diagnostics are restored afterwards (also on failure)")]
    public async Task ResidualDecode_DiagnosticsOffThenRestored()
    {
        var interop = new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [] };
        await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, logger: null);

        var ev = interop.Events.Where(e => e is "Diag(false)" or "DecodeAll" or "Diag(true)").ToList();
        ev.Should().Equal("Diag(false)", "DecodeAll", "Diag(true)");

        var failing = new SubtractionPassTests.FakeInterop { ResidualDecodeThrowsAv = true };
        await SubtractionPass.RunAsync(failing, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, logger: null);
        failing.Events.Where(e => e is "Diag(false)" or "Diag(true)").Should().Equal("Diag(false)", "Diag(true)");
    }

    // ── 8.5: thread count (A4) ────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-077: 8.5: MaxThreads_ZeroIsAutoAndClamp (table over ProcessorCount and configured value)")]
    //           cpus configured expected clamped
    [InlineData(1,  0,   1,  false)]
    [InlineData(2,  0,   1,  false)]
    [InlineData(4,  0,   2,  false)]
    [InlineData(16, 0,   14, false)]
    [InlineData(1,  -1,  1,  true)]
    [InlineData(2,  -1,  1,  true)]
    [InlineData(4,  -1,  1,  true)]
    [InlineData(16, -1,  1,  true)]
    [InlineData(1,  1,   1,  false)]
    [InlineData(2,  1,   1,  false)]
    [InlineData(4,  1,   1,  false)]
    [InlineData(16, 1,   1,  false)]
    [InlineData(1,  999, 1,  true)]
    [InlineData(2,  999, 2,  true)]
    [InlineData(4,  999, 4,  true)]
    [InlineData(16, 999, 16, true)]
    [InlineData(16, 16,  16, false)]
    [InlineData(16, 17,  16, true)]
    public void MaxThreads_ZeroIsAutoAndClamp(int cpus, int configured, int expected, bool expectClamped)
    {
        int effective = SubtractionThreads.Resolve(configured, cpus, out bool clamped);

        effective.Should().Be(expected);
        clamped.Should().Be(expectClamped);
    }

    [Fact(DisplayName = "FR-077: 8.5: an absent key deserialises to 0 = auto (the default), and 0 equals auto exactly")]
    public void AbsentKeyIsAuto()
    {
        new DecoderConfig().SubtractionMaxThreads.Should().Be(0);
        SubtractionThreads.Resolve(new DecoderConfig().SubtractionMaxThreads, 16, out _)
            .Should().Be(SubtractionThreads.Resolve(0, 16, out _)).And.Be(14);
    }

    [Fact(DisplayName = "FR-077: 8.5: MaxThreads_ChangeTakesEffectNextCycle (pool bound and fit parallelism follow the config, per cycle)")]
    public async Task MaxThreads_ChangeTakesEffectNextCycle()
    {
        var interop = new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [Msg("Q1ABC Q1XYZ JO33")] };
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), logger: null, interop: interop);
        decoder.SetSubtractionEnabled(true);
        int cpus = Environment.ProcessorCount;

        decoder.SetSubtractionMaxThreads(1);
        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);
        decoder.SetSubtractionMaxThreads(2);
        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);
        decoder.SetSubtractionMaxThreads(0);
        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        // each cycle reads the configured value afresh
        interop.PoolConfigureCalls.Should().Equal([1, Math.Min(2, cpus), Math.Max(1, cpus - 2)]);
    }

    [Fact(DisplayName = "FR-077: 8.5: an out-of-range value logs exactly one warning at apply, and none over subsequent cycles or re-applies")]
    public async Task OutOfRangeValue_OneWarning_AtApply_NeverPerCycle()
    {
        var log = new CapturingLogger();
        var interop = new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [Msg("Q1ABC Q1XYZ JO33")] };
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), log, interop: interop);
        decoder.SetSubtractionEnabled(true);

        decoder.SetSubtractionMaxThreads(999_999);
        log.Warnings("subtractionMaxThreads").Should().ContainSingle().Which.Should().Contain("999999");

        for (int i = 0; i < 20; i++) await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);
        decoder.SetSubtractionMaxThreads(999_999); // an unrelated config save re-applies the same value
        log.Warnings("subtractionMaxThreads").Should().HaveCount(1, "never per cycle, and not again for the same value");

        decoder.SetSubtractionMaxThreads(0);
        decoder.SetSubtractionMaxThreads(-1);       // a different bad value warns once more
        log.Warnings("subtractionMaxThreads").Should().HaveCount(2);
        decoder.SetSubtractionMaxThreads(2);
        log.Warnings("subtractionMaxThreads").Should().HaveCount(2, "an in-range value never warns");
    }

    // ── 8.9: Debug loops are not run when Debug is off (M3) ───────────────────────────────────────

    [Fact(DisplayName = "8.9: DebugLogLoops_NotRun_WhenDebugDisabled (no per-pass Debug entry is even created)")]
    public async Task DebugLogLoops_NotRun_WhenDebugDisabled()
    {
        var off = new CapturingLogger { DebugEnabled = false };
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), off,
            interop: new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [Msg("Q1ABC Q1XYZ JO33")] });

        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        off.Count(l => l.Level == LogLevel.Debug && l.Text.StartsWith("Iterative subtraction: pass", StringComparison.Ordinal))
            .Should().Be(0, "with Debug off, neither per-pass loop may run or format anything");

        var on = new CapturingLogger { DebugEnabled = true };
        var decoderOn = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), on,
            interop: new SubtractionPassTests.FakeInterop { ResidualDecodeResults = [Msg("Q1ABC Q1XYZ JO33")] });
        await decoderOn.DecodeAsync(LoudPcm(), CancellationToken.None);
        on.Count(l => l.Level == LogLevel.Debug && l.Text.StartsWith("Iterative subtraction: pass", StringComparison.Ordinal))
            .Should().BeGreaterThan(0, "control: with Debug on the same lines are still produced");
    }

    // ── helpers ───────────────────────────────────────────────────────────────────────────────────

    private static (int ReturnCode, float[] Shat) SpinUntilFlagThenCancel(IntPtr flag, TimeSpan guard)
    {
        var sw = Stopwatch.StartNew();
        while (Marshal.ReadInt32(flag) == 0)
        {
            if (sw.Elapsed > guard) return (0, new float[PcmLength]); // guard: the flag never came (test would fail on its asserts)
            Thread.Sleep(1);
        }
        return (Ft8LibInterop.SubfeasRcCancelled, new float[PcmLength]);
    }

    private static Ft8NativeResult Msg(string message)
        => new() { FreqHz = 1500, Dt = 0.2f, Snr = -10, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[PcmLength];
        for (int i = 0; i < pcm.Length; i++) pcm[i] = 0.1f;
        return pcm;
    }

    /// <summary>Records every entry (level + formatted text) so tests can assert on what was and was not logged.</summary>
    private sealed class CapturingLogger : ILogger<Ft8Decoder>, ILogger
    {
        public bool DebugEnabled { get; init; } = true;
        private readonly ConcurrentQueue<(LogLevel Level, string Text)> _entries = new();

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => logLevel != LogLevel.Debug || DebugEnabled;

        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
            => _entries.Enqueue((logLevel, formatter(state, exception)));

        public int Count(Func<(LogLevel Level, string Text), bool> predicate) => _entries.Count(predicate);

        public List<string> PassLines()
            => _entries.Where(e => e.Text.StartsWith("Sub-feas residual pass: residualDecodes=", StringComparison.Ordinal))
                       .Select(e => e.Text).ToList();

        public List<string> Warnings(string containing)
            => _entries.Where(e => e.Level == LogLevel.Warning && e.Text.Contains(containing, StringComparison.Ordinal))
                       .Select(e => e.Text).ToList();
    }
}
