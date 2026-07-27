#!/usr/bin/env python3
"""D-001 R.4b -- real-corpus decode-probability curve.

Measures P(we also decode it | WSJT-X-reported SNR) directly on real traffic, no synthetic-to-real
conversion anywhere. Arithmetic only on data already collected by B.1/B.1b/R.4 -- no new capture,
no rebuild, no decode wall-time.

Design: `2026-07-27-1522-architect-r4-ruling-and-r4b.md` Sec.4. Operationalised by
`2026-07-27-r4b-realworld-sensitivity-task-spec.md`.

NFR-021: reports aggregate counts/SNR-bin statistics only. Real corpus data (WSJT-X ALL.TXT) stays
inside git-ignored artefacts/; message text is never printed.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b1_jt9_ablation as b1
import b1b_second_corpus_ablation as b1b
import b2_synthetic_calibration as b2

REPO_ROOT = b1.REPO
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "d001_r4b_realworld_sensitivity")

DELTA_SNR = 2.625  # corrected value, confirmed independently -- see task spec Sec.0
HIGH_SNR_CUTOFF = 5.0  # "unambiguously strong" -- see task spec Sec.2 step 4


# -------------------- per-corpus row extraction --------------------

def corpus1_rows() -> list[dict]:
    wav_names = sorted(os.path.splitext(f)[0]
                        for f in os.listdir(b1.OURS_WAV_DIR) if f.endswith(".wav"))
    cycle_set = set(wav_names)
    wsjtx_rows = [r for r in b1.parse_all_txt(b1.WSJTX_ALL_TXT) if r["ts"] in cycle_set]
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(b1.OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    return _label(wsjtx_rows, ours_by_cycle)


def corpus2_rows() -> list[dict]:
    wav_names = sorted(os.path.splitext(f)[0]
                        for f in os.listdir(b1b.WAV_DIR) if f.endswith(".wav"))
    cycle_set = set(wav_names)
    wsjtx_rows = [r for r in b1.parse_all_txt(b1b.WSJTX_ALL_TXT) if r["ts"] in cycle_set]
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(b1b.OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    return _label(wsjtx_rows, ours_by_cycle)


def _label(wsjtx_rows: list[dict], ours_by_cycle: dict[str, set[str]]) -> list[dict]:
    out = []
    for r in wsjtx_rows:
        key = b1.normalize_hash_tokens(r["message"])
        hit = key in ours_by_cycle.get(r["ts"], set())
        out.append({"ts": r["ts"], "snr": round(float(r["snr"])), "hit": hit})
    return out


# -------------------- curve computation --------------------

def snr_curve(rows: list[dict]) -> list[dict]:
    by_bin: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # bin -> [hits, total]
    for r in rows:
        by_bin[r["snr"]][1] += 1
        if r["hit"]:
            by_bin[r["snr"]][0] += 1
    out = []
    for snr in sorted(by_bin):
        k, n = by_bin[snr]
        p, lo, hi = b2.wilson_interval(k, n)
        out.append({"snr_db": snr, "n": n, "k": k, "p": p, "ci_lo": lo, "ci_hi": hi})
    return out


def p_lookup(curve: list[dict], snr: float) -> float:
    """Nearest-bin lookup, falling back to nearest populated bin at the edges -- same convention
    as B.2's p_decode_from_curve."""
    best, best_d = None, None
    for row in curve:
        d = abs(row["snr_db"] - snr)
        if best is None or d < best_d:
            best, best_d = row, d
    return best["p"] if best else 0.0


def high_snr_asymptote(rows: list[dict], cutoff: float = HIGH_SNR_CUTOFF) -> dict:
    strong = [r for r in rows if r["snr"] >= cutoff]
    n = len(strong)
    k = sum(1 for r in strong if r["hit"])
    p, lo, hi = b2.wilson_interval(k, n)
    return {"cutoff": cutoff, "n": n, "k": k, "p": p, "ci_lo": lo, "ci_hi": hi}


def shift_model_estimate(rows: list[dict], curve: list[dict], delta_snr: float) -> dict:
    missed = [r for r in rows if not r["hit"]]
    expected = sum(p_lookup(curve, r["snr"] + delta_snr) for r in missed)
    return {"n_missed": len(missed), "expected_recovered": expected,
            "pct_of_missed": 100.0 * expected / max(1, len(missed))}


def cycle_density_split(rows: list[dict]) -> tuple[list[dict], list[dict], float]:
    per_cycle_n = defaultdict(int)
    for r in rows:
        per_cycle_n[r["ts"]] += 1
    densities = sorted(per_cycle_n.values())
    median_density = densities[len(densities) // 2]
    sparse_ts = {ts for ts, n in per_cycle_n.items() if n < median_density}
    dense_ts = {ts for ts, n in per_cycle_n.items() if n >= median_density}
    sparse_rows = [r for r in rows if r["ts"] in sparse_ts]
    dense_rows = [r for r in rows if r["ts"] in dense_ts]
    return sparse_rows, dense_rows, median_density


# -------------------- self-check --------------------

def self_check(rows: list[dict], expected_hit: int, expected_miss: int, label: str) -> bool:
    n_hit = sum(1 for r in rows if r["hit"])
    n_miss = sum(1 for r in rows if not r["hit"])
    ok = (n_hit == expected_hit and n_miss == expected_miss)
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: hit={n_hit} (expect {expected_hit}) "
          f"miss={n_miss} (expect {expected_miss})")
    return ok


