"""S5 Gate A -- first-point analysis behind the Architect ruling of 2026-09-08 14:29Z.

Ships the ruling's arithmetic as code rather than as prose (HK-021(r)), so every figure in
`2026-09-08-1429-architect-to-qa-ruling-s5-gate-a-first-point-and-gate-form.md` can be
re-derived by anyone without re-reading the run directories.

INPUTS ARE COUNTS, NOT FILES. Every (events, AWGN slots) pair below is taken from that run's
own STUDY-SPEC Section 10 gate line, which QA's `fp_composition_per_part.py` (2026-09-04,
ROW C1) reproduced 18/18 against the committed reports. Nothing here re-reads a matched CSV,
and nothing here is back-computed from Section 6's `S5 FP` column -- that column mixes plain
rates with 95% upper bounds and is not a source of counts (standing guard).

Population, held constant throughout: SIGNAL-FREE AWGN SLOTS, S5 parts 0/1. Runs before
R&R-010 contributed 60 such slots each (2 parts x 30 trials), whether the battery's total S5 N
was 120 (4 parts) or 60 (R&R-009, AWGN parts only). R&R-010 raised parts 0/1 to 60 trials
each, so 2026-09-07 contributes 120.

CITATION GUARD. `18/540` evaluates to 3.333% -- the same digits as FP-PARITY's `12/360 =
3.333%` CP95 [1.934%, 5.345%], which is a DIFFERENT measurement carrying the mandatory labels
"in-chain, <=20260049, POST-REGRESSION". They share no population, denominator or instrument.
Cite this series only as `21/660 = 3.182%`, denominator attached.

Run: python qa/rr-study/s5_gate_a_first_point_analysis.py
"""

import math

from scipy import stats

CEILING = 0.06  # STUDY-SPEC Section 10, R&R-004. A convention, never traced to an NFR.

# (label, FP events, AWGN slots) -- each from that run's own Section 10 gate line.
SERIES = [
    ("8d6e1b1", 1, 60),
    ("7d36038", 1, 60),
    ("f5dec23", 4, 60),
    ("22b749c", 0, 60),
    ("872ba65", 1, 60),
    ("2e60949", 2, 60),
    ("3b52608", 4, 60),
    ("35378b9", 2, 60),
    ("4c7d5ad", 3, 60),   # targeted S5-only re-run; see the outcome-choice sensitivity below
    ("4cc1984", 3, 120),  # 2026-09-07, first run scored under R&R-010's Gate A
]
TARGETED = {"4c7d5ad"}  # run BECAUSE of a concern -> its inclusion must not carry the result

# Standalone S5 runs. Same scenario, different instrument (S5 alone, not the full battery).
# Reported for concordance only -- NEVER pooled into SERIES.
STANDALONE = [("a3738fc", 8, 300), ("10bbaad", 6, 300)]

# WSJT-X control on the identical slots: 0 events in every run on record.
CONTROL_EVENTS = 0


def cp_ub(k, n, alpha=0.05):
    """One-sided Clopper-Pearson upper bound -- the quantity the gate reads."""
    return 1.0 if k == n else float(stats.beta.ppf(1 - alpha, k + 1, n - k))


def cp_lb(k, n, alpha=0.05):
    return 0.0 if k == 0 else float(stats.beta.ppf(alpha, k, n - k + 1))


def max_passing_k(n, ceiling=CEILING):
    """Largest event count whose 95% UB still clears the ceiling at this N (-1 = none can)."""
    best = -1
    for k in range(n + 1):
        if cp_ub(k, n) <= ceiling:
            best = k
        else:
            break
    return best


def pct(x):
    return f"{x:.3%}"


