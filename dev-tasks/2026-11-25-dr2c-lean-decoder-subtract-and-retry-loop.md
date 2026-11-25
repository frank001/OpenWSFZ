# Developer task: DR-2 step 2c, the lean engine's subtract-and-retry loop (S3)

**Date:** 2026-11-25
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** `docs/decoder-rebuild/spec-dr2-lean-decoder.md` §2.3 (S3) and §3 step 2c, on `arch/decoder-rebuild` (read with `git show arch/decoder-rebuild:docs/decoder-rebuild/<file>`); the Captain approved the plan on 2026-11-24.
**Status:** Proposed. HK-011: `src/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/lean-2c`, a child of `feat/lean-2b` (tip `2de6fb75`, reviewed `18c11bea`, APPROVED).
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay, no on-air period, no statistical gate. Run tests per project (HK-022) and read the per-assembly "Passed: N" lines. Run the golden and lean tests once with `DOTNET_PROCESSOR_COUNT=4` as well.

---

## 0. Why

Steps 2a and 2b decode round 0 (the original audio): tier A, tier B, CQ-AP. In the baseline (DR-0, Slice 40) the classic decoder's residual work adds +12.03 pp (residual pass), +7.32 pp (third pass, Deep) and +1.95 pp (late round) of WSJT-X-confirmed decodes, and it is also the largest CPU cost (+9.63, +8.56 and +2.10 CPU-s per cycle). Step 2c replaces those three with one loop: subtract what is found, re-search only where the subtraction happened. This is the step on which target T1 (6.31 CPU-s per cycle) is won or lost, so it logs the per-stage cost split (D7).

## 1. What to build

