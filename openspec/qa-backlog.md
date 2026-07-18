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

**Status: RESOLVED, merged 2026-07-09** (`PR #64`, `c2a8227`). Recurred exactly as predicted
below — flaked `FR-009` again on the PR #63 merge-to-main run (`ubuntu-latest` this time), which
prompted implementing the suggested fix rather than deferring again. `DecodeEventBus`,
`AudioOffsetEventBus`, and `TxEventBus` now carry a shared `appScope` GUID (generated once in
`Program.cs`, threaded through `WebApp.Create`), and `BroadcastDecodes`/`BroadcastAudioOffset`/
`BroadcastTxState` scope-filter exactly like `BroadcastCatStatus` already did. Verified with 10
repeated full `OpenWSFZ.Web.Tests` runs (5 Windows, 5 WSL/Linux — the platform the recurrence
actually hit) plus full-solution runs on both platforms, all green; CI green on all three
platforms on the PR. New regression test `Broadcast_FromDifferentAppInstance_DoesNotReachThisFixturesSocket`
proves the guard directly rather than relying on absence-of-flakiness. Full handoff:
`dev-tasks/2026-07-09-n6-websocket-broadcast-scope-guard.md`. Kept below for history only, no
longer an open item.

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

---

## N7 — possible N6 recurrence: local build/test failed then passed on immediate retry, no code change between runs

**Status:** OPEN, unconfirmed — logged on the Captain's say-so alone; not yet reproduced or
diagnosed by QA. Recorded per his explicit request ("just record it") rather than investigated in
the moment.
**Severity:** Unknown pending investigation (Low if it is in fact N6-shaped, per that item's own
severity rationale — test-isolation only, no production impact)
**Source:** Captain, 2026-07-09, on branch `feat/qso-confirmation-band-awareness`, immediately
after QA's `min-width` CSS fix + `tasks.md` edits for that change (see
`openspec/changes/qso-confirmation-band-awareness/tasks.md` 6.4/7.4/8.8)
**File:** unknown — no failing test name, error text, or platform captured

The Captain compiled and ran the test suite locally, it failed, and an immediate retry with no
intervening code change succeeded. He states this directly correlates with N6 (the
`WebSocketHub` unscoped-broadcast cross-test-contamination flake, `PR #64`, RESOLVED
2026-07-09 — see above) — i.e. the same "fail once, pass on identical retry" signature N6 produced
before its fix.

