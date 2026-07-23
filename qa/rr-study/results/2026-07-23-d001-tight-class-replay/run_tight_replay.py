"""D-001 Option D, Step 1 -- Tight-class live VB-CABLE replay driver (spec §3.2-§3.3).

Executes the live-replay portion of
`dev-tasks/2026-07-23-d001-option-d-tight-class-replay-spec.md`, using the candidate sample
materialised by `materialise_tight_sample.py` (§3.1, already run).

Adapted from the sibling isolated-miss pass's `run_isolated_replay.py`
(`qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py`)
unchanged in every mechanical respect -- same throwaway daemon lifecycle, same VB-CABLE
loopback, same boundary-aligned playback with pre-roll noise, same Gate R reproduction check
via cycle-delimited log/ALL.TXT diffing. The only deliberate differences, per spec §3.2-§3.3:

  1. Samples from `tight_sample_candidates_with_msg.json` (Tight-class population) instead
     of the Isolated one.
  2. Does NOT attempt the Tier-1 candidate-generation-vs-LDPC-convergence split -- that
     instrumentation already proved unable to resolve anything on this corpus (100%
     Ambiguous in the Isolated pass) and re-running it here would not answer a new question.
     Candidate count / meanAbsLLR are still recorded per cycle (cheap, already available)
     for descriptive completeness in the report, but no CG/LDPC verdict is assigned.
  3. No reference-success-pool run (it existed only to support the Tier-1 LLR threshold,
     which this pass does not compute).

For each stratum (`< -15 dB`, `-15..-10 dB`), walks the pre-drawn, seeded, over-drawn
candidate list (up to 60) until 20 have been confirmed as **reproduced** misses (Gate R) or
the list is exhausted -- identical target/over-draw shape to the Isolated pass, which is what
makes the two resulting Decoded-on-replay rates directly comparable.

NFR-021: only ts/freq/snr/band/candidate-count/LLR values are ever written to the committed
result file. Message text is read into memory only (from the local, git-ignored
`_work/tight_sample_candidates_with_msg.json`) to perform the Gate R comparison, and never
written to any output.

Usage: python run_tight_replay.py [--target-per-stratum N] [--max-tries-per-stratum M]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from scipy.io import wavfile

REPO_ROOT = Path(__file__).resolve().parents[4]
RESULTS_DIR = Path(__file__).resolve().parent
WORK_DIR = RESULTS_DIR / "_work"
RUN_DIR = WORK_DIR / "daemon_run"
SAVE_DIR = REPO_ROOT / "artefacts" / "20260706_live_run_2308" / "save"

DAEMON_EXE = (REPO_ROOT / "src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish"
              / "OpenWSFZ.Daemon.exe")
PORT = 8098  # distinct from the isolated-miss pass's 8099, in case both are ever run close together
BASE_URL = f"http://localhost:{PORT}"
CONFIG_PATH = RUN_DIR / "config.json"
LOG_DIR = RUN_DIR / "logs"
ALLTXT_PATH = RUN_DIR / "OpenWSFZ_ALL.TXT"

SLOT_SECONDS = 15
SAMPLE_RATE_HZ = 12000
OUTPUT_DEVICE_SUBSTR = "CABLE Input"
INPUT_DEVICE_SUBSTR = "CABLE Output"
GAP_NOISE_DBFS = -30.0
PLAYBACK_PEAK = 0.9
FLUSH_WAIT_S = 2.5
STARTUP_WARMUP_S = 4.0

TARGET_PER_STRATUM = 20
MAX_TRIES_PER_STRATUM = 60

BANDS = ["< -15 dB", "-15..-10 dB"]

LINE_RE = re.compile(
    r"^(?P<ts>\d{6}_\d{6})\s+(?P<dial>[\d.]+)\s+Rx\s+FT8\s+"
    r"(?P<snr>-?\d+)\s+(?P<dt>-?[\d.]+)\s+(?P<freq>\d+)\s+(?P<msg>.+?)\s*$"
)
CYCLE_DELIM_RE = re.compile(r"Cycle \d{2}:\d{2}:\d{2}: \d+ decode\(s\) found")
PASS_RE = re.compile(
    r"Iterative subtraction: pass (\d+) of (\d+), (\d+) candidates found, (\d+) decoded\."
)
FAIL_RE = re.compile(
    r"Iterative subtraction: pass (\d+) LDPC fail stats.*?"
    r"failCands=(\d+) meanAbsLLR=(-?[\d.]+) prenormVar=(-?[\d.]+)"
)

FREQ_MATCH_TOLERANCE_HZ = 30


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    # Windows console default codepage (cp1252) can't encode arbitrary Unicode (e.g. Δ, —);
    # replace anything it can't render rather than crashing mid-run.
    safe_msg = msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
        sys.stdout.encoding or "utf-8", errors="replace"
    )
    print(f"[{ts}Z] {safe_msg}", flush=True)


# ---------------------------------------------------------------------------
# Daemon lifecycle
# ---------------------------------------------------------------------------

def start_daemon() -> subprocess.Popen:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = RUN_DIR / "daemon_stdout.log"
    proc = subprocess.Popen(
        [str(DAEMON_EXE), "--config", str(CONFIG_PATH), "--port", str(PORT)],
        stdout=open(stdout_path, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    log(f"Daemon launched, pid={proc.pid}, stdout -> {stdout_path}")
    return proc


def wait_ready(timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/v1/status", timeout=2)
            if r.status_code == 200:
                log(f"Daemon ready: {r.json()}")
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Daemon did not become ready in time")


def configure_daemon() -> None:
    devices = requests.get(f"{BASE_URL}/api/v1/audio/devices", timeout=5).json()
    match = next((d for d in devices if INPUT_DEVICE_SUBSTR.lower() in d["name"].lower()), None)
    if match is None:
        names = [d["name"] for d in devices]
        raise RuntimeError(f"No capture device matching '{INPUT_DEVICE_SUBSTR}': {names}")
    log(f"Capture device: {match['name']} ({match['id']})")

    cfg = requests.get(f"{BASE_URL}/api/v1/config", timeout=5).json()
    cfg["audioDeviceId"] = match["id"]
    cfg["audioDeviceFriendlyName"] = match["name"]
    cfg["logging"]["fileEnabled"] = True
    cfg["logging"]["fileLogLevel"] = "Debug"
    cfg["logging"]["directory"] = str(LOG_DIR)
    cfg["decodeLog"]["enabled"] = True
    cfg["decodeLog"]["path"] = str(ALLTXT_PATH)
    cfg["decodeLog"]["dialFrequencyMHz"] = 14.074

    r = requests.post(f"{BASE_URL}/api/v1/config", json=cfg, timeout=10)
    r.raise_for_status()
    log("Config applied (audio device + Debug file logging + ALL.TXT logging).")

    r = requests.post(f"{BASE_URL}/api/v1/decode/start", timeout=10)
    r.raise_for_status()
    log("Decode started.")


def stop_daemon(proc: subprocess.Popen) -> None:
    try:
        requests.post(f"{BASE_URL}/api/v1/decode/stop", timeout=5)
    except Exception as exc:  # noqa: BLE001
        log(f"decode/stop call failed (continuing shutdown): {exc}")
    # Kill by exact PID only -- never by image name, in case another OpenWSFZ instance
    # is running elsewhere on this machine.
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    log(f"Daemon (pid={proc.pid}) stopped.")


# ---------------------------------------------------------------------------
# Audio
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


def noise_gap_samples(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SAMPLE_RATE_HZ * SLOT_SECONDS)
    raw = rng.standard_normal(n) * (10.0 ** (GAP_NOISE_DBFS / 20.0))
    return raw.astype(np.float32)


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


# ---------------------------------------------------------------------------
# ALL.TXT / log parsing
# ---------------------------------------------------------------------------

def parse_all_txt_lines(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        rows.append({
            "ts": m.group("ts"),
            "snr": int(m.group("snr")),
            "freq": int(m.group("freq")),
            "msg": " ".join(m.group("msg").split()).upper(),
        })
    return rows


def split_into_cycle_blocks(new_lines: list[str]) -> list[list[str]]:
    """Split a batch of new Debug/Info log lines into per-cycle blocks, using each
    cycle's terminal 'Cycle HH:MM:SS: N decode(s) found.' Info line (always present,
    regardless of Debug level) as the unambiguous delimiter."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in new_lines:
        current.append(line)
        if CYCLE_DELIM_RE.search(line):
            blocks.append(current)
            current = []
    return blocks


