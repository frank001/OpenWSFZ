# Architect → QA — work order after Measurement D
# Five items. One is a measurement, two are prerequisites, two are routing.

**Author:** Architect, 2026-07-31 (13:56 UTC, `date -u`, per HK-017). Repo at `0a42719`.
**For:** QA. Every item below is QA's to do or to route; none of it is mine to apply.
**Supersedes:** the work queue in `2026-07-31-1222-…-outstanding-work-after-task4.md` §0, all four
items of which are now **closed** — including the two that were open measurements.
**Design this executes:** `2026-07-31-1355-architect-row4-decomposition-rev2-competition-scoped.md`.
**Standing reference remains** `2026-07-27-2012-…-d001-closing-handoff.md` §0.

---

## 0. The board

| # | item | status | cost |
|---|---|---|---|
| **1** | **Drift screen on 8081/20m** — confirm Measurement D's own corpus | **Do first (§1)** | ~1 h |
| **2** | **Arm S.1 — spectral locality** | **The only open measurement (§2)** | ~half a session |
| 3 | Route the drift-fix push sign-off | Not started (§3) | minutes |
| 4 | Resolve the 07-27 design's branch location | Not started (§4) | QA's call |
| 5 | Everything else | **Gated — do not start (§5)** | — |

**Authorisation note.** S.1 is a **new arm**, and `1222` §8 barred new arms. The Captain asked for
this work order off the back of the rev2 design, which I am reading as authorising items 1 and 2
and nothing beyond them. **If that is not what was intended, say so before QA starts** — I would
rather stall a day than have QA burn a session on an arm that was not actually opened.

## 1. Task 1 — drift screen on 8081/20m ⟨do before S.1⟩

**Why this is ahead of the measurement.** The rev2 design added a standing prerequisite: every
arm's corpus must pass a drift screen first, because **dense cycles cluster in time and so does
drift** — a contaminated corpus manufactures a density penalty that is not there. S.1 measures a
density penalty. The prerequisite applies to S.1 before it applies to anything else.

**What the record already says.** `DEFECT-capture-clock-drift-silent-decode-loss.md` §2.4 lists
`20260729_live_run_1831-8081` (10m/20m/80m, Voicemeeter B1 / SDR Uno) at drift **~0**, *"stable
parity throughout."* So the expected answer is **clean**, and this task is a confirmation, not an
investigation.

**Why confirm it anyway.** That record is **qualitative** — "stable parity throughout" — not a
measured drift figure like 489135a's `drift(14) = −2.473 s`. And task 4's whole finding was that a
corpus previously believed sound had in fact reached the cliff in its final hours. That is a direct
precedent, on the same programme, from today. An hour of measurement against a repeat of that is
proportionate.

**Method.** Produce a per-hour DT-slope figure for 8081/20m, on the DT-derived method ruled valid
at `1030` and corrected at `1044`. Two existing scripts do this work but **both hardcode their
corpus paths at module level**:

- `verify_dt_drift_489135a.py` — DT slope per elapsed hour, ppm, with a WSJT-X flatness control.
  Hardcoded to `20260728_live_run_2354-8080`.
- `measure_drift_8080_session.py` — per-cycle cross-correlation drift. Hardcoded to
  `20260729_live_run_1831-8080`; heavier, and needs a WSJT-X WAV pair 8081/20m may not have.

**The cheap route is to generalise the first one's paths to arguments** rather than write a third
script. That is the reusable drift screen the rev2 design's prerequisite assumes exists — it does
not exist yet in reusable form, and saying so plainly is better than implying it is turnkey.

**Reading, fixed now:**

| result | consequence |
|---|---|
| Drift stays well inside \|drift\| < 0.5 s across the session | Screen passes. **S.1 proceeds on the full corpus.** Record the figure against the defect report's §2.4 row, replacing the qualitative entry |
| Drift approaches or crosses 0.5 s at any point | **Stop. Escalate before running S.1.** S.1 would then need a healthy-window restriction — and Measurement D's own result would need re-reading against the same window |

The second outcome is not expected. It is written down because task 4's was not expected either.

## 2. Task 2 — Arm S.1, spectral locality ⟨the only open measurement⟩

