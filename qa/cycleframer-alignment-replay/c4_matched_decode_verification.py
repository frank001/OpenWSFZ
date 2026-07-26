#!/usr/bin/env python3
"""D-001 C.4 -- Architect's verification of the min-score sweep's decode yield.

WHY THIS EXISTS
---------------
c4_min_score_sweep_analysis.py reports `recov648` -- the count of C.3's 648-message
candidate-generation-gap population that gains ANY candidate at a given K_MIN_SCORE.
Its own closing note is explicit that this is "not the same as a decode", but the
findings doc's verdict ("recovers 16.2% -> 50-51% -> 55-91% -> 58-95%+") reads as a
decode-recovery claim. This script computes the number that was never computed:

    MATCHED = sum over cycles of |our messages INTERSECT WSJT-X messages|

i.e. how many of WSJT-X's 2028 messages we actually decode, per setting. That is the
only quantity that moves the D-001 gap. `total decodes` does not distinguish a
recovered real signal from a CRC-passing false decode; MATCHED does.

It then characterises the unique-to-us population (ours MINUS WSJT-X) on three axes
that discriminate real weak signals from false decodes:

  1. PERSISTENCE  -- share of distinct message texts appearing in >1 cycle. A station
     calling CQ transmits every other cycle; over a 68-cycle (~17 min) corpus real
     traffic repeats. Random CRC collisions never repeat.
  2. SNR          -- median reported SNR. FT8's decode threshold is approx -21 dB; a
     population centred below that is not a population of signals.
  3. CALL REUSE   -- share of unique-to-us messages containing a callsign-shaped token
     that also appears somewhere in the MATCHED (known-real) population.

A fourth axis, message-grammar validity, is computed only to demonstrate that it is
UNINFORMATIVE: the unpacker emits syntactically legal text for any 77-bit payload that
passes CRC, so ~98% grammar validity is guaranteed and is not evidence of authenticity.

CAVEAT stated plainly: WSJT-X is a reference, not absolute ground truth, so
"unique-to-us" is not identically "false". The three axes above are strong joint
evidence, not proof. The decisive test is a noise-only decode run (see the ruling doc
2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md, Sec.7), which is
held pending a Captain decision and is NOT scoped here.

ASCII-only console output (HK-009). NFR-021: aggregate statistics only -- no callsign,
message text, or per-record field is ever printed.
"""
from __future__ import annotations

import os
import re
import statistics as st
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.join(os.path.dirname(__file__), "..", "..",
                    "artefacts", "20260725_live_run_1806")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
WAV68_DIR = os.path.join(BASE, "owsfz", "wav68")

SETTINGS = [
    ("k10 (shipped)", "c4_min_score/k10/k10_c0.10_n60"),
    ("k8",            "c4_min_score/k8/k10_c0.10_n60"),
    ("k6",            "c4_min_score/k6/k10_c0.10_n60"),
    ("k4",            "c4_min_score/k4/k10_c0.10_n60"),
    ("k8_cap2000",    "c4_min_score/k8_cap2000/k10_c0.10_n60"),
    ("k6_cap2000",    "c4_min_score/k6_cap2000/k10_c0.10_n60"),
    ("k4_cap2000",    "c4_min_score/k4_cap2000/k10_c0.10_n60"),
]

# Same hash-token normalisation as c3/c4 analyses, so populations are comparable.
_HASH_BRACKET_RE = re.compile(r"<[^>]*>")
_GRID = re.compile(r"^[A-R]{2}[0-9]{2}$")
_RPT = re.compile(r"^[-+][0-9]{2}$")


