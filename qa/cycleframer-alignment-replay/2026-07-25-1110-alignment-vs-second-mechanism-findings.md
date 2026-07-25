# 11.10: the live-path loss is NOT explained by alignment error — a second mechanism exists

**Author:** QA, 2026-07-25. **Status:** verdict delivered — falsifies the Architect's stated
prediction (`2026-07-25-d001-live-path-decomposition-findings.md` §4).
**Harness:** `d001_1110_decomposition.py`. **Raw output:** `_work/d001_1110/per_cycle_alignment.csv`
(1,783 rows), `_work/d001_1110/decile_summary.csv`. NFR-021: both git-ignored, no callsigns in
either (message text is never written by this script — only counts, DT, recall, δ).

---

## 0. The falsifiable prediction, and the verdict

`tasks.md` 11.10's handoff stated a prediction in advance: reconstructed `δ_live(k)` should sit
near 0 in decile 1, reach `|δ| ≈ 2.3` by decile 2, exceed `|δ| ≈ 3` in deciles 3–4, and hover at
`|δ| ≈ 2.4–2.6` thereafter — matching alignment explaining the count-ratio pass's observed
retention collapse.

**Verdict: DOES NOT MATCH.** Measured `|δ_live|` never exceeds 1.9 s in any decile, including the
two (3, 4) where retention collapsed to 2–3% in the original count-ratio pass. Applied through the
study's own validated, zero-free-parameter recall(δ) model (SPEC.md §2.5 item 10, RMS 0.056 against
Phase 1b), the *measured* alignment error in the worst deciles predicts recall of **0.96–0.99** —
near-total — while the *actual* measured recall there is **0.00–0.17**. This is not a small
residual; it is the model being wrong by 90+ percentage points, and only in specific deciles.

**A second, distinct mechanism exists in the live capture path, and it — not alignment — is what
dominates D-001's live-path loss.** Per the handoff's own framing, this was flagged as "the more
important outcome to be able to detect," which is why the prediction was committed to numerically
in advance rather than after the fact.

## 1. Method

1. **True-UTC reconstruction (method constraint b).** Walked both daemon log files
   (`openswfz-20260724T202531Z.log`, `...210711Z.log`) in order, tracking `cycleStart` precisely
   (millisecond precision) per window: advance by exactly 15.000 s on ordinary windows; jump to the
   exact value reported by each `Cycle boundary resync: ... cycleStart re-anchored to HH:MM:SS.mmm`
   line (136 of them — matches `corrections_table.csv` exactly); **hard-reset to the reported grid
   value on each `CycleFramer started` line** (3 occurred: two within the first 90 s before
   sustained decoding began, one genuine mid-session restart at 21:07:00 UTC, ~41 min in — this
   restart is not mentioned in any prior artefact and would have silently corrupted the
   reconstruction across that boundary if missed). 2,839 windows reconstructed; 0 unresolved.
   **Validated against SPEC.md §2 item 1's independently-established figure**: the last
   reconstructed `cycleStart`'s offset from the true 15 s UTC grid is **5.958 s**, matching the
   documented final offset (65.96 s cumulative correction mod 15 = 5.96 s) to the millisecond —
   the reconstruction is correct, not merely plausible.
2. **Joining (method constraint b, continued).** For each of the live daemon's 1,789 decoded
   cycles, round its reconstructed `cycleStart` to the nearest true 15 s UTC grid instant and match
   to arm A's (grid-aligned, all 2,827 cycles, from Phase 1b's `baseline_decoded/`) reference cycle
   at that instant. 1,783 of 1,789 joined (6 had no reference cycle — WAV-archive gaps); 0 excluded
   by the `|ref(k)| ≥ 5` filter (arm A never drops below 5 decodes/cycle, per the original
   count-ratio pass).
