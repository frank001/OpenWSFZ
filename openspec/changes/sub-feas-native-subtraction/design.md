## Context

Three prior native subtraction attempts were reverted (2026-06): `fix-d001-pcm-sic` (CP-FSK synthesis,
fixed phase-zero) caused two independent production `0xC0000005` crashes and zero accuracy gain — the
first crash from a 703 KB stack allocation in a P/Invoke target, the **second surviving a stack→heap
fix**, meaning heap allocation alone did not root-cause it; `diag-d001-h3b-gfsk-sic` (GFSK quadrature,
still fixed-phase) drove the fit amplitude to ≈0 on a modulation/phase model mismatch, no crash, no
gain. `openspec/specs/iterative-subtraction/spec.md` already carries the scars of that history: a
heap-allocation-only requirement and an Option C PoC approval gate.

`SUB-FEAS` (`qa/sub-feas`, 2026-09-27–28) validated a categorically different method — a **data-aided
fit**: each already-decoded signal's true position, linear frequency drift, and a *time-varying*
complex amplitude envelope are fit directly against the real recorded audio (not synthesised from an
assumed phase/amplitude model). Stage 2 measured this method's actual payoff on real off-air audio:
net +8.89 pp [8.01, 9.75] WSJT-X-corroborated new decodes, after a replay-vs-live control. The Captain
authorised a scoped, flag-gated native build of exactly this method (`qa/rr-study/2026-09-28-1601-…`),
explicitly choosing to run the Architect's recommended second-corpus/runtime-bar acceptance check
*after* the build exists rather than before it.

This design ports the validated Python implementation (`qa/rr-study/sub-feas/fitter.py`,
`stage2.py`) to native code. It does not re-derive the algorithm — the algorithm is settled; the open
questions here are implementation placement, memory safety, and how the still-unmeasured runtime cost
is gated before this can ever run live.

## Goals / Non-Goals

**Goals:**
- Implement the exact validated algorithm (§ Decision 1) as an additive residual-decode pass, flag-gated,
  default OFF, with existing decode behaviour byte-identical when the flag is OFF.
- Extend the existing heap-allocation-only requirement to every new buffer this method needs, and add a
  stability/stress gate independent of decode-rate accuracy — the first attempt's crashes were never
  caught by a decode-rate corpus.
- Produce, as a build-time deliverable, the runtime and second-corpus measurements the Architect's
  original acceptance sequencing called for — resequenced to run against this build, not before it.

**Non-Goals:**
- Redesigning or tuning the fit algorithm itself. `τ0`, `W*`, the drift/frequency search ranges, and the
  envelope window are inherited constants from the validated measurement (§ Decision 1) — this change
  ports them, it does not re-optimise them.
- Any change to `K_MAX_PASSES` or the existing spectrogram-domain soft-SNR suppression mechanism
  (a *different* two-pass mechanism inside a single `ft8_decode_all` call — see § Decision 5).
- Multi-pass subtraction (subtract, decode, subtract again). The validated method is exactly one
  residual pass; the Architect's own stated limit ("one pass only. Multi-pass is untested, in either
  direction") is preserved as a limit, not silently extended.
- Reaching a live A/B endurance run. That is explicitly the step *after* this change's own acceptance
  gates (`tasks.md`), not part of it.

## Decisions

### Decision 1 — Port the validated algorithm exactly, parameters included

**Chosen:** implement, in whichever language boundary § Decision 2 settles on, precisely the method
measured in Stage 2:

1. Run the existing decode pipeline unmodified ("pass 0").
2. For every pass-0 decoded message that re-encodes cleanly (not a `<...>` placeholder, ≥3 tokens —
   `stage2.py:_is_reencodable`), fit against the **original** analytic PCM (Hilbert transform of the
   real buffer):
   - Nominal position `nominal_t = decoded_dt + τ0`, `τ0 = −0.1600 s` (inherited constant).
   - Coarse-to-fine search, `fitter.py:fine_fit_with_drift`:
     1. `(Δt, Δf)` at `ḟ=0`: `Δt` grid ±100 ms @ 1 ms steps (integer-sample, no interpolation), `Δf`
        via FFT-argmax restricted to ±2 Hz, `n_fft = 262144`.
     2. `ḟ` search over `[−0.10, +0.10] Hz/s` @ `0.005 Hz/s` steps, `Δt` held at step 1's value, `Δf`
        re-fit at each `ḟ` candidate.
     3. `Δt` refined once more over the same ±100 ms grid, `(ḟ, Δf)` held, scored by direct correlation
        (no further FFT).
   - Time-varying complex envelope `c(t)`: Hann-windowed moving average of
     `(segment · conj(template)) / |template|²`, window width `W* = 0.32 s` (`fitter.py:lp_envelope`).
     **`W ≥` the full 12.64 s transmission must still be a supported, correctly-computed degenerate
     case** (single complex scalar for the whole transmission) — that degenerate case is the old,
     inadequate June model; the general windowed implementation must not silently collapse to only ever
     computing it.
   - `s_hat(t) = Re{c(t) · template(t)}`; subtract from **a copy** of the original buffer at that
     signal's fitted position.
