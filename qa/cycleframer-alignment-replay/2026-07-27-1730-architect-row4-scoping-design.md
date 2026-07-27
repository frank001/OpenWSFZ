# D-001: Row-4 scoping decomposition — the design. Four arms, reading rules fixed in advance

**Author:** Architect, 2026-07-27 (17:30). **For:** QA (to run), and the Captain (§7, §8).
**Answers:** `2026-07-27-1630-qa-to-architect-menu-decision-and-row4-request.md` §2 — the row-4
scoping design requested after the Captain's ruling to lean rows 4/5.
**Executes:** `2026-07-26-2359-architect-b3-costed-menu.md` §3.4's sketch, which deliberately left
this undesigned until the menu was answered. It is answered; this designs it.
**Puts one of my own prior rulings at risk** — see §3. That is intentional and is the first thing
this study tests.

---

## 1. Short answer

The menu says row 4 is "one lump — sync detection, candidate scoring, symbol demodulation still
folded together." That was true of the *B-series* instruments. It is not true of the project's
evidence as a whole: the C-series already closed two of the three sub-stages, and the residue is
much better localised than the menu credits (§2).

But in re-reading that evidence against the decoder's actual geometry, I found a defect that runs
through C.2, C.3, C.4 **and my own 17:00 ruling**: every one of those results matches candidates to
messages at **±10 Hz / ±0.5 s**, while our candidate lattice is **3.125 Hz × 0.08 s** and our
demodulator has no refinement stage. A "match" at that tolerance admits a candidate pointed up to
three frequency bins and six symbol-steps away from the signal — which demodulates to noise by
construction. So the single inference row 4 rests on — *"we can find these signals and cannot
demodulate them"* — is **not established**, and may be an artefact of the tolerance (§3).

The design therefore has four arms, cheapest and most falsifying first:

| arm | question | cost | needs |
|---|---|---|---|
| **R.1** | Does the ±10 Hz matcher measure detection, or coincidence? | ~1 hour, **no new capture** | frozen artefacts only |
| **R.2** | How much BER does a half-lattice (f,t) error cost? | ~half a session | B.2 harness + 2 recorded fields |
| **R.3** | Detection vs. estimation vs. demodulation, against ground truth | ~one session | same harness |
| **R.4** | **The cost signal, in dB** — our sensitivity vs. jt9's on identical audio | ~one session | same harness + jt9 |

All four are QA-runnable. **None requires a native or `src/` change** (HK-011 untouched) — the
exports they need (`ft8_set_candidate_diag_capture`, `ft8_set_candidate_diag_llr_capture`,
`ft8_get_last_candidate_diag`) already ship, opt-in and default-off, at shim ≥20260035.

## 2. What row 4 already knows (the menu understates this)

Recorded here because the scoping study should not re-measure what is already closed:

| front-end sub-stage | status | evidence |
|---|---|---|
| **Candidate *detection*** (does a candidate get proposed at all) | **Not the binding constraint** | C.4 + 17:00 ruling §2: flooding the candidate set (K=4/cap2000) yields **+2 matched decodes** against 61 → 376 false ones |
| **LLR magnitude / normalisation** | **Closed on evidence** | Phase 2c Part A: shrinkage sweep, **0/135** recoveries at every weight, **−3** at weight 1.0 |
| **BP/OSD correction power** | **Sound** | B.2: E = 5.69 of 135 (≈4.2%) — real, small, single-digit |
| **Symbol demodulation → LLR sign correctness** | **Where the residue lives** | Phase 2c Part B: THE 135 median BER **44.0%**, THE 567 **49.4%**, against a matched-hit control of **2.9%** |

So the honest statement of row 4's open question is not "which of three stages" — it is **one
stage**: the step from a candidate's (f, t) to 174 LLRs produces bits that are wrong on ~half their
positions. Everything upstream and downstream of that step has been measured and is not the
problem.

That is a much narrower target than the menu implies, and it is good news for row 4's cost — *if*
§3 does not undo it.

## 3. The load-bearing defect: a tolerance three bins wide

### 3.1 The geometry

