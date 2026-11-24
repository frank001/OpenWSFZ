/*
 * ftz_decoder.c -- the lean decoder engine, step 2a (DR-2, shim 20260073): ftz_decode_cycle.
 *
 * PROVENANCE: OpenWSFZ-original, written 2026-11-24 from docs/decoder-rebuild/spec-dr2-lean-decoder.md (arch/decoder-rebuild).
 * It composes, with their meaning unchanged, the ft8_lib building blocks (MIT, Karlis Goba) the shim already uses: the
 * waterfall (monitor.c + KISS FFT), ftx_find_candidates, ft8_extract_likelihood through ftx_decode_candidate_tier_a (decode.c),
 * ldpc.c, crc.c, message.c, and the shim's own callsign table. No line of WSJT-X is copied or ported.
 *
 * THIS FILE IS NOT A SEPARATE TRANSLATION UNIT. ft8_shim.c #includes it at its very end, so that the lean engine shares the
 * shim's callsign table, its message-text interface and its SNR helpers (statics of ft8_shim.c) instead of duplicating them,
 * and so that every build recipe that already compiles ft8_shim.c (rebuild_shim.bat, build_linux.sh, the CI macOS and Linux
 * steps) builds it without a new compile line. Nothing here is reachable except through ftz_decode_cycle and ftz_shutdown.
 *
 * Shape of a call (spec section 2.3, S1 + S2 steps 1, 2, 6 and 7):
 *   S1  spectrogram (same monitor configuration as the primary pass: window, oversampling and scaling are closed arms)
 *   S2  candidates (ftx_find_candidates, today's primary parameters), tier A on every candidate IN PARALLEL on a fixed
 *       worker pool, then ON THE CALLING THREAD, in a fixed order: sort by (frequency, time, payload), unpack against the
 *       callsign table, de-duplicate by payload and by text, SNR, write the result.
 *   The sort happens before anything touches the callsign table, so the output does not depend on the thread count.
 *
 * Memory safety (the 2026-09 crash history): every index is bounds-checked against a size the call itself computed; the
 * spectrogram's allocations are checked; an access violation is caught (MSVC builds) and returned as FTZ_ERR_FAULT; no
 * function here writes through a pointer the caller did not size, and nothing here allocates per candidate.
 */

#include "ftz_decoder.h"

#ifdef _WIN32
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  ifndef NOMINMAX
#    define NOMINMAX
#  endif
#  include <windows.h>
#else
#  include <pthread.h>
#  include <time.h>
#endif

#include <stdlib.h>

/* decode.c (patched): the thread-safe tier A. Declared here, not in the vendored decode.h. */
bool ftx_decode_candidate_tier_a(const ftx_waterfall_t* wf, const ftx_candidate_t* cand, int max_iterations,
                                 ftx_message_t* message, ftx_decode_status_t* status);

#define FTZ_DEFAULT_MIN_SCORE       K_MIN_SCORE          /* 10  */
#define FTZ_DEFAULT_MAX_CANDIDATES  K_MAX_CANDIDATES     /* 140 */
#define FTZ_DEFAULT_LDPC_ITERATIONS K_LDPC_ITERATIONS    /* 50  */
#define FTZ_PAYLOAD_BYTES           FTX_PAYLOAD_LENGTH_BYTES

/* ── Clocks ───────────────────────────────────────────────────────────────── */

static int64_t ftz_wall_us(void)
{
#ifdef _WIN32
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    if (f.QuadPart <= 0) return 0;
    return (int64_t)((c.QuadPart / f.QuadPart) * 1000000LL + ((c.QuadPart % f.QuadPart) * 1000000LL) / f.QuadPart);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000LL + ts.tv_nsec / 1000;
#endif
}

/* CPU time consumed by THE CALLING THREAD, microseconds. */
static int64_t ftz_thread_cpu_us(void)
{
#ifdef _WIN32
    FILETIME c, e, k, u;
    if (!GetThreadTimes(GetCurrentThread(), &c, &e, &k, &u)) return 0;
    uint64_t kt = ((uint64_t)k.dwHighDateTime << 32) | k.dwLowDateTime;
    uint64_t ut = ((uint64_t)u.dwHighDateTime << 32) | u.dwLowDateTime;
    return (int64_t)((kt + ut) / 10u);          /* 100 ns units */
#else
    struct timespec ts;
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts) != 0) return 0;
    return (int64_t)ts.tv_sec * 1000000LL + ts.tv_nsec / 1000;
