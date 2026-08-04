# Arm S.2a — spec: S.1 gate LIFTED, reading rule MECHANISED, reference decoder REMOVED
# ⚠️ A different gate binds: the diagnostic exports are still absent from `main`. Verified today.

**Author:** Architect, 2026-08-04 (18:25 UTC, `date -u`, per HK-017).
**Requested by:** the Captain, 2026-08-04 — *"spec S.2a with the gate lifted and the rule mechanised."*
**Supersedes:** `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` §4 arm S.2a, and
§7 sequencing rule 3.
**Carries forward unchanged:** `2026-07-31-1702-architect-correction-s2a-diagnostic-exports-not-on-main.md`
— **re-verified on `origin/main` today, §5 below.**
**For:** QA (§§2–4 — the arm, if and when it is unblocked) and the Captain (§5 — the cost decision).

---

## 0. Headline, stated before the detail

Three things, in descending order of how much they change the board:

1. **The S.1 gate is lifted.** S.2a no longer waits on S.1. Justification in §1 — Task 3 measured
   the precondition directly, and S.1's own instrument is compromised.
2. **The rule is mechanised, and mechanising it exposed a design defect in rev2's S.2a** that would
   have produced an undefined statistic on one whole stratum. §3. This is the substantive change.
3. **⚠️ Lifting the S.1 gate does not make S.2a runnable.** The binding constraint was never S.1 —
   it is that `ft8_set_candidate_diag_capture` and its LLR sibling **do not exist on `main`**. I
   documented this on 2026-07-31 and verified it again today. **S.2a is not a QA-only arm and this
   spec does not make it one.**

I am putting item 3 at the top rather than in a caveats section because the request was to lift a
gate, and the honest answer is that the gate I was asked to lift is not the one holding this arm.

## 1. Lifting the S.1 gate — the justification

Rev2 gated S.2a on S.1 firing row 2 or row 3 (cycle-global, or both). The gate existed because
S.2a is only worth running if the density penalty has a cycle-global component. Two things have
changed since it was written.

**Task 3 measured the precondition directly, from our own process log.** 4,552 cycles from the
18.96 h decisive epoch of `20260803_live_run_1713`:

```
sat_0 (pass-0 candidates == 140): 2083/4552 = 0.4576
```

stratified cleanly and monotonically by our own decodes/cycle — essentially 0 % saturation below 8,
essentially 100 % above 22, transition concentrated in 13–21. The candidate budget demonstrably
binds, and binds as a function of **cycle-global occupancy**. That is the empirical content the S.1
gate was standing in for, obtained without S.1 and without a reference decoder.

**S.1's own instrument is compromised.** S.1 as specced takes `ALL.TXT` against `jt9_ALL.TXT` — jt9
defines both the density strata and the matched-recall outcome. Under the standing rule, offline
`jt9 -d 3` is not a valid reference leg, and the specific failure mode is hostile to S.1's core
metric: **jt9 emits duplicate `(ts, message)` pairs from its own multi-pass search.** Duplicates of
one signal land at nearly the same frequency, inflating `n_local` hardest at small `W` — which is
exactly where S.1's rule reads (`W = 50 Hz`). That could manufacture a Δ_local out of an instrument
artefact and fire row 1, *"frequency-local ⇒ subtraction architecture"*, the expensive branch, on
nothing. S.1's self-check 4 was drafted before that property was known and I do not believe it
catches this.

**Consequence.** Gating a reference-free arm behind a reference-compromised one is backwards.
**S.2a's S.1 gate is lifted. S.1 is not cancelled** — it still owns the H2-vs-H3 split that S.2a
cannot make — but it needs a jt9-free redesign before it runs, and that redesign is mine and is not
in this document.

## 2. The arm, restated reference-free

**Question, unchanged:** is the material discarded at the `K_MAX_CANDIDATES = 140` boundary *better*
when the band is busy than when it is quiet?

**What changes from rev2:** density is indexed on **our own decodes/cycle**, not on reference
decodes/cycle. No jt9, no WSJT-X, no external decoder anywhere in the arm. Our candidates against
our candidates.

**Corpus:** `artefacts/20260803_live_run_1713/` — 4,614 `owsfz` cycles, 4,971 `owsfz` WAVs
(`qa/ARTEFACT_INVENTORY.md`, scanned 2026-08-04 14:00 UTC, checked fresh before writing this).
Post-`be5960a`, and it carries a **drift screen ROW 5 PASS** over its 18.96 h decisive epoch, which
satisfies rev2 §7's standing prerequisite **by citation, not by re-running it**.

**Restrict to the decisive epoch only** (`openswfz-20260803T185914Z.log`, one process instance =
one epoch by construction). The 1.76 h epoch is excluded — it sits across the 18:58Z heartbeat
stall and the restart boundary, and Task 5 already had to handle that boundary explicitly.

## 3. The defect mechanising the rule exposed — read this before §4

