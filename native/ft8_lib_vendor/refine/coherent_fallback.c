/*
 * coherent_fallback.c -- COH-FALLBACK (A' step 3) Stage 1: the native core of the coherent-extraction fallback.
 *
 * PROVENANCE / CLEAN-ROOM: OpenWSFZ-original. A C port of our own clean-room Python reference at QA commit 44c70ea2
 * (qa/rr-study/coh-gain/fine_sync.py, qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py and the F1b function of
 * qa/rr-study/coh-gain/cg_gate_features.py), which are themselves written from FT8's public protocol constants (tone spacing
 * 6.25 Hz, symbol 0.16 s, the Costas array 3,1,4,0,6,5,2, the Gray map 0,1,3,2,5,6,4,7) and standard coherent-correlation
 * theory. NO WSJT-X source was opened or consulted. The Hann-sinc downconversion follows our own sync_refiner.c's method.
 *
 * WHAT IS EXACT AND WHAT IS REARRANGED (A2 is the judge of "exactly", spec R1):
 *   - The arithmetic is the reference's, in double precision: the 61-tap Hann-sinc lowpass at 900 Hz (12 kHz in, decimated by 6),
 *     the fine-sync objective |sum over the 21 Costas symbols of (the symbol's correlation against its Costas tone) x
 *     exp(-j 2 pi df start/2000)| on the 41 x 49 (df, dt) grid, first maximum, F1b over the median of the 24 reference peaks,
 *     and the V3 order-1+2+3 max-log LLRs over the 8-tone Gray bits.
 *   - Rearranged, mathematically identical (SHORTCUT S1): the reference evaluates the objective as one (K*P, 320) x (320, n_df)
 *     matrix product per surface. Writing the symbol correlation as a windowed sum of bb[i] exp(-j 2 pi (df i/2000 + tone
 *     (i - s_k)/320)) (the 320p term of the tone phase is a whole number of cycles), each (tone, df) needs only a prefix sum over
 *     the 800 samples around the tone's symbol, and the 49 dt windows are differences of that prefix. Same values to rounding,
 *     about 25 times fewer multiplications per surface.
 *   - SHORTCUT S2: only the decimated samples the three Costas blocks (or, for the C3 extraction, the 79 symbols) can touch are
 *     computed; the reference decimates the whole 180 000-sample buffer and never reads the rest.
 *   - SHORTCUT S3: the mixing phase exp(-j w i) is formed from two small tables (i = 512 q + r) instead of one sincos per sample.
 *
 * ANCHOR CONVENTION (R3). (f0, t0) are in the CANDIDATE convention of ft8_extract_llrs_at and ft8_decode_all: for a candidate on
 * the production lattice, f0 = (min_bin + freq_offset + freq_sub/freq_osr)/symbol_period and t0 = (time_offset + time_sub/
 * time_osr) x symbol_period, exactly the numbers ft8_decode_all reports as a decode's frequency and dt. In that convention
 * symbol 0 of the signal starts t0 - one symbol period into the PCM (the reference's TIME_ORIGIN_CORRECTION_SAMPLES_2K = -320 at
 * 2 kHz, calibrated against ft8_extract_llrs_at), so the estimator's symbol-0 start index at 2 kHz is round(t0 x 2000) - 320
 * and the search window (+-0.12 s, +-2 Hz) is centred on the lattice position itself. No other offset is applied.
 *
 * COH-MULTISET (shim 20260071): the four further bit-metric sets C1, J2, J3, N1 (cf_multiset_llrs below) are a C port of our own
 * clean-room Python reference qa/rr-study/coh-multiset/ms_metrics.py @ QA commit 96aa80d4, itself written from the Architect's PROSE
 * method (spec 2026-10-24) and FT8's public constants. METHOD ONLY: NO WSJT-X source was opened, copied, transliterated or ported
 * (licence policy; Captain 2026-10-24). They read the per-symbol correlations cf_v3_llrs leaves in the context.
 *
 * No mutable global state: every table lives in the context or on the stack (the hash-state completeness test scans this file).
 */

#include "coherent_fallback.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  include <windows.h>
#else
#  include <time.h>
#endif

#ifndef M_PI
#  define M_PI 3.14159265358979323846
#endif

