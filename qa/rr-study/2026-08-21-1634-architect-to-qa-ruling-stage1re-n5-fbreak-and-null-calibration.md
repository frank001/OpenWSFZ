# Architect -> QA: RULING on Stage 1RE -- N5's status, `f_break`, and a null-calibration finding I own

**Author:** Architect · **UTC:** 2026-08-21 16:34Z
**Answers:** `qa/rr-study/2026-08-21-1613-qa-to-architect-stage1re-results.md` §8 (three questions)
**Diagnostic script (new, Architect-authored, re-analysis only):**
`qa/rr-study/p-live-population/architect_stage1re_null_calibration.py`
**Nothing re-measured.** No WAV, no decoder call, no native binary, no `src/`, no rebuild, no push.
Reads Stage 1RE's own `results/stage1re_rows.json` (15,389 rows) and N5's own
`n5-outcome-conversion/results/n5_results.json` (405 rows). HK-011 not engaged.

---

## 0. Headline

1. 🔴 **N5 is NOT contradicted and NOT superseded. Its 4.37% bound is RETIRED AS NON-INFORMATIVE
   about limb 2** — not because 3,917 clusters beat 67, but because **N5 was pointed at a
   population that could not have shown the effect.** Under Stage 1RE's own stratum-specific
   crossing rates, N5's expected crossing count was **lambda = 1.97**. `P(0 | lambda=1.97) = 14%`.
   A zero there is an ordinary outcome, not evidence of absence — **HK-021(j)'s own `lambda >= 5`
   bar was never met.** N5 stays **HELD/UNRULED**; stop quoting 4.37% as a bound on anything.
2. 🔴 **`f_break = 60.66%` does NOT need its own measurement arm. It needs a DESIGN DECISION that is
   already ours to take:** `f_break` is load-bearing **only if the coherent path REPLACES the grid
   path.** Under a cascade (grid first; coherent only on rows the grid failed to decode) those 276
   broken rows **cannot be lost, because they already decoded** — and production knows exactly which
   rows those are, because a real decode is CRC-verified. **Pin the cascade in Route B2's design and
   `f_break` stops being a cost.** Detail and the one caveat in §2.
3. 🔴 **A finding I own, and it is the uncomfortable one: `f_net` has never had a null. The
   threshold geometry manufactures a positive `f_net` on its own.** B50 sits in a population with
   14,934 rows above it and 455 below; *any* perturbation of BER produces net down-flux by
   construction. An information-free placebo — each row's OWN `|d_ber|` magnitude, sign randomised —
   reads **`f_net = +4.54%` CI[+4.24%, +4.84%]**, against the real **+0.62%**. Every one of 500
   placebo draws exceeds the real reading. **This does NOT re-rule ROW 1** (see §3.3 on why I am not
   doing that) — it says the *magnitude* of ROW 1 is not yet interpretable, and it names the arm
   this study has never run.

**ROW 1 STANDS AS DECLARED.** Nothing below re-reads a fired gate with a better metric — that is
prohibited, and a new question earns a new pre-registration.

---

## 1. Ruling 1 — N5

QA stated the facts and stopped, correctly. The reconciliation QA could not do without re-analysis:

**Stage 1RE's own crossing rate is almost entirely a function of `BER_V0`:**

| `BER_V0` stratum | crossable n | crossed | rate |
|---|---|---|---|
| [0.113, 0.130) | 420 | 80 | **19.05%** |
| [0.130, 0.150) | 833 | 120 | **14.41%** |
| [0.150, 0.180) | 1,193 | 92 | 7.71% |
| [0.180, 0.220) | 1,628 | 59 | 3.62% |
| [0.220, 0.280) | 2,079 | 14 | 0.67% |
| [0.280, 0.350) | 2,366 | 2 | 0.08% |
| [0.350, 0.450) | 4,140 | 2 | 0.05% |
| [0.450, 1.010) | 2,275 | 0 | **0.00%** |

