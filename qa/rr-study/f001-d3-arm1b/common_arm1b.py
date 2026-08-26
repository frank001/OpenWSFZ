"""F-001 D3 ARM 1B -- 12-bit mis-resolution correctness. Shared helpers.

Spec: qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md

Sec.3.1's `slot()` predicate is shipped as code (HK-021(r)) -- transcribed
character-for-character against the spec's own listing, not re-derived from
its prose gloss. `is_callsign_token` / `n22_of` / `SimTable` are IMPORTED from
common_b1.py / common_arm1.py, never re-implemented (Sec.2 "reuse, do not
re-implement"; ROW 0c asserts this by object identity).

NFR-021: real callsign strings and raw message text live in memory only, as
`message_norm` fields on row dicts (identical discipline to common_g2a.py /
gap-census-a/common.py -- neither of those write raw text to disk either).
Nothing that reaches result.json, the report, or a log line is anything but
counts, cycle timestamps, frequencies, and sha256[:6]-redacted CS-xxxxxx
tokens (common_b1.redact, re-exported here as `redact`).
"""
from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ARM1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1")
B1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "b1-coverage-a")
G2A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "g2a-remeasure-a")
GAP_CENSUS_A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "gap-census-a")
sys.path.insert(0, ARM1_DIR)
sys.path.insert(0, B1_DIR)
sys.path.insert(0, G2A_DIR)
sys.path.insert(0, GAP_CENSUS_A_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1 as A   # noqa: E402  (n22_of/n12_of/SimTable/EMPTY/OCCUPIED)
import common_b1 as B     # noqa: E402  (is_callsign_token/redact)
import common_g2a as G    # noqa: E402  (dump loaders, THEIRS_ALL_TXT, pins)
import common as gc       # noqa: E402  (parse_all_txt)

redact = B.redact

# ---- Sec.3.1: the type-4 population predicate, shipped verbatim -----------
STD = re.compile(r'^[A-Z0-9]{1,2}[0-9][A-Z]{1,3}$')
GRID = re.compile(r'^[A-R]{2}[0-9]{2}$')
UNRES = re.compile(r'^<\.*>$')
NONCALL = {'CQ', 'DE', 'QRZ', 'RRR', 'RR73', '73', 'TU', 'NA', 'SA', 'EU', 'AS', 'AF', 'OC', 'AN', 'DX', 'TEST'}


def slot(msg):
    """None unless the message has EXACTLY ONE bracket slot."""
    toks = msg.split()
    br = [t for t in toks if t.startswith('<')]
    if len(br) != 1:
        return None
    others = [t for t in toks if not t.startswith('<')]
    nonstd = any((not STD.fullmatch(t)) and (not GRID.fullmatch(t)) and t not in NONCALL
                 and not re.fullmatch(r'[+-]?[0-9]{1,2}', t)
                 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t) for t in others)
    kind = "unresolved" if UNRES.fullmatch(br[0]) else "resolved"
    return kind, br[0].strip('<>'), tuple(others), nonstd, len(toks)


# ---- Sec.2 pins -------------------------------------------------------------
EXPECTED_L2_SHA256 = G.L2_SHA256
EXPECTED_L2_SHIM_VERSION = G.L2_SHIM_VERSION
EXPECTED_N_DECODES = 71600
EXPECTED_N_THEIRS_ROWS = 43423


def load_l2run1_ours_rows():
    return A.load_l2run1_ours_rows()


def load_l2run2_ours_rows():
    return A.load_l2run2_ours_rows()


def load_theirs_rows():
    return G.load_theirs_rows()


def sorted_stream(ours_rows):
    return sorted(ours_rows, key=lambda r: (r["ts"], r["freq_hz"], r["message_norm"]))


# ---- Sec.3.2: pairing to the reference --------------------------------------
def build_theirs_index(theirs_rows):
    """key = (ts, non-bracket-token tuple, token count) -> sorted list of
    candidate dicts. Sorted at construction (hash-randomised-iteration
    hazard on the board); the final pick in `best_match` re-sorts explicitly
    so insertion order never matters regardless."""
    idx: dict = {}
    for r in sorted(theirs_rows, key=lambda r: (r["ts"], r["freq_hz"], r["message_norm"])):
        s = slot(r["message_norm"])
        if s is None:
            continue
        kind, payload, others, nonstd, ntok = s
        key = (r["ts"], others, ntok)
        idx.setdefault(key, []).append({
            "freq_hz": r["freq_hz"], "kind": kind, "payload": payload,
            "message_norm": r["message_norm"], "nonstd": nonstd,
        })
    return idx


