# QA → Architect: fix-negative-time-offset-snr-collapse — §6.2 re-classified, §7 acceptance PASSES

**2026-08-22 16:23 UTC** · QA session, reviewing `/opsx:apply` output on
`fix/negative-time-offset-snr-collapse` (Developer session escalation
`qa/rr-study/2026-08-22-1611-developer-to-architect-ac-n1-premise-false.md`), then running
`tasks.md` §7 (B-dt-C3 acceptance re-run), which §7.4 assigns to QA, not the Developer.

## 1. Code review (native fix)

`ft8_shim.c:1491-1502` matches `design.md` Decision 1 exactly: `b1` now derives from
`cand->time_offset` unclamped, `tone_col` derives from `b - (int)cand->time_offset`
unclamped. Re-derived the in-bounds proof independently (not taken on task 1.2's word):
for `time_offset < 0`, `b0 = 0`, so `tone_col` ranges over
`[|time_offset|, min(FT8_NN, num_blocks - time_offset))` — strictly inside `[0, FT8_NN)`
for every `b` in `[b0, b1)`. No out-of-bounds read possible. Version bump,
`Ft8LibInterop.cs`, and the ten mechanical test-mock updates (one-method stub for the new
`GetLastSnrTerms` interface member) are all consistent. **Approved.**

## 2. §6.2 — AC-N1 regression, re-classified

Independently re-diffed `replay_{win,linux}_amend2.json` (pre-fix, shim 20260045) against
`replay_{win,linux}_negdt_fix.json` (post-fix, shim 20260046) myself, not from the
Developer's numbers:

| | win-x64 | linux-x64 |
|---|---|---|
| Cycles differing | 85/250 | 85/250 |
| Same 85 timestamps both platforms | yes | yes |
| Entry diffs, `dt >= 0` | 0 | 0 |
| Entry diffs, `dt < 0` | 95 | 95 |
| Diffs touching message/freq/dt | 0 | 0 |
| Diffs, SNR-only | 95 | 95 |
| SNR delta range | 1-15 dB | 1-15 dB |

Exact match to the Developer's report. `dll_sha256` embedded in each JSON matches the
recorded rebuild hash. **Conclusion: `tasks.md` §6.2's own premise — "every recorded
decode `[has] time_offset >= 0`" for the AC-N1 corpus — is false; the corpus is real 20 m
off-air traffic and already contains negative-`dt` decodes.** The fix's own invariant (no
`dt >= 0` decode touched) holds without exception on both platforms. This is the fix
working as designed, not a regression. **§6.2 re-classified PASS** under the corrected
premise — see `tasks.md` for the updated checkbox. The wording correction to
`proposal.md`/`tasks.md` §6.1's requirement text and the `ft8-decoder` spec delta's
"Existing real-decode replays are unaffected (regression)" scenario is left to the
Architect (spec-authorship boundary, HK-015) — flagging again here since it's still open.

## 3. §7 — B-dt-C3 acceptance re-run (this session's own run)

