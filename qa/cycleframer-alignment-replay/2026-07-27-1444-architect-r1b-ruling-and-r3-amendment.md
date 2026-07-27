# D-001: R.1b executed correctly, but row 2 does not fire — my §5 table was unreadable as written. R.2 deferred, R.3 amended

**Author:** Architect, 2026-07-27 (14:44 UTC). **For:** QA (to run), and the Captain (§4, §9).
**Answers:** `2026-07-27-1930-qa-to-architect-r1b-notification.md` §5 — "rule on R.2's grid /
sequencing given no τ was returned, and on whether R.1b changes how R.3 should be designed."
**Ruling: the execution is accepted; the reading is not.** "Anti-correlation" must not be quoted.
The substantive changes are §5 (R.2 deferred), §6 (R.3 amended), §7 (sequencing).

---

## 1. Short answer

R.1b was run exactly as specified and its numbers are sound. **But row 2 of my §5 table cannot fire,
because row 2 was not readable from this instrument under any outcome.** The displaced null is not
strength-matched, and the 648 are — by C.3, at p = 1.1×10⁻⁷⁴ — a systematically weaker population
than the band at large. A detector whose precision improves with SNR will produce exactly the
observed depression without being "anti-correlated" with anything. That is every detector.

This is a defect in **my design**, not in QA's execution or QA's reading. QA applied my table
verbatim, which is what it was for, and flagged its own boundary caveat in §6 of the findings. The
table was the thing at fault.

There is also a second, independent reason to reject the anti-correlation reading, and it comes out
of QA's own numbers rather than from any argument of mine: **read as ratios rather than as
percentage-point differences, the effect is strongest at the *smaller* candidate budget, in 12 cells
out of 12.** That is the signature of a truncated ranked list, not of a scoring metric that points
away from these locations. §3 sets it out.

What survives is worth stating plainly and is enough for everything downstream:

> At lattice resolution, our candidate set carries **no demonstrable location information** about the
> 648. Whether it carries *negative* information is not measurable with this instrument.

Rows 1 and 2 of my §5 table therefore collapse into one another. Their consequences were nearly
identical anyway, which I should have noticed when I wrote them.

## 2. Reason one — the null is not strength-matched, and my "conservative direction" argument reverses

In §2 of the 19:00 note I observed that the displaced null wraps inside 200–3000 Hz, lands near
other real signals, and is therefore **inflated** — and I said this made the finding conservative.

That was true **for row 1 only.** An inflated null makes "true ≈ null" harder to reach, so row 1
firing against an inflated null is a strong result. But the same inflation makes "true < null"
*easier* to reach. I stated a directional property as though it were a general strength, and then
wrote a table with a row that the property biases toward. That is the error.

Concretely, what the tight-tolerance cells compare is:

| | population sampled | typical signal strength |
|---|---|---|
| TRUE | the 648 — messages WSJT-X decoded and **we missed** | median −8 dB (C.3) |
| NULL | arbitrary points in a band whose occupied spectrum is dominated by signals **we decoded fine** | median +1 dB for the shared-hit population (C.3) |

A candidate's *positional accuracy* is a function of SNR in any sync detector — the peak is sharper
when there is more signal to find it with. So "true sits below null at tight tolerance" is the
predicted result of a perfectly ordinary detector operating on a weaker population. It does not
discriminate between:

1. **Anti-correlation** — the scoring metric actively rewards something other than where these
   signals are;
2. **Strength-dependent precision** — the detector fires near them, less accurately, because they
   are weak;
3. **Ranked-list truncation** — it would fire near them, but they rank below the cap (§3).

All three predict the observed sign. The instrument separates none of them. Row 2 asserted (1).

**This also disposes of QA's §3.1 and my own §9 caveat, and disposes of them more harshly than
either put it.** I wrote that "R.2's widened grid is still a guess *if* R.1b returns no separation
tolerance." There was never a branch in which it could have returned a usable one: a τ measured
against a strength-mismatched null would have been contaminated by the same confound, and row 3
would have handed R.2 a number that looked empirical and was not. R.1b could not size R.2's grid
under **any** outcome. QA's observation was right and the reason is worse than stated.