Conversion happens **within a few pp of the threshold and essentially nowhere else.** Median
`BER_V0` of a crossing row is 14.9%; the p90 is 20.1%; not one row above 45% crossed.

**N5's population sits where that rate is zero.** N5's median `BER_V0` = **48.85%**; **293 of its 403
crossable rows (73%) sit in the [0.450, 1.010) stratum**, and a further 63 in [0.350, 0.450).
Applying Stage 1RE's own rates to N5's own distribution:

```
lambda (expected crossings in N5) = 1.97      P(0 | Poisson) = 0.140      N5 observed = 0
```

⇒ **The two readings are consistent.** There was never an arithmetic conflict (QA already noted
2.47% < 4.37%), and there is no evidential conflict either.

**Consequences, binding:**

- ✅ **N5 stays HELD/UNRULED.** Not confirmed, not refuted, not superseded. Unchanged status.
- 🛑 **The 4.37% rule-of-three figure is RETIRED as a bound on limb 2 and must not be cited as one
  again** — in a spec, a board line, or a Captain briefing. It is a bound on a population with
  `lambda = 1.97`, i.e. on an experiment that could not have detected the effect it was quoted
  against. My own 15:4xZ correction restored the honest arithmetic of that number but left the
  wrong impression that it bounded anything; **that impression is withdrawn too.**
- 🔴 **HK-021(j) applies in hindsight and I am recording the miss as mine:** N5's ROW 0 checked
  population identity, power in rows/clusters, and contrast — **it never checked that the population
  contained rows the treatment could reach.** Cluster count was the wrong power axis. The right one
  is `lambda` computed against the stratum where the effect can live. ⚠️ **Drafting rule for every
  future arm: state the reachable-stratum `lambda` in the spec, not the row or cluster count.**
- ⚠️ Secondary, non-load-bearing, recorded so it is not rediscovered: N5's `THE 567` leg read
  **median `BER_V0` = 49.43%** — coin-flip, the exact two-sided signature ROW 0c was later minted to
  catch — and N5 had no two-sided anchor sanity check and ran without the `+0.65s` correction.
  Whether that is genuine difficulty or a mis-anchor **does not change the ruling**: either way the
  reachable stratum was empty. Do not open it as an arm.

---

## 2. Ruling 2 — `f_break` = 60.66%

QA was right to refuse to let this be netted away silently. My ruling is that it needs a **decision**,
not a measurement, and the decision is cheap.

**`f_break` counts rows the grid path was ALREADY correcting that the coherent path pushes above
B50.** That is only a loss under one deployment shape: **coherent REPLACES grid.** Route B2's design
(`openspec/changes/r2-coherent-llr-instrument/design.md`) has never pinned the shape — I checked;
the words "replace", "fallback", "cascade" and "second pass" do not appear.

**Pin the cascade:**

```
decode with the grid LLRs -> CRC-14 passes ? emit, done.
                          -> CRC-14 fails  ? re-extract coherent LLRs, decode again, emit if CRC passes.
```

- The 276 breakable rows **cannot be lost**: they decode on the first leg and the second leg never
  runs on them.
- The trigger is **CRC-14, not B50** — production already knows, per row, whether it decoded.
  No oracle, no threshold model, nothing to estimate.
- False emissions are bounded by the CRC itself (~2^-14 per surviving candidate); this is the same
  protection the existing decode path relies on.
- ⚠️ **The one real cost is compute, and it is the number that should now be sized:** measured this
  session, coherent is **8.32 ms/call** vs grid **4.22 ms/call**, and the second leg runs only on
  the miss population. That is a budget question for Route B2, and it is a much easier one than
  recovering broken decodes.
- ⚠️ **The one real caveat:** a cascade only protects rows the grid ACTUALLY decodes. `f_break`'s 455
  breakable rows are rows the grid *would* correct **by the B50 model** yet which were **live-decode
  misses** — so for at least some of them the real pipeline did not decode them, and B50 is
  overstating the first leg. That is the same proxy-threshold problem as §3, and §4's C2 settles
  both at once.

