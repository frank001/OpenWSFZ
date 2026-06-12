/*
 * ft8_shim.c — OpenWSFZ libft8.dll shim
 *
 * Wraps the kgoba/ft8_lib v2.0 decode pipeline (monitor → find candidates →
 * decode each → unpack text) behind the simple ft8_decode_all() entry point
 * declared in ft8_shim.h.
 *
 * p15 — Iterative signal subtraction (spectrogram-domain approach):
 *
 *   After the first decode pass, each decoded signal's waterfall tiles are
 *   suppressed using the EXACT decoded tone sequence (from ft8_encode).  For
 *   each of the 79 decoded symbols, the active tone bin and its ±1 nearest
 *   neighbours (to cancel Hann-window first sidelobes) are set to the
 *   noise-floor median value across all time/frequency over-sampling sub-bins.
 *   A second pass then runs on the modified waterfall using a wider candidate
 *   net (lower min_score, more candidates, more LDPC iterations).
 *
 * revert-pcm-sic — PCM-domain SIC reverted:
 *
 *   The fix-D001 PCM-domain SIC (three-pass: carrier estimation, CP-FSK
 *   waveform synthesis, PCM subtraction, waterfall rebuild) was reverted after
 *   the R&R study showed no measurable improvement (-0.1 pp) and two fatal
 *   0xC0000005 crashes occurred in production.  The two-pass spectrogram-
 *   suppression structure from p15 is restored.  FT8_SHIM_VERSION returns to
 *   20260002.  See DEFECT-native-stack-overflow-pcm-residual.md.
 *
 * fix-d001-revised — Option B: soft SNR-scaled tile attenuation:
 *
 *   The hard-zero tile suppression (noise_raw assignment) is replaced by a
 *   linear SNR-scaled attenuation factor.  At SNR ≤ K_SOFT_SUPP_SNR_MIN_DB
 *   the tile is left unchanged (factor = 1.0); at SNR ≥ K_SOFT_SUPP_SNR_MAX_DB
 *   the tile is fully suppressed (factor = 0.0).  Between those bounds the
 *   factor varies linearly.  This reduces collateral damage on adjacent
 *   weaker signals when the decoded signal is borderline (low SNR).
 *   FT8_SHIM_VERSION incremented to 20260004 (skipping 20260003, which
 *   was the reverted PCM-SIC version, to avoid any confusion).
 *
 * fix-D002 — SNR bandwidth constant calibration (FT8_SHIM_VERSION 20260006):
 *
 *   The bandwidth correction constant in the SNR formula is adjusted from
 *   -26.0 dB to -26.5 dB.  R&R study S1 runs confirmed a systematic +2.42 dB
 *   over-report in OpenWSFZ across three independent runs.  PCM RMS normalisation
 *   (managed layer) was unable to close the residual gap because both signal_db
 *   and noise_floor_db are waterfall-derived, making the formula invariant to
 *   amplitude scaling.  The -0.5 dB adjustment brings the reported bias within
 *   the ±2.0 dB R&R S1 acceptance threshold.
 *
 * diag-D001-three-pass-sic (FT8_SHIM_VERSION 20260007) — TRIED AND REVERTED:
 *
 *   K_MAX_PASSES was increased from 2 to 3 as a controlled diagnostic experiment.
 *   S7 R&R result: 50.54% overall vs 54.84% 2-pass baseline (−4.30 pp).
 *   H2 rejected: no improvement on any co-channel part (P0/P1/P2/P8 still 0/6);
 *   marginal capture regression (P11: 5→3/6, P12: 5→4/6).  The third pass
 *   provides no benefit over spectrogram-domain SIC for exact co-channel
 *   separation.  FT8_SHIM_VERSION returned to 20260006.
 *   Full findings: qa/rr-study/results/2026-06-12-3ecf8ae/report-v2.md.
 *
 * Build: see BUILD.md.  encode.c must be compiled and linked.
 */

#include "ft8_shim.h"

/* M_PI is not defined by MSVC's <math.h> under strict C11; enable it explicitly.
 * Must be defined before any header that transitively includes <math.h>.        */
#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif

#include <ft8/decode.h>
#include <ft8/encode.h>
#include <ft8/message.h>
#include <common/monitor.h>

#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

/* Fallback definition of M_PI in case the platform still does not provide it */
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#ifdef _MSC_VER
char* stpcpy(char* dest, const char* src)
{
    while ((*dest = *src) != '\0') { dest++; src++; }
    return dest;
}
#endif

