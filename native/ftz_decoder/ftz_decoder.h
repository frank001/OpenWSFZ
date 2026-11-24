/*
 * ftz_decoder.h -- the lean decoder engine's native ABI (DR-2 step 2a, shim 20260073).
 *
 * PROVENANCE: OpenWSFZ-original, written 2026-11-24 for the decoder rebuild (docs/decoder-rebuild/spec-dr2-lean-decoder.md
 * on arch/decoder-rebuild). It reuses, unchanged in meaning, the building blocks of ft8_lib (MIT, Karlis Goba): the
 * waterfall (monitor.c, KISS FFT), ftx_find_candidates, the magnitude likelihood extraction, ldpc.c, crc.c, message.c.
 * No line of WSJT-X is copied or ported. See native/ft8_lib_vendor/PROVENANCE.md for the vendored sources.
 *
 * One call per 15 s cycle: spectrogram, candidate search, tier A (magnitude LLRs, belief propagation, CRC), unpack.
 * No tier B, no CQ-AP, no OSD, no subtraction loop in step 2a.
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

#define FTZ_PARAMS_VERSION   1
#define FTZ_MIN_THREADS      1
#define FTZ_MAX_THREADS      8
#define FTZ_DEFAULT_THREADS  2
#define FTZ_MAX_ABS_SAMPLE   1.0e6f

/* Input parameters. Zero in a field means "today's primary value" (min_score 10, max_candidates 140, ldpc_iterations 50,
 * threads 2). struct_size is sizeof(ftz_params_t) as the caller compiled it; a larger native struct reads only that many bytes. */
typedef struct
{
    int32_t struct_size;
    int32_t threads;          /* worker count, clamped to [1, 8]; 0 = 2                                                    */
    int32_t min_score;        /* ftx_find_candidates min score; 0 = 10 (the primary pass today)                           */
    int32_t max_candidates;   /* candidate cap, clamped to [1, FTZ_MAX_CANDIDATES]; 0 = 140 (the primary pass today)       */
    int32_t ldpc_iterations;  /* belief-propagation iterations; 0 = 50                                                    */
    int32_t reserved[3];
} ftz_params_t;

/* Output statistics (aggregates only, never message text). Times are microseconds: wall per stage, and CPU summed over the
 * threads that worked on the stage. */
typedef struct
{
    int32_t struct_size;
    int32_t error;              /* the return code of the call (FTZ_OK or an FTZ_ERR_*)                                    */
    int32_t n_candidates;       /* candidates ftx_find_candidates returned                                                  */
    int32_t n_tier_a;           /* candidates whose tier A attempt produced a CRC-valid payload                             */
    int32_t n_results;          /* results written to the output array                                                      */
    int32_t threads;            /* the effective worker count used                                                          */
    int32_t abandoned;          /* 1 if the output array was too small and results were dropped; 0 otherwise                 */
    int32_t reserved0;
    int64_t spectrogram_wall_us, spectrogram_cpu_us;
    int64_t candidates_wall_us, candidates_cpu_us;
    int64_t tier_a_wall_us,     tier_a_cpu_us;
    int64_t unpack_wall_us,     unpack_cpu_us;
    int64_t total_wall_us,      total_cpu_us;
} ftz_stats_t;

#define FTZ_MAX_CANDIDATES 256

/*
 * ftz_decode_cycle -- decode one cycle.
 *   pcm          n float samples, 12 kHz mono; n may be anything from 0 up (a buffer longer than 180 000 samples is read
 *                to its first 180 000; a shorter or truncated one just has fewer symbols).
 *   params       see above; NULL is an error.
 *   out_results  caller-allocated array of FT8Result (ft8_shim.h, 48 bytes each), capacity cap.
 *   out_stats    may be NULL.
 * Returns the number of results, sorted by frequency, then time, then payload (a hash-free stand-in for the text, so that
 * nothing touches the callsign table before the order is fixed). The same audio and the same starting callsign-table
 * state give the same bytes for every thread count. Returns FTZ_ERR_* (< 0) on an error; never raises.
 */
int ftz_decode_cycle(const float* pcm, int n, const ftz_params_t* params, void* out_results, int cap, ftz_stats_t* out_stats);

/* Stops and frees the worker pool. Safe to call at any time (also when there is none) and to call twice; the pool is
 * re-created by the next ftz_decode_cycle. The daemon calls it on shutdown. */
void ftz_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif /* FTZ_DECODER_H */
