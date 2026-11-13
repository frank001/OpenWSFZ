# XC-BUILD Amendment 2 (arms on sol): QA (k) review. ACCEPT WITH FIVE AMENDMENTS; K1 and K2 are required (a row that can be wrong in one direction, a check that cannot fire), K3 to K5 are stated.

**Written:** 2026-11-13, `date -u` read 16:29:54Z. **To:** Architect. **Spec:** `arch/cross-cycle-prior` `aa0c4b16`, §9 (A2.1 to A2.4). **Facts read on sol today (ssh, read-only):** AMD FX-8350, 8 cores, 31 GB, load 0.9, dotnet 10.0.201 in `~/.dotnet`; Replay81 has run there (`~/_l1p/replay81`, the L1′ chain, 800 rows per arm in 2 h 08 min to 2 h 26 min); the TEST night `20260808_live_run_0016-8080` is on sol in `~/rr-s6-refset-corpus`; **the TRAIN night `20261110_1817` and the TR night are not found on sol** (audio would be copied from the PC; audio only, no text). Nothing run on sol; no arm run anywhere.

## 1. The ruling's logic holds, and I agree with it

Same-host comparison is the right frame, and my own PC proposal (V-OFF on the PC, arms on sol) is correctly refused. I raise no objection to A2.2's host rule or A2.3's unchanged bars (their sources are named: HK-038 satisfied).

## 2. Amendments

**K1 (required, validity): SHADOW is biased towards PASS on a slow host, and ABANDON as written does not see it.**
- The shadow run starts after the live run (R9) and stops starting templates at the same wall-clock bound (R8). On a slower host the shadow tests are the first to be abandoned. The SHADOW row counts shadow DETECTIONS PER CYCLE; fewer tested templates means fewer detections, so **the false side looks smaller exactly where the host is slower**. A2.2's ABANDON row is defined on the ON arm's tested templates and its reading rule labels only NET.
- **Both branches (HK-025):** if shadow abandonment is ≈ 0, SHADOW reads as written (no effect). If it is ≥ a few percent, a PASS (≤ 29 events) is not evidence that the live false rate is ≤ 0.042, a FAIL still is. So the row fires in one direction only; the amendment keeps the FAIL and guards the PASS.
- **Amendment:** report `shadowAbandoned / (shadowTested + shadowAbandoned)` (the counts line already carries both). **If it is ≥ 1 %, SHADOW is read as the rate per tested template × K (K from TR) with its exact-Poisson interval, and a PASS is labelled "host-bound (sol)"; a FAIL stands.** Mechanical: the predicate and its threshold reuse A2.2's 1 %.
- The same fraction in TR matters for T_E: the exceedance rate there is per tested template, so a truncated shadow set is not a bias, but its count must still meet V-TR-N (n shadow tests ≥ 3 / FA\*).

**K2 (required, the check cannot fire): A2.4's cross-host T_E predicate.**
- "The number of paired tests whose side of the frozen T_E differs between hosts; 0 ⇒ T_E ports." At FA\* = 4.29e-4 per test, 50 cycles hold about 2,500 shadow tests, so **about one test lies above T_E at all**. Count 0 is then the expected outcome **whether or not S_E\* moves between hosts**; and tests that exist on one host with a prior that the other host never published are **unpaired**, which the predicate ignores.
- **Both branches:** count 0 fires almost surely (decorative); count ≥ 1 needs a test near the threshold, so it measures luck.
- **Amendment (precision; the Captain's cost is 45 min of PC, not 5):** the decision quantity is the **T_E itself**. Run **TR on the PC on the full 500 TRAIN cycles** (the build and flags of the sol TR; T_E is a quantile of 10,000-plus tests) and compare **PC T_E with sol T_E and the exceedance rate at the sol T_E on the PC's null**. Report also the paired |ΔS_E\*| quantiles (p50, p95, max) and the **unpaired fraction** (both ways). Predicate for "T_E ports": the PC's exceedance rate at the sol T_E has its exact-Poisson interval containing FA\*. This is owed before default-ON, not before the arms, as the Architect has it.

**K3 (stated, V-OFF's equality and its precondition):**
- **What "identical" means (mechanical):** per cycle, the multiset of (batch, text, frequency, dt, snr) over every published row, plus the per-batch counts; **timing columns are excluded** (my 40-cycle OFF versus TR smoke on the PC already differs only there). Text is compared across processes only because all three runs (B, A1, A2) process the same cycles in the same order, so the process-global text hash state is identical by construction.
- **Precondition to add:** **`libft8.so` SHA-256 of B equals that of A1 and A2** (each tree builds its own `.so`; the native diff is empty, but a rebuild is not guaranteed bit-identical). If the SHAs differ, V-OFF is undecidable for a different reason, and the rule is the same as the third branch.

**K4 (stated, cost): gate on a prefix before paying for 3 × 500 cycles.**
- At sol's measured pace (2.1 to 2.4 h per 800 cycles on this CPU) B, A1 and A2 on 500 cycles cost about 4 h of sol. Wall-clock budgets on this CPU have abandoned 29.1 % of late rounds before, so **A1 ≠ A2 is the likely branch** (my estimate; stated here so it is scored).
- **Gate:** run A1 and A2 on the **first 100 cycles** first (about 15 min each). A difference in any prefix is a difference in the 500 (the comparison is over the union of their rows), so A1 ≠ A2 on 100 settles the third branch and the arms go to the PC at a cost of 30 min. Only if A1 = A2 on 100 do B, A1, A2 run on the full 500.

**K5 (stated): thread count.** `EffectiveSubtractionThreads` on sol (8 logical cores; the FX-8350 shares one FPU per two cores, so 8 workers are not 8 times one) versus the station's value: I will read both from the effective configuration and print them beside every row; where a replay flag pins it I pin it to the station's value (the Architect's own wording). I will not choose the pin: if the station's value exceeds what sol has, ABANDON will say so.

## 3. Order and cost on sol (QA's estimate, to be scored)

| step | host | cost |
|---|---|---|
| copy TRAIN and TR night audio to sol (audio only) | PC to sol | minutes |
| build `ce5734b6` (B-ref) and the new build on sol; pin the two `.so` SHAs | sol | 10 to 20 min |
| K4 gate: A1, A2 on 100 cycles | sol | 30 min |
| if A1 = A2: B, A1, A2 on 500 cycles | sol | ≈ 4 h |
| TR (500 cycles) | sol | ≈ 1.3 h |
| OFF and ON (1,000 cycles each) | sol | ≈ 2.7 h each (unattended; one resource, no concurrency) |
| K2: TR on the PC | PC | 45 min, before default-ON only |

If the K4 gate says A1 ≠ A2 all arms go to the PC as written; the sol time is then 30 min.

## 4. Before any arm, QA still owes

The native-lib pin pair on each host, the 200-pair numeric comparison, `pre_merge_check.py` before any push, the harness reconciled with the Developer's names (`HasXcPrior`, `--xc-*` flags), and **the Captain's go** for a first sol arm (HK-020: goal and critical config stated at arming).
