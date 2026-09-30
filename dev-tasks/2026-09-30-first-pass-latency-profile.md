# First-pass latency profile: where do the ~500 ms of the first decode go? (test-only)

**Date:** 2026-09-30
**Prepared by:** QA (HK-015: Architect → QA → Developer)
**Audience:** Developer (to execute **only when QA says so**); Captain (hand-over per HK-000)
**Status:** **DRAFT. SCHEDULED, NOT TO START until QA messages you (expected right after the S2 timing run ends, ~17:20Z 2026-09-30).** Revised on the Captain's instruction: this runs BEFORE the Engineer's heavy work and no longer waits for S2b (`qa/rr-study/2026-09-30-post-s2b-schedule.md`).
**Branch:** a new test-only branch off `feat/sub-feas-two-stage-publish` (or off whatever head the Captain has decided to merge by then; QA will say). **No product-path change.**

---

## 0. Why

The flag-OFF first-pass decode takes about 480 ms median (max about 830 ms; #122's series p50 518 ms). The window that matters is the ~2.36 s guard after the audio ends (TX must start by 17.36 s), so pass 0 uses about a fifth of it (#122). The Captain's point: 0.3-0.4 s is not nothing in that window (#122 comment `issuecomment-5914822230`). Whether the first pass can be made faster, and by threading which step, depends on the split, which nobody has measured. **This task measures it. It changes nothing that ships.**

## 1. What you build (test-only)

A tool under `tests/`, in the style of `tests/Ft8.FitProbe` and its `native/phase_timing.c` (the measured-cost-map precedent from the fit speed-up), that decodes real cycles one at a time and reports wall-clock **milliseconds per stage** of one first-pass decode:

1. managed side before native: PCM normalisation and marshalling;
2. spectrogram / waterfall build (`monitor_process` or the equivalent);
3. candidate search, pass 0 (`ftx_find_candidates`);
4. the per-candidate decode loop, pass 0: likelihood extraction, LDPC, CRC, message unpack. **Also report the candidate count and the successful-decode count as integers;**
5. spectrogram suppression, candidate search and decode loop of pass 1 (`K_MAX_PASSES` = 2);
6. noise floor, SNR terms, and the managed side after native (mapping, logging).

Method: a timing-instrumented **copy** of the pipeline compiled for the test (never shipped, not in the export list), so `libft8.dll` and the product decoder are untouched. Single decode at a time, one thread. Warm up once per process. Cycles: the **161 E1 cycles** (`qa/rr-study/results/2026-09-30-sub-feas-speed-e1/e1_selection.json`, SHA-256 `f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2`), audio from `artefacts/<run>_endurance_run-gathered/owsfz/wav/<stamp>.wav` (12 kHz, mono, 16-bit, exactly 180 000 samples; assert it in code).

Output: **integers and stamps only** (HK-037 / NFR-021): per stage the median, p95 and max in milliseconds, each stage's share of the total, the candidate and success counts, and the sum-of-stages against the measured whole call (they should agree within a few percent; report the gap).

## 2. What you must decide and record

- How the per-stage timers are inserted without changing what is computed (the timed copy must produce the same decodes as the shipped path: assert the pass-0 decode **count and outcome hash** equal the shipped DLL's on the same cycles, as the E1 probe does).
- Where each stage boundary sits in `ft8_decode_all`; name the functions.

## 3. What you do NOT do

- No change to `ft8_shim.c`, `decode.c` or any shipped file's behaviour; no shim bump; no new export in the shipped DLL.
- No threading, no optimisation, no proposal in the code. **This is a measurement.** If the result suggests a split, QA reports it and the Architect scopes any follow-on; it needs the Captain's go.
- No decode-rate work and no claim about decode rate.

## 4. Pitfalls
1. **Timer overhead:** a stopwatch around a 50 µs step adds noise; time a stage over its whole loop, not per candidate, and report the timer's own overhead.
2. **Quiet machine:** QA runs the tool with WSJT-X closed and nothing else running; do not run it yourself for numbers.
3. **The whole-call reference:** compare your sum against `DecodeAsync` measured the same way (flag OFF), so the stages add up to what the log line says.
4. **Cross-platform:** the timed copy is Windows-only test scaffolding; say so.

## 5. Hygiene
- 🔒 No message text, callsigns or exception text in any output.
- **HK-011:** you are the separate Developer session. **Stage by path, never `git add -A`.** Check `git branch --show-current` before committing.
- Nothing is pushed or merged without the Captain's go (HK-010, HK-033).

## 6. Done means

The tool committed with its build recipe; a short report to QA with the per-stage table for a small fixture set, the timer-overhead figure and the equivalence assertion result. **QA then runs it on the 161 E1 cycles on the quiet machine and reads it.** The question it answers, for the record: *is the per-candidate decode step (the natural thing to split across threads) the bulk of the ~500 ms, or is it the spectrogram and search?*
