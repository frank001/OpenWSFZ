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
 * fix-D001 — PCM-domain Successive Interference Cancellation (SIC):
 *
 *   Three-pass decode structure (K_MAX_PASSES = 3):
 *
 *   Pass 0: Full-waterfall decode (unchanged from p15 pass 0).
 *
 *   PCM subtraction (between passes 0 and 1):
 *     For each pass-0 decoded signal, estimate the sub-Hz carrier frequency
 *     via DFT parabolic interpolation on the Costas-array column, synthesise
 *     its CP-FSK waveform, and subtract from a working copy (pcm_residual) of
 *     the original PCM buffer.  Then free the monitor and rebuild the waterfall
 *     from pcm_residual.
 *
 *   Pass 1: Decode from the PCM-residual waterfall (wider candidate net).
 *
 *   Spectrogram suppression (between passes 1 and 2):
 *     All signals decoded in passes 0 and 1 have their waterfall tiles zeroed.
 *
 *   Pass 2: Decode from the suppressed PCM-residual waterfall.
 *
 *   The original const float* pcm argument is never written (Decision 6).
 *   The PCM residual buffer is 720 KB; see Decision 6 / OWSFZ_TLS_RESIDUAL.
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

/* FT8 tone spacing in Hz (symbol rate = 6.25 Hz) */
#define FT8_TONE_SPACING_HZ  6.25

#define K_MIN_SCORE       10
#define K_MAX_CANDIDATES  140
#define K_LDPC_ITERATIONS 25
#define K_FREQ_OSR        2
#define K_TIME_OSR        2

/* ── Iterative subtraction parameters ───────────────────────────────────── */
/*
 * K_MAX_PASSES — total number of decode passes.
 * Pass 0: full waterfall.
 * Pass 1: PCM-residual waterfall (after PCM-domain SIC).
 * Pass 2: spectrogram-suppression pass on the PCM-cleaned waterfall.
 */
#define K_MAX_PASSES   3

/*
 * Passes 1 and 2 use a wider candidate net.
 */
#define K_MIN_SCORE_PASS2       1
#define K_MAX_CANDIDATES_PASS2  200
#define K_LDPC_ITERATIONS_PASS2 50

/*
 * PCM-domain SIC — SNR gate.  Signals below this threshold use the
 * waterfall bin-centre frequency without parabolic interpolation.
 */
#define K_PCM_SIC_SNR_GATE_DB  (-10.0f)

/*
 * K_MAX_DECODED — cross-pass dedup hash table entries.
 * Sized to accommodate all three passes.
 */
#define K_MAX_DECODED  (K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2 + K_MAX_CANDIDATES_PASS2)

/* ── Thread-local per-pass stats ─────────────────────────────────────────── */
static _Thread_local int tls_pass_counts[K_MAX_PASSES];
static _Thread_local int tls_num_passes = 0;

/* ── PCM residual buffer ─────────────────────────────────────────────────── */
/*
 * Decision 6 (revised): heap-allocated working buffer for PCM-domain SIC.
 *
 * The original implementation used a stack allocation (float[180000] = 720 KB).
 * That exhausts the usable call stack on .NET thread pool threads, which have a
 * 1 MB stack of which the CLR reserves ~128 KB for its own use (GC, managed
 * exception handling).  Adding the managed frames (~36 KB), the ft8_decode_all
 * frame (~742 KB), and the monitor_process frame (~64 KB) exceeds ~896 KB,
 * causing a fatal 0xC0000005 access violation.
 *
 * Heap allocation eliminates the stack risk entirely.  malloc(720 KB) is
 * effectively guaranteed to succeed on any system that can load this DLL.
 * The buffer is freed in step 6 (cleanup) below.
 */

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
 * suppress_candidate_tiles — zero the waterfall tiles occupied by a decoded
 * FT8 signal, using the EXACT tone sequence from ft8_encode.
 *
 * For each of the 79 symbols, the bin actually transmitted plus its ±1
 * nearest neighbours (one FT8 bin = 3.125 Hz at freq_osr=2) are set to
 * noise_raw.  This covers the Hann-window first sidelobe while preserving
 * the 6 remaining tone bins that an adjacent co-channel signal might use.
 */
