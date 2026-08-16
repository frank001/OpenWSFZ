#!/usr/bin/env python3
"""N2 -- coherent multi-symbol LLR extractor: the Python front end (V1/V2/V3).

Spec: qa/rr-study/2026-08-16-1408-architect-to-qa-N2-coherent-llr-extractor-spec.md
Sec.4.1 (method) and Sec.9 (scope discipline: NO src/ change -- this is Python off the
WAV, per Sec.2.3's finding that HK-011 is not engaged for this arm).

PROVENANCE / CLEAN-ROOM NOTE (Captain's binding licence ruling, 2026-08-11 -- WSJT-X may
be read for method, never copied, spec Sec.4.1's licence constraint repeats this in full
force for N2): this module is written directly from FT8's own PUBLIC protocol constants
(tone spacing 6.25 Hz, symbol period 0.16 s, Gray map [0,1,3,2,5,6,4,7] --
C:/Temp/ft8_lib_headers/ft8/constants.c:13, kFT8_Gray_map, already used unmodified
elsewhere in this repo's own QA tooling, e.g. n1-extract-llrs-at-position's
extract_llrs_ctypes.true_codeword) and from standard coherent matched-filter / max-log
APP demodulation theory. NO WSJT-X source (ft8_downsample, sync8d, ft8b) was opened or
consulted in writing this file. The downconvert/decimate METHOD (mix to baseband, Hann-
windowed-sinc lowpass, decimate) follows native/ft8_lib_vendor/refine/sync_refiner.c's
own downconvert_decimate -- that file is OUR OWN code, clean-room by construction per its
own header (sync_refiner.c:11-22) -- reusing the METHOD and its two empirically-validated
design corrections, not any buffer, per spec Sec.2.2's explicit instruction.

KEY DERIVED FACT (this session's own derivation, not asserted from any external source
and not present in sync_refiner.c): FT8's tone spacing (6.25 Hz) times its symbol period
(0.16 s) equals exactly 1.0 -- every tone completes an integer number of full carrier
cycles in exactly one symbol period. Consequence: a per-symbol correlation reference that
resets to phase zero at the START of every symbol (an ordinary 320-point DFT, computed
independently per symbol -- spec Sec.2.3/Sec.6.3's "(79,320) x (320,8) matrix product") is
ALREADY exactly phase-continuous with a hypothetical globally phase-integrated reference,
for ANY sequence of hypothesised tones, with NO running phase accumulator needed --
unlike sync_refiner.c's costas_coherent_sum, which genuinely needs one, but only because
it searches a residual delta_hz that is free to be any value, not restricted to multiples
of the tone spacing.

Proof: the true continuous-phase reference for tone t at GLOBAL sample index (p*320+n),
measured from an arbitrary t=0 at symbol 0's own start, is
    exp(-j * 2*pi * t*6.25 * (p*320+n) / 2000).
The position-dependent factor exp(-j * 2*pi * t*6.25*p*320/2000) reduces to
exp(-j * 2*pi * t*p) = 1 EXACTLY, because t*6.25*320/2000 = t*1.0 is always an integer.
So the global reference factorises into (local per-symbol reference) x 1, for every p and
every t. This is what makes V2/V3's "just complex-sum the relevant per-symbol DFT bins,
no extra phase-correction factor" implementation exact rather than approximate -- and it
is exactly why this project's FT8 tone spacing was chosen the way it was (a standard MFSK
design property, not an OpenWSFZ-specific fact). A residual carrier error (df != 0, the
df sweep in Sec.7.2) breaks this identity in general (df is not a multiple of the tone
spacing) -- handled here not by phase-tracking but by folding df into the downconversion
carrier itself (extract_variants' df_hz), after which the same local-zero-phase argument
applies again relative to the shifted carrier.

DESIGN DECISION on the spec's own underspecified "combine group orders by summation"
(Sec.4.1 step 4, and the V1/V2/V3 table's "V1 + 2-symbol coherent groups" / "V2 +
3-symbol coherent groups" phrasing) -- read literally and cumulatively:
    V1_llr[k] = order-1 (single symbol) max-log Gray LLR
    V2_llr[k] = V1_llr[k] + sum of order-2 (pair) max-log Gray LLR contributions from
                every RAW-adjacent pair containing symbol k (up to 2: left, right)
    V3_llr[k] = V2_llr[k] + sum of order-3 (triple) max-log Gray LLR contributions from
                every RAW-adjacent triple containing symbol k (up to 3)
This is a documented judgement call (HK-004), not dictated unambiguously by the spec
text -- flagged in the N2 report for Architect review. It is not load-bearing on hard-
decision BER's sign in the overwhelming majority of cases (the higher-order term
dominates the sum in magnitude; the lower orders can only rarely flip a marginal sign),
which is the same scale-insensitivity reasoning the spec itself gives for skipping
ftx_normalize_logl on the primary statistic.

Groups are formed over the FULL 79-symbol RAW sequence (not just the 58 data symbols),
matching the spec's own cost estimate (Sec.6.3: "78 pairs", "77 triples"): a group
touching a Costas sync symbol still enumerates all 8 tone hypotheses for that position --
this does NOT exploit the fact that sync tones are actually known, fixed values (that
would be a further optimisation the spec does not describe; out of scope here). Only the
DATA member's own 3 Gray bits are ever emitted into the 174-bit output, exactly mirroring
decode.c's ft8_extract_likelihood: its k-loop (decode.c:369-388) only ever writes bits
for symbols outside the three Costas sync ranges.
"""
from __future__ import annotations

