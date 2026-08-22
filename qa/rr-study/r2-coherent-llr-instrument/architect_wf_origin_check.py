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

# Faithful re-implementation of monitor.c's block/subblock/window indexing.
SR, SYMP = 12000, 0.16
B = int(SR * SYMP)          # block_size = 1920
T, F = 2, 2                 # time_osr, freq_osr
SUB = B // T                # 960
NFFT = B * F                # 3840
win = np.sin(np.pi * np.arange(NFFT) / NFFT) ** 2   # hann_i

def waterfall(pcm):
    """Returns mag[block][sub][bin] exactly as monitor_process fills it."""
    last = np.zeros(NFFT)
    out = []
    nblocks = len(pcm) // B
    for b in range(nblocks):
        frame = pcm[b*B:(b+1)*B]
        fp = 0
        subs = []
        for s in range(T):
            last[:NFFT-SUB] = last[SUB:]
            last[NFFT-SUB:] = frame[fp:fp+SUB]; fp += SUB
            spec = np.fft.rfft(win * last)
            subs.append(np.abs(spec)**2)
        out.append(subs)
    return out

# Plant a pure tone burst occupying EXACTLY one symbol, starting at symbol index t0.
t0 = 40
f0 = 1500.0
n = B * 93
pcm = np.zeros(n)
sl = slice(t0*B, (t0+1)*B)
pcm[sl] = np.sin(2*np.pi*f0*np.arange(t0*B, (t0+1)*B)/SR)

wf = waterfall(pcm)
bin0 = int(round(f0 * SYMP * F))     # src_bin for freq_sub=0 lattice point
scores = []
for b in range(t0-3, t0+4):
    for s in range(T):
        scores.append((wf[b][s][bin0], b, s))
scores.sort(reverse=True)
print("tone burst occupies PCM symbol [%d, %d)" % (t0, t0+1))
print("top waterfall cells (block, sub) by energy at bin %d:" % bin0)
for v,b,s in scores[:5]:
    print("   block=%2d sub=%d  energy=%.4g   -> block-t0 = %+d" % (b,s,v,b-t0))
best = scores[0]
print()
print("PEAK CELL block index      : %d" % best[1])
print("TRUE PCM symbol start index: %d" % t0)
print("=> waterfall block index EXCEEDS true PCM symbol index by %+d symbol(s)" % (best[1]-t0))
