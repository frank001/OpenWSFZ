# #194 captured-audio scan: INTERIM validation report (calibration checkpoint)

- **To:** Architect, cc QA, Captain  **From:** Engineer (owner of #194 part A)  **Date:** 2026-10-02 (HK-017: derive the time mechanically when filing)
- **Branch:** `eng/194-scan` (local, off `origin/main`; not pushed, only QA pushes). QA tooling under `qa/` only; `git diff --stat -- src/ native/` is empty.
- **Status: STOPPED at the section-5 calibration checkpoint.** The spec says that when more than 1 % of slots are flagged on a metric, the Architect rules on the histogram *before the freeze*. That happened (11 of 20 side-metrics). So `thresholds.json` is **NOT frozen**; what is committed is `thresholds_draft.json` (the mechanical rule's output, unmodified). **The 2026-09-29 pair has NOT been read** (no WAV of either 09-29 run was opened; only their `truth.csv` slot lists and reference renders were produced, which need no audio). PC1, V1 to V3 on the 09-29 runs, section 7 and section 11's fix are therefore not done.

## 0. Guard paragraph (spec section 1, verbatim)

> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows **in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about how either decoder handled it.

Also (section 9): S1 `g_db`/`resid_db` below are descriptive only and say nothing about the dropped +1.45 dB bias follow-up.

## 1. Section 2 facts (FILE:LINE)

1. **Slot to WAV mapping.** Both apps name the WAV `yymmdd_hhmmss` of the slot start, and that equals `truth.csv` `cycle_utc` exactly: 407 of 407 truth slots matched a name on both apps for 09-23, with zero off-by-one (a ±1 s shift matches 0, a ±15 s shift matches 406/407, i.e. only the grid neighbour). Daemon: `CycleArchiveService.cs:316` (`item.CycleStart.ToString("yyMMdd_HHmmss")`, collision suffix `_n` at `:317`, none present). WSJT-X `save/` uses the same label. Verified, not assumed.
2. **One slot = one render key.** `run_scenario.py:1232` `seed = compute_seed(scenario_id, part_index, trial_index)`; truth.csv has several rows per slot for S4/S7/S8 (755 rows, 407 slots) with identical `cycle_utc` and seed. Slot key = (scenario, part, trial, seed); the renderer recomputes every seed with the harness's own `compute_seed` and aborts on a mismatch (0 mismatches).
3. **What the daemon archive holds.** `DecodePump.cs:154` passes the framer's `pcmWindow` to `EnqueueArchive` **before** decoding; `CycleArchiveService.cs:314` encodes it with `CycleWavWriter.Encode`, which does only `MathF.Round(pcm[i]*32767f)` and clamps (`CycleWavWriter.cs`, Encode). **No gain, AGC or normalisation anywhere before the archive.** The only normalisation, `Ft8Decoder.cs:421` (`NormalisePcm`, target RMS 0.20), runs on a copy afterwards. The upstream path is WASAPI → NAudio `WdlResamplingSampleProvider` to 12 kHz (`WasapiAudioSource.cs:129`), left channel only (`:364`). So OpenWSFZ-side level metrics measure the chain plus WDL resampling, not an application gain step. (The 09-29 V0 "69/72 normalised" refers to the decoder's own copy, not to the archive.) The harness batches up to 20 slots into one continuous `sd.play` (`run_scenario.py:1196`), so slot boundaries are not separate playbacks.
4. **Unpaired slots, 09-23:** 407 truth slots, 407 paired on both apps; the 30/31 WAV-only files are `UNPLANNED` (gap slots between batches). The "437 vs 438" is one extra WAV on the WSJT-X side, among the `UNPLANNED`. `MISSING` = 0, `UNPAIRED` = 0 for truth slots (see `files.csv`).

## 2. R0a to R0c

- **R0a PASS.** Every slot rendered in two separate processes: SHA-256 of the float32 array identical, 407/407 for 09-23 and for each 09-29 run (renders only; no audio read).
- **R0b: 0 of 407** slots differ between the run-commit render and the current harness, for all three runs. Consistent with `git diff --stat 5f17b43 HEAD -- qa/rr-study/{harness,synth,scenarios}` and `5f17b43 62e8e74 -- harness` both being empty. **Harness commit:** `5f17b43a` for 09-23 (committed 09:25Z, before the 10:33Z run start). The 09-29 report records the *daemon* build `62e8e74`, not a harness commit; a worktree of `62e8e74` was used and its harness tree is byte-identical to `5f17b43`'s.
- **Reference construction.** The renderer imports `run_scenario._render_*` / `_finalize_playback_samples` and `run_study._SCENARIO_REGISTRY` from the run-commit worktree; the only code that is ours is the `if/elif` scenario dispatch (mirroring `run_scenario.py:1245-1300`). Six S3 slots (parts 8 and 9) render 721 920 / 736 320 samples; the reference is truncated to 15 s (the overflow belongs to the next slot) and the sidecar carries `oversize` / `after_oversize`.
- **R0c AS WRITTEN FAILS, and cannot be passed by this reference. My reading is that this is a defect of the test, not of the mapping; the Architect rules.** The spec's rule compares each slot's own `rho_peak` with the *run's largest* neighbour-slot `rho_peak`. Facts (`r0c.json`):
  - 175 of 407 slots (43 %) have a reference that is itself ≥ 0.5 correlated with its neighbour's reference: S5 part 2/3 (a steady carrier, birdies: identical every trial), most of S7, S4, S1 (13/30) and S8. A wrong seed would give nearly the same reference there, so the neighbour control **cannot discriminate** for them (HK-026: the instrument's response is flat where the question sits). The run-wide largest neighbour `rho_peak` is 0.55 (owsfz) / 0.51 (wsjt-x); on the noise-dominated slots it is ≈ 0.01.
  - Literal rule: owsfz 12/407 (2.9 %), wsjt-x 42/407 (10.3 %) fail the 0.2 margin, above the 2 % stop line. They are noise slots whose own `rho` is 0.46 to 0.9 against neighbours at 0.01: the mapping is right, the run-wide max is the wrong yardstick.
  - **Proposed Amendment A1 (used here, clearly provisional):** apply the same 0.2 margin *per slot against that slot's own neighbours*, and only on slots whose reference differs from its neighbours' (`ref_vs_neighbour_ref_rho` < 0.5). Result: 232 discriminating slots per side, **0 REF-MISMATCH on both sides**. For the 175 non-discriminating slots the mapping is confirmed by the file-name/`cycle_utc` identity and, for S5 p0/p1 and S1b, by the neighbour control; for the tone-dominated ones **nothing in the audio can verify the seed**, and the report says so rather than counting them as verified.
