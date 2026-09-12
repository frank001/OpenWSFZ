# NFR-021 clobber hazard: `Row0rCarryForwardTests` + `AwgnFpReplayTests` write raw decoder output into TRACKED, redacted CSVs with no guard — third incident, first structural fix

**Date:** 2026-09-12
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (sign-off required before merge, HK-010)
**Escalated by:** Architect, 2026-09-12 ~11:00Z (found at 09:02:56Z, an unfiltered `dotnet test` run in
the Architect's own worktree overwrote a committed CSV; restored, nothing committed, raw copy kept
in the Architect's own gitignored scratchpad — not this repo). Requested as a dev-task per HK-015.
**Status:** Proposed. Per HK-011, needs the Captain's explicit sign-off before pickup.
**Branch:** new branch off `main`, name at the Developer's/Captain's discretion.

---

## 0. Executive summary

`Row0rCarryForwardTests.cs` and `AwgnFpReplayTests.cs` both write decoder output CSVs unconditionally
(`new StreamWriter(path, append: false, ...)`, no existence check, no tracked-path check) into
`qa/rr-study/fp-parity/results/` and `qa/rr-study/awgn-fp-replay/results/` respectively — **both are
git-tracked, redaction-mapped directories**, not scratch space. Neither class has any clobber guard.
This is the **third** occurrence of exactly this exposure: 2026-09-06 (twice, same day,
`memory/rr-study-matched-csv-nfr021-contamination.md`), and now 2026-09-12 (found today, this
escalation). **A fourth-generation test class, `FpParityP3Tests.cs`, already carries the correct
fix** (`AssertPathUntracked`, writes only to a gitignored `_out/`) — written specifically *because
of* the first two incidents — but it was never backported to the two classes that actually caused
all three incidents. This task backports it, and centralises the guard so a future new Fact in
either class inherits it automatically rather than needing to remember it.

**Both classes are `[Trait("Category", "AwgnFpReplay")]`**, excluded from `pre_merge_check.py`'s
default `--filter Category!=AwgnFpReplay` run — that filter is why this defect has never blocked a
merge, and exactly why it keeps recurring: **any unfiltered `dotnet test`** (a developer's local
habit, an IDE's "run all tests" button, a future CI change) reintroduces the exposure with zero
warning. The filter is a mitigation for CI time, not a safety control for this hazard — do not treat
it as one.

## 1. Precise scope

### 1.1 The defect, exactly, in both files

- **`tests/OpenWSFZ.Ft8.Tests/Row0rCarryForwardTests.cs`**, private helper `DecodeDirectory`
  (`:141-160` builds `slotsCsvPath`/`decodesCsvPath` under `outDir`, `:154-156` opens both with
  `append: false`), called once at `:91` with
  `outDir = qa/rr-study/fp-parity/results` (`:85`) — **the same tracked directory
  `FpParityP3Tests.cs` was written to protect.**
- **`tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs`**, its own (separately duplicated, per that
  file's own docstring — "Duplicated rather than shared to avoid touching `AwgnFpReplayTests.cs` at
  all") copy of `DecodeDirectory` (`:457-474`, same `append: false` pattern), called from **seven**
  sites, each with `outDir = qa/rr-study/awgn-fp-replay/results` (or `Path.Combine(root, "results")`
  where `root` already resolves there): `:98`, `:140` (twice, `:142-143`), `:190` (three times,
  `:192-194`), `:237`, `:276` (twice, `:278-279`), `:345`, `:390`. **Nine `DecodeDirectory` calls in
  total across seven Facts**, every one unguarded.
- **Lower-severity but still in scope:** `AwgnFpReplayTests.WriteVerdictLine` (`:549-554`) appends
  (not overwrites) a line to `row0_verdicts.txt` under the same tracked `results/` directory, called
  from all seven Facts above. Append is less destructive than overwrite, but it is still an
  unconditional write into a tracked path with no guard, and `row0_verdicts.txt` is itself tracked
  (confirmed via `git ls-files`) — include it in the same fix.

### 1.2 Today's actual incident, for context (not this task's job to redress — already handled)

The Architect found, at 09:02:56Z, that a run of `Row0rCarryForwardTests` had overwritten
`qa/rr-study/fp-parity/results/m1m4_s5_20260050_decodes.csv` with raw decoder output: 265 message
cells, 278 callsign-shaped tokens where the committed file has 69, and the committed file's own
`<RDCTR..>` redaction placeholders gone. **Already restored** (the Architect reverted the working
tree to the committed version); nothing was staged or committed, so there is no git-history
cleanup needed. This task is the structural fix so a fourth occurrence needs a person to notice and
revert every time, rather than the tooling refusing by construction.

### 1.3 The fix: centralise the guard, don't repeat it at each call site

`FpParityP3Tests.cs` has exactly **one** `DecodeDirectory`-shaped call site, so its own fix
(`AssertPathUntracked` called explicitly right before the writer, `:180-183`) reads fine inline.
**`AwgnFpReplayTests` has nine.** Repeating an explicit guard call at each of nine sites is exactly
the shape of defect that produces a *tenth*, ungated site the next time someone adds a Fact and
forgets — **put the guard inside the shared `DecodeDirectory` and `WriteVerdictLine` helpers
themselves**, once each, so every existing and future caller inherits it automatically and cannot
opt out short of deleting the guard from the helper (a much more visible, reviewable change than a
missing call at a new site).

- **Reuse `AssertPathUntracked` verbatim** (HK-018) — copy `FpParityP3Tests.cs:283-304`'s exact
  implementation (`git ls-files --error-unmatch <relative-path>`, exit code 0 ⇒ tracked ⇒ fail) into
  each of `Row0rCarryForwardTests.cs` and `AwgnFpReplayTests.cs` (both already stand-alone, per the
  existing "duplicated rather than shared" convention — do not introduce a new shared base class or
  utility file as part of this task; that is a larger refactor than this defect needs, and the
  duplication is already this codebase's chosen convention for this exact family of test).
- **In `AwgnFpReplayTests.DecodeDirectory`** (`:457`): call `AssertPathUntracked` on both
  `slotsCsvPath` and `decodesCsvPath` immediately after they're constructed (`:471-472`), **before**
  either `StreamWriter` opens (`:473-474`) — matching `FpParityP3Tests`'s own "a guard that runs
  after the write is not a guard" comment (`:180-181`) exactly.
- **In `AwgnFpReplayTests.WriteVerdictLine`** (`:549`): same guard on `path` (`:551`), before
  `File.AppendAllText` (`:552`).
- **In `Row0rCarryForwardTests.DecodeDirectory`** (`:141`): same guard on both CSV paths (`:154-156`),
  before either `StreamWriter` opens.
- **Redirect the default write target to a gitignored `_out/`, not just guard the tracked one:**
  a guard that only *fails loudly* still leaves every Fact red until someone manually redirects it —
  do both, matching `FpParityP3Tests`'s own model exactly (guard **and** a safe default target):
  - `Row0rCarryForwardTests.cs:85`: `outDir` → `qa/rr-study/fp-parity/_out/` (**already gitignored**,
    `.gitignore:231` — no new ignore entry needed, this class can move today).
  - `AwgnFpReplayTests.cs`, all nine `outDir`/`root`-derived paths above: → a new
    `qa/rr-study/awgn-fp-replay/_out/`. **Add this to `.gitignore`** (near the existing
    `qa/rr-study/awgn-fp-replay/_work/` entry, `.gitignore:222`, and the `fp-parity/_out/` entry and
    its explanatory comment, `.gitignore:225-231` — extend that comment to cover both families
    rather than writing a second near-duplicate one).
  - With both the redirect AND the guard in place, the guard becomes a defence against a *future*
    edit that points `outDir` back at a tracked path by mistake — it should never actually fire in
    normal operation once the redirect lands. Keep it anyway (belt-and-braces, this codebase's own
    idiom — see `JsonConfigStore.SaveAsync`'s own comments on exactly this reasoning for its
    null-config guards).

### 1.4 Promotion into `results/` — check before assuming this is compatible

`FpParityP3Tests`'s own docstring states the model this task adopts: *"Promotion into `results/` is
a separate, deliberate redact-then-rescan-then-commit step — never this fixture's own write."*
**Before landing the redirect, check whether anything currently depends on these two classes writing
directly into `results/`** — e.g., a follow-on script, a report generator, or a documented manual
step in an existing `qa/rr-study/*.md` report that says "run this Fact, then look in `results/`."
Grep the `qa/rr-study/awgn-fp-replay/` and `qa/rr-study/fp-parity/` trees for references to the
specific filenames these Facts produce (`row0b_baseline_*.csv`, `m1m4_s5_*.csv`,
`row0_verdicts.txt`, etc.) before assuming the redirect is a no-op for anyone using these tests'
output today. If something does depend on the current path, say so in the PR description rather
than silently breaking it — do not fix that dependency as part of this task without checking with
QA/Architect first (scope creep guard, §5 below).

## 2. Tests

This task is itself a test-infrastructure fix; the required proof is negative-then-positive:

1. **Before the fix** (do this first, on the unmodified files, to confirm the defect is real and not
   already mitigated by something this task's author missed): construct a throwaway tracked file at
   one of the target paths (e.g. `qa/rr-study/fp-parity/results/_devtask_probe.csv`, committed to a
   scratch/local branch only, never pushed) and run the affected Fact; confirm it silently overwrites
   the probe file. Delete the probe afterward; do not leave it committed anywhere.
2. **After the fix:** the same probe-file setup must now cause the affected Fact to **fail** with the
   `AssertPathUntracked` message, not silently overwrite the probe.
3. **Run every Fact in both classes at least once** (`dotnet test --filter
   "FullyQualifiedName~Row0rCarryForwardTests|FullyQualifiedName~AwgnFpReplayTests"` — this
   deliberately bypasses the `Category!=AwgnFpReplay` filter, on purpose, since that's exactly the
   unfiltered-run scenario this defect needs to be safe under) and confirm each one now writes into
   `_out/` and **zero files under either tracked `results/` directory change**
   (`git status --short qa/rr-study/fp-parity/results/ qa/rr-study/awgn-fp-replay/results/` empty
   before and after the run).
4. Confirm `_out/` for both families is actually gitignored after the `.gitignore` edit
   (`git check-ignore -v qa/rr-study/awgn-fp-replay/_out/anything.csv` reports a match).

## 3. Rigour controls

1. **Do not touch any already-committed file under either `results/` directory.** This task fixes
   where FUTURE runs write; it is not a redaction pass over existing committed data (that data is
   already confirmed clean per the Architect's check this session).
2. **Do not change what either class measures or asserts.** This is a write-target and
   guard-placement fix only — no Fact's decode logic, assertions, or `[Trait]` categories change.
3. **Verify §1.4 (promotion dependency check) before landing the redirect**, not after — if something
   depends on the current path, that changes this task's own scope and needs a decision from
   QA/Architect before the PR, not a silent workaround inside it.
4. **The guard must run before any file is opened**, not after (repeat of `FpParityP3Tests`'s own
   stated principle, `:180-181`) — verify this by reading the diff, not just running the tests, since
   a guard placed after a `using var writer = new StreamWriter(...)` line would already have
   truncated the file by the time it fires.

## 4. Scope guardrails — what this is NOT

- **Not a refactor into a shared base class or utility.** Both classes stay standalone, matching the
  existing "duplicated rather than shared" convention already documented in `AwgnFpReplayTests.cs`'s
  own comments about `Row0rCarryForwardTests`'s relationship to it.
- **Not a fix to the `pre_merge_check.py` filter.** `Category!=AwgnFpReplay` staying the default is
  a separate, Captain-initiative decision (HK-006); this task does not touch that file or propose
  changing the filter.
- **Not a redaction-map audit of the already-committed CSVs.** Confirmed clean this session; out of
  scope here.
- **Not a decision about §1.4's promotion-dependency question if one is found** — surface it, don't
  resolve it unilaterally.

## 5. Deliverables

1. `AssertPathUntracked` added to both `Row0rCarryForwardTests.cs` and `AwgnFpReplayTests.cs`
   (verbatim reuse of `FpParityP3Tests.cs:283-304`'s implementation), called inside the shared
   `DecodeDirectory`/`WriteVerdictLine` helpers, before any write.
2. `outDir`/`root`-derived write targets in both classes redirected to a gitignored `_out/` (new
   `.gitignore` entry for `awgn-fp-replay/_out/`; `fp-parity/_out/` already exists).
3. §1.4's promotion-dependency check, with its finding stated in the PR description either way.
4. All four checks in §2 run and reported, negative-then-positive.
5. A short PR description confirming `git diff --stat main -- src/ native/` is empty (this is a
   `tests/`-only change).

QA verifies against this task before recommending merge (HK-002/HK-006); the Captain signs off the
merge itself (HK-010).

## 6. References

| Reference | Content |
|---|---|
| `memory/rr-study-matched-csv-nfr021-contamination.md` | The first two incidents, 2026-09-06 |
| `tests/OpenWSFZ.Ft8.Tests/FpParityP3Tests.cs:37-44,180-183,283-304` | The correct pattern to backport, verbatim |
| `tests/OpenWSFZ.Ft8.Tests/Row0rCarryForwardTests.cs:85-91,141-160` | Defect site 1 |
| `tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs:98,140,190,237,276,345,390,457-474,549-554` | Defect site 2, all call sites + both shared helpers |
| `.gitignore:222-231` | Existing `_work/`/`_out/` ignore entries — extend the comment, add one line |
| `qa/rr-study/fp-parity/results/`, `qa/rr-study/awgn-fp-replay/results/` | The two tracked, redaction-mapped directories this task protects |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_018hitYaAmoBNwbRKNMuCk3m*
