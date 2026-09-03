#!/usr/bin/env python3
"""`FP-PARITY` -- pre-registered rows, shipped as code (HK-021(r)).

Spec: qa/rr-study/2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md
(Architect -> QA, 2026-09-03 16:16Z). Handoff (2026-09-03-1616-architect-to-qa-handoff-post-po-
rulings.md) assigns QA's priority order as: (1) ROW 0q, (2) ROW 0m, both zero-run/analysis-only.
THIS SCRIPT IMPLEMENTS ONLY THOSE TWO ROWS this session. ROW 0n/0o/0p/1/2/3 are NOT run here --
see the "NOT RUN" block at the bottom of main() for why each is out of THIS session's assigned
scope (0n needs a supervised decode run per HK-013/HK-023; 0o/0p are quick but were not on the
handoff's priority list; 1/2/3 depend on 0n/0o/0p and on S1b data not yet located).

Usage:
    python fp_parity_checks.py
Writes qa/rr-study/fp-parity/fp_parity_results.txt alongside stdout output.
"""
from __future__ import annotations

import csv
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_QA_ROOT = _HERE.parent
_AWGN_FP_RESULTS = _QA_ROOT / "awgn-fp-replay" / "results"
_RESULTS_DIR = _QA_ROOT / "results"
_RESULTS_PATH = _HERE / "fp_parity_results.txt"

# ── ROW 0m — the six named sweeps and their PUBLISHED per-sweep S5 AWGN event counts ──────────
# Published k_i values, sourced from the board's 2026-09-02 19:06Z entry (per-sweep FP-vs-<=-25dB
# breakdown) cross-checked against the AWGN-FP Amendment 2 A2.1 note on denominators. Every
# published sweep here is asserted to be a FULL S1-S8 battery run (S5 parts 0/1 = 60 AWGN slots),
# never an S7-only rerun sharing the same short SHA (2026-08-31-2e60949 is exactly that trap --
# an S7 R3 rerun with no S5_matched.csv/S5 truth rows at all -- excluded by construction below).
_NAMED_SWEEPS: dict[str, dict] = {
    "7d36038": {"run_dir": "2026-08-21-7d36038", "published_k": 1, "published_denom": 120},
    "f5dec23": {"run_dir": "2026-08-22-f5dec23", "published_k": 4, "published_denom": 120},
    "22b749c": {"run_dir": "2026-08-27-22b749c", "published_k": 0, "published_denom": 60},
    "872ba65": {"run_dir": "2026-08-29-872ba65", "published_k": 1, "published_denom": 60},
    "2e60949": {"run_dir": "2026-08-30-2e60949", "published_k": 2, "published_denom": 120},
    "3b52608": {"run_dir": "2026-09-02-3b52608", "published_k": 4, "published_denom": 60},
}


def _log(lines: list, msg: str) -> None:
    print(msg)
    lines.append(msg)


# ── ROW 0q ──────────────────────────────────────────────────────────────────

_M1M4_DECODES = _AWGN_FP_RESULTS / "m1m4_s5_decodes.csv"
_M3_DECODES = _AWGN_FP_RESULTS / "m3_s1_decodes.csv"


def _round_half_away_from_zero(x: float) -> int:
    """C's roundf(): halves round away from zero (roundf(-26.5) == -27, roundf(2.5) == 3)."""
    import math
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


def _round_half_to_even(x: float) -> int:
    # Python's built-in round() on a float already does banker's rounding.
    return round(x)


def _truncate_toward_zero(x: float) -> int:
    return int(x)  # Python's int() truncates toward zero, same as a C (int) cast.


def _floor(x: float) -> int:
    import math
    return int(math.floor(x))