3. Accumulate **every** fitted signal's subtraction into **one** residual buffer (batch, not
   sequential — no signal's fit depends on another signal already having been subtracted; this is not
   iterative SIC).
4. Run the existing decode pipeline **a second time, unmodified**, on the residual buffer.
5. Merge: a residual-pass decode is reported only if its **payload** (bit-level) does not match any
   pass-0 decode from the same cycle. Payload comparison must handle the RR73 on-air-sentinel vs
   re-encoded-text-sentinel asymmetry exactly as `stage2.py`'s `_same_qso`/`v_star` handling does — a
   naive text-based or single-sentinel comparison will silently miss or double-count genuine on-air
   `RR73` reports (this exact asymmetry was a defect QA caught and fixed in the *offline measurement
   harness itself* before trusting Stage 2's numbers; it applies with equal force to the native merge
   logic).

**Rationale:** this is the one method, among four attempts, actually shown to work on real audio. Every
prior failure traces to either a wrong signal model (fixed phase, wrong modulation) or a memory-safety
bug unrelated to the algorithm. Reimplementing "the idea" instead of porting the exact validated
parameters would reopen exactly the risk SUB-FEAS was run to close.

**Alternative considered:** re-derive or simplify the search grid for native performance (e.g. coarser
`Δt`/`ḟ` steps, smaller `n_fft`) before validating that the coarser version still delivers the measured
gain. Rejected for this change — performance tuning against an *unvalidated* variant would silently
reopen the algorithm question this proposal exists to close. If runtime (§ Risks) makes the exact port
infeasible, that is a finding to bring back to QA/Architect, not a silent substitution.

### Decision 2 — Where the fit/subtract logic lives: native C, recommended but not mandated here

