# Developer handoff: SUB-FEAS Stage B item B2 — a pruned `freq_search` in the native fit

**Date:** 2026-10-03. **From:** QA. **To:** Developer. **Priority:** high (the Captain asked for it). **Spec (Architect, Captain "yes, proceed", 2026-10-03):**
`qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §5h (Amendment 5), on the Architect's local branch `arch/sub-feas-stage-b`, commit `7f544638`
(read it with `git show arch/sub-feas-stage-b:<path>`; it reaches `main` when QA pushes it, with the Captain's go).
**OpenSpec:** change `sub-feas-speed-redesign`, `tasks.md` §15 (15.3, 15.4, 15.9 to 15.11), `design.md` D11, requirement "Stage B SHALL be built one item at a time, B2 first…" (this branch: `qa/stage-b-amendment5`).

## 0. 🔴 Hold: no build and no test suite until the Engineer says done

The Engineer's #122 gate 4a run (started 2026-10-03 11:39:10Z, about 3 h, expected to end about 14:40Z) **measures decode wall-time**. **Do not run `dotnet build`, `dotnet test`, a native rebuild, a benchmark or any extra daemon until the Engineer (or QA) messages "done"**, unless the Captain relaxes the rule. Reading code, planning, and **writing** code and documents is fine and encouraged: it uses almost no CPU. Check the clock with `date -u`, not from memory.

## 1. Context

Stage B is re-aimed at **batch 2's arrival time**: can a batch-2 decode get a same-slot reply? The 2026-09-30 on-air night measured T2 p50 5.71 s (decode start 0.03 s + batch 1 about 0.53 s + residual pass about 5.0 s). The fit profile (`feat/sub-feas-stage-b` `ef7e765c`, `artefacts/sub_feas_fitprofile/`, 5 cycles, 111 fits) says a fit costs a median **1 561 ms at 1 worker and 1 904 ms at 8**, of which **step 1 (the Δt search) is 71 %** and **step 2 (the ḟ search) 25 %**. Step 1 runs `freq_search` 201 times per signal, each a full 262 144-point FFT of which only about ±44 bins are used.

**B2 is the first item:** prune `freq_search`. If B2 alone does not reach the bar (median `T2_replay` ≤ 2.50 s, QA measures it), B3 (coarse-to-fine Δt) and then B1 (a faster FFT, pocketfft-C only) are separate handoffs later. **This handoff is B2 only.**

## 2. Branch

`feat/sub-feas-stage-b` (exists; native source is identical to `main`'s at `git diff --stat origin/main feat/sub-feas-stage-b -- native`, `src/` is not). NEVER commit to `main`.

**First action: bring the branch up to date.** At the time of writing it is **100 commits behind and 25 ahead of `origin/main`** (merge-base `08222591`); `src/` differs in 7 files (`ConfigOverlay.cs`, `WebApp.cs`, …) because `main` has since gained default-ON, the config overlay and other work. Merge `origin/main` into it (a merge, not a rebase; resolve conflicts by reading both sides; **never take one side of a binary conflict**), build once, and confirm `git diff --stat origin/main -- native` shows only what you changed. The same-session Stage A baseline is the **current `main` build**, so the branch must contain `main`'s managed code.

## 3. Actions

1. **Record the design choice in `design.md` D11 before coding** (the OpenSpec file on `qa/stage-b-amendment5`, or a note in your report if that branch has not merged): how `freq_search` is pruned. The spec names "decimation plus a small FFT, or a pruned DFT". Constraints, whatever you choose:
   - Only bins with |f| ≤ `SUBFEAS_DF_RANGE_HZ` (2.0 Hz; bin spacing `FS / N_FFT` = 0.0458 Hz) may influence the result.
   - State the argmax tie-break. Today's code (`native/ft8_lib_vendor/subfeas/subfeas_fit.c:361-394`) scans bins in index order (0 to N/2−1, then N/2 to N−1, i.e. the negative frequencies from −Nyquist to −1 bin) and keeps the **first strictly greater** magnitude.
   - If the new method interpolates or lands between bins, say so; E2 still judges it at ±1 bin (§5).
2. **Implement the pruned search** in `subfeas_fit.c`, called from step 1 (`:443`, 201 candidates) and step 2 (`:474`, each ḟ step). Keep the function signature, `cancel_flag` handling (A5) and workspace ownership rules as they are (the workspace pool is heap-only and bounded, design D2: read it before touching `ws->scratch_search` or `ws->fwd`). Do not change anything outside the fit's numerics.
3. **Test-only visibility of the fitted parameters** (tasks 15.3, needed for E2): QA must be able to read Δt, Δf and ḟ per fitted signal from the Stage A DLL **and** the B2 DLL. Record the mechanism in D11 first. It must not add to the **shipped** export list or change the shipped ABI beyond what B2 itself needs (a compile-time test switch, or a test-only build of the fit, are acceptable). Tell QA how to call it.
4. **Unit tests** (in `tests/`, no product-path change): on synthetic inputs (a known tone at a known offset, plus noise at a fixed seed), the pruned search returns the **same bin as the reference full-FFT search** for offsets across the full ±2.0 Hz range including both edges and 0, and the same result when two bins are within one magnitude step (the tie-break). Add the cancel-flag case (a set flag returns promptly).
5. **Shim bump.** One **new** `FT8_SHIM_VERSION`: take the next free number above **every number used or reserved on any live ref** (`git grep` over `origin/*`). At the time of writing **20260057 is reserved by the DI sync** (`dev-tasks/2026-10-01-sync-decoding-improvement-with-main.md`), so expect **20260058**; verify, do not assume. Set it **everywhere it lives**: `ft8_shim.h`, `Ft8LibInterop.cs` (`ExpectedShimVersion`), `win-x64/libft8.version.txt`, `BUILD.md`, `rebuild_shim.bat` header text, `openspec/specs/ft8lib-interop/spec.md`, and any ABI-sentinel test constant. (Procedure as in the Stage A bump: tasks §9.)
6. **Rebuild the native binaries from source.** Windows: `native/ft8_lib_build/rebuild_shim.bat` (see `BUILD.md`); record the new `libft8.dll` **SHA-256**. Linux: `native/ft8_lib_build/build_linux.sh` (WSL Debian; it also compiles `subfeas_fit.c`), commit the `.so`. macOS: CI rebuilds the dylib; leave the committed `.dylib` to the CI "Commit rebuilt native binaries" step and say so. Run `python tools/check_native_version.py <binary> <new number>` for each binary you built and quote the output.
7. **Fit timing probe** (after the hold lifts): run `Ft8.FitProbe fitprofile` on the B2 DLL at **1 and at 8 workers**, and report the median per fit and the step-1 and step-2 shares. Integers only (HK-037). This is a developer's sanity check; **it is not the acceptance measurement** (QA's T2′ replay is).
8. **Full unfiltered `dotnet test`** once the hold lifts (quote the exact command and the pass/fail/skip counts: a filtered-out suite is silent, not green, HK-022).

## 4. Out of scope (do not touch)

B3 (coarse-to-fine Δt) and B1 (a faster FFT) — separate handoffs, only if the bar is still missed. The flag default, the thread default, the two-stage publish, the QSO controllers and anything in `src/` that is not needed for the shim constant or the test hook. The batch-2 → auto-QSO choice stays the Captain's and the automation stays fenced from batch 2.

## 5. Acceptance criteria (what QA checks; the rows are the spec's)

QA owns the measurements. In this order, any miss rejects B2 however fast it is:

| Row | Predicate |
|---|---|
| **E2 — equivalence** | per fitted signal, B2 vs the Stage A DLL, with no deadline, on the E1 cycles (the 60 pilot cycles plus every 9th stamp of H ∪ M, about 100 cycles): Δt identical ±1 step (12 samples), Δf within ±1 bin (0.0458 Hz), ḟ the same step, on **≥ 99 %** of signals; per-cycle residual energy within ±0.1 dB on ≥ 99 % of cycles |
| **E3 — no loss** | on the same cycles, with no deadline: total `residualDecodes`(B2) ≥ **0.98 ×** the Stage A baseline (QA measures it first, tasks 15.2(a)). SUB-FEAS's value is its extra decodes; a faster fit that loses them buys nothing |
| R1′ | max whole-call elapsed ≤ 13 000 ms |
| R3 | 0 access violations, 0 contained faults, 0 exits |
| **R4′** | deadline-abandon rate ≤ 5 %, read **at 8 workers on the T2′ list** |
| **T2′ — the bar** | on a replay of the 2026-09-30 night (flag ON, `subtractionMaxThreads` = 8, `nhard` 40, `replay81` mode `two1`, every 4th cycle of the frozen 10-01 selection), **median `T2_replay` ≤ 2.50 s**, with a same-session Stage A baseline |

T′ (4 workers) is report-only. A replay PASS makes **no on-air claim**.

**Review checks QA will make beyond the rows:** the shim literal is identical everywhere in the list in action 5; the DLL SHA-256 in `libft8.version.txt` matches the file; `git diff --stat origin/main -- native` contains only B2 and the shim; no new export in the shipped list; the unit tests would **fail** on a deliberately broken pruning (QA will mutate the bin range to check); `LicenseInventoryCheck` is untouched (B2 adds no library).

## 6. Report back (in this order)

1. The design choice (D11) and the tie-break. 2. The branch state after the merge (commit hashes, conflicts and how each was resolved). 3. The shim number and **every** file changed for it. 4. `libft8.dll` SHA-256 (actual) and the `check_native_version.py` output. 5. The unit-test list and the exact `dotnet test` line with counts. 6. The fit probe at 1 and 8 workers, before and after, integers only. 7. How QA calls the test-only parameter dump. 8. Anything you could not do, said plainly.

*(`tools/pre_merge_check.py` is QA's review-step gate, not part of your checklist, HK-006.)*

## 7. References

Architect's spec §5h and its predictions SB1 to SB4 (SB1: B2 passes E2 and E3 on its first build, P 0.60; SB2: median `T2_replay` ≤ 2.50 s after B2 alone, P 0.40; SB3: per-fit median at 8 workers ≤ 700 ms after B2, P 0.50); fit profile `artefacts/sub_feas_fitprofile/`; `native/ft8_lib_vendor/subfeas/subfeas_fit.c`; OpenSpec `sub-feas-speed-redesign` §15 and D10, D11; the companion keying-latency spec (`qa/rr-study/2026-10-03-1235-architect-to-qa-spec-keying-latency.md`), which measures the margin T2′ leaves.