## 3. Reason two — the effect tracks the candidate budget, in 12 cells out of 12

QA reported the two settings in percentage points and concluded K=10@600 was "underpowered." Read as
**ratios** (true ÷ null), the same table says something quite different and considerably more useful.

| freq tol | dt tol | ratio @cap600 | ratio @cap2000 |
|---:|---:|---:|---:|
| 10 | 0.5 | 0.98 | 1.05 |
| 10 | 0.16 | 0.61 | 0.93 |
| 10 | 0.08 | 0.41 | 0.77 |
| 5 | 0.5 | 0.62 | 0.91 |
| 5 | 0.16 | 0.37 | 0.62 |
| 5 | 0.08 | 0.29 | 0.54 |
| 3.125 | 0.5 | 0.50 | 0.83 |
| 3.125 | 0.16 | 0.33 | 0.57 |
| 3.125 | 0.08 | 0.23 | 0.53 |
| 1.5625 | 0.5 | 0.50 | 0.83 |
| 1.5625 | 0.16 | 0.46 | 0.57 |
| 1.5625 | 0.08 | 0.43 | 0.54 |

**The relative depression is deeper at cap 600 than at cap 2000 in every single cell — 12 of 12, no
exceptions, monotone.** In the tight cells the mean ratio is ≈0.35 at cap 600 against ≈0.56 at cap
2000: the effect is roughly 1.6× stronger at the smaller budget. K=10@600 is not the underpowered
setting. On the scale that matters it is the setting showing the *larger* effect, and QA's
"underpowered" reading is an artefact of comparing differences on a 3% base with differences on a
35% base.

**Why this points at truncation.** Two facts already on the record combine:

- `ftx_find_candidates` sorts the candidate heap into **descending sync-score order** before
  returning, so `MaxPass0Candidates` is a **head-take of the top N by score**, not a random sample
  (my 2026-07-26 20:30 ruling §7.1, `native/ft8_lib_build/patched/ft8/decode.c:340–353`).
- The 648 are weak, and weak signals score low.

Shrink a score-ranked list and you preferentially delete exactly the population under study, while
barely touching the strong signals the null is sampling. The ratio must fall. It does, everywhere.

**One property makes this comparison cleaner than it looks:** `recov648` is computed against the
*candidate list*, which `ftx_find_candidates` produces **before** any decoding. The number of LDPC
passes cannot affect it. So although the two settings differ nominally in both K and cap, the only
operative difference for this measurement is **600 vs 2000**, and the ratio table is a
single-variable candidate-budget sweep that we already own and had not read as one.

I am not claiming truncation *is* the explanation — that would repeat the mistake of reading one
number as one mechanism. I am claiming it is a third live explanation that the instrument cannot
exclude, that it predicts a budget-dependence which the other two do not obviously predict, and that
the data show that budget-dependence cleanly. It is also, if true, by far the cheapest of the three
to act on — which is why §6 makes it a first-class axis rather than a footnote.

## 4. What changes on the record, and what does not

**Does not change.** Everything in the 19:00 note's §3 accounting stands exactly as written — C.4's
+2, B.2's E = 5.69, C.3's SNR split, B.1/B.1b's 437, and the withdrawals of THE 135 / THE 567's
interpretation. R.1b is downstream of all of it. **Row 4's prize is still 437.**

**Changes.** Three things:

1. **"Anti-correlation" is withdrawn as a finding before it was ever used.** It must not be quoted in
   the menu, in a Captain-facing summary, or as a premise in any later arm. If it appears anywhere
   downstream of this note, that is a defect.
2. **The claim that survives is weaker and cleaner:** no demonstrable location information at lattice
   resolution. This is unchanged in force from R.1 + R.1b's row-1 branch, and it is all that
   downstream work actually needs.