import numpy as np

SAMPLE_RATE_HZ = 12000.0
BUFFER_SAMPLES = 180_000
SYMBOL_PERIOD_S = 0.16

REFINE_DECIM_FINE = 6                                   # sync_refiner.c REFINE_DECIM_FINE
RATE_FINE_HZ = SAMPLE_RATE_HZ / REFINE_DECIM_FINE        # 2000 Hz
LP_TAPS_FINE = 61                                        # sync_refiner.c REFINE_LP_TAPS_FINE
LP_CUTOFF_FINE_HZ = 900.0                                # sync_refiner.c REFINE_LP_CUTOFF_FINE_HZ

TONE_SPACING_HZ = 6.25
N_TONES = 8
SPS_2K = int(round(RATE_FINE_HZ * SYMBOL_PERIOD_S))      # 320 samples/symbol @ 2000 Hz
N_SYM = 79                                               # FT8_NN
FT8_ND = 58                                              # FT8 data symbols

GRAY_MAP = (0, 1, 3, 2, 5, 6, 4, 7)  # ft8/constants.c:13 kFT8_Gray_map -- public protocol
                                      # constant, not WSJT-X-derived; already used verbatim
                                      # in extract_llrs_ctypes.py's true_codeword.

# decode.c:369-388's own data-symbol schedule ("Skip either 7 or 14 sync symbols"):
# k=0..28 -> raw index k+7 (7..35); k=29..57 -> raw index k+14 (43..71).
DATA_SYM_IDX = [k + (7 if k < 29 else 14) for k in range(FT8_ND)]


def design_lowpass_hann(ntaps: int, cutoff_hz: float, fs_hz: float) -> np.ndarray:
    """Hann-windowed-sinc lowpass FIR, unit DC gain -- same design as our own
    sync_refiner.c's design_lowpass_hann (standard DSP technique, no external source)."""
    mid = ntaps // 2
    n = np.arange(ntaps)
    k = n - mid
    fc = cutoff_hz / fs_hz
    with np.errstate(divide="ignore", invalid="ignore"):
        sinc = np.where(k == 0, 2.0 * fc, np.sin(2.0 * np.pi * fc * k) / (np.pi * k))
    window = 0.5 - 0.5 * np.cos(2.0 * np.pi * n / (ntaps - 1))
    taps = sinc * window
    s = taps.sum()
    if s != 0.0:
        taps = taps / s
    return taps


