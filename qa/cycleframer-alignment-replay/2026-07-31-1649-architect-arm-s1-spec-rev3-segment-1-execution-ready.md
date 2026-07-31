# Arm S.1 — spectral locality — SPEC REV 3, execution-ready on segment 1
# Supersedes rev2 §4. Two method defects found and fixed BEFORE any outcome was computed.

**Author:** Architect, 2026-07-31 (16:49 UTC, `date -u`, per HK-017). Repo at `26168f7`.
**For:** QA — to scope and author as `dev-tasks/`, then execute.
**Requested by:** the Captain, 2026-07-31, on the post-Measurement-D summary.
**Supersedes:** `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` **§4, arm S.1
only**. The rest of rev2 — tracks A and C, S.2a/S.2b, the sequencing in §7, the menu consequence
in §8 — is untouched and still governs.
**Executes:** work order `2026-07-31-1356-…-work-order-after-measurement-d.md` task 2.

---

## 0. Why this revision exists

Rev2 §4 was written at 13:55, **before** the two-session ruling (`1530`) and the segment-2 void
(`1602`). Those two rulings moved S.1's corpus from the pooled 20m corpus to **segment 1 only**,
and in doing so invalidated three of rev2's concrete anchors:

| rev2 §4 said | why it is now wrong | rev3 |
|---|---|---|
| Matching gate reproduces **24,201** | That is the *pooled* two-session count. The per-segment re-run report states explicitly that this gate "does not apply per segment by construction" | **9,751** (segment 1's own matched total) |
| Split cycles at **sparse ≤30, dense ≥43** | Those are the *pooled* cutoffs. Segment 1's own quartile cutoffs are different | **sparse ≤23, dense ≥41** |
| Split decodes at **each stratum's median `n_local`** | **Mechanically degenerate at the reading width.** See §7 | **Fixed integer cuts, §3.3** |

The third of these is not bookkeeping. It would have cost the run a third of its statistical
support and produced a lopsided comparison at exactly the width the reading rule reads. I found it
by computing the neighbour-count distribution rather than by reasoning about it (HK-018); §7 and §8
give the full disclosure.

**Nothing in the reading rule's thresholds has changed.** The 8-point and 3-point bars, the W = 50
Hz reading width, and the W-ladder are carried over from rev2 unedited.

## 1. The question, and what it decides

> Is the density penalty frequency-**local** or cycle-**global**?

| answer | mechanism | what row 4 becomes | cost class |
|---|---|---|---|
| frequency-local | H3 collision / H2 masking | subtractive multi-pass architecture — a large share of what makes jt9 good | **expensive**; strengthens row 5 |
| cycle-global | H1 candidate budget / H4 hash rejection | a constant, plus a harness that already exists | **cheap**; ships incrementally |

These differ by roughly an order of magnitude in engineering cost, and **nothing measured so far
distinguishes them.** That is why this arm runs first and alone.

## 2. Corpus, prerequisite, and cost

- **Corpus:** `artefacts/20260729_live_run_1831-8081/owsfz/20m/` — `ALL.TXT` vs `jt9_ALL.TXT`,
  **restricted to segment 1** (rows before `2026-07-30 00:00:00`, the same cut
  `measurement_d_segment_rerun.py` already applies).
- **Segment 2 is not run.** It is VOID as a density comparison (`1602` V1); running S.1 on it
  would inherit that void. This is a simplification of R4, not a change to it.
- **10m and 80m** remain free replication — each is already a single contiguous segment. Report
  them, **report them as not decisive**, exactly as Measurement D did.
- **Prerequisite:** the drift screen (work order `1356` task 1), amended by `1602` V4 to report
  **per segment**. S.1 needs the screen to clear **segment 1** specifically. If segment 1 shows
  drift approaching 0.5 s, **stop and escalate** — a drift-contaminated corpus manufactures a
  density penalty that is not there, because dense cycles cluster in time and so does drift.
- **Cost:** ~half a QA session. **Frozen artefacts only** — no decode run, no native rebuild, no
  new capture, no `src/` change.

## 3. Method

### 3.1 Reuse, do not reimplement

`measurement_d_within_band_density.py` already provides `stratify_cycles`,
`matched_stratified_bins`, `duplicate_key_rate`, `wilson_interval` and `median_or_nan`;
`anova_common.parse_all_txt` already carries `freq_hz` per decode; `filter_rows_by_window` already
does the segment cut. **S.1 needs no new parsing and no new matching logic.** Reusing D's matching
unmodified is also what makes the matching gate in §6 meaningful.

### 3.2 Unit of analysis and the two exposures

Unit of analysis is **one reference decode**. Outcome is **matched-by-us (1/0)**, resolved by
Measurement D's own matching mechanism — **once, over the full corpus, in reference arrival order,
never re-resolved per stratum or per cell.**

For each reference decode compute:

- **`n_cycle`** — reference decodes in that cycle (Measurement D's density).
- **`n_local(W)`** — reference decodes in the *same cycle* within **±W Hz** of this one,
  **excluding itself**, for **W ∈ {25, 50, 100, 200, 400, 800} Hz**.

### 3.3 The 2×2 — cut points pre-registered as fixed integers

**Density axis** (segment 1's own quartile cutoffs, from the per-segment re-run):

| stratum | cut | cycles | mean ref decodes/cycle |
|---|---|---:|---:|
| sparse | `n_cycle ≤ 23` | 176 | 18.47 |
| dense | `n_cycle ≥ 41` | 159 | 48.86 |

Middle-quartile cycles still participate in the single matching pass (preserving global consumption
order) but are **not tallied into either stratum**, exactly as in Measurement D.

**Locality axis at the reading width W = 50 Hz** — fixed integer cuts, *different per stratum by
design*:

| stratum | `lo` cell | `hi` cell |
|---|---|---|
| sparse | `n_local(50) == 0` | `n_local(50) ≥ 1` |
| dense | `n_local(50) ≤ 1` | `n_local(50) ≥ 2` |

**Why per-stratum cuts rather than one absolute cut.** Dense cycles have more neighbours by
construction; any single absolute cut balances one stratum and starves the other. These two cuts
each split their own stratum near 50/50 (§7). **Δ_local therefore means "more local crowding than is
typical at this density," not a fixed absolute neighbour count** — state that wording in the
write-up, because the alternative reading would be wrong.

Note the sparse `lo` cell is exactly **zero co-channel neighbours** — a clean isolated-signal
reference class, which is the sharpest possible comparison for the collision hypothesis H3.

**At every other W**, use each stratum's own median `n_local(W)`, ties to the low side. Those
widths are diagnostic only and are not read (§4).

### 3.4 Binning and the two reported quantities

Bin reference decodes by the **reference's own reported SNR**, 2 dB bins — never ours (the S7 gain
error, slope 0.6865, would re-enter as noise). Compute matched recall with 95% Wilson intervals in
all four cells, per bin.

Report:

- **Δ_local** = recall(`lo`) − recall(`hi`), computed within each density stratum, then **averaged
  over the two strata**. *Effect of local crowding, cycle occupancy held roughly constant.*
- **Δ_cycle** = recall(sparse) − recall(dense), computed within each locality cell, then **averaged
  over the two cells**. *Effect of cycle occupancy, local crowding held roughly constant.*

Both are **medians across usable bins**, as Measurement D took its own reading.

## 4. Reading rule — PRE-REGISTERED, fixed now, before any outcome exists

**Read at W = 50 Hz only. Evaluate in strict order; first match wins.**

| # | condition | reading | consequence |
|---|---|---|---|
| **0** | `Δ_local ≤ −8` **or** `Δ_cycle ≤ −8` | **Reversal** — crowding *helps*, which no hypothesis predicts | **Escalate. Do not interpret.** Suspect the metric before the mechanism |
| **1** | `Δ_local ≥ 8` **and** `abs(Δ_cycle) < 3` | Penalty is frequency-local | **H3/H2.** Row 4 needs multi-signal handling. Expensive; strengthens row 5. **S.2 is not run.** Escalate before any engineering |
| **2** | `Δ_cycle ≥ 8` **and** `abs(Δ_local) < 3` | Penalty is cycle-global | **H1/H4.** Capacity or budget. **S.2a runs.** A cheap component is likely; strengthens row 4 |
| **3** | `Δ_local ≥ 8` **and** `Δ_cycle ≥ 8` | Two sub-mechanisms | Both proceed. **Report the ratio `Δ_local / Δ_cycle`** — it prices the split |
| **4** | `abs(Δ_local) < 3` **and** `abs(Δ_cycle) < 3` | Effect vanishes under joint stratification | **Measurement D's effect is confounded by something neither variable captures. Escalate. Do not rationalise.** |
| **5** | otherwise | Partial | **Ambiguous. Do not interpret further. Escalate** |

Units are **percentage points** throughout. Bars are hard: `8` and `3`, not "about 8" and "about 3".

**Row 0 is new in rev3** and is the second defect §7 records: rev2's row 4 said "both < 3 pts",
which a strongly *negative* Δ also satisfies — so a reversal would have been reported as "the effect
vanishes." Fixed with `abs()` on rows 1, 2 and 4 plus the explicit row 0. **Fixed before any
outcome existed**; §8 is the disclosure.

**The W-ladder is diagnostic and must be reported at every W**, but the reading is taken at
W = 50 Hz — one FT8 signal width, the scale at which true co-channel overlap occurs. **Do not take
the reading at whichever W looks most decisive.** The *shape* across W separates H3 from H2: a
Δ_local peaking at 25–50 Hz and decaying is overlap; one flat out to 800 Hz is a wideband
normalisation effect. That shape is evidence for whoever scopes the fix — it is **not** a reading.

## 5. Mandatory null

Shuffle `freq_hz` **within each cycle**, recompute `n_local`, recompute Δ_local.

**It must land within ±2 pts of zero.** If it does not, the locality metric is measuring something
structural about how frequencies are distributed, and **the arm is VOID** — report the null failure,
not the result.

**This null is exact, and the §3.3 cut points need no re-derivation under it.** Permuting `freq_hz`
within a cycle preserves that cycle's frequency multiset exactly, so the *marginal distribution* of
`n_local` is preserved to the decode — only its pairing with (SNR, matched) is destroyed. Cell sizes
therefore stay comparable and the fixed integer cuts remain valid unchanged. Run it at least 20
times and report the mean and spread, not a single draw.

## 6. Mandatory self-checks — ALL must pass, or the run is VOID

Evaluated **before** the reading rule. On any failure, **report the self-check failure, not the
arm's result** (standing stop rule, rev2 §7, carried from the 07-27 design §6).

| # | check | pass condition | on failure |
|---|---|---|---|
| **1** | **Matching gate** | Segment 1 total matched count reproduces **9,751 exactly** | VOID — matching has been perturbed; nothing downstream means what it says |
| **2** | **Density contrast** (mechanised, `1602` V3) | `dense_mean / sparse_mean ≥ 2.0` | VOID. Expected **2.65×**; do not evaluate the reading rule |
| **2b** | **Locality contrast** ⟨new, §7⟩ | `mean n_local(hi) − mean n_local(lo) ≥ 1.0` in **both** strata | VOID — the locality cells are not meaningfully separated |
| **3** | **Common support** | **≥ 10 SNR bins** with `n ≥ 20` in **all four** cells | VOID — insufficient support. Expected **18** |
| **4** | **Duplicate-key** | dup-key rate gap across cells **< 1/10** of the measured effect | Confounded; must not be read |
| **5** | **Temporal composition** (`1530` R5) | Satisfied **by construction** — segment 1 is a single contiguous segment | State this explicitly; do not silently omit the check |
| **6** | **Cut reproduction** ⟨new, §7⟩ | At W = 50: sparse splits **1620 / 1631**, dense splits **4359 / 3410** | The `n_local` implementation differs from the one the cuts were chosen on. **Stop and reconcile before proceeding** |

**Self-check 2b uses a difference, not a ratio, deliberately** — the sparse `lo` cell has mean
`n_local` of exactly 0.00, against which a ratio is undefined. This is the same drafting lesson as
`1602` V3 (HK-021): the check is stated as an assertion a script can evaluate, with a hard number.

**Self-check 6 is the strongest gate here.** It is cheap, mechanical, and it catches the single most
likely implementation divergence — an off-by-one in the `±W` boundary (`<` vs `≤`) or a failure to
exclude the decode itself.

## 7. What changed from rev2, and the evidence for it

Rev2 §4 said: *"Within each [density stratum], split decodes at that stratum's median `n_local(W)`."*
I computed the actual `n_local` marginals on segment 1. **That instruction is degenerate at the
reading width:**

| W | stratum | median | ties at median | resulting split |
|---:|---|---:|---:|---|
| 25 | sparse | 0 | 73.5% | **73.5 / 26.5** |
| 25 | dense | 1 | 40.7% | **89.3 / 10.7** |
| **50** | **sparse** | **1** | **34.7%** | **84.5 / 15.5** |
| **50** | dense | 1 | 36.5% | 56.1 / 43.9 |
| 100 | sparse | 1 | 28.9% | 51.4 / 48.6 |
| 100 | dense | 3 | 24.6% | 57.1 / 42.9 |

`n_local` is a **small-integer count with heavy ties**, so at narrow widths the median is not a
median in any useful sense. At W = 50 the sparse stratum would have split **84.5 / 15.5**, and that
starved cell is the binding constraint on every SNR bin.

**Consequence, computed both ways:**

| split rule at W = 50 | usable bins (`n ≥ 20`, all four cells) |
|---|---:|
| rev2's median split | **12** |
| rev3's fixed integer cuts | **18** |

Rev2's rule would have cleared its own `≥ 10` bar with a margin of two bins, on a lopsided
comparison — a run that passes its checks while quietly being much weaker than designed. That is
the same failure shape as `1602`: a check that a run can technically satisfy while its own premise
is unmet.

The fixed cuts also give a cleaner comparison: sparse **49.8 / 50.2**, dense **56.1 / 43.9**, mean
`n_local` 0.00 → 1.38 (sparse) and 0.65 → 2.42 (dense).

**The second defect** — rev2's row 4 firing on a large negative Δ — is fixed in §4 by row 0 and the
`abs()` guards.

## 8. Disclosure: what I computed to write this, and why it cannot leak the reading

Per HK-018 I measured rather than reasoned. Being precise about exactly what was measured matters
here, because I am the author of the reading this arm could overturn (rev2 §10 makes that
declaration and it still stands).

**What I computed:** the marginal distribution of `n_local(W)` over segment 1's *reference* decodes,
the resulting cell sizes, and the per-SNR-bin cell counts.

**What I did not compute, at any W, in any cell:** matched recall, Δ_local, Δ_cycle, or any quantity
derived from the outcome variable. The probe never calls `matched_stratified_bins`.

**Why this cannot pre-empt the result.** Δ_local and Δ_cycle are functions of *matched recall*.
Choosing strata from the **exposure** distribution without reference to the **outcome** is standard
practice and cannot bias the comparison — it is the same act as Measurement D choosing its density
quartiles from the density distribution. Had I chosen cut points after seeing recall, that would be
a researcher degree of freedom and this arm would be worthless.

**Corroboration that the probe is using D's own logic:** it reproduces the published segment-1
stratification exactly — 618 cycles, 176 sparse / 159 dense, means **18.47** and **48.86**, cutoffs
**≤23 / ≥41**. Those are not fitted; they fell out of `stratify_cycles` unmodified.

**Reproduction:** the probe is scratch, under the git-ignored `_work/`. QA should not depend on it —
self-check 6 exists so QA's own independent implementation is verified against these marginals
rather than inheriting mine.

**The pre-registration that matters** is this document committed to git before QA runs anything,
exactly as `0e23697` was for Measurement D. That safeguard works because it does not depend on
anyone being reliable — which, per `1344`, is more than can be said for the one I advertised last
time.

## 9. Escalation, boundaries, and what this does not authorise

**Escalate rather than interpret on rows 0, 1, 4 and 5.** Row 1 is a menu-level fact about row 4's
cost; rows 0, 4 and 5 are ambiguity or instrument failure. **None of the four is QA's to resolve**,
and none of them is a prompt to go looking for a third variable that rescues the result.

**Only row 2 or row 3 opens anything** — S.2a, and only S.2a.

- **No `src/`, no native rebuild** (HK-011). S.1 is frozen artefacts and Python only.
- **No new corpus gathering.** A fresh contiguous 20m capture is a separate open item with the
  Captain; S.1 does not need it and must not wait for it.
- **No push, no merge** (HK-014/HK-010) — this is committed locally and stops there. I do not ask.
- **No `pre_merge_check.py`** (HK-006) — the Captain's trigger only.
- **NFR-021:** aggregates and counts only. `n_local` is computed from `freq_hz`; message text is
  read solely to build the match key and is never printed or written out. Real callsigns are touched
  only inside git-ignored `artefacts/`.
- **Per HK-015 this is a design, not a task.** `dev-tasks/*.md` and `tasks.md` are QA's to author.
- **Rev2's stated limitation stands:** S.1 controls the target decode's own SNR but **not its
  neighbours' strength**. It separates local from global cleanly; it does **not** decisively separate
  H2 from H3. If row 1 fires, expect to need one more arm, priced then rather than pre-committed now.
- **Descriptive extra, not rule-bound:** repeat with neighbour *power* (sum of neighbour SNRs within
  W) in place of neighbour *count*. Masking should track power; collision should track proximity. A
  lead for whoever scopes the fix, not a finding.

## 10. Cross-references

- `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` §4 — the spec this revises;
  §§5–8 untouched and still governing.
- `2026-07-31-1356-…-work-order-after-measurement-d.md` §1 — the drift-screen prerequisite, §2 —
  this arm's place in the queue.
- `2026-07-31-1530-…-corpus-is-two-sessions.md` — R4/R5, why the corpus is per-segment.
- `2026-07-31-1602-…-segment-2-void-on-self-check-2.md` — V3 (contrast gate), and §6 "Not affected"
  (S.1 is segment 1 only).
- `measurement_d_segment_rerun_report.md` — segment 1's cutoffs, matched total 9,751, contrast
  2.65×, 21 bins.
- `2026-07-31-1344-…-withheld-figures-do-not-exist.md` — why §8 is written as explicitly as it is.
- `measurement_d_within_band_density.py`, `qa/endurance/anova_common.py` — the tooling S.1 extends.

---

*Per HK-015 this is Architect → QA: a design for QA to scope and author as `dev-tasks/`, not tasks
issued by me. Per HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per
HK-011 nothing here touches `src/` or native code. Per HK-017 filename and byline carry `date -u`
UTC. Per HK-021 every check in §6 is stated as a mechanical assertion with a hard threshold and an
explicit consequence, and the §4 rows are mutually exclusive in strict order. Per HK-018 §3.3's cut
points, §6's expected figures and §7's tables were computed from the corpus, not asserted — and §8
states exactly what was and was not computed.*
