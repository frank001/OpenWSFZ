# ARCHITECT → QA — `NBR-A` **AUTHORISED**, Amendment 1

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 20:23:55Z
**Amends:** `qa/rr-study/2026-08-27-2100-architect-to-qa-spec-nbr-a-near-neighbour-exclusion-fix-route.md`
(commit `427a5cf`) — **§1 sizing only, plus a new non-gating Part D.**
**Status:** 🟢 **AUTHORISED. QA may run.** No `src/` change, no Developer session, no capture, no
transmit.

**Captain's directions, recorded verbatim before the run (HK-029 principle):**

1. ✅ **`NBR-A` is AUTHORISED** — spec §5 **option 1**.
2. ✅ **P2 is adopted as Route B2's acceptance test** (§4 below).
3. ✅ **Route B2 itself is NOT authorised** — agreed and unchanged.

🔴 **The gate does not move.** §4.4's ROW 0 rows and §4.5's ROW 1–4 reading rows are **unchanged,
character for character.** Everything below is either a correction to stale prose, or an explicitly
**non-gating** addition. If anything here appears to loosen a bar, the original spec wins and this
document is the defect.

---

## 0. ✅ ROW 0a's precondition is now satisfiable — verified

Spec §4.4 ROW 0a requires `libft8.dll` SHA256 = `bc8efcf1…b051d7f`, shim `20260046`. The tree held
the retired Hamming build until the housekeeping landed. **Verified just now at both locations:**

```
bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f  src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll
bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f  native/ft8_lib_build/libft8.dll
```

✅ ROW 0a will pass. **Assert it anyway at run start** — that is the row's whole point, and a tree can
change between now and arming.

⚠️ **Note the harness distinction:** `NBR-A` runs on `qa/rr-study/f-nbr-a/`, **not** the S1–S8
`run_scenario.py`. The batched-playback change pinned at `dc4281f` is therefore **irrelevant to this
arm** — no live playback, no audio device, no cycle timing. `NBR-A` renders PCM in-process and feeds
the DLL directly. **That is a feature: this arm is immune to the instrument question that voided the
last one.**

---

## 1. 🔴 Correction to spec §1 — two statements are now false

Spec §1 reads: *"The remaining S7 residual is dominated by P2's 3-stack co-channel case (15 misses),
which is structural and was Captain-waived on 2026-06-22."*

**Both halves are wrong as of today:**

| claim in §1 | status |
|---|---|
| *"was Captain-waived"* | 🔴 **The waiver was RETRACTED by the Captain on 2026-08-29.** P2 counts against the product. |
| *"3-stack co-channel"* | 🔴 **Not co-channel.** Truth rows are **1492 / 1500 / 1511 Hz — 8 Hz and 11 Hz apart, 19 Hz span**, all 0 dB. |
| *"which is structural"* | ⚠️ **Unsupported.** OpenWSFZ solves both of those spacings at **10/10 with two signals** (P8, P19 at 8 Hz; P9 at 11 Hz; P10/P20 at 9 Hz). WSJT-X scores **12–15/15** on P2. It is demonstrably solvable. |

### 1.1 Revised sizing — and it is an upper bound, not a forecast

Spec §1 sized the near-neighbour family at **26 of 46** S7 misses and **5 of 5** S8 misses. With P2
no longer excluded, **if P2 shares the mechanism** the family is **41 of 46 S7 misses**:

| | now | if the family closes |
|---|---|---|
| S7 | 78.60% (169/215) | ≈ **97.7%** |
| S8 | 91.67% (55/60) | **100%** |

🛑 **"If P2 shares the mechanism" is exactly what is NOT established** — it is the §3 reading in my
HK-018 pass, explicitly labelled a reading and not a result. Spec §1's own warning applies with more
force now, not less: **treat this as the ceiling on the prize, never a forecast.** Part D (§3) is the
cheapest thing that speaks to it, and it is deliberately non-gating.

---

## 2. ROW 0e is de-risked — 🛑 but its bar does NOT move

Spec §4.4 ROW 0e reproduces the ΔF = 0, −6 dB survival and fires if `R < 0.80`. My §6 prediction
priced it as *"the most likely of those to fire"*, reasoning that the observation *"rests on a single
scenario with N = 5"*.

**That basis has widened.** Measured across four independent runs on S8's own 1500 Hz pair (0 dB and
−6 dB, both `dt = 0`): `7d36038` 5/10, `f5dec23` 10/10, `22b749c` 10/10, `872ba65` 5/5 ⇒ **30/35.**

🛑 **The `R < 0.80` bar is unchanged, and I am explicitly refusing to move it.** Widening a bar after
seeing data that supports it is the same class of error as narrowing one after seeing data against
it. What changes is only **my prediction**, which gates nothing: `P(ROW 0e fires)` drops from "most
likely of the ROW 0s" to roughly **10%**.

⚠️ **ROW 0e can still fire, and it still means what it says**: `R < 0.80` ⇒ the S8 observation does
not generalise off the S8 scene ⇒ the §6.2 mechanism lead is VOID ⇒ **STOP and report.** The 30/35 is
four runs of *one scene*; ROW 0e tests whether it survives *scene change*, which no run has done.

---

## 3. 🆕 Part D — the three-signal observation. **NON-GATING**

🔴 **Part D cannot change the verdict. It does not feed ROW 1, 2, 3 or 4, and no ROW 0 row depends on
it.** If Part D and the reading rows disagree, **the reading rows win.** It is included because the
harness is already running, the marginal cost is ~7%, and it is the only cheap way to learn whether
P2 belongs to this family at all.

