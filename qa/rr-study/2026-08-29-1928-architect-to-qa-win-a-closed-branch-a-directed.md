# ARCHITECT → QA — `WIN-A` **CLOSED**. Captain directed branch A. Window family retired.

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 19:28:22Z
**Closes:** spec `fb25010` (`WIN-A`, the analysis-window sidelobe ladder), both rungs.
**Captain's direction, verbatim:** *"go with A then."*

---

## 1. What is closed, and on what basis

🔴 **The analysis-window family is CLOSED. Hann stays. Both rungs are retired — Hamming (Rung 1) and
Blackman (Rung 2), the latter never built and not to be.**

**Closed on a failed pre-registered preflight row, not on a decode verdict.** ROW 0e required the
treatment to reduce the strong neighbour's leakage into the weak signal's bins by **≥ 6 dB** at
P13's geometry before the decode arm was allowed to run. Measured (`qa/rr-study/win_a_row0e.py`,
offline window arithmetic, validated to 8–9 digits against the build's own committed window dumps):

| part | ΔF | bins | Hann | Hamming | change |
|---|---:|---:|---:|---:|---:|
| **P11** | 14 Hz | 4.48 | −47.27 dB | −39.91 dB | **−7.36 dB — worse** |
| P12 | 9 Hz | 2.88 | −30.62 dB | −42.33 dB | +11.71 dB |
| **P13** | 7 Hz | 2.24 | −23.26 dB | −28.92 dB | **+5.66 dB — FAILS by 0.34 dB** |
| P14 | 11 Hz | 3.52 | −40.39 dB | −40.42 dB | +0.03 dB |

Hann's 18 dB/octave rolloff overtakes Hamming's ≈−42 dB plateau beyond ≈3.5 bins, so **Hamming helps
only in a narrow band near 2.9 bins and hurts outside it — including at P11, the one capture part
OpenWSFZ currently recovers (5/5) and the gate's `w11` must-not-lose control.** ⚠️ **That geometry
argument applies with more force to Blackman**, whose main lobe is 50% wider, which is why the family
closes as a unit rather than leaving Rung 2 dangling.

✅ **Corroboration** — from the confounded 08-29 leg, reading changes *within* it against its own
parts rather than across sessions: **an 11.7 dB leakage reduction bought nothing at P12 (0/5 → 0/5)
and a 7.4 dB increase cost nothing at P11 (5/5 → 5/5).** Two large, opposite-signed perturbations of
the theorised mechanism; neither moved the outcome.

---

## 2. 🔴 What may NOT be claimed — read this before writing anything up

**No gate verdict exists.** `win_a_gate` / `win_a_gate_v2` never fired. There is no ROW 1, 2, 3 or 4
for `WIN-A`, and none is to be quoted, inferred, or written into a report, board entry, or trend row.

🛑 **In particular, do NOT write "sidelobe leakage is not the capture mechanism."** That is ROW 4's
wording, and spec §6.2 made ROW 4 explicitly conditional — *"given 0e confirmed the leakage itself
moved."* **0e did not confirm it; 0e failed.** The correct claim is narrower and it is this:

> **Hamming is the wrong lever at this geometry, and Blackman is worse.** Where the window change did
> deliver a large leakage reduction, recovery did not follow. The window family is therefore retired
> as a route to the capture deficit.

The elimination is **strong, not airtight**, and the difference is not pedantry — it decides whether
a future reader treats sidelobe masking as settled (it is not) or as disfavoured (it is).

⚠️ **The capture deficit remains OPEN under D-001** — a weak signal ≥6 dB below a near neighbour is
still never recovered, ≈**6.98 pp** of the S7 gap. This arm removed a candidate explanation; it fixed
nothing.

### 2.1 The defect that made this decisive, recorded against myself

ROW 0e was written as a **bar without a method**. HK-021(r) — ship the predicate as code — applies to
preflight rows, and I did not apply it when I authored spec §4. That is why a **0.34 dB** margin, on
a metric whose definition I chose after the fact, was allowed to decide an arm. 🔴 **Any future
re-opening of the window family needs a fresh pre-registration with the leakage metric shipped as
executable code**, per the standing rule that a closed gate is never re-read with a better metric.

---

## 3. Consequences — what QA does now

| item | disposition |
|---|---|
| `experiment/win-a-hamming-rung1` | **Not merged, not recommended.** Retain or delete per HK-003 branch hygiene — QA's call, no Architect input needed. |
| The Hamming DLL (`c8281297…`) | Superseded. `main`'s `bc8efcf1…` remains the pinned production binary. ⚠️ **The tree currently holds the treatment DLL at both locations** — restore `main`'s before any other work runs against it. |
| **AC-4** (`SameCycleResolution_Type4AndHashReferenceInOneCall_BothResolve`) | **Dies with the branch.** It was a merge precondition owned by S9, investigated only on ROW 1/ROW 3. No branch, no merge, no investigation. ✅ Not a `main` defect — `main` is unaffected. |
| Rung 2 / Blackman | **Retired unbuilt.** Recorded in the standing prohibitions. |
| `libft8.version.txt` | Leave the `20260047` entry unmade — the arm did not survive. |
| Standing prohibitions | ✅ Already recorded in `closed-arms-prohibitions.md` with the measured figures. |

### 3.1 🔴 Outstanding, and independent of this closure

1. **PULL the `trend.csv` row** `2026-08-29,872ba653…` (FP 7.66%). Still not done. No notes column
   exists, so it is remove-or-mislead, and the run is confounded.
2. **The harness change is still UNCOMMITTED** (+182/−77) ⇒ it has no identity and cannot be pinned
   or re-run. **Commit it** (QA-owned tooling, HK-011).
3. ⚠️ **The runbook change is materially larger than "skipping the 15 s silence"** — whole scenarios
   play as one continuous stream, S3's two oversized parts are excluded by a new `_SLOT_SAMPLES`
   constant, and **truth-row writing was refactored** into `_write_truth_row()`. `truth.csv` is
   ground truth for every metric in the battery. **This is now the standing instrument for all
   future sweeps and it has never been validated live against the unbatched cadence.** Flagged for
   the Captain as a decision on its own merits.
4. `matcher.py` Pass 2 scoping (low priority, no reported number affected) — now unblocked, since
   there is no arm to protect from a second instrument change.

🛑 Nothing here authorises `src/`, `native/`, a merge, a push, or a Developer session. Per HK-014
this is committed locally and not pushed.
