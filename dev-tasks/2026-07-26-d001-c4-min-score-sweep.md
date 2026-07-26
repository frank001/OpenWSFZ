# Developer handoff: D-001 C.4 — is the pass-0 sync-score floor (`K_MIN_SCORE`) costing us decodes?

**Authored by:** QA (per HK-000/HK-015). **Status:** ready for a Developer session. Needs a native
rebuild (`src/OpenWSFZ.Ft8/Native/ft8_shim.c`), so this is HK-011 work — not QA-only.
**Source:** `qa/cycleframer-alignment-replay/2026-07-26-c3-candidate-generation-gap-findings.md` —
the QA-only diagnostic this follows from directly.

---

## 1. Why this is the right experiment now

C.2's own Phase 1 matching (`2026-07-26-c2-llr-normalization-findings.md` §3) turned up a
byproduct it explicitly did not investigate: of the 793 WSJT-X messages missed on the fixed
68-cycle corpus, only 135 (17.0%) are candidates that exist but fail LDPC/OSD — C.2's own target
population. **648 (81.7%) have no candidate of ours anywhere near that frequency/time at all.**
C.3 (`2026-07-26-c3-candidate-generation-gap-findings.md`) tested this population against two
hypotheses:

- Co-channel masking / lack of successive-interference-cancellation (the consolidation doc's own
  §6.3 fallback hypothesis) — **refuted**, in the wrong direction (Mann-Whitney U p = 5.4×10⁻⁵²;
  the 648 sit *farther* from a decoded neighbour than messages that did decode, not closer).
- A plain weak-signal/sensitivity gap — **strongly supported** (p = 1.1×10⁻⁷⁴; median WSJT-X SNR
  −8 dB for the gap population vs. +1 dB for shared hits, holding at every SNR band checked).

This points at a specific, cheap-to-test mechanism: `src/OpenWSFZ.Ft8/Native/ft8_shim.c:466`,
`#define K_MIN_SCORE 10` — pass 0's sync-candidate score floor, fed to
`ftx_find_candidates(..., min_score)`
(`native/ft8_lib_build/patched/ft8/decode.c:264`), which discards any candidate scoring below it
**before** it is ever placed in the heap (`decode.c:285-286`). This is a gate entirely separate
from `K_MAX_CANDIDATES` (the array-size question C.1 already tested and found does not explain
this population — raising the array to 600 barely moved total decodes, consistent with a
score-floor rejection happening upstream of array size entirely).

**This is now the largest untested lead in D-001.** Even a fully successful C.2 Phase 2
(LLR-shrinkage) fix caps out at ~17% of the remaining gap (135 of 793); this experiment's
population is ~5x larger.

## 2. Prerequisite — confirm C.1's stack-safety fix is present before touching either constant

