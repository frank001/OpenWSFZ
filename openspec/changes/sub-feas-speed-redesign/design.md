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

### D2. Workspace ownership: a bounded, explicitly-owned pool is preferred; per-thread storage needs a shutdown story

A3 says "one workspace and plan set per worker, allocated once". The trap is that C# fits run on **thread-pool
threads that the native code does not own**. Thread-local storage in C has no destructor here, so per-thread
workspaces would leak when the pool retires a thread, and cannot be freed at shutdown from another thread. Two
mechanisms satisfy the spec:

1. **A bounded pool** (recommended): a fixed array of `subtractionMaxThreads` workspaces guarded by a lock;
   `fit_signal` acquires one, uses it, releases it. Freed by an explicit export at shutdown. Memory is bounded by
   construction and the ownership is visible.
2. **Thread-local workspaces plus a registry** of every allocation so a shutdown export can free them all.

The Developer records the choice here before writing code (tasks §1). Constraints either way: heap only; the bound
is the configured thread count (a changed count must resize or drain the pool safely, or take effect at next cycle
boundary with nothing in flight); no two concurrent fits share a workspace; freeing while a fit is in flight is
impossible (shutdown waits or refuses). This is where the base change's two `0xC0000005` crashes lived, so this is
the review focus.

### D3. The cancellation flag: shape, memory model, lifetime

- **Shape:** one extra `const volatile int* cancel_flag` parameter on `ft8_subfeas_fit_signal` (NULL means "no
  deadline", which keeps the no-deadline path identical). New return code `-4`. The Architect's spec names the
  exact mechanism (`int*` that C# sets, checked per Δt/ḟ iteration); the exact ABI signature is a Developer decision
  recorded here.
- **Checked at:** the top of each of the 201 Δt candidates, each of the 41 ḟ candidates and the envelope loop, and at
  entry. The longest uninterruptible stretch is then one candidate (a small number of FFTs, tens of milliseconds
  expected; **unmeasured**, tasks §2 measures it), which is why a 1 000 ms reserve is comfortable for the fit and the
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
1 000 ms, a named constant, not a literal), and skips the residual decode if less than the reserve remains. The margin
between the reserve (1 000 ms) and the largest observed flag-OFF whole call (830 ms) is **170 ms**, on a single
outlier, before the merge/dedup step. **R1′ is therefore a tight bar**, not a comfortable one. That is the
Architect's registered row and it stands; this note exists so a marginal R1′ miss is read as "the reserve is thin",
not as a surprise. M2 should make the residual decode cheaper, which helps.

### D6. Thread count

`decoder.subtractionMaxThreads`, default `max(1, ProcessorCount − 2)`, clamped `[1, ProcessorCount]`, read per cycle
like `decoder.subtractionEnabled`. Two threads are left for capture, the web UI and any co-resident WSJT-X. **Memory:**
about 25–30 MB per worker resident (about 0.4 GB at 14 workers); accepted by the Architect's default, changeable by the
Captain. **A new config key interacts with the in-flight config-save work** (#193, "config save preserves unsent
settings"): the key is optional and has no UI, and the config POST is a full replace (HK-035), so the Developer must
confirm a save from the settings page neither drops nor resets it once that workstream lands.

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
covers other hardware. R5′ compares the new build's flag-OFF cost with the old build's: QA proposes (to the
Architect, `qa/rr-study/2026-09-30-…-qa-to-architect-…`) that the baseline be the `2b39cf18` DLL **re-measured in the
same acceptance session** on the same cycles, not the §8.1 medians, because the §8.1 medians were taken with WSJT-X
and a browser resident and the acceptance run is made with WSJT-X closed, which would flatter the candidate.

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
- Whether `subtractionMaxThreads` changes mid-run resize the pool or apply at the next cycle boundary (D2).
- Whether a native memory counter export is acceptable for the leak test, or the test uses process private bytes
  (tasks §8).
