# N1 — does using the refiner's position fix the reading? BER as the primary, not a proxy

**Architect → QA** · 2026-08-15 18:40Z · branch `feat/r1b-sync-refiner-instrument-correction`
**Captain's direction, 2026-08-15:** *"I really don't like how we have been side-tracked multiple
times from the root cause of D-001 … we need to keep the goal at solving D-001."* Route chosen by
the Captain from the four presented: **the BER outcome arm.**

**🛑 M5 IS WITHDRAWN.** The zero-crossing spec of 18:05Z is superseded before it ran. Its statistic
was sound but it was a sixth round on the smaller limb, measured by proxy, producing no decode
outcome. **Do not run it.** Its one durable finding — that a positional statistic must be signed —
is carried into §4 below and into HK-021 sibling (l).

---

## 1. Why the M-series is being abandoned, in one paragraph

M1, M2 and M4 were all void, each because a **proxy statistic** failed to mean what its gate named.
Every M-round asked *"does the refiner locate?"* and none asked *"does using the refiner change a
decode?"* N1 replaces the proxy with the outcome. Its metric is **BER against a bar that was
measured, not invented** — and a null result is a genuine, citable finding rather than a void,
because BER-versus-correction-threshold **is** the thing D-001 is about.

🔴 **And one realisation that reframes the whole M-series, recorded because it is load-bearing and
because it is my error:** M1's population took the refiner's anchor from **WSJT-X's** `ALL.TXT`
(`m1_build_population.py:105-109`) while the harness read **our** WAV — which is the ~0.65 s
time-base confound that voided M1 and M2. **The production path does not do this.** A real
integration anchors the refiner at *our own candidate's* position, which is already buffer-relative
and carries no convention mismatch. **A large part of five rounds was spent chasing a confound the
study design introduced and the real integration would never have had.** N1 anchors from our own
candidate and the confound does not arise.

---

## 2. The question, and the bar

**Question:** on the population where we find a candidate and fail to read it, does extracting at
the **refiner's** position instead of the **grid** position move BER across the correction
threshold?

**Bar, already measured, not invented** (W1 §5 calibration, `2026-08-07-2319-qa-w1-sec5-calibration-results.md`):

| quantity | value | source |
|---|---|---|
| BP+OSD correction threshold `B50` | **11.3%** | W1 §8, curve crossing |
| THE 135 own-BER median | **44.0%** (p10 17.2, p90 52.3) | W1 §8, same capture |
| matched-hit control BER median | **2.9%** | W1 self-check |

🛑 **`k_50 = 13` / 7.47% is RETRACTED and must not be cited** (C.5a, retracted 2026-08-07). `B50 =
11.3%` is a **different quantity from a different run** and is live. Do not conflate them; if any
document you touch cites 7.47% as the threshold, flag it, do not use it.

---

## 3. 🔴 BLOCKING PRECONDITIONS — both discovered while writing this, both real

### 3.1 The BER harness is not in this tree

`c2_phase2c_ber_measurement.py` — the harness that produced **every number in §2** — is **not on
`main` and not on this branch.** `git ls-files` returns nothing. It exists at commit `7a604b4` on
the unmerged branch **`d001-c4-min-score-sweep`**, and in a stale worktree at
`.claude/worktrees/w1-sec5-calibration/`.

This is the same branch the board already flags as the sole home of the raw-LLR capture, and it is
one of the five unmerged `d001-*` branches with colliding `FT8_SHIM_VERSION` integers.

**QA recovers it onto this branch and, before it is used as an instrument, REPRODUCES §2's numbers
from it.** If the reproduction disagrees with §2 by more than 1 pp on any of the three quantities,
**that is ROW 0a and the arm stops** — the bar is not a bar if the instrument that set it cannot be
re-run. 🛑 Do not proceed on the published numbers alone; they are three weeks old, from a July
corpus, produced by a harness that was never merged.

