## Context

Two shipped settings only take effect after a full process restart:

- `ptt.method` (`cat-tx-ptt`) — `Program.cs` (lines 424-451) switches on
  `configStore.Current.Ptt.Method` exactly once, at `services.AddSingleton<IPttController, …>()`
  registration time, before the host is built. Changing it persists to `config.json` immediately
  (`POST /api/v1/config` → `store.Current` is mutable and hot), but the already-running
  `IPttController` singleton never changes.
- `RemoteAccess.Enabled` / bind address (`lan-remote-access`) — `IBindPolicy` is resolved once at
  Kestrel startup; its own design.md states outright: "the bind address cannot be changed without a
  daemon restart (Kestrel limitation)."

Today the *only* remedy is physical/console access to the machine: send Ctrl-C or close the
terminal, then re-launch. That directly undermines the LAN remote-access capability's own premise
— an operator on another device on the network has no way to apply a restart-required change at
all. `TECHNICAL_SPEC.md` lists "Windows-service deployment" as a *planned* seam (NFR-009) but
confirms "in v1 only `TerminalLifecycle` is registered" — there is no Windows Service, NSSM wrapper,
or systemd unit watching this process today. The documented working deployment model is a plain
foreground process (`dotnet run`, or a published exe launched directly). Consequently, if the
daemon merely exits, nothing brings it back — any remote-restart design must have the daemon
relaunch itself before it goes away.

`Program.cs`'s existing shutdown sequence (lines 553-783) is already well-defined: `WebApp.Create`
registers an `ApplicationStopping` hook that aborts all WebSocket connections first (`AbortAll`,
`WebApp.cs` line 1591), then `Program.cs`'s own `ApplicationStopping` hook stops the capture
pipeline, disposes it, and flushes the logging pipeline (lines 753-783), guarded by
`restartSemaphore` so it cannot race a concurrent capture-restart. `await app.RunAsync()` (line 803)
returns once that whole sequence completes and the process exits 0 — matching the existing
`daemon-host` spec's Ctrl-C/SIGTERM requirements. This design deliberately reuses that sequence
unchanged rather than inventing a parallel shutdown path.

## Goals / Non-Goals

**Goals:**
- A `POST /api/v1/system/restart` endpoint, reachable over LAN like every other mutating endpoint,
  that relaunches the daemon with the currently-persisted config and exits the old process.
- Zero window where "the daemon is just gone" — the new instance must come up on the same port
  without requiring anything external (no service manager, no operator action) to bring it back.
- Never interrupt a real, in-progress over-the-air transmission.
- A Settings-page action the operator actually discovers when it's needed (next to `ptt.method` and
  Remote Access), not buried in an unrelated tab.

**Non-Goals:**
- PTT-method hot-reloading. Considered and dropped: once this ships, the same friction is solved by
  "Save, click Restart," without engineering mid-transmission hand-off between
  `AudioOnlyPttController` / `CatPttController` / `SerialRtsDtrPttController` instances.
- Full NFR-009 Windows-service / systemd-unit deployment. A real service manager would make restart
  (and crash recovery) more robust, but is a separate, larger, already-tracked item; this change
  must work in the *current*, service-less deployment model.
- Zero-downtime restart (e.g., two processes briefly serving traffic side by side, handing off
  live WebSocket connections). Out of scope — a short, visible "reconnecting" gap in the UI is
  acceptable.
- Restarting to apply a *different* config than what's already persisted (e.g., "restart with these
  unsaved edits") — the endpoint restarts with whatever `config.json` currently holds; Save is a
  separate, already-existing step.

## Decisions

### 1. Self re-exec, gated by an explicit relaunch marker — not a blanket bind-retry, not env var

**Decision:** The restart handler spawns a new child process of the same executable with the same
CLI arguments *plus* a new `--relaunched-from <pid>` flag, added to `LaunchOptions` (which already
documents "unknown arguments are silently ignored (forward-compatible)" — this is purely additive).
Only when that flag is present does the new process's startup wrap its final host-start call
(`await app.RunAsync()`/equivalent `StartAsync`) in a bind-retry loop; a normal cold start (no flag)
still fails fast on a port conflict exactly as today.

