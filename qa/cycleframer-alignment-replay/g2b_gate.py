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

Usage:
    python g2b_gate.py --band 20m --f-min 140 --f-max 3030 \
        --baseline base_20m.json --widened wide_20m_f140.json \
        --repeat  base_20m_repeat.json \
        --manifest g2b_dll_manifest.json \
        --burned-corpus yes \
        --burned-wav-dir artefacts/20260808_live_run_0016-8080/wsjt-x/wav \
        --held-out-from 260808_014215 \
        --g-new-min-rate 0.0100 --g-high-min-rate 0.0050 \
        --churn-net-min-rate -0.0025 --churn-gross-max-rate 0.0200
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

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


def bootstrap_bounds(rows, metrics):
    """metrics: {name: (metric_fn, pct)}. pct=0.05 -> 95% LOWER bound;
    pct=0.95 -> 95% UPPER bound (gross churn is a harm metric, bounded above;
    everything else here is bounded below).

    ONE resampling loop computes every named metric from the SAME draw. The
    four separate bootstrap_bound() calls this replaces each reseeded the rng
    identically and drew the same n-sized sample sequence, so they already
    shared common random numbers -- this is exactly equivalent and ~4x faster
    for four metrics. Flagged by the Architect's B-round review as worth doing
    before the ladder's 9 legs run.
    """
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(rows)
    acc = {name: [] for name in metrics}
    for _ in range(BOOTSTRAP_N):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        r = rates(sample)
        for name, (metric_fn, _pct) in metrics.items():
            acc[name].append(metric_fn(r))
    out = {}
    for name, (_metric_fn, pct) in metrics.items():
        vals = sorted(acc[name])
        idx = min(max(int(pct * BOOTSTRAP_N), 0), BOOTSTRAP_N - 1)
        out[name] = vals[idx]
    return out


def build_verdict(band, f_min, f_max, row, scope, p1_fired, rates, bounds, bars):
    """D2 fix: the one dict this gate can emit for a cross-rung adjudicator to
    read. `rates`/`bounds` are None when no read was possible (ROW_0) -- there
    is nothing honest to report for them, and None says so rather than a
    fabricated zero. `bars` are always present: they are CLI-supplied and
    known before any precondition is even evaluated."""
    return {"band": band, "f_min": f_min, "f_max": f_max, "row": row,
            "scope": scope, "p1_fired": p1_fired, "rates": rates,
            "bounds": bounds, "bars": bars}


