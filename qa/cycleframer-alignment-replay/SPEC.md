# Offline alignment-replay study — how much recall does cycle-boundary misalignment cost?

**Author:** Architect session, 2026-07-25. **Status:** Phases 0, 0b and 1a complete and ratified
(§2.5, §14, §15). **Phase 1b re-scoped to confirm-and-cut** (11 offsets, ≈7 200 decodes) against
§5.2's falsification criterion — authorised, not yet run. §2.5 item 9 is **retracted**; item 10
supersedes it.
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

9. ~~**Therefore the tolerance band is asymmetric about δ=0 and its centre is δ ≈ +0.8.**~~
   **RETRACTED 2026-07-25 — falsified by Phase 1a and superseded by item 10.** This item predicted
   the negative cliff near δ ≈ −1.7 ("roughly half the positive side's tolerance"), reasoning from
   an assumed symmetric ±2.5 s decoder search bound and from symbol-clipping headroom. Phase 1a
   measured the negative cliff at δ ≈ −2.3…−2.4 and recall still 0.833 at δ=−2.125. Both the
   predicted *number* and the predicted *mechanism* were wrong. The claim that the band is "centred
   near δ=+0.8" is retracted with it. Recorded rather than deleted, per §3's standing rule.

10. **The decoder's time search is `DT_obs ∈ [−1.60, +3.12] s` — hardcoded and asymmetric — and
    this alone explains the entire recall(δ) curve.** *Added 2026-07-25 (Architect, reviewing
    Phase 1a).* Read directly from
    `native/ft8_lib_build/patched/ft8/decode.c:279`:

    ```c
    for (candidate.time_offset = -10; candidate.time_offset < 20; ++candidate.time_offset)
    ```

    30 blocks × 0.16 s/block, plus sub-block reach from `time_osr = 2` (`ft8_shim.c:470`,
    `K_TIME_OSR 2`). **The "bounded near ±2.5 s" figure previously asserted in §5.2 and in the
    retracted item 9 is not what the code does** and every prediction derived from it inherits
    the error.

    Combined with item 7's `DT_obs = DT_true − δ`, this yields a **zero-free-parameter model**:

    > `recall(δ) = P( DT_true ∈ [δ − 1.60, δ + 3.12] )` over the reference decode population.

    Tested against all 12 measured δ points (Phase 0 + Phase 1a), with the bound read from source
    and `DT_true` read from arm A's own `ALL.TXT` — nothing fitted:

    | δ | measured | predicted | resid |
    |---|---|---|---|
    | −2.500 | 0.115 | 0.120 | −0.005 |
    | −2.375 | 0.423 | 0.188 | +0.236 |
    | −2.250 | 0.769 | 0.615 | +0.154 |
    | −2.125 | 0.833 | 0.783 | +0.051 |
    | −1.750 | 0.885 | 0.920 | −0.035 |
    | −1.375 | 0.909 | 0.958 | −0.049 |
    | −1.000 | 0.957 | 0.966 | −0.009 |
    | +2.000 | 0.920 | 0.962 | −0.042 |
    | +3.000 | 0.077 | 0.080 | −0.003 |
    | +5.000 | 0.000 | 0.000 | 0.000 |
    | +7.500 | 0.000 | 0.000 | 0.000 |

    **RMS error 0.085.** The previously assumed symmetric ±2.5 s bound scores **0.472** on the
    same data — falsified, not marginal. The two large residuals sit in the steepest part of the
    cliff, where the 0.08 s sub-block quantum moves the prediction sharply; both point the same
    way (the decoder slightly out-reaches the hard block bound), consistent with `time_sub`
    interpolation.

    **Predicted cliff centres: δ = DT_med − 3.12 and δ = DT_med + 1.60**, i.e. **−2.32 and +2.40**
    at segment 0's DT_med = +0.80. Phase 1a measured the negative one at −2.3…−2.4.

    Three consequences that matter downstream:

    - **The gradual negative shoulder is DT spread, not symbol loss.** Phase 1a's own hypothesis
      (per-cycle DT spread smears a per-station step function into an aggregate slope) is correct
      in form; the step is each station reaching the *search bound* at a different δ, not losing
      tail symbols. Same smearing, different cause.
    - **The near-symmetry of the two cliffs in δ is a coincidence of this signal population.** The
      decoder's own asymmetry (window centred at DT_obs +0.76) very nearly cancels the population's
      DT offset (+0.80), leaving a δ-frame band centred at ≈ +0.1. Change the DT population and the
      band becomes asymmetric in δ again. **The tolerance interval therefore tracks `DT_true` 1:1
      and is not a fixed property of the decoder.** This is why §9's session-wide DT baseline is
      load-bearing, and why deliverable #5 must still be stated asymmetrically — for this reason,
      not the retracted item 9's reason.
    - **Recall is a population statistic, not a per-signal one.** Every station is in or out on its
      own DT; the curve's shape is the DT CDF, so the median understates the tail (see §5.3).

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

