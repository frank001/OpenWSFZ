/*
 * phase_timing.c -- TEST-ONLY white-box cost map of the sub-feas fit (sub-feas-speed-redesign tasks 2.1/2.2).
 *
 * #includes subfeas_fit.c itself (path given by -DSUBFEAS_SRC="...") so it can call the static helpers directly;
 * NOTHING in the product source is modified for this. Times ONE unit of each repeated step, then composes the
 * per-signal cost from the loop counts in fine_fit_with_drift, and prints the longest stretch a cancel flag that is
 * checked once per loop iteration would have to wait through.
 *
 * Output: integers/microseconds only (HK-037). Build with build_phase_timing.bat, run with no arguments.
 */
#ifdef _WIN32
#include <windows.h>   /* BEFORE the fit source: its short macro names (FS, N_TX...) collide with SDK headers */
#endif
#include SUBFEAS_SRC

#ifdef _WIN32
static double now_us(void)
{
    static LARGE_INTEGER f; LARGE_INTEGER c;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart * 1e6 / (double)f.QuadPart;
}
#endif
#include <stdio.h>

#define REPS 5
static volatile double sink; /* keeps the optimiser from deleting the step-3 timing body */

static double median(double* v, int n)
{
    int i, j;
    for (i = 1; i < n; i++) { double x = v[i]; for (j = i - 1; j >= 0 && v[j] > x; j--) v[j + 1] = v[j]; v[j + 1] = x; }
    return v[n / 2];
}

#define TIME(label, ...) do { double t[REPS]; int r; for (r = 0; r < REPS; r++) { double a = now_us(); { __VA_ARGS__ ; } t[r] = now_us() - a; } \
    label##_us = median(t, REPS); } while (0)

int main(void)
{
    static float pcm[SUBFEAS_PCM_LEN], re[SUBFEAS_PCM_LEN], im[SUBFEAS_PCM_LEN], shat[SUBFEAS_PCM_LEN];
    uint8_t tones[SUBFEAS_NUM_SYMBOLS];
    workspace_t ws;
    int i, k;
    double analytic_us, rfit_us, shift_us, mix_us, fsearch_us, conv_us, corr_us, whole_us, gp_us;
    double f_hat, val;
    unsigned s = 12345u;

    for (i = 0; i < SUBFEAS_NUM_SYMBOLS; i++) { s = s * 1664525u + 1013904223u; tones[i] = (uint8_t)((s >> 16) & 7); }
    for (i = 0; i < SUBFEAS_PCM_LEN; i++) { s = s * 1664525u + 1013904223u; pcm[i] = ((float)((s >> 8) & 0xFFFF) / 32768.0f - 1.0f) * 0.2f; }

    TIME(analytic, ft8_subfeas_compute_analytic(pcm, re, im));

    memset(&ws, 0, sizeof(ws));
    if (!workspace_alloc(&ws)) { printf("workspace_alloc failed\n"); return 1; }
    gaussian_pulse(ws.pulse);

    TIME(gp, gaussian_pulse(ws.pulse));
    /* r_fit_drift with drift != 0 exercises the drift branch of instantaneous_phase (the ḟ loop's case). */
    TIME(rfit, r_fit_drift(&ws, tones, 0.05, ws.r_unit));
    TIME(shift, apply_freq_shift(ws.r_unit, N_TX, 1500.0, ws.r_base));
    TIME(mix, {
        for (i = 0; i < N_TX; i++) { ws.mixed[i].r = re[1000 + i]; ws.mixed[i].i = im[1000 + i]; }
        for (i = 0; i < N_TX; i++) {
            float mr = ws.mixed[i].r, mi = ws.mixed[i].i, rr = ws.r_base[i].r, ri = -ws.r_base[i].i;
            ws.mixed[i].r = mr * rr - mi * ri; ws.mixed[i].i = mr * ri + mi * rr;
        }
    });
    TIME(fsearch, freq_search(&ws, ws.mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &f_hat, &val));
    TIME(conv, fft_convolve_same(ws.fwd, ws.inv, N_FFT, ws.tone_arr, N_TX, ws.win_cf, ENV_W_SAMPLES, ws.num_c,
                                 ws.scratch_a, ws.scratch_b, ws.scratch_full));
    /* step 3: one direct-correlation Δt candidate */
    TIME(corr, {
        double sr = 0.0, si = 0.0;
        for (i = 0; i < N_TX; i++) {
            float xr = re[1000 + i], xi = im[1000 + i], rr = ws.r_base[i].r, ri = -ws.r_base[i].i;
            sr += xr * rr - xi * ri; si += xr * ri + xi * rr;
        }
        sink = sqrt(sr * sr + si * si);
    });
    workspace_free(&ws);

    /* whole fit, single thread, for the sum check (decoded_dt chosen so no candidate runs off the edge) */
    TIME(whole, ft8_subfeas_fit_signal(re, im, tones, 0.5f, 1500.0f, shat));

    {
        const int n_dt = 2 * DT_N_STEPS + 1;       /* 201 */
        const int n_fd = 2 * FDOT_N_STEPS + 1;     /* 41  */
        double step1_us = n_dt * (mix_us + fsearch_us) + rfit_us + shift_us;
        double step2_us = n_fd * (rfit_us + shift_us + mix_us + fsearch_us);
        double final_us = rfit_us + 2 * shift_us;
        double step3_us = n_dt * corr_us;
        double env_us   = 2 * conv_us;
        double sum_us   = step1_us + step2_us + final_us + step3_us + env_us;
        double iter_dt  = mix_us + fsearch_us;
        double iter_fd  = rfit_us + shift_us + mix_us + fsearch_us;
        double longest  = iter_fd > iter_dt ? iter_fd : iter_dt;
        if (conv_us > longest) longest = conv_us;
        printf("unit_us: analytic=%.0f gaussian_pulse=%.0f r_fit_drift=%.0f apply_freq_shift=%.0f mix=%.0f freq_search=%.0f "
               "fft_convolve_same=%.0f step3_candidate=%.0f\n",
               analytic_us, gp_us, rfit_us, shift_us, mix_us, fsearch_us, conv_us, corr_us);
        printf("phase_ms: step1_dt_search=%.0f step2_fdot_search=%.0f final_template=%.0f step3_dt_refine=%.0f envelope=%.0f "
               "sum=%.0f measured_whole_fit=%.0f\n",
               step1_us / 1000, step2_us / 1000, final_us / 1000, step3_us / 1000, env_us / 1000, sum_us / 1000, whole_us / 1000);
        printf("longest_uninterruptible_stretch_ms (one loop iteration, flag checked per iteration)=%.0f  "
               "(dt_iteration=%.0f fdot_iteration=%.0f envelope_convolution=%.0f)\n",
               longest / 1000, iter_dt / 1000, iter_fd / 1000, conv_us / 1000);
        printf("uncancellable_per_cycle_ms: compute_analytic=%.0f\n", analytic_us / 1000);
        (void)k;
    }
    return 0;
}
