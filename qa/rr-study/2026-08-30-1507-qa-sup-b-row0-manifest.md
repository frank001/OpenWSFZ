# F-001 `SUP-B` — ROW 0 manifest (Sec.4 pin)

**QA.** Written 2026-08-30 15:07Z (`date -u`, HK-017). Branch `qa/sup-b-2026-08-30`.

Per spec Sec.4 / Amendment 1 Sec.A8 step 2: pinned **before** the first replay. `git diff --stat`
against this commit must be empty when ROW 0 starts — verified in the same session (working tree
clean at commit `3b9f960`, `git status` reports nothing to commit).

Every leg below asserts its DLL's SHA256 against this table at run time. **A version label or
`git merge-base` is never sufficient** — `FT8_SHIM_VERSION` identifies nothing (standing rule).

## win-x64 (this session replays on Windows — the platform ctypes loads)

| leg | source | shim version | DLL SHA256 |
|---|---|---:|---|
| `BASE` | `git show main:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `20260046` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` |
| `INST` | `qa/sup-b-2026-08-30` HEAD (`3b9f960`), `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `20260047` | `37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26` |

Both re-hashed mechanically this session (`sha256sum`), not copied from a prior report:

```
bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f  BASE (git show main:...)
37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26  INST (working tree, committed 3b9f960)
```

Both match their standing pins: `BASE` = the `main` pin recorded on `BOARD.md`; `INST` = the
14:17Z Developer-session hash and the Amendment 1 Sec.A1 table's re-derivation.

## linux-x64 (recorded for completeness; this session's replays do not use it)

| leg | shim version | `.so` SHA256 |
|---|---:|---|
| `BASE` | `20260046` | `b982a96d7bc915cffeaf720b74d6507d60e5ecd302c20d853c7b321dc68eecc9` |
| `INST` (superseded, Amendment 1) | `20260047` | `4970ec5fcc37e0ab291b4d3442b1f91b0fab5f982cc4703f19bc8764cf58384e` |
| `INST` (Amendment 2, current) | `20260048` | `4686a4f7eec31d2190c545586d39d95cab6e10e0758fbb59f7fab44e77498b62` |

## Amendment 2 re-pin (execution pack Sec.C7.1 step 3) — 2026-08-30 17:52Z

`BASE` is unchanged (`bc8efcf1…`/`20260046`) — Amendment 2 re-pins `INST` only, superseding the
`20260047` row above for every ROW 0 run from this point on. Precondition verified per Sec.4/Sec.C7.1:
`git diff --stat` empty at `47447e3` (`git status` clean) before this pin and before any leg starts.

Re-hashed mechanically this session (`sha256sum` against the committed working-tree binaries at
HEAD `47447e3`), not copied from `libft8.version.txt` unchecked:

```
e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e *src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll
4686a4f7eec31d2190c545586d39d95cab6e10e0758fbb59f7fab44e77498b62 *src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so
```

Both match `libft8.version.txt`'s own recorded SHA256 for the `f001-sup-b-amendment-2-cluster-
instrumentation (FT8_SHIM_VERSION 20260048)` entry, and match the 17:43Z QA code review's
independently-derived hashes (`BOARD.md`).

| leg | shim version | win-x64 DLL SHA256 |
|---|---:|---|
| `BASE` | `20260046` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` (unchanged) |
| `INST` | `20260048` | `e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e` |

## Traps carried forward (Sec.A3.4, not restated in full)

- `p23_common.DLL_SHA256 = 39aa1031…` is **neither** leg above — `g2_verification_replay.py` and
  `g3_h12_replay.py` both bypass it (`verify=False`) deliberately; ROW 0a asserts against **this**
  manifest only.
- `--wav-dir` is always passed explicitly; `p23_common.WAV_DIR`'s default is a different corpus.
