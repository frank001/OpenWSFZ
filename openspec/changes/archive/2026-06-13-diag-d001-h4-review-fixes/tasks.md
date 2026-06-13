## 1. F-H4-01 — Fix stale identity in GfskQuadratureSynthTests.cs

- [x] 1.1 Search the repo for any reference to `GfskQuadratureSynthTests` outside the test file itself (`grep -rn GfskQuadratureSynthTests .`); note any hits that would also need updating if the class is renamed
- [x] 1.2 Replace the class XML doc comment (lines 13–37) with a description that reflects the current purpose: a two-pass spectrogram-domain suppression smoke-test running against shim 20260010; remove all mention of "GFSK quadrature PCM-domain SIC", "H3b", "diag-d001-h3b-gfsk-sic", and "shim 20260009"
- [x] 1.3 Update the `[Fact]` `DisplayName` (line 40) — replace `"H3b/T2 gate: Ft8Decoder.DecodeAsync with synth-qso-01 returns expected results (shim 20260009 GFSK quadrature SIC)"` with a name that reflects the current gate, e.g. `"H4 smoke: Ft8Decoder.DecodeAsync with synth-qso-01 returns expected results (shim 20260010 spectrogram suppression)"`
- [x] 1.4 Update the assertion failure message (line 57) — replace the phrase `"the GFSK quadrature SIC path (shim 20260009) must produce at least one decoded message"` with wording that references the spectrogram suppression path and shim 20260010
- [x] 1.5 *(Optional, preferred)* Rename the class from `GfskQuadratureSynthTests` to `SpectrogramSuppressionSmokeTests` and rename the file accordingly; update any references found in task 1.1

## 2. F-H4-02 — Extend version history in Ft8Decoder.cs

- [x] 2.1 In `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, locate the version history comment (class XML doc, currently ending at line 28: `/// 20260006 — fix(D-002): SNR bandwidth constant…`)
- [x] 2.2 Append the following four entries immediately after the 20260006 line, matching the existing single-line `/// VVVVVVVV — <name>: <description>.` style:
  - `20260007 — diag-d001-three-pass-sic (H2): K_MAX_PASSES 2→3 diagnostic. REVERTED (S7 50.54%, −4.30 pp).`
  - `20260008 — diag-d001-pcm-sic (H3): CP-FSK/cosine PCM-domain SIC. REJECTED (S7 40.86%, −13.98 pp).`
  - `20260009 — diag-d001-h3b-gfsk-sic (H3b): GFSK quadrature PCM SIC; analytic amplitude estimator. REJECTED (S7 37.63%, −17.21 pp).`
  - `20260010 — diag-d001-h4-spectrogram-reinstate (H4): spectrogram suppression reinstated; H3b call site removed; GFSK helpers retained.`

## 3. Verification

- [x] 3.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings
- [x] 3.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm **327 passed**, 0 failures, 0 skips
- [x] 3.3 Confirm the updated test DisplayName appears correctly in test runner output (no truncation, no leftover "H3b" or "20260009" strings visible)
