## Context

`ft8_decode_all`'s per-candidate `signal_db` computation (`ft8_shim.c`, inside the block
that follows a successful `ftx_message_decode`) is:

```c
float signal_db;
{
    float sum = 0.0f; int cnt = 0;
    int bs = mon.wf.block_stride;
    int pt = mon.wf.freq_osr * mon.wf.num_bins;
    int nb = mon.wf.num_bins;
    int b0 = (int)cand->time_offset; if (b0 < 0) b0 = 0;      /* line 1491 */
    int b1 = b0 + FT8_NN;                                      /* line 1492 */
    if (b1 > mon.wf.num_blocks) b1 = mon.wf.num_blocks;
    int fi = (int)cand->time_sub * pt + (int)cand->freq_sub * nb +
             (int)cand->freq_offset;
    for (int b = b0; b < b1; b++) {
        const WF_ELEM_T* row = mon.wf.mag + b * bs + fi;
        int tone_col = (int)tones[b - b0];                     /* line 1498 */
        if ((int)cand->freq_offset + tone_col >= nb) continue;
        float mx = (float)row[tone_col] * 0.5f - 120.0f;
        sum += mx; cnt++;
    }
    signal_db = cnt > 0 ? sum / (float)cnt : noise_floor_db;
}
```

`b` iterates **absolute waterfall block indices** (0 = start of the retained 15 s / 180 000
sample buffer). `tones[]` holds the candidate's own 79-symbol re-encoding, indexed 0..78
by **symbol position within the transmission**. The mapping from one to the other is
`symbol_index = b - time_offset` (block `b`'s content is symbol `b - time_offset` of the
candidate, because the candidate's symbol 0 starts at absolute block `time_offset`).

When `time_offset >= 0` this is exactly what the code computes: `b0 = time_offset`, so
`tones[b - b0] == tones[b - time_offset]`. The defect is that `b0` is **clamped** to 0
before that subtraction ever happens, so once `time_offset < 0`, `tones[b - b0]` becomes
`tones[b - 0] = tones[b]` — the **wrong symbol**, off by exactly `|time_offset|` blocks,
for all 79 iterations. `cnt` still reaches (up to) 79 because the loop bound `b1` is
computed from the clamped `b0`, not the true `time_offset`, so no iterations are skipped
either — the corruption is silent and total, not a partial-data effect.

`ft8_lib`'s own candidate-scoring code (`native/ft8_lib_build/patched/ft8/decode.c:160,226`,
vendored, not modified by us) faces the identical situation and handles it correctly:

```c
int block_abs = candidate->time_offset + block;  // relative to the captured signal
if (block_abs < 0)
    continue;
```

It computes the absolute block from the **unclamped** `time_offset` and skips (does not
re-anchor) any block that falls outside the retained waterfall. Our shim is meant to
mirror this convention (per `qa/rr-study/2026-08-22-1411-...-spec-b-dt-c-reported-dt-sign.md`
§1.1) and does not.

**Confirmation.** `qa/rr-study/2026-08-22-1454-qa-to-architect-b-dt-c3-results.md`
(arm B-dt-C3) measured this mechanically: a synthesised signal swept from `true_dt =
+0.08 s` to `−1.20 s`, decoded through the pinned production binary, shows a **17.4 dB**
step in reported SNR landing at **exactly** the block where the reported `time_offset`
proxy (`dt`) turns negative (`p_step == p_sign`, both part 4) — 210× larger than the
largest deficit a "signal partly outside the window" explanation could produce at that
point (0.083 dB, computed in advance from the known 12.64 s transmission length). ROW 0
validity passed on all four limbs, including an exact, six-decimal-place reproduction of
a prior independent run.

## Goals / Non-Goals

**Goals:**

- Make the symbol index used in the `signal_db` loop track the candidate's true,
  unclamped `time_offset`, so every averaged sample comes from the tone bin the
  candidate's own re-encoding says should be there.
- Preserve the existing safety property that the loop never reads the waterfall at a
  negative or out-of-range block index.
- Close the latent out-of-bounds *write-adjacent* read this fix would otherwise open:
  correcting the symbol index alone, without also correcting the loop's upper bound,
  would let `b` run past the point where `b - time_offset` exceeds `FT8_NN - 1`,
  reading `tones[]` past its 79-element bound. Both bounds move together.
- Change no ABI, no struct layout, no other decode-path behaviour.

**Non-Goals:**

- Recalibrate the `−26.5 dB` SNR bandwidth constant. The constant relates `signal_db −
  local_noise_db` to true SNR; it is unaffected by which tone bins `signal_db` is
  averaged from being *correct* rather than *wrong*. No re-derivation is implied. (If
  the post-fix acceptance run — see Migration Plan — shows a level shift on the
  `time_offset >= 0` side, that would be a surprise and grounds to stop, not proceed.)
- Change `ftx_find_candidates()`'s search range or anything about how a candidate's
  `time_offset` is chosen. This fix only changes how an *already-found* candidate's SNR
  is measured.
