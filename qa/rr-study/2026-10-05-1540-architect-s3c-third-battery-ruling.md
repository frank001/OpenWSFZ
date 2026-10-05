# RULING — S3c at its third battery: S3C1/S3C2 scored; the E −2.00 movement is real, cause open

- **To:** QA (owner of S3c) — cc Captain, Engineer  **From:** Architect  **Date:** 2026-10-05 15:40Z (`date -u` 15:35:45Z at drafting, HK-017)
- **Branch:** `arch/122-latency` (the only candidate cause in code is #122 step 4). Docs only: `git diff --stat -- src/ native/` empty.
- **Reads:** S3c spec `qa/rr-study/2026-10-02-1730-architect-to-qa-spec-194-s3c-start-time-edge-guard.md` §4, §6; the three S3c tables in
  `qa/rr-study/results/2026-10-02-96077a0/report.md`, `…/2026-10-03-96077a0/report.md`, `…/2026-10-04-766f9cc/report.md` (§ "S3c start-time edge guard");
  `git diff cddd7e34 766f9cc2 -- src/ native/` (read, not run). QA's note `2026-10-05-1530-…` is on QA's local commit `346b7d18` (not pushed); this
  ruling rests on the three reports, which carry the same figures.

## 1. Scoring (spec §6; the first three batteries that include S3c)

| Battery | Build | WSJT-X row | OpenWSFZ row | OpenWSFZ E −2.00 |
|---|---|---|---|---:|
| 1 `2026-10-02-96077a0` | `cddd7e34`, shim 56 | PASS | PASS | 17/32 |
| 2 `2026-10-03-96077a0` | `cddd7e34`, shim 56 | PASS | PASS | 16/32 |
| 3 `2026-10-04-766f9cc` | `766f9cc2`, shim 58 | PASS | PASS | **32/32** |

| # | Prediction | P | Class | Outcome |
|---|---|---:|:---:|---|
| S3C1 | No S3c-WSJT-X FAIL in the first three batteries | 0.80 | H | ✅ **HIT** (0 FAIL in 3) |
| S3C2 | No S3c-OWSFZ FAIL in the first three batteries | 0.75 | H | ✅ **HIT** (0 FAIL in 3) |

Both are the easy direction ("nothing fails"), and S3C2 hit on a guard that is **one-sided**: battery 3's change was upward, which S3c cannot
fail on. S3C2's stated premise ("no sync-search change is planned") held for the source (§3), but the decoder's output at this cell did change,
so the hit is on the letter of the row, not evidence that nothing moved.

## 2. The movement is not luck — correction to the report

`report.md` §5 item 3 (battery 3) says "a coincidence with run-to-run luck at one battery cannot be excluded". **Under the spec's own model it
can.** Batteries 1–2 give 33/64 at E −2.00 (and the edge run 14/32 flag OFF, consistent with them). With independent signals at p = 33/64,
P(X = 32 of 32) ≈ **6 × 10⁻¹⁰**; even at the upper Wilson 95 % bound of 33/64 (≈ 0.64) it is ≈ 5 × 10⁻⁷. Signals within a part share slot
geometry and `L`, so some over-dispersion is possible, but three earlier counts of 14, 17, 16 show no sign of it.

**Ruling:** OpenWSFZ's early-side edge at −8 dB has **moved outward by at least one grid step** (E −2.00 from ≈ 50 % to 32/32) between battery 2
and battery 3. WSJT-X's four rows are identical across all three batteries and the scenario SHA-256 is the same, so the shared harness and
render are not the explanation. Something on OpenWSFZ's side changed. **QA: please amend that sentence where it lives** (HK-022) to
"luck is excluded at P ≈ 6 × 10⁻¹⁰ under independence; the cause is not established".

🛑 **Not a decode-rate claim, and not an improvement claim for the build.** It is one cell, one battery, and its cause is unknown. Do not cite it
outside S3c.

## 3. What the code says (read 2026-10-05; HK-018)

Three `src/`/`native/` commits sit between `cddd7e34` and `766f9cc2`: `fee81a2b` (step 4), `ca8e3118` (completeness test only),
`1d2d81eb` (default ON + absent-key fix). Reading their diff:

- **`CycleFramer.cs`:** the window alignment and boundaries are unchanged. The only addition copies the first 156 000 samples into a new
  zero-filled array for the early output. The full window is untouched.
- **`ft8_shim.c` / `rebuild_shim.bat`:** three new exports (`ft8_hash_state_size/save/restore`) and their link lines. `ft8_decode_all` is not
  edited.
- **`Ft8Decoder.cs` / `DecodePump.cs`:** the ordinary path makes the same calls in the same order. The early path brackets `DecodeAll` with
  save/restore. The final decode waits on the early decode's gate.

So **by reading, step 4 should not change ALL.TXT at all** (spec R3, R8; acceptance A1, A1b). That leaves three candidates, none shown:

| | Candidate | How it would show |
|---|---|---|
| (a) | The early path does reach the final decode after all (an R3/A1b leak, or state the image does not cover) | E −2.00 differs between `earlyDecodeEnabled` false and true on `766f9cc2` |
| (b) | The rebuilt DLL decodes differently at a marginal cell (new link, same source; the PE is not bit-reproducible) | `766f9cc2` early OFF = 32/32 and `cddd7e34` repeat ≈ 16/32 on the same audio |
| (c) | A non-build difference in battery 3 (config or chain) | `cddd7e34` on battery 3's archived audio also gives ≈ 32/32 |

(a) matters most: if it holds, the identity guarantee step 4 merged on is broken. That is why the cause is worth separating, even though the
movement is upward.

## 4. The separating test (parked by the Captain on #194; needs his go)

Recommended form: an **offline replay**, not a station run. Battery 3 ran with `cycleAudioArchive` = all, so its 12 S3c cycles are on disk. Replay
those cycles through the daemon path on three arms and score E −2.00 (plus the other three parts, as a check that nothing else moved) by the S3c
match rule:

1. `766f9cc2`, `earlyDecodeEnabled = true` (should reproduce 32/32: a replay check)
2. `766f9cc2`, `earlyDecodeEnabled = false`
3. `cddd7e34` (the baseline-194 scratch tree still exists)

Reading: 1 ≠ 2 ⇒ (a). 1 = 2 ≈ 32 and 3 ≈ 16 ⇒ (b). 3 ≈ 32 ⇒ (c), and the replay of batteries 1–2's archived S3c cycles through `766f9cc2` is
the next step. If arm 1 does not reproduce battery 3's count, the replay is not the live path for this cell and the test stops there (no
reading of arms 2–3).

