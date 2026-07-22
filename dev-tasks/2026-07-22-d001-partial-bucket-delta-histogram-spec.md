# D-001 — Partial-Bucket Δf Structure: Analysis Spec

**Date:** 2026-07-22
**Author:** QA (self-directed)
**Audience:** Architect, Captain
**Decision context:** `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` (Option B) — the window-sensitivity sweep (§3.2) that showed F climbing from 22.1% (10 Hz) to 44.7% (25 Hz) with no data points between the 25 Hz sweep ceiling and the 50 Hz Isolated boundary.
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Status:** Proposed. Not yet approved to execute — offered as bounded groundwork in parallel with the outstanding Captain decision on Option B's mixed verdict.

---

## 0. Executive summary

Option B's own §3.2 sweep table shows F rising steadily as the tight-cutoff widens (22.1% → 24.9%
→ 29.6% → 37.1% → 44.7% across 10/12/15/20/25 Hz) and explicitly says F′ (the optimistic
Tight+Partial bound) reaches 75.5% at the 50 Hz partial boundary. What the sweep does *not* show
is the **shape** of that climb between 25 Hz and 50 Hz, nor whether the Partial bucket (15,428
pooled misses — the single largest of the three classes) is a smooth spectral skirt (consistent
with one mechanism — imperfect rejection of a nearby signal, the thing MMSE targets, just
weakening with distance) or has internal structure, e.g. a second cluster near 40–50 Hz that would
suggest a different or additional mechanism. This is purely descriptive statistics on data Option
B's classifier already computed and discarded past the three coarse buckets — no new inputs, no
new session, re-running the existing committed script with a finer histogram in place of three
bins.

**Effort:** hours, not days — the cheapest of the two follow-ups proposed alongside this spec.

---

## 1. The precise question this answers

> Within the 15–50 Hz "Partial overlap" band Option B defined, how is Δf actually distributed —
> and does the capture-effect signature Option B found in the Tight class (§3.4: 36.4% of Tight
> misses show ≥10 dB SNR delta to a stronger neighbour) extend into the Partial band, taper off,
> or vanish?

This sharpens, but does not reopen, Option B's F/F′ figures: it is diagnostic detail behind a
verdict that already stands (mixed, per the locked §3 thresholds), giving the Captain a clearer
picture of what the 18.4pp recoverable-recall ceiling is actually made of before weighing it
against H7's 3–6 month cost.

---

## 2. Inputs

