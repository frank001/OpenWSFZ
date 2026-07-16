## Context

`remote-daemon-restart` (implemented, merged to `main`, not yet archived) added a self re-exec
mechanism: `DaemonRelauncher.TrySpawnReplacement()` spawns a replacement process via
`new ProcessStartInfo(cmd.FileName) { UseShellExecute = false }`, with no console-detachment flags
and no stdio redirection. On Windows, a child spawned this way inherits the parent's console
handles wholesale — confirmed live: after a restart, the console's foreground-process tracking
reverts to whatever shell was underneath the original `dotnet run`/apphost invocation (so Ctrl-C
stops reliably reaching the child), but the child remains attached to that console's process
group, so closing the console window still terminates it.

Two platform-specific facts drive this design:

- **Windows**: a console-subsystem process (which `OpenWSFZ.Daemon` is) can call `FreeConsole()`
  (`kernel32.dll`) on itself at any point to detach from whatever console it is currently attached
  to. Once detached, closing that console no longer affects the process — Windows only sends
  `CTRL_CLOSE_EVENT` / forcibly terminates processes still attached to a console being torn down.
  `System.Diagnostics.ProcessStartInfo` does not expose the Win32 process-creation flags
  (`DETACHED_PROCESS` / `CREATE_NEW_PROCESS_GROUP`) that would prevent console inheritance at
  spawn time — there is no supported way to pass a custom `dwCreationFlags` through
  `Process.Start`. `FreeConsole()` avoids needing that entirely: it works by having the process
  detach *itself*, after it already exists, regardless of how it was spawned.
- **POSIX (Linux/macOS)**: a terminal closing sends `SIGHUP` to the foreground process group of
  its controlling terminal. A process that ignores `SIGHUP` survives terminal closure — this is
  the entire mechanism `nohup` uses; it does nothing else (no session detach, no fd juggling).
  .NET has a built-in, purely-managed API for this since .NET 6: `PosixSignalRegistration`.
  `PosixSignal.SIGHUP` is POSIX-only — `PosixSignalRegistration.Create` throws
  `PlatformNotSupportedException` if attempted on Windows, so this must be gated by
  `!OperatingSystem.IsWindows()`, mirroring this codebase's existing `WASAPI_SUPPORTED`-style
  platform branching (`AudioOnlyPttController.cs`).

Neither mechanism requires forking a running managed process (which the CLR does not support
safely — `fork()` without an immediate `exec()` is documented as unsafe in a multi-threaded
process, and the CLR is always multi-threaded by the time `Main` runs). Both mechanisms operate on
an already-running, already-`exec`'d process detaching itself from whatever terminal/console it
happens to have inherited — no raw `fork()` anywhere in this design.

`LoggingPipeline.Apply` (from `f-004-operator-visibility-improvements`) always wires a Console
sink; `LoggingConfig.FileEnabled` defaults to `false`. A detached process with no console and no
file sink would run invisibly with zero observability — a background instance must not be allowed
to end up in that state silently.

## Goals / Non-Goals

**Goals:**
- An operator-facing `--background` CLI flag: `dotnet run -- --background` (or the published
  exe) spawns a detached instance and returns control of the shell immediately, without the
  operator needing a platform-specific incantation (`Start-Process`, `nohup ... &`, `setsid`).
- The detached instance survives its originating console/terminal closing, on both Windows and
  POSIX.
- Detached status persists across every future restart triggered via
  `POST /api/v1/system/restart` — a background instance's replacement is also spawned detached,
  by default, with no separate flag the operator has to remember to pass again.
- A background instance is never silently unobservable: file logging is guaranteed on, and the
  operator gets a clear one-time confirmation (or diagnosable failure) at the point of launch.

**Non-Goals:**
- Full `NFR-009` Windows-service / systemd-unit deployment. This change makes the process survive
  a closed terminal; it adds no crash-restart supervision — if the process itself crashes, nothing
  brings it back, exactly as today. A real service manager remains a separate, larger, already-
  tracked future item.
- A fully "invisible" Windows spawn with zero console flash in every scenario (see Decision 3's
  accepted cosmetic risk for the restart-of-a-background-instance case).
- Any change to `DaemonRelauncher`'s or `DaemonRelaunch.ResolveCommand`'s existing spawn mechanism
  (`Process.Start`, argument resolution) — this design deliberately reuses that mechanism
  unmodified and adds new flags to the argument list it already builds, rather than replacing it.

## Decisions

### 1. Self-detach in the child, not special creation flags in the parent

