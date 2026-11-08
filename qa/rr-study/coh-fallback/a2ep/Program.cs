// COH-FALLBACK step 4, row A2(e') (Architect spec section 16; QA-owned; numbers only, HK-037: no payload, text or hash of either is written).
//
// For each of the first 100 selected cycles of 20261009_1752: read the WAV, run the ordinary native decode (ft8_decode_all) on this thread, take the
// candidate snapshot on the same thread, then run the fallback twice on that snapshot:
//   - single thread  : Ft8LibInterop.CohFallbackRun(pcm, snapshot, -1, none)          (the Stage 1 / Stage 2 walk, output-first)
//   - parallel       : CohFallbackParallelRunner.Run(CohFallbackLibBackend.Instance, pcm, snapshot, -1, workers, none)   (the step-4 path)
// and compare the PUBLISHED payload list (CoherentFallbackSelector.Select), IN ORDER: identical N/N, any difference is a FAIL.
// workers = 8 is the gate row; 1 and 2 are descriptive. Also reported: whether ALL rows (state, payload, SNR, F1b, estimate) are identical, and
// the published count against the per-cycle count the Stage 1 export wrote (a0_per_cycle.csv, n_published) when that file is given.
//
// The internal types of OpenWSFZ.Ft8 are reached by reflection (no InternalsVisibleTo for this harness; no src/ change, HK-011).
//
//   A2ep.dll --selection <json> --run 20261009_1752 --stratum Y40 --wav-root <artefacts> --out <csv> --summary <json> --pin <dll sha256> [--stage1-csv <a0_per_cycle.csv>]
using System.Collections;
using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

internal static class A2ep
{
    private const int PcmSamples = 180_000;
    private const int SampleRateHz = 12_000;
    private const int GateWorkers = 8;
    private static readonly int[] DescriptiveWorkers = [2, 1];
    private const int PayloadKeyBytes = 10;           // the selector's payload key (CoherentFallbackSelector.PayloadKeyBytes)
    private const double NoDeadline = -1.0;
    private const double ProductionTargetRms = 0.20;      // Ft8Decoder.PcmNormalisationTargetRms
    private const double SilenceRmsThreshold = 1e-6;       // wavio.SILENCE_RMS_THRESHOLD

