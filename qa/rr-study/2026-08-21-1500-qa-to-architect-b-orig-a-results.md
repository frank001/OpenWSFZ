# QA → Architect: B-orig-A results (the waterfall-origin-convention arm)

**Author:** QA
**Date:** 2026-08-21 15:00 UTC (`date -u`, HK-017)
**Spec:** `qa/rr-study/2026-08-21-1412-architect-to-qa-origin-convention-finding-and-spec-b-orig-a.md`
**Script:** `qa/rr-study/r2-coherent-llr-instrument/b_orig_a_origin_convention.py`
**Artefacts:** `qa/rr-study/r2-coherent-llr-instrument/results/b_orig_a_report.json`,
`.../b_orig_a_run.log`
**Binary under test:** current merged `main` (`a420016`), shim 20260043, DLL SHA256
`1889408787...` — pin verified before running.

🔴 **ROW 1 FIRED — CONFIRMED**, per spec §6.4. This is the first GATED arm in this thread
(B-pos-A was diagnostic-only). **ROW 0g is unchanged: FIRED, task 4.3 stays VOID, Route B2 is
not dead.** No `src/`/`native/` edit, no rebuild, no push, no merge — HK-011 not engaged, as
specced (synth + the two existing diagnostic exports + a caller-side loop). This does **not**
itself amend design.md D1 — the 1201 spec §5 ruling is still the Captain's and still owed; ROW 1
firing only makes that ruling's text ready, per spec §5.

---

## 0. Preconditions (spec §6.3) — all three clear on the FIRST attempt

| ROW | check | result | bar | verdict |
|---|---|---|---|---|
| 0a | argmin resolvable | 2/100 trials undecidable (tied on grid or coherent), frac=0.020 | ≤0.10 | **PASS**, no remedy needed |
| 0b | truth axis measured, not asserted (HK-026) | 100/100 trials agree `t_true`↔`dt_cmd` within ±0.04s | ≥0.95 | **PASS** |
| 0c | optima interior | `mode(G)=+2`, `mode(C)=0`, both well inside swept ±4 quanta | not at ±4 | **PASS**, no widening needed |

**ROW 0b detail:** `t_true` is measured per trial from the rendered PCM's own smoothed-power
onset crossing (10% of peak, sub-sample-interpolated) on the *clean* (noiseless) render —
entirely independent of the decoder, the lattice, or any `ft8_lib` call (HK-026: the instrument
under test cannot bound its own blind spot). Observed bias: `t_true - dt_cmd` = +0.0036s
constant across all 100 trials (`max_abs_diff_s=0.0036`, `mean_abs_diff_s=0.0036`) — the expected
signature of `modulator.py`'s 10ms raised-cosine fade-in, not scored against, and 11× inside the
0.04s tolerance.

**ROW 0a detail:** operating SNR calibrated via Phase A's own ladder function (reused verbatim,
HK-018), landed at `snr_db=-19.0` (grid median `n_err`=8.0, inside the `[5,25]` target band). At
that point only 2/100 trials had a tied argmin on either path — well clear of the 10% bar, so the
pre-specified remedy (recalibrate + retry once) was never invoked.

---

## 1. HEADLINE — mode(G) and mode(C) against known ground truth

100 independent synthetic trials, distinct messages, independent noise draws, fixed seed
(`SEED=20260821`, `NOISE_SEED_BASE=21160821`, both recorded in the JSON). `dt_cmd` cycles through
8 sub-symbol offsets spanning a full 0.16s symbol (`BASE_DT_S=0.50` + `{0.00, 0.02, ..., 0.14}`).
Frequency fixed at the nominal lattice point throughout (`n=0`, `BASE_FREQ_HZ=1500.0`) — no
frequency residual injected, per spec §6.2 ("the derivation is purely about time"). For each
trial, both paths swept over the absolute call offset `q·0.08s` for `q` spanning `k_true ± 4`
quanta, `k_true = round(t_true / 0.08)`.

```
mode(G) = +2   frac_at_mode = 0.867   histogram {1: 13, 2: 85}      n_decidable = 98
mode(C) =  0   frac_at_mode = 0.918   histogram {-1: 8, 0: 90}      n_decidable = 98
```

