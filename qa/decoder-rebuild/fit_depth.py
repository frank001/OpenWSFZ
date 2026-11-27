#!/usr/bin/env python3
"""FIT-DEPTH (spec-fit-depth.md, Architect 2026-11-27): how deeply does QA's production-equivalent fit remove a strong signal, and does a shorter envelope window or a plain-CPFSK template do better?

  python -I fit_depth.py --tag pilot --slices S40 --cycles 20          timing pilot: the first 20 cycles of the slice
  python -I fit_depth.py --tag full --k 1                                every k-th cycle of each slice (k from the pilot's timing, spec 3.4)

Offline, CPU only. Re-fits every WSJT-X decode >= -15 dB of the LC-BASE cycles (S40, H40, H20; the cycle lists are the xn run's sel.json) with fitter.py (the SUB-FEAS fitter, now with a `smooth` switch;
default unchanged) on the original audio, once per pulse shape (GFSK BT=2 / plain CPFSK), then the envelope + subtraction once per window W in {0.64, 0.32, 0.16, 0.08} s: 8 variants.
Per signal and variant (spec 2.1-2.3): L before/after in the signal's own tone cells (79 own cells vs the trimmed mean of 7x79 reference cells), by thirds; the noise control (same template at a free spot) -> D = L_after - L_ctl;
for S0-S2 an injected -18 dB synthetic neighbour T: L_T (what S leaves where T is read) and T's retention loss.

HK-037 / NFR-021: message text is read inside read_wsjtx() ONLY, which returns numbers and tone arrays; the per-signal records written to _qa-scratch carry numbers only. T is a fixed Q-prefix message.
Choices the spec leaves open (stated, and repeated in the result): the injected neighbour reuses S's fitted position (the search is not repeated on the injected audio; only the envelope is, as the injection changes the audio the envelope reads);
the drift of the fit is applied at each symbol's centre when placing the cells; T's level is scaled from the trimmed-mean reference cells of S's grid before subtraction (white-noise relation, 2500 Hz scale);
RR73: both encodings are fitted with the GFSK search and the better score kept (corpus.py's practice); the injection spot is the first admissible of the 6 offsets in a seeded order (Architect's clarification: other decodes than S within +-60 Hz
of T, lean's included, make an offset inadmissible; none admissible -> S skipped and counted).
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import multiprocessing
import os
import sys
import time

import numpy as np
from scipy.signal import hilbert

HERE = os.path.dirname(os.path.abspath(__file__))
SF = os.path.abspath(os.path.join(HERE, "..", "rr-study", "sub-feas"))
sys.path.insert(0, SF)
import common  # noqa: E402  (appends the gap-locate and synth paths)
import corpus  # noqa: E402
import fitter  # noqa: E402
import synth.modulator as MOD  # noqa: E402
import wavio  # noqa: E402

ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
SC = r"D:\Projects\claude\_qa-scratch"
LCRUNS = SC + r"\lc-base\runs"
SLICES = {"S40": (170, "20261114_2312_endurance_run-gathered"), "H40": (240, "20261028_2233_endurance_run-gathered"), "H20": (240, "20260808_live_run_0016-8080")}
DLL = ART + r"\sub-feas\bin\libft8_C3.dll"

SEED = 20261127
TAU0_S = -0.1600                       # SUB-FEAS ROW 0g (September corpus); NOT used here: calibrate_tau0 measures the offset on each slice
FS = fitter.FS
N_TX = fitter.N_TX
SYMBOL = 1920
NSYM = 79
TONE_HZ = 6.25
WINDOWS = (0.64, 0.32, 0.16, 0.08)
PRODUCTION_W = 0.32
SHAPES = (("gfsk", True), ("cpfsk", False))
BANDS = (("S0", 0, 10**6), ("S1", -5, 0), ("S2", -10, -5), ("SC", -15, -10))     # lower bound inclusive: S0 >= 0, S1 -5..-1, S2 -10..-6, SC -15..-11
SNR_MIN = -15
CROWD_HZ = 60.0
SELF_TOL_HZ = 3.2                      # SUB-PROBE's position tolerance: a lean decode this close to S IS S
TRIM_TOP = 0.10
T_LEVEL_DB = -18.0
T_OFFSETS_HZ = (-37.5, -25.0, -12.5, 12.5, 25.0, 37.5)
T_TIME_RANGE_S = 0.5
CTL_LO_HZ, CTL_HI_HZ = 200.0, 2800.0
T_MESSAGE = "Q1ZZZ Q2YYY JO33"          # NFR-021: Q-prefix synthetic
NOISE_BW_RATIO = 2500.0 / (FS / 2.0)   # 2500 Hz of the 0..6000 Hz audio band
KIND_SUB = 1
N_WORKERS = max(1, min(14, multiprocessing.cpu_count() - 2))

assert N_TX == NSYM * SYMBOL == 151680
assert FS == 12000


def band_of(snr):
    for n, lo, hi in BANDS:
        if lo <= snr < hi:
            return n
    return None


# ----------------------------------------------------------------------------------------------------------------------------------------------------------- reading (HK-037: text stays in here)
def read_wsjtx(path, stamps, enc):
    """{stamp: [dict(snr, f, dt, tones, tones_alt, reason)]} -- numbers and tone arrays only. reason: None (encodable) or 'hashed' / 'short' / 'not_encodable'."""
    out = {s: [] for s in stamps}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            st = line[:13]
            if st not in out:
                continue
            f = [x for x in line.split(" ") if x]
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                snr, freq, dt = int(f[4]), int(f[6]), float(f[5])
            except ValueError:
                continue
            msg = " ".join(f[7:]).strip()
            rec = {"snr": snr, "f": float(freq), "dt": dt, "tones": None, "tones_alt": None, "reason": None, "rr73": False}
            toks = msg.split()
            if "<" in msg:
                rec["reason"] = "hashed"
            elif len(toks) < 3:
                rec["reason"] = "short"
            else:
                t = enc.encode_tones(msg)
                if t is None:
                    rec["reason"] = "not_encodable"
                else:
                    rec["tones"] = t
                    if corpus._is_rr73_message(toks):
                        rec["rr73"] = True
                        try:
                            rec["tones_alt"] = corpus._rr73_alt_tones(enc.payload77(msg))
                        except Exception:
                            rec["tones_alt"] = None
            out[st].append(rec)
    return out


def read_lean_freqs(probe_path, stamps):
    """Frequencies of lean's published results (the probe's SUB rows: kind 1). Numbers only; the file carries no text."""
    out = {s: [] for s in stamps}
    with open(probe_path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 5 or c[0] not in out:
                continue
            if int(c[1]) == KIND_SUB:
                out[c[0]].append(float(c[3]))
    return out


# ----------------------------------------------------------------------------------------------------------------------------------------------------------- the cells (spec 2.1)
class Grid:
    """The 79 symbols x 8 tone cells of a transmission at (start sample, base frequency f0, drift fdot): one DFT bin (1920 samples) per cell; the drift applied at each symbol's centre."""

    def __init__(self, start, f0, fdot, cols=tuple(range(8))):
        self.start = int(start)
        n = np.arange(SYMBOL, dtype=np.float64) / FS
        m = np.arange(NSYM)
        centre = (m + 0.5) * SYMBOL / FS - fitter.TRANSMISSION_S / 2.0
        k = np.asarray(cols)
        f = f0 + TONE_HZ * k[None, :] + fdot * centre[:, None]                 # (79, 8)
        self.E = np.exp(-2j * np.pi * f[:, :, None] * n[None, None, :])        # (79, 8, 1920)

    def power(self, y_full):
        a = self.start
        if a < 0 or a + N_TX > len(y_full):
            return None
        blocks = np.asarray(y_full[a:a + N_TX], dtype=np.float64).reshape(NSYM, SYMBOL)
        proj = np.einsum("mn,mkn->mk", blocks, self.E)
        return proj.real ** 2 + proj.imag ** 2                                  # (79, 8)


