## 1. Pre-implementation decisions (record in `design.md` before writing code)

- [x] 1.1 M1 consumer precondition (QA, 2026-09-30): four QA scripts parse the LDPC-fail Debug line; the Captain
      chose **defer M1**. Recorded in `design.md` D7. **Do not implement M1.**
- [ ] 1.2 Base: branch `feat/sub-feas-speed-redesign` off `feat/sub-feas-native-subtraction` (`ab95bea1`, code
      `2b39cf18`). Confirm `libft8.dll` SHA-256 of the base is `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`
      before changing anything, and keep that DLL: E1 needs it.
- [x] 1.3 Workspace ownership is **decided** (Architect, Amendment 1; `design.md` D2): a bounded, locked pool of heap
      workspaces, size = effective `subtractionMaxThreads`, leased per fit and returned in a `finally`, no native
      thread-local state, freed at decoder dispose. The Developer records only the pool API shape and how a changed
      thread count resizes it (at the next cycle boundary, nothing in flight).
- [ ] 1.4 Record the exact ABI shape of the cancel flag (D3) and of the M2 diagnostics switch.
- [ ] 1.5 Pick the next `FT8_SHIM_VERSION` literal after checking `main` (`20260051`), `decoding_improvement`
      (`20260054`), the base branch (`20260055`) and any live branch's pin. Do not assume.
