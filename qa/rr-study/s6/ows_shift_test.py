"""OWS-REPLAY-CONSISTENCY step 3: the SHIFT TEST (QA tooling; Architect spec 2026-10-16-2150, section 3).

Is window placement ALONE enough to make OpenWSFZ inconsistent? Take WSJT-X's save WAVs (stable placement; OpenWSFZ is ~90 % consistent on them) and give each trial OpenWSFZ's
MEASURED placement error for that play, then decode again with the same harness, pins and settings as R-W.

    python ows_shift_test.py build   --sweep-dir D --audio-dir D --corpus D --wavlist J --runs DIR --out DIR   (offsets, shifted WAVs, lists, SV4 spot check)
    python ows_shift_test.py analyse --sweep-dir D --audio-dir D --runs DIR --shift DIR --daemon-log LOG --tz-h 2 --out JSON

Arms (each one fresh harness process, ids SH-Z / SH-S / SH-K):
  Z identity (shift 0): must reproduce R-W exactly.   S measured: d = e_O - e_W for that play.   K constant: per WAV, the mean of its 3 d values, applied to all 3 trials.
Construction: the stream is [WSJT-X slot before | the slot | the slot after] (zeros where a neighbour file is missing; counted). The shifted window starts d seconds LATER than the
saved one (window sample 0 then carries source time nominal + e_O: archive_xcorr's convention e = source time - nominal time; positive d = later). int16 throughout, so Z is bit-identical.
Rows (WAV-clustered paired bootstrap, 2,000 resamples, s6_stats via ows_replay_consistency):
  S1 = W_Z - W_S > 0 (CI excludes 0): placement alone lowers consistency; share (W_Z - W_S) / (W - A), descriptive.
  S2 = W_Z - W_K > 0: the mean lag alone also lowers it.
  S3 = W_K - W_S > 0 (QA ADDITION, direct paired contrast): the SPREAD beyond the mean lag. Added because "S1 fires while S2 does not" compares two significance verdicts, not the arms.
Limits stated with the rows: one constant shift per play does not model steps INSIDE a window (the framer's realignment), so a non-firing S1 does not clear placement.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import wave
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import archive_xcorr as X  # noqa: E402
import ows_input_spread as I  # noqa: E402
import ows_replay_consistency as R  # noqa: E402

FS = X.FS
WIN = X.WINDOW
SLOT_S = 15
SV4_TOL_S = 0.02            # spec SV4: half the WSJT-X spread's p90 (0.050 s), from sweep1_input_spread.json
SV4_N = 10
SV3_FILL_SHARE = 0.10       # spec SV3: more than 10 % of the plays zero-filled labels S1 and S2 "fill-affected"
SEED = 20261016
ARMS = {"Z": "SH-Z", "S": "SH-S", "K": "SH-K"}


# ------------------------------------------------------------------ construction

def stamp_plus(stamp: str, slots: int) -> str:
    t = datetime.strptime(stamp, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc) + timedelta(seconds=SLOT_S * slots)
    return t.strftime("%y%m%d_%H%M%S")


def read_int16(path: str) -> np.ndarray | None:
    if not os.path.isfile(path):
        return None
    with wave.open(path, "rb") as w:
        assert w.getframerate() == FS and w.getnchannels() == 1 and w.getsampwidth() == 2, os.path.basename(path)
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return x if len(x) == WIN else None


def write_int16(path: str, x: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(x.astype(np.int16).tobytes())


def shift_window(prev: np.ndarray | None, cur: np.ndarray, nxt: np.ndarray | None, d_s: float) -> tuple:
    """-> (window int16, filled). The window starts round(d_s * FS) samples later in [prev | cur | nxt]; a missing neighbour is zeros. `filled` = the window reaches a missing neighbour."""
    m0 = int(round(d_s * FS))
    z = np.zeros(WIN, dtype=np.int16)
    stream = np.concatenate([prev if prev is not None else z, cur, nxt if nxt is not None else z])
    a = WIN + m0
    if a < 0 or a + WIN > len(stream):
        raise ValueError("shift beyond the +-1 slot stream")
    filled = (m0 < 0 and prev is None) or (m0 > 0 and nxt is None)
    return stream[a:a + WIN].copy(), filled


def build_arm(plan: list, audio_dir: str, shifts: dict, out_arm_dir: str) -> dict:
    """Write the shifted WAVs of one arm and its list file. -> {"zero_filled_plays": n}."""
    lines, filled_n = [], 0
    for p in plan:
        cur = read_int16(os.path.join(audio_dir, "wsjt-x", "wav", p["stamp_w"] + ".wav"))
        prev = read_int16(os.path.join(audio_dir, "wsjt-x", "wav", stamp_plus(p["stamp_w"], -1) + ".wav"))
        nxt = read_int16(os.path.join(audio_dir, "wsjt-x", "wav", stamp_plus(p["stamp_w"], +1) + ".wav"))
        if cur is None:
            raise FileNotFoundError("save WAV missing for a play")
        win, filled = shift_window(prev, cur, nxt, shifts[p["index"]])
        filled_n += 1 if filled else 0
        path = os.path.join(out_arm_dir, "%03d.wav" % p["index"])
        write_int16(path, win)
        lines.append("%d\t%s\t%s" % (p["index"], path, p["stamp_w"]))
    with open(out_arm_dir + ".tsv", "w", encoding="utf8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"zero_filled_plays": filled_n, "plays": len(plan)}


def constant_shifts(plan: list, d_s: dict) -> dict:
    """K arm: per WAV the mean of its trials' d, applied to every trial of the WAV."""
    by = {}
    for p in plan:
        by.setdefault(p["wav_id"], []).append(d_s[p["index"]])
    mean = {w: sum(v) / len(v) for w, v in by.items()}
    return {p["index"]: mean[p["wav_id"]] for p in plan}


