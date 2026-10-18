/*
 * freq_search_selftest.c -- TEST-ONLY. B2 (sub-feas-speed-redesign tasks.md 15.4, design.md D11): the pruned freq_search
 * against the REFERENCE full-FFT search, on synthetic inputs. White-box: it #includes the product source so it can call the
 * static freq_search directly; the product file is NOT edited and no export is added. Build and run with
 * run_freq_search_selftest.py (MSVC cl on Windows, cc/gcc/clang elsewhere). Exit code 0 = every assertion held.
 *
 * freq_search_reference below is the Stage A function, copied VERBATIM (native/ft8_lib_vendor/subfeas/subfeas_fit.c at
 * origin/main e2fdd446, 'static void freq_search'), renamed. It is the oracle.
 *
 * What it asserts (the handoff's action 4):
 *   A. one tone at a known offset, across the FULL +-2.0 Hz range including both edges and 0, at bin centres, between
 *      bins and just outside the range, without noise and with noise at a fixed seed: the pruned search returns the
 *      SAME bin (frequency) as the reference;
 *   B. a chirp (the step-2 case: residual drift after mixing): same bin;
 *   C. two tones whose magnitudes differ by 1 % and by 0.1 %: both pick the larger, and agree with the reference;
 *   D. a float-level near-tie through the whole pipeline returns one of the two bins (descriptive; a decimated, FFT'd,
 *      droop-corrected signal never produces an EXACTLY equal pair, so this cannot test the tie-break);
 *   D2. the tie-break, BINDING: argmax_in_index_order (the product's scan, a separate function) is driven with hand-built
 *      magnitude arrays holding exact ties (+k and -k, two positive bins, two negative bins, 0 and +-1, every bin equal) and
 *      must pick what the reference's scan loop (Stage A's, verbatim) picks;
 *   F.  a product length that is not a multiple of 64 is handled like the reference;
 *   E. the cancel flag: a set flag returns -4 promptly from the public entry and from fine_fit_with_drift.
 * Descriptive output: how often the two disagree for gaps of 1e-4 and 1e-5 (the method's documented error bound), and the
 * time per call of each search.
 */
#include "../../../native/ft8_lib_vendor/subfeas/subfeas_fit.c"

#include <stdio.h>
#include <time.h>

