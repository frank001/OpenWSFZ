# D-001 — Architect Decision: Is H7 (MMSE Joint Demodulation) Now Due?

**Date:** 2026-07-07
**Raised by:** QA
**Audience:** Architect
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Current decoder baseline:** H6 (Directed AP Decode) + OSD fallback, shim 20260033, main HEAD `bb0a1c4`

---

## 0. Executive summary

H7 (MMSE joint demodulation) has sat on the D-001 hypothesis ladder as "next diagnostic
step" since at least 2026-06-18, explicitly gated behind one condition: **real-world
on-air QSO testing confirming H6+OSD is insufficient.** That condition has now been
tested three times independently, on live 40 m traffic, with no directional
improvement. **QA's assessment: the evidentiary gate is satisfied.** Whether that
means H7 should be commissioned is a scope/product decision this document does not
make — it hands the architect a clean evidence trail plus one caveat that should be
resolved *before* committing to a 3–6 month architectural effort, not after.

No code or OpenSpec change is proposed here. This is a decision point, not a handoff.

---

## 1. The gate, as originally set

H7 was never rejected on technical grounds — it was deferred pending evidence, across
multiple independent reports:

| Source | Gating language |
|---|---|
| `qa/rr-study/results/2026-06-18-e5ce641/report.md` | "If H6 proves insufficient in on-air use, the next hypothesis is MMSE joint demodulation (H7)... should be scoped only after real-world QSO testing with H6 active." |
| `qa/rr-study/results/d009-investigation-2026-06-21/report.md` §5.2, Option D | "MMSE joint demodulation — removes the fundamental coupling between co-channel gain and FP manufacture. Substantial R&D; D-001 history suggests 3–6 months minimum. **Defer unless Captain rejects A/B/C.**" |
| `qa/rr-study/scenarios/s7-compounding.json` | K reduced from 10→5 trials/part for gating purposes; "Restore to K=10 for any active hypothesis investigation (H7 MMSE, SIC changes, etc.)" — i.e. today's synthetic harness is deliberately under-powered for an H7 go/no-go and would need reconfiguring. |

The consistent thread: H7 is a large commitment, and the project's stated policy is
not to open it on synthetic-harness results alone — it wants live on-air confirmation
that H6+OSD has hit its ceiling.

---

## 2. The evidence now on the table

Three independent live endurance sessions, each explicitly testing "is the D-001 gap
unchanged," now exist:

| Report | Session | Shim | Duration | Recall < −15 dB | Recall > +5 dB | Verdict |
|---|---|---|---|---|---|---|
| `qa/endurance/2026-06-22-f11f438` | live, evening–dawn | 20260029 | — | 22–37% | 85–90% | baseline established |
| `qa/endurance/2026-07-06-7340e45` | live, evening–dawn | 20260031 | — | 23–43% | 84–91% | within variance |
| `qa/endurance/2026-07-07-bb0a1c4` | live, full day/night/day cycle | 20260033 | 16h59m (longest yet) | 23–32% | 83–87% | within variance, no directional trend |

All three reports independently conclude: no regression, no improvement, no
directional shift attributable to intervening work (D-009, D-012, F-005). The gap is
stable, structural, and has now survived three separate live sessions spanning
different times of day, band conditions, and roughly 40 hours of combined on-air
operation. This is the on-air evidence the original gate asked for.

---

## 3. One caveat the architect should resolve before scoping H7

**H7 is specifically a co-channel / multi-signal remedy** — MMSE joint demodulation
jointly estimates parameters for two or more overlapping signals instead of treating
one as noise. It is not obviously a fix for a single isolated weak signal decoded
against a clean noise floor; that is more of an LDPC/matched-filter sensitivity
question.

The endurance reports' headline metric — "SNR-stratified recall vs WSJT-X" — is a
**general** on-air recall figure. It does not decompose the gap by whether the missed
signal had a co-channel interferer within the ~5–7 Hz window the synthetic
`co_channel_sweep` study (P15/P16) identifies as the hard case, or was simply weak and
isolated. The synthetic harness *has* isolated this distinction before (e.g.
`qa/rr-study/results/2026-06-20-d70aad5/report.md`: "H7 (MMSE joint demodulation)
would be required" specifically for the equal-SNR co-channel case), but that was a lab
scenario, not the live endurance data now being cited as the trigger.

**Before committing 3–6 months to H7, QA recommends confirming that the live gap is
actually co-channel-attributable** — e.g. by cross-referencing missed-decode
frequency/time proximity to other simultaneously-decoded signals in the existing
endurance logs (06-22 / 07-06 / 07-07 all have raw decode logs retained) — rather than
assuming the general SNR-stratified figure is evidence for a joint-demodulation fix.
If a meaningful fraction of the low-SNR misses are isolated single signals with no
nearby interferer, H7 would not address them, and the 3–6 month estimate would be
buying less than the headline recall numbers imply.

This is a bounded log-analysis exercise (no new live session required), not another
open-ended investigation round.

---

## 4. Options for the architect

| Option | What it means | Effort |
|---|---|---|
| **A. Commission H7 scoping now** | Treat the on-air gate as satisfied; open an OpenSpec proposal to design the MMSE joint-demodulation architecture. | 3–6 months per the D-009 report's own estimate (§2 above) |
| **B. Resolve the caveat first (§3), then decide** | QA runs a bounded co-channel-attribution pass over the three retained endurance logs before H7 is scoped, to confirm the fix actually targets the observed failure mode. | Days, using existing logs |
| **C. Continue deferring** | Judge the current 83–87% (>+5 dB) / 23–32% (<−15 dB) recall profile as an acceptable, disclosed product limitation; no further D-001 work scheduled. | None |

**QA recommendation: B.** The evidentiary gate for "is H6+OSD insufficient" is met;
the open question is narrower — "insufficient at what, specifically" — and answering
it first avoids the risk of committing a multi-month architectural effort against a
partially mis-attributed root cause. This does not reopen or relitigate the
three-report conclusion; it sharpens it before the money is spent.

---

## 5. References

| Reference | Content |
|---|---|
| `qa/endurance/2026-06-22-f11f438/report.md` | First live D-001 baseline, shim 20260029 |
| `qa/endurance/2026-07-06-7340e45/report.md` | Second live confirmation, shim 20260031 |
| `qa/endurance/2026-07-07-bb0a1c4/report.md` | Third live confirmation, 16h59m full day/night/day cycle, shim 20260033 |
| `qa/rr-study/results/d009-investigation-2026-06-21/report.md` §5.2 | Option D — H7 scope estimate (3–6 months), original deferral rationale |
| `qa/rr-study/results/2026-06-18-e5ce641/report.md` | Original "scope only after on-air QSO testing" gating language |
| `qa/rr-study/results/2026-06-20-d70aad5/report.md` | Synthetic co_channel isolation showing H7 targets equal-SNR co-channel specifically |
| `qa/rr-study/scenarios/s7-compounding.json` | Harness note: restore K=10 for active H7 investigation |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | H6 hypothesis documentation (co-channel interference, D-001 root cause) |
| `tests/OpenWSFZ.Ft8.Tests/D001H6ApDecodeTests.cs` | H6 AP-decode unit coverage (current baseline, unaffected by this decision) |
