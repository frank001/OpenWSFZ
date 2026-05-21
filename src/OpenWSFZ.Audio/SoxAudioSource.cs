using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// macOS audio capture source using <c>sox</c> (install via <c>brew install sox</c>).
/// Pipes raw FLOAT_LE PCM at 12 000 Hz mono from a CoreAudio device.
/// </summary>
internal sealed class SoxAudioSource : IAudioSource
{
    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [EnumeratorCancellation] CancellationToken ct)
    {
        // sox -t coreaudio "<deviceId>" -t raw -e float -b 32 -r 12000 -c 1 -
        var startInfo = new ProcessStartInfo("sox")
        {
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            UseShellExecute        = false,
        };
        startInfo.ArgumentList.Add("-t");    startInfo.ArgumentList.Add("coreaudio");
        startInfo.ArgumentList.Add(deviceId);
        startInfo.ArgumentList.Add("-t");    startInfo.ArgumentList.Add("raw");
        startInfo.ArgumentList.Add("-e");    startInfo.ArgumentList.Add("float");
        startInfo.ArgumentList.Add("-b");    startInfo.ArgumentList.Add("32");
        startInfo.ArgumentList.Add("-r");    startInfo.ArgumentList.Add("12000");
        startInfo.ArgumentList.Add("-c");    startInfo.ArgumentList.Add("1");
        startInfo.ArgumentList.Add("-");     // stdout

        // Start the process before the yield-containing try block so that
        // a startup exception (sox not installed) can be surfaced immediately.
        Process process;
        try
        {
            process = new Process { StartInfo = startInfo };
            process.Start();
        }
        catch
        {
            throw new AudioCaptureException(
                deviceId,
                "sox is not installed — run: brew install sox");
        }

        var    stdout    = process.StandardOutput.BaseStream;
        const int ChunkBytes = 2048 * sizeof(float);
        var    buf       = new byte[ChunkBytes];
        int    pos       = 0;
        int    exitCode  = 0;
        bool   eofExit   = false;

        try
        {
            while (!ct.IsCancellationRequested)
            {
                int read = await stdout.ReadAsync(buf.AsMemory(pos), ct);
                if (read == 0) { eofExit = true; break; }

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
            exitCode = process.ExitCode;
            process.Dispose();
        }

        // Reached here only when the loop exited via EOF (not cancellation).
        if (eofExit && exitCode != 0)
            throw new AudioCaptureException(
                deviceId,
                $"sox exited with code {exitCode}");
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
