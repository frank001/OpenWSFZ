"""F-001 R5 -- own-callsign direct hash match on the answerer path. Shared helpers.

Spec: qa/rr-study/2026-08-27-1531-architect-to-qa-spec-f001-r5-own-callsign-direct-hash-match.md

Sec.3's predicates (try_parse_message / to_us_current / to_us_l1l2 / hash_dest_n12 /
to_us_l3) are shipped as code (HK-021(r)) and are transcribed below CHARACTER FOR
CHARACTER against the spec's own listing -- do not "clean up" or re-derive them.

n22_of/n12_of (common_arm1), cp_lower_one_sided/cp_upper_one_sided/slot/STD/
build_theirs_index/best_match (common_arm1b), redact/is_callsign_token (common_b1),
and parse_all_txt (gap-census-a/common) are IMPORTED, never re-implemented (Sec.2).

Two extra predicates NOT shipped in Sec.3 -- to_us_l1_only / to_us_l2_only -- are
QA's own derivation for G2's "how much each layer is worth" breakdown (the spec asks
for a three-way split but ships only the combined L1+L2 predicate). They are natural,
narrow extensions of Sec.3.2's own logic (one axis of the L1+L2 change each), disclosed
here rather than silently invented, and used ONLY for the descriptive, non-gated G2 --
never for G1 or G3.

DISCLOSED READING, G1a (see run_r5.py and the report for the full account): Sec.5's
G1a formula reads "4,343 single-bracket decodes" literally, but Sec.1's outcome #2
("a HASHED-DEST decode IS recognised...") and Sec.0.1's own reasoning both scope the
claim to the hashed-dest subset (2,933 of the 4,343 -- the other 1,410 include 1,206
ordinary bracket-at-src messages whose PLAIN dest token can legitimately match a real
own-call with no hash involved at all, which is correct existing behaviour, not a
counter-example to Sec.0.1(a)). Both readings are computed and reported; the
hashed-dest-only reading is treated as the one that tests the spec's actual claim.

DISCLOSED CONSTRUCTION, G3 UNKNOWN adversarial assignment (see run_r5.py Sec.5/G3):
unlike ARM 1D's "unknown callsign, unknown replayed multiplicity" ignorance -- where
the real identity is at least known -- an UNKNOWN theirs_name here means the TRUE
12-bit target hash is not observable in either log at all (`<...>` carries no residual
bits). QA's adversarial bounds, both applied per decode, both disclosed:
  MAX pass (least favourable to G3-1 FAVOURABLE): the decode is assumed to fire for
    every own-call in the single largest occupancy bucket, and EVERY firing own-call
    counts as a false positive (fp_contribution == n_fires_contribution == bucket_max).
  MIN pass (least favourable to G3-2 UNFAVOURABLE): the decode contributes zero to
    both fp and n_fires (assumed never to fire for any hypothetical own-call).
This is QA's construction, not shipped code -- flagged for the Architect same as any
other disclosed reading (HK-025 precedent: CLASSIFY then disclose, never silently
resolve a validity ambiguity).

NFR-021: real callsign strings and message text live in memory only. Nothing that
reaches result.json, run.log, or the report is anything but counts, redacted
CS-xxxxxx tokens (common_b1.redact), or the literal string "PD2FZ" itself, which is
the spec's explicit, pre-registered NFR-021 exception (OWNCALL, Sec.0.2) -- no OTHER
real callsign may appear in output.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ARM1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1")
ARM1B_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1b")
B1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "b1-coverage-a")
G2A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "g2a-remeasure-a")
GAP_CENSUS_A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "gap-census-a")
sys.path.insert(0, ARM1_DIR)
sys.path.insert(0, ARM1B_DIR)
sys.path.insert(0, B1_DIR)
sys.path.insert(0, G2A_DIR)
sys.path.insert(0, GAP_CENSUS_A_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1 as A     # noqa: E402  (n22_of / n12_of)
import common_arm1b as CB   # noqa: E402  (slot / STD / build_theirs_index / best_match / cp bounds)
import common_b1 as B       # noqa: E402  (redact / is_callsign_token)
import common as gc         # noqa: E402  (parse_all_txt, OURS_ALL_TXT, THEIRS_ALL_TXT)

n22_of = A.n22_of
n12_of = A.n12_of
redact = B.redact
STD = CB.STD
cp_lower_one_sided = CB.cp_lower_one_sided
cp_upper_one_sided = CB.cp_upper_one_sided

OURS_ALL_TXT = gc.OURS_ALL_TXT
THEIRS_ALL_TXT = gc.THEIRS_ALL_TXT

OWNCALL = "PD2FZ"   # NFR-021 exception, pre-registered (Sec.0.2)

# ---- Sec.4 ROW 0b pins -------------------------------------------------------
EXPECTED_OURS_RX = 64417
EXPECTED_OURS_TX = 0
EXPECTED_THEIRS_RX = 43423
EXPECTED_THEIRS_TX = 0

EXPECTED_SHAPE_OURS = {
    "2tok_bracket_first": 177,
    "2tok_bracket_second": 18,
    "3tok_dest_resolved": 293,
    "3tok_dest_unresolved": 2640,
    "3tok_src": 1206,
    "other": 9,
}
EXPECTED_SHAPE_OURS_TOTAL = 4343
EXPECTED_SHAPE_THEIRS_TOTAL = 2867
EXPECTED_SHAPE_THEIRS_DEST = 1805          # 3tok_dest_resolved + 3tok_dest_unresolved, theirs side
EXPECTED_SHAPE_THEIRS_DEST_RESOLVED = 626

# ---- Sec.4 ROW 0c pins -------------------------------------------------------
EXPECTED_N_DISTINCT_CALLS = 11233
EXPECTED_N_OCCUPIED_CODES = 3848
EXPECTED_OCCUPANCY_HIST = {1: 714, 2: 1009, 3: 914, 4: 645, 5: 339, 6: 153, 7: 40, 8: 22, 9: 10, 10: 2}
EXPECTED_OTHER_COLLIDING = 8               # bucket(OWNCALL) - 1
EXPECTED_HASHED_REFS_TOTAL = 1553          # theirs resolved bracket names, n22 computable
EXPECTED_HASHED_REFS_CARRYING_OWN_CODE = 0

# ---- Sec.4 ROW 0e pins -------------------------------------------------------
EXPECTED_TWO_TOKEN_COUNT = 195             # 177 + 18
EXPECTED_THREE_TOKEN_COUNT = 4146

# =============================================================================
# Sec.0.2 population classification (ROW 0b) -- NOT shipped as code in the spec,
# QA's own derivation of the shape table, transcribed to match the drafting
# probe's documented method (bracket-token = a full `^<[^>]*>$` token; unresolved
# marker = `^<\.*>$`). Verified below against the pinned EXPECTED_* constants.
# =============================================================================
_BRACKET_TOKEN_RE = re.compile(r"^<[^>]*>$")
_UNRESOLVED_RE = re.compile(r"^<\.*>$")


def bracket_positions(msg: str):
    return [i for i, t in enumerate(msg.split()) if _BRACKET_TOKEN_RE.fullmatch(t)]


def classify_shape(msg: str):
    """One of Sec.0.2's six shape labels, or None if not a single-bracket decode."""
    toks = msg.split()
    br = bracket_positions(msg)
    if len(br) != 1:
        return None
    pos = br[0]
    ntok = len(toks)
    if ntok == 2 and pos == 0:
        return "2tok_bracket_first"
    if ntok == 2 and pos == 1:
        return "2tok_bracket_second"
    if ntok == 3 and pos == 0:
        return "3tok_dest_unresolved" if _UNRESOLVED_RE.fullmatch(toks[0]) else "3tok_dest_resolved"
    if ntok == 3 and pos == 1:
        return "3tok_src"
    return "other"


