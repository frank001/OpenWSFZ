# SUB-FEAS: Captain authorised the scoped build — handing to the Architect for a design proposal

**QA, 2026-09-28 16:01Z** (`date -u`, HK-017). Branch `qa/sub-feas`. Follows the Stage 2 diagnostic
(`qa/rr-study/2026-09-28-1025-qa-to-architect-sub-feas-stage2-diagnostic-results.md`) and the
ruling `dc9fceed` on `arch/subtraction-feasibility` ("build prohibition stands, lifting it is the
Captain's call").

## The decision

The Captain, 2026-09-28: **lift the subtraction BUILD prohibition for the scoped, flag-gated
build** — explicitly choosing this over the Architect's recommended sequencing (second-corpus
acceptance against the ORIG control, plus a runtime bar, before any build). That precondition is
**not** being required first. This is the Captain's call to make (`closed-arms-prohibitions.md`:
"Only a ruling on SUB-FEAS's result can license a build, and that needs the Captain") and it has
now been made. Recorded on the board and in `closed-arms-prohibitions.md` in the same edit as this
memo.

QA is not the design authority for the build (HK-015: Architect → QA → Developer). This memo hands
the build to the Architect for a change proposal; QA will write `tasks.md` and the Developer
dev-task once that design lands, and will review the implementation per the usual flow.

## What QA is flagging for the design doc, and why

This is not the first attempt at native-code signal subtraction. `closed-arms-prohibitions.md`
already carries "Subtract-and-resynthesise DEAD — three builds, three reverts" as a standing
prohibition; SUB-FEAS's precondition measurement was authorised precisely because it tested
something those three attempts didn't (a data-aided fit of an already-decoded signal). QA pulled
the archived record on what specifically failed each time, since none of it is summarised in the
current board entry:

1. **`fix-d001-pcm-sic` (2026-06-07, reverted at `efc0920`).** CP-FSK/cosine cancellation
   synthesiser, fixed phase-zero assumption. Result: **two independent production `0xC0000005`
   crashes** — the first from a 703 KB stack allocation in a P/Invoke target, the **second
   persisting after that was patched to a heap allocation** (i.e. the stack-vs-heap fix did not
   root-cause the second crash) — **and zero measurable improvement (−0.1 pp)** on real signals.
   Reverted for both reasons independently; either alone would have been sufficient.
2. **`diag-d001-h3b-gfsk-sic` (2026-06-12).** Follow-on after an intermediate PCM-SIC diagnostic
   regressed −13.98 pp. Root cause: CP-FSK vs the actual GFSK (BT=2.0) modulation, plus a
   cos/sin phase-initialisation error — together drove the least-squares fit amplitude to `a ≈ 0`,
   so the subtraction removed essentially nothing while discarding spectrogram-domain suppression
   that had been working. Model-mismatch failure, not a crash.
3. **`diag-d001-three-pass-sic` (2026-06-12).** Isolated pass-count as a variable (2→3 passes,
   no subtraction change) — not itself a subtraction attempt, but part of the same investigation
   arc.

Also on record: `fix-d001-revised` (2026-06-07) already named the path SUB-FEAS has now measured —
its Option C was "retry PCM-domain SIC using a realistic channel model: per-symbol amplitude from
waterfall magnitudes + linear frequency trajectory fitted across all 79 symbols. **Requires Captain
approval gate based on Python PoC results before any production code is written.**" SUB-FEAS Stage
1/2 is that PoC, run three months later. The process named in June has been followed; this memo is
the approval-gate outcome.

## What QA asks the design proposal to address (given the above, not new invention)

- **Model fidelity to what was actually measured.** Stage 2's offline diagnostic gain (net +8.89 pp
  after the replay control) was measured with a specific data-aided fit method. The design doc
  should state plainly whether the native implementation reproduces that method exactly, and if not,
  what differs and why the offline result should still be expected to transfer — attempt 2 above
  failed exactly on a model/reality mismatch that wasn't caught until production.
- **Crash/stability testing, as a named gate independent of decode-rate accuracy.** Attempt 1's
  fatal defects were never visible to the R&R decode-rate corpus — they surfaced in production
  (endurance-class, long-running, varied input). The design should specify a stress/endurance pass
  (not just the decode-rate corpus) before this is considered mergeable, given the precedent.
- **Flag-gated, default OFF** — per the Architect's own recommendation, unchanged by the Captain's
  sequencing decision.
- **Runtime budget.** FR-026 / the ft8-decoder spec's 13 s cycle budget; Stage 2 itself flagged
  runtime as unmeasured. Even without the pre-build corpus/runtime gate, the design doc should
  characterise the added pass's wall-clock cost before Developer starts, not after.
- **Bounded, configurable iteration count** as a named constant (echoes the June `AC-IS-4` pattern
  that held up under the original briefing).
- **`FT8_SHIM_VERSION` bump**, checked against current pins (`main` `20260051`,
  `decoding_improvement` `20260054`) to avoid a collision — the outstanding renumbering item is
  still open on the board.

None of this reopens Stage 1 or Stage 2's readings, and it does not re-litigate the Captain's
sequencing decision. It is the same class of question QA asked in the original
`DEV-BRIEFING-iterative-subtraction.md` (AC-IS-7) four months ago, updated for what has actually
happened since.

## Handoff

Awaiting the Architect's change proposal (design.md addressing the above) on `arch/`. QA will write
`tasks.md` and the Developer dev-task once it lands, per HK-015, and will hold review to the usual
standard (HK-011: QA proposes `src/`/`native/` changes and stops; a separate Developer session
applies them — the actual build is not QA's to write).
