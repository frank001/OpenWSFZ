#!/usr/bin/env python3
"""M3 window selection -- mechanical, no judgement. Implements SS5.2 of
`2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`.

Offline, no playback. Reads `qa/ARTEFACT_INVENTORY.md` (standing rule, HK-018) to confirm
the corpus row exists before touching anything, then enumerates every contiguous 20-cycle
window in `20260803_live_run_1713` for which all 20 WAVs exist on the WSJT-X side, excludes
low-yield windows, and picks the lowest-density survivor. Writes the density-leverage
contrast check (step 5) as the final gate -- if it fails, M3 must not run at all, and this
script says so rather than silently proceeding.

NFR-021: only ts tokens and integer counts are ever read/written; message text is never
touched by this script.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "endurance"))
from anova_common import parse_all_txt, parse_cycle_ts  # noqa: E402

LIVE_REPLAY_DIR = Path(__file__).resolve().parents[1] / "2026-08-06-live-cross-decode-replay"
sys.path.insert(0, str(LIVE_REPLAY_DIR))
from run_cross_decode_replay import WINDOW as BUSY_WINDOW  # noqa: E402

import gates  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS = REPO_ROOT / "artefacts" / "20260803_live_run_1713"
INVENTORY = REPO_ROOT / "qa" / "ARTEFACT_INVENTORY.md"
OUT_DIR = Path(__file__).resolve().parent
SLOT_SECONDS = 15
WINDOW_LEN = 20
# CORRECTED AGAIN 2026-08-07 (Architect, handoff SS5.1,
# 2026-08-06-2346-architect-to-qa-handoff-index-and-work-queue.md -- replaces spec SS5.2 AND
# the 2249 SS6.1 revision below). Both prior rules failed:
#   - original (spec SS5.2): minimise mean_combined subject to a wsjtx_total floor -- always
#     returns a window sitting exactly on the floor (it did: wsjtx_total=60 on the nose).
#   - first fix (2249 SS6.1): 10th-percentile by mean_combined among wsjtx_total>=100
#     survivors -- ignored the contrast constraint entirely; produced contrast=1.937 against
#     the required 3.0, so M3 could not even run.
# Third rule: filter candidates on BOTH contrast>=3.0 AND wsjtx_total>=60, then select the
# MAXIMUM wsjtx_total among survivors (objective on denominator stability, not fighting the
# constraint). Tie-break earliest UTC. QA-verified 2026-08-07: reproduces the handoff's
# figures exactly (window 260803_234000..260803_234445, wsjtx_total=105, owsfz_total=157,
# mean_combined=13.10, contrast=3.031) and is invariant to MIN_WSJTX_TOTAL at every floor
# from 40 to 100 -- confirming it is not an artifact of the floor's placement.
MIN_WSJTX_TOTAL = 60
MIN_CONTRAST = 3.0

# Established from tonight's 5-run ANOVA series and the original archive: owsfz=466,
# wsjtx=328 for the busy window -> combined=794, mean=39.7/cycle. Recomputed from the
# archive here rather than hardcoded, so a stale constant can never silently diverge from
# what the archive actually contains.


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] M3-select: {msg}", flush=True)


def confirm_inventory_row() -> None:
    if not INVENTORY.exists():
        raise SystemExit(f"FATAL: {INVENTORY} does not exist -- regenerate it "
                          f"(python qa/artefact_inventory.py) before selecting a window")
    text = INVENTORY.read_text(encoding="utf-8", errors="replace")
    if "20260803_live_run_1713" not in text:
        raise SystemExit(f"FATAL: {INVENTORY} has no row for 20260803_live_run_1713 -- "
                          f"regenerate it before proceeding (HK-018 standing rule)")
    log(f"confirmed corpus row for 20260803_live_run_1713 present in {INVENTORY.name}")


def cycle_counts(all_txt: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in parse_all_txt(str(all_txt)):
        counts[r["ts"]] = counts.get(r["ts"], 0) + 1
    return counts


def available_wav_ts(wav_dir: Path) -> list[str]:
    out = []
    for entry in os.scandir(wav_dir):
        if entry.is_file() and entry.name.endswith(".wav"):
            token = entry.name[:-4]
            if parse_cycle_ts(token) is not None:
                out.append(token)
    return sorted(out, key=lambda t: parse_cycle_ts(t))


def contiguous_20_windows(ts_list: list[str]) -> list[list[str]]:
    """All maximal 15s-spaced runs, sliced into every contiguous 20-length sub-window."""
    if not ts_list:
        return []
    runs: list[list[str]] = [[ts_list[0]]]
    for prev, cur in zip(ts_list, ts_list[1:]):
        prev_dt, cur_dt = parse_cycle_ts(prev), parse_cycle_ts(cur)
        if (cur_dt - prev_dt).total_seconds() == SLOT_SECONDS:
            runs[-1].append(cur)
        else:
            runs.append([cur])
    windows = []
    for run in runs:
        if len(run) < WINDOW_LEN:
            continue
        for start in range(0, len(run) - WINDOW_LEN + 1):
            windows.append(run[start:start + WINDOW_LEN])
    return windows


def main() -> int:
    confirm_inventory_row()

    wsjtx_counts = cycle_counts(CORPUS / "wsjt-x" / "ALL.TXT")
    owsfz_counts = cycle_counts(CORPUS / "owsfz" / "ALL.TXT")
    combined_counts = {ts: wsjtx_counts.get(ts, 0) + owsfz_counts.get(ts, 0)
                        for ts in set(wsjtx_counts) | set(owsfz_counts)}

    wsjtx_wav_ts = available_wav_ts(CORPUS / "wsjt-x" / "wav")
    log(f"{len(wsjtx_wav_ts)} WSJT-X-side WAVs on disk, spanning "
        f"{wsjtx_wav_ts[0]} .. {wsjtx_wav_ts[-1]}")

    candidates = contiguous_20_windows(wsjtx_wav_ts)
    log(f"{len(candidates)} contiguous 20-cycle candidate windows")

    busy_cycles = [w[:-4] for w in BUSY_WINDOW]
    busy_mean_combined = sum(combined_counts.get(ts, 0) for ts in busy_cycles) / WINDOW_LEN
    log(f"busy-window mean_combined={busy_mean_combined:.2f}/cycle (comparator for contrast)")

    # Filter on BOTH constraints together, then select the MAXIMUM wsjtx_total among
    # survivors (objective on denominator stability, not fighting the contrast constraint).
    # Tie-break earliest UTC. See the module docstring/constants above for why the two prior
    # rules (minimise subject to a floor; 10th-percentile ignoring contrast) both failed.
    survivors = []
    for w in candidates:
        wsjtx_total = sum(wsjtx_counts.get(ts, 0) for ts in w)
        if wsjtx_total < MIN_WSJTX_TOTAL:
            continue
        mean_combined = sum(combined_counts.get(ts, 0) for ts in w) / WINDOW_LEN
        contrast = (busy_mean_combined / mean_combined) if mean_combined > 0 else float("inf")
        if contrast < MIN_CONTRAST:
            continue
        survivors.append((wsjtx_total, w[0], w, mean_combined, contrast))

    if not survivors:
        run_m3 = False
        log(f"NO candidate window satisfies BOTH wsjtx_total>={MIN_WSJTX_TOTAL} AND "
            f"contrast>={MIN_CONTRAST} -- cannot run M3. Escalating: corpus does not offer "
            f"enough density leverage for this test.")
        result = {
            "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                              .strftime("%Y-%m-%d %H:%M:%S UTC"),
            "selected_window": None,
            "min_wsjtx_total_floor": MIN_WSJTX_TOTAL,
            "busy_window": busy_cycles,
            "busy_mean_combined": busy_mean_combined,
            "min_contrast_required": MIN_CONTRAST,
            "run_m3": run_m3,
            "n_candidate_windows": len(candidates),
            "n_surviving_windows": 0,
        }
        out_path = OUT_DIR / "m3_window_selection.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        log(f"wrote {out_path}")
        return 0

    log(f"{len(survivors)} windows survive BOTH constraints "
        f"(wsjtx_total>={MIN_WSJTX_TOTAL}, contrast>={MIN_CONTRAST})")

    survivors.sort(key=lambda t: (-t[0], t[1]))  # descending wsjtx_total, tie-break earliest
    sel_wsjtx_total, sel_start, sel_window, sel_mean_combined, contrast = survivors[0]
    sel_owsfz_total = sum(owsfz_counts.get(ts, 0) for ts in sel_window)
    log(f"selected window (max wsjtx_total among {len(survivors)} survivors): "
        f"{sel_window[0]} .. {sel_window[-1]}, wsjtx_total={sel_wsjtx_total}, "
        f"owsfz_total={sel_owsfz_total}, mean_combined={sel_mean_combined:.2f}/cycle, "
        f"contrast={contrast:.3f}")

    run_m3 = gates.m3_density_leverage_ok(contrast)

    result = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%d %H:%M:%S UTC"),
        "selected_window": sel_window,
        "selected_window_wav_files": [f"{ts}.wav" for ts in sel_window],
        "mean_combined": sel_mean_combined,
        "wsjtx_total": sel_wsjtx_total,
        "owsfz_total": sel_owsfz_total,
        "min_wsjtx_total_floor": MIN_WSJTX_TOTAL,
        "busy_window": busy_cycles,
        "busy_mean_combined": busy_mean_combined,
        "contrast": contrast,
        "min_contrast_required": MIN_CONTRAST,
        "run_m3": run_m3,
        "n_candidate_windows": len(candidates),
        "n_surviving_windows": len(survivors),
    }
    out_path = OUT_DIR / "m3_window_selection.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    log(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
