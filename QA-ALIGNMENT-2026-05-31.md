# QA Alignment Brief — 2026-05-31

**To:** QA
**From:** Developer / Architect
**Re:** Current system state, stale artefacts, and next QA actions

This document exists because the code, the test comments, the findings artefact, and the
open requirement backlog have drifted relative to each other since QA's last full review
(p14-decode-start-stop). Work through this brief top-to-bottom before picking up any new
task.

---

## 1. Decoder state — what actually shipped

| Phase | Change | Status |
|---|---|---|
| Phase 1 — oracle | p10-decoder-ground-truth | ✅ Archived |
| Phase 2B attempt (patch) | p11-decoder-port (Bluestein DFT) | ❌ Abandoned — never merged |
| Phase 2A — ft8_lib port | p12-ft8lib-port | ✅ Archived & **merged to `main`** |
| Phase 2A — cross-platform | p13-cross-platform-decoder | ✅ Archived & **merged to `main`** |
| Decode start/stop | p14-decode-start-stop | ✅ Archived & **merged to `main`** |

**Bottom line:** the homegrown DSP is gone. The decoder on `main` is a thin C# wrapper
around the reference `ft8_lib` (MIT / kgoba) C library, compiled as a native shared
library and loaded via `Ft8LibInterop.cs`. All `p12`/`p13` artefacts are archived.

---

## 2. G6 gate — current state

**G6 is GREEN.**

```
dotnet test -c Release --filter "RealSignal"
→  Passed: 3, Failed: 0, Skipped: 0
```

The three committed WAV fixtures (260528_235745, 260529_000030, 260529_000200) decode
correctly against their answer-key subsets. CI enforces this on every push and PR.

### What G6 measures — and what it does NOT measure

G6 asserts that **the strongest signals in each committed fixture** are recovered.
Answer-key subsets are SNR ≥ +6 dB signals only; the threshold was set low enough to be
meaningful but high enough to be reliable across decoder improvements.

G6 passing does **not** mean 100% recovery of all WSJT-X decodes. The 42-WAV corpus
measurement (replay harness) shows:

| Metric | Value |
|---|---|
| WSJT-X total decodes (42 cycles) | 887 |
| ft8_lib matched | 591 |
| False positives | 24 |
| **Overall recovery rate** | **66.6%** |

The 33% miss rate is real. It is consistent with ft8_lib not implementing iterative
subtraction (the WSJT-X second-pass decoder that strips decoded signals and re-decodes the
residual for weaker co-channel stations). This is a known limitation, not a defect in the
port. Whether to close this gap is an open product decision; no change has been opened for it.

---

## 3. Stale artefacts QA must fix

### 3.1 `RealSignalFixtureTests.cs` — class doc comment

**Location:** `tests/OpenWSFZ.Ft8.Tests/RealSignalFixtureTests.cs`, lines 24–28

**Current (wrong):**
```csharp
/// <para><strong>This test is expected to be RED</strong> until the decoder is
/// fixed in a follow-on change (Phase 2A — port <c>ft8_lib</c>, or Phase 2B —
/// patch). A red result here is not a broken test — it is the measurement proving
/// the decoder cannot decode real off-air FT8 signals, as documented in
/// <c>RECOVERY_PLAN.md</c> and <c>findings.md</c>.</para>
```

**Required:** Replace with a description of the GREEN steady-state. This test is now the
live correctness gate; it is expected to remain green. The "expected RED" framing was
correct during p10 but is now actively misleading for anyone reading the file.

### 3.2 `RealSignalFixtureTests.cs` — inline comment

**Location:** line 76

**Current (wrong):**
```csharp
// This test is expected RED until the decoder is fixed (RECOVERY_PLAN.md §5).
```

**Required:** Remove or replace with "G6 gate — must remain GREEN (NFR-016)."

### 3.3 `ReplayHarnessTests.cs` — decision-gate text

**Location:** lines 172–180, 205–207

The harness still emits:

> **Decision: Phase 2B — Patch against the oracle.** Re-evaluate the patch strategy
> per `RECOVERY_PLAN.md` §8.

This was correct when it was written (pre-p12). With ft8_lib ported, any non-zero
recovery now triggers this label, which implies patching the homegrown DSP — a path that
no longer exists. The text is confusing and should be updated to reflect the new baseline:

- **0%** → ft8_lib interop broken — investigate `Ft8LibInterop.cs`
- **> 0% and < expected threshold** → ft8_lib wrapper regression or parameter change
- **≥ current baseline (~66%)** → normal; iterative subtraction not implemented

