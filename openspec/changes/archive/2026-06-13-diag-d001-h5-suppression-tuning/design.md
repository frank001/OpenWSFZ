## Context

The soft SNR-scaled suppression ramp in `ft8_shim.c` has used the same constants since it was
introduced in shim 20260006 (fix-d001-revised Option B): `K_SOFT_SUPP_SNR_MIN_DB = −5.0f` and
`K_SOFT_SUPP_SNR_MAX_DB = +15.0f`. These values have survived four diagnostic iterations (H1–H4)
unchanged because each experiment was controlled to a single variable; tuning was explicitly
deferred to avoid confounding the diagnostic results.

H4 (shim 20260010) was accepted at 56.99% S7 overall. The per-family breakdown shows:

| Family | Condition | OW (H4 R1) | WSJT-X (H4 R1) | Gap |
|---|---|---|---|---|
| co_channel | exact overlap | 0/21 = 0.0% | 9/21 = 42.9% | structural floor |
| near_collision | ≥ 3 Hz separation | 27/30 = 90.0% | 30/30 = 100% | minor |
| time_freq | time-offset co-channel | 10/18 = 55.6% | 18/18 = 100% | **addressable** |
| capture | one signal 3–10 dB weaker | 16/24 = 66.7% | 16/24 = 66.7% | at parity |

The time_freq family is where spectrogram suppression is the sole active mechanism: pass 0
decodes the earlier signal; `suppress_candidate_tiles` attenuates its tiles; pass 1 finds the
later signal in the residual waterfall. At the test SNR of 0 dB, the current ramp applies only
25% suppression:

```
factor = 1 − clamp((0 − (−5)) / (15 − (−5)), 0, 1) = 1 − 0.25 = 0.75   [25% suppression]
```

H5 tests whether shifting the ramp window 10 dB toward lower SNRs produces enough additional
clearance to close (or reduce) the remaining gap on P9 (dt = 1.0 s) and P10 (dt = 2.0 s).

## Goals / Non-Goals

**Goals:**
- Change `K_SOFT_SUPP_SNR_MIN_DB` from `−5.0f` to `−15.0f`
- Change `K_SOFT_SUPP_SNR_MAX_DB` from `+15.0f` to `+5.0f`
- Bump `FT8_SHIM_VERSION` to `20260011` and update `ExpectedShimVersion` in `Ft8LibInterop.cs`
- Rebuild all three platform binaries and commit
- Run S7 R&R validation; accept or reject against gates (a) and (b)

**Non-Goals:**
- Addressing the co_channel parts (P0/P1/P2). These are a structural floor: co-timed
  co-frequency signals superimpose on the waterfall; no constant change can recover energy
  that was lost by addition before the spectrogram was built.
- Removing the GFSK helper functions retained in shim 20260010. They remain inert.
- Any change to `K_MIN_SCORE_PASS2`, `K_MAX_CANDIDATES_PASS2`, `K_LDPC_ITERATIONS_PASS2`,
  or `K_MAX_PASSES`. Single-variable change only.
- Any change to managed-layer logic beyond the version constant.
- Running the full S1–S8 suite. Only the S7 validation run is required.

## Decisions

### D1 — Shift the ramp window by −10 dB (−15/+5) rather than narrowing it

**Decision:** Both constants move by −10 dB. The ramp width (20 dB) is preserved; the
operating window shifts from [−5, +15] to [−15, +5].

**Resulting suppression at key SNR values:**

| SNR | Current factor (suppression) | H5 factor (suppression) |
|---|---|---|
| −15 dB or below | 1.0 (0%) | 1.0 (0%) — floor unchanged |
| −5 dB | 1.0 (0%) | 0.5 (50%) |
| 0 dB | 0.75 (25%) | 0.25 (75%) |
| +5 dB | 0.5 (50%) | 0.0 (100%) |
| +15 dB or above | 0.0 (100%) | 0.0 (100%) |

