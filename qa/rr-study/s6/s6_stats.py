"""S6 statistics (QA tooling; spec 2026-10-13-1625 section 3 + amendment 1). PURE functions on in-memory observations; no files, no text out.

Data model (built by s6_analyse.build_obs; keys are opaque tuples that exist only in memory):
    obs[wav] = {"band": str, "sun": str, "trials": {t: {"w": {key: snr}, "o": {key: snr}, "hw": int, "ho": int, "order": int, "abandoned": bool}}}
  w / o  = the non-hashed rows of WSJT-X / OpenWSFZ for that play, key -> reported SNR (dB); hw / ho = hashed rows, counted and EXCLUDED.

Method notes (each is stated in the report):
  * signal identity = (message text, rank among same-text rows by frequency), not the 50 Hz bin of the old S6 (a bin edge splits a signal
    whose two reported frequencies differ by a few Hz); the key is built in s6_analyse.
  * the ANOVA parts are the signals BOTH appraisers decoded in ALL trials: conditional on detection, so repeatability is understated and ndc
    overstated; the candidate count is reported beside the part count.
  * every interval is a WAV-clustered bootstrap (signals of one WAV share a cycle; the WAV is the cluster), fixed seed.
  * kappa is computed on the union universe over trials (rows = wav x signal x trial); its "neither" cell exists only through trial-to-trial
    flicker, so it is reported with that caveat; the positive-agreement share is the readable agreement figure.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

BOOT_N = 2000
BOOT_SEED = 20261013
K = 3


# ---------------------------------------------------------------- ANOVA (vectorised twin of analyse_corpus_anova._gage_rr_anova)

def gage_rr(cube: np.ndarray) -> dict:
    """cube[n_parts, 2 appraisers (0 WSJT-X, 1 OpenWSFZ), r trials] of SNR. AIAG two-way crossed ANOVA with interaction."""
    n, a, r = cube.shape
    if n < 2 or r < 2:
        return {"error": "only %d parts" % n}
    gm = cube.mean()
    pm = cube.mean(axis=(1, 2))
    am = cube.mean(axis=(0, 2))
    cm = cube.mean(axis=2)
    ss_part = a * r * ((pm - gm) ** 2).sum()
    ss_app = n * r * ((am - gm) ** 2).sum()
    ss_int = r * ((cm - pm[:, None] - am[None, :] + gm) ** 2).sum()
    ss_err = ((cube - cm[:, :, None]) ** 2).sum()
    df_p, df_a = n - 1, a - 1
    df_i, df_e = df_p * df_a, n * a * (r - 1)
    ms_p, ms_a, ms_i, ms_e = ss_part / df_p, ss_app / df_a, ss_int / df_i, ss_err / df_e
    ev2 = ms_e
    av2 = max(0.0, (ms_a - ms_i) / (n * r))
    int2 = max(0.0, (ms_i - ms_e) / r)
    pv2 = max(0.0, (ms_p - ms_i) / (a * r))
    repro2 = av2 + int2
    rr2 = ev2 + repro2
    tv2 = rr2 + pv2
    ev, av, it, rep, rr, pv, tv = (math.sqrt(x) for x in (ev2, av2, int2, repro2, rr2, pv2, tv2))

    def pc(v2): return 100.0 * v2 / tv2 if tv2 > 0 else 0.0
    def ps(v): return 100.0 * v / tv if tv > 0 else 0.0

    return {"n_parts": n,
            "pct_contribution": {"EV": pc(ev2), "AV": pc(av2), "INT": pc(int2), "Reproducibility": pc(repro2), "RR": pc(rr2), "PV": pc(pv2)},
            "pct_study_var": {"EV": ps(ev), "AV": ps(av), "INT": ps(it), "Reproducibility": ps(rep), "RR": ps(rr), "PV": ps(pv)},
            "ndc": (1.41 * pv / rr) if rr > 0 else float("inf"),
            "components_db": {"EV": ev, "AV": av, "INT": it, "RR": rr, "PV": pv, "TV": tv},
            "appraiser_means_db": [float(am[0]), float(am[1])], "ms": {"part": ms_p, "appraiser": ms_a, "interaction": ms_i, "error": ms_e}}


def parts_of_wav(trials: dict) -> np.ndarray:
    """The wav's ANOVA parts as an array [n, 2, K]: signals decoded by BOTH appraisers in EVERY one of the K trials."""
    if sorted(trials) != list(range(K)):
        return np.zeros((0, 2, K))
    common = None
    for t in range(K):
        k = set(trials[t]["w"]) & set(trials[t]["o"])
        common = k if common is None else common & k
    rows = [[[trials[t]["w"][key] for t in range(K)], [trials[t]["o"][key] for t in range(K)]] for key in sorted(common or [])]
    return np.array(rows, dtype=float).reshape(-1, 2, K)