#endif
}

/* ── Portable lock / condition / thread ───────────────────────────────────── */

#ifdef _WIN32
typedef CRITICAL_SECTION   ftz_mutex_t;
typedef CONDITION_VARIABLE ftz_cond_t;
typedef HANDLE             ftz_thread_t;
static void ftz_mutex_init(ftz_mutex_t* m)    { InitializeCriticalSection(m); }
static void ftz_mutex_destroy(ftz_mutex_t* m) { DeleteCriticalSection(m); }
static void ftz_mutex_lock(ftz_mutex_t* m)    { EnterCriticalSection(m); }
static void ftz_mutex_unlock(ftz_mutex_t* m)  { LeaveCriticalSection(m); }
static void ftz_cond_init(ftz_cond_t* c)      { InitializeConditionVariable(c); }
static void ftz_cond_destroy(ftz_cond_t* c)   { (void)c; }
static void ftz_cond_wait(ftz_cond_t* c, ftz_mutex_t* m) { SleepConditionVariableCS(c, m, INFINITE); }
static void ftz_cond_broadcast(ftz_cond_t* c) { WakeAllConditionVariable(c); }
typedef DWORD (WINAPI *ftz_thread_fn)(LPVOID);
#  define FTZ_THREAD_RET DWORD WINAPI
static int  ftz_thread_start(ftz_thread_t* t, ftz_thread_fn fn, void* arg)
{
    *t = CreateThread(NULL, 0, fn, arg, 0, NULL);
    return *t != NULL ? 0 : -1;
}
static void ftz_thread_join(ftz_thread_t t) { WaitForSingleObject(t, INFINITE); CloseHandle(t); }
static SRWLOCK g_ftz_call_lock = SRWLOCK_INIT;
static void ftz_call_lock(void)   { AcquireSRWLockExclusive(&g_ftz_call_lock); }
static void ftz_call_unlock(void) { ReleaseSRWLockExclusive(&g_ftz_call_lock); }
#else
typedef pthread_mutex_t ftz_mutex_t;
typedef pthread_cond_t  ftz_cond_t;
typedef pthread_t       ftz_thread_t;
static void ftz_mutex_init(ftz_mutex_t* m)    { pthread_mutex_init(m, NULL); }
static void ftz_mutex_destroy(ftz_mutex_t* m) { pthread_mutex_destroy(m); }
static void ftz_mutex_lock(ftz_mutex_t* m)    { pthread_mutex_lock(m); }
static void ftz_mutex_unlock(ftz_mutex_t* m)  { pthread_mutex_unlock(m); }
static void ftz_cond_init(ftz_cond_t* c)      { pthread_cond_init(c, NULL); }
static void ftz_cond_destroy(ftz_cond_t* c)   { pthread_cond_destroy(c); }
static void ftz_cond_wait(ftz_cond_t* c, ftz_mutex_t* m) { pthread_cond_wait(c, m); }
static void ftz_cond_broadcast(ftz_cond_t* c) { pthread_cond_broadcast(c); }
typedef void* (*ftz_thread_fn)(void*);
#  define FTZ_THREAD_RET void*
static int  ftz_thread_start(ftz_thread_t* t, ftz_thread_fn fn, void* arg) { return pthread_create(t, NULL, fn, arg) == 0 ? 0 : -1; }
static void ftz_thread_join(ftz_thread_t t) { pthread_join(t, NULL); }
static pthread_mutex_t g_ftz_call_lock = PTHREAD_MUTEX_INITIALIZER;
static void ftz_call_lock(void)   { pthread_mutex_lock(&g_ftz_call_lock); }
static void ftz_call_unlock(void) { pthread_mutex_unlock(&g_ftz_call_lock); }
#endif

/* ── The fixed worker pool ────────────────────────────────────────────────── */
/*
 * Created once (on the first call that needs it, or when the configured thread count changes between cycles), never per
 * cycle. A job is "run fn(ctx, i) for i in [0, n_items)"; workers take items under the mutex, so each item runs exactly once.
 * ftz_pool_run returns when every item is done. Only ever used under g_ftz_call_lock, so one job at a time.
 */
typedef void (*ftz_item_fn)(void* ctx, int item);

