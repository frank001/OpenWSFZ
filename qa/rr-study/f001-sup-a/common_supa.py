"""F-001 SUP-A -- shared helpers.

Spec: qa/rr-study/2026-08-30-1031-architect-to-qa-spec-f001-sup-a-unique-match-suppression-sizing.md
(as amended, commit a6a1b2f).

Reuse, not re-implementation (HK-018 / Sec.3 "reuse it, do not re-implement"):
  - common_arm1.SimTable / EMPTY / TOMBSTONE / OCCUPIED / n22_of  -- the fill-
    and-freeze hash table simulator, faithful to ft8_shim.c:631-700, and the
    22-bit FT8 callsign hash (message.c:557-590).
  - common_b1.is_callsign_token / redact -- the plaintext-callsign-token shape
    predicate and the NFR-021 redaction helper.
  - common_arm1b.slot() -- the type-4 (12-bit-path) population predicate,
    ARM 1B's precedented, DISCLOSED-AS-A-LOWER-BOUND method for identifying
    which hash-bracket lookups are on the 12-bit path from plaintext alone.
  - gap-census-a/common.parse_all_txt -- the canonical ALL.TXT row parser.

QA NOTE ON A SPEC GAP (HK-025, filed in the SUP-A report, not hidden here):
SUP-A's Sec.3.1 describes the arrival-stream extractor (feeds hash_table_add)
but never ships a predicate for identifying which LOOKUP events are on the
12-bit path in the first place -- Sec.1's own HK-021(x) note anticipates the
danger ("a 22-bit lookup with an ambiguous 12-bit code would trip a naively
scoped predicate") but does not supply the filter. Checked against source
(message.c:594-613, add_brackets/lookup_callsign): a 12-bit-resolved and a
22-bit-resolved slot render IDENTICALLY ("<CALLSIGN>" or "<...>"), and no
artefact available to QA (ALL.TXT, or the richer L2_*.json decode dumps used
by ARM1B) carries the message's i3/hash-type. This is the SAME limitation
ARM1B disclosed and solved with a heuristic, not a new one. This module
reuses that exact, precedented, disclosed-as-imperfect solution rather than
inventing a fresh one: `slot()`'s `nonstd` flag (Sec.3.1 of the ARM1B spec)
is the 12-bit-path indicator, and it undercounts (a lower bound), never
overcounts, by construction (a nonstandard callsign that happens to look
standard is missed, not a standard one wrongly flagged nonstandard).

NFR-021: real callsign strings live in memory only. Nothing that reaches
result.json or the report is anything but counts, cycle timestamps, and
sha256[:6]-redacted CS-xxxxxx tokens (common_b1.redact).
"""
from __future__ import annotations

