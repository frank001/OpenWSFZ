# D-001 row-4 decomposition — REVISION 2, competition-scoped
# Supersedes the 2026-07-27 four-arm design. Two mechanisms, three tracks, one free arm first.

**Author:** Architect, 2026-07-31 (13:55 UTC, `date -u`, per HK-017). Repo at `c37d46d`.
**For:** QA (to scope and author as `dev-tasks/`), and the Captain (§8, §9 — the authorisation
and the menu consequence).
**Requested by:** the Captain, 2026-07-31, on the Measurement D escalation.
**Supersedes:** `2026-07-27-1730-architect-row4-scoping-design.md` — which is **not discarded**;
§6 carries three of its four arms forward intact. That document currently lives only on branch
`d001-c4-min-score-sweep` and is not on `main`; §11 notes what that means.
**Standing reference:** `2026-07-27-2012-…-d001-closing-handoff.md` §0 stop rule, untouched.

---

## 0. Correction that precedes this document

The Measurement D "withheld figures" I promised as an independent check **never reached the
Captain and no longer exist**. Corrected in full at
`2026-07-31-1344-architect-correction-measurement-d-withheld-figures-do-not-exist.md`. Measurement
D's result is unaffected — it stands on a reading rule pre-registered in git at `0e23697` before
the run — but nothing below should be read as awaiting that comparison. It is not coming.

## 1. Short answer

The 07-27 design asked *"which front-end sub-stage loses the signal?"* and answered it with
experiments on **isolated synthetic signals** — Arm A geometry, co-channel explicitly excluded as
"row 2's territory."

Measurement D has now measured an **18.21-point loss at matched SNR that only exists when other
signals are present.** A decomposition built on isolated signals cannot see it, by construction.

But the correct response is **not** to throw the 07-27 design away and re-point it at competition.
Reading Measurement D §6.2's own numbers back carefully shows something the write-up did not draw
out: **there are two mechanisms of comparable size, not one.** The 07-27 design targets one of
them correctly and is blind to the other. This revision keeps it for the first and adds a track
for the second.

The entry point is **one free arm, S.1**, which splits the new mechanism into the two engineering
outcomes that cost most differently — and which needs no new data, no decode run, no native
rebuild, and no `src/` change.

## 2. The two mechanisms — read out of Measurement D §6.2

Measurement D's §6.2 table was published as a descriptive extra about a "capacity ceiling." Taking
its per-quartile yields as ratios makes a second thing visible:

| band | quartile | ref decodes/cycle | ours/cycle | ours ÷ ref |
|---|---|---:|---:|---:|
| 80m | Q1 | 2.21 | 2.15 | **97.3%** |
| 10m | Q1 | 5.17 | 4.33 | 83.8% |
| 80m | Q4 | 9.61 | 8.20 | 85.3% |
| 10m | Q4 | 12.61 | 9.32 | 73.9% |
| **20m** | **Q1 (sparsest)** | 23.15 | 14.16 | **61.2%** |
| 20m | Q2 | 35.09 | 19.15 | 54.6% |
| 20m | Q3 | 40.89 | 21.67 | 53.0% |
| **20m** | **Q4 (densest)** | 52.32 | 23.01 | **44.0%** |

**⚠️ These are unmatched count ratios, not the matched recall Measurement D reads.** They are
orientation for arm design only. **They are not citable as a result**, and specifically the
cross-band rows remain confounded exactly as Measurement A established. I am putting the
restriction in the same breath as the table because a monotone-looking eight-point series is
precisely the object this programme has already been burned by twice.

With that restriction stated, two things follow that the arms must account for:

**Mechanism 1 — the baseline deficit.** In 20m's *sparsest* quartile we still return only ~61% of
what the reference does. Competition cannot explain this: these are the least crowded cycles in
the band. Something costs us ~39% before density enters at all. **This is what the 07-27 design
was built to decompose, and that design remains correct for it.**

