# ARCHITECT → QA — SPEC `WIN-A`: the analysis-window sidelobe ladder

**Author:** Architect → QA
**Date (UTC, `date -u`, HK-017):** 2026-08-29 14:00:38Z
**Type:** 🔴 **BUILD SPEC with a pre-registered gate.** Produces a D-001 finding in either direction.
**Blocked until:** a Developer session produces the Rung-1 build (HK-011, HK-021(p) — see §7).

**Captain's authorisation, 2026-08-29, recorded verbatim in effect:**

1. ✅ **Developer build session APPROVED** — §7 may proceed; QA drafts the dev-task.
2. ✅ **Scope: S7 + S5 only.** Not the full S1–S8 battery. §3's pins and §6.3's FP check already
   reflect this; no other scenario is to be run on either leg.
3. ✅ **Rung 2 (Blackman) stays behind a fresh pre-registration** — a ROW 3 verdict does not
   auto-license it. §6.2 already states this and is unchanged.

---

## 0. The question, in one line

**Is the capture-family deficit — a weak signal 6 dB or more below a near neighbour, never
recovered — caused by analysis-window sidelobe leakage from the strong neighbour?**

If it is, `common/monitor.c`'s window function is the cheapest lever in the programme: the
alternative windows are already written in that file, commented out, by the upstream MIT author.

---

## 1. What I verified before writing this (HK-018)

Every number below was re-derived **from `S7_matched.csv` and `truth.csv` of run `22b749c`**, not
read from the report prose (HK-022). QA should reproduce them as ROW 0a and stop if any differs.

### 1.1 The gap, decomposed

S7, 215 observations, 21 parts. WSJT-X 210/215 = 97.67%. OpenWSFZ 169/215 = 78.60%. Net gap 41
observations = **19.07 pp**.

| Cluster | Parts | Net gap (obs) | pp |
|---|---|---:|---:|
| **Capture — weak signal ≥6 dB down** | P12, P13, P14 | 15 | **6.98** |
| P2 3-stack (**Captain-waived 2026-06-22**) | P2 | 12 | 5.58 |
| Tight separation ΔF 5–7 Hz | P15, P4, P0 | 14 | 6.51 |
| ΔF 13 Hz | P1 | 2 | 0.93 |
| **OpenWSFZ beats WSJT-X** | P3 (ΔF 3 Hz) | −2 | −0.93 |

**13 of 21 parts are at parity or better.** Excluding the waived P2: 169/200 vs 198/200 = **14.50 pp**.

### 1.2 The capture cliff — the single sharpest fact in the battery

Weak-signal recovery, OpenWSFZ, capture family, split strong-vs-weak per trial:

| Part | ΔF | ΔSNR | weak | strong |
|---|---:|---:|---:|---:|
| P11 | 14 Hz | **−3 dB** | **5/5** | 5/5 |
| P12 | 9 Hz | **−6 dB** | **0/5** | 5/5 |
| P13 | 7 Hz | −10 dB | **0/5** | 5/5 |
| P14 | 11 Hz | −13 dB | **0/5** | 5/5 |

The strong signal is recovered in **every** trial. The weak signal is recovered in **every** trial
at −3 dB and in **no** trial at −6 dB or below. That is a hard cliff between −3 and −6 dB.

### 1.3 Why this is a dynamic-range effect and not a separation effect

ΔF is held constant and only dynamic range changes:

| Condition | ΔF | Result |
|---|---:|---|
| P20 — equal power, 0 / 0 dB | **9 Hz** | 10/10, both signals |
| P12 — unequal, 0 / −6 dB | **9 Hz** | strong 5/5, **weak 0/5** |

At 9 Hz separation OpenWSFZ recovers both signals when they are equal, and never recovers the
weak one when it is 6 dB down. **Separation is not the operative variable at fixed ΔF; level
difference is.** That is the signature of masking by a stronger neighbour, which is what a window
sidelobe skirt does.

### 1.4 ⚠️ A noise finding QA must carry into the power reading

