#!/usr/bin/env python3
"""OSD-FA-A Amendment 1, Part 0 -- compare the three legs and apply Sec.1.3's rows.

Loads S1/S2/C JSON (artefacts/, gitignored) written by part0_runner.py, diffs them per slot,
per field, mechanically (never asserts byte-identity -- spec Sec.1.2), and prints/writes the
row verdict per Sec.1.3 (first match wins, predicates as code, HK-021(r)).

Per-slot classification, since a slot can hold >1 decode and decode ORDER is not itself
meaningful: decodes within a slot are paired across legs by (freq_hz, dt_s) -- the two fields
least likely to depend on session-table history -- sorted ascending; snr and message are then
compared on the paired records. A count mismatch (different number of decodes) is its own
category and is never paired. This is a disclosed methodological choice (spec Sec.8/HK-021(r)):
it matters only for the rare multi-decode slot (population is ~0.11 decodes/slot on average).

Output: counts and structured diff categories ONLY. Never prints or writes message text --
NFR-021 (spec Sec.7): this population is noise-only/synthetic but the ROW 0r noise CSV carried
361 callsign-shaped tokens, so it is scanned, not assumed clean, same as everywhere else in
this arm.

Usage:
    python part0_compare.py <s1.json> <s2.json> <c.json> <before_csv> <after_csv> <out_report_md>
"""
from __future__ import annotations

import csv
import json
import sys


def load_leg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def slot_map(leg: dict) -> dict:
    return {(s["part"], s["trial"], s["seed"]): s for s in leg["slots"]}


def classify(a_decodes: list, b_decodes: list) -> str:
    """Returns one of: 'identical', 'count_diff', 'numeric_diff', 'text_diff'."""
    if len(a_decodes) != len(b_decodes):
        return "count_diff"
    if len(a_decodes) == 0:
        return "identical"
    a_sorted = sorted(a_decodes, key=lambda r: (r["f"], r["dt"]))
    b_sorted = sorted(b_decodes, key=lambda r: (r["f"], r["dt"]))
    numeric_diff = False
    text_diff = False
    for ra, rb in zip(a_sorted, b_sorted):
        if ra["f"] != rb["f"] or ra["dt"] != rb["dt"] or ra["snr"] != rb["snr"]:
            numeric_diff = True
        if ra["m"] != rb["m"]:
            text_diff = True
    if numeric_diff:
        return "numeric_diff"
    if text_diff:
        return "text_diff"
    return "identical"


def diff_legs(leg_a: dict, leg_b: dict) -> dict:
    ma, mb = slot_map(leg_a), slot_map(leg_b)
    keys_a, keys_b = set(ma), set(mb)
    pop_mismatch = keys_a != keys_b
    cats = {"identical": 0, "count_diff": 0, "numeric_diff": 0, "text_diff": 0}
    differing_keys = {"count_diff": [], "numeric_diff": [], "text_diff": []}
    for key in sorted(keys_a & keys_b):
        sa, sb = ma[key], mb[key]
        if sa["av"] != sb["av"]:
            cats["numeric_diff"] += 1
            differing_keys["numeric_diff"].append(key)
            continue
        cat = classify(sa["decodes"], sb["decodes"])
        cats[cat] += 1
        if cat != "identical":
            differing_keys[cat].append(key)
    return {
        "pop_mismatch": pop_mismatch,
        "only_in_a": len(keys_a - keys_b),
        "only_in_b": len(keys_b - keys_a),
        "n_common": len(keys_a & keys_b),
        "cats": cats,
        "differing_keys": differing_keys,
    }


def lt_count_csv(path: str) -> tuple[int, int]:
    n = tot = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tot += 1
            if "<...>" in row["message"]:
                n += 1
    return n, tot


