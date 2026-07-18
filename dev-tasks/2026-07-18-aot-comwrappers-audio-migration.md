# DEV TASK — Native AOT / NAudio COM interop migration (ComWrappers)

**Date:** 2026-07-18
**Prepared by:** QA Engineer
**Motivating goal (Captain, this session):** build installers for end users.
**Status:** **DEFERRED — backlog, not scheduled.** Captain's decision 2026-07-18: get a
working standalone binary first via the separate, smaller
`dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md`, which needs none of this
work. Revisit this document only when Native AOT specifically (not just "a working binary")
becomes the actual goal. When resumed, Phase A (spike) must report back before Phase B
(implementation) is scoped in detail — see §3.

---

## 0. Read this first — you may not need this migration to ship an installer

Two things are being conflated under "the AOT problem" and they are not the same
requirement:

1. Whether the app can be packaged into an installer and handed to end users.
2. Whether the binary inside that installer is a Native AOT (`PublishAot=true`) executable.

A **self-contained, non-AOT publish** —

```
dotnet publish -c Release -r win-x64 --self-contained
```

(i.e. everything the daemon's Release-build gate already does, minus
`-p:PublishAot=true`) — produces a runnable folder today, with zero code changes, JIT-based,
full COM interop intact, WASAPI working exactly as it does under `dotnet run`. That folder can
be wrapped in a conventional Windows installer (Inno Setup, WiX/MSIX, etc.) this week. The only
costs versus AOT: the install carries the .NET runtime (tens of MB larger) and starts via JIT
rather than instant native code — neither affects correctness.

**If the goal is simply "give users a `Setup.exe` that works," that path does not depend on
anything below and can be scoped as its own small dev-task immediately.** This document is for
the case where Native AOT specifically is wanted (smallest footprint, no bundled runtime, fastest
cold start) — worth confirming with the Captain which outcome is actually desired before
committing to Phase B's effort. Phase A (spike) is cheap either way and settles the question with
evidence rather than guesswork, so it's worth doing regardless.

---

## 1. Context

`OpenWSFZ.Daemon.csproj` already publishes AOT structurally (`PublishAot` flips on whenever
`RuntimeIdentifier` is set) but the resulting binary cannot capture, enumerate, or play audio.
Reproduced live tonight (2026-07-18): running the published `.exe` directly threw

```
AudioCaptureException: Cannot capture from device '...':
Common Language Runtime detected an invalid program. The body of method
'Void NAudio.CoreAudioApi.Interfaces.MMDeviceEnumeratorComObject..ctor()' is invalid.
```

**Root cause:** NAudio's `MMDeviceEnumerator` and related WASAPI types activate via classic
`[ComImport]` COM interop. NativeAOT compiles with `BuiltInComInterop.IsSupported=false`, so that
activation machinery is stripped/mis-emitted at compile time — the CLR then rejects the resulting
method body outright.

**This is not new** — it was identified, reproduced, and explicitly deferred during
`2026-05-21-p4-audio-pipeline` (see `openspec/changes/archive/2026-05-21-p4-audio-pipeline/qa-review.md`
and the source comment atop `WasapiAudioDeviceProvider.cs`):

> "The NativeAOT-published binary... does not support WASAPI and is not the operational binary.
> It exists solely as a structural prove-out... Resolution (ComWrappers migration) is Phase 6."

That Phase 6 item was never started. Note also that Phase 4's `design.md` (§9, "AOT
considerations") asserted "NAudio 2.2.1 compiles clean under AOT... for the enumeration path" —
tonight's reproduction shows that optimism did not hold even for enumeration/capture activation;
treat that line in the old design doc as superseded, not as evidence the problem is narrower than
described above.

---

## 2. Scope — exact call sites affected

All Windows-only, gated behind `WASAPI_SUPPORTED`:

| File | NAudio COM surface used |
|---|---|
| `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs` | `MMDeviceEnumerator` (capture device enum) |
| `src/OpenWSFZ.Audio/WasapiAudioOutputDeviceProvider.cs` | `MMDeviceEnumerator` (render device enum) |
| `src/OpenWSFZ.Audio/WasapiAudioSource.cs` | `MMDeviceEnumerator` + `WasapiCapture` (live capture pipeline) |
| `src/OpenWSFZ.Daemon/WasapiTxPlayer.cs` | `MMDeviceEnumerator` + `WasapiOut` (TX playback) |
| `src/OpenWSFZ.Daemon/AudioOnlyPttController.cs` | none directly — delegates entirely to `WasapiTxPlayer`; confirmed by inspection, no change expected here beyond re-verifying after `WasapiTxPlayer` changes |
| `src/OpenWSFZ.Audio/StaThread.cs` | none — generic STA-thread dispatcher, needed regardless of which COM interop mechanism is used underneath; **do not assume it needs changing, but re-verify** |

**Not in scope:** `NAudio.Wave.SampleProviders` (`WdlResamplingSampleProvider`,
`BufferedWaveProvider`) are pure managed code with no COM/reflection dependency — already
AOT-safe per the original P4 design and confirmed by the fact enumeration/capture, not resampling,
is what throws. Leave these untouched; only the COM-activation layer (`MMDeviceEnumerator`,
`WasapiCapture`, `WasapiOut` and the underlying `IMMDeviceEnumerator` / `IMMDevice` /
`IPropertyStore` / `IAudioClient` / `IAudioCaptureClient` / `IAudioRenderClient` COM interfaces)
needs replacing.

---

## 3. Phase A — Spike (time-box: recommend 1–2 days before committing to Phase B)

