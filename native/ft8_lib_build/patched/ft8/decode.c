#include "decode.h"
#include "constants.h"
#include "crc.h"
#include "ldpc.h"

#include <stdbool.h>
#include <math.h>
#include <stddef.h>   /* NULL — required for ftx_decode_candidate_ap (GCC/Clang strict C11) */
#include <string.h>   /* memcpy, memset — required for osd_decode (shim 20260025)           */

// #define LOG_LEVEL LOG_DEBUG
// #include "debug.h"

/* OSD confidence gate threshold (shim 20260026, D-009).
 * Normalised correlation score below which an OSD-found codeword is rejected as
 * a CRC-14 false alarm.  Range [-1, +1]; initial value 0.10 (calibrated from
 * S5 FP analysis 2026-06-20).  Increase if S5 FP rate remains elevated; decrease
 * if S7 co-channel decode rate regresses. */
#define OSD_CORR_THRESHOLD 0.10f

// Lookup table for y = 10*log10(1 + 10^(x/10)), where
//   y - increase in signal level dB when adding a weaker independent signal
//   x - specific relative strength of the weaker signal in dB
// Table index corresponds to x in dB (index 0: 0 dB, index 1: -1 dB etc)
static const float db_power_sum[40] = {
    3.01029995663981f, 2.53901891043867f, 2.1244260279434f, 1.76434862436485f, 1.45540463109294f,
    1.19331048066095f, 0.973227937086954f, 0.790097496525665f, 0.638920341433796f, 0.514969420252302f,
    0.413926851582251f, 0.331956199884278f, 0.265723755961025f, 0.212384019142551f, 0.16954289279533f,
    0.135209221080382f, 0.10774225511957f, 0.085799992300358f, 0.06829128312453f, 0.054333142200458f,
    0.043213737826426f, 0.034360947517284f, 0.027316043349389f, 0.021711921641451f, 0.017255250287928f,
    0.013711928326833f, 0.010895305999614f, 0.008656680827934f, 0.006877654943187f, 0.005464004928574f,
    0.004340774793186f, 0.003448354310253f, 0.002739348814965f, 0.002176083232619f, 0.001728613409904f,
    0.001373142636584f, 0.001090761428665f, 0.000866444976964f, 0.000688255828734f, 0.000546709946839f
};

/// Compute log likelihood log(p(1) / p(0)) of 174 message bits for later use in soft-decision LDPC decoding
/// @param[in] wf Waterfall data collected during message slot
/// @param[in] cand Candidate to extract the message from
/// @param[in] code_map Symbol encoding map
/// @param[out] log174 Output of decoded log likelihoods for each of the 174 message bits
static void ft4_extract_likelihood(const ftx_waterfall_t* wf, const ftx_candidate_t* cand, float* log174);
static void ft8_extract_likelihood(const ftx_waterfall_t* wf, const ftx_candidate_t* cand, float* log174);

/* Non-static diagnostic probe — called from ft8_shim.c (Task B, shim 20260020).
 * Returns post-normalisation mean|LLR| and sets *out_prenorm_variance.
 * Returns NaN if the pre-normalisation variance is zero (degenerate candidate). */
float ftx_compute_candidate_llr_stats(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand,
    float*                 out_prenorm_variance);

/* AP-constrained decode — called from ft8_shim.c for pass 0 (Task A, shim 20260020).
 * Behaves identically to ftx_decode_candidate but applies the ap_overrides array
 * to log174 after extraction and before normalisation.  Entries with value 0.0f are
 * left unchanged; non-zero entries replace the waterfall-derived LLR with that value.
 * Pass ap_overrides=NULL (or all-zero array) to behave identically to
 * ftx_decode_candidate (AP disabled). */
bool ftx_decode_candidate_ap(
    const ftx_waterfall_t*  wf,
    const ftx_candidate_t*  cand,
    int                     max_iterations,
    const float*            ap_overrides,   /* FTX_LDPC_N floats; 0.0f = no override */
    ftx_message_t*          message,
    ftx_decode_status_t*    status);

/// Packs a string of bits each represented as a zero/non-zero byte in bit_array[],
/// as a string of packed bits starting from the MSB of the first byte of packed[]
/// @param[in] plain Array of bits (0 and nonzero values) with num_bits entires
/// @param[in] num_bits Number of bits (entries) passed in bit_array
/// @param[out] packed Byte-packed bits representing the data in bit_array
static void pack_bits(const uint8_t bit_array[], int num_bits, uint8_t packed[]);

static float max2(float a, float b);
static float max4(float a, float b, float c, float d);
static void heapify_down(ftx_candidate_t heap[], int heap_size);
static void heapify_up(ftx_candidate_t heap[], int heap_size);

static void ftx_normalize_logl(float* log174);
static void ft4_extract_symbol(const WF_ELEM_T* wf, float* logl);
static void ft8_extract_symbol(const WF_ELEM_T* wf, float* logl);
static void ft8_decode_multi_symbols(const WF_ELEM_T* wf, int num_bins, int n_syms, int bit_idx, float* log174);

static const WF_ELEM_T* get_cand_mag(const ftx_waterfall_t* wf, const ftx_candidate_t* candidate)
{
    int offset = candidate->time_offset;
    offset = (offset * wf->time_osr) + candidate->time_sub;
    offset = (offset * wf->freq_osr) + candidate->freq_sub;
    offset = (offset * wf->num_bins) + candidate->freq_offset;
    return wf->mag + offset;
}

