/*
 * test_b2_fusion_normalization.c -- mandatory unit test for B2 (task 8.2,
 * design.md D9, specs/ft8-coherent-llr/spec.md's "Fusion selects by
 * normalised reliability, not by window length" scenario).
 *
 * PLACEMENT (Developer's choice, recorded per tasks.md 8.2's own
 * instruction): C-side, a standalone throwaway executable that #includes
 * coherent_llr.c directly to reach its `static` coh_bits_from_window /
 * coh_window_scale helpers -- neither is (or should be) exported from the
 * DLL, and this repo has no existing native C test runner/framework
 * (BUILD.md has no "tests" section; every other diagnostic export in this
 * project's history is smoke-tested from Python ctypes against the built
 * DLL instead -- see test_b4_ldpc_decode_llrs.py for B4's own choice).
 * A C-side test was chosen HERE specifically because B2's own scenario
 * ("two windows whose magnitudes carry equal discriminative information but
 * differ in absolute scale by a known factor") is about the internal
 * per-window magnitude array and the static scale/fusion arithmetic
 * directly -- exercising it through the full ft8_coherent_llr_at() pipeline
 * (PCM -> downconvert -> correlate) would only let two windows differ in
 * scale INDIRECTLY (via coherent gain over a longer window), which is
 * exactly the effect B2 is correcting for, not a clean, independently
 * constructed test of the normalisation arithmetic itself.
 *
 * NOT linked into libft8.dll and NOT part of rebuild_shim.bat -- compiled
 * and run standalone (see this file's own header for the exact command),
 * discarded after. This file's job is to prove the arithmetic once, on
 * record; it is not test infrastructure this repo is expected to maintain
 * a CI job for (no native CI test step exists for any other diagnostic
 * export's own unit-level checks either).
 *
 * Build (from the repo root, MSVC x64 Native Tools prompt; requires
 * rebuild_shim.bat to have already populated native\ft8_lib_build\obj\ --
 * this test's own main() only calls coh_bits_from_window/coh_window_scale,
 * but #including the whole of coherent_llr.c also compiles
 * ft8_coherent_llr_at() into this translation unit, which pulls in
 * design_lowpass_hann/downconvert_decimate (sync_refiner.obj),
 * monitor_init/monitor_free (monitor.obj, which itself needs
 * kiss_fftr.obj/kiss_fft.obj) and kFT8_Gray_map (constants.obj) at link
 * time even though this test never calls it):
 *   cl /I native\ft8_lib_vendor /I src\OpenWSFZ.Ft8\Native /std:c11 /W3 /c ^
 *      /Fo:test_b2_fusion_normalization.obj ^
 *      native\ft8_lib_vendor\refine\tests\test_b2_fusion_normalization.c
 *   link /OUT:test_b2_fusion_normalization.exe ^
 *      test_b2_fusion_normalization.obj ^
 *      native\ft8_lib_build\obj\constants.obj ^
 *      native\ft8_lib_build\obj\monitor.obj ^
 *      native\ft8_lib_build\obj\sync_refiner.obj ^
 *      native\ft8_lib_build\obj\kiss_fft.obj ^
 *      native\ft8_lib_build\obj\kiss_fftr.obj
 *   .\test_b2_fusion_normalization.exe
 *
 * Exit code 0 and "ALL PASS" on success; non-zero and a named FAIL line on
 * any assertion failure. Confirmed run 2026-08-21 (this session): ALL PASS
 * -- raw_llr_b == 3.7000 * raw_llr_a exactly on all 3 bits (pre-
 * normalisation disagreement, as required), norm_llr_a == norm_llr_b to
 * float32 rounding on all 3 bits (post-normalisation agreement).
 */

#include "../coherent_llr.c" /* pulls in coh_bits_from_window, coh_window_scale (both static) */

#include <stdio.h>

static int g_failures = 0;

#define CHECK(cond, msg)                                              \
    do {                                                               \
        if (!(cond)) {                                                 \
            printf("FAIL: %s (%s:%d)\n", (msg), __FILE__, __LINE__);   \
            g_failures++;                                              \
        }                                                               \
    } while (0)