def level(P, tones, lo=0, hi=NSYM):
    """L = 10 log10( mean own cells / trimmed mean of the 7 reference cells per symbol ), symbols [lo, hi)."""
    t = np.asarray(tones[lo:hi])
    Pm = P[lo:hi]
    own = Pm[np.arange(hi - lo), t]
    mask = np.ones_like(Pm, dtype=bool)
    mask[np.arange(hi - lo), t] = False
    ref = np.sort(Pm[mask])
    keep = ref[: int(round(len(ref) * (1.0 - TRIM_TOP)))]
    return float(10.0 * math.log10(max(own.mean(), 1e-30) / max(keep.mean(), 1e-30)))


def ref_trimmed_mean(P, tones):
    t = np.asarray(tones)
    mask = np.ones_like(P, dtype=bool)
    mask[np.arange(NSYM), t] = False
    ref = np.sort(P[mask])
    return float(ref[: int(round(len(ref) * (1.0 - TRIM_TOP)))].mean())


# ----------------------------------------------------------------------------------------------------------------------------------------------------------- one cycle
def free_spots(all_freqs):
    f = np.arange(CTL_LO_HZ, CTL_HI_HZ + 1e-9, 1.0)
    ok = np.ones(len(f), dtype=bool)
    for d in all_freqs:
        ok &= np.abs(f - d) > CROWD_HZ
    return f[ok]


