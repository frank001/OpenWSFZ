#!/usr/bin/env python3
"""COH-FALLBACK step 3: FIELD-ID of the not-confirmed fallback outputs (Architect option (I), spec section 13; Captain: "identify the 123 unconfirmed outputs offline").
Question: are the not-confirmed fallback outputs (path 2, no WSJT-X same-text match within 10 Hz) real signals that WSJT-X missed, or noise that a CRC accepted?
Instrument: for each fallback output, re-encode its message to the 79 tones (ft8_encode_message of the pinned DLL) and measure, in the cycle's audio around the output's own frequency/time,
the fraction of the 58 DATA symbols whose strongest of 8 tone bins is the transmitted tone (HIT). Pure noise gives 1/8. The position (time x frequency grid) is chosen by the 21 Costas symbols ALONE (identical for every message), so the choice does not depend on the message tested; NULLS are the data tones of K other fallback outputs of other cycles (valid codewords, nearly-same messages excluded) scored at that same position.
Groups: U = not-confirmed fallback outputs, C = confirmed fallback outputs (control, positive: real signals WSJT-X also decoded), N = nulls.
PRESENT iff the DATA-symbol HIT >= T, T = the 99th percentile of the pooled nulls (computed from nulls only, before the groups are looked at).  Descriptive; no verdict row.
HK-037: message text exists only in this process's memory, read from the scratch working file; what is written is numeric aggregates. The working file lives under _qa-scratch and is deleted at job close.
  python cf_fbid.py <fb_dump.tsv> <wav_root> <libft8.dll> <out.json>
"""
import collections
import ctypes
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(RR, "n2-coherent-llr-extractor"))
sys.path.insert(0, os.path.join(RR, "gap-locate"))
import coherent_extract as CE  # noqa: E402
import wavio  # noqa: E402

N_SYM = 79
N_TONES = 8
K_NULL = 20                      # null tone sequences per output
SEED = 20261021
NULL_PCTL = 99.0
DF_GRID_HZ = (-3.125, 0.0, 3.125)
DT_HALF_WINDOW_S = 0.12          # search window half-width around the centre
DT_STEP_S = 0.01
FS_OUT = CE.RATE_FINE_HZ         # 2000 Hz
CALIB_HALF_WINDOW_S = 1.0        # first pass: broad search to learn where this replay's reported dt puts symbol 0
UNENCODABLE = "unencodable"
WS_CONF_DF = 10                  # Test B's window, Hz (informational)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def encoder(dll_path):
    dll = ctypes.CDLL(dll_path)
    dll.ft8_encode_message.restype = ctypes.c_int
    dll.ft8_encode_message.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]

    def enc(text):
        buf = (ctypes.c_uint8 * N_SYM)()
        rc = dll.ft8_encode_message(text.encode("ascii", errors="replace"), buf, N_SYM)
        return list(buf) if rc == N_SYM else None
    return enc


SYNC_IDX = list(range(0, 7)) + list(range(36, 43)) + list(range(72, 79))
DATA_IDX = [k for k in range(N_SYM) if k not in set(SYNC_IDX)]
assert len(SYNC_IDX) == 21 and len(DATA_IDX) == 58


def locate_and_score(pcm_cache, pcm, f0, centre_s, half_s, sync_tones, seqs):
    """Position chosen by the 21 Costas symbols ONLY (identical for every message, so the choice is independent of the message under test);
    returns (sync_hit, [data-symbol hit fraction at that position for each tone sequence in seqs])."""
    sync_arr = np.array(sync_tones)
    best, best_X = -1.0, None
    starts = np.arange(centre_s - half_s, centre_s + half_s + 1e-9, DT_STEP_S)
    for dfz in DF_GRID_HZ:
        key = round(f0 + dfz, 3)
        bb = pcm_cache.get(key)
        if bb is None:
            bb = CE.downconvert_decimate(pcm, key)
            pcm_cache[key] = bb
        for st in starts:
            X = CE.correlate_symbols(bb, int(round(st * FS_OUT)))
            am = np.abs(X).argmax(axis=1)
            h = float((am[SYNC_IDX] == sync_arr).mean())
            if h > best:
                best, best_X = h, am
    outs = [float((best_X[DATA_IDX] == np.array(s)[DATA_IDX]).mean()) for s in seqs]
    return best, outs


