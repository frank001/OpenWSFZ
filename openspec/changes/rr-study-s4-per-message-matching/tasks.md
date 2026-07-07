## 1. Truth generation — `harness/run_scenario.py`

- [ ] 1.1 Change `_render_multi`'s signature/return to also produce `signals_meta:
      list[dict]` (one dict per station: `message_text`, `freq_hz`, `dt_s`, `snr_db`),
      following the exact pattern already used by `_render_band_scene` (S8) and
      `_render_compound` (S7). Reuse the `freqs[i]`/`snr_list[i]`/`text` values
      `_render_multi` already computes internally — do not recompute them.
- [ ] 1.2 In `_run()`, capture `s4_signals_meta` from `_render_multi` in the `elif
      is_s4:` branch (mirroring the existing `s7_signals_meta`/`s8_signals_meta`
      locals).
- [ ] 1.3 Add an `elif is_s4 and s4_signals_meta is not None:` branch to the
      truth-writing dispatch (alongside the existing `is_s8`/`is_s7` branches), writing
      one `_append_truth()` call per signal with that signal's own `snr_db`, `dt_s`,
      `freq_hz`, `message_text`.
- [ ] 1.4 Remove the now-unused pooled-string construction (`msg_text = "; ".join(pool[i
      % len(pool)] ...)`) from the `elif is_s4:` render branch — it was only needed to
      feed the old single-row truth write.

## 2. Matcher — `harness/matcher.py`

- [ ] 2.1 Delete the S4-specific pool-matching special case (the `else:` sub-branch at
      lines ~170–177 handling `"; "`-joined `truth_msg` pools) from `_match_appraiser`.
      Confirm no scenario still emits `true_freq_hz == ""` with a non-empty
      `message_text` after task 1's changes (S4 no longer does; S5 already emits
      `message_text == ""`, which the remaining `if truth_msg == "":` branch already
      and correctly handles).
- [ ] 2.2 Confirm (by reading, then by test in task 4) that S4 truth rows now flow
      through the same generic `else` branch (real `true_freq_hz` + single-message
      text-equality + frequency-tolerance matching) already used by S1–S3/S7/S8 —
      no new matcher code path should be needed.

## 3. Analysis — `harness/analyse.py`

- [ ] 3.1 Verify `_attribute_agreement`'s grouping/key logic requires no changes given
      the new per-message S4 row shape (design.md's expectation, stated as a risk to
      confirm rather than assumed). Add an assertion or test if any implicit
      per-part-row-count assumption is found.
- [ ] 3.2 Add the informational decodable-SNR-restricted Kappa computation: filter S4
      positives to `true_snr_db >= -12` before computing the restricted-population
      confusion matrix and κ, alongside (not replacing) the existing full-population
      pooled κ.
- [ ] 3.3 Update `_attribute_report_lines()` (or equivalent render function) to show
      both the full-population and decodable-SNR-restricted κ rows, both clearly
      labelled advisory/informational, neither contributing to the overall verdict.
- [ ] 3.4 Confirm the overall-verdict computation (wherever it aggregates gate rows)
      excludes the new restricted-population κ row exactly as it already excludes the
      existing pooled κ row.

## 4. Testing

- [ ] 4.1 Add a synthetic-data unit test constructing a multi-message S4 part (e.g. 3+
      signals per cycle, mixed match/miss outcomes) and asserting the matcher produces
      one independent matched/missed row per message, with no cross-message
      contamination (a miss on message A does not affect message B's outcome).
- [ ] 4.2 Add a regression test confirming a correctly-decoded secondary message in a
      busy S4 cycle is recorded as a matched row, not a false positive.
- [ ] 4.3 Add/update a test confirming S7 and S8's existing per-signal truth/matching
      behavior is byte-for-byte unaffected (same seeds → same truth.csv/matched.csv
      content) by this change.
- [ ] 4.4 Run the full `analyse.py`/`matcher.py` unit test suite; confirm zero
      regressions (record before/after pass count in the PR description).
- [ ] 4.5 `--dry-run` the S4 scenario and inspect `truth.csv`/`S4_matched.csv` shape:
      confirm row count per part equals `n_signals × trials`, confirm `message_text` is
      always a single message, confirm each row carries its own `true_snr_db`/
      `true_freq_hz`.

## 5. Live re-run and real data

- [ ] 5.1 Schedule and run a live-audio re-run (real WSJT-X + VB-CABLE) covering at
      minimum S4 (the changed scenario) and S5 (the negative population the pooled κ
      needs); include S1 as a rig-health sanity check.
- [ ] 5.2 Regenerate `report.md`/`report.html` from the new run; confirm the new
      per-message S4 confusion matrix and both κ figures (full + decodable-SNR-restricted)
      render correctly and no longer show the degenerate TP=15/FN=0 ceiling result.
- [ ] 5.3 Compare the new S4 per-message recovery figures against S7's per-message
      figures from the same run as a sanity cross-check (they should now tell a
      broadly consistent story about QRM-handling capability, unlike the `793a298`
      contradiction that triggered RR-007).

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
