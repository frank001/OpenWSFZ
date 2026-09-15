# Developer handoff: `build_linux.sh` hardcodes `FT8_ROOT` to the Architect's worktree

**Authored by:** QA, 2026-09-15 14:55Z (per HK-000/HK-015), timestamp per `date -u` (HK-017).
**Status:** ✅ **Captain signed off for Developer pickup, 2026-09-15 14:56Z.** Per HK-011, the
Developer session implementing this does not run `pre_merge_check.py` or push/merge on its own
initiative (QA verifies, Captain signs off the merge separately, HK-010).
**Tracking:** No GitHub issue filed — this is a build-script defect, not a flake (`TESTING_STRATEGY.md`
§11's issue-filing requirement doesn't apply); relayed via `BOARD.md` 2026-09-15T14:53Z entry and an
Architect cross-session message re-confirming the defect, both citing QA's own 2026-09-14 finding.
**Branch:** own short branch off `main`, name at the Developer's/Captain's discretion. **Do not
combine with the flake fix branch** (`dev-tasks/2026-09-14-cyclearchiveservicetests-manifestgapmarker-
ioexception-repeat-flake.md` — its own §0 says "do not combine with any other fix"; two independent
workstreams, HK-003 branch hygiene). The Captain's ask was to *pair* the two tasks for one Developer
pickup, not put them on one branch — two branches, one pickup.

---

## 0. The defect (found by QA 2026-09-14, reviewing the PASSBAND-140 ship; re-confirmed here directly
   from source before writing this task, HK-018)

`native/ft8_lib_build/build_linux.sh`:

```
10: FT8_ROOT=/mnt/d/Projects/claude/OpenWSFZ
...
63: cp "$BUILD_DIR/libft8.so" "$FT8_ROOT/src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so"
```

Line 10 hardcodes `FT8_ROOT` to the Architect's own worktree path
(`/mnt/d/Projects/claude/OpenWSFZ`, i.e. `D:\Projects\claude\OpenWSFZ` under WSL). Every other path in
the script (`BUILD_DIR`, `SRC_DIR`, `LIB_SRC`, `PATCHED`, `OBJ_DIR`) derives from `FT8_ROOT`, so this
one line steers the whole build. Line 63's `cp` then writes the freshly-built `.so` straight into that
hardcoded tree's **tracked** `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` — not wherever the script
was actually invoked from.

