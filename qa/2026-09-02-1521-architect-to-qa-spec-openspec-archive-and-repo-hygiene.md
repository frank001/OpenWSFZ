# Architect → QA — OpenSpec archive + repo hygiene

**Authored:** 2026-09-02 15:21Z (mechanically derived, `date -u`, HK-017)
**From:** Architect · **To:** QA (HK-015 — this is a spec, not a dev-task; QA authors any dev-task
that falls out of it)
**Base:** `main` @ `47a781c` (post-PR-#138), shim `20260049`
**Product Owner rulings folded in:** 2026-09-02 — (1) SUP-B §14–16 are **moot, close and archive**;
(2) the webtests dev-task records **land on `main`**.

---

## 0. Why this exists, and why the order is load-bearing

`F-001` Option A is closed and merged. Sitting in front of the next queue item (`F-001 R5 L3` +
site-6) is an OpenSpec hygiene backlog that is **larger than the board recorded**: the board names
one unarchived change, there are **three**, and all three are already merged into `main`.

| Change | Merged into `main` | Tasks `[x]`/`[ ]` | Archived |
|---|---|---|---|
| `external-reporting-single-connection` | yes | 22 / 1 | no |
| `f001-sup-b-instrumented-suppression-sizing` | yes | 37 / 18 | no |
| `f001-h12-unique-match-suppression` | yes (PR #138) | **0 / 43** | no |

Verified consequences (measured on `main`, not inherited from the board):

1. **The base spec is three versions stale.** `openspec/specs/ft8lib-interop/spec.md` reads
   `20260046` at lines 49, 53 and 172. `main` ships `20260049`
   (`src/OpenWSFZ.Ft8/Native/ft8_shim.h:680`, `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:405`).

2. **🔴 ORDER IS LOAD-BEARING AND ONE DIRECTION SILENTLY DESTROYS HISTORY.** `SUP-B` and `h12` each
   carry a `## MODIFIED Requirements` block rewriting **the same requirement** — *"ABI self-test on
   first load"*. Confirmed by header scan of both delta files.
   - Archive `h12` **first** ⇒ base spec version history jumps `20260046 → 20260049`, silently
     dropping the `20260047`/`20260048` entries **and** losing `SUP-B`'s two `## ADDED` diagnostic
     export requirements.
   - Archive `SUP-B` **after** `h12` ⇒ the pin **regresses** to `20260048`.
   - **⇒ `SUP-B` MUST be spec-synced and archived BEFORE `h12`. This is not a preference.**
   - `external-reporting-single-connection` touches different capabilities (`configuration`,
     `external-reporting`) ⇒ **no collision, any order**.

3. **`h12`'s `tasks.md` is a false record** — 43 boxes unchecked for work that is built
   (`b616b6d`), QA-reviewed, replayed (`27d9c6a`), Architect-ruled (`8071391`) and merged (#138).

---

## 1. Preconditions — evaluate mechanically, STOP if any fails

Run before touching anything. Each is a hard predicate, not a judgement (HK-021(r)).

```bash
cd "D:/Projects/claude/OpenWSFZ"
git rev-parse --abbrev-ref HEAD            # MUST be: main
git rev-parse HEAD                         # MUST be: 47a781c (or later, if main advanced)
git status --porcelain | grep -v '^?? pre_merge_check_'   # MUST be empty
openspec validate --strict --all           # record the pass/fail count BEFORE any edit
```

**If `main` has advanced past `47a781c`, STOP and escalate** — this spec's version arithmetic was
computed against that tip.

Work on a new branch off `main`: `qa/2026-09-02-openspec-archive-and-hygiene`.

**Scope note (HK-011):** every task below is docs / `.gitignore` / branch refs. **No `src/` change,
no rebuild, no Developer session, no shim bump.** If any task appears to require a `src/` edit, that
is a defect in this spec — **stop and escalate, do not improvise.**

---

## 2. Task A — archive `external-reporting-single-connection` (independent, do first)

Lowest risk, and doing it first proves the archive mechanism works before the ordered pair.

1. Resolve the single open task. Read it; if it is genuinely complete on `main`, tick it with a
   one-line evidence note. **If it is not complete, do NOT tick it — escalate.**
2. `opsx:archive` the change.
3. `openspec validate --strict --all` MUST pass.

---

## 3. Task B — back-fill `h12`'s `tasks.md` as a RECORD CORRECTION (before Task D)

🔴 **This is a record correction, not a formality. Do not tick boxes to make tooling pass.**

For each of the 43 tasks, tick **only** if you can name the artefact that discharges it — a commit
SHA, a file path, a test result, or a task-list line in the merged dev-task
(`dev-tasks/2026-09-01-f001-h12-unique-match-suppression.md`). Known anchors:

- Build: `b616b6d` · QA replay + AC results: `27d9c6a` · Architect ruling: `8071391`, `5786709`
- Version bump: `cc0f5e3` · Merge: PR #138 → `47a781c`

**Tasks that must NOT be ticked as done — mark them explicitly instead:**

- **AC-2** — Architect ruled it **VOID BY CONSTRUCTION** on 2026-09-02 (`8071391`): the encoder
  hard-wires `n12=0` per CQ, so the condition AC-2 tests cannot arise. Mark
  `[~] VOID BY CONSTRUCTION — see 8071391`, **not** `[x]`.
- **macOS ARM64 rebuild** — carries the same standing "not rebuilt locally, owned by the
  `macos-latest` CI leg" deferral as every prior native change. Mark as deferred with that reason.
  🛑 This is **expected and permanent** on a Windows box — it is not a finding, do not raise it.

Any task you can neither discharge nor classify ⇒ **escalate that specific task**, do not guess.

---

## 4. Task C — `SUP-B`: close §14–16 as superseded, spec-sync, archive (FIRST of the ordered pair)

### 4.1 Close the 18 open tasks — by classification, not by ticking

**PO ruling 2026-09-02: §14–16 are MOOT.** Those legs existed to size per-band ambiguity so we could
decide *whether to suppress per band*. The PO decided **Option A — unconditional unique-match
suppression on all bands** (`78713b8`), and it shipped at `20260049`. The question the measurement
was going to answer no longer has a consequence attached.

Mark each of §14.1–14.4, §15.1–15.3, §16.1–16.4 as:

```
- [~] SUPERSEDED by PO Option A ruling 2026-09-01 (78713b8) — per-band sizing has no
      consequence once suppression is unconditional on all bands.
```

**Use `[~]` or the repo's existing superseded convention — NEVER `[x]`.** These legs did not run;
recording them as done would put a false measurement claim into the archive.

Remaining open tasks and their disposition:
- **§3.3, §10.3 (macOS ARM64)** — standing CI-owned deferral, as §3 above.
- **§17.1–17.3 (Spec Sync)** — these are Task C.2 below; tick them as you complete it.
- **§18.1–18.2 (Housekeeping)** — these are Task H below; tick as completed.

### 4.2 Spec-sync — merge the deltas into the base specs

Per `SUP-B` §17.1–17.2, merge into `openspec/specs/`:
- `specs/ft8lib-interop/spec.md` — the `MODIFIED` ABI self-test requirement (pin → `20260048`) **and**
  both `ADDED` diagnostic-export requirements (Phase 1 three getters `20260047`; Phase 2 cluster
  table `20260048`).
- `specs/hashed-callsign-resolution/spec.md` — both `ADDED` observable-sizing requirements.

🔴 **Preserve the full version-history chain in the ABI paragraph.** It is a running narrative
(`20260021` → `20260049`), not a single value. `20260047` and `20260048` must be **inserted**, and
the existing `20260046`-and-earlier history carried forward verbatim. Do not rewrite prose you are
not adding to.

⚠️ Both `20260047` and `20260048` were **MEASURE-ONLY** — no decode-output change. Say so; it is the
contrast that makes `20260049` legible.

### 4.3 Archive

`opsx:archive` `f001-sup-b-instrumented-suppression-sizing`, then
`openspec validate --strict --all` MUST pass. **Do not proceed to Task D until it does.**

---

## 5. Task D — archive `f001-h12-unique-match-suppression` (SECOND, only after Task C passes)

Gate — assert before starting:

```bash
grep -c "20260048" openspec/specs/ft8lib-interop/spec.md    # MUST be >= 1
ls openspec/changes/f001-sup-b-instrumented-suppression-sizing 2>/dev/null   # MUST NOT exist
```

If either fails, Task C is incomplete ⇒ **STOP**.

Then spec-sync `h12`'s deltas (pin `20260048` → `20260049`, plus the `ADDED` suppression-count
export requirement) and `opsx:archive` it.

🔴 **`20260049` is the first bump in this family that CHANGES DECODE OUTPUT.** The base spec must say
that plainly and must not blur it with the two measure-only bumps before it.

---

## 6. Task E — verification gate (mechanical, run after Tasks A–D)

**All of these must hold. Any failure ⇒ STOP and escalate; do not hand-patch the base spec to make
the gate pass.**

```bash
cd "D:/Projects/claude/OpenWSFZ"
# 1. Base spec pins the shipped version
grep -c "20260049" openspec/specs/ft8lib-interop/spec.md          # >= 1
# 2. Base spec no longer claims the stale pin as current
grep -n "20260046" openspec/specs/ft8lib-interop/spec.md          # only inside HISTORY prose
# 3. Intermediate history survived the ordered archive  <-- THE POINT OF THE ORDERING
grep -c "20260047" openspec/specs/ft8lib-interop/spec.md          # >= 1
grep -c "20260048" openspec/specs/ft8lib-interop/spec.md          # >= 1
# 4. Spec pin agrees with the shipped binary
grep "define FT8_SHIM_VERSION" src/OpenWSFZ.Ft8/Native/ft8_shim.h # 20260049
grep "ExpectedShimVersion =" src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs  # 20260049
# 5. No merged change left open
ls openspec/changes/                                              # only archive/ remains
# 6. Validator
openspec validate --strict --all                                  # pass, count >= the §1 baseline
```

Check 3 is the one that matters — it is the **only** check that fails if the archive order was
wrong, and it fails **silently** otherwise (the spec would still validate, just with history
deleted). Do not skip it because checks 1/2 look green (HK-022: a green result answers only what it
was pointed at).

---

## 7. Task F — land the webtests dev-task records

**PO ruling 2026-09-02: land them.** Branch `qa/2026-09-01-webtests-isolation-findings`, 5 commits
(`8b3a261`, `c0fc904`, `a6f0e36`, `59ae2e7`, `014f917`), **docs only**.

Confirm docs-only before merging — this is the assertion that keeps it out of HK-011 territory:

```bash
git diff --stat main...qa/2026-09-01-webtests-isolation-findings -- src/ native/   # MUST be empty
```

If that is non-empty, the branch is **not** docs-only ⇒ **STOP and escalate**; it then needs a
Developer session, not this spec.

Fold into the same branch as Tasks A–E. These records carry the root-cause write-ups for three
fixes already on `main` via PR #137, including the Captain-accepted-as-documented
`CycleArchiveServiceTests` residual flake — which currently has **no record on `main` at all**.

---

## 8. Task G — `.gitignore` gap + the 9 untracked logs

`.gitignore` covers `openswfz-*.log` (line 150) but **not** `pre_merge_check_*.log`, leaving 9
untracked files at repo root:

```
pre_merge_check_2026-08-31.log            pre_merge_check_2026-09-01c.log
pre_merge_check_2026-08-31b.log           pre_merge_check_2026-09-02-f001-merge.log
pre_merge_check_2026-09-01-integration.log pre_merge_check_2026-09-02-f001-merge-run2.log
pre_merge_check_2026-09-01.log            pre_merge_check_2026-09-02-f001-merge-run3.log
pre_merge_check_2026-09-01b.log
```

1. Add `pre_merge_check_*.log` to `.gitignore`, in the existing tooling-log section near line 150.
2. 🔴 **NFR-021 FIRST, DELETE SECOND.** These are run logs and **may contain real callsigns**.
   Grep all 9 for callsign patterns before disposing of them. They are untracked, so they were never
   committed — but **confirm that** (`git log --all --oneline -- pre_merge_check_*.log` ⇒ empty)
   rather than assuming it.
3. Delete them from the working tree once clean, or move to `artefacts/` (blanket-gitignored) if any
   is worth keeping. **Do not commit any of them.**

⚠️ **NFR-021 scanner limits — both live, both recorded:** it skips `.cs`/`.h`/`.yaml`/`.bat`
(21 of 37 file types unscanned) and **misses untracked files entirely**. For these logs the second
limit is the binding one — a CLEAN result from the scanner on an untracked file means nothing.
**Grep them directly.**

This also discharges the board's standing *"console-log `.gitignore` gap"* TODO. Close that TODO in
the same edit.

---

## 9. Task H — branch and worktree sweep

### 9.1 Safe to delete — 19 branches, each verified `0 commits ahead of main`

I verified every one with `git rev-list --count main..<branch>` ⇒ `0`. Re-verify before deleting;
do not trust this list if `main` has moved.

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

Delete with `git branch -d` (**not `-D`**) — `-d` refuses if a branch is not fully merged, which is
exactly the safety net wanted here. **If `-d` refuses on any branch, STOP on that branch and
escalate**; do not reach for `-D`.

🔴 **`docs/architect-record-2026-08-29` — resolve a contradiction before deleting.** It measures
`0 ahead` (⇒ its content is on `main`), but memory records it as *"LOCAL, NOT PUSHED"*. One of those
is stale. **Verify the record file actually exists on `main`** (`git show main:<path>`) before
deleting the branch. If it does not, **STOP** — something is wrong with the inference and an
Architect record is at stake. Report which claim was stale either way, so memory gets corrected.

Also delete the corresponding `origin/` refs where they exist (`git push origin --delete`) —
🔴 **but see §11: pushing needs sign-off. Propose the deletions, do not execute them.**

### 9.2 Do NOT touch — 16 unmerged branches

Every branch below carries commits not on `main`. Leave all of them.

Two need calling out specifically:

- 🔴 **`d001-c4-min-score-sweep` (62 ahead)** — the **raw-LLR exports live ONLY here** and the
  standing §5 calibration (`P(decode | measured BER)`) is blocked on them. Deleting this loses work
  that is not reproducible without a re-run. It is also the branch the stale worktree is pinned to.
- ⚠️ **`qa/sup-b-step7-2026-08-31` (6 ahead)** — SUP-B step-7 work. We are archiving SUP-B as
  superseded; **check whether this branch holds anything not on `main`** before it gets swept in a
  future pass. Not in scope to resolve now — **flag it in your report** so it is a decision, not an
  accident.

### 9.3 Stale worktree

`.claude/worktrees/w1-sec5-calibration` is pinned to `d001-c4-min-score-sweep` at `2f904f0`.

Removing the **worktree** does not delete the **branch** — but confirm that before acting, and
confirm the worktree has no uncommitted changes:

```bash
git -C ".claude/worktrees/w1-sec5-calibration" status --porcelain    # MUST be empty
```

**If it is non-empty, STOP** — there is unsaved calibration work in there. If clean,
`git worktree remove` it and `git worktree prune`.

---

## 10. Task I — memory and board updates (HK-024)

Update **in the same edit** as the result, not later:

- **`BOARD.md`** — record: three changes archived (not one); base spec synced `20260046` → `20260049`
  with `20260047`/`20260048` history preserved; the ordering hazard and that it was handled;
  SUP-B §14–16 closed as superseded by PO ruling; webtests records landed; branch/worktree sweep;
  `.gitignore` gap closed.
- **`MEMORY.md` one-liner** — this discharges the standing 🔴 *"`SUP-B` WAS NEVER SPEC-SYNCED"*
  blocker and the 📌 *"dev-task documentation lives only on an unmerged branch"* note. Retire both.
- **Correct whichever claim §9.1 proves stale** about `docs/architect-record-2026-08-29`.
- Close the *console-log `.gitignore` gap* TODO.

Discharges SUP-B §18.1–18.2.

---

## 11. What QA must NOT do

- 🛑 **Do not run `pre_merge_check.py`.** HK-006 — Captain's initiative **only**.
- 🛑 **Do not push or merge to `main`.** HK-010 — explicit sign-off required. Stop with the branch
  ready and report. This includes the `origin/` branch deletions in §9.1.
- 🛑 **Do not touch `src/` or `native/`, and do not rebuild.** HK-011. Nothing here needs it.
- 🛑 **Do not tick a task you cannot evidence**, and never tick §14–16 or AC-2 as `[x]`.
- 🛑 **Do not `git branch -D`.** If `-d` refuses, that is the safety net working.
- 🛑 **Do not commit any `pre_merge_check_*.log`.**

## 12. Escalate immediately, do not work around, if

1. `main` has advanced past `47a781c`.
2. `opsx:archive` refuses to archive a change with open tasks — **report the refusal, do not tick
   boxes to satisfy it.** That is the tool doing its job; the fix is a ruling, not a workaround.
3. The §6 verification gate fails — **especially check 3** (`20260047`/`20260048` missing ⇒ the
   ordered archive did not do what this spec claims and the base spec's history is wrong).
4. `git diff main...qa/2026-09-01-webtests-isolation-findings -- src/ native/` is non-empty.
5. The `docs/architect-record-2026-08-29` file is not present on `main`.
6. The `w1-sec5-calibration` worktree has uncommitted changes.
7. Any NFR-021 hit in the `pre_merge_check_*.log` files that is **not** `PD2FZ` or a Q-prefix
   synthetic call.

**HK-025 stands: QA may refuse any check in this spec on HK-021(k) grounds without Architect
agreement** — name the check and the evaluation, stop, no partial run.

---

## 13. Deliverable

One QA → Architect report at `qa/<UTC>-qa-to-architect-openspec-archive-and-hygiene-results.md`
(filename and byline both from real `date -u`, in agreement — HK-017), carrying:

- The §1 precondition trace and the §6 verification gate output, **verbatim**.
- The disposition of all 43 `h12` tasks and all 18 `SUP-B` tasks — how each was classified, and
  which (if any) you refused to classify.
- The NFR-021 grep result for the 9 logs.
- The `docs/architect-record-2026-08-29` resolution — which claim was stale.
- The `qa/sup-b-step7-2026-08-31` flag from §9.2.
- Branch/worktree sweep result, and the proposed (not executed) `origin/` deletions.
- Anything this spec got wrong. It was written from a single pass over `main` at `47a781c`; if the
  repo disagrees with it, **the repo is right**.
