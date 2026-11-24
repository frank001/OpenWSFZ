"""CQ-AP analysis (spec arch/cq-ap qa/rr-study/2026-11-10-1546-architect-to-qa-spec-cq-ap-build.md, Amendments 1-3; freeze Part 1 342d320b).

Reads the arms' replay outputs (scratch only: message text lives in nc.tsv under _qa-scratch, HK-037), the PSK Reporter spot file and
WSJT-X's ALL.TXT INSIDE find_extras()/score_extras(); prints and writes counts and rates, never a callsign, never message text.

Every number below is fixed by the spec or the freeze and is ASSERTED in code, not recalled in prose.

  python cqap_analysis.py --selftest                       synthetic Q-prefix data only; touches no real file
  python cqap_analysis.py --run --arms-dir ... (see main)  ONCE, after the freeze's Part 2 is committed

Rows (spec section 4 as amended):
  V-NAT / V-SET   build head, DLL SHA-256 pin, each arm's readback (start and end) shows exactly its parameter set (incl. cqap), same thread count.
  V-OFF           OFF arm's OUTCOME fields (kind, freq, dt, snr, path; never text) == a 98332f2a replay on the first 50 cycles, counting only
                  cycles in which neither run abandoned any stage; fails if more than 5 of the 50 are excluded.
  V-FEED / V-SELF no feed gap > 120 s inside the capture; own spots / {Reported} >= 0.90 (as CQ-AP-PSK).
  G-GAIN          CI_lo(K_C per 100 cycles) > 0.            K_C = corroborated AP-only extras.
  NO-GAIN (A1.1)  CI_hi((K_C + K_N) / D_OFF) < 0.15 %.      K_N = uncorroborated AP-only extras; D_OFF = the OFF arm's decodes.
  U-UB            CI_hi(K_N per cycle) <= 0.021.
  T-TIME          ON latest-batch p95 - OFF's <= 1.0 s AND ON's abandoned cycles per 100 <= OFF's + 1.
  Verdict (exclusive, in order): VOID, NO-GAIN, SHIP-CANDIDATE, FP-UNRESOLVED, BETWEEN.
Bootstrap: B = 2000 resamples of the cycles, seed 20261111, percentile 95 % interval.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "cq-ap-psk"))
import cqapsk_analysis as P      # noqa: E402  (match rule, spot reader, self-log reader; committed and hashed in the freeze's Part 2)

# ---- constants fixed by the spec / freeze (asserted) ---------------------------------------------------------------------------
SEED, B_RESAMPLES = 20261111, 2000
NO_GAIN_BAR = 0.0015            # 0.15 %  (spec section 4, NO-GAIN)
U_BAR = 0.021                   # per cycle (spec section 4, U-UB)
T_P95_BAR_MS = 1000.0           # T-TIME latest-batch p95 difference
T_ABANDON_SLACK_PER_100 = 1.0   # T-TIME abandons per 100 cycles, ON <= OFF + 1
V_OFF_N, V_OFF_MAX_EXCLUDED = 50, 5
V_SELF_MIN = 0.90
N1_FLAG_SHARE = 0.10            # N-1 line flagged if more than 10 % of the AP-only extras
SAME_SIGNAL_HZ = 5              # descriptive only: an extra with an OFF decode this close in the same cycle
PIN_ON = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"
PIN_REF = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
HEAD_ON, HEAD_REF = "7ca00264a5a8d1af7a0f5ab4c8f97f60243572b1", "98332f2a"
SHIM_ON, SHIM_REF = "20260072", "20260071"
N_CYCLES_EXPECTED = 500
assert (SEED, B_RESAMPLES, NO_GAIN_BAR, U_BAR, T_P95_BAR_MS, T_ABANDON_SLACK_PER_100, V_OFF_N, V_OFF_MAX_EXCLUDED, V_SELF_MIN) == \
       (20261111, 2000, 0.0015, 0.021, 1000.0, 1.0, 50, 5, 0.90)
assert (P.MATCH_T_S, P.MATCH_F_HZ, P.FEED_GAP_S, P.OWN_CALL) == (1800, 50, 120, "PD2FZ")
HASHED = "<"


# ---- readers ---------------------------------------------------------------------------------------------------------------------
def norm(t: str) -> str: return " ".join(t.split())


def load_nc(path):
    """nc.tsv -> {stamp: [row]}; row = dict(kind, f, dt, snr, path, text, ap). ap is None on a build without the column."""
    d = collections.defaultdict(list)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 11: continue
            d[p[0]].append(dict(kind=int(p[1]), f=int(p[3]), dt=p[4], snr=int(p[5]), path=p[9], text=norm(p[10]), ap=(int(p[11]) if len(p) > 11 else None)))
    return d


def csv_rows(p):
    with open(p, newline="", encoding="utf-8", errors="replace") as fh: return list(csv.DictReader(fh))


def abandon_cycles(d):
    """Stamps in which ANY stage abandoned (as kr_analyse.timing: fallback, residual pass, third pass abandoned/failed, late round)."""
    s = set()
    for r in csv_rows(f"{d}/coh.csv"):
        if int(r["abandoned"]) > 0: s.add(r["stamp"])
    for r in csv_rows(f"{d}/abandon.csv"):
        if int(r["abandoned"]) > 0: s.add(r["stamp"])
    for r in csv_rows(f"{d}/third.csv"):
        if r["outcome"] in ("abandoned", "failed"): s.add(r["stamp"])
    for r in csv_rows(f"{d}/late.csv"):
        if r["outcome"] == "abandoned": s.add(r["stamp"])
    return s


def latest_batch_ms(d):
    out = []
    for r in csv_rows(f"{d}/run.csv"):
        ts = [float(r[k]) for k in ("tb1_ms", "tb2_ms", "tb3_ms", "tb4_ms", "tb5_ms") if r.get(k) not in (None, "") and float(r[k]) > 0]
        if ts: out.append(max(ts))
    return out


def cq_ap_lines(log_path):
    """(attempts, decodes) per 'cq-ap:' line of a replay log (counts only)."""
    a = dd = n = 0
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.search(r"cq-ap: attempts=(\d+) decodes=(\d+)", line)
            if m: a += int(m[1]); dd += int(m[2]); n += 1
    return dict(lines=n, attempts=a, decodes=dd)


def read_wsjtx(path, stamps):
    """{stamp: set of normalised message texts}, for the arm's stamps only. Text stays in memory (HK-037)."""
    want, out = set(stamps), collections.defaultdict(set)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.split(None, 7)
            if len(p) < 8 or p[2] != "Rx" or p[3] != "FT8" or p[0] not in want: continue
            out[p[0]].add(norm(p[7]))
    return out


