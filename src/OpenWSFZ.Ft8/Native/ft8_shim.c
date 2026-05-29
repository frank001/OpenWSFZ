/*
 * ft8_shim.c — OpenWSFZ libft8.dll shim
 *
 * Wraps the kgoba/ft8_lib v2.0 decode pipeline (monitor → find candidates →
 * decode each → unpack text) behind the simple ft8_decode_all() entry point
 * declared in ft8_shim.h.
 *
 * Build: compile alongside ft8_lib source files (see BUILD.md for the full
 * MSVC command). Include path must contain the ft8_lib repo root so that
 * #include <ft8/...> and #include <common/...> resolve correctly.
 */

#include "ft8_shim.h"

#include <ft8/decode.h>
#include <ft8/message.h>
#include <common/monitor.h>

#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

/* ── MSVC compatibility ──────────────────────────────────────────────────── */
/*
 * stpcpy is POSIX (C17 annex K optional) but absent from MSVC's CRT import
 * libs.  ft8_lib/ft8/message.c uses it; providing it here prevents LNK2019.
 */
#ifdef _MSC_VER
/* External linkage required so message.obj can resolve the reference. */
char* stpcpy(char* dest, const char* src)
{
    while ((*dest = *src) != '\0') { dest++; src++; }
    return dest;
}
#endif

/* ── Decode configuration (matches demo/decode_ft8.c defaults) ──────────── */

#define FT8_SAMPLE_RATE      12000
#define FT8_EXPECTED_SAMPLES 180000   /* 15 s × 12 000 Hz */
#define FT8_SLOT_TIME        15.0f

#define K_MIN_SCORE       10
#define K_MAX_CANDIDATES  140
#define K_LDPC_ITERATIONS 25
#define K_FREQ_OSR        2
#define K_TIME_OSR        2

/* ── Simple per-call callsign hash table ────────────────────────────────── */
/*
 * ftx_message_decode() uses a hash table to resolve hashed callsigns in
 * Type 4 (non-standard) messages.  We supply a minimal per-call table so
 * the library never receives a NULL interface pointer.  Standard messages
 * (Type 1/2/3) do not consult the table at all; Type 4 callsigns will be
 * displayed as <HASH> when the originating callsign is not in this table —
 * identical behaviour to the demo app on first-seen calls.
 */

#define HASH_TABLE_SIZE 256

typedef struct
{
    char     callsign[12]; /* up to 11 chars + NUL */
    uint32_t hash;         /* 8-MSB age | 22-LSB hash value */
} callsign_entry_t;

typedef struct
{
    callsign_entry_t entries[HASH_TABLE_SIZE];
    int              count;
} callsign_table_t;

static void hash_table_init(callsign_table_t* tbl)
{
    memset(tbl, 0, sizeof(*tbl));
}

