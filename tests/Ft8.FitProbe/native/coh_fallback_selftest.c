/*
 * coh_fallback_selftest.c -- TEST-ONLY native self-test of COH-FALLBACK (A' step 3) Stage 1 (shim 20260066):
 * ft8_coherent_fallback_at / ft8_coherent_fallback_cycle and the candidate retention in ft8_decode_all.
 *
 * It #includes the product shim (ft8_shim.c) so the exports and the thread-local candidate list are the real ones, and links the
 * rest of libft8 (run_coh_fallback_selftest.py builds and runs it, with ASan + UBSan on a non-Windows host). Synthetic callsigns
 * only (NFR-021).
 *
 * What is checked:
 *   A. the estimator on clean synthetic signals recovers a known (df, dt) offset on the grid; window-edge detection;
 *   B. F1b rises monotonically with signal strength and sits low on noise only; the gate (T1) follows F1b;
 *   C. BP-only decode of a known C3 vector: a strong synthetic CQ decodes to the encoded payload with path 0 (never OSD, path 1),
 *      noise only does not; the flags (FORCE_C3, SKIP_F1B, ESTIMATE_ONLY) do what they say; bad arguments are refused;
 *   D. the retained candidate list of ft8_decode_all (R2): counts add up, decoded candidates are excluded, a payload already
 *      decoded in the call is skipped by the cycle export, flag-independence (the decode's output is unchanged by the export),
 *      an empty list gives 0 rows;
 *   E. the signal is not mis-anchored by the lattice (R3): the estimate for a decoded candidate sits within the window centre.
 */
#include "../../../src/OpenWSFZ.Ft8/Native/ft8_shim.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static int g_checks = 0, g_failures = 0;
#define CHECK(cond, ...) do { g_checks++; if (!(cond)) { g_failures++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static float g_pcm[180000];
static float g_pcm2[180000];

/* deterministic noise: xorshift64* + Box-Muller */
static uint64_t g_rng = 0x9E3779B97F4A7C15ull;
static double rnd01(void)
{
    g_rng ^= g_rng >> 12; g_rng ^= g_rng << 25; g_rng ^= g_rng >> 27;
    return ((double)((g_rng * 2685821657736338717ull) >> 11) + 0.5) / 9007199254740992.0;
}
static double gauss(void) { double u = rnd01(), v = rnd01(); return sqrt(-2.0 * log(u)) * cos(2.0 * M_PI * v); }

/* Adds one continuous-phase 8-FSK FT8 signal (unit-power sine, 12 kHz) with amplitude `amp`; symbol 0 starts at start_s. */
static void add_signal(float* pcm, const uint8_t* tones, double f_hz, double start_s, double amp)
{
    double phase = 0.0;
    long n0 = (long)lround(start_s * 12000.0);
    for (int s = 0; s < FT8_NN; s++) {
        double f = f_hz + 6.25 * tones[s];
        for (int i = 0; i < 1920; i++) {
            long idx = n0 + (long)s * 1920 + i;
            if (idx >= 0 && idx < 180000) pcm[idx] += (float)(amp * sin(phase));
            phase += 2.0 * M_PI * f / 12000.0;
        }
    }
}
static void add_noise(float* pcm, double sigma)
{
    for (int i = 0; i < 180000; i++) pcm[i] += (float)(sigma * gauss());
}
/* sigma of white noise that gives `snr_db` in a 2500 Hz reference bandwidth for a sine of amplitude `amp` (power amp^2/2). */
static double sigma_for_snr(double amp, double snr_db)
{
    double sig_p = amp * amp / 2.0;
    double noise_p_2500 = sig_p / pow(10.0, snr_db / 10.0);
    return sqrt(noise_p_2500 * (6000.0 / 2500.0));
}

static int tones_for(const char* text, uint8_t* tones, ftx_message_t* msg_out)
{
    callsign_table_t t; hash_table_init(&t);
    callsign_table_t* prev = tls_hash_table; tls_hash_table = &t;
    ftx_message_t m; memset(&m, 0, sizeof(m));
    ftx_message_rc_t rc = ftx_message_encode(&m, &s_hash_if, text);
    tls_hash_table = prev;
    if (rc != FTX_MESSAGE_RC_OK) return -1;
    ft8_encode(m.payload, tones);
    if (msg_out) *msg_out = m;
    return 0;
}

/* Candidate convention: symbol 0 of a signal starting at start_s has anchor time start_s + one symbol period. */
#define ANCHOR_OF(start_s) ((start_s) + 0.16)

static FT8CohFallbackResult run_at(const float* pcm, double f0, double t0, int flags, int* rc_out)
{
    FT8CohFallbackResult r; memset(&r, 0x7f, sizeof(r));
    int rc = ft8_coherent_fallback_at(pcm, 180000, f0, t0, flags, &r, NULL);
    if (rc_out) *rc_out = rc;
    return r;
}

