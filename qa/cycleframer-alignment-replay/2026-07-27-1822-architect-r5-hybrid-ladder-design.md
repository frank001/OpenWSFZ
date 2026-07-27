# D-001: R.3 replaced by R.5 — the hybrid ladder. Two more hypotheses killed on the way in

**Author:** Architect, 2026-07-27 (18:22 UTC, `date -u`, per HK-017). **For:** QA (to scope and run).
**Delivers:** the R.3 replacement owed since 16:03.
**Design: R.5, a bisection between the two conditions we have already measured** — 100% on isolated
synthetic, 61% on real corpus audio. Every prior arm probed one endpoint. This one interpolates.

---

## 1. The pre-design check, and what it killed

Per HK-018 I checked what the existing results already answer before designing. Two of the three
candidate mechanisms I named at 16:03 are dead, and one of them was already dead when I named it.

### 1.1 Co-channel is not merely unreplicated — C.3 refuted it, with the right instrument

At 15:55 I withdrew the co-channel bet on weak grounds (the cycle-density proxy failed to replicate)
and said the proper instrument would be *frequency proximity, not cycle density*. **C.3 had already
run exactly that**, and the result is the opposite of the hypothesis:

> Mann-Whitney U **p = 5.4×10⁻⁵²**, the gap population **farther** from a decoded neighbour, not
> closer — and the effect survives stratification by SNR band, so it is not an SNR confound.

C.3's own conclusion says it plainly: "the specific structural mechanism it named (SIC/co-channel
masking) is **not** what the data shows."

**Co-channel collision is refuted, not open.** I listed it at 16:03 as the leading remaining
candidate. That was the fifth time today I have reasoned past a result already on record; this time
the check caught it before it became a design.

### 1.2 Frequency-dependent noise reference is refuted too — I tested it just now

The shim documents a 28 dB audio-chain rolloff (signal_db −39.7 dB at 800–1000 Hz falling to
−67.5 dB at 2800–3000 Hz, `ft8_shim.c:110–125`). D-003/D-004 made the *reported SNR* rolloff-invariant
by switching to a local sideband noise estimate — but that is the display path, not the decode path.
A plausible hypothesis: candidate scoring or LLR normalisation still uses a band-global reference,
so signals at the quiet end are scored against a reference set by the loud end.

**Tested against corpus 1 directly** — P(we decoded | WSJT-X decoded), by frequency:

| freq bin | hit | miss | P(decode) |
|---|---:|---:|---:|
| 0–399 | 95 | 36 | 72.5% |
| 400–799 | 161 | 66 | 70.9% |
| 800–1199 | 184 | 166 | **52.6%** |
| 1200–1599 | 236 | 163 | 59.1% |
| 1600–1999 | 200 | 203 | **49.6%** |
| 2000–2399 | 210 | 96 | 68.6% |
| 2400–2799 | 122 | 57 | 68.2% |
| 2800–3199 | 27 | 6 | **81.8%** |

**No rolloff signature.** There is no monotone trend, and the *highest* band — where the rolloff is
worst — is the **best** performing at 81.8%. The hypothesis predicts the opposite. Killed.

### 1.3 What the same table does show, and the tension it creates

P(decode) swings from 49.6% to 81.8% across the band, and the two worst bins (800–1199, 1600–1999)
are the two busiest. That looks like crowding — but C.3's nearest-neighbour analysis says misses are
*farther* from neighbours, at p = 5.4×10⁻⁵².

**Both are measured; I am not going to resolve them by assertion.** They are compatible only if the
effect operates at a *band-segment* scale (aggregate energy over hundreds of Hz) rather than a
*nearest-neighbour* scale. That is a real, specific, testable distinction, and R.5 is built to test it
without needing me to pick a side first.

## 2. What is left standing

Everything decoder-internal has now been excluded by measurement: sensitivity (2.62 dB, ~7% marginal),
demodulation on clean signals (147/147), candidate capacity (+12), band limits (~1–2%), harmonics
(≤ −49 dBc), co-channel proximity (refuted, p = 5.4×10⁻⁵²), frequency-dependent noise reference
(refuted, §1.2).

> **The loss is a property of real received audio, distributed across the band, that isolated
> synthetic buffers do not reproduce — and it is not any of the seven mechanisms above.**

Every arm so far has probed one of two endpoints: **isolated synthetic, where we score 100%**, or
**real corpus, where we score 61%**. Neither endpoint can name what separates them. That is the gap
R.5 closes.

## 3. R.5 — the hybrid ladder

**Question.** Which property of real audio, added to a synthetic buffer, collapses our decode rate
from ~100% to ~61%?

**Method.** Build a ladder of buffers that interpolates between the two measured endpoints, one
property at a time, and decode each rung with **our decoder and jt9 on byte-identical audio**. Ground
truth is exact on every synthetic component and is WSJT-X's decode set on every real component.

| rung | signals | noise/background | what it adds |
|---|---|---|---|
| **0** | synthetic, isolated (8/buffer) | synthetic AWGN | the R.4 baseline — must reproduce **147/147** or the harness is wrong |
| **1** | synthetic, **at real density and real (f, dt) layout** taken from a real cycle's WSJT-X decode list | synthetic AWGN | population geometry only |
| **2** | synthetic, real layout, **at each message's real reported SNR** | synthetic AWGN | plus real amplitude distribution |
| **3** | synthetic, real layout, real SNRs | **real captured band noise**, signals notched out of a real cycle | plus the real noise environment |
| **4** | **real** signals (the real cycle, unmodified) | real | the R.4b endpoint — must reproduce **~61%** |

**The rung at which P(decode) collapses names the property.** Rungs 0 and 4 are self-checks with
known answers; rungs 1–3 are the measurement.