Rev2's method says: *"record the score distribution at the cap boundary — specifically the score of
the 140th-ranked candidate — against the same statistic on the sparse quartile."*

**In sparse cycles there is no 140th-ranked candidate.** Task 3 measured `sat_0 ≈ 0` below 8
decodes/cycle: fewer than 140 candidates are found at all, so the cap never binds and the boundary
score is **undefined**, not merely small. Rev2's comparison is between a stratum where the
statistic exists and one where it does not.

Note where this came from: rev2 inherited *"saturated at the cap (median exactly 140.0) at ~19 ref
decodes/cycle"* from the c1 sweep and generalised it to "the cap binds." Task 3, indexing on **our**
decodes/cycle rather than reference decodes/cycle, shows saturation is a **steep function of
density**, not a constant. The generalisation was wrong and only became visible once someone
measured saturation against density directly.

**The corrected population: saturated cycles only.** The contrast is between cycles that *all*
saturate, split by how dense they are. The question becomes the sharper one anyway — *among cycles
where the cap binds, does it cut into better material as density rises?*

**Cost of the correction, stated honestly.** Restricting to saturated cycles truncates the
available density range from below, so the strata cannot be separated by the 2.0× contrast bar
Measurement D used. §4 sets the bar at 1.5× for this reason. That is a **weaker** separation than
D's and it is a property of the mechanism, not a drafting convenience — I am recording it as a
limitation rather than quietly picking a bar the data can clear.

## 4. The reading rule — mechanical, pre-registered, evaluated in strict order

### 4.1 Population and strata (fixed here, before any number exists)

- **Included:** cycles in the decisive epoch whose **pass-0 candidate count == 140** (saturated).
- **Stratum L (low-density saturated):** our decodes/cycle **∈ [13, 16]**.
- **Stratum H (high-density saturated):** our decodes/cycle **≥ 22**.
- **Excluded:** 17–21, deliberately, to keep the strata non-overlapping with a gap.

Expected yield from Task 3's table: `n_L ≈ 484`, `n_H ≈ 373`. Both clear the floor in §4.3.

### 4.2 Statistic

Per included cycle, one number: **the sync score of the 140th-ranked (lowest surviving) pass-0
candidate.** Let `B_L`, `B_H` be those per-cycle scores in strata L and H.

Define `m_H = median(B_H)`, `med_L = median(B_L)`, `q75_L = 75th percentile(B_L)`.

### 4.3 VOID gates — evaluated FIRST, in order. Any one firing ⇒ VOID, and no row outcome of any kind is reported.

| # | condition | ⇒ |
|---|---|---|
| V1 | `n_L < 300` **or** `n_H < 300` | **VOID** |
| V2 | `median(density \| H) < 1.5 × median(density \| L)` | **VOID** |
| V3 | any included cycle has pass-0 count `!= 140` | **VOID** |
| V4 | the corpus's drift-screen row is not a PASS (cited, not re-run) | **VOID** |
| V5 | permutation null fails (§4.5) | **VOID** |

### 4.4 Reading rule — mutually exclusive, exhaustive, strict order

| # | condition | reading | consequence |
|---|---|---|---|
| **1** | `m_H >= q75_L` | Cap discards **better** material when busy | **H1 SUPPORTED.** S.2b becomes worth its rebuild cost ⇒ return to the Captain **priced**. Do not start it |
| **2** | `med_L < m_H < q75_L` | Partial | **Report as ambiguous. Do not interpret further. Escalate** |
| **3** | `m_H <= med_L` | Cap discards the **same or worse** material when busy | **H1 IS DEAD.** S.2b is **not run**. Re-read against H4, then escalate |

### 4.5 Mandatory permutation null

Shuffle the stratum label (L/H) across the included saturated cycles, **20 times**, recomputing
`m_H − med_L` each time. **The observed `m_H − med_L` must exceed the maximum absolute shuffled
value across all 20 shuffles.** If it does not ⇒ **V5 fires ⇒ VOID**; report the null failure, not
the result.

### 4.6 Reporting

Report `n_L`, `n_H`, both density medians and their ratio, `med_L`, `q75_L`, `m_H`, the 20 shuffled
values, and the full `B_L`/`B_H` distributions as deciles. **NFR-021: aggregates only** — no
callsigns, no message text, in output or committed files.

## 5. ⚠️ The gate that actually binds — and it needs the Captain, not QA

**Verified today on `origin/main`, not recalled:**

| check | result |
|---|---|
| `git grep -l candidate_diag origin/main -- src/` | **NONE** |
| score-bearing lines in `openswfz-20260803T185914Z.log` | **NONE** — counts only |
| `d001-c4-min-score-sweep` (where the exports live) | still unmerged, `2f904f0`, local + remote |

The shipped `[DBG]` lines Task 3 used carry **candidate counts, not scores**. §4's statistic cannot
be computed from anything on `main` today. The 2026-07-31 correction stands in full:

