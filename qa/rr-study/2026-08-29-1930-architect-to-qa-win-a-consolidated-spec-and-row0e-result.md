# ARCHITECT → QA — `WIN-A` **CONSOLIDATED SPEC**, and a ROW 0e result that gates the whole arm

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 19:30Z
**Supersedes, as the single document QA executes:** the 18:39Z ruling and the 18:59Z Amendment A1.
Spec `fb25010` remains the ratified pre-registration; **nothing here loosens one of its bars.**
**Status:** 🔴 **ARM IS GATED — do not run any leg until §2 is directed by the Captain.**

Three documents were becoming a reconciliation problem, which is the exact failure mode that
produced the void run. **This one is self-contained.** Shipped code: `qa/rr-study/win_a_row0e.py`,
`qa/rr-study/win_a_gate_v2.py`.

---

## 0. Headline — I ran ROW 0e, and it FAILS as pre-registered

ROW 0e was blocking and unspecified in method, so I implemented and ran it rather than sending QA to
invent it. **Pure window arithmetic — no decoder, no radio, no harness.**

🔴 **My implementation is validated against the build's own artefacts before any conclusion is drawn:**

| | computed here | committed dump |
|---|---|---|
| Hann `sum × fft_norm` | 1.000000000 | 1.000000026 |
| Hamming `sum × fft_norm` | 1.086956522 | 1.086956532 |
| Hamming `w[0] × fft_norm` | 0.000045290 | 0.000045290 |

Agreement to 8–9 digits ⇒ the windows in the model **are** the windows in the DLL.

**Leakage from the strong neighbour into the weak signal's bin, worst case over the strong tone's
sub-bin position, at each capture-family geometry:**

| part | ΔF | ΔF (bins) | Hann | Hamming | change | vs the 6 dB bar |
|---|---:|---:|---:|---:|---:|---|
| **P11** | 14 Hz | 4.48 | −47.27 dB | −39.91 dB | **−7.36 dB** | 🔴 **Hamming is WORSE** |
| **P12** | 9 Hz | 2.88 | −30.62 dB | −42.33 dB | **+11.71 dB** | ✅ PASS |
| **P13** | 7 Hz | 2.24 | −23.26 dB | −28.92 dB | **+5.66 dB** | ❌ **FAIL by 0.34 dB** |
| **P14** | 11 Hz | 3.52 | −40.39 dB | −40.42 dB | **+0.03 dB** | ❌ FAIL |

🔴 **The spec names P13 for ROW 0e. P13 returns +5.66 dB against a ≥6 dB bar ⇒ ROW 0e FAILS ⇒ by
spec §4 the arm is VOID and does not run.**

### 0.1 🛑 What I am NOT doing, and QA should hold me to it

P12 passes at +11.71 dB. **Switching ROW 0e to P12 now that I have seen the numbers would be
choosing the row after seeing the data** — the cardinal sin this programme has a standing rule
against ("never re-read a closed gate with a better metric — it earns a NEW pre-registration").
**I am not proposing it and QA should refuse it if anyone does.**

### 0.2 The two things this measurement explains, and they matter more than the verdict

**(a) It confirms my own ROW 2 prediction, quantitatively.** Spec §9 predicted 15% ROW 2 on the
grounds that *"Hamming's far-out sidelobe plateau is worse than Hann's rolloff, which could cost the
wideband parts."* That is exactly what P11 (−7.36 dB) and P14 (+0.03 dB) show: Hann's 18 dB/octave
rolloff overtakes Hamming's ~−42 dB plateau beyond ≈3.5 bins. **Hamming helps only in a narrow band
around 2.9 bins and hurts outside it.** P11 is the one capture part that currently works (5/5) and
is the gate's `w11` must-not-lose control.

**(b) 🔴 The decode data and the leakage model already agree, and they say the same thing.**

| part | model predicts | treatment leg measured |
|---|---|---|
| P12 | 11.7 dB *less* leakage ⇒ recovery should improve | **0/5 → 0/5. No change.** |
| P11 | 7.4 dB *more* leakage ⇒ recovery should degrade | **5/5 → 5/5. No change.** |

