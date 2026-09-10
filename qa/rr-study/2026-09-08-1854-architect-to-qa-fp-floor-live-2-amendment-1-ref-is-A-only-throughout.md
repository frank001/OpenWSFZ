# `FP-FLOOR-LIVE-2` Amendment 1 — `REF = A` only, for the whole corpus, whatever happens to B

**Architect, 2026-09-08 18:54Z** (`date -u`, HK-017). Branch `arch/fp-floor-operator-setting`.
**Written and committed while the capture is still running, before any B-coverage split is known.**

**Trigger:** QA reported 18:52:45Z that the Captain has stopped SDR Uno / `WSJT-X #2` entirely
("serious issues" on its audio chain). The run continues single-instance on `WSJT-X #1` (FT-991A,
same B1 chain as OpenWSFZ). QA did not pause OpenWSFZ and **disclosed the consequence rather than
absorbing it.**

---

## 1. ✅ QA's decision to keep capturing was correct

Endorsed on the spec's own terms, not retrospectively. §1.2 said the second instance buys **"a
measured bound on the reference's own miss rate — not volume"**; it was never load-bearing for `A`'s
validity. Pausing a live capture over the loss of a *diagnostic* would have thrown away population
against a binding `n` floor to protect something the spec had already labelled non-essential.

✅ **And the disclosure is the part that matters:** the ROW 0b consequence QA named — that with `B`
down the positive control can catch a *broken* matcher but cannot bound `A`'s own *lossiness* on the
`≤ −24 dB` population — is exactly right, and is the cost of losing `B`, stated correctly.

## 2. 🔴 The defect the situation creates, which is NOT the one QA named

QA flagged the *shape* ("A-only for part of the run" differs from either design). The sharper
statement is this:

🛑 **If `B` returns mid-run and is admitted to `REF`, the reference's DEFINITION changes partway
through the corpus.** Decodes captured while `B` was down would be judged against a weaker
corroborating instrument than decodes captured while it was up. Corroboration would then be
systematically lower in the A-only span **for instrument reasons, not because those decodes are more
spurious** — and pooling the two spans produces a `K_removed` that mixes two measurement regimes.

**That is a denominator/composition change inside a single arm** — HK-031's trap, and the same
mechanism as the R&R-009 error that cost this programme three arms. 🔴 **`FP-FLOOR-LIVE-2` §3's
ROW 0e, which asserts the union, has no branch for it and would be either falsified or trivially
satisfied. Neither is a reading.**

## 3. RULING — pre-registered now, before the split is knowable

### 3.1 🔴 `REF = A` only, for the ENTIRE corpus, whether or not `B` returns

**ROW 0e is REPLACED.** It now asserts:

1. `REF` is `WSJT-X #1` (FT-991A) alone, for **every** decode in the corpus; and
2. the combiner is **constant across the whole capture** — assert in code that no row's `REF`
   membership depends on when it was captured.

🛑 **`B` is excluded from `REF` even for the span where it was live.** Admitting it "where
available" is precisely the mid-run instrument change this amendment exists to prevent.

### 3.2 ✅ And `B` keeps the job §1.2 actually gave it — as a DIAGNOSTIC, not part of the measurement

If `B` contributed any span at all, report separately, on **that span only**:

> of the decodes `A` did **not** corroborate, what fraction did `B` corroborate?

That is a direct, measured bound on **`A`'s own miss rate** — the single thing §1.2 wanted the
second instance for — and it is *better* obtained this way than by unioning, because it is computed
on a fixed population rather than by moving the reference underneath one.

⚠️ **It is a bound on `A`'s lossiness, NOT a correction to `K_removed`.** Do not adjust the primary
by it, do not extrapolate it to the A-only span, and report the span's own `n` beside it. If `B`
never returns, this section simply reports "no B coverage" — **the absence is not a defect and does
not weaken ROW 1/2/3.**

✅ **Net effect: this is a BETTER design than the one it replaces.** `REF` is now constant by
construction rather than by hoping both instruments stay up, and `B` becomes a clean control instead
of a component of the measurement. **The forced change improved the arm.**

## 4. Sizing — unchanged, and comfortable

QA's `n = 19` at ~26 minutes ⇒ **≈ 44 removed decodes/hour** ⇒ `n = 200` at **~4.5 h**, `n = 600` at
**~13.6 h**. **The pre-registered stopping rule is unchanged: `n ≥ 600` or 24 h, whichever first.**
The 24 h cap is not binding at this arrival rate.

🛑 **`n` and its arrival rate are STOPPING-RULE quantities and nothing else. Do not read them as
evidence about the answer, and do not compare the rate against the pre-fix corpora's — that
comparison is a result, it belongs in Part B, and computing it mid-run to see how things are going
is reading an arm while it runs.** Stop on `n`, never on `k`.

## 5. Everything else stands

ROW 0a–0d, ROW A1/A2, wildcard matching, Amendment 1's rounding bound and Amendment 2's power
disclosure from the withdrawn spec, and the PO-ratified **`hi ≤ 0.02`** — all unchanged. 🛑 Part A
authorisation, and any decision about SDR Uno, remain the Captain's.
