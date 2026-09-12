#!/usr/bin/env python3
"""OSD-FA-A Part D -- Mechanism 2 bit-field diagnostic (Architect's ruling, arch/osd-fa-a
`68c6a07`, sec.3.2): for every D2-sample decode where the probe converges (out_path in
{0,1}) but its payload != true_codeword(text) -- restricted to UNAMBIGUOUS dt (Mechanism
1 does not apply) and no '<' token (hash-packing ground removed) -- XOR the two 77-bit
payloads and histogram the differing bits by field, by category. Counts only.

Field boundaries, read from native/ft8_lib_vendor/ft8/message.c:354-376
(ftx_message_decode_std) rather than assumed from the ruling's field-name ORDER (i3 sits
at the END of the payload, bits [74,77), despite being named first):
  c28_1 [0,28)   p1_1 [28,29)   c28_2 [29,57)   p1_2 [57,58)   R1 [58,59)
  g15 [59,74)    i3 [74,77)

Reuses part_d2.py's exact same sample (identical seed -> identical cycle/decode set as
D2a.json) and part_d.decode_one's own extract+probe call, extended to also return a91
(needed here; part_d.decode_one only returns path/fidelity booleans).

NFR-021: message text held in memory only for true_codeword() and category/bracket
checks -- never printed. Output is bit-position counts only.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "harness"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
from common import compute_seed  # noqa: E402
import part_d2 as PD2  # noqa: E402
from part_d import read_wav_normalised  # noqa: E402

FIELDS = [
    ("c28_1", 0, 28), ("p1_1", 28, 29), ("c28_2", 29, 57), ("p1_2", 57, 58),
    ("R1", 58, 59), ("g15", 59, 74), ("i3", 74, 77),
]


def is_unambiguous(dt_s: float) -> bool:
    """Mechanism 1 (ruling sec.2.1): printed dt with round(10*dt) mod 4 == 2 sits
    exactly halfway between two 0.08s grid cells."""
    n = round(10 * dt_s)
    return (n % 4) != 2


def field_of(bit_idx: int) -> str:
    for name, lo, hi in FIELDS:
        if lo <= bit_idx < hi:
            return name
    raise AssertionError(bit_idx)


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    by_cycle = PD2.parse_all_txt_with_snr(PD2.ALL_TXT)
    by_cycle = {ts: v for ts, v in by_cycle.items() if PD2.BOUNDARY_LO <= ts < PD2.BOUNDARY_HI}
    wav_cycles = set(fn[:-4] for fn in os.listdir(PD2.WAV_DIR)
                      if fn.endswith(".wav") and not fn.endswith("_2.wav"))
    all_cycles = sorted(c for c in wav_cycles if PD2.BOUNDARY_LO <= c < PD2.BOUNDARY_HI)
    rng = random.Random(PD2.SAMPLE_SEED)
    sample_cycles = sorted(rng.sample(all_cycles, min(PD2.N_SAMPLE_CYCLES, len(all_cycles))))
    print(f"sampled {len(sample_cycles)} cycles (same seed as D2a: {PD2.SAMPLE_SEED})", flush=True)

    dec = P.load_decoder(verify=True)
    print(f"shim={dec.version}", flush=True)

    field_decode_count = {}   # (category, field) -> n decodes with >=1 differing bit there
    field_bit_count = {}      # (category, field) -> total differing bits there
    n_mismatched = {}         # category -> n qualifying mismatched decodes
    n_considered = {}         # category -> n qualifying decodes considered (unambig, no '<', converged)

    t0 = time.perf_counter()
    n_done = 0
    for cycle_ts in sample_cycles:
        wav_path = os.path.join(PD2.WAV_DIR, cycle_ts + ".wav")
        pcm = None
        for freq_hz, dt_s, message, snr in by_cycle.get(cycle_ts, []):
            if "<" in message or not is_unambiguous(dt_s):
                continue
            cat = PD2.categorize(message)
            if pcm is None:
                pcm = read_wav_normalised(wav_path)
            time_offset_s = dt_s  # no +0.16 (accepted correction)
            rc, llr = dec.extract_at(pcm, freq_hz, time_offset_s)
            if rc != 0:
                continue
            res = dec.ldpc_decode_llrs(llr, max_iters=P.K_LDPC_ITERATIONS, osd_depth=P.OSD_DEPTH)
            if res["path"] not in (0, 1) or res["a91"] is None:
                continue
            true_bits = dec.true_codeword(message)
            if true_bits is None:
                continue
            n_considered[cat] = n_considered.get(cat, 0) + 1
            recovered = P.a91_to_bits(res["a91"], P.FT8_PAYLOAD_BITS)
            expected = true_bits[:P.FT8_PAYLOAD_BITS]
            if res["crc_ok"] == 1 and recovered == expected:
                continue  # fidelity pass -- not a mismatch, nothing to histogram
            n_mismatched[cat] = n_mismatched.get(cat, 0) + 1
            for i in range(P.FT8_PAYLOAD_BITS):
                if recovered[i] != expected[i]:
                    fld = field_of(i)
                    key = (cat, fld)
                    field_bit_count[key] = field_bit_count.get(key, 0) + 1
            fields_hit = {field_of(i) for i in range(P.FT8_PAYLOAD_BITS) if recovered[i] != expected[i]}
            for fld in fields_hit:
                key = (cat, fld)
                field_decode_count[key] = field_decode_count.get(key, 0) + 1
        n_done += 1
        if n_done % 200 == 0:
            print(f"  {n_done}/{len(sample_cycles)} cycles ({time.perf_counter()-t0:.0f}s)", flush=True)

    out = {
        "n_considered": n_considered,
        "n_mismatched": n_mismatched,
        "field_decode_count": {f"{c}|{f}": v for (c, f), v in field_decode_count.items()},
        "field_bit_count": {f"{c}|{f}": v for (c, f), v in field_bit_count.items()},
        "total_wall_s": time.perf_counter() - t0,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    os.replace(tmp, out_json)
    print(json.dumps(out, indent=2))
    print(f"-> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
