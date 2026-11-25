/*
 * ftz_fuzz.c -- native test harness for ftz_decode_cycle (DR-2 steps 2a to 2e): built and run under AddressSanitizer and
 * UndefinedBehaviorSanitizer by native/ftz_decoder/tests/run_asan.sh and by the CI job `native-asan`.
 *
 * PROVENANCE: OpenWSFZ-original, written 2026-11-24. No third-party code.
 *
 * What it does (the C twin of tests/OpenWSFZ.Ft8.Tests/LeanEngineNativeTests.cs):
 *   1. For every WAV path given (12 kHz mono 16-bit, e.g. the committed synth-qso-0N.wav): decode with 1, 2, 4, 2 and 1 threads from the
 *      same starting callsign-table state and require the outputs byte-identical and non-empty (determinism, thread-count independence).
 *   2. Fuzz: N runs (default 10000) on random, hard-clipped, silent and DC audio, tones, impulses, very loud finite noise and truncated /
 *      oversized buffers, at every thread count, requiring the call to return FTZ_OK with a sane result count. No crash and no sanitizer
 *      report is the pass criterion; the sanitizers abort the process on the first report.
 *   3. Non-decodable audio (NaN, infinity, a huge sample) must return FTZ_ERR_BADAUDIO, and the next call must work.
 *   4. (step 2c) The subtract-and-retry loop is ON in the determinism run (results, tiers, rounds byte-identical at every thread count) and in the
 *      fuzz; every 200th fuzz run decodes MUTATED REAL audio (the first WAV, truncated, clipped, offset or gapped) so the loop actually runs;
 *      the three accept-rule functions are checked directly.
 *   5. (step 2d) The round-0 callback (exactly once, with the round-0 count), the final residual buffer (NULL and exactly-sized, byte-identical at every thread
 *      count) and the no-tier-B flag are exercised in the determinism run and in the fuzz.
 *   6. (step 2e) The fit-skip rule is on in half the runs and in the determinism run (with and without), a simulated fit error after the first chunk of a round
 *      is injected in one run in eight (it must return FTZ_ERR_NOMEM and NO residual), and the two fit paths (reference and fast) give the same determinism digest.
 * Exit status 0 = all passed. Prints counts only.
 */
#include "../ftz_decoder.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ft8_shim.h, FT8Result (48 bytes): repeated here to keep the harness independent of the shim's header guard history. */
typedef struct { int freq_hz; float dt; int snr; char message[36]; } FT8Result;
int  ft8_hash_state_size(void);
int  ft8_hash_state_save(void* buf, int cap);
int  ft8_hash_state_restore(const void* buf, int len);

#define MAX_RESULTS 340
#define PCM_SAMPLES 180000

static uint32_t g_rng = 20261124u;
static uint32_t rnd(void) { g_rng ^= g_rng << 13; g_rng ^= g_rng >> 17; g_rng ^= g_rng << 5; return g_rng; }
static float    rndf(void) { return (float)(rnd() >> 8) / 8388608.0f - 1.0f; }   /* [-1, 1) */

static int failures = 0;
#define CHECK(cond, ...) do { if (!(cond)) { fprintf(stderr, "FAIL %s:%d: ", __FILE__, __LINE__); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); failures++; } } while (0)

static float* read_wav(const char* path, int* n_out)
{
    FILE* f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
    if (len < 44) { fclose(f); return NULL; }
    uint8_t* buf = (uint8_t*)malloc((size_t)len);
    if (!buf || fread(buf, 1, (size_t)len, f) != (size_t)len) { free(buf); fclose(f); return NULL; }
    fclose(f);
    long pos = 12; uint32_t data_len = 0; long data_pos = -1;
    while (pos + 8 <= len) {
        uint32_t sz = (uint32_t)buf[pos+4] | ((uint32_t)buf[pos+5] << 8) | ((uint32_t)buf[pos+6] << 16) | ((uint32_t)buf[pos+7] << 24);
        if (!memcmp(buf + pos, "data", 4)) { data_pos = pos + 8; data_len = sz; break; }
        pos += 8 + (long)sz + (long)(sz & 1u);
    }
    if (data_pos < 0) { free(buf); return NULL; }
    if ((long)data_len > len - data_pos) data_len = (uint32_t)(len - data_pos);
    int n = (int)(data_len / 2);
    float* pcm = (float*)malloc((size_t)(n > 0 ? n : 1) * sizeof(float));
    for (int i = 0; i < n; i++) {
        int16_t s = (int16_t)((uint16_t)buf[data_pos + 2*i] | ((uint16_t)buf[data_pos + 2*i + 1] << 8));
        pcm[i] = (float)s / 32768.0f;
    }
    free(buf);
    *n_out = n;
    return pcm;
}

