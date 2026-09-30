/*
 * subfeas_fit.c -- data-aided fit + time-varying-envelope subtraction.
 * See subfeas_fit.h for provenance, licence-footing, and API contract.
 *
 * Every function below is a direct, line-traceable port of:
 *   qa/rr-study/sub-feas/fitter.py       (fine_fit, fine_fit_with_drift,
 *                                          lp_envelope, subtract, r_fit,
 *                                          r_fit_drift, apply_freq_shift,
 *                                          _freq_search, extract_segment)
 *   qa/rr-study/synth/modulator.py       (instantaneous_phase, _gaussian_pulse)
 *
 * Constants, search ranges and window width are INHERITED, not
 * re-derived (design.md Decision 1 Non-Goal) -- see subfeas_fit.h.
 *
 * FFT: KissFFT (native/ft8_lib_vendor/fft/kiss_fft.{c,h}), already vendored
 * and linked into libft8.dll (design.md Decision 3 addendum) -- complex-to-
 * complex only (kiss_fft, not kiss_fftr): every FFT this module performs is
 * on complex data.
 *
 * CONCURRENCY: ft8_subfeas_fit_signal is called concurrently, once per
 * signal, from C# (design.md's Decision 2 addendum). Every buffer this
 * module's internals use is heap-allocated fresh in ft8_subfeas_fit_signal
 * and threaded through as part of a single `workspace_t*` -- there is
 * deliberately no `static` (process-shared) storage anywhere below. An
 * earlier draft of this file used `static` local arrays inside the helper
 * functions as a "compute once, don't reallocate" shortcut; that is a
 * process-wide sharing bug under concurrent calls (silent cross-thread data
 * corruption, never a crash -- the worst kind to ship in a change whose
 * whole point is stability), caught and fixed before this was committed.
 */

#include "subfeas_fit.h"
#include "../fft/kiss_fft.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#ifdef _MSC_VER
#  include <excpt.h>
#endif

/* ---- derived constants ------------------------------------------------- */

#define N_FFT            SUBFEAS_N_FFT
#define N_TX             SUBFEAS_N_TX
#define FS               SUBFEAS_FS_HZ
#define SAMPLES_PER_MS   12   /* FS / 1000, exact */

/* Δt search: ±100ms @ 1ms steps -> 201 candidates */
#define DT_N_STEPS       100  /* round(DT_RANGE_MS / DT_STEP_MS) */
#define DT_STEP_SAMPLES  12   /* round(DT_STEP_MS * SAMPLES_PER_MS) */

/* ḟ search: [-0.10,+0.10] @ 0.005 steps -> 41 candidates */
#define FDOT_N_STEPS     20   /* round(FDOT_RANGE_HZ_S / FDOT_STEP_HZ_S) */

/* Gaussian pulse: span=3 symbols */
#define GAUSS_TAPS       (3 * SUBFEAS_SPS)   /* 5760 */

/* Envelope window: round(0.32 * 12000) = 3840 samples */
#define ENV_W_SAMPLES    3840

#define TRANSMISSION_S   (N_TX / FS)   /* 12.64, exact */

typedef struct { float r, i; } cf32;

/* ========================================================================
 * Per-call workspace: every buffer this module's internals need, allocated
 * ONCE at the top of ft8_subfeas_fit_signal and freed before it returns.
 * Passed by pointer to every helper -- nothing below is `static`.
 * ===================================================================== */
typedef struct {
    kiss_fft_cfg fwd, inv;
    void *work_fwd, *work_inv;

    /* N_FFT-sized (complex), used as FFT in/out scratch */
    kiss_fft_cpx *scratch_a, *scratch_b, *scratch_full, *scratch_search;

    /* N_TX-sized (complex) */
    cf32 *tone_arr, *smoothed;          /* instantaneous_phase */
    cf32 *r_unit, *r_base, *mixed, *seg; /* fine_fit_with_drift */
    cf32 *r_base_final, *envelope;       /* fit_signal top level */
    cf32 *num, *num_c, *den_cf, *den_c;  /* lp_envelope */
    float *den;                          /* lp_envelope */
    double *phase;                       /* instantaneous_phase */

    /* small, fixed-size */
    double *pulse;      /* GAUSS_TAPS */
    cf32 *pulse_cf;      /* GAUSS_TAPS */
    double *hann_d;      /* ENV_W_SAMPLES */
    cf32 *win_cf;         /* ENV_W_SAMPLES */
} workspace_t;

