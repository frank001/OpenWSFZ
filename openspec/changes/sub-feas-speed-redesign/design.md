## Context

`2b39cf18` fits each pass-0 signal with `fine_fit_with_drift` (`native/ft8_lib_vendor/subfeas/subfeas_fit.c`), about
377 complex FFTs of N = 262 144 per signal plus about 12 M sin/cos pairs, times about 23 signals on a busy cycle, on
at most 4 threads, with a deadline that is only observed between native phases. The measured consequence is in
`proposal.md`. The cost map is the Architect's static reading (`qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md`
§0); **the build logs no per-phase time, so nothing below is a measured breakdown.** The first Developer task
(tasks §2) adds the measurement that makes the breakdown checkable.

## Decisions

### D1. Stage A is exact-only; exactness is proven by a hash, not by reasoning

A1 (hoist the tone smoothing), A2 (cache the pulse and window spectra) and A3 (reuse workspace and plans) do the same
arithmetic in the same order on the same values, only less often. A4 changes how many signals run at once, not what
one signal computes. **This is a claim, and floating-point code breaks such claims quietly** (a stored value at a
different precision, a reordered sum, a fused multiply-add the old code did not have). So acceptance row E1 compares
`sha256(out_shat)` and the return code per (cycle, signal) against the `2b39cf18` DLL on real cycles. Build flags
SHALL NOT change in Stage A (no `/fp:fast`, no `/arch:AVX2`): a flag change is a Stage B item.

The one hazard worth naming for A1: `instantaneous_phase` adds the drift term **after** the convolution. The hoisted
smoothed track must be held at the precision the old code held it at when it added the drift term. If the old code
kept it in a `double` array, keep a `double` array. If E1 fails, the first suspect is here.

Alternatives considered: accept "equal within 1 ulp" (rejected: it makes E1 a tolerance test and Stage A could then
drift silently; Stage B exists for that); vectorise the sin/cos loops (rejected for Stage A: changes rounding).

### D2. Workspace ownership: a bounded, locked pool of heap workspaces (FIXED by the Architect's Amendment 1)