### 3.2 There is no way to extract at a supplied position — this arm needs a `src/` change

`measure_population()` reads `cand["llr174"]` from a **captured diagnostic export**, keyed by
`nearest_candidate(freq, dt, cands)`. It does not re-run extraction; it looks up LLRs that were
already emitted at the candidate's own grid position. Confirmed by reading the function, and by
`grep` finding **no native export that runs extraction at a caller-supplied (freq, dt)**.

🔴 **Therefore N1 requires a new native export.** This is **not** harness-only, unlike M1–M5.

> **HK-011 applies in full: QA proposes and stops. A separate Developer session runs `opsx:apply`
> (build and tests only, never `pre_merge_check.py`). The Captain reviews the diff.** The Captain
> authorised this route knowing it carried a Developer session; that authorises the *route*, not
> any particular diff.

**The export, scoped as narrowly as it can be:**

```
ft8_extract_llrs_at(pcm, pcm_len, freq_hz, time_offset_s, out_llr174[174]) -> int
```

Runs the existing `ft8_extract_likelihood()` path at a caller-supplied position and returns the
**raw, pre-normalisation** LLRs. 🛑 **No change to any decode path, no change to candidate
selection, no change to what production does.** New symbol only; existing behaviour byte-identical.
`FT8_SHIM_VERSION` bumps to **20260042** (39–41 were reserved; 41 is in use by M1–M4). 🔴 **Pin the
new DLL's SHA256 and assert it — never infer a build from a label.**

---

## 4. Design — paired, so each row is its own control

**Population:** the candidate-present-and-failed rows — the 87.9% (RC1/RC4). For each row we have
`(ts, message, WSJT-X freq/dt, our nearest candidate's grid freq/dt)`.

Each row is measured **twice, on the same audio, the same candidate, the same true codeword**:

| arm | extraction position | expected |
|---|---|---|
| **GRID** (control) | our candidate's own grid position | reproduces ~44% median |
| **REFINED** (treatment) | grid position **+** `ft8_refine_candidate`'s `(Δf, Δt)` | the question |

🔴 **The refiner is anchored at OUR candidate's `(freq_hz, dt)`, buffer-relative, NOT at WSJT-X's
reported values.** Assert this in code with a comment naming the M1/M2 confound. This is the single
easiest way to repeat five rounds of error.

**Pairing is the point.** A paired design removes population selection, SNR composition, corpus
vintage and candidate-mismatch inflation — every confound that has attacked this programme — because
both measurements come from the same row. Report the **paired** difference, never two independent
medians.

**Primary statistic `d_ber` = the paired median of `BER_grid − BER_refined`**, positive meaning
refinement helps. Report with CI and p from a **cluster bootstrap over `ts`** (rows in one cycle
share propagation and noise — HK-021(i)). **Slope/statistic + CI + p, never a bare `r`.**

**Secondary, reported always, gated below:** `f_cross` = the fraction of rows whose BER crosses from
above to below **11.3%** under refinement. This is the number that converts to recall, and it is the
one to quote if ROW 1 fires.

🛑 **Both statistics are signed.** No statistic in N1 may be computed on an absolute value where a
signed one exists (HK-021 sibling (l), ruled today off M4's third occurrence of exactly that
defect).

**Sign unit test, mandatory before arming:** `d_ber == +1.0`-equivalent on synthetic input where
every refined row is perfect and every grid row is maximally wrong, and the negation reversed.
**Do not arm until it passes.** A sign error inverts the verdict exactly.

---

## 5. The gate — pre-registered, mechanical, strict order

### ROW 0a — the recovered instrument does not reproduce its own numbers
**Fires if:** the recovered harness (§3.1) fails to reproduce `B50 = 11.3%`, matched-hit control
median `2.9%`, or THE 135 median `44.0%` **each within 1 pp**.
**Consequence:** the bar is not established on this tree. **No verdict.** Escalate. 🛑 Do not
re-derive the bar from the new run — that is the instrument setting its own threshold.

