# QA → Architect — consolidated handoff, 2026-08-04
# All five tasks from your 15:09 index executed. One closed clean, one blocked on hardware I
# can't drive, one PARTIAL with a striking stratification, one observation as specced, one
# STRONG. Branch state untouched -- still yours to resolve.

**Author:** QA, 2026-08-04 (17:38 UTC, `date -u`, per HK-017).
**Branch:** `feature/ft991a-cap-drift-screen-closeout`, now at `90219d8`. 11 new commits since your
`7d25e5f` handoff, each with its pre-registered rule committed before running it (HK-021). Full
range: `7d25e5f..HEAD`.
**Executes:** `qa/2026-08-04-1509-architect-to-qa-consolidated-handoff.md`,
`qa/rr-study/2026-08-04-1500-…-spec-false-positive-surge-and-window4-closure.md` (tasks 1-4),
`qa/cycleframer-alignment-replay/2026-08-04-1441-…-spec-isolated-replay-rerun-post-drift-fix.md`
(task 5).
**For:** Architect.

---

## 0. The board, closed out

| # | task | verdict | report |
|---|---|---|---|
| **1** | Close Window 4 against `be5960a` | **ROW 3 — CLOSED** | `qa/rr-study/2026-08-04-1525-qa-to-architect-task1-window4-closure-CLOSED.md` |
| **2** | Re-run S5 vs the ratified FP gate | **BLOCKED**, not skipped | `qa/rr-study/2026-08-04-1535-qa-to-architect-task2-BLOCKED-loopback-rig.md` |
| **3** | Candidate-budget saturation | **ROW 3 — PARTIAL** | `qa/rr-study/2026-08-04-1545-qa-to-architect-task3-candidate-saturation-PARTIAL.md` |
| **4** | Callsign-recurrence FP proxy | **Observation, no verdict** (as specced) | `qa/rr-study/2026-08-04-1555-qa-to-architect-task4-callsign-recurrence-OBSERVATION.md` |
| **5** | Isolated-replay re-run, two arms | **ROW 4 — STRONG** | `qa/cycleframer-alignment-replay/2026-08-04-1733-qa-to-architect-task5-isolated-replay-ROW4-STRONG.md` |

Ran in your specified order. Task 5 ran last, after 1-4, per your instruction that its number is
"worth less" until the FP question has some shape — it does now (3 PARTIAL, 4 observational), and
5 landed STRONG regardless of that shape, so the two results stand independently as you designed
them to.

---

## 1. Task 1 — Window 4 CLOSED

`artefacts/20260803_live_run_1713`'s decisive 18.96h epoch: `median(ratio, after 13.7h) = 1.4615`
vs `median(ratio, before) = 1.5635` — 93.5% retention, clear of the 0.80× NOT-CLOSED bar (2,822 /
1,263 cycles either side, both over the 200 floor). **ROW 3.**

Actioned per your §2.1: `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` got a
dated addendum (its `be5960a` closure banner was already there from 08-03; this adds the
measurement). `CONTAMINATION-NOTE.md` Window 4's stale *"root cause not yet identified"* clause is
struck in place with a superseding note — **the original observation is untouched**, only that one
clause was stale. Cross-instance detector recorded as not needed for this failure mode; whether
it's wanted for a different one stays open, unchanged.

Instrument: `qa/endurance/2026-08-03-drift-screen/window4_closure_check.py`.

## 2. Task 2 — BLOCKED, not run

S5 plays synthetic PCM live into a shared device captured in real time by a running WSJT-X
instance and a running OpenWSFZ daemon (`harness/run_scenario.py` — no headless mode exists).
Checked before declaring blocked (HK-004): `wsjtx.exe` is running but I have no way to inspect or
reconfigure its audio-device state without a GUI automation tool for native Windows apps, and no
OpenWSFZ daemon was running. Reconfiguring WSJT-X blind risks interfering with whatever it's
currently doing. This matches your own "blocks on: loopback rig" annotation — it isn't a QA
judgement call, the instrument genuinely needs a live bring-up outside what this session can drive.

**Needed to unblock:** confirm the VB-CABLE rig is free, then either you bring up WSJT-X + a
daemon on it, or authorise QA to do so once that's established as safe. Sec.4's OpenWSFZ-only
fallback is equally blocked — it still needs a running daemon on the loopback device.

## 3. Task 3 — candidate budget PARTIALLY saturated, and the stratification is worth your look

4,552 cycles from the decisive epoch's own process log carried both pass counts (no replay
needed). `sat_0 = 0.4576` → **ROW 3 PARTIAL**.

**Flagging this beyond the task's own scope:** the stratification by decodes/cycle is unusually
clean for field data — essentially 0% saturation below 8 decodes/cycle, rising monotonically to
essentially 100% above 22, with the transition concentrated in a narrow 13-21 band. That shape is
consistent with your Sec.1 hypothesis (rivalry only bites once the top-140 cut is close to the
signal population) and doesn't refute it — ROW 4 REFUTED did not fire. If you want the candidate-cap
sweep priced (`dev-tasks/2026-07-26-d001-candidate-cap-sweep.md`), this curve is the strongest
single piece of supporting evidence produced today; I did not extend past reporting it, per Sec.5's
"do not propose raising either cap" instruction.

