#!/usr/bin/env python3
"""Smoke test for g2b_gate.py revision 5 (2026-08-12, fourth Architect review).

Re-run required by the Architect's fourth review
(`2026-08-12-2052-architect-to-qa-g2b-review-4.md`), which found two blocking
(D1, D2), one serious (D3), and two minor (D4, D5) findings. D2/D3 need a
producer-side change and a new aggregator, and D4/D5 are producer/pre-reg
fixes -- none of them land in this file. D1 does:

  D1  --burned-wav-dir matching ZERO legs was silent -- indistinguishable
      from the correct, common case (an un-burned corpus). Fixed:
      --burned-corpus {yes,no} is now REQUIRED, and a mismatch between the
      declaration and the legs' actual shared wav_dir is ROW 0 in EITHER
      direction. New coverage below: declared-burned-but-isn't,
      declared-unburned-but-is, and the "held-out floor applied to N leg(s)"
      line printed unconditionally.

Revision 4 (2026-08-12, third Architect review) found three blocking
(C1/C2/C5) plus one serious (C3, producer) and one moderate (C4, producer)
defects. C3/C4 land in g2_verification_replay.py, on its own branch, and are
covered by that file's own tests, not here. That revision:

  - Drops --is-widest-rung from every gate invocation (C5: the flag and the
    combination rule it drove are gone from g2b_gate.py).
  - Replaces the two ROW 3 (widest/non-widest) checks with one check against
    the repaired ROW 3 text -- evidence about the invoked rung only, family
    closure named as a separate cross-rung adjudication.
  - Every fixture leg now also carries `window`/`start_cycle` (C2: the gate
    now requires all three provenance fields -- wav_dir, window, start_cycle
    -- present and, across the three legs, IDENTICAL once normalised).
  - Adds a fixture reproducing C2(b) directly: three legs sharing every `ts`
    but with the widened leg drawn from a DIFFERENT corpus -- today this
    passes (caught only by luck, via the cycle-set gap between owsfz/wav and
    wsjt-x/wav); after the fix it must ROW 0.
  - Updates the B2 "missing wav_dir field" regression check for the new,
    three-field error message.

Keeps every revision-3 check otherwise unchanged: B1/B2/B3/B5/B6 coverage,
the REAL-ts-format fixtures (still real, still literal, per B2.4's lesson),
and the direct (non-subprocess) unit checks.

Exercises, by subprocess CLI invocation against fixture JSONs:
  - ROW 0, P2: same-binary, manifest-missing (widened), manifest-mismatch
    (widened), manifest-missing (BASELINE, B1), manifest-mismatch (BASELINE,
    B1), held-out violation on the burned corpus using REAL ts (B2), missing
    provenance fields (B2/C2 fail-closed), legs sharing every ts but drawn
    from different corpora (C2b, NEW)
  - ROW 0, P3: determinism failure
  - ROW 1 (ELIGIBLE): P1 fired (low-band only), P1 not fired with the high
    band ALSO clearing its own separate floor (B3 -- both ends adjudicated)
  - ROW 1: an unrelated, un-burned corpus using REAL ts that would trip a
    NAIVE global lexical floor is NOT blocked by --held-out-from (B2 -- this
    is the exact defect the fix closes, reproduced and shown fixed)
  - ROW 1: an AV cycle on one leg is excluded rather than counted as churn,
    and the row reads identically to the same fixture with the AV cycle
    simply absent (B5)
  - ROW 2, once failing on net churn alone and once failing on gross churn
    alone (A4 co-primary); once where g_low clears but g_high (adjudicated)
    does NOT -- scope narrows to low-band-only rather than failing the rung
    (B3's "own row path" for g_high)
  - ROW 3, mechanism underdelivers -- evidence about this rung only, no
    combination-rule flag involved (C5, REVISED from A3's widest/non-widest
    pair)
  - ROW 0d, reached for the NAMED reason A10 introduced (mechanism sub-bar AND
    gross churn ceiling exceeded together), with NO "catastrophic" wording
    anywhere in the output (B6)

Plus direct (non-subprocess) checks against the imported module:
  - A2: in_new_band_low is parameterised on f_min, not closed over a constant
  - A8: phys_by_cycle de-duplicates exact (freq, dt) repeats within a cycle
  - B5: av_cycles() identifies exactly the cycles marked av=True on a leg

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

# ── Real ts values, read ONCE off the actual corpora on disk (2026-08-12) via
# plain os.listdir -- not re-read at test time (a fresh checkout has no
# artefacts/ directory at all; it is blanket-gitignored), and not synthesised
# in an invented format (B2.4's lesson: the old fixture format never made
# contact with what the real producer emits). These are literal fixture data.
REAL_WAV_DIR_08_08 = "artefacts/20260808_live_run_0016-8080/wsjt-x/wav"  # C1: RULED
REAL_TS_08_08_EARLY = ["260808_000830", "260808_000845", "260808_000900",
                       "260808_000915", "260808_000930"]
REAL_HELD_OUT_FLOOR_08_08 = "260808_014215"  # the Architect's own cited floor
                                              # (250th in-window cycle);
                                              # independently reproduced by
                                              # g2_verification_replay.py's
                                              # select_files() against the
                                              # real corpus (see its own
                                              # extraction commit).
REAL_WAV_DIR_08_03 = "artefacts/20260803_live_run_1713/wsjt-x/wav"
REAL_TS_08_03_EARLY = ["260803_171345", "260803_171400", "260803_171415",
                       "260803_171430", "260803_171445"]
# NOTE: REAL_TS_08_03_EARLY is lexically LESS than REAL_HELD_OUT_FLOOR_08_08
# ("260803..." < "260808_014215") -- exactly the shape of B2's global-pooling
# defect. A leg from this corpus must NOT be rejected by a floor that names a
# completely different run.


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


# ── Fixture construction ─────────────────────────────────────────────────────

def make_cycle(ts, base_start, n_base, g_low, g_high, g_else, n_lost,
                f_min, f_max, dup=False):
    """Return (baseline_decodes, widened_decodes) for one cycle, both as the
    {"ts": ..., "av": False, "decodes": [{"f":.., "dt":..}, ...]} shape the
    gate reads.

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

    return ({"ts": ts, "av": False, "decodes": baseline_decodes},
            {"ts": ts, "av": False, "decodes": widened_decodes})


