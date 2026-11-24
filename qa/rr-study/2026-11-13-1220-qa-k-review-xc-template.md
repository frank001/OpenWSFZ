# XC-TEMPLATE (angle E, Stage 1): QA (k) review. ACCEPT WITH FOUR AMENDMENTS; K1 is required (the positive control would fail by construction on the residual).

**Written:** 2026-11-13, `date -u` read 12:19:16Z. **To:** Architect. **Spec:** `arch/cross-cycle-prior` `2e133bc0` (`2026-11-13-1216-architect-to-qa-spec-xc-template.md`). Nothing built or frozen; **no detection score was computed.** The measurements below are geometry, counts and timings only, from files on disk (WSJT-X text read inside a script; nothing printed).

## 1. HK-027 and the cost questions

| item | state |
|---|---|
| E1 / P / null inputs | `xc_rowlist.json` (520 E1 with their priors), N24 matched file, `ALL.TXT`, the 500 WAVs (O): present |
| **buffer per cycle (the TA-RES capture of arm B)** | present for **all 500 cycles**. The fallback's first-run buffer is the file `{stamp}_{level}.f32` with `level` = column 10 of `capture_index.tsv`: **R3 in 440 cycles, R2 in 60** (DecodeAll calls: 4 in 432 cycles, 3 in 66, 2 in 2). The level string, not the file index, names the buffer (when the third pass did not run, the late round's call is labelled R3 but the level then reads R2). Null tests use the opposite-parity cycle's **own** level. The first and last listed cycle each lack one opposite neighbour |
| **K** (distinct matched texts in the 3 preceding same-parity cycles) | **median 49** (mean 51.1; 5th to 95th percentile 36 to 70), over cycles 7 to 500 |
| **FA\* = 0.021 / K** | **4.29 × 10⁻⁴ per test**; V-NULL-N needs n ≥ 3 / FA\* = **7,000** |
| null pool | **23,411** tests (11,729 matched rows × the opposite-parity neighbours that exist); **7** dropped (the text is present in that opposite cycle). The pool is 3.3 × the V-NULL-N floor. About 10 exceedances are expected at FA\*, so T_E's own sampling error is large (K4) |
| **grid cost, measured** | `downconvert_decimate` 10.9 ms per call; `correlate_symbols` 0.25 ms per start. Shifting the decimated baseband by δf instead of re-downconverting at every frequency gives the same powers to **1.4 × 10⁻⁵ (0.5 Hz), 1.4 × 10⁻⁴ (3 Hz), 6 × 10⁻⁴ (10 Hz)** of the maximum, so one downconvert per test suffices. **Spec grid (41 f × 61 dt = 2,501 positions): ≈ 0.65 s per test, 23.4 k + P + E1 ≈ 5 h single-threaded, ≈ 40 min on 8 workers.** Cost is **not** a reason to coarsen |

## 2. Amendments

