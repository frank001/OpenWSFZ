#!/usr/bin/env python3
"""COH-MULTISET harness (Architect spec qa/rr-study/2026-10-24-1240-architect-to-qa-spec-coh-multiset.md + Amendment 1, branch arch/coh-multiset).

Night 20261022_1949 (owsfz/wav), selection frozen in results/2026-10-24-coh-multiset/selection.json (commit 31821058). BAR_L = 0.5 pp, ratified by the Captain
2026-10-24 12:50:57Z before any real-audio decode. Pinned DLL: the deployed v0.62 build (shim 20260069), OSD sign fix ON read back, nhard 24 / corr 0.10 SET (this build has
no decode-params getter, so nhard cannot be read back: disclosed in the report).

Per WSJT-X row (encodable ones; the rest are counted in N and credited zero), at WSJT-X's own position (anchor f = ws_freq, t = ws_dt + 0.7, cg_common.anchor_time):
  G   ft8_extract_llrs_at at GAP-LOCATE's 9 lattice cells + production BP -> OSD depth 2 (sign fix ON); g_out = any cell gave a CRC-valid payload, g_right = a payload that matches
      the row's text (comparator.payload_match with v_star).
  C3  (where G is not RIGHT) coherent V3 LLRs, BP ONLY (osd_depth -1); c3_out = CRC-valid output (path 0); c3_right = it matches.
  X   CONSULTED only where G and C3 BOTH returned no CRC-valid payload (A1.1): consulted = (not g_out) and (not c3_out). There C3 (once more, BP + OSD) and each of C1, J2, J3, N1
      (fixed order) is decoded twice from the SAME fine-sync estimate: BP only, and BP then OSD depth 2 (the L2 descriptive factor).

HK-037 / NFR-021: message text and bit arrays live only inside _work_cycle (and V2/V3/noise below); what is persisted is numbers and flags.

  python qa/rr-study/coh-multiset/ms_run.py rows  --dll <dll> --out <dir>
  python qa/rr-study/coh-multiset/ms_run.py run   --rows <rows json> --out <dir> --dll <dll> [--workers 4] [--first N] [--fresh]
  python qa/rr-study/coh-multiset/ms_run.py v2    --dll <dll> --out <dir>           # V2a / V2b synthetic
  python qa/rr-study/coh-multiset/ms_run.py v3    --rows <rows json> --dll <dll> --out <dir>   # Python C3 vs native fallback on the first 300 rows
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "coh-gain"))
sys.path.insert(0, os.path.join(HERE, "..", "coh-fallback"))
import cg_common as CG  # noqa: E402
import cg_select as SEL  # noqa: E402
import comparator as CMP  # noqa: E402
import fine_sync as FS  # noqa: E402
import lattice  # noqa: E402
import ms_metrics as MM  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits  # noqa: E402

REPO = CG.REPO_ROOT
RUN = "20261022_1949"
GATHERED = os.path.join(SEL.ART, f"{RUN}_endurance_run-gathered")
WS_ALLTXT = os.path.join(GATHERED, "wsjt-x", "ALL.TXT")
OWS_ALLTXT = os.path.join(GATHERED, "owsfz", "ALL.TXT")
WAV_DIR = os.path.join(GATHERED, "owsfz", "wav")
RES_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-24-coh-multiset")
SELECTION = os.path.join(RES_DIR, "selection.json")
SELECTION_SHA256_LF = "f521a1de8bc76531b13748caaeebaea91a8c1474ed9fbd18005ad46a2fa1ee7f"

DLL_PIN = "aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef"      # the deployed v0.62 libft8.dll (QA's deploy of f683dc87; native unchanged to main 5a9667ee)
SHIM = 20260069
PARAMS = (10, 0.10, 24)
BAR_L = 0.5
SEED = 20261024
assert (SHIM, PARAMS, BAR_L, SEED) == (20260069, (10, 0.10, 24), 0.5, 20261024)

ROW_COLUMNS = ["cycle_index", "stamp", "widx", "ws_freq", "ws_dt", "ws_snr", "ws_load", "live_hit", "enc"]
SET_FIELDS = [f"{s}_{k}" for s in MM.ORDER for k in ("bp_out", "bp_right", "osd_out", "osd_right")]
OUT_COLUMNS = (["cycle_index", "stamp", "widx", "snr", "load", "live_hit", "fault", "g_out", "g_right", "c3_run", "c3_out", "c3_right", "c3_df", "c3_dt", "c3_edge",
                "consulted", "c3_osd_out", "c3_osd_right"] + SET_FIELDS + ["t_g", "t_c3", "t_sets"])
TIMING = ("t_g", "t_c3", "t_sets")


# ------------------------------------------------------------------------------------------------------------------------ pins
def load_decoder(dll_path: str) -> LdpcDecodeLLRs:
    sha = CG.file_sha256(dll_path)
    assert sha == DLL_PIN, ("DLL differs from the pin", sha)
    dec = LdpcDecodeLLRs(dll_path, verify=True, expected_sha256=DLL_PIN, expected_shim_version=SHIM, check_version=True)
    dec.dll.ft8_set_decode_params(PARAMS[0], PARAMS[1], PARAMS[2])
    dec.dll.ft8_set_osd_sign_fix(1)
    assert dec.dll.ft8_get_osd_sign_fix() == 1, "osd sign fix not read back"
    return dec


def script_pins():
    names = ("ms_run.py", "ms_metrics.py", "ms_gates.py", "ms_noise.py")
    return {n: CG.sha256_lf(os.path.join(HERE, n)) for n in names if os.path.exists(os.path.join(HERE, n))}


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()


def judge(res, payload, text):
    """-> (crc-valid output present, matches the row's text, decoder path). Text and payload are used here only."""
    if res["rc"] == 0 and res["crc_ok"] == 1 and res["a91"] is not None:
        rec = a91_to_bits(res["a91"], CG.PAYLOAD_BITS)
        return 1, int(CMP.payload_match(payload, rec, text, CG.V_STAR)), res["path"]
    return 0, 0, res["path"]


def decode(dec, llr, osd_depth):
    return dec.ldpc_decode_llrs([float(x) for x in llr], max_iters=CG.K_LDPC_ITERATIONS, osd_depth=osd_depth)


# ------------------------------------------------------------------------------------------------------------------------ rows
def build_rows(a):
    dec = load_decoder(a.dll)
    assert CG.sha256_lf(SELECTION) == SELECTION_SHA256_LF, "selection.json differs from its freeze"
    sel = json.load(open(SELECTION))
    ws, ows = SEL.read_alltxt(WS_ALLTXT), SEL.read_alltxt(OWS_ALLTXT)
    os.makedirs(a.out, exist_ok=True)
    for tag in ("sample", "pilot"):
        rows, excl = [], collections.Counter()
        for i, stamp in sel[tag]:
            wl = ws.get(stamp, [])
            hits = SEL.test_b_matches(wl, ows.get(stamp, []))
            for widx, (snr, dt, freq, text) in enumerate(wl):
                enc = int(CG.encode_tones(dec, text) is not None and dec.true_codeword(text) is not None)
                if not enc:
                    excl[SEL.text_feature(text)] += 1
                rows.append([i, stamp, widx, freq, dt, snr, len(wl), int(hits[widx]), enc])
        spec = {"night": RUN, "tag": tag, "selection_sha256_lf": SELECTION_SHA256_LF, "dll_pin": DLL_PIN, "shim": SHIM, "wsjtx_alltxt_sha256": CG.file_sha256(WS_ALLTXT),
                "owsfz_alltxt_sha256": CG.file_sha256(OWS_ALLTXT), "columns": ROW_COLUMNS,
                "counts": {"cycles": len(sel[tag]), "rows_all": len(rows), "rows_encodable": sum(r[8] for r in rows), "excluded_by_reason": dict(excl),
                           "live_hit_rows_encodable": sum(r[7] for r in rows if r[8])},
                "rule": "live_hit = COH-GAIN Test B (same cycle, same text, |df| <= 10 Hz, one-to-one nearest-first) against the live OpenWSFZ ALL.TXT", "rows": rows}
        p = os.path.join(a.out, f"rows_{tag}.json")
        data = (json.dumps(spec, indent=0, sort_keys=True) + "\n").encode("utf-8")
        with open(p, "wb") as fh:
            fh.write(data)
        print(tag, spec["counts"], "sha256_lf", hashlib.sha256(data).hexdigest())


# ------------------------------------------------------------------------------------------------------------------------ per-cycle worker
_DEC = _WS = None


def _init(dll):
    global _DEC, _WS
    _DEC = load_decoder(dll)
    _WS = SEL.read_alltxt(WS_ALLTXT)


def _work_cycle(task):
    """task = (cycle_index, stamp, [rows]) -> (records, cpu_s). Text, payloads and bit arrays never leave this function."""
    ci, stamp, rows = task
    dec = _DEC
    cpu0 = time.process_time()
    pcm = wavio.load_cycle_pcm(os.path.join(WAV_DIR, stamp + ".wav"))
    wl = _WS.get(stamp, [])
    recs = []
    for (_ci, _st, widx, freq, dt, snr, load, live_hit, enc) in rows:
        rec = {c: 0 for c in OUT_COLUMNS}
        rec.update({"cycle_index": ci, "stamp": stamp, "widx": widx, "snr": snr, "load": load, "live_hit": live_hit})
        s_snr, s_dt, s_freq, text = wl[widx]
        tb = dec.true_codeword(text)
        if s_freq != freq or s_snr != snr or tb is None:
            rec["fault"] = 1
            recs.append(rec)
            continue
        payload = tb[:CG.PAYLOAD_BITS]
        anchor_f, anchor_t = float(freq), CG.anchor_time(dt)
        t0 = time.process_time()
        for cell in lattice.snap_and_neighbours(anchor_f, anchor_t):                        # ---- G
            rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
            if rc != 0:
                rec["fault"] = 1
                continue
            out, right, _ = judge(decode(dec, llr, CG.OSD_DEPTH), payload, text)
            if out:
                rec["g_out"] = 1
            if right:
                rec["g_right"] = 1
                break
        rec["t_g"] = round(time.process_time() - t0, 4)
        if not rec["g_right"]:                                                              # ---- C3, BP only
            t0 = time.process_time()
            rec["c3_run"] = 1
            est = FS.estimate(pcm, anchor_f, anchor_t)
            v3 = CG.coherent_llrs(pcm, anchor_f, anchor_t, est)["V3"]
            out, right, path = judge(decode(dec, v3, -1), payload, text)
            rec["c3_out"], rec["c3_right"] = int(out and path == 0), int(right and path == 0)
            rec.update({"c3_df": round(est["est_df_hz"], 6), "c3_dt": round(est["est_dt_s"], 6), "c3_edge": int(est["edge"])})
            rec["t_c3"] = round(time.process_time() - t0, 4)
            if not rec["g_out"] and not rec["c3_out"]:                                      # ---- X is consulted (A1.1)
                rec["consulted"] = 1
                t0 = time.process_time()
                out, right, path = judge(decode(dec, v3, CG.OSD_DEPTH), payload, text)
                rec["c3_osd_out"], rec["c3_osd_right"] = int(out and path == 1), int(right and path == 1)
                X = MM.spectra(pcm, anchor_f, anchor_t, est)
                for name in MM.ORDER:
                    v = MM.SETS[name](X)
                    o, r, p = judge(decode(dec, v, -1), payload, text)
                    rec[f"{name}_bp_out"], rec[f"{name}_bp_right"] = int(o and p == 0), int(r and p == 0)
                    o, r, p = judge(decode(dec, v, CG.OSD_DEPTH), payload, text)
                    rec[f"{name}_osd_out"], rec[f"{name}_osd_right"] = int(o and p == 1), int(r and p == 1)
                rec["t_sets"] = round(time.process_time() - t0, 4)
        recs.append(rec)
    return recs, time.process_time() - cpu0


def run(a):
    spec = json.load(open(a.rows))
    assert spec["columns"] == ROW_COLUMNS and spec["dll_pin"] == DLL_PIN
    rows = [r for r in spec["rows"] if r[8]]
    if a.first:
        rows = rows[:a.first]
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault((r[0], r[1]), []).append(r)
    tasks = [(ci, st, rs) for (ci, st), rs in by.items()]
    os.makedirs(a.out, exist_ok=True)
    part = os.path.join(a.out, "rows_part.csv")
    done = set()
    if os.path.exists(part) and not a.fresh:
        done = {int(float(r["cycle_index"])) for r in csv.DictReader(open(part, newline="", encoding="utf-8"))}
    tasks = [t for t in tasks if t[0] not in done]
    pins = os.path.join(a.out, "pins.jsonl")

    def stamp_pins(when):
        with open(pins, "a") as fh:
            fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "when": when, "dll_sha256": CG.file_sha256(a.dll), "pin": DLL_PIN, "git_head": git_head(),
                                 "scripts": script_pins(), "rows_json_sha256_lf": CG.sha256_lf(a.rows), "cycles_to_run": len(tasks), "rows_to_run": sum(len(t[2]) for t in tasks)}) + "\n")

    stamp_pins("start")
    newfile = not os.path.exists(part) or a.fresh
    cpu = {}
    with open(part, "w" if newfile else "a", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if newfile:
            w.writerow(OUT_COLUMNS)
        with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll,)) as ex:
            futs = {ex.submit(_work_cycle, t): t[0] for t in tasks}
            n = 0
            for f in as_completed(futs):
                recs, secs = f.result()
                cpu[futs[f]] = (len(recs), secs)
                for r in recs:
                    w.writerow([r.get(c, "") for c in OUT_COLUMNS])
                fh.flush()
                n += 1
                if n % 20 == 0:
                    print(f"  {n}/{len(tasks)} cycles {time.strftime('%H:%M:%SZ', time.gmtime())}", flush=True)
    stamp_pins("end")
    tot = sum(s for _n, s in cpu.values())
    nrows = sum(n for n, _s in cpu.values())
    info = {"cycles": len(cpu), "rows": nrows, "cpu_s": round(tot, 1), "cpu_s_per_row": round(tot / nrows, 4) if nrows else None}
    json.dump(info, open(os.path.join(a.out, "run_info.json"), "w"))
    print(json.dumps(info))