def parse_cycle_debug_block(block_lines: list[str]) -> dict:
    total_candidates = 0
    total_decoded = 0
    fail_entries: list[tuple[int, float, float]] = []
    for line in block_lines:
        m = PASS_RE.search(line)
        if m:
            total_candidates += int(m.group(3))
            total_decoded += int(m.group(4))
            continue
        m2 = FAIL_RE.search(line)
        if m2:
            fail_entries.append((int(m2.group(2)), float(m2.group(3)), float(m2.group(4))))
    return {
        "total_candidates": total_candidates,
        "total_decoded": total_decoded,
        "fail_entries": fail_entries,
    }


def weighted_mean_abs_llr(fail_entries: list[tuple[int, float, float]]) -> float | None:
    total_w = sum(fc for fc, _, _ in fail_entries)
    if total_w == 0:
        return None
    return sum(fc * m for fc, m, _ in fail_entries) / total_w


# ---------------------------------------------------------------------------
# Reader with running offset (avoids re-processing already-seen text)
# ---------------------------------------------------------------------------

class TextCursor:
    def __init__(self):
        self._offset = 0

    def new_lines(self, full_text: str) -> list[str]:
        new = full_text[self._offset:]
        self._offset = len(full_text)
        return new.splitlines()


def fetch_full_log() -> str:
    r = requests.get(f"{BASE_URL}/api/v1/logs/full", timeout=10)
    r.raise_for_status()
    return r.text