def nearest_free_spot(all_freqs, f_s, rng):
    """Amendment 1 (spec 8.2): the free spot NEAREST in frequency to S (clear of every WSJT-X and lean decode, S's own included, by +-60 Hz); the seed only breaks ties."""
    sp = free_spots(all_freqs)
    if not len(sp):
        return None
    dist = np.abs(sp - f_s)
    cand = sp[dist == dist.min()]
    return float(cand[0]) if len(cand) == 1 else float(rng.choice(cand))


def synth_T(tones_T):
    """Unit-amplitude baseband phase of the synthetic neighbour (GFSK BT 2, the modulator's)."""
    return MOD.instantaneous_phase(tones_T, 0.0, FS)


def process_cycle(args):
    t0 = time.time()
    slice_name, cyc_i, stamp, sigs, wav_path, all_freqs, tones_T, tau0 = args
    pcm = wavio.load_cycle_pcm(wav_path).astype(np.float64)
    x_a = hilbert(pcm)
    phaseT = synth_T(tones_T)
    n_ax = np.arange(N_TX, dtype=np.float64) / FS
    recs = []
    for sig in sigs:
        recs.append(process_signal(slice_name, cyc_i, stamp, sig, pcm, x_a, all_freqs, tones_T, phaseT, n_ax, tau0))
    return stamp, recs, time.time() - t0