static int ft8_sync_score(const ftx_waterfall_t* wf, const ftx_candidate_t* candidate)
{
    int score = 0;
    int num_average = 0;

    // Get the pointer to symbol 0 of the candidate
    const WF_ELEM_T* mag_cand = get_cand_mag(wf, candidate);

    // Compute average score over sync symbols (m+k = 0-7, 36-43, 72-79)
    for (int m = 0; m < FT8_NUM_SYNC; ++m)
    {
        for (int k = 0; k < FT8_LENGTH_SYNC; ++k)
        {
            int block = (FT8_SYNC_OFFSET * m) + k;          // relative to the message
            int block_abs = candidate->time_offset + block; // relative to the captured signal
            // Check for time boundaries
            if (block_abs < 0)
                continue;
            if (block_abs >= wf->num_blocks)
                break;

            // Get the pointer to symbol 'block' of the candidate
            const WF_ELEM_T* p8 = mag_cand + (block * wf->block_stride);

            // Weighted difference between the expected and all other symbols
            // Does not work as well as the alternative score below
            // score += 8 * p8[kFT8_Costas_pattern[k]] -
            //          p8[0] - p8[1] - p8[2] - p8[3] -
            //          p8[4] - p8[5] - p8[6] - p8[7];
            // ++num_average;

            // Check only the neighbors of the expected symbol frequency- and time-wise
            int sm = kFT8_Costas_pattern[k]; // Index of the expected bin
            if (sm > 0)
            {
                // look at one frequency bin lower
                score += WF_ELEM_MAG_INT(p8[sm]) - WF_ELEM_MAG_INT(p8[sm - 1]);
                ++num_average;
            }
            if (sm < 7)
            {
                // look at one frequency bin higher
                score += WF_ELEM_MAG_INT(p8[sm]) - WF_ELEM_MAG_INT(p8[sm + 1]);
                ++num_average;
            }
            if ((k > 0) && (block_abs > 0))
            {
                // look one symbol back in time
                score += WF_ELEM_MAG_INT(p8[sm]) - WF_ELEM_MAG_INT(p8[sm - wf->block_stride]);
                ++num_average;
            }
            if (((k + 1) < FT8_LENGTH_SYNC) && ((block_abs + 1) < wf->num_blocks))
            {
                // look one symbol forward in time
                score += WF_ELEM_MAG_INT(p8[sm]) - WF_ELEM_MAG_INT(p8[sm + wf->block_stride]);
                ++num_average;
            }
        }
    }

    if (num_average > 0)
        score /= num_average;

    return score;
}

static int ft4_sync_score(const ftx_waterfall_t* wf, const ftx_candidate_t* candidate)
{
    int score = 0;
    int num_average = 0;

    // Get the pointer to symbol 0 of the candidate
    const WF_ELEM_T* mag_cand = get_cand_mag(wf, candidate);

    // Compute average score over sync symbols (block = 1-4, 34-37, 67-70, 100-103)
    for (int m = 0; m < FT4_NUM_SYNC; ++m)
    {
        for (int k = 0; k < FT4_LENGTH_SYNC; ++k)
        {
            int block = 1 + (FT4_SYNC_OFFSET * m) + k;
            int block_abs = candidate->time_offset + block;
            // Check for time boundaries
            if (block_abs < 0)
                continue;
            if (block_abs >= wf->num_blocks)
                break;

            // Get the pointer to symbol 'block' of the candidate
            const WF_ELEM_T* p4 = mag_cand + (block * wf->block_stride);

            int sm = kFT4_Costas_pattern[m][k]; // Index of the expected bin

            // score += (4 * p4[sm]) - p4[0] - p4[1] - p4[2] - p4[3];
            // num_average += 4;

            // Check only the neighbors of the expected symbol frequency- and time-wise
            if (sm > 0)
            {
                // look at one frequency bin lower
                score += WF_ELEM_MAG_INT(p4[sm]) - WF_ELEM_MAG_INT(p4[sm - 1]);
                ++num_average;
            }
            if (sm < 3)
            {
                // look at one frequency bin higher
                score += WF_ELEM_MAG_INT(p4[sm]) - WF_ELEM_MAG_INT(p4[sm + 1]);
                ++num_average;
            }
            if ((k > 0) && (block_abs > 0))
            {
                // look one symbol back in time
                score += WF_ELEM_MAG_INT(p4[sm]) - WF_ELEM_MAG_INT(p4[sm - wf->block_stride]);
                ++num_average;
            }
            if (((k + 1) < FT4_LENGTH_SYNC) && ((block_abs + 1) < wf->num_blocks))
            {
                // look one symbol forward in time
                score += WF_ELEM_MAG_INT(p4[sm]) - WF_ELEM_MAG_INT(p4[sm + wf->block_stride]);
                ++num_average;
            }
        }
    }

    if (num_average > 0)
        score /= num_average;

    return score;
}

