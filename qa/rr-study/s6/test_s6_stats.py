"""Unit tests for s6_stats: parity with the existing ANOVA, recovery of known variance components, hand-checked tallies, determinism."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, RR)
import s6_stats as S  # noqa: E402


def toy_cube(n, ev, av, it, pv, seed=7, mean=-12.0):
    """Known variance components: part sd pv, appraiser effect +-av/2 (sd av), part x appraiser sd it, trial noise sd ev."""
    rng = np.random.default_rng(seed)
    part = rng.normal(0, pv, size=(n, 1, 1))
    app = np.array([-av / 2, av / 2]).reshape(1, 2, 1)           # a fixed offset between the two appraisers
    inter = rng.normal(0, it, size=(n, 2, 1))
    noise = rng.normal(0, ev, size=(n, 2, 3))
    return mean + part + app + inter + noise


def test_vectorised_anova_equals_the_existing_one():
    from harness.analyse_corpus_anova import _gage_rr_anova
    cube = toy_cube(80, 1.0, 0.8, 1.5, 5.0)
    old = _gage_rr_anova({("w%d" % i, "k"): {t: (float(cube[i, 0, t]), float(cube[i, 1, t])) for t in range(3)} for i in range(len(cube))}, 3)
    new = S.gage_rr(cube)
    for k in ("EV", "AV", "INT", "RR", "PV"):
        assert abs(old["pct_study_var"][k] - new["pct_study_var"][k]) < 1e-9, k
        assert abs(old["pct_contribution"][k] - new["pct_contribution"][k]) < 1e-9, k
    assert abs(old["ndc"] - new["ndc"]) < 1e-9


def test_known_variance_components_are_recovered():
    ev, it, pv = 1.0, 1.5, 5.0
    g = S.gage_rr(toy_cube(4000, ev, 0.0, it, pv))
    c = g["components_db"]
    assert abs(c["EV"] - ev) < 0.05 and abs(c["INT"] - it) < 0.10 and abs(c["PV"] - pv) < 0.20
    # the appraiser offset 0.8 dB is recovered through the appraiser means
    g2 = S.gage_rr(toy_cube(4000, ev, 0.8, it, pv))
    assert abs((g2["appraiser_means_db"][1] - g2["appraiser_means_db"][0]) - 0.8) < 0.1


def obs_one_wav(trials):
    return {"band": "40m", "sun": "day", "trials": trials}


def tr(w, o, order=0, hw=0, ho=0):
    return {"w": w, "o": o, "hw": hw, "ho": ho, "order": order, "abandoned": False}


def test_tallies_by_hand():
    # signal a: decoded by both in all 3 trials; b: WSJT-X in 3, OWS in 1; c: OWS only in trial 0
    trials = {0: tr({"a": -10.0, "b": -15.0}, {"a": -9.0, "b": -14.0, "c": -20.0}),
              1: tr({"a": -10.5, "b": -15.0}, {"a": -9.5}),
              2: tr({"a": -10.0, "b": -16.0}, {"a": -9.0})}
    t = S.wav_tally(trials)
    assert t["n_universe"] == 3
    # WSJT-X: a 3, b 3, c 0 -> all three consistent; OpenWSFZ: a 3, b 1, c 1 -> only a consistent
    assert t["cons_w_leg"] == 3 and t["cons_o_leg"] == 1
    assert (t["own_w"], t["own_w_all"]) == (2, 2) and (t["own_o"], t["own_o_all"]) == (3, 1)
    assert t["both"] == 2 + 1 + 1 and t["either"] == 3 + 2 + 2
    assert abs(t["dec_w"] - 2.0) < 1e-12 and abs(t["dec_o"] - 5 / 3) < 1e-12
    assert t["snr_d_n"] == 4
    assert len(t["parts"]) == 1 and t["parts"].shape == (1, 2, 3)  # only "a" was decoded by both in every trial


def test_pool_and_bootstrap_are_deterministic_and_bracket_the_point():
    rng = np.random.default_rng(3)
    obs = {}
    for i in range(40):
        base = {("m%d" % j, 0): float(rng.normal(-12, 5)) for j in range(6)}
        trials = {}
        for t in range(3):
            w = {k: v + rng.normal(0, 0.5) for k, v in base.items() if rng.random() < 0.9}
            o = {k: v + 1.0 + rng.normal(0, 0.5) for k, v in base.items() if rng.random() < 0.7}
            trials[t] = tr(w, o, order=int(rng.integers(0, 40)))
        obs["w%02d" % i] = obs_one_wav(trials)
    tallies = [S.wav_tally(obs[w]["trials"]) for w in sorted(obs)]
    p = S.pool(tallies)
    assert 0.5 < p["positive_agreement"] < 0.9 and p["decodes_per_wav_wsjtx"] > p["decodes_per_wav_owsfz"]
    assert abs(p["snr_delta_mean"] - 1.0) < 0.15 and p["anova_parts"] > 20 and "anova" in p
    b1, b2 = S.bootstrap(tallies, n_boot=300), S.bootstrap(tallies, n_boot=300)
    assert b1 == b2
    lo, hi = b1["headline"]["positive_agreement"]
    assert lo < p["positive_agreement"] < hi
    lo, hi = b1["anova"]["pct_study_var/RR"]
    assert lo < p["anova"]["pct_study_var"]["RR"] < hi
    assert S.kappa_legacy(tallies)["rows"] == sum(sum(t["kappa"].values()) for t in tallies)
    assert S.order_effect(obs)["wsjtx"]["n"] == 120
    te = S.trial_effect(obs, n_boot=200)
    assert len(te["wsjtx"]["mean_by_trial"]) == 3