def fetch_all_txt() -> str:
    if not ALLTXT_PATH.exists():
        return ""
    return ALLTXT_PATH.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Main replay loop
# ---------------------------------------------------------------------------

def replay_one_candidate(candidate: dict, device_idx: int,
                          log_cursor: TextCursor, txt_cursor: TextCursor,
                          gap_seed: int) -> dict:
    wav_path = SAVE_DIR / f"{candidate['ts']}.wav"
    target_wav = load_wav_normalised(wav_path)
    gap_noise = noise_gap_samples(gap_seed)

    # Pre-roll noise (disposable, not boundary-aligned -- only the target play matters).
    play(gap_noise, device_idx)

    # Boundary-aligned target play. Note: unlike the Isolated pass, this WAV's passband
    # contains a real neighbour within 15 Hz by construction (that's what makes it Tight)
    # -- it is played as-is, same as the isolated pass played its (non-adjacent-but-busy)
    # passband as-is. This measures whether the target decodes on replay DESPITE its
    # neighbour still being present, not whether the neighbour is removed.
    b1 = next_boundary()
    wait_for_boundary(b1)
    play_start = datetime.now(timezone.utc)
    play(target_wav, device_idx)

    time.sleep(FLUSH_WAIT_S)

    log_text = fetch_full_log()
    txt_text = fetch_all_txt()
    new_log_lines = log_cursor.new_lines(log_text)
    new_txt_lines = txt_cursor.new_lines(txt_text)

    blocks = split_into_cycle_blocks(new_log_lines)
    play_block = blocks[-1] if blocks else []
    debug_info = parse_cycle_debug_block(play_block)

    new_txt_rows = parse_all_txt_lines("\n".join(new_txt_lines))
    decoded_on_replay = any(
        row["msg"] == candidate["msg"]
        and abs(row["freq"] - candidate["freq_hz"]) <= FREQ_MATCH_TOLERANCE_HZ
        for row in new_txt_rows
    )

    return {
        "ts": candidate["ts"],
        "freq_hz": candidate["freq_hz"],
        "wsjt_snr_db": candidate["wsjt_snr_db"],
        "band": candidate["band"],
        "neighbour_delta_hz": candidate.get("neighbour_delta_hz"),
        "decoded_on_replay": decoded_on_replay,
        "debug_info": debug_info,
        "n_blocks_seen": len(blocks),
        "play_start_utc": play_start.isoformat(),
    }


