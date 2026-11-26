/*
 * ftz_decoder.h -- the lean decoder engine's native ABI (DR-2 step 2a, shim 20260073).
 *
 * PROVENANCE: OpenWSFZ-original, written 2026-11-24 for the decoder rebuild (docs/decoder-rebuild/spec-dr2-lean-decoder.md
 * on arch/decoder-rebuild). It reuses, unchanged in meaning, the building blocks of ft8_lib (MIT, Karlis Goba): the
 * waterfall (monitor.c, KISS FFT), ftx_find_candidates, the magnitude likelihood extraction, ldpc.c, crc.c, message.c.
 * No line of WSJT-X is copied or ported. See native/ft8_lib_vendor/PROVENANCE.md for the vendored sources.
 *
 * One call per 15 s cycle: spectrogram, candidate search, tier A (magnitude LLRs, belief propagation, CRC), tier B, CQ-AP, unpack
 * (round 0, steps 2a and 2b); then, with FTZ_FLAG_ROUNDS, up to three subtract-and-retry rounds (step 2c, shim 20260075): subtract what
 * was found, re-compute the residual's spectrogram, search only where the subtraction happened, decode those candidates the same way.
 * No OSD.
 */
#ifndef FTZ_DECODER_H
#define FTZ_DECODER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Error codes: ftz_decode_cycle returns the number of results (>= 0) or one of these (< 0). On an error the call
 * has already published nothing it cannot stand behind: results[0 .. *n_valid) in the stats are valid. */
#define FTZ_OK            0
#define FTZ_ERR_ARG      (-1)   /* a NULL pointer, a negative length, an undersized struct, a zero capacity            */
#define FTZ_ERR_NOMEM    (-2)   /* an allocation (spectrogram, candidate list, worker pool) failed                      */
#define FTZ_ERR_FAULT    (-3)   /* an access violation was caught by the SEH wrapper (MSVC builds only)                 */
#define FTZ_ERR_BADAUDIO (-4)   /* a sample is NaN, infinite or beyond +-FTZ_MAX_ABS_SAMPLE: not decodable audio        */

#define FTZ_PARAMS_VERSION   6
#define FTZ_MIN_THREADS      1
#define FTZ_MAX_THREADS      16
#define FTZ_DEFAULT_THREADS  2
#define FTZ_MAX_ABS_SAMPLE   1.0e6f

/* ftz_params_t.flags */
#define FTZ_FLAG_CQ_AP   1   /* run the CQ a-priori attempt (FR-103) on candidates that failed tier A and tier B                   */
#define FTZ_FLAG_BUDGET  2   /* budget_ms is a real wall-clock budget (0 then means "none left"); without it there is no budget  */
#define FTZ_FLAG_ROUNDS  4   /* step 2c: run the subtract-and-retry rounds after round 0 (without it the call is the step-2b call)   */
#define FTZ_FLAG_RESIDUAL_UNGATED 8    /* a residual tier-B row whose F1b is above T1 is published (decoder.coherentFallbackResidualUngated)   */
#define FTZ_FLAG_RESIDUAL_CANDS   16   /* ACCEPTED AND IGNORED since step 2e: a residual tier-B row is published when F1b-passed, or when the ungating is on, at any frequency */
#define FTZ_FLAG_NO_TIER_B        32   /* step 2d, decoder.effort = fast: tier B is not run in any round (CQ-AP still is, if asked)                   */
#define FTZ_FLAG_SKIP_FITS        64   /* step 2e (D3): a round-r result is fitted only if a candidate of round r that did NOT decode lies in its patch window (ftz_fit_needed) */

#define FTZ_FLAG_PROBE            128  /* SUB-PROBE (params version 6): test-only diagnostic; fill the caller's ftz_probe_t. OFF: nothing is allocated or computed. ON: the published decodes are byte-identical */

#define FTZ_MAX_ROUNDS            3      /* rounds after round 0                                                                 */
#define FTZ_PATCH_BELOW_HZ        50.0f  /* a residual candidate is searched only within [f - 50, f + 100] Hz of a signal subtracted in the round */
#define FTZ_PATCH_ABOVE_HZ        100.0f
#define FTZ_RESIDUAL_RUN_MAX_HZ   1097   /* CohFallbackAudioSelector.ResidualRunMaxFreqHz                                         */
#define FTZ_RESIDUAL_RESERVE_MS   1500   /* SubtractionPass.SubtractionResidualDecodeReserve: a round is not started with less left */

/* Which tier produced a result (the optional out_tiers array of ftz_decode_cycle). */
#define FTZ_TIER_A   0
#define FTZ_TIER_B   1
#define FTZ_TIER_CQ  2