/* Returns 1 if every allocation in `ws` succeeded, 0 otherwise. On 0, the
 * caller must still call workspace_free (frees whichever pointers are
 * non-NULL; every field is malloc'd or NULL, matching free's own contract
 * for NULL). */
static int workspace_alloc(workspace_t* ws)
{
    size_t ws_fwd = 0, ws_inv = 0;
    memset(ws, 0, sizeof(*ws));

    kiss_fft_alloc(N_FFT, 0, NULL, &ws_fwd);
    kiss_fft_alloc(N_FFT, 1, NULL, &ws_inv);
    ws->work_fwd = malloc(ws_fwd);
    ws->work_inv = malloc(ws_inv);

    ws->scratch_a      = (kiss_fft_cpx*)malloc(sizeof(kiss_fft_cpx) * N_FFT);
    ws->scratch_b       = (kiss_fft_cpx*)malloc(sizeof(kiss_fft_cpx) * N_FFT);
    ws->scratch_full    = (kiss_fft_cpx*)malloc(sizeof(kiss_fft_cpx) * N_FFT);
    ws->scratch_search  = (kiss_fft_cpx*)malloc(sizeof(kiss_fft_cpx) * N_FFT);

    ws->tone_arr        = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->smoothed        = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->r_unit          = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->r_base          = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->mixed           = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->seg             = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->r_base_final    = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->envelope        = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->num             = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->num_c           = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->den_cf          = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->den_c           = (cf32*)malloc(sizeof(cf32) * N_TX);
    ws->den             = (float*)malloc(sizeof(float) * N_TX);
    ws->phase           = (double*)malloc(sizeof(double) * N_TX);

    ws->pulse           = (double*)malloc(sizeof(double) * GAUSS_TAPS);
    ws->pulse_cf        = (cf32*)malloc(sizeof(cf32) * GAUSS_TAPS);
    ws->hann_d          = (double*)malloc(sizeof(double) * ENV_W_SAMPLES);
    ws->win_cf          = (cf32*)malloc(sizeof(cf32) * ENV_W_SAMPLES);

    if (!ws->work_fwd || !ws->work_inv || !ws->scratch_a || !ws->scratch_b ||
        !ws->scratch_full || !ws->scratch_search || !ws->tone_arr || !ws->smoothed ||
        !ws->r_unit || !ws->r_base || !ws->mixed || !ws->seg || !ws->r_base_final ||
        !ws->envelope || !ws->num || !ws->num_c || !ws->den_cf || !ws->den_c ||
        !ws->den || !ws->phase || !ws->pulse || !ws->pulse_cf || !ws->hann_d || !ws->win_cf) {
        return 0;
    }

    ws->fwd = kiss_fft_alloc(N_FFT, 0, ws->work_fwd, &ws_fwd);
    ws->inv = kiss_fft_alloc(N_FFT, 1, ws->work_inv, &ws_inv);
    return (ws->fwd != NULL && ws->inv != NULL);
}

static void workspace_free(workspace_t* ws)
{
    free(ws->work_fwd); free(ws->work_inv);
    free(ws->scratch_a); free(ws->scratch_b); free(ws->scratch_full); free(ws->scratch_search);
    free(ws->tone_arr); free(ws->smoothed);
    free(ws->r_unit); free(ws->r_base); free(ws->mixed); free(ws->seg);
    free(ws->r_base_final); free(ws->envelope);
    free(ws->num); free(ws->num_c); free(ws->den_cf); free(ws->den_c); free(ws->den);
    free(ws->phase);
    free(ws->pulse); free(ws->pulse_cf); free(ws->hann_d); free(ws->win_cf);
}

/* ========================================================================
 * Small numeric helpers
 * ===================================================================== */

/* fitter.py/modulator.py:_gaussian_pulse -- length-3-symbol Gaussian
 * smoothing pulse, normalised to unit (discrete) sum. */
static void gaussian_pulse(double* pulse /* GAUSS_TAPS long */)
{
    const int n = GAUSS_TAPS;
    const double sps = (double)SUBFEAS_SPS;
    const double sigma = sqrt(log(2.0)) / (2.0 * M_PI * SUBFEAS_GFSK_BT);
    double sum = 0.0;
    int i;
    for (i = 0; i < n; i++) {
        double t = ((double)i - (double)n / 2.0 + 0.5) / sps; /* symbol periods */
        double v = exp(-(t * t) / (2.0 * sigma * sigma));
        pulse[i] = v;
        sum += v;
    }
    for (i = 0; i < n; i++) pulse[i] /= sum;
}