| Id | What |
|---|---|
| **D1 Loop** | Inside `ftz_decode_cycle`, after round 0, rounds r = 1, 2, 3 (spec §2.3 S3): (1) subtract every result not yet subtracted from the residual buffer; (2) recompute the residual's spectrogram in full; (3) `ftx_find_candidates` on it with min score 10 and cap 200 (today's pass-1 values, `K_MIN_SCORE_PASS2` and `K_MAX_CANDIDATES_PASS2`, `ft8_shim.c:573`, :1953), then keep only candidates whose base frequency lies in **[f − 50 Hz, f + 100 Hz]** of a signal subtracted **in this round**; (4) S2 on those candidates (tier A, tier B, CQ-AP, with the step-2b code); (5) the accept rules of §3. **Stop** when a round adds nothing new, at round 3, or when the budget is gone. |
| **D2 Subtraction** | Use `ft8_subfeas_fit_signal` (`subfeas_fit.c`), as classic does, on the **original** audio's analytic signal (one analytic signal per cycle, computed once, read-only across the fits), and subtract each fitted signal's `shat` from the running residual. Tones come from the payload (re-encode), not from text. **A fit that answers "no valid fit" (rc −3) contributes zero**, as classic. Fits for one round run on the worker pool; the sum is made in the sorted result order so the residual is the same bytes at any thread count. |
| **D3 What is subtracted** | Classic subtracts only texts that are re-encodable: not containing `<` (a hash placeholder) and at least 3 tokens (`SubtractionPass.IsReencodable`, `SubtractionPass.cs:530`). Reproduce that rule **on the unpacked text**, so unpack the round's results (in the sorted order, before the next round's search) and subtract only those. Say in the result how you did it; a rule decided from the payload type alone is acceptable if you show it matches on the unit-test fixtures. |
| **D4 Tags** | Every result carries its round (0 to 3) in a new `out_rounds` byte array beside `out_tiers`. The C# side publishes round 0 as batch 1 and rounds 1 to 3 together as batch 2 (spec §2.1; the three-batch wiring is step 2d, so in this step the C# side only **returns the tags and logs the counts**; it does not yet publish batch 2 separately). |
| **D5 Budget** | The existing `budget_ms`. A round is **all or nothing**: a round that the budget stops publishes nothing from that round (earlier rounds stand), sets `abandoned`, and the residual rounds do not start with less than the reserve left. Reserve for a round's decode: 1,500 ms (`SubtractionResidualDecodeReserve`, `SubtractionPass.cs:43`), as classic. |
| **D6 Safety** | Everything of 2a and 2b stands: bounded indexes, checked allocations, `FTZ_ERR_FAULT` on a caught access violation, no per-cycle thread creation. The residual buffer, the analytic signal and the per-fit workspaces are allocated once per call (or per worker, once) and freed on **every** exit path. |
| **D7 Log line** | The per-cycle `lean:` line gains aggregates only (HK-037): rounds run; per round: signals subtracted, fits with rc −3, candidates found, candidates kept by the patch rule, results, wall and CPU ms of subtract, re-spectrogram, search, decode. Totals of wall and CPU for the whole S3. **The CPU split matters:** the Architect's risk for this step is that fitting, not searching, dominates the residual cost. The line must show fit CPU and search CPU separately. |
| **D8 Documents** | `REQUIREMENTS.md`: extend FR-108 or add the next free FR number, **without writing any other FR number in prose** (Gate G3 counts them; it failed step 2a's CI once). The OpenSpec change `lean-decoder` (tasks, delta spec) updated and validated `--strict`. **VERSION:** none, the engine stays internal and default `classic`; run `check_version_bump.py` after committing. |

## 2. Tests (unit tests only)

1. **Round 1 finds a masked signal.** Build a fixture with a strong signal and a weaker one within 50 Hz and 1 to 3 dB under it, so that round 0 decodes only the strong one and round 1 (after subtracting it) decodes the weak one. Say how you built it (the classic residual-pass tests and `SubtractionPassTests.cs` are the place to look). The lean engine with rounds on publishes both; with the loop off (a test hook or `max_rounds = 0`) only the strong one.
2. **Equivalence with classic's residual pass.** On a fixture where classic's residual pass finds at least one new message, the lean engine's round 1 finds the same payload. Compare payload sets, never rendered text across processes.
3. **The patch window.** A candidate in the residual spectrogram outside [f − 50, f + 100] Hz of every signal subtracted in this round is **not** attempted (test the keep rule as a function and once end to end through the stats); a candidate inside it is.
4. **Accept rules** (§3): one test per rule: (a) the payload already known (also the RR73-aware case) is not published again; (b) a text published earlier in the cycle is not published again; (c) a residual tier-B row with F1b above T1 is published iff the ungating flag is on (see §3 item 4) and is counted as ungated; (d) a row above 1097 Hz from the residual tier-B run is dropped (the v2 rule, §3 item 5) when the flag for it is on and kept when it is off.
5. **Stop rules.** A cycle with nothing to find stops after round 1 (stats: rounds run 1); a cycle that keeps finding runs to round 3 and no further.
6. **Order and determinism.** The same audio and starting hash state, run twice and at `threads` = 1, 2 and 4: byte-identical results, tiers, rounds and residual-derived output. Mechanically diffed.
7. **Budget.** A budget that expires during round 2 returns round 0 and round 1's results only, with `abandoned` set and no crash; a budget of zero returns early without a round.
8. **Memory safety.** The ASan + UBSan fuzz harness (`native/ftz_decoder/tests/ftz_fuzz.c`) extended so the 10,000-run fuzz and the determinism run include the loop, on random, clipped, silent, DC and truncated audio. The CI `native-asan` job runs it.
9. **Steps 2a and 2b unchanged.** Their tests and the classic golden stay green, at `DOTNET_PROCESSOR_COUNT` 4 and at the host's own; the existing suites per project.

## 3. Accept rules for a decode from residual audio (read from the code by QA, `feat/lean-2b` tip `2de6fb75`, 2026-11-25)

The spec says: exactly today's gates, no new, none removed. This is what today applies, in order:

1. **Candidate floor and cap for a residual search:** min score 10 (`s_k_min_score_pass2`, default 10, valid 5 to 30) and 200 candidates (`K_MAX_CANDIDATES_PASS2`); LDPC iterations 50 (`K_LDPC_ITERATIONS_PASS2`). The lean engine reads the same setting for the floor.
2. **Payload-based dedup against what is already known** (`SubtractionPass.cs:489-521`): a residual decode is dropped if its payload equals, or is the **RR73-aware same-QSO** of (`SubfeasPayload.SameQso`: a std-message RR73 already known covers the same two calls with an acknowledgement), any payload of a signal fitted this round **or already known from earlier rounds**. In lean "already known" is every result of the cycle so far.
3. **Text dedup per cycle and `IsPlausibleMessage`** with the grammar store: applied in the C# `MapNative` to every batch, unchanged; **not** done in native code.
4. **Tier B on residual audio:** F1b `<= 17.552446` dB, **or** admitted by R-F4 ungating (`decoder.coherentFallbackResidualUngated`, default **true**; in classic it acts only with `coherentFallbackAudio = Both`, which is the default and the baseline's setting). Rows admitted only by the ungating are counted separately. The lean engine reads the same setting.
5. **The v2 residual-candidates run, 1097 Hz rule:** `decoder.coherentFallbackResidualCandidates` is **OFF in code by default but ON in the baseline A6** (`--cohrescand 1` in `qa/decoder-rebuild/dr0_run.py:35`), so the baseline includes it. In classic it is a third fallback run over the residual buffer's own candidate list, keeping **new-text rows only, F1b-passed rows only, published frequency `<= 1097 Hz`** (`CohFallbackAudioSelector.ResidualRunMaxFreqHz`, `PassesResidualRunGate`). In the lean loop the residual tier-B attempts are the third run's equivalent; apply the 1097 Hz and F1b-passed rules to a residual tier-B row **when that setting is on**, and read it from the same key. **Do not apply them when it is off.**
6. **The late round's fit list** in classic is only the natives published in batches 3 and 4 (not yet subtracted); lean subtracts "every result not yet subtracted", which is the same idea. The late round runs the primary decoder only (no tier B on its residual); **the lean loop runs tier B on every round's patch candidates**, as spec §2.3 step 4 says. Record this as the one deliberate difference.
7. **OSD:** OFF in the lean engine (DR-0, NET −0.015 pp). **So the OSD thresholds (`osdCorrThreshold`, `osdNhardMax`) are not applied; no need to read them.** The `K_MIN_SCORE_PASS2` floor above IS applied.
8. **Not applicable:** the 13 s cycle budget and the batch numbering of the classic path.

## 4. Out of scope

XC wiring and the three batches (2d), `effort` (2d), the C# publish of batch 2 (2d), OSD, any new gate or threshold, any closed arm (window, input scaling, OSR, candidate budgets), changing the patch window from [−50, +100] Hz.

## 5. Report back

The commit SHA; the per-project "Passed: N" lines; the fixtures for tests 1 and 2 and how test 1's was built; the result of the `DOTNET_PROCESSOR_COUNT=4` run; how D3 was decided; **the S3 CPU split on your fixtures (fit versus search versus decode), because the Architect is watching it**; any case where the lean loop's outcome differs from classic's residual pass on a fixture.
