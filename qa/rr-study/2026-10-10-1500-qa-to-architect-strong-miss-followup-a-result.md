# STRONG-MISS follow-up A (desk): what the plausibility filter rejects among real WSJT-X decodes (QA, 2026-10-10)

- **To:** Architect, cc Captain. **From:** QA. **Spec:** `2026-10-10-1400-architect-to-qa-spec-strong-miss-followups-a-b.md` section A (`arch/strong-miss` `0625c6fd`). **Go:** the Captain, in the QA window ("run A").
- **What ran:** the product's own `Ft8Decoder.IsPlausibleMessage` (build `421e3ce2`, by reflection, no grammar store) over every non-`;` WSJT-X row of `20261009_1752`. No decoding. Tool: `qa/rr-study/sub-feas/strongmiss/PlausDesk.cs` (qa/base `ab7e2702`; the compound-half classifier was added after and is in the next commit). Aggregates only, no per-message file; callsign scan of the outputs: clean. Aggregates: `qa/rr-study/results/2026-10-10-strong-miss-followup-A/`.
- **Nature:** descriptive, one night, one chain, new era. The filter is a pure text rule, so every count is an **upper bound** on loss to the filter (it does not show the decoder produced the row). The false-decode side is not measured.

## 1. Validity rows (first)

| row | bar | reading | verdict |
|---|---|---|---|
| **A-V1** matched rows rejected | at most 62 of 62,340 | **0 of 62,340** (CI upper 0.006 %) | PASS |
| **A-V2** of the 504 T targets rejected | at least 70 | **73 of 504** | PASS |
| **A-V3** token-rule counts reproduce `pf_01` | 560 WSJT-X-only (513 / 30 / 12 / 5), 0 matched | I ran `pf_01` itself on the same files: 518 + 30 + 12 = 560 (518 = the 513 + 5 of the "3-token unknown last field" split), 14 `CALL CALL R GRID`, OpenWSFZ rows failing the rules 0. My C# port gives 518 / 30 / 12 and 14, matched 0 | PASS |

Also: the product rejects 0 of 62,617 non-`;` OpenWSFZ rows (the reflection call reads as the live filter). Note the T figure 73 equals step 2's P-FILTER 73 by count only; the populations differ (504 here, 471 there), so it is not the same set of rows.

## 2. Result

| group | non-`;` rows | rejected | share |
|---|---|---|---|
| matched | 62,340 | 0 | 0 % |
| **WSJT-X-only** | 30,978 (293 `;` rows skipped) | **1,805** | **5.83 % [5.57, 6.09]** |

Of the 1,805: **560 by the token-count rules** (518 three-token "unknown last field", 30 four-token non-CQ, 12 five-plus) and **1,245 by the callsign-shape rules** (passing `token_rule()`, rejected by the product).

By form (all 1,805): compound `/` 908, CQ standard 516, hashed 340, other 19, two-call 13, free text 9. By WSJT-X SNR: at most -20 dB 74; -20..-15 218; -15..-10 478; -10..-5 558; -5..0 337; above 0 dB **140**. Shape rules alone: compound 900, hashed 326, other 12, CQ 3, two-call 2, free text 2; SNR 30 / 103 / 299 / 414 / 279 / 120.

Shape-rule rows, failing position (substituting one token with a valid call and asking the product again; positions only): 2-token form, token index 1: 976; 3-token form: token index 1 142, token index 0 111; 2-token token 0: 2; no single substitution fixes it 14. **For 1,217 of the 1,245 the failing token is a compound `PREFIX/CALL` whose part before `/` is at most 3 characters.** Keeping either half alone makes the row plausible in all 1,217. Cause (code, `origin/main` `8256a48f`): `IsCallsignShapeInvalid` (`Ft8Decoder.cs:1056`) splits at `/` (`:1074`) and parses the part BEFORE the slash as the base callsign (`:1083`); a bare prefix such as the country part of `PREFIX/CALL` has no letters after its digit and fails.

Token-rule rows: 513 of the 518 are `CQ <modifier> <call>` with no grid; 14 of the 30 four-token rows are `CALL CALL R GRID`.

Restricted to the 504 T targets: 73 rejected.

## 3. Issue drafts (to review before filing; nothing filed)

All three: "no build requested"; counts are upper bounds on one night (`20261009_1752`, WSJT-X side, shim 20260061 build); the false-decode side is not measured and any fix must weigh it (the rules came from D-009 verification, "OSD CRC-14 false alarms"). Q-prefix examples only.

**Issue 1: compound `PREFIX/CALL` messages are rejected by the callsign-shape rule**
- Rule: `IsCallsignShapeInvalid`, `src/OpenWSFZ.Ft8/Ft8Decoder.cs:1056`, slash split `:1074`, base-call parse `:1083` (`origin/main` `8256a48f`); called for token 0 and 1 of 2- and 3-token messages at `:905` and `:921`.
- Behaviour: a message such as `CQ QA4/Q1ABC` or `Q2ABC QA4/Q1ABC` is dropped, because the part before `/` (`QA4`) is parsed as a base callsign and has no letter suffix.
- Count: up to 1,217 WSJT-X-only rows (of 30,978 non-`;`), 120 of the 1,245 shape rows above 0 dB (all forms, not only this one). SNR spread is the shape-rule one above.
- A compound call with a trailing suffix (`Q1ABC/P`) is not affected.

**Issue 2: `CQ <modifier> <call>` without a grid is rejected as "unknown last field"**
- Rule: the 3-token last-field rule, `Ft8Decoder.cs:984` (return false), after the terminal, report, grid and all-digit exemptions.
- Behaviour: `CQ DX Q1ABC` (valid Type 1 CQ with a blank grid) is dropped; the four-token form `CQ DX Q1ABC FN42` passes (`:927-933`).
- Count: up to 513 WSJT-X-only rows; 17 of the 3-token unknown-last-field rows are above 0 dB.

**Issue 3: `CALL CALL R GRID` four-token messages are rejected**
- Rule: `Ft8Decoder.cs:933` (token 0 must be `CQ`), commented as an OSD false alarm pattern (D-009 R2, Category A).
- Behaviour: `Q1ABC Q2XYZ R FN42` is a valid Type 1 message that ft8_lib renders itself (`native/ft8_lib_vendor/ft8/message.c:952-953`, the `R ` before the grid); the rule drops it.
- Count: up to 14 WSJT-X-only rows (3 above 0 dB). Smallest of the three; keep as its own issue so the false-alarm history can be argued separately.

Not drafted: 5-plus tokens (12 rows) and the 16 other four-token non-CQ rows: free text and hashed forms, not shown to be legitimate Type 1 shapes by this check.

## 4. Predictions scored (QA's reading, for your ledger)

PF1 A-V1 pass: HIT (0). PF2 A-V2 pass: HIT (73). PF3 shape-rule rejections exceed the token-rule 560: HIT (1,245 against 560). PF4 at least one issue: HIT, pending your review.

## 5. Next

Awaiting your review of the three drafts before anything is filed (the Captain's go to file is also needed in my window). B is next: QA's estimate of 1h45 stands, protocol note to be written and committed first.
