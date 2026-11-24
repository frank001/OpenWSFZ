# XC-BUILD (angle E, Stage 2): QA (k) review. ACCEPT WITH SIX AMENDMENTS; K1 is required (the TRAIN arm cannot produce T_E from the log line as written), K2 and K3 are required choices, the rest are stated.

**Written:** 2026-11-13, `date -u` read 13:02:12Z (the clock guard's last reading before this file). **To:** Architect. **Spec:** `arch/cross-cycle-prior` `14dc9bd3` (`2026-11-13-1258-architect-to-qa-spec-xc-template-build.md`). Nothing built; no arm run; no `src/` read for review yet (nothing to review). Counts below are from files on disk and from the harness source; WSJT-X text was read inside scripts only.

## 1. Your three HK-027 questions

**(a) Can Replay81 carry decoder state across cycles in one process? Yes.** One `Ft8Decoder` instance is built once and `DecodeStagedAsync(pcm, cycleStart, null, publishBatch)` is called per cycle (`Replay81/Program.cs:402, 795`) with `cycleStart` parsed from the stamp (`yyMMdd_HHmmss`, `:1233`), cycles in selection order. Per-instance state (the hash table, a prior store) persists across cycles; chronological selections give exact t − 30 / 60 / 90 s arithmetic. **Two things follow:** (i) the harness passes `currentBand = null` every cycle, so the store is never cleared by band in replay: R2's band-clear is a unit-test matter only, and the **gap** rule (exact `cycleStart` arithmetic) is what replay exercises; (ii) **the harness itself needs work (QA-owned, `qa/`)**: batch 6 does not exist in it (`run.csv` columns, `nc-dump` kinds, `matched-batch-out`, `ScoreTestB`'s kinds `1…5`, `Program.cs:666-717, 817, 839`), and it needs flags (`--xc-prior`, `--xc-shadow`, `--xc-te`, read back at start and end) and a consumer for the diagnostic sink of K1. About 2.5 h with its self-test.

**(b) TEST night, with its reference.** The REFERENCE-SET corpus names the runs whose OpenWSFZ recordings are correctly framed (0.014–0.017 s lag; the six early runs 0725 to 0731-8080 are framed 0.16–0.65 s late and are **unusable**). Of the well-framed, non-40 m runs on disk (contiguity counted from the owsfz stamps at 15 s steps; WSJT-X rows per cycle from its own `ALL.TXT`, dial 14.074 MHz for all three):

| run (band) | contiguous owsfz run | WSJT-X reference | rows per cycle (mean over the run; best 500-cycle window) |
|---|---|---|---|
| **`20260808_live_run_0016-8080` (20 m)** | **2,728 cycles from `260808_001600`** | `wsjt-x\ALL.TXT`, every cycle has rows | **27.8** (TRAIN night 28.0); first 500 cycles 33.2 |
| `20260921_1624_live_run-live-gap-map` (20 m) | 5,135 cycles | `wsjtx-1-ft991a\ALL.TXT` | 21.0; best window 34.7 (`19:15`–`21:20`) |
| `20260803_live_run_1713` (20 m) | 4,552 cycles | `wsjt-x\ALL.TXT` | 8.2 (a thin night); best window 15.0 |

**Recommended TEST night: `20260808_live_run_0016-8080`**, WSJT-X reference `artefacts\20260808_live_run_0016-8080\wsjt-x\ALL.TXT`, the first contiguous cycles from `260808_001615` (the first cycle as warm-up). It is 20 m (not 40 m: E165), as busy as the TRAIN night, long, and in the frozen corpus with its framing pin. The 17 m and 80 m runs are single runs and thinner; the 0803 run is too quiet to give NET power.

**(c) Does V-OFF need the full night? No new pre-change run is needed at all (K2).**

## 2. Amendments

**K1 (required): the TRAIN arm cannot make T_E from a counts-only log line.**
- §2 says TR "collects the shadow null's S_E\* and K". R10 says one counts-only line per cycle. T_E is "the smallest threshold with shadow exceedance per test ≤ FA\*", a quantile of the **per-test S_E\* values**; counts per cycle cannot give it.
- **Amendment:** add to R9/R10 an **internal diagnostic sink** (an `internal` interface or event on `Ft8Decoder`, visible to Replay81 through the existing `InternalsVisibleTo("Ft8.FitProbe")`), called once per tested template with **numbers only**: kind (live / shadow), S_E\*, the prior's age in cycles, argmax offsets. **No text, no callsign, no payload.** The shipped build has no subscriber and the log line stays counts-only.
- And **T_E must be settable for replay** (an internal setter, as `SetCoherentFallbackResidualUngated` etc. are): "T_E as a config constant" is the shipped value; TR runs with +∞ and ON with the frozen value, so one build must carry both.