    private static int Main(string[] argv)
    {
        var a = new Dictionary<string, string>();
        for (int i = 0; i + 1 < argv.Length; i += 2) a[argv[i].TrimStart('-')] = argv[i + 1];
        string Req(string k) => a.TryGetValue(k, out var v) ? v : throw new ArgumentException("missing --" + k);
        string run = Req("run"), stratum = Req("stratum"), wavRoot = Req("wav-root"), outCsv = Req("out"), summaryPath = Req("summary"), pin = Req("pin").ToLowerInvariant();

        var ft8 = typeof(OpenWSFZ.Ft8.Ft8Decoder).Assembly;
        string dir = Path.GetDirectoryName(ft8.Location)!;
        string dll = Path.Combine(dir, "libft8.dll");
        string actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(dll))).ToLowerInvariant();
        if (actual != pin) { Console.Error.WriteLine($"PIN MISMATCH actual={actual} pinned={pin}"); return 3; }

        var interop = ft8.GetType("OpenWSFZ.Ft8.Interop.Ft8LibInterop") ?? throw new InvalidOperationException("Ft8LibInterop not found");
        var runner = ft8.GetType("OpenWSFZ.Ft8.CohFallbackParallelRunner") ?? throw new InvalidOperationException("CohFallbackParallelRunner not found");
        var selector = ft8.GetType("OpenWSFZ.Ft8.CoherentFallbackSelector") ?? throw new InvalidOperationException("CoherentFallbackSelector not found");
        var backendType = ft8.GetType("OpenWSFZ.Ft8.Interop.CohFallbackLibBackend") ?? throw new InvalidOperationException("CohFallbackLibBackend not found");
        var backend = backendType.GetField("Instance", BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;
        var decodeAll = interop.GetMethod("DecodeAll", BindingFlags.Public | BindingFlags.Static)!;
        var snapshotM = interop.GetMethod("CohFallbackSnapshot", BindingFlags.Public | BindingFlags.Static)!;
        var singleM = interop.GetMethod("CohFallbackRun", BindingFlags.Public | BindingFlags.Static)!;
        var parallelM = runner.GetMethod("Run", BindingFlags.Public | BindingFlags.Static)!;
        var selectM = selector.GetMethod("Select", BindingFlags.Public | BindingFlags.Static)!;

        using var selDoc = JsonDocument.Parse(File.ReadAllBytes(Req("selection")));
        var stamps = selDoc.RootElement.GetProperty("runs").GetProperty(run).GetProperty(stratum).EnumerateArray().Select(e => e.GetString()!).ToList();
        if (a.TryGetValue("only", out var only)) { var keep = only.Split(',').ToHashSet(); stamps = stamps.Where(keep.Contains).ToList(); }
        bool dups = a.ContainsKey("dups");
        var stage1 = new Dictionary<string, int>();
        if (a.TryGetValue("stage1-csv", out var s1))
            foreach (var line in File.ReadLines(s1).Skip(1))
            {
                var f = line.Split(',');
                stage1[f[0]] = int.Parse(f[14], CultureInfo.InvariantCulture);      // n_published
            }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outCsv))!);
        using var csv = new StreamWriter(outCsv, false, new UTF8Encoding(false));
        csv.WriteLine("stamp,eligible,n_single,single_ms,n_par8,par8_ms,list_identical_8,rows_identical_8,list_identical_2,list_identical_1,stage1_n_published,count_equals_stage1");

        int cycles = 0, identical8 = 0, rowsIdentical8 = 0, identical2 = 0, identical1 = 0, countsVsStage1 = 0, countsChecked = 0, withOutput = 0;
        var differentStamps = new List<string>();
        foreach (var stamp in stamps)
        {
            float[] pcm = ReadWav(Path.Combine(wavRoot, $"{run}_endurance_run-gathered", "owsfz", "wav", stamp + ".wav"));
            decodeAll.Invoke(null, new object[] { pcm });                          // same thread as the snapshot (thread-local candidate list)
            var snap = (byte[])snapshotM.Invoke(null, null)!;

            var sw = System.Diagnostics.Stopwatch.StartNew();
            var single = singleM.Invoke(null, new object[] { pcm, snap, NoDeadline, CancellationToken.None })!;
            double singleMs = sw.Elapsed.TotalMilliseconds;
            var singleList = Published(selectM, single);
            if (dups) Console.WriteLine($"DUPS {stamp} {DuplicateGroups(single)}");

            sw.Restart();
            var par8 = parallelM.Invoke(null, new object[] { backend, pcm, snap, NoDeadline, GateWorkers, CancellationToken.None })!;
            double par8Ms = sw.Elapsed.TotalMilliseconds;
            var par8List = Published(selectM, par8);

            bool same8 = ListEqual(singleList, par8List);
            bool rows8 = RowsEqual(single, par8);
            bool same2 = true, same1 = true;
            foreach (int w in DescriptiveWorkers)
            {
                var p = parallelM.Invoke(null, new object[] { backend, pcm, snap, NoDeadline, w, CancellationToken.None })!;
                bool same = ListEqual(singleList, Published(selectM, p));
                if (w == 2) same2 = same; else same1 = same;
            }

            int eligible = (int)Stats(single).GetType().GetProperty("Eligible")!.GetValue(Stats(single))!;
            int s1n = stage1.TryGetValue(stamp, out var v) ? v : -1;
            bool eq1 = s1n >= 0 && s1n == singleList.Count;
            if (s1n >= 0) { countsChecked++; if (eq1) countsVsStage1++; }
            cycles++;
            if (same8) identical8++; else differentStamps.Add(stamp);
            if (rows8) rowsIdentical8++;
            if (same2) identical2++;
            if (same1) identical1++;
            if (singleList.Count > 0) withOutput++;
            csv.WriteLine(string.Join(",", stamp, eligible, singleList.Count, F(singleMs), par8List.Count, F(par8Ms), same8 ? 1 : 0, rows8 ? 1 : 0, same2 ? 1 : 0, same1 ? 1 : 0,
                s1n, s1n < 0 ? "" : (eq1 ? "1" : "0")));
        }
        csv.Flush();

        var summary = new
        {
            row = "A2(e')",
            build_dll_sha256 = actual,
            workers_gate = GateWorkers,
            cycles,
            cycles_with_published_output = withOutput,
            list_identical_8 = identical8,
            rows_identical_8 = rowsIdentical8,
            list_identical_2_descriptive = identical2,
            list_identical_1_descriptive = identical1,
            different_stamps_8 = differentStamps,
            count_equals_stage1_export = $"{countsVsStage1}/{countsChecked}",
            result = identical8 == cycles ? "PASS" : "FAIL",
        };
        File.WriteAllText(summaryPath, JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine(JsonSerializer.Serialize(summary));
        return identical8 == cycles ? 0 : 1;
    }

    /// <summary>Descriptive (no payload written): among the NewGated rows, how many share a payload key, and the edge flags / estimates of each group's members.</summary>
    private static string DuplicateGroups(object result)
    {
        var rows = ((IEnumerable)result.GetType().GetProperty("Rows")!.GetValue(result)!).Cast<object>().ToList();
        var groups = new Dictionary<string, List<(int Idx, bool Edge, double F1b, float OutF, float OutDt)>>();
        int newGated = 0;
        var distinct12 = new HashSet<string>();
        for (int i = 0; i < rows.Count; i++)
        {
            var t = rows[i].GetType();
            if (Convert.ToInt32(t.GetProperty("State")!.GetValue(rows[i])) != 4) continue;     // CohFallbackState.NewGated
            newGated++;
            distinct12.Add(Convert.ToHexString((byte[])t.GetProperty("Payload")!.GetValue(rows[i])!));
            string key = Convert.ToHexString((byte[])t.GetProperty("Payload")!.GetValue(rows[i])!, 0, PayloadKeyBytes);
            if (!groups.TryGetValue(key, out var g)) groups[key] = g = new();
            g.Add((i, (bool)t.GetProperty("Edge")!.GetValue(rows[i])!, (double)t.GetProperty("F1bDb")!.GetValue(rows[i])!,
                   (float)t.GetProperty("OutFreqHz")!.GetValue(rows[i])!, (float)t.GetProperty("OutDtS")!.GetValue(rows[i])!));
        }
        var multi = groups.Values.Where(g => g.Count > 1).Select(g => "[" + string.Join(";", g.Select(m =>
            $"cand{m.Idx} edge={(m.Edge ? 1 : 0)} f1b={m.F1b.ToString("F2", CultureInfo.InvariantCulture)} df={m.OutF.ToString("F2", CultureInfo.InvariantCulture)} dt={m.OutDt.ToString("F2", CultureInfo.InvariantCulture)}")) + "]");
        return $"newGated={newGated} distinct10={groups.Count} distinct12={distinct12.Count} collapsed={newGated - groups.Count} multiGroups={string.Join(" ", multi)}";
    }

    private static string F(double x) => x.ToString("F1", CultureInfo.InvariantCulture);

    private static object Stats(object result) => result.GetType().GetProperty("Stats")!.GetValue(result)!;

    /// <summary>The published payload keys (first 10 payload bytes of each selected row), in publication order.</summary>
    private static List<string> Published(MethodInfo select, object result)
    {
        var rows = result.GetType().GetProperty("Rows")!.GetValue(result)!;
        var picked = (IEnumerable)select.Invoke(null, new[] { rows })!;
        var list = new List<string>();
        foreach (var row in picked)
        {
            var payload = (byte[])row.GetType().GetProperty("Payload")!.GetValue(row)!;
            list.Add(Convert.ToHexString(payload, 0, PayloadKeyBytes));
        }
        return list;
    }

    private static bool ListEqual(List<string> x, List<string> y) => x.Count == y.Count && x.Zip(y).All(p => p.First == p.Second);

    /// <summary>Every row, in candidate order: state, estimate, SNR, F1b and payload identical (descriptive).</summary>
    private static bool RowsEqual(object r1, object r2)
    {
        var a = ((IEnumerable)r1.GetType().GetProperty("Rows")!.GetValue(r1)!).Cast<object>().ToList();
        var b = ((IEnumerable)r2.GetType().GetProperty("Rows")!.GetValue(r2)!).Cast<object>().ToList();
        if (a.Count != b.Count) return false;
        for (int i = 0; i < a.Count; i++)
        {
            foreach (var prop in a[i].GetType().GetProperties().Where(p => p.GetIndexParameters().Length == 0 && p.Name != "EqualityContract"))
            {
                var x = prop.GetValue(a[i]);
                var y = prop.GetValue(b[i]);
                bool eq = x is byte[] bx ? bx.AsSpan().SequenceEqual((byte[])y!) : Equals(x, y);
                if (!eq) return false;
            }
        }
        return true;
    }

    private static float[] ReadWav(string path)
    {
        byte[] b = File.ReadAllBytes(path);
        if (b.Length < 44 || Encoding.ASCII.GetString(b, 0, 4) != "RIFF" || Encoding.ASCII.GetString(b, 8, 4) != "WAVE") throw new InvalidDataException("not a RIFF/WAVE file");
        int pos = 12, channels = 0, rate = 0, bits = 0, dataOff = -1, dataLen = 0;
        while (pos + 8 <= b.Length)
        {
            string id = Encoding.ASCII.GetString(b, pos, 4);
            int len = BitConverter.ToInt32(b, pos + 4);
            if (id == "fmt ") { channels = BitConverter.ToInt16(b, pos + 10); rate = BitConverter.ToInt32(b, pos + 12); bits = BitConverter.ToInt16(b, pos + 22); }
            else if (id == "data") { dataOff = pos + 8; dataLen = len; break; }
            pos += 8 + len + (len & 1);
        }
        if (channels != 1 || rate != SampleRateHz || bits != 16 || dataOff < 0 || dataLen / 2 != PcmSamples)
            throw new InvalidDataException($"WAV assertion failed (ch={channels} rate={rate} bits={bits} samples={dataLen / 2})");
        // Same input as the Stage 1 export (gap-locate/wavio.py load_cycle_pcm): int16 values as float, then RMS-normalised to the production target.
        var pcm = new float[PcmSamples];
        double sumSq = 0;
        for (int i = 0; i < PcmSamples; i++) { float v = BitConverter.ToInt16(b, dataOff + 2 * i); pcm[i] = v; sumSq += (double)v * v; }
        double rms = Math.Sqrt(sumSq / PcmSamples);
        if (rms >= SilenceRmsThreshold)
            for (int i = 0; i < PcmSamples; i++) pcm[i] = (float)(pcm[i] * (ProductionTargetRms / rms));
        return pcm;
    }
}
