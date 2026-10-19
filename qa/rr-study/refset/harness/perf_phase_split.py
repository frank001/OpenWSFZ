#!/usr/bin/env python
"""Phase split of a `perf script` callchain dump (QA tooling; OLD-CPU SPEED step 0, spec 2026-10-13-1630 + amendment 1). Aggregates only.

    perf script -i <perf.data> -F ip,sym,dso > <dump>          (one block per sample, leaf frame first, blank line between samples)
    python perf_phase_split.py --dump <dump> --out <json> [--vocab 60]

Every sample is placed in exactly ONE phase row, by the first rule that matches, so the rows are mutually exclusive and sum to 100 %:
  1. unresolved        the leaf frame has no symbol (OC-V2's numerator)
  2. fits              any frame ft8_subfeas_fit_signal            (per-signal fits: fine_fit_with_drift, freq_search, lp_envelope, ...)
  3. analytic          any frame ft8_subfeas_compute_analytic
  4. residual_decode   any frame ft8_decode_all AND any managed frame of SubtractionPass (the residual pass's native decode)
  5. pass0_decode      any frame ft8_decode_all otherwise          (pass 0)
  6. managed           any other resolved frame from the .NET perf map or a managed assembly (merge, plausibility, harness, GC, JIT)
  7. other             anything else (kernel-free: user-space only, perf_event_paranoid 2)
Inside "fits" (again mutually exclusive, first match wins):
  kiss_fft             any frame kiss_fft*, kf_*  (all callers within the fits; broken down by the nearest fit function above it)
  trig                 any frame r_fit_drift / apply_freq_shift / instantaneous_phase, or a libm sin/cos/sincos leaf
  freq_search_self     any frame freq_search (outside its FFT)
  lp_envelope_self     any frame lp_envelope (outside its FFT)
  step3_correlation    the leaf is fine_fit_with_drift itself (its 201 x 151,680 complex multiply-adds)
  fits_other           the rest of ft8_subfeas_fit_signal
Also: top symbols by SELF (leaf) %. No message text can appear: only function names and library names are read.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter

FITS_FN = "ft8_subfeas_fit_signal"
ANALYTIC_FN = "ft8_subfeas_compute_analytic"
DECODE_FN = "ft8_decode_all"
RESIDUAL_MARK = "SubtractionPass"
KISS = re.compile(r"^(kiss_fft|kf_)")
TRIG_FN = {"r_fit_drift", "apply_freq_shift", "instantaneous_phase"}
LIBM_TRIG = re.compile(r"^(__)?(sin|cos|sincos)(f|_fma|_avx|_sse|_fma4)?\d*$|^__(sin|cos)_")
UNRESOLVED = re.compile(r"^\[unknown\]$|^0x[0-9a-fA-F]+$|^$")
MANAGED_DSO = re.compile(r"perf-\d+\.map|\.dll|libcoreclr|libclrjit|libSystem|\[JIT\]|/tmp/perf-")

PHASES = ["fits", "analytic", "residual_decode", "pass0_decode", "managed", "other", "unresolved"]
FIT_ROWS = ["kiss_fft", "trig", "freq_search_self", "lp_envelope_self", "step3_correlation", "fits_other"]


def parse_dump(lines):
    """-> iterator of samples; a sample is a list of (symbol, dso), leaf first."""
    cur = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            if cur:
                yield cur
                cur = []
            continue
        t = line.strip().split(None, 1)
        rest = t[1] if len(t) > 1 else ""
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", rest)
        sym, dso = (m.group(1), m.group(2)) if m else (rest, "")
        sym = re.sub(r"\+0x[0-9a-fA-F]+$", "", sym.strip())
        cur.append((sym, dso))
    if cur:
        yield cur


def classify(frames) -> tuple:
    """frames: [(sym, dso)], leaf first. -> (phase, fit_row or None)."""
    syms = [s for s, _ in frames]
    leaf_sym, leaf_dso = frames[0]
    if UNRESOLVED.match(leaf_sym):
        return "unresolved", None
    if FITS_FN in syms:
        up = frames[:syms.index(FITS_FN)]                      # the frames below the fit entry point, leaf first
        usyms = [s for s, _ in up]
        if any(KISS.match(s) for s in usyms):
            return "fits", "kiss_fft"
        if any(s in TRIG_FN for s in usyms) or LIBM_TRIG.match(leaf_sym):
            return "fits", "trig"
        if "freq_search" in usyms:
            return "fits", "freq_search_self"
        if "lp_envelope" in usyms:
            return "fits", "lp_envelope_self"
        if leaf_sym == "fine_fit_with_drift":
            return "fits", "step3_correlation"
        return "fits", "fits_other"
    if ANALYTIC_FN in syms:
        return "analytic", None
    if DECODE_FN in syms:
        return ("residual_decode" if any(RESIDUAL_MARK in s for s in syms) else "pass0_decode"), None
    if any(MANAGED_DSO.search(d) for _, d in frames) or any("::" in s or s.startswith(("OpenWSFZ.", "RefSet", "System.", "Microsoft.")) for s in syms):
        return "managed", None
    return "other", None


def kiss_by_parent(frames) -> str:
    """For a sample classified kiss_fft: the nearest fit function above the FFT frames."""
    syms = [s for s, _ in frames]
    for name in ("freq_search", "lp_envelope", "r_fit_drift", "fine_fit_with_drift"):
        if name in syms:
            return name
    return "other"


def summarise(samples, top_n: int = 15, vocab_n: int = 0) -> dict:
    ph, fr, kp, leaf = Counter(), Counter(), Counter(), Counter()
    vocab = Counter()
    n = 0
    for fr_list in samples:
        n += 1
        p, row = classify(fr_list)
        ph[p] += 1
        leaf[fr_list[0][0] or "[unknown]"] += 1
        if row:
            fr[row] += 1
            if row == "kiss_fft":
                kp[kiss_by_parent(fr_list)] += 1
        if vocab_n:
            for s, d in fr_list:
                vocab[(s, d.split("/")[-1][:40])] += 1
    if n == 0:
        return {"samples": 0}
    pc = lambda c: round(100.0 * c / n, 2)
    out = {"samples": n,
           "phase_pct": {k: pc(ph[k]) for k in PHASES},
           "phase_pct_sum": round(sum(pc(ph[k]) for k in PHASES), 2),
           "fits_inner_pct_of_all_samples": {k: pc(fr[k]) for k in FIT_ROWS},
           "kiss_fft_by_parent_pct_of_all_samples": {k: pc(v) for k, v in kp.most_common()},
           "top_self_symbols_pct": [[s, pc(c)] for s, c in leaf.most_common(top_n)]}
    if vocab_n:
        out["frame_vocabulary"] = [[s, d, c] for (s, d), c in vocab.most_common(vocab_n)]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--vocab", type=int, default=0, help="also list the N most frequent (symbol, library) pairs: a smoke-test aid")
    a = ap.parse_args()
    with open(a.dump, encoding="utf-8", errors="replace") as fh:
        res = summarise(parse_dump(fh), vocab_n=a.vocab)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1)
    print("samples", res["samples"], "phases", res.get("phase_pct"), "sum", res.get("phase_pct_sum"))


if __name__ == "__main__":
    main()
