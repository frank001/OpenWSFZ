#!/usr/bin/env python3
"""XS-PRIOR (programme angle G, Stage 0) counter.  Spec: arch/exchange-step-prior 7a8a4494, qa/rr-study/2026-11-16-1815-architect-to-qa-spec-xs-prior.md.  QA tooling: no src/ or native/ change, no replay.
HK-037: message text is read INSIDE the functions below and never leaves them; only counts reach the JSON / stdout.  Working files (if any) go to D:/Projects/claude/_qa-scratch/xs-prior and are KEPT.

Usage:  python -I xs_count.py selftest
        python -I xs_count.py kcheck     the (k) items ONLY: V-N, the 15 s grid, the report range, V-PARSE, the exclusion counts, the loose pair-condition count with its CI half-width.  NO S1 / S2 / verdict.
        python -I xs_count.py count      S1, S2, C-PAR, the split, the descriptives and the decision.  Run ONCE per frozen code.

FROZEN (as code; section numbers are the spec's):
  Messages are F1 F2 F3 (F1 addressee, F2 sender, F3 payload).  Payload types, checked in this order: RR73, RRR, 73, rreport (R+nn / R-nn), report (+nn / -nn), grid (4 or 6 characters), empty (2 tokens).
  Step table N(P) for the REPLY: grid|empty -> reports -30..+31 (62, widened from the spec's -30..+20 by the (k) report-range check); report -> rreports -30..+31 (62); rreport -> {RR73, RRR, 73} (3); RR73|RRR -> {73} (1); 73 -> {} (0).
  N2(P) = the table applied twice: grid|empty -> rreports (62); report -> {RR73, RRR, 73} (3); rreport -> {73} (1); RR73|RRR|73 -> {} (0).
  U = WSJT-X-only rows (matched = same cycle + normalised text, multiset-paired as anova_common.match_pairs) minus, in this order: (1) a '<' field or ';'; (2) CQ / QRZ / DE; (3) not parsed by the table; (4) XC territory: the same text matched at t-30, -60 or -90 s within 10 Hz.
  S1 (first match wins): u = 'X Y Pu' at t, a MATCHED row 'Y X Pp' at t-15 s, Pu in N(Pp).   S2: a MATCHED row 'X Y Pp' at t-30 s within 10 Hz, text differs, Pu in N2(Pp).   S-LOOSE: the pair condition of S1 or S2 holds, the payload is not in the set.
  C-PAR (control): as S1 with p at t-30 s.   K-low: the applicable set has <= 3 members; K-high: 51.
  Rows: V-N (WSJT-X-only 10,110 and matched 75,673); V-PARSE (>= 90 % of U parsed before exclusion 3); V-PAR (C-PAR <= 0.25 x S1, else VOID); S = (S1 + S2) / n_ref in pp, cycle bootstrap B = 2000 seed 20261116.
  Decision (the first matching row wins): 1 CLOSE iff CI_hi(S) < 1.0 pp | 2 VOID iff V-PAR fails | 3 PURSUE iff CI_lo(S) >= 1.0 pp | 4 BETWEEN."""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "endurance"))
import anova_common as AC  # noqa: E402

NIGHT = "D:/Projects/claude/OpenWSFZ/artefacts/20261114_2312_endurance_run-gathered"
OUT = "D:/Projects/claude/_qa-scratch/xs-prior"
CYCLE_S = 15
WINDOW_HZ = 10.0                  # cf_fbid.WS_CONF_DF (qa/rr-study/coh-fallback/cf_fbid.py:39), the corroboration window
REP_LO, REP_HI = -30, 31          # the spec said -30..+20; the (k) check found 50 of 18,095 matched report rows above +20 (+21..+31), so the range is widened to the OBSERVED maximum +31 (spec section 2: "widens it")
N_REP = REP_HI - REP_LO + 1       # 62 templates for a report-valued set (the spec's 51 was the +20 range)
K_LOW_MAX = 3
BAR_PP = 1.0
PAR_RATIO = 0.25
PARSE_MIN = 0.90
SEED, B_BOOT = 20261116, 2000
N_REF_EXPECT, N_OWS_EXPECT, N_MATCHED_EXPECT, N_UNREACHED_EXPECT = 85783, 79317, 75673, 10110
assert (CYCLE_S, WINDOW_HZ, REP_LO, REP_HI, K_LOW_MAX, BAR_PP, PAR_RATIO, PARSE_MIN, SEED, B_BOOT) == (15, 10.0, -30, 31, 3, 1.0, 0.25, 0.90, 20261116, 2000) and N_REP == 62
assert N_REF_EXPECT - N_MATCHED_EXPECT == N_UNREACHED_EXPECT