def main():
    k_all = sum(k for _, k, _ in SERIES)
    n_all = sum(n for _, _, n in SERIES)
    p_all = k_all / n_all

    print("== 0. Gate envelope at N=120 reproduces R&R-004's ratified worked examples ==")
    for k in range(5):
        v = "PASS" if cp_ub(k, 120) <= CEILING else "FAIL"
        print(f"   k={k}/120  rate={pct(k/120):>8}  95% UB={pct(cp_ub(k, 120)):>8}  {v}")
    assert f"{cp_ub(2, 120):.4f}" == "0.0515", "k=2 must reproduce the ratified 5.15% PASS"
    assert f"{cp_ub(3, 120):.4f}" == "0.0633", "k=3 must reproduce the ratified 6.33% FAIL"

    print("\n== 1. The established rate: one population, ten readings ==")
    print(f"   {k_all}/{n_all} = {pct(p_all)}  CP95 [{pct(cp_lb(k_all, n_all))}, "
          f"{pct(cp_ub(k_all, n_all))}]")
    assert (k_all, n_all) == (21, 660), "series drifted -- re-read the ruling before citing"

    print("\n== 2. Is 2026-09-07 different from the nine before it? ==")
    name, k_t, n_t = SERIES[-1]
    k_h, n_h = k_all - k_t, n_all - n_t
    p_h = k_h / n_h
    print(f"   today      {k_t}/{n_t} = {pct(k_t/n_t)}  CP95 [{pct(cp_lb(k_t, n_t))}, "
          f"{pct(cp_ub(k_t, n_t))}]")
    print(f"   prior nine {k_h}/{n_h} = {pct(p_h)}  (never cite bare -- see CITATION GUARD)")
    print(f"   expected events today at the prior rate: {p_h * n_t:.2f}; observed {k_t}; "
          f"P(X<={k_t}) = {stats.binom.cdf(k_t, n_t, p_h):.3f}")
    print("   Fisher today vs prior nine: p = "
          f"{stats.fisher_exact([[k_t, n_t - k_t], [k_h, n_h - k_h]])[1]:.4f}")

    kr = sum(k for lab, k, _ in SERIES[:-1] if lab not in TARGETED)
    nr = sum(n for lab, _, n in SERIES[:-1] if lab not in TARGETED)
    print(f"   HK-021(y) sensitivity, dropping the targeted run(s) {sorted(TARGETED)}:")
    print(f"     routine-only history {kr}/{nr} = {pct(kr/nr)}; Fisher vs today p = "
          f"{stats.fisher_exact([[k_t, n_t - k_t], [kr, nr - kr]])[1]:.4f}")

    print("\n== 3. Homogeneity and trend across all ten readings ==")
    chi = sum((k - n * p_all) ** 2 / (n * p_all * (1 - p_all)) for _, k, n in SERIES)
    df = len(SERIES) - 1
    print(f"   chi2 = {chi:.3f}  df = {df}  p = {1 - stats.chi2.cdf(chi, df):.4f}")
    for lab, k, n in SERIES:
        z = (k - n * p_all) / math.sqrt(n * p_all * (1 - p_all))
        print(f"     {lab:9s} {k}/{n:<4d} z = {z:+.2f}")
    xs = list(range(len(SERIES)))
    xbar = sum(x * n for x, (_, _, n) in zip(xs, SERIES)) / n_all
    num = sum(k * (x - xbar) for x, (_, k, _) in zip(xs, SERIES))
    den = p_all * (1 - p_all) * sum(n * (x - xbar) ** 2 for x, (_, _, n) in zip(xs, SERIES))
    z = num / math.sqrt(den)
    print(f"   Cochran-Armitage trend on chronological order: z = {z:+.3f}, "
          f"two-sided p = {2 * (1 - stats.norm.cdf(abs(z))):.4f}")

    print("\n== 4. A fixed 6% UB ceiling is an N-DEPENDENT rate threshold ==")
    print(f"   {'N':>6} {'PASS iff k<=':>13} {'max tolerated rate':>20}")
    for n in (60, 120, 240, 300, 480, 600):
        k = max_passing_k(n)
        print(f"   {n:6d} {k:13d} {pct(k/n):>20}")

    print("\n== 5. The verdict flipped on N, not on the decoder ==")
    for lab, k, n in STANDALONE:
        v = "PASS" if cp_ub(k, n) <= CEILING else "FAIL"
        print(f"   standalone {lab:9s} {k}/{n} = {pct(k/n)}  UB {pct(cp_ub(k, n))}  {v}")
    lab, k, n = STANDALONE[-1]
    print(f"   Fisher {k}/{n} (2026-09-05) vs {k_t}/{n_t} (2026-09-07): "
          f"p = {stats.fisher_exact([[k_t, n_t - k_t], [k, n - k]])[1]:.4f}  -> same rate")

    print("\n== 6. Gate A's operating characteristic at the established rate ==")
    for n in (60, 120, 240, 480, 600):
        k = max_passing_k(n)
        print(f"   N={n:4d}  P(PASS) = {stats.binom.cdf(k, n, p_all):.3f}")
    print("   as a CHANGE detector at N=120 (FAIL iff k>=3):")
    for mult, lab in ((1.0, "no change"), (1.5, "1.5x"), (2.0, "doubling")):
        print(f"     true rate {pct(p_all * mult):>8} ({lab:9s}) -> P(FAIL) = "
              f"{1 - stats.binom.cdf(2, 120, p_all * mult):.3f}")

    print("\n== 7. Option A: the ratified ceiling on a trailing M-sweep window (N=120M) ==")
    for m in (2, 3, 4, 5, 6):
        n = 120 * m
        k = max_passing_k(n)
        print(f"   last {m} sweeps (N={n:3d}): PASS iff k<={k:3d}  "
              f"P(PASS) unchanged = {stats.binom.cdf(k, n, p_all):.3f}  "
              f"P(PASS) if doubled = {stats.binom.cdf(k, n, 2 * p_all):.3f}")

    print("\n== 8. The finding the gate argument does not touch: the WSJT-X control ==")
    print(f"   OpenWSFZ {k_all}/{n_all} = {pct(p_all)}  CP95 [{pct(cp_lb(k_all, n_all))}, "
          f"{pct(cp_ub(k_all, n_all))}]")
    print(f"   WSJT-X   {CONTROL_EVENTS}/{n_all} = {pct(0)}  95% UB {pct(cp_ub(0, n_all))}")
    print("   Fisher exact: p = "
          f"{stats.fisher_exact([[k_all, n_all - k_all], [CONTROL_EVENTS, n_all]])[1]:.3e}")
    print(f"   separation is at least {cp_lb(k_all, n_all) / cp_ub(0, n_all):.1f}x "
          "(a LOWER bound -- the control's numerator is zero)")


if __name__ == "__main__":
    main()
