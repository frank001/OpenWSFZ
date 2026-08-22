"""
ARCHITECT PROVENANCE ARTEFACT -- not a QA harness, not a gate, not a measurement
of the shipped binary.

Re-implements monitor.c's block/subblock/Hann-window indexing in numpy to verify
the derivation in
  qa/rr-study/2026-08-21-1412-architect-to-qa-origin-convention-finding-and-spec-b-orig-a.md
namely that a waterfall block index runs exactly (freq_osr/2 + 0.5 - 1/time_osr)
symbols AHEAD of raw-PCM symbol time -- +1.000 symbol at production's osr=2/2.

This tests a RE-IMPLEMENTATION. B-orig-A (same doc, Sec.6) is what tests the real
binary. Do not cite this file as evidence about the shipped waterfall.
"""

import numpy as np
SR, SYMP, f0 = 12000, 0.16, 1500.0

def peak_offset(T, F, t0_frac=0.0):
    B = int(SR*SYMP); SUB = B//T; NFFT = B*F
    win = np.sin(np.pi*np.arange(NFFT)/NFFT)**2
    n = B*93
    pcm = np.zeros(n)
    start = int(round((40 + t0_frac)*B))
    idx = np.arange(start, start+B)
    pcm[idx] = np.sin(2*np.pi*f0*idx/SR)
    last = np.zeros(NFFT); best = (-1, None)
    bin0 = int(round(f0*SYMP*F))
    for b in range(93):
        frame = pcm[b*B:(b+1)*B]; fp = 0
        for s in range(T):
            last[:NFFT-SUB] = last[SUB:]; last[NFFT-SUB:] = frame[fp:fp+SUB]; fp += SUB
            e = abs(np.fft.rfft(win*last)[bin0])**2
            # cell's implied time origin in symbols, as the shim converts it:
            origin = b + s/T
            if e > best[0]: best = (e, origin)
    return best[1] - (40 + t0_frac)

print("predicted displacement = F/2 + 0.5 - 1/T   (symbols)")
print()
print(" T  F | predicted | measured")
for T in (1,2,4):
    for F in (1,2):
        pred = F/2 + 0.5 - 1/T
        meas = peak_offset(T,F)
        print(" %d  %d |   %+.3f   |  %+.3f" % (T,F,pred,meas))
print()
print("independence from sub-symbol placement of the true signal (T=2,F=2):")
for frac in (0.0, 0.17, 0.33, 0.5, 0.71, 0.9):
    print("   true dt offset %+.2f symbol -> displacement %+.3f" % (frac, peak_offset(2,2,frac)))
