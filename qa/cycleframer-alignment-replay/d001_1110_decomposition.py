#!/usr/bin/env python3
"""tasks.md 11.10 -- D-001 absolute-gap sizing on the 0724 session's own audio.

Settles the one open question from the Architect's count-ratio pass
(2026-07-25-d001-live-path-decomposition-findings.md): is the live-path half of D-001's
recall gap explained by CycleFramer alignment error, or by a second, distinct capture-path
mechanism? Method constraints (a)-(e) per the ARCHITECT HANDOFF TO QA, tasks.md 11.10:

(a) SPEC.md 5.3's paired within-cycle recall metric, not a count ratio.
(b) True UTC reconstructed from cycleStart + the daemon log's own correction/restart
    events -- timestamp-keyed joining against the live ALL.TXT label is invalid (it drops
    1,348/1,789 cycles and selects on the correction residue).
(c) delta_live(k) = DT_ref(k) - DT_live(k) (SPEC.md section 6 step 3's corrected sign),
    absolute delta frame -- do not compare against DT-relative intervals.
(d) 11.6's two guards: collision assertion (fail loudly on any hash-token merge), and
    hashTableRejectCount recorded per arm.
(e) NFR-021: this script and its console output must never print a bare callsign; only
    aggregate counts/medians. --out CSVs (message text included) stay under _work/,
    already git-ignored.

Reconstruction method (see this file's own docstring on combine_date_time / the log walk
for the full reasoning): cycleStart's departure from the true UTC 15 s grid is exactly the
cumulative signed correction sum (SPEC.md section 2 item 1, verified to the millisecond).
The daemon's own "Cycle boundary resync: ... cycleStart re-anchored to HH:MM:SS.mmm" log
line already reports that exact post-correction value -- millisecond precision, no need to
re-derive the arithmetic from corrections_table.csv. Three "CycleFramer started" events
occurred in this session (2 within the first 90s at startup, before sustained decoding
began; 1 genuine mid-session restart at 21:07:00 UTC, ~41 min in) -- each is a hard reset
of the correction chain and is treated as such below. Between resync/restart events,
cycleStart advances by exactly the nominal 15.000 s (CycleFramer.cs: nothing else ever
touches it).

HK-009: reconfigure stdout to UTF-8 up front.
"""
from __future__ import annotations

import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from score_recall import parse_all_txt, normalize_hash_tokens  # noqa: E402
from falsification_check import predict_recall  # noqa: E402

ARTE = ROOT / "artefacts" / "20260724_live_run_2227"
LOG_FILES = [
    ARTE / "openswfz-20260724T202531Z.log",
    ARTE / "openswfz-20260724T210711Z.log",
]
LIVE_ALL_TXT = ARTE / "ALL.TXT"
BASELINE_ALL_TXT = HERE / "_work" / "phase1b" / "baseline_decoded" / "k10_c0.10_n60" / "ALL.TXT"
BASELINE_DT_POPULATION = HERE / "_work" / "phase1b" / "baseline_dt_population.json"
OUT_DIR = HERE / "_work" / "d001_1110"

SESSION_START = datetime(2026, 7, 24, 20, 28, 0, tzinfo=timezone.utc)  # first WAV, SPEC.md section 4
MIN_REF = 5  # SPEC.md 5.3

LOG_LINE_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) ([+-]\d{2}:\d{2}) \[(\w+)\] (.*)$'
)
STARTED_RE = re.compile(
    r'CycleFramer started; leading silence = \d+ samples \([\d.]+ s\), cycle start = (\d{2}:\d{2}:\d{2})\.'
)
EMITTED_RE = re.compile(r'Window emitted \(\d+ samples, cycle (\d{2}:\d{2}:\d{2})\)')
RESYNC_RE = re.compile(r'cycleStart re-anchored to (\d{2}:\d{2}:\d{2}\.\d+)\.')
REJECT_RE = re.compile(r'hashTableRejectCount=(\d+) \(process-lifetime cumulative\)')


def parse_log_line_utc(ts_str: str, tz_str: str) -> datetime:
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    sign = 1 if tz_str[0] == "+" else -1
    hh, mm = tz_str[1:].split(":")
    offset = sign * timedelta(hours=int(hh), minutes=int(mm))
    return dt.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)