3. **The candidate cap is promoted from a harness nuisance to a live hypothesis about the mechanism.**
   It has now bitten this study three times (C.4's 140→600 truncation; THE 567's 279/567 subsample;
   and now, as a possible confound, here). My 20:30 ruling said "the third time it happens it should
   become a guard that errors rather than truncates." **This is the third time.** That guard is now
   owed — but as a QA-authored item under HK-011, not as anything this note issues.

## 5. R.2 — deferred, not revised. QA's §3.2 is accepted in full

QA argued that R.2 "presupposes a candidate exists to be offset," and therefore does not test the
mechanism now in play. **That is correct, and it is correct under all three of §2's surviving
explanations, not only under anti-correlation.** R.2 measures what a known offset costs. Every live
explanation is about whether a candidate is produced at all.

I am not widening R.2's grid. I am **taking R.2 out of the sequence** until R.3 says whether the
class it measures is populated. Its three deliverables are dispositioned as follows:

| R.2 deliverable | disposition |
|---|---|
| The offset→BER surface | **Deferred.** Runs only if R.3 shows the E-cand class (§6) materially populated. |
| The **inverse map** (BER → implied offset) | **Deferred with it.** Its stated purpose was to reinterpret THE 135's 44.0% BER — a corpus number whose population is matcher-defined and, after R.1, unreadable. The bridge it was built to be no longer has a far bank. |
| Recording the two discarded fields (`cand["freq_hz"] − base_freq`, `cand["dt"] − pdt`) | **Kept, and moved into R.3.** They cost nothing, they settle B.2's `nearest_candidate` caveat, and R.3 needs them for §6's classifier anyway. |

**Net effect on the study's size: it gets smaller.** Deferring R.2 removes about half a session;
§6's amendment to R.3 adds appreciably less than that, because it reuses buffers R.4 will already
have generated and persisted. After three consecutive notes in which I added scope, I want it on the
record that this one subtracts it — and that the subtraction is the *consequence* of taking QA's
argument seriously, not a schedule gesture.

## 6. R.3 amended — a detection-vs-budget axis, and E-loss decoupled from R.2

R.3 is the right arm for all of this: ground truth, planted signals at known (f, t, codeword), **no
matcher and no null anywhere in it.** It is structurally immune to both defects that have now cost
me two rulings. Two amendments.

### 6.1 New: the detection axis (this is the ground-truth replacement for R.1/R.1b)

For each planted signal, report **P(candidate within τ)** as a function of:

- **SNR** — B.2's existing grid, with the −12 to −4 dB band called out separately, since C.3 puts the
  real miss population's median at −8 dB;
- **candidate cap** — **600, 2000, and one run with the cap effectively removed** (large enough that
  no cycle reaches it; assert this rather than assume it);
- **τ** — the same 4×3 ladder R.1b used, so the two are directly comparable.

This measures, against ground truth, precisely what the displaced null was a proxy for — and it
separates all three of §2's explanations, which the null could not separate at all:

| observation | explanation it selects |
|---|---|
| Detection recovers substantially when the cap is lifted | **Truncation / ranking.** The detector finds these signals and we throw them away. |
| Detection tracks SNR smoothly and is simply low at −8 dB, cap-independent | **Strength-dependent detection.** Ordinary sensitivity limit; row 4's target is detector sensitivity. |
| Detection stays poor at −8 dB even uncapped, while comparable-SNR signals elsewhere are found | **Anti-correlation**, properly evidenced this time — the scoring metric is the target. |

**Why the cap axis is worth its cost, in one sentence:** if lifting the cap materially recovers
detection, row 4's front-end problem is a *capacity and ranking* problem rather than a
signal-processing one — and that is very much cheaper than either of the alternatives, which bears
directly on the row-4-vs-row-5 decision the Captain is holding.

**Self-check, mandatory, reported as a self-check failure and not as a result if it fails:** at the
top of B.2's SNR grid, P(candidate within one lattice step) must be ≈100%. If a planted signal at
comfortable SNR is not detected, the harness is wrong and nothing else in the arm may be read.

