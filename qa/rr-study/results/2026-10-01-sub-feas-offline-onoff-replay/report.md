# SUB-FEAS offline flag-OFF/ON replay of the 2026-09-30 on-air night: report

- **Author:** QA. **Run:** 2026-10-01 19:53Z to 2026-10-02 05:19Z (UTC). **Report written:** 2026-10-02.
- **Spec (pre-registered):** `qa/rr-study/2026-10-01-1935-architect-to-qa-spec-sub-feas-offline-onoff-replay.md` plus **Amendment 1** (V6, spec §9a, `arch/subtraction-feasibility` `d292f913`, committed before any decode of this night).
- **Harness:** branch `qa/onoff-replay`, harness commit `88ca7059` (decode and rows), watchdog `87636bca`. 44 instrument tests (41 for the rows, 3 for the watchdog), each row shown on both branches.
- **Raw numeric rows:** `artefacts/rr_2026-10-01_onoff_replay/` (gitignored); the computed rows are `rows.json` in this directory.

## 1. Scope, in the words the spec requires

*A second night on the same band, station and capture chain as the Stage 2 corpus. It replicates night to night; it does not replicate across bands. Replay is not the live path.*

## 2. Result

**Verdict: D1 REPLICATED.** NET **+11.73 pp**, 95 % percentile CI **[11.41, 12.03]**. The registered bar is `CI_lo >= 1.0` (the Stage 2 replication bar, set 2026-09-28, not re-tuned); `CI_lo` is 11.41. Every validity row passed, so a verdict is issued.

| Quantity | Value |
|---|---|
| Included cycles scored | 4 298 of 4 298 (4 300 WAVs, the 2 window-edge cycles excluded, 0 R0 failures) |
| ΣW, WSJT-X decodes in the live `ALL.TXT` over those cycles | 129 608 |
| ΣM_off, matched decodes, flag OFF | 78 128 |
| ΣM_on, matched decodes, flag ON (union of both batches, one-to-one) | 93 326 |
| NET = 100·Σ(M_on − M_off) / ΣW | **+11.726 pp** |
| CI, block bootstrap | block **40** (registered), 108 blocks, B = 10 000, seed 20261001, ratio estimator, last partial block kept; numpy 2.4.6 |

**Reported, not used for the verdict:** CI at block 20 = [11.47, 11.98]; at block 160 = [11.25, 12.17]. Autocorrelation of the per-cycle difference d_i = M_on,i − M_off,i: lag 1 = 0.20, lag 4 = 0.46, lag 40 = 0.34. Cycles are autocorrelated (band activity), which is why the interval is a block bootstrap; the three block lengths agree to within about 0.2 pp at each end (lower bounds 11.25, 11.41, 11.47; upper bounds 11.98, 12.03, 12.17).

## 3. What was run (so the result can be reproduced and checked)

| Item | Value |
|---|---|
| Build | `247ac391` (two-stage publish), shim 20260056 |
| `libft8.dll` SHA-256 | `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` (actual == pinned at the start and end of every arm) |
| Decode call | managed `DecodeTwoStageAsync`, one call per cycle; OFF arm = harness `--mode two0` (flag OFF), ON arm = `--mode two1` (flag ON, 8 workers); the two arms differ only in the flag |
| Decoder config (both arms) | `nhard` 40, `kMinScorePass2` 10, `osdCorrThreshold` 0.10, `subtractionMaxThreads` 8, read back from the decoder object at the start and end of each run |
| Audio | `artefacts/20260930_1930_endurance_run/cycle-audio/` (4 300 WAVs, 12 kHz mono 16-bit, 180 000 samples, all pass R0) |
| Cycle list | `selection.json`, SHA-256 over LF-normalised bytes `55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf`, frozen and committed before any decode of this night |
| Reference | WSJT-X `ALL.TXT` of the same night, read only inside the matching function (HK-037, strict route); W_i = its `Rx FT8` rows of the cycle (4 296 cycles have at least one row, the rest are W = 0 and stay in) |
| "Matched" | Test B's rule exactly as implemented: same message text, same cycle, |Δf| ≤ 10 Hz, one-to-one nearest-first, in-process. **Not** the ANOVA's `match_pairs`. |
| Post-processing parity | `DecodeTwoStageAsync`'s output already has the plausibility filter and the per-cycle text de-duplication applied to **both** batches (`src/OpenWSFZ.Ft8/Ft8Decoder.cs`: dedup set `seen` created once per cycle at :510, `seen.Add` at :528, `IsPlausibleMessage` at :534; batch 1 = `MapNative(native)` :598, batch 2 = `MapNative(newFromResidual)` :701, same set). The harness therefore applied **no** extra filter or dedup; both arms were treated identically. |
| Arms, in order | OFF (20:20:48Z to 20:58:48Z, 38 min), ON (20:58:48Z to 04:56:53Z, 7 h 58 min), ON-repeat over the first 160 included cycles (04:56:53Z to 05:18:53Z). Each a fresh detached process; all exited 0. |
| Commands | `python qa\rr-study\sub-feas\onoff_replay_run.py` (OFF, ON, ON-repeat) then `python qa\rr-study\sub-feas\onoff_replay_rows.py`, both with `OPENWSFZ_ARTEFACTS` pointing at the QA worktree's artefacts. This is a replay, not a test run: no `--filter` exists to quote. |
| Machine | WSJT-X and `jt9` closed; Developer and Engineer sessions closed; the sampler recorded **0** competing processes in the whole run; orphan check empty |

