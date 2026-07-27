# D-001 R.4b — real-corpus decode-probability curve: findings

**Author:** QA, 2026-07-27 (15:42 UTC, `date -u`, per HK-017). **Executes:**
`2026-07-27-r4b-realworld-sensitivity-task-spec.md`, operationalising
`2026-07-27-1522-architect-r4-ruling-and-r4b.md` §4.

---

## 0. Verdict

**Self-checks pass on both corpora.** None of the three pre-registered reading-rule rows fires
cleanly — the result sits between them, and I am reporting that honestly rather than forcing it
into one row. Two things came out of this arm that the design's own reading table did not fully
anticipate, and one caught what would have been a second under-scrutinised headline number in this
same thread:

1. **The naive shift-model estimate (56.4% / 52.0%) is inflated by baseline decode
   non-determinism and is not the sensitivity-attributable number.** Checked before reporting it
   (§3) — the corrected, marginal figure is **7.4% / 6.8%**, close to the withdrawn step-model
   floor's 6.3%/6.2%. The *number* from the rejected step model turns out to be roughly right; the
   *model* was still correctly rejected.
2. **The high-SNR asymptote is 89.8%/89.0%** — elevated, but short of the ~95% the reading rule's
   row 1 treats as saturation. Ambiguous by the rule's own terms.
3. **The cycle-density split gives a modest, one-corpus-only signal** (+5.8 points favouring
   sparse cycles on corpus 1, 21 of 34 well-powered bins; a statistically flat +1.6 points on
   corpus 2, split 15/20). Suggestive of co-channel effects on one corpus, not confirmed on the
   other.

## 1. Self-checks

```
[PASS] corpus 1 (40m, 68 cyc): hit=1239 (expect 1239) miss=789 (expect 789)
[PASS] corpus 2 (20m, 126 cyc): hit=2437 (expect 2437) miss=1934 (expect 1934)
```
Both match the totals already on record from R.4/B.1/B.1b exactly.

## 2. The curve and the high-SNR asymptote

