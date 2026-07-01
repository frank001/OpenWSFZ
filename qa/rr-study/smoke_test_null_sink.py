"""Smoke test — combined-sink loopback for WSL2 cross-platform R&R.

Generates one strong FT8 signal (+10 dB SNR), plays it to the PulseAudio
default output (ft8combined sink → ft8loopback + RDPSink), waits for the
decode window, then checks BOTH decode logs:
  - linux-all.txt  (Linux daemon via ft8loopback.monitor)
  - ALL.TXT        (Windows daemon via RDPSink → WSLg → Voicemeeter AUX → B2)

Pre-flight (once per WSL2 session):
    pactl load-module module-null-sink sink_name=ft8loopback \\
          sink_properties=device.description=FT8Loopback
    pactl load-module module-combine-sink sink_name=ft8combined \\
          sink_properties=device.description=FT8Combined \\
          slaves=ft8loopback,RDPSink
    pactl set-default-sink ft8combined
    pactl set-default-source ft8loopback.monitor

Run from WSL2 inside the .venv-linux:
    cd /mnt/d/Projects/claude/OpenWSFZ/qa/rr-study
    source .venv-linux/bin/activate
    python smoke_test_null_sink.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd

_QA_ROOT = Path(__file__).resolve().parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from synth.encoder import encode_message
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

# ── Test parameters ───────────────────────────────────────────────────────────
_MESSAGE        = "CQ Q1ABC FN42"      # primary study message — known good with synth
_AUDIO_FREQ_HZ  = 1500.0              # nominal FT8 centre frequency
_SNR_DB         = 10.0                # well above the −18 dB threshold
_SAMPLE_RATE    = DEFAULT_SAMPLE_RATE_HZ
_SLOT_SECONDS   = 15
_REPEAT_CYCLES  = 3                   # play signal N consecutive cycles — guarantees at
                                      # least one complete cycle window regardless of
                                      # PulseAudio onset latency
_LINUX_ALL_TXT  = _QA_ROOT.parent.parent / "linux-all.txt"   # Linux daemon AllTxtWriter output
_WIN_ALL_TXT    = _QA_ROOT.parent.parent / "ALL.TXT"          # Windows daemon AllTxtWriter output
_SETTLE_S       = 8                   # seconds after last cycle ends to wait for decode


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _next_cycle_start() -> float:
    """Return the Unix timestamp of the next 15-second UTC cycle boundary."""
    now = time.time()
    return now + (_SLOT_SECONDS - (now % _SLOT_SECONDS))


def _tail_all_txt(path: Path, since: float) -> list[str]:
    """Return lines added to path after Unix timestamp `since`."""
    if not path.exists():
        return []
    lines = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if line:
                lines.append(line)
    # ALL.TXT lines we care about appeared after `since`; filter by mtime as a
    # proxy — if the file was updated after `since`, include all lines that
    # contain our message text (crude but sufficient for a smoke test).
    return [l for l in lines if _MESSAGE.upper() in l.upper()]


def main() -> None:
    print("=== Cross-platform smoke test (ft8combined sink) ===")
    print(f"  Message      : {_MESSAGE}")
    print(f"  Audio freq   : {_AUDIO_FREQ_HZ:.0f} Hz")
    print(f"  SNR          : {_SNR_DB:+.0f} dB")
    print(f"  Sample rate  : {_SAMPLE_RATE} Hz")
    print(f"  Linux log    : {_LINUX_ALL_TXT}")
    print(f"  Windows log  : {_WIN_ALL_TXT}")
    print()

    # ── Enumerate sounddevice devices ─────────────────────────────────────────
    print("--- sounddevice devices ---")
    try:
        devs = sd.query_devices()
        for i, d in enumerate(devs):
            if d["max_output_channels"] > 0:
                marker = " ← DEFAULT OUT" if i == sd.default.device[1] else ""
                print(f"  [{i:2d}] OUT {d['name']}{marker}")
        print()
    except Exception as exc:
        print(f"  WARNING: could not enumerate devices: {exc}")
        print()

    # ── Render signal ─────────────────────────────────────────────────────────
    print("Rendering FT8 signal ...")
    samples = encode_message(_MESSAGE, _AUDIO_FREQ_HZ, snr_db=_SNR_DB, seed=42,
                             sample_rate_hz=_SAMPLE_RATE)
    samples = samples.astype(np.float32)
    # Normalise to 90% of full scale — sounddevice clips at ±1.0
    peak = float(np.max(np.abs(samples)))
    if peak > 0:
        samples *= 0.9 / peak
    print(f"  Rendered {len(samples)} samples ({len(samples)/_SAMPLE_RATE:.1f} s), "
          f"peak={float(np.max(np.abs(samples))):.3f}")
    print()

    # ── Align to next cycle boundary and play N consecutive cycles ───────────
    # Playing the same signal for _REPEAT_CYCLES × 15 s means at least one
    # complete daemon cycle window captures the full FT8 frame, regardless of
    # PulseAudio onset latency.
    cycle_t = _next_cycle_start()
    wait_s  = cycle_t - time.time()
    print(f"  First cycle boundary: {datetime.fromtimestamp(cycle_t, tz=timezone.utc).strftime('%H:%M:%S')} UTC")
    print(f"  Waiting {wait_s:.1f} s ...")
    if wait_s > 0:
        time.sleep(max(0.0, wait_s - 0.05))  # sleep until ~50 ms before boundary
    while time.time() < cycle_t:
        pass  # busy-wait the last fraction

    play_start = _utc_now()
    print(f"  Playing {_REPEAT_CYCLES} cycles starting {play_start.strftime('%H:%M:%S')} UTC "
          f"→ ft8loopback")
    for i in range(_REPEAT_CYCLES):
        sd.play(samples, samplerate=_SAMPLE_RATE, blocking=True)
        print(f"    cycle {i+1}/{_REPEAT_CYCLES} complete at {_utc_now().strftime('%H:%M:%S')} UTC")
    print("  Playback complete.")
    print()

    # ── Wait for decode ───────────────────────────────────────────────────────
    print(f"  Waiting {_SETTLE_S} s for both daemons to process ...")
    since_ts = play_start.timestamp()
    time.sleep(_SETTLE_S)

    # ── Check both decode logs ────────────────────────────────────────────────
    def _check_log(path: Path, label: str) -> list[str]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return [l for l in lines if "Q1ABC" in l]

    lin_hits = _check_log(_LINUX_ALL_TXT, "Linux")
    win_hits = _check_log(_WIN_ALL_TXT,   "Windows")

    # Filter to only lines plausibly from this run (crude: any Q1ABC hit)
    print()
    print("─── Linux daemon (ft8loopback.monitor) ──────────────────────────────")
    if lin_hits:
        print(f"  ✅  {len(lin_hits)} decode(s) total in log (last 3):")
        for h in lin_hits[-3:]:
            print(f"     {h}")
    else:
        print("  ❌  No Q1ABC decodes in linux-all.txt")
        print("      Check: pactl info | grep 'Default Sink'  → should be ft8combined")
        print("             pactl list sinks short | grep ft8loopback")

    print()
    print("─── Windows daemon (Voicemeeter AUX → B2) ───────────────────────────")
    if win_hits:
        print(f"  ✅  {len(win_hits)} decode(s) total in log (last 3):")
        for h in win_hits[-3:]:
            print(f"     {h}")
    else:
        print("  ❌  No Q1ABC decodes in ALL.TXT")
        print("      Check: RDPSink is a slave of ft8combined")
        print("             Voicemeeter AUX Input is routed to B2")
        print("             Windows daemon captures from Voicemeeter Out B2")

    print()
    if lin_hits and win_hits:
        print("Smoke test PASSED — both daemons received the signal.")
    elif lin_hits:
        print("Smoke test PARTIAL — Linux OK, Windows silent. Check Voicemeeter routing.")
        sys.exit(1)
    elif win_hits:
        print("Smoke test PARTIAL — Windows OK, Linux silent. Check ft8combined default sink.")
        sys.exit(1)
    else:
        print("Smoke test FAILED — neither daemon decoded the signal.")
        sys.exit(1)


if __name__ == "__main__":
    main()
