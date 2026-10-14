"""Per-sweep MONITORING SUMMARY (QA tooling; aggregates and process/kernel state only, NFR-021: no message text is read into the output).

    python monitoring_summary.py --sup-dir <supervisor dir> --run-dir <results run folder> [--tz-h 2] [--from-slot HH:MM:SS]

Collects, for one battery, everything the monitoring layer recorded and writes `<run-dir>/monitoring_summary.json` (the full-ANOVA / baseline report reads it):
  M1  the monitor log (`monitor.jsonl`, `stall_events.jsonl`): samples, how old the newest WSJT-X save WAV got, stall episodes, WSJT-X / jt9 process identity
      (a restart shows as a second PID), memory and thread counts, `aplay` count and age, ALSA stream states, the suspended-time delta (a sleep during the
      run shows as a change), OpenWSFZ's cycle-archive age, host load;
  M2  the liveness gate (`liveness_gate.json`, `STALLED.json`);
  M3  the coverage rows of the analyser's report (`Coverage (validity)`), per scenario and appraiser;
  OTHER  the daemon log's aggregates (late cycles, cycle-grid realignment warnings, residual passes and abandonments, drop-like line COUNT), the build pins
      (`arm_config.json`), the S6 pins and validity rows if S6 ran, core files left in the home folder, the replacement marker if this sweep replaced another.
The daemon log is read only for the counts the `s6/collapse_check.py` parser already extracts; no line of it is copied.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "s6"))


def read_jsonl(path: str) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def _kb(v) -> int | None:
    if not v:
        return None
    m = re.match(r"\s*(\d+)", str(v))
    return int(m.group(1)) if m else None


def _pct(v: list, p: float):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]


def _t(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def summarise_monitor(samples: list, stall_events: list) -> dict:
    if not samples:
        return {"samples": 0, "note": "no monitor log: M1 was not running"}
    ts = [_t(s["t"]) for s in samples]
    gaps = [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]
    age = [s["wav_age_s"] for s in samples if s.get("wav_age_s") is not None]
    wp = Counter()
    rss, thr, jp = [], [], Counter()
    for s in samples:
        for p in s.get("wsjtx", []):
            wp[p["pid"]] += 1
            if _kb(p.get("rss_kb")) is not None:
                rss.append(_kb(p["rss_kb"]))
            if p.get("threads") is not None:
                try:
                    thr.append(int(p["threads"]))
                except ValueError:
                    pass
        for p in s.get("jt9", []):
            jp[p["pid"]] += 1
    alsa: dict = {}
    for s in samples:
        for k, v in (s.get("alsa") or {}).items():
            alsa.setdefault(k, Counter())[v] += 1
    susp = [s["suspended_s"] for s in samples if s.get("suspended_s") is not None and s["suspended_s"] >= 0]
    apl = [s.get("aplay", {}) for s in samples]
    load = [s["load1"] for s in samples if s.get("load1") is not None]
    arch = [s["owsfz_archive_age_s"] for s in samples if s.get("owsfz_archive_age_s") is not None]
    return {"samples": len(samples), "first_utc": samples[0]["t"], "last_utc": samples[-1]["t"], "interval_s_median": statistics.median(gaps) if gaps else None,
            "gaps_over_2x_interval": sum(1 for g in gaps if g > 2 * (statistics.median(gaps) if gaps else 15)), "max_gap_s": max(gaps) if gaps else None,
            "ok_share": round(sum(1 for s in samples if s.get("ok")) / len(samples), 4), "samples_not_ok": sum(1 for s in samples if not s.get("ok")),
            "wav_age_s": {"median": statistics.median(age) if age else None, "p99": _pct(age, 0.99), "max": max(age) if age else None},
            "stall_episodes": len(stall_events), "stalls": [{"t": e.get("t"), "reason": e.get("reason"), "snapshot": os.path.basename(e.get("snapshot") or "")} for e in stall_events],
            "wsjtx_pids": sorted(wp), "wsjtx_restarts_during_monitoring": max(0, len(wp) - 1),
            "wsjtx_rss_kb": {"first": rss[0] if rss else None, "last": rss[-1] if rss else None, "max": max(rss) if rss else None},
            "wsjtx_threads": {"min": min(thr) if thr else None, "max": max(thr) if thr else None},
            "jt9_pids": sorted(jp), "jt9_restarts_during_monitoring": max(0, len(jp) - 1),
            "aplay": {"max_count": max((a.get("count", 0) for a in apl), default=0), "max_oldest_s": max((a.get("oldest_s") or 0 for a in apl), default=0)},
            "alsa_states": {k: dict(v) for k, v in sorted(alsa.items())},
            "suspended_s": {"first": susp[0] if susp else None, "last": susp[-1] if susp else None, "delta": round(susp[-1] - susp[0], 1) if susp else None},
            "owsfz_archive_age_s_max": max(arch) if arch else None,
            "host_load1": {"median": statistics.median(load) if load else None, "max": max(load) if load else None}}


def summarise_daemon_log(path: str, tz_h: float, from_slot: str = "00:00:00") -> dict:
    if not os.path.isfile(path):
        return {"note": "no daemon.stdout.log in the supervisor folder"}
    import collapse_check as cc
    d = cc.parse(path, tz_h)
    lo = cc.sod(*from_slot.split(":"))
    cyc = [c for c in d["cycles"] if c["slot_sod"] >= lo]
    clamps = [c for c in d["clamps"] if c["t_sod"] >= lo]
    el = [p["elapsed_ms"] for p in d["passes"]]
    return {"cycles_logged": len(cyc), "late_cycles": sum(1 for c in cyc if c["lag_s"] > cc.LATE_S), "late_threshold_s": cc.LATE_S,
            "lag_s_median": statistics.median(c["lag_s"] for c in cyc) if cyc else None, "lag_s_max": max((c["lag_s"] for c in cyc), default=None),
            "cycle_decode_elapsed_ms_median": statistics.median(c["elapsed_ms"] for c in cyc) if cyc else None,
            "cycle_decode_elapsed_ms_max": max((c["elapsed_ms"] for c in cyc), default=None),
            "clamp_warnings": len(clamps), "clamp_positive": sum(1 for c in clamps if c["wanted_s"] > 0), "clamp_negative": sum(1 for c in clamps if c["wanted_s"] < 0),
            "residual_passes": len(d["passes"]), "residual_abandoned": sum(1 for p in d["passes"] if p["abandoned"]),
            "residual_elapsed_ms": {"median": statistics.median(el) if el else None, "p90": _pct(el, 0.9), "max": max(el) if el else None},
            "fitted_signals_median": statistics.median(p["fitted"] for p in d["passes"]) if d["passes"] else None,
            "drop_or_overflow_like_lines": len(d["dropish"]), "episodes": cc.episodes(cyc, d["passes"])}


def coverage_rows_from_report(report_md: str) -> list:
    rows = []
    for line in report_md.splitlines():
        m = re.match(r"^\| Coverage \(validity\) \| ([^|]+) \| ([^|]+) \| (\w+) \|", line)
        if m:
            rows.append({"scope": m.group(1).strip(), "value": m.group(2).strip(), "verdict": m.group(3)})
    return rows


def _load(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def summarise_run(sup_dir: str, run_dir: str, tz_h: float, from_slot: str = "00:00:00", core_dir: str | None = None) -> dict:
    out: dict = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "supervisor_dir": os.path.basename(sup_dir.rstrip("/\\")),
                 "run_dir": os.path.basename(run_dir.rstrip("/\\"))}
    out["M1_monitor"] = summarise_monitor(read_jsonl(os.path.join(sup_dir, "monitor.jsonl")), read_jsonl(os.path.join(sup_dir, "stall_events.jsonl")))
    gate = _load(os.path.join(run_dir, "liveness_gate.json"))
    st = _load(os.path.join(run_dir, "STALLED.json"))
    out["M2_gate"] = {"gate_record": gate, "stalled": st is not None, "stalled_record": st}
    rep = os.path.join(run_dir, "report.md")
    cov = coverage_rows_from_report(open(rep, encoding="utf-8").read()) if os.path.isfile(rep) else []
    out["M3_coverage"] = {"rows": cov, "rows_pass": sum(1 for r in cov if r["verdict"] == "PASS"), "rows_invalid": sum(1 for r in cov if r["verdict"] != "PASS"),
                          "slot_files": {"wsjtx": os.path.isfile(os.path.join(run_dir, "coverage_slots_wsjtx.txt")), "owsfz": os.path.isfile(os.path.join(run_dir, "coverage_slots_owsfz.txt"))}}
    out["daemon_log"] = summarise_daemon_log(os.path.join(sup_dir, "daemon.stdout.log"), tz_h, from_slot)
    arm = _load(os.path.join(run_dir, "arm_config.json")) or {}
    out["build_pins"] = {"commit": (arm.get("build") or {}).get("commit"), "dirty": (arm.get("build") or {}).get("build_dirty"),
                         "shim": (arm.get("daemon") or {}).get("shim_version"), "libft8_sha256": (arm.get("daemon") or {}).get("dll_sha256"),
                         "decoder_readback": (arm.get("daemon") or {}).get("decoder_readback"), "wsjtx_ndepth": (arm.get("wsjtx") or {}).get("NDepth")}
    s6v = _load(os.path.join(run_dir, "s6", "s6_validity.json"))
    out["S6_validity"] = None if s6v is None else {k: (v.get("result") if isinstance(v, dict) else v) for k, v in s6v.items() if k.startswith("S6-")}
    warm = _load(os.path.join(run_dir, "warmup_check.json"))
    out["warmup_check"] = None if warm is None else {"ok": warm.get("ok", warm.get("skipped")), "attempts": len(warm.get("attempts", []))}
    cores = []
    if core_dir and os.path.isdir(core_dir):
        status = _load(os.path.join(sup_dir, "status.json")) or {}
        t0 = _t(status["started_utc"]).timestamp() if status.get("started_utc") else 0
        cores = [os.path.basename(p) for p in glob.glob(os.path.join(core_dir, "core*")) if os.path.getmtime(p) >= t0]
    out["core_files_since_start"] = cores
    out["replacement"] = _load(os.path.join(run_dir, "REPLACEMENT.json"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sup-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--tz-h", type=float, default=None, help="local offset from UTC in hours (default: this machine's)")
    ap.add_argument("--from-slot", default="00:00:00")
    ap.add_argument("--core-dir", default=None)
    a = ap.parse_args()
    tz = a.tz_h if a.tz_h is not None else -(time.altzone if time.localtime().tm_isdst > 0 else time.timezone) / 3600.0
    res = summarise_run(a.sup_dir, a.run_dir, tz, a.from_slot, a.core_dir)
    with open(os.path.join(a.run_dir, "monitoring_summary.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({k: res[k] for k in ("M2_gate",)}, indent=1)[:600])
    print("monitor samples:", res["M1_monitor"].get("samples"), "| stall episodes:", res["M1_monitor"].get("stall_episodes"),
          "| coverage rows pass/invalid:", res["M3_coverage"]["rows_pass"], "/", res["M3_coverage"]["rows_invalid"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
