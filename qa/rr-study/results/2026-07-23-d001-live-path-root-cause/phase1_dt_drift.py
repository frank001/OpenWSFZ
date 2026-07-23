"""D-001 live-path root-cause, Phase 1 (spec 3.1/3.2). Offline only.

1a: mine retained Debug-level daemon logs (07-07, 06-22) for restarts + [WRN] counts.
1b: cross-app DT-drift -- matched decodes, delta_dt = openwsfz_dt - wsjt_dt, binned hourly by
    session-elapsed time, OLS trend per session/band, plus each app's own DT stability check.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[4]
ARTEFACTS = REPO_ROOT / "artefacts"

SESSIONS = [
    ("2026-07-07", "20260706_live_run_2308", "logs/openswfz-20260706T210818Z.log"),
    ("2026-07-06", "20260706_live_run", None),
    ("2026-06-22", "20260622_live run", "openswfz-20260621T225646Z.log"),
]

LINE_RE = re.compile(
    r"^(?P<ts>\d{6}_\d{6})\s+(?P<dial>[\d.]+)\s+Rx\s+FT8\s+"
    r"(?P<snr>-?\d+)\s+(?P<dt>-?[\d.]+)\s+(?P<freq>\d+)\s+(?P<msg>.+?)\s*$"
)
HASH_RE = re.compile(r"<[^>]*>")
BANDS = [("< -15 dB", lambda s: s < -15), ("-15..-10 dB", lambda s: -15 <= s < -10)]


def parse(path, source):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            rows.append({"ts": m.group("ts"), "snr": int(m.group("snr")),
                         "dt": float(m.group("dt")), "freq": int(m.group("freq")),
                         "msg": " ".join(m.group("msg").split()).upper(), "source": source})
    return rows


def freq_bin(f, w=50):
    return int(round(f / w)) * w


def sig_key(r):
    return (r["ts"], freq_bin(r["freq"]), r["msg"])


def ts_to_dt(ts):
    return datetime.strptime(ts, "%y%m%d_%H%M%S")


def ols_slope(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return None
    slope = sxy / sxx
    resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in resid)
    if n <= 2:
        return {"slope": slope, "n": n, "se": None, "t": None, "p_lt_05": None}
    mse = sse / (n - 2)
    se = (mse / sxx) ** 0.5 if sxx > 0 else None
    t = (slope / se) if se and se > 0 else None
    # rough two-sided p<0.05 threshold via t>~2.0 for n>~20; flag only, not exact p-value
    sig = (abs(t) > 2.0) if t is not None else None
    return {"slope": slope, "n": n, "se": se, "t": t, "p_lt_05": sig}


def phase1a():
    print("=== Phase 1a: retained-log mining ===")
    out = {}
    for label, dirname, logrel in SESSIONS:
        if logrel is None:
            print(f"{label}: no retained daemon log")
            out[label] = None
            continue
        p = ARTEFACTS / dirname / logrel
        if not p.exists():
            print(f"{label}: expected log not found at {p}")
            out[label] = None
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        starts = [l for l in lines if "CycleFramer started" in l]
        cancels = [l for l in lines if "CycleFramer cancelled" in l]
        wrns = [l for l in lines if "[WRN]" in l]
        print(f"{label}: {len(lines)} lines, {len(starts)} CycleFramer-started, "
              f"{len(cancels)} CycleFramer-cancelled, {len(wrns)} [WRN] lines")
        for w in wrns[:5]:
            print(f"    WRN: {w.strip()}")
        out[label] = {"lines": len(lines), "starts": len(starts), "cancels": len(cancels),
                       "wrn": len(wrns), "wrn_samples": wrns[:10]}
    return out


def phase1b():
    print("\n=== Phase 1b: cross-app DT drift ===")
    out = {}
    for label, dirname, _ in SESSIONS:
        session_dir = ARTEFACTS / dirname
        of = session_dir / "OpenWSFZ ALL.TXT"
        wf = session_dir / "WSJT-X ALL.TXT"
        if not of.exists() or not wf.exists():
            print(f"{label}: ALL.TXT pair missing")
            continue
        owsfz = parse(of, "owsfz")
        wsjt = parse(wf, "wsjt")
        okeys = {sig_key(r): r for r in owsfz if not HASH_RE.search(r["msg"])}
        wkeys = {sig_key(r): r for r in wsjt if not HASH_RE.search(r["msg"])}
        matched = set(okeys) & set(wkeys)
        if not matched:
            print(f"{label}: no matched decodes")
            continue
        all_ts = [ts_to_dt(r["ts"]) for r in owsfz] + [ts_to_dt(r["ts"]) for r in wsjt]
        t0 = min(all_ts)

        session_result = {}
        for scope_name, scope_fn in [("ALL SNR", lambda s: True)] + BANDS:
            xs, ys_delta, ys_o, ys_w = [], [], [], []
            for k in matched:
                orow, wrow = okeys[k], wkeys[k]
                if not scope_fn(wrow["snr"]):
                    continue
                hrs = (ts_to_dt(orow["ts"]) - t0).total_seconds() / 3600.0
                xs.append(hrs)
                ys_delta.append(orow["dt"] - wrow["dt"])
                ys_o.append(orow["dt"])
                ys_w.append(wrow["dt"])
            fit_delta = ols_slope(xs, ys_delta)
            fit_o = ols_slope(xs, ys_o)
            fit_w = ols_slope(xs, ys_w)
            spread = (max(ys_delta) - min(ys_delta)) if ys_delta else None
            print(f"{label} [{scope_name}]: n_matched={len(xs)}  "
                  f"delta_dt slope={fit_delta['slope']:.5f}s/hr t={fit_delta['t']}  "
                  if fit_delta else f"{label} [{scope_name}]: n_matched={len(xs)} (too few for fit)")
            if fit_delta:
                print(f"    openwsfz_dt slope={fit_o['slope']:.5f}s/hr  "
                      f"wsjt_dt slope={fit_w['slope']:.5f}s/hr  delta spread={spread:.3f}s")
            session_result[scope_name] = {
                "n_matched": len(xs), "delta_dt_fit": fit_delta,
                "openwsfz_dt_fit": fit_o, "wsjt_dt_fit": fit_w,
                "delta_dt_spread_s": spread,
            }
        out[label] = session_result
    return out


def main():
    log_results = phase1a()
    dt_results = phase1b()
    out_path = Path(__file__).resolve().parent / "phase1_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"log_mining": log_results, "dt_drift": dt_results}, f, indent=2, default=str)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