**Both clear the pre-registered 0.80 bar. Both land exactly on the derivation's own predicted
lattice points (`mode(G)=+2`, `mode(C)=0`) — not fitted to them; the prediction was written
before this run.** The histograms are concentrated, not diffuse: 85/98 grid trials sit at exactly
`G=+2` (the remainder at `G=+1`, the immediate neighbour — none scattered further); 90/98
coherent trials sit at exactly `C=0` (remainder at `C=-1`).

Per spec §6.4's strict, ordered, mutually exclusive ROW table:

> **ROW 1 fires:** `mode(G)=+2` and `mode(C)=0` and both `frac_at_mode≥0.80`. **CONFIRMED.** The
> one-symbol displacement is the waterfall origin convention; the grid path is the displaced one;
> coherent is correct in raw-PCM terms. The displacement is no longer unexplained.

---

## 2. Secondary readout (spec §6.5, NOT gated) — sign-agreement curve

Per-bit hard-decision agreement between `coherent @ (k+2+m)` and `grid @ (k+2)` (fixed), as a
function of `m`. **Confounded by C1** (the exported LLRs are fused across `n_syms` 1/2/3) — spec
explicitly instructs: report the curve, draw no conclusion, do not let it influence the ROW.
Reported here for context only, consistent with that instruction:

| m | -6 | -5 | -4 | -3 | **-2** | -1 | 0 | +1 | +2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mean agreement | 0.571 | 0.584 | 0.598 | 0.731 | **0.908** | 0.716 | 0.606 | 0.580 | 0.571 |

Sharp, isolated peak at `m=-2` (0.908) against a neighbourhood otherwise in 0.57–0.73 — a third,
independent readout landing on the same displacement as the primary statistic and as B-pos-A's
own-best coherent cell (`m=-2`, 13:51Z). Not scored, not gating, consistent with everything else.

---

## 3. What this does and does not establish

- **Established, against known ground truth (not just internal consistency):** the grid path's
  own-best lattice cell sits at `k_true+2` quanta; the coherent path's sits at `k_true+0`. This is
  the asymmetric claim B-pos-A structurally could not make (real rows carry no true `dt`) — this
  arm closes that gap directly. The Architect's derivation (§1–§2 of the spec, a re-implementation
  check) is now also confirmed against the actual shipped binary's two diagnostic exports.
- **Established:** the displacement reproduces at exactly one FT8 symbol (2 quanta), matching
  every prior measurement in this thread (B-pos-A's `m=-2`, Phase A §2's plateau gap, Phase A
  §0.2's `+0.150s` vs `≈0.030s` synth anchors) — five independent readouts (four prior + this
  arm's own primary and secondary statistics) now agree on sign, magnitude and which path is
  displaced.
- **Not established, still:** B-pos-A's residual `d_global=-6.0` (CI95 `[-7,-4]`) — this arm says
  nothing about it; it stays with C1 (fusion) / C2 (frequency), per the spec's own scope note
  (§8). Nor does this arm touch the `wsjt_dt_correction_s: 0.55` link, which earns its own
  pre-registration per the spec.
- **Not re-litigated:** ROW 0g's own verdict, gate status, or Route B2's standing. Task 4.3 stays
  VOID; ROW 3 (Phase 1's own numbering) is not declared.
- **Prediction scoring:** per spec §7, scoring was SUSPENDED going in (blinding compromised by
  Phase A §0.2, which the Architect had already read before writing the spec's own non-scoring
  ~80%/~85% figures). This result is reported against that disclosure, not scored.

---

## 4. For the Architect

Per spec §6.4, ROW 1 firing is the row that reads: *"A narrow, D1-compatible origin correction
becomes the named Phase B fix; B3 stays HELD; Architect brings the Captain the §5 ruling with
numbers."* That is what fired, cleanly, on the first attempt, with every precondition clear and
every headline number landing exactly on the pre-registered lattice point. I make no ruling on
design.md D1 itself — spec §5's argument (that the fix is a unit conversion inside D1, not an
amendment to it) is the Architect's to bring to the Captain, and the 1201 §5 ruling remains the
Captain's either way.

---

**No `src/`/`native/` edit, no rebuild, no push, no merge.** Full per-trial data (all swept cells,
both paths, argmin/tie flags, full histograms, the secondary curve) is in `b_orig_a_report.json`.