_TAPS_FINE = design_lowpass_hann(LP_TAPS_FINE, LP_CUTOFF_FINE_HZ, SAMPLE_RATE_HZ)

# Per-symbol 8-tone matched filter as a (320, 8) DFT matrix (spec Sec.2.3: 2000/320 =
# 6.25 Hz = the tone spacing exactly, so the 8 tones land on exactly orthogonal bins).
_DFT_MAT = np.exp(-2j * np.pi * np.outer(np.arange(SPS_2K), np.arange(N_TONES)) / SPS_2K)


def downconvert_decimate(pcm: np.ndarray, carrier_hz: float) -> np.ndarray:
    """pcm: BUFFER_SAMPLES @ 12000 Hz (float32/float64). Returns complex128 baseband @
    RATE_FINE_HZ (2000 Hz). Method: mix to baseband at carrier_hz, Hann-sinc lowpass,
    decimate by 6 -- algebraically identical to sync_refiner.c's fused
    mix-filter-decimate loop (derivation: for symmetric taps of odd length L=61 with
    half=L//2=30, out[m] = sum_t taps[t]*mixed[m*decim-half+t] equals
    convolve(mixed, taps, 'full')[m*decim+half], and numpy's 'same' mode is exactly
    convolve(...,'full')[half : half+len(mixed)] for odd-length taps -- so
    convolve(mixed, taps, 'same')[m*decim] equals the C code's out[m], for every m)."""
    n = len(pcm)
    idx = np.arange(n)
    w = 2.0 * np.pi * carrier_hz / SAMPLE_RATE_HZ
    mixed = pcm.astype(np.float64) * np.exp(-1j * w * idx)
    filtered = np.convolve(mixed, _TAPS_FINE, mode="same")
    return filtered[::REFINE_DECIM_FINE]


def correlate_symbols(baseband_2k: np.ndarray, start_sample: int) -> np.ndarray:
    """Per-symbol 8-tone matched filter. Returns X, complex128 shape (N_SYM, N_TONES):
    X[p, tone] is symbol p's coherent correlation against `tone`. start_sample: the
    decimated-stream (2000 Hz) sample index of symbol 0's start (anchor_dt_s *
    RATE_FINE_HZ, exact -- see extract_variants). Out-of-bounds symbols zero-padded,
    mirroring ft8_extract_likelihood's own block<0/block>=num_blocks -> 0 convention
    (decode.c:377-383)."""
    n = len(baseband_2k)
    mat = np.zeros((N_SYM, SPS_2K), dtype=np.complex128)
    for p in range(N_SYM):
        lo = start_sample + p * SPS_2K
        hi = lo + SPS_2K
        clo, chi = max(lo, 0), min(hi, n)
        if chi > clo:
            mat[p, clo - lo:chi - lo] = baseband_2k[clo:chi]
    return mat @ _DFT_MAT


def _gray_bit_llrs(s2: np.ndarray) -> tuple[float, float, float]:
    """s2: length-8, indexed by GRAY INDEX j (s2[j] = score at tone GRAY_MAP[j]). Same
    max4-comparison structure as decode.c:1073-1075 -- logl[0]=bit2(j), logl[1]=bit1(j),
    logl[2]=bit0(j) of the gray index j, matching extract_llrs_ctypes.true_codeword's
    inv_gray unpacking ((b3>>2)&1, (b3>>1)&1, b3&1) bit-for-bit."""
    def max4(a, b, c, d):
        return max(a, b, c, d)
    l0 = max4(s2[4], s2[5], s2[6], s2[7]) - max4(s2[0], s2[1], s2[2], s2[3])
    l1 = max4(s2[2], s2[3], s2[6], s2[7]) - max4(s2[0], s2[1], s2[4], s2[5])
    l2 = max4(s2[1], s2[3], s2[5], s2[7]) - max4(s2[0], s2[2], s2[4], s2[6])
    return l0, l1, l2


