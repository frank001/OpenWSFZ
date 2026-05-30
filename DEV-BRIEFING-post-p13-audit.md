# Developer Briefing — Post-p13 Codebase Audit

**Date:** 2026-05-30  
**Branch:** `feat/p13-cross-platform-decoder`  
**Prepared by:** QA  
**Purpose:** Holistic review of requirements completeness, irrelevant code, and repository hygiene before the p13 branch is merged and any new work begins.

---

## 1. Requirements Status

### 1.1 — FR-017 is NOT implemented (Must Have)

**Severity: High — missing Must Have requirement**

FR-017 (Decode start/stop control) was added to REQUIREMENTS.md in version 1.2 (2026-05-22) and has not been implemented in any subsequent phase.

**What it requires (abridged):**

> The main UI SHALL provide a control (button or toggle) that starts and stops the FT8 decode pipeline. The current decode state SHALL be clearly indicated in the status area. The decode state SHALL persist to the configuration file so that a session explicitly stopped by the operator does not auto-resume on the next application launch.

**What is missing:**

| Component | Status |
|---|---|
| `AppConfig.DecodingEnabled` field | ❌ Not in `AppConfig.cs` |
| API endpoint for start/stop toggle | ❌ Not in `WebApp.cs` |
| Program.cs: conditional pipeline start based on `DecodingEnabled` | ❌ Pipeline always starts if a device is configured |
| UI: start/stop button/toggle on main page | ❌ Not in `index.html` or `main.js` |
| UI: decode state badge in status area | ❌ Not present |
| Config save on state change | ❌ Cannot save a field that does not exist |

**Current behaviour:** The pipeline starts unconditionally on launch if `AudioDeviceId` is set. There is no way to stop decoding without clearing the device selection (which is not the same thing) or restarting the process.

**Action required:** Implement FR-017 in a new change. The implementation touches `AppConfig`, `WebApp` API, `Program.cs`, `index.html`, and `main.js`.

---

### 1.2 — All other requirements: verified present

| Requirement | Status |
|---|---|
| FR-001 FT8 receive-only decode | ✅ `Ft8Decoder` + `ft8_lib` native |
| FR-002 Self-hosted web UI | ✅ `WebApp.cs`, Kestrel |
| FR-003 USB audio device selection | ✅ `PlatformAudioDeviceProvider`, settings UI |
| FR-004 Configuration persistence | ✅ `JsonConfigStore` |
| FR-005 Configurable config-file path | ✅ `ConfigPathResolver`, `LaunchOptions` |
| FR-006 Default config ships with app | ✅ `JsonConfigStore` creates default on first run |
| FR-007 Terminal welcome banner | ✅ `WelcomeBannerEmitter` |
| FR-008 Waterfall display | ✅ `SpectrumAnalyser`, `spectrum.js` |
| FR-009 Decoded messages list | ✅ `DecodeEventBus`, `main.js` |
| FR-010 Settings page navigable | ✅ `settings.html` |
| FR-011 Save action on Settings | ✅ `settings.js`, POST `/api/v1/config` |
| FR-012 Dark theme by default | ✅ `app.css` |
| FR-013 CSS-file-based theming | ✅ |
| FR-014 Frontend folder layout | ✅ `web/` |
| FR-015 Frontend files user-editable | ✅ |
| FR-016 Strict UI visibility rule | ✅ (enforced by process) |
| FR-017 Decode start/stop control | ❌ **See §1.1 above** |
| FR-018 Cycle countdown timer | ✅ `ShowCycleCountdown` in `AppConfig`, `main.js` lines 70–148 |
| FR-019 Configurable logging | ✅ `LoggingPipeline`, Serilog, `LogLevel` in `AppConfig` |
| FR-020 Audio activity in heartbeat | ✅ `AudioActivityMonitor` |
| FR-021 Capture stop logging | ✅ `CaptureManager` events |
| FR-022 File logging sink | ✅ `LoggingPipeline` |
| FR-023 Log rotation | ✅ `LogRotationService` |
| FR-024 Log file retention | ✅ `LogRotationService` |
| FR-025 Audio device friendly name | ✅ `AudioDeviceFriendlyName` in `AppConfig` |
| FR-026 FT8 decode throughput | ✅ Performance test present and passing |
| FR-027 Dial frequency configuration | ✅ `DecodeLogConfig.DialFrequencyMHz` |
| FR-028 ALL.TXT decode log | ✅ `AllTxtWriter` |
| FR-029 Real-signal fixture tests | ✅ `RealSignalFixtureTests` — G6 gate passes on all 3 platforms |
| NFR-001 Cross-platform | ✅ Fixed in p13 — Linux x64 and macOS ARM64 binaries committed |
| NFR-016 G6 CI gate | ✅ Tests pass (not skip) on all three matrix legs |

---

## 2. Irrelevant Code — Remove or Correct

### 2.1 — Stale XML documentation: `FftCompute.cs`

**File:** `src/OpenWSFZ.Ft8/Dsp/FftCompute.cs`, line 7–8  
**Severity:** Cosmetic

The class summary says:

