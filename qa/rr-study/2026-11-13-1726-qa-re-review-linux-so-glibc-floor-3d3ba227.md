# Linux `libft8.so` glibc floor: re-review of the Developer's `3d3ba227`: APPROVED (tests complete; acceptance items 2 to 4 are post-merge)

Reviewed-commit: 3d3ba227b4e08954e9bdded80b4305b3e8a5b11e
Verdict: APPROVED

**Written:** 2026-11-13, `date -u` read 17:25:28Z. Follows the RETURNED record `2026-11-13-1725-qa-review-linux-so-glibc-floor-4c377f75.md` (`f77caddb`). Branch `fix/linux-so-glibc-floor`, the Developer's, local, off `origin/main` `ce5734b6`.

| check | result |
|---|---|
| Delta `4c377f75..3d3ba227` | one file, `tools/check_glibc_floor.py` (+23): the self-test now calls `main()` end to end through a temp synthetic ELF. `git diff --stat ce5734b6 3d3ba227` lists only `.github/workflows/ci.yml` and `tools/check_glibc_floor.py` (G5: no `native/`, no `src/`) |
| Self-test | 16 of 16 pass (above the floor 1; at and below 0; missing file, non-ELF, `main([])`, unknown option 2) |
| **Mutation of the guard, 10 mutants** (`<=`→`<`, floor 2.40, floor 2.38, `max`→`min`, third version component dropped, `check` always true, FAIL path 1→0, usage 2→0, read error 2→0, OK path 0→1) | **10 of 10 killed**, including the three that survived `4c377f75` |
| Real blobs, `3d3ba227`'s guard (my run) | `ce5734b6` blob (`e8cb81805322…`): GLIBC_2.43, **rc 1 FAIL**; `70bc72b1` blob: 2.35, **rc 0 OK** |
| Workflow | unchanged since `4c377f75`: matrix `ubuntu-24.04`; the guard step after the Linux build and before the artifact upload |

**Still owed, post-merge (the bot rebuilds the `.so`):** on the first `main` build after the merge, the rebuilt `libft8.so` reads at most 2.39 (the guard or `readelf -V`), and `pre_merge_check.py` from a clean checkout has its WSL Debian leg green. Also the Captain's: the branch-protection check name ("Build & Test (ubuntu-24.04)"), and every merge (HK-010). Nothing pushed; QA pushes only on the Captain's word and after `pre_merge_check.py` (HK-006). On this branch that script cannot show the WSL leg green until the rebuilt `.so` exists, so a named failure is expected for that one leg until then.
