#!/usr/bin/env python3
"""COH-FALLBACK step 4: the U' instrument (spec sections 14 A14.3, 15 A15.3, 16 A16.3, 17 A17.2 + the Captain's decision of 2026-10-21 18:45Z).

THE PROCEDURE IS FROZEN HERE, BEFORE THE OFF ARM RUNS (committed first; every constant below is a decision value with its source).
  Instrument ......... cf_fbid.py @ ecc4c5e7 (imported, not copied; its git blob is asserted), tone-presence HIT of the 58 data symbols at the position chosen by the 21 Costas symbols alone.
  T .................. 0.276, frozen from 10-09's pooled-null 99th percentile (A16.3). The night's own null is computed DESCRIPTIVELY; if its p99 differs by more than 0.03, FLAG (exit status 4) - the Architect rules before any ON decode.
  Shape classes ...... cf_fbid.shape_class(), as committed.
  Testable class ..... the OFF arm's CONFIRMED decodes of the class: a random sample of up to 50 (seed 20261007), n >= 10 AND present rate >= 0.80 (the section 16 DEFAULT; the Captain chose it, 2026-10-21 18:45Z).
  Untestable ......... (i) hashed (<...>) or cannot be re-encoded; or (ii) a class that is not testable. Both count as NOT SHOWN PRESENT (conservative: U' is an upper bound).
  U'_i ............... in one cycle: Test-B not-confirmed decodes (all batches) that are not shown present = tested-absent + hashed/unencodable + untestable class.
  Class list ......... frozen from the OFF arm ALONE (stage `off`), written to a JSON, applied unchanged to the ON arms (stage `arm`).
  Cycles ............. only cycles where WSJT-X decoded something (ws > 0), paired across arms.
  U'_max proposal .... 0.30 x U'0; projected paired half-width 1.96 x sqrt(2 x U'_max / n_cycles) (A11.2); the "U'_max <= 2 x 0.021 = 0.042" line (A15.3); and "2 x half-width vs U'_max" (A2.4(a)).

HK-037: message text exists only in this process's memory, read from the scratch working file (--nc-dump, under _qa-scratch). What is written is numeric aggregates only.

  python cf_uprime.py off  <nc_dump.tsv> <testb.csv> <wav_root> <run> <libft8.dll> <out.json>
  python cf_uprime.py arm  <nc_dump.tsv> <testb.csv> <wav_root> <run> <libft8.dll> <classes.json> <out.json>
"""
import collections
import csv
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- FROZEN DECISION VALUES (see the module docstring for where each comes from) -------------------------------------------------------------------------
INSTRUMENT_GIT_BLOB = "ecc4c5e7:qa/rr-study/coh-fallback/cf_fbid.py"
T_FROZEN = 0.276
NULL_P99_TOLERANCE = 0.03
MIN_N_PER_CLASS = 10
MIN_PRESENT_RATE = 0.80
SAMPLE_PER_CLASS = 50
SAMPLE_SEED = 20261007
K_NULL = 20
CALIBRATION_CONTROLS = 80
CALIBRATION_MIN_SYNC_HIT = 0.6
BAR_FRACTION = 0.30
BAR_LINE = 2 * 0.021
OBSERVED_DELTA_U_1009 = 0.021
HALF_WIDTH_Z = 1.96
EXIT_NULL_FLAG = 4

HASHED_OR_UNENCODABLE = "hashed_or_unencodable"
UNTESTABLE_CLASS = "untestable_class"
TESTED_ABSENT = "tested_absent"


