# OSD-FIX PEEK-100: fix ON vs OFF on 100 cycles, second pass included (pre-registered, descriptive)

- **From:** Architect. **To:** QA. cc Captain. **Date:** 2026-10-08 17:15Z (by `date -u`, HK-017).
- **Asked for by:** the Captain, in the Architect's window: *"can we do a short test with the fix on and including the second pass, like 100 cycles. before TRAIN?"*
- **Status:** written **before** any fix-ON product-pipeline decode exists. Nobody has seen a switch-1 Replay81 output. Descriptive only: **no bar, no verdict**, and nothing in the OSD-FIX spec (`2026-10-07-1545`), its rulings (`2026-10-08-1545`, `-1630`), the TRAIN grid, the `n*` rule or the TEST rows changes because of what this shows.
- **Needs:** the Captain's go **in QA's window** (PC only, about 13 min; a relayed go is not a go).

## 1. Why this is cheap and paired

QA's A-OFF part 2 (`bb4fd256`, `aoff_part2.json`) already ran the full product pipeline on these exact cycles with the fix **OFF**: Replay81 `two1`, subtraction ON, threads 8, Test B, `nhard` 40, `--osd-sign-fix 0`, final DLL `2029b080…82bb`, the first 100 cycles of NHARD-REP SAMPLE in its own order, outputs in `artefacts/rr_2026-10-08_osd_fix/aoff2/`. That run is **REF** here. It is not re-run.

**FIX40** is the same command with **one change**: `--osd-sign-fix 1`. Same DLL, same selection file (`aoff2_selection.json`), same order, same warm-up, same Test B rule. Outputs go to `artefacts/rr_2026-10-08_osd_fix/peek_fix40/`.

These 100 cycles are residue 0, inside TRAIN. **TEST cycles are not touched.**

## 2. Validity (each must hold, or the rows are withheld and named)

| row | predicate |
|---|---|
| PV1 | harness rc 0 |
| PV2 | `libft8.dll` SHA-256 at start = at end = `2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb` |
| PV3 | every `# readback` line in the log contains `osdSignFixSet=1 osdSignFixRead=1` (at least 2 lines) |
| PV4 | cycles with residual work abandoned ≤ 5 % (spec V6), in FIX40 **and** in REF |
| PV5 | blind-instrument check: if FIX40's per-cycle batch-1 and batch-2 multisets equal REF's in **all 100** cycles, report "switch not applied", not a reading. (A-OFF part 1 showed 48/100 cycles differ in the first pass alone, so this should not fire.) |

## 3. Rows (descriptive, all mandatory, no bar)

Same match rule and the same NET/CI method as the NHARD-REP report (Test B confirmed decodes, as pp of WSJT-X's decodes on these cycles, 95 % cycle-bootstrap CI).

| row | what |
|---|---|
| PK1 | NET (FIX40 − REF), all batches, with CI; plus K (confirmed decodes FIX40 gains) and G (confirmed decodes FIX40 loses) |
| PK2 | NET **batch 1 only** and **batch 2 only**, each with CI |
| PK3 | batch-1 **not-confirmed** decodes per cycle, REF vs FIX40 |
| PK4 | batch-2 **confirmed** decodes per cycle, REF vs FIX40 |
| PK5 | R6 diagnostics, aggregates only: OSD accepts per cycle by batch, and the distribution of `nhard` on accepts (median, p90), REF vs FIX40 |
| PK6 | total and batch-1 decode wall time per cycle (median, p95), REF vs FIX40 |

**Reading the Captain's mechanism (descriptive):** it predicts PK3 falls **and** PK4 rises together. Report both numbers side by side. Do not call it confirmed or refuted on 100 cycles.

## 4. What 100 cycles can and cannot see (HK-038: where the number comes from)

NHARD-REP's NET on 311 cycles of the same night had a CI half-width of about 0.19 pp ([−0.79, −0.41]). Scaled to 100 cycles (×√3.11), expect about **±0.34 pp**. So this peek can see a second-pass effect **as large as** NHARD-REP's 60-vs-40 batch-2 loss (−0.53 pp). It **cannot** see an effect of the size every corrected-OSD figure on file has shown (≤ 0.05 pp). A CI that includes zero means "not large", not "none".

## 5. Guards

- 🛑 Not citable as an OSD-FIX result or verdict. Label it **PEEK-100** wherever it appears.
- 🛑 `nhard` 40 was calibrated on the inverted OSD. FIX40 is one grid point, not the right setting for the corrected OSD. TRAIN chooses that.
- 🛑 No grid value, bar, rule or TRAIN/TEST selection changes because of this. If the Architect wants to change anything after seeing it, that is a new amendment, marked as post-data.
- HK-037: ALL.TXT stays inside the matching function. Every output is numeric.
- Run folder copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\` as the last step.

## 6. Blind expectation (Architect, before data; scored when QA reports)

| # | prediction | P |
|---|---|---:|
| PK-a | PK1's CI includes 0 | 0.70 |
| PK-b | PK3 (batch-1 not-confirmed per cycle) is lower in FIX40 than in REF | 0.60 |
| PK-c | PK2 batch-2 NET point estimate > 0 | 0.50 |

⚠️ My calls lean toward the tidy mechanism (CW3), so PK-c is held at a coin flip.
