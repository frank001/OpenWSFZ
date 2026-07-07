# D-001 Option B — Co-Channel Attribution Pass: Analysis Spec

**Date:** 2026-07-07
**Author:** Architect
**Audience:** QA (execution)
**Decision context:** `dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md` (QA → Architect scoping question)
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Status:** Approved by Architect as the required gate before any H7 (MMSE) scoping. Awaiting Captain sign-off on the *decision thresholds* in §3 before results are acted on.

---

## 0. Executive summary

QA's scoping doc established that the on-air gate ("is H6+OSD insufficient") is met, but
flagged one unresolved caveat: the headline SNR-stratified recall gap is **undecomposed**, so
we do not know what fraction of it is co-channel (the failure mode MMSE joint demodulation
actually addresses) versus isolated-weak (a sensitivity problem MMSE does **not** fix).

This spec defines a bounded, falsifiable analysis — **Option B** — that decomposes the gap and
resolves into one of three pre-committed recommendations before a 3–6 month H7 effort is
committed. It is a decision gate, not an open-ended investigation. It uses only **already-retained
text decode logs** (ALL.TXT pairs) — **no new live session, no WAV re-decode, no code change to
the product.**

**Effort:** days, not weeks. **Blocking for:** any move to Option A (H7 scoping).

---

## 1. The precise question B answers

> Of the low-SNR decodes that WSJT-X recovered and OpenWSFZ missed, what fraction had a
> co-channel interferer close enough in frequency and time that MMSE joint demodulation could
> plausibly recover them — versus being isolated weak signals against a clean floor, which MMSE
> cannot help?

That fraction is the **ceiling** on what H7 can buy. Translated into recall points, it is the
number the Captain must weigh against the 3–6 month cost. Everything below serves producing that
one figure defensibly, with an honest error direction.

---

## 2. Inputs (all already exist; confirm availability first)

The analysis needs, **per session**, only two small text files plus the truth/matcher already
used to produce the endurance recall tables:

| Input | Source | Notes |
|---|---|---|
| OpenWSFZ `ALL.TXT` | `artefacts/<session>/` (git-ignored, local) | decoded msg + UTC slot + audio freq (Hz) + SNR (dB) |
| WSJT-X `ALL.TXT` | `artefacts/<session>/` (git-ignored, local) | the oracle decode list, same fields |
| Recall matcher | the analysis script committed alongside each session's raw logs (local, git-ignored per NFR-021) | already aligns the two ALL.TXT streams by slot+freq+text to produce "WSJT-X-only" misses |

**Sessions (in priority order):**

1. `artefacts/20260706_live_run_2308/` (07-07 session, 16h59m, shim 20260033) — primary; longest, cleanest shutdown, largest miss sample.
2. 07-06 session (shim 20260031) — corroboration.
3. 06-22 session (shim 20260029) — corroboration.

**FIRST ACTION — data-availability check (do before anything else):** confirm the two `ALL.TXT`
files are still on disk for each session. They are small text files, so are far more likely
retained than the 1.4 GB WAV sets — **and the WAVs are not needed**, because B classifies from
decode metadata, it does not re-decode. If only the 07-07 pair survives, B can still run and
produce a defensible answer on the largest single sample; treat 07-06/06-22 as robustness
corroboration, not prerequisites. If **no** ALL.TXT pair survives, stop and escalate — B is not
runnable and the caveat cannot be resolved from retained data (see §7).

---

## 3. Pre-committed decision thresholds (the gate)

Set these **before** looking at results so the outcome cannot be rationalised after the fact.
Let **F = co-channel-attributable fraction** of the low-SNR miss set (see §4 for how the miss set
and "co-channel" are defined), reported with its window-sensitivity band from §5.

| Result | Interpretation | Architect recommendation to Captain |
|---|---|---|
| **F ≥ 0.60** | Gap is predominantly co-channel; MMSE is well-targeted. | **Proceed to Option A (H7 scoping)** — *contingent on first restoring the s7 harness to K=10 with co_channel/near_collision as the primary regression oracle* (see §6). |
| **F ≤ 0.30** | Gap is predominantly isolated-weak; MMSE would leave most of it untouched. | **Do not scope H7.** Redirect D-001 to sensitivity remedies (matched-filter / soft-decision / additional LDPC-OSD depth) **or** accept Option C (disclosed product limitation). |
| **0.30 < F < 0.60** | Mixed. | **Scope-with-a-price-tag decision.** Present the recoverable-recall estimate (§4.4) and cost-per-recoverable-decode; Captain decides whether the co-channel slice justifies 3–6 months versus alternatives. |