int ftx_find_candidates(const ftx_waterfall_t* wf, int num_candidates, ftx_candidate_t heap[], int min_score)
{
    int (*sync_fun)(const ftx_waterfall_t*, const ftx_candidate_t*) = (wf->protocol == FTX_PROTOCOL_FT4) ? ft4_sync_score : ft8_sync_score;
    int num_tones = (wf->protocol == FTX_PROTOCOL_FT4) ? 4 : 8;

    int heap_size = 0;
    ftx_candidate_t candidate;

    // Here we allow time offsets that exceed signal boundaries, as long as we still have all data bits.
    // I.e. we can afford to skip the first 7 or the last 7 Costas symbols, as long as we track how many
    // sync symbols we included in the score, so the score is averaged.
    for (candidate.time_sub = 0; candidate.time_sub < wf->time_osr; ++candidate.time_sub)
    {
        for (candidate.freq_sub = 0; candidate.freq_sub < wf->freq_osr; ++candidate.freq_sub)
        {
            for (candidate.time_offset = -10; candidate.time_offset < 20; ++candidate.time_offset)
            {
                for (candidate.freq_offset = 0; (candidate.freq_offset + num_tones - 1) < wf->num_bins; ++candidate.freq_offset)
                {
                    candidate.score = sync_fun(wf, &candidate);

                    if (candidate.score < min_score)
                        continue;

                    // If the heap is full AND the current candidate is better than
                    // the worst in the heap, we remove the worst and make space
                    if ((heap_size == num_candidates) && (candidate.score > heap[0].score))
                    {
                        --heap_size;
                        heap[0] = heap[heap_size];
                        heapify_down(heap, heap_size);
                    }

                    // If there's free space in the heap, we add the current candidate
                    if (heap_size < num_candidates)
                    {
                        heap[heap_size] = candidate;
                        ++heap_size;
                        heapify_up(heap, heap_size);
                    }
                }
            }
        }
    }

    // Sort the candidates by sync strength - here we benefit from the heap structure
    int len_unsorted = heap_size;
    while (len_unsorted > 1)
    {
        // Take the top (index 0) element which is guaranteed to have the smallest score,
        // exchange it with the last element in the heap, and decrease the heap size.
        // Then restore the heap property in the new, smaller heap.
        // At the end the elements will be sorted in descending order.
        ftx_candidate_t tmp = heap[len_unsorted - 1];
        heap[len_unsorted - 1] = heap[0];
        heap[0] = tmp;
        len_unsorted--;
        heapify_down(heap, len_unsorted);
    }

    return heap_size;
}

static void ft4_extract_likelihood(const ftx_waterfall_t* wf, const ftx_candidate_t* cand, float* log174)
{
    const WF_ELEM_T* mag = get_cand_mag(wf, cand); // Pointer to 4 magnitude bins of the first symbol

    // Go over FSK tones and skip Costas sync symbols
    for (int k = 0; k < FT4_ND; ++k)
    {
        // Skip either 5, 9 or 13 sync symbols
        // TODO: replace magic numbers with constants
        int sym_idx = k + ((k < 29) ? 5 : ((k < 58) ? 9 : 13));
        int bit_idx = 2 * k;

        // Check for time boundaries
        int block = cand->time_offset + sym_idx;
        if ((block < 0) || (block >= wf->num_blocks))
        {
            log174[bit_idx + 0] = 0;
            log174[bit_idx + 1] = 0;
        }
        else
        {
            ft4_extract_symbol(mag + (sym_idx * wf->block_stride), log174 + bit_idx);
        }
    }
}

static void ft8_extract_likelihood(const ftx_waterfall_t* wf, const ftx_candidate_t* cand, float* log174)
{
    const WF_ELEM_T* mag = get_cand_mag(wf, cand); // Pointer to 8 magnitude bins of the first symbol

    // Go over FSK tones and skip Costas sync symbols
    for (int k = 0; k < FT8_ND; ++k)
    {
        // Skip either 7 or 14 sync symbols
        // TODO: replace magic numbers with constants
        int sym_idx = k + ((k < 29) ? 7 : 14);
        int bit_idx = 3 * k;

        // Check for time boundaries
        int block = cand->time_offset + sym_idx;
        if ((block < 0) || (block >= wf->num_blocks))
        {
            log174[bit_idx + 0] = 0;
            log174[bit_idx + 1] = 0;
            log174[bit_idx + 2] = 0;
        }
        else
        {
            ft8_extract_symbol(mag + (sym_idx * wf->block_stride), log174 + bit_idx);
        }
    }
}

static void ftx_normalize_logl(float* log174)
{
    // Compute the variance of log174
    float sum = 0;
    float sum2 = 0;
    for (int i = 0; i < FTX_LDPC_N; ++i)
    {
        sum += log174[i];
        sum2 += log174[i] * log174[i];
    }
    float inv_n = 1.0f / FTX_LDPC_N;
    float variance = (sum2 - (sum * sum * inv_n)) * inv_n;

    // Normalize log174 distribution and scale it with experimentally found coefficient
    float norm_factor = sqrtf(24.0f / variance);
    for (int i = 0; i < FTX_LDPC_N; ++i)
    {
        log174[i] *= norm_factor;
    }
}

/* ── Ordered Statistics Decoding (OSD) — shim 20260025 ─────────────────────
 *
 * Called when bp_decode() fails to find a zero-parity codeword under wrong-sign
 * LLR conditions (D-001 root cause: equal-SNR co-channel interference).
 *
 * WSJT-X uses OSD (osd174_91.f90) with maxosd=2 (at ndepth=3), saving LLR
 * snapshots from BP iterations 0–2.  We use the pre-BP normalised LLRs, which
 * corresponds to WSJT-X's zsave(:,1) (iteration-0 snapshot).
 *
 * Algorithm:
 *   1. Sort the 174 bits by reliability (descending |LLR|).
 *   2. Form the permuted parity-check matrix H_perm.
 *   3. GF(2) Gaussian elimination → systematic form; identify free columns.
 *   4. Enumerate bit-flip patterns in the least-reliable free positions.
 *   5. For each trial, compute pivot bits from parity equations, un-permute,
 *      and perform a CRC check.  Return the first CRC-valid codeword found.
 *
 * With ndeep=2 and search_k=32: 1 + 32 + 496 = 529 CRC trials per candidate.
 * Gaussian elimination (one-time per candidate): O(M^2 * N) ≈ 1.2M GF(2) ops.
 * Stack frame for osd_decode: ~18 KB (H[83][174]=14 KB dominant).
 * ──────────────────────────────────────────────────────────────────────────── */

