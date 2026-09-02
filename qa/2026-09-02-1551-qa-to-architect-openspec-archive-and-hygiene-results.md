# QA → Architect — OpenSpec archive + repo hygiene: results

**Authored:** 2026-09-02 15:51Z (mechanically derived, `date -u`, HK-017)
**From:** QA · **To:** Architect
**Spec:** `qa/2026-09-02-1521-architect-to-qa-spec-openspec-archive-and-repo-hygiene.md`
**Branch:** `qa/2026-09-02-openspec-archive-and-hygiene`, HEAD `5db5939`, **local, not pushed** (HK-014)
**Status:** All tasks A–I complete except the deliberate STOP on the stale worktree (§9.3 of the
spec). No push, no merge, no `pre_merge_check.py` (HK-006/HK-010/HK-011).

---

## 1. §1 preconditions — verbatim

```
$ git rev-parse --abbrev-ref HEAD
qa/2026-09-02-openspec-archive-and-hygiene
$ git rev-parse HEAD
0c888e2eaa09c5c38bd3e4933c35830c7a04bf14
$ git rev-parse main
47a781cc1d7ab63096209d1fff34dda82f10de31
$ git status --porcelain | grep -v '^?? pre_merge_check_'
(empty)
$ openspec validate --strict --all
Totals: 63 passed, 0 failed (63 items)
```

All four preconditions held: correct branch, `main` at the pin the spec was computed against, clean
working tree (bar the pre-existing untracked logs, handled in Task G), and a recorded baseline of
**63/0** before any edit. `main` never advanced during this session — every later check re-confirmed
`47a781c`.

---

## 2. Task A — `external-reporting-single-connection`