QA owns the wording; Developer will apply once QA provides the replacement copy.

### 3.4 `openspec/changes/p10-decoder-ground-truth/findings.md` — untracked on `main`

The replay harness writes this file to the working tree when run locally. The current file
(dated 2026-05-30 23:39:36 UTC, 66.6% rate) is untracked on `main`. Its "Phase 2B —
Patch" label is technically correct — further improvement is possible — but:

1. It was generated post-ft8_lib-port, so "Phase 2B" here means "tune the wrapper",
   not "patch the homegrown DSP". The ambiguity should be resolved in the file header.
2. The file should be committed to `main` so the last-known measurement is versioned.

**Action:** QA to confirm the file content is accurate and approve commit; Developer to
commit it.

---

## 4. Orphaned branch — p11-decoder-port

`feat/p11-decoder-port` exists locally (never pushed to `origin`). It contains:

- Bluestein 1920-pt DFT spectrogram
- Mixed-radix callsign decode
- QA review artefacts (two rounds)
- Findings: G6 still RED at the time; root cause identified as iterative subtraction

**Status:** Superseded by p12 (ft8_lib port). The Bluestein/mixed-radix work is
**not** on `main` and is not needed — ft8_lib handles spectrogram and callsign decode
internally.

**Action:** Delete the local branch. The QA review docs (`QA-REVIEW-p11-decoder-port*.md`,
`DEV-BRIEFING-p11-decoder-port*.md`, `DEV-REMEDIATION-p11-decoder-port.md`) are at the
repo root on that branch only — they do not need to be preserved on `main`.

---

## 5. `native/ft8_lib` — submodule modified content

`git status` reports `modified: native/ft8_lib (modified content)`. This means local
changes exist inside the submodule working tree that are not committed to the submodule.

**Action:** QA to flag this to Developer to inspect and either commit the submodule change
(if intentional) or restore clean state (`git submodule update`).

---

## 6. Open requirement — FR-030 (logging hot-reload)

FR-030 was formalised in REQUIREMENTS.md v1.11 (2026-05-31). It requires all logging
configuration changes (console level, file sink on/off, file level, directory, rotation,
max files) to take effect immediately on settings save — no restart.

**Current implementation gap (known):** The console log level already hot-reloads via
`IOptionsMonitor<AppConfig>`. The file sink, directory, rotation schedule, and max-files
do **not** hot-reload; the daemon must be restarted for those changes to take effect.

**Status:** No OpenSpec change has been opened for FR-030. This is the next planned change.

**QA action:** Before the Developer opens the change, QA should produce an acceptance
criteria list covering each of the five sub-requirements in FR-030 and the expected
observable behaviour for each. This prevents the same partial-implementation trap that
produced FR-030 in the first place (the restart-required defect went undetected because
there was no explicit test for hot-reload).

---

## 7. QA backlog — standing items

These items from `openspec/qa-backlog.md` remain open. None are merge-blocking today but
QA should schedule them.

| Item | Severity | Location |
|---|---|---|
| N1 — `LoadAndVerify()` retry buries original exception | Low | `Ft8LibInterop.cs` |
| N2 — platform filename computed twice in `LoadAndVerify()` | Cosmetic | `Ft8LibInterop.cs` |
| N3 — 6 720-byte heap alloc on every decode cycle | Low | `Ft8LibInterop.cs` — `DecodeAll()` |

---

## 8. Summary of actions required from QA

| # | Action | Urgency |
|---|---|---|
| QA-1 | Rewrite stale doc comment in `RealSignalFixtureTests.cs` (§3.1, §3.2) | Before next PR |
| QA-2 | Provide replacement decision-gate text for `ReplayHarnessTests.cs` (§3.3) | Before next PR |
| QA-3 | Confirm findings.md content and approve commit to `main` (§3.4) | Before next PR |
| QA-4 | Confirm orphaned p11 branch deletion is acceptable (§4) | Before next PR |
| QA-5 | Flag native/ft8_lib submodule modified-content to Developer for resolution (§5) | Before next PR |
| QA-6 | Write FR-030 acceptance criteria list before change is opened (§6) | High — blocks p15 |
| QA-7 | Schedule N1/N2/N3 from backlog into a housekeeping change (§7) | Low |

---

*Document authored: 2026-05-31*
*Next action: QA reviews this document and responds to items QA-1 through QA-7.*