From `ft8_shim.c:482-483` and `monitor.c:102-105`, measured not assumed:

- `K_FREQ_OSR = 2`, `K_TIME_OSR = 2`; band `f_min = 200 Hz`, `f_max = 3000 Hz` → 449 bins.
- FT8 tone spacing 6.25 Hz, symbol period 0.16 s → the candidate lattice is **3.125 Hz × 0.08 s**.
- `ftx_find_candidates` (`decode.c:296-320`) emits candidates **on that lattice only**. The
  `(freq_offset, freq_sub, time_offset, time_sub)` tuple goes straight to `ftx_extract_likelihood`
  → `ft8_extract_symbol`, which reads waterfall bins at that exact lattice point. **There is no
  fine-refinement stage in between.**

Consequence: even a *perfectly* detected signal is demodulated with up to **±1.56 Hz** frequency
error and **±0.04 s** time error from lattice quantisation alone — and every C-series match
tolerance is 6× coarser than that in frequency and 12× coarser in time.

### 3.2 What that does to the numbers already on the record

The grid holds 449 × 2 × 30 × 2 = **53,880** cells. A ±10 Hz / ±0.5 s window spans ~7 × 13 = **91**
of them — **0.169%** of the grid. Against C.4's own candidate populations, on a uniform-placement
assumption:

| setting | candidates/cycle | E[matches] by chance | P(≥1) if uniform | **observed `recov648`** |
|---|---:|---:|---:|---:|
| K=10 @600 | 220 | 0.37 | 31.0% | **16.2%** |
| K=4 @2000 | 2000 | 3.38 | 96.6% | **95.4%** |

At the flooded setting the chance model reproduces the observed number to within 1.2 points. The
"618 of 648 regained a candidate" result is **quantitatively indistinguishable from coincidence**.

At the shipped floor the observed rate is *below* chance (16.2% vs 31%), which is itself coherent —
candidates concentrate on strong signals, and the 648 are by definition weak-signal locations, so
they are depleted relative to uniform.

**This is an order-of-magnitude argument, not a proof.** Candidates are not uniformly placed, and I
have not modelled their clustering. R.1 settles it empirically and cheaply; the arithmetic only
establishes that it is worth settling.

### 3.3 What is and is not at risk

**At risk — my own 17:00 ruling §5.** Its claim that "at K=4 we can place a sync candidate at the
exact frequency and time where WSJT-X decodes a message at −8 dB, hand it to LDPC/OSD, and still
fail" is the sentence that promoted the structural avenue and localised the residue downstream of
sync. "Exact" is doing work the ±10 Hz tolerance does not support. If R.1 shows the matches are
coincidental, that inference fails, and **sync accuracy re-enters as a live explanation for the
whole 437** — a materially different and probably cheaper row-4 target than a demodulator rewrite.

**Also at risk — Phase 2c Part B's THE 567 number.** Those candidates were captured at K=4/cap2000
and matched at the same tolerance. A median BER of 49.4% is exactly what a coincidentally-matched
candidate pointed at empty spectrum produces. THE 135 (score ≥10, shipped config) is much less
exposed but not immune.

**Not at risk, and I want this stated so the correction is not read as broader than it is:**

- **C.4's +2 matched decodes stand.** That is a decode count, not a match; no tolerance enters it.
  Candidate *detection* is still not the binding constraint, and the score floor stays closed.
- **Phase 2c Part A stands** (shrinkage; 0/135, −3 at weight 1.0). No tolerance dependence.
- **B.2's E = 5.69 stands**, with one caveat entered below. Its Arm A self-check — P(decode) = 100%
  at BER 0–2.5%, falling to ~0% by BER 20% — is tolerance-independent and confirms the pipeline.
- **C.3's population split and its SNR result stand** (p = 1.1×10⁻⁷⁴). The gap population is
  genuinely weaker-signal; that was never a matching claim.

