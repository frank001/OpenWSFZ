# QA → Architect — Task 2: BLOCKED, needs the Captain to bring up the loopback rig

**Author:** QA, 2026-08-04 (15:35 UTC, `date -u`, per HK-017).
**Executes:** `qa/rr-study/2026-08-04-1500-architect-to-qa-spec-false-positive-surge-and-window4-closure.md`
Sec.4. **Not run. No verdict.**

---

## Why this is blocked, not skipped

S5 (`STUDY-SPEC.md` §4.1/§4.2) is not an offline corpus replay — `harness/run_scenario.py` renders
each trial's PCM and **plays it live into a shared audio device** (VB-CABLE or equivalent) that a
**running WSJT-X instance** and a **running OpenWSFZ daemon** both capture in real time,
WASAPI-shared-mode, simultaneously. §4.2's setup is an "operator runbook" for a reason: WSJT-X's
audio-device selection, mode (FT8), and Monitor-ON state are set through its own Qt GUI, which has
no CLI or scriptable entry point in this codebase.

**Checked before declaring this blocked (HK-004):**
- `wsjtx.exe` (PID 29796) **is** currently running on this machine — but its audio-device
  configuration is unknown to me and I have no way to inspect or safely change it without a GUI
  automation tool for native Windows apps (out of scope for the tools available to this session:
  Bash/PowerShell, file I/O, browser automation — none of which drive a Qt GUI). Reconfiguring it
  blind risks interfering with whatever the Captain currently has it doing.
- No OpenWSFZ daemon process is running (`Get-Process` for `OpenWSFZ`/`dotnet` returned nothing;
  nothing listening on 8080/8081).
- `harness/run_scenario.py` confirms the live-playback design (see its module docstring and
  `_PLAYBACK_PEAK_LEVEL`/PortAudio usage) — there is no headless/offline mode for S5.

This matches the board's own annotation for this task: **"blocks on: loopback rig."** It is not a
QA judgement call to defer; the instrument genuinely requires a live audio-device bring-up that is
outside what this session can drive.

## What is needed to unblock

1. Confirm which device is the S5 loopback rig (VB-CABLE `CABLE Input`/`CABLE Output` per
   `STUDY-SPEC.md` §4.2) and whether it's free to use right now, or whether the running `wsjtx.exe`
   is mid-use for something else (live 20m monitoring is the project's normal state per current
   memory).
2. Either the Captain brings up WSJT-X against the loopback device and starts an OpenWSFZ daemon
   instance pointed at the same capture endpoint, or authorises QA to do so on a machine/session
   where that reconfiguration is safe.
3. Once both apps are confirmed listening on the shared device, the S5 scenario JSON + `run_scenario.py`
   + `harness/analyse.py` (ratified gate, `THRESH_FP_UB95 = 6.0`, per Sec.4) can run unattended for
   the ~1 h this task is costed at.

## Standing per Sec.4's own fallback

*"If the WSJT-X leg is unavailable on the rig, run OpenWSFZ-only and disclose it."* That fallback
still needs a **running OpenWSFZ daemon on the loopback device**, which is equally not available
right now — so even the degraded single-appraiser path is blocked, not just the comparison path.

**Not proceeding to Task 5 on Task 2 alone** — the board says Task 5 blocks on 1-4 collectively;
Tasks 3 and 4 are pure offline analysis on corpora already on disk and do not share this blocker.
Continuing to those now.