#define CF_LP_TAPS          61
#define CF_LP_HALF          30
#define CF_LP_CUTOFF_HZ     900.0
#define CF_TONES            8
#define CF_TONE_TABLE       512     /* low part of the mixing-phase index */
#define CF_BLOCKS           3
#define CF_BLOCK_SYMBOLS    7
#define CF_WIN_PAD          240     /* 24 dt steps x 10 samples either side of a symbol start */
#define CF_PFX_LEN          (CF_SPS + 2 * CF_WIN_PAD)        /* 800: the samples around one tone's symbol */
#define CF_REGION_LEN       (CF_BLOCK_SYMBOLS * CF_SPS + 2 * CF_WIN_PAD + CF_SPS)   /* span of one Costas block's samples (2800) */
#define CF_DF_MAX_HZ        2.0
#define CF_DF_STEP_HZ       0.1
#define CF_DT_STEP_S        0.005
#define CF_TIME_ORIGIN_CORRECTION_SAMPLES_2K (-CF_SPS)       /* -320: one symbol period (see ANCHOR CONVENTION) */
#define CF_GRAY_RESEED      128     /* direct sincos every this many samples of a phase recurrence */
#define CF_REF_COUNT        24      /* F1b reference frequencies */
#define CF_REF_FIRST_HZ     40.0
#define CF_REF_STEP_HZ      10.0
#define CF_REF_MIN_HZ       200.0
#define CF_REF_MAX_HZ       3000.0

static const int kCostas[CF_BLOCK_SYMBOLS]  = { 3, 1, 4, 0, 6, 5, 2 };
static const int kCostasStart[CF_BLOCKS]    = { 0, 36, 72 };
static const int kGrayMap[CF_TONES]         = { 0, 1, 3, 2, 5, 6, 4, 7 };

struct cf_ctx {
    int     n;                       /* PCM length */
    int     nd;                      /* decimated length, ceil(n / 6) */
    double  taps[CF_LP_TAPS];
    double  tp_re[CF_SPS], tp_im[CF_SPS];          /* cis(-2 pi k / 320) */
    double  lo_re[CF_TONE_TABLE], lo_im[CF_TONE_TABLE];
    double* hi_re;  double* hi_im;                 /* cis(-w 512 q) for the current carrier */
    double* mix_re; double* mix_im;                /* the mixed PCM for the current carrier (only the touched range is valid) */
    double* dec_re; double* dec_im;                /* the decimated baseband for the current carrier */
    double* g_re;   double* g_im;                  /* bb x exp(-j 2 pi df i / 2000) over one Costas block's region */
    double  p_re[CF_PFX_LEN + 1], p_im[CF_PFX_LEN + 1];
    double* acc_re; double* acc_im;                /* the complex sum per (df, dt) */
    double  x_re[CF_NSYM * CF_TONES], x_im[CF_NSYM * CF_TONES];
};

double cf_monotonic_ms(void)
{
#ifdef _WIN32
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return 1000.0 * (double)c.QuadPart / (double)f.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return 1000.0 * (double)ts.tv_sec + (double)ts.tv_nsec / 1.0e6;
#endif
}

/* Hann-windowed-sinc lowpass, unit DC gain: design_lowpass_hann of coherent_extract.py, in double. */
static void cf_design_taps(double* taps)
{
    const int    mid = CF_LP_TAPS / 2;
    const double fc  = CF_LP_CUTOFF_HZ / (double)CF_SAMPLE_RATE_HZ;
    double       sum = 0.0;
    for (int n = 0; n < CF_LP_TAPS; n++) {
        int    k      = n - mid;
        double sinc   = (k == 0) ? 2.0 * fc : sin(2.0 * M_PI * fc * (double)k) / (M_PI * (double)k);
        double window = 0.5 - 0.5 * cos(2.0 * M_PI * (double)n / (double)(CF_LP_TAPS - 1));
        taps[n] = sinc * window;
        sum += taps[n];
    }
    if (sum != 0.0)
        for (int n = 0; n < CF_LP_TAPS; n++) taps[n] /= sum;
}

