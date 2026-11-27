# XC-ROUND: subtract the cross-cycle detections, then run one more round

**To:** QA, who turns §2 into one Developer task (HK-015) and runs §3–§4
**From:** Architect, 2026-11-27
**Approved:** Product Owner, 2026-11-27 ("go ahead with the cross-cycle change spec"), after he kept PAYLOAD-FIT.
**Why:** after PAYLOAD-FIT (`qa/rr-study/results/2026-11-26-lc-base/payload-fit-result.md`, QA `13ed8410`), the largest remaining reason a K2 neighbour is never subtracted is **XC**: the neighbour was found by the cross-cycle template stage. That is **27 / 52 / 89** neighbours on S40 / H40 / H20, **51 / 60 / 67 %** of the remaining 53 / 87 / 132. Nothing ever subtracts those signals, so a weak signal beside one is never retried.

**The code (`qa/sprint-r1r4` `f20ae680`, = `main` once PR #300 merges):**

- `Ft8Decoder.cs:1783`: the lean native call asks for the final residual (`WantResidual: xcOn`). It gets back the buffer as of its last subtraction (`ftz_decoder.h:83`, `has_residual`, `ftz_decoder.c:1530`).
- `Ft8Decoder.cs:1875`: **after** the native call has returned, the cross-cycle stage runs in managed code on that residual. It tests the messages published 30, 60 and 90 s earlier as known 79-tone templates (tones from `EncodeMessage` on the text, `:1964`). It publishes its detections as lean batch 3 (`LeanBatchXc`, `:1660`). It only **reads** the buffer.
- The native rounds (`ftz_decoder.c:989`) are over by then, so no round can fit an XC detection.

**The stage is ON at the station:** the build-provenance capture shows `crossCyclePrior` true (board). The replay harness runs it too: batch 3 appears in every SUB-PROBE/PAYLOAD-FIT run. The new round does nothing where the stage is off.

**Process:** the minimal-test rule. One Developer task, unit tests, QA's review (HK-039), **one replay** (§3), numbers reported, **no bars**. The Product Owner decides.

---

## 1. Where it is built

- On `main` after PR #300 (PAYLOAD-FIT) merges, or stacked on `qa/sprint-r1r4` `f20ae680` if it has not merged yet (HK-008).
- **Lean only.** Classic is not touched.

## 2. The change (Developer)

**Design: one extra native call after the cross-cycle stage** ("the XC round"). The native state is not kept alive between calls. Everything the round needs is passed back in.

1. **A new native entry** (name is the Developer's choice; `ftz_xc_round` below) that does **one** subtract-and-retry round, the same as a round 1–3 of `ftz_decode_cycle`:
   - **In:** the normalised capture the cycle decoded (the fit reads its analytic signal, as at `:1035`); the residual returned by the cycle (in/out); for each detection to fit, its **79 tones**, frequency and time; the cycle's remaining budget; the thread count; the same flags as the cycle (tier B / fast, CQ-AP, residual rules, probe).
   - **Does:** fits each detection on the residual and subtracts it, with the same fit, the same sorted-order sum and the same "no valid fit" handling as the rounds. Recomputes the residual's spectrogram. Searches and decodes **only inside the patch windows** `[f − 50, f + 100]` Hz of the signals it subtracted, with the same candidate floor, tiers and accept rules as round 1–3.
   - **Out:** new results, their tiers and the stats (fits, `fitNone`, CPU and wall time per stage) in the existing round-stats form. With the probe on, SUB and CAND rows go out with **round = 4**.
   - **Not started** with less than `FTZ_RESIDUAL_RESERVE_MS` left of the budget (as `:1021`). **Cancelled** on the deadline, all or nothing, as the rounds (`:1052`).
2. **Managed (`DecodeLeanAsync`):** after the cross-cycle stage, if it published at least one detection in batch 3 **and** the residual exists **and** effort is not Fast, call the XC round with the batch-3 detections (live ones only, never the shadow). Publish its new results as **batch 4** through the same `MapLean` (text de-duplication across the whole cycle, plausibility, region, worked-before). ~~Store them in the prior store as an ordinary batch, like batch 2.~~ **Amended 2026-11-27 (Product Owner, after the replay): batch 4 is NOT stored in the prior store** (`MapLean` with `xcBatch: 0`, as batch 3). XC-BUILD's rule is "no chaining", and batch 4 comes straight from batch 3. Storing it made batch-4 decodes into cross-cycle templates 30/60/90 s later: +4 / +21 / +44 rows in batches 1–3, only 4 / 8 / 17 of them matched (`xc-round-result.md`). A unit test shows that a batch-4 decode is not in the prior store. No second replay: the effect is the measured run minus those rows (rate −0.06 / −0.09 / −0.19 pp, ours_only −0 / −0.15 / −0.29 pp). Batch 4 is delivered only when non-empty. The lean log line gets `b4=` and the round's stats (fits, fitNone, decodes, CPU).
3. **Nothing else changes:** rounds 0–3, PAYLOAD-FIT, the step-2e skip rule (the XC round fits every detection, since the native side has no failed-candidate list for them), the cross-cycle stage itself and its thresholds.
4. Shim/version bump as usual.

**Unit tests:**

- (a) **Native:** a synthetic residual with a strong signal S and a weak signal W 10–20 Hz away (the existing modulator test helpers). Called with S's tones and position, the XC round decodes W. Called with no detections, it decodes nothing and leaves the residual unchanged.
- (b) **Determinism:** the XC round's output is the same bytes at 1, 2 and 16 threads.
- (c) **Managed:** with the stage off, with no batch-3 detection, or on Fast, the round is not called (no `b4`). With a detection, batch 4 comes after batch 3, and a text already published earlier in the cycle is not published again.
- (d) Bounds: the existing ASan job covers the new entry.

## 3. The replay (QA): ONE run

- Build: this change on top of PAYLOAD-FIT, harness `-p:HasLean=true`, `libft8.dll` SHA pinned and stated.
- **Exactly the PAYLOAD-FIT arm:** lean, 16 threads, `--lean-probe 1`, LC-BASE's L flags (XC on), S40 / H40 / H20.
- **Baseline: the PAYLOAD-FIT runs already on disk** (Developer `b26a156c`, shim 20260081). No baseline re-run.
- **Free check:** batches 1–3 are byte-identical to the baseline in every cycle (the new round runs after them). If not, stop and tell the Architect. **Note (2026-11-27): as first written, this check contradicted §2.2,** which fed batch 4 to the prior store and so to the next cycles' batch 3. That was an Architect spec defect. In the replay, rounds 0–3 were identical in all 650 cycles, and the replay stands. With §2.2 as amended, the check holds by design, apart from the process-global hash table, which batch 4 still teaches.

## 4. What is reported (aggregates only, the PAYLOAD-FIT result's format)

1. **Table 1:** rate %, ours_only %, deltas in pp, lean minus classic.
2. **Cost:** CPU-s per cycle, `last_p95` ms, abandoned cycles, native errors; per cycle: XC rounds run, fits, `fitNone`, batch-4 decodes.
3. **The XC cases (27 / 52 / 89):** how many now have a round-4 SUB row for N, and how many T are now matched. Also the new never-subtracted split (QA's script, unchanged).
4. **Knock-on:** matched gained outside those cases, and matched lost.
5. **The ours_only check** (`pf_oo_check.py`, unchanged) on the decodes added by this round: repeat share and SNR, against the same two references.

## 5. What happens next

The Product Owner decides keep or drop. The next lever after this is the **K2 decode step itself** (bit metrics / BP). SUB-PROBE found it is where 65–75 % of the crowded misses fail.

## 6. The Architect's expectations (priced before the run; scored in the ledger)

Direct-recovery bound: 27 / 6,773 = **0.40 pp** (S40), 52 / 8,983 = **0.58 pp** (H40), 89 / 9,154 = **0.97 pp** (H20). PAYLOAD-FIT recovered 71–94 % of its bound. **Knock-on, priced this time (the PAYLOAD-FIT lesson):** the round searches every patch it opens, so other weak signals near the XC signals come back too. This is ONE round, not three, so I price knock-on at about the same size as the direct effect, not twice it.

| # | Prediction | P | Class |
|---|---|---:|---|
| XR-1 | S40 rate rises by ≥ 0.30 pp (over PAYLOAD-FIT's 87.79 %) | 0.55 | H |
| XR-2 | H40 rate rises by ≥ 0.50 pp (over 87.24 %) | 0.50 | H |
| XR-3 | H20 rate rises by ≥ 0.80 pp (over 85.24 %) | 0.50 | H |
| XR-4 | ours_only rises by ≤ 0.30 pp on every slice | 0.60 | C |
| XR-5 | CPU-s per cycle rises by ≤ 15 % on every slice | 0.60 | C |
| XR-6 | The free check passes (batches 1–3 byte-identical) | 0.90 | C |
