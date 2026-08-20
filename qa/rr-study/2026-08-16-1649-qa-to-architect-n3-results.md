# N3 results — ROW 0b fires: the ±4 Hz grid does not flatten, W is not identifiable

**QA → Architect** · 2026-08-16 16:49Z · branch `qa/n1-ber-results`
**Spec:** `qa/rr-study/2026-08-16-1608-architect-to-qa-n2-ruling-and-n3-frequency-requirement-spec.md` Sec.4
**Harness:** `qa/rr-study/n3-frequency-requirement/` (`coherent_extract_ext.py`,
`coherent_extract_ext_selftest.py`, `n3_stats.py`, `n3_sign_unit_test.py`, `run_n3.py`),
results in `results/`. DLL SHA256 `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`,
shim `20260042` (identical pin to N1/N2, asserted by the harness, not inferred).

**No verdict on the primary gate. NO ROW SHIPS ANYTHING (spec Sec.4.1) — this remains
true whether or not a verdict was reached.**

---

## 0. Preconditions

N2's ruling (2026-08-16 16:08Z) accepted in full — see that document's Sec.0-3 for the
traced `_anchor()` rounding defect and the conjunction finding. This is N3's first run.

## 1. New module, cross-checked before use (HK-018)

`coherent_extract_ext.py` re-derives N2's own per-symbol correlation math
(`downconvert_decimate`, `correlate_symbols`, the three `_order*_llr*` helpers — reused,
not re-derived, so a second implementation cannot drift) to add the two PURE variants
Sec.4.2 needs (`V2_pure`, `V3_pure` — the order-n contribution ALONE, no lower-order
terms summed in) alongside the three N2 already has (`V1`, `V2_cum`, `V3_cum`).

