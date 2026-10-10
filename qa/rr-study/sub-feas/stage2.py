#!/usr/bin/env python3
"""SUB-FEAS Stage 2 (spec sec.8): the payoff diagnostic. Authorised by the Captain
2026-09-28 as a LABELLED DIAGNOSTIC despite Stage 1's FAIL (Architect ruling
`d8a8436d`, sec.4-5: "Running it now would be a new, Captain-initiated diagnostic
... its result could not retro-promote Stage 1"). Bars per sec.8, unchanged. Plus
one extra W=0.16s leg, reported descriptively (Architect recommendation sec.5).

For each split-B cycle: fit and subtract ALL of OWS's re-encodable decodes in
that cycle (not just the isolated/SNR>=0 population P -- "all of OWS's
re-encodable decodes" per sec.8's own wording; the point is to clean the whole
cycle, not just the isolated subset Stage 1 measured). Decode the residual with
the pinned DLL. A new decode is one not in that cycle's OWS list (payload-bit
comparison, RR73-equivalent). Corroborated = also in WSJT-X's ALL.TXT for the
same cycle (same payload-match + |df|<=10Hz nearest-pairing convention as
Amendment 1's twin detection).

RR73 asymmetry (same reasoning as corpus.py / ROW 0f, NOT reused blindly): every
REFERENCE payload here (the cycle's own OWS list, and WSJT-X's list) comes from
RE-ENCODING LOGGED TEXT with our own encoder, so it always carries our own
MAXGRID4+3 sentinel for a literal "RR73" report. A NEW decode's payload comes
from the pinned DLL's own LDPC decode of REAL RF, which -- if it really is an
RR73 report -- may legitimately carry the ON-AIR sentinel (corpus.RR73_ONAIR_IGRID4,
32373) instead. `comparator.payload_match(ref, candidate, ..., v_star)` is built
for exactly this asymmetry; using `v_star=RR73_STD` (as corpus.py's twin-detector
correctly does, since there both sides come from re-encoded text) would be wrong
here and silently miss every genuine on-air RR73 "new" decode.

NFR-021/HK-037: message text touches this module only transiently (per-cycle text
dedup, matching Ft8Decoder.cs:338-354's own convention, and payload re-encoding
for the outcome-field comparison) -- never logged, never written to disk. Only
numeric/boolean outcomes cross this module's boundary.
"""
from __future__ import annotations

import collections
import multiprocessing
import os
import time

import numpy as np
from scipy.signal import hilbert

import comparator as CMP
import common
import corpus
import fitter
import gl_dll_pin as DC
import pack77_fields as PF
import wavio

TAU0_S = -0.1600
W_STAR = 0.32
W_EXTRA = 0.16
CORROBORATION_DELTA_F_HZ = 10.0
N_WORKERS = min(12, max(1, multiprocessing.cpu_count() - 1))

RR73_ONAIR_V_STAR = (0, corpus.RR73_ONAIR_IGRID4)

_CYCLE_OWSFZ = {}
_CYCLE_WSJTX = {}


def _is_rr73_std(p77) -> bool:
    f = PF.std_fields(p77)
    return f.i3 == 1 and (f.ir, f.igrid4) == CMP.RR73_STD


def _same_qso(ref_p77, cand_p77) -> bool:
    """True if `cand_p77` (from a real LDPC decode) is the SAME transmission as
    `ref_p77` (from re-encoded logged text): exact bit match, or ref is our own
    RR73-standard encoding and candidate carries the on-air RR73 sentinel with
    matching call1/call2 (see module docstring)."""
    if ref_p77 == cand_p77:
        return True
    if not _is_rr73_std(ref_p77):
        return False
    return CMP.payload_match(ref_p77, cand_p77, "C1 C2 RR73", RR73_ONAIR_V_STAR)


def _is_reencodable(enc, msg: str):
    tokens = msg.split()
    if msg.startswith("<") or "<" in msg:
        return None
    if len(tokens) < 3:
        return None
    return enc.encode_tones(msg)


