#!/usr/bin/env python3
"""Task 5 mandatory self-check 4 (replay spec Sec.4.4): grid alignment control.

Confirms a +/-1 cycle tolerance on the (ts, freq_bin, msg) match key recovers ZERO additional
matches beyond exact-ts matching, as it did on arm B's corpus (PASS report Sec.8). If it recovers
matches on arm A, that is drift showing up in the labels and changes how the miss set is built --
must be reported, not silently absorbed.

NFR-021: reads message text into memory only for the match-key computation; only counts are
printed, no message text or callsigns.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

LINE_RE = re.compile(
    r"^(?P<ts>\d{6}_\d{6})\s+(?P<dial>[\d.]+)\s+Rx\s+FT8\s+"
    r"(?P<snr>-?\d+)\s+(?P<dt>-?[\d.]+)\s+(?P<freq>\d+)\s+(?P<msg>.+?)\s*$"
)
HASH_TOKEN_RE = re.compile(r"<[^>]*>")
CYCLE_S = 15


def parse(path: Path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            rows.append({
                "ts": m.group("ts"),
                "snr": int(m.group("snr")),
                "freq": int(m.group("freq")),
                "msg": " ".join(m.group("msg").split()).upper(),
            })
    return rows


def freq_bin(freq_hz: int, width: int = 50) -> int:
    return int(round(freq_hz / width)) * width


def is_hashed(msg: str) -> bool:
    return bool(HASH_TOKEN_RE.search(msg))


def shift_ts(ts: str, cycles: int) -> str:
    dt = datetime.strptime(ts, "%y%m%d_%H%M%S") + timedelta(seconds=CYCLE_S * cycles)
    return dt.strftime("%y%m%d_%H%M%S")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    corpus = args.corpus.resolve()
    owsfz_rows = parse(corpus / "owsfz" / "ALL.TXT")
    wsjt_rows = parse(corpus / "wsjt-x" / "ALL.TXT")

    owsfz_keys_exact = {(r["ts"], freq_bin(r["freq"]), r["msg"]) for r in owsfz_rows}

    wsjt_nonhashed = [r for r in wsjt_rows if not is_hashed(r["msg"])]
    exact_matches = sum(1 for r in wsjt_nonhashed
                         if (r["ts"], freq_bin(r["freq"]), r["msg"]) in owsfz_keys_exact)

    def matches_with_tolerance(tol_cycles: int) -> int:
        n = 0
        for r in wsjt_nonhashed:
            key_variants = {(shift_ts(r["ts"], d), freq_bin(r["freq"]), r["msg"])
                             for d in range(-tol_cycles, tol_cycles + 1)}
            if key_variants & owsfz_keys_exact:
                n += 1
        return n

    m0 = exact_matches
    m1 = matches_with_tolerance(1)
    m2 = matches_with_tolerance(2)

    print("=" * 78)
    print(f"[{args.label}] GRID ALIGNMENT CONTROL")
    print(f"corpus: {corpus}")
    print("=" * 78)
    print(f"WSJT-X non-hashed decodes: {len(wsjt_nonhashed)}")
    print(f"exact-ts matches       : {m0}")
    print(f"+/-1 cycle tolerance    : {m1}  (delta vs exact: {m1 - m0:+d})")
    print(f"+/-2 cycle tolerance    : {m2}  (delta vs exact: {m2 - m0:+d})")

    if m1 - m0 == 0:
        print(f"\n[{args.label}] +/-1 cycle tolerance recovers ZERO additional matches -- "
              "consistent with a grid-locked (non-drifting-label) corpus at match time.")
    else:
        print(f"\n[{args.label}] +/-1 cycle tolerance recovers {m1 - m0} additional matches -- "
              "this IS drift showing up in the labels. Report; do not silently absorb into the "
              "miss-set construction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