cf_ctx_t* cf_ctx_new(int pcm_len)
{
    if (pcm_len <= 0) return NULL;
    cf_ctx_t* c = (cf_ctx_t*)calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->n  = pcm_len;
    c->nd = (pcm_len + CF_DECIM - 1) / CF_DECIM;
    const int nhi = pcm_len / CF_TONE_TABLE + 2;
    c->hi_re  = (double*)malloc((size_t)nhi * sizeof(double));
    c->hi_im  = (double*)malloc((size_t)nhi * sizeof(double));
    c->mix_re = (double*)malloc((size_t)pcm_len * sizeof(double));
    c->mix_im = (double*)malloc((size_t)pcm_len * sizeof(double));
    c->dec_re = (double*)calloc((size_t)c->nd, sizeof(double));
    c->dec_im = (double*)calloc((size_t)c->nd, sizeof(double));
    c->g_re   = (double*)malloc((size_t)CF_REGION_LEN * sizeof(double));
    c->g_im   = (double*)malloc((size_t)CF_REGION_LEN * sizeof(double));
    c->acc_re = (double*)malloc((size_t)CF_NDF * CF_NDT * sizeof(double));
    c->acc_im = (double*)malloc((size_t)CF_NDF * CF_NDT * sizeof(double));
    if (!c->hi_re || !c->hi_im || !c->mix_re || !c->mix_im || !c->dec_re || !c->dec_im ||
        !c->g_re || !c->g_im || !c->acc_re || !c->acc_im) {
        cf_ctx_free(c);
        return NULL;
    }
    cf_design_taps(c->taps);
    for (int k = 0; k < CF_SPS; k++) {
        double a = 2.0 * M_PI * (double)k / (double)CF_SPS;
        c->tp_re[k] =  cos(a);
        c->tp_im[k] = -sin(a);
    }
    return c;
}

void cf_ctx_free(cf_ctx_t* c)
{
    if (!c) return;
    free(c->hi_re);  free(c->hi_im);
    free(c->mix_re); free(c->mix_im);
    free(c->dec_re); free(c->dec_im);
    free(c->g_re);   free(c->g_im);
    free(c->acc_re); free(c->acc_im);
    free(c);
}

/* Prepare the mixing-phase tables for a carrier: exp(-j w i), w = 2 pi carrier / 12000, i = 512 q + r. */
static void cf_set_carrier(cf_ctx_t* c, double carrier_hz)
{
    const double w = 2.0 * M_PI * carrier_hz / (double)CF_SAMPLE_RATE_HZ;
    for (int r = 0; r < CF_TONE_TABLE; r++) {
        c->lo_re[r] =  cos(w * (double)r);
        c->lo_im[r] = -sin(w * (double)r);
    }
    const int nhi = c->n / CF_TONE_TABLE + 2;
    for (int q = 0; q < nhi; q++) {
        double a = w * (double)CF_TONE_TABLE * (double)q;
        c->hi_re[q] =  cos(a);
        c->hi_im[q] = -sin(a);
    }
}

/* Decimated baseband bb[m] for m in [m0, m1) (clipped to the stream): mix to baseband at the current carrier, lowpass, decimate.
 * out[m] = sum_{u=-30}^{30} taps[30+u] mixed[6m+u], zero outside the PCM: what the reference's np.convolve(...,'same')[::6] gives
 * (the taps are symmetric). Samples outside the clipped range keep whatever they held and must not be read. */
static void cf_downconv_range(cf_ctx_t* c, const float* pcm, long m0, long m1)
{
    if (m0 < 0) m0 = 0;
    if (m1 > c->nd) m1 = c->nd;
    if (m1 <= m0) return;
    long raw_lo = (long)CF_DECIM * m0 - CF_LP_HALF;
    long raw_hi = (long)CF_DECIM * (m1 - 1) + CF_LP_HALF + 1;      /* exclusive */
    if (raw_lo < 0) raw_lo = 0;
    if (raw_hi > c->n) raw_hi = c->n;
    for (long i = raw_lo; i < raw_hi; i++) {
        const int    q = (int)(i >> 9), r = (int)(i & (CF_TONE_TABLE - 1));
        const double cr = c->hi_re[q] * c->lo_re[r] - c->hi_im[q] * c->lo_im[r];
        const double ci = c->hi_re[q] * c->lo_im[r] + c->hi_im[q] * c->lo_re[r];
        const double x  = (double)pcm[i];
        c->mix_re[i] = x * cr;
        c->mix_im[i] = x * ci;
    }
    for (long m = m0; m < m1; m++) {
        const long centre = (long)CF_DECIM * m;
        double ar = 0.0, ai = 0.0;
        for (int u = -CF_LP_HALF; u <= CF_LP_HALF; u++) {
            long k = centre + u;
            if (k < 0 || k >= c->n) continue;
            const double t = c->taps[CF_LP_HALF + u];
            ar += t * c->mix_re[k];
            ai += t * c->mix_im[k];
        }
        c->dec_re[m] = ar;
        c->dec_im[m] = ai;
    }
}

