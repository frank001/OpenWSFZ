# Developer handoff: `rebuild_shim.bat` hardcodes every path to the Architect's worktree

**Authored by:** QA, 2026-09-15 15:15Z (per HK-000/HK-015), timestamp per `date -u` (HK-017).
**Status:** ✅ **Captain signed off directly for Developer pickup, 2026-09-15 15:20Z** (confirmed in
this session, not just the Architect's relay of the decision to author it — HK-011/HK-033 both
require the Captain's own word for this session's sign-off/push, a peer relay doesn't substitute).
Per HK-011, the Developer session implementing this does not run `pre_merge_check.py` or push/merge
on its own initiative (QA verifies, Captain signs off the merge separately, HK-010).
**Tracking:** No GitHub issue — build-tooling defect, not a flake, same posture as the sibling
`build_linux.sh` task.
**Branch:** own short branch off `main`, name at the Developer's/Captain's discretion. **Do not
combine with either sibling task's branch** — `dev-tasks/2026-09-14-cyclearchiveservicetests-
manifestgapmarker-ioexception-repeat-flake.md` and `dev-tasks/2026-09-15-build-linux-sh-hardcoded-
ft8-root-landmine.md` are independent workstreams (HK-003). Three branches, one Developer pickup, per
the Captain's stated preference.

---

## 0. The defect (sibling of the `build_linux.sh` landmine QA fixed as a separate task; found while
   writing that task, not yet actioned until now — Captain: fold it into the same batch)

`native/ft8_lib_build/rebuild_shim.bat` hardcodes the literal path `D:\Projects\claude\OpenWSFZ`
**63 times** across the file — every `/I` include, every `/Fo` object output path, every source `.c`
path, the `/OUT:` DLL path, the object list handed to `link`, and both sides of the final `copy` — as
opposed to deriving it from where the script itself lives. Confirmed directly (`grep -c` against the
literal string, 63 matches, no `%~dp0` or other self-location derivation anywhere in the file).

**This is NOT the same defect as the D5 `/EXPORT:` list landmine already fixed in this file (shim
`20260048`→`20260049`).** That fix added a missing export entry to the existing `/EXPORT:` list (lines
139-160 today) — a different problem, already closed. **Do not touch the `/EXPORT:` list as part of
this task** — it is correct and current as of shim `20260051` (the PASSBAND-140 ship); this task is a
path-resolution fix only.

**Effect, same shape as `build_linux.sh`'s (now-fixed) sibling landmine:** run this script from any
worktree other than the Architect's own (QA's or the Developer's), and every `cl.exe`/`link.exe`
invocation reads source from and writes objects into the Architect's tree regardless of which
worktree invoked the script, and the final `copy` overwrites the Architect's tracked
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` — never the invoking worktree's own. Not yet observed to
have actually bitten anyone (Windows native rebuilds have so far only been run from the Architect's
own worktree, per the board), but it is a landmine sitting under the next Windows rebuild from
anywhere else, same as `build_linux.sh` was.

## 1. Recommended fix

Batch has no `BASH_SOURCE`-equivalent, but the standard idiom for "the directory this .bat file lives
in" is `%~dp0` (drive + path of argument 0, trailing backslash included). Near the top of the script,
before the first `cl` invocation, resolve and normalize the repo root into a variable:

```bat
for %%i in ("%~dp0..\..") do set "FT8_ROOT=%%~fi"
```

(`%~dp0` is `...\native\ft8_lib_build\`; two levels up is the repo root; the `for %%i in (...) do set
"...=%%~fi"` idiom resolves the resulting relative path — including the `..\..`  — into a clean
absolute path, exactly as `%~f` is designed to do.) Then **replace every one of the 63 literal
`D:\Projects\claude\OpenWSFZ` occurrences with `%FT8_ROOT%`**, changing nothing else — same compiler
flags, same object list, same link order, same `/EXPORT:` list, same error-handling labels. This
mirrors `build_linux.sh`'s own fix (`FT8_ROOT` variable, same name, same role) so the two scripts stay
recognizably parallel.

Do **not**:
- Touch the `/EXPORT:` list (§0 — separate, already-closed landmine).
- Touch object compile order, flags, or the `stpcpy_msvc_compat.h` `/FI` on `message.c` — path
  resolution only.
- Attempt to fix the separate, already-known non-reproducibility of this script (no `/Brepro` on the
  `link` step, previously flagged elsewhere on the board as a distinct open item) — out of scope here,
  don't conflate the two.
- Introduce a `git`-based derivation (`git rev-parse --show-toplevel` or similar) without first
  checking whether the Windows environment this script actually runs in has `git` on `PATH` — the
  `build_linux.sh` sibling task found its target WSL distro did not; check the equivalent assumption
  here before relying on it, even though `%~dp0` makes this moot for the recommended fix above.

## 2. Scope

- `native/ft8_lib_build/rebuild_shim.bat` only.

## 3. Definition of done

- [ ] `FT8_ROOT` (or equivalently-named variable) derived from the script's own location via `%~dp0`,
      not a literal path; every one of the 63 hardcoded occurrences replaced.
- [ ] Verified from at least two different worktrees (this task's own plus one other) that the script
      builds against *that* worktree's source and writes the rebuilt `libft8.dll` into *that*
      worktree's tracked file — not the Architect's — regardless of which worktree ran it. This
      requires the MSVC toolchain (`vcvars64.bat`) to actually be available in whichever environment
      runs this verification; state plainly if that constrains which worktree/machine could be used.
- [ ] Verified invoked via a relative path, an absolute path, and from inside
      `native\ft8_lib_build\` itself — three invocation shapes, matching the `build_linux.sh` task's
      own bar.
- [ ] `/EXPORT:` list unchanged — diff the list itself against `main` and confirm zero difference
      beyond whitespace/line-ending noise, if any.
- [ ] `git diff main --stat` confirmed limited to `native/ft8_lib_build/rebuild_shim.bat`.
- [ ] NFR-021 / callsign scan — not applicable (build tooling only, no decode data touched), state so
      explicitly.
- [ ] Closing commit states plainly that this closes the sibling landmine `build_linux.sh`'s own fix
      commit named as deliberately out of scope there, and that the D5 `/EXPORT:` landmine (already
      fixed, different defect) and the separate non-reproducibility issue (not fixed, different
      defect, not this task's concern) are both explicitly NOT touched by this diff.

🛑 **Developer session must stop after implementing and self-verifying — no push, no merge, no
`pre_merge_check.py` run** (HK-010/HK-014/HK-006). QA reviews the diff against this task; the Captain
rules on merge.

## 4. Relationship to the other two tasks in this batch

Per the Captain's direction (relayed via the Architect): this task rides the same Developer pickup as
`dev-tasks/2026-09-14-cyclearchiveservicetests-manifestgapmarker-ioexception-repeat-flake.md` and
`dev-tasks/2026-09-15-build-linux-sh-hardcoded-ft8-root-landmine.md` — **three separate branches, one
pickup**, not combined onto any single branch (HK-003). All three remain independently reviewable and
independently mergeable.