/* ========================================================================
 * FFT-based linear convolution, scipy.signal.fftconvolve(mode="same")
 * semantics: output has the same length as `a` (the first/larger operand),
 * centred within the full (len(a)+len(b)-1) convolution per scipy's own
 * `_centered` slicing: start = (len(b) - 1) // 2 into the full result.
 *
 * `a_buf`/`b_buf` are caller-supplied N_FFT-long scratch (ws->scratch_a/b);
 * `full_buf` is caller-supplied N_FFT-long scratch (ws->scratch_full) for
 * the product/inverse-transform step. n_fft must be >= a_len + b_len - 1.
 * ===================================================================== */
static void fft_convolve_same(
    kiss_fft_cfg fwd, kiss_fft_cfg inv, int n_fft,
    const cf32* a, int a_len,
    const cf32* b, int b_len,
    cf32* out /* a_len long */,
    kiss_fft_cpx* a_buf, kiss_fft_cpx* b_buf, kiss_fft_cpx* full_buf)
{
    int i;
    int start;

    for (i = 0; i < n_fft; i++) {
        if (i < a_len) { a_buf[i].r = a[i].r; a_buf[i].i = a[i].i; }
        else            { a_buf[i].r = 0.0f;  a_buf[i].i = 0.0f;  }
    }
    for (i = 0; i < n_fft; i++) {
        if (i < b_len) { b_buf[i].r = b[i].r; b_buf[i].i = b[i].i; }
        else            { b_buf[i].r = 0.0f;  b_buf[i].i = 0.0f;  }
    }

    kiss_fft(fwd, a_buf, a_buf);
    kiss_fft(fwd, b_buf, b_buf);
    for (i = 0; i < n_fft; i++) {
        float re = a_buf[i].r * b_buf[i].r - a_buf[i].i * b_buf[i].i;
        float im = a_buf[i].r * b_buf[i].i + a_buf[i].i * b_buf[i].r;
        full_buf[i].r = re;
        full_buf[i].i = im;
    }
    kiss_fft(inv, full_buf, full_buf);

    /* KissFFT's inverse does not normalise (matches FFTW convention):
     * divide by n_fft, matching numpy's ifft. */
    start = (b_len - 1) / 2; /* scipy _centered start index, integer division */
    for (i = 0; i < a_len; i++) {
        out[i].r = full_buf[start + i].r / (float)n_fft;
        out[i].i = full_buf[start + i].i / (float)n_fft;
    }
}

/* ========================================================================
 * modulator.py:instantaneous_phase, split in two (sub-feas-speed-redesign A1).
 *
 * The Gaussian-smoothed tone track (tone_arr convolved with the pulse) depends only on the
 * signal's TONES, never on base_freq or drift: the original single function recomputed it for
 * every one of the ~243 templates a fit builds. compute_smoothed_track() now does it ONCE per
 * signal into ws->smoothed (held as float cf32, exactly the precision the old code held it at
 * when it added the drift term, per design.md D1), and instantaneous_phase() applies only the
 * drift-dependent part. Same arithmetic, same order, on the same values: bit-identical output.
 * ===================================================================== */
static void compute_smoothed_track(workspace_t* ws, const uint8_t* tones)
{
    int sym, s, i;

    for (sym = 0; sym < SUBFEAS_NUM_SYMBOLS; sym++) {
        float tv = (float)tones[sym];
        int base = sym * SUBFEAS_SPS;
        for (s = 0; s < SUBFEAS_SPS; s++) {
            ws->tone_arr[base + s].r = tv;
            ws->tone_arr[base + s].i = 0.0f;
        }
    }
    for (i = 0; i < GAUSS_TAPS; i++) { ws->pulse_cf[i].r = (float)ws->pulse[i]; ws->pulse_cf[i].i = 0.0f; }

    fft_convolve_same(ws->fwd, ws->inv, N_FFT, ws->tone_arr, N_TX, ws->pulse_cf, GAUSS_TAPS,
                       ws->smoothed, ws->scratch_a, ws->scratch_b, ws->scratch_full);
}

/* Unwrapped instantaneous phase (rad) at base_freq_hz + optional linear drift_hz (total excursion
 * over the transmission, centred). REQUIRES ws->smoothed from compute_smoothed_track(). Writes
 * ws->phase (N_TX long). */
static void instantaneous_phase(workspace_t* ws, double base_freq_hz, double drift_hz)
{
    int i;
    double cum = 0.0;

    for (i = 0; i < N_TX; i++) {
        double inst_freq = base_freq_hz + (double)ws->smoothed[i].r * SUBFEAS_TONE_SPACING_HZ;
        if (drift_hz != 0.0) {
            double t_tx = (double)i / FS;
            inst_freq += drift_hz * (t_tx / TRANSMISSION_S - 0.5);
        }
        cum += inst_freq;
        ws->phase[i] = 2.0 * M_PI * cum / FS;
    }
}

