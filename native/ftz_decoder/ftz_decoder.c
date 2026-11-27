/*
 * ftz_decoder.c -- the lean decoder engine, steps 2a to 2c (DR-2, shim 20260073 to 20260075): ftz_decode_cycle.
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
 * Shape of a call (spec section 2.3, S1 + S2 steps 1 to 4, 6 and 7):
 *   S1  spectrogram (same monitor configuration as the primary pass: window, oversampling and scaling are closed arms)
 *   S2  candidates (ftx_find_candidates, today's primary parameters), tier A on every candidate IN PARALLEL on a fixed
 *       worker pool; tier B (the coherent fallback's per-candidate body, one coherent context per worker) on every candidate
 *       that failed tier A; CQ-AP (FR-103) on every candidate that failed both; then ON THE CALLING THREAD, in a fixed order: sort by (frequency, time, payload), unpack against the
 *       callsign table, de-duplicate by payload and by text, SNR, write the result.
 *   The sort happens before anything touches the callsign table, so the output does not depend on the thread count.
 *
 * Step 2c (S3, spec section 2.3), with FTZ_FLAG_ROUNDS, rounds 1 to 3 after round 0:
 *   (1) subtract every result not yet subtracted (re-encodable text only, SubtractionPass.IsReencodable; tones from the payload) from a
 *       residual buffer, with ft8_subfeas_fit_signal on the ORIGINAL audio's analytic signal (computed once), FTZ_FIT_CHUNK fits at a
 *       time on the worker pool and summed in the sorted result order; a fit that answers "no valid fit" (-3) contributes zero;
 *   (2) the residual's spectrogram in full; (3) ftx_find_candidates (floor s_k_min_score_pass2, cap 200), kept only within
 *       [f - 50, f + 100] Hz of a signal subtracted in THIS round; (4) tier A, tier B, CQ-AP on those; (5) the accept rules (payload
 *       dedup incl. the RR73-aware same transmission, text dedup, the residual tier-B rules). Stops when a round adds nothing, at the
 *       last round, or when the budget is gone; a round the budget stops publishes nothing (earlier rounds stand).
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
static void ftz_cond_wait_ms(ftz_cond_t* c, ftz_mutex_t* m, int64_t ms) { SleepConditionVariableCS(c, m, (DWORD)(ms < 1 ? 1 : (ms > 1000000 ? 1000000 : ms))); }
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
static void ftz_cond_wait_ms(ftz_cond_t* c, ftz_mutex_t* m, int64_t ms)
{
    struct timespec ts;                                  /* pthread_cond_timedwait's default clock is CLOCK_REALTIME */
    clock_gettime(CLOCK_REALTIME, &ts);
    if (ms < 1) ms = 1;
    ts.tv_sec  += (time_t)(ms / 1000);
    ts.tv_nsec += (long)(ms % 1000) * 1000000L;
    if (ts.tv_nsec >= 1000000000L) { ts.tv_sec += 1; ts.tv_nsec -= 1000000000L; }
    pthread_cond_timedwait(c, m, &ts);
}
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
 * cycle. A job is "run fn(ctx, i, worker) for i in [0, n_items)"; workers take items under the mutex, so each item runs exactly once,
 * and `worker` (0 .. n_threads-1, 0 for the calling thread when it runs inline) names the scratch state the item may use alone.
 * ftz_pool_run returns when every item is done. Only ever used under g_ftz_call_lock, so one job at a time.
 */
typedef void (*ftz_item_fn)(void* ctx, int item, int worker);

typedef struct ftz_pool ftz_pool_t;

typedef struct { ftz_pool_t* pool; int id; } ftz_worker_arg_t;

struct ftz_pool
{
    int              n_threads;
    int              n_started;
    ftz_thread_t     threads[FTZ_MAX_THREADS];
    ftz_worker_arg_t args[FTZ_MAX_THREADS];
    ftz_mutex_t      mu;
    ftz_cond_t       cv_work;
    ftz_cond_t       cv_done;
    unsigned         generation;     /* bumped for every job; a worker runs each generation once */
    int              stop;
    ftz_item_fn      fn;
    void*            ctx;
    int              n_items;
    int              next_item;
    int              n_finished;     /* workers that have finished the current generation        */
    int              fault;          /* an item raised an access violation (MSVC builds)         */
    int64_t          job_cpu_us;     /* CPU summed over the workers for the current job          */
};

static ftz_pool_t* g_ftz_pool = NULL;

/* One item under a guard: on MSVC an access violation in fn is caught and reported instead of ending the process. */
static int ftz_guarded_item(ftz_item_fn fn, void* ctx, int item, int worker)
{
#ifdef _MSC_VER
    __try { fn(ctx, item, worker); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return 1; }
    return 0;
#else
    fn(ctx, item, worker);
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
    ftz_worker_arg_t* wa = (ftz_worker_arg_t*)arg;
    ftz_pool_t* p = wa->pool;
    const int id = wa->id;
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
            if (ftz_guarded_item(fn, ctx, item, id)) faulted = 1;
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
        p->args[i].pool = p;
        p->args[i].id   = i;
        if (ftz_thread_start(&p->threads[i], ftz_worker_main, &p->args[i]) != 0) { ftz_pool_destroy(p); return NULL; }
        p->n_started++;
    }
    return p;
}

/* Returns 0 on success, 1 if an item faulted. Fills *cpu_us with the CPU the workers used. With cancel_flag and cancel_at_us (absolute ftz_wall_us)
 * the calling thread, while it waits, sets *cancel_flag (a volatile write) once that time has passed: the fits read it and stop. */
static int ftz_pool_run(ftz_pool_t* p, ftz_item_fn fn, void* ctx, int n_items, int64_t* cpu_us, volatile int* cancel_flag, int64_t cancel_at_us)
{
    ftz_mutex_lock(&p->mu);
    p->fn = fn; p->ctx = ctx; p->n_items = n_items; p->next_item = 0;
    p->n_finished = 0; p->fault = 0; p->job_cpu_us = 0;
    p->generation++;
    ftz_cond_broadcast(&p->cv_work);
    while (p->n_finished < p->n_started)
    {
        if (cancel_flag != NULL && cancel_at_us > 0)
        {
            int64_t left_us = cancel_at_us - ftz_wall_us();
            if (left_us <= 0) { *cancel_flag = 1; cancel_at_us = 0; continue; }
            ftz_cond_wait_ms(&p->cv_done, &p->mu, (left_us + 999) / 1000);
        }
        else
            ftz_cond_wait(&p->cv_done, &p->mu);
    }
    int fault = p->fault;
    if (cpu_us != NULL) *cpu_us = p->job_cpu_us;
    ftz_mutex_unlock(&p->mu);
    return fault;
}

/* One coherent context per worker (tier B's cf_ctx_t is not thread-safe), created on first use, kept until ftz_shutdown. */
static cf_ctx_t* g_ftz_cf[FTZ_MAX_THREADS];

void ftz_shutdown(void)
{
    ftz_call_lock();
    ftz_pool_destroy(g_ftz_pool);
    g_ftz_pool = NULL;
    for (int i = 0; i < FTZ_MAX_THREADS; ++i) { if (g_ftz_cf[i] != NULL) cf_ctx_free(g_ftz_cf[i]); g_ftz_cf[i] = NULL; }
    ftz_call_unlock();
}

/* Runs a job on the pool, or inline on the calling thread (worker 0) when there is no pool. Returns 1 on a fault. cancel_flag / cancel_at_us as
 * ftz_pool_run; inline, the flag is set between items (an item already running is not interrupted). */
static int ftz_run_job_ex(ftz_item_fn fn, void* ctx, int n_items, int use_pool, int64_t* cpu_us, volatile int* cancel_flag, int64_t cancel_at_us)
{
    if (use_pool && g_ftz_pool != NULL)
        return ftz_pool_run(g_ftz_pool, fn, ctx, n_items, cpu_us, cancel_flag, cancel_at_us);
    int64_t cc0 = ftz_thread_cpu_us();
    for (int i = 0; i < n_items; ++i)
    {
        if (cancel_flag != NULL && cancel_at_us > 0 && ftz_wall_us() >= cancel_at_us) *cancel_flag = 1;
        if (ftz_guarded_item(fn, ctx, i, 0)) return 1;
    }
    if (cpu_us != NULL) *cpu_us = ftz_thread_cpu_us() - cc0;
    return 0;
}

static int ftz_run_job(ftz_item_fn fn, void* ctx, int n_items, int use_pool, int64_t* cpu_us)
{
    return ftz_run_job_ex(fn, ctx, n_items, use_pool, cpu_us, NULL, 0);
}

/* ── The per-cycle work shared by the three tiers ─────────────────────────── */

#define FTZ_B_NONE      0   /* not eligible, or not reached                                            */
#define FTZ_B_SKIPPED   1   /* eligible, the budget ran out before it was attempted                    */
#define FTZ_B_NO_CRC    2   /* attempted, no CRC-valid output                                          */
#define FTZ_B_KNOWN     3   /* CRC-valid, the payload is one tier A produced                           */
#define FTZ_B_GATED_OUT 4   /* CRC-valid, a new payload, F1b above T1                                  */
#define FTZ_B_NEW_GATED 5   /* CRC-valid, a new payload, F1b <= T1: publishable                        */

/* SUB-PROBE: what each stage said about one candidate (written by the stage's own item, read on the calling thread afterwards). Only allocated with FTZ_FLAG_PROBE. */
typedef struct
{
    int32_t a_kind, a_err;                 /* tier A: 0 not run, 1 CRC-valid, 2 BP failed, 3 CRC failed, 4 degenerate; unsatisfied checks (BP failed)       */
    int32_t b_c3, b_rc, b_crc, b_err;      /* tier B: C3 ran, bp_rc, CRC ok, bp_ldpc_errors                                                                  */
    int32_t cq_ran, cq_err;                /* CQ-AP: attempted, unsatisfied checks                                                                           */
} ftz_pstat_t;