## 4. Validity rows (any FAIL would have withheld the verdict; none did)

| Row | Predicate (spec §6, as code) | Result |
|---|---|---|
| V1 | DLL actual == pinned, start and end, all three runs | **PASS** (6 of 6 records) |
| V2 | flags as in §2 read back in every run; `selection.json` SHA identical | **PASS** (OFF reads `subtractionEnabled=False`, ON and ON-repeat `True`, threads 8, nhard 40, at start and end) |
| V3 | 0 access violations, 0 contained exceptions, 0 non-zero exits, every run | **PASS** |
| V4 | per included cycle, ON batch-1 numeric multiset (freqHz, dt, snr) == OFF multiset | **PASS 4 298 / 4 298** |
| V5 | ON-arm residual passes abandoned ≤ 5 % of included cycles | **PASS: 0 of 4 298 abandoned** (0.0 %) |
| V6 (Amendment 1) | over the first 160 cycles, a mismatching ON vs ON-repeat union is explained iff abandoned in exactly one run; PASS iff unexplained = 0 and explained ≤ 8 | **PASS: 160 of 160 identical** (0 explained, 0 unexplained) |

Instrument-consistency checks (not spec rows, any failure would also have withheld the verdict): all cycles present in both arms, W identical in both arms, and M_on = M_on,b1 + M_on,b2 on every cycle: all **true**.

## 5. Descriptive rows (no bar)

