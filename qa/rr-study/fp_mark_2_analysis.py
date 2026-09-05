"""FP-MARK-2 -- four categorical, no-geo-instrument marking candidates.

Spec: qa/rr-study/2026-09-05-1823-architect-to-qa-spec-fp-mark-2-no-geo-candidates.md
Re-draft superseding FP-MARK's geographic candidate set (R-ENT retired, R-CONT/R-CQZ
suspended). No src/native change, no geographic classifier, no live run.

Reuses fp_mark_row0b_identifiability.py's verified ports UNCHANGED (do not re-port,
per the spec's own execution notes): sha256_of, is_grid_square, strip_portable_suffix,
is_candidate_callsign_token, extract_primary_callsign_token, RegionIndex,
REGION_TABLE_PATH.

New in this script, each cited by file:line, not invented:
  - strip_brackets / is_unresolved_hash_marker  <- QsoMessageParsing.cs:36-53
  - callsign_position_tokens()                  <- generalises Ft8Decoder.cs:885-908's own
                                                     tokens[0]/tokens[1] candidate checks to
                                                     BOTH positions instead of just the primary
  - linear_resolves()                           <- the untouched O(n) TryMatchPrefix scan
                                                     (CallsignRegionStore.cs:48-73), kept
                                                     alongside the binary-search RegionIndex so
                                                     the two can be mechanically diffed (spec Sec5,
                                                     banking the 18:20Z verification's requirement)
  - cp_interval()                                <- s5_standalone_rows.py:41-48, imported not
                                                     copied

NFR-021: reads real callsigns from artefacts/ (gitignored) and the 72 labelled synthetic FP
decodes (R&R-injected noise, not real traffic). Prints ONLY aggregate counts/rates. No
callsign, message, or grid value is written to any committed file.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "qa" / "rr-study"))
sys.path.insert(0, str(REPO_ROOT / "qa" / "rr-study" / "harness"))

from fp_mark_row0b_identifiability import (  # noqa: E402
    REGION_TABLE_PATH,
    RegionIndex,
    extract_primary_callsign_token,
    is_candidate_callsign_token,
    is_grid_square,
    sha256_of,
    strip_portable_suffix,
)
from common import parse_all_txt  # noqa: E402
from s5_standalone_rows import cp_interval  # noqa: E402

# ── Pins carried over from ROW 0b (2026-09-05-1809 result) -- asserted, not re-derived ──
EXPECTED_REGION_SHA256 = "bcf0bee2302c21c54fb66c6bcec3f6aa432352e424e32b3740413aa2658c98e6"
EXPECTED_CORPUS_SHA256 = {
    "artefacts/2026023_live run/OpenWSFZ ALL.TXT":
        "a19708dca89c560270c4bb57e06e3797f9f3ac5176870f48c0d171d7a735bb29",
    "artefacts/20260613_live run 1h40_items/OpenWSFZ ALL.TXT":
        "3ea09837d73220a463f381bef19f78511d37de04da12d811187a180d286e5a06",
    "artefacts/20260614_live_run/OpenWSFZ ALL.TXT":
        "925a0fed4afbd68d3c874c66378df5e5089a40125e81fc971b155256de0192c5",
    "artefacts/20260615_live_run/OpenWSFZ ALL.TXT":
        "2c1f696590f2450e450f75a106e2ff46c13d84232e9eb89edadcf02e88f98acc",
    "artefacts/20260622_live run/OpenWSFZ ALL.TXT":
        "bfc6a2c22b406400d3de6aa34b17a773b5c4bbbb940b40fa8547a2506013cd5d",
    "artefacts/20260706_live_run/OpenWSFZ ALL.TXT":
        "5255b9a0f53d7b1806a72aa53ea2ee563c56b934e760429c660ca95f47c3b6ae",
    "artefacts/20260706_live_run_2308/OpenWSFZ ALL.TXT":
        "8385bea2a84e1974dd558c9670c0a9ac7251e6562c2f997fc01913a27300d29c",
}

# ── The S5 runs backing the 72 windowed labelled FPs (HK-018) ──────────────────────────────
# NOT taken on a sub-agent's citation of a nonexistent doc ("2026-09-05-1311-...") -- that list
# omitted three non-zero June runs and included two runs that are actually zero, silently
# under-counting by exactly half (36 instead of 72). Verified instead by scanning EVERY
# S5_matched.csv directly under qa/rr-study/results/ (22 dirs), applying the same fp_in_window
# scoping to each, and summing: the grand total across all 22 is exactly 72, and exactly these
# 13 contribute a non-zero count (the other 9 are windowed to zero). This IS the "13 runs" the
# established fact table means. The script's own == 72 assertion below is what caught the
# original wrong list -- do not remove that assertion.
S5_RUN_DIRS = [
    "2026-06-20-6e821fa",
    "2026-06-20-8eea3c4",
    "2026-06-20-d40b4cd",
    "2026-07-04-a3738fc-f002-s5-n300",
    "d011-fp-recheck-2026-07-04",
    "2026-08-15-8d6e1b1",
    "2026-08-21-7d36038",
    "2026-08-22-f5dec23",
    "2026-08-29-872ba65",
    "2026-08-30-2e60949",
    "2026-09-02-3b52608",
    "2026-09-03-35378b9",
    "2026-09-05-10bbaad-s5-standalone-n300",
]

SEED = 20260905  # fixed, per §5's "sample explicitly and seed it"


# ── New helpers, cited ──────────────────────────────────────────────────────

def strip_brackets(token: str) -> str:
    """QsoMessageParsing.cs:36-41 StripBrackets."""
    if len(token) >= 2 and token[0] == "<" and token[-1] == ">":
        return token[1:-1]
    return token


def is_unresolved_hash_marker(s: str) -> bool:
    """QsoMessageParsing.cs:52-53 IsUnresolvedHashMarker."""
    return s == "" or all(c == "." for c in s)


def is_hash_token0(message: str) -> bool:
    """R-HASH's actual, verified definition: token 0 is bracket-wrapped -- i.e. it fails
    IsCandidateCallsignToken's own `token[0] != '<'` check (Ft8Decoder.cs:913), the same
    exclusion that already makes ExtractPrimaryCallsignToken/callsign_position_tokens() skip
    it. NOT literally IsUnresolvedHashMarker (all-dots-only) -- see the discrepancy note in
    the FP-MARK-2 result report: the spec cites IsUnresolvedHashMarker as R-HASH's instrument,
    but only this broader "any bracket, resolved-looking or not" definition reproduces the
    spec's own established 12/72=16.7% constant (verified: bracket-anywhere reproduces 21/72
    and bracket-in-token0 reproduces 12/72 exactly; the all-dots-only subset gives 18/72 and
    10/72 respectively). This is the design's own stated rationale too -- "no prefix in the
    addressee slot" is true for ANY bracketed token, not only the all-dots marker.
    """
    tokens = message.split(" ")
    if not tokens:
        return False
    return tokens[0].startswith("<")


def is_hash_token0_strict_unresolved(message: str) -> bool:
    """The literal IsUnresolvedHashMarker shape (all-dots only) -- kept for the disclosure
    breakdown, not used as R-HASH's flag."""
    tokens = message.split(" ")
    if not tokens:
        return False
    return tokens[0].startswith("<") and is_unresolved_hash_marker(strip_brackets(tokens[0]))


