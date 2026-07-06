# QA Backlog

Observations that are not merge-blocking but must be addressed in a future change.
Each item is classified with a severity and the change in which it was first noted.

---

## Process notes (read before authoring a `proposal.md`)

**Every `proposal.md` MUST declare its user-facing status.** On a single line, before the
`## Why` heading, add exactly one of:

```
**User-facing:** yes
```
```
**User-facing:** no
```

A change is **user-facing** if and only if it ships operator-visible behaviour (e.g. a new or
changed feature, UI, API response, or stdout the operator sees). Defect fixes, diagnostics,
QA-study runs, CI/tooling, and documentation-only changes are **not** user-facing.

This declaration is the sole input to the "one user-facing feature = one minor version bump"
rule, enforced mechanically by CI gate **G9** (`version-governance` job in
`.github/workflows/ci.yml`, backed by `tools/check_version_bump.py`). When a PR archives a
`**User-facing:** yes` change, G9 fails the build unless the root `VERSION` file is also bumped;
when the declaration is missing or malformed, G9 fails and names the offending change. The
canonical definition lives in the `release-versioning` capability spec
(`openspec/specs/release-versioning/spec.md`).

The OpenSpec CLI's stock `proposal` template does not scaffold this line (it ships inside the
globally-installed npm package, not the repo), so it is added by convention — don't forget it.

### PR granularity and branch protection (decided 2026-07-05, Captain + QA)