/* ------------------------------------------------------------------------------------------------------------------ */
static void sizes(void)
{
    CHECK(sizeof(FT8CohFallbackResult) == 112, "FT8CohFallbackResult is %zu bytes", sizeof(FT8CohFallbackResult));
    CHECK(sizeof(FT8CohFallbackCycleStats) == 96, "FT8CohFallbackCycleStats is %zu bytes", sizeof(FT8CohFallbackCycleStats));
    CHECK(sizeof(FT8CohFallbackRow) == 144, "FT8CohFallbackRow is %zu bytes", sizeof(FT8CohFallbackRow));
    CHECK(sizeof(FT8Result) == 48, "FT8Result is unchanged at %zu bytes", sizeof(FT8Result));
    CHECK(ft8_lib_version_check() == FT8_SHIM_VERSION, "shim version");
    CHECK(fabs(CF_T1_DB - 17.552446) < 1e-12, "T1 constant");
}

static void estimator(void)
{
    uint8_t tones[FT8_NN]; ftx_message_t m;
    CHECK(tones_for("CQ Q1ABC FN20", tones, &m) == 0, "encode");
    const double f_true = 1500.0, start = 0.55;
    memset(g_pcm, 0, sizeof(g_pcm));
    add_signal(g_pcm, tones, f_true, start, 0.3);
    add_noise(g_pcm, sigma_for_snr(0.3, 5.0));

    /* anchors off by known amounts inside the window: the estimate is minus the offset, on the 0.1 Hz / 5 ms grid */
    const double dfs[] = { 0.0, 0.7, -1.3, 1.9, -2.0 };
    const double dts[] = { 0.0, 0.035, -0.06, 0.115, -0.12 };
    for (int i = 0; i < 5; i++) {
        int rc; FT8CohFallbackResult r = run_at(g_pcm, f_true + dfs[i], ANCHOR_OF(start) + dts[i], FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0, "rc %d", rc);
        CHECK(fabs(r.est_df_hz + dfs[i]) < 0.151, "df offset %+.2f: estimate %+.2f", dfs[i], r.est_df_hz);
        CHECK(fabs(r.est_dt_s + dts[i]) < 0.0101, "dt offset %+.3f: estimate %+.3f", dts[i], r.est_dt_s);
        CHECK(r.c3_ran == 0 && r.bp_rc == FT8_COH_BP_NOT_RUN && r.n_refs == 0 && isnan(r.f1b_db), "ESTIMATE_ONLY ran nothing else");
        CHECK(r.dt_step == (int)lround(r.est_dt_s / 0.005), "dt_step %d vs est_dt %.3f", r.dt_step, r.est_dt_s);
    }
    /* a signal exactly at the window boundary (2.0 Hz, 0.12 s off) puts the argmax on an edge; centred it does not */
    {
        int rc; FT8CohFallbackResult r = run_at(g_pcm, f_true + 2.0, ANCHOR_OF(start), FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0 && r.edge == 1 && fabs(r.est_df_hz + 2.0) < 1e-9, "df at the window edge: edge=%d est_df=%+.2f", r.edge, r.est_df_hz);
        r = run_at(g_pcm, f_true, ANCHOR_OF(start) - 0.12, FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0 && r.edge == 1 && r.dt_step == 24, "dt at the window edge: edge=%d dt_step=%d", r.edge, r.dt_step);
        r = run_at(g_pcm, f_true + 3.0, ANCHOR_OF(start) + 0.2, FT8_COH_FLAG_ESTIMATE_ONLY, &rc);   /* outside: no crash, no claim */
        CHECK(rc == 0, "outside the window: rc %d", rc);
        r = run_at(g_pcm, f_true, ANCHOR_OF(start), FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0 && r.edge == 0, "centred: edge=%d", r.edge);
    }
    /* a signal that starts before the buffer (zero-padded symbols) and one that runs past its end: no crash, a sane answer */
    {
        memset(g_pcm2, 0, sizeof(g_pcm2));
        add_signal(g_pcm2, tones, f_true, -0.20, 0.3);
        int rc; FT8CohFallbackResult r = run_at(g_pcm2, f_true, ANCHOR_OF(-0.20), FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0 && r.peak > 0.0, "early signal: rc=%d peak=%g", rc, r.peak);
        memset(g_pcm2, 0, sizeof(g_pcm2));
        add_signal(g_pcm2, tones, f_true, 2.60, 0.3);
        r = run_at(g_pcm2, f_true, ANCHOR_OF(2.60), FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0 && r.peak > 0.0, "late signal: rc=%d peak=%g", rc, r.peak);
        /* anchors at the extremes of the band and of the cycle */
        r = run_at(g_pcm2, 150.0, 0.0, FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0, "anchor at 150 Hz, t = 0");
        r = run_at(g_pcm2, 3070.0, 14.9, FT8_COH_FLAG_ESTIMATE_ONLY, &rc);
        CHECK(rc == 0, "anchor at 3070 Hz, t = 14.9");
    }
    printf("A: estimator, %d failures so far\n", g_failures);
}