### ROW 0b — the export is miswired
**Fires if:** on the **matched-hit control** population (things we *did* decode), GRID-arm median
BER **> 5%**, or any `rc != 0`, or the DLL SHA256 does not assert.
**Consequence:** the new export does not reproduce the extraction the decoder actually performs.
**Harness invalid, no verdict**, QA fixes and re-runs. *(This is the HK-022 guard: a green number
from a miswired export would look exactly like a finding.)*

### ROW 0c — underpowered
**Fires if:** fewer than **200 paired rows** survive with both arms measured and a true codeword
available.
**Consequence:** instrument failure, **not a null**. THE 135 measured only 126 of 135; if the
candidate-present-and-failed population cannot be assembled at ≥200 pairs from the available
corpora, say so and stop.

### ROW 0d — the refiner moved nothing
**Fires if:** the median `|Δt|` returned by the refiner is **< 5 ms** AND median `|Δf|` **< 0.25 Hz**
across the population.
**Consequence:** the treatment arm is not a treatment — GRID and REFINED are the same position, so
`d_ber ≈ 0` is guaranteed and means nothing. **No verdict, escalate.** 🔴 *This row exists because
M4 taught us to check that the contrast can move before reading that it didn't.*

### ROW 1 — position is the root cause of the misread
**Fires if:** paired median `d_ber ≥ 15 pp` **AND** CI_lo `> 5 pp` **AND** `f_cross ≥ 0.20`.
**Consequence:** reading in the wrong place is established as a first-order D-001 term. **R2 (wiring
refinement into the decode path) is justified and now SIZED in decode units** — `f_cross` is its
expected recall contribution. R2 becomes scopeable, by the Architect, in a later document.

### ROW 2 — position is not the root cause of the misread
**Fires if:** `|d_ber| ≤ 5 pp` **AND** CI_hi `< 15 pp`.
**Consequence:** 🔴 **limb 1 is DEAD as a D-001 treatment.** Extracting at a better position does not
fix the reading, so the failure is in **how the bits are formed**, not where they are read —
i.e. the non-coherent, magnitude-only, single-symbol metric. **R2 as framed is dead; the next work
is limb 2** (coherent multi-symbol LLRs off the complex baseband `sync_refiner.c:417-449` already
builds and `free()`s). ✅ **This is a real finding, not a void** — it closes a limb.

### ROW 3 — partial
**Fires if:** none of the above. **Consequence:** escalate with the paired distribution and the
per-SNR-stratum table. 🛑 Do not average to a verdict.

---

## 6. HK-025 classification — QA re-derives independently and may refuse

| Row | If it fires, still an estimate of what the gate names? | Class | Both branches |
|---|---|---|---|
| 0a | **No** — an unreproducible bar is not a bar | VALIDITY | fires ⇒ no verdict, escalate; else ⇒ 0b. Different ✅ |
| 0b | **No** — a miswired export measures its own wiring | VALIDITY | fires ⇒ no verdict, fix + re-run; else ⇒ 0c. Different ✅ |
| 0c | **No** — an underpowered pairing is instrument failure, not a null | VALIDITY | fires ⇒ no verdict; else ⇒ 0d. Different ✅ |
| 0d | **No** — a null contrast between two identical positions estimates nothing | VALIDITY | fires ⇒ escalate; else ⇒ ROW 1/2/3. Different ✅ |

All four VALIDITY, none DIAGNOSTIC, none merely changes printed text (HK-021(k)).
🔴 **QA re-derives this independently, including against this paragraph, and may refuse under
HK-025 without my agreement and without escalation.**

## 7. HK-026 self-check

**Is the 11.3% bar derived from the instrument whose blind spot it bounds?** No — `B50` comes from
the **LDPC/OSD** decoder's correction curve, a *different* stage from the demodulator N1 measures.
The demodulator's output is the input to that curve. ✅ *(This is why ROW 0a forbids re-deriving the
bar from N1's own run — doing so would create the violation.)*

