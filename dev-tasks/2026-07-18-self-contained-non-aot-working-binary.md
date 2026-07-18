# DEV TASK — Working standalone binary (self-contained, non-AOT) + permanent CI gate

**Date:** 2026-07-18
**Prepared by:** QA Engineer
**Motivating goal (Captain, clarified 2026-07-18):** both `dotnet run` **and** direct execution
of the published `.exe` must work, for every merge to `main` going forward — not a one-time local
fix, a standing guarantee enforced by CI (and locally via `tools/pre_merge_check.py`), the same
way the existing AOT-publish gate is enforced today.
**Explicitly out of scope:** installer packaging (WiX/Inno Setup/MSIX), code signing, update
channel — later, separate work. Native AOT itself remains deferred; see
`dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md`.

---

## 1. Context

Tonight's session found two distinct things, and this task fixes the second one and makes sure
it *stays* fixed:

1. **Root cause of the reported crash:** NAudio's `[ComImport]` WASAPI COM activation is
   incompatible with Native AOT — throws `Common Language Runtime detected an invalid program` on
   `MMDeviceEnumeratorComObject..ctor()` the instant real WASAPI code runs in an AOT-compiled
   binary. Real fix is the deferred ComWrappers migration; not needed for this task.
2. **Why a standalone binary is broken at all today:** `OpenWSFZ.Daemon.csproj` sets
   `<PublishAot Condition="'$(RuntimeIdentifier)'!=''">true</PublishAot>` — AOT switches on for
   **any** RID-targeted publish, self-contained or not. `README.md` (lines 260–273) documents
   exactly that command with no override, and CI's own "AOT publish (Daemon)" step
   (`.github/workflows/ci.yml`, ~line 226) publishes the *same* way, explicitly with
   `-p:PublishAot=true`. So the only self-contained binary this project currently produces,
   anywhere, is the AOT one — and it is the one that's broken for Windows audio.

**Why this needs to be a gate, not a one-time fix:** nothing today would stop a future change
from silently reintroducing this — there is no automated check anywhere in CI or
`pre_merge_check.py` that a self-contained *non-AOT* publish exists, runs standalone, and can
reach its own audio endpoints without crashing. `dotnet run` isn't at risk (no RID is ever set for
it, so `PublishAot` never activates) and needs no new gate — but it's worth stating plainly in the
gate's own output that both modes are separately verified, so "ready for merge" claims cover both,
not just whichever one happened to be tested by hand.

---

## 2. Branch

`chore/self-contained-non-aot-publish-gate` — touches CI workflow, the pre-merge check script,
README, and a new E2E-style test; route through a normal PR.

---

## 3. Actions

### 3.1 — Publish command / profile

The fix is an MSBuild command-line override (global properties beat the project file's
conditional `<PropertyGroup>`):

```bash
dotnet publish src/OpenWSFZ.Daemon -c Release -r <rid> --self-contained -p:PublishAot=false
```

**Publish to a distinct output directory**, not the default — the default publish path
(`bin/Release/net10.0/<rid>/publish/`) is the same regardless of `PublishAot`, and CI's existing
AOT publish step already writes there, consumed by the existing E2E tests
(`DaemonProcess.ResolveBinaryPath()`). A second publish into the same folder would silently
clobber the AOT binary those tests expect. Use `-o` to send this publish somewhere separate, e.g.:

```bash
dotnet publish src/OpenWSFZ.Daemon -c Release -r <rid> --self-contained -p:PublishAot=false \
  -o src/OpenWSFZ.Daemon/bin/Release/net10.0/<rid>/publish-selfcontained/
```

Wrap this in either a publish profile (`src/OpenWSFZ.Daemon/Properties/PublishProfiles/`) or a
`tools/publish-selfcontained.ps1`/`.sh` script covering all three RIDs already in the README
(`win-x64`, `linux-x64`, `osx-arm64`) — check `tools/` for the prevailing script style before
picking one.

### 3.2 — New E2E-style verification (the actual proof, automated)

Add a test (new file or extend `tests/OpenWSFZ.E2E.Tests/`) that:

1. Launches the self-contained non-AOT binary from the `publish-selfcontained/` output above —
   reuse `DaemonProcess`'s launch/banner-wait pattern, but parameterize or duplicate
   `ResolveBinaryPath()` so it can point at either publish output rather than only the AOT one.
