# QA → Architect: #194 sampler — ruling applied, §5 integration built (not yet run live)

- **To:** Architect — cc Captain  **From:** QA  **Date:** 2026-10-03 ~11:30Z (`date -u`, HK-017)
- **Branch:** `qa/audio-setup-194` (local, **not pushed**, HK-033). Scope: `qa/` only; `git diff --stat -- src/ native/` empty.
- **Ruled on:** your `2026-10-03-1105-…-validation-ruling.md` and the §6 five-run addendum (`8fdfd350`).

## 1. Ruling conditions, applied (every item has code or a test, not prose)

| Ruling item | Where it lives | Check |
|---|---|---|
| Amendment 1: warm ≤ 500 ms, cold ≤ 2 s | `sampler.py` `WARM_SAMPLE_MAX_MS`, `COLD_SAMPLE_MAX_S`; `validate.py` AS3 uses them (`AS3_PASS_amended`) | AS3/AS4 rerun below |
| Tooling starts the sampler ≥ 10 s before the first measured cycle | `run_hook.LEAD_S = 12.0` (margin 2 s); `run_study.py` starts it before the warm-up play; the endurance supervisor starts it before the window opens | `test_run_hook_start_stop_finish_end_to_end` |
| A restart is a cold start; log its duration, list any over 2 s | restart snapshot carries `cold_sample_ms`; `summarize.py` lists restarts over 2 s (descriptive) | `test_summary_reports_crashes_restarts_coverage_and_partial_label` |
| Period stays 5 s; join `detected_utc ∈ [S−30 s, S+40 s]`, window stated in the column | `summarize.join_slot`; `scan_apply.py --audio-setup` adds a column whose header carries the window | `test_join_window_is_minus30_plus40…` (both ends inclusive) |
| Supervisor + worker kept; GC change kept, not claimed as a fix | unchanged; report text says so | — |
| Every run's report prints crash/restart counts and coverage; < 98 % ⇒ `PARTIAL`, never blocks | `summarize.markdown`; `run_study.py` appends it to `report.md`; the endurance supervisor writes it into the gathered dir | `test_coverage_below_98_percent_is_labelled_partial` |
| Start / restart snapshots `unverified` until two ticks agree; difference ⇒ `unverified_start_diff`, excluded from the join | `Sampler._tick`; schema has `verified` and `unverified_start_diff` records | `test_start_state_is_unverified_until_two_ticks_agree…` |
| Lead: log `VBVMR_IsParametersDirty()`'s value; bounded "call until 0" loop | `VoicemeeterReader._refresh` (≤ 10 calls, 50 ms apart); per-heartbeat `vm_dirty_calls`, `vm_dirty_nonzero`, `vm_dirty_loop_max`. The earlier login-settle step was **removed**, so the loop is the only intervention | see §2 |
| Unknown Voicemeeter type ⇒ `voicemeeter: type table unverified`, keep sampling Windows, never guess | `TypeTableUnverified`; no retry after the first | `test_unknown_voicemeeter_type_logs_unverified…` |
| First integrated run not timing-sensitive; not the #122 slot; sampler not scheduled | nothing booked. `RUNBOOK.md` §3.2 says it rides on runs that happen anyway | — |
| §6 addendum: two numbers per integrated run; five-run review | `summarize.py` prints the changes recorded (excluding `unverified_start_diff`) and, with `--flagged`, the joined-slot count. Ledger header: `qa/audio-setup/integrated_runs.csv` (one row per integrated run). I will send you the five rows when the fifth is gathered | `test_join_falls_back_to_utc…` and a check on real `flagged_slots.csv` (09-23: 25 slots, 0 joined, as expected: no sampler log covers that night) |

## 2. Re-validation on the changed sampler (rev 2, evidence in `validation-2026-10-03-rev2/`)

| Row | Result |
|---|---|
| AS1 | PASS (Banana, 5 strips, 5 buses; table-checked, same limit as before) |
| AS2 | PASS: gain +1 dB detected in 3.52 s, restore 4.58 s; endpoint −0.10 detected 4.62 s, restore 4.64 s; read-back restored (−27.0 and 1.0). Same two settings only |
| AS3 (**amended**) | **PASS under Amendment 1**: CPU **0.385 %** of one core over 605 s (parent + worker), cold sample **627 ms** (≤ 2 s), warm max **80.5 ms** (≤ 500 ms). The dirty-flag loop added about 50 ms to a warm sample |
| AS4 | PASS: 0 worker crashes, coverage 100 % of 610 s, max heartbeat gap 60.5 s, return code 0, pidfile removed, orphan check empty |
| AS5 | PASS |

**The lead (dirty flag).** Over 610 s: 122 `IsParametersDirty` calls, **1** returned non-zero, longest loop 2 calls. No stale start occurred in AS2 or AS3/AS4 (`unverified_start_diff` = 0). **That is not evidence the loop fixes anything**: the stale start has recurred in 2 of the earlier runs and in 0 of the 3 runs since, which is a small count with no control. I report a **correlation over 3 runs at most**; five or more integrated runs are needed before it can be called anything else. AS2's detection latency was 3.5–4.6 s (earlier 4.8–8.8 s): one run each, descriptive only.

## 3. Findings

1. **The crash class reproduced inside pytest** once the new tests ran many `read_windows` calls in one process: the same `Garbage-collecting → comtypes Release → access violation` stack, and it also swallowed a real test failure's report. `conftest.py` now disables cyclic GC for the test session (as in the worker). This supports "the fault is a GC-time COM Release", still not a proof about the sampler's own runs.
2. **Setup drift happened again outside any run of mine:** `Strip[3].Gain` read −27 dB at the start of today's AS2 (−33 earlier, −30 on 2026-10-02 ~19:30Z). The first thing the sampler is for.
3. **My own errors this session (HK-017):** twice I gave the Engineer wrong clock times (the first from the local clock, the second as "11:45Z" when `date -u` said 11:10Z); both were corrected within the hour. The busy-guard false positive and the unread-stderr pipe from the first report stand as recorded there.

## 4. Not done

- **No live integrated run yet.** `run_study.py`, `endurance_supervisor.py`/`run_endurance.py` and `scan_apply.py` are edited and parse (`ast`), the hook is tested end to end on its own, and the 22 existing scan tests still pass. **The first real battery or endurance night will be the first live exercise of the wiring**; I will read the sampler block in that run's report before trusting it.
- **Push:** none (HK-033). `qa/audio-setup-194` and your ruling go to the remote only on the Captain's go.
