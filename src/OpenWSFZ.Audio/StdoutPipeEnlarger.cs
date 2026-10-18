using System.IO.Pipes;
using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;
using Microsoft.Win32.SafeHandles;

namespace OpenWSFZ.Audio;

/// <summary>Outcome of one pipe-resize attempt (capture-pipe-headroom).</summary>
/// <param name="GrantedBytes">The pipe capacity read back after the request; 0 when the attempt failed.</param>
/// <param name="Errno">The errno of the failing call; 0 when the attempt succeeded.</param>
/// <param name="NotAttempted">Why no syscall was made (for example the stream is not a pipe); null when one was.</param>
internal readonly record struct PipeResizeResult(int GrantedBytes, int Errno, string? NotAttempted = null);

/// <summary>
/// The syscall seam: asks the OS to give the pipe behind <paramref name="stdout"/> a capacity of
/// <paramref name="requestedBytes"/>.  Injected through <c>ArecordAudioSource</c>'s test constructor.
/// </summary>
internal delegate PipeResizeResult PipeResizer(Stream stdout, int requestedBytes);

/// <summary>
/// Linux <c>fcntl(F_SETPIPE_SZ)</c> / <c>fcntl(F_GETPIPE_SZ)</c> through libc
/// (capture-pipe-headroom).  On Unix, .NET exposes a redirected child's stdout as an
/// <see cref="AnonymousPipeClientStream"/> whose <see cref="SafePipeHandle"/> holds the pipe's
/// file descriptor; the pipe capacity is a property of the pipe, so either end may set it.
/// </summary>
internal static class LibcPipeResizer
{
    /// <summary>Linux <c>F_SETPIPE_SZ</c> (<c>F_LINUX_SPECIFIC_BASE + 7</c>).</summary>
    internal const int F_SETPIPE_SZ = 1031;

    /// <summary>Linux <c>F_GETPIPE_SZ</c> (<c>F_LINUX_SPECIFIC_BASE + 8</c>).</summary>
    internal const int F_GETPIPE_SZ = 1032;

    [DllImport("libc", SetLastError = true)]
    private static extern int fcntl(int fd, int cmd, int arg);

    /// <summary>
    /// The production <see cref="PipeResizer"/>.  Makes no syscall unless <paramref name="stdout"/>
    /// is a pipe (an <see cref="AnonymousPipeClientStream"/>, which is what .NET gives a redirected
    /// child's stdout on Unix; on Windows it is a <c>FileStream</c>).
    /// </summary>
    internal static PipeResizeResult Resize(Stream stdout, int requestedBytes)
    {
        if (stdout is not AnonymousPipeClientStream pipeStream)
            return new PipeResizeResult(0, 0, $"the stream is a {stdout.GetType().Name}, not a pipe");

        var pipe = pipeStream.SafePipeHandle;
        bool addRef = false;
        try
        {
            pipe.DangerousAddRef(ref addRef);
            int fd = (int)pipe.DangerousGetHandle();

            if (fcntl(fd, F_SETPIPE_SZ, requestedBytes) < 0)
                return new PipeResizeResult(0, Marshal.GetLastPInvokeError());

            int granted = fcntl(fd, F_GETPIPE_SZ, 0);
            return granted < 0
                ? new PipeResizeResult(0, Marshal.GetLastPInvokeError())
                : new PipeResizeResult(granted, 0);
        }
        finally
        {
            if (addRef) pipe.DangerousRelease();
        }
    }
}

/// <summary>
/// Enlarges <c>arecord</c>'s stdout pipe so a stalled reader has seconds of headroom instead of the
/// kernel default (64 KiB, about 1.37 s of 12 kHz float).  Never throws and never changes which
/// bytes are read.
/// </summary>
internal static class StdoutPipeEnlarger
{
    /// <summary>Requested pipe capacity: 1 MiB, about 21.8 s of 12 kHz float mono.</summary>
    internal const int RequestedBytes = 1_048_576;

    /// <summary>Attempts the resize on <paramref name="stdout"/> and logs the outcome.</summary>
    internal static void Apply(Stream stdout, PipeResizer resizer, ILogger? logger)
    {
        try
        {
            var result = resizer(stdout, RequestedBytes);
            if (result.NotAttempted is not null)
                logger?.LogWarning(
                    "could not enlarge the arecord stdout pipe: {Reason}; not attempted; " +
                    "capture continues with the default pipe size",
                    result.NotAttempted);
            else if (result.GrantedBytes > 0)
                logger?.LogInformation(
                    "arecord stdout pipe enlarged: requested {Requested}, granted {Granted} bytes",
                    RequestedBytes, result.GrantedBytes);
            else
                logger?.LogWarning(
                    "could not enlarge the arecord stdout pipe (errno {Errno}); " +
                    "capture continues with the default pipe size",
                    result.Errno);
        }
        catch (Exception ex)
        {
            // Missing libc, EntryPointNotFoundException, a closed handle: never fatal.
            logger?.LogWarning(ex,
                "could not enlarge the arecord stdout pipe (errno unavailable: {ExType}); " +
                "capture continues with the default pipe size",
                ex.GetType().Name);
        }
    }
}
