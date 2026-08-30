# ARCHITECT → QA — `WIN-A` **AMENDMENT A1**: the re-arm, specified to test the Captain's runbook claim

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 18:59:49Z
**Amends:** spec `fb25010` (§3 scope and same-session rule, §6 gate predicate) and the 18:39Z ruling
`2026-08-29-1839-architect-to-qa-ruling-win-a-rung1-run-is-void-and-rearm-instruction.md` (§4.1
revert instruction, **withdrawn**).
**Status:** 🔴 **BUILD EXISTS, ARM IS UNBLOCKED.** No Developer session required. No `src/` or
`native/` change authorised.

**Captain's directions, recorded as amendments before the run (the HK-029 principle, applied whether
or not the rule is ratified):**

1. ✅ **A full S1–S8 sweep was directed on 2026-08-29 and is hereby recorded as a scope amendment to
   §3's "S7+S5 only".** The 18:39Z ruling's void cause **V5 is WITHDRAWN**; QA breached nothing.
2. ✅ **The runbook change — skipping the 15 s silence between parts — is RETAINED.** The 18:39Z
   ruling's §4.1 revert instruction is **withdrawn in full**. See §1.
3. ⏳ **HK-029 deferred**, not rejected. This document applies its substance to `WIN-A` only.

---

## 0. What changed in my position, and why

The Captain's objection was that the runbook change "does not seem to have any effects on the results
of the study," and that a full S1–S8 run already contains all the S5 and S7 data. **He is right on
both counts as stated, and I was solving the wrong problem in §4.1 of the ruling.**

- **Breadth was never the fault.** A full S1–S8 sweep contains every S7 and S5 observation the gate
  needs. The fault was that the run had **one leg** and was differenced against a *different day's*
  numbers.
- **A harness change only confounds when it falls BETWEEN the compared things.** Run both legs on the
  same harness and it cancels out of the contrast exactly. Reverting it was unnecessary, and would
  have thrown away a change that **halves battery runtime (8460 s → 4422 s)** — which is precisely
  what makes the clean three-leg arm below affordable at all. **The Captain's runbook change pays for
  this arm.**

🔴 **What does not change: the arm still needs a same-session baseline.** WSJT-X — unchanged code —
scored **210/215 on 08-27 and 200/215 on 08-29**. Ten observations left a decoder nobody touched.
That is measured, it is in this run's own data, and my requirement does not depend on knowing its
cause: **a same-session baseline cancels the unknown cause whatever it turns out to be.** That is the
one thing this amendment insists on, and it is the only thing.

✅ **And it converts the disagreement into a measurement.** ROW 0b (§4) requires the two baseline legs
to agree within 4 observations. **That is a direct empirical test of the Captain's claim.** If they
agree, the runbook change is *demonstrated* harmless on this metric and the arm resolves cleanly. If
they disagree, we have found something real that would otherwise have been billed to Hamming.

---

## 1. 🔴 Read this before planning the run — the verdict is already half-decided

QA must know this going in, because it changes what the run is *for* and I will not have it
discovered afterwards.

**The treatment leg measured `w_hit = 0/15`** — Hamming recovered **not one** additional weak signal
in P12/P13/P14, identical to baseline. Applied to the §6 predicate:

- ROW 1 (BENEFIT) needs `w_hit >= 5`. **Impossible on this data.**
- ROW 3 (PARTIAL) needs `w_hit >= 1`. **Impossible on this data.**

⇒ **The verdict is already constrained to ROW 4 (NULL) or ROW 2 (HARM), and the only open question is
which.** That question is exactly `is c_hit_base − c_hit >= 12?` — i.e. does the re-measured baseline
land at **171 or higher**. Nothing else in the battery can move it.

✅ **This is good news, not a disappointment.** With ROW 0e passing, **ROW 4 is a real result**: per
§6.2, *"sidelobe leakage is not the capture mechanism. Close the window family."* A mechanism
eliminated cheaply and permanently — which §9 of the spec called worth more than the last ten weeks
produced. The arm is not being run in hope of a win; it is being run to **bank an elimination**, and
the elimination is only bankable if the baseline is sound.

⚠️ **Corollary for planning: do not let anyone read a NULL here as "the session was bad."** ROW 0b
and ROW 0g exist to close that escape hatch in advance.

---

## 2. Two variants. Pick one before arming; do not decide after seeing data

