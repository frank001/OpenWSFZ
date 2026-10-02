# SUB-FEAS §8.1 Real-Band Runtime Replay Report

| Field | Value |
|---|---|
| Run date | 2026-09-29 (timing 20:49Z → 2026-09-30 00:27Z); analysed 2026-09-30 06:14Z |
| Build under test | `2b39cf185ea4d004c730482390147651da5c695b` (`feat/sub-feas-native-subtraction`, base `0d6b1937`), shim `20260055` |
| `libft8.dll` pin, build under test | actual `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` / pinned (expected) `5a6a4dc0…e38c5`, **match**. Self-referential: no independent pin exists |
| R0 producing DLLs | `84cac119` (runs 20260922_2056, 20260923_1730) and `51e40b55` (20260925_2010): actual = expected = `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba` for both |
| Flag | `decoder.subtractionEnabled`, each selected cycle decoded OFF and ON, order alternated by cycle parity |
| Spec | `qa/rr-study/2026-09-29-2010-architect-sub-feas-8-1-real-band-runtime-replay-spec.md` incl. Amendment 1 and Amendment 2 (Architect's worktree, `arch/subtraction-feasibility`) |
| Harness | `cd36bb42017012a805b561418c6b55f9cac87873` (C#, public `Ft8Decoder`; tree clean, `preflight.json`); rows script `0a53979e23410e1f970bc95597efd9778d950c28` |
| Selection | `selection.json` SHA-256 `730d6ea61f25ba8cad90520a17266b3efe0e1e476b1bd1ce29d1a6cbcc3b1f15`, committed `f16d23be` before any timing; re-hashed at analysis, identical |
| `--filter` | none. This is a replay harness, not a test run; no test suite was filtered |
| Machine | AMD Ryzen 7 7800X3D, 8C/16T, 64 GB. `env_start.txt` / `env_end.txt` in the artefact dir |

> 🔴 **Bottom line.** **R1 FAIL, R2 FAIL, R3 PASS, R6 PASS.** The cooperative deadline guard does **not** hold the
> pre-registered 13 000 ms whole-call budget on real busy cycles: 765 of 905 flag-ON cycles (84.5 %) exceeded it,
> maximum **16 309 ms**. The guard also abandoned the residual pass in **531 of 605 (87.8 %)** heavy cycles.
> Nothing crashed. This is a runtime result only: **no decode-rate claim** (R7 is descriptive).

## Section 1 — Study hypothesis

**Question (spec §header).** With `decoder.subtractionEnabled = true`, does a busy REAL cycle stay inside the 13 s
decode budget on the station's hardware, without crashing, and how often does the cooperative deadline abandon
the residual pass?

**Answer.** No, on the registered predicate; and yes, it does not crash.
- **Budget (R1):** FAIL. The guard is cooperative (`SubtractionPass.cs:62`, "checked before/after each native phase"), so
  the whole call ran past its deadline: median flag-ON call 13 841 ms, p95 14 763 ms, max 16 309 ms.
- **Headroom (R2):** FAIL on both terms (max 16 309 > 10 000; p95 over H 14 809 > 6 000).
- **Stability (R3):** PASS. 0 access violations, 0 contained exceptions, 0 non-zero process exits, 0 CSV rows with an exception.
- **Abandon rate (R4):** 87.8 % over H, far above the spec's pre-recorded 5 % flag: on a busy real band the pass is
  mostly cut off by its deadline (the spec's own reading: "mostly inert on busy bands", see Section 5 for why that phrase is too strong).
- **Stress (R6):** PASS on the registered bar (max 14 089 ms ≤ 16 000 ms), see the caveat in Section 4.

**Claims NOT made.** No decode-rate claim. One corpus family, no residual-pass attribution beyond the log line.
No claim above 32 real pass-0 signals (Section 3). Nothing about the live path beyond this offline replay.

## Section 2 — Selection and instrument validity

**Selection (frozen before timing; sorted-at-construction, seed 20260929).**

| Run | Stratum | Cycles | Contiguous blocks (15 s adjacency) |
|---|---|---:|---:|
| 20260922_2056 (Voicemeeter B1) | H | 161 | 161 |
| 20260922_2056 | M | 100 | 96 |
| 20260923_1730 (direct CODEC) | H | 406 | 290 |
| 20260923_1730 | M | 100 | 97 |
| 20260925_2010 (direct CODEC) | H | 38 | 36 |
| 20260925_2010 | M | 100 | 100 |
| **Total** | H 605, M 300 | 905 | |

Per the spec the effective N for any rate is the block count, not the cycle count. Also selected: 60 pilot (20 per run), 20 R6 pairs.

**Disclosed interpretations (made in `select_81.py` before any timing was read).**
- Pilot = 20 cycles **per run** (Amendment 1). Pilots are excluded from H/M, so H = **605**, not the spec's "611 per QA's count" (the 6 difference is pilot cycles that would otherwise have been H).
- Contiguous block = maximal run of stamps exactly 15 s apart within one run and one stratum.
- R6 pairs = the 20 lowest stamps of the pooled H list, each paired with the next H stamp.

**R0 (instrument validity): PASSED, 20/20 within ±1 on every run** (through each run's producing DLL; Amendment 1).

| Run | within ±1 | Δ histogram |
|---|---:|---|
| 20260922_2056 | 20/20 | −1:1, 0:18, +1:1 |
| 20260923_1730 | 20/20 | 0:19, +1:1 |
| 20260925_2010 | 20/20 | 0:20 |

Timing began only after R0 passed on all three. The 180 000-sample assertion is enforced per file in the harness.

## Section 3 — Blind spot (HK-026), stated up front

The instrument's response is **flat above 32 signals on real data**: no real cycle in the corpus exceeds 32 pass-0
decodes. R6 is the only probe above that and it is **synthetic** (two real cycles summed). A PASS on any row means "no
problem found up to 32 real signals", never "safe on any band". Here the rows that failed do so *inside* the covered range.

## Section 4 — Rows

### R1 (read jointly with R4, Amendment 1) and R2 — timing

Flag-ON whole-call elapsed, ms (`time_*.csv`, `elapsed_ms`); flag-OFF shown for scale.

| Run | Stratum | n | ON median | ON p95 | ON max | OFF median | Abandoned (log) | Abandon % | ON ≥ 12 500 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20260922_2056 | H | 161 | 13 444.5 | 14 067.1 | 14 925.1 | 472.6 | 103 | 64.0 % | 104 |
| 20260922_2056 | M | 100 | 12 362.9 | 14 366.9 | 14 705.4 | 505.6 | 44 | 44.0 % | 46 |
| 20260923_1730 | H | 406 | 13 918.4 | 14 898.9 | **16 309.0** | 479.3 | 390 | 96.1 % | 393 |
| 20260923_1730 | M | 100 | 13 897.9 | 14 762.6 | 15 003.6 | 528.0 | 92 | 92.0 % | 92 |
| 20260925_2010 | H | 38 | 13 963.1 | 14 124.8 | 14 136.9 | 486.2 | 38 | 100 % | 38 |
| 20260925_2010 | M | 100 | 13 996.7 | 14 730.7 | 15 094.6 | 509.5 | 98 | 98.0 % | 98 |
| **H ∪ M** | | **905** | **13 840.9** | **14 762.6** | **16 309.0** | | | | |

- **R1:** max 16 309 ms vs bar 13 000 ms ⇒ **FAIL**. Over the bar: **765 / 905** (147/261, 482/506, 136/138 by run). Over 14 000 ms: 260; over 15 000 ms: 15; over 16 000 ms: 1. Only 140 of 905 calls finished inside 13 000 ms. The per-cycle stamp list is in `rows.json` (`R1.over_bar`; stamps and integers only).
- **R1 read jointly with R4:** the maxima sit at 13–14 s **because** the guard fired. In the abandoned cycles the pass runs to its deadline and then some. So the calls are not "slow because the pass is heavy and unbounded", they are "clamped by a guard that overshoots".
- **R2:** max 16 309 > 10 000 and p95(H) 14 809.3 > 6 000 ⇒ **FAIL** (both terms). Because R1 also fails, R2 is not a PARTIAL.
- For the flag-OFF path, the median whole-call cost is 473–528 ms in every stratum (max 830 ms). OFF is unaffected.

**Overshoot (descriptive).** The build passes `SubtractionCycleBudget − pass-0 elapsed` (13 s budget, `Ft8Decoder.cs:70,374`) as the residual pass's deadline. The whole-call maximum is therefore **+3 309 ms past 13 s**. The mechanism is consistent with one uninterruptible native phase running past a between-phase check; **that is not measured**, the build logs no per-phase time.

### R3 — stability: PASS

| Check | Result |
|---|---|
| Access violations | 0 — grep `WARN-TEMPLATE .*access violation` over the 7 harness logs |
| Contained exceptions (warning) | 0 — grep `WARN-TEMPLATE Sub-feas residual pass failed` |
| Contained exceptions (log line field) | 0 — `containedException=True` on 0 lines |
| CSV rows with an exception | 0 |
| Harness process exits ≠ 0 | 0 of 10 invocations (`process_exits.log`; 3 R0 pilots, 6 H/M blocks, 1 R6) |
| Orphan check | `empty` (`orphan_check.txt`) |

### R4 — deadline-abandon rate (report only; flag threshold 5 % over H, recorded in the spec before the run)

Grep: `Sub-feas residual pass: residualDecodes=` (Amendment 2). **Lines == cycles asserted per stratum: TRUE in all 6 blocks** (the log has one extra line per block from the discarded warm-up cycle, which the harness excludes; `mismatched_blocks` empty).

**H: 531 / 605 = 87.8 %** ⇒ flagged (> 5 %). M: 234 / 300 = 78.0 %. Per run/stratum in the Row R1 table above (20260923_1730 and 20260925_2010, both direct-CODEC, are 92–100 %; 20260922_2056 is 44–64 %).
`fittedSignals` means signals **selected** for fitting (Amendment 2), not fitted; the mean is 22.9 over all 905 cycles.

### R5 — flag-OFF cost: not available

Archived daemon per-cycle timing does not exist for any of the three runs. Report only, so no bar is unmet; OFF median 473–528 ms is given above for scale.

### R6 — synthetic stress: PASS on the registered bar

| Item | Value |
|---|---|
| Pairs | 20 (two real H cycles summed, renormalised, peak asserted) |
| ON elapsed max | 14 089.4 ms |
| Bar | 13 000 + **3 000 (constant fixed by Amendment 1 before the run)** = 16 000 ms ⇒ PASS |
| AV / contained / rows with exception | 0 / 0 / 0 |
| Abandoned | 18 / 20 |
| Decodes (pass-0 + residual) | 17 – 27 (max `fittedSignals` 27) |

**Caveat, stated after the fact and not used to change the row:** the real-band max (16 309 ms, one cycle above 16 000 ms) exceeds the R6 allowance constant. The 3 000 ms allowance did not bound real-band overshoot (3 309 ms). R6 is synthetic and the row's verdict stands as registered.

### R7 — descriptive only (no claim, no bar)

ON − OFF decode count per cycle (`decodes` column; a **difference in count, not a subtraction gain**, and not attributed by the build).

| Run | Cycles | Mean ON−OFF | Cycles with 0 | Non-zero | Max | Mean `residualDecodes` |
|---|---:|---:|---:|---:|---:|---:|
| 20260922_2056 | 261 | +1.68 | 149 | 112 | 9 | 2.01 |
| 20260923_1730 | 506 | +0.20 | 482 | 24 | 13 | 0.24 |
| 20260925_2010 | 138 | +0.04 | 136 | 2 | 3 | 0.06 |
| **All** | **905** | **+0.60** | **767** | **138** | **13** | **0.72** |

**Do not pool for a headline** (spec §1). The per-run means differ by a factor of ~40 and the runs differ by chain (B1 vs direct CODEC) and by abandon rate; both are confounded and neither is separated here. The ON count was never lower than OFF in any cycle in this table's histogram.

## Section 5 — Recommendations

1. 🔴 **Registered outcome: FAIL** (R1, and R2 by the same evidence). Merge sign-off and any live use are the Captain's call (HK-010/033); QA does not advise "PASS with notes". The flag stays OFF by default and in every live run.
2. **R2 is not repairable by tuning the budget.** 87.8 % of H cycles run until the deadline, so the ON call is ≈ the budget by construction. Bringing max ≤ 10 s and p95(H) ≤ 6 s needs the residual pass to **finish sooner on 24-signal cycles**, not to be cut off sooner. The FFT-only estimate in the spec (~26 s at 24 signals before parallelism) is consistent with this; that estimate is not re-derived here.
3. **The overshoot (R1) is a separate defect from the speed.** A guard that checks between native phases cannot promise a wall-clock bound better than its longest phase. Whether the whole-call bound must be hard (given the ~15 s cycle) is a design question for the Architect/Captain. **Any change is `src/`; QA proposes and stops (HK-011).**
4. **"Mostly inert on busy bands" is too strong.** In 138/905 cycles (15.2 %) the ON path produced a different decode count, and never fewer. Whether abandoned cycles contribute anything is **unmeasured**, and R7 makes no claim.
5. **Operational note (inference, not a measurement):** a flag-ON call of ≈ 14 s in a 15 s cycle leaves ≈ 1 s; this bears on the standing decode-panel latency item (#122, on hold). Not assessed here.
6. **§7 stability gate and §8.2 (independent real corpus) remain unsatisfied; §8.1 is now read and failed on R1/R2.** Nothing in this report supports lifting the flag-OFF default.

## Section 6 — Historical trend

None. This is the first §8.1 replay. Section 6 of the standard R&R report is the S1–S8 sweep trend, which does not apply to a timing replay. The closest prior runtime datum is the paired R&R (`2026-09-29-0d6b193-subfeas-off-vs-on`): max 2.49 s on sparse synthetic scenes (≤ 11 decodes/cycle), zero `Sub-feas` lines; the 0d6b1937 build had no log line to attribute abandonment. It is **not** comparable to the real-band numbers above.

## Provenance and hygiene

- **Environment (`env_start.txt` / `env_end.txt`):** the machine was not idle. Voicemeeter, iCUE, Firefox/Chrome, Steam, Radeon Software, and WSJT-X (`wsjtx`, `jt9`) were resident throughout (jt9 +3.6 CPU-s and wsjtx present at start/end, listening on B1); whether a live OpenWSFZ daemon was also running is not recorded. The replay was serial (one harness process at a time). **Unquantified:** a possible effect of this background load on the ON timings (the spec asked that it be recorded, not modelled).
- **NFR-021 / HK-037:** the harness and this report read and record **stamps and integers only**; no message text left the function reading `ALL.TXT`. `rows.json` holds stamps and integers. Raw CSV/logs remain in the gitignored `artefacts/rr_2026-09-29_replay81/`.
- **Artefacts:** `qa/rr-study/results/2026-09-29-sub-feas-8-1-replay/` holds `selection.json` (frozen), `rows.json` (R0–R7 aggregates) and this report.
- **Not disclosed elsewhere and worth a look by the Architect:** the R1 predicate is over the **whole call** (pass-0 ≈ 0.5 s + residual pass), as pre-registered; the residual pass alone (`elapsedMs` in the log) is ≈ 0.5 s shorter than the numbers above.
