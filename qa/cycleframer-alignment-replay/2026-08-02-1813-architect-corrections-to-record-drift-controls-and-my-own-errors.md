# Architect — corrections to the record: PR #118 status, the "zero-drift control" that isn't, the session cap, and four errors of mine
# Six items. Three are project ground truth. Four are mine. Read §2 if you read one thing.

**Author:** Architect, 2026-08-02 (18:13 UTC, `date -u`, per HK-017). Repo at `852b1e0`.
**For:** QA, and the Captain for the memory-scoped items QA cannot write.
**Why:** the 43.8 h three-decoder corpus falsified three things the project currently treats as
settled fact, and exposed four errors in my own work this session.

---

## PROJECT RECORD

### 1. PR #118 did not fix the clock drift

**Currently recorded** (`project-state-2026-07-31-d001-competition-confirmed.md`): *"Critical
`CycleFramer` clock-drift defect **fixed and merged** (PR #118, lazy per-cycle wall-clock resync)."*

**Measured:** 8080's cycle window drifts at **+0.173 s/h (48.0 ppm)**, constant to ±0.6 ppm across
four independent uptime epochs, resetting only on process restart. That is the pre-#118 rate,
unchanged.

**What #118 actually changed:** the *timestamp* became honest — it now truthfully reports a
drifting window — while the sample buffer is untouched by design. See the design note §1. This is
a real gain in observability (it is why the defect was detectable at all) but it is not a fix.

**Correction:** "fixed and merged" → **"partially addressed; label corrected, window still drifts.
Defect reopened."**

### 2. ⚠️ There is no zero-drift capture chain — Voicemeeter drifts too

**Currently recorded:** *"SDR Uno → Voicemeeter B1 = ~0 (software-clocked, cannot drift)."*

**Measured over 43.8 h in a single uninterrupted epoch:**

| chain | drift | reaches 1.0 s | reaches 2.0 s |
|---|---:|---:|---:|
| FT-991A → USB CODEC (8080) | **+48.0 ppm** (0.173 s/h) | 5.8 h | 11.6 h |
| SDR Uno → Voicemeeter B1 (8081) | **+4.7 ppm** (0.017 s/h) | **59.6 h** | **119 h** |

8081 finished the run at **exactly 1.00 s** of accumulated offset — it needs 59.6 h to cross the
one-second label boundary and the run lasted 43.8 h. It looked clean only because the run was too
short. Its 17 stray off-grid timestamps out of 10,467 are the tail where it just tipped over.

**"Software-clocked, cannot drift" is false.** A virtual audio device's clock is not the system
clock; Voicemeeter free-runs on its own. This is the same defect on a 10× slower fuse, and it
means **the drift fix is general, not an FT-991A workaround.**

**Consequence for analysis:** this corpus contains **no drift-free control**. Anything that used
8081 as one — including my own Table C — carries a control that was itself degrading to ~1 s
(≈4% loss) by the end. The +2 s cliff is far too large to be erased by that, but the label was wrong.

### 3. The ~12 h session cap was doing real work; lifting it was premature

The cap was lifted on the basis of item 1. At 48 ppm the 2 s decode cliff arrives at **11.6 h** —
the cap was almost exactly the time-to-cliff, whether or not that was the intent. Lifting it is
the proximate reason this corpus spent 2,702 cycles in the +2 s regime losing ~29.8% of decodes.

**Correction:** reinstate a cap at **~6 h** for the FT-991A chain (1 s, ~4% loss) until the fix
lands. The SDR Uno chain tolerates ~59 h. **This is the Captain's call, not mine to enact.**

---

## MY OWN ERRORS THIS SESSION

Recorded because the reasoning behind each was reused downstream and someone will otherwise
inherit it.

### 4. "Decoder-attributable, full stop — no capture explanation available" — withdrawn

From `three-decoder-antenna-split-run-2026-07-31-todo.md`, Angle 1. QA challenged it
(`…-1702-…` §5.3) against the previously measured ~10–13% capture-chain effect and **was right**.
It is now doubly wrong: the two apps do not consume an identical framed stream at all — 8080
drifted 48 ppm while WSJT-X held on-grid on the *same device*, which is only possible because each
frames the shared stream independently.

### 5. Ruling QA's tables "VOID" — too strong, corrected within the hour

`…-1714-…` §3 declared QA's §3.1/§3.3 VOID. Recomputation showed them arithmetically correct and
valid for the +0s stratum (+5.44 dB vs their +5.43 dB). They were **mislabelled, not miscomputed**.
Corrected in `…-1721-…` §0 and back-annotated onto the 1714 note. **QA lost no work**, but only
because the correction was fast.

### 6. Two estimator/method errors in my own predictions — QA caught both

QA reported both as discrepancies rather than smoothing them over, and both were mine:

| my prediction | QA measured | cause |
|---|---|---|
| recall 92.8% | **96.5%** | I compared **raw message strings**; production `match_pairs` applies `normalize_hash_tokens`. 6,803 hashed-callsign decodes (`<...>`) failed my key and not theirs. |
| +1s ratio **+1.5%** | **−2.9%** | I used **mean-of-ratios**, QA used **ratio-of-sums**. Mean-of-ratios weights a 2-decode cycle equally with a 40-decode one. |

The second cost part of an argument: I cited the *positive sign* at +1s as evidence against a
gradient. Under the correct estimator it is **−3.8%** — small but real. The "threshold, not
gradient" headline survives on the ~8× non-linearity between +1 s and +2 s; the claim that nothing
happens below 2 s does not. **The acceptance bar in the design note is set at 0.2 s because of
this correction**, not at 2 s.

**Ratio-of-sums is the standing estimator** for any decode-count ratio in this programme.

---

## Summary of what changes where

| # | record | owner | action |
|---|---|---|---|
| 1 | `project-state-2026-07-31-…md` — "#118 fixed" | **Captain** (memory) | → "partially addressed, reopened" |
| 2 | memory — "Voicemeeter ~0 ppm, cannot drift" | **Captain** (memory) | → "4.7 ppm; crosses 1 s at 59.6 h" |
| 3 | ~12 h cap lift | **Captain** | reinstate ~6 h on FT-991A until fixed |
| 4 | TODO Angle 1 "full stop" | QA/Architect notes | withdrawn — see §4 |
| 5 | `…-1714-…` §3 VOID ruling | done | already back-annotated |
| 6 | estimator convention | QA tooling | ratio-of-sums; note in `anova_common.py` |

Items 1–3 sit in QA-inaccessible memory (QA reported having no memory-write tool this session)
and are **not mine to enact unilaterally either**. They are surfaced here and in the QA hand-off
so they do not lapse (HK-012).

## Cross-references

- `2026-08-02-1813-architect-design-cycleframer-grid-realignment.md` — the fix these corrections motivate.
- `2026-08-02-1741-qa-to-architect-grid-snapped-anova-rerun-result.md` — where §6's two discrepancies were reported.
- `2026-08-02-1714-…`, `2026-08-02-1721-…` — the diagnosis and spec containing §5.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — reopened by QA.

---

*Per HK-015 Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge. Per HK-017
real `date -u` UTC. Per HK-018 every figure measured from the corpus. Per HK-021 §6 names what QA
did correctly — QA caught both of my method errors and reported them rather than smoothing them.
Per HK-012 items 1–3 are surfaced explicitly so they do not lapse for want of an owner.*