def load_instrument():
    """Import cf_fbid.py and assert it is byte-for-byte the committed ecc4c5e7 blob (fail closed)."""
    path = os.path.join(HERE, "cf_fbid.py")
    want = subprocess.run(["git", "-C", HERE, "rev-parse", INSTRUMENT_GIT_BLOB], capture_output=True, text=True, check=True).stdout.strip()
    have = subprocess.run(["git", "-C", HERE, "hash-object", path], capture_output=True, text=True, check=True).stdout.strip()
    if want != have:
        raise SystemExit(f"INSTRUMENT MISMATCH: cf_fbid.py blob {have} != {INSTRUMENT_GIT_BLOB} blob {want}")
    spec = importlib.util.spec_from_file_location("cf_fbid_frozen", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, have


def read_dump(path, ws_cycles):
    """Rows of the working file for cycles with ws > 0: dict(stamp, kind, matched, f, dt, snr, path, text)."""
    rows = []
    for ln in open(path, encoding="utf-8"):
        p = ln.rstrip("\n").split("\t")
        if len(p) < 11:
            continue
        stamp = p[0]
        if stamp not in ws_cycles:
            continue
        rows.append(dict(stamp=stamp, kind=int(p[1]), matched=int(p[2]), f=int(p[3]), dt=float(p[4]), snr=int(p[5]), path=int(p[9]), text="\t".join(p[10:])))
    return rows


def ws_cycle_set(testb_csv):
    """Cycles where WSJT-X decoded something: the 'ws' lines of the Test-B file (run,stamp,ws,ALL,n,corroborated)."""
    cyc = set()
    for r in csv.reader(open(testb_csv)):
        if len(r) >= 5 and r[2] == "ws" and int(r[4]) > 0:
            cyc.add(r[1])
    return cyc


def locate_start(F, pcm, f0, centre, half, sync_tones):
    """Verbatim from cf_fbid.main's nested locate_start: the broad Costas-only search used to calibrate where a reported dt puts symbol 0."""
    best, bs = -1.0, None
    sync_arr = np.array(sync_tones)
    for dfz in F.DF_GRID_HZ:
        bb = F.CE.downconvert_decimate(pcm, round(f0 + dfz, 3))
        for st in np.arange(centre - half, centre + half + 1e-9, F.DT_STEP_S):
            am = np.abs(F.CE.correlate_symbols(bb, int(round(st * F.FS_OUT)))).argmax(axis=1)
            h = float((am[F.SYNC_IDX] == sync_arr).mean())
            if h > best:
                best, bs = h, float(st)
    return best, bs


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("off", "arm"):
        print(__doc__)
        return 2
    stage = sys.argv[1]
    if stage == "off":
        dump, testb, wav_root, run, dll, out = sys.argv[2:8]
        classes_in = None
    else:
        dump, testb, wav_root, run, dll, classes_in, out = sys.argv[2:9]
    F, blob = load_instrument()
    enc = F.encoder(dll)
    ws_cycles = ws_cycle_set(testb)
    rows = read_dump(dump, ws_cycles)
    for r in rows:
        r["tones"] = enc(r["text"])
        r["hashed"] = any(x.startswith("<") for x in r["text"].split())
        r["cls"] = F.shape_class(r["text"])
    pcms = {}

    def pcm_of(stamp):
        if stamp not in pcms:
            pcms[stamp] = F.wavio.load_cycle_pcm(os.path.join(wav_root, f"{run}_endurance_run-gathered", "owsfz", "wav", stamp + ".wav"))
        return pcms[stamp]

    res = {"stage": stage, "instrument_blob": blob, "T_frozen": T_FROZEN, "min_n": MIN_N_PER_CLASS, "min_present_rate": MIN_PRESENT_RATE,
           "cycles_ws_gt_0": len(ws_cycles), "decodes": len(rows), "confirmed": sum(r["matched"] for r in rows), "not_confirmed": sum(1 - r["matched"] for r in rows)}

    # ---- calibration: where does a reported dt put symbol 0 (confirmed controls, the cf_fbid procedure). The OFF arm sets it; the ON arms reuse it unchanged. ----
    ctl = sorted((r for r in rows if r["matched"] and r["tones"] is not None), key=lambda r: (r["stamp"], r["f"]))
    if stage == "off":
        offs = []
        for r in ctl[:CALIBRATION_CONTROLS]:
            h, st = locate_start(F, pcm_of(r["stamp"]), r["f"], r["dt"] + 0.5, F.CALIB_HALF_WINDOW_S, [r["tones"][i] for i in F.SYNC_IDX])
            if h >= CALIBRATION_MIN_SYNC_HIT:
                offs.append(st - r["dt"])
        c_off = float(np.median(offs)) if offs else 0.5
        res["calibration"] = {"controls_used": min(len(ctl), CALIBRATION_CONTROLS), "with_sync_hit_ge_0.6": len(offs), "start_minus_dt_median_s": c_off}
    else:
        frozen = json.load(open(classes_in))
        c_off = float(frozen["start_minus_dt_median_s"])
        res["calibration"] = {"reused_from": classes_in, "start_minus_dt_median_s": c_off}

    def hit_of(r, cache):
        sh, outs = F.locate_and_score(cache, pcm_of(r["stamp"]), r["f"], r["dt"] + c_off, F.DT_HALF_WINDOW_S, [r["tones"][i] for i in F.SYNC_IDX], [r["tones"]])
        return outs[0]

    if stage == "off":
        # ---- the class table, from the OFF arm's CONFIRMED decodes (sample of up to 50 per class), with the night's null (descriptive) ----
        rng = np.random.default_rng(SAMPLE_SEED)
        by_class = collections.defaultdict(list)
        for r in ctl:
            if not r["hashed"]:
                by_class[r["cls"]].append(r)
        all_tones = [r["tones"] for r in ctl]
        table, nulls = {}, []
        for cls in sorted(by_class):
            pool = by_class[cls]
            idx = rng.permutation(len(pool))[:SAMPLE_PER_CLASS]
            sample = [pool[i] for i in sorted(idx)]
            hits = []
            for r in sample:
                cache = {}
                own = r["tones"]
                cand = [i for i, x in enumerate(ctl) if x["stamp"] != r["stamp"]
                        and float((np.array(x["tones"])[F.DATA_IDX] == np.array(own)[F.DATA_IDX]).mean()) <= 0.3]
                pick = rng.choice(cand, size=K_NULL, replace=False)
                sh, outs = F.locate_and_score(cache, pcm_of(r["stamp"]), r["f"], r["dt"] + c_off, F.DT_HALF_WINDOW_S,
                                              [own[i] for i in F.SYNC_IDX], [own] + [all_tones[i] for i in pick])
                hits.append(outs[0])
                nulls.extend(outs[1:])
            present = int(sum(h >= T_FROZEN for h in hits))
            n = len(sample)
            lo, hi = F.wilson(present, n)
            rate = present / n if n else 0.0
            table[cls] = {"confirmed_in_class": len(pool), "n_sampled": n, "present": present, "present_rate": rate, "wilson": [lo, hi],
                          "testable": bool(n >= MIN_N_PER_CLASS and rate >= MIN_PRESENT_RATE)}
        res["class_table"] = table
        res["testable_classes"] = sorted(k for k, v in table.items() if v["testable"])
        nulls = np.array(nulls)
        p99 = float(np.percentile(nulls, F.NULL_PCTL)) if nulls.size else float("nan")
        res["null_this_night"] = {"n": int(nulls.size), "mean": float(nulls.mean()) if nulls.size else None, "p99": p99,
                                  "T_frozen": T_FROZEN, "abs_diff": abs(p99 - T_FROZEN) if nulls.size else None,
                                  "flag_architect": bool(nulls.size == 0 or abs(p99 - T_FROZEN) > NULL_P99_TOLERANCE)}
        testable = set(res["testable_classes"])
    else:
        testable = set(frozen["testable_classes"])
        res["classes_from"] = classes_in

    # ---- U'_i for this arm: not-confirmed decodes that are not shown present ----
    per_cycle = collections.defaultdict(lambda: {TESTED_ABSENT: 0, HASHED_OR_UNENCODABLE: 0, UNTESTABLE_CLASS: 0, "tested_present": 0, "not_confirmed": 0})
    per_band = collections.defaultdict(lambda: collections.defaultdict(int))
    band_of = lambda snr: "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"   # Replay81 BandOf
    for r in rows:
        if r["matched"]:
            continue
        c = per_cycle[r["stamp"]]
        cb = per_band[(r["stamp"], band_of(r["snr"]))]      # A19.5 descriptive split by SNR band; adds output only, changes no number
        c["not_confirmed"] += 1
        cb["not_confirmed"] += 1
        if r["hashed"] or r["tones"] is None:
            c[HASHED_OR_UNENCODABLE] += 1
            cb[HASHED_OR_UNENCODABLE] += 1
        elif r["cls"] not in testable:
            c[UNTESTABLE_CLASS] += 1
            cb[UNTESTABLE_CLASS] += 1
        else:
            if hit_of(r, {}) >= T_FROZEN:
                c["tested_present"] += 1
                cb["tested_present"] += 1
            else:
                c[TESTED_ABSENT] += 1
                cb[TESTED_ABSENT] += 1
    n_cyc = len(ws_cycles)
    tot = {k: sum(per_cycle[s][k] for s in per_cycle) for k in (TESTED_ABSENT, HASHED_OR_UNENCODABLE, UNTESTABLE_CLASS, "tested_present", "not_confirmed")}
    u_prime_sum = tot[TESTED_ABSENT] + tot[HASHED_OR_UNENCODABLE] + tot[UNTESTABLE_CLASS]
    res["U_prime"] = {"cycles": n_cyc, "totals": tot, "U_prime_per_cycle": u_prime_sum / n_cyc if n_cyc else None,
                      "split_per_cycle": {k: tot[k] / n_cyc for k in (TESTED_ABSENT, HASHED_OR_UNENCODABLE, UNTESTABLE_CLASS)} if n_cyc else None}
    with open(out + ".byband.csv", "w") as f:
        f.write("stamp,band,not_confirmed,tested_absent,hashed_or_unencodable,untestable_class,tested_present\n")
        for (st, bd) in sorted(per_band):
            c = per_band[(st, bd)]
            f.write(",".join([st, bd] + [str(c[k]) for k in ("not_confirmed", TESTED_ABSENT, HASHED_OR_UNENCODABLE, UNTESTABLE_CLASS, "tested_present")]) + "\n")
    with open(out + ".percycle.csv", "w") as f:
        f.write("stamp,not_confirmed,tested_absent,hashed_or_unencodable,untestable_class,tested_present\n")
        for s in sorted(ws_cycles):
            c = per_cycle.get(s)
            f.write(",".join([s] + [str(c[k]) if c else "0" for k in ("not_confirmed", TESTED_ABSENT, HASHED_OR_UNENCODABLE, UNTESTABLE_CLASS, "tested_present")]) + "\n")
    if stage == "off":
        u0 = res["U_prime"]["U_prime_per_cycle"]
        umax = BAR_FRACTION * u0
        hw = HALF_WIDTH_Z * math.sqrt(2 * umax / n_cyc) if n_cyc and umax > 0 else None
        res["proposal"] = {"U_prime_0": u0, "U_prime_max_0.30x": umax, "projected_paired_half_width": hw,
                           "two_x_half_width": (2 * hw if hw is not None else None),
                           "U_max_ge_2x_half_width": bool(hw is not None and umax >= 2 * hw),
                           "bar_line_0.042": BAR_LINE, "U_prime_max_le_0.042": bool(umax <= BAR_LINE),
                           "observed_delta_U_prime_1009": OBSERVED_DELTA_U_1009}
        json.dump({"testable_classes": res["testable_classes"], "class_table": res["class_table"], "T_frozen": T_FROZEN,
                   "min_n": MIN_N_PER_CLASS, "min_present_rate": MIN_PRESENT_RATE, "instrument_blob": blob,
                   "start_minus_dt_median_s": c_off}, open(out.replace(".json", "_classes.json"), "w"), indent=1)
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return EXIT_NULL_FLAG if stage == "off" and res["null_this_night"]["flag_architect"] else 0


if __name__ == "__main__":
    sys.exit(main())
