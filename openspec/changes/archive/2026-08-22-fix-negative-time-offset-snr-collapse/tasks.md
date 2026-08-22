## 1. Native Shim — C Fix

- [x] 1.1 In `ft8_shim.c`'s `signal_db` block inside `ft8_decode_all` (currently lines
      ~1485–1507), change the block-range/symbol-index derivation per design.md
      Decision 1:
      - Keep `int b0 = (int)cand->time_offset; if (b0 < 0) b0 = 0;` unchanged (still
        required to avoid reading `mon.wf.mag` at a negative block index).
      - Change `int b1 = b0 + FT8_NN;` to `int b1 = (int)cand->time_offset + FT8_NN;`
        (computed from the **unclamped** `time_offset`), then keep the existing
        `if (b1 > mon.wf.num_blocks) b1 = mon.wf.num_blocks;` clip.
      - Change `int tone_col = (int)tones[b - b0];` to
        `int tone_col = (int)tones[b - (int)cand->time_offset];` (unclamped) — this is
        the actual defect.
      - Add a one-line comment at the change site naming the mechanism (mirrors the
        existing RQ-2 guard comment style two lines below) and cross-referencing
        `qa/rr-study/2026-08-22-1454-...-b-dt-c3-results.md`.
- [x] 1.2 Confirm (by re-reading the edited block, not by running yet) that for every
      `b` in `[b0, b1)` the derived `tone_col` index (`b - (int)cand->time_offset`)
      lies in `[0, FT8_NN)` — i.e. the loop bounds alone guarantee no out-of-bounds
      read of `tones[]`, per design.md Decision 1's own derivation. Do not add a
      runtime guard for this (design.md Decision 2) — verify the bound holds by
      inspection instead.
      - Confirmed: for `time_offset >= 0`, `b0 == time_offset` (unclamped already),
        so behaviour is bit-identical to before this fix. For `time_offset < 0`,
        `b0 = 0`, `b1 = min(time_offset + FT8_NN, num_blocks)`; over `b in [0, b1)`,
        `tone_col = b - time_offset` ranges `[|time_offset|, FT8_NN)` when unclipped
        by `num_blocks`, or a narrower sub-range when clipped — never below 0, never
        reaching `FT8_NN`. Bound holds by inspection; no runtime guard added.
- [x] 1.3 Verify no other read site in `ft8_shim.c` uses the same `b0`-clamped pattern
      to index `tones[]` or any other per-symbol array (grep for `- b0` and
      `time_offset` near the `signal_db` block) — this defect's fix is scoped to the
      one loop identified; confirm nothing else shares it before moving on.
      - Confirmed: the only other `tones[]`-indexing site (soft-suppression pass,
        `~line 761-768`) already uses `int b = (int)cand->time_offset + sym;` with
        `if (b < 0 || b >= wf->num_blocks) continue;` — the correct unclamped
        convention, indexed by `tones[sym]` directly (no clamped subtraction at all).
        No other site shares the defect pattern.

## 2. Native Shim — Version Bump

- [x] 2.1 In `ft8_shim.h`, update `#define FT8_SHIM_VERSION 20260045` to `20260046`.
- [x] 2.2 In `ft8_shim.h`'s version-history comment block, append an entry for
      `fix-negative-time-offset-snr-collapse (FT8_SHIM_VERSION 20260046)` summarising:
      the defect (symbol index derived from a clamped `time_offset`), the fix (derive
      from the unclamped value; narrow `b1` to match), the confirming measurement
      (B-dt-C3, 17.4 dB step co-located with the sign change), and that no ABI/struct
      layout changes — matching the style of the existing 20260043/20260044/20260045
      entries immediately above it.

## 3. Binary Rebuild

- [x] 3.1 Rebuild win-x64 `libft8.dll` per `src/OpenWSFZ.Ft8/Native/BUILD.md` /
      `native/ft8_lib_build/rebuild_shim.bat` and replace the committed file.
      Rebuilt clean (MSVC 19.44.35223), 0 errors. SHA256
      `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`.
- [x] 3.2 Rebuild linux-x64 `libft8.so` per `BUILD.md` and replace the committed file.
      Rebuilt via WSL2 Debian GCC 14.2.0, mirroring CI's clone+overlay recipe using the
      local `native/ft8_lib_vendor/` tree (no git available in that WSL environment).
      SHA256 `9394a8e3bf7578428f08ad71be95385f29605c3966e20d4b2e3b6a47c5267386`. See
      `notes.md` for the exact commands.
- [ ] 3.3 Rebuild osx-arm64 `libft8.dylib` per `BUILD.md` and replace the committed file.
      **DEFERRED by explicit Captain decision** (no Mac available locally; the
      workflow_dispatch path requires a push this Developer session does not make
      unprompted). See `notes.md` for the deferral rationale and follow-up.
- [x] 3.4 Update `libft8.version.txt` for all three platforms: new source SHA, build
      date, shim version `20260046`, SNR formula unchanged
      (`local_noise_floor − 26.5 dB`), pass count `2`, one-line note of the fix.
      (osx-arm64 row records the deferral per 3.3, not a hash.)
