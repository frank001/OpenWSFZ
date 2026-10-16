"""OWS-REPLAY-CONSISTENCY (QA tooling; Architect spec 2026-10-16-1635 + amendment 1 `arch/ows-replay-consistency`).

Why is OpenWSFZ less consistent than WSJT-X on replayed real audio (B2BASE report C6)? Offline, on audio the B2BASE sweeps already recorded:
  R-A  : OpenWSFZ decodes its OWN archive cycle of every play (pass-O slot), 1 repeat, 8 threads
  R-D8 : the same archive cycles, 3 repeats (3 fresh processes), 8 threads         (determinism)
  R-D1 : the same, 1 thread, only if R-D8 is not fully identical                      (threading vs the rest)
  R-W  : OpenWSFZ decodes WSJT-X's save WAV of every play (pass-W slot), 1 repeat, 8 threads

    python ows_replay_consistency.py lists   --sweep-dir D --audio-dir D --out DIR [--pilot N]
    python ows_replay_consistency.py analyse --sweep-dir D --audio-dir D --runs DIR --out JSON [--tag sweep1]

Everything statistical is built on the S6 analyser's OWN code: `s6_analyse.parse_log` / `key_rows` (signal key = (text, rank among same-text rows by frequency), hashed rows
excluded by text) and `s6_stats.wav_tally` (own-universe consistency). The replay is judged by exactly the rule that gave the 71.0 % (test: `own_cons` equals `S.pool`).
Every interval is a WAV-clustered bootstrap (S.BOOT_N resamples, S.BOOT_SEED), PAIRED by WAV wherever two measures are differenced.
HK-037: message text lives only in the reading functions; the working files sit in scratch (outside git) and every output here is an aggregate.

Pre-registered definitions (amendment 1):
  * D8 (i)  = share of plays whose non-hashed key set is identical in all repeats (plays abandoned in any repeat excluded and counted; the full figure beside it).
  * D8 (ii) = for each trial t, the pooled own-universe consistency over the 3 REPEATS of that trial's archive cycle (60 WAVs), then the MEAN over the 3 trials.
  * X2 = D8 (ii) - A, labelled "approximate decomposition, not additive" when D8 (i) < 100 %, "100 % - A: derived, not a finding" when D8 (i) = 100 %.
  * X4 is "sensitivity or threshold density, not separated". Beside it: consistency by bins of each program's own reported SNR (A, W, C_w) and the COMMON-set line
    (signals both programs decoded at least once on the same three save WAVs, matched on the key, binned by WSJT-X's reported SNR).
  * A signal's reported SNR is the mean over the trials in which it was decoded, rounded to the nearest dB (floor(x + 0.5)).
  * By batch: each trial's key set is restricted to the decodes of batch b (1 = pass 0, 2 = residual pass) before the consistency is formed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import s6_analyse as A  # noqa: E402
import s6_stats as S  # noqa: E402

K = S.K
SNR_BINS = ((None, -18), (-17, -10), (-9, None))          # the spec's bins (<= -18, -17 to -10, >= -9 dB)
SNR_BIN_LABELS = ("<= -18 dB", "-17 to -10 dB", ">= -9 dB")
V4_TOL = 0.001                                            # spec V4: L recomputed equals the report's per-sweep figure to 0.1 pp (the report states pp to one decimal)
V_PLAYS = 180                                             # spec V2/V3: 180 plays per sweep at the standard tier (60 WAVs x 3 trials)


# ------------------------------------------------------------------ plan: which file is which play

def load_plays(sweep_dir: str) -> list:
    """The sweep's plays in LIVE PLAY ORDER of the OpenWSFZ pass (ascending pass-O slot)."""
    rows = [json.loads(x) for x in open(os.path.join(sweep_dir, "s6", "s6_playlog.jsonl"), encoding="utf8") if x.strip()]
    plays = [r for r in rows if r["kind"] == "play"]
    plays.sort(key=lambda p: A.stamp_o(p))
    return plays


