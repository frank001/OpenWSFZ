#!/usr/bin/env python3
"""Q-GATE-2 harness (Architect spec qa/rr-study/2026-10-20-1530-architect-to-qa-spec-q-gate-2.md + Amendment 1 section 12; branch arch/coherent-limb2).

Night 20261019_1905 (gathered), cycle list = every 15 s slot, gap-inclusive, frozen in _qa-scratch/q-gate-2/cycle_list.txt (SHA pinned below).
  main sample  i mod 5 == 1   (933 cycles after the 6 outage stamps are dropped)    fallback i mod 7 == 1 (665) if the pilot projects > 6 h CPU
  pilot        i mod 5 == 3   (disjoint; DISCARDED from every row)
Pinned DLL: the Developer's amendment build 8b2f7c82, shim 20260065 (S0: #225 V1 PASSED, board 2026-10-20), nhard 24, osd-sign-fix 1 (read back).

Per WSJT-X row (encodable ones; the rest counted by reason):
  live_hit  the endurance ANOVA's own matcher (qg2_live.py, V-L PASS 97,480)
  G         ft8_extract_llrs_at at the 9 lattice cells + production BP->OSD (osd_depth 2); RIGHT = CRC ok AND (i) payload_match with the row's v_star rule OR
            (ii) output i3 = 4 AND ENC-ID's enc_match against the row's own text (cg_encid.enc_flags, unchanged code)
  C3        (only when G is not RIGHT) coherent V3 LLRs through ft8_ldpc_decode_llrs with BP ONLY (osd_depth -1): an output is rc 0, path 0, CRC ok
  class     RIGHT_i / RIGHT_ii / M-NEAR (+-12.5 Hz, +-0.32 s) / M-FAR / M-OWS / M-NONE, first match wins, rules (i)/(ii) against every encodable WSJT-X row
            of the cycle, then against the cycle's live OWS rows
  F1b       cg_gate_features.costas_snr_noise_ref_db (outputs only)
V-T2 control items: every CRC-valid i3 = 4 output (G and C3) is matched with the text of a DIFFERENT encodable row of the SAME cycle (seeded derangement).

HK-037 / NFR-021: text, payload bits, calls and hashes live only inside _work_cycle; what is persisted is numbers and flags (stamps, positions, SNR, classes).

  python qa/rr-study/coh-gain/qg2.py select --out <dir>
  python qa/rr-study/coh-gain/qg2.py run --rows <rows json> --out <dir> --dll <dll> [--workers 4] [--max-rows N]
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_encid as EN  # noqa: E402
import cg_gate_features as GF  # noqa: E402
import cg_select as SEL  # noqa: E402
import comparator as CMP  # noqa: E402
import fine_sync as FS  # noqa: E402
import lattice  # noqa: E402
import pack77_fields as PF  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits  # noqa: E402

ART = SEL.ART
NIGHT = "20261019_1905"
GATHERED = os.path.join(ART, f"{NIGHT}_endurance_run-gathered")
WS_ALLTXT = os.path.join(GATHERED, "wsjt-x", "ALL.TXT")
OWS_ALLTXT = os.path.join(GATHERED, "owsfz", "ALL.TXT")
WAV_DIR = os.path.join(GATHERED, "owsfz", "wav")
WORK = r"D:\Projects\claude\_qa-scratch\q-gate-2"
CYCLE_LIST = os.path.join(WORK, "cycle_list.txt")
CYCLE_LIST_SHA256 = "aed896e433867cbd5c3ee915cbec08e9cd6dc1d86aef2460dc60d4fc48802201"      # frozen 2026-10-20 (freeze_record.json)
LIVE_HIT_JSON = os.path.join(WORK, "live_hit.json")                                           # qg2_live.py, V-L PASS 97,480
OUTAGE = ("261019_193200", "261019_195800", "261020_084915", "261020_084930", "261020_084945", "261020_085000")
DLL_PIN = "cf5ee3dea09f55cbbd3a46bd387b3b7eb5510d862282bbf12bda27aa4c15deab"                  # 8b2f7c82, shim 20260065 (verified 2026-10-20)
SHIM = 20260065
PARAMS = (10, 0.10, 24)
T1 = 17.552446          # GA threshold, frozen (results/2026-10-06-coh-gain/gate_thresholds.json)
U_MAX = 0.05            # Captain, 2026-10-20 (QA window)
BAR_G = 1.0
SEED = 20261020
BLOCK_CYCLES = 8
B_RESAMPLES = 10_000
NEAR_HZ, NEAR_S = 12.5, 0.32
MAIN_RULE, PILOT_RULE, FALLBACK_RULE = (5, 1), (5, 3), (7, 1)       # (modulus, residue)
PILOT2_RULE, PILOT4_RULE = (5, 2), (5, 4)                           # Amendment 2 A2.1: control-pilot extension residues (discarded from every row)
assert abs(T1 - json.load(open(os.path.join(CG.RR, "results", "2026-10-06-coh-gain", "gate_thresholds.json")))["thresholds"]["GA"]["T1"]) < 1e-9

ROW_COLUMNS = ["cycle_index", "stamp", "widx", "freq", "dt", "snr", "load", "live_hit", "enc"]
OUT_COLUMNS = ["cycle_index", "stamp", "widx", "snr", "live_hit", "fault", "g_right", "g_rule", "g_out", "g_i3", "g_wrong",
               "c3_run", "c3_out", "c3_class", "c3_i3", "f1b", "cpu_s"]


# ----------------------------------------------------------------------------------------------------------------------- the decoder
def load_decoder(dll_path: str) -> LdpcDecodeLLRs:
    sha = CG.file_sha256(dll_path)
    assert sha == DLL_PIN, ("DLL differs from the pin", sha)
    dec = LdpcDecodeLLRs(dll_path, verify=True, expected_sha256=DLL_PIN, expected_shim_version=SHIM, check_version=True)
    dec.dll.ft8_set_decode_params(PARAMS[0], PARAMS[1], PARAMS[2])
    dec.dll.ft8_set_osd_sign_fix(1)
    assert dec.dll.ft8_get_osd_sign_fix() == 1, "osd sign fix not read back"
    return dec


def parse_rows(path: str):
    """stamp -> [(snr, dt, freq, text)] in file order with anova_common.parse_all_txt's acceptance rule (so the index matches live_hit.json)."""
    d = collections.OrderedDict()
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            tok = line.rstrip("\r\n").split()
            if len(tok) < 8:
                continue
            try:
                snr, dt, freq = float(tok[4]), float(tok[5]), float(tok[6])
            except ValueError:
                continue
            d.setdefault(tok[0], []).append((int(snr), dt, int(freq), " ".join(tok[7:])))
    return d


