using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// sub-feas-speed-redesign, native half (tasks.md 8.1, 8.2, 8.6, 8.7a, 8.7, 8.8): drives the REAL <c>libft8.dll</c>.
///
/// <para>
/// The workspace pool is process-global, so every test here shares one xUnit collection (serial), and each starts
/// by calling <c>ft8_subfeas_pool_configure</c>, which resets the pool's peak and refusal counters.
/// </para>
/// <para>
/// The golden hashes (<c>tests/Ft8.FitProbe/golden/e1-base-5a6a4dc0.csv</c>, embedded here as <c>e1-golden.csv</c>) were
/// recorded from the BASE build (<c>2b39cf18</c>, shim 20260055, <c>libft8.dll</c> SHA-256 5a6a4dc0…e38c5) by the E1 probe.
/// A fit that no longer reproduces them means Stage A is not exact. 🔒 NFR-021 / HK-037: hashes, return codes, counts
/// and milliseconds only; synthetic Q-prefix fixtures.
/// </para>
/// </summary>
[Collection("subfeas-native-pool")]
public sealed class SubfeasNativeSpeedTests
{
    private const int PcmLen = 180_000;
    private const int GridSeed = 20260930; // the seed the golden CSV's grid rows were recorded with
    private const int GridCount = 48;

    // ── 8.1: the fit's output is bit-identical to the base build ─────────────────────────────────────

    [Fact(DisplayName = "8.1: Fit_NoDeadline_OutputBitIdenticalToBase (fixture cycles + pseudo-random grid, golden from the base DLL)")]
    public void Fit_NoDeadline_OutputBitIdenticalToBase()
    {
        Fresh(4);
        var golden = Golden();

        // The analytic signal of every fixture cycle.
        foreach (string wav in new[] { "synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav" })
        {
            float[] norm = Norm(Fixture(wav));
            (float[] re, float[] im) = Ft8LibInterop.SubfeasComputeAnalytic(norm);
            golden.Single(r => r.Kind == "analytic" && r.Label == wav).Hash.Should().Be(Hash(re, im), $"analytic of {wav}");
        }

        // Every pass-0 signal of synth-qso-01, fitted through the same path SubtractionPass uses.
        float[] norm1 = Norm(Fixture("synth-qso-01.wav"));
        (float[] re1, float[] im1) = Ft8LibInterop.SubfeasComputeAnalytic(norm1);
        var jobs = Pass0Jobs(norm1);
        var fixtureRows = golden.Where(r => r.Kind == "fit" && r.Label == "synth-qso-01.wav").OrderBy(r => r.Idx).ToList();
        jobs.Count.Should().Be(fixtureRows.Count);
        for (int i = 0; i < jobs.Count; i++)
        {
            (int rc, float[] shat) = Ft8LibInterop.SubfeasFitSignal(re1, im1, jobs[i].Tones, jobs[i].Dt, jobs[i].Freq);
            rc.ToString().Should().Be(fixtureRows[i].Rc, $"rc of fixture signal {i}");
            Hash(shat).Should().Be(fixtureRows[i].Hash, $"out_shat of fixture signal {i}");
        }

        // A spread of the grid: both rc 0 and rc -3 rows (signals near the buffer edges).
        var grid = GridJobs();
        var picks = golden.Where(r => r.Kind == "grid" && r.Rc == "0").Take(5)
            .Concat(golden.Where(r => r.Kind == "grid" && r.Rc == "-3").Take(4)).ToList();
        picks.Select(p => p.Rc).Distinct().Should().BeEquivalentTo(["0", "-3"], "the sample must cover both outcomes");
        foreach (var p in picks)
        {
            var j = grid[p.Idx];
            (int rc, float[] shat) = Ft8LibInterop.SubfeasFitSignal(re1, im1, j.Tones, j.Dt, j.Freq);
            rc.ToString().Should().Be(p.Rc, $"rc of grid signal {p.Idx}");
            Hash(shat).Should().Be(p.Hash, $"out_shat of grid signal {p.Idx}");
        }
    }