typedef struct
{
    const ftx_waterfall_t* wf;
    const ftx_candidate_t* cands;
    int                    n_cands;
    int                    ldpc_iterations;
    const float*           pcm_full;        /* FT8_EXPECTED_SAMPLES samples (zero-padded when the capture was shorter)           */
    int64_t                deadline_us;     /* absolute wall time (ftz_wall_us) after which tier B / CQ-AP items skip; 0 = none  */
    const uint8_t*         cq_force;        /* the CQ-AP force pattern, or NULL                                                   */
    /* per candidate, each item writes only its own index */
    float*                 pos_freq;        /* the candidate's lattice position as the primary pass computes it                   */
    float*                 pos_dt;
    ftx_message_t*         msgs;            /* tier A                                                                              */
    uint8_t*               ok_a;
    uint8_t*               b_eligible;      /* set before the job (main thread)                                                    */
    uint8_t*               b_state;         /* FTZ_B_*                                                                             */
    uint8_t*               b_edge;
    uint8_t                (*b_payload)[FTZ_PAYLOAD_BYTES];
    float*                 b_freq;          /* published position: anchor + estimate                                               */
    float*                 b_dt;
    int32_t*               b_snr;
    int                    n_known;         /* tier A payloads, in known[]                                                         */
    uint8_t              (*known)[FTZ_PAYLOAD_BYTES];
    uint8_t*               c_attempted;     /* CQ-AP                                                                               */
    uint8_t*               c_ok;
    ftx_message_t*         c_msgs;
    const uint8_t*         c_eligible;      /* set before the job                                                                  */
    ftz_pstat_t*           pstat;           /* SUB-PROBE: NULL unless FTZ_FLAG_PROBE; per candidate, each item writes only its own index                  */
} ftz_cycle_t;

static int ftz_deadline_passed(const ftz_cycle_t* c)
{
    return c->deadline_us != 0 && ftz_wall_us() >= c->deadline_us;
}

static void ftz_tier_a_item(void* vctx, int i, int worker)
{
    ftz_cycle_t* c = (ftz_cycle_t*)vctx;
    (void)worker;
    if (i < 0 || i >= c->n_cands) return;                 /* bounds: the item index is the pool's, the arrays are ours */
    ftx_decode_status_t status;
    memset(&status, 0, sizeof(status));
    c->ok_a[i] = ftx_decode_candidate_tier_a(c->wf, &c->cands[i], c->ldpc_iterations, &c->msgs[i], &status) ? 1u : 0u;
    if (c->pstat != NULL)                                  /* SUB-PROBE: read-only on the decode */
    {
        ftz_pstat_t* p = &c->pstat[i];
        if (c->ok_a[i])                                   p->a_kind = 1;
        else if (status.ldpc_errors > 0)                  { p->a_kind = 2; p->a_err = status.ldpc_errors; }
        else if (status.crc_extracted != status.crc_calculated) p->a_kind = 3;
        else                                              { p->a_kind = 4; p->a_err = -1; }     /* ldpc_errors 0 and no CRC computed: the degenerate-LLR guard */
    }
}

/* Tier B for one eligible candidate, on the worker's own coherent context: estimate, coherent LLRs (multi-set on), BP, CRC; then,
 * for a CRC-valid payload tier A did not produce, the coherent SNR and F1b against T1. The per-candidate body is
 * ft8_coherent_fallback_process's, statement for statement; what it does not do is touch any shared state. */
static void ftz_tier_b_item(void* vctx, int i, int worker)
{
    ftz_cycle_t* c = (ftz_cycle_t*)vctx;
    if (i < 0 || i >= c->n_cands || worker < 0 || worker >= FTZ_MAX_THREADS) return;
    if (!c->b_eligible[i]) return;
    if (ftz_deadline_passed(c)) { c->b_state[i] = FTZ_B_SKIPPED; return; }
    cf_ctx_t* ctx = g_ftz_cf[worker];
    if (ctx == NULL) { c->b_state[i] = FTZ_B_SKIPPED; return; }

    FT8CohFallbackResult r;
    cf_walk_info_t wi;
    const double f0 = (double)c->pos_freq[i], t0 = (double)c->pos_dt[i];
    cf_process_one(ctx, c->pcm_full, f0, t0, FT8_COH_FLAG_SKIP_F1B, &r, NULL, &wi);
    c->b_state[i] = FTZ_B_NO_CRC;
    if (c->pstat != NULL)                                  /* SUB-PROBE */
    {
        ftz_pstat_t* p = &c->pstat[i];
        p->b_c3 = r.c3_ran ? 1 : 0; p->b_rc = r.bp_rc; p->b_crc = r.bp_crc_ok ? 1 : 0; p->b_err = r.bp_ldpc_errors;
    }
    c->b_edge[i]  = r.edge ? 1u : 0u;
    c->b_freq[i]  = (float)(f0 + r.est_df_hz);
    c->b_dt[i]    = (float)(t0 + r.est_dt_s);
    if (!(r.c3_ran && r.bp_rc == 0 && r.bp_crc_ok)) return;
    memcpy(c->b_payload[i], r.a91, FTZ_PAYLOAD_BYTES);

    for (int k = 0; k < c->n_known; ++k)
        if (!memcmp(c->known[k], r.a91, FTZ_PAYLOAD_BYTES)) { c->b_state[i] = FTZ_B_KNOWN; return; }

    uint8_t tones[FT8_NN];
    ft8_encode(r.a91, tones);
    const double snr = cf_snr_db(ctx, tones);          /* the tone powers are in the context only until the next extraction */
    c->b_snr[i] = (int32_t)lround(isfinite(snr) ? snr : CF_SNR_FLOOR_DB);

    int nrefs = 0;
    const double f1b = cf_f1b_db(ctx, c->pcm_full, f0, t0, r.peak, &nrefs);
    c->b_state[i] = (f1b <= CF_T1_DB) ? FTZ_B_NEW_GATED : FTZ_B_GATED_OUT;   /* a NaN F1b compares false: gated out */
}

/* CQ-AP for one candidate that failed tier A and tier B (FR-103: BP only, the encoder's own CQ force pattern). */
static void ftz_cq_item(void* vctx, int i, int worker)
{
    ftz_cycle_t* c = (ftz_cycle_t*)vctx;
    (void)worker;
    if (i < 0 || i >= c->n_cands || !c->c_eligible[i] || c->cq_force == NULL) return;
    if (ftz_deadline_passed(c)) return;
    ftx_decode_status_t status;
    memset(&status, 0, sizeof(status));
    c->c_attempted[i] = 1u;
    c->c_ok[i] = ftx_decode_candidate_cq_ap(c->wf, &c->cands[i], c->ldpc_iterations, c->cq_force, &c->c_msgs[i], &status) ? 1u : 0u;
    if (c->pstat != NULL) { c->pstat[i].cq_ran = 1; c->pstat[i].cq_err = status.ldpc_errors; }   /* SUB-PROBE */
}

/* ── Ordering ─────────────────────────────────────────────────────────────── */

typedef struct
{
    float   freq_hz;
    float   dt;
    uint8_t payload[FTZ_PAYLOAD_BYTES];
    int     index;       /* into the candidate arrays */
    int     tier;        /* FTZ_TIER_* */
    int     ungated;     /* a residual tier-B row published only because the ungating is on */
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
    if (x->tier != y->tier) return x->tier - y->tier;
    return (x->index > y->index) - (x->index < y->index);  /* total order: identical hits keep a fixed order */
}

/* DR-3 duplicate rule, part 1 (the same payload twice in one round). hits[0..n) are ONE round's hits in published order (ascending frequency, then the
 * ftz_hit_cmp tie-breaks); payloads is n * FTZ_PAYLOAD_BYTES bytes and scores[k] the candidate sync score of hit k (ftx_candidate_t.score, the field
 * ftx_find_candidates ranks by; higher = more likely). Among hits that carry the same payload (round 0: bit-identical; a residual round: also the RR73-aware
 * same transmission, ftz_payload_same_qso), the one with the HIGHEST score survives; equal scores keep today's rule (the earlier hit in the order survives).
 * Hits already marked in drop[] are ignored; losers are marked drop[k] = 1. Returns the number newly dropped. Pure: no allocation, no state. */
int ftz_dedup_select(int round, int n, const uint8_t* payloads, const int32_t* scores, uint8_t* drop)
{
    int dropped = 0;
    if (n <= 0 || payloads == NULL || scores == NULL || drop == NULL) return 0;
    for (int k = 0; k < n; ++k)
    {
        if (drop[k]) continue;
        for (int j = 0; j < k; ++j)
        {
            if (drop[j]) continue;
            const uint8_t* pj = payloads + (size_t)j * FTZ_PAYLOAD_BYTES;
            const uint8_t* pk = payloads + (size_t)k * FTZ_PAYLOAD_BYTES;
            const int same = round == 0 ? (memcmp(pj, pk, FTZ_PAYLOAD_BYTES) == 0) : ftz_payload_same_qso(pj, pk);
            if (!same) continue;
            if (scores[k] > scores[j]) { drop[j] = 1; ++dropped; }       /* the later, stronger hit replaces the earlier one */
            else { drop[k] = 1; ++dropped; break; }                       /* a tie or a weaker hit never replaces the earlier one */
        }
    }
    return dropped;
}

/* DR-3 duplicate rule, part 2 (the same rendered text twice in one round, from two payloads): 1 if a new hit with sync score new_score replaces the result already
 * published this round with score old_score (strictly higher only; equal scores keep the earlier result). */
int ftz_text_replace_wins(int new_score, int old_score)
{
    return new_score > old_score ? 1 : 0;
}

/* The 12-bit-hash accounting of one published result (SUP-B, f001), kept per result so that a result replaced by the duplicate rule can be un-counted: the
 * counters are "a display counted exactly where a result is emitted", and a replaced result is no longer emitted. */
typedef struct
{
    uint8_t  performed, resolved, ambiguous, divergent, suppressed;
    uint32_t code;
} ftz_h12_t;

static ftz_h12_t ftz_h12_capture(void)
{
    ftz_h12_t a;
    a.performed  = tls_h12_lookup_performed ? 1u : 0u;
    a.resolved   = tls_h12_resolved ? 1u : 0u;
    a.ambiguous  = tls_h12_multiplicity >= 2 ? 1u : 0u;
    a.divergent  = tls_h12_divergent ? 1u : 0u;
    a.suppressed = tls_h12_suppressed ? 1u : 0u;
    a.code       = tls_h12_code;
    return a;
}

