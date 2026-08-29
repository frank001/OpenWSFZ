# ARCHITECT — **P2 WAIVER RETRACTED** by the Captain, and a **correction** to my own validity flag

**Author:** Architect (recording the Captain's decision; HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 19:50:21Z
**Captain's direction, verbatim:** *"I retract the waiver on P2"*
**Supersedes:** the P2 waiver of 2026-06-22, and **corrects §3/§4 of my own 19:40Z report**.

---

## 1. The retraction

🔴 **The P2 waiver of 2026-06-22 is RETRACTED, effective now. P2's failure counts against the product
again.** It is a live D-001 target, not an excused structural gap.

Immediate consequences:

- **The S7 headline reverts to the unadjusted `19.07 pp`.** The "fair figure excluding P2" of
  **14.50 pp** is **withdrawn** and must not be quoted again — it existed only because of the waiver.
- **P2's 12 net missed observations (5.58 pp) return to the accountable gap.**
- Spec `WIN-A` §8's exclusion (*"does not revisit P2, which the Captain waived"*) is spent — that arm
  is closed, so this is a record correction only, not an operational one.
- ✅ **The waiver's own wording problem is now moot** — there is no waiver left to re-word. What must
  be carried forward instead is the **accurate description** (§3).

---

## 2. 🔴 CORRECTION — my "scenario-validity" flag was over-called. I withdraw it

My 19:40Z report flagged S7's capture family as having a **validity problem** and put *"~12.6 pp of
the 19.07 pp is under a validity question"* on the board. 🔴 **That framing was wrong, and I withdraw
it.** Checking WSJT-X's per-part scores — which I should have done before writing it (HK-018, second
time today on my own work) — settles it:

| part | geometry | WSJT-X | OpenWSFZ |
|---|---|---:|---:|
| P12 | 2 sig, 9 Hz, 0 / −6 dB | **10/10** | 5/10 |
| P13 | 2 sig, 7 Hz, 0 / −10 dB | **10/10** | 5/10 |
| P14 | 2 sig, 11 Hz, 0 / −13 dB | **10/10** | 5/10 |
| P2 | 3 sig, 8+11 Hz, all 0 dB | **12/15** | **0/15** |

✅ **WSJT-X recovers every weak signal in the capture family, 10/10 on all three parts, both runs.**
The audio therefore contains exactly what the truth rows claim. **The scenario is not broken and the
capture family is not an artefact.** No part of the 19.07 pp is under a validity question.

**What actually survives, restated correctly:** OpenWSFZ recovers a −6 dB signal at **0 Hz**
separation (S8's 1500 Hz pair, 10/10 across runs) but not at **9 Hz** (P12, 0/5). That remains
genuinely odd — wider separation performing worse — and it remains worth understanding. But it is an
**OpenWSFZ behaviour on valid audio**, not a defect in how the test was built.

🔴 **This makes the deficit *stronger* evidence, not weaker.** Every failing cluster now carries an
**existence proof**: a reference decoder recovers these signals from the identical audio, so none of
it is a physics limit. What I had written as "the target may be illusory" is the opposite of the
truth — the target is real and demonstrably achievable.

⚠️ **Recorded against myself:** I flagged a validity doubt without checking the one number that
resolves it, and it was on the board for ten minutes before I caught it. The `WIN-A` ROW 0e result
made me too willing to believe the battery was misleading us.

---

## 3. What P2 actually is — the description to carry forward

Since there is no waiver left to re-word, this is the record:

**Three stations transmitting simultaneously, all at exactly equal power (0 dB), at 1492 / 1500 /
1511 Hz — 8 Hz and 11 Hz apart, spanning 19 Hz.** An FT8 signal is ~50 Hz wide (8 tones × 6.25 Hz),
so the three overlap heavily.

🔴 **What makes it a sharp question rather than a vague "stacking is hard":**

- **The overlap is not the obstacle.** OpenWSFZ solves every pairwise spacing inside P2 at **10/10**
  with two signals — P8 (8 Hz) 10/10, P19 (8 Hz) 10/10, P9 (11 Hz) 10/10, P10/P20 (9 Hz) 10/10.
- **The failure is total.** Zero of three, never one, never two, across **45 trial-signal
  opportunities and nine runs — 135 observations, no variance.** A capacity ceiling would leak one
  or two through.
- **It is not a signal-count limit.** S8 carries **12 simultaneous signals** per cycle at **91.67%**.
- **It is demonstrably solvable.** WSJT-X: **12–15 of 15**, consistently.

⇒ **Three equal-power signals within ~19 Hz yield zero decodes, at spacings solved perfectly with
two, while twelve spread across the band are fine.**

---

## 4. The accountable gap, with the waiver gone

From `22b749c` (the clean run; `872ba65` is confounded and is not the reference):

| cluster | parts | net gap | pp | status |
|---|---|---:|---:|---|
| **P2 three-signal** | P2 | **12** | **5.58** | 🔴 **NOW LIVE** — existence proof, WSJT-X 12/15 |
| Capture, weak ≥6 dB down | P12/P13/P14 | 15 | 6.98 | ✅ real, existence proof, WSJT-X 30/30 |
| Tight separation | P15, P4, P0 | 14 | 6.51 | ✅ real, existence proof |
| ΔF 13 Hz | P1 | 2 | 0.93 | real |
| OpenWSFZ ahead | P3 | −2 | −0.93 | ✅ we beat WSJT-X |
| **total** | | **41** | **19.07** | |

⚠️ **In the clean run, P2 is the ONLY part where OpenWSFZ scores zero.** Every other deficit is
partial. That singularity is itself the most interesting property it has.

⚠️ **Context that has not changed:** the realistic scenario (S8) sits at **55/60 vs WSJT-X's 58/60** —
a three-decode gap, stable across three runs. S7 is an adversarial battery, and 13 of 21 parts are
at parity or better. The 19.07 pp is a torture-test figure, not product standing.

---

## 5. Direction requested — nothing starts without it

The waiver is retracted and recorded; that alone required no work. What it opens:

1. **P2 is now the largest single addressable cluster with a clean existence proof**, and the only
   total-zero part. If any target deserves the next arm on evidence, it is this one.
2. 🛑 **I am not proposing an arm.** D-001's record is that every mechanism proposed has failed, and
   the last one failed on a preflight row I wrote without a method. **Before any `P2-*` arm is
   drafted I want to do the HK-018 pass I flagged earlier** — read the accumulated D-001 ledger
   properly rather than design off a fresh idea.
3. ⏳ Still outstanding and unrelated: pull the `trend.csv` row; commit the harness change (it is the
   standing instrument and has no identity); restore `main`'s `bc8efcf1…` DLL into the tree.

🛑 Nothing here authorises a scenario edit, a `src/`/`native/` change, an arm, or a merge. Per HK-014
committed locally, not pushed.