def _pool_init(cycle_owsfz, cycle_wsjtx):
    global _CYCLE_OWSFZ, _CYCLE_WSJTX
    _CYCLE_OWSFZ = cycle_owsfz
    _CYCLE_WSJTX = cycle_wsjtx


def _process_cycle(args):
    """Runs in a worker process. Returns numeric-only counters for one cycle."""
    ts, dll_path = args
    enc = corpus.Encoder(dll_path)
    dec = DC.load_decoder(common.RUN_DIR)

    owsfz_here = _CYCLE_OWSFZ.get(ts, [])
    wsjtx_here = _CYCLE_WSJTX.get(ts, [])

    pcm = wavio.load_cycle_pcm(corpus.cycle_wav_path(ts))
    x_a = hilbert(pcm)

    original_payloads = []
    fits = []  # (start_sample, r_l2, seg, freq_hz)
    for msg, _snr, dt, freq_hz in owsfz_here:
        tones = _is_reencodable(enc, msg)
        if tones is None:
            continue
        p77 = enc.payload77(msg)
        if p77 is not None:
            original_payloads.append(p77)
        nominal_t = float(dt) + TAU0_S
        fit = fitter.fine_fit_with_drift(x_a, tones, float(freq_hz), nominal_t_s=nominal_t)
        if fit is None:
            continue
        r_l2 = fitter.apply_freq_shift(fit["r_base"], fit["best_df_hz"])
        fits.append((fit["start_sample"], r_l2, fit["seg"], float(freq_hz)))

    # Pre-encode WSJT-X's own list once per cycle (small, <=~30 typically).
    wsjtx_payloads = []
    for wmsg, _s, _d, wfreq in wsjtx_here:
        wp77 = enc.payload77(wmsg)
        wsjtx_payloads.append((wp77, wfreq))

    def build_residual(w_env):
        buf = pcm.astype(np.float64).copy()
        for start, r_l2, seg, _f in fits:
            c = fitter.lp_envelope(seg, r_l2, w_env)
            s_hat = np.real(c * r_l2)
            n = len(s_hat)
            end = start + n
            if start < 0 or end > len(buf):
                continue
            buf[start:end] -= s_hat
        return buf

    def decode_and_classify(buf, track_ghost_dist=False):
        results = dec.decode_all(buf.astype(np.float32))
        if not results:
            return {"n_new": 0, "n_corroborated": 0, "ghost_dists": []}
        seen_text = set()
        n_new = 0
        n_corrob = 0
        used_wsjtx = set()
        ghost_dists = []
        for res in results:
            msg = res["message"]
            if msg in seen_text:
                continue  # Ft8Decoder.cs:338-354's own text-dedup
            seen_text.add(msg)
            p77 = enc.payload77(msg)
            if p77 is None:
                continue
            if any(_same_qso(op, p77) for op in original_payloads):
                continue  # already known to OWS before subtraction
            n_new += 1
            best = None
            for j, (wp77, wfreq) in enumerate(wsjtx_payloads):
                if j in used_wsjtx or wp77 is None:
                    continue
                df = abs(wfreq - res["freq_hz"])
                if df > CORROBORATION_DELTA_F_HZ:
                    continue
                if _same_qso(wp77, p77):
                    if best is None or df < best[0]:
                        best = (df, j)
            if best is not None:
                used_wsjtx.add(best[1])
                n_corrob += 1
                if track_ghost_dist and fits:
                    # Diagnostic only (stage2_ghost_check.py): distance from this
                    # NEW+corroborated decode's own frequency to the NEAREST
                    # signal that was subtracted from this same cycle. Near-zero
                    # would suggest a re-decoded ghost of a known signal, not a
                    # genuinely different, previously-masked one.
                    ghost_dists.append(min(abs(res["freq_hz"] - f) for _s, _r, _sg, f in fits))
        return {"n_new": n_new, "n_corroborated": n_corrob, "ghost_dists": ghost_dists}

    return {
        "cycle_ts": ts,
        "n_wsjtx": len(wsjtx_here),
        "n_subtracted": len(fits),
        "w_star": decode_and_classify(build_residual(W_STAR), track_ghost_dist=True),
        "w_extra": decode_and_classify(build_residual(W_EXTRA)),
    }