/* The round-0 hand-off: counts the calls and copies what it was given (the callee must copy; the buffers are valid only during the call). */
typedef struct { int calls; int n; FT8Result res[MAX_RESULTS]; uint8_t tiers[MAX_RESULTS]; int have_tiers; } cb_probe_t;
static void round0_probe(void* ctx, int n, const void* results, const uint8_t* tiers)
{
    cb_probe_t* pr = (cb_probe_t*)ctx;
    pr->calls++;
    pr->n = n;
    if (n > 0 && n <= MAX_RESULTS) {
        memcpy(pr->res, results, sizeof(FT8Result) * (size_t)n);
        if (tiers) { memcpy(pr->tiers, tiers, (size_t)n); pr->have_tiers = 1; }
    }
}

static int g_inject = 0;     /* the test hook inject_error_round of the next call */

static int decode_full2(const float* pcm, int n, int threads, int max_cand, int flags, int budget_ms, int max_rounds, int expire_round,
                        FT8Result* out, uint8_t* tiers, uint8_t* rounds, ftz_stats_t* st, cb_probe_t* probe, float* out_residual)
{
    ftz_params_t p;
    memset(&p, 0, sizeof(p));
    p.struct_size = (int32_t)sizeof(p);
    p.threads = threads;
    p.max_candidates = max_cand;
    p.flags = flags;
    p.budget_ms = budget_ms;
    p.max_rounds = max_rounds;
    p.expire_round = expire_round;
    if (probe) { memset(probe, 0, sizeof(*probe)); p.round0_cb = round0_probe; p.round0_ctx = probe; }
    p.out_residual = out_residual;
    p.inject_error_round = g_inject;
    return ftz_decode_cycle(pcm, n, &p, out, MAX_RESULTS, tiers, rounds, st);
}

static int decode_full(const float* pcm, int n, int threads, int max_cand, int flags, int budget_ms, int max_rounds, int expire_round,
                       FT8Result* out, uint8_t* tiers, uint8_t* rounds, ftz_stats_t* st)
{
    return decode_full2(pcm, n, threads, max_cand, flags, budget_ms, max_rounds, expire_round, out, tiers, rounds, st, NULL, NULL);
}

static int decode_ex(const float* pcm, int n, int threads, int max_cand, int flags, int budget_ms, FT8Result* out, uint8_t* tiers, ftz_stats_t* st)
{
    return decode_full(pcm, n, threads, max_cand, flags, budget_ms, 0, 0, out, tiers, NULL, st);
}

/* Every tier on (tier B always runs; CQ-AP is a flag), no budget, loop off (the step-2b call). */
static int decode(const float* pcm, int n, int threads, FT8Result* out, ftz_stats_t* st)
{
    return decode_ex(pcm, n, threads, 0, FTZ_FLAG_CQ_AP, 0, out, NULL, st);
}

#define LOOP_FLAGS (FTZ_FLAG_CQ_AP | FTZ_FLAG_ROUNDS | FTZ_FLAG_RESIDUAL_UNGATED | FTZ_FLAG_SKIP_FITS)

