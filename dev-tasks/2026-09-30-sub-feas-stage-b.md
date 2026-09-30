# SUB-FEAS Stage B: profile first, then numerics-changing fit items one at a time, to a fixed finish line

**Date:** 2026-09-30
**Prepared by:** QA (HK-015: Architect → QA → Developer)
**Audience:** Developer (to execute); Captain (hand-over per HK-000, merge sign-off HK-010, push go-ahead HK-033)
**Status:** **DRAFT for hand-over.** The Captain authorised Stage B on 2026-09-30 ("option a, do stage B too"), recorded in the Architect's Amendment 4 (`arch/subtraction-feasibility` `935af9d4`, §5d). QA has not had a separate direct go for this hand-over; the Captain hands it over.
**Branch:** create `feat/sub-feas-stage-b` **off** `feat/sub-feas-speed-redesign` (`ca0bcd9b`, Stage A). **Not** off the two-stage branch: Stage B is a **separate follow-on, never mixed into the two-stage work**, and is measured on the same instrument as Stage A. The two combine at merge (a Captain decision).
**OpenSpec change:** `openspec/changes/sub-feas-speed-redesign/` on `qa/sub-feas`: the last added requirement, `design.md` **D10**, `tasks.md` **§15**. `openspec validate --all --strict` is 62/62.

---

## 0. Why this exists, and what "done" is

Stage A made the residual pass fit inside the cycle on this machine but not with headroom on a smaller one: at `subtractionMaxThreads = 4`, 337 of 605 heavy cycles (55.7 %) were deadline-abandoned (the hard bound held, max 12 095 ms). Stage B exists for **other hardware**. Its finish line is fixed **before any Stage B build**:

> **T′: with `subtractionMaxThreads` = 4, over the heavy (H) stratum, deadline-abandon ≤ 5 % AND max whole call ≤ 13 000 ms.**

