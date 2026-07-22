# D-001 — Isolated-Miss Pipeline-Stage Diagnosis: Analysis Spec

**Date:** 2026-07-22
**Author:** QA (self-directed)
**Audience:** Architect, Captain
**Decision context:** `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` (Option B) — the co-channel attribution pass that produced F=29.6% (mixed verdict) and left the **Isolated** miss class (8,236 of 33,620 pooled low-SNR misses, ~24.5%) entirely undiagnosed at the pipeline-stage level.
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Status:** Proposed. Not yet approved to execute — the Captain's Option B "scope-with-a-price-tag" decision is still outstanding (no action on D-001 since 2026-07-08); this spec is offered as bounded groundwork that can run **in parallel with, not instead of**, that decision.

---

## 0. Executive summary

Option B answered "is the D-001 gap co-channel-attributable" (partially: F=29.6%, mixed). It did
not answer the mirror question for the 24.5% of misses it classified as **Isolated** — no
same-slot neighbour within 50 Hz in either app's decode list. Isolated misses are, by
construction, not something H7 (MMSE joint demodulation) can fix; they are a sensitivity
question. But *which* sensitivity question — is OpenWSFZ's matched-filter/candidate search never
proposing these signals at all, or is it finding them and failing to converge in LDPC — has never
been asked. Those two failure modes point at completely different, and much cheaper, remedies
than either H7 or "accept as a limitation."

This spec defines a bounded diagnostic pass that answers it, reusing instrumentation and audio
that already exist: the always-on candidate-count/LLR diagnostic added for the June 2026-06-17
LLR probe (shim 20260019+, still live in the current 20260033 shim), and the primary session's
retained per-slot WAV audio (`artefacts/20260706_live_run_2308/save/`, confirmed on disk — 4,075
per-slot `.wav` files, 4,076 directory entries including one `samples/` subdirectory, full ~17h
span).

**One caveat up front, in scope from the start (§3.3, §4):** the existing diagnostic is
*pass-level* — it reports one candidate count and one LDPC-fail statistic per decode pass across
the **whole** FT8 passband, not per candidate and not per frequency. Because each replayed WAV
carries the entire recorded slot (only the ±50 Hz neighbourhood around the target is empty, by the
"Isolated" definition — the rest of the ~3 kHz passband is as busy as the band was on-air), most
slots will present many passband-wide candidates that cannot be attributed to the target signal.
This pass is therefore honestly framed as a **cheap first look that may land largely in the
Ambiguous bucket**; whether that is acceptable, or whether a decisive version warrants surfacing
per-candidate frequency across the interop (a bounded, instrumentation-only native-shim addition —
no decode-behaviour change), is an explicit decision for the Captain/Architect (§4.5), not
something this spec smuggles in.

**Effort:** a few hours of local replay plus an afternoon of log correlation, not days.
**Not** a new on-air capture. **Not** a product/decoder code change — pure instrumentation reuse.

---

## 1. The precise question this answers

> Of the Isolated-class low-SNR misses (WSJT-X decoded, OpenWSFZ did not, no plausible co-channel
> interferer within 50 Hz), what fraction failed because OpenWSFZ's candidate search never
> proposed the signal — versus failed because a candidate was found but LDPC could not converge
> on it?

This is the same diagnostic question the 2026-06-17 LLR probe answered for the co-channel
(Tight-class-equivalent) failure mode — it found candidate generation was *not* the bottleneck
there (15–28 candidates/cycle reaching LDPC) and LDPC convergence *was*, driven by high-confidence
wrong-sign LLRs under equal-SNR interference (revised finding, shim 20260020; see
`qa/rr-study/results/2026-06-17-abd6190/report.md` §5). That mechanism is specific to **mutual
interference** and has no reason to apply to an isolated weak signal against a clean floor. This
pass asks the analogous question for the population Option B calls Isolated, where the answer is
not yet known and the two possible answers point at different remedies:

- **Candidate-generation failure dominant** → the fix is in `ftx_find_candidates` / sync-score
  threshold / spectral resolution (`pass_min_score`, `K_MAX_CANDIDATES*` in `ft8_shim.c`) — a
  tuning and possibly a matched-filter change, weeks not months.
- **LDPC-convergence failure dominant** (candidates found, `meanAbsLLR` low, still fails) → a
  soft-decision / additional-iteration-depth question — potentially an OSD-depth (`ndeep`)
  increase or LLR-scaling change, similarly bounded.
- **Mixed, no dominant mode** → informs the Captain that neither cheap remedy has a clean target;
  strengthens the case for treating the low-SNR floor as a disclosed limitation (Option C) rather
  than searching for a quick win.

---