def main() -> None:
    global TARGET_PER_STRATUM, MAX_TRIES_PER_STRATUM
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-per-stratum", type=int, default=TARGET_PER_STRATUM,
                        help="Reproduced misses to collect per stratum (default: 20; "
                             "pass a small value for a smoke test)")
    parser.add_argument("--max-tries-per-stratum", type=int, default=MAX_TRIES_PER_STRATUM,
                        help="Over-draw cap per stratum (default: 60; "
                             "pass a small value for a smoke test)")
    args = parser.parse_args()
    TARGET_PER_STRATUM = args.target_per_stratum
    MAX_TRIES_PER_STRATUM = args.max_tries_per_stratum

    samples_path = WORK_DIR / "tight_sample_candidates_with_msg.json"
    if not samples_path.exists():
        sys.exit(f"ERROR: {samples_path} not found -- run materialise_tight_sample.py first")
    samples = json.loads(samples_path.read_text(encoding="utf-8"))

    proc = start_daemon()
    results: dict[str, dict] = {}
    try:
        wait_ready()
        configure_daemon()
        time.sleep(STARTUP_WARMUP_S)

        device_idx = select_output_device()
        log_cursor = TextCursor()
        txt_cursor = TextCursor()

        # Prime the cursors so pre-existing startup log noise isn't attributed to trial 0.
        log_cursor.new_lines(fetch_full_log())
        txt_cursor.new_lines(fetch_all_txt())

        for band in BANDS:
            collected: list[dict] = []
            decoded_on_replay_count = 0
            tried = 0
            candidates = samples[band]
            log(f"\n=== Stratum: {band} -- target {TARGET_PER_STRATUM} reproduced, "
                f"up to {MAX_TRIES_PER_STRATUM} tries ===")
            for i, cand in enumerate(candidates):
                if len(collected) >= TARGET_PER_STRATUM or tried >= MAX_TRIES_PER_STRATUM:
                    break
                tried += 1
                r = replay_one_candidate(cand, device_idx, log_cursor, txt_cursor, gap_seed=200000 + i)
                if r["decoded_on_replay"]:
                    decoded_on_replay_count += 1
                    log(f"  [{tried}/{MAX_TRIES_PER_STRATUM}] {cand['ts']} @ {cand['freq_hz']}Hz "
                        f"({cand['wsjt_snr_db']} dB, delta_hz={cand.get('neighbour_delta_hz')}Hz) -> "
                        f"DECODED-ON-REPLAY")
                else:
                    collected.append(r)
                    log(f"  [{tried}/{MAX_TRIES_PER_STRATUM}] {cand['ts']} @ {cand['freq_hz']}Hz "
                        f"({cand['wsjt_snr_db']} dB, delta_hz={cand.get('neighbour_delta_hz')}Hz) -> "
                        f"still missed on replay, total_candidates="
                        f"{r['debug_info']['total_candidates']} "
                        f"({len(collected)}/{TARGET_PER_STRATUM} collected)")

            results[band] = {
                "tried": tried,
                "decoded_on_replay": decoded_on_replay_count,
                "reproduced_collected": collected,
            }

        out = {
            "target_per_stratum": TARGET_PER_STRATUM,
            "max_tries_per_stratum": MAX_TRIES_PER_STRATUM,
            "results": {
                band: {
                    "tried": results[band]["tried"],
                    "decoded_on_replay": results[band]["decoded_on_replay"],
                    "reproduced_collected_n": len(results[band]["reproduced_collected"]),
                    "reproduced_records": [
                        {
                            "ts": r["ts"], "freq_hz": r["freq_hz"], "wsjt_snr_db": r["wsjt_snr_db"],
                            "band": r["band"], "neighbour_delta_hz": r["neighbour_delta_hz"],
                            "total_candidates": r["debug_info"]["total_candidates"],
                            "mean_abs_llr": weighted_mean_abs_llr(r["debug_info"]["fail_entries"]),
                        }
                        for r in results[band]["reproduced_collected"]
                    ],
                }
                for band in BANDS
            },
        }
        out_path = RESULTS_DIR / "tight_replay_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        log(f"\nResults (committed, no message text) written to {out_path}")

        for band in BANDS:
            b = out["results"][band]
            log(f"\n{band}: tried={b['tried']} decoded_on_replay={b['decoded_on_replay']} "
                f"reproduced={b['reproduced_collected_n']}")

    finally:
        stop_daemon(proc)


if __name__ == "__main__":
    main()
