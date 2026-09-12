#!/usr/bin/env python3
"""LIVE-GAP-NOW: decode every C1 and every C2 cycle through ONE leg's binary,
in this one process (spec section 2: "one process per leg, distinct DLL
filenames"; NOW40 shares NOW's file but is a distinct process/leg here).

Output: artefacts/live-gap-now/_out/<leg>_C1.jsonl and <leg>_C2.jsonl, one JSON
object per cycle: {"ts": ..., "results": [{"freq_hz","dt","snr","message"}, ...]}.
Written incrementally (flushed every line) so a supervised run can be resumed /
inspected mid-flight and so a crash loses at most the in-flight cycle.

NFR-021: writes to artefacts/ (gitignored), never qa/. Message text is written
here (needed for the matcher's wildcard logic later) but stays out of any
tracked path.

Usage: python decode_leg.py <leg> [--corpus C1|C2|both] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "cycleframer-alignment-replay"))

import corpus  # noqa: E402
import dll_pin  # noqa: E402
import p23_common  # noqa: E402

OUT_DIR = os.path.join(dll_pin.REPO_ROOT, "artefacts", "live-gap-now", "_out")
# Must equal p23_common.MAX_RESULTS -- that module-level constant sizes the ctypes
# results buffer inside Decoder.__init__ (dll_pin.load_leg reuses it unmodified),
# so this is the actual native call cap, not an independent choice.
MAX_RESULTS = p23_common.MAX_RESULTS


def decode_corpus(dec, cycles, out_path, leg, corpus_id, log_every=200):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n_truncated = 0
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as fh:
        for i, (ts, wav_path) in enumerate(cycles):
            pcm = p23_common.read_wav(wav_path)
            pcm = p23_common.normalise_rms(pcm, p23_common.PROD_TARGET_RMS)
            results = dec.decode(pcm)
            if results is None:
                results = []  # native AV caught by shim's SEH -- record as zero decodes
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
                print("[%s/%s] %d/%d cycles (%.1f/s, ETA %.0fs)" %
                      (leg, corpus_id, i + 1, len(cycles), rate, eta), flush=True)
    print("[%s/%s] DONE: %d cycles, %d truncated at MAX_RESULTS=%d" %
          (leg, corpus_id, len(cycles), n_truncated, MAX_RESULTS), flush=True)
    return n_truncated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("leg", choices=list(dll_pin.LEGS))
    ap.add_argument("--corpus", choices=["C1", "C2", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    print("[%s] loading decoder..." % args.leg, flush=True)
    dec = dll_pin.load_leg(args.leg)
    print("[%s] loaded: sha256 ok, shim=%d, params set" % (args.leg, dec.version), flush=True)

    total_truncated = 0
    if args.corpus in ("C1", "both"):
        c1 = corpus.c1_cycles()
        if args.limit:
            c1 = c1[:args.limit]
        out1 = os.path.join(OUT_DIR, "%s_C1.jsonl" % args.leg)
        total_truncated += decode_corpus(dec, c1, out1, args.leg, "C1")

    if args.corpus in ("C2", "both"):
        c2, dup_report = corpus.c2_cycles()
        if args.limit:
            c2 = c2[:args.limit]
        out2 = os.path.join(OUT_DIR, "%s_C2.jsonl" % args.leg)
        total_truncated += decode_corpus(dec, c2, out2, args.leg, "C2")
        print("[%s] C2 dup report: %s" % (args.leg, dup_report), flush=True)

    if total_truncated:
        print("[%s] WARNING: %d cycles hit MAX_RESULTS=%d -- truncation guard should "
              "raise MAX_RESULTS to 400 and re-run this leg." % (args.leg, total_truncated, MAX_RESULTS),
              flush=True)
    print("[%s] ALL DONE" % args.leg, flush=True)


if __name__ == "__main__":
    main()
