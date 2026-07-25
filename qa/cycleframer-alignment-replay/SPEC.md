# Offline alignment-replay study — how much recall does cycle-boundary misalignment cost?

**Author:** Architect session, 2026-07-25. **Status:** Phase 0 complete and ratified (see §2.5 and
§14); Phase 1 specified below, amended 2026-07-25 in light of Phase 0's results.
**Scope:** QA tooling only — zero `src/` changes, no live radio time. Implementable by a QA
session under HK-000.

---

## 1. The question

`fix-cycle-boundary-clock-drift` exists because the capture device's clock-rate error moves
OpenWSFZ's 15-second decode window off the true UTC cycle grid. Five live rounds have measured
the *correction loop's* behaviour in detail. **None has ever measured what misalignment actually
costs in decodes.**

That gap matters right now because the Captain's decision on whether the cycle-boundary work is
folded into D-001 or split out turns on exactly one question:

> **How much decode recall is lost per second of window-alignment error?**

Everything downstream needs this number:

- Whether the alignment excursions the live runs exhibit are material to D-001's recall gap.
- What maximum correction magnitude is acceptable — a correction perturbs alignment by its own
  size, so an oversized correction is itself a recall event.
- A quantitative acceptance bound for `tasks.md` 10.8, replacing criteria that only read the
  framer's internal deviation log.

This study produces that number as a curve: **recall as a function of alignment offset.**

## 2. What is already established (do not re-derive)

From the 9.5 session's own artefacts (`artefacts/20260724_live_run_2227/`), Architect analysis
2026-07-25:

1. **`cycleStart`'s offset from the UTC 15-second grid equals the cumulative signed correction
   sum, exactly, modulo 15** — verified to the millisecond across all 136 corrections of the
   11h51m session. Cumulative correction sum reached +65.96 s; final off-grid offset 5.958 s
   (65.96 mod 15 = 5.96). Emitted cycle labels are spread across all 15 residues (only 452 of
   2,839 on-grid).
2. **The label slide does not track content position.** Median DT shows no monotonic trend and no
   correlation with the slide. Had window *content* slid 66 s, every decode would have vanished;
   20,092 decodes were logged, including at the session's end.
3. **Window alignment oscillates by roughly ±1–2 s**, on the same scale as the corrections firing
   at the time (0.9–1.1 s late in the session). Median DT per 30-minute bucket, against a
   cumulative slide rising monotonically from 0.18 s to 66.80 s:

   | elapsed | slide | median DT | p10 | p90 |
   |---|---|---|---|---|
   | 0.0 h | 0.18 s | +0.60 | 0.30 | 1.00 |
   | 1.5 h | 2.80 s | −1.10 | −1.60 | −0.60 |
   | 5.0 h | 11.90 s | +2.90 | 2.20 | 3.10 |
   | 6.0 h | 17.94 s | −0.80 | −1.30 | 0.00 |
   | 9.0 h | 43.75 s | +1.30 | 0.50 | 1.50 |
   | 9.5 h | 47.10 s | −1.30 | −1.40 | −0.20 |
   | 11.5 h | 66.80 s | +0.15 | −1.40 | 2.20 |

   Real FT8 stations transmit within roughly ±0.5 s of the cycle boundary, so a window sitting at
   median DT +2.9 s is badly misaligned. **What that costs is unmeasured — this study measures
   it.**

4. **The drift correction is not on `main`** (`git show main:src/OpenWSFZ.Ft8/CycleFramer.cs`
   contains no correction code). D-001's original recall gap was therefore measured *without* it.

### 2.5 Added by Phase 0 (2026-07-25) — established, do not re-derive

Phase 0 ran 129 decodes over 25 cycles of segment 0 at δ ∈ {0, 2.0, 3.0, 5.0, 7.5}. Every figure
below was reproduced independently by the Architect from the committed harness and the local
`_work/` outputs before being recorded here.