Following `adopt-canonical-version-source` shipping as three separate PRs (#49 hotfix, #50
implement, #51 archive+bump) for what was really one logical change, the Captain flagged the
process as overengineered for a solo-maintainer repo. Two changes were agreed:

- **One PR per OpenSpec change by default.** Implement, archive, and any accompanying `VERSION`
  bump belong in the same branch/PR once tasks are complete and CI is green — do not default to
  a separate follow-up PR just to run `/opsx:archive`. Split into multiple PRs only for a genuine
  reason: an urgent hotfix that shouldn't wait behind unrelated work, or the Captain explicitly
  wanting to review the implementation before archiving.
- **Branch protection on `main` no longer requires an approving review**
  (`required_approving_review_count: 0`, set 2026-07-05). A PR is still required before merging
  (no direct pushes), and all required status checks (`Build & Test` × 3 OSes, `Gate G9`) still
  block a merge — but the review-count requirement was pure friction on a repo with one
  contributor: GitHub disallows self-approval, so every merge needed an `--admin` bypass that
  added a step without adding a check. Revisit both of these if the project ever gains another
  human contributor.

---

## N1 — `Ft8LibInterop`: retry-after-failure produces a confusing exception

**Severity:** Low
**Source:** p13-cross-platform-decoder QA review
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `LoadAndVerify()`

`LoadAndVerify()` registers `NativeLibrary.SetDllImportResolver` as its first step, then performs
the native binary existence check. If the existence check throws (file not present in output dir),
`_initialized` remains `false` and the double-checked lock permits a subsequent retry. On that
second call, `SetDllImportResolver` throws `InvalidOperationException: "A DllImportResolver is
already set for this assembly"`, which buries the original `DllNotFoundException` about the
missing binary.

This path is unreachable in normal operation (a built project always has the binaries in the
output directory), but it would confuse a developer investigating a broken local build.

**Suggested fix:** Guard the `SetDllImportResolver` call with a separate `_resolverRegistered`
volatile flag, or wrap it in `try { … } catch (InvalidOperationException) { /* already
registered */ }` to make it idempotent.

---

## N2 — `Ft8LibInterop`: platform filename computed twice in `LoadAndVerify()`

**Severity:** Cosmetic
**Source:** p13-cross-platform-decoder QA review
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `LoadAndVerify()`

The platform-appropriate filename (`libft8.dll` / `libft8.so` / `libft8.dylib`) is computed once
inside the resolver lambda and a second time outside it for the `File.Exists` check. Both
computations produce the same result via identical `RuntimeInformation.IsOSPlatform` chains.

**Suggested fix:** Extract a `static string GetPlatformLibFileName()` private method and call it
from both sites.

---

## N3 — `Ft8LibInterop`: 6 720-byte heap allocation on every decode cycle

**Severity:** Low
**Source:** p12-ft8lib-port QA review (carry-through); confirmed in p13
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `DecodeAll()`

```csharp
var results = new Ft8NativeResult[MaxResults];   // 140 × 48 bytes = 6 720 bytes, every cycle
```

A fresh 140-element array is heap-allocated on every 15-second decode cycle. The allocation
is negligible at current cycle rates but will appear prominently in any allocation profiler
trace.

**Suggested fix:** `ArrayPool<Ft8NativeResult>.Shared.Rent(MaxResults)` with a corresponding
`Return()` after the slice is extracted, eliminating the per-cycle heap pressure.

---

## N4 — 11 main specs lack a `## Purpose` section (fail `validate --strict`)

**Severity:** Minor
**Source:** p19/p20 archive (2026-06-05); logged as F-011
**Files:** `openspec/specs/{audio-capture, audio-device, build-pipeline, ci-quality-gates, daemon-host, decode-control, decode-log, decoder-ground-truth, dependency-licence-policy, file-logging, requirement-traceability}/spec.md`

OpenSpec's current validation requires every spec to carry both a `## Purpose` and a
`## Requirements` section. Eleven main specs predate that rule and open directly with
`## Requirements`, so they fail `openspec validate --all --strict` (8 passed, 11 failed as of
2026-06-05). This is latent debt, not a regression: the four specs touched by the p19/p20 archive
(`cat-control`, `configuration`, `web-frontend`, `web-server`) were brought into compliance at
that time, but the remaining eleven were deliberately left untouched to keep the archive in scope.

Because the rule only bites when a spec is rebuilt during `openspec archive`, any future change
whose delta touches one of these eleven capabilities will abort mid-archive until the Purpose
section is added — a latent trip-hazard for the next developer.

**Suggested fix:** Add a concise, content-neutral `## Purpose` paragraph above `## Requirements`
in each of the eleven specs (one short sentence describing the capability), then confirm
`openspec validate --all --strict` reports 19/19 passing. Doc-only; no behaviour change.

---

## N5 — `check_version_bump.py` misses a proposal archived in a separate PR from its own creation

**Severity:** Low
**Source:** `g9-automate-release-tagging` archive (PR #53, 2026-07-06)
**File:** `tools/check_version_bump.py` — `_added_proposals()`

The script detects newly-archived proposals via `git diff --name-only --diff-filter=A
<base>...HEAD -- 'openspec/changes/archive/**/proposal.md'`, i.e. it only catches files that are
pure **additions** relative to the PR's base ref. If a change's `proposal.md` is created and
merged to `main` first (as an active, un-archived change) and only archived — i.e. moved under
`openspec/changes/archive/...` — in a **later, separate** PR, git correctly detects that move as a
**rename** (the file already existed on `main` at the old path), not an addition. `--diff-filter=A`
excludes renames, so `_added_proposals()` returns empty and gate G9b silently reports "this PR
archives no new OpenSpec changes; no version bump required" — even if the proposal declares
`**User-facing:** yes` and no `VERSION` bump is present.

Confirmed empirically: `python3 tools/check_version_bump.py origin/main` returned this false-negative
"OK" for PR #53, which archived `g9-automate-release-tagging` (itself `User-facing: no`, so no
enforcement gap materialised in that instance — but the detection logic itself would have missed a
`yes`-declared change archived the same way).

This gap only bites when propose-and-implement and archive happen in **separate** PRs. The
Captain and QA agreed on 2026-07-05 to default to one PR per OpenSpec change (see the Process
notes above) specifically to avoid this shape of split, which makes the trigger rare going
forward — logged here rather than fixed immediately for that reason.

**Suggested fix:** Either (a) add `-M`-aware rename detection and treat a renamed-in file under
the archive path the same as an addition (`git diff --diff-filter=AR` plus reading the *new* path's
content, not the old one), or (b) accept the narrower rename-blind-spot as a documented limitation
and rely on the one-PR-per-change convention to avoid triggering it. Whichever is chosen, add a
regression test/scratch-branch exercise (mirroring `adopt-canonical-version-source` task 4.4) that
specifically covers the split-PR/rename case before changing the script.

---

## N6 — `WebSocketHub.BroadcastDecodes`/`BroadcastAudioOffset`/`BroadcastTxState` lack the scope guard `BroadcastCatStatus` already has

**Severity:** Low (test-isolation flake only; no production impact — a real daemon process hosts
exactly one `WebApp` instance, so there is only ever one scope in practice)
**Source:** found reviewing/merging `f-005-hash-table-saturation-diagnostic` (PR #54, 2026-07-06)
**File:** `src/OpenWSFZ.Web/WebSocketHub.cs`

`ActiveSockets` (the socket→scope registry `BroadcastDecodes`, `BroadcastAudioOffset`, and
`BroadcastTxState` all iterate) is a `static ConcurrentDictionary`, shared by every `WebApp`/test-host
instance created in the same process. `BroadcastCatStatus` already scope-filters
(`if (socketScope != scope) continue;`, explicitly to stop one in-process test host's
`CatPollingService` broadcasting into a concurrently-running test server's sockets — see that
method's own doc comment) but `BroadcastDecodes`, `BroadcastAudioOffset`, and `BroadcastTxState` do
not: they send to every registered socket regardless of which `WebApp` instance registered it.

Observed effect: PR #54's CI run failed `WebSocketTests.WebSocket_DecodeEventReceived_AfterBroadcast`
(FR-009) on `windows-latest` — the test's socket received a stray `audioOffset` frame (from some
other, concurrently-running test's `AudioOffsetEventBus.Publish`) instead of the `decode` frame it
had just triggered. Confirmed unrelated to that PR's own changes (identical files had passed
`windows-latest` in the immediately preceding run; a re-run of the same failed job then passed) — a
pre-existing gap, not a regression. This is the same failure *shape* `b126e61` ("fix(test): eliminate
FR-009 WebSocket broadcast race") already fixed once, for a different cause (that fix made
`BroadcastDecodes`'s own send awaited instead of fire-and-forget); this is a second, distinct
mechanism producing the same symptom — cross-test contamination via the unscoped static registry,
not a within-test timing race.

**Suggested fix:** add the same `scope` parameter and guard to `BroadcastDecodes`,
`BroadcastAudioOffset`, and `BroadcastTxState` that `BroadcastCatStatus`/`AbortAll` already use, and
thread `appScope` through their call sites (`DecodeEventBus`, `AudioOffsetEventBus`, TX event
publishing) the same way `WebApp.Create` already does for CAT status. Low priority given no
production impact, but worth doing before this test flakes again — likely to recur as the Web test
suite grows more WS-connecting tests sharing the same process.