def load_join(sweep_dir: str, runs_dir: str) -> tuple:
    plan = json.load(open(os.path.join(runs_dir, "plan.json"), encoding="utf8"))
    by_stamp = {R.A.stamp_o(p): p for p in R.load_plays(sweep_dir)}
    po = [{"index": q["index"], "wav_id": q["wav_id"], "stamp": q["stamp_o"], "boundary_utc_o": by_stamp[q["stamp_o"]]["boundary_utc_o"]} for q in plan]
    pw = [{"index": q["index"], "wav_id": q["wav_id"], "stamp": q["stamp_w"], "boundary_utc": by_stamp[q["stamp_o"]]["boundary_utc"]} for q in plan]
    return plan, po, pw


def spot_check(plan: list, shifts: dict, target: dict, audio_dir: str, tl: np.ndarray, origin: float, ids: list) -> dict:
    """SV4: archive_xcorr on shifted windows recovers the intended e. -> max |error| and the per-play errors (numbers only)."""
    errs = []
    for i in ids:
        p = plan[i]
        cur = read_int16(os.path.join(audio_dir, "wsjt-x", "wav", p["stamp_w"] + ".wav"))
        prev = read_int16(os.path.join(audio_dir, "wsjt-x", "wav", stamp_plus(p["stamp_w"], -1) + ".wav"))
        nxt = read_int16(os.path.join(audio_dir, "wsjt-x", "wav", stamp_plus(p["stamp_w"], +1) + ".wav"))
        win, _ = shift_window(prev, cur, nxt, shifts[i])
        ch = X.analyse_window(win.astype(np.float32), I.stamp_to_epoch(p["stamp_w"]), tl, origin)
        es = [c["e_s"] for c in ch if c["e_s"] is not None]
        errs.append(abs(float(np.median(es)) - target[i]) if len(es) >= 5 else float("inf"))
    return {"plays_checked": len(ids), "max_abs_error_s": max(errs), "errors_s": errs, "bar_s": SV4_TOL_S, "result": "PASS" if max(errs) <= SV4_TOL_S else "FAIL"}


