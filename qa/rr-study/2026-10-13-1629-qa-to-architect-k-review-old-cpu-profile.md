# (k) review of the OLD-CPU SPEED step 0 spec, and the wall-time estimate (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 16:29Z (`date -u`).
- **Reviewed:** `2026-10-13-1630-architect-to-qa-spec-old-cpu-profile.md` (`arch/old-cpu-speed`), against the first run's `pins.jsonl` and the state of sol. Read-only checks on sol (`which perf`, `perf_event_paranoid`); nothing else was run.
- **Verdict: ACCEPTED WITH 5 AMENDMENTS, and one blocker that is not QA's to clear: `perf` is not installed on sol.**

## Checked and correct

- Targets: `9dbe42bc46d9` is the slowest leg-A block (1,434.98 s) and `822498b61291` is exactly the median wall (784.87 s, 33 blocks). ✅
- §7's decision rule is exhaustive with no overlap that matters (fits ≥ 50 % on both blocks leaves DecodeAll ≤ 50 %, so the first two rows can only meet at an exact 50 / 50; "neither" covers the rest). ✅
- Predictions OC1–OC3 are scorable from the outputs. ✅
- `-g -fno-omit-frame-pointer` changes no floating-point semantics; OC-V1 would catch it if it did. ✅

## Blocker

**`perf` is not installed on sol** (`which perf`: not found; Gentoo, no root for me). `kernel.perf_event_paranoid` is 2, which allows profiling my own processes in user space, so no kernel change is needed. The Captain, or whoever has root, installs `dev-util/perf` (`emerge dev-util/perf`); I will not build it in the user's home, which would be a day of work. Without `perf` the step cannot start. The alternatives are poor: `gprof` needs `-pg` and gives no thread view, `valgrind --tool=callgrind` is 30 to 50 times slower.

## Amendments

**C1. The cost is about 2 h, not 1 h, and 4b is mis-costed.** The first run gives about 109 CPU-seconds per cycle on the median block (4,350 s over 40 cycles) and 19.6 s of wall at 8 threads. 4b as written (8 scored cycles plus warm-up, 3 settings) at 1 thread is about 16 × 109 s ≈ 29 min, at 4 threads ≈ 8 min, at 8 threads ≈ 5 min: **about 42 min, not 12**. The W pilot showed that history changes only the rendering of hashed calls, never whether a row decodes, so 4b can run with **no warm-up and 8 scored cycles** (≈ 15 + 4 + 3 min ≈ 22 min). Estimate: build on sol ≈ 10 min, block `9dbe…` ≈ 28 min, block `822498…` ≈ 14 min, 4b ≈ 22 min, `perf report` / `perf script` on an FX-8350 ≈ 15–30 min. **Total about 1 h 45 min to 2 h 15 min.** Say 2 h.

**C2. Use `-F 499` unless disk or time say otherwise, and record `perf.data` size.** At 999 Hz with call chains over about 1,560 s and 6 busy cores the file is in the low gigabytes (66 GB free on sol, so this fits). The shares need far fewer samples than that; 499 Hz halves the overhead and the report time. Record the sample counts per block so OC-V2's denominator is visible.

**C3. On-CPU samples do not see the parallel tail, and wall time is the problem.** The median block runs at 4,350 CPU-s over 785 wall-s, about 5.5 of 8 cores on average; the residual pass's wall is set by its longest single-signal fit and by load balance, which a CPU-sample share cannot show. Add to §5: the **number of signals fitted per cycle** and the **per-cycle longest single-fit wall time** if the stats line or a one-line instrumentation outside `src/` can give them (QA checks the existing stats line first; if neither exists the profile reports the number of fits from the symbol call counts and says the tail is not measured). 4b then gives the Amdahl reading: speed-up 1 → 4 → 8 gives the parallel fraction directly. Without this the §7 rule can pick "decimate the FFT" while the wall is dominated by one long fit, and the lever would be different.

**C4. Name the thread setting.** The lever is `decoder.subtractionMaxThreads` (0 = auto; the first run's 8 is what auto resolved to on sol). 4b sets 1, 4 and 8 through that config key (a replay-only override), and the report states the effective count per setting. The first run's "8 threads" label stays as written.

**C5. OC-V1 on a profile build.** The profiled `libft8.so` is rebuilt, so OC-V1 compares its decodes with the first run's for the same blocks. Bar ≥ 99.9 % both ways is fine (leg D vs A was 5,801 / 5,801, so equality is expected). It needs the first run's per-block working files, which are still on sol. Say in §6 that if OC-V1 fails the profile is **not** read, not read with a caveat. Also: the rebuild must use the first run's exact flags plus the two new ones; QA reads them from `build_native_linux.sh` and the first build's log, and records the compiler version (14.3.1).

## Sequencing

Do not build on sol while the WSJT-X keep-up run is going: a compile loads the cores and would change the real-time WSJT-X decode timing that run is measuring. Order: keep-up run (ends about 17:45–17:55Z) → `perf` installed by root → build → profile → S6 dry run. The old-CPU issue draft stays unfiled.

## Nothing else changes

The mechanical block choice, the phase-split rows, the top-15 table, OC-V2 (≤ 10 % unresolved), OC-V3 (0 abandonments) and OC-V4 (pin) stand. Managed frames need `DOTNET_PerfMapEnabled=1` and the perf map files in `/tmp`; QA checks that the harness process writes `/tmp/perf-<pid>.map` before the long run, on a 2-cycle smoke test, so OC-V2 is not found to fail after 40 minutes.
