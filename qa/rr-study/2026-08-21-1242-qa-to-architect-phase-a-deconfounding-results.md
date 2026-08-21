# QA → Architect: Phase A de-confounding results (ROW 0g-2)

**Author:** QA
**Date:** 2026-08-21 12:42 UTC (`date -u`, HK-017)
**Spec:** `qa/rr-study/2026-08-21-1201-architect-to-qa-b2-row0g-native-fix-triage-and-phase-a-
deconfounding.md`
**Script:** `qa/rr-study/r2-coherent-llr-instrument/phase_a_deconfounding.py`
**Artefacts:** `qa/rr-study/r2-coherent-llr-instrument/results/phase_a_report.json`,
`.../phase_a_run.log`
**Binary under test:** current merged `main` (`a420016`), shim 20260043, DLL SHA256
`1889408787...` — pin verified before every trial.

🔴 **DIAGNOSTIC ONLY, per spec Sec.6.** No ROW defined, no PASS/FAIL, no `f_net`. ROW 0g is
unchanged: FIRED, gate VOID, Route B2 not dead, ROW 3 not declared. This report names a
mechanism candidate; it does not re-read or amend the gate.

---

## 0. Two corrections made mid-run, recorded per HK-018/HK-022 (not silently absorbed)

1. **Floor degeneracy in A1.** An initial noiseless A1 run read `median(n_err)=0` for BOTH
   paths across the ENTIRE swept `delta_f` range — the identical degeneracy 0g-1's own
   noiseless primary run hit (`row0g_report.json`: `"floor_degenerate": true`). Ported 0g-1's
   own remedy verbatim: calibrated an operating `snr_db` (ladder search) at which the grid
   path's own median lands in `[5, 25]` (landed at **-19.0 dB**, grid median = 8.00), and ran
   every Phase A sweep at that one fixed operating point.
2. **Naive `delta_t=0.0` is not a meaningful shared reference.** A2/A3 need one SHARED call
   offset for both paths (that is the confound under test — 0g-2's real methodology uses one
   un-swept anchor for both). An initial run anchored at `delta_t=0.0` read grid=70.5 (near the
   ~87 pure-noise ceiling) while coherent read 6.0 at the *same* point — i.e. it had landed on
   the wrong side of the known encoder/extractor convention gap (design.md D3, "~+0.1-0.2s").
   Replaced with a principled shared anchor: the offset that minimises the **grid** path's own
   median over the 49-point sweep (matching design.md D1 — coherent forms at grid's *existing*
   position, never its own search). This landed at **time_offset_s = 0.150s** — inside D3's
   independently-reasoned 0.1-0.2s band, an unplanned cross-check of that estimate.

Both corrections are in the script's own docstrings/comments, not just this report.

---

## 1. A1 — frequency residual (timing neutralised, 49-point per-path sweep retained)

| `delta_f` (Hz) | median n_err grid | median n_err coh | `d_clean` |
|---:|---:|---:|---:|
| -1.5625 | 17.5 | 28.5 | -11.5 |
| -0.5208 | 9.0 | 9.5 | +0.5 |
| **0.0000** | **8.0** | **6.0** | **+3.0** |
| +0.5208 | 8.5 | 8.0 | +2.0 |
| +1.5625 | 16.0 | 31.0 | -15.5 |

Full 13-point table in the JSON. **Confirmed:** near the anchor both paths are comparable
(coherent slightly ahead), but coherent degrades faster once `|delta_f|` approaches the lattice
edge — at the worst swept point coherent gained **+22.5** bit-errors vs grid's **+9.5** off the
`delta_f≈0` baseline. This matches the Architect's blind prediction (~80% confidence, spec
Sec.7) and is consistent with C2 (coherent integration loses more to frequency residual over a
longer window). It is a real but **modest** effect at this SNR — nowhere near 0g-2's magnitude
on its own.

## 2. A2 — timing residual (single shared, un-swept call offset)

Full 25-point sweep in the JSON; shape only is meaningful (D3 — axis zero is uncalibrated). The
striking result is **structural, not gradual**: `median(n_err_grid)` and `median(n_err_coh)`
each sit on a flat plateau, and **the two paths' plateaus are different, and displaced from each
other by roughly 0.12-0.15s** — not a smooth joint degradation curve.

- Grid reads its best (8.0) on `time_offset_s ∈ [0.12, 0.19]` roughly (`delta_t ∈ [-0.03,+0.04]`
  relative to the anchor) — a wide, forgiving plateau, consistent with the Architect's own
  §1.2 reasoning about a single-symbol FFT bin degrading gracefully.