The trap A3 has to avoid: C# fits run on **thread-pool threads that the native code does not own**. Thread-local
storage in C has no destructor here, so per-thread workspaces would leak when the pool retires a thread and cannot
be freed at shutdown from another thread. **Decided** (QA recommended it, the Architect adopted it in
`qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §5a): a **bounded, locked pool** of heap
workspaces, size = `subtractionMaxThreads` (the effective value), each workspace **leased per fit call and returned in
a `finally`**, freed when the decoder is disposed. **No native thread-local state.**

Constraints the Developer implements and QA reviews: heap only; no two concurrent fits share a workspace; a fit that
is cancelled, fails or throws still returns its lease; freeing is impossible while a lease is out (dispose waits for
in-flight fits or refuses); a lease request when the pool is empty must not allocate beyond the bound (with
`MaxDegreeOfParallelism` equal to the pool size it should never block; assert that rather than assume it). A changed
`subtractionMaxThreads` takes effect at the next cycle boundary, with nothing in flight, and resizes the pool then.
This is where the base change's two `0xC0000005` crashes lived, so this is the review focus.

### D3. The cancellation flag: shape, memory model, lifetime

- **Shape:** one extra `const volatile int* cancel_flag` parameter on `ft8_subfeas_fit_signal` (NULL means "no
  deadline", which keeps the no-deadline path identical). New return code `-4`. The Architect's spec names the
  exact mechanism (`int*` that C# sets, checked per Δt/ḟ iteration); the exact ABI signature is a Developer decision
  recorded here.
- **Checked at:** the top of each of the 201 Δt candidates, each of the 41 ḟ candidates and the envelope loop, and at
  entry. The longest uninterruptible stretch is then one candidate (a small number of FFTs, tens of milliseconds
  expected; **unmeasured**, tasks §2 measures it), which is why the 1 500 ms reserve is comfortable for the fit and the
  reserve exists for the residual decode.
- **Memory model:** the native side reads through a `volatile` (or an atomic relaxed load); the managed side writes
  with `Volatile.Write` / `Interlocked`. No lock. A stale read costs at most one more iteration.
- **Lifetime:** the flag's memory must outlive every in-flight native call. The managed side owns it (unmanaged
  allocation or a pinned handle) for the whole of `RunCoreUnguarded` and frees it only after `Parallel.For` has
  returned, which it already waits for.
- **Not covered by the flag:** `ft8_subfeas_compute_analytic` (one call per cycle) and the residual `DecodeAll`. The
  reserve covers the decode; the analytic call's cost is small but **unmeasured**, so tasks §2 measures it too.

### D4. Return code `-4` is a deadline outcome, not an error

The managed interop currently throws on any return code other than 0 and -3 (see `SubtractionPass.cs`:
"defensive; interop already throws on other codes"). `-4` must be mapped to a value `SubtractionPass` treats as
"deadline abandon", not raised as an exception, or every deadline would be recorded as `containedException=true`
and the R3 and R4′ rows would read the wrong thing. This is a small change with a test (tasks §7).

### D5. The reserve and the budget arithmetic

Budget 13 000 ms is for the whole call. Pass-0 takes about 0.5 s (flag-OFF medians 473–528 ms, max 830 ms). The residual
pass receives `13 000 − pass0`, sets the flag at `that − reserve` (reserve `SubtractionResidualDecodeReserve` =
1 500 ms, a named constant, not a literal), and skips the residual decode if less than the reserve remains. QA's
first draft used 1 000 ms, which left **170 ms** over the largest observed flag-OFF whole call (830 ms, a single
outlier) before the merge/dedup step. The Architect raised it to **1 500 ms** (Amendment 1), a design parameter fixed
before any build; the margin is now **670 ms** over that outlier. R1′'s bar is unchanged at 13 000 ms and remains a
fairly tight bar. The larger reserve costs about 0.5 s of fit time on cycles that hit the deadline; if R4′ misses
narrowly, that is the price to read it against. M2 should make the residual decode cheaper, which helps.

### D6. Thread count

`decoder.subtractionMaxThreads`: **`0` = auto = `max(1, ProcessorCount − 2)`, and `0` is the default** (Architect,
Amendment 1); any other value is clamped `[1, ProcessorCount]` (negative becomes 1, confirmed by the Architect; one
warning log when the config is applied, never per cycle, see Open Questions). Read per cycle like `decoder.subtractionEnabled`. Two threads are left for
capture, the web UI and any co-resident WSJT-X. **Memory:** about 25–30 MB per worker resident (about 0.4 GB at 14
workers); accepted by the Architect's default, changeable by the Captain. **Why `0 = auto`:** the config-save defect
(#193) resets any setting the Settings page does not send. The page sends neither `subtractionEnabled` nor
`subtractionMaxThreads`, so until the Engineer's fix lands a Settings save resets both: the flag to OFF (fail safe)
and this key to 0 = auto (a sensible value, not a wrong one). The Engineer owns that fix and has been told of both keys.
The Developer still confirms a settings-page save after the fix lands.

### D7. M1 is deferred: the consumer precondition fired

The Architect's spec: "if anything in `qa/` or `tools/` reads `prenormVar`/`meanAbsLLR`/`failCands`, STOP and ask
the Captain." QA's grep on 2026-09-30 found four scripts that regex-parse the Debug line
`Iterative subtraction: pass N LDPC fail stats — failCands=… meanAbsLLR=… prenormVar=…` (paths in `proposal.md`),
plus historical dev-task and report prose that only *describes* it. `tools/` and the RUNBOOK have no consumer. The
line is Debug-only and the code's own comment says the hypothesis it served was refuted, so it costs nothing when
Debug is off **if** the computation is also skipped; today the computation runs regardless (`ft8_shim.c:1631-1636`).
The Captain chose to **defer** M1 (asked 2026-09-30). Recorded so that:
- the R5′ row is measured with M1 absent and M2 and M3 alone are credited or not with what they do;
- if M1 is revisited, the surface is: `ft8_shim.c/.h` (TLS, getter, computation), `native/ft8_lib_build/patched/ft8/decode.c`
  (`ftx_compute_candidate_llr_stats`), `rebuild_shim.bat`, `rebuild_shim_new.bat`, `rebuild_diag.bat`, `build_linux.sh`
  exports, `Ft8LibInterop.cs`, `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`, the specs
  `ft8lib-interop` and `native-build-provenance` (which name `ft8_get_last_llr_stats`), and the **twelve test fakes** (which A5 touches anyway, so M1's marginal test cost is small)
  (`GetLastLlrStats` in `CoherentLlrAtTests`, `AvContainmentTests`, `D011…`, `D005…`, `D009…`, `GetLastSnrTerms…`,
  `H12Instrumentation…`, `HashTableRejectCountLogging…`, `RefineCandidate…`, `RegionLookup…`, `SetDecodeParams…`,
  `WorkedBeforeLookup…`).

An intermediate option was offered and not chosen: keep the statistics but compute them only when Debug is enabled.

### D8. What acceptance can and cannot show

E1 shows the fit is unchanged. R0 shows the replay is the live path. R1′/R2′/R4′/R6 show speed and the deadline on
one machine. **Nothing here measures decode rate** (Stage A is bit-identical, so it cannot move it), and nothing
covers other hardware. R5′ compares the new build's flag-OFF cost with the old build's. **Accepted by the Architect
(Amendment 1):** the baseline is the `2b39cf18` DLL **re-measured in the same acceptance session** on the same
cycles, not the §8.1 medians, because the §8.1 medians were taken with WSJT-X and a browser resident and the
acceptance run is made with WSJT-X closed, which would flatter the candidate. **P4 is scored on M2 + M3 alone; nothing
in R5′ may be credited to M1** (deferred). E1's selection is likewise fixed: pooled `(run, stamp)` pairs sorted by
`(run, stamp)`, indices 0, 9, 18, …, plus the 60 pilot cycles.

### D9. Two-stage publish (Architect's Amendment 2, 2026-09-30 14:21Z; a requirement for live use)

**Why.** Verified by QA at `ca0bcd9b`: the pump awaits `ft8Decoder.DecodeAsync` and publishes once (panel
`decodeEventBus.Publish`, ALL.TXT, archive `TryEnqueue`, filter admission, then the answerer, caller and
external-reporting channels: `Program.cs` ~858-906). The residual pass runs inside `DecodeAsync`, before that publish
(`Ft8Decoder.cs` ~370-384). So with the flag ON **every decode**, pass-0 included, reaches the operator only after the
whole residual pass: about 15 s + 5.5 s = 20.5 s median, against the 17.36 s deadline to answer a station heard in
that cycle (#122). No speed-up reaches that deadline (the pass would have to finish in under 1.8 s). This is an
operational defect of the flag-ON path, independent of R2′, so **two-stage publish is required whether or not Stage B
is built.**

**Shape (Developer decision, recorded here before coding).** `IModeDecoder.DecodeAsync` is unchanged and returns one list;
other callers (tests, the §8.1 harness, any other decoder) keep it. The two-stage path needs a new entry on `Ft8Decoder`
(for example an overload taking a publish callback for batch 1, or one that returns both batches) that the pump uses when
the flag is ON. **The same entry must be callable by a test or replay harness without the daemon pump**, or acceptance
rows S1 and S2 cannot be measured. The mapping state (`seen` text set, plausibility, region, worked-before, band) is
per cycle and shared by both batches.

**Consumer facts, verified in code at `ca0bcd9b` (QA, 2026-09-30):**

| Consumer | Verified behaviour | Consequence for batch 2 |
|---|---|---|
| Decode panel (`web/js/main.js` `handleDecodes`, ~777) | **Prepends** each result as a new row and never clears the table | Batch 2 rows arrive above batch 1's rows of the same cycle; nothing is replaced. No fix needed; the Developer still confirms with a test (S3 d) |
| ALL.TXT | `AppendAsync(cycleStart, dialFreq, results)` per publish | Batch 2 appends after batch 1 with the same stamp (pump stays serial) |
| Archive | `TryEnqueue(pcm, cycleStart, …, results.Count, …)` | Once, at batch 1 (P-6) |
| Filter admission | per-result `AdmitNewValues` | Runs for batch 2 as well (P-4) |
| QSO answerer | `_lastIdleDecodeBatch = batch` on **every** idle batch (`QsoAnswererService.cs` ~657); read by `TryEngageExternal` (~382) | A batch 2 sent here would **replace** the pass-0 snapshot. Hence **P-5: not sent** |
| QSO caller | treats every batch it receives as a cycle | Same reason. Not sent |
| **Manual engage (double-click)** | `POST /api/v1/tx/engage-decode` takes the callsign, frequency, cycle start, SNR and payload **from the browser's row** and validates with `IEngagementTargetValidator`. **It does not read `_lastIdleDecodeBatch`** | 🔴 **See the correction below** |
| External reply (GridTracker) | `TryEngageExternal` validates against `_lastIdleDecodeBatch` (idle, a CQ in the batch, not filtered out) | A reply naming a station heard only in batch 2 is ignored with the existing log line |

🔴 **Correction to the stated consequence of P-5 (for the Architect and the Captain).** The amendment says residual
decodes "cannot be engaged (a click or external reply is ignored with the existing log line)". Verified: that is true of
an **external reply**, and **not** of a double-click on the panel row, which does not consult the batch snapshot. So a
batch-2 CQ row **can probably be answered by double-click**, but by the time batch 2 arrives (about 20.5 s after the
cycle start) the immediate reply slot (17.36 s) has passed, so what the answerer then does with a pending target for the
*next* opposite-phase window is **not verified** and must be characterised by a test (tasks §13). What P-5 does
guarantee, and what is stated plainly for the operator: **residual decodes never reach the answerer or caller as batch
input.** So the caller will not see a reply to its own CQ that only the residual pass decoded, and an answerer mid-QSO
will not see a partner's report or RR73 that only the residual pass decoded (it counts that cycle as empty). With the
flag OFF those decodes do not exist at all, so this is not a regression; it means two-stage publish makes residual
decodes **visible, logged and spotted, not actionable by the automation**.

**Row review (HK-021 (k) / HK-026, QA's right, exercised as amendments not refusals). All three proposals were accepted
by the Architect as Amendment 3 (`arch/subtraction-feasibility` `974a450e`, §5c), and the P-5 correction below was
verified by them (`_lastIdleDecodeBatch` is read only at `QsoAnswererService.cs:382`, reached from
`QsoControllerRouter.cs:162`). The wording for the operator is now "visible, logged and spotted, not actionable by the
automation".**
- **S1** (union of batches equals the single-batch output of `ca0bcd9b` on the 161 E1 cycles; batch 1 equals flag OFF):
  not decorative (a split that drops or duplicates a decode fires it) and not vacuous (about 5 residual decodes per
  cycle). **One method point:** the native decoder's callsign hash table is process-global, so text and the plausibility
  filter can depend on what a process has already decoded. Both builds are therefore run in **fresh processes over the same
  cycles in the same order** (the sorted `(run, stamp)` order of `e1_selection.json`), so the sequence of native calls, and
  with it the hash-table history, is identical. Outcome fields only, never rendered text.
- **S2** (batch-1 median per run ≤ 1.05 × flag-OFF whole-call median; max ≤ 1 000 ms): the median term is sound (the
  same DLL measured twice differs by up to 1.5 %). **The max term is the concern:** the flag-OFF whole-call max was 830 ms
  in §8.1 and 791 ms in the Stage A session, so 1 000 ms sits only 170-210 ms above the tail of the very distribution it
  is compared to; over 905 cycles a single scheduler stall fires it, and then it would be reading noise, not a defect.
  **Accepted (Amendment 3):** the max term is read **per cycle** against the same-session flag-OFF whole call; cycles
  whose flag-OFF call itself exceeds 1 000 ms are excluded from the max term and counted; if more than 1 % are excluded
  the max term is **"not evaluable"**, reported as such, not passed. The median term is unchanged and the bar is not
  moved.
- **S3 additions (accepted):** (g) a manual engage on a batch-2 row: the behaviour is characterised, whatever it is;
  (h) an external reply naming a batch-2 station is ignored with the existing log line (the P-5 consequence, now tested);
  (i) the pump does not start the next window until batch 2 is published or abandoned (P-7); (j) the external-reporting
  channel sends no cycle-level message twice for a two-batch cycle (the Developer reads the service to confirm).
- **A gap S2 does not cover:** it times the hand-off of batch 1, not its delivery. The residual pass then runs 14 workers
  on 16 logical processors while the WebSocket delivery of batch 1 is in flight. The two cores reserved by A4 exist for
  this, but nothing measures it. **Accepted as a REPORT-ONLY row S2b** (time from batch-1 publish to receipt by a
  WebSocket client while the residual pass runs, against flag OFF; if materially above, it goes back to the Architect
  before any live use); the definitive check is an on-air session, which needs the Captain's separate go.
- **The flag-OFF control must reach the managed path (now run once, at the merge).** The base change's control compared three native DLLs through
  the raw C ABI, so the managed flag-OFF branch was never exercised (recorded caveat). This build changes exactly that
  managed path (one batch, the pump, the mapping). **Accepted:** the control re-run compares the outcome fields of
  `DecodeAsync` with the flag OFF between `2b39cf18` and the new build on the same cycles, in addition to the native
  comparison, so the caveat can finally be retired.

**Implementation record (Developer, `feat/sub-feas-two-stage-publish` @`247ac391`; QA code review: no defect found).**
- **API shape (13.1):** `Ft8Decoder.DecodeTwoStageAsync(pcm, cycleStart, currentBand, Func<IReadOnlyList<DecodeResult>, Task> publishFirstBatch, ct)`
  **returns batch 2**. `publishFirstBatch` is called **exactly once, always** (an empty batch 1 is a real cycle); with the flag ON it
  is called right after pass 0 is mapped and **before** the residual pass; with the flag OFF, a silent cycle or a native AV it is
  called once with the ordinary single-batch output and the return value is empty. Callable with no pump. `IModeDecoder.DecodeAsync`
  and every current caller are unchanged (the band overload is now a wrapper over a private core). `Ft8Decoder.SubtractionEnabled`
  exposes the flag; the pump reads it once per window and the core once per decode (a change in between degrades safely to one batch).
- **Pump:** the loop moved from `Program.cs` into `DecodePump` (delegates and channel writers, testable without the host). Flag OFF
  goes through the old inline sequence (panel, ALL.TXT, archive, admission, answerer/caller/external), no two-batch code touched.
- **P-8 semantic:** flag ON, the `Cycle {Time}: N decode(s) found, elapsed=` line reports **time to batch 1** (the stopwatch keeps
  running because the residual pass's budget is measured from the start of the decode). Flag OFF unchanged. The `Sub-feas residual
  pass:` line is unchanged. Note that batch 1's publish (including the awaited ALL.TXT append) is counted in the residual pass's budget.
- **13.4, external reporting (finding j):** a batch yields only Decode datagrams; Status and Heartbeat are timer-driven; there is no
  per-batch Clear; a same-cycle second batch repeats nothing. **Side effect:** the service's `_lastDecodeBatch` becomes batch 2, and it
  feeds only the diagnostic "Reply named X not found in own current decode batch", so that line becomes misleading for a pass-0 CQ
  after batch 2 arrives. Behaviour unchanged; a possible small follow-up, not a defect of this change.
- 🔴 **Finding (g), the double-click on a batch-2 CQ row (observed by the Developer, characterised, not changed):**
  `AnswererService.AnswerCqAsync` does not read the snapshot, arms the opposite-phase pending target and pushes a wake-up batch for the
  cycle running **now**. Batch 2 arrives about 5.5 s into that cycle, so the phase matches and **the answerer fires the reply
  immediately, mid-slot, with no lateness gate** (D-CALLER-021; `TransmitAsync` truncates). A 12.64 s message started about 5.5 s
  into a 15 s slot cannot complete, so **an operator's double-click on a residual row keys the transmitter for a truncated,
  undecodable transmission.** This is the answer to "can a residual decode be engaged by double-click": it can, and the result is
  worse than being unable to. It is the existing late-click behaviour, made likely for batch-2 rows because they arrive inherently
  late. **DECIDED by the Captain, 2026-09-30: NO CHANGE** (the Architect's §5e): *"when I look at wsjt-x is just starts transmitting
  no matter where it is in the cycle, the operator is in full control even when it is known to fail. I quite like that, it gives also
  direct feedback to the operator."* So: no lateness gate, no refusal, no row marking. **Immediate transmit on a late click is
  deliberate behaviour, matching WSJT-X, and is not a defect.** Test (g) stays as the record of that behaviour. (The external-reporting
  diagnostic above is behaviour-neutral and low priority, out of this change unless the Captain asks.)

**No native change and no shim bump** for two-stage publish: `src/` only. The DLL stays `ee00d118…990e4c`, so E1 and the
Stage A native evidence are unaffected.

### D10. Stage B: authorised by the Captain (Amendment 4); the finish line T′ and QA's HK-021 (k) review of it

**Decision (Captain, 2026-09-30, "option a, do stage B too").** Stage A's timing is accepted by him (R2 was designated
Captain-adjustable); the registered verdict "Stage A FAIL on R2′" stands and is not rewritten. Two-stage publish goes ahead
on the Stage A build and is not gated on Stage B. Stage B is a separate follow-on on its own branch
(`feat/sub-feas-stage-b` off `ca0bcd9b`): profile first, then items one at a time on E2/E3, then re-timed.

**Finish line T′ (fixed before any Stage B build):** `subtractionMaxThreads` = 4, over H, abandon ≤ 5 % AND max whole call
≤ 13 000 ms. R2′ at 14 workers is report-only. Stop at the first item that passes T′, after B3, or on the Captain's word.

**QA's (k) review of T′: accepted, no refusal, four notes.**
1. **The max term does not discriminate.** With the hard deadline the whole call is bounded by design (12 095 ms was measured
   at 4 workers while 56 % of cycles were abandoned), so `max ≤ 13 000 ms` fires only if A5 breaks. It re-tests A5, not Stage
   B. Harmless; **the term that decides T′ is the abandon rate.**
2. **T′ is a proxy for a small machine, not the machine.** It sets 4 workers on a 16-thread machine with the rest of the system
   idle. A real 4-thread machine defaults to 2 workers and contends with capture, the web UI and everything else. A pass says
   "this build finishes a heavy cycle at 4 workers on this machine", not "safe on other hardware" (HK-026). The report says so.
3. **Reachable, by rough arithmetic, not certain.** At 4 workers the abandon rate over H was 55.7 %. To keep 95 % of heavy
   cycles inside the deadline, a 28-signal cycle (7 waves at 4 workers) must finish its fits in about 10.9 s, so a fit at
   4-way concurrency must cost about 1.5 s or less. The Stage A single-thread fit is 1.26 s and the concurrency penalty at 4
   is unmeasured (the profile measures it). A cut of the order of 10-25 % looks like what T′ needs; that is an estimate from
   the Stage A rows, not a measurement.
4. **The pool is dominated by one run** (406 of 605 heavy cycles are 20260923_1730), as for every §8.1-selection row. T′ is
   pooled as R1′-R4′ were, and reported per run.

**Two practical requirements the finish line brings:**
- **E2 needs the fitted parameters.** The shipped fit returns only `out_shat`, so Δt, Δf and ḟ are not visible. A
  **test-only** way to read them is needed (tasks 15.3); the shipped ABI must not change beyond what an item itself needs.
- **E3 needs a Stage A baseline.** QA measures the Stage A total `residualDecodes` on the 161 E1 cycles with no deadline in
  effect (14 workers, asserting 0 abandons so it equals the unbounded result) before any Stage B build (tasks 15.2).

**Consequences to keep in view:** a numerics-changing item **breaks bit-identity, so E1 no longer applies**; each item's DLL
gets its own shim bump and SHA pin. **The flag-OFF control (native and managed) is a merge gate and runs ONCE, at the merge**, on whichever build the Captain decides to merge (Captain via the Architect, 2026-09-30); it is dropped from the current queue and not re-run per phase (tasks 10.5, 14.4, 15.7).

## Risks

- **Concurrency is the historical crash class.** D2's ownership model is the highest-risk item; it needs a stress
  test (many workers, many cycles, forced cancels) before any timing is read. Base-change §7 (stability gate) is
  still open and this change does not close it.
- **Exactness may fail at A1 or A2** for a rounding-order reason; E1 will say. The fallback is to revert that item
  or reclassify it as Stage B.
- **The reserve is thin** (D5); R1′ may miss by tens of milliseconds even if the design is right.
- **Stage A may not be enough.** The Architect registers P2 = 0.55 and P3 = 0.60 for meeting R2′ and R4′ on Stage A
  alone; the basis is arithmetic (about 170 of 377 FFTs removed, 6 waves cut to 2), not measurement.

## Open Questions

- The exact ABI shape of the cancel flag and of the M2 diagnostics switch (D3, tasks §1).
- ~~Negative `subtractionMaxThreads`~~ **CLOSED 2026-09-30 (Architect):** any non-zero value clamps to
  `[1, ProcessorCount]`, so a negative value becomes 1. **One warning log when the config is applied**, following the
  existing clamp-with-warning pattern in `POST /api/v1/config` (`WebApp.cs:578` region, e.g. `CAT: pollIntervalSeconds
  {Original} out of range [1, 60] — clamped to {Clamped}.`). **Never per cycle**: nothing new goes on the hot path.
  A value edited into the config file (which bypasses that POST path) is clamped silently per cycle and warned about
  at most once when the config is loaded.
- Whether a native memory counter export is acceptable for the leak test, or the test uses process private bytes
  (tasks §8).