| | **A1-FULL (recommended)** | **A1-REUSE (fallback)** |
|---|---|---|
| legs | baseline ×2 **+ fresh treatment ×1**, all in ONE session | baseline ×2 this session; **reuse** the 2026-08-29 treatment leg |
| batteries | **3** ≈ **3.7 h** (74 min each at 4422 s) | **2** ≈ **2.5 h** |
| §3 same-session rule | ✅ **fully satisfied** | ⚠️ **deliberately deviated** — needs ROW 0g |
| extra rows | none | **ROW 0g** (§4.1) becomes mandatory |
| residual risk | **none identified** | bounded — see §2.1 |

🔴 **I recommend A1-FULL.** It costs one extra battery (~1.2 h), removes every caveat, restores §3
in full, and produces an arm nobody has to defend later. Under the *old* harness this would have been
7 h and I would not have proposed it; at 3.7 h it is one evening.

### 2.1 The exact, bounded risk of A1-REUSE (HK-021(t) — state the cost, do not imply there is none)

Reusing a treatment leg from a session that demonstrably lost ~10/200 observations raises one
question: **could that session have suppressed a real weak-signal recovery?**

Quantified: a session effect costing 10 of 200 is 5%. Applied to the 15 weak observations, its
expected cost is **≈0.75 observations**.

- ⇒ It could plausibly hide **one** recovery — turning a true ROW 3 into an observed ROW 4.
- ⇒ It **cannot** hide five. **A1-REUSE cannot cost us a ROW 1.**

✅ So the entire exposure of the cheap path is: *a genuine ROW 3 might read as ROW 4.* And ROW 3's
only consequence is licensing **Rung 2 (Blackman)**, which carries a **strong prior of harm** (§2 of
the spec: an 18.75 Hz main lobe swallows most of the battery). **The bounded downside is missing a
licence to run an arm we expect to fail.** That is why A1-REUSE is defensible — but A1-FULL is still
what I would run.

---

## 3. Pins — assert every one, fail loudly

Spec §3's pins carry over **unchanged** except where listed. Additions and changes:

