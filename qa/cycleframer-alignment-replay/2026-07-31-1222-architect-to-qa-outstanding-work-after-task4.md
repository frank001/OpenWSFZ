# Architect → QA — outstanding work, after task 4 closed
# Supersedes the work queue in `2026-07-31-0910` §3. Task 4 is closed; one new item is ahead
# of everything else and is not a measurement.

**Author:** Architect, 2026-07-31 (12:22 UTC, `date -u`, per HK-017). Repo at `3eb0f2d`.
**For:** QA. Every item below is QA's to do or to route; none of it is mine to apply.
**Replaces:** `2026-07-31-0910` §3's queue (tasks 1–4), which is now out of date.
**Standing reference remains** `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md` §0.

---

## 0. The board

| # | item | status |
|---|---|---|
| **0** | **Commit today's work** | **NOT DONE — do this first (§1)** |
| 1 | Drift fix (oracle + fix) | Built and verified. **Uncommitted**; then needs the Captain's sign-off |
| 2 | **Measurement D** | **Not started.** Spec at `0853`. The only open D-001 measurement (§3) |
| 3 | Measurement A correction + script fix | **Not started** (§4) |
| 4 | 489135a recompute | **CLOSED INCONCLUSIVE** (`1212`). Two small housekeeping items remain (§5) |

## 1. Task 0 — commit the record ⟨do before anything else⟩

Nothing produced today is in git. Verified at `3eb0f2d`:

```
 M src/OpenWSFZ.Ft8/CycleFramer.cs                       37 insertions — WORKING TREE ONLY
?? tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs      224 lines — UNTRACKED
?? 2026-07-31-{0925,1001,1013,1024,1041,1137,1207}-*.md             7 QA documents
?? measurement_489135a_recompute.{py,_report.md,_run.log}
?? measurement_task4_calibration_penalty.{py,_report.md}
?? verify_dt_drift_489135a.py

git log --since=2026-07-30 -- src/   →   (empty)
```

**Why this is ahead of the measurements.** The drift fix and its oracle are the response to a
Critical defect, verified through a Developer session and an independent QA review (301/301,
600/601, 7/7). They exist only as unstaged edits on `main`. A `git checkout`, `git stash`, or
branch switch destroys both, and the 224-line oracle is untracked so a stash would not even
catch it. Separately, the entire task-4 evidentiary record is uncommitted, which means **the
five rulings I committed today cite documents that do not exist in the repo's history.**

**Also correct the footers.** All seven documents carry *"Per HK-014/HK-010 committed locally,
no push, no merge."* That was not true when written. Either commit them and the statement
becomes true, or correct the wording — but do not leave an assertion in the record that the
repo contradicts. `1024` §1's *"1a (oracle): landed"* has the same problem.

