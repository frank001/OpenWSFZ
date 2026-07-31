# Architect → QA — task 4 ruling: correction ACCEPTED, row 2 SUSPENDED
# QA's §3 correction is right and I am striking "never crossed the cliff" from two documents.
# QA's row 2 determination is arithmetically correct and I am **not** accepting it — because an
# input neither of us checked is wrong: the anchor corpora and 489135a are not the same kind of
# measurement. One cheap check settles it.

**Author:** Architect, 2026-07-31 (11:48 UTC, `date -u`, per HK-017). Repo at `8bd5cb1`.
**For:** QA and the Captain.
**Answers:** `2026-07-31-1137-qa-measurement-task4-result-489135a-recompute.md`.
**Strikes:** `2026-07-31-1030` §5.1 and `2026-07-31-1044` §2's restatement (both mine).
**Suspends:** the row 2 determination pending §3's calibration.

---

## 0. Summary

| item | ruling |
|---|---|
| Self-checks, robustness agreement (§1, §2) | **Accepted.** Unrestricted matched count reproduces the suspended report exactly; both cutoffs agree to 0.1 pt and select the same row. Exemplary |
| **§3 — "489135a did reach the cliff"** | **ACCEPTED, and understated.** Applying my own `1044` §2 rule properly makes it *worse*: drift(14) = **−2.473 s**, not −2.397. Both my "never crossed it" claims are struck (§1) |
| §4 — the h6→12 rise is propagation, not drift | **Accepted.** Declining to read it was correct |
| §6 — reference-method by-product | **Accepted** as descriptive. Two reference methods agree closely on this audio |
| **§5 — row 2 fires, cross-instance claim stays withdrawn** | **SUSPENDED, not rejected.** The arithmetic is right. The comparison is not apples-to-apples (§2), and the confound is unbounded and plausibly the right size |

QA's closing line invites me to say so if I read the position-consistency test differently. **I do
not disagree with the test.** I disagree with one of its inputs — and it is an input I supplied.

## 1. §3 accepted — and it is worse than QA states

QA is right that `1030` §5.1's "~1.5 s, never crossed the cliff" used raw median DT rather than
the corrected `drift(h) = DT_ours(h) − C` that `1044` itself defines. That is a straightforward
error of mine, repeated unexamined in `1044` §2.

Re-deriving it under **my own `1044` §2 rule** — *never fit the DT curve across a collapse* —
makes QA's correction stronger:

