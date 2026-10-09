# LATENESS / EDGE test: RESULTS report (Engineer, owner of the edge test)

- **To:** Architect (cc Captain, QA)  **From:** Engineer  **Date:** 2026-10-02 22:20Z (HK-017, `date -u`)
- **Spec:** `qa/rr-study/2026-10-02-0720-architect-to-qa-spec-lateness-tolerance.md` with Amendments 1 to 3. **Freeze:** `46994f57`, on `main` since `286ca16b`; manifest SHA-256 `49db08690850c92cf3e7383ba7ab3dc2252cfac39f7573717b7ec07dd1df75e2`. Played after the freeze; nothing in the frozen artefacts changed since (LF-normalised SHA-256 of `analysis.py` `72e2b3ee…6a63`, `design.py` `efeacdfc…1b62`, `manifest.json` `49db0869…75e2`, `renders_index.json` `061cfa9f…89ec9`, all equal to the freeze report).
- **Run record (QA, with every SHA-256):** `artefacts/20261002_2115_lateness_edge_run/RUN-REPORT.md`. Playback 2026-10-02 21:18:49Z to 22:13:00Z, 204 cycles, no restart, no supervisor trigger, no drift row. Build under test `main` `b87529a3` (v0.54, shim 20260056, `libft8.dll` SHA-256 `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c`, pinned = actual), flag **OFF** read back (with `subtractionOnMigrationApplied` true). WSJT-X live install, version not re-read (2.7.0 per the 2026-09-23 report).
- `git diff --stat -- src/ native/` empty. Aggregates only (HK-037): no message text, callsign or text-derived value is in this report or its data files.
- **This report is the Engineer's. The rulings, the prediction scoring and the ledger are the Architect's.**

## 1. Independent verification (what QA asked: confirm cell by cell)

| Step | Result |
|---|---|
| Frozen files extracted from `origin/main` (`git archive`; the checkout is CRLF, so hashes were compared LF-normalised) | all equal to the freeze report |
| Inputs hashed: `playback_log.csv`, `ALL.TXT`, `ALL.wsjtx.TXT` | equal to RUN-REPORT §2 (`094b0d86…`, `0babb692…`, `b6c20fd6…`) |
| **`analysis.py` re-run** (frozen, from the clean extraction, no flag) | `ALL_VALIDITY_PASS: true`. Output **byte-identical** to QA's `analysis_result.json` (SHA-256 `f248b7ffbc6a9141d0b0c6e5f33583d7c4919535135069f7876ed8292aa9c3fc`, `cmp` equal) |
| **Independent recount** (`results/recount_independent.py`: does not import `analysis.py` or `design.py`; own parser, own matching: planted text exact, own cycle stamp from the playback log, \|Δf\| ≤ 10 Hz) | **152 of 152 cells equal** (2 decoders × 76 cells), 0 mismatches. Σ matched = 1 295 (OpenWSFZ) and 1 403 (WSJT-X) = the planted-text line counts of the two `ALL.TXT`, so every planted-text line landed in its own cell and none was left over |
| `--filter` | none (no test suite was run for this report; no decoder was run) |

## 2. Validity rows (frozen `analysis.py`, no filter)

| Row | WSJT-X | OpenWSFZ | |
|---|---|---|---|
| P1, P2 (pre-playback, freeze report) | PASS | PASS | placement and truncation; P1 caveat as stated in the freeze report (same `modulate`, catches arithmetic only) |
| P3 late L = 0, −8 dB (≥ 0.90) | 32/32 | 32/32 | PASS |
| P3b early L = 0, −8 dB (≥ 0.90 and within 3 of P3) | 32/32 (P3 32) | 32/32 (P3 32) | PASS |
| P4 a decode pass in every planted cycle | 152/152 | 152/152 | PASS |
| P5 median reported SNR, L = 0, −8 dB (−8 ± 3) | −7.0 dB (n 32) | −7.0 dB (n 32) | PASS |
| P6 planted texts decoded in another cycle | 0 planted, 0 idle | 0 planted, 0 idle | PASS |

**All validity rows PASS first time, so the edges are reported.**

**P7 (descriptive, no bar).** Median reported DT at L = 0.00, −8 dB (n 32 each; IQR 0, ALL.TXT resolution 0.1 s): WSJT-X **−0.3** s in both the LATE and the EARLY block, OpenWSFZ **+0.3** s in both. **Δ_chain = −0.3 s** (WSJT-X is the reference); ours reads 0.6 s above WSJT-X. Both arming paths show the same offset.