def normalize_hash_tokens(message: str) -> str:
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def parse_all_txt(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                print(f"[WARN] unparsable ALL.TXT line in {path}", file=sys.stderr)
                continue
            rows.append({"ts": tok[0], "snr": float(tok[4]), "dt": float(tok[5]),
                         "freq": float(tok[6]), "message": " ".join(tok[7:])})
    return rows


def grammar_valid(message: str) -> bool:
    """Standard FT8 message forms. Deliberately permissive -- the point is to show
    this check is uninformative, not to build a strict validator."""
    t = message.split()
    if len(t) < 2 or len(t) > 4:
        return False
    if t[0] == "CQ":
        return True
    if len(t) == 3:
        return bool(_GRID.match(t[2]) or _RPT.match(t[2])
                    or t[2] in ("RRR", "RR73", "73", "R"))
    if len(t) == 2:
        return t[1] in ("RRR", "RR73", "73")
    return False


def persistence(rows: list[dict]) -> float:
    """Share of distinct message texts seen in more than one cycle."""
    seen: dict[str, set[str]] = {}
    for r in rows:
        seen.setdefault(normalize_hash_tokens(r["message"]), set()).add(r["ts"])
    if not seen:
        return 0.0
    return sum(1 for v in seen.values() if len(v) > 1) / len(seen)


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0]
                    for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    cycle_set = set(cycles)
    print(f"corpus: {len(cycles)} matched cycles")

    wsjtx_by_cycle: dict[str, set[str]] = {}
    for r in parse_all_txt(WSJTX_ALL_TXT):
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))
    wsjtx_total = sum(len(v) for v in wsjtx_by_cycle.values())
    print(f"WSJT-X deduped messages on those cycles: {wsjtx_total}")
    print()

    print("DECODE YIELD -- 'matched' is the only column that closes the D-001 gap")
    hdr = (f"{'setting':<15} {'rows':>6} {'dedup':>6} {'matched':>8} {'unique':>7} "
           f"{'d_total':>8} {'d_matched':>10} {'uniq_share':>11}")
    print(hdr)
    print("-" * len(hdr))

    base_matched = base_total = None
    characterise: list[tuple[str, list[dict], list[dict]]] = []

    for label, rel in SETTINGS:
        rows = parse_all_txt(os.path.join(BASE, rel, "ALL.TXT"))
        by_cycle: dict[str, set[str]] = {}
        for r in rows:
            by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))
        dedup = sum(len(v) for v in by_cycle.values())
        matched = sum(len(v & wsjtx_by_cycle.get(ts, set())) for ts, v in by_cycle.items())
        unique = sum(len(v - wsjtx_by_cycle.get(ts, set())) for ts, v in by_cycle.items())

        if base_matched is None:
            base_matched, base_total = matched, len(rows)

        print(f"{label:<15} {len(rows):>6} {dedup:>6} {matched:>8} {unique:>7} "
              f"{len(rows) - base_total:>+8} {matched - base_matched:>+10} "
              f"{unique / max(1, dedup):>10.1%}")

        m_rows = [r for r in rows
                  if normalize_hash_tokens(r["message"]) in wsjtx_by_cycle.get(r["ts"], set())]
        u_rows = [r for r in rows
                  if normalize_hash_tokens(r["message"]) not in wsjtx_by_cycle.get(r["ts"], set())]
        characterise.append((label, m_rows, u_rows))

    print()
    print("UNIQUE-TO-US CHARACTERISATION -- real weak signals vs CRC-passing false decodes")
    hdr2 = (f"{'setting':<15} {'n_uniq':>7} {'persist_u':>10} {'persist_m':>10} "
            f"{'medSNR_u':>9} {'medSNR_m':>9} {'callreuse':>10} {'grammar':>8}")
    print(hdr2)
    print("-" * len(hdr2))
    for label, m_rows, u_rows in characterise:
        real_calls = set()
        for r in m_rows:
            for tok in r["message"].split()[1:]:
                if len(tok) >= 3 and any(c.isdigit() for c in tok):
                    real_calls.add(tok)
        reuse = sum(1 for r in u_rows
                    if any(tok in real_calls for tok in r["message"].split()[1:]))
        gram = sum(1 for r in u_rows if grammar_valid(r["message"]))
        n = max(1, len(u_rows))
        print(f"{label:<15} {len(u_rows):>7} {persistence(u_rows):>9.1%} "
              f"{persistence(m_rows):>9.1%} "
              f"{st.median([r['snr'] for r in u_rows]) if u_rows else 0:>9.1f} "
              f"{st.median([r['snr'] for r in m_rows]):>9.1f} "
              f"{reuse / n:>9.1%} {gram / n:>7.1%}")

    print()
    print("READING THIS: 'grammar' near 100% at every setting is EXPECTED and carries no")
    print("information -- the unpacker emits legal text for any CRC-passing payload.")
    print("'persist_u' at 0.0% against 'persist_m' near 25% is the discriminating result:")
    print("real traffic repeats across cycles over a ~17-minute corpus; random CRC")
    print("collisions do not. Read alongside medSNR_u below FT8's approx -21 dB threshold.")


if __name__ == "__main__":
    main()