def shape_class(text):
    t = text.split()
    hashed = any(x.startswith("<") for x in t)
    last = t[-1] if t else ""
    kind = "RR73/73/RRR" if last in ("RR73", "73", "RRR") else ("grid" if len(last) == 4 and last[:2].isalpha() and last[2:].isdigit() else ("report" if last.lstrip("R").lstrip("+-").isdigit() else "other"))
    return ("hashed " if hashed else "") + kind + (" CQ" if t and t[0] == "CQ" else "")


def main():
    dump, wav_root, dll, out = sys.argv[1:5]
    enc = encoder(dll)
    rng = np.random.default_rng(SEED)
    rows = []
    for ln in open(dump, encoding="utf-8"):
        p = ln.rstrip("\n").split("\t")
        if len(p) < 10:
            continue
        stamp, kind, matched, freq, dt, snr, same_any, min_df, wcount, text = p[0], p[1], int(p[2]), int(p[3]), float(p[4]), int(p[5]), int(p[6]), int(p[7]), int(p[8]), "\t".join(p[9:])
        rows.append(dict(stamp=stamp, matched=matched, f=freq, dt=dt, snr=snr, same_any=same_any, min_df=min_df, text=text, tones=enc(text)))
    res = {"outputs": len(rows), "confirmed": sum(r["matched"] for r in rows), "unconfirmed": sum(1 - r["matched"] for r in rows),
           "unencodable": sum(1 for r in rows if r["tones"] is None)}
    ok = [r for r in rows if r["tones"] is not None]
    pcms = {}
    def pcm_of(stamp):
        if stamp not in pcms:
            pcms[stamp] = wavio.load_cycle_pcm(os.path.join(wav_root, "20261009_1752_endurance_run-gathered", "owsfz", "wav", stamp + ".wav"))
        return pcms[stamp]

    # ---- calibration pass (confirmed controls only): where does a reported dt put symbol 0?  Uses the Costas-only locator over a broad window ----
    ctl = [r for r in ok if r["matched"]]
    def locate_start(pcm, f0, centre, half, sync_tones):
        best, bs = -1.0, None
        sync_arr = np.array(sync_tones); cache = {}
        for dfz in DF_GRID_HZ:
            bb = CE.downconvert_decimate(pcm, round(f0 + dfz, 3))
            for st in np.arange(centre - half, centre + half + 1e-9, DT_STEP_S):
                am = np.abs(CE.correlate_symbols(bb, int(round(st * FS_OUT)))).argmax(axis=1)
                h = float((am[SYNC_IDX] == sync_arr).mean())
                if h > best: best, bs = h, float(st)
        return best, bs
    offs = []
    for r in ctl[:80]:
        h, st = locate_start(pcm_of(r["stamp"]), r["f"], r["dt"] + 0.5, CALIB_HALF_WINDOW_S, [r["tones"][i] for i in SYNC_IDX])
        if h >= 0.6:
            offs.append(st - r["dt"])
    c_off = float(np.median(offs)) if offs else 0.5
    res["calibration"] = {"controls_used": min(len(ctl), 80), "with_sync_hit_ge_0.6": len(offs), "start_minus_dt_median_s": c_off,
                          "start_minus_dt_p5_p95": [float(np.percentile(offs, 5)), float(np.percentile(offs, 95))] if offs else None}

    # ---- main pass: locate by Costas, then score the data symbols for the own sequence and K nulls ----
    all_tones = [r["tones"] for r in ok]
    for r in ok:
        pcm = pcm_of(r["stamp"])
        cache = {}
        centre = r["dt"] + c_off
        own = r["tones"]
        cand = [i for i, x in enumerate(ok) if x["stamp"] != r["stamp"]
                and float((np.array(x["tones"])[DATA_IDX] == np.array(own)[DATA_IDX]).mean()) <= 0.3]       # drop sequences that are (nearly) the same message
        pick = rng.choice(cand, size=K_NULL, replace=False)
        sh, outs = locate_and_score(cache, pcm, r["f"], centre, DT_HALF_WINDOW_S, [own[i] for i in SYNC_IDX], [own] + [all_tones[i] for i in pick])
        r["sync_hit"], r["hit"], r["null"] = sh, outs[0], outs[1:]
    pooled = np.array([x for r in ok for x in r["null"]])
    T = float(np.percentile(pooled, NULL_PCTL))
    res["null"] = {"n": int(pooled.size), "mean": float(pooled.mean()), "sd": float(pooled.std()), "p99_threshold_T": T, "max": float(pooled.max())}

    def grp(sel, name):
        g = [r for r in ok if sel(r)]
        hits = np.array([r["hit"] for r in g])
        pres = int((hits >= T).sum())
        lo, hi = wilson(pres, len(g))
        return {"n": len(g), "hit_p10_p50_p90": [float(np.percentile(hits, q)) for q in (10, 50, 90)] if len(g) else None,
                "present": pres, "present_rate": pres / len(g) if g else None, "wilson": [lo, hi]}
    res["U_unconfirmed"] = grp(lambda r: not r["matched"], "U")
    res["C_confirmed_all"] = grp(lambda r: r["matched"], "C")
    # SNR-matched control: confirmed outputs in the same reported-SNR range as the unconfirmed ones
    us = [r["snr"] for r in ok if not r["matched"]]
    if us:
        lo_s, hi_s = min(us), max(us)
        res["C_confirmed_snr_matched"] = grp(lambda r: r["matched"] and lo_s <= r["snr"] <= hi_s, "Cm")
        res["U_snr_range"] = [lo_s, hi_s]
    # within U: by whether WSJT-X decoded the same text in the cycle at another frequency, and by message shape
    res["U_same_text_in_cycle_other_freq"] = grp(lambda r: not r["matched"] and r["same_any"] == 1, "Us")
    res["U_text_absent_from_cycle"] = grp(lambda r: not r["matched"] and r["same_any"] == 0, "Ua")
    shapes = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in ok:
        s = shape_class(r["text"]); i = 0 if not r["matched"] else 2
        shapes[s][i] += 1
        if r["hit"] >= T: shapes[s][i + 1] += 1
    res["shape_unconfirmed_n_present_confirmed_n_present"] = {k: v for k, v in sorted(shapes.items())}
    # does the hit rate of U look like noise (the null) or like signals (C)? rank-sum style: fraction of U above the C median, and of U below the 99th null percentile
    cm = float(np.median([r["hit"] for r in ok if r["matched"]])) if any(r["matched"] for r in ok) else None
    res["U_fraction_above_C_median"] = float(np.mean([r["hit"] >= cm for r in ok if not r["matched"]])) if cm is not None else None
    res["U_hit_histogram_0.05_bins"] = np.histogram([r["hit"] for r in ok if not r["matched"]], bins=np.arange(0, 1.0001, 0.05))[0].tolist()
    res["C_hit_histogram_0.05_bins"] = np.histogram([r["hit"] for r in ok if r["matched"]], bins=np.arange(0, 1.0001, 0.05))[0].tolist()
    res["N_hit_histogram_0.05_bins"] = np.histogram(pooled, bins=np.arange(0, 1.0001, 0.05))[0].tolist()
    # random-CRC expectation (descriptive): attempts x 2^-14
    res["expected_random_crc_passes_given_attempts_172385"] = 172385 / 16384.0
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