### 4.1 WSJT-X decode log — RECOVERED 2026-07-25

§11's open request is **answered on this session's own audio.** The Captain recovered
`artefacts/20260724_live_run_2227/wsjt-x ALL.TXT`. Verified 2026-07-25:

| | `wsjt-x ALL.TXT` | `ALL.TXT` (OpenWSFZ) |
|---|---|---|
| lines | 82,943 | 20,092 |
| Rx/FT8 cycles | **2,827 — every WAV** | 1,789 distinct labels |
| first → last | `260724_202800` → `260725_081815` | `260724_202800` → `260725_081705` |

The WSJT-X log's cycle set is **exactly the 2,827 WAVs**, so it is complete for this session with
no gaps to reconcile. It is unambiguously a different decoder, not a copy: 4.13× the decode count,
and on the first cycle alone it reports SNR 24 / DT +0.2 where OpenWSFZ reports SNR 4 / DT +0.8.
**This is therefore not §3's invalidated self-comparison.**

**Consequence: the alignment component and the absolute gap are now measurable on the same audio,
the same session, and the same signal population.** That removes the `DT_med` transfer problem
that would have applied to sizing the gap on the 0723 archive (§11) — the recall(δ) curve's own
`DT_med` is the right one to use, by construction. `artefacts/20260723_live_run_2223/` remains a
valid independent second session, but is no longer the primary route.

**Caveats that still bind (do not skip these):**

- **Only 441 of OpenWSFZ's 1,789 labels sit on the 15 s UTC grid**, so 1,348 cycles have no
  same-timestamp counterpart in the WSJT-X log. Naive timestamp-keyed joining silently drops 75%
  of the session and **selects on the cumulative-correction residue**, which is not a random
  subset. Reconstruct the true UTC cycle from `cycleStart` and the daemon log's correction sum.
- **An on-grid label does not mean the content was aligned.** §2 item 2 established that the label
  slide does *not* track content position; the two are decoupled. Any argument of the form "these
  cycles were grid-aligned, so alignment error ≈ 0 there" is invalid. *(Recorded because the
  Architect made exactly this error on first inspection of the recovered file.)*
- The raw 82,943-vs-20,092 ratio is **not** a recall figure — §3's trap. Use §5.3's paired
  within-cycle metric.

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

**Sweep grid — second amendment, 2026-07-25 (supersedes the first).** The first amendment sized a
27-point grid around §2.5 item 9's predicted −1.7 negative cliff. Item 9 is now retracted and item
10's search-bound model reproduces the whole curve with no free parameters, so tracing 27 points
empirically buys much less than it did. Phase 1b is re-scoped to **confirm-and-cut** (Captain's
decision, 2026-07-25): probe where the model makes its sharpest and least-tested predictions, and
if it survives, *derive* the curve from the session-wide DT distribution instead of tracing it.

