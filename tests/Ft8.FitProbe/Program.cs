using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;

// Ft8.FitProbe: TEST-ONLY tool for the sub-feas-speed-redesign change (tasks §2 and §3).
//
//   Ft8.FitProbe e1   --dll <libft8.dll> --out <csv> [--wav <file>]... [--grid <n>] [--threads <t>] [--seed <s>]
//   Ft8.FitProbe time --dll <libft8.dll> --wav <file> [--threads <t>]
//   Ft8.FitProbe fitprofile|fitsummary|fitcompare ...   Stage B step-1 per-phase fit profile; see FitProfile.cs
//   Ft8.FitProbe fitparams|fitparamscompare ...         Stage B E2: fitted parameters per signal, two DLLs; see FitProfile.cs
//
// e1   Hash probe (E1). Pass-0 decodes each cycle THROUGH the given DLL, encodes each re-encodable decode, fits it
//      with NO deadline, and writes one CSV row per (label, signal): rc and sha256(out_shat), plus per-cycle rows
//      for the analytic signal and the pass-0 outcome. "--grid n" adds n pseudo-random (tones, dt, freq) fits against
//      the first cycle (or a deterministic noise cycle), covering the edge cases (-3 near a buffer edge).
// time Wall-clock of one compute_analytic call, each single-threaded fit, and one residual DecodeAll.
//
// NOTE: this tool is built against the CURRENT interop, so it loads a libft8.dll of the CURRENT shim version.
// The golden CSV was recorded from the base DLL (shim 20260055) with the tool as of commit 348e067e; to compare
// a candidate DLL against it, run this tool with --dll <candidate> and diff (line endings normalised).
//
// 🔒 NFR-021 / HK-037: output is rc values, counts, hashes and milliseconds ONLY. Never message text, callsigns
// or exception message text. The DLL under test is copied over libft8.dll next to this tool BEFORE the first native
// call, so the same tool binary can be pointed at two DLLs.

return Probe.Run(args);

internal static class Probe
{
    private const int PcmLen = 180_000;
    private const int NumSymbols = 79;
    private const float TargetRms = 0.20f;

    public static int Run(string[] args)
    {
        if (args.Length == 0) return Usage();
        string mode = args[0];
        // Stage B step-1 fit profile (sub-feas-speed-redesign tasks.md 15.1): its own modes and arguments.
        if (mode is "fitprofile" or "fitsummary" or "fitcompare" or "fitparams" or "fitparamscompare") return FitProfile.Run(args);
        string? dll = null, outPath = null;
        var wavs = new List<string>();
        int grid = 0, threads = 1, seed = 20260930;
        for (int i = 1; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--dll": dll = args[++i]; break;
                case "--out": outPath = args[++i]; break;
                case "--wav": wavs.Add(args[++i]); break;
                case "--grid": grid = int.Parse(args[++i]); break;
                case "--threads": threads = int.Parse(args[++i]); break;
                case "--seed": seed = int.Parse(args[++i]); break;
                default: return Usage();
            }
        }
        if (dll is null) return Usage();

        // Point the interop at the DLL under test: it loads libft8.dll from AppContext.BaseDirectory.
        string target = Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        File.Copy(dll, target, overwrite: true);
        Console.Error.WriteLine($"dll under test sha256={Hex(SHA256.HashData(File.ReadAllBytes(target)))}");

