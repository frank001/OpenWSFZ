## Context

The decoder's candidate search (`ftx_find_candidates()`) returns a coarse `(freq_hz, time_offset)`
quantised to the waterfall lattice — **3.125 Hz / 0.08 s** — and extraction proceeds directly from
that quantised point. There is no refinement stage anywhere in the pipeline: the waterfall stores
`uint8_t` magnitude only (`decode.h:21`), `WATERFALL_USE_PHASE` is commented out with zero
`#ifdef` branches wired to it in `decode.c`, and `ft8_decode_multi_symbols()` (`decode.c:1059`) is
both dead code and wrong if it were ever revived (`WF_ELEM_MAG(a) + WF_ELEM_MAG(b)` adds dB
magnitudes rather than coherently summing complex values). WSJT-X achieves ≈0.5 Hz / 5 ms via a
downconvert → coherent-Costas-correlate → refine pipeline (`ft8_downsample` → `sync8d` → refined
`ft8b` extraction); this design reimplements that *method*, never its code (binding Captain's
ruling, 2026-08-11 — see proposal.md Impact).

This is a **build-with-acceptance-criteria** change, not a measurement arm: the six ACs decide
ship/fix/stop, not a pre-registered ROW. The reason this is its own change rather than folded into
R2 is the interpretability hazard named in the proposal — an unvalidated refiner wired into the
decode path makes a flat R2 result ambiguous between "refinement doesn't help" and "our refiner is
broken." This design's entire job is to remove that ambiguity before R2 ever runs.

R0 (native build reproducibility) merged to `main` 2026-08-14 (`f164123`, DLL SHA256 `897f81dd…`,
shim `20260039`) and is this change's dependency and baseline.

## Goals / Non-Goals

**Goals:**
- Build a per-candidate refinement stage that, given a coarse candidate and the cycle's retained
  PCM, returns a refined `(Δf, Δt)` and a sync quality score, using coherent (complex, phase-
  retaining) correlation against the three Costas 7×7 arrays.
- Validate it against a synthetic oracle (`qa/rr-study/synth/`) with truth known by construction,
  across a pre-registered grid of frequency offset, time offset, and SNR, evaluated against six
  mechanical acceptance criteria (proposal's What Changes / spec's Requirements).
- Leave every existing production decode behaviour — `DecodeAll`, `GetLastPassCounts`,
  `SetDecodeParams`, and all `ft8-decoder` scenarios — byte-for-byte unchanged.

**Non-Goals:**
- Not wiring the refiner into `ftx_decode_candidate()` or any production decode call. That is R2's
  scope entirely; if achieving AC-1 appears to require touching the production path, this change
  stops and escalates rather than reaching into R2's territory to make its own bar.
- Not measuring recovery or false-positive rate against the real corpus. Those are R2 outputs; this
  change's oracle is encoder-only and the decoder side is never involved.
- Not `K_FREQ_OSR`/`K_TIME_OSR` 2→4 (barred on P3's evidence, superseded by this approach anyway —
  refinement scales with candidate count, OSR 4 scales with the whole waterfall for a worse result).
- Not subtract-and-resynthesise (`subtractft8`) in any form — DEAD, three builds, three reverts,
  standing prohibition.
- Not pre-committing R3 (coherent multi-symbol LLRs) — its inputs don't exist until this change and
  R2 both report.

## Decisions

**D1 — Diagnostic export only; `ftx_decode_candidate()` is not touched.**
The refiner is reached exclusively through a new native export (e.g. `ft8_refine_candidate`),
callable from the validation harness, with no call site anywhere in the production decode path.
Alternative considered: wire it in behind a runtime flag defaulted off. Rejected — a flag that
exists but defaults off is still a change to the production call graph and a future accidental
flip; a genuinely separate export makes "R1 cannot touch a production decode" mechanically true
rather than configuration-dependent.

**D2 — Coherent correlation (sum complex, then magnitude), explicitly not the
`ft8_decode_multi_symbols()` shape.** That existing dead code adds per-symbol dB magnitudes, which
is incoherent and would defeat the entire point of retaining phase. The refiner sums the complex
baseband samples against each Costas reference symbol-by-symbol first, and takes the magnitude of
the sum last. This is stated explicitly in code review criteria for the Developer session because
the wrong-but-plausible shape already exists in the tree as something a Developer could reach for
by pattern-matching nearby code.

**D3 — Baseband rate ~200 Hz and WSJT-X's ±2.5 Hz / ±4-sample search ranges are a *starting point*
tuned by AC-1, not a hard requirement.** Alternative considered: pin the exact WSJT-X ranges as a
requirement. Rejected — the acceptance criteria (RMS/bias/noise-null/monotonicity) are the actual
contract; the search ranges are free parameters a Developer session may need to widen or narrow to
hit AC-1 without copying WSJT-X's tuning blindly. What is fixed is the *method* (coherent Costas
correlation, phase retained, three-stage coarse/fine search), not its numeric constants.