Per task 7.1, re-pinned the harness before running rather than reusing the pre-fix pin:
`qa/rr-study/r2-coherent-llr-instrument/snr_terms_ctypes.py`'s `CURRENT_DLL_SHA256`/
`CURRENT_SHIM_VERSION` updated to `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`
/ `20260046`, verified against `sha256sum` of the on-disk rebuilt
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` directly (not copied from a report). This is
an uncommitted working-tree change on this branch, same status as everything else this
session.

Ran `b_dt_c3_offline_negative_dt.py` unchanged. ROW 0 validity clear on all four limbs
(placement exact on all 10 parts, err=0; exact reproduction of B-dt-C1's part-0/part-1
numbers to six decimal places; 50/50 cells matched; straddle present). Result:

**`max_p Δ(p) = 0.400 dB`** at `p_step = 8` — **20× under** the pre-registered 8.0 dB bar.
`neg_side_flatness_db = 0.400 dB`. `noise_spread_db = 0.100 dB` (unchanged from pre-fix,
as design.md's Non-Goals predicted — `compute_local_noise_floor_db` is untouched by this
fix). `n_matched = 50/50`, `n_unmatched = 0`. **Pre-registered acceptance condition
(§8 of the original B-dt-C3 spec, restated in `design.md` Decision 4 item 2) MET.**

### Before/after, direct comparison

Pre-fix numbers are the committed `qa/rr-study/2026-08-22-1454-qa-to-architect-b-dt-c3-results.md`
§5 table (arm B-dt-C3, shim 20260045) — see note below on why this markdown, not the raw
JSON, is the source for the pre-fix side.

| part | `true_dt` | pre `E(p)` | post `E(p)` | recovered | pre `signal_db` | post `signal_db` |
|---|---|---|---|---|---|---|
| 0 | +0.08 | +2.000 | +2.000 | 0.000 | −7.575 | −7.575 |
| 1 | 0.00 | +2.000 | +2.000 | 0.000 | −7.596 | −7.596 |
| 2 | −0.08 | +2.000 | +2.000 | 0.000 | −7.643 | −7.643 |
| 3 | −0.16 | +2.000 | +2.000 | 0.000 | −7.915 | −7.915 |
| **4** | **−0.24** | **−15.400** | **+2.000** | **+17.400** | −24.818 | −7.672 |
| 5 | −0.32 | −15.400 | +1.800 | +17.200 | −24.919 | −7.929 |
| 6 | −0.48 | −15.800 | +1.800 | +17.600 | −25.392 | −7.987 |
| 7 | −0.72 | −16.600 | +2.000 | +18.600 | −25.985 | −7.628 |
| 8 | −0.96 | −16.400 | +1.600 | +18.000 | −25.959 | −7.977 |
| 9 | −1.20 | −18.400 | +1.800 | +20.200 | −27.786 | −7.638 |

Parts 0-3 (`time_offset >= 0` throughout the sweep, never entered the clamped branch) are
bit-identical pre/post, as the fix's own invariant requires. Parts 4-9 recover 17.2-20.2 dB
and land back in the same −7.6 to −8.0 dB band the unaffected parts already occupy — the
whole sweep is flat post-fix, where it stepped by 17.4 dB pre-fix. The recovered amount at
part 4 (+17.400) matches the pre-fix report's own `max_delta` (17.4 dB) exactly, which is
the expected identity (the pre-fix "collapse relative to baseline" and the post-fix
"recovery relative to pre-fix" are the same quantity, sign-flipped) — a useful internal
consistency check, not an independent confirmation.

### Housekeeping note — pre-fix raw JSON/log overwritten, recorded here as the fix

`b_dt_c3_offline_negative_dt.py` writes to a fixed path,
`results/b_dt_c3_report.json` (and `results/b_dt_c3_run.log`), with no run-specific
suffix. Both files were **untracked** (never git-committed, despite `design.md`/
`proposal.md` calling `b_dt_c3_report.json` "committed" — another instance of the same
premise-drift this change's own §6.2 finding surfaced). Running the acceptance re-run
therefore overwrote the pre-fix JSON/log in place; there is no git blob to recover them
from. No data is actually lost: the pre-fix numbers used in the before/after table above
come from `qa/rr-study/2026-08-22-1454-...md`'s own §5 table, which was written before
this run and is unaffected — but the raw machine-readable pre-fix artifact is gone.
**Recommend, as a small process fix (Architect/Captain call, not applying it myself):**
either the harness should accept an output-path override, or QA process should `cp` the
prior report aside before any future re-run. Flagging rather than quietly proceeding.

## 4. Sign-off

`tasks.md` §7.1-7.3 checked off below with these results. §7.4's own text is now moot
(QA ran it, as it anticipated as an allowed convenience) — this document is the QA
sign-off it calls for. **§8 (spec sync) and §9 (housekeeping) remain open** and still
belong to the Architect / Captain: §8 in particular should fold in the §6.2 premise
correction (this document + the Developer's own escalation) at the same time as the
version-reference merge, rather than as a second pass.