def combine_date_time(anchor_utc: datetime, hms: str) -> datetime:
    """Attach a bare HH:MM:SS[.mmm] time-of-day (as reported inline in a log message) to
    the calendar date implied by the log line's OWN (already-UTC) leading timestamp,
    correcting for a +/-1 day wraparound if the two disagree by more than 12h (only
    possible right at a UTC midnight the ~15s-old 'cycle'/'re-anchored to' value spans)."""
    if "." in hms:
        t = datetime.strptime(hms, "%H:%M:%S.%f").time()
    else:
        t = datetime.strptime(hms, "%H:%M:%S").time()
    candidate = anchor_utc.replace(hour=t.hour, minute=t.minute, second=t.second,
                                    microsecond=t.microsecond)
    delta = candidate - anchor_utc
    if delta > timedelta(hours=12):
        candidate -= timedelta(days=1)
    elif delta < -timedelta(hours=12):
        candidate += timedelta(days=1)
    return candidate


def reconstruct_windows() -> tuple[dict[str, datetime], int, int]:
    """Walk both log files in order, returns (ts_field -> precise reconstructed cycleStart),
    plus (n_resync_consumed, n_restarts) for the report."""
    label_to_precise: dict[str, datetime] = {}
    precise: datetime | None = None
    pending_override: datetime | None = None
    awaiting_reset: datetime | None = None
    n_resync = 0
    n_restart = 0
    n_mismatch = 0

    for lf in LOG_FILES:
        with open(lf, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = LOG_LINE_RE.match(line)
                if not m:
                    continue
                ts_str, tz_str, _level, rest = m.groups()

                sm = STARTED_RE.search(rest)
                if sm:
                    anchor = parse_log_line_utc(ts_str, tz_str)
                    awaiting_reset = combine_date_time(anchor, sm.group(1))
                    pending_override = None
                    n_restart += 1
                    continue

                rm = RESYNC_RE.search(rest)
                if rm:
                    anchor = parse_log_line_utc(ts_str, tz_str)
                    pending_override = combine_date_time(anchor, rm.group(1))
                    n_resync += 1
                    continue

                em = EMITTED_RE.search(rest)
                if em:
                    label_hms = em.group(1)
                    if awaiting_reset is not None:
                        precise = awaiting_reset
                        awaiting_reset = None
                        pending_override = None
                    elif pending_override is not None:
                        precise = pending_override
                        pending_override = None
                    elif precise is not None:
                        precise = precise + timedelta(seconds=15.0)
                    else:
                        continue  # no anchor yet -- can't happen after first started line
                    floored = precise.replace(microsecond=0)
                    if floored.strftime("%H:%M:%S") != label_hms:
                        n_mismatch += 1
                    ts_field = floored.strftime("%y%m%d_%H%M%S")
                    if ts_field in label_to_precise and label_to_precise[ts_field] != precise:
                        raise SystemExit(
                            f"FATAL: ts_field collision during reconstruction: {ts_field!r} "
                            f"maps to both {label_to_precise[ts_field]!r} and {precise!r}. "
                            f"Ambiguous join -- refusing to proceed."
                        )
                    label_to_precise[ts_field] = precise

    if n_mismatch:
        print(f"[WARN] {n_mismatch} window(s) where the reconstructed cycleStart's floored "
              f"second disagreed with the log's own truncated 'cycle HH:MM:SS' label -- "
              f"reconstruction may have drifted from the real sequence.", file=sys.stderr)
    return label_to_precise, n_resync, n_restart


def session_reject_count(log_files: list[Path]) -> int | None:
    last = None
    for lf in log_files:
        with open(lf, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = REJECT_RE.search(line)
                if m:
                    last = int(m.group(1))
    return last


def group_by_ts(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["ts"], []).append(r)
    return out


def median_dt(rows: list[dict]) -> float | None:
    vals = [float(r["dt"]) for r in rows]
    return statistics.median(vals) if vals else None


def normalized_set(rows: list[dict]) -> tuple[set[str], dict[str, set[str]]]:
    norm_set: set[str] = set()
    provenance: dict[str, set[str]] = {}
    for r in rows:
        norm = normalize_hash_tokens(r["message"])
        norm_set.add(norm)
        provenance.setdefault(norm, set()).add(r["message"])
    return norm_set, provenance


def nearest_grid(precise: datetime) -> datetime:
    delta_s = (precise - SESSION_START).total_seconds()
    nearest_k = round(delta_s / 15.0)
    return SESSION_START + timedelta(seconds=15.0 * nearest_k)


def main() -> None:
    import json
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dt_population = json.loads(BASELINE_DT_POPULATION.read_text())["values"]
    print(f"Loaded arm-A session-wide DT population: n={len(dt_population)} "
          f"(SPEC.md 2.5 item 10's zero-free-parameter model; falsification_check.predict_recall)")

    print("=== Step 1: reconstruct true UTC per live cycle from the daemon log ===")
    label_to_precise, n_resync, n_restart = reconstruct_windows()
    print(f"  {len(label_to_precise)} distinct windows reconstructed; "
          f"{n_resync} resync events consumed; {n_restart} CycleFramer (re)starts seen.")

    print("=== Step 2: load live and reference (arm A, all 2,827 cycles) decode logs ===")
    live_rows = parse_all_txt(LIVE_ALL_TXT)
    ref_rows = parse_all_txt(BASELINE_ALL_TXT)
    live_by_ts = group_by_ts(live_rows)
    ref_by_ts = group_by_ts(ref_rows)
    print(f"  live: {len(live_rows)} decode rows across {len(live_by_ts)} distinct cycle labels")
    print(f"  reference: {len(ref_rows)} decode rows across {len(ref_by_ts)} distinct cycle labels")

    live_reject = session_reject_count(LOG_FILES)
    ref_reject = 73490  # qa/cycleframer-alignment-replay/_work/phase1b_run.log, arm-A baseline decode
    print(f"  hashTableRejectCount (11.6(b) guard): live={live_reject}, reference(arm A)={ref_reject}")

    print("=== Step 3: join each live cycle to its nearest true-UTC reference cycle, score ===")
    per_cycle = []
    n_no_precise = 0
    n_no_ref = 0
    n_low_ref = 0
    all_merges: list[tuple[str, str, list[str]]] = []

    for live_ts, live_group in live_by_ts.items():
        precise = label_to_precise.get(live_ts)
        if precise is None:
            n_no_precise += 1
            continue
        grid = nearest_grid(precise)
        ref_ts = grid.strftime("%y%m%d_%H%M%S")
        ref_group = ref_by_ts.get(ref_ts)
        if not ref_group:
            n_no_ref += 1
            continue
        if len(ref_group) < MIN_REF:
            n_low_ref += 1
            continue

        live_norm, live_prov = normalized_set(live_group)
        ref_norm, ref_prov = normalized_set(ref_group)
        for norm, originals in live_prov.items():
            if len(originals) > 1:
                all_merges.append((f"live {live_ts}", norm, sorted(originals)))
        for norm, originals in ref_prov.items():
            if len(originals) > 1:
                all_merges.append((f"ref {ref_ts}", norm, sorted(originals)))

        inter = live_norm & ref_norm
        recall = len(inter) / len(ref_norm)

        dt_live = median_dt(live_group)
        dt_ref = median_dt(ref_group)
        delta_live = dt_ref - dt_live  # SPEC.md section 6 step 3, corrected sign
        predicted = predict_recall(delta_live, dt_population)  # SPEC.md 2.5 item 10 model

        elapsed_s = (precise - SESSION_START).total_seconds()

        per_cycle.append({
            "live_ts": live_ts, "ref_ts": ref_ts, "precise_utc": precise.isoformat(),
            "elapsed_h": elapsed_s / 3600.0,
            "ref_n": len(ref_norm), "live_n": len(live_norm), "inter_n": len(inter),
            "recall": recall, "dt_live": dt_live, "dt_ref": dt_ref, "delta_live": delta_live,
            "predicted_recall": predicted, "residual": recall - predicted,
        })

    print(f"  scored {len(per_cycle)} cycles; excluded: no-reconstruction={n_no_precise}, "
          f"no-reference-cycle={n_no_ref}, |ref|<{MIN_REF}={n_low_ref}")

    if all_merges:
        print(f"\n[COLLISION] {len(all_merges)} hash-normalization merge(s) -- 11.6(a) guard FAILED:",
              file=sys.stderr)
        for ctx, norm, originals in all_merges[:20]:
            print(f"  {ctx}: {originals} -> {norm!r}", file=sys.stderr)
        raise SystemExit(
            f"FATAL (SPEC.md 7.4(b-i) / tasks.md 11.6(a)): {len(all_merges)} hash-token "
            f"collision(s). Refusing to report a figure until investigated."
        )
    print(f"  11.6(a) collision guard: 0 merges across {len(per_cycle)} scored cycles -- PASS.")

    if not per_cycle:
        raise SystemExit("FATAL: no cycles scored -- reconstruction or join is broken.")

    # ---- decile aggregation, matching the count-ratio findings doc's own bucketing ----
    session_end = max(datetime.fromisoformat(r["precise_utc"]) for r in per_cycle)
    span_h = (session_end - SESSION_START).total_seconds() / 3600.0
    decile_w = span_h / 10.0

    print(f"\n=== Step 4: per-decile delta_live vs. the stated falsifiable prediction ===")
    print(f"  session span used for deciles: {span_h:.2f} h (width {decile_w*60:.1f} min/decile)")
    header = (f"{'decile':>6} {'window':>17} {'n':>5} {'med recall':>10} {'med predicted':>14} "
              f"{'med residual':>13} {'med δ_live':>11} {'med |δ_live|':>13} {'predicted |δ|':>14}")
    print(header)

    # predicted |delta| by decile, from 2026-07-25-d001-live-path-decomposition-findings.md
    # section 4 (both branches carry the same magnitude; only the sign was previously unknown)
    predicted_abs = [0.30, 2.35, 3.0, 3.0, 2.40, 2.48, 2.46, 2.43, 2.53, 2.53]

    decile_rows = []
    for d in range(10):
        lo = SESSION_START + timedelta(hours=d * decile_w)
        hi = SESSION_START + timedelta(hours=(d + 1) * decile_w)
        members = [r for r in per_cycle
                   if lo <= datetime.fromisoformat(r["precise_utc"]) < hi
                   or (d == 9 and datetime.fromisoformat(r["precise_utc"]) == hi)]
        if not members:
            print(f"{d+1:>6} {lo.strftime('%H:%M')+'-'+hi.strftime('%H:%M'):>17} {0:>5}"
                  f" {'--':>10} {'--':>14} {'--':>13} {'--':>11} {'--':>13} {predicted_abs[d]:>14.2f}")
            continue
        recalls = [m["recall"] for m in members]
        predicteds = [m["predicted_recall"] for m in members]
        residuals = [m["residual"] for m in members]
        deltas = [m["delta_live"] for m in members]
        abs_deltas = [abs(x) for x in deltas]
        med_recall = statistics.median(recalls)
        med_predicted = statistics.median(predicteds)
        med_residual = statistics.median(residuals)
        med_delta = statistics.median(deltas)
        med_abs_delta = statistics.median(abs_deltas)
        decile_rows.append({
            "decile": d + 1, "window": f"{lo.strftime('%H:%M')}-{hi.strftime('%H:%M')}",
            "n": len(members), "median_recall": med_recall, "median_predicted_recall": med_predicted,
            "median_residual": med_residual, "median_delta_live": med_delta,
            "median_abs_delta_live": med_abs_delta, "predicted_abs_delta": predicted_abs[d],
        })
        print(f"{d+1:>6} {lo.strftime('%H:%M')+'-'+hi.strftime('%H:%M'):>17} {len(members):>5} "
              f"{med_recall:>10.4f} {med_predicted:>14.4f} {med_residual:>+13.4f} "
              f"{med_delta:>+11.2f} {med_abs_delta:>13.2f} {predicted_abs[d]:>14.2f}")

    # ---- session-wide summary ----
    all_recalls = [r["recall"] for r in per_cycle]
    all_predicted = [r["predicted_recall"] for r in per_cycle]
    all_residual = [r["residual"] for r in per_cycle]
    all_deltas = [r["delta_live"] for r in per_cycle]
    print(f"\nSession-wide: n={len(per_cycle)} median recall={statistics.median(all_recalls):.4f} "
          f"median predicted recall={statistics.median(all_predicted):.4f} "
          f"median residual={statistics.median(all_residual):+.4f}")
    print(f"              median δ_live={statistics.median(all_deltas):+.2f}s "
          f"median |δ_live|={statistics.median([abs(x) for x in all_deltas]):.2f}s")

    # ---- write raw per-cycle CSV (NFR-021: aggregate/DT/recall only, no message text) ----
    import csv
    out_csv = OUT_DIR / "per_cycle_alignment.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(per_cycle[0].keys()))
        wr.writeheader()
        wr.writerows(per_cycle)
    out_decile_csv = OUT_DIR / "decile_summary.csv"
    with open(out_decile_csv, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(decile_rows[0].keys()))
        wr.writeheader()
        wr.writerows(decile_rows)
    print(f"\n-> {out_csv}\n-> {out_decile_csv}")


if __name__ == "__main__":
    main()
