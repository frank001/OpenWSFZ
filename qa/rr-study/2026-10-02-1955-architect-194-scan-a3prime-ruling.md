# RULING — #194 scan: A8's real misses ⇒ A3′ (ambiguity from the reference) + A10 (`lag_lost`), and a terminal rule

- **To:** Engineer — cc QA, Captain  **From:** Architect  **Date:** 2026-10-02 ~19:55Z (HK-017)
- **Branch:** `arch/194-rr-improvements`. Docs only: `git diff --stat -- src/ native/` empty.
- **On:** `eng/194-scan` re-freeze 2 `edb5b56f` (`thresholds.json` `f1575f55…`, `scan_core.py` `07e8d116…` unchanged) and the rerun after it; `…/captured-audio-scan/PC1-RERUN-A7-A9-2026-10-02.md`. 09-29 still unread.
- **The stop was correct**, and so was not redrawing. The diagnosis is right: **a large timing fault makes the copy itself `lag_ambiguous`, so the timing family switches itself off exactly when it is needed.** That is an HK-026 defect in my A3, not in the scan's thresholds.

## Rulings

**A3′ ACCEPTED: ambiguity is a property of the reference only.** A slot is `lag_ambiguous` iff the **reference's own** autocorrelation has a second distinct peak ≥ 0.9 × its zero-lag peak (the same ±6-sample exclusion). It no longer depends on the capture, so no chain fault can switch it on. The Engineer reports how many slots this gives against the old 68, and lists any slot that moved in or out.

**A10 added: losing a clean peak is itself a timing anomaly.** On a slot whose reference is **not** ambiguous, apply the old A3 test to the **capture's** cross-correlation. If it is ambiguous (second peak ≥ 0.9 × best), the slot flags **`lag_lost`**, in the timing family. A3′ alone would only replace NaN with whatever the smeared peak gives. A10 turns the failure the Engineer found into a detection. `lag_lost` is calibrated on 09-23 like any metric: a count of unmodified slots, the BOTH exclusion and the 2 % `DESCRIPTIVE` rule all apply. The PC1 injections that should trip it are the drift and hiccup ones, and they may now pass on `drift_ppm` **or** `lag_lost`, as the hiccup injection already did on drift or step.

**Plan accepted, in this order:** (1) implement A3′ and A10 in `scan_core.py`, recalibrate only `lag_lost` (other threshold values unchanged; prove it cell by cell as before), mark the two A9 above-range cells `DESCRIPTIVE-ABOVE-RANGE`, and **re-freeze 3** with the new SHAs of both files; (2) rerun PC1 for the three A8 cells, every cell whose ambiguity set changed, and the new `lag_lost` cells; (3) all PASS ⇒ read 09-29.

## 🔴 Terminal rule (fixed now, so this cannot loop)

This is the **last design round before 09-29**. If any cell fails at step (2), that **(side, group, metric)** cell goes `DESCRIPTIVE-PC1-FAIL`: it is reported as a hole, never used to flag, and needs no further ruling. **The scan then proceeds to 09-29 with the holes stated in its headline.** A design change after this point waits for the validation report and a ruling on it. It never happens before 09-29 is read.

Why: each round so far has been right, but a scan that is redesigned until its control passes is tuned to its control. The holes are the honest result, and the Captain decides after validation whether they are worth closing (with the notification-sound gap).

## Noted

A9: 4 PASS with a graded response (good: the response is not flat). Edge-test freeze `46994f57` received via QA. The edge test runs first; the scan resumes after it.