- Why `rho_peak` of a *correct* reference is only 0.8 to 0.95 on noise slots: the apps' own 48 → 12 kHz decimation filters differ from the harness's `resample_poly` near the band edge, so the fit residual is chain behaviour (median `resid_db` −9.7 owsfz / −12.5 wsjt-x). **CA2 (WSJT-X median residual in [−45, −25] dB) is a MISS**: −12.45 over all slots (−10 to −12 on noise-dominated groups, −24 to −29 on signal-dominated ones).

## 3. Calibration on 2026-09-23 (thresholds_draft.json; the rule applied unmodified)

Median + 6 × 1.4826 × MAD with the spec's floors. 407 paired slots, 0 REF-MISMATCH. Tool: `scan_core.py`, `scan_run.py`, `scan_calibrate.py`; wall time of the measure stage 136 to 150 s for one run on one core (**V3: 09-23 ≈ 2.5 min measuring, plus ≈ 0.5 min per reference render**, so automatic post-run use is feasible).

| side | metric | median | MAD | **T** | floor applied | flagged on calibration |
|---|---|---:|---:|---:|:--:|---:|
| owsfz | g_db (dev) | −1.87 | 1.02 | 9.06 | no | 0 |
| owsfz | step_db_max | 0.50 | 0.38 | 3.87 | no | 18 (4.4 %) |
| owsfz | drift_ppm (abs) | 0.03 | 0.02 | 20.0 | yes | 13 (3.8 %) |
| owsfz | zero_run_ms | 0.08 | 0 | 5.0 | yes | 20 (4.9 %) |
| owsfz | tile_excess_db | 15.7 | 7.3 | 80.4 | no | 60 (14.7 %) |
| owsfz | click_max | 4.85 | 0.25 | 7.04 | n/a | 20 (4.9 %) |
| owsfz | clip_n | 0 | 0 | 1 | yes | 0 |
| wsjt-x | g_db (dev) | −0.63 | 0.49 | 4.36 | no | 3 (0.7 %) |
| wsjt-x | step_db_max | 0.08 | 0.05 | 0.50 | yes | 37 (9.1 %) |
| wsjt-x | drift_ppm (abs) | 0.00 | 0.00 | 20.0 | yes | 12 (3.5 %) |
| wsjt-x | zero_run_ms | 0.08 | 0 | 5.0 | yes | 10 (2.5 %) |
| wsjt-x | tile_excess_db | 10.5 | 5.6 | 60.0 | no | 36 (8.8 %) |
| wsjt-x | click_max | 10.6 | 5.6 | 60.0 | n/a | 63 (15.5 %) |
| cross | dg_db (dev) | −1.10 | 0.60 | 5.32 | no | 0 |
| cross | dtau_ms (dev) | −3.83 | 3.42 | 30.4 | no | 1 |

(`tau_ms`, `resid_db`, `tail_zero_ms` rows are in `thresholds_draft.json`.) **Metrics over 1 %: 11** (list in the JSON). Per the spec this is "not one population", and `population_breakdown.txt` shows why:

- **Content, not chain, makes the populations.** Per scenario group, medians differ by an order of magnitude: `tile_excess_db` 2 (S5 noise) vs 15 to 19 (signal slots) vs 83 to 176 (S5 p2/p3, a steady carrier whose structured residual breaks "max tile over median tile"); `click_max` 4.9 (owsfz) vs 8 to 127 (wsjt-x, where S7/S8 give 45 to 127); `g_db` −2.9 (noise) vs −0.1 (tone). One threshold per side for all scenarios is too coarse: it flags 30/30 S5 p2/p3 slots on `tile_excess_db` and 27 S7 slots on wsjt-x `click_max` as "anomalies" that are just content.
- **Real events exist and are shared.** `drift_ppm` flags 13 / 12 slots and **12 are the same slots on both apps**, all with a mid-slot **lag step of 108 to 144 samples (9 to 12 ms)** identical on both recordings to within 0.1 sample, e.g. `S1b_p001_t000` (10:42:30Z, 144.4/144.5), `S3_p001_t000` (10:53:45Z), `S5_p001_t022` (11:27:45Z, 115.6/115.7), `S7_p015_t001` (12:13:15Z). `step_db_max` flags 18/18 and `zero_run_ms` 10 of 20 as the same slots. By the section-1 rule that is **BOTH ⇒ shared playback path** (≈ 3 % of slots), consistent with a ≈ 10 ms (480 frames at 48 kHz) buffer slip somewhere in render → PortAudio → Voicemeeter, not in either recorder. I did not look for a cause; this is a measurement, and no claim is made about any decoder.
- **A second shared-path signature:** S5 part 0 slots `t011` to `t024` (11:09 to 11:12Z) show `rho` 0.82 / 0.69 against 0.93 / 0.88 for the slots around them, on both apps at once, preceded by a `step_db_max` ≈ 49 to 56 dB slot (`t010`, 11:08:45Z). Descriptive; flagged for the Architect, not explained.

## 4. Deviations the Architect must rule on (all decided before reading 09-29, from the calibration run only)

| # | Deviation | Why |
|---|---|---|
| A1 | R0c margin per slot, on discriminating slots only (§2) | the literal rule cannot pass on 43 % of slots by construction |
| A2 | `tail_zero_ms` / `head_zero_ms` added; a zero run touching either end of the file is **excluded** from `zero_run_ms` and from the support | WSJT-X writes 14.4 s of audio then exactly 600.0 ms of zeros on **all** 407 slots (median 600.0, MAD 0): structural, not a dropout. Without this, every WSJT-X slot would carry a 61 ms "zero run" that varies with `tau`. `tail_zero_ms` is flagged above its calibration median |
| A3 | `lag_ambiguous`: if the second distinct correlation peak is ≥ 0.9 × the best, `tau_ms`, `dtau_ms` and `drift_ppm` are NaN | 68 slots (steady-carrier S5 p2/p3 and some others): lag is not identifiable from a periodic reference (found: best lag jumped by 1 933 samples between the two apps on the same slot) |
| A4 | `click_max` = max\|e_hf\| / (1.4826 × MAD(e_hf)), `e_hf` = residual − 31-sample median filter, over the support; `tile_excess_db` over whole seconds fully inside the support; `|drift_ppm|` and the floors treated as in `scan_core.RULES` | spec wording ambiguous; stated in `scan_core.py`'s header |
| A5 (**proposal, not applied**) | calibrate per scenario group (e.g. S5-noise, S5-tone, S1/S2/S3, S4, S7/S8) and per side, instead of one population per side | §3 above; the single-population rule makes 11 side-metrics fail the 1 % test for content reasons |
| A6 (note) | `clip_n` floor 1 is applied with "exceeds", i.e. a slot needs ≥ 2 clipped samples to flag | literal reading of section 5 |

## 5. Not done, and what I need

Not done: freeze; PC1; V1 to V3 on 09-29 (V1/V2 on 09-23 can be shown from `files.csv`: 407 + 407 scanned, 30 + 31 `UNPLANNED`, counts add to 437 / 438 WAVs); section 7 event log; section 11 fix. Section 11's cause is **confirmed for the current tree** (CA5 HIT): `tools/gather_live_run_artefacts.py:288-298` `git_build_info()` runs `git rev-parse HEAD` in `REPO_ROOT`, the *QA tooling* worktree, giving `345e75ff`; the daemon's own record is `84cac119` (`arm_config.json`, report lines 12 to 30) and the harness run was `5f17b43`.

**Rulings requested:** (1) A1 to A4 accepted or amended; (2) A5: freeze per-scenario-group thresholds, or one population per side with a stated "content flags are expected" note; (3) whether the 09-29 pair may now be read once the freeze is made. I will then freeze, commit `thresholds.json` with its SHA-256, and run PC1, V1 to V3 on the pair.

Reproduce: `render_reference.py` (R0a/R0b), `scan_run.py measure`, `scan_calibrate.py`; scratch `D:\Projects\claude\_qa-scratch\194-scan\` (to be deleted by me when the job closes). No decoder, daemon, station, `ALL.TXT` or message text was touched; no `--filter`/DLL pin applies (no decoder runs).
