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
- **AND** exactly one warning is logged when the config is applied, following the existing clamp-with-warning pattern
  of `POST /api/v1/config`, and none is logged per decode cycle

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

### Requirement: With the flag ON the daemon SHALL publish the pass-0 decodes first and the residual decodes as a second batch of the same cycle

When `decoder.subtractionEnabled` is true, the decoder SHALL make the pass-0 decodes available for publication as
**batch 1** as soon as pass 0 has returned and been mapped, and SHALL start the residual pass only after batch 1 has been
handed to the pump's publish path. Residual decodes SHALL be published as **batch 2** of the same cycle (the same
`cycleStart`) when the pass completes. Nothing SHALL be published as batch 2 when the pass is abandoned or yields no new
decode. The reason is operational, not a speed target: the residual pass ran inside the single decode call, before the
one publish, so every decode reached the operator only after the whole pass (about 20.5 s median after the cycle starts,
against a 17.36 s deadline to answer a station heard in that cycle). The `IModeDecoder.DecodeAsync` contract used by other
callers SHALL be unchanged.

#### Scenario: Batch 1 does not wait for the residual pass

- **WHEN** the flag is ON and pass 0 returns
- **THEN** batch 1 is published through the pump's existing path before the residual pass begins

#### Scenario: Batch 2 follows

- **WHEN** the residual pass completes with at least one new decode
- **THEN** those decodes are published as batch 2 with the same `cycleStart` as batch 1

#### Scenario: Nothing is published for an abandoned or empty residual pass

- **WHEN** the residual pass is abandoned on the deadline, fails, or yields no new decode
- **THEN** no second batch is published and batch 1 stands as the cycle's output

### Requirement: Batch 2 SHALL use the same mapping and the same de-duplication as batch 1

Batch 2 SHALL be mapped exactly as batch 1 is (trailing-space trim, plausibility filter, region lookup, worked-before,
band). Text de-duplication SHALL span both batches: the set of message texts already published in the cycle is per cycle,
not per batch, so a residual decode whose text equals a pass-0 text is not published again. The residual pass's payload
de-duplication is unchanged.

#### Scenario: A repeated text is published once

- **WHEN** a residual decode has the same message text as a pass-0 decode of the same cycle
- **THEN** it is not published in batch 2

### Requirement: Batch 2 SHALL reach the panel, ALL.TXT, filter admission and external reporting, and SHALL NOT reach the QSO answerer or caller