**Decision:** Do not attempt to prevent console/terminal inheritance at spawn time. Instead, the
spawned child calls the platform detach primitive on itself, as the very first thing it does after
`LaunchOptions.Parse` — before the logging pipeline is built, before the config store is loaded,
before anything else in `Program.cs`:
- **Windows**: P/Invoke `kernel32.dll`'s `FreeConsole` using `[LibraryImport]`
  (source-generated marshalling), **not** classic `[DllImport]`. `OpenWSFZ.Daemon.csproj` sets
  `PublishAot=true` (whenever a `RuntimeIdentifier` is supplied) with `TreatWarningsAsErrors=true`
  — the exact combination that already broke this project's CI once today on an unrelated
  AOT-incompatibility (`IL3000`, `remote-daemon-restart`'s `Assembly.Location` call). A
  no-marshalling `bool`-returning P/Invoke like `FreeConsole` is a trivial case for
  `LibraryImport` (it has supported `net7.0`+, is NativeAOT/trimming-safe by construction since it
  generates the marshalling stub at compile time rather than relying on runtime reflection, and is
  this project's own `.editorconfig`-enforceable modern-interop convention where one doesn't
  already exist to match) — there is no reason to reach for the legacy, AOT-riskier `DllImport`
  here.
- **POSIX**: `PosixSignalRegistration.Create(PosixSignal.SIGHUP, ctx => ctx.Cancel = true)`,
  keeping the returned `PosixSignalRegistration` alive for the process's lifetime (assigned to a
  field/local that is never disposed until shutdown, matching the pattern .NET's own docs use for
  long-lived signal handlers). This is a fully-managed BCL API, not P/Invoke — no AOT concern here
  beyond what .NET itself already guarantees for this type.

**Why:** `ProcessStartInfo` cannot pass `DETACHED_PROCESS` (Windows) and there is no equivalent
"don't inherit the controlling terminal" flag needed on POSIX at all — `SIGHUP`-ignore requires no
special process-creation step whatsoever, it is entirely a property of the already-running
process. This keeps `DaemonRelauncher.TrySpawnReplacement()` and `DaemonRelaunch.ResolveCommand`
— both already shipped and tested by `remote-daemon-restart` — completely unmodified in their
spawn mechanics; the only change to that code is which flags get appended to the argument list
(Decision 2).

**Alternative considered:** P/Invoke `CreateProcess` directly (`kernel32.dll`) with
`dwCreationFlags = DETACHED_PROCESS`, bypassing `ProcessStartInfo`/`Process.Start` entirely for
the Windows spawn path. Rejected — this requires reimplementing Win32 command-line argument
quoting (`CreateProcess` takes a single command-line string, not an argv array; `Process.Start`'s
own quoting logic is internal, not public) purely to shave a sub-second, self-correcting console
flash in one edge case (Decision 3). Meaningfully more P/Invoke surface and a new failure mode
(incorrect quoting silently mangling an argument containing spaces, e.g. a Windows config path)
for no behavioural benefit over `FreeConsole()`.

**Alternative considered (POSIX):** A full daemonize (`setsid()` to become a new session leader,
optionally a double-fork, explicit fd redirection to `/dev/null`). Rejected as unnecessary for the
stated problem — `SIGHUP`-ignore is the exact mechanism `nohup` uses in production Unix tooling for
precisely "survive the terminal closing," is a single managed API call with no P/Invoke, and does
not need the additional session-detachment semantics a true daemon (e.g. one also protecting
against job-control signals sent to a whole process group) would need. If a future requirement
needs those additional guarantees, this can be revisited without touching anything else in this
design.

### 2. New flags: `--background` (spawn-and-exit) vs. `--background-worker` (detach-in-place)

**Decision:** Two new CLI flags, following `LaunchOptions`'s existing pattern:
- `--background`: operator-facing. Present with no other special flag, at what is otherwise a
  normal cold start (no `--relaunched-from`). Triggers "spawn a child with `--background-worker`
  appended to its arguments (reusing `DaemonRelaunch.ResolveCommand`'s existing dotnet-muxer/
  apphost branching unchanged), then exit" — mirrors `remote-daemon-restart`'s existing
  spawn-then-stop shape, but self-detach rather than replace-in-place.