**Suggested split** (QA's call, not binding):

| commit | contents | notes |
|---|---|---|
| 1 | `src/CycleFramer.cs` + the oracle test | **Branch first** — this is `src/` work sitting on `main`. Per HK-011 it is the Developer session's commit and needs the Captain's sign-off **before push**, not before commit |
| 2 | The 7 QA documents + 6 analysis scripts/reports | Docs and qa-tooling only; unaffected by HK-011 |

**Boundaries:** per HK-014 I neither push nor merge nor ask for it, and I have not committed any
of the above on QA's behalf. Per HK-012 I am raising it rather than letting it lapse.

## 2. Task 1 — drift fix: what remains

The engineering is done and I have no further requirements on it. Remaining steps are process:

1. Commit (§1).
2. **Raise the push sign-off with the Captain directly** — HK-011/HK-010. Per HK-014 that request
   is not mine to make.
3. On merge: HK-010 sign-off is needed every time, and green CI is necessary but never sufficient.

**One note for the merge conversation, not a new requirement.** I read the diff while verifying
§1. It matches the scoping exactly — per-cycle wall-clock resync, residual absorbed by the
timestamp, no buffer resize, no rate estimation or PLL. And the decision to resync **lazily**
(when the next window's first sample arrives) rather than eagerly at window close is subtler than
what I specified and is correct: time lost to a slow crystal *or to a silently dropped chunk* has
not elapsed yet at window close. That covers both failure paths from `0910` §4.3, not just the
crystal. Worth stating in the PR description, because it is the kind of reasoning that gets
"simplified" away by a later maintainer.

**Until this is merged**, `0910` §4.5's operational guidance stands: fix it, or cap sessions below
~12 h on the affected device, before gathering any further long-session corpus (HK-020).

## 3. Task 2 — Measurement D ⟨the only open measurement⟩

Spec: `2026-07-31-0853`, unchanged and still current. Half a QA session, no decoding, no new
data, no `src/`.

**Nothing that happened today affects it.** Measurement D is a within-corpus comparison and never
touches the density law — which is what task 4 just established cannot bear predictive weight
(`1212` §2). If anything the case for D is stronger: it is now the only route to ungating the row
4 decomposition, and the cheapest thing on the board by a wide margin.

Re-read `0853` §3's four mandatory self-checks before running, in particular the **duplicate-key
artefact** check. Today's task-4 sequence is a live demonstration of why those exist: three of the
four escalations were caused by a comparison being subtly not what it appeared to be.

## 4. Task 3 — Measurement A correction

Not started; confirmed untouched at `3eb0f2d`. Three parts:

1. **Escalate the corrected reading** per `0029` §1.3 — the co-channel withdrawal is dead (row 1
   excluded by a 36-point separation), but the reversal is **not** licensed: rows 3+4 fire, so the
   outcome is *escalate, do not interpret*. What is measured is a 20m-specific deficit.
2. **Fix `measurement_a_snr_recall.py` lines 196–200.** The `monotone_count` check tests only
   `recall(80m) >= recall(20m)` — the outer band pair — and then prints "monotone". The full
   three-band ordering fails in 10 of 26 bins. Either implement the real check or delete the
   verdict line; do not leave a script printing a conclusion its test does not support.
3. **Correct `measurement_a_snr_recall_report.md`'s** auto-generated outcome line accordingly.

The drafting defect in the rule was mine, not QA's execution — say so in the correction so the
record is accurate about where it originated.

## 5. Task 4 housekeeping — two small items, then it is closed

1. **Annotate `qa/endurance/2026-07-29-489135a/anova_report_40m.md`.** Its 62.4% is **un-suspended
   but superseded**: the corpus's honest figure is **56.6% drift-free** (`1137` §2). Record both,
   with the note that 62.4% is session-averaged across a drift ramp and a late collapse, and that
   **neither figure may be compared against the density law** (`1212` §6).
2. **Record the durable constant somewhere it will be found.** Task 4's most valuable output is
   not a parity number: **sub-0.5-second capture misalignment costs ~0.15 points of matched
   parity** (`1207` §2, ruled at `1212` §1.2). It retroactively justifies the `|drift| < 0.5 s`
   healthy-window bar this programme has used on intuition, and supports the 2.34–2.48 s cliff
   being a genuine cliff rather than the end of a ramp. It belongs with the defect report, not
   buried in a calibration write-up.

## 6. Not on QA's list — so nothing waits on QA for these

- **The row 4 decomposition** is mine, still owed, gated on Measurement D.
- **The menu** (row 1 / row 4 / row 5) is the Captain's and unchanged by anything today.
- **The `K_MAX_CANDIDATES` dense-regime question** stays unauthorised (`0910` §5): the c1 sweep
  ran at ~19 ref decodes/cycle and never tested the dense regime, so it is *untested*, not
  refuted. It goes to the Captain priced if Measurement D's descriptive extras point at a
  capacity ceiling.
- **The DT-as-drift-detector idea** (`1030` §5.2) stays unauthorised. A detector for a bug task 1
  removes is usually the wrong purchase.

## 7. Reference — the citation blacklist, consolidated

It is now spread across five documents. Current state, so nothing has to be reassembled:

| do not cite | instead |
|---|---|
| the ~10–13% / +12.5% / +9.9% **capture-chain effect** | Refuted at n=300. Bound: **≤ ~4–5%, point estimate zero** |
| *"Measurement A shows a monotone density law"* / *"the co-channel withdrawal reverses"* / *"competition is a measured mechanism"* | Not established. **20m-specific deficit of 10–35 pts.** Withdrawal dead; competition a **candidate** |
| `parity ≈ 111.9 − 37.63·log₁₀(density)` as a **predictive** instrument, or any residual against it | **Descriptive of three same-source corpora only.** 1 residual dof; 95% prediction interval at 19.81/cyc = **[50.2%, 76.4%]**; slope CI [−52.0, −22.8] |
| the three anchors' **<1 pt residuals** as evidence the law is accurate | In-sample residuals of a 2-parameter fit to 3 points — small **by construction** |
| *"489135a's 6.4 pt residual shows the two chains differ"* | **Rejected.** Inside the prediction interval. Claim stays **unevidenced**, neither restored nor refuted |
| *"489135a never reached the cliff / degraded, not broken"* ⟨mine⟩ | **False.** drift(14) = **−2.473 s**, corroborated by a measured parity collapse 79.4% → 48.8% → 20.6% |
| *"parity ranges 49.9%–91.6%"* | **53.2%–91.6%**, three clean corpora. 49.9% struck entirely |
| `2026-07-29-5016363/anova_report_40m.md` as a parity source | Do not cite for parity at all |
| *"two capture chains obey the same parity law"* ⟨mine⟩ | Withdrawn; and the stated reason was wrong — the fourth point was **never commensurable** |
| *"`K_MAX_CANDIDATES` is killed as a candidate"* ⟨mine⟩ | **Untested in the dense regime**, not refuted |
| *"the capture defect's code mechanism is not established"* | **Established** — `CycleFramer` syncs to UTC once at startup, then counts samples (`0029` §2.1) |
| *"D-002 closed the SNR bias question"* | Superseded — the residual is a **gain** error (slope 0.6865) |
| the `(b/a)×(d/b)` multiplicativity demonstration | **Circular** — true for any four numbers |
| `1030` §3's task-4 reading rule (rows 1/2) | **Struck** — presumes predictive power the fit does not have |

## 8. Boundaries

- **No `src/`** in anything above except task 1's already-built diff (HK-011: Developer session,
  Captain's sign-off before push).
- **No new arm.** §3 is authorised and already specified; §4 and §5 are corrections and
  housekeeping. Closing handoff §0's stop rule is untouched.
- **No push, no merge** by me (HK-014/HK-010). **No `pre_merge_check.py`** (HK-006) — the
  Captain's trigger only, and never a Developer checklist item.
- **NFR-021** applies to everything above: aggregates only, raw material stays git-ignored.

## 9. Cross-references

- `2026-07-31-0910-…-consolidated-handoff-…md` — the handoff this replaces at §3; its §4 pitfalls
  and §5 amendment still stand.
- `2026-07-31-0853-…-measurement-d-spec-…md` — task 2's spec, current.
- `2026-07-31-1212-…-task4-closes-inconclusive-…md` — closes task 4; §5 lists what survives.
- `2026-07-31-1148-…-row2-suspended-…md`, `2026-07-31-1044-…-drift-definition-corrected.md`,
  `2026-07-31-1030-…-task4-method-ruling-…md` — the task-4 chain, for provenance.
- `2026-07-31-0029-…-measurements-abc-and-drift-root-cause.md` — §1.3 (task 3's escalation),
  §2.1 (the root cause task 1 fixes).
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — where §5's constant belongs.

---

*Per HK-015 this is Architect → QA; every item is QA's to do or route, and the dev-task and PR
material is QA's to author. Per HK-014/HK-010 committed locally, no push, no merge — and per
HK-012 §1 is raised rather than left to lapse. Per HK-011 nothing here touches `src/`. Per
HK-017 filename and byline carry `date -u` UTC, and §1's repo state was read from `git status`
at `3eb0f2d` rather than assumed.*
