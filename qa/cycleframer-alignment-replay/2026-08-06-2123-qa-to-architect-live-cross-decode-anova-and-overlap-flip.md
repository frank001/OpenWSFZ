# QA → Architect: live cross-decode ANOVA (n=5) — and a overlap-pattern flip worth your attention

**Author:** QA, 2026-08-06 (21:23 UTC, `date -u`, per HK-017). Repo `main` at `f6c5b46`.
**For:** Architect.
**Authorisation:** Captain-directed throughout — live replay experiment, the 5-run
extension, the 3-way ANOVA, and this write-up were each requested in-session tonight, not
a QA-initiated arm. Nothing here touches `src/`, no capture run, no `jt9`.
**Reads together with:** `2026-08-06-1920-qa-wav-content-comparison-1713.md` (audio
content), `2026-08-06-1933-qa-decode-config-comparison-wsjtx-vs-openwsfz.md` (decoder
settings), `2026-08-06-2022-qa-live-cross-decode-replay-results.md` (single-run version),
`2026-08-06-2115-qa-live-cross-decode-full-anova-results.md` (the 5-run ANOVA this note
summarises and extends) — all from tonight, all in this directory.

---

## 0. Headline

Five independent live replays (no `jt9`) of the same 20-cycle window confirm, with a real
ANOVA behind it, that the WSJT-X-vs-OpenWSFZ decode-count gap is large, real, and not
confounded with which capture chain's audio gets replayed. That part is confirmatory, not
new. **What's new, and what you should weigh**: checking the *overlap pattern* (not just
the counts) against the original archived captures shows the disagreement structure itself
changed shape between the original live session and tonight's replay — from genuinely
two-sided to almost entirely one-sided — in a way that points at the original session's
WSJT-X suppression (§4 of the 2026-08-06-2022 note) as a candidate explanation for at least
part of OpenWSFZ's *exclusive*-decode population, not just its raw counts.

## 1. What was run

`qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/` — 5 independent live
sessions, each replaying the same 20 consecutive matched cycles from
`20260803_live_run_1713` (`260804_085845` → `260804_090330`, the busiest 5-minute window in
that corpus) out through a VB-CABLE loopback, WSJT-X (`--rig-name=FT991A`, Deep, AP off,
confirmed unchanged since the 3rd) and a fresh OpenWSFZ daemon both listening
simultaneously in real time. Two passes per run (WSJT-X-source WAVs, then OpenWSFZ-source
WAVs, same 20 cycles both times). Full method and per-response ANOVA tables in the
cross-referenced 2115 note; not repeated here.

## 2. Confounding check (the Captain asked directly; answered with a 3-way ANOVA)

Fixed-effects Decoder × Source × Cycle ANOVA, Run (n=5) as the replicate/residual axis:

| effect | F | p | %SS |
|---|---:|---:|---:|
| Decoder | 17423.0 | <0.000001 | 84.7% |
| Source | 5.2 | 0.023 | 0.03% |
| Decoder × Source | 0.16 | 0.688 | 0.0008% |

Decoder and Source are not confounded. Source is statistically detectable but trivial
(0.03% of variance) and still can't be distinguished from within-run pass order (never
counterbalanced across the 5 runs — WSJT-X-source always played first). The
Decoder × Source interaction being flat is the best evidence available that the
Source-or-order effect is a shared artifact, not a genuine per-decoder sensitivity to which
chain captured the audio — consistent with the WAV-content note's finding that the two
chains' in-band audio is essentially identical.

## 3. The overlap-pattern flip

Checked tonight, prompted by the Captain asking "any surprises here?": how much of each
decoder's output is *exclusive* (not found by the other), on this exact 20-cycle window,
original captures vs. tonight's replay.

