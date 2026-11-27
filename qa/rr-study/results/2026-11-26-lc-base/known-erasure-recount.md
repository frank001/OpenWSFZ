# KNOWN-ERASURE §0 re-counted: how many failed candidates end at five or fewer unsatisfied checks?

**Date:** 2026-11-27 · **Author:** QA · **Asked by:** the Architect (`spec-known-erasure.md` §0, "re-count it in your own script for the record") · **Input:** the XC-ROUND confirmation runs `xn_*` (build `f9662335`), `probe.tsv` (numbers only; no message text is read) · **Script:** `qa/decoder-rebuild/ke_recount.py` (counts) and the quartile comparison below (same data).

## Result

**The Architect's denominators reproduce exactly** (kept candidates that failed every tier: **45,322 / 69,543 / 70,117** on S40 / H40 / H20). **His numerators reproduce exactly under one definition, and under the other the share is about half:**

| Definition of "best tier" | S40 | H40 | H20 |
|---|---:|---:|---:|
| **min of tier A, tier B and CQ-AP** unsatisfied checks, at most 5 (the Architect's 15,469 / 24,238 / 23,769) | 15,469 (34.1 %) | 24,238 (34.9 %) | 23,769 (33.9 %) |
| **tier A and tier B only** (the predicate SUB-PROBE's "best attempt" uses: tier A when its code is A_BP, tier B when its code is B_BP) | 8,042 (17.7 %) | 13,043 (18.8 %) | 11,966 (17.1 %) |
| of the first row, the part that is CQ-AP alone at most 5 (every candidate gets a CQ-AP attempt, whose fixed CQ bits lower the count mechanically) | 9,044 | 13,860 | 14,229 |

So the Architect's figures are right but include the CQ-AP attempt, which makes "at most 5" about twice as common; SUB-PROBE's "5 to 6 checks short" for K2 was measured on tier A and B only, so the like-for-like noise figure is the second row (17 to 19 %).

## Does the conclusion hold? Yes, with a correction to how it is put

Best tier A / B unsatisfied checks, quartiles (q1, median, q3):

| Slice | all failed kept candidates (mostly noise) | K2 targets T (best attempt, the same predicate) | share of all failed candidates at most 5 |
|---|---|---|---:|
| S40 | 7, 10, 13 (n = 45,322) | 3, 5, 7 (n = 337) | 17.7 % |
| H40 | 6, 10, 13 (n = 69,543) | 3, 4, 6 (n = 450) | 18.8 % |
| H20 | 7, 10, 13 (n = 70,117) | 3, 5, 8 (n = 527) | 17.1 % |

- **K2 targets ARE closer than the typical failed candidate** (median 4 to 5 against 10), so "5 to 6 checks short" is not nothing: there is an enrichment.
- **It is still not a usable near-miss signature.** At least about half of the K2 targets (some 170 to 260 or more per slice) lie at five or fewer, among **8,042 / 13,043 / 11,966** failed candidates at that level: roughly one real target in 50 (a rough figure from the quartiles). A rescue acting on the "at most 5" candidates would work on some 8,000 to 13,000 mostly-noise candidates to reach those 170 to 260. That supports the Architect's conclusion (OSD or any "almost decoded" rescue is not the lever), on the stricter tier A / B count as well as on his.
- Wording to carry into the record: "about 17 to 19 % of all failed kept candidates end at five or fewer unsatisfied checks on tier A or B (34 to 35 % if CQ-AP's count is included); K2 targets' median is 4 to 5 against 10 for all failed candidates".
