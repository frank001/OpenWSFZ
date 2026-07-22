"""Generator driver for the OpenWSFZ R&R study harness.

Usage:
    python harness/run_scenario.py <scenario_json> [--device <name>] [--dry-run]

Reads a scenario JSON file, renders each (part × trial) signal via the clean-room
FT8 synthesiser, plays the PCM into an audio output device aligned to the FT8
15-second UTC cycle boundary, and writes injected-truth metadata to truth.csv in
the versioned run directory.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Resolve qa/rr-study as a package root so ``synth`` and ``harness`` are importable.
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import compute_seed, make_run_dir, normalise_slot, SLOT_SECONDS
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

# ── Playback constants ────────────────────────────────────────────────────────
_PLAYBACK_PEAK_LEVEL: float = 0.9   # target peak amplitude after normalisation;
                                     # keeps headroom below PortAudio's ±1.0 clip limit
_CYCLE_PREWARM_S: float = 0.5       # seconds before cycle boundary to wake and arm playback

# Half-cosine fade-out applied to the last _FADEOUT_DURATION_S seconds of every
# rendered slot.  The FT8 signal is fully transmitted by ~12.64 s (79 symbols ×
# 0.160 s/symbol); the fade window (14.8–15.0 s) falls entirely within the
# noise tail and cannot affect any symbol amplitude or decoder SNR estimate.
# Its purpose is to eliminate the step discontinuity when playback stops at the
# cycle boundary, which otherwise creates a brief broadband click in the
# VB-CABLE stream.
_FADEOUT_DURATION_S: float = 0.2    # seconds; half-cosine taper at end of slot

# ── S4 multi-signal frequency spread ─────────────────────────────────────────
_MULTI_SIGNAL_FREQ_MIN_HZ: float = 300.0   # lower bound of S4 station spread (Hz)
_MULTI_SIGNAL_FREQ_MAX_HZ: float = 2700.0  # upper bound of S4 station spread (Hz)

# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------

# Noise bandwidth for all rendered scenarios (Hz).
# Restricts the AWGN floor to a band matching a real SSB receiver's audio
# path, so 48 kHz playback is perceptually realistic and WSJT-X's noise
# floor estimator sees a representative spectrum.
# Constraints: must be > 2700 Hz (FT8 audio ceiling); must not be a harmonic
# of the 1500 Hz nominal centre frequency (harmonics: 3000, 4500, 6000 Hz…).
_NOISE_CUTOFF_HZ: float = 4700.0


def _load_messages(scenarios_dir: Path) -> dict[str, str]:
    """Load study-messages.json and return {msg_id: text}."""
    msg_file = scenarios_dir / "study-messages.json"
    if not msg_file.exists():
        sys.exit(f"ERROR: study-messages.json not found: {msg_file}")
    try:
        data = json.loads(msg_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: cannot parse study-messages.json: {exc}")
    return {m["id"]: m["text"] for m in data.get("messages", [])}


def _load_scenario(path: Path, messages: dict[str, str]) -> dict:
    """Load and validate a scenario JSON file.

    Returns the scenario dict augmented with a ``message_texts`` key that maps
    each message_id to its text.
    """
    if not path.exists():
        sys.exit(f"ERROR: scenario file not found: {path}")
    try:
        scenario = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: cannot parse scenario file: {path} — {exc}")

    for field in ("id", "trials"):
        if field not in scenario:
            sys.exit(f"ERROR: scenario file missing required field '{field}': {path}")
    # S8 uses a top-level 'signals' array instead of 'parts'; a linked-pair
    # scenario (rr-linked-cycle-effectiveness-scenario) uses a top-level
    # 'pairs' array instead of both; all others require 'parts'.
    if (scenario.get("id") != "S8"
            and "parts" not in scenario
            and "pairs" not in scenario):
        sys.exit(f"ERROR: scenario file missing required field 'parts' (or 'pairs'): {path}")

    # Resolve message texts
    msg_ids = scenario.get("message_ids") or []
    msg_pool = scenario.get("message_pool") or msg_ids
    # Pairs scenarios nest their msg_ids under pairs[].announce/reference
    # rather than a flat message_ids/message_pool list (design D2).
    for pair in scenario.get("pairs") or []:
        for half in ("announce", "reference"):
            mid = pair.get(half, {}).get("msg_id")
            if mid and mid not in msg_pool:
                msg_pool = [*msg_pool, mid]
    resolved = {}
    for mid in msg_pool:
        if mid not in messages:
            sys.exit(f"ERROR: message id '{mid}' not found in study-messages.json")
        resolved[mid] = messages[mid]
    scenario["message_texts"] = resolved
    return scenario


# ---------------------------------------------------------------------------
# Device selection
# ---------------------------------------------------------------------------

def _select_device(substring: str):
    """Return the sounddevice device index/name matching ``substring`` (case-insensitive).

    Exits 1 with an available-device list if no match is found.
    """
    import sounddevice as sd
    devices = sd.query_devices()
    matches = [
        (i, d) for i, d in enumerate(devices)
        if substring.lower() in d["name"].lower() and d["max_output_channels"] > 0
    ]
    if not matches:
        print(f"ERROR: no output device matching '{substring}'. Available output devices:")
        for i, d in enumerate(devices):
            if d["max_output_channels"] > 0:
                print(f"  [{i}] {d['name']}")
        sys.exit(1)
    idx, dev = matches[0]
    return idx


# ---------------------------------------------------------------------------
# FT8 cycle boundary alignment
# ---------------------------------------------------------------------------

def _next_cycle_boundary() -> float:
    """Return the Unix timestamp of the next UTC second divisible by 15."""
    now = time.time()
    # Whole-second portion
    now_s = int(now)
    rem = now_s % SLOT_SECONDS
    if rem == 0:
        # Exactly on a boundary — advance to the *next* one so we don't try to
        # play into a cycle that's already started.
        return float(now_s + SLOT_SECONDS)
    return float(now_s + (SLOT_SECONDS - rem))


def _wait_for_cycle(boundary_ts: float) -> datetime:
    """Sleep until 500 ms before *boundary_ts*, then return the cycle UTC datetime."""
    target = boundary_ts - _CYCLE_PREWARM_S
    remaining = target - time.time()
    if remaining > 0:
        time.sleep(remaining)
    cycle_utc = datetime.fromtimestamp(boundary_ts, tz=timezone.utc).replace(microsecond=0)
    return cycle_utc


# ---------------------------------------------------------------------------
# PCM rendering — S1/S2/S3 (single signal per slot)
# ---------------------------------------------------------------------------

def _render_single(scenario: dict, part: dict, trial_index: int,
                   seed: int) -> "numpy.ndarray":
    """Render a single-message part (S1, S1b, S2, S3, S11) using the clean-room synthesiser.

    The signal is encoded clean (no noise), then **wideband** AWGN is added
    (no ``noise_cutoff_hz``).  Single-signal scenarios intentionally use wideband
    noise for the following reason: libft8's noise floor estimator does not handle
    bandlimited noise reliably.  When noise is hard-rolled off by the Kaiser FIR
    (as it is in the multi-signal path), the estimator occasionally returns a
    wildly incorrect noise floor — producing SNR readings ~15 dB below the true
    value in roughly one in four trials (D-003).  Wideband noise presents a flat
    spectrum that the estimator handles correctly, yielding zero outliers and
    excellent GR&R repeatability (σ² ≈ 0.15, ndc = 11 in the 4b3a4ca baseline).

    The noise cutoff (``_NOISE_CUTOFF_HZ``) is preserved for multi-signal scenarios
    (S4, S7, S8) where perceptual realism matters and the shared-floor mixer is
    used; it is not applied here.

    rr-linked-cycle-effectiveness-scenario (D1 path 1, S11): a scenario file
    may set a top-level ``"message_kind": "type4"`` to render its message via
    the Type-4 "CQ <nonstandard callsign>" packer instead of the standard
    Type-1 packer — everything else about this function (noise model, dt/freq
    handling) is identical and message-type-agnostic. Absent from S1/S1b/S2/S3
    (all standard-message scenarios), so they are unaffected.
    """
    from synth import channel, encoder

    fixed = scenario.get("fixed", {})
    msg_ids = list(scenario["message_texts"].keys())
    # S1/S1b/S2/S3/S11 use only the first message_id
    text = scenario["message_texts"][msg_ids[0]]

    base_freq_hz = part.get("base_freq_hz", fixed.get("base_freq_hz", 1500.0))
    dt_s = part.get("dt_s", fixed.get("dt_s", 0.0))
    snr_db = part.get("snr_db", fixed.get("snr_db", 0.0))

    if scenario.get("message_kind") == "type4":
        tokens = text.strip().split()
        if len(tokens) != 2 or tokens[0].upper() != "CQ":
            sys.exit(
                f"ERROR: Type-4 message {text!r} must be of the form 'CQ <callsign>' "
                f"(scenario {scenario.get('id')!r} sets message_kind='type4')"
            )
        clean = encoder.encode_message_type4(
            tokens[1],
            base_freq_hz=float(base_freq_hz),
            dt_s=float(dt_s),
            snr_db=None,
            sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        )
        return channel.add_noise(clean, float(snr_db), seed,
                                 sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)

    clean = encoder.encode_message(
        text,
        base_freq_hz=float(base_freq_hz),
        dt_s=float(dt_s),
        snr_db=None,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
    )
    # Wideband noise — no noise_cutoff_hz.  See docstring.
    return channel.add_noise(clean, float(snr_db), seed,
                             sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)


# ---------------------------------------------------------------------------
# PCM rendering — S4 (multiple simultaneous signals)
# ---------------------------------------------------------------------------

def _render_multi(scenario: dict, part: dict, trial_index: int,
                  seed: int) -> "tuple[numpy.ndarray, list[dict]]":
    """Render a multi-signal density part (S4) over one shared band-noise floor.

    Stations are spread evenly across 300–2700 Hz and scaled by their relative
    SNR; a single seeded noise floor is added once (see
    :func:`synth.channel.mix_to_shared_floor`) — not one floor per station.

    Returns ``(mixed_samples, signals_meta)`` where ``signals_meta`` is a list
    of ``{message_text, freq_hz, dt_s, snr_db}`` dicts, one per signal, used to
    write one truth row PER SIGNAL (rr-density-qrm-scenario) so the matcher
    scores each message independently instead of pooling the whole cycle into
    a single "matched any one" outcome. Mirrors ``_render_band_scene`` (S8) and
    ``_render_compound`` (S7), which already do this correctly.
    """
    from synth import channel, encoder

    msg_pool = list(scenario["message_texts"].values())
    n_signals = part["n_signals"]
    snr_db_set = part["snr_db_set"]

    # Spread frequencies evenly across 300–2700 Hz
    freq_min, freq_max = _MULTI_SIGNAL_FREQ_MIN_HZ, _MULTI_SIGNAL_FREQ_MAX_HZ
    if n_signals == 1:
        freqs = [1500.0]
    else:
        freqs = [freq_min + i * (freq_max - freq_min) / (n_signals - 1)
                 for i in range(n_signals)]

    clean_signals = []
    snr_list = []
    signals_meta: list[dict] = []
    for i in range(n_signals):
        text = msg_pool[i % len(msg_pool)]
        snr_db = float(snr_db_set[i % len(snr_db_set)])
        clean_signals.append(encoder.encode_message(
            text,
            base_freq_hz=freqs[i],
            dt_s=0.0,
            snr_db=None,  # clean render; the floor is added once by the mixer
            sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        ))
        snr_list.append(snr_db)
        signals_meta.append({
            "message_text": text,
            "freq_hz":      freqs[i],
            "dt_s":         0.0,
            "snr_db":       snr_db,
        })

    mixed = channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
                                        noise_cutoff_hz=_NOISE_CUTOFF_HZ)
    return mixed, signals_meta


# ---------------------------------------------------------------------------
# PCM rendering — S8 (realistic band scene)
# ---------------------------------------------------------------------------

def _render_band_scene(scenario: dict,
                       seed: int) -> "tuple[numpy.ndarray, list[dict]]":
    """Render the S8 fixed band-scene: all 12 stations mixed into one slot.

    Each entry in ``scenario["signals"]`` carries ``message_text``, ``freq_hz``,
    ``snr_db``, and ``dt_s``.  Stations are encoded clean, scaled by their
    relative ``snr_db``, summed, and given ONE shared seeded AWGN floor via
    :func:`synth.channel.mix_to_shared_floor` — the same model used by S7.

    Returns ``(mixed_samples, signals_meta)`` where ``signals_meta`` is a list
    of ``{message_text, freq_hz, dt_s, snr_db, station}`` dicts, one per signal,
    used to write one truth row PER SIGNAL so the matcher scores each independently.
    """
    from synth import channel, encoder

    signals = scenario.get("signals", [])
    if not signals:
        raise ValueError("S8 scenario has no 'signals' array")

    clean_signals: list = []
    snr_list: list[float] = []
    signals_meta: list[dict] = []

    for s in signals:
        text     = s["message_text"]
        freq_hz  = float(s["freq_hz"])
        dt_s     = float(s["dt_s"])
        snr_db   = float(s["snr_db"])
        station  = s.get("station", "?")
        clean_signals.append(encoder.encode_message(
            text,
            base_freq_hz=freq_hz,
            dt_s=dt_s,
            snr_db=None,  # clean render; the floor is added once by the mixer
            sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        ))
        snr_list.append(snr_db)
        signals_meta.append({
            "message_text": text,
            "freq_hz":      freq_hz,
            "dt_s":         dt_s,
            "snr_db":       snr_db,
            "station":      station,
        })

    mixed = channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
                                        noise_cutoff_hz=_NOISE_CUTOFF_HZ)
    return mixed, signals_meta


# ---------------------------------------------------------------------------
# PCM rendering — S7 (compounding / co-channel overlap)
# ---------------------------------------------------------------------------

def _render_compound(scenario: dict, part: dict,
                     seed: int) -> "tuple[numpy.ndarray, list[dict]]":
    """Render an S7 compounding part: 2–3 stations overlapping in freq/time.

    Each station carries its own (freq_hz, dt_s, snr_db). They are rendered
    *clean*, scaled by their relative SNR, summed, and given ONE shared seeded
    noise floor (see :func:`synth.channel.mix_to_shared_floor`) — the physical
    "compounding" of co-channel transmissions arriving at a single receiver.
    Because snr_db now sets relative *strength*, capture pairs (e.g. 0 / -10 dB)
    really differ in level, and an N-stack does not inflate the noise floor.

    Returns ``(mixed_samples, signals_meta)`` where ``signals_meta`` is a list
    of ``{message_text, freq_hz, dt_s, snr_db}`` dicts, one per signal, used to
    write one truth row PER SIGNAL so the matcher scores each independently.
    """
    import numpy as np
    from synth import channel, encoder

    signals = part.get("signals", [])
    if not signals:
        raise ValueError(f"S7 part {part.get('part_index')} has no 'signals'")

    clean_signals: list = []
    snr_list: list[float] = []
    signals_meta: list[dict] = []

    for s in signals:
        msg_id = s["msg_id"]
        if msg_id not in scenario["message_texts"]:
            sys.exit(f"ERROR: S7 references unknown message id '{msg_id}'")
        text = scenario["message_texts"][msg_id]
        freq_hz = float(s["freq_hz"])
        dt_s = float(s["dt_s"])
        snr_db = float(s["snr_db"])
        clean_signals.append(encoder.encode_message(
            text,
            base_freq_hz=freq_hz,
            dt_s=dt_s,
            snr_db=None,  # clean render; the floor is added once by the mixer
            sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        ))
        snr_list.append(snr_db)
        signals_meta.append({
            "message_text": text,
            "freq_hz": freq_hz,
            "dt_s": dt_s,
            "snr_db": snr_db,
        })

    mixed = channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
                                        noise_cutoff_hz=_NOISE_CUTOFF_HZ)
    return mixed, signals_meta


# ---------------------------------------------------------------------------
# PCM rendering — S5 (noise-only / signal-free)
# ---------------------------------------------------------------------------

def _render_noise(part: dict, seed: int) -> "numpy.ndarray":
    """Render a signal-free noise buffer for S5 false-positive tests."""
    import numpy as np

    sample_rate = DEFAULT_SAMPLE_RATE_HZ
    n_samples = int(sample_rate * SLOT_SECONDS)
    rng = np.random.default_rng(seed)
    noise_type = part.get("noise_type", "awgn")
    level_dbfs = part.get("level_dbfs", -20)

    # Convert dBFS to linear amplitude (0 dBFS = peak amplitude 1.0).
    # We interpret level_dbfs as RMS level: amplitude = 10^(level_dbfs/20).
    amplitude = 10.0 ** (level_dbfs / 20.0)

    if noise_type == "awgn":
        samples = rng.standard_normal(n_samples) * amplitude
    elif noise_type == "steady_carrier":
        freq_hz = float(part.get("carrier_freq_hz", 1500.0))
        t = np.linspace(0, 15.0, n_samples, endpoint=False)
        samples = amplitude * np.sin(2.0 * np.pi * freq_hz * t)
    elif noise_type == "multi_carrier":
        freqs = part.get("carrier_freqs_hz", [1500.0])
        t = np.linspace(0, 15.0, n_samples, endpoint=False)
        samples = np.zeros(n_samples, dtype="float32")
        per_amp = amplitude / len(freqs)
        for f in freqs:
            samples += per_amp * np.sin(2.0 * np.pi * float(f) * t)
    else:
        # Unknown noise type — fall back to AWGN
        print(f"WARNING: unknown noise_type '{noise_type}'; using AWGN", file=sys.stderr)
        samples = rng.standard_normal(n_samples) * amplitude

    return samples.astype("float32")


# ---------------------------------------------------------------------------
# PCM rendering — linked-pair scenario (rr-linked-cycle-effectiveness-scenario)
# ---------------------------------------------------------------------------

def _render_pair_announce(scenario: dict, announce: dict, seed: int) -> tuple:
    """Render the Type-4 "CQ <nonstandard callsign>" half of a linked pair.

    The announce message's stored text (study-messages.json) must be of the
    form "CQ <CALLSIGN>" — the harness extracts <CALLSIGN> and packs it via
    the Type-4 packer (`encoder.encode_message_type4`), NOT the standard
    Type-1 packer used everywhere else in this harness.

    Returns (samples, text, freq_hz, snr_db, callsign).
    """
    from synth import channel, encoder

    text = scenario["message_texts"][announce["msg_id"]]
    tokens = text.strip().split()
    if len(tokens) != 2 or tokens[0].upper() != "CQ":
        sys.exit(
            f"ERROR: Type-4 announce message {text!r} (msg_id={announce['msg_id']!r}) "
            "must be of the form 'CQ <callsign>'"
        )
    callsign = tokens[1]

    freq_hz = float(announce.get("freq_hz", 1500.0))
    dt_s = float(announce.get("dt_s", 0.0))
    snr_db = float(announce.get("snr_db", 0.0))

    clean = encoder.encode_message_type4(
        callsign,
        base_freq_hz=freq_hz,
        dt_s=dt_s,
        snr_db=None,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
    )
    samples = channel.add_noise(clean, snr_db, seed, sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)
    return samples, text, freq_hz, snr_db, callsign


def _render_pair_reference(scenario: dict, reference: dict, seed: int) -> tuple:
    """Render the standard-message hash-reference half of a linked pair.

    This is an ordinary Type 1/2/3 message (e.g. "Q1TST Q0ABCDEF RR73")
    rendered exactly like any S1/S2-style single signal — the nonstandard
    callsign's hash-sub-range packing (task 1.3) is transparent to the
    caller here; no Type-4-specific handling is needed for this half.

    Returns (samples, text, freq_hz, snr_db).
    """
    from synth import channel, encoder

    text = scenario["message_texts"][reference["msg_id"]]
    freq_hz = float(reference.get("freq_hz", 1500.0))
    dt_s = float(reference.get("dt_s", 0.0))
    snr_db = float(reference.get("snr_db", 0.0))

    clean = encoder.encode_message(
        text,
        base_freq_hz=freq_hz,
        dt_s=dt_s,
        snr_db=None,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
    )
    samples = channel.add_noise(clean, snr_db, seed, sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)
    return samples, text, freq_hz, snr_db


def _finalize_playback_samples(samples: "numpy.ndarray") -> "numpy.ndarray":
    """Cast to float32, peak-normalise to ±_PLAYBACK_PEAK_LEVEL, and apply the
    half-cosine fade-out — the same finishing steps every rendered slot in
    the main loop already applies (extracted here so the pairs path reuses
    them verbatim instead of duplicating the logic; see the main loop's
    inline comments for why each step exists).
    """
    import numpy as np

    samples = samples.astype("float32")
    peak = float(np.max(np.abs(samples)))
    if peak > 0.0:
        samples = (samples * (_PLAYBACK_PEAK_LEVEL / peak)).astype("float32")

    n_fade = int(_FADEOUT_DURATION_S * DEFAULT_SAMPLE_RATE_HZ)
    if 0 < n_fade <= len(samples):
        t = np.linspace(0.0, 1.0, n_fade, endpoint=True)
        fade_env = (0.5 * (1.0 + np.cos(np.pi * t))).astype("float32")
        samples[-n_fade:] *= fade_env
    return samples


# ---------------------------------------------------------------------------
# --dump-wav-dir: persist rendered slots as 12 kHz mono WAVs (D-001 param sweep)
# ---------------------------------------------------------------------------

# The offline FT8 decoder (OpenWSFZ.Ft8.Ft8Decoder) requires exactly 12 kHz mono
# 16-bit PCM, 180 000 samples/slot (15 s × 12 000 Hz). Rendered slots are 48 kHz
# (DEFAULT_SAMPLE_RATE_HZ), so each dumped slot is decimated 48 → 12 kHz with an
# anti-aliasing polyphase filter before writing.
_DUMP_SAMPLE_RATE_HZ = 12_000
_DUMP_SLOT_SAMPLES = _DUMP_SAMPLE_RATE_HZ * SLOT_SECONDS  # 180 000


def _dump_slot_wav(dump_dir: str, scenario_id: str, part_index: int,
                   trial_index: int, seed: int,
                   samples: "numpy.ndarray") -> None:
    """Write one rendered slot's PCM to ``dump_dir`` as a 12 kHz mono int16 WAV.

    The filename encodes (scenario, part, trial, seed) verbatim from the truth.csv
    key columns (``_append_truth`` writes the same fields) so each WAV pairs back to
    its truth row(s) with no separate index. Purely additive side effect — the caller
    still plays/does whatever it would have with ``samples`` unchanged.
    """
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly

    out_dir = Path(dump_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 48 kHz → 12 kHz (down=4) with the polyphase anti-alias FIR resample_poly applies.
    twelve = resample_poly(np.asarray(samples, dtype="float64"), up=1, down=4)

    # Guarantee the decoder's exact-length contract (pad tail with zeros / truncate).
    if len(twelve) < _DUMP_SLOT_SAMPLES:
        twelve = np.concatenate([twelve, np.zeros(_DUMP_SLOT_SAMPLES - len(twelve))])
    elif len(twelve) > _DUMP_SLOT_SAMPLES:
        twelve = twelve[:_DUMP_SLOT_SAMPLES]

    # Float [-1, 1] → int16, matching WavReader.cs's (s / 32768.0f) inverse.
    clipped = np.clip(twelve, -1.0, 1.0)
    pcm16 = np.round(clipped * 32767.0).astype("<i2")

    name = f"{scenario_id}_p{part_index:03d}_t{trial_index:03d}_s{seed}.wav"
    wavfile.write(str(out_dir / name), _DUMP_SAMPLE_RATE_HZ, pcm16)


def _play_samples(samples: "numpy.ndarray", args: argparse.Namespace,
                  device_idx, label: str) -> None:
    """Wait is the CALLER's job (cycle alignment); this only renders/plays.

    Mirrors the main loop's existing dry-run/live playback branch verbatim
    (see the main loop for the identical PortAudio error-handling path).
    """
    if args.dry_run:
        print(f"{label} [DRY RUN] would play {len(samples)} samples at 48 kHz")
        return
    import sounddevice as sd
    try:
        sd.play(samples, samplerate=DEFAULT_SAMPLE_RATE_HZ, device=device_idx, blocking=False)
        sd.wait()
    except sd.PortAudioError as exc:
        print(f"\nERROR: PortAudio playback failed: {exc}")
        print("Available output devices:")
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                print(f"  [{i}] {d['name']}")
        sys.exit(1)
    print(f"{label} done")


def _cycle_boundary_utc(args: argparse.Namespace) -> datetime:
    """Wait for (or, in --dry-run, snap to) the next FT8 cycle boundary and
    return its UTC datetime — shared alignment step for every play in a pair
    (announce, silent intervening cycles, and reference alike)."""
    if args.dry_run:
        now_s = int(time.time())
        snap = now_s - (now_s % SLOT_SECONDS)
        return datetime.fromtimestamp(snap, tz=timezone.utc).replace(microsecond=0)
    boundary_ts = _next_cycle_boundary()
    return _wait_for_cycle(boundary_ts)


def _run_pairs(scenario: dict, run_dir: Path, args: argparse.Namespace,
              device_idx, qa_rr_root: Path) -> None:
    """Play every (pair × trial) of a linked-pair scenario (design D2).

    For each pair: play `announce` at cycle N, wait `gap_cycles - 1` silent
    intervening cycles, play `reference` at cycle N + gap_cycles, then write
    ONE truth row covering the whole pair (both halves' truth fields plus
    resolved_expected) — see _PAIR_TRUTH_EXTRA_COLUMNS.
    """
    import numpy as np

    scenario_id = scenario["id"]
    pairs = scenario["pairs"]
    n_trials = scenario["trials"]
    silence = np.zeros(int(DEFAULT_SAMPLE_RATE_HZ * SLOT_SECONDS), dtype="float32")

    total = len(pairs) * n_trials
    played = 0

    for pair in pairs:
        pair_index = pair["pair_index"]
        announce = pair["announce"]
        reference = pair["reference"]
        gap_cycles = int(reference.get("gap_cycles", 1))
        if gap_cycles < 1:
            sys.exit(f"ERROR: pair {pair_index} gap_cycles must be >= 1, got {gap_cycles}")

        for trial_index in range(n_trials):
            ann_seed = compute_seed(f"{scenario_id}:announce", pair_index, trial_index)
            ref_seed = compute_seed(f"{scenario_id}:reference", pair_index, trial_index)

            ann_samples, ann_text, ann_freq, ann_snr, callsign = _render_pair_announce(
                scenario, announce, ann_seed
            )
            ann_samples = _finalize_playback_samples(ann_samples)
            ref_samples, ref_text, ref_freq, ref_snr = _render_pair_reference(
                scenario, reference, ref_seed
            )
            ref_samples = _finalize_playback_samples(ref_samples)

            label = (
                f"[{scenario_id}] Pair {pair_index} Trial {trial_index + 1}/{n_trials} "
                f"gap={gap_cycles}"
            )
            print(f"{label} — announce …", end=" ", flush=True)
            ann_cycle_utc = _cycle_boundary_utc(args)
            _play_samples(ann_samples, args, device_idx, label="  announce")

            for k in range(gap_cycles - 1):
                _cycle_boundary_utc(args)
                _play_samples(silence, args, device_idx, label=f"  silence ({k + 1}/{gap_cycles - 1})")

            ref_cycle_utc = _cycle_boundary_utc(args)
            _play_samples(ref_samples, args, device_idx, label="  reference")

            ann_cycle_str = ann_cycle_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            ref_cycle_str = ref_cycle_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            _append_pair_truth(run_dir, {
                "scenario_id": scenario_id,
                "part_index": pair_index,
                "trial_index": trial_index,
                "seed": ann_seed,
                "true_snr_db": "",
                "true_dt_s": "",
                "true_freq_hz": "",
                "message_text": f"{ann_text}; {ref_text}",
                "cycle_utc": ann_cycle_str,
                "gap_cycles": gap_cycles,
                "resolved_expected": True,
                "announce_text": ann_text,
                "announce_freq_hz": ann_freq,
                "announce_snr_db": ann_snr,
                "announce_cycle_utc": ann_cycle_str,
                "reference_text": ref_text,
                "reference_freq_hz": ref_freq,
                "reference_snr_db": ref_snr,
                "reference_cycle_utc": ref_cycle_str,
                "resolved_callsign": callsign,
                "unresolved_placeholder": UNRESOLVED_CALLSIGN_PLACEHOLDER,
            })
            played += 1

    truth_rel = (run_dir / "truth.csv").relative_to(qa_rr_root)
    print(
        f"\nScenario {scenario_id} complete — {played} pairs injected "
        f"({total} expected). Truth: {truth_rel}"
    )


# ---------------------------------------------------------------------------
# Truth CSV logging
# ---------------------------------------------------------------------------

_TRUTH_COLUMNS = [
    "scenario_id", "part_index", "trial_index", "seed",
    "true_snr_db", "true_dt_s", "true_freq_hz", "message_text", "cycle_utc",
]

# rr-linked-cycle-effectiveness-scenario (design D2/D3, spec: "Harness writes
# one truth row per pair, not one per part"): extra columns for the
# linked-pair truth-row schema, appended ALONGSIDE the existing columns above
# (never replacing them — existing per-part rows leave these blank via
# csv.DictWriter's restval). A pair row reuses "part_index" for pair_index
# and "cycle_utc"/"message_text" for the announce half (for continuity with
# the existing per-part convention), and carries both halves' full truth plus
# the resolution-scoring fields in the columns below.
_PAIR_TRUTH_EXTRA_COLUMNS = [
    "gap_cycles", "resolved_expected",
    "announce_text", "announce_freq_hz", "announce_snr_db", "announce_cycle_utc",
    "reference_text", "reference_freq_hz", "reference_snr_db", "reference_cycle_utc",
    "resolved_callsign", "unresolved_placeholder",
]
_TRUTH_COLUMNS = _TRUTH_COLUMNS + _PAIR_TRUTH_EXTRA_COLUMNS

# Placeholder text ft8_lib's lookup_callsign() emits for an unresolved hash
# (confirmed by inspection of the vendored ft8_lib submodule's git history —
# message.c's lookup_callsign: `strcpy(callsign, "<...>");` — a real,
# already-shipped protocol/reference-implementation constant, not a guess).
UNRESOLVED_CALLSIGN_PLACEHOLDER = "<...>"


def _append_truth(run_dir: Path, row: dict) -> None:
    """Append one row to truth.csv; write header only if creating the file."""
    truth_path = run_dir / "truth.csv"
    write_header = not truth_path.exists()
    with open(truth_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TRUTH_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _append_pair_truth(run_dir: Path, row: dict) -> None:
    """Append one linked-pair truth row (see _PAIR_TRUTH_EXTRA_COLUMNS) to truth.csv.

    Shares truth.csv with the per-part schema (same file, superset of
    columns) rather than a separate file, so a single run directory holds one
    complete truth record regardless of scenario shape.
    """
    _append_truth(run_dir, row)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _run(args: argparse.Namespace) -> None:
    scenario_path = Path(args.scenario_json)
    scenarios_dir = scenario_path.parent

    messages = _load_messages(scenarios_dir)
    scenario = _load_scenario(scenario_path, messages)

    scenario_id: str = scenario["id"]

    # S3b negative-DT playback is not yet implemented.  The synthesiser clamps
    # negative dt_s to zero, so every part would render as DT=0 and produce
    # near-100% decode rates — the exact opposite of what the study measures.
    # Remove this guard once the early-playback timing is wired up (subtract
    # |dt_s| seconds from _next_cycle_boundary() before arming playback, and
    # allow the modulator to shift energy into the tail of the previous slot).
    # See harness_note in scenarios/s3b-dt-boundary.json.
    if scenario_id == "S3b":
        sys.exit(
            "ERROR: S3b negative-DT playback is not yet implemented.\n"
            "The playback layer must arm |dt_s| seconds early per part.\n"
            "See harness_note in scenarios/s3b-dt-boundary.json."
        )

    # S8 has no 'parts' array — a single implicit part covers all trials.
    # A 'pairs' scenario (rr-linked-cycle-effectiveness-scenario, e.g. S9) has
    # no 'parts' array either — the placeholder below is inert for it (see the
    # 'pairs' dispatch further down); it exists only so this function's shared
    # setup code (run_dir, device_idx, the part-filter guard immediately below)
    # doesn't need a third special case threaded through it.
    parts: list[dict] = scenario.get("parts", [{"part_index": 0}])
    n_trials: int = scenario["trials"]
    is_s5 = (scenario_id == "S5")
    is_s4 = (scenario_id == "S4")
    is_s7 = (scenario_id == "S7")
    is_s8 = (scenario_id == "S8")
    is_pairs = "pairs" in scenario

    # ── Part filter ────────────────────────────────────────────────────────────
    # --parts 0,2,5  selects specific parts by part_index.
    # Not applicable to S8 (single implicit slot, no parts array) or to a
    # 'pairs' scenario (S9: pairs are addressed by pair_index within their own
    # playback path, not by this parts-array filter). Silently ignored for
    # both so the caller does not need special-case logic when forwarding
    # flags from run_study.py. Without this guard, a pairs scenario's inert
    # single-element 'parts' placeholder above would make --parts reject any
    # index other than 0, which would be actively misleading (S9 has 2 valid
    # pairs) rather than merely inapplicable.
    _requested_parts = getattr(args, "parts", None)
    if _requested_parts is not None and not is_s8 and not is_pairs:
        requested_indices: set[int] = set()
        for _tok in _requested_parts.split(","):
            _tok = _tok.strip()
            if not _tok.isdigit():
                sys.exit(
                    f"ERROR: invalid part index '{_tok}' in --parts — "
                    "must be a non-negative integer"
                )
            requested_indices.add(int(_tok))
        available_indices = {p["part_index"] for p in parts}
        unknown_indices   = requested_indices - available_indices
        if unknown_indices:
            sys.exit(
                f"ERROR: unknown part index(es) in --parts: "
                f"{', '.join(str(i) for i in sorted(unknown_indices))}\n"
                f"       Valid indices for {scenario_id}: "
                f"{', '.join(str(i) for i in sorted(available_indices))}"
            )
        n_total = len(parts)
        parts   = [p for p in parts if p["part_index"] in requested_indices]
        # Preserve the JSON order rather than the order the user typed the indices.
        print(
            f"  Part filter   : indices "
            f"{', '.join(str(p['part_index']) for p in parts)} "
            f"({len(parts)} of {n_total} parts)\n"
        )

    # Run directory
    qa_rr_root = Path(__file__).resolve().parent.parent
    results_root = qa_rr_root / "results"
    if args.run_dir is not None:
        # Resolve relative paths from CWD (same convention as analyse.py),
        # not from results_root — avoids double-nesting results/results/…
        run_dir = Path(args.run_dir)
        if not run_dir.is_absolute():
            run_dir = Path.cwd() / run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = make_run_dir(results_root)
    print(f"Run directory: {run_dir.relative_to(qa_rr_root)}")

    # Device selection (skip in dry-run)
    device_idx = None
    if not args.dry_run:
        device_idx = _select_device(args.device)

    # rr-linked-cycle-effectiveness-scenario: a 'pairs' scenario (e.g. S9)
    # takes an entirely separate playback/truth path (design D2). The 'parts'/
    # is_s5/is_s4/... locals built above for a pairs scenario are inert
    # placeholders (default [{"part_index": 0}], never referenced below this
    # point once we return) — kept that way, rather than skipping their
    # construction, so this dispatch sits at the same place in the function
    # the original code already computed run_dir/device_idx, leaving every
    # existing scenario's control flow and print order byte-for-byte
    # unchanged (spec: "Existing part-based scenarios are unaffected";
    # verified via before/after --dry-run diff, task 2.4/6.2).
    if "pairs" in scenario:
        _run_pairs(scenario, run_dir, args, device_idx, qa_rr_root)
        return

    total_trials = len(parts) * n_trials
    played = 0

    for part in parts:
        part_index: int = part["part_index"]
        for trial_index in range(n_trials):
            seed = compute_seed(scenario_id, part_index, trial_index)

            # Render PCM
            import numpy as np
            s7_signals_meta = None  # populated only for S7/S8/S4 (one truth row per signal)
            s8_signals_meta = None
            s4_signals_meta = None
            if is_s8:
                samples, s8_signals_meta = _render_band_scene(scenario, seed)
                # Per-slot truth fields unused for S8 (logged per signal below).
                true_snr_db  = ""
                true_dt_s    = ""
                true_freq_hz = ""
                msg_text = "; ".join(s["message_text"] for s in s8_signals_meta)
            elif is_s5:
                samples = _render_noise(part, seed)
                true_snr_db = part.get("level_dbfs", "")
                true_dt_s = 0.0
                true_freq_hz = ""
                msg_text = ""
            elif is_s7:
                samples, s7_signals_meta = _render_compound(scenario, part, seed)
                # Per-slot truth fields are unused for S7 (logged per signal below).
                true_snr_db = ""
                true_dt_s = ""
                true_freq_hz = ""
                msg_text = "; ".join(s["message_text"] for s in s7_signals_meta)
            elif is_s4:
                samples, s4_signals_meta = _render_multi(scenario, part, trial_index, seed)
                # Per-slot truth fields are unused for S4 (logged per signal below,
                # rr-density-qrm-scenario — one truth row per injected message so the
                # matcher scores each independently instead of "matched any one").
                # No pooled msg_text is built here (task 1.4): it was only ever
                # needed to feed the old single pooled-row truth write, which the
                # per-signal branch below replaces.
                true_snr_db = ""
                true_dt_s = ""
                true_freq_hz = ""
                msg_text = ""
            else:
                # S1, S1b, S2, S3 — single signal
                fixed = scenario.get("fixed", {})
                true_snr_db = part.get("snr_db", fixed.get("snr_db", 0.0))
                true_dt_s = part.get("dt_s", fixed.get("dt_s", 0.0))
                true_freq_hz = part.get("base_freq_hz", fixed.get("base_freq_hz", 1500.0))
                msg_ids = list(scenario["message_texts"].keys())
                msg_text = scenario["message_texts"][msg_ids[0]]
                samples = _render_single(scenario, part, trial_index, seed)

            samples = samples.astype("float32")

            # Normalise to ±1.0 peak before playback.  The noise sigma is
            # calibrated for a 2 500 Hz reference bandwidth (FT8 SNR convention)
            # at 48 kHz, so raw samples typically peak at 10–14 — far beyond the
            # ±1.0 range PortAudio expects for float32.  Without normalisation
            # ~70 % of samples are hard-clipped to ±1.0, producing audible
            # square-wave distortion.  Uniform scaling preserves SNR (signal and
            # noise both divided by the same constant), so decode rates and S1
            # SNR-linearity measurements are unaffected.
            _peak = float(np.max(np.abs(samples)))
            if _peak > 0.0:
                samples = (samples * (_PLAYBACK_PEAK_LEVEL / _peak)).astype("float32")

            # Half-cosine fade-out — applied after normalisation so the taper
            # envelope is not distorted by any subsequent scaling.
            _n_fade = int(_FADEOUT_DURATION_S * DEFAULT_SAMPLE_RATE_HZ)
            if 0 < _n_fade <= len(samples):
                _t = np.linspace(0.0, 1.0, _n_fade, endpoint=True)
                _fade_env = (0.5 * (1.0 + np.cos(np.pi * _t))).astype("float32")
                samples[-_n_fade:] *= _fade_env

            # --dump-wav-dir (D-001 param sweep, additive; gated behind the new flag).
            # Persist this rendered slot's PCM as a 12 kHz mono 16-bit WAV so an offline
            # decoder can re-decode it. Purely additive: it neither consumes nor alters
            # `samples`, `cycle_utc`, or truth.csv, so the live-playback path below is
            # byte-for-byte unaffected when the flag is unset (work-order step 8).
            if args.dump_wav_dir:
                _dump_slot_wav(args.dump_wav_dir, scenario_id, part_index,
                               trial_index, seed, samples)

            # Cycle boundary alignment (skipped in dry-run mode)
            if args.dry_run:
                # In dry-run, use the current time snapped to the nearest past boundary
                now_s = int(time.time())
                snap = now_s - (now_s % SLOT_SECONDS)
                cycle_utc = datetime.fromtimestamp(snap, tz=timezone.utc).replace(microsecond=0)
            else:
                boundary_ts = _next_cycle_boundary()
                cycle_utc = _wait_for_cycle(boundary_ts)
            cycle_utc_str = cycle_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            snr_str = f"SNR={true_snr_db} dB" if true_snr_db != "" else "SNR=N/A"
            status_prefix = (
                f"[{scenario_id}] Part {part_index + 1}/{len(parts)}  "
                f"Trial {trial_index + 1}/{n_trials}  "
                f"{snr_str}  seed={seed}  cycle={cycle_utc_str}"
            )
            print(f"{status_prefix} …", end=" ", flush=True)

            if args.dry_run:
                print(f"[DRY RUN] would play {len(samples)} samples at 48 kHz")
            else:
                import sounddevice as sd
                try:
                    sd.play(samples, samplerate=DEFAULT_SAMPLE_RATE_HZ, device=device_idx, blocking=False)
                    sd.wait()
                except sd.PortAudioError as exc:
                    print(f"\nERROR: PortAudio playback failed: {exc}")
                    print("Available output devices:")
                    for i, d in enumerate(sd.query_devices()):
                        if d["max_output_channels"] > 0:
                            print(f"  [{i}] {d['name']}")
                    sys.exit(1)
                print("done")

            # Log truth row(s).  S4, S7, and S8 write one row per signal so the
            # matcher scores each message independently (rr-density-qrm-scenario
            # extended this to S4, which previously wrote a single pooled row per
            # cycle — see RR-007); all other scenarios write a single per-slot row.
            if is_s8 and s8_signals_meta is not None:
                for sig in s8_signals_meta:
                    _append_truth(run_dir, {
                        "scenario_id":  scenario_id,
                        "part_index":   part_index,
                        "trial_index":  trial_index,
                        "seed":         seed,
                        "true_snr_db":  sig["snr_db"],
                        "true_dt_s":    sig["dt_s"],
                        "true_freq_hz": sig["freq_hz"],
                        "message_text": sig["message_text"],
                        "cycle_utc":    cycle_utc_str,
                    })
            elif is_s7 and s7_signals_meta is not None:
                for sig in s7_signals_meta:
                    _append_truth(run_dir, {
                        "scenario_id": scenario_id,
                        "part_index": part_index,
                        "trial_index": trial_index,
                        "seed": seed,
                        "true_snr_db": sig["snr_db"],
                        "true_dt_s": sig["dt_s"],
                        "true_freq_hz": sig["freq_hz"],
                        "message_text": sig["message_text"],
                        "cycle_utc": cycle_utc_str,
                    })
            elif is_s4 and s4_signals_meta is not None:
                for sig in s4_signals_meta:
                    _append_truth(run_dir, {
                        "scenario_id": scenario_id,
                        "part_index": part_index,
                        "trial_index": trial_index,
                        "seed": seed,
                        "true_snr_db": sig["snr_db"],
                        "true_dt_s": sig["dt_s"],
                        "true_freq_hz": sig["freq_hz"],
                        "message_text": sig["message_text"],
                        "cycle_utc": cycle_utc_str,
                    })
            else:
                _append_truth(run_dir, {
                    "scenario_id": scenario_id,
                    "part_index": part_index,
                    "trial_index": trial_index,
                    "seed": seed,
                    "true_snr_db": true_snr_db,
                    "true_dt_s": true_dt_s,
                    "true_freq_hz": true_freq_hz,
                    "message_text": msg_text,
                    "cycle_utc": cycle_utc_str,
                })
            played += 1

    truth_rel = (run_dir / "truth.csv").relative_to(qa_rr_root)
    print(
        f"\nScenario {scenario_id} complete — {played} trials injected. "
        f"Truth: {truth_rel}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R&R study generator driver — render FT8 signals and play into VB-CABLE"
    )
    parser.add_argument("scenario_json", help="Path to scenario JSON file")
    parser.add_argument(
        "--device",
        default="CABLE Input",
        help="Output device name substring (default: 'CABLE Input')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render audio and write truth.csv but skip actual playback",
    )
    parser.add_argument(
        "--dump-wav-dir",
        default=None,
        metavar="DIR",
        help=(
            "Additionally write each rendered slot's PCM to DIR as a 12 kHz mono "
            "16-bit WAV named <scenario>_p<part>_t<trial>_s<seed>.wav (D-001 offline "
            "param sweep). Additive and independent of --dry-run: it does not alter "
            "truth.csv or the playback path. Combine with --dry-run to generate a WAV "
            "corpus + truth.csv without playing anything."
        ),
    )
    parser.add_argument(
        "--parts",
        default=None,
        metavar="IDX[,IDX...]",
        help=(
            "Comma-separated list of part indices to run (0-based). "
            "If omitted, all parts are run. "
            "Not applicable to S8 or to a 'pairs'-schema scenario such as S9 "
            "(neither has a parts array — silently ignored for both)."
        ),
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        metavar="DIR",
        help=(
            "Override the auto-generated results/<date>-<sha7> directory. "
            "Use to keep calibration-step runs in separate directories (Lesson 14). "
            "Relative paths are resolved from qa/rr-study/results/."
        ),
    )
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
