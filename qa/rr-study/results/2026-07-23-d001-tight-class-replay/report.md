# D-001 Option D, Step 1 — Tight-Class Replay (Class-Independence Test) — Results Report

| Field | Value |
|---|---|
| Defect ID | D-001 (open, issue #3) |
| Type | Live local-replay diagnostic (no product/decoder code touched — instrumentation reuse only) |
| Governing spec | `dev-tasks/2026-07-23-d001-option-d-tight-class-replay-spec.md` |
| Decision context | `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` §3.1 — the Captain selected **Option D**; this pass answers the specific extension §3.1 asked for: is the live-path/gain-staging effect PR #103 found in the Isolated class class-independent? |
| Analysis date | 2026-07-23 |
| Session analysed | 07-07 (`20260706_live_run_2308`) — same session as PR #103, the only one with retained per-slot WAV audio |
| Scripts | `materialise_tight_sample.py` (§3.1), `run_tight_replay.py` (§3.2–§3.3), both this directory |
| Numeric results | `tight_sample_candidates.json`, `tight_replay_results.json` (this directory) |
| Status | **COMPLETE** |

---

## Section 1 — Study Hypothesis

### 1.1 What this pass answers

> For Tight-class low-SNR misses (WSJT-X decoded, OpenWSFZ did not, a same-slot neighbour
> within 15 Hz exists — the class the ≤18.4pp H7 ceiling is built on), what fraction decode
> successfully when the identical historical audio is replayed in isolation? Is that rate
> consistent with Isolated's (13.0% / 44.4% per band, PR #103), or materially lower?

PR #103 found that a large, first-order fraction of **Isolated**-class misses (no same-slot
neighbour within 50 Hz — not H7's target) decode on isolated replay despite failing live,
pointing at a live-path/gain-staging effect (AGC warm-up, cycle-boundary/sample-clock
alignment, adjacent-cycle state). The go/no-go brief's §3.1 flagged that nothing about those
candidate mechanisms is obviously specific to Isolated-class signals — if the same effect costs
decodes in the **Tight** class too, some fraction of the 9,956 Tight-class misses underpinning
the H7 ceiling are the live-path fix's to recover, not H7's, and the ≤18.4pp figure overstates
what H7 could actually buy. This pass measures that directly, reusing PR #103's method
unchanged apart from which population is sampled.

### 1.2 Method summary (full detail in the governing spec)

1. **§3.1 (offline, safe):** extend `classify_cochannel.py`'s `classify_delta` (used verbatim,
   unmodified) to retain `(ts, freq_hz, wsjt_snr, band, neighbour_delta_hz)` for every 07-07
   miss classified **Tight** at the primary 15 Hz cutoff — the identical cutoff Option B and
   PR #103 both use, so the three populations (Tight/Partial/Isolated) can never disagree with
   Option B's own classification. Stratified, seeded (`D001-TIGHT`, independent of PR #103's
   `D001-ISO` seed), over-drawn sample (60/stratum) via `compute_seed`.
2. **§3.2 (live):** identical throwaway-daemon / VB-CABLE-loopback / boundary-aligned replay
   harness as PR #103, distinct port (8098) to avoid any collision. Each Tight-class WAV
   necessarily contains a real neighbour within 15 Hz (that is what makes it Tight) — it is
   played as-is; this measures whether the target decodes on replay *despite* that neighbour
   still being present, not whether the neighbour is removed.
