## 1. Pre-implementation decisions (record before writing the fit loop)

- [x] 1.1 Confirmed by the Captain 2026-09-28: native C, recommended in `design.md` Decision 2.
      **Shape revised same session** (2nd design.md addendum): per-signal native entry point, not one
      per-cycle call — see 1.4's note and the "Decision 2's shape revised" addendum (SEH
      crash-containment is per-OS-thread; a single per-cycle call parallelized with internal native
      worker threads would not be crash-isolated the way per-signal P/Invoke calls are).
- [x] 1.2 Confirmed by the Captain 2026-09-28: **KissFFT** — already vendored/linked into `libft8.dll`
      today (`native/ft8_lib_vendor/fft/kiss_fft.c`/`kiss_fftr.c`), and benchmarked ~6.5% faster than
      PocketFFT at the real `n_fft=262144` workload on this toolchain (2.41ms vs 2.57ms/call, both
      real upstream sources, MSVC `/O2`). See design.md's Decision 3 addendum for the full benchmark
      writeup, including the early runtime-feasibility finding it also surfaced. No new licence file
      needed to add (KissFFT's `LICENSE`/`COPYING` gap in `native/ft8_lib_vendor/fft/` predates this
      change — noted as a one-line incidental fix, not a blocker).
- [ ] 1.3 Preliminary mechanical check done (2026-09-28): swept `FT8_SHIM_VERSION` across all 60
      local+origin branches — highest live value is `20260054` (`decoding_improvement`); `20260055`
      currently free. **Re-verify immediately before the actual version-bump commit** (per this task's
      own caution) — this is a preliminary read, not the final pin.
- [x] 1.4 Decided 2026-09-28, as a direct consequence of 1.1's shape revision: **no shared pool data
      structure needed.** Each per-signal native call is self-contained (allocates its own heap
      buffers on entry, frees before returning) — the only concurrency bound needed is the C#-side
      `Parallel.ForEach`/`Task` degree-of-parallelism cap, proposed `Math.Min(Environment.ProcessorCount,
      4)` (~9.6MB worst-case concurrent template memory), satisfying the spec's "concurrently-allocated
      per-signal buffers are bounded" scenario directly. Open to retuning once task 8.1 has real
      numbers.

## 2. Algorithm port (design.md Decision 1)

- [x] 2.1 Ported `fine_fit_with_drift`'s coarse-to-fine search exactly, in
      `native/ft8_lib_vendor/subfeas/subfeas_fit.c` (`fine_fit_with_drift`, `freq_search`): `(Δt, Δf)`
      at `ḟ=0` (±100 ms @ 1 ms, 201 candidates), then `ḟ` search (`[-0.10,+0.10] Hz/s` @ 0.005 steps,
      41 candidates, `Δf` re-fit each step), then `Δt` refined once more via direct correlation (no
      FFT) — same order, same ranges, same `n_fft=262144` **complex-to-complex** FFT (corrected from
      an initial wrong real-to-complex assumption during the Task 1.2 benchmark — see design.md's
      Decision 3 correction note; `mixed = seg * conj(r_base)` is complex). Verified by round-trip
      self-test (below), not yet against `fitter.py` output directly (no Python/native cross-check
      harness exists yet — a gap worth closing before task 8, not closed here).
- [x] 2.2 Ported `lp_envelope`'s Hann-windowed moving-average complex gain, `W*=0.32s` (`lp_envelope`),
      **including the `W ≥` full-transmission degenerate case** as a real branch in the same function
      (`w_samples >= N_TX`), not a separate code path.