static bool hash_table_lookup(callsign_table_t*      tbl,
                               ftx_callsign_hash_type_t hash_type,
                               uint32_t               hash,
                               char*                  callsign)
{
    uint8_t  hash_shift = (hash_type == FTX_CALLSIGN_HASH_10_BITS) ? 12
                        : (hash_type == FTX_CALLSIGN_HASH_12_BITS) ? 10
                        : 0;
    uint16_t hash10    = (hash >> (12 - hash_shift)) & 0x3FFu;
    int      idx       = (hash10 * 23) % HASH_TABLE_SIZE;

    while (tbl->entries[idx].callsign[0] != '\0')
    {
        if (((tbl->entries[idx].hash & 0x3FFFFFu) >> hash_shift) == hash)
        {
            strcpy(callsign, tbl->entries[idx].callsign);
            return true;
        }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    callsign[0] = '\0';
    return false;
}

static void hash_table_add(callsign_table_t* tbl,
                            const char*       callsign,
                            uint32_t          hash)
{
    uint16_t hash10 = ((hash >> 12) & 0x3FFu);
    int      idx    = (hash10 * 23) % HASH_TABLE_SIZE;

    while (tbl->entries[idx].callsign[0] != '\0')
    {
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            (0 == strcmp(tbl->entries[idx].callsign, callsign)))
        {
            /* duplicate — reset age */
            tbl->entries[idx].hash &= 0x3FFFFFu;
            return;
        }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash         = hash;
}

/* Thread-local storage so the C callback can reach the per-call table.
 * The managed side calls ft8_decode_all() from a single thread (Ft8Decoder
 * is already single-threaded after the p12 rewrite), so TLS is sufficient. */
static _Thread_local callsign_table_t* tls_hash_table = NULL;

static bool cb_lookup_hash(ftx_callsign_hash_type_t hash_type,
                            uint32_t                 hash,
                            char*                    callsign)
{
    if (tls_hash_table == NULL) { callsign[0] = '\0'; return false; }
    return hash_table_lookup(tls_hash_table, hash_type, hash, callsign);
}

static void cb_save_hash(const char* callsign, uint32_t hash)
{
    if (tls_hash_table != NULL)
        hash_table_add(tls_hash_table, callsign, hash);
}

static ftx_callsign_hash_interface_t s_hash_if = {
    .lookup_hash = cb_lookup_hash,
    .save_hash   = cb_save_hash,
};

/* ── ABI sentinel ────────────────────────────────────────────────────────── */

int ft8_lib_version_check(void)
{
    return FT8_SHIM_VERSION;
}

/* ── Main decode entry point ─────────────────────────────────────────────── */

int ft8_decode_all(
    const float* pcm,
    int          pcm_len,
    FT8Result*   results,
    int          max_results)
{
    if (pcm_len != FT8_EXPECTED_SAMPLES)
        return -1;

    /* ── 1. Build waterfall from PCM ─────────────────────────────────────── */
    monitor_t mon;
    monitor_config_t cfg = {
        .f_min       = 200.0f,
        .f_max       = 3000.0f,
        .sample_rate = FT8_SAMPLE_RATE,
        .time_osr    = K_TIME_OSR,
        .freq_osr    = K_FREQ_OSR,
        .protocol    = FTX_PROTOCOL_FT8
    };
    monitor_init(&mon, &cfg);

    /* Feed PCM in block_size chunks (monitor.block_size is set by monitor_init). */
    for (int pos = 0; pos + mon.block_size <= pcm_len; pos += mon.block_size)
    {
        monitor_process(&mon, pcm + pos);
    }

    /* ── 2. Find sync candidates ─────────────────────────────────────────── */
    ftx_candidate_t candidates[K_MAX_CANDIDATES];
    int num_candidates = ftx_find_candidates(&mon.wf,
                                              K_MAX_CANDIDATES,
                                              candidates,
                                              K_MIN_SCORE);

    /* ── 3. Set up per-call hash table ───────────────────────────────────── */
    callsign_table_t hash_table;
    hash_table_init(&hash_table);
    tls_hash_table = &hash_table;

    /* ── 4. Decode each candidate ────────────────────────────────────────── */
    /*
     * Deduplication via a small message-hash table (same approach as demo).
     * ftx_message_t.hash is a 16-bit value; collisions are rare (50 slots).
     */
    int            num_decoded = 0;
    ftx_message_t  decoded_msgs[K_MAX_CANDIDATES];     /* decoded payloads     */
    ftx_message_t* decoded_ht[K_MAX_CANDIDATES];       /* dedup hash table     */
    memset(decoded_ht, 0, sizeof(decoded_ht));

    for (int ci = 0; ci < num_candidates && num_decoded < max_results; ++ci)
    {
        const ftx_candidate_t* cand = &candidates[ci];

        ftx_message_t      message;
        ftx_decode_status_t status;
        if (!ftx_decode_candidate(&mon.wf, cand, K_LDPC_ITERATIONS,
                                   &message, &status))
            continue;

        /* Dedup check */
        int   slot       = message.hash % K_MAX_CANDIDATES;
        bool  is_dup     = false;
        bool  slot_found = false;
        int   walk       = slot;
        for (int s = 0; s < K_MAX_CANDIDATES; ++s)
        {
            walk = (slot + s) % K_MAX_CANDIDATES;
            if (decoded_ht[walk] == NULL) { slot_found = true; break; }
            if (decoded_ht[walk]->hash == message.hash &&
                memcmp(decoded_ht[walk]->payload, message.payload,
                       sizeof(message.payload)) == 0)
            { is_dup = true; break; }
        }
        if (is_dup || !slot_found) continue;

        /* Store message for dedup */
        memcpy(&decoded_msgs[walk], &message, sizeof(message));
        decoded_ht[walk] = &decoded_msgs[walk];

        /* Unpack text */
        char text[FTX_MAX_MESSAGE_LENGTH + 1];
        if (ftx_message_decode(&message, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
            continue;

        /* Compute freq, dt, snr from candidate coordinates */
        float freq_hz = (mon.min_bin + cand->freq_offset +
                         (float)cand->freq_sub / mon.wf.freq_osr) / mon.symbol_period;
        float dt      = (cand->time_offset +
                         (float)cand->time_sub / mon.wf.time_osr) * mon.symbol_period;
        float snr_f   = (float)cand->score * 0.5f;

        FT8Result* r = &results[num_decoded++];
        r->freq_hz = (int)roundf(freq_hz);
        r->dt      = dt;
        r->snr     = (int)roundf(snr_f);
        strncpy(r->message, text, 35);
        r->message[35] = '\0';
    }

    /* ── 5. Cleanup ──────────────────────────────────────────────────────── */
    tls_hash_table = NULL;
    monitor_free(&mon);

    return num_decoded;
}
