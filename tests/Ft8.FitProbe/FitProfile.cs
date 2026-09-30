using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;

// Stage B step 1 (sub-feas-speed-redesign tasks.md 15.1): the per-phase profile of ONE fit, at 1, 4 and 14 CONCURRENT
// workers, on real signals. TEST-ONLY: no product-path change, no shim bump, integers/stamps only (NFR-021 / HK-037).
//
//   fitprofile --dll <libft8.dll> (--selection <e1_selection.json> --artefacts-root <dir> [--cycles N] | --wav <f>...)
//              [--workers 1,4,14] [--fits-per-worker K] --out <csv>
//   fitsummary <csv>                   per-phase table (median, p95, max ms) per worker count, penalty vs 1 worker
//   fitcompare <a.csv> <b.csv>         equivalence: (cycle, signal, rc, sha256(out_shat)) identical between two runs
//
// HOW IT MEASURES. The fits go through the SHIPPED path: Ft8LibInterop.SubfeasFitSignal with the real workspace pool
// sized by ft8_subfeas_pool_configure(W). W dedicated threads each run fits back to back (so W fits are in flight
// the whole time, unlike a cycle's 3 to 5 signals), each measuring its own wall time (managed stopwatch, marshalling
// included, as in the product). Phases come from a timed COPY of subfeas_fit.c (native/make_timed_fit.py, built by
// native/build_timed_fit_dll.py): QueryPerformanceCounter reads around each phase, recorded into THREAD-LOCAL
// accumulators and read on the same worker thread right after the call. Run it against the SHIPPED dll too (phase
// columns are -1) and `fitcompare` the two: out_shat must be bit-identical.
//
// Signals: the pass-0 decodes of the chosen E1 cycles, decoded through the same libft8.dll. Workers are NOT pinned
// (no affinity is set); the logical processor count is written into the CSV header row.
internal static class FitProfile
{
    private const int PcmLen = 180_000;
    private static readonly string[] Phases =
        ["lease", "smooth", "step1", "step2", "final", "step3", "envelope", "write", "fit_total"];

    private const string Header =
        "kind,workers,cycle,signal,rc,wall_us,lease_us,smooth_us,step1_us,step2_us,final_us,step3_us,envelope_us,write_us,fit_total_us,shat_sha256";

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int PtGet(long[] o, int n);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate long PtFreq();

    public static int Run(string[] a) => a[0] switch
    {
        "fitprofile" => Profile(a[1..]),
        "fitsummary" => Summary(a[1..]),
        "fitcompare" => Compare(a[1..]),
        _ => 2,
    };

    // ── fitprofile ───────────────────────────────────────────────────────

    private sealed record Job(int Cycle, int Signal, float[] Re, float[] Im, byte[] Tones, float Dt, float Freq);