**An 11.7 dB leakage reduction bought nothing at P12, and a 7.4 dB leakage increase cost nothing at
P11.** Two large, opposite-signed perturbations of the theorised mechanism, neither of which moved
the outcome. ✅ **That is a real, positive elimination for the capture family's geometry — sidelobe
leakage is not what is binding — and it does not depend on the void run's absolute counts**, because
it reads *changes* within the treatment leg against its own baseline parts, not across sessions.

⚠️ Stated honestly: the treatment leg is confounded, so this is **strong corroboration, not proof.**
But it is independent of ROW 0e's 0.34 dB margin, and it points the same way.

### 0.3 The weakness in my own result, stated plainly

**P13 fails by 0.34 dB on a metric whose precise definition spec §4 left open.** I chose "worst case
over sub-bin offset, strong tone's skirt at the weak tone's nearest bin". Other defensible choices —
mean rather than worst case, integrating over the weak signal's occupied bins, modelling the
decoder's time-oversampling — could plausibly move the figure by more than 0.34 dB in either
direction. **A pre-registered bar decided by the implementer's choice of definition is not a clean
pass or a clean fail, and I will not present it as one.**

🔴 **This is my error, not QA's and not the spec author's bad luck: ROW 0e was written as a bar
without a method.** HK-021(r) — ship the predicate as code — applies to preflight rows too, and I
did not apply it when I wrote spec §4.

---

## 1. Self-review — three further corrections to my own prior documents

The Captain asked me to review my own findings before speccing. Three things were wrong.

### 1.1 🔴 ROW 0g's bar of ±4 was WRONG, and it would have cost a run

Amendment A1 §4.1 set ROW 0g at `abs(wsjt_s7_leg − 200) <= 4`, justified as "ROW 0b's own noise
allowance". **I never measured WSJT-X's actual run-to-run spread before setting it.** HK-018, on my
own document. Measured now, across every run with the comparable 215-row population:

| run | WSJT-X S7 |
|---|---:|
| 2026-06-20 `6e821fa` | 199/215 |
| 2026-06-22 `f11f438` | 202/215 |
| 2026-07-04 `793a298` | 207/215 |
| 2026-08-05 `3bd4cd0` | 207/215 |
| 2026-08-15 `8d6e1b1` | 205/215 |
| 2026-08-21 `7d36038` | 205/215 |
| 2026-08-22 `f5dec23` | 211/215 |
| 2026-08-27 `22b749c` | 210/215 |
| **2026-08-29 `872ba65`** | **200/215** |

⚠️ Pre-`06-19` runs are excluded — a scenario revision moved WSJT-X's S7 and the series is not
like-for-like across it (standing note in memory).

**Consequences, both of which change the advice I gave:**

1. ✅ **My headline claim survives but must be restated more carefully.** The last five comparable
   runs sit in a **205–211** band (mean 207.6, SD ≈ 2.7). **200 is below every one of them**, ≈2.8 SD
   low. It is an outlier, **not** "10 lost therefore broken" — the natural spread is ≈±3, not ≈0.
   The conclusion is unchanged; the phrasing I used with the Captain overstated the precision.
2. 🔴 **A1-REUSE is very likely dead on arrival.** ROW 0g would require the baseline legs to land in
   196–204 to match the treatment leg's 200. **Recent history says they will land in 205–211.**
   ⇒ ROW 0g fails ⇒ fall back to A1-FULL — after burning ~2.5 h to find out. **I should have caught
   this before offering the variant.**

### 1.2 ⚠️ An internal contradiction in Amendment A1 — S5

A1 §6 said the 08-29 `1/60` S5 event "does NOT carry forward as evidence" **while simultaneously
offering A1-REUSE, which reuses that very leg** — under which that event *is* the treatment
measurement. Both cannot be true. **Resolution: under A1-REUSE the 1/60 is the treatment S5 datum and
must be reported as such.** What does not carry forward is its use as *confirmatory evidence for a
prior claim*, which is a different thing and I conflated them.

### 1.3 🔴 The runbook change is materially larger than "skipping the 15 s silence"

The Captain retained the change described as *"skipping the 15 seconds silence between parts."* I
read the diff. What is implemented is **broader**, and the difference is not cosmetic:

