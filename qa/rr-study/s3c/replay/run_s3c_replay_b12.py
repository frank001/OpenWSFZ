"""S3c replay of batteries 1 and 2 (QA, test-only). Architect ruling 2026-10-05, section 4b (S3Y1-3). Harness UNCHANGED (db2da962).

    python -X utf8 run_s3c_replay_b12.py

Per battery (1 = 2026-10-02-96077a0, 2 = 2026-10-03-96077a0; audio in artefacts/_rr_baseline194_daemon_output/cycle-audio) and per arm
(cddd7e34 no early; 766f9cc2 early ON), a FRESH process decodes the battery's 12 archived S3c cycles (flag ON, nhard 40, both batches)
and is scored with the battery's own scorer against that battery's playback log. No stop rule (no live count to reproduce on new audio):
the arms check each other.

READING TABLE as code (ruling 4b), applied to S3c-E50 (E -2.00) per battery after the arms are checked:
  arms disagree by more than 2           -> the replay is the finding; the rest is NOT read
  both arms <= 24 (each battery)         -> AUDIO
  both arms >= 28 (each battery)         -> LIVE PATH
  25..27                                 -> not separable at n = 32, descriptive only
Prediction thresholds printed for the Architect's scoring: S3Y1 arms within 2 on each battery; S3Y2 Audio on both batteries.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_s3c_replay as R  # noqa: E402  (unchanged driver of the battery-3 replay: pins, preflight, harness binaries)

SC = R.SC
BAT = {1: R.RR / "results" / "2026-10-02-96077a0", 2: R.RR / "results" / "2026-10-03-96077a0"}
AUDIO = Path(r"D:\Projects\claude\OpenWSFZ\artefacts\_rr_baseline194_daemon_output\cycle-audio")
AGREE, LOW, HIGH = 2, 24, 28
TARGET = R.TARGET_PART


def stamps_of(battery_dir: Path) -> list[str]:
    R.BATTERY = battery_dir            # R.stamps() reads the playback log of R.BATTERY
    R.WAV_DIR = AUDIO
    return R.stamps()


def one(battery: int, arm: str, exe_dir: Path, early: str, pin: str) -> dict:
    R.BATTERY, R.WAV_DIR = BAT[battery], AUDIO
    R.OUT = R.REPO / "artefacts" / "20261005_s3c_replay" / f"b{battery}"
    d = R.run_arm(arm, exe_dir, early, pin)
    return R.score_arm(d)


def main() -> None:
    R.preflight()
    out = {}
    for b in (1, 2):
        stamps_of(BAT[b])
        out[b] = {"old": one(b, "old", R.BIN / "bin_old", "na", R.OLD_DLL),
                  "new_early_on": one(b, "new", R.BIN / "bin_new", "on", R.NEW_DLL)}
        print(f"battery {b}: cddd7e34 {out[b]['old']}  |  766f9cc2 early ON {out[b]['new_early_on']}", flush=True)
    verdict = {}
    for b in (1, 2):
        x_old, x_new = out[b]["old"][TARGET], out[b]["new_early_on"][TARGET]
        if abs(x_old - x_new) > AGREE:
            verdict[b] = "ARMS DISAGREE: the replay is the finding; the rest is not read"
        elif x_old <= LOW and x_new <= LOW:
            verdict[b] = "AUDIO"
        elif x_old >= HIGH and x_new >= HIGH:
            verdict[b] = "LIVE PATH"
        else:
            verdict[b] = "NOT SEPARABLE (25..27 or straddling), descriptive only"
    s3y1 = all(abs(out[b]["old"][TARGET] - out[b]["new_early_on"][TARGET]) <= AGREE for b in (1, 2))
    s3y2 = all(v == "AUDIO" for v in verdict.values())
    res = {"scores": out, "reading": verdict, "S3Y1_arms_agree_within_2_each_battery": s3y1, "S3Y2_audio_on_both": s3y2}
    p = R.REPO / "artefacts" / "20261005_s3c_replay" / "results_b12.json"
    p.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