Identical to Option B's — no new data. `artefacts/{20260706_live_run_2308,20260706_live_run,
"20260622_live run"}/{OpenWSFZ,WSJT-X} ALL.TXT` (confirmed present for all three sessions, per
Option B's own Gate 0 and reconfirmed on disk 2026-07-22). No WAV audio needed — this is drawn
entirely from `classify_cochannel.py`'s existing per-miss neighbour-Δf computation, which is
already implemented as an in-memory list (`min_deltas`) and discarded after producing the three
coarse buckets.

---

## 3. Method

### 3.1 Fine-grained histogram

Extend `classify_cochannel.py` (copy, do not modify the committed Option B script) to bin every
classified miss's `best_delta` (the nearest-same-slot-neighbour distance already computed in the
existing `min_deltas` loop) into 5 Hz bins from 0–50 Hz, plus a final ">50 Hz / no same-slot
neighbour (Isolated)" bin, pooled across all three sessions and both SNR bands. The per-miss
distance already exists — the change is capturing it into a histogram instead of only the three
coarse bucket counters.

**Two correctness points the copy must get right (both are how the existing script actually
behaves, not hypotheticals):**

1. **Source the histogram from `min_deltas`, not the existing `pooled_min_deltas` accumulator.**
   `pooled_min_deltas.append(...)` sits *inside* the `if neighbours:` branch, so the truly-isolated
   misses — those with **no same-slot decode at all**, which the script records as `(None, None)`
   and `continue`s past — never reach `pooled_min_deltas`. Building the histogram from
   `pooled_min_deltas` would silently drop them from the Isolated bin. `min_deltas` retains both
   cases (a real `best_delta`, or `None` for no-neighbour); iterate that per band and pool in the
   copy. Map **both** `best_delta is None` **and** `best_delta > 50` into the single Isolated bin —
   they are the two distinct ways Option B's `classify()` reaches `"isolated"`.
2. **Reconcile against Option B as a built-in self-check.** The Isolated bin must sum to Option B's
   combined isolated count (**8,236**), and the 0–50 Hz bins together to tight + partial
   (**9,956 + 15,428 = 25,384**), pooled across both bands and all three sessions. Assert this in
   the script; a mismatch means the finer binning diverged from the coarse classification it is
   supposed to be decomposing, and the run should fail loudly rather than publish a
   silently-inconsistent histogram.

### 3.2 Fill the 25–50 Hz sweep gap

Extend the existing window-sensitivity sweep (currently {10, 12, 15, 20, 25} Hz) to also report F
at {30, 35, 40, 45} Hz, using the same `classify()` logic already in the script — this is a
one-line change to `TIGHT_CUTOFFS` (the sweep loop, `combine_pooled`, and the console print all
iterate that list, so the extension propagates with no other edits). Gives a complete monotonic
F-vs-cutoff curve from 10 to 50 Hz instead of a gap between 25 and the 50 Hz ceiling.

**Read the top of the curve with care.** The 50 Hz partial boundary is held fixed while the tight
cutoff is widened, so as the cutoff approaches 50 the climb in F is increasingly *definitional*
rather than empirical: every Hz the cutoff moves reclassifies whatever `min_deltas` mass lies in
that slice from Partial to Tight, and F(50 Hz) would equal F′(50 Hz) = 75.5% exactly, by
construction. The sweep is the cumulative integral of the §3.1 histogram; **the histogram, not the
sweep, is the honest picture of where the Δf mass actually sits.** Report both, but anchor
interpretation on the histogram.

### 3.3 Capture-effect check extended to Partial

Repeat the existing §3.4-equivalent capture-effect sub-check (SNR delta between miss and nearest
neighbour, fraction ≥10 dB) **separately for the Partial class**, not just Tight. If the Partial
bucket shows a similar or higher ≥10 dB fraction to Tight, that is evidence the same
capture/near-collision mechanism extends past 15 Hz and F′ (not F) is the more honest ceiling
estimate. If the Partial bucket's SNR-delta distribution looks materially different (e.g. centred
near 0 dB — no capture signature, just background density), that argues the Partial bucket is
closer to noise than to a co-channel mechanism, and F (not F′) remains the right anchor.

**Small implementation note (this is not free, unlike §3.1/§3.2).** The committed script only
accumulates `capture_deltas` inside the `best_delta <= PRIMARY_TIGHT_CUTOFF` branch — i.e. Tight
only — and `min_deltas` retains the *neighbour* row but discards the *miss's* SNR after the loop.
The delta is `best_neighbour["snr"] − miss_row["snr"]`, so to compute it for the Partial band the
copy must additionally retain `miss_row["snr"]` per record and evaluate the delta in the
`PRIMARY_TIGHT_CUTOFF < best_delta <= PARTIAL_CUTOFF` branch. It is a few lines, but call it out
honestly rather than describing this pass as pure re-binning. **Interpretation caveat:** at larger
Δf the receiver's adjacent-signal rejection is easier, so a *falling* ≥10 dB fraction from Tight to
Partial is the physically expected default; only a *flat-or-rising* fraction is the notable,
mechanism-extends-outward finding.

### 3.4 Report, do not re-decide

This pass produces a histogram, an extended sweep table, and a Partial-class capture-effect
figure. It does **not** propose new decision thresholds — Option B's F ≥ 0.60 / ≤ 0.30 / mixed
gate stands as the Captain-locked reference. This is descriptive detail underneath an existing
verdict, offered to make the £-per-point conversation in the Option B report more concrete, not to
relitigate it.

---

## 4. Rigour controls

1. **No re-running of the classification decision itself.** The three coarse buckets and F/F′ as
   already reported stand unchanged; this only adds resolution inside what was already computed.
2. **Same error-direction caveat as Option B applies unchanged** — a miss classed at any Δf still
   can only see *decoded* neighbours; the fine histogram inherits the same downward bias Option B
   already documented (§3.3 of that report). Restate it, do not re-derive it.
3. **Report the histogram pooled and per-session** — if the shape is inconsistent session-to-session
   (unlike Option B's F, which clustered tightly at 28–32%), that itself is a finding worth
   surfacing rather than smoothing over.

---

## 5. Scope guardrails — what this is NOT

- **Not** a new live session or WAV re-decode — pure re-analysis of the existing three ALL.TXT
  pairs already on disk.
- **Not** a product or decoder code change.
- **Not** a reopening of Option B's F=29.6% verdict, its thresholds, or the §3 branch it selected
  — purely additive descriptive detail underneath an unchanged conclusion.
- **Not** a substitute for the isolated-miss pipeline-stage diagnosis proposed alongside this spec
  (`dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md`) — that answers a different
  question (why isolated misses fail) using different inputs (retained audio, not just text logs).

---

## 6. Deliverables

1. A short addendum to, or a small new section appended alongside,
   `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/` — either a
   `delta-histogram-addendum.md` in that directory (preferred, keeps it attached to the analysis it
   refines) or a new dated results directory if the Captain prefers analyses kept strictly
   one-per-directory. QA's default: addendum in place, since this is refinement of that report's
   own data, not an independent study.
2. The extended script (a copy of `classify_cochannel.py` with the histogram/sweep/Partial
   capture-effect additions), committed alongside its aggregate-only JSON output per the same
   NFR-021 handling Option B already established.

---

## 7. References

| Reference | Content |
|---|---|
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` | Option B — the verdict and sweep table this pass adds resolution underneath |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/classify_cochannel.py` | The script this pass extends (copy, not modify in place) |
| `dev-tasks/2026-07-07-d001-b-cochannel-attribution-spec.md` §5 | Original rigour controls (window sweep, error direction, capture-effect sub-check) this pass extends rather than replaces |
| `dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md`, `dev-tasks/2026-07-22-d001-runtime-param-recall-fp-sweep-spec.md` | The other two of the three groundwork passes offered ahead of the Captain's H7 decision |
