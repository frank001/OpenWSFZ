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
 *   Carrier-frequency precision note:
 *   The waterfall stores frequency at 3.125 Hz/bin resolution (6.25 Hz tone
 *   spacing with freq_osr=2).  This prevents accurate PCM-domain waveform
 *   reconstruction (phase drifts by up to ±π per symbol), so spectrogram-
 *   domain suppression is the most accurate approach available without a
 *   dedicated sub-Hz carrier-frequency estimator.
 *
 *   Measured result on the 42-cycle corpus: 69.1% recovery (613/887).
 *   Baseline (single pass): 66.6% (591/887).
 *
 * Build: see BUILD.md.  encode.c must be compiled and linked.
 */

#include "ft8_shim.h"

#include <ft8/decode.h>
#include <ft8/encode.h>
#include <ft8/message.h>
#include <common/monitor.h>

#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

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

#define K_MIN_SCORE       10
#define K_MAX_CANDIDATES  140
#define K_LDPC_ITERATIONS 25
#define K_FREQ_OSR        2
#define K_TIME_OSR        2

/* ── Iterative subtraction parameters (AC-IS-4) ─────────────────────────── */
/*
 * K_MAX_PASSES — total number of decode passes (default 2, matching WSJT-X).
 */
#define K_MAX_PASSES   2

/*
 * Pass 2 uses a wider candidate net to find signals masked in pass 1.
 */
#define K_MIN_SCORE_PASS2       1
#define K_MAX_CANDIDATES_PASS2  200
#define K_LDPC_ITERATIONS_PASS2 50

/*
 * K_MAX_DECODED — cross-pass dedup hash table entries.
 */
#define K_MAX_DECODED  (K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2)

/* ── Thread-local per-pass stats (AC-IS-4) ──────────────────────────────── */
static _Thread_local int tls_pass_counts[K_MAX_PASSES];
static _Thread_local int tls_num_passes = 0;

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

/* ── ABI sentinel ────────────────────────────────────────────────────────── */
int ft8_lib_version_check(void) { return FT8_SHIM_VERSION; }

