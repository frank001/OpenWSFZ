## 1. Truth generation — `harness/run_scenario.py`

- [x] 1.1 Change `_render_multi`'s signature/return to also produce `signals_meta:
      list[dict]` (one dict per station: `message_text`, `freq_hz`, `dt_s`, `snr_db`),
      following the exact pattern already used by `_render_band_scene` (S8) and
      `_render_compound` (S7). Reuse the `freqs[i]`/`snr_list[i]`/`text` values
      `_render_multi` already computes internally — do not recompute them.
- [x] 1.2 In `_run()`, capture `s4_signals_meta` from `_render_multi` in the `elif
      is_s4:` branch (mirroring the existing `s7_signals_meta`/`s8_signals_meta`
      locals).
- [x] 1.3 Add an `elif is_s4 and s4_signals_meta is not None:` branch to the
      truth-writing dispatch (alongside the existing `is_s8`/`is_s7` branches), writing
      one `_append_truth()` call per signal with that signal's own `snr_db`, `dt_s`,
      `freq_hz`, `message_text`.
- [x] 1.4 Remove the now-unused pooled-string construction (`msg_text = "; ".join(pool[i
      % len(pool)] ...)`) from the `elif is_s4:` render branch — it was only needed to
      feed the old single-row truth write.

## 2. Matcher — `harness/matcher.py`

- [x] 2.1 Delete the S4-specific pool-matching special case (the `else:` sub-branch at
      lines ~170–177 handling `"; "`-joined `truth_msg` pools) from `_match_appraiser`.
      Confirm no scenario still emits `true_freq_hz == ""` with a non-empty
      `message_text` after task 1's changes (S4 no longer does; S5 already emits
      `message_text == ""`, which the remaining `if truth_msg == "":` branch already
      and correctly handles).
- [x] 2.2 Confirm (by reading, then by test in task 4) that S4 truth rows now flow
      through the same generic `else` branch (real `true_freq_hz` + single-message
      text-equality + frequency-tolerance matching) already used by S1–S3/S7/S8 —
      no new matcher code path should be needed. Confirmed by reading (task 2.1);
      test coverage added in task group 4.

## 3. Analysis — `harness/analyse.py`

- [x] 3.1 Verify `_attribute_agreement`'s grouping/key logic requires no changes given
      the new per-message S4 row shape (design.md's expectation, stated as a risk to
      confirm rather than assumed). Add an assertion or test if any implicit
      per-part-row-count assumption is found. Confirmed by reading: the key already
      incorporates `message_text`, which is now naturally unique per message instead
      of a repeated pooled string — no change needed to the grouping/key logic
      itself. Refactored the confusion/κ/repeatability computation into a shared
      `_confusion_kappa_repeatability()` helper so both the full and restricted
      populations (task 3.2) are computed identically.
- [x] 3.2 Add the informational decodable-SNR-restricted Kappa computation: filter S4
      positives to `true_snr_db >= -12` before computing the restricted-population
      confusion matrix and κ, alongside (not replacing) the existing full-population
      pooled κ. Added `S4_DECODABLE_SNR_FLOOR_DB = -12.0` constant and
      `attr_results["restricted"]`.
- [x] 3.3 Update `_attribute_report_lines()` (or equivalent render function) to show
      both the full-population and decodable-SNR-restricted κ rows, both clearly
      labelled advisory/informational, neither contributing to the overall verdict.
- [x] 3.4 Confirm the overall-verdict computation (wherever it aggregates gate rows)
      excludes the new restricted-population κ row exactly as it already excludes the
      existing pooled κ row. Confirmed: `main()` passes only `attr_results["kappa"]`
      (never `attr_results["restricted"]`) to `_collect_verdicts`.

## 4. Testing

- [x] 4.1 Add a synthetic-data unit test constructing a multi-message S4 part (e.g. 3+
      signals per cycle, mixed match/miss outcomes) and asserting the matcher produces
      one independent matched/missed row per message, with no cross-message
      contamination (a miss on message A does not affect message B's outcome). Added
      `tests/test_matcher.py::test_multi_message_s4_cycle_scores_each_message_independently`.
- [x] 4.2 Add a regression test confirming a correctly-decoded secondary message in a
      busy S4 cycle is recorded as a matched row, not a false positive. Added
      `test_correctly_decoded_secondary_message_is_matched_not_false_positive`.
- [x] 4.3 Add/update a test confirming S7 and S8's existing per-signal truth/matching
      behavior is byte-for-byte unaffected (same seeds → same truth.csv/matched.csv
      content) by this change. Added `test_s7_s8_style_multi_signal_cycle_still_matches_correctly`
      (exercises the shared generic matching path S7/S8 already relied on) plus
      `test_s5_signal_free_slot_yields_no_match_and_no_consumption` and
      `test_repeated_message_text_at_different_frequencies_matched_independently`
      (S4's message-pool wraparound case) in `tests/test_matcher.py`; added
      `tests/test_analyse.py` covering `_attribute_agreement`'s full and restricted
      populations plus verdict-engine exclusion.
- [x] 4.4 Run the full `analyse.py`/`matcher.py` unit test suite; confirm zero
      regressions (record before/after pass count in the PR description). Result:
      **174/174 pass** (163 pre-existing + 11 new in `test_matcher.py`/`test_analyse.py`),
      zero regressions.
- [x] 4.5 `--dry-run` the S4 scenario and inspect `truth.csv`/`S4_matched.csv` shape:
      confirm row count per part equals `n_signals × trials`, confirm `message_text` is
      always a single message, confirm each row carries its own `true_snr_db`/
      `true_freq_hz`. Ran `run_scenario.py scenarios/s4-density.json --dry-run --parts
      0,1,4`: truth.csv row counts were exactly 3 (part 0, 1 signal), 15 (part 1, 5
      signals), 90 (part 4, 30 signals) — each row single-message with its own SNR/freq.
      Confirms the fix end-to-end for truth generation; `S4_matched.csv` shape
      requires real decode logs and will be confirmed during the live re-run (task 5).

## 5. Live re-run and real data

- [x] 5.1 Schedule and run a live-audio re-run (real WSJT-X + VB-CABLE) covering at
      minimum S4 (the changed scenario) and S5 (the negative population the pooled κ
      needs); include S1 as a rig-health sanity check. Run: `results/2026-07-07-df4cc89/`
      (`--scenarios S1,S4,S5`), Captain-operated live session.
- [x] 5.2 Regenerate `report.md`/`report.html` from the new run; confirm the new
      per-message S4 confusion matrix and both κ figures (full + decodable-SNR-restricted)
      render correctly and no longer show the degenerate TP=15/FN=0 ceiling result.
      Confirmed: WSJT-X TP=75/FN=33 (69.44% recovery), OpenWSFZ TP=71/FN=37 (65.74%
      recovery) — real, differentiated, non-degenerate figures (vs `793a298`'s
      TP=15/FN=0, 100%, κ=1.000 for both). Restricted-population κ table also
      rendered (WSJT-X/OpenWSFZ both 79.01% recovery, between-appraiser κ=0.931 PASS).
      Sections 1/2/5 authored per HK-001; HTML rendered via `render_report.py`.
- [x] 5.3 Compare the new S4 per-message recovery figures against S7's per-message
      figures from the same run as a sanity cross-check (they should now tell a
      broadly consistent story about QRM-handling capability, unlike the `793a298`
      contradiction that triggered RR-007). **Caveat:** S7 was not included in this
      run (out of the task 5.1 minimum scope), so the comparison used the most
      recent available S7 data (`793a298`) rather than a same-run check. Direction is
      consistent (OpenWSFZ trails WSJT-X in both S4 and S7's co_channel family);
      magnitude differs as expected (S4 aggregates all SNRs/densities, S7's
      `co_channel` isolates the hardest equal-power case). A same-run comparison
      would require a follow-up run including S7 — noted in `report.md` Section 5 and
      left as a suggestion, not a blocking gap.

## 6. Documentation

- [ ] 6.1 Update `STUDY-SPEC.md`'s S4 scenario description (§6) to record the
      per-message truth/matching redesign and reference this change.
- [ ] 6.2 Update `STUDY-SPEC.md` §9.3's Kappa note to record that condition 3 (per
      RR-007) has been addressed, and add the real decodable-SNR-restricted κ figure
      once available from the re-run — without ratifying the gate (that remains a
      separate, explicit Captain decision).
- [ ] 6.3 Update `qa/rr-study/RR-007.md` with the outcome: implementation landed, real
      per-message data obtained, and the current state of the two original §9.3
      ratification conditions now that both can actually be evaluated.
- [ ] 6.4 Close or update GitHub issue #59 reflecting the implemented fix and the
      real data obtained, distinguishing clearly between "the matcher defect is fixed"
      and "the gate is ratified" (the latter is explicitly not decided by this change).