**D4 — Acceptance bars are derived from the lattice being replaced, not from any prediction.**
Baseline quantisation RMS is `3.125/√12 = 0.902 Hz` and `0.08/√12 = 0.0231 s` (uniform distribution
over the cell the current scheme picks the centre of). AC-1 requires beating that by ≥3×
(`RMS(Δf) ≤ 0.30 Hz`, `RMS(Δt) ≤ 7.7 ms`), which also roughly matches WSJT-X's own working
resolution. This keeps the bar mechanical and falsifiable rather than anchored to the Architect's
expectation (whose calibration record on magnitude predictions is explicitly poor — see spec §9).

**D5 — AC-3 (noise-only null) is a stop-the-programme gate, not a fix-and-retry finding.**
Every other criterion failing (AC-1, AC-2, AC-4) means the *implementation* is wrong: fix and
re-run, and it says nothing about D-001. AC-3 failing means the refiner manufactures false
positives by locking onto noise — if that shipped into R2, every false-positive measurement in the
next change would be uninterpretable. This is the one criterion where the Developer/QA session must
stop and escalate to the Captain rather than iterate locally (HK-021(k) both-branches-evaluated,
applied per-criterion, not once for the whole set).

**D6 — Cost is reported, never gated, but a >~8 h projected full-corpus runtime is an escalation
trigger, not a target to hit by any means.** WSJT-X performs equivalent work in real time on weaker
hardware, so a prohibitive projection more likely indicates a naive implementation (e.g.
re-deriving the full baseband per trial offset instead of once per candidate) than a fundamental
cost ceiling. The fix for a slow-but-correct refiner is an implementation review, not a scope cut
agreed unilaterally — hence escalate rather than optimise ad hoc past that threshold.

**D7 — The refiner's new C source is additive to `native/ft8_lib_vendor/`, not a modification of
any byte-identical vendored file.** R0 established the vendor tree as behaviourally pinned
(AC-1/AC-2 byte-identical decode output); this change adds new, OpenWSFZ-original files alongside
it rather than editing any file R0 verified against upstream, keeping R0's provenance guarantee
intact for everything it already covers.

## Risks / Trade-offs

- **[Risk] A sign error in the downconversion mixer** — named explicitly in advance (spec §5) as
  the single highest-probability defect: the refiner would still converge, still report plausible
  offsets, and pass a casual eyeball while moving every candidate the *wrong* direction, which would
  make a subsequent R2 look like a falsified hypothesis rather than a broken instrument. →
  **Mitigation:** AC-2 (systematic bias) is gated separately from AC-1 (RMS) specifically because a
  sign error inflates RMS only modestly while driving mean error hard away from zero; the Developer
  session must assert sign/index conventions with a test, not by re-reading the code (this programme
  has already been bitten once by an `ALL.TXT` `[5]`/`[6]` field-index inversion that cost a
  near-miss on a published finding).
- **[Risk] The refiner "locks" on noise, inflating false positives** → **Mitigation:** AC-3, gated
  as a stop condition (D5), with the statistical test and its p-value reported explicitly, before
  R2 is ever proposed.
- **[Risk] An underpowered SNR × offset-class cell** in the validation grid produces a
  falsely-reassuring PASS → **Mitigation:** `n ≥ 200` per cell is a floor, not a target; any cell
  falling short is reported as an instrument failure (HK-021(i)), not silently averaged in.
- **[Trade-off] Per-candidate downconvolution is the expensive part of this design**, and R2's
  candidate volume (a few hundred per cycle across two passes) means full-corpus runtime could be
  substantially slower than existing replay arms (36–44 min for 2 529 cycles). Accepted per D6 —
  reported, not gated, with an explicit escalation trigger rather than a silent scope cut.

## Migration Plan

No runtime migration — the refiner is diagnostic-only and no production call site changes.
Deployment is: merge to `main`; `FT8_SHIM_VERSION` / `ExpectedShimVersion` advances to `20260040`;
all three platform binaries rebuilt from the extended vendor tree. Rollback is a plain `git revert`
of the new-export + harness commit; R0's `20260039` binary remains valid and any already-published
result stays pinned to its own SHA regardless (specs pin by SHA, not by build-process identity, per
R0's own D2). R2 does not start until this change reports all-AC PASS; a FAIL here blocks nothing
already shipped, only the next step in the ladder.

## Open Questions

1. **Exact placement of the new refiner source within `native/ft8_lib_vendor/` vs. a new sibling
   directory** (e.g. `native/ft8_lib_vendor/refine/`) — left to the Developer session to decide and
   record, since R0 already established that the vendor tree's *byte-identical-to-upstream*
   guarantee must not be diluted by mixing OpenWSFZ-original files into the same paths as upstream
   files; a clearly separated directory is the likely answer but is not mandated here.
2. **Time-domain vs. FFT-domain mixer** for the coarse/fine search — the spec explicitly treats a
   prohibitively slow AC-6 result as more likely to indicate the wrong implementation choice here
   than a fundamental cost problem (D6); left as an implementation decision informed by the actual
   measured cost, not pre-decided.
3. **Whether the validation harness lives under `qa/rr-study/` (alongside the synth it drives) or a
   new `qa/` subdirectory of its own** — a QA-tooling placement choice with no bearing on the
   acceptance criteria themselves, left to the Developer/QA session implementing this change.