static int determinism(const char* path)
{
    int n = 0;
    float* pcm = read_wav(path, &n);
    CHECK(pcm != NULL, "cannot read %s", path);
    if (!pcm) return 0;
    int image_size = ft8_hash_state_size();
    void* start = malloc((size_t)image_size);
    ft8_hash_state_save(start, image_size);

    static FT8Result first[MAX_RESULTS], cur[MAX_RESULTS];
    static uint8_t first_t[MAX_RESULTS], cur_t[MAX_RESULTS], first_r[MAX_RESULTS], cur_r[MAX_RESULTS];
    int first_n = -1, first_rounds = 0, first_loop_results = 0, first_has_resid = 0, first_cb_n = -1;
    static float first_resid[PCM_SAMPLES], cur_resid[PCM_SAMPLES];
    static cb_probe_t probe;
    const int threads[] = { 1, 2, 4, 2, 1 };
    for (int t = 0; t < 5; t++) {
        ft8_hash_state_restore(start, image_size);
        ftz_stats_t st;
        memset(cur, 0, sizeof(cur)); memset(cur_t, 0, sizeof(cur_t)); memset(cur_r, 0, sizeof(cur_r));
        memset(cur_resid, 0, sizeof(cur_resid));
        int rc = decode_full2(pcm, n, threads[t], 0, LOOP_FLAGS, 0, 0, 0, cur, cur_t, cur_r, &st, &probe, cur_resid);   /* the loop is ON: step 2c; callback and residual: step 2d */
        CHECK(rc >= 0, "%s threads=%d: error %d", path, threads[t], rc);
        if (rc < 0) continue;
        int r0count = 0;
        for (int i = 0; i < rc; i++) if (cur_r[i] == 0) r0count++;
        CHECK(probe.calls == 1 && probe.n == r0count, "%s threads=%d: round-0 callback called %d time(s) with %d, round 0 has %d", path, threads[t], probe.calls, probe.n, r0count);
        CHECK(probe.n == 0 || memcmp(probe.res, cur, sizeof(FT8Result) * (size_t)probe.n) == 0, "%s threads=%d: callback results differ from the returned round-0 results", path, threads[t]);
        if (first_n < 0)
        {
            first_n = rc; memcpy(first, cur, sizeof(first)); memcpy(first_t, cur_t, sizeof(first_t)); memcpy(first_r, cur_r, sizeof(first_r));
            first_rounds = st.n_rounds;
            first_has_resid = st.has_residual; first_cb_n = probe.n;
            memcpy(first_resid, cur_resid, sizeof(first_resid));
            for (int i = 0; i < rc; i++) if (cur_r[i] > 0) first_loop_results++;
            CHECK(rc > 0, "%s decoded nothing", path);
        }
        else {
            CHECK(rc == first_n, "%s threads=%d: %d results, expected %d", path, threads[t], rc, first_n);
            int m = first_n < rc ? first_n : rc;
            CHECK(memcmp(first, cur, sizeof(FT8Result) * (size_t)m) == 0, "%s threads=%d: output differs from threads=1", path, threads[t]);
            CHECK(memcmp(first_t, cur_t, (size_t)m) == 0, "%s threads=%d: tiers differ from threads=1", path, threads[t]);
            CHECK(memcmp(first_r, cur_r, (size_t)m) == 0, "%s threads=%d: rounds differ from threads=1", path, threads[t]);
            CHECK(st.n_rounds == first_rounds, "%s threads=%d: %d rounds, expected %d", path, threads[t], st.n_rounds, first_rounds);
            CHECK(st.has_residual == first_has_resid, "%s threads=%d: has_residual %d, expected %d", path, threads[t], st.has_residual, first_has_resid);
            CHECK(memcmp(first_resid, cur_resid, sizeof(first_resid)) == 0, "%s threads=%d: residual differs from threads=1", path, threads[t]);
            CHECK(probe.n == first_cb_n, "%s threads=%d: callback delivered %d, expected %d", path, threads[t], probe.n, first_cb_n);
        }
    }
    ft8_hash_state_restore(start, image_size);
    printf("determinism %s: %d results (%d from rounds 1 to 3, %d round(s) run, residual %s), identical at 1/2/4/2/1 threads\n", path, first_n, first_loop_results, first_rounds, first_has_resid ? "returned" : "none");
    free(start); free(pcm);
    return 1;
}