def callsign_position_tokens(message: str) -> list[str]:
    """Both callsign-position tokens, generalising Ft8Decoder.cs:885-908's own tokens[0]/
    tokens[1] candidate checks (IsCandidateCallsignToken) to collect BOTH positions instead
    of just the one ExtractPrimaryCallsignToken returns. A CQ message has exactly one
    (the caller); everything else has up to two (addressee, sender)."""
    tokens = message.split(" ")
    if not tokens:
        return []
    if tokens[0] == "CQ":
        if len(tokens) in (2, 3):
            cand = tokens[1]
        elif len(tokens) >= 4:
            cand = tokens[2]
        else:
            cand = None
        return [cand] if cand is not None and is_candidate_callsign_token(cand) else []
    positions = []
    if len(tokens) >= 1 and is_candidate_callsign_token(tokens[0]):
        positions.append(tokens[0])
    if len(tokens) >= 2 and is_candidate_callsign_token(tokens[1]):
        positions.append(tokens[1])
    return positions


def is_suffixed(token: str) -> bool:
    """A portable/rover suffix is present iff StripPortableSuffix would change the token."""
    return "/" in token


def linear_resolves(token: str, entries: list[dict]) -> bool:
    """Untouched O(n) port of CallsignRegionStore.cs:48-73 TryMatchPrefix -- kept deliberately
    separate from RegionIndex so the two can be mechanically diffed."""
    token = token.upper()
    best_len = -1
    for e in entries:
        ps, pe = e["prefixStart"], e["prefixEnd"]
        if len(ps) == 0 or len(pe) != len(ps):
            continue
        if len(token) < len(ps):
            continue
        candidate = token[: len(ps)]
        if candidate < ps or candidate > pe:
            continue
        if len(ps) > best_len:
            best_len = len(ps)
    return best_len >= 0