- `--background-worker`: internal marker (not intended for direct operator use, though — per
  `LaunchOptions`'s existing "unknown arguments are silently ignored" convention and
  `--relaunched-from`'s own precedent — nothing prevents an advanced operator passing it by hand).
  Present → the process is the actual detached worker: call the platform detach primitive
  (Decision 1) immediately, force file logging on and suppress the console sink (Decision 4), then
  continue normal startup in place. Does **not** spawn another child.

`DaemonRelaunch.ResolveCommand` gains one new parameter, `bool propagateBackgroundWorker`, appended
identically on both the dotnet-muxer and apphost branches (mirroring how `--relaunched-from
<pid>` is already appended identically on both). `DaemonRelauncher` is constructed (via DI, in
`Program.cs`'s `configureServices`) with the current instance's `options.IsBackgroundWorker`
captured, so `POST /api/v1/system/restart` on an already-detached instance produces a replacement
that is also spawned with `--background-worker` — satisfying the Captain's stated requirement that
detached status persists across restarts, not just the original cold start.

**Why two flags, not one:** A single `--background` flag would leave `Program.cs` unable to
distinguish "I am the original interactive invocation, please spawn a detached child and hand
back the shell" from "I am the detached child, just detach and start" — collapsing them would
either spawn a child forever (infinite recursion) or never actually return control to the
invoking shell.

### 3. Restarting an already-background instance: accepted cosmetic risk on Windows

**Decision:** No special handling. When `DaemonRelauncher.TrySpawnReplacement()` runs from a
process that has already called `FreeConsole()`, the resulting child (a console-subsystem EXE
spawned from a console-less parent) may have Windows auto-allocate it a new console window
momentarily, before it reaches its own `--background-worker` handling and calls `FreeConsole()`
again on itself.

**Why this is acceptable:** Windows destroys a console automatically once zero processes remain
attached to it. The auto-allocated console (if one appears at all — this depends on Windows
Terminal/ConPTY specifics) exists for at most the few milliseconds between process creation and
the child reaching its own `FreeConsole()` call, which happens before any other startup work
(Decision 1). Worst case is a sub-second window flash, self-correcting with no operator action
and no functional impact — not worth the added P/Invoke surface (Decision 1's rejected
`CreateProcess` alternative) to fully eliminate.

### 4. Observability: force file logging on, suppress the console sink

**Decision:** `Program.cs`'s logging bootstrap (`LoggingPipeline.Apply`) gains a
`suppressConsoleSink: bool` parameter, `true` when `options.IsBackgroundWorker`. When true:
- The `LoggingConfig` passed to `Apply` has `FileEnabled` forced to `true` in memory (never
  rewritten to the persisted `config.json` — the operator's saved preference is untouched; this
  mirrors `remote-daemon-restart`'s own precedent of never silently rewriting persisted config).
  If forcing it on, log one line at Warning *before* the console sink is suppressed (so it is the
  last thing visible in the console flash, if any) naming the resolved log file path.
- `LoggerConfiguration.WriteTo.Console(...)` is skipped entirely rather than configured and left
  to silently fail — after `FreeConsole()`, `Console.Out`/`Console.Error` point at invalid
  handles; Serilog's own sink-dispatch layer generally swallows a misbehaving sink's exceptions,
  but not configuring it at all is strictly safer and avoids relying on that.

**Why force rather than fail fast:** A background instance is, by definition, launched with no
one necessarily watching. Refusing to start because `logging.fileEnabled` happened to be `false`
would contradict the entire purpose of `--background` (start it and walk away) for the sake of a
setting most operators have never had a reason to touch. Forcing it on with a clearly-logged
one-time notice is closer to this project's existing "prefer the design that fails toward staying
observable" instinct (echoing `cat-tx-ptt`'s "fail toward rig stays silent" framing, applied here
to "fail toward the operator can still find out what happened").

### 5. Cold-start confirmation: bounded poll, not a hard wait or a fire-and-forget

**Decision:** After spawning the detached child (`--background` cold-start path), the original
process polls `GET /api/v1/status` on the resolved port for up to 5 seconds (500 ms interval,
mirroring `DaemonStartup`'s existing retry-interval convention) before exiting. On success, print
a confirmation line naming the PID and the resolved log file path. If the budget is exhausted
without a successful response, print a caveat — "spawned but could not confirm it is listening
yet; check `<logfile>`" — and still exit 0 (the spawn itself succeeded; a slow child is not
necessarily a failed one).

**Why bounded, not unbounded or none:** An unconfirmed silent exit ("ran `--background`, prompt
came back immediately, no idea if it worked") is exactly the unobservability Decision 4 exists to
avoid. An unbounded wait would defeat "hand the shell back immediately," the other half of what
`--background` is for. Five seconds is short enough to feel instant for the normal case and long
enough to cover realistic startup work (config load, device enumeration) without the operator
mistaking a slow-but-fine startup for a failure.

### 6. Guard the two existing direct-`Console`-write call sites, found by audit not assumption

**Decision:** A repo-wide grep for `Console.Out.Write`/`Console.Error.Write`/`Console.Write` under
`src/OpenWSFZ.Daemon` and `src/OpenWSFZ.Web` (performed while writing this design, not assumed)
found exactly two live call sites that bypass Serilog entirely and would very likely throw once
`FreeConsole()` has run (Windows) — `Console.Out`/`Console.Error` point at invalid handles after
detachment:
- `WelcomeBannerEmitter.Emit` (`Console.Out.WriteLine`) — called unconditionally from
  `Program.cs`'s `ApplicationStarted.Register` callback, i.e. exactly when a background worker
  finishes starting up. Left unguarded, this would crash the process at the worst possible moment
  — the instant it starts successfully serving.
- `Program.cs`'s own `Console.Error.WriteLine($"[OpenWSFZ] Config: {configSource} → {configPath}")`
  — runs immediately after `LaunchOptions.Parse`, before the config store or logging pipeline
  exist, i.e. before this design's own detach point could even have logging infrastructure to
  fall back on.

Both call sites SHALL be guarded to no-op when `options.IsBackgroundWorker` is `true`: skip the
banner write entirely (the equivalent "listening on port N" fact is already covered by
`daemon-host`'s existing "Startup with the flag is logged"-style Information-level log line, which
for a background worker goes to the forced-on file sink per Decision 4); skip the early config-
path stderr line similarly (its Information-level logged equivalent, per `daemon-host`'s existing
"Resolved config path logged at startup" requirement, already fires once the logger exists and
will reach the file sink the same way).

A third location, `StderrLoggerProvider` (`src/OpenWSFZ.Daemon/Logging/StderrLoggerProvider.cs`),
also writes directly to `Console.Error` on every log call — but a repo-wide search confirms it is
never registered/instantiated anywhere in `src/` or `tests/` (dead code, unrelated to this
change). No action needed; noted here only so a future reader doesn't have to re-derive that it's
inert.

**Why call this out as its own decision rather than folding it into Decision 1:** this was a
concrete implementation-blocking finding from auditing the actual codebase, not a natural
consequence of the FreeConsole()/SIGHUP-ignore choice alone — it needed to be found by grep, not
inferred, and is exactly the kind of thing worth being explicit about rather than leaving implicit
for whoever implements this to discover the hard way (mid-crash, in the field).

## Risks / Trade-offs

- **[Risk] `SIGHUP`-ignore is not a full daemonize** — the process stays a member of its original
  session/process group; a mechanism other than terminal-close that targets the whole foreground
  process group (rare, and distinct from the terminal-close scenario this change targets) could
  still reach it. → Accepted (Decision 1): the concrete, reported problem is terminal closure,
  which `SIGHUP`-ignore fully addresses; a true daemonize is strictly more code and interop
  surface for guarantees nothing in this proposal asks for.
- **[Risk] Forcing `FileEnabled` in memory means a background instance's disk footprint changes
  from what the operator's `config.json` says**, which could surprise someone auditing disk usage.
  → Mitigation: logged once at Warning before the console sink disappears (Decision 4); the
  persisted config file itself is never modified, so a subsequent normal (non-background) start
  reverts to exactly what was there before.
- **[Trade-off] Windows console flash on restart of an already-detached instance** (Decision 3) —
  accepted as a sub-second, self-correcting cosmetic artifact rather than adding P/Invoke
  `CreateProcess` purely to eliminate it.
- **[Risk] `--background`'s 5-second confirmation poll (Decision 5) could itself be slow/blocked**
  if something is badly wrong (e.g. the resolved port is unexpectedly firewalled even from
  loopback) — the operator sees the caveat message rather than a hang, since the budget is fixed
  and always exits 0 regardless of poll outcome.

## Migration Plan

- Purely additive: two new CLI flags (both silently ignored by any older build, per
  `LaunchOptions`'s existing forward-compatibility convention), no config schema change, no change
  to any existing flag's behaviour when `--background`/`--background-worker` are absent (the
  overwhelmingly common case — an ordinary cold start or an ordinary restart of a non-background
  instance is untouched).
- No rollback concerns beyond a normal code revert — this feature has no persisted state of its
  own (the in-memory `FileEnabled` override never touches `config.json`).

## Open Questions

- Should the Settings page eventually surface "this instance is running in background mode" (e.g.
  next to the existing native-decoder-shim-version read-only field on the Advanced tab), so an
  operator connecting remotely can tell without checking the process list? Deferred — no UI is
  strictly required for this change to be useful (it is a CLI-only, launch-time choice), and
  `daemon-status-visibility`'s existing surface can absorb this later if it turns out to matter in
  practice.
- ~~Should `--background` validate that stdin is not itself needed for anything?~~ Resolved:
  confirmed by grep (`Console.In`/`Console.Read`/`Console.OpenStandardInput`) that nothing under
  `src/` reads from stdin anywhere in this codebase — moot, no action needed.