static void suppress_candidate_tiles(
    ftx_waterfall_t*       wf,
    const ftx_candidate_t* cand,
    const ftx_message_t*   msg,
    WF_ELEM_T              noise_raw)
{
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
                        row[f] = noise_raw;
                }
            }
        }
    }
}

/* ── Carrier frequency estimation (fix-D001) ────────────────────────────── */
/*
 * goertzel_magnitude — compute the DFT magnitude at integer bin k of an
 * N-point sequence starting at pcm[start].  Uses Goertzel's algorithm
 * (2 multiplies + 2 adds per sample).
 *
 * Returns: |X[k]| (magnitude, not power).  Returns 0.0 if power < 0
 *          (numerical noise near the noise floor).
 */
static double goertzel_magnitude(const float* pcm, int start, int N, int k)
{
    double coeff = 2.0 * cos(2.0 * M_PI * (double)k / (double)N);
    double s1 = 0.0, s2 = 0.0;
    for (int n = 0; n < N; n++) {
        double s = (double)pcm[start + n] + coeff * s1 - s2;
        s2 = s1;
        s1 = s;
    }
    double power = s1 * s1 + s2 * s2 - coeff * s1 * s2;
    return power > 0.0 ? sqrt(power) : 0.0;
}

/*
 * estimate_carrier_hz_offset — estimate the sub-Hz carrier frequency offset
 * via DFT parabolic interpolation on the FT8 Costas-array column.
 *
 * The first 7 symbols of every FT8 frame are the Costas sequence
 * {3, 1, 4, 0, 6, 5, 2} (tone indices in the 6.25 Hz grid).  For each
 * symbol window of FT8_SAMPLES_PER_SYMBOL (1920) samples, the DFT
 * magnitude is computed at the expected tone bin and its two neighbours
 * using Goertzel's algorithm; parabolic interpolation then estimates the
 * sub-bin offset.  The result is averaged across all 7 symbols.
 *
 * Parameters:
 *   pcm_buf  — original (unmodified) PCM buffer
 *   pcm_len  — buffer length (must be FT8_EXPECTED_SAMPLES)
 *   freq_hz  — waterfall-derived carrier frequency in Hz
 *   dt_s     — time offset in seconds (from waterfall candidate)
 *   snr_db   — SNR estimate; signals below K_PCM_SIC_SNR_GATE_DB return 0.0f
 *
 * Returns: sub-Hz carrier offset in Hz.  Add to freq_hz for refined carrier.
 *          Returns 0.0f if SNR is below gate or estimation fails.
 */