`d001-c1-candidate-cap-sweep` (PR #115, open at time of writing) found and fixed a genuine stack
buffer overflow: `ft8_shim.c`'s pass-loop local `candidates[]` array was hardcoded to
`K_MAX_CANDIDATES_PASS2` (200), true only while `K_MAX_CANDIDATES <= 200`. If this branch is
started before PR #115 merges, **re-apply that fix first** — do not skip it because "this
experiment doesn't touch `K_MAX_CANDIDATES`" (see §3 step 2 below for why it does need to move,
even though it isn't the primary variable). Confirm which state `main` is in before starting;
if PR #115 has merged, this is a no-op check, not a re-implementation.

## 3. Why `K_MAX_CANDIDATES` has to move too, even though `K_MIN_SCORE` is the variable under test

Lowering `K_MIN_SCORE` alone, with `K_MAX_CANDIDATES` left at 140, is confounded:
`ftx_find_candidates`'s heap keeps only the top `num_candidates` (140) by score among everything
that clears the floor (`decode.c:288-303`). If lowering the floor from 10 admits a large volume of
low-score entries — a mix of the specific weak *real* signals this experiment is after, and pure
noise that now also clears a lower bar — the 140-slot heap competes both populations against each
other. A result showing "no improvement" at a lower floor could mean either "no real signals down
there" or "real signals are down there but noise crowded them out of the top 140," and this
experiment cannot tell those apart unless the array is generously sized so the floor, not the
array, is the only thing being tested.

**Method:** pair every `K_MIN_SCORE` setting below with `K_MAX_CANDIDATES = 600` (pass 0 only,
`K_MAX_CANDIDATES_PASS2` untouched) — the same ceiling C.1 already verified crash-free and
correctly-sized at 4.3x the shipped cap. This isolates the floor's effect from the array-size
question C.1 already closed.

## 4. Method

For each `K_MIN_SCORE` ∈ {10 (baseline), 8, 6, 4} (all with `K_MAX_CANDIDATES = 600` per §3):

1. Edit `src/OpenWSFZ.Ft8/Native/ft8_shim.c:466` (`#define K_MIN_SCORE 10` → 8, 6, 4 in turn) and
   `:467` (`#define K_MAX_CANDIDATES 140` → 600, held constant across all four settings). Leave
   `s_k_min_score_pass2` (pass 1's runtime-configurable floor, default 10, `ft8_shim.c:437`)
   untouched — this experiment is pass-0-only, matching C.1's and C.2's scope.
2. Rebuild `libft8.dll` (`native/ft8_lib_build/rebuild_shim.bat`) for each setting. Local Windows
   dev binary only — do not commit until §8 decides.
3. Re-decode the fixed corpus: **`artefacts/20260725_live_run_1806/wsjt-x/wav/`** (WSJT-X's own
   captured audio for the same 68 matched cycles — keeps the capture chain, already measured at
   0.5% of the gap, out of this experiment) via
   `qa/rr-study/d001-param-sweep-2026-07-22/D001ParamSweep` at `--points k10_c0.10_n60
   --dial-mhz 7.074 --candidate-diag-csv candidate_diag.csv` (C.2's own flag — reuse it, do not
   invent a second diagnostic path).
4. For each setting, run `c3_candidate_generation_gap_analysis.py`'s matching logic (or a small
   adaptation of it) against the new `candidate_diag.csv`, to answer the question this experiment
   is actually about: **how many of the specific 648 candidate-generation-gap messages identified
   in C.3 now have *any* candidate of ours (decoded or not) within tolerance** — not just whether
   the total decode count went up, which conflates this population with C.2's 135 and with any new
   false positives. Report this count per setting.
5. Also report, per setting, exactly as C.1 did: total decodes, `failCands`/`meanAbsLLR` (median/
   mean, `ldpc_stats.py`'s existing methodology), and decode elapsed time (median/p90 ms per cycle
   against the 15 s production budget).
6. **False-positive spot-check, not optional.** Lowering the sync floor admits more noise into
   LDPC/OSD; the CRC gate rejects most of it, but not necessarily all. For each setting, count
   decoded messages that are *not* in WSJT-X's `ALL.TXT` for that cycle (mirroring C.2/C.3's own
   "unique to us" count — baseline ~49 on the current 140/K_MIN_SCORE=10 setting, per C.3 §3's
   population-split arithmetic: 1284 ours total − 1235 shared). A setting whose unique-to-us count
   grows sharply relative to its recovered-candidate count is a false-positive risk, not a clean
   win — report the ratio, don't just report the headline recovery number.

## 5. Interpretation

- **A materially rising count of the 648 gaining a candidate, without a matching rise in
  unique-to-us decodes** ⇒ the floor is costing us real signal; part of the 648 is directly
  recoverable and `K_MIN_SCORE` becomes a tuned parameter, same shape as C.1's conclusion for
  `K_MAX_CANDIDATES` at 300.
- **The 648-recovery count stays flat, or unique-to-us decodes rise in lock step with it** ⇒ the
  floor is not the constraint (or the ones it does admit are just as likely to be noise as signal),
  and the candidate-generation gap is not fixable by this knob — escalate to the consolidation
  doc's §6.3 avenue (structural comparison against WSJT-X) as a Captain-level product decision,
  per that document's own framing, since C.1, C.2, and this experiment will together have closed
  every parameter-tuning avenue this codebase currently exposes.

Either outcome is decisive.

## 6. Watch for

