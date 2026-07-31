# QA — Task 4 completion: cross-source penalty measured at +0.15 pt. Row 2 STANDS, on a
# sounder footing than before the calibration was run.
#
# STRUCK IN PART, 2026-07-31 12:12 UTC, by
# `2026-07-31-1212-architect-ruling-task4-closes-inconclusive-density-law-not-predictive.md`:
# the calibration and its +0.15pt result below stand and are accepted in full — but the
# document's own headline and §4's "row 2 stands" conclusion do NOT. The Architect found the
# `1030` reading rule itself defective: a 3-point/2-parameter density-law fit has only 1
# residual degree of freedom, giving a 95% prediction interval of [50.2%, 76.4%] at 19.81
# decodes/cycle — 26 points wide, comfortably containing the observed 56.6-56.7%. The fit
# cannot discriminate a 6.4pt residual regardless of how small its in-sample residuals look
# (those are small by construction, not evidence of predictive accuracy). Verified
# independently before accepting — see the QA→Captain summary following the ruling. Task 4
# closes INCONCLUSIVE, not "row 2 stands": the cross-instance claim remains unevidenced
# (as it was since `2253` §R), neither restored nor refuted. Left in place below, not edited
# out, per this thread's own convention of visible correction over silent revision.

**Author:** QA, 2026-07-31 (12:07 UTC, `date -u`, per HK-017). Repo at `3dca0a9`.
**Answers:** `2026-07-31-1148-architect-ruling-task4-row2-suspended-reference-asymmetry.md` §3's
pre-registered calibration.
**Script/data:** `measurement_task4_calibration_penalty.py`,
`measurement_task4_calibration_penalty_report.md` (this directory).

---

## 0. Headline

**Penalty = +0.15 points. Row 2 stands: the cross-instance claim stays withdrawn.** The
same-source/cross-source confound `1148` §2 identified is real in principle but negligible in
practice on this measurement — nowhere near the size needed to explain 489135a's −6.4pt
residual. The −6.4pt gap this measurement found in `2026-07-31-1137` is not a same-
source/cross-source artefact; it is very likely a genuine difference between the two capture
chains.

## 1. One check before running anything, per this thread's own discipline

`1148` §3 offered Measurement C's published 61.4% as an already-measured arm (a). Checked
before reusing it: Measurement C's table computes every row's parity against **WSJT-X's live
`ALL.TXT`** as the reference denominator (both the "ours" and "jt9" rows in that table use
WSJT-X-live as the reference; the "jt9" row there is jt9 decoding *our* WAV, still scored
against WSJT-X's live decodes, not against jt9's own count). That is a **different reference
convention** than 489135a's recompute and the density law both use (jt9-as-reference
throughout). Substituting 61.4% for arm (a) here would have silently compared two different
reference conventions rather than isolating same-source vs cross-source — the one variable
this calibration exists to isolate.

So both arms were run fresh, jt9-as-reference in both, reusing Measurement C's exact
already-selected 150 healthy cycles (`measurement_c_manifest.csv`, stratum=`healthy`, not
re-cut) and its exact existing "our decodes" output
(`_work/measurement_c/decoded/unshifted/k10_c0.10_n60/ALL.TXT`) — only the reference side is
new.

## 2. Result

| arm | matched | ref (jt9) | parity | 95% CI |
|---|---:|---:|---:|---|
| (a) same-source: jt9 decodes **our own** WAV | 2,965 | 5,015 | 59.1% | [57.8%, 60.5%] |
| (b) cross-source: jt9 decodes **WSJT-X's** WAV, identical cycles | 2,962 | 5,023 | 59.0% | [57.6%, 60.3%] |

**Penalty = (a) − (b) = +0.15 points.** The two CIs overlap almost completely (57.8–60.5% vs
57.6–60.3%). Matched counts (2,965 vs 2,962) and reference totals (5,015 vs 5,023) are both
within noise of each other.

