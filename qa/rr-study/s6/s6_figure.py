"""S6 six-panel figure (QA tooling): aggregates and per-WAV / per-signal numbers only, never message text.

Panels: (1) decodes per WAV, OpenWSFZ against WSJT-X; (2) within-appraiser consistency, own universe, with WAV-clustered CIs;
(3) matched SNR, OpenWSFZ against WSJT-X (the ANOVA parts, mean of the 3 trials); (4) %StudyVar of the Gage R&R components with CIs;
(5) SNR delta histogram (OpenWSFZ - WSJT-X); (6) mean decodes per play by trial index.
"""
from __future__ import annotations

import os

import numpy as np


def make_figure(path: str, obs: dict, tallies: list, head: dict, boot: dict) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    wavs = sorted(obs)
    cw = np.array([np.mean([len(obs[w]["trials"][t]["w"]) for t in obs[w]["trials"]]) for w in wavs])
    co = np.array([np.mean([len(obs[w]["trials"][t]["o"]) for t in obs[w]["trials"]]) for w in wavs])
    parts = np.concatenate([t["parts"] for t in tallies if len(t["parts"])] or [np.zeros((0, 2, 3))])
    fig, ax = plt.subplots(2, 3, figsize=(15, 8.5))

    a = ax[0, 0]
    lim = max(1.0, float(max(cw.max(initial=0), co.max(initial=0)))) * 1.05
    a.scatter(cw, co, s=14, alpha=0.7)
    a.plot([0, lim], [0, lim], "k--", lw=0.8)
    a.set(xlabel="WSJT-X decodes per WAV (mean of 3 plays)", ylabel="OpenWSFZ decodes per WAV", title="1. Decodes per WAV", xlim=(0, lim), ylim=(0, lim))

    a = ax[0, 1]
    b = boot.get("headline", {})
    names, vals, errs = [], [], []
    for lab, key in (("WSJT-X", "consistency_own_wsjtx"), ("OpenWSFZ", "consistency_own_owsfz")):
        v = head.get(key)
        if v is None:
            continue
        names.append(lab)
        vals.append(100 * v)
        c = b.get(key)
        errs.append([100 * v - 100 * c[0], 100 * c[1] - 100 * v] if c else [0, 0])
    a.bar(names, vals, yerr=np.array(errs).T if errs else None, capsize=4, color=["#4C78A8", "#F58518"][:len(names)])
    a.set(ylabel="% decoded in all 3 plays (of those decoded at least once)", ylim=(0, 100), title="2. Within-appraiser consistency")

    a = ax[0, 2]
    if len(parts):
        mw, mo = parts[:, 0, :].mean(axis=1), parts[:, 1, :].mean(axis=1)
        a.scatter(mw, mo, s=8, alpha=0.5)
        lo, hi = float(min(mw.min(), mo.min())) - 1, float(max(mw.max(), mo.max())) + 1
        a.plot([lo, hi], [lo, hi], "k--", lw=0.8)
    a.set(xlabel="WSJT-X SNR (dB, mean of 3)", ylabel="OpenWSFZ SNR (dB, mean of 3)", title="3. Matched SNR (ANOVA parts: %d)" % len(parts))

    a = ax[1, 0]
    g = head.get("anova")
    if g and "error" not in g:
        keys = ["EV", "AV", "INT", "RR", "PV"]
        v = [g["pct_study_var"][k] for k in keys]
        bb = boot.get("anova", {})
        er = [[v[i] - bb["pct_study_var/" + k][0], bb["pct_study_var/" + k][1] - v[i]] if bb.get("pct_study_var/" + k) else [0, 0] for i, k in enumerate(keys)]
        a.bar(keys, v, yerr=np.array(er).T, capsize=3, color="#54A24B")
        a.set(ylabel="% Study Variation", title="4. Gage R&R on SNR (ndc %.1f)" % g["ndc"])
    else:
        a.set(title="4. Gage R&R: not enough parts")

    a = ax[1, 1]
    d = (parts[:, 1, :] - parts[:, 0, :]).ravel() if len(parts) else np.array([])
    if d.size:
        a.hist(d, bins=40, color="#B279A2")
        a.axvline(float(d.mean()), color="k", lw=1)
    a.set(xlabel="OpenWSFZ - WSJT-X SNR (dB), ANOVA parts", ylabel="signals x trials", title="5. SNR delta")

    a = ax[1, 2]
    mt = {k: np.array([np.mean([len(obs[w]["trials"][t][k]) for w in wavs]) for t in range(3)]) for k in ("w", "o")}
    a.plot([1, 2, 3], mt["w"], "o-", label="WSJT-X")
    a.plot([1, 2, 3], mt["o"], "s-", label="OpenWSFZ")
    a.set(xlabel="trial", ylabel="mean decodes per play", xticks=[1, 2, 3], title="6. Decodes by trial index")
    a.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return os.path.basename(path)