static void fill(float* x, int n, int kind)
{
    switch (kind) {
    case 0: memset(x, 0, sizeof(float) * (size_t)n); break;                                       /* silence */
    case 1: { float v = rndf(); for (int i = 0; i < n; i++) x[i] = v; break; }                    /* DC */
    case 2: for (int i = 0; i < n; i++) x[i] = rndf(); break;                                     /* white noise */
    case 3: for (int i = 0; i < n; i++) { float v = rndf() * 50.0f; x[i] = v > 1.0f ? 1.0f : (v < -1.0f ? -1.0f : v); } break;   /* clipped */
    case 4: { double f = 100.0 + 3000.0 * ((double)(rnd() >> 8) / 16777216.0);
              for (int i = 0; i < n; i++) { float v = (float)(3.0 * sin(2.0 * 3.14159265358979 * f * i / 12000.0)); x[i] = v > 1.0f ? 1.0f : (v < -1.0f ? -1.0f : v); } break; }   /* clipped tone */
    case 5: memset(x, 0, sizeof(float) * (size_t)n); for (int i = 0; i < n; i += 1 + (int)(rnd() % 600u)) x[i] = (rnd() & 1u) ? 1.0f : -1.0f; break;   /* impulses */
    default: for (int i = 0; i < n; i++) x[i] = rndf() * 1.0e5f; break;                          /* very loud, finite */
    }
}

/* The first WAV the determinism run read, kept for the mutated-real-audio fuzz runs. */
static float* g_real = NULL;
static int    g_real_n = 0;

/* A mutation of real audio into x (n samples); kind 0 clipped, 1 DC offset, 2 gapped (zeros), 3 plain. */
static void mutate_real(float* x, int n, int kind)
{
    for (int i = 0; i < n; i++) {
        float v = i < g_real_n ? g_real[i] : 0.0f;
        switch (kind) {
        case 0: v *= 30.0f; v = v > 1.0f ? 1.0f : (v < -1.0f ? -1.0f : v); break;
        case 1: v += 0.25f; break;
        case 2: if ((i / 12000) % 3 == 1) v = 0.0f; break;
        default: break;
        }
        x[i] = v;
    }
}