> Used by both `SpectrumAnalyser` (waterfall display) and `SymbolExtractor` (FT8 decode spectrogram path).

`SymbolExtractor` was part of the homegrown DSP pipeline and was deleted when ft8_lib was ported in p12. Only `SpectrumAnalyser` now uses `FftCompute`.

**Fix:** Change the summary to:

```csharp
/// <summary>
/// Shared radix-2 Cooley-Tukey in-place FFT for power-of-2 sizes.
/// Used by <see cref="SpectrumAnalyser"/> for the waterfall display.
/// </summary>
```

---

### 2.2 — Stale XML documentation: `SpectrumAnalyser.cs`

**File:** `src/OpenWSFZ.Ft8/Dsp/SpectrumAnalyser.cs`, line 99  
**Severity:** Cosmetic

The `Fft()` method comment says:

> Delegates to the shared FftCompute utility so the algorithm is not duplicated between this class and SymbolExtractor's spectrogram path.

`SymbolExtractor` is gone. The delegation rationale still holds (avoid duplication), but the reference to a deleted class is misleading.

**Fix:** Change the comment to:

```csharp
// Delegates to the shared FftCompute utility — keeps the FFT implementation in one place
// so it can be reused by additional analysers (e.g. a future protocol monitor) without duplication.
private static void Fft(float[] re, float[] im) => FftCompute.Fft(re, im);
```

---

### 2.3 — Internal diagnostic labels in `Program.cs`

**File:** `src/OpenWSFZ.Daemon/Program.cs`, lines ~133, ~159  
**Severity:** Low

Two variables carry `// L-13 (DIAG)` and `// L-14 (DIAG)` labels — internal bookkeeping markers from the development session that have no meaning to any reader unfamiliar with session history:

```csharp
var captureRestartCount = 0; // L-13 (DIAG): counts auto-restart attempts
```

```csharp
// L-14 (DIAG): log the IsCapturing guard result …
```

These are not harmful but are noise. A reader encountering "L-13" for the first time has no reference point.

**Fix:** Remove the `// L-13 (DIAG)` and `// L-14 (DIAG)` suffixes. The surrounding comments already explain the intent; the labels add nothing.

---

### 2.4 — Five permanently-skipped tests in `Ft8DecoderFixtureTests.cs`

**File:** `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs`  
**Severity:** Low — deferred decision required

Five `[Fact(Skip = ...)]` tests will never pass in their current form because `TestFt8Encoder.PackType1` hardcodes `i3=0` (FREE TEXT) rather than `i3=1` (Standard QSO). `ft8_lib` correctly rejects `i3=0` payloads.

The class-level doc explains this clearly. The tests are retained as context, which is reasonable.

**Options:**

A. **Delete the five skipped tests** — they assert nothing currently and never will without fixing the encoder. Keeping skipped tests indefinitely trains developers to ignore skip output. The authoritative oracle (G6 gate) is `RealSignalFixtureTests`; these add no coverage.

B. **Fix `TestFt8Encoder` to use `i3=1`** — the standard callsign type. This would require updating `PackType1` and re-verifying the round-trip, after which the tests can be un-skipped. This option redeems the encoder as a meaningful internal consistency tool.

C. **Leave as-is** — acceptable only if the skip count is tracked and the team acknowledges it as permanent technical debt.

**QA recommendation:** Option A. Five permanent skips create CI noise. The context in the class doc is already preserved; delete the test methods, retain the skip-reason documentation as a comment on the class if desired.

Note: `TestFt8Encoder` itself must be retained regardless, as the FR-026 performance test (`DecodeAsync_MultiSignal_CompletesWithinBudget`) uses it to synthesise multi-signal PCM.

---

## 3. Native Submodule Build Artifacts — Clean Up

**Location:** `native/ft8_lib/`  
**Severity:** Medium — causing dirty submodule status

The following compiled object files are present in the `native/ft8_lib/` working tree (left from the Linux/Windows builds):

```
native/ft8_lib/constants.o    ← Linux GCC output
native/ft8_lib/constants.obj  ← Windows MSVC output
native/ft8_lib/crc.o
native/ft8_lib/crc.obj
native/ft8_lib/decode.o
native/ft8_lib/decode.obj
```

These are the direct cause of the `m native/ft8_lib` dirty-submodule status in `git status`. They are not tracked by the submodule's own `.gitignore` (which does not cover `*.obj`).

**Fix options:**

1. **Delete them locally:** From the repository root, run:
   ```bash
   # From WSL or Git Bash
   rm native/ft8_lib/*.o native/ft8_lib/*.obj
   ```
   Then verify: `git status native/ft8_lib` should show `m` cleared.

2. **Add to the ft8_lib submodule's `.gitignore`** — not recommended since `native/ft8_lib` is a submodule pinned to an upstream commit; editing its `.gitignore` creates a local divergence.

Option 1 (delete locally) is the correct action.

---

## 4. OpenSpec Housekeeping

### 4.1 — Two open changes should be archived

