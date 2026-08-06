#!/usr/bin/env python3
"""Live cross-decode replay -- WSJT-X vs OpenWSFZ, 2026-08-06.

The Captain's experiment design: WSJT-X's FT991A instance is switched off the real radio
and listens to `CABLE Output (VB-Audio Virtual Cable)` instead. A fresh OpenWSFZ daemon
listens on the same virtual cable. Two 20-cycle (5-minute) passes replay real captured WAVs
out to `CABLE Input`, so both decoders decode the *same* live audio simultaneously, in real
time -- no offline `jt9`, which the standing rule bars as a reference decoder:

  Pass 1: WSJT-X's own captured WAVs (from `20260803_live_run_1713/wsjt-x/wav/`), the
          20 consecutive matched cycles 260804_085845 -> 260804_090330 (the busiest 5-minute
          window in the corpus by combined original decode count: owsfz=466, wsjtx=328).
  Pass 2: OpenWSFZ's own captured WAVs for the SAME 20 cycles
          (`20260803_live_run_1713/owsfz/wav/`).

Both decoders listen through both passes, giving the full 2x2 (source x decoder) matrix in
one ~10-minute session, all four cells live-decoded.

Daemon lifecycle / audio-playback mechanics ported from
`qa/cycleframer-alignment-replay/2026-08-04-isolated-replay-rerun/run_isolated_replay_generic.py`
(itself unmodified-core-logic from the 07-23 original) -- proven for exactly this VB-CABLE
replay pattern across the Task 5 arm A/B runs. This script swaps out that harness's
Gate-R/candidate-diagnosis analysis (not needed here) for a straight SNR/DT/freq/decode-count
comparison, and replaces its scattered-candidate sample list with a single consecutive
20-cycle window replayed twice (once per source).

NFR-021: message text is read only to build match keys (`normalize_hash_tokens`, identical
convention to every other script in this directory) and is never printed or written to any
committed file. Only aggregate stats and per-row SNR/DT/freq (no callsigns) are written out.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests
from scipy.io import wavfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "endurance"))
from anova_common import normalize_hash_tokens, parse_all_txt, parse_cycle_ts  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_EXE = (REPO_ROOT / "src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish"
              / "OpenWSFZ.Daemon.exe")
CORPUS = REPO_ROOT / "artefacts" / "20260803_live_run_1713"
OUT_DIR = Path(__file__).resolve().parent

# CORRECTED 2026-08-06 20:07 UTC: the running instance is launched --rig-name=FT991A, which
# uses its OWN AppData directory per WSJT-X's multi-instance convention (already on record
# from the 2026-08-02 launch-order investigation, missed here on the first pass -- see the
# correction appended to 2026-08-06-1933-qa-decode-config-comparison-wsjtx-vs-openwsfz.md).
# The plain `WSJT-X\ALL.TXT` path is a stale, untouched-since-08-02 default profile, NOT what
# any live session this week has used. Verified via
# `(Get-CimInstance Win32_Process -Filter "Name='wsjtx.exe'").CommandLine`.
WSJTX_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")

PORT = 8080
SLOT_SECONDS = 15
SAMPLE_RATE_HZ = 12000
OUTPUT_DEVICE_SUBSTR = "CABLE Input"   # we play OUT to this -- feeds CABLE Output, which
INPUT_DEVICE_SUBSTR = "CABLE Output"   # both WSJT-X and our daemon LISTEN on
PLAYBACK_PEAK = 0.9
FLUSH_WAIT_S = 3.0
STARTUP_WARMUP_S = 4.0
WSJTX_DECODE_LATENCY_SLACK_S = 4.0  # WSJT-X's own decode can land a few s after cycle end

WINDOW = [
    "260804_085845.wav", "260804_085900.wav", "260804_085915.wav", "260804_085930.wav",
    "260804_085945.wav", "260804_090000.wav", "260804_090015.wav", "260804_090030.wav",
    "260804_090045.wav", "260804_090100.wav", "260804_090115.wav", "260804_090130.wav",
    "260804_090145.wav", "260804_090200.wav", "260804_090215.wav", "260804_090230.wav",
    "260804_090245.wav", "260804_090300.wav", "260804_090315.wav", "260804_090330.wav",
]


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Daemon lifecycle (ported unmodified from run_isolated_replay_generic.py)
# ---------------------------------------------------------------------------

def start_daemon(run_dir: Path, port: int) -> subprocess.Popen:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "config.json"
    stdout_path = run_dir / "daemon_stdout.log"
    proc = subprocess.Popen(
        [str(DAEMON_EXE), "--config", str(config_path), "--port", str(port)],
        stdout=open(stdout_path, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    log(f"Daemon launched, pid={proc.pid}, port={port}, stdout -> {stdout_path}")
    return proc


def wait_ready(base_url: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/api/v1/status", timeout=2)
            if r.status_code == 200:
                log(f"Daemon ready: {r.json()}")
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Daemon did not become ready in time")


def configure_daemon(base_url: str, log_dir: Path, all_txt_path: Path) -> None:
    devices = requests.get(f"{base_url}/api/v1/audio/devices", timeout=5).json()
    match = next((d for d in devices if INPUT_DEVICE_SUBSTR.lower() in d["name"].lower()), None)
    if match is None:
        names = [d["name"] for d in devices]
        raise RuntimeError(f"No capture device matching '{INPUT_DEVICE_SUBSTR}': {names}")
    log(f"Capture device: {match['name']} ({match['id']})")

    cfg = requests.get(f"{base_url}/api/v1/config", timeout=5).json()
    cfg["audioDeviceId"] = match["id"]
    cfg["audioDeviceFriendlyName"] = match["name"]
    cfg["logging"]["fileEnabled"] = True
    cfg["logging"]["fileLogLevel"] = "Debug"
    cfg["logging"]["directory"] = str(log_dir)
    cfg["decodeLog"]["enabled"] = True
    cfg["decodeLog"]["path"] = str(all_txt_path)
    cfg["decodeLog"]["dialFrequencyMHz"] = 14.074

    r = requests.post(f"{base_url}/api/v1/config", json=cfg, timeout=10)
    r.raise_for_status()
    log("Config applied (CABLE Output + Debug file logging + ALL.TXT logging).")

    r = requests.post(f"{base_url}/api/v1/decode/start", timeout=10)
    r.raise_for_status()
    log("Decode started.")


def stop_daemon(base_url: str, proc: subprocess.Popen) -> None:
    try:
        requests.post(f"{base_url}/api/v1/decode/stop", timeout=5)
    except Exception as exc:  # noqa: BLE001
        log(f"decode/stop call failed (continuing shutdown): {exc}")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    log(f"Daemon (pid={proc.pid}) stopped.")


# ---------------------------------------------------------------------------
# Audio (ported unmodified from run_isolated_replay_generic.py)
# ---------------------------------------------------------------------------

def select_output_device() -> int:
    import sounddevice as sd
    devices = sd.query_devices()
    matches = [(i, d) for i, d in enumerate(devices)
               if OUTPUT_DEVICE_SUBSTR.lower() in d["name"].lower()
               and d["max_output_channels"] > 0]
    if not matches:
        raise RuntimeError(f"No output device matching '{OUTPUT_DEVICE_SUBSTR}'")
    idx, d = matches[0]
    log(f"Output device: [{idx}] {d['name']}")
    return idx


def load_wav_normalised(path: Path) -> np.ndarray:
    sr, data = wavfile.read(path)
    if sr != SAMPLE_RATE_HZ:
        raise RuntimeError(f"{path}: unexpected sample rate {sr} (expected {SAMPLE_RATE_HZ})")
    x = data.astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0.0:
        x = x * (PLAYBACK_PEAK / peak)
    return x.astype(np.float32)


def play(samples: np.ndarray, device_idx: int) -> None:
    import sounddevice as sd
    sd.play(samples, samplerate=SAMPLE_RATE_HZ, device=device_idx, blocking=True)
    sd.wait()


def next_boundary() -> float:
    now_s = int(time.time())
    rem = now_s % SLOT_SECONDS
    if rem == 0:
        return float(now_s + SLOT_SECONDS)
    return float(now_s + (SLOT_SECONDS - rem))


def wait_for_boundary(ts: float, prewarm: float = 0.5) -> None:
    remaining = (ts - prewarm) - time.time()
    if remaining > 0:
        time.sleep(remaining)


def play_pass(wav_dir: Path, output_device_idx: int, label: str) -> tuple[datetime.datetime, datetime.datetime]:
    boundary = next_boundary()
    log(f"[{label}] waiting for cycle boundary at {boundary} (in {boundary - time.time():.1f}s)")
    wait_for_boundary(boundary)
    pass_start = datetime.datetime.now(datetime.timezone.utc)
    log(f"[{label}] playback starting, {len(WINDOW)} cycles ({len(WINDOW) * SLOT_SECONDS}s)")
    for fname in WINDOW:
        samples = load_wav_normalised(wav_dir / fname)
        play(samples, output_device_idx)
    pass_end = datetime.datetime.now(datetime.timezone.utc)
    log(f"[{label}] playback done: {pass_start.isoformat()} -> {pass_end.isoformat()}")
    time.sleep(FLUSH_WAIT_S)
    return pass_start, pass_end


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def filter_by_window(rows: list[dict], start: datetime.datetime, end: datetime.datetime,
                      slack_s: float = 0.0) -> list[dict]:
    lo = start - datetime.timedelta(seconds=slack_s)
    hi = end + datetime.timedelta(seconds=slack_s)
    out = []
    for r in rows:
        dt = parse_cycle_ts(r["ts"])
        if dt is None:
            continue
        dt = dt.replace(tzinfo=datetime.timezone.utc)
        if lo <= dt <= hi:
            out.append(r)
    return out


def match_pairs(rows_a: list[dict], rows_b: list[dict]) -> list[tuple[dict, dict]]:
    """(ts, normalised message) exact match -- both sides are decoding the same live audio
    at the same wall-clock cycles, so ts should line up exactly, same convention as every
    other matcher in this directory."""
    from collections import defaultdict, Counter
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows_b:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        by_key[key].append(r)
    consumed: Counter = Counter()
    pairs = []
    for r in rows_a:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        avail = by_key.get(key, ())
        if consumed[key] < len(avail):
            pairs.append((r, avail[consumed[key]]))
            consumed[key] += 1
    return pairs


def summarise_pass(label: str, our_rows: list[dict], wx_rows: list[dict]) -> dict:
    pairs = match_pairs(our_rows, wx_rows)
    print(f"\n--- {label} ---")
    print(f"OpenWSFZ decodes: {len(our_rows)}   WSJT-X decodes: {len(wx_rows)}   "
          f"matched pairs: {len(pairs)}")
    if not pairs:
        return dict(label=label, n_our=len(our_rows), n_wx=len(wx_rows), n_matched=0)

    d_snr = np.array([p[0]["snr"] - p[1]["snr"] for p in pairs], dtype=float)
    d_dt = np.array([p[0]["dt"] - p[1]["dt"] for p in pairs], dtype=float)
    d_freq = np.array([p[0]["freq_hz"] - p[1]["freq_hz"] for p in pairs], dtype=float)
    print(f"SNR delta (ours-wsjtx), dB:  mean={d_snr.mean():+.2f} median={np.median(d_snr):+.2f} "
          f"stdev={d_snr.std():.2f}")
    print(f"DT delta (ours-wsjtx), s:    mean={d_dt.mean():+.3f} median={np.median(d_dt):+.3f} "
          f"stdev={d_dt.std():.3f}")
    print(f"freq delta (ours-wsjtx), Hz: mean={d_freq.mean():+.1f} median={np.median(d_freq):+.1f} "
          f"stdev={d_freq.std():.1f}")
    return dict(
        label=label, n_our=len(our_rows), n_wx=len(wx_rows), n_matched=len(pairs),
        snr_delta_mean=float(d_snr.mean()), snr_delta_median=float(np.median(d_snr)),
        dt_delta_mean=float(d_dt.mean()), dt_delta_median=float(np.median(d_dt)),
        freq_delta_mean=float(d_freq.mean()), freq_delta_median=float(np.median(d_freq)),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-index", type=int, default=1,
                     help="Replicate number (1-5 for the ANOVA series). Selects "
                          "_work/run<N>/ as this run's directory so repeated invocations "
                          "don't clobber each other.")
    args = ap.parse_args()

    run_dir = OUT_DIR / "_work" / f"run{args.run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)
    our_all_txt = run_dir / "our_ALL.TXT"
    base_url = f"http://127.0.0.1:{PORT}"
    log(f"=== run {args.run_index}: run_dir={run_dir} ===")

    proc = start_daemon(run_dir, PORT)
    try:
        wait_ready(base_url)
        configure_daemon(base_url, run_dir / "logs", our_all_txt)
        time.sleep(STARTUP_WARMUP_S)

        output_device_idx = select_output_device()

        p1_start, p1_end = play_pass(CORPUS / "wsjt-x" / "wav", output_device_idx,
                                      "pass1: WSJT-X-source WAVs")
        p2_start, p2_end = play_pass(CORPUS / "owsfz" / "wav", output_device_idx,
                                      "pass2: OpenWSFZ-source WAVs")
    finally:
        stop_daemon(base_url, proc)

    windows_path = run_dir / "pass_windows.json"
    windows_path.write_text(json.dumps({
        "pass1_wsjtx_source": [p1_start.isoformat(), p1_end.isoformat()],
        "pass2_owsfz_source": [p2_start.isoformat(), p2_end.isoformat()],
    }, indent=2))
    log(f"Pass windows written: {windows_path}")

    # ---- analysis ----
    our_rows_all = parse_all_txt(str(our_all_txt))
    wx_rows_all = parse_all_txt(str(WSJTX_ALL_TXT))
    log(f"our_ALL.TXT total rows this session: {len(our_rows_all)}")
    log(f"WSJT-X ALL.TXT total rows (all-time file): {len(wx_rows_all)}")

    our_p1 = filter_by_window(our_rows_all, p1_start, p1_end, slack_s=1.0)
    our_p2 = filter_by_window(our_rows_all, p2_start, p2_end, slack_s=1.0)
    wx_p1 = filter_by_window(wx_rows_all, p1_start, p1_end, slack_s=WSJTX_DECODE_LATENCY_SLACK_S)
    wx_p2 = filter_by_window(wx_rows_all, p2_start, p2_end, slack_s=WSJTX_DECODE_LATENCY_SLACK_S)

    s1 = summarise_pass("PASS 1 -- WSJT-X-source audio: OpenWSFZ vs WSJT-X", our_p1, wx_p1)
    s2 = summarise_pass("PASS 2 -- OpenWSFZ-source audio: OpenWSFZ vs WSJT-X", our_p2, wx_p2)

    print("\n--- decode-count matrix (source x decoder) ---")
    print(f"{'':25s} {'OpenWSFZ decoder':>18s} {'WSJT-X decoder':>16s}")
    print(f"{'WSJT-X-source WAVs':25s} {s1.get('n_our', 0):18d} {s1.get('n_wx', 0):16d}")
    print(f"{'OpenWSFZ-source WAVs':25s} {s2.get('n_our', 0):18d} {s2.get('n_wx', 0):16d}")

    summary_path = OUT_DIR / f"summary_run{args.run_index}.json"
    summary_path.write_text(json.dumps({"pass1": s1, "pass2": s2}, indent=2))
    log(f"Summary written: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
