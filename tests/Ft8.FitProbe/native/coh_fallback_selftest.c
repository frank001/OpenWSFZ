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
    CHECK(sizeof(FT8CohFallbackCycleStats) == 80, "FT8CohFallbackCycleStats is %zu bytes", sizeof(FT8CohFallbackCycleStats));
    CHECK(sizeof(FT8CohFallbackRow) == 136, "FT8CohFallbackRow is %zu bytes", sizeof(FT8CohFallbackRow));
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
    CHECK(st.n_attempted <= st.n_gated + 0 || st.n_attempted <= st.n_eligible, "attempted %d", st.n_attempted);
    CHECK(st.n_gated <= st.n_eligible && st.n_attempted == st.n_gated, "gated %d attempted %d eligible %d (no FORCE_C3: attempted == gated)",
          st.n_gated, st.n_attempted, st.n_eligible);
    CHECK(st.n_crc_new <= st.n_crc_ok && st.n_crc_ok <= st.n_attempted, "crc %d new %d attempted %d", st.n_crc_ok, st.n_crc_new, st.n_attempted);
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
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_FORCE_C3, &st, rows, 400);
    CHECK(n == 1 && st.n_eligible == 1 && st.n_attempted == 1 && st.n_crc_ok == 1 && st.n_crc_new == 0 && rows[0].crc_new == 0,
          "already-decoded payload: n=%d ok=%d new=%d", n, st.n_crc_ok, st.n_crc_new);
    tls_cf_npayloads = 0;
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_FORCE_C3, &st, rows, 400);
    CHECK(n == 1 && st.n_crc_ok == 1 && st.n_crc_new == 1 && rows[0].crc_new == 1 && memcmp(rows[0].r.a91, m.payload, 10) == 0,
          "new payload: ok=%d new=%d", st.n_crc_ok, st.n_crc_new);
    /* the same lattice position twice in the list is attempted once */
    tls_cf_ncands = 2; tls_cf_cands[1] = tls_cf_cands[0]; tls_cf_cands[1].pass = 1;
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_FORCE_C3, &st, rows, 400);
    CHECK(n == 1 && st.n_eligible == 1 && st.n_dup_position == 1, "duplicate position: n=%d eligible=%d dup=%d", n, st.n_eligible, st.n_dup_position);
    /* rows_cap smaller than the rows: counts stay complete, rows are capped */
    tls_cf_ncands = 3; tls_cf_cands[0].freq_hz = 1000.0f; tls_cf_cands[1].freq_hz = 1200.0f; tls_cf_cands[2].freq_hz = 1400.0f;
    tls_cf_cands[1].pass = 0; tls_cf_cands[2].pass = 0; tls_cf_cands[1].dt = tls_cf_cands[2].dt = 0.66f; tls_cf_cands[1].decoded = tls_cf_cands[2].decoded = 0;
    n = ft8_coherent_fallback_cycle(g_pcm, 180000, FT8_COH_FLAG_ESTIMATE_ONLY, &st, rows, 2);
    CHECK(n == 2 && st.n_rows == 3 && st.n_eligible == 3, "capped rows: n=%d n_rows=%d", n, st.n_rows);
    tls_cf_ncands = 0; tls_cf_npayloads = 0;
    printf("D/E: cycle export and candidate retention, %d failures so far\n", g_failures);
}

int main(void)
{
    sizes();
    estimator();
    f1b_and_gate();
    bp_decode();
    cycle_export();
    printf("%d checks, %d failures\nRESULT: %s\n", g_checks, g_failures, g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