/* Step 2d: the round-0 hand-off. Called once, on the thread that runs ftz_decode_cycle, while the call still holds its lock, right after round 0's results are
 * unpacked and BEFORE round 1 starts (also with n = 0: an empty batch 1 is a real cycle). results points at n FT8Result (48 bytes each) and tiers at n bytes
 * (FTZ_TIER_*; NULL if the caller passed no out_tiers); both are valid only for the duration of the call, so the callee copies them. The callee MUST NOT call
 * any ftz_* function or any other function of this library, MUST NOT throw, and SHOULD return quickly (hand the copy to another thread and return): the cycle's
 * remaining rounds wait for it. It is not called when the cycle fails before round 0 is unpacked (the caller then has every result in the return value). */
typedef void (*ftz_round0_fn)(void* ctx, int n, const void* results, const uint8_t* tiers);

/* Input parameters. Zero in a field means "today's primary value" (min_score 10, max_candidates 140, ldpc_iterations 50,
 * threads 2, no CQ-AP, no budget). struct_size is sizeof(ftz_params_t) as the caller compiled it; a shorter struct reads zero for the rest. */
typedef struct
{
    int32_t struct_size;
    int32_t threads;          /* worker count, clamped to [1, 16]; 0 = 2                                                  */
    int32_t min_score;        /* ftx_find_candidates min score; 0 = 10 (the primary pass today)                           */
    int32_t max_candidates;   /* candidate cap, clamped to [1, FTZ_MAX_CANDIDATES]; 0 = 140 (the primary pass today)       */
    int32_t ldpc_iterations;  /* belief-propagation iterations; 0 = 50                                                    */
    int32_t flags;            /* FTZ_FLAG_*                                                                               */
    int32_t budget_ms;        /* with FTZ_FLAG_BUDGET: wall-clock ms the cycle may still spend; tier B and CQ-AP stop at it */
    int32_t reserved;
    int32_t max_rounds;       /* with FTZ_FLAG_ROUNDS: rounds after round 0, clamped to [1, 3]; 0 = 3                       */
    int32_t expire_round;     /* TEST HOOK: the round (1 to 3) at whose decode stage the budget is treated as gone; 0 = none */
    /* Step 2d (params version 4); a caller built against version 3 has struct_size 40 and reads NULL for all three. */
    ftz_round0_fn round0_cb;  /* NULL, or called ONCE on the calling thread right after round 0 is unpacked, BEFORE round 1 starts (see ftz_round0_fn) */
    void*   round0_ctx;       /* passed back to round0_cb                                                                    */
    float*  out_residual;     /* NULL, or FT8_EXPECTED_SAMPLES floats that receive the residual as of the last subtraction made (stats.has_residual) */
    /* Step 2e (params version 5). */
    int32_t inject_error_round;   /* TEST HOOK: the round (1 to 3) whose fits end, after the first chunk, in a simulated allocation failure (FTZ_ERR_NOMEM); 0 = none */
    int32_t reserved2;
    /* SUB-PROBE (params version 6); a caller built against version 5 has struct_size 72 and reads NULL. */
    struct ftz_probe* probe;      /* NULL, or (with FTZ_FLAG_PROBE) the caller's probe buffer; see ftz_probe_t */
} ftz_params_t;

/* ── SUB-PROBE: a test-only diagnostic, numbers only (no message text, no payload; HK-037). Read-only on decoder state. ──────────────────────────────────────
 * With FTZ_FLAG_PROBE and params.probe set, the call fills probe->rows[0 .. probe->n) with one 64-byte ftz_probe_row_t per record, in the order written (round by round:
 * round 0 CAND rows; then for each round 1 to 3: SUB rows, LOW rows, CAND rows). cap rows fit; a row that does not fit sets probe->overflow = 1 and is dropped (nothing is
 * ever written past rows[cap - 1]). Worst case without overflow: FTZ_PROBE_MAX_ROWS (4 x 256 CAND + 3 x 400 LOW + 1024 SUB = 3248, rounded up). */
#define FTZ_PROBE_MAX_ROWS 3300

#define FTZ_PROBE_SUB  1   /* a signal subtracted: round, freq_hz, time_s, amp (the fit's amplitude), supp_db                                                              */
#define FTZ_PROBE_CAND 2   /* a candidate ftx_find_candidates returned (before any filter): round, freq_hz, time_s, score, kept, outcome, and the stage columns            */
#define FTZ_PROBE_LOW  3   /* rounds 1 to 3: a candidate of the extra floor-0, cap-400 search on the round's residual (never decoded): freq_hz, time_s, score, kept = reason */