static void f1b_and_gate(void)
{
    uint8_t tones[FT8_NN];
    CHECK(tones_for("CQ Q1ABC FN20", tones, NULL) == 0, "encode");
    const double f_true = 1500.0, start = 0.55;
    const double snrs[] = { -26.0, -18.0, -10.0, -2.0, 6.0, 14.0 };
    double prev = -1e9;
    int monotonic = 1;
    for (int i = 0; i < 6; i++) {
        memset(g_pcm, 0, sizeof(g_pcm));
        add_signal(g_pcm, tones, f_true, start, 0.3);
        add_noise(g_pcm, sigma_for_snr(0.3, snrs[i]));
        int rc; FT8CohFallbackResult r = run_at(g_pcm, f_true, ANCHOR_OF(start), FT8_COH_FLAG_FORCE_C3, &rc);
        CHECK(rc == 0 && r.n_refs == 24, "rc %d refs %d", rc, r.n_refs);
        CHECK(r.gated == (r.f1b_db <= CF_T1_DB ? 1 : 0), "gate follows F1b: %.3f gated=%d", r.f1b_db, r.gated);
        if (!(r.f1b_db > prev)) monotonic = 0;
        printf("   SNR %+5.0f dB -> F1b %.2f dB gated=%d crc=%d\n", snrs[i], r.f1b_db, r.gated, r.bp_crc_ok);
        prev = r.f1b_db;
    }
    CHECK(monotonic, "F1b is not monotonic in signal strength");
    /* noise only: F1b low (the anchor peak is a noise peak like the references) and well under the gate */
    memset(g_pcm, 0, sizeof(g_pcm));
    add_noise(g_pcm, 0.1);
    int rc; FT8CohFallbackResult r = run_at(g_pcm, 1234.5, 0.66, 0, &rc);
    CHECK(rc == 0 && r.n_refs == 24 && r.f1b_db < 6.0 && r.gated == 1, "noise only: F1b %.2f gated %d", r.f1b_db, r.gated);
    /* references outside 200..3000 Hz are dropped: at 230 Hz the +40..+150 side survives, and the -40... side below 200 is dropped */
    r = run_at(g_pcm, 230.0, 0.66, FT8_COH_FLAG_ESTIMATE_ONLY | 0, &rc);
    memset(g_pcm2, 0, sizeof(g_pcm2)); add_noise(g_pcm2, 0.1);
    r = run_at(g_pcm2, 230.0, 0.66, 0, &rc);
    CHECK(rc == 0 && r.n_refs == 12 + 0 && r.n_refs <= 24, "230 Hz: %d references (expected 12 above; those below 200 Hz dropped)", r.n_refs);
    r = run_at(g_pcm2, 2950.0, 0.66, 0, &rc);
    CHECK(rc == 0 && r.n_refs < 24 && r.n_refs > 0, "2950 Hz: %d references", r.n_refs);
    printf("B: F1b and the gate, %d failures so far\n", g_failures);
}

static void bp_decode(void)
{
    uint8_t tones[FT8_NN]; ftx_message_t m;
    CHECK(tones_for("CQ Q1ABC FN20", tones, &m) == 0, "encode");
    const double f_true = 1500.0, start = 0.55;
    memset(g_pcm, 0, sizeof(g_pcm));
    add_signal(g_pcm, tones, f_true, start, 0.3);
    add_noise(g_pcm, sigma_for_snr(0.3, -4.0));
    int rc; float llr[174];
    FT8CohFallbackResult r; memset(&r, 0, sizeof(r));
    rc = ft8_coherent_fallback_at(g_pcm, 180000, f_true + 0.8, ANCHOR_OF(start) + 0.04, FT8_COH_FLAG_FORCE_C3, &r, llr);
    CHECK(rc == 0 && r.c3_ran == 1 && r.bp_rc == 0, "rc %d c3 %d bp_rc %d", rc, r.c3_ran, r.bp_rc);
    CHECK(r.bp_crc_ok == 1 && r.bp_path == 0, "BP only: crc %d path %d (path 1 would be OSD)", r.bp_crc_ok, r.bp_path);
    CHECK(memcmp(r.a91, m.payload, 10) == 0, "the decoded payload equals the encoded one");
    /* the hard decisions of the V3 LLRs on a clean strong signal: positive = bit 1; most should match the codeword */
    int nz = 0; for (int i = 0; i < 174; i++) if (llr[i] != 0.0f) nz++;
    CHECK(nz > 150, "only %d non-zero LLRs", nz);

    /* flags */
    FT8CohFallbackResult r2 = run_at(g_pcm, f_true, ANCHOR_OF(start), FT8_COH_FLAG_SKIP_F1B, &rc);
    CHECK(rc == 0 && r2.c3_ran == 1 && r2.n_refs == 0 && isnan(r2.f1b_db) && r2.gated == 0 && r2.f1b_ms == 0.0, "SKIP_F1B");
    /* a strong signal has F1b above the gate: without FORCE_C3 C3 does not run */
    memset(g_pcm2, 0, sizeof(g_pcm2));
    add_signal(g_pcm2, tones, f_true, start, 0.3);
    add_noise(g_pcm2, sigma_for_snr(0.3, 15.0));
    r2 = run_at(g_pcm2, f_true, ANCHOR_OF(start), 0, &rc);
    CHECK(rc == 0 && r2.gated == 0 && r2.f1b_db > CF_T1_DB && r2.c3_ran == 0 && r2.bp_rc == FT8_COH_BP_NOT_RUN && r2.bp_crc_ok == 0,
          "gate closes on a strong signal: F1b %.2f gated %d c3 %d", r2.f1b_db, r2.gated, r2.c3_ran);
    r2 = run_at(g_pcm2, f_true, ANCHOR_OF(start), FT8_COH_FLAG_FORCE_C3, &rc);
    CHECK(rc == 0 && r2.gated == 0 && r2.c3_ran == 1 && r2.bp_crc_ok == 1, "FORCE_C3 runs C3 although the gate is closed");
    /* noise only: no CRC-valid codeword */
    memset(g_pcm2, 0, sizeof(g_pcm2)); add_noise(g_pcm2, 0.1);
    r2 = run_at(g_pcm2, 1000.0, 0.7, FT8_COH_FLAG_FORCE_C3, &rc);
    CHECK(rc == 0 && r2.c3_ran == 1 && r2.bp_crc_ok == 0 && r2.bp_path == -1, "noise only: crc %d path %d", r2.bp_crc_ok, r2.bp_path);
    /* bad arguments */
    CHECK(ft8_coherent_fallback_at(NULL, 180000, 1000, 0.5, 0, &r2, NULL) == -1, "NULL pcm");
    CHECK(ft8_coherent_fallback_at(g_pcm, 180000, 1000, 0.5, 0, NULL, NULL) == -1, "NULL result");
    CHECK(ft8_coherent_fallback_at(g_pcm, 179999, 1000, 0.5, 0, &r2, NULL) == -1, "wrong length");
    FT8CohFallbackCycleStats st;
    CHECK(ft8_coherent_fallback_cycle(NULL, 180000, 0, &st, NULL, 0) == -1, "cycle: NULL pcm");
    CHECK(ft8_coherent_fallback_cycle(g_pcm, 180000, 0, NULL, NULL, 0) == -1, "cycle: NULL stats");
    CHECK(ft8_coherent_fallback_cycle(g_pcm, 1000, 0, &st, NULL, 0) == -1, "cycle: wrong length");
    printf("C: BP-only decode and flags, %d failures so far\n", g_failures);
}

