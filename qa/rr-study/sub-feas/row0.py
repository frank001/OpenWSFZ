#!/usr/bin/env python3
"""SUB-FEAS ROW 0 (spec sec.6) + Stage 1 gate (sec.7). Orchestrator lives in
run.py; this module holds each row's implementation, numeric-only (HK-037)."""
from __future__ import annotations

import collections
import json
import os
import random
import time

import numpy as np
from scipy.signal import hilbert

import common
import corpus
import fitter

SEED = common.SEED


# ── ROW 0a: encoder fidelity ──────────────────────────────────────────────────

def row0a(dec, pop, log, n_sample=300):
    """Bench: synthesise a clean signal at nominal (freq, DT) and decode it with
    the pinned DLL; the 77-bit payload must round-trip. A handful of real rows
    have DT outside [0, slot_length - transmission] (including the known
    negative-DT capture-chain artefact, memory: "July 40m negative-DT rows...
    capture-chain-suspect (not decoder)") -- a clean synthetic signal simply
    cannot be PLACED at such a DT in a single 15 s slot buffer at all, which is
    not a question this row is testing (it is a population-membership fact, not
    an encoder/decoder fidelity fact). Those rows are VOID here -- reported and
    excluded from BOTH n_ok and the denominator, not silently counted as fails."""
    rows = pop["all_rows"]
    rng = random.Random(SEED)
    sample = rng.sample(rows, min(n_sample, len(rows)))
    n_ok = 0
    n_void = 0
    for r in sample:
        tones = r["tones"]
        r0 = fitter.r_fit(tones)
        t = np.arange(len(r0)) / fitter.FS
        carrier = r0 * np.exp(1j * 2 * np.pi * float(r["freq_hz"]) * t)
        sig = np.real(carrier).astype(np.float64)
        buf = np.zeros(common.BUFFER_SAMPLES, dtype=np.float64)
        start = int(round(float(r["dt"]) * fitter.FS))
        end = start + len(sig)
        if start < 0 or end > len(buf):
            n_void += 1
            continue
        buf[start:end] = sig
        results = dec.decode_all(buf.astype(np.float32))
        if not results:
            continue
        for res in results:
            if abs(res["freq_hz"] - r["freq_hz"]) < 10 and abs(res["dt"] - r["dt"]) < 0.5:
                y_tones = _redecode_tones(dec, res)
                if y_tones is not None and y_tones == tones:
                    n_ok += 1
                    break
    n_tested = len(sample) - n_void
    rate = n_ok / n_tested if n_tested else 0.0
    log("ROW 0a: n_sample=%d n_void=%d n_tested=%d n_ok=%d rate=%.4f bar=0.99"
        % (len(sample), n_void, n_tested, n_ok, rate))
    return {"n_sample": len(sample), "n_void": n_void, "n_tested": n_tested,
            "n_ok": n_ok, "rate": rate, "pass": bool(n_tested > 0 and rate >= 0.99)}


def _redecode_tones(dec, decode_all_result):
    """decode_all already resolved text via the DLL's own hash table (synthetic
    bench data only, ROW 0a -- not real off-air text, HK-037 does not restrict
    this). Re-encode that text to compare tone-for-tone against truth."""
    msg = decode_all_result["message"]
    buf = (__import__("ctypes").c_uint8 * 79)()
    rc = dec.dll.ft8_encode_message(msg.encode("ascii", errors="replace"), buf, 79)
    if rc != 79:
        return None
    return list(buf)


# ── ROW 0d: population size ───────────────────────────────────────────────────

def row0d(pop, log):
    na, nb = len(pop["split_a"]), len(pop["split_b"])
    log("ROW 0d: n_A=%d n_B=%d bar=>=1000 each" % (na, nb))
    return {"n_A": na, "n_B": nb, "pass": bool(na >= 1000 and nb >= 1000)}


# ── ROW 0e: DLL pin ────────────────────────────────────────────────────────────