| | OpenWSFZ exclusive | WSJT-X exclusive | match rate (of OpenWSFZ's total) |
|---|---:|---:|---:|
| **Original captures, 08-03/04** | 279 / 466 (59.9%) | 141 / 328 (43.0%) | 40.1% |
| **Tonight, pooled over 5 runs** | ~54-58 / ~2,300 (2.3-2.5%) | ~1,530 / ~3,770 (~40%) | **97.5-97.7%** |

Originally: a genuinely two-sided disagreement. WSJT-X missed 141 of OpenWSFZ's 466 decodes
(43%); OpenWSFZ missed 279 of WSJT-X's own 328 (60%) — both real, both substantial, on the
*same* 20 cycles.

Tonight: OpenWSFZ's exclusive rate collapsed to ~2.3-2.5% — its decode set is now close to
a strict subset of WSJT-X's. WSJT-X's exclusive *fraction* barely moved (43% → ~40%), but
its exclusive *count* roughly tripled, because its total roughly doubled (§3 of the 2115
note — WSJT-X decoded 748-759 messages per run tonight vs. 328 originally, tight and
reproducible across all 5 runs).

**Reading, stated carefully:** tonight's expanded WSJT-X yield appears to have absorbed
almost everything that used to be OpenWSFZ's unique territory on this window. That is
consistent with a real possibility worth your weighing: some portion of the "OpenWSFZ finds
messages WSJT-X can't" story — part of what's fed the D-001 menu's framing since 07-27 — may
be an artifact of WSJT-X underperforming in the original session (cause still unconfirmed;
CPU contention remains an unverified hypothesis, §4 of the 2026-08-06-2022 note), rather
than a genuine decoder-capability advantage for us on that content. **Not claiming this
generally** — one window, not re-run on others, and OpenWSFZ's own exclusive decodes could
still be real distinct sensitivity elsewhere in the corpus. But it is a concrete, quantified,
reproducible (matched across all 5 runs, not a pooling artifact) shift in the *shape* of the
disagreement, not only its size, and it sits directly underneath the 42.2%/61.8%
whole-corpus scouting figures in the R.D spec and Measurement D's own framing of exclusive
decodes as informative.

## 4. What this does and does not decide

- **Decides**: Decoder is not confounded with Source in this design (§2). The overlap
  pattern on this window is real and reproducible (§3).
- **Does not decide**: what the original WSJT-X suppression was, whether it generalises
  beyond this one window, or how much of any corpus-wide "OpenWSFZ-exclusive" population it
  actually explains. All open.
- **Does not touch** Arm R.D (still not authorised), Measurement D, or any pre-registered
  gate. This is exploratory, Captain-directed, off-the-record-corpus analysis.
- **Not chased further by QA without direction** — per this project's standing cost
  discipline, and because the next useful step (repeating this on a second window, or
  investigating the original session's system load) is a real decision with real cost, not
  a QA judgement call.

## 5. Cross-references

- `2026-08-06-2115-qa-live-cross-decode-full-anova-results.md` — the full 5-run ANOVA
  (decode count, SNR, DT, frequency) this note's §2-3 draw from.
- `2026-08-06-2022-qa-live-cross-decode-replay-results.md` §4 — the original single-run
  discovery of WSJT-X's suppressed original-session yield, which §3 above now bears on.
- `2026-08-05-1459-architect-to-qa-spec-reciprocal-density-asymmetry.md` — the 42.2%/61.8%
  whole-corpus scouting figures this window's overlap numbers sit underneath.
- `project-state-2026-07-31-d001-competition-confirmed.md` — the original 64.1%-parity/
  789-miss framing this may bear on, if the suppression hypothesis generalises.

## 6. Correction — 2026-08-06 (22:04 UTC, `date -u`, per HK-017)

**Architect catch, applied here per
`2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md` §0.1.** The §3 table
above is correct and internally consistent (279 + 187 = 466; 141 + 187 = 328; 187/466 =
40.1%). The prose beneath it (original lines 68–70) swapped the two decoders:

> ~~"WSJT-X missed 141 of OpenWSFZ's 466 decodes (43%); OpenWSFZ missed 279 of WSJT-X's own
> 328 (60%)"~~ — **wrong**. 141/466 = 30.3%, not 43%; 279/328 = 85.1%, not 60%, and would
> force matched = 49 against the table's 187.

**Correct statement: WSJT-X missed 279 of OpenWSFZ's 466 (59.9%). OpenWSFZ missed 141 of
WSJT-X's 328 (43.0%).**

This is an Architect-side catch on a QA note, and it cuts in QA's favour, not against it —
the corrected reading makes the finding *stronger*. Originally OpenWSFZ appeared to
out-decode WSJT-X 466 to 328, with 279 decodes exclusively its own; tonight it is 461 to
752, with ~14 exclusively its own. The comparison does not merely shift, it **inverts**. No
other figure in this note (§2, §3's table itself, §4) is affected — only the two prose
sentences at original lines 68–70, which should be read via the corrected statement above.

---

*Per HK-015 this is QA → Architect. Per HK-014/HK-010 committed locally, no push, no merge
implied, none asked for. Per HK-011 nothing here touches `src/`. Per NFR-021, message text
was read only to build match keys throughout every script tonight — never printed, never
committed.*