typedef struct ftz_pool
{
    int          n_threads;
    int          n_started;
    ftz_thread_t threads[FTZ_MAX_THREADS];
    ftz_mutex_t  mu;
    ftz_cond_t   cv_work;
    ftz_cond_t   cv_done;
    unsigned     generation;     /* bumped for every job; a worker runs each generation once */
    int          stop;
    ftz_item_fn  fn;
    void*        ctx;
    int          n_items;
    int          next_item;
    int          n_finished;     /* workers that have finished the current generation        */
    int          fault;          /* an item raised an access violation (MSVC builds)         */
    int64_t      job_cpu_us;     /* CPU summed over the workers for the current job          */
} ftz_pool_t;

static ftz_pool_t* g_ftz_pool = NULL;

/* One item under a guard: on MSVC an access violation in fn is caught and reported instead of ending the process. */
static int ftz_guarded_item(ftz_item_fn fn, void* ctx, int item)
{
#ifdef _MSC_VER
    __try { fn(ctx, item); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return 1; }
    return 0;
#else
    fn(ctx, item);
    return 0;
#endif
}

static FTZ_THREAD_RET ftz_worker_main(
#ifdef _WIN32
    LPVOID arg
#else
    void* arg
#endif
)
{
    ftz_pool_t* p = (ftz_pool_t*)arg;
    unsigned seen = 0;
    for (;;)
    {
        ftz_mutex_lock(&p->mu);
        while (!p->stop && p->generation == seen) ftz_cond_wait(&p->cv_work, &p->mu);
        if (p->stop) { ftz_mutex_unlock(&p->mu); break; }
        seen = p->generation;
        ftz_item_fn fn = p->fn;
        void*       ctx = p->ctx;
        ftz_mutex_unlock(&p->mu);

        int64_t cpu0 = ftz_thread_cpu_us();
        int faulted = 0;
        for (;;)
        {
            ftz_mutex_lock(&p->mu);
            int item = p->next_item < p->n_items ? p->next_item++ : -1;
            ftz_mutex_unlock(&p->mu);
            if (item < 0) break;
            if (ftz_guarded_item(fn, ctx, item)) faulted = 1;
        }
        int64_t cpu = ftz_thread_cpu_us() - cpu0;

        ftz_mutex_lock(&p->mu);
        if (faulted) p->fault = 1;
        if (cpu > 0) p->job_cpu_us += cpu;
        p->n_finished++;
        if (p->n_finished >= p->n_started) ftz_cond_broadcast(&p->cv_done);
        ftz_mutex_unlock(&p->mu);
    }
    return 0;
}

static void ftz_pool_destroy(ftz_pool_t* p)
{
    if (p == NULL) return;
    ftz_mutex_lock(&p->mu);
    p->stop = 1;
    ftz_cond_broadcast(&p->cv_work);
    ftz_mutex_unlock(&p->mu);
    for (int i = 0; i < p->n_started; ++i) ftz_thread_join(p->threads[i]);
    ftz_cond_destroy(&p->cv_work);
    ftz_cond_destroy(&p->cv_done);
    ftz_mutex_destroy(&p->mu);
    free(p);
}

/* NULL on failure (the caller then runs inline). */
static ftz_pool_t* ftz_pool_create(int n_threads)
{
    if (n_threads < FTZ_MIN_THREADS || n_threads > FTZ_MAX_THREADS) return NULL;
    ftz_pool_t* p = (ftz_pool_t*)calloc(1, sizeof(*p));
    if (p == NULL) return NULL;
    p->n_threads = n_threads;
    ftz_mutex_init(&p->mu);
    ftz_cond_init(&p->cv_work);
    ftz_cond_init(&p->cv_done);
    for (int i = 0; i < n_threads; ++i)
    {
        if (ftz_thread_start(&p->threads[i], ftz_worker_main, p) != 0) { ftz_pool_destroy(p); return NULL; }
        p->n_started++;
    }
    return p;
}

/* Returns 0 on success, 1 if an item faulted. Fills *cpu_us with the CPU the workers used. */
static int ftz_pool_run(ftz_pool_t* p, ftz_item_fn fn, void* ctx, int n_items, int64_t* cpu_us)
{
    ftz_mutex_lock(&p->mu);
    p->fn = fn; p->ctx = ctx; p->n_items = n_items; p->next_item = 0;
    p->n_finished = 0; p->fault = 0; p->job_cpu_us = 0;
    p->generation++;
    ftz_cond_broadcast(&p->cv_work);
    while (p->n_finished < p->n_started) ftz_cond_wait(&p->cv_done, &p->mu);
    int fault = p->fault;
    if (cpu_us != NULL) *cpu_us = p->job_cpu_us;
    ftz_mutex_unlock(&p->mu);
    return fault;
}