**Recommended:** implement the fit/subtract/merge pipeline in `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (or
a new, separately-compiled native source file linked into the same shim), operating directly on the PCM
buffer already resident in native memory — not reconstructing it at the C# `Ft8Decoder` boundary.

**Rationale for the recommendation:** the per-signal fit costs ~3.9 s in Python/numpy, dominated by
~242 FFT calls at `n_fft=262144`. A cycle with ~24 signals is therefore the primary runtime risk (§
Risks). Native FFT (§ Decision 3) inside the same process as the existing decode pipeline avoids a
second P/Invoke round-trip per signal and avoids marshalling ~180,000-sample PCM buffers across the
boundary twice per cycle. C# doing FFT-heavy numeric work at this volume is very unlikely to meet the
budget.

**This is not settled here.** The historical crashes happened *at* the P/Invoke boundary — that
argues for keeping the fit/subtract loop entirely native (fewer boundary crossings, not more), but it
also means this is exactly the code that most needs careful buffer-ownership design (§ Decision 4). Per
this project's own precedent for exactly this kind of choice
(`DEV-BRIEFING-iterative-subtraction.md` §4, "Architectural paths — decision required"), the Developer
session implementing this **must record the final placement decision and its rationale** in a short
addendum to this file before writing the fit loop itself — not silently follow this recommendation
without confirming it still holds once real profiling numbers exist, and not silently deviate from it
without saying why.

**Alternative considered:** C# at the `Ft8Decoder` wrapper boundary (reconstruct via P/Invoke calls per
signal, subtract in managed memory, call the existing native decode entry point again on the modified
buffer). Rejected as the default because of the runtime cost above, but not eliminated — if native FFT
licensing or build complexity (§ Decision 3) proves harder than expected, this remains a fallback, at a
known performance cost that must then be measured, not assumed.

### Decision 3 — FFT library: permissive licence only, not FFTW

**Chosen:** any native FFT implementation added for this change SHALL be permissively licensed
(MIT/BSD/ISC), per the project's standing licence policy — the repository is AGPL-3.0 and does not take
on GPL dependencies. **FFTW is explicitly excluded**: it is GPL-licensed (commercial licence available,
not applicable here) and would violate that policy if reached for by default because it is the most
commonly recommended C FFT library. A permissively-licensed alternative (e.g. KissFFT, BSD-3-Clause;
PocketFFT, BSD-3-Clause) must be selected and the choice recorded, with the licence file checked into
`native/` alongside the existing bundled dependencies' own licence files, matching this repo's existing
convention for `ft8_lib` itself.

**Rationale:** this is a compliance requirement, not a performance one — it was not part of SUB-FEAS's
own offline measurement (Python used `scipy.signal`/`numpy.fft`, whose own licensing is not this
project's concern once nothing from `scipy`/`numpy` ships in the native binary), and would be an easy
thing to get wrong by default if a Developer reaches for the most familiar C FFT library without
checking.

**Alternative considered:** hand-rolled radix-2 FFT, avoiding a new dependency entirely. Not rejected,
but not chosen here — `n_fft=262144` is a moderate size where a well-tested library likely outperforms
a fresh hand-rolled implementation, and correctness bugs in a hand-rolled FFT are exactly the kind of
defect a stress gate (§ Risks) would need to catch the hard way. Left as an option if the licensing path
proves difficult.

### Decision 4 — Every new buffer is heap-allocated, with graceful degradation, extending the existing requirement

**Chosen:** `openspec/specs/iterative-subtraction/spec.md`'s existing "Any PCM residual buffer SHALL use
heap allocation, not stack allocation" requirement (from `fix-d001-revised`, written after the P/Invoke
stack-overflow crash) extends, verbatim in spirit, to every new buffer this method introduces:

- The residual PCM buffer (`720,000` bytes, `FT8_EXPECTED_SAMPLES * sizeof(float)` — same size the
  existing requirement already names).
- Per-signal complex templates (`151,680` samples × 16 bytes ≈ 2.4 MB **each** — two orders of
  magnitude over the existing 100 KB stack-allocation threshold; a busy cycle with ~24 signals needs
  either ~58 MB resident simultaneously or a bounded pool reused per signal — a memory-budgeting
  decision for the Developer to make explicitly, not default to "allocate all of them").
- FFT working buffers (size `n_fft = 262144` complex or real, per call).
- The envelope arrays (`lp_envelope`'s convolution output, same length as the segment).

All of the above: `malloc`/`free` (or an explicit pool with the same non-stack property), never a stack
array, in any function reachable from a .NET thread pool thread via P/Invoke. On any allocation failure,
**fall back to the single-pass (no-subtraction) result for that cycle and log it** — do not crash, and
do not silently skip only the failed signal while leaving partial state (matching the existing spec's
own "Allocation failure is handled gracefully" scenario, extended to this larger set of buffers).

**Rationale:** the second historical crash happened *after* the first fix (stack → heap) was applied —
meaning the original root-cause analysis was incomplete. This design does not assume "heap allocation"
by itself is sufficient; it also requires the graceful-degradation path to be real and tested (§
tasks.md's stability gate), not just declared.

### Decision 5 — Name and gate the new pass distinctly from `K_MAX_PASSES`

**Chosen:** the residual-decode pass introduced here is exposed as a **separate, explicitly-named**
mechanism — e.g. a new function (`ft8_decode_all_with_subtraction`) or a boolean parameter on the
existing entry point — never a `K_MAX_PASSES` increment. `K_MAX_PASSES` (currently 2) governs the
*existing*, unrelated spectrogram-domain soft-SNR candidate-search mechanism
(`iterative-subtraction/spec.md`'s "Two-pass decode structure" requirement); this change's residual pass
runs the **entire** existing two-pass pipeline a second time, over different audio, not a third internal
candidate-search iteration. `diag-d001-three-pass-sic` (`K_MAX_PASSES` 2→3, reverted, −4.30 pp) already
tested and rejected the "just add a pass" idea in the *wrong* mechanism; this design must not be
mistaken for a repeat of that, in code, in logs, or in the spec delta's own wording.

**Rationale:** the terminology collision is a real hazard — both are colloquially "a second pass" over
FT8 decoding. Distinct names prevent a future reader (or a future diagnostic experiment) from
conflating an orthogonal, already-closed question with this one.

### Decision 6 — Config flag, default OFF, decoder-settings convention

**Chosen:** a new boolean field on the existing decoder-settings config surface
(`openspec/changes/archive/2026-07-02-decoder-settings-page/` convention), default `false`. With the
flag `false`, pass 0 runs exactly as today and the residual pass is not attempted — decode output SHALL
be byte-identical to pre-change behaviour. The Developer selects the field's exact name and location
following that existing page's established pattern rather than introducing a new config subsystem.

## Risks / Trade-offs

- **[Runtime infeasibility]** — the validated Python fit costs ~3.9 s/signal; ~24 signals/cycle is
  ~90+ s of Python-equivalent work against a 13 s hard / 30 s CI budget. **Not resolved by this
  design** — it is the primary reason `tasks.md` requires a measured native runtime-per-cycle result as
  a build-time gate, with the flag remaining OFF by default regardless of outcome until that gate is
  read. → *Mitigation:* profile early (first working native fit, before full integration), and treat a
  failing runtime result as a valid, reportable outcome (a FAIL, not a defect to hide) — mirroring how
  Stage 1's own FAIL was treated as a real, useful result rather than something to route around.
- **[Repeat of the crash history]** → *Mitigation:* Decision 4 (heap-only, graceful degradation) plus a
  stability/stress gate independent of decode-rate accuracy (`tasks.md`) — the first attempt's crashes
  were never visible to a decode-rate corpus.
- **[Single-corpus overfit]** — Stage 2 measured one 40m night. → *Mitigation:* `tasks.md`'s
  second-corpus acceptance gate, run after this build exists, before any live A/B — the Architect's
  original recommendation, resequenced not dropped.
- **[FFT licence]** → *Mitigation:* Decision 3, permissive-only, explicitly excluding FFTW.
- **[Per-signal buffer memory pressure at high signal density]** — a very busy cycle (dense band
  conditions) could carry more than the ~24-signal figure used in this design's estimates. →
  *Mitigation:* the Developer's buffer-pooling decision (Decision 4) should have an explicit, named,
  bounded cap on concurrently-allocated per-signal buffers, not an unbounded allocation per decoded
  signal — this is exactly the shape of unbounded-growth defect this project's standing rules
  (candidate-budget family, hash-table sizing) have repeatedly had to close elsewhere.

## Migration Plan

Purely additive and flag-gated (default OFF) — no migration of existing data or config. Rollback is
setting the flag back to OFF (or reverting the shim to the prior `FT8_SHIM_VERSION` if a defect is found
post-merge, matching this project's existing revert convention for shim changes).

## Open Questions

- **Final placement (Decision 2):** native-C loop vs C# boundary — recommended native, but the
  Developer must record the confirmed decision and rationale before implementation, per Decision 2.
- **Per-signal buffer pooling strategy and its cap (Decision 4):** bounded pool size vs per-call
  allocation — a memory/latency trade-off the Developer should measure, not assume.
- **Exact next `FT8_SHIM_VERSION` integer:** current pins are `main`=`20260051`,
  `decoding_improvement`=`20260054`; the board also records an open, unexecuted renumbering
  recommendation for collisions among other unmerged branches (`dev-tasks/2026-09-03-shim-version-renumber-rc1rc2-and-rc4-branches.md`).
  **Check the current state of that renumbering item and every live branch's pin before picking a
  literal** — do not assume `20260055` is free without checking, the exact mistake that item exists to
  prevent.
- **FFT library selection (Decision 3):** KissFFT vs PocketFFT vs another permissively-licensed option —
  left to the Developer, constrained only by the licence requirement.

## Addendum — Decision 2 confirmed (Task 1.1)

**Confirmed 2026-09-28, by the Captain, presented with this design's recommendation and rationale
unchanged:** the fit/subtract/merge pipeline lives in native C — `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
or a new, separately-compiled native source file linked into the same shim, operating directly on the
PCM buffer already resident in native memory. The C# `Ft8Decoder`-boundary alternative is not taken.

