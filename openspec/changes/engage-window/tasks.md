## 1. Remove the late-start rejection guard (`QsoAnswererService`)

- [x] 1.1 Delete the `MaxLateStartSeconds` constant (line ~147) and its doc comment.
- [x] 1.2 Remove the late-start guard block from the jump-in consumption path (~lines 626–642),
      leaving the 60-second stale-expiry check and the phase check untouched, so consumption falls
      straight through to `ExecuteJumpInAsync` once the phase check passes.
- [x] 1.3 Remove the late-start guard block from the pending-target consumption path (~lines
      710–726), leaving the 60-second stale-expiry check and the phase check untouched, so
      consumption falls straight through to `ExecuteTxAnswerAsync` once the phase check passes.
- [x] 1.4 Search the file for any other reference to `MaxLateStartSeconds`/`jumpSecondsIn`/
      `pendSecondsIn` and remove now-dead locals (`jumpNow`, `jumpWindowStart`, `pendNow`,
      `pendWindowStart` if unused elsewhere) to avoid compiler warnings.

## 2. Window-boundary transmission truncation (both services)

- [x] 2.1 In `QsoAnswererService.TransmitAsync` (~line 1193), compute the window boundary via the
      existing `RoundDownTo15s(_timeProvider.GetUtcNow()) + TimeSpan.FromSeconds(15)`, derive
      `remaining = boundary - _timeProvider.GetUtcNow()`, and truncate the synthesised `samples`
      array to `min(samples.Length, remaining.TotalSeconds * 48000)` samples (clamped to a
      non-negative sample count) before calling `_pttController.LoadAudio(...)`.
- [x] 2.2 In the same method, if the computed remaining-sample count is zero, skip
      `LoadAudio`/`KeyDownAsync`/`KeyUpAsync` entirely, log at Debug level ("window already closed
      — skipping transmission"), and return without throwing.
- [x] 2.3 Apply the identical truncation logic to `QsoCallerService.TransmitAsync` (~line 931),
      reusing `QsoCallerService`'s own `RoundDownTo15s` helper (already present at ~line 1153).
- [x] 2.4 Factor the truncation computation into a small shared private helper if it can be
      expressed identically in both classes without awkward coupling; otherwise duplicate it
      inline consistently with each class's existing style (both classes already duplicate
      `RoundDownTo15s` rather than sharing it — match that precedent unless a natural shared
      location exists, e.g. a static helper in a shared utility class already used by both).
      **Done via `Ft8TimeHelper.ClampSampleCountToWindowBoundary` — that class was already used by
      both services (`DeriveFt8CycleStartUtc`), a natural shared home per the note above.**

## 3. Formalise `QsoCallerService`'s existing correct behaviour (no code change)

- [x] 3.1 Confirm (already done during design, re-verify at implementation time) that
      `HandleWaitAnswerAsync`'s pending-responder consumption path (~lines 601–653) has no
      lateness guard and requires no code change for the "Pending responder fires unconditionally"
      requirement. **Re-verified 2026-07-15: still no lateness guard, only the 60s stale-expiry
      check and the phase check gate consumption.**
- [x] 3.2 Add a regression test asserting a late-but-correct-phase pending responder still fires
      immediately (protects against a future contributor adding a lateness guard by analogy with
      the pattern this change removes from `QsoAnswererService`).

## 4. Rewrite existing late-start-guard tests