### 6.2 Amended: E-loss no longer depends on R.2

R.3's original E-loss class was defined as "a candidate exists within one step, but BER > 25% **and
R.2's surface says the observed offset accounts for it**." With R.2 deferred that definition
dangles. Replaced, so R.3 stands alone:

- **D-miss** — no candidate within one lattice step (3.125 Hz / 0.08 s). Detection failed.
- **X-loss** — candidate at ≤ **half** a lattice step, BER > 25% anyway. Demodulation failed; the
  offset is too small to be blamed without R.2 and does not need it.
- **E-cand** — candidate between half and one step, BER > 25%. **Estimation-*candidate*, explicitly
  unconfirmed.** Reported under that name, never as "estimation failed."
- **Decoded** — CRC-passing decode.

**R.2's entire remaining purpose is to resolve E-cand**, and it runs only if E-cand is materially
populated. This is a better justification than R.2 previously had, and it makes the dependency point
the right way round: R.3 sizes R.2, instead of R.2's surface being needed to define R.3's classes.

**Reading rule, unchanged and still fixed:** the stage carrying > 50% of the loss in the −12 to −4 dB
band is row 4's primary target. If no stage clears 50%, that fact is the finding and it strengthens
row 5's relative position. **Added:** the split must be reported at each cap setting separately and
**never collapsed across caps** — collapsing is what made R.1b's budget-dependence invisible until it
was re-read as ratios.

## 7. Sequencing

**Revised order:** R.1 ✅ → R.1b ✅ → **R.4** → **R.3 (amended)** → **R.2 (only if E-cand is
populated)**.

R.4 stays first, for the three reasons given in the 19:00 note §7(b), all of which this result
strengthens rather than weakens: it is the arm the Captain's decision needs; it has no matcher in it
anywhere; and it generates and persists the shared buffer corpus that R.3's amended detection axis
now depends on more heavily than before. R.4's method, reading rule and limits are **unchanged** —
ΔSNR with its Wilson interval, the dB→messages curve for both corpora separately and never
collapsed, no summary number quoted without the curve beside it.

## 8. What I considered and declined

For discipline's sake, since this thread's failure mode has been accretion: the obvious cheap fix to
R.1b is a **strength-matched null** — restrict the displaced null to points ≥25 Hz from any WSJT-X
decode in that cycle, giving a quiet-spectrum control. ~30 minutes on the same script and frozen
artefacts.

**Declined.** R.3's §6.1 detection axis answers the same question with ground truth, no matcher, no
null, and an SNR axis the corpus cannot provide — and it is on the critical path regardless. Running
a better null first would produce a weaker version of a result we are about to obtain properly, and
would be the fourth 30-minute add-on in this thread. If R.3 is blocked or deferred for an unrelated
reason, this is the fallback to reach for, and that is the only circumstance in which it should run.

## 9. What I owe the Captain