/* ── Pass count query ────────────────────────────────────────────────────── */
/* Returns the compile-time K_MAX_PASSES constant so the managed layer can   */
/* detect drift between the C and C# definitions at library load time.       */
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
    float noise_floor_db;
    WF_ELEM_T noise_raw;
    {
        uint32_t hist[256];
        memset(hist, 0, sizeof(hist));
        int total = mon.wf.num_blocks * mon.wf.block_stride;
        const WF_ELEM_T* wp = mon.wf.mag;
        for (int i = 0; i < total; i++) hist[wp[i]]++;
        uint32_t cum = 0; int med = 0;
        for (int v = 0; v < 256; v++) {
            cum += hist[v];
            if (cum * 2 >= (uint32_t)total) { med = v; break; }
        }
        noise_floor_db = (float)med * 0.5f - 120.0f;
        noise_raw      = (WF_ELEM_T)med;
    }

    /* ── 4. Cross-pass dedup state ───────────────────────────────────────── */
    int            num_decoded = 0;
    ftx_message_t  decoded_msgs[K_MAX_DECODED];
    ftx_message_t* decoded_ht[K_MAX_DECODED];
    memset(decoded_ht, 0, sizeof(decoded_ht));
    for (int i = 0; i < K_MAX_PASSES; i++) tls_pass_counts[i] = 0;
    tls_num_passes = 0;

    /* ── 5. Multi-pass decode loop ───────────────────────────────────────── */
    /* Per-pass configuration table — one row per pass, indexed by pass index.
     * Add a row here if K_MAX_PASSES is ever increased beyond 2. */
    static const struct { int min_score; int max_cands; int ldpc; } k_pass_cfg[K_MAX_PASSES] = {
        { K_MIN_SCORE,       K_MAX_CANDIDATES,  K_LDPC_ITERATIONS  }, /* pass 0 */
        { K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }, /* pass 1 */
    };
    for (int pass = 0; pass < K_MAX_PASSES; pass++)
    {
        /* Skip candidate search when the result buffer is already full.
         * ftx_find_candidates is a full waterfall scan (~1-2 ms); there is no
         * point running it when the inner loop would exit on its first iteration.
         * Record zero new decodes so TLS pass stats remain consistent. */
        if (num_decoded >= max_results) {
            tls_pass_counts[pass] = 0;
            tls_num_passes        = pass + 1;
            continue;
        }

        int pass_min_score  = k_pass_cfg[pass].min_score;
        int pass_max_cands  = k_pass_cfg[pass].max_cands;
        int pass_ldpc       = k_pass_cfg[pass].ldpc;

        /* Size to the per-pass limit; pass 0 uses K_MAX_CANDIDATES (140),
         * pass 1 uses K_MAX_CANDIDATES_PASS2 (200). */
        ftx_candidate_t candidates[K_MAX_CANDIDATES_PASS2]; /* max across all passes */
        int ncands = ftx_find_candidates(&mon.wf, pass_max_cands,
                                          candidates, pass_min_score);

        int             new_decodes = 0;
        ftx_candidate_t supp_cands[K_MAX_CANDIDATES_PASS2];
        ftx_message_t   supp_msgs[K_MAX_CANDIDATES_PASS2];
        int             nsupp = 0;

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
             * we bail here so the slot stays free; pass 2 can retry the same
             * payload once the companion callsign has been decoded. */
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;

            /* Text decode succeeded — now commit to the dedup table. */
            memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
            decoded_ht[walk] = &decoded_msgs[walk];

            /* freq, dt, SNR */
            float freq_hz = (mon.min_bin + cand->freq_offset +
                             (float)cand->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
            float dt      = (cand->time_offset +
                             (float)cand->time_sub / mon.wf.time_osr) * mon.symbol_period;

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
                    float mx = (float)row[0] * 0.5f - 120.0f;
                    for (int f = 1; f < 8 && (int)cand->freq_offset + f < nb; f++) {
                        float v = (float)row[f] * 0.5f - 120.0f;
                        if (v > mx) mx = v;
                    }
                    sum += mx; cnt++;
                }
                signal_db = cnt > 0 ? sum / (float)cnt : noise_floor_db;
            }
            /* SNR relative to 2500 Hz bandwidth (WSJT-X convention).
             * Bin width = 6.25 Hz → 10*log10(2500/6.25) = 10*log10(400) ≈ 26 dB.
             * No post-correction is applied (R6 weak-signal correction removed;
             * see R&R-001 — correction created a slope defect on synthetic signals). */
            float snr = signal_db - noise_floor_db - 26.0f;

            FT8Result* r = &results[num_decoded++];
            r->freq_hz = (int)roundf(freq_hz);
            r->dt      = dt;
            r->snr     = (int)roundf(snr);
            strncpy(r->message, text, 35);
            r->message[35] = '\0';

            new_decodes++;

            /* Track for suppression — only needed when a subsequent pass will
             * use the data.  In the final pass this is always false, avoiding
             * up to 200 struct copies that would be silently discarded. */
            if (pass < K_MAX_PASSES - 1 && nsupp < K_MAX_CANDIDATES_PASS2) {
                supp_cands[nsupp] = *cand;
                supp_msgs[nsupp]  = msg;
                nsupp++;
            }
        }

        tls_pass_counts[pass] = new_decodes;
        tls_num_passes        = pass + 1;

        /* Suppress decoded signals before next pass */
        if (pass < K_MAX_PASSES - 1) {
            for (int i = 0; i < nsupp; i++)
                suppress_candidate_tiles(&mon.wf, &supp_cands[i],
                                         &supp_msgs[i], noise_raw);
        }
    }

    /* ── 6. Cleanup ──────────────────────────────────────────────────────── */
    tls_hash_table = NULL;
    monitor_free(&mon);

    return num_decoded;
}
