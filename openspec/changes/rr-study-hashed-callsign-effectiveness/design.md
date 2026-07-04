## Context

`qa/rr-study/` is a from-scratch, independently-implemented R&R (repeatability/reproducibility)
harness that plays synthetic FT8 signals through a live VB-CABLE audio loopback into WSJT-X and
OpenWSFZ running concurrently, aligned to real 15-second FT8 cycle boundaries
(`run_scenario.py`'s `_next_cycle_boundary`/`_wait_for_cycle`), and scores each app's decode
output against injected ground truth (`analyse.py`). Each existing scenario (S1–S8) plays one or
more signals summed into a single independent "part" (one cycle), scores that part's decode
result against its own truth row, and moves on — there is no existing concept of a *pair* of
parts where the second part's correct score depends on what happened in the first.

The synth encoder (`qa/rr-study/synth/packing.py`) is deliberately a second, independent
implementation of the FT8 packing spec (Franke/Somerville/Taylor, QEX 2020) — not a port of
`ft8_lib`/`ft8_shim.c` — so that the R&R study's ground truth is not circular (the QA synth is a
test oracle, not a decoder-implementation clone; see `MEMORY.md`'s architecture note). It
currently supports only Type-1 standard messages and explicitly raises `NotImplementedError` for
non-standard/hashed callsigns (`_pack_callsign`'s docstring, module docstring line 15–18).

`f-001-hashed-callsign-resolution`'s own test suite (native shim + a managed-pipeline test)
already proves the resolution *mechanism* is deterministic once a Type 4 announcement has been
decoded. What it cannot prove — because its tests hand-pack signals and feed them directly to
`Ft8LibInterop.DecodeAll`/`Ft8Decoder.DecodeAsync`, never through a live audio channel — is
whether a genuine Type 4 announcement decodes reliably often enough, under realistic noise, for
the feature to matter in practice. That is squarely an R&R-study-shaped question, not a unit-test
question.

## Goals / Non-Goals

**Goals:**
- Add an independent (non-`ft8_lib`-derived) Type 4 packer and `ihashcall` hash function to the
  QA synth encoder, so R&R scenarios can construct a genuine announce message and a genuine
  hash-reference message for the same nonstandard callsign.
- Give the harness a way to express and play a **linked two-cycle scenario** — an announcement in
  cycle *N*, a hash reference in cycle *N+k* — and score a **"resolved"** outcome against the
  second cycle's decode text, independently of (but building on) the existing
  decoded/not-decoded scoring.
- Keep the two scientific questions this capability measures explicitly separate, because they
  have different maturity and different answers are expected:
  1. **Type 4 decode rate under realistic SNR** — genuinely unknown; worth a proper
     statistically-powered sweep, following the existing S1/S2 decode-rate methodology.
  2. **Resolution given a decoded announcement** — already proven deterministic by unit tests;
     needs only a thin confirmatory check (does it still hold end-to-end over a real audio
     channel), not a full statistical study.
- Do not disturb any existing scenario (S1–S8), their scoring, or their trend data.

**Non-Goals:**
- Re-validating `f-001-hashed-callsign-resolution`'s already-merged, already-unit-tested native
  table mechanism itself (persistence, eviction, AV-safety) — out of scope, already closed.
- Re-litigating D-011 (a different, already-resolved defect) — referenced only as prior informal
  evidence that resolution works on real traffic.
- Extending `Ft8CallsignPacker` (C#) / AP-assist for nonstandard callsigns — that is
  `f-001-hashed-callsign-resolution`'s own deferred "Gap B," unrelated to this measurement
  tooling.
- Modelling every possible gap *k* between announce and reference cycles. The native table's
  persistence is not time-limited (Non-Goal already established in `f-001`'s own design: no
  decay, only capacity-bounded eviction), so an arbitrarily large *k* tests the same code path as
  a small one. One or two representative gaps are enough; this is not a timing-sensitivity study.

## Decisions

### D1 — Two separate scenario/analysis paths, not one blended metric

Rather than inventing a single composite "end-to-end success rate," measure the two questions
independently:
- A **decode-rate sweep** for the Type 4 message class, following the existing S1/S2-style
  bias/decode-rate scenario shape (single independent parts, varying SNR, scored purely on
  "was `CQ <nonstandard-call>` decoded correctly") — reusing `analyse.py`'s existing
  `_analyse_decode_rate`-style pattern (each scenario type gets its own bespoke analyser function
  per the established convention: `_analyse_compounding`, `_analyse_band_scene`,
  `_analyse_decode_rate`), rather than the new linked-cycle logic.
- A **linked-cycle resolution scenario** (this proposal's main new mechanism) at one or two fixed,
  comfortably-decodable SNR points (e.g. the existing corpus's "clean" reference level plus one
  moderate-noise point), whose only job is confirming "resolved" fires correctly over a live
  channel — not characterising a decode-rate curve, since that curve is already covered by the
  first path.

Alternative considered: one combined scenario sweeping SNR and reporting a single "resolved / not
resolved" rate that conflates "announcement didn't decode" with "announcement decoded but wasn't
resolved." Rejected — conflating the two would make a low resolution rate uninterpretable (is the
table broken, or did OSD/LDPC just not decode the announcement at that SNR?), and the table side
is already known-good from unit tests, so paying for a full statistical sweep on it buys nothing.

### D2 — Harness: an explicit two-part "pair" scenario shape, not implicit adjacency

Rather than assuming "part N+1 always references part N" (fragile — scenario authors reorder,
skip, or `--parts`-filter parts routinely, per `run_scenario.py`'s existing `--parts 0,2,5`
support), the new scenario JSON schema explicitly declares each pair:

```json
{
  "id": "S9",
  "name": "Hashed-callsign cross-cycle resolution",
  "pairs": [
    {
      "pair_index": 0,
      "announce":  {"msg_id": "TYPE4-ANNOUNCE", "freq_hz": 1500, "snr_db": 0},
      "reference": {"msg_id": "TYPE1-HASHREF",  "freq_hz": 1500, "snr_db": 0, "gap_cycles": 1}
    }
  ]
}
```

`gap_cycles` controls how many intervening (otherwise-silent, per Non-Goals) cycles separate the
two plays. The harness plays `announce`, waits `gap_cycles` cycle boundaries, plays `reference`,
and writes **one truth row covering the pair** (not one per part) carrying both messages' truth
plus a `resolved_expected=true` flag, so `analyse.py` can join the pair's two decode outcomes
without needing to infer pairing from part-index adjacency.

Alternative considered: reuse the existing `parts` array with an implicit "next part references
this one" convention keyed off a new field. Rejected as too easy to silently break under
`--parts` filtering or scenario-file editing; an explicit `pairs` array with both halves named in
one object is harder to misuse.

### D3 — Scoring: a new "resolved" boolean, computed by text-matching the reference cycle's decode output

`analyse.py` gains a new per-pair analyser (`_analyse_hashed_callsign_resolution`, following the
existing one-function-per-scenario-type convention) that:
1. Confirms the announce cycle decoded the full nonstandard callsign (reusing the existing
   text-match logic already used for standard messages).
2. Confirms the reference cycle decoded *some* message referencing the same QSO, then checks
   whether the decoded text contains the resolved callsign (success) or the placeholder /
   nothing at all (not resolved) — matching the same text-based approach
   `HashedCallsignResolutionTests` already uses on the native-test side (`Message.Contains(...)`
   equivalent in Python), rather than needing any new instrumentation on the app side.
3. Reports resolution rate **conditional on the announce cycle having decoded**, per D1, so a low
   number is unambiguous.

Alternative considered: query some new app-exposed diagnostic (e.g. exposing
`g_hash_table_reject_count` via a new P/Invoke surface, raised as an Open Question in `f-001`'s
own `design.md`) instead of text-matching decode output. Rejected for this change — it would
require reopening `f-001`'s already-shipped, already-merged native surface for a measurement this
proposal can already make from black-box decode-text comparison, which is exactly how every other
R&R scenario already scores correctness.

### D4 — Independent packer, not a shared implementation with `ft8_shim.c`

Per the existing QA-synth attestation convention (`packing.py`'s own module docstring: "No
algorithmic code has been ported from any encoder/decoder implementation"), the new Type 4/
`ihashcall` code must be written independently from the published protocol description
(Franke/Somerville/Taylor, QEX 2020, plus the `ihashcall` formula as documented in
`f-001-hashed-callsign-resolution/design.md`'s Context section), not copied or transliterated
from `ft8_shim.c`. This preserves the study's evidentiary value — a bug shared between the synth
encoder and the shim under test would otherwise silently cancel out.

## Risks / Trade-offs

- **[Risk] Type 4 decode rate turns out to be poor at realistic SNR**, independent of anything
  this change controls (an OSD/LDPC property of the message class, not a defect in `f-001`'s
  table). → **Mitigation**: this is exactly the finding this capability exists to surface;
  D1 already separates it from the resolution-mechanism question so a poor result is
  interpretable and actionable (e.g. feeds a future AP-assist prioritisation decision, tying back
  into `f-001`'s deferred Gap B) rather than being mistaken for a table bug.
- **[Risk] Live-rig time is scarce** (VB-CABLE loopback, both apps running concurrently, an
  operator present) — same constraint that got `f-001`'s own task 5.3 deferred. →
  **Mitigation**: D1's split means the confirmatory resolution check (the cheaper half) can run
  first and alone if rig time is short; the full decode-rate sweep can be scheduled separately
  whenever there is appetite, without blocking the confirmatory result.
- **[Trade-off] `gap_cycles` sweep is deliberately shallow** (Non-Goal) — if the native table
  ever grows a time-based decay policy (contradicting its current no-decay design), this
  harness extension would need revisiting. Acceptable: no such change is proposed or planned
  anywhere in `f-001`'s own design.
- **[Risk] New pair-truth schema diverges from the existing per-part truth-row schema**, adding a
  second truth shape `analyse.py` must handle. → **Mitigation**: scoped to its own analyser
  function (D3), matching the existing precedent that S7/S8 already have their own
  bespoke analysis paths distinct from the generic ANOVA path — this is additive, not a rework
  of the common schema.

## Migration Plan

- Purely additive: new synth functions, a new scenario JSON, a new harness code path gated on the
  new `pairs` key (absent from every existing scenario file, so S1–S8 take the existing code path
  unchanged), and a new `analyse.py` analyser function. No existing scenario, result, or trend
  file is touched.
- Rollback is a straight revert; no persisted state, no schema migration for existing results.
- Roll-out order: (1) synth packer + unit tests (`test_packing.py`) — no rig needed; (2) harness
  `pairs` support + new analyser — no rig needed, exercisable via `--dry-run` per the existing
  harness convention; (3) the confirmatory resolution run (D1, cheap) — needs rig time; (4) the
  full Type 4 decode-rate sweep (D1, the real investment) — needs rig time, schedule
  independently once (3) is in hand.
- Report authored per the existing convention: `render_report.py`, QA-authored Sections 1/5 (+2
  framing) once a live run produces a `report.md` (per `MEMORY.md`'s HK-001 note).

## Open Questions

- Exact SNR sweep points and sample size for the Type 4 decode-rate path (D1, path 1) — should
  mirror an existing S1/S2 design rather than be invented fresh here; confirm which existing
  scenario file is the closest template at implementation time.
- Whether one `gap_cycles` value (e.g. 1) is sufficient for the confirmatory check, or whether a
  second, larger value (e.g. 5) is worth the extra rig time to also touch "other traffic decoded
  in between" as a basic sanity check — recommend starting with one and adding a second only if
  the first raises a question.
- Naming: this design uses `S9` as a placeholder scenario ID; confirm the next free scenario ID
  against `qa/rr-study/scenarios/` at implementation time (S8 is the highest existing ID as of
  this proposal).