- **Timing budget**, same concern C.1 already flagged at `K_MAX_CANDIDATES = 600`: more candidates
  clearing the floor means more LDPC/OSD attempts per cycle. C.1 found 600 stayed comfortably
  inside the 15 s budget (749.5 ms median / 827 ms p90) at the *current* `K_MIN_SCORE = 10` — a
  lower floor at the same 600 ceiling will likely cost more, since more of that ceiling's headroom
  will actually be used. Recheck, don't assume C.1's timing numbers still apply unchanged.
- **D-009's calibrated OSD gate** (`OSD_CORR_THRESHOLD`, `OSD_NHARD_MAX`) was calibrated against
  the population of candidates that currently clear `K_MIN_SCORE = 10`. Widening that population
  changes what OSD is asked to adjudicate — same caveat C.2's Phase 2 scoping raised for the
  LLR-normalisation change. This experiment does not need to re-calibrate OSD to report a result,
  but any decision to ship a lowered `K_MIN_SCORE` permanently should not skip that step (§8).

## 7. What this experiment does not resolve, even if it succeeds

`score` is a sync-correlation metric, not SNR directly (C.3 §4's own hedge). A positive result
here confirms the floor is *a* constraint; it does not by itself prove the mechanism is "SNR
sensitivity" as cleanly as C.3's correlation suggests — report what actually happens, not what the
prior hypothesis predicted.

## 8. Definition of done

- [ ] §2's prerequisite confirmed (PR #115's stack-safety fix present, or re-applied).
- [ ] Four rebuilds (`K_MIN_SCORE` ∈ {10, 8, 6, 4}, `K_MAX_CANDIDATES = 600` throughout), each
      re-decoding the full 68-cycle `wsjt-x/wav/` corpus at `k10_c0.10_n60` with
      `--candidate-diag-csv` enabled.
- [ ] Report table: setting → count of the 648 gaining any candidate → total decodes →
      unique-to-us decode count → `failCands`/`meanAbsLLR` (median/mean) → decode elapsed time
      (median/p90 ms/cycle).
- [ ] A written verdict per §5's criteria — not left ambiguous.
- [ ] Any deviation from this spec recorded in the findings doc's own "Done (deviation recorded)"
      annotation, per project convention.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) before any "ready" claim — see the C.2
      findings doc's own precise account of what "green" actually required there (a real,
      reproducible, non-blocking local-tooling gap on the WSL step; do not wave this away without
      checking what's actually failing and why, the way that document did).
- [ ] `git status` clean of any rebuilt `libft8.dll` unless §9 below decides to keep a new
      `K_MIN_SCORE`/`K_MAX_CANDIDATES` value permanently, with its own explicit Captain sign-off.

## 9. What happens after this reports

QA owns the analysis. If the result contradicts the consolidation doc's decomposition table
(`2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1) in any way, escalate to the Architect
rather than quietly revising it, same rule C.1's own dev-task recorded. If this closes a
meaningful share of the 648, a permanent `K_MIN_SCORE`/`K_MAX_CANDIDATES` change needs the same
weight of validation C.2 already specified for its own Phase 2 (at minimum, an R&R S1–S8 rerun
before any shipped-constant decision) — this is not lower-risk than that change merely because the
diff is a one-line constant; it changes the daemon's real decode output on every cycle, same as
Phase 2 would.

## 10. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-c3-candidate-generation-gap-findings.md` — the
  finding this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` — C.2, sibling
  experiment; establishes the 135-message population this one is *not* about.
- `qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1; the
  stack-safety-fix prerequisite (§2) and the `K_MAX_CANDIDATES = 600` ceiling reused here (§3).
- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3, §6.3
  — the two-mechanism framing C.3 corrected, and the fallback avenue if this also closes nothing.
- `qa/cycleframer-alignment-replay/c3_candidate_generation_gap_analysis.py` — matching machinery
  to reuse for §4 step 4's per-setting recovery count.
- `native/ft8_lib_build/patched/ft8/decode.c:264-306` (`ftx_find_candidates`) — the score-gate
  mechanism under test.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:466-467` (`K_MIN_SCORE`, `K_MAX_CANDIDATES`) — the constants
  this experiment edits.