**P0 and P16 are geometrically identical** — both 1500/1507 Hz, both 0/0 dB, both `dt = 0.0`,
ΔF 7 Hz — and differ **only in seed**. They scored **7/10 and 10/10** in the same run. Per-part
n = 10 readouts therefore carry real between-seed variation of at least 3/10. **No single part may
be read as a result.** This is why the gate below pools and why ROW 0b measures the noise rather
than assuming it.

### 1.5 The source, and the trap in it

`native/ft8_lib_build/patched/common/monitor.c`:

```c
me->window[i] = me->fft_norm * hann_i(i, me->nfft);
// me->window[i] = blackman_i(i, me->nfft);
// me->window[i] = hamming_i(i, me->nfft);
```

`hamming_i` and `blackman_i` are present, complete, and commented out — upstream, by Kārlis Goba.

🛑 **THE TRAP, and it is the single most important line in this spec.** The live line multiplies by
`me->fft_norm`. **The commented lines do not.** Uncommenting one as written silently removes the
FFT normalisation and changes the global amplitude scale — which would (a) confound the arm
completely and (b) constitute an **input-scaling change, which is a standing prohibition.**

**The treatment MUST be `me->fft_norm * hamming_i(i, me->nfft);` — `fft_norm` preserved,
character for character.** ROW 0c asserts this mechanically.

### 1.6 Licence

`native/ft8_lib_vendor/LICENSE` and `native/ft8_lib_build/LICENSE` are both **MIT, © 2018 Kārlis
Goba**. The window functions are already in our tree under that licence. **No WSJT-X source is to
be consulted, read, or referenced for this arm** — none is needed, and the standing licence policy
is permissive-only. Window functions are textbook (Harris 1978); cite that if a citation is wanted.

---

## 2. The ladder — two rungs, run in order, second only on a stated condition

Bin spacing is **3.125 Hz** (6.25 Hz tone spacing, `freq_osr = 2`). Main-lobe width is stated
null-to-null, in bins and in Hz, because it is the cost side of this trade.

| Rung | Window | 1st sidelobe | Main lobe | Prior |
|---|---|---:|---:|---|
| baseline | Hann | −31 dB | 4 bins = **12.5 Hz** | current shipped behaviour |
| **1** | **Hamming** | **−42 dB** | 4 bins = **12.5 Hz** | **+11 dB rejection at ZERO main-lobe cost** |
| 2 | Blackman | −58 dB | 6 bins = **18.75 Hz** | +27 dB rejection, main lobe **+50% wider** |

🔴 **Rung 1 (Hamming) is the arm.** It buys 11 dB of near-in sidelobe rejection — more than the
3-to-6 dB cliff in §1.2 needs — **without widening the main lobe at all**. If sidelobe masking is
the mechanism, Hamming should move it.

⚠️ **Rung 2 (Blackman) carries a strong prior of HARM and must not be run first.** An 18.75 Hz
main lobe spans ±9.4 Hz, which swallows P15 (Δ5), P4 (Δ6), P0/P16 (Δ7), P13 (Δ7), P19 (Δ8), P12
(Δ9) and P20 (Δ9) — most of the battery. Run it **only** if Rung 1 reads ROW 3 (null), and read
its cost limb first.

🛑 **Do not run both rungs in one battery.** Two window changes in one run makes a null
uninterpretable — the exact mistake R1 exists to prevent, and the one that cost us the R2 line.

---

## 3. Pins — assert every one at startup, fail loudly