**Full specification: rev2 design §4, arm S.1.** Not restated here — read it there, because the
reading rule, the W-ladder, the mandatory null and the four self-checks are all pre-registered in
that document and **must be quoted verbatim in the write-up and not edited after results are
seen.** That discipline is the only reason Measurement D is trustworthy today (see §6).

Summary of what it costs and touches, so it can be scoped without re-reading:

- **Question:** is the density penalty frequency-**local** (collision) or cycle-**global**
  (candidate budget)? These cost an order of magnitude apart in engineering.
- **Corpus:** `artefacts/20260729_live_run_1831-8081/owsfz/20m/` — `ALL.TXT` vs `jt9_ALL.TXT`.
  20m decisive; 10m/80m free replication, reported not decisive.
- **Cost:** ~half a QA session. **Frozen artefacts only** — no decode run, no native rebuild, no
  new capture, no `src/`.
- **Tooling already exists and should be extended, not reimplemented:**
  `measurement_d_within_band_density.py` already provides `stratify_cycles`,
  `matched_stratified_bins`, `duplicate_key_rate` and `wilson_interval`; `anova_common.parse_all_txt`
  already carries `freq_hz` per decode. S.1 needs **no new parsing and no new matching logic** —
  reusing D's matching unmodified is also what makes the matching-gate self-check meaningful.

**Four things that will decide whether this run is trusted:**

1. **The matching gate must reproduce 24,201 exactly.** If it does not, the run is void — the
   matching has been perturbed and nothing downstream means what it says.
2. **The shuffled-frequency null must land within ±2 pts of zero.** This is the arm's own
   falsification test. If it does not, the locality metric is measuring something structural about
   the frequency distribution and **the arm is void** — report the null failure, not the result.
3. **The rule reads W = 50 Hz only.** Report the full W-ladder, but do not take the reading at
   whichever W looks most decisive. That choice is fixed in advance for a reason.
4. **Rule row 4 (both effects vanish) escalates, it does not get rationalised.** If joint
   stratification kills the effect, Measurement D is confounded by something neither variable
   captures, and that is a finding — not a prompt to find a third variable that rescues it.

**Escalate rather than interpret on rows 1, 4 and 5.** Row 1 is a menu-level fact about row 4's
cost; rows 4 and 5 are ambiguity. None of the three is QA's to resolve.

## 3. Task 3 — route the drift-fix push sign-off

Unchanged from `1222` §2 and still not done. The fix is committed on branch
`fix-cycleframer-clock-drift-boundary-resync` (`5a90d85`, `5c283da`) and **is not on `main`**.

1. **Raise the push sign-off with the Captain** — HK-011/HK-010. Per HK-014 that request is not
   mine to make, which is why it is still sitting here.
2. `pre_merge_check.py` runs on the **Captain's trigger only** (HK-006) — not QA's judgement call,
   and never a Developer checklist item.
3. Two notes for the PR description, both reasoning that a later maintainer will otherwise
   "simplify" away:
   - The resync is **lazy** (at the next window's first sample) rather than eager (at window
     close) because time lost to a slow crystal *or to a silently dropped chunk* has not elapsed
     yet at window close. That covers both failure paths, not just the crystal.
   - `5c283da`'s `windowDialFreq` fix exists **because** the resync is lazy — the snapshot timing
     had to move with it. It is not an unrelated tidy-up and should not be dropped from the PR.

**Until this merges**, `0910` §4.5 stands: fix it, or cap sessions below ~12 h, before gathering
any further long-session corpus (HK-020).

## 4. Task 4 — the 07-27 design is not on `main`

`2026-07-27-1730-architect-row4-scoping-design.md` exists **only on branch
`d001-c4-min-score-sweep`**. The rev2 design on `main` now carries three of its arms (R.1/R.2/R.3)
forward as live work, so **a document on `main` cites one that is not there.**

**QA's to resolve** — cherry-pick onto `main`, fold into the branch disposition, or otherwise. I am
flagging it, not directing it. Note that `d001-c4-min-score-sweep`'s disposition was already open
and blocking on the Captain before today, so this may fold into that decision rather than needing
its own.