**Effect:** run this script from any worktree other than the Architect's own (`QA`'s or the
`Developer`'s, both of which live under `worktrees\` and are separate git worktrees per
`operational-note-persona-worktrees-2026-09-06.md`), and:
- Compilation reads source from the Architect's `native/ft8_lib_vendor/` and `native/ft8_lib_build/
  patched/`, not the invoking worktree's own checkout — silently building the wrong revision if the
  two trees have diverged.
- The freshly-built `.so` lands in the **Architect's** tracked file, not the invoking worktree's,
  which never sees the rebuild it just ran, and the Architect's tree gets a binary it didn't ask for.

This was caught in a WSL run from `qa/base` while confirming the PASSBAND-140 ship's Linux binary was
current: the build silently succeeded against stale/wrong-tree source, traced to 246 resulting
Linux-side test failures before the actual cause (this script) was found. **Not a source-code
correctness defect** — `libft8.so`'s content was fine once rebuilt correctly; this is a build-tooling
landmine, same shape as the `git worktree` split itself was designed to prevent for source, just not
yet closed for this one script.

## 1. Correction to the framing this task was relayed under — verify before reusing

The relay (Architect cross-session message, 2026-09-15) describes this as "the same landmine family as
the **already-fixed** `rebuild_shim.bat`." **That characterisation does not hold up against the file
as it stands today.** I read `native/ft8_lib_build/rebuild_shim.bat` directly before writing this task
(HK-018) and it is **not fixed** for this defect: it hardcodes `D:\Projects\claude\OpenWSFZ\...`
absolute paths **63 times** across the file (every `/I`, every `/Fo`, every source path), with no
`%~dp0`-style or other derivation from the script's own location anywhere in it. `BOARD.md`'s own
prior wording only ever calls this "the **known** `rebuild_shim.bat` landmine" (i.e. previously
identified) — never "fixed." The `rebuild_shim.bat` fix that *did* ship (shim `20260048`→`20260049`,
the D5 `/EXPORT:` list gap) is a **different** landmine in the same file — missing Windows export
entries, nothing to do with the hardcoded root path.

**Consequence for this task:** do not point the Developer at `rebuild_shim.bat` as a worked example of
the fix pattern — it isn't one. `rebuild_shim.bat` carries the identical hardcoded-root defect, unfixed,
today. That script is **out of scope for this task** (Windows build, not what was asked; fixing it
would be a second, larger diff the Captain hasn't asked for) — but it should be named on the board as a
known sibling landmine so it isn't lost. QA will add that note to `BOARD.md` alongside this task.

## 2. Recommended fix

Derive `FT8_ROOT` from the script's own location instead of a literal path, so the script is correct
regardless of which worktree invokes it. Either of:

```bash
FT8_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
```

(script lives at `native/ft8_lib_build/build_linux.sh`, so two levels up is the worktree root), or

```bash
FT8_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
```

Developer's call which — state which was chosen and why in the closing commit. Either must resolve
correctly when the script is invoked via a relative path, an absolute path, and via `bash
build_linux.sh` from inside `native/ft8_lib_build/` itself (three invocation shapes to check, not just
one).

Do **not**:
- Hardcode a different fixed path (e.g. swap the Architect's path for QA's or the Developer's own) —
  that only relocates the landmine, it doesn't clear it.
- Touch `rebuild_shim.bat` as part of this diff (§1 — separate, larger, not asked for here).
- Touch anything under `native/ft8_lib_vendor/` or the `patched/` sources — this is a path-resolution
  fix only, zero behavioural change to what gets compiled.

## 3. Scope

- `native/ft8_lib_build/build_linux.sh` only.

## 4. Definition of done

- [ ] `FT8_ROOT` derived from the script's own location, not a literal path.
- [ ] Verified from at least two different worktrees (e.g. this task's own worktree plus one other, or
      a temporary clone) that the script builds against *that* worktree's source and writes the `.so`
      into *that* worktree's tracked file — not the Architect's, regardless of which worktree ran it.
- [ ] Verified across the three invocation shapes named in §2 (relative path, absolute path, run from
      inside `native/ft8_lib_build/`).
- [ ] `nm -D` export check (script's own existing §"Verifying exports" step) still passes — confirms
      the rebuilt `.so` is functionally unchanged, only its resolution path changed.
- [ ] `git diff main --stat` confirmed limited to `native/ft8_lib_build/build_linux.sh`.
- [ ] NFR-021 / callsign scan — not applicable (build tooling only, no decode data touched), state so
      explicitly.
- [ ] Closing commit states plainly that `rebuild_shim.bat` carries the identical unfixed defect and is
      deliberately out of scope here (so this isn't mistaken for "the family is now closed").

🛑 **Developer session must stop after implementing and self-verifying — no push, no merge, no
`pre_merge_check.py` run** (HK-010/HK-014/HK-006). QA reviews the diff against this task; the Captain
rules on merge.

## 5. Pairing with the flake fix task

Per the Captain's direction (relayed via the Architect, `BOARD.md` 2026-09-15T14:53Z): this task and
`dev-tasks/2026-09-14-cyclearchiveservicetests-manifestgapmarker-ioexception-repeat-flake.md` are meant
for **one Developer pickup**, not a second round trip — but as **two separate branches**, each scoped
to its own file(s), per that task's own "do not combine" line and HK-003 branch hygiene. Both remain
gated on the Captain's HK-011 sign-off before either reaches a Developer session.
