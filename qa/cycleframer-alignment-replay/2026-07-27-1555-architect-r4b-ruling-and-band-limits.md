# D-001: the Captain's 5 kHz observation checked (ceiling costs nothing, floor costs ~1–2%), R.4b accepted, the co-channel bet withdrawn

**Author:** Architect, 2026-07-27 (15:55 UTC, `date -u`, per HK-017). **For:** QA (to run), and the
Captain (§2, §7).
**Answers:** the Captain's WSJT-X wide-graph observation (§2), and
`2026-07-27-1543-qa-to-architect-r4b-notification.md` §5 (§6 below).
**Ruling: R.4b accepted as run. Our *upper* band limit costs essentially nothing; our *lower* one
costs ~1–2% of the miss population and is worth a look. The co-channel hypothesis I said I would bet
on does not survive its first direct test, and I am withdrawing the bet.**

---

## 1. Short answer

**The Captain's observation is correct and was worth checking — but it does not bite where it
looks like it should.** WSJT-X does feed its decoder to 5 kHz with a hard cutoff and no user
setting; our shim is `f_min = 200.0f, f_max = 3000.0f` (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1363`).
That is a real capability difference. But on both corpora, **WSJT-X decoded nothing meaningful above
3000 Hz** — 0 of 2684 on corpus 1 (max 2928 Hz), 9 of 43,707 on corpus 2 (max 3095 Hz). Standard FT8
traffic lives inside the first 3 kHz of the passband whatever the decoder is willing to search.

**The interesting half is the other end.** Corpus 2's lowest WSJT-X decode is **132 Hz** — below our
`f_min = 200`. Out-of-band decodes below 200 Hz run at **0.60% (corpus 1) / 0.34% (corpus 2)** of all
decodes, which lands at roughly **1–2% of the miss population**. Small, but it is a *free* class of
miss in the sense that no decoder algorithm is involved — we simply do not look there.

On R.4b: **accepted.** "None of the three rows fires cleanly" is itself the finding, and my table was
at fault for assuming one mechanism dominates. The number of record is the **high-SNR asymptote,
89.8% / 89.0%**, and §2 below now accounts for one to two points of that ~10% structural deficit.

And QA's zero-shift control (§5) is the best piece of methodological work anyone has done in this
thread. It is also self-applied, which is the part that matters.

## 2. The band limits, checked on both corpora

Our search band is 200–3000 Hz. WSJT-X's is roughly 200–5000 Hz with the low edge user-adjustable.
Counting every WSJT-X decode outside our band:

| | corpus 1 (40m) | corpus 2 (20m) |
|---|---:|---:|
| total WSJT-X decodes | 2,684 | 43,707 |
| **below 200 Hz** (our `f_min`) | **16 — 0.60%** | **148 — 0.34%** |
| **above 3000 Hz** (our `f_max`) | **0 — 0.00%** | **9 — 0.02%** |
| lowest / highest decode | 193 / 2928 Hz | 132 / 3095 Hz |

### 2.1 The ceiling: costs nothing here, but it is a cliff rather than a slope

Zero decodes above 3000 Hz on corpus 1 and nine on corpus 2. **None of the 437 is attributable to
our upper limit.** WSJT-X searching to 5 kHz buys it nothing on this traffic, because FT8 operating
convention puts everyone inside a 3 kHz sub-band. Our `f_max = 3000` is correctly placed *for this
operating pattern* and is not a defect.

**But it is worth the Captain knowing it is a hard edge, not a soft one.** If the dial offset ever
changes, or a band/contest/mode puts activity above 3000 Hz, we would lose **all** of it silently
while WSJT-X kept decoding — and no arm of this study would show it, because every arm measures
against a corpus captured under the current operating pattern. It costs nothing today. It is not
guaranteed to cost nothing tomorrow, and the failure mode is silent.

### 2.2 The floor: a real, if small, contribution — and not free to claim

16 and 148 decodes sit below our `f_min = 200`, concentrated at 120–200 Hz. As a share of *all*
decodes that is well under 1%; as a share of the **miss** population — which is what row 4 is about —
it is roughly **1–2%**, since every one of them is necessarily a miss for us. (Exact figure needs
the cycle-set intersection; see §8.)

That is the same order as R.4b's marginal sensitivity estimate (7.4%/6.8%) is large — i.e. small but
not negligible, and unlike everything else in this study **it requires no algorithmic work at all**,
just a constant.

**It is not free, though, and I want to be explicit about why before anyone treats it as a quick
win.** Three reasons:

1. **Below 200 Hz is soundcard rumble, mains hum and its harmonics.** This is precisely why WSJT-X
   exposes a low-cut setting and why the Captain found one — it exists to *remove* that noise. Our
   200 Hz floor is plausibly a deliberate, correct choice rather than an oversight.
2. **NFR-018.** Decoding into a noise-dominated region is the classic false-positive generator, and
   FP behaviour is a hard requirement in this project, not a preference.
3. **Widening either edge enlarges the candidate search space**, which interacts directly with
   `MaxPass0Candidates` — the constant that has now silently truncated three diagnostics in this
   study. A wider band with the same cap could *lose* more than it gains.

**So: worth measuring, not worth assuming.** If it is pursued it is a `src/`+native change under
HK-011 — a Developer session with a pre-push sign-off — and it should be justified by a measurement
of the FP/decode-time cost, not by the 1–2% alone. **I am not commissioning it now.** Row 4's
decision does not turn on it, and it should not be allowed to displace R.3.

### 2.3 Third instance of the same defect class in two hours

This matters more than the numbers:

- **R.4's slot 7** — planted above our search ceiling; counted as a sensitivity deficit (15:22 §2).
- **The corpus floor** — WSJT-X decodes below our search floor; would have been counted as a
  detection or demodulation failure by any arm that looked.
- **The corpus ceiling** — checked, and clean, but only because we finally looked.

Two of the three were live, and both would have been attributed to decoder *quality*. **Standing
check, added now:** before any gap between two decoders is attributed to algorithm quality, the
search band each one actually used must be stated and their intersection verified. Every arm's
output header should carry the band it searched. This is cheap and it has already paid twice today.

I would not have gone looking for either of them without the Captain's observation. It is the second
time in this thread that a question from outside the study's own framing has caught something the
framing could not see.

## 3. R.4b — accepted

**Self-checks pass; §11's verification is answered.** QA reconstructed the per-slot rows
independently rather than from my regrouping, and tested both my wholesale slot-7 exclusion and a
stricter per-signal occupied-spectrum test. Both give **ΔSNR = 2.625 dB**, identical to three
decimals. That is a better verification than I asked for — it tests the *rule*, not just the number,
and it closes my 15:22 §11 caveat completely. **2.62 dB is final.**

### 3.1 The zero-shift control

QA computed a naive shift-model estimate of **56.4% / 52.0%**, which sits close enough to
jt9-depth-1's real 55.4% / 55.8% coverage to look like a decisive result — sensitivity explaining
the whole gap after all. Before reporting it, QA ran the **same computation at shift = 0** and found
the baseline is already **49.0% / 45.2%**. Almost the entire apparent effect was baseline
probabilistic non-determinism, not anything a sensitivity improvement buys. The marginal figure is
**7.4% / 6.8%**.

**This is the single best methodological act in this thread, and I want it on the record as such.**
A number that would have overturned the study's direction was caught, before it left QA's desk, by
constructing the control that isolates it. Five of the six self-corrections logged so far were mine
and were caught by me auditing my own designs after the fact. This one was caught *before* it
propagated, by the person who produced it. That is a better place for the check to live.

### 3.2 "None of the three rows fires cleanly" — the reading

**That outcome is a finding, and the fault is in my table, not in the data.** All three rows were
written as though one mechanism would dominate: saturation → structural, broad shortfall →
sensitivity, density gradient → co-channel. The result says the loss is **distributed** — no single
mechanism in my enumeration owns it. My table had no row for that, which is the same drafting error
as R.1b's row 2: I wrote branches for the answers I expected.

Taking the three results at face value:

- **Asymptote 89.8% / 89.0% at ≥ +5 dB.** This is the number of record from R.4b. **At strong
  signal, where sensitivity cannot be the explanation, we still lose ~10% of what WSJT-X gets.**
  Short of my 95% bar, so row 1 does not fire — but it is high, and it is now partly decomposable:
  **§2.2's band-floor misses are 1–2 points of that ~10**, leaving a structural residue of roughly
  8% for R.3 to attribute.
- **Marginal shift 7.4% / 6.8%.** Sensitivity is a minority contributor. Third independent
  instrument to say so.
- **Density split +5.8 / +1.6.** §4.

### 3.3 On the step model's number surviving — QA's §3.1, and the precise statement

QA is right to put this on the record and right that the 15:22 rejection should not read as having
been aimed at the wrong target. The exact position:

**The model was correctly rejected; the quantity it estimated was approximately right.** Those are
compatible, and the second does not rehabilitate the first. A step model whose own companion
statistic falsifies it cannot be trusted *even when it lands near the truth*, because nothing about
its construction told us it would — that it did is now known only because a differently-constructed
estimator was built to check.

What we have gained is real and is better than either estimate alone: **two estimators built on
different assumptions — a step threshold on raw counts, and a marginal shift of a measured
probability curve with a zero-shift control — agree at ~6–7%.** That agreement is evidence about the
quantity. It is not evidence about the model, and the ~7.4%/6.8% marginal figure is the one to quote
because it is the one whose construction we can defend.

## 4. The co-channel bet — withdrawn

In the 15:22 note I said co-channel was the branch I would "bet on given C.3." **The first direct
test does not support it, and I am withdrawing the bet rather than defending it.**

The density split gives **+5.8 points on corpus 1** (21/34 well-powered bins) but only **+1.6 points
on corpus 2** (15/37, near noise). One corpus, modest, no replication. Every other cross-corpus
claim in this study has been held to a replication standard — B.1b exists precisely for that — and
this one fails it.

**I tested the obvious rescue, and it failed.** The natural defence is that corpus 2 lacks the
density dynamic range to show the effect. It does not. Decodes per cycle:

| | p10 | median | p90 | p90/p10 |
|---|---:|---:|---:|---:|
| corpus 1 (40m) | 23 | 28 | 36 | 1.57 |
| corpus 2 (20m) | 19 | 27 | 35 | **1.84** |

**Corpus 2 has *more* density spread than corpus 1, not less, and still showed +1.6.** The
non-replication is not a power artefact. I went looking for a reason to keep the hypothesis and the
data took it away.

**Consequence — answering QA's §5 directly: no Arm B, not now.** Designing a co-channel arm on the
strength of a hypothesis whose first direct test came back one-corpus-and-modest would be exactly
the error that produced R.1b's row 2 and R.2's unmeasured grid: building instruments around a belief
the data has not earned. **Co-channel returns to the queue only if R.3's D-miss class dominates
*and* the candidate-cap axis fails to explain it** — at which point it is the leading survivor by
elimination rather than by my prior.

## 5. R.3 — unchanged, plus the band header

R.3 as amended at 14:44 §6 and 15:22 §6 stands: cap axis (600 / 2000 / uncapped), SNR axis,
tolerance ladder, D-miss / X-loss / E-cand classes, per-signal failure reporting, band-intersection
self-check. **One addition from §2.3:** every arm's output header states the search band actually
used by each decoder involved.

No prior is installed on D-miss, for the reason given at 15:22 §7 and reinforced by §3.2 above — my
enumerations have twice now failed to contain the answer, which is an argument for keeping R.3
neutral, not for tuning it to my current guess.

## 6. QA's §5, answered directly

**Q: how should "none of the three rows fires cleanly" be read?** As a genuine result about the
*shape* of the loss — it is distributed across mechanisms rather than concentrated in one — and as a
drafting failure in my table, which had no branch for that. Report it that way. It is not a null
result and it should not be written up as one: it excludes "one dominant mechanism," which was the
implicit premise of the whole R-series and of row 4's costing.

**Q: does it change R.3's design beyond the existing amendments?** No, apart from §5's band header.
R.3's axes already span what R.4b left open.

**Q: does the one-corpus co-channel signal warrant an Arm B?** No — §4, including the failed rescue.
Its non-replication argues against betting on it further without more evidence, exactly as QA's
question anticipated.

## 7. What the Captain should take from this

- **Your 5 kHz observation was worth making and I checked it on both corpora.** Our 3000 Hz ceiling
  costs us **nothing** on this traffic — WSJT-X decoded nothing above 2928/3095 Hz, because FT8
  convention keeps everyone inside 3 kHz. It is still a silent cliff if your operating pattern ever
  changes.
- **The floor is the live one.** WSJT-X decodes down to 132 Hz; we start at 200. That is ~1–2% of the
  miss population for zero algorithmic work — but it points into soundcard-noise territory, so it
  trades against NFR-018 false positives and needs measuring before it is claimed. Not commissioned;
  flagged.
- **ΔSNR = 2.62 dB is final** (independently verified two ways).
- **Sensitivity is a minority contributor** — now three instruments agreeing, at ~7%.
- **At strong signal we still lose ~10%** of what WSJT-X gets. That is the structural core of row 4,
  and it is the number I would watch from here.
- **I withdrew the co-channel bet I stated three notes ago** — it failed to replicate and the rescue
  failed too.
- **The 437 has still never moved.** Six arms.

## 8. What this does not authorise or settle

- **No native or `src/` change** (HK-011). §2.2's band-floor question would be one — a Developer
  session with pre-push sign-off — and it is **not** commissioned here.
- **No push, no merge** (HK-014). **No `pre_merge_check.py`** (HK-006 — Captain's trigger).
- **Row 5 untouched**; rows 2 and 3 stay sequenced behind row 4.
- **The `libft8.dll` size ruling is now overdue by four notes.** I am not going to keep listing it as
  "owed" — **it is the next thing I write, ahead of ruling on R.3's results.** Flagging that
  explicitly per HK-012's spirit rather than letting it lapse again.
- **The `MaxPass0Candidates` guard** remains owed and remains QA's to author.
- **NFR-021:** §2's counts are aggregates read from git-ignored `artefacts/`; no callsigns printed.
- **Per HK-015 this is a design, not a task.**

## 9. Honest caveats

- **§2's out-of-band counts are over the full `ALL.TXT` files without the cycle-set filtering the
  arms apply** (corpus 1: 2684 rows vs 2028 analysed; corpus 2: 43,707 vs 4,371). The percentages are
  sound as band-occupancy figures, and the **≤1–2% of the miss population** claim is a bound, not a
  measurement. **QA should compute the exact intersection** before any number here is quoted — it is
  a filter away and I did not want to reimplement the cycle-set logic in an audit.
- **§4's density spread is computed the same way** — cumulative files, all cycles — so it is
  indicative rather than exact. It is a strong enough refutation of the power-artefact defence to act
  on, but QA should confirm on the analysed subsets if the co-channel hypothesis is ever revived.
- **§2.1's "costs nothing" is corpus-specific**, and both corpora are one operator, two bands, one
  season. It is a statement about this operating pattern, not about FT8.
- **CPFSK vs GFSK** does not touch R.4b (its whole point) but still touches ΔSNR itself.
- **Six self-corrections caught mid-flight**, five of them mine. §3.1's was QA's and was caught
  pre-propagation, which is the better location. The rate is not falling.

## 10. Cross-references

- `2026-07-27-1543-qa-to-architect-r4b-notification.md` — answered; §5's three questions in §6.
- `2026-07-27-r4b-realworld-sensitivity-findings.md` — accepted; asymptote and marginal figure are
  the numbers of record.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` — §4's row 3 (co-channel) **withdrawn** by §4
  above; §11's verification ask **closed** by §3.
- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §6 — R.3's axes, unchanged.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1363` — `f_min = 200.0f, f_max = 3000.0f`, the constants §2 is
  about.
- `artefacts/20260725_live_run_1806/wsjt-x/ALL.TXT`,
  `artefacts/20260724_live_run_1607/ALL.TXT` — the corpora §2 counts.

---

*Per HK-015 this is Architect → QA material. Per HK-014 this note is committed locally and goes no
further. Per HK-011 nothing here touches `src/` or native code, and §2.2's band question is
explicitly not commissioned. The decision the study feeds — row 4 vs. row 5 — remains the Captain's,
on the Captain's clock.*
