"""H3 (#259 late-start alignment): offline decodability check, design. Pure design, no audio, no I/O.

Spec: qa/rr-study/2026-10-23-1735-architect-to-qa-spec-late-start-time-alignment.md, section 4 H3 + Amendment 1 (A1.1).
Everything the spec fixes is an assertion here so a silent edit cannot change the design after the freeze.

Styles (t = start offset into the 15 s slot, seconds; clip = the 12.64 s FT8 transmission, 606,720 samples at 48 kHz):
  O  old     symbol 0 at t, tail cut at 15 s (today): signal at WSJT-X DT = t - 0.5.
  A  aligned R1: t <= 2.36 s full clip at t; 2.36 < t < 11.25 s skip round((t-0.5)*48000) samples of the clip start,
             play the rest from t (so it sits at DT = 0), with the A1.4 240-sample raised-cosine fade-in.
  M  minimal skip only (t - 2.36) s so the clip just fits (DT = +1.86), same fade-in. Descriptive only, no code.
For t <= 2.36 s the three styles are the SAME audio (the render step asserts it), so those t are played once, style F.
"""
from __future__ import annotations

import hashlib
import json
import random

SEED = 20261024
FS = 48_000
SLOT_S = 15.0
NOMINAL_S = 0.5                      # WSJT-X DT = 0 <=> the clip starts 0.5 s into the slot
TX_S = 79 * 0.16                     # 12.64 s
TX_N = 606_720
WHOLE_EDGE_S = 2.36                  # LatestWholeStart = 15 - 12.64 (asserted below; float-safe literal)
LAST_START_S = 11.25
RAMP_N = 240                         # A1.4: 5 ms raised cosine at a cut start
M_DT_S = WHOLE_EDGE_S                # style M places the whole clip at dt 2.36 s (DT +1.86 s)
SNRS_DB = (-8, -16)                  # WSJT-X 2500 Hz convention (S4 reference-sigma convention, as the lateness-edge test)
SEEDS = 5
T_FULL = (0.62, 1.5, 2.36)           # at or below the whole-clip edge: styles identical -> style F
T_CUT = (3.5, 4.9, 6.5, 8.0, 10.0)   # above it: O, A, M differ
STYLES_CUT = ("O", "A", "M")
TEXT, FREQ_HZ = "Q1ABC Q2DEF FN42", 1500.0   # synthetic Q-calls only (NFR-021)
MAX_BATCH = 20                       # run_scenario._MAX_BATCH_TRIALS
CUTOFF_HZ = 4700.0

# --- the spec's numbers, as assertions -------------------------------------------------------------------------------
assert TX_N == round(TX_S * FS) and abs(WHOLE_EDGE_S - (SLOT_S - TX_S)) < 1e-9 and LAST_START_S == 11.25
assert all(t < LAST_START_S for t in T_CUT) and all(t <= WHOLE_EDGE_S for t in T_FULL)
assert 4.9 in T_CUT and 3.5 in T_CUT and 1.5 in T_FULL and 0.62 in T_FULL and 2.36 in T_FULL   # G1, G2, A1.1 extras
assert set(SNRS_DB) == {-8, -16} and SEEDS == 5 and RAMP_N == round(0.005 * FS)


def skip_samples(t: float) -> int:
    """R1: samples skipped from the clip start by style A at start offset t (half-up like the C# helper)."""
    return int(round((t - NOMINAL_S) * FS)) if t > WHOLE_EDGE_S else 0


assert skip_samples(2.37) == 89_760 and skip_samples(4.9) == 211_200 and skip_samples(11.24) == 515_520
assert skip_samples(2.36) == 0 and skip_samples(3.5) == 144_000


def noise_seed(ti: int, snr: int, k: int) -> int:
    """Noise realisation depends on (t, SNR, replicate) only, so O/A/M of one cell share the SAME noise (paired)."""
    return int(hashlib.sha256(f"h3|{SEED}|{ti}|{snr}|{k}".encode()).hexdigest()[:8], 16) % (2 ** 31)


def cells():
    out = []
    for ti, t in enumerate(T_FULL + T_CUT):
        for style in (("F",) if t in T_FULL else STYLES_CUT):
            for snr in SNRS_DB:
                for k in range(SEEDS):
                    out.append({"t": t, "ti": ti, "style": style, "snr": snr, "k": k,
                                "noise_seed": noise_seed(ti, snr, k)})
    return out


def build() -> dict:
    cs = cells()
    assert len(cs) == (len(T_FULL) * 1 + len(T_CUT) * 3) * len(SNRS_DB) * SEEDS == 180
    order = list(range(len(cs)))
    random.Random(SEED).shuffle(order)           # run order randomised: no time-of-run confound with a style
    cycles = []
    for ci, idx in enumerate(order):
        c = dict(cs[idx])
        c["cycle"] = ci
        cycles.append(c)
    return {"seed": SEED, "text": TEXT, "freq_hz": FREQ_HZ, "n_cycles": len(cycles), "cycles": cycles}


if __name__ == "__main__":
    import sys
    d = build()
    path = sys.argv[1] if len(sys.argv) > 1 else "manifest.json"
    open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=1, sort_keys=True) + "\n")
    print(path, d["n_cycles"], "cycles")
