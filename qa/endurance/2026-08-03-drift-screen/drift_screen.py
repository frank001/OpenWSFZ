#!/usr/bin/env python3
"""Pre-registered drift screen for the ~6 h FT-991A session cap.

THIS SCRIPT *IS* THE PRE-REGISTERED CHECK (HK-021: "draft the check by writing the code
that would evaluate it"). Its thresholds are constants below, fixed in git before the run
starts. It prints exactly one verdict row. Nothing here is a judgement call at analysis
time.

WHAT IT ASKS
------------
The CycleFramer grid-realignment fix (`be5960a`, 2026-08-03) re-anchors the capture window
to the UTC grid at sample level every cycle. Its unit oracle proves 9 samples (0.75 ms)
worst case over a simulated 24 h at 48.4 ppm. This script asks the *live* question that a
unit oracle cannot: does the window stay on the grid on the real FT-991A / USB Audio CODEC
chain, past the ~13.7 h point where the defect previously reached FT8's ~2.36 s guard
interval and decoding collapsed entirely?

The ~6 h session cap on that chain is mitigation for that defect. It lifts as a decision by
the Captain, informed by this screen -- never as an assumption from a green unit test. The
previous ~12 h cap was lifted on the belief that PR #118 had fixed this; that belief cost
2,702 cycles in the +2 s regime.

WHY THERE IS A POSITIVE CONTROL (--expect-fail)
-----------------------------------------------
A green result answers whatever it was pointed at (HK-022). If this script is broken, or
pointed at the wrong directory, or its correlation never locks, it would report "no drift
detected" for a corpus that is *saturated* with drift. So before the screen may be believed,
it must be run with --expect-fail against a corpus captured BEFORE the fix
(`20260731_live_run_2004-8080`, 43.6 h, pre-be5960a, known ~0.18 s/h sawtooth). That run
MUST fire ROW 2 (FAIL). If it does not, the instrument is broken and the screen is VOID
regardless of what it says about the new corpus.

Note the pre-fix corpus can only ever serve as this control. It cannot screen the fix --
it was captured on the defective build, ~19 h before the fix existed.

SIGN CONVENTION
---------------
Inherited from measure_capture_alignment.ncc_full via measure_drift_8080_session.py, and
re-validated by self_test() before any real file is touched:

    lag_seconds = -L / SAMPLE_RATE      negative == OpenWSFZ's window opened LATER

NFR-021: reads only .wav PCM, cycle-archive.csv and daemon log FILENAMES. Never ALL.TXT,
never message text, never callsigns. ASCII-only output (HK-009).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

_REPLAY = Path(__file__).resolve().parents[2] / "cycleframer-alignment-replay"
sys.path.insert(0, str(_REPLAY))
import measure_capture_alignment as mca  # noqa: E402  -- reused, not reimplemented

SAMPLE_RATE = mca.SAMPLE_RATE

# ---------------------------------------------------------------------------
# PRE-REGISTERED CONSTANTS -- fixed in git before the run. Do not tune post hoc.
# ---------------------------------------------------------------------------

# Coverage. The screen is meaningless unless one uninterrupted uptime epoch crosses the
# point where the defect previously became total. 13.7 h is where 48.0 ppm reaches FT8's
# ~2.36 s guard interval; 14.0 h gives that a small margin.
MIN_EPOCH_HOURS = 14.0

# Statistical floor: below this many locked pairs in the decisive epoch, a slope fit is not
# worth reading.
MIN_LOCKED_PAIRS = 200

# Correlation lock. Pairs below this peak are excluded from every statistic -- an unlocked
# correlation carries no lag information, and including it would inject noise as signal.
PEAK_LOCK = 0.5

# FAIL thresholds. 0.173 s/h is the measured pre-fix defect signature (48.0 ppm); 0.05 s/h
# is well under a third of it, so a returning defect cannot hide beneath this bar. 0.5 s is
# the programme's healthy-window bar, retroactively justified by the measured 0.15-pt
# matched-parity cost of sub-0.5 s misalignment.
FAIL_SLOPE_S_PER_H = 0.05
FAIL_MAX_ABS_LAG_S = 0.5
FAIL_MAX_ABS_LABEL_S = 0.5

# PASS thresholds. 0.2 s is the bar the fix's own oracle is held to. 0.02 s/h is an order of
# magnitude under the defect signature, so a genuinely fixed framer clears it with room while
# a drifting one cannot. The fix predicts 9 samples / 0.75 ms OVER 24 H, i.e. a slope of
# 3.125e-5 s/h -- so this bar sits ~640x above the predicted drift, not the ~27x an earlier
# version of this comment claimed (that arithmetic read the prediction as 0.75 ms PER HOUR).
# Found and corrected 2026-08-04, after the ROW 5 PASS this constant governed -- the constant
# itself did NOT change, only this rationale. The error was conservative (it made the bar
# look tighter than it is), so it did not inflate the 2026-08-03 PASS. It does mean a screen
# built to catch PARTIAL regression should not inherit this constant unexamined: a 640x bar
# is a considerably blunter instrument than a 27x one. See
# 2026-08-04-1416-architect-to-qa-post-cap-lift-work-order.md secs 2-3 for the full context.
PASS_SLOPE_S_PER_H = 0.02
# GATE, registered 2026-08-04, not yet built -- do not extend this constant's use
# unexamined. PASS_MAX_ABS_LAG_S is checked against max(|lag|), a POINT MAXIMUM over all
# locked pairs in the decisive epoch, which is monotonically non-decreasing in sample count.
# On the 2026-08-03 18.96 h epoch it read 0.095 s -- 2.1x, the tightest margin of any
# statistic that run produced, where the slope-based statistics cleared by two orders of
# magnitude. A materially longer epoch raises this figure on noise alone, with a perfectly
# stationary window, and can drift the screen toward ROW 4 INCONCLUSIVE for no physical
# reason. Removing the ~6h FT-991A cap (2026-08-04) is what makes this live: the cap was the
# only thing preventing the long runs that would exercise this bar.
#   ASSERTION: any future drift screen over an epoch materially longer than 18.96 h must
#   re-derive this bar first. It may not be inherited as-is.
# Candidate fix (not decided, not implemented): split the two jobs this statistic does today
# -- keep a fixed absolute bar as a catastrophe detector on the FAIL row only (0.5 s is
# sample-size-insensitive in any realistic corpus), and replace the PASS row's point maximum
# with a high quantile, which is stable under growing N.
PASS_MAX_ABS_LAG_S = 0.2

# Epoch detection. A restart resets accumulated drift to zero, so epochs must be found even
# when the restart gap is short. Daemon log files are the primary signal (one per process
# start); the gap rule is a fallback for corpora whose logs were not gathered.
FALLBACK_GAP_SECONDS = 300

# Slope admissibility. A drift slope fitted over a stub epoch is not a measurement, it is
# noise divided by a small number: on the pre-fix control corpus a 6-cycle, 0.10 h epoch
# produced a label slope of -2.3544 s/h, ~13x the real device drift, purely from quantisation
# over too short a baseline. Left unguarded that would fire a FALSE ROW 2 FAIL on an
# otherwise clean run. Epochs below EITHER bar contribute no slope (their point statistics --
# max |lag|, max |label| -- still count in full, since those are measurements, not fits).
SLOPE_MIN_SPAN_H = 1.0
SLOPE_MIN_POINTS = 20

CYCLE_SECONDS = 15


def self_test() -> None:
    """Synthetic control for the sign convention. Aborts everything if it does not hold."""
    rng = np.random.default_rng(20260803)
    n = 180000
    known_delay = 1000  # OpenWSFZ starts 1000 samples (83.3 ms) later, by construction

    base = rng.standard_normal(n + known_delay + 2000)
    wsjtx_synth = base[1000:1000 + n]
    owsfz_synth = base[1000 + known_delay:1000 + known_delay + n]

    lag_limit = int(6 * SAMPLE_RATE)
    lags, corr = mca.ncc_full(owsfz_synth, wsjtx_synth, lag_limit)
    idx = int(np.argmax(corr))
    L = int(lags[idx])
    peak = float(corr[idx])
    lag_seconds = -L / SAMPLE_RATE

    print(f"[self-test] known delay {known_delay} samples "
          f"({known_delay / SAMPLE_RATE * 1000:.1f} ms), OpenWSFZ later by construction")
    print(f"[self-test] recovered L = {L}, peak corr = {peak:.4f}, "
          f"lag = {lag_seconds:+.4f} s (expected {-known_delay / SAMPLE_RATE:+.4f} s)")

    assert peak > 0.99, f"self-test peak correlation too low ({peak:.4f})"
    assert L == known_delay, (
        f"self-test FAILED: recovered {L} != known {known_delay}. Sign/magnitude convention "
        f"is NOT validated -- ABORTING, do not trust real-data output.")
    print("[self-test] PASSED -- negative lag == OpenWSFZ window opened later.\n")


def parse_cycle_name(name: str) -> datetime:
    """'260731_200415.wav' -> aware UTC datetime. No day-offset guessing."""
    stem = name[:-4] if name.lower().endswith(".wav") else name
    return datetime.strptime(stem, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)


def grid_offset_seconds(ts: datetime) -> float:
    """Signed offset of ts from the NEAREST 15 s UTC grid line, in seconds."""
    epoch = ts.replace(tzinfo=timezone.utc).timestamp()
    off = epoch % CYCLE_SECONDS
    return off - CYCLE_SECONDS if off > CYCLE_SECONDS / 2 else off


def read_epoch_starts(corpus: Path) -> list[datetime]:
    """Process-start times from daemon log filenames, e.g. openswfz-20260731T200425Z.log.

    A restart zeroes accumulated drift, so epoch boundaries must be detected even when the
    restart gap is far below FALLBACK_GAP_SECONDS -- which a 60 s supervisor cooldown makes
    the normal case. Gaps alone would silently merge two epochs and average a sawtooth into
    a flat line, hiding the very defect under screen.
    """
    starts: list[datetime] = []
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


def assign_epochs(times: list[datetime], epoch_starts: list[datetime]) -> list[int]:
    """Map each cycle time to an epoch index."""
    if epoch_starts:
        out = []
        for t in times:
            idx = 0
            for i, s in enumerate(epoch_starts):
                if s <= t:
                    idx = i
                else:
                    break
            out.append(idx)
        return out

    # Fallback: gap-based. Weaker -- see read_epoch_starts.
    print(f"[warn] no daemon logs found; falling back to >{FALLBACK_GAP_SECONDS}s gap "
          f"detection. Short-cooldown restarts will NOT be detected.\n")
    out, idx = [], 0
    for i, t in enumerate(times):
        if i and (t - times[i - 1]).total_seconds() > FALLBACK_GAP_SECONDS:
            idx += 1
        out.append(idx)
    return out


def load_labels(corpus: Path) -> dict[str, datetime]:
    """filename -> cycle_start_utc, from cycle-archive.csv.

    This is the FULL-COVERAGE drift measure and it needs no pairing at all. Since PR #118
    the emitted label honestly reports where the window actually opened, so its offset from
    the UTC grid IS the drift. Audio correlation corroborates it (and is what catches a
    label-only fix), but coverage and the primary curve must never depend on pairing --
    see pair_by_time().
    """
    path = corpus / "owsfz" / "cycle-archive.csv"
    labels: dict[str, datetime] = {}
    if not path.exists():
        print(f"[warn] no cycle-archive.csv at {path}; label check will be skipped\n")
        return labels
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("cycle_start_utc") or "").strip()
            if not raw:
                continue
            try:
                labels[row["filename"]] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
    return labels


def pair_by_time(ours: list[str], theirs: list[str]) -> dict[str, str]:
    """Pair our WAVs to WSJT-X's by NEAREST timestamp, not by identical filename.

    Filename equality looks like the obvious pairing and is actively harmful here. Once the
    window drifts past a second, our filename's second-field diverges from WSJT-X's and the
    pair silently vanishes from the intersection -- so exact-name matching discards precisely
    the drifted cycles that carry the signal, and biases the screen towards "no drift found".
    On the known-drifting pre-fix corpus it dropped 6,851 of 10,469 pairs (65%).

    Tolerance is half a cycle: beyond that the nearest neighbour would be a different
    transmission entirely.
    """
    theirs_ts = sorted((parse_cycle_name(n), n) for n in theirs)
    stamps = [t for t, _ in theirs_ts]
    out: dict[str, str] = {}
    for name in ours:
        t = parse_cycle_name(name)
        i = int(np.searchsorted(np.array([s.timestamp() for s in stamps]), t.timestamp()))
        best, best_d = None, None
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(theirs_ts):
                d = abs((theirs_ts[j][0] - t).total_seconds())
                if best_d is None or d < best_d:
                    best, best_d = theirs_ts[j][1], d
        if best is not None and best_d is not None and best_d <= CYCLE_SECONDS / 2:
            out[name] = best
    return out


def measure(corpus: Path, stride: int, lag_limit_s: float) -> list[dict]:
    """One row per ARCHIVED CYCLE (not per matched pair).

    Coverage and the label-drift curve span every archived cycle, so neither can be
    suppressed by a pairing failure. Audio lag is filled in on a strided subset.
    """
    ours_dir, wsjtx_dir = corpus / "owsfz" / "wav", corpus / "wsjt-x" / "wav"
    if not ours_dir.is_dir():
        raise SystemExit(f"ERROR: missing directory {ours_dir}")

    labels = load_labels(corpus)
    ours = sorted(p.name for p in ours_dir.glob("*.wav"))
    if not ours:
        raise SystemExit("ERROR: no OpenWSFZ WAVs -- wrong corpus, or archiving was off.")

    rows = [{"stem": n[:-4], "ts": parse_cycle_name(n), "name": n,
             "label_off_s": grid_offset_seconds(labels[n]) if n in labels else None,
             "lag_s": None, "lag_sub_s": None, "peak": None}
            for n in ours]
    print(f"Archived cycles (coverage basis): {len(rows)}")

    if not wsjtx_dir.is_dir():
        print("[warn] no WSJT-X WAVs -- audio corroboration skipped, label curve only.\n")
        return rows

    theirs = sorted(p.name for p in wsjtx_dir.glob("*.wav"))
    pairs = pair_by_time(ours, theirs)
    exact = len(set(ours) & set(theirs))
    print(f"WSJT-X WAVs: {len(theirs)} | paired by time: {len(pairs)} "
          f"(exact-filename would have paired only {exact})")

    sampled = [r for r in rows[::stride] if r["name"] in pairs]
    print(f"Stride {stride} -> correlating {len(sampled)} pairs\n")

    lag_limit = int(lag_limit_s * SAMPLE_RATE)
    for i, r in enumerate(sampled):
        a = mca.read_pcm(ours_dir / r["name"])
        b = mca.read_pcm(wsjtx_dir / pairs[r["name"]])
        n = min(len(a), len(b))
        if n < SAMPLE_RATE:
            continue
        lags, corr = mca.ncc_full(a[:n], b[:n], min(lag_limit, n - 1))
        idx = int(np.argmax(corr))
        r["lag_s"] = -int(lags[idx]) / SAMPLE_RATE
        r["lag_sub_s"] = -mca.refine(lags, corr, idx) / SAMPLE_RATE
        r["peak"] = float(corr[idx])
        if i % 50 == 0:
            print(f"  [{i + 1}/{len(sampled)}] {r['stem']}  lag={r['lag_s']:+.3f}s  "
                  f"peak={r['peak']:.3f}")
    return rows


def _slope(items: list[dict], key: str) -> float:
    """OLS slope in units-per-hour, or NaN if under-determined.

    NaN is the deliberate output for an inadmissible fit: verdict() treats NaN as "never
    trips a bar", so a stub epoch abstains rather than voting with a wild number.
    """
    if len(items) < SLOPE_MIN_POINTS:
        return float("nan")
    t0 = items[0]["ts"]
    hrs = np.array([(r["ts"] - t0).total_seconds() / 3600.0 for r in items])
    if hrs[-1] - hrs[0] < SLOPE_MIN_SPAN_H:
        return float("nan")
    val = np.array([r[key] for r in items], dtype=float)
    return float(np.polyfit(hrs, val, 1)[0])


def summarise_epochs(rows: list[dict]) -> list[dict]:
    times = [r["ts"] for r in rows]
    for r, e in zip(rows, assign_epochs(times, ROWS_EPOCH_STARTS)):
        r["epoch"] = e

    out = []
    for e in sorted({r["epoch"] for r in rows}):
        er = [r for r in rows if r["epoch"] == e]
        locked = [r for r in er if r["peak"] is not None and r["peak"] > PEAK_LOCK]
        labelled = [r for r in er if r["label_off_s"] is not None]
        audio_slope = _slope(locked, "lag_s")
        label_slope = _slope(labelled, "label_off_s")
        out.append({
            "epoch": e,
            # Span comes from every archived cycle in the epoch, so a pairing failure can
            # never shrink it into a false ROW 1 VOID.
            "span_h": (er[-1]["ts"] - er[0]["ts"]).total_seconds() / 3600.0,
            "n": len(er),
            "n_locked": len(locked),
            "audio_slope_s_per_h": audio_slope,
            "label_slope_s_per_h": label_slope,
            "ppm": (audio_slope / 3600.0) * 1e6 if audio_slope == audio_slope else float("nan"),
            "max_abs_lag_s": max((abs(r["lag_s"]) for r in locked), default=float("nan")),
            "max_abs_label_s": max((abs(r["label_off_s"]) for r in labelled), default=float("nan")),
        })
    return out


def _worst(epochs: list[dict], key: str) -> float:
    vals = [abs(e[key]) for e in epochs if e[key] == e[key]]  # NaN-safe
    return max(vals) if vals else float("nan")


def verdict(epochs: list[dict]) -> tuple[str, str]:
    """Evaluate the pre-registered rows in STRICT ORDER. First match wins; the rows are
    mutually exclusive and exhaustive. Returns (row_id, consequence).

    ORDERING IS LOAD-BEARING. ROW 2 (FAIL) is evaluated BEFORE ROW 3 (VOID on
    corroboration), because drift itself destroys pairing: as the window walks away from the
    grid, our WAVs stop lining up with WSJT-X's and locked pairs collapse. Ordered the other
    way, the worse the drift the more certainly the run would VOID instead of FAIL, and a
    catastrophically drifting corpus would exonerate itself. The label curve has full
    coverage and needs no pairing, which is why it alone can fire ROW 2.
    """
    if not epochs:
        return ("ROW 1 -- VOID (coverage)", "No epochs. NO VERDICT. The cap STAYS.")

    decisive = max(epochs, key=lambda e: e["span_h"])
    if decisive["span_h"] < MIN_EPOCH_HOURS:
        return ("ROW 1 -- VOID (coverage)",
                f"Longest uninterrupted uptime epoch is {decisive['span_h']:.2f} h, under the "
                f"{MIN_EPOCH_HOURS} h bar. NO VERDICT on the cap. The cap STAYS. "
                f"Re-run; do not reinterpret.")

    worst_audio_slope = _worst(epochs, "audio_slope_s_per_h")
    worst_label_slope = _worst(epochs, "label_slope_s_per_h")
    worst_lag = _worst(epochs, "max_abs_lag_s")
    worst_label = _worst(epochs, "max_abs_label_s")

    def over(v: float, bar: float) -> bool:
        return v == v and v >= bar  # NaN never trips a bar

    if (over(worst_audio_slope, FAIL_SLOPE_S_PER_H) or over(worst_label_slope, FAIL_SLOPE_S_PER_H)
            or over(worst_lag, FAIL_MAX_ABS_LAG_S) or over(worst_label, FAIL_MAX_ABS_LABEL_S)):
        return ("ROW 2 -- FAIL",
                f"Drift is present (worst audio slope {worst_audio_slope:+.4f} s/h, worst label "
                f"slope {worst_label_slope:+.4f} s/h, worst |lag| {worst_lag:.3f} s, worst "
                f"|label| {worst_label:.3f} s). The cap STAYS and "
                f"DEFECT-capture-clock-drift-silent-decode-loss.md REOPENS.")

    if decisive["n_locked"] < MIN_LOCKED_PAIRS:
        return ("ROW 3 -- VOID (corroboration)",
                f"Decisive epoch has {decisive['n_locked']} locked audio pairs, under the "
                f"{MIN_LOCKED_PAIRS} bar. The label curve is clean but cannot rule out a "
                f"label-only fix on its own. NO VERDICT. The cap STAYS.")

    if (over(worst_audio_slope, PASS_SLOPE_S_PER_H) or over(worst_label_slope, PASS_SLOPE_S_PER_H)
            or over(worst_lag, PASS_MAX_ABS_LAG_S)):
        return ("ROW 4 -- INCONCLUSIVE",
                f"Between the bars (worst audio slope {worst_audio_slope:+.4f} s/h, worst |lag| "
                f"{worst_lag:.3f} s). The cap STAYS. No reopen; escalate to the Architect.")

    return ("ROW 5 -- PASS",
            f"No drift detectable over {decisive['span_h']:.2f} h of uninterrupted uptime "
            f"(worst audio slope {worst_audio_slope:+.4f} s/h, worst |lag| {worst_lag:.3f} s, "
            f"worst |label| {worst_label:.3f} s). QA RECOMMENDS the Captain lift the ~6 h "
            f"FT-991A cap. The lift remains his decision, not this script's.")


ROWS_EPOCH_STARTS: list[datetime] = []


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-registered drift screen for the ~6h FT-991A cap.")
    ap.add_argument("--corpus", required=True, type=Path,
                    help="artefacts/<run> directory containing owsfz/ and wsjt-x/")
    ap.add_argument("--stride", type=int, default=10, help="measure every Nth matched pair")
    ap.add_argument("--lag-limit-s", type=float, default=6.0)
    ap.add_argument("--out", type=Path, default=None, help="CSV of the per-cycle curve")
    ap.add_argument("--expect-fail", action="store_true",
                    help="POSITIVE CONTROL: assert ROW 3 fires. Use against a PRE-FIX corpus "
                         "to prove the instrument can see drift at all. Exits non-zero if the "
                         "screen fails to detect known drift.")
    args = ap.parse_args()

    corpus = args.corpus.resolve()
    print("=" * 78)
    print("PRE-REGISTERED DRIFT SCREEN -- ~6 h FT-991A session cap")
    print(f"corpus : {corpus}")
    print(f"mode   : {'POSITIVE CONTROL (--expect-fail)' if args.expect_fail else 'SCREEN'}")
    print("=" * 78 + "\n")

    self_test()

    global ROWS_EPOCH_STARTS
    ROWS_EPOCH_STARTS = read_epoch_starts(corpus)
    print(f"Uptime epochs from daemon logs: {len(ROWS_EPOCH_STARTS)}"
          + (f" (first {ROWS_EPOCH_STARTS[0]:%Y-%m-%d %H:%M:%SZ})" if ROWS_EPOCH_STARTS else ""))

    rows = measure(corpus, args.stride, args.lag_limit_s)
    if not rows:
        raise SystemExit("ERROR: no usable pairs measured.")

    epochs = summarise_epochs(rows)

    print("\n" + "-" * 86)
    print(f"{'epoch':>5} {'span_h':>8} {'cycles':>8} {'locked':>7} {'audio_s/h':>11} "
          f"{'label_s/h':>11} {'ppm':>9} {'max|lag|':>9} {'max|lbl|':>9}")
    print("-" * 86)
    for e in epochs:
        print(f"{e['epoch']:>5} {e['span_h']:>8.2f} {e['n']:>8} {e['n_locked']:>7} "
              f"{e['audio_slope_s_per_h']:>+11.4f} {e['label_slope_s_per_h']:>+11.4f} "
              f"{e['ppm']:>+9.1f} {e['max_abs_lag_s']:>9.3f} {e['max_abs_label_s']:>9.3f}")
    print("-" * 86)

    def fmt(v, spec="+.5f"):
        return "" if v is None else format(v, spec)

    out_path = args.out or (Path(__file__).resolve().parent / f"drift_curve_{corpus.name}.csv")
    with open(out_path, "w", encoding="ascii", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cycle_stem", "epoch", "utc", "lag_s", "lag_subsample_s", "peak_corr",
                    "label_offset_s"])
        for r in rows:
            w.writerow([r["stem"], r["epoch"], r["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        fmt(r["lag_s"]), fmt(r["lag_sub_s"]), fmt(r["peak"], ".4f"),
                        fmt(r["label_off_s"])])
    print(f"\nPer-cycle curve: {out_path} ({len(rows)} rows)")

    row_id, consequence = verdict(epochs)
    print("\n" + "=" * 78)
    print(f"VERDICT: {row_id}")
    print("=" * 78)
    for line in consequence.split(". "):
        if line.strip():
            print("  " + line.strip().rstrip(".") + ".")
    print("=" * 78)

    if args.expect_fail:
        ok = row_id.startswith("ROW 2")
        print("\n[positive control] expected ROW 2 (FAIL) on a known-drifting pre-fix corpus: "
              + ("PASSED -- the instrument can see drift." if ok else
                 "FAILED -- the instrument did NOT detect known drift. The screen is VOID "
                 "regardless of what it reports on the new corpus."))
        return 0 if ok else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
