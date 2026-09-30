# SPEC — SUB-FEAS speed redesign: more threads, faster fit, hard deadline, lean hot path

- **Date (UTC):** 2026-09-30 06:41Z (mechanically derived, `date -u`, HK-017)
- **Author:** Architect. **To:** QA (SUB-FEAS owner). QA authors the OpenSpec change, `tasks.md` and the Developer
  handoff (HK-015/HK-000). The build is `src/` + `native/`, so it needs a separate Developer session (HK-011).
- **Authorised:** the Captain, 2026-09-30, after the §8.1 FAIL (`2026-09-30-0641-architect-sub-feas-8-1-ruling.md`):
  *"go for option 2. more threads, code speedup, remove redundant monitoring from hot decode path"*.
- **Base:** `feat/sub-feas-native-subtraction` @ `2b39cf18` (shim `20260055`, `libft8.dll` `5a6a4dc0…e38c5`).
- **Claims NOT made:** no decode-rate claim, and no live use. The flag stays **OFF** by default; §7 and §8.2 stay open.

---

## 0. Where the time goes (static reading of `2b39cf18`; not measured, the build logs no per-phase time)

One `ft8_subfeas_fit_signal` call (`native/ft8_lib_vendor/subfeas/subfeas_fit.c`) does roughly **377 complex FFTs of
N = 262 144** plus about 12 M double-precision sin/cos pairs:

| Phase (`fine_fit_with_drift`, `:341`) | Work per signal |
|---|---|
| Step 1: Δt search, 201 candidates (`DT_N_STEPS` = 100) | 201 × `freq_search` = **201 FFTs**, plus 1 `r_fit_drift` |
| Step 2: ḟ search, 41 candidates (`FDOT_N_STEPS` = 20) | 41 × (`r_fit_drift` → `instantaneous_phase` = **3 FFTs** + 151 680 cos/sin, then `apply_freq_shift` = 151 680 cos/sin, then `freq_search` = 1 FFT) = **164 FFTs** |
| Final template | 1 `r_fit_drift` (3 FFTs) + 2 shifts |
| Step 3: Δt refine, direct correlation | 201 × 151 680 complex MACs (no FFT) |
| `lp_envelope` | 2 × `fft_convolve_same` = **6 FFTs** |
| Setup, **every signal** | `workspace_alloc`: ~25 MB of `malloc`, and 2 × `kiss_fft_alloc(262144)` (twiddle tables recomputed); `gaussian_pulse` recomputed |

**Redundancies I can see in the code; all four are exact (bit-identical output):**

1. **The tone smoothing does not depend on ḟ, but it is recomputed 43 times per signal.** `instantaneous_phase`
   (`:238`) convolves `tone_arr` with the Gaussian pulse (3 FFTs) on every `r_fit_drift` call. Only the drift term
   (`:261-264`), which is added **after** the convolution, depends on ḟ. The smoothed tone track is the same for all
   43 calls. **About 126 of the 377 FFTs are pure repeats.**
2. **Constant spectra are re-transformed on every convolution:** the Gaussian pulse (`pulse_cf`) and the Hann window
   (`win_cf`) are FFT'd each time `fft_convolve_same` runs.
3. **The workspace and the FFT plans are rebuilt for every signal** (`ft8_subfeas_fit_signal`, `workspace_alloc` /
   `workspace_free`, `kiss_fft_alloc`).
4. **Parallelism is capped at 4** (`Ft8Decoder.cs:63`, `Math.Min(Environment.ProcessorCount, 4)`), on a 16-thread
   station machine. The fits are independent per signal (`SubtractionPass.cs:237`).

**Why the deadline overshoots:** the guard is checked only between phases (`SubtractionPass.cs:222/250/279`), and
`Parallel.For` cancellation is only observed **between** iterations. Once a native fit (~1 s or more) or the residual
`DecodeAll` (~0.5 s) has started, nothing can stop it.

