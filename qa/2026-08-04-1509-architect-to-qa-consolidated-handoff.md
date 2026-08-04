# Architect → QA — consolidated handoff, 2026-08-04
# One index. Five open tasks, in order. Everything else on this page is a pointer.

**Author:** Architect, 2026-08-04 (15:09 UTC, `date -u`, per HK-017).
**Branch:** `feature/ft991a-cap-drift-screen-closeout` at `d57ebb2`. ⚠️ See §5 — the branch state
is unresolved and is the Captain's call, not QA's.
**For:** QA. Nothing here is mine to apply.

> **This document does not restate any pre-registered rule.** Each task points at the spec that
> owns its rule. Two copies of a threshold is how a threshold drifts — HK-021 requires one
> mechanical source, and that source is the spec, not this index.

---

## 0. Where everything is

### The specs that own the tasks

| file | owns |
|---|---|
| `qa/rr-study/2026-08-04-1500-architect-to-qa-spec-false-positive-surge-and-window4-closure.md` | **Tasks 1–4** |
| `qa/cycleframer-alignment-replay/2026-08-04-1441-architect-to-qa-spec-isolated-replay-rerun-post-drift-fix.md` | **Task 5** |
| `qa/endurance/2026-08-03-drift-screen/2026-08-04-1416-architect-to-qa-post-cap-lift-work-order.md` | ✅ **fully executed** — retained for provenance |

### Evidence produced by the drift screen (closed, ROW 5 PASS)

| file | what it is |
|---|---|
| `qa/endurance/2026-08-03-drift-screen/2026-08-04-1405-qa-to-architect-…-PASS.md` | the verdict report; §8 is the decode-correspondence observation |
| `qa/endurance/2026-08-03-drift-screen/drift_screen.py` | the instrument; constants at `:71-107` |
| `qa/endurance/2026-08-03-drift-screen/ui_stall_check.py` | now carries the C1–C3 input contract (`48ecc3d`) |
| `qa/endurance/2026-08-03-drift-screen/drift_curve_20260803_live_run_1713.csv` | 4,971 per-cycle rows |
| `qa/endurance/2026-08-03-drift-screen/2026-08-03-1652-qa-run-spec-…md` | the authorising run spec |
| `qa/endurance/2026-08-03-drift-screen/2026-08-04-1426-TODO-settings-page-heartbeat-stall.md` | filed, unchased |

### Corpora — both already on disk, neither needs capturing

| corpus | span | build | used by |
|---|---|---|---|
| `artefacts/20260803_live_run_1713/` | 20.73 h wall, **18.96 h decisive epoch** | **post-fix** | tasks 1, 3, 4, 5 (arm B) |
| `artefacts/20260731_live_run_2004-8080/` | 43.6 h | pre-fix | task 5 (arm A) |

**Check `qa/ARTEFACT_INVENTORY.md` before proposing any capture run** (HK-018 / HK-004). It is
regenerated and `--check` clean.

### Background that bounds what may be claimed