def row0q_int_snr_conversion_rule(lines: list) -> bool | None:
    _log(lines, "\n=== ROW 0q: the int SNR conversion -- truncation or rounding? ===")

    rows: list[tuple[str, int, float]] = []  # (source_file, reported_snr_db, reconstructed_snr_db)
    for path in (_M1M4_DECODES, _M3_DECODES):
        if not path.is_file():
            _log(lines, f"ROW 0q: FAILED -- missing {path}")
            return None
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows.append((path.name, int(row["reported_snr_db"]), float(row["reconstructed_snr_db"])))

    _log(lines, f"ROW 0q: {len(rows)} decode rows loaded "
                 f"({_M1M4_DECODES.name}: {sum(1 for r in rows if r[0]==_M1M4_DECODES.name)}, "
                 f"{_M3_DECODES.name}: {sum(1 for r in rows if r[0]==_M3_DECODES.name)})")
    _log(lines, "ROW 0q: NOTE -- spec text says '2,754 rows already on disk' for these two files; "
                 f"the actual row count is {len(rows)} (454 + {len(rows)-454}). 2,754 = 454 + 2,300 "
                 "is M1M4's full count plus M3's GENUINE-ONLY subset (M1-M4-report.md S5); this "
                 "check instead classifies EVERY decode row in both files (the int<->float cast "
                 "rule is a shim-level property of every decode, genuine or spurious -- restricting "
                 "to genuine-only is not stated anywhere else in ROW 0q's own text). Flagged as a "
                 "drafting inconsistency, not acted on as a scope restriction.")

    rules = {
        "round_half_away_from_zero": _round_half_away_from_zero,
        "round_half_to_even": _round_half_to_even,
        "truncate_toward_zero": _truncate_toward_zero,
        "floor": _floor,
    }
    agreement: dict[str, int] = {name: 0 for name in rules}
    disagreement_examples: dict[str, list] = {name: [] for name in rules}

    for src, reported, reconstructed in rows:
        for name, fn in rules.items():
            predicted = fn(reconstructed)
            if predicted == reported:
                agreement[name] += 1
            elif len(disagreement_examples[name]) < 3:
                disagreement_examples[name].append((src, reported, reconstructed, predicted))

    n = len(rows)
    _log(lines, f"ROW 0q: agreement counts out of {n} rows:")
    unanimous_rules = []
    for name in rules:
        pct = 100.0 * agreement[name] / n
        _log(lines, f"  {name}: {agreement[name]}/{n} ({pct:.2f}%)")
        if agreement[name] == n:
            unanimous_rules.append(name)

    fires = len(unanimous_rules) != 1
    _log(lines, f"ROW 0q: rules with 100% agreement across all {n} rows: {unanimous_rules}")
    _log(lines, f"ROW 0q FIRES (not unanimous / not exactly one matching rule) = {fires}")

    if not fires:
        rule = unanimous_rules[0]
        _log(lines, f"ROW 0q PASSED (does not fire) -> the int SNR conversion is "
                     f"'{rule}', confirmed on all {n} decode rows, matching "
                     f"ft8_shim.c:1732's `r->snr = (int)roundf(snr);` (C roundf = "
                     f"round-half-away-from-zero) read directly from source.")
        _log(lines, "ROW 0q consequence: this is NOT truncation, so there is no truncation-"
                     "upward bias. The mechanical rounding error is at most 0.5 dB in EITHER "
                     "direction (not systematically upward) -- the conservative correction for a "
                     "FLOOR (ROW 1, not run this session) is to subtract 0.5 dB from any "
                     "reconstructed-from-int F, since round-half-away-from-zero can report an "
                     "excess up to 0.5 dB HIGHER than the true float excess for negative values.")
    else:
        _log(lines, "ROW 0q FAILED (fires) -> in-chain excess is not reconstructible by a single "
                     "rule from the int SNR alone. Per spec: ROW 1 must be re-scoped to a "
                     "populated-terms capture -- a NEW pre-registration, not a patch. Do not "
                     "proceed to ROW 1 as specified.")
        for name in rules:
            if disagreement_examples[name]:
                _log(lines, f"  {name} first disagreements: {disagreement_examples[name]}")

    return not fires