/* delta = +1 counts the display (exactly the counters the loop incremented before this change), -1 takes it back. */
static void ftz_h12_apply(const ftz_h12_t* a, int delta)
{
    if (!a->performed) return;
    const uint32_t c = a->code & (H12_CODE_SPACE - 1u);
    if (a->code >= H12_CODE_SPACE) g_h12_code_out_of_range += delta;
    if (a->resolved)
    {
        g_h12_displaying += delta;
        if (a->ambiguous)  g_h12_ambiguous += delta;
        if (a->divergent)  g_h12_divergent += delta;
        if (a->suppressed) g_h12_suppressed += delta;
        g_h12_by_code_displaying[c] += delta;
        if (a->ambiguous)  g_h12_by_code_ambiguous[c] += delta;
        if (a->divergent)  g_h12_by_code_divergent[c] += delta;
    }
    else
    {
        g_h12_unresolved_by_code[c] += delta;
    }
}

/* ── SUB-PROBE helpers (test-only; never called without FTZ_FLAG_PROBE) ─────────────────────────────────────────────────────────────────────────────────── */

/* Appends a row; returns its index, or -1 (and sets overflow) when the caller's buffer is full. Nothing is ever written past rows[cap - 1]. */
static int ftz_probe_add(ftz_probe_t* pb, const ftz_probe_row_t* row)
{
    if (pb == NULL) return -1;
    if (pb->n < 0 || pb->n >= pb->cap) { pb->overflow = 1; return -1; }
    pb->rows[pb->n] = *row;
    return pb->n++;
}

/* The row at index ix, or NULL when ix is not a row written in this call. */
static ftz_probe_row_t* ftz_probe_at(ftz_probe_t* pb, int ix)
{
    return (pb != NULL && ix >= 0 && ix < pb->n && ix < pb->cap) ? &pb->rows[ix] : NULL;
}

/* The power in a signal's footprint on a waterfall: the 8 tone columns x 79 symbols, summed over the waterfall cells nearest to the signal's frequency and time
 * (the frequency and time subdivision the candidate search would use for the position). Cells outside the waterfall are skipped. Returns the summed linear power
 * (the waterfall's uint8 is 2 dB + 240, so WF_ELEM_MAG is dB), or -1 when fewer than half of the 632 cells are inside. Reads the waterfall only. */
static double ftz_probe_footprint_power(const ftx_waterfall_t* wf, float min_bin, float symbol_period, float freq_hz, float dt_s)
{
    if (wf == NULL || wf->mag == NULL || wf->num_blocks <= 0 || wf->num_bins <= 0 || wf->time_osr <= 0 || wf->freq_osr <= 0 || !(symbol_period > 0.0f)) return -1.0;
    if (!isfinite(freq_hz) || !isfinite(dt_s)) return -1.0;
    const float y  = freq_hz * symbol_period - min_bin;
    int   fb = (int)floorf(y);
    int   fs = (int)lroundf((y - (float)fb) * (float)wf->freq_osr);
    if (fs >= wf->freq_osr) { fs -= wf->freq_osr; fb++; }
    double sum = 0.0;
    int cells = 0;
    for (int sym = 0; sym < FT8_NN; ++sym)
    {
        const float x  = dt_s / symbol_period + (float)sym;
        int   tb = (int)floorf(x);
        int   ts = (int)lroundf((x - (float)tb) * (float)wf->time_osr);
        if (ts >= wf->time_osr) { ts -= wf->time_osr; tb++; }
        if (tb < 0 || tb >= wf->num_blocks) continue;
        for (int tone = 0; tone < 8; ++tone)
        {
            const int bin = fb + tone;
            if (bin < 0 || bin >= wf->num_bins) continue;
            const WF_ELEM_T v = wf->mag[(size_t)tb * (size_t)wf->block_stride + (size_t)((ts * wf->freq_osr + fs) * wf->num_bins + bin)];
            sum += pow(10.0, (double)WF_ELEM_MAG(v) / 10.0);
            ++cells;
        }
    }
    return cells * 2 >= FT8_NN * 8 ? sum : -1.0;
}

#define FTZ_PO_PENDING   (-1)   /* internal: a hit that has not reached an outcome yet */
#define FTZ_PROBE_LOW_CAP 400   /* the LOW search's cap */
#define FTZ_PROBE_NO_SUPP (-999.0f)

