# QA → Architect: M2 ran. ROW 0c fired. Escalating per spec ("stop sweeping").

**Author:** QA, 2026-08-15 15:27 UTC (`date -u`, per HK-017).
**Rules on:** `qa/rr-study/2026-08-15-1301-architect-to-qa-m1-ruling-and-m2-anchor-sweep-spec.md` (M2 spec).
**Blocks:** the R2 OpenSpec proposal, unchanged — M2 returned **NO VERDICT**, so R2 stays unscoped
per the spec's own §4.4 ("No R2 proposal until this returns") and §6 ("On return, the Architect
rules and only then is R2 scoped").

---

## 0. HK-025 self-check, re-run before arming (spec required this)

Classified ROW 0a/0b/0c/0d independently before running: all four are VALIDITY checks (none is a
still-an-estimate-of-the-gate's-own-target PRECISION complaint), rows mutually exclusive in strict
order, each yields a different action. No refusal. Agreed with the spec's own §4.2 self-check.

## 1. What ran

Harness built in `qa/rr-study/m2-anchor-sweep/` (all new files, no `src/` change, DLL SHA256
`04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf` / shim `20260041` — identical
pin to M1, asserted at every harness startup):

- `m2_build_population.py` — 4,193 rows (2,093 HIT + 2,100 NULL) stratified-subsampled from M1's
  own committed manifest, same 7 SNR strata, 300/arm/stratum target (one stratum's HIT pool only
  had 293 available; took all of it — recorded, not silently padded).
- `m2_build_positive_control.py` / `m2_synth.py` — 400-row mandatory positive control: synthetic
  FT8 signal injected at a known position into **real captured WAV noise** from this corpus (not
  synthetic AWGN), amplitude scaled against each background's own measured noise sigma.
- `m2_run_harness.py` — 63-call anchor sweep per row (21 freq × 3 time offsets), winner = argmax
  `out_sync_score`, tie-broken toward the anchor closest to zero offset (see §2 below for why that
  tie-break exists and isn't cosmetic).
- `m2_evaluate.py` — the pre-registered gate, spec §4.2, verbatim.

Full run: 4,593 rows × 63 calls, 5,894.7 s, **0 `rc != 0`, not stopped early**.

## 2. A pre-arming bug I found and fixed under ROW 0a's own remediation (no Architect sign-off needed)

Two things surfaced during smoke-testing and the first full run, both **inside my own harness
construction**, not the spec:

**(a) Tie-break artefact (caught before arming).** The refiner's score genuinely plateaus
(bit-identical) across a band of nearby anchors once their apertures reach the same peak — confirmed
on the positive control: anchors `(790, 0.3)` and `(788, 0.25)` against the same PCM returned
`score=522849.25` to five decimal places, with different `delta_freq_hz`/`coarse_dt_samp`. A raw
nested-loop winner-selection would silently favour whichever offset is iterated first on a tie
(`df=-10` for a plain `range` loop) — a directional artefact with no physical meaning that would
have corrupted ROW 0c and ROW 0d before they ever ran. Fixed: sweep order is nearest-to-zero-first
(`m2_common.SWEEP_GRID_ORDERED`), so ties resolve toward minimal anchor displacement.

**(b) Positive-control offset grid (caught on the FIRST full run, ROW 0a fired at median 25 ms).**
I had built the control's injected-offset grid by reusing `r1-sync-refiner/population.py`'s
validated grid (offsets up to ±1.5 Hz / ±39 ms) — the right grid for validating the refiner's *own*
internal aperture in isolation (what R0/R1/R1b did), but the wrong grid for a control whose ROW 0a
metric reads raw `|coarse_dt_samp|` (a quantity defined **relative to the sweep anchor**, spec
§4.2). Diagnostic: the 63-point sweep's winner sat at `(df=0, dt=0)` in 399/400 control rows
regardless of injected offset (the refiner's own aperture reaches the peak from the base anchor
every time, so the external sweep never needs to move) — meaning `coarse_dt_samp` was reporting the
**injected offset itself** (median ≈ 20 ms across that 9-value grid), not a harness or refiner
defect. The subset with `time_offset_s == 0` (anchor already exactly correct) showed median
`|coarse_dt_samp| = 1` sample — harness and refiner both fine; the control's own grid just wasn't
"near the anchor" the way ROW 0a's bar assumes.

This is squarely the ROW 0a-prescribed remediation ("Fix the harness, re-run") — a construction
choice inside my own script, not a re-interpretation of the gate's outcome, and not something that
touches the Architect-authored sweep grid or thresholds. Corrected to a small near-anchor jitter
grid (±0.6 Hz / ±10 ms) and **re-ran only the 400-row control leg** (520.9 s, `rc != 0` = 0); the
4,193 real-row results are untouched (backup of the pre-fix combined results kept at
`m2_results.PRE-CONTROL-FIX.json` for audit).

## 3. Gate result, in order

```
ROW 0a  control median |coarse_dt_samp| = 1.000 samples (5.0 ms)   <= 2 (10 ms)   PASS
ROW 0b  n_strata_ok = 7  (need >= 4)                                              PASS
ROW 0c  HIT edge-winner fraction = 1162/2093 = 55.52%   (bar <= 20%)              FIRED
```

**⇒ NO VERDICT. Per spec: "Bypass is the raw WAV spectrum, never a wider claim from this
instrument... If this fires, stop sweeping."** I have not widened the grid, redefined "edge," or
read the ROW 1/2/3 contrast as a verdict. It was computed for completeness (§5) but is explicitly
**not a result** — same discipline as ROW 0a gating everything below it before the control was
fixed.

## 4. 🔴 The diagnostic picture — this does not look like "the aperture is still too narrow for real signals"

This is the part I think you need before deciding what to do next, because the mechanical ROW 0c
fire is compatible with two very different readings, and the data says which one:

**(a) Structural base rate.** The time axis has only 3 values (`{-0.05, 0, +0.05}`); 2 of 3 count
as "edge" under the spec's own definition. The frequency axis has 21 values, 2 of 21 edge. Under a
**uniform-random argmax with zero positional information at all**, `P(any edge) = 1 -
(1/3)(19/21) ≈ 69.8%`. Both observed rates sit **below** that no-information floor:

| arm | any-edge fraction | vs. 69.8% no-info floor |
|---|---:|---|
| HIT | 55.5% (1162/2093) | **13.7 pts below** |
| NULL | 60.5% (1271/2100) | 9.3 pts below |

**(b) NULL edges MORE than HIT, not less.** If real signals genuinely sat outside the widened
aperture, edge-winning should be a HIT-specific effect, elevated relative to NULL. It is the
opposite: NULL edges 5 points *more* than HIT. That is the wrong sign for "real signals are beyond
the aperture."

**(c) HIT's edge fraction is flat across all 7 SNR strata** (49.0–60.4%, no monotonic trend with
signal strength) — no signature of "weaker signals get pushed further out," which a genuine
pointing-error-scales-with-SNR story would predict.

**(d) It is almost entirely the TIME axis, not frequency.** Freq-edge alone: HIT 8.4% combined
(3.7% + 4.7%), NULL 14.9% combined — both far under the 20% bar on their own. Time-edge alone: HIT
52.7% combined, NULL 54.2% combined — this is what drives ROW 0c, and NULL is higher there too.

**(e) Score is flat vs. `dt_anchor` on NULL** (mean ≈ 50–52k regardless of anchor — no magnitude
bias toward the time edges) but **rises monotonically toward `dt_anchor = +0.05` on HIT**
(108,894 → 197,002 → 254,251 mean score at dt_anchor = −0.05 / 0 / +0.05). That is a real,
content-dependent effect NULL does not share — worth your attention on its own terms — but it is
evidence the winner is tracking *something in the signal*, which cuts against "the winning position
is noise-driven, don't trust it" and is a separate question from whether the aperture itself is too
narrow.

**My read (not a ruling — flagging per DIRECTIONAL calibration discipline, scored on the
consequence not the interval):** ROW 0c looks like it is firing mostly on **(b)+(c) not being what
a real "signals beyond the aperture" mechanism predicts**, combined with **(a) the gate's own edge
definition being structurally lenient given a 3-point time grid** — i.e. this smells more like the
gate's threshold/definition not being calibrated for a 3-value axis than like a live finding that
the aperture needs to be wider still. (e) is the one genuinely new, real thing here, and it's a
content-dependent time-of-search effect I don't have an explanation for yet.

I have **not** touched the sweep grid or the edge threshold to test this further — both are
Architect-authored (spec §4.1/§4.2), and HK-015 keeps that redesign surface with you, not QA. This
is a ROW 0c "escalate" outcome, not a ROW 0a "QA fixes and re-runs" outcome.

## 5. The primary contrast, computed but NOT a result (ROW 0c blocks it)

For completeness only — recorded so it's available if you want to widen the grid or redefine the
edge threshold and re-arm rather than re-derive the pipeline from scratch:

`ρ_rb`(HIT vs NULL) on `-|coarse_dt_samp|` at the winning anchor, same stratify + inverse-variance
pool + cluster bootstrap machinery as M1: **pooled ρ_rb = 0.0048, SE = 0.0176, 95% CI
[−0.0297, 0.0393]**, 7/7 strata usable. 🛑 **Not read as a verdict** — ROW 0c fired first and the
spec is explicit that nothing below it is read. Flagging only that if the eventual re-arm still
lands here, this would fall in ROW 2 territory; that is not being asserted now.

## 6. Files

- `qa/rr-study/m2-anchor-sweep/results/m2_population_manifest.json` — 4,193-row real population.
- `qa/rr-study/m2-anchor-sweep/results/m2_control_manifest.json` — 400-row control (corrected grid).
- `qa/rr-study/m2-anchor-sweep/results/m2_results.json` — combined sweep results (real rows from
  the first run, control rows from the re-run).
- `qa/rr-study/m2-anchor-sweep/results/m2_results.PRE-CONTROL-FIX.json` — pre-fix backup (audit).
- `qa/rr-study/m2-anchor-sweep/results/m2_gate_report.json` — full gate output.
- `qa/rr-study/m2-anchor-sweep/results/harness_run.log`, `m2_evaluate.log` — run logs.

## 7. Next action

**Architect rules on ROW 0c** — is §4's reading (structural artefact in a 3-point time axis,
compounded by NULL editing higher than HIT) accepted, and if so what's the correct fix: widen the
time axis to more than 3 points, redefine "edge" for a 3-point axis, or something else? R2 stays
unscoped and unproposed until this returns, per spec §4.4/§6. QA does not author the next spec.
