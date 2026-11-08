# QA: O2 trace, why the answerer's first transmission started 4.9 s into its slot (read only)

**Stamped:** 2026-10-23 ~17:00Z (`date -u`). **To: Architect.** QA, branch `qa/refset`.
**Asked by:** the Architect, 2026-10-23 (his prediction Z1: the late start is deliberate, written into the design, and matches WSJT-X's late-start allowance; 0.55 H). **Read only:** no `src/` change, no on-air test.
**Code read:** `origin/main` `326a8af7` (the #257 build adds no change to the answerer). **Facts only**; the Architect decides whether it is a defect.

## What was observed (the #257 L-2 run, build `e8ef9544`)

The Captain's double-click engaged a CQ at 16:46:49.872Z. The first transmission keyed at 16:46:49.890Z, **4.89 s into the 15 s slot** that began at :45, with 10,115 ms of audio loaded (a full FT8 transmission is 12.64 s). It ended at 16:47:00.203Z, the slot boundary.

## (a) Where the code decides to answer in the current slot, and its cut-off

`src/OpenWSFZ.Daemon/QsoAnswererService.cs` on `origin/main` `326a8af7`:
- **The engage arms a pending target:** `TryEngageExternal` (`:372`) and `AnswerCqAsync` (`:338`) call `ArmPendingTarget` (`:454-476`), which sets `_pendingTargetIsAPhase = !cqIsAPhase` (`:465`, the opposite phase to the CQ) and pushes a wake-up batch (`:476`) so the background loop fires "within the current cycle window" (`:162-165`, D-TX-UI-007).
- **The decision is `HandleIdleAsync`, the pending-target block `:738-803`.** Its only gates are: the 60 s stale expiry (`:764`) and the phase check `nextCycleIsAPhase != pendingIsAPhase` (`:783-784`, with `nextCycleIsAPhase = IsAPhase(batch.CycleStart + 15 s)`). When the phase matches, it fires at `:795-801` (`ExecuteTxAnswerAsync`). **There is no lateness cut-off for starting.** The comment at `:795-797`: "regardless of how many seconds into the window this cycle is (D-CALLER-021: no lateness rejection; TransmitAsync truncates the audio buffer to fit the remaining window instead)."
- **The truncation:** `TransmitAsync` (`:1614`) calls `Ft8TimeHelper.ClampSampleCountToWindowBoundary` (`src/OpenWSFZ.Daemon/Ft8TimeHelper.cs:46-59`) at `:1627`: remaining time = window start + 15 s minus now; the buffer is cut to `remaining x sample rate`, never more than the full clip; **zero or negative remaining skips the transmission** (`:1629-1633`). So the cut-off is the window boundary at the END of the clip: a start at any time before the boundary keys, and the tail is cut.
- The same code is in `QsoCallerService.cs:1321` (the caller path).
- The code comments name two decision IDs: **D-CALLER-021** (no lateness rejection; truncate instead) and **D-CALLER-013** (an earlier late-start guard, `:154`, `:207-208`; per the spec text below it has since been removed).

## (b) What the OpenSpec says (`openspec/specs/qso-answerer/spec.md`; the caller has the same two requirements at `qso-caller/spec.md:553` and `:578`)

- Requirement **"Manual engage fires unconditionally within a correct-phase window"** (`:430`): "...it SHALL fire the transmission in the first decode cycle whose phase matches the armed target's expected phase, **regardless of how many seconds into that window the consumption occurs. There SHALL be no lateness-based rejection or deferral**: the only gating conditions are the phase check ... and the existing 60-second stale-target expiry." Scenarios: a pending target consumed "5 s into that A-phase window" and a jump-in "6 s into that B-phase window" SHALL "begin transmitting in that same cycle — it SHALL NOT defer to the next ... occurrence"; "Stale target still expires after 60 seconds regardless of lateness ... unaffected by the removal of the lateness guard".
- Requirement **"Transmission never keys past the current window's boundary"** (`:463`): `TransmitAsync` "SHALL ... truncate the synthesised sample buffer so that playback cannot extend past that window's boundary ... truncation SHALL only shorten the buffer when the full 12.64 s clip would otherwise overrun the window." Scenario: "TransmitAsync is called 8 s into its 15 s window (7 s remaining) ... truncated to at most 7 s of playback"; an on-time transmission "SHALL be passed ... unmodified"; zero remaining skips. A truncated transmission counts for retry, watchdog and ADIF "identically to a full-length transmission".

So the late start with a truncated tail is written into the design twice (the 5 s and 6 s scenarios are the same behaviour as the 4.9 s observed).

## (c) How often it happened in data on file (station logs since v0.59, 2026-10-23T14:22:15Z; the era is not pooled with anything older)

Source: the station's log directory (`D:\Projects\claude\OpenWSFZ\artefacts\20260914_1822_rr-study-s1s8\daemon-logs`, seven files kept). **Only one file in it holds any transmission: `openswfz-20261023T164621Z.log` (the #257 L-2 run). Three transmissions in all, all keyed by that run:**

| KeyDown (UTC) | Offset into the 15 s slot | Keyed (KeyDown to KeyUp) | Which |
|---|---:|---:|---|
| 16:46:49.890 | **4.89 s** | **10.31 s** (audio loaded 10,115 ms, Debug line) | first TX of the QSO (the manual engage) |
| 16:47:15.617 | 0.62 s | 12.84 s | retry 1/3 |
| 16:47:45.629 | 0.63 s | 12.82 s | retry 2/3 |

Counts: first transmissions by start offset: one, at 4.89 s; retries: two, at 0.6 s. **n = 1 first transmission.** No other transmission exists in these logs (the earlier files are receive-only runs). Whether the station's earlier QSOs of 2026-10-22 (build `b8fc732e`, before v0.59) left logs elsewhere was not searched, and they are a different era. The "TX audio loaded" line is a Debug line, so audio lengths are on file only for the Debug-level part of the run; for the others the keyed time is the figure.

## (d) What WSJT-X does for a late start (source: GitHub `saitohirga/WSJT-X` master, NOT the 2.7.0 tag; the user guide pages returned 404 and 403 and were not read)

- **Start gate:** `widgets/mainwindow.cpp`, `MainWindow::guiUpdate()`: `double fTR=float((ms%int(1000.0*m_TRperiod)))/int(1000.0*m_TRperiod); if(g_iptt==0 and ((m_bTxTime and (fTR < 0.75) and (msgLength>0)) or m_tune)) { //### Allow late starts`. **A transmission may start while less than 0.75 of the period has elapsed: 11.25 s into a 15 s FT8 period.** (`m_bTxTime = (t2p >= tx1) and (t2p < tx2)`, with `tx2 = txDuration` capped at the period.)
- **What happens to the audio:** `Modulator/Modulator.cpp`, `Modulator::start()`: `delay_ms=500` for FT8; `if(!m_silentFrames && mstr >= delay_ms) { m_ic = (mstr - delay_ms) * m_frameRate / 1000; }`, with the comment "adjust for late starts". **WSJT-X plays the waveform from an offset: it SKIPS THE START of the clip and plays to the waveform's end; it does not truncate the end.** (The agent's inference, not stated in code: a start near the 11.25 s limit leaves about 1.9 s of signal.)
- **Caveats the agent reported:** master not 2.7.0; the FT8 `txDuration`, `NTMAX` (the modulator's period) and `txDelay` details were not read; the user guide was not read.

## Reading, against the Architect's prediction Z1 (facts, not a verdict)

- "Deliberate, written into the design": **supported** by D-CALLER-021, the code comments, and the two OpenSpec requirements with their scenarios (5 s, 6 s, 8 s).
- "Matches WSJT-X's late-start allowance": **partly.** Both allow a late start. They differ in the limit (WSJT-X: not after 11.25 s into the period; OpenWSFZ: any time before the boundary, with the clip cut to what remains) and in the mechanism (WSJT-X skips the beginning of the waveform; OpenWSFZ keeps the beginning and cuts the tail).
- **Not known from any data on file:** whether a receiver can decode a transmission started 4.9 s late and cut to 10.1 s; the one occurrence got no answer, and the two full-length retries got none either, so it says nothing.
