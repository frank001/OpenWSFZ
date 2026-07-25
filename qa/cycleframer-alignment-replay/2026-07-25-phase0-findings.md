# Phase 0 findings — cycleframer-alignment-replay

> **Superseded 2026-07-26.** Closed alignment-replay work, retained as history; no live D-001
> lead. See `2026-07-26-0015-d001-consolidation-and-clean-slate.md`.

**Author:** QA session, 2026-07-25. **Scope:** SPEC.md Phase 0 (re-windowing self-test + the
four mandatory controls, section 7), on real off-air audio from
`artefacts/20260724_live_run_2227/wav/` (2,827 files, 15 segments — independently reproduced
the same segment/gap structure SPEC.md section 4 records). Decodes: 25 cycles (segment 0,
k=0..24) x 6 offsets (0, 2.0, 3.0, 5.0, 7.5, plus 3 repeats for determinism) = 129 total,
well inside the "~50" Phase 0 budget for the mandatory-gate portion.

Tooling built (all zero-`src/`, QA-scoped per HK-000): `rewindow.py` (segmentation +
offset-cutting, the one genuinely new capability per SPEC.md section 8), `score_recall.py`
(paired within-cycle recall scorer, SPEC.md 5.3), `determinism_check.py`. All reuse
`qa/rr-study/d001-param-sweep-2026-07-22`'s `D001ParamSweep` decode harness **completely
unmodified** — rewindowed audio is fed to it via the existing `--manifest` option, exactly as
SPEC.md section 8 predicted.

## Gate results

| Control | Result | Verdict |
|---|---|---|
| **Self-test** (delta=0 reproduces source sample-for-sample) | 2,827/2,827 windows across all 15 segments, byte-identical | **PASS** |
| **Shuffled-pairing** (cycle k's delta=0 decodes vs ref(k+7)) | median recall = 0.0000 exactly, all 25 cycles | **PASS** |
| **Determinism** (one real WAV decoded 4x in one process) | all 4 copies byte-identical (29 decodes each) | **PASS** |
| **Sensitivity** (delta=+2.0 vs delta=0) | median recall 0.9200 (IQR 0.878-0.957) vs 1.0000 baseline | **See below — not a clean pass on the literal SPEC.md wording** |

## The sensitivity control — diagnosis, not a rubber stamp

SPEC.md section 7.1 requires delta=+2.0s to show a "materially lower" median recall than
delta=0, on pain of voiding the whole study. 0.92 vs 1.00 does not obviously clear that bar,
so per the SPEC's own instruction ("if it does not, stop and diagnose") this was investigated
before accepting or rejecting it.

**Ruled out: repeated-message contamination.** Text-only message matching (SPEC.md 5.3) could
in principle inflate recall if a station retransmits an identical message across adjacent
cycles — a delta=2.0 window could pick up cycle k+1's copy and still count it as a "hit" on
cycle k. Checked directly: of 585 reference messages across the 25 cycles, **zero** recur
verbatim in an adjacent cycle, and of the 535 delta=2.0 hits, **zero** are attributable to this
mechanism. Not the explanation.

**What it actually is: a cliff between 2.0s and 3.0s, not a gradual decline.**

| delta | median recall |
|---|---|
| 0.0 | 1.0000 |
| 2.0 | 0.9200 |
| 3.0 | 0.0769 |
| 5.0 | 0.0000 |
| 7.5 | 0.0000 |

The harness is unambiguously sensitive to alignment — recall collapses by 92% between delta=2.0
and delta=3.0 — it just isn't "materially lower" at exactly the single probe point (2.0s) the
control specifies. This lines up with SPEC.md's own stated rationale (section 5.2): ft8_lib's
internal time-offset search is bounded near +/-2.5s, so a 2.0s cut still falls mostly inside
that search range (FT8's LDPC coding also tolerates losing ~2s/~16% of a transmission's
symbols at strong SNR), while a 3.0s cut does not. The cliff sitting almost exactly where the
SPEC predicts the decoder's own search bound to be is, if anything, corroborating evidence that
the harness is measuring a real physical effect — not a sign that it is insensitive.

**This was not resolved unilaterally.** The literal control as written does not pass; the
underlying evidence argues the harness is sound and the control's single probe point was
mis-placed relative to where the real transition sits. Routing this judgment call to the
Captain rather than deciding it in this QA session — same convention as the CycleFramer
RateClock escalation (`qa/cycleframer-code-review/2026-07-25-decision9-review-and-rateclock-escalation.md`).

## Not yet built

- An orchestrating driver for the full 25-point sweep (Phase 1 needs this; Phase 0 was run via
  direct `rewindow.py`/harness/`score_recall.py` invocations per offset).
- The explicit refuse-if-ref-and-test-share-delta guard SPEC.md section 7.3 asks for — currently
  an implicit property of how each offset was invoked separately, not an enforced check. Needs
  building into the Phase 1 driver before that guard claim can be made honestly.
- The S-wide confirmation points (+/-3.5, +/-4.0) and the DT-baseline/live-mapping work
  (SPEC.md sections 5.2/6) — deferred pending the decision below.

## Recommendation

Treat the cliff-at-~2.5-3s finding as a pass on the *intent* of the sensitivity control (the
harness plainly can detect an alignment effect) while flagging that SPEC.md section 7.1's
probe point undersells how sharp the real transition is — worth noting for the eventual
recall(delta) curve write-up regardless. Recommend proceeding to Phase 1 on that basis, but
this is the Captain's call, not mine to make silently.