## 3. The edges (frozen definitions; L is the primary grid, grid step 0.25 s)

DT form: `DT_edge = L_edge + Δ_chain`, labelled **"WSJT-X DT convention, via this chain's offset (Δ_chain, P7)"**. E50 = E90 in every row, at both SNRs; no non-monotone cell after any edge (the frozen list is empty in all 16 rows).

| Edge | WSJT-X | OpenWSFZ |
|---|---|---|
| Late E50 = E90, −8 dB **and** −16 dB | **L +2.75** (DT_edge **+2.45**) | **L +2.75** (DT_edge **+2.45**) |
| Early E50e = E90e, −8 dB **and** −16 dB | **L −2.25** (DT_edge **−2.55**) | **L −1.75** (DT_edge **−2.05**) |

Matched signals out of 32 (full grids are in `results/recount_output.txt`; the DT_edge of OpenWSFZ is, as the spec says, stated through WSJT-X's offset, for comparison on one axis).

| LATE, L | 2.00 | 2.25 | 2.50 | 2.75 | **3.00** | 3.25 to 6.00 |
|---|---|---|---|---|---|---|
| WSJT-X −8 dB | 32 | 32 | 31 | 32 | **0** | 0 |
| WSJT-X −16 dB | 32 | 32 | 32 | 32 | **0** | 0 |
| OpenWSFZ −8 dB | 32 | 32 | 32 | 32 | **0** | 0 |
| OpenWSFZ −16 dB | 32 | 32 | 32 | 32 | **0** | 0 |

| EARLY, L | −2.75 and −3.00 | −2.50 | −2.25 | −2.00 | −1.75 | −1.50 to 0 |
|---|---|---|---|---|---|---|
| WSJT-X −8 dB | 0 | 0 | 32 | 31 | 32 | 32 |
| WSJT-X −16 dB | 0 | 0 | 32 | 31 | 32 | 32 |
| OpenWSFZ −8 dB | 0 | 0 | 0 | **14** | 32 | 32 |
| OpenWSFZ −16 dB | 0 | 0 | 0 | **1** | 32 | 32 |

(All 0 to 31 dips on the otherwise full rows are single signals: WSJT-X −8 dB L 2.50, −16 dB L 0.75 and EARLY L −0.50, both SNRs at L −2.00. None sits at an edge.)

Median reported DT of the matched signals in the last passing cell, as the decoders printed it (descriptive; ALL.TXT resolution 0.1 s): LATE L 2.75: WSJT-X **+2.4**, OpenWSFZ **+3.1**. EARLY: WSJT-X L −2.25 **−2.6**; OpenWSFZ L −1.75 **−1.4**.

## 4. Reading, stated with its limits

1. **The late edge is a cliff, identical for both decoders and both SNRs:** 32/32 at L 2.75, 0/32 at L 3.00. At L the signal is cut by `L − 1.86` s, so the cut is 0.89 s at 2.75 (0.23 s of the last Costas array, about 1.4 of its 7 symbols, still present) and 1.14 s at 3.00 (the whole last Costas array gone, and the first data symbols). *Inference, not tested:* the edge follows the content that is left, not a decoder's DT search window. What supports it: the two decoders stop at the same L although they print DTs 0.7 s apart at that point (+2.4 and +3.1), and the edge does not move between −8 and −16 dB.
2. **The early edge differs:** WSJT-X still decodes in full at L −2.25 and not at −2.50 (a cliff); OpenWSFZ is complete from −1.75, partial at −2.00 (14/32 at −8 dB, 1/32 at −16 dB, so the transition is SNR-dependent) and 0 at −2.25. **WSJT-X is 0.5 s (two grid steps) more forgiving on the early side.** The spec warns against drawing a conclusion from a one-step difference; this is two steps, a 32/32 against 0/32 contrast at L −2.25, and it holds at both SNRs, but it is one build of each decoder on one night.
3. **Δ_chain belongs to this playback chain** (the playback device and Voicemeeter path; the freeze report's inference is that most of it is the harness's 0.5 s prewarm less the device latency). It is not a property of a real partner. `DT_edge` is the form the spec asks for; for Q2 the L form is given beside it.
4. **Nothing here says how often a real reply lands inside the late edge:** that is Q2 (§6).
5. **Limits (spec §6):** synthetic AWGN signals through the playback chain, no fading, no drift; 16 signals per cycle 150 Hz apart (a moderate, controlled crowd; OpenWSFZ loses more than WSJT-X as a scene gets denser, DENSITY live cost ≈ 4.30 pp, so a busier band could move OpenWSFZ's edges, not WSJT-X's, by an amount this run cannot say); one build of each decoder, one WSJT-X install; the other station is assumed to run WSJT-X, JTDX and MSHV are not measured; **two SNR levels only (−16 and −8 dB, full-signal SNR by the Amendment 3 convention): an edge at another SNR is not interpolated** (the edges did not move between the two, which is a reason to expect little movement between them, not a measurement).
6. **Precision, and the replicate sentence:** 32 signals per cell give a Wilson 95 % half-width of about ±16 pp at r = 0.5; the edge is located to one grid step (0.25 s) where the fall is steep, and no better. **Cycles of one composition are replicates, so the effective number of independent neighbourhoods per cell is 8, not 32** (25 distinct 16-cell compositions in the late block and 13 in the early block, each used in exactly 4 cycles with different slot assignments; QA's audit of the manifest, 22 of 22 rows). Signals in one cycle share a noise realisation and decoder state. This report draws no conclusion from a one-step difference between decoders. The cliffs (32/32 beside 0/32) are not a precision question; the position of OpenWSFZ's early transition between −2.00 and −1.75 is.

## 5. Predictions (the Architect's table; the Architect scores at ruling time)

| # | Prediction | Reading from this run |
|---|---|---|
| LT1 | E50(WSJT-X, −8 dB) in [2.25, 3.00] | **HIT**: 2.75 |
| LT2 | E50(OpenWSFZ, −8 dB) > E50(WSJT-X, −8 dB) | **MISS**: equal, 2.75 and 2.75 |
| LT3 | Q2, k = 0: fewer than 5 % of on-air batch-2 cycles land before E50(WSJT-X, −16 dB) | **HIT**: 1.52 % (DT form), 1.74 % (L form); see §6 |
| LT4 | P1 to P6 all pass first time | **HIT** |
| LT5 | E50e(WSJT-X, −8 dB) in [−2.50, −1.50] | **HIT**: −2.25 |

## 6. Q2: where batch 2 lands on air (descriptive; labelled "on-air night, one CPU, 8 workers")

**Source.** The 2026-09-30 endurance night (`artefacts/20260930_1930_endurance_run/daemon-logs/`, the 3 daemon logs; the middle one is empty; window 2026-09-30 19:30:54Z to 2026-10-01 13:25:45Z): build `feat/sub-feas-two-stage-publish` `247ac391` (the DLL SHA-256 is the same as the edge test's, `ee00d118…`), flag ON, 8 workers, receive only. 4 300 `Cycle` lines, 4 298 residual lines (the two without one are the first and last cycle, as the on-air report §1 says), paired by order.

**Fields (all from the daemon's existing per-cycle lines; line text at `247ac391`, `src/OpenWSFZ.Ft8/`):**

| Quantity | Line | Code |
|---|---|---|
| Cycle label (slot start, UTC) and batch-1 time | `Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms.` (its own log stamp is the publish time of batch 1) | `Ft8Decoder.cs:639` (`sw` started at `:409`, kept running in two-stage mode, `:504`) |
| Residual decodes, residual elapsed | `Sub-feas residual pass: residualDecodes=… elapsedMs=… deadlineAbandoned=… containedException=… fittedSignals=…` | `Subfeas/SubtractionPass.cs:138` (`wall` started `:131`) |

**Decode-start offset is not logged directly.** It is derived: `Cycle`-line stamp − `elapsed` − (cycle label + 15 s). Over the 4 135 cycles used: min −0.013, p5 0.003, **p50 0.032**, p95 0.061, max 0.072 s into the reply slot (so the decode starts about at the slot end, as designed; the design value of 0 would shift every T2 by 0.03 s and no figure below).

**T2** = decode-start offset + batch-1 elapsed + residual `elapsedMs` (the spec formula), for the **4 135 cycles with at least 1 residual decode** (of 4 298 passes; 163 passes found no residual decode and are not in the denominator). Check: T2 from the residual line's own stamp differs from the formula by at most 0.005 s. Batch 1 itself is published at p50 0.557 s (min 0.225, p95 0.632, max 0.696). Reproduced figures of the on-air report as a check on the parse: 4 298 passes, 16 701 residual decodes, mean 3.89, 0 abandoned, 0 exceptions, max `elapsedMs` 9 421; p50 5 002 (the report's 5 001 is the other median convention) and p95 6 421 (the report's 6 423: another percentile convention).

**T2 (s after the reply-slot start):** min 2.066, p5 3.545, **p50 5.711**, p95 6.985, max 9.934.

**Fraction of those cycles with `T2 + k − 0.5 ≤` edge**, for a TX keying latency k. **No keying latency has been measured** (none found in the QA documents or the memory), so the three values stand:

| k | vs `DT_edge` +2.45 (the spec's form) | vs `L_edge` +2.75 (shown beside it) |
|---|---|---|
| 0.0 s | **63 / 4 135 = 1.52 %** | 72 / 4 135 = 1.74 % |
| 0.5 s | 22 / 4 135 = 0.53 % | 53 / 4 135 = 1.28 % |
| 1.0 s | 0 / 4 135 = 0.00 % | 7 / 4 135 = 0.17 % |

The same numbers hold for −8 and −16 dB because E50(WSJT-X) is 2.75 at both. E90 = E50, so a "grace of E90" (option c) is the same threshold. In T2 terms, with k = 0 a reply starts in time if T2 ≤ 3.25 s (L form) or ≤ 2.95 s (DT form); 72 of the 4 135 cycles have T2 ≤ 3.25 s.

**By hour (UTC), to show it is not uniform** (n, median T2, in time at k = 0, DT form): 00Z to 08Z about 240 cycles per hour, median 5.5 to 6.7 s, **0 in time**; 09Z 2/227; 10Z 4/211, median 3.84; 11Z 21/192, median 3.61; 12Z 27/210, median 3.65; 13Z 5/91; 19Z to 21Z 0 of 589; 22Z 4/230; 23Z 0/237. **The in-time cycles are concentrated in the daytime hours (09Z to 13Z, 59 of the 63, up to 12.9 % in the best hour), when the band is thin and the pass is short.** Full table in `results/q2_output.txt`.

**Limits (Q2).** One night, one band (40 m), one CPU with WSJT-X running, 8 worker threads, flag ON, a build that is not `main` (same DLL); other load on the PC during the night was not recorded, and the hours with a lower median (04Z, 21Z, 22Z) are not explained here. The log stamps are the daemon's clock. T2 measures when batch 2 is **published**, not when a reply could be keyed: the QSO service's own latency and the keying latency k are on top, and k is assumed, not measured. The fraction is of cycles with a residual decode, not of cycles in which a reply would be wanted. The partner's tolerance is assumed to be WSJT-X's.

## 7. What this does not do

No claim that batch 2 should or should not drive the auto-QSO: that is the Captain's choice among (a′), (b), (c), made on §5 of the spec. The numbers it rests on: the late edge is 2.75 s in L (2.45 s as a WSJT-X DT) and a cliff; batch 2 is published at a median of 5.7 s into the reply slot, so a reply keyed at once would be late for 98.5 % of the cycles with k = 0 (99.5 % at k = 0.5, all of them at k = 1.0 on the DT form). Option (a′) needs no edge.

## 8. Files (this branch, counts only)

`qa/rr-study/lateness-edge/results/`: `analysis_result_engineer_rerun.json` (byte-identical to QA's), `recount_independent.py` + `recount_cells.json` + `recount_output.txt`, `q2_extract.py` + `q2_result.json` + `q2_output.txt`. SHA-256: `q2_extract.py` `12975fe9…9b79e`, `recount_independent.py` `78a92ed3…8b75`, `q2_result.json` `965c6a89…db7`, `recount_cells.json` `5889c783…703b`. The scripts read the run folder and the daemon logs by absolute path under `D:\Projects\claude\OpenWSFZ\artefacts\` (gitignored, one folder for all worktrees), so they run from any checkout.

**Housekeeping (not mine to do):** `_qa-scratch\edge-run` (build tree and published daemon) stays until the Architect accepts this report; my renders stay in `_qa-scratch\lateness-edge\renders`.
