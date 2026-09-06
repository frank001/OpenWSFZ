# Developer handoff: `AwgnFpReplayTests` ROW 0a SHA256 pin is stale against shim 20260050

🛑 **SUPERSEDED, 2026-09-06 — committed for provenance only, do not act on §2.** This proposal's
re-pin was applied (`test(fp-regression): re-pin AwgnFpReplayTests ROW 0a to shim 20260050`), then
reverted (`7cf11d7`) on PO-directed ruling: `AwgnFpReplayTests.PinnedShaWinX64` stays the `20260049`
identity of every already-landed row (`AWGN-FP` A3.1) — it is not to be re-pinned a second time. The
actual fix for the `pre_merge_check.py` failure this note diagnoses was `3306265`
(`fix(pre-merge-check): exclude Category=AwgnFpReplay from both test-suite runners`), landed via
PR #140. §0–§1's root-cause diagnosis below is accurate and unaffected; §2's remedy is not the one
that shipped.

**Authored by:** QA, 2026-09-05 (19:31 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Follows:** the Captain's request to run `tools/pre_merge_check.py` against `main`
(`ec5b416`), 2026-09-05.
**Status:** 🔴 **Proposal, not approved work in itself (HK-011).** A separate Developer session
runs `opsx:apply` (build + tests only — never `pre_merge_check.py` itself again unless
re-verifying this fix, that is HK-006, the Captain's initiative). The Captain reviews the diff
before any push or merge (HK-010/HK-014). QA does not declare readiness.

---

## 0. `pre_merge_check.py` result: **NOT READY** — two gates failed of twelve

Run at the Captain's explicit request (HK-006). Full summary:

```
[WARN ] Native binary freshness — win-x64 DLL: current (20260050); linux-x64 .so: current
        (20260050); osx-arm64 .dylib: STALE, could not rebuild here (not on macOS — expected/
        permanent, per standing note; not this ticket's concern)
[PASS ] G9a — doc/VERSION consistency
[FAIL ] G9b — mandatory VERSION bump on user-facing change   <- separate issue, not this ticket
[PASS ] Solution build (Release)
[PASS ] Lint — UDP capture margin check
[PASS ] G10 — test-delay-synchronization lint
[FAIL ] Full test suite (Release)                             <- this ticket
[PASS ] G3 — requirement traceability
[FAIL ] WSL Debian compile + test                              <- same root cause as above
[PASS ] G8 — OpenSpec strict validation
[PASS ] Self-contained non-AOT publish (local platform)
[PASS ] AOT publish (local platform)
```

This note covers **only** the test-suite / WSL failures. The `G9b` VERSION-bump failure
(`openspec/changes/decode-implausibility-marking/proposal.md` still declares `User-facing: yes`
despite the change's withdrawal) is a separate QA/Architect reconciliation and is being tracked
apart from this ticket — do not fold a VERSION bump into this fix.

---

## 1. Root cause — traced, not guessed

`OpenWSFZ.Ft8.Tests.dll` failed **8 of 330** tests, identically on both the native Windows leg
and the WSL Debian leg (16 failure instances total, same 8 test names, same error):

```
Row0a_BinaryIdentity_MatchesPinnedSha256                                    [FAIL]
M3: offline replay of the N=230/part S1 genuine-decode population           [FAIL]
M1/M2/M4: offline replay of the N=2000/part S5 AWGN population              [FAIL]
ROW 0b: offline replay of the in-chain sweep's own 60 S5 seeds (anchor)     [FAIL]
ROW 0c FIRST ATTEMPT (INVALID — normalisation cancels level...)             [FAIL]
ROW 0c (corrected): level-dependence probe via level-preserving rerender   [FAIL]
ROW 0d: M3 complement (S1 ladder, N=25/part) yields >= 200 genuine decodes  [FAIL]
ROW 0k: S5-LEVEL deletion decode sets identical before/after               [FAIL]
```

Every one of them throws from the same shared helper, `AssertBinaryPin()`
(`tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs:430`):

```
Expected actualSha to be "ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e"
because HK-021(p): every row is void if the binary pin does not hold for the whole run, but
"6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c" differs near "6b2" (index 0).
```

**This is the fixture working exactly as designed, not a false alarm.** `PinnedShaWinX64`
(line 58–59) is a comment-dated pin for **shim 20260049**, taken "from
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` line 28 ... as of this arm's base commit
`main@3b52608`". Since then, `ac6150d` ("feat(f001-l3): add ft8_get_h12_unresolved_by_code
native export (shim 20260050)") bumped `FT8_SHIM_VERSION` and rebuilt the win-x64 DLL. I
confirmed this mechanically, not just from the stack trace:

```
$ tools/check_native_version.py src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll 20260050
Result : OK — binary contains shim version 20260050
$ tools/check_native_version.py src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so 20260050
Result : OK — binary contains shim version 20260050
```

Both committed platform binaries are correctly at `20260050`. The pin in the test file simply
never followed. Because ROW 0a fails, and every other row calls the same `AssertBinaryPin()`
guard per its own stated design (HK-021(p): a mismatched binary pin voids the whole run rather
than let any row silently run against the wrong binary), all eight rows fail in sympathy — this
is one defect, not eight.

The WSL leg fails identically because the win-x64 `libft8.dll` bytes are copied into the WSL
test output alongside `libft8.so` (for this same cross-platform pin check), so `AssertBinaryPin`
reads the identical stale-pin mismatch on both legs.

---

## 2. What to do

1. Recompute the SHA256 of the **currently committed**
   `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` independently — do not copy the value below
   without verifying it yourself, e.g.:
   ```
   certutil -hashfile src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll SHA256
   ```
   I observed `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` from the
   test's own `actualSha` output during this run, against the file `check_native_version.py`
   independently confirmed is shim `20260050` — but confirm it fresh rather than trust my copy.
2. Update `PinnedShaWinX64` in `tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs` (lines 54–59) to
   the verified value, and update the citing comment: shim version `20260049` → `20260050`,
   source commit `main@3b52608` → `ac6150d`, and the `libft8.version.txt` line number if it has
   moved (the "CURRENT" block is now at the top of that file, headed
   `=== CURRENT: f001-l3-unresolved-by-code-export (FT8_SHIM_VERSION 20260050) ===`).
3. Also update the stale `20260049` literal inside the `[Fact(DisplayName = ...)]` string on
   line 74 ("ROW 0a: loaded libft8.dll SHA256 matches the pinned shim 20260049 manifest value")
   — cosmetic, but it is a manifest number and should not be left claiming the wrong shim.
4. Re-run `OpenWSFZ.Ft8.Tests` (or the full `pre_merge_check.py`) and confirm all 8 previously-
   failing rows pass on both the native and WSL legs.
5. Commit as its own small commit, e.g. `test(fp-regression): re-pin AwgnFpReplayTests ROW 0a to
   shim 20260050` — do not fold it into any unrelated change.

---

## 3. What NOT to do

🛑 No change to decode behaviour, no change to any other pinned constant in this file
(`AnchorBandLow`/`AnchorBandHigh`, `Row0dMinGenuineDecodes`) — none of those are implicated by
this drift. This is strictly re-pinning a stale binary-identity hash to match the binary the
project has already, correctly, moved to.

🛑 Do not touch the `G9b` VERSION-bump failure in the same commit — that is a separate,
unrelated gate failure (see §0) with its own reconciliation path.

---

## 4. Definition of done

- [ ] `PinnedShaWinX64` re-pinned to a freshly, independently verified SHA256 of the committed
      `win-x64/libft8.dll` (shim 20260050)
- [ ] Comment block (lines 54–57) and `[Fact(DisplayName=...)]` string (line 74) updated to cite
      `20260050` / `ac6150d`, not `20260049` / `3b52608`
- [ ] `OpenWSFZ.Ft8.Tests` re-run (native and WSL); all 8 previously-failing rows pass
- [ ] Committed as its own `test(fp-regression)` commit, not folded into anything else

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No further
`pre_merge_check.py` runs beyond re-verifying this specific fix (HK-006 — the Captain's
initiative). The Captain reviews the diff and decides on merge.
