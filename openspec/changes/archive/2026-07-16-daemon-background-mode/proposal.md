**User-facing:** yes

## Why

`remote-daemon-restart` (implemented, merged to `main`, not yet archived) spawns a replacement
daemon process via `DaemonRelauncher.TrySpawnReplacement()` using
`new ProcessStartInfo(cmd.FileName) { UseShellExecute = false }`, with no `CreateNoWindow` and no
stdio redirection. On Windows this means the child inherits the parent's console handles
wholesale. The Captain tested this live: after a restart triggered from the Settings page, the
originating console no longer meaningfully controls the running daemon — Ctrl-C stops reaching it
once the console's foreground-process tracking reverts to the shell underneath the original
`dotnet run`/apphost process — yet **closing that console still terminates the child**, because it
remains attached to the console's process group. This is correct, expected behaviour for a
console-attached child process, not a defect in the restart mechanism itself. The actual gap: there
is currently no supported way to run the daemon detached from a console at all, at any point (cold
start or relaunch), so an operator who wants "start it once, then close my terminal or log out"
has no option that doesn't kill the process.

## What Changes

- Add a `--background` CLI flag, recognised by `LaunchOptions.Parse` following the existing
  `--port`/`--config`/`--relaunched-from` pattern. When present at cold start, the daemon spawns
  itself as a fully detached process (no console attachment) and the original invocation exits
  once the detached instance is confirmed running — mirroring the "spawn child, then let the
  parent finish" shape `remote-daemon-restart` already established, but for a deliberate
  self-detach rather than a replace-in-place restart.
- Platform-specific detachment mechanism (exact approach decided in design.md):
  - **Windows**: `ProcessStartInfo` does not expose the Win32 process-creation flags needed
    (`DETACHED_PROCESS` / `CREATE_NO_WINDOW`) to spawn a console-detached child — requires either
    P/Invoke `CreateProcess` or another documented .NET mechanism.
  - **Linux/macOS**: requires a real daemonize (controlling-terminal detachment, e.g.
    `setsid`-equivalent) so a `SIGHUP` on terminal close does not propagate to the process.
- `DaemonRelauncher`/`DaemonRelaunch.ResolveCommand` (from `remote-daemon-restart`) are extended so
  that an instance already running detached propagates that fact to its replacement on every
  future self-relaunch triggered via `POST /api/v1/system/restart` — detached status persists
  across restarts by default, not just at the original cold start, closing the loop the Captain's
  live test surfaced (every restart re-creates the same console-attachment problem otherwise).
- Background mode's interaction with logging is made explicit and safe: a detached process has no
  console for an operator to read `Console.WriteLine` output from, and `LoggingConfig.FileEnabled`
  defaults to `false` — launching detached with file logging still off would produce a running but
  completely unobservable daemon. Exact behaviour (force file logging on, fail fast, or something
  else) is a design.md decision.
- Explicitly **not** in scope: full `NFR-009` Windows-service/systemd-unit deployment (a real
  process supervisor with automatic restart-on-crash). This change only prevents "closing the
  console kills the process" — it adds no crash-recovery guarantee. Stated plainly so the two are
  never conflated, the same way `remote-daemon-restart`'s own design.md drew that line.

## Capabilities

### New Capabilities
- `daemon-background-mode`: the `--background` CLI flag, the platform-specific detachment
  mechanisms (Windows process-creation flags, POSIX daemonize), and the propagation of detached
  status across self-relaunches.

### Modified Capabilities
- `daemon-host`: `LaunchOptions.Parse` gains a new recognised flag; the existing "logging pipeline
  initialised before web host" requirement gains background-mode-specific behaviour around file
  logging.

## Impact

- **Affected code**: `src/OpenWSFZ.Daemon/LaunchOptions.cs`, `src/OpenWSFZ.Daemon/Program.cs`,
  `src/OpenWSFZ.Daemon/DaemonRelauncher.cs`, `src/OpenWSFZ.Daemon/DaemonRelaunch.cs` (all from
  `remote-daemon-restart`), `src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs`, plus a new
  platform-detachment helper (Windows P/Invoke + POSIX daemonize implementations).
- **Depends on**: `remote-daemon-restart` (implemented and merged to `main`, but not yet archived
  at the time this proposal is written) — the self-relaunch propagation requirement modifies
  `DaemonRelauncher`/`DaemonRelaunch`, which that change introduced. This proposal does not
  re-litigate any `remote-daemon-restart` decision; it only extends the relaunch command those
  types already build.
- **Not affected**: the restart-refusal-while-transmitting guard, the bind-retry mechanism
  (`DaemonStartup.StartWithBindRetryAsync`), and the Settings-page "Restart Daemon" action's
  request/response shape — all orthogonal to console attachment.
- **Explicitly out of scope**: `NFR-009` full service/unit deployment with crash-restart
  supervision (see "What Changes" above).
