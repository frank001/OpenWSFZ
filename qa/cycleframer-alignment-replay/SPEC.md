# Offline alignment-replay study — how much recall does cycle-boundary misalignment cost?

**Author:** Architect session, 2026-07-25. **Status:** specification, not yet implemented.
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
| **S — sweep** | −3.00 … +3.00 in 0.25 s steps (25 points, δ=0 shared with A) | **Primary deliverable.** Produces recall(δ). |
| **S-wide** | ±3.5, ±4.0 | Confirms the curve has bottomed out rather than being truncated by the sweep range. |
| **N — negative controls** | see §7 | Proves the harness can detect an alignment effect at all. **Mandatory; results are void without it.** |

Range rationale: an FT8 transmission occupies 12.64 s of the 15 s cycle, and ft8_lib's time search
is bounded near ±2.5 s, so the interesting structure lies within ±3 s.

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
3. Alignment error per cycle ≈ `DT_live(k) − DT_reference(k)`.
4. Map through recall(δ) to get the predicted recall cost of the live alignment, per cycle and
   session-wide.

This decomposition is deliberate: it separates a robustly measurable quantity (the curve) from a
separately-derived input (the live alignment error), instead of attempting one fragile end-to-end
replay that would require sample-level registration between OpenWSFZ's capture and WSJT-X's — two
different captures of the same audio at slightly different rates. **Do not attempt that
registration.**

## 7. Controls — mandatory, not optional

Two of the three invalidated approaches in §3 failed because nothing would have caught a
degenerate comparison. These controls exist to catch exactly that:

1. **Sensitivity control.** δ = +2.0 s must show a materially lower median recall than δ = 0. If it
   does not, the harness is not sensitive to alignment and **every result in the study is void** —
   stop and diagnose.
2. **Shuffled-pairing control.** Score cycle *k*'s δ=0 decodes against reference set `ref(k+7)`.
   Recall must collapse to ≈ 0. If it does not, the matcher is broken.
3. **Provenance record.** Every output file records: source WAV directory, segment index, δ,
   harness git SHA, and decoder parameter values. The harness refuses to run if the reference and
   a test arm resolve to identical δ.
4. **Determinism check.** Decode one WAV twice in the same process and assert byte-identical
   output. `Ft8Decoder`'s iterative-subtraction path and `hashTableRejectCount` are
   process-lifetime cumulative (visible in the live logs); if determinism fails, use a fresh
   decoder instance per arm and re-assert.

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
| **0** | Re-windowing self-test (§5.1) + controls (§7) | ~50 | All must pass before Phase 1. |
| **1** | 400 cycles stratified across the session × 25 offsets | ~10 000 | Curve shape. Proceed only if the sensitivity control passes. |
| **2** | Full 2,827 cycles × 25 offsets, only if Phase 1's curve needs tightening | ~70 000 | — |

Phase 1 stratification: sample evenly across the 11h51m span, restricted to cycles with
`|ref(k)| ≥ 5`, so both good and poor propagation periods are represented.

Precedent for feasibility: the D-001 sweep ran ~106 000 offline decodes.

## 10. Deliverables

1. `qa/cycleframer-alignment-replay/report.md` — per NFR-024/HK-001 section conventions.
2. **The recall(δ) curve** with median and IQR per offset — the study's reason for existing.
3. The DT baseline distribution from arm A.
4. Predicted recall cost of the 9.5 session's observed alignment excursions (§6).
5. A recommended **maximum acceptable alignment error in seconds**, derived from the curve, for
   use as a `tasks.md` 10.8 acceptance bound and as a cap on correction magnitude.
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
