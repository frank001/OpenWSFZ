# `DENSITY-REMEDY` Stage 2 — result: **two finalists, both the footprint lever alone at the default ramp** — `(−5,+15,0.0)` and `(−5,+15,0.5)`; **every deeper-ramp variant was rejected**, 🔴 **and ROW 0d FIRED (disclosed in its own section, §4)**

QA, 2026-09-20 (`date -u`, HK-017). Per spec `2026-09-19-1228-architect-to-qa-spec-density-remedy-suppression.md` §5 as amended by
§14, §15 and §16 (`arch/density` `b590aff0`). Harness `qa/rr-study/density-remedy/stage2_sweep.py`, **pre-registered before any
decode as `f1690044`, amended per §15 as `58b770dd`, re-registered per §16 as `04c8ad1a` before any measure was evaluated**.
🛑 **Stage 3 is NOT started** and needs its own Captain go and a Captain-ratified `U_base` / `GAIN_BAR`. **No default changes in this arm.**

**Headline.** On the bench, **narrowing the ±1-bin footprint at today's ramp recovers victims and costs nothing measurable**: side weight
**0.0** lifts recovery in the V0-excluded units from **0.007 to 0.492** (`G − G0` = **+0.485**), and side weight **0.5** to **0.224** (+0.218), with
**no neighbour harm** (H1 worst-cell drop 0.000, every ungated cell also improves), **no bystander harm** (H2 = 1.000) and **fewer junk rows**
(−156 and −106 rows, `z` −5.05 and −3.43). **Of the 23 variants that deepen the ramp, 16 fail H2 and 7 fail H1**, so the floor lever and the top-of-ramp lever
**did not survive on this bench**. **There is no third-ranked variant** (only two passed), so Stage 3 has no substitute without a re-run.

🔴 **Four things to read before citing it.**
1. **The gain is near-binary and lives in the strong-blocker cells.** With the side bins untouched, F goes from ~0 to **1.000** in every cell whose
   blocker E reports ≥ +5 dB (all Δf), and **stays at ~0 in the E −5 "floor" cells** (§6). The pooled 0.492 is a property of *which* cells V0 excludes,
   **not an estimate of anything live**. Cells are a design, not a sample.
2. **Stage 0 said the live RB bucket is FLAT in Δf (38.8 / 43.1 / 43.6 %), not where a footprint predicts.** This bench finds the footprint is what
   kills the victim. The two are **not reconciled**; Stage 3 is the test. Do not read the bench as a live forecast.
3. **H2 is driven by ONE bystander.** Every H2 rejection is the loss of station `H`, which shares 1500 Hz with the stronger `G` (§5). The other ten stations
   recover at ~1.000 in every variant. The instrument is flat except there (HK-026).
4. 🔴 **Scope limit, next to the finding (§15.1.1): reported SNR saturates at +16 for nominal ≥ +15, so the bench cannot show a blocker stronger than the
   "full" band. Any `snr_max` statement speaks to the RAMP INTERIOR only.**

---

## 1. HK-020 / HK-022 — critical config