| item | value |
|---|---|
| scenario | **S7 only**, all 21 parts, unchanged. No scenario revision, no part edits. |
| population | **215** truth rows; per-part shape `{P2: 15, all others: 10}` |
| baseline recovery | WSJT-X **210/215**; OpenWSFZ **169/215** |
| baseline build | `main` @ `2ae939c`, shim **20260046**, `libft8.dll` SHA256 **`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`** — verified 2026-08-29 identical at both `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and `native/ft8_lib_build/libft8.dll`. Assert the **full** SHA, never a prefix, and never a shim-version label (`FT8_SHIM_VERSION` identifies nothing). |
| treatment build | shim **20260047**, SHA256 recorded at run time (HK-021(p) — see §7) |
| WSJT-X | **2.7.0**, binary date 2025-02-04, unchanged — the fixed reference appraiser |
| decoder config | `kMinScorePass2=10`, `osdCorrThreshold=0.1`, `osdNhardMax=60` — **unchanged on both legs** |
| audio device | `Voicemeeter AUX Input` — pass `--device` explicitly, the default is wrong on this machine |
| `ALL.TXT` fields | `[4]` SNR · `[5]` **DT** · `[6]` **freq Hz** — confusing 5/6 inverts a result |

🔴 **Both legs run in the SAME session, on the SAME machine, with the SAME harness.** Do not
compare the treatment leg against `22b749c`'s historical numbers. The baseline is **re-measured**.

⚠️ Clear **both** `ALL.TXT` files before arming (uncleared logs contaminate `*_matched.csv`,
NFR-021). ⚠️ **No commits of any kind while the run is live** — this cost us the 08-27 sweep.

---

## 4. ROW 0 — preflight, strict order, all must pass

| row | check | bar | if it fails |
|---|---|---|---|
| **0a** | truth population reproduces | exactly **215** rows, per-part shape as pinned; §1.1 and §1.2 tables reproduce **exactly** | **VOID** — loader or scenario drift |
| **0b** | 🔴 **instrument noise measured, not assumed** | baseline leg run **twice**; `abs(c_hit_1 - c_hit_2) <= 4` **and** `w_hit_1 == w_hit_2 == 0` | **VOID** — instrument too noisy for a 4-observation cost bar; escalate, do not widen the bar |
| **0c** | build identity **and the `fft_norm` trap** | treatment DLL SHA256 asserted; shim `20260047`; `git diff` of `monitor.c` between legs is **exactly one changed line**, and that line reads `me->window[i] = me->fft_norm * hamming_i(i, me->nfft);` | **VOID** — mechanically diffed, never asserted by eye |
| **0d** | 🔴 **the window is actually different** | at runtime, dump the first 8 `me->window[]` coefficients on both legs; require `max_abs_diff > 1e-6` **and** `sum(window)` differs | **VOID** — the change is in the tree but inert, and the arm would measure a no-op while looking like a null |
| **0e** | 🔴 **a unit whose metric MOVES** (HK-021(q)) | offline, no decoder: for one P13 trial's synthesised audio, compute the strong signal's window sidelobe level at the weak signal's tone bins under both windows. Require the Hamming figure to be **≥ 6 dB lower**. | **VOID** — if the window change does not reduce leakage at the geometry in question, the mechanism is absent and the decode arm cannot inform it |
| **0f** | strong-signal control | strong signals in P11–P14 remain **5/5 each** on both legs | **escalate** — a strong-signal regression means the arm is measuring something other than masking |

**0d and 0e are the two that would otherwise go unnoticed.** 0d catches a wired-but-inert change.
0e is the HK-021(q) requirement: exhibit a unit whose metric moves under treatment *before* the
gate runs, so a null cannot be blamed on an untested premise.

---

## 5. Metrics

Counts only. **No confidence intervals are to be computed or reported on `w_hit`** — n = 15 across
3 parts is 3 geometry clusters, and a CI at that n is theatre, not evidence (HK-021(i), (o)).
The gate resolves against the readout quantum: **1 observation = 1/15 = 6.67 pp on target,
1/200 = 0.50 pp on cost.**

- **`w_hit`** — weak-signal recoveries by OpenWSFZ in **P12, P13, P14**. Population **15**.
  Baseline **0**. The weak signal is the lower `true_snr_db` of the trial's two.
- **`c_hit`** — OpenWSFZ recoveries over **all other 200 S7 observations** (215 − the 15 weak).
  Baseline **169**.
- **`w11`** — weak-signal recoveries in **P11**. Population **5**. Baseline **5**. A must-not-lose
  control, not a gated metric.

🔴 **`c_hit` is the cost limb and it is mandatory (HK-021(t)).** `w_hit` is selected on exactly
the outcome the treatment targets, so a gate on `w_hit` alone is blind to what the treatment
costs. **Both limbs are evaluated in the same row.**

---

## 6. The gate — ship this predicate as code, character for character (HK-021(r))

Rows are evaluated in strict order. The first row whose condition is true is the verdict; later
rows are not evaluated.

```python
def win_a_gate(w_hit, c_hit, w11):
    """WIN-A verdict. Baselines: w_hit=0 of 15, c_hit=169 of 200, w11=5 of 5.
    Evaluated in strict order; first true row wins. Signed throughout (HK-021(l))."""

    # ROW 2 -- HARM. Checked FIRST so a benefit cannot mask a material cost.
    if c_hit <= 157:                      # lost 12 or more of 200 (>= 6.0 pp)
        return "ROW 2 -- HARM"

    # ROW 1 -- BENEFIT. Both limbs required.
    if w_hit >= 5 and c_hit >= 165 and w11 == 5:
        return "ROW 1 -- BENEFIT"

    # ROW 3 -- PARTIAL. Target moved but did not clear, or cost sits in the tolerance band.
    if w_hit >= 1:
        return "ROW 3 -- PARTIAL"

    # ROW 4 -- NULL.
    return "ROW 4 -- NULL"
