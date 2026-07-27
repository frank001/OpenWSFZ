# D-001 R.6 — Addendum: the jt9-SNR calibration is run. The control is confirmed healthy by
# measurement, the convention is confirmed sound, and my own §3/§4 mechanism is REFUTED.

**Author:** Architect, 2026-07-27 (19:57 UTC, `date -u`, per HK-017). **For:** QA.
**Amends:** `2026-07-27-1946-architect-r6-control-audit-ruling.md` — §0/§1/§2 stand and are now
measured rather than argued; **§3 and §4 are withdrawn** in the form they were written.
**Harness:** `r6_jt9_snr_calibration.py` (new, `qa/` only). **Data:**
`artefacts/d001_r6_jt9_snr_calibration/calibration.json`.

---

## 0. Why this exists

The 19:46 ruling ended by telling QA to run this measurement first, because the ruling's own
central mechanism was unconfirmed. On the Captain's instruction I ran it myself rather than
hand a possibly-wrong diagnosis to QA. It took four minutes and it caught a wrong ruling of mine
before anyone implemented against it — which is the whole of HK-018, applied to its author.

`r5.run_jt9_single` discards jt9's reported `snr`. `r6_jt9_snr_calibration.py` keeps it and
changes nothing else: `r6.build_pair` is imported and called **verbatim**, so this measures the
harness as it actually stands. Grid `-6, 0, +6, +10` in-band, 4 cycles, 4 grafts, 16 signals/cell.

## 1. Result

Prediction under test: `jt9_snr - nominal = -10*log10(2500/43.75) = -17.57 dB`, both arms.

```
  SNR |  arm |      decoded | jt9 snr (med) |  jt9-nominal | vs predicted
------------------------------------------------------------------------------
   -6 | real | 100.0% (16/16) |         -23.5 |       -17.50 |        +0.07
   -6 | awgn |   0.0% ( 0/16) |            -- |           -- |           --
   +0 | real | 100.0% (16/16) |         -17.5 |       -17.50 |        +0.07
   +0 | awgn | 100.0% (16/16) |         -18.0 |       -18.00 |        -0.43
   +6 | real | 100.0% (16/16) |         -10.5 |       -16.50 |        +1.07
   +6 | awgn | 100.0% (16/16) |         -12.0 |       -18.00 |        -0.43
  +10 | real | 100.0% (16/16) |          -6.5 |       -16.50 |        +1.07
  +10 | awgn | 100.0% (16/16) |          -8.0 |       -18.00 |        -0.43
```

## 2. What is now established by measurement, not argument

**2.1 The SNR convention is sound.** Measured jt9-minus-nominal is **−17.50 dB** against a
predicted **−17.57 dB**. The 43.75 Hz → 2500 Hz conversion in ruling §1 is correct to within
jt9's own reporting granularity. Every number in that ruling's conversion table stands.

**2.2 The AWGN control arm is healthy — measured.** It goes **0% at −6, then 100% at 0, +6 and
+10**. That is precisely the shape ruling §1 predicted from the threshold arithmetic. The AWGN
arm's jt9 offset is **exactly −18.00 dB at all three decoding points** — perfectly linear
tracking, which is what a correctly-constructed control looks like under an independent
instrument.

**SC3 passes at the full grid's top with 100%, against its 90% bar.** The escalation's premise is
now dead by measurement as well as by arithmetic: **the control arm was never broken, and the
smoke grid was simply sub-threshold.** R.6's block on the full sweep, on the grounds that the
control is broken, **lifts**.

**2.3 The level sweep and candidate diagnostics re-read as ruling §2 said.** Nothing in QA's
escalation evidence needs re-explaining.

## 3. What is REFUTED — my own §3 and §4

Ruling §3 estimated the real arm was planting grafts **6–10 dB hot**, and §4 gave the mechanism:
`find_gaps` clears only against WSJT-X-*decoded* signals, so gaps are pervasively occupied, and a
median estimator survives sparse but not uniform contamination.

**Measured real-minus-AWGN excess: +1.00 dB.**

That is not 6–10 dB. **The mechanism in §4 is refuted and I withdraw it.** The gaps are not
pervasively contaminated to any material degree; `band_noise_rms_robust` is doing its job; the
real arm is at most ~1 dB hot and the drift is small and orderly (−17.5 dB offset at −6 and 0,
−16.5 dB at +6 and +10).

I got there by reasoning from a single anomalous number — jt9's 79.2% at a nominal −23.6 dB in
the earlier run — to a mechanism large enough to explain it, without measuring the mechanism. The
number was real; the size I inferred from it was wrong. **§4's claim that SC4 is structurally
blind to uniform contamination remains true as a statement about SC4** — a ratio of raw to robust
genuinely cannot see uniform elevation — but it is now a latent weakness in a self-check rather
than an active defect explaining anything, and it should be filed as such, not chased.

## 4. What the measurement opens up, which is R.6's actual question

