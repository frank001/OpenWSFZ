using System.Diagnostics;
using System.Runtime.InteropServices;
using FluentAssertions;
using OpenWSFZ.Audio;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

/// <summary>
/// capture-loss-instrument: <c>ArecordAudioSource</c> must drain <c>arecord</c>'s stderr (an
/// undrained pipe fills and blocks the child), count overruns, and leave the yielded audio
/// byte-identical.  Fake processes are built from files so the tests need no real <c>arecord</c>.
/// </summary>
public sealed class ArecordStderrTests
{
    internal const int ChunkFloats = 2048;

    /// <summary>
    /// Builds a fake <c>arecord</c>: writes <paramref name="stderrFile"/> to stderr in full FIRST,
    /// then <paramref name="pcmFile"/> to stdout, then exits 0.  If nothing reads stderr and the
    /// file exceeds the pipe buffer, the child blocks before it ever writes stdout.
    /// </summary>
    internal static ProcessStartInfo StderrThenStdoutStartInfo(string pcmFile, string stderrFile)
    {
        ProcessStartInfo psi;
        if (OperatingSystem.IsWindows())
        {
            psi = new ProcessStartInfo("powershell.exe");
            var script =
                $"$e=[Console]::OpenStandardError();$s=[System.IO.File]::ReadAllBytes('{stderrFile}');" +
                "$e.Write($s,0,$s.Length);$e.Flush();" +
                $"$o=[Console]::OpenStandardOutput();$b=[System.IO.File]::ReadAllBytes('{pcmFile}');" +
                "$o.Write($b,0,$b.Length);$o.Flush()";
            psi.ArgumentList.Add("-NoProfile");
            psi.ArgumentList.Add("-NonInteractive");
            psi.ArgumentList.Add("-EncodedCommand");
            psi.ArgumentList.Add(Convert.ToBase64String(System.Text.Encoding.Unicode.GetBytes(script)));
        }
        else
        {
            psi = new ProcessStartInfo("/bin/sh");
            psi.ArgumentList.Add("-c");
            psi.ArgumentList.Add($"cat '{stderrFile}' >&2; cat '{pcmFile}'");
        }

        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError  = true;
        psi.UseShellExecute        = false;
        return psi;
    }

    /// <summary>Deterministic PCM: <paramref name="chunks"/> chunks of known float values.</summary>
    internal static byte[] MakePcm(int chunks)
    {
        var floats = new float[chunks * ChunkFloats];
        for (int i = 0; i < floats.Length; i++)
            floats[i] = (float)((i * 7) % 1000) / 1000f - 0.5f;
        var bytes = new byte[floats.Length * sizeof(float)];
        MemoryMarshal.AsBytes(floats.AsSpan()).CopyTo(bytes);
        return bytes;
    }