- Every ordinary trial's rendered buffer is **concatenated into ONE `sd.play()`/`sd.wait()` call for
  the whole scenario** — not "silence removed between parts" but *the entire scenario played as one
  uninterrupted stream.* This is the mechanism that made S3's DT residual noisy.
- A new `_SLOT_SAMPLES` constant detects and **excludes S3's two oversized parts** (`dt_s` +2.4/+2.7
  render to 721920/736320 samples, not 720000).
- 🔴 **Truth-row writing was refactored** into a new `_write_truth_row()` parameterised over queued
  items, replacing the inline S8/S7/S4/else dispatch. **`truth.csv` is the ground truth for every
  metric in the battery** — this is a correctness-relevant change, not a timing one, and it is a
  wider blast radius than the description implies.

⚠️ **I am reporting the mismatch, not re-litigating the decision.** The Captain's judgement that it
is harmless may well be right — but it was formed about a smaller change than the one in the tree,
and he is entitled to know that before it is pinned as the instrument for three legs. ✅ The diff's
own comments show the author considered and **rejected** a tolerance-based relaxation *specifically
because it would inflate DT* — the DT sensitivity was understood; the batching broke it anyway.

---

## 2. 🔴 Three branches. The Captain directs; QA runs nothing until then

| | branch | what it costs | what it yields |
|---|---|---|---|
| **A** | ✅ **Accept the ROW 0e VOID. Close the window family.** | **zero** | Rung 1 and Rung 2 both die. Recorded as a standing prohibition. Backed by §0.2's independent decode evidence. |
| **B** | **QA independently re-derives ROW 0e** from spec §4's text, in their own implementation, **then** we compare | ~1 h, no radio | Removes *my* choice of definition from a 0.34 dB decision. 🔴 Only legitimate if the Captain fixes the decision rule **before** QA reports — see §2.1. |
| **C** | **Override ROW 0e and run the arm anyway** (A1-FULL, 3 legs, ~3.7 h) | ~3.7 h + a session | 🛑 **I recommend against.** Overriding a VOID row after seeing it fail is exactly the post-hoc move the ruling on AC-4 refused. And §0.2 says the decode answer is already visible. |

🔴 **My recommendation: A.** ROW 0e fails as pre-registered; the decode data independently agrees;
and the arm's reachable verdicts were already only ROW 4 or ROW 2 (`w_hit = 0/15` ⇒ ROW 1 and ROW 3
unreachable, verified exhaustively). **Branch A reaches the same place as branch C for zero hours.**

⚠️ **The honest case for B:** a 0.34 dB margin on an under-specified metric is thin, and §1.3 shows I
have already been wrong once today about something I had not measured. B is cheap insurance against
my own arithmetic.

### 2.1 If B is directed, the decision rule must be fixed FIRST

🛑 Otherwise B is just shopping for a pass. Before QA reports a number, the Captain fixes:

> **QA implements ROW 0e from spec §4's text alone. The Architect's implementation and figures are
> not shared until QA's number is committed.** Both are then run at **P13 only**. If QA's figure
> is ≥ 6 dB **and** mine is < 6 dB, the metric is definition-sensitive at the bar ⇒ **the row is
> VOID as under-specified and the arm does not run on it** — it would need a fresh
> pre-registration with the method shipped as code. **Two implementations disagreeing is not a
> pass; it is a demonstration that the bar cannot decide.**

⚠️ QA should note they may refuse this on HK-025 grounds if they judge it diagnostic rather than
verdict-changing. I evaluated both branches and believe it is verdict-changing (it decides whether
the arm runs), but that call is theirs.

---

## 3. The run spec — complete, executable, and gated on §2

**Do not execute any of §3 unless the Captain directs branch C, or branch B returns a pass under
§2.1's rule.** It is written out in full so no reconciliation across documents is needed if he does.

### 3.1 Corrections folded in

- **Scope: full S1–S8 on every leg** (Captain's amendment; the 18:39Z ruling's void cause **V5 is
  withdrawn — QA breached nothing**).