These thresholds are the Architect's proposal and are the one item in this spec that needs
**Captain sign-off before results are acted on** — the numeric cutoffs encode a
cost/benefit appetite that is the Product Owner's to set, not QA's or the Architect's.

---

## 4. Method

### 4.1 Build the miss set

1. Reuse the existing endurance recall matcher to produce the **WSJT-X-only** set: messages
   WSJT-X decoded that OpenWSFZ did not, aligned by slot + audio frequency + text.
2. **Exclude hashed (`<...>`) messages.** The endurance report already isolates a hash-resolution
   confound; keep this analysis on non-hashed decodes so we are measuring the demodulation gap,
   not the hash-table gap.
3. **Stratify by WSJT-X SNR** and restrict the primary analysis to the low-SNR bands where the gap
   concentrates (the report's `< −15 dB` and `−15…−10 dB` bins). Report F for each band separately
   as well as pooled — the co-channel fraction may itself be SNR-dependent.

### 4.2 Establish each miss's neighbourhood

For every miss, gather all **other decodes in the same UTC slot** from the **union of both apps'**
ALL.TXT (a co-channel interferer may have been decoded by only one app; using the union avoids
undercounting). For each neighbour compute Δf = |freq_miss − freq_neighbour| in Hz. Same-slot is
the correct time gate: FT8 signals in one 15 s slot overlap in time by construction (≈12.6 s
occupancy, dt typically within ±2.5 s); adjacent slots do not overlap and are excluded.

### 4.3 Classify each miss (tiered, anchored to FT8 physics + the s7 probe points)

| Class | Rule (nearest same-slot neighbour) | Rationale |
|---|---|---|
| **Tight co-channel** | Δf ≤ 15 Hz | Within ~2 tone bins (6.25 Hz spacing); capture effect fails here — this is the regime MMSE joint estimation exists for. Matches the s7 `co_channel` family (Δ7–14 Hz). |
| **Partial overlap** | 15 < Δf ≤ 50 Hz | Spectral overlap exists (FT8 occupies ~50 Hz) but subtractive cancellation / conventional demod often suffices; MMSE benefit is marginal. Matches s7 `near_collision` 25/50 Hz probes. |
| **Isolated** | no same-slot neighbour within 50 Hz | Weak signal against a clean floor. **MMSE cannot help** — sensitivity problem. |

**F (headline) = Tight co-channel / (all classified misses).** Report Partial and Isolated
counts alongside; the Partial bucket is deliberately *not* counted toward F (it is the honest
"maybe" that MMSE only partially addresses), but include a secondary F′ = (Tight + Partial)/total
as the optimistic bound so the §3 decision sees both ends.

### 4.4 Translate to recoverable recall (the number Captain needs)

Upper-bound recall recoverable by a *perfect* H7 =
`F × (low-SNR miss count) / (WSJT-X total decodable in those bands)`, expressed in recall
percentage points. State it as an **upper bound** — a real MMSE implementation recovers a fraction
of the co-channel cases, not all. Pair it with the 3–6 month estimate as cost-per-pp so the
trade-off is explicit.

---

## 5. Rigour controls (do not skip — these are what make F defensible)

1. **Window sensitivity.** Recompute F sweeping the tight-co-channel cutoff across
   {10, 12, 15, 20, 25} Hz. Report F as a band across this sweep, not a single point. If the §3
   verdict flips within the sweep, the result is "inconclusive → default to the mixed-case
   scope-with-price-tag path," not a coin-flip pick.
2. **Error direction, stated explicitly.** The classifier can only see *decoded* neighbours; a
   miss tagged "isolated" may have had an interferer that neither app decoded. This biases F
   **downward** (understates co-channel). So F ≥ 0.60 is a *conservative* trigger for A, and
   F ≤ 0.30 for "don't scope" is the claim that must survive this bias — call that out in the
   writeup.
3. **Confound guard: SNR vs presence-of-interferer.** Classify strictly on neighbour presence and
   Δf, never on the miss's own SNR. Low SNR and co-channel co-occur; folding SNR into the class
   definition would circular-reason the answer.
4. **Capture-effect sub-check.** Within Tight co-channel, tabulate the SNR delta between the miss
   and its nearest strong neighbour. A cluster of "missed the weaker of a strong+weak pair" is the
   textbook capture-effect case and is the strongest single piece of evidence that MMSE is the
   right remedy — surface it if present.

---

## 6. If B points to A: the harness precondition (carry forward, do not action now)

Should F land in the A range, H7 is **still not ready to scope the same day**. Two items from the
scoping doc's own references must precede an OpenSpec H7 proposal:

- **Restore s7 to K=10.** `s7-compounding.json` was down-powered to K=5 trials/part for gating and
  explicitly notes "restore to K=10 for any active hypothesis investigation (H7 MMSE...)". A K=5
  harness cannot serve as the H7 development oracle.
- **Make co_channel / near_collision the primary regression oracle.** The D-009 report's core
  concern is the coupling between co-channel gain and false-positive manufacture — the exact thing
  H7 claims to break. That claim needs a powered synthetic gate verifying it *during* development,
  not a post-hoc check at month six.

These are noted here so the A entry cost is not under-estimated; they are **not** part of the B
deliverable.

---

## 7. Scope guardrails — what B is NOT

- **Not** a new live session. Retained ALL.TXT only.
- **Not** a re-decode. No WAV processing, no decoder invocation, no shim change.
- **Not** a product or OpenSpec change. Pure offline log analysis (HK-000: this is a QA analysis
  task, not app/product code — no developer handoff required).
- **Not** a reopening of the three endurance conclusions. It sharpens their shared headline
  figure; it does not relitigate whether the gap exists.
- **Not** open-ended. If §2's ALL.TXT pairs do not exist for any session, B **stops** and escalates
  to Captain with two choices: (a) accept Option C on current evidence, or (b) authorise a
  short instrumented live session whose *sole* added requirement is retaining ALL.TXT pairs for
  this analysis — explicitly a larger ask than B and requiring its own approval.

---

## 8. Deliverables

1. `qa/rr-study/results/<date>-<sha>-d001-cochannel-attribution/report.md` — following the standard
   R&R report shape (QA authors Sections 1/5 per HK-001), containing: the miss-set construction,
   the per-class counts per SNR band per session, F with its §5.1 sensitivity band, F′, the §4.4
   recoverable-recall upper bound, the §5.4 capture-effect sub-check, and a single explicit line
   mapping the result to the §3 verdict.
2. The classification script, committed to the results dir (it consumes only the small ALL.TXT
   text, so — unlike the raw WAV artefacts — it and its text inputs may be committed, subject to
   the NFR-021 callsign-privacy check: scrub/aggregate any real callsigns, keep only what the
   privacy policy permits).
3. A one-paragraph recommendation to the Architect + Captain stating which §3 branch the evidence
   selects, with the error-direction caveat (§5.2) stated in the same paragraph.

---

## 9. References

| Reference | Content |
|---|---|
| `dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md` | The scoping question and the caveat this spec resolves |
| `qa/endurance/2026-07-07-bb0a1c4/report.md` | Primary session; recall-by-SNR tables, artefact path `artefacts/20260706_live_run_2308/`, matcher method |
| `qa/endurance/2026-07-06-7340e45/report.md` | Corroboration session (shim 20260031) |
| `qa/endurance/2026-06-22-f11f438/report.md` | Corroboration session (shim 20260029) |
| `qa/rr-study/scenarios/s7-compounding.json` | co_channel (Δ7–14 Hz) + near_collision (3/6/12/25/50 Hz) probe points anchoring §4.3; K=10 restore note for §6 |
| `qa/rr-study/results/2026-06-20-d70aad5/report.md` | Synthetic isolation showing H7 targets the equal-SNR co-channel case specifically |
| `qa/rr-study/results/d009-investigation-2026-06-21/report.md` §5.2 | H7 3–6 month estimate; co-channel-gain ↔ FP-manufacture coupling (§6 rationale) |
