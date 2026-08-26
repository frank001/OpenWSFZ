"""B1-COVERAGE-A -- shared helpers.

Spec: qa/rr-study/2026-08-25-1836-architect-to-qa-spec-b1-coverage-a.md

NFR-021: message text and real callsign tokens live in memory only, to build
the naming/candidate machinery. Nothing downstream of `redact()` ever leaves
this process holding a real callsign or raw message text -- results JSON and
report prose carry only counts, cycle timestamps, frequencies, and
sha256[:6]-redacted tokens (same discipline as common_g2a.py / common.py).

Reuses gap-census-a's Population/classify_partition and g2a-remeasure-a's
dump-loading/corrected-predicate helpers verbatim (imported, not copied --
HK-018): this arm partitions the SAME B1 population those harnesses already
produce, it does not recompute it from scratch.
"""
from __future__ import annotations

import hashlib
import os
import random
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
G2A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "g2a-remeasure-a")
GAP_CENSUS_A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "gap-census-a")
sys.path.insert(0, G2A_DIR)
sys.path.insert(0, GAP_CENSUS_A_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as gc  # noqa: E402  (gap-census-a/common.py)
import common_g2a as G  # noqa: E402  (g2a-remeasure-a/common_g2a.py)
from partition import classify_partition, ours_lookup_from_population  # noqa: E402

# ---- pinned constants (spec Sec.2.1) -- never re-derived -------------------
FREEZE_CYCLE_TS = "260803_202600"     # measured L2_freeze_cycle.json, index 767/4971
HASH_TABLE_SIZE = 4096                # ft8_shim.c:631
N_THEIRS_PINNED = 43423               # D-001 normalisation basis
EXPECTED_L2_SHA256 = G.L2_SHA256
EXPECTED_L2_SHIM_VERSION = G.L2_SHIM_VERSION
EXPECTED_N_DECODES = 71600
EXPECTED_N_THEIRS_ONLY = 18508
EXPECTED_B1_COUNT = 470

# ---- naming rule (spec Sec.2.4/2.5) -----------------------------------------
HASH_SLOT_RE = re.compile(r"^<\.*>$")
CS_RE = re.compile(r"^[A-Z0-9/]{3,11}$")
GRID_RE = re.compile(r"^[A-R]{2}[0-9]{2}$")
NONCALL = {"CQ", "DE", "QRZ", "RRR", "RR73", "73", "TU", "NA", "SA", "EU", "AS", "AF", "OC", "AN", "DX"}


def is_callsign_token(t: str) -> bool:
    return bool(CS_RE.fullmatch(t) and t not in NONCALL and not GRID_RE.fullmatch(t)
                and any(c.isdigit() for c in t) and any(c.isalpha() for c in t))


_ENCLOSING_BRACKETS_RE = re.compile(r"^<(.*)>$")


def strip_enclosing_brackets(tok: str) -> str:
    """QA CORRECTION to spec Sec.2.4 step 3 / Sec.2.5 (disclosed in the
    report, empirically verified): a reference token at the hash position is
    NOT necessarily an unresolved marker -- ft8_lib's add_brackets() wraps a
    *resolved* compound/hash-type callsign in <> too (common_g2a.py's own
    Sec.1 note), and the reference is by construction always the hash-type
    message that our decode failed to resolve. Empirically, ALL 339
    mismatch=0 candidates carry a bracket-wrapped reference token (339/339)
    -- applying Sec.2.5's shape test to the bracketed literal fails every
    single one (k=0), while applying it to the token with one enclosing
    <...> layer stripped reproduces the Architect's disclosed k=47 histogram
    exactly. This strip is applied ONLY when extracting the callsign to be
    NAMED (and hence to the T_plain plaintext-emission lookup, which is
    inherently a bracket-free predicate); it does not touch template
    matching or the Sec.2.2 mismatch classifier, both of which compare
    tokens literally."""
    m = _ENCLOSING_BRACKETS_RE.fullmatch(tok)
    return m.group(1) if m else tok


def redact(token: str) -> str:
    """NFR-021: the only form a real callsign token may take outside this
    process -- counts and this string, never the token itself."""
    return "CS-" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:6]


def template_match(o_tokens: list, r_tokens: list):
    """Spec Sec.2.4 item 2: O is template-consistent with R iff they have the
    same token count, O has exactly one token fullmatching ^<\\.*>$, and every
    other position is byte-equal. Returns the hash-slot index, or None."""
    if len(o_tokens) != len(r_tokens):
        return None
    hash_positions = [i for i, t in enumerate(o_tokens) if HASH_SLOT_RE.fullmatch(t)]
    if len(hash_positions) != 1:
        return None
    pos = hash_positions[0]
    for i in range(len(o_tokens)):
        if i == pos:
            continue
        if o_tokens[i] != r_tokens[i]:
            return None
    return pos


def mismatch_count(o_tokens: list, r_tokens: list):
    """Sec.2.2's descriptive classifier: same token count, exactly one hash
    slot in O, count of non-hash positions that differ. Returns None if O and
    R do not have equal token count, or O does not carry exactly one hash
    slot (i.e. not 'token-aligned' in Sec.2.2's sense)."""
    if len(o_tokens) != len(r_tokens):
        return None
    hash_positions = [i for i, t in enumerate(o_tokens) if HASH_SLOT_RE.fullmatch(t)]
    if len(hash_positions) != 1:
        return None
    pos = hash_positions[0]
    return sum(1 for i in range(len(o_tokens)) if i != pos and o_tokens[i] != r_tokens[i])


# ---- ROW 0a identity -------------------------------------------------------

def check_dump_identity(dump: dict) -> dict:
    return {
        "dll_sha256": dump.get("dll_sha256"),
        "shim_version": dump.get("shim_version"),
        "n_decodes": dump.get("n_decodes"),
        "n_records": len(dump.get("records", [])),
    }


# ---- plaintext-emission index (Sec.2.5) ------------------------------------

def build_t_plain_index(ours_rows_corrected: list) -> dict:
    """T_plain(X) = earliest cycle ts at which some ours-decode emits
    callsign-shaped token X as a whole whitespace token that does NOT begin
    with '<'. ts strings sort lexicographically == chronologically
    (YYMMDD_HHMMSS, fixed width)."""
    out = {}
    for r in ours_rows_corrected:
        ts = r["ts"]
        for t in r["message_norm"].split():
            if t.startswith("<"):
                continue
            if not is_callsign_token(t):
                continue
            prev = out.get(t)
            if prev is None or ts < prev:
                out[t] = ts
    return out


# ---- callsign-level bootstrap (spec Sec.2.3: decode counts NEVER get a CI) --

def bootstrap_proportion_ci(flags: dict, n_boot: int = 2000, seed: int = 20260826,
                             alpha: float = 0.05):
    """flags: {unit_name: bool}. Unit of resampling is the KEY of this dict
    (callsigns), never a decode. Sorted at construction (hazard 1)."""
    units = sorted(flags.keys())
    n = len(units)
    if n == 0:
        return 0.0, 0.0, 0.0
    values = [1.0 if flags[u] else 0.0 for u in units]
    point = sum(values) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        boots.append(s / n)
    boots.sort()
    lo_idx = int((alpha / 2) * n_boot)
    hi_idx = int((1 - alpha / 2) * n_boot) - 1
    hi_idx = min(hi_idx, n_boot - 1)
    return point, boots[lo_idx], boots[hi_idx]
