## 1. Synth encoder — Type 4 packing + `ihashcall` (D1/D4)

- [x] 1.1 Implement Type 4 (`i3=4`) full-text nonstandard-callsign packing in
      `qa/rr-study/synth/packing.py`, independently from the published protocol description
      (Franke/Somerville/Taylor QEX 2020) and `f-001-hashed-callsign-resolution/design.md`'s
      Context section — NOT ported from `ft8_shim.c` (design D4). Reuses the existing 38-char
      alphabet already defined for the `/R`/`/P` rover flag handling where applicable.
      Done via `pack_type4_announce` (CQ-form only; the shape the linked-pair scenario needs).
      Exact field widths (12+58+1+2+1+3=77) confirmed against the real `ft8_lib` reference
      source recovered from the orphaned submodule's git history (`.git/modules/native/ft8_lib`
      — `ft8/message.c`, `ftx_message_encode_nonstd`/`pack58`/`unpack58`, and the public
      `ft4_ft8_public/hashcodes.f90`), by inspection only — no code copied/transliterated.
- [x] 1.2 Implement the 22-bit `ihashcall` hash function per the published formula.
      Done as `ihashcall()`; also derives the 12/10-bit widths (top-bits shift), matching the
      published relationship.
- [x] 1.3 Extend `_pack_callsign` (or add a parallel path) so a nonstandard-shaped callsign packs
      into the `NTOKENS ≤ n28 < NTOKENS + MAX22` hash sub-range instead of raising
      `NotImplementedError`, leaving all existing standard-callsign behaviour unchanged.
      Note: this closes a real gap in the OLD behaviour — a callsign with no digit position but
      length in [3,11] (e.g. "AAAAA") previously raised `ValueError`; it now correctly falls back
      to hash encoding, matching the real protocol's own `pack28`. One existing test
      (`test_invalid_callsign_format_raises`) asserted the old (incomplete) behaviour and was
      updated with an explanatory note + a new test documenting the change.
- [x] 1.4 Add a committed shared test vector (fictional Q-prefix callsign → expected 22-bit hash)
      cross-checked against `ft8_shim.c`'s own `ihashcall` implementation by inspection (not by
      calling into the native shim from Python — the two must stay independent implementations
      per D4), to catch a transcription error in either without coupling the two at runtime.
      Test vector: "Q0ABCDEF" → h22=2523336, h12=2464, h10=616 (hand-derived; cross-checked by
      inspection against `hashcodes.f90`/`message.c`'s `save_callsign`, recovered from the
      orphaned ft8_lib submodule's git history since ft8_shim.c itself delegates to the vendored
      library rather than implementing ihashcall inline).
- [x] 1.5 Add unit tests in `qa/rr-study/tests/test_packing.py`: Type 4 packing round-trip,
      `ihashcall` determinism and the shared test vector, hash-reference packing for a
      nonstandard callsign in a standard-message context, and confirmation that existing
      standard-callsign test cases are unaffected. 70/70 packing tests pass; full suite
      150/150 pass (no regression).

## 2. Harness — linked-pair scenario support (D2)

- [x] 2.1 Design and implement the `pairs` scenario-file schema in
      `qa/rr-study/harness/run_scenario.py` (announce/reference signal definitions,
      `gap_cycles`), per design.md's D2 example shape.
      Implemented exactly per the D2 example shape (`gap_cycles` nested under `reference`).
- [x] 2.2 Implement linked-pair playback: play `announce` at cycle *N*, silence for
      `gap_cycles - 1` intervening cycles, play `reference` at cycle *N + gap_cycles*, reusing
      the existing `_next_cycle_boundary`/`_wait_for_cycle` alignment mechanism.
      `_run_pairs`/`_cycle_boundary_utc` reuse the existing alignment helpers unchanged.
- [x] 2.3 Implement the per-pair truth-row schema (both messages' truth fields plus
      `resolved_expected`), distinct from the existing per-part truth schema, written alongside
      (not replacing) the existing truth CSV columns.
      `_PAIR_TRUTH_EXTRA_COLUMNS` appended to `_TRUTH_COLUMNS`; existing per-part rows leave
      the new columns blank via `csv.DictWriter`'s `restval`.
- [x] 2.4 Confirm existing `parts`-based scenarios (S1–S8) are unaffected: run at least one
      existing scenario in `--dry-run` mode before and after this change and diff the output.
      S1 `--dry-run` (part 0) diffed byte-for-byte before/after (git HEAD vs. working tree):
      identical print order and identical truth.csv data for every pre-existing column; only
      the new (blank) pair columns are appended.