**Predictions (blind, written before any arm runs; scored at the test's report):**

| # | Prediction | P | Class |
|---|---|---:|:---:|
| S3X1 | Arm 1 reproduces battery 3 within ±2 of 32 | 0.75 | H |
| S3X2 | Arms 1 and 2 agree within ±2 (early decode is NOT the cause) | 0.75 | H |
| S3X3 | Arm 3 gives ≤ 24/32 (the build, not the run, moved) | 0.55 | H |

## 4a. Separating replay: result and ruling (2026-10-05, after QA's note `qa/rr-study/2026-10-05-1552-qa-s3c-separating-replay-result.md`)

QA ran it on the Captain's go: offline, battery 3's 12 archived S3c cycles, fresh process per arm, flag ON, nhard 40, both batches; harness
committed before any decode (`db2da962`); DLL pins checked at start and end. **E −2.00: arm 1 = 32, arm 2 = 32, arm 3 = 32** (E −1.75 32,
L +2.75 32, L +3.00 0 in all three). The stop rule passed.

| # | Outcome |
|---|---|
| S3X1 | ✅ HIT (32) |
| S3X2 | ✅ HIT (32 = 32): **(a), an early-path leak, is NOT supported** |
| S3X3 | ❌ MISS (arm 3 = 32, not ≤ 24): **(b), the rebuilt DLL, is NOT supported** |

**Ruling: step 4 is cleared for this cell.** The old build gets 32/32 on battery 3's recorded audio, so the cause sits on the "run" side, (c):
either the **audio** that reached the decoder in battery 3 differs from batteries 1–2, or the **live daemon** in batteries 1–2 lost decodes
that a fresh-process replay does not lose.

**Already gathered, read before specifying (HK-018):**

- **Playback scheduling is identical.** `s3c/playback_log.csv`: early cycles started −3.4995 ± 0.0002 s before the boundary in all three
  batteries; late cycles −0.5000 ± 0.0003 s.
- **Chain timing is identical at ALL.TXT's 0.1 s resolution.** WSJT-X's reported DT on the four early-part cycles: −2.3 (32) and −2.1 (29–32)
  in every battery. OpenWSFZ's: −1.6 for the E −2.00 part and −1.4 for the E −1.75 part in every battery (17, 16, 32 rows at −1.6). The S3 and S1 mean
  DT errors agree to ±0.02 s across the three. **So the signal did not arrive later in battery 3.** If anything, battery 3 had none of the
  1–3 WSJT-X rows at −2.0 that batteries 1–2 had. (Aggregates only, computed from the root and QA-tree `wsjt-all.txt`/`owsfz-all.txt`;
  no text read out, HK-037.)

That leaves the **signal level or noise in the recording** (not measured), or **live-path loss** in batteries 1–2 (process state after S1–S8,
or something on the live path the replay does not reproduce).

## 4b. Next step — PRE-REGISTERED before any decode; needs the Captain's go

**Replay batteries 1 and 2's archived S3c cycles** (`_rr_baseline194_daemon_output`: `261003_010600`–`010845` and `261003_030645`–`030930`)
through the **same harness, unchanged** (`db2da962`), on two arms: `cddd7e34` and `766f9cc2` (early ON). Score all four parts with
`s3c_score`. Same stop rule: none needed (there is no live count to reproduce on new audio; the arms check each other).

**Plus one measurement on the archived audio of all three batteries (read-only, no decode):** for each early-part planted slot, the in-band
power at the planted frequency (±25 Hz, over the samples the signal occupies) against the power in the idle cycle that follows at the same
frequency. Reported per battery as a median dB with its IQR. This is the "level" half of (c). QA writes the predicate as code before running it
(HK-025).

Reading (mechanical, both arms must agree within ±2, or the replay is the finding and the rest is not read):

| Batteries 1–2 replay at E −2.00 | Reading |
|---|---|
| ≤ 24 on both arms (each battery) | **Audio.** The recordings differ; the level measurement says whether the cause is level. |
| ≥ 28 on both arms (each battery) | **Live path.** Batteries 1–2's live daemon lost decodes that a fresh-process replay keeps. That is a defect class to chase (state after S1–S8, or timing on the live path). |
| 25–27 | Not separable at n = 32; report descriptively, no further arm without a ruling. |

| # | Prediction (blind) | P | Class |
|---|---|---:|:---:|
| S3Y1 | The two arms agree within ±2 on each battery | 0.90 | H |
| S3Y2 | Reading = **Audio** (≤ 24 on both arms, both batteries) | 0.60 | H |
| S3Y3 | If Audio: battery 3's early-slot in-band level is ≥ 0.5 dB above batteries 1–2's median | 0.55 | H |

🛑 Until this reports, the cell's history stays split at battery 3, as §5 says. Step 4 is no longer a candidate.

## 5. Standing consequences

- S3c stays in the routine battery unchanged. `r_ref` and `k*` are pre-registered and stay as they are: a guard is not re-based on a movement
  whose cause is unknown.
- 🛑 From battery 3 on, never pool S3c E −2.00 counts across `cddd7e34` and `766f9cc2`-or-later builds until §4 has reported.
- #122 phase 4a stays merged. Nothing here shows a defect. It shows that A1b's "identical" has not been tested at a start-time edge.