| item | value |
|---|---|
| scenarios | 🔴 **full S1–S8 on EVERY leg** (Captain's amendment). Identical battery, identical order, every leg. |
| **harness** | 🔴 **the NEW batched `run_scenario.py`, on every leg.** ⚠️ **It is currently UNCOMMITTED (+182/−77) ⇒ it has no identity and cannot be pinned.** **Commit it before arming** (QA-owned tooling, HK-011) and **record its commit SHA here as a pin.** An instrument that cannot be named cannot be re-run. |
| baseline build | `main` @ `2ae939c`, shim 20260046, `libft8.dll` SHA256 **`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`**. 🔴 Full working-tree checkout, managed **and** native together — `ExpectedShimVersion` **throws on load** against a DLL swap. |
| treatment build | `experiment/win-a-hamming-rung1`, shim 20260047, SHA256 **`c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a`** |
| S7 population | 215 truth rows, shape `{P2: 15, others: 10}` — ROW 0a, unchanged |
| ⚠️ historical baselines | 🛑 **`22b749c`'s 169/210 are NO LONGER the arm's baseline.** They are provenance only. The baseline is what §4's legs measure. |
| audio device | `Voicemeeter AUX Input` — pass `--device` explicitly |
| `ALL.TXT` | clear **both** files before **every leg**, not once per session. Back up per the `_pre-run-backups/` convention. |
| commits | 🛑 **no commits of any kind while a leg is live** |

⚠️ **Rebuild Release fresh at every leg switch.** QA caught a stale `Release` directory last time and
deserves the credit; with three legs the exposure triples, and a stale binary is the one failure that
yields a *plausible-looking* result rather than an obvious one.

### 3.1 Treatment-leg attestation (A1-REUSE only)

If A1-REUSE is chosen, the 08-29 treatment leg's binary identity is attested **retrospectively**:
`git status` shows both `libft8.dll` copies **unmodified since commit `2401915`**, which recorded
SHA `c8281297…`; the run confirmed shim 20260047 loaded via the daemon startup log and
`/api/v1/status`. ⚠️ **This is weaker than an assertion made at run start** — it proves the tree
holds the right binary *now*, not that it did then. I judge it sufficient given the commit record and
the untouched working tree, and I am recording the weakness rather than papering it. Under A1-FULL
this paragraph does not apply.

---

## 4. ROW 0 — preflight, strict order, all must pass

Rows **0a, 0c, 0d, 0e, 0f** carry over from spec §4 unchanged in substance. Amendments:

| row | check | bar | if it fails |
|---|---|---|---|
| **0a** | truth population reproduces | exactly **215** rows, per-part shape as pinned, on every leg | **VOID** |
| **0b** | 🔴 **instrument noise measured, not assumed** — *this is the test of the Captain's claim* | baseline leg run **twice**: `abs(c_hit_1 − c_hit_2) <= 4` **and** `w_hit_1 == w_hit_2 == 0` **and** `w11_1 == w11_2 == 5` | **escalate, do NOT widen the bar.** A fail here is a finding about the harness, not about Hamming |
| **0c** | build identity + the `fft_norm` trap | SHA asserted **at the start of each leg**; `monitor.c` diff is exactly one changed line reading `me->window[i] = me->fft_norm * hamming_i(i, me->nfft);` | **VOID** |
| **0d** | the window is actually different | ✅ **satisfied from the committed `native/ft8_lib_build/{baseline,treatment}_window.txt`** — `max_abs_diff = 4.5e-5 > 1e-6` ✅, `sum` 1.000000 vs 1.086957 ✅. 🛑 **Do NOT rebuild the baseline DLL to produce a runtime dump — that voids `bc8efcf1…`.** | **VOID** |
| **0e** | 🔴 **a unit whose metric MOVES** (HK-021(q)) — **BLOCKING, run it FIRST** | offline, no decoder, no radio: for one P13 trial's synthesised audio, compute the strong signal's window sidelobe level at the weak signal's tone bins under Hann and under Hamming. Require the Hamming figure **≥ 6 dB lower**. Commit the artefact. | **VOID — and the arm does not run.** ⚠️ A 0e fail is itself a cheap, permanent D-001 result: report it as one, not as a setback |
| **0f** | strong-signal control | strong signals in P11–P14 remain **5/5 each**, every leg | **escalate** |
| **0g** | 🔴 **NEW — cross-session equivalence. A1-REUSE ONLY.** | using WSJT-X, whose code is identical on every leg, as the session probe: `abs(wsjt_s7_base1 − 200) <= 4` **and** `abs(wsjt_s7_base2 − 200) <= 4` **and** `abs(wsjt_s7_base1 − wsjt_s7_base2) <= 4`, where **200/215** is the treatment leg's measured WSJT-X S7 total | **VOID for A1-REUSE.** The baseline session is not equivalent to the treatment session ⇒ fall back to **A1-FULL** and run a fresh treatment leg |

### 4.1 Why ROW 0g is the right instrument, and why the bar is 4

WSJT-X is **unchanged across every leg and every session in this programme**. Any movement in its
score is therefore *pure session effect* with the decoder held constant — it is the one probe in the
battery that cannot be contaminated by the treatment. This is the same logic that exposed the problem
in the first place, turned into a gate.

**The bar of 4 is ROW 0b's own instrument-noise allowance**, applied to the unchanged appraiser
rather than assumed for it. It is not a new number and it is not tuned to pass: 🔴 **the 08-27 → 08-29
movement was 10, so this bar would have caught the exact failure that voided the last run.** That is
the test HK-022 asks for — a row that could actually have detected the error it is meant to detect.

⚠️ **HK-021(k)/HK-025 evaluated, both branches:** pass ⇒ the treatment leg is reusable and the arm
proceeds on 2 batteries. Fail ⇒ the treatment leg is discarded and a third battery is run. **The two
branches produce different runs and different data ⇒ verdict-changing, not diagnostic ⇒ this is a
legitimate gate and QA is not entitled to refuse it on HK-025 grounds.** Recording the evaluation so
nobody has to redo it.

---

## 5. 🔴 The gate — AMENDED. The baseline is now measured, not a constant

Spec §6's predicate hard-codes thresholds derived from `c_hit_base = 169`. **That constant is gone.**

✅ **Shipped as code, not prose: `qa/rr-study/win_a_gate_v2.py`.** Import it or call it; do not
retype it. `python win_a_gate_v2.py` re-executes every claim in this section and exits non-zero if
any fails — **run it once before arming.** The listing below is that file's predicate verbatim.

```python
def win_a_gate_v2(w_hit, c_hit, w11, c_hit_base):
    """WIN-A verdict, AMENDMENT A1: baseline RE-MEASURED in this arm.

    c_hit_base -- mean of the two baseline legs' c_hit, rounded half to even.
    Preconditions, asserted by ROW 0b BEFORE this is called (never inside it):
        baseline w_hit == 0 on both legs
        baseline w11  == 5 on both legs
        abs(c_hit_1 - c_hit_2) <= 4
    Evaluated in strict order; first true row wins. Signed throughout (HK-021(l)).
    """

    # ROW 2 -- HARM. Checked FIRST so a benefit cannot mask a material cost.
    if c_hit <= c_hit_base - 12:
        return "ROW 2 -- HARM"

    # ROW 1 -- BENEFIT. Both limbs required (HK-021(t)).
    if w_hit >= 5 and c_hit >= c_hit_base - 4 and w11 == 5:
        return "ROW 1 -- BENEFIT"

    # ROW 3 -- PARTIAL.
    if w_hit >= 1:
        return "ROW 3 -- PARTIAL"

    # ROW 4 -- NULL.
    return "ROW 4 -- NULL"
```

### 5.1 This is a strict generalisation, not a new gate

✅ **Substituting `c_hit_base = 169` reproduces spec §6 exactly** — `169 − 4 = 165`, `169 − 12 = 157`,
the original thresholds character for character. Every derivation in §6.1 stands as written; the
`−4` is still ROW 0b's measured noise and the `−12` is still 3× it. The ROW 1 and ROW 2 bands remain
**mutually exclusive and 8 observations apart** for any `c_hit_base`, so no input can satisfy both.

⚠️ **`w_hit >= 5` and `w11 == 5` stay absolute**, because ROW 0b *asserts* the baseline at `w_hit = 0`
and `w11 = 5` rather than measuring a variable. If ROW 0b fails, the gate is not run at all.

### 5.2 Boundary behaviour, executed (HK-021(r))

🔴 **Executed, not written.** All four claims below were run before this spec was filed:

| claim | domain checked | result |
|---|---|---|
| the table below is what the code returns | the 8 listed inputs | ✅ **all 8 match** |
| §5.1's strict-generalisation claim — `v2(…, 169) == ` spec §6 | **full domain**, `w_hit` 0–15 × `c_hit` 0–200 × `w11` 0–5 = 19,296 inputs | ✅ **0 mismatches** |
| ROW 1 and ROW 2 can never both fire | every `c_hit_base` 140–200 × full input domain | ✅ **0 inputs satisfy both** |
| §1's claim that ROW 1 and ROW 3 are unreachable at `w_hit = 0` | every `c_hit_base` 140–200 × `c_hit` 0–200 | ✅ reachable verdicts are **exactly {ROW 2, ROW 4}** |

Run at `c_hit_base = 160` to confirm the thresholds track:

| `w_hit` | `c_hit` | `w11` | `c_hit_base` | verdict |
|---:|---:|---:|---:|---|
| 0 | 160 | 5 | 160 | ROW 4 — NULL |
| 0 | 148 | 5 | 160 | **ROW 2 — HARM** (148 = 160−12) |
| 0 | 149 | 5 | 160 | ROW 4 — NULL |
| 5 | 156 | 5 | 160 | **ROW 1 — BENEFIT** (156 = 160−4) |
| 5 | 155 | 5 | 160 | ROW 3 — PARTIAL |
| 1 | 160 | 5 | 160 | ROW 3 — PARTIAL |
| **0** | **159** | **5** | **169** | **ROW 4 — NULL** ← the 08-29 treatment leg vs the *historical* baseline |
| **0** | **159** | **5** | **171** | **ROW 2 — HARM** ← the only baseline value that flips it |

🔴 **The last two rows are the whole arm.** Everything else is preflight.

---

## 6. S5 — unchanged gate, better evidence

S5 runs on **every leg** (it is in S1–S8). Its ratified gate is unchanged: 95% Clopper–Pearson UB
on the FP event rate **≤ 6%**, windowed to S5's own 60 injection cycles.

✅ **The re-arm improves this for free.** Two baseline legs give **120** baseline AWGN slots against
the treatment leg's 60 — a materially better FP comparison than the 60-vs-60 that produced the
inconclusive 1/60 event. Report baseline as pooled 120 **and** per-leg (HK-021(i) — the legs are the
cluster unit, do not treat 120 slots as 120 independent trials without saying so).

⚠️ **The 08-29 `1/60` event does NOT carry forward as evidence** (18:39Z ruling §3, Q2). The re-arm's
S5 starts from zero. Per §6.3 of the spec, an S5 fail on the treatment leg blocks a merge
recommendation under ROW 1 — which §1 above has already shown is unreachable, so S5 is reported here
for the record and for the FP trend, not as a gate that can change this arm's verdict.

🛑 **Do NOT touch `matcher.py` before the run** (18:39Z ruling §3, Q3). Its Pass 2 scope defect is
real, documented, and provably not affecting reported numbers because `analyse.py::_compute_fp_rates()`
re-windows independently. Fixing it now stacks a second uncontrolled instrument change on top of the
harness change. **After the arm, not before.**

---

## 7. Execution order — stop on the first failure

1. ✅ **Commit the harness change** and record its SHA in the run's `README.md` (§3). Nothing else
   changes in the working tree.
2. ✅ **ROW 0e, offline.** Minutes, no radio, no decoder. Commit the artefact. **Stop if it fails.**
3. ✅ **ROW 0d** asserted from the two committed `*_window.txt` files. No rebuild.
4. ✅ **Choose A1-FULL or A1-REUSE and record the choice** in the run README **before any leg runs.**
5. ✅ **Baseline leg 1** — full `main`@`2ae939c` checkout. Assert `bc8efcf1…` **at leg start.** Clear
   both `ALL.TXT`. Full S1–S8.
6. ✅ **Baseline leg 2** — identical. Assert the SHA again.
7. ✅ **ROW 0b** — evaluate. **Escalate on failure; do not widen the bar.**
8. ✅ **A1-FULL:** treatment leg — checkout `experiment/win-a-hamming-rung1`, assert `c8281297…` at
   leg start, full S1–S8.
   **A1-REUSE:** evaluate **ROW 0g** instead. On fail, run the treatment leg anyway (fall back to
   A1-FULL).
9. ✅ Compute `c_hit_base`, run **`win_a_gate_v2`** as shipped code, and **report the string it
   returns.** Do not narrate around it, and do not report a verdict the function did not produce.
10. ✅ Report the **WSJT-X DT residual mean and SD per leg** (§8).

---

## 8. Recorded observation, gating nothing — the runbook change, measured properly

Not a gate. It must not block or alter the verdict, and I am pre-registering the interpretation now
so it cannot be chosen after the fact (HK-021):

Report WSJT-X's S3 DT residual **mean and SD for each leg**. Reference: `22b749c`, unbatched, an
exact **−0.800 s constant, SD = 0.000** across all 30 trials; 08-29, batched, **−1.200 s, SD 0.330 s**.

| what the three legs show | pre-registered reading |
|---|---|
| SD reproducible across legs (all ≈0.33 s, spread small) | The batching raises the DT **noise floor** by a stable, characterisable amount. It is a **precision cost, not a bias**, it cancels in the contrast, and the Captain's "no effect on the study" holds for every metric except S3's own precision gate. **Retain the change**; re-baseline S3's gate under it. |
| SD varies materially between legs | The jitter is **not stationary** ⇒ it is not characterisable and it *can* leak into contrasts. **Escalate**; the harness needs bounding before the next arm. |

✅ Either way this settles the runbook question **with data instead of argument**, at zero extra cost,
because these legs are being run anyway. This is the paired A/B the 18:39Z ruling asked for, obtained
for free.

---

## 9. What this amendment does NOT do

- 🛑 No `src/` or `native/` change, no Developer session, no rebuild of any binary, no merge, no push.
- 🛑 **Rung 2 (Blackman) stays behind a fresh pre-registration** and is licensed by ROW 3 only —
  which §1 shows is unreachable on the existing treatment data. Under A1-REUSE, Rung 2 is therefore
  **out of reach by construction**; under A1-FULL a fresh treatment leg could in principle reach it.
  ⚠️ **This is the one substantive difference between the variants and the Captain should see it.**
- 🛑 `/Brepro` remains **post-verdict**. Adding it now voids both SHA pins.
- 🛑 **AC-4** (`SameCycleResolution_Type4AndHashReferenceInOneCall_BothResolve`) is untouched: a merge
  precondition owned by **S9**, investigated only on a ROW 1 or ROW 3 verdict. On ROW 2 or ROW 4 the
  rung dies and AC-4 dies with it.
- 🛑 Per HK-014 this is committed locally and **not pushed**. Per HK-025 QA may refuse any row here on
  mechanical grounds without my agreement — ROW 0g's evaluation is recorded in §4.1 to save the work.