- [x] 2.5 Add a `--dry-run`-exercisable path for the new `pairs` schema so the harness/synth
      integration can be validated without live-rig time (per design.md's Migration Plan
      roll-out ordering).
      Verified via `scenarios/s9-hashed-callsign-resolution.json --dry-run`: both pairs (2
      SNR points x 5 trials) played and truth rows written correctly with all fields populated.

## 3. Analysis — "resolved" outcome (D1/D3)

- [x] 3.1 Add `_analyse_hashed_callsign_resolution` (or similarly named) to
      `qa/rr-study/harness/analyse.py`, following the existing one-analyser-per-scenario-type
      convention (`_analyse_compounding`, `_analyse_band_scene`, `_analyse_decode_rate`).
      Note: unlike every other analyser, this one is NOT `*_matched.csv`-driven — a pair's truth
      row spans two decode cycles, which doesn't fit matcher.py's one-row-per-message model — so
      it reads truth.csv's pair rows + the raw WSJT-X/OpenWSFZ ALL.TXT logs directly (own
      slot-bucketed text/freq matching, same black-box approach every other scenario uses).
- [x] 3.2 Implement conditional scoring: announce-cycle decode rate reported separately from
      reference-cycle resolution rate, with the resolution rate's denominator restricted to
      pairs where the announcement decoded (spec requirement: distinguishable "not resolved" vs
      "announcement never decoded").
      Three distinguishable per-pair outcomes when announce decoded: resolved /
      not_resolved_placeholder / reference_not_decoded, plus announce_not_decoded when the
      announce cycle itself didn't decode (excluded from the resolution-rate denominator).
- [x] 3.3 Implement report-lines rendering for the new analyser, following the existing
      `_compounding_report_lines`/`_band_scene_report_lines`/`_decode_rate_report_lines`
      convention, wired into `_write_report`/`_collect_verdicts`.
      `_hashed_callsign_resolution_report_lines` wired into `_write_report` (new `hcr_results`
      param) and `main()`; informational only (no PASS/FAIL verdict, matching S7/S8/decode-rate
      convention) — the table mechanism itself is already gated by f-001's own unit tests.
      Verified end-to-end via a synthetic run directory (fabricated truth.csv + ALL.TXT logs,
      `analyse.py --run-dir ... --scenario S9` produces a correct report.md section + chart).
- [x] 3.4 Add unit-level test coverage for the new analyser function using a small synthetic
      matched-CSV fixture (mirroring existing `analyse.py` test conventions), independent of a
      live run.
      `tests/test_analyse_hashed_resolution.py` — 6 tests (resolved vs. placeholder
      distinguished, announce-not-decoded excluded from denominator, reference-not-decoded
      distinguished from placeholder, empty/missing-log edge cases, truth-row filtering).

## 4. Scenario definition & documentation