# ---- "distinct plain callsign" extraction, ported verbatim from the drafting ----
# probe's filter (Architect, artefacts/2026-08-27-route5-probe/probe_route5_exposure.py)
# so the 11,233/3,848/histogram pins reproduce exactly. Deliberately LOOSER than
# common_b1.is_callsign_token (no NONCALL/GRID exclusion, no alpha requirement) --
# that is what the pinned Sec.0.2 numbers were measured with.
_PLAIN_CALL_RE = re.compile(r"^[A-Z0-9/]{3,11}$")


def is_plain_call_loose(t: str) -> bool:
    return (not t.startswith("<")) and bool(_PLAIN_CALL_RE.fullmatch(t)) and any(c.isdigit() for c in t)


def distinct_plain_calls(ours_rows, theirs_rows):
    calls = set()
    for rows in (ours_rows, theirs_rows):
        for r in rows:
            for t in r["message_norm"].split():
                if is_plain_call_loose(t):
                    calls.add(t)
    return calls


def occupancy_by_n12(calls):
    """{n12: [call, call, ...]} for every call whose hash resolves, sorted at
    construction (hash-randomised-iteration hazard on the board)."""
    by12: dict = {}
    for c in sorted(calls):
        h = n22_of(c)
        if h is None:
            continue
        by12.setdefault(n12_of(h), []).append(c)
    return by12