def write_verdict(path, verdict):
    """D2 fix: writes the verdict as JSON if --emit-verdict was given; a no-op
    otherwise (the flag is optional so every existing invocation, and every
    existing smoke-test fixture, keeps working unchanged)."""
    if path is None:
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=2, sort_keys=True)
        fh.write("\n")


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

    # B2 fix: --held-out-from is no longer a bare global lexical floor pooled
    # across every leg from every corpus (that construction ROW-0'd an
    # un-burned 4,614-cycle corpus under a correct floor, and protected
    # nothing at all under the pre-reg's own example format -- both silently).
    # The floor now applies ONLY to legs drawn from --burned-wav-dir, which
    # g2_verification_replay.py's extraction records as each leg's `wav_dir`
    # field. A leg from any other corpus is never compared against it.
    # C2 fix: this value, and every leg's recorded wav_dir, is normalised
    # (normcase+realpath) before any comparison -- a bare string `!=` is not
    # an identity check (relative vs absolute, `/` vs `\\`, a trailing
    # separator, or case all defeat it silently).
    # D1 fix (Architect review 4, 2026-08-12 20:52Z): the operator now
    # pre-declares whether these three legs ARE the burned corpus, rather
    # than the gate inferring it from whether any leg happens to match
    # --burned-wav-dir. Three rounds of the same shape (B2 -> C1 -> D1): each
    # correction fixed the VALUE and left the SILENCE that made a wrong value
    # undetectable -- a typo or a stale path made every leg's comparison
    # `continue`, "P2 legs ok" printed, and the burned run's held-out floor
    # was never applied, indistinguishable from the correct, common case (an
    # un-burned corpus, where zero legs SHOULD match). A mismatch between the
    # declaration and the legs' actual shared wav_dir is now ROW 0 in EITHER
    # direction, never a silent skip.
    ap.add_argument("--burned-corpus", required=True, choices=("yes", "no"),
                     help="does --burned-wav-dir name the corpus these three "
                          "legs are actually drawn from? 'yes' requires the "
                          "legs' shared wav_dir to equal --burned-wav-dir and "
                          "applies the held-out floor to all three; 'no' "
                          "requires it NOT to equal it. Either mismatch is "
                          "ROW 0, not a silent skip (D1)")
    ap.add_argument("--burned-wav-dir", required=True,
                     help="the WAV directory the burned leg was drawn from, "
                          "e.g. artefacts/20260808_live_run_0016-8080/"
                          "wsjt-x/wav -- the floor below applies ONLY to legs "
                          "whose recorded wav_dir equals this, never pooled "
                          "across corpora (RULED 2026-08-12: wsjt-x/wav, not "
                          "owsfz/wav, for the 08-08 corpus -- C1)")
    ap.add_argument("--held-out-from", required=True,
                     help="ts floor (exclusive), evaluated only against legs "
                          "drawn from --burned-wav-dir, e.g. 260808_014215 "
                          "(the burned run's 250th in-window cycle)")

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
                          "bounds (null if no read), and the four bars as "
                          "invoked (D2)")

    args = ap.parse_args()

    # D2 fix: the bars are CLI-supplied, so they are known before ANY
    # precondition is evaluated -- included in the verdict even on ROW 0,
    # where rates/bounds are honestly None (no read happened).
    bars = {"g_new_min_rate": args.g_new_min_rate,
            "g_high_min_rate": args.g_high_min_rate,
            "churn_net_min_rate": args.churn_net_min_rate,
            "churn_gross_max_rate": args.churn_gross_max_rate}

    base, wide, rep = load(args.baseline), load(args.widened), load(args.repeat)
    print(f"\n{'=' * 78}\nG2(b) GATE -- band {args.band}  f_min={args.f_min} "
          f"f_max={args.f_max}\n{'=' * 78}")
    for leg in (base, wide, rep):
        print(f"  {leg['label']:12s} sha={leg['dll_sha256'][:16]}... "
              f"shim={leg['shim_version']} files={leg['n_files']}")

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
    for role, leg in (("baseline", base), ("widened", wide), ("repeat", rep)):
        trunc = truncated_cycles(leg)
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
    # already asserts that) are drawn from the burned corpus at
    # --burned-wav-dir. The OLD per-leg `if wav_dir != burned_dir: continue`
    # made a --burned-wav-dir typo silent: every leg `continue`d, "P2 legs
    # ok" printed, and the floor was never applied -- indistinguishable from
    # the correct, common case where zero legs SHOULD match (an un-burned
    # corpus). Declaring the expected answer up front and checking it against
    # what the legs actually are turns that silence into ROW 0, in EITHER
    # direction: declared burned but the legs are not, or declared un-burned
    # but they are.
    burned_wav_dir_norm = os.path.normcase(os.path.realpath(args.burned_wav_dir))
    legs_share_one_corpus = (len(provenance) == 3
                              and len(set(provenance.values())) == 1)
    n_floor_applied = 0
    if legs_share_one_corpus:
        legs_wav_dir_norm = next(iter(provenance.values()))[0]
        legs_are_burned = legs_wav_dir_norm == burned_wav_dir_norm
        if args.burned_corpus == "yes" and not legs_are_burned:
            p2.append(f"--burned-corpus yes was declared, but the legs are "
                       f"drawn from {legs_wav_dir_norm!r}, not "
                       f"{burned_wav_dir_norm!r} ({args.burned_wav_dir}) -- "
                       f"the held-out floor was never applied")
        elif args.burned_corpus == "no" and legs_are_burned:
            p2.append(f"--burned-corpus no was declared, but the legs are "
                       f"drawn from the burned corpus {burned_wav_dir_norm!r} "
                       f"({args.burned_wav_dir}) -- the operator declared an "
                       f"unburned corpus and handed the gate the burned one")
        elif args.burned_corpus == "yes":  # and legs_are_burned
            for role, cycles in (("baseline", cycles_base),
                                  ("widened", cycles_wide),
                                  ("repeat", cycles_rep)):
                if not cycles:
                    continue
                n_floor_applied += 1
                leg_min = min(cycles)
                if leg_min <= args.held_out_from:
                    p2.append(f"{role} leg is drawn from the burned run "
                               f"({args.burned_wav_dir}) and its earliest "
                               f"cycle {leg_min} does not exceed the "
                               f"held-out floor {args.held_out_from} -- the "
                               f"burned leg must not be read")
        # else: --burned-corpus no, legs genuinely not burned -- correct,
        # common case; the floor does not apply and nothing is checked.
    # else: provenance is incomplete or the legs disagree on wav_dir/window/
    # start_cycle -- already flagged above and ROW 0 fires regardless; the
    # burned-corpus declaration cannot be evaluated against an unconfirmed
    # corpus, so it is not (n_floor_applied stays 0, printed honestly below).

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

    if p2 or p3_fired:
        print("\n  ROW 0 -- NO READ. A precondition failed; the quantity is not an "
              "estimate of what this gate names. Do not interpret the numbers below.")
        write_verdict(args.emit_verdict, build_verdict(
            args.band, args.f_min, args.f_max, "ROW_0",
            scope=None, p1_fired=None, rates=None, bounds=None, bars=bars))
        return 0

    # ── The measurement ──────────────────────────────────────────────────────
    rows = per_cycle_terms(base, wide, args.f_min, args.f_max, av_all)
    r = rates(rows)
    # A8/B5: d_base is now simply rates()'s own denominator, computed from the
    # SAME (already AV-excluded) `rows` -- not an independently recomputed
    # figure from phys_by_cycle(base) that could silently drift from it.
    d_base = sum(row[4] for row in rows)

    if av_all:
        print(f"\n  AV cycles excluded from every rate (B5 fix): {len(av_all)} "
              f"cycle(s) where the shim's SEH caught a native access "
              f"violation on at least one leg")

    g_high_total = sum(row[1] for row in rows)

    # A1/A6 fix: P1 is now an OBSERVED-count check (A6), and it determines
    # whether the high end is adjudicated AT ALL (A1) -- previously it fired
    # into printed text only, which made it diagnostic-only and refusal-grade
    # under HK-025.
    p1_fired = g_high_total < MIN_HIGH_BAND_OBSERVATIONS
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

    # B3 fix: ONE bootstrap pass, four metrics, g_low and g_high NEVER pooled.
    bounds = bootstrap_bounds(rows, {
        "g_low": (lambda rr: rr["g_low"], 0.05),
        "g_high": (lambda rr: rr["g_high"], 0.05),
        "churn_net": (lambda rr: rr["churn_net"], 0.05),
        "churn_gross": (lambda rr: rr["churn_gross"], 0.95),
    })
    g_low_lo = bounds["g_low"]
    g_high_lo = bounds["g_high"]
    churn_net_lo = bounds["churn_net"]
    churn_gross_hi = bounds["churn_gross"]

    print(f"\n  G_new (low-band)  = {r['g_low'] * 100:+.3f}%  "
          f"(95% lower {g_low_lo * 100:+.3f}%, bar {args.g_new_min_rate * 100:+.2f}%)")
    if not p1_fired:
        print(f"  G_new (high-band) = {r['g_high'] * 100:+.3f}%  "
              f"(95% lower {g_high_lo * 100:+.3f}%, "
              f"bar {args.g_high_min_rate * 100:+.2f}%)")
    print(f"  churn net  = {r['churn_net'] * 100:+.3f}%  "
          f"(95% lower {churn_net_lo * 100:+.3f}%, "
          f"bar {args.churn_net_min_rate * 100:+.2f}%)")
    print(f"  churn gross = {r['churn_gross'] * 100:+.3f}%  "
          f"(95% upper {churn_gross_hi * 100:+.3f}%, "
          f"bar {args.churn_gross_max_rate * 100:+.2f}%)")

    # B3 fix: g_low is barred against its own floor ALWAYS -- it is never
    # pooled with g_high, and its floor is never diluted by the high band's
    # contribution. g_high, when adjudicated, gets its own separate floor and
    # decides SCOPE only, never whether the rung passes.
    g_ok = g_low_lo >= args.g_new_min_rate
    high_adjudicated = not p1_fired
    high_ok = high_adjudicated and (g_high_lo >= args.g_high_min_rate)
    net_ok = churn_net_lo >= args.churn_net_min_rate
    gross_ok = churn_gross_hi <= args.churn_gross_max_rate

    if p1_fired:
        scope = (" (LOW END ONLY -- P1 fired, the high end is NOT adjudicated; "
                 f"licensed consequence is [{args.f_min}, {OLD_F_MAX}) only)")
    elif high_ok:
        scope = (f" (both ends adjudicated and both clear; licensed "
                 f"consequence is [{args.f_min}, {args.f_max}))")
    else:
        scope = (" (LOW END ONLY -- high end adjudicated but did not clear "
                 f"its own floor; licensed consequence is "
                 f"[{args.f_min}, {OLD_F_MAX}) only)")

    # ── Rows, in strict order, mutually exclusive ────────────────────────────
    # A10 fix: ROW 0d is now reachable for a NAMED reason -- gross churn fails
    # its ceiling (the same ceiling ROW 2 tests -- B6 fix, no second tier is
    # claimed) landing together with a mechanism that does not clear its own
    # bar. That combination is worse than a plain "mechanism underdelivers"
    # (ROW 3) and worse than "mechanism confirmed, perturbation real" (ROW 2,
    # which requires the mechanism to have cleared its bar). It gets its own
    # stop.
    if not g_ok and not gross_ok:
        row_id = "ROW_0d"
        print(f"\n  ROW 0d -- CATCH-ALL, reached for a named reason (A10): the "
              f"mechanism does not clear its own bar AND gross churn exceeds "
              f"its ceiling{scope}. Both bars failed together, against the "
              f"SAME gross-churn ceiling ROW 2 tests (B6 fix: no distinct "
              f"severity tier is claimed here); it reaches this row rather "
              f"than ROW 2 only because the mechanism ALSO failed. STOP and "
              f"escalate; do not improvise a reading.")
    elif g_ok and net_ok and gross_ok:
        row_id = "ROW_1"
        print(f"\n  ROW 1 -- ELIGIBLE{scope}. The mechanism clears its own "
              "pre-committed floor and both churn metrics are bounded. The "
              "Captain chooses among eligible rungs; this gate does not.")
    elif g_ok and (not net_ok or not gross_ok):
        row_id = "ROW_2"
        reason = []
        if not net_ok:
            reason.append("net churn exceeds its floor")
        if not gross_ok:
            reason.append("gross churn exceeds its ceiling")
        print(f"\n  ROW 2 -- MECHANISM CONFIRMED, PERTURBATION REAL "
              f"({'; '.join(reason)}){scope}. Do NOT ship the raw widening. "
              "Escalate decoupling the noise-floor estimate from the passband "
              "as its own change; the widening returns on top of it.")
    elif not g_ok:
        # C5 fix: the previous rule ("family closes only if the WIDEST rung
        # reads ROW 3") let the thinnest-margin rung -- the raw WAV shows this
        # IS the widest rung, by construction of the ladder -- close the whole
        # family alone, discarding a passing narrower rung. This invocation
        # sees one rung only and cannot perform a cross-rung adjudication;
        # ROW 3 is now evidence about this rung's width, full stop.
        row_id = "ROW_3"
        print(f"\n  ROW 3 -- this rung does not deliver{scope}. This is "
              "evidence about THIS rung's width only. Per the repaired "
              "combination rule (C5): the passband family closes only if NO "
              "rung reads ROW 1 or ROW 2 -- a separate adjudication made "
              "after all three rungs have run, not by this invocation alone.")
    else:
        # Structurally unreachable given the branches above are exhaustive over
        # (g_ok, gross_ok) x net_ok; kept as a safety net, same discipline A10
        # applied to the previous unreachable branch -- if this ever prints, that
        # is itself a finding to report, not a row to trust. Marked ROW_0d in
        # the verdict too (D2): g2b_family.py refuses on ROW_0d, so an
        # adjudicator can never silently treat this defect as real evidence.
        row_id = "ROW_0d"
        print("\n  ROW 0d -- CATCH-ALL, reached via the UNEXPECTED branch (should "
              "be structurally unreachable). STOP and escalate; report this as a "
              "gate defect, do not improvise a reading.")

    write_verdict(args.emit_verdict, build_verdict(
        args.band, args.f_min, args.f_max, row_id, scope.strip(), p1_fired,
        rates=r, bounds=bounds, bars=bars))
    return 0


if __name__ == "__main__":
    sys.exit(main())
