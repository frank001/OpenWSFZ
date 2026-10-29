# GAP-RESIDUAL: QA (k) review of the spec (nothing was run)

**To:** Architect · **From:** QA · **Date:** 2026-10-29T16:27:57Z (`date -u`)
**Spec reviewed:** `qa/rr-study/2026-10-29-1622-architect-to-qa-spec-gap-residual.md`, commit `74a38158` on `arch/gap-residual`, read with `git show`.
**Code read (on `origin/main` `c2c85c45`):** `CohFallbackAudioSelector.cs`, `Ft8Decoder.cs:1050-1082` and `:668-685`, `SubtractionPass.cs` (`ThirdPassResult`, the residual build and `DecodeAll`), `Ft8LibInterop.CohFallbackMakePlan`, `CohFallbackTypes.cs`; Replay81 `StageProbe.cs` and `Program.cs`.

## Verdict

**APPROVE WITH FIVE REQUIRED AMENDMENTS (A1 to A5).** The design is sound and the correction in §0 is right: the capture is a `qa/` change to the Replay81 wrapper and needs no Developer round. `StageProbeInterop` already forwards `DecodeAll` and `CohFallbackRun`, and the selector, the residual pass and the third pass each hand the decoder's own arrays to the interop (`report.Residual` is the array that was decoded and is never pooled; the third pass works on a copy). Rows 0a, 0b, 0c and 0f are real validity checks. Rows 0d and 0e need the changes below, and the routing sentences need A3 to A5, before I would run.

## Your four questions

1. **0c(ii) and 0c(iii): cheap, yes.**
   - (ii) is a byte compare of arrays the wrapper already holds: `F` against `R3`, `R2` and `O`. The level the selector implies comes from outcomes the harness already writes (`--third-out`: outcome, fitted) and from the residual-pass line (abandoned, contained exception, fitted = 0). I would also assert that the **second** `CohFallbackRun` of a `Both` cycle reads `O`. About half an hour on top of the capture.
   - (iii) is a second `DecodeAll(R2)` in the same process. The risk is the process-global callsign hash table, which can change what a later decode accepts. See A2.
   - 0c(i): I will state the expected call count per cycle from the logged outcomes after reading `RunCore`. A third pass that ends `skipped-no-new` may still call `DecodeAll` on an unchanged copy, so "`R3` exactly where the outcome is `Ran`" may not equal "a third `DecodeAll` call exists". The count rule will list `ran`, `skipped-no-new`, `abandoned` and `failed` separately.
2. **0e: cheap, and it can be made stronger.** The legs on 40 pilot cycles take minutes. First compare `O` byte for byte with the PCM `gr_forced.py` used for GAP-RELOCATE (A5). If they are identical in 400 of 400 cycles, the class agreement is 1.000 by construction and 0e becomes a confirmation. The bar of 0.98 stays.
3. **0d control size: enough for the pooled figure, not for the part that matters.** About 376 non-pilot rows gives a standard error near 1.5 pp at 0.96. The residual-only fallback stratum is 92 rows (standard error about 3 pp at 0.90) and some bands will fall below 50. See A1.
4. **D6-R: parseable in `qa/` code with no export.** `Ft8LibInterop.CohFallbackMakePlan(snapshot)` (reachable under `HasInternals`) returns the eligible candidates with `FreqHz` and `DtS` from the snapshot bytes. I do not need to parse the byte layout myself. The spec lacks the **window**: see A3.

## Required amendments

**A1. 0d must be judged per tag, and its blind spot bounded (HK-021(k), HK-026).**
- Batch-2 control rows are close to tautological. The forced primary on `R2` at the cell where the product decoded the row will find it. A pooled bar of 0.90 can therefore pass while the stratum that resembles N's weakness (residual-only fallback, n 92) is poor. For example, 76 % at 1.00 plus 24 % at 0.60 pools to 0.90.
- **Required:** bar 0.90 on each of (batch 2 or 3 rows) and (residual-only fallback rows), reported with n and with the Wilson interval. A stratum below the bar makes every N row "not reachable not established" for that buffer type.
- **Required:** the same rule for REF-SNR terciles. The control rows are product decodes and so sit above the product's threshold, while N lives at and below it. Report the SNR range of the control rows beside the N rows' range. A tercile with n >= 50 and `P_ctrl,R` < 0.80 marks NR in that tercile "not established" (the band rule, applied to SNR).
- **Required:** R-NR is computed with the "not established" strata removed from NR, shown as a separate count. Otherwise R-NR can fire on rows the instrument is blind to.

**A2. 0c(iii) compares fields that do not depend on the hash table, as code.** Compare freq, dt, payload bytes, SNR and counts, never rendered text (outcome fields, as the standing rule says). Save the hash state at the capture point (`HashStateSave`) and restore it before the offline rerun. The bar stays exact and gets no escape hatch: a mismatch voids the section and is reported.

**A3. D6-R: state the window and its source (HK-038).** "Within the fallback's own search window" has no number. Give it, with its source line in `ft8_shim.c`, or let me read it from the native source and assert it in code. If it is not a single constant, report "offered" at two windows (the native one and GAP-RELOCATE's frozen δ). "Offered" means a candidate in the plan's eligible set (`CohFallbackMakePlan`); an ineligible candidate counts as never offered.

**A4. Split RP into "native decoded it" and "native did not".** The wrapper holds each `DecodeAll` return array. An RP row whose payload is already in the captured native result for `R2` or `R3` was decoded by the product's search and then lost afterwards (dedup, plausibility filter, hash handling). It is not a candidate-search or sync-placement miss, which is what the R-RP sentence says. Report `RP-native` and `RP-search` separately, and word R-RP's route on `RP-search` only. It costs nothing: the arrays are already captured.

**A5. 0e order.** Compare the captured `O` with `gr_forced.py`'s PCM byte for byte first (400 of 400). Run the class agreement (>= 0.98) on the pilot as confirmation. If the PCM is identical, say so, and 0e is recorded as implied.

## Other findings (no change required unless you disagree)

- **0b.** Run the OFF arm as **one process, in GAP-RELOCATE's cycle order**, because the hash table carries across cycles (ledger Q27 was a reference arm that was not one process). Exact equality is the right bar.
- **0f.** The capture adds about two megabytes of copying per cycle, which is negligible. The guard against the station daemon is right.
- **R-NR.** It stays a question to the Captain, and the spec already says it is not a floor. I accept it as routing, not as a gate, on that basis.
- **D4-R.** The load-quintile NR rate is descriptive only. It must not be quoted as a DENSITY result (that family is closed).
- **Multiplicity.** No adjustment, as the spec says. Say so in the report.
- **Cost.** The estimate is plausible. My additions (A1 strata, A2 hash state, A4 split) are post-processing on captured data and add little time.

## What I need from you

Confirm A1 to A5 in the spec (or tell me which you decline and why). Then the Captain's run go. I will not run anything before it. HK-039 does not apply (`qa/` only, no `src/` or `native/` change), and the review record for the Replay81 extension will be this file plus the commit that adds it.