# ---------------------------------------------------------------- per-WAV tallies

def wav_tally(trials: dict) -> dict:
    """Everything one WAV contributes, as counts and sums (so a bootstrap can add them up)."""
    keys_w, keys_o = defaultdict(int), defaultdict(int)
    both = either = 0
    cnt_w = cnt_o = 0
    snr_d, tp = [], 0
    kap = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    universe = set()
    for t in trials.values():
        universe |= set(t["w"]) | set(t["o"])
    for t in sorted(trials):
        w, o = trials[t]["w"], trials[t]["o"]
        for key in w:
            keys_w[key] += 1
        for key in o:
            keys_o[key] += 1
        b = set(w) & set(o)
        both += len(b)
        either += len(set(w) | set(o))
        cnt_w += len(w)
        cnt_o += len(o)
        snr_d += [o[k] - w[k] for k in b]
        for key in universe:
            iw, io = key in w, key in o
            kap["tp" if iw and io else "tn" if not iw and not io else "fp" if io else "fn"] += 1
    nt = len(trials)
    # legacy consistency: over the union universe of the WAV, "same decision in every trial"
    cons_w_leg = sum(1 for k in universe if keys_w[k] in (0, nt))
    cons_o_leg = sum(1 for k in universe if keys_o[k] in (0, nt))
    # own-universe consistency: among the signals the appraiser decoded at least once, the share decoded in every trial
    own_w, own_w_all = sum(1 for k in universe if keys_w[k] > 0), sum(1 for k in universe if keys_w[k] == nt)
    own_o, own_o_all = sum(1 for k in universe if keys_o[k] > 0), sum(1 for k in universe if keys_o[k] == nt)
    return {"n_universe": len(universe), "cons_w_leg": cons_w_leg, "cons_o_leg": cons_o_leg,
            "own_w": own_w, "own_w_all": own_w_all, "own_o": own_o, "own_o_all": own_o_all,
            "both": both, "either": either, "trials": nt, "dec_w": cnt_w / nt if nt else 0.0, "dec_o": cnt_o / nt if nt else 0.0,
            "snr_d_sum": float(sum(snr_d)), "snr_d_n": len(snr_d), "snr_d_sq": float(sum(x * x for x in snr_d)),
            "kappa": kap, "parts": parts_of_wav(trials)}


def pool(tallies: list) -> dict:
    """Headline numbers from a list of per-WAV tallies (a bootstrap resample repeats entries)."""
    if not tallies:
        return {}
    s = lambda k: sum(t[k] for t in tallies)
    n_univ = s("n_universe")
    out = {"wavs": len(tallies), "signals_in_universe": n_univ,
           "consistency_legacy_wsjtx": s("cons_w_leg") / n_univ if n_univ else None,
           "consistency_legacy_owsfz": s("cons_o_leg") / n_univ if n_univ else None,
           "consistency_own_wsjtx": s("own_w_all") / s("own_w") if s("own_w") else None,
           "consistency_own_owsfz": s("own_o_all") / s("own_o") if s("own_o") else None,
           "positive_agreement": s("both") / s("either") if s("either") else None,
           "decodes_per_wav_wsjtx": float(np.mean([t["dec_w"] for t in tallies])),
           "decodes_per_wav_owsfz": float(np.mean([t["dec_o"] for t in tallies]))}
    out["decodes_per_wav_diff_owsfz_minus_wsjtx"] = out["decodes_per_wav_owsfz"] - out["decodes_per_wav_wsjtx"]
    n = s("snr_d_n")
    out["snr_delta_n"] = n
    out["snr_delta_mean"] = s("snr_d_sum") / n if n else None
    if n > 1:
        var = max(0.0, (s("snr_d_sq") - s("snr_d_sum") ** 2 / n) / (n - 1))
        out["snr_delta_sd"] = math.sqrt(var)
    parts = [t["parts"] for t in tallies if len(t["parts"])]
    cube = np.concatenate(parts) if parts else np.zeros((0, 2, K))
    out["anova_parts"] = int(len(cube))
    if len(cube) >= 2:
        g = gage_rr(cube)
        out["anova"] = g
    return out