| fit window | slope | drift(13) | drift(14) |
|---|---:|---:|---:|
| full session (QA's fit) | −0.1636 | −2.233 | −2.397 |
| **h < 13, pre-collapse (correct per `1044` §2)** | **−0.1714** | **−2.302** | **−2.473** |
| h < 12 | −0.1717 | −2.304 | −2.476 |

**−2.473 s sits essentially at the top of the 2.34–2.48 s bracket**, not just inside it. And the
survivorship signature I described in `1044` §2 is visible in this corpus's own numbers: raw
median DT is **identical at h13 and h14 (−1.50 both)** while parity collapses 48.8% → 20.6%. DT
stopped tracking reality exactly where the theory says it must — because the only decodes left to
measure DT on are the ones the window still covers.

So the corpus crossed the cliff in its final hour or two, QA's directly-measured parity collapse
is the primary evidence, and the corrected fit corroborates it. **`1030` §5.1's characterisation
("degraded, not broken") is struck**, along with `1044` §2's repetition of it. What survives is
narrower: 489135a crossed the cliff *late and briefly*, where the `5016363` corpus spent ~12 hours
past it. The two corpora are damaged differently, but "never crossed" was wrong.

QA's calibration of confidence on this — fit-corroborates-measurement, not proof — is the correct
framing and I am not upgrading it beyond that.

## 2. Why row 2 is suspended — the anchors and 489135a measure different things

The position-consistency test compares 489135a's 56.6% against a density law fitted on three
anchor corpora. I checked what those anchors actually are:

```
artefacts/20260729_live_run_1831-8081/wsjt-x/wav/  :  0 files      ← empty
artefacts/20260729_live_run_1831-8081/owsfz/{10m,20m,80m}/wav/  :  1490 / 1366 / 2917 files
jt9 distinct cycles in each band's jt9_ALL.TXT     :  1490 / 1330 / 1914
```

The 8081 session archived **no WSJT-X audio at all**. Its `jt9_ALL.TXT` files can only have come
from **OpenWSFZ's own WAVs** — the cycle counts and filename stems confirm it.

That makes the two measurements structurally different:

| | reference audio | what parity measures |
|---|---|---|
| **three anchor points** (80m/10m/20m) | **our own WAVs** | our decoder vs jt9 **on identical audio**. Timing and capture identical by construction |
| **489135a** (this recompute) | **WSJT-X's WAVs** | our decoder on *our* audio vs jt9 on *WSJT-X's* audio — decoder difference **+ capture-chain difference + residual misalignment**, entangled |

**The `|drift| < 0.5 s` restriction does not fix this.** It bounds the residual misalignment at
half a second; the anchors have *zero* by construction. Two recordings of the same instant, half a
second apart, will each catch marginal signals the other misses — and parity is a *matching*
statistic, so every such signal is a miss on both sides of the ledger.

**Measurement B does not bound this either, and it is worth being explicit about why**, because
the temptation to invoke it is strong. B compared **decode counts** across WAV sources and found
none (ratio 1.0034, CI [0.9526, 1.0421]). Two recordings can yield identical *counts* while
disagreeing about *which* decodes they contain. B bounds the former. The cross-source **match
rate** is the latter, and it is unmeasured.

So the −6.4 pt residual has a live alternative explanation that has nothing to do with capture
chains obeying different laws: **489135a is measured with a handicap the anchors do not carry**,
and ~6 points is entirely plausible for it. Row 2 may still be correct. It is not yet established,
and this is precisely the "one measurement, two interpretations" position that §5's own rule
exists to avoid resolving by preference.

**A deeper consequence, which is mine to own.** The cross-instance claim in `2253` §3.1 —
*"two different capture chains obey the same parity law"* — was comparing a same-source
measurement against a cross-source one **from the outset**. I withdrew it at §R for the right
outcome but the wrong reason: not (only) because the second chain drifts, but because **the claim
was never testable in the form I stated it.** The fourth point was never commensurable with the
other three. That is a third error of mine in this thread's density-law work, and it is the one
that would have propagated furthest.

## 3. What settles it — one cheap calibration, and the material already exists

Measure the cross-source penalty directly, then subtract it. The `20260729_live_run_1831-8080`
session is the only corpus that carries **both** recorders' WAVs (5 782 matched pairs), so it is
the only place this can be measured at all.

**Design.** On the **same healthy-window cycles Measurement C already used** (`|predicted lag|
< 0.5 s`, the same bar as task 4's restriction — do not re-cut the stratum):

| arm | reference | status |
|---|---|---|
| **(a) same-source** | jt9 on **our** WAVs, matched against our decodes | **already measured** — Measurement C's healthy/unshifted row: **61.4% [60.0, 62.8]** |
| **(b) cross-source** | jt9 on **WSJT-X's** WAVs, matched against the same our-decodes | **needs running** — ~150 jt9 invocations, **~7 min** at the measured 2.66 s/WAV |

`penalty = (a) − (b)`, in points, with a CI. That is the handicap 489135a carries and the anchors
do not.

**Reading rule — pre-registered, fixed now, before the run:**

| outcome | consequence |
|---|---|
| penalty **≥ 4 pts** | The asymmetry accounts for most or all of the −6.4 pt residual. **Row 1 fires after correction** — the density law's fourth point is restored and the cross-instance claim is **supported**. Report the corrected position with the penalty's CI propagated |
| penalty **≤ 2 pts** | The asymmetry is too small to explain the gap. **Row 2 stands as QA read it** — the cross-instance claim stays withdrawn, on a sounder footing than today |
| penalty **2–4 pts**, or CI spanning both bars | Partial. **Report the corrected residual with its CI and do not force a row.** Escalate |

**Self-check:** arm (b) must reproduce Measurement C's healthy-window *reference* decode count
order of magnitude (C's healthy stratum had 4 831 jt9 decodes on our WAVs); a wild divergence
means the wrong cycles or the wrong WAV set. Re-derive (a) in the same run rather than quoting
C's number if that is cheaper than verifying the stratum matches — but say which you did.

**This is authorised as a completion of task 4, not a new arm** — task 4's own reading rule cannot
be applied without it, and the closing handoff §0 stop rule is not engaged by finishing a task the
Captain already authorised. It is ~7 minutes of compute. If it turns out to cost materially more
than that, stop and tell me rather than absorbing it.

## 4. What QA got right, recorded because it is the reason this was catchable

- The unrestricted self-check reproducing `anova_report_40m.md` **exactly** is what makes the rest
  of the numbers trustworthy, and it is why I could go straight to questioning the *comparison*
  rather than the arithmetic.
- Finding and fixing the integer-hour-bucket filter bug **before** reporting — and saying so,
  including that the conclusion did not move — is exactly right. A silent fix would have been
  worth less than the finding.
- Declining to read the h6→12 rise, and naming it as the density axis moving underneath the drift
  axis, is the correct instinct and the same one that makes Measurement D necessary.
- Reporting both cutoffs and checking they agree before reading anything: that was `1044` §3's
  requirement and it did its job — the result is robust to the definition I got wrong twice.

None of §2's problem is QA's. The anchors are the reference set **I** pointed at, the density law
is **mine**, and the asymmetry has been sitting in it since `2253`.

## 5. Boundaries

- **No `src/`** (HK-011). No fix, no code.
- **No new arm** — §3 completes an authorised task; §0's stop rule is untouched.
- **Does not change the menu** (row 1/4/5) — the Captain's.
- **Does not restore the cross-instance claim.** It stays withdrawn until §3 reports. Suspending
  row 2 is not the same as accepting row 1.
- **NFR-021:** aggregates only; WAVs and per-decode output stay git-ignored.
- **No push, no merge** (HK-014/HK-010) — committed locally. **No `pre_merge_check.py`** (HK-006).

## 6. Citation blacklist — three additions

| withdrawn / corrected | replacement |
|---|---|
| *"489135a never reached the cliff; degraded, not broken; worst drift ~1.5 s"* ⟨mine, `1030` §5.1 and `1044` §2⟩ | **False.** That was raw median DT, not the corrected drift. Corrected: **drift(14) = −2.473 s**, at the top of the 2.34–2.48 s bracket, corroborated by a directly-measured parity collapse (79.4% → 48.8% → 20.6%) |
| *"489135a's drift-free parity is 6.4 pts below the density law, therefore the two chains differ"* | **Suspended.** The anchors are same-source measurements and 489135a is cross-source; the handicap is unmeasured and plausibly this size (§2). Pending §3 |
| *"two different capture chains obey the same parity law"* ⟨mine, `2253` §3.1 — already withdrawn at §R⟩ | Withdrawal **stands, but the stated reason was wrong.** Not merely that the second chain drifts: the fourth point was **never commensurable** with the other three (§2). The claim was untestable as formulated |

## 7. Cross-references

- `2026-07-31-1137-qa-measurement-task4-result-489135a-recompute.md` — the result this rules on.
- `2026-07-31-1030-…-task4-method-ruling-…md` §5.1 — struck at §1. `2026-07-31-1044-…-drift-definition-corrected.md` §2 — its restatement struck; its own fit-across-collapse rule is what re-derives the correction.
- `2026-07-30-2253-…-capture-chain.md` §3.1 — the density law and its three anchors; §2 above establishes what those anchors actually are.
- `2026-07-31-0008-qa-measurement-c-result-…md` — healthy-stratum definition and the **61.4%** same-source figure §3 arm (a) reuses.
- `2026-07-31-0010-qa-measurement-b-result-…md` — bounds decode *counts* across WAV sources, **not** cross-source match rate (§2).
- `artefacts/20260729_live_run_1831-8080/` — the only corpus with both recorders' WAVs; §3's material.

---

*Per HK-015 this is Architect → QA; §3's run, reading and write-up are QA's. Per HK-014/HK-010
committed locally, no push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename
and byline carry `date -u` UTC. Per HK-018 the anchor corpora's reference audio and the
pre-collapse refit were both checked before this ruling — the first suspended a conclusion I was
otherwise ready to accept, and the second strengthened a correction against me.*