| region | δ points | n | why |
|---|---|---|---|
| positive cliff | +2.00, +2.25, +2.50, +2.75, +3.00 | 5 | **The model's strongest untested prediction.** The positive side has exactly two measurements ever (+2.0, +3.0) and the predicted centre (+2.40) has never been probed. Highest information per decode. |
| negative cliff | −2.00, −2.25, −2.50, −2.75 | 4 | Confirm Phase 1a's 25-cycle result at 400 cycles, and bracket the bottom — the previous grid stopped at −2.50, inside the drop. |
| plateau | −1.00 | 1 | One genuine (non-anchor) plateau point at 400 cycles. |
| bottomed-out shoulder | +3.50 | 1 | Confirms the positive side has floored. |
| identity anchor | 0.00 | — | Arm A; §7.3 whitelisted. Not evidence. |

**11 non-anchor points** (down from 27). Cost: 400 × 12 ≈ **4 800 decodes**, plus extending the
arm-A DT baseline to the full 2 827 cycles (≈2 427 beyond the 400 already decoded at δ=0) —
**≈7 200 total, versus ≈13 200 for the full grid.**

**Falsification criterion — state the verdict before looking (mandatory).** The model passes iff,
after re-deriving cliff centres from the *session-wide* DT median:

1. `|measured − predicted|` ≤ **0.10** at every point outside the two cliff transitions, and
   ≤ **0.25** at points inside them (where the 0.08 s sub-block quantum dominates); **and**
2. the measured 50 % crossing of the positive cliff falls within **±0.15 s** of
   `DT_med + 1.60`; **and**
3. the negative 50 % crossing falls within ±0.15 s of `DT_med − 3.12`.

**If any of the three fails, fall back to the full 27-point grid** (previous amendment's table,
with the negative dense region shifted to −2.75 … −1.75) before quoting deliverable #2 or #5. A
cut budget is only legitimate while the model that justifies it is still standing.

Range rationale (corrected): an FT8 transmission occupies 12.64 s of the 15 s cycle and, per §2.5
item 6, sits at DT +0.80; the decoder's time search is `DT_obs ∈ [−1.60, +3.12]` per §2.5 item 10.
The tolerance band in δ is therefore `[DT_med − 3.12, DT_med + 1.60]` ≈ **−2.32 … +2.40** for this
population — centred near δ ≈ +0.1, *not* +0.8 — and the interesting structure lies in −3.0 … +3.5.

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

**Also report p10 and the count of zero-recall cycles (added 2026-07-25).** Phase 1a's data has a
left tail the median hides: `min` recall is 0.000 at *every* negative δ probed, including δ=−1.0
where the median is 0.957, and the mean trails the median throughout (0.905 vs 0.957 at −1.0).
Some cycles fail completely well inside the tolerance band. Per §2.5 item 10 this is expected —
recall is a population statistic over each cycle's own DT spread — but it means **deliverable #5's
bound must be quoted against a stated percentile, never the median alone**, or it will be too loose
for the cycles that matter most.

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
   asymmetric (~~§2.5 item 9~~ → **§2.5 item 10**, which retracts item 9 but confirms the
   asymmetry — in the opposite direction, with *more* headroom on the negative side), this sign
   error would not merely have flipped a label — it would have assigned the live run's worst
   excursions to the tolerant side and concluded misalignment was nearly free. **The correction
   stands and is now doubly load-bearing**: with the true interval −2.32 … +2.40, the sign error
   would still have mapped negative-δ excursions to positive δ and vice versa.

   *Frame note, 2026-07-25 (Architect).* "More headroom on the negative side" above is stated in the
   **DT-relative** frame, where it is emphatically true — at ±2.3 s from `DT_med`, population recall
   is 0.966 negative vs 0.055 positive. **This step's output `δ_live(k)` is in the absolute δ frame**,
   where 0724's `DT_med` = +0.80 makes the positive side the wider one (`[−2.32, +2.40]`). Compare
   `δ_live` against absolute-frame intervals only. See §10 item 5 and
   `2026-07-25-deliverable-5-alignment-bound.md` §0.
