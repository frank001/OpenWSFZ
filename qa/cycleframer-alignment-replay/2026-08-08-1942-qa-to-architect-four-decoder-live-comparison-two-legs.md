# QA → Architect: four-decoder live comparison, 2026-08-08 — two legs (20m + 17m)

**Author:** QA, 2026-08-08 (19:42 UTC, `date -u`, per HK-017). Repo `main` at `b8845cd`.
**Scope:** the 2026-08-08 live run — 2× OpenWSFZ (ports 8080/8081) against 2× WSJT-X
(FT991A / FT991A-Copy), one antenna split to one radio, one shared USB Audio CODEC.
**Status:** corpora gathered and verified; analysis is **exploratory except where a
pre-registration is named**. Nothing committed, nothing pushed (HK-014). No `src/` change is
proposed here.

> **Bottom line for the Architect, in one paragraph.** Two fresh live corpora (20m and 17m, ~19 h
> total) **corroborate** the decode gap already established by your 2026-08-06 replay work, on
> different days, different bands, and a different instrument. OpenWSFZ recovers **55.5%** of the
> reference on 20m and **62.6–63.7%** on 17m, bracketing your pooled **59.6%**. The SNR curve
> replicates almost exactly — **83.2%** recovery at ≥ 0 dB against your 83.4%. What is genuinely new
> is a **~4% false-positive rate** measured against a live reference, which bears on the still-open
> post-fix FP surge. Three things are **withdrawn or corrected**: the "94.4% self-consistency"
> figure is not a decoder property; the density→recovery slope **magnitude** is not stable (though
> your SNR-controlled finding that the penalty *exists* stands, and is stronger than my fit); and a
> pre-registered leg **voided under a gate I drafted badly**, which I have not rewritten.
>
> 🔴 **Correction, 19:55Z.** The first version of this document claimed these were "the first clean
> measurement against a valid reference." **That was wrong** — `2026-08-06-2323-architect-where-the-decode-gap-actually-lives.md` had already done it. I wrote the
> claim without opening the 08-06 thread. That is an HK-018 failure, on the same day I cited HK-018
> to the Captain. §0 records what was already known; the sections below are reframed accordingly.

---

## 0. What was ALREADY established, before this run (added 19:55Z)

Read this first; several sections below are corroboration rather than discovery. From
`2026-08-06-2323-architect-where-the-decode-gap-actually-lives.md` (5 replay sessions, live
WSJT-X reference, 3 779 decodes):

| already known, 2026-08-06 | value |
|---|---|
| miss rate vs WSJT-X, 5 independent sessions | **39.9–40.6%**, pooled **40.4%** (⇒ ~59.6% recovery) |
| SNR is the dominant axis, monotone over 8 buckets | miss 0.792 (< −20 dB) → **0.166** (≥ 0 dB) |
| density penalty, **within fixed SNR bands** | monotone in all four bands; confound runs the *wrong* way |
| sub-200 Hz / ≥3000 Hz decodes | **100% missed**, 3.3% of all misses, mechanism certain |
| D-009 sweep, 45 parameter points | **+0.109 pp** ⇒ "the deficit is not parametric" |
| priced prize (weak-signal gap closed) | 60% → **83%** of WSJT-X |