/*
 * osd_try_codeword — derive a codeword from given free-bit values and CRC-check it.
 *
 * Computes pivot bits using parity equations from the post-elimination H matrix,
 * un-permutes the resulting codeword to the original bit domain, and runs the
 * FT8 CRC-14 check.  Writes the codeword to plain[] and returns 1 on CRC hit;
 * returns 0 otherwise.
 *
 * Parameters:
 *   free_vals   — n_free trial free-bit values (0/1).
 *   n_free      — number of free (non-pivot) columns.
 *   free_cols   — sorted indices of the free columns in the permuted domain.
 *   num_pivots  — number of rows that found a pivot (= rank of H_perm, normally 83).
 *   pivot_col   — pivot_col[m] = the permuted column index that row m pivoted on.
 *   H           — post-elimination parity-check matrix [FTX_LDPC_M][FTX_LDPC_N].
 *   perm        — perm[i] = original bit index of the i-th sorted (most-reliable) bit.
 *   plain       — output: FTX_LDPC_N bits (0/1) when CRC passes.
 *
 * Returns 1 if CRC passes, 0 otherwise.
 */
static int osd_try_codeword(
    const uint8_t  free_vals[],
    int            n_free,
    const int      free_cols[],
    int            num_pivots,
    const int      pivot_col[],
    uint8_t        H[][FTX_LDPC_N],   /* [FTX_LDPC_M][FTX_LDPC_N], post-elimination */
    const int      perm[],
    uint8_t        plain[])
{
    uint8_t cw_perm[FTX_LDPC_N];

    /* Assign free bits */
    for (int i = 0; i < n_free; ++i)
        cw_perm[free_cols[i]] = free_vals[i];

    /* Compute pivot bits: cw_perm[pivot_col[m]] = H[m] · free_vals  (GF2 dot) */
    for (int m = 0; m < num_pivots; ++m) {
        uint8_t s = 0;
        for (int i = 0; i < n_free; ++i)
            s ^= (uint8_t)(H[m][free_cols[i]] & free_vals[i]);
        cw_perm[pivot_col[m]] = s;
    }

    /* Un-permute: cw_orig[perm[i]] = cw_perm[i] */
    uint8_t cw_orig[FTX_LDPC_N];
    for (int i = 0; i < FTX_LDPC_N; ++i)
        cw_orig[perm[i]] = cw_perm[i];

    /* CRC-14 check on the first FTX_LDPC_K (91) information bits */
    uint8_t a91[FTX_LDPC_K_BYTES];
    pack_bits(cw_orig, FTX_LDPC_K, a91);
    uint16_t crc_ext  = ftx_extract_crc(a91);
    a91[9]  &= 0xF8;
    a91[10] &= 0x00;
    uint16_t crc_calc = ftx_compute_crc(a91, 96 - 14);

    if (crc_ext == crc_calc) {
        memcpy(plain, cw_orig, FTX_LDPC_N);
        return 1;
    }
    return 0;
}

/*
 * osd_decode — Ordered Statistics Decoding fallback for LDPC(174,91).
 *
 * llr[]   — 174 channel LLRs (normalised, pre-BP); positive = bit 0, negative = bit 1.
 * ndeep   — maximum flip order: 1 = single flips, 2 = double flips (WSJT-X default).
 * plain[] — output: 174 bits (0/1) if a CRC-valid codeword is found.
 *
 * Returns 1 if a CRC-valid codeword was found and written to plain[], 0 otherwise.
 */
