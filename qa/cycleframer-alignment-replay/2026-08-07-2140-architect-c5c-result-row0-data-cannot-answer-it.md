# C.5c result — ROW 0. The retained data cannot answer the question, and my ROW 1 prediction is untested.

**Author:** Architect, 2026-08-07 (21:40 UTC, `date -u`, per HK-017). Repo `main` at `de0c0da`.
**For:** QA and the Captain.
**Reports against:** `2026-08-07-2117-architect-to-qa-rc-programme-closed-c5-correction-threshold.md`
§4.3 and §5.3 (the C.5c spec and its `c5c_row` gate), which I wrote ninety minutes ago.
**Scripts:** `qa/cycleframer-alignment-replay/2026-08-07-c5c-rank-conversion/`
(`c5c_rank_conversion.py`, `c5c_rank_conversion_result.json`). Read-only re-analysis of RC1's
retained `_work/`; no `src/` change, no capture, no replay, no NFR-021 exposure.

---

## 1. Verdict

**`c5c_row` fires ROW 0 — instrument failure. No verdict on RC3.**

`c_bottom = 0.476%` under the policy that best models the decoder, and `36.5%` under the opposing
one. The D1 decile *inverts* between them — 83.7% vs 0.36%. The tie-break rule, not the data, was
setting the answer, and the divergence guard caught it.

**I ran this because HK-004 says check whether you can just do a follow-up rather than recommend
it. The answer to "can this be done from data on disk" turns out to be no, and that is worth
knowing for a cost of one script.**

## 2. What the numbers are

60 cycles pooled over RC1's 3 runs, 8,400 pass-0 candidates, 1,382 of our decodes, 99.2% attributed
to at least one candidate. The candidate list is confirmed sorted descending by score — **0 sort
violations in 60 cycles**, so RC1's getter preserved `ftx_find_candidates`'s ordering.

| decile | ranks | n | highest-ranked policy | lowest-ranked policy |
|---|---|---:|---:|---:|
| D1 | 0–13 | 840 | **83.690%** | 0.357% |
| D2 | 14–27 | 840 | 39.643% | 2.857% |
| D5 | 56–69 | 840 | 4.762% | 11.667% |
| D9 | 112–125 | 840 | 0.833% | 27.619% |
| D10 | 126–139 | 840 | **0.476%** | 36.548% |

Both curves are monotone and they run in opposite directions. That is the signature of an
unidentifiable attribution, not of a weak effect.

## 3. Why neither policy can be trusted — and why the better one still fails

**The ambiguity is structural.** Each of our decodes has a **median of 4** candidates within the
±6.25 Hz / ±0.5 s tolerance (mean 3.83, p90 6, max 9). That is inherent: `ftx_find_candidates`
searches a time/frequency grid at `time_osr=2, freq_osr=2`, so one real signal lights up several
neighbouring grid points. Tightening the tolerance does not fix it — the cluster is the signal.

**I first chose the wrong primary policy.** My draft credited each decode to the *lowest*-ranked
matching candidate, reasoning it was conservative against my own stated prediction. It is not
conservative, it is wrong: `ft8_shim.c:1354` iterates candidates in returned (descending-score)
order, and the cross-pass dedup at `:1387` is **by message hash** — so a later candidate producing
an already-decoded message is dropped before it can be recorded. A lower-ranked candidate is
unreachable for a message a higher-ranked one already claimed. I verified both lines tonight rather
than assuming them.

**But the corrected policy fails too, for RC1's own reason.** "The first matching candidate wins"
holds *only if that candidate actually decodes*. RC1's entire result is that ~90% of candidates
fail LDPC/OSD. So within a cluster of four candidates around one signal, ranks 3, 40 and 90 may all
fail and rank 130 succeed — and the highest-ranked policy would credit rank 3 for a decode it never
produced. **Under exactly the failure regime RC1 measured, the model breaks.** The 0.476% is
therefore a plausible figure resting on an assumption RC1 has already falsified in general.

**The root cause, stated plainly:** `candidate_lists.json` records which candidates *existed*, not
which one *decoded*. RC1's getter runs before any LDPC attempt — correctly, that was its job.
Nothing in the artefact links a decode back to its originating candidate, and no matching rule over
frequency and timing can manufacture that link.

## 4. Consequences

- **RC3 stays deferred.** Its cap-interaction objection is neither retired nor confirmed. My §4.3
  claim that this measurement "is already paid for" was wrong — it is cheap, but it is not
  *sufficient*, which is a different thing and I did not check it before writing.
- **My prediction is untested, not confirmed.** §4.3 recorded, in advance and in writing, that I
  expected ROW 1. `c_bottom = 0.476%` is superficially consistent with that, and I want it on the
  record that **it must not be cited as support**: it is the output of a model RC1 falsified. A
  prediction that survives only under a broken instrument has not survived.
- **Answering C.5c properly needs a `src/` change** — a per-decode originating-candidate index
  alongside the existing getters. That is a Developer session, small but not free, and I am not
  scoping it here. It should be weighed against C.5a/C.5b, which are still genuinely free and still
  unrun, and which bear on the much larger 87.9% of the gap rather than on RC3's 3.1%.
- **My recommendation on priority is unchanged and now firmer:** C.5a and C.5b first. RC3 is worth
  ~3.1%; it does not deserve a `src/` change ahead of the measurement that tells us whether we are
  facing a bug or a rebuild.

## 5. What went right, and the one rule that earned its keep

The ROW 0 row was added to every gate this morning, hours before this ran, because S.1r returned
ROW 4 from an empty stratum and ROW 4 read like a null when it was an instrument failure. Here the
instrument failed a second, different way — not an unpopulated stratum but an unidentifiable
metric — and the explicit ROW 0 meant the failure surfaced as *"no verdict"* rather than as
`c_bottom = 36.5%`, ROW 2, "displacement is real."

Had I kept my original primary policy and shipped it without the opposing bound, this note would
have reported ROW 2 and blocked RC3 on an artefact of a tie-break. The cross-check that saved it was
built in only because I wanted a bound that ran *against* my own prediction. **That habit is the
thing worth keeping**, more than either number in the table above.

**A third gate-drafting failure today, same family as the other two.** S.1r's boundary could not
populate; D-009's strict `>` hid an option; C.5c's metric was not identifiable. Each time the gate's
*structure*, not its threshold, was the defect — and each time I would have caught it by working one
example through by hand before writing the rule. The HK-021 sibling this earns:

> **A gate is not mechanical until you have verified its metric is identifiable from the data it
> will be computed on.** "Can I compute this number?" and "does this number mean what I think?" are
> different questions, and pre-registration only protects the second one.

---

*Per HK-015 this is the Architect reporting a result QA did not ask for and should not be assumed to
own; the C.5 dev-task remains QA's to author. Per HK-014 committed locally, no push, no merge. Per
HK-011 nothing here touches `src/`. Per NFR-021 the analysis reads only frequency, timing and score
columns — message text is never loaded, and no callsign appears in any output.*
