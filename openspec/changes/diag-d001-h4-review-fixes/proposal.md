## Why

Two mandatory remediation items identified during the H4 code review (diag-d001-h4-spectrogram-reinstate)
must be resolved before the S7 validation run is authorised. Both are stale documentation defects
introduced when the H3b mechanism was removed: one in a test file whose displayed identity no
longer matches what it actually exercises, and one in a class-level version history comment that
was not extended to cover four successive shim versions.

## What Changes

- **`tests/OpenWSFZ.Ft8.Tests/GfskQuadratureSynthTests.cs`** — update or rename the class and
  correct all three stale H3b/20260009 narrative strings:
  - Class XML doc comment (currently describes GFSK quadrature PCM-domain SIC, H3b, shim 20260009)
  - `[Fact]` `DisplayName` (currently "H3b/T2 gate: … shim 20260009 GFSK quadrature SIC")
  - Assertion failure message (currently "the GFSK quadrature SIC path (shim 20260009) must…")
  - Preferred: rename the class from `GfskQuadratureSynthTests` to `SpectrogramSuppressionSmokeTests`;
    acceptable minimum: correct the three strings in place without renaming.

- **`src/OpenWSFZ.Ft8/Ft8Decoder.cs`** — append four missing entries to the native shim version
  history comment in the class XML doc:
  - 20260007 — diag-d001-three-pass-sic (H2): K_MAX_PASSES 2→3; REVERTED (−4.30 pp, S7 50.54%)
  - 20260008 — diag-d001-pcm-sic (H3): CP-FSK/cosine PCM SIC; REJECTED (−13.98 pp, S7 40.86%)
  - 20260009 — diag-d001-h3b-gfsk-sic (H3b): GFSK quadrature PCM SIC; REJECTED (−17.21 pp, S7 37.63%)
  - 20260010 — diag-d001-h4-spectrogram-reinstate (H4): spectrogram suppression reinstated; H3b call site removed

## Capabilities

### New Capabilities

*(none)*

### Modified Capabilities

*(none — both changes are documentation/comment corrections; no requirement or behaviour changes)*

## Impact

- `tests/OpenWSFZ.Ft8.Tests/GfskQuadratureSynthTests.cs` — comments, DisplayName, assertion message
  (and optionally: class name, filename)
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — XML doc comment only; no logic changes
- No binary rebuild; no spec changes; no API surface changes