R2′ at 14 workers is now report-only. **Stop** at the first item after which T′ passes, or after B3, or when the Captain says so. If T′ still fails after B3, report the residual gap. (QA's note: the max term is bounded by the hard deadline and re-tests A5; **the abandon rate is what decides T′**. T′ is a proxy for a small machine, not the machine: it sets 4 workers on a 16-thread machine.)

## 1. Step 1: profile (test-only; no product-path change; do this first)

Re-run `Ft8.FitProbe time` on the **candidate** DLL (`libft8.dll` `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c`) at **1, 4 and 14 concurrent workers**. Report per-phase milliseconds (step 1 Δt search, step 2 ḟ search, final template, step 3, envelope, the analytic call, one residual `DecodeAll`) and the **per-fit concurrency penalty** at 4 and at 14 (the roughly 2× at 14 workers is unmeasured and is what the Architect's P2 arithmetic missed). Integers only. The profile **ranks the items**: the default order is B1 → B2 → B3, re-ordered by evidence. Send it to QA and the Architect **before building any item.**

## 2. Step 2: the items, one at a time (after QA has the E3 baseline and you have recorded the test-only parameter hook)

| Item | What | Note |
|---|---|---|
| **B1** | A faster FFT than KissFFT | 🛑 **Licence: permissive only (MIT/BSD/ISC).** pocketfft-C (BSD-3) qualifies. **FFTW is GPL and prohibited.** Add its licence file under `native/`; `tools/LicenseInventoryCheck` must pass. |
| **B2** | Prune `freq_search` | only \|f\| ≤ `SUBFEAS_DF_RANGE_HZ` = 2.0 Hz is used, about ±44 of 262 144 bins at 0.0458 Hz spacing: decimation plus a small FFT, or a pruned DFT. Step 1 runs 201 of these per signal. |
| **B3** | Coarse-to-fine Δt in step 1 | about 201 → 50 candidates. Changes the search. |

**Each item is its own commit(s), its own `FT8_SHIM_VERSION` bump, its own pinned DLL SHA-256.** Each is accepted on **E2 and E3 first, never on speed**, then re-timed by QA:

- **E2 (equivalence), per fitted signal, Stage B vs Stage A, no deadline, on the 161 E1 cycles:** Δt identical ±1 step (12 samples), Δf within ±1 bin (0.0458 Hz), ḟ the same step, on **≥ 99 %** of signals; per-cycle residual energy within **±0.1 dB** on ≥ 99 % of cycles.
- **E3 (no loss):** total `residualDecodes`(B) ≥ **0.98 ×** the Stage A total on the same cycles, no deadline. **QA measures the Stage A baseline before your first item.**
- An item that misses E2 or E3 is **rejected however fast it is.**

## 3. What you must decide and record (`design.md` D10, before coding)

1. **Test-only visibility of the fitted parameters.** E2 compares Δt, Δf and ḟ, but the shipped fit returns only `out_shat`. You need a **test-only** way to read them (a build of the fit compiled with a test switch, or a test-only export that is **not** in the shipped export list). It must not change the shipped ABI beyond what an item itself needs.
2. The order of the items, from the profile.
3. For B1: which library and licence, and how it is vendored.

## 4. The pitfalls, in order of how much they will hurt

1. **Bit-identity is gone.** Stage A's E1 (hash equality) does not apply to a numerics-changing item. Do not "fix" an E2 miss by loosening anything: report it. Each item is compared against the Stage A fit, not against the previous Stage B item.
2. **Rounding is the whole game.** A faster FFT changes low bits everywhere; B2 and B3 change *which* candidates are examined. The risk is a fit that lands on a slightly different peak and subtracts less energy: that shows up as a fall in `residualDecodes` (E3), not as a crash. Keep the fitted-parameter hook so you can see *which* signals moved.
3. **Do not touch the deadline, the pool, the thread count or the flag** (all Stage A). The hard deadline is what makes T′'s max term safe; do not weaken it.
4. **Licence.** B1 adds a third-party file to the repository. Check the licence text, not the README's claim.
5. **The heap-allocation requirement and its crash history stand.** A new FFT plan or workspace layout goes through the same bounded pool, heap only.
6. **`FT8_SHIM_VERSION`:** verify against `main` (`20260051`), `decoding_improvement` (`20260054`), the base (`20260055`), Stage A (`20260056`) and any live branch; the two-stage branch has **no** shim bump. Do not assume the next integer.
7. **Stage B changes the native decode-adjacent path after the two-stage flag-OFF control.** QA re-runs the control (native **and** managed) on the **final native DLL**; plan for that, do not assume the earlier control covers it.

## 5. Tests and hygiene

- Per item: unit tests for the changed maths against the Stage A fit on fixtures; the concurrency stress test (`Fit_ManyWorkersManyCycles_…`) still green; the existing E1 probe re-purposed to emit the fitted parameters for E2. **Full unfiltered `dotnet test OpenWSFZ.slnx`; quote the exact command and the total.**
- 🔒 **NFR-021 / HK-037:** integers, hashes and stamps only; no message text or callsigns anywhere.
- **HK-011:** you are the separate Developer session; QA and the Architect touch no `src/` or `native/`. **Stage by path, never `git add -A`.** Check `git branch --show-current` before committing.
- Nothing is pushed or merged without the Captain's explicit go (HK-010, HK-033).

## 6. Done means

Per item: the change committed, the DLL SHA pinned (actual and pinned), tests green with the command quoted, the parameter hook working, a short report to QA. **QA then runs E2, E3 and the re-timing (T′; R1′, R3, R4′, R6 at 14 workers; R2′ report-only).** The Architect rules. After the **last** item: QA re-runs the flag-OFF control on the final native DLL, native and managed. **Blind spot:** T′ is measured at 4 workers on a 16-thread machine, one machine, no real cycle above 31 signals; a pass does not say a real 4-thread machine is safe. The flag stays OFF by default; a first on-air flag-ON session needs the Captain's explicit go.
