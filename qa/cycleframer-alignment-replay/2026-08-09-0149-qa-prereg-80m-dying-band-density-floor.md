# QA pre-registration — 80m dying-band leg: does the recovery-vs-density relationship hold into a true near-zero density floor?

**2026-08-09 01:49Z, written before any capture data exists for this leg.** Radio already tuned to
80m (3.573 MHz), both WSJT-X instances decoding, `dialFrequencyMHz` in both OpenWSFZ configs
corrected 18.100 → 3.573 this session (was stale from the 08-08 17m leg — `cat.enabled=false` in
both, so this field is the only band label and there is no independent way to verify it once
armed). Arming is time-sensitive: the Captain's framing is "80m is guaranteed to die when morning
comes" — the value of this leg is the *natural*, propagation-driven decay to near-zero density,
which cannot be reproduced on demand and is worth capturing opportunistically rather than
constructing an artificial sparse-band leg later (per the standing "no sparse regime exists"
correction — this pushes the floor further than any prior leg, deliberately).

## 0. Setup (HK-020: goal stated explicitly, not inherited)

- **8080** = OpenWSFZ vs the Captain's two live WSJT-X instances (FT-991A / FT991A-Copy) — the
  reference-recovery comparison, same shape as the 08-08 three-way run.
- **8081** = OpenWSFZ vs itself, same device, same build — the self-consistency control (Captain
  confirmed this session: intentional same-device pairing, not the earlier SDR Uno split).
- Both instances: build `main @ b8845cd` (identical binaries to the 08-08 legs, not rebuilt),
  `ptt.method="AudioVox"`, `cat.enabled=false`, decoder settings frozen identical to every prior
  leg (`kMinScorePass2=10`, `osdCorrThreshold=0.1`, `osdNhardMax=60`) — changing them voids
  comparison to prior corpora.
- Supervisors: `2026-08-09-supervisor-8080-80m-dying-band.sh` /
  `-8081-80m-dying-band.sh` — line-for-line the same HK-013-validated watch/kill/restart logic as
  the 08-08 comparison/self-consistency pair (diff is header comments + log tags only; **not
  re-run through a fresh live kill-test**, since the logic is unchanged from an already-validated
  script — flagged here rather than silently assumed).

## 1. The question

Every density-vs-recovery reading on disk (T2, the 08-08 four-decoder run) comes from bands/legs
whose minimum cycle density was **15.3 (20m)** or **9.7 at Q1 / 3 minimum (17m)** — never a true
approach to zero. A band dying at dawn is the first opportunity to see whether:

- **(a)** the recovery-vs-density relationship (direction: recovery falls as density rises,
  established within-band on 20m, replicated in direction though not magnitude — see the 08-08
  23:30Z retraction, slope is NOT a stable, citable parameter) continues smoothly as density falls
  toward zero, consistent with an intercept-ward extrapolation, or
- **(b)** something qualitatively different happens near the floor — e.g. recovery collapses
  because the only remaining signals are marginal/fading (SNR distribution shifts down with the
  band, not just density), or recovery stays flat/improves because OpenWSFZ's time-bounded
  candidate/pass budget (T2a's structural-ceiling finding) stops being the binding constraint once
  there's almost nothing left to decode per cycle.

This is explicitly **not** a re-run of T2/T2a — those hit a *structural* ceiling on distinct
frequencies at high runtime on one fixed band; this leg varies density by a different, exogenous
mechanism (propagation collapse) and is confounded with a real SNR-distribution shift as the band
fades, which T2a's within-SNR-band check did not have to contend with. **That confound must be
carried into the read, not resolved away**: if recovery drops near the floor, the analysis must
attempt to separate "lower density" from "worse SNR" using the same per-cycle SNR data used
elsewhere, or report the two as entangled.

## 2. What is deliberately NOT pre-committed here

Per HK-021(b)/(g)/(j): quantile bin edges cannot be chosen before the actual density-decay curve
is observed — the 17m leg's ROW 0b failure (gating on the corpus's own median instead of range
coverage) is the direct lesson. **Binning for the eventual analysis will be derived from this
leg's own quantiles at analysis time, not fixed now.** This document pre-registers the hypothesis,
the void conditions, and the read logic — not the bin edges.

## 3. ROW 0 — void conditions (mechanical, checked before any other row is read)

- **ROW 0a (population floor):** fewer than 150 cycles in the post-dawn-decline window ⇒ VOID,
  underpowered. (150, not 20m's 400+, because this leg is expected to be short and is valued for
  its *range*, not its volume.)
- **ROW 0b (does the leg actually reach a new floor):** the minimum single-cycle density recorded
  in the run must be **< 3** (17m's own floor) or the leg's own bottom decile must sit below 17m's
  Q1 of 9.7 dec/cycle. If neither is met, the leg replicates 17m's floor at best and does not
  answer the "true near-zero" question ⇒ VOID as an instrument failure (band didn't die enough
  before capture had to stop), not a null.
- **ROW 0c (self-consistency baseline, from 8081):** WSJT-X-equivalent OpenWSFZ vs OpenWSFZ
  agreement must be ≥ 90% in the well-populated (pre-decline) portion of the run, consistent with
  the 94.4%/99.6%-family baselines already on disk. Below that, instrument health is in question
  and the leg cannot be read.
- **ROW 0d (band label correctness):** spot-check that `ALL.TXT`'s own frequency column for a
  sample of decodes falls in the 80m FT8 sub-band (~3.567–3.579 MHz after audio offset), confirming
  the corrected `dialFrequencyMHz` actually took effect and no stale process from the 17m config
  contaminated the file. Mechanical, not a judgment call.
- **ROW 0e (WSJT-X reference validity into the decline):** if WSJT-X itself stops decoding
  entirely before OpenWSFZ's density has cratered (i.e., the reference goes to zero first), the
  low-density tail has no reference to compute recovery against — that tail becomes descriptive
  only (raw OpenWSFZ decode counts, no recovery %), flagged, not silently dropped from the corpus.

## 4. Predicted outcome (recorded before data exists)

QA's own prediction, for later calibration scoring: **(b)-leaning** — recovery will fall faster
than the 20m/17m within-band slopes predict as density approaches the true floor, because the
SNR-distribution shift (fading signals, not just fewer of them) is expected to dominate once the
band is genuinely dying rather than merely quiet. Confidence: low — this is the first leg of its
kind, and per the standing calibration note, ranges have historically been read too pessimistically
about how cleanly an effect separates.

## 5. Stop condition

No fixed duration — the leg ends when the Captain judges 80m has died for the morning (WSJT-X
decode rate on the reference instances drops to ~0 and stays there), or if left running,
naturally exhausted by the following evening's revival, whichever the Captain calls first. Gather
per HK-016 before archiving, same as every prior leg.
