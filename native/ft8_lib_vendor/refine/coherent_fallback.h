/*
 * coherent_fallback.h -- COH-FALLBACK (A' step 3) Stage 1: the native core of the coherent-extraction fallback.
 *
 * OpenWSFZ-original, no WSJT-X source. This is a C port of three of OUR OWN clean-room Python reference files at QA commit
 * 44c70ea2: qa/rr-study/coh-gain/fine_sync.py (the data-free Costas fine-sync estimator), qa/rr-study/n2-coherent-llr-extractor/
 * coherent_extract.py (the 2 kHz downconversion, the per-symbol correlation and the V3 coherent LLRs) and the F1b feature of
 * qa/rr-study/coh-gain/cg_gate_features.py (costas_snr_noise_ref_db). The BP decode and the CRC are NOT here: the shim calls
 * decode.c's ftx_ldpc_decode_llrs with osd_depth -1 (BP only).
 *
 * The functions here allocate (one context per call chain), hold NO mutable global state, and are safe to call from any thread
 * with their own context.
 */

#ifndef COHERENT_FALLBACK_H
#define COHERENT_FALLBACK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CF_SAMPLE_RATE_HZ   12000   /* the PCM rate */
#define CF_DECIM            6       /* 12 kHz -> 2 kHz */
#define CF_RATE_HZ          2000    /* the decimated rate */
#define CF_SPS              320     /* samples per symbol at 2 kHz */
#define CF_NSYM             79      /* FT8_NN */
#define CF_NDATA            58      /* data symbols */
#define CF_NDF              41      /* df grid: -2.0 .. +2.0 Hz step 0.1 */
#define CF_NDT              49      /* dt grid: -0.12 .. +0.12 s step 5 ms */
#define CF_DT_STEP_SAMPLES  10      /* 5 ms at 2 kHz */
#define CF_N_LLR            174

/*
 * T1: the F1b strength-gate threshold in dB. Chosen on TRAIN and fixed by the Architect's Q-GATE ruling 7313db6f; the value is
 * the constant `T1` of qa/rr-study/results/2026-10-06-coh-gain/gate_thresholds.json @ 1e8a5270. Not user-configurable.
 */
#define CF_T1_DB            17.552446

#define CF_SNR_BIN_TO_2500_DB (-26.0206)   /* 10 log10(6.25 Hz tone bin / 2500 Hz) */
#define CF_SNR_FLOOR_DB       (-30.0)      /* the lowest SNR the coherent estimate reports */

typedef struct cf_ctx cf_ctx_t;

/* The fine-sync estimate: offsets from the anchor, the argmax's dt step index, whether it sits on a grid edge, the peak. */
typedef struct {
    double est_df_hz;   /* offset from the anchor frequency, on the 0.1 Hz grid */
    double est_dt_s;    /* offset from the anchor time, dt_step * 5 ms */
    double peak;        /* the surface maximum */
    int    dt_step;     /* -24 .. +24 */
    int    edge;        /* 1 iff the argmax is on a window edge (df index 0/40 or dt index 0/48) */
} cf_estimate_t;

/* A context for a PCM buffer of pcm_len samples (180 000 in production). NULL on allocation failure or pcm_len <= 0. */
cf_ctx_t* cf_ctx_new(int pcm_len);
void      cf_ctx_free(cf_ctx_t* ctx);

/* The data-free fine-sync estimate at the anchor (f0 Hz, t0 s). The anchor convention is the CANDIDATE convention of
 * ft8_extract_llrs_at / ft8_decode_all (symbol 0 starts at t0 - one symbol period): see coherent_fallback.c. */
void cf_estimate(cf_ctx_t* ctx, const float* pcm, double f0, double t0, cf_estimate_t* est);

/* F1b in dB: the anchor's Costas peak over the median of the same peak at the 24 reference frequencies f0 +- (40..150) Hz that
 * fall within 200..3000 Hz. anchor_peak is est->peak from cf_estimate at the same anchor. *n_refs receives how many references
 * were usable. +infinity when there are none or the median is not positive (as the reference does). */
double cf_f1b_db(cf_ctx_t* ctx, const float* pcm, double f0, double t0, double anchor_peak, int* n_refs);

/* The 174 V3 coherent max-log LLRs at the estimate (carrier f0 + est_df, symbol start moved by est->dt_step). Raw, as the
 * reference's extract_variants()["V3"]: no normalisation. */
void cf_v3_llrs(cf_ctx_t* ctx, const float* pcm, double f0, double t0, const cf_estimate_t* est, double out174[CF_N_LLR]);

/* Stage 2 (shim 20260068): the SNR in dB relative to a 2500 Hz noise bandwidth, from the 79 x 8 tone powers cf_v3_llrs left in the
 * context (call it right after cf_v3_llrs on the same context). tones[] is the decoded message's 79 FT8 tones. Floored at
 * CF_SNR_FLOOR_DB. NaN when the context holds no noise power. */
double cf_snr_db(const cf_ctx_t* ctx, const uint8_t tones[CF_NSYM]);

/* Monotonic wall-clock milliseconds (QueryPerformanceCounter / CLOCK_MONOTONIC). */
double cf_monotonic_ms(void);

#ifdef __cplusplus
}
#endif

#endif /* COHERENT_FALLBACK_H */