Two consequences for what follows. **(a)** My §4 caution that density might merely proxy SNR was
already answered on 08-06 — the penalty survives *within* fixed SNR bands, which is stronger
evidence than my quintile fit, and the confound runs the wrong way (denser cycles carry *stronger*
signals). I raised a question that had been closed two days earlier. **(b)** The candidate-cap
hypothesis (`K_MAX_CANDIDATES = 140`, §6.2 there, explicitly out of D-009's scope) is a sharper
form of the "time-bounded budget" mechanism I improvised this afternoon. It predicts exactly the
density signature. It remains the best open explanation and this run does not test it.

**Configuration asymmetry, from `2026-08-06-1933-qa-decode-config-comparison-wsjtx-vs-openwsfz.md`
— absent from the first version of this document and load-bearing for every figure below.** The
reference runs **`NDepth = 3` (Deep, top of its range)**, `FT8AP=false`, `Ftol=50`, `DTtol=3.0`.
OpenWSFZ runs `K_MAX_PASSES = 2`, candidate caps 140/200, and a **hardcoded 200–3000 Hz** search
band (`ft8_shim.c:1183`). Every recovery number in this document therefore means *"against WSJT-X
at maximum decode depth."* Part of the gap is a depth and candidate-budget asymmetry, not
necessarily a capability difference.

## 1. What ran

Two sequential legs, same hardware, same antenna, same audio device, **same frozen decoder
settings** (`kMinScorePass2=10`, `osdCorrThreshold=0.1`, `osdNhardMax=60`), same self-contained
publish of `main` @ `b8845cd`. Both OpenWSFZ instances ran the literal same binary.
`cat.enabled=false`, `ptt.method="AudioVox"`, `tx.autoAnswer=false` throughout — this station had
zero TX capability on either leg.

| leg | window (UTC) | cycles | ref decodes | density (median, range) | artefacts |
|---|---|---:|---:|---|---|
| **20m** (14.074) | 00:40–11:15 | 2 529 | 69 222 | 28.0 (5–50) | `artefacts/20260808_live_run_0016-808{0,1}/` |
| **17m** (18.100) | 12:00–19:38 | 1 824 | 38 636 | 21.0 (3–35) | `artefacts/20260808_live_run_1154-808{0,1}-17m/` |

Both gathered per HK-016; live-vs-artefact line counts and WAV counts match **exactly** on all four
folders. `qa/ARTEFACT_INVENTORY.md` regenerated, `--check` clean.

**"Reference" throughout this document means the intersection of the two WSJT-X instances** — a
decode both of them made. That is the conservative choice and it is what every figure below uses.

⚠️ **All figures are computed on clean windows that exclude each leg's unsettled opening.** The
full-corpus figures differ materially and should not be quoted: on the 20m corpus taken whole,
OpenWSFZ self-consistency reads 90.8% and WSJT-X 94.6%, purely because the instances came up at
different times. Use the windows in the table above.

**Two operational notes worth carrying forward.** First, `DialFreq` in WSJT-X's `.ini` is a
**lagging** indicator — it read 7.074/14.074 while the GUI showed 24.915. I made a wrong call off
that stale data during the session. On a *silent* band there is no mechanical way to confirm the
dial frequency at all (the `.ini` lags; `ALL.TXT`'s frequency field only appears when something
decodes), so the GUI is the only authority. Second, with `cat.enabled=false` OpenWSFZ takes its
dial frequency from `decodeLog.dialFrequencyMHz`; changing band **requires editing both configs
before the VFO moves**, or the corpus is silently mislabelled and shows zero overlap.

## 2. Headline findings

### 2.1 Recovery against a valid reference — the number this run existed to produce

| leg | recovery (8080 vs both-WSJT-X) |
|---|---:|
| 20m | **55.5%** (38 440 / 69 222) |
| 17m, 12:00–13:07 | **62.6%** |
| 17m, 13:10–19:38 | **63.7%** |

Using the union of both OpenWSFZ instances instead of 8080 alone lifts 20m only to 56.0% — the
deficit is not a per-instance accident.

🔴 **This CORROBORATES, it does not supersede.** Your 08-06 replay work pooled **59.6%** recovery
across five sessions; today's two legs bracket it (55.5% / 62.6–63.7%) on different days, different
bands, and with a different instrument. Three independent estimates now sit in a ~55–64% band.

What today's setup adds over the replay corpus is narrow but real: two *concurrent* WSJT-X
instances, so the reference's own stability is **measured** (99.6% self-agreement) rather than
assumed, and "reference" can mean a decode both of them made. It is a firmer reference, not a
first one.

⚠️ **Read every figure as "against WSJT-X at `NDepth = 3`"** — see §0. The reference is at maximum
decode depth; we run two passes with hard candidate caps.

### 2.2 Where the misses lie (20m, n = 30 926 missed)

**Not bandwidth — and the sub-200 Hz part has a *certain* mechanism I under-claimed.** Misses span
the whole passband and track the matched distribution closely, except below 200 Hz: 2.3% of misses
against 0.2% of matches. The first version of this document called that a mild "band-edge
disproportion." It is nothing of the sort — `ft8_shim.c:1183` hardcodes `f_min = 200.0f,
f_max = 3000.0f`, so **we cannot see those decodes at all**. The 08-06 note measured it exactly:
100% missed below 200 Hz and above 3000 Hz, 3.3% of all misses. Bounded, certain, already known.

**Mostly, but not only, SNR — and this REPLICATES 08-06 closely.** Recovery stratified by WSJT-X's
own reported SNR (never OpenWSFZ's — `DEFECT-snr-reported-gain-error.md`):

| SNR band (dB) | recovery |
|---|---:|
| −30…−21 | 19.8% |
| −21…−18 | 21.6% |
| −18…−15 | 30.0% |
| −15…−10 | 43.4% |
| −10…−5 | 57.9% |
| −5…0 | 71.3% |
| ≥ 0 | **83.2%** |

🔴 **The last row is the interesting one.** Roughly **one loud signal in six is still lost** — and
your 08-06 corpus put that same figure at 0.166 miss, i.e. **83.4% against today's 83.2%**. Two
corpora, two bands, two days, two instruments, agreeing to two-tenths of a point. That is the
firmest number in the whole D-001 programme, and it is what §5's "size of the prize" (60% → 83%) is
priced against. It is not a sensitivity floor, and it is consistent with D-001 sitting in the
decode stage rather than in detection.

### 2.3 False positives — bears directly on the open post-fix FP surge

On 20m, OpenWSFZ produced **3 972 decodes that neither WSJT-X instance made**. Using "does every
callsign in this message appear anywhere in the 10.6 h WSJT-X corpus (3 735 distinct calls)" as a
plausibility proxy:

| class | n | callsigns known to WSJT-X |
|---|---:|---:|
| matched (OpenWSFZ ∧ WSJT-X) | 38 361 | 100.0% *(tautological — it **is** the reference)* |
| novel, in both OpenWSFZ instances | 1 988 | 86.7% |
| novel, single instance only | 1 704 | **9.1%** |

Samples from the single-instance class: `0B3UQV VV7EHC GB07`, `ZT7XIM/R 7I3JVE/R KK02`,
`K49QVB T88WJT/P BK18`. These are not callsigns. Rough FP rate ≈ **4% of OpenWSFZ's output**.

⚠️ **Two cautions, both load-bearing.** Agreement between 8080 and 8081 does **not** validate a
decode — same build, same audio, so a deterministic false positive appears in both; note the
corroborated class still carries 13.3% unknown callsigns, i.e. ~264 *systematic* FPs. And the proxy
has a floor, not a zero: a genuine rare DX heard once by OpenWSFZ alone counts as unknown, so 9.1%
is a lower bound on legitimacy, and the FP estimate is correspondingly an upper bound. The 17m FP
analysis has **not** been done on a clean window and its full-corpus numbers look anomalous; I have
deliberately not quoted them.

## 3. 🔴 Withdrawn and corrected

**3.1 "OpenWSFZ self-consistency = 94.4%" is withdrawn as a decoder property.**

| leg | OpenWSFZ vs itself | WSJT-X vs itself |
|---|---:|---:|
| 20m | 94.4% | 99.6% |
| 17m, pre-rephase | **99.7%** | 97.8% |
| 17m, post-rephase | 98.6% | 97.2% |

At *matched density* (20m Q1 = 15.3, 17m ≈ 15.0) the same pair agrees 94.2% on one band and 99.7%
on the other. Two explanations were tested and **both ruled out by measurement**:

- **not density** — flat 93.0–94.7% across all five 20m quintiles (15.5 → 37.7 dec/cycle);
- **not run-length drift** — flat 93.3–95.4% across all eleven hours of the 20m leg.

Note also that the two decoders **swap ranks** between legs: on 17m OpenWSFZ is the steadier of the
pair. Whatever this is, it is a property of conditions, not of the decoder.

**3.2 The board's earlier "~0.96–0.999 decode-count ratio" described the WSJT-X↔WSJT-X pair, not
OpenWSFZ against WSJT-X.** Corrected on the board.

## 4. 🔴 The density→recovery slope is NOT stable — treat the earlier framing as retracted

This morning's 20m quintiles suggested a clean law. Fitting each clean window separately:

| window | n cycles | slope | intercept | R² |
|---|---:|---:|---:|---:|
| 20m, 00:40–11:15 | 2 529 | **−0.4208** | 67.93 | 0.854 |
| 17m, 12:00–13:07 | 271 | **−0.2724** | 67.00 | 0.676 |
| 17m, 13:10–19:38 | 1 553 | **−0.8794** | 84.09 | 0.938 |

Each fit is decent *within* its window. Across windows the slope varies by a **factor of three —
including between two windows of the same leg, on the same band, hours apart.** The 17m
post-rephase slope (−0.88) falls outside even the generous "within a factor of two of −0.42" band I
had pre-registered.

There is also substantial variance density cannot explain at all: at density ≈ 15–16 on 17m, one
window gives 62.9% recovery and another 71.1%. Same band, same binary, same day.

**Recommendation: do not carry "recovery falls ~0.42 points per decode/cycle" forward as a
finding.** The direction is consistently negative in all three windows, and that much looks real.
The magnitude is not a parameter we have measured; it is a number that moves with conditions we
have not identified.

🔴 **Scoped against §0.** This qualifies the *magnitude* only. Your 08-06 §3 established that the
density penalty **exists and is SNR-independent** — monotone in all four fixed-SNR bands, with the
confound running the wrong way — and that is better evidence than any fit of mine, because it
controls for the variable my quintiles confound. Nothing here weakens it. What today adds is a
caution against ever quoting a *slope*: the effect is real, its size is not yet a measured
quantity, and my own reading of it swung from −0.27 to −0.88 within one afternoon.

## 5. 🔴 A pre-registered leg voided — and the bad draft was QA's

`qa/endurance/2026-08-08-1145-qa-prereg-12m-sparse-regime-leg.md` was written before any data
existed. Its ROW 0b voids the leg if median density ≥ 15.3. The 17m leg came in at **21.0** — the
band grew busier through the afternoon, the reverse of the diurnal decline I predicted. **The leg
reads nothing and no row may be cited from it.**

The failure is structural and mine, and it is the HK-021 pattern precisely: **ROW 0b gated on a
central-tendency statistic to answer a question about range.** Its own stated intent was "the leg
has no sparse regime" — yet the leg's Q1 sits at density 9.7 and its quietest cycles at 3,
comfortably below the 20m corpus's floor of 15.3. A sparse regime *was* delivered; my gate could not
see it.

I have **not** rewritten the threshold after seeing the numbers. For the record and explicitly not
as a result: had ROW 0b not fired, the pre-rephase window would have read ROW 1 (E = 2.97 pts,
inside the 4.0 bar) — and the post-rephase window would **not** have, which is itself an argument
that the leg deserved to void.

**Correction for any future draft:** gate on **range coverage** ("at least N cycles below density
X"), never on a median, whenever the question is "does this corpus reach regime X."

## 6. Capture-phase test — ROW C, inconclusive

`qa/endurance/2026-08-08-capture-phase-selfconsistency-test.py`, registered before the intervention.
Hypothesis: the 20m pair was started 21 minutes apart (incidentally — the second instance was a late
idea), the 17m pair within the same second; does capture start phase drive self-consistency?

8081 alone was killed and relaunched at 13:08:24Z with a fresh phase; 8080 ran untouched. Result:
**99.65% → 97.58%, delta −2.07 points**, landing inside the pre-declared 97.0–99.0 dead band ⇒
**ROW C, inconclusive; it stays confounded.** Measured over the full post window rather than the
test's hour, it reads 98.6% — closer to the "ruled out" side. The direction favours the hypothesis;
it does not clear the bar, and I am not going to reclassify it.

Cost to the host leg was nil by construction: the primary metric is 8080 vs WSJT-X, and both ROW 0
gates were computed from the WSJT-X reference alone.

## 7. What I recommend next — and the one thing that needs your ruling

**7.1 The pooled analysis (recommended, no capture needed).** The two legs **overlap at density
≈ 13–28 on different bands**. That permits fitting recovery against density *with a band term* and
asking whether band survives — which neither leg alone could do, and which the sparse leg I spent
the afternoon chasing would not have delivered either. Given §4, I would frame the primary question
as **"is there a band effect at matched density?"** rather than as estimating a slope.

⚠️ **Disclosure that must appear in that pre-registration:** I have already seen 17m running ~3
points above 20m at matched density (28.2 → 56.9% vs 28.8 → 60.0%). The *direction* is no longer
blind. Only the magnitude, and whether density survives the band term, remain honestly open.

**7.2 The sparse regime is still not obtained.** 12m was dead (zero decodes in 21 cycles); 17m never
quietened. Today's evidence is that the gap between "dead" and "busier than 20m's quietest quintile"
is narrow and hard to hit deliberately. I would stop hunting it by band selection and take it from a
quiet *hour* on a band we already trust.

**7.3 Needs your ruling — D-009 Option B (`osd_nhard_max` 60→40).** The board carries QA's
recommendation to HOLD, on the grounds that it shallows OSD at the stage RC1 localised. §2.3 cuts
both ways and QA should not settle it alone: a ~4% FP rate is evidence *for* Option B, while the
recovery deficit says recall is the larger wound and argues *against*.

🔴 **Scoped against §0, which already answers half of it.** Your D-009 sweep returned **+0.109 pp
across 45 parameter points** — the recall side is settled, and it is negative. So the live question
is **FP only**, and the recall argument against Option B is weaker than my first draft implied.

**On the instrument, which is the Captain's question of 2026-08-08.** Option B's FP evidence rests
on S5/S7, whose entire channel model is `channel.py`: **AWGN plus co-channel mixing of valid
signals, and nothing else** — no fading, no multipath, no Doppler, no impulsive noise, no non-FT8
interference (grepped; zero hits). So a synthetic false positive can arise only by OSD forcing a
codeword out of noise or out of overlapping *legitimate* signals, whereas live FPs also come from
fading-corrupted partials and adjacent interference. The issue is **mechanism, not sample size** —
the phrase "synthetic arms only" in my first draft was imprecise. Two further cautions: **"FP → 0"
on 225 slots bounds the rate at ~1.3% by the rule of three, not at zero**; and both known harness
defects sit in exactly this path (S5's OpenWSFZ-only fallback spec'd-but-uncoded, and the
`s7_recovery_pct` ≠ `co_channel_sweep` inventory confusion).

**Cheap decisive test, data already on disk:** replay today's 4 510 live WAVs through an
`nhard=40` build and score FP *and* recall against the two-instance WSJT-X reference. That needs a
rebuilt DLL ⇒ Developer session under HK-011; QA proposes and stops.

## 8. Citation limits

🔴 **Updated 2026-08-08 21:35Z following H1** (`2026-08-08-2135-qa-to-architect-h1-hash-token-contamination-results.md`).
H1 measured how much the never-re-initialised 256-slot hash table (`<...>` tokens) distorts the two
headline figures below. **Gate A fired A-ROW 1 (material, `M = 2.26 pp`): the §2.1 recovery figures
must now be read as the bracket `[R_base, R_wild]`, i.e. 20m is `[55.5%, 57.8%]`, not a bare 55.5%.**
`R_wild` is an upper bound with only a 0.5% ambiguous fraction attached — cite the bracket, not the
upper end alone, and never describe the gap between them as "new decodes" (H1 §0). **Gate B read
B-ROW 2 (immaterial, `ΔF = 0.02 pp`): the §2.3 ~4% FP estimate is UNCHANGED and confirmed clean of
`<...>` contamination** — its existing upper-bound caveat (below) still applies, and now applies with
full weight to §7.3's D-009 Option B question, since the FP evidence there was not a text-matching
artefact.

**May be cited:** the recovery figures in §2.1, now read as the **bracket `[55.5%, 57.8%]`** on 20m
per H1 (with their windows, and 17m unaffected — H1 was 20m-only, spec §1.3); the SNR stratification
in §2.2; the ~4% FP estimate in §2.3 **as an upper bound, with the two cautions attached, and now
also confirmed independent of hash-token contamination (H1 Gate B, B-ROW 2)**; the ruling-out of
density and run-length as explanations for self-consistency in §3.1.

🛑 **May NOT be cited:** anything from the 17m leg as a *pre-registered result* (§5 — it voided);
"94.4% self-consistency" as an OpenWSFZ property (§3.1); any density slope as a law or parameter
(§4); the capture-phase test as evidence that start phase matters (§6 — ROW C); any 17m
false-positive figure (§2.3 — not yet computed on a clean window); 🔴 **and this run as a "first"
of any kind (§0 — the 08-06 replay corpus got there first, and this document said otherwise until
19:55Z).**

⚠️ **Every recovery figure is against WSJT-X at `NDepth = 3`.** Quoting one without that
qualifier overstates it as a pure capability gap; part of it is decode-depth and
candidate-budget asymmetry (§0).

## 9. Artefacts and harnesses

- `artefacts/20260808_live_run_0016-808{0,1}/` — 20m, 1.9 G + 1.8 G
- `artefacts/20260808_live_run_1154-808{0,1}-17m/` — 17m, 1.3 G each; 8081's folder carries **two**
  daemon logs, the second being the deliberate 13:08:24Z rephase
- `qa/endurance/2026-08-08-four-decoder-interim-comparison.py` — the general evaluator
- `qa/endurance/2026-08-08-capture-phase-selfconsistency-test.py` — §6, thresholds fixed pre-hoc
- `qa/endurance/2026-08-08-1145-qa-prereg-12m-sparse-regime-leg.md` — §5, the voided pre-registration
- `qa/endurance/2026-08-08-supervisor-808{0,1}-*.sh` — both HK-013-validated by live kill-tests

All untracked. Committing is the Captain's call (HK-010).