/* ── Decode configuration ────────────────────────────────────────────────── */

#define FT8_SAMPLE_RATE      12000
#define FT8_EXPECTED_SAMPLES 180000

/* Samples per FT8 symbol: 12000 Hz / 6.25 symbols-per-second = 1920 */
#define FT8_SAMPLES_PER_SYMBOL 1920

/* Float-typed equivalents — avoid integer-division errors in synthesis math */
#define TONE_SPACING_HZ   6.25f    /* Hz per FT8 tone step (6.25 Hz / tone)        */
#define FT8_SAMPLE_RATE_F 12000.0f /* Nominal sample rate used by all synthesis math */

#define K_MIN_SCORE       10
#define K_MAX_CANDIDATES  140
#define K_LDPC_ITERATIONS 25
#define K_FREQ_OSR        2
#define K_TIME_OSR        2

/* ── Iterative subtraction parameters ───────────────────────────────────── */
/*
 * K_MAX_PASSES — total number of decode passes.
 * Pass 0: full waterfall.
 * Pass 1: spectrogram-suppression pass on the original waterfall.
 */
#define K_MAX_PASSES   2

/* ── Soft SNR-scaled tile suppression constants ───────────────────────────── */
/*
 * Attenuation factor is a linear ramp between these SNR bounds:
 *   SNR ≤ K_SOFT_SUPP_SNR_MIN_DB  → factor = 1.0  (no suppression)
 *   SNR ≥ K_SOFT_SUPP_SNR_MAX_DB  → factor = 0.0  (full suppression)
 *   Between the two bounds         → factor = 1 − (snr − min) / (max − min)
 *
 * Rationale: a borderline decode (SNR near the decoder floor) has a higher
 * probability of tile overlap with an adjacent co-channel signal.  Scaling
 * the suppression by SNR reduces collateral damage in proportion to the
 * confidence in the decoded signal's tile locations.
 */
#define K_SOFT_SUPP_SNR_MIN_DB  (-5.0f)   /* below this: no suppression    */
#define K_SOFT_SUPP_SNR_MAX_DB  (15.0f)   /* above this: full suppression   */

/*
 * Pass 1 uses a wider candidate net.
 */
#define K_MIN_SCORE_PASS2       1
#define K_MAX_CANDIDATES_PASS2  200
#define K_LDPC_ITERATIONS_PASS2 50

/*
 * K_MAX_DECODED — cross-pass dedup hash table entries.
 * Sized to accommodate all two passes: 140 + 200 = 340.
 */
#define K_MAX_DECODED  (K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2)

/* ── Thread-local per-pass stats and noise floor ─────────────────────────── */
static _Thread_local int   tls_pass_counts[K_MAX_PASSES];
static _Thread_local int   tls_num_passes       = 0;
static _Thread_local float tls_last_noise_floor_db = 0.0f;

/* ── Callsign hash table ─────────────────────────────────────────────────── */

#define HASH_TABLE_SIZE 256
typedef struct { char callsign[12]; uint32_t hash; } callsign_entry_t;
typedef struct { callsign_entry_t entries[HASH_TABLE_SIZE]; int count; } callsign_table_t;

static void hash_table_init(callsign_table_t* tbl) { memset(tbl, 0, sizeof(*tbl)); }