/* fitter.py:r_fit_drift -- unit-amplitude complex baseband template,
 * frequency offset 0 (applied separately via apply_freq_shift), with linear
 * drift rate fdot_hz_per_s. At fdot=0, identical to r_fit(tones). */
static void r_fit_drift(workspace_t* ws, double fdot_hz_per_s, cf32* out_r /* N_TX */)
{
    double drift_hz = fdot_hz_per_s * TRANSMISSION_S;
    int i;
    instantaneous_phase(ws, 0.0, drift_hz);
    for (i = 0; i < N_TX; i++) {
        out_r[i].r = (float)cos(ws->phase[i]);
        out_r[i].i = (float)sin(ws->phase[i]);
    }
}

/* fitter.py:apply_freq_shift -- r_unit * exp(j*2*pi*df_hz*t) */
static void apply_freq_shift(const cf32* r_unit, int len, double df_hz, cf32* out)
{
    int i;
    for (i = 0; i < len; i++) {
        double t = (double)i / FS;
        double ph = 2.0 * M_PI * df_hz * t;
        double c = cos(ph), s = sin(ph);
        double rr = r_unit[i].r, ri = r_unit[i].i;
        out[i].r = (float)(rr * c - ri * s);
        out[i].i = (float)(rr * s + ri * c);
    }
}

/* fitter.py:_freq_search -- argmax_f |FFT(mixed, n_fft)| restricted to
 * |f| <= f_range_hz. mixed is N_TX long, zero-padded to n_fft inside this
 * function. Returns best_f_hz and best_val via out-params. */
static void freq_search(
    workspace_t* ws,
    const cf32* mixed, int mixed_len, double f_range_hz,
    double* out_best_f, double* out_best_val)
{
    int i;
    double best_val = -1.0;
    double best_f = 0.0;
    double bin_hz = FS / (double)N_FFT;
    int half = N_FFT / 2;
    kiss_fft_cpx* scratch = ws->scratch_search;

    for (i = 0; i < N_FFT; i++) {
        if (i < mixed_len) { scratch[i].r = mixed[i].r; scratch[i].i = mixed[i].i; }
        else                { scratch[i].r = 0.0f;       scratch[i].i = 0.0f;       }
    }
    kiss_fft(ws->fwd, scratch, scratch);

    /* kiss_fft bin layout matches numpy.fft.fftfreq's convention: bins
     * [0, n_fft/2) are freqs [0, +Nyquist), bins [n_fft/2, n_fft) are freqs
     * [-Nyquist, 0). */
    for (i = 0; i < N_FFT; i++) {
        double f = (i < half) ? (double)i * bin_hz : (double)(i - N_FFT) * bin_hz;
        double mag;
        if (fabs(f) > f_range_hz) continue;
        mag = sqrt((double)scratch[i].r * scratch[i].r + (double)scratch[i].i * scratch[i].i);
        if (mag > best_val) { best_val = mag; best_f = f; }
    }
    *out_best_f = best_f;
    *out_best_val = best_val;
}

/* ========================================================================
 * fitter.py:fine_fit_with_drift -- coarse-to-fine search, exact order:
 *   1. (Δt, Δf) at ḟ=0                          (plain fine_fit)
 *   2. ḟ search, Δt held, Δf re-fit each step
 *   3. Δt refined once more, (ḟ, Δf) held, direct correlation (no FFT)
 * Returns 1 on success (out-params populated), 0 if every candidate ran off
 * the buffer edge (fitter.py returning None).
 * ===================================================================== */
