# `DENSITY-P1` Stage 2 — result: **ROW 1 DIRTY, ROW 0 silent** — but it is two different DIRTYs: at E −5 dB **no suppression is applied** (factor 0.93), and where suppression IS applied at Δ 6.25 Hz its ±1-bin footprint **destroys F's own tone bins** (collateral, 0 errors elsewhere)

QA, 2026-09-19 12:01Z (`date -u`, HK-017). Per spec `2026-09-18-1758-architect-to-qa-spec-density-pass1-probe.md`
§2 **as amended by §7** (`arch/density` `c0270a83`, Architect ruling on QA's A1–A4). Captain's go: *"proceed
with stage 2"*. Harness `qa/rr-study/density-p1/density_p1.py`, **pre-registered before any verdict run** as
`73ee2d4f`. Nothing here is a remedy; it locates the loss inside pass 1 and nothing more.

**Headline.** The mechanical verdict is **ROW 1 DIRTY**: all 9 excluded cells read DIRTY (`o1` ≤ 0.15), ROW 0
silent (0a–0g), run A and run B byte-identical. 🛑 **Do not read it as "suppression is too weak".** The spec
asked that E's applied factor be read *before* any DIRTY, and it splits the verdict in two:

- 🔴 **7 of the 9 excluded cells are the E −5 dB cells, and E's median applied factor there is 0.93.** E is
  reported at −3.6 dB, just above the ramp's −5 dB floor, so pass 1 removes ~7 % of its energy. **Essentially
  no suppression was applied**, and DIRTY is near-automatic. The question in those cells is the **ramp's floor**.
- 🔴 **The 2 cells where suppression IS applied heavily are also DIRTY, and they are the informative ones.**
  E +15 at Δ 6.25 Hz (factor **0.000**) and E +8 at Δ 6.25 Hz (factor **0.305**): F's bits are wrong **only** on
  symbols where E's attenuated ±1-bin footprint covers F's tone bin (BER **0.59**), and **0 errors in 9,000 bits
  everywhere else**. That is **collateral damage**, not residual E. The question there is the **footprint**.

**And one thing the CLEAN branch can no longer claim:** the P1 oracle and production agree on **every one of
1,400 trials** (444 both succeed, 956 both fail). **Zero** trials where the bits were decodable at F's true
position and production missed. In this scene, pass 1's candidate stage has no headroom.

---

## 1. HK-020 / HK-022 — critical config

| item | value |
|---|---|
| Binary | Stage 1 DLL, SHA-256 `50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7`, shim `20260053`, from `git show`, checked on disk and in every run (ROW 0a) |
| Params | `k_min_score_pass2 10`, `osd_corr_threshold 0.10`, `osd_nhard_max 40` = `DecoderConfig` defaults (the LIVE app). 🔴 **SET, not read back: no getter exists** (spec §7.1 A3). Set after the wrappers were built |
| Test filter | **none.** Python/ctypes harness; nothing can be filtered out silently |
| Scene | `DENSITY-MECH`'s, verbatim: the **12-station** f-nbr-a scene (A–L), E `Q1AW Q1ABC +05` @ 1150 Hz, F `Q1ABC Q1AW RR73`, all synthetic `Q` callsigns |
| Cells | 14: 9 primary (Δ {6.25, 12, 18.75} × X {1, 3, 6}, E −5) + 3 strong (F +5, E +8) + 2 E+15 (F +12); **N = 100**; all 14 gated (A4) |
| Runs | A and B, one **process** per cell, 30 processes; readings from A |
| ⚠️ Smoke | plumbing was smoke-tested at **N = 2** before the run. Its N=2 "excluded cell" list was seen (noise); the data was deleted |
| Feasibility pilot | control legs only, N = 20, no verdict quantity: found ROW 0e unpassable as written; drove §7 |

## 2. ROW 0 — all silent

| row | check | result |
|---|---|---|
| **0a** | SHA + version on disk and in every run; params SET recorded | ✅ (read-back impossible, stated) |
| **0b** | (i) armed = disarmed, every trial; (ii) run A ≡ run B, byte-identical | ✅ **30/30 JSONL files identical** (`results/stage2_run_hashes.json`) |
| **0c** | pass-1 oracle decodes F where production did, ≥ 0.95, ≥ 50 trials | ✅ **444/444 = 1.000** (pooled; every one of them `pass_F` = 1) |
| **0d** | F alone at −30 dB: `P1_0` ≤ 0.20 | ✅ **0/100** |
| **0e-i** | excluded cells with control F factor ≥ 0.90: `P1_0` ≥ 0.90 | ✅ 7 qualify (the 7 primary excluded cells), all `P1_0` = 1.00 |
| **0e-ii** | `P0_0` ≥ 0.90 in all 14 cells | ✅ 1.00 in all 14 |
| **0f** | ≥ 6 excluded cells | ✅ **9** |
| **0g** *(QA-added, stricter-only, disclosed in the pre-registration)* | no probe status ≠ 0; `supp_n == pass_counts[0]` | ✅ |

## 3. The cell map (run A, N = 100). Read E's factor column first.

| cell | prod | `pass_F`=1 | `P0` | `P1` | `P1_0`† | **E reported SNR** | **E applied factor** | reads |
|---|---:|---:|---:|---:|---:|---:|---:|:--|
| primary Δ6.25 X1 | 0.35 | 35 | 0.00 | 0.35 | 1.00 | −3.6 | **0.930** | *(not excluded)* |
| primary Δ6.25 X3 | 0.00 | 0 | 0.00 | 0.00 | 1.00 | −3.6 | **0.930** | DIRTY |
| primary Δ6.25 X6 | 0.00 | 0 | 0.00 | 0.00 | 1.00 | −3.6 | **0.931** | DIRTY |
| primary Δ12 X1 | 0.15 | 15 | 0.00 | 0.15 | 1.00 | −3.7 | **0.936** | DIRTY (`o1` **0.15**) |
| primary Δ12 X3 | 0.00 | 0 | 0.00 | 0.00 | 1.00 | −3.7 | **0.936** | DIRTY |
| primary Δ12 X6 | 0.00 | 0 | 0.00 | 0.00 | 1.00 | −3.7 | **0.935** | DIRTY |
| primary Δ18.75 X1 | 0.94 | 94 | 0.00 | 0.94 | 1.00 | −3.8 | **0.941** | *(not excluded)* |
| primary Δ18.75 X3 | 0.00 | 0 | 0.00 | 0.00 | 1.00 | −3.8 | **0.941** | DIRTY |
| primary Δ18.75 X6 | 0.00 | 0 | 0.00 | 0.00 | 1.00 | −3.6 | **0.928** | DIRTY |
| **strong Δ6.25** (F+5,E+8) | **0.00** | 0 | 0.00 | **0.00** | 0.00‡ | 8.9 | **0.305** | **DIRTY** ⚑ |
| strong Δ12 | 1.00 | 100 | 0.00 | 1.00 | 0.00‡ | 8.8 | 0.309 | *(not excluded)* |
| strong Δ18.75 | 1.00 | 100 | 0.00 | 1.00 | 0.00‡ | 9.1 | 0.297 | *(not excluded)* |
| **E+15 Δ6.25** (F+12) | **0.00** | 0 | 0.00 | **0.00** | 0.00‡ | 15.4 | **0.000** | **DIRTY** ⚑ |
| E+15 Δ12 | 1.00 | 100 | 0.00 | 1.00 | 0.00‡ | 15.6 | 0.000 | *(not excluded)* |

† `P0_0` = 1.00 in every cell. ‡ **the control is invalid here**: F is self-suppressed (control F factor 0.43 / 0.10),
so `P1_0` = 0.00 is not evidence about the probe (§7.2). ⚑ excluded but control factor < 0.90: still **read** and
flagged, as §7.2 requires; its YES evidence is 0e-ii + 0c.

**Sensitivity of the verdict.** Dropping the two ⚑ cells leaves the 7 primary cells, **all DIRTY**: ROW 1
stands. Dropping E+15 (the 12-cell variant, reporting only) also stands. 🔴 **One cell is near its bar:**
primary Δ12 X1 has `o1` = **0.15**, 0.05 under the DIRTY bar of 0.20 (SE ≈ 0.036, about 1.4 SE). A MIXED there
would make the verdict SPLIT. Run B is a determinism replicate, **not** an independent sample.

## 4. Where the bits are wrong (spec §2.5 item 3, descriptive, gates nothing)

BER of F's data bits from the pass-1 probe, split by whether E's attenuated bins (tone ±1) **overlap** F's tone
bin on that symbol:

| cell | E factor | overlap symbols | no-overlap symbols |
|---|---:|---|---|
| **E+15 Δ6.25** | **0.000** | **0.589** (4950/8400) | **0.000 (0/9000)** |
| **strong Δ6.25** | **0.305** | **0.588** (4941/8400) | **0.000 (0/9000)** |
| primary Δ6.25 X3 / X6 | 0.93 | 0.238 / 0.242 | 0.435 / 0.521 |
| primary Δ12 X1 / X3 / X6 | 0.94 | 0.140 / 0.250 / 0.259 | 0.203 / 0.429 / 0.476 |
| primary Δ18.75 X3 / X6 | 0.93–0.94 | 0.167 / 0.167 | 0.344 / 0.401 |

- **Where suppression is real (factor 0.000, 0.305): collateral.** Errors are confined *exactly* to the overlap
  symbols, and the rest is **perfect**. At Δ = 6.25 Hz, F sits one bin from E, so E's ±1-bin footprint covers
  roughly half of F's tone bins. The attenuation that removes E removes F there too.
- **Where suppression is nil (factor 0.93): residual.** Errors are spread across *both* categories and are
  *larger* off the footprint (0.20–0.52 vs 0.14–0.26). E's energy was never taken out.
- **Pass 1 does its job where it can:** `P0` = 0.00 in all 14 cells, yet `P1` = 1.00 for strong Δ12/18.75 and
  E+15 Δ12. Suppression drops the paired BER by 0.35 (`P0 − P1`) there. The mechanism works, and its limits are
  the two regimes above.

## 5. What this could NOT see

1. **One synthetic 12-station AWGN scene.** Live pairs vary (spec §3.1).
2. **The probe reads at F's true position.** CLEAN would have meant "decodable there", not "pass 1 would rank
   that lattice point". (Moot here: zero CLEAN-type events.)
3. **`o1` = `prod` in every cell.** That is agreement, but it also means the probe adds no information *beyond*
   production's own outcome on **whether** F is recovered. Its value is the **BER map** (§4) and the applied
   factors, which say **why**.
4. **The E −5 dB cells cannot test the ramp's strength**, only its floor. They say what happens when almost
   nothing is removed.
5. **The two informative cells are both Δ = 6.25 Hz, one bin.** The footprint result is established for one bin
   of separation. Δ12/18.75 with real suppression decode 100/100, so it does *not* generalise.
6. **`nhard` 40 here vs 60 in `DENSITY-MECH`:** `prod` rates are not comparable across the two, by design.
7. **No remedy is tested, and no FP price exists.** Two remedies pull in **opposite** directions: strengthening
   suppression near E −5 dB worsens collateral at one-bin separation. H5's June rejection (over-suppression at
   0 dB) is the known failure.

