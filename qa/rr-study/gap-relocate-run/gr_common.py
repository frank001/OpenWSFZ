#!/usr/bin/env python3
"""GAP-RELOCATE shared loaders (QA; counts and positions only leave this module; message text stays in memory, HK-037).

REF = every WSJT-X 'Rx FT8' line of the night's ALL.TXT, per cycle stamp, in file order (the index Replay81 writes to matched.csv /
matchedbatch.csv). The first 400 cycles = the stamps of selection400.json (B2's population).
"""
from __future__ import annotations

import csv
import json
import os

S = r"D:\Projects\claude\_qa-scratch\gap-relocate"
RUN = "20260925_2010"
ALLTXT = r"D:\Projects\claude\OpenWSFZ\artefacts\20260925_2010_endurance_run-gathered\wsjt-x\ALL.TXT"
WAVDIR = r"D:\Projects\claude\OpenWSFZ\artefacts\20260925_2010_endurance_run-gathered\owsfz\wav"
SEL = os.path.join(S, "selection400.json")

N_CYCLES = 400
B2_BOTH_BATCH4 = 1350          # B2 report.md line 58 (Both: passed T1 and published), build 9ef703d0
B2_W = 12124                   # B2 report.md line 6: sum of WSJT-X decodes in the 400 cycles
B2_BOTH_PCT = 81.91            # B2 report.md: WSJT-X decodes corroborated (all batches), % of W, Both


def selection_stamps() -> list[str]:
    d = json.load(open(SEL, encoding="utf-8"))
    full = d["runs"][RUN]["FULL"]
    out = []
    for e in full:
        out.append(e if isinstance(e, str) else (e.get("stamp") or e.get("ts") or e[0]))
    return out


def load_ref(stamps: set[str]) -> dict[str, list[tuple[int, float, int, str]]]:
    """stamp -> [(snr, dt, freq_hz, text)] in ALL.TXT order (same filter as Replay81.LoadWsjtx)."""
    ref: dict[str, list] = {}
    with open(ALLTXT, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if f[0] not in stamps:
                continue
            try:
                snr, dt, freq = int(f[4]), float(f[5]), int(f[6])
            except ValueError:
                continue
            ref.setdefault(f[0], []).append((snr, dt, freq, " ".join(f[7:]).strip()))
    return ref


def load_matched_batch(path: str) -> dict[str, dict[int, int]]:
    """stamp -> {wsjtx_idx: batch of the OWS decode that matched it} (absent = unmatched)."""
    out: dict[str, dict[int, int]] = {}
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            st, _, rest = line.partition(",")
            d = {}
            if rest:
                for part in rest.split(";"):
                    if ":" in part:
                        i, b = part.split(":")
                        d[int(i)] = int(b)
            out[st] = d
    return out


def load_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_tsv(path: str) -> list[list[str]]:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            rows.append(line.rstrip("\n").split("\t"))
    return rows


def band_of(snr: int) -> str:
    """Replay81's SNR bands (BandOf): kept in step with Program.cs; asserted against a testb.csv band count in gr_item1."""
    return "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"
