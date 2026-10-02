# `GAP-LOCATE`: final ruling. **S0 + LB**: the strong misses are not lost after decode and not a candidate-search problem. At the right position, our extraction plus LDPC/OSD cannot decode them

**Architect, 2026-09-27 16:10Z** (`date -u`, HK-017). Branch `arch/gap-locate`. Docs-only;
`git diff --stat origin/main -- src/ native/` is empty. Rules on QA
`qa/rr-study/2026-09-27-1556-qa-to-architect-gap-locate-final-result.md` (`qa/gap-locate` `0b96f758`).
Spec `2026-09-22-1807` + Amendments 1–4 (`75fb9b97`, `04feb5e1`, `8ca12ef0`, `e5a4e023`).

---

## §1. ROW 0: PASS (accepted)

| row | result |
|---|---|
| 0a / 0b / 0d | carried (QA `8c4e617b`). `n_ref` 127,482, `H10` 19.2686 pp, `\|M\|` 24,564, exact |
| **0f** | `v_star` = `(ir 0, igrid4 32373)`, which is the Maidenhead grid value of "RR73". Coverage 122/122, 0 collisions across 50,097 encodable corpus messages |
| **0c′** | fresh K′ (seed 20260927, 0 overlap with old K): **`P_ctrl` = 95.96 %** [94.98, 96.76], n 1,883. Bar 0.90 |
| **0e** | Leg R replay ≥ live in 98.68 % of 5,459 cycles. Bar 0.95 |

## §2. Rows (accepted; the Architect verified them against `final_analysis.json`, HK-018)

| family | statistic | row |
|---|---|---|
| **S** | `s` = 1.71 % [1.17, 2.44]. `CI_lo` 1.17 % < 10 % | **S0**: post-decode loss is not material |
| **L** | `R_F` = 0.377 % [0.283, 0.479] (85 / 22,563). `R_norm` = 0.393 % [0.298, 0.499]. `CI_hi` 0.50 % < 20 % | **LB**: mostly cannot be decoded even at the right place |

**LB robustness (the Architect's bound):** suppose **every** row that option A cannot score was in fact F:
the 1,580 unencodable rows plus the 726 non-standard type-mismatch rows. Then `R_F` = 2,391 / 24,143 = 9.90 %,
and `R_norm` = 10.3 %, still under the 20 % bar. **LB does not depend on the unscored residual.**

**D1 (accounts for `H10`):** S 421 (0.33 pp) + M_unencodable 1,580 (1.24 pp) + F 85 (0.07 pp) + M_nonstd_W3 726
(0.57 pp) + **N 21,752 (17.06 pp)** = 24,564 = 19.27 pp.

## §3. What it means

- Of the 19.27 pp strong-miss pool, **17.06 pp** are signals WSJT-X decodes that our decoder cannot decode
  **even when told exactly where they are**. Only **0.07 pp** would be recovered by a perfect candidate
  stage, and only **0.33 pp** are decoded and then dropped.
- **Ruled out as material:** the managed layer and the seam (`IsPlausibleMessage`, dedup, rendering);
  candidate search, ranking and cap; sync placement (D2: F is only 44 centre / 41 neighbour, all BP).
  🛑 **So there is no candidate-stage arm (LA's route), and no seam-fix arm (S1's route).**
- It confirms THRESH-A's answer (a perfect candidate stage buys nothing), now on **strong, real** signals,
  across every SNR band: N is 1,347 rows even at ≥ +10 dB (D3). It gets worse with cycle load (D4, N by
  quintile 1→5: 1,493 → 8,124).
- D5, descriptive: 1,150 M rows yield a CRC-valid, **same-type, different** message at WSJT-X's position.
  So another transmission dominates that cell. That fits interference-limited loss, and LIVE-GAP-MAP's D7
  (7.5 pp next to a stronger signal). **Not gated; not an attribution.**

## §4. Routing: the Captain's decision (spec §4, LB)

The known remedies for interference-limited extraction are **closed** in the standing record:
subtract-and-resynthesise **DEAD** (three builds, three reverts), the OSR 2→4 change barred on existing
evidence, spectral locality **RETIRED**, DENSITY **PARKED** (suppression family closed). 🛑 This ruling
re-opens none of them. An L-row routes a question, not a build.

**Architect's recommendation:** **close GAP-LOCATE**, and close the LIVE-GAP-MAP localisation line with it. The
question "where are the strong misses lost?" now has its answer, and no cheap lever exists on that answer.
Any further decode-rate work in this territory would be a new, Captain-initiated line against a parked or
closed family, not a continuation of this one.

## §5. Side findings (recorded, no action from this arm)

1. **`_forced_success` bit-compare vs the on-air `RR73` convention.** On-air `RR73` is sent as grid value
   32373. OpenWSFZ's encoder uses `MAXGRID4+3`. **Earlier arms are unaffected** (HK-022 check): THRESH-A and
   F-NBR-A forced-decode **synthetic** audio rendered by our own encoder (`scene_render`), so their
   bit-compare is self-consistent. Endurance and R&R are unaffected, because they match by text, and both
   forms render as "RR73" in both decoders (board, 2026-09-27). Any future forced-decode arm on **real**
   audio must use Amendment 4's comparator or better.
2. **Issue #192** (`TryParseResponder` takes `RR73`/`RRR` as a grid): filed, and separate.
3. **QA's self-reported HK-037 slip** (Leg R first persisted `ts|message` keys to a gitignored JSON): caught,
   fixed and remapped by QA. The Architect scanned all 12 artefact JSONs and found **0** text-like strings.
   Accepted, with credit for surfacing it rather than sweeping it.

## §6. Ledger (scored at ruling time)

- Spec §6: G-1 **FALSE** (already scored) · G-2 S1 0.20 **FALSE** · G-3 LA 0.25 **FALSE** · **G-4 LB 0.25 TRUE**
  · G-5 LC 0.45 **FALSE** (the modal call was wrong) · G-6 **FALSE** (already scored).
- Amendment 4: GA-1 0f 0.85 **TRUE** · GA-2 0c′ 0.75 **TRUE** · GA-3 0e 0.75 **TRUE**.
- The LA ("findable localised defect") call was deliberately priced below modal, and it was false. The
  Architect's modal call (LC, mixed) was also wrong. The outcome was the less comfortable one.
