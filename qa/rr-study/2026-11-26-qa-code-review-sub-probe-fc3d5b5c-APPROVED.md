# QA code review (HK-039): SUB-PROBE, a test-only diagnostic probe in the lean decoder

**Reviewed commit:** `fc3d5b5c1a3abe5ba968dc657ad3a82b42f68b0f` (`feat/sub-probe`, one commit on `main` `c3ba377c`, not pushed)
**Reviewed-commit:** fc3d5b5c1a3abe5ba968dc657ad3a82b42f68b0f
**Verdict:** APPROVED, with 5 minor notes
**Reviewer:** QA, 2026-11-26. Read: `native/ftz_decoder/ftz_decoder.c` and `.h` (the whole probe diff), `native/ftz_decoder/tests/ftz_fuzz.c`, `src/OpenWSFZ.Ft8/Interop/LeanCycle.cs`, `Ft8LibInterop.cs`, `ft8_shim.h`, `LeanEngineProbeTests.cs`, the OpenSpec change, against `dev-tasks/2026-11-26-sub-probe-lean-diagnostic.md` and the Architect's `docs/decoder-rebuild/spec-sub-probe.md` (`arch/decoder-rebuild` `028ad6ac`).

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\probe-review`, Release, whole projects, no `--filter`, HK-022)

- OpenWSFZ.Config.Tests: **Passed: 237, Failed: 0**. OpenWSFZ.Web.Tests: **Passed: 464, Failed: 0**. OpenWSFZ.Daemon.Tests: **Passed: 963, Failed: 0**.
- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests (6 m 24 s): **Passed: 917, Failed: 0** (910 plus the 7 new `LeanEngineProbeTests`).
- JavaScript, `node --test web/js/*.test.js`: **tests 131, pass 131, fail 0**.
- All equal the Developer's figures. From the Developer's report, not re-run by QA: ASan + UBSan fuzz (10,000 runs, 7,123 with the flag on, tiny and exactly-sized buffers, 726 overflows), `check_native_version`, `check_version_bump`, `openspec validate --strict`. CI repeats ASan, Linux and macOS; `pre_merge_check` runs once on the sprint PR.

## What was checked and found sound

- **D1, the flag is read-only.** `FTZ_FLAG_PROBE` (128) in `ftz_params_t.flags` and a `probe` pointer (params version 6, checked against `struct_size`); the probe state is allocated only with the flag (all pointers NULL otherwise: no memory, no work; an allocation failure turns the probe off and sets the overflow flag, never the decode). Every probe write sits behind `pb != NULL`; the stage items write only into their own `pstat[i]`; the footprint and amplitude computations read the waterfall and the fitted waveform; the extra `ftx_find_candidates` call writes into the probe's own `low_buf`. The tests show flag off against on byte-identical on the three synth files and their mix at 1, 2, 4, 8 and 16 threads, and the same on the two-signal fixture and with an overflowing buffer.
- **D2, the buffer.** `ftz_probe_add` refuses a row when `n >= cap` and sets the overflow flag; `ftz_probe_at` bounds-checks the later lookups; `FTZ_PROBE_MAX_ROWS` 3,300 covers the stated worst case (4 × 256 CAND + 3 × 400 LOW + 1,024 SUB = 3,248), asserted by a test. The small-buffer test (capacity 1, 5, 40) checks the rows that fit are the first rows, unchanged, and the output is unchanged.
- **The outcome codes are exclusive and exhaustive.** Every kept CAND row gets exactly one outcome from `ftz_probe_finish_cand`, driven by what the publish loop decided (`pr_out` / `pr_gate`): published (A, B, CQ), `DUP` (the DR-3 rule, including a result replaced by a stronger duplicate, tier B re-finding a known payload, an earlier round's payload), `GATE` (unpack failure, F1b in round 0, the residual accept rule, capacity), the failure stage codes, and `B_SKIP` / `B_NOC3`; a test asserts that a finished cycle leaves no CAND undecided and that the published-outcome rows equal the published results.
- **D3, managed side.** `LeanCycleParams(..., Probe, ProbeCapacity)`, `LeanCycleOutcome.ProbeRows` / `ProbeOverflow`, the two wire structs (64 and 24 bytes). `internal`; the daemon never sets it. The harness can reach it through its existing interop wrapper (`StageProbeInterop`), so QA's part needs no `src/` change.
- **D4, documents.** Shim 20260080; no VERSION bump (test-only; `check_version_bump` OK); the OpenSpec change has a section; no new FR.

## Minor notes (none blocks)

1. **`NOT_KEPT_CAP` (13) is never written on a CAND row.** The cap cuts before `ftx_find_candidates` returns; the analysis must use the LOW row's `Kept = 2` for that case (the Developer documents it). **A LOW row's `Kept` is a reason (0, 1, 2), not the CAND row's 0 or 1:** read it by `Kind`.
2. **CAND positions are the lattice position, SUB positions are the published (refined) frequency.** Matching a SUB row to a candidate, or a candidate to a WSJT-X decode, needs the spec's tolerance (±3.2 Hz, ±0.16 s); an exact match would miss.
3. **Suppression is the round's total subtraction in the footprint:** a neighbour subtracted in the same round counts too, and `-999` means "not measured" (the footprint outside the waterfall or less than half inside, or the round ended before the residual spectrogram). The K-class medians must leave `-999` out and count it separately.
4. **The probe adds work when on** (one extra candidate search per round 1 to 3 and a footprint sum per subtracted signal): **CPU and last-batch figures from a probe run are not comparable with a normal run.** The probe replay's published decodes (rate, matched, ours) are, by the byte-identical test; its CPU and latency are not, and the report must say so.
5. **The Windows `libft8.dll` is committed; the Linux `.so` and macOS `.dylib` are two shims behind** (20260078 on `main` now, CI's bot PR for 20260079 is superseded by this commit's 20260080). Expected; the next bot PR after the merge refreshes them.

## Next

QA writes the harness part (`--lean-probe 1`, `--probe-out`, one TSV row per probe row; no `src/` change) and runs the one replay of the DR-3 + probe build on S40, H40 and H20; the free check is S40's matched 5,737 and ours 6,009. `pre_merge_check` and the push come once, with the sprint PR, on the Captain's go.