# =============================================================================
# Sec.3.1 -- transcribed from QsoAnswererService.cs:1631-1645, :1079.
# =============================================================================
def try_parse_message(msg):
    """Transcription of QsoAnswererService.TryParseMessage (C#:1631-1645).
    C# splits on ' ' with RemoveEmptyEntries after Trim(); str.split() is
    equivalent for these inputs. Returns None where C# returns false."""
    parts = msg.strip().split()
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]   # dest, src, payload
    return None


def to_us_current(msg, ours):
    """Transcription of QsoAnswererService.cs:1079 --
    dest.Equals(ours, StringComparison.OrdinalIgnoreCase)."""
    p = try_parse_message(msg)
    if p is None:
        return False
    return p[0].upper() == ours.upper()


# =============================================================================
# Sec.3.2 -- L1+L2 only; L3 needs a hash the ABI does not carry.
# =============================================================================
def to_us_l1l2(msg, ours):
    """L1: accept the 2-token Type-4 shorthand. L2: strip one bracket pair
    from dest before comparing. NO hash is consulted -- this is exactly the
    part of route 5 that needs no native change."""
    parts = msg.strip().split()
    if len(parts) == 2:
        dest, src, payload = parts[0], parts[1], ""
    elif len(parts) == 3:
        dest, src, payload = parts[0], parts[1], parts[2]
    else:
        return False
    if len(dest) >= 2 and dest[0] == '<' and dest[-1] == '>':
        dest = dest[1:-1]
    if dest == '' or set(dest) == {'.'}:
        return False                      # the <...> marker is not a callsign
    return dest.upper() == ours.upper()


# ---- QA's own two single-axis variants for G2 (see module docstring) --------
def to_us_l1_only(msg, ours):
    """L1 (2-token acceptance) WITHOUT L2 (no bracket strip) -- dest compared
    literally. Isolates what accepting the 2-token shorthand buys on its own."""
    parts = msg.strip().split()
    if len(parts) == 2:
        dest = parts[0]
    elif len(parts) == 3:
        dest = parts[0]
    else:
        return False
    return dest.upper() == ours.upper()


def to_us_l2_only(msg, ours):
    """L2 (bracket strip) WITHOUT L1 -- still requires exactly 3 tokens.
    Isolates what stripping brackets buys on its own."""
    parts = msg.strip().split()
    if len(parts) != 3:
        return False
    dest = parts[0]
    if len(dest) >= 2 and dest[0] == '<' and dest[-1] == '>':
        dest = dest[1:-1]
    if dest == '' or set(dest) == {'.'}:
        return False
    return dest.upper() == ours.upper()


