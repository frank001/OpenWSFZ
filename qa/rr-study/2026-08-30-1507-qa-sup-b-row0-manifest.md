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
| `INST` | `20260047` | `4970ec5fcc37e0ab291b4d3442b1f91b0fab5f982cc4703f19bc8764cf58384e` |

## Traps carried forward (Sec.A3.4, not restated in full)

- `p23_common.DLL_SHA256 = 39aa1031…` is **neither** leg above — `g2_verification_replay.py` and
  `g3_h12_replay.py` both bypass it (`verify=False`) deliberately; ROW 0a asserts against **this**
  manifest only.
- `--wav-dir` is always passed explicitly; `p23_common.WAV_DIR`'s default is a different corpus.