static void reset_session(void) { hash_table_init(&g_session_hash_table); g_hash_table_initialised = true; }

static void cycle_export(void)
{
    uint8_t tones[FT8_NN]; ftx_message_t m;
    CHECK(tones_for("CQ Q1ABC FN20", tones, &m) == 0, "encode");
    FT8CohFallbackCycleStats st; FT8CohFallbackRow rows[400];

    /* no decode on this thread yet (or an empty list): nothing */
    tls_cf_ncands = 0; tls_cf_npayloads = 0;
    memset(g_pcm, 0, sizeof(g_pcm)); add_noise(g_pcm, 0.1);
    int n = ft8_coherent_fallback_cycle(g_pcm, 180000, 0, &st, rows, 400);
    CHECK(n == 0 && st.n_candidates == 0 && st.n_eligible == 0 && st.n_rows == 0, "empty list: n=%d", n);

    /* one decodable signal plus noise */
    reset_session();
    memset(g_pcm, 0, sizeof(g_pcm));
    add_signal(g_pcm, tones, 1000.0, 0.5, 0.3);
    add_noise(g_pcm, sigma_for_snr(0.3, 12.0));
    FT8Result res[64];
    int nd = ft8_decode_all(g_pcm, 180000, res, 64);
    CHECK(nd >= 1, "the synthetic CQ was not decoded (%d)", nd);
    int found = 0; for (int i = 0; i < nd; i++) if (!strcmp(res[i].message, "CQ Q1ABC FN20")) found++;
    CHECK(found >= 1, "decoded text");
    CHECK(tls_cf_ncands > 0 && tls_cf_ncands <= CF_CAND_CAPACITY, "retained %d candidates", tls_cf_ncands);
    CHECK(tls_cf_npayloads >= 1 && tls_cf_npayloads <= tls_cf_ncands, "retained %d payloads", tls_cf_npayloads);
    int ndec_rec = 0; for (int i = 0; i < tls_cf_ncands; i++) ndec_rec += tls_cf_cands[i].decoded;
    CHECK(ndec_rec == tls_cf_npayloads, "decoded candidates %d vs payloads %d", ndec_rec, tls_cf_npayloads);

    /* flag-independence: the export changes nothing the decode reports */
    FT8Result res2[64];
    reset_session();
    int nd2 = ft8_decode_all(g_pcm, 180000, res2, 64);
    CHECK(nd2 == nd && memcmp(res, res2, (size_t)nd * sizeof(FT8Result)) == 0, "a repeat decode differs (%d vs %d)", nd, nd2);

    n = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_INCLUDE_DECODED, &st, rows, 400);
    CHECK(n >= 0 && n == st.n_rows, "rows %d vs %d", n, st.n_rows);
    CHECK(st.n_candidates == tls_cf_ncands && st.n_decoded == ndec_rec, "counts: cand %d decoded %d", st.n_candidates, st.n_decoded);
    CHECK(st.n_eligible + st.n_dup_position + st.n_decoded == st.n_candidates, "eligible %d + dup %d + decoded %d != candidates %d",
          st.n_eligible, st.n_dup_position, st.n_decoded, st.n_candidates);
    /* R12' chain, output-first (the default): C3 + BP on every eligible candidate, F1b only on a new CRC-valid output */
    CHECK(st.n_gated <= st.n_f1b_computed && st.n_f1b_computed == st.n_crc_new && st.n_crc_new <= st.n_crc_ok &&
          st.n_crc_ok <= st.n_attempted && st.n_attempted == st.n_eligible && st.n_published <= st.n_gated && st.n_abandoned == 0,
          "chain: eligible %d attempted %d crcOk %d new %d f1b %d gated %d published %d abandoned %d",
          st.n_eligible, st.n_attempted, st.n_crc_ok, st.n_crc_new, st.n_f1b_computed, st.n_gated, st.n_published, st.n_abandoned);
    int decoded_rows = 0, eligible_rows = 0;
    for (int i = 0; i < n; i++) { if (rows[i].decoded) decoded_rows++; else eligible_rows++; }
    CHECK(eligible_rows == st.n_eligible && decoded_rows == st.n_decoded_estimated, "rows eligible %d/%d decoded %d/%d",
          eligible_rows, st.n_eligible, decoded_rows, st.n_decoded_estimated);
    /* R3 / A2(d): for the decoded candidate of the strong signal, the estimate lies in the window and is not on an edge */
    int checked = 0;
    for (int i = 0; i < n; i++) {
        if (rows[i].decoded && fabsf(rows[i].freq_hz - 1000.0f) < 6.0f) {
            CHECK(rows[i].r.edge == 0, "decoded candidate at %.1f Hz: edge", rows[i].freq_hz);
            CHECK(fabs(rows[i].r.est_dt_s) <= 0.06 && fabs(rows[i].r.est_df_hz) <= 2.0, "decoded candidate estimate (%+.2f Hz, %+.3f s)",
                  rows[i].r.est_df_hz, rows[i].r.est_dt_s);
            checked++;
        }
    }
    CHECK(checked >= 1, "no decoded row near 1000 Hz");
    for (int i = 0; i < n; i++) CHECK(rows[i].r.elapsed_ms >= 0.0 && rows[i].r.bp_rc != 0x7f7f7f7f, "row %d initialised", i);
    CHECK(st.total_ms > 0.0, "total_ms");

    /* a payload already decoded in the call is skipped; a new one is counted: plant the strong signal's own position as an
     * ELIGIBLE candidate and run with FORCE_C3 (the gate is closed on a strong signal) */
    tls_cf_ncands = 1;
    tls_cf_cands[0].freq_hz = 1000.0f; tls_cf_cands[0].dt = (float)ANCHOR_OF(0.5); tls_cf_cands[0].pass = 0; tls_cf_cands[0].decoded = 0;
    tls_cf_npayloads = 1; memcpy(tls_cf_payloads[0], m.payload, FTX_PAYLOAD_LENGTH_BYTES);
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, 0, &st, rows, 400);
    CHECK(n == 1 && st.n_eligible == 1 && st.n_attempted == 1 && st.n_crc_ok == 1 && st.n_crc_new == 0 && rows[0].crc_new == 0 &&
          st.n_f1b_computed == 0 && rows[0].f1b_computed == 0 && st.n_published == 0 && rows[0].published == 0,
          "already-decoded payload: n=%d ok=%d new=%d f1b=%d (F1b must NOT be computed)", n, st.n_crc_ok, st.n_crc_new, st.n_f1b_computed);
    tls_cf_npayloads = 0;
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, 0, &st, rows, 400);
    CHECK(n == 1 && st.n_crc_ok == 1 && st.n_crc_new == 1 && rows[0].crc_new == 1 && memcmp(rows[0].r.a91, m.payload, 10) == 0,
          "new payload: ok=%d new=%d", st.n_crc_ok, st.n_crc_new);
    CHECK(st.n_f1b_computed == 1 && rows[0].f1b_computed == 1 && rows[0].r.n_refs == 24 && rows[0].r.gated == 0 && st.n_gated == 0 &&
          rows[0].published == 0 && st.n_published == 0, "strong signal: F1b computed on demand, gate closed, not published");
    /* the same lattice position twice in the list is attempted once */
    tls_cf_ncands = 2; tls_cf_cands[1] = tls_cf_cands[0]; tls_cf_cands[1].pass = 1;
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, 0, &st, rows, 400);
    CHECK(n == 1 && st.n_eligible == 1 && st.n_dup_position == 1, "duplicate position: n=%d eligible=%d dup=%d", n, st.n_eligible, st.n_dup_position);
    /* rows_cap smaller than the rows: counts stay complete, rows are capped */
    tls_cf_ncands = 3; tls_cf_cands[0].freq_hz = 1000.0f; tls_cf_cands[1].freq_hz = 1200.0f; tls_cf_cands[2].freq_hz = 1400.0f;
    tls_cf_cands[1].pass = 0; tls_cf_cands[2].pass = 0; tls_cf_cands[1].dt = tls_cf_cands[2].dt = 0.66f; tls_cf_cands[1].decoded = tls_cf_cands[2].decoded = 0;
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_ESTIMATE_ONLY, &st, rows, 2);
    CHECK(n == 2 && st.n_rows == 3 && st.n_eligible == 3, "capped rows: n=%d n_rows=%d", n, st.n_rows);
    tls_cf_ncands = 0; tls_cf_npayloads = 0;
    printf("D/E: cycle export and candidate retention, %d failures so far\n", g_failures);
}