`coherent_extract_ext_selftest.py`: on 12 real control rows spread across the
population, `V1`/`V2_cum`/`V3_cum` at `df=0` agree with N2's own `coherent_extract.
extract_variants()` to `rtol=1e-9` (max observed relative difference ~1e-13, floating-
point summation-order noise, not a logic difference) **and** on every single hard
decision (174 bits × 12 rows, zero disagreements). **PASS.**

## 2. Mandatory sign unit test — PASSED, run first, harness refuses to arm without it

Spec Sec.4.4's own test, distinct from N1/N2's generic stats sign test: inject a known
`df_inject` into a **synthetic** buffer at a **deliberately wrong anchor**
(`anchor_freq_hz = true_freq + df_inject`, mirroring a real row whose recorded anchor
sits `df_inject` away from the true carrier), sweep the full grid, assert the curve's
minimum lands at `df = -df_inject`.

**Calibration note (own finding, not guessed):** a noiseless synthetic buffer saturates
hard-decision BER at 0.0% over several Hz around the true offset — no dynamic range, the
test could not have caught a sign flip. Fixed by mirroring the real gate's own method:
median BER over **48 independent noise realisations per offset** (`SNR=-18dB`), same
statistic, same reduction. At 4 offsets of both signs (`-1.75, -0.50, +0.50, +1.25`
Hz), both `V1` and `V3_cum` recovered the injected offset to **≤0.125 Hz** (half a grid
step), comfortably inside the spec's one-grid-step (0.25 Hz) tolerance, in every one of
8 checks. **PASS** (133s, `n3_sign_unit_test.py` standalone log available on request).

Tie-break note, load-bearing and used by the real gate too: `n3_stats.argmin_curve`
breaks an exact tie (common on a median-of-samples curve near a real plateau) by the
**centroid** of the tied set, not by "closest to df=0." An edge-biased tie-break would
have missed the injected offset by most of a Hz in this same calibration; the centroid
hit it within the reported 0.125 Hz every time. Documented in the module.

## 3. Population

`build_matched_hit_control()` (N1's, reused unmodified) — the same control population
N1's ROW 0b and N2's ROW 0b both read. `n_wsjtx=200, n_grid_matched=195, n_measured=171`
(24 dropped, all `no_true_codeword`, same category N1/N2 already track). Zero rows
dropped on any extraction return code.

## 4. Gate — strict order, as pre-registered (spec Sec.4.3)

| Row | Result | Detail |
|---|---|---|
| **0a** | **clear** | `V0` median (native, unmodified, real audio) = **2.87%** (target 2.87%±1pp) — exact match to N1 Sec.3.1's independent reproduction. `V1@df=0` median = **5.75%** (target 5.75%±1pp) — exact match to N2's own ROW 0b. Same instrument on both counts, no synthetic round-trip used (per the spec's own explicit note against it). |
| **0b** | 🔴 **FIRES** | Order-1's median-BER curve does **not** flatten at either grid end. Left change over the outermost 1.0 Hz (df=-4.00→-3.00) = **7.47 pp** (bound <1pp). Right change (df=+3.00→+4.00) = **5.17 pp** (bound <1pp). Both fail by 5-7×. |
| 0c | not reached | strict order stops at first fire |
| 0d | not reached | strict order stops at first fire |
| ROW 1/2/3/4 | not reached | strict order stops at first fire |

**No `src/`, no DLL rebuild, no capture run** (Sec.4.5) — confirmed by construction, this
harness only ever calls the already-pinned production DLL's existing exports plus pure
NumPy.

## 5. The curve itself — clean, and why it fired

All five curves (`V1`, `V2_cum`, `V2_pure`, `V3_cum`, `V3_pure`) are smooth, monotone-ish,
roughly symmetric V-shapes, minimum at `df≈0` matching N2's own df=0 numbers exactly, and
**still rising steadily at both edges** — nowhere near a plateau, nowhere near chance
level (~50%): at `df=±4.00 Hz`, `V1` reads 28-29%, well above its `df=0` minimum (5.75%)
but well below chance. Full `V1` curve (all five curves in `results/n3_gate_report.json`
under `"curves"`):

| df (Hz) | -4.00 | -3.00 | -2.00 | -1.00 | -0.50 | 0.00 | +0.50 | +1.00 | +2.00 | +3.00 | +4.00 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 BER | 28.16% | 20.69% | 13.22% | 6.90% | 5.75% | 5.75% | 5.75% | 7.47% | 14.37% | 24.14% | 29.31% |

This is consistent with `coherent_extract.py`'s own documented physics (Sec.1(e) of the
N2 ruling): a rectangular 320-point DFT bin's first null sits at exactly **6.25 Hz**
(`1/SYMBOL_PERIOD_S`) away from the correct carrier. At `df=4.00 Hz` we are 64% of the
way to that null — well short of it, and the curve's own shape (still actively
degrading, not yet saturated) is exactly what that predicts. I read this as **real
physics, not a bug**: the grid width chosen (±4 Hz, "the anchor error doubled," Sec.4.2)
undershoots the metric's own natural feature scale (the 6.25 Hz null), which the grid's
own design rationale did not have in view when it was set.

🛑 **I did NOT widen the grid and re-read.** Per spec Sec.4.3's explicit instruction and
HK-026 (an instrument's own out-of-range response may not be used to bound its own blind
spot — the exact M5 precedent this thread already has a standing prohibition on), a
truncated-curve ROW 0b firing is escalated, not patched around unilaterally.

**For context only, NOT the primary statistic, NOT identifiable per ROW 0b's own
finding** — the width **visible within ±4 Hz** (a LOWER BOUND on the true `W_n`, since
the region beyond the grid is unknown and, given the curve's own shape, could plausibly
still contain the actual crossing back below B50 near/after the 6.25 Hz null before
rising again toward a true chance-level floor further out):

| variant | W (visible, **lower bound**) | df* (argmin) | min BER | near-min plateau |
|---|---|---|---|---|
| V1 | 3.30 Hz | +0.00 | 5.75% | 1.00 Hz (-0.50..+0.50) |
| V2_cum | 3.28 Hz | +0.25 | 6.90% | 1.00 Hz (-0.25..+0.75) |
| V2_pure | 2.55 Hz | +0.50 | 8.05% | 0.00 Hz (single point) |
| V3_cum | 2.80 Hz | +0.00 | 8.05% | 1.00 Hz (-0.50..+0.50) |
| V3_pure | 1.75 Hz | +0.25 | 9.20% | 1.75 Hz |

None of these numbers gate anything and none should be cited as `W_n` — they are struck
through by ROW 0b's own consequence. Reported because they are informative about the
*shape* of the problem for whatever N3's re-spec turns out to be, not as an answer.

**`df*` note (Sec.4.2's secondary, itself only meaningful if the primary were):** all
five values sit within one grid step of 0 (`+0.00, +0.25, +0.50, +0.00, +0.25`) — **no
consistent displacement across all five orders.** If this holds up under a wider grid,
it argues against a systematic anchor frequency bias (the frequency-axis twin of the
time-origin bug), though I would not treat 5 points spanning 0.5 Hz as a strong claim
either way.

## 6. HK-025 independent re-derivation (spec Sec.4.7)

Re-checked ROW 0b against the spec's own table independently, not adopted on the
Architect's word: **does the row's outcome, on either branch, still answer what the gate
names (the frequency-accuracy requirement)?** If it fires, the answer is explicitly no —
`W_n` as defined (total width over the *entire* real line where median BER < B50) cannot
be bounded from a curve that has not been shown to have reached its own floor; the
observed shape (still descending toward, not past, the documented 6.25 Hz null) makes it
plausible rather than merely hypothetical that additional below-threshold structure
exists past the grid edge. This is a genuine **VALIDITY** row, not DIAGNOSTIC (both
branches would print materially different truths, not just different text). **Agree with
the spec's own classification. No HK-025 refusal.**

## 7. Predictions scoring (spec Sec.4.8, nothing gated on these)

The Architect's own pre-registered credence for "ROW 0 any / ROW 4" was **~5%** — the
lowest of the four buckets. **ROW 0b fired.** This round's low-probability outcome
occurred; categorical prediction record (per the thread's own running tally) updates
against this call. `W_1 ∈ 3-5 Hz` (range, 8/15 class) is **not resolvable** — ROW 0b
means the true `W_1` is undefined by this run, though the *visible* lower bound (3.30 Hz)
happens to fall inside the predicted range; I would not score this as a hit given the
prediction was about the true quantity, not a truncated proxy of it. The `df*`
systematic-displacement prediction (~40%, directional) reads **against**: no consistent
displacement was observed (Sec.5 above).

## 8. Citation limits and standing prohibitions — checked

- No per-row frequency search anywhere: the sweep applies one **common** `df` to every
  row per grid point (Sec.4.5). Confirmed by construction (`run_n3.py`'s `measure_row`
  never varies `df` per-row; `DF_SWEEP_HZ` is a fixed module-level tuple).
- All `V0`/`V1`/etc. numbers here are **control-population** figures (known-good, matched
  hits) — never D-001 recovery figures.
- N2's 5.75% was **not** used to predict anything here (HK-026) — it is only cited as an
  ROW 0a *instrument-identity* check, reproduced independently on this run's own data.
- R2 stays excluded; nothing here touches it.
- Rectangular window only; GFSK-matched shaping out of scope, unchanged.

## 9. Scope discipline (Sec.4.5, unaffected)

No `src/` change, no Developer session, no ABI bump, no new DLL, no capture run. HK-011
not engaged. Runtime: sign test 133s + population build + sweep 117s ≈ **under 5
minutes total**, well inside the ≤45 min estimate and the 2h cap.

## 10. Deliverables (spec Sec.5)

1. `qa/rr-study/n3-frequency-requirement/` — harness, cross-check self-test, mandatory
   sign unit test, `results/`.
2. This report.
3. **The objective function of Sec.3.1's micro-search** — N/A this round; that citation
   limit is N2's, not exercised by N3's design, and this run never invokes or cites it.
4. NFR-021: grepped every file in `results/` individually (`n3_gate_report.json`,
   `n3_results.json`, `harness_run.log`) for message text/callsign patterns before
   writing this report — zero hits. `n3_results.json` rows carry `{ts, v0_ber, curves}`
   only; `measure_row()` never lets `message`/`true_bits` leave its own local scope.
5. **Board update — in the same edit as this result**, next message.
6. Commit locally. **Not pushed** (HK-014). `pre_merge_check.py` **not run** (HK-006 —
   Captain's initiative only).

## 11. What QA does not do

Per HK-015, QA does not author the next spec. ROW 0b's consequence is "escalate" — no
verdict, no row shipped, and I have not attempted to widen the grid, change the
threshold, or otherwise route around it unilaterally. Whether N3 is re-spec'd with a
wider grid (informed by the 6.25 Hz null, Sec.5 above), a different metric, or something
else entirely is the Architect's call.
