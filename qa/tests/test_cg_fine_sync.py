"""COH-GAIN: the fine-sync estimator (coh-gain/fine_sync.py). Pure NumPy, synthetic CPFSK signals with KNOWN offsets: no DLL, no corpus, no text.

HK-021(k)/HK-026: each property is shown to give both answers (a true offset is recovered; a wrong anchor beyond the window is flagged as an edge hit;
a data-free estimate is not the oracle's), and the efficient matmul form is checked against the naive per-hypothesis downconversion.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

CG = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CG))
import fine_sync as fs  # noqa: E402

FS12 = 12000
SYM12 = 1920            # samples per symbol at 12 kHz
N = 180_000


def make_tones(seed=1):
    rng = np.random.default_rng(seed)
    t = rng.integers(0, 8, fs.N_SYM)
    for s, tone in fs.SYNC_SYMBOLS.items():
        t[s] = tone
    return [int(x) for x in t]


def render(tones, f0, anchor_dt, df_true, dt_true, snr_db=None, seed=2, amp=0.2):
    """Continuous-phase 8-FSK at 12 kHz. Symbol 0 starts where fine_sync's convention puts it for the TRUE offsets."""
    start12 = 6 * (int(round(anchor_dt * fs.RATE_HZ)) - 320) + int(round(dt_true * FS12))
    pcm = np.zeros(N)
    phase = 0.0
    for p, tone in enumerate(tones):
        a = start12 + p * SYM12
        n = np.arange(SYM12)
        f = f0 + df_true + tone * 6.25
        ph = phase + 2 * np.pi * f * n / FS12
        lo, hi = max(a, 0), min(a + SYM12, N)
        if hi > lo:
            pcm[lo:hi] = amp * np.cos(ph[lo - a:hi - a])
        phase = ph[-1] + 2 * np.pi * f / FS12
    if snr_db is not None:
        rng = np.random.default_rng(seed)
        sig_pow = np.mean(pcm[start12:start12 + 79 * SYM12] ** 2)
        noise_pow = sig_pow / (10 ** (snr_db / 10)) * (6.25 * 8 / 2500.0) * 0 + sig_pow / (10 ** (snr_db / 10))
        pcm = pcm + rng.normal(0, np.sqrt(noise_pow), N)
    return pcm.astype(np.float32)


def test_grid_and_constants():
    assert fs.N_DF == 41 and fs.N_DT == 49 and fs.DT_STEP_SAMPLES == 10
    assert fs.DF_GRID[0] == -2.0 and fs.DF_GRID[-1] == 2.0
    assert abs(fs.DT_GRID_S[0] + 0.12) < 1e-12 and abs(fs.DT_GRID_S[-1] - 0.12) < 1e-12
    assert sorted(fs.SYNC_SYMBOLS) == list(range(0, 7)) + list(range(36, 43)) + list(range(72, 79))
    assert [fs.SYNC_SYMBOLS[i] for i in range(7)] == [3, 1, 4, 0, 6, 5, 2]


@pytest.mark.parametrize("df,dt", [(0.0, 0.0), (0.8, -0.035), (-1.3, 0.06), (1.9, 0.115), (-0.4, -0.11)])
def test_costas_estimator_recovers_a_known_offset_clean(df, dt):
    tones = make_tones()
    pcm = render(tones, 1500.0, 0.5, df, dt)
    r = fs.estimate(pcm, 1500.0, 0.5)
    assert abs(r["est_df_hz"] - df) <= 0.1 + 1e-9 and abs(r["est_dt_s"] - dt) <= 0.005 + 1e-9
    assert r["edge"] is False or max(abs(df), abs(dt) * 100 / 6) > 1.85


def test_costas_estimator_survives_noise():
    tones = make_tones(3)
    errs = []
    for seed in range(6):
        pcm = render(tones, 1200.0, 0.4, 0.7, 0.03, snr_db=-8, seed=seed)
        r = fs.estimate(pcm, 1200.0, 0.4)
        errs.append((abs(r["est_df_hz"] - 0.7), abs(r["est_dt_s"] - 0.03)))
    assert np.median([e[0] for e in errs]) <= 0.15 and np.median([e[1] for e in errs]) <= 0.0075


