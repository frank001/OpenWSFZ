#!/usr/bin/env python3
"""COH-GAIN: the extraction runner (offline Python, detached-friendly, resumable).

Modes (spec section 7):
  v2     the 200 synthetic off-lattice signals          -> synthetic.csv
  pilot  the 50 frozen pilot rows, all arms, DISCARDED  -> pilot.csv, timing_pilot.csv  (+ the projected CPU hours and the 1-in-10 / 1-in-20 choice)
  main   the frozen rows of the chosen sample           -> rows.csv   (rows_part.csv while running; resumable by cycle)
  v5     a second FRESH process over the first 300 rows -> v5.csv

HK-037 / NFR-021: text and bit arrays live only inside cg_common.evaluate_signal; this file persists NUMERIC fields. The DLL is the run-folder copy
(Amendment-1 discipline: never a build directory), SHA-256 verified at load and recorded at the start and at the end of every run (pins.jsonl).
Rows are independent, so cycles are distributed over --workers processes; the output is sorted by (cycle_index, widx), so it does not depend on the
worker count (V5 shows it).

  python qa/rr-study/coh-gain/cg_run.py --mode v2 --out <run dir>
  python qa/rr-study/coh-gain/cg_run.py --mode pilot|main|v5 --out <run dir> --workers 4 [--modulus 10|20]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_synth as SY  # noqa: E402
import cg_rows as ROWS  # noqa: E402
import wavio  # noqa: E402

_DEC = None
_WS = None


def _init(dll_path):
    global _DEC, _WS
    _DEC = CG.load_decoder(dll_path)
    _WS = SEL.read_alltxt(SEL.WS_ALLTXT)         # text stays in this worker process


def _work_cycle(task):
    """task = (stamp, [row lists]); returns [(meta + numeric fields), ...] and the CPU seconds spent. Text never leaves this function."""
    stamp, rows = task
    cpu0 = time.process_time()
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    lines = _WS.get(stamp, [])
    out = []
    for (ci, _stamp, widx, ws_freq, ws_dt, ws_snr, ws_load, live_hit, _m20) in rows:
        rec = {"cycle_index": ci, "widx": widx, "ws_snr": ws_snr, "ws_load": ws_load, "live_hit": live_hit}
        ok_line = widx < len(lines) and lines[widx][0] == ws_snr and lines[widx][2] == ws_freq
        if not ok_line:
            rec["fault"] = 1
        else:
            rec.update(CG.evaluate_signal(_DEC, pcm, float(ws_freq), CG.anchor_time(ws_dt), lines[widx][3]))
        out.append(rec)
    return out, time.process_time() - cpu0


def _synth_one(i_spec):
    return SY.evaluate(_DEC, i_spec)


def _pin(out, mode, when, dll_path):
    sha = CG.file_sha256(dll_path)
    with open(os.path.join(out, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": mode, "when": when,
                             "libft8_sha256": sha, "pinned": CG.DLL_PIN, "match": sha == CG.DLL_PIN}) + "\n")
    assert sha == CG.DLL_PIN, ("DLL differs from the pin", sha)


def _write_csv(path, columns, records):
    with open(path, "w", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for r in records:
            w.writerow([r.get(c, "") for c in columns])


def _row_columns():
    return ROWS.CSV_COLUMNS


def _load_frozen():
    spec = json.load(open(SEL.ROWS_JSON))
    return spec


def _group(rows):
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault((r[0], r[1]), []).append(r)
    return [(stamp, rs) for (_ci, stamp), rs in by.items()]


def _run_rows(rows, out, name, workers, dll, resume=True):
    """Runs every row (grouped by cycle); resumable through <name>_part.csv; writes <name>.csv sorted. Returns (records, cpu_by_cycle)."""
    part = os.path.join(out, f"{name}_part.csv")
    cols = _row_columns()
    done = {}
    if resume and os.path.exists(part):
        for r in csv.DictReader(open(part, newline="", encoding="utf-8")):
            done.setdefault(int(float(r["cycle_index"])), []).append(r)
    tasks = [t for t in _group(rows) if t[1][0][0] not in done]
    cpu = {}
    newfile = not os.path.exists(part) or not done
    with open(part, "a" if done else "w", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if newfile:
            w.writerow(cols)
        with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dll,)) as ex:
            futs = {ex.submit(_work_cycle, t): t[1][0][0] for t in tasks}
            n = 0
            for f in as_completed(futs):
                recs, secs = f.result()
                cpu[futs[f]] = (len(recs), secs)
                for r in recs:
                    w.writerow([r.get(c, "") for c in cols])
                fh.flush()
                n += 1
                if n % 10 == 0:
                    print(f"  {n}/{len(tasks)} cycles", flush=True)
    records = ROWS.load_rows(part)
    return records, cpu


def _run_synth(a, set_path, csv_name):
    spec = json.load(open(set_path))
    cols = ["i", "fault"] + CG.ROW_FIELDS[1:] + ["err_df", "err_dt", "err_df_oracle", "err_dt_oracle"]
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll,)) as ex:
        recs = list(ex.map(_synth_one, spec, chunksize=4))
    recs.sort(key=lambda r: r["i"])
    _write_csv(os.path.join(a.out, csv_name), cols, recs)
    return spec


def mode_v2(a):
    """The gated tier (-14 dB, row V2 under Amendment 1's (b')) and the DESCRIPTIVE -20 dB tier (V2-T). A tier already on disk is NOT re-rendered or
    re-run (Amendment 1 item 1: re-evaluate the SAME 200 signals), unless --force."""
    if a.force or not os.path.exists(os.path.join(a.out, "synthetic.csv")):
        assert len(_run_synth(a, SY.SET_PATH, "synthetic.csv")) == CG.V2_N
    if a.force or not os.path.exists(os.path.join(a.out, "synthetic_t.csv")):
        assert len(_run_synth(a, SY.SET_T_PATH, "synthetic_t.csv")) == CG.V2T_N
    ok, det = ROWS.row_v2(ROWS.load_synth(os.path.join(a.out, "synthetic.csv"), SY.SET_PATH))
    tdesc = ROWS.v2t_descriptive(ROWS.load_synth(os.path.join(a.out, "synthetic_t.csv"), SY.SET_T_PATH))
    print(json.dumps({"V2_pass": ok, **det, "V2T_descriptive_minus20dB": tdesc}, indent=1, default=str))


def mode_pilot(a):
    frozen = _load_frozen()
    rows = frozen["pilot_rows"]
    t0 = time.time()
    recs, cpu = _run_rows(rows, a.out, "pilot", a.workers, a.dll, resume=False)
    tot_cpu = sum(s for _n, s in cpu.values())
    per_row = tot_cpu / len(rows)
    n10, n20 = frozen["counts"]["rows_mod10"], frozen["counts"]["rows_mod20"]
    proj10 = per_row * n10 / 3600.0
    choice = CG.SAMPLE_MODULUS_PRIMARY if proj10 <= CG.PILOT_MAX_CPU_HOURS else CG.SAMPLE_MODULUS_FALLBACK
    info = {"pilot_rows": len(rows), "cpu_s_per_row": per_row, "rows_mod10": n10, "rows_mod20": n20, "projected_cpu_hours_mod10": proj10,
            "projected_cpu_hours_mod20": per_row * n20 / 3600.0, "rule": f"> {CG.PILOT_MAX_CPU_HOURS} h CPU for all four arms => 1-in-20",
            "chosen_modulus": choice, "rows_chosen": n10 if choice == 10 else n20, "wall_s": time.time() - t0, "workers": a.workers}
    json.dump(info, open(os.path.join(a.out, "pilot_result.json"), "w"), indent=1)
    print(json.dumps(info, indent=1))


def _chosen_rows(frozen, modulus):
    return [r for r in frozen["rows"] if modulus == 10 or r[8]]


def mode_main(a):
    frozen = _load_frozen()
    rows = _chosen_rows(frozen, a.modulus)
    print(f"main: modulus {a.modulus}, {len(rows)} rows, {len({r[0] for r in rows})} cycles, workers {a.workers}", flush=True)
    _pin(a.out, "main", "start", a.dll)
    recs, cpu = _run_rows(rows, a.out, "rows", a.workers, a.dll)
    _write_csv(os.path.join(a.out, "rows.csv"), _row_columns(), recs)
    with open(os.path.join(a.out, "timing_main.csv"), "w") as fh:
        fh.write("cycle_index,rows,cpu_s\n" + "".join(f"{c},{n},{s:.3f}\n" for c, (n, s) in sorted(cpu.items())))
    _pin(a.out, "main", "end", a.dll)
    print("main done:", len(recs), "rows")


def mode_v5(a):
    frozen = _load_frozen()
    rows = sorted(_chosen_rows(frozen, a.modulus), key=lambda r: (r[0], r[2]))[:CG.V5_ROWS]
    # whole cycles only: the first 300 rows may end mid-cycle; run the rows of those cycles that are in the first 300 (same grouping as main)
    recs, _cpu = _run_rows(rows, a.out, "v5", 1, a.dll, resume=False)
    _write_csv(os.path.join(a.out, "v5.csv"), _row_columns(), recs)
    print("v5 done:", len(recs), "rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["v2", "pilot", "main", "v5"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dll", default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="v2 mode: re-run tiers already on disk")
    ap.add_argument("--modulus", type=int, default=CG.SAMPLE_MODULUS_PRIMARY, choices=[10, 20])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    a.dll = a.dll or os.path.join(a.out, "bin", "libft8_20260058.dll")
    # frozen inputs: asserted BEFORE anything is extracted (a changed file refuses to run)
    if a.mode == "v2":
        assert CG.sha256_lf(SY.SET_PATH) == CG.SYNTH_SHA256 and CG.sha256_lf(SY.SET_T_PATH) == CG.SYNTH_T_SHA256, "synthetic set differs from its pin"
    else:
        assert CG.sha256_lf(SEL.ROWS_JSON) == CG.ROWS_JSON_SHA256, "rows.json differs from its pin"
    _pin(a.out, a.mode, "start", a.dll)
    {"v2": mode_v2, "pilot": mode_pilot, "main": mode_main, "v5": mode_v5}[a.mode](a)
    _pin(a.out, a.mode, "end", a.dll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