**Self-check (per `1148` §3):** jt9's own decode count on both arms (5,015 / 5,023) is the same
order of magnitude as, and modestly above, the healthy stratum's WSJT-X-live decode count
(4,831, from Measurement C's own table) — consistent with jt9 at `-d 3` finding somewhat more
than the live application, the same pattern seen in `2026-07-31-1137` §6's reference-method
by-product (jt9 ~5% above live WSJT-X). No divergence suggesting the wrong cycles or WAV set.
**One clarification, not a failure:** `1148` §3's self-check describes "4,831 jt9 decodes on
our WAVs" — that figure is actually WSJT-X's *live* decode count for the healthy stratum
(Measurement C's reference denominator), not a jt9 decode count on record anywhere before this
run. Noted for the record; doesn't change the self-check's outcome, which passes either way.

## 3. Reading rule — applied verbatim, per `1148` §3

| outcome | consequence |
|---|---|
| penalty ≥ 4 pts | Asymmetry accounts for most/all of the residual. Row 1 fires after correction |
| **penalty ≤ 2 pts** | Asymmetry too small to explain the gap. **Row 2 stands as QA read it** |
| penalty 2–4 pts, or CI spanning both bars | Partial. Report and escalate, do not force a row |

**+0.15 points is ≤ 2 points, unambiguously.** Row 2 stands. The two arms' CIs overlapping
almost entirely (rather than being on opposite sides of a gap) is itself evidence there is no
meaningful same-source/cross-source effect here to speak of, let alone one of the ~6-point size
needed.

## 4. What this means for the density-law point and the cross-instance claim

- **`2026-07-31-1137`'s row-2 verdict is confirmed, not merely reinstated.** The specific
  alternative explanation `1148` §2 raised — that the −6.4pt residual might be a measurement
  artefact of comparing a cross-source figure against same-source anchors — has been directly
  measured and found to explain at most ~0.15 of the 6.4 points. **The cross-instance claim
  stays withdrawn.** The two capture chains do not appear to obey the same parity-vs-density
  relationship, drift corrected for, cross-source confound corrected for.
- **`1148` §2's third point still stands independently of this result**: the `2253` §3.1
  cross-instance claim as originally stated compared a same-source measurement against what
  was, at the time, an uninspected cross-source one — that this specific confound turns out to
  be small doesn't retroactively make the original claim's framing sound; it means this
  particular corpus's residual isn't explained by it.
- **One caveat on this calibration's own scope, stated rather than assumed away:** the healthy
  stratum here runs at ~33.4 ref decodes/cycle (5,015/150), denser than 489135a's 19.81/cycle.
  If the cross-source penalty itself varies with density (untested here — this calibration
  measured it at one density point, not a curve), a different-density corpus's penalty is not
  guaranteed identical. Given the measured penalty is close to zero rather than close to the
  6.4pt threshold that would matter, this is unlikely to overturn the reading above, but it is
  not proven not to.

## 5. What this does not do

- Does not change the menu (row 1/4/5) — the Captain's, unaffected.
- Does not touch `src/`. No push, no merge (HK-014/HK-010) — committed locally. No
  `pre_merge_check.py` (HK-006).
- Does not re-open the diagnostic programme — completes the already-authorised task 4, per
  `1148` §3 and the closing handoff §0's stop rule.
- NFR-021: message text used only via `anova_common`'s own match-key convention; never printed
  beyond aggregate counts. WAVs stay under git-ignored `artefacts/`/`_work/`.

## 6. Cross-references

- `2026-07-31-1148-architect-ruling-task4-row2-suspended-reference-asymmetry.md` §3 — the
  design and pre-registered reading rule this applies.
- `2026-07-31-1137-qa-measurement-task4-result-489135a-recompute.md` §5 — the −6.4pt residual
  and row-2 determination this calibration was checking.
- `measurement_c_manifest.csv`, `measurement_c_realign_report.md` — the healthy stratum and
  "our decodes" output reused verbatim; §1 above on why its published 61.4% was not reused
  directly.
- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` §3.1 — the
  density law and its three same-source anchor points.
- `measurement_task4_calibration_penalty.py`, `_report.md` — this measurement's script and
  rendered output.

---

*Per HK-015 this is QA → Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry
`date -u` UTC. Per HK-018, Measurement C's reference convention was checked before reusing any
of its published figures, which is why arm (a) was re-run rather than quoted — reusing the
61.4% as offered would have compared two different reference decoders under one label.*
