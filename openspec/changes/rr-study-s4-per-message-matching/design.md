## Context

`qa/rr-study/RR-007.md` (GitHub #59) found that S4's truth generation
(`harness/run_scenario.py::_render_multi`) and matcher (`harness/matcher.py`'s S4
branch, lines ~161–177) pool every message injected into a cycle into a single truth
row, and score a match as "decoded *any one* of the N pooled messages." Live data (run
`793a298`) shows the resulting ceiling effect directly: both appraisers score a perfect
TP=15/FN=0, κ=1.000, PASS, while the same run's S7 (which already does per-message
matching correctly) shows OpenWSFZ recovering only 40% of co-channel stacks vs WSJT-X's
100%.

The good news, found while reading the surrounding code: **this exact problem was
already solved once, for S7 and S8.** Both scenarios' render functions
(`_render_compound`, `_render_band_scene`) return a `signals_meta` list — one dict per
injected signal, each carrying its own `message_text`, `freq_hz`, `dt_s`, `snr_db` — and
`_run()` writes one `truth.csv` row per signal for those two scenarios (see the
`is_s8`/`is_s7` branches around line 926–951 of `run_scenario.py`). `matcher.py`'s
*generic* matching path (the `else` branch at line 178, used whenever `true_freq_hz` is
non-empty) already matches each such row independently — this is exactly per-message
matching, already proven correct in production for S7 and S8. The special-cased "S4:
truth_msg is a pool" branch in `matcher.py` exists **only** because S4 is currently the
one scenario that supplies an empty `true_freq_hz` alongside a concatenated
message-pool string. S4 does not need a bespoke matching mechanism — it needs to stop
being the odd one out and adopt the pattern S7/S8 already use.

## Goals / Non-Goals

**Goals:**
- S4 truth generation emits one truth row per individual injected message (part,
  trial, message), each carrying that message's own `true_snr_db` and `true_freq_hz`.
- Each message is matched and scored independently (match/miss), eliminating the
  any-one-of-N ceiling effect.
- Re-use the existing, already-proven S7/S8 per-signal truth-row + generic-matcher
  path rather than inventing new machinery.
- Retire the now-unreachable S4-specific "pool" branch in `matcher.py`.
- Re-run S4 (live audio) once implemented and report real per-message recovery/κ
  figures, including an **informational** decodable-SNR-restricted κ variant (operationalising
  STUDY-SPEC.md §9.3 condition 2 for evaluation purposes).
- Keep `analyse.py`'s pooled-κ *method* (S4 positives + S5 negatives) and its advisory,
  non-gating status completely unchanged.

**Non-Goals:**
- Ratifying attribute-Kappa as a hard gate. That is a separate Captain decision;
  this change only makes it *possible to evaluate soundly*, per RR-007's recommendation.
- Any change to S1, S2, S3, S5, S7, S8's own truth/matching behaviour.
- Any change to the FP-rate gate, SNR-bias gate, or GR&R gates.
- Any product/application code change — this is QA test-harness-only work.
- Changing `s4-density.json`'s schema (`parts`, `n_signals`, `snr_db_set` fields are
  unchanged; only how the harness *consumes* them internally changes).

## Decisions

### D1 — Model S4 on the existing S7/S8 `signals_meta` + per-signal truth-row pattern
`_render_multi` gains a second return value, `signals_meta: list[dict]`, built the same
way `_render_band_scene`/`_render_compound` already build theirs (one dict per station:
`message_text`, `freq_hz`, `dt_s`, `snr_db`). `_run()` gains an `is_s4 and
s4_signals_meta is not None` branch in the truth-writing dispatch, structurally
identical to the existing `is_s7`/`is_s8` branches.

*Alternative considered:* keep the pooled truth row as-is and add a parallel
per-message "side channel" file just for the new analysis. Rejected — this would
duplicate truth-tracking machinery that already exists and works, doubling maintenance
surface for no benefit, and would not let S4 reuse the matcher's proven generic
per-row matching loop.

### D2 — Retire the S4-specific pool-matching branch in `matcher.py`, don't keep it dormant
Once no scenario emits `true_freq_hz == ""` with a non-empty pooled `message_text`, the
branch at `matcher.py` lines ~170–177 is dead code. It is deleted (not left in place
"just in case").

*Alternative considered:* leave the branch in place defensively, unreachable but
present. Rejected — an untested, unreachable special case is precisely the kind of
latent defect this whole investigation started from (S1's original ANOVA contamination
and now S4's ceiling effect were both scenario-specific special cases nobody was
re-examining). Deletion is safer than dormancy; git history preserves the old code if
ever needed.