- [x] 4.1 In `QsoAnswererServiceTests.cs`, rewrite the D-CALLER-013/016 test region (~lines
      2383–2650+, including `BuildLateStartSut`) so that pending-target and jump-in scenarios
      previously named `*_LateStart_IsDeferred_ThenFiresNextCycle` now assert **immediate firing**
      instead of deferral — rename tests accordingly (e.g.
      `PendingTarget_LateStart_FiresImmediatelyInSameWindow`).
      **Fixture renamed `BuildLateStartSut` → `BuildTimeControlledSut` (still time-controlled, no
      longer "late-start"-specific since it's shared with the truncation tests too).**
- [x] 4.2 Keep (or add, if any were only implicit) explicit wrong-phase-still-defers tests as
      distinct cases from late-but-correct-phase-now-fires, so the phase-check coverage that was
      previously interleaved with the lateness guard is not lost. **Added
      `PendingTarget_WrongPhase_StillWaitsForNextMatchingPhase` and (new, no prior equivalent
      existed) `JumpIn_WrongPhase_StillWaitsForNextMatchingPhase`.**
      **Production-code addendum:** these (plus the new truncation/AC-1/AC-2 tests) initially
      flaked intermittently under full-suite runs — root cause: `AnswerCqAsync`/`EngageAtAsync`
      push a "wakeup" batch computed from real `DateTimeOffset.UtcNow` (not the injectable
      `TimeProvider`), which races the background loop's own concurrent read of the same channel;
      whichever side loses can leave a stray real-time-phase-dependent processing pass in flight.
      Attempted fix of routing that wakeup through `_timeProvider` was reverted — it broke an
      unrelated passing test (`D-TX-UI-007`) by changing production wakeup-phase behaviour, which
      is out of scope here. Correct fix: added test-only `QsoAnswererService.TestSetPendingTarget`/
      `TestSetJumpTarget` (mirroring `QsoCallerService.TestSetPendingResponder`'s existing,
      identically-motivated pattern) so tests that don't need to exercise the public
      `AnswerCqAsync`/`EngageAtAsync` entry points can arm state deterministically with no wakeup
      push at all. The four original real-API tests (A/B/C/D) were left as-is, matching
      pre-existing precedent — no observed flakiness there. Verified clean across 8 consecutive
      full-class runs after the fix.
- [x] 4.3 Update the shared fixture comment/setup that referenced "0 s into the window ≤
      MaxLateStartSeconds = 2.0 s" (line ~62) since lateness is no longer a pass/fail condition for
      the shared SUT — simplify or remove the comment as appropriate. **Also updated two other
      near-identical comments at ~1433/~1703 referencing the same removed guard.**
- [x] 4.4 Update the D-CALLER-018-adjacent Abort-while-armed-late test (~line 2591) if its scenario
      setup depended on the target being deferred rather than fired — confirm the abort-mid-defer
      race it reproduces still has a meaningful equivalent under the new fire-immediately model, or
      document why it no longer applies. **Rewrote both AC-1/AC-2 to arm-then-retain via a
      wrong-phase cycle (the only remaining way to reach "armed but not yet fired, sitting Idle")
      instead of the removed late-start defer — the abort-while-quietly-waiting race is otherwise
      unchanged.**

## 5. New tests for window-boundary truncation

- [x] 5.1 Add a `QsoAnswererServiceTests` case: `TransmitAsync` invoked late in a window (e.g. 8 s
      in) loads a truncated sample buffer into the fake `IPttController` (assert on the length
      passed to `LoadAudio`).
- [x] 5.2 Add a `QsoAnswererServiceTests` case: `TransmitAsync` invoked at the start of a window
      loads the full, untruncated buffer (regression guard for the common case, AC-4).
- [x] 5.3 Add a `QsoAnswererServiceTests` case: `TransmitAsync` invoked with zero/negative
      remaining time skips `LoadAudio`/`KeyDownAsync` and does not throw.
- [x] 5.4 Add a `QsoAnswererServiceTests` case: a truncated transmission that goes unanswered still
      increments `_retryCount` exactly like a full-length one.
- [x] 5.5 Mirror tasks 5.1–5.4 in `QsoCallerServiceTests.cs` for `QsoCallerService.TransmitAsync`.
      **Required adding an optional `TimeProvider` to `QsoCallerService` (it had none — unlike
      `QsoAnswererService` — so truncation couldn't be tested deterministically otherwise); see
      the production-code note below.**

## 6. Live verification (required — not optional, per AC-5)

- [x] 6.1 Run a real isolated daemon with a VB-CABLE (or equivalent virtual-audio) loopback,
      following the same audio-isolation convention used for prior D-CALLER live-verification
      passes. **VB-Audio Virtual Cable was confirmed present but ultimately not needed: like
      `d-caller-018-abort-hard-stop-live-verify`'s precedent, CQ/answer transmission only requires
      a real audio OUTPUT device, no decode input — so this reused that script's simpler posture
      (real Release daemon + real WASAPI output device) rather than a full loopback rig. New
      script: `qa/engage-window-live-verify/live_verify_engage_window.py`, modelled directly on
      the abort-hardstop precedent's daemon-process/WebSocket/report-writer scaffolding.**
- [x] 6.2 Reproduce deliberately late manual engages (clicks landing 2–10 s into a correct-phase
      window) and confirm from the daemon log: (a) TX fires immediately in the same window — no
      "late start ... deferring" line appears; (b) `KeyUpAsync` occurs at the window boundary, not
      after a full 12.64 s clip, for the late cases. **Confirmed live (Phase B, 7 s into window):
      fires immediately (no old-guard log line, regex-checked across the whole daemon log),
      keying:true→false duration = 7.99–8.01s across 3 runs (vs. Phase A's full ~12.65s sanity
      control) — matches the predicted ~8 s remaining-window truncation exactly.**
- [x] 6.3 Reproduce a wrong-phase click and confirm it still correctly waits for the next
      matching-phase window (AC-2 regression check). **Confirmed live (Phase C) — but note a real
      design constraint discovered while writing the script, worth recording: with only two
      alternating phases, a target armed via `AnswerCqAsync` can only ever mismatch the CURRENT
      window (no instant fire via the wakeup) and then necessarily MATCHES the very next 15 s
      boundary — there is no way to construct a live "misses two consecutive windows" scenario the
      way the unit tests can via `TestSetPendingTarget` bypassing the wakeup. Phase C proves the
      narrower but still real thing: a mismatching click does NOT fire instantly, and DOES fire at
      the next matching boundary — took two iterations to get the phase-parity arithmetic and the
      keying-duration poll deadline right (first attempt fired on what was mislabeled the "wrong"
      boundary because it was actually already a match; second attempt's poll deadline didn't
      account for waiting through the full ~12.64 s clip after the boundary before `keying:false`
      arrives). Final version passed consistently across 3 full runs.**
- [x] 6.4 Attach the resulting log excerpt(s) to the PR as the live-verification evidence, per this
      project's standing convention for QSO-timing defects. **Reports written to
      `qa/engage-window-live-verify/live-reports/*.md` (full WS `txState` event tables + daemon
      log tails); latest confirmed PASS: `2026-07-15T191642Z-19a4253.md`.**

## 7. Close-out

- [x] 7.1 Run the full test suite and confirm no regressions outside the rewritten/added tests
      above. **`dotnet test OpenWSFZ.slnx --filter "FullyQualifiedName!~E2E"` — all green across 2
      consecutive full runs (~1204 tests: Daemon.Tests 477, Web.Tests 238, Ft8.Tests 289,
      Config.Tests 82, Audio.Tests 19, Rig.Tests 41, LicenseInventoryCheck.Tests 24,
      TraceabilityCheck.Tests 34). One `FR-020 ... audioActive` flake seen in a single Web.Tests
      run — a real-WASAPI-capture-timing test unrelated to this change's TX-side code, confirmed
      non-reproducing on rerun (3/3 clean thereafter). E2E.Tests excluded — requires a separate AOT
      publish pipeline unrelated to this change's diff.**
- [x] 7.2 Run `openspec validate --strict --all` and confirm the archived spec delta applies
      cleanly. **56/56 passed, including `change/engage-window`.**
- [x] 7.3 Update `dev-tasks/2026-07-14-engage-window-wsjtx-redesign.md` with a closing status
      pointing at this change and the merged PR, per this project's dev-task handoff convention.
      **Closing note added (§6) — PR not yet opened, noted as a next step since this session ends
      at implementation+verification, not merge.**