static bool hash_table_lookup(callsign_table_t* tbl,
                               ftx_callsign_hash_type_t hash_type,
                               uint32_t hash, char* callsign)
{
    uint8_t  sh  = (hash_type == FTX_CALLSIGN_HASH_10_BITS) ? 12
                 : (hash_type == FTX_CALLSIGN_HASH_12_BITS) ? 10 : 0;
    uint16_t h10 = (hash >> (12 - sh)) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    /* Probe-limit guard: cap at HASH_TABLE_SIZE iterations so a full table
     * (all slots occupied) cannot spin forever.  Mirrors the count-check in
     * hash_table_add (R3-2). */
    for (int probe = 0; probe < HASH_TABLE_SIZE; probe++) {
        if (tbl->entries[idx].callsign[0] == '\0') break;
        if (((tbl->entries[idx].hash & 0x3FFFFFu) >> sh) == hash) {
            strcpy(callsign, tbl->entries[idx].callsign); return true; }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    callsign[0] = '\0'; return false;
}

static void hash_table_add(callsign_table_t* tbl, const char* callsign, uint32_t hash)
{
    /* Guard: discard new callsigns when the table is full rather than looping
     * forever.  Full table → unknown callsigns display as <HASH>, matching
     * WSJT-X first-seen behaviour; no crash, no hang, no data corruption. */
    if (tbl->count >= HASH_TABLE_SIZE) return;

    uint16_t h10 = (hash >> 12) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    while (tbl->entries[idx].callsign[0] != '\0') {
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            !strcmp(tbl->entries[idx].callsign, callsign)) {
            tbl->entries[idx].hash &= 0x3FFFFFu; return; }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash = hash;
}

static _Thread_local callsign_table_t* tls_hash_table = NULL;
static bool cb_lookup_hash(ftx_callsign_hash_type_t t, uint32_t h, char* cs) {
    if (!tls_hash_table) { cs[0] = '\0'; return false; }
    return hash_table_lookup(tls_hash_table, t, h, cs);
}
static void cb_save_hash(const char* cs, uint32_t h) {
    if (tls_hash_table) hash_table_add(tls_hash_table, cs, h);
}
static ftx_callsign_hash_interface_t s_hash_if = { cb_lookup_hash, cb_save_hash };

/* ── Spectrogram-domain tile suppression ─────────────────────────────────── */
/*
 * suppress_candidate_tiles — attenuate the waterfall tiles occupied by a
 * decoded FT8 signal, using the EXACT tone sequence from ft8_encode and a
 * soft SNR-scaled attenuation factor.
 *
 * For each of the 79 symbols, the bin actually transmitted plus its ±1
 * nearest neighbours (one FT8 bin = 3.125 Hz at freq_osr=2) are multiplied
 * by an attenuation factor derived from the decoded signal's SNR:
 *
 *   SNR ≤ K_SOFT_SUPP_SNR_MIN_DB  → factor = 1.0  (tile unchanged)
 *   SNR ≥ K_SOFT_SUPP_SNR_MAX_DB  → factor = 0.0  (tile zeroed to noise_raw)
 *   In between                     → factor = 1 − (snr − min) / (max − min)
 *
 * At factor = 0.0 the tile is assigned noise_raw (matching the previous
 * hard-zero behaviour for strong signals).  At intermediate factors the tile
 * value is linearly interpolated between its current value and noise_raw.
 * This preserves the Hann-window first-sidelobe cancellation for strong
 * signals while reducing collateral damage on adjacent weaker signals when
 * the decoded signal is borderline (SNR near the decoder floor).
 */
static void suppress_candidate_tiles(
    ftx_waterfall_t*       wf,
    const ftx_candidate_t* cand,
    const ftx_message_t*   msg,
    WF_ELEM_T              noise_raw,
    float                  snr_db)
{
    /* Compute soft attenuation factor from SNR */
    float norm   = (snr_db - K_SOFT_SUPP_SNR_MIN_DB)
                 / (K_SOFT_SUPP_SNR_MAX_DB - K_SOFT_SUPP_SNR_MIN_DB);
    float factor = 1.0f - fmaxf(0.0f, fminf(1.0f, norm));
    /* factor: 1.0 at SNR ≤ −5 dB (no change), 0.0 at SNR ≥ +15 dB (full suppress) */

    uint8_t tones[FT8_NN];
    ft8_encode(msg->payload, tones);

    int per_tsub = wf->freq_osr * wf->num_bins;

    for (int sym = 0; sym < FT8_NN; sym++)
    {
        int b = (int)cand->time_offset + sym;
        if (b < 0 || b >= wf->num_blocks) continue;

        int tone_bin = (int)cand->freq_offset + (int)tones[sym];

        WF_ELEM_T* block = wf->mag + b * wf->block_stride;
        for (int ts = 0; ts < wf->time_osr; ts++)
        {
            for (int fs = 0; fs < wf->freq_osr; fs++)
            {
                WF_ELEM_T* row = block + ts * per_tsub + fs * wf->num_bins;
                for (int d = -1; d <= 1; d++)
                {
                    int f = tone_bin + d;
                    if (f >= 0 && f < wf->num_bins)
                    {
                        /* Interpolate between current value and noise_raw
                         * by the attenuation factor:
                         *   factor = 0 → noise_raw  (full suppression)
                         *   factor = 1 → row[f]     (no change)            */
                        float attenuated = (float)noise_raw
                                         + factor * ((float)row[f] - (float)noise_raw);
                        row[f] = (WF_ELEM_T)(attenuated + 0.5f);
                    }
                }
            }
        }
    }
}

/* ── Noise floor computation (shared helper) ─────────────────────────────── */
/*
 * compute_noise_floor — histogram-median estimator over all waterfall bins.
 * Sets *noise_floor_db and *noise_raw from mon.wf.
 */
static void compute_noise_floor(
    const monitor_t* mon,
    float*           noise_floor_db,
    WF_ELEM_T*       noise_raw)
{
    uint32_t hist[256];
    memset(hist, 0, sizeof(hist));
    int total = mon->wf.num_blocks * mon->wf.block_stride;
    const WF_ELEM_T* wp = mon->wf.mag;
    for (int i = 0; i < total; i++) hist[wp[i]]++;
    uint32_t cum = 0; int med = 0;
    for (int v = 0; v < 256; v++) {
        cum += hist[v];
        if (cum * 2 >= (uint32_t)total) { med = v; break; }
    }
    *noise_floor_db = (float)med * 0.5f - 120.0f;
    *noise_raw      = (WF_ELEM_T)med;
}

/* ── T2 pre-condition: monitor_t isolation gate (task 1.1) ───────────────── */
/*
 * monitor.c isolation check (verified 2026-06-12 against native/ft8_lib_build/patched/common/monitor.c):
 *
 * monitor_init() allocates all internal state (window, last_frame, fft_work,
 * fft_cfg, and wf.mag) via malloc/calloc and stores each pointer exclusively in
 * fields of the monitor_t struct passed by pointer.  No static or TLS variables
 * are read or written by monitor_init or monitor_free.  monitor_free() only frees
 * those same heap pointers.  The kiss_fftr_alloc work area is likewise stored in
 * me->fft_work / me->fft_cfg — no library-level global state.
 *
 * VERDICT: Two monitor_t instances can be independently initialised and freed
 * within the same ft8_decode_all call stack without any interference.
 * GO — waterfall rebuild via a second monitor_t (T2 Decision 4) is safe.
 */

/* ── CP-FSK synthesis helpers (T1 — present but not yet wired into decode) ── */

/*
 * synth_ft8_cpsfc — synthesise a CP-FSK FT8 waveform into a caller-provided buffer.
 *
 * Parameters:
 *   tones       — FT8_NN (79) tone indices in [0..7], from ft8_encode
 *   freq_hz     — carrier frequency of tone 0 in Hz
 *   start_sample— first sample index in out_buf at which to write the waveform
 *   out_buf     — caller-provided output buffer; must be at least buf_len floats
 *   buf_len     — length of out_buf in samples
 *
 * Phase accumulates continuously across all 79 symbols (no phase discontinuity
 * at symbol boundaries).  Initialised to 0.0 (phase-zero assumption).
 * Writes cosf(phase) for each in-bounds sample; indices outside [0, buf_len)
 * are silently skipped (bounds guard — not an assert, not UB).
 * No heap or stack buffer allocation; no global or TLS state modified.
 */
static void synth_ft8_cpsfc(
    const uint8_t* tones,
    float          freq_hz,
    int            start_sample,
    float*         out_buf,
    int            buf_len)
{
    float phase = 0.0f;
    for (int sym = 0; sym < FT8_NN; sym++)
    {
        float f_tone    = freq_hz + (float)tones[sym] * TONE_SPACING_HZ;
        float phase_step = 2.0f * (float)M_PI * f_tone / FT8_SAMPLE_RATE_F;
        for (int s = 0; s < FT8_SAMPLES_PER_SYMBOL; s++)
        {
            int idx = start_sample + sym * FT8_SAMPLES_PER_SYMBOL + s;
            if (idx >= 0 && idx < buf_len)
                out_buf[idx] = cosf(phase);
            phase += phase_step;
        }
    }
}

/*
 * compute_projection_amplitude — least-squares projection of pcm onto synth.
 *
 * Returns dot(pcm[start..end], synth[start..end]) / dot(synth[start..end], synth[start..end]).
 * Returns 0.0f if denominator is zero (all-zero synth window) or if start >= end.
 * No heap allocation.
 */
static float compute_projection_amplitude(
    const float* pcm,
    const float* synth,
    int          start,
    int          end)
{
    if (start >= end) return 0.0f;
    float dot_ps = 0.0f;
    float dot_ss = 0.0f;
    for (int i = start; i < end; i++)
    {
        dot_ps += pcm[i]   * synth[i];
        dot_ss += synth[i] * synth[i];
    }
    return (dot_ss == 0.0f) ? 0.0f : dot_ps / dot_ss;
}

/* ── ABI sentinel ────────────────────────────────────────────────────────── */
int ft8_lib_version_check(void) { return FT8_SHIM_VERSION; }

/* ── Pass count query ────────────────────────────────────────────────────── */
int ft8_get_max_passes(void) { return K_MAX_PASSES; }

/* ── Noise floor query ───────────────────────────────────────────────────── */
float ft8_get_last_noise_floor_db(void) { return tls_last_noise_floor_db; }

/* ── Per-pass stats query ────────────────────────────────────────────────── */
int ft8_get_last_pass_counts(int* out_counts, int capacity)
{
    int n = (tls_num_passes < capacity) ? tls_num_passes : capacity;
    for (int i = 0; i < n; i++) out_counts[i] = tls_pass_counts[i];
    return n;
}

/* ── Main decode entry point ─────────────────────────────────────────────── */
int ft8_decode_all(
    const float* pcm,
    int          pcm_len,
    FT8Result*   results,
    int          max_results)
{
    if (pcm_len != FT8_EXPECTED_SAMPLES) return -1;

    /* ── 1. Build waterfall from PCM ─────────────────────────────────────── */
    monitor_t mon;
    monitor_config_t cfg = {
        .f_min = 200.0f, .f_max = 3000.0f,
        .sample_rate = FT8_SAMPLE_RATE,
        .time_osr = K_TIME_OSR, .freq_osr = K_FREQ_OSR,
        .protocol = FTX_PROTOCOL_FT8
    };
    monitor_init(&mon, &cfg);
    for (int pos = 0; pos + mon.block_size <= pcm_len; pos += mon.block_size)
        monitor_process(&mon, pcm + pos);

    /* ── 2. Callsign table ───────────────────────────────────────────────── */
    callsign_table_t htbl;
    hash_table_init(&htbl);
    tls_hash_table = &htbl;

    /* ── 3. Noise floor ──────────────────────────────────────────────────── */
    float     noise_floor_db;
    WF_ELEM_T noise_raw;
    compute_noise_floor(&mon, &noise_floor_db, &noise_raw);
    tls_last_noise_floor_db = noise_floor_db; /* expose to managed diagnostic layer */

    /* ── 4. Cross-pass dedup state ───────────────────────────────────────── */
    int            num_decoded  = 0;
    ftx_message_t  decoded_msgs[K_MAX_DECODED];
    ftx_message_t* decoded_ht[K_MAX_DECODED];
    memset(decoded_ht, 0, sizeof(decoded_ht));
    for (int i = 0; i < K_MAX_PASSES; i++) tls_pass_counts[i] = 0;
    tls_num_passes = 0;

    /* ── 4a. Cross-pass suppression accumulator ──────────────────────────── */
    /* Holds decoded candidates from pass 0 for spectrogram suppression
     * before pass 1.  snr_db stored per entry so suppress_candidate_tiles
     * can apply the soft SNR-scaled attenuation factor.                  */
    ftx_candidate_t all_supp_cands[K_MAX_CANDIDATES];
    ftx_message_t   all_supp_msgs [K_MAX_CANDIDATES];
    float           all_supp_snrs [K_MAX_CANDIDATES];
    int             n_all_supp    = 0;

    /* ── 5. Multi-pass decode loop ───────────────────────────────────────── */
    static const struct { int min_score; int max_cands; int ldpc; } k_pass_cfg[K_MAX_PASSES] = {
        { K_MIN_SCORE,       K_MAX_CANDIDATES,       K_LDPC_ITERATIONS       }, /* pass 0: full waterfall         */
        { K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }, /* pass 1: spectrogram-suppressed */
    };

    for (int pass = 0; pass < K_MAX_PASSES; pass++)
    {
        /* ── Early-exit: skip if result buffer is already full ───────────── */
        if (num_decoded >= max_results) {
            tls_pass_counts[pass] = 0;
            tls_num_passes        = pass + 1;
            continue;
        }

        /* ── Spectrogram suppression: execute before pass 1 ────────────────── */
        if (pass == 1)
        {
            for (int i = 0; i < n_all_supp; i++)
                suppress_candidate_tiles(&mon.wf, &all_supp_cands[i],
                                         &all_supp_msgs[i], noise_raw,
                                         all_supp_snrs[i]);
        }

        int pass_min_score = k_pass_cfg[pass].min_score;
        int pass_max_cands = k_pass_cfg[pass].max_cands;
        int pass_ldpc      = k_pass_cfg[pass].ldpc;

        /* Size the local candidate array to the maximum across all passes */
        ftx_candidate_t candidates[K_MAX_CANDIDATES_PASS2]; /* largest per-pass max */
        int ncands = ftx_find_candidates(&mon.wf, pass_max_cands,
                                          candidates, pass_min_score);

        int new_decodes = 0;

        for (int ci = 0; ci < ncands && num_decoded < max_results; ++ci)
        {
            const ftx_candidate_t* cand = &candidates[ci];

            ftx_message_t       msg;
            ftx_decode_status_t status;
            if (!ftx_decode_candidate(&mon.wf, cand, pass_ldpc, &msg, &status))
                continue;

            /* Cross-pass dedup */
            int  slot = (int)(msg.hash % K_MAX_DECODED);
            bool dup  = false, found = false;
            int  walk = slot;
            for (int s = 0; s < K_MAX_DECODED; ++s) {
                walk = (slot + s) % K_MAX_DECODED;
                if (!decoded_ht[walk]) { found = true; break; }
                if (decoded_ht[walk]->hash == msg.hash &&
                    !memcmp(decoded_ht[walk]->payload, msg.payload,
                            sizeof(msg.payload)))
                { dup = true; break; }
            }
            if (dup || !found) continue;

            /* Attempt text decode BEFORE occupying the dedup slot.
             * If ftx_message_decode fails (e.g. Type-4 hash not yet known),
             * bail here so the slot stays free for a later retry.          */
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;

            /* Text decode succeeded — commit to the dedup table */
            memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
            decoded_ht[walk] = &decoded_msgs[walk];

            /* Frequency, time offset, and SNR */
            float freq_hz = (mon.min_bin + cand->freq_offset +
                             (float)cand->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
            float dt      = (cand->time_offset +
                             (float)cand->time_sub / mon.wf.time_osr) * mon.symbol_period;

            uint8_t tones[FT8_NN];
            ft8_encode(msg.payload, tones);

            float signal_db;
            {
                float sum = 0.0f; int cnt = 0;
                int bs = mon.wf.block_stride;
                int pt = mon.wf.freq_osr * mon.wf.num_bins;
                int nb = mon.wf.num_bins;
                int b0 = (int)cand->time_offset; if (b0 < 0) b0 = 0;
                int b1 = b0 + FT8_NN; if (b1 > mon.wf.num_blocks) b1 = mon.wf.num_blocks;
                int fi = (int)cand->time_sub * pt + (int)cand->freq_sub * nb +
                         (int)cand->freq_offset;
                for (int b = b0; b < b1; b++) {
                    const WF_ELEM_T* row = mon.wf.mag + b * bs + fi;
                    float mx = (float)row[tones[b - b0]] * 0.5f - 120.0f;
                    sum += mx; cnt++;
                }
                signal_db = cnt > 0 ? sum / (float)cnt : noise_floor_db;
            }
            float snr = signal_db - noise_floor_db - 26.5f;

            FT8Result* r = &results[num_decoded++];
            r->freq_hz = (int)roundf(freq_hz);
            r->dt      = dt;
            r->snr     = (int)roundf(snr);
            strncpy(r->message, text, 35);
            r->message[35] = '\0';

            new_decodes++;

            /* Track for spectrogram suppression accumulator (pass 0 only).
             * Pass 0 signals are suppressed before pass 1.  Excess beyond
             * K_MAX_CANDIDATES is silently discarded.                        */
            if (pass == 0 && n_all_supp < K_MAX_CANDIDATES) {
                all_supp_cands[n_all_supp] = *cand;
                all_supp_msgs [n_all_supp] = msg;
                all_supp_snrs [n_all_supp] = snr;
                n_all_supp++;
            }
        }

        tls_pass_counts[pass] = new_decodes;
        tls_num_passes        = pass + 1;
    }

    /* ── 6. Cleanup ──────────────────────────────────────────────────────── */
    tls_hash_table = NULL;
    monitor_free(&mon);

    return num_decoded;
}