import datetime
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ARM1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1")
ARM1B_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "f001-d3-arm1b")
B1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "b1-coverage-a")
G2A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "g2a-remeasure-a")
GAP_CENSUS_A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "gap-census-a")
for p in (ARM1_DIR, ARM1B_DIR, B1_DIR, G2A_DIR, GAP_CENSUS_A_DIR, os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

import common as gc          # noqa: E402  (gap-census-a: parse_all_txt)
import common_arm1 as A      # noqa: E402  (SimTable / EMPTY / TOMBSTONE / OCCUPIED / n22_of)
import common_arm1b as AB    # noqa: E402  (slot() -- 12-bit-path population predicate)
import common_b1 as B        # noqa: E402  (is_callsign_token / redact)

parse_all_txt = gc.parse_all_txt
SimTable = A.SimTable
EMPTY, TOMBSTONE, OCCUPIED = A.EMPTY, A.TOMBSTONE, A.OCCUPIED
n22_of = A.n22_of
is_callsign_token = B.is_callsign_token
redact = B.redact
slot = AB.slot

CORPORA = {
    "S-17M": dict(band="17m", path="artefacts/20260808_live_run_1154-8080-17m/owsfz/ALL.TXT",
                  log="artefacts/20260808_live_run_1154-8080-17m/owsfz/openswfz-20260808T115445Z.log",
                  declared_span_h=7.73, role="primary"),
    "S-80M": dict(band="80m", path="artefacts/20260809_live_run_0155-8080-80m/owsfz/ALL.TXT",
                  log="artefacts/20260809_live_run_0155-8080-80m/owsfz/openswfz-20260809T015438Z.log",
                  declared_span_h=8.27, role="primary"),
    "S-20M": dict(band="20m", path="artefacts/20260808_live_run_0016-8080/owsfz/ALL.TXT",
                  log="artefacts/20260808_live_run_0016-8080/owsfz/openswfz-20260808T001605Z.log",
                  declared_span_h=11.48, role="primary_prefix8h", saturates_h=7.82,
                  # QA correction: ALL.TXT starts at 000845, two process restarts
                  # (000842.log, 001357.log, 19 cycle-lines total) BEFORE the daemon
                  # settled into the process the pinned log (001605Z) covers. The
                  # real g_session_hash_table is a static, zero-initialised ONCE per
                  # PROCESS start (ft8_shim.c) -- it does not survive a restart. ROW
                  # 0b's positive control must therefore start its 256-slot
                  # simulation at the SAME process boundary the observed log does,
                  # not at ALL.TXT's first row, or the comparison is not apples-to-
                  # apples. Sec.5's readings are UNAFFECTED (they use the full
                  # declared 11.48h span, matching Sec.2.1's own pin).
                  row0b_start_ts="260808_001605"),
    "L-20M": dict(band="20m", path="artefacts/20260731_live_run_2004-8080/owsfz/ALL.TXT",
                  log=None, declared_span_h=43.79, role="contrast"),
}


# ---- Sec.3.2 (Amendment 1): 12-bit chain walk, first + n_matches + most_recent
def lookup12_multiplicity(tbl, n12: int):
    """ft8_shim.c:637-655 at sh=10, plus Amendment 1's recency field. Faithful
    re-derivation of the spec's Sec.3.2 listing against the SAME SimTable
    object model common_arm1.SimTable already implements (state/hash/
    callsign/last_used arrays, EMPTY-breaks-the-scan semantics). Does NOT
    refresh last_used (the Sec.3.2 trap: only SimTable.add() may do that)."""
    sh = 10
    h10 = (n12 >> (12 - sh)) & 0x3FF
    idx = (h10 * 23) % tbl.n
    first, n_matches = None, 0
    best_idx, best_used = None, None
    for _ in range(tbl.n):
        st = tbl.state[idx]
        if st == EMPTY:
            break
        if st == OCCUPIED and ((tbl.hash[idx] & 0x3FFFFF) >> sh) == n12:
            n_matches += 1
            if first is None:
                first = tbl.callsign[idx]
            if best_used is None or tbl.last_used[idx] > best_used:
                best_used, best_idx = tbl.last_used[idx], idx
        idx = (idx + 1) % tbl.n
    most_recent = tbl.callsign[best_idx] if best_idx is not None else None
    return first, n_matches, most_recent


def suppressed(n_matches: int) -> bool:
    return n_matches >= 2


def diverges(first, most_recent) -> bool:
    return most_recent != first


# ---- ts parsing / cycle-index arithmetic (ROW 0b) --------------------------
_TS_RE = re.compile(r"^(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$")


def ts_to_dt(ts: str) -> datetime.datetime:
    m = _TS_RE.match(ts)
    if not m:
        raise ValueError("unrecognised ts %r" % ts)
    yy, mo, dd, hh, mi, ss = (int(x) for x in m.groups())
    return datetime.datetime(2000 + yy, mo, dd, hh, mi, ss)


def cycle_index(ts: str, start_dt: datetime.datetime, cadence_s: int = 15) -> int:
    """1-based absolute cycle number at 15s cadence from session start,
    matching the real daemon's own per-cycle log line numbering (verified:
    total logged cycles == round(span_hours*3600/15) within 1, for all three
    primary corpora)."""
    dt = ts_to_dt(ts)
    delta = (dt - start_dt).total_seconds()
    return round(delta / cadence_s) + 1


# ---- observed freeze cycle from an openswfz-*.log ---------------------------
_CYCLE_LOG_RE = re.compile(r"Cycle (\S+): hashTableRejectCount=(\d+)")


def observed_freeze_cycle(log_path: str):
    """First 1-based cycle-log-line index at which hashTableRejectCount > 0,
    and the total cycle-log-line count (== total cycles in the session, log
    records every 15s tick whether or not it decoded anything)."""
    n = 0
    freeze = None
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _CYCLE_LOG_RE.search(line)
            if not m:
                continue
            n += 1
            if freeze is None and int(m.group(2)) > 0:
                freeze = n
    return freeze, n