/* The decimated range one Costas block's objective can touch: from the first window of its first symbol to the last window's end. */
static void cf_block_region(long s0, int block, long* lo, long* hi)
{
    *lo = s0 + (long)CF_SPS * kCostasStart[block] - CF_WIN_PAD;
    /* the last symbol's 800-sample span: its start s0 + 320 p - 240, plus CF_PFX_LEN (exclusive end) */
    *hi = s0 + (long)CF_SPS * (kCostasStart[block] + CF_BLOCK_SYMBOLS - 1) - CF_WIN_PAD + CF_PFX_LEN;
}

/* Downconvert the three Costas blocks' regions at the current carrier. */
static void cf_downconv_sync_regions(cf_ctx_t* c, const float* pcm, long s0)
{
    for (int b = 0; b < CF_BLOCKS; b++) {
        long lo, hi;
        cf_block_region(s0, b, &lo, &hi);
        cf_downconv_range(c, pcm, lo, hi);
    }
}

static long cf_posmod(long a, long m)
{
    long r = a % m;
    return r < 0 ? r + m : r;
}

/*
 * The fine-sync objective surface, accumulated into acc[df * 49 + dt] as the COMPLEX sum over the 21 Costas symbols (the caller
 * takes the magnitude). dec_* must hold the baseband for the three block regions of s0. SHORTCUT S1: see the file header.
 */
static void cf_surface_accumulate(cf_ctx_t* c, long s0)
{
    memset(c->acc_re, 0, (size_t)CF_NDF * CF_NDT * sizeof(double));
    memset(c->acc_im, 0, (size_t)CF_NDF * CF_NDT * sizeof(double));

    for (int b = 0; b < CF_BLOCKS; b++) {
        long rlo, rhi;
        cf_block_region(s0, b, &rlo, &rhi);
        long a = rlo < 0 ? 0 : rlo;                       /* clipped to the stream: bb is zero outside it */
        long e = rhi > c->nd ? c->nd : rhi;
        if (e <= a) continue;

        for (int d = 0; d < CF_NDF; d++) {
            const double df  = (double)(d - CF_NDF / 2) / 10.0;                 /* DF_GRID: -2.0 .. +2.0 */
            const double dph = 2.0 * M_PI * df / (double)CF_RATE_HZ;
            const double sr = cos(dph), si = -sin(dph);                            /* the per-sample step cis(-dph) */
            double pr = 1.0, pi_ = 0.0;
            for (long i = a; i < e; i++) {
                if (((i - a) % CF_GRAY_RESEED) == 0) {                              /* direct phase every 128 samples */
                    pr =  cos(dph * (double)i);
                    pi_ = -sin(dph * (double)i);
                }
                const double xr = c->dec_re[i], xi = c->dec_im[i];
                c->g_re[i - a] = xr * pr - xi * pi_;
                c->g_im[i - a] = xr * pi_ + xi * pr;
                const double nr = pr * sr - pi_ * si;
                pi_ = pr * si + pi_ * sr;
                pr = nr;
            }

            for (int q = 0; q < CF_BLOCK_SYMBOLS; q++) {
                const int  p    = kCostasStart[b] + q;
                const int  tone = kCostas[q];
                const long lop  = s0 + (long)CF_SPS * p - CF_WIN_PAD;
                c->p_re[0] = 0.0; c->p_im[0] = 0.0;
                for (int j = 0; j < CF_PFX_LEN; j++) {
                    const long i = lop + j;
                    double hr = 0.0, hi = 0.0;
                    if (i >= a && i < e) {
                        const int k = (int)((tone * cf_posmod(i, CF_SPS)) % CF_SPS);
                        const double gr = c->g_re[i - a], gi = c->g_im[i - a];
                        hr = gr * c->tp_re[k] - gi * c->tp_im[k];
                        hi = gr * c->tp_im[k] + gi * c->tp_re[k];
                    }
                    c->p_re[j + 1] = c->p_re[j] + hr;
                    c->p_im[j + 1] = c->p_im[j] + hi;
                }
                for (int kk = 0; kk < CF_NDT; kk++) {
                    const int j0 = CF_DT_STEP_SAMPLES * kk;
                    const double wr = c->p_re[j0 + CF_SPS] - c->p_re[j0];
                    const double wi = c->p_im[j0 + CF_SPS] - c->p_im[j0];
                    /* the constant exp(+j 2 pi tone s_k / 320), s_k = s0 + 10 (kk - 24) */
                    const long sk = s0 + (long)CF_DT_STEP_SAMPLES * (kk - CF_NDT / 2);
                    const int  ci = (int)((tone * cf_posmod(sk, CF_SPS)) % CF_SPS);
                    const double cr = c->tp_re[ci], cim = -c->tp_im[ci];
                    c->acc_re[d * CF_NDT + kk] += cr * wr - cim * wi;
                    c->acc_im[d * CF_NDT + kk] += cr * wi + cim * wr;
                }
            }
        }
    }
}

