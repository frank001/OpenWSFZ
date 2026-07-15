using System.Globalization;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Resolves the executable and argument list needed to spawn a replacement instance of the
/// current daemon process, as part of an API-initiated restart (remote-daemon-restart,
/// design.md Decision 2).
/// </summary>
internal static class DaemonRelaunch
{
    /// <summary>An executable path and the argument list to launch it with.</summary>
    internal readonly record struct RelaunchCommand(string FileName, string[] Arguments);

    /// <summary>
    /// Resolves the relaunch command for the current process.
    /// </summary>
    /// <param name="processPath">
    /// Typically <see cref="Environment.ProcessPath"/>. Passed explicitly (rather than read
    /// internally) so unit tests can exercise both branches below without depending on the
    /// real test-runner's own process path.
    /// </param>
    /// <param name="originalArgs">
    /// The CLI arguments this process was launched with — i.e. <c>args</c> as received by
    /// <c>Main</c>/top-level statements, not including the executable path itself.
    /// </param>
    /// <param name="entryAssemblyLocation">
    /// Typically <c>Assembly.GetEntryAssembly()!.Location</c>. Only consulted on the
    /// <c>dotnet</c>-muxer branch below (a framework-dependent launch, e.g. <c>dotnet run</c>),
    /// where <paramref name="processPath"/> resolves to the <c>dotnet</c> muxer itself rather
    /// than the managed assembly — re-launching <paramref name="processPath"/> with only
    /// <paramref name="originalArgs"/> would run bare <c>dotnet</c> with nothing to load.
    /// </param>
    /// <param name="currentPid">
    /// The current process's PID, appended via <c>--relaunched-from</c> so the new instance's
    /// startup can log which instance it is replacing and retry a transient bind conflict
    /// while that instance finishes shutting down.
    /// </param>
    internal static RelaunchCommand ResolveCommand(
        string processPath, string[] originalArgs, string entryAssemblyLocation, int currentPid)
    {
        // Framework-dependent launch (`dotnet OpenWSFZ.Daemon.dll` / `dotnet run`, this
        // project's own documented working deployment model): processPath is the `dotnet`
        // muxer, not the managed DLL. Prepend the entry assembly's own location so the
        // spawned `dotnet` has something to load.
        var isDotnetMuxer = string.Equals(
            Path.GetFileNameWithoutExtension(processPath), "dotnet",
            StringComparison.OrdinalIgnoreCase);

        var args = new List<string>(originalArgs.Length + 3);
        if (isDotnetMuxer)
            args.Add(entryAssemblyLocation);

        args.AddRange(originalArgs);
        args.Add("--relaunched-from");
        args.Add(currentPid.ToString(CultureInfo.InvariantCulture));

        // Self-contained/apphost launch: processPath IS the real executable in both branches —
        // only the argument list differs.
        return new RelaunchCommand(processPath, args.ToArray());
    }
}
