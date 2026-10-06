#!/usr/bin/env python3
"""COH-GAIN: freeze the real-audio row list (spec section 4) and the timing-pilot rows (section 7 step 2). No extraction happens here.

Night 20261004_1634. The ordered cycle list is the NHARD-REP frozen FULL list (3,104 cycles, selection.json, LF SHA pinned in nhard_rep_rows.py):
  sampled cycles = positions i mod 10 == 3          (NHARD-REP used residues 0 and 5, so no cycle is shared)
  pilot cycles   = positions i mod 10 == 7          (disjoint from the sample: the pilot is DISCARDED from the analysis)
Rows = every WSJT-X decode (Rx FT8 line of WSJT-X's ALL.TXT) in a sampled cycle. A row the vendored encoder cannot pack is EXCLUDED before extraction and
counted by reason; the reason is a coarse text FEATURE, never text. live_hit = Test B's rule (same cycle, same text, |df| <= 10 Hz, one-to-one nearest-first)
against the live OpenWSFZ ALL.TXT. ws_load = WSJT-X decodes in that cycle (all of them, including excluded rows).

HK-037 / NFR-021: message text exists only inside this module's reading functions. rows.json holds numeric fields and the cycle stamp only.
The mod-20 variant (section 4's 6 h rule) is a subset of the mod-10 rows: each row carries in_mod20 = (i mod 20 == 3).

  python qa/rr-study/coh-gain/cg_select.py --dll <libft8.dll>
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
import cg_common as CG  # noqa: E402
import nhard_rep_rows as NR  # noqa: E402

REPO = CG.REPO_ROOT
ART = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
RUN = "20261004_1634"
GATHERED = os.path.join(ART, f"{RUN}_endurance_run-gathered")
WS_ALLTXT = os.path.join(GATHERED, "wsjt-x", "ALL.TXT")
OWS_ALLTXT = os.path.join(GATHERED, "owsfz", "ALL.TXT")
WAV_DIR = os.path.join(GATHERED, "owsfz", "wav")
NH_SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-coh-gain")
ROWS_JSON = os.path.join(OUT_DIR, "rows.json")
CORROBORATION_DELTA_HZ = 10    # Test B's rule, replay81 CorroborationDeltaHz


def read_alltxt(path):
    """stamp -> [(snr, dt, freq, text)] in file order, the same line convention as the NHARD-REP harness (Rx FT8, >= 8 fields, integer snr/freq).
    TEXT STAYS IN THIS RETURN VALUE: callers must not print or persist it."""
    d = collections.OrderedDict()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                snr, freq = int(f[4]), int(f[6])
                dt = float(f[5])
            except ValueError:
                continue
            d.setdefault(f[0], []).append((snr, dt, freq, " ".join(f[7:]).strip()))
    return d


def test_b_matches(ws_lines, ows_lines):
    """Per WSJT-X line index: True iff matched by one OpenWSFZ decode under Test B's rule (nearest-first, one-to-one)."""
    cands = []
    for i, (_, _, f1, t1) in enumerate(ows_lines):
        for j, (_, _, f2, t2) in enumerate(ws_lines):
            df = abs(f1 - f2)
            if df <= CORROBORATION_DELTA_HZ and t1 == t2:
                cands.append((df, i, j))
    cands.sort()
    used_o, used_w = set(), set()
    for _, i, j in cands:
        if i in used_o or j in used_w:
            continue
        used_o.add(i)
        used_w.add(j)
    return [j in used_w for j in range(len(ws_lines))]


def text_feature(text):
    """Coarse reason an unencodable row is excluded (a FEATURE of the text, never the text)."""
    return "hashed_call_token" if "<" in text else "other_unencodable"


def build(dll_path):
    sel_bytes = open(NH_SELECTION, "rb").read().replace(b"\r\n", b"\n")
    assert hashlib.sha256(sel_bytes).hexdigest() == NR.SELECTION_SHA256, "NHARD-REP selection.json differs from its pin"
    full = json.loads(sel_bytes)["runs"][RUN]["FULL"]
    ws, ows = read_alltxt(WS_ALLTXT), read_alltxt(OWS_ALLTXT)
    dec = CG.load_decoder(dll_path)

    def rows_for(residue_positions):
        rows, excluded, n_cycles = [], collections.Counter(), 0
        for i, stamp in residue_positions:
            n_cycles += 1
            wl = ws.get(stamp, [])
            hits = test_b_matches(wl, ows.get(stamp, []))
            for widx, (snr, dt, freq, text) in enumerate(wl):
                if CG.encode_tones(dec, text) is None or dec.true_codeword(text) is None:
                    excluded[text_feature(text)] += 1
                    continue
                rows.append([i, stamp, widx, freq, dt, snr, len(wl), int(hits[widx]), int(i % 20 == CG.SAMPLE_RESIDUE)])
        return rows, dict(excluded), n_cycles

    sample = [(i, s) for i, s in enumerate(full) if i % 10 == CG.SAMPLE_RESIDUE]
    pilot_cycles = [(i, s) for i, s in enumerate(full) if i % 10 == CG.PILOT_RESIDUE]
    rows, excluded, n_cycles = rows_for(sample)
    prows, _, _ = rows_for(pilot_cycles[:12])           # a dozen cycles are far more than 50 rows
    prows = prows[:CG.PILOT_ROWS]
    assert len(prows) == CG.PILOT_ROWS
    sampled20 = [r for r in rows if r[8]]
    spec = {
        "spec": "qa/rr-study/2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md (branch arch/coherent-limb2) sections 4, 7",
        "night": RUN, "nhard_selection_sha256_lf": NR.SELECTION_SHA256,
        "wsjtx_alltxt_sha256": CG.file_sha256(WS_ALLTXT), "owsfz_alltxt_sha256": CG.file_sha256(OWS_ALLTXT),
        "columns": ["cycle_index", "stamp", "widx", "ws_freq", "ws_dt", "ws_snr", "ws_load", "live_hit", "in_mod20"],
        "counts": {"full_list_cycles": len(full), "sampled_cycles_mod10": n_cycles, "rows_mod10": len(rows), "rows_mod20": len(sampled20),
                   "sampled_cycles_mod20": len({r[0] for r in sampled20}), "excluded_before_extraction": excluded,
                   "live_hit_rows_mod10": sum(r[7] for r in rows), "pilot_rows": len(prows)},
        "rule": {"sample": "position i of the NHARD-REP FULL list with i mod 10 == 3 (primary) / i mod 20 == 3 (fallback)",
                 "pilot": "positions i mod 10 == 7, first 50 encodable rows; discarded from the analysis"},
        "rows": rows, "pilot_rows": prows,
    }
    return spec


def serialise(spec):
    return (json.dumps(spec, indent=0, sort_keys=True) + "\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True)
    a = ap.parse_args()
    spec = build(a.dll)
    data = serialise(spec)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(ROWS_JSON, "wb") as fh:
        fh.write(data)
    c = spec["counts"]
    print("wrote", ROWS_JSON)
    print({k: c[k] for k in ("sampled_cycles_mod10", "rows_mod10", "rows_mod20", "live_hit_rows_mod10", "excluded_before_extraction", "pilot_rows")})
    print("rows.json sha256(LF)", hashlib.sha256(data).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