- **The runbook/harness change is RETAINED on every leg** (the 18:39Z ruling's revert instruction is
  withdrawn; a harness change only confounds when it falls *between* the compared legs). ⚠️ Read §1.3
  first.
- **A1-REUSE is withdrawn.** §1.1 shows ROW 0g would almost certainly fail. **A1-FULL only:
  baseline ×2 + fresh treatment ×1, one session, 3 batteries ≈ 3.7 h** (74 min each; the 08-29
  session ran 16:49–18:05Z ≈ 76 min, confirming the estimate). ⇒ **ROW 0g is deleted** — it existed
  only to license reuse.
- The 08-29 treatment leg is **not** reused for anything.

### 3.2 Pins

| item | value |
|---|---|
| scenarios | full S1–S8, identical battery and order, **every leg** |
| harness | the batched `run_scenario.py`. 🔴 **Currently UNCOMMITTED (+182/−77) ⇒ no identity ⇒ cannot be pinned. COMMIT IT FIRST and record its SHA in the run README.** An instrument that cannot be named cannot be re-run. |
| baseline build | `main` @ `2ae939c`, shim 20260046, `libft8.dll` SHA256 `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`. 🔴 **Full working-tree checkout, managed + native together** — `ExpectedShimVersion` throws on load against a DLL swap. |
| treatment build | `experiment/win-a-hamming-rung1`, shim 20260047, SHA256 `c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a` |
| S7 population | 215 truth rows, shape `{P2: 15, others: 10}` |
| WSJT-X | 2.7.0, binary date 2025-02-04, unchanged |
| decoder config | `kMinScorePass2=10`, `osdCorrThreshold=0.1`, `osdNhardMax=60` — unchanged both legs |
| audio device | `Voicemeeter AUX Input` — pass `--device` explicitly |
| `ALL.TXT` fields | `[4]` SNR · `[5]` DT · `[6]` freq Hz |
| 🛑 historical numbers | `22b749c`'s 169/210 are **provenance only, never the arm's baseline** |

### 3.3 ROW 0 — strict order, stop on first failure

| row | check | bar | on failure |
|---|---|---|---|
| **0e** | leakage actually moves (HK-021(q)) | `python win_a_row0e.py`, P13, ≥ 6 dB | **VOID — already run, already FAILED (§0). This is what §2 is deciding.** |
| **0a** | truth population | exactly 215 rows, shape as pinned, every leg | VOID |
| **0c** | build identity + `fft_norm` trap | SHA asserted **at the start of each leg**; `monitor.c` diff exactly one changed line reading `me->window[i] = me->fft_norm * hamming_i(i, me->nfft);` | VOID |
| **0d** | the window is really different | ✅ **already satisfied** from committed `{baseline,treatment}_window.txt`: `max_abs_diff = 4.5e-5 > 1e-6`, sums 1.000000 vs 1.086957. 🛑 **Never rebuild the baseline DLL** — it voids `bc8efcf1…` | VOID |
| **0b** | 🔴 instrument noise **measured** | baseline leg run **twice**: `abs(c_hit_1 − c_hit_2) <= 4` **and** `w_hit_1 == w_hit_2 == 0` **and** `w11_1 == w11_2 == 5` | **escalate. Do NOT widen the bar.** |
| **0f** | strong-signal control | strong signals in P11–P14 remain 5/5 each, every leg | escalate |

✅ **ROW 0b doubles as the empirical test of the Captain's "no effect" claim** about the runbook
change: two legs, same code, same harness, must agree within 4.

### 3.4 The gate

Shipped as code: **`qa/rr-study/win_a_gate_v2.py`**. Import it; do not retype it.
`python win_a_gate_v2.py` re-executes every claim below and exits non-zero on failure — **run it once
before arming.**

```python
def win_a_gate_v2(w_hit, c_hit, w11, c_hit_base):
    # ROW 2 -- HARM. Checked FIRST so a benefit cannot mask a material cost.
    if c_hit <= c_hit_base - 12:
        return "ROW 2 -- HARM"
    # ROW 1 -- BENEFIT. Both limbs required (HK-021(t)).
    if w_hit >= 5 and c_hit >= c_hit_base - 4 and w11 == 5:
        return "ROW 1 -- BENEFIT"
    # ROW 3 -- PARTIAL.
    if w_hit >= 1:
        return "ROW 3 -- PARTIAL"
    return "ROW 4 -- NULL"
```

