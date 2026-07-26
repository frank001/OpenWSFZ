# D-001 C.2 Phase 2a — ceiling re-derivation against the K=4/cap2000 candidate set

**Author:** QA session, 2026-07-26. **For:** Architect (per HK-015 — this reaches the Architect
before Phase 2b is scoped further, whichever way the verdict comes out, per the dev-task's own
closing instruction).
**Source:** `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §2.
**Analysis only** — no native/managed code touched, no rebuild, no re-decode. Reuses committed
artefacts from C.2 Phase 1, C.3, and C.4 exactly as the dev-task specified. Script:
`qa/cycleframer-alignment-replay/c2_phase2_ceiling_rederivation.py`.

---

## 1. Summary verdict

**Ceiling stays bounded near the original 135. Do not proceed to Phase 2b on Phase 2a's evidence
alone.**

The expanded population (567 of 648, after excluding genuine recoveries — §3) does **not**
reproduce C.2 Phase 1's weak-LLR signature once score is controlled at real resolution. `prenorm_var`
looks strongly lower in aggregate (Mann-Whitney p≈2e-25) but that is a score-distribution artefact
(§5): once compared at each population's own exact sync score, only 39.3% of the expanded population
sits below its same-score matched-hit control — essentially a coin flip, not the systematic,
every-band effect C.2 Phase 1 found; scores 5, 6, and 9 alone (344 of 567 = 60.7%) show
matched-missed's own median *higher*, the wrong direction for a weak-LLR story. `postnorm_mean_abs_llr`
— the metric one step closer to what a shrinkage fix would actually change — shows **no significant
difference in aggregate** (p=0.36 raw, p=0.60 score-overlap-restricted) and, at exact resolution, is
**higher for matched-missed than matched-hit at every one of scores 5–10** (98.6% of the population)
— the opposite of C.2 Phase 1's original direction, not merely a weaker version of it. This is
decision-rule outcome 2 in the dev-task's §2: *"No consistent signature, or a materially
weaker/inconsistent one... ⇒ Phase 2's ceiling stays bounded near the original 135."*

Per the dev-task's own instruction, this is where §6.3 (structural comparison) becomes the
Architect's next call, not QA's.

## 2. Self-check (dev-task step 2) — passed, but only after finding a real confound

The dev-task's self-check compares this script's matched-decode count against the ruling's own
independently-measured **+2** for K=4/cap2000
(`2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §2 table, "K=4 @2000" row,
Δ matched). First pass did **not** pass:

| check | count | vs. ruling's +2 |
|---|---:|---|
| freq/dt-proximity "matched a decoded candidate" (any candidate near the target, decoded=1) | 21 | not directly comparable (see below) |
| exact message-TEXT match, restricted to the 648, absolute (K=4/cap2000's own ALL.TXT) | 33 | off by +31 |

Two distinct issues, both resolved before trusting anything downstream:

1. **Freq/dt proximity is not the same claim as recovering the target message.** A candidate can
   exist near a missed message's frequency/time and show `decoded=1` while decoding a *different*
   message — almost certainly the stronger co-channel signal C.3 already showed these messages sit
   near. Fixed by re-deriving the exact hash-normalized message-TEXT intersection
   (`c4_matched_decode_verification.py`'s own methodology) restricted to the 648 population, instead
   of trusting the `decoded` flag alone.
2. **The remaining +31 gap was a baseline confound, not a bug in the matching logic.** The ruling's
   +2 is a *delta relative to the K=10/cap=600 baseline* (which already decodes WSJT-X's own
   captured audio, per C.4's deliberate audio-source deviation), not an absolute count against C.2
   Phase 1's original owsfz-audio identity run. Those two audio sources already differ by the
   ~0.5% capture-chain gap the dev-task's own §3 cites. Computing the *same* text-match check
   against the K=10/cap=600 baseline's own `ALL.TXT` found **31** of the 648 already match there,
   purely from the audio-source switch — nothing to do with `K_MIN_SCORE`. The baseline-relative
   delta is **33 − 31 = +2**, an exact match to the ruling's own figure.

**Self-check result: exact match (+0 difference) once corrected for the baseline confound.** This
gives higher confidence in the matching logic than a coincidental near-miss would have — the
number that had to be found (the audio-source-driven baseline count) was not something the dev-task
anticipated, and finding it exactly cancels the discrepancy.

## 3. Population classification against K=4/cap2000

| population | n | % of 648 |
|---|---:|---:|
| still no candidate anywhere within tolerance | 30 | 4.6% |
| matched a decoded candidate (freq/dt; self-check population, §2) | 21 | 3.2% |
| matched a failed candidate (raw expanded population) | 597 | 92.1% |
| **matched a failed candidate, after dropping 30 genuine recoveries** (§3.1) | **567** | **87.5%** |

Consistent with C.4's own `recov648` figure for k4_cap2000 (95.4% gaining *any* candidate: 30 + 21 +
567 + ... ≈ 95.4% of 648 — exact agreement, independent re-derivation).

### 3.1 Excluding genuine recoveries from the expanded population

`nearest_candidate()` picks the closest-by-frequency candidate, which is not always the one that
actually decoded the target message when several candidates sit within tolerance of each other. 30
of the 597 freq/dt-nearest-failed rows had their *source* WSJT-X message text-match K=4/cap2000's
own `ALL.TXT` via a different, non-nearest candidate — i.e. they were genuinely recovered. These are
excluded from the LLR comparison population (597 → 567); comparing "still failing" candidates
against messages that in fact now decode would have been the wrong test.

## 4. Score-banded LLR comparison, expanded matched-missed (n=567) vs. matched-hit (n=6834)

| metric | matched-missed median | matched-hit median | Mann-Whitney U (raw) |
|---|---:|---:|---|
| score (uncontrolled) | 6.0 | 10.0 | — |
| `prenorm_var` | 93.74 | 121.13 | U=1427976.5, p=1.99e-25 |
| `postnorm_mean_abs_llr` | 4.165 | 4.182 | U=1892787.0, **p=0.361** |

Width-10 score bands (C.2 Phase 1's own convention): `prenorm_var` lower in 2/3 populated bins, but
**546 of 567 (96%) sit in a single [0,10) bin** — K_MIN_SCORE=4 admits scores as low as 4, so this
population's own score range (5–29) is almost entirely below C.2 Phase 1's original population's
range (10–40+). A width-10 bin cannot "control for score" for a population this concentrated; it
would silently average away exactly the resolution the comparison needs.

### 4.1 Finer-grained (width=1) score comparison — the real test

| score | n missed | n hit | missed < hit prenorm_var? |
|---:|---:|---:|---|
| 5 | 87 | 384 | no (84.04 vs 79.63) |
| 6 | 222 | 1563 | no (95.32 vs 87.59) |
| 7 | 134 | 819 | **yes** (90.93 vs 96.98) |
| 8 | 68 | 413 | **yes**, essentially tied (99.82 vs 99.89) |
| 9 | 35 | 193 | no (96.07 vs 93.75, missed higher) |
| 10 | 13 | 114 | **yes** (90.90 vs 102.45) |
| 11 | 5 | 68 | **yes** (83.21 vs 105.28) |
| 12, 13 | 0 | 85, 85 | no missed candidates at these scores |
| 14, 27, 29 | 1 each | 126, 126, 109 | **yes** at all three (single-candidate reads) |
| 15–26, 28 | 0 | moderate | no missed candidates at these scores |

(Full table in the script's own output; the findings doc's job is the summary, not a transcript.)

**Result: missed < hit at only 7 of 10 distinct scores with a same-score control, covering 223 of
567 candidates (39.3%) — not the "lower in every populated band" result C.2 Phase 1 found.** Scores
5, 6, and 9 (87 + 222 + 35 = 344, 60.7% of the population) show matched-missed's median *higher*
than matched-hit's, the wrong direction. `postnorm_mean_abs_llr` is worse, not better, at exact
resolution: matched-missed's median sits *above* matched-hit's at every one of scores 5 through 10
(559 of 567 candidates, 98.6%) — e.g. score 6: 4.185 vs 4.098; score 9: 4.164 vs 4.060; score 10:
4.261 vs 4.096 — a consistent reversal of C.2 Phase 1's original direction across almost the entire
population, not merely an attenuated version of it.

### 4.2 Floor/clamp-infeasibility re-check (C.2 §6)

Re-checked at this larger sample: matched-hit's own `prenorm_var` minimum (7.31) still sits below
matched-missed's minimum (18.91) — the same conclusion C.2 §6 reached at n=135 holds unchanged here.
A naive floor/clamp remains infeasible regardless of which way the ceiling question resolves.

## 5. Why the aggregate numbers looked decisive and are not

The raw, score-uncontrolled comparison (§4's headline row) shows a large, highly significant
`prenorm_var` gap. That is a **confound, not a finding**: the matched-hit control population spans
scores 5–38 (median 10), while the expanded matched-missed population is concentrated at scores 5–9
(median 6) by construction — `prenorm_var` rises with score in this corpus (visible directly in the
per-score table, hit-population column: ~80 at score 5 up to ~250 at score 29). Comparing an
almost-entirely-low-score population against a control spanning much higher scores manufactures a
lower aggregate median even with *no* causal LLR effect at all. This is exactly the failure mode
score-banding exists to catch, and it only shows up because this population needed finer bins than
C.2 Phase 1's original one did — a direct consequence of C.4 admitting candidates at scores as low
as 4/5, well below C.2 Phase 1's population's floor of 10.

## 6. Verdict, per the dev-task's §2 decision rule

> No consistent signature, or a materially weaker/inconsistent one (e.g., `prenorm_var` not
> systematically lower once banded by score, or the gap present but tiny next to C.2's original
> effect size) ⇒ Phase 2's ceiling stays bounded near the original 135. Report that finding and
> stop — do not proceed to 2b on the strength of the original 135-message result alone without the
> Architect/Captain explicitly deciding it is still worth a hot-path change for that yield.

This is that outcome. `prenorm_var` is not systematically lower once banded at real resolution
(39.3%, effectively a coin flip once the score confound is removed), and `postnorm_mean_abs_llr` —
the metric closer to what a shrinkage fix targets — shows no significant difference at all and
reverses in the two dominant score bins. **Phase 2b (the shrinkage fix itself) is not started by
this finding.** Per the dev-task, this is the point where the ruling's promoted §6.3 (structural
decoder comparison) becomes the Architect's next call.

## 7. What this does not overturn

- **C.2 Phase 1's original 135-message finding stands unchanged** — that population, entirely at
  score ≥10, still shows the effect at the same p-values C.2 reported. Only the *expanded*
  candidate-generation-gap population (score 4/5–9, reachable solely because of C.4's floor
  lowering) fails to replicate it.
- **C.4's own verdict stands** (score-floor rejection closed, ~+2 decodes, near-zero yield) — this
  note's self-check independently reproduces that exact figure once the audio-source baseline
  confound is accounted for, which is corroborating evidence for C.4's own number, not a revision
  of it.
- **The floor/clamp-infeasibility conclusion (C.2 §6) is re-confirmed**, not revised, at this larger
  sample (§4.2).

## 8. Honest caveats

- This is one 21-minute session, one device, one band — the same single-sample caveat every prior
  note in this thread has carried, and it applies here too.
- The per-score table's resolution runs out fast above score ~11 (few or zero missed candidates per
  score), so §4.1's "39.3%" figure is itself dominated by the five lowest scores (5–9, 546 of 567
  candidates). That is not a weakness introduced by this analysis — it is a direct description of
  where this expanded population actually sits — but it means the finer-grained read is only as
  informative as the lowest handful of scores, which is exactly where it turns out not to be
  informative in the direction Phase 2b would need.
- WSJT-X is a reference, not absolute ground truth (same caveat the ruling's own §3 raised); "genuine
  recovery" in §3.1 means "text-matches WSJT-X's report," not independently verified ground truth.

## 9. Cross-references

- `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §2 — the task this executes; §3 (Phase 2b)
  remains gated on this finding and is not started.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §2, §5.1 — the ruling this
  self-checks against and the instruction to re-derive Phase 2's ceiling this way.
- `2026-07-26-c2-llr-normalization-findings.md` §3, §4, §6 — Phase 1's original method, the 135-
  message result this expanded population fails to replicate, and the floor/clamp-infeasibility
  finding re-confirmed in §4.2 above.
- `2026-07-26-c4-min-score-sweep-findings.md`, `c4_matched_decode_verification.py` — the K=4/cap2000
  artefacts and exact-text-match methodology this script reuses.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the 648-message population's original
  identity.
- `qa/cycleframer-alignment-replay/c2_phase2_ceiling_rederivation.py` — this note's source script,
  reproducible against the same committed artefacts.

---

*Per HK-015, this reaches the Architect before Phase 2b is scoped further, regardless of which way
the verdict came out — here, to confirm the decomposition table's §4 entry for mechanism 3 stays as
scoped-but-unshipped rather than being promoted on the strength of this expanded population.*