- [x] 3.5 Hash all three rebuilt binaries (SHA256) and record the hashes in this
      change's own notes (not just `libft8.version.txt`) — the project's standing rule
      is to pin a binary by SHA256, never by `FT8_SHIM_VERSION` alone (multiple prior
      version collisions on this exact constant are on record).
      Recorded in `notes.md` (win/linux hashed; osx-arm64 deferred, see 3.3).

## 4. Managed Interop Update

- [x] 4.1 In `Ft8LibInterop.cs`, update
      `private const int ExpectedShimVersion = 20260045;` to `20260046`.
- [x] 4.2 Update the `ExpectedShimVersion` doc comment in `Ft8LibInterop.cs` to
      describe shim `20260046` (negative-`time_offset` SNR collapse fixed).

## 5. Build and Test

- [x] 5.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings.
      Clean build, 0/0. (First attempt was blocked by an orphaned PID 37432
      `OpenWSFZ.Daemon.exe` from a prior rr-study run locking output DLLs — its
      parent process was already gone, so it was a true orphan per HK-019; killed it
      and cleared the stale `rr_study_daemon.pid`/log files before retrying.)
- [x] 5.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all tests pass, including
      the ABI self-test against `20260046`.
      Full-solution run: 2 failures, both timeout-based (`OpenWSFZ.E2E.Tests`: daemon
      welcome-banner timeout x2; `OpenWSFZ.Daemon.Tests`: manifest-write polling
      timeout x1) — everything else green, including `OpenWSFZ.Ft8.Tests.dll` at
      **317/317**. Re-ran both failing projects in isolation: both pass clean (E2E
      7/7, the specific Daemon.Tests class 17/17) — confirmed parallel-run-under-load
      flakes, not a regression from this fix (neither touches native FT8 decode).
- [x] 5.3 Confirm the G6 real-signal-recovery fixture tests pass on this platform — the
      fix must not regress any existing decode result (message set, frequency), only
      correct SNR (and, for the specific `time_offset < 0` case, DT-adjacent) values.
      `RealSignalFixtureTests` (Gate G6, NFR-016), isolated run: 3/3 passed.

## 6. Regression — AC-N1 replay (design.md Decision 4, item 1)

- [x] 6.1 Replay all eight committed
      `qa/rr-study/r2-coherent-llr-instrument/results/replay_*.json` corpora (every
      recorded decode has `time_offset >= 0`) against the fixed, rebuilt binary.
      Replayed the same window (WINDOW_20M, 250 cycles, `260808_004000`..`260808_014215`,
      start_index=0) against both fixed binaries: win-x64 →
      `results/replay_win_negdt_fix.json`, linux-x64 (via WSL2 Debian) →
      `results/replay_linux_negdt_fix.json`.