3. **Recall (method constraint a).** SPEC.md §5.3's paired within-cycle metric — message-text
   match, hash-token normalized (`<...>`/`<CALLSIGN>` → `<HASH>`) per SPEC.md §7.4(b) — reused
   directly from `score_recall.normalize_hash_tokens`.
4. **δ_live (method constraint c).** `δ_live(k) = DT_ref(k) − DT_live(k)`, both sides the per-cycle
   population median DT (SPEC.md §6 step 3's corrected sign — verified against this study's own
   established `DT_obs = DT_true − δ` relation).
5. **Predicted recall.** `falsification_check.predict_recall(δ_live(k), dt_population)` — the same
   model Phase 1b validated at RMS 0.056 against 12 independent measured points, applied here
   per-cycle against the session-wide 51,862-value arm-A DT population.
6. **Guards (method constraint d).** Collision assertion: **0 merges across all 1,783 scored
   cycles** — PASS. `hashTableRejectCount`: live session final **25,465**; arm-A baseline (2,827
   cycles) **73,490** — both recorded; arm A's is larger in absolute terms simply because it
   decodes ~2.6× as much material overall (18.35 vs 7.08/cycle), not evidence of a confound by
   itself.

## 2. Per-decile result

| decile | window (UTC) | n | median recall | median predicted recall | median residual | median δ_live | median \|δ_live\| | predicted \|δ\| (count-ratio pass) |
|---|---|---|---|---|---|---|---|---|
| 1 | 20:28–21:38 | 282 | 0.9545 | 0.9987 | −0.044 | +0.30 | 0.30 | 0.30 |
| 2 | 21:38–22:49 | 255 | 0.8500 | 0.9655 | −0.076 | +1.70 | 1.80 | 2.35 |
| 3 | 22:49–00:00 | 127 | **0.0000** | 0.9883 | **−0.986** | +0.25 | 1.20 | 3.0 (beyond) |
| 4 | 00:00–01:11 | 111 | **0.0000** | 0.9886 | **−0.989** | +0.70 | 1.05 | 3.0 (beyond) |
| 5 | 01:11–02:22 | 214 | 0.8500 | 0.9840 | −0.108 | −1.10 | 1.38 | 2.40 |
| 6 | 02:22–03:33 | 189 | 0.1667 | 0.9731 | **−0.401** | +1.00 | 1.50 | 2.48 |
| 7 | 03:33–04:44 | 170 | 0.3889 | 0.9916 | −0.163 | +0.60 | 1.00 | 2.46 |
| 8 | 04:44–05:55 | 185 | 0.9167 | 0.9956 | −0.073 | −0.55 | 0.60 | 2.43 |
| 9 | 05:56–07:06 | 135 | **0.0769** | 0.9560 | **−0.712** | +1.70 | 1.90 | 2.53 |
| 10 | 07:06–08:17 | 115 | 0.7500 | 0.9729 | −0.244 | +0.90 | 1.80 | 2.53 |
| **session** | | **1,783** | **0.8333** | **0.9886** | **−0.124** | +0.40 | 1.10 | — |

Two clearly distinct decile populations, not a smooth gradient:

- **"Good" deciles (1, 2, 5, 8, 10):** small residual (−0.04 to −0.24), and measured `|δ_live|`
  broadly tracks what the count-ratio pass predicted (loosely — decile 1 matches almost exactly,
  others run 20–40% under). Alignment is a real, present, second-order effect here.
- **"Collapsed" deciles (3, 4, 6, 9):** median measured recall 0.00–0.17, but median measured
  `|δ_live|` is *small* (1.0–1.9 s) — well inside the range where the validated model predicts
  0.95+ recall. The residual is −0.40 to −0.99. **These are the deciles the count-ratio pass's
  retention column showed collapsing to 2–3% (deciles 3–4) or dropping to a quarter (6, 9), and
  alignment measurably is not why.**

Decile 7 sits in between (moderate residual, −0.163) — consistent with a session that has two
superimposed effects of different relative weight cycle to cycle, not a single clean on/off switch.

