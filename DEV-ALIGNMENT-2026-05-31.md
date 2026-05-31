# Developer Alignment Brief — 2026-05-31

**To:** Developer  
**From:** QA  
**Re:** Required changes before the next PR may be opened against `main`

This document is QA's response to `QA-ALIGNMENT-2026-05-31.md`. Work through items
top-to-bottom; they are ordered by urgency. Items marked **BLOCKING** must be resolved
before any further merge activity. The remainder must be resolved before the next PR is
opened.

---

## BLOCKING — `native/ft8_lib` submodule uncommitted patches

**Files affected inside submodule:**
- `common/monitor.c`
- `ft8/decode.c`

`git submodule status` reports `modified content` on `native/ft8_lib`. The diff reveals
the MSVC VLA compatibility patches are present only in the **local working tree** of the
submodule. They are not committed anywhere.

```diff
// common/monitor.c
-   kiss_fft_scalar timedata[me->nfft];
-   kiss_fft_cpx freqdata[me->nfft / 2 + 1];
+   kiss_fft_scalar timedata[8192];     /* MSVC VLA patch: nfft max = 8192 */
+   kiss_fft_cpx freqdata[4097];        /* MSVC VLA patch: nfft/2+1 max = 4097 */

// ft8/decode.c
-   float s2[n_tones];
+   float s2[512]; /* MSVC VLA patch: n_tones max = 512 (2^9) */
```

Without these patches the library does not compile under MSVC. Any developer who runs
`git submodule update`, or any CI runner that initialises submodules cleanly, will restore
the upstream `ft8_lib` and the Windows build will **break silently**.

**The Windows build currently depends on uncommitted, non-reproducible submodule state.**

### Required action

Choose one of the following, in order of preference:

1. **Fork `ft8_lib`** — create a fork under the project organisation, commit the three
   patch hunks there on a branch (e.g. `msvc-compat`), and update `.gitmodules` to point
   at the fork. This keeps upstream tracking possible.

2. **Commit directly in the submodule working tree** — `git -C native/ft8_lib checkout
   -b msvc-compat`, commit the two modified files, then update the superproject's
   submodule pointer to that commit.

3. **Apply patches at build time** — add a CMake step that patches the two files from a
   committed `.patch` file, leaving the submodule pointer at the upstream tag. More
   complex; only preferred if the fork management overhead is unacceptable.

Option 1 is strongly preferred. Do not open another PR until this is resolved.

---

## Before next PR — stale code comments

### 1. `tests/OpenWSFZ.Ft8.Tests/RealSignalFixtureTests.cs` — class XML doc (lines 24–28)

**Current (remove entirely):**
```csharp
/// <para><strong>This test is expected to be RED</strong> until the decoder is
/// fixed in a follow-on change (Phase 2A — port <c>ft8_lib</c>, or Phase 2B —
/// patch). A red result here is not a broken test — it is the measurement proving
/// the decoder cannot decode real off-air FT8 signals, as documented in
/// <c>RECOVERY_PLAN.md</c> and <c>findings.md</c>.</para>
```

**Replace with:**
```csharp
/// <para><strong>This test is expected to remain GREEN.</strong> The decoder is the
/// thin C# wrapper around the reference <c>ft8_lib</c> C library (MIT / kgoba),
/// compiled as a native shared library and loaded via <c>Ft8LibInterop.cs</c>. The
/// homegrown DSP that could not decode real signals has been replaced (Phase 2A —
/// <c>p12-ft8lib-port</c>). Any regression that makes this test red is a genuine
/// defect and will block merge via Gate G6 (NFR-016).</para>
```

### 2. `tests/OpenWSFZ.Ft8.Tests/RealSignalFixtureTests.cs` — inline comment (line 76)

**Current (remove):**
```csharp
// This test is expected RED until the decoder is fixed (RECOVERY_PLAN.md §5).
```

**Replace with:**
```csharp
// G6 gate — this assertion must remain GREEN (NFR-016).
```

---

## Before next PR — stale decision-gate logic in `ReplayHarnessTests.cs`

### Lines 172–180 — findings.md body

The current two-branch conditional (`0% → Phase 2A`, `else → Phase 2B`) implies there is
still a homegrown DSP to patch. Replace with a three-branch switch:

```csharp
sb.AppendLine(recoveryRate switch
{
    0.0 => "Recovery rate is **0.0%** — no signals decoded.\n\n" +
           "**Action required:** ft8_lib interop is broken. Investigate `Ft8LibInterop.cs`, " +
           "confirm the native shared library is present in the output directory, and verify " +
           "that `LoadAndVerify()` succeeds without exception.",

    < 55.0 => $"Recovery rate is **{recoveryRate:F1}%** — below the established baseline (~66.6%).\n\n" +
              "**Action required:** ft8_lib wrapper regression or parameter change. " +
              "Compare decoder parameters against the p12 baseline. Review recent changes to " +
              "`Ft8LibInterop.cs` and `Ft8Decoder.cs`. G6 gate may still be green if the committed " +
              "fixture answer keys are all recovered — check `RealSignalFixtureTests` results.",

    _ => $"Recovery rate is **{recoveryRate:F1}%** — within normal operating range.\n\n" +
         "**Status: nominal.** The ~33% miss rate relative to WSJT-X is a known, accepted " +
         "limitation of ft8_lib not implementing iterative subtraction (second-pass decoder). " +
         "This is a product-level decision deferred to a future change. No action required."
});
```

