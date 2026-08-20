# ARCHITECT RETRACTION — the N4 infeasibility ruling is WITHDRAWN. The corpus was never 68 clusters.

**Author:** Architect
**UTC:** 2026-08-17 17:44Z (`date -u`, HK-017)
**Branch:** `qa/n1-ber-results` @ `a896968`
**Supersedes:** `2026-08-17-1648-architect-to-qa-n4-ruling-and-n5-spec.md` §2 (the infeasibility pricing) — and ONLY that. The rest of the N4 ruling stands; §7 below states exactly what survives.
**Prompted by:** the Captain, who challenged the 68-cluster figure directly and was right twice in a row while I defended it.

---

## 1. The retraction, stated plainly

My N4 ruling closed the narrowing route with this chain:

> required SE 0.003295 ⇒ 371× variance reduction ⇒ **14,838 clusters** vs **the 68 the corpus yields** ⇒ **218× the ENTIRE decisive corpus** ⇒ **~172 days of equivalent capture**. And the population is **SPENT** — the never-read remainder is 283 rows / 16 clusters.

**Every clause after "14,838 clusters" is withdrawn.** The 68 is not what the corpus yields. It is what one hardcoded path yields.

`qa/cycleframer-alignment-replay/c2_phase2c_ber_measurement.py:56`:

```python
BASE = os.path.join(REPO_ROOT, "artefacts", "20260725_live_run_1806")
```

Every N-series round — N1, N2, N3, N4, N5 — has run on the cycles that path exposes. Measured from N5's own committed results (`n5_results.json`, 405 rows):

| | |
|---|---|
| Cluster span | `260725_180615` → `260725_182645` |
| Elapsed | **20 minutes 30 seconds** |
| Distinct `ts` clusters | **67** |
| Distinct days | **1** |

Five rounds of D-001's decisive programme have been standing on twenty and a half minutes of one afternoon, and I priced a closure decision as if that were the whole corpus.

## 2. What is actually on disk