/* argmax of |acc| (first maximum, df-major) and the peak. */
static void cf_surface_argmax(const cf_ctx_t* c, int* idf, int* idt, double* peak)
{
    double best = -1.0;
    int    bi = 0;
    for (int i = 0; i < CF_NDF * CF_NDT; i++) {
        const double v = c->acc_re[i] * c->acc_re[i] + c->acc_im[i] * c->acc_im[i];
        if (v > best) { best = v; bi = i; }
    }
    *idf = bi / CF_NDT;
    *idt = bi % CF_NDT;
    *peak = sqrt(best);
}

static long cf_symbol_start(double t0)
{
    return (long)nearbyint(t0 * (double)CF_RATE_HZ) + CF_TIME_ORIGIN_CORRECTION_SAMPLES_2K;
}

void cf_estimate(cf_ctx_t* c, const float* pcm, double f0, double t0, cf_estimate_t* est)
{
    const long s0 = cf_symbol_start(t0);
    cf_set_carrier(c, f0);
    cf_downconv_sync_regions(c, pcm, s0);
    cf_surface_accumulate(c, s0);
    int idf, idt; double peak;
    cf_surface_argmax(c, &idf, &idt, &peak);
    est->est_df_hz = (double)(idf - CF_NDF / 2) / 10.0;
    est->dt_step   = idt - CF_NDT / 2;
    est->est_dt_s  = (double)est->dt_step * CF_DT_STEP_S;
    est->peak      = peak;
    est->edge      = (idf == 0 || idf == CF_NDF - 1 || idt == 0 || idt == CF_NDT - 1) ? 1 : 0;
}

double cf_f1b_db(cf_ctx_t* c, const float* pcm, double f0, double t0, double anchor_peak, int* n_refs)
{
    const long s0 = cf_symbol_start(t0);
    double peaks[CF_REF_COUNT];
    int    nref = 0;
    for (int k = 0; k < 12; k++) {
        for (int sgn = -1; sgn <= 1; sgn += 2) {
            const double f = f0 + (double)sgn * (CF_REF_FIRST_HZ + CF_REF_STEP_HZ * (double)k);
            if (!(f >= CF_REF_MIN_HZ && f <= CF_REF_MAX_HZ)) continue;
            cf_set_carrier(c, f);
            cf_downconv_sync_regions(c, pcm, s0);
            cf_surface_accumulate(c, s0);
            int idf, idt; double peak;
            cf_surface_argmax(c, &idf, &idt, &peak);
            peaks[nref++] = peak;
        }
    }
    if (n_refs) *n_refs = nref;
    if (nref == 0) return INFINITY;                       /* the reference: median of [nan] is nan, "ref > 0" is False -> inf */
    for (int i = 1; i < nref; i++) {                      /* insertion sort for the median */
        double v = peaks[i]; int j = i - 1;
        while (j >= 0 && peaks[j] > v) { peaks[j + 1] = peaks[j]; j--; }
        peaks[j + 1] = v;
    }
    const double ref = (nref % 2 == 1) ? peaks[nref / 2] : 0.5 * (peaks[nref / 2 - 1] + peaks[nref / 2]);
    if (!(ref > 0.0)) return INFINITY;
    return 20.0 * log10(anchor_peak / ref);
}

/* ---- the V3 coherent LLRs ------------------------------------------------------------------------------------------------- */

static double cf_max4(double a, double b, double cc, double d)
{
    double m = a > b ? a : b;
    if (cc > m) m = cc;
    if (d > m) m = d;
    return m;
}