```

### 6.1 Where every threshold comes from (HK-021(m), (o))

| threshold | value | derivation | resolvable distance |
|---|---:|---|---|
| `w_hit >= 5` | 5 of 15 | baseline is **0/15**; rule-of-three 95% UB on 0/15 is **18.1%**, so 5/15 = 33.3% sits clear of it. 5 is also exactly one part's weak population, so the result is interpretable as "one part's worth recovered". | **5 quanta** above baseline; nearest failing value 4/15 is 1 quantum away and reads ROW 3 |
| `c_hit >= 165` | lose ≤ 4 of 200 | ROW 0b requires the two baseline runs to agree within **4**. The benefit limb therefore tolerates exactly the measured instrument noise and no more. | **4 quanta = 2.00 pp**; validated by 0b, not assumed |
| `c_hit <= 157` | lose ≥ 12 of 200 | **3× the 0b noise bar.** A loss this size cannot be run-to-run variation. | **8 quanta** clear of the benefit bar — the two cannot both fire |
| `w11 == 5` | no loss | P11 is the one capture part that currently works. Losing it while gaining elsewhere is a trade, not a win, and must not read as BENEFIT. | 1 quantum |

The ROW 1 and ROW 2 bands are **mutually exclusive and separated by 8 observations**, so no input
can satisfy both, and the `157 < c_hit < 165` band falls to ROW 3/4 by construction rather than by
judgement.

### 6.1a The predicate was executed, not just written

Exhaustive check over the full input domain (`w_hit` 0–15 × `c_hit` 0–200): **zero** inputs satisfy
both ROW 1 and ROW 2. Boundary behaviour, run:

| case | `w_hit` | `c_hit` | `w11` | verdict |
|---|---:|---:|---:|---|
| baseline / no effect | 0 | 169 | 5 | ROW 4 — NULL |
| clean benefit | 5 | 169 | 5 | **ROW 1 — BENEFIT** |
| one quantum short | 4 | 169 | 5 | ROW 3 — PARTIAL |
| benefit at cost boundary | 5 | 165 | 5 | **ROW 1 — BENEFIT** |
| benefit, cost 1 over | 5 | 164 | 5 | ROW 3 — PARTIAL |
| gain but P11 lost | 5 | 169 | 4 | ROW 3 — PARTIAL |
| big gain, big cost | 15 | 150 | 5 | **ROW 2 — HARM** |
| pure harm | 0 | 157 | 5 | **ROW 2 — HARM** |

### 6.2 Pre-written consequences

| verdict | consequence |
|---|---|
| **ROW 1** | Sidelobe masking is a **material, cheap-to-fix** component of the capture deficit. Recommend Hamming to the Captain for merge, with the FP check of §6.3 as a merge precondition. **Do not** proceed to Rung 2 — the question is answered. |
| **ROW 2** | Hamming harms. **Revert. The window family is CLOSED** — do not proceed to Rung 2, whose main lobe is 50% wider and whose harm prior is strictly stronger. Record as a standing prohibition. |
| **ROW 3** | Real but sub-threshold movement. The mechanism is present and under-served by 11 dB. **This — and only this — licenses Rung 2 (Blackman)** under a fresh pre-registration reusing this gate with the same bars. |
| **ROW 4** | Sidelobe leakage is **not** the capture mechanism, given 0e confirmed the leakage itself moved. Close the window family. The capture deficit needs a different hypothesis and this arm has eliminated one cheaply. |

### 6.3 False positives are not deferred

Report OpenWSFZ's S7 unmatched-output count on both legs, and run **S5 in the same battery**
(N=60 AWGN default, R&R-009). A window change alters what reaches the CRC. **A recovery gain
bought with an FP rise is a different product, not a better one.** If S5 fails its ratified gate
on the treatment leg, ROW 1 does not license a merge recommendation regardless of `w_hit`.

---

## 7. 🔴 The arm is BLOCKED at drafting until the build exists (HK-021(p), HK-011)

There is no Hamming binary. Per HK-021(p) an arm may not be armed against a build that does not
exist, and per HK-011 `native/` changes need a **separate Developer session** — QA proposes and
stops; QA never runs `pre_merge_check.py`.

**Sequence:**

1. **QA** drafts `dev-tasks/2026-08-29-win-a-hamming-window-build.md` from §1.5, §3 and ROW 0c/0d.
   The task is one line of `monitor.c` (with `fft_norm` preserved), a shim bump to `20260047`, the
   ROW 0d coefficient dump, and rebuilds of all three platform binaries.
2. **Developer** builds it in their own session and records the SHA256 of each artefact.
3. **Captain** reviews the diff. It should be one line plus the version bump plus the dump hook.
4. **QA** arms WIN-A with both legs in one session.

⚠️ Windows console is `cp1252` — the ROW 0d coefficient dump must be ASCII or call
`reconfigure(encoding="utf-8")` (HK-009).

---

## 8. What this spec does NOT do

- 🛑 It does **not** touch `src/`, the decoder logic, the LDPC path, or any parameter.
- 🛑 It does **not** reopen subtract-and-resynthesise, the candidate-budget family, input scaling
  (see the §1.5 trap — the `fft_norm` requirement exists precisely to stay clear of it), OSR, or
  spectral locality. It is a **frontend analysis-window** change and touches none of those.
- 🛑 It does **not** revisit P2, which the Captain waived on 2026-06-22. P2 sits in `c_hit`'s
  complement only as an unchanged 0/15 and cannot move the verdict either way.
- 🛑 It does **not** license a live-corpus arm, a capture run, or a Developer session beyond the
  one build in §7.

---

## 9. Predictions, gating nothing (HK-021 practice, and my record is on the table)

My directional calls in this programme stand at **6 of 9**. These gate nothing and are recorded so
the arm scores itself honestly:

- **ROW 1 — 30%.** Hamming's 11 dB is comfortably more than the 3-to-6 dB cliff needs, *if*
  leakage is the mechanism.
- **ROW 3 — 20%.**
- **ROW 4 — 35%.** The cliff's sharpness (5/5 → 0/5 across 3 dB) is arguably too abrupt for a
  smooth sidelobe skirt and may point at a threshold or candidate-selection stage instead.
- **ROW 2 — 15%.** Hamming's far-out sidelobe *plateau* is worse than Hann's rolloff, which could
  cost the wideband parts.

🔴 **The value of this arm does not depend on my direction being right.** ROW 4 with 0e passing
eliminates a mechanism cheaply and permanently, which is worth more than the last ten weeks
produced.