int main(void)
{
    /* ── Construct an n_syms=1 window's 8 tone magnitudes (n_tones = 8^1). ──
     * Chosen so every bit's discriminative evidence is UNAMBIGUOUS (tone 5 is
     * the clear winner, well separated from the rest) -- the exact bit
     * pattern doesn't matter for this test, only that (a) it is
     * non-degenerate (nonzero spread) and (b) window B is window A scaled by
     * a known factor, so B2's normalisation should make their FUSED
     * per-bit LLRs agree while their RAW per-bit LLRs do not. */
    float mag_a[8] = { 1.0f, 2.0f, 1.5f, 3.0f, 2.5f, 9.0f, 4.0f, 3.5f };

    const float SCALE_FACTOR = 3.7f; /* "differ in absolute scale by a known factor" */
    float mag_b[8];
    for (int i = 0; i < 8; i++) mag_b[i] = mag_a[i] * SCALE_FACTOR;

    /* Sanity: same discriminative CONTENT (same argmax structure), different
     * absolute scale -- exactly the scenario spec.md names. */
    CHECK(mag_a[5] == 9.0f && mag_b[5] == 9.0f * SCALE_FACTOR, "fixture: tone 5 is the winner in both");

    float raw_llr_a[3], raw_llr_b[3];
    coh_bits_from_window(mag_a, 1, raw_llr_a);
    coh_bits_from_window(mag_b, 1, raw_llr_b);

    /* ── Pre-normalisation: the two windows' LLRs do NOT agree (B2's own
     * "prove the normalisation, not merely the window construction, is what
     * produces the agreement" requirement, spec.md). Since B is a pure
     * positive scaling of A, raw_llr_b == SCALE_FACTOR * raw_llr_a exactly
     * (max-log is linear under positive scaling) -- distinct from raw_llr_a
     * whenever raw_llr_a is nonzero and SCALE_FACTOR != 1, which holds here. */
    int any_disagree = 0;
    for (int i = 0; i < 3; i++)
    {
        if (fabsf(raw_llr_a[i] - raw_llr_b[i]) > 1e-4f) any_disagree = 1;
        printf("bit %d: raw_llr_a=%.4f raw_llr_b=%.4f (ratio %.4f, expect %.4f)\n",
               i, raw_llr_a[i], raw_llr_b[i],
               (raw_llr_a[i] != 0.0f) ? (raw_llr_b[i] / raw_llr_a[i]) : 0.0f, SCALE_FACTOR);
    }
    CHECK(any_disagree, "pre-normalisation LLRs must NOT agree (they differ by SCALE_FACTOR)");

    /* ── Post-normalisation (B2, design.md D9): each window divided by its
     * OWN coh_window_scale(mag, n_tones) -- the exact code coherent_llr.c's
     * main fusion loop now runs before the cross-n_syms comparison. */
    float scale_a = coh_window_scale(mag_a, 8);
    float scale_b = coh_window_scale(mag_b, 8);
    CHECK(scale_a > 0.0f && scale_b > 0.0f, "fixture: both windows are non-degenerate");
    /* coh_window_scale is a population stddev, itself linear under positive
     * scaling -- scale_b should equal SCALE_FACTOR * scale_a to float32
     * rounding. Asserted here as an independent cross-check on the helper
     * itself, not just the end-to-end agreement below. */
    CHECK(fabsf(scale_b - SCALE_FACTOR * scale_a) < 1e-3f * scale_b,
          "coh_window_scale must itself scale linearly with a positive magnitude scaling");

    float norm_llr_a[3], norm_llr_b[3];
    for (int i = 0; i < 3; i++)
    {
        norm_llr_a[i] = raw_llr_a[i] / scale_a;
        norm_llr_b[i] = raw_llr_b[i] / scale_b;
    }

    const float TOLERANCE = 1e-3f;
    int all_agree = 1;
    for (int i = 0; i < 3; i++)
    {
        float d = fabsf(norm_llr_a[i] - norm_llr_b[i]);
        printf("bit %d: norm_llr_a=%.5f norm_llr_b=%.5f |diff|=%.6f (tol %.6f)\n",
               i, norm_llr_a[i], norm_llr_b[i], d, TOLERANCE);
        if (d > TOLERANCE) all_agree = 0;
    }
    CHECK(all_agree, "post-normalisation LLRs must agree to the stated tolerance");

    /* ── Guard path (design.md D9): a degenerate (zero-spread) window's LLRs
     * are left UNSCALED, not divided by zero. */
    float mag_degenerate[8] = { 5.0f, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f };
    float scale_degenerate = coh_window_scale(mag_degenerate, 8);
    CHECK(scale_degenerate == 0.0f, "a zero-spread window's coh_window_scale must be exactly 0.0f (guard signal)");

    if (g_failures == 0)
    {
        printf("\nALL PASS (B2 mandatory unit test, task 8.2 / design.md D9)\n");
        return 0;
    }
    printf("\n%d FAILURE(S)\n", g_failures);
    return 1;
}