def main() -> int:
    s1_path, s2_path, c_path, before_csv, after_csv, out_path = sys.argv[1:7]

    s1 = load_leg(s1_path)
    s2 = load_leg(s2_path)
    c = load_leg(c_path)

    lines = []

    def log(msg=""):
        print(msg)
        lines.append(msg)

    log("# OSD-FA-A Amendment 1, Part 0 -- result")
    log()
    log(f"S1: dll={s1['dll_path']} sha256={s1['dll_sha256']} shim={s1['shim_version']} "
        f"n_files={s1['n_files']} wall_s={s1['total_wall_s']:.1f} decodes={s1['n_decodes']} "
        f"av_slots={s1['n_av_slots']} lt_ellipsis={s1['n_lt_ellipsis_decodes']}")
    log(f"S2: dll={s2['dll_path']} sha256={s2['dll_sha256']} shim={s2['shim_version']} "
        f"n_files={s2['n_files']} wall_s={s2['total_wall_s']:.1f} decodes={s2['n_decodes']} "
        f"av_slots={s2['n_av_slots']} lt_ellipsis={s2['n_lt_ellipsis_decodes']}")
    log(f"C:  dll={c['dll_path']} sha256={c['dll_sha256']} shim={c['shim_version']} "
        f"n_files={c['n_files']} wall_s={c['total_wall_s']:.1f} decodes={c['n_decodes']} "
        f"av_slots={c['n_av_slots']} lt_ellipsis={c['n_lt_ellipsis_decodes']}")
    log()

    # P0-0a -- already enforced IN-RUN by part0_runner.py (ExtractLLRs raises on mismatch
    # before any WAV is touched); re-assert here as a second, independent check.
    pins = {
        "S1": (s1, "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c", 20260050),
        "S2": (s2, "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c", 20260050),
        "C": (c, "ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e", 20260049),
    }
    p0_0a_fail = []
    for label, (leg, sha, ver) in pins.items():
        if leg["dll_sha256"] != sha or leg["shim_version"] != ver:
            p0_0a_fail.append(label)
    if p0_0a_fail:
        log(f"P0-0a FIRES -- VOID. Pin mismatch on: {p0_0a_fail}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return 1
    log("P0-0a clear -- all three legs' loaded DLL SHA/shim match their pin.")

    # P0-0b -- population mismatch.
    if s1["n_files"] != 4000 or s2["n_files"] != 4000 or c["n_files"] != 4000:
        log(f"P0-0b FIRES -- VOID. n_files: S1={s1['n_files']} S2={s2['n_files']} C={c['n_files']}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return 1
    log("P0-0b clear -- all three legs processed exactly 4,000 slots.")
    log()

    # P0-R1 -- S1 vs S2 (same binary, two fresh processes).
    d_s1s2 = diff_legs(s1, s2)
    log("## S1 vs S2 (determinism check, same binary)")
    log(f"population match: {not d_s1s2['pop_mismatch']} (only_in_S1={d_s1s2['only_in_a']} "
        f"only_in_S2={d_s1s2['only_in_b']} common={d_s1s2['n_common']})")
    log(f"cats: {d_s1s2['cats']}")
    r1_fires = d_s1s2["pop_mismatch"] or any(
        v > 0 for k, v in d_s1s2["cats"].items() if k != "identical")
    log(f"P0-R1 FIRES = {r1_fires}")
    log()

    if r1_fires:
        log("P0-R1 FIRES -- STOP. The harness is not deterministic on one binary; S1 vs C "
            "cannot be read. Differing slot keys (part,trial,seed) by category:")
        for cat, keys in d_s1s2["differing_keys"].items():
            log(f"  {cat}: {len(keys)} slots, first 10: {keys[:10]}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return 0

    # P0-1/2/3 -- S1 vs C.
    d_s1c = diff_legs(s1, c)
    log("## S1 vs C (the counter build vs the pre-change control)")
    log(f"population match: {not d_s1c['pop_mismatch']} (only_in_S1={d_s1c['only_in_a']} "
        f"only_in_C={d_s1c['only_in_b']} common={d_s1c['n_common']})")
    log(f"cats: {d_s1c['cats']}")

    if d_s1c["pop_mismatch"] or d_s1c["cats"]["count_diff"] > 0 or d_s1c["cats"]["numeric_diff"] > 0:
        log("P0-2 FIRES -- the build perturbs decoding (count and/or freq/dt/snr differs).")
        row = "P0-2"
    elif d_s1c["cats"]["text_diff"] > 0:
        log("P0-3 FIRES -- counts and numerics identical; message text differs on "
            f"{d_s1c['cats']['text_diff']} slot(s). Reproduces ROW 0r within one harness.")
        row = "P0-3"
    else:
        log("P0-1 FIRES -- zero differences in every field on every slot.")
        row = "P0-1"
    log(f"\nVERDICT: {row}")
    log()

    if d_s1c["cats"]["text_diff"] > 0:
        log("First 10 text-only-differing slot keys (part,trial,seed):")
        log(f"  {d_s1c['differing_keys']['text_diff'][:10]}")
    log()

    # Descriptive: <...> counts per leg vs the two committed CSVs.
    log("## Descriptive: <...> rendering counts")
    before_lt, before_tot = lt_count_csv(before_csv)
    after_lt, after_tot = lt_count_csv(after_csv)
    log(f"committed 'before' CSV ({before_csv}): decodes={before_tot} lt_ellipsis={before_lt}")
    log(f"committed 'after'  CSV ({after_csv}): decodes={after_tot} lt_ellipsis={after_lt}")
    log(f"S1 (this run): decodes={s1['n_decodes']} lt_ellipsis={s1['n_lt_ellipsis_decodes']}")
    log(f"S2 (this run): decodes={s2['n_decodes']} lt_ellipsis={s2['n_lt_ellipsis_decodes']}")
    log(f"C  (this run): decodes={c['n_decodes']} lt_ellipsis={c['n_lt_ellipsis_decodes']}")
    log()
    log("## Descriptive: wall time per leg (sequential, not concurrent)")
    log(f"S1: {s1['total_wall_s']:.1f}s  S2: {s2['total_wall_s']:.1f}s  C: {c['total_wall_s']:.1f}s")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
