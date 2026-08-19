# ARCHITECT RULING — AO1 Part C ACCEPTED, arm CLOSED, and a ledger figure of mine corrected

**2026-08-19 12:17Z · Architect · on QA's 12:11Z Part C report**

**Status: C2 ACCEPTED. AO1 is CLOSED. No re-run, no further arm, no `src/` change authorised here.**

---

## 1. The ruling

**ROW C2 is accepted as reported.** `L = +0.706 pp`, CI95 `[+0.492, +0.926] pp`,
`1.96·SE = 0.223 pp` — powered, clear of the C0 bound by ~4.5×, and clear of **both** the C2/C3 and
C2/C1 boundaries. **This is not a straddle**, and the contrast with ROW 0f is the point: a gate
drafted with its resolution stated in advance separated the bars; one drafted with a tolerance equal
to its own grid step could not.

**The consequence is the pre-registered one, unchanged:** the ROW 3 production framing defect
carries a **real, small recall cost — fix it on product grounds, not as a D-001 route.** It does not
displace Route B in any sizing document.

**AO1 is closed.** Part B (ROW 3, confirmed-in-part) and Part C (C2) both have their answers. The
only live descendant is the drift question, which stays **deferred and unarmed** (11:55Z ruling §7).

QA's run was faithful to the ruling: `run_part_c()` called unmodified, DLL re-hashed and asserted
before arming, ROW 0g re-evaluated fresh rather than inherited, all three mandatory disclosures
carried, C0 evaluated first and strictly. I accept it without qualification.

---

## 2. An audit I ran on `L`, and its outcome — reported whichever way it fell

Before accepting, I checked one structural property of the statistic. `compute_L`
(`run_ao1.py:264-289`) sums `(n_d / total_n) × (modal_recovery − d_recovery)` over non-modal `dt`
strata, and **skips the modal stratum entirely** (`:281`). So **any recall cost the offset imposes
equally on all `dt` strata cancels exactly.** `L` is a pure **contrast**; it is structurally blind to
a **level**. With the modal stratum holding **80.7%** of the population, that blind spot is not
small in principle.

**The concern was: is `+0.706 pp` a lower bound rather than a sizing?** If a constant ~0.65 s buffer
misplacement cost recall *uniformly* — e.g. by truncating ~5% of every signal's energy — `L` would
report ≈0 of it, and C2 would understate the defect.

🔴 **I checked it in code, and it does not bite. The answer validates C2.** An FT8 transmission
occupies **12.64 s** of the 15 s slot, so a signal fits entirely inside our 15 s buffer for start
positions spanning **2.36 s**. A constant offset **translates** that acceptance window; it does not
**narrow** it. In reference-`dt` terms the window moves from roughly `[0, +2.36]` to `[−0.65, +1.71]`
— **same width**. The modal stratum `[0.0, 0.5)` sits comfortably inside **both**, so it is an
uncompromised baseline, and the entire cost lands in the **tails** — which is exactly and only what
`L` is built to see. (`ft8_shim.c:744-745` skips out-of-buffer symbols rather than rejecting the
candidate, so the tail effect is graded, not a cliff — which softens the edge but keeps it tail-
concentrated.)

✅ **Unplanned corroboration, worth recording.** That mechanism predicts loss concentrated above
`dt ≈ +1.7 s`. QA's own stratum table has **361 + 81 + 1 = 443 rows above +1.5 s, ≈1.0% of the
population** — the right order of magnitude for a `+0.706 pp` effect, from a direction nobody
designed the statistic to test. Two independent routes to the same size.

🛑 **Stated plainly: I went looking for a reason the number might be understated, and did not find
one.** I am recording that I looked, because the search was motivated — it is the mirror image of
the bias I flagged in myself at 11:55Z, and it would not have been visible if it had quietly
returned nothing.

---

## 3. A figure of mine in the D-001 ledger was never coherent, and C2 exposes it

The 18:24Z investigation ledger gives **"the anchor-offset question — 20%"**, against its own
definition of *solve* := **closing ≥ half the 20m gap** (57.8% → ≥79%, i.e. **≈21 pp**).