static int osd_decode(const float llr[], int ndeep, uint8_t plain[])
{
    /* Step 1: sort bits by reliability (descending |LLR|) using insertion sort (N=174). */
    int perm[FTX_LDPC_N];
    for (int i = 0; i < FTX_LDPC_N; ++i) perm[i] = i;
    for (int i = 1; i < FTX_LDPC_N; ++i) {
        int   key     = perm[i];
        float key_rel = fabsf(llr[key]);
        int   j       = i - 1;
        while (j >= 0 && fabsf(llr[perm[j]]) < key_rel) {
            perm[j + 1] = perm[j];
            j--;
        }
        perm[j + 1] = key;
    }

    /* inv_perm[perm[i]] = i (inverse permutation) */
    int inv_perm[FTX_LDPC_N];
    for (int i = 0; i < FTX_LDPC_N; ++i) inv_perm[perm[i]] = i;

    /* Step 2: hard decisions on sorted positions. */
    uint8_t hard[FTX_LDPC_N];
    for (int i = 0; i < FTX_LDPC_N; ++i)
        hard[i] = (llr[perm[i]] < 0.0f) ? 1 : 0;

    /* Step 3: build permuted parity-check matrix.
     * H[m][j] = 1 iff check m involves permuted column j = inv_perm[orig_n].
     * Stack: 83 * 174 = 14,442 bytes — acceptable per handoff spec. */
    uint8_t H[FTX_LDPC_M][FTX_LDPC_N];
    memset(H, 0, sizeof(H));
    for (int m = 0; m < FTX_LDPC_M; ++m) {
        for (int j = 0; j < (int)kFTX_LDPC_Num_rows[m]; ++j) {
            int orig_n = (int)kFTX_LDPC_Nm[m][j] - 1;   /* 1-indexed → 0-indexed */
            H[m][inv_perm[orig_n]] = 1;
        }
    }

    /* Step 4: GF(2) Gaussian elimination — put H into reduced row echelon form. */
    int     pivot_col[FTX_LDPC_M];
    uint8_t pivoted[FTX_LDPC_N];
    memset(pivoted, 0, sizeof(pivoted));
    int num_pivots = 0;

    for (int col = 0; col < FTX_LDPC_N && num_pivots < FTX_LDPC_M; ++col) {
        /* Find first row ≥ num_pivots with a 1 in this column. */
        int pr = -1;
        for (int r = num_pivots; r < FTX_LDPC_M; ++r) {
            if (H[r][col]) { pr = r; break; }
        }
        if (pr < 0) continue;   /* no pivot in this column */

        /* Swap rows pr ↔ num_pivots. */
        if (pr != num_pivots) {
            uint8_t tmp[FTX_LDPC_N];
            memcpy(tmp,             H[num_pivots], FTX_LDPC_N);
            memcpy(H[num_pivots],   H[pr],         FTX_LDPC_N);
            memcpy(H[pr],           tmp,            FTX_LDPC_N);
        }

        /* Eliminate this column from every other row. */
        for (int r = 0; r < FTX_LDPC_M; ++r) {
            if (r != num_pivots && H[r][col]) {
                for (int c = 0; c < FTX_LDPC_N; ++c)
                    H[r][c] ^= H[num_pivots][c];
            }
        }

        pivot_col[num_pivots] = col;
        pivoted[col]          = 1;
        num_pivots++;
    }

    /* Step 5: identify free (non-pivot) columns — these are the information bits. */
    int free_cols[FTX_LDPC_N];
    int n_free = 0;
    for (int col = 0; col < FTX_LDPC_N; ++col) {
        if (!pivoted[col]) free_cols[n_free++] = col;
    }
    /* n_free == FTX_LDPC_N - num_pivots; for a full-rank code == 91. */

    /* Step 6: base free values from hard decisions. */
    uint8_t base_free[FTX_LDPC_N];   /* only first n_free entries used */
    for (int i = 0; i < n_free; ++i)
        base_free[i] = hard[free_cols[i]];

    /* Trial buffer for flip enumeration. */
    uint8_t trial_free[FTX_LDPC_N];

    /* 0-flip base trial. */
    if (osd_try_codeword(base_free, n_free, free_cols, num_pivots, pivot_col, H, perm, plain))
        return 1;

    /* Search the search_k least-reliable free positions (highest free_col index,
     * since perm[] is sorted most-reliable-first and free_cols[] is ascending). */
    int search_k = (n_free < 32) ? n_free : 32;

    if (ndeep >= 1) {
        /* Single flips */
        for (int a = n_free - 1; a >= n_free - search_k; --a) {
            memcpy(trial_free, base_free, (size_t)n_free);
            trial_free[a] ^= 1;
            if (osd_try_codeword(trial_free, n_free, free_cols, num_pivots, pivot_col, H, perm, plain))
                return 1;
        }
    }

    if (ndeep >= 2) {
        /* Double flips */
        for (int a = n_free - 1; a >= n_free - search_k; --a) {
            for (int b = a - 1; b >= n_free - search_k; --b) {
                memcpy(trial_free, base_free, (size_t)n_free);
                trial_free[a] ^= 1;
                trial_free[b] ^= 1;
                if (osd_try_codeword(trial_free, n_free, free_cols, num_pivots, pivot_col, H, perm, plain))
                    return 1;
            }
        }
    }

    return 0;
}