def make_legs(n_cycles, n_base, g_low, g_high, g_else, n_lost,
              f_min, f_max, sha_base="a" * 64, sha_wide="b" * 64,
              sha_rep=None, repeat_matches=True, first_ts_num=1000,
              wav_dir="SMOKETEST_WAV_DIR", window=("SMOKETEST_LO", "SMOKETEST_HI"),
              start_cycle=1, ts_list=None,
              av_cycle_idx=None, av_leg="wide", omit_provenance=False):
    """wav_dir/window/start_cycle are recorded on every leg (C2 needs all
    three present, and IDENTICAL across all three legs, to scope the held-out
    floor and to bind the legs to one corpus). ts_list, if given, overrides
    the synthesised '202608{n:06d}Z' timestamps with a caller-supplied list --
    pass one of the REAL_TS_* lists above to exercise the real format
    contract. av_cycle_idx/av_leg, if given, marks that cycle av=True (decodes
    cleared) on the named leg ("base"/"wide"/"rep"), for B5 coverage.
    omit_provenance drops wav_dir/window/start_cycle entirely, for the C2
    fail-closed regression check (simulating a producer older than the B4
    extraction, which recorded none of the three).
    """
    sha_rep = sha_rep or sha_base
    base_files, wide_files, rep_files = [], [], []
    for i in range(n_cycles):
        ts = ts_list[i] if ts_list else f"202608{first_ts_num + i:06d}Z"
        b, w = make_cycle(ts, 200, n_base, g_low, g_high, g_else, n_lost,
                           f_min, f_max)
        if repeat_matches:
            r = {"ts": ts, "av": False, "decodes": list(b["decodes"])}
        else:
            rep_decodes = list(b["decodes"]) + [{"f": 999999, "dt": 0.0}]
            r = {"ts": ts, "av": False, "decodes": rep_decodes}

        if av_cycle_idx is not None and i == av_cycle_idx:
            target = {"base": b, "wide": w, "rep": r}[av_leg]
            target["av"] = True
            target["decodes"] = []

        base_files.append(b)
        wide_files.append(w)
        rep_files.append(r)

    def leg(label, sha, files):
        out = {"label": label, "dll_sha256": sha, "shim_version": 20260039,
               "n_files": n_cycles, "per_file": files}
        if not omit_provenance:
            out["wav_dir"] = wav_dir
            out["window"] = list(window)
            out["start_cycle"] = start_cycle
        return out

    return (leg("base", sha_base, base_files),
            leg("widened", sha_wide, wide_files),
            leg("repeat", sha_rep, rep_files))


