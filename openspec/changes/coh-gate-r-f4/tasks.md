> **Status note (QA, 2026-10-28).** Authorised by the Captain ("spec it for qa", relayed by the Architect) after the G-BUILD ruling `db578cf7`. Build spec: `qa/rr-study/2026-10-28-1724-architect-to-qa-build-spec-coh-gate-r-f4.md` with Amendment 1 section 7 (`15e0f838`, `arch/coh-gate-g`); read with `git show 15e0f838:<path>`. Nothing built, nothing pushed.

## 1. Pre-implementation (record in `design.md` before writing code)

- [ ] 1.1 Re-check every FILE:LINE in `proposal.md` and `design.md` on the branch tip (`CoherentFallbackSelector.cs:31`, `Subfeas/CohFallbackAudioSelector.cs:101/105/114`, `Ft8Decoder.cs:1060-1069`, the log line at `Ft8Decoder.cs:1122`; the spec said 1125), record drift.
- [ ] 1.2 Read `qa/rr-study/gap-relocate-run/gg_lib.py` (`publish`, `select`): it is the reference for the merge order and the edge rule.

## 2. Implementation (Developer, `src/`; C# only)

- [ ] 2.1 `decoder.coherentFallbackResidualUngated` (bool, absent or false = off) in `DecoderConfig`, a volatile field on `Ft8Decoder`, set by the daemon before the first window, read once per window; config overlay (HK-035); no Settings control.
- [ ] 2.2 In `Both` mode, residual-run `GatedOut` rows are treated as gated-in from the merge onwards (D3, D4); original-run `GatedOut` rows are not; `Original` and `Residual` modes are unchanged; the row keeps its true state and is never relabelled in a counter or log.
- [ ] 2.3 The log line: `ungated=N` only when ON; `fromOriginal / fromResidual / inBoth` count admitted rows as found by the residual run; `Gated` unchanged (D6).
- [ ] 2.4 **No native change.** `git diff --stat <base> -- native/ src/OpenWSFZ.Ft8/Native/` empty; the built `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`. If unavoidable, stop and return to the Architect.

## 3. Tests (Developer; no fixed sleeps, TESTING_STRATEGY section 11)

- [ ] 3.1 Merge and `Select` with residual `GatedOut` rows, ON and OFF.
- [ ] 3.2 An original-run `NewGated` row is dropped when an admitted residual row has the same payload.
- [ ] 3.3 Edge preference across the mixed states.
- [ ] 3.4 The setting absent means OFF; explicit round trip; a partial config post leaves it as it was (HK-035).
- [ ] 3.5 **(a)** Residual run complete, original run `NotRun` (budget spent, through the internal `BudgetClock` / `TimeProvider` seam of `c9255ae2`): the residual `GatedOut` rows are admitted and published. **(b)** A lone original-audio run (`both(unavailable)`): nothing is admitted over T1.
- [ ] 3.6 `Original` and `Residual` modes ignore the setting.
- [ ] 3.7 The log line: `ungated=` present only when ON, counters as in D6.

## 4. Housekeeping (Developer)

- [ ] 4.1 `VERSION` 0.66 to 0.67 in every place the gates check (the `REQUIREMENTS.md` anchor included); run `check_version_bump.py` and G9a/G9b. G9b reads the proposal from git: commit this change first.
- [ ] 4.2 `REQUIREMENTS.md`: new FR-101 (the setting and the residual-run admission) and the changelog row 1.63. Every requirement in the delta spec has scenarios.
- [ ] 4.3 `openspec validate coh-gate-r-f4 --strict` before committing any edit to this change.

## 5. Acceptance (QA; PC, station stopped; order matters)

- [ ] 5.1 HK-039 review record of the Developer's commit as a `qa/rr-study/*code-review*.md` FILE with `Reviewed-commit:` and `Verdict:` BEFORE any acceptance run (hook-enforced).
- [ ] 5.2 **B-NAT** native diff empty AND DLL SHA-256 equal to the pin.
- [ ] 5.3 **B-OFF** setting absent: per cycle, the published batch-4 set equals `main` `95e69e87` (1,350 on TRAIN, 2,891 on TEST; batches 1-3 unchanged), all 1,200 cycles.
- [ ] 5.4 **B-EQ** setting ON: per cycle, published batch-4 messages WITHOUT `<...>` equal the offline R-F4 publication with 0 differences (255 additions on TRAIN, 522 on TEST); messages WITH `<...>` compared by count per cycle, differences reported with the first differing cycle, not barred. Count the single-run cycles (expected 0).
- [ ] 5.5 **B-AB** setting ON: fallback abandoned 0 and residual pass abandoned 0, all 1,200 cycles. Descriptive beside it: maximum fallback end time and budget margin, OFF vs ON.
- [ ] 5.6 **Second night** `20261022_1949_endurance_run-gathered` (same-band check passed): selection stride 3, offset 1, first 800, outage slots dropped after selection, committed BEFORE the replay; arms OFF, ON, and Original on the first 200 selected cycles (if any unconfirmed admitted output on the ON arm falls in untestable_class, run Original on the other 600 and re-freeze the classes from all 800 before computing U-OK, HK-026). Rows as on TEST: ACCEPT-2N iff N-GO (`CI_lo(NET)` >= 0.5 pp) and U-OK (`CI_hi(dU_ta)` <= 0.021 per cycle) and H-SHARE not fired (hashed share of admitted <= 0.5); FAIL-2N iff N-STOP or U-FAIL; OPEN-2N otherwise. CI: cycle bootstrap, N = 2000, seed 20261028.
- [ ] 5.7 `pre_merge_check.py` from a clean checkout of the exact commit (HK-006) before any push.
- [ ] 5.8 The Captain's push go (HK-033), CI green on the branch (QA pushes early; macOS result in about 6 minutes), the Captain's merge sign-off (HK-010). Only ACCEPT-2N lets the Captain be asked about default ON.
