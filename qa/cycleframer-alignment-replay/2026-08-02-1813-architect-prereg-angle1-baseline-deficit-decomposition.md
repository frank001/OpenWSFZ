# Architect — PRE-REGISTRATION: D-001 Angle 1, decomposing the baseline deficit
# ▶ DOCUMENT 2 OF 2 for QA. Read the 2316 hand-off first. See README.md for the full order.
# 🟢 AUTHORISED by the Captain 2026-08-02 23:45 UTC. Amended twice pre-authorisation, pre-data (N3 guard, ROW 5) — no threshold changed.

**Author:** Architect, 2026-08-02 (18:13 UTC, `date -u`, per HK-017). Repo at `852b1e0`.
**For:** QA to execute **only on the Captain's authorisation**.
**Discipline:** S.1 precedent — anything reading this corpus is pre-registered *before* it sees the
data. I have deliberately **not** computed the primary metric, though it was one line away with the
data open. Everything cited below is either already-published totals or drift-defect characterisation.

---

## 1. The question

**Is OpenWSFZ missing decodes, or was the signal not there to be had?**

D-001's baseline deficit (~34% on record) has always carried that ambiguity. Every prior corpus
confounded it: the comparison decoder sat on either a different capture chain or a jt9 re-decode
of our own audio. Neither isolates the decoder.

## 2. Why this corpus can answer it now, and could not this morning

Two things changed today:

1. **Drift is separable.** The +0s stratum — 3,635 cycles where 8080's window sat on the UTC grid —
   is a drift-free population. Before today the drift was smeared invisibly across everything.
2. **The jt9 leg is rehabilitated.** In `…-1714-…` §8.4 I recommended *against* the jt9 re-decode,
   because it would re-decode WAVs carrying misaligned windows — "a third measurement of the same
   defect, not a third opinion." The Captain agreed and it was dropped. **On the +0s stratum that
   objection disappears**: those WAVs are grid-aligned. jt9 goes from worthless to decisive.

**I am reversing my own recommendation and saying so plainly.** The earlier call was right for the
whole corpus and wrong for this subset.

## 3. Design — a genuine 2×2

| leg | capture framing | decoder | source |
|---|---|---|---|
| **A** | ours (8080) | ours | 8080 live `ALL.TXT`, +0s cycles |
| **B** | ours (8080) | theirs | **jt9 offline over 8080's +0s WAVs** |
| **C** | theirs (WSJT-X) | theirs | WSJT-X live `ALL.TXT`, same cycles |

```
decoder-attributable  =  B - A      (identical audio bytes, different decoder)
capture-attributable  =  C - B      (identical decoder, different capture framing)
total deficit         =  C - A
F_dec                 = (B - A) / (C - A)      <- the primary statistic
```

**Population:** cycles present in all three legs, `offset == 0` on 8080, both 8080 segments
(§2 of the 1702 note) pooled. **Estimator: ratio-of-sums, never mean-of-ratios** (corrections
note §6). **Matching:** exact `(ts, normalize_hash_tokens(message))`, no grid-snap needed on this
stratum.

## 4. Pre-registered decision rows — mechanical, ordered, mutually exclusive

Evaluated in order; the first matching row is the verdict.

```
ROW 0 (guard):  B < A          ⇒ STOP, DO NOT INTERPRET.
                jt9 decoding fewer than our own decoder on our own audio
                inverts the design's premise. Report and escalate.

ROW 1:  (C - A) / C <= 0.05    ⇒ NO MATERIAL DEFICIT on this corpus.
                D-001's baseline deficit is not reproduced here; the premise
                needs re-examination before any B.3 menu row is costed.

ROW 2:  F_dec >= 0.70          ⇒ PREDOMINANTLY DECODER-ATTRIBUTABLE.
                Decoder-sensitivity work is justified; B.3 rows targeting the
                decoder address the dominant mechanism.

ROW 3:  0.30 < F_dec < 0.70    ⇒ MIXED. Both mechanisms material.
                No single-mechanism design is sufficient; any B.3 row that
                addresses only one must state the residual it leaves.

ROW 4:  F_dec <= 0.30          ⇒ PREDOMINANTLY CAPTURE-ATTRIBUTABLE.
                Decoder work is misdirected. Capture chain becomes the priority.

ROW 5 (catch-all): no row above fired
                ⇒ NO VERDICT. Report and escalate. Reachable only if F_dec is
                NaN or infinite (degenerate denominator: C == A, or an empty
                leg). Rows 1-4 are exhaustive over the reals but NOT over
                float("nan"), which compares False against every threshold.
```

⚠️ **AMENDED 2026-08-02 23:40 UTC, before authorisation and before any data was seen.** ROW 5 did
not exist in the original draft, which asserted rows 1-4 were exhaustive. They are not: a NaN
`F_dec` matched no row and the pre-registration produced no defined outcome. Surfaced by QA's
`ratio_of_sums()` (T3 item 4) returning NaN on a zero denominator, then verified by execution.
**No threshold changed; this only makes an undefined case defined.**

## 5. Mandatory nulls — any failure ⇒ VOID