- Fix D-001 (the broader weak-signal recovery gap) outright. This removes one confirmed
  contributing mechanism; whether it moves the D-001 headline number is a separate,
  future measurement, not a claim of this change.
- Touch `compute_local_noise_floor_db` (the *denominator* term) — it has no time
  argument and is confirmed (B-dt-C1, B-dt-C3, both flat to ~0.1 dB across the sweep)
  not to participate in this defect.
- Add any new native export or diagnostic surface. This is a correctness fix to an
  always-active production path, not instrumentation.

## Decisions

### Decision 1: Fix both the symbol-index term and the loop's upper bound together

**Chosen:** Compute `b1` from the **unclamped** `time_offset` (`time_offset + FT8_NN`,
then clip to `mon.wf.num_blocks`), and compute the per-iteration symbol index as
`b - (int)cand->time_offset` (unclamped), not `b - b0`. `b0` itself is unchanged — it
still exists solely to keep `b`'s starting value non-negative (a required guard: `mon.wf.mag`
has no valid negative index).

**Why not fix only the symbol index (line 1498) and leave `b1` as `b0 + FT8_NN`?**
Once the symbol index is computed from the true `time_offset`, an unclamped-`b1`-sized
loop would push `b` up to `b0 + FT8_NN - 1 = FT8_NN - 1` (since `b0` is clamped to 0),
giving a symbol index of `(FT8_NN - 1) - time_offset`, which for any negative
`time_offset` exceeds `FT8_NN - 1` — an out-of-bounds read of `tones[]` (a 79-byte stack
array). The current code never hits this because it doesn't need to: its (wrong) symbol
index formula happens to stay in-bounds by construction. Fixing the index without the
bound would trade a silent correctness bug for a memory-safety bug. Both must move
together; this is why the proposal frames it as "closing a latent out-of-bounds read
that the clamp mismatch made possible," not a second, independent defect.

**Alternative considered — mirror `decode.c`'s `continue`-based skip exactly, block by
block:** iterate `b` over `[0, mon.wf.num_blocks)` unconditionally and `continue` when
`b - time_offset` falls outside `[0, FT8_NN)`. Rejected: more iterations than necessary
(the existing `b0`/`b1` pre-clipping already bounds the useful range in two arithmetic
lines), and changes the loop's shape more than the minimal fix requires. The chosen form
is arithmetically identical in effect — every block that would be skipped by a
`continue` is instead never entered — while touching only the two lines the defect lives
in.

### Decision 2: No defensive bounds check added inside the loop body

**Chosen:** Do not add an `if (sym_idx < 0 || sym_idx >= FT8_NN) continue;` guard inside
the loop, despite the existing precedent for such guards elsewhere in this same block
(the RQ-2 frequency-bin guard two lines below). Given the corrected `b0`/`b1`
derivation, `sym_idx = b - time_offset` is provably in `[0, FT8_NN)` for every `b` in
`[b0, b1)` — the loop bounds *are* the correctness argument, not a heuristic that a
runtime check would be hedging against.

**Alternative considered:** add the guard anyway, purely as defence-in-depth, matching
the RQ-2 style. Rejected for this change: RQ-2's guard exists because its own condition
(`freq_offset + tone_col >= nb`) genuinely can be true at runtime depending on candidate
frequency — it is not provably excluded by the surrounding loop bounds the way `sym_idx`
is here. Adding an unreachable branch would suggest a residual doubt about the derivation
that the design does not actually have; if a future change alters `b0`/`b1` in a way that
reintroduces the risk, that change's own review should re-derive the bound, not lean on
a silent guard here. (Recorded as a considered-and-rejected choice rather than left
implicit, since it departs from a local stylistic precedent.)

### Decision 3: `FT8_SHIM_VERSION` advances to `20260046`

Current committed version is `20260045` (r2-coherent-llr-instrument Amendment 2/3,
`ft8_get_last_snr_terms`). This fix is unrelated to that diagnostic work but shares the
same source tree; the next sequential version is `20260046`. `ExpectedShimVersion` in
`Ft8LibInterop.cs` and the version constant in `ft8lib-interop/spec.md` are updated to
match. Struct layout is unchanged; this is not an ABI break, only a behaviour-bearing
rebuild, consistent with how `fix-d004-local-noise-floor` (`20260012`) and every other
SNR-formula change in this project's history has been versioned.

### Decision 4: Regression proof is AC-N1 replay + the B-dt-C3 harness, not a new S1-style R&R run

**Chosen:** Two mechanical checks, both already specified and both cheap:

1. **Regression (no change where none is expected):** the eight committed
   `results/replay_*.json` files from AC-N1 — real decode replays where every observed
   `dt >= 0` — must be bit-identical, decode for decode, against the fixed binary. Since
   the fix only changes behaviour on the `time_offset < 0` branch, any divergence here
   would mean the fix's arithmetic is wrong even for the case it claims not to touch.