/* Amendment 3: output-first (default) and gate-first (harness) publish the SAME payloads, on a planted cycle with signals above and
 * below T1, a duplicate payload, a payload already decoded in the call, and noise-only candidates. */
static void order_equivalence(void)
{
    static const struct { const char* msg; double f; double amp; } sig[] = {
        { "CQ Q1AAA FN20", 800.0,  3.0 },    /* strong: F1b above T1 */
        { "CQ Q1BBB FN21", 1200.0, 0.30 },   /* weak */
        { "CQ Q1CCC FN22", 1600.0, 0.30 },   /* weak */
        { "CQ Q1BBB FN21", 2000.0, 0.30 },   /* the weak one's payload again */
        { "CQ Q1DDD FN23", 2400.0, 0.30 },   /* its payload is preloaded as "already decoded" */
    };
    uint8_t tones[FT8_NN]; ftx_message_t ms[5];
    memset(g_pcm, 0, sizeof(g_pcm));
    for (int i = 0; i < 5; i++) {
        CHECK(tones_for(sig[i].msg, tones, &ms[i]) == 0, "encode %d", i);
        add_signal(g_pcm, tones, sig[i].f, 0.5, sig[i].amp);
    }
    add_noise(g_pcm, sigma_for_snr(0.30, -15.0));
    const double freqs[] = { 800.0, 1200.0, 1600.0, 2000.0, 2400.0, 2800.0, 600.0 };   /* the last two: noise only */
    tls_cf_ncands = 7;
    for (int i = 0; i < 7; i++) {
        tls_cf_cands[i].freq_hz = (float)freqs[i]; tls_cf_cands[i].dt = (float)ANCHOR_OF(0.5); tls_cf_cands[i].pass = 0; tls_cf_cands[i].decoded = 0;
    }
    tls_cf_npayloads = 1; memcpy(tls_cf_payloads[0], ms[4].payload, FTX_PAYLOAD_LENGTH_BYTES);

    FT8CohFallbackCycleStats so, sg; static FT8CohFallbackRow ro[16], rg[16];
    int no = ft8_coherent_fallback_cycle(g_pcm, 180000, 0, &so, ro, 16);
    int ng = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_GATE_FIRST, &sg, rg, 16);
    CHECK(no == 7 && ng == 7, "rows %d / %d", no, ng);
    int same = 1, pubs = 0;
    for (int i = 0; i < 7; i++) {
        if (ro[i].published != rg[i].published) same = 0;
        if (ro[i].published && memcmp(ro[i].r.a91, rg[i].r.a91, FTX_PAYLOAD_LENGTH_BYTES)) same = 0;
        pubs += ro[i].published;
    }
    CHECK(same, "the two orders disagree on what publishes");
    CHECK(so.n_published == sg.n_published && so.n_published == pubs, "published %d / %d / %d", so.n_published, sg.n_published, pubs);
    CHECK(pubs >= 1, "nothing published: the weak signals should decode");
    CHECK(so.n_published <= 2, "the duplicate payload must publish once (published %d)", so.n_published);
    CHECK(ro[4].published == 0 && ro[4].crc_new == 0, "the already-decoded payload is not published");
    CHECK(ro[0].published == 0, "the strong signal is above T1 and is not published");
    CHECK(so.n_eligible == 7 && so.n_attempted == 7, "output-first attempts every eligible candidate: %d / %d", so.n_attempted, so.n_eligible);
    CHECK(sg.n_f1b_computed == 7 && sg.n_attempted == sg.n_gated, "gate-first computes F1b on every eligible: %d, attempts only the gated: %d vs %d",
          sg.n_f1b_computed, sg.n_attempted, sg.n_gated);
    CHECK(so.n_f1b_computed < sg.n_f1b_computed, "output-first computes F1b less often (%d vs %d)", so.n_f1b_computed, sg.n_f1b_computed);
    CHECK(so.n_gated <= so.n_f1b_computed && so.n_f1b_computed <= so.n_crc_ok && so.n_crc_ok <= so.n_attempted && so.n_attempted <= so.n_eligible,
          "output-first chain");
    CHECK(sg.n_gated <= sg.n_f1b_computed && sg.n_published <= sg.n_gated && sg.n_crc_ok <= sg.n_attempted && sg.n_attempted <= sg.n_eligible,
          "gate-first chain");
    for (int i = 0; i < 7; i++) CHECK(ro[i].published == 0 || (ro[i].f1b_computed && ro[i].r.gated && ro[i].crc_new), "row %d published without its predicates", i);
    tls_cf_ncands = 0; tls_cf_npayloads = 0;
    printf("F: order equivalence (published %d of 7; F1b computed %d vs %d), %d failures so far\n", so.n_published, so.n_f1b_computed, sg.n_f1b_computed, g_failures);
}

