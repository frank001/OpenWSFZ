# D-001 C.3 — candidate-generation gap findings

**Author:** QA, 2026-07-26. Pure offline analysis of already-captured artefacts — no native or
managed code touched, so this is QA-only work, not a Developer session (HK-000/HK-015/HK-011).
**Source:** `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` §3, a
byproduct C.2's own Phase 1 matching surfaced but did not investigate: of the 793 WSJT-X messages
missed on the fixed 68-cycle corpus, 658 have no candidate of ours (decoded or not) anywhere
within tolerance, and of those, ~10 sit near a candidate that *did* decode (a separate dedup/
text-unpack loss). The remaining **648 (81.7% of the missed set)** are a candidate-*generation*
gap — `ftx_find_candidates` never proposes a sync candidate near that frequency/time at all —
distinct from both C.1's candidate-cap question and C.2's LDPC/LLR-survival question.
**Tool:** `qa/cycleframer-alignment-replay/c3_candidate_generation_gap_analysis.py`, reusing C.2's
own `candidate_diag.csv` and both `ALL.TXT` files under
`artefacts/20260725_live_run_1806/c2_phase1/k10_c0.10_n60/` (git-ignored, NFR-021).

---

## 1. Verdict

Two candidate explanations for the 648 were tested against each other:

- **(a) Weak-signal/sensitivity gap** — mundane: WSJT-X's sync detector is simply more sensitive
  at low/negative SNR than ours.
- **(b) Co-channel masking / lack of successive-interference-cancellation** — structural: matches
  the consolidation doc's own §6.3 fallback (WSJT-X runs extra decode passes with SIC and a-priori
  decoding; ft8_lib's single-pass sync search cannot separate a weak signal sitting near a stronger
  one it has already decoded).

**(a) is strongly supported. (b) is refuted, in the wrong direction.** This corrects my own
suggestion in the prior session (a proximity/masking hypothesis) — the data does not support it.

## 2. Method

Independently re-derived C.2's own population split first (verification, not blind trust), then
computed two comparisons between the 648-strong gap population and the 1235-strong shared-hit
population on the same 68 cycles:

- **Nearest decoded-candidate-of-ours frequency distance**, same cycle. For shared-hit messages,
  each message's own matching decode is excluded (its nearest *other* decoded neighbour is what's
  measured) so the comparison is like-for-like.
- **WSJT-X-reported SNR** (`ALL.TXT` field, both populations).

## 3. Results

**Population split, reproduced independently** (matches the C.2 findings doc's reported figures
exactly): 2028 WSJT-X messages / 1235 shared hit / 793 missed → 135 matched-to-a-failed-candidate
(17.0%), 10 near-a-decoded-candidate (1.3%), **648 no-candidate-anywhere (81.7%)**.

**Hypothesis (b) — proximity to a decoded neighbour:**

| population | n | median distance to nearest decoded neighbour | within 50 Hz |
|---|---:|---:|---:|
| candidate-generation gap | 648 | **32.9 Hz** | 67.6% |
| shared-hit (excl. self) | 1235 | **2.5 Hz** | 80.8% |

Mann-Whitney U p = 5.4×10⁻⁵², gap population **farther** from a decoded neighbour, not closer —
the opposite of what masking predicts. Messages that decode tend to sit *near* other decoded
signals (plausibly reflecting locally strong/busy parts of the band), not the reverse.

**Hypothesis (a) — WSJT-X-reported SNR:**

| population | n | median SNR |
|---|---:|---:|
| candidate-generation gap | 648 | **−8 dB** |
| shared-hit | 1235 | **+1 dB** |

Mann-Whitney U p = 1.1×10⁻⁷⁴ — the largest effect measured anywhere in this thread (C.1, C.2, or
this analysis). Holds at every SNR band checked in the [−25, +20) dB range, not just in aggregate
(the gap population's nearest-decoded-neighbour distance stays high in every band, ruling out an
SNR confound explaining away the proximity result rather than the other way round).

## 4. A concrete mechanism

`src/OpenWSFZ.Ft8/Native/ft8_shim.c:466`: `#define K_MIN_SCORE 10` — pass 0's sync-candidate
score floor, passed straight to `ftx_find_candidates(..., min_score)`
(`native/ft8_lib_build/patched/ft8/decode.c:264`), which discards any candidate scoring below it
**before** it is ever placed in the heap (`decode.c:285-286`: `if (candidate.score < min_score)
continue;`) — a gate entirely separate from `K_MAX_CANDIDATES` (`ft8_shim.c:467`, the array-size
question C.1 already tested). This is consistent with both findings above: a candidate whose
underlying sync correlation never clears 10 is invisible to every later stage regardless of array
size (explaining why C.1's cap-raising to 600 barely moved the needle), and low-SNR signals are
the population most likely to fall below that floor.

**This is a plausible mechanism, not a proven one.** `score` is a sync-correlation metric, not
SNR directly — the link between low reported SNR and a sub-10 sync score is asserted by
correlation and domain plausibility here, not measured candidate-by-candidate in this analysis.

## 5. What this changes about D-001's framing

The consolidation doc's §3 claim — "these are the only two things standing between us and the
740" (candidate-cap truncation and LDPC/LLR survival) — does not survive this data. There is a
third mechanism, and on this corpus it is the *dominant* one: 82% of the missed-message population
(648) versus 17% (135, C.2's own Phase 1 target). Even a fully successful C.2 Phase 2
(LLR-shrinkage) fix caps out around a sixth of the remaining gap. The consolidation doc's §6.3
fallback ("structural comparison against WSJT-X... successive interference cancellation") was
triggered here earlier than its own "only if 6.1 and 6.2 don't close it" ordering anticipated —
but the specific structural mechanism it named (SIC/co-channel masking) is not what the data
shows. A sync-sensitivity floor is a narrower, cheaper thing to test than reimplementing SIC.

## 6. Recommendation

Scope a `K_MIN_SCORE` sweep, same shape as C.1's `K_MAX_CANDIDATES` sweep: lower the pass-0 floor,
re-decode the fixed corpus, and measure directly how many of these 648 gain a candidate at all
(reusing this analysis's own matching machinery), separately from whether they then survive
LDPC/OSD. See `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md`.

## 7. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` §3 — where this
  population was first noticed and flagged as out of scope.
- `qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1;
  establishes that raising `K_MAX_CANDIDATES` to 600 barely moves total decodes, consistent with
  §4's mechanism (a score-floor gate that array size cannot work around).
- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3, §6.3
  — the two-mechanism framing this corrects, and the fallback avenue it triggers early.
- `qa/cycleframer-alignment-replay/c3_candidate_generation_gap_analysis.py` — this analysis.
- `native/ft8_lib_build/patched/ft8/decode.c:264-306` (`ftx_find_candidates`) — the score-gate
  mechanism.
- `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md` — the follow-up this findings doc motivates.