void ftz_shutdown(void)
{
    ftz_call_lock();
    ftz_pool_destroy(g_ftz_pool);
    g_ftz_pool = NULL;
    ftz_call_unlock();
}

/* ── Tier A on the pool ───────────────────────────────────────────────────── */

typedef struct
{
    const ftx_waterfall_t* wf;
    const ftx_candidate_t* cands;
    int                    n_cands;
    int                    ldpc_iterations;
    ftx_message_t*         msgs;     /* [n_cands]; written only at the item's own index */
    uint8_t*               ok;       /* [n_cands]; likewise                              */
} ftz_tier_a_ctx_t;

static void ftz_tier_a_item(void* vctx, int i)
{
    ftz_tier_a_ctx_t* c = (ftz_tier_a_ctx_t*)vctx;
    if (i < 0 || i >= c->n_cands) return;                 /* bounds: the item index is the pool's, the arrays are ours */
    ftx_decode_status_t status;
    memset(&status, 0, sizeof(status));
    c->ok[i] = ftx_decode_candidate_tier_a(c->wf, &c->cands[i], c->ldpc_iterations, &c->msgs[i], &status) ? 1u : 0u;
}

/* ── Ordering ─────────────────────────────────────────────────────────────── */

typedef struct
{
    float   freq_hz;
    float   dt;
    uint8_t payload[FTZ_PAYLOAD_BYTES];
    int     index;       /* into the candidate / message arrays */
} ftz_hit_t;

static int ftz_hit_cmp(const void* a, const void* b)
{
    const ftz_hit_t* x = (const ftz_hit_t*)a;
    const ftz_hit_t* y = (const ftz_hit_t*)b;
    if (x->freq_hz < y->freq_hz) return -1;
    if (x->freq_hz > y->freq_hz) return 1;
    if (x->dt < y->dt) return -1;
    if (x->dt > y->dt) return 1;
    int c = memcmp(x->payload, y->payload, FTZ_PAYLOAD_BYTES);
    if (c != 0) return c;
    return (x->index > y->index) - (x->index < y->index);  /* total order: identical hits keep a fixed order */
}

/* ── SNR (the primary pass's formula, unchanged) ──────────────────────────── */

static float ftz_snr_db(const monitor_t* mon, const ftx_candidate_t* cand, const uint8_t* tones, float noise_floor_db)
{
    float signal_db;
    float sum = 0.0f; int cnt = 0;
    int bs = mon->wf.block_stride;
    int pt = mon->wf.freq_osr * mon->wf.num_bins;
    int nb = mon->wf.num_bins;
    int b0 = (int)cand->time_offset; if (b0 < 0) b0 = 0;
    int b1 = (int)cand->time_offset + FT8_NN;
    if (b1 > mon->wf.num_blocks) b1 = mon->wf.num_blocks;
    int fi = (int)cand->time_sub * pt + (int)cand->freq_sub * nb + (int)cand->freq_offset;
    for (int b = b0; b < b1; b++) {
        int sym = b - (int)cand->time_offset;
        if (sym < 0 || sym >= FT8_NN) continue;           /* bounds: tones[] has FT8_NN entries */
        const WF_ELEM_T* row = mon->wf.mag + (size_t)b * (size_t)bs + (size_t)fi;
        int tone_col = (int)tones[sym];
        if ((int)cand->freq_offset + tone_col >= nb) continue;
        float mx = (float)row[tone_col] * 0.5f - 120.0f;
        sum += mx; cnt++;
    }
    signal_db = cnt > 0 ? sum / (float)cnt : noise_floor_db;
    float local_noise_db = compute_local_noise_floor_db(&mon->wf, (int)cand->freq_offset);
    return signal_db - local_noise_db - 26.5f;
}

/* ── The cycle ────────────────────────────────────────────────────────────── */

