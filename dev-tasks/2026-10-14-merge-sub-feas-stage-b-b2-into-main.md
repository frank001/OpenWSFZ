# Dev task: merge Stage B B2 (`feat/sub-feas-stage-b`, shim 20260059) with `origin/main`, locally

- **From:** QA. **To:** Developer. **Date:** 2026-10-14. **HK-000 handoff**, on the Architect's request (`arch-9f`, 2026-10-14) and the **Captain's direction: "skip all the testing and go straight for a merge with main locally"**.
- **Branch:** `feat/sub-feas-stage-b` (the existing branch, `origin/feat/sub-feas-stage-b` = `aab18b75`). Do NOT commit to `main`. **Commit locally only; do not push, do not open a PR, do not merge into `main`** (push, PR and merge need the Captain's sign-off, HK-010 / HK-033).
- **Nothing in this task is a measurement.** QA does the one measurement afterwards (see the end).

## 1. Context

Stage B item B2 is a pruned frequency search inside the native sub-feasibility fit (`native/ft8_lib_vendor/subfeas/subfeas_fit.c`, function `freq_search`). It was **accepted on 2026-10-04** (T2 6.737 s → 2.424 s; E2 3,628 of 3,629 signals bit-identical; E3 795 = 795 residual decodes) and **never merged**. `origin/main` is now 155 commits ahead (`76aa48cd`, shim 20260060). Every sol timing so far, including the live-path collapse work, is `main` **without** B2.

Facts the Architect checked on 2026-10-14, and QA re-checked on `git fetch` the same day:

- merge base `e2fdd446`; `origin/main` is 155 commits ahead of the B2 branch; `git diff --stat e2fdd446 origin/main -- native/ft8_lib_vendor/subfeas/` is **empty** (`subfeas_fit.c` is unchanged on `main`), so B2's only source change merges clean;
- `git merge-tree --write-tree --name-only origin/main origin/feat/sub-feas-stage-b` conflicts in **exactly five files**: `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, `src/OpenWSFZ.Ft8/Native/ft8_shim.h`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`. That is the shim number and the binaries, nothing else;
- B2's own diff in the two source files is small: `Ft8LibInterop.cs` changes only `ExpectedShimVersion` (and its remarks), `ft8_shim.h` adds one history entry and changes `#define FT8_SHIM_VERSION`. **B2 adds no export and changes no ABI.**
- **QA found one correction to the brief:** the highest `FT8_SHIM_VERSION` on any `origin/*` ref is **20260061** (`origin/decoding_improvement` and `origin/qa/plausibility-fix-di`), not 20260060 (`main`). The next free number is therefore **20260062** (recheck in Action 5).

**Waived by the Captain/Architect:** the 2026-10-04 ruling's pre-merge T′ and SB3 items (SB3 stays unscored), and every measurement. The only checks are the ones below.

## 2. Actions

1. **Start clean.** `git fetch origin`. Confirm `git rev-parse origin/feat/sub-feas-stage-b` is `aab18b75…` and note `git rev-parse origin/main` (expected `76aa48cd…`; if `main` has moved, merge whatever it is **now** and say so in the report). Your working tree must be clean; if another worktree holds `feat/sub-feas-stage-b`, git will refuse the switch: that is the mechanism, tell QA and stop. Then `git switch -c feat/sub-feas-stage-b origin/feat/sub-feas-stage-b` (or `git switch feat/sub-feas-stage-b` if a local branch already exists; check it equals `aab18b75`).
2. **Guard.** Run `git diff --stat e2fdd446 origin/main -- native/ft8_lib_vendor/subfeas/`. It must print nothing. If it prints anything, **stop and report**: the premise of this merge has changed.
3. **Merge.** `git merge origin/main` (a normal merge commit, no rebase, no squash). Expect conflicts in the five files above and **no others**. If any other file conflicts, **stop and report** which.
4. **Resolve the three text files by keeping BOTH histories:**
   - `ft8_shim.h`: keep `main`'s version of the file (all of `main`'s history entries and exports, including the OSD sign-fix exports `ft8_set_osd_sign_fix` / `ft8_get_osd_sign_fix`, `ft8_get_last_osd_diag`, the hash-state exports, and the subtraction-budget exports) and add B2's `20260059` history entry after `main`'s last entry, then a new history entry for the merge number from Action 5 (say: B2 merged with `main` at `76aa48cd`; no new export, no ABI change). Set `#define FT8_SHIM_VERSION` to the number from Action 5.
   - `Ft8LibInterop.cs`: keep `main`'s file; add B2's remarks paragraph for 20260059 and a paragraph for the new number; set `ExpectedShimVersion` to the number from Action 5. Nothing else in this file changes.
   - `win-x64/libft8.version.txt`: put a new `=== CURRENT: ... (FT8_SHIM_VERSION <number>) ===` block on top (what was merged, the base commits, how it was built, the SHA-256 of each binary you built, macOS: not rebuilt here, CI owns it), then keep `main`'s current block and B2's block as `=== Previous: ... ===` entries. Do not delete either.