3. **§3.3 (Gate R only):** does the target message reappear among OpenWSFZ's decodes on replay?
   Unlike PR #103, no Tier-1 CG-vs-LDPC split is attempted — that instrumentation already
   proved unable to resolve anything on this corpus (100% Ambiguous in PR #103) and would not
   answer a new question here. Candidate count is recorded per cycle for descriptive
   completeness only.

### 1.3 Pre-committed decision thresholds

**None**, per the governing spec — this is a direct measurement compared against PR #103's
already-published rates via a two-proportion test (Fisher's exact), not a go/no-go gate the
way Option B's F was. The spec pre-registered two possible readings (§1): a rate comparable to
Isolated's would argue the H7 ceiling needs correcting downward; a rate near zero / clearly
distinguishable would mean the effect is Isolated-class-specific and the ceiling stands.

### 1.4 Null hypothesis

The Tight-class decoded-on-replay rate is statistically indistinguishable from the Isolated-
class rate in both bands (i.e., the live-path effect is class-independent). **Rejected in the
`−15..−10 dB` stratum (p = 0.0020); not rejected at conventional significance in the
`< −15 dB` stratum (p = 0.61), though the point estimate trends the same direction** (Section 3).

---

## Section 2 — Data Summary

### 2.1 Inputs (spec §2 Gate 0 — reconfirmed 2026-07-23)

| Input | Status |
|---|---|
| Tight-class miss list, 07-07 session | Materialised fresh — **3,879** misses (15 Hz primary cutoff), a comparable order of magnitude to PR #103's Isolated population (3,688) from the same session |
| Per-slot WAV audio, 07-07 | **100% coverage** — all 3,879 Tight-class misses have an on-disk same-named `save/*.wav`, matching PR #103's Isolated-class coverage |
| Replay harness | Reused from PR #103 unchanged apart from population/port; smoke-tested (`--target-per-stratum 2 --max-tries-per-stratum 4`) before the full run |
| Local binary used for replay | Same self-contained `OpenWSFZ.Daemon.exe` publish build as PR #103 |

### 2.2 Sample composition

| Band | Population | Drawn (over-draw) | Tried | Reproduced (Gate R fail) | Decoded-on-replay |
|---|---:|---:|---:|---:|---:|
| `< -15 dB` | 1,797 | 60 | 21 | 20 | 1 |
| `-15..-10 dB` | 2,082 | 60 | 21 | 20 | 1 |
| **Combined** | **3,879** | **120** | **42** | **40** | **2** |

Both strata reached their 20-reproduced-miss target within 21 tries (well inside the 60-try
over-draw budget) — no re-seeding needed. Live session wall time: **17:45:40Z – 18:17:21Z**
(~31.7 minutes), inside the spec's own "a few hours" estimate and faster than PR #103's own
~44.5-minute run (fewer Decoded-on-replay hits meant fewer wasted draws against the 20-per-
stratum target).

---

## Section 3 — Results

### 3.1 Tight-class Decoded-on-replay rate, and direct comparison to Isolated (PR #103)

| Band | Tight (this pass) | Isolated (PR #103) | Fisher's exact (Tight vs Isolated) |
|---|---|---|---|
| `< -15 dB` | 1/21 = **4.8%**, 95% CI [0.8%, 22.7%] | 3/23 = 13.0%, 95% CI [4.5%, 32.1%] | odds ratio 0.33, **p = 0.61** |
| `-15..-10 dB` | 1/21 = **4.8%**, 95% CI [0.8%, 22.7%] | 16/36 = 44.4%, 95% CI [29.5%, 60.4%] | odds ratio 0.06, **p = 0.0020** |
| **Population-weighted pooled** | **≈4.8%** (weights: Tight-class population, 1,797/2,082 — computed correctly from the start, not retrofitted) | ≈23.4% (PR #103, corrected post-merge) | — |

*(Naive tried-weighted pooled figure, reported per spec §3.3 for transparency and labelled
explicitly as a sample rate, not the headline: Tight 2/42 = 4.8%. In this particular run the
naive and population-weighted figures for Tight happen to coincide, because both strata drew
identical 1/21 rates — this is a small-n coincidence, not evidence the weighting correction is
unnecessary in general; PR #103's own experience is the reason this pass computed the weighted
figure deliberately rather than assuming the naive one would do.)*

**This is the headline finding, and it points the opposite direction from what §3.1 of the
go/no-go brief flagged as the risk to check.** The Tight-class Decoded-on-replay rate (4.8% in
both bands) is **far below** the Isolated-class rate in the `-15..-10 dB` stratum — where
Isolated's effect was largest (44.4%) — and the difference is statistically decisive (Fisher's
exact p = 0.0020, odds ratio 0.06). In the `< -15 dB` stratum the point estimate is also lower
(4.8% vs 13.0%) and trends the same direction, but at n=21/23 the confidence intervals overlap
substantially and the difference is not statistically distinguishable from chance (p = 0.61) —
consistent with the governing spec's own rigour-control caveat (§4.4) that a clean read might
not be achievable at pilot size in every stratum.

**Reading the two strata together:** the one stratum with enough signal to resolve the
comparison decisively (`-15..-10 dB`) says clearly that the live-path effect is **not**
operating on Tight-class misses anywhere near the magnitude it operates on Isolated-class
misses. The other stratum (`< -15 dB`) is directionally consistent with the same conclusion
but underpowered to confirm it on its own.

### 3.2 An expected, not surprising, mechanism — stated so the finding isn't over-read

This does not mean "there is no live-path effect at all" for Tight-class signals — it means
this pilot did not detect one anywhere close to Isolated's magnitude. The natural explanation,
consistent with what Tight-class misses *are* by construction: a Tight-class miss already has
a real co-channel interferer within 15 Hz **present in the replayed audio, unremoved** (§1.2
point 2) — its failure mode is plausibly dominated by that interferer's effect on candidate
generation/LDPC convergence, which isolating the playback from live AGC/timing state does
little to fix. That is the co-channel mechanism Option B/PR #102 already evidenced (the
Partial-class capture-effect signature), not a new one. This pilot cannot fully rule out a
smaller live-path effect being masked by the dominant co-channel failure mode, but it gives no
evidence for one at anywhere near the size that would materially discount the H7 ceiling.

### 3.3 Caveats

- **n=42 tried (21/stratum) is a pilot, not a precision estimate** — same caveat as PR #103.
  The `< -15 dB` comparison in particular is underpowered; a materially larger sample would be
  needed to either confirm or rule out a smaller Tight-class live-path effect in that stratum.
- **Single session (07-07), same limitation as PR #103** — the only session with retained WAV
  audio; not corroborated across band conditions.
- **This pilot answers the class-independence question, not the root-cause mechanism
  question.** *Why* the live-path effect exists at all for Isolated-class misses remains
  undiagnosed (unchanged from PR #103's own Section 5 caveats) — this pass only establishes
  that whatever it is, it does not transfer to the Tight class at a similar magnitude.
- **Candidate counts remain saturated in most reproduced Tight-class cycles** (median at or
  near the 340-candidate shim ceiling in most tries, same signature PR #103 observed) —
  reported descriptively (§2.2/raw JSON) but, per spec §3.2, no CG-vs-LDPC split was attempted
  on this data; that question was already answered (unresolvable on this corpus) by PR #103 and
  re-asking it here would not add information.

---

## Section 4 — Verdict Table

| Question | Answer |
|---|---|
| Tight-class Decoded-on-replay, `< -15 dB` | 4.8% (95% CI [0.8%, 22.7%]) vs Isolated 13.0% — not statistically distinguishable (p = 0.61) |
| Tight-class Decoded-on-replay, `-15..-10 dB` | 4.8% (95% CI [0.8%, 22.7%]) vs Isolated 44.4% — **statistically distinguishable, Tight far lower** (p = 0.0020) |
| Tight-class Decoded-on-replay, population-weighted | **≈4.8%**, computed correctly from the start (cf. PR #103's post-merge correction) |
| Is the live-path effect class-independent? | **No — not at a similar magnitude.** The decisive stratum rejects it; the underpowered stratum is directionally consistent with the same rejection. |
| Effect on the ≤18.4pp H7 ceiling (go/no-go brief §3.1) | **No correction indicated by this evidence.** The risk §3.1 flagged — that the ceiling silently double-counts a live-path-recoverable fraction — is not supported for the Tight class at the magnitude that would matter. |

---

## Section 5 — Recommendations

### 5.1 One-paragraph recommendation to Architect and Captain

**This pass resolves the specific risk the go/no-go brief's §3.1 flagged, and resolves it in
the direction that does *not* require revising the H7 ceiling.** The go/no-go brief warned that
the live-path effect found in the Isolated class might silently be eating into the same
Tight-class misses the ≤18.4pp H7 ceiling is priced against, which would make Option A cheaper
than stated. This pass measured that directly: the Tight-class Decoded-on-replay rate (4.8% in
both bands) is far below the Isolated-class rate, decisively so in the `-15..-10 dB` stratum
(p = 0.0020) and directionally consistent (though not independently significant) in `< -15 dB`.
**The ≤18.4pp ceiling stands, uncorrected by this finding.** Option D — the live-path/gain-
staging investigation — reverts to being the additive, orthogonal lead PR #103's own report
originally framed it as: worth pursuing on its own merits for the ~23.4% of Isolated-class
misses it can still recover, but **not** a precondition for pricing Option A. The A-vs-C
decision the Captain still has to make is therefore back to resting on the evidence the go/no-go
brief itself already laid out (F=29.6%, F′=75.5%, runtime lever exhausted), without a further
open discount to account for.

### 5.2 What this pass does NOT authorise

- **Not** a re-run or reopening of Option B's F=29.6% verdict, the histogram addendum, or the
  runtime-parameter sweep.
- **Not** a root-cause diagnosis of the live-path effect itself — still open, still Isolated-
  class scoped, per PR #103 §5.3.
- **Not** proof that zero live-path effect exists for Tight-class misses — only that this
  pilot found none at a comparable magnitude, with the `< -15 dB` stratum underpowered to fully
  exclude a smaller one.
- **Not** a decoder or product code change of any kind.
- **Not** the A-vs-C H7 decision itself — this closes one specific open question the brief
  flagged; the underlying cost/benefit call remains the Captain's.

### 5.3 Suggested next steps, in priority order

1. **Update `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` §3.1** to record this pass's
   answer (done alongside this report — see the brief's addendum).
2. **The A-vs-C H7 decision itself** can now proceed without an open live-path discount
   pending — the Captain has what §3.1 was missing.
3. **The live-path/gain-staging root-cause investigation** (Isolated-class-scoped, per PR #103
   §5.3) remains a reasonable, cheap, independent follow-up — its priority relative to A/C is
   now a plain cost/benefit call (≈23.4% of Isolated-class misses, a class H7 cannot address
   either way), not a blocking dependency of the H7 decision.

---

## Appendix A — Reproduction

- `python materialise_tight_sample.py` — regenerates the local population (`_work/`,
  git-ignored) and the committed candidate-sample skeleton (`tight_sample_candidates.json`,
  msg-stripped per NFR-021).
- `python run_tight_replay.py` — runs the full live pilot (target 20/stratum, over-draw
  60/stratum; pass `--target-per-stratum N --max-tries-per-stratum M` for a smaller smoke
  test). Requires: the self-contained `OpenWSFZ.Daemon.exe` publish output present, VB-Audio
  Virtual Cable installed (`CABLE Input`/`CABLE Output`), and `requests`/`sounddevice`/`numpy`/
  `scipy` importable. Produces `tight_replay_results.json` (committed, ts/freq/snr/band/
  neighbour-delta/candidate-count/LLR only — no callsigns, no message text, per NFR-021).
- Total live session wall time for this run: **2026-07-23 17:45:40Z – 18:17:21Z** (~31.7 min).