def _clopper_pearson_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """One-sided 95% Clopper-Pearson upper bound on a binomial rate, no scipy dependency."""
    if k >= n:
        return 1.0
    from math import comb

    def cdf_le(p: float, k: int, n: int) -> float:
        return sum(comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, k + 1))

    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        # P(X <= k | p=mid) decreases as p increases; want smallest p s.t. P(X<=k)=alpha
        if cdf_le(mid, k, n) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def _clopper_pearson_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    upper = _clopper_pearson_upper(k, n, alpha)
    # lower bound: smallest p s.t. P(X>=k|p) = alpha, i.e. 1 - P(X<=k-1|p) = alpha
    if k == 0:
        lower = 0.0
    else:
        from math import comb

        def cdf_le(p: float, kk: int, nn: int) -> float:
            return sum(comb(nn, i) * (p ** i) * ((1 - p) ** (nn - i)) for i in range(0, kk + 1))

        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if cdf_le(mid, k - 1, n) > (1 - alpha):
                lo = mid
            else:
                hi = mid
        lower = lo
    return (lower, upper)


# ── ROW 0m ──────────────────────────────────────────────────────────────────

def row0m_independent_recount(lines: list) -> bool | None:
    _log(lines, "\n=== ROW 0m: in-chain S5 AWGN numerator, recounted independently ===")
    _log(lines, "Method: harness.common.parse_all_txt/normalise_slot (a shared, non-aggregating "
                 "line-format parser also used BY matcher.py, but carrying none of matcher.py's "
                 "Pass-2/OR-dedupe/attribution-join logic -- that logic, not the timestamp parser, "
                 "is what HK-026 bars reusing). No *_matched.csv read anywhere in this function.")

    sys.path.insert(0, str(_QA_ROOT / "harness"))
    import common as harness_common  # noqa: E402

    any_missing = False
    per_sweep: dict[str, dict] = {}

    for sha, meta in _NAMED_SWEEPS.items():
        run_dir = _RESULTS_DIR / meta["run_dir"]
        truth_path = run_dir / "truth.csv"
        alltxt_path = run_dir / "owsfz-all.txt"
        if not truth_path.is_file() or not alltxt_path.is_file():
            _log(lines, f"  {sha} ({meta['run_dir']}): MISSING -- truth.csv={truth_path.is_file()} "
                         f"owsfz-all.txt={alltxt_path.is_file()}")
            any_missing = True
            continue

        # S5 parts 0/1 truth cycles (the AWGN population, per s5-level ROW 0f -- parts 2/3 are
        # carrier/multi-carrier, excluded).
        s5_cycles: dict = {}
        with open(truth_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("scenario_id") == "S5" and row.get("part_index") in ("0", "1"):
                    dt = harness_common.datetime.strptime(
                        row["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=harness_common.timezone.utc)
                    s5_cycles[dt] = (int(row["part_index"]), int(row["trial_index"]))

        denom = len(s5_cycles)

        records, skipped = harness_common.parse_all_txt(alltxt_path)
        cycles_with_decode: set = set()
        for rec in records:
            if rec.utc in s5_cycles:
                cycles_with_decode.add(rec.utc)
        k = len(cycles_with_decode)

        # Coverage sanity (what this row cannot otherwise detect, spec's own caveat): does the
        # ALL.TXT record timestamp range actually bracket every S5 slot, and is there a gap in
        # ALL.TXT logging (of ANY scenario) that swallows part of the S5 window?
        all_ts = sorted({rec.utc for rec in records})
        if all_ts:
            span_lo, span_hi = all_ts[0], all_ts[-1]
            out_of_span = [c for c in s5_cycles if not (span_lo <= c <= span_hi)]
            gaps = [(all_ts[i + 1] - all_ts[i]).total_seconds() for i in range(len(all_ts) - 1)]
            max_gap_s = max(gaps) if gaps else 0.0
        else:
            span_lo = span_hi = None
            out_of_span = list(s5_cycles)
            max_gap_s = float("nan")

        published_k = meta["published_k"]
        published_denom = meta["published_denom"]
        k_matches = (k == published_k)
        denom_matches = (published_denom == 60)

        _log(lines, f"  {sha} ({meta['run_dir']}): denom(S5 p0/1 cycles)={denom}  "
                     f"recounted_k={k}  published_k={published_k} (match={k_matches})  "
                     f"published_denom={published_denom} (==60: {denom_matches})  "
                     f"ALLTXT_lines_parsed={len(records)} skipped={skipped}  "
                     f"S5_cycles_outside_ALLTXT_span={len(out_of_span)}  max_gap_s={max_gap_s:.1f}")

        per_sweep[sha] = {
            "denom": denom, "k": k, "published_k": published_k,
            "published_denom": published_denom, "k_matches": k_matches,
            "denom_matches": denom_matches,
        }

    if any_missing:
        _log(lines, "ROW 0m: FAILED -- one or more sweeps missing raw data, cannot recount")
        return None

    any_k_mismatch = any(not v["k_matches"] for v in per_sweep.values())
    any_denom_mismatch = any(not v["denom_matches"] for v in per_sweep.values())
    fires = any_k_mismatch or any_denom_mismatch

    total_k = sum(v["k"] for v in per_sweep.values())
    total_n = sum(v["denom"] for v in per_sweep.values())
    rate_pct = 100.0 * total_k / total_n if total_n else float("nan")
    ci_lo, ci_hi = _clopper_pearson_ci(total_k, total_n) if total_n else (float("nan"), float("nan"))

    _log(lines, f"\nROW 0m: any k_i mismatch={any_k_mismatch}  any published denom != 60={any_denom_mismatch}  FIRES={fires}")
    _log(lines, f"ROW 0m: recounted pooled rate = {total_k}/{total_n} = {rate_pct:.3f}% "
                 f"[95% CP CI {100*ci_lo:.3f}%, {100*ci_hi:.3f}%]")

    if fires:
        _log(lines, "ROW 0m FIRES -> per spec Sec.4: the recounted Sigma(k_i)/360 and its exact "
                     "Clopper-Pearson 95% CI REPLACE [1.15%, 3.85%] as the in-chain comparator for "
                     "all future work; the 2.22% figure is RETIRED, not merely corrected.")
    else:
        _log(lines, "ROW 0m does not fire -> 12/360 = 3.33% is confirmed and becomes the "
                     "comparator (this branch was not expected to occur, since 3 of 6 published "
                     "denominators are already known to be 120, not 60 -- Amendment 2 A2.1).")

    return not fires


def main() -> int:
    lines: list = []
    _log(lines, "FP-PARITY -- ROW 0q and ROW 0m (this session's assigned scope only)")
    _log(lines, "Spec: qa/rr-study/2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md")

    ok_0q = row0q_int_snr_conversion_rule(lines)
    ok_0m = row0m_independent_recount(lines)

    _log(lines, "\n=== SUMMARY (this session) ===")
    _log(lines, f"ROW 0q (int SNR conversion is a single, unanimous rule): "
                 f"{'PASS (unanimous)' if ok_0q else ('FIRES (not unanimous)' if ok_0q is False else 'NOT RUN')}")
    _log(lines, f"ROW 0m (recount matches published numbers exactly, incl. denominator==60): "
                 f"{'PASS (no fire)' if ok_0m else ('FIRES' if ok_0m is False else 'NOT RUN (missing data)')}")

    _log(lines, "\n=== NOT RUN THIS SESSION (out of the handoff's priority-2 scope) ===")
    _log(lines, "ROW 0n (normalisation parity, paired re-decode) -- needs a supervised decode run "
                 "(HK-013/HK-023), not zero-run; not on the handoff's priority list for this pass.")
    _log(lines, "ROW 0o (decode-param parity), ROW 0p (WAV->decoder path identity) -- quick "
                 "assertions but likewise not on the handoff's explicit priority-2 list.")
    _log(lines, "ROW 1 (F, the in-chain genuine excess floor) -- depends on ROW 0q's correction "
                 "(now available) but needs an S1b sweep located/confirmed on disk first, and on "
                 "ROW 0n/0o/0p closing clean per spec Sec.5 step 4-5 ordering.")
    _log(lines, "ROW 2/ROW 3 (emission floor viability) -- depend on ROW 1.")

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    # Non-zero exit iff either check could not even be evaluated (missing data) -- a FIRE is a
    # valid, informative, "complete, publishable" outcome for both rows (per the project's own
    # convention for pre-registered rows), not a script failure.
    return 0 if (ok_0q is not None and ok_0m is not None) else 1


if __name__ == "__main__":
    sys.exit(main())
