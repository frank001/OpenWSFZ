# LATE-SUB L1′: QA (k) review of the spec (nothing was run)

**To:** Architect · **From:** QA · **Date:** 2026-10-30T07:06:37Z (`date -u`, last reading before drafting)
**Spec reviewed:** `qa/rr-study/2026-10-30-0704-architect-to-qa-spec-late-sub-l1p.md`, commit `8152d4ce` on `arch/late-sub`.
**Read:** the spec; `LateSub.cs` (`664c5e97`, lines 112-228: where C, the fit list and L2 sit); the on-disk R-F4 files `selection_2n.json`, `u2/orig_classes.json`, `second_night_result.json`; `ls_analyse.py` (what is hard-wired to the refset).

## Verdict

**APPROVE WITH FIVE REQUIRED AMENDMENTS (E1 to E5).** The design answers the problem it was built for: L1 was picked after seeing TEST, so the verdict moves to a night the study never saw, and the refset TEST is kept descriptive. The rows are exclusive and ordered. Both branches are live: GO and COST differ only in the U/H condition, so no row is decorative. Bars are stated with their origin (HK-038: the COH-GATE-G bars, the Captain's "agreed" and "go with your recommendations"; same `main` lineage, same station band). None of the amendments changes a bar or the arm.

## Your three open points

**(a) The 2N selection and class files are reachable from the PC: YES.** Both sit in `D:\Projects\claude\_qa-scratch\coh-gate-r-f4\` and are stamps and class tables only (no message text):
- `selection_2n.json`, SHA-256 `cf9908a5dcc66ef8966693b2d29ae5bd04fc357d3e1af5058b0e35d7eea6726e`: night `20261022_1949`, 800 FULL cycles, "stride 3, offset 1, first 800 slots of the gap-inclusive 15 s grid", `outage_dropped` 0.
- `u2/orig_classes.json`, SHA-256 `0d83d685db2aee961211b022d5b563c0b5b24a83e51f16c126d0f6cff870ab25`: 4 testable classes of 5, `T_frozen` 0.276, `min_n` 10, `min_present_rate` 0.8, instrument blob `66dd1e94…`.
These are scratch files. Job-close deletion must **not** touch them until the L1′ verdict is ruled (I will hold the deletion and put both hashes in the freeze commit; copying them into the repo is a small stamps-only commit I can do if you prefer).

**(b) n_ref on the PC is 20,753: ON FILE, not yet re-derived on the PC.** `second_night_result.json` records `n_ref` 20,753 and `cycles_with_wsjtx` 799 of 800 (the R-F4 acceptance, computed on the Windows side from the WSJT-X reference, so the number is a function of the data, not the decoder). See E4: I make it a mechanical row rather than a report line.

**(c) The harness can drop C and L2 without touching V2/V3: YES, with a code change.** In `LateSub.cs` V2 and V3 (the offline reproduction of batches 1, 2, 3, the R3 bytes and batch 4) finish before arm C starts (the arm code begins at the `CohFallbackRun(B…)` call, line 177). The L1′ mode removes three things: the arm C call (line 177), `pc` from the fit list (line 185: `pub3.Concat(pub4).Concat(pc)` becomes `pub3.Concat(pub4)`), and the second fallback on R4 (line 208). V2/V3 code is not on that path. What the change does touch is the hash-state bracket sequence (one Save/Restore fewer) and the `ls_cycle.tsv` columns (`pubC`, `pubL2`, `ms_C`, `ms_L2` become empty). Required: E2.

## Amendments

**E1. The analysis is hard-wired to the refset, and must be parametrised before the freeze.** `ls_analyse.py` and `ls_check.py` fix the night (`RUN = 20260925_2010`), the reference, the selection (`selection1200.json`), the U′ classes (`uprime_orig_classes.json`) and the baseline (the on-disk R-F4 arms). For the verdict night:
- the **baseline is the same run's own product output** (the PC harness's published rows), per your §3 note; that file must be named in the freeze;
- the night, reference path, selection and classes are arguments, and each is **asserted** in code against the hashes in the freeze commit (`cf9908a5…`, `0d83d685…`, DLL `1ba8dc3d…`);
- the same code runs the descriptive refset leg, so the L1′ vs L1 comparison uses identical metric code.
This is `qa/` code only. It must be in the freeze commit (V6 cites "the code commit").

**E2. Dropping C and L2 gets its own regression row (V7, validity, mechanical).** Run the new mode on **refset cycles 1-40** (the old pilot) and compare to the existing pilot output (`late-sub\raw`, pilot run): the V2 and V3 columns (`v2_b1`, `v2_b2`, `v2_b3`, `v2_r3_bytes`, `v3_b4`) and the product's published batch counts must be **identical cycle by cycle**; the fit list must equal the old fit list **minus the Arm C rows** (a count check: `fit_n_new` = `fit_n_old` − `pubC`, per cycle). Cost: minutes. Any difference means the mode flag leaked into reproduction: stop and report. This is the proof of your point (c) in code, not prose.

**E3. HK-026 re-freeze: state the cost and the compute path.** The spec says "QA runs the Original arm on the remaining 600 cycles and re-freezes the classes from all 800". That arm is not in the 4-5 h of §7. It is a further full pass over 600 cycles, on the PC, of the Original (no-fallback) configuration, so about 1 h, and it needs a build of the Original arm that I will name in the freeze. The trigger stays exactly as written (any unconfirmed L1′ output on the OFF arm in `untestable_class`). I ask only that the freeze commit state this, so that "the 4-5 h" is not read as a ceiling if it fires. If it fires, the verdict rows are computed once, on the 800-cycle classes, never on both.

**E4. n_ref is a validity row, not a report line.** V8: the PC-derived n_ref equals 20,753, asserted in code. A different value means the reference extraction differs from the one the bars were ratified against, and a pp bar scales with n_ref. On mismatch: stop and report before any outcome is read. (This is the same class of check as V2/V3; the spec's "report it" leaves a path where the number is read through a different denominator.)

**E5. Platform pointer, and what V1 does not cover.** V1 is descriptive because the R-F4 2N arms ran on sol (a different library). Agreed. Two statements to put in the report, not rows: (i) the pointer is the count of cycles where the PC product's batch counts differ from sol's OFF arm, with no threshold, as you wrote; (ii) the U′ classes were frozen from a sol Original arm, and the class table is a property of reference rows (SNR, dt, frequency), not of which decoder ran, so the platform enters the instrument weakly. I could not verify (ii) from the class file's keys alone; the freeze will say "classes taken as frozen, platform not re-tested". If the pointer count is large (I propose: more than 5 % of cycles), the report says so in the first paragraph. It changes no row.

## Smaller points (no amendment)

- **"The R3 buffers QA kept may shorten this" (§7.5):** the kept captures are from GAP-RESIDUAL (cycles 1-400 of the refset). Refset TEST 401-1,200 will be the full harness at about 1.4 h. Please don't plan on a saving.
- **Time:** pilot (40 cycles, minutes), OFF 800 cycles about 1.4 h, ON 800 about 1.4 h, refset TEST 800 about 1.4 h, plus E2 minutes: about 4.5 h unattended, station stopped, PC otherwise idle. The harness at L1′ is cheaper per cycle than L (no C, no L2), so this is an upper estimate.
- **Pilot:** V0/V2/V3/V5 only, no outcome read: fine. Add V7 (E2) and V8 (E4) to the pilot, since they are free there.
- **Predictions L1P-1..5:** noted and not touched; L1P-5's reasoning needs C's rows being a minor part of the fit list, which the refset leg will show directly.
- **Skip rule:** counted and reported; with batches 3+4 the survivor count is almost never zero, so I expect few or no skips.
- **Hash-state limitation** carries over unchanged (NET is conservative); it will be in the report's limitations.

## What happens next

1. You confirm E1-E5 (or amend); I need no Captain decision for the review itself.
2. I implement the mode flag and the parametrised analysis, run the E2 regression, write the freeze commit (selection and class hashes, DLL, code commit, baseline file name), and wait.
3. **The run needs the Captain's go** (he approved writing the spec only). I will ask him with the estimate above.
4. Pilot, then OFF, ON, refset leg in one detached chain, and the report with the V-rows (V0, V2, V3, V5, V6, V7, V8) first.

Nothing pushed. No `src/`/`native/` change.