5. **Shim number.** Run a `git grep` of `#define FT8_SHIM_VERSION` over **every** `origin/*` ref (`git for-each-ref refs/remotes/origin` then `git show <ref>:src/OpenWSFZ.Ft8/Native/ft8_shim.h`, as the 20260058 and 20260060 entries did) and take **the highest + 1**. QA's check on 2026-10-14 gave 20260061 as the highest, so the expected answer is **20260062**. Record the evidence (the ref and number of the highest) in `libft8.version.txt`.
6. **Do not resolve the two binaries by taking either side.** `git checkout --ours`/`--theirs` on `libft8.dll` / `libft8.so` is wrong: both sides are the wrong binary. **Rebuild both from the merged tree with `main`'s recipe**, after the three text files are resolved and staged:
   - Windows x64: `native\ft8_lib_build\rebuild_shim.bat` (MSVC; it derives its own repo root from its location, so it builds this worktree);
   - Linux x64: `native/ft8_lib_build/build_linux.sh` (GCC under WSL2 Debian, as the 20260060 entry did);
   - macOS: **not rebuilt here** (CI owns it); the `.dylib` stays as it is on `main`.
   Record the SHA-256 of both new binaries in `libft8.version.txt`. Then run `python tools/check_native_version.py` and confirm it reports the new shim number for both files you built. Confirm the Linux `.so` exports the union of both lines: `nm -D src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so | grep -E "ft8_(set|get)_osd_sign_fix|ft8_get_last_osd_diag|ft8_hash_state|ft8_subfeas"` (inside WSL2) must list `main`'s exports and the `ft8_subfeas_*` ones.
7. **Run the normal test suite** (`dotnet test OpenWSFZ.slnx -c Release`, plus whatever your normal pre-hand-back run is). Include the B2 test `SubfeasPrunedFreqSearchTests`; it must pass against the **rebuilt** DLL. Report the counts. Do not add, remove, skip or loosen any test. If a test fails, say which and why; do not "fix" it by changing the test.
8. **Commit locally.** The merge commit's message says what it merges and the shim number. If rebuilding the binaries needs a second commit, make it a separate commit on top. Do **not** push. Leave `VERSION` unchanged and report its current value (QA decides the version bump at review).
9. **Hand back.** Report: the merge commit SHA and its two parents; the list of conflicted files and how each was resolved; the shim number and the evidence for it; the SHA-256 of both binaries; the `check_native_version.py` output; the `nm` check; the test counts; `git diff --stat origin/main..HEAD -- src native` (the net change against `main`).

## 3. Acceptance criteria (what QA will check)

- the merge commit has parents `origin/main` and `aab18b75`; only the five files conflicted; no other file differs from the merge of the two sides;
- `native/ft8_lib_vendor/subfeas/subfeas_fit.c` is byte-identical to B2's (`git diff aab18b75 HEAD -- native/ft8_lib_vendor/subfeas/` is empty);
- net change against `main` is B2's change plus the shim number: `git diff --stat origin/main HEAD -- src native` shows `subfeas_fit.c`, the two source files, `libft8.version.txt` and the two rebuilt binaries, and nothing else under `src/` or `native/` (apart from the existing `libft8.dylib`, untouched);
- shim number = highest on any ref + 1, in `ft8_shim.h`, `Ft8LibInterop.cs`, `libft8.version.txt` and **both** binaries (`tools/check_native_version.py`); both history blocks kept in `libft8.version.txt`;
- both binaries differ from `main`'s and from B2's committed binaries and were built from this tree; the `.so` exports the union of both lines;
- the test suite passes, `SubfeasPrunedFreqSearchTests` included; no test was changed;
- nothing was pushed; `main` was not touched; `VERSION` unchanged.

## 4. After the hand-back (QA's part, not yours)

One measurement on `sol`, the one that answers the old-CPU question: the residual-pass median on the merged build against the first reference-set run's **18.8 s** (leg A median 18,758 ms), same harness, block `822498b61291`, the first 8 scored cycles, 8 threads, budget unlimited, about 10 minutes. The `sol` perf profile of the 10-13 spec is on hold until that number exists. Push, PR and the merge to `main` are the Captain's decision.

## 5. References

- B2: `origin/feat/sub-feas-stage-b` `aab18b75` (`a8014b3c` the change, `aab18b75` the tie-break test fix); OpenSpec `openspec/changes/sub-feas-speed-redesign/` (`design.md` D11; accepted 2026-10-04).
- Recipe precedent: the `libft8.version.txt` entries for 20260058 and 20260060 on `origin/main` (the shim-number rule and the build record).
- Architect's facts and the Captain's direction: `arch-9f` message to QA, 2026-10-14.
- HK-000 (this handoff), HK-010 / HK-033 (no push, no merge to `main` without the Captain), HK-011 (the Developer owns `src/` and `native/`).