No new information changed the recommendation's basis — this is the Captain's explicit choice to
accept the runtime-performance case over the P/Invoke-boundary caution, not a re-derivation. The
buffer-ownership care Decision 2 called for (§ Decision 4: heap-only, bounded pooling, graceful
degradation) is unchanged in importance by this confirmation and remains a hard blocker (`tasks.md`
§3), precisely because the loop now living in native C is the scenario Decision 2 itself flagged as
needing it most.

## Addendum — Decision 3 confirmed (Task 1.2), and an early runtime-feasibility finding

**Confirmed 2026-09-28: KissFFT.** Before benchmarking, a codebase check found a fact this design
did not have: **KissFFT is already vendored and linked into `libft8.dll` today**
(`native/ft8_lib_vendor/fft/kiss_fft.c`/`kiss_fftr.c`, compiled by `rebuild_shim.bat` on the exact
MSVC/`std:c11` toolchain this change builds with, already exercised by the existing STFT waterfall
at `nfft` up to ~8192). It is dual-covered: the umbrella `ft8_lib` port is MIT (Kārlis Goba,
`native/ft8_lib_vendor/LICENSE`), and `kissfft` itself carries its own `SPDX-License-Identifier:
BSD-3-Clause` header in each file (Mark Borgerding) — no separate `COPYING` text file exists for it
today, a pre-existing gap (predates this change) worth a one-line fix in passing, not a blocker.

