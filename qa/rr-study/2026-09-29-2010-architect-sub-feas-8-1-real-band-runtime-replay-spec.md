# SPEC — SUB-FEAS §8.1 real-band runtime replay (pre-registered)

- **Date (UTC):** 2026-09-29 (drafted after QA's corpus count, message 2026-09-29 ~19:5xZ)
- **Author:** Architect. **Executor:** QA. **src/native changes:** none (HK-011); replay-only.
- **Question:** with `decoder.subtractionEnabled=true`, does a busy REAL cycle stay inside the 13 s decode budget on the station's hardware, without crashing, and how often does the cooperative deadline abandon the residual pass?
- **Claims NOT made:** no decode-rate claim (single corpus family, no attribution until §4.2). No claim above 32 pass-0 signals from real cycles (see Blind spot).
- **Build under test:** the post-§4.2 merge candidate if it exists when this runs; otherwise `0d6b1937` and say so. Pin `libft8.dll` SHA-256 actual/pinned pair in the report (HK-022). Any report with no pin, or with a `--filter` not quoted, is not a result.

## 1. Corpus and selection (frozen BEFORE any timing is read)

Corpus: runs `20260922_2056`, `20260923_1730`, `20260925_2010` (not the `20260922_1937` smoke test). Cycle key = `ALL.TXT` cycle stamp; audio = the daemon-side `<stamp>.wav` in the gathered `wav/` dir. "Pass-0 count" = OpenWSFZ decodes for that cycle under that run's own build.

Selection, in code, `random.Random(20260929)` over lists **sorted by stamp at construction** (hash-order guard):

| Stratum | Rule | Selected |
|---|---|---|
| H (heavy) | pass-0 count ≥ 25 | ALL (611 per QA's count) |
| M (moderate) | 20 ≤ count ≤ 24 | 100 per run, sampled (300) |
| Pilot | 20 cycles, count ≥ 20, chosen by the same RNG stream FIRST and **excluded** from H/M | for §2 R0 calibration only |

Freeze the stamp lists (stamps only) into a committed `selection.json` and record its SHA-256 before the first timed decode. Report per-run counts in every stratum and the count of distinct contiguous time blocks (busy cycles are band-opening clusters, not independent draws; the effective N for any rate is the block count, not the cycle count). Do NOT pool runs for the headline: report per run, then all (1730/2010 = direct CODEC, 2056 = Voicemeeter B1).

## 2. Rows (mechanical; each is a predicate on the output CSV)

Instrument: replay through the **same C# decode entry the daemon uses** (deadline logic included), not a raw C-ABI call. Each selected cycle decoded twice, flag OFF then flag ON, order alternated by cycle parity to spread drift. Serial, nothing else CPU-heavy on the machine (record what was running). One discarded warm-up cycle per process start. Wall-clock per whole-cycle decode call in ms.

- **R0 — instrument validity (must pass or STOP; nothing below is read).** On the Pilot set, replay flag OFF and compare pass-0 decode COUNT to the archived count for that stamp: |Δ| ≤ 1 on ≥ 95 % of pilot cycles. This also settles QA's open question whether the daemon archive WAV is pre- or post-RMS-normalisation. Also assert each WAV has exactly 180000 samples (per-file assertion, in code). Outcome fields only; never rendered text (process-global hash table). Failure means the replay is not the live path and no timing is citable.
- **R1 — hard budget (validity of the guard).** Over H ∪ M, flag ON: max per-cycle elapsed ≤ 13 000 ms. Any cycle over is a FAIL and is reported individually with its stamp and pass-0 count.
- **R2 — headroom (Captain-adjustable margin).** Max ≤ 10 000 ms AND p95 over H ≤ 6 000 ms. Fails while R1 passes ⇒ **PARTIAL**, reported as such; whether to proceed is the Captain's call, not a QA/Architect pass.
- **R3 — stability.** Zero access violations, zero contained exceptions, zero process exits across all ON decodes. Any non-zero ⇒ FAIL. (Contained exceptions are logged by the build as a warning per your review finding R2; count them from the daemon log, and quote the exact grep.)
- **R4 — deadline-abandon rate (usefulness, not safety).** Report count and fraction of ON cycles where the residual pass was abandoned on deadline, per stratum and per run. No pass/fail: a guard that fires works as designed, but if the rate in H exceeds 5 % the Captain should read the feature as "mostly inert on busy bands". Threshold recorded here so it is not chosen afterwards.
- **R5 — flag-OFF cost.** OFF vs archived per-cycle timing: report only; OFF must not be measurably slower than the archive's own decode time (report ratio of medians; no bar, the OFF path is ruling 2's concern).
- **R6 — stress row (labelled SYNTHETIC, runtime only).** Take 20 H cycles (lowest 20 stamps by sort, fixed), sum each with the next H cycle's audio (renormalise, no clipping — assert peak), decode ON. Bar: no AV, no contained exception, and elapsed ≤ 13 000 ms + (max single native call observed in R1, from the log or 0 if unmeasured — state which). Purpose: the corpus tops out at 32 pass-0 signals; this probes beyond it without claiming anything about real-band realism.
- **R7 — descriptive only:** ON − OFF pass-0-plus-residual decode count per cycle, distribution and per-run mean. **No claim, no bar.** The build has no residual-pass attribution yet (§4.2); the count difference is not a subtraction gain.

## 2a. Amendment 1 (2026-09-29, QA's HK-021(k) review; accepted, drafting defect mine)

- **R0 as written fired on both branches** (replay not the live path, OR the lineage decodes differently): the archives came from the `decoding_improvement` lineage (shim `20260054`, e.g. `20260922_2056` = DI@`84cac119`, DLL `38a21f84…`), the replay build is `0d6b1937` (main lineage, `20260055`). **Replacement:** R0 runs on the Pilot through **the DLL that PRODUCED each archive** (QA verifies by SHA-256 which build each of the three runs used, incl. `20260923_1730`, and records the actual/pinned pair per run), flag-OFF path/equivalent, predicate unchanged (|Δ| ≤ 1 on ≥ 95 %). Pilot cycles are drawn per run so every run's producing DLL is exercised. If a producing DLL cannot be recovered for a run, that run is EXCLUDED from R1–R7 (stated, not silently dropped). R1–R7 timing rows stay on `0d6b1937` / the post-§4.2 build.
- **R6 term fixed before the run:** the allowance is a constant **3 000 ms** (bar = 13 000 + 3 000 = 16 000 ms), not "the max single native call". The build logs no per-call time, so no measured value exists; a constant cannot be chosen after seeing results.
- **R1 is read jointly with R4.** A max sitting at ~13 s with a high abandon rate means the guard clamped it; report the two together, and do not call R1 "fast" on its own.
- Harness is QA-owned C# through the public `Ft8Decoder` (`SubtractionPass` is internal); no `src/` change. State the harness commit SHA in the report.

## 3. Blind spot (HK-026), stated up front

The response of the instrument is flat above 32 signals on real data: no real cycle in the corpus exceeds 32 pass-0 decodes (max 29/32/28), while the design's FFT-only benchmark predicted ~26 s at 24 signals before parallelism. R6 is the only probe above 32 and it is synthetic. A PASS therefore means "no problem found up to 32 real signals", never "safe on any band".

## 4. Hygiene

- 🔒 NFR-021 / HK-037: read only stamps and integers; write timings and counts to gitignored `_out/`, assert the output paths are untracked before decoding; no message text leaves the function that reads `ALL.TXT`. Promote only aggregates.
- HK-016/HK-019: gather artefacts into dated `./artefacts/`, detached run + log-tail (HK-023), orphan check after. Approx run time: ≤ ~ (611+300) × 2 × ≤13 s ≈ ≤ 6.5 h worst case; typically far less.
- Read the report's own Section 4-equivalent (aggregate table per run) before summarising (HK-036 spirit).
- QA may REFUSE any row on HK-021(k) grounds; the Architect is not asked to pre-agree. If R0 fails, report that and stop; do not adjust the tolerance afterwards.
