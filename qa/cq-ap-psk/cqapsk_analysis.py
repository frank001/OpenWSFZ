"""CQ-AP-PSK analysis (spec qa/rr-study/2026-11-10-1153-architect-to-qa-spec-cq-ap-psk-check.md + Amendments 1-2).

One script, aggregates only. Reads OpenWSFZ's ALL.TXT and the PSK Reporter spot file INSIDE run(); prints and writes counts and
rates per bin, never a callsign, never message text (NFR-021, HK-037). Real calls exist only in memory.

Run order is fixed by the freeze record: this file is committed, then `python cqapsk_analysis.py --run ...` is run ONCE.
`--selftest` runs on synthetic Q-prefix data and touches no real file.
"""
from __future__ import annotations
import argparse, bisect, collections, datetime, json, math, re, subprocess, sys
import numpy as np
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c28_ghosts as G

# ---- constants fixed by the spec and the freeze (assertions below) -------------------------------------------------------
SEED = 20261110
N_GHOSTS = 10_000
CAND_BLOCK = 400_000            # candidate (n28, donor) pairs drawn once, consumed in order until N_GHOSTS are accepted
TRIM_S = 1800                   # window loses 1800 s at each end of the capture
MATCH_T_S = 1800                # |t_tx - cycle start|
MATCH_F_HZ = 50                 # |spot f - absolute f|
PR_T_S = 600                    # P_R: other cycles within +-600 s ...
PR_F_HZ = 10                    # ... each within +-10 Hz of the decode's audio offset
PR_MIN_OTHER = 2                # ... at least two
SHUFFLE_T_S = 7200              # P_S: partner at least 2 h away ...
SHUFFLE_F_HZ = 200              # ... and 200 Hz away
FEED_GAP_S = 120
OWN_CALL = "PD2FZ"
BINS = [("ge-10", -10, 99), ("-11..-15", -15, -11), ("-16..-18", -18, -16), ("le-19", -99, -19)]
WEAK, NEXT = "le-19", "-16..-18"
G_COVER, G_SLOPE, G_GHOST, GHOST_SHARE_MAX, V_SELF_MIN, N_MIN = 0.40, 0.20, 0.02, 0.05, 0.90, 30
Z95 = 1.96
LOCAL_UTC_OFFSET_S = 3600       # daemon log prefix is local (CET); verified against the "Cycle HH:MM:SS" UTC stamps below
assert (SEED, N_GHOSTS, TRIM_S, MATCH_T_S, MATCH_F_HZ, PR_T_S, PR_F_HZ, PR_MIN_OTHER) == (20261110, 10000, 1800, 1800, 50, 600, 10, 2)
assert (G_COVER, G_SLOPE, G_GHOST, V_SELF_MIN, N_MIN, GHOST_SHARE_MAX) == (0.40, 0.20, 0.02, 0.90, 30, 0.05)
assert G.N_STD == 262177560

MODIFIER = re.compile(r"^(?:[A-Z]{1,4}|\d{3})$")
GRID4 = re.compile(r"^[A-R]{2}\d\d$")


def epoch(ts: str) -> int:               # 'YYMMDD_HHMMSS' (UTC) -> epoch seconds
    d = datetime.datetime.strptime(ts, "%y%m%d_%H%M%S").replace(tzinfo=datetime.timezone.utc)
    return int(d.timestamp())


def bin_of(snr: int) -> str:
    for name, lo, hi in BINS:
        if lo <= snr <= hi: return name
    raise ValueError(snr)


def wilson(k: int, n: int, z: float = Z95):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / den, (c + r) / den)


def cq_sender(msg: str):
    """(sender, reason): sender None when excluded; reason in {'ok','not-cq','hashed','no-sender'}."""
    t = msg.split()
    if not t or t[0] != "CQ": return None, "not-cq"
    i = 1
    if len(t) >= 3 and MODIFIER.match(t[1]): i = 2
    if i >= len(t): return None, "no-sender"
    s = t[i]
    if "<" in s: return None, "hashed"
    return s, "ok"


def donor_grid(msg: str):
    last = msg.split()[-1]
    return last if GRID4.match(last) else None


def read_decodes(path, t0, t1):
    """CQ decodes (one per cycle and sender) with cycle epoch in [t0, t1]. Returns (list, counts)."""
    seen, out = set(), []
    cnt = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.split(None, 7)
            if len(p) < 8 or p[2] != "Rx" or p[3] != "FT8": continue
            try: c = epoch(p[0])
            except ValueError: continue
            if not (t0 <= c <= t1): continue
            cnt["decodes"] += 1
            s, why = cq_sender(p[7].strip())
            if why == "not-cq": continue
            cnt["cq_" + why] += 1
            if s is None: continue
            if (c, s) in seen: cnt["cq_dup"] += 1; continue
            seen.add((c, s))
            out.append(dict(c=c, s=s, snr=int(p[4]), off=int(p[6]), dial=float(p[1]), grid=donor_grid(p[7].strip())))
    return out, cnt