    private static int Profile(string[] a)
    {
        string? dll = null, outPath = null, selection = null, root = null;
        var wavs = new List<string>();
        int cycles = 5, perWorker = 3;
        int[] workerCounts = [1, 4, 14];
        for (int i = 0; i < a.Length; i++)
        {
            switch (a[i])
            {
                case "--dll": dll = a[++i]; break;
                case "--out": outPath = a[++i]; break;
                case "--wav": wavs.Add(a[++i]); break;
                case "--selection": selection = a[++i]; break;
                case "--artefacts-root": root = a[++i]; break;
                case "--cycles": cycles = int.Parse(a[++i]); break;
                case "--fits-per-worker": perWorker = int.Parse(a[++i]); break;
                case "--workers": workerCounts = a[++i].Split(',').Select(int.Parse).ToArray(); break;
                default: Console.Error.WriteLine($"unknown argument {a[i]}"); return 2;
            }
        }
        if (dll is null || outPath is null) { Console.Error.WriteLine("need --dll and --out"); return 2; }

        // Cycles: evenly spread over the selection file (or the given WAVs), so the set is fixed and reproducible.
        var paths = new List<(string Label, string Path)>();
        foreach (var w in wavs) paths.Add((System.IO.Path.GetFileNameWithoutExtension(w), w));
        if (selection is not null)
        {
            if (root is null) { Console.Error.WriteLine("--selection needs --artefacts-root"); return 2; }
            using var doc = JsonDocument.Parse(File.ReadAllText(selection));
            var all = doc.RootElement.GetProperty("cycles").EnumerateArray()
                .Select(c => (Run: c.GetProperty("run").GetString()!, Stamp: c.GetProperty("stamp").GetString()!)).ToList();
            int n = Math.Min(cycles, all.Count);
            for (int k = 0; k < n; k++)
            {
                var c = all[k * all.Count / n];
                paths.Add((c.Stamp, System.IO.Path.Combine(root, $"{c.Run}_endurance_run-gathered", "owsfz", "wav", $"{c.Stamp}.wav")));
            }
        }
        if (paths.Count == 0) { Console.Error.WriteLine("no cycles"); return 2; }

        string target = System.IO.Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        File.Copy(dll, target, overwrite: true);
        Console.Error.WriteLine($"dll under test sha256={Probe.Hex(SHA256.HashData(File.ReadAllBytes(target)))}");

        var interop = new Ft8NativeInteropAdapter();
        var h = NativeLibrary.Load(target);
        bool timed = NativeLibrary.TryGetExport(h, "ft8_subfeas_pt_get", out var pg);
        PtGet? ptGet = timed ? Marshal.GetDelegateForFunctionPointer<PtGet>(pg) : null;
        long freq = timed && NativeLibrary.TryGetExport(h, "ft8_subfeas_pt_frequency", out var pf)
            ? Marshal.GetDelegateForFunctionPointer<PtFreq>(pf)() : 1;
        Console.Error.WriteLine(timed ? "timed fit exports found: phase columns are filled" : "no timed exports: phase columns are -1 (shipped DLL)");

        var rows = new List<string>
        {
            $"# logical_processors={Environment.ProcessorCount} workers_pinned=no cycles={paths.Count} counter_hz={freq}",
            Header,
        };

        // Load the cycles, decode pass 0, build the analytic signal and the job list; time the analytic call and one
        // residual DecodeAll per cycle (single thread, the way the product does them).
        var jobs = new List<Job>();
        int ci = 0;
        foreach (var (label, path) in paths)
        {
            float[] norm = Ft8Decoder.NormalisePcm(Probe.ReadWav(path), 0.20f);
            var pass0 = interop.DecodeAll(norm);

            long t0 = Stopwatch.GetTimestamp();
            (float[] re, float[] im) = interop.SubfeasComputeAnalytic(norm);
            long analyticUs = Us(Stopwatch.GetTimestamp() - t0, Stopwatch.Frequency);
            rows.Add($"analytic,1,{ci},-1,0,{analyticUs},-1,-1,-1,-1,-1,-1,-1,-1,-1,-");

            var cycleJobs = new List<Job>();
            foreach (var nr in pass0)
            {
                string msg = nr.Message.TrimEnd();
                if (!Probe.IsReencodable(msg)) continue;
                try { cycleJobs.Add(new Job(ci, cycleJobs.Count, re, im, interop.EncodeMessage(msg), nr.Dt, nr.FreqHz)); }
                catch (InvalidOperationException) { }
            }

            // One residual DecodeAll, exactly as SubtractionPass does it: pcm minus every fitted signal.
            interop.SubfeasPoolConfigure(1);
            var residual = (float[])norm.Clone();
            foreach (var j in cycleJobs)
            {
                var (rc, shat) = interop.SubfeasFitSignal(j.Re, j.Im, j.Tones, j.Dt, j.Freq, IntPtr.Zero);
                if (rc == 0) for (int s = 0; s < PcmLen; s++) residual[s] -= shat[s];
            }
            long r0 = Stopwatch.GetTimestamp();
            interop.SetDiagnosticsEnabled(false);
            interop.DecodeAll(residual);
            interop.SetDiagnosticsEnabled(true);
            long residualUs = Us(Stopwatch.GetTimestamp() - r0, Stopwatch.Frequency);
            rows.Add($"residual_decode,1,{ci},-1,{cycleJobs.Count},{residualUs},-1,-1,-1,-1,-1,-1,-1,-1,-1,-");
            // pass-0 decode time, for reference
            long p0 = Stopwatch.GetTimestamp();
            interop.DecodeAll(norm);
            rows.Add($"pass0_decode,1,{ci},-1,{pass0.Length},{Us(Stopwatch.GetTimestamp() - p0, Stopwatch.Frequency)},-1,-1,-1,-1,-1,-1,-1,-1,-1,-");

            jobs.AddRange(cycleJobs);
            ci++;
        }
        if (jobs.Count == 0) { Console.Error.WriteLine("no re-encodable signals in the chosen cycles"); return 1; }
        Console.Error.WriteLine($"signals={jobs.Count} over {paths.Count} cycles");

        // Warm-up: one fit of each signal on one thread (page faults, first workspace build), discarded.
        interop.SubfeasPoolConfigure(1);
        foreach (var j in jobs.Take(2)) interop.SubfeasFitSignal(j.Re, j.Im, j.Tones, j.Dt, j.Freq, IntPtr.Zero);

        foreach (int w in workerCounts)
        {
            interop.SubfeasPoolShutdown();
            interop.SubfeasPoolConfigure(w);           // the real pool, sized exactly as the product sizes it
            // W=1 fits EVERY signal once (at least), so a run against the shipped DLL covers the same set for fitcompare.
            var results = new string[w == 1 ? Math.Max(perWorker, jobs.Count) : w * perWorker];
            var start = new ManualResetEventSlim();
            int next = -1;
            var threads = new Thread[w];
            for (int t = 0; t < w; t++)
            {
                threads[t] = new Thread(() =>
                {
                    start.Wait();
                    int idx;
                    while ((idx = Interlocked.Increment(ref next)) < results.Length)
                    {
                        var j = jobs[idx % jobs.Count];
                        long t0 = Stopwatch.GetTimestamp();
                        string rcText, hash;
                        try
                        {
                            var (rc, shat) = interop.SubfeasFitSignal(j.Re, j.Im, j.Tones, j.Dt, j.Freq, IntPtr.Zero);
                            rcText = rc.ToString();
                            hash = Probe.HashFloats(shat);
                        }
                        catch (Exception ex) { rcText = "EX:" + ex.GetType().Name; hash = "-"; }
                        long wallTicks = Stopwatch.GetTimestamp() - t0;
                        var v = new long[16];
                        bool have = ptGet is not null && ptGet(v, 16) > 0;   // this thread's phase ticks, right after the call
                        string P(int k) => have ? Us(v[k], freq).ToString() : "-1";
                        results[idx] = $"fit,{w},{j.Cycle},{j.Signal},{rcText},{Us(wallTicks, Stopwatch.Frequency)}," +
                                       $"{string.Join(',', Enumerable.Range(0, Phases.Length).Select(P))},{hash}";
                    }
                }) { IsBackground = true };
                threads[t].Start();
            }
            var wall = Stopwatch.StartNew();
            start.Set();
            foreach (var t in threads) t.Join();
            wall.Stop();
            rows.AddRange(results);
            rows.Add($"batch,{w},-1,-1,{results.Length},{wall.ElapsedMilliseconds * 1000},-1,-1,-1,-1,-1,-1,-1,-1,-1,-");
            Console.Error.WriteLine($"workers={w}: {results.Length} fits in {wall.ElapsedMilliseconds} ms");
        }

        File.WriteAllText(outPath, string.Join('\n', rows) + "\n");
        return 0;
    }