## 5. Gated — do not start

Named explicitly so nothing gets picked up out of completeness:

| item | gate |
|---|---|
| **S.2a** (cap-boundary score distribution) | Gated on **S.1 firing rule row 2 or 3**. If S.1 fires row 1, S.2 is not run at all |
| **S.2b** (dense-regime cap sweep) | Gated on S.2a **and** on the Captain, **priced** — native rebuilds are a different cost class |
| **S.3** (does jt9 suffer the same penalty?) | Authorised by nobody yet. Runs last, always, but not now |
| **Track A** — R.1, R.2, R.3 | Carried forward from 07-27, **demoted below S.1**, not dropped. Not authorised to start |
| **The row 1 / row 4 / row 5 menu** | The Captain's, unchanged |
| **`K_MAX_CANDIDATES` in the dense regime** | Still *untested, not refuted*. It reaches the Captain priced **via S.2a's result**, not before |

**No new arm beyond S.1.** The closing handoff §0 stop rule is untouched.

## 6. One thing worth carrying into how S.1 is run

Measurement D is trustworthy today for one reason that survived scrutiny: **its reading rule was
committed to git at `0e23697` before QA ran anything.** That is checkable by anyone, independent of
anyone's memory or good faith.

The other safeguard I advertised for that run — a blind comparison against exploratory figures I
claimed the Captain held — **never existed**; see
`2026-07-31-1344-architect-correction-measurement-d-withheld-figures-do-not-exist.md`. QA relied on
it in good faith and it was fiction. My error, corrected on the record.

The lesson is not about that mistake. It is that **pre-registration in git is the safeguard that
actually works**, because it does not depend on anyone being reliable. S.1's rule is already
committed at `0a42719`. Quote it verbatim, do not edit it after seeing numbers, and the arm will
stand on its own the way D did.

## 7. Boundaries

- **No `src/`** in anything above (HK-011). Task 3 is routing an already-built diff, not touching
  it. S.2b's rebuilds are gated and would be a Developer session's work.
- **No push, no merge** by me (HK-014/HK-010); the sign-off request in §3 is QA's to raise.
- **No `pre_merge_check.py`** (HK-006) — the Captain's trigger only.
- **No new corpus gathering** — every arm runs on frozen artefacts. And per HK-020, none should be
  gathered until §3 merges or sessions are capped below ~12 h.
- **NFR-021:** aggregates only; raw material stays git-ignored. S.1 touches real callsigns only
  inside `artefacts/` and must print counts only.
- **Per HK-015 this is Architect → QA.** `dev-tasks/*.md` and `tasks.md` are **QA's to author** —
  the items above are work to be scoped, not tasks issued by me.

## 8. Cross-references

- `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` — the design; §4 is S.1's full
  spec, §7 the sequencing and stop rules, §8 the menu consequence.
- `2026-07-31-1344-…-withheld-figures-do-not-exist.md` — §6's correction.
- `2026-07-31-1245-qa-measurement-d-result-competition-confirmed.md` — the result S.1 follows up;
  §6.2 is where the two-mechanism reading comes from.
- `2026-07-31-1222-…-outstanding-work-after-task4.md` — the queue this replaces (all four closed);
  §7's citation blacklist still stands unchanged.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` §2.4 — the 8081 row task 1 confirms and
  replaces with a measured figure.
- `qa/cycleframer-alignment-replay/measurement_d_within_band_density.py`,
  `qa/endurance/anova_common.py` — the tooling S.1 extends.
- `qa/cycleframer-alignment-replay/verify_dt_drift_489135a.py` — task 1's starting point, corpus
  paths to be generalised.

---

*Per HK-015 this is Architect → QA; every item is QA's to do or route, and the `dev-tasks/` and PR
material is QA's to author. Per HK-014/HK-010 committed locally, no push, no merge — and per HK-012
§3 is raised rather than left to lapse. Per HK-011 nothing here touches `src/`. Per HK-017 filename
and byline carry `date -u` UTC. Per HK-018 §1's tooling limitations and §2's reuse claims were read
from the scripts themselves, and §1's expected answer from the defect report's own table, rather
than assumed.*