Instrument: `qa/rr-study/candidate_saturation_check.py`.

## 4. Task 4 — observation, no verdict, as specced

8080-only decodes (39,006, this run's version of your 37,511 figure — full corpus here vs. your
window-restricted one) show a 53.3% singleton (single-cycle) rate; matched-in-both (25,411, vs your
24,480) shows 16.6%. Every extracted callsign was SHA-256 hashed at first use — no plaintext
callsign anywhere in output or committed files (NFR-021). Full disclosure of what this can and
cannot exclude is in the report; short version: the +36.7pt delta is consistent with an elevated FP
rate in the 8080-only population but is equally consistent with genuine weak-DX/sensitivity
effects and extraction-method noise. No verdict drawn, per your instruction that this must not
acquire verdict status by repetition (echoing PASS report §8).

Instrument: `qa/rr-study/callsign_recurrence_proxy.py`.

## 5. Task 5 — ROW 4 STRONG

Adapted `run_isolated_replay.py` / `materialise_isolated_sample.py` (`0726bd6`, confirmed running
unmodified in shape before adapting) to accept a corpus path — disclosed in each script's header,
made before pre-registering, per your Sec.5 instruction. Two changes: corpus-path parameter, and
WAV source is `<corpus>/wsjt-x/wav/` rather than a single shared `save/` folder (documented
reasoning in the script header).

All four mandatory self-checks passed: epoch contiguity (arm A 5 epochs matching the known
Window 4/6/7 history; arm B 2 epochs, 1.76h + 18.96h), drift-screen rows cited not re-run (arm A
ROW 2 FAIL −47.3/−48.6/−47.7 ppm; arm B ROW 5 PASS +0.0 ppm — HK-018), grid alignment (arm A +7 of
59,227 at ±1 cycle — drift in the labels, small and disclosed; arm B +0), classification balance
not confounded (28.4% vs 25.2% isolated fraction).

Live replay via VB-CABLE + a throwaway daemon on port 8099, ~2.5h wall clock across both arms
(85 candidates arm A, 44 arm B):

```
recovery_A = 45/85 = 0.5294   (arm A: drifting build, positive control)
recovery_B = 4/44  = 0.0909   (arm B: fixed build, be5960a)
r = recovery_B / recovery_A = 0.1717
```

`r <= 0.333` → **ROW 4 STRONG.** Drift accounted for most of the live-path Isolated-class miss
recovery PR #103 measured; the fix is validated on the live path. Neither absolute recovery figure
is cited as a standalone number (WSJT-X co-appraiser caveat, per your Sec.5 constraint) — only the
ratio.

All 80 reproduced-miss records across both arms classified `ambiguous_busy_passband`
(total_candidates 130-340 throughout) — the reference-pool LLR comparison never triggered in
either arm, the outcome your original spec's §3.3 power caveat anticipated as likely on a dense
band. Doesn't touch the recovery-rate contrast.

Instruments and evidence:
`qa/cycleframer-alignment-replay/2026-08-04-isolated-replay-rerun/` — `evaluate_rule.py` (the
pre-registered rule, committed `7b7c968` before either arm ran), the two generic harness scripts,
`grid_alignment_control.py`, `arm-A/` and `arm-B/` (sample json, results json, replay console log
each — no message text or callsigns committed anywhere, NFR-021).

---

## 6. What none of this decides

Unchanged from your own scope statements, carried forward rather than re-derived:

- **Not D-001.** Baseline deficit and density penalty untouched by any of the five tasks.
- **Not decoder quality.** No oracle was introduced anywhere in this batch; a recovered or
  higher-volume decode is not a validated one (Task 5 §4, Task 4's own caveats, Task 3's scope
  note all say this independently).
- **Not S.1/S.1b, not the B.3 menu/T5 density penalty, not the settings-page stall.** None of
  today's tasks touched them; your §6 open-item list stands exactly as you left it.
- **`jt9` offline was not used anywhere in this batch.**
- **No `src/` change, no cap change, no gate re-tuning.** Task 3's flagged observation in §3 above
  is a pointer for your pricing decision, not a proposal.

## 7. Not QA's — still yours

Your §5 branch-state flag was **not touched** — and it has moved since you wrote it, so flagging
rather than resolving: `origin/main` is no longer at the `cccfd54` your handoff cited. As of this
report it's at `61465c7` (`Merge pull request #120 from frank001/fix/revert-bypassed-drift-screen-batch`,
2026-08-04T17:08:43+02:00) — that PR merged sometime during today's task execution. I did not
inspect what #120 changed relative to your `cccfd54`/`c2c0919` description; I only confirmed it via
`git fetch` just now, for this report, and did not act on it. All 11 new commits in this handoff
landed on the current local branch as additive, non-destructive commits — no push, no merge, no
rebase, no delete. Whether #120 resolves, supersedes, or complicates the history-churn question you
raised is still yours to determine with the Captain.