2. Confirms the welcome banner appears (process didn't crash on startup).
3. Calls `GET /api/v1/status` — expects HTTP 200.
4. Calls `GET /api/v1/audio/devices` **and** `GET /api/v1/audio/output-devices`
   (`src/OpenWSFZ.Web/WebApp.cs` lines ~306, ~314) — expects HTTP 200 with a JSON array
   (empty is fine; CI runners have no real capture hardware). **This is the check that actually
   matters**: it forces the WASAPI COM-activation path to run. An empty array is an acceptable
   pass (no devices present); a 500 or a crashed process is not — that's exactly the failure mode
   reported tonight, and it fires regardless of whether real hardware is attached, since the
   defect is in COM activation itself, not in enumeration results.
5. Runs on all three OSes in the CI matrix, even though the underlying bug is Windows-only (NAudio
   COM interop) — Linux (`arecord`) and macOS (`sox`) shell out to external processes rather than
   using COM, so they're expected to already pass; running the same check everywhere costs little
   and keeps the gate symmetric rather than carrying Windows-only special-casing that's easy to
   forget when the matrix changes later.

### 3.3 — Wire into CI (`.github/workflows/ci.yml`)

Add a new step after the existing "AOT publish (Daemon)" step (~line 226), for each matrix leg:

```yaml
- name: Self-contained (non-AOT) publish
  run: >
    dotnet publish src/OpenWSFZ.Daemon
    -c Release
    -r ${{ matrix.rid }}
    --self-contained
    -p:PublishAot=false
    -o src/OpenWSFZ.Daemon/bin/Release/net10.0/${{ matrix.rid }}/publish-selfcontained/
```

then let the normal `dotnet test` step (which already runs after both publishes) pick up the new
test from 3.2 alongside the existing E2E tests — no separate test-invocation step needed if it
lives in the same `OpenWSFZ.E2E.Tests` project.

### 3.4 — Wire into `tools/pre_merge_check.py`

Add a new gate function (mirroring `step_aot()`, ~line 173) that runs the 3.1 publish locally and
reports PASS/FAIL — this is what makes "ready for merge" claims about this actually checkable in
one command, matching the whole reason `pre_merge_check.py` exists (HK-006). Whether it re-runs
the full E2E devices-endpoint check (3.2) or just confirms the publish succeeds locally (with the
endpoint check left to CI, which has the full OS matrix) is a reasonable implementation choice —
state which was chosen in the PR description.

While in this file: **clarify the existing `step_aot()` gate's PASS meaning** (~docstring around
line 26 and the function itself). Today a PASS there only proves the AOT toolchain compiled the
binary — it says nothing about whether the binary is functionally correct, and Windows WASAPI
audio is known-broken under it. Add a short note (in the docstring and/or the printed detail) so
a future reader doesn't repeat tonight's exact misunderstanding: "AOT publish PASS means it
compiles, not that Windows audio works — see the deferred ComWrappers dev-task."

### 3.5 — Correct `README.md` (lines 260–277)

Update the three documented publish commands to match whichever of 3.1's profile/script exists,
and add one sentence on why `-p:PublishAot=false` (or the profile) is needed, so this doesn't
regress the next time someone edits this section by hand.

---

## 4. Tests / Acceptance Criteria

- **AC-1:** New self-contained non-AOT publish step exists in CI for all three matrix legs and
  succeeds.
- **AC-2:** New E2E test (3.2) passes on all three OSes — banner, `/api/v1/status` 200, and both
  audio-device endpoints 200 against the **non-AOT** binary.
- **AC-3:** `tools/pre_merge_check.py` has a new gate covering this publish path and reports it in
  the PASS/FAIL/WARN/SKIP summary table alongside the existing gates.
- **AC-4:** Existing AOT-publish step and its E2E tests (`DaemonProcess`, `FR-002`/`FR-007`)
  continue to pass unchanged — the new publish output directory must not interfere with the
  existing one.
- **AC-5:** `README.md` corrected per 3.5; a fresh read of that section no longer reproduces
  tonight's bug if followed literally.
- **AC-6:** `dotnet run` (no RID, JIT) is unaffected by anything in this task — call this out
  explicitly in the PR description as "verified unaffected," not left implicit.
- **AC-7:** Full existing test suite otherwise green; no changes anticipated to
  `src/OpenWSFZ.Audio/**` or `src/OpenWSFZ.Daemon/**` application code — this task is publish
  tooling, CI, and test infrastructure only.
- **AC-8:** On an actual Windows machine with a real capture device (manual, one-time — CI can't
  do this part), confirm the self-contained non-AOT `.exe`, launched standalone, genuinely
  captures live audio end-to-end, not just that the devices endpoint returns 200. CI's check
  proves the COM-activation path doesn't crash; it can't prove a real microphone produces real
  samples. Record this manual confirmation in the PR description.

---

## 5. References

- `src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj` (line 18) — the `PublishAot` conditional this task
  overrides at the command line, not by editing the file.
- `.github/workflows/ci.yml` (~lines 221–240) — existing AOT publish step this task adds a sibling
  step next to.
- `tests/OpenWSFZ.E2E.Tests/DaemonProcess.cs` — launch/banner-wait pattern to reuse or parameterize
  for 3.2.
- `src/OpenWSFZ.Web/WebApp.cs` (~lines 306, 314) — the two audio-device endpoints the new test
  calls.
- `tools/pre_merge_check.py` (`step_aot()`, ~line 173; module docstring, ~line 26) — existing gate
  pattern to mirror, and the PASS-meaning clarification from 3.4.
- `README.md` (lines 260–277) — publish instructions this task corrects.
- `dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md` — deferred; the actual Native-AOT fix,
  not needed for this task.
- Reproduction, this session, 2026-07-18: standalone AOT-published `.exe` failed capture with
  `MMDeviceEnumeratorComObject..ctor()` "invalid program"; root-caused to `PublishAot` silently
  activating on any RID-targeted publish, which is exactly what both README's documented command
  and CI's existing publish step already do.
