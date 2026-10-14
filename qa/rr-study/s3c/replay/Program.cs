// S3c separating replay harness (QA-owned, test-only, no src/ change).
// Architect ruling 2026-10-05 15:40Z section 4: replay battery 3's archived S3c cycles through the product's decode entry in
// three arms and score E -2.00 (and the other three parts) with the battery's own scorer.
//
// Per cycle, in ONE process, in list order (the daemon's order for a cycle):
//   --early on  : (build 766f9cc2 only) a zero-filled copy of the window holding exactly the first 156 000 samples (cut 2.0 s)
//                 is decoded through Ft8Decoder.DecodeEarlyAsync (save, pass 0 only, restore); its result is DISCARDED (panel only)
//   then        : the final decode of the whole window through DecodeTwoStageAsync with the subtraction flag ON (battery 3 ran
//                 flag ON; both batches are what ALL.TXT receives).
// Decoder settings = the battery's config: nhard 40, kMinScorePass2 10, osdCorrThreshold 0.10, threads default (0 = auto),
// flag ON. The process is FRESH per arm; the callsign hash table starts empty (the battery's daemon had run S1..S8 before S3c:
// a stated difference, not a defect; planted texts are standard-call Q-prefix messages).
//
// 🔒 HK-037 / NFR-021: decoded text is read only here, and a decode is WRITTEN only if its text is exactly one of the
// scenario's planted SYNTHETIC texts (the scorer's own rule); everything else is counted and dropped. Output is an
// ALL.TXT-format file of planted synthetic decodes (stamp, MHz, Rx, FT8, snr, dt, freq, text) plus a numeric counts CSV.
using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;

internal static class Program
{
    private const int PcmSamples = 180_000;
    private const int SampleRateHz = 12_000;
    private const int KMinScorePass2 = 10;
    private const float OsdCorrThreshold = 0.10f;
    private const int OsdNhardMax = 40;
    private const double EarlyCutSeconds = 2.0;
    private const string DialMhz = "7.074";

    private static int Main(string[] args)
    {
        try { return RunAsync(args).GetAwaiter().GetResult(); }
        catch (Exception ex) { Console.Error.WriteLine("FATAL " + ex.GetType().Name + " " + ex.Message); return 3; }
    }