def run_gate(tmp, base, wide, rep, f_min, f_max, manifest,
             g_new_bar, g_high_bar, churn_net_bar, churn_gross_bar,
             held_out_from="0", burned_wav_dir="UNBURNED_WAV_DIR_SENTINEL",
             burned_corpus="no"):
    """burned_corpus (D1): the operator's required declaration of whether the
    legs ARE drawn from burned_wav_dir. Defaults to "no", which matches every
    pre-D1 fixture in this file (none of them use the sentinel/default
    wav_dir as their burned dir), so existing fixtures need no change. Callers
    exercising the burned-corpus path pass "yes" explicitly.
    """
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
           "--manifest", str(mpath),
           "--burned-corpus", burned_corpus,
           "--burned-wav-dir", burned_wav_dir,
           "--held-out-from", held_out_from,
           "--g-new-min-rate", str(g_new_bar),
           "--g-high-min-rate", str(g_high_bar),
           "--churn-net-min-rate", str(churn_net_bar),
           "--churn-gross-max-rate", str(churn_gross_bar)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def main():
    print("=" * 78)
    print("g2b_gate.py smoke test -- revision 4, 2026-08-12 (third review)")
    print("=" * 78)

    F_MIN, F_MAX = 140, 3030
    N_BASE = 1000
    G_HIGH_BAR_UNUSED = 0.0050   # never reached: every ROW0/ROW2/ROW3/ROW0d
                                 # fixture below has g_high=0, so P1 fires and
                                 # the high end is never adjudicated -- the
                                 # value is a placeholder, not a claim.
    GOOD_MANIFEST = {"b" * 64: {"f_min": F_MIN, "f_max": F_MAX},
                      "a" * 64: {"f_min": g2b.OLD_F_MIN, "f_max": g2b.OLD_F_MAX}}

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ── ROW 0 -- P2: baseline and widened are the SAME binary ───────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     sha_wide="a" * 64)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX,
                        {"a" * 64: {"f_min": F_MIN, "f_max": F_MAX}},
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 same-binary", "ROW 0 -- NO READ" in out
              and "SAME binary" in out)

        # ── ROW 0 -- P2: manifest missing the WIDENED SHA entirely ──────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX,
                        {"a" * 64: {"f_min": g2b.OLD_F_MIN, "f_max": g2b.OLD_F_MAX}},
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 widened manifest-missing (A7)", "ROW 0 -- NO READ" in out
              and "widened leg's SHA" in out
              and "is not in the pre-registered manifest" in out)

        # ── ROW 0 -- P2: widened SHA present but f_min mismatch ─────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        bad_manifest = {"b" * 64: {"f_min": 180, "f_max": F_MAX},
                         "a" * 64: {"f_min": g2b.OLD_F_MIN, "f_max": g2b.OLD_F_MAX}}
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, bad_manifest,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 widened manifest-mismatch (A7)", "ROW 0 -- NO READ" in out
              and "widened leg's SHA" in out and "was built for f_min=180" in out)

        # ── ROW 0 -- P2/B1: manifest missing the BASELINE SHA entirely ──────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX,
                        {"b" * 64: {"f_min": F_MIN, "f_max": F_MAX}},
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 baseline manifest-missing (B1)", "ROW 0 -- NO READ" in out
              and "baseline leg's SHA" in out
              and "is not in the pre-registered manifest" in out)

        # ── ROW 0 -- P2/B1: baseline SHA present but bound to the wrong band ─
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        bad_baseline_manifest = {"b" * 64: {"f_min": F_MIN, "f_max": F_MAX},
                                  "a" * 64: {"f_min": 140, "f_max": g2b.OLD_F_MAX}}
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX,
                        bad_baseline_manifest, 0.01, G_HIGH_BAR_UNUSED,
                        -0.0025, 0.02)
        check("ROW0 baseline manifest-mismatch (B1)", "ROW 0 -- NO READ" in out
              and "baseline leg's SHA" in out and "was built for f_min=140" in out)

        # ── ROW 0 -- B2: held-out violation, REAL ts, on the burned corpus ──
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_08,
                                     ts_list=REAL_TS_08_08_EARLY)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        held_out_from=REAL_HELD_OUT_FLOOR_08_08,
                        burned_wav_dir=REAL_WAV_DIR_08_08, burned_corpus="yes")
        check("ROW0 held-out violation, burned corpus, REAL ts (B2)",
              "ROW 0 -- NO READ" in out and "burned leg must not be read" in out, out)
        check("D1: held-out floor applied to all 3 legs (declared burned, is burned)",
              "held-out floor applied to 3 leg(s)" in out, out)

        # ── ROW 1 -- B2: an UNRELATED corpus using REAL ts that would trip a
        # naive global lexical floor is NOT blocked -- the exact defect fixed.
        # burned_corpus defaults to "no" here, correctly: these legs are NOT
        # drawn from --burned-wav-dir.
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_03,
                                     ts_list=REAL_TS_08_03_EARLY)
        assert min(REAL_TS_08_03_EARLY) <= REAL_HELD_OUT_FLOOR_08_08, (
            "fixture no longer reproduces the global-pooling shape B2 fixes")
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        held_out_from=REAL_HELD_OUT_FLOOR_08_08,
                        burned_wav_dir=REAL_WAV_DIR_08_08)
        check("ROW1 unrelated corpus NOT blocked by unrelated floor (B2)",
              "ROW 1 -- ELIGIBLE" in out and "burned leg must not be read" not in out, out)
        check("D1: held-out floor applied to 0 legs (correctly un-burned)",
              "held-out floor applied to 0 leg(s)" in out, out)

        # ── ROW 0 -- D1: operator declares --burned-corpus yes, but the legs
        # are NOT drawn from --burned-wav-dir (a typo/stale-path stand-in).
        # Pre-D1 this was silent: every leg `continue`d, "P2 legs ok" printed,
        # and the held-out floor was never applied. Now it is ROW 0.
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_03,
                                     ts_list=REAL_TS_08_03_EARLY)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        held_out_from=REAL_HELD_OUT_FLOOR_08_08,
                        burned_wav_dir=REAL_WAV_DIR_08_08, burned_corpus="yes")
        check("ROW0 D1: declared burned but legs are not -- was silent, now ROW 0",
              "ROW 0 -- NO READ" in out
              and "--burned-corpus yes was declared, but the legs are drawn "
                  "from" in out
              and "the held-out floor was never applied" in out, out)
        check("D1: floor NOT applied when the declaration itself failed",
              "held-out floor applied to 0 leg(s)" in out, out)

        # ── ROW 0 -- D1: operator declares --burned-corpus no, but the legs
        # ARE drawn from --burned-wav-dir -- the operator handed the gate the
        # burned corpus while declaring it unburned. Also ROW 0.
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_08,
                                     ts_list=REAL_TS_08_08_EARLY)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        held_out_from=REAL_HELD_OUT_FLOOR_08_08,
                        burned_wav_dir=REAL_WAV_DIR_08_08, burned_corpus="no")
        check("ROW0 D1: declared unburned but legs are burned",
              "ROW 0 -- NO READ" in out
              and "--burned-corpus no was declared, but the legs are drawn "
                  "from the burned corpus" in out, out)

        # ── ROW 0 -- C2 fail-closed: a leg with no provenance fields at all ──
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     omit_provenance=True)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 missing wav_dir/window/start_cycle, fails closed (C2)",
              "ROW 0 -- NO READ" in out
              and "is missing wav_dir, window, start_cycle" in out, out)

        # ── ROW 0 -- C2(b): legs share EVERY ts but the widened leg is drawn
        # from a DIFFERENT corpus. Today this is caught only by luck (the
        # cycle-set gap between owsfz/wav and wsjt-x/wav); it must not depend
        # on luck -- provenance equality catches it directly.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir="CORPUS_A/wav",
                                     window=("CORPUS_A_LO", "CORPUS_A_HI"))
        wide["wav_dir"] = "CORPUS_B/wav"
        wide["window"] = ["CORPUS_B_LO", "CORPUS_B_HI"]
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 legs share every ts but differ in corpus (C2b)",
              "ROW 0 -- NO READ" in out
              and "do not share one corpus/slice" in out, out)

        # ── ROW 0 -- P3 fails: repeat leg differs from baseline ─────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     repeat_matches=False)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 P3 determinism fail", "ROW 0 -- NO READ" in out
              and "churn NOT identified" in out)

        # ── ROW 1 -- P1 FIRED (no high-band gains): low-band-only scope ─────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW1 eligible, P1 fired -> low-band-only scope (A1/A6)",
              "ROW 1 -- ELIGIBLE" in out and "LOW END ONLY -- P1 fired" in out, out)

        # ── ROW 1 -- P1 NOT fired AND g_high clears its own floor (B3) ──────
        # g_high=1/cycle, identical every cycle (zero variance) -> rate and its
        # 95% lower bound are both exactly 0.10%; bar set below that.
        base, wide, rep = make_legs(20, N_BASE, 15, 1, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, 0.0005, -0.0025, 0.02)
        check("ROW1 eligible, P1 not fired, high band clears its OWN floor (B3)",
              "ROW 1 -- ELIGIBLE" in out
              and "both ends adjudicated and both clear" in out, out)

        # ── ROW 2 -- B3: g_low clears, high end adjudicated but does NOT ────
        # clear ITS OWN floor -- scope narrows to low-band-only, does not fail
        # the rung outright (this used to be untestable: v2 pooled g_low+g_high
        # so a low-band pass with a high-band shortfall could never surface).
        base, wide, rep = make_legs(20, N_BASE, 15, 1, 2, 3, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, 0.0050, -0.0025, 0.02)  # 0.0050 > the 0.10% rate
        check("ROW1 eligible, high band adjudicated but under its OWN floor "
              "-> scope narrows, rung still passes (B3)",
              "ROW 1 -- ELIGIBLE" in out
              and "high end adjudicated but did not clear its own floor" in out, out)

        # ── ROW 1 -- B5: an AV cycle is EXCLUDED, not counted as churn ──────
        # Same composition as the plain ROW1/P1-fired case above, but with one
        # extra AV cycle on the widened leg carrying decode counts that WOULD,
        # if read literally, register as a large loss. If excluded correctly,
        # this must read identically (same G_new%, same churn%) to the
        # AV-free fixture.
        base_noav, wide_noav, rep_noav = make_legs(20, N_BASE, 15, 0, 2, 3,
                                                     F_MIN, F_MAX)
        out_noav = run_gate(tmp, base_noav, wide_noav, rep_noav, F_MIN, F_MAX,
                             GOOD_MANIFEST, 0.01, G_HIGH_BAR_UNUSED,
                             -0.0025, 0.02)
        base_av, wide_av, rep_av = make_legs(21, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                              av_cycle_idx=20, av_leg="wide")
        out_av = run_gate(tmp, base_av, wide_av, rep_av, F_MIN, F_MAX,
                           GOOD_MANIFEST, 0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)

        def g_new_line(out):
            return next(l for l in out.splitlines() if l.strip().startswith("G_new (low-band)"))

        check("ROW1 AV cycle excluded, identical G_new% to the AV-free fixture (B5)",
              "ROW 1 -- ELIGIBLE" in out_av
              and g_new_line(out_av) == g_new_line(out_noav),
              f"noav={out_noav!r} av={out_av!r}")
        check("B5: AV cycle count is reported (21st cycle, wide leg)",
              "AV cycles excluded from every rate (B5 fix): 1 cycle" in out_av, out_av)

        # ── ROW 2 -- mechanism ok, NET churn fails, gross still ok ──────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 10, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW2 net-churn-only failure (A4)",
              "ROW 2 -- MECHANISM CONFIRMED" in out
              and "net churn exceeds its floor" in out
              and "gross churn exceeds its ceiling" not in out, out)

        # ── ROW 2 -- mechanism ok, net ok, GROSS churn fails ─────────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 110, 100, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW2 gross-churn-only failure (A4)",
              "ROW 2 -- MECHANISM CONFIRMED" in out
              and "gross churn exceeds its ceiling" in out
              and "net churn exceeds its floor" not in out, out)

        # ── ROW 3 -- mechanism underdelivers -- evidence about this rung only
        # (C5: no --is-widest-rung flag any more; the combination rule that
        # closed the family on the widest rung alone is repealed -- family
        # closure is a separate cross-rung adjudication this row names but
        # cannot itself perform).
        base, wide, rep = make_legs(20, N_BASE, 2, 0, 1, 1, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW3 evidence about this rung only, no widest-rung flag (C5)",
              "ROW 3" in out
              and "evidence about THIS rung's width only" in out
              and "family closes only if NO rung reads ROW 1 or ROW 2" in out
              and "--is-widest-rung" not in out, out)

        # ── ROW 0d -- mechanism sub-bar AND gross churn ceiling exceeded ────
        base, wide, rep = make_legs(20, N_BASE, 2, 0, 300, 300, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0d reached for a named reason (A10)",
              "ROW 0d -- CATCH-ALL, reached for a named reason (A10)" in out, out)
        check("ROW0d: no 'catastrophic' tier claimed anywhere in the output (B6)",
              "catastrophic" not in out.lower(), out)

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

    av_leg = {"per_file": [{"ts": "t1", "av": False, "decodes": []},
                            {"ts": "t2", "av": True, "decodes": []},
                            {"ts": "t3", "decodes": []}]}  # no 'av' key at all
    check("B5: av_cycles() identifies exactly the cycles marked av=True",
          g2b.av_cycles(av_leg) == {"t2"})

    print()
    print("=" * 78)
    if FAILURES:
        print(f"SMOKE TEST FAILED -- {len(FAILURES)} check(s) did not hold:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("SMOKE TEST PASSED -- all rows, including B1/B2/B3/B5/B6/C2/C5 "
          "coverage and the real-ts-format fixtures, verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
