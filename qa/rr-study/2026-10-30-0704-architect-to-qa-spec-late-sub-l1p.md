# `LATE-SUB L1′`: one late subtract-and-decode round with the primary decoder only, verdict on a fresh night

**From:** Architect · **To:** QA · **Date:** 2026-10-30 07:04:20Z (`date -u`) · **Branch:** `arch/late-sub` (the same arm's workstream)
**Authority:** the Captain, 2026-10-30, in the Architect's window: "go with your recommendations". This is option 1 of the LATE-SUB ruling (`qa/rr-study/2026-10-30-0655-architect-late-sub-ruling.md` §5, `91f80ecd`; §1 corrected in `2e8c7afe`).
**Base:** LATE-SUB spec `5c33391f` + Amendment 1 `e2f7c5b2`; QA harness `664c5e97` (`LateSub.cs`); QA report `4e790030`. Everything not changed here is as in those documents.
**Status:** an offline lever study, `qa/` code only. **No `src/`/`native/` change** (`git diff --stat origin/main -- src/ native/` is empty).

---

## §0. Why this arm, and why a fresh night

On the refset TEST cycles, the step-by-step breakdown of L (ruling §3) showed:
- **L1**, the primary decode on the late residual R4, added 282 rows. 93.6 % of them were corroborated, at a cost of about 0.004 ΔU′ per pp. That is as clean as R-F4 and multi-set.
- **C and L2**, the fallback steps that build their own candidate list from a residual buffer, carried the cost.

**L1′ keeps the clean step and drops the two fallback steps.** I picked L1 out *after looking at TEST*. Re-testing it on those cycles would grade my own selection. 🔴 **So the verdict comes from a night the LATE-SUB study never saw.** The refset TEST cycles are reported alongside, descriptively, and never decide.

## §1. Arm definition

For each cycle, the product runs unchanged (the same harness, the same Amendment 1 conditions). Then:

1. **B** = R3 if the third pass ran; otherwise R2. This is unchanged from LATE-SUB §2.
2. **Fit list** = the product's published **batch 3 ∪ batch 4**, built as the product builds a fit list. This is Amendment 1 D2: unrounded `OutDtS` (`Ft8Decoder.cs:1114`), null logger and deadline. **There are no Arm C rows**, because Arm C is not run.
3. **The round:** `SubtractionPass.RunThirdPassAsync(B, fit = batch3 ∪ batch4, alsoKnown = batch1 ∪ batch2)`. This gives R4 and its primary decodes. **Those decodes are L1′.**
4. **Nothing else.** There is no fallback on B and no fallback on R4.
5. **Skip rule:** if no fit-list entry survives `IsReencodable`/`EncodeMessage`, L1′ is skipped for that cycle. The count is reported.
6. **Publication emulation:** as in Amendment 1 D5 (code; `seen` is seeded with every earlier text in the cycle).
7. **Hash state:** every extra call is bracketed with HashStateSave/Restore (Amendment 1 D3). NET stays conservative.

**Configurations:**
- **OFF** (`decoder.coherentFallbackResidualUngated` = false) **decides**.
- **ON** is reported descriptively. L1′ has no fallback rows of its own, so ON changes only the product rows L1′ is measured against.

## §2. Nights and cycles

**Verdict night: `20261022_1949_endurance_run-gathered`** (R-F4's second night). It is on the PC under `artefacts\`.
- **Same-band check:** already done and passed (R-F4 build spec A1.4: 0 mismatches).
- **Selection:** R-F4's frozen 800-cycle 2N selection (stride 3, offset 1, the first 800; outage slots dropped after selection). **QA cites its file SHA-256 in the freeze commit.** Then n_ref = 20,753, as in the R-F4 acceptance. If the PC's count differs, report it.
- **U′ classes:** R-F4's frozen 2N classes, from the 200-cycle Original arm, frozen instrument. QA cites the file and its hash.
  - The HK-026 condition carries over, mechanical: **if any unconfirmed L1′ output on the OFF arm falls in `untestable_class`**, QA runs the Original arm on the remaining 600 cycles and re-freezes the classes from all 800. Only then are the U rows computed. The report states the cycle count behind the classes.

**Descriptive night:** refset `20260925_2010`, TEST cycles 401–1,200, OFF only, `selection1200.json` `328c85d4`, the same U′ classes as LATE-SUB. This gives L1′ against L1 (+1.140 pp) on the same cycles, which shows how much C's rows in the fit list mattered. **It does not enter any verdict row.**

**Machine:** the PC, the station stopped, the DLL pin `1ba8dc3d…` (V0). sol is not needed.

## §3. Validity (mechanical; all must pass on the verdict night before any outcome is read)

| row | predicate |
|---|---|
| V0 | the DLL SHA-256 equals the pin `1ba8dc3d6a7d…` |
| V2 | the offline reproduction of batches 1/2/3 and the B buffer: 0 cycles not reproduced |
| V3 | batch 4 reproduction: 0 cycles not reproduced |
| V5 | residual pass, third pass and fallback abandoned or contained = 0 in every selected cycle (the PC budget, as in LATE-SUB) |
| V6 (new) | the freeze commit (selection SHA, U′ class-file SHA, DLL SHA, the code commit) is **earlier** than the first L1′ output file's mtime |

**V1 on the verdict night is descriptive, not a row.**
- The R-F4 2N arms ran on sol (a different library and platform), so byte-identity to them is not expected.
- Report the number of cycles where the PC product's batch counts differ from sol's OFF arm, as a pointer only.
- The verdict compares L1′ with the **same run's** product output, so the platform does not enter it.

**Pilot:** the first 40 cycles of the verdict selection; V0/V2/V3/V5 only, with no outcome read. Any failure means stop and report.

## §4. Verdict rows (OFF, verdict night; cycle bootstrap B = 2000, seed 20261030)

**Bars (HK-038).** These are the COH-GATE-G bars: ratified 2026-10-28, re-used for LATE-SUB by the Captain's "agreed" (2026-10-29T19:22:19Z), and carried here under his "go with your recommendations". **BAR_G 0.5 pp, U_bar_G 0.021 per cycle on tested_absent, h 0.5.** The populations are the same: today's `main` lineage and the same station band.

| row | predicate | leads to |
|---|---|---|
| **L1′-GO** | `CI_lo(NET)` ≥ 0.5 **and** `CI_hi(ΔU′_ta)` ≤ 0.021 **and** H-SHARE ≤ 0.5 | a Developer **build spec** (HK-011) with a sol timing row. The acceptance night for the build is a third night, never this one |
| **L1′-COST** | `CI_lo(NET)` ≥ 0.5, but the U or H condition fails | the Captain decides with the table |
| **L1′-STOP** | `CI_hi(NET)` < 0.5 | no build |
| **L1′-OPEN** | otherwise | too wide to call; reported as such, not re-run on the same night |

The rows are exclusive and are evaluated in this order. The predicate is code, asserted in the analysis script.

**Metrics:** exactly as in LATE-SUB (NET pp of n_ref; ΔU′_ta per cycle; H-SHARE = hashed/unencodable share of L1′'s added outputs).

## §5. Also reported (descriptive)

- **Per night:** the L1′ rows added, corroborated, tested-absent, hashed; the cycles where L1′ ran and where it was skipped; how many fit-list entries were refused.
- **Refset TEST (OFF):** NET and ΔU′_ta for L1′, beside LATE-SUB's L1 (+1.140; step ΔU′ about +0.005).
- **Timing on the PC:** L1′ round median, p90 and max; end-of-work with L1′, against the product's own. sol's margin (11.1 s fallback end) is a build-spec row, not this study's.
- **ON (verdict night):** NET and ΔU′_ta of L1′ against the ON product.

## §6. Predictions (Architect; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| L1P-1 | the pilot and the full verdict-night V-rows pass without an amendment | 0.75 | C |
| L1P-2 | L1′-GO | 0.50 | H |
| L1P-3 | NET point on the verdict night ≥ 0.8 pp | 0.35 | H |
| L1P-4 | ΔU′_ta point on the verdict night ≤ 0.010 | 0.75 | H |
| L1P-5 | refset TEST L1′ NET point ≥ 0.9 pp (C's rows add less than 0.25 pp to the late round) | 0.55 | H |

**Reasoning for L1P-2/3.** On R-F4, the second night gave 0.70 of TEST's NET (+1.47 against +2.10). Applied to L1′, that is roughly 0.70 × 0.9–1.1, about +0.65–0.8 pp. TEST's CI half-width was about 0.13 pp, so CI_lo sits near the 0.5 bar. A coin flip is the honest price.

🔴 **Bias check:** this is a "findable localised defect" lever picked after seeing the data, which is the worst case for over-calling. That is why the GO prediction stays at 0.50.

## §7. Cost and order

1. QA's (k) review of this spec.
2. Freeze commit (V6).
3. Pilot of 40 cycles.
4. Verdict night: OFF, then ON, 800 cycles each. At about 3 s per cycle for the V2 reproduction, that is roughly 1.4 h each.
5. Refset TEST OFF, 800 cycles, about 1.4 h. The R3 buffers QA kept may shorten this.
6. Analysis, report, then my ruling.

Total: about 4–5 h of PC time, unattended, with the station stopped.

**The run go.** The Captain's "go with your recommendations" covers writing this spec. **The run itself needs his go after QA's (k) review**, as usual.
