# Issue drafts: plausibility-filter rejections of real WSJT-X decodes (QA, approved by the Architect with corrections, NOT filed)

Basis for all three: STRONG-MISS follow-up A, one night (`20261009_1752`), one chain, WSJT-X side. Code references are `origin/main` `8256a48f`, file `src/OpenWSFZ.Ft8/Ft8Decoder.cs`. Counts are rows WSJT-X decoded and the product's own `IsPlausibleMessage` (no grammar store) rejects: an **upper bound**, because it does not show that our decoder produced the row. The false-decode side is not measured. **No build requested.** Examples are synthetic (Q-prefix). Aggregates: `qa/rr-study/results/2026-10-10-strong-miss-followup-A/`; report `qa/rr-study/2026-10-10-1500-qa-to-architect-strong-miss-followup-a-result.md` (qa/base `fdd43a15`).

---

## Issue 1: compound `PREFIX/CALL` messages are rejected by the callsign-shape rule

- **Rule:** `IsCallsignShapeInvalid` (`:1056`) takes the part before `/` as the base callsign (`:1074`, `:1075` `baseCall = token[..slashPos]`) and requires it to parse as a callsign shape (`:1083`). It is called for tokens 0 and 1 of 2- and 3-token messages (`:905`, `:921`). A bare prefix has no letters after its digit and fails.
- **Origin of the rule:** the callsign-structure grammar (change `f-002-callsign-structure-region-lookup`, D9-R3). It is **not** the OSD false-alarm work behind issue 3, so its false-decode side is a separate question.
- **Example (synthetic):** `CQ QA4/Q1ABC` and `Q2ABC QA4/Q1ABC` are dropped. Observation: keeping either half alone (`QA4`, `Q1ABC`) makes the message plausible. A suffix compound such as `Q1ABC/P` is not affected by this path.
- **Count:** up to **1,217** WSJT-X-only rows (of 30,978 non-`;`), 119 of them above 0 dB. By WSJT-X SNR bin: at most -20 dB 24; -20..-15 95; -15..-10 289; -10..-5 411; -5..0 279; above 0 dB 119.
- **Related:** issues 2 and 3 (same study), #225 (DXpedition/contest messages). Found by the STRONG-MISS study.

## Issue 2: `CQ <modifier> <call>` without a grid is rejected as "unknown last field"

- **Rule:** the 3-token last-field check, `:984-985` (`:984` the comment, `:985` the `return false`), reached after the terminal, report, grid and all-digit exemptions.
- **Example (synthetic):** `CQ DX Q1ABC` (valid Type 1 CQ with a blank grid) is dropped; the 4-token form `CQ DX Q1ABC FN42` passes (`:927-934`).
- **Count:** up to **513** WSJT-X-only rows; 17 of the 518 three-token "unknown last field" rows are above 0 dB.
- **Related:** issues 1 and 3, #225. Found by the STRONG-MISS study.

## Issue 3: `CALL CALL R GRID` four-token messages are rejected

- **Rule:** `:933-934` (`:933` the `if` that requires token 0 to be `CQ`, `:934` the `return false`). The code comment at `:930-931` says such messages "are not Type 1 FT8 messages".
- **That comment is contradicted** by ft8_lib's own renderer (`native/ft8_lib_vendor/ft8/message.c:952-953`, the `ir` flag that writes `R ` before the grid) and by WSJT-X, which decoded 14 of them on this night.
- **Example (synthetic):** `Q1ABC Q2XYZ R FN42`.
- **Count:** up to **14** WSJT-X-only rows (3 above 0 dB). The rule's false-alarm evidence (D-009 R2, "OSD CRC-14 false alarms") was gathered before the OSD sign fix (#215, on the station since 2026-10-09 14:01:15Z). Whether those false alarms occur with the corrected OSD is **not known**.
- **Related:** issues 1 and 2, #225. Found by the STRONG-MISS study.