**Mechanism 2 — the density penalty.** From 20m Q1 to Q4 we lose a further ~17 points, and
Measurement D confirms 18.21 points of it survives SNR matching inside one band, one antenna, one
session. **Nothing in the 07-27 design addresses this.**

The two are roughly the same size. Neither is a rounding error on the other, and **an engineering
commitment that fixes only one leaves most of the gap in place** — which is exactly the
wrong-sized commitment the B.3 menu caveat warns against.

### 2.1 One thing the within-band series does establish

The four 20m quartiles are a **dose-response inside a single band** — same antenna, same receiver,
same session, same propagation. 61.2% → 54.6% → 53.0% → 44.0% against 23.15 → 35.09 → 40.89 →
52.32 decodes/cycle.

A monotone dose-response inside one band is a materially stronger form of evidence than the
cross-corpus density law that task 4 destroyed, because the confound that killed that law — band
identity varying with band density — is absent by construction. **This does not resurrect the
density law**, which stays struck as a predictive instrument per `1212`; it is a statement about
one band's internal behaviour, which is a different and much better-controlled claim.

I am **not** fitting a curve to it. Task 4's lesson was that a two-parameter fit to a handful of
points cannot bear predictive weight, and four points is not meaningfully better than three. The
dose-response is a reason to believe the mechanism is causal and a guide to where the arms should
sample. It is not a law and must not be cited as one.

## 3. Candidate mechanisms for the density penalty

Named so the arms have something to falsify, and so nobody has to reconstruct my reasoning later.

| # | mechanism | prediction | if true, row 4 is… |
|---|---|---|---|
| **H1** | **Candidate budget.** `K_MAX_CANDIDATES = 140` on pass 0. Dense cycles have more real signals than the cap can carry; weak ones are crowded out by strong ones | Penalty is **cycle-global** — depends on total occupancy, not on spectral neighbourhood | **Cheap.** A constant, already-swept, with a built harness. Ships incrementally |
| **H2** | **Wideband masking.** Strong signals distort the noise-floor / normalisation estimate, depressing LLRs for weak signals anywhere in the band | Penalty is **broadly frequency-dependent**, falling off over hundreds of Hz | **Moderate.** A normalisation change, bounded |
| **H3** | **True co-channel collision.** Overlapping signals in time-frequency. jt9 handles this with subtractive multi-pass demodulation; we do not | Penalty is **sharply frequency-local**, within ~50 Hz (one FT8 signal width) | **Expensive.** Subtraction-pass architecture — a large share of what makes jt9 good. Strengthens row 5 |
| **H4** | **Hash-table over-rejection.** More messages per cycle → more duplicate-hash collisions → spurious rejects (`hashTableRejectCount` 595→690 across the c1 sweep) | Penalty tracks message count with **no frequency structure at all** | **Trivial.** A bug fix |

**H1 and H3 imply opposite decisions and opposite costs.** Measurement D §6.2's flattening is
consistent with both, which is precisely why it cannot be acted on as it stands. Separating them
is the whole job of arm S.1 — and S.1 separates them **for free**.

## 4. Track B — the density penalty ⟨new; this is the priority⟩

### S.1 — spectral locality (run first, alone; free)

**Question:** is the density penalty frequency-**local** or cycle-**global**?

**Cost:** half a QA session. **Frozen artefacts only** — no decode run, no rebuild, no new
capture, no `src/`. Reuses `anova_common.parse_all_txt` (which already carries `freq_hz` per
decode) and Measurement D's own matching, unmodified.

**Corpus:** `artefacts/20260729_live_run_1831-8081/owsfz/20m/` — `ALL.TXT` against `jt9_ALL.TXT`.
The 20m arm only; 10m/80m as free replication, reported not decisive, exactly as in Measurement D.

**Method.** Unit of analysis is one reference decode. Outcome is matched-by-us (1/0), resolved by
Measurement D's mechanism (once, over the full corpus, in reference arrival order — never
re-resolved per stratum). For each reference decode compute:

- `n_cycle` — reference decodes in that cycle (Measurement D's density).
- `n_local(W)` — reference decodes in the *same cycle* within ±W Hz of this one, excluding itself,
  for **W ∈ {25, 50, 100, 200, 400, 800} Hz**.

Then a 2×2 stratification, per 2 dB SNR bin as in Measurement D:

- Split cycles at Measurement D's own published cutoffs (sparse ≤30, dense ≥43 ref decodes/cycle).
- Within each, split decodes at that stratum's median `n_local(W)`.
- Compute matched recall in all four cells; take medians across usable bins.

Report two quantities:

- **Δ_local** = recall(low `n_local`) − recall(high `n_local`), averaged over the two `n_cycle`
  strata. *Effect of local crowding, cycle occupancy held roughly constant.*
- **Δ_cycle** = recall(low `n_cycle`) − recall(high `n_cycle`), averaged over the two `n_local`
  strata. *Effect of cycle occupancy, local crowding held roughly constant.*

**Reading rule — fixed now, before any number exists. Evaluated in strict order.**

| # | condition (at W = 50 Hz) | reading | consequence |
|---|---|---|---|
| 1 | Δ_local ≥ 8 pts **and** Δ_cycle < 3 pts | Penalty is frequency-local | **H3/H2.** Row 4 needs multi-signal handling. Expensive; strengthens row 5's relative position. **S.2 is not run.** Escalate before any engineering |
| 2 | Δ_cycle ≥ 8 pts **and** Δ_local < 3 pts | Penalty is cycle-global | **H1/H4.** Capacity or budget. **S.2a runs.** A cheap component is likely; strengthens row 4 |
| 3 | Both ≥ 8 pts | Two sub-mechanisms | Both proceed. Report the ratio; it prices the split |
| 4 | Both < 3 pts | Effect vanishes under joint stratification | **Measurement D's effect is confounded by something neither variable captures. Escalate. Do not rationalise.** |
| 5 | else | Partial | Report as ambiguous. **Do not interpret further.** Escalate |

**The W-ladder is diagnostic and must be reported at every W**, but the rule reads W = 50 Hz only
(one FT8 signal width — the scale at which true co-channel overlap occurs). The *shape* across W
separates H3 from H2: a Δ_local that peaks at 25–50 Hz and decays is overlap; one that is flat out
to 800 Hz is a wideband normalisation effect.

**Mandatory null.** Shuffle `freq_hz` within each cycle — preserves `n_cycle` and the SNR
distribution exactly, destroys locality — and recompute Δ_local. **It must land within ±2 pts of
zero.** If it does not, the locality metric is measuring something structural about how frequencies
are distributed and **the arm is void**; report the null failure, not the result.

**Mandatory self-checks — all four must pass or the run is void** (same discipline as Measurement
D §1, which is why that run was trustworthy):

1. **Matching gate** — reproduce 20m matched count **24,201** exactly.
2. **Null** — shuffled Δ_local within ±2 pts of zero (above).
3. **Common support** — ≥10 SNR bins with n ≥ 20 in *all four* cells.
4. **Duplicate-key** — dup-key rate gap across cells < 1/10 of the measured effect.

**Descriptive extra, not rule-bound:** repeat with neighbour *power* (sum of neighbour SNRs within
W) in place of neighbour *count*. Masking should track power; collision should track proximity.
This is a lead for whoever scopes the fix, not a finding.

**Stated limitation.** S.1 controls the target decode's own SNR but **not its neighbours'
strength**. It cleanly separates local from global; it does not by itself separate H2 from H3 — the
W-ladder shape and the power extra are indicative, not decisive. If rule row 1 fires, expect to
need one more arm to split H2 from H3, and price it then rather than pre-committing here.

### S.2a — does the candidate cap bind harder when the band is busy? ⟨gated on S.1 row 2 or 3⟩

**Question:** at 52 ref decodes/cycle, is the material discarded at the `K_MAX_CANDIDATES = 140`
boundary better than the material discarded at ~19/cycle?

**Why this is not already answered.** The c1 sweep found pass-0 candidate counts already
**saturated at the cap** (median exactly 140.0) at ~19 ref decodes/cycle, and raising it to 300/600
bought **+0.93%** — the extra ~80 candidates were overwhelmingly the same low-confidence
population. *"The cap binds"* is therefore already known and already known not to matter much
**in the sparse regime**. The open question is whether the **marginal value** of candidates beyond
140 rises with density. It is untested, not refuted — the standing blacklist entry says exactly
this.

**Method.** No rebuild. Run the shipped 140 build over the dense-quartile 20m WAVs with the
already-shipped, default-off diagnostic exports (`ft8_set_candidate_diag_capture` et al., shim
≥20260035) and record the **score distribution at the cap boundary** — specifically the score of
the 140th-ranked candidate — against the same statistic on the sparse quartile.

**Reading rule, fixed now:**

| result | reading | consequence |
|---|---|---|
| Boundary score materially higher on dense cycles (≥ the sparse quartile's 75th percentile) | The cap is discarding better material when the band is busy | **S.2b is worth its rebuild cost.** Return to the Captain, priced |
| Boundary score comparable or lower on dense cycles | The cap discards the same noise either way | **H1 is dead. S.2b is not run.** Re-read S.1's result against H4, then escalate |

**Cost:** half a QA session, dominated by decode wall-time. No native build.

### S.2b — the dense-regime cap sweep ⟨gated on S.2a; needs the Captain, priced⟩

Re-run the c1 sweep (`K_MAX_CANDIDATES` ∈ {140, 300, 600}, pass 0 only) against the **dense 20m
stratum** instead of the ~19/cycle corpus c1 used.

**This is a different cost class** — three native rebuilds — and per the Measurement D spec §7 it
returns to the Captain priced rather than being started off the back of a cheap positive. **Cost:
~1 QA session plus a Developer session for the builds (HK-011).**

**Two pitfalls, both already on record — reuse, do not rediscover:**

1. **The stack-safety fix must be present.** `ft8_shim.c`'s pass-loop `candidates[]` array was
   hardcoded to 200; without `K_MAX_CANDIDATES_ANY_PASS` the 300/600 arms silently overrun it.
   Fixed and verified behaviourally neutral at 140 in the c1 work.
2. **`dotnet run --no-build` does not refresh the native DLL.** c1's first 300/600 attempts
   silently ran against the stale 140 binary. An explicit `dotnet build` between each native
   rebuild is mandatory, and pass-0 candidate counts exceeding 140 is the confirmation that the
   right binary loaded.

**Self-check:** the 140 arm must reproduce the dense stratum's already-published matched count
before the 300/600 deltas are trusted — the same anchor discipline c1 used against its 1288.

## 5. Track A — the baseline deficit ⟨carried forward from 07-27, unchanged in substance⟩

Mechanism 1 is still real, still ~39% in 20m's sparsest quartile, and the 07-27 design is still
the right instrument for it. Carried forward:

| arm | question | status |
|---|---|---|
| **R.1** | Does the ±10 Hz / ±0.5 s matcher measure detection or coincidence? | **Still owed, still ~1 hour.** Audits an unaudited metric that C.2/C.3/C.4 and one of my own rulings rest on. **Demoted below S.1, not dropped** |
| **R.2** | What does a half-lattice (f,t) error cost in BER? | **Unchanged.** Still the highest information-per-hour arm for mechanism 1 |
| **R.3** | Detection vs. estimation vs. demodulation against ground truth | **Unchanged**, still gated on R.2 being ambiguous or negative |
| ~~R.4~~ | The dB cost curve | **Replaced by S.3** — R.4's isolated-signal geometry cannot price the density penalty |

**Why Track A is demoted rather than run first.** It is not less important — the two mechanisms
are comparable in size. It is that S.1 is **free and splits a decision worth an order of magnitude
in engineering cost**, while Track A's arms refine a target whose general shape is already known.
Cheapest and most falsifying first, exactly as the 07-27 design sequenced its own arms.

**One correction to carry forward:** R.2 and R.3's reading rules should note that a stage
attribution measured on isolated signals is now known to describe **only mechanism 1**. Neither
arm's conclusion may be stated as *"the front end's loss divides as…"* without that scope
attached — that phrasing would silently reclaim mechanism 2's share.

## 6. Track C — S.3, the cost signal the menu actually needs

**S.3 replaces R.4.** R.4 asked *"how many dB behind jt9 is our front end on isolated signals?"*
The question the menu now needs is:

> **Does jt9 suffer the same density penalty we do?**

This is the single most decision-relevant unknown on the board, and neither Measurement D nor
anything else on record answers it:

- If jt9's recall **also** degrades with density (from a better baseline), then a large share of
  the 18.21 points is **irreducible physics** — signals genuinely collide — and row 4's prize is
  much smaller than it looks.
- If jt9 is **flat** across density while we lose 18 points, then **the entire penalty is ours to
  win**, and row 4's prize is far larger than the 07-27 pricing credited.

**These imply opposite decisions and nothing measured so far distinguishes them.**

**Why it cannot be done from the corpus.** Density is *defined* as jt9's own decode count per
cycle, so jt9's recall cannot be measured against itself. A third reference would be needed, and
WSJT-X is the same algorithm family — not independent.

**Method — synthetic, ground-truth, multi-signal.** Extend `b2_synthetic_calibration.py` from
single planted signals to **cycles containing N planted signals**, N ∈ {2, 8, 20, 40, 55} (spanning
20m's observed Q1→Q4 range and beyond it), at controlled SNRs, frequencies drawn to match the
corpus's observed spacing distribution. Decode each buffer **twice** — once through our decoder,
once through `jt9 -8 -d 1` (the same minimum-effort arm B.1 used, so the number stays comparable).
Both measured against known truth.

**Deliverable:** P(decode) vs N, for both decoders, with Wilson intervals. **The gap's slope in N
is the answer**, and it is reported as a curve, never a single number.

**Reading rule, fixed now:** report both slopes with intervals, and report the **ratio of our
density-penalty slope to jt9's**. No summary figure is quoted without the curve beside it.

**Self-check (stop rule):** at N = 2 the arm must reproduce B.2's own single-signal P(decode)-vs-SNR
behaviour, and the jt9 arm must reproduce B.1's depth-1 behaviour on a shared buffer. If either
fails, **report the self-check failure, not the result.**

**Cost:** ~1–1.5 QA sessions. **Always run**, whatever S.1/S.2 conclude — it is the only arm that
produces a cost signal, and the menu decision needs one.

**⚠️ This arm's biggest weakness, stated before the numbers.** The CPFSK-vs-GFSK caveat (B.2 §5,
still unresolved) is **more exposed here than anywhere previously**, because how signals interact —
spectral skirts, intermodulation, adjacent-channel leakage — depends on getting the modulation
shape right in a way that single isolated signals never tested. A synthetic multi-signal collision
model that is wrong about skirt shape will mis-price H2 and H3 specifically.

**Mitigation, and it is partial:** cross-check S.3's predicted density slope against the corpus's
*measured* slope for our own decoder (which S.1 already produces). If synthetic and corpus slopes
disagree materially for **our** decoder — where we can check both — then the synthetic channel is
not modelling interaction correctly and **jt9's synthetic slope should not be trusted either.**
That check is free, it is a genuine falsification test of the instrument, and it is mandatory
before S.3's jt9 comparison is quoted.

## 7. Sequencing and stop rules

1. **S.1 first, alone, report before anything else starts.** Free, and it splits an
   order-of-magnitude cost decision. Nothing downstream should be built on Measurement D's
   §6.2 "capacity ceiling" reading until S.1 reports.
2. **If S.1 fires row 1 (frequency-local), stop Track B and escalate.** Row 4 is then a subtraction
   architecture; that is a menu-level fact, not something to keep measuring. S.2 is not run.
3. **If S.1 fires row 2 or 3, S.2a runs.** If S.2a's boundary scores are flat, **H1 is dead — stop,
   do not run S.2b.** A native rebuild to confirm a negative is the wrong purchase.
4. **S.2b only on the Captain's authorisation, priced** (native rebuild cost class).
5. **Track A (R.1 → R.2 → R.3) runs in parallel or after**, on its own 07-27 stop rules
   (R.2 hitting its first row stops before R.3).
6. **S.3 last, always run**, whatever anything else concluded.

**The throughout stop rule from 07-27 stands unchanged:** if any arm's self-check fails, **report
the self-check failure rather than the arm's result.** Four self-corrections of this class have
now been caught mid-flight in this thread; today's task-4 sequence added three more, all of them
comparisons that were subtly not what they appeared to be.

**One new standing prerequisite.** Any corpus used by any arm must first pass the **drift screen**
established by Measurement C and task 4. The clock-drift defect silently destroys parity, it was
present in corpora already in use, and it is not fixed on `main` yet. A drift-contaminated corpus
will manufacture a density penalty that is not there — dense cycles cluster in time, and so does
drift. **This screen is not optional and it is cheap.**

## 8. What this means for the menu ⟨the Captain's decision⟩

**The honest position: Measurement D has made row 4's price *more uncertain*, not less — and S.1
resolves that uncertainty for free.**

| S.1 outcome | mechanism | row 4's shape | menu effect |
|---|---|---|---|
| cycle-global | capacity / budget | Has a **cheap, shippable component** — a constant, a harness that exists, incremental delivery | **Row 4 up.** Partial commitment becomes real |
| frequency-local | collision | Needs **subtraction-pass architecture** — a large share of what makes jt9 good | **Row 5 up.** Row 4 approaches a rewrite |
| both | two sub-mechanisms | Split commitment; ratio prices it | Depends on the ratio |

**Nothing should be committed before S.1 reports.** It is half a session, it needs no data we do
not have, and it is the difference between a constant and an architecture.

**What has genuinely improved since 07-27:** row 4's target was *"one lump — sync detection,
candidate scoring, symbol demodulation folded together."* It is now **two named mechanisms of
comparable size, one with a free experiment pending that splits it into four falsifiable
hypotheses.** That is a materially better position to decide from, even though the decision itself
is not yet due.

## 9. What this does not authorise or settle

- **No `src/` or native change** (HK-011). S.1 and S.2a use already-shipped, default-off
  diagnostic exports. S.2b needs rebuilds and is explicitly gated on the Captain, priced.
- **No push, no merge** (HK-014/HK-010) — this is committed locally and stops there. I do not ask.
- **No `pre_merge_check.py`** (HK-006) — the Captain's trigger only.
- **No new corpus gathering.** Every arm runs on frozen artefacts or synthetic audio. And per
  HK-020/`0910` §4.5, no long-session corpus should be gathered at all until the drift fix merges
  or sessions are capped below ~12 h.
- **Row 5 untouched.** No position taken on GPLv3; S.3 exists to give it something honest to be
  compared against.
- **Rows 2 and 3 stay sequenced behind row 4**, unchanged. Note that Measurement D has arguably
  moved row 2's subject matter *into* row 4 — competition is now row 4's problem, not a separate
  row's. **I am flagging that rather than acting on it**; renumbering the menu mid-decision would
  be its own kind of damage.
- **The density law stays struck** as a predictive instrument (`1212`). §2.1's dose-response does
  not restore it.
- **Per HK-015 this is a design, not a task.** `dev-tasks/` and `tasks.md` are QA's to author.
- **NFR-021:** aggregates only. S.1/S.2a touch real callsigns only inside git-ignored `artefacts/`
  and must print counts only. S.3's synthetic messages are Q-prefix by construction.

## 10. Honest caveats

- **§2's eight-point table is unmatched count ratios and cross-band rows are confounded.** Stated
  at the table and repeated here because it is the single most misusable object in this document.
  It guided arm design; it is not a result.
- **S.1 does not control neighbour strength**, only the target's own SNR. It separates local from
  global cleanly; it does not separate H2 from H3 decisively (§4, stated limitation).
- **H1–H4 are not exhaustive.** They are the four I can name from the evidence on record. S.1's
  rule row 4 exists precisely because the true mechanism may be none of them, and that outcome
  escalates rather than being rationalised into the nearest listed candidate.
- **CPFSK vs GFSK carries forward into S.3 and is more exposed there than in any prior arm** (§6).
  The corpus-slope cross-check is a real mitigation but a partial one.
- **I authored the reading that S.1 rule row 4 could overturn** — Measurement D's §6.2 capacity
  reading is mine, drawn out in §2 above. Rules are fixed here before numbers exist and QA runs it,
  not me. Those are mitigations, not neutrality, and the Captain should weight them as such. This
  caveat has more force than usual today: §0's correction is a case of exactly this failing.
- **None of this measures how hard our front end would be to *improve*,** which is ultimately what
  row 4 costs. S.3's curve is the closest available proxy and it is a proxy.

## 11. A note on the superseded design's location

`2026-07-27-1730-architect-row4-scoping-design.md` exists **only on branch
`d001-c4-min-score-sweep`** and is not on `main`. §5 carries three of its arms forward as live
work, so a document on `main` now depends on one that is not. **That is QA's to resolve** — whether
by cherry-picking it onto `main`, by branch disposition, or otherwise. I am flagging it, not
directing it; branch disposition for `d001-c4-min-score-sweep` was already open and blocking on
the Captain before today.

## 12. Cross-references

- `2026-07-31-1245-qa-measurement-d-result-competition-confirmed.md` — the result this re-scopes
  from; §6.2 is where §2's two-mechanism reading comes from.
- `2026-07-31-1344-architect-correction-…-withheld-figures-do-not-exist.md` — §0's correction.
- `2026-07-27-1730-architect-row4-scoping-design.md` ⟨branch `d001-c4-min-score-sweep`⟩ — the
  design this supersedes; §3's tolerance defect and R.1/R.2/R.3 carry forward intact.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — S.2a's baseline (+0.93% at ~19/cycle, cap
  saturated at 140) and S.2b's two pitfalls.
- `2026-07-31-1222-…-outstanding-work-after-task4.md` §7 — the citation blacklist, including the
  `K_MAX_CANDIDATES` "untested, not refuted" entry S.2 acts on.
- `2026-07-31-1212-…-task4-closes-inconclusive-…md` — why the density law is not predictive, and
  why §2.1 refuses to fit a curve.
- `2026-07-31-1232-qa-measurement-a-correction-escalated.md` — mechanism 1's cross-band statement.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — §7's drift-screen prerequisite.
- `qa/endurance/anova_common.py` — `parse_all_txt`, which already carries `freq_hz` per decode;
  S.1 needs no new parsing.
- `qa/cycleframer-alignment-replay/b2_synthetic_calibration.py` — the harness S.3 extends.

---

*Per HK-015 this is Architect → QA material: the arms above are a design for QA to scope and author
as `dev-tasks/`, not tasks issued by me. Per HK-014 committed locally, no push, no merge, and I do
not ask for one. Per HK-011 nothing here touches `src/` or native code; S.2b's rebuilds are gated
on the Captain and would be a Developer session's work. Per HK-017 filename and byline carry
`date -u` UTC. Per HK-018 §2's table and §4's tooling claims were read from the committed
artefacts and from `anova_common.py`, not assumed. The row 1 vs row 4 vs row 5 decision remains the
Captain's, on the Captain's clock.*
