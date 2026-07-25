# Architect → QA: PR #108 disposition and D-001 alignment work plan

**Author:** Architect, 2026-07-25 (23:30). **For:** QA.
**Evidence base:** `2026-07-25-2300-alignment-root-cause.md` (this directory), commit `e584082`.

This document does two things: it sets out the recommendation to **close PR #108 unfixed**, and
it specifies the **follow-on work** in enough detail for QA to author `tasks.md` entries and
`dev-tasks/*.md` handoffs. Per HK-015 I have not written either — task authorship is QA's.

> **Partially superseded 2026-07-26.** §4's work plan is withdrawn, replaced by
> `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §6 and
> `2026-07-26-0100-architect-to-qa-land-housekeep-and-continue-d001.md` Part C. §2 (PR #108
> mechanics/close recommendation) remains current.

---

## 1. TL;DR

- `CycleFramer` does not drift. Measured absolute alignment σ = **59 ms** over 94 cycles with
  **zero dropped samples**; the reference implementation it was being compared against is
  **3.5× less stable** (σ = 208 ms). PR #108 corrects a fault that is not in our arm.
- **Recommend: close PR #108 unfixed**, salvaging ~157 lines of observability code from it.
  This closes `cycle-audio-archive` tasks.md **§9.5**, the last open item in that change.
- One real defect surfaced instead: **`Ft8Decoder` reports DT ~0.735 s high** on byte-identical
  audio. Whether it costs decodes or is report-only is **not yet known** and is decided by a
  single offline run (§4.1) using tooling already on `main`.

## 2. The §9.5 decision: close PR #108 unfixed

### 2.1 Why

PR #108 (`docs/propose-fix-cycle-boundary-clock-drift`, draft, base `main`, merge-base
`9369900`) exists to add periodic wall-clock re-anchoring to `CycleFramer`, on the theory that
device clock-rate error was walking our cycle windows off the UTC grid. Three fix rounds were
built and all three were defeated by live testing.

They were defeated because the premise is wrong. Measuring absolute window alignment against
the transmitting stations (which are collectively time-locked, so a cycle's median decoder DT
*is* an absolute alignment measurement):

| arm | per-cycle median DT | σ |
|---|---:|---:|
| our capture (same decoder) | +0.679 s | **59 ms** |
| WSJT-X capture (same decoder) | +0.546 s | **208 ms** |

Holding the decoder fixed makes this a clean capture-vs-capture comparison. Supporting
evidence, all from `artefacts/20260725_live_run_1806/`:

- `cycle-archive.csv`, 84 rows: `dropped_before` = **0 on every cycle**; consecutive
  `window_closed_utc` deltas 14987–15056 ms, i.e. 15.000 s ± 50 ms with **no accumulation**
  over 21 minutes.
- Waveform cross-correlation, 68/68 pairs locking at 0.933–0.992: the ±500 ms sawtooth in the
  relative lag belongs to **WSJT-X's** arm. It ramps ~155 ms/cycle then resets, and the 16
  cycles WSJT-X failed to save are *exactly* the 16 reset points. Our arm wrote a complete,
  unbroken 84-slot grid.
- Two independent instruments (waveform lag; decoder DT) agree at slope 1.036, r = +0.972.

There is no drift in our framer for PR #108 to fix. Merging it would add 318 lines of
correction machinery to `CycleFramer` that can only ever move a correctly-anchored window off
target, plus a standing risk of exactly the non-convergence the three live rounds already saw.

### 2.2 What closing discards, and what to salvage

Full `src/`+`tests/` diff vs merge-base is **1305 insertions**. Not all of it is drift work:

| file | lines | disposition |
|---|---:|---|
| `src/OpenWSFZ.Ft8/CycleFramer.cs` | +318 | **discard** — the re-anchoring correction itself |
| `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` | +677 | **discard** — tests for the above |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` | +19 | **salvage** — per-cycle `hashTableRejectCount` logging |
| `tests/…/HashTableRejectCountLoggingTests.cs` | +141 | **salvage** — tests for the above |
| `src/OpenWSFZ.Audio/WasapiAudioSource.cs` | +49 | **salvage (recommended)** — aggregated capture gap / enqueue-latency diagnostics |
| `src/OpenWSFZ.Audio/CaptureManager.cs` | +48 | **salvage (recommended)** — same |
| `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs` | +53 | **salvage (recommended)** — tests for the above |

The salvage set is pure observability and is independent of the drift hypothesis — it stands or
falls on its own merits, and both halves are useful to work that is still live:

- `hashTableRejectCount` per-cycle logging replaces ad hoc `GET /api/v1/status` polling that a
  previous live run could not reconcile against the daemon log afterwards. The remaining open
  question in D-001 is **decoder sensitivity**, which is exactly what this instruments.
- The capture-gap/enqueue-latency summary would have shortened tonight's investigation
  materially — establishing "our capture is clean" took three separate measurements that this
  telemetry would have answered directly.

I am recommending the salvage, not assuming it. If QA judges the observability not worth a
separate PR, closing all 1305 lines is a defensible call and the analysis stands either way.

### 2.3 Mechanics

- `openspec/changes/fix-cycle-boundary-clock-drift/` exists **only on the branch** — it was
  never merged to `main` (`openspec/changes/` currently holds only `archive/` and
  `cycle-audio-archive/`). So there is **no OpenSpec archive step**: closing the PR removes the
  change wholesale. HK-002's pre-merge audit does not apply to a close.
- **No stacked PRs.** #108 is the only open PR in the repo and targets `main` directly, so
  HK-008's retarget-before-delete hazard does not arise. Branch cleanup is safe once closed.
- Closing the PR and deleting the branch are **remote operations — QA's, not mine** (HK-014,
  HK-000), and require the Captain's explicit sign-off (HK-010). This document is the
  recommendation; it is not authorisation.
- The six `dev-tasks/2026-07-2[345]-cycleframer-*.md` handoffs on that branch describe the
  three defeated fix rounds. They die with the branch. Their diagnostic narrative is worth
  preserving — suggest QA either lands them to `main` as historical record or folds a summary
  into the §9.5 closure note, rather than letting the reasoning vanish silently.

### 2.4 Closing §9.5

§9.5 reads: *"Decide, with the Captain, what happens to the paused PR #108."* On the Captain's
sign-off it can be ticked with a one-line disposition pointing at
`2026-07-25-2300-alignment-root-cause.md` and this document. That is the last open box in
`cycle-audio-archive`, which then becomes archivable (`opsx:archive`) — subject to HK-002's
manual audit, since that change *is* being archived rather than closed.

## 3. Correcting the 21:45 note

`2026-07-25-2145-raw-audio-crosscorrelation-check.md` is on `main` at `7a04928` and its §2–§4
are wrong: a ±50 ms lag search was truncating (true lags reach −504 ms), so 57 of 68 pairs were
reported as physically "inconclusive" when the search had simply run out of room, and its §3
argued both that the two arms share one ADC clock domain and that their noise is independent.

It is QA's document, so the correction is QA's to make and I have not touched it. My
recommendation is a **superseded-by banner pointing at the 23:00 analysis, with the body left
intact** — the failure mode (a truncated search reading as a physical result, then attracting a
mechanism to explain it) is worth keeping visible rather than editing away.

Note the note's *verdict* — capture-chain parity — was correct, and now rests on 68/68 waveform
lock instead of 11/68. Only the reasoning needs correcting, not the conclusion.

## 4. Work plan

Ordered by value. Owners follow HK-011/HK-015: QA proposes and runs offline analysis; anything
touching `src/` goes to a separate Developer session with Captain review before push.

### 4.1 Decide whether the DT offset costs decodes — **highest value, do first**

**Question.** `Ft8Decoder` reports DT +0.735 s high vs WSJT-X on identical audio. Two
possibilities with very different consequences:
- *Report-only* — `ft8_lib`'s sync search is symmetric about the true position and only the
  reported number is offset. Consequence: a logging-correctness bug (ADIF and UI carry a wrong
  DT), no sensitivity impact.
- *Mis-anchored* — the search interval itself is offset, so we spend ~0.7 s of a ~±2.5 s search
  range on one side. Consequence: a real sensitivity defect and a candidate contributor to the
  standing 1749-vs-2684 decode gap.

**Method.** Fully offline, deterministic, no live run, all tooling and data already on `main`:

1. Use **our own** 84 WAVs (`artefacts/20260725_live_run_1806/owsfz/wav/`) as the substrate —
   an unbroken 15 s grid with the stable alignment established above. WSJT-X's directory has 16
   gaps and a ±500 ms sawtooth, which would confound the sweep; keep it as a cross-check only.
2. `rewindow.py cut --wav-dir … --out-dir … --delta D` for D ∈ {−1.0, −0.75, −0.5, −0.25, 0,
   +0.25, +0.5} s. It concatenates contiguous segments before cutting, so there is **no
   tail-truncation confound** — this is why the sweep must go through `rewindow.py` and not
   through naive per-file padding.
3. Decode each delta with `D001ParamSweep --manifest` at the production baseline
   (`k10_c0.10_n60`), unmodified.