/* scores by TONE -> the three Gray bit max-log LLRs (decode.c's max4 structure, as _gray_bit_llrs). */
static void cf_gray_bit_llrs(const double* by_tone, double out[3])
{
    double s[CF_TONES];
    for (int j = 0; j < CF_TONES; j++) s[j] = by_tone[kGrayMap[j]];
    out[0] = cf_max4(s[4], s[5], s[6], s[7]) - cf_max4(s[0], s[1], s[2], s[3]);
    out[1] = cf_max4(s[2], s[3], s[6], s[7]) - cf_max4(s[0], s[1], s[4], s[5]);
    out[2] = cf_max4(s[1], s[3], s[5], s[7]) - cf_max4(s[0], s[2], s[4], s[6]);
}

void cf_v3_llrs(cf_ctx_t* c, const float* pcm, double f0, double t0, const cf_estimate_t* est, double out174[CF_N_LLR])
{
    /* The reference: extract_variants(pcm, anchor_f, anchor_dt_for_step(anchor_t, dt_step), df_hz = est_df), V3.
     * carrier = f0 + est_df; symbol-0 start = round(t0 x 2000) + 10 dt_step - 320. */
    const long start = cf_symbol_start(t0) + (long)CF_DT_STEP_SAMPLES * est->dt_step;
    cf_set_carrier(c, f0 + est->est_df_hz);
    cf_downconv_range(c, pcm, start, start + (long)CF_NSYM * CF_SPS);

    /* X[p][tone] = sum_n bb[start + 320 p + n] exp(-j 2 pi n tone / 320), zero outside the stream. */
    for (int p = 0; p < CF_NSYM; p++) {
        const long lo = start + (long)CF_SPS * p;
        for (int t = 0; t < CF_TONES; t++) {
            double ar = 0.0, ai = 0.0;
            for (int n = 0; n < CF_SPS; n++) {
                const long m = lo + n;
                if (m < 0 || m >= c->nd) continue;
                const int k = (n * t) % CF_SPS;
                ar += c->dec_re[m] * c->tp_re[k] - c->dec_im[m] * c->tp_im[k];
                ai += c->dec_re[m] * c->tp_im[k] + c->dec_im[m] * c->tp_re[k];
            }
            c->x_re[p * CF_TONES + t] = ar;
            c->x_im[p * CF_TONES + t] = ai;
        }
    }

    memset(out174, 0, CF_N_LLR * sizeof(double));
    for (int k = 0; k < CF_NDATA; k++) {
        const int sym = k + (k < 29 ? 7 : 14);
        const int b0  = 3 * k;
        double by_tone[CF_TONES], l[3];

        for (int t = 0; t < CF_TONES; t++) {
            const double re = c->x_re[sym * CF_TONES + t], im = c->x_im[sym * CF_TONES + t];
            by_tone[t] = re * re + im * im;
        }
        cf_gray_bit_llrs(by_tone, l);
        out174[b0] = l[0]; out174[b0 + 1] = l[1]; out174[b0 + 2] = l[2];

        /* order 2: every raw-adjacent pair containing the symbol, max-log over the other member's 8 tones */
        for (int s2 = 0; s2 < 2; s2++) {
            const int other = (s2 == 0) ? sym - 1 : sym + 1;
            if (other < 0 || other >= CF_NSYM) continue;
            for (int st = 0; st < CF_TONES; st++) {
                double best = -1.0;
                for (int ot = 0; ot < CF_TONES; ot++) {
                    const double re = c->x_re[sym * CF_TONES + st] + c->x_re[other * CF_TONES + ot];
                    const double im = c->x_im[sym * CF_TONES + st] + c->x_im[other * CF_TONES + ot];
                    const double v = re * re + im * im;
                    if (v > best) best = v;
                }
                by_tone[st] = best;
            }
            cf_gray_bit_llrs(by_tone, l);
            out174[b0] += l[0]; out174[b0 + 1] += l[1]; out174[b0 + 2] += l[2];
        }

        /* order 3: the three raw-adjacent triples containing the symbol */
        for (int pos = 2; pos >= 0; pos--) {
            const int a = sym - pos, bb = a + 1, cc = a + 2;     /* self sits at position `pos` of (a, bb, cc) */
            if (a < 0 || cc >= CF_NSYM) continue;
            for (int st = 0; st < CF_TONES; st++) by_tone[st] = -1.0;
            for (int ta = 0; ta < CF_TONES; ta++) {
                for (int tb = 0; tb < CF_TONES; tb++) {
                    const double rab = c->x_re[a * CF_TONES + ta] + c->x_re[bb * CF_TONES + tb];
                    const double iab = c->x_im[a * CF_TONES + ta] + c->x_im[bb * CF_TONES + tb];
                    for (int tc = 0; tc < CF_TONES; tc++) {
                        const double re = rab + c->x_re[cc * CF_TONES + tc];
                        const double im = iab + c->x_im[cc * CF_TONES + tc];
                        const double v = re * re + im * im;
                        const int si = (pos == 0) ? ta : (pos == 1) ? tb : tc;
                        if (v > by_tone[si]) by_tone[si] = v;
                    }
                }
            }
            cf_gray_bit_llrs(by_tone, l);
            out174[b0] += l[0]; out174[b0 + 1] += l[1]; out174[b0 + 2] += l[2];
        }
    }
}