    private static long Us(long ticks, long freq) => ticks * 1_000_000L / freq;

    // ── fitsummary ───────────────────────────────────────────────────────

    private static List<string[]> Fits(string[] lines, string kind)
        => lines.Where(l => l.StartsWith(kind + ",")).Select(l => l.Split(',')).ToList();

    private static int Summary(string[] a)
    {
        var lines = File.ReadAllLines(a[0]).Where(l => l.Length > 0).ToArray();
        Console.WriteLine(lines[0]);
        var fits = Fits(lines, "fit");
        bool timed = fits.All(f => f[6] != "-1");
        string[] cols = ["wall", "lease", "smooth", "step1", "step2", "final", "step3", "envelope", "write", "fit_total"];
        double Med(IEnumerable<double> v) { var s = v.OrderBy(x => x).ToArray(); return s.Length % 2 == 1 ? s[s.Length / 2] : (s[s.Length / 2 - 1] + s[s.Length / 2]) / 2; }
        double P95(IEnumerable<double> v) { var s = v.OrderBy(x => x).ToArray(); return s[Math.Min(s.Length - 1, (int)Math.Ceiling(0.95 * s.Length) - 1)]; }

        Console.WriteLine("all values milliseconds; one row per phase, medians per worker count, then the penalty vs 1 worker");
        var byW = fits.GroupBy(f => int.Parse(f[1])).OrderBy(g => g.Key).ToList();
        Console.WriteLine($"{"phase",-12}" + string.Concat(byW.Select(g => $"{"W=" + g.Key + " med",12}{"p95",9}{"max",9}")));
        double[] baseMed = new double[cols.Length];
        for (int c = 0; c < cols.Length; c++)
        {
            if (c > 0 && !timed) break;
            Console.Write($"{cols[c],-12}");
            foreach (var g in byW)
            {
                var v = g.Where(f => f[4] == "0").Select(f => double.Parse(f[5 + c]) / 1000).ToArray();   // rc 0 only: a -3 (off-edge) fit is not a fit
                if (g.Key == byW[0].Key) baseMed[c] = Med(v);
                Console.Write($"{Med(v),12:F1}{P95(v),9:F1}{v.Max(),9:F1}");
            }
            Console.WriteLine();
        }
        Console.WriteLine("per-fit concurrency penalty (median wall at W / median wall at the first worker count): " +
            string.Join(", ", byW.Select(g => $"W={g.Key}: {Med(g.Where(f => f[4] == "0").Select(f => double.Parse(f[5]) / 1000)) / baseMed[0]:F2}x")));
        if (timed)
        {
            Console.WriteLine("per-phase penalty vs first worker count:");
            for (int c = 3; c <= 7; c++)
                Console.WriteLine($"  {cols[c],-10}" + string.Join("  ", byW.Select(g =>
                    $"W={g.Key}: {Med(g.Where(f => f[4] == "0").Select(f => double.Parse(f[5 + c]) / 1000)) / baseMed[c]:F2}x")));
        }
        foreach (var kind in new[] { "analytic", "residual_decode", "pass0_decode" })
        {
            var v = Fits(lines, kind).Select(f => double.Parse(f[5]) / 1000).ToArray();
            if (v.Length > 0) Console.WriteLine($"{kind,-16} median {Med(v),8:F1} ms  max {v.Max(),8:F1} ms  ({v.Length} cycles)");
        }
        foreach (var f in Fits(lines, "batch"))
            Console.WriteLine($"batch W={f[1]}: {f[4]} fits in {double.Parse(f[5]) / 1000:F0} ms wall = {double.Parse(f[5]) / 1000 / double.Parse(f[4]):F0} ms per fit of throughput");
        return 0;
    }

    // ── fitcompare ───────────────────────────────────────────────────────

    private static int Compare(string[] a)
    {
        string[] Key(string file) => File.ReadAllLines(file).Where(l => l.StartsWith("fit,"))
            .Select(l => l.Split(',')).Where(f => f[1] == "1")
            .Select(f => $"{f[2]}|{f[3]}|{f[4]}|{f[15]}").OrderBy(x => x, StringComparer.Ordinal).ToArray();
        var x = Key(a[0]); var y = Key(a[1]);
        bool same = x.Length > 0 && x.SequenceEqual(y);
        Console.WriteLine(same ? $"EQUIVALENT: {x.Length} single-worker fits, rc and sha256(out_shat) identical"
                               : $"FAIL: {x.Length} vs {y.Length} fits, or a difference in rc / out_shat hash");
        return same ? 0 : 1;
    }
}
