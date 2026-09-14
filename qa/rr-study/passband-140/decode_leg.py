#!/usr/bin/env python3
"""PASSBAND-140: decode ONE (leg, corpus) pair per process.

Spec section 2.2: "One process per (leg, corpus), each starting cold... the
callsign hash table is process-global." Unlike LIVE-GAP-NOW's decode_leg.py,
this script does NOT accept a "both" corpus option -- that was flagged in
the spec's own reused-not-rebuilt table (section 0.5) as unacceptable here.

Output: artefacts/passband-140/_out/<leg>_<corpus>.jsonl, one JSON object
per cycle: {"ts": ..., "results": [{"freq_hz","dt","snr","message"}, ...]}.
Written incrementally (flushed every 100 cycles) so a supervised run can be
resumed/inspected mid-flight.

NFR-021: writes to artefacts/ (gitignored), never qa/. Message text is
written here (needed for the matcher's wildcard logic and the managed
chain later) but stays out of any tracked path.

Usage: python decode_leg.py <leg> <C2|C1P> [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "..", "cycleframer-alignment-replay"))

import dll_pin  # noqa: E402  (imported before corpus -- corpus.py inserts
                              # live-gap-now/ at sys.path[0], which would
                              # otherwise shadow this dir's own dll_pin.py)
import corpus  # noqa: E402  (this arm's own corpus.py, not live-gap-now's)
import p23_common  # noqa: E402

OUT_DIR = os.path.join(dll_pin.REPO_ROOT, "artefacts", "passband-140", "_out")
MAX_RESULTS = p23_common.MAX_RESULTS


def decode_corpus(dec, cycles, out_path, leg, corpus_id, log_every=100):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n_truncated = 0
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as fh:
        for i, (ts, wav_path) in enumerate(cycles):
            pcm = p23_common.read_wav(wav_path)
            pcm = p23_common.normalise_rms(pcm, p23_common.PROD_TARGET_RMS)
            results = dec.decode(pcm)
            if results is None:
                results = []
                rec_note = "AV"
            else:
                rec_note = None
            if len(results) == MAX_RESULTS:
                n_truncated += 1
            rec = {"ts": ts, "results": results}
            if rec_note:
                rec["note"] = rec_note
            fh.write(json.dumps(rec) + "\n")
            if (i + 1) % log_every == 0:
                fh.flush()
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (len(cycles) - i - 1) / rate if rate > 0 else float("inf")
                print("[%s/%s] %d/%d cycles (%.2f/s, ETA %.0fs)" %
                      (leg, corpus_id, i + 1, len(cycles), rate, eta), flush=True)
    print("[%s/%s] DONE: %d cycles, %d truncated at MAX_RESULTS=%d" %
          (leg, corpus_id, len(cycles), n_truncated, MAX_RESULTS), flush=True)
    if n_truncated:
        print("[%s/%s] WARNING: truncation guard (ROW 0g) fired -- raise MAX_RESULTS "
              "to 400 and re-run this leg on this corpus." % (leg, corpus_id), flush=True)
    return n_truncated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("leg", choices=list(dll_pin.LEGS))
    ap.add_argument("corpus_id", choices=["C2", "C1P"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    print("[%s/%s] loading decoder..." % (args.leg, args.corpus_id), flush=True)
    dec = dll_pin.load_leg(args.leg)
    print("[%s/%s] loaded: sha256 ok, shim=%d, params set" %
          (args.leg, args.corpus_id, dec.version), flush=True)

    if args.corpus_id == "C2":
        cycles, dup_report = corpus.c2_cycles()
        print("[%s/C2] dup report: %s" % (args.leg, dup_report), flush=True)
    else:
        cycles = corpus.c1_prime_cycles()

    if args.limit:
        cycles = cycles[:args.limit]

    out_path = os.path.join(OUT_DIR, "%s_%s.jsonl" % (args.leg, args.corpus_id))
    n_truncated = decode_corpus(dec, cycles, out_path, args.leg, args.corpus_id)

    print("[%s/%s] ALL DONE, output=%s" % (args.leg, args.corpus_id, out_path), flush=True)
    return 1 if n_truncated else 0


if __name__ == "__main__":
    sys.exit(main())
