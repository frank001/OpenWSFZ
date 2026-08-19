# ARCHITECT → QA — ROUTE B, BUILD SPEC: make the DT axis honest in BOTH directions

**2026-08-19 16:30Z · Architect · Captain authorised "Route A now, then B" at 16:12Z · follows the `D2` ruling (15:58Z) and Route A (committed)**

**Status: BUILD SPEC, NOT A MEASUREMENT. QA-tooling only — `qa/rr-study/**`. NO `src/` change,
HK-011 NOT engaged. 🛑 This document deliberately does NOT pre-register the measurement; see §5 for
why that is a correctness requirement and not a delay.**

---

## 0. 🔴 BLOCKING FINDING — the same clamp is ALSO wrong on the positive side, and that side is LIVE

I found this while grounding this spec in `modulator.py` rather than writing it from the `D2`
report. **Deal with this before anything else in this document.**

`modulator.py:80-81` clamps at **both** ends:

```python
start = int(round(dt_s * fs))
start = max(0, min(start, len(slot) - len(signal)))
```

The FT8 transmission is **12.64 s** inside a **15 s** slot, so the largest representable positive
offset is **2.36 s**. `s3-dt-offset.json` sweeps parts to **2.7 s**. Measured, not reasoned:

| S3 part | label `dt_s` | actually rendered | truth-label error |
|---|---|---|---|
| 0–7 | 0.0 … 2.1 | exact | 0.000 s |
| **8** | **2.4** | **2.3600** | **−0.040 s** |
| **9** | **2.7** | **2.3600** | **−0.340 s** |

**Two of ten S3 parts are mislabelled, and parts 8 and 9 render IDENTICAL audio under two different
truth labels.** This is not the guarded negative-DT case — **S3 runs in the routine suite and this
is live today.** Consequences:

- **Every S3 Bias & Linearity and DT GR&R number since 2026-06-06 is computed against wrong truth
  for 20 % of its parts**, with two parts degenerate (same physical position, different label).
- **It lands exactly on `D2`'s sparse high-leverage x-values.** `D2`'s ROW 4 slope regressed `Δ` on
  `true_dt_s` out to 2.7 with only 1–3 pairs per bucket above 0.30 — i.e. its entire x-leverage sat
  on the two mislabelled parts. This is **error in the stratifying variable**, which per the
  standing note *attacks the contrast, always toward zero*. It is a **second, independent** reason
  ROW 4's slope was uninterpretable, arrived at from a different direction than §2 of the ruling.
  ✅ It does not change the ruling; it hardens it.

🛑 **QA: do not fold this into the Route B build silently.** Report it as its own defect with its own
before/after evidence, because it invalidates published S3 history and the negative-DT work does
not. The *fix* is the same line, which is why it belongs in this spec — the *disclosure* is separate.

⚠️ **Do NOT "fix" this by widening the slot buffer.** 2.36 s is a real physical limit of a 12.64 s
signal in a 15 s slot; a part at 2.7 s cannot both start at 2.7 s and finish inside its own slot.
The honest options are (a) re-grid S3's parts to ≤ 2.36 s, or (b) let the signal run into the next
slot as §1 requires for the negative case. **That is a scenario-design decision, not a coding
decision — bring me the measurement, and I will rule with the Captain.** Do not re-grid unilaterally.

---

## 1. What Route B must build — stated as a CONTRACT, not an implementation

I am specifying behaviour and acceptance. **The mechanism is QA's** — you own this harness and you
know its timing better than I do.

**C1 — `modulate()` must place a signal at any `dt_s` it is given, or refuse.**
> For any `dt_s` in the scenario range, the rendered audio's actual signal position must equal
> `dt_s` to within **one sample**. Where that is physically impossible in a single slot buffer, the
> function must **raise**, not silently clamp. 🛑 **Silent saturation is the defect this whole
> thread is about. A loud failure is always acceptable; a quiet wrong answer never is.**

**C2 — negative `dt_s` must produce genuinely early audio.**
> The signal occupies the tail of the preceding slot and the head of the nominal one. Whether that
> is a split render, a padded two-slot buffer, or an early-armed playback is yours to choose.

**C3 — `run_scenario.py` must arm playback so that the rendered signal reaches the device at the
time its truth label claims**, and the S3b hard-exit at `:820` is removed **in the same change that
makes S3b correct** — never before.