        return mode switch
        {
            "e1" => RunE1(wavs, grid, threads, seed, outPath),
            "time" => RunTime(wavs, threads),
            _ => Usage(),
        };
    }

    private static int Usage()
    {
        Console.Error.WriteLine("usage: Ft8.FitProbe e1|time --dll <libft8.dll> [--out csv] [--wav f]... [--grid n] [--threads t] [--seed s]");
        return 2;
    }

    // ── E1 ───────────────────────────────────────────────────────────────

    private static int RunE1(List<string> wavs, int grid, int threads, int seed, string? outPath)
    {
        var interop = new Ft8NativeInteropAdapter();
        var rows = new List<string> { "kind,label,idx,rc,sha256,pass0_count,pass0_outcome_sha256" };

        float[]? firstNorm = null;
        foreach (string wav in wavs)
        {
            float[] raw = ReadWav(wav);
            float[] norm = Ft8Decoder.NormalisePcm(raw, TargetRms);
            firstNorm ??= norm;
            string label = Path.GetFileName(wav);

            Ft8NativeResult[] pass0 = interop.DecodeAll(norm);
            string outcome = OutcomeHash(pass0);

            (float[] re, float[] im) = interop.SubfeasComputeAnalytic(norm);
            rows.Add($"analytic,{label},-1,0,{HashFloats(re, im)},{pass0.Length},{outcome}");

            var jobs = new List<(byte[] Tones, float Dt, float Freq)>();
            foreach (var nr in pass0)
            {
                string msg = nr.Message.TrimEnd();
                if (!IsReencodable(msg)) continue;
                try { jobs.Add((interop.EncodeMessage(msg), nr.Dt, nr.FreqHz)); }
                catch (InvalidOperationException) { }
            }
            rows.AddRange(FitAll("fit", label, jobs, re, im, threads, interop, pass0.Length, outcome));
        }

        if (grid > 0)
        {
            firstNorm ??= NoiseCycle(seed);
            (float[] re, float[] im) = interop.SubfeasComputeAnalytic(firstNorm);
            var rng = new Random(seed);
            var jobs = new List<(byte[] Tones, float Dt, float Freq)>();
            for (int g = 0; g < grid; g++)
            {
                var tones = new byte[NumSymbols];
                for (int s = 0; s < NumSymbols; s++) tones[s] = (byte)rng.Next(8);
                // dt spans the interior AND both buffer edges, so some fits return -3.
                float dt = (float)(rng.NextDouble() * 4.6 - 1.4);
                float freq = (float)(rng.NextDouble() * 2800 + 200);
                jobs.Add((tones, dt, freq));
            }
            rows.AddRange(FitAll("grid", $"grid-{seed}", jobs, re, im, threads, interop, 0, "-"));
        }

        string csv = string.Join('\n', rows) + "\n";
        if (outPath is not null) File.WriteAllText(outPath, csv); else Console.Write(csv);
        Console.Error.WriteLine($"rows={rows.Count - 1}");
        return 0;
    }

    private static List<string> FitAll(
        string kind, string label, List<(byte[] Tones, float Dt, float Freq)> jobs,
        float[] re, float[] im, int threads, Ft8NativeInteropAdapter interop, int p0count, string p0hash)
    {
        var lines = new string[jobs.Count];
        interop.SubfeasPoolConfigure(Math.Max(1, threads)); // size the native workspace pool to the parallelism
        Parallel.For(0, jobs.Count, new ParallelOptions { MaxDegreeOfParallelism = Math.Max(1, threads) }, i =>
        {
            var j = jobs[i];
            string rc, hash;
            try
            {
                (int r, float[] shat) = interop.SubfeasFitSignal(re, im, j.Tones, j.Dt, j.Freq, IntPtr.Zero);
                rc = r.ToString();
                hash = HashFloats(shat);
            }
            catch (Exception ex)
            {
                // Type name only (HK-037): never the message text.
                rc = "EX:" + ex.GetType().Name;
                hash = "-";
            }
            lines[i] = $"{kind},{label},{i},{rc},{hash},{p0count},{p0hash}";
        });
        return lines.ToList();
    }

    // ── time ─────────────────────────────────────────────────────────────

    private static int RunTime(List<string> wavs, int threads)
    {
        var interop = new Ft8NativeInteropAdapter();
        foreach (string wav in wavs)
        {
            string label = Path.GetFileName(wav);
            float[] norm = Ft8Decoder.NormalisePcm(ReadWav(wav), TargetRms);

            var sw = Stopwatch.StartNew();
            Ft8NativeResult[] pass0 = interop.DecodeAll(norm);
            long p0ms = sw.ElapsedMilliseconds;

            sw.Restart();
            (float[] re, float[] im) = interop.SubfeasComputeAnalytic(norm);
            long anaMs = sw.ElapsedMilliseconds;

            var jobs = new List<(byte[] Tones, float Dt, float Freq)>();
            foreach (var nr in pass0)
            {
                string msg = nr.Message.TrimEnd();
                if (!IsReencodable(msg)) continue;
                try { jobs.Add((interop.EncodeMessage(msg), nr.Dt, nr.FreqHz)); }
                catch (InvalidOperationException) { }
            }

            interop.SubfeasPoolConfigure(Math.Max(1, threads));
            var fitMs = new long[jobs.Count];
            var shats = new float[jobs.Count][];
            var wall = Stopwatch.StartNew();
            Parallel.For(0, jobs.Count, new ParallelOptions { MaxDegreeOfParallelism = Math.Max(1, threads) }, i =>
            {
                var t = Stopwatch.StartNew();
                shats[i] = interop.SubfeasFitSignal(re, im, jobs[i].Tones, jobs[i].Dt, jobs[i].Freq, IntPtr.Zero).Shat;
                fitMs[i] = t.ElapsedMilliseconds;
            });
            long fitsWall = wall.ElapsedMilliseconds;

            float[] residual = (float[])norm.Clone();
            foreach (float[] s in shats) for (int k = 0; k < PcmLen; k++) residual[k] -= s[k];
            sw.Restart();
            Ft8NativeResult[] res = interop.DecodeAll(residual);
            long resMs = sw.ElapsedMilliseconds;

            Console.WriteLine(
                $"label={label} threads={threads} pass0Ms={p0ms} pass0Decodes={pass0.Length} analyticMs={anaMs} " +
                $"signals={jobs.Count} fitMsPerSignal=[{string.Join(',', fitMs)}] fitsWallMs={fitsWall} " +
                $"residualDecodeMs={resMs} residualDecodes={res.Length}");
        }
        return 0;
    }

    // ── helpers ──────────────────────────────────────────────────────────

    /// <summary>SubtractionPass.IsReencodable, restated: no hash placeholder and at least 3 tokens.</summary>
    internal static bool IsReencodable(string msg)
    {
        if (msg.Contains('<')) return false;
        int tokens = 0; bool inToken = false;
        foreach (char c in msg)
        {
            if (c == ' ') inToken = false;
            else if (!inToken) { inToken = true; tokens++; }
        }
        return tokens >= 3;
    }

    /// <summary>Hash of the pass-0 outcome NUMBERS (count, freq, dt, snr): never message text.</summary>
    private static string OutcomeHash(Ft8NativeResult[] r)
    {
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write(r.Length);
        foreach (var x in r) { w.Write(x.FreqHz); w.Write(x.Dt); w.Write(x.Snr); }
        w.Flush();
        return Hex(SHA256.HashData(ms.ToArray())).Substring(0, 16);
    }

    internal static string HashFloats(params float[][] arrays)
    {
        using var h = SHA256.Create();
        foreach (float[] a in arrays)
        {
            var bytes = new byte[a.Length * sizeof(float)];
            Buffer.BlockCopy(a, 0, bytes, 0, bytes.Length);
            h.TransformBlock(bytes, 0, bytes.Length, null, 0);
        }
        h.TransformFinalBlock([], 0, 0);
        return Hex(h.Hash!);
    }

    internal static string Hex(byte[] b) => Convert.ToHexString(b).ToLowerInvariant();

    /// <summary>Deterministic white-noise cycle (seeded LCG), RMS-normalised: the grid's fallback input.</summary>
    private static float[] NoiseCycle(int seed)
    {
        var rng = new Random(seed);
        var pcm = new float[PcmLen];
        for (int i = 0; i < PcmLen; i++) pcm[i] = (float)(rng.NextDouble() * 2 - 1);
        return Ft8Decoder.NormalisePcm(pcm, TargetRms);
    }

    /// <summary>12 kHz mono WAV (int16 or float32) to float[]; asserts exactly 180 000 samples.</summary>
    internal static float[] ReadWav(string path)
    {
        byte[] d = File.ReadAllBytes(path);
        if (d.Length < 44 || Encoding.ASCII.GetString(d, 0, 4) != "RIFF") throw new InvalidDataException("not a RIFF file");
        int pos = 12; int fmt = 0, ch = 0, rate = 0, bits = 0; int dataOff = -1, dataLen = 0;
        while (pos + 8 <= d.Length)
        {
            string id = Encoding.ASCII.GetString(d, pos, 4);
            int len = BitConverter.ToInt32(d, pos + 4);
            if (id == "fmt ")
            {
                fmt = BitConverter.ToUInt16(d, pos + 8);
                ch = BitConverter.ToUInt16(d, pos + 10);
                rate = BitConverter.ToInt32(d, pos + 12);
                bits = BitConverter.ToUInt16(d, pos + 22);
            }
            else if (id == "data") { dataOff = pos + 8; dataLen = Math.Min(len, d.Length - dataOff); break; }
            pos += 8 + len + (len & 1);
        }
        if (dataOff < 0 || ch != 1 || rate != 12_000) throw new InvalidDataException("expected 12 kHz mono");
        float[] pcm;
        if (fmt == 3 && bits == 32)
        {
            pcm = new float[dataLen / 4];
            Buffer.BlockCopy(d, dataOff, pcm, 0, pcm.Length * 4);
        }
        else if (fmt == 1 && bits == 16)
        {
            pcm = new float[dataLen / 2];
            for (int i = 0; i < pcm.Length; i++) pcm[i] = BitConverter.ToInt16(d, dataOff + i * 2) / 32768f;
        }
        else throw new InvalidDataException("unsupported WAV sample format");
        if (pcm.Length != PcmLen) throw new InvalidDataException($"expected {PcmLen} samples, got {pcm.Length}");
        return pcm;
    }
}