## 3. Why this is the right test, and its one honest limitation

**Why this is decisive, not just suggestive.** The recall(δ) model being applied here is not new or
provisional — it is the same zero-free-parameter model (SPEC.md §2.5 item 10) that Phase 1b already
validated against 12 independently-measured points at RMS 0.056, reproducing every one of them from
source code (`decode.c:279`'s hardcoded time-search bound) with nothing fitted. Applying that same
validated model to this study's own directly-measured `δ_live(k)` and finding a 90-point residual in
specific deciles is not "the model might be imprecise here" — it is the model correctly saying these
cycles' *measured* alignment error should not have cost them anything close to what they actually
lost.

**The one honest limitation.** `δ_live(k)` can only be computed for cycles with **at least one live
decode** — DT is a property of a decoded signal, not of silence. The 1,050/2,839 (37.0%) cycles that
decoded *nothing at all* (disproportionately concentrated in deciles 3–4, per the count-ratio pass's
own retention figures) are invisible to this method entirely; they contribute no row to
`per_cycle_alignment.csv`. What this study establishes is therefore precisely: **among the cycles
that did produce at least one live decode during the collapsed deciles, their own measured alignment
error does not predict the recall they actually got.** It does not, by construction, directly test
alignment on the fully-silent remainder. It does not need to, for the falsification verdict above —
those survivor cycles already contradict "alignment explains it" on their own terms, and there is no
mechanism by which the *invisible* cycles would need a *smaller* second-mechanism effect than the
*visible* ones that already show it. If anything, the fully-silent cycles are the more, not less,
affected end of whatever this second mechanism is.

## 4. Consequences

1. **10.8's live acceptance gate should proceed only with this qualification on record.** A `10.1`–
   `10.4` fix that fully converges the correction loop would still be worth pursuing (deciles 1/2/5/
   8/10's non-trivial residual, and decile 5/6/7's partial one, are real, alignment IS costing
   something) — but it would **not** recover most of D-001's live-path half. The Architect's own
   framing ("a working `CycleFramer` fix is worth ~11 decodes/cycle, roughly half the total D-001
   gap") was explicitly conditioned on this prediction holding; it did not hold, so that sizing does
   not carry over. A revised estimate needs the second mechanism identified first — sizing it from
   this data alone would be guessing.
2. **A second, distinct, time-varying mechanism in the live capture path is now the highest-value
   open question**, ahead of continuing `CycleFramer` convergence work. Candidates not yet
   evaluated: capture-buffer starvation/backpressure independent of `CycleFramer`'s own drift
   correction (the WASAPI/`Channel<float[]>` pipeline instrumentation added in tasks.md §8 measured
   *timing* flatness, not *data-loss*/dropout — a genuinely silent or corrupted capture window would
   not necessarily show up as elevated inter-window elapsed time); a periodic resource contention
   effect correlated with wall-clock time-of-band rather than with the correction loop; or something
   in the decode/decision path specific to the live daemon's runtime conditions (concurrent I/O,
   GC pauses, thread-pool contention under sustained load) not present in the offline replay
   harness. Diagnosing which is out of this item's scope (SPEC.md §11's "what this settles, and what
   it does not").
3. **Deliverable #4** (predicted recall cost of the 9.5 session's alignment excursions, SPEC.md §6)
   should be sized from this study's own directly-measured `δ_live`/predicted-recall pairs, not from
   the count-ratio pass's inverted-magnitude table, now superseded by this result for that purpose.
4. Flagging for the Captain/Architect explicitly, not resolving unilaterally (this is a
   scope/priority call on a multi-week investigation, not a QA-scoped mechanical one): whether to
   (a) continue `10.1`–`10.4`'s live acceptance run anyway, now correctly scoped as "recovers a
   modest, not dominant, share of D-001," (b) pause it to chase the second mechanism first, since a
   passing `10.8` would no longer mean what earlier framing assumed it would mean, or (c) something
   else.