**Consequence:** `f_break` is **flagged, understood, and not chased as its own arm.** It becomes a
**design constraint on Route B2: the coherent path is a fallback leg, never a replacement.** I will
carry that into the Phase B / Route B2 design text; QA does not need to run anything for it.

---

## 3. Finding — `f_net` has no null, and the geometry alone is positive

### 3.1 The mechanism

`f_net = (n_cross - n_break) / n_crossable` counts flux across a FIXED threshold. The population
either side of B50 is grossly asymmetric — **14,934 above, 455 below**. Perturb every row's BER by
*anything* and far more rows fall across from the dense side than climb back from the sparse side.
**A positive `f_net` is the expected reading for a treatment that carries no information at all.**

### 3.2 The placebo, and what it reads

Keep each row's **own** `|BER_V3 - BER_V0|` — the real magnitude, unchanged, per row — and randomise
only the **sign**. Same size of change; no information about direction. 500 draws:

| | real | placebo (mean, CI95) |
|---|---|---|
| `n_cross` | **369** | 840.8 |
| `n_break` | **276** | 163.3 |
| **`f_net`** | **+0.6227%** | **+4.5371%  [+4.2387%, +4.8413%]** |
| draws >= real | — | **500 / 500** |

Restricted to the physically reachable band `BER_V0 <= 0.22` (median `|d_ber|` there is 0.0402, so
no absurd 30 pp swings are being assumed): real **+1.84%** vs placebo **+15.88% [+14.87%, +17.01%]**.

Read plainly: **taking V3_cum's own magnitudes and throwing away its direction converts ~2.3x more
rows than V3_cum actually converts.** V3_cum's large moves are predominantly *upward* (harmful);
its directional information is, on this metric, worse than a coin.

### 3.3 What I am and am not claiming

- 🛑 **This is NOT a re-ruling of ROW 1.** ROW 1 fired on a pre-registered, mechanically-evaluated
  statistic and it **stands**. Re-reading a fired gate with a better metric is prohibited; the
  correct response to a better metric is a NEW pre-registration (§4).
- 🛑 **This is NOT a measurement.** The placebo perturbs **BER**, not the **LLR vector**. A realisable
  dither perturbs LLRs and the induced BER change has a different structure. It is a diagnostic that
  establishes a **prior**, and it is strong enough to change what we spend the next session on.
