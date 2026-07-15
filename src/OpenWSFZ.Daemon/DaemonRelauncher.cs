using System.Diagnostics;
using System.Reflection;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Production <see cref="IDaemonRelauncher"/>: resolves the relaunch command via
/// <see cref="DaemonRelaunch.ResolveCommand"/> and spawns it with <see cref="Process.Start(ProcessStartInfo)"/>
/// (remote-daemon-restart, design.md Decisions 1-3).
/// </summary>
internal sealed class DaemonRelauncher : IDaemonRelauncher
{
    private readonly ILogger<DaemonRelauncher> _logger;

    public DaemonRelauncher(ILogger<DaemonRelauncher> logger) => _logger = logger;

    public bool TrySpawnReplacement()
    {
        var processPath = Environment.ProcessPath;
        if (processPath is null)
        {
            _logger.LogError(
                "Cannot relaunch: Environment.ProcessPath is null — the current instance " +
                "remains up and serving.");
            return false;
        }

        // IL3000: Assembly.Location always returns "" for a single-file AOT-published
        // executable (which this project ships — OpenWSFZ.Daemon.csproj sets PublishAot=true
        // whenever a RuntimeIdentifier is supplied). That is harmless here: the resolved value
        // is only *consulted* by DaemonRelaunch.ResolveCommand when Environment.ProcessPath's
        // file name is "dotnet" (a framework-dependent dotnet-run/dotnet-exec launch,
        // design.md Decision 2) — a condition that can never be true for a process that is
        // itself the AOT-compiled single-file executable, so an empty string here is simply
        // never used on that code path.
#pragma warning disable IL3000
        var entryAssemblyLocation = Assembly.GetEntryAssembly()?.Location ?? string.Empty;
#pragma warning restore IL3000

        // GetCommandLineArgs()[0] is the executable path itself — skip it, matching the
        // `args` this process's own Main/top-level statements received.
        var originalArgs = Environment.GetCommandLineArgs()[1..];

        var cmd = DaemonRelaunch.ResolveCommand(
            processPath, originalArgs, entryAssemblyLocation, Environment.ProcessId);

        _logger.LogInformation(
            "Relaunching daemon: {FileName} {Arguments}",
            cmd.FileName, string.Join(' ', cmd.Arguments));

        try
        {
            var psi = new ProcessStartInfo(cmd.FileName) { UseShellExecute = false };
            foreach (var arg in cmd.Arguments)
                psi.ArgumentList.Add(arg);

            Process.Start(psi);
            return true;
        }
        catch (Exception ex)
        {
            // A failure to spawn the child must abort the restart before the current process
            // stops — the currently-running daemon remains up and serving (design.md Decision 1
            // Risks, "malformed or unreachable relaunch command").
            _logger.LogError(ex,
                "Failed to spawn replacement daemon process — the current instance remains up " +
                "and serving.");
            return false;
        }
    }
}
