"""S6 corpus replay harness.

Plays each WAV from the local off-air corpus through VB-CABLE in independently
randomised order, K=3 times, capturing ALL.TXT snapshots from both WSJT-X and
OpenWSFZ after each cycle.

Usage (from qa/rr-study/):
    python harness/corpus_replay.py
    python harness/corpus_replay.py --device "CABLE Input" --runs 3
    python harness/corpus_replay.py --corpus ../p10-decoder-ground-truth_items --skip-warmup

Output:
    results/corpus-<YYYY-MM-DD>/
        run_manifest.json          # WAV order, seeds, timing — local only
        raw/
            run_<R>_<wav>.jsonl    # per-cycle ALL.TXT snapshots — local only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Package root ───────────────────────────────────────────────────────────────
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import parse_all_txt, normalise_slot, SLOT_SECONDS  # noqa: E402
from harness.run_scenario import (                                        # noqa: E402
    _select_device,
    _next_cycle_boundary,
    _wait_for_cycle,
    _CYCLE_PREWARM_S,
    _PLAYBACK_PEAK_LEVEL,
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE           = _QA_ROOT
_RESULTS        = _HERE / "results"
_DEFAULT_CORPUS = _HERE.parent.parent / "p10-decoder-ground-truth_items"

WSJT_ALL_TXT  = Path(r"C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT")
OWSFZ_ALL_TXT = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")

# ── Study parameters ───────────────────────────────────────────────────────────
_SCENARIO_ID         = "S6"
_DEFAULT_RUNS        = 3
_EXPECTED_WAV_COUNT  = 42
_WAV_PATTERN         = re.compile(r"^\d{6}_\d{6}\.wav$", re.IGNORECASE)
_POST_CYCLE_SETTLE_S = 5.0   # seconds to wait after playback for decoders to write ALL.TXT
_CORPUS_FS           = 12_000  # source WAV sample rate (Hz)
_PLAYBACK_FS         = 48_000  # VB-CABLE preferred sample rate (Hz)


# ── Seed ──────────────────────────────────────────────────────────────────────

def _run_seed(run_index: int) -> int:
    """Deterministic seed for run R: SHA-256 of 'S6,<run_index>'."""
    key = f"{_SCENARIO_ID},{run_index}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest(), 16) % (2 ** 31)


# ── WAV discovery ──────────────────────────────────────────────────────────────

def _discover_wavs(corpus_dir: Path) -> list[Path]:
    """Return sorted WAV files matching the p10 naming pattern (YYMMDD_HHMMSS.wav)."""
    if not corpus_dir.exists():
        sys.exit(
            f"ERROR: corpus directory not found: {corpus_dir}\n"
            "       Set --corpus to the path of p10-decoder-ground-truth_items/"
        )
    wavs = sorted(
        p for p in corpus_dir.iterdir()
        if p.is_file() and _WAV_PATTERN.match(p.name)
    )
    if len(wavs) == 0:
        sys.exit(f"ERROR: no WAV files matching YYMMDD_HHMMSS.wav found in {corpus_dir}")
    if len(wavs) != _EXPECTED_WAV_COUNT:
        print(
            f"  WARNING: expected {_EXPECTED_WAV_COUNT} WAV files, "
            f"found {len(wavs)}. Proceeding with {len(wavs)}.",
            flush=True,
        )
    return wavs


# ── WAV loading & resampling ───────────────────────────────────────────────────

def _load_wav(path: Path) -> "numpy.ndarray":
    """Load a 12 kHz mono int16 WAV and return float32 PCM at 48 kHz.

    Resamples from 12 kHz → 48 kHz (×4 upsample) using scipy.signal.resample_poly
    to match VB-CABLE's preferred rate.  Normalises peak amplitude to
    _PLAYBACK_PEAK_LEVEL to avoid PortAudio clipping.
    """
    import numpy as np
    import wave

    with wave.open(str(path), "rb") as wf:
        n_channels   = wf.getnchannels()
        sampwidth    = wf.getsampwidth()
        framerate    = wf.getframerate()
        n_frames     = wf.getnframes()
        raw_bytes    = wf.readframes(n_frames)

    if n_channels != 1:
        sys.exit(f"ERROR: WAV is not mono ({n_channels} channels): {path.name}")
    if sampwidth != 2:
        sys.exit(f"ERROR: WAV is not 16-bit ({sampwidth * 8}-bit): {path.name}")
    if framerate != _CORPUS_FS:
        print(
            f"  WARNING: {path.name} sample rate is {framerate} Hz "
            f"(expected {_CORPUS_FS} Hz); resampling anyway.",
            flush=True,
        )

    samples_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
    samples_f64   = samples_int16.astype(np.float64) / 32768.0

    # Upsample 12 kHz → 48 kHz (factor 4)
    if framerate != _PLAYBACK_FS:
        from scipy.signal import resample_poly
        up   = _PLAYBACK_FS // framerate
        down = 1
        samples_f64 = resample_poly(samples_f64, up, down)

    samples_f32 = samples_f64.astype(np.float32)
    peak = float(np.max(np.abs(samples_f32)))
    if peak > 0.0:
        samples_f32 = (samples_f32 * (_PLAYBACK_PEAK_LEVEL / peak)).astype(np.float32)
    return samples_f32


# ── ALL.TXT snapshot ───────────────────────────────────────────────────────────

def _snapshot_decodes(
    all_txt_path: Path,
    cycle_utc: datetime,
    since_pos: int,
) -> tuple[list[dict], int]:
    """Read new lines appended since *since_pos* and return decodes for *cycle_utc*.

    Returns (list_of_decode_dicts, new_file_position).
    Each dict: {utc, freq_hz, dt_s, snr_db, message}.
    """
    if not all_txt_path.exists():
        return [], since_pos

    with open(all_txt_path, encoding="utf-8", errors="replace") as fh:
        fh.seek(since_pos)
        new_lines = fh.readlines()
        new_pos   = fh.tell()

    records, _ = _parse_lines(new_lines)

    # Filter to the cycle we just played
    slot_utc = normalise_slot(cycle_utc)
    matched = [
        {
            "utc":     r.utc.isoformat(),
            "freq_hz": r.freq_hz,
            "dt_s":    r.dt_s,
            "snr_db":  r.snr_db,
            "message": r.message,
        }
        for r in records
        if normalise_slot(r.utc) == slot_utc
    ]
    return matched, new_pos


def _parse_lines(lines: list[str]) -> tuple[list, int]:
    """Parse a list of ALL.TXT lines using harness.common.parse_all_txt logic."""
    import tempfile
    from harness.common import parse_all_txt as _pat
    # Write to a temp file so we can reuse parse_all_txt
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    ) as tf:
        tf.writelines(lines)
        tmp = Path(tf.name)
    try:
        return _pat(tmp)
    finally:
        tmp.unlink(missing_ok=True)


# ── Result directory ───────────────────────────────────────────────────────────

def _make_corpus_run_dir() -> Path:
    """Create results/corpus-<YYYY-MM-DD>/ and its raw/ subdirectory."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir  = _RESULTS / f"corpus-{date_str}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(exist_ok=True)
    return run_dir


