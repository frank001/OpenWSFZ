# QA -> ARCHITECT -- ROUTE B SEC.8 STEPS 2-4: BUILT, VALIDATED OFFLINE, REPORTING AND STOPPING PER SEC.8 STEP 5

**2026-08-19 16:54 UTC -- QA -> Architect**

**Status: build complete (C1-C4, G1/G2/G3 tooling, sec.3 test replacement, sec.4 sizing
correction). No live run performed -- this is the hard stop your sec.8 step 5 calls for.
QA-tooling only, no `src/`, HK-011 not engaged.**

Spec: `qa/rr-study/2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md`
("the spec"). Step 1 (SS0 disclosure) was reported separately:
`2026-08-19-1631-qa-to-architect-route-b-step1-g1-s3-positive-grid-disclosure.md`.

---

## 1. C1/C2 -- `synth/modulator.py`

`modulate()` gained an `extended: bool = False` keyword-only parameter.

- **Default (`extended=False`)** -- unchanged return shape for every existing caller.
  Placement outside `[0.0, slot_length_s - transmission_s]` (~`[0.0, 2.36]` s at FT8
  defaults) now **raises `ValueError`** naming the exact samples requested, the buffer
  bounds, and the valid range -- instead of silently clamping. This is the direct fix for
  SS0: I confirmed by dry-running the UNMODIFIED `s3-dt-offset.json` part 8 through the
  full harness (`harness/run_scenario.py --dry-run`) and it now raises with a full
  traceback naming `dt_s=2.4000` and the 2.36 s cap, rather than silently mislabeling.
- **`extended=True`** -- returns `(buffer, buffer_start_s)`. `buffer_start_s <= 0.0`
  always; it is exactly `0.0` (and `buffer` byte-identical to the non-extended return)
  whenever the placement already fits in one slot -- this is a superset contract, not a
  divergent one, and I unit-tested that claim directly
  (`test_extended_matches_single_slot_when_placement_already_fits`).

`synth/encoder.py`'s `render_tones`/`encode_message`/`encode_message_type4` gained the
same `extended` keyword and forward it through unchanged; noise is added to the signal
array either way, the offset passes through untouched.

**Checked, not touched:** `m2-anchor-sweep/m2_synth.py` calls `modulator.modulate()`
directly with a non-default `slot_length_s` (a real captured-buffer length, not 15 s) and
never passes `extended=`. It is closed/archived M2 work, out of Route B's scope, and the
default-`False` behaviour for any `dt_s` that already fit is byte-identical to before --
unaffected unless it was already silently wrong, which I did not investigate (out of
scope).

## 2. sec.3 -- test replacement

`tests/test_modulator.py`:

- `test_negative_dt_is_clamped_to_zero` -> **renamed** (not deleted)
  `test_negative_dt_shifts_signal_earlier`. Asserts `buffer_start_s == -1.5`, asserts
  energy exists in the samples before absolute t=0 (the retired contract had none, ever),
  and cross-correlates against the dt=0 render to confirm the *signal content* sits at
  -1.5 s to one sample -- the same black-box method as G1, not a re-derivation of
  `modulate()`'s own arithmetic.
- New `test_positive_dt_beyond_single_slot_raises_or_places_exactly` -- the SS0 case
  itself (label 2.7 s): asserts the default call raises `ValueError`, and that
  `extended=True` places it exactly.
- New `test_extended_matches_single_slot_when_placement_already_fits` -- the superset
  claim above, checked directly.

Full suite: **176/176 pass**. `test_modulator.py` itself: 6 tests before this change, 8
after (one renamed+rewritten in place, two newly added). Re-run twice, byte-identical
`pytest` summary line both times.

## 3. G1/G2 over the full grid -- `g1_g2_full_grid_placement_check.py`

Supersedes step 1's script in scope (that one stays as-is: it is now the "before"
evidence, and correctly raises on S3 parts 8/9 today rather than needing an update). This
one renders **every S3 part (0-9, positive) and every S3b part (0-9, negative) with
`extended=True`**, cross-correlates each against a `dt_s=0.0` reference, and checks G2
distinctness across the full 20-part set using absolute-time alignment (so buffers of
different length/offset are compared bit-for-bit rather than trivially "not equal").

Result, run twice, byte-identical:

```
RESULT: all 20 parts PASSED placement (S3: 10, S3b: 10).   [max |error| = 0.0000 s]

G2: 1 bit-identical pair(s) total (1 same-label/expected, 0 DIFFERENT-label/UNEXPECTED):
    ('S3', 0) (label 0.0) == ('S3b', 0) (label 0.0)  [expected (same label)]
```

Every part places to the sample. **S3 parts 8 and 9 -- the SS0 degenerate pair -- are no
longer identical**; the only bit-identical pair left is the two scenarios' shared
`dt_s=0.0` part, which is supposed to match. G1/G2 both pass cleanly.

## 4. G3 -- `g3_full_grid_self_validation_render.py`

Renders one +10 dB, 12 kHz WAV per (scenario, part) across the full 20-part grid,
generalising `gate_render.py`'s existing pattern. Ran cleanly, 20 WAVs written to
`g3_full_grid_wav/` (gitignored, same as `gate_wav/`).

**NOT YET CONFIRMED.** Per `gate_render.py`'s own established convention, the actual
"does WSJT-X decode this and report the right text" check is a **manual File > Open
step in the WSJT-X GUI** -- this harness does not automate that, and I have no way to
drive the GUI from here. The WAVs are rendered and waiting; someone needs to load all 20
and confirm text, per the printed procedure. **I am reporting this gap plainly rather
than asserting a pass I did not observe.**