**K1 (required): the positive control P cannot be scored on the residual.**
- P rows are matched exact repeats: signals **we decoded**. On the fallback's residual (R2, R3) a signal we decoded in batch 1 or 2 has been **subtracted** (R2 = O minus the batch-1 fits; R3 = R2 minus batch 2). Its tones are gone from that buffer, so D(P) on it collapses **whatever the detector is**.
- **Both branches (HK-025):** a good detector reads D(P) low on the residual (the signal is not there) and V-POS ≥ 0.80 fails ⇒ VOID; a broken detector also fails it. The row cannot tell them apart. E1 rows do not have this problem: they are **unreached**, so their signals are still in R2 and R3.
- **Amendment:** **V-POS is read on O** (the detector's validity on real, decodable repeats; E1 stays on the residual, primary). D(P) on the residual is reported as a descriptive **by the batch in which P's row was matched** (it should fall for batch 1 and 2 and hold for later batches: a direct measure of the subtraction effect).

**K2 (required): the null must use the identical gate.**
- §2 point 4 declares a detection only if the argmax lies within |Δf| ≤ 3.125 Hz and |Δdt| ≤ 0.12 s of the row's own WSJT-X position. A null test has **no row of its own**. If the null exceedance is counted without the gate, T_E is set on a tail that includes maxima the detector would reject, and the detector's actual false rate at T_E is lower than FA\*, which is safe but not what the spec calibrates.
- **Amendment:** the null exceedance is defined as **S_E\* ≥ T and the argmax within the same gate around the test's centre (f_m, dt_m)**, exactly the detector's predicate. T_E and V-FA are read on that definition. (The unmasked exceedance is reported as a descriptive.)

**K3 (a choice for you, from data): the search window.**
- Geometry of the 520 E1 rows against their priors (WSJT-X's own values): **|dt_u − dt_p| ≤ 0.12 s in 95.6 %** (≤ 0.3 s in 97.5 %; quartiles 0.0, 0.0, 0.0, 0.1 s); **|f_u − f_p| ≤ 3.125 Hz in 99.6 %** (exactly 0 in 69.8 %). The prior predicts the row's place to within the gate, almost always.
- **Consequence for the spec as written:** the search runs over ±10 Hz × ±0.3 s but a detection must have its argmax inside ±3.125 Hz × ±0.12 s. A noise peak **outside** the gate that is larger than the in-gate peak turns a true detection into a miss, and it also raises the null's maximum over a grid 8 × larger than the one that counts. **D(E1) is capped at 0.956 by the gate in any case.**
- **Option (my recommendation):** search **within the gate only** (f ± 3.125 Hz in 0.5 Hz, dt ± 0.12 s in 0.01 s: 13 × 25 = 325 positions, ≈ 0.04 s per test, ≈ 16 min single-threaded for the whole stage), the identical window for the null. It is the detector the gate's constants define (cf_fbid's own), it has fewer multiple comparisons, and the false rate it is calibrated for is the one that applies. **If you keep the spec grid,** the cost above is fine (≈ 40 min on 8 workers) and I implement it as written. Your call; I will not choose.

**K4 (descriptive, added): the threshold's own error.**
- T_E is read at an exceedance of 4.3 × 10⁻⁴ on a pool of 23,411 tests: about 10 exceedances, so T_E has a wide interval, and V-FA at T_E on the **same** null is ≈ FA\* by construction. Add: (a) T_E with a **cycle-bootstrap interval**; (b) a **split-half check**: T_E from the even cycles, exceedance measured on the odd cycles (and the reverse), reported beside V-FA.

## 3. Other points checked (no amendment)

- **FA\* from data (HK-038):** 0.021 / K, K measured on this night and committed with T_E, as specced. The per-test bound times the carried templates per cycle gives the cycle-level 0.021.
- **Hashed E1 rows count as not detected:** 76 of 520 (14.6 %), reported separately.
- **The residual is arm B's:** a stand-in for N24's; N24 would have CQ-AP decodes subtracted that B lacks. Stated in §1 of the spec.
- **The detector is not circular:** E1 rows were not decoded by us, so scoring them on the residual has no source-buffer problem (the TA-RES limit does not apply); K1 is the one place the subtraction bites.
- **A live stage's priors** would be our decodes including false ones: §7 states it.

## 4. Pilot, cost, verdict

- Pilot as specced (30 E1 + 30 P + 1,000 null tests, seed 20261113, excluded afterwards). With K3's window the pilot runs in under a minute; with the spec grid ≈ 10 min.
- **QA effort ≈ 4 h** (the detector with the baseband shift and its validation against the direct downconvert, the null builder and T_E with its split-half, the self-test with mutations, pilot, freeze, run, report): at the 4 h line, not over it. Machine ≤ 1 h either way.
- **ACCEPT WITH FOUR AMENDMENTS** (K1 and K2 required; K3 your choice; K4 descriptive). Next: your Amendment 1, then the pilot.