`c_hit_base` = mean of the two baseline legs' `c_hit`, rounded half to even. Preconditions asserted
by ROW 0b **before** the call, never inside it.

✅ **Executed, not asserted:** at `c_hit_base = 169` it reproduces ratified spec §6 **exactly — 0
mismatches across all 19,296 domain inputs**; ROW 1 and ROW 2 never both fire for any `c_hit_base`
140–200; and at `w_hit = 0` the reachable verdicts are **exactly {ROW 2, ROW 4}**.

### 3.5 Execution order

1. Commit the harness change; record its SHA in the run README.
2. Run `python win_a_gate_v2.py` — must exit 0.
3. Baseline leg 1: full `main`@`2ae939c` checkout, assert `bc8efcf1…` **at leg start**, clear both
   `ALL.TXT`, rebuild Release, full S1–S8.
4. Baseline leg 2: identical. Assert the SHA again.
5. Evaluate **ROW 0b**. Escalate on failure; do not widen the bar.
6. Treatment leg: checkout `experiment/win-a-hamming-rung1`, assert `c8281297…` **at leg start**,
   clear both `ALL.TXT`, rebuild Release, full S1–S8.
7. Compute `c_hit_base`; call `win_a_gate_v2`; **report the string it returns.** Do not narrate
   around it, and do not report a verdict the function did not produce.
8. Report WSJT-X's S3 DT residual **mean and SD per leg** (§3.6).

⚠️ **Rebuild Release at every leg switch** and **clear both `ALL.TXT` before every leg**. 🛑 **No
commits of any kind while a leg is live.**

### 3.6 Recorded observation, gating nothing — the runbook change, measured

Interpretation pre-registered now so it cannot be chosen afterwards. Reference: `22b749c` unbatched,
an exact **−0.800 s constant, SD 0.000**; 08-29 batched, **−1.200 s, SD 0.330 s**.

| the three legs show | pre-registered reading |
|---|---|
| SD reproducible across legs | a stable **precision** cost that cancels in the contrast ⇒ the Captain's claim holds for every metric except S3's own precision gate ⇒ **retain the change**, re-baseline S3's gate under it |
| SD varies materially between legs | **non-stationary jitter — it can leak into contrasts. Escalate**; bound the harness before the next arm |

### 3.7 S5

Unchanged ratified gate: 95% Clopper–Pearson UB on the FP event rate **≤ 6%**, windowed to S5's own
60 injection cycles. Two baseline legs give **120** baseline AWGN slots vs 60 treatment — report
pooled **and** per-leg (HK-021(i): the legs are the cluster unit; 120 slots are not 120 independent
trials). The 08-29 `1/60` is not carried forward (§1.2). 🛑 **Do not touch `matcher.py` before the
run** — its Pass 2 scope defect is real but provably not affecting reported numbers, and fixing it
now stacks a second uncontrolled instrument change.

---

## 4. Standing constraints

- 🛑 No `src/` or `native/` change, no Developer session, no rebuild of any binary, no merge, no push.
- 🛑 **Rung 2 (Blackman) stays behind a fresh pre-registration**, licensed by ROW 3 only — unreachable
  at `w_hit = 0`. ⚠️ §0.2's P11 result (−7.36 dB at 4.48 bins) is **direct evidence against**
  Blackman, whose main lobe is 50% wider; if branch A is directed, record that alongside the closure.
- 🛑 `/Brepro` remains **post-verdict**. Adding it now voids both SHA pins.
- 🛑 **AC-4** stays a merge precondition owned by **S9**, investigated only on a ROW 1 or ROW 3
  verdict — both unreachable on current data. On ROW 2/ROW 4, or on branch A, the rung dies and AC-4
  dies with it.
- 🛑 **PULL the `trend.csv` row** `2026-08-29,872ba653…` (18:39Z ruling §4.5) — still outstanding.
- Per HK-014 this is committed locally and **not pushed**. Per HK-025 QA may refuse any row here on
  mechanical grounds without my agreement.
