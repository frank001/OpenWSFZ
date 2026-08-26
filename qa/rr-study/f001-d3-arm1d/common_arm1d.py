"""F-001 D3 ARM 1D -- the unique-match trade, measured with BOUNDS instead of
a FILTER. Shared helpers.

Spec: qa/rr-study/2026-08-26-1743-architect-to-qa-spec-f001-d3-arm1d-unique-match-trade-bounded.md

This is a NEW pre-registration, not a re-run of ARM 1C and not ARM 1C with
Sec.3.2 deleted (ARM 1C is VOID at ROW 0d and stays VOID -- its gates were
never computed).

Sec.2 "reuse, do not re-implement" (HK-018): everything needed to reproduce
ARM 1B's population and ARM 1C's replay/multiplicity machinery
(`slot`, `build_theirs_index`, `best_match`, `T12`, `cp_lower_one_sided`,
`cp_upper_one_sided`, the input pins, `build_part_a`, `apply_row0d`,
`callsign_flags`, `T12C.matches12`, `run_12bit_leg_c`, `clone_table`,
`CUR_SIZE`, `SZ8_SIZE`) is IMPORTED from common_arm1b.py / run_arm1b.py /
common_arm1c.py, never re-implemented. `matches12` is NOT re-specified here
(ARM 1C's ROW 0c already proved it walks the same probe chain `lookup12`
does, with zero exceptions -- re-checked below as a drift guard, not
re-derived).

The only NEW code in this arm is Sec.3's four functions (shipped verbatim,
character-for-character against the spec listing, per HK-021(r)) and the
two-pass adversarial driver in run_arm1d.py.

NFR-021: real callsign strings live in memory only. Nothing that reaches
result.json, the report, or a log line is anything but counts, cycle
timestamps, frequencies, and sha256[:6]-redacted CS-xxxxxx tokens
(common_b1.redact, re-exported here as `redact`).
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ARM1B_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1b")
ARM1C_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1c")
sys.path.insert(0, ARM1B_DIR)
sys.path.insert(0, ARM1C_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1c as C1C   # noqa: E402  (T12C/matches12, run_12bit_leg_c, clone_table, CUR_SIZE/SZ8_SIZE)
import common_arm1b as B1    # noqa: E402  (slot/build_theirs_index/best_match/T12/CP/pins)
import common_arm1 as A      # noqa: E402  (n22_of/n12_of/SimTable/EMPTY/OCCUPIED)
import common_b1 as B        # noqa: E402  (is_callsign_token/redact)
import run_arm1b as R1B      # noqa: E402  (build_part_a/apply_row0d/callsign_flags -- object identity)

redact = B.redact

CUR_SIZE = C1C.CUR_SIZE
SZ8_SIZE = C1C.SZ8_SIZE

EXPECTED_L2_SHA256 = C1C.EXPECTED_L2_SHA256
EXPECTED_L2_SHIM_VERSION = C1C.EXPECTED_L2_SHIM_VERSION
EXPECTED_N_DECODES = C1C.EXPECTED_N_DECODES
EXPECTED_N_THEIRS_ROWS = C1C.EXPECTED_N_THEIRS_ROWS

# ARM 1B's own pre-registered/measured population -- ROW 0b must reproduce
# these EXACTLY before this arm's own machinery is trusted at all.
EXPECTED_ARM1B_K = C1C.EXPECTED_ARM1B_K
EXPECTED_ARM1B_N_CS = C1C.EXPECTED_ARM1B_N_CS
EXPECTED_ARM1B_N_DISAGREE_PAIRS = C1C.EXPECTED_ARM1B_N_DISAGREE_PAIRS

# Sec.0.4 drafting facts -- measured while drafting, ROW 0b/0d reproduce them,
# they are never discovered fresh by this run.
EXPECTED_N_IN_LEG = 243
EXPECTED_KNOWN = 206
EXPECTED_UNKNOWN_DISAGREE = 4
EXPECTED_UNKNOWN_AGREE = 33
EXPECTED_ROWC_UNITS = 59
EXPECTED_ROWD_UNITS = 56
EXPECTED_ROWC_UNKNOWN_UNITS = 3     # ROW C units carrying an UNKNOWN *disagreeing* decode
EXPECTED_ROWD_UNKNOWN_UNITS = 7     # ROW D units carrying any UNKNOWN decode
EXPECTED_FROZEN_NUM = 144
EXPECTED_FROZEN_DEN = 243
EXPECTED_SIM_NONE_BUT_REAL_RESOLVED_NUM = 20
EXPECTED_SIM_NONE_BUT_REAL_RESOLVED_DEN = 1868


def load_l2run1_ours_rows():
    return C1C.load_l2run1_ours_rows()


def load_theirs_rows():
    return C1C.load_theirs_rows()


def sorted_stream(ours_rows):
    return C1C.sorted_stream(ours_rows)


def build_theirs_index(theirs_rows):
    return C1C.build_theirs_index(theirs_rows)


def slot(msg):
    return C1C.slot(msg)


def run_12bit_leg_c(stream, size, capture_key=None):
    return C1C.run_12bit_leg_c(stream, size, capture_key=capture_key)


clone_table = C1C.clone_table
T12C = C1C.T12C

cp_lower_one_sided = C1C.cp_lower_one_sided
cp_upper_one_sided = C1C.cp_upper_one_sided


def key_of(p):
    return (p["ts"], p["freq_hz"], p["message_norm"])


# =============================================================================
# Sec.3 -- shipped verbatim, character for character (HK-021(r))
# =============================================================================

# ---- Sec.3.1 -- KNOWN vs UNKNOWN: a LABEL, never a filter -----------------
def is_known(p, leg):
    """True iff the replay reproduced the EXACT name the real build printed.
    ARM 1C used this as a FILTER and was VOIDed for it. Here it is only a
    label: every one of the 243 decodes enters the analysis either way."""
    v = leg.get((p["ts"], p["freq_hz"], p["message_norm"]))
    return v is not None and v["sim_name"] == p["o_payload"]


# ---- Sec.3.2 -- adversarial assignment ------------------------------------
def ambiguous(p, leg, unknown_as):
    """Ambiguity of ONE decode under ONE adversarial pass. `unknown_as` is
    True or False and applies ONLY to UNKNOWN decodes; a KNOWN decode reads
    its replayed multiplicity identically in both passes."""
    if not is_known(p, leg):
        return unknown_as
    return leg[(p["ts"], p["freq_hz"], p["message_norm"])]["matches12"] >= 2


# ---- Sec.3.3 -- the two unit families, unchanged from ARM 1C (HK-021(t)) --
def rowc_units(by_cs):
    """Callsigns with >=1 DISAGREEING decode -- where a rescue could happen."""
    return sorted(cs for cs, ps in by_cs.items() if any(q["disagree"] for q in ps))


def rowd_units(by_cs):
    """The COMPLEMENT: callsigns with NO disagreeing decode -- where the cost
    lands. HK-021(t): the cost is gated on the complement of the population
    the rescue is measured on, in the same run."""
    return sorted(cs for cs, ps in by_cs.items() if not any(q["disagree"] for q in ps))


def is_rescued(ps, leg, unknown_as):
    """ROW C, deliberately conservative AGAINST the remedy: ALL of a
    callsign's disagreeing decodes must be ambiguous."""
    return all(ambiguous(q, leg, unknown_as) for q in ps if q["disagree"])


def is_lost(ps, leg, unknown_as):
    """ROW D, deliberately conservative AGAINST the remedy: ANY one of a
    callsign's decodes being ambiguous is enough to call the name lost."""
    return any(ambiguous(q, leg, unknown_as) for q in ps)
