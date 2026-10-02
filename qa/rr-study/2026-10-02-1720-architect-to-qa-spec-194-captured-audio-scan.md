# SPEC — #194 part A: CAPTURED-AUDIO SCAN for synthetic R&R runs (read-only; no deletion)

- **To:** QA (owner; the Engineer may build it if QA assigns it, one owner recorded on the board) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~17:20Z (HK-017)
- **Branch:** `arch/194-rr-improvements`. Docs only: `git diff --stat -- src/ native/` empty. **QA tooling under `qa/` only. No daemon change.**
- **Source:** GitHub #194 (Captain's proposal, 2026-09-29) and the Architect review comment on it (four points; all four are written into this spec).
- **Status:** PRE-REGISTERED. Thresholds are fixed by the mechanical rule in §5 **before** the scan reads the validation runs. Changes after that only by a dated amendment that says why.
- **Needs:** no station time, no playback, no build. CPU only. 🔴 Not while a QA timing run or a live/overnight run is on (the PC's CPU is shared).

## 0. What this spec does and does not do

- ✅ **Builds the SCAN only:** a read-only tool that compares each captured slot with the audio the harness rendered for it, writes a per-slot sidecar and a report, and flags anomalies by numeric rule.
- 🛑 **Does NOT build the CLEAN tool, and nothing deletes any WAV.** Retention is cheap (≈ 300 MB for 2026-09-23) and deletion cannot be undone. Whether a cleanup script is worth building is **the Captain's decision after the scan's validation report** (§9). The constraints any later cleanup must meet are recorded in §10, so that they are not lost.
- 🛑 Synthetic R&R runs only. Live and endurance corpora have no rendered reference, and the endurance `spectrum_scan.py` already covers them.

## 1. What a finding can and cannot mean (put this in every scan report, verbatim)

> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows **in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about how either decoder handled it.

## 2. Inputs

Per run: `qa/rr-study/results/<run>/truth.csv`, the run's report or run log (for the build and harness commit), and `<run>-captured-audio/{owsfz,wsjt-x}/wav/*.wav` (in-tree for 2026-09-23, under QA's `artefacts/rr_2026-09-29_subfeas_off_on/` for the 09-29 pair). QA states with FILE:LINE:

1. **Slot ↔ WAV mapping:** how each WAV filename (`yymmdd_hhmmss`) maps to `truth.csv`'s `cycle_utc`, for both apps (WSJT-X's `save/` naming may mark the slot start differently from the daemon's archive; check, don't assume).
2. **Which rows are one slot:** multi-signal parts (S4, S7, S8, E4) have several truth rows per cycle. The slot's render key is (scenario, part, trial, seed).
3. **What the daemon's archive WAV holds:** pre-normalisation, as V0 of the 2026-09-29 flag-OFF control found (69/72 normalised vs 53/72 raw). State where in `src/` the archive is written and whether **any** gain, AGC or normalisation is applied before it. If one is, the OpenWSFZ-side level metrics measure that step, not the chain, and the report must say so per metric.
4. **Unpaired slots:** a `truth.csv` slot with a WAV on one side only is `UNPAIRED` (2026-09-23 has 437 vs 438). A WAV with no truth slot is `UNPLANNED`. A truth slot with no WAV on either side is `MISSING`. These three are listed and **never** counted as anomalies or as normal.

## 3. The reference: re-render, and prove it before using it

- The reference for a slot is the harness's own render of that slot, finished exactly as playback finished it: the main loop's normalise and fade (`run_scenario.py` ~L1296–1316, `_finalize_playback_samples` L718), then 48 → 12 kHz with the same `resample_poly(up=1, down=4)` as `_dump_slot_wav` (L752), **kept as float** (no int16 rounding).
- 🔴 **Import the harness's functions; do not re-implement any render step.** Render from a detached worktree of **the harness commit that produced the run** (under `D:\Projects\claude\_qa-scratch\194-scan\`), not from today's tree.
- **R0a determinism:** every slot rendered twice in separate processes is sample-identical (SHA-256 of the float32 array). FAIL ⇒ stop.
- **R0b drift:** re-render every slot with the **current** harness as well. Count the slots that differ from the run-commit render. This is reported only (it tells us whether the renderer has drifted since). The run-commit render is the reference.
- **R0c the reference is the right one:** per slot and side, the peak normalised cross-correlation `ρ_peak` between the captured WAV and its reference. The correct reference gives a value near 1. A wrong seed or slot mapping gives the value for unrelated noise. QA also computes `ρ_peak` against the reference of the **neighbouring** slot for every slot (a negative control). **R0c PASSES if** every paired slot's own `ρ_peak` exceeds the largest neighbour-slot `ρ_peak` in the run by at least 0.2. Slots that fail are listed as `REF-MISMATCH` and are not scanned. If more than 2 % of paired slots fail, stop: the mapping is wrong.

