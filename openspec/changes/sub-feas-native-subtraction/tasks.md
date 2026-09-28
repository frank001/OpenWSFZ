## 1. Pre-implementation decisions (record before writing the fit loop)

- [ ] 1.1 Confirm or override `design.md` Decision 2's recommendation (native C in `ft8_shim.c`/a new
      linked source file, vs the C# `Ft8Decoder` wrapper boundary) — record the final choice and its
      rationale as an addendum to `design.md` before starting 3.x. Do not start implementation on the
      recommendation alone without this recorded confirmation.
- [ ] 1.2 Select a permissively-licensed (MIT/BSD/ISC) FFT library per `design.md` Decision 3 (e.g.
      KissFFT, PocketFFT) — **FFTW is excluded (GPL)**. Record the choice and add its licence file to
      `native/` alongside the existing bundled-dependency licences.
- [ ] 1.3 Check the current state of the open `FT8_SHIM_VERSION` renumbering item
      (`dev-tasks/2026-09-03-shim-version-renumber-rc1rc2-and-rc4-branches.md`) and every live/unmerged
      branch's pin (`main`=`20260051`, `decoding_improvement`=`20260054` at time of writing — verify,
      do not assume current) before picking the next literal version integer.
- [ ] 1.4 Decide the per-signal buffer pooling strategy and its concurrency cap (`design.md` Decision 4 /
      Open Questions) — a bounded pool, not one allocation set per decoded signal with no upper bound.

## 2. Algorithm port (design.md Decision 1)

- [ ] 2.1 Port `fine_fit_with_drift`'s coarse-to-fine search exactly: `(Δt, Δf)` at `ḟ=0` (±100 ms @
      1 ms), then `ḟ` search (`[-0.10,+0.10] Hz/s` @ 0.005 steps, `Δf` re-fit each step), then `Δt`
      refined once more — same order, same ranges, same `n_fft=262144` for the FFT-based `Δf` search.
      Reference: `qa/rr-study/sub-feas/fitter.py:88-209` (on `qa/sub-feas`, unpushed — pull the branch
      or request the file).
- [ ] 2.2 Port `lp_envelope`'s Hann-windowed moving-average complex gain, `W*=0.32s`, **including the
      `W ≥` full-transmission degenerate case** (single complex scalar) as a correctly-computed special
      case of the general windowed computation, not a separate code path that the general path never
      actually reaches in testing.
- [ ] 2.3 Port `subtract`: `s_hat = Re{c(t)·template(t)}`, subtracted from a copy of the original buffer.
      Confirm (test 4.x) that all fits for a cycle are computed against the **original** buffer, and all
      subtractions applied to **one** shared residual copy — not sequential/iterative.
- [ ] 2.4 Implement the residual-pass invocation: call the existing decode entry point a second,
      unmodified time on the residual buffer.
- [ ] 2.5 Implement payload-based merge/dedup, including the RR73 on-air-sentinel vs re-encoded-text
      asymmetry (reference `qa/rr-study/sub-feas/stage2.py:63-77`'s `_same_qso`/`_is_rr73_std` — port the
      comparison logic, not just its result).
- [ ] 2.6 Reuse this repo's own GFSK template synthesis convention (already used natively / mirrored in
      `qa/rr-study/synth/modulator.py`) — do **not** reintroduce a CP-FSK or fixed-phase-zero model; that
      is the specific defect that sank two of the three prior attempts.

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
