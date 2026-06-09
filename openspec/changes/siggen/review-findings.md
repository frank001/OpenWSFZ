# Code Review Findings — `feat/siggen`

**Reviewer:** QA  
**Date:** 2026-06-10  
**Verdict:** RETURN FOR CHANGES — 3 required fixes before merge

**Implementer:** Developer  
**Resolved:** 2026-06-10  
**Resolution verdict:** All 3 required changes applied; informational notes acknowledged

---

## Required Changes

These must be resolved and re-reviewed before the branch may merge to `main`.

---

### RC-1 — Correlated noise from shared RNG seed (Medium)

**File:** `qa/rr-study/siggen.py`, line 323  
**Status:** ✅ Fixed

Any two `noise` descriptors that omit a `seed` field both evaluate to `seed=0` and
independently construct `np.random.default_rng(0)`. They produce **identical** sample
sequences for the same `n_sig`. In a multi-noise scene the mixed noise floor is
perfectly correlated — not independent — silently biasing any SNR or decode-probability
measurement drawn from the scene.

**Fix:** Derive per-signal seeds from the global seed *and* the signal index so each
noise signal gets a distinct-but-deterministic seed:

```python
# line 323 — replace:
seed = int(d.get("seed", scene_config.get("seed", 0)))

# with (idx must be threaded into render_noise from render_scene):
base_seed = int(scene_config.get("seed", 0))
seed = int(d.get("seed", base_seed ^ (idx * 2654435761)))
```

`render_scene` already has `idx` in its loop; pass it to `render_noise` as an
additional argument (or via the descriptor dict under a reserved key).

---

### RC-2 — `TypeError` from `null` JSON field not caught; produces Python traceback (Low-Medium)

**File:** `qa/rr-study/siggen.py`, line 447  
**Status:** ✅ Fixed

`float(None)` raises `TypeError`, which is not a subclass of `KeyError` or
`ValueError`. A scene line such as `{"type":"sine","freq_hz":null,...}` escapes the
handler and prints an unformatted Python traceback to the terminal in single-scene
mode, with no `ERROR: signal[N]` prefix and a confusing exit.

**Fix:** Add `TypeError` to the handler:

```python
# line 447 — replace:
except (KeyError, ValueError) as exc:

# with:
except (KeyError, ValueError, TypeError) as exc:
```

---

### RC-3 — `render_chirp` method validation calls `sys.exit()` directly, losing signal-index context (Low)

**File:** `qa/rr-study/siggen.py`, line 291  
**Status:** ✅ Fixed

Every other parameter error from a renderer surfaces via `render_scene`'s
`except (KeyError, ValueError)` handler, which wraps it as
`ERROR: signal[{idx}] ('chirp'): …`. The invalid-`method` path calls `sys.exit()`
directly, producing an error with no signal index — unhelpful when a scene contains
multiple chirp signals.

**Fix:** Raise `ValueError` instead and let the existing handler add the context:

```python
# lines 291-294 — replace:
if method not in ("linear", "logarithmic"):
    sys.exit(
        f"ERROR: chirp 'method' must be 'linear' or 'logarithmic', "
        f"got '{method}'"
    )

# with:
if method not in ("linear", "logarithmic"):
    raise ValueError(
        f"'method' must be 'linear' or 'logarithmic', got {method!r}"
    )
```

---

## Informational Notes

No code change required for any of these before merge. They are recorded for the
developer's awareness and as candidates for a follow-up change.

---

### N-1 — `_lowpass_fir` imported as a private symbol (Fragility)

**File:** `qa/rr-study/siggen.py`, line 43

`from synth.channel import _lowpass_fir` imports a module-private symbol. If
`channel.py` is refactored, `siggen.py` acquires an `ImportError` at load time with
no graceful fallback. Consider promoting `_lowpass_fir` to the public API of
`synth.channel`, or re-implementing the three-line helper locally in `siggen.py`
with a comment pointing at the canonical version.

---

### N-2 — `level_dbfs` means **peak** for tones but **RMS** for noise (Documentation)

**File:** `qa/rr-study/siggen.py`, line 70

`_parse_amplitude` applies `10^(v/20)` identically for all signal types. For `sine`,
`chirp`, and `ft8`, the result is a *peak* linear amplitude. For `noise`, it is an
*RMS* (std-dev). This is correct and matches the spec, but `level_dbfs:-6` on a sine
and on a noise source do not produce equal loudness — the sine is ~3 dB louder in RMS.
A comment in `_parse_amplitude` pointing to the noise docstring would pre-empt the
most common operator confusion when building calibrated SNR scenes.

---

### N-3 — `sd.play(blocking=False)` + `KeyboardInterrupt` leaves device open (Low)

**File:** `qa/rr-study/siggen.py`, line 524

`sd.play(blocking=False)` starts background playback; `sd.wait()` blocks until done.
A `KeyboardInterrupt` during `sd.wait()` propagates upward leaving the stream open.
In batch mode, subsequent `sd.play()` calls in the same process may find the device
busy. `sounddevice` cleans up on process exit, so this is not a crash risk, but
using `blocking=True` would eliminate the window entirely.

---

### N-4 — `_select_device` duplicates `harness/run_scenario.py` (Reuse)

**File:** `qa/rr-study/siggen.py`, line 458

Both files implement identical case-insensitive substring matching with the same
error-output format. When the pattern evolves in one file, the other silently keeps
the old behaviour. Consolidate into `harness/common.py` as part of a future
synthesiser CLI improvement change (see R-004 in the spec).

---

### N-5 — `_place_signal` allocates N full zero-filled buffers per scene (Efficiency)

**File:** `qa/rr-study/siggen.py`, line 182

Each renderer calls `_place_signal`, which allocates a fresh `np.zeros(n_samples)`
array. `render_scene` then accumulates with `buf += contrib`. For a 12-signal S8
scene at 48 kHz / 15 s this allocates ~72 MB of float64 intermediates per item.
An `out` parameter to `_place_signal` would allow direct write-into-accumulator
semantics and reduce peak allocation to one buffer regardless of signal count.

---

## Resolution Checklist

| ID  | Description                              | Status |
|-----|------------------------------------------|--------|
| RC-1 | Correlated noise: per-signal seed derivation | ✅ Fixed |
| RC-2 | Add `TypeError` to `render_scene` handler   | ✅ Fixed |
| RC-3 | Raise `ValueError` in `render_chirp` method validation | ✅ Fixed |
| N-1  | `_lowpass_fir` private import — noted      | ✅ Acknowledged (future change) |
| N-2  | `level_dbfs` peak/RMS comment — noted      | ✅ Acknowledged |
| N-3  | `sd.play` blocking mode — noted            | ✅ Acknowledged (future change) |
| N-4  | `_select_device` duplication — noted       | ✅ Acknowledged (R-004 candidate) |
| N-5  | `_place_signal` buffer allocation — noted  | ✅ Acknowledged (future change) |