NAudio is a third-party package (`Directory.Packages.props`, pinned `2.2.1`) — its
`[ComImport]` interop cannot be patched in place. Before writing production code, establish which
of these is actually true:

1. **Has upstream NAudio already solved this?** 30 minutes of research against NAudio's GitHub
   issues/PRs for "NativeAOT" / "ComWrappers" before assuming 2.2.1 (pinned since P4, over a
   year of NAudio releases ago) is still the state of the art. If a newer release or a documented
   workaround exists, that changes everything below.
2. **If not, is a minimal hand-rolled `ComWrappers`-based WASAPI binding — covering only the
   handful of interfaces this app actually calls (`IMMDeviceEnumerator`, `IMMDevice`,
   `IPropertyStore` for friendly names, `IAudioClient`, `IAudioCaptureClient`,
   `IAudioRenderClient`) — realistic?** This means bypassing `NAudio.CoreAudioApi` entirely for
   the COM-activation layer while keeping NAudio for the pure-managed pieces noted in §2. Build
   the smallest possible spike (e.g. just device enumeration) and prove it survives a real
   `dotnet publish -r win-x64 -p:PublishAot=true` + standalone run, not just `dotnet build`.
3. **If both of the above are too costly for the value delivered, staying on self-contained JIT
   permanently is a legitimate outcome**, not a failure to report quietly. It's the status quo
   already ("dotnet run is the documented working deployment model") and, per §0, does not block
   installers.

**Deliverable of Phase A:** a short written recommendation — which option, a rough effort
estimate for Phase B if proceeding, and what was found upstream — reported back before any of §4
is scoped further or implemented.

---

## 4. Phase B — Implementation (do not start until Phase A's recommendation is agreed)

Shape only, pending Phase A's actual findings:

- New minimal WASAPI COM-interop module (e.g. `OpenWSFZ.Audio.Interop`) built on `ComWrappers`
  for the interfaces enumerated in §3.2.
- Swap the four call sites in §2 one at a time, each independently reviewable and testable — do
  not attempt all four in a single changeset (same "independently reviewable blast radius"
  principle already used on other multi-part changes in this codebase, e.g. the
  `f-004-operator-visibility-improvements` kickoff).
- Re-verify `StaThread` needs no change (WASAPI's apartment-threading requirement is orthogonal
  to which COM activation mechanism is used).
- `runtimeconfig.template.json`'s existing COM-interop-override entry was flagged as dead/
  misleading in the P4 `qa-review.md` (item A-3) because it cannot affect NativeAOT. Once real
  ComWrappers activation lands, re-assess whether it does anything now, and either restore it
  with a corrected comment or remove it — don't leave a stale entry unexamined.
- Update the now-stale AOT-limitation comments once fixed — `WasapiAudioDeviceProvider.cs` and
  `WasapiAudioOutputDeviceProvider.cs` (both ~lines 9–13) and `OpenWSFZ.Daemon.csproj` (~lines
  11–17) all currently document the limitation as present; false documentation left behind is
  worse than no documentation.

---

## 5. Tests / Acceptance Criteria

- **AC-1:** Full existing unit/integration suite passes unchanged — behavioural parity with the
  NAudio COM path (device enumeration results, capture sample data, TX playback timing).
- **AC-2 (the real proof):** A genuine `dotnet publish -c Release -r win-x64 --self-contained
  -p:PublishAot=true` binary, launched standalone (not via `dotnet run`), successfully enumerates
  capture and render devices, captures live audio, and completes a TX playback cycle. Code review
  or a `dotnet run` pass does **not** satisfy this — this is exactly the class of claim that needs
  to be exercised, not read (same standing concern as the f-003 flaky-decode-test precedent).
- **AC-3:** `tools/pre_merge_check.py`'s AOT-publish gate continues to pass.
- **AC-4:** No regression to the Linux (`arecord`) or macOS (`sox`) capture paths — confirm the
  `WASAPI_SUPPORTED` compile guard still correctly excludes this code elsewhere.
- **AC-5:** Any new COM interop correctly releases COM references (`ComWrappers` ref-counting
  behaves correctly on dispose/finalize) — a leak here is a slow handle/memory leak over an
  unattended run, which is this app's actual usage pattern (a background daemon left running for
  a contest weekend). QA will look at this specifically during review.

---

## 6. Installer follow-up

Superseded by the split described in the Status line above.
`dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md` covers getting a working
standalone binary now; actual installer packaging (WiX Toolset vs. Inno Setup vs. MSIX,
code-signing, update channel) remains a further, even-later dev-task once that one lands.

---

## 7. References

- `src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj` — `PublishAot` condition (line 18) and the AOT/
  COM caveat comment (lines 11–17).
- `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs` (lines 9–13) and
  `WasapiAudioOutputDeviceProvider.cs` — current AOT-limitation source comments, to be rewritten
  once fixed.
- `openspec/changes/archive/2026-05-21-p4-audio-pipeline/qa-review.md` — original diagnosis,
  item A-3 (`runtimeconfig.template.json` dead code), and the Phase 6 deferral.
- `openspec/changes/archive/2026-05-21-p4-audio-pipeline/design.md` §9 — original (superseded)
  AOT assessment.
- `tools/pre_merge_check.py` — existing AOT-publish gate (`dotnet publish ... -p:PublishAot=true`),
  reusable as the AC-2 verification harness.
- `Directory.Packages.props` — `NAudio` pinned at `2.2.1`; check for newer releases during Phase A.
- Reproduction: this session, 2026-07-18 — standalone AOT-published `.exe` run directly, capture
  failed on `MMDeviceEnumeratorComObject..ctor()` with "invalid program."