- [x] 2.3 Ported `subtract`: `s_hat = Re{c(t)·template(t)}` (inlined in `ft8_subfeas_fit_signal`,
      written into the caller's full-cycle-length output buffer at the fitted position). Confirmed: all
      fits for a cycle are computed against the caller-supplied analytic buffer (`x_a_re`/`x_a_im`,
      populated once per cycle by the new `ft8_subfeas_compute_analytic`, unmutated by any fit call);
      one call fits and returns one signal's contribution — the **accumulation** into one shared
      residual copy is a C# orchestration responsibility (task 2.4/4.x), not yet implemented.
- [x] 2.4 Implemented the residual-pass invocation in
      `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs` (`SubtractionPass.RunAsync`): sums all
      per-signal `out_shat` buffers into one residual copy of the exact PCM pass-0 decoded
      from, then calls the **existing, unmodified** `IFt8NativeInterop.DecodeAll` on it — no
      new native decode entry point, per design.md's Decision 2 addendum. Per-signal fits run
      concurrently (`Parallel.For`, bounded by a caller-supplied degree-of-parallelism — the
      1.4 concurrency cap, not yet wired to a concrete config value since §5's flag doesn't
      exist yet). Decision 4's "any AV → whole cycle falls back, no partial state" contract is
      enforced: an access violation on any one signal's fit, or on the residual decode itself,
      returns no new decodes rather than a partial set. **Not yet wired into `Ft8Decoder`'s live
      `DecodeAsync` path** — that's §5 (config flag), the next increment; this is a standalone,
      independently-tested unit today.
- [x] 2.5 Implemented payload-based merge/dedup in `src/OpenWSFZ.Ft8/Subfeas/SubfeasPayload.cs`
      (`ExtractPayload77`, `ExtractStdFields`, `SameQso`), including the RR73 on-air-sentinel vs
      re-encoded-text asymmetry (ported from `stage2.py`'s `_same_qso`/`_is_rr73_std` and
      `pack77_fields.py`'s exact bit boundaries, both read directly rather than assumed). Payload
      extraction (79 tones → 77-bit payload) is new — not itself mirrored from the Python
      reference (which gets payload77 from its own encoder's internal state) — derived from this
      project's own protocol constants (Costas positions, Gray-code map) and the
      systematic-LDPC convention `ft8_ldpc_decode_llrs`'s own `out_a91` doc comment already
      establishes. **Cross-checked against the REAL native encoder** (not a fake) in
      `SubfeasPayloadTests.cs` — a real RR73-encoded message's extracted fields match
      message.c's own layout exactly (i3=1, ir=0, igrid4=32403), the strongest available
      correctness signal for this port.
- [x] 2.6 Reused this repo's own template synthesis convention — **not** `Ft8AudioSynthesiser.cs`
      (checked: that file's own docstring says "rectangular frequency pulse (no Gaussian shaping)",
      48kHz, a different/unrelated TX code path) — the actual validated convention is
      `qa/rr-study/synth/modulator.py`'s `instantaneous_phase`/`_gaussian_pulse` (true Gaussian-shaped
      GFSK, `BT=2.0`, ported at 12kHz to match the decode-domain sample rate: `SPS=1920`,
      `N_TX=151680`, matching `fitter.py`'s own asserted constant). Confirmed **not** reintroducing a
      CP-FSK/fixed-phase-zero model.

**Verification so far (round-trip self-test, `SUBFEAS_SELFTEST` build, scratch-only, not part of the
shipped DLL):** a known synthetic signal — tones, frequency, DT, and (in one case) a nonzero drift
rate — synthesized with this module's own `r_fit_drift`, embedded **off-centre** from the search
grid's nominal position (so the ±100ms/±2Hz/ḟ search must actually search, not trivially land on the
centre candidate) — is recovered with 35.9dB residual-energy suppression; the degenerate centred case
reaches 90.8dB. This confirms internal self-consistency of the ported search/envelope/subtract math,
**not** validation against `fitter.py`'s actual numeric output or real/WSJT-X-corroborated audio —
that remains open (a Python/native cross-check would strengthen this further; task 8's live/
second-corpus gates are the real bar).

**Wired into the real build** (not just scratchpad): `ft8_shim.h` (shim 20260055, two new exports
declared), `rebuild_shim.bat` (compiles/links `subfeas_fit.c`), `build_linux.sh` (mirrored, unverified
— no Linux toolchain on this Windows session), `Ft8LibInterop.cs` (`ExpectedShimVersion` bumped),
`libft8.version.txt`. Full `dotnet build` (0 warnings) and `dotnet test` run: `OpenWSFZ.Ft8.Tests`
(321/321) green — confirms existing decode output is unaffected (no call site touches the new code
yet). One unrelated pre-existing flake (`CycleArchiveServiceTests`, documented in
`flaky-cyclearchiveservice-manifest-test-todo.md`) reproduced and confirmed non-blocking on rerun.

## 3. Memory safety (design.md Decision 4, spec MODIFIED heap-allocation requirement)

- [ ] 3.1 Heap-allocate (or draw from the pool decided in 1.4) every new buffer: residual PCM, per-signal
      complex templates, FFT working buffers, envelope arrays. No stack array for any of them, anywhere
      reachable via P/Invoke from a .NET thread pool thread.
- [ ] 3.2 Implement graceful degradation on any allocation failure: fall back to the single-pass (no
      subtraction) result for that cycle, log the failure, do not crash and do not leave partial state.
- [ ] 3.3 Code review checkpoint (self-review before QA review, §7): grep the new source for any
      fixed-size local array above 100 KB in a function reachable from the P/Invoke boundary — this is
      exactly what the first crash's own post-mortem should have caught earlier than it did.

## 4. Distinctness from `K_MAX_PASSES` (spec ADDED requirement)

- [ ] 4.1 Confirm `K_MAX_PASSES` remains `2` and unmodified by this change — add a test asserting
      `ft8_get_max_passes()` still returns 2 with the subtraction flag both on and off.
- [x] 4.2 Log the residual-decode pass under a distinct message, not the existing per-`K_MAX_PASSES`-pass
      log line pattern (`"Iterative subtraction: pass N of 2, K new decodes"` stays exactly as-is and
      unrelated to this new pass's own logging).
      **Done in 2b39cf18:** template "Sub-feas residual pass: residualDecodes= elapsedMs= deadlineAbandoned= containedException= fittedSignals=", emitted once per RunAsync call, flag ON only.

## 5. Config flag (spec ADDED requirement)

- [x] 5.1 Added `DecoderConfig.SubtractionEnabled` (default `false`), following the exact
      `[JsonConstructor]`-with-defaults pattern the existing `OsdNhardMax`/`Nhard40MigrationApplied`
      fields already use (`src/OpenWSFZ.Abstractions/DecoderConfig.cs`). **Not added: a web-UI
      checkbox** — `openspec/changes/archive/2026-07-02-decoder-settings-page/`'s convention covers
      the config-field shape, but a UI control is a separate, larger surface this scoped-build
      increment left out; the flag is settable today via a direct config-file edit or
      `POST /api/v1/config` (full-replace, HK-035). Worth flagging to QA/the Captain as a real gap
      before any operator-facing use, even though it's outside the SubtractionPass/native scope
      this build's own risk is concentrated in.
- [x] 5.2 Wired `Ft8Decoder.SetSubtractionEnabled(bool)` (volatile field, read once per cycle) and
      called it from both `Program.cs` call sites that already call `SetDecodeParams`
      (startup + `configStore.OnSaved`). With the flag off (default), `DecodeAsync` never touches
      `native` after pass-0 — byte-identical to pre-change behaviour, confirmed by test 6.1.
- [x] 5.3 Confirmed by test 6.2 — `SetSubtractionEnabled` takes effect on the very next
      `DecodeAsync` call, no rebuild (same volatile-field mechanism `SetDecodeParams` already uses).

## 6. Tests

- [x] 6.1 `SubtractionFlagTests.FlagOff_Default_NeverCallsSubfeasComputeAnalytic` — flag off,
      `SubfeasComputeAnalytic` never called even with a re-encodable pass-0 decode present;
      `DecodeAll` called exactly once (no residual pass).
- [x] 6.2 `SubtractionFlagTests.FlagOn_NextCycle_AppendsGenuinelyNewResidualDecode` — flag set
      `true` on an already-constructed `Ft8Decoder`, next `DecodeAsync` call picks it up and a
      genuinely new residual-pass decode is appended to the returned results.
- [x] 6.3 `AllFitsAgainstOriginalBuffer_NotSequential` — **true by construction, not yet given its
      own dedicated test.** `SubtractionPass.RunCore` passes the SAME `xaRe`/`xaIm` (computed once,
      read-only) to every concurrent `SubfeasFitSignal` call; accumulation into the residual only
      happens AFTER all fits complete (§ step 3), so no fit can ever see another's subtraction —
      structurally impossible for this to be sequential given the current control flow. A test that
      asserts this explicitly (e.g. a fake `SubfeasFitSignal` capturing the `xaRe`/`xaIm` array
      identity/contents it was called with across ≥2 concurrent calls) would still be worth adding.
      **Done in 2b39cf18** (SubtractionLogLineTests), mutation-checked by QA.
- [x] 6.4 Covered by `SubfeasPayloadTests`' RR73 asymmetry tests (cross-checked against the real
      native encoder) and `SubtractionPassTests`/`SubtractionFlagTests`' "same QSO re-decoded from
      residual is filtered" cases — payload-based, not text-based, dedup is exercised directly.
- [x] 6.5 `MaxPassesUnaffectedBySubtractionFlag` (§4.1) — **not yet a dedicated test.** True by
      construction (this change never touches `ft8_get_max_passes`/`K_MAX_PASSES`), same caveat as 6.3.
      **Done in 2b39cf18.**
- [~] 6.6 `AllocationFailure_FallsBackGracefully_NoCrash` — **not started.** Needs a native test hook
      or constrained-memory harness to genuinely inject a `malloc` failure inside
      `workspace_alloc` — not achievable from the C# test suite alone.
      **Managed half done in 2b39cf18** (rc -1 from ComputeAnalytic and FitSignal, decoder level); native malloc-failure injection NOT done, unmet by design: it would change libft8.dll and void the flag-OFF control (a=b=c identical on 182/182 cycles, ruling 2).
- [ ] 6.7 Expand G6 fixture answer keys — **DEFERRED by Captain decision (2026-09-29) until after §8 (the runtime gate); answer keys are only worth adding once enabling the flag is realistic. Needs a flag-ON replay of the G6 fixtures and per-signal QA approval when it resumes.**
- [ ] 6.8 Full `dotnet test` green on all three platforms — **Windows only, this session** (`OpenWSFZ.Ft8.Tests`
      346/346, full solution green, flag both on and off exercised). Linux/macOS unverified — no
      toolchain access on this Windows Developer session; `build_linux.sh` was updated (§ prior
      commit) but never run.
- [x] 6.9 QA review R1-R3 (2026-09-29): all three required changes landed in 91444300 and were re-verified by QA (Ft8.Tests 353/353 in a detached worktree; no --filter). R1 thread-local AP state set/cleared on the residual DecodeAll thread; hash table confirmed process-global (ft8_shim.c:787, :1489), so no change needed there. R2 whole residual pass contained, pass-0 results never lost. R3 cooperative 13 s deadline (cannot interrupt an in-flight native call); 26 s FFT-only benchmark stands, so 8.1 is the real runtime gate.

## 7. Stability gate — independent of decode-rate accuracy (spec ADDED requirement)

> **Captain's decision, 2026-09-30 (via the Architect, spec §5f): §7 is MET on existing evidence** and no separate stress run is
> required. The evidence is two flag-ON multi-hour replays (the §8.1 replay 20:49Z–00:27Z, about 3.6 h, and the Stage A acceptance
> 10:11Z–13:54Z, about 3.7 h), each with 0 access violations, 0 contained exceptions and 0 non-zero process exits. **Stated gaps:**
> those runs held only busy cycles (no silence or single-signal mix) and measured no memory, so **memory is checked in the first
> on-air flag-ON run instead**. The Captain: a separate run would be "quite excessive, with also 2x 3.6h already in the pocket".

- [x] 7.1 Run a sustained, multi-hour, multi-cycle stress pass with the flag enabled against varied real
      or replayed audio (silence, single-signal, and dense multi-signal cycles) — the historical crashes
      were never caught by a decode-rate corpus; this gate exists specifically because of that history.
- [x] 7.2 Confirm no crash and no unbounded memory growth attributable to the subtraction path over the
      run (HK-019-style orphan/resource check).
- [x] 7.3 Report the stress result plainly, including if it fails — a FAIL here is a valid, useful
      result (mirrors how Stage 1's own FAIL was treated as real and reportable, not something to route
      around).

## 8. Build-time measurement gates (spec ADDED "Live-use readiness" requirement — these gate LIVE USE, not this change's own merge)

- [ ] 8.1 Measure decode-cycle runtime with the flag enabled, against the 13 s hard / 30 s CI budget.
      Report the result plainly whether it passes or fails — this is the Architect-flagged "feasibility
      not measured" risk becoming an actual number for the first time.
- [ ] 8.2 Run a decode-rate acceptance measurement on a corpus **independent of** `SUB-FEAS`'s own 40m
      corpus, using the same replay-vs-live control methodology as Stage 2, and confirm a net
      improvement ≥ the WIN bar (≥1.0pp, 95% CI lower bound) SUB-FEAS itself used.
- [ ] 8.3 **CAPTAIN DECISION** — present 8.1 and 8.2's results (pass or fail, either way) before the flag
      is enabled in any live endurance or production run. This is the Architect's originally-recommended
      pre-build acceptance step, resequenced to run here instead, per the Captain's 2026-09-28 choice —
      not omitted.

## 9. Documentation and spec reconciliation

- [ ] 9.1 Archive this change's spec delta into `openspec/specs/iterative-subtraction/spec.md` per the
      normal `openspec archive` flow (Requirements section only — the delta mechanism does not touch
      freeform narrative sections, so 9.2–9.4 are separate, manual edits).
- [ ] 9.2 Correct the spec's stale "Current deployed shim" line (`49ea303`/`20260009`) to the actual
      shim landing with this change.
- [ ] 9.3 Add a dated entry to the spec's "Acceptance Criteria" / history narrative recording this
      change's method, the SUB-FEAS PoC result it rests on, and §8's build-time measurement outcomes.
- [ ] 9.4 Add a `REQUIREMENTS.md` FR entry for the new config flag (design.md Decision 6).
- [ ] 9.5 Update `VERSION`/`libft8.version.txt` per this project's standard shim-change convention (all
      three platform entries).

## 10. QA review and Captain sign-off

- [ ] 10.1 QA reviews the diff against this `tasks.md` and `design.md` (HK-002/HK-006) — in particular
      §3 (memory safety) and §7 (stability gate) are treated as hard blockers, not advisory. **§8 (8.1-8.3) is NOT a merge blocker:
      it gates LIVE USE** (the §8 header and the spec's "Live-use readiness" requirement; corrected 2026-09-30, this sentence used to list §8
      as a hard blocker, contradicting both). §7 was ruled MET by the Captain on existing evidence (2026-09-30, see §7). Code review pass 1 returned R1-R3; pass 2 approved 91444300 (code only). Open before merge: 6.3/6.5/6.6 dedicated tests, 6.7 (deferred), 6.8 Linux/macOS, 5.1 UI checkbox gap, Captain merge sign-off (HK-010). Code review pass 3 approved 2b39cf18 (code); libft8.dll unchanged 5a6a4dc0...e38c5; Ft8.Tests 364/364. Open before merge: 6.8 Linux/macOS, 5.1 UI checkbox, 6.7 deferred, 6.6 native half unmet by design, Captain merge sign-off.
- [ ] 10.2 `git diff --stat main -- src/ native/` confirmed non-empty and scoped to what this proposal's
      Impact section named — no unrelated changes folded in.
- [ ] 10.3 **CAPTAIN DECISION** — merge sign-off (HK-010). The flag remains OFF by default regardless of
      this sign-off; §8.3's separate Captain decision gates live use.
