/*
 * ftz_fuzz.c -- native test harness for ftz_decode_cycle (DR-2 step 2a): built and run under AddressSanitizer and
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

static int decode(const float* pcm, int n, int threads, FT8Result* out, ftz_stats_t* st)
{
    ftz_params_t p;
    memset(&p, 0, sizeof(p));
    p.struct_size = (int32_t)sizeof(p);
    p.threads = threads;
    return ftz_decode_cycle(pcm, n, &p, out, MAX_RESULTS, st);
}

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
    int first_n = -1;
    const int threads[] = { 1, 2, 4, 2, 1 };
    for (int t = 0; t < 5; t++) {
        ft8_hash_state_restore(start, image_size);
        ftz_stats_t st;
        memset(cur, 0, sizeof(cur));
        int rc = decode(pcm, n, threads[t], cur, &st);
        CHECK(rc >= 0, "%s threads=%d: error %d", path, threads[t], rc);
        if (rc < 0) continue;
        if (first_n < 0) { first_n = rc; memcpy(first, cur, sizeof(first)); CHECK(rc > 0, "%s decoded nothing", path); }
        else {
            CHECK(rc == first_n, "%s threads=%d: %d results, expected %d", path, threads[t], rc, first_n);
            CHECK(memcmp(first, cur, sizeof(FT8Result) * (size_t)(first_n < rc ? first_n : rc)) == 0,
                  "%s threads=%d: output differs from threads=1", path, threads[t]);
        }
    }
    ft8_hash_state_restore(start, image_size);
    printf("determinism %s: %d results, identical at 1/2/4/2/1 threads\n", path, first_n);
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

static void fuzz(int runs)
{
    const int edge[] = { 0, 1, 1919, 1920, 1921, 3840, 12000, 179999, 180000, 200000 };
    static FT8Result out[MAX_RESULTS];
    int full = 0;
    for (int run = 0; run < runs; run++) {
        int n = (run % 50 == 0) ? PCM_SAMPLES : (run % 7 == 0) ? edge[rnd() % 10u] : (int)(rnd() % 30000u);
        if (n >= PCM_SAMPLES) full++;
        int kind = (int)(rnd() % 7u);
        const int tc[] = { 1, 2, 4, 8, 3 };
        int threads = tc[run % 5];
        /* Exactly-sized heap block, so AddressSanitizer sees any read past n. */
        float* x = (float*)malloc(sizeof(float) * (size_t)(n > 0 ? n : 1));
        fill(x, n, kind);
        ftz_stats_t st;
        int rc = decode(x, n, threads, out, &st);
        CHECK(rc >= 0 && rc <= MAX_RESULTS, "run %d: kind %d n %d threads %d: rc %d", run, kind, n, threads, rc);
        CHECK(st.error == 0 && st.n_results == (rc > 0 ? rc : 0), "run %d: stats inconsistent (error %d, n_results %d, rc %d)", run, st.error, st.n_results, rc);
        for (int i = 0; i < rc; i++) CHECK(memchr(out[i].message, '\0', sizeof(out[i].message)) != NULL, "run %d: result %d not terminated", run, i);
        free(x);
        if (failures > 20) break;
    }
    printf("fuzz: %d runs (%d full length), no crash, no sanitizer report\n", runs, full);
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
    CHECK(ftz_decode_cycle(NULL, 10, &p, out, MAX_RESULTS, &st) == FTZ_ERR_ARG, "NULL pcm with n > 0");
    CHECK(ftz_decode_cycle(y, -1, &p, out, MAX_RESULTS, &st) == FTZ_ERR_ARG, "negative n");
    CHECK(ftz_decode_cycle(y, 10, NULL, out, MAX_RESULTS, &st) == FTZ_ERR_ARG, "NULL params");
    CHECK(ftz_decode_cycle(y, 10, &p, NULL, MAX_RESULTS, &st) == FTZ_ERR_ARG, "NULL results");
    CHECK(ftz_decode_cycle(y, 10, &p, out, 0, &st) == FTZ_ERR_ARG, "zero capacity");
    CHECK(ftz_decode_cycle(NULL, 0, &p, out, MAX_RESULTS, NULL) == 0, "n = 0 with NULL pcm and NULL stats");
    free(y);
    printf("bad audio and argument errors: handled\n");
}

int main(int argc, char** argv)
{
    int runs = 10000;
    int wavs = 0;
    for (int i = 1; i < argc; i++) {
        if (!strncmp(argv[i], "--runs=", 7)) runs = atoi(argv[i] + 7);
        else { determinism(argv[i]); wavs++; }
    }
    fuzz(runs);
    bad_audio();
    ftz_shutdown();
    ftz_shutdown();   /* twice: must be harmless */
    if (failures) { fprintf(stderr, "%d check(s) failed\n", failures); return 1; }
    printf("OK (%d wav(s), %d fuzz runs)\n", wavs, runs);
    return 0;
}
