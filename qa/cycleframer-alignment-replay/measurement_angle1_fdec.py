#!/usr/bin/env python3
"""T4 / Angle 1 -- step 4: F_dec, the ROW verdict, and the AP-eligible sensitivity split.

Reads the outputs of measurement_angle1_population.py, measurement_angle1_n3_calibration.py
and measurement_angle1_legb.py and applies the 2026-08-02-1813 pre-registration's section 4
(decision rows) and section 6 (AP confound) mechanically.

Design (prereg section 3):
    decoder-attributable  =  B - A      (identical audio bytes, different decoder)
    capture-attributable  =  C - B      (identical decoder, different capture framing)
    total deficit         =  C - A
    F_dec                 = (B - A) / (C - A)

A, B, C here are each the TOTAL decode count (sum over the population, not a per-cycle
mean) for that leg -- consistent with "ratio-of-sums, never mean-of-ratios" (T3 item 4):
summing every leg fully across the population before taking the one ratio is ratio-of-sums
by construction; there is no per-cycle ratio anywhere in this computation to average.

ROW 5 / N3's non-finite guard both follow the amended (post-23:40 UTC) text exactly --
these amendments changed no threshold, they only made NaN/inf cases defined (see the
prereg's own inline changelog).

AP-eligible sensitivity (section 6): WSJT-X's compound/hashed-callsign tokens print as the
literal string "<...>" when NOT resolved via a-priori context (own callsign / active QSO
partner) and as the actual resolved callsign when they ARE. jt9 as invoked by
measurement_angle1_legb.py carries no -x/MyCall/AP flags at all (see endurance_anova_jt9.
_run_one_jt9_batch's cmd list), so leg B never resolves these. A C-side decode is therefore
classed AP-ELIGIBLE here iff, at the same cycle ts, there exists an UNMATCHED leg-B decode
whose message has the same token count and is identical to the C message in every token
except that one or more tokens read "<...>" in B where C shows a real value -- i.e. the
same underlying transmission, decoded both ways, differing only by hash resolution. This is
disclosed as a heuristic, not asserted as ground truth: WSJT-X's ALL.TXT format carries no
explicit AP-pass marker in this pipeline, so there is no fully authoritative signal
available; this is the closest mechanical proxy the data on disk supports.

Usage: python measurement_angle1_fdec.py
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
import anova_common as ac  # noqa: E402

WORK = os.path.join(os.path.dirname(__file__), "_work")
CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts",
                       "20260731_live_run_2004-8080")
OWSFZ_ALL_TXT = os.path.join(CORPUS, "owsfz", "ALL.TXT")
WSJTX_ALL_TXT = os.path.join(CORPUS, "wsjt-x", "ALL.TXT")


def load(name):
    with open(os.path.join(WORK, name), encoding="utf-8") as fh:
        return json.load(fh)


def evaluate_rows(f_dec, b_count, a_count):
    """Mechanical, ordered, mutually exclusive -- prereg section 4, ROW 0 guard first,
    ROW 5 catch-all last. Returns (row_number, verdict_text)."""
    if b_count < a_count:
        return 0, "STOP, DO NOT INTERPRET -- jt9 decoded fewer than our own decoder on our own audio; inverts the design's premise."
    if not math.isfinite(f_dec):
        return 5, "NO VERDICT -- F_dec is NaN/inf (degenerate denominator: C == A, or an empty leg)."
    if f_dec >= 0.70:
        return 2, "PREDOMINANTLY DECODER-ATTRIBUTABLE."
    if 0.30 < f_dec < 0.70:
        return 3, "MIXED. Both mechanisms material."
    if f_dec <= 0.30:
        return 4, "PREDOMINANTLY CAPTURE-ATTRIBUTABLE."
    return 5, "NO VERDICT -- reached fallthrough (should be unreachable if the above is exhaustive)."


def main() -> int:
    pop = load("angle1_population.json")
    n3 = load("angle1_n3_result.json")
    legb = load("angle1_legb_result.json")

    population = pop["population"]
    pop_set = set(population)
    a_count = pop["leg_a_n"]
    c_count = pop["leg_c_n"]
    b_count = legb["leg_b_count"]

    print(f"Population: {len(population)} cycles")
    print(f"A (8080 live, own decoder, own audio):      {a_count}")
    print(f"B (jt9 on 8080's own audio):                 {b_count}")
    print(f"C (WSJT-X live, own decoder, own audio):     {c_count}")

    decoder_attrib = b_count - a_count
    capture_attrib = c_count - b_count
    total_deficit = c_count - a_count
    f_dec = ac.ratio_of_sums([decoder_attrib], [total_deficit]) if total_deficit != 0 else float("nan")
    # ratio_of_sums treats an empty/zero-sum denominator as NaN already; make the ROW-0/
    # ROW-5 non-finite guard explicit here regardless of how ratio_of_sums got there.
    if total_deficit == 0:
        f_dec = float("nan")

    print(f"decoder-attributable (B-A):  {decoder_attrib}")
    print(f"capture-attributable (C-B):  {capture_attrib}")
    print(f"total deficit (C-A):         {total_deficit}")
    print(f"F_dec = (B-A)/(C-A) = {f_dec!r}")

    row, verdict = evaluate_rows(f_dec, b_count, a_count)
    print(f"ROW {row}: {verdict}")

    # Mandatory-null summary (N1/N2 from step 1, N3/N4 from steps 2-3).
    n1_pass = pop["n1_recall"] == 1.0
    n2_pass = all(pop[k]["verdict"] == "PASS" for k in ("gate_a", "gate_c", "gate_population"))
    n3_pass = n3["n3_verdict"] == "PASS"
    n4_pass = n3["n4_verdict"] == "PASS" and legb["n4_verdict"] == "PASS"
    any_null_failed = not (n1_pass and n2_pass and n3_pass and n4_pass)
    print(f"N1 {'PASS' if n1_pass else 'VOID'}, N2 {'PASS' if n2_pass else 'VOID'}, "
          f"N3 {'PASS' if n3_pass else 'VOID'}, N4 {'PASS' if n4_pass else 'VOID'}")
    if any_null_failed:
        print("*** ARM VOID: at least one mandatory null failed. F_dec/ROW above is reported for the record, not as a usable verdict. ***")

    # --- AP-eligible sensitivity split (section 6) ---
    owsfz_rows = ac.parse_all_txt(OWSFZ_ALL_TXT)
    wsjtx_rows = ac.parse_all_txt(WSJTX_ALL_TXT)
    a_rows = [r for r in owsfz_rows if r["ts"] in pop_set]
    c_rows = [r for r in wsjtx_rows if r["ts"] in pop_set]
    b_rows = legb["jt9_rows"]

    a_keys = {(r["ts"], ac.normalize_hash_tokens(r["message"])) for r in a_rows}
    b_keys = {(r["ts"], ac.normalize_hash_tokens(r["message"])) for r in b_rows}

    b_by_ts: dict[str, list[list[str]]] = {}
    for r in b_rows:
        b_by_ts.setdefault(r["ts"], []).append(r["message"].split())

    def is_ap_eligible(c_row) -> bool:
        key = (c_row["ts"], ac.normalize_hash_tokens(c_row["message"]))
        if key in b_keys:
            return False  # already matched into B verbatim -- not a C-only decode at all
        c_tok = c_row["message"].split()
        for b_tok in b_by_ts.get(c_row["ts"], []):
            if len(b_tok) != len(c_tok):
                continue
            if not any(t == "<...>" for t in b_tok):
                continue
            if all(bt == ct or bt == "<...>" for bt, ct in zip(b_tok, c_tok)):
                return True
        return False

    ap_eligible_c = [r for r in c_rows if is_ap_eligible(r)]
    n_ap = len(ap_eligible_c)
    print(f"AP-eligible C decodes (hash-resolution-only difference vs a same-ts B row): {n_ap}")

    c_count_noap = c_count - n_ap
    total_deficit_noap = c_count_noap - a_count
    f_dec_noap = float("nan") if total_deficit_noap == 0 else decoder_attrib / total_deficit_noap
    print(f"C excluding AP-eligible: {c_count_noap}")
    print(f"total deficit excluding AP-eligible (C_noAP - A): {total_deficit_noap}")
    print(f"F_dec excluding AP-eligible: {f_dec_noap!r}")
    if math.isfinite(f_dec) and math.isfinite(f_dec_noap):
        delta_points = (f_dec_noap - f_dec) * 100
        print(f"delta vs headline F_dec: {delta_points:+.1f} points "
              f"({'>10pt -- AP is a named sub-mechanism' if abs(delta_points) > 10 else '<=10pt'})")

    out = {
        "a_count": a_count, "b_count": b_count, "c_count": c_count,
        "decoder_attributable": decoder_attrib, "capture_attributable": capture_attrib,
        "total_deficit": total_deficit, "f_dec": f_dec, "row": row, "verdict": verdict,
        "n1_pass": n1_pass, "n2_pass": n2_pass, "n3_pass": n3_pass, "n4_pass": n4_pass,
        "any_null_failed": any_null_failed,
        "n_ap_eligible": n_ap, "c_count_noap": c_count_noap,
        "total_deficit_noap": total_deficit_noap, "f_dec_noap": f_dec_noap,
    }
    with open(os.path.join(WORK, "angle1_fdec_result.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {os.path.join(WORK, 'angle1_fdec_result.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
