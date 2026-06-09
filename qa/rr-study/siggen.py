#!/usr/bin/env python3
"""General-purpose multi-signal audio scene renderer for OpenWSFZ QA.

Reads a JSONL scene file (or a batch JSON array), renders an arbitrary mix of
signals — sine, square, sawtooth, triangle, chirp, noise, ft8 — into a single
float64 buffer and routes the result to a WAV file, an audio output device, or
both simultaneously.  No FT8 encoder is loaded unless the scene contains at
least one signal of type ``ft8``.

Usage — single scene:
    python siggen.py SCENE_FILE [--out PATH] [--device NAME] [--rate HZ]
                                [--duration S]

Usage — batch mode:
    python siggen.py --batch BATCH_FILE [--out PATH] [--device NAME]
                                        [--rate HZ]

See ``docs/siggen-reference.md`` for the full operator reference.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from typing import Any

import numpy as np
from scipy import signal as _scipy_signal

# ---------------------------------------------------------------------------
# Package root — must run before any local imports.
# ---------------------------------------------------------------------------
_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ``synth.wavio`` and ``synth.channel._lowpass_fir`` are used at render time.
# NOTE: ``synth.encoder`` is NOT imported here (design D-5 — lazy import).
#       It is imported inside ``render_ft8()`` only.  Scenes with no ``ft8``
#       signals will never trigger the FT8 encode chain.
from synth.channel import _lowpass_fir   # noqa: E402
from synth import wavio                  # noqa: E402


# ---------------------------------------------------------------------------
# Amplitude helpers
# ---------------------------------------------------------------------------

def _parse_amplitude(d: dict) -> float:
    """Return the linear peak amplitude from a signal descriptor.

    Rules (design D-3):
    - ``amplitude`` (linear) — returned as-is.
    - ``level_dbfs`` (dBFS) — converted via ``10 ** (v / 20)``.
    - Neither → default ``1.0``.
    - Both → ``ValueError``.
    """
    has_amp = "amplitude" in d
    has_dbfs = "level_dbfs" in d
    if has_amp and has_dbfs:
        raise ValueError(
            "signal descriptor specifies both 'amplitude' and 'level_dbfs' — "
            "they are mutually exclusive"
        )
    if has_amp:
        return float(d["amplitude"])
    if has_dbfs:
        return 10.0 ** (float(d["level_dbfs"]) / 20.0)
    return 1.0


# ---------------------------------------------------------------------------
# JSONL scene file parser
# ---------------------------------------------------------------------------

def parse_scene(path: str) -> tuple[dict, list[dict]]:
    """Read a JSONL scene file and return ``(scene_config, signals)``.

    Rules (design D-1, D-2):
    - Blank lines are skipped.
    - Lines whose stripped form begins with ``#`` are skipped (comment syntax;
      this is a ``siggen.py``-specific pre-processing rule, not a JSON extension).
    - Each remaining line is parsed as a JSON object.
    - Objects with ``"type": "scene"`` are merged into ``scene_config``
      (last-wins for duplicates).
    - All other objects are appended to the signal list in order.
    """
    scene_config: dict = {}
    signals: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    sys.exit(
                        f"ERROR: {path}:{lineno}: JSON parse error — {exc}"
                    )
                if not isinstance(obj, dict):
                    sys.exit(
                        f"ERROR: {path}:{lineno}: expected a JSON object, "
                        f"got {type(obj).__name__}"
                    )
                if obj.get("type") == "scene":
                    scene_config.update(obj)
                else:
                    signals.append(obj)
    except OSError as exc:
        sys.exit(f"ERROR: cannot open scene file '{path}': {exc}")
    return scene_config, signals


def resolve_config(scene_config: dict, args: argparse.Namespace) -> dict:
    """Merge parsed scene config with CLI flag overrides.

    CLI flags always take precedence over scene-line values (design D-2).
    Validates that at least one output sink (``out`` or ``device``) is present.
    """
    config = dict(scene_config)

    # CLI overrides
    if args.out is not None:
        config["out"] = args.out
    if args.device is not None:
        config["device"] = args.device
    if args.rate is not None:
        config["sample_rate"] = args.rate
    if getattr(args, "duration", None) is not None:
        config["duration_s"] = args.duration

    # Defaults
    config.setdefault("sample_rate", 48000)
    config.setdefault("seed", 0)

    # Validate output sinks
    if not config.get("out") and not config.get("device"):
        sys.exit(
            "ERROR: no output sink specified. Provide at least one of:\n"
            "  --out PATH          (WAV file output)\n"
            "  --device NAME       (audio device output)\n"
            "  a \"type\":\"scene\" line in the scene file with an 'out' or "
            "'device' field."
        )

    return config


# ---------------------------------------------------------------------------
# Auto-duration computation (design D-7)
# ---------------------------------------------------------------------------

# Populated lazily the first time an ``ft8`` signal is encountered.
_FT8_SLOT_LENGTH_S: float | None = None


def _get_ft8_slot_length() -> float:
    """Return the FT8 slot length in seconds (lazy import from synth.constants)."""
    global _FT8_SLOT_LENGTH_S
    if _FT8_SLOT_LENGTH_S is None:
        from synth.constants import SLOT_LENGTH_S  # noqa: PLC0415
        _FT8_SLOT_LENGTH_S = SLOT_LENGTH_S
    return _FT8_SLOT_LENGTH_S


def _signal_end_s(d: dict) -> float:
    """Return the end time (seconds) of a signal descriptor."""
    start = float(d.get("start_s", 0.0))
    if d.get("type") == "ft8":
        return start + _get_ft8_slot_length()
    return start + float(d.get("duration_s", 0.0))


# ---------------------------------------------------------------------------
# Shared placement helper
# ---------------------------------------------------------------------------

def _place_signal(
    signal_samples: np.ndarray,
    start_s: float,
    n_samples: int,
    sample_rate: int,
) -> np.ndarray:
    """Place ``signal_samples`` into a zero-filled buffer of ``n_samples`` at ``start_s``.

    Signals that extend beyond the buffer boundary are truncated silently.
    """
    buf = np.zeros(n_samples, dtype=np.float64)
    start_idx = int(math.floor(start_s * sample_rate))
    if start_idx >= n_samples or start_idx < 0:
        return buf
    end_idx = start_idx + len(signal_samples)
    actual_end = min(end_idx, n_samples)
    take = actual_end - start_idx
    if take > 0:
        buf[start_idx:actual_end] = signal_samples[:take]
    return buf


# ---------------------------------------------------------------------------
# Signal renderers — primitive types (no FT8 dependency)
# ---------------------------------------------------------------------------

def render_sine(d: dict, n_samples: int, sample_rate: int) -> np.ndarray:
    """Render a continuous-phase sinusoid.

    Required fields: ``freq_hz``, ``start_s``, ``duration_s``.
    Optional: ``amplitude`` or ``level_dbfs`` (default 1.0), ``phase_deg`` (default 0).
    """
    amp = _parse_amplitude(d)
    freq = float(d["freq_hz"])
    start_s = float(d["start_s"])
    duration_s = float(d["duration_s"])
    phase_rad = math.radians(float(d.get("phase_deg", 0.0)))
    n_sig = int(math.ceil(duration_s * sample_rate))
    t = np.arange(n_sig, dtype=np.float64) / sample_rate
    sig = amp * np.sin(2.0 * math.pi * freq * t + phase_rad)
    return _place_signal(sig, start_s, n_samples, sample_rate)


def render_square(d: dict, n_samples: int, sample_rate: int) -> np.ndarray:
    """Render a square wave using ``scipy.signal.square``.

    Required fields: ``freq_hz``, ``start_s``, ``duration_s``.
    Optional: ``amplitude`` / ``level_dbfs`` (default 1.0),
              ``duty_cycle`` (0.0–1.0 exclusive, default 0.5).
    """
    amp = _parse_amplitude(d)
    freq = float(d["freq_hz"])
    start_s = float(d["start_s"])
    duration_s = float(d["duration_s"])
    duty_cycle = float(d.get("duty_cycle", 0.5))
    n_sig = int(math.ceil(duration_s * sample_rate))
    t = np.arange(n_sig, dtype=np.float64) / sample_rate
    sig = amp * _scipy_signal.square(2.0 * math.pi * freq * t, duty=duty_cycle)
    return _place_signal(sig, start_s, n_samples, sample_rate)


def render_sawtooth(d: dict, n_samples: int, sample_rate: int) -> np.ndarray:
    """Render a sawtooth wave using ``scipy.signal.sawtooth(width=1)``.

    Required fields: ``freq_hz``, ``start_s``, ``duration_s``.
    Optional: ``amplitude`` / ``level_dbfs`` (default 1.0).
    """
    amp = _parse_amplitude(d)
    freq = float(d["freq_hz"])
    start_s = float(d["start_s"])
    duration_s = float(d["duration_s"])
    n_sig = int(math.ceil(duration_s * sample_rate))
    t = np.arange(n_sig, dtype=np.float64) / sample_rate
    sig = amp * _scipy_signal.sawtooth(2.0 * math.pi * freq * t, width=1)
    return _place_signal(sig, start_s, n_samples, sample_rate)


def render_triangle(d: dict, n_samples: int, sample_rate: int) -> np.ndarray:
    """Render a triangle wave using ``scipy.signal.sawtooth(width=0.5)``.

    Required fields: ``freq_hz``, ``start_s``, ``duration_s``.
    Optional: ``amplitude`` / ``level_dbfs`` (default 1.0).
    """
    amp = _parse_amplitude(d)
    freq = float(d["freq_hz"])
    start_s = float(d["start_s"])
    duration_s = float(d["duration_s"])
    n_sig = int(math.ceil(duration_s * sample_rate))
    t = np.arange(n_sig, dtype=np.float64) / sample_rate
    sig = amp * _scipy_signal.sawtooth(2.0 * math.pi * freq * t, width=0.5)
    return _place_signal(sig, start_s, n_samples, sample_rate)


def render_chirp(d: dict, n_samples: int, sample_rate: int) -> np.ndarray:
    """Render a linear or logarithmic frequency-swept sinusoid.

    Required fields: ``freq_start_hz``, ``freq_end_hz``, ``start_s``, ``duration_s``.
    Optional: ``amplitude`` / ``level_dbfs`` (default 1.0),
              ``method`` — ``"linear"`` (default) or ``"logarithmic"``.

    Uses ``scipy.signal.chirp`` per spec.
    """
    amp = _parse_amplitude(d)
    f0 = float(d["freq_start_hz"])
    f1 = float(d["freq_end_hz"])
    start_s = float(d["start_s"])
    duration_s = float(d["duration_s"])
    method = d.get("method", "linear")
    if method not in ("linear", "logarithmic"):
        sys.exit(
            f"ERROR: chirp 'method' must be 'linear' or 'logarithmic', "
            f"got '{method}'"
        )
    n_sig = int(math.ceil(duration_s * sample_rate))
    t = np.arange(n_sig, dtype=np.float64) / sample_rate
    sig = amp * _scipy_signal.chirp(t, f0=f0, t1=duration_s, f1=f1, method=method)
    return _place_signal(sig, start_s, n_samples, sample_rate)


def render_noise(
    d: dict,
    n_samples: int,
    sample_rate: int,
    scene_config: dict,
) -> np.ndarray:
    """Render a burst of AWGN (white or bandlimited).

    Required fields: ``start_s``, ``duration_s``.
    Optional: ``amplitude`` / ``level_dbfs`` (default 1.0 — interpreted as RMS /
              std-dev, not peak, for noise signals),
              ``cutoff_hz`` (Kaiser FIR lowpass via ``synth.channel._lowpass_fir``),
              ``seed`` (overrides scene global ``seed``, default 0).

    The ``amplitude`` / ``level_dbfs`` value is used as the noise sample
    standard deviation (RMS), consistent with
    ``numpy.random.Generator.standard_normal`` scaling.
    """
    amp = _parse_amplitude(d)  # RMS / std-dev for noise
    start_s = float(d["start_s"])
    duration_s = float(d["duration_s"])
    cutoff_hz = d.get("cutoff_hz")
    seed = int(d.get("seed", scene_config.get("seed", 0)))
    n_sig = int(math.ceil(duration_s * sample_rate))
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n_sig) * amp
    if cutoff_hz is not None:
        noise = _lowpass_fir(noise, float(cutoff_hz), int(sample_rate))
    return _place_signal(noise, start_s, n_samples, sample_rate)


# ---------------------------------------------------------------------------
# Signal renderer — ft8 type (LAZY import — design D-5)
# ---------------------------------------------------------------------------
# ASSERTION: ``synth.encoder`` does NOT appear in the module-level import block
# of this file.  Only ``render_ft8()`` (below) may import it, and only at
# call time.  A scene with no ``ft8`` signal lines will never trigger an
# import of the FT8 encode chain.

def render_ft8(
    d: dict,
    n_samples: int,
    sample_rate: int,
    scene_config: dict,
) -> np.ndarray:
    """Render an FT8 message using ``synth.encoder`` (lazy import per design D-5).

    Required fields: ``message``, ``freq_hz``.
    Optional: ``amplitude`` / ``level_dbfs`` (default 1.0),
              ``start_s`` (default 0.0), ``dt_s`` (default 0.0).
    The ``duration_s`` field is NOT used (FT8 slot is always ``SLOT_LENGTH_S``
    seconds) and is rejected with an error if supplied.
    """
    if "duration_s" in d:
        sys.exit(
            "ERROR: 'ft8' signal descriptor must not include 'duration_s' — "
            "the FT8 slot duration is fixed at 15.0 s (SLOT_LENGTH_S). "
            "Remove the 'duration_s' field to avoid confusion."
        )

    # Lazy import: only triggered when the first ft8 signal is rendered.
    try:
        from synth import encoder as _encoder  # noqa: PLC0415
    except ImportError as exc:
        sys.exit(f"ERROR: cannot import synth.encoder — {exc}")

    text = d["message"]
    freq_hz = float(d["freq_hz"])
    amp = _parse_amplitude(d)
    start_s = float(d.get("start_s", 0.0))
    dt_s = float(d.get("dt_s", 0.0))

    try:
        clean = _encoder.encode_message(
            text,
            base_freq_hz=freq_hz,
            dt_s=dt_s,
            snr_db=None,          # always clean render; noise is added separately
            sample_rate_hz=sample_rate,
        )
    except Exception as exc:
        sys.exit(f"ERROR: could not encode FT8 message '{text}': {exc}")

    sig = amp * clean
    return _place_signal(sig, start_s, n_samples, sample_rate)


# ---------------------------------------------------------------------------
# Scene mixer (design D-4)
# ---------------------------------------------------------------------------

_PRIMITIVE_RENDERERS: dict[str, Any] = {
    "sine":     render_sine,
    "square":   render_square,
    "sawtooth": render_sawtooth,
    "triangle": render_triangle,
    "chirp":    render_chirp,
}
_ALL_SIGNAL_TYPES = sorted(_PRIMITIVE_RENDERERS) + ["noise", "ft8"]


def render_scene(signals: list[dict], config: dict) -> np.ndarray:
    """Mix all signals into a single float64 buffer.

    Buffer length is determined by ``config["duration_s"]`` when present;
    otherwise auto-computed as ``max(start_s + signal_duration)`` across all
    signal descriptors (design D-7).

    Mixing is a plain element-wise sum — no normalisation is applied here.
    Normalisation is performed downstream in :func:`write_outputs`.
    """
    sample_rate = int(config.get("sample_rate", 48000))

    # Determine total scene duration
    if "duration_s" in config:
        total_s = float(config["duration_s"])
    elif signals:
        total_s = max(_signal_end_s(d) for d in signals)
    else:
        total_s = 0.0

    n_samples = int(math.ceil(total_s * sample_rate))
    if n_samples <= 0:
        sys.exit(
            "ERROR: computed scene duration is zero or negative. "
            "Provide --duration or ensure at least one signal has "
            "start_s + duration_s > 0."
        )

    buf = np.zeros(n_samples, dtype=np.float64)

    for idx, d in enumerate(signals):
        sig_type = d.get("type", "")
        try:
            if sig_type == "ft8":
                contrib = render_ft8(d, n_samples, sample_rate, config)
            elif sig_type == "noise":
                contrib = render_noise(d, n_samples, sample_rate, config)
            elif sig_type in _PRIMITIVE_RENDERERS:
                contrib = _PRIMITIVE_RENDERERS[sig_type](d, n_samples, sample_rate)
            else:
                sys.exit(
                    f"ERROR: signal[{idx}]: unknown type '{sig_type}'. "
                    f"Supported types: {', '.join(_ALL_SIGNAL_TYPES)}"
                )
        except (KeyError, ValueError) as exc:
            sys.exit(f"ERROR: signal[{idx}] ({sig_type!r}): {exc}")

        buf += contrib

    return buf


# ---------------------------------------------------------------------------
# Device selection helper (mirrors harness/run_scenario.py pattern)
# ---------------------------------------------------------------------------

def _select_device(substring: str) -> int:
    """Return the sounddevice device index matching ``substring`` (case-insensitive).

    Exits with a non-zero code and prints available output devices if no match
    is found.
    """
    import sounddevice as sd  # noqa: PLC0415
    devices = sd.query_devices()
    matches = [
        (i, dev)
        for i, dev in enumerate(devices)
        if substring.lower() in dev["name"].lower()
        and dev["max_output_channels"] > 0
    ]
    if not matches:
        print(f"ERROR: no output device matching '{substring}'. Available output devices:")
        for i, dev in enumerate(devices):
            if dev["max_output_channels"] > 0:
                print(f"  [{i}] {dev['name']}")
        sys.exit(1)
    idx, _dev = matches[0]
    return idx


# ---------------------------------------------------------------------------
# Output routing (design D-4)
# ---------------------------------------------------------------------------

def write_outputs(buffer: np.ndarray, config: dict) -> None:
    """Route the mixed buffer to file and/or audio device.

    File output uses :func:`synth.wavio.write_wav` (16-bit PCM, 6 dB headroom
    normalisation).  Device output normalises to 0.9 peak amplitude and plays
    via ``sounddevice.play()`` (blocking).

    When both sinks are declared, the WAV file is written first, then playback
    begins.
    """
    sample_rate = int(config.get("sample_rate", 48000))
    out_path = config.get("out")
    device_name = config.get("device")

    # ── File output ──────────────────────────────────────────────────────────
    if out_path:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        wavio.write_wav(str(p), buffer, sample_rate_hz=sample_rate)
        duration_s = len(buffer) / sample_rate
        print(
            f"  Written: {p}  "
            f"({len(buffer)} samples @ {sample_rate} Hz, {duration_s:.3f} s)"
        )

    # ── Device output ─────────────────────────────────────────────────────────
    if device_name:
        import sounddevice as sd  # noqa: PLC0415
        dev_idx = _select_device(device_name)
        # Normalise to 0.9 peak before playback (mirrors run_scenario.py pattern).
        _peak = float(np.max(np.abs(buffer)))
        if _peak > 0.0:
            playback = (buffer * (0.9 / _peak)).astype(np.float32)
        else:
            playback = buffer.astype(np.float32)
        dev_name = sd.query_devices(dev_idx)["name"]
        print(f"  Playing on device [{dev_idx}] — {dev_name} …", end=" ", flush=True)
        try:
            sd.play(playback, samplerate=sample_rate, device=dev_idx, blocking=False)
            sd.wait()
        except sd.PortAudioError as exc:
            print(f"\nERROR: PortAudio playback failed: {exc}")
            sys.exit(1)
        print("done")


# ---------------------------------------------------------------------------
# Batch mode (design D-6)
# ---------------------------------------------------------------------------

def run_batch(batch_path: str, cli_overrides: dict) -> bool:
    """Process a JSON array of scene objects sequentially.

    Each element in the array is a scene object:
    - ``signals`` (required): list of signal descriptor objects.
    - ``out``, ``device``, ``sample_rate``, ``duration_s``, ``seed`` (optional).

    ``cli_overrides`` are applied over each item's own fields.  A failure in
    one item prints ``[item N] ERROR: <msg>`` and continues to the next
    (non-fatal batch semantics).  Returns ``True`` if all items succeeded,
    ``False`` if any item failed.
    """
    try:
        raw = pathlib.Path(batch_path).read_text(encoding="utf-8")
        items = json.loads(raw)
    except OSError as exc:
        sys.exit(f"ERROR: cannot open batch file '{batch_path}': {exc}")
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: cannot parse batch file '{batch_path}': {exc}")

    if not isinstance(items, list):
        sys.exit(
            f"ERROR: batch file must contain a JSON array, "
            f"got {type(items).__name__}"
        )

    all_ok = True
    for i, item in enumerate(items):
        print(f"\n[item {i}] processing …")
        try:
            if not isinstance(item, dict):
                raise ValueError(
                    f"batch item must be a JSON object, got {type(item).__name__}"
                )

            # Merge CLI overrides over item fields
            merged: dict = dict(item)
            merged.update({k: v for k, v in cli_overrides.items() if v is not None})
            merged.setdefault("sample_rate", 48000)
            merged.setdefault("seed", 0)

            signals: list[dict] = merged.pop("signals", [])
            if not isinstance(signals, list):
                raise ValueError("'signals' must be an array of signal descriptor objects")

            # Validate output sink
            if not merged.get("out") and not merged.get("device"):
                raise ValueError(
                    "no output sink: provide 'out' or 'device' in the batch "
                    "item or via CLI flags"
                )

            # Validate amplitude fields early (fail fast before rendering)
            for j, sig in enumerate(signals):
                _parse_amplitude(sig)

            buf = render_scene(signals, merged)
            write_outputs(buf, merged)
            print(f"[item {i}] OK")

        except SystemExit as exc:
            # render_scene / write_outputs can call sys.exit; catch so the
            # batch continues with the next item.
            msg = exc.code
            if isinstance(msg, int):
                msg = f"exit code {msg}"
            print(f"[item {i}] ERROR: {msg}")
            all_ok = False
        except Exception as exc:
            print(f"[item {i}] ERROR: {exc}")
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="siggen.py",
        description=(
            "General-purpose multi-signal audio scene renderer. "
            "Reads a JSONL scene file and mixes sine, square, sawtooth, "
            "triangle, chirp, noise, and ft8 signals into a WAV file and/or "
            "audio device output. See docs/siggen-reference.md for the full "
            "operator reference."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional: scene file (optional — mutually exclusive with --batch)
    parser.add_argument(
        "scene_file",
        nargs="?",
        metavar="SCENE_FILE",
        help="Path to JSONL scene file (mutually exclusive with --batch)",
    )

    # Output sinks
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="Output WAV file path (overrides scene 'out' field)",
    )
    parser.add_argument(
        "--device",
        metavar="NAME",
        default=None,
        help=(
            "Audio output device name substring, case-insensitive "
            "(overrides scene 'device' field)"
        ),
    )

    # Render parameters
    parser.add_argument(
        "--rate",
        type=int,
        metavar="HZ",
        default=None,
        help="Sample rate in Hz (default: 48000, or scene 'sample_rate')",
    )
    parser.add_argument(
        "--duration",
        type=float,
        metavar="S",
        default=None,
        help=(
            "Total scene duration in seconds "
            "(overrides scene 'duration_s'; default: auto from signals)"
        ),
    )

    # Batch mode
    parser.add_argument(
        "--batch",
        metavar="BATCH_FILE",
        default=None,
        help="Batch mode: JSON array of scene objects (mutually exclusive with SCENE_FILE)",
    )

    args = parser.parse_args()

    # Validate modes
    if args.batch and args.scene_file:
        parser.error("SCENE_FILE and --batch are mutually exclusive")
    if not args.batch and not args.scene_file:
        parser.error("provide either SCENE_FILE or --batch BATCH_FILE")

    if args.batch:
        # ── Batch mode ────────────────────────────────────────────────────────
        cli_overrides: dict[str, Any] = {}
        if args.out is not None:
            cli_overrides["out"] = args.out
        if args.device is not None:
            cli_overrides["device"] = args.device
        if args.rate is not None:
            cli_overrides["sample_rate"] = args.rate
        ok = run_batch(args.batch, cli_overrides)
        sys.exit(0 if ok else 1)

    else:
        # ── Single-scene mode ─────────────────────────────────────────────────
        scene_config, signals = parse_scene(args.scene_file)
        config = resolve_config(scene_config, args)

        # Validate amplitude fields before any rendering starts
        for i, sig in enumerate(signals):
            try:
                _parse_amplitude(sig)
            except ValueError as exc:
                sys.exit(f"ERROR: signal[{i}]: {exc}")

        n_sigs = len(signals)
        print(
            f"siggen: rendering '{args.scene_file}' "
            f"({n_sigs} signal{'s' if n_sigs != 1 else ''}) …"
        )
        buf = render_scene(signals, config)
        write_outputs(buf, config)
        print("siggen: done.")


if __name__ == "__main__":
    main()
