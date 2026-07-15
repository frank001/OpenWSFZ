## Why

Two settings already shipped this year — `ptt.method` (`cat-tx-ptt`) and `RemoteAccess.Enabled`/bind
address (`lan-remote-access`) — only take effect after a full daemon restart, and today the *only*
way to restart the daemon is physical/console access to the machine it runs on. That is a direct
contradiction of the LAN remote-access capability's own premise (an operator managing the box from
another device on the network) and was confirmed today as the root cause of a real field incident:
an operator saved `ptt.method = SerialRtsDtr` from a remote browser, the config persisted correctly,
but the already-running process kept using its stale, previously-selected `IPttController` — the
rig never keyed, and there was no way to apply the fix without walking over to the machine. This
requirement was first raised during `f-004-operator-visibility-improvements` (archived 2026-07-05)
and explicitly parked as a non-goal at the time; it is no longer hypothetical.

## What Changes

- Add a `POST /api/v1/system/restart` endpoint that restarts the daemon process in place: it spawns
  a fresh detached copy of itself (same executable path and CLI arguments, resolved from
  `AppContext.BaseDirectory` / `Environment.GetCommandLineArgs()`), then gracefully stops the current
  instance so the new process can bind the listening port. This is a **self re-exec**, not a request
  to an external supervisor — v1 has no Windows Service/systemd unit watching this process
  (`TECHNICAL_SPEC.md` NFR-009 is not implemented yet), so nothing else would bring it back up.
- The endpoint refuses with HTTP 409 while `IQsoController.Keying` is `true` (a real QSO is
  transmitting), mirroring the existing `/api/v1/ptt/test` guard — restart never interrupts an
  in-flight over-the-air transmission; the operator must wait for it to finish or abort it first.
- Add a "Restart Daemon" action to the Settings page (Advanced tab), gated behind an explicit
  confirmation dialog (unlike this page's other, non-destructive actions) because it drops the
  WebSocket, interrupts the current decode cycle, and briefly takes the whole UI offline.
- Add restart-required notices next to the two settings that need it today (PTT Config's
  `ptt.method`, Remote Access's bind-address controls), each linking/pointing at the new action,
  reusing the existing "restart notice" UI pattern already shown for Remote Access changes.
- The frontend polls `GET /api/v1/status` after triggering a restart and shows a "reconnecting…"
  state until the new process answers, rather than surfacing the brief unavailability window as an
  error.
- No change to `IAuthPolicy`/`IBindPolicy` behaviour: the new endpoint is just another `/api/*` path
  and is already covered by the existing blanket passphrase-auth middleware (`specs/remote-access`,
  `specs/web-server`) — confirmed by inspection, not modified by this change.

## Capabilities

### New Capabilities
- `remote-daemon-restart`: the restart API endpoint, the self re-exec process-relaunch mechanism,
  the in-flight-transmission safety gate, and the port hand-off sequencing between the old and new
  process instances.

### Modified Capabilities
- `daemon-host`: the shutdown sequence gains a second trigger (an API-initiated restart) distinct
  from SIGINT/SIGTERM, and startup gains the "am I a self-relaunched instance" hand-off with the
  process that spawned me.
- `web-frontend`: Settings page gains the Restart Daemon action (with confirmation dialog),
  restart-required notices on `ptt.method` and Remote Access controls that link to it, and a
  reconnect-polling UX for the brief restart window.

## Impact

- **Affected code**: `src/OpenWSFZ.Daemon/Program.cs` (startup self-relaunch detection, graceful
  shutdown sequencing), a new `src/OpenWSFZ.Daemon/DaemonRestartService.cs`-style component wired
  into `WebApp.cs` alongside the existing `IQsoController`/`IPttController` service captures, and
  `web/settings.html` / `web/js/settings.js` for the new Advanced-tab action and notices.
- **Not affected**: `IAuthPolicy`, `IBindPolicy`, `IPttController` implementations, `PttConfig`,
  `RemoteAccessConfig` — this change adds a way to *apply* their restart-dependent settings, it does
  not change what those settings do.
- **Explicitly out of scope**: PTT-method hot-reloading (considered and dropped — once remote
  restart exists, "Save, click Restart" solves the same friction without the mid-transmission
  controller-handoff safety engineering hot-reload would require); full NFR-009 Windows-service /
  systemd-unit deployment support (separate, larger, already-tracked future item); the pre-existing,
  separate defect where the Settings-page PTT Test button's availability gate reads persisted config
  rather than the actually-registered controller kind (real, already diagnosed, but a distinct bug
  fix).
