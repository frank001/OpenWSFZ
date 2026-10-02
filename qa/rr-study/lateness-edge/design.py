"""LATENESS / EDGE test (spec 2026-10-02-0720, Amendment 2): the seeded scenario design.

Pure design: no audio, no I/O except the manifest writer. Everything the Architect's spec fixes
is an assertion here, so a silent edit cannot change the design after the freeze.

Lateness convention (spec section 2, FILE:LINE in the freeze report):
  L = seconds after the nominal FT8 start; WSJT-X DT = 0  <=>  the signal starts 0.5 s into the slot.
  synth/modulator.py:110 places a signal at slot sample round(dt_s*fs), so dt_s = 0.5 + L.

Cycle layout (204 cycles):
  LATE  block: cycles   0..99   planted (100)
  EARLY block: cycles 100..203  as (idle, planted) x 52. Deviation from the spec's wording
        ("each planted early cycle is followed by one idle cycle"): the idle slot is placed
        BEFORE each planted early cycle instead. Each early buffer is armed 3.0 s before its
        boundary, i.e. inside the previous slot, so it is the previous slot that must be free
        of any other playback (that includes the last LATE buffer, which sounds to its slot end).
        The count (104 = 52 planted + 52 idle) and the purpose are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import numpy as np

SEED = 20261002
FS = 48_000
SLOT_S = 15.0
OFFSET_S = 0.5                       # WSJT-X DT = 0 <=> start 0.5 s into the slot
TX_S = 79 * 0.16                     # 12.64 s
CUT_ONSET_S = SLOT_S - OFFSET_S - TX_S   # L above this is cut at the slot end: 1.86 s
SNRS_DB = (-16, -8)
LATE_L_GRID = tuple(i * 0.25 for i in range(25))          # 0.00 ... 6.00
EARLY_L_GRID = tuple(-3.0 + i * 0.25 for i in range(13))  # -3.00 ... 0.00
SIGNALS_PER_CELL = 32
SIGNALS_PER_CYCLE = 16
FREQ_SLOTS_HZ = tuple(300 + 150 * i for i in range(SIGNALS_PER_CYCLE))
LATE_CYCLES = 100
EARLY_PLANTED = 52
EARLY_CYCLES = 104
TOTAL_CYCLES = 204
EARLY_ARM_S = 3.0                    # early buffers start this long before the boundary
MIN_DISTINCT_SLOTS = 12

# --- the spec's numbers, as assertions ---------------------------------------------------
assert len(LATE_L_GRID) == 25 and len(EARLY_L_GRID) == 13 and len(SNRS_DB) == 2
assert LATE_L_GRID[-1] == 6.0 and EARLY_L_GRID[0] == -3.0 and EARLY_L_GRID[-1] == 0.0
assert len(LATE_L_GRID) * len(SNRS_DB) * SIGNALS_PER_CELL == 1600
assert len(EARLY_L_GRID) * len(SNRS_DB) * SIGNALS_PER_CELL == 832
assert 1600 // SIGNALS_PER_CYCLE == LATE_CYCLES and 832 // SIGNALS_PER_CYCLE == EARLY_PLANTED
assert EARLY_CYCLES == 2 * EARLY_PLANTED and LATE_CYCLES + EARLY_CYCLES == TOTAL_CYCLES == 204
assert FREQ_SLOTS_HZ[0] == 300 and FREQ_SLOTS_HZ[-1] == 2550 and len(FREQ_SLOTS_HZ) == 16
assert abs(CUT_ONSET_S - 1.86) < 1e-9 and abs(TX_S - 12.64) < 1e-9


def dt_for_L(L: float) -> float:
    """Placement argument of synth.modulator for lateness L."""
    return OFFSET_S + L


def cell_id(block: str, L: float, snr: int) -> str:
    return f"{block}_L{L:+.2f}_S{snr:+d}"


def _cells(block: str) -> list[tuple[str, float, int]]:
    grid = LATE_L_GRID if block == "LATE" else EARLY_L_GRID
    return [(cell_id(block, L, s), L, s) for L in grid for s in SNRS_DB]


def _deal(n_cells: int, n_cycles: int, rng: np.random.Generator) -> np.ndarray:
    """(n_cycles x 16) matrix of cell indexes. Each cell appears exactly 32 times, never twice in
    a cycle, and uses >= 12 distinct frequency slots. Rows are 16 consecutive cells (mod n_cells) of a
    32x tiled sequence (so no repeat within a row since 16 < n_cells); the column order within each
    row is a seeded permutation, redrawn until the distinct-slot constraint holds."""
    tokens = np.tile(np.arange(n_cells), SIGNALS_PER_CELL)
    rows = tokens.reshape(n_cycles, SIGNALS_PER_CYCLE)
    for attempt in range(10_000):
        grid = np.array([rng.permutation(r) for r in rows])
        ok = True
        for c in range(n_cells):
            cols = np.where(grid == c)[1]
            if len(cols) != SIGNALS_PER_CELL or len(set(cols.tolist())) < MIN_DISTINCT_SLOTS:
                ok = False
                break
        if ok:
            return grid
    raise RuntimeError("could not satisfy the distinct-slot constraint")


def _messages(n: int, rng: random.Random) -> list[str]:
    """n unique Q-prefix synthetic standard messages '<CALL> <CALL> <GRID4>' (NFR-021). Every callsign
    is unique across the whole session too."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    seen_calls: set[str] = set()
    texts: list[str] = []

    def call() -> str:
        while True:
            c = f"Q{rng.randrange(10)}{rng.choice(letters)}{rng.choice(letters)}{rng.choice(letters)}"
            if c not in seen_calls:
                seen_calls.add(c)
                return c

    while len(texts) < n:
        a, b = call(), call()
        grid = f"{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.randrange(10)}{rng.randrange(10)}"
        texts.append(f"{a} {b} {grid}")
    assert len(set(texts)) == n
    return texts


