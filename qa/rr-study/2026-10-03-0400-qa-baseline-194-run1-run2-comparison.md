# R&R S1-S8 NEW BASELINE with the #194 improvements: run 1 (baseline) and run 2 (confirmation)

- **From:** QA  **To:** Architect, Captain  **Date:** 2026-10-03 03:19Z (the time of the commit that first carried this document, `b248c8f9` at 03:19:14Z; corrected 09:2xZ by `date -u`, HK-017: it first said "~04:00Z", ahead of the clock, and the `0400` in the file name is that same wrong stamp, kept only because other documents cite the name)
- **Order (Captain, 2026-10-03):** a new R&R S1-S8 baseline carrying the #194 improvements (S3c in the battery, the captured-audio scan in the analysis), then a second run to confirm it. Build `main` with subtraction ON.
- **Result: BASELINE CONFIRMED.** Both runs PASS overall, S3c PASS twice, scan completed twice (not SKIPPED), no config drift, no orphan daemon.

## 1. Provenance (HK-022: the pins)

| item | value |
|---|---|
| Build | `main` `cddd7e340d922abddefbbe1dc9ff35e76ec93e7d` (v0.54, src/native identical to `b87529a3`; later commits are docs only) |
| `libft8.dll` SHA-256 | `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` (the same in the source tree and the published daemon), shim 20260056 |
| Publish | `tools/publish_selfcontained.py` (`-p:PublishAot=false`), NEVER a raw `dotnet publish` (a trimmed publish killed NAudio's COM interop, exception E7) |
| Flag / config | `subtractionEnabled` true read back over `GET /api/v1/config`, `osdNhardMax` 40, `nhard40MigrationApplied` and `subtractionOnMigrationApplied` true, `subtractionMaxThreads` 0 (auto), `kMinScorePass2` 10; the tracked flag-ON R&R template with only the output paths changed |
| Scenario list | S1, S1b, S2, S3, S4, S5, S7, S8, then S3c; identical seeds in both runs |
| S3c scenario SHA-256 | `dc3a3fe87de0f227bf51e952cd085888ef3c873cc2a912f345c909a0af9604aa` (points L +2.75, +3.00, E -1.75, -2.00 picked mechanically from the accepted edge run) |
| Scan freeze | `thresholds.json` `c1d793ec...26d8d`, `scan_core.py` `582f422e...2a21`, calibration run `2026-09-23-5f17b43` |
| `--filter` | none (a battery, not a test run). Tests: `pytest tests/test_s3c.py tests/test_lateness_edge.py` 42 passed before the runs |
| Station | radio off, `Voicemeeter AUX Input` -> B1; pre-flight before run 1: chain RMS 0.000 over 12 s, warm-up decoded by both apps; WSJT-X 2.7.0 NDepth 3 |
| Run 1 | 2026-10-02 23:15:56Z to 2026-10-03 01:09:17Z, `results/2026-10-02-96077a0` |
| Run 2 | 2026-10-03 01:16:24Z to 03:10:01Z, `results/2026-10-03-96077a0` |

The run directory names carry the QA tooling commit `96077a0f` (branch `qa/baseline-194`), not the daemon build: the analyser's "OpenWSFZ SHA" field was corrected by hand in both reports (fourth occurrence of that defect).

## 2. Comparison

| metric | run 1 (baseline) | run 2 (confirmation) |
|---|---|---|
| Overall verdict | PASS | PASS |
| S1 %GR&R / ndc | 0.14% / 37 | 0.19% / 31 |
| S2 %GR&R / ndc | 0.00% / 1491 | 0.00% / 1536 |
| S3 %GR&R / ndc | 0.51% / 19 | 0.71% / 16 |
| SNR bias S1, WSJT-X / OpenWSFZ | +0.82 / +0.92 dB | +0.82 / +0.85 dB |
| kappa vs truth, WSJT-X / OpenWSFZ / between | 0.932 / 0.909 / 0.946 | 0.955 / 0.909 / 0.954 |
| S5 AWGN FP, WSJT-X / OpenWSFZ | 0/120, 0/120 (Gate A-W 0/480, UB 0.622%) | 0/120, 0/120 (Gate A-W 0/480) |
| S5 Check B (narrowband) | WSJT-X 1/60, OpenWSFZ 0/60 | 0/60, 0/60 |
| S7 recovery, WSJT-X / OpenWSFZ | 95.35% / 79.53% | 99.07% / 82.79% |
| S8 decode rate, WSJT-X / OpenWSFZ | 91.67% / 91.67% (55/60 each) | 93.33% / 91.67% |
| Pooled S7+S8, OpenWSFZ as % of WSJT-X | 86.92% (226/260) | 86.62% (233/269) |
| Unexplained decodes (info), WSJT-X / OpenWSFZ | 1 / 3 | 0 / 3 |
| S3c rows | WSJT-X validity PASS; OpenWSFZ guard PASS | PASS; PASS |
| S3c OpenWSFZ X per part (L90 / L50 / E90 / E50) | 32 / 0 / 32 / 17 | 32 / 0 / 32 / 16 |
| Config drift rows | 0 | 0 |
| Scan flagged slots (of 407) | 38 | 47 |

Reading. Every gate PASSES in both runs and the two runs agree on every metric the series treats as stable (S1-S3 %GR&R, S5, S8, the pooled ratio within 0.3 pp). S7 moved by +3.7 pp (WSJT-X) and +3.3 pp (OpenWSFZ); S7 is instrument-suspect by standing rule, and the OpenWSFZ-minus-WSJT-X gap (15.8 and 16.3 pp) stays inside the known band. No S7 finding is drawn.

## 3. S3c (flag direction and what each row can see)

Both batteries: every non-descriptive part decoded 32/32 for both decoders except OpenWSFZ at E -2.00 (17/32 and 16/32 against 14/32 in the edge run, r_ref 0.28, k* 4). That row detects a COLLAPSE of the early transition, not a one-step shift. The L +3.00 row is 0/32 for both decoders and DESCRIPTIVE (k* 0), so the late side's only live guard is L +2.75. The battery ran with the flag ON while the reference rates come from a flag-OFF edge run: batch 1 equals flag OFF, so ON can only add matches and biases S3c toward PASS. S3C1/S3C2 are the Architect's blind predictions, scored at the third battery; two batteries are recorded so far.

## 4. Scan

Both scans completed after the gather (the first took 278.7 s on one core). No `RUN-LEVEL` offset in either run (every `g_db` median within +-0.05 dB of the calibration median). Findings by class, run 1 / run 2: BOTH 48 / 44, OpenWSFZ-only 10 / 10, WSJT-X-only 37 / 40, cross-side 4 / 4. Most are S5 noise slots. Run 2 shows 11 OpenWSFZ noise-group slots beyond the frozen timing threshold against 0 in run 1 (2 and 1 after re-centring on the run's own median): a run-level timing offset, the A11 evidence, not a slot event. None of this is a decoder defect by construction (a WAV is recorded before either decoder runs). The scan's holes stand: 30 descriptive cells, 12 above range; it cannot see a short added sound or a click in those groups; 43% of slots are REF-UNVERIFIABLE (limit 50%).

## 5. Exceptions

The full log is `qa/rr-study/results/2026-10-03-baseline-194-exceptions.md` (19 entries). The ones that matter for reading the runs: E7 (the trimmed publish, found by the precheck trial before any audio), E13 (a watchdog false alarm during S5: my silence limit was too short), E15 (no separate pre-flight for run 2; checked afterwards), E16 (the S3c scorer counted a cumulative log's earlier battery as wrong-cycle; fixed with a test, both runs re-scored; match counts were never affected).

## 6. Proposals (the Architect decides)

1. RUNBOOK 5.4: run the scan BEFORE the HTML render and quote it in `report.md` (done in that order here); a script, `baseline_assemble_report.py`, does it.
2. `analyse.py` should take the build commit from `arm_config.json`.
3. `run_study.py` should write a per-run record of the S3c flag state itself instead of relying on forwarded arguments.
4. Merge the QA tooling of `qa/baseline-194` (S3c, restored detached launcher, pre-flight, report assembler) into `main`.
