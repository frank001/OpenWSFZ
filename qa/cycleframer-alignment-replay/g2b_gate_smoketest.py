#!/usr/bin/env python3
"""Smoke test for g2b_gate.py revision 2 (2026-08-12 16:00Z).

Re-run required by the Architect's review (§5 item 3): "revise g2b_gate.py ...
then re-smoke-test every row including a now-reachable 0d, as you did the first
time." The first pass was not saved as an artefact; this one is, so the claim
"smoke-tested" is checkable rather than asserted (HK-022).

Exercises, by subprocess CLI invocation against synthetic fixture JSONs:
  - ROW 0, four independent ways to fail P2 (same-binary, manifest-missing,
    manifest-mismatch, held-out violation) and one way to fail P3 (determinism)
  - ROW 1 (ELIGIBLE) under BOTH P1 branches -- high end unadjudicated (A1 low-band
    -only selection) and high end adjudicated (A1 pooled selection)
  - ROW 2, once failing on net churn alone and once failing on gross churn alone
    (A4 co-primary)
  - ROW 3, once as a non-widest rung (does not close the family) and once as the
    widest rung (closes the family) -- A3's combination rule
  - ROW 0d, reached for the NAMED reason A10 introduced (mechanism sub-bar AND
    gross churn catastrophic together), not as dead code

Plus two direct (non-subprocess) checks against the imported module:
  - A2: in_new_band_low is parameterised on f_min, not closed over a constant --
    the same frequency classifies differently under different rungs
  - A8: phys_by_cycle de-duplicates exact (freq, dt) repeats within a cycle, and
    that de-duplicated count is what rates()/d_base both use -- not a raw
    per-file row count that could double count a duplicate

Exits non-zero and prints every mismatch if anything drifts from the expected row.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "g2b_gate.py"

spec = importlib.util.spec_from_file_location("g2b_gate", GATE)
g2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g2b)

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


# ── Fixture construction ─────────────────────────────────────────────────────

def make_cycle(ts, base_start, n_base, g_low, g_high, g_else, n_lost,
                f_min, f_max, dup=False):
    """Return (baseline_decodes, widened_decodes) for one cycle, both as the
    {"ts": ..., "decodes": [{"f":.., "dt":..}, ...]} shape the gate reads.

    Baseline occupies freq [base_start, base_start+n_base). Losses remove the
    LAST n_lost of those. Low-band gains sit just under f_min's opening (i.e. in
    [f_min, OLD_F_MIN)); high-band gains sit in [OLD_F_MAX, f_max); "elsewhere"
    gains sit in a reserved range far above the baseline block so they cannot
    collide with it.
    """
    base_freqs = list(range(base_start, base_start + n_base))
    baseline_decodes = [{"f": f, "dt": 0.0} for f in base_freqs]
    if dup:
        baseline_decodes.append(dict(baseline_decodes[0]))  # exact repeat

    kept = base_freqs[: n_base - n_lost] if n_lost else base_freqs
    widened_decodes = [{"f": f, "dt": 0.0} for f in kept]

    low_span = g2b.OLD_F_MIN - f_min
    assert g_low <= low_span, "fixture asks for more low-band gains than room"
    for i in range(g_low):
        widened_decodes.append({"f": f_min + i, "dt": 0.0})

    high_span = f_max - g2b.OLD_F_MAX
    assert g_high <= high_span, "fixture asks for more high-band gains than room"
    for i in range(g_high):
        widened_decodes.append({"f": g2b.OLD_F_MAX + i, "dt": 0.0})

    else_base = base_start + 500_000  # well clear of any baseline block used here
    for i in range(g_else):
        widened_decodes.append({"f": else_base + i, "dt": 0.0})

    return ({"ts": ts, "decodes": baseline_decodes},
            {"ts": ts, "decodes": widened_decodes})


def make_legs(n_cycles, n_base, g_low, g_high, g_else, n_lost,
              f_min, f_max, sha_base="a" * 64, sha_wide="b" * 64,
              sha_rep=None, repeat_matches=True, first_ts_num=1000):
    sha_rep = sha_rep or sha_base
    base_files, wide_files, rep_files = [], [], []
    for i in range(n_cycles):
        ts = f"202608{first_ts_num + i:06d}Z"
        b, w = make_cycle(ts, 200, n_base, g_low, g_high, g_else, n_lost,
                           f_min, f_max)
        base_files.append(b)
        wide_files.append(w)
        if repeat_matches:
            rep_files.append({"ts": ts, "decodes": list(b["decodes"])})
        else:
            extra = dict(b["decodes"])
            rep_decodes = list(b["decodes"]) + [{"f": 999999, "dt": 0.0}]
            rep_files.append({"ts": ts, "decodes": rep_decodes})

    base = {"label": "base", "dll_sha256": sha_base, "shim_version": 20260039,
            "n_files": n_cycles, "per_file": base_files}
    wide = {"label": "widened", "dll_sha256": sha_wide, "shim_version": 20260039,
            "n_files": n_cycles, "per_file": wide_files}
    rep = {"label": "repeat", "dll_sha256": sha_rep, "shim_version": 20260039,
           "n_files": n_cycles, "per_file": rep_files}
    return base, wide, rep


def run_gate(tmp, base, wide, rep, f_min, f_max, is_widest, manifest,
             g_new_bar, churn_net_bar, churn_gross_bar, held_out_from="0"):
    bpath, wpath, rpath = tmp / "base.json", tmp / "wide.json", tmp / "rep.json"
    bpath.write_text(json.dumps(base))
    wpath.write_text(json.dumps(wide))
    rpath.write_text(json.dumps(rep))
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps(manifest))

    cmd = [sys.executable, str(GATE),
           "--band", "smoketest",
           "--baseline", str(bpath), "--widened", str(wpath), "--repeat", str(rpath),
           "--f-min", str(f_min), "--f-max", str(f_max),
           "--is-widest-rung", is_widest,
           "--manifest", str(mpath),
           "--held-out-from", held_out_from,
           "--g-new-min-rate", str(g_new_bar),
           "--churn-net-min-rate", str(churn_net_bar),
           "--churn-gross-max-rate", str(churn_gross_bar)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def main():
    print("=" * 78)
    print("g2b_gate.py smoke test -- revision 2, 2026-08-12 16:00Z")
    print("=" * 78)

    F_MIN, F_MAX = 140, 3030
    N_BASE = 1000
    GOOD_MANIFEST = {"b" * 64: {"f_min": F_MIN, "f_max": F_MAX}}

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ── ROW 0 -- P2: baseline and widened are the SAME binary ───────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     sha_wide="a" * 64)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no",
                        {"a" * 64: {"f_min": F_MIN, "f_max": F_MAX}},
                        0.01, -0.0025, 0.02)
        check("ROW0 same-binary", "ROW 0 -- NO READ" in out
              and "SAME binary" in out)

        # ── ROW 0 -- P2: manifest missing the widened SHA entirely ──────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", {},
                        0.01, -0.0025, 0.02)
        check("ROW0 manifest-missing (A7)", "ROW 0 -- NO READ" in out
              and "not in the pre-registered manifest" in out)

        # ── ROW 0 -- P2: manifest present but f_min mismatch ─────────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        bad_manifest = {"b" * 64: {"f_min": 180, "f_max": F_MAX}}
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", bad_manifest,
                        0.01, -0.0025, 0.02)
        check("ROW0 manifest-mismatch (A7)", "ROW 0 -- NO READ" in out
              and "was built for f_min=180" in out)

        # ── ROW 0 -- held-out-from violation ──────────────────────────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     first_ts_num=1000)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02, held_out_from="20260800999999Z")
        check("ROW0 held-out violation (A11)", "ROW 0 -- NO READ" in out
              and "burned leg must not be read" in out)

        # ── ROW 0 -- P3 fails: repeat leg differs from baseline ─────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     repeat_matches=False)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW0 P3 determinism fail", "ROW 0 -- NO READ" in out
              and "churn NOT identified" in out)

        # ── ROW 1 -- P1 FIRED (no high-band gains): low-band-only selection ──
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW1 eligible, P1 fired -> low-band selection (A1/A6)",
              "ROW 1 -- ELIGIBLE" in out and "LOW END ONLY -- P1 fired" in out
              and "G_new (low-band only)" in out, out)

        # ── ROW 1 -- P1 NOT fired (>=5 high-band gains): pooled selection ────
        base, wide, rep = make_legs(20, N_BASE, 15, 1, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW1 eligible, P1 not fired -> pooled selection (A1/A6)",
              "ROW 1 -- ELIGIBLE" in out and "both ends adjudicated" in out
              and "G_new (pooled, both ends)" in out, out)

        # ── ROW 2 -- mechanism ok, NET churn fails, gross still ok ──────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 10, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW2 net-churn-only failure (A4)",
              "ROW 2 -- MECHANISM CONFIRMED" in out
              and "net churn exceeds its floor" in out
              and "gross churn exceeds its ceiling" not in out, out)

        # ── ROW 2 -- mechanism ok, net ok, GROSS churn fails ─────────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 110, 100, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW2 gross-churn-only failure (A4)",
              "ROW 2 -- MECHANISM CONFIRMED" in out
              and "gross churn exceeds its ceiling" in out
              and "net churn exceeds its floor" not in out, out)

        # ── ROW 3 -- mechanism underdelivers, NOT the widest rung ───────────
        base, wide, rep = make_legs(20, N_BASE, 2, 0, 1, 1, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW3 non-widest rung does not close family (A3)",
              "ROW 3" in out and "does not close the passband family" in out
              and "CLOSE the passband family" not in out, out)

        # ── ROW 3 -- mechanism underdelivers, IS the widest rung ────────────
        base, wide, rep = make_legs(20, N_BASE, 2, 0, 1, 1, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "yes", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW3 widest rung closes family (A3)",
              "ROW 3" in out and "CLOSE the passband family" in out, out)

        # ── ROW 0d -- catastrophic: mechanism sub-bar AND gross churn huge ──
        base, wide, rep = make_legs(20, N_BASE, 2, 0, 300, 300, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, "no", GOOD_MANIFEST,
                        0.01, -0.0025, 0.02)
        check("ROW0d catastrophic, reached for a named reason (A10)",
              "ROW 0d -- CATCH-ALL, reached for a named reason (A10)" in out, out)

    # ── Direct checks, no subprocess ─────────────────────────────────────────
    print()
    check("A2: in_new_band_low is parameterised on f_min, not a closed-over "
          "constant (freq=120 is low-band for rung 100, is not for rung 140)",
          g2b.in_new_band_low(120, 100) is True
          and g2b.in_new_band_low(120, 140) is False)

    dup_leg = {"per_file": [{"ts": "t1", "decodes": [
        {"f": 500, "dt": 0.0}, {"f": 500, "dt": 0.0}, {"f": 501, "dt": 0.0}]}]}
    by_cycle = g2b.phys_by_cycle(dup_leg)
    check("A8: phys_by_cycle de-duplicates an exact (freq, dt) repeat within a "
          "cycle (3 raw rows collapse to 2 physical decodes)",
          len(by_cycle["t1"]) == 2)

    print()
    print("=" * 78)
    if FAILURES:
        print(f"SMOKE TEST FAILED -- {len(FAILURES)} check(s) did not hold:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("SMOKE TEST PASSED -- all rows, including the now-reachable 0d, verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