**Sizing.** 20 real cycles drawn from corpus 1, each producing 5 rungs = 100 buffers, both decoders.
Comparable to R.4's 51 buffers. Report P(decode) per rung with Wilson intervals, and **always report
jt9 on the same rungs** — a rung where jt9 also collapses is a property of the audio, not of us.

**Reading rule, fixed now, before any number exists:**

| collapse first appears at | reading |
|---|---|
| **Rung 1** (density/layout alone, synthetic noise, uniform SNR) | The mechanism is **population geometry** — how many signals and where, independent of their strength or the noise. Points at candidate ranking/selection under load. Cheapest of the four to act on. |
| **Rung 2** (adding the real SNR distribution) | The mechanism is **dynamic range** — strong signals impairing our handling of weak ones in the same buffer. Classic AGC/normalisation-scaling territory, and it would explain the ~10% strong-signal asymptote and §1.3's busy-bin dip together. **This is the one I would bet on**, and I am flagging the bet so it can be held against me. |
| **Rung 3** (adding real noise) | The mechanism is the **noise environment** — non-white, non-stationary background our AWGN model does not represent. Hardest to act on; would make row 4 substantially more expensive and materially strengthen row 5. |
| **Rung 4 only** (no synthetic rung reproduces it) | Nothing about the *content* explains it; the difference is in the **capture/processing chain** ahead of the decoder, not the decoder. Would redirect the whole study and is the most surprising outcome. |
| **No collapse anywhere** | Harness failure, not a result. Rung 4 must reproduce ~61%; if it does not, the arm is void. |

**If jt9 collapses on the same rung as us**, that rung's property is hard for *any* decoder and the
437 is not attributable to our implementation on that axis — report it as such and move to the next
rung.

**Cost:** roughly one QA session. Buffer generation reuses B.2's synthesiser and R.4's persisted
harness; the notching for rung 3 is the only new tooling and it is a spectral mask, not an algorithm.

**Stop rules.** Rung 0 must reproduce 147/147 and rung 4 must reproduce ~61%; either failing is a
self-check failure reported as such, not a result. Per today's standing check, every rung's output
header states the search band each decoder used. Per §1.2's method, per-signal rows are persisted —
that property is what made R.4's slot-7 defect findable in four minutes.

## 4. Why this and not another synthetic arm

R.3 failed because it probed the endpoint we already understood. Every candidate mechanism I have
named across three notes has been refuted by an existing measurement or a five-minute check — which
is itself the finding: **enumerating mechanisms and testing them one at a time has a bad track record
in this study, and my enumerations have twice failed to contain the answer.**

R.5 does not require me to guess correctly. It brackets the unknown between two measured endpoints
and bisects. Whatever the property is, it is added at exactly one rung, including a rung for "none of
the content — it's the capture chain," which no enumeration of mine would have produced.

## 5. What this does not authorise or settle

- **No `src/` or native change** (HK-011). R.5 uses shipped, default-off diagnostic exports.
- **No push, no merge** (HK-014/HK-010); **no `pre_merge_check.py`** (HK-006, Captain's trigger).
- **R.2 stays deferred**, R.3 stays cancelled — not held, cancelled; §1 and the 16:03 note between
  them leave it nothing to measure.
- **Row 5 untouched.** Rows 2 and 3 stay sequenced behind row 4.
- **NFR-021:** synthetic messages are Q-prefix by construction; real-cycle work touches callsigns only
  inside git-ignored `artefacts/` and reports counts only.
- **Per HK-015 this is a design for QA to scope and author**, not a task issued to a Developer.

## 6. Honest caveats

- **§1.2's frequency table is mine, computed inline from the corpus `ALL.TXT` pair, not a QA arm.**
  It matches on `(cycle, normalised message)` using the study's own `normalize_hash_tokens`, and gets
  hit=1235/miss=793 against the study's own 1239/789 — a 4-message discrepancy from cycle-set edges I
  did not chase. It is sound as a shape; QA should recompute properly if any number from it is quoted.
- **CPFSK vs GFSK** carries into rungs 0–3 and is most exposed at rung 2, where synthetic amplitudes
  are matched to real reported SNRs across a synthetic/real boundary.
- **WSJT-X's reported SNR is its own estimator**, so rung 2's amplitudes inherit its calibration.
- **Rung 3's notching is imperfect by construction** — removing 30 signals from real audio leaves
  residue, and the residue is itself a real-audio property. If rung 3 shows partial collapse this
  caveat is load-bearing.
- **I have now named a favourite (rung 2) before the data exists.** That is stated so it can be held
  against me, and the reading rule was fixed before the bet, not after.

## 7. Cross-references

- `2026-07-26-c3-candidate-generation-gap-findings.md` §§ on hypothesis (b) — the p = 5.4×10⁻⁵²
  proximity refutation §1.1 rests on.
- `2026-07-26-b2-synthetic-calibration-findings.md` §3 — Arm B's location-rate selection bias, which
  is why R.5 uses ground-truth planting rather than Arm B's located-conditioned population.
- `2026-07-27-r4-sensitivity-gap-findings.md` (147/147, rung 0's target),
  `2026-07-27-r4b-realworld-sensitivity-findings.md` (the ~61%/asymptote, rung 4's target).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:110–125` — the rolloff and the D-003/D-004 local-noise fix §1.2
  tested.
- `2026-07-27-1603-architect-hold-r3.md` — R.3's cancellation; §1 above removes its last candidate.
- `2026-07-27-1752-architect-to-qa-consolidated-handoff.md` — §2.2's exclusion table, extended by §2.

---

*Per HK-015 Architect → QA. Per HK-014 committed locally, no push. Per HK-011 nothing here touches
`src/` or native code. Row 4 vs. row 5 remains the Captain's decision, on the Captain's clock.*
