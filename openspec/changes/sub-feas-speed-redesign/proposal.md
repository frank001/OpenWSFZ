**User-facing:** no

## Why

`sub-feas-native-subtraction` (build `2b39cf18`, shim `20260055`) passed its stability review but **failed its
real-band runtime replay** (§8.1, `qa/rr-study/results/2026-09-29-sub-feas-8-1-replay/report.md`, ruled
`qa/rr-study/2026-09-30-0641-architect-sub-feas-8-1-ruling.md`). Over 905 real busy cycles (three 40 m/direct-CODEC
and Voicemeeter runs), flag ON:

| Row | Bar | Result |
|---|---|---|
| R1 max whole call | ≤ 13 000 ms | **16 309 ms**; 765 / 905 over |
| R2 max / p95 over H | ≤ 10 000 / ≤ 6 000 ms | 16 309 / 14 809 ms |
| R4 deadline-abandon rate over H | flag > 5 % | **531 / 605 = 87.8 %** |
| R3 stability | 0 AV / 0 contained / 0 exits | 0 / 0 / 0 (PASS) |

Two separate defects, neither fixable by moving the budget (Architect's ruling §2):
(a) the residual pass is too slow for a busy cycle: most heavy cycles run **to** the deadline; and
(b) the cooperative guard is not a wall-clock bound: it is checked between phases, so an in-flight native fit
(about 1 s or more) or the residual decode (about 0.5 s) cannot be stopped (worst overshoot +3 309 ms).

On 2026-09-30 the Captain chose to fund a speed redesign: *"go for option 2. more threads, code speedup, remove
redundant monitoring from hot decode path"*. The Architect's static cost map
(`qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §0) finds about **377 complex FFTs of
262 144 points per signal**, about 126 of them pure repeats (the ḟ-independent tone smoothing is recomputed for every
ḟ step), a per-signal workspace and FFT-plan rebuild (about 25 MB `malloc` plus two `kiss_fft_alloc(262144)`), and a
thread cap of 4 on a 16-thread machine (`Ft8Decoder.cs:63`). This change is that redesign, in two stages.

## What Changes

**Stage A: exact changes only (fit output bit-identical to `2b39cf18`). This change builds Stage A.**

- **A1** compute the smoothed tone track once per signal; `r_fit_drift` applies only the ḟ-dependent drift term.
- **A2** transform the Gaussian pulse and the Hann window once per workspace; reuse their spectra.
- **A3** reuse workspaces and FFT plan sets instead of one per signal (heap only; the existing heap-allocation
  requirement and its crash history stand). Mechanism fixed by the Architect's Amendment 1: a **bounded, locked pool**
  of heap workspaces, size = `subtractionMaxThreads`, leased per fit and returned in a `finally`, freed at decoder
  dispose; **no native thread-local state** (`design.md` D2).
- **A4** the fit thread cap becomes config `decoder.subtractionMaxThreads`: **`0` = auto = `max(1, ProcessorCount − 2)`,
  and 0 is also the default**; any other value is clamped to `[1, ProcessorCount]`. Config-file key only; no
  settings-page control. Until the config-save fix (#193) lands, a Settings save resets this key (and the flag) to its
  default, which for this key means auto and for the flag means OFF, so both fail safe.
- **A5** a **hard deadline**: a cancellation flag the native fit checks at every Δt, ḟ and envelope iteration and
  answers with a new return code `-4`; C# sets it at `budget − reserve` (reserve = 1 500 ms for the residual
  decode) and does not start the residual decode with less than the reserve left. Semantics unchanged: a deadline
  abandons the pass and the cycle keeps its pass-0 results.
- **M2** the residual `DecodeAll` runs with its diagnostics off. **M3** guard the Debug-only per-pass log loops
  with `IsEnabled(Debug)`.
- **BREAKING (conditional):** `FT8_SHIM_VERSION` bump; the exported surface changes (A5 adds a parameter and a
  return code, M2 adds a parameter or an export). A binary at the prior version is rejected by the managed ABI
  self-test, as for every shim change in this project.

**Deferred, NOT in this change: M1** (remove the LDPC-fail LLR statistics). The Architect's own precondition fired:
four QA D-001 replay scripts regex-parse the Debug line `LDPC fail stats — failCands= meanAbsLLR= prenormVar=`
(`qa/cycleframer-alignment-replay/ldpc_stats.py`, `.../run_isolated_replay_generic.py`,
`qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py`,
`qa/rr-study/results/2026-07-23-d001-tight-class-replay/run_tight_replay.py`). The Captain was asked on 2026-09-30
and chose **defer**. Consequence: R5′ (flag-OFF cost) is measured with M1 absent, so nothing is credited to it.
Full record in `design.md` D7.

**Stage B (numerics-changing: faster FFT, pruned frequency search, coarse-to-fine Δt) is NOT built here.** It is
built only if Stage A misses R2′ or R4′ at acceptance, item by item, and needs its own gate (`tasks.md` §11).

## Impact

- `native/ft8_lib_vendor/subfeas/subfeas_fit.c` and `.h` (A1, A2, A3, A5), `native/ft8_lib_build/patched/`
  or `src/OpenWSFZ.Ft8/Native/ft8_shim.c/.h` (A5 export shape, M2), build scripts (export list).
- `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs`, `Ft8Decoder.cs`, `Interop/*` (A3 shutdown hook, A4, A5, M2, M3).
- Config: `decoder.subtractionMaxThreads` (new optional key) and its `REQUIREMENTS.md` entry.
- Tests under `tests/OpenWSFZ.Ft8.Tests/` and a test-only E1 hash probe. Every test fake implementing
  `IFt8NativeInterop` is touched, because A5 changes `SubfeasFitSignal` (12 fakes plus `SubtractionFlagTests`,
  `SubtractionLogLineTests`, `SubtractionPassTests`; verified by grep on `2b39cf18`).
- `FT8_SHIM_VERSION` and the `libft8.version.txt` entries per the project's standard shim-change convention.

## Claims NOT made

- **No decode-rate claim, and no live use.** The flag stays **OFF** by default and in every live run. Stage A is
  bit-identical by construction, so it cannot change what is decoded; it can only change how long it takes.
- **§7 (stability gate) and §8.2 (independent real corpus) of the base change stay open.**
- **Hardware coverage is not claimed.** Runtime acceptance is one machine (Ryzen 7 7800X3D, 16 threads). A4's
  default scales with `ProcessorCount`, so a 4-thread machine gets 2 fit threads, and nothing here says it meets
  13 s.
- **Blind spot (HK-026):** no real cycle in the corpus has more than 32 pass-0 signals. A PASS means "up to 32 real
  signals on this machine".
- CPU-specific builds (`/arch:AVX2`, `/fp:fast`) are out of scope: they would make the DLL CPU-specific or change
  numerics. A separate decision.

## Dependency

Builds on `feat/sub-feas-native-subtraction` (`ab95bea1`, code `2b39cf18`), which is **not yet merged to `main`**. This
change adds requirements only and modifies none, so it validates independently, but it cannot merge before the base
change does.