static void fuzz(int runs)
{
    const int edge[] = { 0, 1, 1919, 1920, 1921, 3840, 12000, 179999, 180000, 200000 };
    static FT8Result out[MAX_RESULTS];
    static uint8_t tiers[MAX_RESULTS];
    int full = 0, loop_runs = 0, real_loop_runs = 0;
    for (int run = 0; run < runs; run++) {
        const int real_run = g_real != NULL && (run % 200 == 100);
        int n = real_run ? (run % 400 == 100 ? PCM_SAMPLES : 20000 + (int)(rnd() % 160000u))
              : (run % 50 == 0) ? PCM_SAMPLES : (run % 7 == 0) ? edge[rnd() % 10u] : (int)(rnd() % 30000u);
        if (n >= PCM_SAMPLES) full++;
        int kind = real_run ? 7 : (int)(rnd() % 7u);
        const int tc[] = { 1, 2, 4, 8, 3 };
        int threads = tc[run % 5];
        /* Exactly-sized heap block, so AddressSanitizer sees any read past n. */
        float* x = (float*)malloc(sizeof(float) * (size_t)(n > 0 ? n : 1));
        if (real_run) mutate_real(x, n, (int)(rnd() % 4u)); else fill(x, n, kind);
        ftz_stats_t st;
        /* Tier B and CQ-AP are on in every run; most runs cap the candidates so a noise buffer does not cost seconds under the sanitizers. */
        int max_cand = real_run ? 40 : (run % 250 == 0) ? 0 : 1 + (int)(rnd() % 4u);
        /* The loop is on in most runs (random round cap, the test hook that expires a round, ungating and the residual-candidates rule), off in some. */
        int flags = FTZ_FLAG_CQ_AP | ((run % 13 == 0) ? FTZ_FLAG_BUDGET : 0) | ((run % 5 != 0) ? FTZ_FLAG_ROUNDS : 0)
                  | ((rnd() & 1u) ? FTZ_FLAG_RESIDUAL_UNGATED : 0) | ((rnd() & 1u) ? FTZ_FLAG_RESIDUAL_CANDS : 0);
        if (real_run) flags = FTZ_FLAG_CQ_AP | FTZ_FLAG_ROUNDS | ((rnd() & 1u) ? FTZ_FLAG_RESIDUAL_UNGATED : 0) | ((rnd() & 1u) ? FTZ_FLAG_RESIDUAL_CANDS : 0);   /* the loop must run on real audio, with no budget */
        int budget = (int)(rnd() % 25u);
        int max_rounds = (int)(rnd() % 5u);                  /* 0 = 3, 4 clamps to 3 */
        int expire = (int)(rnd() % 6u);                      /* 0 none; 4 and 5 are never reached */
        if (real_run && (rnd() & 3u) != 0) expire = 0;       /* mostly let the rounds finish; a quarter expire at a round */
        static uint8_t rounds[MAX_RESULTS];
        if ((rnd() & 3u) == 0) flags |= FTZ_FLAG_NO_TIER_B;                        /* decoder.effort = fast */
        if (rnd() & 1u) flags |= FTZ_FLAG_SKIP_FITS;                               /* step 2e: the fit-skip rule */
        g_inject = (real_run && (rnd() % 8u) == 0) ? 1 + (int)(rnd() % 3u) : 0;   /* step 2e: a simulated fit error after the first chunk of that round */
        const int want_resid = (rnd() & 1u) != 0, want_cb = (rnd() & 1u) != 0;
        /* Exactly-sized heap block, so AddressSanitizer sees any write past FT8_EXPECTED_SAMPLES floats. */
        float* resid = want_resid ? (float*)malloc(sizeof(float) * PCM_SAMPLES) : NULL;
        static cb_probe_t fprobe;
        int rc = decode_full2(x, n, threads, max_cand, flags, budget, max_rounds, expire, out, tiers, rounds, &st, want_cb ? &fprobe : NULL, resid);
        if (want_cb) CHECK(fprobe.calls <= 1, "run %d: round-0 callback called %d times", run, fprobe.calls);
        if (want_cb && rc >= 0) CHECK(fprobe.calls == 1, "run %d: round-0 callback not called on a successful cycle", run);
        CHECK(st.has_residual == 0 || (resid != NULL && (flags & FTZ_FLAG_ROUNDS)), "run %d: has_residual without a buffer or without the loop", run);
        if (flags & FTZ_FLAG_NO_TIER_B) CHECK(st.n_b_eligible == 0 && st.n_b_attempted == 0 && st.n_b_published == 0, "run %d: tier B ran with the no-tier-B flag", run);
        free(resid);
        const int injected_error = g_inject != 0 && rc == FTZ_ERR_NOMEM;           /* the hook fired: results of the earlier rounds stand, no residual */
        CHECK((rc >= 0 && rc <= MAX_RESULTS) || injected_error, "run %d: kind %d n %d threads %d: rc %d", run, kind, n, threads, rc);
        if (injected_error) CHECK(st.has_residual == 0 && st.error == FTZ_ERR_NOMEM, "run %d: a fit error must export no residual (has_residual %d, error %d)", run, st.has_residual, st.error);
        else CHECK(st.error == 0 && st.n_results == (rc > 0 ? rc : 0), "run %d: stats inconsistent (error %d, n_results %d, rc %d)", run, st.error, st.n_results, rc);
        if (injected_error) rc = st.n_results;                                      /* the per-result checks below read the results the call had written */
        g_inject = 0;
        CHECK(st.n_rounds >= 0 && st.n_rounds <= FTZ_MAX_ROUNDS, "run %d: %d rounds", run, st.n_rounds);
        if (real_run) real_loop_runs++;
        if (st.n_rounds > 0) loop_runs++;
        int sum_rounds = 0;
        for (int r = 0; r <= FTZ_MAX_ROUNDS; r++) sum_rounds += st.rounds[r].n_results;
        CHECK(sum_rounds == (rc > 0 ? rc : 0), "run %d: per-round results %d, total %d", run, sum_rounds, rc);
        for (int i = 0; i < rc; i++) CHECK(rounds[i] <= FTZ_MAX_ROUNDS && (i == 0 || rounds[i] >= rounds[i - 1]), "run %d: result %d has round %d after %d", run, i, rounds[i], i ? rounds[i - 1] : 0);
        for (int i = 0; i < rc; i++) CHECK(tiers[i] <= FTZ_TIER_CQ, "run %d: result %d has tier %d", run, i, tiers[i]);
        for (int i = 0; i < rc; i++) CHECK(memchr(out[i].message, '\0', sizeof(out[i].message)) != NULL, "run %d: result %d not terminated", run, i);
        free(x);
        if (failures > 20) break;
    }
    printf("fuzz: %d runs (%d full length, %d on mutated real audio, %d with at least one subtract-and-retry round), no crash, no sanitizer report\n", runs, full, real_loop_runs, loop_runs);
}