4. Map through recall(δ) to get the predicted recall cost of the live alignment, per cycle and
   session-wide.

   Worked example — **corrected 2026-07-25**, using §2's live medians, the +0.80 baseline, and the
   *measured* curve rather than the retracted item 9's prediction. Still **to be replaced with real
   per-cycle figures once recall(δ) is final, not quoted as a result**:

   | bucket | median DT_live | δ_live | recall | source |
   |---|---|---|---|---|
   | 5.0 h | +2.90 | −2.10 | **≈0.83** | measured (Phase 1a, δ=−2.125) |
   | 1.5 h | −1.10 | +1.90 | ≈0.92 | measured (Phase 0, δ=+2.00) |
   | 9.5 h | −1.30 | +2.10 | ≈0.90 | interpolated |

   *The previous version of this example called the 5.0 h bucket "past the predicted negative cliff
   (near-total recall loss)". That rested on the retracted −1.7 cliff. The real cliff is at −2.32,
   so δ_live = −2.10 sits on the shoulder, not past it, and the measured cost is ~17% — not ~100%.*
   **This materially changes the provisional answer to §1**: on bucket medians, the 9.5 session's
   alignment cost the worst 30-minute window roughly a sixth of its decodes, not nearly all of
   them. Bucket medians average over per-cycle excursions that may be far worse (see §5.3's left
   tail), so this is a floor on the damage, not a settled figure — but it no longer supports the
   framing that misalignment was catastrophic session-wide.

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
   2.0 s falls *inside* the decoder's time search, so the decoder is expected to absorb most of
   it. A control that proves the harness can detect misalignment must probe **outside** the
   decoder's compensation range. (The ±2.5 s figure cited when this amendment was first written is
   itself wrong — see §2.5 item 10; the real bound is `DT_obs ∈ [−1.60, +3.12]`, which puts the
   positive-δ edge at +2.40 and so leaves this amendment's conclusion intact: δ=+3.0 is outside it,
   δ=+2.0 is inside.) Phase 0 measured 0.9200 at δ=2.0 and 0.0769 at δ=3.0 — the
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
     **Must pass before Phase 1's results are trusted.** ~~If it fails, use a fresh decoder instance
     per window and re-assert.~~

     **Outcome, 2026-07-25 — the control FAILS as specified, and the prescribed remedy does not
     work.** Phase 0b measured 14/25 cycles mismatched. Root cause: `ft8_shim.c:627`'s
     `g_session_hash_table` is a **native process-global**, deliberately session-scoped, so a
     hashed callsign renders `<...>` or `<PD00DOG>` depending purely on which windows were decoded
     earlier in the same process. The prescribed fix (fresh managed `Ft8Decoder` per window) was
     built and tried — identical 14/25 mismatch, because the state is in native static memory the
     managed wrapper never touches. Only a fresh *process* would clear it.

     **Resolution: narrow the metric, and say so.** The study proceeds by canonicalizing
     bracketed hash tokens (`<[^>]*>` → `<HASH>`) before matching, via `score_recall.py`'s
     `normalize_hash_tokens()` — 0/25 mismatches after. Re-scoring Phase 0's ratified δ ∈ {2.0,
     3.0, 5.0, 7.5} figures with normalization on changed no median and shifted IQR/mean by
     <0.002, so §2.5's established facts stand. **This is a deliberate reduction in the metric's
     discriminating power, not a passing control**, and it carries two mandatory guards:

     - **(b-i) Collision assertion.** Normalization can merge two *genuinely distinct* messages
       (`<X> CALL −14` and `<Y> CALL −14` collapse to the same string), which would *inflate*
       recall. Measured on Phase 0's reference: 7.18 % of rows carry a bracket token and **0
       within-cycle merges occurred across all 25 cycles** — safe there, but 7.18 % is high enough
       that it will not stay zero at Phase 1b's 400 cycles. `score_recall.py` **must count merges
       per run and fail loudly if the count is nonzero.** Do not assume.
     - **(b-ii) Reject-count recording.** This section names `hashTableRejectCount` as the hazard,
       and a hash-driven *reject* yields a genuinely missing decode — which normalization neither
       fixes nor reveals. Phase 0b's "never a missing or extra decode" observation covers 25 cycles
       under one perturbation; Phase 1b diverges the arms much harder. **Record
       `hashTableRejectCount` per arm in Phase 1b** and compare across arms; a systematic
       difference is a confound signature.

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