### D3 — Add an informational decodable-SNR-restricted κ figure, without touching the gate
Once per-message `true_snr_db` exists for S4, `analyse.py` gains a second, clearly
labelled **informational** κ computation restricted to positives with `true_snr_db >=
-12` (the R&R-005-established decodable floor), reported alongside — not replacing —
the existing pooled κ. This directly operationalises STUDY-SPEC.md §9.3's second
ratification condition so the Captain has real numbers for it, without this change
unilaterally deciding ratification.

*Alternative considered:* leave the SNR-restriction question for a separate, later
change. Rejected — the per-message SNR data will already exist as a side effect of D1;
computing this one extra, informational figure is low-cost and directly serves the
Captain's original request to "investigate further," giving a complete picture in one
pass rather than two.

### D4 — No change to `s4-density.json`
The scenario file's `parts`/`n_signals`/`snr_db_set` shape is unchanged. Only
`_render_multi`'s internal handling changes (it already computes per-station `freqs[i]`
and `snr_list[i]` today — line 259–273 — it simply doesn't return them; D1 makes it do
so).

## Risks / Trade-offs

- **[Risk]** `S4_matched.csv` row count changes from 3/part to `n_signals × 3`/part
  (e.g. part 4: 3 → 90 rows/appraiser). Any external script assuming the old shape
  breaks. → **Mitigation:** grepped `analyse.py`, `full_stats.py`, `full_report_compute.py`
  for hardcoded S4 row-count assumptions during design; none found. Documented in
  `STUDY-SPEC.md` and `RR-007.md` as a deliberate, one-time shape change. Historical run
  artifacts under `results/*/` are untouched (read-only).
- **[Risk]** `_attribute_agreement`'s grouping key (`part_index, trial_index, cycle_utc,
  message_text`) was written assuming (and tolerating) a pooled string; feeding it ~13×
  more distinct rows per part could expose an untested assumption. → **Mitigation:** add
  a synthetic-data unit test in `analyse.py`'s test suite with a multi-message S4 part
  before relying on a live audio re-run; run the full existing suite (currently 92
  tests, confirm count at implementation time) with zero regressions required.
- **[Risk]** Validating the fix requires a live audio re-run (real WSJT-X + VB-CABLE),
  the same operational constraint every prior full-study run has had. → **Mitigation:**
  no different from existing practice (R&R-005's S1 redesign required the same);
  scheduled as an explicit task, not assumed to happen automatically in CI.
- **[Trade-off]** Deleting the S4 pool-matching branch (D2) means if a future scenario
  ever legitimately wants "matched if any-of-N" semantics, it must be reintroduced
  deliberately and tested — it will not silently still be there. This is considered a
  feature of the decision, not a cost.

## Migration Plan

1. Implement `run_scenario.py` (D1) and `matcher.py` (D2) changes.
2. Run the full `analyse.py`/`matcher.py` unit test suite; add the synthetic multi-message
   S4 regression test (risk mitigation above) before touching live audio.
3. `--dry-run` S4 to sanity-check `truth.csv`/`S4_matched.csv` shape without playing audio.
4. Schedule a live audio re-run covering at minimum S4 (the changed scenario) and S5
   (needed as the negative population for pooled κ); S1 is a reasonable regression
   sanity-check given it shares no code path but confirms the rig itself is healthy.
5. Regenerate `report.md`; update `RR-007.md` with the real per-message and
   decodable-SNR-restricted κ figures.
6. Update `STUDY-SPEC.md`'s S4 row/§9.3 note to record the fix and point to this change.
7. No rollback complexity beyond `git revert` — no data migration, no product code, no
   deployed state.

## Open Questions

- Should the live audio re-run (migration step 4) be a task within this change, or
  scheduled as separate QA follow-up work once the harness code lands? Recommend
  including it as a task here, since RR-007's recommendation was explicit that
  re-running S4 is what makes the investigation's numbers real rather than theoretical
  — but flagging for Captain input in case rig availability makes that impractical to
  bundle.
- D3's `-12 dB` decodable-floor threshold is R&R-005's value for the redesigned S1
  ladder; S4's own SNR sets differ per part. Confirm during implementation that `-12
  dB` is still the right cutoff for S4's specific signal population, or whether it
  should be re-derived from S4's own data.