**Feasibility verified, not assumed:** `scene_render.render_scene(signals, seed)` takes an arbitrary
list of station dicts, so a three-signal scene needs **no new tooling**.

**Conditions**, all at N = 100, at the ROW 0c-selected `L* `where applicable:

| id | scene | expectation |
|---|---|---|
| **D1** | **P2 replica** — three signals, all **0 dB**, at `E`, `E+8 Hz`, `E+19 Hz`. Score each of the three separately. | `R ≈ 0` on all three |
| **D2** | **Two-signal positive control** — same spacings, taken pairwise (0/+8, then 0/+11), both 0 dB | `R ≈ 1.0` — this is the S7 P8/P9/P19 result, and D2 failing means the harness does not reproduce known-good behaviour |
| **D3** | **Three signals, wide** — all 0 dB at `E`, `E+100 Hz`, `E+200 Hz` | discriminates **count** from **density** |

### 3.1 Pre-registered readings — fixed now, not chosen after (HK-021)

| what D1/D3 show | reading |
|---|---|
| D1 ≈ 0 **and** D3 ≈ 1.0 | **Density, not count.** Three signals are fine when spread; the failure is three *overlapping* signals ⇒ P2 belongs to the near-neighbour family ⇒ the §1.1 sizing is the right ceiling, and P2 is a legitimate Route B2 acceptance test. |
| D1 ≈ 0 **and** D3 ≈ 0 | **Count, not density** — a signal-multiplicity ceiling independent of spacing. 🔴 This would **contradict S8** (12 simultaneous signals at 91.67%) ⇒ escalate; something about the harness or the scene is not what we think, and **do not proceed to interpret Parts A–C until it is resolved.** |
| D1 materially > 0 | **The harness does not reproduce P2's zero.** Escalate. P2's 0/15 is 135 observations with zero variance in the S7 battery; a Part D that recovers signals is measuring a different thing, and the difference must be found before any of this is cited. |
| **D2 < 0.90** | 🔴 **Harness invalid for this question.** Stop Part D and report — the known-good two-signal case must reproduce or nothing in Part D means anything. Parts A–C are unaffected. |

⚠️ **Rule-of-three note (HK-021(o)):** at N = 100 an observed 0 gives a 95% upper bound of **3%**.
That is the resolution — do not report "zero", report "0/100, UB 3%".

🛑 **Part D authorises no remedy in any outcome.** It is an observation whose interpretation is
pre-registered so it cannot be read opportunistically later.

---

## 4. ✅ P2 adopted as Route B2's acceptance test — standing criterion

Recorded per the Captain's direction, binding on any future Route B2 proposal:

> **A candidate per-candidate-complex-baseband implementation must move S7 P2 off `0/15`.** A
> proposal that does not is not evidence of having closed the architectural gap, whatever it scores
> on a live corpus.

**Why P2 and not a live number:** it is **synthetic, deterministic, needs no radio, and has zero
variance across 135 observations in nine runs** — so any movement at all is signal, not noise. And it
carries a **reference existence proof**: WSJT-X recovers 12–15 of 15 from identical audio, using
exactly the machinery Route B2 would add.

⚠️ **This is an acceptance criterion, not a target to optimise against.** 🛑 It does not authorise
Route B2, does not license work aimed at P2 specifically, and must not be used to justify re-opening
any closed family (§2 of my HK-018 pass lists them).

---

## 5. What is unchanged

- 🛑 **§4.4 ROW 0a–0e and §4.5 ROW 1–4: character for character as ratified.** Part D touches neither.
- 🛑 §2's prohibition check stands — this is **not** retired spectral locality, and **nothing here may
  be used to reopen LOCAL-vs-DIFFUSE.**
- 🛑 §3 stands: the coherent extractor **cannot** be switched on as a remedy until ROW 0g clears.
- 🛑 **HK-025 — QA may still refuse any row on HK-021(k) grounds without my agreement**, including
  Part D. Authorisation by the Captain does not remove that.
- ⚠️ §4.3's resolvable distance is unchanged: **at N = 100, structure smaller than ~20 pp is not
  readable.** If ROW 1's periodicity test is wanted at finer amplitude, N must rise to 400/point —
  **tell the Captain the cost before arming, not after.**
- 🛑 NFR-021: 100% synthetic, Q-prefix callsigns only.
- 🛑 HK-014: committed locally, not pushed.

---

## 6. ⚠️ Housekeeping risk I need to flag — the session's record is on a doomed branch

**Not part of `NBR-A`, but it should be settled before any branch cleanup.**

All eight Architect documents from this session — the `WIN-A` void ruling, Amendment A1, the
consolidated spec, the closure, the P2 reassessment, the waiver retraction, the HK-018 pass, and the
QA TODO — are committed on **`experiment/win-a-hamming-rung1`** (HEAD `123821f`).

🔴 **That branch also carries the retired Hamming build (`2401915`) and is never to be merged.** I
told QA that retaining or deleting it was their call under HK-003. **If it is deleted, this entire
session's rulings and the rationale behind the window-family prohibition go with it.**

The two `NBR-A` code artefacts (`win_a_gate_v2.py`, `win_a_row0e.py`) are on the same branch.

**Recommended:** move the docs-only commits onto a branch off `main` — `qa/housekeeping-2026-08-29`
already exists and is where this amendment is being written — and only then let HK-003 take its
course on the experiment branch. 🛑 **Per HK-014 I have not restructured branches and will not
without instruction**; flagging it because a routine cleanup would silently destroy the record.