/* The accept rules of step 2c, called directly (the cycle calls the same functions). */
static void accept_rules(void)
{
    const float subs[] = { 1000.0f, 2000.0f };
    CHECK(ftz_patch_keep(1000.0f, subs, 2) == 1, "patch: the centre");
    CHECK(ftz_patch_keep(950.0f, subs, 2) == 1 && ftz_patch_keep(949.9f, subs, 2) == 0, "patch: 50 Hz below is in, just below is out");
    CHECK(ftz_patch_keep(1100.0f, subs, 2) == 1 && ftz_patch_keep(1100.1f, subs, 2) == 0, "patch: 100 Hz above is in, just above is out");
    CHECK(ftz_patch_keep(2100.0f, subs, 2) == 1 && ftz_patch_keep(2100.1f, subs, 2) == 0 && ftz_patch_keep(1950.0f, subs, 2) == 1 && ftz_patch_keep(1949.9f, subs, 2) == 0, "patch: the second signal window");
    CHECK(ftz_patch_keep(1000.0f, subs, 0) == 0 && ftz_patch_keep(1000.0f, NULL, 2) == 0 && ftz_patch_keep(NAN, subs, 2) == 0, "patch: empty and NaN");

    int u = -1;
    CHECK(ftz_residual_b_accept(1, 1500, 0, 0, &u) == 1 && u == 0, "accept: passed row, no rules");
    CHECK(ftz_residual_b_accept(0, 500, 0, 0, &u) == 0, "accept: gated-out row, ungating off");
    CHECK(ftz_residual_b_accept(0, 500, 1, 0, &u) == 1 && u == 1, "accept: gated-out row, ungating on, counted ungated");
    CHECK(ftz_residual_b_accept(1, 1098, 1, 1, &u) == 1 && u == 0, "accept: above 1097 Hz, the residual-candidates flag has no effect (step 2e)");
    CHECK(ftz_residual_b_accept(0, 2400, 1, 1, &u) == 1 && u == 1, "accept: gated-out row at any frequency, ungating on, flag on: published as ungated (step 2e)");
    CHECK(ftz_residual_b_accept(0, 500, 0, 1, &u) == 0, "accept: gated-out row, ungating off, flag on");
    CHECK(ftz_fit_needed(1000.0f, NULL, 0) == 0 && ftz_fit_needed(1000.0f, &(float){ 950.0f }, 1) == 1 && ftz_fit_needed(1000.0f, &(float){ 1100.1f }, 1) == 0, "fit_needed: window edges and the empty list");
    CHECK(ftz_residual_b_accept(1, 1098, 0, 0, NULL) == 1, "accept: above 1097 Hz, rule off");

    uint8_t a[10] = { 0 }, b[10] = { 0 };
    for (int i = 0; i < 10; i++) { a[i] = (uint8_t)(rnd() & 0xFFu); b[i] = a[i]; }
    a[9] &= 0xF8u; b[9] = (uint8_t)(a[9] | 0x05u);                       /* the three padding bits do not count */
    CHECK(ftz_payload_same_qso(a, b) == 1, "same_qso: identical 77 bits");
    b[3] ^= 0x10u;
    CHECK(ftz_payload_same_qso(a, b) == 0, "same_qso: one bit different");
    /* A standard-message payload: call1 = 29 bits at 0, call2 = 29 bits at 29, ir bit 58, igrid4 bits 59..73, i3 = 1 at 74..76. */
    uint8_t rr_std[10] = { 0 }, rr_air[10] = { 0 };
    for (int pass = 0; pass < 2; pass++) {
        uint8_t* p = pass ? rr_air : rr_std;
        uint32_t ig = pass ? 32373u : 32403u;
        for (int i = 0; i < 58; i++) { int bit = (int)((0xA5A5A5A5u >> (i % 29)) & 1u); if (bit) p[i >> 3] |= (uint8_t)(0x80u >> (i & 7)); }
        for (int i = 0; i < 15; i++) if ((ig >> (14 - i)) & 1u) p[(59 + i) >> 3] |= (uint8_t)(0x80u >> ((59 + i) & 7));
        p[9] |= (uint8_t)(1u << 3);                                      /* i3 = 001: bits 74..76 = 0,0,1, i.e. bit 76 */
    }
    CHECK(ftz_payload_same_qso(rr_std, rr_air) == 1, "same_qso: std RR73 known, on-air RR73 candidate, same calls");
    CHECK(ftz_payload_same_qso(rr_air, rr_std) == 0, "same_qso: the reverse is not a match (the one-way rule of classic)");
    rr_air[1] ^= 0x01u;
    CHECK(ftz_payload_same_qso(rr_std, rr_air) == 0, "same_qso: different calls");
    printf("accept rules: patch window, residual tier-B rules, payload same-QSO: checked\n");
}

