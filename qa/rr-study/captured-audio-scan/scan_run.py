"""#194 captured-audio scan: per-run measurement stage (read-only; CPU only).

    python scan_run.py measure --run <name> --truth <truth.csv> --ref <ref dir> \
        --audio <...-captured-audio dir> --out <_out/run dir>

Writes (to a gitignored _out/ only; the path is asserted untracked first):
  files.csv            every WAV: side, filename, sha256, class (SCANNED / UNPAIRED / UNPLANNED
                       / REF-MISMATCH) plus MISSING rows for truth slots with no WAV on either side
  sidecar_<side>.csv   one row per SCANNED slot (spec section 4 columns + R0c columns)
  r0c.json             the R0c numbers
Audio only; no ALL.TXT, no message text.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402
from render_reference import read_slots  # noqa: E402

SIDES = ("owsfz", "wsjt-x")
R0C_MARGIN = 0.2          # spec section 3
R0C_MAX_FAIL_FRAC = 0.02  # spec section 3
NONDISCRIM_REF_RHO = 0.5  # (deviation D3, see report) reference-vs-neighbour-reference rho at/above this
METRICS = ["g_db", "tau_ms", "resid_db", "step_db_max", "drift_ppm", "drift_dlag_samples",
           "zero_run_ms", "head_zero_ms", "tail_zero_ms", "click_max", "tile_excess_db", "clip_n"]


def assert_untracked(path: Path) -> None:
    """Refuse to write where git tracks anything (measurement output must never overwrite results/)."""
    r = subprocess.run(["git", "ls-files", "--", str(path)], capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parent)
    if r.stdout.strip():
        raise SystemExit(f"REFUSING: {path} contains tracked files: {r.stdout[:200]}")
    ig = subprocess.run(["git", "check-ignore", "-q", str(path / "probe.csv")],
                        cwd=Path(__file__).resolve().parent)
    if ig.returncode != 0:
        raise SystemExit(f"REFUSING: {path} is not gitignored")


def stem_dt(stem: str) -> datetime:
    return datetime.strptime(stem[:13], "%y%m%d_%H%M%S")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["measure"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    assert_untracked(out)
    t_start = time.time()

    slots = read_slots(Path(a.truth))
    slots.sort(key=lambda s: s["cycle_utc"])
    for s in slots:
        s["dt"] = datetime.strptime(s["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ")
    by_dt = {s["dt"]: s for s in slots}
    refs = {s["key"]: np.load(Path(a.ref) / f"{s['key']}.npy").astype("float64") for s in slots}
    ref_manifest = json.loads((Path(a.ref) / "manifest.json").read_text())

    # --- inventory: slot <-> WAV mapping (filename yymmdd_hhmmss == truth cycle_utc, both apps)
    wavs = {}
    for side in SIDES:
        d = Path(a.audio) / side / "wav"
        wavs[side] = {stem_dt(p.stem): p for p in sorted(d.glob("*.wav"))}
        extra = [p.name for p in d.glob("*.wav") if len(p.stem) != 13]
        if extra:
            raise SystemExit(f"suffixed WAV names present (collision files) on {side}: {extra[:3]}")
    file_rows = []
    paired = []
    for s in slots:
        have = [side for side in SIDES if s["dt"] in wavs[side]]
        if len(have) == 2:
            paired.append(s)
        elif len(have) == 0:
            file_rows.append({"side": "-", "filename": f"(slot {s['cycle_utc']})", "sha256": "", "class": "MISSING"})
    paired_dts = {s["dt"] for s in paired}
    for side in SIDES:
        for dt, p in wavs[side].items():
            if dt in paired_dts:
                continue
            cls = "UNPAIRED" if dt in by_dt else "UNPLANNED"
            file_rows.append({"side": side, "filename": p.name, "sha256": sc.sha256_file(p), "class": cls})

    # --- measurement, paired slots only
    idx_of = {s["key"]: i for i, s in enumerate(slots)}
    # reference-vs-neighbour-reference rho (does the reference discriminate between slots?)
    refrho = {}
    for s in paired:
        i = idx_of[s["key"]]
        v = 0.0
        for j in (i - 1, i + 1):
            if 0 <= j < len(slots):
                v = max(v, sc.rho_peak(refs[slots[j]["key"]], refs[s["key"]])[0])
        refrho[s["key"]] = v
    rows = {side: [] for side in SIDES}
    for n, s in enumerate(paired):
        i = idx_of[s["key"]]
        for side in SIDES:
            w = sc.read_wav(wavs[side][s["dt"]])
            m = sc.measure(w["x"], refs[s["key"]])
            nb = 0.0
            for j in (i - 1, i + 1):
                if 0 <= j < len(slots):
                    nb = max(nb, sc.rho_peak(w["x"].astype("float64") / 32768.0, refs[slots[j]["key"]])[0])
            row = {"slot": s["key"], "cycle_utc": s["cycle_utc"], "scenario": s["scenario_id"],
                   "part": s["part_index"], "n_truth_rows": s["n_truth_rows"],
                   "oversize": int(ref_manifest[s["key"]]["n_samples_48k"] != 720000),
                   "after_oversize": 0, "wav_sha256": w["sha256"], "fs": w["fs"], "bits": w["bits"],
                   "channels": w["channels"], "n_samples": w["n_samples"],
                   "rho_peak": m["rho_peak"], "rho_sign": m["rho_sign"], "rho_neighbour_max": nb,
                   "ref_vs_neighbour_ref_rho": refrho[s["key"]], "lag_ambiguous": int(m["lag_ambiguous"]),
                   "g_sign": m["g_sign"], "n_support": m["n_support"]}
            for k in METRICS:
                row[k] = m[k]
            rows[side].append(row)
        if (n + 1) % 50 == 0:
            print(f"  {n + 1}/{len(paired)} slots", flush=True)
    for side in SIDES:
        prev_over = False
        for r in rows[side]:
            r["after_oversize"] = int(prev_over)
            prev_over = bool(r["oversize"])

    # --- R0c: own rho must beat the run's largest neighbour rho by >= 0.2 (discriminating slots)
    r0c = {"margin": R0C_MARGIN, "max_fail_fraction": R0C_MAX_FAIL_FRAC, "sides": {}}
    mism = {side: set() for side in SIDES}
    for side in SIDES:
        disc = [r for r in rows[side] if r["ref_vs_neighbour_ref_rho"] < NONDISCRIM_REF_RHO]
        nondisc = [r for r in rows[side] if r["ref_vs_neighbour_ref_rho"] >= NONDISCRIM_REF_RHO]
        nb_max = max(r["rho_neighbour_max"] for r in disc)
        # R0c exactly as written: own rho must beat the RUN's largest neighbour rho by >= 0.2.
        fails_spec = [r["slot"] for r in rows[side] if r["rho_peak"] - nb_max < R0C_MARGIN]
        fails_spec_disc = [r["slot"] for r in disc if r["rho_peak"] - nb_max < R0C_MARGIN]
        # Amendment A1 (proposed; used for classification): the same margin, per slot, against
        # that slot's OWN neighbours, on slots whose reference differs from its neighbours'.
        fails = [r["slot"] for r in disc if r["rho_peak"] - r["rho_neighbour_max"] < R0C_MARGIN]
        mism[side] = set(fails)
        r0c["sides"][side] = {
            "paired_slots": len(rows[side]), "discriminating": len(disc), "nondiscriminating": len(nondisc),
            "nondiscriminating_by_scenario": {sc_: sum(1 for r in nondisc if r["scenario"] == sc_)
                                              for sc_ in sorted({r["scenario"] for r in nondisc})},
            "largest_neighbour_rho_run": nb_max,
            "own_rho_min_disc": min(r["rho_peak"] for r in disc),
            "own_rho_median_disc": float(np.median([r["rho_peak"] for r in disc])),
            "spec_literal_fail_all_slots": len(fails_spec),
            "spec_literal_fail_fraction_all": len(fails_spec) / max(1, len(rows[side])),
            "spec_literal_fail_discriminating": len(fails_spec_disc),
            "spec_literal_PASS": bool(len(fails_spec) / max(1, len(rows[side])) <= R0C_MAX_FAIL_FRAC),
            "A1_fail_slots": fails, "A1_fail_fraction": len(fails) / max(1, len(disc)),
            "A1_PASS": bool(len(fails) / max(1, len(disc)) <= R0C_MAX_FAIL_FRAC),
        }
    for side in SIDES:
        for r in rows[side]:
            r["nondiscriminating"] = int(r["ref_vs_neighbour_ref_rho"] >= NONDISCRIM_REF_RHO)
            r["ref_mismatch"] = int(r["slot"] in mism[side])
            p = wavs[side][datetime.strptime(r["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ")]
            file_rows.append({"side": side, "filename": p.name, "sha256": r["wav_sha256"],
                              "class": "REF-MISMATCH" if r["ref_mismatch"] else "SCANNED"})

    def write(path, recs):
        recs = list(recs)
        if not recs:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(recs[0].keys()), lineterminator="\n")
            wr.writeheader()
            wr.writerows(recs)

    write(out / "files.csv", file_rows)
    for side in SIDES:
        write(out / f"sidecar_{side.replace('-', '')}.csv", rows[side])
    r0c["wall_seconds"] = round(time.time() - t_start, 1)
    r0c["n_slots_truth"] = len(slots)
    r0c["n_paired"] = len(paired)
    (out / "r0c.json").write_text(json.dumps(r0c, indent=1), encoding="utf-8")
    print(json.dumps(r0c, indent=1))


if __name__ == "__main__":
    main()