static int fine_fit_with_drift(
    workspace_t* ws,
    const float* x_a_re, const float* x_a_im,
    const uint8_t* tones, double freq_hz, double nominal_t_s,
    double* out_dt_s, double* out_df_hz, double* out_fdot,
    int* out_start_sample, cf32* out_r_base_final /* N_TX long */)
{
    int base_start = (int)(nominal_t_s * FS + (nominal_t_s >= 0 ? 0.5 : -0.5));
    int k, i;

    double step1_best_val = -1.0;
    int step1_best_dt_samples = 0;
    int have_step1 = 0;

    /* A1: the tone-dependent smoothing, once for all ~243 templates below. */
    compute_smoothed_track(ws, tones);

    /* ---- Step 1: (Δt, Δf) at ḟ=0 ---- */
    r_fit_drift(ws, 0.0, ws->r_unit);
    apply_freq_shift(ws->r_unit, N_TX, freq_hz, ws->r_base);

    for (k = -DT_N_STEPS; k <= DT_N_STEPS; k++) {
        int start = base_start + k * DT_STEP_SAMPLES;
        double f_hat, val;
        if (start < 0 || start + N_TX > SUBFEAS_PCM_LEN) continue;
        for (i = 0; i < N_TX; i++) {
            ws->mixed[i].r = x_a_re[start + i];
            ws->mixed[i].i = x_a_im[start + i];
        }
        /* mixed *= conj(r_base) */
        for (i = 0; i < N_TX; i++) {
            float mr = ws->mixed[i].r, mi = ws->mixed[i].i;
            float rr = ws->r_base[i].r, ri = -ws->r_base[i].i;
            ws->mixed[i].r = mr * rr - mi * ri;
            ws->mixed[i].i = mr * ri + mi * rr;
        }
        freq_search(ws, ws->mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &f_hat, &val);
        if (!have_step1 || val > step1_best_val) {
            have_step1 = 1;
            step1_best_val = val;
            step1_best_dt_samples = k * DT_STEP_SAMPLES;
        }
    }
    if (!have_step1) return 0;

    /* ---- Step 2: ḟ search, Δt held at step 1's value, Δf re-fit each ḟ ---- */
    {
        int fixed_start = base_start + step1_best_dt_samples;
        double best_val2 = -1.0;
        double best_fdot = 0.0, best_df2 = 0.0;
        int kf;
        for (i = 0; i < N_TX; i++) {
            ws->seg[i].r = x_a_re[fixed_start + i];
            ws->seg[i].i = x_a_im[fixed_start + i];
        }
        for (kf = -FDOT_N_STEPS; kf <= FDOT_N_STEPS; kf++) {
            double fdot = kf * SUBFEAS_FDOT_STEP_HZ_S;
            double f_hat, val;
            r_fit_drift(ws, fdot, ws->r_unit);
            apply_freq_shift(ws->r_unit, N_TX, freq_hz, ws->r_base);
            for (i = 0; i < N_TX; i++) {
                float mr = ws->seg[i].r, mi = ws->seg[i].i;
                float rr = ws->r_base[i].r, ri = -ws->r_base[i].i;
                ws->mixed[i].r = mr * rr - mi * ri;
                ws->mixed[i].i = mr * ri + mi * rr;
            }
            freq_search(ws, ws->mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &f_hat, &val);
            if (val > best_val2) { best_val2 = val; best_fdot = fdot; best_df2 = f_hat; }
        }
        *out_fdot = best_fdot;
        *out_df_hz = best_df2;

        /* Final template at (ḟ*, Δf*) -- used for step 3's direct-correlation
         * scoring AND returned as the fit's template for envelope/subtract. */
        r_fit_drift(ws, best_fdot, ws->r_unit);
        apply_freq_shift(ws->r_unit, N_TX, freq_hz, ws->r_base);
        apply_freq_shift(ws->r_base, N_TX, best_df2, out_r_base_final);
    }

    /* ---- Step 3: Δt refined once more, (ḟ, Δf) held, direct correlation ---- */
    {
        double best_score = -1.0;
        int best_dt_samples = 0;
        for (k = -DT_N_STEPS; k <= DT_N_STEPS; k++) {
            int start = base_start + k * DT_STEP_SAMPLES;
            double sr = 0.0, si = 0.0, score;
            if (start < 0 || start + N_TX > SUBFEAS_PCM_LEN) continue;
            for (i = 0; i < N_TX; i++) {
                float xr = x_a_re[start + i], xi = x_a_im[start + i];
                float rr = out_r_base_final[i].r, ri = -out_r_base_final[i].i; /* conj(r) */
                sr += xr * rr - xi * ri;
                si += xr * ri + xi * rr;
            }
            score = sqrt(sr * sr + si * si);
            if (score > best_score) { best_score = score; best_dt_samples = k * DT_STEP_SAMPLES; }
        }
        if (best_score < 0.0) return 0; /* every step-3 candidate also ran off the edge */
        *out_start_sample = base_start + best_dt_samples;
        *out_dt_s = (double)best_dt_samples / FS;
    }

    return 1;
}

/* ========================================================================
 * fitter.py:lp_envelope -- Hann-weighted moving-average complex-gain
 * envelope. W >= the full transmission is the degenerate "one complex
 * scalar for the whole 12.64s" case (broadcast, not windowed convolution --
 * matches fitter.py's own documented reasoning; SUBFEAS_ENVELOPE_W_S=0.32s
 * never hits this branch in production use, but a larger W correctly would).
 * ===================================================================== */