Look at the −6 row:

```
   -6 | real | 100.0% (16/16)  jt9 reports -23.5 dB
   -6 | awgn |   0.0% ( 0/16)
```

At a level difference the same run measures as **~0.5–1.0 dB**, the real arm decodes **16/16** and
the control decodes **0/16**. jt9 — the reference decoder, on byte-identical treatment — is
reliably decoding at a *reported* −23.5 dB in real audio and failing completely in flat AWGN at
essentially the same level.

Two readings, and I am deliberately not choosing between them here:

1. **The FT8 cliff is genuinely that steep and we are sitting exactly on it.** −6 in-band is
   within a decibel of the hard sensitivity floor; a 1 dB edge could plausibly carry 0/16 to
   16/16. If so this row is uninformative about environment and the answer is to measure the
   curve, not one point.
2. **Real audio is genuinely easier than flat AWGN at threshold**, for a reason worth naming —
   which would be a real finding, and notably in the *opposite* direction to D-001's founding
   worry that our decoder underperforms in real conditions.

Distinguishing them is one run: **a fine grid across the cliff (−8 to −2 in-band, 1 dB steps),
both arms, both decoders.** If both arms show the same steep curve merely offset by ~1 dB,
reading 1 is right and R.6's fork is answered "environment is not the problem". If the AWGN arm's
curve is displaced by much more than the measured level difference, reading 2 is right and R.6
has found something.

**This is now R.6's original (A)/(B) fork, askable cleanly for the first time** — with a
confirmed convention and a control arm proven healthy at ceiling.

## 5. Smaller items, updated

- **`SIG_OCCUPIED_HZ` = 43.75 vs 50 Hz (ruling §5).** Untouched by this measurement — the
  −17.57 dB conversion is correct *for this comparison* regardless, because the graft amplitude is
  set from noise measured in the same 43.75 Hz band that the conversion uses. The §5 claim is
  about SC1's *absolute* signal reading, and it stands unverified. Worth noting only that the AWGN
  arm's constant −0.43 dB residual is the right order for a small systematic of this kind; I am
  not claiming that as confirmation.
- **SC3's relative-vs-absolute ceiling (ruling §7 item 5).** Stands, and is now the single most
  valuable fix in the ruling: had SC3 gated on an absolute SNR, or reported `SKIPPED` instead of
  `FAIL` when the grid never reaches the ceiling point, this entire escalation cycle would not
  have happened.
- **SC4's blindness (§3 above).** Downgrade from defect to known limitation; document, don't chase.

## 6. Revised next steps for QA, replacing ruling §7

1. **Run the fine cliff grid** (§4): `R6_SNRS=-8,-7,-6,-5,-4,-3,-2`, both arms, both decoders,
   with jt9's reported SNR retained. This answers R.6's fork.
2. **Fix SC3 to gate on an absolute SNR** and to report `SKIPPED` rather than `FAIL` on a grid
   that never reaches the ceiling point. (Ruling §7 item 5, unchanged.)
3. **Fold `r6_jt9_snr_calibration.py`'s SNR retention into `r6_clean_graft.py` itself** — jt9's
   reported SNR should be a standing output of the main harness, not a side script. It is the only
   absolute instrument in R.6 and it was being discarded.
4. **Fix `SIG_OCCUPIED_HZ` = 50.0 and window the signal RMS** to the graft's 12.64 s extent
   (ruling §5), then re-read SC1's absolute.
5. **Drop ruling §7 item 4 (SC5 / p10 floor check).** It was designed against the mechanism §3
   above refutes. Do not build it.

Item 5 matters: the 19:46 ruling would have had QA build a self-check for a defect that does not
exist. That is the cycle this measurement saved.

## 7. Standing

- **R.6 unblocked** for the sweep, the control having been demonstrated at ceiling.
- **Still no R.6 real-vs-AWGN number is established.** §4's fine grid produces the first one that
  can be quoted. Nothing in this addendum is a result about the decoder.
- Ruling §0/§1/§2 stand and are strengthened. Ruling §3/§4 withdrawn. Ruling §5/§7-item-5 stand.

## 8. Cross-references

- `2026-07-27-1946-architect-r6-control-audit-ruling.md` — amended here.
- `2026-07-27-qa-to-architect-r6-control-escalation.md` — QA's escalation; premise now measured
  dead, and the escalation itself was correct procedure throughout.
- `r6_jt9_snr_calibration.py` — new, `qa/` only, imports `r6.build_pair` verbatim.
- `artefacts/d001_r6_jt9_snr_calibration/calibration.json` — every number in §1.

---

*Per HK-015 this is Architect writing for QA; the task-spec update remains QA's to author. Per
HK-014 committed locally, no push, no merge. Per HK-011 no `src`/native change. Per HK-018 the
central claim of my own prior ruling was measured before QA was asked to act on it, and it did not
survive — recorded as a withdrawal rather than quietly dropped.*
