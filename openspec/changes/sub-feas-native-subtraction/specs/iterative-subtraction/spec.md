## MODIFIED Requirements

### Requirement: Option C approval gate — PoC SHALL demonstrate improvement before PCM-domain SIC implementation proceeds

A Python proof-of-concept SHALL demonstrate a measured, Captain-approved improvement before any
production PCM-domain signal-subtraction native code is written. The original form of this gate
(≥ +5 percentage-point improvement on at least 10 synthetic S7 co-channel trial cases) is satisfied
by an alternative, Captain-approved methodology for the specific method this change implements:
`SUB-FEAS` (2026-09-27–28) measured a **data-aided fit** approach — position, linear frequency
drift, and time-varying complex-amplitude envelope fit directly against real off-air audio — on a
real 40 m corpus, using decode-rate corroboration against WSJT-X rather than a synthetic-S7 trial
count. Result: net +8.89 percentage points [95% CI 8.01, 9.75] WSJT-X-corroborated new decodes,
after a replay-vs-live control. The Captain reviewed this result and explicitly authorised a scoped,
flag-gated native build on 2026-09-28. This satisfaction applies **only** to the exact method
measured (data-aided fit + `W*=0.32s` time-varying envelope, per `design.md`'s Decision 1) — a
future, materially different subtraction method SHALL require its own PoC gate, not inherit this
one.

This requirement continues to exist to prevent a repeat of the `fix-d001-pcm-sic` pattern, in which
production-quality three-platform infrastructure was built before the core hypothesis was validated.

#### Scenario: PoC gate blocks production implementation

- **WHEN** a signal-subtraction PoC is completed
- **AND** its measured improvement does not meet a pre-registered bar reviewed by the Captain
- **THEN** production implementation SHALL NOT proceed; the Captain is informed and the option is
  either revised or closed

#### Scenario: Captain approval gate is recorded before implementation

- **WHEN** a signal-subtraction PoC meets its pre-registered bar
- **THEN** the Captain SHALL review the PoC results and provide explicit approval before any
  production changes to `ft8_shim.c` (or an equivalent native module) are authored

#### Scenario: SUB-FEAS satisfies this gate for the data-aided-fit method only

- **WHEN** the `sub-feas-native-subtraction` change implements the data-aided fit + `W*=0.32s`
  envelope method
- **THEN** this requirement is satisfied by the Captain's 2026-09-28 authorisation of
  `qa/rr-study/2026-09-28-1025-…-stage2-diagnostic-results.md` and
  `qa/rr-study/2026-09-28-1601-…-build-authorised.md`, and no further synthetic-S7 PoC is required
  for this specific method

#### Scenario: A future, different subtraction method requires its own gate

- **WHEN** a proposal considers a subtraction method materially different from the data-aided fit
  method this change implements (e.g. a different residual model, joint multi-signal fitting)
- **THEN** that proposal SHALL run its own PoC and obtain its own Captain approval; it MAY NOT cite
  this requirement's SUB-FEAS satisfaction as already covering it

### Requirement: Any PCM residual buffer SHALL use heap allocation, not stack allocation

Any buffer used by a signal-subtraction decode path SHALL be allocated via `malloc`/an explicit heap-backed pool and freed before the owning call returns — this covers the PCM residual buffer (`FT8_EXPECTED_SAMPLES * sizeof(float)`, 720,000 bytes), per-signal complex templates (one per subtracted signal, ~151,680 samples × 16 bytes ≈ 2.4 MB each), FFT working buffers (sized to the fit's `n_fft`), and time-varying envelope arrays alike.

Stack allocation of any such buffer, or of any buffer exceeding 100 KB, in a function called via P/Invoke from a .NET thread pool thread is prohibited, as the combined managed + native stack frame approaches the 1 MB thread pool thread stack limit. A prior fix that moved only the PCM residual buffer from stack to heap did not prevent a second, independent crash — this requirement therefore extends to every buffer class the subtraction path introduces, not only the one implicated in the first crash.

#### Scenario: PCM residual is heap-allocated

- **WHEN** `ft8_decode_all` (or its subtraction-enabled equivalent) is compiled with the
  subtraction path enabled
- **THEN** the residual buffer SHALL be allocated with `malloc(FT8_EXPECTED_SAMPLES * sizeof(float))`
  and freed before the function returns, with no automatic (stack) array of that size declared

#### Scenario: Per-signal template and envelope buffers are heap-allocated

- **WHEN** the subtraction path fits and subtracts any decoded signal
- **THEN** that signal's complex template, FFT working buffers, and envelope array SHALL each be
  heap-allocated (or drawn from an explicitly heap-backed pool) and released before the cycle's
  decode call returns, with no automatic (stack) array used for any of them

#### Scenario: Concurrently-allocated per-signal buffers are bounded

- **WHEN** a cycle contains more decoded signals than the subtraction path's configured concurrent
  buffer cap
- **THEN** the implementation SHALL process signals within that bound (sequentially reusing pooled
  buffers, or an equivalent bounded strategy) rather than allocating one buffer set per signal with
  no upper bound

#### Scenario: Allocation failure is handled gracefully

- **WHEN** a heap allocation for any subtraction-path buffer fails
- **THEN** the decode call SHALL fall back to the single-pass (no subtraction) result for that
  cycle, log the allocation failure, and return whatever results pass 0 produced, without crashing

## ADDED Requirements

### Requirement: Data-aided fit and time-varying envelope subtraction, as an additive residual-decode pass

The system SHALL, only when the subtraction feature flag is enabled and after the existing decode pipeline completes a cycle's decode ("pass 0", unmodified): fit each pass-0 decoded message that re-encodes to a valid FT8 payload — position, linear frequency drift, and a time-varying complex amplitude envelope — against the **original** recorded audio for that cycle; subtract every such fit from one copy of the original audio; and run the existing decode pipeline a second time, unmodified, on that residual. This is exactly one additional decode pass — not an iterative or multi-pass loop, and not a change to the existing `K_MAX_PASSES` mechanism (see the separate requirement on their distinctness, below).

The fit SHALL use the following parameters, inherited from the validated `SUB-FEAS` measurement and
not independently re-derived by this change:
- Nominal fit position: the decoded DT plus a fixed offset `τ0 = −0.1600 s`.
- Position search: ±100 ms around the nominal position, at 1 ms (integer-sample) resolution.
- Frequency drift search: linear rate `ḟ ∈ [−0.10, +0.10] Hz/s`, at `0.005 Hz/s` steps.
- Residual frequency search: ±2 Hz around the decoded frequency.
- Envelope: a Hann-windowed moving-average complex gain, window width `W* = 0.32 s`. A window width
  at or beyond the full transmission length (12.64 s) SHALL still be computed correctly as its own
  degenerate case (one complex scalar for the whole transmission) — the implementation SHALL NOT
  special-case away the general windowed computation in a way that only ever produces that
  degenerate result.

All fits for a given cycle SHALL be computed against the original (pre-subtraction) audio — no
signal's fit SHALL depend on another signal already having been subtracted from the buffer used for
fitting.

#### Scenario: Flag OFF leaves decode output unchanged

- **WHEN** the subtraction feature flag is disabled (the default)
- **THEN** decode output for a cycle SHALL be byte-identical to the pre-change (pass-0-only) behaviour

#### Scenario: Flag ON produces at most one additional decode pass

- **WHEN** the subtraction feature flag is enabled and pass 0 decodes at least one re-encodable
  message
- **THEN** the system SHALL fit and subtract every such message once, run exactly one residual decode
  pass, and SHALL NOT repeat subtraction or fitting against the residual itself

#### Scenario: A residual-pass decode is reported only if its payload is genuinely new

- **WHEN** the residual decode pass produces a message
- **THEN** the system SHALL compare its payload (bit-level), not its rendered text, against every
  pass-0 decode for that cycle, correctly accounting for the RR73 on-air-sentinel vs
  re-encoded-text-sentinel asymmetry, and SHALL report it as new only if no pass-0 payload matches

#### Scenario: All fits use the original audio, not a partially-subtracted buffer

- **WHEN** a cycle has more than one re-encodable pass-0 decode
- **THEN** each signal's fit SHALL be computed against the original recorded audio for that cycle,
  and all fitted subtractions SHALL be applied to one shared copy of that original audio, not applied
  incrementally with each subsequent fit computed against an already-modified buffer

### Requirement: The residual-decode pass is distinct from `K_MAX_PASSES` and SHALL NOT be implemented as a `K_MAX_PASSES` change

The residual-decode pass SHALL NOT be implemented by incrementing `K_MAX_PASSES`, and `K_MAX_PASSES` SHALL remain 2 regardless of whether the subtraction feature flag is enabled — it is a separate mechanism from `K_MAX_PASSES` (the existing spectrogram-domain soft-SNR candidate-search pass count, currently 2, specified by this capability's "Two-pass decode structure" requirement); the residual-decode pass instead runs the **entire** existing `K_MAX_PASSES`-governed decode pipeline a second time, over different audio (a subtraction residual).

#### Scenario: `K_MAX_PASSES` is unchanged by this capability

- **WHEN** the subtraction feature flag is enabled or disabled
- **THEN** `ft8_get_max_passes()` SHALL continue to return 2, and the existing two-pass
  spectrogram-domain candidate search SHALL be unaffected

#### Scenario: The residual-decode pass is separately identifiable in logs

- **WHEN** the subtraction feature flag is enabled and a residual decode pass runs
- **THEN** the system SHALL log it distinctly from the existing per-`K_MAX_PASSES`-pass log lines,
  so an operator or a future diagnostic cannot mistake one mechanism for the other

### Requirement: Subtraction feature flag, default OFF

A configuration field SHALL gate the residual-decode pass, defaulting to disabled. The field SHALL
follow the existing decoder-settings configuration surface's established convention rather than
introducing a new configuration subsystem.

#### Scenario: Feature is disabled by default on a fresh configuration

- **WHEN** the daemon starts with no prior configuration for this field
- **THEN** the subtraction feature flag SHALL read as disabled and the residual-decode pass SHALL NOT run

#### Scenario: Feature can be enabled without a rebuild

- **WHEN** an operator (or a test harness) sets the configuration field to enabled
- **THEN** the residual-decode pass SHALL run on the next decode cycle without requiring a new build

### Requirement: The residual-decode pass SHALL NOT crash the process under sustained operation

The residual-decode pass, when enabled, SHALL run for a sustained, multi-hour period without crashing the host process, independent of whether it produces any accuracy improvement — given this capability's history of two independent production crashes from an earlier subtraction attempt, the second of which survived the first crash's own fix.

#### Scenario: Sustained operation does not crash

- **WHEN** the subtraction feature flag is enabled for a multi-hour, multi-cycle run against varied
  real or replayed audio (silence, single-signal, and dense multi-signal cycles included)
- **THEN** the process SHALL NOT crash, and memory usage attributable to the subtraction path SHALL
  NOT grow unbounded over the run

### Requirement: Live-use readiness — second-corpus and runtime acceptance required before any live A/B

The implementation SHALL be validated against two gates before the subtraction feature flag may be enabled in any live (non-offline, non-replay) endurance or production run: (a) a measured decode-cycle runtime, with the flag enabled, against the existing 13-second hard / 30-second CI decode-cycle budget; and (b) a decode-rate acceptance result on a corpus independent of the one `SUB-FEAS` used, reproducing a net improvement (over a no-subtraction control, same methodology as `SUB-FEAS` Stage 2's replay-vs-live control) of at least the WIN bar `SUB-FEAS` itself used (≥ 1.0 percentage point, 95% CI lower bound). Both are gates on live use, not on this change's own merge — per the Captain's 2026-09-28 decision, the native build may land and be measured before these are read, but the flag SHALL remain OFF in any live run until they are.

#### Scenario: Runtime gate blocks live use, not the build itself

- **WHEN** the native subtraction build exists but its measured decode-cycle runtime (flag enabled)
  has not yet been checked against the 13 s / 30 s budget
- **THEN** the build MAY merge with the flag OFF by default, but the flag SHALL NOT be enabled in any
  live endurance or production run until the runtime measurement is taken and reported

#### Scenario: Second-corpus gate blocks live use, not the build itself

- **WHEN** the native subtraction build exists but has not yet been validated on a corpus independent
  of `SUB-FEAS`'s own
- **THEN** the flag SHALL NOT be enabled in any live endurance or production run until that
  second-corpus acceptance result is taken and reported, regardless of the original `SUB-FEAS` result's
  strength
