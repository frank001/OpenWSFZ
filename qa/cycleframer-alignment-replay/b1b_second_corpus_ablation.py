#!/usr/bin/env python3
"""D-001 B.1b -- second-corpus jt9 ablation replication.

Same instrument and conventions as b1_jt9_ablation.py (imported, not copied), new corpus:
artefacts/20260724_live_run_1607/ (20m, afternoon, 126 cycles, WSJT-X's own saved audio).
Per `2026-07-27-0015-architect-b3-addendum-second-corpus.md` Sec.3, Sec.4 and
`2026-07-27-b1b-second-corpus-task-spec.md`.

NFR-021: aggregate counts only on stdout; raw jt9 output under git-ignored artefacts/.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b1_jt9_ablation as b1  # reuse parse_all_txt, parse_jt9_stdout, normalize_hash_tokens,
                                # to_by_cycle, run_arm -- all generic over corpus paths already.

REPO = b1.REPO
BASE2 = os.path.join(REPO, "artefacts", "20260724_live_run_1607")
WAV_DIR = os.path.join(BASE2, "wav")
WSJTX_ALL_TXT = os.path.join(BASE2, "ALL.TXT")  # cumulative -- filtered by cycle_set below
OURS_LIVE_ALL_TXT = os.path.join(BASE2, "owsfx ALL.TXT")
OURS_OFFLINE_ALL_TXT = os.path.join(
    REPO, "artefacts", "d001_b1b_second_corpus", "our_offline",
    "k10_c0.10_n60", "k10_c0.10_n60", "ALL.TXT")
b1.SCRATCH_ROOT = os.path.join(REPO, "artefacts", "d001_b1b_second_corpus", "jt9")


def main() -> None:
    wav_names = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV_DIR) if f.endswith(".wav"))
    cycle_set = set(wav_names)
    assert len(wav_names) == 126, f"expected 126 matched cycles, got {len(wav_names)}"
    print(f"corpus: {len(wav_names)} matched cycles (second corpus, 20m, afternoon)")

    wsjtx_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(WSJTX_ALL_TXT)
                                     if r["ts"] in cycle_set)
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    ours_live_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(OURS_LIVE_ALL_TXT)
                                         if r["ts"] in cycle_set)
    wsjtx_total = sum(len(v) for v in wsjtx_by_cycle.values())
    ours_total = sum(len(v) for v in ours_by_cycle.values())
    ours_live_total = sum(len(v) for v in ours_live_by_cycle.values())
    print(f"anchor: live WSJT-X GUI (window-filtered, cumulative-file) = {wsjtx_total}")
    print(f"anchor: our decoder offline on WSJT-X's WAVs (same substrate as corpus 1) = {ours_total}")
    print(f"for continuity only (different substrate, live stream): our live = {ours_live_total}")

    missed_by_cycle: dict[str, set[str]] = {}
    missed_total = 0
    for ts, wset in wsjtx_by_cycle.items():
        m = wset - ours_by_cycle.get(ts, set())
        if m:
            missed_by_cycle[ts] = m
            missed_total += len(m)
    print(f"the miss population (WSJT-X-live minus our-offline, per cycle) = {missed_total}")
    print()

    arms = [("A0p_d3", 3), ("A1p_d2", 2), ("A2p_d1", 1)]
    print("Running arms (WSJT-X's own WAVs, single process per arm, chronological order)...")
    results = {}
    for label, depth in arms:
        results[label] = b1.run_arm(label, depth, WAV_DIR, wav_names)
    print()

    print("SCORING")
    hdr = f"{'arm':<8} {'total':>7} {'miss_cov':>9} {'miss_pct':>9} {'ovl_ours':>9} {'ovl_pct':>8}"
    print(hdr)
    print("-" * len(hdr))
    for label, _ in arms:
        by_cycle = results[label]
        total = sum(len(v) for v in by_cycle.values())
        miss_cov = sum(len(by_cycle.get(ts, set()) & m) for ts, m in missed_by_cycle.items())
        ovl_ours = sum(len(by_cycle.get(ts, set()) & ours_by_cycle.get(ts, set()))
                       for ts in cycle_set)
        print(f"{label:<8} {total:>7} {miss_cov:>9} {miss_cov / max(1, missed_total):>8.1%} "
              f"{ovl_ours:>9} {ovl_ours / max(1, ours_total):>7.1%}")

    a0_total = sum(len(v) for v in results["A0p_d3"].values())
    a1_total = sum(len(v) for v in results["A1p_d2"].values())
    a2_total = sum(len(v) for v in results["A2p_d1"].values())

    print()
    print("READING RULES (addendum Sec.4, fixed in advance):")
    r1 = a2_total / max(1, ours_total)
    print(f"  R1: A2'/our-offline = {a2_total}/{ours_total} = {r1:.3f}  "
          f"(corpus1=1.302; replicates if >1.10) -> {'FIRES' if r1 > 1.10 else 'does not fire'}")
    r2 = a0_total / max(1, wsjtx_total)
    print(f"  R2: A0'/live-reference = {a0_total}/{wsjtx_total} = {r2:.3f}  "
          f"(corpus1=1.005; replicates if 0.85-1.10) -> "
          f"{'REPLICATES' if 0.85 <= r2 <= 1.10 else 'does NOT replicate'}")
    d1_pct = results["A2p_d1"] and sum(len(results['A2p_d1'].get(ts, set()) & m)
                                        for ts, m in missed_by_cycle.items()) / max(1, missed_total)
    d3_pct = sum(len(results["A0p_d3"].get(ts, set()) & m)
                 for ts, m in missed_by_cycle.items()) / max(1, missed_total)
    print(f"  R3: miss coverage d1={d1_pct:.1%} d3={d3_pct:.1%}  "
          f"(corpus1=55.4%/98.0%; replicates if d3>85% and d1>35%) -> "
          f"{'REPLICATES' if (d3_pct > 0.85 and d1_pct > 0.35) else 'does NOT replicate'}")

    print(f"\n  T(3)-T(2) = {a0_total - a1_total}, T(2)-T(1) = {a1_total - a2_total}")


if __name__ == "__main__":
    main()
