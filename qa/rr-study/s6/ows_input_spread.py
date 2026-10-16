"""OWS-REPLAY-CONSISTENCY step 2: the INPUT-DIFFERENCE line (QA tooling; Architect sweep-1 ruling section 4.2).

For ONE sweep and BOTH appraisers: how much does each appraiser's capture of the SAME played WAV differ from trial to trial, and does that separate the WAVs that are consistent
from those that are not?

    python ows_input_spread.py --sweep-dir D --audio-dir D --corpus D --wavlist s6-wavlist.json --runs DIR --out JSON

Method (reuses archive_xcorr.py's own functions: build_timeline, analyse_window, parse_utc):
  * the played stream of each pass is rebuilt on a wall-clock timeline from the corpus audio at the pass's own boundaries (WSJT-X pass: `boundary_utc`; OpenWSFZ pass: `boundary_utc_o`);
  * each play's captured 15 s window (OpenWSFZ: the cycle archive WAV of its pass-O slot; WSJT-X: its save WAV of its pass-W slot) is cut into 1 s chunks, each correlated with the timeline
    within +-14 s: e(chunk) = source time - nominal time;
  * e of a PLAY = the median e over its matched chunks (a play needs >= 1 matched chunk; WAVs with a trial lacking one are excluded and counted);
  * SPREAD of a WAV = max - min of the e of its 3 trials (seconds), per appraiser;
  * the WAVs are split at the MEDIAN spread (a data-derived cut, so descriptive only): lower = spread < median, upper = spread > median, WAVs equal to the median are counted aside;
  * for each group the own-universe consistency (s6_stats via ows_replay_consistency): OpenWSFZ on its own captures (A, R-A), OpenWSFZ on WSJT-X's captures (W, R-W), WSJT-X's own (C_w);
    the upper - lower difference carries an UNPAIRED WAV-clustered bootstrap CI (the groups are disjoint WAV sets); Spearman rho of spread against per-WAV consistency is given beside it.
Pre-stated reading (sweep-1 ruling 4.2): if the spread does not separate the groups (the CI of upper - lower contains 0, rho's CI/p likewise), the report says so plainly.
No message text is read except through ows_replay_consistency's own readers; every output is an aggregate.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import archive_xcorr as X  # noqa: E402
import ows_replay_consistency as R  # noqa: E402
import s6_stats as S  # noqa: E402

MIN_MATCHED_CHUNKS = 1          # a play needs at least one matched chunk to have an offset (design: any fewer and it has none)


def stamp_to_epoch(stamp: str) -> float:
    from datetime import datetime, timezone
    return datetime.strptime(stamp, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc).timestamp()


def play_offsets(plays: list, boundary_key: str, window_path, corpus_loader, trim_s: float = 0.0) -> dict:
    """-> {play_index: {"e_med": float | None, "matched": int, "chunks": int, "median_peak": float}} for one pass.
    `plays`: dicts with wav_id, boundary_key, stamp. `window_path(p)` -> a WAV path; `corpus_loader(wav_id)` -> float32 samples."""
    pl = [{"wav_id": p["wav_id"], "boundary_utc": p[boundary_key]} for p in plays]
    t_lo = min(X.parse_utc(p["boundary_utc"]) for p in pl)
    t_hi = max(X.parse_utc(p["boundary_utc"]) for p in pl)
    origin = t_lo - 30.0
    tl = X.build_timeline(pl, origin, (t_hi - t_lo) + 90.0, corpus_loader)
    out = {}
    for p in plays:
        win = X.read_wav(window_path(p))
        chunks = X.analyse_window(win, stamp_to_epoch(p["stamp"]), tl, origin)
        es = [c["e_s"] for c in chunks if c["e_s"] is not None]
        out[p["index"]] = {"e_med": float(np.median(es)) if len(es) >= MIN_MATCHED_CHUNKS else None, "matched": len(es), "chunks": len(chunks),
                           "median_peak": float(np.median([c["peak"] for c in chunks]))}
    return out


def wav_spreads(plan: list, offsets: dict, wavs: list) -> tuple:
    """-> (spread[n] (NaN when a trial has no offset), n_excluded). Spread = max - min of the WAV's trial offsets."""
    by = {w: [] for w in wavs}
    for p in plan:
        by[p["wav_id"]].append(offsets[p["index"]]["e_med"])
    sp = np.full(len(wavs), np.nan)
    for i, w in enumerate(wavs):
        v = by[w]
        if v and all(x is not None for x in v):
            sp[i] = max(v) - min(v)
    return sp, int(np.isnan(sp).sum())


def split_at_median(spread: np.ndarray) -> dict:
    ok = np.isfinite(spread)
    med = float(np.median(spread[ok]))
    return {"median": med, "lower": np.where(ok & (spread < med))[0], "upper": np.where(ok & (spread > med))[0], "equal": np.where(ok & (spread == med))[0]}


def group_diff(own: np.ndarray, all_: np.ndarray, lower: np.ndarray, upper: np.ndarray, n_boot: int = S.BOOT_N, seed: int = S.BOOT_SEED) -> dict:
    """Own-universe consistency of the upper-spread group minus the lower-spread group, UNPAIRED WAV-clustered bootstrap (disjoint WAV sets)."""
    rng = np.random.default_rng(seed)

    def cons(idx):
        o = own[idx].sum()
        return float(all_[idx].sum() / o) if o else float("nan")
    point_l, point_u = cons(lower), cons(upper)
    vals = np.array([cons(rng.choice(upper, len(upper))) - cons(rng.choice(lower, len(lower))) for _ in range(n_boot)])
    vals = vals[np.isfinite(vals)]
    lo, hi = (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) else (float("nan"), float("nan"))
    return {"lower_n_wavs": int(len(lower)), "upper_n_wavs": int(len(upper)), "lower": point_l, "upper": point_u, "upper_minus_lower": point_u - point_l, "lo": lo, "hi": hi,
            "separates": bool(math.isfinite(lo) and (lo > 0 or hi < 0))}