**C4 — S3b is registered** in `run_study.py`'s `_SCENARIO_REGISTRY` and reachable from a targeted
run. ⚠️ Per HK-020, verify the ONE config that defeats this: pass
`--device "Voicemeeter AUX Input"` explicitly — the default is still `"CABLE Input"`, which is
unreliable on this machine.

---

## 2. 🔴 The acceptance gate that matters — prove the audio MOVED, in the synth, before any decode

This is the heart of the spec. The clamp survived from 2026-06-05 to 2026-08-19 — through a code
review that *documented it* — because **nothing ever asserted that the audio went where the label
said.** Every downstream check consumed the label and agreed with itself.

**G1 — Placement proof, offline, no decoder, no device.**
> For each `dt_s` in the scenario grid, render the part and **cross-correlate against the `dt_s = 0`
> render**. Assert the argmax lag equals `dt_s` **to within one sample**. Report the full table:
> label, measured lag, error, PASS/FAIL. Any FAIL blocks the run.

Cheap, decisive, and it would have caught this on day one in both directions. **G1 must also run
over S3's positive grid**, which is how §0 gets its before/after evidence.

**G2 — Distinctness (the inverted contract).**
> For every pair of distinct labels, assert the renders are **not** bit-identical. This is the exact
> assertion `tests/test_modulator.py:73` currently inverts, and it is what catches degeneracy like
> S3 parts 8 and 9.

**G3 — Self-validation, per STUDY-SPEC §5, extended to the new range.**
> WSJT-X must decode a clean (+10 dB) rendering at **every** `dt_s` in the grid, including the
> negative ones. 🛑 **If WSJT-X cannot decode an early-rendered signal, the render is wrong until
> proven otherwise** — the reference decoder handles real early transmissions in service, so a
> failure here is our synth, not its limitation. Do not proceed to a study run on a grid point that
> fails G3; report which points failed and stop.

**G4 — HK-026, stated now so it cannot be skipped later.**
> At `dt_s = 0`, both appraisers must decode **≥ 95 %** at the scenario's fixed SNR. If they do not,
> the run measures SNR margin, not the DT boundary, and no decode-rate knee it reports is
> attributable to DT.

---

## 3. Replacing `tests/test_modulator.py:73` — do it visibly

`test_negative_dt_is_clamped_to_zero()` asserts `at_zero == at_neg`. It is a **correct test of the
old contract** and it must be **replaced with its inversion**, not deleted:

- New test asserts negative `dt_s` renders **differently** from zero, and that the cross-correlation
  lag equals `dt_s`.
- 🔴 **Keep the old test's name in the diff** (rename to something like
  `test_negative_dt_shifts_signal_earlier`) so a reviewer sees a contract *changed*, not a test
  *lost*. A deleted test is invisible in a green CI run; a changed one is not.
- Add the positive-side case from §0 as its own test — a part at 2.7 s must either render at 2.7 s
  or raise.

---

## 4. ⚠️ S3b as designed CANNOT resolve a decode-rate knee — fix the sizing before running it

Applying HK-021(m)/(o) to the scenario *before* it runs, which is the point of having them.

S3b specifies **10 parts × 2 appraisers × 3 trials**. Three Bernoulli trials per part gives a
decode-rate standard error of **≈ 29 pp** at p = 0.5 — the readout cannot distinguish 100 % from
70 % at a single part. **A knee is exactly what such a design cannot see.**

**Required sizing, to be confirmed by QA against wall-clock reality:**
- Target resolution **≈ ±10 pp per part** ⇒ **n ≈ 100 trials per part** (`1.96·SE ≈ 9.8 pp` at
  p = 0.5, tighter at the extremes).
- 10 parts × 100 trials × 15 s ≈ **4.2 hours**, both appraisers concurrent on one stream.
- ⚠️ That is an unattended run ⇒ **HK-013 applies: a validated supervisor, live-tested, with the
  UTC-midnight log-rotation guard ported** (HK-013 addendum — it has killed two healthy instances).
- ⚠️ HK-021(j): any *absence*-based claim (e.g. "no decodes below X") needs λ ≥ 5 expected events
  before absence is evidence.

🔴 **If 4.2 hours is not acceptable, cut PARTS, not TRIALS.** A 5-part grid at 100 trials resolves a
knee; a 10-part grid at 30 trials resolves nothing. Bring me the tradeoff rather than splitting the
difference.

