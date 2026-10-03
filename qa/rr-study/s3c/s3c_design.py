"""S3c: a lean start-time EDGE guard for the R&R S1-S8 battery (spec 2026-10-02-1730, #194 part B step 2).

PRE-REGISTERED RULE AS CODE. The four points are picked MECHANICALLY from the accepted edge run's
OpenWSFZ results at -8 dB, never by eye; the edge run's result file is pinned by SHA-256 and the
design asserts every number the Architect's ruling (2026-10-02-2225) fixed:

    S3c-L90  L = E90(OpenWSFZ, -8)            late  (truncated at the slot end)
    S3c-L50  L = E50(OpenWSFZ, -8)            late   (E90 = E50  =>  moves outward: E50 + 0.25)
    S3c-E90  L = E90e(OpenWSFZ, -8)           early (early-armed, idle slot before it)
    S3c-E50  L = E50e(OpenWSFZ, -8)           early  (E90e = E50e =>  moves outward: E50e - 0.25)

r_ref(part, d) = the LOWER Wilson 95 % bound of decoder d's rate at that cell in the edge run (32
signals per cell).  k*(part, d) = the largest integer k with P(X < k | n = 32, p = r_ref) <= 0.01.
A row with k* = 0 cannot fail: it is labelled DESCRIPTIVE (the Architect's ruling names the
L +3.00 part; the code applies the same rule to every row, so a second such row is labelled too).

Layout (12 cycles, ~3 min): LATE block = 4 planted cycles (one continuous batch; each cycle holds 8
signals of S3c-L90 and 8 of S3c-L50 on a seeded split of the 16 frequency slots), then EARLY block
= (idle, planted) x 4 (each cycle 8 signals of S3c-E90 and 8 of S3c-E50).  -8 dB, 16 signals per
cycle on the edge test's 150 Hz slots, every text unique and Q-prefix synthetic (NFR-021).

Seeds: harness.common.compute_seed with 'S3c' as the scenario key (the battery's own formula);
every battery therefore plays IDENTICAL audio (the same convention as every other scenario).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RR = HERE.parent
EDGE = RR / "lateness-edge"
for p in (str(RR), str(EDGE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from harness.common import compute_seed  # noqa: E402
import design as ED  # noqa: E402  (the edge test's frozen constants; imported, never copied)

SCENARIO_ID = "S3c"
SNR_DB = -8
SIGNALS_PER_PART = 32
SIGNALS_PER_CYCLE = 16
PARTS_PER_CYCLE_SPLIT = 8                  # 8 signals of each of two parts per cycle
LATE_CYCLES = 4
EARLY_PLANTED = 4
TOTAL_CYCLES = LATE_CYCLES + 2 * EARLY_PLANTED      # 12
MIN_DISTINCT_SLOTS = 12
ALPHA_ONE_SIDED = 0.01
GRID_STEP_S = 0.25
WILSON_Z = 1.959964

# The pinned edge-run result (the Engineer's independent re-run, byte-identical to QA's first look).
EDGE_RESULT_RELPATH = "lateness-edge/results/analysis_result_engineer_rerun.json"
EDGE_RESULT_SHA256_PREFIX = "f248b7ffbc6a9141d0b0"
EDGE_RUN_COMMIT_FREEZE = "46994f57"          # freeze commit; on main since 286ca16b
EDGE_RUN_BUILD = "main b87529a3 (v0.54, shim 20260056), flag OFF"

# --- the Architect's ruling (2026-10-02-2225), as assertions ---------------------------------------
EXPECTED_L = (2.75, 3.00)
EXPECTED_E = (-1.75, -2.00)
assert TOTAL_CYCLES == 12 and 2 * LATE_CYCLES * PARTS_PER_CYCLE_SPLIT == 2 * SIGNALS_PER_PART
assert 2 * EARLY_PLANTED * PARTS_PER_CYCLE_SPLIT == 2 * SIGNALS_PER_PART
assert ED.FREQ_SLOTS_HZ[0] == 300 and ED.FREQ_SLOTS_HZ[-1] == 2550 and len(ED.FREQ_SLOTS_HZ) == 16


# --------------------------------------------------------------------------- statistics
def wilson_lower(k: int, n: int, z: float = WILSON_Z) -> float:
    if n == 0:
        return 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half)


def binom_cdf_lt(k: int, n: int, p: float) -> float:
    """P(X < k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 0.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0 if k <= n else 1.0
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, min(k, n + 1)))