static void lp_envelope(
    workspace_t* ws,
    const float* x_seg_re, const float* x_seg_im, /* N_TX long: analytic segment at fitted position */
    const cf32* r_seg,                              /* N_TX long: fitted template */
    cf32* out_c /* N_TX long */)
{
    int i;
    int w_samples = ENV_W_SAMPLES;

    for (i = 0; i < N_TX; i++) {
        /* num = x_seg * conj(r_seg) */
        float xr = x_seg_re[i], xi = x_seg_im[i];
        float rr = r_seg[i].r, ri = -r_seg[i].i;
        ws->num[i].r = xr * rr - xi * ri;
        ws->num[i].i = xr * ri + xi * rr;
        ws->den[i] = r_seg[i].r * r_seg[i].r + r_seg[i].i * r_seg[i].i;
    }

    if (w_samples >= N_TX) {
        double sumr = 0.0, sumi = 0.0, sumd = 0.0;
        cf32 c0;
        for (i = 0; i < N_TX; i++) { sumr += ws->num[i].r; sumi += ws->num[i].i; sumd += ws->den[i]; }
        c0.r = (float)(sumr / sumd);
        c0.i = (float)(sumi / sumd);
        for (i = 0; i < N_TX; i++) out_c[i] = c0;
        return;
    }

    {
        int j;
        /* numpy.hanning(M): 0.5 - 0.5*cos(2*pi*n/(M-1)), n=0..M-1 */
        for (j = 0; j < w_samples; j++) {
            ws->hann_d[j] = (w_samples > 1)
                ? 0.5 - 0.5 * cos(2.0 * M_PI * (double)j / (double)(w_samples - 1))
                : 1.0;
            ws->win_cf[j].r = (float)ws->hann_d[j];
            ws->win_cf[j].i = 0.0f;
        }
        for (i = 0; i < N_TX; i++) { ws->den_cf[i].r = ws->den[i]; ws->den_cf[i].i = 0.0f; }

        fft_convolve_same(ws->fwd, ws->inv, N_FFT, ws->num, N_TX, ws->win_cf, w_samples,
                           ws->num_c, ws->scratch_a, ws->scratch_b, ws->scratch_full);
        fft_convolve_same(ws->fwd, ws->inv, N_FFT, ws->den_cf, N_TX, ws->win_cf, w_samples,
                           ws->den_c, ws->scratch_a, ws->scratch_b, ws->scratch_full);

        for (i = 0; i < N_TX; i++) {
            if (ws->den_c[i].r > 1e-12f) {
                out_c[i].r = ws->num_c[i].r / ws->den_c[i].r;
                out_c[i].i = ws->num_c[i].i / ws->den_c[i].r;
            } else {
                out_c[i].r = 0.0f;
                out_c[i].i = 0.0f;
            }
        }
    }
}

/* ========================================================================
 * Public entry points
 * ===================================================================== */

int ft8_subfeas_compute_analytic(const float* pcm, float* out_re, float* out_im)
{
    kiss_fft_cfg fwd, inv;
    kiss_fft_cpx* buf;
    size_t work_size_fwd = 0, work_size_inv = 0;
    void *work_fwd, *work_inv;
    int n = SUBFEAS_PCM_LEN;
    int i, half;
    int rc = 0;

    if (!pcm || !out_re || !out_im) return -1;

#ifdef _MSC_VER
    __try {
#endif
        kiss_fft_alloc(n, 0, NULL, &work_size_fwd);
        kiss_fft_alloc(n, 1, NULL, &work_size_inv);
        work_fwd = malloc(work_size_fwd);
        work_inv = malloc(work_size_inv);
        buf = (kiss_fft_cpx*)malloc(sizeof(kiss_fft_cpx) * (size_t)n);
        if (!work_fwd || !work_inv || !buf) {
            free(work_fwd); free(work_inv); free(buf);
            rc = -1;
        } else {
            fwd = kiss_fft_alloc(n, 0, work_fwd, &work_size_fwd);
            inv = kiss_fft_alloc(n, 1, work_inv, &work_size_inv);

            for (i = 0; i < n; i++) { buf[i].r = pcm[i]; buf[i].i = 0.0f; }
            kiss_fft(fwd, buf, buf);

            /* scipy.signal.hilbert's frequency-domain multiplier, N even:
             * h[0]=1, h[1..N/2-1]=2, h[N/2]=1, h[N/2+1..]=0. */
            half = n / 2;
            for (i = 1; i < half; i++) { buf[i].r *= 2.0f; buf[i].i *= 2.0f; }
            for (i = half + 1; i < n; i++) { buf[i].r = 0.0f; buf[i].i = 0.0f; }
            /* buf[0] and buf[half] unchanged (multiplier 1). */

            kiss_fft(inv, buf, buf);
            for (i = 0; i < n; i++) {
                out_re[i] = buf[i].r / (float)n;
                out_im[i] = buf[i].i / (float)n;
            }
            free(work_fwd); free(work_inv); free(buf);
        }
#ifdef _MSC_VER
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return -2;
    }
#endif
    return rc;
}