# ---- the comparison: ALL text comparisons live in these two functions (HK-037) ----------------------------------------------------
def find_extras(stamps, on, off, wsjt, dial_hz):
    """AP-only extras and the A1.7 / N-1 / same-signal lines. Returns (extras, counts, per-cycle d_off).
    An AP-only extra: an ON decode with apKind = cq (1) whose text is not among the OFF arm's decodes for the same cycle (any batch).
    Hashed-call texts ('<') are excluded and counted. One extra per (cycle, text)."""
    extras, cnt = [], collections.Counter()
    d_off = np.zeros(len(stamps))
    for i, s in enumerate(stamps):
        o_rows, n_rows = off.get(s, []), on.get(s, [])
        d_off[i] = len(o_rows)
        off_txt = {r["text"] for r in o_rows}
        on_txt = {r["text"] for r in n_rows}
        seen = set()
        for r in n_rows:
            if r["ap"] == 1:
                cnt["on_ap_decodes"] += 1
                if HASHED in r["text"]: cnt["ap_hashed_excluded"] += 1; continue
                if r["text"] in off_txt or r["text"] in seen: continue
                seen.add(r["text"])
                near = any(abs(q["f"] - r["f"]) <= SAME_SIGNAL_HZ for q in o_rows)
                cnt["same_signal_in_off"] += near
                extras.append(dict(i=i, stamp=s, text=r["text"], f=r["f"], snr=r["snr"], near=near,
                                   w=(r["text"] in wsjt.get(s, set()))))
        for r in n_rows:                                           # A1.7: gains via the residual (apKind none), and losses
            if r["ap"] == 0 and r["text"] not in off_txt:
                cnt["on_only_ap_none_hashed" if HASHED in r["text"] else "on_only_ap_none"] += 1
        for r in o_rows:
            if r["text"] not in on_txt:
                cnt["off_only_hashed" if HASHED in r["text"] else "off_only"] += 1
    return extras, cnt, d_off


