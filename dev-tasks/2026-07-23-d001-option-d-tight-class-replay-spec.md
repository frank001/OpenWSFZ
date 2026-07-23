# D-001 — Option D, Step 1: Matched Tight-Class Replay (Class-Independence Test)

**Date:** 2026-07-23
**Author:** QA (self-directed)
**Audience:** Architect, Captain
**Decision context:** `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` §3.1 — the Captain has
selected **Option D** (investigate the live-path/gain-staging lead before committing to H7),
specifically including its §3.1 extension: *"replay a matched sample of Tight-class misses
alongside the Isolated ones, to measure directly whether the live-path effect is
class-independent."*
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Status:** Proposed, approved to execute (Captain selected Option D, 2026-07-23).

---

## 0. Executive summary

PR #103's isolated-miss replay pilot found that 13.0% (`< −15 dB`) / 44.4% (`−15..−10 dB`) of
sampled **Isolated**-class misses — misses Option B already ruled out as H7's target — decode
successfully when the identical historical audio is replayed in isolation, but did not decode
live. That is a large, first-order effect, and nothing about its likely mechanisms (AGC
warm-up state, cycle-boundary/sample-clock alignment, adjacent-cycle history) is specific to
signals that happen to lack a same-slot neighbour within 50 Hz. The go/no-go brief's §3.1
therefore flags a real risk: if the same live-path handicap costs decodes in the **Tight**
class too, some fraction of the 9,956 Tight-class misses underpinning the ≤18.4pp "H7 ceiling"
are not H7's to recover at all — they're the live-path fix's, which is far cheaper.

This spec answers exactly that question, and only that question, before any root-cause
mechanism work is scoped: **is the decoded-on-replay rate for Tight-class misses similar to
Isolated's, or is it near zero?** It reuses PR #103's infrastructure end to end — same session
(07-07, the only one with retained WAV audio), same two SNR bands, same replay harness, same
Gate R reproduction check — changing only which population is sampled from. No new capture, no
product or decoder code change.

**Effort:** a few hours, matching PR #103's own (~45 minutes of live session time last time).

---

## 1. The precise question this answers

> For Tight-class low-SNR misses (WSJT-X decoded, OpenWSFZ did not, a same-slot neighbour
> **within 15 Hz** exists) — the class the ≤18.4pp H7 ceiling is built on — what fraction
> decode successfully when the identical historical audio is replayed in isolation? Is that
> rate consistent with Isolated's (13.0% / 44.4% per band), or materially lower?

Two possible outcomes, and what each means for the H7 decision:

- **Tight-class decoded-on-replay rate is comparable to Isolated's (roughly the same order of
  magnitude, same direction across bands).** The live-path effect looks class-independent. The
  ≤18.4pp ceiling is an overstatement by roughly that same fraction — a portion of what's been
  attributed to "H7's problem" is actually the live-path fix's. This **lowers the price of
  Option A** and **raises the value of fixing the live-path issue first**, exactly as §3.1
  warned. It does not, by itself, tell us whether what's left after subtracting the live-path
  effect still clears any H7 threshold — that would need a follow-up.
