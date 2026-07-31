#!/usr/bin/env python3
"""Independent verification of the Architect's DT-drift method ruling (2026-07-31-1030) for
the 489135a corpus, before committing to the ~2.6h jt9 re-decode.

Reuses anova_common.parse_all_txt (no reimplementation). Computes median DT per elapsed hour
for both OpenWSFZ's own ALL.TXT and WSJT-X's own ALL.TXT (the flatness control), fits a simple
linear regression against elapsed hours, and reports the slope in ppm terms -- checking it
against the ruling's own quoted numbers (OpenWSFZ ~-0.1636 s/h / 45.4ppm; WSJT-X flat).

ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import statistics
import sys

sys.path.insert(0, r"D:\Projects\claude\OpenWSFZ\qa\endurance")
import anova_common as ac  # noqa: E402

OURS = r"D:\Projects\claude\OpenWSFZ\artefacts\20260728_live_run_2354-8080\owsfz\ALL.TXT"
WSJTX = r"D:\Projects\claude\OpenWSFZ\artefacts\20260728_live_run_2354-8080\wsjt-x\ALL.TXT"


def elapsed_hours(rows: list[dict], t0: datetime.datetime) -> list[tuple[float, float]]:
    out = []
    for r in rows:
        ts = ac.parse_cycle_ts(r["ts"])
        if ts is None:
            continue
        h = (ts - t0).total_seconds() / 3600.0
        out.append((h, r["dt"]))
    return out


def hourly_median(pairs: list[tuple[float, float]]) -> list[tuple[float, float, int]]:
    buckets: dict[int, list[float]] = {}
    for h, dt in pairs:
        buckets.setdefault(int(h), []).append(dt)
    return [(h, statistics.median(v), len(v)) for h, v in sorted(buckets.items())]


def fit_slope(binned: list[tuple[float, float, int]]) -> tuple[float, float]:
    """Least-squares fit of median DT vs bin hour (unweighted, matching the ruling's own
    'fit' language -- simple hour-bucket regression, not per-row)."""
    xs = [b[0] for b in binned]
    ys = [b[1] for b in binned]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else float("nan")
    intercept = mean_y - slope * mean_x
    return slope, intercept


def main() -> int:
    ours_rows = ac.parse_all_txt(OURS)
    wsjtx_rows = ac.parse_all_txt(WSJTX)
    print(f"ours rows: {len(ours_rows)}, wsjtx rows: {len(wsjtx_rows)}")

    all_ts = [ac.parse_cycle_ts(r["ts"]) for r in ours_rows + wsjtx_rows]
    all_ts = [t for t in all_ts if t is not None]
    t0 = min(all_ts)
    t1 = max(all_ts)
    print(f"session span: {t0} -> {t1} ({(t1 - t0).total_seconds()/3600:.2f} h)")

    ours_pairs = elapsed_hours(ours_rows, t0)
    wsjtx_pairs = elapsed_hours(wsjtx_rows, t0)

    ours_binned = hourly_median(ours_pairs)
    wsjtx_binned = hourly_median(wsjtx_pairs)

    print("\nOpenWSFZ median DT per elapsed hour (h, median_dt, n):")
    for h, med, n in ours_binned:
        print(f"  h={h:>3d}  dt={med:+.3f}  n={n}")

    print("\nWSJT-X median DT per elapsed hour (h, median_dt, n):")
    for h, med, n in wsjtx_binned:
        print(f"  h={h:>3d}  dt={med:+.3f}  n={n}")

    ours_slope, ours_intercept = fit_slope(ours_binned)
    wsjtx_slope, wsjtx_intercept = fit_slope(wsjtx_binned)

    ours_ppm = -ours_slope / 3600.0 * 1e6
    wsjtx_ppm = -wsjtx_slope / 3600.0 * 1e6

    print(f"\nOpenWSFZ fit: dt ~= {ours_intercept:+.4f} + ({ours_slope:+.4f})*elapsed_h "
          f"  ({ours_ppm:.1f} ppm slow)")
    print(f"WSJT-X   fit: dt ~= {wsjtx_intercept:+.4f} + ({wsjtx_slope:+.4f})*elapsed_h "
          f"  ({wsjtx_ppm:.1f} ppm 'slow' -- expect ~0, this is the flatness control)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