## 6. Status, and the pre-registered next step (§2.6)

- ✅ **Stage 2 complete.** Verdict **ROW 1 DIRTY**, ROW 0 silent, deterministic.
- ➡️ **Pre-registered:** Architect → Captain: a **suppression-route remedy arm** (factor ramp, ±1-bin footprint,
  SNR input), pre-registered with **FP primary**, priced live with `DENSITY-LIVE`'s classifier before anything
  ships. §2.6 says the applied factor decides its shape: *E unsuppressed ⇒ the ramp's floor; fully suppressed
  and still dirty ⇒ the footprint.* **Both regimes are present**, so the arm has two separable questions.
  **That arm is not specified here and needs its own pre-registration and its own Captain go.**
- 🛑 **Nothing merged; nothing pushed** (HK-033 needs the Captain's go for these QA commits).
- Data points for the Architect's ledger (scored by the Architect, not QA): §5 #3 "ROW 1 DIRTY given ROW 0
  silent" (0.40); #4 "ROW 2 CLEAN" (0.20); #5 "ROW 3 SPLIT" (0.40); #6 "E at −5 dB is reported at an SNR giving
  factor ≥ 0.90" (0.60): **E's median applied factor is 0.928–0.941 across the nine E −5 cells**.
- Artefacts: `artefacts/density-p1-stage2/` (gitignored). Committed: the harness, `results/stage2_verdict.json`
  (rates and counts only), `results/stage2_run_hashes.json` (sha256 of the 30 raw JSONL files).

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
