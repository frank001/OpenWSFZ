#!/usr/bin/env python3
"""AO1 Part C -- recall cost at matched SNR (spec Sec.7), run standalone per the
Architect's ruling that unblocked it.

Ruling: qa/rr-study/2026-08-19-1155-architect-to-qa-ao1-row0f-ruling-part-c-unblocked.md
Spec:   qa/rr-study/2026-08-19-1058-architect-to-qa-prereg-ao1-production-time-origin-offset.md

WHY A SEPARATE SCRIPT, NOT A re-run of run_ao1.py's main(): ROW 3 and ROW 0f are
already reported (`results/ao1_report.json`, 2026-08-19 11:35Z) and are UNCHANGED
by this ruling -- the ruling struck only the clause in run_ao1.py:662 that made
Part C's eligibility depend on ROW 0f (`and not qcheck["fires"]`). Ruling Sec.2:
run_part_c() reads ONLY the reference population (snr/dt/recovered) -- it never
touches K, the 49-point grid, ft8_extract_llrs_at, or owsfz/wav/. So re-running R,
K, the sign test, or the extension-corpus sweeps would burn the "minutes not
hours" budget the ruling grants for zero additional evidence. This script runs
exactly the residual: re-verify the DLL pin (ruling Sec.5 step 1, an assertion,
not a Part C input), re-check ROW 0g fresh (ruling Sec.5 step 3: "re-evaluate, do
not inherit"), then call the SAME run_part_c() from run_ao1.py, unmodified.

WHAT THIS DOES NOT DO: it does not touch run_ao1.py's ROW 0f gating clause. That
clause is still live code (struck by the ruling, not yet edited out -- editing it
was unnecessary to satisfy the ruling's own instruction, which is "run Part C",
not "fix the harness"). Left as-is deliberately; a future full AO1 re-run would
still skip Part C at that line and would need the same manual override this
script performs. Flagged here so nobody mistakes this script's existence for that
line having been fixed.

NFR-021: reference population rows carry no message text (ao1_common.
build_reference_population drops it before returning). Every emitted file is
grepped for "message" after writing, per standing practice.

No src/, no Developer session, no DLL rebuild, no capture run -- HK-011 not engaged.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH, DEFAULT_DLL_SHA256, EXPECTED_SHIM_VERSION  # noqa: E402

from ao1_common import PRIMARY_CORPUS, build_matched_pairs, build_reference_population  # noqa: E402
from run_ao1 import ROW_0G_MAX_FRAC, run_part_c  # noqa: E402 -- run_part_c() UNMODIFIED


def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("AO1 PART C -- standalone run per 2026-08-19 11:55Z ruling")
    log("=" * 90)
    log("Ruling: qa/rr-study/2026-08-19-1155-architect-to-qa-ao1-row0f-ruling-part-c-unblocked.md")
    log("Prior result this amends: results/ao1_report.json (2026-08-19 11:35Z),")
    log("  final_row=3, row_0f.fires=true, part_c.evaluated=false (WITHHELD)")
    log("")
    log("MANDATORY DISCLOSURES (ruling Sec.6 -- must accompany every citation of the number below):")
    log("  1. ROW 0f FIRED. Part C runs because L is independent of K, NOT because the")
    log("     offset was shown constant. The offset has NOT been shown constant.")
    log("  2. The Part C gate (run_ao1.py:662's qcheck['fires'] clause) was amended post-hoc")
    log("     by the ruling above, after ROW 0f blocked it. Cite the ruling alongside this result.")
    log("  3. A C3 (null) reading is attenuation-suspect and may NOT be cited as 'no recall")
    log("     cost' -- drift (ruling Sec.2.1) can only push L toward zero. C1/C2/C4 do not")
    log("     carry this caveat.")

    bundle: dict = {
        "ruling": "qa/rr-study/2026-08-19-1155-architect-to-qa-ao1-row0f-ruling-part-c-unblocked.md",
        "amends": "results/ao1_report.json (2026-08-19 11:35Z, final_row=3, row_0f.fires=true)",
        "mandatory_disclosures": [
            "ROW 0f FIRED -- L is independent of K, offset NOT shown constant",
            "Part C gate amended post-hoc by the ruling above; cite it alongside this result",
            "A C3 (null) reading is attenuation-suspect, may NOT be cited as 'no recall cost'; "
            "C1/C2/C4 do not carry this caveat",
        ],
    }

    # -- ROW 0a re-verification, ruling Sec.5 step 1 -- an assertion, not a Part C
    # input (Part C never touches the DLL); done anyway because the ruling asks
    # for it explicitly before arming.
    log("\nRe-verifying DLL pin before arming (ruling Sec.5 step 1): %s" % DEFAULT_DLL_PATH)
    try:
        ex = ExtractLLRs(DEFAULT_DLL_PATH, verify=True, expected_sha256=DEFAULT_DLL_SHA256,
                          expected_shim_version=EXPECTED_SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a FIRES on re-verification: %s" % e)
        log("VALIDITY, STOP. Part C not run.")
        bundle["row_0a"] = {"fires": True, "error": str(e)}
        _write(out_dir, bundle, log_lines)
        return 2
    log("ROW 0a clear: DLL SHA256 asserted (%s...), shim version %d confirmed."
        % (DEFAULT_DLL_SHA256[:16], ex.version))
    bundle["row_0a"] = {"fires": False, "sha256_prefix": DEFAULT_DLL_SHA256[:16], "shim_version": ex.version}

    # -- ROW 0g re-check, ruling Sec.5 step 3: "re-evaluate, do not inherit" ----
    log("\n" + "=" * 90)
    log("ROW 0g -- reference SNR-field parseability (re-evaluated fresh, not inherited from 11:35Z)")
    log("=" * 90)
    _pairs, diag = build_matched_pairs(PRIMARY_CORPUS)
    frac_bad = diag["frac_ref_snr_unparseable"]
    row0g_fires = frac_bad > ROW_0G_MAX_FRAC
    log("frac_ref_snr_unparseable=%.2f%% (bound <=%.0f%%) -> %s"
        % (frac_bad * 100, ROW_0G_MAX_FRAC * 100, "FIRES" if row0g_fires else "clear"))
    bundle["row_0g"] = {"fires": row0g_fires, "frac_ref_snr_unparseable": frac_bad, "bound": ROW_0G_MAX_FRAC}
    if row0g_fires:
        log("ROW 0g FIRES: Part C's row below is DESCRIPTIVE ONLY -- gates nothing, licenses no "
            "C1/C2 consequence.")

    # -- Part C itself, run_ao1.run_part_c() UNMODIFIED -------------------------
    log("\nBuilding reference population on PRIMARY (%s) for Part C..." % PRIMARY_CORPUS)
    ref_population = build_reference_population(PRIMARY_CORPUS)
    log("  n=%d reference rows" % len(ref_population))

    part_c_result = run_part_c(ref_population, log)
    if row0g_fires and part_c_result.get("evaluated"):
        log("(Part C's row above is DESCRIPTIVE ONLY per ROW 0g -- SNR control is degraded on "
            ">5%% of the reference population; it does not license the C1/C2 consequences formally.)")
    bundle["part_c"] = part_c_result
    bundle["part_c_descriptive_only"] = row0g_fires

    log("\n" + "=" * 90)
    log("PART C ROW: %s" % part_c_result.get("row", "n/a"))
    log("=" * 90)

    _write(out_dir, bundle, log_lines)
    log("\nWrote results/ao1_part_c_report.json, results/ao1_part_c_run.log")
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "ao1_part_c_report.json"), bundle)
    with open(os.path.join(out_dir, "ao1_part_c_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
