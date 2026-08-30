"""WIN-A ROW 0e -- shipped as code, not prose (HK-021(q), HK-021(r)).

Spec:      qa/rr-study/2026-08-29-1400-architect-to-qa-spec-win-a-analysis-window-sidelobe-ladder.md  (Sec.4, ROW 0e)
Amendment: qa/rr-study/2026-08-29-1859-architect-to-qa-amendment-a1-win-a-rearm-spec.md

ROW 0e asks the HK-021(q) question BEFORE the decode arm runs: does the treatment
actually move the quantity it is theorised to move? If Hamming does not reduce the
strong neighbour's leakage into the weak signal's bins at the capture family's own
geometry, then the mechanism is absent and no decode result can inform it.

Bar (spec Sec.4): the Hamming leakage figure must be at least 6 dB below Hann's.

This is pure window arithmetic -- no decoder, no radio, no audio device, no harness.
It depends only on numpy.

Lattice, from architecture-ft8-lib.md and the spec:
    fs   = 12000 Hz   (ft8_lib monitor rate)
    nfft = 3840       (freq_osr = 2)
    bin  = 12000/3840 = 3.125 Hz

Capture-family geometry, from spec Sec.1.2 (re-derived there from 22b749c):
    part   dF      dSNR    weak recovery (OpenWSFZ)
    P11    14 Hz    -3 dB   5/5   <- the one that works
    P12     9 Hz    -6 dB   0/5
    P13     7 Hz   -10 dB   0/5
    P14    11 Hz   -13 dB   0/5

ASCII only -- Windows console is cp1252 (HK-009).
"""

import numpy as np

FS_HZ = 12000.0
NFFT = 3840
BIN_HZ = FS_HZ / NFFT          # 3.125

# (label, delta_f_hz, delta_snr_db)
CAPTURE_FAMILY = [
    ("P11", 14.0, -3.0),
    ("P12", 9.0, -6.0),
    ("P13", 7.0, -10.0),
    ("P14", 11.0, -13.0),
]

ROW_0E_PART = "P13"            # the part the spec names for ROW 0e
ROW_0E_BAR_DB = 6.0            # Hamming must be >= this many dB below Hann


def hann(n):
    """Matches ft8_lib common/monitor.c hann_i()."""
    i = np.arange(n)
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * i / n)


def hamming(n):
    """Matches ft8_lib common/monitor.c hamming_i(): alpha = 25/46, as confirmed
    against the committed treatment_window.txt dump (sum = 2*alpha = 1.086957)."""
    a0 = 25.0 / 46.0
    i = np.arange(n)
    return a0 - (1.0 - a0) * np.cos(2.0 * np.pi * i / n)


def leakage_db(window, delta_f_hz, nfft=NFFT, fs=FS_HZ):
    """Level, in dB relative to the strong tone's own peak response, that the strong
    tone leaks into the analysis bin nearest the weak tone, delta_f_hz away.

    Worst-case over the strong tone's sub-bin position: a real signal sits at an
    arbitrary offset within its bin, and the leakage depends on that offset. We
    report the WORST (highest leakage) case, because the arm must survive it.
    """
    n = np.arange(nfft)
    worst = -np.inf
    # sweep the strong tone's sub-bin offset across one full bin
    for frac in np.linspace(-0.5, 0.5, 101):
        f_strong_bins = frac
        f_weak_bins = frac + delta_f_hz / (fs / nfft)
        # response of the windowed DFT at an arbitrary (fractional) bin offset
        def resp(bin_offset):
            phasor = np.exp(-2j * np.pi * bin_offset * n / nfft)
            return np.abs(np.sum(window * phasor))
        peak = resp(f_strong_bins)                       # strong tone in its own bin
        nearest_weak_bin = np.round(f_weak_bins)         # the bin the weak tone lands in
        spill = resp(f_strong_bins - nearest_weak_bin)   # strong tone's skirt at that bin
        if spill <= 0.0:
            continue                                     # exact null; cannot be the worst case
        worst = max(worst, 20.0 * np.log10(spill / peak))
    return worst


def run():
    w_hann = hann(NFFT)
    w_hamm = hamming(NFFT)

    # sanity: reproduce the committed window dumps before trusting anything else
    fft_norm = 2.0 / NFFT
    print("== window identity check vs committed dumps ==")
    print("  hann  sum*fft_norm = %.9f   (baseline_window.txt:  1.000000026)" % (w_hann.sum() * fft_norm))
    print("  hamm  sum*fft_norm = %.9f   (treatment_window.txt: 1.086956532)" % (w_hamm.sum() * fft_norm))
    print("  hamm  w[0]*fft_norm = %.9f  (treatment_window.txt: 0.000045290)" % (w_hamm[0] * fft_norm))

    print()
    print("== leakage from the strong neighbour into the weak signal's bin ==")
    print("   (worst case over the strong tone's sub-bin position)")
    print()
    print("  %-5s %7s %8s %10s %10s %9s %s" % (
        "part", "dF(Hz)", "dF(bins)", "Hann(dB)", "Hamming(dB)", "gain(dB)", "vs 6 dB bar"))
    results = {}
    for label, df, _dsnr in CAPTURE_FAMILY:
        lh = leakage_db(w_hann, df)
        lm = leakage_db(w_hamm, df)
        gain = lh - lm          # positive == Hamming leaks LESS
        results[label] = (df, lh, lm, gain)
        verdict = "PASS" if gain >= ROW_0E_BAR_DB else "FAIL"
        print("  %-5s %7.1f %8.2f %10.2f %10.2f %9.2f  %s" % (
            label, df, df / BIN_HZ, lh, lm, gain, verdict))

    df, lh, lm, gain = results[ROW_0E_PART]
    print()
    print("== ROW 0e verdict (spec names %s) ==" % ROW_0E_PART)
    print("  Hann    leakage: %+.2f dB" % lh)
    print("  Hamming leakage: %+.2f dB" % lm)
    print("  improvement    : %+.2f dB   (bar: >= %.1f dB)" % (gain, ROW_0E_BAR_DB))
    ok = gain >= ROW_0E_BAR_DB
    print()
    print("  ROW 0e: %s" % ("PASS -- the mechanism is present, the arm may run"
                            if ok else
                            "FAIL -- VOID. The window change does not reduce leakage at this\n"
                            "          geometry, so the decode arm cannot inform the hypothesis."))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