static float estimate_carrier_hz_offset(
    const float* pcm_buf, int pcm_len,
    float freq_hz, float dt_s, float snr_db)
{
    /* Gate: below SNR threshold, use bin-centre frequency without interpolation */
    if (snr_db < K_PCM_SIC_SNR_GATE_DB)
        return 0.0f;

    /* FT8 Costas sequence (3GPP TS 103 236 / WSJT-X protocol) */
    static const int costas_seq[7] = {3, 1, 4, 0, 6, 5, 2};

    /* Starting sample of the frame */
    int t_start = (int)roundf(dt_s * (float)FT8_SAMPLE_RATE);
    if (t_start < 0) t_start = 0;

    const int N = FT8_SAMPLES_PER_SYMBOL;  /* 1920 */
    const double bin_width_hz = (double)FT8_SAMPLE_RATE / (double)N; /* 6.25 Hz */

    double sum_delta = 0.0;
    int    valid     = 0;

    for (int sym = 0; sym < 7; sym++)
    {
        int t_sym = t_start + sym * N;

        /* Guard: symbol window must lie within the buffer */
        if (t_sym < 0 || t_sym + N > pcm_len) continue;

        /* Expected frequency for this Costas tone */
        double f_sym = (double)freq_hz + (double)costas_seq[sym] * FT8_TONE_SPACING_HZ;

        /* Nearest integer DFT bin */
        int k = (int)round(f_sym / bin_width_hz);
        if (k < 1 || k >= N / 2 - 1) continue; /* guard edges */

        /* Goertzel magnitudes at k-1, k, k+1 */
        double m_minus = goertzel_magnitude(pcm_buf, t_sym, N, k - 1);
        double m_0     = goertzel_magnitude(pcm_buf, t_sym, N, k    );
        double m_plus  = goertzel_magnitude(pcm_buf, t_sym, N, k + 1);

        /* Parabolic interpolation: δ = 0.5 × (M+1 − M-1) / (2M0 − M-1 − M+1) */
        double denom = 2.0 * m_0 - m_minus - m_plus;
        if (denom <= 0.0) continue; /* peak not at k; skip */

        double delta_bins = 0.5 * (m_plus - m_minus) / denom;
        double delta_hz   = delta_bins * bin_width_hz;

        sum_delta += delta_hz;
        valid++;
    }

    return (valid > 0) ? (float)(sum_delta / (double)valid) : 0.0f;
}

/* ── CP-FSK waveform synthesis and subtraction (fix-D001) ───────────────── */
/*
 * synthesise_cp_fsk — synthesise a continuous-phase FSK (CP-FSK) FT8 replica
 * and SUBTRACT it in-place from out_buf.
 *
 * The replica is placed starting at sample max(0, round(dt_s * sample_rate)).
 * A double-precision phase accumulator ensures < 10⁻⁸ rad phase error over
 * the full 79 × 1920 = 151 680 sample waveform.
 *
 * Parameters:
 *   out_buf     — residual PCM buffer; replica is subtracted in-place
 *   buf_len     — size of out_buf
 *   tones       — 79-element tone sequence (from ft8_encode)
 *   n_symbols   — number of symbols (FT8_NN = 79)
 *   carrier_hz  — refined carrier frequency in Hz (base of the 8-tone grid)
 *   dt_s        — frame time offset in seconds
 *   amplitude   — peak amplitude of the replica
 *   sample_rate — PCM sample rate (FT8_SAMPLE_RATE = 12000)
 */
