## ADDED Requirements

### Requirement: The Stage A fit optimisations SHALL leave the fit's output bit-identical

The native fit SHALL produce, for any input **with no deadline set**, exactly the same return code and exactly the
same bytes in `out_shat` after every Stage A change (`ft8_subfeas_fit_signal`: the hoisted tone smoothing, the cached
pulse and window spectra, the reused workspace and FFT plans, the thread count) as the pre-change build (shim
`20260055`, `libft8.dll` SHA-256 `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`). "Same" means a
byte-for-byte comparison of the output buffer, not a tolerance. Exactness SHALL be demonstrated on real cycles by a
hash comparison against that DLL (acceptance row E1), not argued from the code. If any signal differs, Stage A is
not exact and the optimisation that caused it SHALL be reverted or reclassified as Stage B.

#### Scenario: Identical output on identical input

- **WHEN** the same pass-0 signal (tones, DT, frequency) and the same analytic buffer are fitted by the pre-change
  DLL and by the candidate DLL, with no deadline
- **THEN** the return codes are equal
- **AND** the SHA-256 of `out_shat` is equal

#### Scenario: Result does not depend on the number of worker threads

- **WHEN** the same set of signals is fitted with one worker and with the default worker count
- **THEN** every signal's `out_shat` hash is equal across the two runs, and the summed residual buffer is equal

#### Scenario: Flag OFF is untouched

- **WHEN** `decoder.subtractionEnabled` is `false`
- **THEN** decode outcome fields are identical to the pre-change build on the same cycles (the existing flag-OFF
  byte-identity requirement continues to apply and is re-verified on the new native build)

### Requirement: The residual pass SHALL be bounded by a hard wall-clock deadline

The native fit SHALL accept a cancellation flag (an integer in memory owned by the managed caller) and SHALL check
it at every Δt-search, ḟ-search and envelope iteration. When the flag is non-zero the fit SHALL stop, leave `out_shat`
zeroed, and return the new code `-4` ("cancelled by deadline"). The managed caller SHALL set the flag at
`budget − reserve`, where the reserve is a named constant of 1 500 ms covering the residual decode, and SHALL NOT
start the residual decode when less than the reserve remains. A deadline SHALL abandon the residual pass exactly as
today (the cycle keeps its pass-0 results, no residual decodes are added) and SHALL be reported through the existing
`deadlineAbandoned` field of the `Sub-feas residual pass:` log line. `-4` SHALL be handled as a deadline outcome and
SHALL NOT be raised as an exception or counted as a contained exception. The whole-call elapsed time of a
flag-ON decode, including pass-0, SHALL NOT exceed the cycle budget of 13 s on the acceptance machine (rows R1′, R6).

#### Scenario: Flag already set when the fit starts

- **WHEN** the cancellation flag is non-zero on entry
- **THEN** the fit returns `-4` promptly, before doing an FFT-scale amount of work, with `out_shat` zeroed

#### Scenario: Flag set while a fit is running

- **WHEN** the flag is set from another thread part-way through a fit
- **THEN** the fit returns `-4` within one search iteration
- **AND** no memory is leaked and no other in-flight fit is disturbed

#### Scenario: Deadline reached

- **WHEN** the deadline fires during the per-signal fits
- **THEN** the residual pass is abandoned, the cycle returns its pass-0 results, `deadlineAbandoned` is `true` and
  `containedException` is `false`

#### Scenario: Not enough time left for the residual decode

- **WHEN** the fits finish with less than the reserve remaining
- **THEN** the residual decode is not started and the pass is abandoned as a deadline outcome

#### Scenario: No deadline set

- **WHEN** no cancellation flag is ever set
- **THEN** behaviour and output are those of the bit-identical requirement above

### Requirement: Fit workspaces and FFT plans SHALL be reused, bounded, heap-only and released

