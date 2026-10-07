# RULING — `FIELD-ID` (Amendment 8): **E-RESIDUAL**, accepted. The pointer is strong: 795 of 917 "unexplained" outputs are non-standard-call messages (`i3` = 4) where the truth was packed standard (`i3` = 1)

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-07 12:54Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA report `report_field.md` (local `qa/coh-gain`, not pushed; row list `75fbdfee`, committed before re-extraction); numeric file `artefacts/rr_2026-10-07_coh_gain_fieldid/field_rows.csv` (numbers only, HK-037).
- **Against:** spec §17 + notes 1 (`93176a0f`) and 2 (`4b1809eb`).

## 1. Verdict: E-RESIDUAL, accepted

`E` = (E-ADJ + E-QSO) / 917 = **33 / 917 = 3.6 % [2.4, 5.0]**. `CI_hi` < 0.50 ⇒ **E-RESIDUAL**. All validity rows pass: X1 1,132 / 1,132, X2 0 / 215, X3 0 failures. **E-ENC = 0 by construction (note 2); hypothesis (i) was NOT TESTED by this amendment.**

**Recounted myself from `field_rows.csv`:** X rows 917: `adj` ≠ none **0**, same two calls **33**, G returned the same message (`g2`) **324**, W1 917 / 917, X3 917 / 917. OSD rows 215: none in E-ADJ / E-QSO. **`i3x` = 4 on 795 of 917 X rows (86.7 %) vs 19 of 215 OSD chance rows (8.8 %, ≈ 1/8, the chance rate for a 3-bit field).**

## 2. What it says (descriptive, post-hoc)

- **(ii) another period's message is ruled out:** `adj` = none on all 917.
- **(iii) the same QSO, different message, is small:** 33.
- **The pointer to (i) is about as strong as a descriptive table gets.** Unrelated outputs land on `i3` = 4 about 1 time in 8. These land there 87 % of the time, while the truth re-encoded from WSJT-X's text is `i3` = 1 on every one. That is what you would see if the station transmitted a **non-standard-call message** (type 4: one full callsign of up to 11 characters plus a 12-bit hash of the other), and our encoder, given WSJT-X's displayed text, packed it as a **standard** message. If so, **both extractors decoded the right message and the truth was wrong.** 🛑 It is a pointer, not a finding, until it is tested (§3).
- **If (i) holds, what changes (not re-read here):** WRONG-ID's 912 and Q-GATE's 0.178 shrink by up to about 795 / 917. The ungated fallback's unexplained rate would be about 0.06 per cycle rather than 0.42. The fallback's gain (+5.25 pp) is **not** affected: a row with a wrong truth can never count as RIGHT. 🛑 **WRONG-ID's W-FALSE and Q-GATE's GATE-OPEN stand as ruled. Neither is re-read with a corrected truth** (standing prohibition). A corrected truth applies to the **next** measurement.
- **Wider scope, if (i) holds:** every offline arm that builds its truth by re-encoding WSJT-X's text with the vendored encoder (COH-GAIN, GAP-LOCATE, the `leg_fk2.py` family) mis-scores non-standard-call messages. Test B matches by **text**, so the live comparisons and NHARD-REP / OSD-OFF are not affected by this.

## 3. The test: `ENC-ID` (spec §18, DRAFT, needs the Captain's go)

It needs **no new DLL or build.** The type-4 layout is public, and the vendored MIT `ft8_lib` (`native/ft8_lib_vendor/ft8/message.c`: `ftx_message_decode_nonstd`, `save_callsign`, the `47055833459` hash constant) gives the field positions and the 12-bit hash. A Python port of those few lines (MIT, licence-clean) runs inside the reading function. Spec §18.

## 4. Predictions

CF1 (X1) ✅ HIT; CF2 (X2) ✅ HIT; **CF3 E-EXPLAINED 0.40 ❌ MISS** (E-RESIDUAL; the class most likely to explain them could not fire, note 2); CF4 void.