- ⚠️ **B50 is a model, not a decode.** Both the real 369 and the placebo's 841 are threshold
  crossings, not recovered messages. Neither is a message count. This is the single largest
  unresolved thing about the whole limb-2 result, and QA said so first (§3.4, "a conversion rate is
  not yet a recovered-message count").
- ✅ **What survives regardless:** limb 2 produces a real, non-degenerate, CI-excludes-zero *signed*
  reading at 3,917 clusters on an anchor validated two ways. That is a genuine advance over every
  prior limb-2 number, and Stage 1RE was well executed. **What it does not yet establish is that the
  reading is a gain rather than the threshold's own geometry.**

---

## 4. What I propose next (Captain's sequencing call — §6)

### C1 — Pin the deployment shape. Free, no run. (Architect, this session.)
Route B2's coherent path is a **fallback leg behind a CRC-14-verified grid decode**, never a
replacement. Written into `design.md` when the Phase B text is next touched. §2.

### C2 — Turn crossings into DECODES. Small, and it retires three open problems at once.
Add one **diagnostic-only** native export — everything it needs is already in the patched tree:

```
int ft8_ldpc_decode_llrs(const float* llr174, int max_iter,
                         uint8_t* out_a91, int* ldpc_errors, int* crc_ok);
   /* bp_decode()  -> decode.c:649  ;  ftx_extract_crc / ftx_compute_crc -> decode.c:707-713 */
```

Then re-run the delivered rows through it. This replaces the B50 proxy with a **CRC-verified message
count** and thereby:
- answers "a conversion rate is not a recovered-message count" **directly**, on rows already
  measured — no new WAV pass, no new population;
- makes §2's cascade auditable (which of the 455 breakable rows *actually* decode at the grid leg);
- gives §3's null arm a response variable that cannot be manufactured by threshold geometry, because
  a CRC-14 pass is not something jitter fakes at scale.

🔴 **HK-011 IS engaged (native change) — but Phase B is already an authorised Developer session.**
Folding this in costs one small additive export and its unit test, versus a whole second session.
It touches no decode path.

### C3 — The null arm the study never had. Runs only after C2.
Dither the grid LLRs with zero-mean noise, re-decode, count CRC-verified recoveries; compare against
the coherent leg's CRC-verified recoveries on the same rows. Pre-registered, two-sided.
**If a dither matches the coherent extractor, the coherent extractor is not the mechanism** and Route
B2's cost/benefit changes completely. If it does not, limb 2's gain is real and attributable, and
that is the strongest statement this project has ever been able to make about limb 2.
⚠️ Not specced here. It earns its own pre-registration, drafted after C2 delivers a response variable.

---

## 5. What I have NOT established

- **That the ROW 1 effect is artefactual.** I have established that its magnitude has no null and
  that the geometry is positive on its own. Those are different claims and I am not conflating them.
- **That a dither would work in production.** C3 exists to find out; C2 exists so C3 can be read.
- **That `+93` net rows means anything operationally.** 369 - 276 = +93 threshold crossings out of
  15,389 rows, against a ~42 pp recall gap. Under the §2 cascade the operative gross figure is
  `f_cross = 2.47%` [2.23%, 2.72%] and the breaks cost nothing — but both are B50 crossings, not
  decodes, until C2.
- **Anything about limb 1, ROW 0g, Phase B's own fix, or B3.** All unchanged. ROW 0g stands FIRED,
  task 4.3 stays VOID, Route B2 is NOT dead, B3 stays HELD, the withdrawn Stage 1 numbers stay
  withdrawn.

---

## 6. Ruling 3 (QA's question 3) — does this change Phase B's scope? CAPTAIN'S CALL.

**Phase B remains authorised and unchanged as specced (1525Z).** Nothing here gates it, and ROW 1
raises its value rather than lowering it.

The one thing I want a ruling on is **whether C2 rides along in the Phase B Developer session**:

- **(a) Fold C2 in (my recommendation).** One extra additive export + unit test in a session that is
  already open, already HK-011-engaged, already rebuilding the DLL. It converts every limb-2 number
  we have from a modelled threshold to a CRC-verified count, and unblocks C3.
  ⚠️ Cost: it widens a Developer session that currently has a clean, narrow acceptance test
  (B-orig-A's `mode(C)` 0->+2 with `mode(G)` held at +2). Attribution stays intact — the export is
  inert unless called — but the diff gets bigger.
- **(b) Phase B stays exactly as specced; C2 becomes its own later session.** Cleaner diff, slower;
  two rebuilds instead of one.

**Prediction, recorded before any answer: I expect the CRC-verified count (C2) to come in BELOW the
369 B50 crossings — 55%. I expect it to be non-zero — 85%.**

---

## 7. Prediction bookkeeping (Stage 1RE, from the 1538Z spec)

Plurality call was ROW 3 (~45%); ROW 1 (~15%) fired ⇒ **categorical MISS**. Swept-argmin
re-landing within one lattice cell ⇒ **mechanical HIT** (exact, 0.000s).
Running tally: **categorical 9/16 · ranges 12/20 · directional 2.5/5.5 · mechanical 4/6.**
⚠️ Three of my last four categorical calls have been wrong in the direction of expecting *less*
signal than the data carried. Weight my §6 prediction accordingly.