def test_a_true_offset_on_the_window_edge_is_flagged_and_one_beyond_it_is_not_recovered():
    tones = make_tones()
    r = fs.estimate(render(tones, 1500.0, 0.5, 2.0, 0.0), 1500.0, 0.5)             # true df exactly on the +2.0 Hz edge
    assert r["edge"] is True and r["est_df_hz"] == 2.0
    r = fs.estimate(render(tones, 1500.0, 0.5, 0.0, 0.12), 1500.0, 0.5)            # true dt exactly on the +0.12 s edge
    assert r["edge"] is True and r["est_dt_s"] == pytest.approx(0.12)
    # HK-026: V3's edge share is SUFFICIENT evidence of a too-narrow window, not necessary. A true offset well beyond the window is
    # simply not recovered, and the argmax need not sit on the edge (the coherent sum has dense interior sidelobes), so the report
    # also carries the histograms of est_df / est_dt.
    r = fs.estimate(render(tones, 1500.0, 0.5, 3.5, 0.0), 1500.0, 0.5)
    assert abs(r["est_df_hz"] - 3.5) > 1.0


def test_the_matmul_form_equals_the_naive_per_hypothesis_downconversion():
    """Row-for-row check of the efficient formulation against the definition: downconvert at f0+df, correlate at the hypothesis' start, sum the 21 Costas bins."""
    tones = make_tones(5)
    pcm = render(tones, 1000.0, 0.45, 0.6, 0.02)
    bb = fs.CE.downconvert_decimate(pcm, 1000.0)
    surf = fs.objective_surface(bb, 0.45, fs.SYNC_SYMBOLS)
    for i_df in (0, 7, 20, 26, 40):
        df = fs.DF_GRID[i_df]
        bb_df = fs.CE.downconvert_decimate(pcm, 1000.0 + df)
        for i_dt in (0, 11, 24, 31, 48):
            start = fs.symbol_start_samples(0.45) + int(fs.DT_STEPS[i_dt]) * fs.DT_STEP_SAMPLES
            X = fs.CE.correlate_symbols(bb_df, start)
            naive = abs(sum(X[p, t] for p, t in fs.SYNC_SYMBOLS.items()))
            assert surf[i_df, i_dt] == pytest.approx(naive, rel=2e-2, abs=1e-3 * surf.max()), (i_df, i_dt)


def test_oracle_uses_all_79_tones_and_is_at_least_as_sharp_as_the_data_free_peak():
    tones = make_tones(7)
    pcm = render(tones, 1700.0, 0.5, -0.9, -0.05, snr_db=-12, seed=11)
    sync = fs.estimate(pcm, 1700.0, 0.5)
    orac = fs.estimate(pcm, 1700.0, 0.5, fs.oracle_tones(tones))
    assert abs(orac["est_df_hz"] + 0.9) <= 0.1 + 1e-9 and abs(orac["est_dt_s"] + 0.05) <= 0.005 + 1e-9
    assert len(fs.oracle_tones(tones)) == 79 and orac["peak"] > sync["peak"]       # 79 coherent symbols out-sum 21


def test_a_wrong_tone_sequence_does_not_peak_at_the_truth():
    tones = make_tones(9)
    wrong = [(t + 3) % 8 if p not in fs.SYNC_SYMBOLS else t for p, t in enumerate(tones)]
    pcm = render(tones, 1300.0, 0.5, 0.5, 0.02)
    good = fs.estimate(pcm, 1300.0, 0.5, fs.oracle_tones(tones))
    bad = fs.estimate(pcm, 1300.0, 0.5, fs.oracle_tones(wrong))
    assert bad["peak"] < 0.5 * good["peak"]


def test_estimate_is_deterministic():
    tones = make_tones(4)
    pcm = render(tones, 900.0, 0.5, 0.3, 0.01, snr_db=-10, seed=5)
    assert fs.estimate(pcm, 900.0, 0.5) == fs.estimate(pcm, 900.0, 0.5)


def test_anchor_dt_for_step_is_whole_decimated_samples():
    for k in (-24, -1, 0, 5, 24):
        a = fs.anchor_dt_for_step(0.5, k)
        assert fs.symbol_start_samples(a) == fs.symbol_start_samples(0.5) + k * fs.DT_STEP_SAMPLES
