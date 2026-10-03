# SPEC: #122 GATE 4a. How much would an early decode catch? Offline truncation replay on two recorded 40 m nights

- **To:** QA (owner; QA may assign the Engineer, with one owner recorded on the board). cc Captain. **From:** Architect. **Date:** 2026-10-03 ~10:15Z (HK-017, `date -u`).
- **Branch:** `arch/122-latency` (local). Docs only: `git diff --stat -- src/ native/` is empty.
- **Why (Captain, 2026-10-03):** *"write the offline step-4 spec in full"*. Roadmap `2026-10-03-1005-architect-122-latency-roadmap.md` §2.3 (step 4 = an **extra** early decode before the slot closes; the final decode stays unchanged).
- 🔴 **#122 stays on HOLD.** This spec is **ready to run, not authorised.** It runs on the Captain's go, given in QA's or the Engineer's window.
- **Status:** PRE-REGISTERED. QA commits the harness changes, both frozen cycle lists and the row predicates as code **before the first decode**. Changes after that only by a dated amendment that says why.
- **Needs:** no station, no radio, no build. About **3 h of exclusive PC time** (four corpora, §3) (decode times are measured, so the CPU rule applies in full: no other runs, suites, builds or daemons). No `src/` or `native/` change: the harness is test-only code under `qa/`.

## 1. Question

**Q1.** If OpenWSFZ decoded the window early, at `15 − x` s, with the rest of the window not yet captured, **what fraction of the decodes that the full window gives would that early decode already have**, per `x`?

**Q2.** **Does an early decode produce decodes that the full window does not**, and are those real (the live WSJT-X also decoded them) or false?

**Q3.** **Which stations does it miss**: late starters (by DT), weak ones (by SNR), or both?

**Q4.** **How much earlier would those decodes appear**, given the early decode's own time?

This tests the claim behind step 4: an early decode published as an extra batch costs nothing in recall, because the final decode is unchanged. It measures the claim's **benefit** (Q1, Q4), and its two possible **costs**: false decodes (Q2), and any effect of the early decode on the final one (V2).

## 2. Fixed inputs (asserted in code)

| Item | Value | Assertion |
|---|---|---|
| Build | current `main` (record the SHA) | provenance recorded |
| DLL | `libft8.dll` SHA-256 `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` | actual = pinned at the start and end of **every** arm; a mismatch makes that arm INVALID |
| Decode call | the ordinary decode, **flag OFF**: `Ft8Decoder.DecodeTwoStageAsync` with `subtractionEnabled=false`, the same call as the 10-01 replay's OFF arm (`replay81` mode `two0`). QA adds a mode `trunc` to `qa/rr-study/sub-feas/replay81/Program.cs` | flag, `nhard`, decode parameters read back in-process at the start and end of each arm (`# readback`) |
| `nhard` | 40 | asserted |
| Post-processing | none added. `DecodeTwoStageAsync` already applies `IsPlausibleMessage` and the per-cycle text de-duplication (10-01 replay report, `Ft8Decoder.cs:510/528/534`). QA re-checks those lines on the build used and cites them | — |
| **Corpus P (primary)** | 2026-09-30/10-01 night: `artefacts/20260930_1930_endurance_run-gathered/owsfz/wav/` (4 299 WAVs). Reference: `…-gathered/wsjt-x/ALL.TXT` | R0 per file: 12 kHz, mono, 16-bit, 180 000 samples |
| **Corpus R (replication)** | 2026-09-22/23 night: `artefacts/20260922_2056_endurance_run-gathered/owsfz/wav/` (2 882 WAVs). Reference: `…-gathered/wsjt-x/ALL.TXT`. 40 m, Voicemeeter B1, `nhard` 40 (since 2026-09-12) | R0 as above. QA confirms band, chain and `nhard` from the run's own record (not from `contents.md` alone, whose build line is unreliable) |

| **Corpus X17 (cross-band)** | 2026-08-08 17 m session: `artefacts/20260808_live_run_1154-8080-17m/owsfz/wav/` (1 856 WAVs). Reference: `…/wsjt-x/ALL.TXT`. Device "USB Audio CODEC" | R0 as above |
| **Corpus X80 (cross-band)** | 2026-08-09 80 m session: `artefacts/20260809_live_run_0155-8080-80m/owsfz/wav/` (1 988 WAVs). Reference: `…/wsjt-x/ALL.TXT`. Device "USB Audio CODEC" | R0 as above |