Full whole-dB-binned curves (46 bins corpus 1, 47 bins corpus 2, Wilson CIs throughout) are in
`artefacts/d001_r4b_realworld_sensitivity/{corpus1,corpus2}.json`. Shape, both corpora: a slow,
genuinely probabilistic rise — roughly 10–30% at −20 to −24 dB, 30–50% through the −15 to −8 dB
band (where C.3 places the real miss population's median), 55–75% through 0 to +4 dB, and only
reaching the 90%+ range from roughly +8 dB up.

| | corpus 1 | corpus 2 |
|---|---:|---:|
| High-SNR asymptote (≥ +5 dB) | **89.8%** (n=528) | **89.0%** (n=627) |
| CI | [86.9%, 92.1%] | [86.3%, 91.2%] |

**Reading against the design's row 1** ("P saturates ≥ ~95%") — this does not clear that bar on
either corpus, but sits closer to it than to "materially below saturation" in the sense the design
probably meant (a curve stuck at 60-70% forever). It is a real, CI-tight ~10% residual failure
rate even on strong signals, on both corpora independently. **Neither the "misses above threshold
are structural" reading nor a clean rejection of it is fully licensed by this number alone** — an
honest ~10% of even comfortably-strong real traffic is never decoded by us, for reasons this arm
cannot attribute (could be co-channel collision even at high SNR, hash-table effects, message
types outside our decode path, or genuine demodulator loss — R.3 territory, not this arm's).

## 3. The shift-model estimate — and why the naive number is wrong

**What I checked before reporting anything:** the design's method (findings task spec §2 step 5)
is "sum, over missed messages, of `P(curve, snr + ΔSNR)`." At the corrected ΔSNR = 2.625 dB:

| corpus | expected recovered | % of missed |
|---|---:|---:|
| 1 | 445.2 / 789 | **56.4%** |
| 2 | 1006.4 / 1934 | **52.0%** |

**This number is close to jt9-depth-1's real-world coverage (55.4%/55.8%) — close enough that I
nearly reported it as confirmation that sensitivity explains most of the gap after all.** Before
doing that, I ran the same computation at **shift = 0 dB** as a control — i.e., "what does the
curve predict for a missed message decoding at its own actual, unchanged SNR?" This isolates how
much of the 56.4%/52.0% is baseline non-determinism (the same SNR bin contains both hits and
misses, so its average `P` is never 0 even for messages that happened to fail) rather than
anything attributable to a sensitivity improvement:

| corpus | shift=0 (baseline) | shift=2.625 dB | **marginal (2.625 − 0)** |
|---|---:|---:|---:|
| 1 | 49.0% (387.0/789) | 56.4% (445.2/789) | **7.4%** (58.2 msgs) |
| 2 | 45.2% (874.2/1934) | 52.0% (1006.4/1934) | **6.8%** (132.2 msgs) |

**The baseline alone is 49.0%/45.2% — most of the raw shift-model number.** Decode is genuinely
probabilistic enough, at the SNR levels where most misses live, that a large fraction of "misses"
are close calls that could plausibly have gone the other way with *zero* change — not evidence of
a sensitivity gap at all, just variance. **The number actually attributable to the 2.625 dB
sensitivity improvement is the marginal difference: 7.4% / 6.8%.**

**This reconciles with, rather than overturns, the withdrawn step-model floor.** The step model's
*number* (6.3%/6.2%) was numerically close to right; its *model* (a hard threshold, falsified by
80%+ of misses sitting above it) was still correctly rejected in the 15:22 ruling. Both things are
true at once and I want that on the record plainly rather than letting the earlier rejection read
as having been about the wrong target.

## 4. Cycle-density split

Median density: 30 WSJT-X decodes/cycle (corpus 1), 34 (corpus 2). Restricted to well-powered
bins (n ≥ 10 both sides — 34 bins corpus 1, 37 corpus 2) and computed a count-weighted mean
`P(sparse) − P(dense)` at matched SNR:

| corpus | bins favouring sparse | bins favouring dense | weighted mean Δ |
|---|---:|---:|---:|
| 1 | 21 of 34 | 12 of 34 (1 tie) | **+5.8 points** |
| 2 | 15 of 37 | 20 of 37 (2 tie) | **+1.6 points** |

**Corpus 1 shows a modest, majority-of-bins signal consistent with row 3's co-channel/collision
hypothesis** (sparse cycles decode ~6 points better at matched SNR). **Corpus 2 shows essentially
nothing** (split close to even, weighted effect near noise floor). Full per-bin tables in the JSON
outputs. This is suggestive, not confirmatory, and materially weaker than I expected given C.3's
proximity finding and R.4's own reasoning about what "the other 93%" was likely to be.

## 5. Reading, against the pre-registered table — none of the three rows fires cleanly

| row | fires? |
|---|---|
| P saturates ≥ ~95% → structural, confirms ~6% | **No** — 89-90%, short of the stated bar. |
| P stays materially below saturation, broad band → shift model **materially larger** than 6.3% | **Partially, then reverses on inspection** — the naive shift number (52-56%) is materially larger, but §3 shows that's an artefact of baseline non-determinism; the *corrected* marginal shift estimate (6.8-7.4%) is **not** materially larger than 6.3%/6.2%. |
| P depressed in dense cycles at matched SNR → co-channel is the driver | **One corpus only** (corpus 1, modestly); corpus 2 does not replicate. |

**My own reading, offered for your ruling rather than as a settled conclusion:** the corrected
numbers now agree with each other in a way the raw ones didn't — a ~7% sensitivity-attributable
contribution (§3, marginal), a high-SNR plateau close to but not at saturation (§2), and a weak,
one-corpus-only co-channel signal (§4) — none of which individually explains the bulk of the
55.4%/55.8% real-world gap. **The result of this arm is that R.4/R.4b together have now ruled out
two mechanisms (pure isolated-signal sensitivity, §R.4's 147/147; a clean sensitivity-shift of the
real curve, §3 here) without the co-channel arm confirming cleanly either.** That leaves the space
of remaining explanations narrower than before but not yet occupied by anything the study has
positively measured — which is, again, an argument for R.3, not a substitute for it.

## 6. Honest caveats

- **The marginal-shift computation (§3) is a QA-added check, not something the ruling's method
  specified.** I ran it because the raw number's closeness to 55.4%/55.8% was suspicious enough to
  warrant checking before reporting — the same posture the 15:22 ruling asked of me generally.
  Flagging it as an addition to the design, not a silent substitution.
- **The shift model, marginal or raw, assumes decode probability is a function of SNR alone**,
  holding everything else about a message fixed. If jt9's real advantage is not "the same decode
  chain at a lower SNR floor" but something SNR-independent (multiple passes, candidate strategy),
  the shift model's marginal number is not measuring that mechanism even at its corrected value —
  it specifically isolates the SNR-shift explanation and nothing else, by construction.
- **Cycle density is a same-instrument congestion proxy, not a direct co-channel measurement** —
  more WSJT-X decodes in a cycle correlates with more signals in the passband but does not
  establish that any specific missed message was lost to a specific collision.
- **CPFSK vs GFSK does not apply here** — R.4b is the one arm in this study built specifically to
  avoid it (ruling §4), since it measures entirely on real GFSK traffic with no synthetic step.
- **Integer SNR quantisation** — whole-dB bins, per the design; some bins (especially at the
  extremes) are thin (n<10, visible in the full tables) and their `P` should be read with the
  correspondingly wide Wilson interval, not as a point estimate.
- **High-SNR asymptote cutoff (+5 dB) is a QA choice** (task spec §2 step 4), not one the ruling
  fixed numerically — flagged in the task spec, repeated here.

## 7. Cross-references

- `2026-07-27-r4b-realworld-sensitivity-task-spec.md` — method, self-check design, threshold/cutoff
  choices.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §4, §7, §8 — the design this executes, and §0's
  independent confirmation of the corrected ΔSNR (2.625 dB) this arm uses.
- `2026-07-27-r4-sensitivity-gap-findings.md` §3 — the withdrawn step-model floor (50/120,
  6.3%/6.2%) this arm's marginal estimate reconciles with.
- `2026-07-26-b1-jt9-ablation-findings.md`, `2026-07-27-b1b-second-corpus-findings.md` — the
  55.4%/55.8% real-world coverage this arm's numbers are read against throughout.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the proximity/SIC proxy §4's weak,
  one-corpus co-channel signal is set against.
- `artefacts/d001_r4b_realworld_sensitivity/` — full curves, asymptote, shift-model, and
  density-split JSON per corpus (git-ignored, NFR-021).
