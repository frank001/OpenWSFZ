## Context

The R&R study (2026-06-06, SHA `46d7f6a`) exposed a linearity defect in OpenWSFZ's SNR
estimator: bias slope = 0.512 (gate: ≤ 0.1). The root cause is the R6 fallback
weak-signal post-correction added to `ft8_shim.c` during the p12 port:

```c
#define SNR_WEAK_SIGNAL_THRESHOLD   (-10.0f)
#define SNR_WEAK_SIGNAL_CORRECTION  ( 8.0f)
…
if (snr < SNR_WEAK_SIGNAL_THRESHOLD) snr -= SNR_WEAK_SIGNAL_CORRECTION;
```

The correction was designed to compensate for an ~8 dB overestimation at WSJT-X SNR
≤ −20 dB seen in the UAT-01 corpus (real off-air signals). However the R&R study uses
**synthesised** signals with precisely calibrated SNR in the 2500 Hz reference bandwidth.
On synthetic signals the raw max-over-8 estimator delivers a flat ~+1 dB bias across
the entire decoded range. The −8 dB correction is therefore overcorrecting, and because
it is triggered by the **estimated** (not true) SNR, it fires for synthetic signals in
the −18 to −12 dB range — creating an 8 dB discontinuity at the −10 dB threshold that
linear regression reads as a large positive slope.

**Empirical evidence from S1_matched.csv (OpenWSFZ column, matched rows only):**

| true_snr | reported_snr | bias |
|----------|-------------|------|
| −18 dB | −25 dB | −7 dB ← correction fires (est. ≈ −17 < −10) |
| −15 dB | −22 dB | −7 dB ← correction fires (est. ≈ −14 < −10) |
| −12 dB | −19 dB | −7 dB ← correction fires (est. ≈ −11 < −10) |
| −9 dB  | −8 dB  | +1 dB ← no correction (est. ≈ −8 > −10) |
| −6 dB  | −5 dB  | +1 dB |
| 0 dB   | +1 dB  | +1 dB |
| +3 dB  | +5 dB  | +2 dB |

Without the correction: bias ≈ +1 dB flat → slope ≈ 0, mean bias ≈ +1.1 dB ✓

## Goals / Non-Goals

**Goals:**
- Remove the R6 fallback correction from `ft8_shim.c`
- Bump `FT8_SHIM_VERSION` to force an ABI check that detects old binaries
- Rebuild all three platform binaries from the updated shim source
- Update all documentation and managed constants that reference the correction
- Close R&R-001 (GitHub issue #30)

**Non-Goals:**
- Revisiting the single-bin estimator approach proposed in the R6 design doc
  (data shows it is not needed — the max-over-8 estimator is already flat without the correction)
- Changing the noise-floor histogram algorithm
- Changing the bandwidth correction constant (−26.0 dB; see design rationale below)
- Re-running the full UAT-01 SNR analysis (that corpus used real off-air signals;
  the R&R study is the authoritative quality gate going forward)

## Decisions

### Decision 1 — Remove the correction entirely, not tune the threshold

**Chosen:** Delete the three lines (two `#define`s and the conditional) completely.

**Alternative considered:** Lower the threshold (e.g., −20 dB) so it only fires at
extreme SNR levels where UAT-01 showed +8 dB overestimation. Rejected because:
- The R&R synthetic data shows the raw estimator is already flat; the correction adds
  no value for synthesised signals
- The UAT-01 overestimation at ≤ −20 dB was measured with WSJT-X as the reference;
  the R&R study compares against the synthesised true SNR, which is the canonical gate
- Adding any threshold-triggered correction risks introducing a new slope discontinuity

### Decision 2 — Bandwidth correction stays at −26.0 dB

The S1 data shows +1 dB bias (not −3 dB), confirming the bin width is 6.25 Hz (not
3.125 Hz as would be the case if the waterfall used `num_bins × freq_osr` as the total
frequency count). The monitor layout places `freq_sub` and `freq_offset` in separate
dimensions; `row[f]` indexes the 6.25 Hz bin dimension directly.

10 × log₁₀(2500 / 6.25) = 10 × log₁₀(400) ≈ 26.02 dB → −26.0 dB is correct.

### Decision 3 — Bump FT8_SHIM_VERSION to 20260002

The existing ABI sentinel mechanism provides an automatic safety net: any deployment
that still carries the old binary will throw `InvalidOperationException` on first decode
rather than silently reporting wrong SNR values.

Old: `20260001` (p15 — iterative subtraction, ft8_get_last_pass_counts added)  
New: `20260002` (this change — R6 weak-signal correction removed)

### Decision 4 — Rebuild all three platform binaries in this branch

The Windows binary will be rebuilt locally using the MSVC build procedure in `BUILD.md`.
The Linux and macOS binaries are produced via the existing GitHub Actions `workflow_dispatch`
workflow (see `ci/`) and committed as binary artifacts — the same process used for p12/p15.

## Risks / Trade-offs

**[Risk] UAT-01 weak-signal overestimation returns** → The UAT-01 corpus at ≤ −20 dB
WSJT-X SNR may again show ~+8 dB mean bias without the correction. However: (a) the
R&R gate is the authoritative acceptance criterion, and (b) signals at ≤ −20 dB are
rarely decoded at all — they are below the practical sensitivity of ft8_lib. Mitigation:
note the regression in the commit message; re-evaluate if a future R&R run produces data
at that SNR range.

**[Risk] +1 to +2 dB mean bias approaches the ±2 dB gate** → The observed mean bias
without the correction is approximately +1.1 dB (well inside the gate). At +3 dB true
SNR the bias was +2 dB; if the distribution of decoded signals shifts toward higher SNR
in a future run the mean could approach the gate. Mitigation: the gate is ±2 dB; current
observed values are at most +2 dB — passing. No action needed now.

**[Risk] Old binaries deployed alongside new managed code** → The ABI version bump from
20260001 → 20260002 ensures the managed loader throws `InvalidOperationException` rather
than silently using the old correction. No silent degradation path.

## Migration Plan

1. Edit `ft8_shim.c` and `ft8_shim.h` (source-controlled)
2. Rebuild Windows binary locally → commit `win-x64/libft8.dll`
3. Trigger macOS + Linux rebuild via `workflow_dispatch` → commit binaries
4. Update `ExpectedShimVersion` in `Ft8LibInterop.cs`
5. Update `libft8.version.txt`, `BUILD.md`, `Ft8NativeResult.cs` doc-comment
6. `dotnet test -c Release` — all tests green
7. PR → main; close issue #30
