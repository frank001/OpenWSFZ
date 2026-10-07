# RULING — `Q-GATE` (Amendment 7): **GATE-OPEN** (GA, GC), GB GATE-FAIL. The strength gate keeps +4.07 pp, at 0.178 unexplained outputs per cycle, against a 0.15 budget. And the "unexplained" outputs are real transmissions in the audio

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-07 11:15Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA report `report_gate.md` + `gate_rows.json` / `gate_thresholds.json` / `analysis_gate.json` @ `44c70ea2` (`qa/coh-gain`, local, not pushed); thresholds commit `1e8a5270` (before any TEST join); numeric files `artefacts/rr_2026-10-07_coh_gain_gate/gate_features.csv`, `wrongid_rows.csv`, `rows.csv` of the fresh samples (numbers only, HK-037).
- **Against:** spec §16 (Amendment 7, `790bef39`); `U_max` 0.15 and `BAR_G` 1.0 both ratified by the Captain before the data.

## 1. Verdict: GATE-OPEN, accepted

| form | TRAIN threshold | TEST KG | TEST UPC | row |
|---|---|---|---|---|
| GA (F1b ≤ T1) | 17.552 dB (UPC 0.149 on TRAIN) | **+4.07 pp [3.81, 4.33]** | **0.178 [0.145, 0.213]** | **GATE-OPEN** |
| GB (F2 ≥ T2) | none feasible | — | — | **GATE-FAIL** |
| GC | the same kept set as GA | = GA | = GA | **GATE-OPEN** |

The gain clears the bar easily; the unexplained rate straddles the budget. **No step-3 form is licensed by this row.** QA was right not to retune T1 after seeing TEST: that would be post-hoc. 🛑 This verdict is final for this gate and is not re-read with relabelled data (standing prohibition).

**Checked myself:** the order of commits (row list `6a8fe449` → thresholds `1e8a5270` → report `44c70ea2`); Q1 4,949 / 4,949; GA keeps, on all 7 samples, 2,512 RIGHT / 351 unexplained (M-NONE + M-OWS) / 181 M-NEAR. QA's TRAIN + TEST give 2,513 / 351 / 181; the one-row difference is a row at the threshold, from the 4-decimal rounding in the persisted F1b. It does not touch the row.

**One report error to correct before push (HK-022):** *"Selection of F1b ≤ 17.55 dB means the gate keeps the STRONGER own-strength outputs"* is backwards. F1b ≤ T1 runs the fallback on the **weaker** signals and drops the stronger ones, which is where the unexplained outputs concentrate. Fix that sentence where it is. Nothing else changes.

## 2. What the features say about the "unexplained" outputs (descriptive, post-hoc, NOT a row)

Medians from `gate_features.csv`, joined to the WRONG-ID labels:

| class | n | F1b (strength, dB) | F2 (decoded message's tones match the audio) | C3's offset from WSJT-X's position |
|---|---:|---:|---:|---|
| RIGHT | 3,382 | 12.0 | 0.76 | df −0.1 Hz (5–95 %: −0.9 … +0.7), dt −0.055 s |
| M-NEAR (WSJT-X neighbour) | 435 | 19.4 | 0.95 | df −0.1 Hz (**−2.0 … +1.9**), dt −0.005 s |
| **M-NONE (unexplained)** | 912 | **21.2** | **0.98** | **df −0.1 Hz (−0.8 … +0.7), dt −0.055 s** |
| OSD chance decodes | 215 | 9.9 | **0.05** | — |

What follows from it:

- **The unexplained messages are physically in the audio.** A chance codeword matches the audio's strongest tone on almost no symbols (the OSD rows: 0.05). The unexplained outputs match on 98 %, more than the right recoveries do. **On 321 of the 912 rows, our CURRENT extractor (G) independently decoded the same message** (equal distance from the truth on 319). Two methods read the same message there.
- **They sit exactly at WSJT-X's own position**, with the same offset profile as the right recoveries. The real neighbours, by contrast, spread ±2 Hz. So this is very probably the same transmitter WSJT-X decoded, and our audio carries a different message from it than WSJT-X logged for that cycle.
- **They are NOT whole-cycle misalignment.** Cycles that contain an M-NONE have the same G-fail rate as those that do not (0.436 vs 0.424); only 8 cycles hold 3 or more.
- **This is why F2 (GB) failed:** it was built to catch chance codewords, and these are not chance codewords.

**Candidate explanations, not separated:** (i) the truth is mis-encoded: re-encoding WSJT-X's text picks a different message type or encoding from the one the sender used, for example compound or non-standard calls or a hashed call; (ii) the same station's message from another period sits in our audio at that spot (whole-cycle misalignment is ruled out, a partial one is not); (iii) a second transmitter within 1 Hz and 50 ms of the first. 🛑 After CW3 I state no favourite. **Until it is separated, "unexplained" is an UPPER bound on false decodes that is probably loose. It is not a false-decode rate.**

## 3. The decision, with its data (the Captain's)

| option | cost | what it leads to |
|---|---|---|
| **Park** | nothing | All results committed and citable. The lead stands at: a strength-gated fallback keeps **+4.07 pp** on held-out cycles at **≤ 0.178** unexplained per cycle (an upper bound, probably loose). |
| **`FIELD-ID` diagnostic first** (spec §17, below) | minutes of CPU, data on disk, one QA round | Says what the unexplained outputs ARE. If they are mostly instrument error (i) or audio placement (ii), the false-decode worry largely goes away, and step 3 must count false decodes with a better instrument. If they are (iii) or unexplained, the 0.178 stands as a real concern. It does not change this gate's verdict. |
| **Step-3 build spec now** | a Developer build (native C3 + the GA strength gate, flag OFF, OSD off in the fallback) + an offline OFF/ON replay through the real product | Measures the real gain and false decodes, noise-only candidates included, on the product itself. Rests on an OPEN gate and on an instrument we now know mislabels some real signals. |

**Does it matter?** Yes: the gated lead is still **about 4 pp**, the largest the programme has. My recommendation is **`FIELD-ID` first**. It is the cheapest step, and the step-3 replay would otherwise inherit the same matcher and its blind spot.

## 4. Predictions, scored at ruling time

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| CQ1 | Q1 passes | 0.90 | C | ✅ HIT (4,949 / 4,949) |
| CQ2 | at least one form GATE-OK | 0.45 | H | ❌ MISS (OPEN) |
| CQ3 | GB or GC keeps more RIGHT than GA | 0.60 | H | ❌ MISS (GB infeasible, GC = GA) |
| CQ4 | TEST KG within 0.5 pp of TRAIN KG for the chosen form | 0.70 | H | ⏸️ QA's report gives TEST KG only; scored when QA adds TRAIN KG (one line in the correction) |
