# `LATE-SUB L1′`: ruling. L1′-GO on a fresh night: +0.74 pp at a cost as low as the shipped levers

**From:** Architect · **To:** the Captain, QA · **Date:** 2026-10-30 13:18:15Z (`date -u`) · **Branch:** `arch/late-sub`
**On:** QA report `qa/rr-study/results/2026-10-30-late-sub-l1p/report.md` (`ea087548`, `qa/refset`, local). Spec `8152d4ce` + Amendment 1 `e3fd391e` + A1.6 `4baed2bd`; QA review `2ce7eabc`; freeze record `23a35eb4` (before any output, V6); code `b7c17464`. Docs only; `git diff --stat origin/main -- src/ native/` is empty.

---

## §1. Validity: accepted

- **V0, V2, V3, V5 and V6 pass in the pilot, OFF, ON and the refset leg.** V7 (the dropped-C mode reproduces the old pilot) and V8 (n_ref 20,753 on the PC) passed before the freeze.
- **Frozen inputs are asserted in code:** selection `cf9908a5…`, classes `0d83d685…`, instrument blob `66dd1e94…`, DLL `1ba8dc3d…`.
- **HK-026 did not fire:** 0 unconfirmed L1′ outputs fell in an untestable class.
- **V1 (descriptive):** the PC product's batch counts differ from sol's in **0 of 800 cycles**, both OFF and ON, so the platform does not enter the comparison.
- **The refset leg ran as one process from cycle 1** (A1.6), so it compares like for like with LATE-SUB's L1.

## §2. Verdict (OFF, `20261022_1949`, 800 cycles, n_ref 20,753)

| metric | value | bar | met |
|---|---|---|:---:|
| NET pp | **+0.742 [0.621, 0.859]** | CI_lo ≥ 0.5 | ✅ |
| ΔU′_ta per cycle | **0.0063 [0.0013, 0.0125]** | CI_hi ≤ 0.021 | ✅ |
| H-SHARE | 0 of 167 | ≤ 0.5 | ✅ |

**Row: L1′-GO** (mechanical; `l1p_analyse.py` printed it). The night added 167 rows: 154 corroborated (92.2 %), 5 tested-absent, 0 hashed.

**Cost per pp:** about 0.008 (0.0063 / 0.742). That is the same order as R-F4 (about 0.002) and multi-set (about 0.003), and five times cheaper than LATE-SUB's L (about 0.023).

**Descriptive:**
- **ON:** +1.123 [0.980, 1.269], ΔU′_ta 0.0075. The late round gains more when R-F4 is on.
- **Refset TEST:** +1.140 [1.009, 1.278], the same point estimate as L1 with Arm C in the fit list. **C's rows did nothing for the late round**: they moved about 7 % of its rows and changed nothing net. So dropping C costs no yield.
- **Ratio to the refset:** the verdict night gives 0.65 of the refset NET, against 0.70 for R-F4 on the same second night. Refset figures overstate a lever by about a third, and this is the second time we have seen it.

## §3. Ledger (scored at ruling time)

| # | prediction | P | result |
|---|---|---:|---|
| L1P-1 | pilot + full V-rows pass without an amendment | 0.75 | ✅ HIT. A1.6 came before the freeze; after the freeze only an unchecked chain-script path changed |
| L1P-2 | L1′-GO | 0.50 | ✅ HIT |
| L1P-3 | verdict-night NET point ≥ 0.8 pp | 0.35 | ❌ FALSE (0.742) |
| L1P-4 | ΔU′_ta point ≤ 0.010 | 0.75 | ✅ HIT (0.0063) |
| L1P-5 | refset TEST L1′ NET point ≥ 0.9 pp | 0.55 | ✅ HIT (1.140) |

**Brier 0.140 over 5.** The night-to-night shrinkage forecast (0.70 × about 1.0) landed on the low side of my range, at 0.65 × 1.14.

## §4. What a build has to answer (for the build spec, not this study)

1. **Where it runs in the pipeline.** The fit list includes batch 4, so the round runs **after the fallback**. On the PC the worst cycle ends at 5.8 s of 13 s. On sol the fallback already ends at 11.1 s (1.9 s margin, FBAUDIO). The PC round takes 0.75 s median and 1.31 s max, and sol is slower. 🔴 **So sol's margin is the open risk.** The build needs a deadline: skip the round when the cycle's time is short, the way the existing passes do. The build spec also needs a sol timing row and an abandonment count.
2. **The setting.** It ships as a new setting, **default OFF**, like R-F4. Turning it on is a new era for live figures, and that is your decision after acceptance.
3. **Acceptance on a third night** (not `20261022_1949` and not the refset), with the same rows, plus a PC-vs-product check that the build reproduces this harness.
4. **Hash state.** The study kept L1′'s outputs out of later cycles' hash state. The product would feed them in. This should be stated as a known, small difference (0 hashed among the added rows here).
5. **#273:** 9.5 % of the fit list is refused by the re-encoding check on this night. That is a separate lever (payload subtraction), not part of this build.

## §5. For the Captain

- **Result:** the clean step passed on a night it had never seen. It adds **+0.74 pp** of WSJT-X's decodes (about +1.1 pp if R-F4 is on), at **about 5 extra unconfirmed decodes in 800 cycles** (roughly one every 3½ hours of operation).
- **Options:**
  1. **Build it (recommended).** I write a Developer build spec: the late round behind a new setting, default OFF, with a time guard, a sol timing row and acceptance on a third night. Cost: my spec (about 1 h), QA's review, a Developer session, then QA's review and acceptance (about half a day of machine time).
  2. **Stop here.** Record the result and move to the next lever. The yield is smaller than R-F4's, but the cost is about the same per pp.
- **Recommendation: 1.** It meets the bars with margin on unseen data, it stacks with R-F4, and its only open risk (sol's time budget) is a measurable build row, not a research question.