**Added 2026-07-25/26:** `measure_dt_alignment.py` (this directory) — a 2×2 decoder×audio
instrument (our decoder/our audio, our decoder/reference audio, reference decoder/reference audio,
all live and offline combinations as available) that separates a capture-chain fault from a
decoder fault by decomposing an absolute DT gap into its two additive components. It resolved the
D-001 capture-vs-decoder question in one run where decode-count comparison alone could not resolve
it at all (see `2026-07-25-2300-alignment-root-cause.md`). General-purpose, not specific to this
study; reach for it before rebuilding an ad hoc alignment probe. Companion:
`measure_capture_alignment.py` (waveform, full-range FFT cross-correlation — use a search window
wide enough for the true lag range, not a narrow default; see the same document §2.1 for the
failure mode of getting that wrong).

## 9. Phasing and cost

| Phase | Scope | Decodes | Gate |
|---|---|---|---|
| **0** | Re-windowing self-test (§5.1) + controls (§7) | 129 | **PASSED and ratified 2026-07-25** (§2.5, §14). |
| **0b** | Control §7.4(b) cross-input determinism + the §7.3 guard, both built into the Phase 1 driver | ~50 | **RUN 2026-07-25.** §7.3 guard passed. §7.4(b) **failed and was resolved by narrowing the metric** — see §7.4(b) and §15; guards (b-i)/(b-ii) are outstanding and land in 1b. |
| **1a** | **Asymmetry probe.** 25 cycles × δ ∈ {−1.00, −1.375, −1.75, −2.125, −2.50}, + refinement at −2.25/−2.375 | 175 | **PASSED 2026-07-25.** Falsified §2.5 item 9; negative cliff at −2.3…−2.4, not −1.7. Superseded by item 10's model. |
| **1b** | **Confirm-and-cut.** 400 cycles stratified × 11 non-anchor offsets (§5.2 second amendment) + arm-A DT baseline across all 2 827 cycles | ~7 200 | §5.2's three-part falsification criterion. **If any part fails, fall back to the full 27-point grid before quoting deliverables #2/#5.** |
| **2** | Full 2,827 cycles × full grid, only if 1b's curve needs tightening | ~76 000 | — |

**Phase 1a ran first, on segment 0's same 25 cycles as Phase 0** — directly comparable to the
positive-δ figures already in hand, at ~1.6% of the full sweep. Its purpose was to avoid spending
the Phase 1b budget on a grid built from an untested model, and it did exactly that: the model was
untrue, and the retracted grid would have put 13 dense points in the wrong place while stopping
short of the real cliff bottom. **This is the phasing working as designed — record it as such.**

Phase 1b stratification: sample evenly across the 11h51m span, restricted to cycles with
`|ref(k)| ≥ 5`, so both good and poor propagation periods are represented.

**The arm-A DT baseline is now load-bearing, not a side deliverable.** Per §2.5 item 10 the
tolerance interval is `[DT_med − 3.12, DT_med + 1.60]` — it moves 1:1 with the signal population's
DT, so segment 0's +0.80 must be widened across the full span *before* deliverable #5 is quoted,
and the falsification criterion in §5.2 is evaluated against the session-wide median, not
segment 0's. Under confirm-and-cut this baseline is the single highest-value measurement in the
phase: if the model holds, the curve is derived from this distribution rather than traced.

Precedent for feasibility: the D-001 sweep ran ~106 000 offline decodes.

## 10. Deliverables