5. **The harness is sensitive to alignment, and the transition is a cliff, not a slope.**

   | δ | median recall | IQR | n cycles |
   |---|---|---|---|
   | 0.0 | 1.0000 | — (identity) | 25 |
   | 2.0 | 0.9200 | 0.878–0.957 | 25 |
   | 3.0 | 0.0769 | 0.045–0.083 | 25 |
   | 5.0 | 0.0000 | — | 25 |
   | 7.5 | 0.0000 | — | 25 |

   Zero cycles were excluded by §5.3's `|ref(k)| ≥ 5` filter (0 of 25). Shuffled-pairing control
   (§7.2) returned median 0.0000 across all 25 cycles. δ=0 returning exactly 1.0000 is the
   **identity case** — arm A scored against itself — and is an anchor, not evidence.

6. **The true DT baseline for these signals is +0.80 s, not 0** (deliverable #3, in hand for
   segment 0; still to be widened across the session). Measured on arm A: median +0.80,
   p10–p90 = +0.60…+1.10, n=585.

7. **The sign relation `DT_obs = DT_true − δ` is confirmed empirically.** Arm δ=2.0 has median DT
   −1.20, exactly `0.80 − 2.00`. **§6 step 3's alignment-error mapping carries this minus sign —
   a live median DT above the +0.80 baseline corresponds to a *negative* δ.**

8. **The cliff is the decoder's time-search bound, evidenced by survivor selection.** At δ=3.0 the
   median DT stops following the shift (−1.25 observed vs −2.20 predicted) while decode count
   drops 550 → 48. Only signals whose natural DT leaves them inside the bound survive. This is
   stronger corroboration than the recall cliff alone.

9. **Therefore the tolerance band is asymmetric about δ=0 and its centre is δ ≈ +0.8.** With
   signals at DT +0.80, a search bound near ±2.5 s, and a transmission spanning ≈[0.80, 13.44] s
   of the cycle: positive δ has ≈3.3 s of headroom and clips the signal *head*; negative δ has
   only ≈1.7 s of headroom and clips almost nothing (δ=−1 loses no symbols at all), so on that
   side the search bound binds *before* symbol loss does. **Prediction: the negative cliff sits
   near δ ≈ −1.7, roughly half the positive side's tolerance.** Phase 0 probed only positive δ, so
   this is an untested model prediction — Phase 1 tests it first (§9).

## 3. Invalidated approaches — do not repeat

Three checks were attempted during the analysis above and are void. They are recorded here
specifically so this study does not re-run them and reach a false conclusion:

| Approach | Why it is void |
|---|---|
| Reading cumulative slide off the WAV filenames | `wav/` is **WSJT-X's** per-cycle recordings on the true UTC grid; it carries no information about OpenWSFZ's `cycleStart`. |
| "Recall vs WSJT-X" from `ALL.TXT` | `ALL.TXT` is **OpenWSFZ's own** decode log (FR-027/028 writes WSJT-X-compatible format). The comparison was OpenWSFZ against itself — it returned a flat 98–102% and a lag-0 correlation of exactly 1.000, both artefacts. |
| Treating a flat recall result as closing Decision 9 Finding 4 / task 10.6 | It rested entirely on the void comparison above. 10.6 remains open. |

**Standing rule for this study:** every arm must record the provenance of every input file, and
the harness must refuse to run if the reference arm and a test arm resolve to the same alignment
parameter. See §7.

## 4. Input data — verified properties

`artefacts/20260724_live_run_2227/wav/` (git-ignored, local only, NFR-021 — real third-party
callsigns; never commit derived files containing callsigns).

Verified 2026-07-25:

- 2,827 files, `YYMMDD_HHMMSS.wav`, spanning 2026-07-24 20:28:00 → 2026-07-25 08:18:15 UTC.
- Every file sampled: **mono, 12 000 Hz, 16-bit, exactly 180 000 frames (15.000 s)**.
- Inter-file gaps: 2,812 × 15 s (contiguous), 13 × 30 s (one missing cycle), 1 × 45 s (two
  missing). **99.5% contiguous.**

This is WSJT-X's own capture, independent of OpenWSFZ's capture path, and it is grid-aligned to
true UTC. Contiguity is what makes re-windowing at arbitrary offsets possible.

## 5. Experimental design

The core design decision: **both arms use the same decoder (`Ft8Decoder`) on the same audio, and
differ only in where the window boundary is cut.** This removes the decoder-implementation
confound entirely — any recall delta is attributable to alignment and nothing else.

### 5.1 Segmentation and re-windowing

1. Group WAVs into **contiguous segments** (consecutive files exactly 15 s apart). Gaps break
   segments; never re-window across a gap. Expect ~15 segments.
