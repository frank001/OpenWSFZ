"""FP-MARK ROW 0b -- identifiability: share of real decodes with BOTH a grid present
AND a resolved prefix, over the pinned seven-corpus population.

Architect ruling, qa/rr-study/2026-09-05-1640-architect-to-qa-ruling-fp-mark-row0-block.md
Sec 3/7: run ROW 0b alone, ROW 0a/1/2/3/4 stay blocked (no grid->geo classifier exists).
This script does NOT classify a grid geographically in any way -- it only detects grid
PRESENCE (a token-shape check, not a region lookup) and resolves a callsign PREFIX (the
existing, real direction the project's region store already supports).

Every non-mechanical piece below is a faithful, cited port of production C# -- not a new
instrument:
  - is_grid_square()              <- src/OpenWSFZ.Web/WebApp.cs:1645-1649 (IsGridSquare)
  - strip_portable_suffix()       <- src/OpenWSFZ.Abstractions/CallsignTokenHelpers.cs:18-22
  - is_candidate_callsign_token() <- src/OpenWSFZ.Ft8/Ft8Decoder.cs:912-913
  - extract_primary_callsign_token() <- src/OpenWSFZ.Ft8/Ft8Decoder.cs:885-908
  - try_match_prefix()            <- src/OpenWSFZ.Daemon/CallsignRegionStore.cs:48-73
      (longest ordinal [PrefixStart, PrefixEnd] range match)

Inputs (both pinned by SHA256 in the emitted report -- HK-021(p), per the ruling):
  - The seven live corpora: artefacts/*/OpenWSFZ ALL.TXT (exactly seven paths match this
    exact filename anywhere under artefacts/, confirmed by `find artefacts -name
    "OpenWSFZ ALL.TXT"` -- a closed, mechanical population, not a hand-picked list).
  - The real, non-seed region table at %APPDATA%\\OpenWSFZ\\callsign-regions.json (29,013
    entries; every region file *committed* to this repo is the 39-entry seed instead).

NFR-021: this script reads real callsigns from artefacts/ (blanket-gitignored) and prints
ONLY aggregate counts/rates to stdout. No callsign, message, or grid value is written to
any committed file.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "qa" / "rr-study" / "harness"))
from common import parse_all_txt  # noqa: E402

REGION_TABLE_PATH = Path(os.environ.get("APPDATA", "")) / "OpenWSFZ" / "callsign-regions.json"

RRR_TOKENS = {"RRR", "73", "RR73"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_grid_square(s: str) -> bool:
    """Port of WebApp.cs:1645-1649 IsGridSquare -- a token-SHAPE check, no geography."""
    if len(s) not in (4, 6):
        return False
    if not (s[0].isalpha() and s[1].isalpha() and s[2].isdigit() and s[3].isdigit()):
        return False
    if len(s) == 6 and not (s[4].isalpha() and s[5].isalpha()):
        return False
    return True


def strip_portable_suffix(token: str) -> str:
    """Port of CallsignTokenHelpers.cs:18-22."""
    idx = token.find("/")
    return token if idx < 0 else token[:idx]


def is_candidate_callsign_token(token: str) -> bool:
    """Port of Ft8Decoder.cs:912-913 IsCandidateCallsignToken."""
    return len(token) > 0 and token[0] != "<" and token not in RRR_TOKENS


def extract_primary_callsign_token(text: str) -> str | None:
    """Port of Ft8Decoder.cs:885-908 ExtractPrimaryCallsignToken."""
    tokens = text.split(" ")
    if not tokens:
        return None
    if tokens[0] == "CQ":
        if len(tokens) in (2, 3):
            candidate = tokens[1]
        elif len(tokens) >= 4:
            candidate = tokens[2]
        else:
            candidate = None
        if candidate is not None and is_candidate_callsign_token(candidate):
            return strip_portable_suffix(candidate)
        return None
    if len(tokens) >= 2 and is_candidate_callsign_token(tokens[1]):
        return strip_portable_suffix(tokens[1])
    if len(tokens) >= 1 and is_candidate_callsign_token(tokens[0]):
        return strip_portable_suffix(tokens[0])
    return None


class RegionIndex:
    """Port of CallsignRegionStore.cs:48-73 TryMatchPrefix, indexed for speed.

    Groups entries by PrefixStart length and binary-searches each group's sorted
    PrefixStart list -- behaviourally identical to the C# linear scan (same ordinal
    range test, same longest-match tie-break), just not O(n) per lookup against
    29,013 entries.
    """

    def __init__(self, entries: list[dict]):
        import bisect
        self._bisect = bisect
        by_len: dict[int, list[tuple[str, str]]] = {}
        for e in entries:
            ps, pe = e["prefixStart"], e["prefixEnd"]
            if len(ps) == 0 or len(pe) != len(ps):
                continue  # malformed-entry guard, same as the C# TryMatchPrefix
            by_len.setdefault(len(ps), []).append((ps, pe))
        for lst in by_len.values():
            lst.sort()
        self._by_len = by_len
        self._lengths_desc = sorted(by_len.keys(), reverse=True)

    def resolves(self, token: str) -> bool:
        token = token.upper()
        for length in self._lengths_desc:
            if len(token) < length:
                continue
            candidate = token[:length]
            lst = self._by_len[length]
            i = self._bisect.bisect_right(lst, (candidate, "￿")) - 1
            if 0 <= i < len(lst):
                ps, pe = lst[i]
                if ps <= candidate <= pe:
                    return True
        return False


def main() -> None:
    if not REGION_TABLE_PATH.is_file():
        print(f"FATAL: region table not found at {REGION_TABLE_PATH}", file=sys.stderr)
        sys.exit(1)

    region_sha256 = sha256_of(REGION_TABLE_PATH)
    region_stat = REGION_TABLE_PATH.stat()
    region_data = json.loads(REGION_TABLE_PATH.read_text(encoding="utf-8"))
    entries = region_data["entries"]
    index = RegionIndex(entries)

    corpus_paths = sorted(REPO_ROOT.glob("artefacts/*/OpenWSFZ ALL.TXT"))

    print("=== FP-MARK ROW 0b -- pinned inputs (HK-021(p)) ===")
    print(f"region table path   : {REGION_TABLE_PATH}")
    print(f"region table sha256 : {region_sha256}")
    print(f"region table size   : {region_stat.st_size} bytes")
    print(f"region table mtime  : {datetime.fromtimestamp(region_stat.st_mtime, tz=timezone.utc).isoformat()}")
    print(f"region entries      : {len(entries)}")
    print()
    print(f"seven-corpus manifest ({len(corpus_paths)} files matched 'artefacts/*/OpenWSFZ ALL.TXT'):")
    corpus_shas = {}
    for p in corpus_paths:
        sha = sha256_of(p)
        corpus_shas[str(p.relative_to(REPO_ROOT))] = sha
        print(f"  {p.relative_to(REPO_ROOT)}  sha256={sha}  size={p.stat().st_size}")
    print()

    total_decodes = 0
    total_skipped_lines = 0
    n_grid = 0
    n_resolved = 0
    n_both = 0
    per_file = []

    for p in corpus_paths:
        records, skipped = parse_all_txt(p)
        f_total = len(records)
        f_grid = 0
        f_resolved = 0
        f_both = 0
        for rec in records:
            tokens = rec.message.split(" ")
            grid = bool(tokens) and is_grid_square(tokens[-1])
            primary = extract_primary_callsign_token(rec.message)
            resolved = primary is not None and index.resolves(primary)
            if grid:
                f_grid += 1
            if resolved:
                f_resolved += 1
            if grid and resolved:
                f_both += 1
        total_decodes += f_total
        total_skipped_lines += skipped
        n_grid += f_grid
        n_resolved += f_resolved
        n_both += f_both
        per_file.append((str(p.relative_to(REPO_ROOT)), f_total, skipped, f_grid, f_resolved, f_both))

    print("=== Per-file (FT8 decodes, non-FT8/malformed lines skipped) ===")
    for name, tot, skip, grid, res, both in per_file:
        pct = (100.0 * both / tot) if tot else 0.0
        print(f"  {name}")
        print(f"    decodes={tot} skipped_lines={skip} grid_present={grid} prefix_resolved={res} evaluable(both)={both} ({pct:.2f}%)")

    print()
    print("=== ROW 0b -- AGGREGATE, decode-level ===")
    print(f"total real FT8 decodes (7 corpora) : {total_decodes}")
    print(f"total non-FT8/malformed lines skipped : {total_skipped_lines}")
    print(f"grid present (last-token shape check) : {n_grid} ({100.0*n_grid/total_decodes:.2f}%)")
    print(f"prefix resolved (real region table)   : {n_resolved} ({100.0*n_resolved/total_decodes:.2f}%)")
    print(f"EVALUABLE (grid present AND prefix resolved) : {n_both} ({100.0*n_both/total_decodes:.4f}%)")
    bar = 40.0
    pct_both = 100.0 * n_both / total_decodes
    print()
    if pct_both < bar:
        print(f"ROW 0b FIRES: {pct_both:.4f}% < {bar}% bar -> STOP, pause and hand back (per spec).")
    else:
        print(f"ROW 0b does NOT fire: {pct_both:.4f}% >= {bar}% bar.")


if __name__ == "__main__":
    main()
