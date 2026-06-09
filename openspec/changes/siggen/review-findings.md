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

## Resolution Checklist — Round 1

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

---

---

# Re-Review — Round 2

**Reviewer:** QA  
**Date:** 2026-06-10  
**Verdict:** RETURN FOR CHANGES — 2 required fixes before merge

**Implementer:** Developer  
**Resolved:** 2026-06-10  
**Resolution verdict:** RC-4 and RC-5 applied; informational notes N-6–N-8 acknowledged

**Context:** Round 1 fixes (RC-1, RC-2, RC-3) are correctly implemented and confirmed.
This round surfaces new findings from a full re-examination of the submitted implementation.

---

## Required Changes

These must be resolved and re-reviewed before the branch may merge to `main`.

---

### RC-4 — Bandlimited noise RMS is ~40% of the specified amplitude (High)

**File:** `qa/rr-study/siggen.py`, approximately line 337  
**Status:** ✅ Fixed

`render_noise` generates `rng.standard_normal(n_sig) * amp` (RMS ≈ `amp`), then
applies `_lowpass_fir`. The FIR lowpass removes all energy above `cutoff_hz`, reducing
the delivered RMS to approximately `amp × √(cutoff_hz / nyquist)`. At `cutoff_hz=4000`
and `sample_rate=48000` this is ≈ 0.41 × `amp` — a **~7.7 dB shortfall**.

The docstring states that `amplitude` is "interpreted as RMS / std-dev", which is only
true for the wideband case. Any operator who sets `cutoff_hz` and expects the delivered
RMS to equal `amplitude` will observe a significant SNR calibration error. This directly
affects D-002 investigation: any R&R run that uses `siggen.py` bandlimited noise to
characterise the SNR bias will have a ~8 dB miscalibration baked in.

**Fix:** Renormalise the filtered noise to the target RMS after `_lowpass_fir`:

```python
amp = _parse_amplitude(d)   # RMS / std-dev for noise
# … generate and filter …
noise = rng.standard_normal(n_sig) * amp
if cutoff_hz is not None:
    noise = _lowpass_fir(noise, float(cutoff_hz), int(sample_rate))
    # Renormalise: _lowpass_fir removes out-of-band energy, reducing RMS
    # below the requested amplitude.  Restore the target RMS.
    actual_rms = float(np.std(noise))
    if actual_rms > 0.0:
        noise = noise * (amp / actual_rms)
```

---

### RC-5 — `--duration` CLI flag is silently ignored in batch mode (Medium)

**File:** `qa/rr-study/siggen.py`, approximately line 701  
**Status:** ✅ Fixed

In the `if args.batch:` branch of `main()`, `cli_overrides` is populated with `out`,
`device`, and `sample_rate` — but `args.duration` is **never forwarded** as
`duration_s`. Running `python siggen.py --batch jobs.json --duration 30` has no effect
on any batch item; each item auto-computes its own duration from signal extents. No
warning or error is printed.

**Fix:** Add one line to the `cli_overrides` block:

```python
if args.out is not None:
    cli_overrides["out"] = args.out
if args.device is not None:
    cli_overrides["device"] = args.device
if args.rate is not None:
    cli_overrides["sample_rate"] = args.rate
if args.duration is not None:              # ← add this
    cli_overrides["duration_s"] = args.duration
```

---

## Informational Notes — Round 2

No code change required for any of these before merge.

---

### N-6 — `render_ft8` inner `except Exception` loses `signal[{idx}]` context for null fields (Low)

**File:** `qa/rr-study/siggen.py`, approximately line 392

RC-3 fixed `render_chirp` so that validation errors surface through `render_scene`'s
`except (KeyError, ValueError, TypeError)` handler, which attaches `signal[{idx}]`
context. The same fix was not applied to `render_ft8`'s inner `except Exception → sys.exit()`
block. If `"message"` is JSON `null`, `text = None` is assigned without error, then
`_encoder.encode_message(None, …)` raises a `TypeError` that is caught by the inner
handler and converted to `sys.exit()`. `SystemExit` bypasses the outer context-adding
handler. The error message is descriptive but lacks the `signal[{idx}]` prefix.

Consider replacing the inner `except Exception` with a narrower catch, or restructuring
so that field-validation errors raise `ValueError` before reaching the encoder call.

---

### N-7 — FT8 `duration_s` rejection fires at render time, not parse time (Low)

**File:** `qa/rr-study/siggen.py`, approximately line 365

The spec states that a `duration_s` field on an `ft8` descriptor is "an immediate parse
error." The check exists inside `render_ft8`, which is only called from `render_scene`'s
signal loop. If the offending ft8 signal is at position N, signals 0 through N−1 are
fully rendered (potentially several FT8 encodes) before the error surfaces and discards
all output. Moving the check to the pre-validation loop in `main()` (alongside the
existing `_parse_amplitude` validation) would honour the "parse error" guarantee and
give faster feedback:

```python
# in main(), before calling render_scene:
for i, sig in enumerate(signals):
    if sig.get("type") == "ft8" and "duration_s" in sig:
        sys.exit(
            f"ERROR: signal[{i}] ('ft8'): 'duration_s' must not be specified — "
            f"FT8 slot duration is fixed at 15.0 s (SLOT_LENGTH_S)."
        )
```

---

### N-8 — NaN buffer bypasses peak normalisation guard in `write_outputs` (Low)

**File:** `qa/rr-study/siggen.py`, approximately line 527

`_peak = float(np.max(np.abs(buffer)))` returns `NaN` if any sample is NaN.
`NaN > 0.0` is `False`, so the `else` branch executes and `buffer.astype(np.float32)`
(containing NaN) is passed to `sounddevice.play()`. PortAudio behaviour on NaN input
is platform-defined. No current renderer produces NaN under well-formed inputs, so this
is not reachable today. A one-line guard eliminates the exposure at negligible cost:

```python
if _peak > 0.0 and not math.isnan(_peak):
    playback = (buffer * (0.9 / _peak)).astype(np.float32)
else:
    playback = buffer.astype(np.float32)
```

---

## Resolution Checklist — Round 2

| ID   | Description                                                  | Status      |
|------|--------------------------------------------------------------|-------------|
| RC-4 | Renormalise bandlimited noise to target RMS after `_lowpass_fir` | ✅ Fixed |
| RC-5 | Forward `--duration` to `cli_overrides` in batch mode        | ✅ Fixed    |
| N-6  | `render_ft8` inner handler loses `signal[{idx}]` context     | ⬜ Acknowledged |
| N-7  | Move `ft8` `duration_s` check to pre-validation loop         | ⬜ Acknowledged |
| N-8  | Add `math.isnan` guard to `write_outputs` normalisation      | ⬜ Acknowledged |