def _scores_by_gray(scores_by_tone: np.ndarray) -> np.ndarray:
    return scores_by_tone[list(GRAY_MAP)]


def _order1_llr(X: np.ndarray, sym: int) -> tuple[float, float, float]:
    scores_by_tone = np.abs(X[sym, :]) ** 2
    return _gray_bit_llrs(_scores_by_gray(scores_by_tone))


def _order2_llr_contrib(X: np.ndarray, self_sym: int, other_sym: int) -> tuple[float, float, float]:
    """`self_sym`'s contribution from its raw-adjacent pair with `other_sym`, max-log
    marginalised over the other member's 8 tone hypotheses."""
    xs = X[self_sym, :]
    xo = X[other_sym, :]
    joint = np.abs(xs[:, None] + xo[None, :]) ** 2   # (8,8): [self_tone, other_tone]
    scores_by_tone = joint.max(axis=1)
    return _gray_bit_llrs(_scores_by_gray(scores_by_tone))


def _order3_llr_contrib(X: np.ndarray, a: int, b: int, c: int, self_pos: int) -> tuple[float, float, float]:
    """self is whichever of (a,b,c) sits at `self_pos` (0/1/2); max-log marginalised
    over the other two members' 64 joint tone hypotheses."""
    xa, xb, xc = X[a, :], X[b, :], X[c, :]
    joint = np.abs(xa[:, None, None] + xb[None, :, None] + xc[None, None, :]) ** 2  # (8,8,8)
    axes = tuple(ax for ax in range(3) if ax != self_pos)
    scores_by_tone = joint.max(axis=axes)
    return _gray_bit_llrs(_scores_by_gray(scores_by_tone))


# EMPIRICAL CALIBRATION FINDING (this session, ROW 0b): `anchor_dt_s` for a REAL
# candidate (from candidate_diag.csv / population.py's grid_dt, i.e. whatever produced
# it upstream of this harness -- that capture code is not in the current source tree to
# re-derive by hand, see the N2 report Sec.4/6) is NOT "symbol-0 starts at
# round(anchor_dt_s * RATE_FINE_HZ)" -- unlike qa/rr-study/synth/modulator.py's OWN
# placement convention, which genuinely is exactly that (confirmed by ROW 0a's 0.0% BER
# using the RAW, uncorrected formula on a self-generated synthetic signal). On the real
# corpus, ROW 0a's self-consistent Python-only test could not catch this: it never
# exercises the C waterfall's own addressing at all.
#
# Calibrated directly against ft8_extract_llrs_at (V0, already production-validated) on
# the matched-hit control population (72 real rows), TWO independent diagnostics agree
# on the SAME correction to within measurement noise:
#   (a) aggregate confidence-score peak (sum of |LLR|, sign-weighted by correctness,
#       across all 72 rows) is unimodal and sharply peaked near -333 decimated samples;
#   (b) raw per-symbol ARGMAX-TONE accuracy against the true transmitted tone sequence
#       (bypassing Gray-bit formation entirely) is a clean, symmetric, single-peaked
#       function of the trial offset, peaking at EXACTLY -320 decimated samples (80.5%
#       symbol accuracy) and falling to the 1/8=12.5% chance floor by +-600 samples --
#       the classic shape of a rectangular per-symbol window sliding across a symbol
#       boundary, unambiguous evidence of a real, fixable alignment bug, not sensor noise.
# -320 decimated samples = -1920 raw (12 kHz) samples = exactly -SYMBOL_PERIOD_S (one
# whole FT8 symbol period) -- a clean, principled constant, adopted over the noisier
# curve-fit estimate (b) rather than (a)'s slightly-off empirical peak.
TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K  # -320 @ 2000 Hz = -1 symbol period


