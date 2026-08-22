"""QA pre-flight check for the 2026-08-21 S1-S8 R&R study run.

Non-interactive stand-in for harness/warmup.py's own operator-eyeball
confirmation (RUNBOOK.md 5.3: "Captain's choice ... I cannot see the GUI").
Reuses the EXACT same warm-up signal (harness.warmup._render_warmup_cycle,
same message/SNR/freq/seed) and the same device-selection/cycle-boundary
helpers, unmodified -- HK-018, not reimplemented. Confirmation is read back
from both apps' own ALL.TXT files (the instrument's own record, HK-027)
rather than asked of a human watching a GUI panel this session cannot see.

Exit 0 iff BOTH WSJT-X and OpenWSFZ ALL.TXT gained a new line containing
the warm-up message text after the cycle. Exit 1 otherwise, with a report
of which side(s) failed.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness.warmup import _render_warmup_cycle, _WARMUP_MESSAGE, _POST_CYCLE_DECODE_SETTLE_S
from harness.run_scenario import _select_device, _next_cycle_boundary, _wait_for_cycle
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

WSJT_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
OWSFZ_ALL_TXT = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")


def tail_has(path: Path, before_lines: int, needle: str) -> tuple[bool, str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = lines[before_lines:]
    hit = any(needle in ln for ln in new_lines)
    sample = new_lines[-1] if new_lines else "(no new lines)"
    return hit, sample


def main() -> int:
    import sounddevice as sd

    device = "Voicemeeter AUX Input"
    device_idx = _select_device(device)

    wsjt_before = len(WSJT_ALL_TXT.read_text(encoding="utf-8", errors="replace").splitlines()) if WSJT_ALL_TXT.exists() else 0
    owsfz_before = len(OWSFZ_ALL_TXT.read_text(encoding="utf-8", errors="replace").splitlines()) if OWSFZ_ALL_TXT.exists() else 0
    print(f"Before: WSJT-X ALL.TXT lines={wsjt_before}, OpenWSFZ ALL.TXT lines={owsfz_before}")

    samples = _render_warmup_cycle()
    boundary_ts = _next_cycle_boundary()
    cycle_utc = _wait_for_cycle(boundary_ts)
    print(f"Playing warm-up ({_WARMUP_MESSAGE!r}) at {cycle_utc.strftime('%H:%M:%S')} UTC ...")
    sd.play(samples, samplerate=DEFAULT_SAMPLE_RATE_HZ, device=device_idx, blocking=False)
    sd.wait()
    print(f"Played. Waiting {_POST_CYCLE_DECODE_SETTLE_S:.0f}s settle ...")
    time.sleep(_POST_CYCLE_DECODE_SETTLE_S + 2.0)  # small margin over the harness's own settle

    wsjt_hit, wsjt_sample = tail_has(WSJT_ALL_TXT, wsjt_before, "Q1ABC")
    owsfz_hit, owsfz_sample = tail_has(OWSFZ_ALL_TXT, owsfz_before, "Q1ABC")

    print(f"WSJT-X   new-line decode of Q1ABC: {wsjt_hit}  (sample: {wsjt_sample})")
    print(f"OpenWSFZ new-line decode of Q1ABC: {owsfz_hit}  (sample: {owsfz_sample})")

    if wsjt_hit and owsfz_hit:
        print("PASS: both apps decoded the warm-up cycle.")
        return 0
    print("FAIL: at least one app did not decode the warm-up cycle.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
