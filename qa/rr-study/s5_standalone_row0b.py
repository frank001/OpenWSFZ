"""
S5-STANDALONE ROW 0b -- stimulus equivalence to July.

Render qa/rr-study/scenarios/s5-noise-wide-n300.json part 0, trials 0-299, under:
  (i)  the current file (main@10bbaad)
  (ii) the July-era file (git show 1e07425:qa/rr-study/scenarios/s5-noise-wide-n300.json)

using the harness's OWN compute_seed / _render_noise / _finalize_playback_samples
(imported, not reimplemented -- per the S5-STANDALONE spec Sec 4 ROW 0b and the
ACTION B / S5-BASELINE ROW 0b precedent). Render only; no device, no playback.

Does not fire  -> 300/300 SHA256 pairs identical.
FIRES          -> any mismatch; report count + differing trial indices.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

RR_STUDY = Path(__file__).resolve().parent
REPO_ROOT = RR_STUDY.parent.parent
sys.path.insert(0, str(RR_STUDY))

from harness.common import compute_seed
from harness.run_scenario import _render_noise, _finalize_playback_samples

CURRENT_FILE = RR_STUDY / "scenarios" / "s5-noise-wide-n300.json"
JULY_REF = "1e07425"
N_TRIALS = 300


def git_show_json(ref: str, path: str) -> dict:
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def main() -> None:
    current = json.loads(CURRENT_FILE.read_text(encoding="utf-8"))
    july = git_show_json(JULY_REF, "qa/rr-study/scenarios/s5-noise-wide-n300.json")

    assert current["id"] == "S5" and july["id"] == "S5", "scenario id mismatch -- compute_seed would not agree by construction"

    part_current = current["parts"][0]
    part_july = july["parts"][0]

    mismatches = []
    hashes = []
    for t in range(N_TRIALS):
        seed_cur = compute_seed(current["id"], 0, t)
        seed_july = compute_seed(july["id"], 0, t)
        buf_cur = _finalize_playback_samples(_render_noise(part_current, seed_cur))
        buf_july = _finalize_playback_samples(_render_noise(part_july, seed_july))
        h_cur = hashlib.sha256(buf_cur.tobytes()).hexdigest()
        h_july = hashlib.sha256(buf_july.tobytes()).hexdigest()
        hashes.append({"trial": t, "seed": seed_cur, "sha256_current": h_cur, "sha256_july": h_july, "match": h_cur == h_july})
        if h_cur != h_july:
            mismatches.append(t)

    fires = len(mismatches) > 0
    result = {
        "row": "ROW 0b -- S5-STANDALONE stimulus equivalence to July",
        "current_file": str(CURRENT_FILE),
        "july_ref": JULY_REF,
        "n_trials": N_TRIALS,
        "n_identical": N_TRIALS - len(mismatches),
        "n_mismatch": len(mismatches),
        "mismatch_trial_indices": mismatches,
        "fires": fires,
        "hashes": hashes,
    }
    out_path = RR_STUDY / "s5_standalone_row0b_result.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="ascii")
    print(f"ROW 0b: {N_TRIALS - len(mismatches)}/{N_TRIALS} trial pairs byte-identical.")
    print(f"FIRES: {fires}")
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