/* Fills one CAND row's stage columns and its exclusive outcome. po / pg: what the publish loop decided for a candidate that produced a hit (0 = not a hit). */
static void ftz_probe_finish_cand(ftz_probe_row_t* row, int round, const ftz_pstat_t* ps, int ok_a, int b_el, int b_st, int c_at, int c_ok, int no_tier_b, int po, int pg)
{
    row->a_code = ps->a_kind;                                   /* 0 not run, 1 ok, 2 BP, 3 CRC, 4 degenerate */
    row->a_unsat = ps->a_kind == 2 || ps->a_kind == 4 ? ps->a_err : -1;
    row->cq_code = c_at ? (c_ok ? 2 : 1) : 0;
    row->cq_unsat = c_at && !c_ok ? ps->cq_err : -1;
    int bcode = 0, bunsat = -1;
    if (b_el)
    {
        if (b_st == FTZ_B_SKIPPED)       bcode = 1;
        else if (b_st == FTZ_B_NONE)     bcode = 0;
        else if (!ps->b_c3)              bcode = 2;
        else if (ps->b_rc != 0)          { bcode = 3; bunsat = -1; }
        else if (ps->b_crc)              bcode = 6;
        else if (ps->b_err > 0)          { bcode = 4; bunsat = ps->b_err; }
        else                             bcode = 5;
    }
    row->b_code = bcode; row->b_unsat = bunsat;

    int outcome = FTZ_PO_UNSET, gate = FTZ_PG_NONE;
    if (po > 0) { outcome = po; gate = pg; }
    else if (b_st == FTZ_B_GATED_OUT) { outcome = FTZ_PO_GATE; gate = round == 0 ? FTZ_PG_F1B : FTZ_PG_F1B_RESIDUAL; }   /* CRC-valid, new payload, not accepted */
    else if (b_st == FTZ_B_KNOWN)     outcome = FTZ_PO_DUP;                                                              /* CRC-valid, a payload tier A produced */
    else if (ok_a || c_ok)            outcome = FTZ_PO_DUP;                                                              /* a decode that never reached the publish step */
    else if (c_at)                    outcome = FTZ_PO_CQ_FAIL;
    else if (b_el && b_st == FTZ_B_SKIPPED) outcome = FTZ_PO_B_SKIP;
    else if (b_el && b_st == FTZ_B_NO_CRC)  outcome = bcode == 2 ? FTZ_PO_B_NOC3 : (bcode == 5 ? FTZ_PO_B_CRC : FTZ_PO_B_BP);
    else if (!b_el && !no_tier_b)     outcome = FTZ_PO_B_NE;
    else                              outcome = ps->a_kind == 3 ? FTZ_PO_A_CRC : FTZ_PO_A_BP;                           /* tier B off: tier A's failure is the last stage */
    row->outcome = outcome; row->gate = gate;
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

/* ── Step 2c: the accept rules, as pure functions (exported for the unit tests; the cycle calls the same code) ─────────────────────────────── */

int ftz_patch_keep(float base_hz, const float* sub_hz, int n_sub)
{
    if (sub_hz == NULL || n_sub <= 0) return 0;
    for (int i = 0; i < n_sub; ++i)
        if (base_hz >= sub_hz[i] - FTZ_PATCH_BELOW_HZ && base_hz <= sub_hz[i] + FTZ_PATCH_ABOVE_HZ) return 1;    /* false for NaN */
    return 0;
}

/* Step 2e (D3): see ftz_decoder.h. The same window as ftz_patch_keep, read the other way round: the failed candidate must lie in [f - 50, f + 100] of the result. */
int ftz_fit_needed(float result_hz, const float* failed_hz, int n_failed)
{
    if (failed_hz == NULL || n_failed <= 0) return 0;
    for (int i = 0; i < n_failed; ++i)
        if (failed_hz[i] >= result_hz - FTZ_PATCH_BELOW_HZ && failed_hz[i] <= result_hz + FTZ_PATCH_ABOVE_HZ) return 1;    /* false for NaN */
    return 0;
}

/* Bits [lo, hi) of a 77-bit payload, MSB first (message.c's layout; SubfeasPayload's field boundaries); hi - lo <= 32. */
static uint32_t ftz_bits77(const uint8_t* p, int lo, int hi)
{
    uint32_t v = 0;
    for (int i = lo; i < hi; ++i) v = (v << 1) | (uint32_t)((p[i >> 3] >> (7 - (i & 7))) & 1u);
    return v;
}

#define FTZ_MAXGRID4        32400u
#define FTZ_RR73_STD_IGRID4 (FTZ_MAXGRID4 + 3u)    /* this encoder's own RR73 sentinel (SubfeasPayload.Rr73Std)        */
#define FTZ_RR73_AIR_IGRID4 32373u                 /* the value a genuine on-air RR73 carries (SubfeasPayload.Rr73OnAirIgrid4) */

int ftz_payload_same_qso(const uint8_t* known, const uint8_t* cand)
{
    if (known == NULL || cand == NULL) return 0;
    if (memcmp(known, cand, 9) == 0 && ((known[9] ^ cand[9]) & 0xF8u) == 0) return 1;             /* the 77 bits are equal */
    if (ftz_bits77(known, 74, 77) != 1u || ftz_bits77(known, 58, 59) != 0u || ftz_bits77(known, 59, 74) != FTZ_RR73_STD_IGRID4) return 0;
    return ftz_bits77(cand, 74, 77) == 1u
        && ftz_bits77(cand, 0, 29) == ftz_bits77(known, 0, 29)
        && ftz_bits77(cand, 29, 58) == ftz_bits77(known, 29, 58)
        && ftz_bits77(cand, 58, 59) == 0u
        && ftz_bits77(cand, 59, 74) == FTZ_RR73_AIR_IGRID4;
}

int ftz_residual_b_accept(int f1b_passed, int published_freq_hz, int ungated_on, int rescand_on, int* ungated_out)
{
    if (ungated_out != NULL) *ungated_out = 0;
    (void)published_freq_hz; (void)rescand_on;       /* step 2e (D4): the residual-candidates flag no longer restricts a residual row, and no frequency rule applies */
    if (f1b_passed) return 1;
    if (!ungated_on) return 0;
    if (ungated_out != NULL) *ungated_out = 1;                                           /* published ONLY because the ungating is on */
    return 1;
}

/* The buffer tier B, the analytic signal and the residual read: the capture as 15 s of samples, zero-padded when it is shorter. NULL: no memory. */
static const float* ftz_full_buffer(const float* pcm, int n, float** pad)
{
    if (n >= FT8_EXPECTED_SAMPLES) return pcm;
    if (*pad == NULL)
    {
        *pad = (float*)calloc((size_t)FT8_EXPECTED_SAMPLES, sizeof(float));
        if (*pad == NULL) return NULL;
        if (n > 0) memcpy(*pad, pcm, (size_t)n * sizeof(float));
    }
    return *pad;
}

/* The worker pool for a job of n_items: created once, rebuilt only when the configured count changes; none when one thread (or one item) is asked for. */
static int ftz_prepare_pool(int threads, int n_items)
{
    int use_pool = 0;
    if (threads > 1 && n_items > 1)
    {
        if (g_ftz_pool != NULL && g_ftz_pool->n_threads != threads) { ftz_pool_destroy(g_ftz_pool); g_ftz_pool = NULL; }
        if (g_ftz_pool == NULL) g_ftz_pool = ftz_pool_create(threads);   /* NULL: fall back to inline */
        use_pool = g_ftz_pool != NULL;
    }
    else if (g_ftz_pool != NULL && threads == 1)
    {
        ftz_pool_destroy(g_ftz_pool);
        g_ftz_pool = NULL;
    }
    return use_pool;
}

/* ── The fits of one round (one item per signal, FTZ_FIT_CHUNK at a time) ──────────────────────────────────────────────────────────────────── */

#define FTZ_FIT_CHUNK 16   /* signals fitted per job: bounds the shat buffers (16 x 720 kB) and is independent of the thread count, so the sum is too */

typedef char ftz_assert_pcm_len[(FT8_EXPECTED_SAMPLES == 180000) ? 1 : -1];   /* SUBFEAS_PCM_LEN */

typedef struct
{
    const float*    xa_re;
    const float*    xa_im;
    int             n;
    uint8_t         tones[FTZ_FIT_CHUNK][FT8_NN];
    float           dt[FTZ_FIT_CHUNK];
    float           freq[FTZ_FIT_CHUNK];
    int             rc[FTZ_FIT_CHUNK];
    float*          shat;                 /* FTZ_FIT_CHUNK x FT8_EXPECTED_SAMPLES */
    volatile int*   cancel;
} ftz_fit_job_t;

static void ftz_fit_item(void* vctx, int i, int worker)
{
    ftz_fit_job_t* j = (ftz_fit_job_t*)vctx;
    (void)worker;
    if (i < 0 || i >= j->n || i >= FTZ_FIT_CHUNK) return;
    j->rc[i] = ft8_subfeas_fit_signal(j->xa_re, j->xa_im, j->tones[i], j->dt[i], j->freq[i],
                                      j->shat + (size_t)i * (size_t)FT8_EXPECTED_SAMPLES, j->cancel);
}

/* The round-0 hand-off under a guard: on MSVC an access violation in the callee is caught and reported (1). */
static int ftz_call_round0(ftz_round0_fn fn, void* ctx, int n, const FT8Result* results, const uint8_t* tiers)
{
#ifdef _MSC_VER
    __try { fn(ctx, n, results, tiers); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return 1; }
    return 0;
#else
    fn(ctx, n, results, tiers);
    return 0;
#endif
}

static int ftz_decode_cycle_impl(const float* pcm, int n, const ftz_params_t* params, FT8Result* results, int cap, uint8_t* out_tiers, uint8_t* out_rounds, ftz_stats_t* st)
{
    const int64_t t_start = ftz_wall_us();

    /* Parameters: zero = today's primary value; everything clamped. */
    int threads  = params->threads         != 0 ? params->threads         : FTZ_DEFAULT_THREADS;
    int min_sc   = params->min_score       != 0 ? params->min_score       : FTZ_DEFAULT_MIN_SCORE;
    int max_c    = params->max_candidates  != 0 ? params->max_candidates  : FTZ_DEFAULT_MAX_CANDIDATES;
    int ldpc_it  = params->ldpc_iterations != 0 ? params->ldpc_iterations : FTZ_DEFAULT_LDPC_ITERATIONS;
    const int want_cq      = (params->flags & FTZ_FLAG_CQ_AP) != 0;
    const int loop_on      = (params->flags & FTZ_FLAG_ROUNDS) != 0;
    const int ungated_on   = (params->flags & FTZ_FLAG_RESIDUAL_UNGATED) != 0;
    const int rescand_on   = (params->flags & FTZ_FLAG_RESIDUAL_CANDS) != 0;
    const int no_tier_b    = (params->flags & FTZ_FLAG_NO_TIER_B) != 0;
    const int skip_fits    = (params->flags & FTZ_FLAG_SKIP_FITS) != 0;
    const int inject_round = params->inject_error_round;
    /* SUB-PROBE: the caller's buffer, only with the flag; reset here so even an early return leaves n = 0. */
    ftz_probe_t* pb = NULL;
    if ((params->flags & FTZ_FLAG_PROBE) != 0 && (size_t)params->struct_size >= sizeof(ftz_params_t) && params->probe != NULL
        && params->probe->rows != NULL && params->probe->cap > 0 && params->probe->struct_size >= (int32_t)sizeof(ftz_probe_t))
        pb = params->probe;
    if (pb != NULL) { pb->n = 0; pb->overflow = 0; }
    ftz_round0_fn r0cb     = params->round0_cb;
    void*         r0ctx    = params->round0_ctx;
    float*        out_resid = params->out_residual;
    int max_rounds = params->max_rounds != 0 ? params->max_rounds : FTZ_MAX_ROUNDS;
    max_rounds = ftz_clamp_int(max_rounds, 1, FTZ_MAX_ROUNDS);
    const int rounds_to_run = loop_on ? max_rounds : 0;
    int64_t deadline_us = 0;
    if (params->flags & FTZ_FLAG_BUDGET)
    {
        int64_t b = params->budget_ms < 0 ? 0 : (int64_t)params->budget_ms;
        deadline_us = t_start + b * 1000;
        if (deadline_us == 0) deadline_us = 1;      /* 0 is "no deadline"; a budget of 0 ms at t = 0 still means "none left" */
    }
    threads = ftz_clamp_int(threads, FTZ_MIN_THREADS, FTZ_MAX_THREADS);
    max_c   = ftz_clamp_int(max_c, 1, FTZ_MAX_CANDIDATES);
    ldpc_it = ftz_clamp_int(ldpc_it, 1, 1000);
    min_sc  = ftz_clamp_int(min_sc, 0, 32767);
    /* A residual search takes today's pass-1 values: floor s_k_min_score_pass2 (decoder setting, default 10), cap 200, 50 iterations. A caller-lowered
     * candidate cap (tests) lowers the residual cap too. */
    const int res_min_sc = ftz_clamp_int(s_k_min_score_pass2, 0, 32767);
    int res_cap = params->max_candidates != 0 ? (max_c < K_MAX_CANDIDATES_PASS2 ? max_c : K_MAX_CANDIDATES_PASS2) : K_MAX_CANDIDATES_PASS2;
    res_cap = ftz_clamp_int(res_cap, 1, FTZ_MAX_CANDIDATES);
    const int alloc_c = max_c > res_cap ? max_c : res_cap;                    /* every per-candidate array has this many entries */
    const int rcap    = cap < alloc_c * (FTZ_MAX_ROUNDS + 1) ? cap : alloc_c * (FTZ_MAX_ROUNDS + 1);   /* results the cycle can hold */
    const int scap    = alloc_c * (FTZ_MAX_ROUNDS + 1);                       /* payloads seen: at most one per candidate per round */
    const int kcap    = scap + alloc_c;                                       /* tier B's known list: those, plus this round's tier A */
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
    st->rounds[0].spec_wall_us = st->spectrogram_wall_us;
    st->rounds[0].spec_cpu_us  = st->spectrogram_cpu_us;

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
    float* pcm_pad = NULL;
    ftx_candidate_t* cands = (ftx_candidate_t*)calloc((size_t)alloc_c, sizeof(ftx_candidate_t));
    ftx_message_t*   msgs  = (ftx_message_t*)calloc((size_t)alloc_c, sizeof(ftx_message_t));
    ftx_message_t*   cmsgs = (ftx_message_t*)calloc((size_t)alloc_c, sizeof(ftx_message_t));
    uint8_t*         ok_a  = (uint8_t*)calloc((size_t)alloc_c, 1);
    uint8_t*         b_el  = (uint8_t*)calloc((size_t)alloc_c, 1);
    uint8_t*         b_st  = (uint8_t*)calloc((size_t)alloc_c, 1);
    uint8_t*         b_ed  = (uint8_t*)calloc((size_t)alloc_c, 1);
    uint8_t*         c_el  = (uint8_t*)calloc((size_t)alloc_c, 1);
    uint8_t*         c_at  = (uint8_t*)calloc((size_t)alloc_c, 1);
    uint8_t*         c_ok  = (uint8_t*)calloc((size_t)alloc_c, 1);
    float*           pos_f = (float*)calloc((size_t)alloc_c, sizeof(float));
    float*           pos_t = (float*)calloc((size_t)alloc_c, sizeof(float));
    float*           b_fr  = (float*)calloc((size_t)alloc_c, sizeof(float));
    float*           b_dt  = (float*)calloc((size_t)alloc_c, sizeof(float));
    int32_t*         b_snr = (int32_t*)calloc((size_t)alloc_c, sizeof(int32_t));
    uint8_t (*b_pl)[FTZ_PAYLOAD_BYTES]    = (uint8_t (*)[FTZ_PAYLOAD_BYTES])calloc((size_t)alloc_c, FTZ_PAYLOAD_BYTES);
    uint8_t (*known)[FTZ_PAYLOAD_BYTES]   = (uint8_t (*)[FTZ_PAYLOAD_BYTES])calloc((size_t)kcap, FTZ_PAYLOAD_BYTES);
    ftz_hit_t*       hits  = (ftz_hit_t*)calloc((size_t)alloc_c * 2, sizeof(ftz_hit_t));
    uint8_t*         drop  = (uint8_t*)calloc((size_t)alloc_c * 2, 1);
    char (*texts)[FTX_MAX_MESSAGE_LENGTH + 1] = (char (*)[FTX_MAX_MESSAGE_LENGTH + 1])calloc((size_t)rcap, FTX_MAX_MESSAGE_LENGTH + 1);
    uint8_t (*seen_payloads)[FTZ_PAYLOAD_BYTES] = (uint8_t (*)[FTZ_PAYLOAD_BYTES])calloc((size_t)scap, FTZ_PAYLOAD_BYTES);
    uint8_t (*res_pl)[FTZ_PAYLOAD_BYTES]  = (uint8_t (*)[FTZ_PAYLOAD_BYTES])calloc((size_t)rcap, FTZ_PAYLOAD_BYTES);   /* the payload of each published result */
    int32_t*         res_score = (int32_t*)calloc((size_t)rcap, sizeof(int32_t));   /* DR-3: the candidate sync score of each published result */
    uint8_t*         res_tier  = (uint8_t*)calloc((size_t)rcap, 1);                 /* DR-3: its tier, and whether it was an ungated tier-B row, for the counters */
    uint8_t*         res_ungated = (uint8_t*)calloc((size_t)rcap, 1);
    ftz_h12_t*       res_h12   = (ftz_h12_t*)calloc((size_t)rcap, sizeof(ftz_h12_t));
    uint8_t*         sel_pl    = (uint8_t*)calloc((size_t)alloc_c * 2, FTZ_PAYLOAD_BYTES);   /* DR-3: one round's hit payloads and scores, for ftz_dedup_select */
    int32_t*         sel_sc    = (int32_t*)calloc((size_t)alloc_c * 2, sizeof(int32_t));
    int32_t*         fit_ix = (int32_t*)calloc((size_t)rcap, sizeof(int32_t)); /* the results a round fits */
    float*           sub_hz = (float*)calloc((size_t)rcap, sizeof(float));     /* the frequencies the round subtracted */
    float*           fail_hz = (float*)calloc((size_t)alloc_c, sizeof(float)); /* step 2e: base frequencies of the last round's candidates that did not decode */
    int              n_fail = 0;
    /* Allocated at the first round only: the residual, the analytic signal of the ORIGINAL audio, the fit job (with its 16 shat buffers). */
    float*           resid  = NULL;
    float*           xa_re  = NULL;
    float*           xa_im  = NULL;
    ftz_fit_job_t*   fitjob = NULL;
    const float*     full0  = NULL;
    /* SUB-PROBE state: allocated only with the flag (NULL otherwise: no memory, no work). */
    int32_t*         pr_row  = NULL;   /* the probe row of each candidate of the round              */
    int32_t*         pr_out  = NULL;   /* the publish loop's outcome for each candidate (0 = none, FTZ_PO_PENDING = a hit not yet decided) */
    int32_t*         pr_gate = NULL;
    ftz_pstat_t*     pstat   = NULL;
    int32_t*         res_cidx = NULL;  /* the candidate index of each published result (this round)  */
    int32_t*         sub_rows = NULL;  /* the SUB rows of the round and the footprint power before its subtraction */
    double*          sub_before = NULL;
    ftx_candidate_t* low_buf = NULL;
    int              resid_valid = 0;     /* resid holds the original minus every subtraction of the rounds that completed */
    if (cands == NULL || msgs == NULL || cmsgs == NULL || ok_a == NULL || b_el == NULL || b_st == NULL || b_ed == NULL || c_el == NULL
        || c_at == NULL || c_ok == NULL || pos_f == NULL || pos_t == NULL || b_fr == NULL || b_dt == NULL || b_snr == NULL || b_pl == NULL
        || known == NULL || hits == NULL || drop == NULL || texts == NULL || seen_payloads == NULL || res_pl == NULL
        || res_score == NULL || res_tier == NULL || res_ungated == NULL || res_h12 == NULL || sel_pl == NULL || sel_sc == NULL
        || fit_ix == NULL || sub_hz == NULL || fail_hz == NULL)
    {
        rc = FTZ_ERR_NOMEM;
        goto done;
    }

    if (pb != NULL)
    {
        pr_row  = (int32_t*)calloc((size_t)alloc_c, sizeof(int32_t));
        pr_out  = (int32_t*)calloc((size_t)alloc_c, sizeof(int32_t));
        pr_gate = (int32_t*)calloc((size_t)alloc_c, sizeof(int32_t));
        pstat   = (ftz_pstat_t*)calloc((size_t)alloc_c, sizeof(ftz_pstat_t));
        res_cidx = (int32_t*)calloc((size_t)rcap, sizeof(int32_t));
        sub_rows = (int32_t*)calloc((size_t)rcap, sizeof(int32_t));
        sub_before = (double*)calloc((size_t)rcap, sizeof(double));
        low_buf = (ftx_candidate_t*)calloc((size_t)FTZ_PROBE_LOW_CAP, sizeof(ftx_candidate_t));
        if (pr_row == NULL || pr_out == NULL || pr_gate == NULL || pstat == NULL || res_cidx == NULL || sub_rows == NULL || sub_before == NULL || low_buf == NULL)
        {
            pb->overflow = 1;                      /* no memory for the probe: the cycle goes on without it (it never touches the decode) */
            pb = NULL;
        }
    }

    uint8_t cq_force[FTX_LDPC_N];
    const int cq_on = want_cq && cq_ap_build_force(cq_force) > 0;

    int nres = 0, nseen = 0, n_sub_done = 0;
    int use_pool = 0;

    /* ── The rounds: round 0 is the step-2a/2b decode of the capture; rounds 1 to 3 (FTZ_FLAG_ROUNDS) subtract what is not yet subtracted, re-compute the
     * residual's spectrogram and decode only the candidates near the signals just subtracted. ── */
    for (int round = 0; round <= rounds_to_run; ++round)
    {
        ftz_round_stats_t* rs = &st->rounds[round];
        int ncands;
        int n_sub_round = 0;
        int n_sub_probe = 0;       /* SUB-PROBE: SUB rows written this round */

        if (round == 0)
        {
            /* ── S2 step 1: candidates ── */
            w0 = ftz_wall_us(); c0 = ftz_thread_cpu_us();
            ncands = ftx_find_candidates(&mon.wf, max_c, cands, min_sc);
            if (ncands < 0) ncands = 0;
            if (ncands > max_c) ncands = max_c;
            rs->n_found = ncands; rs->n_kept = ncands;
            st->candidates_wall_us += ftz_wall_us() - w0;
            st->candidates_cpu_us  += ftz_thread_cpu_us() - c0;
            rs->search_wall_us = ftz_wall_us() - w0;
            rs->search_cpu_us  = ftz_thread_cpu_us() - c0;
        }
        else
        {
            /* ── S3 (1): what is not yet subtracted. PAYLOAD-FIT: every result is fitted, the tones come from the payload, never from the text ── */
            int nfit = 0;
            for (int k = n_sub_done; k < nres; ++k)
            {
                /* Step 2e (D3): the fit is skipped when no candidate of the round that found this result failed to decode in its patch window. */
                if (skip_fits && !ftz_fit_needed((float)results[k].freq_hz, fail_hz, n_fail)) { rs->n_fit_skipped++; continue; }
                fit_ix[nfit++] = k;
            }
            n_sub_done = nres;
            if (nfit == 0) break;                                    /* nothing to subtract: nothing new can be found */
            if (deadline_us != 0 && deadline_us - ftz_wall_us() < (int64_t)FTZ_RESIDUAL_RESERVE_MS * 1000) { st->abandoned = 1; break; }   /* not started with less than the reserve left */
            st->n_rounds++;
            rs->n_fits = nfit;

            if (resid == NULL)
            {
                full0 = ftz_full_buffer(pcm, n, &pcm_pad);
                resid  = (float*)malloc((size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
                xa_re  = (float*)malloc((size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
                xa_im  = (float*)malloc((size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
                fitjob = (ftz_fit_job_t*)calloc(1, sizeof(ftz_fit_job_t));
                if (fitjob != NULL) fitjob->shat = (float*)malloc((size_t)FTZ_FIT_CHUNK * (size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
                if (full0 == NULL || resid == NULL || xa_re == NULL || xa_im == NULL || fitjob == NULL || fitjob->shat == NULL) { rc = FTZ_ERR_NOMEM; goto done; }
                memcpy(resid, full0, (size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
                int arc = ft8_subfeas_compute_analytic(full0, xa_re, xa_im);     /* ONE per cycle, read-only for every fit */
                if (arc == -2) { rc = FTZ_ERR_FAULT; goto done; }
                if (arc != 0)  { rc = FTZ_ERR_NOMEM; goto done; }
                use_pool = ftz_prepare_pool(threads, nfit);
                ft8_subfeas_pool_configure(use_pool && g_ftz_pool != NULL ? g_ftz_pool->n_threads : 1);
            }
            else
            {
                use_pool = ftz_prepare_pool(threads, nfit);
                ft8_subfeas_pool_configure(use_pool && g_ftz_pool != NULL ? g_ftz_pool->n_threads : 1);
            }
            if (use_pool && g_ftz_pool != NULL) st->threads = g_ftz_pool->n_threads;

            /* ── S3 (1, continued): the fits, a chunk at a time on the pool; each chunk is summed into the residual in the sorted result order ── */
            w0 = ftz_wall_us();
            resid_valid = 0;                                                  /* step 2e (D5): from here to the end of the sums the buffer is half-subtracted; only a round that completes makes it a residual */
            volatile int cancel = 0;
            const int64_t fit_cancel_at = deadline_us != 0 ? deadline_us - (int64_t)FTZ_RESIDUAL_RESERVE_MS * 1000 : 0;
            int cancelled = 0;
            for (int j0 = 0; j0 < nfit && !cancelled; j0 += FTZ_FIT_CHUNK)
            {
                const int m = (nfit - j0) < FTZ_FIT_CHUNK ? (nfit - j0) : FTZ_FIT_CHUNK;
                fitjob->xa_re = xa_re; fitjob->xa_im = xa_im; fitjob->n = m; fitjob->cancel = &cancel;
                for (int t = 0; t < m; ++t)
                {
                    const int k = fit_ix[j0 + t];
                    ft8_encode(res_pl[k], fitjob->tones[t]);                  /* the tones come from the payload, not from the text */
                    fitjob->dt[t]   = results[k].dt;
                    fitjob->freq[t] = (float)results[k].freq_hz;
                    fitjob->rc[t]   = 0;
                }
                int64_t cpu_us = 0;
                if (ftz_run_job_ex(ftz_fit_item, fitjob, m, use_pool, &cpu_us, &cancel, fit_cancel_at)) { rc = FTZ_ERR_FAULT; goto done; }
                rs->fit_cpu_us += cpu_us;
                for (int t = 0; t < m; ++t)
                {
                    const int frc = fitjob->rc[t];
                    if (frc == -4) cancelled = 1;                              /* the deadline flag: a deadline outcome, not an error */
                    else if (frc == -3) rs->n_fit_none++;                      /* "no valid fit": contributes zero */
                    else if (frc == -2) { rc = FTZ_ERR_FAULT; goto done; }     /* an access violation the fit caught */
                    else if (frc != 0)  { rc = FTZ_ERR_NOMEM; goto done; }     /* -1: a bad argument or no workspace */
                }
                if (cancelled) break;
                int64_t sc0 = ftz_thread_cpu_us();
                for (int t = 0; t < m; ++t)                                    /* sorted order: the residual is the same bytes at any thread count */
                {
                    if (fitjob->rc[t] != 0) continue;
                    const float* sh = fitjob->shat + (size_t)t * (size_t)FT8_EXPECTED_SAMPLES;
                    for (int s = 0; s < FT8_EXPECTED_SAMPLES; ++s) resid[s] -= sh[s];
                    sub_hz[n_sub_round++] = (float)results[fit_ix[j0 + t]].freq_hz;
                    rs->n_subtracted++;
                    if (pb != NULL)                                            /* SUB-PROBE: read-only; the footprint power BEFORE is read from the waterfall the round was searched on */
                    {
                        const FT8Result* sr = &results[fit_ix[j0 + t]];
                        double e2 = 0.0;
                        for (int s = 0; s < FT8_EXPECTED_SAMPLES; ++s) e2 += (double)sh[s] * (double)sh[s];
                        ftz_probe_row_t row;
                        memset(&row, 0, sizeof(row));
                        row.kind = FTZ_PROBE_SUB; row.round = round; row.freq_hz = (float)sr->freq_hz; row.time_s = sr->dt;
                        row.amp = (float)sqrt(2.0 * e2 / ((double)FT8_NN * (double)mon.block_size * 2.0)) ;
                        row.supp_db = FTZ_PROBE_NO_SUPP;
                        if (n_sub_probe < rcap)
                        {
                            sub_before[n_sub_probe] = ftz_probe_footprint_power(&mon.wf, mon.min_bin, mon.symbol_period, (float)sr->freq_hz, sr->dt);
                            sub_rows[n_sub_probe++] = ftz_probe_add(pb, &row);
                        }
                    }
                }
                rs->sum_cpu_us += ftz_thread_cpu_us() - sc0;
                if (inject_round == round && j0 == 0) { rc = FTZ_ERR_NOMEM; goto done; }    /* TEST HOOK (step 2e, D5): a non-fault error after the first chunk */
            }
            rs->sub_wall_us = ftz_wall_us() - w0;
            if (cancelled) { resid_valid = 0; st->abandoned = 1; break; }      /* all or nothing: this round publishes nothing, earlier rounds stand; the half-subtracted buffer is not a residual */
            if (n_sub_round == 0) break;                                       /* every fit said "no valid fit": the residual is unchanged */
            resid_valid = 1;
            if (deadline_us != 0 && deadline_us - ftz_wall_us() < (int64_t)FTZ_RESIDUAL_RESERVE_MS * 1000) { st->abandoned = 1; break; }   /* the decode keeps its reserve */

            /* ── S3 (2): the residual's spectrogram, in full ── */
            w0 = ftz_wall_us(); c0 = ftz_thread_cpu_us();
            monitor_reset(&mon);
            memset(mon.last_frame, 0, (size_t)mon.nfft * sizeof(mon.last_frame[0]));
            for (int pos = 0; pos + mon.block_size <= n; pos += mon.block_size)
                monitor_process(&mon, resid + pos);
            compute_noise_floor(&mon, &noise_floor_db, &noise_raw);
            tls_last_noise_floor_db = noise_floor_db;
            rs->spec_wall_us = ftz_wall_us() - w0;
            rs->spec_cpu_us  = ftz_thread_cpu_us() - c0;
            st->spectrogram_wall_us += rs->spec_wall_us;
            st->spectrogram_cpu_us  += rs->spec_cpu_us;
            if (pb != NULL)                                                    /* SUB-PROBE: suppression = footprint power before / after, on the round's input waterfall and the residual's */
            {
                for (int q = 0; q < n_sub_probe; ++q)
                {
                    ftz_probe_row_t* sr = ftz_probe_at(pb, sub_rows[q]);
                    if (sr == NULL || !(sub_before[q] > 0.0)) continue;
                    const double after = ftz_probe_footprint_power(&mon.wf, mon.min_bin, mon.symbol_period, sr->freq_hz, sr->time_s);
                    if (after > 0.0) sr->supp_db = (float)(10.0 * log10(sub_before[q] / after));
                }
            }

            /* ── S3 (3): candidates on the residual (floor 10, cap 200), then only those near a signal subtracted in THIS round ── */
            w0 = ftz_wall_us(); c0 = ftz_thread_cpu_us();
            ncands = ftx_find_candidates(&mon.wf, res_cap, cands, res_min_sc);
            if (ncands < 0) ncands = 0;
            if (ncands > res_cap) ncands = res_cap;
            rs->n_found = ncands;
            if (pb != NULL)                                                    /* SUB-PROBE: the LOW search, one extra call on the same waterfall; its result is only recorded */
            {
                const int nlow = ftx_find_candidates(&mon.wf, FTZ_PROBE_LOW_CAP, low_buf, 0);
                for (int q = 0; q < nlow && q < FTZ_PROBE_LOW_CAP; ++q)
                {
                    const ftx_candidate_t* lc = &low_buf[q];
                    int in_normal = 0;
                    for (int i = 0; i < ncands; ++i)
                        if (cands[i].freq_offset == lc->freq_offset && cands[i].time_offset == lc->time_offset && cands[i].freq_sub == lc->freq_sub && cands[i].time_sub == lc->time_sub) { in_normal = 1; break; }
                    ftz_probe_row_t row;
                    memset(&row, 0, sizeof(row));
                    row.kind = FTZ_PROBE_LOW; row.round = round;
                    row.freq_hz = (mon.min_bin + lc->freq_offset + (float)lc->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
                    row.time_s  = (lc->time_offset + (float)lc->time_sub / mon.wf.time_osr) * mon.symbol_period;
                    row.score   = lc->score;
                    row.kept    = in_normal ? 0 : (lc->score < res_min_sc ? 1 : 2);
                    (void)ftz_probe_add(pb, &row);
                }
            }
            int kept = 0;
            for (int i = 0; i < ncands; ++i)
            {
                const ftx_candidate_t* cd = &cands[i];
                const float f = (mon.min_bin + cd->freq_offset + (float)cd->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
                const int keep_it = ftz_patch_keep(f, sub_hz, n_sub_round);
                if (pb != NULL)                                                /* SUB-PROBE: a CAND row for EVERY candidate returned, before any filter */
                {
                    ftz_probe_row_t row;
                    memset(&row, 0, sizeof(row));
                    row.kind = FTZ_PROBE_CAND; row.round = round; row.freq_hz = f;
                    row.time_s = (cd->time_offset + (float)cd->time_sub / mon.wf.time_osr) * mon.symbol_period;
                    row.score = cd->score; row.kept = keep_it ? 1 : 0;
                    row.outcome = keep_it ? FTZ_PO_UNSET : FTZ_PO_NOT_KEPT_PATCH;
                    row.a_unsat = row.b_unsat = row.cq_unsat = -1;
                    const int rix = ftz_probe_add(pb, &row);
                    if (keep_it) pr_row[kept] = rix;                           /* kept <= i: the entry is not read again */
                }
                if (!keep_it) continue;
                if (kept != i) cands[kept] = cands[i];
                kept++;
            }
            ncands = kept;
            rs->n_kept = kept;
            rs->search_wall_us = ftz_wall_us() - w0;
            rs->search_cpu_us  = ftz_thread_cpu_us() - c0;
            st->candidates_wall_us += rs->search_wall_us;
            st->candidates_cpu_us  += rs->search_cpu_us;

            if (params->expire_round == round) { st->abandoned = 1; break; }   /* TEST HOOK: the budget is gone at this round's decode stage */
            if (ncands == 0) break;                                            /* nothing near the subtraction: the round adds nothing */

            /* per-candidate state of the round starts clean */
            memset(ok_a, 0, (size_t)alloc_c); memset(b_el, 0, (size_t)alloc_c); memset(b_st, 0, (size_t)alloc_c); memset(b_ed, 0, (size_t)alloc_c);
            memset(c_el, 0, (size_t)alloc_c); memset(c_at, 0, (size_t)alloc_c); memset(c_ok, 0, (size_t)alloc_c);
            memset(drop, 0, (size_t)alloc_c * 2);
            if (pb != NULL) { memset(pr_out, 0, (size_t)alloc_c * sizeof(int32_t)); memset(pr_gate, 0, (size_t)alloc_c * sizeof(int32_t)); memset(pstat, 0, (size_t)alloc_c * sizeof(ftz_pstat_t)); }
        }
        st->n_candidates += ncands;
        for (int i = 0; i < ncands; ++i)
        {
            const ftx_candidate_t* cand = &cands[i];
            pos_f[i] = (mon.min_bin + cand->freq_offset + (float)cand->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
            pos_t[i] = (cand->time_offset + (float)cand->time_sub / mon.wf.time_osr) * mon.symbol_period;
            if (pb != NULL && round == 0)                                      /* SUB-PROBE: round 0's CAND rows (every candidate is kept) */
            {
                ftz_probe_row_t row;
                memset(&row, 0, sizeof(row));
                row.kind = FTZ_PROBE_CAND; row.round = 0; row.freq_hz = pos_f[i]; row.time_s = pos_t[i];
                row.score = cand->score; row.kept = 1; row.outcome = FTZ_PO_UNSET;
                row.a_unsat = row.b_unsat = row.cq_unsat = -1;
                pr_row[i] = ftz_probe_add(pb, &row);
            }
        }

        const int64_t dec_w0 = ftz_wall_us();
        int64_t dec_cpu = 0;
        ftz_cycle_t cyc;
        memset(&cyc, 0, sizeof(cyc));
        cyc.wf = &mon.wf; cyc.cands = cands; cyc.n_cands = ncands; cyc.ldpc_iterations = round == 0 ? ldpc_it : K_LDPC_ITERATIONS_PASS2;
        cyc.deadline_us = deadline_us; cyc.cq_force = cq_on ? cq_force : NULL;
        cyc.pos_freq = pos_f; cyc.pos_dt = pos_t; cyc.msgs = msgs; cyc.ok_a = ok_a;
        cyc.b_eligible = b_el; cyc.b_state = b_st; cyc.b_edge = b_ed; cyc.b_payload = b_pl; cyc.b_freq = b_fr; cyc.b_dt = b_dt; cyc.b_snr = b_snr;
        cyc.known = known;
        cyc.c_attempted = c_at; cyc.c_ok = c_ok; cyc.c_msgs = cmsgs; cyc.c_eligible = c_el;
        cyc.pstat = pstat;                                                     /* NULL unless FTZ_FLAG_PROBE */
        if (round > 0)
        {
            for (int s = 0; s < nseen; ++s) memcpy(known[cyc.n_known++], seen_payloads[s], FTZ_PAYLOAD_BYTES);   /* everything already found is "known" to tier B */
            cyc.pcm_full = resid;
        }

        /* The pool for round 0: as before (not for a single candidate). Later rounds decide again for their own candidate count. */
        use_pool = ftz_prepare_pool(threads, ncands);
        if (round == 0 && !use_pool) st->threads = 1;
        else if (use_pool && g_ftz_pool != NULL) st->threads = g_ftz_pool->n_threads;
        const int nworkers = use_pool && g_ftz_pool != NULL ? g_ftz_pool->n_threads : 1;
        int round_incomplete = 0;   /* the budget kept tier B or CQ-AP from a candidate in this round */

        /* ── S2 step 2: tier A on every candidate, in parallel ── */
        w0 = ftz_wall_us();
        {
            int64_t cpu_us = 0;
            if (ftz_run_job(ftz_tier_a_item, &cyc, ncands, use_pool, &cpu_us)) { rc = FTZ_ERR_FAULT; goto done; }
            st->tier_a_cpu_us += cpu_us; dec_cpu += cpu_us;
        }
        st->tier_a_wall_us += ftz_wall_us() - w0;
        for (int i = 0; i < ncands; ++i)
            if (ok_a[i])
            {
                if (cyc.n_known >= kcap) continue;                                  /* bounds: cannot happen (kcap leaves room for every round's tier A) */
                memcpy(known[cyc.n_known], msgs[i].payload, FTZ_PAYLOAD_BYTES); cyc.n_known++; st->n_tier_a++; rs->n_tier_a++;
            }

        /* ── S2 step 3: tier B on every candidate that failed tier A and is not a duplicate position ── */
        w0 = ftz_wall_us();
        {
            int n_eligible = 0;
            for (int i = 0; i < ncands && !no_tier_b; ++i)    /* decoder.effort = fast: no tier B, so nothing is eligible */
            {
                if (ok_a[i]) continue;
                int dup = 0;
                for (int j = 0; j < i; ++j)
                    if (!ok_a[j] && pos_f[j] == pos_f[i] && pos_t[j] == pos_t[i]) { dup = 1; break; }   /* an earlier undecoded candidate at the same position */
                if (dup) continue;
                b_el[i] = 1;
                n_eligible++;
            }
            st->n_b_eligible += n_eligible;

            int have_ctx = 1;
            if (n_eligible > 0)
            {
                /* The coherent contexts: one per worker, on the full-length buffer; created here, on this thread, so a failed allocation is a
                 * skipped tier B and not a failure inside a worker. A capture shorter than 15 s is read as if zero-padded to 15 s. */
                for (int w = 0; w < nworkers && have_ctx; ++w)
                {
                    if (g_ftz_cf[w] == NULL)
                    {
                        g_ftz_cf[w] = cf_ctx_new(FT8_EXPECTED_SAMPLES);
                        if (g_ftz_cf[w] != NULL) cf_ctx_set_multiset(g_ftz_cf[w], 1);   /* multi-set ON, as today's default */
                    }
                    if (g_ftz_cf[w] == NULL) have_ctx = 0;
                }
                if (round == 0)
                {
                    full0 = ftz_full_buffer(pcm, n, &pcm_pad);
                    if (full0 == NULL) have_ctx = 0;
                    cyc.pcm_full = full0;
                }
            }
            if (n_eligible > 0 && have_ctx)
            {
                int64_t cpu_us = 0;
                if (ftz_run_job(ftz_tier_b_item, &cyc, ncands, use_pool, &cpu_us)) { rc = FTZ_ERR_FAULT; goto done; }
                st->tier_b_cpu_us += cpu_us; dec_cpu += cpu_us;
            }
            else if (n_eligible > 0)
            {
                for (int i = 0; i < ncands; ++i) if (b_el[i]) b_st[i] = FTZ_B_SKIPPED;   /* no memory for tier B: counted as skipped, flagged */
            }
            for (int i = 0; i < ncands; ++i)
            {
                if (!b_el[i]) continue;
                if (b_st[i] == FTZ_B_SKIPPED || b_st[i] == FTZ_B_NONE) { st->n_b_skipped++; st->abandoned = 1; round_incomplete = 1; continue; }
                st->n_b_attempted++;
                if (b_ed[i]) st->n_b_edge++;
                if (b_st[i] != FTZ_B_NO_CRC) st->n_b_crc_valid++;
                if (b_st[i] == FTZ_B_GATED_OUT || b_st[i] == FTZ_B_NEW_GATED) st->n_b_f1b++;
                if (b_st[i] == FTZ_B_NEW_GATED) st->n_b_gated++;
            }
        }
        st->tier_b_wall_us += ftz_wall_us() - w0;

        /* ── S2 step 4: CQ-AP on every candidate that failed tier A and produced no CRC-valid tier-B output ── */
        w0 = ftz_wall_us();
        if (cq_on)
        {
            int n_cq = 0;
            for (int i = 0; i < ncands; ++i)
                if (!ok_a[i] && b_st[i] != FTZ_B_KNOWN && b_st[i] != FTZ_B_GATED_OUT && b_st[i] != FTZ_B_NEW_GATED) { c_el[i] = 1; n_cq++; }
            if (n_cq > 0)
            {
                int64_t cpu_us = 0;
                if (ftz_run_job(ftz_cq_item, &cyc, ncands, use_pool, &cpu_us)) { rc = FTZ_ERR_FAULT; goto done; }
                st->cq_ap_cpu_us += cpu_us; dec_cpu += cpu_us;
            }
            for (int i = 0; i < ncands; ++i)
            {
                if (c_el[i] && c_at[i]) st->n_cq_attempts++;
                else if (c_el[i]) { st->abandoned = 1; round_incomplete = 1; }   /* eligible, never attempted: the budget stopped it */
            }
        }
        st->cq_ap_wall_us += ftz_wall_us() - w0;

        /* All or nothing: a residual round the budget stopped publishes nothing, and no round follows. */
        if (round > 0 && round_incomplete)
        {
            rs->decode_wall_us = ftz_wall_us() - dec_w0; rs->decode_cpu_us = dec_cpu;
            break;
        }

        /* ── S2 steps 6 and 7: order the union of the three tiers, then unpack / de-duplicate / publish, on this thread ── */
        w0 = ftz_wall_us(); c0 = ftz_thread_cpu_us();
        int nhits = 0;
        for (int i = 0; i < ncands; ++i)
        {
            ftz_hit_t* h = NULL;
            int b_take = 0, b_ungated_row = 0;
            if (b_st[i] == FTZ_B_NEW_GATED || b_st[i] == FTZ_B_GATED_OUT)
            {
                if (round == 0) b_take = (b_st[i] == FTZ_B_NEW_GATED);
                else b_take = ftz_residual_b_accept(b_st[i] == FTZ_B_NEW_GATED, (int)nearbyintf(b_fr[i]), ungated_on, rescand_on, &b_ungated_row);
            }
            if (ok_a[i])                     { h = &hits[nhits++]; h->tier = FTZ_TIER_A;  h->freq_hz = pos_f[i]; h->dt = pos_t[i]; memcpy(h->payload, msgs[i].payload,  FTZ_PAYLOAD_BYTES); }
            else if (b_take)                 { h = &hits[nhits++]; h->tier = FTZ_TIER_B;  h->freq_hz = b_fr[i];  h->dt = b_dt[i];  memcpy(h->payload, b_pl[i],           FTZ_PAYLOAD_BYTES); h->ungated = b_ungated_row; }
            else if (c_ok[i])                { h = &hits[nhits++]; h->tier = FTZ_TIER_CQ; h->freq_hz = pos_f[i]; h->dt = pos_t[i]; memcpy(h->payload, cmsgs[i].payload, FTZ_PAYLOAD_BYTES); }
            if (h != NULL) { h->index = i; if (h->tier != FTZ_TIER_B) h->ungated = 0; }
        }
        qsort(hits, (size_t)nhits, sizeof(ftz_hit_t), ftz_hit_cmp);

        /* Step 2e (D3): the candidates of this round that did not decode (no tier A / tier B / CQ-AP payload, and not a known payload tier B re-found): the evidence
         * that something may be hiding near them, read by the next round's fit-skip rule. */
        n_fail = 0;
        for (int i = 0; i < ncands; ++i)
        {
            const int decoded = ok_a[i] || c_ok[i] || b_st[i] == FTZ_B_KNOWN || b_st[i] == FTZ_B_NEW_GATED
                             || (b_st[i] == FTZ_B_GATED_OUT && round > 0 && ungated_on);
            if (!decoded && n_fail < alloc_c) fail_hz[n_fail++] = pos_f[i];
        }

        /* One tier-B row per payload: the first, in the sorted order, whose estimate is not on a window edge; failing that the first
         * (CoherentFallbackSelector.Select's rule). */
        for (int k = 0; k < nhits; ++k)
        {
            if (hits[k].tier != FTZ_TIER_B) continue;
            for (int j = 0; j < k; ++j)
            {
                if (hits[j].tier != FTZ_TIER_B || drop[j] || memcmp(hits[j].payload, hits[k].payload, FTZ_PAYLOAD_BYTES) != 0) continue;
                if (b_ed[hits[j].index] && !b_ed[hits[k].index]) drop[j] = 1;   /* a non-edge member replaces an edge one */
                else drop[k] = 1;                                              /* later members never replace a non-edge one */
                break;
            }
        }

        /* DR-3 duplicate rule, part 1: of two or more hits of this round with the same payload (round 0) or the same transmission (a residual round), the one
         * with the HIGHEST candidate sync score survives, at its own frequency and time; equal scores keep the lowest-frequency (first) one, as before. */
        for (int k = 0; k < nhits; ++k)
        {
            memcpy(sel_pl + (size_t)k * FTZ_PAYLOAD_BYTES, hits[k].payload, FTZ_PAYLOAD_BYTES);
            sel_sc[k] = (hits[k].index >= 0 && hits[k].index < ncands) ? (int32_t)cands[hits[k].index].score : 0;
        }
        (void)ftz_dedup_select(round, nhits, sel_pl, sel_sc, drop);
        if (pb != NULL)                                                        /* SUB-PROBE: every hit is pending until the loop decides; a dropped hit is a duplicate */
            for (int k = 0; k < nhits; ++k)
                if (hits[k].index >= 0 && hits[k].index < ncands) pr_out[hits[k].index] = drop[k] ? FTZ_PO_DUP : FTZ_PO_PENDING;

        const int nres_before = nres;
        for (int k = 0; k < nhits; ++k)
        {
            if (drop[k]) continue;
            const int i = hits[k].index;
            if (i < 0 || i >= ncands) continue;
            const ftx_candidate_t* cand = &cands[i];

            /* Round 0: the same payload twice is one decode. A residual round: also the RR73-aware same transmission of anything already found. */
            bool dup = false;
            for (int s = 0; s < nseen; ++s)
            {
                if (round == 0 ? !memcmp(seen_payloads[s], hits[k].payload, FTZ_PAYLOAD_BYTES) : ftz_payload_same_qso(seen_payloads[s], hits[k].payload))
                { dup = true; break; }
            }
            if (dup) { if (pb != NULL) pr_out[i] = FTZ_PO_DUP; continue; }

            ftx_message_t msg;
            memset(&msg, 0, sizeof(msg));
            memcpy(msg.payload, hits[k].payload, FTZ_PAYLOAD_BYTES);
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            tls_h12_lookup_performed = false;
            tls_h12_suppressed       = false;
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
            {
                if (pb != NULL) { pr_out[i] = FTZ_PO_GATE; pr_gate[i] = FTZ_PG_UNPACK; }
                continue;                              /* e.g. a Type-4 hash not yet known: not a decode */
            }
            text[FTX_MAX_MESSAGE_LENGTH] = '\0';

            /* Past this point the payload unpacked: remember it, then de-duplicate by text (two payloads can render alike; a text published earlier in the cycle is not published again). */
            if (nseen >= scap) { st->abandoned = 1; break; }                      /* bounds: cannot happen (one payload per candidate per round) */
            memcpy(seen_payloads[nseen++], hits[k].payload, FTZ_PAYLOAD_BYTES);
            /* DR-3 duplicate rule, part 2: the same text from two payloads in ONE round: the higher candidate sync score is the one published (it replaces the result
             * already published this round, in its slot, un-counting that result); equal scores keep the earlier one. A text published in an EARLIER round stands. */
            const int new_score = (int)cands[i].score;
            int replace_slot = -1;
            bool text_dup = false;
            for (int s = 0; s < nres; ++s)
                if (!strcmp(texts[s], text))
                {
                    text_dup = true;
                    if (s >= nres_before && ftz_text_replace_wins(new_score, res_score[s])) replace_slot = s;
                    break;
                }
            if (text_dup && replace_slot < 0) { if (pb != NULL) pr_out[i] = FTZ_PO_DUP; continue; }

            if (replace_slot < 0 && nres >= rcap)
            {
                if (pb != NULL) { pr_out[i] = FTZ_PO_GATE; pr_gate[i] = FTZ_PG_CAPACITY; }
                st->abandoned = 1; break;              /* the caller's array is full: stop, flag it, keep what is there */
            }
            const int slot = replace_slot >= 0 ? replace_slot : nres;
            if (replace_slot >= 0)
            {
                if (pb != NULL) pr_out[res_cidx[slot]] = FTZ_PO_DUP;           /* SUB-PROBE: the replaced result's candidate is now the duplicate */
                ftz_h12_apply(&res_h12[slot], -1);
                if (res_tier[slot] == FTZ_TIER_B) { st->n_b_published--; if (res_ungated[slot]) { st->n_ungated--; rs->n_ungated--; } }
                else if (res_tier[slot] == FTZ_TIER_CQ) st->n_cq_decodes--;
            }

            /* The primary pass's 12-bit-hash accounting (SUP-B, f001): count a display exactly where a result is emitted. */
            res_h12[slot] = ftz_h12_capture();
            ftz_h12_apply(&res_h12[slot], 1);

            FT8Result* r = &results[slot];
            if (hits[k].tier == FTZ_TIER_B)
            {
                /* the fallback's row: the estimate's frequency rounded to the nearest even integer Hz (as the managed Math.Round), its dt, the coherent SNR */
                r->freq_hz = (int)nearbyintf(hits[k].freq_hz);
                r->dt      = hits[k].dt;
                r->snr     = (int)b_snr[i];
                st->n_b_published++;
                if (hits[k].ungated) { st->n_ungated++; rs->n_ungated++; }
            }
            else
            {
                uint8_t tones[FT8_NN];
                ft8_encode(msg.payload, tones);
                float snr = ftz_snr_db(&mon, cand, tones, noise_floor_db);
                r->freq_hz = (int)roundf(hits[k].freq_hz);
                r->dt      = hits[k].dt;
                r->snr     = (int)roundf(snr);
                if (hits[k].tier == FTZ_TIER_CQ) st->n_cq_decodes++;
            }
            strncpy(r->message, text, 35);
            r->message[35] = '\0';
            memcpy(texts[slot], text, sizeof(texts[slot]));
            memcpy(res_pl[slot], hits[k].payload, FTZ_PAYLOAD_BYTES);
            if (pb != NULL) { pr_out[i] = hits[k].tier == FTZ_TIER_B ? FTZ_PO_B_OK : (hits[k].tier == FTZ_TIER_CQ ? FTZ_PO_CQ_OK : FTZ_PO_A_OK); res_cidx[slot] = i; }
            res_score[slot]   = new_score;
            res_tier[slot]    = (uint8_t)hits[k].tier;
            res_ungated[slot] = (uint8_t)(hits[k].tier == FTZ_TIER_B && hits[k].ungated ? 1 : 0);
            if (out_tiers  != NULL) out_tiers[slot]  = (uint8_t)hits[k].tier;
            if (out_rounds != NULL) out_rounds[slot] = (uint8_t)round;
            if (replace_slot < 0)
            {
                nres++;
                st->n_results = nres;                          /* visible even if a later step faults */
            }
        }
        if (pb != NULL)                                                        /* SUB-PROBE: one exclusive outcome and the stage columns for every kept candidate of the round */
        {
            for (int i = 0; i < ncands; ++i)
            {
                ftz_probe_row_t* pr = ftz_probe_at(pb, pr_row[i]);
                if (pr == NULL) continue;
                int po = pr_out[i], pg = pr_gate[i];
                if (po == FTZ_PO_PENDING) { po = FTZ_PO_GATE; pg = FTZ_PG_CAPACITY; }   /* a hit the loop never reached: the results array filled first */
                ftz_probe_finish_cand(pr, round, &pstat[i], ok_a[i], b_el[i], b_st[i], c_at[i], c_ok[i], no_tier_b, po, pg);
            }
        }
        st->n_results         = nres;
        st->unpack_wall_us   += ftz_wall_us() - w0;
        st->unpack_cpu_us    += ftz_thread_cpu_us() - c0;
        dec_cpu              += ftz_thread_cpu_us() - c0;
        rs->n_results         = nres - nres_before;
        rs->decode_wall_us    = ftz_wall_us() - dec_w0;
        rs->decode_cpu_us     = dec_cpu;
        if (round == 0 && r0cb != NULL)
        {
            /* Step 2d: batch 1 leaves now, before round 1. The callee copies what it needs and returns; native then goes on. */
            if (ftz_call_round0(r0cb, r0ctx, nres, results, out_tiers)) { rc = FTZ_ERR_FAULT; goto done; }
        }
        if (round > 0 && rs->n_results == 0) break;            /* a round that adds nothing new ends the loop */
    }
    rc = nres;

done:
    /* Step 2d: the residual as of the last subtraction made (not after a fault: the heap may be damaged). */
    if (rc != FTZ_ERR_FAULT && resid_valid && resid != NULL && out_resid != NULL)
    {
        memcpy(out_resid, resid, (size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
        st->has_residual = 1;
    }
    free(cands); free(msgs); free(cmsgs); free(ok_a); free(b_el); free(b_st); free(b_ed); free(c_el); free(c_at); free(c_ok);
    free(pos_f); free(pos_t); free(b_fr); free(b_dt); free(b_snr); free(b_pl); free(known); free(hits); free(drop); free(texts); free(seen_payloads);
    free(res_pl); free(res_score); free(res_tier); free(res_ungated); free(res_h12); free(sel_pl); free(sel_sc); free(fit_ix); free(sub_hz); free(fail_hz);
    free(pr_row); free(pr_out); free(pr_gate); free(pstat); free(res_cidx); free(sub_rows); free(sub_before); free(low_buf);
    free(resid); free(xa_re); free(xa_im);
    if (fitjob != NULL) { free(fitjob->shat); free(fitjob); }
    free(pcm_pad);
    tls_hash_table = NULL;
    monitor_free(&mon);
    st->total_wall_us = ftz_wall_us() - t_start;
    st->total_cpu_us  = st->spectrogram_cpu_us + st->candidates_cpu_us + st->tier_a_cpu_us + st->tier_b_cpu_us + st->cq_ap_cpu_us + st->unpack_cpu_us;
    for (int r = 1; r <= FTZ_MAX_ROUNDS; ++r) st->total_cpu_us += st->rounds[r].fit_cpu_us + st->rounds[r].sum_cpu_us;
    return rc;
}

int ftz_decode_cycle(const float* pcm, int n, const ftz_params_t* params, void* out_results, int cap, uint8_t* out_tiers, uint8_t* out_rounds, ftz_stats_t* out_stats)
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
    __try { rc = ftz_decode_cycle_impl(pcm, n, &p, (FT8Result*)out_results, cap, out_tiers, out_rounds, st); }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        /* As ft8_decode_all does: clear the thread-local table pointer; the spectrogram heap is deliberately not freed
         * (it may be corrupt). Results already counted in st->n_results stand. */
        tls_hash_table = NULL;
        rc = FTZ_ERR_FAULT;
    }
#else
    rc = ftz_decode_cycle_impl(pcm, n, &p, (FT8Result*)out_results, cap, out_tiers, out_rounds, st);
#endif
    ftz_call_unlock();
    st->error = rc < 0 ? rc : FTZ_OK;   /* error is the error code, never the result count */
    return rc;
}
