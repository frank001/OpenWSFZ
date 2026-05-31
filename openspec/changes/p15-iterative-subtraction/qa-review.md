# QA Review — p15-iterative-subtraction

**Reviewer:** QA  
**Date:** 2026-05-31  
**Branch:** `feat/p15-iterative-subtraction`  
**Suite result at review:** 212 passed, 4 skipped, 0 failed ✓

---

## Verdict: APPROVED ✅

All required items resolved (2026-05-31). Merge is permitted.

~~CONDITIONAL APPROVAL — The implementation is technically sound. Two items must be resolved before merge is permitted.~~

---

## Required Before Merge

- [x] **Finding 1 — `findings.md` decision-gate text is factually incorrect**

  **File:** `openspec/changes/p10-decoder-ground-truth/findings.md`, lines 66–68

  The current text says iterative subtraction (second-pass decoder) is *"deferred to a future change"*.
  This was boilerplate from before p15. After p15, the second-pass decoder **has been implemented**.
  The text must be replaced with an accurate description:

  - Iterative subtraction was implemented in p15 using spectrogram-domain ±1-bin suppression.
  - The 30% gap to WSJT-X parity is not due to missing implementation; it is the ceiling of the
    spectrogram-domain approach (FFT waterfall ±3.125 Hz resolution, Hann-window sidelobe leakage).
  - PCM-domain subtraction (a future change) is the path to ≥80%.

  The correct language already exists in `design.md §Decision 6` — mirror it here.

- [x] **Finding 2 — AC-IS-1 recovery target (≥80%) not met — Captain decision required**

  The implementation achieves **69.1% (613/887)**; the goal was **≥80% (≥710/887)**.
  This is not a code defect. The developer has provided a credible technical explanation
  (design.md §Decision 6) and exhaustive parametric tuning evidence.

  The Captain must formally choose one of:

  - **(A — Recommended)** Accept 69.1% as the achievable result for the spectrogram-domain
    approach. Update AC-IS-1 in `specs/iterative-subtraction/spec.md` to reflect that ≥80%
    is a PCM-domain target, not a shim-domain target. Open a follow-up change
    (e.g. `p16-pcm-iterative-subtraction`) to track the remaining work. Then merge.

  - **(B)** Block merge until ≥80% is achieved. Note: by the developer's own analysis,
    this requires PCM-domain waveform subtraction — a materially larger change that does
    not belong in this PR.

  Record the Captain's decision here before proceeding.

  **Captain's decision:** **Option A — accepted (2026-05-31).** 69.1% is the achievable ceiling of the spectrogram-domain approach. AC-IS-1 updated in `specs/iterative-subtraction/spec.md` to reflect that ≥80% is a PCM-domain target. Follow-up change `p16-pcm-iterative-subtraction` will track the remaining work. Merge approved pending Finding 3.

---

## Recommended (Fix Before Merge)

- [x] **Finding 3 — `ft8_shim.c` header comment misquotes the measurement**

  **File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 24

  | Current | Correct |
  |---|---|
  | `69.0% recovery (612/887)` | `69.1% recovery (613/887)` |

  The authoritative source (`findings.md`, 2026-05-31 15:13:22 UTC) reports 613 matched decodes.
  The comment is off by one message and one tenth of a percent.

---

## Noted — No Action Required This PR

- [ ] *(Awareness only)* **Finding 4 — `MaxResults = 140` is below the two-pass theoretical ceiling**

  **File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, line 33

  With two passes (`K_MAX_CANDIDATES = 140` + `K_MAX_CANDIDATES_PASS2 = 200`), the theoretical
  maximum unique decoded messages is 340 (`K_MAX_DECODED`). The C# buffer is 140. Messages that
  push the total over 140 would be silently discarded by the native shim.

  **Practical risk: essentially zero** — the busiest observed cycle in the corpus produced 18
  matched decodes; 140 is an order of magnitude above any real-world scenario.

  No fix required in this PR. Consider renaming to `MaxTotalResults = 340` in a future
  housekeeping change for clarity.

---

## Summary

| # | Severity | Action | Item |
|---|---|---|---|
| 1 | 🔴 Required | Fix before merge | `findings.md` decision-gate text — stale, factually wrong post-p15 |
| 2 | 🔴 Required | Captain decision | AC-IS-1 ≥80% not met — accept 69.1% or block |
| 3 | 🟡 Recommended | Fix before merge | `ft8_shim.c` comment: 69.0% / 612 → 69.1% / 613 |
| 4 | ⚪ Noted | Future housekeeping | `MaxResults = 140` below two-pass theoretical ceiling |

Return this document with all required items checked and the Captain's decision recorded.
Merge will be approved on re-submission.