**Why:** Two alternatives were considered and rejected:
- *Always retry-bind on any startup, restart or not.* Rejected — this would silently mask the
  genuine operator mistake of double-launching the daemon (e.g., double-clicking the exe twice)
  behind up to ~20 seconds of apparent hang before the second instance finally reports a conflict,
  which is worse UX than today's immediate, clear failure.
- *Pass the marker via an environment variable instead of a CLI flag.* Rejected — a CLI flag is
  visible in the OS process list/Task Manager command line, which is useful when diagnosing "why
  are there two OpenWSFZ processes" during development or support; an env var is invisible without
  inspecting the child's environment block. `LaunchOptions.Parse` already has a simple, extensible
  pattern for adding recognised flags (mirrors `--port`/`--config`).

### 2. Resolving what to relaunch: detect the `dotnet` generic host vs. a self-contained apphost

**Decision:** Resolve the relaunch command as follows:
1. Let `processPath = Environment.ProcessPath` and `args = Environment.GetCommandLineArgs()`.
2. If `processPath`'s file name (case-insensitive, extension-agnostic) is `dotnet`, this is a
   framework-dependent launch (`dotnet OpenWSFZ.Daemon.dll …` / `dotnet run`, the project's own
   documented working deployment model) — relaunch as
   `Process.Start(processPath, [Assembly.GetEntryAssembly()!.Location, ...originalArgs, "--relaunched-from", pid])`.
3. Otherwise, `processPath` is already the real apphost/self-contained executable — relaunch it
   directly with `[...originalArgs, "--relaunched-from", pid]`.