## 2. Inputs (data-availability check already performed)

| Input | Status | Detail |
|---|---|---|
| Isolated-class miss list (ts, freq_hz) for the 07-07 session | **Must be generated** — not currently materialised anywhere; `classify_cochannel.py` computes counts but discards per-miss identity after classification | Requires a small, local-only extension of the existing classifier (§4.1) |
| Per-slot raw audio for the 07-07 session | **Confirmed present** | `artefacts/20260706_live_run_2308/save/*.wav` — 4,075 `.wav` files (plus one `samples/` subdirectory), filename = UTC slot timestamp (`YYMMDD_HHMMSS.wav`), spanning `260706_211700` → `260707_141530` (2026-07-06 21:17 → 2026-07-07 14:15). Filename stem matches the raw 6-digit `ts` field in `OpenWSFZ ALL.TXT` / `WSJT-X ALL.TXT` **exactly** (verified: first WAV `260706_211700.wav` ↔ ts `260706_211700`) — trivial string join on the raw ts, no normalisation or timestamp arithmetic. **Caveat:** not every ALL.TXT decode slot is guaranteed a same-named WAV (capture gaps, session-boundary slots); over-draw the sample (§3.1) so any sampled miss without an on-disk WAV can be dropped without re-seeding. |
| Candidate-count / LLR diagnostic instrumentation | **Confirmed present and always-on** | `Ft8Decoder.cs` lines ~280–294 unconditionally captures `GetLastCandidateCounts` and `GetLastLlrStats` on every `DecodeAll` cycle (not behind a feature flag or diagnostic build). Logged at `Debug` level (lines ~399–422): per pass, candidate count + decoded count, plus per-pass `failCands` / `meanAbsLLR` / `prenormVar` for LDPC-failing candidates. Enabling capture requires only `Logging.FileEnabled=true` / `Logging.FileLogLevel=Debug` (the existing "Lesson 8" configuration used for the original LLR probe) — no code change. |
| 07-06 / 06-22 sessions | **No per-slot audio retained** — checked; only ALL.TXT pairs exist for those two. | Not usable for this pass. 07-07 alone is sufficient as a first pass (it is also Option B's primary/largest session). |

**Gate 0 verdict: PASS.** Unlike Option B, this pass does need the WAV audio — but it is already
on disk for the one session needed, so no new capture, live or otherwise, is required.

---

## 3. Method

### 3.1 Materialise the Isolated-miss sample (local only, NFR-021)

Extend (do not modify in place — copy to a new script) `classify_cochannel.py`'s per-band loop:
where it currently classifies each miss and discards `(ts, freq)`, additionally append `(ts,
freq_hz, wsjt_snr)` to a local list for misses classified `isolated` in the 07-07 session only,
restricted to the two primary low-SNR bands. This list contains no callsigns or message text —
`freq_hz`/`snr`/`ts` alone are not privacy-sensitive under NFR-021, but per existing project
convention (Option B kept all ALL.TXT-derived per-record data local/git-ignored, committing only
aggregates), keep this list in the local `artefacts/` or results working directory, not committed.

From this list, draw a **stratified random sample of 40** isolated misses (20 from `< −15 dB`, 20
from `−15…−10 dB`), seeded deterministically (reuse `compute_seed` from `harness/common.py` for
reproducibility) rather than hand-picked, to avoid cherry-picking. **Over-draw** — take an ordered
seeded sample of ~60 per stratum and walk it, keeping the first 20 that (a) have an on-disk
same-named WAV and (b) survive replay as a genuine, reproduced miss (§3.3 Gate R) — so slots
dropped for either reason do not force a re-seed or bias the sample toward earlier draws.

### 3.2 Local replay session

1. Run OpenWSFZ locally (not on-air — VB-CABLE loopback, as the existing harness scenarios do)
   with `Logging.FileEnabled=true`, `Logging.FileLogLevel=Debug`.
2. For each of the 40 sampled misses, play its corresponding `save/{ts}.wav` file through the
   configured input device, one at a time, with enough gap between plays that each lands as its
   own decode cycle (mirror the cycle-boundary discipline `run_h6_probe.py` already uses — no new
   timing mechanism needed, just reuse `_wait_for_boundary`/`_next_boundary` or an equivalent
   fixed inter-play pause).
3. Record the resulting Debug log lines for that cycle: `Iterative subtraction: pass {P} of {M},
   {C} candidates found, {K} decoded` and, where present, `... LDPC fail stats — failCands=...
   meanAbsLLR=... prenormVar=...`.

### 3.3 Classify each sampled miss

**Gate R (prerequisite — the miss must reproduce).** For each replayed slot, first check whether
the target message now appears among OpenWSFZ's decodes. Playing one slot's WAV in isolation is
*not* identical to the original live cycle — no live AGC/soft-limiter history, no exact
sample-clock/cycle-boundary alignment, no adjacent-cycle state. If OpenWSFZ **decodes the target on
replay**, the original miss did not reproduce and the slot tells us nothing about *why* it was
missed live — it must be excluded from the CG/LDPC split. This is not a nuisance to hide: a **high
decoded-on-replay fraction is itself a first-order finding**, pointing at a live-path / timing /
gain-staging difference rather than a raw decoder-sensitivity gap, and would redirect D-001 away
from both `ftx_find_candidates` tuning *and* OSD depth. Report this fraction explicitly.

For the slots that **do** reproduce the miss:

| Observation | Classification |
|---|---|
| **Gate R:** target message *is* among the replayed decodes | **Miss did not reproduce — exclude from the split; tally separately (see above).** |
| Candidate count = 0 across every pass | **Candidate-generation failure** — the signal was never proposed to LDPC. *(Expected to be rare: the WAV replays the full busy passband, so a genuinely empty candidate list is unlikely even when the target specifically was not proposed — see the power caveat below.)* |
| Candidate count > 0, target message not decoded, and the cycle has **≤ 3 total candidates** and `meanAbsLLR` is low relative to the passing-candidate baseline (compare against a small set of *successful* isolated-band decodes from the same session as a reference distribution — do not invent a hardcoded threshold) | **LDPC-convergence failure.** |
| Candidate count > 0 but the cycle has **> 3 total candidates** (the per-pass log is not per-candidate-frequency, so the target candidate cannot be isolated with confidence) | **Ambiguous — exclude from the headline split, report separately.** |

**Power caveat — read this before trusting the split.** The classification above leans on
candidate count as a proxy for "was *this* signal proposed," but the diagnostic is pass-level and
passband-wide (`candidateCounts[p]` in `Ft8Decoder.cs` is one integer per pass across the whole
~3 kHz spectrum; per-candidate frequency exists inside native `decode.c` as `candidate.freq_offset`
but is **not** surfaced across the interop). On a busy band most reproduced-miss slots will carry
well more than 3 candidates, so:

- the **CG-failure** signal (count = 0) can essentially never fire — a genuinely empty candidate
  list requires the *entire* passband to be quiet, which these slots are not; and
- the **Ambiguous** bucket may absorb the majority of the sample.

Both effects are honest constraints of the existing instrumentation, not classifier sloppiness —
do not paper over them by lowering the ">3 candidates" bar the way a threshold-chase would. If the
pilot returns mostly-Ambiguous (the likely outcome), that is the finding: **the current pass-level
diagnostic cannot resolve the CG-vs-LDPC question for the Isolated class on a busy band, and a
decisive answer requires surfacing per-candidate frequency (§4.5).**

### 3.4 Report the split

Report as counts and fractions of the 40-sample, in two tiers:

- **Tier 0 — reproduction:** `Reproduced-miss` vs `Decoded-on-replay` (Gate R). The
  `Decoded-on-replay` fraction is reported as a headline number in its own right, not buried.
- **Tier 1 — split within the reproduced misses only:** `Isolated-CG` (candidate-generation
  failures) / `Isolated-LDPC` (convergence failures) / `Isolated-Ambiguous`, with a binomial
  confidence interval on each.

n=40 is small — state this plainly; this is a **pilot**, not a precision estimate. Two lopsided
outcomes are both *findings*, not failures: a high `Decoded-on-replay` fraction redirects D-001 at
the live path, and a high `Isolated-Ambiguous` fraction shows the pass-level diagnostic is
insufficient and motivates the §4.5 per-candidate-frequency addition. Only a clean CG-vs-LDPC lean
warrants the follow-up tuning work, and a larger confirmatory sample would then be the natural next
step — not something to front-load here.

---

## 4. Rigour controls

1. **Reference baseline, not a hardcoded LLR cutoff.** "Low meanAbsLLR" must be judged against a
   same-session reference distribution from *successful* low-SNR decodes, not an arbitrary number
   — the 2026-06-17 probe's own history (near-zero-LLR hypothesis refuted, revised to
   wrong-sign-LLR) is a caution against assuming a threshold without checking.