static void bad_audio(void)
{
    static FT8Result out[MAX_RESULTS];
    const float poison[] = { NAN, INFINITY, -INFINITY, 1.0e30f };
    for (int k = 0; k < 4; k++) {
        float* x = (float*)calloc(PCM_SAMPLES, sizeof(float));
        for (int i = 0; i < PCM_SAMPLES; i++) x[i] = rndf() * 0.1f;
        x[90000] = poison[k];
        ftz_stats_t st;
        int rc = decode(x, PCM_SAMPLES, 2, out, &st);
        CHECK(rc == FTZ_ERR_BADAUDIO, "poison %d: rc %d, expected FTZ_ERR_BADAUDIO", k, rc);
        free(x);
    }
    float* y = (float*)calloc(PCM_SAMPLES, sizeof(float));
    for (int i = 0; i < PCM_SAMPLES; i++) y[i] = rndf() * 0.1f;
    ftz_stats_t st;
    CHECK(decode(y, PCM_SAMPLES, 2, out, &st) >= 0, "the call after bad audio failed");

    /* Argument errors. */
    ftz_params_t p; memset(&p, 0, sizeof(p)); p.struct_size = (int32_t)sizeof(p);
    CHECK(ftz_decode_cycle(NULL, 10, &p, out, MAX_RESULTS, NULL, NULL, &st) == FTZ_ERR_ARG, "NULL pcm with n > 0");
    CHECK(ftz_decode_cycle(y, -1, &p, out, MAX_RESULTS, NULL, NULL, &st) == FTZ_ERR_ARG, "negative n");
    CHECK(ftz_decode_cycle(y, 10, NULL, out, MAX_RESULTS, NULL, NULL, &st) == FTZ_ERR_ARG, "NULL params");
    CHECK(ftz_decode_cycle(y, 10, &p, NULL, MAX_RESULTS, NULL, NULL, &st) == FTZ_ERR_ARG, "NULL results");
    CHECK(ftz_decode_cycle(y, 10, &p, out, 0, NULL, NULL, &st) == FTZ_ERR_ARG, "zero capacity");
    CHECK(ftz_decode_cycle(NULL, 0, &p, out, MAX_RESULTS, NULL, NULL, NULL) == 0, "n = 0 with NULL pcm and NULL stats");
    free(y);
    printf("bad audio and argument errors: handled\n");
}

int main(int argc, char** argv)
{
    int runs = 10000;
    int wavs = 0;
    for (int i = 1; i < argc; i++) {
        if (!strncmp(argv[i], "--runs=", 7)) runs = atoi(argv[i] + 7);
        else
        {
            determinism(argv[i]); wavs++;
            if (g_real == NULL) g_real = read_wav(argv[i], &g_real_n);       /* the first one feeds the mutated-real-audio fuzz runs */
        }
    }
    accept_rules();
    fuzz(runs);
    bad_audio();
    free(g_real);
    ftz_shutdown();
    ftz_shutdown();   /* twice: must be harmless */
    if (failures) { fprintf(stderr, "%d check(s) failed\n", failures); return 1; }
    printf("OK (%d wav(s), %d fuzz runs)\n", wavs, runs);
    return 0;
}