def k_star(r_ref: float, n: int = SIGNALS_PER_PART, alpha: float = ALPHA_ONE_SIDED) -> int:
    """Largest integer k in 0..n with P(X < k | n, r_ref) <= alpha (k = 0 always qualifies)."""
    best = 0
    for k in range(0, n + 1):
        if binom_cdf_lt(k, n, r_ref) <= alpha:
            best = k
    return best


# --------------------------------------------------------------------------- point selection
def sha256_prefix_ok(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    assert h.startswith(EDGE_RESULT_SHA256_PREFIX), f"edge result changed: {h}"
    return h


def _edge_value(edges: dict, key: str) -> float:
    e = edges[key]["edge"]
    assert e is not None, f"{key}: no edge"
    return float(e)


def pick_points(edge_result: dict) -> dict:
    """The pre-registered rule (spec section 2). Returns {part_name: L}. OpenWSFZ at -8 dB."""
    ed = edge_result["edges"]["owsfz"]
    e90, e50 = _edge_value(ed, "E90(snr=-8)"), _edge_value(ed, "E50(snr=-8)")
    e90e, e50e = _edge_value(ed, "E90e(snr=-8)"), _edge_value(ed, "E50e(snr=-8)")
    for side in (e90, e50, e90e, e50e):
        assert ed  # edges beyond the grid would carry a label with '>' / '<'; guarded below
    labels = [ed[k]["label"] for k in ("E90(snr=-8)", "E50(snr=-8)", "E90e(snr=-8)", "E50e(snr=-8)")]
    assert not any(l.startswith((">", "<")) for l in labels), \
        "an edge beyond the grid: the spec's grid-end rule applies; QA must amend the labels, not guess"
    l90 = e90
    l50 = e50 if e50 != e90 else round(e50 + GRID_STEP_S, 2)
    p90 = e90e
    p50 = e50e if e50e != e90e else round(e50e - GRID_STEP_S, 2)
    return {"S3c-L90": l90, "S3c-L50": l50, "S3c-E90": p90, "S3c-E50": p50}


def cell_id(L: float) -> str:
    block = "LATE" if L >= 0 else "EARLY"
    return ED.cell_id(block, L, SNR_DB)


def reference_rows(edge_result: dict, points: dict) -> dict:
    """r_ref (lower Wilson of the edge run's cell) and k* for every (part, decoder)."""
    rows = {}
    for part, L in points.items():
        cid = cell_id(L)
        rows[part] = {"L": L, "cell": cid}
        for dec, name in (("owsfz", "OpenWSFZ"), ("wsjtx", "WSJT-X")):
            c = edge_result["cells"][dec][cid]
            assert c["n"] == SIGNALS_PER_PART
            r_ref = wilson_lower(int(c["k"]), SIGNALS_PER_PART)
            assert abs(r_ref - c["lo"]) < 1e-9, "Wilson lower bound differs from the edge run's own"
            ks = k_star(r_ref)
            rows[part][name] = {"edge_k": int(c["k"]), "r_ref": r_ref, "k_star": ks,
                                "descriptive": ks == 0}
    return rows


# --------------------------------------------------------------------------- the design
def _messages(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    seen: set[str] = set()
    out: list[str] = []

    def call() -> str:
        while True:
            c = f"Q{rng.randrange(10)}{rng.choice(letters)}{rng.choice(letters)}{rng.choice(letters)}"
            if c not in seen:
                seen.add(c)
                return c

    while len(out) < n:
        a, b = call(), call()
        g = f"{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.randrange(10)}{rng.randrange(10)}"
        out.append(f"{a} {b} {g}")
    assert len(set(out)) == n
    return out


def build_design(points: dict) -> dict:
    """Cycles 0..3 LATE (planted), then (idle, planted) x 4 EARLY.  Signals carry the edge test's
    keys (sig_id, cycle, slot, freq_hz, cell, block, L_s, snr_db, dt_s, text) so the edge test's
    matcher and renderer work on this design unchanged."""
    texts = _messages(4 * SIGNALS_PER_PART, compute_seed("S3c-text", 0, 0))
    ti = 0
    cycles: list[dict] = []
    signals: list[dict] = []
    part_names = {"LATE": ("S3c-L90", "S3c-L50"), "EARLY": ("S3c-E90", "S3c-E50")}
    for block, n_planted in (("LATE", LATE_CYCLES), ("EARLY", EARLY_PLANTED)):
        pa, pb = part_names[block]
        for pos in range(n_planted):
            if block == "EARLY":
                cycles.append({"index": len(cycles), "block": block, "planted": False, "signals": []})
            cyc = {"index": len(cycles), "block": block, "planted": True, "signals": []}
            slot_seed = compute_seed("S3c", 100 + (0 if block == "LATE" else 10) + pos, 0)
            perm = np.random.default_rng(slot_seed).permutation(SIGNALS_PER_CYCLE)
            for rank, slot in enumerate(perm.tolist()):
                part = pa if rank < PARTS_PER_CYCLE_SPLIT else pb
                L = points[part]
                sig = {"sig_id": len(signals), "cycle": cyc["index"], "slot": int(slot),
                       "freq_hz": ED.FREQ_SLOTS_HZ[int(slot)], "cell": part, "block": block,
                       "L_s": L, "snr_db": SNR_DB, "dt_s": ED.dt_for_L(L), "text": texts[ti]}
                ti += 1
                signals.append(sig)
                cyc["signals"].append(sig["sig_id"])
            cycles.append(cyc)
    audit(cycles, signals)
    return {"scenario": SCENARIO_ID, "points": points,
            "constants": {"fs": ED.FS, "slot_s": ED.SLOT_S, "offset_s": ED.OFFSET_S, "snr_db": SNR_DB,
                          "signals_per_part": SIGNALS_PER_PART, "signals_per_cycle": SIGNALS_PER_CYCLE,
                          "freq_slots_hz": list(ED.FREQ_SLOTS_HZ), "cycles": TOTAL_CYCLES,
                          "early_arm_s": ED.EARLY_ARM_S, "noise_cutoff_hz": 4700.0,
                          "late_planted": LATE_CYCLES, "early_planted": EARLY_PLANTED},
            "cycles": cycles, "signals": signals}


def audit(cycles: list[dict], signals: list[dict]) -> None:
    assert len(cycles) == TOTAL_CYCLES and len(signals) == 4 * SIGNALS_PER_PART
    by_part: dict[str, list[dict]] = {}
    for s in signals:
        by_part.setdefault(s["cell"], []).append(s)
    assert sorted(by_part) == ["S3c-E50", "S3c-E90", "S3c-L50", "S3c-L90"]
    for part, lst in by_part.items():
        assert len(lst) == SIGNALS_PER_PART, (part, len(lst))
        assert len({s["slot"] for s in lst}) >= MIN_DISTINCT_SLOTS, f"{part}: too few distinct slots"
        assert len({s["cycle"] for s in lst}) == (LATE_CYCLES if part[5] == "L" else EARLY_PLANTED)
    for c in cycles:
        if c["planted"]:
            sl = [signals[i] for i in c["signals"]]
            assert len(sl) == 16 and sorted(s["slot"] for s in sl) == list(range(16))
        else:
            assert not c["signals"]
    assert len({s["text"] for s in signals}) == len(signals)
    for s in signals:
        assert all(w[0] == "Q" for w in s["text"].split()[:2])
    for i, c in enumerate(cycles):
        if c["block"] == "EARLY" and c["planted"]:
            assert not cycles[i - 1]["planted"], "an early cycle needs an idle slot before it"


def canonical_json(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode("utf-8")


def load_points_and_reference():
    path = RR / EDGE_RESULT_RELPATH
    sha = sha256_prefix_ok(path)
    edge_result = json.loads(path.read_text(encoding="utf-8"))
    points = pick_points(edge_result)
    assert (points["S3c-L90"], points["S3c-L50"]) == EXPECTED_L, points
    assert (points["S3c-E90"], points["S3c-E50"]) == EXPECTED_E, points
    return points, reference_rows(edge_result, points), sha


if __name__ == "__main__":
    pts, ref, sha = load_points_and_reference()
    print(json.dumps({"points": pts, "reference": ref, "edge_result_sha256": sha}, indent=1))