    private static async Task<int> RunAsync(string[] args)
    {
        var a = ParseArgs(args);
        string wavDir = Req(a, "wav-dir"), scenario = Req(a, "scenario"), outAll = Req(a, "out-alltxt"), outCsv = Req(a, "out-counts");
        var stamps = Req(a, "stamps").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        string early = Req(a, "early");   // on | off | na
        if (early is not ("on" or "off" or "na")) throw new ArgumentException("--early on|off|na");
#if !HAS_EARLY
        if (early != "na") throw new InvalidOperationException("this build has no early decode: --early na");
#else
        if (early == "na") throw new InvalidOperationException("this build has early decode: --early on|off");
#endif

        var planted = new HashSet<string>(StringComparer.Ordinal);
        using (var doc = JsonDocument.Parse(File.ReadAllBytes(scenario)))
            foreach (var s in doc.RootElement.GetProperty("design").GetProperty("signals").EnumerateArray())
                planted.Add(s.GetProperty("text").GetString()!);
        if (planted.Count == 0) throw new InvalidOperationException("no planted texts");

        var decoder = new Ft8Decoder(new WallClock(), NullLogger<Ft8Decoder>.Instance);
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, OsdNhardMax);
        decoder.SetSubtractionEnabled(true);
        if (!decoder.SubtractionEnabled) throw new InvalidOperationException("flag is not ON");
        string dllStart = LoadedDllSha256();
        Console.WriteLine($"# s3c-replay early={early} flag=ON nhard={OsdNhardMax} kMin={KMinScorePass2} osd={OsdCorrThreshold} " +
                          $"shim={Ft8Decoder.LoadedShimVersion} dllSha256={dllStart} cycles={stamps.Length} planted={planted.Count}");

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outAll))!);
        await using var all = new StreamWriter(outAll, append: false, new UTF8Encoding(false)) { NewLine = "\n" };
        await using var csv = new StreamWriter(outCsv, append: false, new UTF8Encoding(false)) { NewLine = "\n" };
        csv.WriteLine("stamp,early_n,early_ms,b1_n,b1_planted,b2_n,b2_planted,final_ms,exc");

        foreach (string stamp in stamps)
        {
            var pcm = ReadWav(Path.Combine(wavDir, stamp + ".wav"));
            var cyc = StampToUtc(stamp);
            int en = 0; double ems = 0; string exc = "";
#if HAS_EARLY
            if (early == "on")
            {
                int n = PcmSamples - (int)Math.Round(SampleRateHz * EarlyCutSeconds);   // 156 000
                var cut = new float[PcmSamples];
                Array.Copy(pcm, cut, n);                                                 // tail stays exactly zero
                for (int i = n; i < PcmSamples; i++) if (cut[i] != 0f) throw new InvalidOperationException("cut tail not zero");
                for (int i = 0; i < n; i++) if (cut[i] != pcm[i]) throw new InvalidOperationException("cut head differs");
                var sw0 = Stopwatch.StartNew();
                try { en = (await decoder.DecodeEarlyAsync(cut, cyc, null)).Count; }
                catch (Exception ex) { exc += "E:" + ex.GetType().Name; }
                ems = sw0.Elapsed.TotalMilliseconds;
            }
#endif
            int b1n = -1, b1p = 0, b2n = -1, b2p = 0;
            var sw = Stopwatch.StartNew();
            try
            {
                IReadOnlyList<DecodeResult>? b1 = null;
                var b2 = await decoder.DecodeTwoStageAsync(pcm, cyc, null, batch => { b1 = batch; return Task.CompletedTask; });
                b1n = b1?.Count ?? -1; b2n = b2.Count;
                if (b1 is not null) b1p = Emit(all, stamp, b1, planted);
                b2p = Emit(all, stamp, b2, planted);
            }
            catch (Exception ex) { exc += "F:" + ex.GetType().Name; }
            sw.Stop();
            csv.WriteLine(string.Join(",", stamp, en, ems.ToString("F1", CultureInfo.InvariantCulture), b1n, b1p, b2n, b2p,
                sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture), exc));
        }
        string dllEnd = LoadedDllSha256();
        Console.WriteLine($"# s3c-replay end dllSha256={dllEnd} same={dllStart == dllEnd}");
        return dllStart == dllEnd ? 0 : 4;
    }

    /// <summary>Writes the decodes whose text is exactly a planted synthetic text; returns how many were written.</summary>
    private static int Emit(StreamWriter w, string stamp, IReadOnlyList<DecodeResult> list, HashSet<string> planted)
    {
        int n = 0;
        foreach (var r in list)
        {
            string text = r.Message.TrimEnd();
            if (!planted.Contains(text)) continue;
            w.WriteLine(string.Join(" ", stamp, DialMhz, "Rx", "FT8",
                r.Snr.ToString(CultureInfo.InvariantCulture), r.Dt.ToString("F1", CultureInfo.InvariantCulture),
                r.FreqHz.ToString(CultureInfo.InvariantCulture), text));
            n++;
        }
        return n;
    }

    private static string LoadedDllSha256()
    {
        foreach (ProcessModule mod in Process.GetCurrentProcess().Modules)
            if (mod.ModuleName.StartsWith("libft8", StringComparison.OrdinalIgnoreCase))
                return Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(mod.FileName))).ToLowerInvariant();
        return "NOT-LOADED";
    }

    private static float[] ReadWav(string path)
    {
        byte[] b = File.ReadAllBytes(path);
        if (b.Length < 44 || Encoding.ASCII.GetString(b, 0, 4) != "RIFF" || Encoding.ASCII.GetString(b, 8, 4) != "WAVE")
            throw new InvalidDataException("not a RIFF/WAVE file");
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
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++) pcm[i] = BitConverter.ToInt16(b, dataOff + 2 * i) / 32768f;
        return pcm;
    }

    private static DateTime StampToUtc(string stamp) =>
        DateTime.SpecifyKind(DateTime.ParseExact(stamp, "yyMMdd_HHmmss", CultureInfo.InvariantCulture), DateTimeKind.Utc);

    private static Dictionary<string, string> ParseArgs(string[] args)
    {
        var d = new Dictionary<string, string>();
        for (int i = 0; i + 1 < args.Length; i += 2)
        {
            if (!args[i].StartsWith("--")) throw new ArgumentException("bad arg");
            d[args[i][2..]] = args[i + 1];
        }
        return d;
    }

    private static string Req(Dictionary<string, string> a, string k) =>
        a.TryGetValue(k, out var v) ? v : throw new ArgumentException("missing --" + k);

    private sealed class WallClock : IClock { public DateTime UtcNow => DateTime.UtcNow; }
}
