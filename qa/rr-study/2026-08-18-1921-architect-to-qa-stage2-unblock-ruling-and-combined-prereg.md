# Architect → QA: Stage 2 is UNBLOCKED. The combined pre-registration, and two code findings that change its design

**Author:** Architect
**Date:** 2026-08-18 19:21Z (mechanically derived, HK-017; filename timestamp agrees)
**Repo state at authoring:** `qa/n1-ber-results` @ `2a1fb4e`, working tree clean
**DLL pin, re-hashed from disk while drafting (not inherited from a label):**
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` = `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`
**Supersedes:** §6 of `2026-08-18-1616-architect-to-qa-p-live-stage1-ruling-anchor-provenance-defect.md`
(the Stage 2 block) — **that section only.** Everything else in the 16:16Z ruling stands.

---

## 0. Verdict

🔴 **CAPTAIN'S RULING, 2026-08-18: Stage 2 is UNBLOCKED, on a combined pre-registration in which the
anchor-offset question is pursued on its own terms AND serves as Stage 2's ROW 0.** The 16:16Z
ruling's §6 sequencing condition ("ROW B **or the Captain rules otherwise**") is discharged by the
second limb, not the first. ROW A fired; the Captain has ruled otherwise; Stage 2 arms.

**This document is the gate.** It is written before any Stage 2 harness exists, per HK-021.

🛑 **Stages 3 and 4 remain BLOCKED.** They were blocked by the same §6 and the Captain's ruling names
Stage 2 only. Do not infer their release from this document.

🔴 **Two findings from a code read while drafting change the design of this arm, and one of them is
a defect in a gate of my own that QA is about to reuse.** They are §1 and §2. Read them before the
gate; the gate does not make sense without them.

---

## 1. Finding 1 — the refiner's search window is ±70 ms. The anchor error is 650 ms.

Verified from source this session, not inferred:

```
native/ft8_lib_vendor/refine/sync_refiner.c
  :89   #define REFINE_COARSE_TIME_HALF_SAMPLES 12   /* +/-12 @ 200 Hz = +/-60 ms */
  :92   #define REFINE_FINE_TIME_HALF_MS 10.0f
  :454  *out_delta_time_s = dt_coarse_s + dt_fine_s;
  :90   #define REFINE_FREQ_HALF_HZ 2.5f