/* ---- the oracle: Stage A freq_search, verbatim ------------------------------------------------------------------ */
static void freq_search_reference(
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

/* ---- deterministic noise ---------------------------------------------------------------------------------------- */
static unsigned long long g_lcg;
static double rnd_uniform(void)
{
    g_lcg = g_lcg * 6364136223846793005ULL + 1442695040888963407ULL;
    return (double)(g_lcg >> 11) / 9007199254740992.0;
}
static double rnd_gauss(void)
{
    double u1 = rnd_uniform() + 1e-300, u2 = rnd_uniform();
    return sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
}

static cf32* g_mixed;

/* one complex tone of unit amplitude at f0 Hz, optional linear chirp, optional gaussian noise of sigma per component */
static void add_tone(double amp, double f0_hz, double chirp_hz_per_s, double phase0)
{
    int i;
    for (i = 0; i < N_TX; i++) {
        double t = (double)i / FS;
        double ph = 2.0 * M_PI * (f0_hz * t + 0.5 * chirp_hz_per_s * t * t) + phase0;
        g_mixed[i].r += (float)(amp * cos(ph));
        g_mixed[i].i += (float)(amp * sin(ph));
    }
}
static void clear_mixed(void) { memset(g_mixed, 0, sizeof(cf32) * N_TX); }
static void add_noise(double sigma)
{
    int i;
    for (i = 0; i < N_TX; i++) { g_mixed[i].r += (float)(sigma * rnd_gauss()); g_mixed[i].i += (float)(sigma * rnd_gauss()); }
}

static int g_fail = 0;
#define CHECK(cond, ...) do { if (!(cond)) { g_fail++; printf("FAIL: "); printf(__VA_ARGS__); printf("\n"); } } while (0)

static double now_us(void)
{
    return (double)clock() * 1e6 / CLOCKS_PER_SEC;
}

int main(void)
{
    workspace_t ws;
    double bin = FS / (double)N_FFT;
    int total = 0, mismatch = 0, noisy_total = 0, noisy_mismatch = 0;
    double f0;

    if (!workspace_alloc(&ws)) { printf("FAIL: workspace_alloc\n"); return 2; }
    g_mixed = (cf32*)malloc(sizeof(cf32) * N_TX);
    if (!g_mixed) return 2;
    g_lcg = 20261003ULL;

    printf("bin_hz=%.9f  kmax at 2.0 Hz: %d\n", bin, (int)floor(SUBFEAS_DF_RANGE_HZ / bin));

    /* ---- A. one tone across the full range, edges, 0, bin centres, between bins, just outside ------------------ */
    {
        const double sigmas[] = { 0.0, 3.0, 30.0 };
        int si;
        for (si = 0; si < 3; si++) {
            /* offsets: every 0.0100 Hz from -2.30 to +2.30, plus each edge bin centre +-0.4 bin, 0, and +-2.0 */
            double extra[] = { 0.0, 43 * bin, -43 * bin, 43 * bin + 0.4 * bin, -43 * bin - 0.4 * bin, 2.0, -2.0,
                               1.0 * bin, -1.0 * bin, 0.5 * bin, -0.5 * bin, 44 * bin, -44 * bin };
            int n = (int)(sizeof(extra) / sizeof(extra[0]));
            int e;
            long steps = 460;
            long s;
            for (s = 0; s <= steps + n; s++) {
                double r_pruned, v_pruned, r_ref, v_ref;
                f0 = (s <= steps) ? -2.30 + 0.01 * (double)s : extra[s - steps - 1];
                clear_mixed();
                add_tone(1.0, f0, 0.0, 0.7 * (double)s);
                if (sigmas[si] > 0.0) add_noise(sigmas[si]);
                freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r_pruned, &v_pruned);
                freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r_ref, &v_ref);
                total++;
                if (sigmas[si] > 0.0) noisy_total++;
                if (r_pruned != r_ref) {
                    mismatch++;
                    if (sigmas[si] > 0.0) noisy_mismatch++;
                    CHECK(0, "A: tone f0=%.5f sigma=%.0f: pruned %.6f vs reference %.6f", f0, sigmas[si], r_pruned, r_ref);
                }
                /* the magnitudes agree to the documented bound (1e-3 is a generous multiple of the 1.1e-4 alias bound + float) */
                if (v_ref > 0.0 && fabs(v_pruned / v_ref - 1.0) > 2e-3 && sigmas[si] == 0.0)
                    CHECK(0, "A: tone f0=%.5f: magnitude ratio %.6f", f0, v_pruned / v_ref);
            }
            (void)e;
        }
    }
    printf("A: %d tones (noise-free and noisy), %d bin disagreements (%d of them with noise)\n", total, mismatch, noisy_mismatch);

    /* ---- B. chirps (the step-2 case) ---------------------------------------------------------------------------- */
    {
        int b_total = 0, b_mismatch = 0;
        double chirps[] = { -0.10, -0.05, 0.0, 0.03, 0.10 };
        int c;
        for (c = 0; c < 5; c++) {
            double fstart;
            for (fstart = -1.9; fstart <= 1.9001; fstart += 0.13) {
                double r1, v1, r2, v2;
                clear_mixed();
                add_tone(1.0, fstart, chirps[c], 0.3);
                add_noise(3.0);
                freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r1, &v1);
                freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r2, &v2);
                b_total++;
                if (r1 != r2) { b_mismatch++; CHECK(0, "B: chirp %.2f Hz/s from %.3f: pruned %.6f vs reference %.6f", chirps[c], fstart, r1, r2); }
            }
        }
        printf("B: %d chirps, %d bin disagreements\n", b_total, b_mismatch);
    }

    /* ---- C. two tones whose magnitudes differ by 1 % and 0.1 %, in both orders ------------------------------- */
    {
        double gaps[] = { 0.01, 0.001 };
        int g, order, c_total = 0, c_mismatch = 0;
        for (g = 0; g < 2; g++)
            for (order = 0; order < 2; order++) {
                double r1, v1, r2, v2;
                double fa = 7 * bin, fb = -7 * bin;                    /* exact bin centres, one on each side of 0 */
                double a_amp = order ? 1.0 + gaps[g] : 1.0, b_amp = order ? 1.0 : 1.0 + gaps[g];
                clear_mixed();
                add_tone(a_amp, fa, 0.0, 0.1);
                add_tone(b_amp, fb, 0.0, 1.3);
                freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r1, &v1);
                freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r2, &v2);
                c_total++;
                if (r1 != r2) { c_mismatch++; CHECK(0, "C: gap %.4f order %d: pruned %.6f vs reference %.6f", gaps[g], order, r1, r2); }
                CHECK(r1 == (order ? fa : fb), "C: gap %.4f order %d: expected the larger tone's bin, got %.6f", gaps[g], order, r1);
            }
        printf("C: %d two-tone cases (1%% and 0.1%% gaps), %d disagreements\n", c_total, c_mismatch);
    }

    /* ---- C'. descriptive: gaps at or below the method's error bound -------------------------------------------- */
    {
        double gaps[] = { 1e-4, 1e-5 };
        int g, k, n = 40;
        for (g = 0; g < 2; g++) {
            int dis = 0;
            for (k = 0; k < n; k++) {
                double r1, v1, r2, v2, fa = (3 + k % 17) * bin, fb = -(3 + (k * 5) % 17) * bin;
                clear_mixed();
                add_tone(1.0 + gaps[g], fa, 0.0, 0.1 * k);
                add_tone(1.0, fb, 0.0, 1.3 + 0.2 * k);
                freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r1, &v1);
                freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r2, &v2);
                if (r1 != r2) dis++;
            }
            printf("C': gap %.0e: pruned and reference pick a different bin in %d of %d cases (descriptive: below the documented bound)\n", gaps[g], dis, n);
        }
    }

    /* ---- D. the tie-break: an exactly equal pair, the reference scans +k before -k ------------------------------- */
    {
        double r1, v1, r2, v2;
        clear_mixed();
        add_tone(1.0, 9 * bin, 0.0, 0.0);
        add_tone(1.0, -9 * bin, 0.0, 0.0);
        freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r1, &v1);
        freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r2, &v2);
        CHECK(r1 == 9 * bin || r1 == -9 * bin, "D: the pruned result %.6f is neither tone", r1);
        CHECK(r2 == 9 * bin || r2 == -9 * bin, "D: the reference result %.6f is neither tone", r2);
        printf("D: exactly equal pair at +-9 bins: reference -> %+.0f bins, pruned -> %+.0f bins (a float-level tie: either is legal; the scan order is the reference's)\n",
               r2 / bin, r1 / bin);
        /* the tie-break is the SCAN ORDER; prove it on the index order itself: with a real cosine the spectrum is exactly
           conjugate-symmetric, so the magnitudes at +k and -k are equal in exact arithmetic */
        clear_mixed();
        { int i; for (i = 0; i < N_TX; i++) { g_mixed[i].r = (float)cos(2.0 * M_PI * 12 * bin * (double)i / FS); g_mixed[i].i = 0.0f; } }
        freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r1, &v1);
        freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r2, &v2);
        printf("D: real cosine at 12 bins (conjugate-symmetric): reference -> %+.0f, pruned -> %+.0f\n", r2 / bin, r1 / bin);
        CHECK(fabs(r1) == 12 * bin && fabs(r2) == 12 * bin, "D: the cosine's peak must be at +-12 bins");
    }

    /* ---- D2. the tie-break, BINDING: drive the argmax helper with exactly equal magnitudes ----------------------- */
    /* A decimated, FFT'd, droop-corrected signal never yields an exactly equal pair, so D above cannot fire. The scan is
       therefore a helper that takes magnitudes (argmax_in_index_order), and here it is compared with the REFERENCE's scan
       loop (Stage A's, verbatim, over FFT indices) on hand-built magnitude arrays with exact ties. */
    {
        enum { KMAX = 43 };
        static double full[N_FFT];
        double mag[2 * KMAX + 1];
        struct { const char* name; int n; int bins[6]; } cases[] = {
            { "+9 and -9",        2, { 9, -9 } },
            { "-9 and +9",        2, { -9, 9 } },
            { "+3 and +20",       2, { 3, 20 } },
            { "-5 and -30",       2, { -5, -30 } },
            { "0, +1 and -1",     3, { 0, 1, -1 } },
            { "+43 and -43",      2, { 43, -43 } },
            { "-1 and +43",       2, { -1, 43 } },
            { "-43, -1, +1, +43", 4, { -43, -1, 1, 43 } },
        };
        int c, i, d2_total = 0, d2_bad = 0;
        for (c = 0; c < (int)(sizeof(cases) / sizeof(cases[0])) + 2; c++) {
            double r_ref = 0.0, v_ref = -1.0, r_new, v_new;
            int idx, b;
            memset(full, 0, sizeof(full));
            if (c < (int)(sizeof(cases) / sizeof(cases[0]))) {
                for (b = 0; b < cases[c].n; b++) full[cases[c].bins[b] >= 0 ? cases[c].bins[b] : N_FFT + cases[c].bins[b]] = 5.0;
            } else if (c == (int)(sizeof(cases) / sizeof(cases[0]))) {
                for (b = -KMAX; b <= KMAX; b++) full[b >= 0 ? b : N_FFT + b] = 2.0;           /* every in-range bin equal */
            } else {
                for (b = -KMAX; b <= KMAX; b++) full[b >= 0 ? b : N_FFT + b] = 1.0 + 0.001 * (b + KMAX);   /* strictly increasing in k */
            }
            /* the reference's scan, verbatim: FFT index order, first strictly greater wins */
            for (idx = 0; idx < N_FFT; idx++) {
                double f = (idx < N_FFT / 2) ? (double)idx * bin : (double)(idx - N_FFT) * bin;
                if (fabs(f) > SUBFEAS_DF_RANGE_HZ) continue;
                if (full[idx] > v_ref) { v_ref = full[idx]; r_ref = f; }
            }
            for (i = -KMAX; i <= KMAX; i++) mag[i + KMAX] = full[i >= 0 ? i : N_FFT + i];
            argmax_in_index_order(mag, KMAX, bin, SUBFEAS_DF_RANGE_HZ, &r_new, &v_new);
            d2_total++;
            if (r_new != r_ref || v_new != v_ref) {
                d2_bad++;
                CHECK(0, "D2: case %d: helper picked %+.6f (%g), the reference scan %+.6f (%g)", c, r_new, v_new, r_ref, v_ref);
            }
        }
        printf("D2: tie-break helper vs the reference scan on %d exact-tie and ordering cases, %d disagreements\n", d2_total, d2_bad);
    }

    /* ---- F. a length that is not a multiple of 64 and a short product are handled like the reference ------------- */
    {
        int lens[] = { N_TX - 17, N_TX - 63, 64 * 1000 + 5, 64 * 10 };
        int li;
        int f_bad = 0;
        for (li = 0; li < 4; li++) {
            double r1, v1, r2, v2;
            clear_mixed();
            add_tone(1.0, -1.37, 0.0, 0.2);
            add_noise(3.0);
            freq_search(&ws, g_mixed, lens[li], SUBFEAS_DF_RANGE_HZ, &r1, &v1);
            freq_search_reference(&ws, g_mixed, lens[li], SUBFEAS_DF_RANGE_HZ, &r2, &v2);
            if (li < 2 && r1 != r2) { f_bad++; CHECK(0, "F: length %d: pruned %.6f vs reference %.6f", lens[li], r1, r2); }
            /* the two short products carry too little tone to compare bins; only that nothing crashes and a bin is returned */
            CHECK(fabs(r1) <= SUBFEAS_DF_RANGE_HZ, "F: length %d: result %.6f out of range", lens[li], r1);
        }
        printf("F: lengths off a multiple of 64 (%d, %d) agree with the reference, short products return in range, %d disagreements\n", lens[0], lens[1], f_bad);
    }

    /* ---- speed (descriptive) ---------------------------------------------------------------------------------- */
    {
        int i, reps = 20;
        double r, v, t0, t1, t2;
        clear_mixed();
        add_tone(1.0, 0.7, 0.0, 0.0);
        add_noise(30.0);
        t0 = now_us();
        for (i = 0; i < reps; i++) freq_search_reference(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r, &v);
        t1 = now_us();
        for (i = 0; i < reps; i++) freq_search(&ws, g_mixed, N_TX, SUBFEAS_DF_RANGE_HZ, &r, &v);
        t2 = now_us();
        printf("speed (descriptive, 1 thread): reference %.0f us per search, pruned %.0f us per search\n", (t1 - t0) / reps, (t2 - t1) / reps);
    }

    /* ---- E. the cancel flag --------------------------------------------------------------------------------------- */
    {
        static float re[SUBFEAS_PCM_LEN], im[SUBFEAS_PCM_LEN], shat[SUBFEAS_PCM_LEN];
        uint8_t tones[SUBFEAS_NUM_SYMBOLS];
        volatile int flag = 1;
        double dt, df, fdot, t0, t1;
        int start = 0, rc;
        cf32* rb = (cf32*)malloc(sizeof(cf32) * N_TX);
        memset(tones, 0, sizeof(tones));
        t0 = now_us();
        rc = ft8_subfeas_fit_signal(re, im, tones, 0.0f, 1500.0f, shat, &flag);
        t1 = now_us();
        CHECK(rc == -4, "E: public entry with a set flag returned %d, not -4", rc);
        CHECK(t1 - t0 < 100000.0, "E: public entry took %.0f us with a set flag", t1 - t0);
        t0 = now_us();
        rc = fine_fit_with_drift(&ws, re, im, tones, 1500.0, 0.0, &dt, &df, &fdot, &start, rb, &flag);
        t1 = now_us();
        CHECK(rc == -4, "E: fine_fit_with_drift with a set flag returned %d, not -4", rc);
        CHECK(t1 - t0 < 100000.0, "E: fine_fit_with_drift took %.0f us with a set flag (it must stop before the first search)", t1 - t0);
        printf("E: cancel flag set -> -4, %.0f us\n", t1 - t0);
        free(rb);
    }

    printf("RESULT: %s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    workspace_free(&ws);
    free(g_mixed);
    return g_fail == 0 ? 0 : 1;
}