Verified directly on disk this session (not read from the inventory's prose — that distinction is the whole point of this document):

| Run | owsfz WAVs | Band | Note |
|---|---|---|---|
| `20260725_live_run_1806` | **85** | — | ← what the entire N-series uses |
| `20260731_live_run_2004-8080` | **10,489** | — | ~43 h |
| `20260803_live_run_1713` | **4,971** | 20m (14.074) | 18.96 h contiguous; both decoders on ONE verified audio path (median \|r\|=0.987, lags ≤34 ms) |
| `20260808_live_run_0016-8080` | **2,747** | 20m (14.074) | clean two-instance pair |
| `20260808_live_run_1154-*-17m` | **1,856** ×2 | 17m | clean two-instance pair |
| `20260809_live_run_0155-*-80m` | **1,988** ×2 | 80m | clean two-instance pair |

Inventory total: **132,296 WAVs across 35 runs.**

**14,838 clusters was never 218× the corpus. It is a fraction of what already sits on the disk**, and the work to reach it is an offline replay over existing WAVs — not a capture run, and not 172 days of anything.

`20260803_live_run_1713` is annotated in the inventory, in the notes column, with: *"D-001 replication corpus — DO NOT PROPOSE A CAPTURE RUN FOR D-001."*

## 3. The hardlink caveat: I generalised from one flagged case

I dismissed the second WSJT-X instance partly on hardlinking. Mechanically checked, by inode:

| Pair | `wsjt-x/ALL.TXT` inodes | Sizes | Verdict |
|---|---|---|---|
| `20260731_..._2004-8080/8081` | `281474977010995` = `281474977010995` | identical | **HARDLINKED** |
| `20260808_..._0016-8080/8081` | `…062097` ≠ `…067511` | 4,975,757 vs 4,726,917 | distinct captures |
| `20260808_..._1154-*-17m` | `…075762` ≠ `…079488` | 2,564,910 vs 2,567,869 | distinct captures |
| `20260809_..._0155-*-80m` | `…087507` ≠ `3096224744198121` | 706,943 vs 706,320 | distinct captures |

**One pair of four is hardlinked.** Three are genuinely two instruments, with different inodes, different sizes and different decode counts — exactly as the Captain said. Leading with the flagged case was wrong.

## 4. What the second instance does and does not buy — measured, not argued

Per-cycle decode-set agreement between the two independent instances:

| Run | Cycles | Shared decodes | Unique A | Unique B | Median per-cycle Jaccard |
|---|---|---|---|---|---|
| 20m `0016` | 2,648 | 72,582 | 571 | 553 | **1.000** |
| 17m `1154` | 1,856 | 37,505 | 2,208 | 2,236 | 0.909 |
| 80m `0155` | 1,196 | 10,763 | 188 | 179 | **1.000** |

**As a cluster multiplier the second instance is worth ~2–10%, not 2×.** Both radios decode essentially the same signal set from the same 15 seconds; the cluster unit is the cycle, and counting each leg as a fresh cluster would repeat the HK-021(i) error that already cost N1/N2/N3 a ≈3.8× CI understatement.

**But there is a version of the Captain's argument I dismissed too fast, and it is not answered by the table above.** The two legs run different capture-clock drift — **48.0 ppm (USB CODEC) vs 4.7 ppm (Voicemeeter)**. `H_3^cum` is a *frequency-offset* statistic. The same signal therefore presents at a **different frequency offset in each leg**. That is a second independent draw of precisely the nuisance variable the statistic measures, and decode-set agreement says nothing about it. **Unmeasured, genuinely open, and mine to have checked before waving it away.**

**The dominant lever remains time** — ~7,600 usable 20m cycles against 67 — but "the second receiver adds nothing" was too strong.

## 5. The defect, named

This is the **eighth Architect-authored defect in the N-series**, and the most consequential, because unlike the other seven it did not cost a round — **it closed a route.**

`qa/ARTEFACT_INVENTORY.md` opens with:

> Read this **before** concluding that data for a question does not exist, and before proposing any capture run (HK-018, HK-004).

That is a standing rule I put into MEMORY myself. I priced a closure at "172 days of capture" without opening the file that lists 132,296 WAVs already captured. HK-018's own trigger — *"treat the feeling of already knowing as the trigger to go and look"* — fired and I did not act on it.

**New standing item, HK-018 addendum:** *a feasibility or infeasibility claim that turns on corpus size MUST cite `ARTEFACT_INVENTORY.md` and a disk-verified count, in the ruling, at the point the number is used. A cost denominated in days-of-capture is a claim about the inventory and may not be written without reading it.*

## 6. Consequences for N5, which I have NOT yet ruled on

N5's ROW 2 bound rests on these same 67 clusters, and there is a second issue with it independent of corpus size:

**The bootstrap CI of [0.00%, 0.00%] is degenerate.** With `n_cross = 0` in every cluster, every resample returns exactly zero — `n5_stats.py:102-113` cannot produce otherwise. The pre-registered ROW 2 test `CI_hi(f_cross) < 0.05` was therefore satisfied the instant the count hit zero, **at any sample size whatsoever**. That is an HK-021 family fault in my own gate: the test's verdict does not depend on the strength of the evidence.

The honest upper bound is rule-of-three:

| Basis | 0 events in n | One-sided 95% upper bound |
|---|---|---|
| Clusters (conservative, correct) | 67 | **4.37%** |
| Rows (only if crossing were unclustered) | 403 | 0.74% |

**4.37% clears the pre-registered 5% by 0.6pp.** ROW 2 does still fire — but marginally, on an instrument that could be made decisive.

✅ **The falsifiability check passes and this is worth recording**: min `BER_V3` on crossable rows = **13.79% = 24 bits/174**, against `B50` = 11.3% = 19.66 bits ⇒ the nearest row missed crossing **by 5 bits**. And `hd_disagree_v0_v3` is **never zero** (min 6, median 21 bits). Both HK-022 closed-loop failure modes are ruled out: the zero is a physical result, not a wiring artefact.

⚠️ **Noted, not yet ruled on:** on the reachable stratum (`BER_V0 < 20%`, n=20) V3 is worse than V0 on **18 of 20 rows**, median +6.3pp. This is **NOT citable as evidence of harm** — it is exactly the regression-to-the-mean artefact my own N5 spec pre-registered as "stated not discovered". Selecting on a noisy baseline realisation of the outcome biases the contrast against V3. It goes in the ruling as confounded-by-design.

**N5 remains unruled.** It should be ruled after §7's measurement, not before, because the measurement determines whether its central bound is 4.37% or something decisive.

## 7. What SURVIVES from the N4 ruling — do not over-read this retraction

Withdrawn: **only** the infeasibility pricing and its conclusion.

Still standing, unaffected:

1. **The 19.3× ratio.** `|H − cut|` = 0.006458 Hz = 0.413% of the cut, CI half-width 0.124386 Hz. A measurement on the data we have.
2. **`H_3^cum` = 1.5689583 Hz**, and all five variants' `H`, `D` = 0.347 CI[0.281, 0.462] p<0.0001, pure-vs-cumulative — citable as measured on Slice B with CIs.
3. **ROW 4 fired correctly.** QA's execution accepted in full.
4. **HK-021(m)** — a gate must state the minimum distance from its threshold it can resolve. Unaffected and reinforced; §6 above is a fresh instance.
5. **The `q`-statistic finding** — a finer-quantised equivalent statistic buys only 6–15%, because SE is genuine between-cluster variance, not discreteness. **This survives and it matters MORE now**, not less: it says the way to narrow is *more clusters*, which is exactly what the corpus turns out to have.
6. 🛑 **R2 STAYS EXCLUDED.** Nothing here rehabilitates limb 1. N1 killed it on outcome evidence and refinement measurably harmed the strong-candidate stratum. The R0/R1/R1b ~1.1 ms / 0.5 Hz prohibition is UNCHANGED.
7. 🛑 The §3 margin/OSR table remains **post-hoc, no CI, not authorisation** for an OSR change.

**Lifted:** the prohibition *"do NOT re-propose narrowing under any statistic, grid or population"* — struck from MEMORY and BOARD. It was founded on the retracted pricing. Narrowing is **open on corpus grounds**, and unpriced on every other ground.

🛑 **"Open" is not "authorised."** Nothing in §8 gates anything, and §8 is a measurement, not a round.

---

## 8. SPEC — the 20m re-point yield measurement (Captain-approved: 20m-only)

**Purpose: price the route. This measurement gates nothing and rules nothing.** It answers one question — *how many usable rows and clusters does the 20m corpus actually yield?* — so that narrowing, and N5's bound, can be argued on measured numbers instead of my estimates.

### 8.1 Population

20m only, per the Captain's ruling. Heterogeneity across bands is thereby avoided by construction, not by argument.

| Corpus | Cycles (WAVs) | Note |
|---|---|---|
| `20260803_live_run_1713` | 4,971 | 18.96 h contiguous, 14.074, drift screen PASS (+0.0 ppm) |
| `20260808_live_run_0016-8080` | 2,747 | 14.074, clean pair — leg **8080 only** for the primary count |
| **Total** | **~7,700** | vs 67 today |

🔴 **Count the `-8081` leg SEPARATELY and report it as its own line.** Do NOT pool it into the primary cluster count. Per §4 it is worth ~2–10% as a cluster multiplier and pooling would be the HK-021(i) error. Its value is the §4 frequency-drift question, which is **out of scope here**.

### 8.2 What to report — counts only, no verdict

1. **Cycles with a usable WAV**, per corpus.
2. **Matched-hit rows** (WSJT-X reference decode present, our candidate present) — rows AND distinct `ts` clusters.
3. **THE 135 / THE 567 equivalents** — the candidate-present-and-failed population — rows AND clusters.
4. **Rows per cluster** distribution (median, IQR). The 07-25 run gave ~18 rows/cycle in the full pool and may have been unusually dense; this is the number that decides whether ~7,700 cycles reaches 14,838 clusters' worth of information.
5. **`no_true_codeword` drop rate**, for comparison against N5's 36/441.

### 8.3 The blocker I could not resolve, and will not guess at

🔴 **The 20m corpora have NO replay products.** They contain `owsfz/` and `wsjt-x/` only. `d001_c2_phase2c` has `ALL.TXT` + `candidate_diag.csv` + `hash_reject_count.txt`; the 20m runs have none of that.

What the population builder actually needs is narrower than it first appears — `load_candidate_diag_simple` (`c2_phase2c_ber_measurement.py:226-233`) reads **only** `cycle_ts`, `freq_hz`, `dt`, `decoded`. It does **not** read `llr174`. So the raw-LLR diagnostic build (`FT8_ENABLE_RAW_LLR_CAPTURE`, which the board records as existing **only on the unmerged `d001-c4-min-score-sweep`**) may well not be required for this measurement.

🔴 **QA: establish this FIRST and report it before doing anything else.** Three outcomes, and the third stops the round:

- **(a)** A candidate-diagnostics export sufficient for those four columns exists on a merged build ⇒ proceed, name the build and pin its SHA256.
- **(b)** It needs the diagnostic build ⇒ **STOP.** That engages HK-011 (`src/` work, separate Developer session, Captain's sign-off). Report and stop; do not build anything.
- **(c)** The only available replay path is the real-time audio harness (`run_cross_decode_replay.py` replays through VB-CABLE at wall-clock speed — ~7,700 cycles × 15 s ≈ **32 hours of playback**) ⇒ **STOP and report the cost.** Do not start a 32-hour run without the Captain's explicit authorisation.

🛑 **Do not modify `c2_phase2c_ber_measurement.py:56` in place.** N1–N5's committed results all read that path and their reproducibility depends on it. Parameterise `BASE`, defaulting to the current value, or drive it from a new module. Whichever you choose, **assert that the 07-25 default still reproduces N5's 67 clusters / 405 rows before trusting any new number.**

### 8.4 Standing obligations

- **HK-025 refusal is available**, as always, on any row here — though note this is a measurement with no gate, so the classify-both-branches test will mostly come back "not a gate."
- **NFR-021**: `wsjt-x/ALL.TXT` on these corpora carries **real callsigns** — 4.9 MB and 2.5 MB of them. Grep every emitted file individually (the standing rule: a report's own cleanliness does not extend to its CSVs). Counts only; no `message_text` in any committed artefact.
- **HK-009**: ASCII console output.
- **HK-016**: gather artefacts properly if any run is made.
- 🛑 No `src/`. No Developer session. No DLL rebuild. No capture run. **HK-011 not engaged** — and if §8.3 says it would be, that is outcome **(b)**: stop.

### 8.5 Architect's predictions — 🛑 nothing gates on these

- P(outcome **a**) ≈ 45% · P(**b**) ≈ 35% · P(**c**) ≈ 20%.
- Matched-hit rows per cluster on 20m: **8–18** (the 07-25 run's ~18 was a dense window; 20m over 19 h will average lower).
- Usable clusters from ~7,700 cycles: **>3,000** (DIRECTIONAL — my weakest class, 2.5/5.5, do not lean on it).

Calibration, quoted per standing rule: **categorical 6/11 · ranges 9/16 · DIRECTIONAL 2.5/5.5 · mechanical 3/4.** Categorical is below 55% and the failure mode is consistent — my intervals land, my row calls miss. This document exists because a categorical judgement of mine was wrong.

---

## 9. NEXT

🔴 **QA runs §8, starting with §8.3.** If §8.3 returns **(b)** or **(c)**, that is the whole deliverable — report and stop.

🔴 **N5 stays UNRULED** until §8 reports. Its ROW 2 bound is 4.37%, not 0.00%, and whether that becomes decisive is what §8 measures.

A2/A3 still open, must not become a round; A1 done.
