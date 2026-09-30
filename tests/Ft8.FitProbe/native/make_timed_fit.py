"""
make_timed_fit.py -- TEST-ONLY. Produces a timing-instrumented COPY of native/ft8_lib_vendor/subfeas/subfeas_fit.c for
the Stage B step-1 profile (sub-feas-speed-redesign tasks.md 15.1).

The product file is never edited. The copy differs ONLY by QueryPerformanceCounter reads around the named phases of
one fit, recorded into THREAD-LOCAL accumulators (so concurrent fits, each on its own worker thread, never mix), and
two extra exports (ft8_subfeas_pt_get, ft8_subfeas_pt_frequency) that exist only in the test DLL. Every insertion is
anchored on an exact, unique piece of the shipped text; the script FAILS if an anchor is missing or ambiguous.

The copy also replaces the one relative include (#include "../fft/kiss_fft.h") so it compiles from a scratch directory;
the build adds the fft\\ include path.

Windows-only test scaffolding. Usage: python make_timed_fit.py <subfeas_fit.c> <out subfeas_fit_timed.c>
"""
import sys

src_path, out_path = sys.argv[1], sys.argv[2]
s = open(src_path, encoding='utf-8', newline='').read().replace('\r\n', '\n')

def once(old, new):
    global s
    n = s.count(old)
    assert n == 1, f'anchor found {n} times (need exactly 1): {old[:80]!r}'
    s = s.replace(old, new, 1)

once('#include "../fft/kiss_fft.h"', '#include "kiss_fft.h"')

TIMER = r'''
/* ===================== TEST-ONLY timing instrumentation (make_timed_fit.py) ================================== */
enum { PT_LEASE, PT_SMOOTH, PT_STEP1, PT_STEP2, PT_FINAL, PT_STEP3, PT_ENVELOPE, PT_WRITE, PT_FIT_TOTAL, PT_COUNT };
static __declspec(thread) long long pt_f[PT_COUNT];         /* per worker thread: the last fit's phase ticks */
static long long pt_now(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart; }
/* ================================================================================================================= */

typedef struct { float r, i; } cf32;'''
once('\ntypedef struct { float r, i; } cf32;', TIMER)

# ---- fine_fit_with_drift ----------------------------------------------------------------------------------------
once('''    /* A1: the tone-dependent smoothing, once for all ~243 templates below. */
    compute_smoothed_track(ws, tones);

    /* ---- Step 1: (Δt, Δf) at ḟ=0 ---- */
''', '''    /* A1: the tone-dependent smoothing, once for all ~243 templates below. */
    long long pt_t = pt_now();
    compute_smoothed_track(ws, tones);
    pt_f[PT_SMOOTH] = pt_now() - pt_t;

    /* ---- Step 1: (Δt, Δf) at ḟ=0 ---- */
    pt_t = pt_now();
''')
once('''    if (!have_step1) return 0;

    /* ---- Step 2:''', '''    pt_f[PT_STEP1] = pt_now() - pt_t;
    if (!have_step1) return 0;

    /* ---- Step 2:''')
once('''    {
        int fixed_start = base_start + step1_best_dt_samples;''', '''    pt_t = pt_now();
    {
        int fixed_start = base_start + step1_best_dt_samples;''')