_RE_REP = re.compile(r"^[+-][0-9]{2}$")
_RE_RREP = re.compile(r"^R[+-][0-9]{2}$")
_RE_GRID = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?$")
SIGNOFF = ("RR73", "RRR", "73")


def parse(msg):
    """-> (kind, F1, F2, type, value).  kind 'ok' | 'hash' | 'cq' | 'unparsed'.  Text does not leave this function."""
    if "<" in msg or ";" in msg:
        return ("hash", None, None, None, None)
    t = msg.split()
    if not t:
        return ("unparsed", None, None, None, None)
    if t[0] in ("CQ", "QRZ", "DE"):
        return ("cq", None, None, None, None)
    if len(t) == 2:
        return ("ok", t[0], t[1], "empty", None)
    if len(t) != 3:
        return ("unparsed", None, None, None, None)
    f1, f2, pay = t
    if pay in SIGNOFF:
        return ("ok", f1, f2, pay, None)
    if _RE_RREP.match(pay):
        return ("ok", f1, f2, "rreport", int(pay[1:]))
    if _RE_REP.match(pay):
        return ("ok", f1, f2, "report", int(pay))
    if _RE_GRID.match(pay):
        return ("ok", f1, f2, "grid", None)
    return ("unparsed", None, None, None, None)


def _in_range(v):
    return v is not None and REP_LO <= v <= REP_HI


def in_n(tp, tu, vu):
    """Pu in N(Pp): tp = the previous payload's type, (tu, vu) = the candidate's."""
    if tp in ("grid", "empty"):
        return tu == "report" and _in_range(vu)
    if tp == "report":
        return tu == "rreport" and _in_range(vu)
    if tp == "rreport":
        return tu in SIGNOFF
    if tp in ("RR73", "RRR"):
        return tu == "73"
    return False


def in_n2(tp, tu, vu):
    if tp in ("grid", "empty"):
        return tu == "rreport" and _in_range(vu)
    if tp == "report":
        return tu in SIGNOFF
    if tp == "rreport":
        return tu == "73"
    return False


def size_n(tp):
    return {"grid": N_REP, "empty": N_REP, "report": N_REP, "rreport": 3, "RR73": 1, "RRR": 1, "73": 0}.get(tp, 0)


def size_n2(tp):
    return {"grid": N_REP, "empty": N_REP, "report": 3, "rreport": 1}.get(tp, 0)


def stamp_index(stamps):
    ts = [dt.datetime.strptime(s, "%y%m%d_%H%M%S") for s in stamps]
    gaps = sum(1 for i in range(len(ts) - 1) if (ts[i + 1] - ts[i]).total_seconds() != CYCLE_S)
    return gaps


def load_night():
    """-> stamps (the OWS cycle archive, contiguous 15 s grid), per cycle: wsjt rows [(snr, freq, text, matched)], plus counts.  Text stays in memory only."""
    ar = [l.split(",")[0] for l in open(NIGHT + "/owsfz/cycle-archive.csv", encoding="utf-8")][1:]
    stamps = [a[:-4] for a in ar]
    w = AC.parse_all_txt(NIGHT + "/wsjt-x/ALL.TXT")
    o = AC.parse_all_txt(NIGHT + "/owsfz/ALL.TXT")
    by_w, by_o = collections.defaultdict(list), collections.defaultdict(list)
    for r in w:
        by_w[r["ts"]].append(r)
    for r in o:
        by_o[r["ts"]].append(r)
    on_grid = all(int(s[-2:]) % CYCLE_S == 0 for s in by_w)
    cycles = {s: [] for s in stamps}
    off_range = 0
    n_matched = 0
    for s, rows in by_w.items():
        if s not in cycles:
            off_range += len(rows)
            continue
        okeys = collections.Counter(AC.normalize_hash_tokens(r["message"]) for r in by_o.get(s, []))
        for r in rows:                                  # multiset pairing: the first k WSJT-X rows of a key are the matched ones
            k = AC.normalize_hash_tokens(r["message"])
            m = okeys[k] > 0
            if m:
                okeys[k] -= 1
                n_matched += 1
            cycles[s].append((r["snr"], r["freq_hz"], r["message"], m))
    return stamps, cycles, {"n_ref": len(w), "n_ows": len(o), "matched": n_matched, "wsjt_only": len(w) - n_matched, "gaps": stamp_index(stamps),
                            "wsjt_rows_off_archive_range": off_range, "wsjt_stamps_on_15s_grid": on_grid}