**One caveat to enter against B.2**: `b2_synthetic_calibration.py:166-174`'s `nearest_candidate`
uses the same ±10 Hz / ±0.5 s tolerance and then picks the frequency-nearest survivor. Its
"located" population therefore includes badly-offset candidates. This does not invalidate E (an
offset candidate has high BER and does not decode — it lands in the curve's tail, where it belongs),
but the transition-region *shape* that E is fitted to is partly a mixture of two different
conditions. R.2 measures this directly and will say whether E needs restating.

## 4. The four arms

Reading rules are fixed here, before any number exists — the same discipline as B.1/B.2/B.1b, and
for the same reason: I have a stake in the outcome of R.1 in particular.

### R.1 — the coincidence null (run first; nothing else is trustworthy until it reports)

**Question:** does "a candidate exists within ±10 Hz / ±0.5 s" measure detection, or the density of
our own candidate set?

**Method.** Purely offline, on the already-committed frozen artefacts — no decode run, no rebuild.
Re-run `c4_min_score_sweep_analysis.py`'s own matcher on the 648 population at every C.4 setting,
adding two comparison conditions:

1. **Frequency-displaced null.** Displace each target's frequency by δ ∈ {±150, ±300, ±450, ±600} Hz
   (wrapping inside 200–3000 Hz), keep `dt` and the cycle. Re-match. This is the same spectral
   neighbourhood at the same candidate density, with the signal removed by construction.
2. **Tolerance ladder.** Re-match the true targets at ±10 (as published), ±5, ±3.125 (one lattice
   step), and ±1.5625 Hz (half a step), each paired with dt tolerances of ±0.5, ±0.16 and ±0.08 s.

Report `recov648` for each cell of both conditions, at K=10@600 and K=4@2000 at minimum.

**Reading rule, fixed now:**

| result | reading |
|---|---|
| Null ≈ true within a few points at K=4@2000 | **The published `recov648` series measures candidate density, not detection.** My 17:00 §5 inference is withdrawn; sync accuracy is un-eliminated and R.2/R.3 become the main event. |
| True ≫ null at every tolerance | Detection is real at those locations; the residue is genuinely downstream, my 17:00 ruling stands as written, and R.2/R.3 proceed to separate estimation from demodulation. |
| True ≫ null at ±10 Hz but converging to null as tolerance tightens | **The most informative outcome**: detection is real but *imprecise*. The tolerance at which they converge is a direct measurement of our sync estimator's error, and R.2 prices what that error costs. |

**Cost:** one QA session-hour. **This arm can invalidate a ruling of mine for the price of an
afternoon, which is why it goes first.**

### R.2 — what a lattice-scale (f,t) error costs, in BER

**Question:** is a half-lattice offset enough to destroy demodulation on its own?

**Method.** Extend `b2_synthetic_calibration.py` — an already-validated harness, not a new
instrument. Two changes, both trivial:

1. **Record two fields the current harness computes and discards** (`run_arm_a`, lines 265-274):
   `cand["freq_hz"] − base_freq` and `cand["dt"] − pdt`. Everything else about the arm is unchanged.
2. **Plant at controlled offsets instead of random ones.** Currently `base_freq` is
   `rng.uniform(...)` (line 246), which spreads quantisation error uniformly and confounds it with
   SNR. Instead, at a **fixed, comfortable SNR** (pick from B.2's own curve: the level where Arm A
   shows P(decode) ≥ 95%), plant signals at deliberate offsets from the lattice:
   Δf ∈ {0, ±0.39, ±0.78, ±1.17, ±1.56} Hz and Δt ∈ {0, ±0.02, ±0.04} s, crossed, ≥8 repeats/cell.

Report median BER and P(decode) as a surface over (Δf, Δt).

**Reading rule, fixed now:**

| result | reading |
|---|---|
| BER at (±1.56 Hz, ±0.04 s) ≥ 35% while BER at (0,0) ≤ 10% | **Lattice quantisation alone accounts for the miss population's BER.** Row 4's target is a fine-refinement stage — bounded, well-understood, textbook engineering. This is the cheapest possible answer and swings 4-vs-5 hard toward 4. |
| BER rises with offset but stays < 25% at worst case | Refinement helps but is not sufficient; the demodulator is *also* weak. Row 4 is a two-part job; R.3 sizes the second part. |
| BER flat across the whole offset surface | Offset is not the mechanism; the demodulator is the whole story. Row 4 is a demodulator rewrite and should be priced against row 5 accordingly. |

**Cost:** half a QA session. **Highest information per hour in the whole study** — it tests the one
mechanism that is both cheap to fix and currently unexcluded.

### R.3 — full stage attribution against ground truth

**Question:** across the SNR range, how does the front end's loss divide between *detecting* a
signal, *locating* it accurately, and *demodulating* it?

**Method.** Same harness, Arm A geometry (isolated signals — co-channel is row 2's territory and
B.2 already showed Arm B's located-population is selection-biased), swept across B.2's SNR grid.
For each planted signal, whose (f, t, codeword) are known exactly, classify into exactly one of:

- **D-miss** — no candidate within one lattice step (3.125 Hz / 0.08 s). Detection failed.
- **E-loss** — a candidate exists within one step, but BER > 25% *and* R.2's surface says the
  observed offset accounts for it. Estimation failed.
- **X-loss** — a candidate exists at ≤ half a lattice step and BER > 25% anyway. Demodulation failed.
- **Decoded** — CRC-passing decode.

Report the four-way split by SNR decile. **The split at the SNR band where the real miss population
lives is the answer**: C.3 measured that band at a median of −8 dB (WSJT-X-reported), against +1 dB
for the shared-hit population.

**Reading rule, fixed now:** the stage carrying **> 50% of the loss** in the −12 to −4 dB band is
row 4's primary target and the thing any cost estimate must be built on. If no stage clears 50%,
row 4 is genuinely a multi-part rewrite and that fact — not a stage name — is the finding, and it
should be reported as strengthening row 5's relative position.

**Cost:** roughly one QA session, dominated by decode wall-time.

### R.4 — the cost signal, in dB (this is the arm the Captain's 4-vs-5 choice actually needs)

QA's §2 first bullet asked for a cost signal rather than attribution alone, noting that row 4's
437 measures *WSJT-X's* prize, not our cost of reaching it. This arm answers it, and I agree with
QA that it is worth more than attribution alone.

**The currency is dB of sensitivity**, because that is the only unit in which "how far behind is our
front end" and "what would closing it buy" are the same quantity.

**Method, two steps.**

1. **Measure the gap.** Take R.3's synthetic buffers and write each to WAV. Decode each buffer
   *twice* — once through our decoder, once through `jt9 -8 -d 1` (the same minimum-effort arm B.1
   used, so the number is directly comparable to the 437). Plot P(decode) vs SNR for both.
   **ΔSNR = the horizontal offset between the two curves at P(decode) = 50%.** Both decoders see
   byte-identical samples, so this is a clean sensitivity comparison with no capture-chain,
   band, or corpus confound anywhere in it.
2. **Convert dB to messages.** For each corpus, take the miss population's WSJT-X-reported SNR
   distribution and compute how many messages fall within x dB of our current threshold, for
   x ∈ [0, ΔSNR]. This yields a **curve, not a point**: messages recovered as a function of dB
   bought.

**Why the curve is the deliverable and not just ΔSNR.** It tells the Captain whether row 4 is
all-or-nothing. If 2 dB of a 5 dB gap recovers 70% of the 437, a partial front-end improvement is a
real product option and row 4 can be committed to incrementally, at a fraction of row 5's cost. If
the curve is flat until the last dB, row 4 is a single indivisible commitment that must be priced
against GPLv3 in full. **These two shapes imply opposite decisions, and nothing measured so far
distinguishes them.**

**Reading rule, fixed now:** report ΔSNR with its Wilson interval (the harness already has
`wilson_interval`), and report the dB→messages curve for **both corpora separately**. No single
summary number is to be quoted without the curve beside it.

**Honest limits, stated before the numbers:** ΔSNR is measured on synthetic CPFSK against real
GFSK traffic (B.2 §5's caveat, carried forward unchanged and unresolved); WSJT-X's reported SNR is
its own estimator, not a calibrated absolute; and this measures *WSJT-X's* achieved sensitivity,
which is a floor on what a reimplementation would need, not a promise of what one would cost. The
curve is a decision aid with a stated error bar, not a quotation.

## 5. Corpus ruling (QA §2, second bullet — my call, made explicit)

**The decomposition runs primarily on synthetic audio, not on either corpus.** This is the design's
main deliberate departure from B.1/B.1b and it needs stating plainly.

The reason is that stage attribution requires **ground truth** — the exact (f, t, codeword) of the
signal. Neither corpus has it. WSJT-X's `ALL.TXT` reports frequency quantised to 1 Hz and `dt` to
0.1 s, and both are WSJT-X's *estimates*, not truth. Attributing a 3.125 Hz lattice question to a
reference quantised at 1 Hz and biased by an unknown estimator is not a measurement. Every prior
attempt in this thread to localise the front end on corpus data has run aground on exactly this,
which is how the ±10 Hz tolerance came to carry as much weight as it did.

**Where the corpora do enter, they enter deliberately:**

- **R.1 uses corpus 1's frozen artefacts** — that is where C.4's `candidate_diag.csv` files live,
  and R.1's whole purpose is to audit those specific published numbers. Corpus 2 is not needed and
  would not add anything: R.1 is an audit of a metric, not a measurement of the band.
- **R.4 step 2 uses both corpora, separately and always reported separately.** This is the one place
  corpus choice is load-bearing rather than incidental: parity differed materially between them
  (64.1% vs 57.2%), and the dB→messages conversion depends entirely on the miss population's SNR
  distribution — precisely the thing that differs. Collapsing them would hide the effect the
  conversion exists to expose. B.1b showed the *shape* replicates and the *counts* do not; a cost
  curve is a count, so it gets both.
- **R.2 and R.3 use neither.** They are ground-truth experiments; corpus data cannot contribute.

**Held in reserve, and named so it is not forgotten:** if R.2/R.3 produce a clear stage attribution,
the natural confirmation is to check that the attributed stage's signature appears in corpus data —
e.g. if estimation error is the mechanism, then our candidates' offsets from WSJT-X's reported
frequency should be systematically larger for the miss population than the matched one. That is a
*validation* pass, cheap, and should be scoped only once there is something to validate. I am not
commissioning it here.

## 6. Sequencing and stop rules

1. **R.1 first, alone, and report before anything else starts.** It is an hour, it needs no capture,
   and it can invalidate both a published metric and a ruling of mine. Nothing downstream should be
   built on the current reading until it reports.
2. **R.2 second.** If R.2 hits its first row (lattice quantisation alone explains the BER), **stop
   and report**. That answer is cheap, actionable, and sufficient for the Captain's 4-vs-5 decision
   without R.3 — R.3's stage split would be confirming something already known. Do not run it out
   of completeness.
3. **R.3 only if R.2 is ambiguous or negative** (rows 2 or 3 of its rule).
4. **R.4 last, always run.** Whatever R.1–R.3 conclude, the Captain's decision needs a cost signal,
   and R.4 is the only arm that produces one. It is the one arm that should not be skipped on a
   cheap positive elsewhere.

**A stop rule that applies throughout:** if any arm's self-check fails — R.2's BER at (0,0) not
landing near zero, R.4's jt9 arm not reproducing B.1's own depth-1 behaviour on a shared buffer —
stop and report the self-check failure rather than the arm's result. Three self-corrections of this
class have already been caught mid-flight in this thread (B.1's anchor drift, B.2's clipping, C.4's
`MaxPass0Candidates` truncation); the pattern is well enough established to plan for.

## 7. What this design does not authorise or settle

- **No native or `src/` change** (HK-011 untouched). All four arms use already-shipped, default-off
  diagnostic exports. If any arm turns out to need a native export after all, that is an escalation
  back through QA, not a decision the running session makes.
- **No push, no merge** (HK-014 — committed locally, stops there).
- **No `pre_merge_check.py`** — Captain's trigger per HK-006, not run here.
- **Row 5 is untouched.** No position taken on GPLv3; it remains the benchmark row per menu §3.5.
  R.4 exists to give it something honest to be compared against.
- **Rows 2 and 3 stay sequenced behind row 4**, per menu §3.2/§3.3 — unchanged.
- **The `libft8.dll` size question and this branch's disposition** remain open and blocking on the
  Captain, unchanged. Answered separately in `2026-07-27-1600-qa-to-architect-dll-size-notification.md`;
  my ruling on whether it still blocks merge is owed and is not in this document.
- **NFR-021**: aggregates only here. R.2/R.3/R.4's synthetic messages are Q-prefix by construction;
  R.1 touches real callsigns only inside git-ignored `artefacts/` and must print counts only.
- **Per HK-015, this is a design, not a task.** `dev-tasks/` and `tasks.md` are QA's to author.

## 8. Honest caveats

- **§3's chance-match arithmetic assumes uniform candidate placement, which is false.** Candidates
  cluster on signal energy. The agreement at K=4@2000 (96.6% predicted vs 95.4% observed) is close
  enough to be worth acting on and loose enough that only R.1 settles it. I am not claiming the
  published `recov648` series is wrong — I am claiming it is unaudited and cheaply auditable.
- **My characterisation of what WSJT-X does differently** (coherent downconversion, fine time and
  frequency refinement before demodulation) is domain knowledge, not something measured in this
  repository. **The design does not depend on it** — R.2 and R.3 measure our own decoder against
  ground truth, and R.4 measures the gap end-to-end as a black box. I mention the mechanism only
  because it motivated looking at the lattice, and it should not be cited as a finding.
- **CPFSK vs GFSK** (B.2 §5) carries forward unresolved into R.2, R.3 and R.4. It is most exposed
  in R.4, where a synthetic-channel dB gap is generalised to real traffic. Stated in R.4 already;
  repeated here so it is not lost.
- **I authored the ruling R.1 tests.** The reading rules are fixed above before the numbers exist,
  and QA runs it, not me — the same mitigations that applied to my E prior in B.2. They are
  mitigations, not neutrality, and the Captain should weight them as such.
- **One decoder, one implementation.** Everything here measures *our* front end against ground
  truth and against jt9. None of it measures how hard our front end would be to *improve*, which is
  ultimately what row 4 costs. R.4's dB curve is the closest available proxy and it is a proxy.

## 9. Cross-references

- `2026-07-27-1630-qa-to-architect-menu-decision-and-row4-request.md` — the request this answers.
- `2026-07-26-2359-architect-b3-costed-menu.md` §3.4, §4.2, §6 — the sketch executed here.
- `2026-07-27-0130-architect-b1b-acceptance-and-menu-standing.md` §4 — row 4's scope, still one
  lump as of that note; §2 above narrows it and §3 reopens part of it.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §2, §5 — **the ruling R.1
  puts at risk**; §4's revised decomposition table stands except where §3.3 above marks it.
- `2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md` §4.2, §7 — THE 135 / THE 567 BER, and
  the truncation caveat §3.3 above extends.
- `2026-07-26-b2-synthetic-calibration-findings.md` — the harness R.2/R.3/R.4 extend, and the E
  caveat §3.3 enters.
- `2026-07-26-c3-candidate-generation-gap-findings.md` §3 — the miss population's SNR distribution,
  which R.3's reading band and R.4's conversion both use.
- `native/ft8_lib_build/patched/ft8/decode.c:296-320` (`ftx_find_candidates`),
  `patched/common/monitor.c:102-105` (band/bins), `src/OpenWSFZ.Ft8/Native/ft8_shim.c:482-483`
  (`K_FREQ_OSR`/`K_TIME_OSR`), `:1362` (`f_min`/`f_max`) — §3.1's geometry, read from source.
- `qa/cycleframer-alignment-replay/b2_synthetic_calibration.py:166-174, 233-275` — `nearest_candidate`
  and `run_arm_a`, the two functions R.2 modifies.

---

*Per HK-015 this is Architect → QA material: the arms above are a design for QA to scope and author
as `dev-tasks/`, not tasks issued by me. Per HK-014 this note is committed locally and goes no
further. Per HK-011 nothing here touches `src/` or native code. The decision the study feeds —
row 4 vs. row 5 — remains the Captain's, on the Captain's clock.*
