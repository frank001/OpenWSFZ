"""Core measurements for the #194 captured-audio scan (spec 2026-10-02-1720, section 4).

Read-only, CPU only. Audio only: no ALL.TXT, no message text. Every function is pure
(arrays in, numbers out) so the positive control can inject into copies and re-measure
through exactly the same code path.

Interpretations the spec leaves open (all stated again in the report):
  * `rho_peak` is the peak of the overlap-normalised cross-correlation
    rho(L) = sum x[n+L] r[n] / sqrt(sum x[n+L]^2 * sum r[n]^2), sums over the overlap,
    L in +/-3.5 s; the sign is kept in `rho_sign` (polarity).
  * `click_max`: e_hf = e - medfilt(e, 31); click_max = max|e_hf| / (1.4826 * MAD(e_hf)).
  * `tile_excess_db`: residual power in 1 s x 100 Hz tiles, 200-3000 Hz, the 14 whole
    seconds of the slot (Hann window); max tile over the median tile, in dB.
  * `drift_ppm`: signed; the anomaly rule applies to |drift_ppm|.

Architect ruling 2026-10-02 1915 (A1-A6) adds the FIXED rules below (GROUPS, FAMILIES, the tail
and head rules, clip at >= 1). This file is the definition of record for the scan (A4); its
SHA-256 is written into thresholds.json.
"""
from __future__ import annotations

import hashlib
import math
import wave
from pathlib import Path

import numpy as np
from scipy.signal import medfilt

FS = 12_000                       # captured and reference rate (Hz)
SLOT_N = 15 * FS                  # 180 000 samples
MAX_LAG_S = 3.5                   # spec section 4
MAX_LAG = int(MAX_LAG_S * FS)
FADE_S = 0.2                      # run_scenario._FADEOUT_DURATION_S (asserted by the caller)
STEP_WIN_S = 0.5
DRIFT_SEG_S = 4.0
TILE_FREQ_LO, TILE_FREQ_HI, TILE_BW = 200, 3000, 100
TILE_SEG_S = 1
NFFT = 1 << 19                    # 524 288 > 180 000 + 2 * 50 000 (no circular wrap)
PAD = 50_000
INT16_MAX, INT16_MIN = 32767, -32768


def read_wav(path: Path) -> dict:
    """Header fields, the int16 samples and the SHA-256 of the file's bytes."""
    raw = Path(path).read_bytes()
    with wave.open(str(path), "rb") as w:
        ch, bits, fs, n = w.getnchannels(), w.getsampwidth() * 8, w.getframerate(), w.getnframes()
        frames = w.readframes(n)
    if bits != 16:
        raise ValueError(f"{path}: {bits}-bit WAV not supported")
    x = np.frombuffer(frames, dtype="<i2")
    if ch != 1:
        x = x.reshape(-1, ch)[:, 0]
    return {"sha256": hashlib.sha256(raw).hexdigest(), "fs": fs, "bits": bits,
            "channels": ch, "n_samples": int(n), "x": x}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- correlation
def _xcorr(x: np.ndarray, r: np.ndarray, max_lag: int = MAX_LAG):
    """Return (lags, c, rho) for L in [-max_lag, max_lag]; c(L)=sum x[n+L] r[n]."""
    N, M = len(x), len(r)
    X = np.fft.rfft(x, NFFT)
    R = np.fft.rfft(r, NFFT)
    cc = np.fft.irfft(X * np.conj(R), NFFT)
    lags = np.arange(-max_lag, max_lag + 1)
    c = cc[lags % NFFT]
    # overlap energies: n in [max(0,-L), min(M, N-L))
    cx = np.concatenate(([0.0], np.cumsum(x.astype("float64") ** 2)))
    cr = np.concatenate(([0.0], np.cumsum(r.astype("float64") ** 2)))
    lo = np.maximum(0, -lags)
    hi = np.minimum(M, N - lags)
    ok = hi > lo
    ex = np.where(ok, cx[np.clip(hi + lags, 0, N)] - cx[np.clip(lo + lags, 0, N)], 0.0)
    er = np.where(ok, cr[np.clip(hi, 0, M)] - cr[np.clip(lo, 0, M)], 0.0)
    den = np.sqrt(np.maximum(ex * er, 1e-300))
    rho = np.where(ok, c / den, 0.0)
    return lags, c, rho


def rho_peak(x: np.ndarray, r: np.ndarray) -> tuple[float, int]:
    """(max |rho|, sign) of the overlap-normalised cross-correlation within +/-3.5 s."""
    _, _, rho = _xcorr(x, r)
    i = int(np.argmax(np.abs(rho)))
    return float(abs(rho[i])), (1 if rho[i] >= 0 else -1)