def score_extras(extras, index, epochs, dial_hz):
    """Corroborated by WSJT-X (same text, same cycle) or by the feed (sender, +-1800 s, +-50 Hz, other receiver). Returns aggregates only."""
    n = len(epochs)
    kc, kn = np.zeros(n), np.zeros(n)
    byb = {b[0]: [0, 0] for b in P.BINS}             # [corroborated, uncorroborated] by OUR snr
    share = collections.Counter()
    n1 = 0
    for e in extras:
        sender, why = P.cq_sender(e["text"])
        if why == "not-cq": n1 += 1                    # N-1: tagged cq, text does not begin with CQ
        feed_ok = bool(sender) and P.corroborated(index, sender, epochs[e["i"]], dial_hz + e["f"])
        ok = e["w"] or feed_ok
        b = P.bin_of(e["snr"])
        if ok: kc[e["i"]] += 1; byb[b][0] += 1
        else: kn[e["i"]] += 1; byb[b][1] += 1
        share["wsjtx_only" if (e["w"] and not feed_ok) else "feed_only" if (feed_ok and not e["w"]) else "both" if ok else "neither"] += 1
    return kc, kn, byb, dict(share), n1


# ---- statistics ------------------------------------------------------------------------------------------------------------------
def ci(a): return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def bootstrap(kc, kn, d_off):
    n = len(kc)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(B_RESAMPLES, n))
    den = d_off[idx].sum(axis=1)
    return dict(K_C_per100=ci(100.0 * kc[idx].sum(axis=1) / n), K_N_per_cycle=ci(kn[idx].sum(axis=1) / n),
                gain_ratio_all=ci((kc[idx].sum(axis=1) + kn[idx].sum(axis=1)) / den))


# ---- rows as pure functions (each tested by the self-test) -----------------------------------------------------------------------
def outcome_key(rows): return sorted((r["kind"], r["f"], r["dt"], r["snr"], r["path"]) for r in rows)


def v_off(stamps, off, ref, off_ab, ref_ab):
    first = stamps[:V_OFF_N]
    excl = [s for s in first if s in off_ab or s in ref_ab]
    diff = [s for s in first if s not in excl and outcome_key(off.get(s, [])) != outcome_key(ref.get(s, []))]
    return dict(cycles=len(first), excluded=len(excl), compared=len(first) - len(excl), differing=len(diff),
                PASS=(len(excl) <= V_OFF_MAX_EXCLUDED and not diff))


def v_nat(head, dll_sha, status_txt, want_head, want_sha):
    return dict(head=head[:8], dll=dll_sha[:8], PASS=(head.startswith(want_head) and dll_sha == want_sha and "mismatch" not in status_txt))


