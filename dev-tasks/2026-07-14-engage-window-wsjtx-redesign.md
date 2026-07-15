# Handoff: D-CALLER-021 — Replace the late-start threshold/defer model with WSJT-X-style "engage if window is still open"

**Date:** 2026-07-14
**Prepared by:** QA engineer (analysis of `logs/openswfz-20260714T171230Z.log`, real-hardware field
test of PR #72 by the Captain)
**Status:** CLOSED 2026-07-15 — implemented via OpenSpec change `engage-window` on branch
`feat/engage-window`, exactly as this document's §2 recommended. See §6 (closing note) at the
bottom of this file for the full disposition; kept here for history only, no longer an open item.

**Original status (superseded by the above):** Awaiting developer/design action — **recommend
routing through `openspec-propose` rather than implementing directly**, see §0 note. This is a
behavioural/architecture change to core TX timing across both `QsoAnswererService` and
`QsoCallerService`, not a narrow bug fix, and it likely touches the `IPttController` audio-playback
contract as well (§3.2). It deserves a design.md and proper spec delta, not a same-shape dev-task as
the two D-CALLER bugfixes it follows.
**Defect ID:** D-CALLER-021 (supersedes D-CALLER-013's original threshold model and D-CALLER-016's
retune of it — not a regression of either, but new field evidence shows the model itself, not just
its constant, is the problem)
**Severity:** High — this materially degrades the manual-engage feature: **10 of 14 (71%) of manual
double-click engage attempts in today's field session were deferred a full ~30 s cycle**, even after
D-CALLER-016 (PR #72, merged today) raised the threshold from 1.5 s to 2.0 s.

---

## 0. Captain's stated model (authoritative — design to this)

> The way I think wsjt-x handles this operator/tx-timing issue is that it just enables TX and starts
> sending if the current TX window is still correct, even when the whole 15s audio can not be
> transmitted in the remaining time. when the window closes the TX is just stopped and wsjt-x starts
> to listen. when the TX window is not correct it waits until the next cycle. If the operator waited
> to long to engage the qso, it is his problem not of the application.

Two distinct decisions are bundled in that statement — keep them distinct in the implementation:
1. **Engage decision**: fire immediately if the *phase* is correct (A/B), regardless of how many
   seconds into that window it already is. No threshold-based rejection/deferral at all.
2. **Playback decision**: whatever audio plays, stops exactly at the 15 s window boundary — it is
   never allowed to overrun into the next window — rather than always playing the full 12.64 s clip
   from click-time regardless of how late that start was.

---

## 1. Context

### 1.1 Field evidence — the current (post-PR #72) model still misses most clicks

Every `"pending target ... — late start ... deferring to next occurrence"` line from today's
session, `logs/openswfz-20260714T171230Z.log` (grep pattern `late start`):

| Time     | Target   | Seconds into window | vs. current 2.0 s threshold |
|----------|----------|----------------------|------------------------------|
| 19:14:32 | EA8UP    | 2.4 s                | over |
| 19:15:21 | OE5CCN   | 6.3 s                | over |
| 19:15:47 | OL900CO  | 2.3 s                | over |
| 19:16:03 | RL2F     | 3.0 s                | over |
| 19:17:17 | SV1ONU   | 2.4 s                | over |
| 19:17:47 | OE5CCN   | 2.6 s                | over |
| 19:23:32 | CT2HUU   | 2.2 s                | over |
| 19:26:47 | SV1EAG   | 2.3 s                | over |
| 19:27:03 | YO4GIY   | 3.1 s                | over |
| 19:27:32 | YO2AMU   | 2.5 s                | over |

Against 4 clicks that landed inside the window and fired immediately (OE5CCN@19:18:15, EX8ABR@19:19:16,
CR7BUJ@19:24:16, EA1FUB@19:28:16). **10/14 = 71% deferred.**

D-CALLER-016's own commit message (this session, `62c7c98`) claimed 2.0 s "leaves a 0.36 s hard
safety margin against overrun, comfortably covering the ~50-90 ms KeyDown/device-open jitter observed
in production logs, while catching realistic decode-to-click latency instead of nearly always missing
it." Today's data directly contradicts that: it is still nearly always missing it. The true physical
ceiling is `15 − 12.64 = 2.36 s` (an FT8 tone is 12.64 s long) — nearly every observed click above is
already past that hard ceiling for a *full-length* transmission, which is exactly why WSJT-X's model
of "transmit whatever fits, don't reject the click" is the right shape of fix and pure threshold
tuning cannot close this gap further without hitting the physical ceiling itself.

### 1.2 Where the current threshold logic lives

`QsoAnswererService.cs`:
- `MaxLateStartSeconds` constant — line 147.
- Pending-target consumption (`AnswerCqAsync`-armed) — late-start guard at lines 710–726.
- Jump-in consumption (`EngageAtAsync`-armed) — late-start guard at lines 626–642.

`QsoCallerService.cs` has the mirror-image logic for the caller side (`CallerPartnerSelect`
auto-engage and pending-responder consumption) — locate via the same `MaxLateStartSeconds` /
`late start` search; not enumerated here in detail since the Answerer side is the one with today's
field evidence, but the redesign must cover both services symmetrically, exactly as D-CALLER-016 did.

### 1.3 Where playback duration is currently fixed

`TransmitAsync` (`QsoAnswererService.cs`, line 1192) always synthesises and loads the *full* message
audio regardless of how far into the window `TransmitAsync` was called:

```csharp
var samples = _synthesiser.Synthesise(tones, freqHz);   // always full 12.64 s (606,720 samples @ 12kHz-equiv)
_pttController.LoadAudio(samples);
...
await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);  // plays to completion or cancellation
```

There is currently no mechanism to start this clip partway through the window and stop it exactly at
the 15 s boundary — `KeyDownAsync` plays what it's given, to completion, unless externally cancelled.
Today's session never actually exercised an overrun (every fired engage was well within the window),
so this half of the redesign is **not** validated by today's evidence — it is required by the
Captain's stated model (§0, point 2) and needs its own design/verification once implemented.

---

## 2. Scope note — recommend `openspec-propose`, not a direct dev-task

Unlike D-CALLER-018/020 (both narrow, single-file-ish bugfixes), this change:
- Touches TX-engagement decision logic in **both** `QsoAnswererService` and `QsoCallerService`.
- Likely requires a new capability on `IPttController` (or a parameter on `KeyDownAsync`/`LoadAudio`)
  to support "play until cancelled/boundary" rather than "play to completion" — an interface change
  affecting `CatPttController`, `SerialRtsDtrPttController`, and every test double implementing
  `IPttController`.
- Removes/replaces a threshold model that shipped across three prior dev-tasks (D-CALLER-013,
  D-CALLER-016, and this one) — worth capturing the "why" in a spec so it isn't re-litigated by a
  fourth.
- Has real design choices the Captain should confirm before code is written, not just review after:
  what governs the *lower* bound (is there still a hard floor below which engaging is pointless — e.g.
  a click landing at 14.9 s into the window, where FT8 demodulation at the far end may not have enough
  clean signal to decode anything useful)? Does a truncated transmission still count toward
  `_retryCount`/ADIF logging the same way a full one does? Does the operator get any UI indication
  that a given engage will be truncated versus full-length?

Suggest running `openspec-propose` for this rather than jumping straight to a branch. This document
is written so its content (evidence, current-state references, the two-part decomposition) can seed
that proposal directly.

---

## 3. Requirements for the eventual fix (for the proposal / branch, whichever comes first)

### 3.1 — Engage decision: drop the late-start rejection

Replace "reject/defer if `secondsIn > MaxLateStartSeconds`" with "engage unconditionally once the
phase check passes," in both the pending-target and jump-in consumption paths (`QsoAnswererService.cs`
lines 626–642 and 710–726) and their `QsoCallerService.cs` equivalents. The phase check itself
(`nextCycleIsAPhase != pendingIsAPhase` / `jumpIsAPhase`) is unaffected and must be kept exactly as
today — that half of the Captain's model ("when the TX window is not correct it waits until the next
cycle") is already correctly implemented.

### 3.2 — Playback decision: stop transmission at the window boundary, never overrun

Whatever mechanism is chosen (truncating the synthesised sample buffer to the remaining
window-time before calling `LoadAudio`, or adding a deadline/cancellation to `KeyDownAsync` itself),
the transmission must never key past the current 15 s window's end. A transmission that starts, say,
8 s into its window has ~7 s of window left and should play (at most) ~7 s of audio, then unkey and
return to listening for the next cycle — not attempt the full 12.64 s clip and overrun by ~4.6 s into
what would be the *other* phase's window.

### 3.3 — Retry/ADIF/state-machine interaction

A transmission truncated by §3.2 is, by FT8 protocol reality, unlikely to be decoded cleanly at the
far end (a partial tone sequence rarely demodulates). Confirm with the Captain whether:
- a truncated TX should still count as a "sent" transmission for `_retryCount`/watchdog purposes
  (current behaviour for full transmissions), or
- it should be excluded/flagged distinctly, since — unlike a full transmission that simply went
  unanswered — a truncated one may not have reached the far end intelligibly at all, and silently
  counting it toward the same 3-retry budget could exhaust retries faster than intended.

This question does not block §3.1 (which is unconditionally correct per the Captain's stated model)
but does need an answer before §3.2 ships.

---

## 4. Acceptance criteria (draft — refine once design is settled)

**AC-1.** A manual double-click engage landing at any point within a correct-phase window fires TX in
that same window — no deferral to the next matching-phase window, regardless of how many seconds late
the click was.

**AC-2.** A manual double-click engage landing in a wrong-phase window still correctly waits for the
next matching-phase window — unchanged from today.

**AC-3.** A transmission that starts late in its window unkeys exactly at that window's boundary, and
never keys into the following window's timing.

**AC-4.** Full retry-exhaustion, watchdog, and ADIF-logging behaviour is unaffected for transmissions
that start early enough to complete in full (i.e. no regression for the common case).

**AC-5.** Live verification required (per this project's standing convention for QSO-timing defects —
see D-CALLER-018 dev-task §5): replay or reproduce a real engage sequence with deliberately late
clicks (2–10 s into the window) against a real isolated daemon and confirm immediate TX with correct
unkey timing at the boundary, not a 30 s deferral.

---

## 5. References

- Evidence log: `logs/openswfz-20260714T171230Z.log` — all `late start` lines (§1.1 table above).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs`:
  - `MaxLateStartSeconds` — line 147.
  - Jump-in late-start guard — lines 626–642.
  - Pending-target late-start guard — lines 710–726.
  - `TransmitAsync` — line 1192 (playback-duration fix target, §3.2).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs` — mirror-image logic, locate via `MaxLateStartSeconds`.
- `src/OpenWSFZ.Abstractions/IPttController.cs` (or wherever `IPttController` is declared) — likely
  interface-surface change for §3.2; confirm exact path before scoping.
- `dev-tasks/2026-06-27-d-caller-013-late-tx-guard.md` — original `MaxLateStartSeconds` rationale
  (1.5 s, no production click-latency data).
- `dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md`, §3.2 — D-CALLER-016's
  retune to 2.0 s (merged PR #72, 2026-07-14) — this document's field evidence is what falsifies that
  fix's own stated rationale; not a fault of that PR, just new information arriving the same day.
- `dev-tasks/2026-07-14-working-cq-false-abort.md` — the other finding from the same field session
  (D-CALLER-020); different root cause, tracked separately, no dependency either direction.
- PR #72 QA sign-off comment (this session) — full mapping of all three field complaints to root
  causes, of which this is one.

---

## 6. Closing note (2026-07-15)

Implemented exactly as this document's §2 recommended — routed through `openspec-propose` rather
than a direct dev-task, producing `openspec/changes/engage-window/{proposal,design,tasks}.md` and
delta specs for `qso-answerer`/`qso-caller`. All 26 tasks across `tasks.md` §1–7 complete on branch
`feat/engage-window`; PR not yet opened as of this note (implementation + verification just
finished this session).

**What shipped, mapped to §3's requirements:**
- §3.1 (drop the late-start rejection): done — `MaxLateStartSeconds` and both
  `QsoAnswererService.cs` guard blocks (jump-in, pending-target) deleted outright, not just retuned
  or raised to a "basically never trips" value.
- §3.2 (truncate playback at the window boundary): done via buffer-slicing (design.md Decision
  D1), not an `IPttController`/`KeyDownAsync` interface change — a new shared
  `Ft8TimeHelper.ClampSampleCountToWindowBoundary` helper is used by both services'
  `TransmitAsync`, so this doc's §3's speculation about a likely `IPttController` surface change
  did not materialise.
- §3.3 (retry/ADIF/state-machine interaction): resolved by the Captain before design — a truncated
  TX counts toward `_retryCount`/watchdog exactly like a full one, no distinct state.
- Investigation during design (recorded in `design.md` D3) found this document's "mirror-image
  logic" assumption about `QsoCallerService` was inaccurate: its pending-responder path already had
  no lateness guard at all. That half of this change is a spec-only formalisation, not a code fix.

**Live verification (AC-5 / tasks.md §6):** new script
`qa/engage-window-live-verify/live_verify_engage_window.py` (modelled on
`d-caller-018-abort-hard-stop-live-verify`'s precedent) proved, against a real Release daemon and a
real audio output device: a click 7 s into its window fires immediately (no deferral, no "late
start ... deferring" log line) with a transmission truncated to ~8 s (vs. Phase A's full ~12.65 s
sanity control) — matching the predicted remaining-window duration to within measurement noise
across 3 consecutive runs. A wrong-phase click still correctly waits for the next matching-phase
boundary (AC-2 regression). Reports: `qa/engage-window-live-verify/live-reports/*.md`.

**Full test suite** (`dotnet test OpenWSFZ.slnx --filter "FullyQualifiedName!~E2E"`): all green
across two consecutive full runs (Daemon.Tests 477, Web.Tests 238, Ft8.Tests 289, plus the smaller
Config/Audio/Rig/License/Traceability projects — ~1204 tests total). `openspec validate --strict
--all`: 56/56 passed.

**Next steps** (not part of this dev-task's closure, tracked via the standard OpenSpec flow): open
the PR, run `/opsx:verify`, merge to `main`, then `/opsx:archive engage-window`.