def prep(stamps, cycles):
    """per cycle index: parsed rows [(snr, f, text, matched, parsed tuple)]; matched_by_cycle for the prior look-ups."""
    pc = []
    for s in stamps:
        pc.append([(snr, f, text, m, parse(text)) for snr, f, text, m in cycles[s]])
    return pc


def prior_matched(pc, i, lag):
    j = i - lag
    return [(f, text, p) for _, f, text, m, p in pc[j] if m] if j >= 0 else []


def exclusions(pc):
    """-> U rows as (i, snr, f, text, parsed) plus the exclusion counts, in the frozen order 1, 2, 3, 4."""
    cnt = collections.Counter()
    U = []
    for i, rows in enumerate(pc):
        xc_priors = None
        for snr, f, text, m, p in rows:
            if m:
                continue
            cnt["u_before_exclusions"] += 1
            kind = p[0]
            if kind == "hash":
                cnt["excl_1_hash_or_dxped"] += 1
                continue
            if kind == "cq":
                cnt["excl_2_cq_qrz_de"] += 1
                continue
            if kind != "ok":
                cnt["excl_3_unparsed"] += 1
                continue
            if xc_priors is None:
                xc_priors = [prior_matched(pc, i, lag) for lag in (2, 4, 6)]
            if any(pt == text and abs(pf - f) <= WINDOW_HZ for pr in xc_priors for pf, pt, _ in pr):
                cnt["excl_4_xc_territory"] += 1
                continue
            U.append((i, snr, f, text, p))
    cnt["u_after_exclusions"] = len(U)
    return U, cnt


def classify(pc, U, with_control=True):
    """-> per-row classes: S1 | S2 | S-LOOSE | none, the C-PAR flag, the K class, the payload step.  Text is read here only."""
    res = []
    for i, snr, f, text, p in U:
        _, f1, f2, tu, vu = p
        cls, kk, step = "none", None, tu
        p15 = prior_matched(pc, i, 1)
        p30 = prior_matched(pc, i, 2)
        pair_s1 = [(pf, pt, pp) for pf, pt, pp in p15 if pp[0] == "ok" and pp[1] == f2 and pp[2] == f1]
        pair_s1_any = [1 for pf, pt, pp in p15 if pp[0] in ("ok", "unparsed", "cq") and _pair_tokens(pt, f2, f1)]
        pair_s2 = [(pf, pt, pp) for pf, pt, pp in p30 if pp[0] == "ok" and pp[1] == f1 and pp[2] == f2 and abs(pf - f) <= WINDOW_HZ and pt != text]
        pair_s2_any = [1 for pf, pt, pp in p30 if _pair_tokens(pt, f1, f2) and abs(pf - f) <= WINDOW_HZ and pt != text]
        s1 = next((pp for pf, pt, pp in pair_s1 if in_n(pp[3], tu, vu)), None)
        s2 = next((pp for pf, pt, pp in pair_s2 if in_n2(pp[3], tu, vu)), None)
        if s1 is not None:
            cls, kk = "S1", ("K-low" if size_n(s1[3]) <= K_LOW_MAX else "K-high")
        elif s2 is not None:
            cls, kk = "S2", ("K-low" if size_n2(s2[3]) <= K_LOW_MAX else "K-high")
        elif pair_s1 or pair_s1_any or pair_s2 or pair_s2_any:
            cls = "S-LOOSE"
        cpar = False
        if with_control:
            cp = prior_matched(pc, i, 2)
            cpar = any(pp[0] == "ok" and pp[1] == f2 and pp[2] == f1 and in_n(pp[3], tu, vu) for pf, pt, pp in cp)
        res.append((i, snr, cls, kk, step, cpar, bool(pair_s1 or pair_s1_any or pair_s2 or pair_s2_any)))
    return res