def build_design(seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    pyrng = random.Random(seed)
    texts = _messages(2432, pyrng)
    ti = 0
    cycles: list[dict] = []
    signals: list[dict] = []
    order_in_block = {}
    for block, n_planted in (("LATE", LATE_CYCLES), ("EARLY", EARLY_PLANTED)):
        cells = _cells(block)
        perm = rng.permutation(len(cells))            # cell id -> row of `cells`, seeded
        grid = _deal(len(cells), n_planted, rng)
        cyc_order = rng.permutation(n_planted)        # seeded cycle shuffle
        order_in_block[block] = cyc_order.tolist()
        for pos in range(n_planted):
            row = grid[int(cyc_order[pos])]
            if block == "EARLY":
                cycles.append({"index": len(cycles), "block": block, "planted": False, "signals": []})
            cyc = {"index": len(cycles), "block": block, "planted": True, "signals": []}
            for slot, c in enumerate(row):
                cid, L, snr = cells[int(perm[int(c)])]
                sig = {"sig_id": len(signals), "cycle": cyc["index"], "slot": slot,
                       "freq_hz": FREQ_SLOTS_HZ[slot], "cell": cid, "block": block,
                       "L_s": L, "snr_db": snr, "dt_s": dt_for_L(L), "text": texts[ti]}
                ti += 1
                signals.append(sig)
                cyc["signals"].append(sig["sig_id"])
            cycles.append(cyc)
    assert ti == 2432 and len(signals) == 2432 and len(cycles) == TOTAL_CYCLES
    # constraint audit (also exercised by the tests)
    audit(cycles, signals)
    return {"seed": seed, "constants": {
                "fs": FS, "slot_s": SLOT_S, "offset_s": OFFSET_S, "snrs_db": list(SNRS_DB),
                "late_L": list(LATE_L_GRID), "early_L": list(EARLY_L_GRID),
                "signals_per_cell": SIGNALS_PER_CELL, "signals_per_cycle": SIGNALS_PER_CYCLE,
                "freq_slots_hz": list(FREQ_SLOTS_HZ), "cycles": TOTAL_CYCLES,
                "early_arm_s": EARLY_ARM_S, "noise_cutoff_hz": 4700.0,
                "late_planted": LATE_CYCLES, "early_planted": EARLY_PLANTED},
            "cycles": cycles, "signals": signals}


def audit(cycles: list[dict], signals: list[dict]) -> None:
    by_cell: dict[str, list[dict]] = {}
    for s in signals:
        by_cell.setdefault(s["cell"], []).append(s)
    assert len(by_cell) == 50 + 26
    for cid, lst in by_cell.items():
        assert len(lst) == SIGNALS_PER_CELL, (cid, len(lst))
        assert len({s["slot"] for s in lst}) >= MIN_DISTINCT_SLOTS, cid
        assert len({s["cycle"] for s in lst}) == len(lst), f"{cid} twice in one cycle"
    for c in cycles:
        if c["planted"]:
            sl = [signals[i] for i in c["signals"]]
            assert len(sl) == 16 and sorted(s["slot"] for s in sl) == list(range(16))
            assert len({s["cell"] for s in sl}) == 16
        else:
            assert not c["signals"]
    assert len({s["text"] for s in signals}) == len(signals)
    for s in signals:
        assert s["text"].startswith("Q") and all(w[0] == "Q" for w in s["text"].split()[:2])
    for i, c in enumerate(cycles):          # every planted early cycle is preceded by an idle one
        if c["block"] == "EARLY" and c["planted"]:
            assert not cycles[i - 1]["planted"]


def canonical_json(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode("utf-8")


def write_manifest(path: Path, design: dict) -> str:
    data = canonical_json(design)
    Path(path).write_bytes(data)           # bytes: LF, no platform newline translation
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1])
    d = build_design()
    print(write_manifest(out, d), out)