    // ── 8.2: cancellation ────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "8.2: Fit_CancelFlagPresetReturnsMinus4Promptly (zeroed buffer, no lease taken)")]
    public void Fit_CancelFlagPreset_ReturnsMinus4Promptly()
    {
        Fresh(2);
        (float[] re, float[] im, byte[] tones, float dt, float freq) = OneRealSignal();
        using var flag = new CancelFlag();
        flag.Set();

        var sw = Stopwatch.StartNew();
        (int rc, float[] shat) = Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq, flag.Pointer);
        sw.Stop();

        rc.Should().Be(-4);
        shat.Should().OnlyContain(v => v == 0f, "out_shat is zeroed on every non-zero return");
        sw.ElapsedMilliseconds.Should().BeLessThan(200, "a whole fit takes over a second: entry must bail out before FFT-scale work");
        Pool().Live.Should().Be(0, "an entry-time cancel must not even lease (let alone allocate) a workspace");
    }

    [Fact(DisplayName = "8.2: Fit_CancelFlagSetMidFitReturnsMinus4WithinOneIteration (and the workspace is returned)")]
    public void Fit_CancelFlagSetMidFit_ReturnsMinus4WithinOneIteration()
    {
        Fresh(2);
        (float[] re, float[] im, byte[] tones, float dt, float freq) = OneRealSignal();
        using var flag = new CancelFlag();

        var started = new ManualResetEventSlim();
        var task = Bg.Run(() =>
        {
            started.Set();
            return Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq, flag.Pointer);
        });
        started.Wait();
        WaitForLeased(1); // the fit holds its workspace lease, so it is inside the fit (about 1.2 s long), not before it
        var setAt = Stopwatch.StartNew();
        flag.Set();
        var (rc, shat) = task.Result;
        setAt.Stop();

        rc.Should().Be(-4);
        shat.Should().OnlyContain(v => v == 0f);
        // Measured longest stretch between checks is one fdot iteration, about 21 ms (tests/Ft8.FitProbe/reports).
        setAt.ElapsedMilliseconds.Should().BeLessThan(300, "the flag is checked at every iteration, so the stop is prompt");
        var pool = Pool();
        pool.Leased.Should().Be(0, "a cancelled fit must return its lease");
        pool.Idle.Should().Be(pool.Live);
    }

    [Fact(DisplayName = "8.2: cancelling one fit does not disturb other in-flight fits (each keeps its own flag and its own workspace)")]
    public void CancelOneFit_OthersUndisturbed()
    {
        Fresh(3);
        var golden = Golden();
        float[] norm = Norm(Fixture("synth-qso-01.wav"));
        (float[] re, float[] im) = Ft8LibInterop.SubfeasComputeAnalytic(norm);
        var grid = GridJobs();
        var ok = golden.Where(r => r.Kind == "grid" && r.Rc == "0").Take(3).ToList();

        using var doomed = new CancelFlag();
        using var f1 = new CancelFlag();
        using var f2 = new CancelFlag();
        var flags = new[] { doomed, f1, f2 };
        var tasks = ok.Select((p, i) => Bg.Run(() =>
            Ft8LibInterop.SubfeasFitSignal(re, im, grid[p.Idx].Tones, grid[p.Idx].Dt, grid[p.Idx].Freq, flags[i].Pointer))).ToArray();
        WaitForLeased(3); // all three fits are inside their fit before one is cancelled
        doomed.Set();
        foreach (var b in tasks) b.Join();

        tasks[0].Result.ReturnCode.Should().Be(-4);
        for (int i = 1; i < 3; i++)
        {
            tasks[i].Result.ReturnCode.Should().Be(0);
            Hash(tasks[i].Result.Shat).Should().Be(ok[i].Hash, "a fit running beside a cancelled one must be untouched");
        }
        Pool().Leased.Should().Be(0);
    }

    // ── 8.6: many workers x many cycles, forced cancels, deterministic per-signal hashes ─────────────

    [Fact(DisplayName = "8.6: Fit_ManyWorkersManyCycles_DeterministicAndNoInterference")]
    public void Fit_ManyWorkersManyCycles_DeterministicAndNoInterference()
    {
        const int workers = 8, rounds = 4;
        Fresh(workers);
        var golden = Golden();
        float[] norm = Norm(Fixture("synth-qso-01.wav"));
        (float[] re, float[] im) = Ft8LibInterop.SubfeasComputeAnalytic(norm);
        var grid = GridJobs();
        var signals = golden.Where(r => r.Kind == "grid" && r.Rc == "0").Take(workers).ToList();
        signals.Count.Should().Be(workers);

        int completed = 0, cancelled = 0;
        for (int round = 0; round < rounds; round++)
        {
            var flags = Enumerable.Range(0, workers).Select(_ => new CancelFlag()).ToArray();
            try
            {
                var tasks = signals.Select((p, w) => Bg.Run(() =>
                {
                    // Forced cancels, mixed in: some pre-set, some raised part-way, some never.
                    int mode = (w + round) % 4;
                    if (mode == 0) flags[w].Set();
                    else if (mode == 1) _ = Bg.Run(() => { WaitForLeased(1); flags[w].Set(); return 0; }); // raised once a fit is in flight
                    var j = grid[p.Idx];
                    return Ft8LibInterop.SubfeasFitSignal(re, im, j.Tones, j.Dt, j.Freq, flags[w].Pointer);
                })).ToArray();
                foreach (var b in tasks) b.Join();

                for (int w = 0; w < workers; w++)
                {
                    var (rc, shat) = tasks[w].Result;
                    if (rc == 0)
                    {
                        completed++;
                        Hash(shat).Should().Be(signals[w].Hash,
                            $"worker {w}, round {round}: a completed fit must equal its single-thread hash");
                    }
                    else
                    {
                        rc.Should().Be(-4, "the only other outcome is a forced cancel");
                        cancelled++;
                        shat.Should().OnlyContain(v => v == 0f);
                    }
                }
            }
            finally { foreach (var f in flags) f.Dispose(); }
        }

        completed.Should().BeGreaterThan(0);
        cancelled.Should().BeGreaterThan(0, "the stress must actually exercise the cancel path");
        var pool = Pool();
        pool.Leased.Should().Be(0);
        pool.Refusals.Should().Be(0, "at parallelism equal to the bound a lease must never be refused");
        pool.PeakLeased.Should().BeLessOrEqualTo(workers);
        pool.Live.Should().BeLessOrEqualTo(workers);
    }

    // ── 8.7a: leases and the bound ───────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "8.7a: Workspace_LeaseReturnedWhenFitCancelledFailsOrThrows")]
    public void Workspace_LeaseReturned_WhenFitCancelledOrFails()
    {
        Fresh(2);
        (float[] re, float[] im, byte[] tones, float dt, float freq) = OneRealSignal();

        // (a) cancelled mid-fit
        using (var flag = new CancelFlag())
        {
            var t = Bg.Run(() => Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq, flag.Pointer));
            WaitForLeased(1);
            flag.Set();
            t.Result.ReturnCode.Should().Be(-4);
        }
        Pool().Leased.Should().Be(0);

        // (b) bad arguments (a tone index outside [0,7]) fail before a lease is taken: rc -1 surfaces as an exception
        var bad = (byte[])tones.Clone();
        bad[3] = 9;
        var act = () => Ft8LibInterop.SubfeasFitSignal(re, im, bad, dt, freq);
        act.Should().Throw<InvalidOperationException>();
        Pool().Leased.Should().Be(0);

        // (c) a "no valid fit" (-3) outcome also returns its lease, and the next fit can use the same workspace
        (int rc3, _) = Ft8LibInterop.SubfeasFitSignal(re, im, tones, 6.0f, freq); // dt far beyond the buffer: every candidate off the edge
        rc3.Should().Be(-3);
        Pool().Leased.Should().Be(0);
        Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq).ReturnCode.Should().Be(0);
        var pool = Pool();
        pool.Leased.Should().Be(0);
        pool.Live.Should().Be(1, "all of that ran serially, so one workspace was enough and it was reused");
    }

    [Fact(DisplayName = "8.7a: Workspace_PoolNeverExceedsBound_NeverBlocksAtMatchingParallelism (and a lease beyond the bound is refused, not allocated)")]
    public void Workspace_PoolNeverExceedsBound()
    {
        // Matching parallelism: never refused, never above the bound.
        Fresh(3);
        (float[] re, float[] im, byte[] tones, float dt, float freq) = OneRealSignal();
        Parallel.For(0, 9, new ParallelOptions { MaxDegreeOfParallelism = 3 },
            _ => Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq).ReturnCode.Should().Be(0));
        var pool = Pool();
        pool.Refusals.Should().Be(0);
        pool.PeakLeased.Should().BeLessOrEqualTo(3);
        pool.Live.Should().BeLessOrEqualTo(3);

        // Beyond the bound: bound 1, two overlapping fits. One is refused (rc -1, which the interop raises), the other is fine.
        Fresh(1);
        using var hold = new CancelFlag();
        var first = Bg.Run(() => Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq, hold.Pointer));
        WaitForLeased(1); // the first fit holds the pool's only workspace
        var refused = () => Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq);
        refused.Should().Throw<InvalidOperationException>("the pool is at its bound with none idle: refuse rather than allocate past it");
        Pool().Refusals.Should().Be(1);
        Pool().Live.Should().Be(1, "the bound was not exceeded");
        hold.Set();
        first.Result.ReturnCode.Should().Be(-4);
        Pool().Leased.Should().Be(0);
    }

    // ── 8.7: growth and release ──────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "8.7: Workspace_NoGrowthAfterWarmup_AndFreedAtDispose (private bytes plateau; freed at shutdown; usable again)")]
    public void Workspace_NoGrowthAfterWarmup_AndFreedAtShutdown()
    {
        const int bound = 2;
        Fresh(bound);
        var golden = Golden();
        float[] norm = Norm(Fixture("synth-qso-01.wav"));
        (float[] re, float[] im) = Ft8LibInterop.SubfeasComputeAnalytic(norm);
        var grid = GridJobs();
        var row = golden.First(r => r.Kind == "grid" && r.Rc == "0");
        var j = grid[row.Idx];

        void Round() => Parallel.For(0, bound * 2, new ParallelOptions { MaxDegreeOfParallelism = bound },
            _ => Ft8LibInterop.SubfeasFitSignal(re, im, j.Tones, j.Dt, j.Freq).ReturnCode.Should().Be(0));

        Round(); // warm-up: the pool builds its workspaces
        int bytesPerWorkspace = Pool().BytesPerWorkspace;
        bytesPerWorkspace.Should().BeGreaterThan(20_000_000, "a workspace is about 25-30 MB");

        long before = PrivateBytes();
        for (int i = 0; i < 3; i++) Round();
        long grown = PrivateBytes() - before;
        // A leak would cost one workspace (about 30 MB) PER FIT: 12 fits here. Allow less than one workspace of noise.
        grown.Should().BeLessThan(bytesPerWorkspace, "private memory must plateau after warm-up, not grow with the number of fits");
        Pool().Live.Should().Be(bound);

        long beforeFree = ReturnableBytes();
        Ft8LibInterop.SubfeasPoolShutdown();
        var stats = Pool();
        stats.Live.Should().Be(0, "every idle workspace is freed at shutdown");
        stats.Idle.Should().Be(0);
        stats.Leased.Should().Be(0);
        (beforeFree - ReturnedBytesAfterFree()).Should().BeGreaterThan((long)(0.3 * bound * bytesPerWorkspace),
            "the memory really goes back, it is not just forgotten by the accounting");

        // A later decode after re-initialisation still works, and is still exact.
        Fresh(1);
        (int rc, float[] shat) = Ft8LibInterop.SubfeasFitSignal(re, im, j.Tones, j.Dt, j.Freq);
        rc.Should().Be(0);
        Hash(shat).Should().Be(row.Hash);
    }

    [Fact(DisplayName = "8.7: a shutdown while a fit holds a lease frees that workspace as it returns, never under the fit")]
    public void Shutdown_WhileLeased_FreesOnReturn()
    {
        Fresh(1);
        (float[] re, float[] im, byte[] tones, float dt, float freq) = OneRealSignal();
        using var flag = new CancelFlag();
        var t = Bg.Run(() => Ft8LibInterop.SubfeasFitSignal(re, im, tones, dt, freq, flag.Pointer));
        WaitForLeased(1);

        Ft8LibInterop.SubfeasPoolShutdown(); // the fit is mid-flight: its workspace must survive this call
        Pool().Leased.Should().Be(1);
        flag.Set();
        t.Result.ReturnCode.Should().Be(-4, "the fit ran to its (cancelled) end on an intact workspace");

        Pool().Live.Should().Be(0, "the leased workspace was freed when it came back");
    }

    // ── 8.8: M2, diagnostics off leaves the decode output alone ──────────────────────────────────────

    [Fact(DisplayName = "8.8: ResidualDecode_DiagnosticsOff_OutputFieldsEqualDiagnosticsOn (and the LLR statistics really are skipped)")]
    public void ResidualDecode_DiagnosticsOff_OutputFieldsEqualDiagnosticsOn()
    {
        try
        {
            // A noise cycle has many failing candidates; a fixture cycle has real decodes. Both must be unchanged.
            foreach (float[] pcm in new[] { NoiseCycle(), Norm(Fixture("synth-qso-02.wav")) })
            {
                Ft8LibInterop.SetDiagnosticsEnabled(true);
                var on = Ft8LibInterop.DecodeAll(pcm);
                float floorOn = Ft8LibInterop.GetLastNoiseFloorDb();

                Ft8LibInterop.SetDiagnosticsEnabled(false);
                var off = Ft8LibInterop.DecodeAll(pcm);
                int failOff = Ft8LibInterop.GetLastLlrStats(Ft8LibInterop.MaxDecodePasses).FailCount.Sum();
                float floorOff = Ft8LibInterop.GetLastNoiseFloorDb();

                off.Select(r => (r.FreqHz, r.Dt, r.Snr, r.Message)).Should().Equal(on.Select(r => (r.FreqHz, r.Dt, r.Snr, r.Message)),
                    "diagnostics off must not change a single decode output field, SNR included");
                floorOff.Should().Be(floorOn, "the noise floor feeds the local-noise SNR fallback and is NOT gated");
                failOff.Should().Be(0, "with diagnostics off the LDPC-failure statistics are not accumulated");
            }

            // Control: the switch is not a no-op on a cycle that has failing candidates.
            Ft8LibInterop.SetDiagnosticsEnabled(true);
            Ft8LibInterop.DecodeAll(NoiseCycle());
            Ft8LibInterop.GetLastLlrStats(Ft8LibInterop.MaxDecodePasses).FailCount.Sum()
                .Should().BeGreaterThan(0, "control: with diagnostics ON a noise cycle produces failing candidates to count");
        }
        finally { Ft8LibInterop.SetDiagnosticsEnabled(true); }
    }

    [Fact(DisplayName = "8.8: NoiseFloorFallback_SnrUnchanged (residual decode SNR fields identical with diagnostics on and off)")]
    public void NoiseFloorFallback_SnrUnchanged()
    {
        try
        {
            float[] norm = Norm(Fixture("synth-qso-01.wav"));
            (float[] re, float[] im) = Ft8LibInterop.SubfeasComputeAnalytic(norm);
            Fresh(4);
            var residual = (float[])norm.Clone();
            foreach (var job in Pass0Jobs(norm))
            {
                var (rc, shat) = Ft8LibInterop.SubfeasFitSignal(re, im, job.Tones, job.Dt, job.Freq);
                rc.Should().BeOneOf(0, -3);
                for (int i = 0; i < PcmLen; i++) residual[i] -= shat[i];
            }

            Ft8LibInterop.SetDiagnosticsEnabled(true);
            var on = Ft8LibInterop.DecodeAll(residual);
            var snrOn = Ft8LibInterop.GetLastSnrTerms(64);
            Ft8LibInterop.SetDiagnosticsEnabled(false);
            var off = Ft8LibInterop.DecodeAll(residual);
            var snrOff = Ft8LibInterop.GetLastSnrTerms(64);

            off.Select(r => (r.FreqHz, r.Dt, r.Snr)).Should().Equal(on.Select(r => (r.FreqHz, r.Dt, r.Snr)));
            snrOff.SignalDb.Should().Equal(snrOn.SignalDb);
            snrOff.LocalNoiseDb.Should().Equal(snrOn.LocalNoiseDb);
        }
        finally { Ft8LibInterop.SetDiagnosticsEnabled(true); }
    }

    // ── A5 end to end, real fits ─────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "A5: with real native fits a short budget stops the pass inside the budget, as a deadline, not an exception")]
    public async Task RealFits_ShortBudget_StopsInsideBudget_AsDeadline()
    {
        float[] norm = Norm(Fixture("synth-qso-01.wav"));
        var interop = new Ft8NativeInteropAdapter();
        var pass0 = interop.DecodeAll(norm);
        pass0.Length.Should().BeGreaterThan(1);
        var log = new LineLogger();
        // 1 700 ms budget: fits are cancelled at 200 ms, long before a single fit (about 1.2 s) can finish.
        var budget = TimeSpan.FromMilliseconds(1700);

        var sw = Stopwatch.StartNew();
        var result = await SubtractionPass.RunAsync(interop, norm, pass0, maxDegreeOfParallelism: 2, log, deadline: budget);
        sw.Stop();

        result.Should().BeEmpty();
        sw.Elapsed.Should().BeLessThan(budget, "the wall-clock deadline is real now: in-flight native fits are stopped");
        var line = log.Lines.Single(l => l.StartsWith("Sub-feas residual pass: residualDecodes=", StringComparison.Ordinal));
        line.Should().Contain("deadlineAbandoned=True").And.Contain("containedException=False");
        Pool().Leased.Should().Be(0);
    }

    // ── helpers ──────────────────────────────────────────────────────────────────────────────────────

    /// <summary>A clean pool at the given bound: idle workspaces from earlier tests are freed first, counters reset.</summary>
    private static void Fresh(int bound)
    {
        Ft8LibInterop.SubfeasPoolShutdown();
        Ft8LibInterop.SubfeasPoolConfigure(bound);
    }

    /// <summary>Blocks until the pool reports at least <paramref name="count"/> leased workspaces (a fit is in flight), instead of sleeping a guessed time.</summary>
    private static void WaitForLeased(int count)
        => Poll.UntilAsync(() => Pool().Leased >= count, timeout: TimeSpan.FromSeconds(30),
                timeoutMessage: () => $"the pool never reached {count} leased workspace(s)")
            .GetAwaiter().GetResult();

    private static float[] Norm(float[] raw) => Ft8Decoder.NormalisePcm(raw, 0.20f);

    private static float[] NoiseCycle()
    {
        var rng = new Random(12345);
        var pcm = new float[PcmLen];
        for (int i = 0; i < pcm.Length; i++) pcm[i] = (float)(rng.NextDouble() * 2 - 1);
        return Norm(pcm);
    }

    private static float[] Fixture(string name)
    {
        var asm = Assembly.GetExecutingAssembly();
        string resource = asm.GetManifestResourceNames().Single(n => n.EndsWith(name, StringComparison.OrdinalIgnoreCase));
        using Stream s = asm.GetManifestResourceStream(resource)!;
        return WavReader.Read(s);
    }

    /// <summary>The pass-0 decodes of a cycle that <see cref="SubtractionPass"/> would fit (same predicate, restated).</summary>
    private static List<(byte[] Tones, float Dt, float Freq)> Pass0Jobs(float[] norm)
    {
        var jobs = new List<(byte[], float, float)>();
        foreach (var nr in Ft8LibInterop.DecodeAll(norm))
        {
            string msg = nr.Message.TrimEnd();
            if (msg.Contains('<') || msg.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length < 3) continue;
            var tones = new byte[Ft8LibInterop.EncodedToneCount];
            try { Ft8LibInterop.EncodeMessage(msg, tones); } catch (InvalidOperationException) { continue; }
            jobs.Add((tones, nr.Dt, nr.FreqHz));
        }
        return jobs;
    }

    /// <summary>One real signal from a fixture cycle plus the analytic buffer it is fitted against (a fit of about 1.2 s).</summary>
    private static (float[] Re, float[] Im, byte[] Tones, float Dt, float Freq) OneRealSignal()
    {
        float[] norm = Norm(Fixture("synth-qso-01.wav"));
        (float[] re, float[] im) = Ft8LibInterop.SubfeasComputeAnalytic(norm);
        var job = Pass0Jobs(norm).First();
        return (re, im, job.Tones, job.Dt, job.Freq);
    }

    /// <summary>The E1 probe's pseudo-random (tones, dt, freq) grid, regenerated identically (same seed, same draw order).</summary>
    private static List<(byte[] Tones, float Dt, float Freq)> GridJobs()
    {
        var rng = new Random(GridSeed);
        var jobs = new List<(byte[], float, float)>();
        for (int g = 0; g < GridCount; g++)
        {
            var tones = new byte[79];
            for (int s = 0; s < 79; s++) tones[s] = (byte)rng.Next(8);
            float dt = (float)(rng.NextDouble() * 4.6 - 1.4);
            float freq = (float)(rng.NextDouble() * 2800 + 200);
            jobs.Add((tones, dt, freq));
        }
        return jobs;
    }

    private static string Hash(params float[][] arrays)
    {
        using var h = SHA256.Create();
        foreach (float[] a in arrays)
        {
            var bytes = new byte[a.Length * sizeof(float)];
            Buffer.BlockCopy(a, 0, bytes, 0, bytes.Length);
            h.TransformBlock(bytes, 0, bytes.Length, null, 0);
        }
        h.TransformFinalBlock([], 0, 0);
        return Convert.ToHexString(h.Hash!).ToLowerInvariant();
    }

    private sealed record GoldenRow(string Kind, string Label, int Idx, string Rc, string Hash);

    private static List<GoldenRow> Golden()
    {
        var asm = Assembly.GetExecutingAssembly();
        using var s = asm.GetManifestResourceStream("e1-golden.csv")
            ?? throw new InvalidOperationException("embedded golden CSV missing");
        using var r = new StreamReader(s);
        var rows = new List<GoldenRow>();
        r.ReadLine(); // header
        while (r.ReadLine() is { } line)
        {
            line = line.Trim();
            if (line.Length == 0) continue;
            var c = line.Split(',');
            rows.Add(new GoldenRow(c[0], c[1], int.Parse(c[2]), c[3], c[4]));
        }
        return rows;
    }

    private static PoolStats Pool()
    {
        int[] s = Ft8LibInterop.SubfeasPoolGetStats();
        return new PoolStats(s[0], s[1], s[2], s[3], s[4], s[5], s[6]);
    }

    private sealed record PoolStats(int Bound, int Live, int Idle, int Leased, int PeakLeased, int Refusals, int BytesPerWorkspace);

    private static long PrivateBytes()
    {
        GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
        using var p = Process.GetCurrentProcess();
        return p.PrivateMemorySize64;
    }

    /// <summary>
    /// The figure "memory really goes back" is measured on. Windows: private bytes, as before (the CRT heap returns a freed
    /// 25-30 MB block to the OS at once). Linux: .NET reports <c>VmData</c> as private bytes, which is VIRTUAL size, and
    /// glibc keeps freed address space in its arenas (the mmap threshold rises after the first large free, so later blocks
    /// are heap-backed) — it never falls at <c>free</c>, even though the pages do go back. Measured in WSL Debian: after
    /// shutdown VmData unchanged, RssAnon -32 MB, and a further -74 MB after <c>malloc_trim(0)</c> (a property of the
    /// allocator, not a leak: <c>Live</c>/<c>Idle</c>/<c>Leased</c> are 0). So on Linux the physical anonymous RSS is read.
    /// </summary>
    private static long ReturnableBytes()
        => OperatingSystem.IsLinux() ? AnonRssBytes() : PrivateBytes();

    /// <summary>The same figure after the free: on Linux the freed arena pages are first handed back with <c>malloc_trim(0)</c>.</summary>
    private static long ReturnedBytesAfterFree()
    {
        if (OperatingSystem.IsLinux()) LibC.TrimHeap();
        return ReturnableBytes();
    }

    private static long AnonRssBytes()
    {
        GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
        string line = File.ReadLines("/proc/self/status").Single(l => l.StartsWith("RssAnon:", StringComparison.Ordinal));
        return long.Parse(line.Split(':', 2)[1].Trim().Split(' ')[0], System.Globalization.CultureInfo.InvariantCulture) * 1024;
    }

    private static class LibC
    {
        [DllImport("libc", EntryPoint = "malloc_trim")]
        private static extern int MallocTrim(UIntPtr pad);

        /// <summary>Ask glibc to return free heap pages to the OS. Absent on musl: then the measurement simply sees no trim.</summary>
        public static void TrimHeap()
        {
            try { MallocTrim(UIntPtr.Zero); }
            catch (EntryPointNotFoundException) { }
        }
    }

    /// <summary>The cancel flag the native fit reads: an int in pinned managed memory, written with a volatile write.</summary>
    /// <summary>
    /// A fit on its own thread. Plain threads, not tasks: xUnit1031 forbids blocking on a Task in a test, and these tests
    /// exist to block until native calls return.
    /// </summary>
    private sealed class Bg<T>
    {
        private readonly Thread _thread;
        private T _value = default!;
        private Exception? _error;

        public Bg(Func<T> body)
        {
            _thread = new Thread(() => { try { _value = body(); } catch (Exception ex) { _error = ex; } }) { IsBackground = true };
            _thread.Start();
        }

        public void Join() => _thread.Join();

        public T Result
        {
            get
            {
                _thread.Join();
                if (_error is not null) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(_error).Throw();
                return _value;
            }
        }
    }

    private static class Bg
    {
        public static Bg<T> Run<T>(Func<T> body) => new(body);
    }

    private sealed class CancelFlag : IDisposable
    {
        private readonly int[] _cell = new int[1];
        private GCHandle _handle;
        public CancelFlag() { _handle = GCHandle.Alloc(_cell, GCHandleType.Pinned); }
        public IntPtr Pointer => _handle.AddrOfPinnedObject();
        public void Set() => Volatile.Write(ref _cell[0], 1);
        public void Dispose() { if (_handle.IsAllocated) _handle.Free(); }
    }

    private sealed class LineLogger : ILogger<Ft8Decoder>
    {
        public List<string> Lines { get; } = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            lock (Lines) Lines.Add(formatter(state, exception));
        }
    }
}