def reason(text: str) -> str:
    """Coarse reason an unencodable row is excluded (a FEATURE of the text, never the text)."""
    if ";" in text and "RR73;" in text.split():
        return "type_0.1_dxpedition"
    return "hashed_call_token" if "<" in text else "other_unencodable"


# ----------------------------------------------------------------------------------------------------------------------- sample selection
def slots():
    assert hashlib.sha256(open(CYCLE_LIST, "rb").read()).hexdigest() == CYCLE_LIST_SHA256, "cycle list differs from its pin"
    return [l.strip() for l in open(CYCLE_LIST) if l.strip()]


def pick(rule, all_slots):
    mod, res = rule
    return [(i, s) for i, s in enumerate(all_slots) if i % mod == res and s not in OUTAGE]


def select(a):
    dll = a.dll
    dec = load_decoder(dll)
    ws = parse_rows(WS_ALLTXT)
    hit = json.load(open(LIVE_HIT_JSON))
    assert hit["V-L"] == "PASS"
    hit = hit["hit_by_stamp"]
    allslots = slots()
    out = {}
    allrules = {"main": MAIN_RULE, "pilot": PILOT_RULE, "fallback7": FALLBACK_RULE, "pilot2": PILOT2_RULE, "pilot4": PILOT4_RULE}
    for tag, rule in [(t, r) for t, r in allrules.items() if not a.tags or t in a.tags.split(",")]:
        sample = pick(rule, allslots)
        rows, excl, nrows = [], collections.Counter(), 0
        for i, stamp in sample:
            wl = ws.get(stamp, [])
            flags = hit.get(stamp, [0] * len(wl))
            assert len(flags) == len(wl), (stamp, len(flags), len(wl))
            for widx, (snr, dt, freq, text) in enumerate(wl):
                nrows += 1
                enc = int(CG.encode_tones(dec, text) is not None and dec.true_codeword(text) is not None)
                if not enc:
                    excl[reason(text)] += 1
                rows.append([i, stamp, widx, freq, dt, snr, len(wl), flags[widx], enc])
        ev = sum(1 for _, s in sample if (int(s[-2:]) // 15) % 2 == 0)
        out[tag] = {"rule": f"i mod {rule[0]} == {rule[1]}", "cycles": len(sample), "even": ev, "odd": len(sample) - ev,
                    "rows_all": nrows, "rows_encodable": sum(r[8] for r in rows), "excluded_by_reason": dict(excl),
                    "live_hit_rows_encodable": sum(r[7] for r in rows if r[8]), "columns": ROW_COLUMNS, "rows": rows}
    spec = {"night": NIGHT, "cycle_list_sha256": CYCLE_LIST_SHA256, "dll_pin": DLL_PIN, "shim": SHIM, "wsjtx_alltxt_sha256": CG.file_sha256(WS_ALLTXT),
            "owsfz_alltxt_sha256": CG.file_sha256(OWS_ALLTXT), "live_hit_sha256": CG.file_sha256(LIVE_HIT_JSON), "samples": out}
    os.makedirs(a.out, exist_ok=True)
    for tag in out:
        p = os.path.join(a.out, f"rows_{tag}.json")
        json.dump({**{k: v for k, v in spec.items() if k != "samples"}, "sample": out[tag]}, open(p, "w"))
        print(tag, {k: v for k, v in out[tag].items() if k not in ("rows", "columns")}, "sha256_lf", CG.sha256_lf(p))


# ----------------------------------------------------------------------------------------------------------------------- per-cycle worker
_DEC = _WS = _OWS = None


def _init(dll):
    global _DEC, _WS, _OWS
    _DEC = load_decoder(dll)
    _WS = parse_rows(WS_ALLTXT)
    _OWS = parse_rows(OWS_ALLTXT)


def rule_match(dec_payload, row):
    """-> 'i' | 'ii' | None for an output payload against one WSJT-X row dict {payload, text}."""
    if CMP.payload_match(row["payload"], dec_payload, row["text"], CG.V_STAR):
        return "i"
    if PF.i3_of(dec_payload) == 4 and EN.enc_flags(dec_payload, row["text"])["enc_match"]:
        return "ii"
    return None


def _payload_of(res):
    return a91_to_bits(res["a91"], CG.PAYLOAD_BITS)


def _work_cycle(task):
    """task = (cycle_index, stamp, [rows]) -> (records, control_items, cpu_s). Text never leaves this function."""
    ci, stamp, rows = task
    cpu0 = time.process_time()
    dec = _DEC
    pcm = wavio.load_cycle_pcm(os.path.join(WAV_DIR, stamp + ".wav"))
    wl = _WS.get(stamp, [])
    enc_rows = {}                                      # widx -> row dict, encodable rows of this cycle
    for widx, (snr, dt, freq, text) in enumerate(wl):
        tb = dec.true_codeword(text)
        if tb is not None and CG.encode_tones(dec, text) is not None:
            enc_rows[widx] = {"widx": widx, "snr": snr, "dt": dt, "freq": freq, "text": text, "payload": tb[:CG.PAYLOAD_BITS]}
    ows_rows = []
    for (snr, dt, freq, text) in _OWS.get(stamp, []):
        tb = dec.true_codeword(text)
        if tb is not None:
            ows_rows.append({"text": text, "payload": tb[:CG.PAYLOAD_BITS]})
    # seeded derangement over this cycle's encodable rows (V-T2)
    idx = sorted(enc_rows)
    other = {}
    if len(idx) >= 2:
        rng = random.Random(SEED * 100003 + ci)
        sh = idx[:]
        rng.shuffle(sh)
        for k, w in enumerate(sh):
            other[w] = sh[(k + 1) % len(sh)]
    recs, control = [], []
    for (ci_, stamp_, widx, freq, dt, snr, load, live_hit, enc) in rows:
        t0 = time.process_time()
        rec = {"cycle_index": ci, "stamp": stamp, "widx": widx, "snr": snr, "live_hit": live_hit, "fault": 0, "g_right": 0, "g_rule": "", "g_out": 0,
               "g_i3": -1, "g_wrong": 0, "c3_run": 0, "c3_out": 0, "c3_class": "", "c3_i3": -1, "f1b": ""}
        row = enc_rows.get(widx)
        if row is None or row["freq"] != freq or row["snr"] != snr:
            rec["fault"] = 1
            recs.append(rec)
            continue
        anchor_f, anchor_t = float(freq), CG.anchor_time(dt)
        # ---- G: nine lattice cells, production BP -> OSD
        first_out = None
        for cell in lattice.snap_and_neighbours(anchor_f, anchor_t):
            rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
            if rc != 0:
                rec["fault"] = 1
                continue
            res = dec.ldpc_decode_llrs([float(x) for x in llr], max_iters=CG.K_LDPC_ITERATIONS, osd_depth=CG.OSD_DEPTH)
            if res["rc"] != 0 or res["crc_ok"] != 1 or res["a91"] is None:
                continue
            pl = _payload_of(res)
            rec["g_out"] = 1
            if first_out is None:
                first_out = pl
            m = rule_match(pl, row)
            if m:
                rec["g_right"], rec["g_rule"] = 1, m
                first_out = pl
                break
            rec["g_wrong"] = 1
        if first_out is not None:
            rec["g_i3"] = PF.i3_of(first_out)
            if rec["g_i3"] == 4 and row_other(other, row["widx"], enc_rows):
                control.append(("G", int(bool(EN.enc_flags(first_out, enc_rows[other[row["widx"]]]["text"])["enc_match"]))))
        # ---- C3 fallback, BP only (only where G is not RIGHT)
        if not rec["g_right"]:
            rec["c3_run"] = 1
            est = FS.estimate(pcm, anchor_f, anchor_t)
            v = CG.coherent_llrs(pcm, anchor_f, anchor_t, est)
            res = dec.ldpc_decode_llrs([float(x) for x in v["V3"]], max_iters=CG.K_LDPC_ITERATIONS, osd_depth=-1)
            if res["rc"] == 0 and res["path"] == 0 and res["crc_ok"] == 1 and res["a91"] is not None:
                pl = _payload_of(res)
                rec["c3_out"], rec["c3_i3"] = 1, PF.i3_of(pl)
                m = rule_match(pl, row)
                if m:
                    rec["c3_class"] = "right_" + m
                else:
                    rec["c3_class"] = _wrong_class(pl, row, enc_rows, ows_rows)
                rec["f1b"] = GF.costas_snr_noise_ref_db(pcm, anchor_f, anchor_t)
                if rec["c3_i3"] == 4 and row_other(other, row["widx"], enc_rows):
                    control.append(("C3", int(bool(EN.enc_flags(pl, enc_rows[other[row["widx"]]]["text"])["enc_match"]))))
        rec["cpu_s"] = round(time.process_time() - t0, 4)
        recs.append(rec)
    ctl = {"stamp": stamp, "cycle_index": ci, "n_enc_rows": len(enc_rows), "items": control}
    return recs, ctl, time.process_time() - cpu0


def row_other(other, widx, enc_rows):
    return widx in other and other[widx] in enc_rows


def _wrong_class(pl, row, enc_rows, ows_rows):
    far = False
    for w, r in enc_rows.items():
        if w == row["widx"]:
            continue
        if rule_match(pl, r):
            if abs(r["freq"] - row["freq"]) <= NEAR_HZ and abs(r["dt"] - row["dt"]) <= NEAR_S:
                return "near"
            far = True
    if far:
        return "far"
    for r in ows_rows:
        if rule_match(pl, r):
            return "ows"
    return "none"


def run(a):
    spec = json.load(open(a.rows))
    sample = spec["sample"]
    assert sample["columns"] == ROW_COLUMNS
    rows = [r for r in sample["rows"] if r[8]]                      # encodable only
    if a.max_rows:
        keep, n, last = [], 0, None
        for r in rows:
            if n >= a.max_rows and r[0] != last:
                break
            keep.append(r); n += 1; last = r[0]
        rows = keep
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
    with open(os.path.join(a.out, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "when": "start", "dll_sha256": CG.file_sha256(a.dll), "pin": DLL_PIN,
                             "rows_json_sha256_lf": CG.sha256_lf(a.rows), "cycles_to_run": len(tasks), "rows_to_run": sum(len(t[2]) for t in tasks)}) + "\n")
    newfile = not os.path.exists(part) or a.fresh
    cpu = {}
    with open(part, "w" if newfile else "a", newline="\n", encoding="utf-8") as fh, open(os.path.join(a.out, "control.jsonl"), "w" if newfile else "a") as cfh:
        w = csv.writer(fh)
        if newfile:
            w.writerow(OUT_COLUMNS)
        with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll,)) as ex:
            futs = {ex.submit(_work_cycle, t): t[0] for t in tasks}
            n = 0
            for f in as_completed(futs):
                recs, ctl, secs = f.result()
                cpu[futs[f]] = (len(recs), secs)
                for r in recs:
                    w.writerow([r.get(c, "") for c in OUT_COLUMNS])
                cfh.write(json.dumps(ctl) + "\n")
                fh.flush(); cfh.flush()
                n += 1
                if n % 20 == 0:
                    print(f"  {n}/{len(tasks)} cycles", flush=True)
    with open(os.path.join(a.out, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "when": "end", "dll_sha256": CG.file_sha256(a.dll), "pin": DLL_PIN}) + "\n")
    tot = sum(s for _n, s in cpu.values())
    nrows = sum(n for n, _s in cpu.values())
    info = {"cycles": len(cpu), "rows": nrows, "cpu_s": round(tot, 1), "cpu_s_per_row": round(tot / nrows, 4) if nrows else None}
    json.dump(info, open(os.path.join(a.out, "run_info.json"), "w"))
    print(json.dumps(info))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["select", "run"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dll", default=r"D:\Projects\claude\_qa-scratch\q-gate-2\bin\libft8.dll")
    ap.add_argument("--rows")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-rows", type=int, default=0)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--tags", default="", help="select mode: only these sample tags (comma separated)")
    a = ap.parse_args()
    {"select": select, "run": run}[a.mode](a)


if __name__ == "__main__":
    main()
