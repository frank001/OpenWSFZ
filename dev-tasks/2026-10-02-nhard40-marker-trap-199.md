# Developer handoff: fix the nhard40 migration marker trap (#199): an operator's explicit `osdNhardMax` 60 must survive a restart

**Date:** 2026-10-02. **From:** QA. **To:** Developer. **Priority:** medium, and it is a **prerequisite** of the default-ON migration (QA's next handoff, spec `qa/rr-study/2026-10-02-0710-architect-to-qa-spec-sub-feas-default-on.md`), which must not repeat this pattern. **Issue:** https://github.com/frank001/OpenWSFZ/issues/199. `src/` is touched, so a separate Developer session does it (HK-011). **Only QA pushes.**

## 1. The defect, tested (QA, `origin/main` `9bade2bc`)

`JsonConfigStore.Load` (`src/OpenWSFZ.Config/JsonConfigStore.cs`, the M2 block at lines ~245 to 270) migrates a persisted `osdNhardMax` of exactly 60 to 40 when `decoder.nhard40MigrationApplied` is `false`, and sets the marker to `true` **only inside that branch**. On any config that never held a 60 (a fresh install, or one already at the code default 40) the marker stays `false` for ever. If the operator then sets 60 on purpose (a Settings save keeps it, the marker stays `false`) and the daemon restarts, `Load` matches `{60, false}` and rewrites the choice to 40.

QA's evidence is committed on the **local** branch `qa/nhard40-marker-trap-test` (commit `2012551d`, one file `tests/OpenWSFZ.Config.Tests/Nhard40MarkerTrapTests.cs`, take it with `git show 2012551d:tests/OpenWSFZ.Config.Tests/Nhard40MarkerTrapTests.cs`). On `9bade2bc`: **2 FAIL** (fresh install + explicit 60 + reload gives 40; a config already at the default 40 + explicit 60 + reload gives 40) and **1 PASS** (the control: a legacy `{60, marker false}` migrates once, and a later explicit 60 then survives, because the marker is true).

## 2. Required behaviour (what must be true; the implementation is yours)

The marker means **"no migration is pending for this install"**. It must therefore be true wherever that is already so, not only after a 60 was seen.

1. **`Load`:** when a `decoder` section exists and `nhard40MigrationApplied` is false: if `osdNhardMax == 60`, migrate exactly as today (40, marker true, written back, the same stderr line); **otherwise leave `osdNhardMax` untouched, set the marker to true and write it back once** (same temp-file-then-rename `WriteAtomic`). After that, later loads write nothing (idempotent: a second `Load` must not rewrite the file).
2. **A decoder section created later from nothing** (the config POST, `src/OpenWSFZ.Web/WebApp.cs` line ~525: `Nhard40MigrationApplied = store.Current.Decoder?.Nhard40MigrationApplied ?? false`): when the store has **no** decoder section, no persisted 60 can ever have existed, so the new section's marker must be **true**. The marker stays **server-owned**: the value a client sends is still ignored (the existing test `…ClientCannotSetMarker`-style in `DecoderConfigApiTests.cs` ~lines 352 to 384 must keep passing as it is).
3. **Do not change `DecoderConfig`'s default** (`Nhard40MigrationApplied { get; init; } = false`, `DecoderConfig.cs:116`): a legacy file whose decoder section lacks the key must still deserialise to false so a genuine legacy 60 still migrates.
4. Look for any other place that builds a decoder section from `null` and saves it (`git grep -n "new DecoderConfig" src`); the same rule applies.
5. A genuine legacy 60 (`{"decoder":{"osdNhardMax":60}}`, no marker) still migrates **once**. A persisted 60 **with** marker true is left at 60 (existing test). Exact-60-only: 55 and 70 pass through unchanged.

## 3. Existing tests that encode the OLD behaviour (change them deliberately, say so, do not weaken anything else)

- `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs` ~line 676 to 695, `Load_PersistedOsdNhardMax_NotExactly60_PassesThroughUnchanged` (55 and 70): asserts `Nhard40MigrationApplied.Should().BeFalse("no migration means no marker set")`. Under the new rule the **value** still passes through unchanged, but the marker becomes **true** (and is persisted once). Update that single assertion and its message; keep the value assertion exactly.
- `Load_NoDecoderKey_YieldsNewCodeDefault_NoMigrationMarkerWritten` (just below): a file with **no decoder key** still writes no marker on `Load` (there is no section to carry it): this test should keep passing unchanged. If it does not, stop and tell QA.
- Your report must list **every** existing test you changed, with the old and new assertion and why, so QA can check that nothing was weakened.

## 4. Branch and tests

Cut **`fix/nhard40-marker-trap`** from `origin/main` (`git fetch` first). Test-first: add `Nhard40MarkerTrapTests.cs` from QA's commit (the two TRAP tests must fail on the base, then pass; the CONTROL must pass throughout). Add: (a) a second `Load` of the same file writes nothing (content and modification time unchanged); (b) a Web test: POST that **creates** the decoder section where the store had none leaves the stored marker **true**; (c) the same POST with the section already present keeps the stored value (server-owned). Cross-platform: the tests use temp directories only.

## 5. Acceptance criteria (what QA checks)

1. The two TRAP tests and the control pass; the base run shows the two TRAP tests failing first (quote it).
2. Your list of changed existing tests (section 3) is complete and each change is justified; no test deleted, no other assertion weakened.
3. Unfiltered `dotnet test OpenWSFZ.slnx -c Release` on **Windows** and on **WSL Debian** (exact commands and per-assembly counts, HK-022). If a first run hits the known parallel-build lock (`CS2012` or a `StaticWebAssets` `IOException`), re-run unchanged and say so.
4. `git diff --stat origin/main -- native` is empty and `src/` is limited to `OpenWSFZ.Config`, `OpenWSFZ.Web` (and `OpenWSFZ.Abstractions` only if unavoidable, with a reason).
5. `python tools/check_test_delay_sync.py` OK; `python tools/check_version_bump.py origin/main` and `check_version_docs.py` run and quoted (a bump is needed only if the gate says so); if any spec or `REQUIREMENTS.md` text describes the marker's semantics, amend it and run `openspec validate --all --strict` (QA's grep found only a passing mention in FR-074).
6. No push (only QA pushes). Do not start the default-ON work.

## 6. References

- Issue #199; `src/OpenWSFZ.Config/JsonConfigStore.cs` (M2 block), `src/OpenWSFZ.Web/WebApp.cs` ~525, `src/OpenWSFZ.Abstractions/DecoderConfig.cs` :116.
- Existing marker tests: `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs` ~640 to 700, `tests/OpenWSFZ.Web.Tests/DecoderConfigApiTests.cs` ~330 to 384.
- Standing rules: HK-011, HK-022, HK-035 (config POST semantics: an overlay on `main` since v0.53).