4. Plot total decode count and median reported DT against D.

**Interpretation.** Decode count flat across D (peak at D ≈ 0) ⇒ report-only; fix as a logging
bug. Count peaking at D ≈ −0.7 ⇒ genuinely mis-anchored; the defect is a sensitivity issue and
belongs in the D-001 thread with priority. Median DT must shift 1:1 with D in either case — if
it does not, the DT derivation is confused in some further way and that supersedes both
branches.

**Definition of done.** A findings doc in this directory with the count-vs-delta table, the
verdict, and a routing decision. **NFR-021:** `rewindow.py` output contains real third-party
callsign audio — all outputs must go under the git-ignored `_work/` (its own docstring says so).

### 4.2 Fix the DT offset — Developer session, gated on 4.1

Locating the exact term is a code question I have deliberately not answered. The leading
hypothesis is a missing 0.5 s nominal-transmission-start subtraction (WSJT-X reports DT
relative to the transmission start 0.5 s into the cycle; `ft8_lib` returns offset from buffer
start), with the ~0.235 s balance plausibly from sync-search quantisation (symbol 0.16 s ÷
`time_osr`). That accounting is unconfirmed and the Developer should not treat it as given.

Scope and urgency depend entirely on 4.1's verdict, so **QA should not draft this dev-task until
4.1 reports.** Either way it needs a regression test pinning median DT on a fixed WAV corpus —
the absence of one is why a 0.735 s offset survived this long.

### 4.3 Salvage the observability from PR #108 — Developer session, independent

Per §2.2. Cleanest as a **separate small PR cherry-picking the four salvage files**, raised
*before* #108 is closed so nothing is lost, and reviewed on its own merits rather than inheriting
#108's history. Needs Captain review before push per HK-011.

### 4.4 Fold the new instruments into the standing harness

`measure_capture_alignment.py` and `measure_dt_alignment.py` are on `main` as of `e584082`,
out of git-ignored `_work/`, and reproduce every number in the 23:00 analysis. The 2×2
decoder-vs-audio design in the second is a **general instrument for separating a capture fault
from a decoder fault** — it resolved in one run what decode-count comparison could not resolve
at all. Worth a mention in `qa/cycleframer-alignment-replay/SPEC.md` so the next alignment
question reaches for it instead of rebuilding ad hoc.

### 4.5 Explicitly not recommended

The band-limited coherence check floated in the 21:45 note §3. It was proposed to rescue the 57
"inconclusive" pairs; those pairs were never inconclusive, and the widened search already
answers the question at full strength. Skip it — it would cost real effort to re-derive a
result now in hand.

## 5. Sequencing and risk

```
  4.1 (QA, offline)  ──┬──> 4.2 (Dev, scope set by 4.1's verdict)
                       │
  §2 close #108 ───────┼──> 4.3 (Dev, salvage — raise BEFORE the close)
  (Captain sign-off)   │
                       └──> §2.4 tick §9.5 ──> archive cycle-audio-archive (HK-002 audit)

  §3 correct 21:45 note (QA) — independent, any time
  4.4 SPEC.md mention (QA)   — independent, any time
```

Risks, honestly stated:

- **The 0.735 s could still be partly capture-side.** I have decomposed it with two independent
  instruments agreeing to 16 ms, and the same-audio/two-decoder comparison is as clean a control
  as this data allows. But every measurement here comes from **one 21-minute session on one
  device**. A second session on different hardware would harden it. I do not think it changes
  the PR #108 recommendation — the σ = 59 ms stability and zero dropped samples are direct
  measurements of our arm, not comparative — but it is the assumption most worth testing if
  anything downstream surprises us.
- **Closing #108 discards working code.** If 4.1 returns "mis-anchored", the fix is in
  `Ft8Decoder`'s DT derivation, not in `CycleFramer` re-anchoring, so #108 still would not have
  been the fix. The branch remains recoverable from the remote ref regardless.
- **The decode-sensitivity gap (1749 vs 2684) stays open.** §4.1 tests one newly-identified
  candidate contributor. Nothing here claims to explain the whole gap, and QA should resist
  reading a positive 4.1 result as closing D-001.

## 6. Boundaries observed

Per HK-014 nothing in this thread has been pushed or merged; `e584082` is local only. Per HK-015
`tasks.md` and `dev-tasks/` are untouched — §2.4, §4.1, §4.2 and §4.3 are written for QA to
author and route. Per HK-010 the close of PR #108 needs the Captain's explicit sign-off; green
evidence is not sign-off. Zero `src/` files were modified in producing this analysis.
