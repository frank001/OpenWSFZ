"""GAP-CENSUS-A Part A (GATED) -- the aperture census. Spec Sec.4."""
from __future__ import annotations

S_A_BAR = 0.04


def run_part_a(pop, bucket_counts: dict, row0f_ok: bool, row0f_detail: dict, log) -> dict:
    n_a = bucket_counts["A"]
    s_a = n_a / pop.n_theirs_only
    pp = pop.pp_of_d001(n_a)

    log("Part A: bucket A (below f_min) count=%d, S_A=%.4f (%.2f%% of theirs-only), "
        "pp-of-D-001=%.2f" % (n_a, s_a, s_a * 100, pp))

    if s_a >= S_A_BAR and row0f_ok:
        row = "A1"
        reading = ("The passband is a funded item. The G2(b) ladder -- specced, five "
                   "Architect reviews, never armed -- is recommended for arming ahead of "
                   "the next DSP arm.")
    elif s_a < S_A_BAR:
        row = "A2"
        reading = "Passband is real but marginal; report and do not prioritise."
    else:  # s_a >= bar but ROW 0f unconfirmed
        row = "A3"
        reading = "S_A reported as an upper bound only; no funding consequence."

    log("Part A: ROW %s -- %s" % (row, reading))
    log("Part A: S_A is a CEILING on recovery -- it assumes every sub-f_min reference decode "
        "would be recoverable through a passband that is dozens of dB down at that frequency "
        "(ROW 0f: median margin over the noise floor there is %.1f dB, well above it, but that "
        "is not the same as 'decodable'). The realised fraction is what G2(b) was built to "
        "measure, not what this row reports."
        % row0f_detail.get("median_margin_db", float("nan")))

    return {
        "n_A": n_a,
        "S_A": s_a,
        "pp_of_d001": pp,
        "S_A_bar": S_A_BAR,
        "row0f_ok": row0f_ok,
        "row": row,
        "reading": reading,
    }