- **P and R** are the standard capture chain (one FT-991A, Voicemeeter B1). The direct-USB-CODEC 24 h night is **not** used.
- **`nhard` does not restrict the corpus choice.** It is a decoder setting, and this replay sets it to 40 itself. The never-pool rule is about **live** decodes made under 60 against 40. The recorded audio does not depend on it.
- **X17 and X80 add bands**, not nights. They were recorded with older daemon builds (gathered `main` `b8845cd` / `46436c4`, with uncommitted changes), before the CycleFramer-alignment work and before the dual-WSJT-X `save\` collision fix (2026-08-19). Two consequences, handled in code:
  - (i) their window may sit at a different offset from the slot boundary. V5 checks this and labels a corpus that fails;
  - (ii) their WSJT-X `ALL.TXT` may be contaminated. **Their `S_corr`/`S_unc` split is descriptive only.**
- **The 8080 folder** of each pair is used. The 8081 folder is the second daemon on the same audio and adds nothing.

## 3. Cycle lists (frozen before any decode)

- **P:** take the 10-01 replay's frozen `selection.json` (4 298 cycles, SHA-256 over LF-normalised bytes `55a951c8…53c977cf`, `qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/selection.json`) and keep every cycle whose 0-based index in that list is **≡ 0 (mod 4)**: ≈ 1 075 cycles, about 2.7 h of the night evenly spaced. Assert the parent SHA, then freeze the child list as `selection_p.json` with its own SHA.
- **R:** every R0-passing WAV of the window **except** the first and last stamps, in ascending stamp order. Then the same `≡ 0 (mod 4)` rule: ≈ 720 cycles. Freeze it as `selection_r.json` with its SHA.
- **X17, X80:** the same rule as R (all R0-passing WAVs except the first and last stamps, every fourth): ≈ 465 and ≈ 495 cycles. Frozen as `selection_x17.json` and `selection_x80.json` with their SHAs.
- No cycle is excluded on its content. Cycles in which WSJT-X logged 0 decodes stay in.
- **Why every fourth cycle:** decodes are pooled across cycles (§5), so about 25 000 final decodes on P is more than enough. The full night would cost about 5 h of exclusive PC time and buy no precision that matters.

## 4. Design

**The cut.** For cut `x` (seconds), keep the first `N_x = 180 000 − 12 000·x` samples of the window, and set samples `N_x … 179 999` to **0**. The array length stays 180 000.
- Zero-filling is what a live early decode would be given. The not-yet-captured part does not exist, and the decoder's call takes a full-length window.
- `x` is measured on the **window**, which starts at the framer's cycle start (≈ the slot boundary; the decode starts about 0.03 s after the slot end, lateness Q2 derivation). That is exactly what a live early decode would cut, so **no DT convention enters the design**. The DT-convention item (≈ 0.65 s, 0.2 s of it unexplained) is used only to label Q3's bins.

**Grid:** `x` ∈ {0.5, 1.0, 1.5, 2.0, 2.5} s, plus **`x` = 4.0 s as the positive control** (V4).

**Arms (each a fresh process, cycles in ascending stamp order):**
- **Arm F (reference):** the full window only, one decode per cycle. This is the "final decode as it is today".
- **Arm T (early + final, in the order live would run them):** per cycle, decode the cut windows **from the largest cut to the smallest** (4.0, 2.5, 2.0, 1.5, 1.0, 0.5), **then** the full window. All of them run in **one process**, so the process-global callsign hash table has the same history it would have live: earlier cuts first, the final decode last.
  - **Matching** is done inside the process (HK-037: text never leaves the matching function; outputs are counts).
  - For each `x`, an early decode **matches** a final decode of the same cycle when it has the same message text and |Δf| ≤ 10 Hz, paired one-to-one nearest-first. That is the Test B rule, `CorroborationDeltaHz = 10`, as used in the 10-01 replay.
  - **Matching against WSJT-X**, for unmatched early decodes only: the same rule against the live WSJT-X `ALL.TXT` rows of that cycle (10-01 replay §4).
- **Timing:** a managed `Stopwatch` around each decode call, recorded per call, in ms.

Order of runs: P-F, P-T, R-F, R-T, X17-F, X17-T, X80-F, X80-T. One process at a time. **About 3 h** of exclusive PC time in total (P ≈ 65 min, R ≈ 45 min, X17 + X80 ≈ 60 min).

## 5. Pre-registered rows

**Validity (if any row FAILS, no catch figure is reported; the report names the row and stops):**

| Row | Predicate (as code) |
|---|---|
| V0 inputs | DLL actual = pinned at the start and end of all eight runs. Flag OFF and `nhard` 40 read back at the start and end. `selection_p.json`'s parent SHA = `55a951c8…53c977cf`. Both child-list SHAs identical in their F and T runs |
| V1 cut placement (HK-026), in code before each decode | for every cut window: samples `[N_x, 180 000)` are exactly 0 **and** samples `[0, N_x)` are bit-identical to the original window. A single failure stops the run |
| V2 the final decode is undisturbed | per cycle, arm T's **final** decode's numeric multiset (freqHz, dt, snr) = arm F's. **PASS iff N/N** on each corpus. This is the "the final decode loses nothing" claim, tested in the one place it could fail offline: the shared hash table seeing the early decodes first |
| V3 stability | 0 access violations, 0 contained exceptions and 0 non-zero exits, in all eight runs |
| V4 positive control: the instrument can see a loss | `C(4.0) ≤ C(0.5) − 0.20` on each corpus (`C` defined below). At `x` = 4 the window ends at 11 s, before any normally-timed transmission has finished (≈ 13.1 s), so a large loss must show. If it does not, the cut is not reaching the decoder, whatever V1 says |
| V5 window alignment (per corpus other than P) | the median OpenWSFZ-reported DT of arm-F decodes that the live WSJT-X corroborates (Test B rule), **minus** the median WSJT-X DT of the same pairs, is within **±0.10 s** of the same quantity on P. A corpus that FAILS is not dropped. Its catch figures are reported with the label *"window offset differs from P by d s: x is not comparable"*, and it is excluded from TR4/TR6 and from the `x*` comparison. This row stops nothing else |

**Outputs (exact definitions; no bar except V-rows).** Every output is given per corpus. Each catch figure also comes with a 95 % percentile CI from a **non-overlapping block bootstrap**: blocks of **10 consecutive listed cycles** (≈ 10 min of night, since the lists take every fourth cycle), the last partial block kept as its own block, numerator and denominator resampled together, B = 10 000, seed 20261003.

- **Catch `C(x)`** = Σ matched early decodes ÷ Σ arm-F decodes, pooled over the list.
- **Spurious, per 100 arm-F decodes:**
  - `S_corr(x)` = unmatched early decodes that **are** corroborated by the live WSJT-X;
  - `S_unc(x)` = unmatched early decodes that are **not**.

  `S_unc` is the false-decode cost that an extra batch would put on the panel and before the automation.
- **Who is missed (Q3):** `C(x)` split by the arm-F decode's reported SNR, in Test B's bands A (≥ 0 dB), B (−10…−1), C (−15…−11) and D (≤ −16). Also split by the arm-F decode's reported DT, in bins ≤ 0, (0, 0.5], (0.5, 1.0], (1.0, 1.5], (1.5, 2.0], (2.0, 2.5] and > 2.5 s, labelled *"OpenWSFZ DT convention, ≈ +0.65 s against WSJT-X's"*.
- **Gain (Q4):** for each `x`, the median and p95 of the early decode's call time `t(x)`, and of the final decode's `t(0)` (from arm F). The early batch appears `G(x) = x + t(0) − t(x)` s before the final batch would, using medians, labelled as a design estimate for this CPU, one process, no other load.
- **Candidate design point (descriptive, for the later build spec, not a verdict on this test):** `x*` = the largest grid `x` with `C(x) ≥ 0.90` **and** `S_unc(x) ≤ 0.10` per 100, computed on **P**, with R reported beside it. If no `x` qualifies, say so.

## 6. What the result decides (for the Captain, after the Architect's ruling)

- If `x*` exists and V2 passed, **step 4 is worth a build spec**. That spec takes `x*` as its starting point, adds the live CPU interaction with the previous cycle's residual pass (flag ON) as a station measurement, and needs the Captain's go (`src/`, HK-011).
- If `S_unc` is material at every useful `x`, an early batch would put false decodes on screen ahead of the final decode. Step 4 then needs a confirmation rule (show only what the final decode keeps, or mark early rows), and that is a design question for the Captain.
- If V2 fails, the early decode **does** disturb the final one through shared state, and "loses nothing by construction" is false. Step 4 stops until that is understood.
- Step 1's EL1 (does WSJT-X publish before the slot ends?) and this test together say whether step 4 is parity with WSJT-X.

## 7. Limits (carried with every figure)

- **Replay is not the live path.** One process, no capture running, no residual pass competing for the CPU. The live early decode would run while the previous cycle's residual pass may still be going.
- **A zero-filled window is not a live partial window in one respect:** the noise floor and candidate scores near the cut may differ from a decoder that is told the window is short. The SNR of matched decodes is reported as a shift (median of early SNR − final SNR, per `x`), descriptive only.
- Two 40 m nights on the standard chain (night-to-night replication), plus one 17 m and one 80 m session on an older build and the USB CODEC device (cross-band, descriptive, subject to V5). One station, one decoder build in the replay, every fourth cycle.
- `C(x)` is a fraction of **OpenWSFZ's own** final decodes, not of WSJT-X's, and not of what is on the band.

## 8. Predictions (blind; scored at ruling time in the ledger)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| TR1 | `C(1.0)` on P ≥ 0.85. Basis: at `x` = 1 the window ends at 14 s, after every station up to `L` ≈ 0.86 s has finished, and the edge run tolerated ≈ 0.89 s of missing tail (synthetic, −8/−16 dB) | 0.70 | H |
| TR2 | `C(2.0)` on P ∈ [0.55, 0.85] | 0.55 | H |
| TR3 | `S_unc(1.0)` on P ≤ 0.50 per 100 arm-F decodes | 0.70 | H |
| TR4 | `|C_P(1.0) − C_R(1.0)| ≤ 0.05` | 0.70 | H |
| TR5 | V0–V4 all pass the first time | 0.65 | H |
| TR6 | for each of X17 and X80 that passes V5: `|C_X(1.0) − C_P(1.0)| ≤ 0.08` | 0.60 | H |

TR1 and TR2 rest on the lateness edge's tolerance carrying over from synthetic AWGN to real signals, and on a DT spread I have not measured for these nights. Weight them accordingly.
