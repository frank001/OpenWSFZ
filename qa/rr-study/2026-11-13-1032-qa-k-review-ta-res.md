# TA-RES (angle A, Stage 1, route R): QA (k) review. ACCEPT WITH FOUR AMENDMENTS; the rows are reachable, but the control for the new domain is missing.

**Written:** 2026-11-13, `date -u` read 10:31:22Z. **To:** Architect. **Spec:** `arch/accept-gate` `cae3015c` (`2026-11-13-1029-architect-to-qa-spec-ta-res.md`). Nothing built, nothing run on the PC, nothing frozen. Evidence below is source reading (the v2 tree `59eb5a8f`, `StageProbe.cs`) and counts already on disk.

## 1. HK-027: what the spec rests on, checked

| item | state |
|---|---|
| groups, pilot list, calibration | present: `_qa-scratch\ta-check\frozen\tc_groups.json`, `ta-mask\frozen\tm_pilot_rows.json`, `tc_calib.json` (0.48 s); the acceptance rows B1 986, B1m 506, T 506, T_bur 237, T_iso 269 are reproducible from them (TA-MASK used exactly these) |
| capture on today's stack | R0: builds, smoke identical to arm B on 3 cycles |
| the merge order (provenance) | read in `CohFallbackAudioSelector.Merge` (`Subfeas\CohFallbackAudioSelector.cs:130-163`): where both the residual run and the original run found a payload, **the residual run's rows are kept**; an original row enters only for a payload the residual run did not find; sorted by candidate position, residual before original. **v2's third run does not enter `Merge`** (it goes through `ThirdRunCandidates`, `:91-96`, then the selector with its seen-guard). So "first in merge order" = residual run, then original-only, then third-run-only; `FromOriginal` / `FromResidual` / `InBoth` are already counted by the product and give the multi-source count |
| what the harness can see | `StageProbeInterop.Record` sees every `CohFallbackRun` result per call in call order (`Runs.Count`), with each row's payload and state; the `--stage-dump` `U` lines map payload to text (unpack). So a published batch-4 row can be tied to a run by payload with no `src/` change: feasible, about 1 h with a self-test, as estimated |
| a row's `Provenance` field | it is the **candidate set** (V3 / C1 / J2 / J3 / N1, `CohFallbackTypes.cs:24-28`), **not the run**; the harness change must not use it |

## 2. Findings and amendments

**K1 (required): a positive control on the residual buffers.**
- **The gap (HK-026: the instrument's response where the change lands).** A-KEEP scores B1 and B1m on **O**, so it cannot show that the tone test still reads a real signal on **R2, R3 and X3**, which is where R is new. B1 rows are, moreover, the signals that were subtracted to make R2 and R3.
- **Both branches:** if subtraction or the fits had thinned real signals in those buffers, A-SEE could pass partly on a threshold T_R tuned by nulls while real rows read present less often, and nothing in the table would show it; if they had not, T_iso reads ≈ 1.0 as it does on O (0.993).
- **Amendment:** **T_iso is the natural control** (same batches 4 and 5, same source buffers, not buried). Add to A-KEEP: **CI_lo(PR_R(T_iso)) ≥ 0.80, fails ⇒ VOID.** The bar is the instrument's own (0.80); T_iso on O read 0.993 [0.981, 1.000] (TA-CHECK), so the row can fail only if the repair breaks the test.

**K2 (required): define "subtracted before the source buffer" as code from the capture.**
- From the product chain (read in `sc_refit.py` `product()` and `Ft8Decoder.cs:1055-1091`): R2 = O minus the fits of batch-1 natives; R3 = R2 minus the batch-2 natives; X3 = (R3, or R2 when the third pass did not run) minus the fits of the published batch-3 and batch-4 natives. Only **re-encodable** natives are fitted (no `<`, at least 3 tokens, `EncodeMessage` accepts).
- Frozen rule (proposed): a T_bur row's strongest neighbour N (the TA-CHECK predicate) is **subtracted before the row's source buffer S** iff N is matched to one of our decodes of batch b whose native is re-encodable and **b ≤ 1 for S ∈ {R2, R3, X3}; b ≤ 2 for S ∈ {R3, X3}; b ≤ 4 for S = X3**; for S = O, never. The matching is `rebuild_matching` on the capture's `nc.tsv` (inside the function, HK-037). The pilot reports the eligible count.

**K3 (required): A-RESIDUE needs a floor on n, and a stratum.**
- With zero events and the bootstrap, CI_hi = 0 whatever n is, so a small eligible set would pass "CI_hi ≤ 0.05" without establishing it. By the rule of three, 0 events in n rows bounds the rate at 3 / n, which is ≤ 0.05 only for **n ≥ 60**.
- **Amendment:** **V-N2: n(A-RESIDUE eligible) ≥ 60**, else A-RESIDUE is **unreadable** and the result goes to the Captain as such (it is neither a pass nor a fail). Source: the rule-of-three arithmetic, not a data figure.
- Report A-RESIDUE also **within ΔSNR ≥ 20 dB**, as TA-MASK did, because a neighbour that strong is exactly the case where an imperfect fit leaves a residue comparable to the row.
- **The bar (CI_hi ≤ 0.05):** no data behind it, as the spec says. I accept it for the pilot; I will challenge it if the pilot's rate is above 0.02 (the TA-MASK precedent).

**K4 (a stated limit and one cheap check).**
- A-GHOST under R is **non-inferior by construction** when the neighbour copy sits on a buffer that is O (identical audio, same test) and drops when the neighbour was subtracted; it guards credulity on un-subtracted neighbours only. A-RESIDUE is the row for subtracted ones. Stated, not changed.
- **Add a descriptive check V-O:** the captured O buffer (the normalised original) against the WAV-derived PCM TA-CHECK scored: the tone share is scale-free, so the same row must read the same share; report the maximum difference of shares over a sample of 200 B1 rows. It costs minutes and rules out a normalisation surprise.

## 3. What else I checked and found sound

- **V-REPRO** (≥ 98 % of cycles identical in matched rows and batch): R0 saw 3 of 3; arm B had 0 abandons, so a repeat at the same settings should reproduce. A cycle that differs excludes its rows (counted).
- **T_R with each null on the row's own source buffer:** the right design (the lesson of TA-MASK's pooled threshold).
- **Reusing TA-MASK's 60 pilot rows as TA-RES's pilot:** acceptable; they were seen by TA-MASK's own scoring but not by R, and the exclusion list stays the same so the two stages compare row for row.
- **The score at WSJT-X's position with the frozen calibration:** the calibration is time-base only, so it carries to R2, R3 and X3.

## 4. Cost

Provenance harness change ≈ 1 h; V-REPRO and V-PROV ≈ 0.5 h; the scorer (source buffer per row, null on it, the subtracted-neighbour mapping, V-O) ≈ 1.5 h; self-test with mutations ≈ 1 h; pilot, freeze, run, report ≈ 1 h: **≈ 5 h**, over the 4 h line, as you say. The PC window is the capture replay only (≈ 45–60 min). Everything after is desk work and not PC-exclusive.

## 5. Verdict

**ACCEPT WITH FOUR AMENDMENTS** (K1 and K2 and K3 required; K4 stated plus one descriptive). Nothing is built before the Captain's decision on the extra hour and the window. No closed ruling is re-read.