2. **Stratified, seeded sampling** — no manual selection of "interesting" misses.
3. **Ambiguous cases excluded, not forced.** See §3.3.
4. **This is a pilot (n=40), stated as such.** No decision threshold is pre-committed here (unlike
   Option B) because the purpose is exploratory — to determine *whether* a dominant failure mode
   exists worth chasing, not to gate a specific go/no-go the way F was gated. If the Captain wants
   a decision-grade version of this, that is a follow-up scoping conversation once the pilot shape
   is known.
5. **Reproduction gate before attribution.** No slot is classified CG vs LDPC until it has been
   confirmed to *still miss* on isolated replay (§3.3 Gate 0). Attributing a cause to a miss that
   does not reproduce would be measuring the replay harness, not the decoder.
6. **The pass-level-diagnostic ceiling is disclosed, not worked around.** Because the reused
   instrumentation cannot attribute candidates to a frequency (§3.3 power caveat), a
   mostly-Ambiguous pilot is an anticipated and reportable outcome, not a run to be re-tuned into a
   cleaner-looking split.

### 4.5 Decision point for the Captain/Architect — decisive vs. cheap

The pilot as specified is deliberately code-change-free and may therefore be inconclusive by
construction (§3.3). Converting it into a *decisive* CG-vs-LDPC attribution requires surfacing
**per-candidate frequency** so the target signal can be isolated from unrelated passband
candidates. The data already exists natively (`candidate.freq_offset` in the patched
`ft8_lib_build/.../decode.c`); exposing it is a **bounded, instrumentation-only** native-shim +
interop + Debug-log addition — it changes *what is observed*, not *what is decoded*, so it stays
within D-001's "no decode-behaviour change" guardrail. This spec does **not** assume that work;
it flags it as an explicit choice: run the cheap pilot first and let its Ambiguous fraction decide
whether the shim work is worth commissioning, or commission the shim up front for a one-shot
decisive pass. QA's recommendation: **run the cheap pilot first** — if `Decoded-on-replay`
dominates, neither the shim nor any decoder tuning is the right next move, and we would have spent
nothing to learn that.

