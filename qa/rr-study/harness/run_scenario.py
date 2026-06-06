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

# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------

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

    for field in ("id", "parts", "trials"):
        if field not in scenario:
            sys.exit(f"ERROR: scenario file missing required field '{field}': {path}")

    # Resolve message texts
    msg_ids = scenario.get("message_ids") or []
    msg_pool = scenario.get("message_pool") or msg_ids
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
    target = boundary_ts - 0.5
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
    """Render a single-message part (S1, S2, S3) using the clean-room synthesiser."""
    from synth import encoder

    fixed = scenario.get("fixed", {})
    msg_ids = list(scenario["message_texts"].keys())
    # S1/S2/S3 use only the first message_id
    text = scenario["message_texts"][msg_ids[0]]

    base_freq_hz = part.get("base_freq_hz", fixed.get("base_freq_hz", 1500.0))
    dt_s = part.get("dt_s", fixed.get("dt_s", 0.0))
    snr_db = part.get("snr_db", fixed.get("snr_db", 0.0))

    return encoder.encode_message(
        text,
        base_freq_hz=float(base_freq_hz),
        dt_s=float(dt_s),
        snr_db=float(snr_db),
        seed=seed,
        sample_rate_hz=48000,
    )


# ---------------------------------------------------------------------------
# PCM rendering — S4 (multiple simultaneous signals)
# ---------------------------------------------------------------------------

def _render_multi(scenario: dict, part: dict, trial_index: int,
                  seed: int) -> "numpy.ndarray":
    """Render a multi-signal density part (S4) over one shared band-noise floor.

    Stations are spread evenly across 300–2700 Hz and scaled by their relative
    SNR; a single seeded noise floor is added once (see
    :func:`synth.channel.mix_to_shared_floor`) — not one floor per station.
    """
    from synth import channel, encoder

    msg_pool = list(scenario["message_texts"].values())
    n_signals = part["n_signals"]
    snr_db_set = part["snr_db_set"]

    # Spread frequencies evenly across 300–2700 Hz
    freq_min, freq_max = 300.0, 2700.0
    if n_signals == 1:
        freqs = [1500.0]
    else:
        freqs = [freq_min + i * (freq_max - freq_min) / (n_signals - 1)
                 for i in range(n_signals)]

    clean_signals = []
    snr_list = []
    for i in range(n_signals):
        text = msg_pool[i % len(msg_pool)]
        clean_signals.append(encoder.encode_message(
            text,
            base_freq_hz=freqs[i],
            dt_s=0.0,
            snr_db=None,  # clean render; the floor is added once by the mixer
            sample_rate_hz=48000,
        ))
        snr_list.append(float(snr_db_set[i % len(snr_db_set)]))

    return channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                       sample_rate_hz=48000)


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
            sample_rate_hz=48000,
        ))
        snr_list.append(snr_db)
        signals_meta.append({
            "message_text": text,
            "freq_hz": freq_hz,
            "dt_s": dt_s,
            "snr_db": snr_db,
        })

    mixed = channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                        sample_rate_hz=48000)
    return mixed, signals_meta


# ---------------------------------------------------------------------------
# PCM rendering — S5 (noise-only / signal-free)
# ---------------------------------------------------------------------------

def _render_noise(part: dict, seed: int) -> "numpy.ndarray":
    """Render a signal-free noise buffer for S5 false-positive tests."""
    import numpy as np

    sample_rate = 48000
    n_samples = int(sample_rate * 15)
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
# Truth CSV logging
# ---------------------------------------------------------------------------

_TRUTH_COLUMNS = [
    "scenario_id", "part_index", "trial_index", "seed",
    "true_snr_db", "true_dt_s", "true_freq_hz", "message_text", "cycle_utc",
]


def _append_truth(run_dir: Path, row: dict) -> None:
    """Append one row to truth.csv; write header only if creating the file."""
    truth_path = run_dir / "truth.csv"
    write_header = not truth_path.exists()
    with open(truth_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TRUTH_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _run(args: argparse.Namespace) -> None:
    scenario_path = Path(args.scenario_json)
    scenarios_dir = scenario_path.parent

    messages = _load_messages(scenarios_dir)
    scenario = _load_scenario(scenario_path, messages)

    scenario_id: str = scenario["id"]
    parts: list[dict] = scenario["parts"]
    n_trials: int = scenario["trials"]
    is_s5 = (scenario_id == "S5")
    is_s4 = (scenario_id == "S4")
    is_s7 = (scenario_id == "S7")

    # Run directory
    qa_rr_root = Path(__file__).resolve().parent.parent
    results_root = qa_rr_root / "results"
    run_dir = make_run_dir(results_root)
    print(f"Run directory: {run_dir.relative_to(qa_rr_root)}")

    # Device selection (skip in dry-run)
    device_idx = None
    if not args.dry_run:
        device_idx = _select_device(args.device)

    total_trials = len(parts) * n_trials
    played = 0

    for part in parts:
        part_index: int = part["part_index"]
        for trial_index in range(n_trials):
            seed = compute_seed(scenario_id, part_index, trial_index)

            # Render PCM
            import numpy as np
            s7_signals_meta = None  # populated only for S7 (one truth row per signal)
            if is_s5:
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
                samples = _render_multi(scenario, part, trial_index, seed)
                true_snr_db = ""  # multiple SNRs per part
                true_dt_s = 0.0
                true_freq_hz = ""
                # Use pool message texts (comma-separated for truth log)
                pool = list(scenario["message_texts"].values())
                n_sig = part["n_signals"]
                msg_text = "; ".join(pool[i % len(pool)] for i in range(n_sig))
            else:
                # S1, S2, S3 — single signal
                fixed = scenario.get("fixed", {})
                true_snr_db = part.get("snr_db", fixed.get("snr_db", 0.0))
                true_dt_s = part.get("dt_s", fixed.get("dt_s", 0.0))
                true_freq_hz = part.get("base_freq_hz", fixed.get("base_freq_hz", 1500.0))
                msg_ids = list(scenario["message_texts"].keys())
                msg_text = scenario["message_texts"][msg_ids[0]]
                samples = _render_single(scenario, part, trial_index, seed)

            samples = samples.astype("float32")

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
                    sd.play(samples, samplerate=48000, device=device_idx, blocking=False)
                    sd.wait()
                except sd.PortAudioError as exc:
                    print(f"\nERROR: PortAudio playback failed: {exc}")
                    print("Available output devices:")
                    for i, d in enumerate(sd.query_devices()):
                        if d["max_output_channels"] > 0:
                            print(f"  [{i}] {d['name']}")
                    sys.exit(1)
                print("done")

            # Log truth row(s).  S7 writes one row per compounded signal so the
            # matcher scores each message independently; all other scenarios
            # write a single per-slot row.
            if is_s7 and s7_signals_meta is not None:
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
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