def spearman_rho(spread: np.ndarray, own: np.ndarray, all_: np.ndarray) -> dict:
    from scipy.stats import spearmanr
    ok = np.isfinite(spread) & (own > 0)
    if ok.sum() < 5:
        return {"n": int(ok.sum()), "rho": None, "p": None}
    r = spearmanr(spread[ok], all_[ok] / own[ok])
    return {"n": int(ok.sum()), "rho": float(r.statistic), "p": float(r.pvalue)}


def describe(spread: np.ndarray) -> dict:
    s = spread[np.isfinite(spread)]
    return {"wavs_with_spread": int(len(s)), "median_s": float(np.median(s)), "p90_s": float(np.percentile(s, 90)), "max_s": float(s.max()), "min_s": float(s.min())}


def run(sweep_dir: str, audio_dir: str, corpus: str, wavlist: str, runs_dir: str) -> dict:
    plan = json.load(open(os.path.join(runs_dir, "plan.json"), encoding="utf8"))
    plays = {p["index"]: p for p in R.load_plays(sweep_dir)}
    # plan index i == the i-th play in pass-O slot order (R.load_plays); join the boundaries back by the stamps
    by_stamp = {R.A.stamp_o(p): p for p in plays.values()}
    pw = [{"index": q["index"], "wav_id": q["wav_id"], "stamp": q["stamp_w"], "boundary_utc": by_stamp[q["stamp_o"]]["boundary_utc"]} for q in plan]
    po = [{"index": q["index"], "wav_id": q["wav_id"], "stamp": q["stamp_o"], "boundary_utc_o": by_stamp[q["stamp_o"]]["boundary_utc_o"]} for q in plan]
    wl = {it["id"]: it for it in json.load(open(wavlist, encoding="utf8"))["items"]}
    cache = {}

    def load(wid):
        if wid not in cache:
            it = wl[wid]
            cache[wid] = X.read_wav(os.path.join(corpus, "wsjt-x", it["run"], it["stamp"] + ".wav"))
        return cache[wid]
    off_o = play_offsets(po, "boundary_utc_o", lambda p: os.path.join(audio_dir, "owsfz", "wav", p["stamp"] + ".wav"), load)
    off_w = play_offsets(pw, "boundary_utc", lambda p: os.path.join(audio_dir, "wsjt-x", "wav", p["stamp"] + ".wav"), load)
    wavs = sorted({p["wav_id"] for p in plan})
    sp_o, ex_o = wav_spreads(plan, off_o, wavs)
    sp_w, ex_w = wav_spreads(plan, off_w, wavs)

    def load_run(rid):
        dec = R.read_decodes(os.path.join(runs_dir, rid + ".decodes.tsv"))
        return R.tally_arrays(R.trials_of(plan, dec), wavs)
    A_own, A_all = load_run("R-A")
    W_own, W_all = load_run("R-W")
    live_w = R.A.parse_log(os.path.join(audio_dir, "wsjt-x", "ALL.TXT"))
    C_own, C_all = R.tally_arrays(R.live_trials(plan, live_w, "stamp_w"), wavs)

    res = {"wavs": len(wavs), "plays": len(plan), "min_matched_chunks": MIN_MATCHED_CHUNKS,
           "offsets": {"owsfz": {"plays_with_offset": sum(1 for v in off_o.values() if v["e_med"] is not None), "median_play_matched_chunks": float(np.median([v["matched"] for v in off_o.values()])),
                                  "play_e_median_s": float(np.median([v["e_med"] for v in off_o.values() if v["e_med"] is not None]))},
                       "wsjtx": {"plays_with_offset": sum(1 for v in off_w.values() if v["e_med"] is not None), "median_play_matched_chunks": float(np.median([v["matched"] for v in off_w.values()])),
                                  "play_e_median_s": float(np.median([v["e_med"] for v in off_w.values() if v["e_med"] is not None]))}},
           "spread": {"owsfz": {**describe(sp_o), "wavs_excluded": ex_o}, "wsjtx": {**describe(sp_w), "wavs_excluded": ex_w}}, "lines": {}}
    for name, sp, measures in (("owsfz_capture", sp_o, {"A_owsfz_own_captures": (A_own, A_all)}),
                               ("wsjtx_capture", sp_w, {"W_owsfz_on_wsjtx_captures": (W_own, W_all), "C_w_wsjtx_own": (C_own, C_all)})):
        sg = split_at_median(sp)
        res["lines"][name] = {"median_spread_s": sg["median"], "wavs_equal_to_median": int(len(sg["equal"])), "measures": {}}
        for mname, (own, all_) in measures.items():
            res["lines"][name]["measures"][mname] = {**group_diff(own, all_, sg["lower"], sg["upper"]), "spearman_spread_vs_wav_consistency": spearman_rho(sp, own, all_)}
    # the cross line: OpenWSFZ-capture spread against WSJT-X's consistency, and WSJT-X-capture spread against A, are NOT given: a capture's spread explains that capture's decodes
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep-dir", required=True)
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--wavlist", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = run(a.sweep_dir, a.audio_dir, a.corpus, a.wavlist, a.runs)
    json.dump(r, open(a.out, "w"), indent=1)
    print("done; spread medians (s): owsfz %.4f wsjtx %.4f" % (r["spread"]["owsfz"]["median_s"], r["spread"]["wsjtx"]["median_s"]))


if __name__ == "__main__":
    main()
