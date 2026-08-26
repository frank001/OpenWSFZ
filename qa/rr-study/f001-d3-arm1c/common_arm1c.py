"""F-001 D3 ARM 1C -- unique-match-trade exposure. Shared helpers.

Spec: qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md

Sec.2 "reuse, do not re-implement" (HK-018): everything needed to reproduce
ARM 1B's population (`slot`, `build_theirs_index`, `best_match`, `T12`,
`cp_lower_one_sided`, `cp_upper_one_sided`, `build_part_a`, `apply_row0d`,
`callsign_flags`) is IMPORTED from common_arm1b.py / run_arm1b.py, never
re-implemented. The only new code here is Sec.3.1's `T12C.matches12` (shipped
verbatim per HK-021(r), transcribed character-for-character from the spec
listing) and the streaming replay / snapshot machinery Sec.3 needs to record
multiplicity and table-freeze state AT PRINT TIME.

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
sys.path.insert(0, ARM1B_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1b as B1   # noqa: E402  (slot/build_theirs_index/best_match/T12/CP/pins)
import common_arm1 as A     # noqa: E402  (n22_of/n12_of/SimTable/EMPTY/OCCUPIED)
import common_b1 as B       # noqa: E402  (is_callsign_token/redact)
import run_arm1b as R1B     # noqa: E402  (build_part_a/apply_row0d/callsign_flags -- object identity)

redact = B.redact

CUR_SIZE = 4096
SZ8_SIZE = 32768

EXPECTED_L2_SHA256 = B1.EXPECTED_L2_SHA256
EXPECTED_L2_SHIM_VERSION = B1.EXPECTED_L2_SHIM_VERSION
EXPECTED_N_DECODES = B1.EXPECTED_N_DECODES
EXPECTED_N_THEIRS_ROWS = B1.EXPECTED_N_THEIRS_ROWS

# ARM 1B's own pre-registered/measured population -- ROW 0b must reproduce
# these EXACTLY before this arm's own machinery is trusted at all.
EXPECTED_ARM1B_K = 243
EXPECTED_ARM1B_N_CS = 115
EXPECTED_ARM1B_N_DISAGREE_PAIRS = 92


def load_l2run1_ours_rows():
    return B1.load_l2run1_ours_rows()


def load_theirs_rows():
    return B1.load_theirs_rows()


def sorted_stream(ours_rows):
    return B1.sorted_stream(ours_rows)


def build_theirs_index(theirs_rows):
    return B1.build_theirs_index(theirs_rows)


def slot(msg):
    return B1.slot(msg)


# ---- Sec.3.1: the multiplicity predicate, shipped verbatim (HK-021(r)) ----
class T12C(B1.T12):
    """T12 plus the chain-multiplicity count. matches12 walks the SAME probe
    chain as lookup12 under the SAME break-on-EMPTY rule, and counts every
    OCCUPIED entry whose stored n22 truncates to the query's n12. lookup12
    returns the FIRST of exactly these; multiplicity >= 2 is the definition
    of an AMBIGUOUS query."""

    def matches12(self, n12):
        h10 = (n12 >> 2) & 0x3FF
        idx = (h10 * 23) % self.n
        found = 0
        for _ in range(self.n):
            st = self.state[idx]
            if st == A.EMPTY:
                break
            if st == A.OCCUPIED and (self.hash[idx] >> 10) == n12:
                found += 1
            idx = (idx + 1) % self.n
        return found


def clone_table(tbl: T12C) -> T12C:
    """Deep-copies a T12C's mutable arrays so an injection/exhibit can be
    tried on a snapshot without touching the live replay table (Sec.4 ROW
    0f). Never used to alter the actual leg/gate computation."""
    new = T12C(tbl.n, None)
    new.state = list(tbl.state)
    new.callsign = list(tbl.callsign)
    new.hash = list(tbl.hash)
    new.last_used = list(tbl.last_used)
    new.freq = list(tbl.freq)
    new.count = tbl.count
    new.reject_count = tbl.reject_count
    new.clock = tbl.clock
    return new


def run_12bit_leg_c(stream, size, capture_key=None):
    """As common_arm1b.run_12bit_leg, but per resolved type-4 query also
    records matches12 (AT PRINT TIME, i.e. after that row's own tokens are
    inserted -- Sec.0.2's "of the names this build printed... how many were
    AMBIGUOUS AT PRINT TIME") and whether the table had already frozen
    (count >= n, fill-and-freeze). key = (ts, freq_hz, message_norm).

    If `capture_key` matches the current row's key, a snapshot of the table
    AT THAT EXACT INSTANT (Sec.4 ROW 0f's worked example) is returned
    alongside the leg -- this is the live streaming state, not the final
    end-of-session table, because a chain's multiplicity can still grow
    after the query if the freeze had not yet happened."""
    tbl = T12C(size, None)
    leg = {}
    snapshot = None
    for r in stream:
        for t in r["message_norm"].split():
            if B.is_callsign_token(t):
                h = A.n22_of(t)
                if h is not None:
                    tbl.add(t, h)
        s = slot(r["message_norm"])
        if s is None:
            continue
        kind, payload, others, nonstd, ntok = s
        if not (nonstd and kind == "resolved" and B.is_callsign_token(payload)):
            continue
        n22 = A.n22_of(payload)
        if n22 is None:
            continue
        n12 = n22 >> 10
        key = (r["ts"], r["freq_hz"], r["message_norm"])
        leg[key] = {
            "sim_name": tbl.lookup12(n12),
            "real_name": payload,
            "matches12": tbl.matches12(n12),
            "frozen": tbl.count >= tbl.n,
            "n12": n12,
        }
        if capture_key is not None and key == capture_key:
            snapshot = (clone_table(tbl), n12)
    return leg, snapshot


# ---- Clopper-Pearson (reused, not re-derived) ------------------------------
cp_lower_one_sided = B1.cp_lower_one_sided
cp_upper_one_sided = B1.cp_upper_one_sided
