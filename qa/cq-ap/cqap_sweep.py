"""CQ-AP A1.3 positive control (Architect spec arch/cq-ap, Amendment 1 A1.3): does the mechanism add anything on clean synthetic audio?

Synthetic `CQ <Q-call> <grid>` (QA's clean-room encoder qa/rr-study/synth, NOT the build's own encoder) in seeded white noise, ONE signal per 15 s cycle,
decoded by the build's native `ft8_decode_all` with the CQ-AP flag OFF and ON on the SAME audio. Q-prefix calls only (NFR-021): nothing real exists here.

Procedure (fixed in code, run once after the freeze commit):
  PHASE A  OFF-only scan, SNR -24..-12 dB in 1 dB steps, 100 cycles per step (seed SEED_A): S50 = the SNR where OFF's decode rate crosses 0.5
           (linear interpolation between the two adjacent steps; rounded to the nearest whole dB).
  PHASE B  grid S50-4 .. S50+1 dB in 1 dB steps (6 steps), 200 cycles per step (seed SEED_B), OFF and ON on the same audio.
  BAR      at one or more steps ON - OFF >= 10 percentage points AND ON's Wilson-95 lower bound > OFF's Wilson-95 upper bound.  PASS / FAIL.
Also reported (descriptive): decodes of a message that is not the one sent (OFF and ON), cq-tagged decodes, ON-only and OFF-only successes per step.
SNR convention: signal power / (noise power in 2500 Hz), white noise over 0..6000 Hz at 12 kHz; the buffer is then RMS-normalised to the decoder's 0.20.
"""
from __future__ import annotations
import argparse, ctypes, hashlib, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "rr-study"))
from synth.encoder import message_to_tones          # clean-room encoder (QA's own)
from synth.modulator import modulate                # DT must lie in [0, 2.36] s (the clamp defect is fixed: out of range raises)

SEED_A, SEED_B = 20261112, 20261113
PIN_SHA256 = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"
SHIM_VERSION = 20260072
FS = 12_000
BUF = 180_000
TARGET_RMS = 0.20                 # Ft8Decoder.cs:53 PcmNormalisationTargetRms
SIL = 1e-6
DECODE_PARAMS = (5, 0.05, 24)     # the station's live values (kMinScorePass2, osdCorrThreshold, osdNhardMax)
SNR_SCAN = list(range(-24, -11)); N_SCAN = 100
GRID_BELOW, GRID_ABOVE, N_GRID = 4, 1, 200
BAR_PP, Z = 0.10, 1.96
F_LO, F_HI, DT_LO, DT_HI = 600.0, 2800.0, 0.2, 1.5
assert (SEED_A, SEED_B, N_SCAN, N_GRID, GRID_BELOW, GRID_ABOVE, BAR_PP) == (20261112, 20261113, 100, 200, 4, 1, 0.10)

LET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GRIDL = "ABCDEFGHIJKLMNOPQR"


def wilson(k, n, z=Z):
    p = k / n; den = 1 + z * z / n; c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / den, (c + r) / den


class Native:
    def __init__(self, path):
        self.sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert self.sha == PIN_SHA256, f"DLL SHA-256 {self.sha} is not the pin"
        d = self.d = ctypes.CDLL(os.path.abspath(path))

        class R(ctypes.Structure):
            _fields_ = [("freq_hz", ctypes.c_int), ("dt", ctypes.c_float), ("snr", ctypes.c_int), ("message", ctypes.c_char * 36)]
        self.R = R
        d.ft8_lib_version_check.restype = ctypes.c_int
        assert d.ft8_lib_version_check() == SHIM_VERSION
        d.ft8_decode_all.restype = ctypes.c_int
        d.ft8_decode_all.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.POINTER(R), ctypes.c_int]
        d.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
        d.ft8_set_decode_params(DECODE_PARAMS[0], DECODE_PARAMS[1], DECODE_PARAMS[2])
        d.ft8_set_osd_sign_fix.argtypes = [ctypes.c_int]; d.ft8_set_osd_sign_fix(1)
        d.ft8_set_cq_ap.argtypes = [ctypes.c_int]
        d.ft8_get_last_ap_kinds.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]; d.ft8_get_last_ap_kinds.restype = ctypes.c_int
        d.ft8_get_last_cq_ap_stats.argtypes = [ctypes.POINTER(ctypes.c_int)] * 3
        self.res = (R * 200)()

    def decode(self, pcm, cq_ap):
        self.d.ft8_set_cq_ap(1 if cq_ap else 0)
        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        n = self.d.ft8_decode_all(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), BUF, self.res, 200)
        assert n >= 0, n
        kinds = (ctypes.c_uint8 * 200)()
        k = self.d.ft8_get_last_ap_kinds(kinds, 200); assert k == n
        att = ctypes.c_int(); dec = ctypes.c_int(); osd = ctypes.c_int()
        self.d.ft8_get_last_cq_ap_stats(ctypes.byref(att), ctypes.byref(dec), ctypes.byref(osd))
        self.d.ft8_set_cq_ap(0)
        return [(self.res[i].message.decode("ascii", "replace").strip(), int(kinds[i])) for i in range(n)], att.value, osd.value