def _parabolic(y: np.ndarray, i: int) -> float:
    if i <= 0 or i >= len(y) - 1:
        return float(i)
    a, b, c = y[i - 1], y[i], y[i + 1]
    d = a - 2 * b + c
    return float(i) if d == 0 else float(i) + 0.5 * (a - c) / d


def shift_ref(r: np.ndarray, tau: float, n_out: int) -> np.ndarray:
    """y[n] = r(n - tau) for fractional tau (FFT linear phase), length n_out, zeros outside."""
    buf = np.zeros(NFFT)
    buf[PAD:PAD + len(r)] = r
    F = np.fft.rfft(buf)
    k = np.arange(len(F))
    y = np.fft.irfft(F * np.exp(-2j * np.pi * k * tau / NFFT), NFFT)
    return y[PAD:PAD + n_out]


def _seg_lag(x: np.ndarray, r: np.ndarray, a: int, b: int, tau0: int) -> float:
    """Local lag (samples, fractional) of r[a:b] inside x around tau0, +/-DRIFT_SEARCH."""
    seg = r[a:b]
    cs, ds = [], range(-DRIFT_SEARCH, DRIFT_SEARCH + 1)
    for d in ds:
        s = a + tau0 + d
        if s < 0 or s + (b - a) > len(x):
            cs.append(-np.inf)
            continue
        cs.append(float(np.dot(x[s:s + (b - a)], seg)))
    cs = np.asarray(cs)
    i = int(np.argmax(cs))
    return tau0 + (-DRIFT_SEARCH) + _parabolic(cs, i)


# --------------------------------------------------------------------------- the fit
AMBIG_RATIO = 0.9        # second distinct correlation peak >= 0.9 x the best => lag not identifiable
AMBIG_EXCL = 6           # samples either side of the best peak that do not count as "distinct"
TAIL_MIN_SAMPLES = 1     # a zero run touching the end of the file is the tail pad (excluded)
DRIFT_SEARCH = 300       # +/- samples for the segment lag fits (a mid-slot lag step of ~115 seen)


def _runs(mask: np.ndarray):
    """(start, length) of every run of True."""
    if not mask.any():
        return []
    d = np.diff(np.r_[0, mask.view(np.int8), 0])
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return list(zip(st.tolist(), (en - st).tolist()))


def ref_is_ambiguous(r: np.ndarray) -> bool:
    """A3' (ruling 2026-10-02 1955): the reference's OWN autocorrelation has a second distinct peak
    (more than AMBIG_EXCL samples from zero lag) >= AMBIG_RATIO x its zero-lag peak. Independent of
    the capture, so no chain fault can switch it on."""
    lags, c, rho = _xcorr(r, r)
    zero = int(np.argmax(rho))
    far = np.abs(np.arange(len(rho)) - zero) > AMBIG_EXCL
    second = float(np.max(np.abs(rho[far]))) if far.any() else 0.0
    return bool(second >= AMBIG_RATIO * float(rho[zero]))