# -------------------- reporting --------------------

def report_corpus(label: str, slug: str, rows: list[dict], expected_hit: int,
                   expected_miss: int) -> dict:
    print("=" * 70)
    print(label)
    print("=" * 70)
    ok = self_check(rows, expected_hit, expected_miss, label)
    if not ok:
        print(f"  [STOP] self-check failed for {label} -- not trusting this corpus's curve.")
        return {"label": label, "self_check_ok": False}

    curve = snr_curve(rows)
    print(f"\nP(decoded | SNR bin), whole dB:")
    for row in curve:
        print(f"  {row['snr_db']:+4d} dB  n={row['n']:4d} k={row['k']:4d} p={row['p']:6.1%} "
              f"ci=[{row['ci_lo']:.1%},{row['ci_hi']:.1%}]")

    asym = high_snr_asymptote(rows)
    print(f"\nHigh-SNR asymptote (>= {asym['cutoff']:+.0f} dB): "
          f"n={asym['n']} k={asym['k']} p={asym['p']:.1%} "
          f"ci=[{asym['ci_lo']:.1%},{asym['ci_hi']:.1%}]")

    shift = shift_model_estimate(rows, curve, DELTA_SNR)
    print(f"\nShift-model recovery estimate (curve shifted left {DELTA_SNR:.3f} dB): "
          f"expected={shift['expected_recovered']:.1f} of {shift['n_missed']} missed "
          f"({shift['pct_of_missed']:.1f}%)")

    sparse_rows, dense_rows, median_density = cycle_density_split(rows)
    sparse_curve = snr_curve(sparse_rows)
    dense_curve = snr_curve(dense_rows)
    print(f"\nCycle-density split (median density = {median_density} WSJT-X decodes/cycle):")
    print(f"  sparse: {len(sparse_rows)} rows across cycles below median")
    print(f"  dense : {len(dense_rows)} rows across cycles at/above median")
    print(f"  {'SNR':>5} {'P(sparse)':>10} {'n':>5}   {'P(dense)':>10} {'n':>5}")
    all_bins = sorted(set(r["snr_db"] for r in sparse_curve) | set(r["snr_db"] for r in dense_curve))
    sparse_by_bin = {r["snr_db"]: r for r in sparse_curve}
    dense_by_bin = {r["snr_db"]: r for r in dense_curve}
    density_rows_out = []
    for b_ in all_bins:
        sr = sparse_by_bin.get(b_)
        dr = dense_by_bin.get(b_)
        sp = f"{sr['p']:.1%}" if sr else "n/a"
        sn = sr["n"] if sr else 0
        dp = f"{dr['p']:.1%}" if dr else "n/a"
        dn = dr["n"] if dr else 0
        print(f"  {b_:+5d} {sp:>10} {sn:>5}   {dp:>10} {dn:>5}")
        density_rows_out.append({"snr_db": b_, "sparse_p": sr["p"] if sr else None,
                                   "sparse_n": sn, "dense_p": dr["p"] if dr else None,
                                   "dense_n": dn})

    result = {"label": label, "self_check_ok": True, "curve": curve, "asymptote": asym,
              "shift_model": shift, "median_density": median_density,
              "density_split": density_rows_out}
    with open(os.path.join(OUT_DIR, f"{slug}.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    return result


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    c1 = corpus1_rows()
    c2 = corpus2_rows()

    r1 = report_corpus("corpus 1 (40m, 68 cyc)", "corpus1", c1, expected_hit=1239,
                        expected_miss=789)
    print()
    r2 = report_corpus("corpus 2 (20m, 126 cyc)", "corpus2", c2, expected_hit=2437,
                        expected_miss=1934)

    print()
    print("=" * 70)
    print("SUMMARY vs the withdrawn step-model floor (R.4 findings Sec.3: 50/789, 120/1934)")
    print("=" * 70)
    for r, step_count, step_n in [(r1, 50, 789), (r2, 120, 1934)]:
        if not r.get("self_check_ok"):
            continue
        sm = r["shift_model"]
        print(f"{r['label']}: step-model floor = {step_count}/{step_n} "
              f"({100.0*step_count/step_n:.1f}%)  |  shift-model estimate = "
              f"{sm['expected_recovered']:.1f}/{sm['n_missed']} ({sm['pct_of_missed']:.1f}%)  |  "
              f"high-SNR asymptote = {r['asymptote']['p']:.1%}")

    print(f"\nAll outputs under {OUT_DIR}")


if __name__ == "__main__":
    main()