def process_signal(slice_name, cyc_i, stamp, sig, pcm, x_a, all_freqs, tones_T, phaseT, n_ax, tau0):
    sl_i = list(SLICES).index(slice_name)
    rng = np.random.default_rng(np.random.SeedSequence([SEED, sl_i, cyc_i, sig["idx"]]))
    rec = {"slice": slice_name, "stamp": stamp, "idx": sig["idx"], "snr": sig["snr"], "band": band_of(sig["snr"]), "crowded": sig["crowded"], "f": sig["f"], "dt": sig["dt"],
           "status": "ok", "rr73": sig["rr73"], "alt_used": False}
    nominal_t = sig["dt"] + tau0
    # --- search, once per pulse shape (RR73: both encodings on the GFSK search, the better score kept)
    tones = sig["tones"]
    fit_g = fitter.fine_fit_with_drift(x_a, tones, sig["f"], nominal_t_s=nominal_t, smooth=True)
    if sig["tones_alt"] is not None:
        fit_a = fitter.fine_fit_with_drift(x_a, sig["tones_alt"], sig["f"], nominal_t_s=nominal_t, smooth=True)
        if fit_a is not None and (fit_g is None or fit_a["best_val"] > fit_g["best_val"]):
            fit_g, tones = fit_a, sig["tones_alt"]
            rec["alt_used"] = True
    if fit_g is None:
        rec["status"] = "fit_failed"
        return rec
    fit_c = fitter.fine_fit_with_drift(x_a, tones, sig["f"], nominal_t_s=nominal_t, smooth=False)
    if fit_c is None:
        rec["status"] = "fit_failed"
        return rec
    fits = {"gfsk": fit_g, "cpfsk": fit_c}
    tones_a = np.asarray(tones)
    rec["fit"] = {s: {"dt": f["best_dt_s"], "df": f["best_df_hz"], "fdot": f["best_fdot_hz_per_s"], "start": f["start_sample"], "edge": bool(f["at_edge_t"] or f["at_edge_f"] or f["at_edge_fdot"])} for s, f in fits.items()}

    # --- grids
    f_fit = {s: sig["f"] + fits[s]["best_df_hz"] for s in fits}
    grid_S = {s: Grid(fits[s]["start_sample"], f_fit[s], fits[s]["best_fdot_hz_per_s"]) for s in fits}
    templ = {s: fitter.apply_freq_shift(fits[s]["r_base"], fits[s]["best_df_hz"]) for s in fits}
    seg = {s: fits[s]["seg"] for s in fits}

    P_before = grid_S["gfsk"].power(pcm)
    if P_before is None:
        rec["status"] = "fit_failed"
        return rec
    rec["L_before"] = level(P_before, tones_a)
    rec["fp_before"] = float(P_before.sum())

    # --- the noise control spot (one per signal, shared by all variants)
    f_ctl = nearest_free_spot(all_freqs, sig["f"], rng)
    ctl = None
    if f_ctl is not None:
        rec["ctl_dist_hz"] = abs(f_ctl - sig["f"])
        others = [d for d in all_freqs if abs(d - sig["f"]) > SELF_TOL_HZ]
        keep = [i for i, kk in enumerate(SIDE_COLS)
                if not any(abs(f_fit["gfsk"] + TONE_HZ * kk - d) <= SIDE_MASK_HZ or abs(f_ctl + TONE_HZ * kk - d) <= SIDE_MASK_HZ for d in others)]
        rec["side_cols_kept"] = len(keep)
        side_S = {s: Grid(fits[s]["start_sample"], f_fit[s], fits[s]["best_fdot_hz_per_s"], SIDE_COLS) for s in fits}
        side_C = {s: Grid(fits[s]["start_sample"], f_ctl, fits[s]["best_fdot_hz_per_s"], SIDE_COLS) for s in fits}
        ctl = {s: Grid(fits[s]["start_sample"], f_ctl, fits[s]["best_fdot_hz_per_s"]) for s in fits}
        ctl_r = {s: fitter.apply_freq_shift(fitter.r_fit_drift(tones, fits[s]["best_fdot_hz_per_s"], smooth=SHAPES_D[s]), f_ctl) for s in fits}
        ctl_seg = {s: x_a[fits[s]["start_sample"]:fits[s]["start_sample"] + N_TX] for s in fits}
    else:
        rec["no_ctl_spot"] = True

    # --- the injected neighbour T (S0-S2 only)
    inj = None
    if rec["band"] in ("S0", "S1", "S2"):
        s_all = [d for d in all_freqs if abs(d - sig["f"]) > SELF_TOL_HZ]                 # every other decode (WSJT-X and lean) than S itself (lean's copy of S is within the probe match tolerance)
        order = rng.permutation(len(T_OFFSETS_HZ))
        for oi in order:
            fT = sig["f"] + T_OFFSETS_HZ[oi]
            if fT < CTL_LO_HZ or fT > CTL_HI_HZ:
                continue
            if any(abs(d - fT) <= CROWD_HZ for d in s_all):
                continue
            inj = {"f": float(fT), "off": float(T_OFFSETS_HZ[oi])}
            break
        if inj is None:
            rec["no_inj_spot"] = True
        else:
            for _try in range(50):
                toff = float(rng.uniform(-T_TIME_RANGE_S, T_TIME_RANGE_S))
                sT = fits["gfsk"]["start_sample"] + int(round(toff * FS))
                if 0 <= sT <= len(pcm) - N_TX:
                    break
            else:
                sT = int(np.clip(sT, 0, len(pcm) - N_TX))
            inj["start"], inj["toff"] = sT, float(sT - fits["gfsk"]["start_sample"]) / FS
            sigma2 = ref_trimmed_mean(P_before, tones_a) / SYMBOL                   # white real noise: E|sum y e^-jwt|^2 = N sigma^2
            amp = math.sqrt(2.0 * (10.0 ** (T_LEVEL_DB / 10.0)) * sigma2 * NOISE_BW_RATIO)
            phi = float(rng.uniform(0, 2 * np.pi))
            rT = np.exp(1j * (phaseT + 2 * np.pi * inj["f"] * n_ax))                # unit template of T (baseband carrier at its frequency)
            T_a = np.zeros(len(pcm), dtype=complex)
            T_a[sT:sT + N_TX] = amp * np.exp(1j * phi) * rT
            inj.update(amp=amp, phi=phi, rT=rT, T_a=T_a, grid=Grid(sT, inj["f"], 0.0))
            P_T0 = inj["grid"].power(pcm)
            rec["LT_before"] = level(P_T0, tones_T) if P_T0 is not None else None
            rec["inj"] = {"off": inj["off"], "toff": inj["toff"], "amp": amp}

    # --- the variants
    var = {}
    for sname, _sm in SHAPES:
        for W in WINDOWS:
            v = {}
            c = fitter.lp_envelope(seg[sname], templ[sname], W)
            sub = c * templ[sname]
            res = pcm.copy()
            a0 = fits[sname]["start_sample"]
            res[a0:a0 + N_TX] -= sub.real
            P_after = grid_S[sname].power(res)
            v["L_after"] = level(P_after, tones_a)
            v["thirds"] = [level(P_after, tones_a, 0, 26), level(P_after, tones_a, 26, 53), level(P_after, tones_a, 53, 79)]
            if sname == "gfsk" and W == PRODUCTION_W:
                rec["fp_after_ref"] = float(P_after.sum())
            if ctl is not None:
                cc = fitter.lp_envelope(ctl_seg[sname], ctl_r[sname], W)
                rc = pcm.copy()
                rc[a0:a0 + N_TX] -= (cc * ctl_r[sname]).real
                P_ctl = ctl[sname].power(rc)
                v["L_ctl"] = level(P_ctl, tones_a)
                v["D"] = v["L_after"] - v["L_ctl"]                                       # the own-cell view (blind by construction, spec 8.1)
                v["F"] = float(10.0 * math.log10(P_after.mean() / P_ctl.mean()))        # the footprint excess (spec 8.2): 8 columns x 79 symbols against the noise spot after its control subtraction
                if keep:
                    PsA, PsC = side_S[sname].power(res), side_C[sname].power(rc)
                    v["F_side"] = float(10.0 * math.log10(PsA[:, keep].mean() / PsC[:, keep].mean()))
            if inj is not None:
                xs = seg[sname] + inj["T_a"][a0:a0 + N_TX]
                ci = fitter.lp_envelope(xs, templ[sname], W)
                subi = ci * templ[sname]
                res_noT = pcm.copy()
                res_noT[a0:a0 + N_TX] -= subi.real                                  # (audio + T) - sub - T: T cancels exactly
                P_T = inj["grid"].power(res_noT)
                v["LT_after"] = level(P_T, tones_T) if P_T is not None else None
                xa_res = x_a + inj["T_a"]
                xa_res[a0:a0 + N_TX] -= subi
                sT = inj["start"]
                g = np.sum(xa_res[sT:sT + N_TX] * np.conj(rT_unit(inj))) / N_TX
                ret = float((g * np.exp(-1j * inj["phi"])).real / inj["amp"])
                v["T_ret"] = ret
                v["T_loss_db"] = float(-20.0 * math.log10(ret)) if ret > 1e-3 else 60.0
            var["%s_%.2f" % (sname, W)] = v
    rec["var"] = var
    # --- C1: the Python suppression of the production fit over the footprint (all 632 cells, before/after)
    if "fp_after_ref" in rec:
        rec["supp_py_db"] = float(10.0 * math.log10(rec["fp_before"] / rec["fp_after_ref"]))
    return rec