def measure(x_i16: np.ndarray, ref: np.ndarray, fade_s: float = FADE_S) -> dict:
    """All section-4 per-slot numbers for one captured slot against its reference.

    x_i16 : captured samples (int16). ref: reference (float, 12 kHz, <= 180 000 samples).
    """
    x = x_i16.astype("float64") / 32768.0
    r = np.asarray(ref, dtype="float64")
    M = min(len(r), SLOT_N)
    r = r[:M]
    N = len(x)
    out: dict = {}

    # integer lag then parabolic refinement (on the raw correlation)
    lags, c, rho = _xcorr(x, r)
    j = int(np.argmax(np.abs(rho)))
    out["rho_peak"] = float(abs(rho[j]))
    out["rho_sign"] = 1 if rho[j] >= 0 else -1
    i = int(np.argmax(rho * out["rho_sign"]))
    far = np.abs(np.arange(len(rho)) - i) > AMBIG_EXCL
    second = float(np.max(np.abs(rho[far]))) if far.any() else 0.0
    cap_ambiguous = bool(second >= AMBIG_RATIO * out["rho_peak"])     # the OLD A3 test, on the capture
    out["lag_ambiguous"] = ref_is_ambiguous(r)                        # A3': a property of the reference only
    # A10: on a slot whose reference is NOT ambiguous, a capture that has lost its clean correlation
    # peak is itself a timing anomaly ("lag_lost", timing family). NaN where not applicable.
    out["lag_lost"] = float(cap_ambiguous) if not out["lag_ambiguous"] else float("nan")
    tau = float(lags[0]) + _parabolic(c * out["rho_sign"], i)
    t0 = int(round(tau))

    # support: reference non-zero, not in the fade tail, inside the captured file, and not in a
    # zero pad that touches either end of the file (WSJT-X writes 14.4 s of audio then zeros)
    n_fade = int(fade_s * FS)
    sup_ref = (r != 0.0)
    sup_ref[max(0, M - n_fade):] = False
    sup = np.zeros(N, dtype=bool)
    lo, hi = max(0, t0), min(N, M + t0)
    if hi > lo:
        sup[lo:hi] = sup_ref[lo - t0:hi - t0]
    zero = (x_i16 == 0)
    head = tail = 0
    for st, ln in _runs(zero):
        if st == 0:
            head = ln
        if st + ln == N:
            tail = ln
    if head:
        sup[:head] = False
    if tail >= TAIL_MIN_SAMPLES:
        sup[N - tail:] = False
    out["head_zero_ms"] = head / FS * 1000.0
    out["tail_zero_ms"] = tail / FS * 1000.0
    out["n_support"] = int(sup.sum())

    rs = shift_ref(r, tau, N)
    num = float(np.dot(x[sup], rs[sup]))
    den = float(np.dot(rs[sup], rs[sup]))
    g = num / den if den > 0 else 0.0
    e = x - g * rs
    sig_p = float(np.sum((g * rs[sup]) ** 2))
    err_p = float(np.sum(e[sup] ** 2))
    out["g_db"] = 20 * math.log10(abs(g)) if g != 0 else float("-inf")
    out["tau_ms"] = tau / FS * 1000.0 if not out["lag_ambiguous"] else float("nan")
    out["resid_db"] = 10 * math.log10(err_p / sig_p) if sig_p > 0 and err_p > 0 else float("nan")

    # level step within a slot: 0.5 s windows
    w = int(STEP_WIN_S * FS)
    idx = np.flatnonzero(sup)
    gw = []
    if len(idx):
        for a in range(int(idx[0]), int(idx[-1]) - w + 2, w):
            m = sup[a:a + w]
            if m.sum() < w // 2:
                continue
            xr = np.dot(x[a:a + w][m], rs[a:a + w][m])
            rr = np.dot(rs[a:a + w][m], rs[a:a + w][m])
            if rr > 0 and xr != 0:
                gw.append(abs(xr / rr))
            elif rr > 0:
                gw.append(1e-6)
    out["step_db_max"] = float(max(abs(20 * math.log10(v / abs(g))) for v in gw)) if gw and g != 0 else float("nan")

    # drift: lag on the first and last 4 s of the covered reference support
    seg = int(DRIFT_SEG_S * FS)
    ra = max(0, -t0) + DRIFT_SEARCH + 1
    rb = min(M - n_fade, N - t0) - DRIFT_SEARCH - 1
    if tail:
        rb = min(rb, N - tail - t0 - DRIFT_SEARCH - 1)
    if head:
        ra = max(ra, head - t0 + DRIFT_SEARCH + 1)
    if rb - ra > 3 * seg and not out["lag_ambiguous"]:
        t_first = _seg_lag(x, r, ra, ra + seg, t0)
        t_last = _seg_lag(x, r, rb - seg, rb, t0)
        out["drift_ppm"] = (t_last - t_first) / ((rb - seg / 2) - (ra + seg / 2)) * 1e6
        out["drift_dlag_samples"] = t_last - t_first
    else:
        out["drift_ppm"] = float("nan")
        out["drift_dlag_samples"] = float("nan")

    # longest run of exactly-zero captured samples inside the (pad-trimmed) support
    best = 0
    for st, ln in _runs(zero & sup):
        best = max(best, ln)
    out["zero_run_ms"] = best / FS * 1000.0

    # clicks and tiles: on the residual inside the support only
    es = e[sup]
    if len(es) > 100:
        ehf = es - medfilt(es, 31)
        mad = float(np.median(np.abs(ehf - np.median(ehf)))) * 1.4826
        out["click_max"] = float(np.max(np.abs(ehf)) / mad) if mad > 0 else float("nan")
    else:
        out["click_max"] = float("nan")

    # tiles: 1 s x 100 Hz residual power, 200-3000 Hz, whole seconds fully inside the support
    win = np.hanning(FS)
    edges = np.arange(TILE_FREQ_LO, TILE_FREQ_HI + 1, TILE_BW)
    tiles = []
    for s in range(14):
        a = s * FS
        if a + FS > N or not sup[a:a + FS].all():
            continue
        P = np.abs(np.fft.rfft(e[a:a + FS] * win)) ** 2   # 1 Hz bins
        tiles.extend(float(P[p:q].sum()) for p, q in zip(edges[:-1], edges[1:]))
    if tiles:
        tiles = np.asarray(tiles)
        med = float(np.median(tiles))
        out["tile_excess_db"] = 10 * math.log10(tiles.max() / med) if med > 0 else float("nan")
    else:
        out["tile_excess_db"] = float("nan")

    out["clip_n"] = int(np.sum((x_i16 >= INT16_MAX) | (x_i16 <= INT16_MIN)))
    out["g_sign"] = 1 if g >= 0 else -1
    return out