A head-to-head benchmark was still run, per the Captain's request, rather than deciding on the
"already vendored" fact alone:

| Library | Per-call (n_fft=262144, single-threaded, MSVC `/O2`) | 242-call/signal estimate | 24-signal/cycle estimate |
|---|---|---|---|
| KissFFT (`kiss_fftr`, real-to-complex) | **2.41 ms** | 0.58 s | **13.98 s** |
| PocketFFT (`pocketfft_hdronly.h` r2c, `nthreads=1`) | 2.57 ms | 0.62 s | 14.93 s |

Methodology: real upstream sources — `kiss_fft.c`/`kiss_fftr.c` from this repo's own vendor tree
(unmodified), `pocketfft_hdronly.h` fetched verbatim from
`https://raw.githubusercontent.com/mreineck/pocketfft/cpp/pocketfft_hdronly.h` — compiled with the
same `cl /O2` (KissFFT: `/std:c11`, matching this repo's convention; PocketFFT is C++-header-only, so
`/std:c++17` — see risk note below) on this machine's MSVC 19.44 toolchain, 242 repeated forward
real-FFT calls at `n_fft=262144` after one warm-up call, timed with `QueryPerformanceCounter`.
Correctness sanity check (DC bin == sum of input) passed for both, matching to 6 decimal places.
Scratch harness and both vendored/fetched sources are in a session scratchpad, not the repo.

**KissFFT measured ~6.5% faster than PocketFFT in this single-threaded configuration on this exact
toolchain** — the opposite of PocketFFT's general reputation, plausibly because MSVC vectorises
PocketFFT's template-heavy C++ less aggressively than GCC/Clang would, or because KissFFT's
split-radix path is already well-suited to this power-of-two size. Combined with zero incremental
vendoring/licensing/build-system cost (PocketFFT's only current well-maintained form is a C++
header-only library — pulling it in means adding a C++ compilation unit and linking the C++ runtime
into a native shim that has been pure C throughout its history, a real toolchain-complexity increase
for a change whose stability gate is already a hard blocker), **KissFFT is confirmed with no
remaining ambiguity.**

**🔴 Early runtime-feasibility finding, surfaced per this design's own Risks-section instruction to
"profile early... and treat a failing runtime result as a valid, reportable outcome":** even using
the faster of the two libraries, **FFT time alone for a 24-signal cycle is ~14.0 s — already at or
past the existing 13 s hard decode-cycle budget, before any of the following are counted**: the
non-FFT fit work (envelope computation, correlation refinement, template synthesis, subtraction), the
additional Hilbert-transform FFT per signal the analytic-PCM step needs, the .NET/native P/Invoke
overhead, and — the largest omitted cost — **running the entire existing decode pipeline a second,
unmodified time on the residual buffer** (§ Decision 1 step 4), which is not a fit-loop cost at all
and is not measured by this benchmark.

This is exactly the scenario `design.md`'s own "Alternative considered" note under Decision 1
anticipates: *"If runtime... makes the exact port infeasible, that is a finding to bring back to
QA/Architect, not a silent substitution."* This FFT-only proxy is not itself that finding — task 8.1's
real, full-pipeline measurement is — but it is a strong enough early signal that continuing straight
into the full §2 algorithm port without flagging it first would risk sinking further implementation
time into search-grid parameters (the `ḟ` sweep in particular: 41 steps × a re-fit each, per signal)
that may need to be revisited on cost grounds regardless of code quality. Recorded here rather than
silently proceeding; raised to QA/the Captain alongside this addendum.