| file | what it constrains |
|---|---|
| `qa/rr-study/results/2026-07-23-d001-live-path-root-cause/report.md` | §5.3 item 2 is what task 5 executes |
| `qa/rr-study/results/corpus-2026-07-10/report.md` | **WSJT-X is not an oracle** — 86.9–93.0% self-repeatability |
| `qa/rr-study/STUDY-SPEC.md` §10 (+ §2.2 D1) | the **ratified** FP gate and the co-appraiser framing |
| `qa/rr-study/harness/analyse.py` | `THRESH_FP_UB95 = 6.0`, `_min_n_for_fp_gate` |
| `qa/endurance/2026-08-02-multiday-20m-anova/CONTAMINATION-NOTE.md` | Window 4 — task 1 closes it |
| `qa/cycleframer-alignment-replay/2026-07-31-1719-qa-drift-screen-8081-20m-per-segment-result.md` | D-001's corpus is drift-clean (0.136 s / 2.72 h) — drift does **not** explain D-001 |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` `:467` `:504` `:514-522` | the candidate caps, and the stack-overrun warning |
| `src/OpenWSFZ.Abstractions/DecoderConfig.cs` | the three D-009 calibrated gates |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/` | task 5's harness (**unread by me** — confirm it runs) |
| `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` | task 1 closes this |
| `dev-tasks/2026-07-26-d001-candidate-cap-sweep.md` | gated behind task 3 |

---

## 1. The board

| # | task | spec § | verdict? | blocks on | cost |
|---|---|---|---|---|---|
| **1** | Close Window 4 against `be5960a` | FP spec §2 | mechanical | — | ~15 min |
| **2** | Re-run S5 vs the ratified FP gate | FP spec §4 | **ratified, do not redraft** | loopback rig | ~1 h |
| **3** | Candidate-budget saturation | FP spec §5 | mechanical | may VOID at step 1 | ~1 h |
| **4** | Callsign-recurrence FP proxy | FP spec §6 | **none — no oracle** | — | ~30 min |
| **5** | Isolated-replay re-run, two arms | replay spec §3 | mechanical | run after 1–4 | ~half a session |

**Run in that order.** Task 5 measures how much live-path loss the drift fix recovered; that
number is worth less until tasks 2–4 establish how much of what came back is real.

**Task 3 can kill the whole hypothesis.** If it fires ROW 4 REFUTED, §2 below is dead and tasks 4–5
still stand on their own. That is the intended behaviour, not a problem.

## 2. The one thread connecting tasks 2–5

Two symptoms from the Captain, 2026-08-04: **a lot of false positives since the drift fix**, and the
**~40% shortfall against WSJT-X still unexplained**.

Candidate slots are capped (`K_MAX_CANDIDATES = 140` pass 0, `200` pass 1) and the Window 4
diagnostics show 8081 pinned at exactly 140. **If the budget saturates, candidates are rivalrous** —
a false candidate displaces a real signal scoring below it, making both symptoms one mechanism.

Why now: drift degraded every candidate's score, real and spurious alike, so it was acting as an
**accidental FP filter** bought with sensitivity. `be5960a` removed it. On this reading the FPs are
the operating point D-009 always calibrated to, **not a regression the fix introduced**.

**This is a hypothesis. Task 3 is what makes it testable, and it may refute it.**

## 3. Closed — do not reopen

- **The drift screen.** ROW 5 PASS, 18.96 h decisive epoch, +0.0 ppm against a 48.0 ppm chain.
- **The ~6 h FT-991A cap.** Lifted by the Captain 2026-08-04. Do not re-impose or cite as standing.
- **The post-cap-lift work order.** All five items landed (`48ecc3d`, `dabf0a8`, `7a545c6`,
  `1fc708e`).
- **Window 4's mechanism.** Attributed to drift by the Captain and the attribution holds — 13.7 h
  predicted vs ~14 h observed, restart cured it, radio power-cycle did not, 8081 at 4.7 ppm
  unaffected. Task 1 supplies the evidence; the *record* is stale, not the question.

## 4. Standing constraints on every task above

- **WSJT-X is a co-appraiser, not an oracle.** No WSJT-X-only decode is automatically real; no
  8080-only decode is automatically false.
- **`jt9` offline is not a reference leg.** It overshoots both real-time decoders (+11.2% / +93.8%)
  and emits duplicate `(ts, message)` pairs.
- **No `src/` change in any task here.** Cap changes and gate re-tuning are HK-011 Developer work,
  reaching the Captain **priced**, never as an edit from a QA task.
- **No capture run.** Everything needed is on disk.
- **A higher line count is not a better decoder**, and §8 of the PASS report carries **no
  pre-registered rule** — it must not acquire verdict status by repetition.

## 5. Not QA's — the Captain's, flagged so QA does not trip over it

**The branch state is unresolved.** `origin/main` is at `cccfd54` and carries the batch.
`fix/revert-bypassed-drift-screen-batch` holds `c2c0919`, which deletes the entire drift-screen
evidence set (18,126 deletions). The current branch contains that revert **plus re-created copies
of all ten commits under new hashes**, then the two specs on top.

**Content is intact** — I verified all four critical files present and
`git diff origin/main HEAD -- qa/endurance/2026-08-03-drift-screen/` **empty**. What exists is
history churn, not loss.

**Unknown to me: what "bypassed" refers to.** If a gate was genuinely skipped that is HK-022
territory and may bear on the closeout's soundness. **QA should not resolve this** — do not push,
merge, rebase or delete anything here. Ask the Captain which branch the work belongs on before
committing task output.

## 6. Still open, not scheduled by this handoff

- **S.1 / S.1b** — my record says S.1 VOID (`2026-07-31-1730` V1/V7) with the corrected estimator
  awaiting the Captain. The Captain's pointer to `qa/endurance/2026-08-02-multiday-20m-anova/`
  contains no locality analysis (searched `frequency-local`, `cycle-global`, `locality`,
  `subtraction`, `spectral`, `K_MAX` — zero hits). **If it was resolved elsewhere I want the
  pointer; my record may be wrong.**
- **D-001's B.3 menu, T5 density penalty** — unchanged, still the Captain's.
- **`max |lag|` sample-size gate** — registered in the work order §3, deliberately **not** a task.
  It binds before any drift screen is run over an epoch materially longer than 18.96 h.
- **The settings page is not cleared.** ROW 4 NOT REPRODUCED; no row votes safe.