# --------------------------------------------------------------------------- thresholds
# metric -> (kind, floor).  kind "dev": two-sided, on |m - median|; "abs": one-sided on |m|
# for drift, one-sided upward on m for the rest.  Floors are the spec's (section 5); a metric
# the spec gives no floor for carries None (no floor).
RULES = {
    "g_db":           ("dev", 0.5),
    "tau_ms":         ("dev", 2.0),
    "step_db_max":    ("up", 0.5),
    "lag_lost":       ("up", None),     # A10: new, calibrated like any metric
    "drift_ppm":      ("abs", 20.0),
    "zero_run_ms":    ("up", 5.0),
    "tile_excess_db": ("up", 10.0),
    "clip_n":         ("up", 0.0),     # A6: any clipped sample flags (m > 0 == m >= 1)
    "click_max":      ("up", None),
    "resid_db":       ("up", None),
}
CROSS_RULES = {"dg_db": ("dev", 0.5), "dtau_ms": ("dev", 2.0)}
# --- Ruling 2026-10-02 1915 -------------------------------------------------------------
# A5: groups fixed by what the scenario plays, not by medians.
def group_of(scenario: str, part) -> str:
    part = int(part)
    if scenario in ("S1", "S1b", "S2", "S3"):
        return "single"
    if scenario in ("S4", "S7", "S8"):
        return "multi"
    if scenario == "S5":
        return {0: "noise", 1: "noise", 2: "tone2", 3: "tone3"}[part]
    raise ValueError(f"no group for scenario {scenario}")


GROUPS = ("single", "multi", "noise", "tone2", "tone3")
MIN_GROUP_N = 20                 # a group below this uses its 09-23 thresholds (never recalibrated)
DESCRIPTIVE_FRACTION = 0.02      # one-sided flags above this share of a group => DESCRIPTIVE
# metric families for the BOTH classification (same slot, same family, both sides)
FAMILIES = {"g_db": "level", "step_db_max": "level",
            "tau_ms": "timing", "drift_ppm": "timing", "lag_lost": "timing",
            "zero_run_ms": "dropout", "head_zero_ms": "dropout", "tail_zero_ms": "dropout",
            "tile_excess_db": "spectral", "click_max": "spectral", "resid_db": "spectral",
            "clip_n": "clip"}
WSJTX_TAIL_MS = 600.0            # WSJT-X writes 14.4 s then zeros (A2); blind spot: its last 600 ms
TAIL_HEAD_TOL_MS = 5.0
CLIP_FLAG_MIN = 1                # A6: flag at clip_n >= 1

K_SIGMA = 6.0
MAD_SCALE = 1.4826


def robust(v: np.ndarray) -> tuple[float, float]:
    v = np.asarray([a for a in v if a == a and np.isfinite(a)], dtype="float64")
    med = float(np.median(v))
    return med, float(np.median(np.abs(v - med)))


def threshold_row(values, kind: str, floor):
    base = values if kind != "abs" else [abs(a) for a in values]
    med, mad = robust(np.asarray(base))
    spread = K_SIGMA * MAD_SCALE * mad
    if kind == "dev":
        t_dev = max(spread, floor or 0.0)
        return {"kind": kind, "median": med, "mad": mad, "rule_value": spread, "floor": floor,
                "floor_applied": bool(floor is not None and spread < floor), "T": t_dev,
                "flag_if": "abs(m - median) > T"}
    t = med + spread
    return {"kind": kind, "median": med, "mad": mad, "rule_value": t, "floor": floor,
            "floor_applied": bool(floor is not None and t < floor),
            "T": max(t, floor) if floor is not None else t,
            "flag_if": "abs(m) > T" if kind == "abs" else "m > T"}


def flagged(value: float, row: dict) -> bool:
    if value != value:
        return False
    if row["kind"] == "dev":
        return abs(value - row["median"]) > row["T"]
    if row["kind"] == "abs":
        return abs(value) > row["T"]
    return value > row["T"]