once('''        /* Final template at (ḟ*, Δf*) -- used for step 3's direct-correlation
         * scoring AND returned as the fit's template for envelope/subtract. */
        r_fit_drift(ws, best_fdot, ws->r_unit);
        apply_freq_shift(ws->r_unit, N_TX, freq_hz, ws->r_base);
        apply_freq_shift(ws->r_base, N_TX, best_df2, out_r_base_final);
    }
''', '''        pt_f[PT_STEP2] = pt_now() - pt_t;
        pt_t = pt_now();
        /* Final template at (ḟ*, Δf*) -- used for step 3's direct-correlation
         * scoring AND returned as the fit's template for envelope/subtract. */
        r_fit_drift(ws, best_fdot, ws->r_unit);
        apply_freq_shift(ws->r_unit, N_TX, freq_hz, ws->r_base);
        apply_freq_shift(ws->r_base, N_TX, best_df2, out_r_base_final);
        pt_f[PT_FINAL] = pt_now() - pt_t;
    }
    pt_t = pt_now();
''')
once('''        *out_start_sample = base_start + best_dt_samples;
        *out_dt_s = (double)best_dt_samples / FS;
    }

    return 1;''', '''        *out_start_sample = base_start + best_dt_samples;
        *out_dt_s = (double)best_dt_samples / FS;
    }
    pt_f[PT_STEP3] = pt_now() - pt_t;

    return 1;''')

# ---- fit_signal_body: envelope and the s_hat write --------------------------------------------------------------
once('''    if (lp_envelope(ws, x_a_re + start_sample, x_a_im + start_sample, ws->r_base_final, ws->envelope,
                    cancel_flag) == -4)
        return -4;

    for (i = 0; i < N_TX; i++) {
        float cr = ws->envelope[i].r, ci = ws->envelope[i].i;
        float rr = ws->r_base_final[i].r, ri = ws->r_base_final[i].i;
        /* s_hat = Re{c(t) * template(t)} */
        out_shat[start_sample + i] = cr * rr - ci * ri;
    }
    return 0;''', '''    long long pt_e = pt_now();
    if (lp_envelope(ws, x_a_re + start_sample, x_a_im + start_sample, ws->r_base_final, ws->envelope,
                    cancel_flag) == -4)
        return -4;
    pt_f[PT_ENVELOPE] = pt_now() - pt_e;

    pt_e = pt_now();
    for (i = 0; i < N_TX; i++) {
        float cr = ws->envelope[i].r, ci = ws->envelope[i].i;
        float rr = ws->r_base_final[i].r, ri = ws->r_base_final[i].i;
        /* s_hat = Re{c(t) * template(t)} */
        out_shat[start_sample + i] = cr * rr - ci * ri;
    }
    pt_f[PT_WRITE] = pt_now() - pt_e;
    return 0;''')

# ---- the public entry: lease and whole-fit ticks ---------------------------------------------------------------
once('''    ws = pool_lease();
    if (!ws) {''', '''    { int k; for (k = 0; k < PT_COUNT; k++) pt_f[k] = 0; }
    long long pt_l = pt_now();
    ws = pool_lease();
    pt_f[PT_LEASE] = pt_now() - pt_l;
    if (!ws) {''')
once('''        rc = fit_signal_body(ws, x_a_re, x_a_im, tones, decoded_dt_s, decoded_freq_hz, out_shat, cancel_flag);''',
     '''        pt_l = pt_now();
        rc = fit_signal_body(ws, x_a_re, x_a_im, tones, decoded_dt_s, decoded_freq_hz, out_shat, cancel_flag);
        pt_f[PT_FIT_TOTAL] = pt_now() - pt_l;''')

# ---- test-only exports, appended before the self-test block -----------------------------------------------------
EXPORTS = r'''
/* ===================== TEST-ONLY exports (make_timed_fit.py) ================================================ */
/* Copies the CALLING THREAD's last ft8_subfeas_fit_signal phase ticks into out[0..n-1]; returns PT_COUNT. */
int ft8_subfeas_pt_get(long long* out, int n)
{
    int i;
    for (i = 0; i < n && i < PT_COUNT; i++) out[i] = pt_f[i];
    return PT_COUNT;
}

long long ft8_subfeas_pt_frequency(void)
{
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    return f.QuadPart;
}

'''
marker = '/* ========================================================================\n * SUBFEAS_SELFTEST'
once(marker, EXPORTS + marker)

open(out_path, 'w', encoding='utf-8', newline='').write(s)
print('ok', out_path)