bool ftx_decode_candidate(const ftx_waterfall_t* wf, const ftx_candidate_t* cand, int max_iterations, ftx_message_t* message, ftx_decode_status_t* status)
{
    float log174[FTX_LDPC_N]; // message bits encoded as likelihood
    if (wf->protocol == FTX_PROTOCOL_FT4)
    {
        ft4_extract_likelihood(wf, cand, log174);
    }
    else
    {
        ft8_extract_likelihood(wf, cand, log174);
    }

    ftx_normalize_logl(log174);

    /* Save normalised LLRs before bp_decode potentially modifies them in place.
     * osd_decode uses these pre-BP soft decisions if BP fails to converge. */
    float llr_for_osd[FTX_LDPC_N];
    memcpy(llr_for_osd, log174, sizeof(log174));

    uint8_t plain174[FTX_LDPC_N]; // message bits (0/1)
    bp_decode(log174, max_iterations, plain174, &status->ldpc_errors);
    // ldpc_decode(log174, max_iterations, plain174, &status->ldpc_errors);

    if (status->ldpc_errors > 0)
    {
        /* BP failed to converge; try OSD fallback (shim 20260025).
         * ndeep=2 matches WSJT-X's default maxosd=2 at ndepth=3. */
        if (!osd_decode(llr_for_osd, 2, plain174))
            return false;

        /* OSD confidence gate (shim 20260026, D-009):
         * Reject candidates where the decoded codeword has low correlation with the
         * input LLRs.  For a genuine signal the decoded bits are predominantly aligned
         * with the LLR signs (score >> 0).  For a CRC-14 coincidence from pure noise
         * the bits are uncorrelated with the noise LLRs (score ~= 0).
         *
         * corr = sum hard_pm1[i] * llr[i]   (positive = decoded bit agrees with LLR sign)
         * norm = sum |llr[i]|
         * score = corr / norm in [-1, +1]
         * Threshold OSD_CORR_THRESHOLD: calibrated at 0.10; tune if S7 false-negatives appear.
         */
        {
            float osd_corr = 0.0f;
            float osd_norm = 0.0f;
            for (int i = 0; i < FTX_LDPC_N; ++i) {
                float hard_pm1 = (plain174[i] == 0) ? 1.0f : -1.0f;
                osd_corr += hard_pm1 * llr_for_osd[i];
                osd_norm += fabsf(llr_for_osd[i]);
            }
            if (osd_norm > 0.0f && (osd_corr / osd_norm) < OSD_CORR_THRESHOLD)
                return false;
        }
        status->ldpc_errors = 0;
    }

    // Extract payload + CRC (first FTX_LDPC_K bits) packed into a byte array
    uint8_t a91[FTX_LDPC_K_BYTES];
    pack_bits(plain174, FTX_LDPC_K, a91);

    // Extract CRC and check it
    status->crc_extracted = ftx_extract_crc(a91);
    // [1]: 'The CRC is calculated on the source-encoded message, zero-extended from 77 to 82 bits.'
    a91[9] &= 0xF8;
    a91[10] &= 0x00;
    status->crc_calculated = ftx_compute_crc(a91, 96 - 14);

    if (status->crc_extracted != status->crc_calculated)
    {
        return false;
    }

    // Reuse CRC value as a hash for the message (TODO: 14 bits only, should perhaps use full 16 or 32 bits?)
    message->hash = status->crc_calculated;

    if (wf->protocol == FTX_PROTOCOL_FT4)
    {
        // '[..] for FT4 only, in order to avoid transmitting a long string of zeros when sending CQ messages,
        // the assembled 77-bit message is bitwise exclusive-ORâ€™ed with [a] pseudorandom sequence before computing the CRC and FEC parity bits'
        for (int i = 0; i < 10; ++i)
        {
            message->payload[i] = a91[i] ^ kFT4_XOR_sequence[i];
        }
    }
    else
    {
        for (int i = 0; i < 10; ++i)
        {
            message->payload[i] = a91[i];
        }
    }

    // LOG(LOG_DEBUG, "Decoded message (CRC %04x), trying to unpack...\n", status->crc_extracted);
    return true;
}

/*
 * ftx_compute_candidate_llr_stats — diagnostic probe for D-001 (shim 20260020).
 *
 * Redesign of ftx_compute_candidate_llr_mean_abs (shim 20260019):
 *   - Computes pre-normalisation variance of the raw log174 array.
 *   - A small pre-normalisation variance indicates ambiguous / degraded LLRs
 *     regardless of the post-normalisation mean (which is a near-constant ≈3.91
 *     due to the normalisation).
 *   - Returns NaN if the pre-normalisation variance is zero (degenerate candidate
 *     — all log174 entries equal; ftx_normalize_logl would divide-by-zero).
 *   - Returns post-normalisation mean|LLR| via return value for continuity with
 *     the shim 20260019 metric.
 *
 * Does NOT call bp_decode.  Read-only with respect to the waterfall.
 * Safe to call for any candidate, including those that subsequently
 * fail ftx_decode_candidate.
 */
float ftx_compute_candidate_llr_stats(
    const ftx_waterfall_t* wf,
    const ftx_candidate_t* cand,
    float*                 out_prenorm_variance)
{
    float log174[FTX_LDPC_N];

    if (wf->protocol == FTX_PROTOCOL_FT4)
        ft4_extract_likelihood(wf, cand, log174);
    else
        ft8_extract_likelihood(wf, cand, log174);

    /* Compute pre-normalisation variance */
    float sum = 0.0f, sum2 = 0.0f;
    for (int i = 0; i < FTX_LDPC_N; ++i)
    {
        sum  += log174[i];
        sum2 += log174[i] * log174[i];
    }
    float mean     = sum / (float)FTX_LDPC_N;
    float variance = sum2 / (float)FTX_LDPC_N - mean * mean;
    *out_prenorm_variance = variance;

    /* Degenerate candidate: variance == 0 → ftx_normalize_logl would divide-by-zero.
     * Return NaN so the caller can detect and skip this candidate.
     * Use nanf("") (C99/C11) rather than 0.0f/0.0f — MSVC rejects the latter as
     * a compile-time constant divide-by-zero under /O2 (error C2124). */
    if (variance == 0.0f)
        return nanf("");

    /* Normalise and compute post-normalisation mean|LLR| */
    ftx_normalize_logl(log174);

    float abs_sum = 0.0f;
    for (int i = 0; i < FTX_LDPC_N; ++i)
        abs_sum += fabsf(log174[i]);

    return abs_sum / (float)FTX_LDPC_N;
}

/*
 * ftx_decode_candidate_ap — AP-constrained decode (Task A, shim 20260020).
 *
 * Implements directed a priori (AP) decode: after extracting soft-decision
 * likelihoods from the waterfall, known bit values (mycall / hiscall) are
 * injected as hard constraints by overriding the corresponding log174 entries
 * with ±LLR_HARD before normalisation.  This anchors LDPC belief-propagation
 * on the known bits, improving convergence when the remaining LLRs are near-zero
 * (equal-SNR co-channel interference — D-001 root cause).
 *
 * Parameters:
 *   ap_overrides  — FTX_LDPC_N floats.  Non-zero entry at index i overrides
 *                   log174[i] with that value (+LLR_HARD for bit=1, -LLR_HARD
 *                   for bit=0) before normalisation.  Entries of 0.0f are left
 *                   unchanged (no override at that bit position).
 *                   Pass NULL to behave identically to ftx_decode_candidate.
 *
 * Behaviour is otherwise identical to ftx_decode_candidate.
 */