**The monitoring in the hot decode path** (Captain's third item), found in `2b39cf18`:

| Item | Where | Consumer | Verdict |
|---|---|---|---|
| **LDPC-fail LLR statistics:** `ftx_compute_candidate_llr_stats` re-extracts and normalises the LLRs of **every failed candidate**, then sums them into `tls_llr_*` | `ft8_shim.c:1631-1636`; getter `:1351`; C# `Ft8Decoder.cs:338`, Debug log `:480-495` | one **Debug** log line. The code's own comment says the hypothesis it served was **REFUTED** ("retained for longitudinal monitoring") | **remove** (§1 M1), subject to the consumer check |
| Per-pass candidate/decode counts | `tls_pass_counts`, `tls_candidate_counts`; Debug log `:470-477` | Debug log | cheap counters; keep, but skip the log formatting unless Debug is enabled (M3) |
| All of the pass-0 diagnostics, **repeated on the residual `DecodeAll`** | `SubtractionPass.cs:271` | **none**: nothing reads the TLS after the residual call | **skip** on the residual call (M2) |
| Global noise floor | `compute_noise_floor`, `ft8_shim.c:1494` | the per-cycle diagnostic **and the local-noise SNR fallback** (`ft8_shim.c:1166`) | **keep**: it feeds a decode output |
| Per-cycle `Information` line; the `Sub-feas residual pass:` line; SEH containment; input validation | | the R4 instrument, crash safety | **keep**: not redundant |

🔴 **My one concern, stated once:** monitoring removal cannot close this gap. The whole flag-OFF decode is
473–528 ms median (§8.1 table), and the diagnostics are a small part of that. The time is in the fit: about 377 FFTs per
signal, times about 23 signals. Part M is worth doing, and it is measured separately (R5′) so that its effect is not
credited with the fit's speedup.

---

## 1. The work, in two stages. Stage B only if Stage A misses its bars.

### Stage A — exact changes only (output bit-identical to `2b39cf18`)

| # | Change | Where |
|---|---|---|
| A1 | Compute the smoothed tone track **once per signal**; `r_fit_drift` applies only the ḟ-dependent drift term and the cos/sin | `subfeas_fit.c:238-283` |
| A2 | FFT the Gaussian pulse and the Hann window **once** (per workspace) and reuse their spectra in `fft_convolve_same` | `:168-230`, `:449-500` |
| A3 | One workspace **and FFT plan set per worker thread**, allocated once and reused across signals and cycles (**heap only**; the heap-allocation requirement and its crash history stand), freed at shutdown | `:102-160`, `ft8_subfeas_fit_signal` |
| A4 | Thread count becomes config `decoder.subtractionMaxThreads`; **default `max(1, ProcessorCount − 2)`** (14 on the station). Clamp to `[1, ProcessorCount]` | `Ft8Decoder.cs:63` |
| A5 | **Hard deadline.** A cancellation flag (an `int*` that C# sets) is checked by the native fit at every Δt, ḟ and envelope iteration; the fit returns a new rc `-4` when it is set. C# sets the flag at `budget − reserve`, with **reserve = 1 000 ms** for the residual `DecodeAll` (the §8.1 flag-OFF max whole call was 830 ms), and does **not** start the residual decode with less than the reserve left. Semantics unchanged: a deadline abandons the pass (pass-0 results only) | `subfeas_fit.c`, `SubtractionPass.cs`, `Ft8Decoder.cs:374` |
| M1 | Remove the LDPC-fail LLR statistics computation, its TLS, getter and Debug log. ⚠️ **Precondition:** QA greps `qa/`, `tools/` and the RUNBOOKs for `prenormVar`, `meanAbsLLR`, `failCands` and `LDPC fail stats`. **If any consumer is found, STOP and ask the Captain**; do not remove | `ft8_shim.c`, `Ft8LibInterop.cs`, `Ft8Decoder.cs` |
| M2 | The residual `DecodeAll` runs with diagnostics off (a flag parameter or a separate export), computing nothing that only a TLS getter would read. It must not change any decode output field | `ft8_shim.c`, `SubtractionPass.cs:271` |
| M3 | Guard the Debug-only per-pass log loops with `logger.IsEnabled(LogLevel.Debug)` | `Ft8Decoder.cs:470-495` |

ABI/shim: A5, M1 and M2 change the exported surface ⇒ bump `FT8_SHIM_VERSION`, rebuild **all three platforms**
(`build_linux.sh` compiles `subfeas_fit.c` too), and pin the new DLL SHA-256 (HK-022).

### Stage B — numerics-changing (**only** if Stage A fails R2′ or R4′; each item is its own gated step)

| # | Change | Note |
|---|---|---|
| B1 | A faster FFT than KissFFT | 🛑 licence policy: permissive only (MIT/BSD/ISC). pocketfft-C (BSD-3) qualifies; **FFTW is GPL and prohibited** |
| B2 | Prune `freq_search`: only \|f\| ≤ `SUBFEAS_DF_RANGE_HZ` = 2.0 Hz is used, i.e. about ±44 of 262 144 bins at 0.0458 Hz spacing. Use decimation plus a small FFT, or a pruned DFT | step 1 is 201 of these per signal |
| B3 | Coarse-to-fine Δt in step 1 (201 → about 50 candidates) | changes the search |

Stage B changes the fitted parameters by rounding or by search, so it is accepted on **equivalence within tolerance**
(E2) plus **no loss of residual decodes** (E3), never on speed alone.

---

## 2. Acceptance: mechanical, pre-registered (HK-021). QA may REFUSE any row on (k) grounds (HK-025)

The instrument is the **§8.1 harness and frozen selection** (`selection.json` SHA-256 `730d6ea6…`, harness `cd36bb42`
updated only for the new config knob, with the SHA stated). Same corpus, same strata, same R0. Record the machine state,
and run with WSJT-X **closed** this time (the §8.1 run had it resident).

| Row | Predicate | Stage |
|---|---|---|
| **E1 — exactness** | A test-only harness (in `tests/`, not in the product path) calls the fit on the **60 pilot cycles** plus a fixed subset of H ∪ M (**every 9th stamp** of the sorted list, ≈ 100 cycles), once through the `2b39cf18` DLL and once through the candidate DLL, **with no deadline**. It writes the SHA-256 of `out_shat` and the rc per (cycle, signal). **PASS iff 100 % identical.** It also asserts, as code, that the flag-OFF decode outcome fields are identical on the same cycles (M1–M3 must not change outputs) | A |
| R0 | as §8.1 (via each archive's producing DLL) | A, B |
| **R1′** | over H ∪ M, flag ON: **max whole-call elapsed ≤ 13 000 ms** (now a hard bound, not a guard reading) | A, B |
| **R2′** | max ≤ 10 000 ms **AND** p95(H) ≤ 6 000 ms (the §8.1 R2 bars, unchanged) | A, B |
| R3 | 0 AV / 0 contained / 0 exits (as §8.1) | A, B |
| **R4′** | deadline-abandon rate over H **≤ 5 %**. **Now a BAR, no longer report-only:** a pass that is abandoned is not useful | A, B |
| **R5′** | flag-OFF median whole call on the new build ≤ `2b39cf18`'s flag-OFF median × 1.05, per run. Report the change (M1–M3 should make it faster; report whatever it is) | A |
| R6 | synthetic pairs as §8.1, bar 13 000 ms (the old +3 000 ms allowance is **dropped**: A5 makes the bound hard) | A, B |
| R7 | descriptive, as §8.1. No claim | A, B |
| **E2 — equivalence (Stage B only)** | per fitted signal, B-build vs A-build, with no deadline, on the E1 cycles: Δt identical ±1 step (12 samples), Δf within ±1 bin (0.0458 Hz), ḟ same step, on **≥ 99 %** of signals; per-cycle residual energy within **±0.1 dB** on ≥ 99 % of cycles | B |
| **E3 — no loss (Stage B only)** | on the E1 cycles, with no deadline: total `residualDecodes`(B) ≥ **0.98 ×** total `residualDecodes`(A) | B |
| **T — threads** | also run R1′/R2′ at `subtractionMaxThreads = 4` on the H stratum only, so the thread effect is separated from the A1–A3 code effect. Report only | A |

**Order:** E1 first (if it fails, STOP: Stage A was not exact), then R0, then the timing rows. Stage A PASS = E1, R0,
R1′, R2′, R3, R4′, R5′ and R6 all pass. If Stage A passes, Stage B is **not** built. If Stage A fails only R2′ or R4′,
Stage B goes ahead item by item (B1, then re-measure, then B2, then B3), stopping at the first item that passes.

---

## 3. Blind spot (HK-026), unchanged

No real cycle has more than 32 pass-0 signals. A PASS means "up to 32 real signals on this machine". **Other hardware
is not covered:** A4's default scales with `ProcessorCount`, so a 4-thread machine gets 2 fit threads, and nothing here
says it meets 13 s. State this in the OpenSpec change and in the report.

## 4. Decisions for the Captain (defaults are set; each is changeable)

- **Thread default `ProcessorCount − 2`** leaves two threads for capture, the web UI and WSJT-X. Memory: A3 keeps
  about **25–30 MB per worker** resident (≈ 0.4 GB at 14 workers). Default kept unless the Captain says otherwise.
- **CPU-specific builds (`/arch:AVX2`, `/fp:fast`) are NOT in scope.** They would speed things up but make the DLL
  CPU-specific or change numerics. A separate decision.

## 5. Predictions (registered now, scored at the acceptance ruling)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| P1 | E1 passes on the first build (Stage A is really bit-identical) | 0.60 | H |
| P2 | Stage A alone meets R2′ (p95(H) ≤ 6 000 ms) | 0.55 | H |
| P3 | Stage A alone meets R4′ (abandon ≤ 5 % over H) | 0.60 | H |
| P4 | R5′: M1–M3 change the flag-OFF median by **less than 5 %** in either direction (monitoring is not where the time is) | 0.80 | H |

The basis for P2/P3 is arithmetic, not measurement: A1–A2 remove about 170 of 377 FFTs per signal, A3 removes the
per-signal setup, and A4 cuts about 23 signals from 6 waves to 2. That is roughly 5–6× on a pass that now needs more
than its budget. Per the ledger, my HYPOTHESISED calls lean toward optimism about a findable, localised fix. Weight
them accordingly.

## 5a. Amendment 1 (2026-09-30, after QA's authoring pass `qa/sub-feas` `3d4d406c`; both proposals accepted)

- **M1 is DEFERRED (Captain).** The precondition fired: four QA scripts parse the LDPC-fail Debug line
  (`ldpc_stats.py`, `run_isolated_replay_generic.py`, `run_isolated_replay.py`, `run_tight_replay.py`). Stage A ships
  A1–A5, M2 and M3 only. **P4 is scored on M2 + M3 alone**, and nothing in R5′ may be credited to M1.
- **R5′ baseline (QA proposal 1, accepted, drafting defect mine):** the baseline is the **`2b39cf18` DLL re-measured in
  the same acceptance session**, on the same machine state, not the §8.1 medians. §8.1 ran with WSJT-X, a browser
  and Voicemeeter resident, and comparing against it would flatter the candidate. Bar unchanged (≤ 1.05×, per run).
- **E1 selection (QA proposal 2, accepted):** pool H ∪ M as `(run, stamp)` pairs, sort by `(run, stamp)`, take indices
  0, 9, 18, …, plus the 60 pilot cycles. My "every 9th stamp of the sorted list" did not say how runs were ordered.
- **A5 reserve is raised from 1 000 ms to 1 500 ms** (a design parameter, not a bar; fixed now, before any build).
  QA's note is correct: 1 000 ms against an 830 ms flag-OFF maximum leaves 170 ms. R1′'s bar is unchanged (13 000 ms).
- **A3 workspace ownership:** adopt QA's `design.md` D2. A **bounded, locked pool** of heap workspaces, size =
  `subtractionMaxThreads`, leased per fit call and returned in a `finally`. No thread-local native state, because
  thread-pool threads are not native-owned. Freed at decoder dispose.
- **Config key vs #193:** `decoder.subtractionMaxThreads` is represented as **`0 = auto` (`ProcessorCount − 2`), which
  is also the default**, so the #193 reset defect degrades it to auto rather than to a wrong value. The Settings page
  does not send `subtractionEnabled` or `subtractionMaxThreads`, so until the config-save fix lands, a Settings save
  resets both (the flag to OFF, which fails safe). The Engineer owns that fix and is told of these two keys.
- **QA's open question (design.md), confirmed:** any non-zero value clamps to `[1, ProcessorCount]`, so a negative value
  becomes 1. The clamp logs **one warning when the config is applied** (the existing clamp-with-warning pattern for
  CAT/TX/Decoder in `POST /api/v1/config`), never per cycle: nothing new goes on the hot path. 1 is the conservative
  direction (slower, so the deadline abandons; it cannot overload the machine).

## 5b. Amendment 2 (2026-09-30 14:21Z): two-stage publish, a REQUIREMENT for live use (Captain, via #122)

**Authorised:** the Captain asked whether GitHub #122 (decode-panel latency) could help, then said *"yes, write the
amendment for QA"* after the Architect's answer below.

### Why (verified in code at `ca0bcd9b`)

- The decode pump (`Program.cs:858-906`) awaits `ft8Decoder.DecodeAsync`, then publishes **once**: the panel
  (`decodeEventBus.Publish`, `:869`), ALL.TXT (`:870`), the archive (`:877`), the filter admission (`:886-895`), and the
  QSO/external channels (`:900-903`).
- With the flag ON, the residual pass runs **inside** `DecodeAsync`, **before** that publish
  (`Ft8Decoder.cs:370-384`): the residual decodes are appended to `native` ahead of the mapping loop. So **every**
  decode, pass-0 included, reaches the operator only after the whole residual pass.
- To answer a station heard in cycle N, TX must start by **17.36 s** (#122: 15 s + the 2.36 s guard). At Stage A
  timings the panel updates at ≈ 15 + 5.5 s = **20.5 s median, ≈ 23.7 s worst**. ⇒ **With the flag ON as built, the
  operator cannot answer anything in the next cycle.** No realistic speed-up fixes this (the pass would need
  < 1.8 s). This is an operational defect of the flag-ON path, independent of R2′.

### The change (`src/` only; no native change, no shim bump)

| # | Requirement |
|---|---|
| **P-1** | Flag ON: pass-0 decodes are mapped and **published as batch 1 as soon as pass 0 returns**, through exactly the same pump path as today (panel, ALL.TXT, archive, filter admission, QSO and external channels). The residual pass starts **after** batch 1 is published. |
| **P-2** | Residual decodes are published as **batch 2** of the same cycle (same `cycleStart`), when the pass completes. Nothing is published for batch 2 if the pass is abandoned or yields no new decodes. |
| **P-3** | **Batch 2 goes through the same mapping as batch 1** (TrimEnd, `IsPlausibleMessage`, region, worked-before, band). **Text de-duplication spans both batches** (the `seen` set is per cycle, not per batch), and the SubtractionPass payload de-dup is unchanged. |
| **P-4** | Batch 2 destinations: **panel** (appended, never replacing batch 1's rows; the Developer verifies `main.js:1820` appends and fixes it if not), **ALL.TXT** (appended after batch 1's lines with the same cycle stamp; the pump stays serial, so the next cycle's lines always come after), **filter admission**, and the **external-reporting channel** (GridTracker/UDP). |
| **P-5** | 🛑 **Batch 2 is NOT sent to the QSO answerer/caller channels in this change.** Verified reason: `QsoAnswererService` keeps `_lastIdleDecodeBatch` (`:104`, used at `:382` by `TryEngageExternal`). A residual-only second batch for the same cycle would **replace** the pass-0 snapshot, so a double-click or GridTracker reply to a pass-0 station would then fail. The answerer and caller also treat each batch as a cycle. **Consequence, stated for the Captain:** residual decodes are visible, logged and spotted, but **cannot be engaged** (a click or external reply is ignored with the existing log line). Making them engageable is a separate change. |
| **P-6** | Archive `TryEnqueue` runs **once**, at batch 1, with the pass-0 count. Equivalent for `Decoded` mode: the residual pass runs only when pass-0 count > 0. |
| **P-7** | The pump stays **serial**: the next capture window is not decoded until batch 2 has been published or abandoned. R1′'s hard bound (13 s from cycle close ≈ 28 s) finishes before the next window closes (30 s). |
| **P-8** | The per-cycle `Cycle {Time}: … elapsed=` line reports **time to batch 1** (for flag OFF, identical to today, which keeps #122's series continuous). The residual time stays in the `Sub-feas residual pass:` line. Record the semantic in `design.md`. |
| **P-9** | **Flag OFF: exactly one batch per cycle, byte-identical behaviour.** The flag-OFF control re-run (tasks 10.5) covers this build too. |

### Acceptance rows (added; nothing above is moved)

| Row | Predicate |
|---|---|
| **S1 — split changes timing only** | On the E1 cycles (161), flag ON: the **union** of batch 1 and batch 2 outcome fields (after mapping and de-dup) equals the single-batch output of `ca0bcd9b` for the same cycle, as a set. Batch 1 equals the flag-OFF output of the same build. Outcome fields only, never rendered text (process-global hash table). PASS iff 161/161 |
| **S2 — batch-1 latency** | Over H ∪ M, flag ON: time to batch 1, median per run ≤ **1.05 ×** the flag-OFF whole-call median in the same session; max ≤ **1 000 ms**. (Pass 0 is unchanged, so this tests that nothing new sits before the first publish) |
| **S3 — consumers** | Tests (in code, not by inspection): (a) the QSO answerer/caller receive exactly one batch per cycle with the flag ON; (b) `_lastIdleDecodeBatch` after a flag-ON cycle equals batch 1; (c) ALL.TXT holds batch 1's lines then batch 2's, same stamp, no duplicate text within the cycle; (d) the panel receives two `decode` events and shows the union; (e) the archive enqueues once; (f) flag OFF gives one publish per cycle |
| S4 — existing rows | E1, R0–R7 and the Stage B rows are unchanged; batch 2's publish time is R1′'s whole-call time |

### Effect on the Stage A ruling and Stage B (the Architect's recommendation changes)

The 6 000 ms p95 bar in R2′ was a **headroom margin I set**, not an operational deadline. Once P-1..P-9 hold, batch 1
meets the TX deadline exactly as today, and batch 2 only has to arrive within the cycle (R1′, met: max 8.65 s).
**I therefore withdraw my recommendation against accepting Stage A's timing.** The choice is the Captain's:

- **(a)** accept Stage A timing on this machine, build P-1..P-9, and treat Stage B as optional; or
- **(b)** also do Stage B. The remaining argument for it is **other hardware**: Row T showed 56 % of heavy cycles
  abandoned at 4 workers.

Either way, two-stage publish is required before any live use. Live use itself remains the Captain's decision, and
the flag stays OFF by default. A first on-air flag-ON session is a **new decision, needing his explicit go**; it is
not implied by this amendment.

## 5c. Amendment 3 (2026-09-30, after QA's fold-in `qa/sub-feas` `3f0183b3`; correction accepted, proposals accepted)

- **CORRECTION to P-5's stated consequence (drafting defect mine, verified):** `_lastIdleDecodeBatch` is read **only**
  by `QsoAnswererService.TryEngageExternal` (`:382`), reached from `QsoControllerRouter.cs:162`, i.e. the
  **external (GridTracker/UDP) reply** path. The **double-click** path (`POST /api/v1/tx/engage-decode`,
  `WebApp.cs:1633`) takes its target from the browser row and validates it with `IEngagementTargetValidator`; it does
  not read that snapshot. So:
  - a batch-2 row **can probably be engaged by double-click**, but it arrives ≈ 20.5 s into the cycle, after the
    17.36 s slot. What the answerer does with that pending target in the next window is **unverified**. QA's
    characterisation test (g) records it, with **no behaviour change** in this change.
  - What P-5 guarantees: residual decodes **never reach the answerer or caller as batch input**. The caller will not
    see a reply to its own CQ that only the residual pass decoded, and an answerer mid-QSO will not see a partner's
    report that only the residual pass decoded.
  - **Correct wording:** residual decodes are *"visible, logged and spotted, not actionable by the automation"*.
    What I first told the Captain ("cannot be engaged") was wrong for double-click, and has been corrected to him.
- **S2 max term (QA 2a, accepted):** read per cycle against the **same-session flag-OFF whole call**. Cycles whose
  flag-OFF call itself exceeds 1 000 ms are excluded from the max term and counted. If more than 1 % of cycles are
  excluded, the max term is **"not evaluable"**, reported as such, not passed. The median term is unchanged.
- **S2b (QA 2b, accepted, REPORT ONLY):** time from batch-1 publish to receipt by a WebSocket client **while the
  residual pass is running**. Reason: 14 fit workers can crowd the thread pool that WebSocket delivery also uses.
  Reported; if it is materially above the flag-OFF delivery time, it comes back to the Architect before any live use.
- **Flag-OFF control (QA 2c, accepted):** extend the re-run (tasks 10.5) to the **managed `DecodeAsync` path**. This
  build edits it, and the base control never exercised it (a gap already on the board).
- **S1 method (QA 3, accepted):** both builds in **fresh processes, over the same cycles in the same order** (the
  native hash table is process-global). S3 additions (g)–(j) as in QA's note.

## 5d. Amendment 4 (2026-09-30): the Captain's decision, "option a, do stage B too"

- **Stage A's timing is ACCEPTED by the Captain** (R2 was designated Captain-adjustable). R2′'s p95 miss (6 410.8 ms)
  no longer blocks anything. The registered verdict stays "Stage A FAIL on R2′"; it is **not** rewritten as a PASS.
  The acceptance is the Captain's, and is recorded here.
- **Two-stage publish (§5b/§5c) goes ahead on the Stage A build** and is **not** gated on Stage B. Order: P-1..P-9,
  then S1–S3/S2b, then the flag-OFF control re-run (extended to managed `DecodeAsync`).
- **Stage B is AUTHORISED as a follow-on**, on its own branch/commits after two-stage publish, never mixed into it.
  First the `FitProbe time` profile of the candidate at 1 and 14 workers. Then items one at a time (default B1 → B2 →
  B3, re-ordered by the profile), each accepted on **E2 and E3 first**, then re-timed.
- **Stage B's finish line (new, fixed before any Stage B build).** Its stated purpose is other hardware, so the target
  is row T:
  - **T′ (a BAR for Stage B only):** at `subtractionMaxThreads = 4`, over H, deadline-abandon **≤ 5 %** AND max
    whole call ≤ 13 000 ms. §8.1's heavy-cycle selection, same session rules as Stage A.
  - Also report R2′ at 14 workers (p95(H) ≤ 6 000 ms would now be a bonus, not a gate).
  - **Stop** at the first item after which T′ passes, **or** after B3, **or** when the Captain says so. If T′ is still
    failing after B3, report the residual gap. A 4-worker machine then simply runs with more abandons (safe: the hard
    deadline held at 4 workers, max 12 095 ms).
- 🛑 Unchanged: the flag stays **OFF** by default. A first on-air flag-ON session needs the Captain's explicit go.

## 6. Hygiene

- 🔒 NFR-021 / HK-037: stamps and integers only, as in §8.1. The E1 harness writes hashes and rcs, never text.
- HK-016/019/023: detached run, artefacts gathered, orphan check. HK-022: pin every DLL used (`2b39cf18` and the
  candidate) by SHA-256 in the report; quote any `--filter`.
- The flag-OFF control (ruling 2) must be re-run on the new build before any merge: A5, M1 and M2 touch the native decode
  path. Same predicate as ruling 2.
- `src/`/`native/` diff of this commit: none (HK-011).
