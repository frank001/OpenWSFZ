## Context

The `ft8_decode_all` function in `ft8_shim.c` currently executes a two-pass decode. Between
pass 0 and pass 1 it applies PCM-domain GFSK quadrature SIC (shim 20260009, H3b): it allocates
five heap buffers, synthesises each pass-0 decoded signal as a GFSK waveform, subtracts a
quadrature-estimated amplitude from a PCM copy, rebuilds the waterfall via a second `monitor_t`
(mon2), and runs pass 1 against the residual waterfall. This mechanism was introduced as a
controlled single-variable diagnostic experiment (H3b) and was rejected: S7 overall 37.63%
vs 54.84% spectrogram-suppression baseline (−17.21 pp).

The `suppress_candidate_tiles` function — the spectrogram-domain tile attenuator from the
baseline — is still present in the shim source, unchanged. The GFSK helper functions
(`build_gfsk_kernel`, `synth_ft8_gfsk_quad`, `compute_quadrature_amplitude`) introduced in H3b
are also still present. Neither set of functions was removed; only the call site changed.

`Ft8LibInterop.cs` hard-asserts `FT8_SHIM_VERSION == 20260009` at load time. This must be
updated to `20260010` in lockstep with the shim version bump.

## Goals / Non-Goals

**Goals:**
- Remove the H3b PCM-domain SIC call site and its supporting infrastructure from
  `ft8_decode_all`.
- Reinstate the `suppress_candidate_tiles` loop as the sole inter-pass mechanism.
- Advance `FT8_SHIM_VERSION` to 20260010 and update the corresponding assertion in
  `Ft8LibInterop.cs`.
- Rebuild and commit all three platform binaries.
- Leave the shim source in a state consistent with the `iterative-subtraction` spec (which
  was always written against the spectrogram-suppression behaviour; H3b was a spec violation).

**Non-Goals:**
- Removing the GFSK helper functions (`build_gfsk_kernel`, `synth_ft8_gfsk_quad`,
  `compute_quadrature_amplitude`). They are inert when not called; retaining them avoids a
  larger diff and preserves them for H3c.
- Removing the D-003 TLS additions (`tls_last_noise_floor_db`,
  `ft8_get_last_noise_floor_db()`). These remain needed for the D-003 soak test.
- Any change to the pass-configuration constants (`K_MIN_SCORE_PASS2`,
  `K_MAX_CANDIDATES_PASS2`, `K_LDPC_ITERATIONS_PASS2`, `K_SOFT_SUPP_SNR_MIN_DB`,
  `K_SOFT_SUPP_SNR_MAX_DB`). Single-variable change only.
- Any change to managed-layer logic beyond the version constant.
- Running the full S1–S8 suite. Only the S7 validation run is required for H4.

## Decisions

### D1 — Revert call site only; retain helpers

**Decision:** Remove only the H3b *call site* (the `if (pass == 1)` SIC block and its
associated variable declarations in `ft8_decode_all`). Retain the three GFSK helper functions.

**Rationale:** A future H3c experiment (hybrid: spectrogram suppression + PCM SIC) would
re-use these functions. Removing them now and re-adding them later doubles the churn. The
functions are `static` and unreferenced after the call site is removed; a compiler with
dead-code elimination will strip them from the binary.

**Alternative considered:** Full removal of all H3b code. Rejected — unnecessary scope for a
recovery change; increases diff size without benefit.

### D2 — No constant tuning in this change

**Decision:** `K_SOFT_SUPP_SNR_MIN_DB` and `K_SOFT_SUPP_SNR_MAX_DB` are left at their
baseline values (−5.0 / +15.0). No other pass-config constants change.

**Rationale:** H4 is a single-variable recovery experiment. Any constant tuning would
introduce a second variable, making the S7 result ambiguous — we would not know whether the
recovery is due to reinstating suppression or to the new constants. Tuning belongs in H5
(if H4 passes).

### D3 — Version bump to 20260010; update interop assertion in the same PR

**Decision:** `FT8_SHIM_VERSION` advances from 20260009 to 20260010. `Ft8LibInterop.cs`
`ExpectedShimVersion` is updated from 20260009 to 20260010 in the same commit as the binary
rebuild, so the repo is never in a state where the managed assertion and the committed binary
disagree.

**Rationale:** The interop layer throws `InvalidOperationException` if the versions differ.
Splitting the version bump across two commits would break the build between them.

## Risks / Trade-offs

**[Risk: compiler dead-code warning for unreferenced GFSK helpers]**
→ GCC/Clang will warn on `-Wunused-function` for `build_gfsk_kernel`, `synth_ft8_gfsk_quad`,
and `compute_quadrature_amplitude` after the call site is removed. Mitigation: add
`__attribute__((unused))` annotations or suppress with a cast to `(void)`. Verify `dotnet
build` (which invokes the native compile step for the local platform) reports 0 warnings.

**[Risk: mon2 / mon_cur references missed in the revert]**
→ If any `mon_cur` reference is left after the revert, the build fails (undeclared identifier).
The compiler is the safety net; the change cannot be silently wrong.

**[Risk: S7 does not recover to exactly 54.84%]**
→ The suppression path is byte-identical to the baseline shim. Minor variation is possible
due to OS scheduling noise in the K=3 run. A result within ±1 decode (50–52/93) would be
acceptable with justification; a result below 50/93 or with a per-part regression would
require investigation before merge.

## Open Questions

None. The implementation path is fully determined by the diff between the current shim and
`git show e4a3982:src/OpenWSFZ.Ft8/Native/ft8_shim.c`.
