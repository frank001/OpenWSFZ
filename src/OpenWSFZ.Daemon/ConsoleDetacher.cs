using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Serilog;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Detaches the current process from whatever console/controlling terminal it inherited at
/// launch (daemon-background-mode, design.md Decision 1), so that subsequently closing that
/// console/terminal does not terminate the process.
///
/// <para>
/// <see cref="Detach"/> is called once, as the very first thing <c>Program.cs</c> does when
/// <c>--background-worker</c> is present — before config load, logging pipeline construction,
/// or host building (design.md Decision 1's "before any other startup work"). Because the
/// Serilog pipeline does not exist yet at that point, this class logs via the static
/// <see cref="Log"/> logger directly (matching <c>LoggingPipeline.EnforceRetention</c>'s own
/// precedent) rather than taking an injected <c>ILogger</c> — before the first
/// <c>LoggingPipeline.Apply</c> call, <c>Log.Logger</c> is Serilog's no-op default, so these
/// calls are harmlessly swallowed at that point in startup and become observable once Apply()
/// has run for any later call.
/// </para>
/// </summary>
internal static partial class ConsoleDetacher
{
    // Kept alive for the process lifetime (never disposed) so the SIGHUP-ignore handler is
    // never garbage-collected/unregistered prematurely (design.md Decision 1).
    private static PosixSignalRegistration? _sigHupRegistration;

    /// <summary>
    /// Detaches from the inherited console/controlling terminal using the platform-appropriate
    /// mechanism, gated at runtime by <see cref="OperatingSystem.IsWindows"/> (design.md Context
    /// — <see cref="PosixSignal.SIGHUP"/> throws <see cref="PlatformNotSupportedException"/> on
    /// Windows; <see cref="FreeConsole"/> is a Windows-only API).
    /// </summary>
    public static void Detach()
    {
        if (OperatingSystem.IsWindows())
        {
            var freed = FreeConsole();
            if (freed)
                Log.Debug("daemon-background-mode: detached from inherited console via FreeConsole().");
            else
                Log.Debug(
                    "daemon-background-mode: FreeConsole() returned failure (GetLastError={Error}) " +
                    "— process may already be console-detached.", Marshal.GetLastWin32Error());
        }
        else
        {
            // ctx.Cancel = true suppresses the default SIGHUP termination behaviour — this is
            // the exact mechanism `nohup` uses (design.md Decision 1's rejected-alternative
            // discussion of a full daemonize).
            _sigHupRegistration = PosixSignalRegistration.Create(PosixSignal.SIGHUP, ctx =>
            {
                ctx.Cancel = true;
            });
            Log.Debug(
                "daemon-background-mode: registered a SIGHUP-ignore handler — process will " +
                "survive its controlling terminal closing.");
        }
    }

    [SupportedOSPlatform("windows")]
    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool FreeConsole();
}