Per the S.1 precedent, where a null failed structurally and voided the arm.

```
N1  IDENTITY:  leg A matched against itself must give recall exactly 1.0000.
               Anything else ⇒ VOID (the matcher is broken).

N2  GRID GATE: G >= 0.99 on the analysed subset for all three legs
               (G per the 1714 correction §6).          Else ⇒ VOID.

N3  INSTRUMENT: jt9 must be calibrated against live WSJT-X before leg B is
               comparable to leg C. Run jt9 over WSJT-X's OWN WAVs for the same
               cycles; it must reproduce WSJT-X's live count within +/-5%.
               NOT isfinite(|jt9(WSJTX wav) - C| / C)   ⇒ VOID.   <- see below
               |jt9(WSJTX wav) - C| / C > 0.05          ⇒ VOID.
               WSJT-X WAVs unavailable                  ⇒ verdict is INDICATIVE,
               not MEASURED, regardless of which row fires.
               STATUS 2026-08-02: WAVs ARE available -- 10,469 on disk, 99.97%
               coverage (T1 closed). MEASURED is reachable.

N4  DEDUP:     jt9 output must carry zero duplicate (ts, message) pairs, as
               already verified for both live logs.     Else ⇒ VOID.
```

⚠️ **AMENDED 2026-08-02 23:40 UTC, before authorisation and before any data was seen — N3's
explicit non-finite guard.** NaN compares `False` against every threshold, so the direction of a
null decides whether it fails safe:

| null | form | on NaN | |
|---|---|---|---|
| N1 | `!= 1.0 ⇒ VOID` | VOID | fails **closed** ✅ |
| N2 | `>= 0.99 else VOID` | VOID | fails **closed** ✅ |
| **N3** | `> 0.05 ⇒ VOID` | **no VOID** | failed **OPEN** ⚠️ |

**N3 was the one null that could silently pass on degenerate data**, and it is the null T1 was run
to enable. A VOID-on-exceed test fails open; a VOID-unless-met test fails closed. Per HK-021 a
pre-registered check must be able to *fire* — a threshold that no input can trip is not mechanical,
it is decorative. **No threshold changed.**

## 6. ⚠️ Named confound: a-priori (AP) decoding

WSJT-X performs multi-pass decoding with **a-priori information** — it exploits knowledge of the
operator's own callsign and current QSO partner to decode signals below the standalone threshold.
That is a genuine decoder capability, but it is **not** general sensitivity, and it inflates leg C
against any decoder not doing it.

**Required:** record the jt9 invocation flags and WSJT-X's live decode-depth/AP settings, and
report `F_dec` **with AP-eligible decodes excluded as a sensitivity analysis** alongside the
headline figure. If the two differ by more than 10 points, AP is a named sub-mechanism in its own
right and must be reported separately rather than folded into "decoder-attributable."

Failing to separate this would attribute a feature gap to a sensitivity gap and mis-cost the
entire B.3 menu.

## 7. Stated in advance, so nothing can be reverse-fitted

- Already-published totals give a whole-run 8080/WSJT-X ratio of **0.521**. Drift-correcting that
  moves it to roughly **0.573**. So a material deficit is expected to survive on the +0s stratum —
  ROW 1 firing would itself be a surprise worth investigating.
- Drift accounts for ~9% of achievable decodes. It is **not** the explanation for D-001, and this
  measurement is not expected to find that it is.
- I hold **no prior** on ROW 2 vs ROW 3 vs ROW 4. That is the entire point of running it.

## 8. What this does NOT do

- **Does not touch the S.1 VOID.** That null failed structurally and its redesign is independent.
- **Does not address the density penalty** (~19.8 pts). That is the other D-001 mechanism and
  needs its own pre-registration — the question QA's 1702 §6.3 raised. It becomes tractable once
  this lands, on the same drift-free stratum.
- **Does not settle ~48% vs ~34%.** Whether this corpus's gap and the recorded baseline deficit
  are the same metric is unresolved; the two must not appear in one sentence until reconciled.

## 9. Cross-references

- `three-decoder-antenna-split-run-2026-07-31-todo.md` — Angle 1 as originally framed ("full stop" withdrawn).
- `2026-08-02-1714-…` §6 — the G gate used by N2; §8.4 — the jt9 recommendation this reverses.
- `2026-08-02-1741-qa-to-architect-…` — Tables A/B/C and the +0s stratum this builds on.
- `2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md` §3 — the ~10–13% capture-chain effect leg (C−B) should recover.

---

*Per HK-015 Architect → QA: design mine, execution QA's, on the Captain's authorisation only. Per
HK-014/HK-010 committed locally, no push, no merge. Per HK-017 real `date -u` UTC. Per HK-021 §4
and §5 are mechanical — hard thresholds, consequences as assertions, rows exclusive and ordered,
written as code that could be evaluated without judgement. Per HK-018 §7 states expectations from
already-measured data before the primary statistic is computed. Per HK-004 §2 reverses a prior
recommendation of mine rather than leaving it to stand by default. NFR-021: aggregates only.*
