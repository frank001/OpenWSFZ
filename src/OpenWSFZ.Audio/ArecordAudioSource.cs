using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.CompilerServices;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Linux audio capture source using <c>arecord</c>. Records FLOAT_LE PCM at
/// 12 000 Hz mono and converts stdout bytes to float samples via
/// <see cref="MemoryMarshal.Cast{TFrom,TTo}"/>.
/// </summary>
/// <remarks>
/// capture-loss-instrument: the child's stderr is drained on its own task from start to exit
/// (an undrained pipe fills and blocks <c>arecord</c>), and its <c>overrun</c> reports are
/// counted and logged.  That task never touches the stdout read loop, so the captured chunks
/// are unchanged.
/// </remarks>
internal sealed class ArecordAudioSource : IAudioSource, ICaptureLossCounters
{
    /// <summary>The first this-many non-overrun stderr lines are logged; after that, every <see cref="StderrLogEvery"/>th.</summary>
    private const int StderrLogFirst = 20;

    /// <summary>Rate limit for non-overrun stderr lines after the first <see cref="StderrLogFirst"/>.</summary>
    private const int StderrLogEvery = 100;

    /// <summary>Upper bound on waiting for the stderr reader at teardown (it ends when the child's pipe closes).</summary>
    private static readonly TimeSpan StderrDrainTimeout = TimeSpan.FromSeconds(2);

    private readonly Func<string, ProcessStartInfo> _startInfoFactory;
    private readonly ILogger<ArecordAudioSource>?   _logger;
    private readonly Func<DateTime>                 _utcNow;

    private long _overrunCount;
    private long _otherStderrLines;

    /// <summary>Production constructor — uses real <c>arecord</c>.</summary>
    public ArecordAudioSource()
        : this(DefaultStartInfo) { }

    /// <summary>Production constructor with a logger for the stderr reports.</summary>
    public ArecordAudioSource(ILogger<ArecordAudioSource>? logger)
        : this(DefaultStartInfo, logger) { }

    /// <summary>
    /// Test constructor — supply a custom <see cref="ProcessStartInfo"/> factory
    /// to redirect the subprocess to a test stub.
    /// </summary>
    internal ArecordAudioSource(
        Func<string, ProcessStartInfo> startInfoFactory,
        ILogger<ArecordAudioSource>?   logger = null,
        Func<DateTime>?                utcNow = null)
    {
        _startInfoFactory = startInfoFactory;
        _logger           = logger;
        _utcNow           = utcNow ?? (() => DateTime.UtcNow);
    }