/* Stage 2 (shim 20260068): ft8_coherent_fallback_snapshot / _run / _unpack on the F cycle's planted candidates. */
static void stage2_exports(void)
{
    static const struct { const char* msg; double f; double amp; } sig[] = {
        { "CQ Q1AAA FN20", 800.0,  3.0 },    /* strong: F1b above T1 */
        { "CQ Q1BBB FN21", 1200.0, 0.30 },   /* weak */
        { "CQ Q1CCC FN22", 1600.0, 0.30 },   /* weak */
        { "CQ Q1BBB FN21", 2000.0, 0.30 },   /* the weak one's payload again */
        { "CQ Q1DDD FN23", 2400.0, 0.30 },   /* its payload is preloaded as "already decoded" */
    };
    uint8_t tones[FT8_NN]; ftx_message_t ms[5];
    memset(g_pcm, 0, sizeof(g_pcm));
    for (int i = 0; i < 5; i++) {
        CHECK(tones_for(sig[i].msg, tones, &ms[i]) == 0, "encode %d", i);
        add_signal(g_pcm, tones, sig[i].f, 0.5, sig[i].amp);
    }
    add_noise(g_pcm, sigma_for_snr(0.30, -15.0));
    const double freqs[] = { 800.0, 1200.0, 1600.0, 2000.0, 2400.0, 2800.0, 600.0 };
    tls_cf_ncands = 7;
    for (int i = 0; i < 7; i++) {
        tls_cf_cands[i].freq_hz = (float)freqs[i]; tls_cf_cands[i].dt = (float)ANCHOR_OF(0.5); tls_cf_cands[i].pass = 0; tls_cf_cands[i].decoded = 0;
    }
    tls_cf_npayloads = 1; memcpy(tls_cf_payloads[0], ms[4].payload, FTX_PAYLOAD_LENGTH_BYTES);

    CHECK(sizeof(FT8CohFallbackOut) == 56, "FT8CohFallbackOut is %zu bytes", sizeof(FT8CohFallbackOut));
    const int ssz = ft8_coherent_fallback_snapshot_size();
    CHECK(ssz > 0, "snapshot size %d", ssz);
    void* snap = malloc((size_t)ssz);
    CHECK(snap != NULL && ft8_coherent_fallback_snapshot(snap, ssz) == ssz, "snapshot");
    CHECK(ft8_coherent_fallback_snapshot(snap, ssz - 1) == -1 && ft8_coherent_fallback_snapshot(NULL, ssz) == -1, "snapshot bad arguments");

    /* the run reads only the snapshot: clobber the thread-local retention first */
    FT8CohFallbackCycleStats sc; static FT8CohFallbackRow rc_rows[16];
    int nc = ft8_coherent_fallback_cycle(g_pcm, 180000, 0, &sc, rc_rows, 16);
    tls_cf_ncands = 0; tls_cf_npayloads = 0;

    FT8CohFallbackCycleStats st; static FT8CohFallbackOut out[16];
    int n = ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, NULL, &st, out, 16);
    CHECK(n == 7 && nc == 7 && st.n_rows == 7 && st.n_eligible == 7 && st.n_attempted == 7 && st.n_abandoned == 0, "run rows %d eligible %d attempted %d abandoned %d",
          n, st.n_eligible, st.n_attempted, st.n_abandoned);
    CHECK(st.n_published == 0, "the run leaves publication to the caller");
    /* every payload the cycle export publishes is NEW_GATED in the run (the cycle de-duplicates; the run reports every member) */
    for (int i = 0; i < 7; i++) {
        if (rc_rows[i].published) {
            int hit = 0;
            for (int j = 0; j < 7; j++) if (out[j].state == FT8_COH_STATE_NEW_GATED && !memcmp(out[j].payload, rc_rows[i].r.a91, FTX_PAYLOAD_LENGTH_BYTES)) hit = 1;
            CHECK(hit, "payload published by the cycle export (row %d) is NEW_GATED in the run", i);
        }
    }
    int new_gated = 0;
    for (int j = 0; j < 7; j++) {
        if (out[j].state == FT8_COH_STATE_NEW_GATED) {
            new_gated++;
            char text[64];
            CHECK(ft8_coherent_fallback_unpack(out[j].payload, text, 64) == 0, "unpack row %d", j);
            int is_b = !strcmp(text, "CQ Q1BBB FN21"), is_c = !strcmp(text, "CQ Q1CCC FN22");
            CHECK(is_b || is_c, "row %d text %s", j, text);
            CHECK(out[j].snr_db >= -20 && out[j].snr_db <= -10, "row %d coherent SNR %d dB (planted -15)", j, out[j].snr_db);
            CHECK(out[j].f1b_db <= CF_T1_DB && !isnan(out[j].f1b_db), "row %d F1b %.2f", j, out[j].f1b_db);
            CHECK(fabsf(out[j].out_freq_hz - out[j].freq_hz) <= 2.001f && fabsf(out[j].out_dt_s - out[j].dt_s) <= 0.1201f, "row %d reported position inside the window", j);
        }
        if (j == 4) CHECK(out[j].state == FT8_COH_STATE_KNOWN || out[j].state == FT8_COH_STATE_NO_CRC, "the preloaded payload is known (or not decoded): state %d", out[j].state);
        if (j == 0) CHECK(out[j].state == FT8_COH_STATE_GATED_OUT || out[j].state == FT8_COH_STATE_KNOWN || out[j].state == FT8_COH_STATE_NO_CRC,
                          "the strong signal is never a candidate for publication: state %d", out[j].state);
        if (j >= 5) CHECK(out[j].state == FT8_COH_STATE_NO_CRC, "noise-only candidate %d: state %d", j, out[j].state);
    }
    CHECK(new_gated >= 2, "both weak signals (and the repeat) recovered: %d NEW_GATED", new_gated);
    CHECK(st.n_gated == new_gated, "n_gated %d vs NEW_GATED rows %d", st.n_gated, new_gated);

    /* R7': a zero budget and a set cancel flag abandon every eligible candidate, counted, none attempted, nothing computed */
    FT8CohFallbackCycleStats sz;
    n = ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, 0.0, NULL, &sz, out, 16);
    CHECK(n == 7 && sz.n_attempted == 0 && sz.n_abandoned == 7 && sz.n_crc_ok == 0 && sz.n_f1b_computed == 0, "zero budget: attempted %d abandoned %d", sz.n_attempted, sz.n_abandoned);
    for (int j = 0; j < 7; j++) CHECK(out[j].state == FT8_COH_STATE_ABANDONED && out[j].out_freq_hz == out[j].freq_hz, "abandoned row %d", j);
    volatile int32_t cancel = 1;
    n = ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, &cancel, &sz, out, 16);
    CHECK(n == 7 && sz.n_attempted == 0 && sz.n_abandoned == 7, "cancel flag: attempted %d abandoned %d", sz.n_attempted, sz.n_abandoned);
    cancel = 0;
    n = ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, &cancel, &sz, out, 16);
    CHECK(n == 7 && sz.n_attempted == 7 && sz.n_abandoned == 0, "cancel flag clear: attempted %d", sz.n_attempted);
    /* a budget that runs out mid-run: attempted + abandoned = eligible, and the abandoned ones are the LAST ones */
    n = ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, st.total_ms / 3.0, NULL, &sz, out, 16);
    CHECK(n == 7 && sz.n_attempted + sz.n_abandoned == 7, "mid-run budget: attempted %d abandoned %d", sz.n_attempted, sz.n_abandoned);
    { int seen_abandoned = 0, order_ok = 1;
      for (int j = 0; j < 7; j++) { if (out[j].state == FT8_COH_STATE_ABANDONED) seen_abandoned = 1; else if (seen_abandoned) order_ok = 0; }
      CHECK(order_ok, "abandoned candidates are the tail of the list"); }
    /* rows capped: counts stay complete */
    n = ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, NULL, &sz, out, 3);
    CHECK(n == 3 && sz.n_rows == 7 && sz.n_attempted == 7, "capped rows: n=%d n_rows=%d", n, sz.n_rows);

    /* bad arguments */
    CHECK(ft8_coherent_fallback_run(NULL, 180000, snap, ssz, 0, -1.0, NULL, &st, out, 16) == -1, "NULL pcm");
    CHECK(ft8_coherent_fallback_run(g_pcm, 180000, NULL, ssz, 0, -1.0, NULL, &st, out, 16) == -1, "NULL snapshot");
    CHECK(ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz - 1, 0, -1.0, NULL, &st, out, 16) == -1, "wrong snapshot length");
    CHECK(ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 1, -1.0, NULL, &st, out, 16) == -1, "non-zero flags are reserved");
    CHECK(ft8_coherent_fallback_run(g_pcm, 179999, snap, ssz, 0, -1.0, NULL, &st, out, 16) == -1, "wrong pcm length");
    CHECK(ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, NULL, NULL, out, 16) == -1, "NULL stats");
    CHECK(ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, NULL, &st, NULL, 16) == -1, "NULL rows");
    { cf_snapshot_t* bad = (cf_snapshot_t*)snap; int32_t keep = bad->n_cands; bad->n_cands = CF_CAND_CAPACITY + 1;
      CHECK(ft8_coherent_fallback_run(g_pcm, 180000, snap, ssz, 0, -1.0, NULL, &st, out, 16) == -1, "out-of-range candidate count"); bad->n_cands = keep; }
    { char text[64]; uint8_t ff[12]; memset(ff, 0xFF, sizeof(ff));
      CHECK(ft8_coherent_fallback_unpack(ff, text, 64) == -2, "an undefined message type does not unpack");
      CHECK(ft8_coherent_fallback_unpack(NULL, text, 64) == -1 && ft8_coherent_fallback_unpack(ff, NULL, 64) == -1 && ft8_coherent_fallback_unpack(ff, text, 8) == -1, "unpack bad arguments"); }

    free(snap);
    tls_cf_ncands = 0; tls_cf_npayloads = 0;
    printf("G: Stage 2 exports (snapshot, run, unpack), %d failures so far\n", g_failures);
}

int main(void)
{
    sizes();
    estimator();
    f1b_and_gate();
    bp_decode();
    cycle_export();
    order_equivalence();
    stage2_exports();
    printf("%d checks, %d failures\nRESULT: %s\n", g_checks, g_failures, g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