    /// <summary>Runs a fake arecord to completion and returns the yielded chunks plus the source.</summary>
    private static async Task<(List<float[]> Chunks, ArecordAudioSource Source, RecordingLogger<ArecordAudioSource> Log)>
        RunAsync(byte[] pcm, byte[] stderr, Func<DateTime>? utcNow = null)
    {
        var pcmFile = Path.GetTempFileName();
        var errFile = Path.GetTempFileName();
        try
        {
            await File.WriteAllBytesAsync(pcmFile, pcm);
            await File.WriteAllBytesAsync(errFile, stderr);
            var log    = new RecordingLogger<ArecordAudioSource>();
            var source = new ArecordAudioSource(
                _ => StderrThenStdoutStartInfo(pcmFile, errFile), log, utcNow);

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(60));
            var chunks = new List<float[]>();
            await foreach (var chunk in source.CaptureAsync("test-device", cts.Token))
                chunks.Add(chunk);
            return (chunks, source, log);
        }
        finally
        {
            File.Delete(pcmFile);
            File.Delete(errFile);
        }
    }

    private static byte[] Lines(params string[] lines) =>
        System.Text.Encoding.ASCII.GetBytes(string.Concat(lines.Select(l => l + "\n")));

    private static byte[] Flatten(IEnumerable<float[]> chunks)
    {
        using var ms = new MemoryStream();
        foreach (var c in chunks)
            ms.Write(MemoryMarshal.AsBytes(c.AsSpan()));
        return ms.ToArray();
    }

    // capture-loss-instrument 1.1 — overruns are counted and logged with their own UTC time.
    [Fact(DisplayName = "capture-loss 1.1: overrun lines are counted and logged at Warning with a UTC millisecond time")]
    public async Task Overruns_AreCounted_AndLoggedWithUtcMillisecondTime()
    {
        var stamp = new DateTime(2026, 10, 17, 12, 34, 56, 789, DateTimeKind.Utc);
        var (_, source, log) = await RunAsync(
            MakePcm(2),
            Lines("overrun!!! (at least 10.5 ms long)", "overrun!!! (at least 20.5 ms long)"),
            () => stamp);

        source.CaptureOverrunCount.Should().Be(2);

        var warnings = log.Entries.Where(e => e.Level == Microsoft.Extensions.Logging.LogLevel.Warning).ToList();
        warnings.Should().HaveCount(2);
        warnings.Should().OnlyContain(w => w.Message.Contains("12:34:56.789"),
            "the message carries its own UTC receive time to the millisecond (log-sink stamps are whole seconds)");
        warnings[0].Message.Should().Contain("overrun!!! (at least 10.5 ms long)", "arecord's own line is logged verbatim");
        warnings[1].Message.Should().Contain("overrun!!! (at least 20.5 ms long)");
    }

    // capture-loss-instrument 1.2 — byte identity.
    [Fact(DisplayName = "capture-loss 1.2: yielded chunks are byte-identical with and without stderr noise")]
    public async Task Chunks_AreByteIdentical_WithAndWithoutStderrNoise()
    {
        // 5 whole chunks plus a partial tail that is never yielded.
        var pcm = MakePcm(5).Concat(new byte[100]).ToArray();

        var (quiet, _, _) = await RunAsync(pcm, Array.Empty<byte>());

        var noise = Lines(
            "Recording raw data 'stdin' : Float 32 bit Little Endian, Rate 12000 Hz, Mono",
            "overrun!!! (at least 3.2 ms long)",
            "OVERRUN",
            "something else entirely");
        var (noisy, _, _) = await RunAsync(pcm, noise);

        quiet.Should().HaveCount(5);
        noisy.Should().HaveCount(quiet.Count);
        Flatten(noisy).Should().Equal(Flatten(quiet),
            "stderr handling must not alter a single captured byte");
        Flatten(noisy).Should().Equal(pcm.Take(5 * ChunkFloats * sizeof(float)).ToArray());
    }

    // capture-loss-instrument 1.4 — rate-limited non-overrun lines; case-insensitive; unparsable length.
    [Fact(DisplayName = "capture-loss 1.4: other stderr lines log at Information (first 20, then every 100th) and are not overruns")]
    public async Task OtherStderrLines_AreRateLimited_AndNotCountedAsOverruns()
    {
        var header = Enumerable.Range(1, 130).Select(i => $"Recording header line {i}").ToArray();
        var (_, source, log) = await RunAsync(MakePcm(1), Lines(header));

        source.CaptureOverrunCount.Should().Be(0);
        var info = log.Entries
            .Where(e => e.Level == Microsoft.Extensions.Logging.LogLevel.Information
                     && e.Message.Contains("Recording header line"))
            .Select(e => e.Message).ToList();
        info.Should().HaveCount(21, "lines 1-20, then line 100");
        info.Last().Should().Contain("Recording header line 100");
    }

    [Fact(DisplayName = "capture-loss 1.4: a mixed-case OVERRUN counts, with or without a length in the line")]
    public async Task MixedCaseOverrun_Counts_WithOrWithoutLength()
    {
        var (_, source, _) = await RunAsync(MakePcm(1), Lines("OVERRUN!!! (at least 7 ms long)", "Overrun!!!"));

        source.CaptureOverrunCount.Should().Be(2);
    }

    // capture-loss-instrument 1.5 — how arecord is started.
    [Fact(DisplayName = "capture-loss 1.5: arecord is started with LC_ALL=C and unchanged arguments")]
    public void DefaultStartInfo_SetsLcAllC_AndKeepsArguments()
    {
        var info = ArecordAudioSource.DefaultStartInfo("hw:1,0");

        info.FileName.Should().Be("arecord");
        info.ArgumentList.Should().Equal(
            "-D", "hw:1,0", "-f", "FLOAT_LE", "-r", "12000", "-c", "1", "-t", "raw", "--period-time=20000", "-");
        info.Environment["LC_ALL"].Should().Be("C");
        info.RedirectStandardOutput.Should().BeTrue();
        info.RedirectStandardError.Should().BeTrue();
    }

    // capture-loss-instrument 1.3 — pipe-fill regression.
    [Fact(DisplayName = "capture-loss 1.3: ArecordAudioSource completes when stderr exceeds the pipe buffer before stdout is written")]
    public async Task CaptureAsync_Completes_WhenStderrFillsThePipeBeforeStdout()
    {
        const int Chunks = 4;
        var pcm     = MakePcm(Chunks);
        var pcmFile = Path.GetTempFileName();
        var errFile = Path.GetTempFileName();
        try
        {
            await File.WriteAllBytesAsync(pcmFile, pcm);
            // 384 KiB of stderr, well beyond any pipe buffer (Linux 64 KiB, Windows far less),
            // written before a single stdout byte.
            var noise = new byte[384 * 1024];
            for (int i = 0; i < noise.Length; i++)
                noise[i] = (byte)(i % 26 == 25 ? '\n' : 'a' + (i % 26));
            await File.WriteAllBytesAsync(errFile, noise);

            var source = new ArecordAudioSource(_ => StderrThenStdoutStartInfo(pcmFile, errFile));

            // A generous bound: the fake needs well under 10 s even on a slow CI box.  On a
            // build that never reads stderr the child blocks and this bound is what ends the test.
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(60));
            var chunks = new List<float[]>();
            await foreach (var chunk in source.CaptureAsync("test-device", cts.Token))
                chunks.Add(chunk);

            chunks.Should().HaveCount(Chunks,
                "all PCM written after the stderr burst must still be delivered; a stderr pipe " +
                "nobody drains blocks the child before it writes stdout");
        }
        finally
        {
            File.Delete(pcmFile);
            File.Delete(errFile);
        }
    }
}