| item | value |
|---|---|
| Binary | `decoding_improvement` `fa8a56ae` (PR #184), `libft8.dll` SHA-256 `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba`, shim `20260054`. **One DLL for every job of every set** (0a), extracted with `git show`, never the working tree |
| Params | `ft8_set_decode_params(10, 0.10, 40)`, **read back through `ft8_get_decoder_params` in every job** (`table_ok` in all 504 + 168 headers). Every variant's triple read back with `ft8_get_supp_params`: **0 mismatches** |
| Test filter | **none**: Python/ctypes harness, nothing can be filtered out silently |
| Scene | 12-station S8HN, E at 1150 Hz, F at 1150 + Δ; only E's and F's message text change. **8 Q-prefix pairs**, both messages 77-bit `i3 = 001` (checked against the decoder's encoder) |
| Cells | **21** = 14 inherited verbatim + 7 interior-of-ramp (`half5`, `heavy12` at each Δ; `e15` at Δ18.75). Sub-bands read in **reported SNR** from a **measured** calibration (reported = nominal + 1 dB, **saturating at +16**) |
| Seeds | classification `31000 + 8·cell + pair`, `t` 0..99 (N = 100); measurement `32000 + …`, `t` 0..49 (N = 50); **25,200 seed rows, unique and disjoint** (sha256 `fb0f91c2…`) |
| Variants | 27 − exactly **(−15, +5, 1.0)** (H5's exact ramp, **never run**) = **V0 + 25**, built **sorted**. V0 in its **own process, setter never called**; variants + the null VN in variant processes |
| Volume | classification **168 jobs / 16,800 scenes** (V0 only); measurement **504 jobs**: V0 ×2 (0b) and 26 decodes per scene, **8,400 scenes, 218,400 variant decodes**. 0 failed jobs |
| FP clause | **branch B′** (§16.2): V0 bench junk emission **164.29 per 1,000** (classification) → the spec's absolute `+1.0` bar was ≈ 0.13 SD and is dead |

## 2. ROW 0

| row | check | result |
|---|---|---|
| **0a** | DLL SHA + version in every header; params read back; every triple read back | ✅ silent |
| **0b** | V0 measurement run twice, record streams identical | ✅ silent |
| **0c** | excluded set ≥ 24 units / ≥ 3 cells / ≥ 4 pairs | ✅ **98 units, 17 cells, 8 pairs**; 0 within 1 SE of the 0.20 boundary; bimodal (95 units < 0.1, 56 units ≥ 0.9) |
| **0d** | VN ≡ V0 per scene | 🔴 **FIRED as first written; passes as re-spec'd (0d′, §16.2).** §4 |
| **0e** | per-lever sensitivity | ✅ every family moves the stream: FLOOR 8,400 / 8,400, TOP 8,400 / 8,400, FOOTPRINT 8,152 and 8,400 of 8,400 |
| **0f** | every (Δf × half/heavy/full) populated, from the **measured** classification SNR | ✅ half = 2, heavy = 1, full = 1 at each Δf |
| **0g** | completeness | ✅ all jobs and record counts |
| **0h** | FP-clause precondition (branch selector) | ✅ **164.29 per 1,000 → branch B′** (not near-bar) |

## 3. The 26-row surface (mandatory, §14.7)

`G` = recovery in the 98 V0-excluded units; `dG` = `G − G0` (`G0` = 0.007); worst-cell H1 = the largest V0-minus-variant drop among the **9 gated cells**
with its paired SE; `junk/1k` = junk rows per 1,000 scenes (V0 **157.50**, 1,323 rows on the measurement set); `S`, `q`, `z` are branch B′'s scene-paired **count** statistics.
The clause column is the **first failing** clause (H1, then H2, then FP, then GAIN).

| variant `(snr_min, snr_max, s)` | G | dG | worst-cell H1 drop ± paired SE | H2 | junk/1k | S | z | dist | first failing clause |
|---|---:|---:|---|---:|---:|---:|---:|---:|:---:|
| **V0 (−5,+15,1)** | 0.007 | — | — | 1.000 | 157.50 | — | — | 0 | — |
| (−15,+5,0) | 0.999 | +0.992 | 0.003 ± 0.007 | 0.909 | 197.98 | +340 | +8.86 | 6.00 | H2 |
| (−15,+5,0.5) | 0.567 | +0.561 | 0.031 ± 0.012 | 0.909 | 170.24 | +107 | +3.13 | 5.00 | H2 |
| (−15,+10,0) | 0.999 | +0.992 | 0.000 ± 0.000 | 0.909 | 175.83 | +154 | +4.35 | 5.00 | H2 |
| (−15,+10,0.5) | 0.573 | +0.567 | 0.010 ± 0.006 | 0.909 | 161.67 | +35 | +1.05 | 4.00 | H2 |
| (−15,+10,1) | 0.358 | +0.351 | **0.828** ± 0.019 | 0.909 | 194.40 | +310 | +9.96 | 3.00 | **H1** |
| (−15,+15,0) | 0.999 | +0.992 | 0.000 ± 0.000 | 0.909 | 163.33 | +49 | +1.44 | 4.00 | H2 |
| (−15,+15,0.5) | 0.623 | +0.617 | 0.010 ± 0.006 | 0.909 | 156.79 | −6 | −0.18 | 3.00 | H2 |
| (−15,+15,1) | 0.356 | +0.349 | **0.785** ± 0.021 | 0.938 | 181.19 | +199 | +7.00 | 2.00 | **H1** |
| (−10,+5,0) | 0.999 | +0.992 | 0.000 ± 0.000 | 0.909 | 192.26 | +292 | +7.73 | 5.00 | H2 |
| (−10,+5,0.5) | 0.574 | +0.568 | 0.010 ± 0.006 | 0.909 | 169.52 | +101 | +2.96 | 4.00 | H2 |
| (−10,+5,1) | 0.358 | +0.351 | **0.820** ± 0.019 | 0.909 | 207.86 | +423 | +12.58 | 3.00 | **H1** |
| (−10,+10,0) | 0.990 | +0.983 | 0.000 ± 0.000 | 0.909 | 165.95 | +71 | +2.05 | 4.00 | H2 |
| (−10,+10,0.5) | 0.549 | +0.543 | 0.010 ± 0.006 | 0.909 | 150.36 | −60 | −1.89 | 3.00 | H2 |
| (−10,+10,1) | 0.282 | +0.275 | **0.529** ± 0.027 | 0.909 | 182.62 | +211 | +7.21 | 2.00 | **H1** |
| (−10,+15,0) | 0.811 | +0.805 | 0.000 ± 0.000 | 0.909 | 148.45 | −76 | −2.35 | 3.00 | H2 |
| (−10,+15,0.5) | 0.487 | +0.480 | 0.000 ± 0.000 | 0.966 | 147.62 | −83 | −2.64 | 2.00 | H2 |
| (−10,+15,1) | 0.244 | +0.238 | **0.080** ± 0.015 | 1.000 | 180.36 | +192 | +6.85 | 1.00 | **H1** |
| (−5,+5,0) | 0.637 | +0.630 | 0.000 ± 0.000 | 0.909 | 176.31 | +158 | +4.42 | 4.00 | H2 |
| (−5,+5,0.5) | 0.240 | +0.234 | 0.010 ± 0.006 | 0.909 | 157.62 | +1 | +0.03 | 3.00 | H2 |
| (−5,+5,1) | 0.087 | +0.080 | **0.562** ± 0.025 | 0.909 | 202.38 | +377 | +11.52 | 2.00 | **H1** |
| (−5,+10,0) | 0.519 | +0.512 | 0.000 ± 0.000 | 0.909 | 152.50 | −42 | −1.29 | 3.00 | H2 |
| (−5,+10,0.5) | 0.172 | +0.165 | 0.000 ± 0.000 | 0.934 | 145.00 | −105 | −3.38 | 2.00 | H2 |
| (−5,+10,1) | 0.028 | +0.021 | **0.503** ± 0.027 | 1.000 | 176.19 | +157 | +5.60 | 1.00 | **H1** |
| **(−5,+15,0)** | **0.492** | **+0.485** | 0.000 ± 0.000 | **1.000** | **138.93** | −156 | **−5.05** | 2.00 | **PASS** |
| **(−5,+15,0.5)** | **0.224** | **+0.218** | 0.000 ± 0.000 | **1.000** | **144.88** | −106 | **−3.43** | 1.00 | **PASS** |

- **Tally of first-failing clauses: H2 16, H1 7, PASS 2, GAIN 0.** FP (B′) was never the *first* failing clause, but `z > 3.0` with `S > 0` also holds for 12 rows (all already rejected earlier).
- **`finalist()` ranking** (`−G`, distance, literal triple): **1. (−5,+15,0)**, **2. (−5,+15,0.5)**. 🛑 **There is no 3rd-ranked variant.**
- **H5 corner:** 0 of the four bracketing cells passed ⇒ **not implicated**; `(−15,+5,1.0)` was never run.
- **Instrument note (§14.5):** 0 variants were rejected by H1 alone ⇒ the note **does not fire**.
- **H1 coverage (disclosed, §15.1.2):** **9** cells gated (≥ 4 non-excluded pairs), **3** reported-only, and **9** have **no** non-excluded pair (F is excluded there, so those cells are judged by G, not H1). For **both finalists the ungated cells all *improve*** (`primary 18.75/3.0`: +0.08 and 0.00; `e15 12/3.0`: +0.36; `heavy12 12/3.0`: +0.167), so nothing hides behind the gate.

## 4. 🔴 ROW 0d FIRED — its own section (§16.5)

**The first evaluation of phase B stopped at ROW 0d.** 0d asserted that the null variant VN (setter called explicitly at `(−5,+15,1.0)`, decoded in a variant process) has a
decode `sha` identical to V0's (own process, setter never called) on **every** scene. It differed on **2 of 8,400 scenes** (two different cells, one scene each), **only in `sha`
and the junk-row text-hash list**. F recovery, the 11-station recovery mask, the junk-row **count**, the pass counts and E's reported SNR were **identical on all 8,400**.

**Cause, verified in `ft8_shim.c`:** `g_session_hash_table` is a **process-global static, initialised once and never re-initialised** for the life of the process, and callsign
resolution also depends on entry recency (`announce_stamp`). A junk row that carries a hashed callsign therefore renders differently depending on what was decoded earlier in the
process. This is the shipped decoder's behaviour, and the live app's, **not a harness bug**. The Architect's ruling (§16) adds that `unpack28` consults the table only for a hashed
`n28`, so a correct decode of a plain `Q` call can never be affected.

**Ruling (§16.2, option A).** 0d was **re-spec'd as 0d′**: VN ≡ V0 per scene on **`f`, `m`, `nfp`, `pc`, `e`** (every field any measure reads), which **holds on all 8,400 scenes**. The FP
clause was **re-keyed from text to per-scene junk COUNTS** (branch B′). **The two scenes stay in the measurement set.** No variant measure had been evaluated when the row fired, and the
re-registration was committed (`04c8ad1a`) before the verdict ran. **ROW 0 was therefore NOT silent under the row as first written**, and this report does not present it as though it were.
A standing consequence (§16.3): **compare outcome fields, never rendered text, when a comparison spans processes.**

## 5. What the surface says, and what it does not

- **The footprint lever alone (`s` < 1 at the default ramp) is the only thing that passes.** Side weight 0 and 0.5 both clear every clause, with zero measured harm and *fewer* junk rows.
- **Deepening the ramp buys a lot of `G` and pays for it.** With `s = 0` the deeper ramps reach `G` 0.52–0.999, but every one fails **H2**: station **`H`** (−6 dB, sharing **1500 Hz** with the stronger `G`) is
  lost. `H`'s recovery is **1.000** at V0 and at both finalists, **0.000** at `(−15,+15,0)` and **0.630** at `(−10,+15,0.5)`; **all other ten stations stay ~1.000 in every variant** (E 0.998 throughout).
  With `s = 1` the deeper ramps instead fail **H1**: neighbour harm of 0.08 to 0.83 in the strong-blocker cells.
- **This is one co-channel pair.** H2's bar (0.01) is ≈ 0.11 of one station, so a single lost co-frequency station rejects a variant. It says "deeper suppression takes a co-channel weaker
  station with it", which is plausibly real live, but it is **one station in one scene**, not a distribution of bystanders.
- **The §11.3 top-of-ramp reading is not supported as a stand-alone lever on this bench**: `snr_max` < +15 with the footprint untouched (`s = 1`) either harms neighbours (H1) or, with `s < 1`, loses `H` (H2).
  **Bounded by the +16 saturation:** the bench cannot present a blocker above the "full" band, so this is a statement about the ramp interior.

## 6. Where the finalists' gain comes from (per cell, V0-excluded units only; reporting)

| cell | units | trials | V0 | (−5,+15,0) | (−5,+15,0.5) |
|---|---:|---:|---:|---:|---:|
| primary Δ6.25, X3 / X6 (E −5) | 8 / 8 | 400 / 400 | 0.000 | 0.000 | 0.000 |
| primary Δ12, X1 | 3 | 150 | 0.060 | 0.240 | 0.113 |
| primary Δ12, X3 / X6 | 8 / 8 | 400 / 400 | 0.000 | 0.003 / 0.000 | 0.000 |
| primary Δ18.75, X1 | 1 | 50 | 0.180 | 0.460 | 0.280 |
| primary Δ18.75, X3 / X6 | 7 / 8 | 350 / 400 | 0.000 | 0.000 | 0.000 |
| **strong (E +8)** Δ6.25 / Δ12 | 8 / 1 | 400 / 50 | 0.000 / 0.100 | **1.000 / 1.000** | 0.075 / 1.000 |
| **half5 (E +5)** Δ6.25 | 8 | 400 | 0.000 | **1.000** | **1.000** |
| **heavy12 (E +12)** Δ6.25 / Δ12 / Δ18.75 | 8 / 5 / 1 | 400 / 250 / 50 | 0.000 | **1.000** | 0.000 / 0.996 / 1.000 |
| **e15 (E +15)** Δ6.25 / Δ12 / Δ18.75 | 8 / 6 / 2 | 400 / 300 / 100 | 0.000 / 0.013 / 0.050 | **1.000** | 0.000 / 0.697 / 0.790 |
| **pooled** | **98** | **4,900** | **0.007** | **0.492** | **0.224** |

- The gain is **all in the cells whose blocker reports ≥ +5 dB**, and it is a **switch**: 0 → 1.000. In the **E −5 cells** (the "floor" regime A) the footprint lever does **almost nothing**, so the
  regime-A loss **is not addressed by the surviving variants**; the variants that do address it (deeper `snr_min`) are the ones H1/H2 reject.
- **Side weight 0.5 is not a smaller dose of the same win at small Δ**: at Δ6.25 it recovers **0.000** with a heavy or full blocker (heavy12, e15) and 0.075 with E +8, **though 1.000 with E +5**. (Consistent with the half-weight side bin still overlapping F's tone at that spacing; the mechanism was **not tested**.)
- **Uncertainty:** treating the 4,900 trials as independent gives SE ≈ 0.007 on G, but the units are **clustered by cell × pair**, so the true uncertainty is larger. The per-cell view above is the honest form.

## 7. Junk rows (counts only, §15.3)

V0 **bench junk emission: 157.50 per 1,000 scenes on the measurement set (1,323 rows) and 164.29 on the classification set (2,760 rows / 16,800)**.
🛑 **A BENCH rate on synthetic AWGN with the offline normalisation: cite it only as "bench junk emission, Stage 2 classification set, V0"; never as a live FP rate; never comparable to any FP-WORKSTREAM figure.**
Junk rows are stored **only as hashes and counts**; no text appears in any committed file or in this report.

**Frequency-bucket breakdown of added/removed junk (§16.2, REPORTED, NEVER GATED).** Junk rows have no stored frequency, so this comes from a targeted re-decode of the **same** 8,400 measurement
scenes for V0 and the two finalists (`junkfreq`, registered in the S16 addendum before it ran); its **per-scene junk counts equal the stored counts on all 8,400 scenes × 3 legs (0 mismatches)**.
Buckets are 500 Hz of the candidate's frequency (history-free).

| bucket (Hz) | 0 | 500 | 1000 | 1500 | 2000 | 2500 | 3000 | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| junk rows, **V0** | 63 | 145 | **658** | 301 | 56 | 100 | 0 | **1,323** |
| junk rows, **(−5,+15,0)** | 63 | 153 | 527 | 271 | 56 | 97 | 0 | 1,167 |
| junk rows, **(−5,+15,0.5)** | 63 | 174 | 551 | 286 | 56 | 87 | 0 | 1,217 |
| added, (−5,+15,0) | 0 | 39 | 256 | 62 | 0 | 27 | 0 | 384 |
| removed, (−5,+15,0) | 0 | 31 | 387 | 92 | 0 | 30 | 0 | 540 |
| added, (−5,+15,0.5) | 0 | 59 | 265 | 68 | 0 | 17 | 0 | 409 |
| removed, (−5,+15,0.5) | 0 | 30 | 372 | 83 | 0 | 30 | 0 | 515 |

- **Half of V0's junk (658 of 1,323) is in the 1000–1500 Hz bucket**, where the scene's strong stations and E/F live (1050, 1150, 1162 and F at 1156–1169 Hz). The finalists' net reduction is concentrated there (−131 for `(−5,+15,0)`).
- **The change is mostly churn, not just a reduction**: 384 rows added and 540 removed for `(−5,+15,0)` (net −156). This is why the breakdown is **not a gate**: a swap pattern is not FP burden. No mechanism is claimed.

## 8. What this could NOT see (HK-022 / HK-026)

1. **One synthetic 12-station AWGN scene, 8 message pairs.** The bench FP is a gross-junk filter only (§5.3); **Stage 3 is the FP primary**.
2. **The +16 SNR saturation**: no blocker above the "full" band can be presented.
3. **One co-channel bystander pair** drives all of H2 (§5). The bench has no other bystander whose recovery moves.
4. **Cells are a design, not a sample**: no `G` here is a live estimate, and it must not be compared to the 4.30 pp.
5. **The live RB bucket is flat in Δf (Stage 0); the bench footprint effect is not.** Unreconciled.
6. **The noise-floor percentile (§13) is not swept**, and **defaults were never changed**: Stage 2 sets parameters at runtime.
7. **History**: the decoder's callsign table is process-global; a fresh-process replay can legitimately render different junk text than the live session (§16.3).
8. **Windows DLL only.** Classification and measurement each ran in fresh processes on one machine.

## 9. Status and what is needed

- ✅ **Stage 2 is computed on a re-registered, disclosed ROW 0.** Finalists: **`(−5,+15,0.0)` and `(−5,+15,0.5)`**; **no third-ranked variant**.
- 🛑 **Stage 3 needs its own Captain go**, and **`U_base` and `GAIN_BAR` (proposed 0.5 pp) must be ratified before any finalist leg is decoded** (§6.4). Stage 3 would run V0 plus these two legs on C2 audio with this DLL; both finalists are the **same lever at two doses**.
- 🛑 **No default changes anywhere in this arm.** A Stage 3 ROW S would only make a variant *ship-eligible* for the Captain.
- Predictions §14.9 #3–#6 are the Architect's to score; the inputs are: **≥ 1 finalist: yes (2)**; **a finalist with `snr_max` < +15: no**; **the footprint-only `(−5,+15,0)` passes: yes**; **≥ 3 variants rejected by H1 alone within 2 paired SE of 0: no (0 H1-alone rejections)**.
- Artefacts: `artefacts/density-remedy-stage2/` (gitignored). Committed: the harness, `results/stage2_{calibration,prereg_manifest,phaseA_classification,phaseB_row0,verdict}.json` (counts and hashes only; NFR-021 scanned, 0 callsign-shaped tokens).

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