/* CAND outcome (one exclusive code per candidate; the last stage that ended its journey). 0 = UNSET (the round ended early: budget, error). */
#define FTZ_PO_UNSET          0
#define FTZ_PO_A_OK           1   /* tier A decoded and the result was published                                                                                */
#define FTZ_PO_A_BP           2   /* tier A failed in belief propagation (a_unsat = unsatisfied parity checks; -1 = degenerate LLRs); final only when tier B is off (effort fast) */
#define FTZ_PO_A_CRC          3   /* tier A: BP converged but the CRC failed; final only when tier B is off                                                      */
#define FTZ_PO_B_NE           4   /* failed tier A and was not eligible for tier B (a duplicate position)                                                         */
#define FTZ_PO_B_OK           5   /* tier B decoded and the result was published                                                                                */
#define FTZ_PO_B_BP           6   /* tier B ran and failed in belief propagation (b_unsat; -1 = degenerate LLRs)                                                  */
#define FTZ_PO_B_CRC          7   /* tier B: BP converged, CRC failed                                                                                             */
#define FTZ_PO_CQ_OK          8   /* CQ-AP decoded and the result was published                                                                                  */
#define FTZ_PO_CQ_FAIL        9   /* CQ-AP was attempted and failed                                                                                               */
#define FTZ_PO_DUP           10   /* decoded but not published: the same payload, transmission or text as another (the DR-3 rule), or a payload tier A already produced */
#define FTZ_PO_GATE          11   /* decoded but not published by an accept gate; the gate is in the gate column (FTZ_PG_*)                                         */
#define FTZ_PO_NOT_KEPT_PATCH 12  /* a residual candidate outside every [f - 50, f + 100] Hz patch of the round's subtractions                                      */
#define FTZ_PO_NOT_KEPT_CAP   13  /* RESERVED, never written on a CAND row: the cap cuts before ftx_find_candidates returns; see the LOW rows' reason 2              */
#define FTZ_PO_B_SKIP         14  /* eligible for tier B, the budget ran out before it was attempted                                                              */
#define FTZ_PO_B_NOC3         15  /* tier B ran its estimate only: the coherent LLR stage (C3) and BP did not run                                                  */

/* GATE codes (the gate column of a CAND row with outcome FTZ_PO_GATE). */
#define FTZ_PG_NONE            0
#define FTZ_PG_UNPACK          1  /* the payload does not unpack (for example a hash not yet known)                                                                */
#define FTZ_PG_F1B             2  /* round 0: a CRC-valid new tier-B payload whose F1b is above T1                                                                 */
#define FTZ_PG_F1B_RESIDUAL    3  /* a residual round: a CRC-valid new tier-B payload rejected by the residual accept rule (ftz_residual_b_accept)                  */
#define FTZ_PG_CAPACITY        4  /* the caller's results array was full                                                                                           */

/* Stage columns of a CAND row. a_code: 0 not run, 1 CRC-valid, 2 BP failed, 3 CRC failed, 4 degenerate LLRs. b_code: 0 not run (not eligible), 1 skipped by the budget,
 * 2 estimate only (no C3), 3 degenerate LLRs, 4 BP failed, 5 CRC failed, 6 CRC-valid. cq_code: 0 not attempted, 1 failed, 2 CRC-valid. *_unsat: unsatisfied parity checks, -1 n/a. */

/* One probe row, 64 bytes (16 x 32 bits). Fields a record does not use are 0 (supp_db of a SUB row whose footprint is outside the waterfall, or whose round ended
 * before the residual's spectrogram, is -999). For a LOW row, kept is the reason: 0 also in the round's CAND list, 1 below the floor (kMinScorePass2), 2 cut by the cap. */
typedef struct
{
    int32_t kind;        /* FTZ_PROBE_*                                                        */
    int32_t round;       /* 0 to 3                                                             */
    float   freq_hz;
    float   time_s;
    float   amp;         /* SUB: the fit's amplitude (sqrt(2 * mean square of the fitted signal over its 79 symbols)) */
    float   supp_db;     /* SUB: 10 log10(footprint power before / after the round's subtraction)  */
    int32_t score;       /* CAND, LOW: ftx_candidate_t.score                                   */
    int32_t kept;        /* CAND: 1 passed the round's patch filter (round 0: all); LOW: reason */
    int32_t outcome;     /* CAND: FTZ_PO_*                                                     */
    int32_t gate;        /* CAND: FTZ_PG_* when outcome is FTZ_PO_GATE                         */
    int32_t a_code;
    int32_t a_unsat;
    int32_t b_code;
    int32_t b_unsat;
    int32_t cq_code;
    int32_t cq_unsat;
} ftz_probe_row_t;