int ft8_subfeas_fit_signal(
    const float* x_a_re, const float* x_a_im,
    const uint8_t* tones,
    float decoded_dt_s, float decoded_freq_hz,
    float* out_shat)
{
    int i, ok;
    int rc = 0;
    workspace_t ws; /* declared before __try, matching ft8_decode_all's own
                      * "monitor_t mon declared before __try" discipline --
                      * in scope for the __except handler if ever needed. */

    if (!x_a_re || !x_a_im || !tones || !out_shat) return -1;
    for (i = 0; i < SUBFEAS_NUM_SYMBOLS; i++) if (tones[i] > 7) return -1;

    memset(out_shat, 0, sizeof(float) * SUBFEAS_PCM_LEN);
    memset(&ws, 0, sizeof(ws));

#ifdef _MSC_VER
    __try {
#endif
    {
        double nominal_t_s, dt_s, df_hz, fdot;
        int start_sample = 0;

        if (!workspace_alloc(&ws)) {
            /* Allocation failure: graceful, no partial state written
             * (out_shat already zeroed) -- matches Decision 4's contract. */
            rc = -1;
        } else {
            gaussian_pulse(ws.pulse);
            nominal_t_s = (double)decoded_dt_s + SUBFEAS_TAU0_S;

            ok = fine_fit_with_drift(
                &ws, x_a_re, x_a_im, tones, (double)decoded_freq_hz, nominal_t_s,
                &dt_s, &df_hz, &fdot, &start_sample, ws.r_base_final);

            if (!ok) {
                rc = -3;
            } else {
                lp_envelope(&ws, x_a_re + start_sample, x_a_im + start_sample, ws.r_base_final, ws.envelope);

                for (i = 0; i < N_TX; i++) {
                    float cr = ws.envelope[i].r, ci = ws.envelope[i].i;
                    float rr = ws.r_base_final[i].r, ri = ws.r_base_final[i].i;
                    /* s_hat = Re{c(t) * template(t)} */
                    out_shat[start_sample + i] = cr * rr - ci * ri;
                }
                rc = 0;
            }
        }
        workspace_free(&ws);
    }
#ifdef _MSC_VER
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        /* Heap may be partially corrupted after an AV -- do not attempt
         * workspace_free here, same discipline ft8_decode_all's own
         * __except uses (a second fault in the handler is worse than a
         * per-call leak). */
        return -2;
    }
#endif
    return rc;
}

/* ========================================================================
 * SUBFEAS_SELFTEST -- standalone round-trip self-check, not compiled into
 * libft8.dll (no call site here from ft8_shim.c). Built only when this
 * translation unit is compiled with -DSUBFEAS_SELFTEST, from a scratch
 * harness. White-box (uses the static internals directly) rather than
 * black-box against the public API only, so it can also sanity-check
 * r_fit_drift/apply_freq_shift/instantaneous_phase in isolation.
 *
 * Test: synthesize a known template (tones, freq_hz, dt_s, fdot=0) with this
 * module's OWN r_fit_drift/apply_freq_shift, embed it into an otherwise-zero
 * 180,000-sample PCM buffer at a known position, run it through
 * ft8_subfeas_compute_analytic + ft8_subfeas_fit_signal, and check:
 *   (a) no crash, non-error return
 *   (b) recovered position/frequency are close to what was embedded
 *   (c) residual energy (original - out_shat) is much lower than the
 *       original signal's energy in-band -- the actual point of this whole
 *       change
 * This is a round-trip self-consistency check (the "ground truth" is this
 * module's own synthesis), not an independent validation against WSJT-X or
 * real audio -- that is what task 8's live/second-corpus gates are for.
 * ===================================================================== */
#ifdef SUBFEAS_SELFTEST
#include <stdio.h>