# =============================================================================
# Sec.3.3 -- the own-hash predicate (L3), evaluated against reference ground truth.
# =============================================================================
def hash_dest_n12(msg, theirs_name):
    """The 12-bit code actually carried in the message's dest slot.
    theirs_name is the reference decoder's resolution of that slot; where the
    reference did not resolve it, this returns None and the decode is UNKNOWN.
    HK-026: our own decoder may NOT be used to bound its own blind spot, so
    the code is derived from the wider-aperture instrument, never from ours."""
    if theirs_name is None:
        return None
    h = n22_of(theirs_name)
    return None if h is None else n12_of(h)


def to_us_l3(msg, ours, theirs_name):
    """Route 5's rule: the dest slot's 12-bit code equals our own. TRUE
    POSITIVE iff theirs_name == ours; FALSE POSITIVE iff it fires and
    theirs_name != ours."""
    n12 = hash_dest_n12(msg, theirs_name)
    if n12 is None:
        return None                        # UNKNOWN -- never silently False
    h = n22_of(ours)
    return h is not None and n12_of(h) == n12


# =============================================================================
# Input identity (ROW 0a)
# =============================================================================
def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rx_tx_counts(path: str):
    rx = tx = 0
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            tok = line.split()
            if len(tok) < 3:
                continue
            if tok[2] == "Rx":
                rx += 1
            elif tok[2] == "Tx":
                tx += 1
    return rx, tx


# =============================================================================
# G3 reference pairing -- reuses CB.slot / CB.build_theirs_index / CB.best_match
# verbatim (Sec.2). Restricted to OUR hashed-dest (3-token, bracket-at-pos0)
# decodes; the theirs_index itself is position-agnostic (see module docstring
# for why that reuse is safe in practice).
# =============================================================================
def hashed_dest_rows(ours_rows):
    """All ours rows classified 3tok_dest_resolved or 3tok_dest_unresolved."""
    out = []
    for r in ours_rows:
        shp = classify_shape(r["message_norm"])
        if shp in ("3tok_dest_resolved", "3tok_dest_unresolved"):
            toks = r["message_norm"].split()
            out.append({"row": r, "shape": shp, "dest_raw": toks[0], "others": (toks[1], toks[2]), "ntok": 3})
    return out


def resolved_hash_refs(rows):
    """All single-bracket decodes (ANY position/shape) whose bracket token is
    RESOLVED and charset-valid -- reproduces the drafting probe's later 'refs'
    loop (Sec.0.2's 'Observed hashed references carrying our code: 0 of 1,553'),
    which does not restrict to the dest position. Returns the list of resolved
    names (real callsign strings -- caller must not let these leave process
    memory except as counts)."""
    out = []
    for r in rows:
        toks = r["message_norm"].split()
        br = bracket_positions(r["message_norm"])
        if len(br) != 1:
            continue
        tok = toks[br[0]]
        if _UNRESOLVED_RE.fullmatch(tok):
            continue
        name = tok[1:-1]
        if n22_of(name) is None:
            continue
        out.append(name)
    return out


def pair_hashed_dest_to_reference(hd_rows, theirs_index):
    """For each hashed-dest ours row, finds the nearest-frequency reference
    match on the same (ts, others, ntok) key (CB.best_match). Returns a list
    of dicts with 'theirs_name' (str or None -- None means either no match was
    found at all, or the match itself was unresolved) and 'matched' (bool,
    whether ANY reference row was found regardless of resolution)."""
    out = []
    for item in hd_rows:
        r = item["row"]
        m = CB.best_match(r, item["others"], item["ntok"], theirs_index)
        theirs_name = None
        if m is not None and m["kind"] == "resolved":
            theirs_name = m["payload"]
        out.append({
            "ts": r["ts"], "freq_hz": r["freq_hz"], "message_norm": r["message_norm"],
            "shape": item["shape"], "matched": m is not None, "theirs_name": theirs_name,
        })
    return out