2. Concatenate each segment's PCM into one sample array.
3. For an offset δ (seconds), cut windows at sample index `round(δ × 12000) + k × 180000`, each
   exactly 180 000 samples. Discard any partial window at either end.
4. Label each window with the UTC time of its first sample: `segment_start + δ + 15k`.

**Mandatory self-test:** at δ = 0 the re-windowed output must reproduce the original files
**sample-for-sample**. Assert this before any decoding. It is the cheapest available guard against
concatenation and off-by-one errors.

### 5.2 Arms

| Arm | Offsets δ | Purpose |
|---|---|---|
| **A — reference** | 0 | Ground truth. Perfect grid alignment. Denominator for all recall figures, and the source of the *true* DT baseline for these signals. |
| **S — sweep** | non-uniform grid, see below (27 points, δ=0 shared with A) | **Primary deliverable.** Produces recall(δ). |
| **S-wide** | −4.0, +4.0 | Confirms the curve has bottomed out rather than being truncated by the sweep range. Two points only — Phase 0 showed recall is already 0.0000 by δ=+3.0, so this arm no longer warrants four. |
| **N — negative controls** | see §7 | Proves the harness can detect an alignment effect at all. **Mandatory; results are void without it.** |

**Sweep grid (amended 2026-07-25).** The original uniform 0.25 s grid put only ~4 points across a
transition that Phase 0 showed collapses 92% within 1 s — inadequate, because deliverable #5's
number sits *on* that transition. Resolution now follows where the structure is, per §2.5 item 9:

| region | δ range | step | points |
|---|---|---|---|
| negative cliff (predicted) | −2.50 … −1.00 | 0.125 | 13 |
| flat / plateau | −0.50 … +2.00 | 0.50 | 6 |
| positive cliff (measured 2.0→3.0) | +2.25 … +3.25 | 0.125 | 9 |
| bottomed-out shoulders | −3.00, +3.50 | — | 2 |

Total 27 points (δ=0 falls on the plateau grid and is shared with arm A). Refine further only if a
cliff proves sharper than 0.125 s resolution can resolve.

Range rationale: an FT8 transmission occupies 12.64 s of the 15 s cycle and, per §2.5 item 6, sits
at DT +0.80; ft8_lib's time search is bounded near ±2.5 s. The tolerance band is therefore centred
near δ=+0.8, not δ=0, and the interesting structure lies in roughly −2.5 … +3.5.

### 5.3 Recall metric — paired, within-cycle

Band conditions vary enormously across the session (reference decode counts per 30 min range from
33 to 2,653). **Absolute counts must never be compared across time.** Use a paired design:

For cycle *k* and offset δ:

```
recall_δ(k) = |decodes(window_δ,k) ∩ ref(k)| / |ref(k)|
```

where `ref(k)` is arm A's decode set for cycle *k*. Message identity is `(message text)` matched
within the cycle, deduplicated; audio frequency is recorded but not required to match, since a
timing shift does not move a signal in frequency.

Report the median and IQR of `recall_δ(k)` over cycles, not a pooled ratio — pooling would let
high-activity cycles dominate.

Cycles with `|ref(k)| < 5` are excluded (insufficient signal to estimate a rate). Record how many
cycles this excludes.

Messages leaking in from cycle *k+1* as δ grows are simply absent from the numerator; that is
correct and needs no special handling.

## 6. Mapping the curve back to the live run

Once recall(δ) exists:

1. Take the live run's per-cycle DT from `ALL.TXT`.
2. Take arm A's own per-cycle DT distribution as the zero-alignment baseline for these same
   signals — **do not assume real stations transmit at DT = 0**; measure it.
3. Alignment error per cycle: **`δ_live(k) ≈ DT_reference(k) − DT_live(k)`**.

   *Corrected 2026-07-25 — this step previously read `DT_live − DT_reference`, which has the sign
   backwards and would have mapped every live cycle onto the wrong half of the curve.* Phase 0
   settles it empirically (§2.5 item 7): the δ=2.0 arm has DT_ref=+0.80 and DT_obs=−1.20, so
   `DT_ref − DT_obs = +2.00 = δ`, whereas `DT_obs − DT_ref` gives −2.00. Because the curve is
   asymmetric (§2.5 item 9), this sign error would not merely have flipped a label — it would have
   assigned the live run's worst excursions to the tolerant side and concluded misalignment was
   nearly free.
