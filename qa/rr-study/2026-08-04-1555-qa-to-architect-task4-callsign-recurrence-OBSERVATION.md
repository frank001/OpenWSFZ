# QA → Architect — Task 4 result: callsign-recurrence FP proxy (observation, no verdict)

**Author:** QA, 2026-08-04 (15:55 UTC, `date -u`, per HK-017).
**Executes:** `qa/rr-study/2026-08-04-1500-architect-to-qa-spec-false-positive-surge-and-window4-closure.md`
Sec.6. **No pre-registered rule governs this; none was drafted. No verdict below.**

---

## Privacy note, read before anything else

This task's method requires reading real off-air message text and extracting callsigns. Per the
GDPR callsign policy (NFR-021: only Q-prefix synthetic calls in VCS, exceptions PD2FZ + public
figures), **no real callsign is printed, written, or retained anywhere in this task's output or in
the script itself.** Every extracted identity is SHA-256 hashed (truncated to 16 hex chars)
immediately on extraction; only the hash is ever used for grouping or printing. Instrument:
`qa/rr-study/callsign_recurrence_proxy.py`.

## Method, as specced

Corpus `artefacts/20260803_live_run_1713/`, full corpus (not restricted to the decisive epoch —
Sec.6 does not ask for that restriction). Built the same two populations as the PASS report's §8
observation: exact `(cycle slot, message)` match between owsfz and wsjtx, **hashed callsigns
normalised first** (any bracketed token, resolved or not, collapsed to a canonical `<HASH>` marker
before the equality check — mirrors §8's 57.11% -> 58.66% finding, so it is not left in).

| | this run (full corpus) | PASS report Sec.8 (window both files cover) |
|---|---:|---:|
| matched in both | 25,411 | 24,480 |
| 8080 only | 39,006 | 37,511 |

Close but not identical, as expected — different window (full corpus here vs. the intersecting
window there), not a discrepancy in method.

For each decode in each population, extracted identity token(s) from the OpenWSFZ message text
(best-effort FT8 grammar: strips `CQ` + directed-CQ qualifier, grid squares, signal reports,
`RR73`/`RRR`/`73`/`RO`; a literal unresolved `<...>` carries no identity and is dropped; a resolved
`<XXXXX>` is treated as that identity). Grouped by (hashed identity), counted **distinct cycles**
each identity appears in within its population.

## Results

| | 8080-only (39,006 decodes) | matched-in-both (25,411 decodes) |
|---|---:|---:|
| decodes with no extractable identity | 1,966 (5.04%) | 498 (1.96%) |
| distinct identities | 7,357 | 3,335 |
| **singleton fraction** (1 cycle only) | **53.32%** | **16.64%** |
| median cycles/identity | 1 | 4 |
| mean cycles/identity | 8.40 | 12.53 |

Cycle-count distribution (fraction of identities):

| cycles seen | 8080-only | matched-in-both |
|---|---:|---:|
| 1 | 53.3% | 16.6% |
| 2 | 7.8% | 19.1% |
| 3-5 | 13.9% | 27.6% |
| 6-10 | 9.4% | 15.7% |
| >10 | 15.5% | 21.0% |

**Delta: the 8080-only set's singleton rate is +36.7 points higher than the matched set's** (53.3%
vs 16.6%).

## What this is and is not, per Sec.6

**This is consistent with an elevated FP rate in the 8080-only population — it is not a
measurement of one.** Sec.6 requires stating which innocent explanations can and cannot be excluded:

- **Cannot exclude: weak DX heard once.** A real station worked once and never heard again
  produces exactly this signature. Nothing here distinguishes "false decode" from "genuine
  single-contact station" at the level of a single identity.
- **Cannot exclude: band-edge / marginal-SNR effects unique to 8080's greater apparent
  sensitivity.** If 8080 genuinely decodes weaker signals than WSJT-X (consistent with the +48.6%
  volume figure from §8), a real population of weak, briefly-audible stations would also show an
  elevated singleton rate without being false.
- **Cannot exclude: extraction-method noise.** The identity extractor is best-effort (documented
  regex heuristics for grid/report/CQ-qualifier stripping), not a validated FT8 grammar parser. Some
  fraction of "distinct identities" in either population may be parsing artefacts (e.g. a malformed
  or partially-garbled decode producing a token that looks callsign-shaped but isn't a real
  identity) rather than genuine stations. This would inflate singleton counts in **both**
  populations, but not necessarily equally — a false decode is more likely to also be a mis-parsed
  one, so this could be inflating the 8080-only figure specifically.
- **Can partially address: the matched-in-both population is not a clean "true positive" baseline
  either.** WSJT-X is a co-appraiser, not an oracle (86.9-93.0% within-appraiser repeatability,
  standing constraint). A decode WSJT-X also produced is more likely real but not guaranteed to be.
- **What the delta does rule out:** the two populations are not statistically indistinguishable —
  53.3% vs 16.6% is not consistent with the same underlying recurrence process by chance on n>3,000
  identities in each group. Something structurally differs between what 8080 finds alone and what
  it finds in agreement with WSJT-X. This proxy cannot say what fraction of that difference is false
  decodes versus genuine extra sensitivity.

**No verdict is drawn.** Per Sec.6 and the standing "must not acquire verdict status by repetition"
instruction (echoing §8 of the PASS report), this observation is reported as context for the
Architect's judgement, not as evidence that closes the FP question either way.