def run_stage2(pop, log, progress_every=20):
    owsfz_raw = corpus._load_all_txt(common.OWSFZ_ALL_TXT)
    wsjtx_raw = corpus._load_all_txt(common.WSJTX_ALL_TXT)
    cycles = sorted({r["cycle_ts"] for r in pop["split_b"]})
    cycle_set = set(cycles)
    log("stage2: n_cycles=%d" % len(cycles))

    cycle_owsfz = collections.defaultdict(list)
    for (ts, msg), (snr, dt, freq) in owsfz_raw.items():
        if ts in cycle_set:
            cycle_owsfz[ts].append((msg, snr, dt, freq))
    cycle_wsjtx = collections.defaultdict(list)
    for (ts, msg), (snr, dt, freq) in wsjtx_raw.items():
        if ts in cycle_set:
            cycle_wsjtx[ts].append((msg, snr, dt, freq))

    dll_path = os.path.join(common.RUN_DIR, "bin", "libft8_C3.dll")
    tasks = [(ts, dll_path) for ts in cycles]

    t0 = time.time()
    out = []
    with multiprocessing.Pool(processes=N_WORKERS, initializer=_pool_init,
                               initargs=(cycle_owsfz, cycle_wsjtx)) as pool:
        for i, rec in enumerate(pool.imap(_process_cycle, tasks), 1):
            out.append(rec)
            if i % progress_every == 0 or i == len(tasks):
                log("  stage2: [%d/%d cycles] elapsed=%.0fs" % (i, len(tasks), time.time() - t0))
    log("stage2: done n_cycles=%d elapsed=%.0fs" % (len(out), time.time() - t0))
    return out


N_BOOT = 2000
BOOT_SEED = common.SEED


def summarize(cycle_results: list, leg: str, log):
    """leg: 'w_star' or 'w_extra'. Returns the primary DeltaR (pp) statistic with
    a cycle-clustered bootstrap CI, plus uncorroborated counts."""
    rng = np.random.default_rng(BOOT_SEED)
    n_wsjtx = np.array([r["n_wsjtx"] for r in cycle_results], dtype=np.float64)
    n_new = np.array([r[leg]["n_new"] for r in cycle_results], dtype=np.float64)
    n_corrob = np.array([r[leg]["n_corroborated"] for r in cycle_results], dtype=np.float64)

    total_wsjtx = float(n_wsjtx.sum())
    total_corrob = float(n_corrob.sum())
    total_new = float(n_new.sum())
    total_uncorrob = total_new - total_corrob
    delta_r = 100.0 * total_corrob / total_wsjtx if total_wsjtx > 0 else float("nan")

    n_c = len(cycle_results)
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx = rng.integers(0, n_c, size=n_c)
        w = n_wsjtx[idx].sum()
        c = n_corrob[idx].sum()
        boot[b] = 100.0 * c / w if w > 0 else np.nan
    ci_lo = float(np.nanpercentile(boot, 2.5))
    ci_hi = float(np.nanpercentile(boot, 97.5))

    if ci_lo >= 1.0:
        verdict = "WIN"
    elif ci_lo > 0.0:
        verdict = "SMALL"
    else:
        verdict = "NONE"

    result = {
        "leg": leg, "n_cycles": n_c,
        "total_wsjtx": int(total_wsjtx), "total_new": int(total_new),
        "total_corroborated": int(total_corrob), "total_uncorroborated": int(total_uncorrob),
        "uncorroborated_share": (total_uncorrob / total_new) if total_new > 0 else float("nan"),
        "delta_r_pp": delta_r, "ci_lo_pp": ci_lo, "ci_hi_pp": ci_hi,
        "verdict": verdict,
    }
    log("stage2 [%s]: %s" % (leg, result))
    return result