    /// <inheritdoc/>
    public long CaptureOverrunCount => Interlocked.Read(ref _overrunCount);

    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [EnumeratorCancellation] CancellationToken ct)
    {
        using var process = new Process { StartInfo = _startInfoFactory(deviceId) };
        process.Start();

        // Drain stderr for the whole life of the child, independent of the stdout loop below.
        var stderrTask = Task.Run(() => DrainStderrAsync(process.StandardError));

        var    stdout   = process.StandardOutput.BaseStream;
        const int ChunkBytes = 2048 * sizeof(float);
        var    buf       = new byte[ChunkBytes];
        int    pos       = 0;

        try
        {
            while (!ct.IsCancellationRequested)
            {
                int read = await stdout.ReadAsync(buf.AsMemory(pos), ct);
                if (read == 0) break; // EOF

                pos += read;

                if (pos >= ChunkBytes)
                {
                    var chunk = new float[2048];
                    MemoryMarshal.Cast<byte, float>(buf.AsSpan(0, ChunkBytes)).CopyTo(chunk);
                    pos = 0;
                    yield return chunk;
                }
            }
        }
        finally
        {
            if (!process.HasExited)
            {
                try { process.Kill(); } catch { }
                await process.WaitForExitAsync(CancellationToken.None);
            }

            await AwaitStderrDrainAsync(stderrTask);
        }

        // Reached here only if the loop exited via EOF (not cancellation).
        await process.WaitForExitAsync(CancellationToken.None);

        if (process.ExitCode != 0)
            throw new AudioCaptureException(
                deviceId,
                $"arecord exited with code {process.ExitCode}");
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;

    // ── stderr ───────────────────────────────────────────────────────────────

    /// <summary>Reads <paramref name="stderr"/> line by line until EOF, counting and logging what it sees.</summary>
    private async Task DrainStderrAsync(StreamReader stderr)
    {
        try
        {
            while (await stderr.ReadLineAsync() is { } line)
                OnStderrLine(line, _utcNow());
        }
        catch (Exception ex)
        {
            // The pipe closing under us (child killed) is expected; anything else is worth a line.
            _logger?.LogDebug(ex, "arecord stderr reader ended with an exception.");
        }
    }

    private async Task AwaitStderrDrainAsync(Task stderrTask)
    {
        try
        {
            await stderrTask.WaitAsync(StderrDrainTimeout);
        }
        catch (TimeoutException)
        {
            _logger?.LogWarning("arecord stderr reader did not finish within {Seconds} s of the child exiting.",
                StderrDrainTimeout.TotalSeconds);
        }
        catch (Exception) { /* already reported inside the reader */ }
    }

    private void OnStderrLine(string line, DateTime receivedUtc)
    {
        if (line.Contains("overrun", StringComparison.OrdinalIgnoreCase))
        {
            // The "(at least N ms long)" figure is NOT parsed or summed: on sol it read 0.02-0.4 ms
            // even for 2 s and 3 s stalls, so it is not a lost duration. The line is logged verbatim.
            var count = Interlocked.Increment(ref _overrunCount);
            _logger?.LogWarning(
                "arecord overrun at {ReceivedUtc:HH:mm:ss.fff} UTC (overrun #{Count}): {Line}",
                receivedUtc, count, line);
            return;
        }

        var n = Interlocked.Increment(ref _otherStderrLines);
        if (n <= StderrLogFirst || n % StderrLogEvery == 0)
            _logger?.LogInformation("arecord stderr [{N}]: {Line}", n, line);
    }

    // ── Factory helpers ──────────────────────────────────────────────────────

    internal static ProcessStartInfo DefaultStartInfo(string deviceId)
    {
        var info = new ProcessStartInfo("arecord")
        {
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            UseShellExecute        = false,
        };
        // Pin the message text: the overrun parser matches alsa-utils' English wording.
        info.Environment["LC_ALL"] = "C";
        info.ArgumentList.Add("-D");    info.ArgumentList.Add(deviceId);
        info.ArgumentList.Add("-f");    info.ArgumentList.Add("FLOAT_LE");
        info.ArgumentList.Add("-r");    info.ArgumentList.Add("12000");
        info.ArgumentList.Add("-c");    info.ArgumentList.Add("1");
        info.ArgumentList.Add("-t");    info.ArgumentList.Add("raw");
        info.ArgumentList.Add("-");     // stdout
        return info;
    }

    /// <summary>
    /// Creates a cross-platform <see cref="ProcessStartInfo"/> that pipes the
    /// contents of <paramref name="filePath"/> to stdout and then exits 0.
    /// Used by tests to feed known PCM bytes without a real <c>arecord</c>.
    /// </summary>
    internal static ProcessStartInfo FilePipeStartInfo(string filePath)
    {
        if (OperatingSystem.IsWindows())
        {
            // PowerShell outputs the raw bytes of the file to stdout.
            var psi = new ProcessStartInfo("powershell.exe")
            {
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
            };
            // ReadAllBytes reads the entire file into memory and releases the file handle
            // before any bytes are written to stdout.  The original FileStream approach held
            // an exclusive Windows lock on the file for the duration of the pipe, causing
            // File.Delete to fail in the test finally block with "being used by another process"
            // (Windows kernel race: handle release is not instantaneous after process exit).
            var script = $"$out=[Console]::OpenStandardOutput();$b=[System.IO.File]::ReadAllBytes('{filePath}');$out.Write($b,0,$b.Length);$out.Flush()";
            var encoded = Convert.ToBase64String(System.Text.Encoding.Unicode.GetBytes(script));
            psi.ArgumentList.Add("-NoProfile");
            psi.ArgumentList.Add("-NonInteractive");
            psi.ArgumentList.Add("-EncodedCommand");
            psi.ArgumentList.Add(encoded);
            return psi;
        }
        else
        {
            var psi = new ProcessStartInfo("/bin/sh")
            {
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
            };
            psi.ArgumentList.Add("-c");
            psi.ArgumentList.Add($"cat '{filePath}'");
            return psi;
        }
    }

    /// <summary>
    /// Creates a cross-platform <see cref="ProcessStartInfo"/> for a process
    /// that exits immediately with a non-zero code.
    /// </summary>
    internal static ProcessStartInfo FailingStartInfo()
    {
        if (OperatingSystem.IsWindows())
        {
            var psi = new ProcessStartInfo("cmd.exe")
            {
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
            };
            psi.ArgumentList.Add("/c");
            psi.ArgumentList.Add("exit 1");
            return psi;
        }
        else
        {
            var psi = new ProcessStartInfo("/bin/sh")
            {
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
            };
            psi.ArgumentList.Add("-c");
            psi.ArgumentList.Add("exit 1");
            return psi;
        }
    }
}
