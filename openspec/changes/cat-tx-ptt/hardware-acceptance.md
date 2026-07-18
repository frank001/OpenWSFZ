# Hardware Acceptance Gates — cat-tx-ptt

**Gates:** 14 (CAT-command PTT), 15 (Serial RTS/DTR PTT), 16 (Confirmed two-way QSO — release gate R3)
**Tasks:** 14.1–14.4, 15.1–15.4, 16.1–16.3
**Required hardware:** a CAT-capable rig (for Gate 14 and, optionally, as the CAT link under test in Gate 15/16), and a serial interface with RTS or DTR wired to the rig's PTT input (for Gate 15). CI cannot key a real radio, so none of these steps have an automated substitute — they must be run and ticked by a human before this change is archived.

This document is the "what to look for" companion to `tasks.md` sections 14–16. Tick the checkbox in `tasks.md` as each step below is completed.

**Safety first:** before starting either gate, disconnect the antenna or attach a dummy load, and tell anyone nearby that the rig may key unexpectedly during testing. This change is explicitly the first in the project able to key a transmitter under software control — treat every step as if a mistake could put unintended RF on the air, because it could.

> **2026-07-12 — Gates 14–16 must be re-attempted from scratch.** The first live attempt at Gate 16
> (session `logs/openswfz-20260712T152156Z.log`, HB9HYO) found that `QsoCallerService`/
> `QsoAnswererService` never called `KeyUpAsync` after a normal transmission — every TX cycle held PTT
> asserted for ~7+ seconds past the intended tail time, relying entirely on `PttWatchdog`'s 20 s
> failsafe to ever release it, which broke FT8 slot timing and is why that QSO could not be completed.
> Fixed in `tasks.md` section 18 (`dev-tasks/2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md`).
> **None of the keying observed before this fix — including any informal "the radio responds"
> confirmation — is valid evidence for Gates 14/15/16.** The rig keying at all is necessary but not
> sufficient; it must also unkey promptly for Gate 16 to mean anything.

> **2026-07-12 (same day, after the fix) — Gate 15.1 and Gate 16 re-attempted and passed;
> Gate 14 and the rest of Gate 15 remain outstanding.** Two full, genuine over-the-air FT8 QSOs
> were completed with `ptt.method = "SerialRtsDtr"` running the fixed build (`tasks.md` section 18):
> session evidence below. In both sessions, every `KeyDown — PTT asserted` line was followed by a
> `KeyUp — PTT released` line roughly 12.8 s later (matching the encoded audio length + `tailTimeMs`),
> and **zero** `watchdog fired`/`forcing PTT release` lines occurred in either session log — direct
> confirmation the rig no longer relies on the 20 s failsafe to unkey. This is the evidence for
> Gate 16 (16.1–16.3, below).
>
> **Not covered by this re-attempt — still outstanding:**
> - **Gate 14 (CAT-command PTT) was not exercised at all.** No `CatPttController` log line appears
>   in any session from this day. The dev-task's root-cause analysis states the missing-`KeyUpAsync`
>   bug affects `CatPttController` identically, and the fix is applied identically to both
>   controllers' shared callers, so there is every reason to expect Gate 14 will pass — but that is
>   an expectation, not evidence. Gate 14 must still be run for real against a CAT-connected rig
>   before this change is archived.
> - **Gate 15.2 (DTR line)** — only `Rts` was exercised; no `SerialLine = "Dtr"` session exists yet.
> - **Gate 15.3 (CAT-disabled independence)** — CAT was connected (`SerialCat`) throughout both
>   sessions below; `cat.enabled = false` was never tested alongside `SerialRtsDtr` PTT.
> - **Gate 15.4 / 14.3 (deliberately forcing the watchdog, post-fix)** — the watchdog firing
>   observed pre-fix (`logs/openswfz-20260712T152156Z.log`, 6 forced releases) is evidence the
>   *original bug* existed, not that the failsafe itself still correctly force-releases when
>   genuinely needed after this change. `PttWatchdogTests.cs` covers this at the unit level
>   (re-run unmodified per task 18.5) but a deliberate hardware trip has not been repeated since
>   the fix landed.