def make_cycle(rng, snr_db):
    call = "Q" + str(rng.integers(0, 10)) + "".join(LET[i] for i in rng.integers(0, 26, size=int(rng.integers(2, 4))))
    grid = GRIDL[rng.integers(0, 18)] + GRIDL[rng.integers(0, 18)] + str(rng.integers(0, 10)) + str(rng.integers(0, 10))
    msg = f"CQ {call} {grid}"
    f0 = float(rng.uniform(F_LO, F_HI)); dt = float(rng.uniform(DT_LO, DT_HI))
    sig = modulate(message_to_tones(msg), f0, dt, FS)
    assert sig.shape[0] == BUF
    # signal power while on air: the transmission is 12.64 s of a 15 s slot; SNR is defined on the on-air power (sine amplitude 1 -> 0.5)
    on_air = 0.5
    sigma2 = on_air / (10 ** (snr_db / 10)) * (6000.0 / 2500.0)
    noise = rng.normal(0.0, math.sqrt(sigma2), size=BUF)
    x = sig + noise
    rms = float(np.sqrt(np.mean(x ** 2)))
    assert rms > SIL
    return msg, (x * (TARGET_RMS / rms)).astype(np.float32)


def run_step(nat, rng, snr_db, n, both):
    off = on = 0; off_wrong = on_wrong = cq_tagged = 0; on_only = off_only = 0; att_sum = 0; osd_sum = 0
    for _ in range(n):
        msg, pcm = make_cycle(rng, snr_db)
        r0, _, _ = nat.decode(pcm, False)
        ok0 = any(m == msg for m, _ in r0)
        off += ok0; off_wrong += sum(1 for m, _ in r0 if m != msg)
        if both:
            r1, att, osd = nat.decode(pcm, True)
            ok1 = any(m == msg for m, _ in r1)
            on += ok1; on_wrong += sum(1 for m, _ in r1 if m != msg)
            cq_tagged += sum(1 for _, k in r1 if k == 1); att_sum += att; osd_sum += osd
            on_only += (ok1 and not ok0); off_only += (ok0 and not ok1)
    return dict(snr=snr_db, n=n, off=off, on=on, off_wrong=off_wrong, on_wrong=on_wrong, cq_tagged=cq_tagged, on_only=on_only, off_only=off_only,
                attempts=att_sum, osd_entries=osd_sum)


def s50(scan):
    pts = [(s["snr"], s["off"] / s["n"]) for s in scan]
    for (a, pa), (b, pb) in zip(pts, pts[1:]):
        if pa < 0.5 <= pb:
            return int(round(a + (0.5 - pa) / (pb - pa) * (b - a)))
    raise RuntimeError(f"OFF never crosses 0.5 in the scan: {pts}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dll", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    nat = Native(a.dll)
    if a.selftest:                                   # plumbing only: 5 cycles at -12 dB, both arms; never the real seeds
        rng = np.random.Generator(np.random.PCG64(1)); print(run_step(nat, rng, -12, 5, True)); return
    rngA = np.random.Generator(np.random.PCG64(SEED_A))
    scan = [run_step(nat, rngA, s, N_SCAN, False) for s in SNR_SCAN]
    S50 = s50(scan)
    rngB = np.random.Generator(np.random.PCG64(SEED_B))
    grid = [run_step(nat, rngB, s, N_GRID, True) for s in range(S50 - GRID_BELOW, S50 + GRID_ABOVE + 1)]
    rows = []
    for g in grid:
        lo0, hi0 = wilson(g["off"], g["n"]); lo1, hi1 = wilson(g["on"], g["n"])
        g.update(off_rate=g["off"] / g["n"], on_rate=g["on"] / g["n"], off_wilson=(lo0, hi0), on_wilson=(lo1, hi1),
                 step_pass=(g["on"] - g["off"]) / g["n"] >= BAR_PP and lo1 > hi0)
        rows.append(g)
    res = dict(dll_sha256=nat.sha, shim=SHIM_VERSION, seeds=[SEED_A, SEED_B], decode_params=DECODE_PARAMS, scan=scan, S50=S50, grid=rows,
               VERDICT="PASS" if any(g["step_pass"] for g in rows) else "FAIL")
    open(a.out, "w").write(json.dumps(res, indent=1, default=str))
    print(json.dumps(dict(S50=S50, VERDICT=res["VERDICT"], steps=[(g["snr"], g["off"], g["on"], g["n"], g["step_pass"]) for g in rows]), default=str))


if __name__ == "__main__":
    main()
