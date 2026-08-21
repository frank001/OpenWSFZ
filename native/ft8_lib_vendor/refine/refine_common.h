/*
 * refine_common.h -- shared downconversion primitives for the refine/
 * diagnostic family (sync_refiner.c, coherent_llr.c).
 *
 * r2-coherent-llr-instrument, task 1.1/1.2: ft8_coherent_llr_at() (in the new
 * coherent_llr.c) reuses sync_refiner.c's existing downconvert_decimate() /
 * design_lowpass_hann() verbatim -- not reimplemented, per this change's own
 * HK-018 discipline. Those two functions were previously `static` inside
 * sync_refiner.c (file-local linkage, single translation unit); this header
 * gives them external linkage via matching non-`static` prototypes so a
 * second translation unit in the same directory can call the SAME compiled
 * functions. sync_refiner.c's own definitions had `static` removed to match
 * (a mechanical, behaviour-preserving linkage change -- see that file's own
 * header comment for the byte-for-byte-unchanged discussion); no algorithm,
 * constant, or logic in either function changed.
 *
 * OpenWSFZ-original, diagnostic-only, no production call site -- same
 * provenance footing as sync_refiner.c itself (design.md D7): additive to
 * the vendor tree, not a modification of any byte-identical-to-upstream file.
 */

#ifndef REFINE_COMMON_H
#define REFINE_COMMON_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * design_lowpass_hann -- Hann-windowed-sinc lowpass FIR, unit DC gain.
 * Standard filter design, derived independently (no external source
 * consulted). See sync_refiner.c for the full implementation.
 */
void design_lowpass_hann(float* taps, int ntaps, float cutoff_hz, float fs_hz);

/*
 * downconvert_decimate -- mix `pcm` (n samples @ fs_in Hz) down by
 * `carrier_hz` (baseband = pcm * exp(-j*2*pi*carrier_hz*t)), apply the FIR
 * lowpass `taps`, and decimate by `decim`, all fused into one pass per
 * output sample. Writes floor(n/decim) complex samples to out_re/out_im.
 * Zero-padded at the buffer edges. Returns the number of output samples
 * written. See sync_refiner.c for the full implementation.
 */
int downconvert_decimate(
    const float* pcm, int n, float fs_in,
    float carrier_hz,
    const float* taps, int ntaps,
    int decim,
    float* out_re, float* out_im);

#ifdef __cplusplus
}
#endif

#endif /* REFINE_COMMON_H */