# ── Warmup ────────────────────────────────────────────────────────────────────

def _warmup(device_idx: int) -> None:
    """Play one silent cycle and ask operator to confirm both apps are decoding."""
    import numpy as np
    import sounddevice as sd

    silence = np.zeros(int(_PLAYBACK_FS * SLOT_SECONDS), dtype=np.float32)

    print()
    print("=" * 70)
    print("S6 CORPUS REPLAY  --  PRE-FLIGHT WARM-UP CHECK")
    print("=" * 70)
    print("  Playing one silent 15-second cycle.")
    print("  After it ends, confirm BOTH apps are in active decode mode.")
    print("  (No decode expected — audio is silence.)")
    print()

    boundary_ts = _next_cycle_boundary()
    cycle_utc   = _wait_for_cycle(boundary_ts)
    print(f"  Playing silent cycle at {cycle_utc.strftime('%H:%M:%S')} UTC … ",
          end="", flush=True)
    sd.play(silence, samplerate=_PLAYBACK_FS, device=device_idx, blocking=False)
    sd.wait()
    print("done")

    time.sleep(3.0)  # brief settle

    while True:
        try:
            ans = input(
                "  Both apps in decode/monitor mode? "
                "[y = yes, proceed / n = abort]: "
            ).strip().lower()
        except EOFError:
            ans = "n"

        if ans in ("y", "yes"):
            print()
            print("  Warm-up confirmed. Starting corpus replay ...")
            print("=" * 70)
            print()
            return
        elif ans in ("n", "no"):
            print("\n  Warm-up check FAILED. Study aborted.")
            sys.exit(1)
        else:
            print("  Please enter y or n.")


# ── Main replay loop ───────────────────────────────────────────────────────────