**Why:** `Environment.ProcessPath` under `dotnet run`/`dotnet exec` returns the path to the `dotnet`
muxer itself, not the managed DLL — naively re-launching `processPath` with only the original args
would just run bare `dotnet` with no assembly to load. Since the housekeeping record for this
project explicitly notes `dotnet run` as "the documented working deployment model," this is not a
hypothetical edge case; it is the primary case this design must handle correctly. The self-contained
apphost branch is kept for when a published exe (`OpenWSFZ.Daemon.exe`, referenced elsewhere in this
repo's publish profiles) is launched directly.

**Alternative considered:** Require the operator to always run a published self-contained exe
(sidestepping the `dotnet`-muxer detection entirely). Rejected — would silently break remote-restart
for every developer/tester running via `dotnet run`, which is today's actual documented workflow.

### 3. Ordering: respond 202 → short flush delay → spawn child → `StopApplication()`

**Decision:** The endpoint handler:
1. Checks `IQsoController.Keying` (see Decision 5) and returns 409 if a QSO is transmitting.
2. Otherwise, returns `202 Accepted` immediately with a small JSON body (e.g.
   `{ "status": "restarting" }`).
3. Schedules the actual relaunch on a fire-and-forget `Task` after a short fixed delay (~500 ms) —
   long enough for the HTTP response to flush to the client before the connection is torn down.
4. That task spawns the child process (Decisions 1-2) *first*, then calls
   `app.Lifetime.StopApplication()` on the current process, which runs the existing, unmodified
   `ApplicationStopping` chain (WebSocket abort → capture-pipeline stop → log flush → process exit
   0).

**Why this order (spawn-then-stop, not stop-then-spawn):** Spawning the child before stopping the
parent lets the child start its bind-retry loop (Decision 4) immediately, in parallel with the
parent's teardown — which is exactly when the child *needs* to be retrying, since the parent still
holds the port throughout its `ApplicationStopping` work (WebSocket abort, capture-pipeline
`StopAsync`/`DisposeAsync`, log flush — none of which are instantaneous). Stopping first and
spawning only after full teardown would add that entire teardown duration as pure extra downtime
for no benefit — the child would just be idle, not yet started, while the parent is still torn down.
Responding 202 *before* either step, rather than restarting synchronously inside the handler, avoids
the response racing (and likely losing to) the process's own shutdown.

### 4. Bind-retry loop: fixed budget and interval, scoped to the final host-start call only

**Decision:** When `--relaunched-from` is present, wrap only the final `app.RunAsync()`/`StartAsync()`
call in a retry loop: on a bind failure (address already in use), wait 500 ms and retry, for a total
budget of 20 seconds, logging each attempt at Debug. If the budget is exhausted, log an error
(`daemon-host`'s existing "abnormal exit uses non-zero code" convention) and exit non-zero.

**Why scoped this narrowly:** All of `Program.cs`'s setup before `app.RunAsync()` — audio device
enumeration, native decoder construction, serial-port objects for CAT, etc. — has no side effects
that open exclusive OS resources until the host actually starts (per the existing code,
`ApplicationStarted.Register` at line 553 is what triggers audio capture, and it only fires once
`StartAsync` has *already* succeeded). Retrying only the host-start call means a failed bind attempt
never re-runs that setup, so nothing is double-opened or double-constructed between attempts.

**Why 20 seconds / 500 ms:** Chosen to match this codebase's existing convention for a generous-but-
bounded failsafe window — `PttWatchdog`'s existing hard ceiling is also 20000 ms (cat-tx-ptt). It
comfortably covers realistic teardown time (WebSocket abort, WASAPI capture stop, log flush) without
leaving an operator staring at a spinner indefinitely if something is genuinely wrong.

**Implementation correction (discovered during task 3.4/3.5):** the mechanism above is described
as "retry `app.RunAsync()`/`StartAsync()`" — that literal approach does not work. ASP.NET Core's
`KestrelServerImpl.StartAsync` marks the host "started" on its very first invocation regardless of
whether the underlying socket bind actually succeeded; a second `StartAsync()` call on the same,
already-attempted `WebApplication` instance throws `InvalidOperationException("Server has already
started.")` instead of retrying the bind. This was caught empirically while writing
`DaemonStartupTests` (task 3.5b/c), not from a documentation source. The shipped implementation
(`DaemonStartup.StartWithBindRetryAsync`) instead retries a cheap, throwaway raw TCP bind probe on
the configured port and calls the real `app.StartAsync()` exactly once, only after the probe
succeeds. This produces the identical observable behaviour for every acceptance scenario in this
change's specs (retries while the port is held; gives up after the budget; a non-relaunch cold
start is completely unaffected; no startup work repeats) without depending on repeatable
`StartAsync()` semantics ASP.NET Core does not provide. The `daemon-host` spec's own requirement
text ("SHALL retry binding its configured HTTP port") is mechanism-agnostic and required no change.

### 5. Safety gate reuses the existing `Keying` check; refuse, do not force-abort

**Decision:** `POST /api/v1/system/restart` checks `IQsoController.Keying` and returns
`409 Conflict` (with a message naming the reason) when a real QSO is currently transmitting —
textually and structurally identical to the existing guard on `/api/v1/ptt/test`
(`WebApp.cs`, "a QSO is currently transmitting"). The operator must let the transmission finish or
call the existing `/api/v1/tx/abort` themselves before retrying restart.

**Why refuse rather than auto-abort:** Force-aborting a real transmission as a side effect of an
unrelated action is exactly the class of surprising rig behaviour this project's own stated design
principle (from `cat-tx-ptt`) argues against — "prefer the design that fails toward 'rig stays
silent' over the one that fails toward 'rig stays keyed'" is about *not* taking unrequested keying
actions on the operator's behalf; auto-aborting a live TX to satisfy a restart request is the same
category of unrequested interference, just in the shutdown direction. Refusing and pointing at the
existing, already-understood abort action keeps one clear way to stop a transmission rather than two
different code paths that can both do it.

### 6. Frontend: confirmation dialog + reconnect-poll, single point of entry

**Decision:** Add one "Restart Daemon" action (Advanced tab), gated behind a confirmation dialog —
explicitly *not* following this page's existing no-confirmation convention (Save/Retry/Refresh),
because restart is materially more disruptive: it drops the WebSocket, interrupts the current decode
cycle, and briefly takes the whole UI dark. After confirming, the frontend polls `GET /api/v1/status`
(already a cheap, existing endpoint) on a short interval and shows a "reconnecting…" state until it
answers again, rather than surfacing the gap as a hard error. The restart-required notices already
planned next to `ptt.method` and the Remote Access bind controls link to this one action instead of
each growing their own restart button — a single, consistent place to actually do it.

**Why break the no-confirmation convention here specifically:** The existing convention's own
rationale (documented in `cat-tx-ptt` design.md) is that Save/Retry/Refresh are all safely reversible
or low-consequence. A restart is neither reversible mid-flight nor low-consequence (it can, per
Decision 5, be *refused* but never silently interrupts a live QSO) — but even outside of an active
QSO it briefly disconnects every connected browser tab (including other operators on the LAN), which
none of the existing unconfirmed actions do.

## Risks / Trade-offs

- **[Risk] The child's bind-retry window (Decision 4) adds up to 20 s of visible "reconnecting" UI
  in the worst case if the parent's teardown is unusually slow.** → Mitigation: 20 s matches an
  already-accepted failsafe convention in this codebase (`PttWatchdog`); the UI's "reconnecting…"
  state (Decision 6) is explicit about what's happening rather than presenting a bare error.
- **[Risk] The parent's `ApplicationStopping` teardown (capture-pipeline stop/dispose) has no
  existing timeout — a hang there delays port release indefinitely, and the child would eventually
  give up and exit non-zero, leaving zero running instances.** → Pre-existing risk, not introduced by
  this change (the same teardown already runs on Ctrl-C/SIGTERM); out of scope to fix here, but
  flagged since restart makes a hang in that path directly user-visible for the first time (Ctrl-C
  today is typically followed by an operator watching the console, not waiting on a web UI).
- **[Risk] A malformed or unreachable relaunch command (e.g., `Environment.ProcessPath` resolving to
  something unexpected in an unusual install) would spawn a child that immediately exits, and the
  parent would still proceed to shut down** — leaving the daemon fully down with no recovery except
  physical access, the exact failure mode this change exists to close. → Mitigation: log the
  resolved relaunch command at Information before spawning (so it's diagnosable after the fact via
  the file log, which is flushed during the parent's own shutdown), and only call
  `StopApplication()` after `Process.Start` returns successfully (an immediate `Process.Start`
  failure — e.g., file not found — throws synchronously and aborts the restart *before* the parent
  begins stopping, rather than after).
- **[Trade-off] No zero-downtime handoff** — every restart is a real, if brief, outage for every
  connected client. Accepted per Non-Goals; a hot dual-process handoff is materially more complex for
  a capability whose entire purpose is an infrequent, operator-initiated action.

## Migration Plan

- Purely additive: new endpoint, new CLI flag (silently ignored by any older build, per
  `LaunchOptions`'s existing forward-compatibility note), new Settings-page action. No config schema
  change, no change to existing restart-required settings' own behaviour.
- No rollback concerns beyond a normal code revert — the feature has no persisted state of its own.

## Open Questions

- Should the restart-required notices (Decision 6) eventually generalise to *any* future
  restart-requiring setting automatically (e.g., a generic "pending restart" banner driven off a
  server-side dirty flag), rather than being hand-added next to `ptt.method` and Remote Access
  specifically? Deferred — only two such settings exist today; worth revisiting if a third appears.
- Should `POST /api/v1/system/restart` itself be logged/audited distinctly (beyond the existing
  Information-level log line) given it's a disruptive action reachable over LAN? Deferred to design
  review; no existing mutating endpoint in this codebase does anything beyond a standard log line
  today, so this would be a new precedent, not a gap specific to this change.
