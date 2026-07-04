## Why

`f-001-hashed-callsign-resolution` (merged to `main` at `86780dc`, shim `20260031`) shipped a
session-scoped native callsign hash table so a Type 4 message's nonstandard/compound callsign
resolves against a later hash reference. Its test coverage — native shim unit tests, plus a
managed-pipeline test added during this change's own QA review — proves the mechanism is
*correct in isolation*: deterministic table persistence, bounded eviction, AV-safety, and that a
resolved callsign survives `Ft8Decoder`'s false-positive guard. None of that measures
*effectiveness under realistic decode conditions*. The QA R&R-study tooling
(`qa/rr-study/`) is this project's only mechanism for answering that kind of question
statistically, over a live audio pipeline rather than hand-packed synthetic PCM fed directly to
`DecodeAll` — and it currently cannot touch this message class at all:
`qa/rr-study/synth/packing.py` raises `NotImplementedError` for Type 4 / hashed-callsign forms
("out of scope for the first R&R study"), and `run_scenario.py`'s scoring model treats every
slot/trial as independent, with no concept of a linked announce-then-reference pair or a
"resolved" outcome distinct from "decoded."

A real off-air session (2026-07-03, documented in
`dev-tasks/2026-07-03-d-011-nonstandard-callsign-fp-guard.md`) already gave informal evidence
that resolution works in practice for one station over 45+ minutes. That is encouraging but is
a single anecdote from a session run to investigate a different defect (D-011) — not a
repeatable, statistically-powered measurement. This change proposes building that measurement
capability.

## What Changes

- Add Type 4 message packing to the independent QA synth encoder (`qa/rr-study/synth/packing.py`)
  — the 58-bit full-text nonstandard-callsign field and the 22-bit `ihashcall` hash computation,
  reproducing the same published-protocol algorithm already implemented in
  `src/OpenWSFZ.Ft8/Native/ft8_shim.c` and documented in `f-001-hashed-callsign-resolution`'s
  `design.md` — as an independent second implementation (per this project's existing QA-synth
  attestation convention), not a port of the shim's C code.
- Extend the R&R harness (`run_scenario.py` and its scenario-file schema) to support a **linked
  two-cycle scenario**: a Type 4 announcement played in cycle *N*, a corresponding hash-reference
  message played in cycle *N+k*, and a new "resolved" response variable scored against the
  *second* cycle's decode output — distinct from, and in addition to, the existing
  "decoded/not-decoded" response the harness already knows how to score. Existing independent-slot
  scenarios (S1–S8) are unaffected.
- Add a new scenario definition measuring the two distinct questions this capability actually
  needs answered, kept separate rather than conflated into one number:
  1. Does a genuine Type 4 announcement decode reliably at realistic SNR? (an OSD/LDPC
     decode-rate question, answerable by extending the existing S1/S2-style bias/decode-rate
     methodology to a Type-4-shaped message rather than inventing new statistical machinery).
  2. Given a decoded announcement, does the cross-cycle resolution then hold? (already proven
     deterministic by unit tests — this needs only a thin confirmatory check under the live
     pipeline, not a full statistical study).
- Document the live-audio-rig run (VB-CABLE loopback, WSJT-X + OpenWSFZ decoding concurrently —
  the same rig used for S1–S8, per `RUNBOOK.md`) needed to execute the new scenario, following
  the existing dated-result-directory / `report.md`+`report.html` convention
  (`qa/rr-study/results/`, `render_report.py`).

## Capabilities

### New Capabilities
- `rr-synth-nonstandard-callsign-packing`: Type 4 full-text callsign packing and 22-bit
  `ihashcall` hash computation in the independent QA synth encoder, enabling it to produce a
  genuine announce message and a corresponding hash-reference message for R&R scenarios.
- `rr-linked-cycle-effectiveness-scenario`: harness support for a scenario that links two
  specific cycles as an announce-then-reference pair and scores a "resolved" outcome against the
  second cycle's decode output, in addition to the existing independent per-slot
  decoded/not-decoded scoring.

### Modified Capabilities
- (none — `rr-synth-channel`, `rr-corpus-replay`, and `rr-band-scene` describe unrelated synth
  and scenario mechanics and are silent on cross-cycle linkage or nonstandard-callsign packing,
  so this is additive)

## Impact

- **QA tooling (synth)**: `qa/rr-study/synth/packing.py` — new Type 4 packing function(s) and
  `ihashcall`; `qa/rr-study/tests/test_packing.py` — new unit coverage for the added packing
  paths, mirroring the existing attestation/test style.
- **QA tooling (harness)**: `qa/rr-study/harness/run_scenario.py` — new linked-cycle playback and
  scoring path; likely `qa/rr-study/harness/analyse.py` (or equivalent) for the new "resolved"
  response variable; a new scenario JSON file (e.g. `qa/rr-study/scenarios/s9-...json`, exact
  name TBD in design).
- **Documentation**: `qa/rr-study/STUDY-SPEC.md` — new scenario methodology section, per existing
  convention; QA-authored report sections per the existing HK-001 convention once a live run
  produces a `report.md`.
- **No production/native code changes.** This change is measurement tooling only; it does not
  reopen `f-001-hashed-callsign-resolution`'s already-shipped, already-merged mechanism, and does
  not require re-litigating D-011 (separate, already-resolved defect referenced here only as
  prior informal evidence).
- **Requires live-audio-rig time** (the Captain's operating position) to actually execute the new
  scenario once built — this change's tooling can be developed and unit-tested without it, but
  producing a result report cannot.