def build_pr(dec):
    by = collections.defaultdict(list)
    for d in dec: by[d["s"]].append(d)
    pr = []
    for s, L in by.items():
        for d in L:
            n = sum(1 for e in L if e is not d and e["c"] != d["c"] and abs(e["c"] - d["c"]) <= PR_T_S and abs(e["off"] - d["off"]) <= PR_F_HZ)
            if n >= PR_MIN_OTHER: pr.append(d)
    return pr


def absf(d): return int(round(d["dial"] * 1e6)) + d["off"]


def read_spots(path, targets, cap_t0, cap_t1):
    """Streams the spot file once. Returns (index, feed, self_spots). index[sc] -> sorted list of (t, f, band_ok)."""
    index = collections.defaultdict(list)
    feed = dict(rows=0, no_t_tx=0, gaps=[], first=None, last=None, own=0, not_ft8=0)
    prev = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "p" not in r: continue
            rx = r["rx"]
            if prev is not None and rx - prev > FEED_GAP_S: feed["gaps"].append((prev, rx))
            prev = rx
            feed["rows"] += 1
            if feed["first"] is None: feed["first"] = rx
            feed["last"] = rx
            p = json.loads(r["p"])
            if OWN_CALL in p.get("rc", ""): feed["own"] += 1
            if p.get("md") != "FT8": feed["not_ft8"] += 1; continue
            sc = p.get("sc")
            if sc not in targets or OWN_CALL in p.get("rc", ""): continue
            t = p.get("t_tx")
            if t is None: t = p.get("t"); feed["no_t_tx"] += 1
            index[sc].append((t, p["f"]))
    for v in index.values(): v.sort()
    return index, feed


def corroborated(index, sender, t, f):
    L = index.get(sender)
    if not L: return False
    i = bisect.bisect_left(L, (t - MATCH_T_S, -1))
    while i < len(L) and L[i][0] <= t + MATCH_T_S:
        if abs(L[i][1] - f) <= MATCH_F_HZ: return True
        i += 1
    return False


def matched_dts(index, sender, t, f):
    L = index.get(sender, [])
    return [x[0] - t for x in L if abs(x[0] - t) <= MATCH_T_S and abs(x[1] - f) <= MATCH_F_HZ]


def gate_messages(msgs, gate_cmd):
    p = subprocess.run(gate_cmd, input="\n".join(msgs) + "\n", capture_output=True, text=True, encoding="utf-8", check=True)
    out = p.stdout.split()
    assert len(out) == len(msgs), (len(out), len(msgs))
    return [o == "1" for o in out]


def make_ghosts(rng, donors, gate_cmd):
    """Draws CAND_BLOCK (n28, donor index) pairs ONCE, in order; keeps the first N_GHOSTS that unpack to a space-free trimmed call
    and pass the product's IsPlausibleMessage('CQ <ghost> [<donor grid>]', live grammar). Returns (ghosts, stats)."""
    n28 = G.draw_n28(rng, CAND_BLOCK)
    di = rng.integers(0, len(donors), size=CAND_BLOCK)
    cand, meta = [], []
    unpackable = 0
    for n, k in zip(n28, di):
        call = G.unpack_std(int(n)).strip()
        if not call or " " in call: continue
        unpackable += 1
        g = donors[int(k)]["grid"]
        cand.append(f"CQ {call} {g}" if g else f"CQ {call}")
        meta.append((call, int(k)))
    ok = gate_messages(cand, gate_cmd)
    kept = []
    tried = 0
    for (call, k), good in zip(meta, ok):
        tried += 1
        if good:
            kept.append((call, k))
            if len(kept) == N_GHOSTS: break
    assert len(kept) == N_GHOSTS, f"only {len(kept)} ghosts accepted of {CAND_BLOCK} candidates"
    return kept, dict(candidates=CAND_BLOCK, unpackable=unpackable, gated=tried, accepted=N_GHOSTS,
                      rejected_unpackable=CAND_BLOCK - unpackable, rejected_by_plausibility=tried - N_GHOSTS,
                      rejected_share_total=1 - N_GHOSTS / CAND_BLOCK)