No original render of a past run was stored, so "byte for byte against the original" (review point) cannot be checked directly. R0a and R0b do that check against the code, and R0c does it against the audio.

## 4. Per-slot measurements (the sidecar; one CSV per side per run)

Fit per slot and side: integer-sample lag `τ` by cross-correlation within ±3.5 s (the S3b early arm is 3.0 s), refined parabolically. Then gain `g` by least squares, residual `e = x − g·ref(τ)`, all over the reference's support (exclude the fade tail and samples where the reference is exactly 0).

| Column | Definition | Catches |
|---|---|---|
| `wav_sha256`, `fs`, `bits`, `channels`, `n_samples` | WAV header and hash | format change; integrity |
| `g_db` | 20·log10 `g` | volume/mixer change **between** slots |
| `tau_ms` | fitted lag | timing jump between slots |
| `rho_peak` | from R0c | wrong audio |
| `resid_db` | 10·log10(Σe² / Σ(g·ref)²) over the slot | anything not in the reference |
| `step_db_max` | max over 0.5 s windows of \|`g_w` − `g`\| (dB), with `g_w` refitted per window at fixed `τ` | level step **within** a slot |
| `drift_ppm` | (`τ` fitted on the last 4 s − `τ` on the first 4 s) / elapsed, in ppm | sample-rate mismatch, spectrum stretch |
| `zero_run_ms` | longest run of exactly-zero samples inside the reference's support | underrun, USB dropout |
| `click_max` | max over samples of \|e\| / RMS(e), using the slot's median-filtered residual | clicks, broken waveform |
| `tile_excess_db` | residual power on 1 s × 100 Hz tiles (200–3 000 Hz). Max tile over the slot's median tile, in dB | notification sounds, beeps |
| `clip_n` | samples at int16 full scale | clipping |

Cross-side, per paired slot: `dg_db = g_db(owsfz) − g_db(wsjt-x)` and `dtau_ms` likewise. These catch the two apps hearing different things.

🛑 **NFR-021:** audio only. The scan reads no `ALL.TXT` and no message text. `truth.csv` is read for keys and seeds only (its texts are Q-prefix synthetic anyway).

## 5. Anomaly rule (mechanical, HK-021): calibrate on a run, freeze, then apply

The chain's normal behaviour has never been measured. This programme has set a bar below the real "nothing" level before (SUB-FEAS Stage 1 and `X_empty`), so the thresholds come from data by a rule fixed **now**:

- **Calibration run:** 2026-09-23 (`5f17b43`, the first full S1–S8 battery). Per side and metric `m`, over all scanned slots: `T_m = median_m + 6 × 1.4826 × MAD_m` (one-sided upward). For `g_db`, `tau_ms`, `dg_db` and `dtau_ms`, the rule is two-sided and applies to the deviation from the run's median.
- **Floors (fixed now; a threshold is never below them):** `step_db_max` 0.5 dB · `|g_db − median|` 0.5 dB · `|drift_ppm|` 20 · `zero_run_ms` 5 ms · `tile_excess_db` 10 dB · `clip_n` 1 · `|dg_db − median|` 0.5 dB · `|tau_ms − median|` and `|dtau_ms − median|` 2 ms.
- QA commits `thresholds.json` (each `T_m`, its median, its MAD and the floor applied) with its SHA-256 **before** the scan reads either 09-29 run. The calibration run's own flagged slots are listed. Six robust standard deviations should flag almost nothing there; if more than 1 % of slots are flagged on one metric, that metric's distribution is not one population. The report shows its histogram and the Architect rules on it before the freeze.
- A slot is **FLAGGED** on metric `m` if it exceeds `T_m`. Classification per flagged slot: **BOTH** (both sides flagged on the same metric family within ±0.5 s) ⇒ shared playback path. **OWSFZ-ONLY** or **WSJTX-ONLY** ⇒ that app's recording path. **CROSS** (only `dg_db`/`dtau_ms` flagged) ⇒ the apps heard different things.

## 6. Positive control (HK-026): the scan must prove it can see before "nothing found" means anything

On **copies** of 10 slots per side drawn (seed 20261002) from slots the calibration run did not flag:

| Injection | Expected metric |
|---|---|
| level step of −Δ at 7.0 s | `step_db_max` |
| whole-slot gain change of Δ | `g_db` |
| zero dropout of length Δ at 5.0 s | `zero_run_ms` |
| 0.5 s 1 kHz tone burst at Δ dB re the slot's RMS, at 9.0 s | `tile_excess_db` |
| resample by (1 + Δ ppm) | `drift_ppm` |
| insert Δ ms of samples at 6.0 s (a clock hiccup) | `drift_ppm` or `step_db_max` |

Each injection at **0.5×, 1× and 2× its frozen threshold** (Δ in that metric's units). **PC1 PASS iff** every injection at 2× is flagged on its expected metric in 10/10 copies, and the unmodified copies are flagged 0/10. The 0.5× and 1× rows are reported: a flat response across them means the scan cannot see near its own bar, and the report says so.

## 7. Windows event log cross-reference (descriptive)

For each run window, query the System and Application logs for events from audio and device providers (QA lists them in code: e.g. `Microsoft-Windows-Kernel-PnP`, `Audiosrv`, `AudioEndpointBuilder`, USB and driver-reset sources). List each event within ±30 s of a flagged slot. Also report the log's oldest retained entry, because a run older than the retention window cannot be checked, and that must be stated, not read as "no events".

## 8. Validation (read-only; HK-018: existing data first)

| Row | Predicate |
|---|---|
| R0a, R0b, R0c | §3 |
| PC1 | §6 |
| V1 coverage | every WAV of 2026-09-23 and both 2026-09-29 runs (`62e8e74`-OFF and -ON) is in a sidecar row or in one of `UNPAIRED`/`UNPLANNED`/`MISSING`/`REF-MISMATCH`. The counts add up to the file count |
| V2 sidecar integrity | `wav_sha256` in the sidecar equals a fresh hash of each file |
| V3 runtime | wall time for the 09-23 run is recorded (descriptive; it decides whether the scan can run automatically after each run) |

Outputs per run: `scan_report.md`, `sidecar_owsfz.csv`, `sidecar_wsjtx.csv`, `thresholds.json` (calibration run only). They go in the run's results directory, committed (counts and hashes only; NFR-021-scanned). The sidecars are what survives if a WAV is ever deleted.

**Then, and only then:** wire the scan into the standard R&R post-run step (after gather, while the event log is fresh). That is a second, small change, after the Architect has ruled on the validation report.

## 9. Guards the report must carry

- 🛑 **The S1 +1.45 dB bias.** `g_db` and `resid_db` on S1 slots will produce numbers bearing on it. They are **descriptive only**: the follow-up was dropped by the Captain on 2026-09-29, and these numbers do not reopen it. Never cite them as a build or chain effect. If they look decisive, that goes to the Captain as a question, not into a conclusion.
- The §1 paragraph, verbatim.
- One-sided findings are recording-path findings, never decoder findings.

## 10. For the later CLEAN decision (recorded here, not built)

If the Captain orders a cleanup tool after §8, it must: run as a dry run by default, deleting only with `--apply`; touch only synthetic R&R `*-captured-audio` directories; **delete a run's audio only if the run carries an explicit `comparison-closed` marker** (written by the Captain's instruction). A missing marker means **keep**: the #194 proposal had a "comparison pending" marker the other way round, which fails into deletion when someone forgets it. It must refuse if the run's scan report or sidecars are missing, keep every flagged slot plus a seeded random sample, and write a manifest with SHA-256s.

## 11. Side item (small, QA tooling): `contents.md` misrecords R&R runs

The 2026-09-23 captured-audio `contents.md` names the build as `qa/live-gap-map` at `345e75ff` with uncommitted changes, not `5f17b43`. It also carries the live-run template unchanged: it says the folder holds real third-party callsigns (the run is synthetic), and its headline section is an unfilled TODO. Likely cause: `tools/gather_live_run_artefacts.py` reads the build from the QA worktree's `HEAD` instead of the daemon's own record. QA confirms with FILE:LINE. The fix is to take the build from the run's own record (report or `arm_config`), and to use a synthetic-run template for R&R gathers. QA tooling, not `src/`.

## 12. Predictions (blind; scored at ruling time)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| CA1 | R0c passes on all three runs with < 0.5 % `REF-MISMATCH` | 0.70 | H |
| CA2 | Calibration `resid_db` median on the WSJT-X side lies in [−45, −25] dB (Voicemeeter is a digital path, so the residual is resampling and quantisation, not noise) | 0.45 | H |
| CA3 | At least one slot across the three runs is FLAGGED and classified BOTH | 0.35 | H |
| CA4 | PC1 passes first time | 0.65 | H |
| CA5 | §11's cause is the worktree-`HEAD` read | 0.70 | H-mech |
