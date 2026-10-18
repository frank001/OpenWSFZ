using System.IO.Pipes;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Audio;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

/// <summary>
/// capture-pipe-headroom: <c>ArecordAudioSource</c> asks the OS for a 1 MiB stdout pipe right after
/// the child starts (Linux), logs the outcome, never fails because of it, and never changes the
/// captured bytes.  The syscall sits behind <see cref="PipeResizer"/>, so the accepted and refused
/// paths run on every platform.
/// </summary>
public sealed class ArecordPipeHeadroomTests
{
    private const int Requested = 1_048_576;
    private const int ChunkBytes = ArecordStderrTests.ChunkFloats * sizeof(float);

    private static async Task<(byte[] Bytes, RecordingLogger<ArecordAudioSource> Log)> RunAsync(
        byte[] pcm, PipeResizer? resizer)
    {
        var pcmFile = Path.GetTempFileName();
        try
        {
            await File.WriteAllBytesAsync(pcmFile, pcm);
            var log    = new RecordingLogger<ArecordAudioSource>();
            var source = new ArecordAudioSource(
                _ => ArecordAudioSource.FilePipeStartInfo(pcmFile), log, pipeResizer: resizer);

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(60));
            using var ms  = new MemoryStream();
            await foreach (var chunk in source.CaptureAsync("test-device", cts.Token))
                ms.Write(System.Runtime.InteropServices.MemoryMarshal.AsBytes(chunk.AsSpan()));
            return (ms.ToArray(), log);
        }
        finally { File.Delete(pcmFile); }
    }

    private static List<string> Messages(RecordingLogger<ArecordAudioSource> log, LogLevel level) =>
        log.Entries.Where(e => e.Level == level).Select(e => e.Message).ToList();

    // 1.2 — refused: Warning with the errno, capture completes, bytes identical to an accepting run.
    [Fact(DisplayName = "pipe-headroom 1.2: a refusing seam logs a Warning with the errno and the chunks are byte-identical to an accepting run")]
    public async Task RefusedResize_WarnsWithErrno_AndChunksAreByteIdentical()
    {
        var pcm = ArecordStderrTests.MakePcm(5);

        var (accepted, _)        = await RunAsync(pcm, (_, _) => new PipeResizeResult(Requested, 0));
        var (refused, refusedLog) = await RunAsync(pcm, (_, _) => new PipeResizeResult(0, 1 /* EPERM */));

        var warnings = Messages(refusedLog, LogLevel.Warning);
        warnings.Should().ContainSingle(w => w.Contains("errno 1"));
        Messages(refusedLog, LogLevel.Information).Should().NotContain(m => m.Contains("enlarged"));
        refused.Length.Should().Be(5 * ChunkBytes);
        refused.Should().Equal(accepted, "a refused pipe resize must not alter a single captured byte");
        refused.Should().Equal(pcm);
    }

    [Fact(DisplayName = "pipe-headroom 1.2: a throwing seam (missing libc) is a Warning, not a failure")]
    public async Task ThrowingResize_IsWarning_NotFatal()
    {
        var pcm = ArecordStderrTests.MakePcm(2);

        var (bytes, log) = await RunAsync(pcm, (_, _) => throw new DllNotFoundException("libc"));

        Messages(log, LogLevel.Warning).Should().ContainSingle(w => w.Contains("could not enlarge"));
        bytes.Should().Equal(pcm);
    }

    // 1.3 — accepted: one Information line with both sizes, no Warning.
    [Fact(DisplayName = "pipe-headroom 1.3: an accepting seam logs requested and granted sizes once, with no Warning")]
    public async Task AcceptedResize_LogsRequestedAndGranted_Once()
    {
        int calls = 0, requestedSeen = 0;
        var (bytes, log) = await RunAsync(ArecordStderrTests.MakePcm(2), (_, req) =>
        {
            calls++; requestedSeen = req;
            return new PipeResizeResult(2_097_152, 0);
        });

        calls.Should().Be(1);
        requestedSeen.Should().Be(Requested);
        var info = Messages(log, LogLevel.Information).Where(m => m.Contains("enlarged")).ToList();
        info.Should().ContainSingle();
        info[0].Should().Contain("1048576").And.Contain("2097152");
        Messages(log, LogLevel.Warning).Should().BeEmpty();
        bytes.Length.Should().Be(2 * ChunkBytes);
    }

    [Fact(DisplayName = "pipe-headroom: with no resizer (other platforms, existing tests) nothing is attempted or logged")]
    public async Task NoResizer_NothingAttempted()
    {
        var (bytes, log) = await RunAsync(ArecordStderrTests.MakePcm(1), resizer: null);

        log.Entries.Should().NotContain(e => e.Message.Contains("pipe"));
        bytes.Length.Should().Be(ChunkBytes);
    }

    // The finding the design asked to confirm: on Unix a redirected child's stdout is an anonymous pipe.
    [Fact(DisplayName = "pipe-headroom: a redirected child's stdout BaseStream is an AnonymousPipeClientStream on Unix")]
    public async Task ChildStdout_IsAnAnonymousPipeClientStream_OnUnix()
    {
        if (OperatingSystem.IsWindows()) return; // Windows hands back a FileStream; the resize is Linux-only

        var pcmFile = Path.GetTempFileName();
        try
        {
            await File.WriteAllBytesAsync(pcmFile, ArecordStderrTests.MakePcm(1));
            Type? seen = null;
            var source = new ArecordAudioSource(
                _ => ArecordAudioSource.FilePipeStartInfo(pcmFile),
                pipeResizer: (s, _) => { seen = s.GetType(); return new PipeResizeResult(Requested, 0); });

            await foreach (var _ in source.CaptureAsync("d", CancellationToken.None)) { }

            seen.Should().Be(typeof(AnonymousPipeClientStream));
        }
        finally { File.Delete(pcmFile); }
    }

    // 1.5 - not a pipe: the syscall is not attempted (libc is not even loaded: this runs on Windows too).
    [Fact(DisplayName = "pipe-headroom 1.5: a stream that is not a pipe is not resized; a Warning is logged")]
    public void NonPipeStream_IsNotAttempted_AndWarns()
    {
        var log = new RecordingLogger<ArecordAudioSource>();

        var direct = LibcPipeResizer.Resize(new MemoryStream(), StdoutPipeEnlarger.RequestedBytes);
        direct.NotAttempted.Should().Contain("not a pipe");
        direct.GrantedBytes.Should().Be(0);

        StdoutPipeEnlarger.Apply(new MemoryStream(), LibcPipeResizer.Resize, log);
        Messages(log, LogLevel.Warning).Should().ContainSingle(w => w.Contains("not a pipe") && w.Contains("not attempted"));
        Messages(log, LogLevel.Information).Should().BeEmpty();
    }

    // 1.4 — real pipe, real P/Invoke, Linux only.
    [Fact(DisplayName = "pipe-headroom 1.4: real pipe on Linux - granted >= 1 MiB or a Warning (never a hang)")]
    public async Task RealPipe_Linux_GrantsAtLeastRequest_OrWarns()
    {
        if (!OperatingSystem.IsLinux()) return; // Linux-only: fcntl(F_SETPIPE_SZ)

        var pcm = ArecordStderrTests.MakePcm(3);
        var (bytes, log) = await RunAsync(pcm, LibcPipeResizer.Resize);

        bytes.Should().Equal(pcm);
        var granted = Messages(log, LogLevel.Information).Where(m => m.Contains("enlarged")).ToList();
        var warned  = Messages(log, LogLevel.Warning).Where(m => m.Contains("could not enlarge")).ToList();
        (granted.Count + warned.Count).Should().Be(1, "exactly one outcome is logged");
        // Where the system allows 1 MiB the request must be granted (the Warning branch is for a
        // lower /proc/sys/fs/pipe-max-size, or an unreadable one, where it is accepted).
        if (long.TryParse(File.ReadAllText("/proc/sys/fs/pipe-max-size").Trim(), out var max) && max >= Requested)
            granted.Should().ContainSingle("pipe-max-size permits 1 MiB, so the real call must succeed");
        if (granted.Count == 1)
            granted[0].Should().MatchRegex(@"granted \d{7,} bytes");
    }
}