The row-4 narrative has now been revised **three times in a single working day** — the 17:00 note
(sync fine, residue downstream), the 19:00 note (withdrawn, sync live again), and this one
(narrowing what 19:00's follow-up was permitted to conclude). The Captain should weight my
characterisations of row 4's *mechanism* accordingly, and I would rather say that a third time than
let the pattern go unnamed.

Three points of context that I think are the honest read:

- **The 437 has never moved.** Every revision has been about *why* row 4's front end fails, never
  about *how much*. The quantity the 4-vs-5 decision rests on is the stable part of this study.
- **This revision reduces scope rather than adding it,** and it came from QA's argument rather than
  from mine.
- **The decision does not need this thread to converge.** R.4 is the arm that serves it, it is next,
  and it is the one arm structurally immune to the defect class that has caused all three revisions.
  If the Captain wants the decision sooner than the attribution, R.4 alone is a defensible stopping
  point and I would not argue against calling it there.

## 10. What this does not authorise or settle

- **No native or `src/` change** (HK-011 untouched). R.4/R.3 use already-shipped, default-off
  diagnostic exports at shim ≥20260035. **One flag:** §6.1's uncapped run may need
  `MaxPass0Candidates` raised beyond 2000. If that cannot be done from the managed side alone, it is
  an escalation back through QA, not a call the running session makes.
- **The `MaxPass0Candidates` guard** (§4.3) is owed but is **QA's to author**, not issued here.
- **No push, no merge** (HK-014 — committed locally, stops there). **No `pre_merge_check.py`**
  (HK-006 — Captain's trigger).
- **Row 5 untouched.** No position on GPLv3; still the benchmark row per menu §3.5. Rows 2 and 3 stay
  sequenced behind row 4.
- **The `libft8.dll` size question and this branch's disposition** remain open and blocking on the
  Captain. My ruling on whether the size delta blocks merge is still owed and is still not here.
- **NFR-021:** R.3/R.4 messages are Q-prefix by construction; aggregates only.
- **Per HK-015 this is a design, not a task.** `dev-tasks/` and `tasks.md` are QA's to author.

## 11. Honest caveats

- **I am now three notes deep in correcting my own rulings, and this note both identifies the defect
  and designs its replacement.** The same partial mitigation applies: §6.1's reading rule is fixed
  before any number exists, and QA runs it. That is a mitigation, not neutrality.
- **The ratio argument in §3 is my re-reading of QA's table, not a new measurement.** It is
  arithmetic on published numbers and can be checked in a minute, but "budget-dependence implies
  truncation" is an inference, and the two settings were separate captures — cycle-level variation
  between them is not controlled. It is a hypothesis for §6.1 to test, not a finding.
- **CPFSK vs GFSK (B.2 §5) is now more exposed, not less.** §6.1 measures detection against
  synthetic signals. If our detector's behaviour near weak signals depends on modulation shape, the
  synthetic detection curve will not transfer cleanly to the corpus. This caveat has been carried
  unresolved since B.2 and is the largest single threat to R.3's amended arm.
- **None of this measures how hard our front end would be to *improve*,** which is what row 4 
  actually costs. R.4's dB curve remains the closest available proxy and remains a proxy.
- **Four self-corrections of this class have now been caught mid-flight** — B.1's anchor drift,
  B.2's clipping, C.4's `MaxPass0Candidates` truncation, R.1 — and R.1b makes five, this time
  catching a defect in a *reading rule* rather than in a harness. The stop rules that have produced
  them survive unchanged.

## 12. Cross-references

- `2026-07-27-1930-qa-to-architect-r1b-notification.md` — the notification this answers; its §3.2 is
  accepted in full and drives §5.
- `2026-07-27-r1b-tight-tolerance-null-findings.md` — the result. Execution accepted; §4's reading
  superseded by §2/§3 above. Its §6 first caveat was closer to the mark than it claimed.
- `2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md` — **§5's reading table (row 2) is
  withdrawn as unreadable; §6's R.2 revision is superseded by §5 above; §7's sequencing is superseded
  by §7 above.** §3's accounting stands unchanged.
- `2026-07-27-1730-architect-row4-scoping-design.md` §4 — R.3's class definitions **amended by §6.2
  above**; R.4 stands unchanged.
- `2026-07-26-2030-architect-c2-phase2c-ruling.md` §7.1 — the head-take-by-score property §3 rests on,
  and the "third time it happens" guard now owed.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the SNR split (−8 dB vs +1 dB) §2 rests on.
- `2026-07-26-b2-synthetic-calibration-findings.md` §5 — the CPFSK/GFSK caveat, most exposed by §6.1.

---

*Per HK-015 this is Architect → QA material: the amended R.3 and the R.4-first sequence are a design
for QA to scope and author, not tasks issued by me. Per HK-014 this note is committed locally and
goes no further. Per HK-011 nothing here touches `src/` or native code. The decision the study feeds
— row 4 vs. row 5 — remains the Captain's, on the Captain's clock.*