**K2 (required choice): V-OFF design.** The decoder code of `bin_v2` (tree `59eb5a8f`, the build behind N24 and every arm so far) equals `origin/main` `ce5734b6` for Windows: `git diff 59eb5a8f origin/main -- src native` lists **only** the Linux `.so` and macOS `.dylib`. So the stored N24 outputs on the TRAIN night are exactly the pre-change reference.
- **V-OFF (proposed):** the new build with **both flags OFF** on the TRAIN night's 500 cycles, compared **per cycle** with N24's stored `matchedbatch.csv` and `run.csv` per-batch counts (b1–b5). Text-level equality is not recoverable from N24 (its `nc.tsv` was deleted at job close, HK-037); matched sets plus per-batch counts per cycle over 500 cycles is the strong form that survives, and a 100-cycle pre-change re-run with `nc.tsv` (≈ 9 min PC) gives the text-level form if you want it.
- **Cost:** 45 min of PC for the 500-cycle OFF run (or 9 min for the first 100). TEST's OFF arm is then a pure arm, not a pre-change check.
- **Also:** unit tests (R12) and my diff review of every changed line outside the new stage (HK-039) are the other two legs.

**K3 (required choice): the TEST night's length, and SHADOW's power.**
- SHADOW (CI_hi ≤ 0.042 per cycle) at the designed point 0.021 is a **counting problem**. With exact Poisson bounds: on **500 cycles** the row passes if ≤ 12 shadow events occur; P(pass) is **0.74** if the true rate is 0.021, **0.27** if it is 0.030 (within XC-TEMPLATE's factor 2–3). On **400 cycles** ≤ 8 events: 0.54 and 0.16. On **1,000 cycles** ≤ 29 events: **0.96** and **0.48**.
- **Recommendation: a 1,000-cycle TEST segment** (the run has 2,728 contiguous cycles), PC about 90 min each for OFF and ON, TR stays 500 cycles (the TRAIN night). Alternatively keep 500 and accept a coin flip on SHADOW at the designed rate. Your call; the cost is +90 min of PC.
- State the interval for SHADOW as the **exact Poisson** one (events over cycles), so the row is mechanical and not a bootstrap of ~10 events.

**K4 (stated): per-cycle cost and the budget.** Measured in Python: one template ≈ 0.09 s per worker over 13 × 25 positions; in managed C# I expect 30–50 ms. K ≈ 49 live templates (plus 49 shadow in arms) is 1.5–5 s of single-threaded work per cycle against about 8 s left after batch 5 (arm B's batch 5 publishes at 4.6–5.0 s; budget 13 s): feasible with the stage parallelised over `EffectiveSubtractionThreads` as the other stages are. **LATE** will show it; the Developer should parallelise, and R8's nearest-first order is what protects the budget.

**K5 (Developer notes to put in the dev task, from reading the tree):**
- Base: **`origin/main` `ce5734b6`**: it contains v2 (#282, `59eb5a8f`) and CQ-AP. `main` in this worktree does not, so the dev task names the base explicitly.
- No managed coherent extractor exists in `src/` (`Dsp\` holds `FftCompute` and `SpectrumAnalyser` only); R5 means a new managed implementation of `downconvert_decimate` (Hann-sinc, 61 taps, decimate 6) and `correlate_symbols` (79 × 8). The desk detector's **numerical equivalence is checkable**: I will supply fixtures (a buffer, a template, expected S_E\* from `xt_lib`) for the Developer's unit test and for my review.
- Batch 6 consumers: `DecodePump.PublishSecondAsync(..., batchNumber)` and the QSO services take a batch number generically (`LateBatch.Token`); the Developer confirms no `switch` or `== 5` assumes ≤ 5 (panel, ALL.TXT writer, reporting).
- R7's SNR: name the function; I will ask for the same estimator the fallback's rows use.

**K6 (stated): "corroborated" for NET** is the harness's Test B (text equal to a WSJT-X row within 10 Hz in that cycle), which batch 6 will go through once the harness carries kind 6. A template detection is by construction a WSJT-X-known text, so NET counts exactly the detections WSJT-X also decoded at that place.

## 3. Estimates (firmed)

| item | estimate |
|---|---|
| Developer | ≈ 1 day (R1–R12 incl. the managed detector, the probe sink, tests) |
| QA before the build: dev task (HK-015) ≈ 1.5 h; Replay81 harness (batch 6, flags, readbacks, sink consumer, self-test) ≈ 2.5 h | ≈ 4 h |
| QA review of the commit (HK-039, mutation checks of the new tests, diff outside the stage) | ≈ 3 h |
| Arms (PC windows, the Captain's): V-OFF on TRAIN 45 min; TR 45–50 min; OFF and ON on TEST 90 min each (1,000 cycles) or 45 min each (500) | 4.5 h or 3 h |
| QA analysis (T_E from TR, NET, SHADOW, LATE, V-STORE from the log, report) | ≈ 3–4 h |

## 4. Verdict

**ACCEPT WITH SIX AMENDMENTS** (K1 required; K2 and K3 your choice; K4 to K6 stated). **Order from here:** your Amendment 1; I write the dev task and the harness changes; the Developer builds; I review with a `Reviewed-commit` record **before any arm**; `pre_merge_check.py` before any push. I touch no PC time before the Captain's windows.
