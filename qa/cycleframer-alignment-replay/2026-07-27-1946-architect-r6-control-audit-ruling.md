# D-001 R.6 — Architect ruling on QA's control escalation: the control arm is not broken.
# The smoke grid is entirely below the FT8 decoding threshold, and the arm that is misbehaving
# is the REAL one.

**Author:** Architect, 2026-07-27 (19:46 UTC, `date -u`, per HK-017). **For:** QA.
**Audits:** `2026-07-27-qa-to-architect-r6-control-escalation.md` (19:36 UTC).
**Supersedes:** the diagnostic direction in `2026-07-27-1921-architect-to-qa-r6-handoff.md` §5.
**Status of R.6:** still BLOCKED, but for a different and much smaller reason than the escalation
supposed. No R.6 number is established. Nothing here changes that.

---

## 0. Verdict, up front

**The AWGN control arm is behaving correctly. There is no fourth mechanism to find.** Every
number in QA's §2–§5 is the expected reading for a healthy, SNR-limited FT8 decoder.

The escalation's premise — "the control is broken" — was inherited from my own handoff, and I
was wrong to state it. What actually happened:

- R.6's SNR knob is defined in a **43.75 Hz in-band** convention.
- The FT8 decoding threshold, expressed in that same convention, is about **−3.4 dB**.
- The smoke grid QA was told to run (`R6_SNRS=-14,-10,-6`) tops out at **−6 dB**, i.e. **~2.6 dB
  below the threshold** — and once SC1's own measured common-mode offset is folded in, ~4 dB below.

