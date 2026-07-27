# D-001: hold R.3 — both of its axes are already dead, and I should have caught it before now

**Author:** Architect, 2026-07-27 (16:03 UTC, `date -u`, per HK-017). **For:** QA, and the Captain.
**Supersedes:** the sequencing in `2026-07-27-1555-architect-r4b-ruling-and-band-limits.md` §5 and
`2026-07-27-1522-architect-r4-ruling-and-r4b.md` §8, **to the extent they say "R.3 next."**
**Instruction: do not start R.3.** Short note, deliberately.

---

## 1. Two problems, both fatal to R.3 as designed

### 1.1 The candidate-cap axis was already swept, by C.1, on real audio

At 14:44 I made the cap axis (600 / 2000 / uncapped) a first-class part of R.3 and pre-registered:
"if detection recovers substantially at large cap, row 4's problem is capacity/ranking — which is
much cheaper." **C.1 already ran that experiment on real corpus audio and answered it.**

| `K_MAX_CANDIDATES` | decodes | Δ | pass-0 candidates (median) |
|---:|---:|---:|---:|
| 140 (shipped) | 1288 | — | 140 |
| 300 | 1300 | +12 | 220 |
| 600 | 1300 | **+12** | 220 |

300 and 600 give **byte-identical decode sets**. The real candidate population plateaus at ~220–295
per cycle and never approaches the raised ceiling. Capacity is not the bottleneck; the answer is
+12 decodes, **1.6% of the gap**.

I designed an axis around a question already on the record. That is the second time — R.2's grid was
the first — and both times the prior result was in this same directory.

### 1.2 Arm A's isolated geometry cannot reproduce the loss it is meant to attribute

Put R.4 and R.4b side by side:

| | condition | our decode rate |
|---|---|---:|
| R.4 | isolated **synthetic**, −14 dB | **100%** (147/147) |
| R.4b | real **corpus**, ≥ +5 dB (far stronger) | **89.8% / 89.0%** |

**On isolated synthetic signals we lose nothing, at signal levels well below where the real corpus
already costs us 10%.** R.3 plants isolated synthetic signals and classifies the failures into
D-miss / X-loss / E-cand. In the SNR band where the real loss lives there will be **no failures to
classify** — the split comes back empty. The only region where R.3 would find anything is the
sensitivity tail below −20 dB, which R.4b has already priced at ~7%.

Even allowing several dB of scale offset between the synthetic `snr_db` and WSJT-X's own estimator
(the standing CPFSK/GFSK and uncalibrated-estimator caveats), the *shapes* do not reconcile: a clean
step from 100% to 0% over ~5 dB, against a shallow curve that tops out at ~90% and stays there. A
10% loss that persists at the strong end cannot be produced by any isolated-signal experiment.

## 2. What this actually tells us — the useful part

The elimination is now sharp, and it is worth more than R.3 would have been:

> **Whatever costs us the 437 is a property of real received audio that isolated synthetic buffers
> do not have.** It is not sensitivity (R.4: 2.62 dB, R.4b: ~7% marginal), not demodulation on clean
> signals (147/147), not candidate capacity (C.1: +12), and not band limits (§2 of the 15:55 note:
> ~1–2%).

Named candidates, none yet measured directly: co-channel collision at close frequency spacing;
channel effects absent from the synthetic generator (fading, drift, multipath); or something in our
own capture/processing chain ahead of the decoder.

**On the co-channel one I want to be careful, because I withdrew that bet an hour ago and I am not
quietly reinstating it.** What I withdrew was the *cycle-density* proxy, which failed to replicate
across corpora and whose rescue I tested and killed. What §2 gives is different: arrival by
elimination rather than by prior. The 15:55 note set the condition for co-channel's return as "R.3's
D-miss dominates *and* the cap axis fails to explain it" — C.1 has now settled the cap half by other
means, and R.3 cannot settle the other half. So the condition is neither met nor refutable as
written, and I am not treating it as met.

## 3. What I am not doing in this note

**Designing the replacement.** The obvious shape is a dense/co-channel ground-truth arm at realistic
signal density, but I have now twice designed an arm without first checking what the existing
results already answer, and the correct response to that is to do the check before the design, not
to write a third arm in the same hour. That design comes after the `libft8.dll` size ruling, which
I committed at 15:55 to writing next and which is genuinely next.

## 4. What QA should do

1. **Do not start R.3.**
2. **One small correction, whenever convenient** — the exact cycle-set intersection behind the 15:55
   note §2's band-floor figure. My ~1–2% is a bound taken over unfiltered `ALL.TXT`; the measured
   number needs the same cycle filter the arms apply. Minutes, not a session.
3. Nothing else. There is no arm to run until the replacement design exists.

## 5. Honest caveats

- **§1.2 rests on comparing two different SNR scales.** The argument is built on the shape mismatch
  rather than on the absolute levels for exactly that reason, but if the synthetic scale is offset
  from WSJT-X's by a large amount the quantitative contrast weakens. The qualitative one — a
  persistent ~10% loss at the strong end — does not, because no offset makes an isolated-signal
  experiment produce a non-zero asymptote.
- **C.1 swept the native `K_MAX_CANDIDATES` at the shipped K=10 configuration.** The K=4/cap2000
  captures are a different regime, and the managed `MaxPass0Candidates` export cap is a third,
  separate constant. §1.1 retires the cap axis *for the shipped configuration*, which is the one
  row 4 is about; it does not merge the three constants.
- **Seven self-corrections now, six of them mine.** This one cost no QA time because it was caught
  before the session started, which is the first time that has been true.

## 6. Cross-references

- `2026-07-26-c1-candidate-cap-sweep-findings.md` §3–§5 — the cap sweep that retires §1.1's axis.
- `2026-07-27-r4-sensitivity-gap-findings.md`, `2026-07-27-r4b-realworld-sensitivity-findings.md` —
  the two results §1.2 puts side by side.
- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §6.1 — the cap axis, retired here.
- `2026-07-27-1555-architect-r4b-ruling-and-band-limits.md` §5, §8 — sequencing superseded; the
  band-floor correction in §4.2 above is its §9 caveat.

---

*Per HK-015 Architect → QA. Per HK-014 committed locally, no further. Per HK-011 nothing touches
`src/` or native code.*