The 55% threshold is QA's proposal. Confirm it is acceptable before applying.

### Lines 205–207 — console echo

```csharp
_out.WriteLine(recoveryRate switch
{
    0.0    => "DECISION: interop failure — 0% recovery, check Ft8LibInterop.cs",
    < 55.0 => $"DECISION: regression — {recoveryRate:F1}% is below ~66.6% baseline",
    _      => $"STATUS: nominal — {recoveryRate:F1}% (iterative subtraction gap is accepted)"
});
```

---

## Before next PR — commit `findings.md` to `main`

**File:** `openspec/changes/p10-decoder-ground-truth/findings.md`  
**Current state:** untracked on `main` (generated locally by the replay harness).

The per-cycle data and aggregate figures are accurate and approved for commit. However,
the **Decision-gate outcome** section at the bottom of the file was machine-generated
by the old two-branch harness logic and is now misleading. Replace it before committing:

**Current (remove):**
```markdown
## Decision-gate outcome

Recovery rate is **66.6%** — partial recovery detected.

**Decision: Phase 2B — Patch against the oracle.** Re-evaluate the patch strategy per `RECOVERY_PLAN.md` §8.
```

**Replace with:**
```markdown
## Decision-gate outcome

Recovery rate is **66.6%** — within normal operating range.

**Status: nominal.** The ~33.4% miss rate relative to WSJT-X reflects ft8_lib not
implementing iterative subtraction (second-pass decoder). This is an accepted limitation
of the current ft8_lib-based architecture. Closing this gap is an open product decision;
no corrective action is required at this measurement.
```

Commit the file to `main` once the footer is updated.

---

## Before next PR — delete orphaned `feat/p11-decoder-port` branch

The Bluestein/mixed-radix work on `feat/p11-decoder-port` is superseded by p12 and has
never been pushed to `origin`. QA approves deletion.

```bash
git branch -D feat/p11-decoder-port
```

The QA review documents that exist only on that branch (`QA-REVIEW-p11-*`,
`DEV-BRIEFING-p11-*`, `DEV-REMEDIATION-p11-*`) do not need to be preserved on `main`.

---

## Before next PR — fix broken cross-reference in `QA-ALIGNMENT-2026-05-31.md`

**§2, last sentence of "What G6 does NOT measure":**

> *Whether to close this gap is an open product decision (see §6).*

§6 of that document covers FR-030 (logging hot-reload), not iterative subtraction.
The cross-reference is incorrect.

**Replace with:**

> *Whether to close this gap is an open product decision; no change has been opened for it.*

---

## For information — performance gap is not a defect

The 66.6% recovery rate versus WSJT-X's 887-decode corpus is not caused by a port
defect. The per-cycle data shows that virtually everything ft8_lib produces matches a
WSJT-X decode; the shortfall is entirely in signals we do not attempt. This is the
structural signature of missing iterative subtraction. The false-positive rate (24 / 615
decoded = 3.9%) is low and acceptable.

No corrective action is required. Whether to invest in closing the gap is a product
decision to be taken by the Captain.

---

## Product decision — iterative signal subtraction is mandatory

The Captain has confirmed: iterative signal subtraction **must be implemented** (Option A).
This is not deferred. Full details, architectural paths, and acceptance criteria are in:

> `DEV-BRIEFING-iterative-subtraction.md`

**Suggested change:** `p15-iterative-subtraction`  
**Dependency:** B1 (submodule fork) must be resolved before implementation begins.

**Sequencing impact:** FR-030 (logging hot-reload) moves to `p16`. Iterative subtraction
is a SHALL compliance issue and takes priority.

---

## For information — QA backlog items N1/N2/N3

Items N1 (retry exception confusion), N2 (duplicate platform filename), and N3 (per-cycle
heap allocation) in `openspec/qa-backlog.md` remain open. QA recommends bundling them
into a single housekeeping change (`p17-interop-housekeeping`) after p15 and p16 are
complete. They are not merge-blocking today.

---

## Checklist summary

| # | Action | Status |
|---|---|---|
| B1 | Commit MSVC VLA patches to submodule (fork or local branch) | **BLOCKING** |
| C1 | Replace stale class doc comment in `RealSignalFixtureTests.cs` | Before next PR |
| C2 | Replace stale inline comment in `RealSignalFixtureTests.cs` | Before next PR |
| C3 | Replace three-branch decision-gate logic in `ReplayHarnessTests.cs` | Before next PR |
| C4 | Update findings.md footer and commit to `main` | Before next PR |
| C5 | Delete `feat/p11-decoder-port` branch | Before next PR |
| C6 | Fix broken §6 cross-reference in `QA-ALIGNMENT-2026-05-31.md` | Before next PR |
| P1 | Open `p15-iterative-subtraction` change after B1–C6 complete | Next change |

---

*QA assessment dated: 2026-05-31*  
*Next action: Developer works through B1 through C6; QA to review once complete.*