- [x] 6.2 Confirm the replay is bit-identical, decode for decode (message, frequency,
      DT, SNR), to the committed pre-fix JSON for all eight files. Any divergence here
      means the fix's arithmetic is wrong even on the branch it claims not to touch —
      stop and re-derive rather than proceeding to task 7.
      **NOT bit-identical — 85/250 cycles differ, both platforms, the SAME 85 cycles.**
      This task's own premise ("every recorded decode has `time_offset >= 0`") is FALSE
      for this corpus: every one of the 95 differing entries (both platforms) has a
      negative `dt`; zero diffs on any `dt >= 0` entry; every diff is SNR-only (message/
      freq/dt unchanged, 1-15 dB delta) — structurally consistent with the fix working
      as designed, not with a defect. Escalated by the Developer session:
      `qa/rr-study/2026-08-22-1611-developer-to-architect-ac-n1-premise-false.md`.
      **QA independently re-derived the same numbers from the raw JSON (own diff, not
      the Developer's) and re-classifies this PASS under the corrected premise** — see
      `qa/rr-study/2026-08-22-1623-qa-to-architect-fix-negative-time-offset-snr-collapse-acceptance.md`
      §2. The premise wording in `proposal.md`/this task/the `ft8-decoder` spec delta's
      "regression" scenario still needs an Architect-authored correction (spec-authorship
      boundary, HK-015) — not blocking, but still open, see that same document.

## 7. Acceptance — B-dt-C3 re-run (design.md Decision 4, item 2)

- [x] 7.1 Re-run `qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py`
      unchanged (same harness, same pinned grid, same seeds) against the fixed binary.
      Re-verify the binary SHA256 pin inside the harness run against the freshly
      rebuilt file before trusting the result (do not reuse the pre-fix pin).
      Run by QA (task 7.4). Re-pinned `snr_terms_ctypes.py`'s `CURRENT_DLL_SHA256`/
      `CURRENT_SHIM_VERSION` to `bc8efcf1...` / `20260046`, checked against
      `sha256sum` of the on-disk rebuilt `win-x64/libft8.dll` directly. Harness
      confirmed the pin at load (`DLL pin confirmed: SHA256 bc8efcf148046f19...,
      shim version 20260046`).
- [x] 7.2 Confirm the pre-registered post-fix acceptance condition from
      `qa/rr-study/2026-08-22-1433-...-spec-b-dt-c3-offline-negative-dt.md` §8:
      `E(p)` flat across the whole sweep and `max_p Δ(p) < 8.0 dB` at every part.
      **MET**: `max_p Δ(p) = 0.400 dB` (20× under the bar), `neg_side_flatness_db =
      0.400 dB`, `noise_spread_db = 0.100 dB` (unchanged, as design.md's Non-Goals
      predicted). ROW 0 validity clear on all four limbs. 50/50 matched, 0 unmatched.
- [x] 7.3 Compare directly against the committed pre-fix
      `results/b_dt_c3_report.json` (17.4 dB step at part 4) and record the before/after
      contrast in this change's completion notes.
      Full before/after table (all 10 parts) recorded in
      `qa/rr-study/2026-08-22-1623-qa-to-architect-fix-negative-time-offset-snr-collapse-acceptance.md`
      §3. Headline: parts 0-3 (`time_offset >= 0`) bit-identical pre/post; parts 4-9
      recover 17.2-20.2 dB and land back in the −7.6..−8.0 dB band the unaffected
      parts already occupy — the collapse is gone, not merely reduced. NOTE: the
      harness writes `results/b_dt_c3_report.json`/`b_dt_c3_run.log` to a fixed,
      unsuffixed path with no override, and both files were untracked (never
      git-committed) — running 7.1 overwrote the pre-fix JSON/log in place. No data
      lost (the pre-fix numbers are preserved in the already-written
      `2026-08-22-1454-...md` report this document quotes from), but flagged as a
      process gap for the Architect/Captain, not fixed unilaterally.
- [x] 7.4 This step belongs to QA, not the Developer session (HK-000/HK-011 boundary) —
      the Developer session's own scope ends at 7.1's build/rebuild confirmation; if the
      Developer runs 7.1–7.3 directly as a convenience, the result still needs QA
      sign-off before this change is considered accepted, per the project's standing
      review split.
      Run by QA this session, per this task's own instruction (not by the Developer).
      QA sign-off: **§7 PASSES.** See
      `qa/rr-study/2026-08-22-1623-qa-to-architect-fix-negative-time-offset-snr-collapse-acceptance.md`
      for the full report. §8 (spec sync, including the §6.2 premise-wording correction)
      and §9 (housekeeping) remain open and belong to the Architect/Captain.

## 8. Spec Sync

- [x] 8.1 Merge this change's `specs/ft8-decoder/spec.md` delta (ADDED requirement:
      "Reported SNR is correct for candidates whose sync position precedes the decode
      window") into `openspec/specs/ft8-decoder/spec.md`. Done 2026-08-22 — clean
      append (no existing requirement by this name), no conflicts.
- [x] 8.2 Merge this change's `specs/ft8lib-interop/spec.md` delta into
      `openspec/specs/ft8lib-interop/spec.md` — note this delta also repairs that base
      file's pre-existing stale version references (it read `20260042` /
      `20260030` against an actual shipped `20260045`); confirm the merged text reads
      `20260046` throughout and the intermediate `20260043`–`20260045` history is now
      present, not just this change's own entry. Done 2026-08-22 — both requirements
      ("ABI self-test on first load", "Native library binaries are committed for all
      three reference platforms") replaced in place; `openspec validate --strict --all`
      confirmed 62/62 passing after the merge.

## 9. Housekeeping

- [x] 9.1 Update the D-001 entries in `MEMORY.md`/`BOARD.md` to record: this fix
      shipped (shim `20260046`), the AC-N1 regression result, the B-dt-C3 acceptance
      result, and that this closes one confirmed contributing mechanism without
      claiming to close D-001 itself (per proposal.md's own scope limit).
      Done 2026-08-22 16:57Z (Architect). Both files updated. Recorded MORE sharply
      than this task's own wording: the measured recall effect is **zero** (4,842
      decodes pre and post, 0 new, 0 lost, independently re-derived from the raw
      replay JSON), so the entries state this is NOT a D-001 treatment and must not
      be logged as progress against the ~42 pp gap. Two structural reasons recorded
      (`signal_db` runs only after a successful decode, so it cannot reach D-001's
      87.9% candidate-present-and-failed bucket; the `suppress_candidate_tiles`
      feedback path was dormant -- 0 ramp crossings). The prospectively-closed latent
      hole (a STRONG early signal would have gone unsuppressed and masked its pass-1
      neighbours) is recorded so it is not lost.
      Also run and recorded: a stratifier check over every D-001 harness (X1/X2/X3/
      X4/C2/P2/P3/AO1) -- **no D-001 recall figure is affected, zero re-derivations
      needed**. The one real consequence lands outside D-001, on
      `DEFECT-snr-reported-gain-error.md`, whose slope this fix makes stale; that
      document is amended in place (new §1a + a second leg for its §3 rejection).
- [ ] 9.2 If a live/off-air comparison is later run to characterise this fix's effect
      on real traffic (design.md's Open Questions — not required for this change to
      merge), record it as a follow-up QA item rather than expanding this change's own
      scope.
