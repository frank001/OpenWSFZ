# D-001 R.4 — sensitivity-gap findings

**Author:** QA, 2026-07-27 (15:08 UTC, `date -u`, per HK-017). **Executes:**
`2026-07-27-r4-sensitivity-gap-task-spec.md`, operationalising
`2026-07-27-1730-architect-row4-scoping-design.md` §4 as resequenced by
`2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §7.

---

## 0. Verdict

**Self-check passed. ΔSNR = 2.86 dB (jt9 depth-1 more sensitive than our shipped decoder, on
byte-identical isolated synthetic signals).** But the dB-to-messages conversion this was meant to
feed produces a striking result that reframes the question rather than answering it as posed:
**closing the entire measured 2.86 dB gap would recover only ~6% of either corpus's miss
population — because 80–85% of the missed messages already sit at WSJT-X-reported SNR levels at
or above the weakest signal we currently decode successfully.** Most of the miss population is not
a sensitivity-tail phenomenon relative to our own demonstrated floor. Pure front-end sensitivity,
measured the only way this arm can measure it (isolated single-signal synthetic buffers, no
co-channel), bounds only a small slice of row 4's real-world gap.

## 1. Self-check

Re-ran `jt9 -8 -d 1 -p 15` on B.1's own recorded WAV (`260725_180615.wav`) via the identical
single-file invocation path this script uses for its own buffers, and compared the resulting
decode set against B.1's own recorded stdout for that timestamp (message text compared, never
printed — NFR-021).

```
elapsed=0.48s recorded_n=27 fresh_n=27 match=27 only_recorded=0 only_fresh=0
[PASS] exact-set reproduction confirmed
```

Exact match. The jt9-invocation plumbing this arm depends on is confirmed correct before any new
number is trusted, per the design's stop rule.

## 2. ΔSNR

**Grid:** -14 to -30 dB, 1 dB steps (17 levels), 3 repeats/level, 8 isolated signals/buffer = 51
buffers, 408 planted-signal measurements per decoder, generated fresh (seed 20260727, distinct
from B.2's own buffers) and **persisted as WAV + manifest** under
`artefacts/d001_r4_sensitivity_gap/buffers/` for R.3's reuse per the 1444 note's instruction.

| decoder | 50% crossing (synthetic `snr_db` scale) |
|---|---:|
| ours (shipped K10/c0.10/n60) | **-21.5 dB** |
| jt9 (`-8 -d 1`, minimum effort) | **-24.36 dB** |

**ΔSNR = ours_50 − jt9_50 = 2.86 dB.** Both curves are well-resolved (n=24 per grid point,
Wilson CIs in the raw table below) and both fall cleanly from ~90%+ to 0% within the swept grid —
no bracketing failure. Full per-level table:

```
OURS  P(decode) vs snr_db                          JT9   P(decode) vs snr_db
 -14.0 dB  n=24 k=21 p=87.5%                        -14.0 dB  n=24 k=24 p=100.0%
 -19.0 dB  n=24 k=21 p=87.5%                        -19.0 dB  n=24 k=24 p=100.0%
 -20.0 dB  n=24 k=21 p=87.5%                        -20.0 dB  n=24 k=24 p=100.0%
 -21.0 dB  n=24 k=15 p=62.5%                        -21.0 dB  n=24 k=24 p=100.0%
 -22.0 dB  n=24 k= 9 p=37.5%                        -22.0 dB  n=24 k=23 p=95.8%
 -23.0 dB  n=24 k= 2 p= 8.3%                         -23.0 dB  n=24 k=24 p=100.0%
 -24.0 dB  n=24 k= 2 p= 8.3%                         -24.0 dB  n=24 k=17 p=70.8%
 -25.0 dB  n=24 k= 0 p= 0.0%                         -25.0 dB  n=24 k= 3 p=12.5%
 -26.0 dB  n=24 k= 0 p= 0.0%                         -26.0 dB  n=24 k= 1 p= 4.2%
