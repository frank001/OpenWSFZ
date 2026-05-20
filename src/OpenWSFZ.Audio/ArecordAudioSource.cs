using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.CompilerServices;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Linux audio capture source using <c>arecord</c>. Records FLOAT_LE PCM at
/// 12 000 Hz mono and converts stdout bytes to float samples via
/// <see cref="MemoryMarshal.Cast{TFrom,TTo}"/>.
/// </summary>
internal sealed class ArecordAudioSource : IAudioSource
{
    private readonly Func<string, ProcessStartInfo> _startInfoFactory;

    /// <summary>Production constructor — uses real <c>arecord</c>.</summary>
    public ArecordAudioSource()
        : this(DefaultStartInfo) { }

    /// <summary>
    /// Test constructor — supply a custom <see cref="ProcessStartInfo"/> factory
    /// to redirect the subprocess to a test stub.
    /// </summary>
    internal ArecordAudioSource(Func<string, ProcessStartInfo> startInfoFactory)
    {
        _startInfoFactory = startInfoFactory;
    }

    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [EnumeratorCancellation] CancellationToken ct)
    {
        using var process = new Process { StartInfo = _startInfoFactory(deviceId) };
        process.Start();

        var    stdout    = process.StandardOutput.BaseStream;
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
        }

        // Reached here only if the loop exited via EOF (not cancellation).
        await process.WaitForExitAsync(CancellationToken.None);

        if (process.ExitCode != 0)
            throw new AudioCaptureException(
                deviceId,
                $"arecord exited with code {process.ExitCode}");
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;

    // ── Factory helpers ──────────────────────────────────────────────────────

    private static ProcessStartInfo DefaultStartInfo(string deviceId)
    {
        var info = new ProcessStartInfo("arecord")
        {
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            UseShellExecute        = false,
        };
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
            // Use -EncodedCommand so we don't fight quoting.
            var script = $"$f=New-Object IO.FileStream('{filePath}',[IO.FileMode]::Open);$o=[Console]::OpenStandardOutput();$f.CopyTo($o)";
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