| Change | Status | Recommended action |
|---|---|---|
| `p9-all-txt-decode-logging` | Implemented (`AllTxtWriter.cs` is production code; ALL.TXT logging is working) | Archive |
| `p10-decoder-ground-truth` | Implemented (real-signal fixture tests passing on all 3 platforms; `findings.md` updated with 66.6% recovery rate, which became the basis for the port decision) | Archive |

### 4.2 — p13 archive is partially staged

`openspec/changes/archive/2026-05-30-p13-cross-platform-decoder/` is untracked (`??` in git status). The archive directory has been created and populated (files moved from `openspec/changes/p13-cross-platform-decoder/`) but the additions have not been staged to git. The corresponding deletions (` D openspec/changes/p13-cross-platform-decoder/*`) are also unstaged.

**Action:** Stage both the deletions and the new archive directory, then include them in the final p13 merge commit.

---

## 5. Root-Level Document Clutter

The following historical documents have accumulated at the repository root during the extended development and debugging phases. They are not referenced by any source code or spec infrastructure.

**Recommendation: move to `docs/archive/` or delete entirely.**

| File | Origin | Why it can go |
|---|---|---|
| `DEFECT-cross-platform-decoder.md` | Pre-p13 defect report | Defect fixed in p13; defect details preserved in p13 QA review (archived) |
| `DEV-BRIEFING-p11-decoder-port.md` | p11 development session | p11 archived; history is in openspec archive |
| `DEV-BRIEFING-p11-decoder-port-r1.md` | p11 r1 session | Same |
| `DEV-REMEDIATION-p11-decoder-port.md` | p11 remediation | Same |
| `IMPLEMENTATION_PLAN.md` | Early project planning | Superseded by REQUIREMENTS.md + openspec artifacts |
| `QA-REVIEW-p7-p6.md` | p6/p7 QA review | p6 and p7 archived; review content is in the archive |
| `QA-REVIEW-p10-decoder-ground-truth.md` | p10 QA review | p10 to be archived (§4.1) |
| `QA-REVIEW-p11-decoder-port.md` | p11 QA review | p11 archived |
| `QA-REVIEW-p11-decoder-port-r2.md` | p11 r2 QA review | Same |
| `RECOVERY_PLAN.md` | Decoder recovery strategy | The recovery is complete (ft8_lib ported, G6 green); the document is historical |
| `TECHNICAL_SPEC.md` | Early technical spec | Superseded by REQUIREMENTS.md + openspec component specs |

The following documents should **remain** at the root:

| File | Reason to keep |
|---|---|
| `REQUIREMENTS.md` | Living requirements document; actively maintained |
| `README.md` | User-facing entry point |
| `TESTING_STRATEGY.md` | Active QA reference |
| `traceability-debt.md` | Active tool input for Gate G3 |

---

## 6. QA Backlog — Carry Forward

The following items were raised in the p13 QA review and logged in `openspec/qa-backlog.md`. They are not merge-blocking but must not be forgotten:

| ID | Item | File |
|---|---|---|
| **N1** | `Ft8LibInterop`: retry-after-failure produces a confusing exception (second call to `SetDllImportResolver` throws, burying the original `DllNotFoundException`) | `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` |
| **N2** | `Ft8LibInterop`: platform filename computed twice in `LoadAndVerify()` — extract a `GetPlatformLibFileName()` helper | Same |
| **N3** | `Ft8LibInterop`: 6 720-byte heap allocation on every decode cycle — switch to `ArrayPool<Ft8NativeResult>` | Same |

These are tracked in `openspec/qa-backlog.md` and require no action before merging p13.

---

## 7. Summary — Priority Order

| Priority | Item | Files affected |
|---|---|---|
| 🔴 **Must address in next change** | FR-017 decode start/stop control not implemented | `AppConfig.cs`, `WebApp.cs`, `Program.cs`, `index.html`, `main.js` |
| 🟠 **Before p13 merge** | Clean up native/ft8_lib `.o`/`.obj` artifacts | `native/ft8_lib/` (delete files) |
| 🟠 **Before p13 merge** | Complete p13 archive git staging | `openspec/changes/p13-*`, `openspec/changes/archive/2026-05-30-p13-*` |
| 🟡 **In next tidy-up change** | Archive p9 and p10 open changes | `openspec/changes/p9-*`, `openspec/changes/p10-*` |
| 🟡 **In next tidy-up change** | Fix stale `SymbolExtractor` references in XML docs | `FftCompute.cs`, `SpectrumAnalyser.cs` |
| 🟡 **In next tidy-up change** | Remove `// L-13 (DIAG)` and `// L-14 (DIAG)` labels | `Program.cs` |
| 🟡 **In next tidy-up change** | Remove or decide on 5 permanently-skipped tests | `Ft8DecoderFixtureTests.cs` |
| 🟢 **Low priority / optional** | Move root-level historical documents to `docs/archive/` | `DEFECT-*.md`, `DEV-BRIEFING-*.md`, `QA-REVIEW-*.md`, `RECOVERY_PLAN.md`, etc. |
| 🟢 **Tracked, not urgent** | QA backlog N1, N2, N3 (Ft8LibInterop housekeeping) | `Ft8LibInterop.cs` |