```
(Full table, all 17 levels both decoders, in `artefacts/d001_r4_sensitivity_gap/curves.json`.)

**This is jt9 at minimum effort (depth 1), the same arm B.1/B.1b used for direct comparability.**
It is a floor on jt9's advantage, not a ceiling — B.1 itself showed depth 2/3 recover materially
more (corpus 1: d1=55.4% -> d3=98.0% of the miss population). Nothing here measures what a
higher-depth jt9 comparison would show; that was out of scope by the design (R.4 mirrors B.1's
minimum-effort arm specifically).

## 3. The dB-to-messages curve — and why it is small

**Threshold definition (a QA operational choice — task spec §2.3, not fixed by the Architect's
design):** the 5th percentile of WSJT-X-reported SNR among each corpus's own successfully-decoded
(shared-hit) population — i.e., the weakest signal we are empirically already handling on that
corpus. Corpus 1: **-14.0 dB**. Corpus 2: **-18.0 dB**.

| x (dB bought, capped at ΔSNR=2.86) | corpus 1 recovered | corpus 2 recovered |
|---:|---:|---:|
| 1.0 | 28 (3.5%) | 65 (3.4%) |
| 2.0 | 50 (6.3%) | 120 (6.2%) |
| 2.86 (full ΔSNR, computed exactly, not interpolated) | 50 (6.3%) | 120 (6.2%) |

(The count does not move between x=2.0 and x=2.86 — integer SNR quantisation, §6, means the next
message only enters at the next whole-dB boundary, which sits past the measured ΔSNR.)

**Why so small.** The corpus SNR distributions, computed directly for this arm (not reused from
C.3):

| | corpus 1 miss (n=789) | corpus 1 hit (n=1239) | corpus 2 miss (n=1934) | corpus 2 hit (n=2437) |
|---|---:|---:|---:|---:|
| median | -8.0 dB | +1.0 dB | -12.0 dB | -2.0 dB |
| p5 | -21.0 dB | -14.0 dB | -22.0 dB | -18.0 dB |
| p25 | -13.0 dB | -6.0 dB | -16.0 dB | -10.0 dB |

**80.4% of corpus 1's miss population and 85.3% of corpus 2's already sit at or above the
threshold** (the weakest SNR we successfully decode on that same corpus). These messages are not,
by this measure, in our sensitivity shadow at all — they are at signal strengths comparable to or
stronger than traffic we already decode cleanly, and are missed for some other reason. Only the
minority below threshold (19.6% / 14.7%) is even eligible for the ΔSNR conversion, and of that
minority, only the sliver within 2.86 dB of the boundary is "buyable" — hence ~6.3%/6.2%, not a number
anywhere near the 55%+ jt9 depth-1 already recovers on real corpus data (B.1 §3/§4, B.1b §3/§4).

**This is the headline finding, not a footnote:** a 2.86 dB pure-sensitivity edge, measured
cleanly on isolated synthetic signals, cannot explain jt9-depth-1's real-world 55.4%/55.8% miss
coverage. Something Arm A's isolated-signal geometry structurally cannot see — co-channel handling,
candidate-generation strategy, or effort beyond "minimum" even within depth 1 — is doing most of
the work. This is independent corroboration, via a different instrument, of the same direction
C.3's proximity/SIC analysis already pointed at, and it puts a number on how little of it sensitivity
explains.

## 4. Reading, per the design's table (§4)

> The curve stays flat until close to the full ΔSNR → Row 4 is an indivisible commitment; price it
> against row 5 in full.

That shape fires, but the more informative statement is upstream of it: **the curve is not just
flat, it is small in absolute terms relative to the miss population, for a reason the SNR data
itself explains (§3).** Row 4's real target, per this measurement, is not "buy a few dB of
sensitivity" — most of the gap sits at SNR levels sensitivity improvements do not reach at all.

## 5. What this does and does not settle

**Settles:** the pure-sensitivity contribution to row 4's gap, isolated-signal-only, is small and
bounded (~6.2-6.3% of either corpus's miss population, at jt9's own minimum-effort ΔSNR). This is a
measurement, not an inference from C.3's proximity proxy — an independent line of evidence landing
in the same place.

**Does not settle:** what the other ~93% of the gap is. R.3's amended detection-vs-budget axis
(ground truth, no matcher, no null, candidate-cap axis, SNR axis) is the arm built to attribute it,
and this result strengthens rather than weakens the case for running it — R.4 alone cannot
distinguish co-channel/SIC handling from candidate-generation/ranking from decode-effort-beyond-
minimum-depth, and Arm A's isolated-signal geometry cannot even test the first of those.

## 6. Honest caveats

- **Arm A is isolated-signal only, by design (§2.1 reuses B.2's Arm A, not Arm B).** jt9's edge in
  real co-channel-dense traffic could be larger still (SIC/multi-pass handling is a co-channel
  phenomenon, not something an isolated-signal sweep can even expose). §3's "80%+ already above
  threshold" finding is therefore, if anything, a conservative lower bound on how much of the gap
  is non-sensitivity — a co-channel arm would likely find even less of the gap attributable to
  raw sensitivity, not more.
- **CPFSK vs GFSK** (B.2 §5, carried forward unresolved through the whole R-series) — ΔSNR is
  measured on synthetic CPFSK against real GFSK traffic. Most exposed exactly here, since §3
  applies a synthetic-channel ΔSNR to real-corpus SNR values.
- **WSJT-X's reported SNR is its own estimator, not a calibrated absolute** (design §4's own
  stated limit). The threshold (§3) sidesteps this for its own definition — it is read entirely
  off real corpus data, no synthetic-to-real conversion — but ΔSNR itself, the step size applied
  to that threshold, does cross the synthetic/real boundary and inherits this caveat directly.
- **Integer SNR quantisation.** WSJT-X's `ALL.TXT` reports SNR as whole dB; the 0.5 dB step in
  §3's table is finer than the underlying data supports (visible as repeated counts at
  consecutive half-dB steps, e.g. corpus 1's x=1.0/1.5 both reading 28). The curve's *shape* is
  real; its half-dB resolution is not.
- **jt9 minimum effort only (depth 1).** §2's last paragraph, restated: this measures the floor of
  jt9's advantage, not its full extent.
- **One decoder generation, one operator, one season** — same standing caveat as every arm in this
  thread.

## 7. Cross-references

- `2026-07-27-r4-sensitivity-gap-task-spec.md` — method, threshold definition, self-check design.
- `2026-07-27-1730-architect-row4-scoping-design.md` §4 — the design this executes.
- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §6.1, §7 — R.3's amended detection
  axis, the arm this result hands the mechanism question to.
- `2026-07-26-b1-jt9-ablation-findings.md`, `2026-07-27-b1b-second-corpus-findings.md` — the
  55.4%/55.8% depth-1 miss coverage this arm's ~6% dB-bought prediction falls far short of.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the proximity/SIC proxy this arm
  independently corroborates via a different instrument.
- `artefacts/d001_r4_sensitivity_gap/` — raw measurements, manifest, curves, WAV buffers
  (git-ignored, NFR-021; buffers are Q-prefix synthetic by construction).
