# D-001: Architect ruling on C.2 Phase 2c — item 3 closes; the BER *median* is accepted, the BER *band reading* is not

**Author:** Architect, 2026-07-26 (20:30). **For:** the Captain and QA.
**Answers:** `2026-07-26-1935-qa-to-architect-c2-phase2c-notification.md` §5, questions 1 and 2.
**Revises:** `2026-07-26-1830-architect-c2-phase2a-ruling.md` §6 (the reading-rule table only) and §8;
`2026-07-26-1930-architect-c2-phase2a-ruling-revision.md` §4 and §7 (item 3's status).
Everything else in both notes stands, including 18:30 §2's corrections, §4's localisation and §7.

Phase 2c is the best-executed session in this thread. Two independent measurements, both self-checked
before being trusted, a sign-convention trap found *by* the self-check rather than shipped past it,
and a temporary constant swap reverted and re-verified byte-identical. The sign-convention finding in
the findings doc §2 item 4 is the single most valuable artefact of the session and I want it treated
as a permanent record, not a footnote — it is the kind of error that silently poisons every downstream
number and it was caught by discipline, not luck.

**Item 3 closes on evidence. I accept that in full and without hedge.**

**Item 4 does not proceed to §6.3 yet, and the reason is an error in my own 18:30 reading rule, not in
anything QA or the Developer session did.**

---

## 1. Short answer

1. **Item 3 (LDPC survival / LLR quality): Closed — on measurement.** Part A is a direct, decisive
   result. §3 below.
2. **The BER measurement is accepted as a measurement and rejected as a one-band reading.** The
   median reads into my ≈50% band. The *distribution* does not, and my 18:30 §6 table was written on
   a summary statistic in a way that discards the discriminating information the measurement was
   commissioned to produce. §4.
3. **QA's question 1 — is this enough to frame §6.3 for the Captain? Not yet.** One cheap step stands
   between this data and a §6.3 framing, and it is the step that gives the Captain a denominator
   instead of an open-ended commitment. §5, §6.
4. **QA's question 2 — does the ≈50% reading need tightening? Yes, but not the part QA expected.**
   THE 567's truncation needs *no* session — I can now sign off its bias direction as harmless. The
   distribution shape and the uncalibrated bands are what need work. §7.

## 2. What I am accepting outright

Recorded first so the corrections in §4 are not misread as a general challenge.

- **Part A's numbers and verdict.** Δ matched +0/+1/+1/+0/−3; THE 135 gained **0/135 at every weight
  tested**. Weight 1.0 triggers the "negative at any weight" row of my own 19:30 §5 rule. Every other
  weight independently sits in the "<10" row. Both readings agree. There is no ambiguity to negotiate.
- **The weight-0.0 no-op proof**, run twice — before the temporary K=4/cap2000 swap and again after
  the revert — byte-identical `ALL.TXT`, 1284 decodes, `hashTableRejectCount=656`. This is the
  self-check my 19:30 §5.2 demanded and §8's second caveat warned might fire. It did not fire, and it
  was demonstrated rather than assumed.
- **The Gray/sync round-trip.** My 18:30 §9 third caveat said I had not verified this and that the
  fallback was a native export. It round-trips: 6/6, verified two independent ways (CRC-14 *and* all
  83 LDPC parity rows), against constants parsed at runtime rather than hand-transcribed. That caveat
  is now retired. No fallback was needed.
- **The matched-hit control self-check**, which is what makes any BER number in this session
  trustworthy at all, and which is what caught the sign-convention error.
- **The revert discipline.** `K_MIN_SCORE`=10, `K_MAX_CANDIDATES`=140, confirmed by re-check and not
  merely by `git diff`.

QA's framing that the two halves "converge independently" is correct as far as it goes, and I want to
be precise about how far that is: Part A is a **direct measurement of the thing we care about**
(decodes recovered). Part B is an **explanatory measurement**. When a direct measurement and an
explanatory one agree, the direct one is doing the load-bearing work and the explanatory one is
corroboration. That distinction matters in §4, because Part B's corroboration is weaker than it looks
while Part A's directness is exactly as strong as it looks.

## 3. Ruling 1 — item 3 closes, and the 19:30 revision was worth its price

Part A settles it. Not "supports closing it" — settles it. The mechanism was given the most
favourable possible ground (its own discovery corpus, at the shipped config, swept across five
weights) and returned **zero recoveries in the population it was designed for, at every weight**, while
costing 1/2/5 previously-working decodes at weights 0.5/0.75/1.0.

Two details sharpen this beyond the headline:

- **The +1 at weights 0.25 and 0.5 is not the mechanism working.** Those rows show 0/135 and 0/567 —
  the single recovered decode came from *outside* both target populations. A mechanism that recovers
  nothing in the population it targets and one thing elsewhere is noise, not a small effect.
- **The regression count rises monotonically with weight** (0/0/1/2/5) while recovery does not rise at
  all. That is a clean dose-response curve for harm with no dose-response curve for benefit. It is the
  strongest possible shape for a negative result.

**Item 3's status: Closed — on evidence.** Not "closed — declined," which is what I wrongly wrote at
18:30 on cost/benefit reasoning. The distinction matters for the record: at 18:30 I closed it by
argument, the Captain challenged that, at 19:30 I reopened it as *measuring*, and it now closes on a
number. My 18:30 conclusion was right and my 18:30 *reasoning* was not sufficient to support it. One
Developer session was the correct price to establish that properly, exactly as 19:30 §8 predicted, and
I would spend it again.

**My 18:30 §3 wrong-sign concern is confirmed rather than merely raised**, per my own rule. And the
19:30 §5 reopening condition from the 18:30 note — "directionally correct but under-confident" — is
**not met in the operative sense**: whatever the LLRs' direction, rescaling their magnitude was
empirically tested on the target population and recovered nothing. Phase 2b stays declined, now on
measurement rather than on cost.

One thing I will *not* say, and QA correctly did not say either: this is not a finding against C.2
Phase 1. Phase 1 found a correlation and said in its own §6 that only re-decoding could establish
whether correcting it recovers decodes. Re-decoding has now established that it does not. Phase 1's
observation stands; the inference from it is closed.

## 4. Ruling 2 — the correction, and it is to my own note

This is the part of this ruling that matters, and it cuts against the conclusion I expected and stated
in advance (18:30 §5: *"My expectation is the latter"*). Per the standard I set myself in 18:30 §2.1,
a result landing where I already wanted it is precisely the one to check hardest.

### 4.1 My band table was specified on the wrong statistic

18:30 §6's table maps a single BER figure to one of three readings. QA and the Developer session
applied it exactly as written — median 44.0% and 49.4%, both "at or near ≈50%," therefore front-end.
That application is faithful. **The table is what is wrong.** It asks a heterogeneous population to
produce one number, and then reads that number as though the population were homogeneous.

The reported summary statistics falsify the homogeneity assumption on their own, without any new work:

| population | n | median | mean | min | max |
|---|---:|---:|---:|---:|---:|
| matched-hit control | 171 | 2.9% | 8.0% | 0.0% | **52.9%** |
| THE 135 | 126 | 44.0% | **39.0%** | **6.9%** | 61.5% |
| THE 567 | 279 | 49.4% | 49.0% | 16.1% | 62.1% |

Two things are visible here that the median hides.

### 4.2 THE 135 is decisively not noise

Under a "demodulating noise" null, each bit is an independent coin flip and per-candidate BER is
Binomial(174, 0.5)/174 — mean 50%, sd 3.79%. That null is too generous to me, because bits are
correlated within a symbol (58 tone decisions carry 3 bits each), so the honest conservative variance
is up to √3 larger, sd ≈ 6.6%. I use the conservative figure throughout:

- **THE 135's mean of 39.0%** sits (50 − 39.0)/(6.6/√126) ≈ **18.7 standard errors** below the null.
  Under the generous binomial null it is 32 SE. Either way: not noise, by a margin that is not
  arguable.
- **THE 135's minimum of 6.9%** is 6.5 sd below the null for a single draw — roughly 12 bit errors in
  174. The probability of any of 126 noise draws landing there is nil.
- **Mean (39.0%) below median (44.0%)** means the distribution is left-skewed: there is a low-BER tail
  carrying real information, and it is heavy enough to pull the mean 5 points below the median.

A population spanning 6.9% to 61.5% with a left skew is not "we are demodulating noise." It is
**heterogeneous**, and it spans all three of my own bands at once.

### 4.3 The control proves that mismatch inflates BER *toward* 50%, never away from it

The control arm — messages we definitely decoded — has a median of 2.9% but a **maximum of 52.9%**.
Some control candidates are therefore not the candidate for that message at all; the ±10 Hz/±0.5 s
nearest-candidate match occasionally picks up a neighbouring signal. That is not a defect in the
method, it is the method's measured noise floor, and the control arm quantifies it — which is exactly
why I asked for a control arm.

The direction is what matters. **A mismatched candidate's LLRs against the wrong codeword read ≈50%.**
Mismatch can only push a measured BER *up* toward 50%; it can never push one down to 6.9%. Therefore:

- The ≈50% mass in both missed populations is **partly inflated by a known artefact**, and the true
  distribution sits at or below what was measured.
- The **low tail cannot be an artefact.** It is the one part of this dataset that is artefact-proof.

So the statistic my band table keyed on is the one biased toward my own expected answer, and the
statistic that contradicts it is the one that cannot be explained away. That is the wrong way round,
and it is my error.

### 4.4 The two populations differ in kind, which is the result I asked for and we flattened

18:30 §6 said explicitly: *"If the two missed populations return different BERs, that is the mechanism
distinguishing them that §3 says we currently lack."* They did, and the difference is sharper in shape
than in median:

- **THE 135** (score ≥10): mean 11 points below the null, heavily left-skewed, min 6.9%. **Not noise.**
- **THE 567** (score 5–9): mean 1.0 point below the null, near-symmetric, min 16.1%. Under the
  conservative correlated-bit variance this is ~2.5 SE — **consistent with noise.**

That is a real dichotomy along the score axis, and it is the first mechanism we have that explains why
the two populations behave differently rather than merely noting that they do. It also coheres with
everything else: the low-score 567 are candidates the front end never locked, while a meaningful part
of the high-score 135 *did* lock and still failed downstream.

The notification reports both numbers accurately and then reads them into one band. The band table
made that the correct thing to do. That is the flaw.

### 4.5 What survives

- **"THE 567 is front-end limited" stands**, and is if anything strengthened (§7.1).
- **"THE 135 is uniformly front-end limited" does not stand.** Part of it is; a real fraction is not.
- **"Kills all LLR-scaling avenues permanently" must not go into the record.** Phase 2b is closed by
  Part A's direct measurement — which is stronger ground anyway. It does not need Part B's inference,
  and Part B's inference will not bear that weight.

## 5. Ruling 3 — §6.3 stays parked, for a reason that is now cheap to remove

QA's question 1 asks whether this is enough to frame §6.3 — "how much of WSJT-X's decoder are we
willing to reimplement" — for the Captain. **No, and one step short of it.**

Here is the problem with taking it up now. §4.2 says a fraction of THE 135 has ~7–25% BER. My own
18:30 table's *second* band reads that as *"close, and LDPC/OSD is running out of correction power →
decode effort — BP iteration count, OSD depth/gate. Cheap constants, not a reimplementation."* I would
be asking the Captain to weigh a decoder reimplementation while a cheap-constants explanation for part
of the same population sits unexamined in data we have already captured. That is asking for the
expensive commitment before exhausting the inexpensive one.

And the question I cannot currently answer is the one that decides it:

> **How many bit errors can *this codebase's* BP+OSD actually correct?**

I flagged this in 18:30 §9 as a caveat — *"What LDPC+OSD can actually correct at this code rate should
be derived or measured, not taken from my table"* — and then built two rulings on top of the
uncalibrated table anyway. That was a mistake, and it is now the binding constraint. Without it, "44%
is near 50%" is a comparison against a number I invented. With it, every candidate in THE 135 sorts
into exactly one of two buckets:

| bucket | meaning | what it costs |
|---|---|---|
| BER **below** our own correction threshold, did not decode | a **defect in our decode path** — we had a correctable codeword and dropped it | cheap to chase; constants, gates, iteration counts |
| BER **above** our own correction threshold | genuinely front-end limited — no decoder change recovers it | §6.3 territory |

The second bucket's **count** is the number the Captain actually needs. "Reimplement some fraction of
WSJT-X's decoder" is unanswerable. "N of the 793 missed messages are unreachable without front-end
work, and here is N, measured" is a decision a Captain can take. That is the same move I made at 18:30
§6 — decompose the product question into a measurement — and it applies one level deeper than I
realised.

## 6. What I recommend QA scope next (HK-015: a recommendation, not a task)

**One session, and I want to be explicit about how cheap it is:** no native change, no rebuild, no new
decode runs, no live data, no NFR-021 exposure. The 36 MB of LLR captures are already on disk under
`artefacts/d001_c2_phase2c/ber/`. Part B is pure re-analysis of committed artefacts; Part A is a
synthetic bench that touches no corpus at all.

### 6.1 Part A — calibrate the correction threshold (the item that retires my 18:30 §9 caveat)

Take known-good synthetic codewords (Q-prefix, same as the round-trip verification), inject *k* random
bit errors for k = 0…45, run our own `bp_decode`/OSD path at the shipped D-009 constants, and plot
success rate against k. That yields the waterfall and a real threshold.

Report it as a curve, not a point — the interesting output is where success falls from ~100% to ~0%,
and how wide that transition is. Repeat at a couple of error *patterns* if cheap (uniform-random vs.
clustered-within-symbol), because real demodulation errors are symbol-correlated and a threshold
derived from uniform errors may be optimistic.

This number is permanently useful. Every future LLR or decode-effort question in this project reads
against it.

### 6.2 Part B — re-read the captured BER data as a distribution

From already-captured data, no re-decode:

1. **Decile table** for all three arms, not median/mean/min/max.
2. **Control-arm mismatch rate** — the fraction of the control above (say) 25% BER. That is the
   measured artefact floor, and it lets the missed populations' upper tails be discounted by a
   measured quantity instead of an assumed one.
3. **The count that matters: how many of THE 135 sit below §6.1's measured threshold and did not
   decode.** This is the whole point of the session.
4. **BER against sync score, and BER against `postnorm_mean_abs_llr`**, within THE 135. Both columns
   are already in `candidate_diag.csv`. If the low-BER subpopulation has a distinguishing signature,
   that is a route to it; if it does not, that is worth knowing too.

### 6.3 The reading rule, fixed in advance again

That discipline has worked twice in this thread and I am keeping it. Read against **the count of THE
135 whose BER is below §6.1's measured correction threshold**:

| count below threshold | reading | next |
|---:|---|---|
| **0** | no candidate we located was ever correctable; the population is front-end limited exactly as the median suggested | §4's correction is noted and overruled by measurement. §6.3 goes to the Captain, with N = the front-end-limited count as its denominator. |
| **1 – 15** | a real but small decode-path residue | Chase it if the cause is a single constant or gate; otherwise fold the count into §6.3's framing and proceed. Captain's call, with a number. |
| **> 15** | we are dropping correctable codewords at material scale | **Stop. This is a defect, not a structural gap**, and it outranks §6.3 entirely. Item 4 re-decomposes around it. |

I will not pretend to know which row this lands in. §4.2's skew makes me think it is not 0; the 18.7
SE result is not compatible with every one of the 126 being uncorrectable. But "not zero" and ">15"
are very different outcomes and I am not going to guess between them, having just been wrong once in
this note about reading a distribution off its median.

**If §6.1's threshold turns out to sit well below every observed BER** — i.e. our decoder corrects far
fewer errors than even the low tail carries — then the count is 0, my §4 correction is interesting but
inconsequential, and §6.3 proceeds immediately on the original reading. That is a perfectly good
outcome and one session is a fair price to establish it.

## 7. Answering QA's question 2 directly — what needs tightening and what does not

### 7.1 THE 567's truncation: no session needed. I am signing off the bias direction.

The findings doc §7 flags n=279/567 as a truncated subsample and asks whether it should be fixed
before the 49.4% is trusted. **It should not, and here is why the truncation is harmless rather than
merely tolerable.**

`ftx_find_candidates` (`native/ft8_lib_build/patched/ft8/decode.c:340–353`) sorts the candidate heap
into **descending score order** before returning. The managed 600-cap in
`Ft8LibInterop.MaxPass0Candidates` is therefore a *head-take of the top 600 by sync score*, not a
random sample — confirmed by the finding that all 68 cycles sat at exactly 600.

THE 567 live at score 5–9. So the measured 279 are the **highest-scoring, most favourable** members of
that population, and the 288 unmeasured ones sit at lower score still. Since BER falls with score
(that is precisely §4.4's dichotomy), the unmeasured remainder will read **worse** — closer to or
above 50%.

**The truncation biases 49.4% optimistically.** Fixing it can only move THE 567 further into the
front-end band, which is the conclusion already drawn. No decision hinges on the exact figure, and I
would rather not spend 6 minutes of decode plus a session confirming something in a direction that
cannot change an outcome.

The findings doc's advice — raise `MaxPass0Candidates` 600→2000 before anyone next runs a K=4/cap2000
capture — is right and should be carried as a note for whoever next touches that path, not as work of
its own. It is the second time this constant has silently truncated a diagnostic; the third time it
happens it should become a guard that errors rather than truncates.

### 7.2 The ≈50% *bands*: yes, and that is §6.1

QA's question 2 asked whether the reading needs tightening before it is load-bearing. The honest answer
is that the bands were never calibrated at all — my own 18:30 §9 said so — and I then let two rulings
lean on them. §6.1 fixes that properly rather than tightening a number against an invented reference.

### 7.3 The distribution: yes, and that is §6.2

Sample size is not this measurement's weak point. Its weak point is that a 126-point distribution was
compressed to one number before being read. §6.2 costs a re-analysis of data already on disk.

## 8. Revised decomposition table

Replaces §7 of the 19:30 revision. Items 1 and 2 unchanged.

| # | mechanism | status | measured decode yield |
|---|---|---|---|
| 1 | Candidate-array truncation (`K_MAX_CANDIDATES`) | **Closed** — C.1 | +12 decodes, +1.6% of gap. Real, small, plateaus. |
| 2 | Sync score-floor rejection (`K_MIN_SCORE`) | **Closed** — C.3/C.4 | +2 decodes while false decodes rise 61 → 376. |
| 3 | LDPC survival / LLR quality | **Closed — on evidence** | Ceiling was 135 (17.0% of gap); **measured conversion 0/135 at every weight**, negative at weight 1.0. Shrinkage closed by direct measurement, not argument. |
| 4 | Structural decoder difference vs WSJT-X | **Open — active, decomposing** | THE 567 reads front-end limited (49.4%, consistent with noise). THE 135 is **heterogeneous** and not uniformly front-end limited. Next: §6.1's correction-threshold calibration + §6.2's distribution re-read. §6.3 stays parked one more step. |

## 9. Housekeeping — the `libft8.dll` growth (notification §6.2)

Outside this ruling's scope and correctly routed to the Captain, so one paragraph only.

A diagnostic-only change growing `win-x64/libft8.dll` from 60,416 to 158,208 bytes — +97 KB, all in
`.rdata` — is not explainable by the code this session added. Two new exported functions and a blend in
`ftx_normalize_logl` are a few hundred bytes of `.text`. A 2.6× size increase concentrated entirely in
read-only data smells like a **build-configuration difference** (optimisation level, CRT linkage, debug
or RTTI metadata) rather than anything in the source diff.

It should be **explained by a section/symbol comparison, not by argument** — a `dumpbin /headers` and
`/symbols` diff against the prior binary will settle it in minutes. My view for the record: an
unexplained binary-size change is a merge blocker regardless of how benign it turns out to be, because
the reason we can trust every "byte-identical" self-check in this thread is that we treat unexplained
binary deltas as findings. That standard is worth more than this specific 97 KB.

Per notification §6, `pre_merge_check.py` has not been re-run. **Nothing in this ruling is a statement
that this branch is ready for anything.**

## 10. Honest caveats

- **I am correcting my own reading rule after seeing the numbers**, which is exactly the thing my
  19:30 §5 fixed decision rules in advance to prevent, and it deserves the scrutiny I applied to
  myself at 19:30 §8. The defence: I am **not** changing the rule for Part A, where a decision rule
  was fixed and the result landed in it — item 3 closes, unchanged, on the rule as written. I am
  changing how Part B's *explanatory* number is read, and the specific defect (a heterogeneous
  population read through a single statistic) is one I can point at in the reported data rather than
  one I inferred from disliking the answer. It also moves the conclusion **away** from my stated prior
  expectation, not toward it. If that reasoning does not persuade, the fallback is that §6.3 proceeds
  as QA proposed and §6.1's calibration runs alongside it — the calibration is worth having either way.
- **My statistical null is my own construction.** The binomial and correlated-bit variances in §4.2
  are back-of-envelope, computed from the five summary statistics QA reported, not from the underlying
  distribution. They are strong enough to carry "not noise" at 18.7 SE with a margin of ~19×, but
  §6.2's decile table should replace them and I would not defend the exact SE figures.
- **§6.3's bands (0 / 1–15 / >15) are set before the numbers, but they are a prior, not a derivation** —
  same status as 19:30 §5's, same invitation to the Captain to set them differently, provided it is
  done now rather than after.
- **The low-BER tail's size is unknown.** I have established it exists and cannot be a matching
  artefact. I have *not* established that it is more than a handful of candidates. §4.2's mean/median
  gap is consistent with anything from a small tail to a broad continuum, and I deliberately have not
  guessed.
- **One 21-minute session, one device, one band.** Unchanged from every prior note in this thread.
- **Item 3's closure is genuinely final absent new evidence.** I have now reopened one item once under
  challenge; that was justified by a specific factual error I could point at. A second reopening would
  need the same standard, and "the negative result is disappointing" is not it.

## 11. Cross-references

- `2026-07-26-1935-qa-to-architect-c2-phase2c-notification.md` — the notification this answers.
- `2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md` §2 item 4 (sign convention — carry this
  forward permanently), §4.1, §4.2, §7.
- `2026-07-26-1930-architect-c2-phase2a-ruling-revision.md` §4, §5, §7 — item 3's status replaced by §8;
  §5's decision rule applied as written in §3.
- `2026-07-26-1830-architect-c2-phase2a-ruling.md` §6 (band table corrected in §4), §9 third caveat
  (Gray/sync — retired, §2) and second caveat (uncalibrated bands — addressed by §6.1). §2, §4, §7 stand.
- `native/ft8_lib_build/patched/ft8/decode.c:340-353` — the descending-score sort §7.1's bias-direction
  sign-off rests on.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:304` — `MaxPass0Candidates = 600`, §7.1's head-take.
- `artefacts/d001_c2_phase2c/ber/` — the captured LLR data §6.2 re-reads; no new capture required.
- `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §6.3 — still parked, one step further along.

---

*Per HK-014 nothing is pushed or merged. Per HK-015 §6 is a recommendation for QA to scope into a
dev-task; `dev-tasks/` remains QA's to author. §6.3's product decision remains the Captain's and is
still not being put to them. §9's binary-size question is the Captain's and QA's, not settled here.*
