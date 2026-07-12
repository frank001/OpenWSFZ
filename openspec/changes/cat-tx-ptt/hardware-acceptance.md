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

**What to look for on the rig:**
- The TX indicator (LED / meter) comes on within roughly `leadTimeMs` (default 50 ms) of the daemon logging that it has asserted PTT — this will look instantaneous to the eye but should not visibly lag by more than a couple of hundred milliseconds
- The rig unkeys within roughly `tailTimeMs` (default 50 ms) of audio playback ending

**What to look for in the log:**
```
CatPttController: KeyDown — PTT asserted (CAT).
CatPttController: KeyUp — PTT released (CAT).
```

**Fail criteria:** the rig never keys, keys but never unkeys, or keys noticeably later/earlier than the audio.

**✅ Mark 14.1 complete once a clean key-down/key-up cycle is observed on the rig.**

---

### 14.2 — Verify CAT polling is unaffected

While transmissions are happening (repeat 14.1 a few times, or let an automated QSO run for a few cycles), watch the main-page status bar.

**What to look for:**
- The CAT status badge stays `Connected` throughout
- The displayed dial frequency keeps updating at the normal poll cadence — it should not freeze, lag, or show stale data during or immediately after a TX cycle

**Fail criteria:** the badge drops to `Error`, or the frequency display visibly stalls around TX events. Either would indicate the wire-serialization gate (design.md Decision 1) isn't working under real timing.

**✅ Mark 14.2 complete once polling is confirmed unaffected across several TX cycles.**

---

### 14.3 — Force the watchdog and confirm automatic unkey

Temporarily set `ptt.watchdogTimeoutMs` to a small value (e.g. `500`) and arrange for a transmission where playback cannot complete before that (a short pre-encoded buffer, or a deliberately induced delay, whatever the implementation's test seam supports) — the intent is a key-down that would otherwise remain asserted well past a real 12.64 s transmission.

**What to look for on the rig:** it unkeys on its own, without any `KeyUpAsync` ever being called normally.

**What to look for in the log:**
```
CatPttController: watchdog fired after <elapsed> ms — forcing PTT release.
```
logged at Error.

Restore `watchdogTimeoutMs` to its normal value afterward.

**✅ Mark 14.3 complete once the watchdog is confirmed to unkey the rig on its own.**

---

### 14.4 — Confirm no other rig-altering command appears

Review the full log for the Gate 14 session.

**What must be absent:** any mode-set command, or any frequency-set the operator did not explicitly request via the tuning UI.

**What to verify on the rig:** mode unchanged; frequency only changed when the operator changed it.

**✅ Mark 14.4 complete once confirmed.**

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

---

### 15.2 — Test the DTR line (if your interface supports it)

Repeat 15.1 with `ptt.serialLine` → `Dtr`. If your interface hardware only supports one of the two lines, note that in this file and mark this step complete based on confirming the *other* line correctly does nothing when unselected (i.e. no unintended keying) rather than skipping it outright.

**✅ Mark 15.2 complete once DTR behaviour is confirmed (or the hardware limitation is documented).**

---

### 15.3 — Verify independence from CAT

Set `cat.enabled` → `false`, keep `ptt.method` → `SerialRtsDtr`. Trigger a transmission.

**What to look for:** PTT still keys/unkeys correctly with no CAT connection open at all.

**Fail criteria:** any error or failure to key that only occurs because CAT is disabled — that would mean the two are not actually independent as designed.

**✅ Mark 15.3 complete once confirmed.**

---

### 15.4 — Force the watchdog (RTS/DTR)

Same procedure as 14.3, but with `ptt.method = "SerialRtsDtr"`. Confirm the line de-asserts automatically and the same Error-level log line (naming the serial controller) appears.

**✅ Mark 15.4 complete once confirmed.**

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

**Status as of 2026-07-12:** 16.1, 16.2, and 16.3 are ticked — the evidence above satisfies them.
15.1 is **not yet ticked**, pending the operator confirming the port-distinctness half of its claim
(see the note under 15.1's evidence above). 14.1–14.4, 15.2, 15.3, and 15.4 remain unticked and
genuinely untested on hardware — do not tick any of these until they are actually run.

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

Do **not** archive until Gate 14 and Gates 15.2–15.4 are also run — archiving with outstanding
hardware gates would let this change ship without ever having proven CAT-command PTT works at all.
Once every gate is genuinely ticked, return to QA and ask to archive the change:

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