## 5. G4 -- not measured

>=95% decode at `dt_s=0` for both appraisers requires an actual decode count, which needs
either the G3 manual step above (at minimum, confirming the two `dt_s=0.0` WAVs decode)
or a live run. Not done. Flagging rather than assuming.

## 6. C3 -- `harness/run_scenario.py`

- The `:820` hard-exit is **removed**, in this same change, per your explicit
  instruction not to remove it separately from making S3b correct.
- `_render_single` now reads a new scenario-JSON field, `"requires_extended_dt"`, and
  when set, calls `encode_message(..., extended=True)` and returns
  `(samples, buffer_start_s)` instead of a bare array. **S3b's JSON sets this flag; S3's
  does not** -- that is deliberate, not an oversight (sec.7). `_wait_for_cycle` gained an
  `early_by_s` parameter; the main loop computes `early_by_s = -buffer_start_s` and, when
  live (non-dry-run), advances `boundary_ts` by whole cycles until there is enough lead
  time for prewarm + the early offset before sleeping -- so an S3b part armed 2.7 s early
  can never compute a sleep target already in the past.
- Verified via `--dry-run` (no device/hardware needed):
  - **S3b**, `--parts 0,1,9` (dt=0.0, -0.3, -2.7), 100 trials each -- 300 trials
    injected, no crash. `truth.csv` inspected: `true_dt_s` matches the label exactly for
    every part (0.0, -0.3, -2.7), `message_text` correct.
  - **S3 unmodified**, `--parts 8` -- raises `ValueError` through the full harness stack
    (not just the synth layer), confirming C1's fix reaches the routine path.
  - **S1, S4, S8** (untouched scenarios) -- dry-run unaffected, no regression.
- **Known, non-blocking gap, out of Route B's declared scope:** `--dump-wav-dir`'s
  `_dump_slot_wav` helper truncates/pads to a fixed 15 s window from the front of
  whatever `samples` array it is given. For S3b's most negative part (dt=-2.7 s, 17.7 s
  buffer) this happens to still capture the whole signal (ends at 9.94 s absolute, well
  inside the kept `[-2.7, 12.3)` window), but I did not verify this generalises and
  `--dump-wav-dir` is not part of C1-C4 or used by S3b's own decode-rate analysis path.
  Flagging, not fixing.

## 7. C4 -- `run_study.py`

`S3b` added to `_SCENARIO_REGISTRY`, reachable via `--scenarios S3b`, **deliberately not**
added to `_CONTROLLED_SCENARIO_IDS` (the default batch) -- same treatment as S8. The
module's `--device` default is still `"CABLE Input"`; per HK-020 and the standing
capture-endpoint note, `--device "Voicemeeter AUX Input"` must be passed explicitly for
any real S3b invocation. Documented inline at the registry entry so this isn't
rediscovered later.

## 8. sec.4 -- sizing

`scenarios/s3b-dt-boundary.json`: `trials` corrected from 3 to **100** (mechanically
required floor for +-10pp resolution at p=0.5, per your sec.4 math -- not a preference).
New `_sizing_note` field states the arithmetic and the open tradeoff. **I have not cut any
parts.** All 10 remain, at ~4.2h unattended (10 parts x 100 trials x 2 appraisers x 15s)
if run as-is. Per your explicit instruction ("bring me the tradeoff rather than splitting
the difference"), that choice is yours/the Captain's:

| option | parts | trials/part | wall-clock | resolves a knee? |
|---|---|---|---|---|
| as specified | 10 | 100 | ~4.2 h | yes, at 0.3 s granularity |
| cut parts | 5 (which 5?) | 100 | ~2.1 h | yes, at 0.6 s granularity (coarser) |

I have not picked which 5 -- that needs your judgement about where the knee is likely to
sit (your own sec.6 prediction, `dt in [-1.5,-0.6] s`, would argue for keeping density
there rather than at the sparse -2.1/-2.4/-2.7 tail, but that's exactly the kind of
post-hoc reasoning your sec.6 asked to have disclosed and discounted, not silently acted
on by me).

## 9. Scope check against sec.7

No `src/` change. No re-grid of S3 (its JSON is untouched; parts 8/9 now raise instead of
mislabeling, which is the correct interim state pending your ruling). Did not reopen AO1,
Part C, `D1`, `D2`, N1, N5, or GH #111. NFR-021: the only message text anywhere in the
new WAVs/JSON is `"CQ Q1ABC FN42"` (synthetic Q-callsign, already in use throughout the
study). No live-run artefacts exist yet (no live run occurred), so HK-016's `./artefacts/`
gathering doesn't apply this round.

## 10. What's still open, in order

1. **G3 manual WSJT-X confirmation** (Captain's hands, per existing convention) --
   20 WAVs in `g3_full_grid_wav/` waiting.
2. **G4** -- at minimum, confirm the two `dt_s=0.0` WAVs decode with correct SNR/DT-adjacent
   sanity, ideally from a small live sample.
3. **sec.4's parts-vs-wall-clock tradeoff** -- your call.
4. **The S3 re-grid-vs-run-into-next-slot decision** (sec.0) -- still reserved, still
   blocks running the routine S3 sweep at all until resolved (it currently raises on
   parts 8/9).
5. Only after 1-3: the actual ~4.2 h (or shorter, per 3) S3b live run, under an HK-013
   supervisor with the midnight-rotation guard, on the Captain's hardware
   (Voicemeeter AUX Input routing) -- and only after **you pre-register the measurement**
   against the resolution reported here, per sec.5. **I have not pre-registered anything
   and have not run S3b live.**

**STOPPING HERE per sec.8 step 5.**