def row0e(dll_path, expected_sha256, log):
    import hashlib
    h = hashlib.sha256()
    with open(dll_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    ok = got == expected_sha256
    log("ROW 0e: loaded=%s pin=%s equal=%s" % (got, expected_sha256, ok))
    return {"loaded_sha256": got, "pin_sha256": expected_sha256, "pass": bool(ok)}


# ── ROW 0i: twin sanity (Amendment 1) -- computed inside corpus.build_population
# already; passthrough helper for the results table. ─────────────────────────

def row0i(pop, log):
    r = pop["row0i"]
    log("ROW 0i: %s" % r)
    return r


# ── ROW 0g: anchor calibration (wide search on the first-10%% pool) ───────────

def row0g(pop, log, dt_range_ms=1000.0, dt_step_ms=5.0, df_range_hz=3.0, n_fft=131072):
    """Amendment 2 (arch/subtraction-feasibility cdba5cf4): the original IQR<=40ms
    bar was unsatisfiable by construction (OWS logs DT to one decimal on an 80ms
    lattice -- rounding alone gives a uniform +/-50ms error). Replaced: split the
    time-ordered anchor pool into halves; tau0 is still the median over the WHOLE
    pool; PASS iff the two halves' tau0 agree within 10ms (a stable single offset)
    and median Delta-f is still in [-1,+1] Hz."""
    rows = sorted(pop["anchor_rows"], key=lambda r: r["cycle_ts"])
    dts, dfs = [], []
    t0 = time.time()
    n_done = 0
    for r in rows:
        wav_path = corpus.cycle_wav_path(r["cycle_ts"])
        pcm = _load_cycle_pcm_cached(wav_path)
        x_a = hilbert(pcm)
        # nominal_t_s: search from (freq, DT + 0) as the CENTRE of the wide window
        # -- tau0 itself is what this row measures, so the centre is DT, not DT+tau0.
        fit = fitter.fine_fit(x_a, r["tones"], r["freq_hz"], nominal_t_s=float(r["dt"]),
                               dt_range_ms=dt_range_ms, dt_step_ms=dt_step_ms,
                               df_range_hz=df_range_hz, n_fft=n_fft)
        n_done += 1
        if fit is None:
            continue
        dts.append(fit["best_dt_s"])
        dfs.append(fit["best_df_hz"])
        if n_done % 50 == 0:
            log("  ROW 0g: [%d/%d] elapsed=%.0fs" % (n_done, len(rows), time.time() - t0))
    dts_arr = np.array(dts)
    dfs_arr = np.array(dfs)
    tau0 = float(np.median(dts_arr)) if len(dts_arr) else float("nan")
    iqr = float(np.percentile(dts_arr, 75) - np.percentile(dts_arr, 25)) if len(dts_arr) else float("nan")
    median_df = float(np.median(dfs_arr)) if len(dfs_arr) else float("nan")

    half = len(dts_arr) // 2
    tau0_first = float(np.median(dts_arr[:half])) if half > 0 else float("nan")
    tau0_second = float(np.median(dts_arr[half:])) if (len(dts_arr) - half) > 0 else float("nan")
    # round to 1e-6 ms: the underlying values are multiples of 0.5ms (medians of a
    # 5ms-step grid), so this only absorbs IEEE-754 binary representation noise
    # (e.g. -0.165 - (-0.155) coming out as 0.010000000000000009 rather than
    # 0.01 exactly) -- it does not hide any real difference at the search grid's
    # own resolution.
    split_half_diff_ms = (round(abs(tau0_first - tau0_second) * 1000.0, 6)
                           if half > 0 else float("nan"))

    ok = bool(len(dts_arr) > 0 and split_half_diff_ms <= 10.0 and (-1.0 <= median_df <= 1.0))
    log("ROW 0g: n=%d tau0=%.4fs iqr_ms=%.2f(side-note only) tau0_first=%.4fs tau0_second=%.4fs "
        "split_half_diff_ms=%.2f median_df_hz=%.3f pass=%s"
        % (len(dts_arr), tau0, iqr * 1000.0, tau0_first, tau0_second, split_half_diff_ms,
           median_df, ok))
    return {"n": len(dts_arr), "tau0_s": tau0, "iqr_ms": iqr * 1000.0,
            "tau0_first_half_s": tau0_first, "tau0_second_half_s": tau0_second,
            "split_half_diff_ms": split_half_diff_ms,
            "median_df_hz": median_df, "pass": ok}


# ── ROW 0f: RR73 form -- among RR73 rows, does the on-air-grid encoding win the
# correlation over our own MAXGRID4+3 encoding? ──────────────────────────────

def row0f(pop, tau0_s, log):
    rr73_rows = [r for r in pop["all_rows"] if r["is_rr73"] and r["tones_alt"] is not None]
    by_cycle = {}
    for r in rr73_rows:
        by_cycle.setdefault(r["cycle_ts"], []).append(r)

    n_total = 0
    n_onair_wins = 0
    t0 = time.time()
    for ts, rs in by_cycle.items():
        pcm = _load_cycle_pcm_cached(corpus.cycle_wav_path(ts))
        x_a = hilbert(pcm)
        for r in rs:
            nominal_t = float(r["dt"]) + tau0_s
            fit_ows = fitter.fine_fit(x_a, r["tones"], float(r["freq_hz"]), nominal_t)
            fit_air = fitter.fine_fit(x_a, r["tones_alt"], float(r["freq_hz"]), nominal_t)
            if fit_ows is None or fit_air is None:
                continue
            n_total += 1
            if fit_air["best_val"] > fit_ows["best_val"]:
                n_onair_wins += 1
    share = (n_onair_wins / n_total) if n_total else float("nan")
    log("ROW 0f: n_total=%d n_onair_wins=%d share=%.4f elapsed=%.0fs bar=>=0.90"
        % (n_total, n_onair_wins, share, time.time() - t0))
    return {"n_total": n_total, "n_onair_wins": n_onair_wins, "share": share,
            "pass": bool(n_total > 0 and share >= 0.90)}


# ── ROW 0h: convergence -- share of fitted P rows whose optimum sits on the
# search-box edge. ────────────────────────────────────────────────────────────

def row0h(fits_all, log):
    """Amendment 2: now load-bearing (it is what proves the widened +/-100ms box
    is wide enough). Edge union also covers `ḟ` -- it is now a searched dimension
    of the same fine-fit box for L1/L2, so a row pinned at the ḟ boundary is the
    same kind of "box too narrow" signal as a Δt/Δf edge hit. Bar unchanged."""
    n = len(fits_all)
    n_edge = sum(1 for f in fits_all
                 if f["at_edge_t"] or f["at_edge_f"] or f.get("at_edge_fdot", False))
    share = (n_edge / n) if n else float("nan")
    log("ROW 0h: n=%d n_edge=%d share=%.4f bar=<=0.02" % (n, n_edge, share))
    return {"n": n, "n_edge": n_edge, "share": share, "pass": bool(n > 0 and share <= 0.02)}


# ── ROW 0b: synthetic recovery (impairment bench) ────────────────────────────

_SYNTH_CALLS = ["Q1AAA", "Q2BBB", "Q3CCC", "Q4DDD", "Q5EEE", "Q6FFF", "Q7GGG", "Q8HHH"]
_SYNTH_REPORTS = ["-05", "+03", "-12", "R-08", "R+01", "RR73", "-20", "+00"]
SNR_LEVELS_0B = (0.0, 5.0, 10.0)
IMPAIRMENTS_0B = ("none", "drift", "fade")


def _rayleigh_fade_gain(n_samples, fs, doppler_hz, seed):
    """Filtered-complex-Gaussian approximation to Clarke/Jakes fading: white
    complex Gaussian noise, lowpass-filtered to the Doppler bandwidth, unit mean
    power. Adequate for a bench feasibility test, not a channel-model claim."""
    from scipy.signal import butter, filtfilt
    rng = np.random.default_rng(seed)
    noise = (rng.standard_normal(n_samples) + 1j * rng.standard_normal(n_samples)) / np.sqrt(2.0)
    wn = doppler_hz / (fs / 2.0)
    b, a = butter(4, wn, btype="low")
    g = filtfilt(b, a, noise)
    rms = np.sqrt(np.mean(np.abs(g) ** 2))
    return g / rms if rms > 0 else np.ones(n_samples, dtype=complex)


def _synth_signal(enc, rng, impairment, snr_db, seed):
    from synth.channel import add_noise
    call1 = rng.choice(_SYNTH_CALLS)
    call2 = rng.choice([c for c in _SYNTH_CALLS if c != call1])
    report = rng.choice(_SYNTH_REPORTS)
    msg = "%s %s %s" % (call1, call2, report)
    tones = enc.encode_tones(msg)
    if tones is None:
        return None

    true_freq = float(rng.uniform(300.0, 2600.0))
    dt_center = 1.0
    true_dt = dt_center + float(rng.uniform(-0.5, 0.5))
    phase0 = float(rng.uniform(0.0, 2.0 * np.pi))
    drift_hz = 0.5 if impairment == "drift" else 0.0

    phase = __import__("synth.modulator", fromlist=["instantaneous_phase"]).instantaneous_phase(
        tones, 0.0, fitter.FS, drift_hz=drift_hz)
    carrier = np.exp(1j * (phase + phase0))
    if impairment == "fade":
        fade = _rayleigh_fade_gain(len(carrier), fitter.FS, doppler_hz=0.2, seed=seed + 777)
        carrier = carrier * fade
    t = np.arange(len(carrier)) / fitter.FS
    carrier = carrier * np.exp(1j * 2 * np.pi * true_freq * t)
    sig = np.real(carrier).astype(np.float64)
    sig = add_noise(sig, snr_db=snr_db, seed=seed, sample_rate_hz=fitter.FS, noise_cutoff_hz=5900.0)

    buf = np.zeros(common.BUFFER_SAMPLES, dtype=np.float64)
    start = int(round(true_dt * fitter.FS))
    end = start + len(sig)
    if start < 0 or end > len(buf):
        return None
    buf[start:end] = sig
    buf = add_noise(buf, snr_db=30.0, seed=seed + 1, sample_rate_hz=fitter.FS, noise_cutoff_hz=5900.0)
    return {"tones": tones, "true_freq": true_freq, "true_dt": true_dt, "buf": buf}


def row0b(enc, log, n_total=400):
    rng = random.Random(SEED)
    np_rng_seed_base = SEED
    cells = collections.defaultdict(list)  # (impairment, snr) -> list of per-trial dict
    n_by_cell = {}
    combos = [(im, sn) for im in IMPAIRMENTS_0B for sn in SNR_LEVELS_0B]
    base_n = n_total // len(combos)
    rem = n_total - base_n * len(combos)
    counts = [base_n + (1 if i < rem else 0) for i in range(len(combos))]

    trial_seed = SEED
    for (impairment, snr_db), n_c in zip(combos, counts):
        for _ in range(n_c):
            trial_seed += 1
            trial = _synth_signal(enc, rng, impairment, snr_db, trial_seed)
            if trial is None:
                continue
            x_a = hilbert(trial["buf"])
            # Amendment 2: the drift-extended fit, same as L1/L2 in bigfit.py.
            fit = fitter.fine_fit_with_drift(x_a, trial["tones"], trial["true_freq"],
                                              nominal_t_s=trial["true_dt"])
            if fit is None:
                continue
            dt_err = abs(fit["best_dt_s"])
            df_err = abs(fit["best_df_hz"])
            fdot_fit = fit["best_fdot_hz_per_s"]
            r_seg = fitter.apply_freq_shift(fit["r_base"], fit["best_df_hz"])
            x_by_w = {}
            for w in bigfit_w_family():
                y = fitter.subtract(fit["seg"], r_seg, w_s=w)
                m = fitter.residual_metrics(fit["seg"], y, trial["true_freq"])
                x_by_w[w] = m["X_db"]
            cells[(impairment, snr_db)].append({"dt_err": dt_err, "df_err": df_err,
                                                 "fdot_fit": fdot_fit, "x_by_w": x_by_w})

    detail = {}
    overall_pass = True
    for impairment in IMPAIRMENTS_0B:
        trials_all_snr = [t for sn in SNR_LEVELS_0B for t in cells[(impairment, sn)]]
        if not trials_all_snr:
            detail[impairment] = {"void": True}
            overall_pass = False
            continue
        med_by_w = {w: float(np.median([t["x_by_w"][w] for t in trials_all_snr])) for w in bigfit_w_family()}
        best_w = min(med_by_w, key=lambda w: med_by_w[w])
        bar = 1.0 if impairment in ("none", "drift") else 2.0
        per_snr = {}
        imp_ok = True
        for snr in SNR_LEVELS_0B:
            trials = cells[(impairment, snr)]
            if not trials:
                per_snr[snr] = {"void": True}
                imp_ok = False
                continue
            med_x = float(np.median([t["x_by_w"][best_w] for t in trials]))
            ok = med_x <= bar
            per_snr[snr] = {"n": len(trials), "median_X": med_x, "bar": bar, "pass": bool(ok)}
            imp_ok = imp_ok and ok
        if impairment == "none":
            med_dt_err = float(np.median([t["dt_err"] for t in trials_all_snr]))
            med_df_err = float(np.median([t["df_err"] for t in trials_all_snr]))
            ok2 = med_dt_err <= 0.002 and med_df_err <= 0.05
            imp_ok = imp_ok and ok2
            detail[impairment] = {"best_w": best_w, "per_snr": per_snr,
                                   "median_dt_err_s": med_dt_err, "median_df_err_hz": med_df_err,
                                   "pass": bool(imp_ok)}
        else:
            detail[impairment] = {"best_w": best_w, "per_snr": per_snr, "pass": bool(imp_ok)}
        overall_pass = overall_pass and imp_ok
        log("ROW 0b [%s]: best_W=%.2f detail=%s" % (impairment, best_w, detail[impairment]))

    # ROW 0b' (Amendment 2): on the "none" cycles, the drift term must not invent
    # drift that isn't there -- share with |fitted fdot| <= 0.005 Hz/s (one step)
    # must be >= 0.90.
    none_trials = [t for sn in SNR_LEVELS_0B for t in cells[("none", sn)]]
    if none_trials:
        n_ok_fdot = sum(1 for t in none_trials if abs(t["fdot_fit"]) <= fitter.FDOT_STEP_HZ_PER_S)
        share_fdot = n_ok_fdot / len(none_trials)
        row0b_prime = {"n": len(none_trials), "n_ok": n_ok_fdot, "share": share_fdot,
                       "pass": bool(share_fdot >= 0.90)}
    else:
        row0b_prime = {"n": 0, "n_ok": 0, "share": float("nan"), "pass": False}
    log("ROW 0b': %s" % row0b_prime)
    overall_pass = overall_pass and row0b_prime["pass"]

    return {"detail": detail, "row0b_prime": row0b_prime, "pass": bool(overall_pass)}


def bigfit_w_family():
    from bigfit import W_FAMILY
    return W_FAMILY


# ── ROW 0c: noise floor accuracy ──────────────────────────────────────────────

def row0c(log, n_noise_only=200, n_with_signals=200, n_truth_ensemble=50):
    rng = np.random.default_rng(SEED + 5000)
    sigma = 0.2  # arbitrary reference sample std-dev for the floor
    band_width_hz = 56.25  # B_i's own width (spec sec.5), independent of freq_hz here

    # Truth: the EXPECTED noise-floor readout for this sigma, estimated once from
    # a large signal-free ensemble average (low-variance), not a single fresh
    # draw per trial (which would just be comparing two independent noise
    # realisations to each other, not the estimator to a stable truth).
    truth_rng = np.random.default_rng(SEED + 6000)
    truth_vals = []
    for _ in range(n_truth_ensemble):
        truth_buf = truth_rng.standard_normal(common.BUFFER_SAMPLES) * sigma
        truth_vals.append(fitter.noise_floor(truth_buf, band_width_hz))
    truth_n_hat = float(np.mean(truth_vals))

    n_ok = 0
    n_total = 0
    for trial_i in range(n_noise_only + n_with_signals):
        n_signals = 0 if trial_i < n_noise_only else 15
        buf = rng.standard_normal(common.BUFFER_SAMPLES) * sigma
        for _ in range(n_signals):
            f0 = float(rng.uniform(300.0, 2600.0))
            amp = sigma * float(rng.uniform(0.5, 3.0))
            t = np.arange(common.BUFFER_SAMPLES) / fitter.FS
            buf = buf + amp * np.sin(2 * np.pi * f0 * t + float(rng.uniform(0, 2 * np.pi)))
        got = fitter.noise_floor(buf, band_width_hz)
        if truth_n_hat > 0 and got > 0:
            err_db = 10.0 * np.log10(got / truth_n_hat)
            n_total += 1
            if abs(err_db) <= 1.0:
                n_ok += 1
    share = (n_ok / n_total) if n_total else float("nan")
    log("ROW 0c: n_total=%d n_ok=%d share=%.4f truth_n_hat=%.3g bar=>=0.95"
        % (n_total, n_ok, share, truth_n_hat))
    return {"n_total": n_total, "n_ok": n_ok, "share": share, "truth_n_hat": truth_n_hat,
            "pass": bool(n_total > 0 and share >= 0.95)}


_pcm_cache = {}


def _load_cycle_pcm_cached(path):
    # Small LRU-less cache: within one row's processing we only touch a wav once,
    # but split_a/split_b share cycles across is_rr73 legs -- cap memory.
    if path in _pcm_cache:
        return _pcm_cache[path]
    import wavio
    pcm = wavio.load_cycle_pcm(path)
    if len(_pcm_cache) > 4:
        _pcm_cache.clear()
    _pcm_cache[path] = pcm
    return pcm
