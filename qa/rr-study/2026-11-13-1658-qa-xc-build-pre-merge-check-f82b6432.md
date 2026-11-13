# XC-BUILD: `pre_merge_check.py` on `f82b6432`: every gate passes except the WSL Debian leg, which fails on a defect that is already on `origin/main`

**Written:** 2026-11-13, `date -u` read 16:57:48Z (run started 16:47:19Z). **Commit checked:** `f82b6432b3eafab40a72b80ab1f294d9a8f1ea51`, a clean `git worktree add --detach` at `D:\Projects\claude\_qa-scratch\premerge-f82b6432`; base `origin/main` = `ce5734b6e5e784525be4038a99329800ab2c29bd`. Command: `python tools/pre_merge_check.py` (no skip flags). Log: `D:\Projects\claude\_qa-scratch\premerge-f82b6432.log` (not committed).

## 1. Result: NOT READY, one gate

| gate | result |
|---|---|
| native binary freshness (Windows, Linux, macOS; shim 20260072) | PASS |
| G9a doc/VERSION; **G9b mandatory bump** (against `origin/main`) | PASS, PASS |
| solution build (Release); UDP capture margin lint; **G10 test-delay lint**; **G3 traceability**; G8 OpenSpec strict | PASS |
| full test suite (Release, Windows) | PASS: Ft8 781, Daemon 935, Web 447, E2E 9, Config 204, Rig 41, Audio 40, TestSupport 12, Traceability 34, LicenseInventory 24; 0 failed |
| self-contained non-AOT publish | PASS |
| **WSL Debian compile + test** | **FAIL**: Ft8 244, Daemon 176, Web 187, E2E 8 failed |

## 2. Why the WSL leg fails: the Linux `libft8.so` on `origin/main` does not load on Debian 13

- The first Ft8 failure reads: `Unable to load shared library '…/libft8.so' … /lib/x86_64-linux-gnu/libm.so.6: version 'GLIBC_2.43' not found`. WSL Debian is Debian 13 trixie, glibc **2.41**. The other failures are consequences (native interop absent; QSO-answerer tests timing out at 5 s waiting for a decode that cannot happen).
- **Highest `GLIBC_2.x` symbol version in the tracked `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`:** at `70bc72b1` **2.35**; at `ce5734b6` (`origin/main`) **2.43**; at `f82b6432` **2.43** (same blob as `ce5734b6`, SHA-256 prefix `e8cb81805322`; the `70bc72b1`/`59eb5a8f` blob is `288ee2d690be`).
- The blob changed in `fa81a0be` ("chore(native): rebuild Linux and macOS binaries to shim 20260072", github-actions[bot], 2026-11-12 12:51:15 +0000).
- **Yesterday's WSL leg passed** on `59eb5a8f` (log `premerge-59eb5a8f.log`, 2026-11-12), which still carried the 2.35 blob.
- `git diff --stat ce5734b6 f82b6432 -- native src/OpenWSFZ.Ft8/Native` is **empty**: the XC build did not touch the binary, and the same failure would occur on `origin/main` itself. (I did not run the WSL leg on `ce5734b6`: the loader message and the blob's symbol versions already settle it; a run would take about 5 minutes if the Captain wants it.)

## 3. What this means

- **For the XC-BUILD review:** nothing; every gate that can see the XC code passes, on Windows.
- **For any push of any branch:** HK-006 says a push needs a PASS or a named failure the Captain accepts. The named failure is: **the WSL leg fails on `libft8.so` GLIBC_2.43, a defect of `origin/main` since `fa81a0be`; it is not caused by this branch.**
- **For CI:** the bot-built `.so` requires 2.43, so a CI runner with an older glibc (the WSL leg is described as the same family as ubuntu-latest) would fail the same way on every branch. I have not looked at CI; that is the Captain's and the Architect's to read.
- **For sol:** `ldd --version` on sol reads `Gentoo 2.43-r4`, so the tracked `.so` can load there; this finding does not stop the sol plan (the sol build will still pin and print its own `.so` SHA-256).
- The repo owner of the binary rebuild workflow is not QA's to change (no `native/` or CI edit proposed here).