---

## 5. 🛑 Why the measurement is NOT pre-registered in this document

This is a direct application of the sibling the Captain minted an hour ago.

**HK-021(o) says a resolution gate must be stated against the coarsest quantum in the readout
chain.** For an instrument that **does not exist yet**, I cannot state that quantum honestly — I
would be guessing at the resolution of a thing QA has not built, which is precisely the error that
made `D2`'s ROW 0f decorative (`1.96·SE ≤ 0.05 s` cleared by `2.2×10⁻¹⁶`, certifying a precision the
instrument never had).

**So: two documents, in this order.**

1. **This one** — build to the contract, pass G1–G4, report the §0 defect, report the achieved
   sizing and the measured per-part resolution.
2. **Then I pre-register the measurement**, with rows and thresholds stated against the resolution
   *you measured*, and score my predictions against it.

🔴 **QA: do not read a decode-rate knee out of the G1–G4 validation data and report it as a result.**
Validation output is allowed to be looked at — that is what it is for — but the *finding* needs its
own pre-registration, or it is a re-read of an ungated instrument. If the knee is glaringly obvious
during validation, say so plainly in your report as an **unblinded observation**, flag that it
de-blinds my §6 predictions, and I will void them rather than argue the point.

---

## 6. Sealed predictions — recorded now, while I am blind

No negative-DT decode data exists anywhere in this repo, so these are genuinely blind. My ranges run
under-dispersed, so I have widened them deliberately.

| quantity | prediction |
|---|---|
| Does `modulate()` currently mis-place any **positive** S3 part? | **YES, parts 8 and 9** — ✅ already confirmed in §0, not scored |
| Decode rate at `dt_s = 0`, both appraisers | **≥ 98 %** |
| Where OpenWSFZ's decode rate first drops below 90 % | **dt ∈ [−1.5, −0.6] s** · P ≈ 0.5 · *the interesting case, and the one that would make the Part C search-window story live* |
| Does OpenWSFZ's knee sit **earlier** (more negative) than WSJT-X's? | **NO — I predict OURS fails FIRST**, P ≈ 0.65 |
| Gap between the two knees | **0.3–0.9 s** · 80 % interval |
| Will G3 (WSJT-X decodes our early renders cleanly) pass at every grid point? | **NO** — P ≈ 0.3 that at least one extreme point fails, most likely `−2.7 s` |

🛑 **Reasoning disclosed so it can be discounted rather than inherited:** the one-sided-search-window
story predicts our knee is earlier and sharper than WSJT-X's. **That story is currently
UNTESTABLE and I have explicitly refused to let it explain Part C** (ruling §5). Recording it as a
prediction is how it earns the right to be believed — or gets killed. **If the knees coincide, the
story is dead and I will say so.**

---

## 7. Scope discipline

- **QA-tooling only.** `synth/modulator.py`, `harness/run_scenario.py`, `run_study.py`,
  `tests/test_modulator.py`, `scenarios/*.json`. **No `src/`. HK-011 not engaged.**
- **Does not authorise a `src/` change on any outcome.** Even a knee exactly at −0.65 s justifies a
  *proposal* to the Captain, not work.
- **Does not reopen:** `AO1` (closed), Part C / C2, the ledger correction, `D1`, `D2`'s ruling, N1,
  N5, GH #111's device axis, or any standing prohibition.
- **Does not re-grid S3** — §0 flags the choice and reserves it (Architect + Captain).
- ⚠️ **NFR-021 applies to every emitted file individually**, including any new validation table; the
  run directory's own cleanliness does not extend to derived files.
- ⚠️ **HK-016:** gather run artefacts into a dated `./artefacts/` dir with a `README.md` before
  reporting done.

---

## 8. Order of work, so a partial run is still useful

1. **§0 disclosure** — G1 over S3's existing positive grid. Standalone, no build needed, ~minutes.
   **Report this first, even if nothing else lands.**
2. Build C1 + G1 + G2 + the §3 test replacement. Offline, no device.
3. G3 self-validation over the full grid.
4. C3 + C4 + sizing (§4), supervisor per HK-013.
5. Report and **STOP**. I pre-register the measurement against your measured resolution.

**Next action: QA runs step 1 and reports. Steps 2–4 need no further authorisation from me; step 5
is a hard stop.**
