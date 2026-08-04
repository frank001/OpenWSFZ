#!/usr/bin/env python3
"""Task 1 (FP spec Sec.2) -- close Window 4 against be5960a, with a measurement.

PRE-REGISTERED RULE (commit before running; strict order, first match wins):

| row | condition                                                                | consequence               |
|-----|---------------------------------------------------------------------------|----------------------------|
| 1 VOID | either uptime window [0, 13.7h) or [13.7h, end] has < 200 cycles with both legs non-zero | no verdict; Window 4 stays open |
| 2 NOT CLOSED | median(ratio, after) < 0.80 * median(ratio, before)                | the cliff is still present => escalate; do not close anything |
| 3 CLOSED | otherwise                                                              | no cliff past 13.7h on the fixed build => close, per Sec.2.1 |

Method: on artefacts/20260803_live_run_1713/, decisive epoch (the longest uninterrupted uptime
epoch, identified from daemon-log filenames exactly as drift_screen.py does it), compute per-cycle
ratio = openwsfz_decodes / wsjtx_decodes for cycles where both legs are non-zero. Split at
uptime-since-epoch-start = 13.7h. WSJT-X sits behind the same splitter, so propagation is
common-mode and cancels -- this is a control, not a second measurement.

NFR-021: reads cycle-archive.csv (decode_count only, no message text) and ALL.TXT line COUNTS per
cycle timestamp (never message text/callsigns from ALL.TXT). ASCII-only output (HK-009).
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

# ---------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS
# ---------------------------------------------------------------------------
UPTIME_SPLIT_H = 13.7
MIN_CYCLES_PER_WINDOW = 200
NOT_CLOSED_RATIO = 0.80

CORPUS = Path("artefacts/20260803_live_run_1713")


def read_epoch_starts(corpus: Path) -> list[datetime]:
    starts = []
    for log in sorted((corpus / "owsfz").glob("*.log")):
        stem = log.stem
        if "-" not in stem:
            continue
        token = stem.rsplit("-", 1)[1]
        try:
            starts.append(datetime.strptime(token, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc))
        except ValueError:
            continue
    return sorted(starts)


def load_owsfz_counts(corpus: Path) -> dict[str, tuple[datetime, int]]:
    """stem -> (cycle_start_utc, decode_count) from cycle-archive.csv."""
    path = corpus / "owsfz" / "cycle-archive.csv"
    out = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            fn = row.get("filename", "")
            stem = fn[:-4] if fn.lower().endswith(".wav") else fn
            raw = (row.get("cycle_start_utc") or "").strip()
            if not raw or not stem:
                continue
            try:
                ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                cnt = int(row.get("decode_count") or 0)
            except ValueError:
                continue
            out[stem] = (ts, cnt)
    return out


def load_wsjtx_counts(corpus: Path) -> Counter:
    """stem -> line count, from wsjt-x/ALL.TXT first whitespace-delimited field."""
    path = corpus / "wsjt-x" / "ALL.TXT"
    c = Counter()
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            stem = line.split(None, 1)[0].strip()
            c[stem] += 1
    return c


def assign_epoch(ts: datetime, epoch_starts: list[datetime]) -> int:
    idx = 0
    for i, s in enumerate(epoch_starts):
        if s <= ts:
            idx = i
        else:
            break
    return idx


def main() -> int:
    corpus = CORPUS.resolve()
    print("=" * 78)
    print("TASK 1 -- Window 4 closure check against be5960a")
    print(f"corpus : {corpus}")
    print("=" * 78 + "\n")

    epoch_starts = read_epoch_starts(corpus)
    print(f"Uptime epochs from daemon logs: {len(epoch_starts)}")
    for i, s in enumerate(epoch_starts):
        print(f"  epoch {i}: starts {s:%Y-%m-%d %H:%M:%SZ}")

    owsfz = load_owsfz_counts(corpus)
    wsjtx = load_wsjtx_counts(corpus)
    print(f"\nowsfz cycle rows: {len(owsfz)}  wsjtx distinct cycle stems: {len(wsjtx)}")

    # Assign each owsfz cycle to an epoch and compute span per epoch.
    rows = []
    for stem, (ts, cnt) in owsfz.items():
        e = assign_epoch(ts, epoch_starts)
        rows.append({"stem": stem, "ts": ts, "owsfz": cnt, "wsjtx": wsjtx.get(stem, 0), "epoch": e})
    rows.sort(key=lambda r: r["ts"])

    epoch_ids = sorted({r["epoch"] for r in rows})
    spans = {}
    for e in epoch_ids:
        er = [r for r in rows if r["epoch"] == e]
        span_h = (er[-1]["ts"] - er[0]["ts"]).total_seconds() / 3600.0
        spans[e] = (span_h, er[0]["ts"], er[-1]["ts"], len(er))
        print(f"  epoch {e}: span {span_h:.2f} h, {len(er)} cycles, "
              f"{er[0]['ts']:%H:%M:%SZ} -> {er[-1]['ts']:%Y-%m-%d %H:%M:%SZ}")

    decisive_epoch = max(epoch_ids, key=lambda e: spans[e][0])
    span_h, e_start, e_end, n_cycles = spans[decisive_epoch]
    print(f"\nDecisive epoch: {decisive_epoch} (span {span_h:.2f} h, {n_cycles} cycles)")

    cutoff = e_start + timedelta(hours=UPTIME_SPLIT_H)
    print(f"Split point (epoch start + {UPTIME_SPLIT_H} h): {cutoff:%Y-%m-%d %H:%M:%SZ}")

    er = [r for r in rows if r["epoch"] == decisive_epoch]
    before = [r for r in er if r["ts"] < cutoff]
    after = [r for r in er if r["ts"] >= cutoff]

    before_both = [r for r in before if r["owsfz"] > 0 and r["wsjtx"] > 0]
    after_both = [r for r in after if r["owsfz"] > 0 and r["wsjtx"] > 0]

    print(f"\nBefore window [{e_start:%H:%M:%SZ}, {cutoff:%H:%M:%SZ}): "
          f"{len(before)} cycles total, {len(before_both)} with both legs non-zero")
    print(f"After window  [{cutoff:%H:%M:%SZ}, {e_end:%Y-%m-%d %H:%M:%SZ}]: "
          f"{len(after)} cycles total, {len(after_both)} with both legs non-zero")

    print("\n" + "-" * 60)
    print("PRE-REGISTERED RULE EVALUATION (strict order)")
    print("-" * 60)

    if len(before_both) < MIN_CYCLES_PER_WINDOW or len(after_both) < MIN_CYCLES_PER_WINDOW:
        print(f"\nROW 1 -- VOID (coverage)")
        print(f"before_both={len(before_both)}, after_both={len(after_both)}, "
              f"bar={MIN_CYCLES_PER_WINDOW}")
        print("NO VERDICT. Window 4 stays open.")
        return 1

    ratios_before = [r["owsfz"] / r["wsjtx"] for r in before_both]
    ratios_after = [r["owsfz"] / r["wsjtx"] for r in after_both]
    med_before = statistics.median(ratios_before)
    med_after = statistics.median(ratios_after)
    bar = NOT_CLOSED_RATIO * med_before

    print(f"\nmedian(ratio, before) = {med_before:.4f}  (n={len(ratios_before)})")
    print(f"median(ratio, after)  = {med_after:.4f}  (n={len(ratios_after)})")
    print(f"NOT-CLOSED bar = {NOT_CLOSED_RATIO} * median(before) = {bar:.4f}")

    if med_after < bar:
        print(f"\nROW 2 -- NOT CLOSED")
        print(f"median(after) {med_after:.4f} < bar {bar:.4f}")
        print("The cliff is still present. ESCALATE; do not close anything.")
        return 2

    print(f"\nROW 3 -- CLOSED")
    print(f"median(after) {med_after:.4f} >= bar {bar:.4f}")
    print("No cliff past 13.7h on the fixed build. Close, per Sec.2.1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
