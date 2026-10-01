# QA → Architect: SUB-FEAS speed-redesign spec authored; one precondition fired, two amendments proposed

- **Date (UTC):** 2026-09-30, written after your spec `2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md`.
- **Author:** QA. **To:** Architect. **`src/`/`native/` diff:** none (HK-011).
- **Authored (local, `qa/sub-feas`, not pushed):** OpenSpec change `openspec/changes/sub-feas-speed-redesign/` (proposal, design, spec delta, tasks; `openspec validate --all --strict` 62/62) and the Developer handoff `dev-tasks/2026-09-30-sub-feas-speed-redesign-stage-a.md` (draft, for the Captain to hand over, HK-000).

## 1. Your M1 precondition fired. I asked the Captain; he chose DEFER.

Your STOP condition: "if anything in `qa/` or `tools/` reads `prenormVar`/`meanAbsLLR`/`failCands`". Four QA scripts regex-parse the Debug line `Iterative subtraction: pass N LDPC fail stats — failCands=… meanAbsLLR=… prenormVar=…`:

- `qa/cycleframer-alignment-replay/ldpc_stats.py`
- `qa/cycleframer-alignment-replay/2026-08-04-isolated-replay-rerun/run_isolated_replay_generic.py`
- `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py`
- `qa/rr-study/results/2026-07-23-d001-tight-class-replay/run_tight_replay.py`

`tools/` and the RUNBOOK have none. (Historical dev-tasks and reports only describe the line.) **The Captain chose "defer M1, ship the rest".** Consequences recorded in the change: M1 is out of scope; R5′ is measured with M1 absent, so M2 and M3 alone are what it can credit. M1's full touch-surface is in `design.md` D7 for later.

## 2. Two amendments proposed to your acceptance rows (yours to accept or refuse; QA has not moved any bar)

1. **R5′ baseline.** Your row compares the new build's flag-OFF median to `2b39cf18`'s. The §8.1 flag-OFF medians (473–528 ms) were taken with WSJT-X, a browser, Voicemeeter and others resident. The acceptance run is made with WSJT-X **closed**, so comparing against the §8.1 figure flatters the candidate. **Proposal:** the baseline is the `2b39cf18` DLL **re-measured in the same session on the same cycles**. Same predicate (≤ 1.05×), different baseline. The same-session re-measure also gives the noise floor of the row for free: two identical builds, same cycles, is the spread the 5 % has to sit above (HK-026: the §8.1 medians differ by about 11 % across strata on one build).
2. **E1 selection made mechanical.** "Every 9th stamp of the sorted list" is ambiguous across runs. **QA will use:** the pooled H ∪ M list of `(run, stamp)` pairs sorted by `(run, stamp)`, indices 0, 9, 18, …, plus the 60 pilot cycles. Disclosed before any timing.

## 3. Three notes, no action needed

- **R1′ margin is thin (`design.md` D5).** Reserve 1 000 ms against an observed flag-OFF max of 830 ms leaves 170 ms, on one outlier, before the merge/dedup step. Registered as you wrote it, no bar moved.
- **A3 ownership.** Thread-pool threads are not native-owned and C thread-local storage has no destructor here, so "one workspace per worker" needs an explicit ownership story to be freed at shutdown. `design.md` D2 recommends a bounded locked pool and leaves the choice to the Developer. This is where the base change's two `0xC0000005` crashes lived, so it is the review focus.
- **Config interaction.** `decoder.subtractionMaxThreads` is a new key while the config-save workstream (#193) is in flight in another session; the config POST is a full replace (HK-035). Flagged to the Developer to confirm, not assumed.

## 4. Still true

No decode-rate claim; the flag stays OFF; base-change §7 and §8.2 stay open; no real cycle above 32 signals and one machine only. The change depends on `feat/sub-feas-native-subtraction` (`ab95bea1`), which is not merged; it adds requirements only, so it validates independently but cannot merge first.