static void synthesise_cp_fsk(
    float*          out_buf,
    int             buf_len,
    const uint8_t*  tones,
    int             n_symbols,
    float           carrier_hz,
    float           dt_s,
    float           amplitude,
    int             sample_rate)
{
    int t_start_raw = (int)roundf(dt_s * (float)sample_rate);
    int t_start     = (t_start_raw > 0) ? t_start_raw : 0;

    double phase = 0.0; /* continuous-phase accumulator (double precision) */

    /* If the frame started before the buffer, advance the phase accumulator
     * past the skipped pre-buffer samples so the replica at buffer sample 0
     * has the correct phase.  Using the first symbol's frequency (tones[0])
     * for the pre-advancement.  fmod keeps the phase in [0, 2π) and avoids
     * double-precision accumulation error over potentially thousands of
     * skipped samples. */
    if (t_start_raw < 0) {
        int    skipped = -t_start_raw;
        double f0      = (double)carrier_hz + (double)tones[0] * FT8_TONE_SPACING_HZ;
        double step0   = 2.0 * M_PI * f0 / (double)sample_rate;
        phase = fmod(step0 * (double)skipped, 2.0 * M_PI);
    }

    for (int sym = 0; sym < n_symbols; sym++)
    {
        double f_sym       = (double)carrier_hz + (double)tones[sym] * FT8_TONE_SPACING_HZ;
        double phase_step  = 2.0 * M_PI * f_sym / (double)sample_rate;

        for (int n = 0; n < FT8_SAMPLES_PER_SYMBOL; n++)
        {
            int idx = t_start + sym * FT8_SAMPLES_PER_SYMBOL + n;
            if (idx < buf_len) /* t_start >= 0 guarantees idx >= 0 */
                out_buf[idx] -= amplitude * (float)cos(phase);

            phase += phase_step; /* advance phase AFTER sample output */
        }
        /* Phase carries over across symbol boundaries — continuous phase */
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

/* ── ABI sentinel ────────────────────────────────────────────────────────── */
int ft8_lib_version_check(void) { return FT8_SHIM_VERSION; }

/* ── Pass count query ────────────────────────────────────────────────────── */
int ft8_get_max_passes(void) { return K_MAX_PASSES; }

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

    /* ── 4. Cross-pass dedup state ───────────────────────────────────────── */
    int            num_decoded  = 0;
    ftx_message_t  decoded_msgs[K_MAX_DECODED];
    ftx_message_t* decoded_ht[K_MAX_DECODED];
    memset(decoded_ht, 0, sizeof(decoded_ht));
    for (int i = 0; i < K_MAX_PASSES; i++) tls_pass_counts[i] = 0;
    tls_num_passes = 0;

    /* ── 4a. PCM residual buffer ─────────────────────────────────────────── */
    /* 720 KB heap buffer — see Decision 6 (revised comment above).
     * Content is populated only when pass 0 decodes at least one signal.
     * The original `pcm` pointer is never written.
     * free(pcm_residual) is called unconditionally in step 6 below.     */
    float* pcm_residual = (float*)malloc((size_t)FT8_EXPECTED_SAMPLES * sizeof(float));
    if (!pcm_residual) {
        tls_hash_table = NULL;
        monitor_free(&mon);
        return -2; /* out of memory; managed caller treats any negative as error */
    }

    /* ── 4b. Cross-pass suppression accumulator ──────────────────────────── */
    /* Holds decoded candidates from passes 0 and 1 for spectrogram
     * suppression before pass 2, AND for PCM subtraction after pass 0.
     * Capacity: pass-0 cap (140) + pass-1 cap (200) = 340.            */
    ftx_candidate_t all_supp_cands[K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2];
    ftx_message_t   all_supp_msgs [K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2];
    float           all_supp_snrs [K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2];
    int             n_all_supp    = 0;

    /* ── 5. Multi-pass decode loop ───────────────────────────────────────── */
    /* Per-pass configuration table: min_score, max_candidates, ldpc_iters.
     * K_MAX_PASSES is 3; add one row here for each additional pass.        */
    static const struct { int min_score; int max_cands; int ldpc; } k_pass_cfg[K_MAX_PASSES] = {
        { K_MIN_SCORE,       K_MAX_CANDIDATES,       K_LDPC_ITERATIONS       }, /* pass 0: full waterfall */
        { K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }, /* pass 1: PCM-residual  */
        { K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }, /* pass 2: spectrogram   */
    };

    for (int pass = 0; pass < K_MAX_PASSES; pass++)
    {
        /* ── Early-exit: skip everything if result buffer is already full ── */
        /* Hoisted before PCM subtraction to avoid a wasted 720 KB memcpy +  */
        /* replica synthesis + waterfall rebuild when the buffer is saturated.*/
        if (num_decoded >= max_results) {
            tls_pass_counts[pass] = 0;
            tls_num_passes        = pass + 1;
            /* Spectrogram suppression must still run before pass 2 */
            if (pass == 1) {
                for (int i = 0; i < n_all_supp; i++)
                    suppress_candidate_tiles(&mon.wf, &all_supp_cands[i],
                                             &all_supp_msgs[i], noise_raw);
            }
            continue;
        }

        /* ── PCM subtraction: execute before pass 1 ─────────────────────── */
        if (pass == 1)
        {
            if (num_decoded > 0)
            {
                /* Copy original PCM to working residual */
                memcpy(pcm_residual, pcm, (size_t)pcm_len * sizeof(float));

                /* For each pass-0 decoded signal: synthesise replica and subtract */
                for (int si = 0; si < n_all_supp; si++)
                {
                    /* Tone sequence from the decoded payload */
                    uint8_t tones[FT8_NN];
                    ft8_encode(all_supp_msgs[si].payload, tones);

                    /* Carrier and timing from the candidate + monitor */
                    float freq_hz = (mon.min_bin
                                     + (float)all_supp_cands[si].freq_offset
                                     + (float)all_supp_cands[si].freq_sub / (float)mon.wf.freq_osr)
                                    / mon.symbol_period;
                    float dt_s    = ((float)all_supp_cands[si].time_offset
                                     + (float)all_supp_cands[si].time_sub / (float)mon.wf.time_osr)
                                    * mon.symbol_period;

                    /* Sub-Hz carrier refinement via Costas-column DFT interpolation */
                    float offset  = estimate_carrier_hz_offset(
                                        pcm, pcm_len, freq_hz, dt_s, all_supp_snrs[si]);
                    float carrier = freq_hz + offset;

                    /* Amplitude: A = sqrt(2) × 10^(SNR/20) × noise_rms */
                    float noise_rms = powf(10.0f, noise_floor_db / 20.0f);
                    float amplitude = sqrtf(2.0f)
                                    * powf(10.0f, all_supp_snrs[si] / 20.0f)
                                    * noise_rms;

                    synthesise_cp_fsk(pcm_residual, pcm_len, tones, FT8_NN,
                                      carrier, dt_s, amplitude, FT8_SAMPLE_RATE);
                }

                /* Rebuild waterfall from residual PCM */
                monitor_free(&mon);
                monitor_init(&mon, &cfg);
                for (int pos = 0; pos + mon.block_size <= pcm_len; pos += mon.block_size)
                    monitor_process(&mon, pcm_residual + pos);

                /* Recompute noise floor from the new waterfall */
                compute_noise_floor(&mon, &noise_floor_db, &noise_raw);
            }
            /* else: pass 0 decoded nothing; skip PCM subtraction entirely.
             * Pass 1 runs on the same (original) waterfall.               */
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
            float snr = signal_db - noise_floor_db - 26.0f;

            FT8Result* r = &results[num_decoded++];
            r->freq_hz = (int)roundf(freq_hz);
            r->dt      = dt;
            r->snr     = (int)roundf(snr);
            strncpy(r->message, text, 35);
            r->message[35] = '\0';

            new_decodes++;

            /* Track for cross-pass suppression accumulator (all passes
             * up to the final one) so spectrogram suppression before
             * pass 2 covers passes 0 AND 1.                             */
            int cap = K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2;
            if (pass < K_MAX_PASSES - 1 && n_all_supp < cap) {
                all_supp_cands[n_all_supp] = *cand;
                all_supp_msgs [n_all_supp] = msg;
                all_supp_snrs [n_all_supp] = snr;
                n_all_supp++;
            }
        }

        tls_pass_counts[pass] = new_decodes;
        tls_num_passes        = pass + 1;

        /* ── Spectrogram suppression: execute before pass 2 ─────────────── */
        if (pass == 1)
        {
            /* Suppress all decoded signals from passes 0 and 1 on the
             * PCM-residual waterfall before pass 2.                     */
            for (int i = 0; i < n_all_supp; i++)
                suppress_candidate_tiles(&mon.wf, &all_supp_cands[i],
                                         &all_supp_msgs[i], noise_raw);
        }
    }

    /* ── 6. Cleanup ──────────────────────────────────────────────────────── */
    free(pcm_residual);
    tls_hash_table = NULL;
    monitor_free(&mon);

    return num_decoded;
}
