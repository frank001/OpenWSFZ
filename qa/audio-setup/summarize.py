"""#194 sampler summary for a run's report, and the scan join (architect ruling 2026-10-03, section 3).

    python summarize.py audio_setup.jsonl                 -> markdown block for the run report
    python summarize.py audio_setup.jsonl --slot <UTC>    -> setup changes joined to one flagged slot

Pure functions over the JSONL; no station access.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

HEARTBEAT_GAP_MAX_S = 70.0           # spec AS4: a gap over this is a hole in coverage
COVERAGE_PARTIAL_BELOW = 0.98        # ruling 3.2: below this the run's sampler output is labelled PARTIAL
COLD_SAMPLE_MAX_MS = 2000.0          # Amendment 1
JOIN_BEFORE_S = 30.0                 # ruling 2.2: detected_utc in [S - 30 s, S + 40 s]
JOIN_AFTER_S = 40.0
JOIN_WINDOW_TEXT = f"detected_utc in [S-{JOIN_BEFORE_S:.0f} s, S+{JOIN_AFTER_S:.0f} s]"


def parse_utc(s: str) -> float:
    """Accepts both the sampler's microsecond stamps and the scan's whole-second ``cycle_utc``."""
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in s else "%Y-%m-%dT%H:%M:%SZ"
    return dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc).timestamp()


def load(path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def coverage(recs: list[dict]) -> dict:
    """Fraction of the run window [first record, last record] lying between consecutive liveness points
    (heartbeats and start/restart/end snapshots) that are no more than HEARTBEAT_GAP_MAX_S apart."""
    live = sorted(parse_utc(r["utc"]) for r in recs
                  if r["type"] == "heartbeat" or (r["type"] == "snapshot"))
    if len(live) < 2:
        return {"window_s": 0.0, "covered_s": 0.0, "coverage": 0.0, "max_gap_s": 0.0}
    window = live[-1] - live[0]
    gaps = [b - a for a, b in zip(live, live[1:])]
    covered = sum(g for g in gaps if g <= HEARTBEAT_GAP_MAX_S)
    return {"window_s": round(window, 1), "covered_s": round(covered, 1),
            "coverage": covered / window if window > 0 else 0.0, "max_gap_s": round(max(gaps), 1)}


def summarise(recs: list[dict]) -> dict:
    cov = coverage(recs)
    crashes = [r for r in recs if r["type"] == "worker_crash"]
    restarts = [r for r in recs if r["type"] == "snapshot" and r["kind"] == "restart"]
    slow_restarts = [{"utc": r["utc"], "cold_sample_ms": r["cold_sample_ms"]}
                     for r in restarts if r.get("cold_sample_ms", 0) > COLD_SAMPLE_MAX_MS]
    starts = [r for r in recs if r["type"] == "snapshot" and r["kind"] == "start"]
    hb = [r for r in recs if r["type"] == "heartbeat"]
    return {
        "worker_crashes": len(crashes), "worker_restarts": len(restarts),
        "slow_restart_cold_samples": slow_restarts,
        "start_cold_sample_ms": starts[0].get("cold_sample_ms") if starts else None,
        "coverage": cov, "label": "OK" if cov["coverage"] >= COVERAGE_PARTIAL_BELOW else "PARTIAL",
        "changes": sum(r["type"] == "change" for r in recs),
        "unverified_start_diffs": sum(r["type"] == "unverified_start_diff" for r in recs),
        "warm_sample_ms_max": max((r.get("sample_ms_max", 0.0) for r in hb[1:]), default=None),
        "vm_dirty_calls": sum(r.get("vm_dirty_calls", 0) for r in hb),
        "vm_dirty_nonzero": sum(r.get("vm_dirty_nonzero", 0) for r in hb),
        "vm_dirty_loop_max": max((r.get("vm_dirty_loop_max", 0) for r in hb), default=0),
        "unavailable_sources": sorted({f"{r['source']}: {r['detail']}" for r in recs if r["type"] == "unavailable"}),
    }


def join_slot(recs: list[dict], slot_utc: str) -> list[dict]:
    """Setup changes for one flagged slot. ``unverified_start_diff`` records are never joined."""
    s = parse_utc(slot_utc)
    return [r for r in recs if r["type"] == "change"
            and s - JOIN_BEFORE_S <= parse_utc(r.get("detected_utc", r["utc"])) <= s + JOIN_AFTER_S]


def joined_slots(recs: list[dict], flagged_csv) -> dict:
    """Scan-flagged slots (by distinct slot key) with >= 1 setup change in the join window (ruling addendum)."""
    import csv
    slots = {}
    with open(flagged_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            slots.setdefault(row["slot"], row["cycle_utc"])
    hit = {k: [r["field"] for r in join_slot(recs, utc)] for k, utc in slots.items()}
    return {"flagged_slots": len(slots), "joined_slots": sum(1 for v in hit.values() if v), "window": JOIN_WINDOW_TEXT}


def markdown(sm: dict, joined: dict | None = None) -> str:
    c = sm["coverage"]
    lines = [
        "### Audio-setup sampler (#194)", "",
        f"- **Sampler output: {sm['label']}** — coverage {c['coverage']*100:.1f} % of {c['window_s']:.0f} s "
        f"(heartbeats with no gap over {HEARTBEAT_GAP_MAX_S:.0f} s; max gap {c['max_gap_s']} s; PARTIAL below {COVERAGE_PARTIAL_BELOW*100:.0f} %).",
        f"- Worker crashes: **{sm['worker_crashes']}**; restarts: **{sm['worker_restarts']}**."
        + (f" Restart cold samples over {COLD_SAMPLE_MAX_MS/1000:.0f} s (descriptive): {sm['slow_restart_cold_samples']}"
           if sm["slow_restart_cold_samples"] else ""),
        f"- First (cold) sample {sm['start_cold_sample_ms']} ms; warm sample max {sm['warm_sample_ms_max']} ms.",
        f"- Setup changes logged: **{sm['changes']}**; `unverified_start_diff` (excluded from the join): {sm['unverified_start_diffs']}.",
        f"- `VBVMR_IsParametersDirty`: {sm['vm_dirty_calls']} calls, {sm['vm_dirty_nonzero']} returned non-zero, longest loop {sm['vm_dirty_loop_max']} calls.",
        f"- Scan join window: {JOIN_WINDOW_TEXT}.",
    ]
    if joined is not None:
        lines.append(f"- **Scan-flagged slots with at least one setup change in the window: {joined['joined_slots']} of "
                     f"{joined['flagged_slots']}** ({joined['window']}; `unverified_start_diff` excluded).")
    else:
        lines.append("- Scan-flagged slots joined: not yet computed (run `summarize.py <jsonl> --flagged <flagged_slots.csv>` after the scan).")
    if sm["unavailable_sources"]:
        lines.append(f"- Unavailable sources: {sm['unavailable_sources']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--slot", default=None)
    ap.add_argument("--flagged", default=None, help="flagged_slots.csv: adds the joined-slot count")
    a = ap.parse_args()
    recs = load(a.jsonl)
    if a.slot:
        print(json.dumps(join_slot(recs, a.slot), indent=1))
    else:
        print(markdown(summarise(recs), joined_slots(recs, a.flagged) if a.flagged else None))