def shuffle_pairs(rng, pr):
    ts = np.array([d["c"] for d in pr]); fs = np.array([absf(d) for d in pr])
    pairs, dropped = [], 0
    for i, d in enumerate(pr):
        ok = np.nonzero((np.abs(ts - d["c"]) >= SHUFFLE_T_S) & (np.abs(fs - absf(d)) >= SHUFFLE_F_HZ))[0]
        if len(ok) == 0: dropped += 1; continue
        j = int(ok[int(rng.integers(0, len(ok)))])
        pairs.append((d["s"], pr[j]["c"], absf(pr[j])))
    return pairs, dropped


def verdict(rows):
    """Exclusive, in order (spec §3 + A1.4). V-REF failure does NOT void: P_R gates and the label says so."""
    lab = "" if rows["V-REF"] else " (P_R)"
    if rows["N-INSUFF"]: return "INSUFFICIENT" + lab
    if rows["C_weak_hi"] < G_COVER or rows["ghost_point"] > GHOST_SHARE_MAX: return "NOT-USABLE" + lab
    if rows["G-COVER"] and rows["G-SLOPE"] and rows["G-GHOST"] and rows["V-SELF"]: return "USABLE" + lab
    return "BETWEEN" + lab


def self_log_reported(logpath, cap_t0, cap_t1):
    """Sum of {Reported} over 'PSK Reporter: N decodes seen, M reported' lines whose send fell in the capture (log stamps are local)."""
    tot = windows = 0
    off_checks = set()
    day = None
    with open(logpath, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"\[(\d\d):(\d\d):(\d\d) \w+\] Cycle (\d\d):(\d\d):(\d\d): \d+ decode", line)
            if m:
                loc = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]); utc = int(m[4]) * 3600 + int(m[5]) * 60 + int(m[6])
                off_checks.add((loc - utc) % 86400)
            m = re.match(r"\[(\d\d):(\d\d):(\d\d) \w+\] PSK Reporter: \d+ decodes seen, (\d+) reported", line)
            if m:
                loc = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
                tot_s = (loc - LOCAL_UTC_OFFSET_S) % 86400
                # capture times are epoch; compare time of day on the capture's UTC date
                d0 = datetime.datetime.fromtimestamp(cap_t0, datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                t = d0 + tot_s
                if cap_t0 <= t <= cap_t1: tot += int(m[4]); windows += 1
    assert off_checks and all(abs(x - LOCAL_UTC_OFFSET_S) <= 120 for x in off_checks), f"log offset not {LOCAL_UTC_OFFSET_S}s: {sorted(off_checks)[:5]}"
    return tot, windows


def run(a):
    """Returns the in-window P_R BEFORE the feed-gap exclusion (ghost donors index into this list) and everything summarise() needs."""
    dec, dcnt = read_decodes(a.all_txt, a.daemon_start, a.cap_end)
    pr_all = build_pr(dec)
    win0, win1 = a.cap_start + TRIM_S, a.cap_end - TRIM_S
    pr_pre = [d for d in pr_all if win0 <= d["c"] <= win1]
    rng = np.random.Generator(np.random.PCG64(SEED))
    ghosts, gstats = make_ghosts(rng, pr_pre, a.gate_cmd)
    shuf, shuf_dropped = shuffle_pairs(rng, pr_pre)
    targets = {d["s"] for d in pr_pre} | {g[0] for g in ghosts}
    index, feed = read_spots(a.spots, targets, a.cap_start, a.cap_end)
    gaps = [(g0 - TRIM_S, g1 + TRIM_S) for g0, g1 in feed["gaps"]]
    return pr_pre, ghosts, shuf, shuf_dropped, index, feed, gstats, dcnt, pr_all, win0, win1, gaps


def summarise(pr_pre, ghosts, shuf, shuf_dropped, index, feed, gstats, dcnt, pr_all, win0, win1, gaps, selfsum):
    in_gap = lambda c: any(g0 <= c <= g1 for g0, g1 in gaps)
    pr = [d for d in pr_pre if not in_gap(d["c"])]
    res = {}
    # P_R by bin
    byb = {b[0]: [0, 0] for b in BINS}
    dts = []
    cb = {b[0]: [0, 0] for b in BINS}       # call + band only, time-limited (descriptive)
    for d in pr:
        b = bin_of(d["snr"]); byb[b][1] += 1
        ok = corroborated(index, d["s"], d["c"], absf(d))
        byb[b][0] += ok
        if ok: dts += matched_dts(index, d["s"], d["c"], absf(d))
        L = index.get(d["s"], [])
        if any(abs(x[0] - d["c"]) <= MATCH_T_S for x in L): cb[b][0] += 1
        cb[b][1] += 1
    res["P_R_by_bin"] = {b: dict(k=v[0], n=v[1], C=(v[0] / v[1] if v[1] else None), wilson=wilson(*v)) for b, v in byb.items()}
    res["P_R_call_band_only_by_bin"] = {b: dict(k=v[0], n=v[1], C=(v[0] / v[1] if v[1] else None)) for b, v in cb.items()}
    # ghosts (donor = a P_R decode in the pre-gap list; excluded if the donor sits in a gap)
    gk = gn = 0
    for call, k in ghosts:
        d = pr_pre[k]
        if in_gap(d["c"]): continue
        gn += 1; gk += corroborated(index, call, d["c"], absf(d))
    res["P_G"] = dict(k=gk, n=gn, point=(gk / gn if gn else None), wilson=wilson(gk, gn))
    sk = sn = 0
    for s, c, f in shuf:
        sn += 1; sk += corroborated(index, s, c, f)
    res["P_S"] = dict(k=sk, n=sn, share=(sk / sn if sn else None), dropped=shuf_dropped)
    if dts:
        a = np.array(dts); res["D_T_s"] = dict(median=float(np.median(a)), p05=float(np.percentile(a, 5)), p95=float(np.percentile(a, 95)), n=len(a))
    # rows
    w = byb[WEAK]; nx = byb[NEXT]
    lo, hi = wilson(*w)
    c_weak = w[0] / w[1] if w[1] else float("nan")
    c_next = nx[0] / nx[1] if nx[1] else float("nan")
    slope = (c_next - c_weak) if (nx[1] and w[1]) else None
    rows = {
        "V-REF": a_vref(), "N-INSUFF": w[1] < N_MIN,
        "C_weak_lo": lo, "C_weak_hi": hi, "C_weak": c_weak,
        "G-COVER": (lo >= G_COVER) if w[1] else False,
        "G-SLOPE": (slope is not None and slope <= G_SLOPE),
        "slope": slope, "slope_defined": slope is not None,
        "ghost_point": (gk / gn if gn else float("nan")), "ghost_hi": wilson(gk, gn)[1],
        "V-SELF": (selfsum["ratio"] is not None and selfsum["ratio"] >= V_SELF_MIN), "V-SELF_ratio": selfsum["ratio"],
    }
    rows["G-GHOST"] = bool(gn) and rows["ghost_hi"] <= G_GHOST
    rows["VERDICT"] = verdict(rows)
    res["rows"] = rows
    res["feed"] = dict(rows=feed["rows"], gaps_over_120s=len(feed["gaps"]), no_t_tx=feed["no_t_tx"], not_ft8=feed["not_ft8"], own_spots=feed["own"])
    res["ghost_stats"] = gstats
    res["decodes"] = dict(dcnt)
    res["P_R_total_all_time"] = len(pr_all)
    res["P_R_in_window"] = len(pr)
    res["window_utc"] = [datetime.datetime.fromtimestamp(x, datetime.timezone.utc).isoformat() for x in (win0, win1)]
    return res


_VREF = {"v": False}
def a_vref(): return _VREF["v"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--all-txt"); ap.add_argument("--spots"); ap.add_argument("--daemon-log")
    ap.add_argument("--wsjtx-all-txt", default=r"C:\Users\frans\AppData\Local\WSJT-X\ALL.TXT")
    ap.add_argument("--cap-start"); ap.add_argument("--cap-end"); ap.add_argument("--daemon-start")
    ap.add_argument("--gate-dll"); ap.add_argument("--pub-dir"); ap.add_argument("--grammar")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.selftest:
        import cqapsk_selftest; return cqapsk_selftest.main()
    a.cap_start = epoch(a.cap_start); a.cap_end = epoch(a.cap_end); a.daemon_start = epoch(a.daemon_start)
    a.gate_cmd = ["dotnet", a.gate_dll, a.pub_dir, a.grammar]
    _VREF["v"] = os.path.exists(a.wsjtx_all_txt)     # V-REF (mechanical existence check; its overlap test is not needed when absent)
    pr_pre, ghosts, shuf, sd, index, feed, gstats, dcnt, pr_all, w0, w1, gaps = run(a)
    tot, wins = self_log_reported(a.daemon_log, a.cap_start, a.cap_end)
    selfsum = dict(spots_with_own_rc=feed["own"], reported=tot, windows=wins, ratio=(feed["own"] / tot if tot else None))
    res = summarise(pr_pre, ghosts, shuf, sd, index, feed, gstats, dcnt, pr_all, w0, w1, gaps, selfsum)
    res["V-SELF_detail"] = selfsum
    res["V-REF_wsjtx_all_txt_present"] = _VREF["v"]
    s = json.dumps(res, indent=1, default=str)
    open(a.out, "w", encoding="utf-8").write(s)
    print(s)


if __name__ == "__main__":
    main()