def build(sweep_dir: str, audio_dir: str, corpus: str, wavlist: str, runs_dir: str, out_dir: str) -> dict:
    plan, po, pw = load_join(sweep_dir, runs_dir)
    wl = {it["id"]: it for it in json.load(open(wavlist, encoding="utf8"))["items"]}
    cache = {}

    def load(wid):
        if wid not in cache:
            it = wl[wid]
            cache[wid] = X.read_wav(os.path.join(corpus, "wsjt-x", it["run"], it["stamp"] + ".wav"))
        return cache[wid]
    off_o = I.play_offsets(po, "boundary_utc_o", lambda p: os.path.join(audio_dir, "owsfz", "wav", p["stamp"] + ".wav"), load)
    off_w = I.play_offsets(pw, "boundary_utc", lambda p: os.path.join(audio_dir, "wsjt-x", "wav", p["stamp"] + ".wav"), load)
    e_o = {i: v["e_med"] for i, v in off_o.items()}
    e_w = {i: v["e_med"] for i, v in off_w.items()}
    d_s = {i: e_o[i] - e_w[i] for i in e_o}
    shifts = {"Z": {i: 0.0 for i in d_s}, "S": d_s, "K": constant_shifts(plan, d_s)}
    os.makedirs(out_dir, exist_ok=True)
    res = {"plays": len(plan), "arms": {}, "d_s": {"median": float(np.median(list(d_s.values()))), "min": min(d_s.values()), "max": max(d_s.values())}}
    for arm, sh in shifts.items():
        res["arms"][arm] = build_arm(plan, audio_dir, sh, os.path.join(out_dir, arm))
    with open(os.path.join(out_dir, "play_offsets.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump({"e_o": e_o, "e_w": e_w, "d_s": d_s, "plan_stamps": {p["index"]: p["stamp_o"] for p in plan}}, fh)
    # SV4: spot-check windows through archive_xcorr (timeline of the WSJT-X pass, the audio they come from)
    t_lo = min(X.parse_utc(p["boundary_utc"]) for p in pw)
    t_hi = max(X.parse_utc(p["boundary_utc"]) for p in pw)
    origin = t_lo - 30.0
    tl = X.build_timeline([{"wav_id": p["wav_id"], "boundary_utc": p["boundary_utc"]} for p in pw], origin, (t_hi - t_lo) + 90.0, load)
    rng = random.Random(SEED)
    ids = sorted(rng.sample(range(len(plan)), SV4_N))
    res["SV4"] = {"S": spot_check(plan, shifts["S"], e_o, audio_dir, tl, origin, ids),
                  "K": spot_check(plan, shifts["K"], {i: e_w[i] + shifts["K"][i] for i in e_w}, audio_dir, tl, origin, ids), "ids_seed": SEED}
    json.dump(res, open(os.path.join(out_dir, "build.json"), "w"), indent=1)
    return res


# ------------------------------------------------------------------ analysis

def paired_diff(a: tuple, b: tuple, n: int) -> dict:
    return R.boot(lambda i: R.own_cons(*a, i) - R.own_cons(*b, i), n)


def clamp_correlation(plan: list, e_o: dict, daemon_log: str, tz_h: float) -> dict:
    """Spearman rank correlation, per play: clamp lines in the 10 cycles before its pass-O slot against |e_O - median e_O of its WAV|. No verdict."""
    import collapse_check as cc
    from scipy.stats import spearmanr
    clamps = [c["t_sod"] for c in cc.parse(daemon_log, tz_h)["clamps"]]
    by = {}
    for p in plan:
        by.setdefault(p["wav_id"], []).append(e_o[p["index"]])
    med = {w: float(np.median(v)) for w, v in by.items()}
    xs, ys = [], []
    for p in plan:
        t = datetime.strptime(p["stamp_o"], "%y%m%d_%H%M%S")
        sod = t.hour * 3600 + t.minute * 60 + t.second
        n = sum(1 for c in clamps if 0 < (sod - c) % 86400 <= 10 * SLOT_S)
        xs.append(n)
        ys.append(abs(e_o[p["index"]] - med[p["wav_id"]]))
    r = spearmanr(xs, ys)
    return {"plays": len(plan), "plays_with_a_clamp_line": int(sum(1 for x in xs if x > 0)), "rho": float(r.statistic) if np.isfinite(r.statistic) else None,
            "p": float(r.pvalue) if np.isfinite(r.pvalue) else None}


def analyse(sweep_dir: str, audio_dir: str, runs_dir: str, shift_dir: str, daemon_log: str | None, tz_h: float) -> dict:
    plan = json.load(open(os.path.join(runs_dir, "plan.json"), encoding="utf8"))
    wavs = sorted({p["wav_id"] for p in plan})
    n = len(wavs)

    def dec(dirpath, rid):
        f, s = os.path.join(dirpath, rid + ".decodes.tsv"), os.path.join(dirpath, rid + ".json")
        return (R.read_decodes(f), json.load(open(s, encoding="utf8"))) if os.path.isfile(f) and os.path.isfile(s) else (None, None)
    runs = {"R-W": dec(runs_dir, "R-W"), "R-A": dec(runs_dir, "R-A"), **{a: dec(shift_dir, rid) for a, rid in ARMS.items()}}
    arr = {k: R.tally_arrays(R.trials_of(plan, v[0]), wavs) for k, v in runs.items() if v[0] is not None}
    allidx = np.arange(n)
    res = {"plays": len(plan), "wavs": n, "validity": {}, "rows": {}, "descriptive": {}}
    res["measures"] = {k: R.own_cons(*a, allidx) for k, a in arr.items()}
    # --- validity
    res["validity"]["SV1"] = {k: {"sha_equal_start_end": v[1]["native_sha256_start"] == v[1]["native_sha256_end"], "sha": v[1]["native_sha256_start"], "readback": v[1]["readback_start"],
                                   "abandoned": v[1]["residual_pass"]["abandoned"], "items": v[1]["items"], "wall_s": v[1]["wall_s"]} for k, v in runs.items() if v[1]}
    if runs["Z"][0] is not None and runs["R-W"][0] is not None:
        differ = 0
        for p in plan:
            a_, b_ = R.keyed(runs["Z"][0].get(p["index"], []))[0], R.keyed(runs["R-W"][0].get(p["index"], []))[0]
            differ += 0 if a_ == b_ else 1
        res["validity"]["SV2"] = {"W_Z": res["measures"]["Z"], "W": res["measures"]["R-W"], "plays_differing": differ,
                                  "result": "PASS" if differ == 0 and abs(res["measures"]["Z"] - res["measures"]["R-W"]) < 1e-12 else "FAIL"}
    bj = os.path.join(shift_dir, "build.json")
    build_res = json.load(open(bj, encoding="utf8")) if os.path.isfile(bj) else None
    if build_res:
        res["validity"]["SV3"] = {a: {**v, "share": v["zero_filled_plays"] / v["plays"]} for a, v in build_res["arms"].items()}
        res["validity"]["SV3"]["fill_affected"] = any(v["zero_filled_plays"] / v["plays"] > SV3_FILL_SHARE for a, v in build_res["arms"].items() if a != "Z")
        res["validity"]["SV4"] = build_res["SV4"]
    # --- rows
    if all(k in arr for k in ("Z", "S", "K", "R-W", "R-A")):
        s1 = paired_diff(arr["Z"], arr["S"], n)
        s2 = paired_diff(arr["Z"], arr["K"], n)
        s3 = paired_diff(arr["K"], arr["S"], n)
        share = R.boot(lambda i: (R.own_cons(*arr["Z"], i) - R.own_cons(*arr["S"], i)) / (R.own_cons(*arr["R-W"], i) - R.own_cons(*arr["R-A"], i)), n)
        res["rows"]["S1"] = {"W_Z": res["measures"]["Z"], "W_S": res["measures"]["S"], "W_Z_minus_W_S": s1, "fires": R.excludes_zero(s1, +1),
                             "share_of_W_minus_A": share, "A": res["measures"]["R-A"], "W": res["measures"]["R-W"]}
        res["rows"]["S2"] = {"W_K": res["measures"]["K"], "W_Z_minus_W_K": s2, "fires": R.excludes_zero(s2, +1)}
        res["rows"]["S3_QA_addition"] = {"W_K_minus_W_S": s3, "fires": R.excludes_zero(s3, +1)}
        res["descriptive"]["by_batch_W_S"] = {str(b): R.own_cons(*R.tally_arrays(R.trials_of(plan, runs["S"][0], batch=b), wavs), allidx) for b in (1, 2)}
        res["descriptive"]["by_batch_W_Z"] = {str(b): R.own_cons(*R.tally_arrays(R.trials_of(plan, runs["Z"][0], batch=b), wavs), allidx) for b in (1, 2)}
    po = os.path.join(shift_dir, "play_offsets.json")
    if daemon_log and os.path.isfile(po) and os.path.isfile(daemon_log):
        e_o = {int(k): v for k, v in json.load(open(po, encoding="utf8"))["e_o"].items()}
        res["descriptive"]["clamp_lines_vs_abs_e_dev"] = clamp_correlation(plan, e_o, daemon_log, tz_h)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    for a in ("--sweep-dir", "--audio-dir", "--corpus", "--wavlist", "--runs", "--out"):
        pb.add_argument(a, required=True)
    pa = sub.add_parser("analyse")
    for a in ("--sweep-dir", "--audio-dir", "--runs", "--shift", "--out"):
        pa.add_argument(a, required=True)
    pa.add_argument("--daemon-log", default=None)
    pa.add_argument("--tz-h", type=float, default=2.0)
    a = ap.parse_args()
    if a.cmd == "build":
        r = build(a.sweep_dir, a.audio_dir, a.corpus, a.wavlist, a.runs, a.out)
        print("built; zero-filled plays", {k: v["zero_filled_plays"] for k, v in r["arms"].items()}, "SV4 S", r["SV4"]["S"]["result"], r["SV4"]["S"]["max_abs_error_s"], "K", r["SV4"]["K"]["result"], r["SV4"]["K"]["max_abs_error_s"])
    else:
        r = analyse(a.sweep_dir, a.audio_dir, a.runs, a.shift, a.daemon_log, a.tz_h)
        json.dump(r, open(a.out, "w"), indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else (o.tolist() if hasattr(o, "tolist") else str(o)))
        print("analysed; rows:", ",".join(sorted(r["rows"])))


if __name__ == "__main__":
    main()