SHAPES_D = dict(SHAPES)
SIDE_COLS = tuple(list(range(-6, 0)) + list(range(8, 14)))   # 1 to 6 tone spacings outside the 8-column footprint, each side
SIDE_MASK_HZ = 25.0


def rT_unit(inj):
    return inj["rT"]


# ----------------------------------------------------------------------------------------------------------------------------------------------------------- driver
CAL_SNR_MIN = 0
CAL_MAX_SIGNALS = 12
CAL_STEP = 240


def calibrate_tau0(slice_name, stamps, wl, folder):
    """The seed offset of the fit (start time - WSJT-X DT) on THIS slice's recordings: SUB-FEAS's -0.16 s was calibrated on the September corpus and is wrong here (the signals start ~0.5 s after the DT).
    Coarse scan of the transmission start (CAL_STEP samples) with the cell measure L on up to CAL_MAX_SIGNALS strong signals of the first cycles; the median of (start - DT) is the slice's offset (the fit then searches +-100 ms around it)."""
    diffs = []
    for st in stamps[:8]:
        sig = [r for r in wl[st] if r["tones"] is not None and r["snr"] >= CAL_SNR_MIN]
        if not sig:
            continue
        pcm = wavio.load_cycle_pcm(os.path.join(ART, folder, "owsfz", "wav", st + ".wav")).astype(np.float64)
        for r in sig[:3]:
            g = Grid(0, r["f"], 0.0)
            ta = np.asarray(r["tones"])
            best = None
            for a in range(0, len(pcm) - N_TX + 1, CAL_STEP):
                g.start = a
                P = g.power(pcm)
                L = level(P, ta)
                if best is None or L > best[0]:
                    best = (L, a)
            diffs.append(best[1] / FS - r["dt"])
            if len(diffs) >= CAL_MAX_SIGNALS:
                break
        if len(diffs) >= CAL_MAX_SIGNALS:
            break
    d = sorted(diffs)
    return float(np.median(d)), {"n": len(d), "p10": d[int(0.1 * (len(d) - 1))], "p90": d[int(round(0.9 * (len(d) - 1)))]}