def make_lists(sweep_dir: str, audio_dir: str, out_dir: str, pilot: int | None = None) -> dict:
    """Writes archive_o.tsv (R-A / R-D inputs), savewav_w.tsv (R-W inputs) and plan.json. -> V2 counts (aggregates only)."""
    plays = load_plays(sweep_dir)
    if pilot:
        plays = plays[:pilot]
    os.makedirs(out_dir, exist_ok=True)
    lists = {"archive_o.tsv": [], "savewav_w.tsv": []}
    plan, missing_o, missing_w = [], 0, 0
    for i, p in enumerate(plays):
        so, sw = A.stamp_o(p), p["slot_stamp"]
        fo = os.path.join(audio_dir, "owsfz", "wav", so + ".wav")
        fw = os.path.join(audio_dir, "wsjt-x", "wav", sw + ".wav")
        missing_o += 0 if os.path.isfile(fo) else 1
        missing_w += 0 if os.path.isfile(fw) else 1
        lists["archive_o.tsv"].append("%d\t%s\t%s" % (i, fo, so))
        lists["savewav_w.tsv"].append("%d\t%s\t%s" % (i, fw, sw))
        plan.append({"index": i, "wav_id": p["wav_id"], "trial": p["trial"], "stamp_o": so, "stamp_w": sw, "band": p["band"]})
    for name, lines in lists.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
    with open(os.path.join(out_dir, "plan.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump(plan, fh)
    return {"plays": len(plays), "missing_archive": missing_o, "missing_savewav": missing_w,
            "v2": "PASS" if (len(plays) == (pilot or V_PLAYS) and not missing_o and not missing_w) else "FAIL"}


# ------------------------------------------------------------------ keys, tallies, bootstrap

def norm_text(t: str) -> str:
    return " ".join(t.split()).upper()


def read_decodes(path: str) -> dict:
    """The harness working file -> {index: [(freq_hz, snr, text, batch)]}. Text stays in memory (HK-037)."""
    out = defaultdict(list)
    with open(path, encoding="utf8") as fh:
        next(fh)
        for line in fh:
            f = line.rstrip("\n").split("\t")
            out[int(f[0])].append((float(f[4]), float(f[2]), norm_text(f[5] if len(f) > 5 else ""), int(f[1])))
    return out


def keyed(rows: list) -> tuple:
    """rows (freq, snr, text, batch) -> ({key: snr}, {key: batch}, n_hashed). The keys are the analyser's own (s6_analyse.key_rows)."""
    keys, hashed = A.key_rows([(f, s, t) for f, s, t, _ in rows])
    seen, batch = defaultdict(int), {}
    for f, s, t, b in sorted((r for r in rows if "<" not in r[2]), key=lambda r: (r[2], r[0])):
        batch[(t, seen[t])] = b
        seen[t] += 1
    assert set(batch) == set(keys), "key/batch ranking drifted from s6_analyse.key_rows"
    return keys, batch, hashed


def snr_bin(x: float, bins=SNR_BINS) -> int:
    v = math.floor(x + 0.5)
    for i, (lo, hi) in enumerate(bins):
        if (lo is None or v >= lo) and (hi is None or v <= hi):
            return i
    raise ValueError("SNR outside every bin")


def own_cons(own: np.ndarray, all_: np.ndarray, idx: np.ndarray) -> float:
    """The analyser's own-universe consistency (s6_stats.pool: sum(own_all) / sum(own)) over the WAVs idx. NaN when the universe is empty."""
    o = own[idx].sum()
    return float(all_[idx].sum() / o) if o else float("nan")


def tally_arrays(trials_by_wav: dict, wavs: list) -> tuple:
    """-> (own[n], all[n]) from S.wav_tally; own = signals decoded at least once over the trials, all = decoded in every trial. Empty/missing WAV -> 0, 0."""
    own, all_ = np.zeros(len(wavs)), np.zeros(len(wavs))
    for i, w in enumerate(wavs):
        trials = trials_by_wav.get(w)
        if not trials:
            continue
        t = S.wav_tally({k: {"w": v, "o": v} for k, v in trials.items()})
        own[i], all_[i] = t["own_o"], t["own_o_all"]
    return own, all_


def boot(stat, n: int, n_boot: int = S.BOOT_N, seed: int = S.BOOT_SEED) -> dict:
    """WAV-clustered bootstrap of stat(idx). `stat` may difference several measures on the SAME idx: that is the pairing."""
    rng = np.random.default_rng(seed)
    point = stat(np.arange(n))
    vals = np.array([stat(rng.integers(0, n, n)) for _ in range(n_boot)], dtype=float)
    vals = vals[np.isfinite(vals)]
    lo, hi = (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) else (float("nan"), float("nan"))
    return {"point": point, "lo": lo, "hi": hi, "resamples": int(len(vals))}


def excludes_zero(ci: dict, sign: int = 0) -> bool:
    """CI excludes 0 (sign: +1 only positive, -1 only negative, 0 either)."""
    if not (math.isfinite(ci["lo"]) and math.isfinite(ci["hi"])):
        return False
    pos, neg = ci["lo"] > 0, ci["hi"] < 0
    return pos if sign > 0 else neg if sign < 0 else (pos or neg)


# ------------------------------------------------------------------ building the per-run data

def trials_of(plan: list, per_index: dict, trial_filter=None, batch=None) -> dict:
    """{wav_id: {trial: {key: snr}}} from a run's decodes. `batch` restricts each trial to that batch's decodes (the by-batch line)."""
    out = defaultdict(dict)
    for p in plan:
        rows = per_index.get(p["index"], [])
        keys, bmap, _ = keyed(rows)
        if batch is not None:
            keys = {k: v for k, v in keys.items() if bmap[k] == batch}
        out[p["wav_id"]][p["trial"]] = keys
    return out


def live_trials(plan: list, log: dict, slot: str) -> dict:
    """{wav_id: {trial: {key: snr}}} from a parsed live ALL.TXT (A.parse_log)."""
    out = defaultdict(dict)
    for p in plan:
        keys, _ = A.key_rows(log.get(p[slot], []))
        out[p["wav_id"]][p["trial"]] = keys
    return out


def bin_counts(trials_by_wav: dict, wavs: list) -> np.ndarray:
    """-> [n_wavs, n_bins, 2] (decoded >= once, decoded in every trial) per own-SNR bin."""
    out = np.zeros((len(wavs), len(SNR_BINS), 2))
    for i, w in enumerate(wavs):
        trials = trials_by_wav.get(w, {})
        nt = len(trials)
        if not nt:
            continue
        cnt, snrs = defaultdict(int), defaultdict(list)
        for t in trials.values():
            for k, s in t.items():
                cnt[k] += 1
                snrs[k].append(s)
        for k, c in cnt.items():
            b = snr_bin(sum(snrs[k]) / len(snrs[k]))
            out[i, b, 0] += 1
            out[i, b, 1] += 1 if c == nt else 0
    return out


def common_set(w_trials: dict, c_trials: dict, wavs: list) -> np.ndarray:
    """The COMMON-set line: signals BOTH programs decoded at least once on the same three save WAVs (matched on the key), binned by WSJT-X's mean reported SNR.
    -> [n_wavs, n_bins, 3] = (n common, n decoded in all trials by OpenWSFZ, n decoded in all trials by WSJT-X)."""
    out = np.zeros((len(wavs), len(SNR_BINS), 3))
    for i, w in enumerate(wavs):
        wt, ct = w_trials.get(w, {}), c_trials.get(w, {})
        if not wt or not ct or sorted(wt) != sorted(ct):
            continue
        nt = len(wt)
        wc, cc, csn = defaultdict(int), defaultdict(int), defaultdict(list)
        for t in wt.values():
            for k in t:
                wc[k] += 1
        for t in ct.values():
            for k, s in t.items():
                cc[k] += 1
                csn[k].append(s)
        for k in set(wc) & set(cc):
            b = snr_bin(sum(csn[k]) / len(csn[k]))
            out[i, b, 0] += 1
            out[i, b, 1] += 1 if wc[k] == nt else 0
            out[i, b, 2] += 1 if cc[k] == nt else 0
    return out


def identity(runs: list, plan: list, abandoned: list) -> dict:
    """D (i): the share of plays whose non-hashed KEY set is identical in every repeat. `abandoned[r]` = set of indices with an abandoned residual pass in repeat r.
    A play abandoned in ANY repeat is excluded from the headline and counted; the full figure is given beside it."""
    ids = [p["index"] for p in plan]
    ex = set().union(*abandoned) if abandoned else set()
    same_all, same_ex, n_ex, same_snr = 0, 0, 0, 0
    for i in ids:
        sets = [frozenset(keyed(r.get(i, []))[0]) for r in runs]
        full = [tuple(sorted(keyed(r.get(i, []))[0].items())) for r in runs]
        ident = len(set(sets)) == 1
        same_all += ident
        same_snr += len(set(full)) == 1
        if i in ex:
            n_ex += 1
        else:
            same_ex += ident
    n = len(ids)
    return {"plays": n, "identical_full": same_all, "share_full": same_all / n if n else None,
            "plays_excluded_abandoned": n_ex, "identical_kept": same_ex, "share_kept": same_ex / (n - n_ex) if n - n_ex else None,
            "identical_incl_snr_full": same_snr}


def repeat_consistency(runs: list, plan: list, wavs: list, abandoned: list, batch=None) -> tuple:
    """D (ii): for each trial t the own-universe consistency over the REPEATS of that trial's cycle (60 WAVs), then the mean over the trials.
    -> (own[t][n], all[t][n]) arrays so the caller can bootstrap them paired with other measures. A play abandoned in any repeat is dropped from its (WAV, t) cell."""
    ex = set().union(*abandoned) if abandoned else set()
    ts = sorted({p["trial"] for p in plan})
    own = np.zeros((len(ts), len(wavs)))
    all_ = np.zeros((len(ts), len(wavs)))
    wi = {w: i for i, w in enumerate(wavs)}
    for p in plan:
        if p["index"] in ex:
            continue
        reps = {}
        for r, run in enumerate(runs):
            keys, bmap, _ = keyed(run.get(p["index"], []))
            reps[r] = {k: v for k, v in keys.items() if batch is None or bmap[k] == batch}
        t = S.wav_tally({r: {"w": v, "o": v} for r, v in reps.items()})
        own[ts.index(p["trial"]), wi[p["wav_id"]]] = t["own_o"]
        all_[ts.index(p["trial"]), wi[p["wav_id"]]] = t["own_o_all"]
    return own, all_


def mean_over_trials(own: np.ndarray, all_: np.ndarray, idx: np.ndarray) -> float:
    vals = [own_cons(own[t], all_[t], idx) for t in range(own.shape[0])]
    return float(np.mean(vals)) if all(math.isfinite(v) for v in vals) else float("nan")


# ------------------------------------------------------------------ the rows

def abandoned_of(summary: dict) -> set:
    return {x["index"] for x in summary["item_info"] if x["abandoned"] > 0}


def analyse(sweep_dir: str, audio_dir: str, runs_dir: str, tag: str = "sweep") -> dict:
    plan = json.load(open(os.path.join(runs_dir, "plan.json"), encoding="utf8"))
    wavs = sorted({p["wav_id"] for p in plan})
    n = len(wavs)

    def load(run_id):
        dec = os.path.join(runs_dir, run_id + ".decodes.tsv")
        sm = os.path.join(runs_dir, run_id + ".json")
        return (read_decodes(dec), json.load(open(sm, encoding="utf8"))) if os.path.isfile(dec) and os.path.isfile(sm) else (None, None)

    res = {"tag": tag, "plays": len(plan), "wavs": n, "rows": {}, "validity": {}, "descriptive": {}}
    runs = {rid: load(rid) for rid in ("R-A", "R-W", "R-D8-1", "R-D8-2", "R-D8-3", "R-D1-1", "R-D1-2", "R-D1-3")}
    have = {rid for rid, (d, _) in runs.items() if d is not None}

    # --- validity V1, V3, V5
    pins = {}
    for rid in sorted(have):
        s = runs[rid][1]
        pins[rid] = {"sha_equal_start_end": s["native_sha256_start"] == s["native_sha256_end"], "sha": s["native_sha256_start"], "readback": s["readback_start"],
                     "items": s["items"], "abandoned": s["residual_pass"]["abandoned"], "ran": s["residual_pass"]["ran"], "wall_s": s["wall_s"],
                     "cpu_s": s["cpu_s"], "contained": s["residual_pass"]["contained"]}
    res["validity"]["V1_runs"] = pins
    res["validity"]["V3"] = {rid: (pins[rid]["items"] == len(plan)) for rid in pins}
    res["validity"]["V5_untagged"] = {rid: runs[rid][1]["untagged_decodes"] for rid in sorted(have)}

    # --- live L and C_w from the full captured-audio ALL.TXT files, with the analyser's own parser
    live_o = A.parse_log(os.path.join(audio_dir, "owsfz", "ALL.TXT"))
    live_w = A.parse_log(os.path.join(audio_dir, "wsjt-x", "ALL.TXT"))
    L_tr, Cw_tr = live_trials(plan, live_o, "stamp_o"), live_trials(plan, live_w, "stamp_w")
    L_own, L_all = tally_arrays(L_tr, wavs)
    C_own, C_all = tally_arrays(Cw_tr, wavs)
    allidx = np.arange(n)
    res["descriptive"]["L_live_owsfz"] = own_cons(L_own, L_all, allidx)
    res["descriptive"]["C_w_live_wsjtx"] = own_cons(C_own, C_all, allidx)
    sr = os.path.join(sweep_dir, "s6", "s6_result.json")
    if os.path.isfile(sr):
        h = json.load(open(sr, encoding="utf8"))["full"]["headline"]
        rep_o, rep_w = h["consistency_own_owsfz"], h["consistency_own_wsjtx"]
        res["validity"]["V4"] = {"L_recomputed": res["descriptive"]["L_live_owsfz"], "L_report": rep_o, "C_w_recomputed": res["descriptive"]["C_w_live_wsjtx"],
                                 "C_w_report": rep_w, "result": "PASS" if abs(res["descriptive"]["L_live_owsfz"] - rep_o) <= V4_TOL else "FAIL"}

    def arr_from_run(rid, batch=None):
        return tally_arrays(trials_of(plan, runs[rid][0], batch=batch), wavs)

    A_arr = arr_from_run("R-A") if "R-A" in have else None
    W_arr = arr_from_run("R-W") if "R-W" in have else None

    # --- X0: replay vs live (descriptive)
    if A_arr:
        ci = boot(lambda i: own_cons(*A_arr, i) - own_cons(L_own, L_all, i), n)
        reproduced, extra, live_n, a_n = 0, 0, 0, 0
        for p in plan:
            lk = set(A.key_rows(live_o.get(p["stamp_o"], []))[0])
            ak = set(keyed(runs["R-A"][0].get(p["index"], []))[0])
            reproduced += len(lk & ak)
            extra += len(ak - lk)
            live_n += len(lk)
            a_n += len(ak)
        res["rows"]["X0"] = {"A": own_cons(*A_arr, allidx), "L": res["descriptive"]["L_live_owsfz"], "A_minus_L": ci, "CI_excludes_0": excludes_zero(ci),
                             "live_rows_reproduced_share": reproduced / live_n if live_n else None, "extra_row_share_of_replay": extra / a_n if a_n else None,
                             "label": "replay != live by A - L" if excludes_zero(ci) else "replay consistent with live (CI of A - L contains 0)"}

    # --- X1, X2: determinism and input
    d8_ids = [f"R-D8-{i}" for i in (1, 2, 3) if f"R-D8-{i}" in have]
    d1_ids = [f"R-D1-{i}" for i in (1, 2, 3) if f"R-D1-{i}" in have]
    ident = {}
    D = {}
    for name, ids in (("D8", d8_ids), ("D1", d1_ids)):
        if len(ids) == 3:
            decs = [runs[r][0] for r in ids]
            ab = [abandoned_of(runs[r][1]) for r in ids]
            ident[name] = identity(decs, plan, ab)
            D[name] = repeat_consistency(decs, plan, wavs, ab)
            D[name + "_full"] = repeat_consistency(decs, plan, wavs, [set()] * 3)
    if "D8" in ident:
        o, a_ = D["D8"]
        ci_d = boot(lambda i: mean_over_trials(o, a_, i), n)
        x1 = {"D8_identity": ident["D8"], "D8_ii": ci_d, "D8_ii_full_incl_abandoned": mean_over_trials(*D["D8_full"], allidx),
              "fires": ident["D8"]["share_kept"] is not None and ident["D8"]["share_kept"] < 1.0, "size_lost_with_no_input_change": 1.0 - ci_d["point"]}
        if "D1" in ident:
            x1["D1_identity"] = ident["D1"]
            x1["reading"] = ("the non-determinism is in the multi-threaded path" if x1["fires"] and ident["D1"]["share_kept"] == 1.0
                             else "non-determinism remains at 1 thread" if x1["fires"] else "decoder deterministic on identical audio")
        else:
            x1["reading"] = "decoder deterministic on identical audio (R-D1 not run)" if not x1["fires"] else "non-determinism (R-D1 not run: threading vs the rest not separated)"
        res["rows"]["X1"] = x1
        if A_arr:
            ci_x2 = boot(lambda i: mean_over_trials(o, a_, i) - own_cons(*A_arr, i), n)
            res["rows"]["X2"] = {"D8_ii_minus_A": ci_x2, "fires": excludes_zero(ci_x2, +1),
                                 "label": ("100 % - A: derived, not a finding" if not x1["fires"] else "approximate decomposition, not additive")}
    if W_arr and A_arr:
        ci3 = boot(lambda i: own_cons(*W_arr, i) - own_cons(*A_arr, i), n)
        res["rows"]["X3"] = {"W": own_cons(*W_arr, allidx), "A": own_cons(*A_arr, allidx), "W_minus_A": ci3, "fires": excludes_zero(ci3),
                             "reading": ("OpenWSFZ more consistent on WSJT-X's captures than on its own (capture or framing side)" if excludes_zero(ci3, +1)
                                         else "OpenWSFZ less consistent on WSJT-X's captures than on its own" if excludes_zero(ci3, -1) else "no difference at this n")}
    if W_arr:
        ci4 = boot(lambda i: own_cons(*W_arr, i) - own_cons(C_own, C_all, i), n)
        res["rows"]["X4"] = {"W": own_cons(*W_arr, allidx), "C_w": own_cons(C_own, C_all, allidx), "W_minus_C_w": ci4, "fires": excludes_zero(ci4, -1),
                             "label": "sensitivity or threshold density, not separated"}

    # --- descriptive: by batch, by SNR, common set, archive health
    for rid, key in (("R-A", "A"), ("R-W", "W")):
        if rid in have:
            res["descriptive"]["by_batch_" + key] = {str(b): own_cons(*arr_from_run(rid, b), allidx) for b in (1, 2)}
    if d8_ids and len(d8_ids) == 3:
        decs = [runs[r][0] for r in d8_ids]
        ab = [abandoned_of(runs[r][1]) for r in d8_ids]
        res["descriptive"]["by_batch_D8_ii"] = {str(b): mean_over_trials(*repeat_consistency(decs, plan, wavs, ab, batch=b), allidx) for b in (1, 2)}
    snr = {}
    for key, trs in (("A", trials_of(plan, runs["R-A"][0]) if "R-A" in have else None), ("W", trials_of(plan, runs["R-W"][0]) if "R-W" in have else None),
                     ("C_w", Cw_tr)):
        if trs:
            bc = bin_counts(trs, wavs)
            snr[key] = [{"bin": SNR_BIN_LABELS[b], "n_signals": int(bc[:, b, 0].sum()),
                         "consistency": boot(lambda i, b=b: float(bc[i, b, 1].sum() / bc[i, b, 0].sum()) if bc[i, b, 0].sum() else float("nan"), n)}
                        for b in range(len(SNR_BINS))]
    res["descriptive"]["by_own_snr"] = snr
    if "R-W" in have:
        cs = common_set(trials_of(plan, runs["R-W"][0]), Cw_tr, wavs)
        res["descriptive"]["common_set_W_vs_C_w"] = [
            {"bin": SNR_BIN_LABELS[b], "n_common": int(cs[:, b, 0].sum()),
             "W": float(cs[:, b, 1].sum() / cs[:, b, 0].sum()) if cs[:, b, 0].sum() else None,
             "C_w": float(cs[:, b, 2].sum() / cs[:, b, 0].sum()) if cs[:, b, 0].sum() else None,
             "W_minus_C_w": boot(lambda i, b=b: float((cs[i, b, 1].sum() - cs[i, b, 2].sum()) / cs[i, b, 0].sum()) if cs[i, b, 0].sum() else float("nan"), n)}
            for b in range(len(SNR_BINS))]
    arch = os.path.join(audio_dir, "owsfz", "cycle-archive.csv")
    if os.path.isfile(arch):
        want = {p["stamp_o"] + ".wav" for p in plan}
        rows = [r for r in csv.DictReader(open(arch, encoding="utf8")) if r["filename"] in want]
        res["descriptive"]["archive_health"] = {"cycles": len(rows), "with_clipped": sum(1 for r in rows if int(r["clipped_samples"]) > 0),
                                                "with_dropped_before": sum(1 for r in rows if int(r["dropped_before"]) > 0)}
    res["descriptive"]["input_difference_archive_xcorr"] = "not computed: needs the played corpus audio and a cross-correlation pass (s6/archive_xcorr.py); a separate step"
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("lists")
    pl.add_argument("--sweep-dir", required=True)
    pl.add_argument("--audio-dir", required=True)
    pl.add_argument("--out", required=True)
    pl.add_argument("--pilot", type=int, default=None)
    pa = sub.add_parser("analyse")
    pa.add_argument("--sweep-dir", required=True)
    pa.add_argument("--audio-dir", required=True)
    pa.add_argument("--runs", required=True)
    pa.add_argument("--out", required=True)
    pa.add_argument("--tag", default="sweep")
    a = ap.parse_args()
    if a.cmd == "lists":
        print(json.dumps(make_lists(a.sweep_dir, a.audio_dir, a.out, a.pilot)))
    else:
        r = analyse(a.sweep_dir, a.audio_dir, a.runs, a.tag)
        with open(a.out, "w", encoding="utf8", newline="\n") as fh:
            json.dump(r, fh, indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else (o.tolist() if hasattr(o, "tolist") else str(o)))
        print("analysed", a.tag, "rows:", ",".join(sorted(r["rows"])))


if __name__ == "__main__":
    main()