/* ---- the coherent SNR (Stage 2, shim 20260068) --------------------------------------------------------------------------- */

double cf_snr_db(const cf_ctx_t* c, const uint8_t tones[CF_NSYM])
{
    /* Valid after cf_v3_llrs on the same context: x_re/x_im then hold the 79 x 8 tone amplitudes at the estimate. The selected
     * tone's mean power is S + N, every other tone's is N (one 6.25 Hz bin of noise), so S/N = (sel - oth) / oth, and the
     * 2500 Hz reference converts the bin noise bandwidth: SNR = (S/N) x (6.25 / 2500). */
    double sel = 0.0, oth = 0.0;
    for (int p = 0; p < CF_NSYM; p++) {
        for (int t = 0; t < CF_TONES; t++) {
            const double re = c->x_re[p * CF_TONES + t], im = c->x_im[p * CF_TONES + t];
            const double pw = re * re + im * im;
            if (t == (int)tones[p]) sel += pw; else oth += pw;
        }
    }
    sel /= (double)CF_NSYM;
    oth /= (double)(CF_NSYM * (CF_TONES - 1));
    if (!(oth > 0.0)) return (double)NAN;
    const double sig = sel - oth;
    if (!(sig > 0.0)) return CF_SNR_FLOOR_DB;
    const double snr = 10.0 * log10(sig / oth) + CF_SNR_BIN_TO_2500_DB;
    return snr < CF_SNR_FLOOR_DB ? CF_SNR_FLOOR_DB : snr;
}

/* ---- COH-MULTISET: the four further bit-metric sets (shim 20260071) ---------------------------------------------------------- */

/* The raw symbol index of data symbol k (0..57): the two halves of 29 sit after the first and the second Costas block. */
static int cf_data_sym(int k) { return k + (k < CF_HALF ? 7 : 14); }

/* The value of the three Gray bits of ONE group member from by_j[j], the best score with that member at Gray index j (the maximum
 * over the other members' hypotheses). bit 2 of j first: out = max over j with the bit 1 minus max over j with the bit 0. */
static void cf_by_j_bits(const double by_j[CF_TONES], double out[3])
{
    out[0] = cf_max4(by_j[4], by_j[5], by_j[6], by_j[7]) - cf_max4(by_j[0], by_j[1], by_j[2], by_j[3]);
    out[1] = cf_max4(by_j[2], by_j[3], by_j[6], by_j[7]) - cf_max4(by_j[0], by_j[1], by_j[4], by_j[5]);
    out[2] = cf_max4(by_j[1], by_j[3], by_j[5], by_j[7]) - cf_max4(by_j[0], by_j[2], by_j[4], by_j[6]);
}

int cf_multiset_groups(int group_size, int first_k[CF_MS_MAX_GROUPS], int n_syms[CF_MS_MAX_GROUPS])
{
    if (group_size != 2 && group_size != 3) return -1;
    int ng = 0;
    for (int h = 0; h < 2; h++) {
        int k = h * CF_HALF;
        const int end = (h + 1) * CF_HALF;
        while (k < end) {
            const int n = (end - k < group_size) ? (end - k) : group_size;
            first_k[ng] = k;
            n_syms[ng]  = n;
            ng++;
            k += n;
        }
    }
    return ng;
}

/* One group of n (1..3) data symbols starting at data index k0: the 3n values in (member, bit2, bit1, bit0) order. The score of a
 * hypothesis is the MAGNITUDE |sum of X[sym_p][tone_p]|; each member's tone is gray[j] for its Gray index j. */