2. **Acceptance (the defect is actually gone):** re-run
   `qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py` unchanged
   (same harness, same seeds, same pinned grid) against the fixed binary. The arm's own
   spec (`qa/rr-study/2026-08-22-1433-...md`, §8) already pre-registers the pass
   condition: `E(p)` flat across the whole sweep, `Δ(p) < 8.0 dB` everywhere. The pre-fix
   `results/b_dt_c3_report.json` is already committed, so this is a direct before/after
   comparison with no new design needed.

**Why not a fresh S1-style R&R gage study (as `fix-d004-local-noise-floor` used)?** S1
only exercises `dt = 0` (single fixed offset per its own scenario definition) — it
cannot see this defect at all, before or after the fix, because it never places a
candidate at negative `time_offset`. B-dt-C3 is the instrument built specifically to see
this defect; reusing it as the acceptance gate is the more direct measurement, not a
weaker one.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| A negative-`time_offset` candidate's `signal_db` now averages fewer than 79 samples (as few as ~1 for the deepest allowed offsets), which could make the estimate noisier for the most extreme early arrivals. | This is the *correct* behaviour (thinned by missing data, not corrupted by wrong data) and matches `ft8_lib`'s own convention. `cnt > 0 ? sum/cnt : noise_floor_db` already handles the degenerate `cnt == 0` case (candidate entirely before the window) by falling back to the noise floor rather than dividing by zero. No new failure mode is introduced. |
| Signals that were previously reported at a wrongly *low* SNR and therefore filtered out downstream (noise suppression, OSD gating) will now report correctly and may newly pass those gates — a behaviour change visible to the operator (more decodes, or decodes with materially different SNR values, for early-arriving signals). | This is the intended effect of the fix, not a side effect to suppress. Flagged here so the post-fix acceptance run's reviewer is not surprised by a live decode-count change; no gate gets an automatic increase in its own threshold as part of this change. |
| Rebuilding all three platform binaries from one C-file change carries the project's standard native-rebuild risk (toolchain drift, platform-specific codegen). | Same rebuild process as every prior shim version bump (`BUILD.md`); G6 real-signal recovery fixtures on all three platforms are an existing, unmodified regression gate that would catch a gross rebuild problem. |
| The fix touches a loop that is the single busiest per-candidate computation in the decode path (up to `K_MAX_DECODED` candidates/cycle); a mistake here is latency-sensitive. | The change is two arithmetic expressions, not a restructuring; loop trip count is now `<= FT8_NN` exactly as before (never more), so there is no plausible latency regression, only a possible small *reduction* in trip count for negative-offset candidates. |

## Migration Plan

1. Implement the corrected `b0`/`b1`/symbol-index derivation in `ft8_shim.c` (design's
   Decision 1), exactly at lines 1491–1498.
2. Bump `FT8_SHIM_VERSION` to `20260046` in `ft8_shim.h`; extend the version-history
   comment block with this change's name and a one-paragraph summary of the fix.
3. Update `Ft8LibInterop.cs`'s `ExpectedShimVersion` constant and its doc comment.
4. Rebuild all three platform binaries via the existing native build process
   (`src/OpenWSFZ.Ft8/Native/BUILD.md`); update each `libft8.version.txt`.
5. `dotnet build -c Release` (0 errors/warnings) and `dotnet test -c Release` (all green,
   including the ABI self-test against `20260046`).
6. Confirm G6 real-signal recovery fixtures still pass on all three platforms (the fix
   must not regress any existing decode, only correct SNR values for a case those
   fixtures may not currently exercise).
7. Run the AC-N1 replay regression check (Decision 4, item 1) — all eight
   `results/replay_*.json` bit-identical.
8. Run the B-dt-C3 acceptance check (Decision 4, item 2) — `E(p)` flat, `Δ(p) < 8.0 dB`
   everywhere; compare directly against the committed pre-fix
   `results/b_dt_c3_report.json`.
9. Update `openspec/specs/ft8-decoder/spec.md` and `openspec/specs/ft8lib-interop/spec.md`
   per this change's spec deltas.

**Rollback:** revert `ft8_shim.c` and restore `FT8_SHIM_VERSION` to `20260045`. The ABI
sentinel prevents a version mismatch from silently loading the wrong binary, as with
every prior shim change.

## Open Questions

- **Does any downstream gate (noise suppression, OSD `nhard`) need re-tuning now that
  negative-`time_offset` candidates report correct SNR?** Not addressed by this change —
  those gates were tuned against the corrupted values for whatever fraction of live
  traffic they saw at negative offset (likely small, but not measured here). Worth a
  follow-up live comparison after this fix ships, not a precondition for merging it.
- **How much of D-001 does this account for?** Unknown and explicitly out of scope
  (Non-Goals). The B-dt-C3 report itself only characterises the *mechanism and its
  magnitude in a controlled sweep*, not its share of live traffic or its share of the
  D-001 headline gap.