def v_set(readbacks, want_extra, shim):
    """readbacks: {'start': line, 'end': line}. Every needed token must be in both."""
    need = ["decodingDepth=Deep", "nhard=24", "kMinScorePass2=5 ", "osdCorrThreshold=0.05", "osdSignFixRead=1", f"shim={shim}", "cohfb=True",
            "cohms=True", "cohaudio=Both", "ungated=True", "lateround=True", "subtractionEnabled=True"] + want_extra
    miss = {k: [n for n in need if n not in v] for k, v in readbacks.items()}
    return dict(missing=miss, PASS=all(not m for m in miss.values()) and len(readbacks) == 2)


def thread_count(line):
    m = re.search(r"threadsResolved=(\d+)", line)
    return int(m[1]) if m else None


def verdict(r):
    """Exclusive, in this order (spec section 4)."""
    if not (r["V-NAT"] and r["V-SET"] and r["V-OFF"] and r["V-FEED"]): return "VOID"
    if r["NO-GAIN"]: return "NO-GAIN"
    if r["G-GAIN"] and r["U-UB"] and r["T-TIME"] and r["V-SELF"]: return "SHIP-CANDIDATE"
    if r["G-GAIN"] and not r["U-UB"]: return "FP-UNRESOLVED"
    return "BETWEEN"


def g_gain(ci_lo_kc_per100): return ci_lo_kc_per100 > 0
def no_gain(ci_hi_ratio): return ci_hi_ratio < NO_GAIN_BAR
def u_ub(ci_hi_kn_per_cycle): return ci_hi_kn_per_cycle <= U_BAR


def t_time(on_ms, off_ms, on_ab, off_ab, n):
    p = lambda v: float(np.percentile(v, 95)) if v else float("nan")
    dp95 = p(on_ms) - p(off_ms)
    on100, off100 = 100.0 * len(on_ab) / n, 100.0 * len(off_ab) / n
    return dict(on_p95_ms=p(on_ms), off_p95_ms=p(off_ms), dp95_ms=dp95, on_abandon_cycles_per100=on100, off_abandon_cycles_per100=off100,
                PASS=bool(dp95 <= T_P95_BAR_MS and on100 <= off100 + T_ABANDON_SLACK_PER_100))


# ---- the run ---------------------------------------------------------------------------------------------------------------------
def readback_lines(log):
    out = {}
    with open(log, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for tag in ("start", "end"):
                if line.startswith(f"# readback {tag}") and tag not in out: out[tag] = line
    return out


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""): h.update(ch)
    return h.hexdigest()


