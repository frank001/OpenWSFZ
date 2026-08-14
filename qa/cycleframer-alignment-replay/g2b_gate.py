#!/usr/bin/env python3
"""G2(b) passband gate -- the MECHANICAL evaluator for the pre-registration at
qa/cycleframer-alignment-replay/2026-08-12-1608-qa-to-architect-prereg-g2b-passband-decomposed-v2.md

HK-021 requires a pre-registered check to be drafted by writing the code that
evaluates it. This IS that code, and it is written before any ladder rung is run.
It takes replay JSONs produced by g2_verification_replay.py and prints exactly one
ROW per rung. It draws no conclusion the rows do not license.

REVISION 2 (2026-08-12 16:08Z) -- rewritten against the Architect's twelve-finding
review (`2026-08-12-1545-architect-to-qa-g2b-prereg-review-and-fmin-ruling.md`).
Findings A1, A2, A4, A7, A8, A9, A10, A11, A12 are fixed here; A3, A5, A6 are
policy/derivation fixes and are documented in the revised pre-registration, with
the mechanical half of each (the combination-rule flag, the non-circular P1
observation rule, the CLI-supplied non-derived bars) landing in this file too.
A1 was ALSO formally refused under HK-025 before this revision was written -- see
the covering document. This file does not "arm" the refused version; it replaces
it.

REVISION 3 (2026-08-12, second Architect review, 19:24Z) -- against
`2026-08-12-1924-architect-to-qa-g2b-review-2-and-producer-ruling.md`'s four
blocking (B1-B4) and two serious (B5-B6) findings. B4 (the producer was off-tree
and unreviewed) is answered by extracting g2_verification_replay.py to its own
branch, not in this file. The rest:

  B1  The manifest previously bound only the WIDENED leg's SHA to its claimed
      band; nothing asserted the baseline was the [200,3000) reference build.
      Fixed: check_manifest_binding() is now called for baseline too (the
      repeat leg is covered transitively, since P2 already asserts its SHA
      equals the baseline's).
  B2  --held-out-from was a global lexical floor pooled across ALL legs from
      ANY corpus -- with a correct floor it silently ROW-0'd an un-burned
      4,614-cycle corpus; with a wrong-format floor it silently protected
      nothing. Fixed: the floor now applies ONLY to legs whose `wav_dir`
      (a field g2_verification_replay.py's extraction now records) matches
      the required --burned-wav-dir. A leg from any other corpus is never
      touched by it, in either direction.
  B3  The per-rung G_new floor was scaled to the low band's width but applied
      to a POOLED low+high metric, so a narrow rung could read ELIGIBLE on
      high-band noise alone while its own intended mechanism delivered
      nothing. Fixed: g_low is barred against its own floor ALWAYS (g_pooled
      and g_sel_fn are gone); g_high, when adjudicated (P1 not fired), gets
      its OWN separate --g-high-min-rate floor and decides only the SCOPE of
      the licensed consequence, never whether the rung passes at all.
  B5  AV cycles (native access violation, caught by the shim's SEH) were
      silently read as legitimate zero-decode cycles, letting a caught crash
      on one leg inflate churn on the other. Fixed: av_cycles() excludes any
      cycle where ANY of the three legs AV'd, uniformly, from every rate.
  B6  ROW 0d's "catastrophic" text described a severity tier the code did not
      implement -- it tests the identical gross-churn ceiling ROW 2 uses.
      Fixed: the word is removed; the row is described as what it is, both
      bars failing together (the Architect's second, no-new-parameter option).

Also fixed: a dangling pointer in this docstring (the pre-reg filename/time
cited "-1600-"/16:00Z; the actual document is "-1608-"/16:08Z -- corrected
above), and bootstrap_bound's four independent resampling loops collapsed into
one (bootstrap_bounds(), same seed, same per-draw samples, ~4x faster) -- the
Architect flagged this as worth doing before the ladder's 9 legs run.

  Preconditions (P1 observation rule aside, which changes the verdict rather
  than merely the printed scope -- see A1) are evaluated FIRST and can each
  change the verdict (HK-021(k)); rows are hard-thresholded, mutually
  exclusive, and read in strict order with an explicit ROW 0 and a reachable
  ROW 0d that fires for a named reason (A10), not as dead code.

REVISION 4 (2026-08-12, third Architect review, 20:15Z) -- against
`2026-08-12-2015-architect-to-qa-g2b-review-3-and-wav-dir-ruling.md`'s three
blocking (C1-C3... C1/C2/C5) plus one serious (C3) and one moderate (C4)
findings against the gate and its producer. The producer fixes (C3/C4) land in
g2_verification_replay.py, on its own branch, not here. This file:

  C1  The docstring's usage example named --burned-wav-dir as .../owsfz/wav.
      RULED: the 08-08 corpus for every leg of every rung is .../wsjt-x/wav
      (raw-WAV measurement, HK-026-valid; the two capture chains are within
      half a dB everywhere that matters, so the choice is not load-bearing and
      consistency with the burned leg and the rest of the programme decides
      it). Fixed here as a doc-only correction; the held-out remainder is
      2,279 cycles (2,529 in-window - 250 burned), corrected in the pre-reg.
  C2  wav_dir was compared as a raw path string (relative vs absolute, `/` vs
      `\\`, a trailing separator, or case all silently defeat a bare `!=`),
      and nothing bound the three legs to ONE corpus -- wsjt-x/wav's in-window
      ts set is a STRICT SUBSET of owsfz/wav's (2,529 shared keys over
      DIFFERENT audio), so a same-ts, different-corpus mix was caught today
      only by an accidental 12-file gap in the existing cycle-set check.
      Fixed: every wav_dir is normalised (normcase+realpath) before any
      comparison, and P2 now asserts baseline/widened/repeat share one
      identical (wav_dir, window, start_cycle) triple -- fields the B4
      extraction already records, which is what makes this checkable at all.
  C5  The A3 combination rule (my own review-1 recommendation, "family closes
      only if the WIDEST rung reads ROW 3") let the THINNEST-MARGIN rung close
      the whole family: raw WAV shows ~20 dB/40-60 Hz rolloff below 200 Hz, so
      the width-proportional bars scale faster than the opportunity, and rung
      100 -- structurally the thinnest margin of the three -- is also the
      widest rung. Fixed per the Architect's own repair: --is-widest-rung is
      REMOVED. ROW 3 is now evidence about that single rung's width only;
      family closure is a separate adjudication made after all three rungs
      have run, and closes only if NO rung reads ROW 1 or ROW 2. This gate,
      invoked once per rung, cannot itself perform that cross-rung
      adjudication -- it prints the fact needed for it and stops.

REVISION 5 (2026-08-12, fourth Architect review, 20:52Z) -- against
`2026-08-12-2052-architect-to-qa-g2b-review-4.md`'s two blocking (D1, D2)
findings, one serious (D3), and two minor (D4, D5). D4 is a producer-only
fix, landing on qa/g2b-verification-replay-extract, not here. D1, D2, D3's
gate half, and D5 do:

  D1  --burned-wav-dir matching ZERO legs was silent and indistinguishable
      from the correct, common case (an un-burned corpus, where zero legs
      SHOULD match) -- a typo, a stale path, or a different drive mapping
      made every leg's comparison `continue`, "P2 legs ok" printed, and the
      burned run's held-out floor was never applied. Three rounds of one
      shape: B2 protected nothing, C1 was B2's fix protecting nothing again,
      D1 is C1's fix protecting nothing a third time. Fixed: --burned-corpus
      {yes,no} is now REQUIRED. The operator pre-declares which case this run
      is; a mismatch between the declaration and the legs' actual shared
      wav_dir (which C2(b) already forces to be identical across all three
      legs, when provenance is otherwise consistent) is ROW 0 in EITHER
      direction, never a silent skip. The gate also now always prints
      "held-out floor applied to N leg(s)", so the artefact records that the
      floor ran rather than leaving its absence inferable only from an
      absent complaint.
  D2  The A3/C5 family-closure rule ("the family closes only if NO rung
      reads ROW 1 or ROW 2") was pre-registered prose with NO mechanism, and
      this gate emitted nothing to build one from -- it printed prose only
      and returned 0 on EVERY path including ROW 0, so a cross-rung
      adjudicator was not buildable without regexing English out of a
      console log (how the bar got softened once already, in
      g2_verification_report.py -- the finding that opened this whole
      review chain). Fixed: --emit-verdict PATH (optional) writes one JSON
      object -- band, f_min, f_max, row, scope, p1_fired, the four point
      rates and bootstrap bounds (null on ROW_0, where no read happened),
      and the four bars as invoked (always known, CLI-supplied). The
      companion aggregator is g2b_family.py, its own file: CLOSE only if
      all three rungs' verdicts read ROW_3, otherwise DO NOT CLOSE naming
      which read ROW_1/ROW_2, and REFUSE outright on fewer/more than three
      verdicts, any ROW_0/ROW_0d, or two verdicts sharing an f_min. It can
      only ever CLOSE the family -- it never recommends a rung; that choice
      stays the Captain's (pre-reg §4/§8, unchanged).
  D3  The `assert len(res) < P.MAX_RESULTS` the Architect ordered last round
      contradicted the C3 fix in the SAME producer file, on the SAME
      hazard: no checkpointing exists, so a mid-run crash discards every
      completed cycle -- exactly what C3 rejected, and `assert` is stripped
      under `python -O` besides. Fixed in the producer (own commit, own
      branch): a suspect cycle is now marked `"truncated": True` and the leg
      continues. This file's half: any leg carrying even one truncated
      cycle is now a P2 failure -- ROW 0, same fail-closed guarantee, no
      lost work. `.get("truncated")` throughout, so a leg produced by a
      pre-D3 g2_verification_replay.py (which never wrote the field) is
      read as "not flagged truncated", not a KeyError.
  D5  A review-3 instruction went uncarried-out because it was appended to
      a line the Architect marked done/verified rather than given its own
      marker -- process point acknowledged in review 4 (§6/§8): a marker
      that carries an instruction is still an instruction. The instruction
      itself: note WHY rep_churn_abs (P3's determinism check) may sum only
      g_else+lost and skip g_low/g_high -- it is complete only because
      `base` in that call is always the fixed-band [200,3000) BASELINE
      binary, which structurally cannot emit in the new bands, so g_low/
      g_high are necessarily zero there. The comment now sits at
      rep_churn_abs itself, warning against ever repurposing that call for
      a widened-vs-widened comparison without adding those columns back.

  E1  Sent early, out of band, ahead of the fifth review proper
      (`2026-08-12-2143-architect-to-qa-g2b-review-5-early-candidates.md`):
      g2b_family.py read `band`/`f_max` off each verdict, printed both, and
      tested neither -- and could not see the corpus at all, since the
      verdict carried none. The pre-reg's own §5 ladder runs three rungs x
      three bands, and 20m alone has two corpora, so three ROW_3 verdicts
      drawn from three DIFFERENT bands, or two DIFFERENT 20m corpora, would
      have printed CLOSE -- closing the passband family on a ladder that was
      never run. BLOCKING for the family adjudication, not for running a
      rung. Fixed here: every verdict now carries the legs' shared
      normalised wav_dir (null-safe on ROW_0, where provenance may be
      unconfirmed) and the --burned-corpus declaration (always known,
      CLI-supplied). g2b_family.py's half: refuse unless all three verdicts
      share one band, one f_max and one wav_dir.
  E2  SERIOUS, same memo. The verdict carried no `dll_sha256` and no
      manifest digest, so the family adjudicator -- the instrument that
      actually combines the three rungs -- could not tell whether they ran
      the same binaries, and the manifest is a mutable file with "never
      edit an existing entry" enforced by nothing (D2's fault, one file
      over, per the manifest's own _comment). Fixed here: every verdict now
      carries `dll_sha256` for all three legs (baseline/widened/repeat) and
      the manifest FILE's own SHA256 as read (manifest_file_sha256() below).
      g2b_family.py's half: refuse if the three rungs' baseline SHAs, or
      their manifest digests, are not identical. Widened SHAs are expected
      to differ across rungs and are deliberately NOT checked for equality
      -- the per-rung manifest binding (A7/B1) already covers them.
  E3  MINOR in code, a process point in the memo: g2b_family.py returned 0
      on CLOSE, DO NOT CLOSE and all six REFUSE paths alike -- the
      identical defect D2 raised against this gate's own exit code,
      reappearing inside the very instrument built to fix it. Fixed in
      g2b_family.py only: 0 = CLOSE, 1 = DO NOT CLOSE, 2 = REFUSE,
      documented in that file's own docstring and asserted in its smoke
      test. This gate's --emit-verdict remains the machine-readable channel
      here, per D2; this gate's own exit code is deliberately UNCHANGED.

REVISION 6 (2026-08-13, fifth Architect review, 15:03Z, plus the Captain's
two rulings on it, 15:17Z) -- against
`2026-08-13-1503-architect-to-qa-g2b-review-5.md`'s two blocking (J1, J2),
one serious (J3) and three minor (J4, J5, J6) findings, and
`2026-08-13-1517-architect-to-qa-g2b-captains-rulings-j4-and-self-contained-
verdict.md`'s two Captain's rulings on J4 and on the verdict's
self-containment. J2's family-side half (F7) and J5's family-side half
land in g2b_family.py, not here. This file:

  J1  ROW 3 fired whenever g_low's 95% LOWER bound failed to clear its bar
      -- guaranteed for ANY underpowered rung, indistinguishable from a
      genuine absence. Measured: an 8-cycle rung with the true low-band
      rate held at 2.5x its own bar still read ROW 3, identically to a
      400-cycle rung with a genuine 0.00% rate, and three such underpowered
      rungs CLOSEd the family. Fixed: bootstrap_bounds() now also computes
      g_low's 95% UPPER bound. ROW 3 requires that upper bound to fall
      BELOW the bar (a genuine, powered absence); if the lower bound fails
      but the upper bound does not, the read is ROW_INDETERMINATE -- new,
      refused by the family exactly like ROW_0/ROW_0d. A zero-cycle (or
      zero-baseline-decode) rung is INDETERMINATE by definition: a
      bootstrap over zero rows returns a degenerate zero-width CI pinned at
      0.0 (rows[rng.randrange(0)] is never evaluated when the sample size
      is 0, so no exception and no honest "no data" signal either) -- that
      is not evidence the true rate is confidently below the bar, it is the
      absence of any measurement at all, and is now caught by an explicit
      d_base > 0 guard, not by the bound comparison alone.
  Captain's ruling (verdict self-containment) -- absorbs J3: rather than
      add one more field per review round (five rounds have shown that
      approach cannot be enumerated by inspection), the verdict now carries
      EVERYTHING the row was computed from -- the per-cycle rows
      themselves, the corpus slice (window/start_cycle/n_cycles/d_base),
      the AV-excluded and truncated-cycle counts, every constant that
      entered the decision (BOOTSTRAP_N, BOOTSTRAP_SEED,
      MIN_HIGH_BAND_OBSERVATIONS, OLD_F_MIN, OLD_F_MAX), and gate_sha256
      (this file's own SHA256, E2's logic applied to the instrument rather
      than the DLL). The row-decision logic itself is extracted into
      decide(), a pure function of (rows, f_min, f_max, bars, constants),
      so a fresh read (main()) and a re-derivation from a verdict's own
      carried terms (--verify-verdict, new) run the IDENTICAL code path and
      cannot silently diverge. `g2b_gate.py --verify-verdict PATH` reads a
      verdict, re-derives its row via decide(), and asserts it equals the
      row recorded -- asserted in the smoke suite for every fixture that
      reaches a row. This certifies what the gate SAW, not what was TRUE;
      the instrument still cannot bound its own blind spot (HK-026), and
      --verify-verdict may only ever check a verdict against itself, never
      produce a row used as new evidence.
  J4  Captain's ruling: --burned-wav-dir and --held-out-from are REMOVED,
      not defaulted -- C1 already settled the burned corpus by measurement,
      and pinning the directory while leaving the floor operator-typed
      would repeat this chain's own B2->C1->D1 pattern one field over. Both
      become ONE pre-registered constant, BURNED_CORPUS, resolved against
      the REPO ROOT (never the CWD -- D4's hazard) and isdir-checked -> ROW
      0 if the resolved path does not exist (a fresh checkout has no
      artefacts/ at all). --burned-corpus {yes,no} stays required (D1's
      point): the operator still declares which case this run is, now
      checked against a ruled constant instead of another operator-typed
      value. No test-only override flag, per the Captain's explicit
      instruction -- fixtures that want to exercise burned behaviour point
      their recorded leg wav_dir AT the constant instead.
  J5  burned_corpus joins F5's identity set in g2b_family.py (own commit,
      that file) -- closes J4's two-error conjunction a second time, at the
      adjudication layer, now that the constant closes it once at the
      source.
  J6  (g2b_family.py, own commit) -- asymmetric null-handling between the
      baseline-SHA and manifest-digest blocks in F6 made consistent.

Usage:
    python g2b_gate.py --band 20m --f-min 140 --f-max 3030 \
        --baseline base_20m.json --widened wide_20m_f140.json \
        --repeat  base_20m_repeat.json \
        --manifest g2b_dll_manifest.json \
        --burned-corpus yes \
        --g-new-min-rate 0.0100 --g-high-min-rate 0.0050 \
        --churn-net-min-rate -0.0025 --churn-gross-max-rate 0.0200

    python g2b_gate.py --verify-verdict verdict_f140.json  (J4/self-containment,
        REVISION 6: re-derives a verdict's own row from its own carried
        rows/bars/constants and asserts equality; see decide()/
        run_verify_verdict() below.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path

# ── Fixed protocol constants. The OLD band is what shipped as G2 item (a)+(b)'s ─
# ── predecessor; NEW_F_MAX is fixed across the whole f_min ladder (pre-reg §4). ─

OLD_F_MIN, OLD_F_MAX = 200, 3000
NEW_F_MAX_DEFAULT = 3030

# A6 fix: an ABSENCE/power check (HK-021(j)) needs >= 5 to be trusted. Previously
# this was a PREDICTED lambda computed from the reference decoder's own decode
# frequency distribution -- which HK-026 rules circular, because that distribution
# cannot see past its own passband. It is now an OBSERVED count from THIS run: no
# decoder output is used to bound a decoder's own blind spot. Run more cycles, or
# declare the high end unadjudicated; do not predict from a contaminated share.
MIN_HIGH_BAND_OBSERVATIONS = 5

BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 20260812

# J4 -- Captain's ruling, fifth review: this file's own location, resolved
# CWD-independently (D4's hazard exactly: os.path.realpath resolves a
# relative path against the PROCESS's CWD, not the file's location, so a
# path meant to be repo-relative must be anchored off __file__, never off
# whatever directory happened to launch the interpreter).
REPO_ROOT = Path(__file__).resolve().parents[2]

# The ONE burned region. RULED by measurement (C1, review 3): the 08-08
# corpus is wsjt-x/wav, and its 250th in-window cycle is 260808_014215
# (independently reproduced by g2_verification_replay.py's select_files()
# against the real corpus). Neither value is operator-supplied any more --
# both were typed on the command line until this revision, and both were
# defeated by the same class of typo (B2 -> C1 -> D1 for the directory; the
# floor was always paired with it and would have repeated the shape one
# field over). isdir-checked at the point of use: a hard-coded path is not
# a correct path -- a fresh checkout has no artefacts/ at all (it is
# blanket-gitignored) -- so an absent directory fails closed (ROW 0), it is
# never silently treated as "not burned".
BURNED_CORPUS = {
    "wav_dir": "artefacts/20260808_live_run_0016-8080/wsjt-x/wav",
    "held_out_from": "260808_014215",
}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def phys_by_cycle(leg):
    """{ts: set((f, dt))} -- physical identity, the correct key for recall.

    Sorted at construction. Set iteration order is hash-randomised per process,
    so any downstream seeded resampling over an unsorted set silently differs
    run to run despite a fixed seed (the p23_common/load_ref defect class).

    AV cycles (av=True; the shim's SEH caught a native access violation) map to
    an empty set here, same as a genuine zero-decode cycle -- the DISTINCTION
    between the two is made by av_cycles() below and applied by the caller
    (B5 fix). This function alone cannot and does not tell them apart.
    """
    out = {}
    for f in leg["per_file"]:
        out.setdefault(f["ts"], set())
        for d in f["decodes"]:
            out[f["ts"]].add((d["f"], round(d["dt"], 2)))
    return {ts: out[ts] for ts in sorted(out)}


def av_cycles(leg):
    """{ts, ...} -- cycles where the shim's SEH caught a native AV on this leg.

    B5 fix. An AV cycle has no valid physical-decode comparison: reading it as
    a zero-decode cycle silently converts a caught crash into a counted LOSS
    (if the other leg being compared decoded fine) or a counted GAIN (in
    reverse) -- feeding churn_net/churn_gross, which are co-primary and can
    stop the arm, off an SEH artefact rather than a decoder result. The shim
    contains SEH specifically because this happens; it is not hypothetical.
    """
    return {f["ts"] for f in leg["per_file"] if f.get("av")}


def truncated_cycles(leg):
    """{ts, ...} -- cycles the producer marked `truncated` (D3): the decoder
    returned >= MAX_RESULTS results, so truncation cannot be ruled out for
    that cycle. Unlike av_cycles(), these are NOT silently excluded from a
    rate and the leg is NOT allowed to proceed missing them -- a truncated
    cycle's decode set is exactly the kind of thing that would manufacture a
    spurious G_new gain (if it is the widened leg, the one most likely to
    grow) or hide a real loss, so P2 ROW 0s the WHOLE LEG. This is the gate
    half of the fix the Architect's fourth review ordered: the producer no
    longer crashes on this condition (a bare `assert` would have, contra
    C3's own "clamp and warn, do not crash" ruling on the identical hazard)
    -- it records the fact instead, and this is where that fact is read.
    .get() rather than a bare key lookup: a leg produced by
    g2_verification_replay.py older than the D3 fix carries no `truncated`
    field at all, and the honest reading of "we don't know" is "not flagged
    truncated", not a KeyError that would ROW-0 every pre-D3 fixture.
    """
    return {f["ts"] for f in leg["per_file"] if f.get("truncated")}


def in_new_band_low(freq, f_min):
    return f_min <= freq < OLD_F_MIN


def in_new_band_high(freq, f_max):
    return OLD_F_MAX <= freq < f_max


def per_cycle_terms(base, other, f_min, f_max, av_exclude=frozenset()):
    """Per-cycle (g_low, g_high, g_elsewhere, lost, n_base). Cycle is the CLUSTER
    unit (HK-021(i)): decodes within a cycle share one noise realisation and one
    candidate ordering. Bootstrap resamples CYCLES, never decodes.

    A1 fix: low-band and high-band gains are counted SEPARATELY, never pooled at
    this layer. Pooling happens (or does not) only at the row-decision layer,
    and only conditioned on whether the high end is adjudicated (A1/P1 below).

    B5 fix: av_exclude removes cycles where ANY of the three legs in this run
    AV'd, so a caught native crash never enters a rate as a loss or a gain.
    """
    b, o = phys_by_cycle(base), phys_by_cycle(other)
    shared = sorted((set(b) & set(o)) - av_exclude)
    rows = []
    for ts in shared:
        gained, lost = o[ts] - b[ts], b[ts] - o[ts]
        g_lo = sum(1 for (f, _) in gained if in_new_band_low(f, f_min))
        g_hi = sum(1 for (f, _) in gained if in_new_band_high(f, f_max))
        g_else = len(gained) - g_lo - g_hi
        rows.append((g_lo, g_hi, g_else, len(lost), len(b[ts])))
    return rows


def rates(rows):
    """Rates dict, all as fractions of baseline decodes (the DE-DUPLICATED
    per-cycle population -- A8 fix: this is now the ONLY denominator anywhere in
    this file; the earlier raw per-file row count is gone)."""
    d = sum(r[4] for r in rows)
    if d == 0:
        return {"g_low": 0.0, "g_high": 0.0,
                "churn_net": 0.0, "churn_gross": 0.0}
    g_lo = sum(r[0] for r in rows)
    g_hi = sum(r[1] for r in rows)
    g_else = sum(r[2] for r in rows)
    lost = sum(r[3] for r in rows)
    return {
        "g_low": g_lo / d,
        "g_high": g_hi / d,
        "churn_net": (g_else - lost) / d,
        "churn_gross": (g_else + lost) / d,
    }


def bootstrap_bounds(rows, metrics, bootstrap_n=BOOTSTRAP_N, seed=BOOTSTRAP_SEED):
    """metrics: {name: (metric_fn, pct)}. pct=0.05 -> 95% LOWER bound;
    pct=0.95 -> 95% UPPER bound (gross churn is a harm metric, bounded above;
    everything else here is bounded below).

    ONE resampling loop computes every named metric from the SAME draw. The
    four separate bootstrap_bound() calls this replaces each reseeded the rng
    identically and drew the same n-sized sample sequence, so they already
    shared common random numbers -- this is exactly equivalent and ~4x faster
    for four metrics. Flagged by the Architect's B-round review as worth doing
    before the ladder's 9 legs run.

    REVISION 6: bootstrap_n/seed are now overridable (default to the module
    constants) so run_verify_verdict() can re-derive a verdict's row using
    the SEED AND DRAW COUNT THE VERDICT ITSELF CARRIES, not whatever this
    file's current globals happen to be -- the self-containment property
    (Captain's ruling) is about the verdict standing on its own, not about
    trusting today's code to still match yesterday's constants.

    n_rows == 0 (J1): `rows[rng.randrange(n_rows)] for _ in range(n_rows)`
    never evaluates `randrange(0)` when n_rows is 0 -- the comprehension's
    own `range(n_rows)` has zero iterations, so this returns [] cleanly,
    and rates([]) is the honest all-zero default. That degenerate,
    zero-width bootstrap CI is a defect if read as "confidently below the
    bar" -- decide() below guards it explicitly (the d_base > 0 check),
    rather than relying on this function to raise.
    """
    rng = random.Random(seed)
    n_rows = len(rows)
    acc = {name: [] for name in metrics}
    for _ in range(bootstrap_n):
        sample = [rows[rng.randrange(n_rows)] for _ in range(n_rows)]
        r = rates(sample)
        for name, (metric_fn, _pct) in metrics.items():
            acc[name].append(metric_fn(r))
    out = {}
    for name, (_metric_fn, pct) in metrics.items():
        vals = sorted(acc[name])
        idx = min(max(int(pct * bootstrap_n), 0), bootstrap_n - 1)
        out[name] = vals[idx]
    return out


def gate_file_sha256():
    """This file's own SHA256, read fresh from disk (Captain's ruling, fifth
    review §2: E2's logic -- pin the SHA256, never infer identity from a
    label or a cached value -- applied to the INSTRUMENT itself, not the
    DLL). Three rungs adjudicated together as one family must have been
    read by the SAME evaluator; g2b_family.py's F9 refuses if the three
    verdicts' gate_sha256 differ."""
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def decide(rows, f_min, f_max, bars,
           min_high_band_observations=MIN_HIGH_BAND_OBSERVATIONS,
           old_f_max=OLD_F_MAX, bootstrap_n=BOOTSTRAP_N, bootstrap_seed=BOOTSTRAP_SEED):
    """The measurement AND the row decision, as ONE pure function of
    (rows, f_min, f_max, bars, constants) -- nothing else, no file I/O, no
    argparse. main() calls this on a fresh read; run_verify_verdict() calls
    the IDENTICAL function on a verdict's own carried rows/bars/constants,
    so the two paths cannot silently diverge (Captain's ruling, fifth
    review §2: "the verdict must be sufficient to RE-DERIVE the row without
    the leg JSONs" -- this function is the derivation, used both ways).

    J1 fix: ROW 3 previously fired whenever g_low's 95% LOWER bound failed
    to clear its bar -- guaranteed for ANY underpowered rung, indistin-
    guishable from a genuine absence. g_low's 95% UPPER bound now decides
    which of the two it is:
      - upper bound  < bar : the rung was measured and genuinely
        underdelivers -> ROW 3 means what it says.
      - upper bound >= bar (lower bound still fails) : the rung was NOT
        powered to tell absence from insufficient data -> ROW_INDETERMINATE,
        new, refused by g2b_family.py exactly like ROW_0/ROW_0d.
      - d_base == 0 (zero baseline decodes -- nothing was measured at all):
        ALWAYS ROW_INDETERMINATE, regardless of what the degenerate
        zero-width bootstrap CI reports. A bootstrap over zero rows never
        raises (see bootstrap_bounds()'s own docstring) and returns 0.0 for
        both bounds, which would otherwise misread as a confident absence.
    """
    r = rates(rows)
    d_base = sum(row[4] for row in rows)
    g_high_total = sum(row[1] for row in rows)
    p1_fired = g_high_total < min_high_band_observations

    bounds = bootstrap_bounds(rows, {
        "g_low":       (lambda rr: rr["g_low"], 0.05),
        "g_low_hi":    (lambda rr: rr["g_low"], 0.95),
        "g_high":      (lambda rr: rr["g_high"], 0.05),
        "churn_net":   (lambda rr: rr["churn_net"], 0.05),
        "churn_gross": (lambda rr: rr["churn_gross"], 0.95),
    }, bootstrap_n=bootstrap_n, seed=bootstrap_seed)

    g_ok = bounds["g_low"] >= bars["g_new_min_rate"]
    g_powered_absence = (d_base > 0) and (bounds["g_low_hi"] < bars["g_new_min_rate"])
    high_adjudicated = not p1_fired
    high_ok = high_adjudicated and (bounds["g_high"] >= bars["g_high_min_rate"])
    net_ok = bounds["churn_net"] >= bars["churn_net_min_rate"]
    gross_ok = bounds["churn_gross"] <= bars["churn_gross_max_rate"]

    if p1_fired:
        scope = (" (LOW END ONLY -- P1 fired, the high end is NOT adjudicated; "
                 f"licensed consequence is [{f_min}, {old_f_max}) only)")
    elif high_ok:
        scope = (f" (both ends adjudicated and both clear; licensed "
                 f"consequence is [{f_min}, {f_max}))")
    else:
        scope = (" (LOW END ONLY -- high end adjudicated but did not clear "
                 f"its own floor; licensed consequence is "
                 f"[{f_min}, {old_f_max}) only)")

    # ── Rows, in strict order, mutually exclusive (J1 adds the first branch;
    # the remaining four are unchanged from REVISION 5, still exhaustive over
    # (g_ok, gross_ok) x net_ok once the underpowered case is split off).
    if not g_ok and not g_powered_absence:
        row_id = "ROW_INDETERMINATE"
    elif not g_ok and not gross_ok:
        row_id = "ROW_0d"
    elif g_ok and net_ok and gross_ok:
        row_id = "ROW_1"
    elif g_ok and (not net_ok or not gross_ok):
        row_id = "ROW_2"
    elif not g_ok:
        row_id = "ROW_3"
    else:
        # Structurally unreachable given the branches above are exhaustive;
        # kept as a safety net, same discipline A10 applied to the previous
        # unreachable branch -- if this is ever selected, that is itself a
        # finding to report, not a row to trust.
        row_id = "ROW_0d"

    return {"row": row_id, "scope": scope, "p1_fired": p1_fired,
            "rates": r, "bounds": bounds, "d_base": d_base,
            "g_high_total": g_high_total, "g_ok": g_ok, "gross_ok": gross_ok,
            "net_ok": net_ok, "high_ok": high_ok,
            "high_adjudicated": high_adjudicated,
            "g_powered_absence": g_powered_absence}


def manifest_file_sha256(path):
    """E2 fix (Architect, 2026-08-12 21:43Z, out-of-band review-5 candidates):
    the SHA256 of the manifest FILE as read, byte-for-byte -- not the SHAs it
    contains. The manifest is a mutable file, and g2b_dll_manifest.json's own
    _comment ("never edit an existing entry after its leg has been run") is
    prose with no mechanism; this is the mechanism. g2b_family.py refuses the
    family adjudication if the three rungs' manifest digests differ, so a
    manifest edited between rungs is detectable rather than silently trusted.
    None if the file does not exist -- P2's manifest-missing checks already
    fail that leg closed (ROW 0); this just reports the fact honestly rather
    than raising a second time."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return None


def build_verdict(*, band, f_min, f_max, row, scope, p1_fired, rates, bounds, bars,
                   dll_sha256, manifest_sha256, wav_dir, burned_corpus,
                   window, start_cycle, n_cycles, d_base, rows,
                   av_excluded_count, truncated_count, gate_sha256,
                   bootstrap_n, bootstrap_seed, min_high_band_observations,
                   old_f_min, old_f_max):
    """D2 fix: the one dict this gate can emit for a cross-rung adjudicator to
    read. `rates`/`bounds` are None when no read was possible (ROW_0) -- there
    is nothing honest to report for them, and None says so rather than a
    fabricated zero. `bars` are always present: they are CLI-supplied and
    known before any precondition is even evaluated.

    E1/E2 fix: `dll_sha256` (per-leg, baseline/widened/repeat) and
    `manifest_sha256` (the manifest FILE's own digest as read) are, like
    `bars`, always present -- known from the leg JSONs and the manifest path
    before any precondition runs. `wav_dir` (the legs' shared normalised
    corpus directory) and `burned_corpus` (the operator's D1 declaration) are
    also always emitted; `wav_dir` is null-safe on ROW_0 where provenance may
    be unconfirmed, `burned_corpus` is CLI-supplied and always known. Without
    these four fields g2b_family.py -- the instrument that actually combines
    three rungs into one conclusion -- cannot tell whether the three verdicts
    it is adjudicating came from one experiment or three.

    Captain's ruling, fifth review §2 (self-contained verdict): the fields
    below make the verdict SUFFICIENT TO RE-DERIVE ITS OWN ROW without the
    leg JSONs (run_verify_verdict() is the mechanism that checks this, not
    merely asserts it) --

      - `rows`: the actual per-cycle (g_low, g_high, g_else, lost, n_base)
        terms per_cycle_terms() computed -- the evidence itself. None on
        ROW_0 (no read happened, nothing to carry).
      - `window`, `start_cycle`, `n_cycles`, `d_base`: the identity of the
        slice measured (J3's field-adding half, absorbed here). `window`/
        `start_cycle` are null-safe exactly like `wav_dir` (unconfirmed
        provenance on some ROW_0 paths); `n_cycles`/`d_base` are None
        whenever `rows` is None, for the same reason `rates`/`bounds` are.
      - `av_excluded_count`, `truncated_count`: always known (computed
        before any precondition is evaluated, like `bars`), so they are
        present on every path including ROW_0.
      - `gate_sha256`, `bootstrap_n`, `bootstrap_seed`,
        `min_high_band_observations`, `old_f_min`, `old_f_max`: the
        INSTRUMENT's own identity and every constant that entered the
        decision. `gate_sha256` is E2's logic (pin the SHA256, never infer
        identity from a label) applied to this file itself, not the DLL --
        g2b_family.py's F9 refuses if three rungs were read by different
        evaluators. Always known, always present.

    Boundary, stated here so nobody over-trusts the artefact: this
    certifies what the gate SAW, not what was TRUE. It cannot certify that
    `wav_dir` held the audio it claims, that the DLL behind a SHA was built
    from the source it claims, or that the producer read the cycles it
    recorded. The instrument still cannot bound its own blind spot
    (HK-026)."""
    return {"band": band, "f_min": f_min, "f_max": f_max, "row": row,
            "scope": scope, "p1_fired": p1_fired, "rates": rates,
            "bounds": bounds, "bars": bars, "dll_sha256": dll_sha256,
            "manifest_sha256": manifest_sha256, "wav_dir": wav_dir,
            "burned_corpus": burned_corpus, "window": window,
            "start_cycle": start_cycle, "n_cycles": n_cycles,
            "d_base": d_base, "rows": rows,
            "av_excluded_count": av_excluded_count,
            "truncated_count": truncated_count, "gate_sha256": gate_sha256,
            "bootstrap_n": bootstrap_n, "bootstrap_seed": bootstrap_seed,
            "min_high_band_observations": min_high_band_observations,
            "old_f_min": old_f_min, "old_f_max": old_f_max}


def write_verdict(path, verdict):
    """D2 fix: writes the verdict as JSON if --emit-verdict was given; a no-op
    otherwise (the flag is optional so every existing invocation, and every
    existing smoke-test fixture, keeps working unchanged)."""
    if path is None:
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=2, sort_keys=True)
        fh.write("\n")


def run_verify_verdict(path):
    """Captain's ruling, fifth review §2: "the verdict must be sufficient to
    RE-DERIVE the row without the leg JSONs" -- this is the mechanism that
    makes that testable rather than merely asserted. Reads a verdict written
    by --emit-verdict, recomputes the row from ONLY its own carried
    `rows`/`bars`/constants via decide() -- the SAME function main() itself
    calls on a fresh read -- and asserts the result equals the row recorded.
    Exit non-zero and name the divergence if not.

    A ROW_0 verdict carries `rows: null` (no read happened, nothing to
    re-derive); this is verified to be exactly what was recorded, not
    treated as a failure.

    🛑 The verdict must not become a second source of truth: this may ONLY
    ever CHECK a verdict against itself, never produce a row that is then
    used as new evidence (Captain's explicit instruction). It takes no
    argument but a single verdict path for exactly this reason -- there is
    no way to feed it two different inputs and ask which is right.

    Boundary, restated (see build_verdict()'s own docstring): a passing
    --verify-verdict certifies the verdict is INTERNALLY CONSISTENT -- what
    the gate saw, re-derives to what the gate said. It does not certify
    that what the gate saw was true (HK-026)."""
    with open(path, encoding="utf-8") as fh:
        v = json.load(fh)

    if v.get("row") == "ROW_0":
        if v.get("rows") is not None:
            print(f"VERIFY-VERDICT FAIL -- {path}: row is ROW_0 (no read) "
                  f"but rows is not null -- a NO-READ verdict must carry no "
                  f"evidence.")
            return 1
        print(f"VERIFY-VERDICT OK -- {path}: ROW_0, no read happened, "
              f"rows correctly null. Nothing to re-derive.")
        return 0

    required = ("rows", "bars", "f_min", "f_max", "bootstrap_n", "bootstrap_seed")
    missing = [k for k in required if v.get(k) is None]
    if missing:
        print(f"VERIFY-VERDICT FAIL -- {path}: row is {v.get('row')!r} (a "
              f"real read) but is missing {', '.join(missing)} -- cannot "
              f"re-derive without them.")
        return 1

    rows = [tuple(row) for row in v["rows"]]
    decision = decide(
        rows, v["f_min"], v["f_max"], v["bars"],
        min_high_band_observations=v.get("min_high_band_observations",
                                          MIN_HIGH_BAND_OBSERVATIONS),
        old_f_max=v.get("old_f_max", OLD_F_MAX),
        bootstrap_n=v["bootstrap_n"], bootstrap_seed=v["bootstrap_seed"])

    if decision["row"] != v["row"]:
        print(f"VERIFY-VERDICT FAIL -- {path}: recorded row is {v['row']!r}, "
              f"re-derived row from the verdict's own carried rows/bars/"
              f"constants is {decision['row']!r}. The verdict does NOT "
              f"re-derive itself.")
        return 1
    if decision["scope"].strip() != v.get("scope"):
        print(f"VERIFY-VERDICT FAIL -- {path}: row matches ({v['row']}) but "
              f"recorded scope {v.get('scope')!r} != re-derived scope "
              f"{decision['scope'].strip()!r}.")
        return 1

    print(f"VERIFY-VERDICT OK -- {path}: row {v['row']} re-derives "
          f"identically from {len(rows)} carried per-cycle row(s), "
          f"gate_sha256={v.get('gate_sha256', '?')[:16]}...")
    return 0


def load_manifest(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def check_manifest_binding(sha, f_min, f_max, manifest, manifest_path, role):
    """B1 fix: this is now called for the BASELINE leg too, not only the
    widened leg. Previously nothing asserted the baseline was actually the
    [200,3000) reference build -- pointing --baseline/--repeat at, say, the
    rung-180 binary passed every other precondition and silently measured a
    narrower mechanism against a floor scaled for the wrong width. The repeat
    leg is covered transitively: P2 already asserts its SHA equals the
    baseline's."""
    problems = []
    entry = manifest.get(sha)
    if entry is None:
        problems.append(f"{role} leg's SHA {sha[:16]}... is not in the "
                         f"pre-registered manifest {manifest_path}")
    elif entry.get("f_min") != f_min or entry.get("f_max") != f_max:
        problems.append(f"manifest says {role} leg's SHA {sha[:16]}... was "
                         f"built for f_min={entry.get('f_min')} "
                         f"f_max={entry.get('f_max')}, not the {role} band "
                         f"[{f_min}, {f_max})")
    return problems


def main():
    # REVISION 6: --verify-verdict is a SEPARATE invocation mode (Captain's
    # ruling, self-contained verdict) -- it needs no --band/--baseline/etc,
    # so it is dispatched before the full parser (which requires those) is
    # even constructed, via a minimal parser of its own.
    if "--verify-verdict" in sys.argv:
        vp = argparse.ArgumentParser()
        vp.add_argument("--verify-verdict", required=True, metavar="PATH",
                         help="read a verdict written by --emit-verdict, "
                              "re-derive its row from its own carried rows/"
                              "bars/constants via decide() (the SAME "
                              "function a fresh read uses), and assert it "
                              "equals the row recorded. May ONLY be used to "
                              "check a verdict against itself -- never to "
                              "produce a row used as new evidence.")
        vargs = vp.parse_args()
        return run_verify_verdict(vargs.verify_verdict)

    ap = argparse.ArgumentParser()
    ap.add_argument("--band", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--widened", required=True)
    ap.add_argument("--repeat", required=True,
                     help="second baseline-binary leg; the P3 determinism control")

    # A2 fix: f_min is a required argument, not a module constant. f_max stays
    # fixed at 3030 across the ladder per pre-reg §4, but is overridable.
    ap.add_argument("--f-min", type=int, required=True,
                     help="this rung's low-end cutoff, e.g. 180 / 140 / 100")
    ap.add_argument("--f-max", type=int, default=NEW_F_MAX_DEFAULT)

    # C5 fix: --is-widest-rung is REMOVED. The A3 combination rule it drove
    # ("family closes only if the widest rung reads ROW 3") let the
    # thinnest-margin rung -- which the raw WAV shows is also the widest rung
    # -- close the whole family alone, discarding a passing narrower rung.
    # ROW 3 is now evidence about the invoked rung's own width only; family
    # closure is a separate, cross-rung adjudication this single invocation
    # cannot perform (see the ROW 3 branch below and the REVISION 4 docstring
    # note).

    # A7/B1 fix: nothing previously bound a leg's binary to the rung it claims
    # to be, and (B1) the check only ever covered the widened leg. The manifest
    # is pre-registered (SHA256 -> {f_min, f_max}) BEFORE the run; P2 now
    # asserts BOTH the widened leg's and the baseline leg's SHA are in it and
    # match what each is claimed to be.
    ap.add_argument("--manifest", required=True,
                     help="path to a JSON SHA256 -> {f_min, f_max} manifest, "
                          "pre-registered before any rung is built")

    # B2 fix: --held-out-from was a bare global lexical floor pooled across
    # every leg from every corpus (that construction ROW-0'd an un-burned
    # 4,614-cycle corpus under a correct floor, and protected nothing at all
    # under the pre-reg's own example format -- both silently). The floor
    # applies ONLY to legs drawn from the burned corpus, identified by each
    # leg's recorded `wav_dir` field.
    # C2 fix: wav_dir, and the burned corpus's own directory, are normalised
    # (normcase+realpath) before any comparison -- a bare string `!=` is not
    # an identity check (relative vs absolute, `/` vs `\\`, a trailing
    # separator, or case all defeat it silently).
    # D1 fix (Architect review 4): the operator pre-declares whether these
    # three legs ARE the burned corpus, rather than the gate inferring it
    # from whether any leg happens to match. A mismatch between the
    # declaration and the legs' actual shared wav_dir is ROW 0 in EITHER
    # direction, never a silent skip.
    # J4 fix (Captain's ruling, fifth review): --burned-wav-dir and
    # --held-out-from are REMOVED, not defaulted. Three rounds (B2 -> C1 ->
    # D1) each fixed the VALUE these named and left the SILENCE that made a
    # wrong value undetectable; pinning the directory while leaving the
    # floor operator-typed would repeat that shape one field over. Both are
    # now ONE pre-registered constant, BURNED_CORPUS (module level, resolved
    # against REPO_ROOT, isdir-checked -> ROW 0 if absent). Only the
    # operator's DECLARATION of which case this run is remains a CLI
    # argument -- checked against the ruled constant, not against another
    # operator-typed value.
    ap.add_argument("--burned-corpus", required=True, choices=("yes", "no"),
                     help="does the pre-registered BURNED_CORPUS constant "
                          "name the corpus these three legs are actually "
                          "drawn from? 'yes' requires the legs' shared "
                          "wav_dir to equal it and applies the held-out "
                          "floor to all three; 'no' requires it NOT to "
                          "equal it. Either mismatch is ROW 0, not a silent "
                          "skip (D1); the constant itself is ROW 0 if its "
                          "directory does not exist on disk (J4)")

    # A5 fix: no bar in this file is derived from anything that passes through a
    # decoder. These are supplied by the caller (the pre-registration document),
    # per-rung, as pre-committed round floors with NO claimed derivational
    # authority -- exactly the honest restatement A5 required. See the revised
    # pre-reg for the actual per-rung numbers and how they were chosen.
    ap.add_argument("--g-new-min-rate", type=float, required=True,
                     help="this rung's own pre-committed low-band G_new floor, "
                          "as a fraction of baseline decodes (e.g. 0.0100)")

    # B3 fix: g_high, when adjudicated (P1 does not fire), now gets its OWN
    # floor rather than being pooled with g_low and tested against the
    # low-band-scaled floor above. Fixed across the ladder (the high band
    # [3000, f_max) is the same fixed width regardless of f_min), unlike
    # --g-new-min-rate which varies per rung.
    ap.add_argument("--g-high-min-rate", type=float, required=True,
                     help="the high-band G_new floor, fraction of baseline "
                          "decodes, tested only when P1 does not fire -- "
                          "failing it narrows the licensed scope to "
                          "[f_min, 3000) rather than failing the rung "
                          "outright (B3 fix)")

    ap.add_argument("--churn-net-min-rate", type=float, required=True,
                     help="net churn floor (negative), fraction of baseline "
                          "decodes (e.g. -0.0025)")

    # A4 fix: gross churn is now a co-primary metric with its own bar and its
    # own place in the row logic, not folded into net churn.
    ap.add_argument("--churn-gross-max-rate", type=float, required=True,
                     help="gross churn ceiling, fraction of baseline decodes "
                          "(e.g. 0.0200) -- must be well below the burned leg's "
                          "observed 4.8%%, per the Architect's instruction that "
                          "a bar that number clears comfortably is not a bar")

    # D2 fix (Architect review 4): HK-021 requires a pre-registered check to
    # be drafted by writing the code that evaluates it. The A3/C5 family-
    # closure rule ("the family closes only if NO rung reads ROW 1 or ROW 2")
    # had no such code -- this gate printed prose only and returned 0 on
    # EVERY path, including ROW 0, so nothing downstream could adjudicate the
    # ladder without regexing English out of a console log (the exact way the
    # bar got softened once already, in g2_verification_report.py). Optional:
    # every existing invocation without this flag behaves exactly as before.
    ap.add_argument("--emit-verdict", default=None, metavar="PATH",
                     help="write this rung's verdict as JSON to PATH, for "
                          "g2b_family.py to read -- band, f_min, f_max, row, "
                          "scope, p1_fired, the four point rates and bootstrap "
                          "bounds (null if no read), the four bars as invoked "
                          "(D2), each leg's dll_sha256, the manifest file's "
                          "own sha256, the legs' shared wav_dir (null-safe on "
                          "ROW_0) and the --burned-corpus declaration (E1/E2)")

    args = ap.parse_args()

    # D2 fix: the bars are CLI-supplied, so they are known before ANY
    # precondition is evaluated -- included in the verdict even on ROW 0,
    # where rates/bounds are honestly None (no read happened).
    bars = {"g_new_min_rate": args.g_new_min_rate,
            "g_high_min_rate": args.g_high_min_rate,
            "churn_net_min_rate": args.churn_net_min_rate,
            "churn_gross_max_rate": args.churn_gross_max_rate}

    base, wide, rep = load(args.baseline), load(args.widened), load(args.repeat)

    # E2 fix: known immediately, exactly like `bars` above -- neither depends
    # on any precondition, so both are emitted in the verdict on every path,
    # including ROW_0, rather than only on a successful read.
    dll_shas = {"baseline": base["dll_sha256"], "widened": wide["dll_sha256"],
                "repeat": rep["dll_sha256"]}
    manifest_sha256 = manifest_file_sha256(args.manifest)

    print(f"\n{'=' * 78}\nG2(b) GATE -- band {args.band}  f_min={args.f_min} "
          f"f_max={args.f_max}\n{'=' * 78}")
    for leg in (base, wide, rep):
        print(f"  {leg['label']:12s} sha={leg['dll_sha256'][:16]}... "
              f"shim={leg['shim_version']} files={leg['n_files']}")
    print(f"  {'manifest':12s} sha="
          f"{(manifest_sha256[:16] + '...') if manifest_sha256 else 'FILE NOT FOUND'} "
          f"({args.manifest})")

    # ── P2 (VALIDITY): are these the legs the gate names? ────────────────────
    p2 = []
    if base["dll_sha256"] == wide["dll_sha256"]:
        p2.append("baseline and widened are the SAME binary")
    if base["dll_sha256"] != rep["dll_sha256"]:
        p2.append("repeat leg is not the baseline binary")
    if not (base["n_files"] == wide["n_files"] == rep["n_files"]):
        p2.append("legs cover different file counts")

    cycles_base = set(phys_by_cycle(base))
    cycles_wide = set(phys_by_cycle(wide))
    cycles_rep = set(phys_by_cycle(rep))
    if cycles_base != cycles_wide:
        p2.append("baseline and widened legs cover different cycles")
    # A9 fix: the repeat leg was previously checked only by n_files. Compare its
    # cycle SET too, not just a count that different timestamps can still match.
    if cycles_base != cycles_rep:
        p2.append("baseline and repeat legs cover different cycles")

    # A7/B1: manifest binds EACH leg's SHA to the band it claims to be.
    manifest = load_manifest(args.manifest)
    p2 += check_manifest_binding(wide["dll_sha256"], args.f_min, args.f_max,
                                  manifest, args.manifest, "widened")
    p2 += check_manifest_binding(base["dll_sha256"], OLD_F_MIN, OLD_F_MAX,
                                  manifest, args.manifest, "baseline")

    # D3 fix (Architect review 4): the producer no longer crashes when a
    # cycle's decode count is indistinguishable from truncated -- it RECORDS
    # the fact (`truncated`) and continues, so a suspect cycle no longer
    # costs the whole leg's worth of completed work. This is where the gate
    # ADJUDICATES that record: any leg carrying even one truncated cycle
    # fails closed here, same guarantee the old `assert` was trying (and
    # failing, by crashing) to provide, with no lost work either way.
    # Captain's ruling §2: truncated_count is accumulated here regardless of
    # outcome -- known before any precondition decides pass/fail, exactly
    # like `bars`/`dll_shas` above, so it is always present in the verdict.
    truncated_count = 0
    for role, leg in (("baseline", base), ("widened", wide), ("repeat", rep)):
        trunc = truncated_cycles(leg)
        truncated_count += len(trunc)
        if trunc:
            p2.append(f"{role} leg has {len(trunc)} truncated cycle(s) "
                       f"(decoder returned >= MAX_RESULTS results; "
                       f"truncation cannot be ruled out) -- earliest "
                       f"{min(trunc)}")

    # C2 fix, two halves.
    #
    # (a) wav_dir is normalised (normcase+realpath) before any comparison. A
    #     bare `!=` on operator-typed strings is not an identity check --
    #     relative vs absolute, `/` vs `\\`, a trailing separator, or (on
    #     Windows) case all defeat it silently, and both conventions are
    #     already live in this codebase (p23_common builds absolute paths
    #     from REPO_ROOT; this file's own usage example is relative).
    #
    # (b) nothing previously asserted the three legs were drawn from the SAME
    #     corpus -- and the ts key cannot catch a mix on its own: wsjt-x/wav's
    #     in-window timestamp set is a STRICT SUBSET of owsfz/wav's (2,529
    #     shared keys over DIFFERENT audio from different capture chains), so
    #     a same-ts, different-corpus mix was caught today only by an
    #     accidental 12-file gap in the cycles_base/wide/rep checks above. A
    #     safety property must not rest on an accidental gap. Fixed: every leg
    #     must carry wav_dir/window/start_cycle (fields the B4 extraction
    #     records precisely for this reason), and all three legs must agree
    #     on all three, normalised.
    provenance = {}
    for leg, role in ((base, "baseline"), (wide, "widened"), (rep, "repeat")):
        missing = [k for k in ("wav_dir", "window", "start_cycle") if k not in leg]
        if missing:
            p2.append(f"{role} leg JSON is missing {', '.join(missing)} -- it "
                       f"was produced by a producer older than the B4 "
                       f"extraction and cannot be checked against the other "
                       f"legs' corpus/slice or the held-out floor; "
                       f"regenerate it with the current "
                       f"g2_verification_replay.py")
            continue
        provenance[role] = (os.path.normcase(os.path.realpath(leg["wav_dir"])),
                             tuple(leg["window"]), leg["start_cycle"])

    if len(provenance) == 3 and len(set(provenance.values())) != 1:
        detail = "; ".join(f"{role}={v}" for role, v in provenance.items())
        p2.append(f"legs do not share one corpus/slice "
                   f"(wav_dir, window, start_cycle) -- {detail}")

    # D1 fix: --burned-corpus is the operator's required, pre-declared answer
    # for whether these three legs (which, by the time we reach here without
    # a corpus/slice-mismatch p2 entry, share ONE normalised wav_dir -- C2(b)
    # already asserts that) are drawn from the burned corpus. The OLD
    # per-leg `if wav_dir != burned_dir: continue` made a typo'd
    # --burned-wav-dir silent: every leg `continue`d, "P2 legs ok" printed,
    # and the floor was never applied -- indistinguishable from the correct,
    # common case where zero legs SHOULD match (an un-burned corpus).
    # Declaring the expected answer up front and checking it against what
    # the legs actually are turns that silence into ROW 0, in EITHER
    # direction: declared burned but the legs are not, or declared un-burned
    # but they are.
    #
    # J4 fix (Captain's ruling): the burned directory is no longer an
    # operator-typed CLI value at all -- it is BURNED_CORPUS, a
    # pre-registered constant resolved against REPO_ROOT (never the CWD --
    # D4's hazard). A hard-coded path is not necessarily a CORRECT path (a
    # fresh checkout has no artefacts/ at all, since it is
    # blanket-gitignored), so it is isdir-checked here and fails closed
    # (ROW 0) if the resolved directory does not exist -- we cannot then
    # determine whether these legs are burned, in either direction.
    burned_dir_abs = REPO_ROOT / BURNED_CORPUS["wav_dir"]
    burned_dir_exists = os.path.isdir(burned_dir_abs)
    if not burned_dir_exists:
        p2.append(f"the pre-registered BURNED_CORPUS directory "
                   f"{burned_dir_abs} does not exist -- cannot determine "
                   f"whether these legs are burned in either direction "
                   f"(J4: BURNED_CORPUS is hard-coded and isdir-checked; a "
                   f"fresh checkout has no artefacts/ at all)")
    burned_wav_dir_norm = os.path.normcase(os.path.realpath(str(burned_dir_abs)))
    legs_share_one_corpus = (len(provenance) == 3
                              and len(set(provenance.values())) == 1)
    # E1 fix: hoisted out of the `if legs_share_one_corpus:` block below so it
    # is available on EVERY path, including ROW_0 -- the verdict needs it
    # regardless of whether provenance was confirmed. None (null-safe, per
    # build_verdict's docstring) when the legs do not share one corpus/slice,
    # which is itself already a p2 failure by this point (C2(b) above).
    if legs_share_one_corpus:
        legs_wav_dir_norm, legs_window, legs_start_cycle = next(iter(provenance.values()))
        legs_window = list(legs_window)
    else:
        legs_wav_dir_norm, legs_window, legs_start_cycle = None, None, None
    n_floor_applied = 0
    if legs_share_one_corpus and burned_dir_exists:
        legs_are_burned = legs_wav_dir_norm == burned_wav_dir_norm
        if args.burned_corpus == "yes" and not legs_are_burned:
            p2.append(f"--burned-corpus yes was declared, but the legs are "
                       f"drawn from {legs_wav_dir_norm!r}, not "
                       f"{burned_wav_dir_norm!r} ({burned_dir_abs}) -- "
                       f"the held-out floor was never applied")
        elif args.burned_corpus == "no" and legs_are_burned:
            p2.append(f"--burned-corpus no was declared, but the legs are "
                       f"drawn from the burned corpus {burned_wav_dir_norm!r} "
                       f"({burned_dir_abs}) -- the operator declared an "
                       f"unburned corpus and handed the gate the burned one")
        elif args.burned_corpus == "yes":  # and legs_are_burned
            held_out_from = BURNED_CORPUS["held_out_from"]
            for role, cycles in (("baseline", cycles_base),
                                  ("widened", cycles_wide),
                                  ("repeat", cycles_rep)):
                if not cycles:
                    continue
                n_floor_applied += 1
                leg_min = min(cycles)
                if leg_min <= held_out_from:
                    p2.append(f"{role} leg is drawn from the burned run "
                               f"({burned_dir_abs}) and its earliest "
                               f"cycle {leg_min} does not exceed the "
                               f"held-out floor {held_out_from} -- the "
                               f"burned leg must not be read")
        # else: --burned-corpus no, legs genuinely not burned -- correct,
        # common case; the floor does not apply and nothing is checked.
    # else: provenance is incomplete or the legs disagree on wav_dir/window/
    # start_cycle, OR the burned-corpus constant's own directory does not
    # exist -- already flagged above and ROW 0 fires regardless; the
    # burned-corpus declaration cannot be evaluated against an unconfirmed
    # corpus or an unconfirmable constant, so it is not (n_floor_applied
    # stays 0, printed honestly below).

    # ── P3 (VALIDITY): is churn identified at all? ───────────────────────────
    # B5: AV parity is not assumed -- av_all (computed below, ahead of P3 too)
    # excludes any cycle where any leg AV'd from every rate, P3's included.
    av_all = av_cycles(base) | av_cycles(wide) | av_cycles(rep)

    rep_rows = per_cycle_terms(base, rep, args.f_min, args.f_max, av_all)
    # D5 fix (review-3 instruction, not carried out at the time because it
    # was appended to a line marked done/verified rather than given its own
    # marker -- see REVISION 5's docstring note): rep_churn_abs deliberately reads
    # ONLY g_else + lost (columns [2]/[3] of per_cycle_terms's tuple), never
    # g_low/g_high (columns [0]/[1]). That omission is complete -- it is not
    # silently dropping a real source of churn -- ONLY because `base` here
    # is always the BASELINE binary, which is built for the fixed
    # [OLD_F_MIN, OLD_F_MAX) = [200, 3000) band and structurally cannot emit
    # a decode in [f_min, 200) or [3000, f_max): g_low and g_high are
    # necessarily zero for every row in rep_rows, so summing them would add
    # nothing here. If this call is EVER changed to compare two WIDENED legs
    # against each other (rather than baseline-vs-repeat), that structural
    # guarantee no longer holds, and rep_churn_abs as written would silently
    # discard every genuine in-band (g_low/g_high) difference between them --
    # p3_fired could read "ok" while churn in the low/high bands went
    # completely uncounted. Do not repurpose this call without adding
    # g_low/g_high back into the sum.
    rep_churn_abs = sum(r[2] + r[3] for r in rep_rows)
    p3_fired = rep_churn_abs != 0

    print(f"  P2 legs    {'FAIL: ' + '; '.join(p2) if p2 else 'ok'}")
    # D1 fix: printed unconditionally, pass or fail, so the artefact records
    # that the floor ran (or didn't) rather than leaving it inferable only
    # from the absence of a complaint.
    print(f"  held-out floor applied to {n_floor_applied} leg(s)")
    print(f"  P3 determinism  baseline-vs-repeat physical differences="
          f"{rep_churn_abs} -> {'FAIL -- churn NOT identified' if p3_fired else 'ok'}")

    gate_sha256 = gate_file_sha256()

    if p2 or p3_fired:
        print("\n  ROW 0 -- NO READ. A precondition failed; the quantity is not an "
              "estimate of what this gate names. Do not interpret the numbers below.")
        write_verdict(args.emit_verdict, build_verdict(
            band=args.band, f_min=args.f_min, f_max=args.f_max, row="ROW_0",
            scope=None, p1_fired=None, rates=None, bounds=None, bars=bars,
            dll_sha256=dll_shas, manifest_sha256=manifest_sha256,
            wav_dir=legs_wav_dir_norm, burned_corpus=args.burned_corpus,
            window=legs_window, start_cycle=legs_start_cycle,
            n_cycles=None, d_base=None, rows=None,
            av_excluded_count=len(av_all), truncated_count=truncated_count,
            gate_sha256=gate_sha256, bootstrap_n=BOOTSTRAP_N,
            bootstrap_seed=BOOTSTRAP_SEED,
            min_high_band_observations=MIN_HIGH_BAND_OBSERVATIONS,
            old_f_min=OLD_F_MIN, old_f_max=OLD_F_MAX))
        return 0

    # ── The measurement ──────────────────────────────────────────────────────
    rows = per_cycle_terms(base, wide, args.f_min, args.f_max, av_all)

    if av_all:
        print(f"\n  AV cycles excluded from every rate (B5 fix): {len(av_all)} "
              f"cycle(s) where the shim's SEH caught a native access "
              f"violation on at least one leg")

    # Captain's ruling §2: decide() is the SAME pure function
    # run_verify_verdict() calls to re-derive a row from a verdict's own
    # carried terms -- one implementation of the measurement and the row
    # decision, so a fresh read and a re-derivation cannot silently diverge.
    decision = decide(rows, args.f_min, args.f_max, bars)
    r = decision["rates"]
    bounds = decision["bounds"]
    d_base = decision["d_base"]
    g_high_total = decision["g_high_total"]
    p1_fired = decision["p1_fired"]
    scope = decision["scope"]
    row_id = decision["row"]
    g_ok = decision["g_ok"]
    gross_ok = decision["gross_ok"]
    net_ok = decision["net_ok"]

    print(f"\n  P1 high-band power  observed high-band gains={g_high_total} "
          f"(need >= {MIN_HIGH_BAND_OBSERVATIONS}) -> "
          f"{'HIGH END UNADJUDICATED' if p1_fired else 'high end adjudicated'}")

    print(f"\n  cycles={len(rows)}  baseline decodes (de-duplicated)={d_base}")
    print(f"  intended mechanism   low-band gains  = {sum(x[0] for x in rows)}   "
          f"({r['g_low'] * 100:+.3f}%)")
    print(f"  intended mechanism   high-band gains = {g_high_total}   "
          f"({r['g_high'] * 100:+.3f}%)")
    print(f"  perturbation         gains elsewhere = {sum(x[2] for x in rows)}   "
          f"losses = {sum(x[3] for x in rows)}")
    print(f"  churn (net)   = {r['churn_net'] * 100:+.3f}%")
    print(f"  churn (gross) = {r['churn_gross'] * 100:+.3f}%   "
          f"(gross = |elsewhere| + |lost|; net can hide re-ordering that gross cannot)")

    # J1: G_new (low-band) now prints BOTH bounds -- the 95% upper bound is
    # what decides ROW 3 vs ROW_INDETERMINATE below.
    print(f"\n  G_new (low-band)  = {r['g_low'] * 100:+.3f}%  "
          f"(95% lower {bounds['g_low'] * 100:+.3f}%, 95% upper "
          f"{bounds['g_low_hi'] * 100:+.3f}%, bar {args.g_new_min_rate * 100:+.2f}%)")
    if not p1_fired:
        print(f"  G_new (high-band) = {r['g_high'] * 100:+.3f}%  "
              f"(95% lower {bounds['g_high'] * 100:+.3f}%, "
              f"bar {args.g_high_min_rate * 100:+.2f}%)")
    print(f"  churn net  = {r['churn_net'] * 100:+.3f}%  "
          f"(95% lower {bounds['churn_net'] * 100:+.3f}%, "
          f"bar {args.churn_net_min_rate * 100:+.2f}%)")
    print(f"  churn gross = {r['churn_gross'] * 100:+.3f}%  "
          f"(95% upper {bounds['churn_gross'] * 100:+.3f}%, "
          f"bar {args.churn_gross_max_rate * 100:+.2f}%)")

    # ── Rows, in strict order, mutually exclusive (decide() above already
    # picked row_id; this block is printing-only, matching the branch it took
    # so the console explanation always agrees with the verdict) ────────────
    if row_id == "ROW_INDETERMINATE":
        # J1 fix: g_low's 95% LOWER bound fails to clear the bar, but its 95%
        # UPPER bound does not fall below the bar either (or d_base == 0,
        # the degenerate zero-measurement case) -- this rung was not powered
        # to tell "does not deliver" from "could not have measured it"
        # (HK-021(j)).
        if d_base == 0:
            reason = ("d_base=0 -- zero baseline decodes were available to "
                       "measure against; this rung could not have been "
                       "measured at all")
        else:
            reason = (f"g_low's 95% lower bound ({bounds['g_low']*100:+.3f}%) "
                       f"does not clear the bar, but its 95% upper bound "
                       f"({bounds['g_low_hi']*100:+.3f}%) does not fall "
                       f"below the bar either")
        print(f"\n  INDETERMINATE -- NO READ. {reason}. This is not evidence "
              "of absence (ROW 3) and not evidence of eligibility (ROW 1); "
              "it is evidence of nothing (J1). Run more cycles, or declare "
              "this rung unadjudicated. STOP and escalate; do not read this "
              "as ROW 3.")
    elif row_id == "ROW_0d" and not g_ok and not gross_ok:
        # A10 fix: ROW 0d is reachable for a NAMED reason -- gross churn
        # fails its ceiling (the same ceiling ROW 2 tests -- B6 fix, no
        # second tier is claimed) landing together with a mechanism that is
        # a genuine, POWERED absence (J1: an underpowered "fails" case is
        # ROW_INDETERMINATE above, never reaches here). That combination is
        # worse than a plain "mechanism underdelivers" (ROW 3) and worse
        # than "mechanism confirmed, perturbation real" (ROW 2, which
        # requires the mechanism to have cleared its bar). It gets its own
        # stop.
        print(f"\n  ROW 0d -- CATCH-ALL, reached for a named reason (A10): the "
              f"mechanism does not clear its own bar AND gross churn exceeds "
              f"its ceiling{scope}. Both bars failed together, against the "
              f"SAME gross-churn ceiling ROW 2 tests (B6 fix: no distinct "
              f"severity tier is claimed here); it reaches this row rather "
              f"than ROW 2 only because the mechanism ALSO failed. STOP and "
              f"escalate; do not improvise a reading.")
    elif row_id == "ROW_1":
        print(f"\n  ROW 1 -- ELIGIBLE{scope}. The mechanism clears its own "
              "pre-committed floor and both churn metrics are bounded. The "
              "Captain chooses among eligible rungs; this gate does not.")
    elif row_id == "ROW_2":
        reason = []
        if not net_ok:
            reason.append("net churn exceeds its floor")
        if not gross_ok:
            reason.append("gross churn exceeds its ceiling")
        print(f"\n  ROW 2 -- MECHANISM CONFIRMED, PERTURBATION REAL "
              f"({'; '.join(reason)}){scope}. Do NOT ship the raw widening. "
              "Escalate decoupling the noise-floor estimate from the passband "
              "as its own change; the widening returns on top of it.")
    elif row_id == "ROW_3":
        # C5 fix: the previous rule ("family closes only if the WIDEST rung
        # reads ROW 3") let the thinnest-margin rung -- the raw WAV shows this
        # IS the widest rung, by construction of the ladder -- close the whole
        # family alone, discarding a passing narrower rung. This invocation
        # sees one rung only and cannot perform a cross-rung adjudication;
        # ROW 3 is now evidence about this rung's width, full stop.
        print(f"\n  ROW 3 -- this rung does not deliver{scope}. This is "
              "evidence about THIS rung's width only -- g_low's 95% upper "
              f"bound ({bounds['g_low_hi']*100:+.3f}%) falls below the bar, "
              "confirming this is a genuine, powered absence, not an "
              "underpowered read (J1). Per the repaired combination rule "
              "(C5): the passband family closes only if NO rung reads ROW 1 "
              "or ROW 2 -- a separate adjudication made after all three "
              "rungs have run, not by this invocation alone.")
    else:
        # Structurally unreachable given decide()'s branches are exhaustive;
        # kept as a safety net, same discipline A10 applied to the previous
        # unreachable branch -- if this ever prints, that is itself a
        # finding to report, not a row to trust. Marked ROW_0d in the
        # verdict too (D2): g2b_family.py refuses on ROW_0d, so an
        # adjudicator can never silently treat this defect as real evidence.
        row_id = "ROW_0d"
        print("\n  ROW 0d -- CATCH-ALL, reached via the UNEXPECTED branch (should "
              "be structurally unreachable). STOP and escalate; report this as a "
              "gate defect, do not improvise a reading.")

    write_verdict(args.emit_verdict, build_verdict(
        band=args.band, f_min=args.f_min, f_max=args.f_max, row=row_id,
        scope=scope.strip(), p1_fired=p1_fired,
        rates=r, bounds=bounds, bars=bars,
        dll_sha256=dll_shas, manifest_sha256=manifest_sha256,
        wav_dir=legs_wav_dir_norm, burned_corpus=args.burned_corpus,
        window=legs_window, start_cycle=legs_start_cycle,
        n_cycles=len(rows), d_base=d_base,
        rows=[list(row) for row in rows],
        av_excluded_count=len(av_all), truncated_count=truncated_count,
        gate_sha256=gate_sha256, bootstrap_n=BOOTSTRAP_N,
        bootstrap_seed=BOOTSTRAP_SEED,
        min_high_band_observations=MIN_HIGH_BAND_OBSERVATIONS,
        old_f_min=OLD_F_MIN, old_f_max=OLD_F_MAX))
    return 0


if __name__ == "__main__":
    sys.exit(main())