static void cf_group_values(const cf_ctx_t* c, int k0, int n, const int gray[CF_TONES], double out[9])
{
    double by_j[3][CF_TONES];
    int sym[3];
    for (int p = 0; p < n; p++) {
        sym[p] = cf_data_sym(k0 + p);
        for (int j = 0; j < CF_TONES; j++) by_j[p][j] = -1.0;       /* every score is >= 0, so -1 is below any real one */
    }
    for (int j0 = 0; j0 < CF_TONES; j0++) {
        const double r0 = c->x_re[sym[0] * CF_TONES + gray[j0]], i0 = c->x_im[sym[0] * CF_TONES + gray[j0]];
        if (n == 1) {
            const double v = hypot(r0, i0);
            if (v > by_j[0][j0]) by_j[0][j0] = v;
            continue;
        }
        for (int j1 = 0; j1 < CF_TONES; j1++) {
            const double r01 = r0 + c->x_re[sym[1] * CF_TONES + gray[j1]], i01 = i0 + c->x_im[sym[1] * CF_TONES + gray[j1]];
            if (n == 2) {
                const double v = hypot(r01, i01);
                if (v > by_j[0][j0]) by_j[0][j0] = v;
                if (v > by_j[1][j1]) by_j[1][j1] = v;
                continue;
            }
            for (int j2 = 0; j2 < CF_TONES; j2++) {
                const double v = hypot(r01 + c->x_re[sym[2] * CF_TONES + gray[j2]], i01 + c->x_im[sym[2] * CF_TONES + gray[j2]]);
                if (v > by_j[0][j0]) by_j[0][j0] = v;
                if (v > by_j[1][j1]) by_j[1][j1] = v;
                if (v > by_j[2][j2]) by_j[2][j2] = v;
            }
        }
    }
    for (int p = 0; p < n; p++) cf_by_j_bits(by_j[p], out + 3 * p);
}

void cf_multiset_llrs_gray(const cf_ctx_t* c, int set, const int gray[CF_TONES], double out174[CF_N_LLR])
{
    memset(out174, 0, CF_N_LLR * sizeof(double));
    if (set == CF_SET_C1) {
        /* order 1 on POWER at the production Gray map (the V3 extractor's own first term, unchanged) */
        for (int k = 0; k < CF_NDATA; k++) {
            const int sym = cf_data_sym(k);
            double by_tone[CF_TONES];
            for (int t = 0; t < CF_TONES; t++) {
                const double re = c->x_re[sym * CF_TONES + t], im = c->x_im[sym * CF_TONES + t];
                by_tone[t] = re * re + im * im;
            }
            cf_gray_bit_llrs(by_tone, out174 + 3 * k);
        }
    } else if (set == CF_SET_J2 || set == CF_SET_J3) {
        int first[CF_MS_MAX_GROUPS], len[CF_MS_MAX_GROUPS];
        const int ng = cf_multiset_groups(set == CF_SET_J2 ? 2 : 3, first, len);
        for (int g = 0; g < ng; g++) cf_group_values(c, first[g], len[g], gray, out174 + 3 * first[g]);
    } else if (set == CF_SET_N1) {
        /* order 1 on magnitudes, each bit divided by the larger of its two maxima (0 when both are 0) */
        for (int k = 0; k < CF_NDATA; k++) {
            const int sym = cf_data_sym(k);
            double by_j[CF_TONES];
            for (int j = 0; j < CF_TONES; j++) by_j[j] = hypot(c->x_re[sym * CF_TONES + gray[j]], c->x_im[sym * CF_TONES + gray[j]]);
            static const int kBitJ[3][2][4] = {      /* [bit][value][4 Gray indices]: bit 2, 1, 0 of j */
                { { 0, 1, 2, 3 }, { 4, 5, 6, 7 } }, { { 0, 1, 4, 5 }, { 2, 3, 6, 7 } }, { { 0, 2, 4, 6 }, { 1, 3, 5, 7 } } };
            for (int b = 0; b < 3; b++) {
                const double m0 = cf_max4(by_j[kBitJ[b][0][0]], by_j[kBitJ[b][0][1]], by_j[kBitJ[b][0][2]], by_j[kBitJ[b][0][3]]);
                const double m1 = cf_max4(by_j[kBitJ[b][1][0]], by_j[kBitJ[b][1][1]], by_j[kBitJ[b][1][2]], by_j[kBitJ[b][1][3]]);
                const double den = m1 > m0 ? m1 : m0;
                out174[3 * k + b] = (den == 0.0) ? 0.0 : (m1 - m0) / den;
            }
        }
    }
}

void cf_multiset_llrs(const cf_ctx_t* c, int set, double out174[CF_N_LLR])
{
    cf_multiset_llrs_gray(c, set, kGrayMap, out174);
}