bool ftx_decode_candidate_ap(
    const ftx_waterfall_t*  wf,
    const ftx_candidate_t*  cand,
    int                     max_iterations,
    const float*            ap_overrides,
    ftx_message_t*          message,
    ftx_decode_status_t*    status)
{
    float log174[FTX_LDPC_N];

    if (wf->protocol == FTX_PROTOCOL_FT4)
        ft4_extract_likelihood(wf, cand, log174);
    else
        ft8_extract_likelihood(wf, cand, log174);

    /* Apply AP constraints (hard-coded known bits) before normalisation */
    if (ap_overrides != NULL)
    {
        for (int i = 0; i < FTX_LDPC_N; ++i)
        {
            if (ap_overrides[i] != 0.0f)
                log174[i] = ap_overrides[i];
        }
    }

    ftx_normalize_logl(log174);

    /* Save normalised LLRs before bp_decode for OSD fallback (shim 20260025). */
    float llr_for_osd[FTX_LDPC_N];
    memcpy(llr_for_osd, log174, sizeof(log174));

    uint8_t plain174[FTX_LDPC_N];
    bp_decode(log174, max_iterations, plain174, &status->ldpc_errors);

    if (status->ldpc_errors > 0)
    {
        /* BP failed; try OSD fallback with pre-BP normalised LLRs. */
        if (!osd_decode(llr_for_osd, 2, plain174))
            return false;

        /* OSD confidence gate (shim 20260026, D-009) — same as ftx_decode_candidate. */
        {
            float osd_corr = 0.0f;
            float osd_norm = 0.0f;
            for (int i = 0; i < FTX_LDPC_N; ++i) {
                float hard_pm1 = (plain174[i] == 0) ? 1.0f : -1.0f;
                osd_corr += hard_pm1 * llr_for_osd[i];
                osd_norm += fabsf(llr_for_osd[i]);
            }
            if (osd_norm > 0.0f && (osd_corr / osd_norm) < OSD_CORR_THRESHOLD)
                return false;
        }
        status->ldpc_errors = 0;
    }

    uint8_t a91[FTX_LDPC_K_BYTES];
    pack_bits(plain174, FTX_LDPC_K, a91);

    status->crc_extracted = ftx_extract_crc(a91);
    a91[9]  &= 0xF8;
    a91[10] &= 0x00;
    status->crc_calculated = ftx_compute_crc(a91, 96 - 14);

    if (status->crc_extracted != status->crc_calculated)
        return false;

    message->hash = status->crc_calculated;

    if (wf->protocol == FTX_PROTOCOL_FT4)
    {
        for (int i = 0; i < 10; ++i)
            message->payload[i] = a91[i] ^ kFT4_XOR_sequence[i];
    }
    else
    {
        for (int i = 0; i < 10; ++i)
            message->payload[i] = a91[i];
    }

    return true;
}

static float max2(float a, float b)
{
    return (a >= b) ? a : b;
}

static float max4(float a, float b, float c, float d)
{
    return max2(max2(a, b), max2(c, d));
}

static void heapify_down(ftx_candidate_t heap[], int heap_size)
{
    // heapify from the root down
    int current = 0; // root node
    while (true)
    {
        int left = 2 * current + 1;
        int right = left + 1;

        // Find the smallest value of (parent, left child, right child)
        int smallest = current;
        if ((left < heap_size) && (heap[left].score < heap[smallest].score))
        {
            smallest = left;
        }
        if ((right < heap_size) && (heap[right].score < heap[smallest].score))
        {
            smallest = right;
        }

        if (smallest == current)
        {
            break;
        }

        // Exchange the current node with the smallest child and move down to it
        ftx_candidate_t tmp = heap[smallest];
        heap[smallest] = heap[current];
        heap[current] = tmp;
        current = smallest;
    }
}

static void heapify_up(ftx_candidate_t heap[], int heap_size)
{
    // heapify from the last node up
    int current = heap_size - 1;
    while (current > 0)
    {
        int parent = (current - 1) / 2;
        if (!(heap[current].score < heap[parent].score))
        {
            break;
        }

        // Exchange the current node with its parent and move up
        ftx_candidate_t tmp = heap[parent];
        heap[parent] = heap[current];
        heap[current] = tmp;
        current = parent;
    }
}

// Compute unnormalized log likelihood log(p(1) / p(0)) of 2 message bits (1 FSK symbol)
static void ft4_extract_symbol(const WF_ELEM_T* wf, float* logl)
{
    // Cleaned up code for the simple case of n_syms==1
    float s2[4];

    for (int j = 0; j < 4; ++j)
    {
        s2[j] = WF_ELEM_MAG(wf[kFT4_Gray_map[j]]);
    }

    logl[0] = max2(s2[2], s2[3]) - max2(s2[0], s2[1]);
    logl[1] = max2(s2[1], s2[3]) - max2(s2[0], s2[2]);
}

