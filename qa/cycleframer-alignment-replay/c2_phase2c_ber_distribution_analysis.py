#!/usr/bin/env python3
"""D-001 C.2 Phase 2c ruling, Sec.6.2 -- re-read the captured BER data as a distribution.

(2026-07-26-2030-architect-c2-phase2c-ruling.md Sec.6.2. "From already-captured data, no
re-decode": 1) decile table for all three arms, not median/mean/min/max; 2) control-arm
mismatch rate (fraction of control above 25% BER); 3) [BLOCKED -- see NOTE below]; 4) BER
against sync score, and BER against postnorm_mean_abs_llr, within THE 135.)

This is pure re-analysis of qa/cycleframer-alignment-replay/c2_phase2c_ber_measurement.py's
own already-self-checked data path -- it imports that module and reuses its Encoder,
population-selection, and hard_decision_ber functions rather than re-deriving them, so the
sign-convention finding and matched-hit self-check are not duplicated, only extended. No
native rebuild, no new decode run, no live data.

NOTE on Sec.6.2 item 3 (count of THE 135 below Sec.6.1's measured correction threshold):
Sec.6.1 asks for "our own bp_decode/OSD path" to be run on synthetic codewords with
injected bit errors, calling it a change requiring "no native change, no rebuild". That
premise does not hold: bp_decode and osd_decode are both `static` in
native/ft8_lib_build/patched/ft8/decode.c and reachable only from inside
ftx_decode_candidate/ftx_decode_candidate_ap, which take full waveform passes, not a raw
174-element LLR array. ft8_shim.h's existing exports (grep-verified this session) contain
no entry point that decodes a caller-supplied LLR array. Sec.6.1's calibration curve
therefore needs a new (small, diagnostic-only, opt-in) native export before it can run --
which is Developer-session work per HK-011, not something this QA session does directly.
Item 3 is BLOCKED on that and is reported as such below, not silently skipped. Items 1, 2
and 4 need no native change and are reported in full.

NFR-021: aggregate statistics only -- no callsign, message text, or per-record field is
ever printed. ASCII-only console output (HK-009).
"""
from __future__ import annotations

import os
import statistics as st
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
import c2_phase2c_ber_measurement as B  # noqa: E402  -- reuse the self-checked base module


def load_candidate_diag_full(path: str) -> dict[str, list[dict]]:
    """Like B.load_candidate_diag_with_llr, but also carries score and
    postnorm_mean_abs_llr, needed for Sec.6.2 item 4's within-THE-135 breakdown."""
    import csv
    by_cycle: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            llr_field = row.get("llr174", "")
            llr = [float(x) for x in llr_field.split(";")] if llr_field else []
            rec = {
                "freq_hz": float(row["freq_hz"]),
                "dt": float(row["dt"]),
                "score": int(row["score"]),
                "decoded": row["decoded"] == "1",
                "postnorm_mean_abs_llr": float(row["postnorm_mean_abs_llr"]),
                "llr174": llr,
            }
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


def measure_population_full(population: list[dict], cand_by_cycle: dict[str, list[dict]],
                             encoder: "B.Encoder", require_decoded: bool | None = None) -> list[dict]:
    """Like B.measure_population, but returns per-candidate (ber, score,
    postnorm_mean_abs_llr) tuples instead of a bare BER list."""
    out: list[dict] = []
    for row in population:
        true_bits = encoder.true_codeword(row["message"])
        if true_bits is None:
            continue
        cands = cand_by_cycle.get(row["ts"], [])
        if require_decoded is not None:
            cands = [c for c in cands if c["decoded"] == require_decoded]
        cand = B.nearest_candidate(row["freq"], row["dt"], cands)
        if cand is None or not cand["llr174"]:
            continue
        ber = B.hard_decision_ber(cand["llr174"], true_bits)
        out.append({"ber": ber, "score": cand["score"],
                     "postnorm_mean_abs_llr": cand["postnorm_mean_abs_llr"]})
    return out


def decile_table(label: str, bers: list[float]) -> None:
    if len(bers) < 10:
        print(f"  {label}: n={len(bers)} -- too few points for a decile table "
              f"(median={st.median(bers):.1%} shown instead)" if bers else f"  {label}: no data")
        return
    q = st.quantiles(sorted(bers), n=10)
    print(f"  {label}: n={len(bers)}")
    labels = ["p10", "p20", "p30", "p40", "p50(median)", "p60", "p70", "p80", "p90"]
    print("    " + "  ".join(f"{lb}={v:.1%}" for lb, v in zip(labels, q)))
    print(f"    mean={st.mean(bers):.1%}  min={min(bers):.1%}  max={max(bers):.1%}")


def mismatch_rate(label: str, bers: list[float], threshold: float = 0.25) -> float | None:
    if not bers:
        print(f"  {label}: no data")
        return None
    n_above = sum(1 for b in bers if b > threshold)
    rate = n_above / len(bers)
    print(f"  {label}: n={len(bers)}  fraction with BER > {threshold:.0%} = {n_above}/{len(bers)} "
          f"= {rate:.1%}")
    return rate


