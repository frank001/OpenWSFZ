#!/usr/bin/env python3
"""Smoke test for g2b_gate.py revision 6 (2026-08-13, fifth Architect review
plus the Captain's two rulings on it).

REVISION 6 additions:
  J1  New coverage: an underpowered rung with a real effect (95% lower bound
      fails, 95% upper bound does not) now reads ROW_INDETERMINATE, not
      ROW 3; a zero-cycle (d_base=0) rung reads ROW_INDETERMINATE with the
      degenerate-bootstrap reason named explicitly. Needs a NEW fixture
      helper, make_legs_varied_low() -- make_legs()'s per-cycle composition
      is IDENTICAL across cycles by construction, which gives every
      bootstrap resample the same rate (zero variance) and can never
      produce the lower/upper SPLIT this finding is about.
  Captain's ruling (self-contained verdict) -- new coverage: a ROW_1
      verdict carries `rows`/`window`/`start_cycle`/`n_cycles`/`d_base`/
      `av_excluded_count`/`truncated_count`/`gate_sha256`/`bootstrap_n`/
      `bootstrap_seed`/the pre-J1 constants; `--verify-verdict` re-derives
      the row from those carried terms and matches on an untampered
      verdict (ROW_1, ROW_0, ROW_INDETERMINATE) and FAILS, naming the
      divergence, on a verdict whose `row` was tampered while its `rows`
      were left genuine -- the negative control proving the re-derivation
      checks the evidence, not the label.
  J4  --burned-wav-dir/--held-out-from removed from every fixture's CLI
      invocation; REAL_WAV_DIR_08_08/REAL_HELD_OUT_FLOOR_08_08 are now
      DEFINED FROM g2b.BURNED_CORPUS itself, per the Captain's explicit
      instruction not to add a test-only override flag -- a fixture that
      wants to be read as "the burned corpus" points its own leg wav_dir at
      the constant.

Everything below this point is REVISION 5 and earlier, unchanged in
substance (only the burned-corpus/held-out CLI plumbing described above
moved):

E1/E2 (the early-candidates memo,
`2026-08-12-2143-architect-to-qa-g2b-review-5-early-candidates.md`): the
verdict this gate emits (--emit-verdict) previously carried no corpus
identity and no binary provenance, so g2b_family.py -- the instrument that
combines three rungs into one conclusion -- could not tell whether the three
rungs shared one band/corpus or ran the same binaries. This file does not
gain new PRECONDITIONS or new ROWS for E1/E2 (no CLI argument changed); it
gains new coverage that the verdict's new fields (dll_sha256 per leg,
manifest_sha256, wav_dir, burned_corpus) are populated correctly -- present
and null-safe on ROW_0, present and real on every other row, and equal to
what was actually read/declared. g2b_family.py's OWN smoke test
(g2b_family_smoketest.py) is where the new E1/E2 REFUSAL conditions
themselves are exercised, since those checks live in that file.

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

import hashlib
import importlib.util
import json
import os
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
# J4 fix (Captain's ruling, fifth review): --burned-wav-dir/--held-out-from
# are gone from the CLI -- REAL_WAV_DIR_08_08/REAL_HELD_OUT_FLOOR_08_08 are
# now defined FROM g2b.BURNED_CORPUS itself (not merely equal to it by
# construction) so this file cannot silently drift from the module constant
# it is meant to exercise. A fixture that wants to be read as "the burned
# corpus" sets its leg wav_dir to REAL_WAV_DIR_08_08; the gate now compares
# that against BURNED_CORPUS internally rather than against a CLI argument.
REAL_WAV_DIR_08_08 = g2b.BURNED_CORPUS["wav_dir"]  # C1: RULED
REAL_TS_08_08_EARLY = ["260808_000830", "260808_000845", "260808_000900",
                       "260808_000915", "260808_000930"]
REAL_HELD_OUT_FLOOR_08_08 = g2b.BURNED_CORPUS["held_out_from"]  # the
                                              # Architect's own cited floor
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


# E1/E2 helpers -- compute the SAME values g2b_gate.py itself computes, so a
# verdict's dll_sha256/manifest_sha256/wav_dir can be checked for EQUALITY to
# something derived independently of the code under test, not merely for
# presence.

def expected_manifest_sha256(manifest_dict):
    """Mirrors manifest_file_sha256() in g2b_gate.py against the exact bytes
    run_gate() itself writes to disk (json.dumps(manifest), no separators
    argument, default encoding -- these manifest fixtures are pure ASCII, so
    the platform's default text encoding and utf-8 agree byte-for-byte)."""
    return hashlib.sha256(json.dumps(manifest_dict).encode("utf-8")).hexdigest()


def expected_wav_dir_norm(wav_dir):
    """Mirrors the normcase(realpath(...)) the gate applies to a leg's
    recorded wav_dir (D4/C2) -- realpath resolves a relative path against the
    CALLER's (the gate subprocess's) CWD, which subprocess.run inherits from
    this smoke test process, so computing it here the same way is valid."""
    return os.path.normcase(os.path.realpath(wav_dir))


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
              av_cycle_idx=None, av_leg="wide", omit_provenance=False,
              truncated_cycle_idx=None, truncated_leg="wide",
              omit_truncated_field=False):
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

    truncated_cycle_idx/truncated_leg (D3), if given, marks that cycle
    "truncated": True on the named leg -- decodes are left untouched (unlike
    av, a truncated cycle's own decodes are exactly what is in question, but
    the fixture does not need to simulate a real MAX_RESULTS-sized decode
    list to exercise the gate's P2 check, which only reads the flag).
    omit_truncated_field drops the "truncated" key entirely from every
    per_file entry, simulating a leg produced by a pre-D3
    g2_verification_replay.py, for the .get("truncated") fail-open-safely
    regression check.
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

        if not omit_truncated_field:
            b["truncated"] = w["truncated"] = r["truncated"] = False
        if truncated_cycle_idx is not None and i == truncated_cycle_idx:
            target = {"base": b, "wide": w, "rep": r}[truncated_leg]
            target["truncated"] = True

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


def make_legs_varied_low(g_low_per_cycle, n_base, f_min, f_max,
                          sha_base="a" * 64, sha_wide="b" * 64, sha_rep=None,
                          wav_dir="SMOKETEST_WAV_DIR",
                          window=("SMOKETEST_LO", "SMOKETEST_HI"), start_cycle=1):
    """J1 coverage needs genuine bootstrap VARIANCE across cycles -- make_legs
    above gives every cycle the IDENTICAL composition, so every bootstrap
    resample draws the same rate every time (see the B3 ROW1 fixture's own
    comment: "identical every cycle -> zero variance"), which can never
    produce a 95% lower/upper bound SPLIT wide enough to distinguish "clears"
    from "underpowered" from "genuinely absent". This helper instead takes
    a PER-CYCLE g_low count, so cycles differ and resampling has something to
    vary over -- the only way to construct an INDETERMINATE fixture at all.
    """
    sha_rep = sha_rep or sha_base
    base_files, wide_files, rep_files = [], [], []
    for i, g_low in enumerate(g_low_per_cycle):
        ts = f"202608{1000 + i:06d}Z"
        b, w = make_cycle(ts, 200, n_base, g_low, 0, 0, 0, f_min, f_max)
        r = {"ts": ts, "av": False, "decodes": list(b["decodes"])}
        b["truncated"] = w["truncated"] = r["truncated"] = False
        base_files.append(b)
        wide_files.append(w)
        rep_files.append(r)

    def leg(label, sha, files):
        return {"label": label, "dll_sha256": sha, "shim_version": 20260039,
                "n_files": len(files), "per_file": files,
                "wav_dir": wav_dir, "window": list(window),
                "start_cycle": start_cycle}

    return (leg("base", sha_base, base_files),
            leg("widened", sha_wide, wide_files),
            leg("repeat", sha_rep, rep_files))


def run_gate(tmp, base, wide, rep, f_min, f_max, manifest,
             g_new_bar, g_high_bar, churn_net_bar, churn_gross_bar,
             burned_corpus="no", emit_verdict=None):
    """burned_corpus (D1): the operator's required declaration of whether the
    legs ARE drawn from the pre-registered BURNED_CORPUS constant. Defaults
    to "no", which matches every fixture in this file that does not
    deliberately set its leg wav_dir to REAL_WAV_DIR_08_08, so existing
    fixtures need no change. Callers exercising the burned-corpus path pass
    "yes" explicitly and point their fixture's wav_dir at REAL_WAV_DIR_08_08.

    J4 fix (Captain's ruling): --burned-wav-dir/--held-out-from are GONE --
    the burned region is now the hard-coded BURNED_CORPUS constant in
    g2b_gate.py itself, isdir-checked against the real repo tree (this
    machine has the real artefacts/ directory, per the Captain's explicit
    instruction NOT to add a test-only override flag: "the correct fix is
    to set the FIXTURE's recorded leg wav_dir to the constant"). Only the
    operator's declaration (`--burned-corpus`) remains a CLI argument.

    emit_verdict (D2): path to pass as --emit-verdict, or None to omit the
    flag entirely (the pre-D2 default -- every existing fixture keeps
    behaving exactly as before).
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
           "--g-new-min-rate", str(g_new_bar),
           "--g-high-min-rate", str(g_high_bar),
           "--churn-net-min-rate", str(churn_net_bar),
           "--churn-gross-max-rate", str(churn_gross_bar)]
    if emit_verdict is not None:
        cmd += ["--emit-verdict", str(emit_verdict)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def main():
    print("=" * 78)
    print("g2b_gate.py smoke test -- revision 6 (fifth review + Captain's "
          "rulings)")
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
                        burned_corpus="yes")
        check("ROW0 held-out violation, burned corpus, REAL ts (B2)",
              "ROW 0 -- NO READ" in out and "burned leg must not be read" in out, out)
        check("D1: held-out floor applied to all 3 legs (declared burned, is burned)",
              "held-out floor applied to 3 leg(s)" in out, out)

        # ── ROW 1 -- B2: an UNRELATED corpus using REAL ts that would trip a
        # naive global lexical floor is NOT blocked -- the exact defect fixed.
        # burned_corpus defaults to "no" here, correctly: these legs are NOT
        # drawn from the BURNED_CORPUS constant.
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_03,
                                     ts_list=REAL_TS_08_03_EARLY)
        assert min(REAL_TS_08_03_EARLY) <= REAL_HELD_OUT_FLOOR_08_08, (
            "fixture no longer reproduces the global-pooling shape B2 fixes")
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW1 unrelated corpus NOT blocked by unrelated floor (B2)",
              "ROW 1 -- ELIGIBLE" in out and "burned leg must not be read" not in out, out)
        check("D1: held-out floor applied to 0 legs (correctly un-burned)",
              "held-out floor applied to 0 leg(s)" in out, out)

        # ── ROW 0 -- D1: operator declares --burned-corpus yes, but the legs
        # are NOT drawn from BURNED_CORPUS (a typo/stale-path stand-in).
        # Pre-D1 this was silent: every leg `continue`d, "P2 legs ok" printed,
        # and the held-out floor was never applied. Now it is ROW 0.
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_03,
                                     ts_list=REAL_TS_08_03_EARLY)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        burned_corpus="yes")
        check("ROW0 D1: declared burned but legs are not -- was silent, now ROW 0",
              "ROW 0 -- NO READ" in out
              and "--burned-corpus yes was declared, but the legs are drawn "
                  "from" in out
              and "the held-out floor was never applied" in out, out)
        check("D1: floor NOT applied when the declaration itself failed",
              "held-out floor applied to 0 leg(s)" in out, out)

        # ── ROW 0 -- D1: operator declares --burned-corpus no, but the legs
        # ARE drawn from BURNED_CORPUS -- the operator handed the gate the
        # burned corpus while declaring it unburned. Also ROW 0.
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_08,
                                     ts_list=REAL_TS_08_08_EARLY)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        burned_corpus="no")
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

        # ── ROW 0 -- D3: a truncated cycle on the WIDENED leg fails closed ───
        # (the leg most likely to grow, so most likely to hit MAX_RESULTS in
        # reality -- the exact censoring the old assert was guarding against,
        # now without crashing to do it).
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     truncated_cycle_idx=5, truncated_leg="wide")
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 D3: truncated cycle on widened leg -> ROW 0",
              "ROW 0 -- NO READ" in out
              and "widened leg has 1 truncated cycle(s)" in out, out)

        # ── ROW 0 -- D3: a truncated cycle on the BASELINE leg also fails
        # closed -- the check is per-leg, not widened-only.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     truncated_cycle_idx=0, truncated_leg="base")
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 D3: truncated cycle on baseline leg -> ROW 0 (per-leg, not widened-only)",
              "ROW 0 -- NO READ" in out
              and "baseline leg has 1 truncated cycle(s)" in out, out)

        # ── ROW 0 -- D3: a truncated cycle on the REPEAT leg also fails closed
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     truncated_cycle_idx=0, truncated_leg="rep")
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0 D3: truncated cycle on repeat leg -> ROW 0",
              "ROW 0 -- NO READ" in out
              and "repeat leg has 1 truncated cycle(s)" in out, out)

        # ── D3: a leg from a PRE-D3 producer (no "truncated" field at all)
        # must NOT be rejected -- .get("truncated") reads absence as "not
        # flagged truncated", not a KeyError, so every fixture and every real
        # leg produced before this fix keeps reading exactly as before.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     omit_truncated_field=True)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("D3: pre-D3 leg with no 'truncated' field at all -> unaffected, ROW 1",
              "ROW 1 -- ELIGIBLE" in out and "truncated cycle(s)" not in out, out)

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
        check("ROW3 (J1): the 95%% upper bound is now printed as CONFIRMING "
              "the absence, not merely the lower bound failing",
              "confirming this is a genuine, powered absence" in out, out)

        # ── ROW_INDETERMINATE (J1) -- underpowered: 8 cycles, 7 with NO
        # low-band gain and 1 carrying the maximum possible for this rung's
        # width (g_low=60, the full [140,200) span -- per_cycle_terms's own
        # assert forbids exceeding it). True rate 0.75%, bar 1%; before the
        # fix this read ROW 3 -- indistinguishable from a genuine absence.
        # Because ~34% of bootstrap resamples never draw the one
        # gain-carrying cycle at all, the 95% LOWER bound is 0.000% (fails
        # the bar); because ~66% of resamples draw it at least once, the
        # 95% UPPER bound is well above the bar -- exactly the split that
        # must now read ROW_INDETERMINATE, not ROW 3.
        base, wide, rep = make_legs_varied_low(
            [0, 0, 0, 0, 0, 0, 0, 60], N_BASE, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW_INDETERMINATE (J1): underpowered rung with a REAL effect "
              "no longer reads ROW 3",
              "INDETERMINATE -- NO READ" in out
              and "\n  ROW 3" not in out
              and "not evidence of absence (ROW 3)" in out
              and "not evidence of eligibility (ROW 1)" in out, out)

        # ── ROW_INDETERMINATE (J1) -- the degenerate d_base == 0 case: a
        # ZERO-cycle rung. bootstrap_bounds() over an empty rows list never
        # raises (rows[rng.randrange(0)] is never evaluated when the sample
        # size is 0) and returns a degenerate 0.0/0.0 bound that would
        # otherwise misread as a confident absence (ROW 3) -- this is the
        # exact case the Architect's own early-candidates memo got wrong
        # twice (§1 of the fifth review). Must read ROW_INDETERMINATE, with
        # the d_base=0 reason named explicitly, not the generic one.
        base, wide, rep = make_legs_varied_low([], N_BASE, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW_INDETERMINATE (J1): zero-cycle rung (d_base=0) reads "
              "INDETERMINATE, not ROW 3, with the d_base=0 reason named",
              "INDETERMINATE -- NO READ" in out
              and "d_base=0" in out
              and "could not have been measured at all" in out
              and "\n  ROW 3" not in out, out)

        # ── ROW 0d -- mechanism sub-bar AND gross churn ceiling exceeded ────
        base, wide, rep = make_legs(20, N_BASE, 2, 0, 300, 300, F_MIN, F_MAX)
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("ROW0d reached for a named reason (A10)",
              "ROW 0d -- CATCH-ALL, reached for a named reason (A10)" in out, out)
        check("ROW0d: no 'catastrophic' tier claimed anywhere in the output (B6)",
              "catastrophic" not in out.lower(), out)

        # ── D2: --emit-verdict on a ROW 1 (full read) ────────────────────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        vpath = tmp / "verdict_row1.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        emit_verdict=vpath)
        check("D2: --emit-verdict is a no-op on stdout otherwise (still ROW 1)",
              "ROW 1 -- ELIGIBLE" in out, out)
        v = json.loads(vpath.read_text()) if vpath.exists() else None
        check("D2: verdict file was written", v is not None, out)
        if v is not None:
            check("D2: verdict row/band/f_min/f_max correct",
                  v["row"] == "ROW_1" and v["band"] == "smoketest"
                  and v["f_min"] == F_MIN and v["f_max"] == F_MAX, v)
            check("D2: verdict rates/bounds present (a real read happened)",
                  v["rates"] is not None and v["bounds"] is not None
                  and set(v["rates"]) == {"g_low", "g_high", "churn_net",
                                           "churn_gross"}
                  # J1: bounds gains g_low_hi (the 95% UPPER bound) alongside
                  # the four pre-existing lower/upper bounds.
                  and set(v["bounds"]) == {"g_low", "g_low_hi", "g_high",
                                            "churn_net", "churn_gross"}, v)
            check("D2: verdict bars match what was invoked",
                  v["bars"] == {"g_new_min_rate": 0.01,
                                "g_high_min_rate": G_HIGH_BAR_UNUSED,
                                "churn_net_min_rate": -0.0025,
                                "churn_gross_max_rate": 0.02}, v)
            check("D2: verdict p1_fired and scope populated on a real read",
                  v["p1_fired"] is True and v["scope"], v)
            check("E2: verdict dll_sha256 matches the three legs' actual SHAs",
                  v["dll_sha256"] == {"baseline": "a" * 64, "widened": "b" * 64,
                                       "repeat": "a" * 64}, v)
            check("E2: verdict manifest_sha256 matches the manifest file "
                  "actually read",
                  v["manifest_sha256"] == expected_manifest_sha256(GOOD_MANIFEST), v)
            check("E1: verdict wav_dir matches the legs' shared (normalised) "
                  "corpus directory",
                  v["wav_dir"] == expected_wav_dir_norm("SMOKETEST_WAV_DIR"), v)
            check("E1: verdict burned_corpus matches what was declared "
                  "(default 'no')",
                  v["burned_corpus"] == "no", v)

        # ── D2: --emit-verdict on a ROW 0 (precondition failure, no read) ────
        # rates/bounds/scope/p1_fired must be None -- honestly reporting that
        # no read happened, not a fabricated zero -- while bars (CLI-known
        # regardless of any precondition) are still present.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     sha_wide="a" * 64)  # same-binary P2 failure
        vpath0 = tmp / "verdict_row0.json"
        row0_manifest = {"a" * 64: {"f_min": F_MIN, "f_max": F_MAX}}
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX,
                        row0_manifest,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        emit_verdict=vpath0)
        check("D2 setup: ROW 0 fixture still reads ROW 0", "ROW 0 -- NO READ" in out, out)
        v0 = json.loads(vpath0.read_text()) if vpath0.exists() else None
        check("D2: ROW 0 verdict has row=ROW_0, rates/bounds/scope/p1_fired "
              "None, bars still present",
              v0 is not None and v0["row"] == "ROW_0"
              and v0["rates"] is None and v0["bounds"] is None
              and v0["scope"] is None and v0["p1_fired"] is None
              and v0["bars"] == {"g_new_min_rate": 0.01,
                                  "g_high_min_rate": G_HIGH_BAR_UNUSED,
                                  "churn_net_min_rate": -0.0025,
                                  "churn_gross_max_rate": 0.02}, v0)
        check("E2: ROW 0 verdict STILL carries dll_sha256 (known before any "
              "precondition, same as bars) -- the same-binary SHA itself",
              v0 is not None
              and v0["dll_sha256"] == {"baseline": "a" * 64, "widened": "a" * 64,
                                        "repeat": "a" * 64}, v0)
        check("E2: ROW 0 verdict STILL carries manifest_sha256 (known before "
              "any precondition)",
              v0 is not None
              and v0["manifest_sha256"] == expected_manifest_sha256(row0_manifest), v0)
        check("E1: ROW 0 verdict wav_dir is non-null when the ROW 0 cause is "
              "UNRELATED to provenance -- the legs still share one corpus "
              "(same-binary P2 failure, not a corpus mismatch)",
              v0 is not None
              and v0["wav_dir"] == expected_wav_dir_norm("SMOKETEST_WAV_DIR"), v0)

        # ── E1: ROW 0 caused by a genuine PROVENANCE disagreement (C2b's
        # cross-corpus fixture) -- wav_dir must be null-safe (None), never a
        # stale or partial value, since legs_share_one_corpus is False here.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir="CORPUS_A/wav",
                                     window=("CORPUS_A_LO", "CORPUS_A_HI"))
        wide["wav_dir"] = "CORPUS_B/wav"
        wide["window"] = ["CORPUS_B_LO", "CORPUS_B_HI"]
        vpath0b = tmp / "verdict_row0_provenance.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        emit_verdict=vpath0b)
        check("E1 setup: cross-corpus fixture still reads ROW 0 (C2b)",
              "ROW 0 -- NO READ" in out, out)
        v0b = json.loads(vpath0b.read_text()) if vpath0b.exists() else None
        check("E1: ROW 0 verdict wav_dir is None when the legs genuinely "
              "disagree on corpus/slice -- null-safe, not a fabricated value",
              v0b is not None and v0b["wav_dir"] is None, v0b)

        # ── E2: manifest FILE does not exist at all -- manifest_sha256 must
        # be None, not a crash, and P2's own manifest-missing check must
        # still fire (the SHA lookup fails closed either way; this is only
        # checking the DIGEST field, a separate concern from A7/B1's binding
        # check).
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        vpath0c = tmp / "verdict_row0_nomanifest.json"
        missing_manifest_path = tmp / "does_not_exist_manifest.json"
        cmd = [sys.executable, str(GATE),
               "--band", "smoketest", "--baseline", str(tmp / "base.json"),
               "--widened", str(tmp / "wide.json"), "--repeat", str(tmp / "rep.json"),
               "--f-min", str(F_MIN), "--f-max", str(F_MAX),
               "--manifest", str(missing_manifest_path),
               "--burned-corpus", "no",
               "--g-new-min-rate", "0.01", "--g-high-min-rate", str(G_HIGH_BAR_UNUSED),
               "--churn-net-min-rate", "-0.0025", "--churn-gross-max-rate", "0.02",
               "--emit-verdict", str(vpath0c)]
        (tmp / "base.json").write_text(json.dumps(base))
        (tmp / "wide.json").write_text(json.dumps(wide))
        (tmp / "rep.json").write_text(json.dumps(rep))
        result = subprocess.run(cmd, capture_output=True, text=True)
        out = result.stdout + result.stderr
        check("E2 setup: missing manifest FILE still ROW 0s (A7, manifest "
              "load returns {} -> SHA lookup fails)",
              "ROW 0 -- NO READ" in out and "is not in the pre-registered "
              "manifest" in out, out)
        v0c = json.loads(vpath0c.read_text()) if vpath0c.exists() else None
        check("E2: manifest_sha256 is None when the manifest file itself "
              "does not exist -- no traceback, no fabricated digest",
              v0c is not None and v0c["manifest_sha256"] is None, v0c)

        # ── E1: --burned-corpus yes is echoed into the verdict verbatim ─────
        base, wide, rep = make_legs(5, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     wav_dir=REAL_WAV_DIR_08_08,
                                     ts_list=REAL_TS_08_08_EARLY)
        vpath_burned = tmp / "verdict_burned.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        burned_corpus="yes", emit_verdict=vpath_burned)
        check("E1 setup: burned corpus fixture still ROW 0s (held-out "
              "violation, unrelated to this check)",
              "ROW 0 -- NO READ" in out, out)
        vburned = json.loads(vpath_burned.read_text()) if vpath_burned.exists() else None
        check("E1: verdict burned_corpus echoes 'yes' verbatim",
              vburned is not None and vburned["burned_corpus"] == "yes", vburned)
        check("E1: verdict wav_dir reflects the legs' actual (burned) corpus",
              vburned is not None
              and vburned["wav_dir"] == expected_wav_dir_norm(REAL_WAV_DIR_08_08),
              vburned)

        # ── D2: no --emit-verdict given -- no file written, no crash ─────────
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        vpath_absent = tmp / "verdict_should_not_exist.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02)
        check("D2: --emit-verdict omitted -> no file written, gate unaffected",
              "ROW 1 -- ELIGIBLE" in out and not vpath_absent.exists(), out)

        # ── Captain's ruling §2 -- --verify-verdict re-derives a ROW_1
        # verdict's own row from ITS OWN carried rows/bars/constants and
        # asserts equality. This is the mechanism that makes "the verdict
        # must be sufficient to re-derive the row without the leg JSONs"
        # testable rather than merely asserted.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX)
        vpath_vv1 = tmp / "verdict_verify_row1.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        emit_verdict=vpath_vv1)
        check("verify-verdict setup: ROW_1 fixture emits a verdict",
              vpath_vv1.exists(), out)
        vv1 = json.loads(vpath_vv1.read_text())
        check("Captain's ruling (self-contained verdict): ROW_1 verdict carries `rows` (the "
              "evidence itself), n_cycles, d_base, gate_sha256, "
              "bootstrap_n/seed and the pre-J1/self-containment constants",
              vv1["rows"] is not None and len(vv1["rows"]) == 20
              and vv1["n_cycles"] == 20 and vv1["d_base"] == 20000
              and vv1["gate_sha256"] and len(vv1["gate_sha256"]) == 64
              and vv1["bootstrap_n"] == g2b.BOOTSTRAP_N
              and vv1["bootstrap_seed"] == g2b.BOOTSTRAP_SEED
              and vv1["min_high_band_observations"] == g2b.MIN_HIGH_BAND_OBSERVATIONS
              and vv1["old_f_min"] == g2b.OLD_F_MIN
              and vv1["old_f_max"] == g2b.OLD_F_MAX
              and vv1["av_excluded_count"] == 0 and vv1["truncated_count"] == 0
              and vv1["window"] == ["SMOKETEST_LO", "SMOKETEST_HI"]
              and vv1["start_cycle"] == 1, vv1)

        vv_result = subprocess.run(
            [sys.executable, str(GATE), "--verify-verdict", str(vpath_vv1)],
            capture_output=True, text=True)
        check("--verify-verdict OK on an untampered ROW_1 verdict, exit 0",
              vv_result.returncode == 0
              and "VERIFY-VERDICT OK" in vv_result.stdout
              and f"row {vv1['row']} re-derives identically" in vv_result.stdout,
              vv_result.stdout + vv_result.stderr)

        # ── --verify-verdict on a ROW_0 verdict: rows is null, nothing to
        # re-derive, and that itself is verified rather than treated as a
        # failure.
        base, wide, rep = make_legs(20, N_BASE, 15, 0, 2, 3, F_MIN, F_MAX,
                                     sha_wide="a" * 64)  # same-binary P2 failure
        vpath_vv0 = tmp / "verdict_verify_row0.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX,
                        {"a" * 64: {"f_min": F_MIN, "f_max": F_MAX}},
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        emit_verdict=vpath_vv0)
        vv0_result = subprocess.run(
            [sys.executable, str(GATE), "--verify-verdict", str(vpath_vv0)],
            capture_output=True, text=True)
        check("--verify-verdict OK on a ROW_0 verdict (rows correctly null, "
              "nothing to re-derive), exit 0",
              vv0_result.returncode == 0
              and "VERIFY-VERDICT OK" in vv0_result.stdout
              and "ROW_0" in vv0_result.stdout, vv0_result.stdout + vv0_result.stderr)

        # ── --verify-verdict FAILS on a TAMPERED verdict -- the negative
        # control proving the re-derivation actually checks something rather
        # than trivially agreeing with whatever `row` says. Tampering the
        # recorded row while leaving the carried `rows`/bars/constants
        # genuine must be caught: decide() re-derives from the EVIDENCE, not
        # from the label.
        tampered = dict(vv1)
        tampered["row"] = "ROW_3"  # was ROW_1; the underlying `rows` still says ROW_1
        vpath_tampered = tmp / "verdict_tampered.json"
        vpath_tampered.write_text(json.dumps(tampered))
        vvt_result = subprocess.run(
            [sys.executable, str(GATE), "--verify-verdict", str(vpath_tampered)],
            capture_output=True, text=True)
        check("--verify-verdict FAILS on a tampered row, exit non-zero, "
              "names the divergence",
              vvt_result.returncode != 0
              and "VERIFY-VERDICT FAIL" in vvt_result.stdout
              and "recorded row is 'ROW_3'" in vvt_result.stdout
              and "re-derived row" in vvt_result.stdout
              and "'ROW_1'" in vvt_result.stdout,
              vvt_result.stdout + vvt_result.stderr)

        # ── --verify-verdict re-derives a ROW_INDETERMINATE verdict too (J1) --
        # not merely ROW_1/ROW_0.
        base, wide, rep = make_legs_varied_low(
            [0, 0, 0, 0, 0, 0, 0, 60], N_BASE, F_MIN, F_MAX)
        vpath_vvi = tmp / "verdict_verify_indeterminate.json"
        out = run_gate(tmp, base, wide, rep, F_MIN, F_MAX, GOOD_MANIFEST,
                        0.01, G_HIGH_BAR_UNUSED, -0.0025, 0.02,
                        emit_verdict=vpath_vvi)
        check("verify-verdict setup: fixture reads ROW_INDETERMINATE",
              "INDETERMINATE -- NO READ" in out, out)
        vvi_result = subprocess.run(
            [sys.executable, str(GATE), "--verify-verdict", str(vpath_vvi)],
            capture_output=True, text=True)
        check("--verify-verdict OK on an untampered ROW_INDETERMINATE "
              "verdict, exit 0",
              vvi_result.returncode == 0
              and "VERIFY-VERDICT OK" in vvi_result.stdout
              and "row ROW_INDETERMINATE re-derives identically" in vvi_result.stdout,
              vvi_result.stdout + vvi_result.stderr)

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
    print("SMOKE TEST PASSED -- all rows including B1/B2/B3/B5/B6/C2/C5 "
          "coverage, the real-ts-format fixtures, the E1/E2 verdict field "
          "checks (dll_sha256, manifest_sha256, wav_dir, burned_corpus, "
          "including their null-safe ROW_0 cases), REVISION 6's "
          "ROW_INDETERMINATE coverage (J1, both the underpowered-real-effect "
          "and zero-cycle/d_base=0 cases), the self-contained-verdict fields "
          "and --verify-verdict re-derivation (including its tampered-row "
          "negative control), and BURNED_CORPUS as a hard-coded constant "
          "(J4), verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
