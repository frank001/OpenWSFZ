# D-001: QA → Architect — Measurements A, B, C results, plus the SNR gain-error defect
# All four items authorised by the 2026-07-30-2253 ruling (S5, S6, S6b, S7). Three fired
# consequential outcomes; none landed in "ambiguous, do nothing."

**Author:** QA, 2026-07-31 (00:18 UTC, `date -u`, per HK-017).
**For:** Architect (S5.3/S6.3/S6b.3 each route a ruling back here on their outcome), and the
Captain.
**Answers:** `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md`
S5, S6, S6b, S7 — all four measurements/items that document marked actionable for QA.
**Supersedes nothing.** Additive to the ruling and to
`2026-07-27-2012-architect-to-qa-d001-closing-handoff.md`, which remains the standing
programme reference.
**Authorisation:** all four items below were explicitly authorised in the ruling this answers
— S5 and S6 by the Captain directly (per that document's own header), S6b as the ruling's own
named highest-value measurement with its reading rule pre-registered in the same document, S7
on the Captain's explicit direction to raise it standalone. Nothing here is a QA-initiated new
arm.

---

## 0. Summary — the one thing to read if you read nothing else

Four items, four self-contained write-ups (linked in §5), one line each:

| # | item | mechanical outcome | what it means |
|---|---|---|---|
| §5 | **Measurement A** — SNR-stratified recall | **ESCALATE.** 36.0-pt max separation at matched SNR (bar was 10); 80m/10m recall >= 20m in 26/26 usable bins | **The co-channel withdrawal REVERSES.** Competition, not pure sensitivity |
| §6b | **Measurement C** — re-alignment experiment | **PROVEN.** Our decoder's collapsed-window parity: 4.0% -> 63.1% after realignment, landing on the healthy baseline (61.4-61.7%). Null control moved 0.3 pts | The capture-clock-drift collapse is window misalignment, **fully recoverable**, not permanent data loss |
| §6 | **Measurement B** — capture-chain replication | **REFUTED.** n=300, drift-free primary arm: interaction 95% CI [0.9526, 1.0421], paired Wilcoxon p=0.44/0.84 | The original 30-cycle ~10-13% "capture-chain effect" was noise — confounded by drift, per C. **Strike S3/S9.** |
| §7 | SNR gain error | **Confirmed at per-decode resolution** (n=41,668 pooled): slope 0.6865, 95% CI [0.6824, 0.6906] — excludes 1.00 by a wide margin | Standalone defect filed (`DEFECT-snr-reported-gain-error.md`); no fix proposed |

Every reading rule was pre-registered before its run and applied mechanically here — no
discretion exercised on any of the four outcomes above. Where a rule's consequence column
names an action ("escalate," "fold in," "strike," "drop"), that action is this document's
request to the Architect, not something QA has already done to S3/S9/the row 4 decomposition.

## 1. Measurement A (§5) — the co-channel withdrawal reverses

Self-check: all four corpora reproduced their published ANOVA matched-decode counts exactly
(20m=24201, 10m=9177, 80m=8290, 40m=52736) — the matching logic had not drifted.

At matched reference SNR, 20m (36.4 decodes/cycle, the densest band measured) recalls
10-36 points worse than 10m (8.5/cycle) and 80m (3.4/cycle) — **across the entire SNR range**,
from -24 dB to +28 dB, not just at the margins. A fixed-sensitivity deficit predicts a
horizontal shift (same curve shape, offset threshold); this is a uniform vertical gap instead.
80m-recall >= 20m-recall held in **every one of 26 usable common-support bins** (n >= 20/bin/
band).

Per S5.3's table this is squarely the "dense bands sit materially below sparse at matched SNR"
row: *"Competition, not sensitivity. The co-channel withdrawal REVERSES. Escalate to the
Captain before any further work."*

One observation flagged but not chased further (S5.3 forbids extending the reading): 10m and
80m track each other closely while 20m sits sharply below both, which reads more like "20m
specifically" than a smooth density gradient — worth a look at whether `K_MAX_CANDIDATES = 140`
(`d001-c1-candidate-cap-sweep`) is saturating on 20m's decode density specifically. Not
measured; recorded so it isn't re-discovered from nothing.

**Full write-up:** `2026-07-30-2337-qa-measurement-a-result-co-channel-reverses.md`.
**Script/data:** `measurement_a_snr_recall.py`, `measurement_a_snr_recall_report.md`,
`measurement_a_recall_by_snr.png`.

## 2. Measurement C (§6b) — the capture-clock-drift collapse is proven recoverable

Full scale, n=300 (150 healthy-window + 150 collapsed-window cycles), fixed-stride sampled
from the drift regression fit in `measure_drift_8080_session.py`. Shift direction derived from
first principles and validated twice before being trusted: a synthetic-control self-test
(known 1000-sample delay recovered exactly, peak correlation 1.0000), then the measurement's
own built-in check (S6b.3) — the healthy-window null control.

| stratum | condition | decoder | parity | 95% CI |
|---|---|---|---:|---|
| healthy | unshifted | ours | 61.4% | [60.0%, 62.8%] |
| healthy | shifted | ours | 61.7% | [60.3%, 63.0%] |
| **collapsed** | **unshifted** | **ours** | **4.0%** | **[3.2%, 5.1%]** |
| **collapsed** | **shifted** | **ours** | **63.1%** | **[60.7%, 65.5%]** |

Collapsed-window recovery: **4.0% -> 63.1%, a 15.8x improvement**, landing inside the
healthy-window baseline's own CI. Healthy-window null control moved 0.3 points — nowhere near
"materially," which is exactly the S6b.3 trap check for a harness/sign error. jt9 recovers
similarly (17.3% -> 90.1%) with a smaller residual gap versus its own healthy baseline
(96.6-98.1%), noted but not chased further.

Per S6b.3: *"Collapsed-window parity recovers toward ~65% -> The collapse is window
misalignment and nothing else. PROVEN, not inferred. The fix targets cycle-boundary
synchronisation. The affected corpora become recoverable by realignment rather than being
written off."*

**Not done as part of this run** (flagged, not silently assumed): the 489135a 40m corpus's
drift-free recompute (S3.1's fourth density-law point) — this measurement used the
`20260729_live_run_1831-8080` session only, per S6b's own design. That corpus's own recompute
is a follow-on task, not a by-product of this one.

**Full write-up:**
`2026-07-31-0008-qa-measurement-c-result-drift-collapse-confirmed-recoverable.md`.
**Script/data:** `measurement_c_realign.py`, `measurement_c_realign_report.md`,
`measurement_c_manifest.csv`.

## 3. Measurement B (§6) — the capture-chain effect was noise

Primary arm only (|drift| < 0.5 s, n=300) — the arm S6.3's reading rule applies to. Pooled 2x2
and the decisive paired per-cycle Wilcoxon:

| | our WAV | WSJT-X WAV | ratio | paired Wilcoxon p |
|---|---:|---:|---:|---:|
| our decoder | 6118 | 6139 | 1.0034 (+0.3%) | 0.4442 |
| jt9 | 10091 | 10089 | 0.9998 (-0.0%) | 0.8364 |

Interaction `ad/bc` = 0.9964, 95% CI [0.9526, 1.0421] — spans no-effect comfortably. Compare
the original n=30 estimates of +12.5%/+9.9%: at n=300 (10x), with a nominal z ~4.9 if a
+12.5% effect were real, finding p=0.44 is a clean null, not "still underpowered."

**Why the effect vanished, not just shrank:** Measurement C independently confirms the
mechanism. The original 30-cycle sample sat at 2.34 s of drift (the ruling's own S4 finding —
confounded, not measuring audio quality). With drift actually excluded by design here, there
is no remaining physical reason for a WAV-source effect, and none was found.

Per S6.3: *"Effect refuted, CI comfortably spans zero -> n=30 was noise. Drop it. Strike S3's
percentages."* This document is that request — S3/S9 of the ruling are the Architect's/QA's
prior documents to correct, not edited by this one.

**Not run:** the secondary dose-response/DT-tolerance-curve arm (S6.2) — descriptive, not
subject to S6.3's rule, and Measurement C's healthy/collapsed split already delivers the
practically relevant version of the same information (the cliff sits where the defect report
bracketed it, 2.34-2.48 s).

**Full write-up:** `2026-07-31-0010-qa-measurement-b-result-capture-chain-effect-refuted.md`.
**Script/data:** `measurement_b_capture_chain.py`, `measurement_b_capture_chain_report.md`.

## 4. SNR gain error (§7) — confirmed at per-decode resolution, filed standalone

Per-decode regression (n=41,668, three jt9-referenced corpora, `anova_common.py`'s matching
reused unmodified) confirms S7.1's three-point corpus-mean fit is not a small-sample artefact:

```
POOLED: ours ~= 0.6865 * reference - 4.742 dB
  slope 95% CI [0.6824, 0.6906] -- excludes 1.00 (a pure offset) by a wide margin
```

Filed as its own defect (`DEFECT-snr-reported-gain-error.md`, repo root), per the Captain's
explicit instruction to raise it outside the D-001 thread. No fix proposed — the correction
shape (gain vs. offset vs. estimator redesign) is the open decision. Per §7.4's item 3, the D6
comment dev-task is drafted and ready: `dev-tasks/2026-07-30-fix-d6-comment-lr-phase-false-
claim.md`.

## 5. Process notes

- **HK-018 discipline applied throughout:** every reading rule was quoted verbatim and applied
  mechanically before any interpretation; self-checks (Measurement A's matched-count
  reproduction, Measurement C's healthy-window null control, Measurement B's power comparison
  against the original n=30 estimate) were run and reported even where they could have been
  skipped.
- **CPU/compute:** Measurements B and C ran concurrently once the Captain confirmed spare
  capacity was available — verified safe beforehand (separate working directories, read-only
  shared source data, process-isolated native decoder state per invocation, no data
  dependency either direction). No warnings or errors in either run's log.
- **HK-017:** two timestamps in this thread's earlier drafts were hand-approximated rather
  than mechanically derived (a byline "region" hedge on two files, and a dev-task filename
  dated the wrong UTC calendar day against local-time crossover) — caught and corrected before
  this document was written, not after.
- Does not touch `src/` or native code anywhere in this batch. No push, no merge (HK-014/
  HK-010) — committed locally, per this session's commit. No `pre_merge_check.py` run implied
  (HK-006, Captain's trigger only).
- NFR-021: all four measurements read message text only to build match keys / de-duplicate
  per-cycle counts, identical to `anova_common.py`'s own convention, and never printed or
  wrote it out. Raw WAVs and per-decode output live under git-ignored `_work/`/`artefacts/`.
  Only aggregate counts, ratios, and statistics are committed.

## 6. What this document asks of the Architect

Per each measurement's own pre-registered consequence column:

1. **§5/Measurement A:** rule on the reversed co-channel withdrawal, and what it means for the
   row 4 decomposition (still owed, per the ruling's own §8 — this document does not change
   that it's owed, only what shape it should now take).
2. **§6b/Measurement C:** rule on whether/when to action "the fix targets cycle-boundary
   synchronisation" as a dev-task, and whether the two affected corpora's headline parity
   figures should be recomputed on realignment before being cited again.
3. **§6/Measurement B:** strike S3/S9's capture-chain percentages from the ruling's own record,
   per S6.3's own instruction.
4. **§7:** no ruling needed — already routed to a standalone defect per the Captain's
   direction; noted here for completeness only.

## 7. Cross-references

- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` — the ruling
  all four items answer.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — the defect Measurements B and C both
  bear on.
- `DEFECT-snr-reported-gain-error.md` — §7's standalone defect.
- `dev-tasks/2026-07-30-fix-d6-comment-lr-phase-false-claim.md` — ready for a Developer
  session.
- The four measurement write-ups and their scripts, listed in §1-§4 above.

---

*Per HK-015 this is QA -> Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline both
carry `date -u` UTC, checked mechanically. The row 4 decomposition, the S3/S9 strike-through,
and any fix scoping remain the Architect's/Captain's to action.*
