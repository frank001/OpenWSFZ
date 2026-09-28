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
- [ ] 2.4 Implement the residual-pass invocation: call the existing decode entry point a second,
      unmodified time on the residual buffer. **Not started** — this is the C# orchestration layer
      (sum all per-signal `out_shat` buffers into one residual, call `ft8_decode_all` again — design.md's
      Decision 2 addendum: reusing the existing entry point unmodified, no new native decode call).
- [ ] 2.5 Implement payload-based merge/dedup, including the RR73 on-air-sentinel vs re-encoded-text
      asymmetry (reference `qa/rr-study/sub-feas/stage2.py:63-77`'s `_same_qso`/`_is_rr73_std` — port the
      comparison logic, not just its result). **Not started** — C# orchestration layer, same as 2.4.
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
- [ ] 4.2 Log the residual-decode pass under a distinct message, not the existing per-`K_MAX_PASSES`-pass
      log line pattern (`"Iterative subtraction: pass N of 2, K new decodes"` stays exactly as-is and
      unrelated to this new pass's own logging).

## 5. Config flag (spec ADDED requirement)

- [ ] 5.1 Add the flag to the existing decoder-settings config surface (follow
      `openspec/changes/archive/2026-07-02-decoder-settings-page/`'s established pattern), default
      `false`.
- [ ] 5.2 Confirm decode output is byte-identical to pre-change behaviour with the flag off (test 6.1).
- [ ] 5.3 Confirm the flag takes effect on the next decode cycle without a rebuild (test 6.2).

## 6. Tests

- [ ] 6.1 `SubtractionFlagOff_DecodeOutputUnchanged` — byte-identical output vs pre-change baseline.
- [ ] 6.2 `SubtractionFlagOn_RuntimeConfigurable` — flag toggled without rebuild, next cycle picks it up.
- [ ] 6.3 `AllFitsAgainstOriginalBuffer_NotSequential` — construct a cycle with ≥2 signals, assert each
      fit's input segment matches the original (pre-subtraction) buffer at that position, not a
      partially-subtracted one.
- [ ] 6.4 `ResidualDecode_PayloadDedup_NotTextDedup` — construct a case where text differs but payload
      matches (or the RR73 sentinel asymmetry applies) and assert correct dedup behaviour both ways.
- [ ] 6.5 `MaxPassesUnaffectedBySubtractionFlag` (§4.1).
- [ ] 6.6 `AllocationFailure_FallsBackGracefully_NoCrash` — inject an allocation failure (a test hook or
      a constrained-memory harness) and assert the single-pass fallback, not a crash, and a logged
      failure.
- [ ] 6.7 Expand G6 fixture answer keys per this project's established convention (see
      `DEV-BRIEFING-iterative-subtraction.md` AC-IS-2 for the original process this mirrors) for any
      newly-recoverable synthetic fixture signals — QA reviews and approves each addition individually
      before merge (§7).
- [ ] 6.8 Full `dotnet test` suite green on all three platforms, subtraction flag both on and off.

## 7. Stability gate — independent of decode-rate accuracy (spec ADDED requirement)

- [ ] 7.1 Run a sustained, multi-hour, multi-cycle stress pass with the flag enabled against varied real
      or replayed audio (silence, single-signal, and dense multi-signal cycles) — the historical crashes
      were never caught by a decode-rate corpus; this gate exists specifically because of that history.
- [ ] 7.2 Confirm no crash and no unbounded memory growth attributable to the subtraction path over the
      run (HK-019-style orphan/resource check).
- [ ] 7.3 Report the stress result plainly, including if it fails — a FAIL here is a valid, useful
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
      §3 (memory safety), §7 (stability gate), and §8 (measurement gates) are treated as hard blockers,
      not advisory.
- [ ] 10.2 `git diff --stat main -- src/ native/` confirmed non-empty and scoped to what this proposal's
      Impact section named — no unrelated changes folded in.
- [ ] 10.3 **CAPTAIN DECISION** — merge sign-off (HK-010). The flag remains OFF by default regardless of
      this sign-off; §8.3's separate Captain decision gates live use.