4. Map through recall(δ) to get the predicted recall cost of the live alignment, per cycle and
   session-wide.

   Worked example of what this implies, using §2's live medians and the +0.80 baseline — **to be
   replaced with real figures once recall(δ) exists, not quoted as a result**: the 5.0 h bucket at
   median DT +2.90 maps to δ_live ≈ −2.10, past the predicted negative cliff (near-total recall
   loss); the 1.5 h and 9.5 h buckets at median DT −1.10/−1.30 map to δ_live ≈ +1.90/+2.10, worth
   roughly 8%. If that pattern survives measurement, the live cost is dominated by a minority of
   negative-δ excursions rather than spread evenly across the session — which is a materially
   different conclusion for §1's question than "±1–2 s of oscillation" suggests on its face.

This decomposition is deliberate: it separates a robustly measurable quantity (the curve) from a
separately-derived input (the live alignment error), instead of attempting one fragile end-to-end
replay that would require sample-level registration between OpenWSFZ's capture and WSJT-X's — two
different captures of the same audio at slightly different rates. **Do not attempt that
registration.**

## 7. Controls — mandatory, not optional

Two of the three invalidated approaches in §3 failed because nothing would have caught a
degenerate comparison. These controls exist to catch exactly that:

1. **Sensitivity control.** δ = **+3.0 s** must show a materially lower median recall than δ = 0.
   If it does not, the harness is not sensitive to alignment and **every result in the study is
   void** — stop and diagnose.

   *Amended 2026-07-25.* This originally specified δ=+2.0, which contradicted §5.2's own rationale:
   2.0 s falls *inside* ft8_lib's ±2.5 s time search, so the decoder is expected to absorb most of
   it. A control that proves the harness can detect misalignment must probe **outside** the
   decoder's compensation range. Phase 0 measured 0.9200 at δ=2.0 and 0.0769 at δ=3.0 — the
   original probe point would have voided a sound harness. The 0.92 figure is not a control
   failure; it is a headline result (the decoder absorbs 2 s of misalignment for ~8% recall), and
   belongs in the recall(δ) write-up as such.
2. **Shuffled-pairing control.** Score cycle *k*'s δ=0 decodes against reference set `ref(k+7)`.
   Recall must collapse to ≈ 0. If it does not, the matcher is broken.
3. **Provenance record.** Every output file records: source WAV directory, segment index, δ,
   harness git SHA, and decoder parameter values.

   **Guard (amended 2026-07-25).** This originally said "the harness refuses to run if the
   reference and a test arm resolve to identical δ", which contradicts §5.2's "δ=0 shared with A"
   and is unimplementable as written. The real hazard — the one that voided §3's `ALL.TXT`
   comparison — is scoring a decode set against *itself* and reporting the result as recall. So:
   the harness must refuse to score unless the reference and test arms resolve to **distinct
   provenance** (different manifest paths and different recorded δ), with exactly one whitelisted
   exception: the **δ=0-vs-δ=0 identity anchor**, which must be run, must be labelled as the
   identity case, and must return exactly 1.0000. Any *other* same-δ pairing is a hard refusal.
4. **Determinism check — two parts.** `Ft8Decoder`'s iterative-subtraction path and
   `hashTableRejectCount` are process-lifetime cumulative (visible in the live logs).
   - **(a) Sequence-position invariance** — decode N ≥ 3 identical copies of one WAV in a single
     process; all copies must yield identical decode content. **Done in Phase 0, passed.**
   - **(b) Cross-input invariance** — *added 2026-07-25.* (a) only varies position among
     *identical* inputs, but each sweep arm decodes a different sequence of *different* windows, so
     the arms' cumulative-state trajectories diverge. Decode arm A's cycle set once in forward
     order and once in reverse, and assert the per-cycle decode sets are identical. ~50 decodes.
     **Must pass before Phase 1's results are trusted.** If it fails, use a fresh decoder instance
     per window and re-assert.

## 8. Reuse — build on the D-001 harness

`qa/rr-study/d001-param-sweep-2026-07-22/` already does most of this and should be the starting
point rather than a fresh build:

- Drives the real production `Ft8Decoder` in-process through its **public API only**.
- Reads 12 kHz mono WAVs; `ExpectedSamples = 180_000` is already its hard contract.
- Writes WSJT-X-`ALL.TXT`-format output byte-compatible with `src/OpenWSFZ.Daemon/AllTxtWriter.cs`,
  so the existing Python scorers ingest it unchanged.
- Already has `--limit`, `--index-start/--index-end`, and sharding.
- Documents its own determinism argument (decode is pure w.r.t. PCM + params).

**The one genuinely new capability is §5.1's segment concatenation and re-windowing.** The sweep
axis changes from decode parameters to alignment offset; the decode parameters stay pinned at the
shipped baseline throughout.

## 9. Phasing and cost

| Phase | Scope | Decodes | Gate |
|---|---|---|---|
| **0** | Re-windowing self-test (§5.1) + controls (§7) | 129 | **PASSED and ratified 2026-07-25** (§2.5, §14). |
| **0b** | Control §7.4(b) cross-input determinism + the §7.3 guard, both built into the Phase 1 driver | ~50 | Must pass before Phase 1's results are trusted. |
| **1a** | **Asymmetry probe.** 25 cycles × δ ∈ {−1.00, −1.375, −1.75, −2.125, −2.50} | ~125 | Locate the negative cliff. Confirms or kills §2.5 item 9 *before* the full grid is spent. |
| **1b** | 400 cycles stratified across the session × 27 offsets (§5.2 grid) | ~10 800 | Curve shape. Re-grid from 1a's measured cliff location if it lands outside −2.5…−1.0. |
| **2** | Full 2,827 cycles × 27 offsets, only if 1b's curve needs tightening | ~76 000 | — |

**Phase 1a runs first, on segment 0's same 25 cycles as Phase 0** — so it is directly comparable to
the positive-δ figures already in hand, and costs ~1% of the full sweep. Its purpose is to avoid
spending the Phase 1b budget on a grid built from an untested model. If the negative cliff lands
outside the predicted −2.5…−1.0 window, amend §5.2's grid before running 1b.

Phase 1b stratification: sample evenly across the 11h51m span, restricted to cycles with
`|ref(k)| ≥ 5`, so both good and poor propagation periods are represented. Also widen the arm-A DT
baseline (§2.5 item 6) across the full span at this point — segment 0's +0.80 may not hold
session-wide, and every δ→live mapping depends on it.

Precedent for feasibility: the D-001 sweep ran ~106 000 offline decodes.

## 10. Deliverables

1. `qa/cycleframer-alignment-replay/report.md` — per NFR-024/HK-001 section conventions.
2. **The recall(δ) curve** with median and IQR per offset — the study's reason for existing.
3. The DT baseline distribution from arm A.
4. Predicted recall cost of the 9.5 session's observed alignment excursions (§6).
5. A recommended **maximum acceptable alignment error in seconds**, derived from the curve, for
   use as a `tasks.md` 10.8 acceptance bound and as a cap on correction magnitude. **This must be
   stated as an asymmetric interval (`δ_min … δ_max`), never as `±X`** — per §2.5 item 9 the
   tolerance band is centred near δ=+0.8 with roughly half as much headroom on the negative side.
   A symmetric bound would be simultaneously too loose on one side and too tight on the other.
6. Raw per-cycle scoring data, callsign-free where possible (NFR-021 — derived artefacts
   containing real callsigns are git-ignored, local only).

## 11. What this settles, and what it does not

**Settles:** the recall cost per second of alignment error, measured on real off-air audio with
the production decoder; whether the alignment excursions the live runs exhibit are material; and a
quantitative bound for correction magnitude.

**Does not settle:** the absolute size of D-001's recall gap. That needs OpenWSFZ measured against
**WSJT-X's own decodes of the same audio**, and no WSJT-X `ALL.TXT` was preserved for this session
— only its WAVs. This study measures the *alignment component* only.

> **Open request to the Captain:** if WSJT-X's `ALL.TXT` (or its `wsjtx_log.adi` / decode history)
> from the night of 2026-07-24 still exists on the shack machine, preserving it would let this
> same harness size D-001's absolute gap on this session's audio at near-zero extra cost. The
> sibling directory `artefacts/20260723_live_run_2223/` has a `wsjtx/` subdirectory, so this data
> has been captured before.