This is notable because N6 was supposedly closed the same day, verified with 10 repeated full
`OpenWSFZ.Web.Tests` runs across both Windows and Linux plus a dedicated regression test
(`Broadcast_FromDifferentAppInstance_DoesNotReachThisFixturesSocket`). If this is a genuine
recurrence, either that fix has a gap the repeated-run verification didn't hit, or a different,
as-yet-unscoped broadcast path is producing the same symptom shape. Equally plausible and *not*
yet ruled out: this branch's own changes at the time were CSS- and Markdown-only (no `.cs` files
touched), so a genuine N6-shaped test failure caused by this branch's own edits would be
surprising — QA's own working theory when this was first raised conversationally was mundane
build-lock contention from two concurrent local `dotnet build`/`dotnet test` invocations (QA's
review runs and the Captain's own), which produces an unrelated but superficially similar
"fails, retry succeeds" pattern (MSBuild "file in use") with no relation to WebSocket broadcast
scoping at all.

**Next step, if/when this recurs:** capture the actual failing test name, exception/assertion
text, and platform *before* retrying — the retry-and-move-on pattern is exactly what let N6 sit
undiagnosed across two separate PRs (#54 and #63) before it was finally actioned. Without that
detail this entry cannot be distinguished from ordinary build-lock contention, nor confirmed as a
genuine N6 regression.

---

## N8 — `DecodeFilterStoreAdmitNewValuesTests`' 3.6 concurrency test asserts an invariant the production code never promised

**Status: RESOLVED, merged 2026-07-18** (`PR #86`, `16afb37`). Test-only fix, exactly as scoped in
the handoff — `ConcurrentSetCallsRacingAdmitNewValues_NeverThrowOrCorruptState`'s final assertion
now requires `AllowedItuZones` non-null, non-empty, and a subset of `{0..19} ∪ {27}`, instead of an
exact count of 1. `DecodeFilterStore`/`Set`/`AdmitNewValues`/`AdmitOne` in `WebApp.cs` untouched, as
required (AC-2) — confirmed via diff, the only file changed is the test. QA independently re-derived
the lock-serialisation argument for why `NotBeEmpty()` is a provable invariant, not a hopeful
loosening: since `_lock` totally orders all 120 racing critical sections, if the temporally-last one
belongs to an `AdmitNewValues` call, all 20 `Set()` calls have already committed before it (by
definition of "last"), so `AllowedItuZones` is guaranteed non-null at that point. Verified
independently before merge: 12 additional consecutive local runs of the isolated test (green, on
top of the developer's own 15), a full local `dotnet test OpenWSFZ.slnx -c Release` run (1297/1297
green), a clean `tools/pre_merge_check.py` run (G9a/build/G3/G8 all PASS, AOT WARN is the known
local `vswhere.exe` toolchain gap, unrelated), and CI green on all three platforms on PR #86. One
transient, non-reproducing "Full test suite (Release) FAIL" was observed on QA's *first*
`pre_merge_check.py` run (detail lost to an incidental `tail -80` truncation) but did not recur on
immediate rerun or on the separate manual full-suite run — attributed to an unrelated flake
elsewhere in the suite, not this diff, given the change is scoped to a single file in one test
project that passed clean both in isolation and in-suite. Original entry retained below for the
root-cause record.

**~~Status: OPEN~~ — found 2026-07-18 on the `qso-transcript-panel` (PR #85) merge-to-main CI run.**
**Severity:** Low (test-only defect; the underlying `DecodeFilterStore` behaviour it misjudges is
already documented, accepted, race-safe production behaviour — no production impact)
**Source:** QA, merge-to-main CI run for PR #85 (`feat/qso-transcript-panel`, unrelated change —
see below), `ubuntu-latest`, run
[29649266618](https://github.com/frank001/OpenWSFZ/actions/runs/29649266618)
**File:** `tests/OpenWSFZ.Web.Tests/DecodeFilterStoreAdmitNewValuesTests.cs:176` — `FR-061: 3.6:
concurrent Set calls racing AdmitNewValues never throw or corrupt internal state`

Confirmed unrelated to PR #85's own changes — that PR touches zero `.cs` files, and this test
belongs to `fix-decode-filter-new-value-admission` (**FR-061**, PR #83), which merged to `main`
five hours earlier with this exact test green on all three platforms, both on its own PR checks
and its archive-commit run. The test simply lost a timing race it was always exposed to.

**Failure observed:**
```
Expected store.Current.AllowedItuZones to contain 1 item(s), but found 2: {0, 27}.
```

**Root cause:** the test seeds `AllowedEntities = {"Seed"}`, fires 100 concurrent
`AdmitNewValues` calls (each `Entity{i}`, all sharing `ItuZone: 27`) against 20 concurrent
`Set()` calls (each a whole-object replace to `AllowedItuZones = {i}`). `DecodeFilterStore.Set`
and `.AdmitNewValues` (`src/OpenWSFZ.Web/WebApp.cs:1910`/`1916`) share one lock, so there is
never torn/corrupted state — the test's own headline claim holds. But its final assertion
(`store.Current.AllowedItuZones` must have exactly 1 item) assumes the *last* `Set()` call to run
is authoritative. That assumption is false whenever the single successful admission of `ItuZone
27` (only one of the 100 racing tasks wins `_seenItuZones.Add(27)` — `WebApp.cs:1964`) happens to
acquire the lock *after* the last `Set()`, which is a legal interleaving under `Task.WhenAll` with
no ordering guarantee between the two task groups. The test's own preceding comment
(`DecodeFilterStoreAdmitNewValuesTests.cs:184-188`) already disclaims this outcome — "not that
every admission survives an arbitrary racing Set" — while the assertion two lines later
contradicts it. `{0, 27}` is a fully valid, uncorrupted `DecodeFilterState`; the test is simply
asserting a stronger guarantee than the code (correctly) provides.

**Suggested fix:** loosen the assertion to match what the test's own comment already says it is
proving — e.g. assert `AllowedItuZones` is non-null, non-empty, and a subset of `{0..19} ∪ {27}`,
rather than an exact count of 1. Do **not** "fix" `DecodeFilterStore` itself — its current
last-write-wins-under-one-lock behaviour is the intentional, already-documented contract (see
`DecodeFilterStoreAdmitNewValuesTests.cs:179-188`'s own comment and design.md Decision 3 for
`fix-decode-filter-new-value-admission`); changing it would be solving a problem that doesn't
exist and risks masking a real future regression behind an artificially loosened guard.

---

## N9 — Native AOT publish is structurally broken for Windows WASAPI audio (NAudio `[ComImport]` incompatible with NativeAOT COM stripping)

**Status:** OPEN, deferred — not scheduled. Full write-up already exists; this entry exists so the
item is tracked in the one place QA backlog items live, not just in a standalone dev-task file.
**Severity:** Low (no production impact — the binary this project actually ships is a
self-contained, non-AOT publish; Native AOT itself is not used for anything user-facing today)
**Source:** QA, 2026-07-18, diagnosing a Captain-reported crash when running the published `.exe`
standalone (root-caused and fixed for the immediate case via PR #87, `24baf6d`)
**File:** `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`, `WasapiAudioOutputDeviceProvider.cs`,
`WasapiAudioSource.cs`, `src/OpenWSFZ.Daemon/WasapiTxPlayer.cs` (COM-activation call sites);
`src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj` (`PublishAot` conditional)

NAudio's `MMDeviceEnumerator`/`WasapiCapture`/`WasapiOut` activate via classic `[ComImport]` COM
interop. NativeAOT compiles with `BuiltInComInterop.IsSupported=false`, stripping that activation
machinery from the native image; the CLR then rejects the resulting method body as "invalid
program" the instant real WASAPI code runs (`MMDeviceEnumeratorComObject..ctor()`). Independently
confirmed by the ILC compiler's own output during a real AOT publish: `ILC: Method
'...MMDeviceEnumeratorComObject..ctor()' will always throw because: Invalid IL or CLR metadata`.

This was known and accepted back in `2026-05-21-p4-audio-pipeline` (the AOT-published binary was
always a "structural prove-out only," never the operational binary) but resurfaced when the
Captain ran a real AOT-published `.exe` standalone and hit the crash directly. The immediate
problem is fixed — a working standalone binary now ships via a self-contained non-AOT publish to
the default `bin/Release/net10.0/<rid>/publish/` (PR #87) — without touching Native AOT itself,
which remains structurally broken for this and is now deliberately isolated to a secondary
`publish-aot/` output consumed by nothing but its own toolchain-compile-check gate.

**Suggested fix:** full write-up already exists —
`dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md`. Two-phase: (A) a bounded spike (~1–2
days) to check whether upstream NAudio has already solved this since this project's `2.2.1` pin,
and if not, prototype a minimal hand-rolled `ComWrappers`-based WASAPI binding for the handful of
interfaces actually used (`IMMDeviceEnumerator`, `IMMDevice`, `IPropertyStore`, `IAudioClient`,
`IAudioCaptureClient`, `IAudioRenderClient`); (B) swap the four call sites over, one at a time,
each independently tested against real hardware. Not scheduled — only worth pursuing if Native
AOT's specific benefits (no bundled .NET runtime, smaller install, faster cold start) become an
actual goal, e.g. as part of future installer polish, since the self-contained non-AOT binary
already ships a fully working, distributable deliverable today.

---

## N10 — TX-D04: every transmitted signal report is still the `+00`/`R+00` placeholder, not the real measured SNR

**Status: RESOLVED, merged 2026-07-19** (`656bd7e`, `fix-tx-report-real-snr`). Real
`DecodeResult.Snr` now threaded through all four TX-composition sites and both ADIF `RstSent`
fields; confirmed by QA reading the diff and by the Captain's own live QSO — ADIF now shows real
values (`RST_SENT:-03`, not `+00`). Verifying this fix is exactly what surfaced **N12/TX-D05**
below (the on-screen TX message rows/Transcript panel were never wired to real data and now show a
stale template) — a display-only follow-on, not a defect in this fix itself. Original entry kept
below for history.

**Status (historical):** OPEN — Captain's explicit instruction (2026-07-18): "This is a real issue that needs to
be raised, the application is able to measure the snr, it should report the correct value." Promoted
from the accepted-risk language in `qso-caller`'s original `design.md` to an active fix.
**Severity:** Medium (protocol correctness — every partner this daemon works logs a fabricated `+00`
signal report in their own ADIF, regardless of actual conditions; not merge-blocking historically
only because it was accepted as a named v1 trade-off, which the Captain has now withdrawn)
**Source:** QA, live-run log review, `logs/openswfz-20260718T185751Z.log` — ten real over-the-air
QSOs in one session, one hundred percent of them `+00`/`R+00`, cross-checked against `ALL.TXT`
showing the daemon had genuine decoded SNR values available in the same cycle.
**File:** `src/OpenWSFZ.Daemon/QsoCallerService.cs` (lines 818, 984, 898),
`src/OpenWSFZ.Daemon/QsoAnswererService.cs` (lines 965, 1056, 1180)

**Suggested fix:** full write-up already exists —
`dev-tasks/2026-07-18-live-run-tx-report-snr-and-reengagement-workflow.md` §2. Thread the matched
`DecodeResult.Snr` (already computed every cycle, already used for `ALL.TXT`/WSJT-X UDP reporting)
through to all four TX-composition sites and the two `QsoRecord.RstSent` ADIF fields; persist the
chosen value for retry-retransmission rather than recomputing it.

---

## N11 — D-CALLER-022: no lightweight way to confirm an already-worked partner actually received the final message

**Status:** OPEN — investigation/design task, not yet scoped to a diff. Captain's framing (2026-07-18):
"it is a regular thing to pursue a correct QSO," i.e. this is a recurring operator need, not a one-off.
**Severity:** Medium (no data-integrity impact — the confirmation-dialog gate correctly prevented any
duplicate ADIF entries — but real RF went out four times to an already-logged partner with no
purpose-built, lighter-weight action available for "make sure they got it")
**Source:** QA, same live-run log review; Captain confirmed intent when asked (re-engaging PA7D
because the partner did not seem to have received the RR73, cancelling each resulting confirmation
dialog since it wasn't new information).
**File:** `src/OpenWSFZ.Daemon/QsoAnswererService.cs` (`ExecuteJumpInAsync`, `D-CALLER-012` jump-in
path, reused here as the only available mechanism), `web/js/main.js` (decode-panel row
affordances/worked-before visibility)

**Suggested fix:** none prescribed — full evidence and candidate directions (a dedicated
lighter-weight resend action; stronger worked-before UI cues on a still-active row; whether the
protocol's own "partner still calling CQ/working someone else" signal already answers the operator's
underlying question without a new TX action at all) are laid out in
`dev-tasks/2026-07-18-live-run-tx-report-snr-and-reengagement-workflow.md` §3. Bring a short design
note back before implementing — this must also not regress `D-CALLER-018`'s abort-is-a-hard-stop
guarantee.

---

## N12 — TX-D05: TX message rows and QSO Transcript show a hardcoded `+00`/`R+00` template, not the real report TX-D04 now sends

**Status:** OPEN — found immediately by the Captain making a real QSO right after `656bd7e`
(TX-D04) merged: ADIF showed real `-03`/`-15`, on-screen Transcript still showed `+00` throughout.
**Severity:** Medium (display-only — no protocol/ADIF/over-the-air content is wrong, confirmed by
reading the TX-D04 diff; but the operator cannot trust the live screen during a QSO, which matters
for exactly the "did they get it" judgement call in N11/D-CALLER-022 above)
**Source:** Captain, 2026-07-19, live QSO with EB3JT immediately after TX-D04 shipped; QA traced
root cause via source read of `web/js/main.js` and `web/js/qsoTranscript.js` against `656bd7e`.
**File:** `web/js/main.js` (`renderMessageRows`, lines ~187–232 — hardcoded `+00`/`R+00` template
strings, reused verbatim by the Transcript's `appendTranscriptEntry('sent', ...)` call);
`src/OpenWSFZ.Web/AppJsonContext.cs` (`TxStatusResponse`, `WsTxStateMessage` — carry no message
text or SNR field, so the frontend has no channel to read the real value from even if it wanted to);
`src/OpenWSFZ.Daemon/QsoCallerService.cs` (no persisted last-sent-message field at all, unlike
`QsoAnswererService`'s existing but unexposed `_lastTxMessage`).

Root cause: the TX message rows / Transcript panel were always a client-side template keyed off
`txState` alone (`qso-transcript-panel`'s own `design.md` says as much), which happened to match
reality only because the real value really was always `+00` before TX-D04. Fixing TX-D04 on the
backend made the template stale; nothing in that fix (correctly scoped to backend/ADIF only) was
asked to touch the display layer.

**Suggested fix:** full write-up already exists —
`dev-tasks/2026-07-19-tx-d05-transcript-and-message-rows-show-stale-template.md`. Persist a real
last-sent-message field on `QsoCallerService` (mirroring `QsoAnswererService`'s existing one),
surface it through `TxStatusResponse`/`WsTxStateMessage`, and have both `renderMessageRows` and the
Transcript's sent-entry logging prefer that real value over the template for any row already
transmitted this session.
