#!/usr/bin/env python3
"""Task 4 (FP spec Sec.6) -- live-band FP proxy by callsign recurrence. OBSERVATION ONLY.

NO PRE-REGISTERED RULE GOVERNS THIS TASK AND NONE SHOULD -- there is no oracle for a live
band. Like Sec.8 of the drift-screen PASS report, this must not acquire verdict status by
repetition.

PREMISE: real stations transmit repeatedly across cycles; a false decode is typically a
one-off.

METHOD: on artefacts/20260803_live_run_1713/, build the same "matched in both" / "8080 only"
decode populations as the PASS report Sec.8 (exact (cycle slot, message) match, hashed
callsigns normalised for the equality check). For each decode in each population, extract
identity token(s) from the OpenWSFZ message text, and count the number of DISTINCT CYCLES each
identity appears in within that population. Compare the two recurrence distributions
(especially the singleton fraction).

PRIVACY (NFR-021 / GDPR callsign policy): this script reads real off-air callsigns from
ALL.TXT, which real people's names/calls appear in. NO CALLSIGN TEXT IS EVER PRINTED, WRITTEN,
OR RETAINED as plaintext beyond the in-memory extraction step -- every identity is SHA-256
hashed (truncated) immediately after extraction and only the hash is used for grouping,
printing, or writing to any output file. This is deliberately stricter than drift_screen.py's
"never reads ALL.TXT" rule, because this task's method requires reading message text; the
mitigation is anonymising every extracted identity at first use, not avoiding the file.

ASCII-only output (HK-009).
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

_HARNESS = Path(__file__).resolve().parent / "harness"
sys.path.insert(0, str(_HARNESS.parent))
from harness.common import parse_all_txt  # noqa: E402

CORPUS = Path("artefacts/20260803_live_run_1713")

# ---------------------------------------------------------------------------
# Message-token classification (best-effort; disclosed as such in the report)
# ---------------------------------------------------------------------------
_GRID_RE = re.compile(r"^[A-R]{2}\d{2}([A-X]{2})?$")
_REPORT_RE = re.compile(r"^R?[+-]\d{2}$")
_TERMINAL_TOKENS = {"RR73", "RRR", "73", "RO"}
_HASH_RESOLVED_RE = re.compile(r"^<([^<>]+)>$")
_HASH_UNRESOLVED = "<...>"
_CALLSIGN_LIKE_RE = re.compile(r"^[A-Z0-9/]{3,12}$")


def _looks_like_callsign(tok: str) -> bool:
    if not _CALLSIGN_LIKE_RE.match(tok):
        return False
    return any(c.isdigit() for c in tok)


def extract_identities(message: str) -> list[str]:
    """Best-effort extraction of callsign-shaped identity tokens from an FT8 message.

    Returns PLAINTEXT identities -- caller MUST hash immediately, never print/store raw.
    """
    tokens = message.split()
    if tokens and tokens[0] == "CQ":
        tokens = tokens[1:]
        # Directed CQ qualifier ("CQ DX CALL GRID", "CQ POTA CALL GRID"): a short
        # all-alnum token immediately before a callsign-shaped token that is not
        # itself grid-shaped.
        if (len(tokens) >= 2 and re.fullmatch(r"[A-Z0-9]{2,4}", tokens[0])
                and not _GRID_RE.match(tokens[0]) and _looks_like_callsign(tokens[1])):
            tokens = tokens[1:]

    out = []
    for t in tokens:
        if _GRID_RE.match(t) or _REPORT_RE.match(t) or t in _TERMINAL_TOKENS:
            continue
        if t == _HASH_UNRESOLVED:
            continue  # unresolved hash reference carries no identity
        m = _HASH_RESOLVED_RE.match(t)
        if m:
            out.append(m.group(1))
            continue
        if _looks_like_callsign(t):
            out.append(t)
    return out


def _anon(identity: str) -> str:
    """SHA-256 hash, truncated -- the ONLY form any identity may take past this point."""
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


_HASHTOK_RE = re.compile(r"<[^<>]*>")


def normalise_for_match(message: str) -> str:
    """Collapse any bracketed hash token (resolved or not) to a canonical marker, so
    formatting differences between the two decoders' hash-resolution state don't split an
    otherwise-identical decode into two different keys. Mirrors the PASS report Sec.8
    finding (57.11% -> 58.66% after this normalisation)."""
    return _HASHTOK_RE.sub("<HASH>", message)


def main() -> int:
    corpus = CORPUS.resolve()
    print("=" * 78)
    print("TASK 4 -- live-band FP proxy: callsign-recurrence, OBSERVATION ONLY, NO VERDICT")
    print(f"corpus : {corpus}")
    print("=" * 78 + "\n")

    owsfz_recs, owsfz_skipped = parse_all_txt(corpus / "owsfz" / "ALL.TXT")
    wsjtx_recs, wsjtx_skipped = parse_all_txt(corpus / "wsjt-x" / "ALL.TXT")
    print(f"owsfz: {len(owsfz_recs)} parsed, {owsfz_skipped} skipped")
    print(f"wsjtx: {len(wsjtx_recs)} parsed, {wsjtx_skipped} skipped")

    wsjtx_keys = {(r.utc, normalise_for_match(r.message)) for r in wsjtx_recs}

    matched, only_8080 = [], []
    for r in owsfz_recs:
        key = (r.utc, normalise_for_match(r.message))
        (matched if key in wsjtx_keys else only_8080).append(r)

    print(f"\nmatched in both : {len(matched)}")
    print(f"8080 only       : {len(only_8080)}")
    print("(PASS report Sec.8, same corpus, reported 24,480 / 37,511 over 'the window both "
          "files cover' -- this run uses the full corpus and the counts above are expected to "
          "differ slightly, not be identical.)")

    def recurrence_stats(records, label: str):
        cycles_per_identity: dict[str, set] = defaultdict(set)
        n_no_identity = 0
        for r in records:
            ids = extract_identities(r.message)
            if not ids:
                n_no_identity += 1
                continue
            for ident in ids:
                cycles_per_identity[_anon(ident)].add(r.utc)
        counts = [len(v) for v in cycles_per_identity.values()]
        n_ident = len(counts)
        singleton = sum(1 for c in counts if c == 1) / n_ident if n_ident else float("nan")
        print(f"\n--- {label} ---")
        print(f"decodes: {len(records)}  decodes with no extractable identity: {n_no_identity} "
              f"({n_no_identity / len(records) * 100 if records else 0:.2f}%)")
        print(f"distinct identities: {n_ident}")
        print(f"singleton fraction (appears in exactly 1 cycle): {singleton:.4f}")
        if counts:
            import statistics
            print(f"cycles-per-identity: median={statistics.median(counts)} "
                  f"mean={statistics.mean(counts):.2f} max={max(counts)}")
            # Histogram buckets, counts only -- no identities.
            buckets = {"1": 0, "2": 0, "3-5": 0, "6-10": 0, ">10": 0}
            for c in counts:
                if c == 1:
                    buckets["1"] += 1
                elif c == 2:
                    buckets["2"] += 1
                elif c <= 5:
                    buckets["3-5"] += 1
                elif c <= 10:
                    buckets["6-10"] += 1
                else:
                    buckets[">10"] += 1
            for k, v in buckets.items():
                print(f"  cycles={k:>4}: {v:>6} identities ({v / n_ident * 100:.1f}%)")
        return singleton, n_ident

    singleton_only8080, n_only8080 = recurrence_stats(only_8080, "8080-ONLY decodes")
    singleton_matched, n_matched = recurrence_stats(matched, "MATCHED-IN-BOTH decodes")

    print("\n" + "-" * 60)
    print("SUMMARY (observation only -- no verdict)")
    print("-" * 60)
    print(f"singleton fraction, 8080-only      : {singleton_only8080:.4f} (n identities={n_only8080})")
    print(f"singleton fraction, matched-in-both : {singleton_matched:.4f} (n identities={n_matched})")
    print(f"delta (8080-only minus matched)     : {singleton_only8080 - singleton_matched:+.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
