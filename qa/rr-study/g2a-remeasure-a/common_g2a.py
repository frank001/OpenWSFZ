"""G2A-REMEASURE-A -- shared population/parsing helpers.

Spec: qa/rr-study/2026-08-23-2127-architect-to-qa-spec-g2a-remeasure-a.md
Amendment: qa/rr-study/2026-08-25-1550-architect-to-qa-null-validity-finding-and-g2a-remeasure-amendment.md

Reuses gap-census-a's Population/classify_partition/bootstrap machinery
verbatim (imported, not copied -- HK-018) since arm #2 explicitly inherits
arm #1's bucket definitions and null construction (spec Sec.0, running
order). Only the INPUT side differs: L1/L2 come from decode_corpus.py's
raw-decode JSON dumps (artefacts/, gitignored) rather than from ALL.TXT.

NFR-021: decode_corpus.py's JSON dumps (message text) live under
artefacts/2026-08-25-g2a-remeasure-a/ only. This module reads them, derives
message_norm/has_hash via gap-census-a's own normalise_text/has_hash_marker,
and discards raw text immediately -- identical discipline to
gap-census-a/common.py's own parse_all_txt.
"""
from __future__ import annotations

import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAP_CENSUS_A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "gap-census-a")
sys.path.insert(0, GAP_CENSUS_A_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as gc  # noqa: E402  (gap-census-a/common.py)

CORPUS_DIR = os.path.join(REPO_ROOT, "artefacts", "20260803_live_run_1713")
L0_OURS_ALL_TXT = os.path.join(CORPUS_DIR, "owsfz", "ALL.TXT")
THEIRS_ALL_TXT = os.path.join(CORPUS_DIR, "wsjt-x", "ALL.TXT")
OURS_WAV_DIR = os.path.join(CORPUS_DIR, "owsfz", "wav")
EXPECTED_WAV_COUNT = 4971

DECODE_DUMP_DIR = os.path.join(REPO_ROOT, "artefacts", "2026-08-25-g2a-remeasure-a")
L1_JSON = os.path.join(DECODE_DUMP_DIR, "L1_decodes.json")
L2_RUN1_JSON = os.path.join(DECODE_DUMP_DIR, "L2_run1_decodes.json")
L2_RUN2_JSON = os.path.join(DECODE_DUMP_DIR, "L2_run2_decodes.json")

# Pinned identities (ROW 0a) -- QA-located this session, see the report.
L1_DLL_PATH = r"D:\Projects\claude\OpenWSFZ-8080-capture\libft8.dll"
L1_SHA256 = "f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015"
L1_SHIM_VERSION = 20260033
L2_DLL_PATH = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "libft8.dll")
L2_SHA256 = "bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f"
L2_SHIM_VERSION = 20260046

L1_SNR_EDGES = [-15, -10, -5, 2]  # pinned, never re-derived (gap-census-a Part C)

# 2026-08-25 17:35Z WITHDRAWAL Sec.1 -- gap-census-a's has_hash_marker() is
# `<[^>]*>`, which matches a RESOLVED `<CALL>` exactly as it matches an
# UNRESOLVED `<...>`. ft8_lib's lookup_callsign() (message.c:606/610) emits
# the literal string "<...>" on a failed hash lookup, or add_brackets(c11) --
# an actual resolved callsign, which is never empty and never contains '.'
# -- on success. This predicate isolates the failed-lookup case only. Written
# generally (zero-or-more dots, not exactly three) in case a hash type ever
# emits a differently-sized placeholder; grep of message.c on this tree finds
# only the one literal "<...>" call site (checked this session).
_UNRESOLVED_HASH_RE = re.compile(r"<\.*>")


def has_unresolved_hash_marker(message: str) -> bool:
    return bool(_UNRESOLVED_HASH_RE.search(message))


def load_decode_dump(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rows_from_dump(dump: dict) -> list[dict]:
    """Convert decode_corpus.py's per-decode records into gap-census-a's row
    shape ({ts, snr, dt, freq_hz, message_norm, has_hash}), discarding raw
    message text immediately (NFR-021)."""
    out = []
    for r in dump["records"]:
        msg = r["message"]
        out.append({
            "ts": r["ts"],
            "snr": float(r["snr"]),
            "dt": float(r["dt"]),
            "freq_hz": float(r["freq_hz"]),
            "message_norm": gc.normalise_text(msg),
            "has_hash": gc.has_hash_marker(msg),
        })
    return out


def rows_from_dump_corrected(dump: dict) -> list[dict]:
    """Same shape as rows_from_dump, but `has_hash` is the CORRECTED
    unresolved-only predicate (WITHDRAWAL Sec.1/Sec.4.1), not
    gc.has_hash_marker's any-bracket predicate. The field is still named
    'has_hash' so it drops straight into part_a.run_part_a / partition.py's
    classify_partition unmodified -- neither consumes anything but the
    boolean. Raw message text is discarded immediately, same as
    rows_from_dump (NFR-021)."""
    out = []
    for r in dump["records"]:
        msg = r["message"]
        out.append({
            "ts": r["ts"],
            "snr": float(r["snr"]),
            "dt": float(r["dt"]),
            "freq_hz": float(r["freq_hz"]),
            "message_norm": gc.normalise_text(msg),
            "has_hash": has_unresolved_hash_marker(msg),
        })
    return out


def load_theirs_rows() -> list[dict]:
    return gc.parse_all_txt(THEIRS_ALL_TXT)


def load_l0_ours_rows() -> list[dict]:
    """The historical archived record -- L0, the validity-check reference for
    ROW 0c. Not used as 'ours' in any gated statistic."""
    return gc.parse_all_txt(L0_OURS_ALL_TXT)


def population_for(ours_rows: list[dict]) -> "gc.Population":
    theirs_rows = load_theirs_rows()
    return gc.Population(ours_rows, theirs_rows)