1. `qa/cycleframer-alignment-replay/report.md` — per NFR-024/HK-001 section conventions.
2. **The recall(δ) curve** with median and IQR per offset — the study's reason for existing.
3. The DT baseline distribution from arm A.
4. Predicted recall cost of the 9.5 session's observed alignment excursions (§6).
5. A recommended **maximum acceptable alignment error in seconds**, derived from the curve, for
   use as a `tasks.md` 10.8 acceptance bound and as a cap on correction magnitude. **This must be
   stated as an asymmetric interval (`δ_min … δ_max`), never as `±X`.**

   *Rationale corrected 2026-07-25.* This previously cited §2.5 item 9 ("centred near δ=+0.8, half
   the headroom on the negative side"), which is retracted. The requirement stands, for item 10's
   reason instead: the decoder's search window is itself asymmetric (`DT_obs ∈ [−1.60, +3.12]`), so
   **in the DT-relative frame** the interval is `[DT_med − 3.12, DT_med + 1.60]` — wider on the
   negative side, the opposite of what item 9 claimed. A symmetric bound would be simultaneously too
   loose on one side and too tight on the other, in the reverse direction to the one previously
   documented.

   **Frame discipline, added 2026-07-25 (Architect), deliverable #5 final.** That asymmetry
   statement is true only in the DT-relative frame. **In the absolute δ frame — the frame this
   study measures, the frame `δ_live(k) = DT_ref(k) − DT_live(k)` (§6.3 step 3) produces, and the
   frame 10.8(d) consumes — `DT_med` = +0.80 shifts the interval to `[−2.32, +2.40]`, which is wider
   on the *positive* side.** Both readings are correct; stating either without naming its frame is
   what produced the contradiction between this paragraph and the value quoted below it.
   **Quote all intervals in the absolute δ frame. Name the frame whenever describing the asymmetry
   direction.**

   Three further constraints on how the number is stated:

   - **Quote it against a stated percentile, not the median** (§5.3's left tail).
   - **State the `DT_med` it was derived from.** The interval tracks the signal population 1:1; it
     is not a fixed property of the decoder and does not transfer to another band or session
     without re-deriving.
   - ~~Provisional value from the data in hand, pending Phase 1b: **δ ∈ [−1.6, +2.0] for ≥92% median
     recall**, with hard cliff centres at −2.32 / +2.40, at `DT_med` = +0.80.~~
     **FINAL, from Phase 1b (2026-07-25): `δ ∈ [DT_p95 − 3.12, DT_p05 + 1.60]`, instantiated on the
     0724 session as `δ ∈ [−1.62, +2.00]` at `DT_med` = +0.80** (`DT_p05`/`DT_p95` = +0.40/+1.50),
     for **0.90 per-cycle median / 0.81 p10** recall at the edges; hard cliff centres −2.32 / +2.40
     confirmed by measurement (−2.345 / +2.434). The percentile form is preferred over
     `DT_med ± margin` because it adapts to the DT distribution's *shape*, not only its median —
     0724's spread is unusually tight (IQR 0.10 s), so median-only margins would silently
     over-estimate headroom on a broader population. Full derivation, edge costs, transfer
     conditions and the corrections this ruling makes to §6.3 and `tasks.md`:
     **`2026-07-25-deliverable-5-alignment-bound.md`.**
6. Raw per-cycle scoring data, callsign-free where possible (NFR-021 — derived artefacts
   containing real callsigns are git-ignored, local only).

## 11. What this settles, and what it does not

**Settles:** the recall cost per second of alignment error, measured on real off-air audio with
the production decoder; whether the alignment excursions the live runs exhibit are material; and a
quantitative bound for correction magnitude.

~~**Does not settle:** the absolute size of D-001's recall gap.~~ **Amended twice on 2026-07-25 —
this caveat is now lifted on this study's own session. See §4.1.**

*First amendment (superseded): the 0724 WSJT-X log was believed lost and `20260723_live_run_2223/`
was identified as a substitute. **Then the Captain recovered
`artefacts/20260724_live_run_2227/wsjt-x ALL.TXT`** — 82,943 lines covering all 2,827 cycles of
this study's own audio. That is strictly better: same session, same signal population, so the
recall(δ) curve's own `DT_med` applies by construction and no cross-session transfer is needed.
Primary route is now 0724; §4.1 has the verification table and caveats.*

`artefacts/20260723_live_run_2223/` remains valuable as an **independent second session** —
different build (`ce13e308` + persistence-gated diff), different night, 7h54m — and is the natural
replication check once 0724's figures exist. Verified 2026-07-25:

| file | content |
|---|---|
| `wsjtx/ALL.TXT` | 50,501 lines, `260723_222345` → `260724_061730` |
| `openwsfz/ALL.TXT` | 31,517 lines, `260723_222330` → `260724_061730` |
| `openwsfz/openswfz-20260723T222314Z.log` | 20 `Cycle boundary resync` + 1,897 `Cycle boundary drift check` lines |
| `wsjtx/wav/` | 1,884 files, mono/12 kHz/16-bit/exactly 180,000 frames, 99.5% contiguous |

The WAVs are **format-identical to §4's 0724 archive**, so `rewindow.py` and the whole Phase 0
harness consume them unmodified. This makes two previously-blocked things executable: `tasks.md`
10.6's DT-offset prediction, and D-001 absolute-gap sizing (`tasks.md` 11.10).

**Three constraints on using it, none optional:**

1. **Keep the recall(δ) curve on the 0724 audio.** Phases 0/0b/1a are three phases deep on
   segment 0 there; rebasing would discard a ratified baseline to buy a comparison better run as
   its own arm. 0723 is a *different session and build* (`ce13e308` + the persistence-gated diff,
   7h54m, 40 m).
2. **0723 needs its own `DT_med`.** Per §2.5 item 10 the tolerance interval is
   `[DT_med − 3.12, DT_med + 1.60]` and moves 1:1 with the signal population. Segment 0's +0.80
   does not transfer.
3. **This is not §3's invalidated comparison** — that was OpenWSFZ against itself. Two different
   decoders is a real comparison. But it *is* two different **captures**, so §6's prohibition on
   sample-level registration still binds: match on per-cycle message sets, never on samples. And
   OpenWSFZ's cycle labels slide off the UTC grid by the cumulative correction (§2 item 1), so
   timestamp-keyed matching breaks by construction — use the daemon log's correction sum to align.
   The raw 50,501-vs-31,517 line ratio is **not** a recall figure.

> ~~**Open request to the Captain:**~~ **CLOSED 2026-07-25 — the Captain recovered the file.**
> `artefacts/20260724_live_run_2227/wsjt-x ALL.TXT`, 82,943 lines, all 2,827 cycles of this
> study's own session. See §4.1. *(An intermediate note here claimed the log was lost and pointed
> at the 0723 archive as a substitute; that is superseded — 0723 is now the replication check, not
> the primary route.)*

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
- `qa/cycleframer-alignment-replay/2026-07-25-phase0b-findings.md`,
  `2026-07-25-phase1a-findings.md` — the QA session's Phase 0b and 1a reports, reviewed in §15.
- `native/ft8_lib_build/patched/ft8/decode.c:279` — the hardcoded time-search bound that §2.5
  item 10 is built on. **Any future re-vendoring or re-patching of ft8_lib must re-check this
  line**; if it changes, every figure in §2.5 item 10, §5.2 and deliverable #5 changes with it.

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

## 15. Architect review of Phase 0b and Phase 1a (2026-07-25)

**Both phases accepted.** All figures in both QA reports were reproduced independently from
`_work/phase1a_summary.csv`, `_work/phase1a_refine_summary.csv` and the committed harness before
ruling — not accepted on report alone. `check_provenance()` and `normalize_hash_tokens()` were read
and confirmed to implement §7.3's amended wording and §7.4(b)'s described fix respectively.

### 15.1 A fifth specification defect, and the model that replaces it

Phase 1a falsified §2.5 item 9's −1.7 prediction and — correctly — offered its replacement as a
hypothesis rather than asserting it. The hypothesis was *tail-symbol clipping smeared by per-cycle
DT spread*. **The smearing half is right; the clipping half is wrong.** The answer was available in
the vendored decoder and neither the original specification nor the QA session went to look:
`decode.c:279` bounds the time search at `DT_obs ∈ [−1.60, +3.12]`, hardcoded and asymmetric, not
the ±2.5 s this specification asserted three separate times.

That bound, applied to arm A's own DT distribution with **no fitted parameters**, reproduces all
12 measured recall points at RMS error 0.085; the assumed ±2.5 s bound scores 0.472 on the same
data. Full model, evidence and consequences are recorded as **§2.5 item 10**; item 9 is struck
through rather than deleted, per §3's standing rule.

**This is the fifth pre-existing defect in this specification, and the second serious one** (after
§6.3's inverted sign). Like the sign error, it would not have been caught by any control in §7 —
§7's controls test whether the *harness* measures what it claims, and this was a wrong physical
constant in the *specification's model*, which the harness faithfully measured around. Both
survived Phase 0's ratification. **The pattern is now established enough to name: this
specification's assumed physics has been wrong more often than its measurements have.** Prefer
reading the vendored source over reasoning from remembered protocol constants.

### 15.2 On QA's Phase 0b resolution

The hash-token diagnosis is the strongest work in either report: root-caused to a named line,
*tested the remedy this specification prescribed*, showed it fails for a stated mechanical reason
(native static memory the managed wrapper never touches), and declined to silently work around it.
The re-scoring check against §2.5's already-ratified figures was unprompted and exactly right.

Two corrections to its framing, neither affecting the outcome:

1. **This is a control that failed, not a defect that was fixed.** §7.4(b) asks whether cumulative
   native state perturbs decodes; the finding is that **it does**, and the study proceeds by making
   the metric blind to the axis it perturbs. That is a legitimate and common move, but it must be
   recorded as a narrowed metric rather than a passed control — §7.4(b) is amended accordingly.
   (That the prescribed remedy proved infeasible is a weaker class of defect than the four in §14;
   it was a wrong fix, not a wrong requirement.)
2. **Two hazards were not addressed** and are now mandatory guards on Phase 1b: §7.4(b-i)
   collision assertion (measured 0 merges across Phase 0's 25 cycles, but 7.18 % of rows carry a
   bracket token, so it will not stay zero at 400 cycles — assert it, don't assume it) and
   §7.4(b-ii) `hashTableRejectCount` recording (the hazard §7.4 actually names; normalization
   neither fixes nor reveals a reject-driven missing decode).

Keeping `D001ParamSweep --fresh-decoder-per-wav` is endorsed, on the reasoning QA gave.

### 15.3 On QA's Phase 1a analysis

Accepted, with the mechanism replaced per §15.1 and two methodological notes:

- **The δ=0 identity anchor is being used as evidence.** Phase 1a's combined table lists
  `0.000 | 1.000` alongside measured points and its shape argument leans on it ("declines gradually
  from 1.00 at δ=0"). §2.5 is explicit that this is an anchor, not a measurement. Phase 0b's
  reverse-order arm is an *independent-order* decode of δ=0 that matched 25/25 after normalization
  — a better anchor, already on disk, free to promote. It remains same-input, so it bounds
  order-dependence rather than establishing sensitivity; label it that way.
- **The left tail is real and was not reported.** `min` recall is 0.000 at every negative δ
  including −1.0. §5.3 is amended to require p10 and a zero-recall cycle count.

QA's recommendation to re-grid before spending Phase 1b's budget is **accepted and went further
than requested**: with item 10's model in hand the Captain has cut Phase 1b from 27 offsets to 11
(≈7 200 decodes rather than ≈13 200), against a stated three-part falsification criterion with a
fallback to the full grid. See §5.2's second amendment and §9.

### 15.4 Consequence for §1's question — provisional, and it moved

The corrected worked example in §6 changes the anticipated answer materially: the 9.5 session's
worst 30-minute bucket (median DT +2.90 → δ_live −2.10) costs **≈17 % of decodes, not ≈100 %**.
The retracted −1.7 cliff had placed that bucket past the cliff; the real cliff is at −2.32 and the
bucket sits on the shoulder. Bucket medians average over per-cycle excursions that may be worse, so
this is a floor rather than a settled figure — but the framing that cycle-boundary misalignment was
catastrophic across the 9.5 session is **not currently supported by measurement**, and
`tasks.md` 10.8's eventual acceptance bound should not be written as though it were.