## 12. Notes for the implementing session

- **HK-009:** this machine's Python `stdout` is cp1252. Write ASCII-only console output from the
  first draft (`->`, `--`, `delta=`), or reconfigure `sys.stdout` up front.
- **NFR-021:** decoded output contains real third-party callsigns. Keep all derived decode files
  git-ignored and local, exactly as `artefacts/` is.
- **HK-006:** no "ready" claim without `python3 tools/pre_merge_check.py`.
- This study is diagnostic. It does not modify `CycleFramer` and does not depend on whether
  `tasks.md` 10.1–10.4 land; it measures the audio, not the framer.

## 13. Cross-references

- `qa/cycleframer-code-review/2026-07-25-decision9-review-and-rateclock-escalation.md` — the QA
  escalation that opened this thread.
- `openspec/changes/fix-cycle-boundary-clock-drift/design.md` Decisions 8 and 9; `tasks.md` §10
  (10.4 blocked, 10.6 open, 10.8 live gate held pending this study).
- `qa/endurance/2026-07-25-40m-band-9.5-fail/report.md` — the session whose artefacts this study
  consumes; its own "Third" recommendation asked for exactly this analysis.
- `qa/rr-study/d001-param-sweep-2026-07-22/` — the harness to extend.
- `qa/cycleframer-alignment-replay/2026-07-25-phase0-findings.md` — the QA session's Phase 0
  report, whose sensitivity-control escalation this revision resolves (§14).

## 14. Architect ruling on Phase 0's escalation (2026-07-25)

QA's Phase 0 report declined to self-certify the §7.1 sensitivity control (0.9200 at δ=2.0 vs
1.0000 at δ=0 is not obviously "materially lower") and routed the judgment call upward rather than
deciding it in-session. That was the correct call, and the escalation is resolved as follows.

**Ruling: the control passes, and the fault was in this specification, not the harness.** §7.1's
probe point contradicted §5.2's own stated rationale by sitting inside the decoder's ±2.5 s search
range. §7.1 is amended to δ=+3.0 above. All four Phase 0 controls are ratified; Phase 1 is
authorised subject to §9's revised phasing.

The Architect independently reproduced all five recall figures and the shuffle control from the
committed harness and local `_work/` outputs before ruling — not accepted on report alone.

**Four specification defects were found in the course of this ruling, all pre-existing, all mine:**

| § | Defect | Status |
|---|---|---|
| 7.1 | Sensitivity probe at δ=2.0 sits inside the decoder's own search bound; would have voided a sound harness | Fixed — probe moved to δ=+3.0 |
| 7.3 | Same-δ refusal guard contradicts §5.2's "δ=0 shared with A"; unimplementable as written | Fixed — reframed as provenance-distinctness with a whitelisted identity anchor |
| 7.4 | Determinism control tests position among *identical* inputs only; the sweep's actual hazard is cumulative state across *different* inputs | Fixed — part (b) added, ~50 decodes, Phase 0b |
| 6.3 | **Alignment-error sign is inverted** (`DT_live − DT_ref` should be `DT_ref − DT_live`) | Fixed — corrected and confirmed empirically against the δ=2.0 arm |

The §6.3 sign error is the serious one. Combined with the asymmetric tolerance band established in
§2.5 item 9, it would have mapped the live run's worst alignment excursions onto the *tolerant*
half of the curve and produced a confident, wrong conclusion that misalignment costs almost
nothing — the same class of failure as §3's three invalidated approaches, and one that no control
in §7 would have caught. Recorded here rather than silently patched, per §3's standing rule.

**Two items QA correctly listed as not-yet-built remain open** and are now assigned: the Phase 1
orchestrating driver, and the §7.3 guard (whose specified behaviour changed above — build against
the amended wording, not the original). Both land in Phase 0b.

**On QA's own recommendation:** its proposal to treat the cliff finding as passing the control's
*intent* while flagging the probe point as mis-placed is accepted essentially verbatim. Its
"ruled out repeated-message contamination" check (585 reference messages, zero verbatim adjacent-cycle
recurrences) was unprompted, is exactly the right instinct for a text-matched metric, and closes a
hole this specification never asked about.