/* The caller's probe buffer. struct_size = sizeof(ftz_probe_t), cap = rows allocated; n and overflow are outputs. */
typedef struct ftz_probe
{
    int32_t struct_size;
    int32_t cap;
    int32_t n;
    int32_t overflow;
    ftz_probe_row_t* rows;
} ftz_probe_t;

/* Per-round aggregates (step 2c). Counts, then microseconds: wall, and CPU summed over the threads that worked on the stage.
 * Ten 32-bit fields and nine 64-bit times: 40 + 72 = 112 bytes. Round 0 fills only the counts that apply to it. */
typedef struct
{
    int32_t n_fits;             /* signals handed to the fit (the re-encodable results of the previous round)               */
    int32_t n_subtracted;       /* of those, fits that answered 0 and were subtracted                                       */
    int32_t n_fit_none;         /* fits that answered -3 ("no valid fit"): contribute zero                                  */
    int32_t n_found;            /* candidates ftx_find_candidates returned                                                  */
    int32_t n_kept;             /* of those, kept by the patch rule (round 0: all)                                          */
    int32_t n_tier_a;           /* kept candidates whose tier A attempt produced a CRC-valid payload                        */
    int32_t n_results;          /* results this round published                                                             */
    int32_t n_ungated;          /* tier-B rows this round published only because of the ungating                            */
    int32_t n_fit_skipped;      /* re-encodable results the fit-skip rule left unfitted (step 2e)                           */
    int32_t reserved;
    int64_t sub_wall_us;        /* the whole subtract step: the fits and the sum into the residual                          */
    int64_t fit_cpu_us;         /* CPU of the fits, summed over the workers                                                  */
    int64_t sum_cpu_us;         /* CPU of the sum into the residual (calling thread)                                         */
    int64_t spec_wall_us, spec_cpu_us;       /* the residual's spectrogram (round 0: the first spectrogram)                  */
    int64_t search_wall_us, search_cpu_us;   /* ftx_find_candidates and the patch rule                                       */
    int64_t decode_wall_us, decode_cpu_us;   /* tier A, tier B, CQ-AP and unpack                                              */
} ftz_round_stats_t;

/* Output statistics (aggregates only, never message text). Times are microseconds: wall per stage, and CPU summed over the
 * threads that worked on the stage. The counts and stage times of the first part are CUMULATIVE over all rounds (with the loop
 * off they are round 0's, as in step 2b). Twenty 32-bit fields and fourteen 64-bit times (80 + 112 = 192 bytes), then four
 * ftz_round_stats_t (448 bytes): 640 bytes. */
typedef struct
{
    int32_t struct_size;
    int32_t error;              /* the return code of the call (FTZ_OK or an FTZ_ERR_*)                                    */
    int32_t n_candidates;       /* candidates ftx_find_candidates returned                                                  */
    int32_t n_tier_a;           /* candidates whose tier A attempt produced a CRC-valid payload                             */
    int32_t n_results;          /* results written to the output array                                                      */
    int32_t threads;            /* the effective worker count used                                                          */
    int32_t abandoned;          /* 1 if the budget stopped tier B or CQ-AP, or the output array was too small; else 0       */
    int32_t n_rounds;           /* subtract-and-retry rounds run (0 to 3): 0 when the loop is off or round 0 left nothing to subtract */
    int32_t n_b_eligible;      /* candidates that failed tier A, not a duplicate position                                  */
    int32_t n_b_attempted;      /* of those, run through the coherent estimate + LLRs + BP (not skipped by the budget)      */
    int32_t n_b_crc_valid;      /* attempted with a CRC-valid output                                                        */
    int32_t n_b_f1b;            /* CRC-valid with a payload tier A did not produce: F1b computed                            */
    int32_t n_b_gated;          /* of those, F1b <= T1 (17.552446 dB)                                                       */
    int32_t n_b_published;      /* tier-B rows in the output                                                                */
    int32_t n_b_edge;           /* attempted rows whose estimate sits on a window edge                                      */
    int32_t n_b_skipped;        /* eligible candidates the budget kept tier B from attempting                               */
    int32_t n_cq_attempts;      /* CQ-AP attempts (candidates that failed tier A and tier B)                                */
    int32_t n_cq_decodes;       /* CQ-AP rows in the output                                                                 */
    int32_t n_ungated;          /* residual tier-B rows published only because the ungating is on (F1b above T1)           */
    int32_t has_residual;       /* 1 if params.out_residual was written: the buffer as of the last subtraction made (0: nothing was subtracted, a fit round was stopped, or no buffer given) */
    int64_t spectrogram_wall_us, spectrogram_cpu_us;
    int64_t candidates_wall_us, candidates_cpu_us;
    int64_t tier_a_wall_us,     tier_a_cpu_us;
    int64_t tier_b_wall_us,     tier_b_cpu_us;
    int64_t cq_ap_wall_us,      cq_ap_cpu_us;
    int64_t unpack_wall_us,     unpack_cpu_us;
    int64_t total_wall_us,      total_cpu_us;
    ftz_round_stats_t rounds[FTZ_MAX_ROUNDS + 1];   /* [0] = round 0 (the step-2b work), [1..3] = the subtract-and-retry rounds */
} ftz_stats_t;