- **NET by OpenWSFZ SNR band** (Test B's bands, same ΣW denominator): A (≥ 0 dB) +0.77 pp, B (−10..−1) +4.71 pp, C (−15..−11) +3.75 pp, D (≤ −16) +2.49 pp (these sum to the headline NET).
- **Matched by batch** (ON arm, from the single one-to-one pairing of the union): batch 1 = 78 033, batch 2 = 15 293. Batch 2 publishes on average **3.66** decodes per cycle (about 15 713 in all). ΣM_on,b1 is 95 below ΣM_off (−0.07 pp): the single pairing of the union and the callsign hash-table history can move a pairing by a few decodes. The NET uses only M_on and M_off.
- **Replay fidelity** (the analogue of Stage 2's 0.76 pp, counts only): the OFF arm decoded 79 702 messages over the 4 298 cycles; the live OpenWSFZ `ALL.TXT` holds 95 383 for the same cycles (mean OFF − live = −3.65 per cycle; equal on 188 cycles). **The live night ran with the flag ON**, so the live record includes the residual decodes: the gap, 15 681, is within 0.2 % of the ON arm's batch-2 total (about 15 713). It is what a flag-ON live record is expected to look like next to a flag-OFF replay, not a replay defect. This cancels in the NET.

## 6. False-positive watch (a mechanical flag, not a verdict; spec §6)

A band is FLAGGED iff `CI_lo(batch-2 not-corroborated rate) > CI_hi(batch-1 not-corroborated rate)` (Wilson 95 %).

| Band (OpenWSFZ SNR) | Batch 1 not-corroborated | Batch 2 not-corroborated | FLAG |
|---|---|---|---|
| A (≥ 0 dB) | 370 / 24 257 = 1.5 %, [1.38, 1.69] % | 7 / 1 022 = 0.7 %, [0.33, 1.41] % | no |
| B (−10..−1) | 563 / 30 587 = 1.8 %, [1.70, 2.00] % | 86 / 6 245 = 1.4 %, [1.12, 1.70] % | no |
| C (−15..−11) | 282 / 13 763 = 2.0 %, [1.83, 2.30] % | 133 / 5 017 = 2.7 %, [2.24, 3.13] % | no |
| **D (≤ −16 dB)** | 454 / 11 095 = 4.1 %, [3.74, 4.48] % | 194 / 3 429 = **5.7 %**, [4.93, 6.48] % | **YES** |

**Band D is flagged**: the two intervals do not overlap. Per the spec a flag goes to the Architect and the Captain and does not change D1 to D3. "Not corroborated" is an upper bound on false positives only, not a count of them: WSJT-X may simply not have decoded a real, weak signal. What the flag shows is that, in the weakest band, batch-2 decodes are somewhat less often confirmed than pass-0 decodes (about 5.7 % against 4.1 %); it does not show that they are false.

## 7. Events that must be on the record

1. **The first OFF attempt was killed by QA.** At 20:19:51Z (2 645 OFF rows done) QA's own test of the watchdog, run with its default orphan-process match `Replay81.dll`, killed the live harness (exit 1). The orchestrator restarted it, but that left a non-zero exit in the OFF arm, which row V3 ("0 non-zero exits") would have counted. QA therefore **discarded that arm and reran it from scratch** at 20:20:44Z; the discarded files are kept in `artefacts/rr_2026-10-01_onoff_replay/aborted_attempt_20261001T2020Z/`. **No pre-registered row, threshold or input was changed.** The cost was about 27 minutes of compute. The tests were corrected (a stub-only match; null stdin for every child process) and the log carries a correction of a local-time stamp that had been mislabelled UTC.
2. **Watchdog:** a detached watchdog (HK-013, HK-019, HK-023) was armed at 20:23:16Z. It made **0 relaunches** and exited by itself on DONE at 05:23:51Z. Its restart path was tested against stubs with a real process tree; it was not tested against the real orchestrator, which would have disturbed the pre-registered run.
3. **Competing processes:** 0 samples in the 30-minute sampler; orphan check empty. WSJT-X and `jt9` were closed for the whole run (they were resident on the live night; both arms replayed without them, so the NET is unaffected by their absence).
4. **Harness changes after the spec:** `--mode two0`, `--wav-dir`, a flag read-back line, and (for Amendment 1) a numeric per-cycle abandon file. All were committed before any decode of this night; a 4-cycle smoke test on the **2026-09-25** night (not this one) validated the modes and the parsing. A smoke test on the on-air night did not occur.

## 8. Limits (what this result does not show)

- **One night, one band, one station, one pass.** The result replicates night to night on the same band and chain; it says nothing about other bands.
- **Replay is not the live path.** The live `ALL.TXT` is post-plausibility and post-dedup; both arms here went through the same managed path, so the comparison is replay against replay on the same audio.
- **The matched percentage is not comparable** to the endurance Section 4 matched percentage (different rule, replay against live), and **the NET is not comparable to the earlier +8.89 pp as if it were the same instrument**: the match rule (message text here, payload there), the build (native here, a Python fit there) and the corpus all differ. Both figures may be quoted side by side, labelled, without a difference test.
- **The bar separates "corroborated" from "not", not "real" from "not"** (the Architect's own (k) note, spec §6). D1 means the extra decodes are *also decoded by WSJT-X in the same cycle* at a rate that adds 11.7 pp; the not-corroborated shares are only upper bounds on false positives. **§8.2 (are the extras real) is not decided by this run.**
- **Text matching and the hash table:** the callsign hash table is process-global and the ON arm's residual decodes seed it, so a later hashed-callsign message can render differently from the OFF arm. Matching is by text, so this is part of the flag's real effect, not an artefact; V4 compares numeric fields and is unaffected. Warm-up: one discarded cycle per process start was decoded with that arm's own flag state, as in S1 and Test B. Neither was affected by a restart: there were none.
- **Inherited open pre-flight item:** `wsjtx_ini_dial_freq_matches_daemon: false` at the live arm time was not resolved; the matched-pair frequency means agree (1 482.4 vs 1 482.3 Hz), so the two decoders heard the same audio.
- **Not measured here:** false-positive rate beyond the upper bound, live-path timing on another machine, multi-pass, any other band.

## 9. What D1 licenses, and what stays open

- **Citable as:** "NET +11.73 pp [11.41, 12.03], one 40m night, replay vs replay, Test B match rule", with the scope sentence of §1.
- **Open after this run:** band replication; the false-positive rate; live-path behaviour (plausibility and the real-time budget on another machine); multi-pass; the band-D flag above.
- **Not decided here, and the Captain's:** whether the flag defaults to ON, and whether batch 2 reaches the answerer. This run informs those decisions; it does not make them.