The fit SHALL NOT allocate a workspace or an FFT plan per signal. A workspace and plan set SHALL be reused across
signals and across cycles, with the number of live workspaces bounded by the configured thread count. Every workspace
SHALL be heap-allocated (the existing requirement "Any PCM residual buffer SHALL use heap allocation, not stack
allocation" and the crash history behind it apply unchanged) and SHALL be released by an explicit shutdown path, not
left to process exit. Concurrent fits SHALL NOT share a mutable workspace. The workspaces SHALL be a bounded,
locked pool whose size equals the effective fit thread count, each workspace leased for one fit call and returned
in a `finally` so a failed or cancelled fit cannot leak its lease; there SHALL be no native thread-local workspace
state, because the fits run on thread-pool threads the native code does not own (`design.md` D2). The pool SHALL be
freed when the decoder is disposed. Resident memory of about 25–30 MB per worker is expected and accepted.

#### Scenario: A failed fit returns its workspace

- **WHEN** a fit is cancelled, fails, or throws
- **THEN** its workspace is returned to the pool and the next fit can lease it

#### Scenario: No growth over many cycles

- **WHEN** a long run of cycles is decoded with the flag ON after warm-up
- **THEN** process private memory attributable to the fit reaches a plateau bounded by the worker count times the
  per-workspace size, and does not grow with the number of cycles or signals

#### Scenario: Concurrent fits do not interfere

- **WHEN** the maximum number of workers fit different signals at the same time
- **THEN** each signal's output equals its output when fitted alone

#### Scenario: Shutdown releases the workspaces

- **WHEN** the decoder is shut down
- **THEN** every workspace and plan set is freed, and a later decode after re-initialisation still works

#### Scenario: Allocation failure

- **WHEN** a workspace cannot be allocated
- **THEN** the fit fails safely into the existing pass-0-only fallback and does not crash (the existing allocation
  failure behaviour is preserved)

### Requirement: The fit thread count SHALL be configurable

The number of concurrent fit workers SHALL come from the optional config key `decoder.subtractionMaxThreads`. When
absent, and when it is `0`, the effective value SHALL be `max(1, ProcessorCount − 2)` ("auto"; `0` is also the
default, so a config reset degrades the key to auto and never to a wrong value). Any other configured value SHALL be
clamped to `[1, ProcessorCount]` (a negative value therefore becomes 1). The value SHALL take effect on the next decode cycle without a rebuild, like the flag. The
setting has no settings-page control.

#### Scenario: Default on a 16-thread machine

- **WHEN** the key is absent on a machine with 16 logical processors
- **THEN** 14 workers are used

#### Scenario: Default on a small machine

- **WHEN** the key is absent on a machine with 2 or fewer logical processors
- **THEN** 1 worker is used

#### Scenario: Out-of-range value

- **WHEN** the key is negative or larger than the processor count
- **THEN** the effective value is clamped into `[1, ProcessorCount]`

#### Scenario: Zero means auto

- **WHEN** the key is `0`
- **THEN** the effective value equals the default (`max(1, ProcessorCount − 2)`)

#### Scenario: Change without rebuild

- **WHEN** the key is changed between two cycles
- **THEN** the second cycle uses the new value

### Requirement: The residual decode SHALL NOT compute diagnostics nothing reads

The residual-pass `DecodeAll` SHALL run with its pass-0 diagnostics disabled: nothing reads the thread-local
diagnostic state after that call, so computing it is pure cost. Disabling diagnostics SHALL NOT change any decode
output field. The global noise-floor computation SHALL be retained because it feeds a decode output (the local-noise
SNR fallback). The Debug-only per-pass log loops SHALL be guarded so that no formatting or loop work is done unless
Debug logging is enabled. The `Sub-feas residual pass:` log line, SEH containment and input validation are not
redundant and SHALL be retained. The LDPC-fail LLR statistics (`failCands`, `meanAbsLLR`, `prenormVar`) SHALL be
retained until every QA script that parses them has been retired or migrated; they are not in scope of this change.

#### Scenario: Outputs unchanged with diagnostics off

- **WHEN** the residual decode runs with diagnostics off on real cycles
- **THEN** every decode outcome field of the residual decode equals its value with diagnostics on

#### Scenario: Debug logging disabled

- **WHEN** the logger reports Debug disabled
- **THEN** the per-pass Debug log loops do no formatting and make no logger call

#### Scenario: Noise floor retained

- **WHEN** a decode uses the local-noise SNR fallback
- **THEN** the SNR value is unchanged from the pre-change build

### Requirement: Runtime acceptance of the redesign SHALL be measured on the frozen §8.1 instrument

The speed claim SHALL be tested with the §8.1 replay harness and frozen selection (`selection.json` SHA-256
`730d6ea61f25ba8cad90520a17266b3efe0e1e476b1bd1ce29d1a6cbcc3b1f15`, harness `cd36bb42`, updated only for the new
config key, with its SHA stated), with the acceptance rows pre-registered in
`qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §2 (E1, R0, R1′, R2′, R3, R4′, R5′, R6,
R7, and the report-only thread row T). The run SHALL be made with WSJT-X closed and the machine state recorded. The
report SHALL pin every DLL used by SHA-256 (actual and pinned), quote any filter, state the blind spot, and make no
decode-rate claim. Exactness (E1) SHALL be read first; if it fails, no timing row is read.
Stage A passes iff E1, R0, R1′, R2′, R3, R4′, R5′ and R6 all pass. The timing rows decide whether Stage B is built and
gate any live use; they do not gate the merge of the exact, flag-OFF-default change, which is gated by E1, the
flag-OFF control re-run, and the stability requirements.

#### Scenario: Exactness fails

- **WHEN** E1 shows any differing fit hash or return code
- **THEN** acceptance stops, no timing row is read, and the differing optimisation is reverted or moved to Stage B

#### Scenario: Stage A misses the speed bars

- **WHEN** Stage A passes E1 but fails R2′ or R4′
- **THEN** Stage B is considered item by item under its own gate (equivalence within tolerance and no loss of
  residual decodes), never accepted on speed alone

#### Scenario: Flag-OFF control before merge

- **WHEN** the change is proposed for merge
- **THEN** the flag-OFF control (the same predicate as the base change's ruling 2) has been re-run on the new native
  build and passes, because the native decode path was touched

### Requirement: Any Stage B change SHALL use only a permissively licensed FFT and SHALL be accepted on equivalence

If Stage B is built, a replacement FFT SHALL be MIT, BSD or ISC licensed (for example pocketfft-C, BSD-3); FFTW and any
other GPL code are prohibited (repository licence policy). A numerics-changing item SHALL be accepted only on
equivalence within tolerance to the Stage A fit and on no loss of residual decodes, not on speed.

#### Scenario: Equivalence is the acceptance criterion

- **WHEN** a Stage B item makes the fit faster but changes fitted parameters beyond the pre-registered tolerance
- **THEN** it is rejected regardless of the speed gained

#### Scenario: Prohibited licence

- **WHEN** a proposed FFT dependency is GPL
- **THEN** it SHALL NOT be added
