# Capture pipe headroom: a 1 MiB stdout pipe for `arecord` and a pinned 20 ms period (Linux, no other behaviour change)

**Date:** 2026-10-17
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-17: "I just want a reliable r&r because we are developing openwsfz". Architect ruling and spec: `qa/rr-study/2026-10-17-1736-architect-pipe-block-b2-ruling-and-product-spec.md` (commit `5e96b49d`, `arch/ows-replay-consistency`). OpenSpec change: `openspec/changes/capture-pipe-headroom/` (proposal, design, tasks, spec delta on `audio-capture`).
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. The Developer does not push or merge, and does not run `pre_merge_check.py` on its own initiative.
**Branch:** `feat/capture-pipe-headroom`, cut from `origin/main` (`96dc5837`, includes PR #239); never commit to `main`. **Do not touch `native/`.**
**Version:** `User-facing: no` in the proposal, so no VERSION bump is required by G9b; say so in the PR if you disagree.

---

## 0. Why (one paragraph)

On `sol`, OpenWSFZ loses capture audio when its reader stalls (the residual decode pass saturates the CPU): `arecord` fills the 64 KiB stdout pipe, blocks, and ALSA overruns. A 1 MiB pipe (about 21.8 s of headroom) removed the loss in a 60-play block on the series' build (0 overruns, 0 off-grid windows, 0 clamped). **This change makes the product do what the test wrapper did, and nothing else but one argument.**

## 1. Precise scope (details and reasons in `design.md`)

1. **`ArecordAudioSource`, after `process.Start()`, Linux only:** `fcntl(fd, F_SETPIPE_SZ = 1031, 1_048_576)` through a libc P/Invoke; read back with `F_GETPIPE_SZ = 1032`; log the granted size at Information. On any failure (errno, exception, missing libc, descriptor not a pipe): log a **Warning with the errno**, never throw, capture continues with the default pipe. **The chunks must stay byte-identical whether the call is granted or refused.**
2. **Confirm how .NET 10 exposes the fd on Unix** (`process.StandardOutput.BaseStream`, probably an `AnonymousPipeClientStream` with a `SafePipeHandle`) and say what you found. If it is not a pipe, do not attempt the call.
3. **`DefaultStartInfo`:** one more argument, `--period-time=20000`, before the final `-`. Everything else (arguments, order, `LC_ALL=C`, redirects) unchanged.
4. **A seam for tests:** put the syscall behind a small internal delegate or interface passed through the test constructor (as the start-info factory is), so the refused and accepted paths are testable on every platform.
5. **Not in this change (the Architect withdrew or parked them):** the channel stays at **16 chunks** (16 -> 256 is withdrawn: untested, and the framer's backlog wrap limit `CycleFramer.cs` ~L253-282, 7.5 s, argues against it); no `--buffer-time`; no framer, `CaptureManager`, Windows (WASAPI) or macOS (`sox`) change; no GUI or API change.

## 2. Tests (test-first; HK-025(k): each must be able to fail)

The list is `tasks.md` section 1 (1.1-1.6). Emphasis:

- **Byte identity with the call refused (1.2):** the chunks with a refusing seam equal, element for element, those with an accepting seam.
- **Real pipe, Linux only (1.4):** the real P/Invoke on a real pipe; skip on other platforms; it must not hang if `/proc/sys/fs/pipe-max-size` is lower than 1 MiB (accept a logged Warning there).
- **Arguments (1.1):** the exact list; only `--period-time=20000` is new relative to the base commit.
- **Existing tests unchanged (1.6):** show the unchanged files in the diff stat.

Use `OpenWSFZ.TestSupport.Poll.*` for any wait; no fixed delays (TESTING_STRATEGY section 11).

## 3. What QA validates afterwards (the Developer needs none of this)

1. Review against `tasks.md` section 1, mutation of the byte-identity and real-pipe tests, full suite on a clean worktree, `git diff --stat -- native/` empty, `pre_merge_check.py` on the combined branch (the Captain's initiative).
2. The PR goes to `main` when the Captain approves. QA then builds the series' fresh B2 + `main` merge (with provenance), runs one sweep, reports the capture counters and checks the residual-pass timing is B2-like (median <= 4 s, none abandoned) before the series goes on.

## 4. Notes for the PR

- `src/` only in `OpenWSFZ.Audio`. **User-facing: no.**
- State plainly: `--period-time=20000` is **untested through the daemon on plain devices**; a read-only probe on `sol` (`arecord -v`) showed `plughw:0,0` going from a 125 ms to a 20 ms period with the buffer unchanged, `dsnoop` ignoring it, and `default` unchanged.
- Known limit, recorded and not fixed: a stall longer than about 7.5 s that ends at a window start (the framer's backlog wrap, F2, parked).
- If anything here collides with what you find in the code, say so in the PR rather than choosing silently. The one thing that must hold is that the captured chunks do not change.