- **Tight-class decoded-on-replay rate is near zero (or clearly, statistically distinguishable
  from Isolated's).** The live-path effect is Isolated-class-specific — plausibly because a
  genuinely co-channel signal's failure mode is dominated by the interferer itself, not by
  AGC/timing margin, so isolating it from live capture noise doesn't help the way it helps a
  merely-weak signal. The ≤18.4pp ceiling stands uncorrected, and Option D reverts to being the
  additive, orthogonal lead the original PR #103 report framed it as — worth doing, but not a
  precondition for pricing Option A.

Either answer is a usable finding; this is not a pass that can come back inconclusive in the
way the CG-vs-LDPC split did.

---

## 2. Inputs (Gate 0)

Identical to PR #103's spec §2, since this reuses the same session and infrastructure:

| Input | Status |
|---|---|
| Tight-class miss list (ts, freq_hz, wsjt_snr, band) for 07-07 | **Must be generated** — `classify_cochannel.py` computes Tight counts but, like it did for Isolated, discards per-miss identity. A small extension is needed (§3.1). |
| Per-slot raw audio for 07-07 | **Confirmed present** (re-verified by PR #103: 100% WAV coverage for the Isolated population; no reason to expect worse coverage for Tight, same session, same date range). |
| Replay harness (throwaway daemon instance, VB-CABLE loopback, boundary-aligned playback, Gate R reproduction check) | **Confirmed present and reusable as-is** — `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py`. Built for exactly this replay shape; the only population-specific logic is upstream of it (sample materialisation). |
| Candidate-count/LLR diagnostic | **Not needed for this pass.** Unlike PR #103, this pass does not attempt a CG-vs-LDPC split (§3.4) — the question here is purely the Gate R reproduction rate. Debug logging may stay on (harness default) but its output is not analysed. |

**Gate 0 verdict: PASS**, on the same basis PR #103 passed it — nothing new needs capturing.

---

## 3. Method

### 3.1 Materialise the Tight-class sample (local only, NFR-021)

Copy `materialise_isolated_sample.py` to a new script (`materialise_tight_sample.py`), changing
only the classification filter: where the original keeps misses where
`classify_delta(best_delta, PRIMARY_TIGHT_CUTOFF) == "isolated"`, this keeps misses where the
result is `"tight"` (i.e. `best_delta is not None and best_delta <= PRIMARY_TIGHT_CUTOFF`, the
same 15 Hz primary cutoff Option B and PR #103 both use — **do not** introduce a different
cutoff here; comparability with Isolated's figures depends on using the identical definition).
Everything else — same session (07-07), same two bands, same `has_wav` check, same NFR-021
handling (local-only full population, committed msg-stripped sample) — carries over unchanged.

Use a distinct scenario id for seeding (`D001-TIGHT` in place of `D001-ISO`) so the draw is
independent of, not a re-derivation of, the Isolated sample's seed — these are two different
populations being sampled, not a shared one.

**Match PR #103's sampling shape exactly:** stratified by the same two bands, target 20
reproduced per stratum, over-draw 60/stratum. This is what makes the two resulting rates
directly comparable — same session, same bands, same n, same stopping rule (and therefore the
same outcome-dependent-stopping bias in *each individual pass*, which cancels out in the
comparison rather than needing correction, since it applies symmetrically to both populations
if class-independence holds. It does **not** cancel out in either pass's own within-class
pooled figure — see §3.3.)

### 3.2 Local replay session

Reuse `run_isolated_replay.py` unmodified except for its input/output file names (point it at
`tight_sample_candidates.json` instead of `isolated_sample_candidates.json`, write results to
`tight_replay_results.json`). Same throwaway daemon instance, same VB-CABLE loopback, same
boundary-aligned playback with pre-roll, same Gate R check (does the target message reappear
among OpenWSFZ's decodes on replay?).

**One difference worth flagging, not working around:** a Tight-class WAV's passband contains,
by construction, a real neighbour within 15 Hz of the target — that's what makes it Tight. This
is not a complication for the replay method (the WAV is played as-is, the same way an Isolated
slot's busy-but-non-adjacent passband was played as-is in PR #103); it is simply a reminder that
"decoded on replay" for a Tight-class miss means the target decoded **despite** its close
neighbour still being present in the replayed audio — the co-channel interference itself is not
removed by this method, only whatever live-only handicap (AGC/timing/adjacent-cycle state) is
under test.

### 3.3 Report Gate R only — no Tier-1 CG/LDPC split

Report, per band and pooled:

- Tried / Reproduced (Gate R fail) / Decoded-on-replay (Gate R pass), with 95% Wilson CI per
  band.
- **Population-weighted pooled figure, computed correctly the first time.** PR #103 initially
  reported a naively pooled 32.2% and had to correct it post-merge to a population-weighted
  ≈23.4% once it was noticed that outcome-dependent stopping (drawing until 20 *reproduce* per
  stratum) inverts the sample's band mix relative to the population's. Apply that lesson here
  from the start: weight each band's Decoded-on-replay rate by that band's **share of the
  Tight-class population** (not the sample's tried-count), using the same population totals
  this pass's own `materialise_tight_sample.py` run reports. Show the naive pooled figure too,
  labelled explicitly as a sample rate, for transparency — but lead with the weighted one.
- **Direct comparison to Isolated's published rates**, per band: a two-proportion test (Fisher's
  exact, appropriate for these sample sizes) between this pass's Tight-class rate and PR #103's
  already-published Isolated-class rate, same band, same session. Report the test statistic/CI
  for the difference, not just a bare "similar" or "different" judgement.

Do **not** attempt the CG-vs-LDPC Tier-1 split from PR #103's spec §3.3 — that instrumentation
already proved unable to resolve anything on this corpus (100% Ambiguous, saturating the
340-candidate buffer) and re-running it here would spend effort on a question already answered
in the negative for this session's band conditions.

---

## 4. Rigour controls

1. **Identical cutoff definition as Option B/PR #103** (15 Hz primary) — no redefinition that
   would make the Tight/Isolated comparison apples-to-oranges.
2. **Stratified, seeded, over-drawn sampling** — no manual selection, same discipline as PR #103.
3. **Population-weighting applied from the start**, not retrofitted — see §3.3. This is the one
   concrete process change from PR #103, made because that pass's own post-hoc correction
   already identified the failure mode; repeating it here after already having named it would
   not be defensible.
4. **This is a pilot (n≈40 reproduced), stated as such.** Same CI-width caveate as PR #103 — a
   `< −15 dB` stratum around n=20 carries wide confidence intervals (PR #103's own equivalent
   spanned [4.5%, 32.1%]). A clean "materially different" or "not distinguishable" read may not
   be achievable at this n; if the comparison lands ambiguous (CIs heavily overlapping, wide
   enough to be uninformative), report that plainly as a finding — it would mean a larger
   confirmatory sample is needed before the ceiling correction in §1 can be sized, not that the
   pilot failed.
5. **Single session (07-07), same limitation as PR #103**, for the same reason (only session
   with retained WAV audio). State this in the report; it constrains generalisation the same way
   it did last time.
6. **No mechanism investigation in this pass.** *Why* a live-path effect exists (AGC state,
   boundary timing, etc.) is explicitly out of scope here — this pass only measures whether the
   *symptom* (decoded-on-replay rate) is class-independent. Root-cause mechanism work is a
   separate, not-yet-scoped follow-up, appropriate only once class-independence itself is
   established (§6).

---

## 5. Scope guardrails — what this is NOT

- **Not** a new on-air capture — reuses the same retained 07-07 WAV audio as PR #103.
- **Not** a product or decoder code change.
- **Not** a re-opening of Option B's F=29.6% verdict, the histogram addendum, or the runtime-
  parameter sweep — this is additive, answering a question none of the three prior passes asked.
- **Not** a root-cause diagnosis of *why* the live-path effect exists — purely a class-
  independence measurement (§1).
- **Not** a decision to commission or defer H7 — this feeds the ceiling correction the Captain
  will weigh, it does not make the A-vs-C call.
- **Not** a precision measurement — pilot-sized, same as PR #103, stated as such throughout.

---

## 6. Deliverables

1. `qa/rr-study/results/<date>-<sha>-d001-tight-class-replay/report.md` (QA authors Sections 1/5
   per HK-001) — sample composition, per-band Decoded-on-replay rate with Wilson CI, the
   correctly-computed population-weighted pooled figure, the Fisher's-exact comparison against
   PR #103's published Isolated-class rates per band, and a recommendation that states plainly
   whether the ≤18.4pp H7 ceiling should be treated as needing correction, and by roughly how
   much (or that the pilot was inconclusive and what n a confirmatory sample would need).
2. `materialise_tight_sample.py` and the adapted replay driver, committed (same NFR-021 handling
   as PR #103 — ts/freq/snr/band/candidate-count values only, no callsigns or message text ever
   committed).
3. An update to `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` §3.1 (or a short addendum, if
   the brief has already been acted on by the time this lands) recording the answer to the
   class-independence question, since that section explicitly flagged it as unmeasured.

---

## 7. References

| Reference | Content |
|---|---|
| `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` §3.1 | The finding that motivates this pass — the live-path effect may not be class-independent, and nothing measured so far excludes that |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/report.md` | Source of the Isolated-class rates (13.0% / 44.4% / ≈23.4% population-weighted) this pass compares against, and the population-weighting correction (§3.1 CORRECTION) this pass's §3.3 applies proactively |
| `dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md` | The governing spec for the infrastructure this pass reuses almost unchanged |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/classify_cochannel.py` | `classify_delta` — the single shared Tight/Partial/Isolated definition this pass must not diverge from |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/materialise_isolated_sample.py` | Template this pass's `materialise_tight_sample.py` is copied from |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py` | Replay harness reused as-is (§3.2) |
| `artefacts/20260706_live_run_2308/save/` | Retained per-slot WAV audio, 07-07 session |
