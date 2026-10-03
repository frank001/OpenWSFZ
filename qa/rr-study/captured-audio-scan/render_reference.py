"""Reference re-render for the #194 captured-audio scan (read-only; CPU only).

Renders every truth.csv slot of a synthetic R&R run with the harness's OWN functions
(imported from a harness root the caller chooses: a detached worktree of the commit
that produced the run, or the current tree for R0b), finished exactly as playback
finished it, then 48 -> 12 kHz with the same resample_poly(up=1, down=4) as
``_dump_slot_wav``. The result is kept as float32 (no int16 rounding).

Nothing here re-implements a render step: the only code that is ours is the
scenario dispatch (which scenario id calls which ``_render_*``), which mirrors the
inline if/elif chain in ``run_scenario._run`` (S8/schema-keyed, S5, S7, S4, else
single) and is cross-checked against truth.csv by recomputing every seed with the
harness's ``compute_seed``.

Usage:
    python scan_render_reference.py --harness-root <wt>/qa/rr-study \
        --truth <truth.csv> --out <dir>
Writes <out>/<slot_key>.npy (float32, 12 kHz) and <out>/manifest.json
(slot_key -> {sha256, n_samples_12k, n_samples_48k, buffer_start_s}).
slot_key = <scenario>_p<part:03d>_t<trial:03d>_s<seed>.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


def slot_key(scenario_id: str, part: int, trial: int, seed: int) -> str:
    return f"{scenario_id}_p{part:03d}_t{trial:03d}_s{seed}"


def read_slots(truth_csv: Path) -> list[dict]:
    """Unique render slots, in truth order. One slot per (scenario, part, trial, seed)."""
    seen: dict[tuple, dict] = {}
    with open(truth_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            k = (r["scenario_id"], int(r["part_index"]), int(r["trial_index"]), int(r["seed"]))
            if k not in seen:
                seen[k] = {"scenario_id": k[0], "part_index": k[1], "trial_index": k[2],
                           "seed": k[3], "cycle_utc": r["cycle_utc"], "key": slot_key(*k),
                           "n_truth_rows": 0}
            seen[k]["n_truth_rows"] += 1
            if seen[k]["cycle_utc"] != r["cycle_utc"]:
                raise SystemExit(f"slot {k} has two cycle_utc values in truth.csv")
    return list(seen.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness-root", required=True, help="<worktree>/qa/rr-study")
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    root = Path(a.harness_root).resolve()
    sys.path.insert(0, str(root))
    import numpy as np
    from scipy.signal import resample_poly
    from harness import run_scenario as rs
    from harness.common import compute_seed

    scen_dir = root / "scenarios"
    messages = rs._load_messages(scen_dir)
    # The run's own scenario registry (run_study._SCENARIO_REGISTRY at the same commit).
    import importlib
    run_study = importlib.import_module("run_study")
    by_id = {k: Path(v) for k, v in run_study._SCENARIO_REGISTRY.items()}
    scenarios = {}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for s in read_slots(Path(a.truth)):
        sid = s["scenario_id"]
        if sid not in scenarios:
            scenarios[sid] = rs._load_scenario(by_id[sid], messages)
        sc = scenarios[sid]
        seed = compute_seed(sid, s["part_index"], s["trial_index"])
        if seed != s["seed"]:
            raise SystemExit(f"seed mismatch for {s['key']}: harness {seed} vs truth {s['seed']}")
        parts = sc.get("parts", [{"part_index": 0}])
        part = next((p for p in parts if p["part_index"] == s["part_index"]), None)
        if part is None and "signals" not in sc:
            raise SystemExit(f"{s['key']}: part_index not in scenario {sid}")
        buffer_start_s = 0.0
        if "signals" in sc:                                   # S8 / S8HN (schema keyed)
            samples, _ = rs._render_band_scene(sc, seed)
        elif sid == "S5":
            samples = rs._render_noise(part, seed)
        elif sid == "S7":
            samples, _ = rs._render_compound(sc, part, seed)
        elif sid == "S4":
            samples, _ = rs._render_multi(sc, part, s["trial_index"], seed)
        elif "e4_ladder" in sc or "pairs" in sc:
            raise SystemExit(f"{sid}: E4/pairs scenarios are out of scope for this renderer")
        else:                                                  # S1, S1b, S2, S3, S3b, S11
            samples, buffer_start_s = rs._render_single(sc, part, s["trial_index"], seed)
        n48 = len(samples)
        fin = rs._finalize_playback_samples(np.asarray(samples))
        ref12 = resample_poly(np.asarray(fin, dtype="float64"), up=1, down=4).astype("float32")
        np.save(out / f"{s['key']}.npy", ref12)
        manifest[s["key"]] = {
            "sha256": hashlib.sha256(ref12.tobytes()).hexdigest(),
            "n_samples_12k": int(len(ref12)), "n_samples_48k": int(n48),
            "buffer_start_s": float(buffer_start_s),
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    print(f"rendered {len(manifest)} slots -> {out}")


if __name__ == "__main__":
    main()
