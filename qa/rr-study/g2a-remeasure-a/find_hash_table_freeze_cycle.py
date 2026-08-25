#!/usr/bin/env python3
"""G2A-REMEASURE-A -- find the hash-table freeze cycle, per WITHDRAWAL Sec.4.2.

`g_session_hash_table` is never evicted or re-initialised (ft8_shim.c:705-711)
-- once `tbl->count >= HASH_TABLE_SIZE` it is FROZEN for the life of the
process. `ft8_get_hash_table_reject_count()` is exported and monotonic
(ft8_shim.c:694), so the first cycle at which it goes non-zero IS the exact
freeze moment. Polling this needs NO rebuild and NO src change -- reuses
decode_corpus.py's own Decoder class verbatim (HK-018).

EARLY STOP: unlike decode_corpus.py's full-corpus replay (~58 min/leg,
2026-08-25 L1/L2 runs), this script stops as soon as the reject counter
turns non-zero (plus a short confirmation tail), since that single cycle
index is the entire measurement -- "the single most informative cheap
measurement now available" per the withdrawal, and it should stay cheap.
If the counter never turns non-zero before EOF, the run falls through to
the end and reports "did not saturate on this corpus" honestly.

NFR-021: writes cycle timestamps and a bare int (reject count) only, never
message text -- decode() results are discarded, not even parsed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decode_corpus import Decoder, WAV_DIR, normalise_rms, read_wav, PROD_TARGET_RMS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--shim-version", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--confirm-tail", type=int, default=20,
                     help="cycles to keep polling after first non-zero, to confirm monotonic non-reset")
    args = ap.parse_args()

    wavs = sorted(f for f in os.listdir(WAV_DIR) if f.endswith(".wav"))
    dec = Decoder(args.dll, args.sha256, args.shim_version)
    if not dec._has_reject_ctr:
        raise RuntimeError("this DLL does not export ft8_get_hash_table_reject_count()")
    print("Decoder loaded: %s  sha256=%s  shim=%d  n_wavs=%d"
          % (args.dll, dec.sha256, dec.version, len(wavs)), flush=True)

    freeze_index = None
    freeze_ts = None
    freeze_reject_count = None
    tail = []
    t0 = time.time()

    for i, fn in enumerate(wavs):
        ts = fn[:-4]
        path = os.path.join(WAV_DIR, fn)
        pcm = read_wav(path)
        pcm = normalise_rms(pcm, PROD_TARGET_RMS)
        dec.decode(pcm)  # result discarded -- only the reject counter matters (NFR-021)
        rc = dec.reject_count()

        if freeze_index is None:
            if rc and rc > 0:
                freeze_index = i
                freeze_ts = ts
                freeze_reject_count = rc
                print("FREEZE at cycle %d/%d  ts=%s  reject_count=%d  elapsed=%.0fs"
                      % (i, len(wavs), ts, rc, time.time() - t0), flush=True)
        else:
            tail.append({"index": i, "ts": ts, "reject_count": rc})
            if len(tail) >= args.confirm_tail:
                break

        if (i + 1) % 500 == 0:
            print("  [%d/%d] %s  reject_count=%s  elapsed=%.0fs"
                  % (i + 1, len(wavs), fn, rc, time.time() - t0), flush=True)

    elapsed = time.time() - t0
    saturated = freeze_index is not None
    out = {
        "dll_path": os.path.abspath(args.dll),
        "dll_sha256": dec.sha256,
        "shim_version": dec.version,
        "n_wavs_total": len(wavs),
        "n_wavs_scanned": (freeze_index + len(tail) + 1) if saturated else len(wavs),
        "saturated": saturated,
        "freeze_cycle_index": freeze_index,
        "freeze_cycle_ts": freeze_ts,
        "freeze_reject_count": freeze_reject_count,
        "confirm_tail": tail,
        "wall_seconds": elapsed,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    os.replace(tmp, args.out)
    if saturated:
        print("DONE. Saturates at cycle %d/%d (ts=%s) after %.0fs -> %s"
              % (freeze_index, len(wavs), freeze_ts, elapsed, args.out), flush=True)
    else:
        print("DONE. Did NOT saturate anywhere in %d cycles (%.0fs) -> %s"
              % (len(wavs), elapsed, args.out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