Batch 2 SHALL be delivered to the decode panel (appended, never replacing batch 1's rows), to ALL.TXT (appended after
batch 1's lines with the same cycle stamp), to the decode-filter new-value admission, and to the external-reporting
channel. Batch 2 SHALL NOT be delivered to the QSO answerer or QSO caller channels in this change: the answerer keeps its
last idle decode batch as the snapshot that validates an external reply, and a residual-only second batch for the same
cycle would replace the pass-0 snapshot, so an external reply to a pass-0 station would then be rejected; the answerer and
caller also treat every batch they receive as a cycle. The cycle-audio archive SHALL be enqueued once per cycle, at batch 1,
with the pass-0 count. Consequence to be stated to the operator: residual decodes are visible, logged and spotted, but a
residual decode is **not** available to the answerer or caller as an engagement or response-detection input.

#### Scenario: The answerer and caller see one batch per cycle

- **WHEN** the flag is ON and a cycle produces batch 1 and batch 2
- **THEN** the answerer and the caller each receive exactly one batch for that cycle, equal to batch 1

#### Scenario: The answerer's idle snapshot is batch 1

- **WHEN** a flag-ON cycle has completed both batches
- **THEN** the answerer's last idle decode batch equals batch 1

#### Scenario: ALL.TXT holds both batches in order

- **WHEN** a flag-ON cycle produces both batches
- **THEN** ALL.TXT holds batch 1's lines then batch 2's, with the same cycle stamp and no duplicate text within the cycle

#### Scenario: The panel shows the union

- **WHEN** a flag-ON cycle produces both batches
- **THEN** the panel receives two `decode` events and shows the rows of both, batch 2 never replacing batch 1

#### Scenario: The archive is enqueued once

- **WHEN** a flag-ON cycle produces both batches
- **THEN** the cycle-audio archive is enqueued once, at batch 1

### Requirement: The decode pump SHALL stay serial and the flag-OFF path SHALL be one batch and byte-identical

The decode pump SHALL NOT start decoding the next capture window until batch 2 of the current cycle has been published or
the residual pass has been abandoned. The per-cycle `Cycle {Time}: … elapsed=` line SHALL report the time to batch 1 (for
flag OFF, identical to today, so the existing latency series stays continuous); the residual pass's own time stays in the
`Sub-feas residual pass:` line. With the flag OFF there SHALL be exactly one batch per cycle and the published output,
ALL.TXT lines, archive enqueue and consumer deliveries SHALL be byte-identical to the pre-change build.

#### Scenario: Flag OFF publishes once

- **WHEN** the flag is OFF
- **THEN** each cycle produces exactly one publish, identical to the pre-change build

#### Scenario: The next window waits

- **WHEN** batch 2 of a cycle is still being computed
- **THEN** the pump does not begin the next window's decode until batch 2 is published or the pass is abandoned

### Requirement: The two-stage split SHALL change timing only, and batch 1 SHALL cost what flag OFF costs

Acceptance SHALL show, mechanically, that the split changes when decodes are published and not which decodes are
published (row S1: on the 161 E1 cycles the union of the two batches equals the single-batch output of build `ca0bcd9b`,
and batch 1 equals the flag-OFF output, compared as outcome fields, never rendered text), that nothing new sits before the
first publish (row S2: time to batch 1 within 1.05 × the flag-OFF whole-call median per run, and a bounded maximum), and
that the consumer behaviour above holds (row S3, tests in code). Two-stage publish SHALL be complete and accepted before
any live use with the flag ON; live use itself remains a separate explicit decision of the Captain, and the flag stays OFF
by default.

#### Scenario: The split loses no decode

- **WHEN** a cycle is decoded through the two-stage path and through the single-batch path of `ca0bcd9b`
- **THEN** the union of batch 1 and batch 2 outcome fields equals the single-batch output, as a set

#### Scenario: Batch 1 equals flag OFF

- **WHEN** a cycle is decoded through the two-stage path
- **THEN** batch 1 equals the flag-OFF output of the same build

### Requirement: Stage B SHALL be built one item at a time, accepted on equivalence first, and stopped at a finish line fixed in advance

Stage B (a faster permissively licensed FFT, a pruned frequency search, a coarse-to-fine time search) SHALL be built only
after the two-stage publish work, on its own branch and commits and never mixed into it, and SHALL start with a measured
profile of the candidate DLL at 1, 4 and 14 concurrent workers. Items SHALL be built one at a time, each accepted on
equivalence within tolerance to the Stage A fit and on no loss of residual decodes (never on speed) and only then re-timed.
The finish line, fixed before any Stage B build, SHALL be: with `decoder.subtractionMaxThreads` = 4, over the heavy stratum,
the deadline-abandon rate at most 5 % and the maximum whole call at most 13 000 ms. Stage B SHALL stop at the first item
after which that holds, or after the third item, or when the Captain says so, and if the finish line is still not met SHALL
report the residual gap. Because a numerics-changing item breaks bit-identity, each item's DLL SHALL be pinned by SHA-256 and
the flag-OFF control SHALL be re-run on the final native DLL, native and managed paths.

#### Scenario: An equivalent-but-slow or fast-but-inequivalent item

- **WHEN** a Stage B item is faster but misses the equivalence or the residual-decode criterion
- **THEN** it is rejected regardless of the speed gained

#### Scenario: Stop at the finish line

- **WHEN** an accepted item brings the 4-worker heavy-stratum abandon rate to at most 5 % with the maximum whole call at most 13 000 ms
- **THEN** no further Stage B item is built unless the Captain asks

#### Scenario: Finish line not met after the last item

- **WHEN** the third item has been accepted and the finish line is still not met
- **THEN** the residual gap is reported and the change stops