def _pair_tokens(text, a, b):
    t = text.split()
    return len(t) >= 2 and t[0] == a and t[1] == b


def boot(count_by_cycle, nref_by_cycle):
    idx = np.random.default_rng(SEED).integers(0, len(count_by_cycle), size=(B_BOOT, len(count_by_cycle)))
    p = 100.0 * count_by_cycle[idx].sum(axis=1) / nref_by_cycle[idx].sum(axis=1)
    return float(100.0 * count_by_cycle.sum() / nref_by_cycle.sum()), [float(np.percentile(p, 2.5)), float(np.percentile(p, 97.5))]


def decide(ci, par_ok):
    if ci[1] < BAR_PP:
        return "CLOSE"
    if not par_ok:
        return "VOID"
    if ci[0] >= BAR_PP:
        return "PURSUE"
    return "BETWEEN"


def common(pc, info):
    n = len(pc)
    nref_c = np.array([len(r) for r in pc], dtype=float)
    return n, nref_c


def kcheck():
    stamps, cycles, info = load_night()
    pc = prep(stamps, cycles)
    n, nref_c = common(pc, info)
    vn = (info["n_ref"], info["n_ows"], info["matched"], info["wsjt_only"]) == (N_REF_EXPECT, N_OWS_EXPECT, N_MATCHED_EXPECT, N_UNREACHED_EXPECT)
    U, cnt = exclusions(pc)
    parsed_share = (cnt["u_before_exclusions"] - cnt["excl_3_unparsed"]) / cnt["u_before_exclusions"]
    # report range: matched report and R-report rows outside -30..+20, and how many reports there are
    rep = collections.Counter()
    for rows in pc:
        for snr, f, text, m, p in rows:
            if m and p[0] == "ok" and p[3] in ("report", "rreport"):
                rep["matched_report_rows"] += 1
                rep["outside_-30_+20"] += (not _in_range(p[4]))
    # loose pair-condition count (the Architect's own pre-count's analogue: the pair exists, no payload or frequency check on S1): per cycle, with its CI
    loose_c = np.zeros(n)
    for i, snr, f, text, p in U:
        _, f1, f2, tu, vu = p
        p15 = prior_matched(pc, i, 1)
        p30 = prior_matched(pc, i, 2)
        if any(_pair_tokens(pt, f2, f1) for pf, pt, pp in p15) or any(_pair_tokens(pt, f1, f2) and abs(pf - f) <= WINDOW_HZ and pt != text for pf, pt, pp in p30):
            loose_c[i] += 1
    pp, ci = boot(loose_c, nref_c)
    out = {"mode": "kcheck (no S1, S2, C-PAR or verdict)", "V_N": {**info, "PASS": bool(vn)}, "V_CONT_gaps": info["gaps"], "exclusions": dict(cnt),
           "V_PARSE": {"parsed_share_of_U_before_exclusion_3": parsed_share, "bar": PARSE_MIN, "PASS": parsed_share >= PARSE_MIN}, "report_range_check": dict(rep),
           "loose_pair_condition": {"rows": int(loose_c.sum()), "pp_of_n_ref": pp, "CI_pp": ci, "half_width_pp": (ci[1] - ci[0]) / 2, "note": "precision check of section 6: if half_width > 0.3 pp QA says so before freezing"}}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(OUT + "/xs_kcheck.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


def count():
    stamps, cycles, info = load_night()
    pc = prep(stamps, cycles)
    n, nref_c = common(pc, info)
    U, cnt = exclusions(pc)
    vn = (info["n_ref"], info["matched"], info["wsjt_only"]) == (N_REF_EXPECT, N_MATCHED_EXPECT, N_UNREACHED_EXPECT)
    parsed_share = (cnt["u_before_exclusions"] - cnt["excl_3_unparsed"]) / cnt["u_before_exclusions"]
    assert vn, info
    assert parsed_share >= PARSE_MIN, ("V-PARSE fails: report the unparsed shapes before counting", parsed_share)
    res = classify(pc, U)
    c = {k: np.zeros(n) for k in ("S1", "S2", "S-LOOSE", "CPAR", "S")}
    split = collections.Counter()
    by_snr, by_step = collections.Counter(), collections.Counter()
    for i, snr, cls, kk, step, cpar, pair in res:
        if cls in ("S1", "S2", "S-LOOSE"):
            c[cls][i] += 1
        if cls in ("S1", "S2"):
            c["S"][i] += 1
            split[cls + ":" + kk] += 1
            by_snr[int(np.floor(snr / 3.0) * 3)] += 1
            by_step[cls + ":" + step] += 1
        if cpar:
            c["CPAR"][i] += 1
    rows = {k: int(v.sum()) for k, v in c.items()}
    pp_s, ci_s = boot(c["S"], nref_c)
    pp_1, ci_1 = boot(c["S1"], nref_c)
    pp_2, ci_2 = boot(c["S2"], nref_c)
    par_ok = rows["CPAR"] <= PAR_RATIO * rows["S1"]
    # how scripted the night is: matched non-CQ rows that are on-script replies to a matched row at t-15 (the S1 rule applied to matched rows)
    on_script = matched_nc = 0
    for i, rws in enumerate(pc):
        p15 = prior_matched(pc, i, 1)
        for snr, f, text, m, p in rws:
            if not m or p[0] != "ok":
                continue
            matched_nc += 1
            if any(pp[0] == "ok" and pp[1] == p[2] and pp[2] == p[1] and in_n(pp[3], p[3], p[4]) for pf, pt, pp in p15):
                on_script += 1
    out = {"verdict": decide(ci_s, par_ok), "V_N": {**info, "PASS": bool(vn)}, "V_PARSE": {"share": parsed_share, "PASS": True}, "V_PAR": {"C_PAR": rows["CPAR"], "S1": rows["S1"], "bar_C_PAR_le_0.25_x_S1": bool(par_ok), "gates": "VOID row (CLOSE ignores it)"},
           "exclusions": dict(cnt), "rows": rows, "S_pp": pp_s, "S_CI_pp": ci_s, "S1_pp": pp_1, "S1_CI_pp": ci_1, "S2_pp": pp_2, "S2_CI_pp": ci_2,
           "K_split": dict(split), "K_low_share_of_S": (split["S1:K-low"] + split["S2:K-low"]) / max(rows["S"], 1),
           "by_wsjtx_snr_3dB_bin": {str(k): v for k, v in sorted(by_snr.items())}, "by_payload_step": dict(by_step),
           "matched_nonCQ_rows": matched_nc, "matched_on_script_replies": on_script, "share_scripted": on_script / max(matched_nc, 1)}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(OUT + "/xs_result.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


def selftest():
    ok = True

    def chk(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print("FAIL", name, got, want)
    chk("rr73 not grid", parse("Q1AAA Q2BBB RR73")[3], "RR73")
    chk("grid", parse("Q1AAA Q2BBB JO93")[3], "grid")
    chk("empty", parse("Q1AAA Q2BBB")[3], "empty")
    chk("report value", parse("Q1AAA Q2BBB -10")[4], -10)
    chk("rreport value", parse("Q1AAA Q2BBB R+05")[3:], ("rreport", 5))
    chk("hash", parse("<...> Q2BBB -10")[0], "hash")
    chk("dxped", parse("Q1AAA RR73; Q2BBB <Q3CCC> -10")[0], "hash")
    chk("cq", parse("CQ Q2BBB JO93")[0], "cq")
    chk("freetext", parse("Q1AAA Q2BBB HELLO")[0], "unparsed")
    chk("N grid->report", in_n("grid", "report", -12), True)
    chk("N grid->rreport must fail", in_n("grid", "rreport", -12), False)
    chk("N report out of range must fail (-31 and +32)", (in_n("grid", "report", -31), in_n("grid", "report", 32)), (False, False))
    chk("N report +31 is inside (the observed maximum)", in_n("grid", "report", 31), True)
    chk("N report->rreport", in_n("report", "rreport", -12), True)
    chk("N rreport->RR73/RRR/73", [in_n("rreport", t, None) for t in ("RR73", "RRR", "73", "grid")], [True, True, True, False])
    chk("N RR73->73 only", [in_n("RR73", t, None) for t in ("73", "RR73")], [True, False])
    chk("N 73->none", in_n("73", "73", None), False)
    chk("N2 grid->rreport", in_n2("grid", "rreport", 3), True)
    chk("N2 report->signoff", [in_n2("report", t, None) for t in SIGNOFF], [True, True, True])
    chk("N2 rreport->73", [in_n2("rreport", t, None) for t in ("73", "RR73")], [True, False])
    chk("sizes", (size_n("grid"), size_n("report"), size_n("rreport"), size_n("RR73"), size_n2("report"), size_n2("rreport")), (62, 62, 3, 1, 3, 1))
    # a toy night, three cycles, synthetic Q calls: cycle0 matched 'Q2BBB Q1AAA -10' (Q1AAA sent a report to Q2BBB); cycle1 unreached 'Q1AAA Q2BBB R-12' = Q2BBB's reply: S1.
    mk = lambda *rows: [(-15, f, t, m, parse(t)) for f, t, m in rows]
    pc = [mk((1000, "Q2BBB Q1AAA -10", True)), mk((1500, "Q1AAA Q2BBB R-12", False), (1700, "Q5EEE Q6FFF JO93", False)), mk((1200, "Q7GGG Q8HHH RR73", False))]
    U, cnt = exclusions(pc)
    res = classify(pc, U)
    chk("toy S1", [r[2] for r in res], ["S1", "none", "none"])
    chk("toy K class (report -> rreport is report-valued, K-high)", res[0][3], "K-high")
    # C-PAR must be 0 here (the pair is at t-15, not t-30), and must be 1 when the same row sits at t-30
    chk("toy C-PAR 0", res[0][5], False)
    pc2 = [mk((1000, "Q2BBB Q1AAA -10", True)), mk(), mk((1500, "Q1AAA Q2BBB R-12", False))]
    U2, _ = exclusions(pc2)
    r2 = classify(pc2, U2)
    chk("toy same-parity prior is NOT S1", r2[0][2], "none")
    chk("toy C-PAR 1", r2[0][5], True)
    # S2: same pair, same frequency, two cycles back: Q2BBB sent 'Q1AAA Q2BBB -10' (report), next own step 'Q1AAA Q2BBB RR73' is in N2(report)
    pc3 = [mk((1500, "Q1AAA Q2BBB -10", True)), mk(), mk((1503, "Q1AAA Q2BBB RR73", False))]
    U3, _ = exclusions(pc3)
    chk("toy S2", [r[2] for r in classify(pc3, U3)], ["S2"])
    # S-LOOSE: the pair exists, the payload is off-script (a grid after a report)
    pc4 = [mk((1000, "Q2BBB Q1AAA -10", True)), mk((1500, "Q1AAA Q2BBB JO93", False))]
    U4, _ = exclusions(pc4)
    chk("toy S-LOOSE", [r[2] for r in classify(pc4, U4)], ["S-LOOSE"])
    # XC territory: the unreached row is the exact text of a matched row at t-30 within 10 Hz, so it leaves U before S1/S2
    pc5 = [mk((1500, "Q1AAA Q2BBB R-12", True)), mk(), mk((1504, "Q1AAA Q2BBB R-12", False))]
    U5, c5 = exclusions(pc5)
    chk("toy XC territory excluded", (len(U5), c5["excl_4_xc_territory"]), (0, 1))
    # decision rows, including ones that must not fire
    chk("decide CLOSE", decide([0.2, 0.9], True), "CLOSE")
    chk("decide CLOSE ignores V-PAR", decide([0.2, 0.9], False), "CLOSE")
    chk("decide VOID", decide([0.5, 1.5], False), "VOID")
    chk("decide PURSUE", decide([1.1, 1.6], True), "PURSUE")
    chk("decide BETWEEN", decide([0.5, 1.5], True), "BETWEEN")
    chk("decide PURSUE needs lo >= 1.0 (0.99 is BETWEEN)", decide([0.99, 1.6], True), "BETWEEN")
    print("selftest ALL PASS" if ok else "selftest FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    m = sys.argv[1]
    sys.exit(selftest() if m == "selftest" else (kcheck() or 0) if m == "kcheck" else (count() or 0) if m == "count" else 2)
