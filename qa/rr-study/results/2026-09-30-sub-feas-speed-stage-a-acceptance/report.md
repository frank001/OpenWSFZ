# SUB-FEAS Speed Redesign, Stage A: Acceptance and Code Review Report

| Field | Value |
|---|---|
| Run date | 2026-09-30 (timing 10:11Z → 13:54Z); analysed 13:55Z (`date -u`) |
| Build under test | `feat/sub-feas-speed-redesign` @ `ca0bcd9b` (base `feat/sub-feas-native-subtraction` `ab95bea1`, code `2b39cf18`), shim `20260056` |
| `libft8.dll`, candidate | actual `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` / pinned (Developer's report) `ee00d118…990e4c`, **match**. Extracted from the committed git blob by QA; also the DLL next to the candidate harness. Self-referential: no independent pin exists |
| `libft8.dll`, base | actual `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` / pinned `5a6a4dc0…e38c5`, **match** (git blob of `ab95bea1`; also the DLL of the harness build `2b39cf18`) |
| R0 producing DLLs | `84cac119` and `51e40b55`: actual = pinned = `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba` |
| Spec | `qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §2 incl. Amendment 1 (`arch/subtraction-feasibility` `b653298e` and the following commit) |
| Selection | §8.1 `selection.json` SHA-256 `730d6ea61f25ba8cad90520a17266b3efe0e1e476b1bd1ce29d1a6cbcc3b1f15` (frozen `f16d23be`); E1 `e1_selection.json` SHA-256 `f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2` (frozen `c40fc850` **before any hash was computed**) |
| Harness / orchestrator | commit `8d7eadb3dd2d808d0e4bd0e2b97b7134a08b6e82`, tree clean at preflight. Harness = §8.1 `Replay81` (`cd36bb42`) with **one** change: an optional `--threads` argument (candidate build only). Harness DLL SHA-256: candidate `be584eba079e…`, base `cebc57603432…`, R0 builds `4d780fccdb32…` / `ba1466cfa1ad…` (full values in `preflight.json`) |
| Machine | AMD Ryzen 7 7800X3D, 8 cores / 16 logical, 64 GB. **WSJT-X closed** (the orchestrator asserts no `wsjtx`/`jt9`/`OpenWSFZ` process before it starts and refuses otherwise); `env_start.txt` / `env_end.txt` list the top processes |
| `--filter` | none. E1 and timing are not test runs. The one test run quoted below is `dotnet test OpenWSFZ.slnx`, unfiltered |

> 🔴 **Bottom line.** **Stage A registered outcome: FAIL, on R2′ alone.** Seven of the eight rows pass: **E1 PASS**
> (3 878 of 3 878 rows bit-identical on real cycles, at 14 and at 4 threads), R0, **R1′ PASS** (max **8 650.2 ms**,
> 0 of 905 over 13 000 ms), R3, **R4′ PASS** (**0 of 605** heavy cycles abandoned; was 531), R5′, R6. **R2′ fails on its
> p95 term: 6 410.8 ms against 6 000 ms** (its max term passes, 8 650.2 ≤ 10 000). Per the spec, a Stage A that fails only
> R2′ sends the Architect and the Captain to **Stage B**, item by item. **No bar was moved.** The code review found no defect.
> This is a runtime result only: **no decode-rate claim**.

## Section 1 — Study hypothesis

**Question.** Does Stage A (exact optimisations A1–A3, hard deadline A5, threads A4, lean hot path M2/M3) bring the flag-ON
decode of a busy real cycle inside the budget, without changing what the fit computes?

**Answer.**
- **Exactness (E1): yes.** Every (cycle, signal) fit hash and return code, and every pass-0 outcome, is identical to the base DLL.
- **Hard bound (R1′): yes.** Max whole call 8 650.2 ms; nothing near 13 s. The §8.1 build's max was 16 309 ms.
- **Usefulness (R4′): yes.** The residual pass now **completes** in every one of 605 heavy cycles (§8.1: 531 abandoned).
- **Headroom (R2′): not quite.** p95 over the heavy cycles is 6 410.8 ms (bar 6 000): 84 of 605 heavy cycles exceed 6 000 ms.
- **Stability (R3), stress (R6), flag-OFF cost (R5′): yes.**

**Claims NOT made.** No decode-rate claim. No live use (the flag stays OFF; base-change §7 and §8.2 stay open). No claim
above 32 real signals (Section 3). No claim for other hardware.

## Section 2 — Code review (tasks §12.1) and instrument validity

**QA code review of `ab95bea1..ca0bcd9b`: no defect found.** Read in full: `subfeas_fit.c` (A1, A2, A3, A5), `subfeas_fit.h`,
the `ft8_shim.c` M2 gate, `SubtractionPass.cs`, `Ft8Decoder.cs`, `Ft8LibInterop.cs`, `SubtractionThreads.cs`, the config, POST and
shutdown wiring, `ci.yml`, and the test inventory against `tasks.md` §8.
- **A1/A2:** same arithmetic in the same order; the smoothed track is held as `cf32`, the precision the old code held it at (design D1). Spectra are computed once per workspace with the same plan.
- **A3:** bounded, locked pool; leases returned on every exit path, including after an access violation (poisoned workspace leaves the accounting); a lease beyond the bound is refused, counted, never allocated; no thread-local state; dispose frees idle now and leased on return.
- **A5:** trailing `const volatile int*`; checked at entry and at the top of every Δt, ḟ, step-3 and envelope iteration; the managed side pins the flag and frees it only after `Parallel.For` returns; `-4` is returned as a value and mapped to a deadline abandon, not an exception.
- **M2:** the added `continue` sits at the end of the already-failed-candidate branch, which ended in `continue` anyway; the noise floor is untouched.
- **Reserve** 1 500 ms as a named constant; **thread config** `0` = auto, clamp `[1, ProcessorCount]`, one warning at apply.

**QA's own full test run** (independent of the Developer's), scratch worktree at `ca0bcd9b`, command
`dotnet test OpenWSFZ.slnx` (**no filter**): **1 623 passed, 1 failed** (Traceability 34, LicenseInventory 24, Rig 41, Audio 23,
Config 105, TestSupport 12, E2E 7, Web 318, Daemon 651 passed + 1 failed, Ft8 408). The failure is
`CycleArchiveServiceTests.Manifest_WritesOneRowPerArchivedCycle_InOrder`, the known load-sensitive manifest flake on the board
(`Poll.UntilAsync` timeout); it **passes alone** (1/1, re-run). The Developer's own run was 1 624 / 0.

**Two Developer-flagged items, reviewed:**
1. `.github/workflows/ci.yml` now compiles and links `subfeas_fit.c` on Linux and macOS (an inherited gap: those recipes never carried the `ft8_subfeas_*` exports). Reasonable and necessary for the new tests. Linux compile verified by the Developer via WSL; macOS **not verified** by anyone.
2. `REQUIREMENTS.md` FR-077 and change-log row 1.51 assume the config-save change (FR-074..076, row 1.50) merges first: renumber otherwise. A merge-order dependency for the Captain, not a defect.

**E1 (real corpus).** 161 cycles: 101 = every 9th `(run, stamp)` of the pooled, sorted H ∪ M list, plus the 60 pilot cycles
(Amendment 1). Both DLLs decode pass-0 themselves and fit every re-encodable decode with **no deadline**; the row carries
`rc`, `sha256(out_shat)`, the pass-0 count and the pass-0 outcome hash (outcome fields, never text). Two probe builds were
used on purpose: the probe links the current managed interop, which rejects a DLL of another shim version, so the base DLL
was probed with the probe as of `348e067e` (the commit that recorded the Developer's golden) and the candidate with the
probe at `ca0bcd9b`; both write the same CSV schema. Reference = base at 14 threads.

| Run | Rows | Identical to reference | Differing rows |
|---|---:|---|---:|
| base, 14 threads (reference) | 3 878 | (self) | 0 |
| candidate, 14 threads | 3 878 | **yes** | 0 |
| candidate, 4 threads | 3 878 | **yes** | 0 |

Rows: 161 analytic buffers, 3 629 fits with rc 0, 87 with rc −3 (a fit near a buffer edge). The Developer's synthetic golden had 22 of
its 62 rows at rc −3; here only 2.3 % of fits are rc −3, so the real-corpus E1 exercised the full fit path on 3 629 fits. **E1: PASS.**

**R0 (instrument validity): PASSED, 20/20 within ±1 on every run** (through each run's producing DLL), the same predicate and
result as §8.1. Run in the same session as the timing.

## Section 3 — Blind spot (HK-026), stated up front

The response of this instrument is **flat above 32 signals on real data**: no real cycle in the corpus has more than 32 pass-0
signals, and the most any heavy cycle here fitted was **31**. R6 is the only probe above that and it is synthetic. A PASS means
"up to 31 real signals on this machine", **not** "safe on any band" and **not** "safe on other hardware". `subtractionMaxThreads`
defaults to `ProcessorCount − 2`, so a 4-thread machine gets 2 fit workers, and nothing here says it meets 13 s. Section 4 shows
the fit time is **not flat in the signal count**, and the steepest part is at the top of the covered range.

## Section 4 — Rows

### R1′, R2′, R4′: flag ON, whole call (candidate, 14 workers by default)

| Run | Stratum | n | ON median | ON p95 | ON max | OFF median | Abandoned | Abandon % | ON ≥ 12 500 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20260922_2056 | H | 161 | 5 516.4 | 5 851.6 | 6 145.6 | 476.4 | 0 | 0 % | 0 |
| 20260922_2056 | M | 100 | 5 517.4 | 6 047.7 | 6 193.1 | 532.7 | 0 | 0 % | 0 |
| 20260923_1730 | H | 406 | 5 612.75 | 6 543.2 | **8 650.2** | 472.9 | 0 | 0 % | 0 |
| 20260923_1730 | M | 100 | 5 112.1 | 5 514.9 | 5 932.5 | 513.25 | 0 | 0 % | 0 |
| 20260925_2010 | H | 38 | 5 416.15 | 5 955.9 | 6 043.9 | 475.75 | 0 | 0 % | 0 |
| 20260925_2010 | M | 100 | 4 937.5 | 5 296.7 | 5 341.5 | 501.25 | 0 | 0 % | 0 |

Time in ms. `Sub-feas residual pass: residualDecodes=` log lines **equal** the ON cycles in every one of the six blocks (asserted).
Contiguous blocks are as in the §8.1 report (161/96/290/97/36/100); the effective N for any rate is the block count, not the cycle count.

- **R1′ (max ≤ 13 000 ms over H ∪ M): PASS.** Max **8 650.2 ms**, **0 of 905** over the bar (§8.1: 765 of 905 over, max 16 309 ms).
- **R2′ (max ≤ 10 000 ms AND p95(H) ≤ 6 000 ms): FAIL.** Max 8 650.2 (pass); **p95(H) = 6 410.8 (fail, over by 410.8 ms, 6.8 %)**.
  84 of 605 heavy cycles exceed 6 000 ms; 23 exceed 6 500 ms. Not a PARTIAL: R2′ is a Stage A row, and the spec names it as a Stage B trigger.
- **R4′ (abandon over H ≤ 5 %, a BAR): PASS.** **0 of 605** (0/161, 0/406, 0/38). The guard **did not fire once** at the default thread count,
  in H or in M. **So the A5 hard deadline was not exercised at 14 workers on real cycles.** It was exercised at 4 workers (row T below) and by the unit tests.

**What drives the p95 (descriptive, from the same log lines; `fittedSignals` = signals *selected* for fitting).**

| Signals fitted | 17–19 | 20–22 | 23–24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Heavy cycles | 12 | 111 | 205 | 115 | 82 | 36 | 23 | 9 | 9 | 3 |
| Median ON, ms | 5 434 (at 19) | 5 303 (at 22) | 5 485 (at 24) | 5 652 | 5 846 | 6 042 | 6 377 | 7 134 | 8 404 | 7 892 |

The whole call **rises with the signal count**, and steps up beyond 28. With 14 workers, 28 signals is two full waves; 29 or more needs a third.
The 21 cycles with 29+ signals (3.5 % of H) have per-count medians of 7.1–8.4 s (max 8.65 s) and set the top of the tail; the 28-signal cycles (median 6 377 ms) put the
p95 just above 6 000. The residual pass alone is a median 5 065 ms of a 5 551 ms whole call. **Not measured:** why one fit at 14 concurrent
workers costs about twice the Developer's single-thread 1.26 s; a memory-bandwidth or cache contention explanation is a hypothesis, not a finding.

### R3 — stability: PASS

| Check | Result |
|---|---|
| Access violations | 0. Grep `WARN-TEMPLATE .*access violation` over all harness logs |
| Contained exceptions (warning) | 0. Grep `WARN-TEMPLATE Sub-feas residual pass failed` |
| Contained exceptions (log-line field) | 0 (`containedException=True` on 0 lines) |
| CSV rows with an exception | 0 |
| Harness process exits ≠ 0 | 0 of 25 invocations (`process_exits.log`: 3 R0 pilots, 12 candidate/base H and M blocks, 1 R6, 3 T blocks, 6 base repeats) |
| Orphan check | `empty` (`orphan_check.txt`) |

`-4` deadline outcomes are counted as `deadlineAbandoned`, never as contained exceptions (checked in row T, where they occur).

### R5′ — flag-OFF whole-call median, candidate vs the base DLL **re-measured in the same session** (Amendment 1): PASS

| Run | Candidate OFF median | Base OFF median | Ratio (bar ≤ 1.05) | Base measured again at the end | Repeat / first (noise floor) |
|---|---:|---:|---:|---:|---:|
| 20260922_2056 | 487.7 | 486.2 | **1.003** | 485.9 | 0.999 |
| 20260923_1730 | 480.4 | 481.35 | **0.998** | 484.25 | 1.006 |
| 20260925_2010 | 494.1 | 493.05 | **1.002** | 500.4 | 1.015 |

Medians over H ∪ M per run, ms; n = 261 / 506 / 138 per side. **The change is within ±0.3 %, below the row's own noise floor**
(the same DLL measured twice differs by up to 1.5 %), so the 5 % bar had headroom and the result is not a rounding artefact.
Reported either way, as the spec asks: **M2 + M3 changed the flag-OFF cost by less than 1 % in either direction. Nothing here is
credited to M1: M1 was deferred by the Captain and is not in this build.** (The Architect scores P4.)

### R6 — synthetic stress: PASS (bar 13 000 ms, the +3 000 ms allowance dropped by the spec)

20 pairs (two real heavy cycles summed, renormalised, peak asserted): max ON **6 186.3 ms**; 0 abandoned; 0 AV / 0 contained / 0 exceptions.
Labelled SYNTHETIC; runtime only.

### R7 — descriptive only (no claim, no bar)

ON − OFF decode count per cycle (a difference in **count**, not a subtraction gain; no false-positive check was made; single corpus family).

| Run | Cycles | Mean ON−OFF | Cycles with 0 | Max | Mean `residualDecodes` |
|---|---:|---:|---:|---:|---:|
| 20260922_2056 | 261 | +3.97 | 5 | 9 | 4.75 |
| 20260923_1730 | 506 | +5.06 | 7 | 16 | 5.73 |
| 20260925_2010 | 138 | +3.67 | 1 | 11 | 4.20 |
| **All** | **905** | **+4.53** | **13** | **16** | **5.21** |

**Do not pool for a headline** (spec §1), and **do not read this as a decode-rate result.** The point of recording it is narrower: in §8.1 the
same descriptive row read +0.60 per cycle because 88 % of the passes were being abandoned. Stage A is bit-identical, so the difference
between +0.60 and +4.53 is the pass now **completing**, not the fit getting better. Whether those extra decodes are real, and whether they
are new to WSJT-X, is exactly what base-change §8.2 (an independent real corpus) exists to test, and it is still open.

### T — threads (report only): heavy stratum at `subtractionMaxThreads = 4`

| Run | n | ON median | ON p95 | ON max | Abandoned |
|---|---:|---:|---:|---:|---:|
| 20260922_2056 | 161 | 8 854.5 | 11 138.5 | 11 710.5 | 4 (2.5 %) |
| 20260923_1730 | 406 | 11 511.3 | 11 888.0 | 12 095.2 | 309 (76 %) |
| 20260925_2010 | 38 | 11 515.3 | 11 814.4 | 11 903.0 | 24 (63 %) |

- **Thread effect:** at 4 workers the heavy cycles take about twice as long as at 14 (median 11.5 s vs 5.6 s on the largest run), and 337 of 605 (55.7 %) are abandoned by the deadline, against 0 at the default.
- **A5 works on real cycles.** The hard bound **held**: max whole call **12 095 ms** with 337 abandons, no overshoot past 13 s, 0 access violations, 0 contained exceptions (the −4 outcomes were counted as deadlines). §8.1 overshot to 16.3 s. This is the only place the deadline path ran on real audio.
- **A 4-thread machine, or one with two spare cores, would sit in this regime.** That is the blind spot of Section 3, measured for one point.

## Section 5 — Recommendations

1. 🔴 **Registered outcome: Stage A FAIL on R2′ (p95(H) 6 410.8 vs 6 000 ms).** No bar moved; QA does not say "PASS with a note". Whether a 6.8 % miss on one term is acceptable is the **Captain's and the Architect's** call, not a QA pass. The flag stays OFF by default and in every live run.
2. **Per the registered spec, the miss sends the change to Stage B**, item by item (B1 faster permissive FFT, re-measure, B2 pruned frequency search, re-measure, B3 coarse-to-fine Δt), each accepted on E2 (equivalence) and E3 (no loss of residual decodes), never on speed. **Before choosing an item**, ask the Developer to re-run the `Ft8.FitProbe time` mode on the **candidate** DLL: the per-phase cost map exists only for the base build (step 1 about 890 ms, step 2 about 870 ms), and the candidate's post-A1/A2 split is unmeasured. That is cheap and it ranks the items by evidence rather than by the design's arithmetic.
3. **The miss is small and the tail is in the signal count.** Most of the p95 is the 28-plus-signal cycles. Any lever that cuts per-fit cost helps every cycle; a lever that only packs work into fewer waves would help only the 3.5 % above 28. That is an observation for the choice in item 2, not a recommendation of a specific build change (HK-011: QA proposes, a Developer session applies).
4. **The merge gate for the exact change is a separate question.** The registered merge gates are E1 (met), the flag-OFF control re-run on the new native build (**not yet run**: §10.5 of `tasks.md`), and stability. QA will run the flag-OFF control next on the Captain's go. The base change (`feat/sub-feas-native-subtraction`) is still unmerged and this change depends on it; base-change §7 (sustained stability) and §8.2/§8.3 remain open. **Merge and push are the Captain's** (HK-010, HK-033).
5. **Hardware.** Row T shows the default thread count is doing the work. If the Captain intends live use, a machine-class statement (how many spare cores, what happens below it) belongs in the live-use decision, not only in this report.
6. **FR-077 and the CI change** need a merge order with the config-save branch (Section 2, item 2).

## Section 6 — Historical trend

The only comparable prior datum is the §8.1 replay of the base build (`2026-09-29-sub-feas-8-1-replay/report.md`, same selection, same harness, same machine class; **WSJT-X was resident then and closed now**, which the Architect's Amendment 1 already accounts for in the R5′ baseline).

| Row | §8.1 (`2b39cf18`) | Stage A (`ca0bcd9b`) |
|---|---:|---:|
| R1 max whole call, H ∪ M | 16 309.0 ms (765/905 over 13 s) | **8 650.2 ms (0/905)** |
| R2 p95 over H | 14 809.3 ms | **6 410.8 ms** |
| R4 abandon over H | 531/605 = 87.8 % | **0/605** |
| R7 mean ON−OFF count | +0.60 | +4.53 (descriptive, no claim) |
| R3 | 0 / 0 / 0 | 0 / 0 / 0 |

## Provenance and hygiene

- **Commands.** E1: `python qa/rr-study/sub-feas/run_e1.py` (probe args `e1 --dll <blob> --out <csv> --threads <14|4> --grid 0 --wav …` ×161). Timing: `python qa/rr-study/sub-feas/replay_speed_run.py`; rows: `python qa/rr-study/sub-feas/replay_speed_rows.py`. Log greps: `Sub-feas residual pass: residualDecodes=`, `WARN-TEMPLATE .*access violation`, `WARN-TEMPLATE Sub-feas residual pass failed`.
- **Disclosed interpretations, made before any result was read:** E1 selection as Amendment 1; the base DLL was probed with the pre-change probe (`348e067e`) and the candidate with the current probe; E1 thread counts 14 and 4 (not 1: the single-thread runs would take about 110 minutes each and the Developer already ran 1, 4, 8, 14 on a synthetic grid); the base flag-OFF baseline measured in "off" mode (flag untouched, the same decode path as OFF in "alt"); an added second base-OFF pass at the end as the row's noise floor. R5′ pooled H ∪ M per run.
- **Not done here:** the flag-OFF control re-run (`tasks.md` §10.5), sustained stability (base-change §7), any decode-rate measurement.
- 🔒 **NFR-021 / HK-037:** the harness, probe, orchestrator and this report read and record stamps, integers, hashes and timings only; no message text left the function that reads `ALL.TXT`. Raw CSVs and logs stay in the gitignored `artefacts/sub_feas_speed_acceptance/` and `artefacts/sub_feas_speed_e1/`.
- **HK-019 orphan check:** empty. Scratch worktrees `C:\Users\Frank\w-speed-review` and `C:\Users\Frank\w-e1-base` removed after the report; the harness output directories are kept.
- **Artefacts committed here:** `report.md`, `rows.json` (per-row aggregates; the R1′ over-bar list is empty), `e1_summary.json`, `preflight.json`.