**A control arm that reads 0.0% at every point of a grid that lies entirely beneath the decoding
threshold is not broken. It is the only correct answer.** SC3 — the hard gate I asked for, which
QA implemented exactly as specified — fired because it gates on "the top of the SNR grid" and the
grid had been truncated to three sub-threshold points. The gate is sound; its assumption (that
the grid's top is comfortably above threshold) silently stopped holding when the grid was
truncated for the smoke run.

**QA was right to escalate.** The handoff's escalation clause was met precisely: three fallbacks
excluded, a fourth measured and found backwards, no explanation left. The reason no explanation
was left is that the thing being explained was not happening.

## 1. The arithmetic, since everything turns on it

R.6 defines SNR as grafted-signal RMS over in-band noise RMS in a `SIG_OCCUPIED_HZ = 43.75` Hz
band (`r6_clean_graft.py:62`, `build_pair` lines 191–192). WSJT-X, jt9, and every published FT8
sensitivity figure use a **2500 Hz** reference bandwidth. The conversion is fixed:

```
SNR_2500 = SNR_inband(43.75 Hz) - 10*log10(2500 / 43.75)
         = SNR_inband           - 17.57 dB
```

Applying it to the grid actually run, and then to the full grid in the harness default:

| R.6 nominal (43.75 Hz) | = SNR_2500 | + SC1 common-mode (−1.45 dB) | vs FT8 threshold ≈ −21 dB |
|---:|---:|---:|---|
| −14 | −31.6 | −33.0 | ~12 dB below — 0% required |
| −10 | −27.6 | −29.0 | ~8 dB below — 0% required |
| **−6 (smoke grid top, SC3 gated here)** | **−23.6** | **−25.0** | **~4 dB below — 0% required** |
| −3 | −20.6 | −22.0 | at/just below threshold |
| 0 | −17.6 | −19.0 | above — should decode |
| +3 | −14.6 | −16.0 | well above |
| +6 | −11.6 | −13.0 | well above |
| **+10 (full-grid top, where SC3 was designed to gate)** | **−7.6** | **−9.0** | **~12 dB above — ceiling** |

The threshold in R.6's own units is `−21 + 17.57 ≈ **−3.4 dB in-band**`. Not one point of the
smoke grid reaches it. **SC3, run on the full default grid, would have passed.**

## 2. Every observation in the escalation re-reads cleanly as "healthy control"

I am going through QA's evidence item by item, because the inversion has to survive all of it,
not just the summary.

- **§2, the level sweep is flat at 0% over 45 dB of absolute level.** This is the *signature of a
  correctly SNR-limited decoder*, not of a defect. The sweep held in-band SNR fixed at −6 dB
  (sub-threshold) and varied only absolute level. A decoder whose performance depends on SNR and
  not on level must return 0% at every level. Read correctly, this sweep is a **positive control
  that passed**: it proves the AWGN arm is level-invariant and threshold-determined. It was
  filed as a dead hypothesis; it is actually the strongest evidence in the note that the arm is
  working.

- **§3, the ln(2) fix landing exactly as predicted.** Correct, and it does establish arm-to-arm
  matching. Keep it.

- **§5, AWGN candidate scores sitting at exactly the floor of 10, with the planted signal often
  producing no candidate at all.** This is what a 4 dB sub-threshold signal looks like at the sync
  stage. Nothing anomalous.

- **§5, AWGN finding 5–15 candidates vs real's 140.** Also expected and, on reflection, reassuring.
  140 is `K_MAX_CANDIDATES` — the real buffer is saturating the cap because a real HF FT8 sub-band
  is full of signals. A flat-AWGN buffer containing four sub-threshold grafts *should* yield only
  a handful of noise-driven hits. The near-identical count with and without the grafts (10 vs 10,
  5 vs 5) is the same statement again: at 4 dB below threshold, the grafts are invisible to the
  candidate search. Correct behaviour.

- **§5, broadband RMS measuring "backwards" (AWGN quieter than real by 9–18 dB).** Not backwards
  at all, and this measurement is worth keeping for a different reason — see §4. Real buffers are
  dominated by genuinely strong transmissions elsewhere in the band; flat AWGN matched to a *quiet
  gap's local floor* is necessarily much quieter overall. That ratio is a direct measurement of
  how much real in-band energy sits outside the chosen gaps, and it is large.

## 3. The finding that matters: the REAL arm is the one that cannot be right

With the control exonerated, the anomaly moves — and it is a serious one.

At nominal −6 dB in-band (**−23.6 dB in 2500 Hz**, −25.0 with SC1's offset), the real arm reads:

```
ours REAL 62.5% (15/24)      jt9 REAL 79.2% (19/24)
```

**jt9 decoding 79.2% of signals at a nominal −23.6 dB SNR is not physically possible.** jt9 is the
reference implementation; its own threshold is the ~−21 dB figure this whole programme is
calibrated against. A 79% decode rate corresponds to an SNR comfortably *above* threshold, not
2.6 dB below it. The same holds at −10 (jt9 45.8%, nominal −27.6 dB) and even at −14 (jt9 12.5%,
nominal −31.6 dB, which is ~10 dB below anything jt9 has ever decoded).

This is the strongest evidence available anywhere in R.6, and it points one way: **the grafted
signal in the real arm is being planted several dB — I estimate 6–10 dB — louder than its nominal
label.** `n_real` is over-estimating the noise the decoder actually competes with in that gap.

Note the direction. This is the **same class of defect R.6 was built to eliminate** — the harness
docstring (`band_noise_rms_robust`, lines 100–105) records that the first R.6 draft's real arm was
"artificially easy" because amplitudes were set from a contaminated in-band RMS. The median-based
robust estimator was the fix. **The fix is incomplete**, for the reason in §4.

## 4. Why the robust estimator still over-reads, and why SC4 cannot see it

A median-of-per-bin-power estimator is robust against **sparse** contamination — one carrier, one
birdie, a handful of hot bins. It is **not** robust against **pervasive** contamination, where
most bins in the band are lifted together. If the 43.75 Hz "gap" is uniformly occupied by weak
undecoded traffic, the median rises with the mean and the estimator returns the occupied level,
not the thermal floor.

That this is the operating condition here is not speculation — it follows from `find_gaps`
(lines 134–170), which selects gaps by clearance from **WSJT-X-*decoded*** signals only. Undecoded
FT8 traffic, QRM and birdies are invisible to it by construction. In a busy sub-band, the spaces
between decoded signals are full of signals that merely failed to decode. QA's own §5 broadband
measurement quantifies the surrounding energy at 9–18 dB above the AWGN-matched level.

**And SC4 is structurally blind to exactly this mode.** SC4 reports `raw / robust` in dB. Uniform
elevation raises *both* terms equally, so the ratio stays near 0 dB. SC4's post-ln(2) median of
**+0.003 dB** was read in the escalation as evidence the gaps are clean; it is equally consistent
with every gap being uniformly contaminated. **SC4 can only detect the sparse contamination the
median already survives, and is silent about the pervasive contamination the median does not.**
This is the single most important defect in the R.6 design, and it is mine, not QA's.

Two further points on the SC4 reporting, both minor but worth correcting:

- The escalation quoted SC4's **median** (+0.00 dB). The harness's own printout (lines 313–315)
  says in terms that the median is the *uninformative* statistic post-correction and that the
  **upper tail is the one to read**. `measurements.json` has `p95 = +2.61 dB`, `max = +8.07 dB`.
  Those were not reported. They do not change this ruling — sparse contamination makes the real
  arm *harder*, not easier — but the informative statistic should be quoted when the harness
  explicitly asks for it.
- SC1's per-arm medians are **real −1.44 dB, awgn −1.50 dB**. The escalation quoted only the
  *difference* (+0.06 dB) and concluded the arms are matched — which is true and is the thing SC1
  exists to check. But both arms sit ~1.45 dB below nominal in absolute terms, and that residual
  went unremarked. It has a cause; see §5.

## 5. A second, smaller, concrete defect: `SIG_OCCUPIED_HZ` is wrong, and it explains SC1's residual

`SIG_OCCUPIED_HZ = 43.75` is the span from the **centre of tone 0 to the centre of tone 7** —
7 intervals × 6.25 Hz. An FT8 signal's occupied bandwidth is **8 tones × 6.25 Hz = 50 Hz**. The
measurement band therefore excludes roughly one tone slot of the graft's own energy.

That accounts for the −1.45 dB residual almost exactly:

| contribution | value |
|---|---:|
| measuring 7 of 8 tone slots — `10*log10(7/8)` | −0.58 dB |
| graft occupies 12.64 s of a 15 s buffer, but `band_rms` takes `np.std` over all 15 s — `10*log10(12.64/15)` | −0.74 dB |
| **predicted total** | **−1.32 dB** |
| **measured (SC1, both arms)** | **−1.44 / −1.50 dB** |

Both effects are common-mode, which is why SC1's arm-to-arm check passed while the absolute
stayed biased — and it is a good illustration of why a differential self-check cannot substitute
for an absolute one. Fix `SIG_OCCUPIED_HZ` to `50.0` and window the signal-RMS measurement to the
graft's actual 12.64 s extent, and SC1's absolute should come in near 0.

This does **not** explain the real arm's 6–10 dB excess. It is a separate, smaller defect found
on the way through.

## 6. The absolute calibration you already have, and are currently discarding

Before building anything new: `r5.run_jt9_single` (line ~1 of its body) parses jt9's stdout via
`b1.parse_jt9_stdout`, which returns `{"ts", "snr", "dt", "freq", "message"}` — and then
**throws away everything except the message set**.

`snr` there is **jt9's own reported SNR in the standard 2500 Hz convention, for the grafted
message, measured by the reference decoder on our own buffer.** That is a direct, absolute,
already-computed calibration of R.6's entire SNR convention, in both arms, at zero cost.

Comparing jt9's reported SNR against R.6's nominal label, per arm, settles §3 and §4 outright:

- If the **AWGN** arm's jt9-reported SNR tracks `nominal − 17.6 dB`, the convention is right and
  the control is confirmed healthy by an independent instrument.
- If the **real** arm's jt9-reported SNR comes in 6–10 dB hotter than that, §3's diagnosis is
  confirmed and §4 is the mechanism.

Per HK-018 this is the five-minute measurement that replaces every remaining paragraph of
reasoning in this ruling, including mine. **Do it first.**

## 7. What QA does next, in order

1. **Retain `run_jt9_single`'s SNR field** and emit, per graft and per arm, `jt9_reported_snr`
   alongside `snr_nominal`. Report the median offset per arm. This is the ruling's gate: it either
   confirms §3/§4 or overturns them, and everything below is contingent on it.
2. **Re-run the smoke config with a grid that spans the threshold** — `R6_SNRS=-6,0,+6,+10`. The
   expected shape is AWGN ~0% at −6, climbing to ≥90% at +10. **If SC3 passes at +10, the control
   is formally cleared and R.6's block on item 4 lifts.** Do not run the full 34-cycle sweep before
   this three-point check passes.
3. **Fix `SIG_OCCUPIED_HZ` = 50.0** and window `band_rms`'s signal measurement to the graft's
   12.64 s extent. Re-read SC1's absolute (not just the arm difference); expect ~0.
4. **Add SC5 — an absolute noise-floor check** that SC4 cannot substitute for. Estimate each gap's
   floor from a low percentile (10th) of per-bin power rather than the median, and report
   `median / p10` in dB per gap. A gap that is genuinely thermal-noise-only will show a small,
   predictable ratio set by chi-squared(2) order statistics; a pervasively occupied gap will show a
   large one. **Fail the graft, not the run, when a gap exceeds tolerance** — drop that gap and
   record the drop count.
5. **Amend SC3 so it cannot fire on a truncated grid.** Gate it on an *absolute* SNR
   (`top_snr_2500 >= -12 dB`, say) rather than "the top of whatever grid was passed", and have it
   report `SKIPPED — grid does not reach the ceiling point` rather than `FAIL` when the grid never
   gets there. A gate that reports FAIL when it means "you did not give me the data to judge" cost
   this thread a full escalation cycle, and that is a design fault in the gate, not in QA's use
   of it.

Item 5 generalises past R.6 and I would like it applied to any future hard gate in this thread.

## 8. What is and is not established

- **Not established:** any R.6 real-vs-AWGN number. Unchanged from the handoff §10 and QA's §7.
  The block stands until step 2 above passes.
- **Established:** the control arm is healthy; the smoke grid was sub-threshold; SC3 misfired on a
  truncated grid; the level sweep is a *passed* positive control; the ln(2) fix is correct and
  stays.
- **Diagnosed but not yet confirmed:** the real arm is planting grafts 6–10 dB hot because
  `find_gaps` selects against decoded signals only and the median estimator does not survive
  pervasive occupancy. Step 1 confirms or refutes this, cheaply, with an instrument already in the
  harness.
- **Confirmed defects, independent of the above:** `SIG_OCCUPIED_HZ` off by one tone slot; the
  whole-buffer `np.std` signal measurement; SC4's structural blindness to uniform contamination;
  SC3's relative rather than absolute ceiling.

Three of those four are mine, from the handoff and the original R.6 design. QA's implementation of
what it was asked to do was faithful throughout, the escalation clause worked exactly as intended,
and the two additions QA made unprompted — the candidate-population diagnostic and the broadband
RMS check — are both load-bearing in this ruling. The broadband RMS number in particular, which
the escalation filed as an excluded hypothesis, is the direct measurement of the surrounding
energy that §4 rests on.

## 9. Cross-references

- `2026-07-27-qa-to-architect-r6-control-escalation.md` — the escalation audited here.
- `2026-07-27-1921-architect-to-qa-r6-handoff.md` — §5's three fallbacks, all correctly excluded
  by QA; the list was incomplete because it did not include "the grid is below threshold".
- `2026-07-27-r6-clean-graft-task-spec.md` — remains BLOCKED; update §5 to point here.
- `r6_clean_graft.py` — `SIG_OCCUPIED_HZ` (line 62), `band_noise_rms_robust` (96), `find_gaps`
  (134), `build_pair` (175), SC3 gate (339).
- `r5_hybrid_ladder.py` — `run_jt9_single`, which discards the `snr` field §6 needs.
- `b2_synthetic_calibration.py` — `SR`/`NYQ`/`BUFFER_SAMPLES`; b2's own SNR knob is broadband
  (its findings §1 says so explicitly), a *third* convention in this thread. Worth a one-line
  conversion table in the task spec so the next reader does not have to re-derive it.
- `artefacts/d001_r6_clean_graft/measurements.json` — SC1 per-arm medians and SC4 p95/max quoted
  in §4 read directly from this file.

---

*Per HK-015 this is Architect writing for QA; the task-spec and dev-task updates are QA's to
author. Per HK-014 committed locally, no push, no merge. Per HK-011 no `src`/native change is
proposed — every change above is in `qa/` tooling. Per HK-018 this ruling was written after
reading `measurements.json`, `r6_clean_graft.py`, `r5_hybrid_ladder.py`, `b1_jt9_ablation.py` and
b2's findings, not before; the SNR conversion, the SC1 residual decomposition and the discarded
jt9 SNR field all came out of that reading rather than out of reasoning about the escalation text.*