def build_tasks(slice_name, k, ncycles, enc, tones_T):
    n, folder = SLICES[slice_name]
    selp = LCRUNS + r"\xn_%s_L_n%d" % (slice_name, n)
    sel = json.load(open(selp + r"\sel.json"))
    stamps = list(sel["runs"][sel["run"]]["FULL"])
    if ncycles:
        stamps = stamps[:ncycles]
    else:
        stamps = stamps[::k]
    wl = read_wsjtx(os.path.join(ART, folder, "wsjt-x", "ALL.TXT"), stamps, enc)
    lean = read_lean_freqs(selp + r"\probe.tsv", stamps)
    tau0, tau_spread = calibrate_tau0(slice_name, stamps, wl, folder)
    print("%s: seed offset (start - DT) = %.3f s, spread %s" % (slice_name, tau0, {k_: round(v, 3) for k_, v in tau_spread.items()}), flush=True)
    tasks, counts = [], collections.defaultdict(collections.Counter)
    for ci, st in enumerate(stamps):
        w = wl[st]
        sigs = []
        for j, r in enumerate(w):
            b = band_of(r["snr"])
            if b is None:
                continue
            if r["reason"] is not None:
                counts[b]["not_encodable_" + r["reason"]] += 1
                continue
            crowded = any(abs(o["f"] - r["f"]) <= CROWD_HZ for i2, o in enumerate(w) if i2 != j)
            sigs.append({"idx": j, "snr": r["snr"], "f": r["f"], "dt": r["dt"], "tones": r["tones"], "tones_alt": r["tones_alt"], "rr73": r["rr73"], "crowded": crowded})
        all_freqs = [o["f"] for o in w] + lean[st]
        if sigs:
            tasks.append((slice_name, stamps.index(st), st, sigs, os.path.join(ART, folder, "owsfz", "wav", st + ".wav"), all_freqs, tones_T, tau0))
    return tasks, counts, len(stamps), (tau0, tau_spread)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--slices", default="S40,H40,H20")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--cycles", type=int, default=0, help="pilot: only the first N cycles of each slice")
    a = ap.parse_args()
    out = SC + r"\fit-depth\%s" % a.tag
    os.makedirs(out, exist_ok=True)
    enc = corpus.Encoder(DLL)
    tones_T = enc.encode_tones(T_MESSAGE)
    assert tones_T is not None and len(tones_T) == NSYM
    meta = {"tag": a.tag, "k": a.k, "cycles": a.cycles, "seed": SEED, "slices": a.slices, "workers": N_WORKERS, "windows": WINDOWS, "dll": DLL}
    t0 = time.time()
    for sl in a.slices.split(","):
        tasks, counts, ncyc, tau = build_tasks(sl, a.k, a.cycles, enc, tones_T)
        meta.setdefault("tau0", {})[sl] = tau
        meta.setdefault("n_cycles", {})[sl] = ncyc
        meta.setdefault("not_encodable", {})[sl] = {b: dict(c) for b, c in counts.items()}
        fh = open(out + r"\recs_%s.jsonl" % sl, "w", encoding="utf-8")
        walls = []
        with multiprocessing.Pool(N_WORKERS) as pool:
            for i, (st, recs, wall) in enumerate(pool.imap(process_cycle, tasks)):      # submission order: deterministic
                walls.append(wall)
                for r in recs:
                    fh.write(json.dumps(r, default=float) + "\n")
                fh.flush()
                if (i + 1) % 10 == 0 or i + 1 == len(tasks):
                    print("%s: %d/%d cycles, elapsed %.0fs, mean cycle wall %.1fs" % (sl, i + 1, len(tasks), time.time() - t0, sum(walls) / len(walls)), flush=True)
        fh.close()
        meta.setdefault("cycle_wall_mean_s", {})[sl] = sum(walls) / max(1, len(walls))
        meta.setdefault("n_tasks", {})[sl] = len(tasks)
    meta["wall_s"] = time.time() - t0
    json.dump(meta, open(out + r"\meta.json", "w"), indent=1, default=float)
    print("done, wall %.0fs" % meta["wall_s"])


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