AO1's own pre-registration, which I wrote **six days later**, says at §10: *"the largest credible
recall figure in play is ~2 pp against a ~42 pp gap."*

🔴 **Those two statements were incompatible the moment the second was written.** A route I had
myself ceilinged at ~2 pp cannot have had a 20% chance of delivering ~21 pp. **C2 did not refute the
20% — my own §10 already had, and I did not notice.** The measurement merely made it unmissable.

**Correction, applied to the ledger's framing:**

| ledger line | was | now |
|---|---|---|
| the anchor-offset question | **20%** (credence) | 🔴 **~0% as a D-001 solve — MEASURED, not estimated.** `L = +0.706 pp` [+0.49, +0.93]. **The first ledger line settled by measurement rather than credence.** |
| aggregate: ship a ≥half-gap fix | ~55% | **lower — I will not put a second decimal on it.** A route dying **subtracts**; it does not reshuffle into the survivors, because these are distinct mechanisms, not competing explanations of one phenomenon. |

⚠️ **Route B2 (45%), Route A framing phase (12%), X1+X2 (8%), B1/C/D-009B (8%) are UNCHANGED.**
Nothing measured here bears on any of them. 🛑 **The ledger's §11 citation limit stands in full: no
probability in it may be cited in, inherited by, or gated on in ANY pre-registration.** These are
Architect credences at **7/12 categorical**, and this section is a worked example of why.

---

## 4. Harness state, recorded so it is not rediscovered

QA flagged, correctly, that `run_ao1.py:662`'s `and not qcheck["fires"]` clause is **still live**.
The 11:55Z ruling struck the clause's *authority to block*, not the line. 🔴 **A future full
`run_ao1.py` re-run would still skip Part C at that line** and would need the same manual override
`run_part_c.py` performs. Not a defect to fix on its own account — but do not mistake the code for
carrying the ruling.

Also still open from 11:55Z §4, unfixed and unaffected by this result: the float-boundary comparison
at `:443` (compare grid-quantised quantities in **integer step units**), and the HK-021(l)
absolute-value in `quartile_check`.

---

## 5. What I recommend to the Captain — decisions, not actions

1. 🔴 **Open a Developer session for the `CycleFramer` fix (HK-011).** Justified on **product**
   grounds: `CycleFramer` does not achieve its own documented intent (`:184` — "spans the wall-clock
   interval `[G, G+15]`"), our published `dt` is wrong by ~0.7 s, and the recall cost is now
   measured rather than asserted. **Not authorised by this document** — Developer session + your
   sign-off, and the diff is yours to review.
2. **Do not let it jump the queue.** +0.7 pp against a ~42 pp gap. It is correctness work with a
   small recall dividend, not a D-001 treatment, and Route B2 remains the D-001 route.
3. **The drift arm stays unarmed** unless something needs the offset asserted as one constant.
   Nothing currently does.
4. **GitHub #3/#111 cross-reference** is still outstanding — carried from the 11:35Z report, now
   two rounds old.

---

## 6. Calibration

| prediction (AO1 §8, pre-registered) | outcome | result |
|---|---|---|
| Part C row **C2**, `L` ∈ **[+0.2, +1.0] pp** | **C2, `L` = +0.706 pp** | 🔴 **HIT — categorical and range, mid-range** |
| Part C power: ~50/50 that C0 fires instead | C0 did not fire, ~4.5× clear | **scores nothing — a 50/50 call is uninformative by construction.** I should have committed to a side. |

**Running tally after this arm: categorical 8/13 · ranges 11/19 · directional 2.5/5.5 ·
mechanical 3/4.**

⚠️ **The range hit is worth less than it looks.** I had seen S4's naive `+0.5 pp` tail arithmetic
while drafting and disclosed it (pre-reg §2). My `[+0.2, +1.0]` band was **anchored on it**, which is
the exact under-dispersion failure my calibration note already warns about. Scored as a hit because
the pre-registration scored it that way; **read as weak evidence of judgement.** The categorical C2
call is the part that carries weight.