# ------------------------------------------------------------------------------------------------------------------------ V2a / V2b (synthetic)
def v2(a):
    import cg_synth as SYN
    dec = load_decoder(a.dll)
    spec = json.load(open(SYN.SET_PATH))
    res = {n: 0 for n in MM.ORDER}
    res.update({"J2_identity": 0, "J3_identity": 0, "C3": 0})
    n_ok = 0
    for s in spec:
        pcm = SYN.render_signal(s)
        tb = dec.true_codeword(s["message"])
        payload = tb[:CG.PAYLOAD_BITS]
        est = FS.estimate(pcm, s["anchor_f"], s["anchor_t"])
        X = MM.spectra(pcm, s["anchor_f"], s["anchor_t"], est)
        n_ok += 1
        vs = {name: MM.SETS[name](X) for name in MM.ORDER}
        vs["J2_identity"] = MM.j2(X, gray=MM.IDENTITY_MAP)
        vs["J3_identity"] = MM.j3(X, gray=MM.IDENTITY_MAP)
        vs["C3"] = CG.coherent_llrs(pcm, s["anchor_f"], s["anchor_t"], est)["V3"]
        for name, v in vs.items():
            o, r, p = judge(decode(dec, v, -1), payload, s["message"])
            res[name] += int(r and p == 0)
    rates = {k: round(v / n_ok, 4) for k, v in res.items()}
    out = {"n": n_ok, "synthetic_set_sha256_lf": CG.sha256_lf(SYN.SET_PATH), "success_rate_bp_only": rates,
           "V2a": {"rule": "C1, J2, J3, N1 each >= 0.99", "pass": bool(all(rates[n] >= 0.99 for n in MM.ORDER))},
           "V2b": {"rule": "J2 and J3 with the identity Gray map each <= 0.50", "pass": bool(rates["J2_identity"] <= 0.50 and rates["J3_identity"] <= 0.50)},
           "dll_pin": DLL_PIN}
    os.makedirs(a.out, exist_ok=True)
    json.dump(out, open(os.path.join(a.out, "v2.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


# ------------------------------------------------------------------------------------------------------------------------ V3 (Python C3 vs the native fallback)
def v3(a):
    import cf_native as N
    nat = N.Native(a.dll, DLL_PIN, expected_shim=SHIM, nhard=PARAMS[2])
    dec = load_decoder(a.dll)
    spec = json.load(open(a.rows))
    rows = [r for r in spec["rows"] if r[8]][:300]
    ws = SEL.read_alltxt(WS_ALLTXT)
    n = agree = est_eq = both_out = right_eq = 0
    max_d = 0.0
    n_nat_out = n_py_out = 0
    for (ci, stamp, widx, freq, dt, snr, load, hit, enc) in rows:
        pcm = wavio.load_cycle_pcm(os.path.join(WAV_DIR, stamp + ".wav"))
        text = ws[stamp][widx][3]
        payload = dec.true_codeword(text)[:CG.PAYLOAD_BITS]
        af, at = float(freq), CG.anchor_time(dt)
        est = FS.estimate(pcm, af, at)
        v3py = CG.coherent_llrs(pcm, af, at, est)["V3"]
        o, r, p = judge(decode(dec, v3py, -1), payload, text)
        py_out, py_right = int(o and p == 0), int(r and p == 0)
        p32 = np.ascontiguousarray(pcm, dtype=np.float32)
        rc, res, llr = nat.at(p32, af, at, flags=N.FLAG_FORCE_C3 | N.FLAG_SKIP_F1B, want_llr=True)
        assert rc == 0
        nat_out = int(res.c3_ran == 1 and res.bp_rc == 0 and res.bp_path == 0 and res.bp_crc_ok == 1)
        nat_right = 0
        if nat_out:
            nat_right = int(CMP.payload_match(payload, a91_to_bits(bytes(res.a91), CG.PAYLOAD_BITS), text, CG.V_STAR))
        n += 1
        n_nat_out += nat_out
        n_py_out += py_out
        agree += int(nat_out == py_out)
        if nat_out and py_out:
            both_out += 1
            right_eq += int(nat_right == py_right)
        est_eq += int(abs(res.est_df_hz - est["est_df_hz"]) < 1e-6 and abs(res.est_dt_s - est["est_dt_s"]) < 1e-6)
        if res.c3_ran:
            max_d = max(max_d, float(np.max(np.abs(np.asarray(llr, dtype=np.float64) - np.asarray(v3py, dtype=np.float64)))))
    out = {"rows": n, "outcome_agree": agree, "estimate_equal": est_eq, "both_have_output": both_out, "rightness_equal_where_both": right_eq,
           "native_outputs": n_nat_out, "python_outputs": n_py_out, "max_abs_dLLR_descriptive": max_d,
           "V3": {"rule": "outcome agrees on >= 299/300 and (df, dt) equal on >= 297/300 (Amendment 1 A1.5)", "pass": bool(n == 300 and agree >= 299 and est_eq >= 297)},
           "dll_pin": DLL_PIN}
    os.makedirs(a.out, exist_ok=True)
    json.dump(out, open(os.path.join(a.out, "v3.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["rows", "run", "v2", "v3"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dll", default=r"D:\Projects\claude\_qa-scratch\coh-multiset\bin\libft8.dll")
    ap.add_argument("--rows")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    {"rows": build_rows, "run": run, "v2": v2, "v3": v3}[a.mode](a)


if __name__ == "__main__":
    main()