---

## 5. Scope guardrails — what this is NOT

- **Not** a new on-air capture — all audio is already-retained, previously-recorded material from
  the 07-07 session replayed locally.
- **Not** a product or decoder code change. The diagnostic getters and their logging already
  exist; this pass only turns on an existing log level and reads the output. (The optional
  per-candidate-frequency shim in §4.5 is a *separately-commissioned* follow-up, explicitly not
  part of this pass, and even it would be instrumentation-only — it never changes what is decoded.)
- **Not** a reopening of Option B's F=29.6% verdict or its thresholds — this is additive, scoped
  strictly to the Isolated class Option B already carved out.
- **Not** a precision measurement. A 40-sample pilot bounds the next question; it does not replace
  a full-population pass if the Captain later wants one.

---

## 6. Deliverables

1. `qa/rr-study/results/<date>-<sha>-d001-isolated-pipeline-diagnosis/report.md` (QA authors
   Sections 1/5 per HK-001) — sample composition, per-slot classification table (ts, freq, SNR,
   reproduced?/decoded-on-replay, pass candidate count, meanAbsLLR where applicable, verdict), the
   Tier-0 reproduction fraction, the Tier-1 CG/LDPC/Ambiguous split with confidence interval, and a
   recommendation that names which of three follow-ups (if any) the evidence points at:
   live-path/gain-staging investigation (if `Decoded-on-replay` dominates), sync-threshold tuning
   (CG), soft-decision/OSD-depth tuning (LDPC), or the §4.5 per-candidate-frequency shim (if
   Ambiguous dominates and the question is worth resolving decisively).
2. The sampling + log-correlation script, committed (NFR-021: ts/freq/SNR/candidate-count/LLR
   values only, no callsigns or message text ever enter it).

---

## 7. References

| Reference | Content |
|---|---|
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` | Option B — defines the Isolated class this pass diagnoses further |
| `dev-tasks/2026-06-17-llr-diagnostic-shim-20260019.md` | Origin of the candidate-count/LLR diagnostic instrumentation this pass reuses |
| `qa/rr-study/results/2026-06-17-abd6190/report.md` §5 | The analogous diagnosis for the co-channel (Tight) case — candidate generation not the bottleneck, LDPC convergence is, wrong-sign LLRs under equal-SNR interference |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (~lines 260–422) | Confirms the diagnostic capture is always-on and the exact Debug log line formats to grep for |
| `qa/rr-study/harness/run_h6_probe.py` | Existing cycle-boundary playback discipline this pass's replay step reuses (not the probe logic itself) |
| `dev-tasks/2026-07-22-d001-runtime-param-recall-fp-sweep-spec.md` | Companion pass — empirically probes this spec's candidate-generation question by testing whether lowering `k_min_score_pass2` recovers Isolated-class misses |
| `artefacts/20260706_live_run_2308/save/` | Retained per-slot WAV audio, confirmed 4,075 `.wav` files (4,076 dir entries incl. a `samples/` subdir) on disk, 2026-07-22 |