static int ftz_clamp_int(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static int ftz_audio_ok(const float* pcm, int n)
{
    for (int i = 0; i < n; ++i)
    {
        float v = pcm[i];
        if (!(v >= -FTZ_MAX_ABS_SAMPLE && v <= FTZ_MAX_ABS_SAMPLE)) return 0;   /* false for NaN too */
    }
    return 1;
}

static int ftz_decode_cycle_impl(const float* pcm, int n, const ftz_params_t* params, FT8Result* results, int cap, ftz_stats_t* st)
{
    const int64_t t_start = ftz_wall_us();

    /* Parameters: zero = today's primary value; everything clamped. */
    int threads  = params->threads         != 0 ? params->threads         : FTZ_DEFAULT_THREADS;
    int min_sc   = params->min_score       != 0 ? params->min_score       : FTZ_DEFAULT_MIN_SCORE;
    int max_c    = params->max_candidates  != 0 ? params->max_candidates  : FTZ_DEFAULT_MAX_CANDIDATES;
    int ldpc_it  = params->ldpc_iterations != 0 ? params->ldpc_iterations : FTZ_DEFAULT_LDPC_ITERATIONS;
    threads = ftz_clamp_int(threads, FTZ_MIN_THREADS, FTZ_MAX_THREADS);
    max_c   = ftz_clamp_int(max_c, 1, FTZ_MAX_CANDIDATES);
    ldpc_it = ftz_clamp_int(ldpc_it, 1, 1000);
    min_sc  = ftz_clamp_int(min_sc, 0, 32767);
    if (n > FT8_EXPECTED_SAMPLES) n = FT8_EXPECTED_SAMPLES;
    st->threads = threads;

    if (!ftz_audio_ok(pcm, n)) return FTZ_ERR_BADAUDIO;

    /* ── S1: spectrogram (the primary pass's monitor configuration) ── */
    int64_t w0 = ftz_wall_us(), c0 = ftz_thread_cpu_us();
    monitor_t mon;
    memset(&mon, 0, sizeof(mon));
    monitor_config_t cfg = {
        .f_min = 140.0f, .f_max = 3075.0f,
        .sample_rate = FT8_SAMPLE_RATE,
        .time_osr = K_TIME_OSR, .freq_osr = K_FREQ_OSR,
        .protocol = FTX_PROTOCOL_FT8
    };
    monitor_init(&mon, &cfg);
    if (mon.wf.mag == NULL || mon.window == NULL || mon.last_frame == NULL || mon.fft_cfg == NULL || mon.block_size <= 0)
    {
        monitor_free(&mon);                       /* free(NULL) is fine; monitor_free frees only what monitor_init allocated */
        return FTZ_ERR_NOMEM;
    }
    for (int pos = 0; pos + mon.block_size <= n; pos += mon.block_size)
        monitor_process(&mon, pcm + pos);         /* monitor_process itself stops at max_blocks */
    st->spectrogram_wall_us = ftz_wall_us() - w0;
    st->spectrogram_cpu_us  = ftz_thread_cpu_us() - c0;

    /* Callsign table: session-scoped, shared with the classic path, initialised once (as ft8_decode_all does). */
    if (!g_hash_table_initialised) {
        hash_table_init(&g_session_hash_table);
        g_hash_table_initialised = true;
    }
    tls_hash_table = &g_session_hash_table;

    float     noise_floor_db;
    WF_ELEM_T noise_raw;
    compute_noise_floor(&mon, &noise_floor_db, &noise_raw);
    (void)noise_raw;
    tls_last_noise_floor_db = noise_floor_db;     /* compute_local_noise_floor_db's fallback reads it */

    int rc = FTZ_OK;
    ftx_candidate_t* cands = (ftx_candidate_t*)calloc((size_t)max_c, sizeof(ftx_candidate_t));
    ftx_message_t*   msgs  = (ftx_message_t*)calloc((size_t)max_c, sizeof(ftx_message_t));
    uint8_t*         ok    = (uint8_t*)calloc((size_t)max_c, sizeof(uint8_t));
    ftz_hit_t*       hits  = (ftz_hit_t*)calloc((size_t)max_c, sizeof(ftz_hit_t));
    char (*texts)[FTX_MAX_MESSAGE_LENGTH + 1] = (char (*)[FTX_MAX_MESSAGE_LENGTH + 1])calloc((size_t)max_c, FTX_MAX_MESSAGE_LENGTH + 1);
    uint8_t (*seen_payloads)[FTZ_PAYLOAD_BYTES] = (uint8_t (*)[FTZ_PAYLOAD_BYTES])calloc((size_t)max_c, FTZ_PAYLOAD_BYTES);
    if (cands == NULL || msgs == NULL || ok == NULL || hits == NULL || texts == NULL || seen_payloads == NULL)
    {
        rc = FTZ_ERR_NOMEM;
        goto done;
    }

    /* ── S2 step 1: candidates ── */
    w0 = ftz_wall_us(); c0 = ftz_thread_cpu_us();
    int ncands = ftx_find_candidates(&mon.wf, max_c, cands, min_sc);
    if (ncands < 0) ncands = 0;
    if (ncands > max_c) ncands = max_c;
    st->n_candidates       = ncands;
    st->candidates_wall_us = ftz_wall_us() - w0;
    st->candidates_cpu_us  = ftz_thread_cpu_us() - c0;

    /* ── S2 step 2: tier A on every candidate, in parallel ── */
    w0 = ftz_wall_us();
    {
        ftz_tier_a_ctx_t ctx = { &mon.wf, cands, ncands, ldpc_it, msgs, ok };
        int64_t cpu_us = 0;
        if (threads > 1 && ncands > 1)
        {
            if (g_ftz_pool != NULL && g_ftz_pool->n_threads != threads) { ftz_pool_destroy(g_ftz_pool); g_ftz_pool = NULL; }
            if (g_ftz_pool == NULL) g_ftz_pool = ftz_pool_create(threads);   /* NULL: fall back to inline below */
        }
        else if (g_ftz_pool != NULL && threads == 1)
        {
            ftz_pool_destroy(g_ftz_pool);
            g_ftz_pool = NULL;
        }
        if (g_ftz_pool != NULL && threads > 1 && ncands > 1)
        {
            if (ftz_pool_run(g_ftz_pool, ftz_tier_a_item, &ctx, ncands, &cpu_us) != 0) { rc = FTZ_ERR_FAULT; goto done; }
        }
        else
        {
            int64_t cc0 = ftz_thread_cpu_us();
            st->threads = 1;
            for (int i = 0; i < ncands; ++i)
                if (ftz_guarded_item(ftz_tier_a_item, &ctx, i)) { rc = FTZ_ERR_FAULT; goto done; }
            cpu_us = ftz_thread_cpu_us() - cc0;
        }
        st->tier_a_cpu_us = cpu_us;
    }
    st->tier_a_wall_us = ftz_wall_us() - w0;

    /* ── S2 steps 6 and 7: order, then unpack / de-duplicate / publish, on this thread ── */
    w0 = ftz_wall_us(); c0 = ftz_thread_cpu_us();
    int nhits = 0;
    for (int i = 0; i < ncands; ++i)
    {
        if (!ok[i]) continue;
        const ftx_candidate_t* cand = &cands[i];
        ftz_hit_t* h = &hits[nhits++];
        h->freq_hz = (mon.min_bin + cand->freq_offset + (float)cand->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
        h->dt      = (cand->time_offset + (float)cand->time_sub / mon.wf.time_osr) * mon.symbol_period;
        memcpy(h->payload, msgs[i].payload, FTZ_PAYLOAD_BYTES);
        h->index = i;
    }
    st->n_tier_a = nhits;
    qsort(hits, (size_t)nhits, sizeof(ftz_hit_t), ftz_hit_cmp);

    int nseen = 0, nres = 0;
    for (int k = 0; k < nhits; ++k)
    {
        const int i = hits[k].index;
        if (i < 0 || i >= ncands) continue;
        const ftx_candidate_t* cand = &cands[i];
        ftx_message_t*         msg  = &msgs[i];

        bool dup = false;
        for (int s = 0; s < nseen; ++s)
            if (!memcmp(seen_payloads[s], msg->payload, FTZ_PAYLOAD_BYTES)) { dup = true; break; }
        if (dup) continue;

        char text[FTX_MAX_MESSAGE_LENGTH + 1];
        tls_h12_lookup_performed = false;
        tls_h12_suppressed       = false;
        if (ftx_message_decode(msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
            continue;                              /* e.g. a Type-4 hash not yet known: not a decode */
        text[FTX_MAX_MESSAGE_LENGTH] = '\0';

        /* Past this point the payload unpacked: remember it, then de-duplicate by text (two payloads can render alike). */
        memcpy(seen_payloads[nseen++], msg->payload, FTZ_PAYLOAD_BYTES);   /* nseen < nhits <= max_c: each hit is added once */
        bool text_dup = false;
        for (int s = 0; s < nres; ++s)
            if (!strcmp(texts[s], text)) { text_dup = true; break; }
        if (text_dup) continue;

        if (nres >= cap) { st->abandoned = 1; break; }   /* the caller's array is full: stop, flag it, keep what is there */

        /* The primary pass's 12-bit-hash accounting (SUP-B, f001): count a display exactly where a result is emitted. */
        if (tls_h12_lookup_performed && tls_h12_resolved) {
            g_h12_displaying++;
            if (tls_h12_multiplicity >= 2) g_h12_ambiguous++;
            if (tls_h12_divergent)         g_h12_divergent++;
            if (tls_h12_suppressed)        g_h12_suppressed++;
            if (tls_h12_code >= H12_CODE_SPACE) g_h12_code_out_of_range++;
            uint32_t c = tls_h12_code & (H12_CODE_SPACE - 1u);
            g_h12_by_code_displaying[c]++;
            if (tls_h12_multiplicity >= 2) g_h12_by_code_ambiguous[c]++;
            if (tls_h12_divergent)         g_h12_by_code_divergent[c]++;
        } else if (tls_h12_lookup_performed && !tls_h12_resolved) {
            if (tls_h12_code >= H12_CODE_SPACE) g_h12_code_out_of_range++;
            uint32_t c = tls_h12_code & (H12_CODE_SPACE - 1u);
            g_h12_unresolved_by_code[c]++;
        }

        uint8_t tones[FT8_NN];
        ft8_encode(msg->payload, tones);
        float snr = ftz_snr_db(&mon, cand, tones, noise_floor_db);

        FT8Result* r = &results[nres];
        r->freq_hz = (int)roundf(hits[k].freq_hz);
        r->dt      = hits[k].dt;
        r->snr     = (int)roundf(snr);
        strncpy(r->message, text, 35);
        r->message[35] = '\0';
        memcpy(texts[nres], text, sizeof(texts[nres]));
        nres++;
        st->n_results = nres;                              /* visible even if a later step faults */
    }
    st->n_results         = nres;
    st->unpack_wall_us    = ftz_wall_us() - w0;
    st->unpack_cpu_us     = ftz_thread_cpu_us() - c0;
    rc = nres;

done:
    free(cands); free(msgs); free(ok); free(hits); free(texts); free(seen_payloads);
    tls_hash_table = NULL;
    monitor_free(&mon);
    st->total_wall_us = ftz_wall_us() - t_start;
    st->total_cpu_us  = st->spectrogram_cpu_us + st->candidates_cpu_us + st->tier_a_cpu_us + st->unpack_cpu_us;
    return rc;
}

int ftz_decode_cycle(const float* pcm, int n, const ftz_params_t* params, void* out_results, int cap, ftz_stats_t* out_stats)
{
    ftz_stats_t  local;
    ftz_stats_t* st = out_stats != NULL ? out_stats : &local;
    memset(st, 0, sizeof(*st));
    st->struct_size = (int32_t)sizeof(*st);

    if (params == NULL || params->struct_size < (int32_t)sizeof(int32_t) * 5 || out_results == NULL || cap <= 0 || n < 0 || (n > 0 && pcm == NULL))
    {
        st->error = FTZ_ERR_ARG;
        return FTZ_ERR_ARG;
    }

    /* A caller built against a shorter ftz_params_t (smaller struct_size) gets zero (= today's value) for the missing fields. */
    ftz_params_t p;
    memset(&p, 0, sizeof(p));
    {
        size_t have = (size_t)params->struct_size < sizeof(p) ? (size_t)params->struct_size : sizeof(p);
        memcpy(&p, params, have);
        p.struct_size = (int32_t)sizeof(p);
    }

    int rc;
    ftz_call_lock();
#ifdef _MSC_VER
    __try { rc = ftz_decode_cycle_impl(pcm, n, &p, (FT8Result*)out_results, cap, st); }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        /* As ft8_decode_all does: clear the thread-local table pointer; the spectrogram heap is deliberately not freed
         * (it may be corrupt). Results already counted in st->n_results stand. */
        tls_hash_table = NULL;
        rc = FTZ_ERR_FAULT;
    }
#else
    rc = ftz_decode_cycle_impl(pcm, n, &p, (FT8Result*)out_results, cap, st);
#endif
    ftz_call_unlock();
    st->error = rc < 0 ? rc : FTZ_OK;   /* error is the error code, never the result count */
    return rc;
}