def best_match(o_row, others, ntok, theirs_index):
    """Nearest-frequency match within 4.0 Hz; ties break on lowest freq_hz,
    then on message_norm (Sec.3.2), both sorted before selection -- never a
    dict/set iteration order."""
    key = (o_row["ts"], others, ntok)
    cands = theirs_index.get(key, [])
    in_tol = [c for c in cands if abs(c["freq_hz"] - o_row["freq_hz"]) <= 4.0]
    if not in_tol:
        return None
    in_tol_sorted = sorted(in_tol, key=lambda c: (abs(c["freq_hz"] - o_row["freq_hz"]),
                                                     c["freq_hz"], c["message_norm"]))
    return in_tol_sorted[0]


def type4_rows(ours_rows):
    """All ours rows whose slot() predicate fires nonstd=True (the 12-bit
    population, Sec.3.1), resolved or unresolved -- Sec.6's coverage table
    needs both."""
    out = []
    for r in ours_rows:
        s = slot(r["message_norm"])
        if s is None:
            continue
        kind, payload, others, nonstd, ntok = s
        if not nonstd:
            continue
        out.append({"row": r, "kind": kind, "payload": payload, "others": others, "ntok": ntok})
    return out


def pair_all(ours_type4, theirs_index):
    """Pairs every ours type-4 row (Sec.3.2). Returns a list of dicts with
    the ours side, whether a reference match was found, and the reference
    side if so. No gating here -- Sec.3.3's agree/disagree and Sec.6's
    contingencies are both derived from this one pass."""
    out = []
    for item in ours_type4:
        r = item["row"]
        m = best_match(r, item["others"], item["ntok"], theirs_index)
        out.append({
            "ts": r["ts"], "freq_hz": r["freq_hz"], "message_norm": r["message_norm"],
            "o_kind": item["kind"], "o_payload": item["payload"],
            "matched": m is not None,
            "t_kind": m["kind"] if m else None,
            "t_payload": m["payload"] if m else None,
        })
    return out


# ---- Sec.3.4 / Part B: the 12-bit simulator (T12) --------------------------
class T12(A.SimTable):
    """ft8_shim.c:637-655 with sh=10 (FTX_CALLSIGN_HASH_12_BITS): h10 =
    (n12 >> 2) & 0x3FF (same start index as the 22-bit form -- h10 is always
    derived from the SAME top bits regardless of sh), compare
    (stored_n22 & 0x3FFFFF) >> 10 == n12, FIRST match wins, break on EMPTY.
    Transcribed from the parent ruling's Sec.7 probe (Architect,
    artefacts/2026-08-26-arm1b-probe/probe_fidelity.py), re-implemented here
    (not imported -- that module lives under a gitignored artefacts/ path and
    is explicitly a scratch probe, not a shared module) so this arm has no
    dependency on a path that may be cleaned up."""

    def lookup12(self, n12: int):
        h10 = (n12 >> 2) & 0x3FF
        idx = (h10 * 23) % self.n
        for _ in range(self.n):
            st = self.state[idx]
            if st == A.EMPTY:
                return None
            if st == A.OCCUPIED and (self.hash[idx] >> 10) == n12:
                return self.callsign[idx]
            idx = (idx + 1) % self.n
        return None


def run_12bit_leg(stream, size):
    """Replays the insert stream against a fresh T12(size), and for every
    resolved type-4 query (nonstd, resolved, callsign-shaped payload,
    charset-valid) records what THIS leg's table names at that point.
    key = (ts, freq_hz, message_norm) -- unique per emitted decode."""
    tbl = T12(size, None)
    leg = {}
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
        key = (r["ts"], r["freq_hz"], r["message_norm"])
        leg[key] = (tbl.lookup12(n22 >> 10), payload, r, others, ntok)
    return leg


def paired_discordance(leg_a, leg_b):
    keys = sorted(set(leg_a) & set(leg_b))
    disc = [k for k in keys if leg_a[k][0] != leg_b[k][0]]
    return keys, disc


# ---- Clopper-Pearson, one-sided (HK-021(n)/(o)) -----------------------------
def cp_lower_one_sided(x: int, n: int, alpha: float = 0.05) -> float:
    if n == 0:
        return 0.0
    if x == 0:
        return 0.0
    from scipy.stats import beta as beta_dist
    return float(beta_dist.ppf(alpha, x, n - x + 1))


def cp_upper_one_sided(x: int, n: int, alpha: float = 0.05) -> float:
    if n == 0:
        return 1.0
    if x == n:
        return 1.0
    from scipy.stats import beta as beta_dist
    return float(beta_dist.ppf(1 - alpha, x + 1, n - x))