def _replay(
    wavs: list[Path],
    run_dir: Path,
    device_idx: int,
    n_runs: int,
) -> None:
    """Execute n_runs passes of the corpus in randomised order."""
    import random
    import sounddevice as sd

    manifest: dict = {
        "scenario":   _SCENARIO_ID,
        "run_dir":    str(run_dir),
        "n_runs":     n_runs,
        "n_wavs":     len(wavs),
        "runs":       [],
    }

    for run_idx in range(n_runs):
        seed = _run_seed(run_idx)
        rng  = random.Random(seed)
        order = list(range(len(wavs)))
        rng.shuffle(order)

        print(f"\n{'=' * 70}")
        print(f"  Run {run_idx + 1}/{n_runs}  (seed={seed})")
        print(f"{'=' * 70}\n")

        run_record = {
            "run_index": run_idx,
            "seed":      seed,
            "wav_order": [wavs[i].name for i in order],
            "cycles":    [],
        }

        # Note file positions before the run so we only read new lines
        wsjt_pos  = WSJT_ALL_TXT.stat().st_size  if WSJT_ALL_TXT.exists()  else 0
        owsfz_pos = OWSFZ_ALL_TXT.stat().st_size if OWSFZ_ALL_TXT.exists() else 0

        for slot_num, wav_idx in enumerate(order):
            wav_path = wavs[wav_idx]
            print(
                f"  [{slot_num + 1:>2}/{len(order)}] {wav_path.name} … ",
                end="", flush=True,
            )

            # Load and resample WAV
            samples = _load_wav(wav_path)

            # Wait for next 15-second UTC boundary
            boundary_ts = _next_cycle_boundary()
            cycle_utc   = _wait_for_cycle(boundary_ts)

            # Play
            sd.play(samples, samplerate=_PLAYBACK_FS, device=device_idx, blocking=False)
            sd.wait()
            print(f"played at {cycle_utc.strftime('%H:%M:%S')} UTC", flush=True)

            # Settle — let both decoders write ALL.TXT
            time.sleep(_POST_CYCLE_SETTLE_S)

            # Snapshot decodes
            wsjt_decodes,  wsjt_pos  = _snapshot_decodes(WSJT_ALL_TXT,  cycle_utc, wsjt_pos)
            owsfz_decodes, owsfz_pos = _snapshot_decodes(OWSFZ_ALL_TXT, cycle_utc, owsfz_pos)

            cycle_record = {
                "slot":         slot_num,
                "wav":          wav_path.name,
                "cycle_utc":    cycle_utc.isoformat(),
                "wsjt_decodes": wsjt_decodes,
                "owsfz_decodes": owsfz_decodes,
            }
            run_record["cycles"].append(cycle_record)

            # Write incremental raw snapshot
            raw_file = run_dir / "raw" / f"run_{run_idx:02d}_{wav_path.stem}.json"
            raw_file.write_text(
                json.dumps(cycle_record, indent=2), encoding="utf-8"
            )

        manifest["runs"].append(run_record)
        print(f"\n  Run {run_idx + 1} complete ({len(order)} WAVs).\n")

    # Write consolidated manifest
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written: {manifest_path.relative_to(_HERE)}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="S6 corpus replay harness — play off-air WAVs through VB-CABLE"
    )
    parser.add_argument(
        "--corpus", type=Path, default=_DEFAULT_CORPUS,
        help=f"Path to WAV corpus directory (default: {_DEFAULT_CORPUS})",
    )
    parser.add_argument(
        "--device", default="CABLE Input",
        help="Output device name substring (default: 'CABLE Input')",
    )
    parser.add_argument(
        "--runs", type=int, default=_DEFAULT_RUNS,
        help=f"Number of randomised passes over the corpus (default: {_DEFAULT_RUNS})",
    )
    parser.add_argument(
        "--skip-warmup", action="store_true",
        help="Skip the pre-flight warm-up check (not recommended)",
    )
    args = parser.parse_args()

    wavs       = _discover_wavs(args.corpus)
    device_idx = _select_device(args.device)
    run_dir    = _make_corpus_run_dir()

    print()
    print("=" * 70)
    print("S6 CORPUS REPLAY STUDY")
    print("=" * 70)
    print(f"  Corpus      : {args.corpus}  ({len(wavs)} WAVs)")
    print(f"  Runs        : {args.runs}")
    print(f"  Device      : {args.device}")
    print(f"  Results dir : {run_dir.relative_to(_HERE)}")
    print(f"  WSJT-X log  : {WSJT_ALL_TXT}")
    print(f"  OpenWSFZ log: {OWSFZ_ALL_TXT}")
    # Each cycle costs ~30 s of wall time: playback starts 0.5 s before the
    # boundary and ends at boundary + 14.5 s; the 5 s settle pushes past the
    # immediately following slot boundary, so the harness always skips to the
    # boundary after that — giving ~30 s per WAV regardless of settle duration.
    est_minutes = len(wavs) * args.runs * (SLOT_SECONDS * 2) / 60
    print(f"  Est. duration: ~{est_minutes:.0f} minutes")
    print()

    if not args.skip_warmup:
        _warmup(device_idx)

    _replay(wavs, run_dir, device_idx, args.runs)

    print()
    print("=" * 70)
    print("Corpus replay complete.")
    print(f"Raw snapshots in: {(run_dir / 'raw').relative_to(_HERE)}")
    print()
    print("Next step — run analysis:")
    print(f"  python harness/analyse_corpus.py --run-dir {run_dir.relative_to(_HERE)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