def git_head(tree): return subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def analyse(a):
    """a: dict of paths and constants. Returns the result dict (aggregates only)."""
    stamps = [x.strip().replace(".wav", "") for x in open(a["cycle_list"], encoding="utf-8") if x.strip() and not x.startswith("#")]
    assert len(stamps) == a.get("expect_cycles", N_CYCLES_EXPECTED), f"cycle list has {len(stamps)} cycles"
    epochs = [P.epoch(s) for s in stamps]
    arms = {k: a["arms"][k] for k in ("OFF", "ON", "OFF2", "REF")}
    nc = {k: load_nc(f"{v}/nc.tsv") for k, v in arms.items()}
    ab = {k: abandon_cycles(v) for k, v in arms.items()}
    res = dict(cycles=len(stamps), first=stamps[0], last=stamps[-1], seed=SEED, B=B_RESAMPLES)
    # V-NAT / V-SET (build identity from the files, readbacks from the logs)
    nat_on = v_nat(a["head_on"], a["dll_sha_on"], a["status_txt_on"], HEAD_ON, PIN_ON)
    nat_ref = v_nat(a["head_ref"], a["dll_sha_ref"], a["status_txt_ref"], HEAD_REF, PIN_REF)
    rb = {k: readback_lines(f"{arms[k]}/log.log") for k in arms}
    sets = {"OFF": v_set(rb["OFF"], ["cqap=False"], SHIM_ON), "ON": v_set(rb["ON"], ["cqap=True"], SHIM_ON), "OFF2": v_set(rb["OFF2"], ["cqap=False"], SHIM_ON),
            "REF": v_set(rb["REF"], [], SHIM_REF)}
    sets["REF"]["no_cqap_token"] = all("cqap" not in v for v in rb["REF"].values())
    sets["REF"]["PASS"] = sets["REF"]["PASS"] and sets["REF"]["no_cqap_token"]
    thr = {k: {t: thread_count(v) for t, v in rb[k].items()} for k in ("OFF", "ON", "OFF2", "REF")}
    same_threads = len({x for k in thr for x in thr[k].values()}) == 1 and None not in {x for k in thr for x in thr[k].values()}
    res["V-NAT"] = dict(on=nat_on, ref=nat_ref, PASS=nat_on["PASS"] and nat_ref["PASS"])
    res["V-SET"] = dict(arms=sets, threads=thr, same_threads=same_threads, PASS=all(v["PASS"] for v in sets.values()) and same_threads)
    # V-OFF
    res["V-OFF"] = v_off(stamps, nc["OFF"], nc["REF"], ab["OFF"], ab["REF"])
    # the feed, the WSJT-X reference
    wsjt = read_wsjtx(a["wsjtx_all_txt"], stamps)
    extras, cnt, d_off = find_extras(stamps, nc["ON"], nc["OFF"], wsjt, a["dial_hz"])
    targets = {P.cq_sender(e["text"])[0] for e in extras} - {None}
    index, feed = P.read_spots(a["spots"], targets, a["cap_start"], a["cap_end"])
    gaps = [g for g in feed["gaps"] if g[1] >= a["cap_start"] and g[0] <= a["cap_end"]]
    res["V-FEED"] = dict(rows=feed["rows"], gaps_over_120s=len(gaps), no_t_tx=feed["no_t_tx"], PASS=(len(gaps) == 0))
    tot, wins = P.self_log_reported(a["daemon_log"], a["cap_start"], a["cap_end"])
    ratio = feed["own"] / tot if tot else None
    res["V-SELF"] = dict(own_spots=feed["own"], reported=tot, windows=wins, ratio=ratio, PASS=(ratio is not None and ratio >= V_SELF_MIN))
    # the extras
    kc, kn, byb, share, n1 = score_extras(extras, index, epochs, a["dial_hz"])
    bs = bootstrap(kc, kn, d_off)
    n = len(stamps)
    res["counts"] = dict(D_OFF=int(d_off.sum()), D_ON=int(sum(len(v) for s, v in nc["ON"].items() if s in set(stamps))), AP_only_extras=len(extras),
                         K_C=int(kc.sum()), K_N=int(kn.sum()), ap_decodes_on=cnt["on_ap_decodes"], ap_hashed_excluded=cnt["ap_hashed_excluded"])
    res["point"] = dict(K_C_per100=100.0 * kc.sum() / n, K_N_per_cycle=kn.sum() / n, K_C_over_D_OFF_pct=100.0 * kc.sum() / d_off.sum(),
                        K_C_plus_K_N_over_D_OFF_pct=100.0 * (kc.sum() + kn.sum()) / d_off.sum())
    res["CI"] = bs
    rows = dict(
        **{"V-NAT": res["V-NAT"]["PASS"], "V-SET": res["V-SET"]["PASS"], "V-OFF": res["V-OFF"]["PASS"], "V-FEED": res["V-FEED"]["PASS"], "V-SELF": res["V-SELF"]["PASS"]},
        **{"G-GAIN": g_gain(bs["K_C_per100"][0]), "NO-GAIN": no_gain(bs["gain_ratio_all"][1]), "U-UB": u_ub(bs["K_N_per_cycle"][1])})
    tt = t_time(latest_batch_ms(arms["ON"]), latest_batch_ms(arms["OFF"]), ab["ON"], ab["OFF"], n)
    rows["T-TIME"] = tt["PASS"]
    res["T-TIME"] = tt
    res["rows"] = rows
    res["VERDICT"] = verdict(rows)
    # descriptive (no gate)
    res["descriptive"] = dict(
        by_our_snr_bin={b: dict(K_C=v[0], K_N=v[1]) for b, v in byb.items()},
        corroboration_share=share,
        AP_only_extras_per100=100.0 * len(extras) / n,
        cq_ap_lines_on=cq_ap_lines(f"{arms['ON']}/log.log"), cq_ap_lines_off=cq_ap_lines(f"{arms['OFF']}/log.log"),
        A17_on_only_ap_none_per100=100.0 * cnt["on_only_ap_none"] / n, A17_off_only_per100=100.0 * cnt["off_only"] / n,
        A17_hashed_excluded=dict(on_only=cnt["on_only_ap_none_hashed"], off_only=cnt["off_only_hashed"]),
        N1_cq_tagged_not_starting_with_CQ=dict(n=n1, share_of_extras=(n1 / len(extras) if extras else None),
                                              FLAG=bool(extras) and n1 / len(extras) > N1_FLAG_SHARE),
        same_signal_in_off_within_5Hz=cnt["same_signal_in_off"],
        abandon_cycles=dict(OFF=len(ab["OFF"]), ON=len(ab["ON"]), OFF2=len(ab["OFF2"]), REF=len(ab["REF"])),
    )
    # OFF-vs-OFF repeat line (run-to-run variation on the same cycles; cycles with an abandon in either run excluded and counted)
    rep = [s for s in stamps if s not in ab["OFF"] and s not in ab["OFF2"]]
    diff = [s for s in rep if outcome_key(nc["OFF"].get(s, [])) != outcome_key(nc["OFF2"].get(s, []))]
    res["OFF_vs_OFF_repeat"] = dict(cycles=len(stamps), excluded_abandon=len(stamps) - len(rep), compared=len(rep), differing_cycles=len(diff),
                                    D_OFF=int(d_off.sum()), D_OFF2=int(sum(len(nc["OFF2"].get(s, [])) for s in stamps)))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--arms-dir", help="folder holding OFF, ON, OFF2, REF (each with run.csv coh.csv abandon.csv third.csv late.csv log.log nc.tsv status.txt)")
    ap.add_argument("--tree-on"); ap.add_argument("--tree-ref"); ap.add_argument("--bin-on"); ap.add_argument("--bin-ref")
    ap.add_argument("--cycle-list"); ap.add_argument("--spots"); ap.add_argument("--wsjtx-all-txt"); ap.add_argument("--daemon-log")
    ap.add_argument("--cap-start"); ap.add_argument("--cap-end"); ap.add_argument("--dial-hz", type=int, default=7074000)
    ap.add_argument("--out")
    x = ap.parse_args()
    if x.selftest:
        import cqap_selftest; return cqap_selftest.main()
    assert x.run and x.arms_dir
    arms = {k: f"{x.arms_dir}/{k}" for k in ("OFF", "ON", "OFF2", "REF")}
    a = dict(arms=arms, cycle_list=x.cycle_list, spots=x.spots, wsjtx_all_txt=x.wsjtx_all_txt, daemon_log=x.daemon_log, dial_hz=x.dial_hz,
             cap_start=P.epoch(x.cap_start), cap_end=P.epoch(x.cap_end),
             head_on=git_head(x.tree_on), head_ref=git_head(x.tree_ref),
             dll_sha_on=sha256(f"{x.bin_on}/libft8.dll"), dll_sha_ref=sha256(f"{x.bin_ref}/libft8.dll"),
             status_txt_on="".join(open(f"{arms[k]}/status.txt", encoding="utf-8").read() for k in ("OFF", "ON", "OFF2")),
             status_txt_ref=open(f"{arms['REF']}/status.txt", encoding="utf-8").read())
    res = analyse(a)
    s = json.dumps(res, indent=1, default=float)
    open(x.out, "w", encoding="utf-8").write(s)
    print(s)


if __name__ == "__main__":
    main()
