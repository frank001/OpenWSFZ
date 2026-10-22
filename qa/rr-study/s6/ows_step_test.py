"""OWS-REPLAY-CONSISTENCY step 4: the STEP TEST (QA tooling; Architect spec 2026-10-16-2100 section 3 + amendment 1 `arch/ows-replay-consistency` e6db72f2).

Do OpenWSFZ's archive windows contain JUMPS of source time inside a window, and does reproducing them (not only the median placement) explain more of the gap?

    python ows_step_test.py build   --sweep-dir D --audio-dir D --corpus D --wavlist J --runs DIR --shift DIR      (per-chunk e(k), arm P audio + list, PV4)
    python ows_step_test.py analyse --runs DIR --shift DIR --out JSON                                                (Part 1 descriptive, rows P1 / P2)

Frozen rules (amendment 1):
  * e(k) is archive_xcorr's per-1-s-chunk source-time estimate (e = source time - nominal time), k = 0..14, for every OpenWSFZ archive window and every WSJT-X save WAV.
  * A chunk with no match (silence; the window holds about 13 s of played audio) carries the NEAREST matched e(k) in arm P (leading chunks take the first matched one). Steps are counted
    only between CONSECUTIVE MATCHED chunks. PV4 checks matched chunks only.
  * A STEP is |e(k+1) - e(k)| > J, J = the 99.9th percentile of WSJT-X's chunk-to-chunk |delta e| over its windows (stable by construction; J is reported, HK-038).
  * Arm P: chunk k of the WSJT-X window is taken from the [prev | slot | next] stream shifted by d_k = e_O(k) - (median e_W of the play), contiguous 1 s per chunk, so repeats and discards appear
    exactly at the chunk boundaries (nothing interpolated). RESOLUTION LIMIT, stated with P1 and P2: a step that falls INSIDE a chunk is placed at the chunk boundary, so a non-firing
    P2 does not clear steps inside a chunk.
  * Rows (WAV-clustered paired bootstrap, 2,000 resamples): P1 = W_Z - W_P > 0; P2 = W_S - W_P > 0 (the steps beyond the median placement). Share (W_Z - W_P) / (W - A), descriptive.
    What remains after P reads only "not explained by timing at 1 s resolution".
  * The with-step / without-step split of A is reported only if each group has >= MIN_SPLIT_WAVS WAVs (a stated floor, not a derived bar); otherwise "not computable, split degenerate".
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import archive_xcorr as X  # noqa: E402
import ows_input_spread as I  # noqa: E402
import ows_replay_consistency as R  # noqa: E402
import ows_shift_test as T  # noqa: E402

FS = X.FS
WIN = X.WINDOW
N_CHUNKS = WIN // FS            # 15
J_PERCENTILE = 99.9             # spec: p99.9 of WSJT-X's chunk-to-chunk |delta e|
MIN_SPLIT_WAVS = 10             # the stated floor of the Part 1 split (Architect amendment 1: QA's floor, not derived)
PV4_TOL_S = 0.02
PV4_N = 10
SEED = 20261016
GRID_S = 0.25                   # the framer's per-cycle correction, for the descriptive "multiples of 0.25 s"


# ------------------------------------------------------------------ per-chunk offsets

def play_chunk_offsets(plays: list, boundary_key: str, window_path, corpus_loader) -> dict:
    """-> {play_index: [e_s | None] * 15} (archive_xcorr's analyse_window, unchanged)."""
    pl = [{"wav_id": p["wav_id"], "boundary_utc": p[boundary_key]} for p in plays]
    t_lo = min(X.parse_utc(p["boundary_utc"]) for p in pl)
    t_hi = max(X.parse_utc(p["boundary_utc"]) for p in pl)
    origin = t_lo - 30.0
    tl = X.build_timeline(pl, origin, (t_hi - t_lo) + 90.0, corpus_loader)
    out = {}
    for p in plays:
        win = X.read_wav(window_path(p))
        out[p["index"]] = [c["e_s"] for c in X.analyse_window(win, I.stamp_to_epoch(p["stamp"]), tl, origin)]
    return out, tl, origin


def fill_nearest(e: list) -> list:
    """Unmatched chunks take the nearest matched e (ties go to the earlier chunk); needs at least one matched chunk."""
    idx = [k for k, v in enumerate(e) if v is not None]
    if not idx:
        raise ValueError("no matched chunk")
    return [e[min(idx, key=lambda m: (abs(m - k), m))] for k in range(len(e))]


def chunk_deltas(e: list) -> list:
    """|e(k+1) - e(k)| between CONSECUTIVE MATCHED chunks only -> [(k, delta signed)]."""
    return [(k, e[k + 1] - e[k]) for k in range(len(e) - 1) if e[k] is not None and e[k + 1] is not None]


def threshold_j(w_chunks: dict) -> float:
    d = [abs(x) for e in w_chunks.values() for _, x in chunk_deltas(e)]
    return float(np.percentile(d, J_PERCENTILE))


def steps_of(e: list, j: float) -> list:
    return [(k, x) for k, x in chunk_deltas(e) if abs(x) > j]


# ------------------------------------------------------------------ arm P

def piecewise_window(prev, cur, nxt, d_chunks: list) -> tuple:
    """Chunk k takes 1 s of the [prev | cur | nxt] stream starting at 180000 + k*FS + round(d_k * FS). -> (window int16, filled)."""
    z = np.zeros(WIN, dtype=np.int16)
    stream = np.concatenate([prev if prev is not None else z, cur, nxt if nxt is not None else z])
    out = np.zeros(WIN, dtype=np.int16)
    filled = False
    for k, d in enumerate(d_chunks):
        a = WIN + k * FS + int(round(d * FS))
        if a < 0 or a + FS > len(stream):
            raise ValueError("piecewise shift beyond the +-1 slot stream")
        out[k * FS:(k + 1) * FS] = stream[a:a + FS]
        if (a < WIN and prev is None) or (a + FS > 2 * WIN and nxt is None):
            filled = True
    return out, filled


def build_p_arm(plan: list, audio_dir: str, d_chunks: dict, out_dir: str) -> dict:
    lines, filled_n = [], 0
    for p in plan:
        cur = T.read_int16(os.path.join(audio_dir, "wsjt-x", "wav", p["stamp_w"] + ".wav"))
        prev = T.read_int16(os.path.join(audio_dir, "wsjt-x", "wav", T.stamp_plus(p["stamp_w"], -1) + ".wav"))
        nxt = T.read_int16(os.path.join(audio_dir, "wsjt-x", "wav", T.stamp_plus(p["stamp_w"], +1) + ".wav"))
        if cur is None:
            raise FileNotFoundError("save WAV missing for a play")
        win, filled = piecewise_window(prev, cur, nxt, d_chunks[p["index"]])
        filled_n += 1 if filled else 0
        path = os.path.join(out_dir, "%03d.wav" % p["index"])
        T.write_int16(path, win)
        lines.append("%d\t%s\t%s" % (p["index"], path, p["stamp_w"]))
    with open(out_dir + ".tsv", "w", encoding="utf8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"zero_filled_plays": filled_n, "plays": len(plan)}


def pv4(plan, d_chunks, e_o_filled, audio_dir, tl, origin, ids) -> dict:
    """10 seeded P windows through archive_xcorr: the recovered e(k) equals the intended e_O(k) in every MATCHED chunk within the tolerance."""
    worst, n_cmp = 0.0, 0
    for i in ids:
        p = plan[i]
        cur = T.read_int16(os.path.join(audio_dir, "wsjt-x", "wav", p["stamp_w"] + ".wav"))
        prev = T.read_int16(os.path.join(audio_dir, "wsjt-x", "wav", T.stamp_plus(p["stamp_w"], -1) + ".wav"))
        nxt = T.read_int16(os.path.join(audio_dir, "wsjt-x", "wav", T.stamp_plus(p["stamp_w"], +1) + ".wav"))
        win, _ = piecewise_window(prev, cur, nxt, d_chunks[i])
        rec = [c["e_s"] for c in X.analyse_window(win.astype(np.float32), I.stamp_to_epoch(p["stamp_w"]), tl, origin)]
        for k, v in enumerate(rec):
            if v is None:
                continue
            worst = max(worst, abs(v - e_o_filled[i][k]))
            n_cmp += 1
    return {"plays_checked": len(ids), "matched_chunks_compared": n_cmp, "max_abs_error_s": worst, "bar_s": PV4_TOL_S, "result": "PASS" if (n_cmp > 0 and worst <= PV4_TOL_S) else "FAIL"}


def build(sweep_dir, audio_dir, corpus, wavlist, runs_dir, shift_dir) -> dict:
    plan, po, pw = T.load_join(sweep_dir, runs_dir)
    wl = {it["id"]: it for it in json.load(open(wavlist, encoding="utf8"))["items"]}
    cache = {}

    def load(wid):
        if wid not in cache:
            it = wl[wid]
            cache[wid] = X.read_wav(os.path.join(corpus, "wsjt-x", it["run"], it["stamp"] + ".wav"))
        return cache[wid]
    c_o, _, _ = play_chunk_offsets(po, "boundary_utc_o", lambda p: os.path.join(audio_dir, "owsfz", "wav", p["stamp"] + ".wav"), load)
    c_w, tl_w, origin_w = play_chunk_offsets(pw, "boundary_utc", lambda p: os.path.join(audio_dir, "wsjt-x", "wav", p["stamp"] + ".wav"), load)
    med_w = {i: float(np.median([v for v in e if v is not None])) for i, e in c_w.items()}
    e_o_filled = {i: fill_nearest(e) for i, e in c_o.items()}
    d_chunks = {i: [x - med_w[i] for x in e_o_filled[i]] for i in e_o_filled}
    os.makedirs(shift_dir, exist_ok=True)
    res = {"plays": len(plan), "arm_P": build_p_arm(plan, audio_dir, d_chunks, os.path.join(shift_dir, "P"))}
    rng = random.Random(SEED)
    ids = sorted(rng.sample(range(len(plan)), PV4_N))
    res["PV4"] = {**pv4(plan, d_chunks, e_o_filled, audio_dir, tl_w, origin_w, ids), "ids_seed": SEED}
    with open(os.path.join(shift_dir, "chunk_offsets.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump({"e_o": c_o, "e_w": c_w}, fh)
    json.dump(res, open(os.path.join(shift_dir, "step_build.json"), "w"), indent=1)
    return res


# ------------------------------------------------------------------ analysis

def describe_steps(chunks: dict, j: float) -> dict:
    sizes, pos, with_step = [], [], 0
    for e in chunks.values():
        st = steps_of(e, j)
        with_step += 1 if st else 0
        for k, x in st:
            sizes.append(x)
            pos.append(k + 1)                                    # the step lies between chunk k and k+1: it starts at chunk k+1
    a = np.abs(np.array(sizes)) if sizes else np.array([])
    near = (np.abs(a / GRID_S - np.round(a / GRID_S)) * GRID_S <= 0.05) if len(a) else np.array([], dtype=bool)
    return {"windows": len(chunks), "windows_with_step": with_step, "share_windows_with_step": with_step / len(chunks), "steps": len(sizes),
            "step_size_s": {"median_abs": float(np.median(a)) if len(a) else None, "max_abs": float(a.max()) if len(a) else None, "positive": int((np.array(sizes) > 0).sum()) if sizes else 0,
                            "negative": int((np.array(sizes) < 0).sum()) if sizes else 0, "share_within_0.05s_of_a_multiple_of_0.25s": float(near.mean()) if len(near) else None,
                            "exactly_one_grid_step_share_within_0.05s": float((np.abs(a - GRID_S) <= 0.05).mean()) if len(a) else None},
            "position_chunk_index_histogram": {str(k): int(sum(1 for x in pos if x == k)) for k in range(1, N_CHUNKS)}}


def analyse(runs_dir: str, shift_dir: str) -> dict:
    plan = json.load(open(os.path.join(runs_dir, "plan.json"), encoding="utf8"))
    wavs = sorted({p["wav_id"] for p in plan})
    n = len(wavs)
    off = json.load(open(os.path.join(shift_dir, "chunk_offsets.json"), encoding="utf8"))
    c_o = {int(k): v for k, v in off["e_o"].items()}
    c_w = {int(k): v for k, v in off["e_w"].items()}
    j = threshold_j(c_w)
    res = {"J_s": j, "J_basis": "p99.9 of WSJT-X chunk-to-chunk |delta e| over %d windows, matched consecutive chunks only" % len(c_w), "part1": {}, "validity": {}, "rows": {}, "descriptive": {}}
    res["part1"]["owsfz"] = describe_steps(c_o, j)
    res["part1"]["wsjtx"] = describe_steps(c_w, j)
    w_share = res["part1"]["wsjtx"]["share_windows_with_step"]
    o_share = res["part1"]["owsfz"]["share_windows_with_step"]
    res["part1"]["ratio_owsfz_to_wsjtx_share"] = (o_share / w_share) if w_share > 0 else None

    def dec(dirpath, rid):
        f, s = os.path.join(dirpath, rid + ".decodes.tsv"), os.path.join(dirpath, rid + ".json")
        return (R.read_decodes(f), json.load(open(s, encoding="utf8"))) if os.path.isfile(f) and os.path.isfile(s) else (None, None)
    runs = {"R-W": dec(runs_dir, "R-W"), "R-A": dec(runs_dir, "R-A"), "Z": dec(shift_dir, "SH-Z"), "S": dec(shift_dir, "SH-S"), "P": dec(shift_dir, "SH-P")}
    arr = {k: R.tally_arrays(R.trials_of(plan, v[0]), wavs) for k, v in runs.items() if v[0] is not None}
    allidx = np.arange(n)
    # --- Part 1 split of A: WAVs with a step in ANY of their 3 trials (OpenWSFZ's windows) against those without
    has = {w: False for w in wavs}
    for p in plan:
        if steps_of(c_o[p["index"]], j):
            has[p["wav_id"]] = True
    no_idx = np.array([i for i, w in enumerate(wavs) if not has[w]], dtype=int)
    yes_idx = np.array([i for i, w in enumerate(wavs) if has[w]], dtype=int)
    if "R-A" in arr and len(no_idx) >= MIN_SPLIT_WAVS and len(yes_idx) >= MIN_SPLIT_WAVS:
        res["part1"]["A_split"] = I.group_diff(arr["R-A"][0], arr["R-A"][1], no_idx, yes_idx)
        res["part1"]["A_split"]["label"] = "lower = WAVs without a step, upper = WAVs with a step in any trial"
    else:
        res["part1"]["A_split"] = {"result": "not computable, split degenerate", "wavs_without_step": int(len(no_idx)), "wavs_with_step": int(len(yes_idx)), "floor": MIN_SPLIT_WAVS}
    # --- validity and rows
    for k, v in runs.items():
        if v[1]:
            res["validity"].setdefault("SV1", {})[k] = {"sha_equal_start_end": v[1]["native_sha256_start"] == v[1]["native_sha256_end"], "sha": v[1]["native_sha256_start"],
                                                       "abandoned": v[1]["residual_pass"]["abandoned"], "items": v[1]["items"], "wall_s": v[1]["wall_s"]}
    bj = os.path.join(shift_dir, "step_build.json")
    if os.path.isfile(bj):
        b = json.load(open(bj, encoding="utf8"))
        res["validity"]["PV4"] = b["PV4"]
        res["validity"]["SV3_P"] = {**b["arm_P"], "share": b["arm_P"]["zero_filled_plays"] / b["arm_P"]["plays"]}
    if runs["Z"][0] is not None and runs["R-W"][0] is not None:
        differ = sum(1 for p in plan if R.keyed(runs["Z"][0].get(p["index"], []))[0] != R.keyed(runs["R-W"][0].get(p["index"], []))[0])
        res["validity"]["SV2"] = {"plays_differing": differ, "result": "PASS" if differ == 0 else "FAIL"}
    res["measures"] = {k: R.own_cons(*a, allidx) for k, a in arr.items()}
    if all(k in arr for k in ("Z", "S", "P", "R-W", "R-A")):
        p1 = T.paired_diff(arr["Z"], arr["P"], n)
        p2 = T.paired_diff(arr["S"], arr["P"], n)
        share = R.boot(lambda i: (R.own_cons(*arr["Z"], i) - R.own_cons(*arr["P"], i)) / (R.own_cons(*arr["R-W"], i) - R.own_cons(*arr["R-A"], i)), n)
        res["rows"]["P1"] = {"W_Z": res["measures"]["Z"], "W_P": res["measures"]["P"], "W_Z_minus_W_P": p1, "fires": R.excludes_zero(p1, +1), "share_of_W_minus_A": share,
                             "resolution_limit": "steps inside a 1 s chunk are placed at the chunk boundary"}
        res["rows"]["P2"] = {"W_S": res["measures"]["S"], "W_S_minus_W_P": p2, "fires": R.excludes_zero(p2, +1), "reading": "the steps beyond the median placement (at 1 s resolution)"}
        res["descriptive"]["by_batch_W_P"] = {str(b_): R.own_cons(*R.tally_arrays(R.trials_of(plan, runs["P"][0], batch=b_), wavs), allidx) for b_ in (1, 2)}
        res["descriptive"]["remaining_after_P"] = "not explained by timing at 1 s resolution: (W - A) - (W_Z - W_P) = %.4f" % ((res["measures"]["R-W"] - res["measures"]["R-A"]) - (res["measures"]["Z"] - res["measures"]["P"]))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    for a in ("--sweep-dir", "--audio-dir", "--corpus", "--wavlist", "--runs", "--shift"):
        pb.add_argument(a, required=True)
    pa = sub.add_parser("analyse")
    for a in ("--runs", "--shift", "--out"):
        pa.add_argument(a, required=True)
    a = ap.parse_args()
    if a.cmd == "build":
        r = build(a.sweep_dir, a.audio_dir, a.corpus, a.wavlist, a.runs, a.shift)
        print("built; P zero-filled", r["arm_P"]["zero_filled_plays"], "PV4", r["PV4"]["result"], r["PV4"]["max_abs_error_s"])
    else:
        r = analyse(a.runs, a.shift)
        json.dump(r, open(a.out, "w"), indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else (o.tolist() if hasattr(o, "tolist") else str(o)))
        print("analysed; J %.4f s; rows: %s" % (r["J_s"], ",".join(sorted(r["rows"]))))


if __name__ == "__main__":
    main()