- [x] 4.1 Confirm the next free scenario ID against `qa/rr-study/scenarios/` at implementation
      time (design.md notes S8 is highest as of this proposal; placeholder used throughout this
      change's artifacts is "S9" — confirm and rename if a scenario has landed in the interim).
      S9 confirmed free against `scenarios/`. IMPORTANT finding: the D1-path-1 decode-rate
      scenario could NOT use "S10" as originally planned — `STUDY-SPEC.md` §17 already reserves
      S10 for a deferred "QSO Context-Awareness Study". Renamed to **S11** throughout (scenario
      file, `analyse.py`'s `DECODE_RATE_SCENARIOS`/`DECODE_RATE_CONFIG`, study-messages.json,
      docstrings/comments) before any of it was committed.
- [x] 4.2 Author the linked-pair scenario JSON file: one or two SNR points for the confirmatory
      resolution check (D1 path 2), following design.md's guidance to keep this thin.
      `scenarios/s9-hashed-callsign-resolution.json` — 2 pairs (0 dB, -10 dB), gap_cycles=1,
      5 trials; verified via `--dry-run`.
- [x] 4.3 Author a separate Type-4-decode-rate scenario JSON file (D1 path 1), modelled on the
      closest existing S1/S2-style decode-rate scenario — confirm the closest template at
      implementation time per design.md's Open Questions.
      `scenarios/s11-type4-decode-rate.json`, modelled directly on `s1b-snr-threshold.json`
      (closest template: same parts/fixed/analysis shape); adds `"message_kind": "type4"`,
      handled by a small addition to `_render_single` — no new analyser needed, reuses
      `_analyse_decode_rate` exactly as D1 specifies. Verified via `--dry-run`.
- [x] 4.4 Add a new scenario methodology section to `qa/rr-study/STUDY-SPEC.md` documenting both
      new scenarios, their response variables, and the D1 rationale for keeping them separate.
      New §6.3 "S9 / S11 rationale — hashed-callsign cross-cycle resolution", plus two new rows
      in the §6 scenarios table.

## 5. Live-rig execution (requires the Captain's operating position)

- [x] 5.1 Run the confirmatory linked-pair resolution scenario (cheaper, per design.md's
      Migration Plan ordering) via VB-CABLE loopback with WSJT-X and OpenWSFZ decoding
      concurrently.
      Run 2026-07-04, `results/2026-07-04-22c3a94/` (shim/SHA `22c3a94`, WSJT-X 2.7.0 b4f9a4).
      S9: 2 pairs × 5 trials = 10 pairs, both SNR points (0 dB, −10 dB). **Result: 100% resolved,
      both appraisers, all 10 pairs** — every reference cycle showed the correctly-resolved
      callsign (WSJT-X and OpenWSFZ decode text identical). See report §1/§5, finding 2.
      A genuine QA-harness defect was found and fixed live during this run (see 5.3 note below).
- [x] 5.2 Run the Type 4 decode-rate sweep scenario — schedule independently; not required to
      unblock 5.1's result.
      Same session/run directory. S11: 5 SNR points (−15…0 dB) × 5 trials = 25 cycles.
      **Result: 100% decode rate, both appraisers, at every SNR point including −15 dB.**
      No evidence of a Type 4 message-class decode-rate penalty versus the standard message
      class at these operating points. See report §1/§5, finding 2.
- [x] 5.3 Render the report via `render_report.py`; QA authors Sections 1/5 (+2 framing) per the
      existing HK-001 convention before committing `report.md`/`report.html` under a dated
      `qa/rr-study/results/` directory.
      `results/2026-07-04-22c3a94/report.md` + `.html` committed. **Live-rig finding: a real bug
      was caught and fixed in this change's own analyser** — `_analyse_hashed_callsign_resolution`
      matched "resolved" against the bare reference text, but the real, ratified decode format
      (confirmed against the recovered `ft8_lib` reference source, `message.c`'s
      `lookup_callsign`/`add_brackets`) wraps *every* hash-lookup result in `<>`, resolved or not
      — so this run initially scored 0/10 resolved before the fix (misclassified
      `reference_not_decoded`). Fixed in `analyse.py` (accepts the bracketed form; bare form kept
      as a defensive fallback) with a new regression test,
      `test_bracketed_resolved_form_is_recognised` (157/157 suite green after the fix). This is a
      harness-only defect — `f-001`'s shipped mechanism was correct throughout; the live data is
      what exposed the harness's wrong assumption, exactly the value this capability exists to
      provide. Also fixed: 3 noise-floor false-CRC decode lines scrubbed from `owsfz-all.txt`
      before commit per `RUNBOOK.md` §7.5 / NFR-021 (coincidental AWGN CRC-14 passes, not real
      traffic, but callsign-shaped — none were synthetic Q-prefix calls).
- [x] 5.4 Record the outcome in this change's own notes (and cross-link from
      `f-001-hashed-callsign-resolution`'s `tasks.md` §4a.3, which currently tracks this work as
      not-started) before archiving this change.
      Outcome: both effectiveness questions D1 separates came back positive at N=10/N=25 —
      Type 4 decodes as reliably as standard messages at every SNR tested, and cross-cycle
      resolution held for every trial over live audio. f-001's tasks.md §4a.3 cross-linked below.

## 6. Regression

- [x] 6.1 Run the full existing `qa/rr-study` test suite (`pytest qa/rr-study/tests/`) to confirm
      no regression from the synth/harness/analyser changes.
      156/156 pass (150 pre-existing + 6 new, `test_analyse_hashed_resolution.py`) — run
      repeatedly throughout implementation, final pass clean.
- [x] 6.2 Re-run at least one existing scenario's `--dry-run` output and diff against
      pre-change output (per 2.4) as a final confirmation before merge.
      Final confirmation (broader than 2.4's single-scenario check): diffed `--dry-run` truth.csv
      output for S1, S1b, S3b, S7, and S8 (single-signal, decode-rate, compounding, and
      band-scene shapes) against the branch-point baseline (`1fc57c6`). All five byte-identical
      on every pre-existing column; only cosmetic diffs (run-dir name, wall-clock dry-run
      timestamp) in stdout.