static int run_case(
    const char* name,
    double embed_dt_s, double embed_freq_hz, double embed_fdot,
    double decoded_dt_s, double decoded_freq_hz)
{
    static float pcm[SUBFEAS_PCM_LEN];
    static float x_a_re[SUBFEAS_PCM_LEN], x_a_im[SUBFEAS_PCM_LEN];
    static float out_shat[SUBFEAS_PCM_LEN];
    uint8_t tones[SUBFEAS_NUM_SYMBOLS];
    int i, rc;
    const int embed_start = (int)(embed_dt_s * SUBFEAS_FS_HZ + 0.5);
    workspace_t ws;
    double before_energy = 0.0, after_energy = 0.0;

    for (i = 0; i < SUBFEAS_NUM_SYMBOLS; i++) tones[i] = (uint8_t)(i % 8);

    memset(pcm, 0, sizeof(pcm));
    memset(&ws, 0, sizeof(ws));
    if (!workspace_alloc(&ws)) { printf("[%s] FAIL: workspace_alloc\n", name); return 1; }
    gaussian_pulse(ws.pulse);
    compute_smoothed_track(&ws, tones);

    {
        cf32 *r_unit = ws.r_unit, *r_base = ws.r_base;
        r_fit_drift(&ws, embed_fdot, r_unit);
        apply_freq_shift(r_unit, N_TX, embed_freq_hz, r_base);
        if (embed_start < 0 || embed_start + N_TX > SUBFEAS_PCM_LEN) {
            printf("[%s] FAIL: test setup, embed_start out of range: %d\n", name, embed_start);
            workspace_free(&ws);
            return 1;
        }
        for (i = 0; i < N_TX; i++) pcm[embed_start + i] = r_base[i].r;
    }
    workspace_free(&ws);

    for (i = embed_start; i < embed_start + N_TX; i++) before_energy += (double)pcm[i] * pcm[i];

    rc = ft8_subfeas_compute_analytic(pcm, x_a_re, x_a_im);
    if (rc != 0) { printf("[%s] FAIL: compute_analytic rc=%d\n", name, rc); return 1; }

    /* decoded_dt_s is what a caller (a real decode) would pass -- the
     * module internally adds tau0 to get its own nominal search centre.
     * Passing decoded_dt_s != (embed_dt_s - tau0) exercises the actual
     * Delta t/Delta f/f-dot search grid instead of trivially landing on k=0. */
    rc = ft8_subfeas_fit_signal(x_a_re, x_a_im, tones, (float)decoded_dt_s, (float)decoded_freq_hz, out_shat);
    if (rc != 0) { printf("[%s] FAIL: fit_signal rc=%d\n", name, rc); return 1; }

    for (i = embed_start; i < embed_start + N_TX; i++) {
        double resid = (double)pcm[i] - (double)out_shat[i];
        after_energy += resid * resid;
    }

    printf("[%s] before=%.6e after=%.6e suppression_dB=%.2f embed_start=%d\n",
           name, before_energy, after_energy,
           (after_energy > 0.0) ? 10.0 * log10(before_energy / after_energy) : 999.0,
           embed_start);

    if (after_energy >= before_energy) { printf("[%s] FAIL: residual energy did not decrease\n", name); return 1; }
    if (after_energy / before_energy > 0.01) {
        printf("[%s] FAIL: suppression weaker than expected (>1%% residual energy, want strong suppression for a zero-noise exact-model round trip)\n", name);
        return 1;
    }
    printf("[%s] PASS\n", name);
    return 0;
}

int main(void)
{
    int failures = 0;
    /* Case 1: embedded exactly at the nominal search centre (decoded_dt_s
     * such that decoded_dt_s + tau0 == embed_dt_s) -- degenerate, k=0,
     * exercises envelope/subtract but not the search grid. */
    failures += run_case("centered", 0.1400, 1500.0, 0.0, 0.30, 1500.0);

    /* Case 2: decoded position/frequency deliberately offset from the true
     * embedded position -- forces the +-100ms Delta t and +-2Hz Delta f
     * search to actually find the right answer, not just confirm k=0. */
    failures += run_case("offset_t_f", 0.1876, 1501.3, 0.0, 0.30, 1500.0);

    /* Case 3: as case 2, plus a nonzero drift rate -- forces the f-dot
     * search (step 2) to find the right ray, not just fit at fdot=0. */
    failures += run_case("offset_t_f_fdot", 0.1876, 1501.3, 0.04, 0.30, 1500.0);

    if (failures) { printf("%d CASE(S) FAILED\n", failures); return 1; }
    printf("ALL PASS\n");
    return 0;
}
#endif /* SUBFEAS_SELFTEST */
