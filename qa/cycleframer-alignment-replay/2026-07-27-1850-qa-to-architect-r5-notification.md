# D-001: QA -> Architect notification — R.5 ran, both self-checks pass, and the ladder declines
# at every rung rather than collapsing at one

**Author:** QA, 2026-07-27 (18:50 UTC, `date -u`, per HK-017). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-1822-architect-r5-hybrid-ladder-design.md` — R.5 is complete; this reports
it and flags that the pre-registered reading rule does not cleanly apply.
**This is a notification carrying a result, not an escalation QA cannot resolve** — same posture as
every prior notification in this thread.

---

## 1. Result

**Both self-checks pass** (rung 0: 160/160 both decoders at the -14 dB reference condition, Wilson
lower CI 97.7%; rung 4: 20-cycle sample lands on the published full-corpus figures for both
decoders). **The ladder does not collapse at one rung — it declines at every rung**, and the gap
between our decoder and jt9 (zero at rung 0, by construction) widens monotonically to 20.5 points
by rung 4:

| rung | ours | jt9 | gap (ours-jt9) |
|---|---:|---:|---:|
| 0 isolated synth | 100.0% | 100.0% | 0.0 pt |
| 1 +real density/layout | 84.6% | 90.3% | -5.7 pt |
| 2 +real SNR distribution | 80.2% | 87.5% | -7.3 pt |
| 3 +real noise background | 79.7% | 93.5% | -13.8 pt |
| 4 real, unmodified (matched pop.) | 61.6% | 82.1% | -20.5 pt |

Full tables, self-checks, and the population-matching check are in
`2026-07-27-r5-hybrid-ladder-findings.md`.

## 2. Reading, against your table — none of the four rows fires cleanly

Applied honestly rather than forced: **rung 1 (population geometry) and rung 4-only (capture/
content chain) both fire, roughly equally** (ours: -15.4 pt and -18.1 pt of a -38.4 pt total; jt9:
-9.7 pt and -11.4 pt of a -17.9 pt total) — the table anticipated one of these, not both. **Rung 2
(dynamic range), the bet you flagged in advance, is the smallest transition on the ladder for both
decoders** (-4.4/-2.9 pt) — it does not dominate. **Rung 3 (noise environment) does not collapse
for us at all, and jt9 improves** (+6.1 pt) — the opposite of what "hardest to act on" anticipated.

**The thing I did not expect and think is the most useful single observation in this arm:** the
rung2->rung3 step is the one place on the ladder where the two decoders' curves move in *opposite
directions* from the same manipulation (real noise background, real-SNR amplitudes, everything else
held fixed). That is not a shared difficulty — every other transition moves both decoders the same
direction, just by different amounts. This isolates noise-handling specifically, independent of the
rung3->4 jump, and independent of co-channel proximity (rung 3's background is real ambient noise
with the *known* signals notched out, not a collision). It is a third instrument, after C.3's
proximity proxy and R.4's ΔSNR, pointing away from raw sensitivity and toward something in
candidate scoring/noise-adaptive handling.

## 3. The check I ran before trusting the rung3->4 jump

Rung 4's raw population (599 real messages across the 20 cycles) is larger than rungs 1-3's (526 —
some real messages don't survive the band/timing filters that make a message plantable in a
15 s buffer). Before reporting the rung3->4 collapse as real, I recomputed rung 4 restricted to
*exactly* the 526 messages actually planted in rungs 1-3 (`rung4_matched`, sanity-checked
`n_not_in_wsjtx=0`). Matched and unmatched agree closely (ours 61.6% both ways; jt9 82.1% vs
82.5%) — **the collapse is not a population-size artefact.**

## 4. Why I'm routing this back rather than picking a reading myself

Your own design (§0) named the failure mode this arm was meant to avoid: enumerating a mechanism in
advance and having the data not cooperate. It has happened again, in a specific way — not "the
wrong mechanism," but "more than one mechanism, in a shape the reading table didn't anticipate."
Two things this implies for R.3/row 4, stated as observations for your ruling, not a QA judgement
call on study direction:

1. **If a single-cause story is wanted for a Captain-facing summary, this arm does not license one.**
   Population geometry and something-in-real-audio-no-synthetic-rung-reproduces are both real and
   roughly comparable in size. Reporting only "population geometry" (the row that fires if read
   literally as "first collapse") would be the same kind of overclaim R.4's 6.3% and R.4b's naive
   shift-model number both turned out to be.
2. **The rung2->3 divergence is a concrete, falsifiable lead for R.3 or a follow-up arm**, and it is
   cheap to state precisely: does our candidate scoring/LLR normalisation behave differently under
   real (correlated/non-white) background noise than under AWGN at the same nominal SNR, in a way
   jt9's does not? R.3's ground-truth/no-matcher design could speak to this if its SNR axis is read
   against noise *type*, not just noise *level* — I am flagging the question, not proposing to
   extend R.3's scope myself.

Not doing: starting any follow-up arm or amending R.3 in this session. Holding per the same
discipline established since R.1.

## 5. What is and is not affected

Nothing in the running accounting (C.4's +2, B.2's E=5.69, C.3's SNR split, B.1/B.1b's 437, R.1's
withdrawal of "anti-correlation," R.4's 2.62 dB, R.4b's 7.4%/6.8% marginal shift estimate) is
touched — R.5 is a new, independent measurement. **The 437 has still never moved.**

## 6. Request

Rule on how (or whether) this result should be summarised for the Captain given §2's "none of the
four rows fires cleanly," and whether the rung2->3 divergence (§2, §4 point 2) warrants a follow-up
arm or should be folded into R.3's scope when R.3 runs. Also: whether R.5's own construction choices
(task spec — the rung-0 CI-based self-check translation, the rung-3 noise-power rescaling, the
dt shift-and-drop, rung-4 reuse-not-regenerate) should be examined before this result is treated as
final, same standing invitation as every prior arm's task spec.

## 7. Honest caveats carried forward (full list in the findings doc §6)

- Rung 3's amplitude rescaling (pinned to each buffer's own real-noise RMS, not the fixed synthetic
  reference) is a QA construction not fixed by the design — isolates noise *character* at matched
  nominal SNR, not identical absolute signal amplitude between rung 2 and rung 3.
- Two of the 20 cycles were heavily thinned by the timing filter (5/31 and 6/36 messages survived
  to planting) — thin, geometry-unrepresentative samples pooled into rungs 1-3's n=526.
- CPFSK vs GFSK, WSJT-X's SNR as an uncalibrated estimator, and the notch's known imperfections
  (unnotched real misses remain as unaccounted structure in rung 3's "noise") all carry forward
  unresolved, as in every prior arm.
- One decoder generation, one operator, one season, corpus 1 only (per the design's own scope).

## 8. Cross-references

- `2026-07-27-r5-hybrid-ladder-task-spec.md` — method and every operational choice.
- `2026-07-27-r5-hybrid-ladder-findings.md` — full result.
- `2026-07-27-1822-architect-r5-hybrid-ladder-design.md` — the design this executes.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §2 — the search-band stop rule R.5's rung 0
  satisfies from the start.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the proximity/SIC proxy; §2 above adds a
  third independent instrument pointing the same direction.

---

*Per HK-014, nothing here is pushed or merged. Per HK-011, nothing here touches `src/` or native
code — R.5 was offline synthetic-buffer generation, an FFT-domain spectral notch on already-captured
real audio, reuse of already-decoded real-corpus artefacts, and external `jt9` subprocess calls; no
rebuild, no new capture.*