def pearson_r(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def bucket_report(title: str, records: list[dict], key: str, edges: list[float]) -> None:
    print(f"  {title} (bucketed by {key}):")
    buckets: list[tuple[float, float, list[float]]] = []
    lo = float("-inf")
    for hi in edges:
        buckets.append((lo, hi, []))
        lo = hi
    buckets.append((lo, float("inf"), []))
    for rec in records:
        v = rec[key]
        for b in buckets:
            if b[0] <= v < b[1]:
                b[2].append(rec["ber"])
                break
    for blo, bhi, bers in buckets:
        lo_s = "-inf" if blo == float("-inf") else f"{blo:g}"
        hi_s = "+inf" if bhi == float("inf") else f"{bhi:g}"
        if bers:
            print(f"    [{lo_s}, {hi_s}): n={len(bers)}  mean_ber={st.mean(bers):.1%}  "
                  f"median_ber={st.median(bers):.1%}")
        else:
            print(f"    [{lo_s}, {hi_s}): n=0")


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(B.WAV68_DIR) if f.endswith(".wav"))
    encoder = B.Encoder(B.DLL_PATH)

    k10_full = load_candidate_diag_full(os.path.join(B.K10_CAP_DIR, "candidate_diag.csv"))
    k4_full = load_candidate_diag_full(os.path.join(B.K4_CAP_DIR, "candidate_diag.csv"))

    control = B.compute_matched_hit_control(cycles, limit=200)
    pop135 = B.compute_135_population(cycles)
    population_648 = B.compute_648_population(cycles)
    pop567 = B.compute_567_population(population_648)

    control_full = measure_population_full(control, k10_full, encoder, require_decoded=True)
    the135_full = measure_population_full(pop135, k10_full, encoder, require_decoded=False)
    the567_full = measure_population_full(pop567, k4_full, encoder, require_decoded=False)

    print("=" * 90)
    print("Sec.6.2 item 1 -- decile tables (all three arms)")
    print("=" * 90)
    decile_table("matched-hit control", [r["ber"] for r in control_full])
    print()
    decile_table("THE 135", [r["ber"] for r in the135_full])
    print()
    decile_table("THE 567", [r["ber"] for r in the567_full])

    print()
    print("=" * 90)
    print("Sec.6.2 item 2 -- control-arm mismatch rate (measured artefact floor)")
    print("=" * 90)
    mismatch_rate("matched-hit control", [r["ber"] for r in control_full], threshold=0.25)

    print()
    print("=" * 90)
    print("Sec.6.2 item 3 -- count of THE 135 below Sec.6.1's measured correction threshold")
    print("=" * 90)
    print("  [BLOCKED] Sec.6.1 requires running bp_decode/osd_decode on synthetic LLR arrays.")
    print("  Both are `static` in decode.c, reachable only via ftx_decode_candidate(_ap), which")
    print("  take a full waveform pass, not a caller-supplied LLR array. No existing ft8_shim.h")
    print("  export exposes this (checked this session). A new opt-in diagnostic export is")
    print("  needed before Sec.6.1's calibration curve -- and by extension this item -- can run.")
    print("  This is Developer-session work per HK-011; not performed here. See the companion")
    print("  findings note for the proposed export shape, put to the Architect for sign-off.")

    print()
    print("=" * 90)
    print("Sec.6.2 item 4a -- THE 135: BER vs sync score")
    print("=" * 90)
    scores = [r["score"] for r in the135_full]
    bers = [r["ber"] for r in the135_full]
    r_score = pearson_r(scores, bers)
    print(f"  Pearson r(score, ber) = {r_score:.3f}" if r_score is not None else "  r: n/a")
    bucket_report("THE 135", the135_full, "score", [12, 15, 20, 25])

    print()
    print("=" * 90)
    print("Sec.6.2 item 4b -- THE 135: BER vs postnorm_mean_abs_llr")
    print("=" * 90)
    llrmag = [r["postnorm_mean_abs_llr"] for r in the135_full]
    r_llr = pearson_r(llrmag, bers)
    print(f"  Pearson r(postnorm_mean_abs_llr, ber) = {r_llr:.3f}" if r_llr is not None else "  r: n/a")
    if llrmag:
        qs = st.quantiles(sorted(llrmag), n=4)
        bucket_report("THE 135", the135_full, "postnorm_mean_abs_llr", qs)

    print()
    print("=" * 90)
    print("Descriptive only (NOT Sec.6.1's calibrated threshold -- illustrative band, per the")
    print("Architect's own caveat that his bands are a prior, not a derivation):")
    print("=" * 90)
    low_15 = sum(1 for b in bers if b <= 0.15)
    low_25 = sum(1 for b in bers if b <= 0.25)
    print(f"  THE 135: {low_15}/{len(bers)} candidates have BER <= 15% (illustrative 'decode effort' band)")
    print(f"  THE 135: {low_25}/{len(bers)} candidates have BER <= 25%")


if __name__ == "__main__":
    main()
