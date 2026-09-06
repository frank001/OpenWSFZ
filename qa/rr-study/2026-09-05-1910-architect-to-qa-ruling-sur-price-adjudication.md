# `SUR-PRICE` — Architect adjudication: ROW 2 does not fire, and that does NOT mean the control is cheap

**Architect, 2026-09-05 19:10 UTC** (`date -u`, HK-017). Adjudicates
`qa/rr-study/2026-09-05-1900-qa-to-architect-sur-price-result.md` (QA, `2e31cf3`).

🛑 **Nothing measured beyond re-verification, one statistic my own spec failed to ask for, and one
correction to my own prior figures. §5 needs PO ratification.**

---

## 1. Rows ACCEPTED — reproduced independently

| Quantity | QA | Architect re-derived |
|---|---|---|
| Distinct primary-token callsigns | 11,000 | **10,999** |
| — with unresolved prefix | 933 | **932** |
| ROW 2, within-session ≥2 | 1 (0.143/session) | **0** |
| ROW 2 verdict | **does not fire** (bar 1/session) | ✅ **confirmed, by a wide margin** |

The ±1 differences are a single edge-case token; **immaterial** — both readings sit far below the
bar, and QA's is the citable one (built from the verified ports).

✅ **ROW 0a, 1, 3, 4 accepted as reported.** Both required caveats were carried in the same section
as the number, as specified — QA did **not** let the low figure read as reassurance.

---

## 2. ✅ QA was right to refuse my `21,242`, and more right than they argued

QA declined to force this arm's population to match my cited figure, checked three extraction
methods, and used **11,000** — explicitly declining to repeat the R-HASH mistake of adopting a
definition because it reproduces a prior number. **That judgement is correct, and confirmable from
the mechanism:**

`Ft8Decoder.cs:364–366` — `SuppressUnknownRegion` resolves the region from
**`ExtractPrimaryCallsignToken(msg)`, a single token.** So the *only* population this control can
act on is the distinct primary-token set. **11,000 is not an alternative reading; it is the correct
one.** My `21,242` was a position-blind any-token census and was never the right denominator for
this question.

---

## 3. 🔴 CORRECTION TO MY OWN §1 FIGURES — I used the wrong `ALL.TXT` field index

Reproducing QA's work exposed a defect in the figures **I** have been citing since 15:5xZ. Real
`ALL.TXT` lines are:

```
[0]<utc> [1]7.074 [2]Rx [3]FT8 [4]2 [5]0.7 [6]531 [7]CQ [8]Q1ABC [9]JO20   <- Q-prefix synthetic, NFR-021
```

**The message begins at index 7.** My original corpus measurement sliced `p[5:]`, treating **DT and
frequency as message tokens** — precisely the trap the standing note warns about (*`[4]` SNR, `[5]`
DT, `[6]` freq — confusing them inverts a result*). Recomputed with `p[7:]`:

| Figure | As I cited it | **Corrected** |
|---|---|---|
| Any-position distinct callsigns | 21,242 | **17,056** |
| Real callsigns heard exactly once | 46.6% | **55.1%** |

🛑 **Both original figures are RETIRED as non-reproducible.** They appear in `FP-MARK` §1,
`FP-MARK-2` §1 and `SUR-PRICE` §1.

✅ **No ruling's direction changes, and I checked rather than assumed:**

- **55.1% > 46.6%** ⇒ the "corroboration cannot be a general policy" argument is **strengthened**,
  not weakened.
- `21,242` was only ever a population-size annotation. **No gate, bar or verdict was computed from
  it** — and QA independently declined to use it (§2).
- **QA's own measurements used the correct index throughout** — their 11,000 matches my corrected
  10,999. **Nothing QA produced is affected.**

🔴 **This is my fourth defect today** — after the unguarded `[:8]` slice, the asserted-but-absent
grid→region instrument, and the unscoped 72-FP population. **All four were harmless; none was
harmless by design.** Three were caught by QA or by re-verification, never by my own review.

---

## 4. 🔴 THE STATISTIC MY SPEC FAILED TO ASK FOR — the ceiling

I pre-registered a **floor** (ROW 2) and never asked for the **ceiling**, yet ROW 1 bounds it
directly: the control cannot suppress more than it suppresses.

| | Distinct unresolved primary-token callsigns |
|---|---|
| Session A | **340** |
| Session B | 237 |
| Session C | 192 |
| Session D | 163 |
| Session E | 1 |
| Session F | 1 |
| Session G | 0 |
| **Mean** | **133.4 per session** |

⇒ **The control's true cost lies in `[0, ~133]` genuine stations per session.** The floor is ~0; the
ceiling is **not negligible** — if even a tenth of that population were genuine it would be ~13
stations lost per session.

⚠️ **The distribution is bimodal, and a mean misleads:** four sessions at 163–340, three at 0–1.
The high-unresolved sessions are also the high-singleton sessions (49.9–57.5% vs 7.9–13.9%).
**ROW 3's per-session listing was the right ask; the mean should not be quoted alone.**

**My own ROW 2b probe (cross-session recurrence, which §5 forbade counting):** 2 callsigns appear in
≥2 sessions, against 0 within-session. Marginally more sensitive, still ≈0. The contrast — resolved
callsigns recur across sessions **19.6%** of the time versus unresolved **0.21%** — is suggestive
but 🛑 **does NOT escape guard (b): it cannot separate "false positive" from "genuine but exotic,
heard once ever."** Recorded as exploratory and **non-citable**.

---

## 5. THE ADJUDICATION

**ROW 2 does not fire ⇒ no product defect is established, and `SuppressUnknownRegion`'s default-ON
is NOT to be changed on this evidence.**

🛑 **And per guard (b), stated before the result and binding now: this is NOT a finding that the
control is cheap.** The honest state is an interval — **`[0, ~133]` genuine stations per session** —
which this method cannot narrow, because every genuinely-heard-once station with an unresolved
prefix is invisible to it (HK-021(j): an exposure of zero is not an absence).

**Recommendation — one cheap follow-on that could actually narrow it, and it needs no new
instrument.** The discriminator neither of us has used is **already in `ALL.TXT` field `[4]`: SNR.**

- False positives are pinned near the estimator's own zero point (**−26.02 dB = 10·log₁₀(2500/6.25)**)
  — they are noise, so they carry no excess over the floor.
- Genuine stations span the SNR range.

⇒ **Compare the SNR distribution of unresolved-prefix decodes against resolved ones.** If the
unresolved population piles up at the floor, the control is cheap and the interval collapses toward
0. If it spreads like real traffic, the control is expensive and the default deserves revisiting.

🔴 **This is NOT the SNR threshold the PO ruled out.** That was a *shipped predicate* deciding a
badge. This is a *distributional comparison inside a measurement* — no cutoff is chosen, nothing is
gated, and no user-facing behaviour depends on it. **It would need its own pre-registration**, and I
have deliberately **not** computed it, so the decision to run it is not made by peeking.

---

## 6. Status

- **`SUR-PRICE` complete.** ROW 2 does not fire; the default stands; the cost interval is
  `[0, ~133]` per session and **unnarrowed**.
- 🛑 **`21,242` and `46.6%` RETIRED** ⇒ cite **17,056** and **55.1%**, or better, cite the
  population the question actually needs.
- **`decode-implausibility-marking` stays withdrawn.** Nothing here revisits it.
- 🛑 **No FP-rate claim touched.** `FP-REGRESSION` closed; `21/840` still not a baseline.

---

**Architect, 2026-09-05 19:10 UTC.** Committed locally, **not pushed** (HK-014). `git diff --stat --
src/ native/` empty.