- Coherent reads its best (6.0) at `time_offset_s ≈ 0.030s` (`delta_t = -0.12`) — a **different**
  position, one plateau-width away from grid's optimum. At grid's own plateau, coherent reads
  ~69-70 (near-ceiling collapse).

This is a genuine, code-grounded finding, not conjecture: **the position that best serves the
single-symbol grid detector is not the position that best serves the multi-symbol coherent
window**, and the gap between them (~0.12-0.15s, ~75-95% of a 0.16s symbol) is large enough that
forcing coherent onto grid's position (exactly what design.md D1 mandates) lands it off its own
plateau entirely.

## 3. A3 — joint, at realistic residuals — the control, not the injected residual, is the story

| Condition | median grid | median coh | `d_clean` |
|---|---:|---:|---:|
| **CONTROL** (`delta_f=0, delta_t=0`, i.e. the shared D1 anchor alone) | 8.0 | 69.0 | **-61.0** |
| worst *injected*-residual condition (`delta_f=-0.745, delta_t=+0.07s`) | 44.0 | 70.5 | -30.0 |
| `delta_t=-0.15s` conditions | 70.0 | 11-13 | **+56 to +59** (sign reversed) |

**0g-2's real measurement: `d_real = -67.0`, CI95 `[-71.0, -65.0]`.**

The CONTROL — the shared D1 anchor with **zero** injected frequency or timing residual beyond
the architectural fact of sharing grid's own position — already reads `d_clean = -61.0`,
approaching 0g-2's CI from outside by only ~4-6 bits. **Every explicitly-injected `delta_f`/
`delta_t` combination tested made the contrast *less* negative than the control, not more** —
injecting `delta_t` moves the shared call position off grid's plateau, which degrades grid about
as much as it degrades coherent (shrinking `d_clean` toward zero), or at `delta_t=-0.15s` moves
the shared position toward *coherent's* plateau instead and **reverses the sign** entirely.

**Reading this against the spec's own pre-stated decision rule (Sec.3):** the joint sweep does
not reach `|d|≈67` from the *externally-motivated* H1a/D2/D3 residual magnitudes tested — but it
gets to ~90% of that magnitude (`-61` vs `-67`) from the **D1 architectural constraint alone**
(shared, un-refined position), which is not one of A3's four swept conditions at all, it is the
control. That was not anticipated in the spec's own framing of A3 (which expected the *injected*
residuals to do the work) and is worth flagging explicitly rather than folded into either of the
spec's two pre-written branches.

---

## 4. What this does and does not establish

- **Established, code-grounded:** grid and coherent have measurably different position optima
  even at `delta_f=0` (no frequency residual at all) — a variant of C3 broader than the spec's
  own framing (which treated C3 as "timing residual *given* a shared anchor," not "the shared
  anchor itself is structurally wrong for one of the two paths"). Combined with C1/C2 (already
  present in `ft8_coherent_llr_at` as shipped — this instrument measures the merged binary
  as-is, fusion included), this reproduces ~90% of 0g-2's magnitude without invoking channel
  (C4) at all.
- **Not established:** that this SAME position-mismatch mechanism, at these SAME magnitudes,
  is what happened on 0g-2's real rows specifically — real audio still carries fading/Doppler/
  multipath (C4) on top of whatever position the real pipeline chose. This experiment shows the
  mechanism is *sufficient* to produce collapse of the observed order, not that C4 contributed
  nothing.
- **Not re-litigated:** ROW 0g's own verdict, gate status, or Route B2's standing.
- The `-19.0 dB` operating point and `0.150s` shared anchor are **calibrated artefacts of this
  synthetic instrument**, not measurements of real-world SNR or timing — do not quote them
  outside this diagnostic's own context.

## 5. Suggested next step (not authorised by me — Phase B is the Architect's to shape)

Per spec Sec.4, B3 (`out_diag`, per-`n_syms` selection share) is the check that would show
directly whether C1's fusion rule is *handing* bits to whichever window the position-mismatch
happens to favour, which would tie this finding concretely to the fusion arithmetic rather than
leaving it as "the positions differ." That remains a native change (HK-011), not run here.

---

**No `src/`/`native/` edit, no rebuild, no push, no merge.** Full per-condition data (all 13
`delta_f` points, all 25 `delta_t` points, all 13 `delta_t×delta_f` joint conditions) is in
`phase_a_report.json`.