- [ ] 1.6 Confirm how the new config key survives the in-flight config-save work (#193): the config POST is a
      full replace (HK-035). Coordinate with whichever session owns that workstream.

## 2. Measure first: make the cost map checkable (test-only, no product-path change)

- [ ] 2.1 In a test-only console tool under `tests/` (`Ft8.FitProbe` or similar; **not** in the product path),
      time one `ft8_subfeas_compute_analytic` call and, for a fixed set of signals, each fit phase (Δt search, ḟ
      search, final template, Δt refine, envelope) and one residual `DecodeAll`, on the base DLL. Write **integers
      and stamps only**; never message text (HK-037/NFR-021).
- [ ] 2.2 Report the per-phase milliseconds and the **longest single uninterruptible stretch a cancel flag would
      have to wait through** (feeds `design.md` D3 and D5).

## 3. E1 hash probe (before any optimisation)

- [ ] 3.1 Build the E1 probe in `tests/` (test-only): given a `libft8.dll` path and a list of cycle WAV files, it
      decodes pass-0 **through that DLL**, encodes each re-encodable decode, fits with **no deadline**, and writes
      one CSV row per (stamp, signal index): `rc`, `sha256(out_shat)`, plus the pass-0 decode **count** and the
      flag-OFF decode outcome fields (never text). Assert 180 000 samples per file in code.
- [ ] 3.2 Run it once on the base DLL over a small synthetic/fixture set and commit the resulting hashes as data
      (hashes and integers only). This is the golden the optimisations are checked against during development.
      QA runs the real-corpus E1 at acceptance (§10).

## 4. Native: exact optimisations (A1, A2, A3)

- [ ] 4.1 **A1.** In `subfeas_fit.c` compute the smoothed tone track **once per signal**; `r_fit_drift` applies only
      the ḟ-dependent drift term and the cos/sin. Hold the smoothed track at the precision the old code held it
      (`design.md` D1). Re-run the golden hashes.
- [ ] 4.2 **A2.** FFT the Gaussian pulse and the Hann window once per workspace and reuse their spectra in
      `fft_convolve_same`. Re-run the golden hashes.
- [ ] 4.3 **A3.** Implement the bounded, locked workspace pool (§1.3): each workspace holds both
      `kiss_fft_alloc(262144)` plans, the cached spectra and `gaussian_pulse`, built once and reused; leased per fit,
      returned in a `finally` (a cancelled or failed fit still returns its lease). Heap only, no stack array above
      100 KB anywhere reachable from P/Invoke (base change task 3.3 self-review applies). **No native thread-local
      state.** Bounded by the thread count; freed at decoder dispose, which cannot free a leased workspace;
      allocation failure falls back to pass-0-only as today.
- [ ] 4.4 Build flags are **unchanged**. No `/fp:fast`, no `/arch:AVX2`, no vectorised sin/cos. If a change here
      is tempting, it is Stage B (§11), not this change.
- [ ] 4.5 After each of 4.1–4.3, run the E1 probe against the base DLL's golden. Any difference: revert that item.

## 5. Native and managed: hard deadline (A5)

- [ ] 5.1 Add the cancellation flag parameter to `ft8_subfeas_fit_signal` per §1.4; check it at entry and at the top
      of every Δt candidate, every ḟ candidate and each envelope iteration; on non-zero, zero `out_shat`, free
      nothing that is pooled, return `-4`. NULL flag means no deadline (the no-deadline path stays identical).
- [ ] 5.2 Managed: allocate the flag (unmanaged or pinned) for the whole of `RunCoreUnguarded`, free it only after
      `Parallel.For` returns; set it with a volatile write at `budget − reserve`. Introduce the named constant
      `SubtractionResidualDecodeReserve` = **1 500 ms** (Architect's Amendment 1; no literal).
- [ ] 5.3 Do not start the residual `DecodeAll` when less than the reserve remains; abandon as a deadline outcome.
- [ ] 5.4 Map `-4` to a deadline abandon inside the interop/`SubtractionPass` (`design.md` D4): **not** an exception,
      not `containedException`. `deadlineAbandoned=true`, `containedException=false`, `ResidualDecodes=0`.
- [ ] 5.5 Confirm the existing `Sub-feas residual pass:` line still carries exactly its current fields
      (`residualDecodes`, `elapsedMs`, `deadlineAbandoned`, `containedException`, `fittedSignals`). It is the R4/R4′ instrument.

## 6. Config: thread count (A4)

- [ ] 6.1 Add `decoder.subtractionMaxThreads` to the decoder settings model: **`0` = auto = `max(1, ProcessorCount − 2)`,
      and `0` is the default**; any other value clamped to `[1, ProcessorCount]` (negative becomes 1, confirmed by the Architect); log **one** warning when the config is applied, using the
      existing clamp-with-warning pattern in `POST /api/v1/config` (`WebApp.cs` ~578), **never per cycle**; read per
      cycle, no settings-page control. Add a test: an out-of-range value logs exactly one warning at apply and none
      over N subsequent cycles. Replace the `Math.Min(Environment.ProcessorCount, 4)` at `Ft8Decoder.cs:63`.
- [ ] 6.2 Until the config-save fix (#193, Engineer) lands, a Settings save resets this key to 0 = auto and the flag
      to OFF; both are safe. Confirm that, and re-confirm after that fix lands that a save neither drops nor
      corrupts the key (§1.6).
- [ ] 6.3 Add the `REQUIREMENTS.md` FR entry for the key, following base change task 9.4.

## 7. Monitoring on the hot path (M2, M3). M1 is NOT in scope.

- [ ] 7.1 **M2.** The residual `DecodeAll` (`SubtractionPass.cs`) runs with pass-0 diagnostics disabled (a flag
      parameter or a separate export, per §1.4), computing nothing only a TLS getter would read. It must not change
      any decode output field. **Keep** `compute_noise_floor` (feeds the local-noise SNR fallback).
- [ ] 7.2 **M3.** Guard the Debug-only per-pass log loops (`Ft8Decoder.cs`, the counts and stats logging) with
      `logger.IsEnabled(LogLevel.Debug)`.
- [ ] 7.3 Do not touch the LDPC-fail LLR statistics (`ftx_compute_candidate_llr_stats`, `tls_llr_*`,
      `ft8_get_last_llr_stats`, `GetLastLlrStats`). M1 is deferred (`design.md` D7).

## 8. Tests

- [ ] 8.1 `Fit_NoDeadline_OutputBitIdenticalToBase` (real DLL, golden hashes from §3.2, several fixture signals).
- [ ] 8.2 `Fit_CancelFlagPresetReturnsMinus4Promptly` and `Fit_CancelFlagSetMidFitReturnsMinus4WithinOneIteration`
      (native, real DLL): `out_shat` zeroed, no leak, other in-flight fits undisturbed.
- [ ] 8.3 `SubtractionPass_DeadlineDuringFits_AbandonsAsDeadlineNotException`: a slow fake fit; assert
      `deadlineAbandoned=true`, `containedException=false`, pass-0 results kept, whole call within budget.
- [ ] 8.4 `SubtractionPass_LessThanReserveLeft_SkipsResidualDecode`.
- [ ] 8.5 `MaxThreads_ZeroIsAutoAndClamp`: a table over `ProcessorCount` ∈ {1, 2, 4, 16} and values {absent, 0 (both = auto),
      −1, 1, 999}; and `MaxThreads_ChangeTakesEffectNextCycle`.
- [ ] 8.6 `Fit_ManyWorkersManyCycles_DeterministicAndNoInterference`: N workers, many cycles, forced cancels mixed
      in; each signal's hash equals its single-thread hash. This is the stress test for §1.3.
- [ ] 8.7a `Workspace_LeaseReturnedWhenFitCancelledFailsOrThrows`, and `Workspace_PoolNeverExceedsBound_NeverBlocksAtMatchingParallelism`.
- [ ] 8.7 `Workspace_NoGrowthAfterWarmup_AndFreedAtDispose`: plateau of fit-attributable private memory over
      hundreds of cycles; released at shutdown; decode still works after re-initialisation. State in the test how
      it measures (private bytes, or a counter export if `design.md` allows one).
- [ ] 8.8 `ResidualDecode_DiagnosticsOff_OutputFieldsEqualDiagnosticsOn` (real DLL, fixtures) and
      `NoiseFloorFallback_SnrUnchanged`.
- [ ] 8.9 `DebugLogLoops_NotRun_WhenDebugDisabled`: a logger reporting Debug off; assert no formatting, no calls.
- [ ] 8.10 Existing `SubtractionFlagOff_DecodeOutputUnchanged`, the AV-containment and `MaxPassesUnaffectedBySubtractionFlag`
      tests still pass on the new native build.
- [ ] 8.11 Full `dotnet test`, no `--filter`, green; **quote the exact command line and the total in the report**
      (a filtered-out suite is silent, not green: HK-022).

## 9. Shim, version and documentation

- [ ] 9.1 Bump `FT8_SHIM_VERSION` to the literal chosen in §1.5; update the managed ABI self-test expectation and
      `libft8.version.txt` per the project's standard shim-change convention (all platform entries).
- [ ] 9.2 Rebuild the native library on every platform the project builds, per `BUILD.md`; `build_linux.sh` also
      compiles `subfeas_fit.c`. Pin the new `libft8.dll` SHA-256 in the report (actual and pinned; note that no
      independent pin exists, as before).
- [ ] 9.3 Update `BUILD.md`/export lists for any new export (shutdown, M2 switch).
- [ ] 9.4 Archive this change's spec delta into `openspec/specs/iterative-subtraction/spec.md` per the normal flow
      (after the base change has merged).

## 10. QA acceptance (QA-owned, after the build exists; **not** Developer tasks)

- [ ] 10.1 **E1 on real cycles**: the 60 pilot cycles plus every 9th `(run, stamp)` of the sorted pooled H ∪ M
      list (about 100 cycles), through the base DLL and the candidate DLL, no deadline; 100 % identical
      `(rc, sha256(out_shat))`, and identical flag-OFF outcome fields. **If not 100 %, stop; read nothing else.**
- [ ] 10.2 R0 as §8.1 (via each archive's producing DLL). Then R1′, R2′, R3, R4′ (a BAR: abandon over H ≤ 5 %), R6
      (13 000 ms, no allowance), R7 (descriptive) on the frozen `selection.json`, harness updated only for the new
      config key, **WSJT-X closed**, machine state recorded.
- [ ] 10.3 R5′: flag-OFF median on the new build ≤ 1.05 × the base build's, per run, with the base build
      **re-measured in the same session** on the same cycles (`design.md` D8; accepted by the Architect, Amendment 1).
      Report the change either way. M1 is absent: P4 is scored on M2 + M3 alone and nothing here may be credited to M1.
- [ ] 10.4 Row T (report only): R1′/R2′ at `subtractionMaxThreads = 4` on the H stratum, to separate the thread
      effect from the code effect.
- [ ] 10.5 **MERGE GATE, REPLACED (Captain, 2026-09-30, Architect spec 5g): one ~15-minute end-to-end run, done by the ENGINEER**, instead of the full native + managed flag-OFF control. **The run:** `origin/main` (c3f42362) vs the merge head `247ac391` (code-identical to the docs-only tip), `DecodeAsync` with the flag OFF, the 161 E1 cycles, a fresh process per (build, run), same order, numeric outcomes compared in order on (freqHz, dt, snr); **PASS iff 161/161.** It closes the one untested link (main's managed path vs SUB-FEAS's); the native chain is covered by the original 182-cycle control (5a6a4dc0 = merge-base = DI) and Stage A E1 (flag-OFF outcome fields identical between 2b39cf18 and ee00d118 on 161 real cycles), and the managed path by QA's interim `2b39cf18` vs `247ac391` comparison (161/161). Harness: `qa/rr-study/sub-feas/replay81` (numeric-only, 70c01fc9) and `flagoff_managed_compare.py`. If the merge head later changes its native DLL (Stage B), this run is repeated on that build.
- [ ] 10.6 Report in the standard format with both DLL SHA pins, the selection SHA, the harness commit, the exact
      command lines, the blind spot (no real cycle above 32 signals; other hardware not covered), and the
      Architect's predictions P1–P4 scored by the Architect at the acceptance ruling, not by QA.

## 11. Stage B: MOVED to §15

- [x] 11.0 Stage A failed R2′ on its p95 term only (6 410.8 vs 6 000 ms; report
      `qa/rr-study/results/2026-09-30-sub-feas-speed-stage-a-acceptance/report.md`). **The Captain accepted Stage A's timing and
      authorised Stage B as a follow-on** (2026-09-30, "option a, do stage B too", the Architect's Amendment 4). Stage B is
      **§15**, after the two-stage tasks (§13, §14), never mixed into them. The registered verdict stays "Stage A FAIL on R2′";
      the acceptance is the Captain's.

## 12. Review and sign-off

- [ ] 12.1 QA reviews the diff against this `tasks.md` and `design.md` (HK-002/HK-006). §4.3 (workspace ownership),
      §5 (deadline and flag lifetime) and §8.6/8.7 (concurrency and growth) are hard blockers, not advisory.
- [ ] 12.2 `git diff --stat main -- src/ native/` non-empty and scoped to this change's Impact list; no unrelated
      changes folded in.
- [ ] 12.3 **CAPTAIN DECISION**: merge sign-off (HK-010) and push (HK-033). The flag remains OFF by default
      regardless; any live use is a separate Captain decision after the base change's §7 and §8.2/§8.3.

## 13. Two-stage publish (Architect's Amendment 2; Developer; `src/` only, no shim bump)

- [ ] 13.1 Record in `design.md` D9 the shape of the two-batch entry on `Ft8Decoder` (a publish callback for batch 1, or a
      return of both batches). `IModeDecoder.DecodeAsync` and every current caller stay unchanged. **The entry must be
      callable from a test or replay harness without the daemon pump** (acceptance rows S1 and S2 need it).
- [ ] 13.2 **P-1/P-2.** Flag ON: map and hand batch 1 (pass-0) to the pump's existing publish path as soon as pass 0
      returns; start the residual pass only after that; publish the residual decodes as batch 2 with the same `cycleStart`,
      only if the pass completed with at least one new decode.
- [ ] 13.3 **P-3.** Same mapping for batch 2 (trim, plausibility, region, worked-before, band); the text `seen` set is per
      cycle and spans both batches; the SubtractionPass payload de-dup is unchanged.
- [ ] 13.4 **P-4.** Batch 2 to the panel, ALL.TXT (appended, same stamp), filter admission and external reporting. Read
      the external-reporting service and confirm it sends no cycle-level message twice for a two-batch cycle; record the
      finding. Confirm on the panel that batch 2 rows appear above batch 1's rows and replace nothing (`handleDecodes`
      prepends; QA verified it does not clear).
- [ ] 13.5 **P-5.** Batch 2 is **not** written to the answerer or caller channels. The answerer's idle snapshot after a
      flag-ON cycle equals batch 1.
- [ ] 13.6 **P-6.** The cycle-audio archive `TryEnqueue` runs once, at batch 1, with the pass-0 count.
- [ ] 13.7 **P-7.** The pump stays serial: no decode of the next window until batch 2 is published or the pass is abandoned.
- [ ] 13.8 **P-8.** The `Cycle {Time}: … elapsed=` line reports time to batch 1 (flag OFF identical to today). Record the
      semantic in `design.md`. The `Sub-feas residual pass:` line is unchanged.
- [ ] 13.9 **P-9.** Flag OFF: exactly one batch per cycle, byte-identical output, ALL.TXT, archive and consumer deliveries.
- [ ] 13.10 Tests **S3 (a)-(f)** in code: (a) the answerer and caller receive exactly one batch per flag-ON cycle; (b)
      `_lastIdleDecodeBatch` after a flag-ON cycle equals batch 1; (c) ALL.TXT holds batch 1's lines then batch 2's, same
      stamp, no duplicate text in the cycle; (d) the panel receives two `decode` events and shows the union; (e) the archive
      enqueues once; (f) flag OFF gives one publish per cycle.
- [ ] 13.11 Tests (g)-(j), accepted by the Architect (Amendment 3): (g) a manual engage on a batch-2 row: characterise whatever the
      answerer then does with the pending target (the double-click path does not read the idle snapshot; see `design.md`
      D9); (h) an external reply naming a batch-2 station is ignored with the existing log line; (i) the pump starts no next
      window before batch 2 is published or abandoned; (j) the external-reporting channel sends no cycle-level message twice.
- [ ] 13.12 Full `dotnet test`, no `--filter`, green; quote the exact command and the total. Two-stage publish touches the
      pump and `Ft8Decoder` but not `libft8.dll`: confirm the DLL SHA-256 is unchanged (`ee00d118…990e4c`).

## 14. QA acceptance of two-stage publish (QA-owned; after §13 builds)

- [ ] 14.1 **S1**, both builds in **fresh processes over the same cycles in the same order** (sorted `(run, stamp)` of
      `e1_selection.json`, 161 cycles): the union of batch 1 and batch 2 outcome fields equals the single-batch output of
      `ca0bcd9b` as a set, and batch 1 equals the flag-OFF output of the same build. Outcome fields, never text. PASS iff 161/161.
- [ ] 14.2 **S2**: over H ∪ M, time to batch 1, median per run ≤ 1.05 × the flag-OFF whole-call median measured in the same
      session; max ≤ 1 000 ms, **read per cycle against the same-session flag-OFF whole call** (Architect's Amendment 3):
      cycles whose flag-OFF call itself exceeds 1 000 ms are excluded from the max term and **counted**; if more than 1 %
      of cycles are excluded the max term is **"not evaluable"**, reported as such, not passed. The median term is
      unchanged. WSJT-X closed.
- [ ] 14.3 **S2b** (REPORT ONLY, accepted, Amendment 3): time from batch-1 publish to receipt by a WebSocket client
      **while the residual pass is running** (14 fit workers can crowd the thread pool that WebSocket delivery also
      uses), against the flag-OFF delivery time. If materially above, it goes back to the Architect before any live use.
- [ ] 14.4 **The merge control is the Engineer's end-to-end run of §10.5** (replacing the full native + managed control). QA's interim datum stands: the S1 phase of the two-stage acceptance recorded flag-OFF `DecodeAsync` outcomes for `2b39cf18` and the two-stage build in fresh processes over the same 161 cycles in the same order, identical 161/161 (an interim managed datum, not the merge control).
- [ ] 14.5 E1, R0-R7 and any Stage B rows are unchanged; batch 2's publish time is R1′'s whole-call time.
- [ ] 14.6 State in the report: **a first on-air flag-ON session is a new decision needing the Captain's explicit go**;
      nothing here implies it.

## 15. Stage B (numerics-changing; AUTHORISED by the Captain 2026-09-30, Architect's Amendment 4; a separate follow-on, after §13/§14, never mixed into them)

> **AMENDMENT 5 (2026-10-03, Captain "yes, proceed"; Architect spec §5h of `qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md`, commit `7f544638` on `arch/sub-feas-stage-b`) SUPERSEDES the finish line and the item order below.**
> Stage B is re-aimed at **batch 2's arrival time** (can a batch-2 decode get a same-slot reply?). **Order: B2 first, then B3, then B1, each only if the bar is still missed.**
> **New bar T2′:** on a replay of the 2026-09-30 night (flag ON, `subtractionMaxThreads = 8`, `nhard` 40, harness `replay81` mode `two1`, every 4th cycle of the frozen 10-01 selection), **median `T2_replay` ≤ 2.50 s**, with a same-session Stage A baseline. E2, E3, R1′, R3 and R4′ stay as bars (R4′ now read at 8 workers on the T2′ list). **T′ (4 workers) is REPORT-ONLY**, run once at the end. The old Amendment 4 text is kept below for the record where it is struck through.

~~**Finish line, fixed before any Stage B build (Amendment 4): T′ = at `subtractionMaxThreads = 4`, over the H stratum, the
deadline-abandon rate ≤ 5 % AND the max whole call ≤ 13 000 ms.** Its purpose is other hardware.~~ *(superseded by Amendment 5: T′ is report-only.)* **R2′ at 14 workers is
report-only now** (p95(H) ≤ 6 000 ms would be a bonus, not a gate). **Stop** at the first item after which **T2′ and E2, E3, R1′, R3, R4′ all pass**, or
after B1 (the last item), or when the Captain says so; if T2′ still fails after all three items, report the remaining gap (batch 2 then stays not answerable in the
same slot, which is today's state). Branch: `feat/sub-feas-stage-b` off
`feat/sub-feas-speed-redesign` (`ca0bcd9b`), not off the two-stage branch, so Stage B is measured on the same instrument as
Stage A; the two combine at merge (both are Captain decisions). **Not decided here, whatever T2′ shows:** the batch-2 → auto-QSO choice stays the Captain's
(parked 2026-10-02) and the automation stays fenced from batch 2 (P-5). A replay PASS is followed, before any reply-policy spec, by one receive-only on-air night on the accepted build; that night is a separate decision.

- [x] 15.1 **DONE (Amendment 5 §5h; `Ft8.FitProbe fitprofile`, `feat/sub-feas-stage-b` `ef7e765c`, `artefacts/sub_feas_fitprofile/`: 5 cycles, 111 fits, timed DLL equivalent to the shipped one on 111/111): median per fit 1 561 ms at 1 worker and 1 904 ms at 8; step 1 (Δt search) is 71 % and step 2 (ḟ search) 25 %, everything else under 4 %.** It ranks B2 first. Original text, kept for the record: **Profile first (Developer, test-only, no product-path change).** Re-run `Ft8.FitProbe time` on the
      **candidate** DLL (`ee00d118…990e4c`) at **1 worker and at 14 concurrent workers**, and add 4 concurrent workers (the T′
      configuration). Report per-phase milliseconds (step 1 Δt search, step 2 ḟ search, final template, step 3, envelope, the
      analytic call, one residual `DecodeAll`) and the **per-fit concurrency penalty** (the ~2× at 14 workers is unmeasured
      and is what the Architect's P2 arithmetic missed). Integers only (HK-037). The profile ranks the items; the order is now
      fixed by Amendment 5: **B2, then B3, then B1**, each only if T2′ is still missed.
- [ ] 15.2 **QA baselines, before any Stage B build:** (a) the Stage A **E3 baseline**: total `residualDecodes` of the
      candidate on the 161 E1 cycles with no deadline in effect (14 workers; assert 0 deadline abandons so it equals the
      unbounded result), from the `Sub-feas residual pass:` lines; (b) the Stage A **T reference** (already measured: 337/605
      abandoned, max 12 095 ms); (c) **the T2′ replay list (Amendment 5):** every 4th cycle (index ≡ 0 mod 4) of the frozen 10-01
      selection (`qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/selection.json`, SHA-256 over LF-normalised bytes
      `55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf`, asserted in code as `onoff_replay_run.py:52` does), about
      1 075 cycles; **the child list of the Engineer's #122 gate 4a may be reused with its SHA asserted.** The list is built and its
      count printed **before** any Stage B build. A script, not a note, asserts the SHA and the count.
- [x] 15.3 **DONE (Developer, 2026-10-03; mechanism and how to call it in `design.md` D11, "B2 as built"): a test-only build of the fit, `tests/Ft8.FitProbe/native/build_params_dll.py`, `Ft8.FitProbe fitparams` / `fitparamscompare`.** Original text: **Fitted-parameter visibility for E2 (design decision, record in `design.md` D10 before coding).** E2 compares
      per-signal Δt, Δf and ḟ between the Stage A and Stage B fits, but the shipped fit returns only `out_shat`. A
      **test-only** way to read the fitted parameters is needed (for example a build of the fit compiled with a test switch, or
      a test-only export that is not in the shipped export list). It must not change the shipped ABI beyond what the item
      itself needs.
- [ ] 15.4 *(B2 BUILT 2026-10-03 on `feat/sub-feas-stage-b`, shim 20260059, design.md D11 "B2 as built"; E2, E3, R1′, R3, R4′ and T2′ are QA's measurements and are NOT yet read; developer sanity: E2 on 12 E1 cycles identical on 257/257 fits.)* **Each item, one at a time, in the Amendment 5 order B2, then B3, then B1, each only if T2′ is still missed (B2 pruned frequency search, |f| ≤ 2.0 Hz is about ±44 of
      262 144 bins; B3 coarse-to-fine Δt, about 201 → 50 candidates; B1 faster permissive FFT, pocketfft-C only):** implement; bump `FT8_SHIM_VERSION`; pin the new DLL
      SHA-256. **E1 (bit-identity) no longer applies** to a numerics-changing item; it is replaced by:
      **E2** per fitted signal, Stage B vs Stage A, no deadline, on the E1 cycles: Δt identical ±1 step (12 samples), Δf within
      ±1 bin (0.0458 Hz), ḟ the same step, on ≥ 99 % of signals; per-cycle residual energy within ±0.1 dB on ≥ 99 % of cycles.
      **E3** total `residualDecodes`(B) ≥ 0.98 × the §15.2 baseline on the same cycles, no deadline. **Then re-time** (§15.5).
      An item that misses E2 or E3 is rejected however fast it is.
- [ ] 15.5 **Re-time each accepted item (Amendment 5 protocol; QA-owned, a TIMING run: the PC to itself, WSJT-X closed, machine state recorded).**
      **T2′ (the bar):** replay of the 2026-09-30 night on the §15.2(c) list, flag ON, `subtractionMaxThreads = 8`, `nhard` 40, harness `replay81` mode
      `two1` (records the time to batch 1 and the batch-2 time per cycle). `T2_replay` = **0.032 s** (the on-air median decode-start offset, a labelled constant)
      + time to batch 1 + residual `elapsedMs`, over cycles with ≥ 1 residual decode, **plus every deadline-ABANDONED cycle counted as T2 = +∞** (an abandoned pass delivers
      nothing in time; Architect `4301e8c5`, QA (k) note (b)); cycles whose pass **completed with 0 residual decodes stay out** (nothing to answer). **PASS iff the median of that
      population ≤ 2.50 s** (so more than half the population abandoned makes the median +∞, a FAIL). The rule lives in the predicate code of §15.12, not in prose. The 0.45 s below the 2.95 s
      condition is a margin for the unmeasured keying latency k (companion spec `qa/rr-study/2026-10-03-1235-architect-to-qa-spec-keying-latency.md`) and for
      replay against live; it is not a tolerance to spend. **Same-session Stage A baseline:** the current `main` build on the same list, reported beside every
      item (descriptive), so each item's gain is measured, not inferred. **Also bars for every item:** E2, E3 first, then R1′ (max ≤ 13 000 ms), R3, and **R4′
      (abandon ≤ 5 %, now read at 8 workers on the T2′ list)**; R6 must still hold; R5′ if the item touches the flag-OFF path. **T′ (4 workers, H) is
      report-only**, run once at the end. **Also reported (descriptive):** per-fit median at 8 workers per item; `T2_replay` p5/p95/max; the fraction of cycles
      with `T2_replay` ≤ 2.95 s by UTC hour (comparable with the lateness Q2 table); **the abandon fraction printed beside EVERY `T2_replay` figure** (design D11 note 2).
      **Reading the bar (Architect `4301e8c5`, QA note (a)):** a T2′ PASS is not by itself "same-slot answerable"; the acceptance ruling reads the measured `k_PC` (keying-latency
      spec) and says so: if `k_PC` > 0.45 s, T2′ can pass while median T2 ≤ 2.95 s − `k_PC` fails.
- [ ] 15.6 **B1 licence:** permissive only (MIT/BSD/ISC); pocketfft-C (BSD-3) qualifies; **FFTW is GPL and prohibited.** Add the
      licence file under `native/` and make `tools/LicenseInventoryCheck` pass.
- [ ] 15.7 **After the last item:** full unfiltered `dotnet test`; every DLL pinned by SHA-256 (actual and pinned). Stage B merges **after** the SUB-FEAS + config-save merge (Captain's plan); the §10.5 end-to-end flag-OFF run is **repeated on Stage B's build** (it changes the native DLL).
- [ ] 15.8 Report in the standard format with the blind spot up front: **T2′ is a REPLAY on this PC with nothing else running, not the live station**
      (live capture, WSJT-X, the web UI and the OS contend for the same cores; the 0.45 s margin is the only allowance and it also has to cover the unmeasured
      keying latency k), **and T′ (report-only) is measured at 4 workers on a 16-thread machine, a proxy for a small machine, not the same thing** (a real
      4-thread machine defaults to 2 workers and contends with the rest of the system), and no real cycle has more than 31 signals. State that the flag stays
      OFF and a first on-air flag-ON session needs the Captain's explicit go.
- [ ] 15.9 **Stop rule (Amendment 5).** After each item, in order: E2, E3, R1′, R3, R4′ first (any miss rejects the item however fast it is), then T2′. Stop at the
      first item after which all six pass, **or** after B1, **or** when the Captain says so. If T2′ still fails after all three items, report the remaining gap;
      batch 2 then stays not answerable in the same slot. **Nothing here changes the flag default, the thread default, the fence on batch 2 (P-5) or the Captain's
      parked batch-2 → auto-QSO choice.**
- [ ] 15.10 **Process and CPU rule (Amendment 5; Developer handoff `dev-tasks/2026-10-03-sub-feas-stage-b-b2-pruned-freq-search.md`).** The build is `native/` on
      `feat/sub-feas-stage-b` in a separate Developer session (HK-011), with a **new `FT8_SHIM_VERSION` per item** and the DLL pinned by SHA-256 (actual and pinned).
      🔴 **No Developer build or test suite until the Engineer reports #122 gate 4a done** (it measures decode wall-time; expected about 14:40Z on 2026-10-03)
      **unless the Captain relaxes the rule**; reading, planning and writing code is fine. The T2′ replays are themselves timing runs and need the PC to themselves
      (no Developer build or suite, no other QA/Engineer job).
- [ ] 15.11 **B2's design freedom and its limit.** The spec names "decimation plus a small FFT, or a pruned DFT" for `freq_search` (`native/ft8_lib_vendor/subfeas/subfeas_fit.c:361-394`,
      called from step 1 at `:443` (201 candidates) and step 2 at `:474`). The Developer chooses and records the choice in `design.md` D11 **before** coding. Whatever is
      chosen: only the bins with |f| ≤ `SUBFEAS_DF_RANGE_HZ` (2.0 Hz) may influence the result, the argmax tie-break must be stated (the current code keeps the first
      strictly greater magnitude, scanning bins in index order 0, 1, …, N/2−1, then −N/2 … −1), and E2's ±1-bin tolerance is the equivalence the item is judged on, so
      an interpolated or sub-bin result must be reported as such and still land within ±1 bin (0.0458 Hz) of the Stage A value on ≥ 99 % of signals.
- [ ] 15.12 **The T2′ predicate is CODE, committed before the first Stage B measurement (QA-owned; HK-021 mechanical).** A pure function in
      `qa/rr-study/sub-feas/replay_t2prime_rows.py` (new) with its tests, taking per cycle: abandoned (0/1) and ran (0/1) from the `--abandon-out` file (`stamp,ran,abandoned,contained`),
      `tb1_ms` from the `two1` CSV (`run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n`), and `residualDecodes` and `elapsedMs` from the `Sub-feas residual pass:` line (joined on
      the stamp, as `replay_speed_rows.py` does). Constants asserted in the file, not in prose: `DECODE_START_S = 0.032`, `T2_BAR_S = 2.50`, `SAME_SLOT_S = 2.95`, `KEYING_MARGIN_S = 0.45` (= 2.95 − 2.50),
      the selection SHA-256 of §15.2(c) and the list count. **Rules, each with a test on synthetic data:** (i) abandoned ⇒ `T2 = +∞` whatever its residual count; (ii) completed with 0 residual decodes ⇒ excluded;
      (iii) otherwise `T2 = DECODE_START_S + tb1_ms/1000 + elapsedMs/1000`; (iv) the median is taken over the population of (i) and (iii), and **PASS iff median ≤ `T2_BAR_S` (equal passes)**;
      (v) an empty population is **UNDEFINED, never PASS**; (vi) more than half abandoned ⇒ median `+∞` ⇒ FAIL; (vii) the output prints, beside the median, the counts of each class and the abandon fraction
      (abandoned ÷ cycles whose pass ran), plus `T2_replay` p5/p95/max over the finite values and the ≤ 2.95 s fraction by UTC hour. A run of the tests is a CPU job: not while the Engineer's #122 run is on.