> **Do not cite** *"S.2a needs no rebuild"* or *"the candidate diagnostic exports are already
> shipped"* — both mine, both false.

**Three routes. The decision is the Captain's, and the authorisation attaches to S.2a itself
(HK-011/HK-010), not merely to S.2b.**

| route | what it is | cost | my view |
|---|---|---|---|
| **A** | Port only the two diag exports onto `main` — read-only, default-off, one shim increment | One Developer session + Captain's diff review | **Recommended.** Small, reviewable, doesn't drag 62 commits of sweep work onto `main` |
| **B** | Land `d001-c4-min-score-sweep` | Not cheap — 62 commits, and its `libft8.dll` size delta was already held as a merge blocker until explained | Settles the 07-27 design's absence from `main` too, but it is a much bigger swallow |
| **C** | ⚠️ **Unverified.** `ft8_set_decode_params(k_min_score_pass2, …)` **already exists on `main`** and the DBG lines already log per-pass counts. Sweeping that threshold and watching where the pass-1 count falls below its 200 cap may give the same rivalry test **with zero rebuild** | Possibly QA-only | **Do not plan on it yet.** It tests **pass 1, not pass 0**, so it is an analogue of S.2a and not S.2a. Needs verifying that the setter is reachable without a rebuild and that the counts respond |

Route C is the only one that could make this arm free, and I found it while checking whether a
Developer session was genuinely required (HK-004). It is a lead, not a design. **If you want it,
the check is small and I should do it before anyone commits to route A.**

## 6. What this spec does not do

- **It does not authorise any run.** §5 blocks execution; §§2–4 exist so the rule is pre-registered
  in git *before* data exists, which is the only safeguard in this programme that has actually held.
- **No `src/` change** (HK-011). Route A is a Developer session's work and is **not** authorised
  here — saying so plainly is the exact error the 07-31 correction was written about.
- **No push, no merge** (HK-014/HK-010). Committed locally; I do not ask.
- **It does not resolve S.1.** S.1 needs a jt9-free redesign. Mine, not in this document.
- **It says nothing about D-001's baseline deficit** (mechanism 1), the B.3 menu, or decoder
  quality. No oracle is introduced anywhere in this arm — a discarded candidate is not a known-false
  one, and §4 measures scores, not correctness.
- **Per HK-015** this is Architect → QA material. `dev-tasks/` and `tasks.md` remain QA's to author.

## 7. Honest caveats

- **The 1.5× density separation is weaker than Measurement D's 2.0× bar**, for the structural reason
  in §3. A reader comparing the two should not read 1.5 as a relaxation of discipline; it is the
  most the saturated population supports.
- **Strata bounds were chosen using Task 3's saturation table, which came from the same corpus this
  arm will run on.** That is mild post-hoc selection. It is mitigated by fixing them here in git
  before the boundary scores exist — the outcome variable has never been observed — but it is not
  zero, and V2 plus §4.5's null are what stand between it and a manufactured result.
- **Saturation is not loss.** `sat_0 = 0.4576` says the cap bound in 45.76 % of cycles; it says
  nothing about whether anything valuable was discarded. That is precisely what this arm asks, and
  the honest prior is c1's **+0.93 %** at ~19 ref decodes/cycle — a negative in the sparse regime.
- **H1–H4 are not exhaustive** (rev2 §10, unchanged). Row 3 firing means the mechanism may be none
  of them, and that escalates rather than being rationalised into the nearest candidate.

## 8. Cross-references

- `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` §4, §7 — the design amended.
- `2026-07-31-1702-…-s2a-diagnostic-exports-not-on-main.md` — §5's blocker; re-verified today.
- `qa/rr-study/2026-08-04-1545-qa-to-architect-task3-candidate-saturation-PARTIAL.md` — §1's
  precondition and §3's defect; `sat_0` and its stratification.
- `qa/rr-study/candidate_saturation_check.py` — the instrument that produced them.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — the +0.93 % baseline and S.2b's two pitfalls
  (stack-safety fix; `dotnet run --no-build` does not refresh the native DLL).
- `qa/ARTEFACT_INVENTORY.md` — §2's corpus, checked fresh (`--check` clean) before writing.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:467,504,514-522` — the caps and the stack-array warning.

---

*Per HK-015 this is Architect → QA: a design for QA to scope and author as `dev-tasks/`, not tasks
issued by me. Per HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per
HK-011 nothing here touches `src/`; §5 route A is a Developer session's work and is explicitly not
authorised by this document. Per HK-021 §4 is drafted as the code that would evaluate it — hard
thresholds, consequences as assertions, rows mutually exclusive and exhaustive in strict order. Per
HK-018 §5's table was read from `origin/main` and from the live log today, and §2's corpus from a
freshly `--check`ed inventory, not asserted from memory. Per HK-017 filename and byline carry
`date -u` UTC.*