def kappa_legacy(tallies: list) -> dict:
    """Cohen's kappa with the old asymptotic CI, on rows = wav x signal x trial of the union universe (see the module note)."""
    k = {x: sum(t["kappa"][x] for t in tallies) for x in ("tp", "tn", "fp", "fn")}
    n = sum(k.values())
    if n == 0:
        return {"kappa": None}
    po = (k["tp"] + k["tn"]) / n
    pe = ((k["tp"] + k["fp"]) / n) * ((k["tp"] + k["fn"]) / n) + ((k["tn"] + k["fn"]) / n) * ((k["tn"] + k["fp"]) / n)
    kap = 1.0 if abs(1 - pe) < 1e-9 else (po - pe) / (1 - pe)
    se = math.sqrt(po * (1 - po) / (n * (1 - pe) ** 2)) if abs(1 - pe) > 1e-9 else 0.0
    return {"kappa": round(kap, 4), "ci95_asymptotic": [round(kap - 1.96 * se, 4), round(kap + 1.96 * se, 4)], "rows": n, **k,
            "note": "the both-negative cell exists only through trial-to-trial flicker; read with the positive-agreement share"}


# ---------------------------------------------------------------- clustered bootstrap

FLAT = ("consistency_legacy_wsjtx", "consistency_legacy_owsfz", "consistency_own_wsjtx", "consistency_own_owsfz", "positive_agreement",
        "decodes_per_wav_wsjtx", "decodes_per_wav_owsfz", "decodes_per_wav_diff_owsfz_minus_wsjtx", "snr_delta_mean")
ANOVA_KEYS = (("pct_study_var", "EV"), ("pct_study_var", "AV"), ("pct_study_var", "INT"), ("pct_study_var", "RR"), ("pct_study_var", "PV"),
              ("pct_contribution", "RR"), ("pct_contribution", "PV"))


def bootstrap(tallies: list, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """WAV-clustered percentile CIs [2.5, 97.5] of the headline numbers and of the ANOVA %StudyVar rows (the WAV is the cluster)."""
    n = len(tallies)
    rng = np.random.default_rng(seed)
    flat = {k: [] for k in FLAT}
    anova = {"/".join(k): [] for k in ANOVA_KEYS}
    anova["ndc"] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        p = pool([tallies[i] for i in idx])
        for k in FLAT:
            v = p.get(k)
            if v is not None:
                flat[k].append(v)
        g = p.get("anova")
        if g and "error" not in g:
            for a, b in ANOVA_KEYS:
                anova[a + "/" + b].append(g[a][b])
            if math.isfinite(g["ndc"]):
                anova["ndc"].append(g["ndc"])

    def ci(v):
        return [round(float(x), 4) for x in np.percentile(v, [2.5, 97.5])] if len(v) >= max(20, n_boot // 10) else None

    return {"n_boot": n_boot, "seed": seed, "cluster": "WAV", "headline": {k: ci(v) for k, v in flat.items()},
            "anova": {k: ci(v) for k, v in anova.items()}}


# ---------------------------------------------------------------- order and trial-index effects

def spearman(x, y) -> dict:
    from scipy.stats import spearmanr
    if len(set(x)) < 2 or len(set(y)) < 2:
        return {"rho": None, "p": None, "n": len(x)}
    r, p = spearmanr(x, y)
    return {"rho": round(float(r), 4), "p": round(float(p), 4), "n": len(x), "flagged_p_lt_0.05": bool(p < 0.05)}


def order_effect(obs: dict) -> dict:
    """Spearman of the position within the trial (0..n-1) against the play's non-hashed decode count, per appraiser."""
    pos, cw, co = [], [], []
    for w in obs.values():
        for t in w["trials"].values():
            pos.append(t["order"])
            cw.append(len(t["w"]))
            co.append(len(t["o"]))
    return {"wsjtx": spearman(pos, cw), "owsfz": spearman(pos, co)}


def trial_effect(obs: dict, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """Mean non-hashed decodes per play by trial index, and the WAV-paired differences (trial 1 - 0, 2 - 0), WAV-clustered CI."""
    wavs = sorted(obs)
    mat = {a: np.array([[len(obs[w]["trials"][t][a]) for t in range(K)] for w in wavs], float) for a in ("w", "o")}
    out = {"wavs": len(wavs)}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(wavs), size=(n_boot, len(wavs)))
    for a, name in (("w", "wsjtx"), ("o", "owsfz")):
        m = mat[a]
        out[name] = {"mean_by_trial": [round(float(m[:, t].mean()), 3) for t in range(K)]}
        for t in (1, 2):
            d = m[:, t] - m[:, 0]
            boot = d[idx].mean(axis=1)
            out[name]["diff_trial%d_minus_trial0" % t] = {"mean": round(float(d.mean()), 3), "ci95": [round(float(x), 3) for x in np.percentile(boot, [2.5, 97.5])]}
    return out