def r_unalloc_flag(message: str, index: RegionIndex) -> tuple[bool, bool]:
    """Returns (evaluable, flagged)."""
    positions = [strip_portable_suffix(t) for t in callsign_position_tokens(message)]
    if not positions:
        return False, False
    flagged = any(not index.resolves(p) for p in positions)
    return True, flagged


def r_suffix_flag(message: str) -> tuple[bool, bool]:
    positions = callsign_position_tokens(message)
    if len(positions) < 2:
        return False, False
    flagged = is_suffixed(positions[0]) and is_suffixed(positions[1])
    return True, flagged


# ── §1: pin assertion ───────────────────────────────────────────────────────

def assert_pins() -> tuple[dict, dict[str, str]]:
    region_sha = sha256_of(REGION_TABLE_PATH)
    if region_sha != EXPECTED_REGION_SHA256:
        print(f"FATAL: region table SHA256 changed since ROW 0b's pin.\n"
              f"  expected {EXPECTED_REGION_SHA256}\n  observed {region_sha}\n"
              f"Per the 18:09Z pin discipline: re-baseline, do not pool.", file=sys.stderr)
        sys.exit(1)
    corpus_paths = sorted(REPO_ROOT.glob("artefacts/*/OpenWSFZ ALL.TXT"))
    observed = {}
    for p in corpus_paths:
        rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        sha = sha256_of(p)
        observed[rel] = sha
        if rel not in EXPECTED_CORPUS_SHA256:
            print(f"FATAL: unexpected corpus file not in the pinned manifest: {rel}", file=sys.stderr)
            sys.exit(1)
        if EXPECTED_CORPUS_SHA256[rel] != sha:
            print(f"FATAL: corpus file changed since ROW 0b's pin: {rel}\n"
                  f"  expected {EXPECTED_CORPUS_SHA256[rel]}\n  observed {sha}", file=sys.stderr)
            sys.exit(1)
    if set(observed) != set(EXPECTED_CORPUS_SHA256):
        print("FATAL: pinned 7-corpus manifest membership changed.", file=sys.stderr)
        sys.exit(1)
    print("=== Pins asserted OK (unchanged since ROW 0b, 2026-09-05 18:09Z) ===")
    print(f"region table sha256 : {region_sha}")
    print(f"7-corpus manifest    : {len(observed)} files, all match")
    print()
    return observed, EXPECTED_CORPUS_SHA256


# ── §2: banked linear-vs-binary mechanical diff (spec Sec5, load-bearing before ROW 1) ──

def bank_linear_vs_binary_diff(index: RegionIndex, entries: list[dict], sample_tokens: list[str]) -> None:
    rng = random.Random(SEED)
    sample = sample_tokens if len(sample_tokens) <= 5000 else rng.sample(sample_tokens, 5000)
    mismatches = []
    for tok in sample:
        a = index.resolves(tok)
        b = linear_resolves(tok, entries)
        if a != b:
            mismatches.append(tok)
    print("=== Banked linear-vs-binary mechanical diff (seed={}) ===".format(SEED))
    print(f"sampled tokens : {len(sample)}")
    print(f"mismatches     : {len(mismatches)}")
    if mismatches:
        print(f"FATAL: binary-search reindex disagrees with the linear TryMatchPrefix port "
              f"on {len(mismatches)} token(s). Do not trust RATE results below.", file=sys.stderr)
        sys.exit(1)
    print("Binary-search reindex is behaviourally IDENTICAL to the linear scan on this sample.")
    print()


