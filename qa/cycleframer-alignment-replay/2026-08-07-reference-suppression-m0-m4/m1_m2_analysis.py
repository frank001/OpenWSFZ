#!/usr/bin/env python3
"""M1 + M2 -- offline, no playback, one shared data pull. Implements SS1.2, SS1.3, SS3, SS4
of `2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`.

Requires M0 to have run first (reads the preserved snapshot under
`artefacts/20260806_cross_decode_replay_2009/`, not the live growing AppData file -- M3/M4
append to the live file, so the M0 snapshot is the only stable ground truth for tonight's
five ANOVA runs).

NFR-021: message text is read only to build match keys (`normalize_hash_tokens`, same
convention as every other script in this directory) and is discarded immediately after --
never printed, never written to any output file. Only aggregate counts/stats are persisted.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "endurance"))
from anova_common import normalize_hash_tokens, parse_all_txt  # noqa: E402

LIVE_REPLAY_DIR = Path(__file__).resolve().parents[1] / "2026-08-06-live-cross-decode-replay"
sys.path.insert(0, str(LIVE_REPLAY_DIR))
from run_cross_decode_replay import WINDOW  # noqa: E402  -- reused, not re-declared (SS1.1)

import gates  # noqa: E402
import mapping  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
PRESERVED_DIR = REPO_ROOT / "artefacts" / "20260806_cross_decode_replay_2009"
CORPUS = REPO_ROOT / "artefacts" / "20260803_live_run_1713"
OUT_DIR = Path(__file__).resolve().parent
SLOT_SECONDS = 15
RUN_INDICES = [1, 2, 3, 4, 5]

WINDOW_CYCLES = [w[:-4] for w in WINDOW]  # strip ".wav"
WINDOW_CYCLE_SET = set(WINDOW_CYCLES)


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] M1M2: {msg}", flush=True)


def utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def map_run_to_corpus_cycles(run_idx: int, wsjtx_rows: list[dict]) -> list[dict]:
    """Returns the subset of `wsjtx_rows` (tonight's, from the preserved all-time ALL.TXT)
    that belong to this run's pass-1 window, each tagged with its corpus_cycle. Applies all
    four SS1.3 mandatory assertions before returning -- a failure here means the extraction
    is wrong and no ROW below may be evaluated, so these are real `assert`s, not warnings."""
    pw_path = PRESERVED_DIR / f"run{run_idx}" / "pass_windows.json"
    pw = json.loads(pw_path.read_text(encoding="utf-8"))
    pass1_start_iso = pw["pass1_wsjtx_source"][0]
    mapped, b0_epoch = mapping.map_rows_to_cycles(wsjtx_rows, pass1_start_iso, WINDOW_CYCLES)
    mapping.assert_mandatory(f"run{run_idx}", mapped, b0_epoch, WINDOW_CYCLES,
                              normalize_hash_tokens)

    log(f"run{run_idx}: {len(mapped)} pass-1 WSJT-X decodes mapped to 20/20 corpus cycles, "
        f"0 duplicates, exact grid -- all four SS1.3 assertions hold")
    return mapped


def median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return float("nan")
    mid = n // 2
    if n % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2.0


def run_m1(tonight_key_snr: dict[tuple, list[float]], archived_wsjtx_keys: set[tuple]) -> dict:
    from scipy.stats import mannwhitneyu

    shared_medians, new_medians = [], []
    for key, snrs in tonight_key_snr.items():
        m = median(snrs)
        (shared_medians if key in archived_wsjtx_keys else new_medians).append(m)

    if not shared_medians or not new_medians:
        return {
            "row": "ROW 4", "reason": "one of SHARED/NEW is empty -- cannot run Mann-Whitney",
            "n_shared": len(shared_medians), "n_new": len(new_medians),
        }

    delta_db = median(new_medians) - median(shared_medians)
    stat, p = mannwhitneyu(new_medians, shared_medians, alternative="two-sided")
    row = gates.m1_row(delta_db, p)
    return {
        "row": row, "consequence": gates.M1_CONSEQUENCE[row],
        "delta_db": delta_db, "p": float(p), "u_stat": float(stat),
        "median_new": median(new_medians), "median_shared": median(shared_medians),
        "n_new": len(new_medians), "n_shared": len(shared_medians),
    }


def run_m2(archived_owsfz_excl: set[tuple], archived_wsjtx_excl: set[tuple],
           tonight_union: set[tuple], tonight_intersection: set[tuple]) -> dict:
    n_owsfz_excl, n_wsjtx_excl = len(archived_owsfz_excl), len(archived_wsjtx_excl)
    if n_owsfz_excl != 279 or n_wsjtx_excl != 141:
        return {
            "verdict": "VOID",
            "reason": (f"could not reproduce the 2123 note's table from the archive: "
                       f"ORIG_OWSFZ_EXCL={n_owsfz_excl} (expected 279), "
                       f"ORIG_WSJTX_EXCL={n_wsjtx_excl} (expected 141). "
                       f"M2 is VOID pending Architect review; SS4.4 not evaluated."),
            "n_owsfz_excl": n_owsfz_excl, "n_wsjtx_excl": n_wsjtx_excl,
        }

    r_owsfz = len(archived_owsfz_excl & tonight_union) / n_owsfz_excl
    r_owsfz_all5 = len(archived_owsfz_excl & tonight_intersection) / n_owsfz_excl
    r_wsjtx_self = len(archived_wsjtx_excl & tonight_union) / n_wsjtx_excl

    validity = gates.m2_validity(r_wsjtx_self)
    if validity == "VOID":
        return {
            "verdict": "VOID",
            "reason": (f"R_wsjtx_self={r_wsjtx_self:.4f} < 0.80 -- replay does not "
                       f"reproduce 80% of WSJT-X's own original exclusive decodes; "
                       f"set-level absorption claims are unsafe. SS4.4 not evaluated. "
                       f"Escalate."),
            "r_wsjtx_self": r_wsjtx_self,
            "n_owsfz_excl": n_owsfz_excl, "n_wsjtx_excl": n_wsjtx_excl,
        }

    row = gates.m2_row(r_owsfz)
    residual = None
    if row == "ROW 2":
        residual = round((1 - r_owsfz) * n_owsfz_excl)
    gap_note = None
    if (r_owsfz - r_owsfz_all5) > 0.15:
        gap_note = (f"R_owsfz - R_owsfz_all5 = {r_owsfz - r_owsfz_all5:.4f} > 0.15 -- "
                    f"the recovered decodes are themselves marginal and only "
                    f"intermittently found across the 5 runs.")
    return {
        "row": row, "verdict": "EVALUATED", "consequence": gates.M2_CONSEQUENCE[row],
        "r_owsfz": r_owsfz, "r_owsfz_all5": r_owsfz_all5, "r_wsjtx_self": r_wsjtx_self,
        "n_owsfz_excl": n_owsfz_excl, "n_wsjtx_excl": n_wsjtx_excl,
        "residual_exclusive_count": residual, "intermittency_note": gap_note,
    }


def main() -> int:
    if not PRESERVED_DIR.exists():
        raise SystemExit(f"FATAL: {PRESERVED_DIR} does not exist -- run m0_preserve.py first")

    log(f"loading preserved WSJT-X all-time ALL.TXT from {PRESERVED_DIR}")
    wsjtx_all_rows = parse_all_txt(str(PRESERVED_DIR / "wsjtx-all-time" / "ALL.TXT"))
    log(f"{len(wsjtx_all_rows)} total rows in the preserved all-time file")

    per_run_mapped: dict[int, list[dict]] = {}
    for i in RUN_INDICES:
        per_run_mapped[i] = map_run_to_corpus_cycles(i, wsjtx_all_rows)

    # Pool by presence-in-any-run (SS3.2 step 3) with per-run SNR for the median-across-runs
    # (SS3.2 step 4).
    tonight_key_snr: dict[tuple, list[float]] = {}
    per_run_keys: dict[int, set[tuple]] = {}
    for i in RUN_INDICES:
        keys_this_run: set[tuple] = set()
        for m in per_run_mapped[i]:
            key = (m["corpus_cycle"], normalize_hash_tokens(m["message"]))
            tonight_key_snr.setdefault(key, []).append(m["snr"])
            keys_this_run.add(key)
        per_run_keys[i] = keys_this_run
    tonight_union = set.union(*per_run_keys.values())
    tonight_intersection = set.intersection(*per_run_keys.values())
    log(f"tonight pooled: {len(tonight_union)} distinct (cycle,msg) keys across 5 runs "
        f"(union); {len(tonight_intersection)} present in all 5 (intersection)")

    log("loading archived original corpus ALL.TXT (owsfz + wsjt-x)")
    archived_wsjtx_rows = [r for r in parse_all_txt(str(CORPUS / "wsjt-x" / "ALL.TXT"))
                            if r["ts"] in WINDOW_CYCLE_SET]
    archived_owsfz_rows = [r for r in parse_all_txt(str(CORPUS / "owsfz" / "ALL.TXT"))
                            if r["ts"] in WINDOW_CYCLE_SET]
    archived_wsjtx_keys = {(r["ts"], normalize_hash_tokens(r["message"]))
                            for r in archived_wsjtx_rows}
    archived_owsfz_keys = {(r["ts"], normalize_hash_tokens(r["message"]))
                            for r in archived_owsfz_rows}
    log(f"archived (this window): wsjtx={len(archived_wsjtx_keys)} keys, "
        f"owsfz={len(archived_owsfz_keys)} keys")

    m1_result = run_m1(tonight_key_snr, archived_wsjtx_keys)
    log(f"M1: {m1_result.get('row')} -- {m1_result.get('consequence', m1_result.get('reason'))}")

    archived_owsfz_excl = archived_owsfz_keys - archived_wsjtx_keys
    archived_wsjtx_excl = archived_wsjtx_keys - archived_owsfz_keys
    m2_result = run_m2(archived_owsfz_excl, archived_wsjtx_excl, tonight_union,
                        tonight_intersection)
    log(f"M2: {m2_result.get('row', m2_result.get('verdict'))} -- "
        f"{m2_result.get('consequence', m2_result.get('reason'))}")

    out = {
        "generated_utc": utc_stamp(),
        "window": WINDOW_CYCLES,
        "m1": m1_result,
        "m2": m2_result,
        "tonight_union_n": len(tonight_union),
        "tonight_intersection_n": len(tonight_intersection),
        "per_run_n": {str(i): len(per_run_keys[i]) for i in RUN_INDICES},
    }
    out_path = OUT_DIR / "m1_m2_result.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