```

⇒ **`|delta_t|` is hard-bounded at 0.060 + 0.010 = 0.070 s. `|delta_f|` is hard-bounded at 2.5 Hz.**

And `run_n1.py:measure_row` hands the anchor to the refiner as well as to the extractor:

```
rc_grid, llr_grid = ex.extract_at(pcm, float(anchor_freq), anchor_dt)
delta_f, delta_t, ... = refiner.refine(pcm, anchor_freq, anchor_dt)
```

🔴 **Consequence for the block that was in place: at the raw anchor, the anchor error (+0.65 s) is
~9× the refiner's ENTIRE time search half-range.** The refiner would have been searching a window
that provably does not contain the answer, and `d_ber` would have been a difference between two
readings of noise. **The block was correct for a stronger reason than the one I gave for it** — I
argued "identically unreadable"; the truth is "structurally unreachable."

🔴 **Consequence for the arm now being armed: this is exactly why the corrected anchor is
load-bearing rather than cosmetic.** At `anchor_dt + 0.65 s` the refiner's ±70 ms window plausibly
contains the true position. At `anchor_dt` it cannot. **ROW 0e below exists to check that claim
rather than assume it.**

### 1.1 The refiner is measurably railed against that window — on N1's own committed data

HK-018: I checked rather than reasoned. Recomputed from
`qa/rr-study/n1-ber-at-refined-position/results/n1_results.json` (405 rows, the committed N1 run):

| quantity | value |
|---|---|
| `median |delta_t|` | 0.0540 s (N1's ROW 0d figure, reproduced exactly) |
| **`max |delta_t|`** | **0.0700 s — exactly the hard ceiling** |
| rows with `|delta_t| ≥ 0.060 s` (coarse half-range) | **147 / 405 = 36.3%** |
| rows at the hard ceiling `0.070 s` | **22 / 405 = 5.4%**, and it is the **modal value of the whole distribution** |
| `median |delta_f|` | 1.500 Hz (N1's ROW 0d figure, reproduced exactly) |
| **rows at the frequency rail `2.5 Hz`** | **108 / 405 = 26.7%** |

🔴 **N1's ROW 0d — "median |dt| = 54 ms, median |df| = 1.5 Hz ⇒ the refiner genuinely moves the
position" — passed while reading a TRUNCATED distribution.** The refiner does move. But for a large
minority it is pinned against its own search boundary and the returned delta is **the window edge,
not an estimate.** A median at 77% of a hard ceiling, with the ceiling as the modal value, is the
signature of a rail. This is the structural-ceiling check HK-021(i) asks for, and neither the N1
spec nor the N1 report ran it.

🛑 **WHAT THIS DOES NOT DO. It does not overturn N1's ROW 2 and it does not reopen limb 1 or R2.**
N1 measured *the refiner as configured*, and as configured is what ships. "Refinement does not help"
remains true of the thing we have. What is now open, and is **NOT settled in this document**, is
whether it is also a statement about position refinement in general or partly a statement about a
±60 ms / ±2.5 Hz window. 🔴 **That earns its own pre-registration. It is not this arm, QA must not
fold it in, and I must not adjudicate it in prose** — I am recording the measurement and stopping.

⚠️ **N1's anchor was convention-clean** (`candidate_diag.csv`'s own grid position, ours), so the
railing above is **not** an anchor artefact. It is a property of the search window. Do not conflate
the two.

---

## 2. Finding 2 — N1's ROW 2 gates on `|d_ber|`. That is HK-021(l), and it is my sixth.

```
run_n1.py:57   ROW_2_D_BER_ABS_MAX = 0.05   # 5 pp -- ROW 2
run_n1.py:343  row2_fires = abs(d_ber_pt) <= ROW_2_D_BER_ABS_MAX and ci_hi < ROW_2_CI_HI_MAX
```

On N1 this never bit — `d_ber` was −0.57 pp, comfortably inside ±5 pp either way. **On P-LIVE it
would.** N1's own per-population breakdown found refinement **harmful at −4.02 pp** on the
strong-candidate stratum. If that replicates on the miss population at, say, −4 pp, then
`|d_ber|` = 4 pp ≤ 5 pp and **ROW 2 fires and reports "no material effect" over a real harm.**

🔴 **HK-021 sibling (l) — never gate on `|x|` where a signed statistic exists — SIXTH occurrence,
all six Architect-authored.** `n1_stats.d_ber_row` is explicitly signed ("Positive = refinement
helped") and its sibling `f_cross_row` carries a docstring explaining why *it* refuses to pool
directions. I wrote that docstring and then wrote the absolute value into the row beneath it.

⇒ **Stage 2 does NOT reuse N1's ROW 2 as written.** §4's ROW 2 is signed, and a separate **ROW 3
(HARM)** exists so the gate can express the outcome N1's own gate could not. **ROW 1's definition is
reused verbatim** so the benefit branch remains a like-for-like replication.

---

## 3. Population, and how the offset is derived

**Corpus: `PRIMARY_CORPUS = "20260803_live_run_1713"` ALONE** (Amendment A4.2 — one confirmatory
population, single verified audio path, 18.96 h contiguous). The other four corpora appear in §7
only, and only descriptively.

Two populations, both from `plive_population.py`, both from the same `ALL.TXT` pair and the same
`wsjt-x/wav/`:

| population | builder | membership | role here |
|---|---|---|---|
| `P-HIT` | `build_p_hit_population()` | WSJT-X decodes our `ALL.TXT` **also** contains for that `ts` | **derives** the offset; positive control |
| `P-LIVE` | `build_p_live_population()` | WSJT-X decodes our `ALL.TXT` **does not** contain for that `ts` | **Stage 2's target** |

🔴 **The offset is DERIVED ON `P-HIT` AND APPLIED TO `P-LIVE`. That is the whole point and it is not
circular** — the population the number is fitted on and the population it is used on are disjoint by
construction.

🔴 **Anchoring from WSJT-X's DT is not a choice.** `P-LIVE` has no `candidate_diag.csv` — that is
the founding premise of the P-LIVE spec (§2). N1 could anchor from our own candidate positions;
Stage 2 cannot. The offset is therefore unavoidable, not a convenience.

**Derivation procedure (Part A):**

1. Build `P-HIT` on PRIMARY. Sample by seeded RNG (`seed = 20260818`, sort-stabilised) **or run the
   full population if compute allows** — state which, and report **rows AND clusters**.
2. Sweep `dt_offset` over `m3_common.TIME_ANCHOR_OFFSETS_S` — **49 points, −1.20…+1.20 s, 0.05 s
   step — reused VERBATIM.** V0 arm only (`ft8_extract_llrs_at`), no refiner, no V3.
3. `OFFSET := argmin_offset median(BER_V0)`. Report the full 49-point table.

🛑 **Do NOT hardcode +0.65 s.** Stage 1R measured it on a 600-row sample; re-derive it here on this
round's own population and let ROW 0c/0d accept or reject it. **If the re-derived `OFFSET` differs
from +0.65 s by more than one grid step (0.05 s), report that prominently — it is a finding about
the sample, not a nuisance.**

⚠️ **`build_p_live_population()` does NOT sort its output; `build_p_hit_population()` does** (the
latter's docstring says why — the hash-randomised-set-iteration rule). P-LIVE's order follows
`parse_all_txt`'s file order and is therefore deterministic, so this is not a live bug — **but if
Stage 2 samples P-LIVE with a seeded RNG, sort at construction first**, matching P-HIT. Determinism
must be **mechanically diffed across two runs, never asserted** (standing rule).

⚠️ **`compute_matched_hit_control(..., limit=N)` TRUNCATES IN FILE ORDER** (`c2_phase2c_ber_measurement.py:291-316`).
If any control figure in this round comes from it, **report cluster counts, never row counts alone.**

---

## 4. The gate — strict order, first match wins

`B50 = 0.113`. `d_ber` is **signed**, positive = refinement helped. All bootstraps: cluster over
`ts`, `n_draws = 2000`, `n1_stats.cluster_bootstrap_median_diff` reused **verbatim**.

| Row | Condition | Bar | Class | Consequence if it fires |
|---|---|---|---|---|
| **0a** | DLL SHA256 re-hashed **from disk** before arming, asserted against the pin in the header | exact match | VALIDITY | **STOP** |
| **0b** | `P-LIVE` measured size on PRIMARY | **< 500 rows OR < 200 clusters** | VALIDITY | **STOP**, underpowered |
| **0c** | median `BER_V0` on `P-HIT` at the swept `OFFSET` | **outside [1.0%, 15.0%]** — two-sided | VALIDITY | **STOP.** Above ⇒ no anchor was found. Below ⇒ implausibly good, suspect a closed loop |
| **0d** | Split `P-HIT` into **4 disjoint chronological `ts` quartiles**; sweep each independently. Per-stratum `argmin` offset vs pooled `OFFSET` | **any stratum differs by > 0.05 s (one grid step)** | VALIDITY | **STOP, escalate.** The offset is not a constant, so no single correction is applicable |
| **0e** | On `P-LIVE` at the corrected anchor: `frac_rail_t` = fraction of rows with `|delta_t| ≥ 0.0695 s` | **≥ 0.50** | VALIDITY | **STOP, escalate.** The refiner is railed on the majority; `d_ber` measures the window edge, not refinement |
| **0f** | On `P-LIVE` at the corrected anchor: `median|delta_t|` and `median|delta_f|` | **`median|delta_t| ≤ 0.005 s` OR `median|delta_f| ≤ 0.25 Hz`** (N1's own 0d floors, reused) | VALIDITY | **STOP.** The treatment cannot move; there is nothing to measure |
| **0g** | median `ber_grid` on `P-LIVE` at the corrected anchor | **outside [8%, 40%]** — two-sided | VALIDITY | **STOP, escalate.** Above ⇒ chance-level, `d_ber` is a difference of two noise readings (structural, not a refinement result). Below ⇒ suspiciously good on a population we failed to decode ⇒ suspect a membership leak |
| **ROW 1** | **BENEFIT** — `d_ber ≥ +15 pp` AND `CI_lo > +5 pp` AND `f_cross ≥ 20%` | N1's ROW 1, **verbatim** | — | Refinement helps materially on the miss population. 🛑 **Does NOT rehabilitate R2** — see §8 |
| **ROW 3** | **HARM** — `CI_hi < 0` AND `d_ber ≤ −2 pp` | — | — | **N1's −4.02 pp harm REPLICATES at scale.** Limb 1 is not merely dead but actively costly; strengthens N1's ROW 2, does not soften it |
| **ROW 2** | **NULL** — `CI_hi ≥ 0` AND `CI_lo > −5 pp` AND `CI_hi < +15 pp` AND `−5 pp ≤ d_ber ≤ +5 pp` | — | — | No material effect either way. N1's ROW 2 replicates at ~58× the clusters |
| **ROW 4** | residue — none of the above | — | — | Report the interval, **do not pick a side**, escalate |

**Mandatory alongside the gate, reported whether or not it fires:**

- `f_cross` (`n1_stats.f_cross_row`, verbatim) with its cluster CI **and its rule-of-three bound if
  `n_cross = 0`** — the bootstrap CI is degenerate by construction at zero (my own N5 defect).
- **`frac_rail_t` and `frac_rail_f`** (`|delta_f| ≥ 2.495 Hz`). 🔴 **`frac_rail_f` is DESCRIPTIVE and
  deliberately ungated — I have no principled bar for it and inventing one would be theatre.** It is
  the §1.1 measurement carried onto a second population and it is a required deliverable.
- A **decile table of `ber_grid`** over `P-LIVE` (the A4.3 structural-ceiling disclosure).
- The full 49-point sweep table from Part A.

### 4.1 Mutual exclusivity, proved

- **ROW 1 vs ROW 3:** ROW 1 requires `CI_lo > +5 pp` ⇒ `CI_hi ≥ CI_lo > 0`; ROW 3 requires
  `CI_hi < 0`. Disjoint on the sign of `CI_hi`.
- **ROW 2 vs ROW 3:** disjoint on a scalar partition of `CI_hi` at **0** (`≥ 0` vs `< 0`).
- **ROW 1 vs ROW 2:** disjoint on a scalar partition of `d_ber` at **+5 pp / +15 pp**.

⚠️ **I got this wrong in a first draft** — a signed ROW 2 without the `CI_hi ≥ 0` clause overlaps
ROW 3 (e.g. `d_ber = −3 pp`, `CI = [−4.5, −0.5] pp` satisfies both). Strict order would have hidden
it. The clause is there to make exclusivity provable rather than merely ordered.

### 4.1a Exclusivity verified mechanically, not argued

HK-021 says draft the gate by **writing the code that evaluates it**. Done, while drafting:
an exhaustive sweep of `(d_ber, CI_lo, CI_hi)` over −0.30…+0.30 in 0.005 steps × six `f_cross`
values, keeping only physically consistent triples (`CI_lo ≤ d_ber ≤ CI_hi`).

**1,815,726 consistent combinations tested. ZERO inputs fire more than one row.** The exclusivity
in §4.1 is verified, not asserted. (Scratch script, not committed — the claim is what matters and
it is reproducible from §4's table in ten lines.)

### 4.1b The gate replayed against N1's own committed numbers

The strongest available check that this gate is a **like-for-like replication** and not a new
instrument. N1's real results (`n1_gate_report.json`) pushed through §4's rows:

| N1 population | `d_ber` | CI95 | Stage 2 row | N1's own verdict |
|---|---|---|---|---|
| pooled (n=405, 67 cl) | −0.57 pp | [−1.15, +0.00] pp | **ROW 2** | ROW 2 ✅ agrees |
| `THE 567` (n=279) | +0.00 pp | [+0.00, +0.00] pp | **ROW 2** | — |
| `THE 135` (n=126, p=0.000) | **−4.02 pp** | **[−6.90, −2.30] pp** | 🔴 **ROW 3 (HARM)** | ROW 2 ("no material effect") |

🔴 **The last line is §2's defect, demonstrated rather than argued.** Under N1's own rule
`|−4.02| = 4.02 ≤ 5` and `CI_hi = −2.30 < 15`, so **ROW 2 fires and reports "no material effect"
on a harm whose CI excludes zero at p = 0.000.** The signed gate separates it correctly. The pooled
line agreeing confirms the replication is still like-for-like where it should be.

### 4.2 HK-021(m) — what this gate can resolve, stated while drafting

N1's clustered SE on `d_ber` was **0.434 pp at 67 clusters**. Stage 1 measured `P-LIVE` on PRIMARY at
**15,389 rows / 3,917 clusters**. Scaling by `√(67/3917) = 0.131` ⇒ **expected SE ≈ 0.057 pp**,
`1.96·SE ≈ 0.11 pp`.

**The bars are 2 pp / 5 pp / 15 pp — between 18× and 130× the resolution. No straddle risk on the
primary.**

🔴 **That extrapolation assumes `P-LIVE`'s per-row `d_ber` spread resembles `THE 135`/`THE 567`'s,
and it may not** — on a population sitting near chance, both arms are noisy and the paired spread
could be materially wider. **QA reports the ACTUAL clustered SE and, if `1.96·SE` exceeds 1 pp,
says so plainly rather than letting my estimate stand.** ROW 4 exists for the case where it does.

### 4.3 HK-025 — classification, both branches evaluated

I have evaluated every ROW 0 under **both** outcomes and believe none is DIAGNOSTIC:

| row | if it fires | if it clears | same verdict? |
|---|---|---|---|
| 0a | STOP — wrong binary | proceed on a pinned binary | **no** |
| 0b | STOP — underpowered | proceed | **no** |
| 0c | STOP — no usable anchor exists | the offset is real and usable | **no** |
| 0d | STOP — offset is per-cycle, needs a per-cycle correction (a different arm) | one global offset is valid | **no** |
| 0e | STOP — `d_ber` measures the window edge | `d_ber` measures refinement | **no** |
| 0f | STOP — no treatment contrast exists | a contrast exists | **no** |
| 0g | STOP — structural (above) or leak (below); either is a finding about the POPULATION | `d_ber` is about refinement | **no** |

🔴 **Re-derive this independently and REFUSE under HK-025 if you disagree. My ROW 0 drafting is
what failed two rounds ago, and §1 and §2 of this very document are two more defects of mine found
by looking at code I had already specced against.** A refusal names the row and its evaluation and
stops; no partial run.

### 4.4 HK-021(n) — the two-sided check, applied to my own draft

The rule this programme produced yesterday: *a pre-gate check on a statistic with a known degenerate
limit must be two-sided, or state why the degenerate direction is unreachable.* Asked of each row:

- **0c** (`BER_V0`, degenerate limit 50%): a broken instrument pushes it **UP**. Bounded above at
  15%. It could also be implausibly **LOW** if the sweep found a spurious minimum or the control
  leaked its own answer. **Bounded below at 1.0%. Two-sided.** ✅
- **0g** (`ber_grid`, same limit): **bounded above at 40%** (chance) and **below at 8%** (a miss
  population reading below `B50` = 11.3% would mean these rows were correctable, contradicting the
  fact that we failed to decode them ⇒ membership leak). **Two-sided.** ✅
- **0e** (`frac_rail_t`, degenerate limit 1.0): the failure direction is **UP** only — a low rail
  fraction is unambiguously good and has no failure interpretation. **One-sided, and this is the
  written statement of why the other direction is unreachable.** ✅
- **0b, 0f** are count/motion floors with no upper failure mode. **0a** is an equality.

**Bars derived, not chosen:** matched-hit control median BER **2.9%** (W1, n = 171); `B50` =
**11.3%**; Stage 1R's own P-HIT reading at the corrected anchor **5.75%**; chance **50%**. 15% is
`B50` + margin. 40% sits above anything a correctly-pointed extraction produced in any run and below
chance. 0.0695 s is the 0.070 s hard ceiling less half a fine step (0.0005 s).

---

## 5. Part A as a finding in its own right — the anchor-offset arm

Per the Captain's ruling this is **one round serving two purposes.** Part A's output above is
Stage 2's ROW 0c/0d. Part A **also** reports, as its own deliverable:

1. **The full 49-point sweep on PRIMARY's `P-HIT`** — location, depth and width of the trough.
2. **The same sweep on ONE extension corpus's `P-HIT`** — QA's choice; `20260808_live_run_0016-8080`
   is the obvious pick (2,740 clusters, same instrument pair, different day).
3. **The per-quartile argmin table** from ROW 0d.

🛑 **Item 2 is DESCRIPTIVE and is NOT a gate row.** Stage 2 runs on PRIMARY regardless of what a
second corpus says, so a row turning on it would not change the verdict — **HK-021(k), and it would
be DIAGNOSTIC, and QA would be right to refuse it.** I am classifying my own row out of the gate
rather than making QA do it. It is reported because *does this offset generalise across corpora* is
the anchor-offset question's own content, and this round is the cheapest place it will ever be
answered.

🔴 **What Part A may and may not claim.** It may state the offset's value, its stability across
cycle strata, and its stability across two corpora. 🛑 **It may NOT claim the offset is a defect in
the production decode path.** Nothing in this arm touches `CycleFramer` or the live daemon; the
harness anchoring is not the production framer. **Whether the production buffer sits offset from the
UTC grid is a DIFFERENT question, it is Route A's territory, and it needs its own pre-registration
with its own instrument.** ⚠️ I flagged that link in the 19:02Z ledger §6.2 as a hypothesis; it is
still a hypothesis and this arm does not test it.

---

## 6. Order of work

1. **ROW 0a** — re-hash the DLL from disk, assert against the header pin. Stop on mismatch.
2. **Part A** — build `P-HIT` on PRIMARY, sweep, derive `OFFSET`. Evaluate **ROW 0c**, then **ROW 0d**.
3. **Dry-count `P-LIVE` on PRIMARY IN ADVANCE** and evaluate **ROW 0b** before measuring anything —
   dry-counted, not fitted after the fact.
4. **Stage 2** — measure both arms on `P-LIVE` at `anchor_dt + OFFSET`. Evaluate **0e → 0f → 0g**,
   then **ROW 1 → 3 → 2 → 4** in that order.
5. **Part A item 2** — the second-corpus sweep. Last, because nothing gates on it.
6. **Report and STOP.** 🛑 Do not proceed to Stages 3 or 4 on any outcome.

**Mandatory sign unit test before arming** (the discipline that has caught a real bug in every round
it was run): inject a known `dt` displacement, assert the sweep's minimum lands at its negation
within one grid step **with the correct sign**, and that at least two opposite-sign offsets are
present. Minutes; it catches exactly the class of bug that cost this thread two sessions.

**Estimated compute:** Part A ≈ 49 × n_control extractions (Stage 1R did 27,244 in 147 s). Stage 2 is
two extractions plus one refine per row over ~15,000 rows. **Well under an hour total.** Cap at 3 h;
if it binds, drop whole **CLUSTERS**, never grid points, and say so.

---

## 7. Standing constraints — unchanged

- 🛑 **No `src/`. No Developer session. No DLL rebuild. No capture run. HK-011 NOT engaged.**
- 🛑 **R2 STAYS EXCLUDED.** Stage 2 tests whether N1's harm replicates. **A ROW 1 firing would NOT
  rehabilitate R2** — it would be a new, differently-anchored population disagreeing with N1, which
  is an escalation to the Captain, not a licence. The R0/R1/R1b ~1.1 ms / 0.5 Hz prohibition is
  **unchanged**.
- 🛑 **N5 stays HELD** on its own 4.37% bound. Nothing in this arm touches it.
- 🛑 **Stage 1 stays WITHDRAWN.** This arm does not re-run it and must not be read as re-running it.
  Every number in the 15:50Z report remains uncitable.
- 🔴 **NFR-021, sharper here than usual:** `P-LIVE` and `P-HIT` are **built from message text** and
  `wsjt-x/ALL.TXT` carries real callsigns. Emit `{ts, freq, dt, ber_*, delta_*}` only. **Grep EVERY
  emitted file individually** — report, log, JSON, harness — not the run directory as a whole.
- 🔴 **Report SLOPE + CI + p on every gate statistic. Never a bare point estimate.** Cluster counts
  alongside row counts, everywhere.
- 🛑 **The per-row dump:** `.gitignore` already carries
  `qa/rr-study/p-live-population/results/*_rows.json`. If this round emits one, it is ignored by
  design — put a retained copy under `artefacts/` per HK-016 if it is worth keeping, and **note in
  the report that it exists and where**, so it is not a lost artefact.

---

## 8. Predictions — 🛑 nothing gates on these

- **P(ROW 2 — null replicates) ≈ 45%** (categorical).
- **P(ROW 3 — harm replicates) ≈ 35%** (categorical).
- **P(ROW 1 — benefit) ≈ 5%** (categorical).
- **P(ROW 4 / any ROW 0 fires) ≈ 15%** (categorical).
- **`frac_rail_t` on `P-LIVE` ∈ [0.10, 0.45]** (range).
- **Re-derived `OFFSET` ∈ [+0.60, +0.70] s**, i.e. within one grid step of Stage 1R (range).

⚠️ **Read the direction, not the number, and note the pattern in my misses.**

### 8.1 Calibration bookkeeping, owed from Stage 1R

The board recorded QA's scoring of ROW A and left the arithmetic to me. Discharging it:

| prediction (16:16Z §9) | outcome | class | result |
|---|---|---|---|
| P(ROW A fires) ≈ 80% | ROW A fired | categorical | **HIT** |
| swept optimum offset ∈ [+0.30, +0.60] s | **+0.65 s** | range | **MISS** |
| median `BER_V0` on `P-HIT` at raw DT ∈ [40%, 50%] | 49.43% | range | **HIT** |

🔴 **Running tally, superseding the board's line: categorical 7/12 · ranges 10/18 · directional
2.5/5.5 · mechanical 3/4.**

⚠️ **The range miss is instructive and I want it on the record: I anchored my interval on M3's
+0.45 s and allowed only +0.15 s of headroom above it, when M4 had already flagged M3's correction
as possibly SHORT.** I had the information that my own interval was skewed the wrong way and did not
use it. **Read my ranges as under-dispersed, and skewed toward whatever measurement I saw last.**

---

## 9. What this document does NOT do

- 🛑 **It does not change N1's status.** ROW 2 stands; limb 1 stays dead; the §1.1 railing
  measurement is recorded, not adjudicated, and earns its own pre-registration.
- 🛑 **It does not change N5's, N4's, N3's or N2's status.**
- 🛑 **It does not release Stages 3 or 4.**
- 🛑 **It does not claim the anchor offset is a production defect.** See §5.
- 🛑 **It does not change D-001's position.** Limb 1 dead, limb 2 held on a thin bound, Route A the
  best-motivated untested thing on the board — exactly as at 19:02Z.

---

## 10. Next

🔴 **QA: run §6 in order, report, and STOP.** HK-025 refusal available on every row, and given that
§1 and §2 are both defects of mine found in specs I had already shipped, **treat my ROW 0
classification in §4.3 as a claim to check, not a conclusion to adopt.**

A2/A3 from the 16:16Z ruling remain open and must not become a round; A1 is done.