# ── §3: gather the 72 windowed labelled FP decodes (guards §0.2 windowing, faithfully) ──

def gather_windowed_fp_messages() -> list[str]:
    messages: list[str] = []
    per_run = []
    for run in S5_RUN_DIRS:
        csv_path = REPO_ROOT / "qa" / "rr-study" / "results" / run / "S5_matched.csv"
        df = pd.read_csv(csv_path)
        # Faithful reproduction of analyse.py:693-706's fp_in_window scoping.
        s5_truth_rows = df[df["false_positive"] == False]  # noqa: E712
        s5_cycles = set(s5_truth_rows["cycle_utc"].dropna().unique())
        sub = df[df["appraiser"] == "OpenWSFZ"]
        fp_sub = sub[sub["false_positive"] == True]  # noqa: E712
        fp_in_window = fp_sub[fp_sub["cycle_utc"].isin(s5_cycles)] if s5_cycles else fp_sub
        msgs = fp_in_window["message_text"].tolist()
        messages.extend(msgs)
        per_run.append((run, len(msgs)))
    return messages, per_run


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    observed_corpus, _ = assert_pins()
    region_data = __import__("json").loads(REGION_TABLE_PATH.read_text(encoding="utf-8"))
    entries = region_data["entries"]
    index = RegionIndex(entries)

    corpus_paths = sorted(REPO_ROOT.glob("artefacts/*/OpenWSFZ ALL.TXT"))

    # ---- Gather real decodes once; reused for the bank-diff sample AND for ROW 1 ----
    print("=== Loading real decodes (7 pinned corpora) ===")
    all_real_records = []
    for p in corpus_paths:
        records, _skipped = parse_all_txt(p)
        all_real_records.extend(records)
    print(f"total real decodes: {len(all_real_records)}")
    print()

    # ---- Banked linear-vs-binary diff, BEFORE any rate is computed ----
    sample_pool = []
    for rec in all_real_records:
        for t in callsign_position_tokens(rec.message):
            sample_pool.append(strip_portable_suffix(t))
    bank_linear_vs_binary_diff(index, entries, sample_pool)

    # ---- §3: the 72 windowed FP decodes ----
    fp_messages, per_run = gather_windowed_fp_messages()
    print("=== Windowed labelled FP decodes (13 runs, guards §0.2) ===")
    for run, n in per_run:
        print(f"  {run}: {n}")
    print(f"TOTAL: {len(fp_messages)} (established fact: 72)")
    if len(fp_messages) != 72:
        print("FATAL: reconstructed FP population does not match the established 72 -- "
              "windowing logic has drifted from analyse.py. STOP.", file=sys.stderr)
        sys.exit(1)
    print()

    # ---- FP-side (ROW 0a / ROW 2 base / ROW 3 coverage / ROW 4 inputs) ----
    fp_flags = {"R-UNALLOC": [], "R-SUFFIX": [], "R-HASH": [], "R-SOLO": []}
    fp_eval = {"R-UNALLOC": [], "R-SUFFIX": []}
    for msg in fp_messages:
        ev_u, fl_u = r_unalloc_flag(msg, index)
        ev_s, fl_s = r_suffix_flag(msg)
        fp_flags["R-UNALLOC"].append(fl_u if ev_u else False)
        fp_eval["R-UNALLOC"].append(ev_u)
        fp_flags["R-SUFFIX"].append(fl_s if ev_s else False)
        fp_eval["R-SUFFIX"].append(ev_s)
        fp_flags["R-HASH"].append(is_hash_token0(msg))
        fp_flags["R-SOLO"].append(True)  # cited constant (0/161 repeat ⇒ ~100% coverage), not re-derived

    n_fp = len(fp_messages)
    print("=== FP-side (labelled, n=72) ===")
    for cand in ("R-UNALLOC", "R-SUFFIX"):
        n_eval = sum(fp_eval[cand])
        n_flag_of_eval = sum(f for f, e in zip(fp_flags[cand], fp_eval[cand]) if e)
        pct = 100.0 * n_flag_of_eval / n_eval if n_eval else float("nan")
        cov = 100.0 * sum(fp_flags[cand]) / n_fp
        print(f"  {cand}: evaluable={n_eval}/{n_fp} ({100.0*n_eval/n_fp:.1f}%)  "
              f"ROW0a flag-of-evaluable={n_flag_of_eval}/{n_eval} ({pct:.1f}%)  "
              f"ROW3 coverage(of 72)={sum(fp_flags[cand])}/{n_fp} ({cov:.2f}%)")
    n_hash = sum(fp_flags["R-HASH"])
    n_hash_strict = sum(1 for m in fp_messages if is_hash_token0_strict_unresolved(m))
    print(f"  R-HASH: coverage(of 72)={n_hash}/{n_fp} ({100.0*n_hash/n_fp:.2f}%)  "
          f"[reproduces established 12/72=16.7% EXACTLY using 'token0 starts with <', "
          f"NOT the spec-cited IsUnresolvedHashMarker shape -- see discrepancy note in report. "
          f"Strict all-dots-only subset: {n_hash_strict}/{n_fp}]  ROW0a N/A per spec §4")
    print(f"  R-SOLO: coverage(of 72)=72/72 (100%)  [CITED constant, spec §1 -- NOT independently re-derived]")
    print()

    # ---- ROW 4: pairwise overlap on the FP population ----
    print("=== ROW 4 -- pairwise overlap on the 72 labelled FPs (descriptive only) ===")
    cands = ["R-UNALLOC", "R-SUFFIX", "R-HASH", "R-SOLO"]
    for a in cands:
        set_a = [i for i, f in enumerate(fp_flags[a]) if f]
        for b in cands:
            if a == b:
                continue
            set_b = set(i for i, f in enumerate(fp_flags[b]) if f)
            if not set_a:
                print(f"  of {a}'s 0 marks, {b} also marks: n/a (A marks nothing)")
                continue
            overlap = sum(1 for i in set_a if i in set_b)
            print(f"  of {a}'s {len(set_a)} marks, {b} also marks {overlap} "
                  f"({100.0*overlap/len(set_a):.1f}%)")
    print()

    # ---- Real-side ROW 1 (decode-level, CP95) ----
    print("=== ROW 1 -- false-flag rate on real traffic (decode-level, CP95) ===")
    n_total = len(all_real_records)
    real_eval = {"R-UNALLOC": 0, "R-SUFFIX": 0}
    real_flag = {"R-UNALLOC": 0, "R-SUFFIX": 0, "R-HASH": 0}
    for rec in all_real_records:
        ev_u, fl_u = r_unalloc_flag(rec.message, index)
        if ev_u:
            real_eval["R-UNALLOC"] += 1
            if fl_u:
                real_flag["R-UNALLOC"] += 1
        ev_s, fl_s = r_suffix_flag(rec.message)
        if ev_s:
            real_eval["R-SUFFIX"] += 1
            if fl_s:
                real_flag["R-SUFFIX"] += 1
        if is_hash_token0(rec.message):
            real_flag["R-HASH"] += 1

    def band(pct: float) -> str:
        if pct < 1.0:
            return "<1%"
        if pct < 10.0:
            return "1-10%"
        return ">=10%"

    for cand, n_eval, k in (
        ("R-UNALLOC", real_eval["R-UNALLOC"], real_flag["R-UNALLOC"]),
        ("R-SUFFIX", real_eval["R-SUFFIX"], real_flag["R-SUFFIX"]),
        ("R-HASH", n_total, real_flag["R-HASH"]),
    ):
        pct = 100.0 * k / n_eval
        lo, hi = cp_interval(k, n_eval)
        print(f"  {cand}: k={k} n={n_eval} rate={pct:.4f}% CP95=[{100*lo:.4f}%, {100*hi:.4f}%] "
              f"band={band(pct)}")
    print(f"  R-SOLO: CITED, not re-derived -- 46.6% [range 7.9-57.5% across the 7 sessions], "
          f"band=1-10%..>=10% depending on session (already established, spec §1)")
    print()
    print("Done. QA draws no verdict on which candidate ships (HK-015).")


if __name__ == "__main__":
    main()