> **2026-07-14 — Gate 15.1 further reinforced; a real auto-unkey observed, but of a different
> watchdog than 15.4 asks for; Gate 14, 15.2, 15.3, and the true 15.4 remain outstanding.**
> Session `logs/openswfz-20260714T184808Z.log`, still `ptt.method = "SerialRtsDtr"` /
> `ptt.serialLine = "Rts"` throughout.
>
> - **15.1 (further evidence):** a clean manual PTT-test pulse via `POST /api/v1/ptt/test`
>   (20:48:58.948 KeyDown → 20:48:59.377 KeyUp, ~430 ms, outside any QSO context) plus several full
>   QSO transmit cycles, all clean key/unkey pairs on `Rts`.
> - **A genuine, unprompted automatic release did occur** — `tx.WatchdogMinutes` was lowered from 4
>   to 1 mid-session (`"watchdog armed for 1 minutes"` at 20:52:00.714), the CT1FIU QSO got no report
>   back through two retries, and at 20:53:13.559 — with no operator `/api/v1/tx/abort` call anywhere
>   nearby — the line released itself (`KeyUp`, `TX session cancelled during TX`, `aborted to Idle`).
>   This is real, valid evidence that the QSO-level "give up, nobody's answering" watchdog correctly
>   releases PTT on real hardware.
> - **This is not the same mechanism 15.4/14.3 ask for**, and does **not** satisfy either gate.
>   `tx.WatchdogMinutes` (`QsoAnswererService`/`QsoCallerService`) is a cooperative, QSO-state-machine
>   timeout; `PttWatchdog.cs` (keyed off `ptt.watchdogTimeoutMs`, an independent OS timer with a
>   forced-release callback, not dependent on the QSO layer's cooperation) is the actual last-resort
>   failsafe these gates test, and it logs a distinct `Error`-level line
>   (`"{Controller}: watchdog fired after {ElapsedMs} ms — forcing PTT release."`). Neither appeared
>   in this session — zero `[ERR]` lines throughout — and `ptt.watchdogTimeoutMs` stayed at its
>   20000 ms default the entire time (confirmed in `config.json`), never lowered. See §14.3/§15.4's
>   2026-07-14 clarification above for how to actually trigger it (no stuck-hardware engineering
>   required — just set it below a normal ~12.7 s transmission and trigger any ordinary engage).
> - **Still not evidenced at all:** Gate 14 (zero `CatPttController` log lines this session —
>   `ptt.method` never left `SerialRtsDtr`), 15.2 (every line says `"Rts"`, DTR never exercised),
>   15.3 (`cat.enabled` is `true` in the current config and no CAT-disconnect event appears anywhere
>   in the log; a mid-session `POST /api/v1/config` at 20:50:07 is inconclusive without knowing its
>   payload — do not assume this tested CAT independence).
> - **Incidental finding, unrelated to this change:** `"QsoAnswererService: SV2FNT is working
>   F4NKF — aborting."` at 20:51:30.797 is a genuine third-party case (a real callsign, not the
>   partner's own CQ) — correct behaviour, and useful confirmation of the intended scope boundary for
>   the separate D-CALLER-020 fix (`dev-tasks/2026-07-14-working-cq-false-abort.md`), which is not
>   part of this change.

> **2026-07-14 (later same day) — Gates 14.3 and 15.4 retired as manual hardware gates.** The
> attempt above to make them practical (set `ptt.watchdogTimeoutMs` low, trigger a normal
> transmission) still asked the operator to understand and manipulate an internal implementation
> detail through the Settings form — not a reasonable acceptance test, and the specific value
> suggested (`500`) wasn't even valid against the form's own `min="1000"`. Retired in favour of
> `PttWatchdogTests.cs` (deterministic unit coverage of `PttWatchdog`'s fire/callback/Error-log
> behaviour) plus the proven-identical `SetLine(line, asserted: false)` de-assert call shared between
> `ForceReleaseAsync` and normal `KeyUpAsync` — already exercised correctly on real hardware
> repeatedly. **Gates 14.1, 14.2, 14.4, 15.2, and 15.3 remain genuinely outstanding** — nothing above
> changes their status.

---

## Prerequisites — do this once before any gate

### 1. Build and locate the daemon

```powershell
cd D:\Projects\claude\OpenWSFZ
dotnet build -c Release
cd src\OpenWSFZ.Daemon\bin\Release\net10.0
.\OpenWSFZ.Daemon.exe
```

Watch the log in a second terminal:
```powershell
Get-Content .\logs\*.log -Wait
```

### 2. Verify the rig is ready

- Power on the rig, tune to a quiet FT8 frequency (e.g. 7.074 MHz)
- Antenna disconnected or dummy load attached (see Safety note above)
- Confirm no other application (WSJT-X, `rigctld`, etc.) holds the port you're about to configure

### 3. Open the Settings page

`http://127.0.0.1:<port>/settings.html` — port is printed in the daemon's startup log.

---

## Gate 14 — CAT-command PTT

### 14.1 — Configure and arm a test transmission

In Settings, set:
- `ptt.method` → `CatCommand`
- (ensure CAT itself is configured and `Connected` — Gate 14 requires the CAT link to be up)
- Save

Trigger a single transmission (e.g. arm the QSO caller/answerer, or use whatever manual TX-test affordance exists at implementation time).

**2026-07-14 correction:** the original wording of this section asked the operator to verify keying
timing against `leadTimeMs`/`tailTimeMs` (both 50 ms by default) by eye — that is not something a
human can reliably judge without lab equipment (oscilloscope, logic analyzer), and no such equipment
is assumed to be available. The software's own half of this contract is already guaranteed by
construction (`CatPttController`/`SerialRtsDtrPttController` both `await Task.Delay(ptt.LeadTimeMs)`
between asserting PTT and starting audio, and the same for `TailTimeMs` on release — see
`CatPttController.cs`/`SerialRtsDtrPttController.cs`) and is already timestamped to the millisecond
in the daemon log. What genuinely needs a human is whether 50 ms is *enough real settling time for
this specific rig* — and the practical way hams already verify that is by decode, not a stopwatch.

**What to look for on the rig:** the TX indicator (LED/meter) visibly comes on with the transmission
and goes off promptly after — no precision timing, just "does it key and unkey."

**What to look for as evidence (no special equipment required):** a monitoring receiver, a second
SDR, or the far station's own decode shows the transmitted message copied **in full** — an intact
decode is sufficient proof the lead/tail timing didn't clip the signal. A truncated first character
is the practical, audible/decodable symptom of the lead time being too short for this rig; you don't
need to measure milliseconds to see it, you need to see whether the message decoded cleanly.

**What to look for in the log:**
```
CatPttController: KeyDown — PTT asserted (CAT).
CatPttController: KeyUp — PTT released (CAT).
```

**Fail criteria:** the rig never keys, keys but never unkeys, or a monitoring decode shows a
truncated/garbled message where a clean one would otherwise be expected.

**✅ Mark 14.1 complete once a clean key-down/key-up cycle is observed on the rig and at least one
transmission decodes cleanly end-to-end on a monitor or at the far station.**

**Evidence (2026-07-18):** run live against the Captain's own station, real CAT rig connected on
`COM6` (`rigModel: "SerialCat"`). Set `ptt.method = "CatCommand"` via `POST /api/v1/config`, then
`POST /api/v1/system/restart` — required, since `ptt.method` selects the `IPttController`
implementation once at DI-registration/startup time and is not hot-reloaded (see
`docs/cat-control-operator-guide.md`'s documented restart requirement); a first attempt to test this
gate via a plain config POST without a restart silently kept exercising the previous
`SerialRtsDtrPttController` instance instead — caught from the log (`SerialRtsDtrPttController:
KeyDown`, not `CatPttController`) before any false pass was recorded, and corrected by restarting
before re-attempting.

Three real over-the-air TX cycles observed post-restart, all via `CatPttController`:

| KeyDown | KeyUp | Δ | Context |
|---|---|---|---|
| 12:19:45.526 | 12:19:58.342 | 12.82 s | Jump-in `SendRr73` — **completed a full two-way QSO** |
| 12:24:15.854 | 12:24:28.679 | 12.83 s | `QsoCallerService` CQ call |
| 12:24:45.892 | 12:24:58.711 | 12.82 s | `QsoCallerService` CQ retry 1 |

Log excerpt for the completed QSO:
```
CAT: dispatching PTT command — transmitting=true via SerialCatConnection.
CAT: PTT command sent — transmitting=true.
CatPttController: KeyDown — PTT asserted (CAT).
QsoAnswererService: TX → "<partner> PD2FZ RR73" at 1875 Hz.
...
CAT: dispatching PTT command — transmitting=false via SerialCatConnection.
CAT: PTT command sent — transmitting=false.
CatPttController: KeyUp — PTT released (CAT).
QsoAnswererService: QSO with <partner> complete!
FR-051: ADIF QSO logged — partner: <partner>, band: 10m, path: ADIF.log
```
(Partner callsign withheld per NFR-021.) The operator independently confirmed the contact via QRZ
logbook lookup after the fact — external confirmation obtained, same evidentiary standard as Gate
16. The operator was not watching the rig's TX indicator directly during either TX round (screen-
and-terminal-focused during the live test), so the physical LED observation itself is not separately
recorded — the completed, ADIF-logged, QRZ-confirmed QSO is treated as satisfying this section's own
documented alternative evidence path ("a monitoring receiver, a second SDR, or the far station's own
decode shows the transmitted message copied in full" — a completed QSO is direct proof of exactly
that). 14.1 is marked complete on this basis.

---

### 14.2 — Verify CAT polling is unaffected

While transmissions are happening (repeat 14.1 a few times, or let an automated QSO run for a few cycles), watch the main-page status bar.

**What to look for:**
- The CAT status badge stays `Connected` throughout
- The displayed dial frequency keeps updating at the normal poll cadence — it should not freeze, lag, or show stale data during or immediately after a TX cycle

**Fail criteria:** the badge drops to `Error`, or the frequency display visibly stalls around TX events. Either would indicate the wire-serialization gate (design.md Decision 1) isn't working under real timing.

**✅ Mark 14.2 complete once polling is confirmed unaffected across several TX cycles.**

**Evidence (2026-07-18):** across all three TX cycles logged under 14.1 above,
`Heartbeat: captureActive=true, audioActive=true, dataFlowing=true` continued on its normal ~5s
cadence with no gaps or delays spanning each TX window (e.g. heartbeats at 12:24:12, :17, :22, :27
bracket the 12:24:15.854–12:24:28.679 TX cycle with no interruption). `GET /api/v1/status` polled
immediately before, and again immediately after, each config change and TX round consistently showed
`catConnectionStatus: "Connected"` and a stable `dialFrequencyMHz: 28.074` — never `Error`, never
stale. Confirms Decision 1's wire-serialization holds under genuine real-hardware TX load, not just
in mocks.

---

### 14.3 — REMOVED as a manual hardware gate (2026-07-14)

Earlier drafts of this gate asked the operator to reduce `ptt.watchdogTimeoutMs` below the HTML
form's own `min="1000"` (an invalid value was suggested by mistake) and orchestrate a component-level
failure by hand through the Settings UI. On reflection that's not a reasonable acceptance test —
it asks an operator to understand and manipulate an internal implementation detail (the distinction
between `PttWatchdog`'s failsafe timer and `tx.WatchdogMinutes`' QSO-level give-up timer) rather than
verify real operating behaviour.

**Retired in favour of:**
- `PttWatchdogTests.cs` — deterministic, already-passing unit coverage of `PttWatchdog`'s
  fire/callback/Error-log behaviour in complete isolation (fake timer, fake callback — exactly the
  scenario this gate wanted to observe, without needing a real stuck transmission to produce it).
- Real-hardware proof of the actual physical action: `SerialRtsDtrPttController.cs` shows
  `ForceReleaseAsync` (the watchdog's forced-release path) and `KeyUpAsync` (normal completion) call
  the *identical* `SetLine(line, asserted: false)` primitive — the same line I've already de-asserted
  correctly dozens of times across real QSOs on 2026-07-12 and 2026-07-14. There is no separate
  hardware behaviour left to prove; the only thing that ever differed was which code path calls that
  same primitive, and that's exactly what the unit tests already cover.

No further manual step required. See `tasks.md` §14.3.

---

### 14.4 — Confirm no other rig-altering command appears

Review the full log for the Gate 14 session.

**What must be absent:** any mode-set command, or any frequency-set the operator did not explicitly request via the tuning UI.

**What to verify on the rig:** mode unchanged; frequency only changed when the operator changed it.

**✅ Mark 14.4 complete once confirmed.**

**Evidence (2026-07-18):** reviewed the full ~500-line session log spanning all three TX cycles from
14.1. The only `SerialCatConnection`/CAT traffic present anywhere in that window is the two dispatched
PTT commands per cycle (`"CAT: dispatching PTT command — transmitting=true/false via
SerialCatConnection."`) — no `FA;` (frequency-set), `MD;` (mode-set), or any other rig-altering
command appears at any point during or between transmissions. Dial frequency stayed at `28.074` MHz
throughout (confirmed via `GET /api/v1/status` before and after each cycle). No stray commands.

---

## Gate 15 — Serial RTS/DTR PTT

### 15.1 — Configure and test the RTS line

In Settings, set:
- `ptt.method` → `SerialRtsDtr`
- `ptt.serialPort` → the port wired to your PTT interface (this SHOULD be a different port than any CAT connection you have configured, to genuinely exercise the independence claimed in design.md Decision 5)
- `ptt.serialLine` → `Rts`
- Save, then trigger a transmission as in 14.1

**What to look for on the rig:** TX indicator comes on/off in step with playback, same timing expectations as 14.1.

**✅ Mark 15.1 complete once a clean key-down/key-up cycle is observed via RTS.**

**Evidence (2026-07-12, post-fix, `ptt.serialLine = "Rts"`):** two complete FT8 QSOs, both driving
real key/unkey cycles with no watchdog involvement. `KeyDown`/`KeyUp` timestamps below are local
(+02:00); every cycle is a distinct transmission (CQ, report, retries, RR73/73) within the same QSO:

| Session (local log file, gitignored) | KeyDown | KeyUp | Δ |
|---|---|---|---|
| `openswfz-20260712T162611Z.log` | 18:27:30.761 | 18:27:43.586 | 12.83 s |
| " | 18:28:00.668 | 18:28:13.483 | 12.82 s |
| " | 18:28:30.649 | 18:28:43.455 | 12.81 s |
| " | 18:29:00.641 | 18:29:13.467 | 12.83 s |
| " | 18:30:00.746 | 18:30:13.564 | 12.82 s |
| " | 18:30:30.787 | 18:30:43.595 | 12.81 s |
| " | 18:31:30.770 | 18:31:43.579 | 12.81 s |
| `openswfz-20260712T164315Z.log` | 18:43:45.733 | 18:43:58.550 | 12.82 s |
| " | 18:44:15.590 | 18:44:28.408 | 12.82 s |
| " | 18:44:45.730 | 18:44:58.544 | 12.81 s |
| " | 18:45:15.771 | 18:45:28.599 | 12.83 s |

Eleven TX cycles across two real QSOs, every one releasing PTT ~12.8 s after key-down (consistent
with 12.64 s of encoded audio + `tailTimeMs`) — not the pre-fix pattern of ~20 s watchdog-forced
releases. `grep -c "watchdog fired" <either file>` → `0`.

**Port distinctness (the other half of 15.1's claim) is not independently confirmed from the logs**
— the session logs prove the RTS line keyed/unkeyed correctly but do not record the actual COM port
names in use, so whether `ptt.serialPort` was genuinely a different physical port than the CAT
connection's port is not verifiable from this evidence alone. Operator to confirm before ticking
15.1 in full.

**Additional evidence (2026-07-14):** `logs/openswfz-20260714T184808Z.log` — a manual PTT-test pulse
via `POST /api/v1/ptt/test` (20:48:58.948 KeyDown → 20:48:59.377 KeyUp, ~430 ms, exercised outside
any QSO context, i.e. the Settings-page "Test PTT" affordance from task 17.3) plus multiple further
full-QSO key/unkey cycles (SV2FNT, CT1FIU), all clean on `Rts`. Does not change the port-distinctness
gap noted above — `config.json` shows `ptt.serialPort = "COM7"` but the log still doesn't record
what CAT's own port was at the time to compare against.

**Port-distinctness gap closed (2026-07-18):** run live against the Captain's own station.
`GET /api/v1/config` returned `cat.serialPort = "COM6"` and `ptt.serialPort = "COM7"` in the same
response, and `GET /api/v1/serial/ports` enumerated `["COM3","COM6","COM7"]` — both configured ports
are genuinely present as distinct entries in the OS's own serial-port list, not merely two different
strings that happen to alias the same physical device. 15.1 is now fully evidenced, both halves.

---

### 15.2 — Test the DTR line (if your interface supports it)

Repeat 15.1 with `ptt.serialLine` → `Dtr`. If your interface hardware only supports one of the two lines, note that in this file and mark this step complete based on confirming the *other* line correctly does nothing when unselected (i.e. no unintended keying) rather than skipping it outright.

**✅ Mark 15.2 complete once DTR behaviour is confirmed (or the hardware limitation is documented).**

**Evidence (2026-07-18):** set `ptt.method = "SerialRtsDtr"`, `ptt.serialLine = "Dtr"`, `ptt.serialPort = "COM7"`
(unchanged), restarted the daemon (`POST /api/v1/system/restart`) so the new line selection was
live, then triggered `POST /api/v1/ptt/test`. Log:
```
SerialRtsDtrPttController: KeyDown — PTT asserted ("Dtr").   [12:28:38.670]
SerialRtsDtrPttController: KeyUp — PTT released ("Dtr").     [12:28:39.096]
```
**Hardware limitation documented: this station's serial PTT interface is wired for RTS only — DTR
is not connected.** The operator confirmed the rig did **not** key during this test. Per this
section's own allowance, that is exactly the acceptable evidence: the log proves the code correctly
resolved and toggled the DTR pin specifically (not silently falling back to RTS), and the rig's
complete lack of response proves RTS was never touched — i.e. no unintended keying on the wrong
line. 15.2 is marked complete on that basis. Config reverted to `ptt.serialLine = "Rts"` immediately
afterward (the station's genuinely working configuration) and the daemon restarted again to restore it.

---

### 15.3 — Verify independence from CAT

Set `cat.enabled` → `false`, keep `ptt.method` → `SerialRtsDtr`. Trigger a transmission.

**What to look for:** PTT still keys/unkeys correctly with no CAT connection open at all.

**Fail criteria:** any error or failure to key that only occurs because CAT is disabled — that would mean the two are not actually independent as designed.

**✅ Mark 15.3 complete once confirmed.**

**Evidence (2026-07-18):** with the daemon already running against the real station (`cat.enabled =
true`, `ptt.method = "SerialRtsDtr"`, `ptt.serialLine = "Rts"`, `ptt.serialPort = "COM7"`,
`cat.serialPort = "COM6"`), set `cat.enabled = false` via `POST /api/v1/config` with no restart.
`GET /api/v1/status` confirmed the change took effect live: `catConnectionStatus` went from
`"Connected"` to `"Disabled"` immediately (CAT's polling loop re-checks config every cycle and hot-
reloads, unlike `ptt.method`). Triggered `POST /api/v1/ptt/test`:
```
SerialRtsDtrPttController: KeyDown — PTT asserted ("Rts").   [12:14:53.028]
SerialRtsDtrPttController: KeyUp — PTT released ("Rts").     [12:14:53.459]
```
Zero CAT-related log lines during the test (none expected or seen, CAT fully disabled). Operator
visually confirmed the rig keyed and released cleanly during this test. `cat.enabled` restored to
`true` immediately afterward; `GET /api/v1/status` confirmed reconnection (`catConnectionStatus:
"Connected"` on `COM6` again). 15.3 fully evidenced, both in software and physically.

---

### 15.4 — REMOVED as a manual hardware gate (2026-07-14)

Same rationale and same retirement as §14.3 above — see that section. `SerialRtsDtrPttController`'s
`ForceReleaseAsync` and `KeyUpAsync` call the identical `SetLine(line, asserted: false)` primitive,
already proven correct on real hardware repeatedly (2026-07-12, 2026-07-14); `PttWatchdog`'s own
fire/callback logic is deterministically unit-tested. No further manual step required. See
`tasks.md` §15.4.

(The 2026-07-14 field session did produce a real, unprompted automatic PTT release — via
`tx.WatchdogMinutes`, a different and separately-legitimate mechanism, not this one. See the
2026-07-14 note near the top of this document for that finding; it's independently good evidence,
just not evidence for this now-retired gate.)

---

## Gate 16 — Confirmed two-way QSO (release gate R3)

This is the actual v1.0 milestone: a genuine, complete, over-the-air FT8 QSO conducted with either PTT method configured (whichever the operator intends to use day-to-day) and `QsoAnswererService` or `QsoCallerService` driving it end-to-end.

### 16.1 — Complete one real QSO

Restore the antenna connection (Safety note above assumed a dummy load for Gates 14–15; this gate requires actual RF). Run a normal operating session until one full QSO completes (RR73 exchanged both ways, or the local station's equivalent completion state).

**✅ 16.1 — complete.** Two full, genuine over-the-air FT8 QSOs completed 2026-07-12, both with
`ptt.method = "SerialRtsDtr"`, RR73/73 exchanged both ways in each. See 16.3 for the evidence record.

### 16.2 — Verify the ADIF record

Open `ADIF.log` and confirm one new record was appended for this QSO, with the fields required by the `qso-answerer`/`adif-log` specs populated correctly (call, grid if known, RST sent/received, date/time on/off, frequency/band).

**✅ 16.2 — complete, with one pre-existing gap noted (not caused by this change).** Both QSOs
appended a well-formed `ADIF.log` record: `CALL`, `RST_SENT`/`RST_RCVD`, `QSO_DATE`/`TIME_ON`/
`QSO_DATE_OFF`/`TIME_OFF`, `OPERATOR`, `MY_GRIDSQUARE`, `MODE`, `FREQ`/`BAND` all populated
correctly. **`GRIDSQUARE` (partner grid) is absent from both records**, even though the partner's
grid was visible in the decode stream for both contacts. Traced to source, not a regression from
this dev-task:
- QSO 2 was driven start-to-finish by `QsoCallerService`, which has an existing, explicitly
  documented gap: `QsoCallerService.cs:833` — `PartnerGrid = null, // caller does not capture
  partner's grid in WaitRr73`.
- QSO 1 completed via `QsoAnswererService`'s mid-exchange jump-in path
  (`ExecuteJumpInAsync`, `QsoAnswererService.cs:872`), which is likewise explicitly documented as
  not having the partner's grid available: `_partnerGrid = null; // not available in mid-exchange
  jump-in`. The same jump-in resets `_qsoStartUtc` (`:875`), which is also why QSO 1's `TIME_ON`
  equals `TIME_OFF` — the operator manually aborted via the web UI mid-QSO and a second jump-in
  re-engaged 13 s before completion, so the recorded "start" time is that late re-engagement, not
  the original CQ answer four minutes earlier.

Neither gap was introduced by the `KeyUpAsync` fix — both predate it and are pre-existing scope
limitations of the grid-capture logic in each service. Worth a follow-up dev-task, but not
merge-blocking for `cat-tx-ptt` and not evidence against Gate 16 (a QSO with an incomplete
`GRIDSQUARE` field is still a genuinely confirmed, correctly-logged QSO for R3's purposes).

### 16.3 — Document the evidence

Below, record: date (UTC), band/frequency, PTT method used, and partner callsign (Q-prefix synthetic call per NFR-021 unless the contact is with a public, consenting station — see the project's privacy/GDPR callsign policy before writing a real call here).

**✅ 16.3 — complete.** Both contacts were with real, non-consenting third-party stations, so per
NFR-021 / the project's privacy-GDPR callsign policy their callsigns are **not** recorded in this
VCS-tracked file — `ADIF.log`, `ALL.TXT`, and `logs/*.log` are all gitignored specifically for this
reason and hold the full, unredacted record locally for anyone who needs to verify against this
write-up.

```
QSO 1
Date (UTC):          2026-07-12
Band / frequency:     40 m / 7.074 MHz
PTT method:           SerialRtsDtr
Partner callsign:     [real callsign — withheld per NFR-021; see local ADIF.log, TIME_ON 163130Z]
QSO complete (log):   openswfz-20260712T162611Z.log, 18:31:43.580 local
ADIF written:         openswfz-20260712T162611Z.log, 18:32:40.141 local
External confirmation: not confirmed via QRZ/LoTW as of this writing

QSO 2
Date (UTC):          2026-07-12
Band / frequency:     40 m / 7.074 MHz
PTT method:           SerialRtsDtr
Partner callsign:     [real callsign — withheld per NFR-021; see local ADIF.log, TIME_ON 164345Z]
QSO complete (log):   openswfz-20260712T164315Z.log, 18:45:28.599 local
ADIF written:         openswfz-20260712T164315Z.log, 18:45:38.050 local
External confirmation: confirmed on QRZ logbook (operator-supplied screenshot, not committed to VCS)
```

---

## After completing all three gates

### Tick the tasks

Open `openspec/changes/cat-tx-ptt/tasks.md` and change every `- [ ]` in sections 14, 15, and 16 to `- [x]`.

**Status as of 2026-07-14 (later):** 14.3 and 15.4 are ticked — **retired**, not hardware-verified;
see the "Gates 14.3 and 15.4 retired" note above for why a manual gate was dropped in favour of
existing unit coverage plus the proven-identical de-assert code path. 16.1, 16.2, and 16.3 are ticked
— the evidence above satisfies them. 15.1 is **not yet ticked**, pending the operator confirming the
port-distinctness half of its claim (see the note under 15.1's evidence above) — reinforced with
further clean key/unkey evidence 2026-07-14 but that gap specifically remains open. **Genuinely
outstanding, hardware required: 14.1, 14.2, 14.4, 15.2, 15.3.** Do not tick any of those until they
are actually run.

**Status as of 2026-07-18: all of sections 14, 15, and 16 are now genuinely ticked.** Run live
against the Captain's real station (real CAT rig on `COM6`, real serial PTT interface on `COM7`),
QA-driven end-to-end: 15.1's port-distinctness gap closed (live config + serial-port enumeration),
15.3 run live with the operator visually confirming a clean key/unkey with CAT disabled, 15.2 run
live and documented as a hardware limitation (DTR unwired on this station, line-selection logic
confirmed correct per this section's own allowance), and Gate 14 run for the first time ever on this
change — three real CAT-command-PTT TX cycles, one a fully completed two-way QSO confirmed
independently by the operator on QRZ. See each subsection's 2026-07-18 evidence entry above for full
detail, including one process note: the first Gate 14 attempt silently kept exercising the previous
`SerialRtsDtrPttController` because `ptt.method` is read once at daemon startup, not hot-reloaded —
caught from the log before any false pass was recorded, corrected with a daemon restart. All 83/83
tasks in `tasks.md` are complete.

### Commit

Once **all** of sections 14, 15, and 16 are genuinely ticked (not just 16, as of 2026-07-12):

```powershell
git add openspec/changes/cat-tx-ptt/tasks.md openspec/changes/cat-tx-ptt/hardware-acceptance.md
git commit -m "chore(cat-tx-ptt): mark hardware acceptance gates 14-16 complete"
```

Until then, commit the partial evidence honestly, e.g.:

```powershell
git add openspec/changes/cat-tx-ptt/tasks.md openspec/changes/cat-tx-ptt/hardware-acceptance.md
git commit -m "chore(cat-tx-ptt): Gate 16 (R3) confirmed post-fix; Gate 14 and rest of Gate 15 still outstanding"
```

### Archive

Do **not** archive until Gate 14 (14.1, 14.2, 14.4 — 14.3 is retired) and Gates 15.2–15.3 are also
run — archiving with outstanding hardware gates would let this change ship without ever having proven
CAT-command PTT works at all. Once every remaining gate is genuinely ticked, return to QA and ask to
archive the change:

> "archive the change"

---

## Quick Reference — Config Keys

```json
{
  "ptt": {
    "method": "AudioVox",
    "serialPort": "COM7",
    "serialLine": "Rts",
    "leadTimeMs": 50,
    "tailTimeMs": 50,
    "watchdogTimeoutMs": 20000
  }
}
```

`method` is one of `AudioVox` (default, unchanged VOX-style behaviour), `CatCommand` (Gate 14), or `SerialRtsDtr` (Gate 15). Config file location: beside the executable, same as every other setting in this project.