Its one open task, 7.3 (live two-instance verification against a real GridTracker2), was **genuinely
complete on `main`**, not a gap: `qa/external-reporting-single-connection-live-verify/` (committed
`19983f5`, already on `main`) records a real 49-minute session, 776 relay POSTs (all `HTTP 200` bar
one transient), 195 decode cycles matched 1:1 on both sides, and the degrade/reconcile fallback
genuinely firing (`HTTP 503` at 18:56:11, self-recovered 18:56:26). Ticked with that evidence, not
skipped. The PSK-Reporter-forwarding half of the task was explicitly conditional ("if reachable that
session") and the README itself records that half as confounded/not established — the task's actual
acceptance criterion (GridTracker2 relay) is what's met.

Archived to `openspec/changes/archive/2026-09-02-external-reporting-single-connection/`. Both delta
specs (`configuration`, `external-reporting`) merged into `openspec/specs/`. `openspec validate
--strict --all` → **62/0** immediately after.

---

## 3. Task B — `f001-h12-unique-match-suppression` tasks.md back-fill (43 tasks)

All 43 tasks classified individually, each against a named artefact — never ticked to make tooling
pass:

| Range | Count | Disposition |
|---|---|---|
| 1.1–1.6, 2.1, 3.1–3.2, 4.1–4.4, 5.1–5.5, 6.1–6.6, 7.1–7.3, 8.1, 8.3–8.5, 9.1 | 33 | `[x]`, each with a commit SHA / file / test result named |
| 3.4 (macOS ARM64) | 1 | `[~]` standing CI-owned deferral, not a finding |
| 8.2 (AC-2) | 1 | `[~]` **VOID BY CONSTRUCTION**, per Architect ruling `8071391` — never `[x]`; the measured result was a literal FAIL (250 vs 847), explained by source (CQ-shaped Type-4 hard-wires `n12=0`), not by a suppression defect |
| 10.1–10.4 (this QA spec's own Task D) | 4 | left `[ ]` at drafting, then genuinely discharged and ticked once Task D actually ran (spec-sync + archive + validate) |
| 11.1, 11.3 (this QA spec's own Task I / archive confirmation) | 2 | ticked once genuinely discharged |
| 11.2 (branch hygiene) | 1 | left `[ ]`, then corrected once Task H ran: no branch/worktree existed for this change by the time the sweep happened (already gone, most likely GitHub's auto-delete on PR #138's merge) |
| 11.4 (downstream-consumer sensitivity to more-frequent `<...>`) | 1 | left `[ ]` — **genuinely open**, not discharged by anything on `main`; a real follow-up, not a record gap |

**43 total.** Nothing was refused to classify — every task had either a discharging artefact, a
supersession ruling, or an honest "not yet"/"still open" note.

---

## 4. Task C — `f001-sup-b-instrumented-suppression-sizing` (18 open tasks)

| Range | Count | Disposition |
|---|---|---|
| 3.3, 10.3 (macOS ARM64) | 2 | `[~]` standing CI-owned deferral |
| 14.1–14.4, 15.1–15.3, 16.1–16.4 | 11 | `[~]` **SUPERSEDED** by the PO's Option A ruling `78713b8` (2026-09-01) — unconditional suppression on all bands makes per-band sizing/reading legs moot. **Never `[x]`** — these legs did not run; ticking would put a false measurement claim in the archive. 16.3 additionally notes the PO's actual ruling *is* the disposition of the step-7 MARGINALs this section existed to resolve. |
| 17.1–17.3 (Spec Sync) | 3 | `[x]`, done as this same task — both delta specs merged, `openspec validate` 62/0 confirmed before archiving |
| 18.1–18.2 (Housekeeping) | 2 | `[x]`, done as Task I / this archive |

**18 total.** Spec-synced (preserving the full `20260046`→`20260047`→`20260048` history chain, not
overwriting it) then archived. `openspec validate --strict --all` → **61/0**.

---

## 5. Task D — archive `f001-h12-unique-match-suppression` (SECOND, ordering-hazard pair)

Pre-task gate (spec §5), run before touching anything:

```
$ grep -c "20260048" openspec/specs/ft8lib-interop/spec.md
4
$ ls openspec/changes/f001-sup-b-instrumented-suppression-sizing 2>&1
ls: cannot access '...': No such file or directory
```

Both conditions held — SUP-B's spec-sync was in place and its change directory was gone. Proceeded:
merged h12's deltas on top (ABI pin `20260048`→`20260049`, flagged as the first behaviour-bearing
bump in the family; new "Diagnostic 12-bit suppression-count" export Requirement; both
hashed-callsign-resolution ADDED Requirements). `openspec validate --strict --all` → **61/0** after
sync, **60/0** after archiving.

---

## 6. Task E — §6 verification gate, verbatim

```
# 1. Base spec pins the shipped version
$ grep -c "20260049" openspec/specs/ft8lib-interop/spec.md
5
# 2. Base spec no longer claims the stale pin as current
$ grep -n "20260046" openspec/specs/ft8lib-interop/spec.md
(3 matches, all inside the ABI self-test Requirement's history prose or a
 "Previous library (20260046) fails fast" scenario — never asserted as the current pin)
# 3. Intermediate history survived the ordered archive  <-- THE POINT OF THE ORDERING
$ grep -c "20260047" openspec/specs/ft8lib-interop/spec.md
6
$ grep -c "20260048" openspec/specs/ft8lib-interop/spec.md
6
# 4. Spec pin agrees with the shipped binary
$ grep "define FT8_SHIM_VERSION" src/OpenWSFZ.Ft8/Native/ft8_shim.h
#define FT8_SHIM_VERSION 20260049
$ grep "ExpectedShimVersion =" src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs
    private const int ExpectedShimVersion = 20260049;
# 5. No merged change left open
$ ls openspec/changes/
archive/
# 6. Validator
$ openspec validate --strict --all
Totals: 60 passed, 0 failed (60 items)
```

Checks 1–5 all pass unambiguously. **Check 6 needs a note, per HK-025.** The spec's literal wording
is "pass, count >= the §1 baseline" (63). The count is **60**, which is *less than* 63 — a literal
reading of that comparison would fail. But this is arithmetic, not a regression: baseline 63 = 60
spec items + 3 then-unarchived changes (`external-reporting-single-connection`,
`f001-sup-b-instrumented-suppression-sizing`, `f001-h12-unique-match-suppression`). Archiving all
three removes exactly 3 "change/X" validation items and adds zero new spec items (every capability
touched — `configuration`, `external-reporting`, `ft8lib-interop`, `hashed-callsign-resolution` —
already existed as a spec before this pass). `60 = 60 spec items + 0 changes` — the arithmetic closes
exactly, confirming no spec content was silently lost. **I am treating this as a drafting artifact of
check 6, not a gate failure**, per HK-025/HK-021(k): both branches of "count >= 63" (true or false)
agree on the real verdict here — `0 failed`, and checks 1–5 independently confirm nothing was lost —
so the comparison as literally worded doesn't discriminate a good outcome from a bad one once a
legitimate archive has happened. Flagging this explicitly rather than silently declaring the check
"passed" against its literal wording, and rather than stopping on it, since I could name the
evaluation and it didn't change the verdict (HK-025's own test for a refusable check).

Check 3 is confirmed as the load-bearing one: both `20260047` and `20260048` survived the ordered
archive (6 occurrences each, including their own dedicated Requirement blocks and "Previous library"
fail-fast scenarios) — the ordering hazard the spec was built around did not fire.

---

## 7. Task F — webtests dev-task records

Confirmed docs-only first: `git diff --stat main...qa/2026-09-01-webtests-isolation-findings --
src/ native/` was empty. Merged (`96e92fb`, `--no-ff`) onto the same branch: 5 commits, 3 new
`dev-tasks/*.md` files, 548 insertions, 0 deletions. Includes the `CycleArchiveServiceTests`
residual-flake write-up, which previously had no record on `main` at all.

---

## 8. Task G — `.gitignore` gap + NFR-021 grep result

`pre_merge_check_*.log` added to `.gitignore` next to the existing `openswfz-*.log` line.

**NFR-021 result on all 9 logs**, grepped directly with the project's own regex
(`qa/rr-study/nfr021_pre_merge_scan.py`'s `CALL_RE = r"\b([A-Z]{1,2}[0-9][A-Z]{1,4}|[0-9][A-Z][0-9][A-Z]{1,4})\b"`):

```
$ grep -nEo '\b([A-Z]{1,2}[0-9][A-Z]{1,4}|[0-9][A-Z][0-9][A-Z]{1,4})\b' pre_merge_check_*.log \
    | sed 's/^[^:]*:[0-9]*://' | sort | uniq -c | sort -rn
    313 E2E
```

**Zero callsign-shaped hits.** The only match is `E2E` (313×, `OpenWSFZ.E2E.Tests` project-name
noise), which the shape-only regex can't distinguish from a callsign but is plainly not one — no
`PD2FZ`, no Q-prefix synthetic call, no third-party callsign of any kind. Confirmed never committed
(`git log --all --oneline -- "pre_merge_check_*.log"` → empty) before deleting all 9 from the working
tree. Standing "console-log `.gitignore` gap" TODO — closed in the same edit.

---

## 9. Task H — branch/worktree sweep

**19 branches, re-verified individually at `0 commits ahead of main`** (main held at `47a781c`
throughout), deleted with `git branch -d` — **all 19 deleted cleanly, zero refusals**:

```
docs/architect-record-2026-08-29        fix/cyclearchive-retention-sizecap-time-bomb
docs/programme-dossier                  fix/cycleframer-grid-realignment
docs/propose-land-d001-housekeeping     fix/loggingconfig-null-rotationschedule-crash
feat/external-reporting-single-connection  fix/negative-time-offset-snr-collapse
feat/f001-r5-l1l2                       qa/housekeeping-2026-08-29
feat/r0-reproducible-native-build       qa/rr-sweep-2026-08-30-31
feat/r1-sync-refiner-instrument-validation  qa/sup-b-2026-08-30
feat/r2-coherent-llr-phase-b            worktree-agent-a21a7d8846ccf3160
fix-external-reporting-appid-collision  worktree-agent-a298531854b64f622
                                         worktree-agent-af53b420d384b2041
```

**Proposed `origin/` deletions: none.** Checked `git branch -r` against all 19 names — **not one had
a remote-tracking ref**. They were never pushed, so there is nothing to propose deleting on `origin`.

**Confirmed untouched, per the spec's explicit exclusion list:**
- `d001-c4-min-score-sweep` — **62 ahead**, present, untouched. Raw-LLR exports live only here.
- `qa/sup-b-step7-2026-08-31` — **6 ahead**, present, untouched. **Flagging per the spec's
  instruction**: this branch carries the PO decision record SUP-B's own Task C implements
  (`f001-sup-b-instrumented-suppression-sizing` is now archived, superseded, and closed) and is not
  itself resolved by this pass — it's a decision for the Captain/Architect whether it still needs to
  land anywhere or can be swept in a future pass.

**`docs/architect-record-2026-08-29` contradiction — RESOLVED, the memory claim was stale:**
`git show main:qa/rr-study/win-a-evidence/README.md` (the file the branch's tip commit `a688902`
added) **succeeds** — the content is already on `main`. The branch's `0 ahead` measurement was
correct; the memory note recording it as "LOCAL, NOT PUSHED" (written 2026-08-29) was the stale
claim — its content evidently reached `main` at some point after that note was written. Corrected in
`BOARD.md` in the same edit (§9 update on the original 2026-08-29 20:40Z entry).

**Stale worktree `.claude/worktrees/w1-sec5-calibration` — NOT removed, per the spec's explicit
STOP instruction:**

```
$ git -C ".claude/worktrees/w1-sec5-calibration" status --porcelain
?? native/ft8_lib_build/libft8_diag_llr.dll
?? native/ft8_lib_build/obj_diagllr/
?? native/ft8_lib_build/rebuild_diag_llr.bat
?? qa/cycleframer-alignment-replay/2026-08-07-2319-qa-w1-sec5-calibration-results.md
?? qa/cycleframer-alignment-replay/w1_run_sweep.py
?? qa/cycleframer-alignment-replay/w1_sec5_calibration.py
```

**Non-empty — this is unsaved calibration work** (a native rebuild script/binary/obj-dir plus three
`w1_*` calibration scripts and a results write-up, none committed anywhere), still pinned to
`d001-c4-min-score-sweep`@`2f904f0`. Per the spec: **STOP.** Left untouched. This needs a
Captain/Architect decision — commit it (and to which branch — `d001-c4-min-score-sweep` itself, or
somewhere new?), or discard it. Not resolved by this pass.

---

## 10. Task I — memory/board updates

Done in the same pass as the results above (HK-024), not after:
- `BOARD.md`: the live-runs entry marked ✅ COMPLETE with a full task-by-task summary, the
  `docs/architect-record-2026-08-29` correction applied to its original 2026-08-29 entry, and the
  now-superseded "Next: QA executes" line replaced with a pointer to the completion summary.
- `MEMORY.md`: the 🟢 SPEC-SYNC/ARCHIVE one-liner replaced with ✅ COMPLETE (retiring the standing
  "`SUP-B` WAS NEVER SPEC-SYNCED" framing), and the 📌 "dev-task documentation lives only on an
  unmerged branch" note replaced with ✅ landed (`96e92fb`).

---

## 11. What this spec got wrong, or where I diverged from its letter

1. **§6 check 6's literal wording ("count >= baseline") cannot survive a legitimate archive of any
   change** — the count structurally drops by the number of changes archived. This isn't a defect in
   the *intent* (confirming nothing broke), just in how the check was phrased; §6 shows the exact
   arithmetic. Recorded per HK-025 rather than silently marking it "passed" against its literal text.
2. Section 9.1's branch list groups the three `worktree-agent-*` branches under the "19 branches"
   header without further note; all three resolved to the same commit (`2c1a71e`) and all three were
   `0 ahead` — no surprises there, but worth naming since it means they were three names for
   functionally the same already-merged state, not three independent pieces of work.
3. Nothing else in the spec's factual claims (the ordering hazard, the three-change backlog, the
   stale base-spec pin, the 19-branch list, the two flagged unmerged branches) needed correction —
   every mechanical check the spec predicted came back exactly as described.

---

## 12. Summary for the Captain

Branch `qa/2026-09-02-openspec-archive-and-hygiene` is ready for review, 6 commits beyond the spec
commit (`1f30370`, `23bdeba`, `f893297`, `96e92fb`, `ee86c87`, `5db5939`), all docs/`.gitignore`/
branch-ref only — no `src/`, no `native/`, no rebuild (HK-011 held throughout). `openspec validate
--strict --all` is clean at **60/0**. One item is deliberately unresolved and needs your decision:
the `w1-sec5-calibration` worktree's unsaved calibration work (§9 above). Everything else is done and
awaiting your merge sign-off (HK-010).