// Compute unnormalized log likelihood log(p(1) / p(0)) of 3 message bits (1 FSK symbol)
static void ft8_extract_symbol(const WF_ELEM_T* wf, float* logl)
{
    // Cleaned up code for the simple case of n_syms==1
#if 1
    float s2[8];

    for (int j = 0; j < 8; ++j)
    {
        s2[j] = WF_ELEM_MAG(wf[kFT8_Gray_map[j]]);
    }

    logl[0] = max4(s2[4], s2[5], s2[6], s2[7]) - max4(s2[0], s2[1], s2[2], s2[3]);
    logl[1] = max4(s2[2], s2[3], s2[6], s2[7]) - max4(s2[0], s2[1], s2[4], s2[5]);
    logl[2] = max4(s2[1], s2[3], s2[5], s2[7]) - max4(s2[0], s2[2], s2[4], s2[6]);
#else
    float a[7] = {
        // (float)wf[7] - (float)wf[0], // 0: p(111) / p(000)
        (float)wf[5] - (float)wf[2], // 0: p(100) / p(011)
        (float)wf[3] - (float)wf[0], // 1: p(010) / p(000)
        (float)wf[6] - (float)wf[3], // 2: p(101) / p(010)
        (float)wf[6] - (float)wf[2], // 3: p(101) / p(011)
        (float)wf[7] - (float)wf[4], // 4: p(111) / p(110)
        (float)wf[4] - (float)wf[1], // 5: p(110) / p(001)
        (float)wf[5] - (float)wf[1]  // 6: p(100) / p(001)
    };
    float k = 1.0f;

    // logl[0] = k * (a[0] + a[2] + a[3] + a[5] + a[6]) / 5;
    // logl[1] = k * (a[0] / 4 + (a[1] - a[3]) * 5 / 24 + (a[5] - a[2]) / 6 + (a[4] - a[6]) / 24);
    // logl[2] = k * (a[0] / 4 + (a[1] - a[3]) / 24 + (a[2] - a[5]) / 6 + (a[4] - a[6]) * 5 / 24);
    logl[0] = k * (a[1] / 6 + a[2] / 3 + a[3] / 6 + a[4] / 6 + a[5] / 3 + a[6] / 6);
    logl[1] = k * (-a[0] / 4 + a[1] * 7 / 24 + (a[4] - a[3]) / 8 + a[5] / 3 + a[6] / 24);
    logl[2] = k * (-a[0] / 4 + (a[1] - a[6]) / 8 + a[2] / 3 + a[3] / 24 + a[4] * 7 / 24 - a[5] * 5 / 18);
#endif
    // for (int i = 0; i < 8; ++i)
    //     printf("%d ", WF_ELEM_MAG_INT(wf[i]));
    // for (int i = 0; i < 3; ++i)
    //     printf("%.1f ", logl[i]);
    // printf("\n");
}

// Compute unnormalized log likelihood log(p(1) / p(0)) of bits corresponding to several FSK symbols at once
static void ft8_decode_multi_symbols(const WF_ELEM_T* wf, int num_bins, int n_syms, int bit_idx, float* log174)
{
    const int n_bits = 3 * n_syms;
    const int n_tones = (1 << n_bits);

    /* VLA -> fixed-size for MSVC: max n_tones=512 (n_syms<=3) */
    float s2[512];

    for (int j = 0; j < n_tones; ++j)
    {
        int j1 = j & 0x07;
        if (n_syms == 1)
        {
            s2[j] = WF_ELEM_MAG(wf[kFT8_Gray_map[j1]]);
            continue;
        }
        int j2 = (j >> 3) & 0x07;
        if (n_syms == 2)
        {
            s2[j] = WF_ELEM_MAG(wf[kFT8_Gray_map[j2]]);
            s2[j] += WF_ELEM_MAG(wf[kFT8_Gray_map[j1] + 4 * num_bins]);
            continue;
        }
        int j3 = (j >> 6) & 0x07;
        s2[j] = WF_ELEM_MAG(wf[kFT8_Gray_map[j3]]);
        s2[j] += WF_ELEM_MAG(wf[kFT8_Gray_map[j2] + 4 * num_bins]);
        s2[j] += WF_ELEM_MAG(wf[kFT8_Gray_map[j1] + 8 * num_bins]);
    }

    // Extract bit significance (and convert them to float)
    // 8 FSK tones = 3 bits
    for (int i = 0; i < n_bits; ++i)
    {
        if (bit_idx + i >= FTX_LDPC_N)
        {
            // Respect array size
            break;
        }

        uint16_t mask = (n_tones >> (i + 1));
        float max_zero = -1000, max_one = -1000;
        for (int n = 0; n < n_tones; ++n)
        {
            if (n & mask)
            {
                max_one = max2(max_one, s2[n]);
            }
            else
            {
                max_zero = max2(max_zero, s2[n]);
            }
        }

        log174[bit_idx + i] = max_one - max_zero;
    }
}

// Packs a string of bits each represented as a zero/non-zero byte in plain[],
// as a string of packed bits starting from the MSB of the first byte of packed[]
static void pack_bits(const uint8_t bit_array[], int num_bits, uint8_t packed[])
{
    int num_bytes = (num_bits + 7) / 8;
    for (int i = 0; i < num_bytes; ++i)
    {
        packed[i] = 0;
    }

    uint8_t mask = 0x80;
    int byte_idx = 0;
    for (int i = 0; i < num_bits; ++i)
    {
        if (bit_array[i])
        {
            packed[byte_idx] |= mask;
        }
        mask >>= 1;
        if (!mask)
        {
            mask = 0x80;
            ++byte_idx;
        }
    }
}