**Rationale:** A pure shift preserves the shape of the ramp — a continuous linear transition
with the same 20 dB span. The target of 75% suppression at 0 dB is principled: aggressive
enough to substantially clear a decoded signal's tile contribution, conservative enough to
preserve some energy for the borderline SNR band (−15 to −5 dB). The alternative (narrowing
to a 10 dB span [−10, 0]) would yield 50% suppression at 0 dB — less aggressive — or a
steeper ramp if centred the same way, which risks abrupt transitions that could clip partial
signals.

**Alternative considered — adjust only `K_SOFT_SUPP_SNR_MAX_DB` (lower ceiling to +5 dB):**
This would give 75% suppression at 0 dB (same result) but leave the minimum unchanged at
−5 dB. At −5 dB the current factor = 1.0 (no change); the alternative would give factor =
1.0 (no change) — identical behaviour below −5 dB. The difference appears in the −15 to −5 dB
band: only the full shift adds partial suppression in this range. The full shift is preferred
as it treats more borderline signals more aggressively and avoids an asymmetric ramp.

**Alternative considered — full-suppression at 0 dB (shift to [−20, 0]):**
This would give 100% suppression at 0 dB. Rejected — it makes 0 dB SNR a hard floor, which
risks complete loss of any tile energy for signals decoded at exactly the test SNR. The 75%
level leaves a margin that prevents full erasure of shared tile bins.

### D2 — Single trial; no grid search at this stage

**Decision:** Only the [−15, +5] configuration is tested in H5. If H5 is rejected and the
regression is attributable to over-suppression, a less-aggressive shift (e.g. [−10, +5]) may
be warranted as H5b.

**Rationale:** Grid searching over constant pairs within a single R&R run introduces multiple
comparisons and makes the acceptance gate ambiguous (which pair is being accepted?). One trial
per change, one clear verdict.

### D3 — Version bump to 20260011; interop assertion updated in the same commit

**Decision:** `FT8_SHIM_VERSION` advances from 20260010 to 20260011. The `ExpectedShimVersion`
constant in `Ft8LibInterop.cs` is updated in the same commit as the binary rebuild.

**Rationale:** Identical reasoning to H4 D3. The interop layer throws `InvalidOperationException`
at load time on version mismatch; splitting the bump across commits would break the build
between them.

## Risks / Trade-offs

**[Risk: over-suppression of borderline signals in the −5 to +5 dB SNR band]**
→ The shift adds partial suppression (50% at −5 dB, 75% at 0 dB) in a range where the current
ramp applies none. If a pass-0 decode is marginal and its tile bins are shared with a true
signal, the additional suppression may degrade the shared signal's pass-1 recovery. This is the
most likely mechanism for a gate (b) regression (per-part count decrease). Gate (b) will detect
this; a regression on near_collision or capture parts would confirm it.

**[Risk: insufficient suppression — 75% at 0 dB may still leave too much residual]**
→ The time_freq gap (P8 = 0/6, P9/P10 = 5/6) may require even more aggressive suppression
than 75%. If H5 passes gate (a) but does not improve P8/P9/P10, a narrower ramp (H5b) could
be considered.

**[Risk: seed variability obscuring a real improvement or regression]**
→ As demonstrated in H4 (R0 rejected, R1 accepted on the same binary), marginal scenarios are
sensitive to AWGN seed. Any H5 failure on parts with baseline count 3–5/6 should be examined
for seed-variability before concluding a genuine regression. If gate (a) fails by ≤ 2 decodes
and all regressing parts are marginal performers, a repeat run (H5 R1) is warranted before
reverting.

**[Risk: compiler warnings for GFSK helpers in the dead-code state]**
→ The GFSK helper functions (`build_gfsk_kernel`, `synth_ft8_gfsk_quad`,
`compute_quadrature_amplitude`) carry `__attribute__((unused))` annotations added in H4.
These suppress the `-Wunused-function` warning; no further action needed. Verify `dotnet build`
reports 0 warnings.

## Open Questions

None. The implementation path is fully determined.
