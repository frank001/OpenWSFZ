# ARCHITECT RULING — Measurement D's 20m corpus is two sessions, not one
# The stated premise is false. The finding survives, and comes out stronger. S.1 must not run pooled.

**Author:** Architect, 2026-07-31 (15:30 UTC, `date -u`, per HK-017). Repo at `298cefa`
(`origin/main`, PR #118 merged).
**For:** QA — **read before running arm S.1**, which is queued against the affected corpus.
**Raised by:** the Captain, from memory of the operating sequence during the 07-29/30 run.
**Affects:** `2026-07-31-1245-qa-measurement-d-result-competition-confirmed.md`,
`2026-07-31-1355-architect-row4-decomposition-rev2-competition-scoped.md` §2,
`2026-07-31-1356-…-work-order-after-measurement-d.md` §2.

---

## 0. Verdict

| # | ruling |
|---|---|
| **R1** | Measurement D's *"holding band, antenna, receiver, and session constant"* is **FALSE**. The 20m corpus is **two segments 18.5 h apart**, and the sparse/dense split is **substantially a segment split** |
| **R2** | **The density effect is UPHELD, not withdrawn.** It reproduces independently within each segment, and the two segments agree where their density ranges overlap |
| **R3** | The headline **18.21-point matched figure is SUSPENDED** — not refuted. It was computed on a composition that does not match its own stated design. Restore it per segment |
| **R4** | **S.1 runs per segment, not pooled.** Segment 1 is primary |
| **R5** | **New mandatory self-check** for every stratified comparison in this programme: report the strata's temporal composition |

## 1. The finding

The 20m data was gathered in two disjoint sittings — 20m at session start, then 80m overnight,
then 10m in daylight, then back to 20m the following evening. All of it landed in one folder, and
Measurement D read it as one session.

| segment | window (UTC) | duration | cycles | mean ref decodes/cycle |
|---|---|---:|---:|---:|
| **1** | 07-29 18:31:30 → 21:14:30 | 2.72 h | 618 | 31.90 |
| **2** | 07-30 15:42:15 → 18:40:00 | 2.96 h | 712 | 41.87 |

**Gap: 18 h 28 m.** Different days, different propagation, and the capture process at very
different uptimes (~0–3 h vs ~21–24 h).

### 1.1 Only 20m is affected — and it is the decisive band

Segmenting all three bands' `cycle-archive.csv` on gaps > 5 min:

| band | segments | span | role in Measurement D |
|---|---:|---|---|
| 10m | **1** | 6.20 h contiguous, 1490 cycles | replication, non-decisive |
| **20m** | **2** | split as above | **DECISIVE** |
| 80m | **1** | 12.15 h contiguous, 2917 cycles | replication, non-decisive |

The two bands Measurement D treated as free replication are clean; the one band the reading was
taken on is the split one. That is unlucky rather than meaningful, but it means the 10m/80m arms
need no revision.

## 2. What is confounded

Measurement D's own published cutoffs (sparse ≤ 30, dense ≥ 43 reference decodes/cycle), against
segment:

| stratum | seg 1 | seg 2 | composition |
|---|---:|---:|---|
| **SPARSE** | 335 | 37 | **90.1% segment 1** |
| mid | 152 | 427 | 73.7% segment 2 |
| **DENSE** | 131 | 248 | **65.4% segment 2** |

**The decisive comparison is substantially one evening against a different evening.** Density and
session are entangled, which is precisely the confound Measurement D was designed to eliminate —
its purpose was to break the band/density confound that defeated Measurement A, and it
reintroduced a session/density confound in doing so.

**None of the four self-checks could have caught this.** The matching gate, density contrast,
duplicate-key and common-support checks all passed and are all blind to temporal structure. This
is a gap in the check battery, **not a QA execution error**, and R5 closes it.

## 3. What survives — and it is more than before

Re-running the density dose-response **within each segment separately**:

| | Q1 yield | Q2 | Q3 | Q4 yield | Q1→Q4 drop |
|---|---:|---:|---:|---:|---:|
| **Segment 1 alone** (618 cycles) | 66.3% | 59.3% | 54.1% | 46.5% | **19.8 pts** |
| **Segment 2 alone** (712 cycles) | 55.8% | 53.8% | 52.9% | 42.2% | **13.5 pts** |
| Pooled, as D ran it (1330) | 61.9% | 55.2% | 52.8% | 44.2% | 17.7 pts |

**Monotone in both segments independently.** Segment 1's effect is *larger* than the pooled
figure, so the confound inflated nothing — if anything it diluted.

### 3.1 The segments agree where they overlap

Segment 1 spans 17.8–49.1 ref decodes/cycle; segment 2 spans 32.9–54.3. In the overlap:

| density | segment 1 yield | segment 2 yield | difference |
|---:|---:|---:|---:|
| ~33 | 55.0% (interp.) | 55.8% | 0.8 pt |
| ~42 | 50.3% (interp.) | 52.9% | 2.6 pt |
| ~49 | 46.5% | 46.8% (interp.) | **0.3 pt** |

**Two independent evenings, 18.5 h apart, landing on the same curve.** That is a stronger claim
than the single-session version ever made — an accidental replication in place of an assumed
constancy.

### 3.2 The limit of this evidence — stated plainly

**§3's figures are unmatched yield ratios** (our decode count ÷ reference decode count per cycle),
**not the matched-SNR recall Measurement D actually reads.** They establish that the effect is not
a segment artefact. They **do not** restore the 18.21-point figure, which is a different quantity
measured a different way. That is R3, and it is why the number is suspended rather than upheld.

## 4. Rulings in detail

**R1 — correct the record.** Measurement D's §0 headline and its §2/§3 framing claim session
constancy that does not hold. **QA's document to amend or errata** — I am not editing QA's
write-up. The correction should state the two-segment structure and point here.

**R2 — the effect is upheld.** Competition remains a named, measured mechanism. Nothing in the
rev2 decomposition's direction changes. **Do not withdraw it, and do not treat this ruling as
casting doubt on the mechanism** — it casts doubt on one number's provenance and on a stated
premise, both of which are repairable.

**R3 — 18.21 is suspended pending a per-segment re-run.** Re-run Measurement D's matched-SNR
analysis on segment 1 alone, and on segment 2 alone, quoting both. Segment 1 is the better test
(335 sparse / 131 dense); segment 2's sparse stratum is thin at 37 and may not clear common
support — **if it does not, say so rather than pooling to rescue it.**

**R4 — S.1 runs per segment.** Segment 1 primary. S.1's whole purpose is separating two
mechanisms; a segment artefact entering there would land directly in the engineering decision.
S.1's reading rule (rev2 §4) is otherwise unchanged and still pre-registered — **the rule is not
being edited after seeing data, only the corpus partition it is applied to.** That distinction
matters and should be stated in the write-up.

**R5 — new mandatory self-check, effective now.** Every stratified comparison in this programme
reports, as a numbered self-check alongside the existing four:

> **Self-check 5 — temporal composition.** For each stratum, report its distribution across
> contiguous capture segments (gap > 5 min in `cycle-archive.csv`). If any stratum is > 65% from a
> segment that contributes < 35% of another stratum, the comparison is **confounded with session**
> and must be re-run per segment.

Applied retroactively to Measurement D, this fires: 90.1% vs 65.4%. **It is cheap, mechanical, and
would have caught this before the result was written.**

## 5. Impact on the rev2 decomposition

**rev2 §2's two-mechanism reading was derived from Measurement D §6.2's pooled quartile table and
therefore inherits the confound.** Re-derived on segment 1 alone:

| | pooled (as published) | **segment 1 alone** |
|---|---|---|
| Baseline deficit (sparsest quartile) | ~39% lost | **~34% lost** (66.3% yield) |
| Density penalty (Q1→Q4) | ~17 pts | **~19.8 pts** |

**Both mechanisms survive, both remain comparable in size, and the central architectural claim
stands**: an engineering commitment fixing only one leaves most of the gap in place. The
magnitudes shift slightly and the density penalty gets marginally *larger*.

**rev2 §2.1 is strengthened, not weakened.** It argued that a dose-response inside one band is
better evidence than the cross-corpus density law. It is now **two** dose-responses in one band, on
two days, agreeing where they overlap. §2.1's refusal to fit a curve to it stands — two
four-point series is still not a law.

**rev2 §7's drift-screen prerequisite needs widening.** It required corpora to pass a drift screen.
It should have required them to be **contiguous**. Drift was the failure mode I anticipated;
band-switching gaps were not, and they are the more mundane and more likely of the two. R5
generalises the prerequisite properly.

## 6. Not affected

- **Measurement A, B, C** — different corpora and different designs; none stratifies within a
  single band's session.
- **Task 4 / 489135a** — closed inconclusive on unrelated grounds.
- **The drift fix** (PR #118, merged) — unrelated, and its own oracle tests are unaffected.
- **The density law's struck status** — unchanged. Nothing here restores it.
- **Measurement D's 10m/80m arms** — both corpora contiguous (§1.1).
- **The 12 h operating guidance** — 80m ran 12.15 h contiguous on the Voicemeeter chain, which does
  not drift. No issue.

## 7. Citation blacklist — additions

Extends `1222` §7.

| do not cite | instead |
|---|---|
| *"Measurement D held band, antenna, receiver **and session** constant"* | **False.** Two segments 18.5 h apart; sparse stratum 90% segment 1, dense 65% segment 2 |
| *"18.21 points at matched SNR"* | **Suspended** pending per-segment re-run (R3). Not refuted |
| Measurement D §6.2's per-quartile table | **Pooled across two sessions.** Do not quote per-quartile figures without segment attribution |
| rev2 §2's *"~39% baseline deficit / ~17 pt density penalty"* ⟨mine⟩ | Superseded by §5's segment-1 figures: **~34% / ~19.8 pts** |

## 8. How this was caught, and what it costs

**The Captain caught it from memory of the operating sequence** — not from any artefact, check, or
review. Verifying it took four minutes against `cycle-archive.csv`, which has carried the
timestamps all along.

This is the **fifth** comparison in this programme to turn out subtly not what it appeared, and the
first that a mechanical check could have caught in advance rather than only in hindsight — which
is why R5 exists and why it is written as a rule rather than a recommendation.

**It also raises the value of a fresh contiguous 20m session.** This corpus can now never fully
shed the doubt; a single uninterrupted run would settle it outright.

## 9. Boundaries

- **No `src/`** (HK-011). Nothing here touches code.
- **No push, no merge** by me (HK-014/HK-010) — this is committed locally and stops there.
- **No `pre_merge_check.py`** (HK-006).
- **NFR-021:** aggregates only; all figures here are counts and ratios.
- **Per HK-015** this is Architect → QA. The Measurement D correction (R1) is **QA's document to
  amend**, and `dev-tasks/` remain QA's to author.
- **No new arm.** R3 and R4 re-partition already-authorised work; they do not open anything.

## 10. Cross-references

- `2026-07-31-1245-qa-measurement-d-result-competition-confirmed.md` — the result R1 corrects and
  R2 upholds.
- `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` §2, §2.1, §7 — re-derived at §5.
- `2026-07-31-1356-…-work-order-after-measurement-d.md` §2 — S.1's task, amended by R4.
- `artefacts/20260729_live_run_1831-8081/owsfz/{10m,20m,80m}/cycle-archive.csv` — the segment
  evidence, git-ignored but on disk.
- `qa/cycleframer-alignment-replay/measurement_d_within_band_density.py` — the script R3's
  re-run extends; needs only a segment filter.

---

*Per HK-015 this is Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge. Per
HK-011 nothing touches `src/`. Per HK-017 filename and byline carry `date -u` UTC. Per HK-018 every
figure here was computed from the corpus rather than reasoned about — including §3, which was run
specifically because the confound might have destroyed the finding and the honest thing was to
measure that rather than argue it either way.*