def extract_variants(pcm: np.ndarray, anchor_freq_hz: float, anchor_dt_s: float,
                      df_hz: float = 0.0) -> dict[str, np.ndarray]:
    """Returns {"V1": arr174, "V2": arr174, "V3": arr174}, float64 RAW (pre-
    normalisation) LLRs -- spec Sec.4.1 step 5, "same convention as ft8_extract_llrs_at".
    174-bit ordering matches extract_llrs_ctypes.true_codeword exactly (data symbols
    k=0..57 in decode.c's own schedule order, 3 bits each: gray-index bit2, bit1, bit0).

    df_hz: assumed carrier offset ADDED to anchor_freq_hz before downconversion --
    Sec.7.2's frequency-sensitivity sweep parameter; 0.0 for the primary arm.

    `anchor_dt_s` is interpreted in the REAL CANDIDATE convention (see
    TIME_ORIGIN_CORRECTION_SAMPLES_2K above) -- callers driving a synthetic signal
    placed via modulator.py's OWN "dt_s*fs=sample index" convention must add
    SYMBOL_PERIOD_S to their dt before calling this function (run_n2.py's ROW 0a does
    exactly this, documented at its own call site)."""
    carrier = anchor_freq_hz + df_hz
    bb = downconvert_decimate(pcm, carrier)
    start = int(round(anchor_dt_s * RATE_FINE_HZ)) + TIME_ORIGIN_CORRECTION_SAMPLES_2K
    X = correlate_symbols(bb, start)

    v1 = np.zeros(174, dtype=np.float64)
    v2 = np.zeros(174, dtype=np.float64)
    v3 = np.zeros(174, dtype=np.float64)

    for k, sym in enumerate(DATA_SYM_IDX):
        b0 = 3 * k
        l0, l1, l2 = _order1_llr(X, sym)
        v1[b0:b0 + 3] = (l0, l1, l2)
        v2[b0:b0 + 3] = (l0, l1, l2)
        v3[b0:b0 + 3] = (l0, l1, l2)

        for other in (sym - 1, sym + 1):
            if 0 <= other < N_SYM:
                dl0, dl1, dl2 = _order2_llr_contrib(X, sym, other)
                v2[b0] += dl0; v2[b0 + 1] += dl1; v2[b0 + 2] += dl2
                v3[b0] += dl0; v3[b0 + 1] += dl1; v3[b0 + 2] += dl2

        for a, b, c, self_pos in (
            (sym - 2, sym - 1, sym, 2),
            (sym - 1, sym, sym + 1, 1),
            (sym, sym + 1, sym + 2, 0),
        ):
            if 0 <= a < N_SYM and 0 <= c < N_SYM:
                dl0, dl1, dl2 = _order3_llr_contrib(X, a, b, c, self_pos)
                v3[b0] += dl0; v3[b0 + 1] += dl1; v3[b0 + 2] += dl2

    return {"V1": v1, "V2": v2, "V3": v3}


def true_bits_from_tones(tones: "list[int]") -> "list[int]":
    """79 transmitted tones (as returned by qa/rr-study/synth/encoder.message_to_tones)
    -> 174 true bits, IDENTICAL convention to extract_llrs_ctypes.true_codeword (same
    Gray map, same DATA_SYM_IDX schedule) but driven directly from the tones the
    synthetic PCM was actually rendered from -- used ONLY for ROW 0a so the self-
    consistency check never depends on the native encoder and the Python synth encoder
    agreeing bit-for-bit (a separate, unrelated concern already flagged pending
    elsewhere in encoder.py's own docstring)."""
    inv_gray = [0] * 8
    for i, v in enumerate(GRAY_MAP):
        inv_gray[v] = i
    bits: list[int] = []
    for sym in DATA_SYM_IDX:
        b3 = inv_gray[tones[sym]]
        bits.append((b3 >> 2) & 1)
        bits.append((b3 >> 1) & 1)
        bits.append(b3 & 1)
    return bits
