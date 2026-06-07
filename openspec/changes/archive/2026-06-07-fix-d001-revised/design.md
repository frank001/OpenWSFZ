## Context

D-001 (Medium) — OpenWSFZ recovers 46.2% of synthetic S7 co-channel signals vs WSJT-X at 77.4%. The previous fix attempt (`fix-d001-pcm-sic`) was reverted at `efc0920` after: (1) a P1 crash caused by a 703 KB stack allocation in a P/Invoke target overflowing the 1 MB .NET thread pool thread stack; (2) zero measurable real-signal improvement (−0.1 pp on 176 real-signal slots), because a clean CP-FSK synthesis model cannot coherently subtract a real HF signal with Doppler spread, multipath, and amplitude flutter.

The current baseline is the two-pass spectrogram-domain suppression introduced in p15 (`ft8_shim.c`, shim version `20260002`): pass 0 decodes the full waterfall; suppressed tiles are hard-zeroed at the decoded tone bin ±1 neighbours; pass 1 operates on the modified waterfall with a wider candidate net.

This change pursues four options in order, with explicit approval gates before the two higher-risk options.

## Goals / Non-Goals

**Goals:**
- Option A: Determine whether upgrading the upstream ft8_lib binary is the path of least resistance for closing D-001.
- Option B: Deliver a safe, incremental improvement to the spectrogram suppression pass without introducing PCM buffer risk or phase model assumptions.
- Option C (gated): Retry PCM-domain SIC with a realistic channel model — but only if a Python PoC demonstrates ≥ +5 pp improvement on synthetic S7 cases first.
- Option D (gated): Formally close or downgrade D-001 with Captain approval once A+B results are known.

**Non-Goals:**
- Closing the 3-stack equal-SNR case (P2: 0/9 for both WSJT-X and OpenWSFZ — theoretical limit).
- Any change to the managed API surface, UI, configuration, or layers above `OpenWSFZ.Ft8`.
- Reproducing WSJT-X's full multi-pass strategy — closing the gap substantially is the goal, not parity.

## Decisions

### Decision 1 — Option B: SNR-scaled tile attenuation, not hard-zero

**Chosen:** Replace the hard `= noise_floor` tile assignment with `tile *= attenuation_factor`, where `attenuation_factor` is a linear function of the decoded signal's SNR:

```c
/* SNR gate constants — tunable, but these are the initial values */
#define K_SOFT_SUPP_SNR_MIN_DB   (-5.0f)   /* below this: no suppression */
#define K_SOFT_SUPP_SNR_MAX_DB   (15.0f)   /* above this: full suppression (factor = 0) */

float norm = (snr_db - K_SOFT_SUPP_SNR_MIN_DB)
           / (K_SOFT_SUPP_SNR_MAX_DB - K_SOFT_SUPP_SNR_MIN_DB);
float factor = 1.0f - fmaxf(0.0f, fminf(1.0f, norm));
/* factor: 1.0 at SNR ≤ −5 dB (no suppression), 0.0 at SNR ≥ +15 dB (full suppression) */
waterfall_tile *= factor;
```

**Rationale:** The hard-zero approach is correct for a strong, cleanly decoded signal. However, the ±1 bin spread suppresses energy that may belong to an adjacent, weaker signal sharing that bin range. A borderline decode (SNR near the decoder floor) is more likely to have tile overlap with a true co-channel partner. Scaling the suppression by SNR reduces collateral damage to adjacent signals in proportion to the confidence in the decoded signal's tile locations.

**Alternative considered:** No attenuation (keep hard-zero). Rejected because it provides no improvement and the hard-zero artefact on adjacent signals is a known loss mechanism.

**Alternative considered:** Per-bin SNR weighting (different factor per symbol position). Rejected as over-engineering; the per-decode scalar is simpler to tune and validate.

### Decision 2 — Option C PoC gate: Python, synthetic S7 only, before any C code

**Chosen:** The Option C PoC SHALL be a Python script that:
1. Generates two synthetic co-channel FT8 signals of equal SNR (using the existing `qa/rr-study/synth/` synthesiser).
2. Sums them in PCM.
3. Implements amplitude-tracked CP-FSK subtraction: per-symbol amplitude from waterfall magnitude, linear frequency trajectory from all 79 symbols (not just Costas columns).
4. Calls the existing `libft8.dll` on the residual and counts additional recoveries.

A Python PoC on clean synthetic signals is the minimal possible test of the hypothesis. If it cannot move the synthetic S7 number — where there is no Doppler or multipath — there is no point building production C code.

**Gate criterion (QA position):** ≥ +5 pp improvement on at least 10 synthetic S7 trials before the Captain is asked to approve production implementation.

**Rationale for the gate:** The previous attempt spent significant effort building production-quality three-platform infrastructure before the core hypothesis was validated. A PoC costs days, not weeks; it either validates or kills the option cheaply.

### Decision 3 — Option C (if approved): heap allocation mandatory for any PCM buffer

**Lesson from the P1 crash:** Any buffer exceeding ~100 KB in a function called from a .NET thread pool thread SHALL use `malloc`/`free` or thread-local storage (`_Thread_local`), never automatic (stack) allocation. `FT8_EXPECTED_SAMPLES * sizeof(float) = 720 000 bytes` is categorically too large for the stack in this call context.

If Option C proceeds to production, the PCM residual buffer SHALL be:
```c
float* pcm_residual = (float*)malloc(FT8_EXPECTED_SAMPLES * sizeof(float));
if (!pcm_residual) { /* return empty result */ }
/* ... use ... */
free(pcm_residual);
```
No `OWSFZ_TLS_RESIDUAL` opt-in macro this time — heap is the only option.

### Decision 4 — Shim version increment on any native code change

**Chosen:** Option B changes `ft8_shim.c`; the shim version SHALL be incremented to `20260004` (skipping `20260003`, which is the reverted SIC version, to avoid any confusion). The `ft8lib-interop` spec and `ExpectedShimVersion` constant in `Ft8LibInterop.cs` are updated accordingly.

**Rationale:** The ABI self-test requirement (`ft8lib-interop` spec) is a safety net against mismatched binaries. Keeping it current is non-negotiable.

## Risks / Trade-offs

- **Option B: soft attenuation may reduce suppression effectiveness on strong signals** → Mitigated by the `K_SOFT_SUPP_SNR_MAX_DB = 15 dB` ceiling; any signal above 15 dB SNR is suppressed as aggressively as before. R&R S1–S6 must remain PASS after Option B.
- **Option B: tuning constants are empirical** → Initial values (`−5` to `+15` dB) are chosen based on the typical ft8 SNR range. If R&R shows a regression, the constants can be tightened. They are named C constants, not magic numbers.
- **Option C PoC may show ≥ +5 pp on synthetic but not on real signals** → The gate only requires the PoC to pass. If real-signal performance doesn't follow, D-001 remains open and Option D is invoked.
- **Option A upstream update may introduce unknown behaviour changes** → Any upstream update must pass the full test suite (314 tests) and the complete R&R study before merge.

## Open Questions

- **Option A:** Is kgoba/ft8_lib still actively maintained? If the repository is abandoned, the investigation can be time-boxed to 30 minutes and skipped.
- **Option B constants:** The initial `−5` to `+15` dB range is a starting point. The S7 R&R run will determine whether tightening (e.g., `0` to `+10` dB) yields better results.
- **Option C amplitude model:** Should per-symbol amplitude use waterfall magnitude at the decoded tone bin, or the maximum across all bins at that symbol time? The former is more specific; the latter is more robust to bin-edge effects.
