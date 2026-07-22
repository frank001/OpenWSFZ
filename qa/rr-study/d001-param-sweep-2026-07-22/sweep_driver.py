"""D-001 runtime-parameter recall / false-positive Pareto sweep — scoring driver.

Orchestrates the scoring half of the sweep (the decode half is the C# harness,
D001ParamSweep). Reuses the study's existing scorers *verbatim* rather than
reimplementing them (work-order steps 13-14):

  * Recall arm  — imports classify_cochannel.py's parse / sig_key / freq_bin /
                  is_hashed / classify_delta / BANDS and the two low-SNR band
                  restriction. The one true WSJT-X-agreement algorithm Option B
                  established; this sweep stays comparable to it.
  * FP arm      — shells out to harness/matcher.py unmodified, once per grid point
                  per scenario (S5, S7), and reads back its <scenario>_matched.csv.

Subcommands:
  plan          Print TOTAL valid WAVs and the tune/validate split index.
  merge-shards  Concatenate per-point ALL.TXT files across process-shard output dirs.
  fp-corpus     Build canonical per-slot cycle_utc manifest + truth.csv for an FP scenario.
  score-recall  Score every grid point's recall on one split; emit recall CSV.
  score-fp      Score every grid point's S5+S7 false positives via matcher.py; emit FP CSV.
  assemble      Join recall + FP CSVs, compute Pareto frontier + verdict; emit the 45-row CSV.

All raw data (truth.csv, ALL.TXT, WAVs, per-point decode output) is local/git-ignored
under _work/ (NFR-021); only the aggregate 45-row CSV and report.md are committed.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Windows consoles default to cp1252 and cannot encode the '->' arrow / other glyphs used
# below (NFR-022, same guard harness/common.py applies). Reconfigure to UTF-8 with replace.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
QA_RR = HERE.parent                      # qa/rr-study
HARNESS = QA_RR / "harness"
COCHANNEL_DIR = QA_RR / "results" / "2026-07-07-b4bdf88-d001-cochannel-attribution"

sys.path.insert(0, str(COCHANNEL_DIR))
sys.path.insert(0, str(QA_RR))
import classify_cochannel as cc  # noqa: E402  (parse, sig_key, is_hashed, classify_delta, BANDS, ...)

# ── The 45-point grid (must match Program.cs's GridPoint enumeration + DirName) ──────────
K_VALUES = [5, 7, 10, 15, 20]
CORR_VALUES = [0.10, 0.15, 0.25]
NHARD_VALUES = [40, 60, 80]
BASELINE = (10, 0.10, 60)


def point_dir(k: int, corr: float, n: int) -> str:
    # Mirrors Program.cs GridPoint.DirName: $"k{K}_c{Corr:0.00}_n{NHard}"
    return f"k{k}_c{corr:.2f}_n{n}"


def grid_points() -> list[tuple[int, float, int]]:
    return [(k, c, n) for k in K_VALUES for c in CORR_VALUES for n in NHARD_VALUES]


BASELINE_DIR = point_dir(*BASELINE)

# ---------------------------------------------------------------------------
# plan — tune/validate split
# ---------------------------------------------------------------------------

def _sorted_wavs(wav_dir: Path) -> list[Path]:
    return sorted(wav_dir.glob("*.wav"), key=lambda p: p.name)


def cmd_plan(args: argparse.Namespace) -> None:
    wavs = _sorted_wavs(Path(args.wav_dir))
    total = len(wavs)
    half = total // 2
    print(f"TOTAL={total}")
    print(f"HALF={half}")   # tune = [0, half), validate = [half, total)
    print(f"TUNE_COUNT={half}")
    print(f"VALIDATE_COUNT={total - half}")


def cmd_split_ts(args: argparse.Namespace) -> None:
    """Write the tune/validate timestamp-stem lists from the same ordinal sort `plan`
    (and the C# harness) use, so the split index and the scoring restriction agree."""
    wavs = _sorted_wavs(Path(args.wav_dir))
    half = len(wavs) // 2
    tune = [w.stem for w in wavs[:half]]
    validate = [w.stem for w in wavs[half:]]
    Path(args.out_tune).write_text("\n".join(tune) + "\n")
    Path(args.out_validate).write_text("\n".join(validate) + "\n")
    print(f"split-ts: tune={len(tune)} → {args.out_tune}; validate={len(validate)} → {args.out_validate}")


# ---------------------------------------------------------------------------
# merge-shards — concatenate per-point ALL.TXT across process shards
# ---------------------------------------------------------------------------

def cmd_merge_shards(args: argparse.Namespace) -> None:
    root = Path(args.root)
    out = Path(args.out)
    all_txt_name = args.all_txt_name
    shard_dirs = sorted(d for d in root.glob("shard*") if d.is_dir())
    if not shard_dirs:
        sys.exit(f"no shard*/ dirs under {root}")
    n_lines = 0
    n_points = 0
    # Union of point dirs across shards
    point_names = set()
    for sd in shard_dirs:
        point_names.update(p.name for p in sd.iterdir() if p.is_dir())
    for pn in sorted(point_names):
        (out / pn).mkdir(parents=True, exist_ok=True)
        dest = out / pn / all_txt_name
        with open(dest, "w", encoding="ascii", newline="") as fout:
            for sd in shard_dirs:
                src = sd / pn / all_txt_name
                if src.exists():
                    txt = src.read_text(encoding="ascii", errors="replace")
                    fout.write(txt)
                    n_lines += txt.count("\n")
        n_points += 1
    print(f"merged {len(shard_dirs)} shards → {n_points} points, {n_lines} total lines → {out}")


# ---------------------------------------------------------------------------
# fp-corpus — build canonical per-slot cycle_utc for an FP scenario
# ---------------------------------------------------------------------------

# A synthetic FT8 cycle base far from any real session so timestamps never collide
# with the recall corpus. Exact 15-second boundaries (seconds always %15==0) so
# common.normalise_slot() is the identity on them.
_FP_BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _wav_name(scenario_id: str, part: int, trial: int, seed: int) -> str:
    # Mirrors run_scenario._dump_slot_wav's naming.
    return f"{scenario_id}_p{int(part):03d}_t{int(trial):03d}_s{int(seed)}.wav"


def cmd_fp_corpus(args: argparse.Namespace) -> None:
    wav_dir = Path(args.wav_dir)
    gen_truth = Path(args.gen_truth)          # the dry-run truth.csv (colliding wall-clock ts)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    wavs = _sorted_wavs(wav_dir)
    # Assign each WAV (=one slot) a unique canonical boundary — the offline analogue of
    # the distinct 15-s boundaries a live playback run would land each slot on.
    canon: dict[str, str] = {}
    for i, w in enumerate(wavs):
        ts = (_FP_BASE + timedelta(seconds=15 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        canon[w.name] = ts

    # manifest.csv: wav,cycle_utc  (consumed by D001ParamSweep --manifest)
    with open(out_dir / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["wav", "cycle_utc"])
        for name, ts in canon.items():
            wr.writerow([name, ts])

    # Canonical truth.csv: identical to the dry-run truth.csv except cycle_utc is rewritten
    # to each row's slot's canonical boundary (keyed by the row's own WAV name). All signal
    # rows of one slot share the WAV → share the boundary. Every other column is untouched.
    with open(gen_truth, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    missing = 0
    for r in rows:
        name = _wav_name(r["scenario_id"], r["part_index"], r["trial_index"], r["seed"])
        if name in canon:
            r["cycle_utc"] = canon[name]
        else:
            missing += 1
    with open(out_dir / "truth.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(rows)

    # Empty-but-well-formed WSJT-X side (no live WSJT run for the synthetic FP arm — matcher
    # computes false_positive from truth.csv vs owsfz-all.txt alone; work-order step 10).
    (out_dir / "wsjt-all.txt").write_text("", encoding="ascii")

    print(f"fp-corpus: {len(wavs)} slots, {len(rows)} truth rows, {missing} rows without a WAV "
          f"→ {out_dir}/manifest.csv, truth.csv, wsjt-all.txt")


# ---------------------------------------------------------------------------
# score-recall
# ---------------------------------------------------------------------------

def _parse_all_txt_cc(path: Path, source: str) -> list[dict]:
    """cc.parse but tolerant of a missing file (returns [])."""
    if not path.exists():
        return []
    return cc.parse(path, source)


def _neighbour_delta(miss_row: dict, slot_index: dict[str, list[dict]]):
    """Nearest same-slot neighbour Δf (Hz), or None if isolated — exactly as
    classify_session computes it (identity-excluding, snr-tiebroken)."""
    ts_m, freq_m = miss_row["ts"], miss_row["freq"]
    neighbours = [r for r in slot_index.get(ts_m, []) if r is not miss_row]
    if not neighbours:
        return None
    deltas = [(abs(freq_m - r["freq"]), r) for r in neighbours]
    deltas.sort(key=lambda t: (t[0], -t[1]["snr"]))
    return deltas[0][0]


def _recall_for_point(owsfz_rows: list[dict], wsjt_rows: list[dict]):
    """Return (total_wsjt, total_miss, miss_map) for one point, pooled over both low-SNR
    bands. miss_map: {sig_key: (band_name, best_delta)} for every classified miss.

    Faithful to classify_session: keys via sig_key, slot_index is the union of both apps'
    rows, isolation is 'no same-slot neighbour <= 50 Hz'."""
    owsfz_keys = {cc.sig_key(r): r for r in owsfz_rows}
    wsjt_keys = {cc.sig_key(r): r for r in wsjt_rows}
    owsfz_set = set(owsfz_keys)
    wsjt_set = set(wsjt_keys)
    wsjt_only = wsjt_set - owsfz_set
    wsjt_only_nonhashed = {k for k in wsjt_only if not cc.is_hashed(k[2])}

    slot_index: dict[str, list[dict]] = {}
    for r in owsfz_rows:
        slot_index.setdefault(r["ts"], []).append(r)
    for r in wsjt_rows:
        slot_index.setdefault(r["ts"], []).append(r)

    total_wsjt = 0
    total_miss = 0
    miss_map: dict[tuple, tuple] = {}
    for band_name, band_fn in cc.BANDS:
        band_wsjt_keys = {k for k, r in wsjt_keys.items()
                          if not cc.is_hashed(k[2]) and band_fn(r["snr"])}
        total_wsjt += len(band_wsjt_keys)
        band_misses = band_wsjt_keys & wsjt_only_nonhashed
        total_miss += len(band_misses)
        for k in band_misses:
            miss_map[k] = (band_name, _neighbour_delta(wsjt_keys[k], slot_index))
    return total_wsjt, total_miss, miss_map, owsfz_set


def cmd_score_recall(args: argparse.Namespace) -> None:
    wsjt_path = Path(args.wsjt)
    decoded_root = Path(args.decoded_dir)   # holds <point>/OpenWSFZ ALL.TXT
    split_ts = set(Path(args.split_ts).read_text().split())
    all_txt_name = args.all_txt_name

    wsjt_all = _parse_all_txt_cc(wsjt_path, "wsjt")
    wsjt_rows = [r for r in wsjt_all if r["ts"] in split_ts]

    # Baseline first — its miss set + per-miss class is the reference for per-class recovery.
    base_owsfz = _parse_all_txt_cc(decoded_root / BASELINE_DIR / all_txt_name, "owsfz")
    base_total, base_miss, base_miss_map, _ = _recall_for_point(base_owsfz, wsjt_rows)
    base_recall = 100.0 * (base_total - base_miss) / base_total if base_total else 0.0

    # Classify each baseline miss at the primary tight cutoff via the shared algorithm.
    base_class: dict[tuple, str] = {
        k: cc.classify_delta(delta, cc.PRIMARY_TIGHT_CUTOFF)
        for k, (band, delta) in base_miss_map.items()
    }
    base_class_totals = {c: sum(1 for v in base_class.values() if v == c)
                         for c in ("tight", "partial", "isolated")}

    points = grid_points()
    rows_out = []
    for (k, corr, n) in points:
        pd = point_dir(k, corr, n)
        owsfz = _parse_all_txt_cc(decoded_root / pd / all_txt_name, "owsfz")
        total_wsjt, total_miss, _mm, owsfz_set = _recall_for_point(owsfz, wsjt_rows)
        recall = 100.0 * (total_wsjt - total_miss) / total_wsjt if total_wsjt else 0.0
        # Per-class recovery of the baseline gap: baseline misses of class c now decoded here.
        recov = {c: 0 for c in ("tight", "partial", "isolated")}
        for mk, mc in base_class.items():
            if mk in owsfz_set:
                recov[mc] += 1
        recov_pct = {
            c: (100.0 * recov[c] / base_class_totals[c] if base_class_totals[c] else 0.0)
            for c in recov
        }
        rows_out.append({
            "point": pd, "k": k, "corr": f"{corr:.2f}", "nhard": n,
            "wsjt_total": total_wsjt, "miss": total_miss,
            "recall_pct": round(recall, 3),
            "recall_dpp": round(recall - base_recall, 3),
            "tight_recov_pct": round(recov_pct["tight"], 2),
            "partial_recov_pct": round(recov_pct["partial"], 2),
            "isolated_recov_pct": round(recov_pct["isolated"], 2),
            "tight_recov_n": recov["tight"],
            "partial_recov_n": recov["partial"],
            "isolated_recov_n": recov["isolated"],
        })

    out = Path(args.out)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        wr.writeheader()
        wr.writerows(rows_out)

    # Sidecar with the baseline anchors the report needs (class totals aren't in the CSV).
    import json
    meta = {
        "label": args.label,
        "baseline_recall_pct": round(base_recall, 3),
        "baseline_wsjt_total": base_total,
        "baseline_miss": base_miss,
        "baseline_class_totals": base_class_totals,
    }
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=2))

    print(f"score-recall[{args.label}]: baseline recall={base_recall:.2f}% "
          f"(wsjt_total={base_total}, miss={base_miss}); "
          f"baseline miss classes tight={base_class_totals['tight']} "
          f"partial={base_class_totals['partial']} isolated={base_class_totals['isolated']}")
    print(f"  → {out}")


# ---------------------------------------------------------------------------
# score-fp
# ---------------------------------------------------------------------------

def _run_matcher(run_dir: Path, scenario: str) -> tuple[int, int, int]:
    """Run matcher.py unmodified against run_dir; return (matched, misses, fp) for OpenWSFZ."""
    cmd = [sys.executable, str(HARNESS / "matcher.py"),
           "--run-dir", str(run_dir), "--scenario", scenario]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    matched_csv = run_dir / f"{scenario}_matched.csv"
    matched = misses = fp = 0
    with open(matched_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["appraiser"] != "OpenWSFZ":
                continue
            if r["false_positive"] == "True":
                fp += 1
            elif r["matched"] == "True":
                matched += 1
            else:
                misses += 1
    return matched, misses, fp


def cmd_score_fp(args: argparse.Namespace) -> None:
    s5 = Path(args.s5_corpus)   # dir with canonical truth.csv, wsjt-all.txt
    s7 = Path(args.s7_corpus)
    s5_decoded = Path(args.s5_decoded)   # <point>/owsfz-all.txt
    s7_decoded = Path(args.s7_decoded)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)

    def n_slots(truth_dir: Path) -> int:
        # distinct (part_index, trial_index) in truth.csv = number of rendered slots
        seen = set()
        with open(truth_dir / "truth.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                seen.add((r["part_index"], r["trial_index"]))
        return len(seen)

    def n_truth_rows(truth_dir: Path) -> int:
        with open(truth_dir / "truth.csv", newline="", encoding="utf-8") as fh:
            return sum(1 for _ in csv.DictReader(fh))

    s5_slots = n_slots(s5)
    s7_slots = n_slots(s7)
    s7_signals = n_truth_rows(s7)

    only = set(args.points.split(",")) if args.points else None

    rows_out = []
    for (k, corr, n) in grid_points():
        pd = point_dir(k, corr, n)
        if only is not None and pd not in only:
            continue
        row = {"point": pd, "k": k, "corr": f"{corr:.2f}", "nhard": n}

        # S5 — assemble a per-point run dir, run matcher unmodified.
        rd5 = work / f"{pd}__S5"
        rd5.mkdir(parents=True, exist_ok=True)
        shutil.copy(s5 / "truth.csv", rd5 / "truth.csv")
        shutil.copy(s5 / "wsjt-all.txt", rd5 / "wsjt-all.txt")
        shutil.copy(s5_decoded / pd / "owsfz-all.txt", rd5 / "owsfz-all.txt")
        _m5, _miss5, fp5 = _run_matcher(rd5, "S5")

        rd7 = work / f"{pd}__S7"
        rd7.mkdir(parents=True, exist_ok=True)
        shutil.copy(s7 / "truth.csv", rd7 / "truth.csv")
        shutil.copy(s7 / "wsjt-all.txt", rd7 / "wsjt-all.txt")
        shutil.copy(s7_decoded / pd / "owsfz-all.txt", rd7 / "owsfz-all.txt")
        m7, _miss7, fp7 = _run_matcher(rd7, "S7")

        row["s5_fp"] = fp5
        row["s5_fp_per_slot"] = round(fp5 / s5_slots, 5) if s5_slots else 0.0
        row["s7_fp"] = fp7
        row["s7_fp_per_slot"] = round(fp7 / s7_slots, 5) if s7_slots else 0.0
        row["s7_matched"] = m7
        row["s7_recovery_pct"] = round(100.0 * m7 / s7_signals, 3) if s7_signals else 0.0
        rows_out.append(row)

    out = Path(args.out)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        wr.writeheader()
        wr.writerows(rows_out)
    print(f"score-fp: S5 slots={s5_slots}, S7 slots={s7_slots}, S7 signals={s7_signals}")
    print(f"  → {out}")


# ---------------------------------------------------------------------------
# assemble — join recall + FP, Pareto frontier, verdict
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["point"]: r for r in csv.DictReader(fh)}


def cmd_assemble(args: argparse.Namespace) -> None:
    recall = _load_csv(Path(args.recall))
    fp = _load_csv(Path(args.fp))

    base = BASELINE_DIR
    base_s5 = float(fp[base]["s5_fp_per_slot"])
    base_s7 = float(fp[base]["s7_fp_per_slot"])

    merged = []
    for (k, corr, n) in grid_points():
        pd = point_dir(k, corr, n)
        r = recall[pd]
        f = fp[pd]
        s5 = float(f["s5_fp_per_slot"])
        s7 = float(f["s7_fp_per_slot"])
        recall_dpp = float(r["recall_dpp"])
        # §3.4/§3.5 two-sided rule: a "win" needs recall gain AND BOTH FP arms <= baseline.
        fp_ok = (s5 <= base_s5 + 1e-9) and (s7 <= base_s7 + 1e-9)
        is_win = fp_ok and recall_dpp > 1e-9
        merged.append({
            "point": pd, "k": k, "corr": f"{corr:.2f}", "nhard": n,
            "is_baseline": (k, corr, n) == BASELINE,
            "recall_pct": r["recall_pct"],
            "recall_dpp": r["recall_dpp"],
            "tight_recov_pct": r["tight_recov_pct"],
            "partial_recov_pct": r["partial_recov_pct"],
            "isolated_recov_pct": r["isolated_recov_pct"],
            "s5_fp_per_slot": f["s5_fp_per_slot"],
            "s5_fp": f["s5_fp"],
            "s5_fp_delta": round(s5 - base_s5, 5),
            "s7_fp_per_slot": f["s7_fp_per_slot"],
            "s7_fp": f["s7_fp"],
            "s7_recovery_pct": f["s7_recovery_pct"],
            "s7_fp_delta": round(s7 - base_s7, 5),
            "fp_within_baseline": fp_ok,
            "pareto_win": is_win,
        })

    out = Path(args.out)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(merged[0].keys()))
        wr.writeheader()
        wr.writerows(merged)

    wins = [m for m in merged if m["pareto_win"]]
    print(f"assemble → {out}")
    print(f"  baseline S5 fp/slot={base_s5}  S7 fp/slot={base_s7}")
    if not wins:
        print("  VERDICT: BASELINE DOMINATES — no point beats (10,0.10,60) on recall while "
              "holding both FP arms at-or-below baseline. Runtime knobs exhausted → Phase 2 / H7.")
    else:
        wins.sort(key=lambda m: float(m["recall_dpp"]), reverse=True)
        best = wins[0]
        print(f"  VERDICT: {len(wins)} candidate win(s). Best: {best['point']} "
              f"recall_dpp={best['recall_dpp']} (S5Δ={best['s5_fp_delta']}, S7Δ={best['s7_fp_delta']})")
        for m in wins:
            print(f"    WIN {m['point']}: +{m['recall_dpp']}pp  "
                  f"S5Δ{m['s5_fp_delta']} S7Δ{m['s7_fp_delta']}  "
                  f"isolated_recov={m['isolated_recov_pct']}%")


# ---------------------------------------------------------------------------
# render — grid markdown table + report token values (for report.md)
# ---------------------------------------------------------------------------

def cmd_render(args: argparse.Namespace) -> None:
    import glob
    import json
    grid = list(csv.DictReader(open(args.grid, encoding="utf-8")))
    meta = json.load(open(args.tune_meta, encoding="utf-8"))
    val = {r["point"]: r for r in csv.DictReader(open(args.validate, encoding="utf-8"))} \
        if args.validate and Path(args.validate).exists() else {}
    val_meta = json.load(open(args.validate_meta, encoding="utf-8")) \
        if args.validate_meta and Path(args.validate_meta).exists() else None

    # decoded / skipped from the tune shard logs
    decoded = skipped = 0
    for lg in glob.glob(args.tune_logs):
        for line in open(lg, encoding="utf-8", errors="replace"):
            if line.startswith("Done."):
                for tok in line.split():
                    if tok.startswith("decoded="):
                        decoded += int(tok.split("=")[1])
                    elif tok.startswith("skipped="):
                        skipped += int(tok.split("=")[1])
    # decoded above counts wavs-per-shard summed = distinct tune wavs (shards are disjoint)

    def g(row, k):
        return row[k]

    # ── grid markdown table ──
    hdr = ("| k | corr | nhard | recall % | Δpp | S5 fp/slot | S5 Δ | "
           "S7 fp/slot | S7 Δ | S7 rec% | win |")
    sep = "|" + "---|" * 11
    lines = [hdr, sep]
    for r in grid:
        star = "**" if r["is_baseline"] == "True" else ""
        win = "✅" if r["pareto_win"] == "True" else ("—" if float(r["recall_dpp"]) <= 0 else "trade")
        lines.append(
            f"| {star}{r['k']}{star} | {star}{r['corr']}{star} | {star}{r['nhard']}{star} | "
            f"{star}{r['recall_pct']}{star} | {r['recall_dpp']} | {r['s5_fp_per_slot']} | "
            f"{r['s5_fp_delta']} | {r['s7_fp_per_slot']} | {r['s7_fp_delta']} | "
            f"{r['s7_recovery_pct']} | {win} |")
    grid_table = "\n".join(lines)

    wins = [r for r in grid if r["pareto_win"] == "True"]
    base = next(r for r in grid if r["is_baseline"] == "True")
    ct = meta["baseline_class_totals"]

    print("===GRID_TABLE===")
    print(grid_table)
    print("===TOKENS===")
    toks = {
        "RECALL_DECODED": decoded,
        "RECALL_SKIPPED": skipped,
        "TUNE_COUNT": decoded,  # tune half size actually decoded
        "VALIDATE_COUNT": args.validate_count or "",
        "BASE_TUNE_RECALL": f"{meta['baseline_recall_pct']:.2f}%",
        "BASE_TUNE_TOTAL": meta["baseline_wsjt_total"],
        "BASE_TUNE_MISS": meta["baseline_miss"],
        "BASE_TIGHT": ct["tight"],
        "BASE_PARTIAL": ct["partial"],
        "BASE_ISOLATED": ct["isolated"],
        "N_WINS": len(wins),
        "BASE_S5_FP_SLOT": base["s5_fp_per_slot"],
        "BASE_S7_FP_SLOT": base["s7_fp_per_slot"],
        "BASE_S5_FP": base["s5_fp"],
        "BASE_S7_FP": base["s7_fp"],
        "BASE_S7_REC": base["s7_recovery_pct"],
    }
    if val_meta:
        toks["VAL_BASE_RECALL"] = f"{val_meta['baseline_recall_pct']:.2f}%"
    for k, v in toks.items():
        print(f"{k}={v}")
    if wins:
        wins.sort(key=lambda r: float(r["recall_dpp"]), reverse=True)
        b = wins[0]
        print(f"BEST_WIN_POINT={b['point']}")
        print(f"BEST_WIN_DPP={b['recall_dpp']}")
        print(f"BEST_WIN_ISOREC={b['isolated_recov_pct']}")
        if b["point"] in val:
            print(f"VAL_CAND_RECALL={val[b['point']]['recall_pct']}")
            print(f"VAL_CAND_DPP={val[b['point']]['recall_dpp']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan"); sp.add_argument("--wav-dir", required=True); sp.set_defaults(fn=cmd_plan)

    sp = sub.add_parser("split-ts")
    sp.add_argument("--wav-dir", required=True)
    sp.add_argument("--out-tune", required=True)
    sp.add_argument("--out-validate", required=True)
    sp.set_defaults(fn=cmd_split_ts)

    sp = sub.add_parser("merge-shards")
    sp.add_argument("--root", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--all-txt-name", required=True)
    sp.set_defaults(fn=cmd_merge_shards)

    sp = sub.add_parser("fp-corpus")
    sp.add_argument("--wav-dir", required=True)
    sp.add_argument("--gen-truth", required=True)
    sp.add_argument("--out-dir", required=True)
    sp.set_defaults(fn=cmd_fp_corpus)

    sp = sub.add_parser("score-recall")
    sp.add_argument("--wsjt", required=True)
    sp.add_argument("--decoded-dir", required=True)
    sp.add_argument("--split-ts", required=True, help="file with whitespace-separated split ts stems")
    sp.add_argument("--all-txt-name", default="OpenWSFZ ALL.TXT")
    sp.add_argument("--out", required=True)
    sp.add_argument("--label", default="")
    sp.set_defaults(fn=cmd_score_recall)

    sp = sub.add_parser("score-fp")
    sp.add_argument("--s5-corpus", required=True)
    sp.add_argument("--s7-corpus", required=True)
    sp.add_argument("--s5-decoded", required=True)
    sp.add_argument("--s7-decoded", required=True)
    sp.add_argument("--work", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--points", default=None, help="comma-separated point dirs (default: all 45)")
    sp.set_defaults(fn=cmd_score_fp)

    sp = sub.add_parser("assemble")
    sp.add_argument("--recall", required=True)
    sp.add_argument("--fp", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=cmd_assemble)

    sp = sub.add_parser("render")
    sp.add_argument("--grid", required=True, help="sweep_grid.csv from assemble")
    sp.add_argument("--tune-meta", required=True, help="recall_tune.csv.meta.json")
    sp.add_argument("--tune-logs", required=True, help="glob of tune shard Done. logs")
    sp.add_argument("--validate", default=None)
    sp.add_argument("--validate-meta", default=None)
    sp.add_argument("--validate-count", type=int, default=None)
    sp.set_defaults(fn=cmd_render)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