**Is `d_ber` such a violation?** No. It is a **paired within-row contrast**, the strongest available
form: each row is its own reference, so no boundary is derived from the instrument's own
distribution. ✅

## 8. Predictions — 🛑 NOTHING GATES ON THESE

| Prediction | Credence | Class + running score |
|---|---|---|
| ROW 2 (position is **not** the cause) | **~55%** | categorical, 5/9 |
| ROW 1 | ~25% | categorical |
| ROW 3 | ~15% | categorical |
| ROW 0a/0b/0c/0d | ~5% combined | categorical |

**I have flipped, and I am saying so loudly.** I have argued for the sync-refinement route since
2026-08-11 and wrote *"R2 is the only thing standing between here and D-001."* Laying the evidence
out for the Captain today, I now think **limb 2 is more likely to be the answer than limb 1** —
because T1 measured the frequency-refinement prize at only ≥3.16 pp, because misses arrive at 44%
BER which is *near-random* rather than *slightly-misaligned*, and because a 6× frequency and 16×
time resolution improvement still leaves a single-symbol non-coherent metric against WSJT-X's
coherent 1/2/3-symbol sums.

🛑 **This prediction is worth little and no row turns on it** — my categorical calls run 5/8 and my
directional calls 1.5/3.5, and I have been wrong in *this specific direction* for four days. The
gate is what decides.

---

## 9. Scope

- 🔴 **`src/`/native IS engaged** (§3.2) — the first time in this thread. **HK-011: QA proposes and
  stops; a separate Developer session applies; the Captain reviews the diff.** New export only;
  existing decode behaviour byte-identical; `FT8_SHIM_VERSION` → **20260042**, new SHA256 pinned and
  asserted.
- 🛑 **No change to candidate selection, no change to the decode path, no OSR change** (barred on
  P3's evidence), no aperture widening, no capture run — the corpora exist
  (`qa/ARTEFACT_INVENTORY.md`; **read it before proposing any capture**).
- 🛑 **M5 is withdrawn and must not be run.** M1/M2/M4 stay void; M3 stands.
- 🛑 **The standing prohibition on R0/R1/R1b's ~1.1 ms / 0.5 Hz figures for real signals REMAINS.**
  N1 does not lift it — N1 measures the *consequence* of using the refiner, not its accuracy. 🔴 **If
  ROW 1 fires, that is evidence the refiner is useful, NOT a licence to quote its accuracy figures.**
- 🛑 **R2 stays unscoped, unproposed and unestimated.** ROW 1 makes it *scopeable*; it does not scope
  it.
- **A2** and **A3** remain open and **must not become a round**. A1 is done.
- HK-014: I commit this locally and stop. I do not push and do not ask.

## 10. What QA delivers

1. The recovered `c2_phase2c_ber_measurement.py` on this branch, with the §3.1 reproduction result
   stated **before** anything else in the report.
2. A `dev-tasks/*.md` proposing the §3.2 export — **QA authors it, QA does not apply it** (HK-000,
   HK-011).
3. `qa/rr-study/n1-ber-at-refined-position/` — harness, committed, with the §4 sign unit test and the
   anchor assertion in code.
4. `results/n1_results.json`, `n1_gate_report.json`, `harness_run.log`.
5. A dated report `qa/rr-study/<UTC>-qa-to-architect-n1-results.md` (HK-017: filename and byline
   mechanically derived and agreeing) with the gate in **strict order**, the paired distribution,
   `f_cross`, the per-stratum table, and the refiner's actual `(Δf, Δt)` distribution so ROW 0d is
   readable.
6. The board updated in the **same edit** as the result (HK-024).

**QA does not author the next spec (HK-015). QA may refuse this one under HK-025 (§6).**