#define FTZ_MAX_CANDIDATES 256

/*
 * ftz_decode_cycle -- decode one cycle.
 *   pcm          n float samples, 12 kHz mono; n may be anything from 0 up (a buffer longer than 180 000 samples is read
 *                to its first 180 000; a shorter or truncated one just has fewer symbols).
 *   params       see above; NULL is an error.
 *   out_results  caller-allocated array of FT8Result (ft8_shim.h, 48 bytes each), capacity cap.
 *   out_tiers    may be NULL; else cap bytes, the tier (FTZ_TIER_*) of each result.
 *   out_stats    may be NULL.
 *   out_rounds   may be NULL; else cap bytes, the round (0 to 3) in which each result was found.
 * Returns the number of results, round by round, each round sorted by frequency, then time, then payload (a hash-free stand-in for the
 * text, so that nothing touches the callsign table before the order is fixed). The same audio and the same starting callsign-table
 * state give the same bytes for every thread count. Returns FTZ_ERR_* (< 0) on an error; never raises.
 */
int ftz_decode_cycle(const float* pcm, int n, const ftz_params_t* params, void* out_results, int cap, uint8_t* out_tiers, uint8_t* out_rounds, ftz_stats_t* out_stats);

/* Test exports: the accept rules of step 2c as pure functions, which the cycle itself calls. */

/* 1 if a residual candidate with this base frequency lies in [f - 50, f + 100] Hz of any of the n_sub signals subtracted in the round. */
int ftz_patch_keep(float base_hz, const float* sub_hz, int n_sub);

/* 1 if candidate (a 10-byte, 77-bit payload) is the SAME transmission as known: bit-identical, or known carries the standard RR73 sentinel
 * and candidate the on-air one with the same two calls (SubfeasPayload.SameQso). */
int ftz_payload_same_qso(const uint8_t* known, const uint8_t* candidate);

/* DR-3 duplicate rule (the lean engine's selection among duplicates of ONE round, pure, called by the cycle itself). ftz_dedup_select: payloads is n * 10 bytes
 * in published order (ascending frequency), scores the candidates' sync scores (ftx_candidate_t.score, higher = more likely); of hits with the same payload
 * (round 0) or the same transmission (a residual round) the HIGHEST score survives, equal scores keep the earlier hit; losers are marked in drop[]; returns
 * the number newly dropped. ftz_text_replace_wins: 1 when a same-text result of the same round with score new_score replaces one with old_score (strictly higher). */
int ftz_dedup_select(int round, int n, const uint8_t* payloads, const int32_t* scores, uint8_t* drop);
int ftz_text_replace_wins(int new_score, int old_score);

/* 1 if a CRC-valid, new tier-B row of a residual round is published. f1b_passed: F1b <= T1. Since step 2e: an F1b-passed row, or (ungated on) any row, at any
 * frequency; rescand_on (decoder.coherentFallbackResidualCandidates) is accepted and has NO effect in the lean engine (the faithful union of classic's residual run
 * and its residual-candidates run). *ungated_out (may be NULL) is set to 1 when the row is published ONLY because of the ungating. */
int ftz_residual_b_accept(int f1b_passed, int published_freq_hz, int ungated_on, int rescand_on, int* ungated_out);

/* Step 2e (D3): 1 if a result published at result_hz is worth fitting and subtracting: some candidate of the same round that did NOT decode (failed_hz, base
 * frequencies, n_failed of them) lies in the result's patch window [f - 50, f + 100] Hz, i.e. something may be hiding there. A signal with no failed candidate near it
 * cannot unmask anything that round's search would find. */
int ftz_fit_needed(float result_hz, const float* failed_hz, int n_failed);

/* Stops and frees the worker pool. Safe to call at any time (also when there is none) and to call twice; the pool is
 * re-created by the next ftz_decode_cycle. The daemon calls it on shutdown. */
void ftz_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif /* FTZ_DECODER_H */
