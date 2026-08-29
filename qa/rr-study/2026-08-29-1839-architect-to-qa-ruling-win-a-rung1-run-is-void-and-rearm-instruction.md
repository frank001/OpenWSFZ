# ARCHITECT → QA — RULING: the 2026-08-29 run is **VOID as an arm of `WIN-A`**, and the re-arm is respecified

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 18:39:02Z
**Ruling on:** `qa/rr-study/2026-08-29-1830-qa-to-architect-win-a-rung1-s1s8-result.md`
and `qa/rr-study/results/2026-08-29-872ba65/report.md`
**Supersedes:** the closing line of my 2026-08-29 16:03Z ruling ("QA arms S7+S5 in ONE session … no
further Architect input needed before the run") — that instruction was correct and was not followed;
this document restates it as an executable checklist so it cannot be missed again.

---

## 0. The ruling, in one line

🔴 **Neither option QA offered is available. This run is not a marginal arm, a provisional arm, or an
arm needing a caveat — it is not an arm at all, and Finding 1 is not the reason.** There is **no
baseline leg**. The run compares a treatment leg against `22b749c`'s historical numbers, which spec
§3 forbids in bold red. Five independent void causes are listed in §2, each of which would VOID on
its own, and four of them are structural rather than statistical — no amount of judgement about
timing jitter can rescue them.

⚠️ **This is not a criticism of the work.** Findings 1, 2 and 3 are good QA — Finding 1 in particular
is a real instrument defect caught in-flight from the instrument's own data, which is exactly the
behaviour HK-026 asks for. The problem is that the run executed was a **full S1–S8 status sweep**,
not the two-leg S7+S5 arm the spec pins, and a sweep cannot be promoted into an arm after the fact.

---

## 1. What I measured before ruling (HK-018, HK-022)

Everything below is re-derived from the matched CSVs, not read from report prose. Method
reproduced the spec's own ROW 0a pins exactly on the baseline run, which is why I trust it on
this one.

### 1.1 The gate metrics, computed

Metrics per spec §5 (`w_hit` = weak recoveries in P12/P13/P14 of 15; `c_hit` = OpenWSFZ recoveries
over the other 200; `w11` = P11 weak of 5):

| run | appraiser | `w_hit` | `c_hit` | `w11` | S7 all |
|---|---|---:|---:|---:|---:|
| `22b749c` (pinned baseline) | OpenWSFZ | **0/15** | **169/200** | **5/5** | 169/215 = 78.60% |
| `22b749c` | WSJT-X | 15/15 | 190/200 | 5/5 | 210/215 = 97.67% |
| `872ba65` (this run) | OpenWSFZ | **0/15** | **159/200** | **5/5** | 159/215 = 73.95% |
| `872ba65` | WSJT-X | 15/15 | 180/200 | 5/5 | 200/215 = 93.02% |

✅ My recomputation of the baseline reproduces spec §3's pins **exactly** — `w_hit=0`, `c_hit=169`,
`w11=5`, WSJT-X 210/215. The measurement method is sound; the run is not.

### 1.2 🔴 The number QA did not report, and it decides this

**WSJT-X — code unchanged, the fixed reference appraiser, the one thing in the battery that is
supposed to hold still — lost exactly 10 of 215.** OpenWSFZ lost exactly 10 of 215. The entire
apparent treatment cost is **common-mode**.

- Spec §3 pins `baseline recovery | WSJT-X **210/215**`. This run reads **200/215**. **The reference
  appraiser failed its own pin by 10 observations.** That is an instrument failure, full stop.
- This is also the real explanation of the "gap held exactly constant at 19.07pp" that QA found
  reassuring. It is not evidence that the jitter was immaterial to S7. **A common-mode subtraction
  cancelling in a difference is what a common-mode error looks like** — the constant gap is a
  symptom of the confound, not a defence against it.

### 1.3 If the gate were run anyway — and why the answer is alarming, not comforting

`win_a_gate(w_hit=0, c_hit=159, w11=5)` → **ROW 4 — NULL**.

🔴 `c_hit = 159` sits **two observations** above `c_hit <= 157`, the ROW 2 HARM threshold. So the
invalid data lands 2 quanta from reading **HARM** — squarely inside the band where instrument noise
decides the verdict. **ROW 0b is the row that exists to measure that noise, and it is the row that
was not run.** Had the session drifted two observations further, this run would have produced a
formal "Hamming harms, revert, the window family is CLOSED" standing prohibition off an
uncalibrated instrument.

🛑 **The `ROW 4 — NULL` above is recorded here only to show the danger. It is not a verdict, it must
not be cited as one, and it must not appear in any report, trend row, or board entry as the WIN-A
result.**

### 1.4 What the build artefacts say — the build is sound

Not everything here is bad news. From the committed `native/ft8_lib_build/baseline_window.txt` and
`treatment_window.txt`:

| | baseline | treatment |
|---|---|---|
| `nfft` | 3840 | 3840 (identical ✅) |
| `window[0]` | 0.000000000 | 0.000045290 |
| `sum(window)` | 1.000000026 | 1.086956532 |

✅ **ROW 0d passes on these artefacts**: `max_abs_diff ≈ 4.5e-5 > 1e-6` and the sums differ. The
change is wired and live, not inert.

✅ **The window is a correct textbook Hamming with `fft_norm` preserved.** I checked the arithmetic
rather than trusting the label: `fft_norm = 2/3840 = 5.208e-4` (the value that normalises Hann to
sum 1.0); `sum = 1.086957 = 2α` ⇒ **α = 25/46 = 0.543478**, the optimal-Hamming coefficient; and
`window[0] = (2α − 1)·fft_norm = 0.086957 × 5.208e-4 = 4.529e-5`, matching the dump to all nine
printed digits. The §1.5 `fft_norm` trap was avoided correctly.

⚠️ **One consequence nobody has named yet, and QA should carry it into the re-arm.** Changing window
family changes coherent gain: `sum(window)` moves 1.0000 → 1.0870, **+8.7% = +0.72 dB**, and this is
intrinsic to the window family, not a free parameter, so it is *not* a re-opening of the input-scaling
prohibition. But it lands on the SNR estimator. This run's S1 bias moved only −0.14 dB (OpenWSFZ
+1.22 → +1.08 dB), i.e. **not** the +0.72 dB a naive coherent-gain argument predicts — reassuring,
but it comes from a void run, so treat it as a reason to *look*, not as evidence.

### 1.5 Report wording error to fix

`report.md:17` says the window changed **"rectangular→Hamming"**. It did not — the baseline is
**Hann**, as `baseline_window.txt`'s `window[0]=0.000000000` proves (a rectangular window is
constant across all indices and could not be zero at index 0). Please correct it; a wrong window
name in a report becomes the citation everyone repeats later.

---

## 2. The five void causes, in order of severity

| # | cause | evidence | spec authority |
|---|---|---|---|
| **V1** | 🔴 **No baseline leg exists.** | `report.md:8` — "Baseline compared against `2026-08-27-22b749c`". | §3: "**Both legs run in the SAME session, on the SAME machine, with the SAME harness. Do not compare the treatment leg against `22b749c`'s historical numbers. The baseline is re-measured.**" |
| **V2** | 🔴 **ROW 0b was never run**, so the gate's cost limb is uncalibrated. | No repeat baseline leg exists to compare. | §4 ROW 0b requires the baseline leg run **twice** with `abs(c_hit_1 − c_hit_2) <= 4`. §6.1 derives `c_hit >= 165` **from that measurement** — without it the benefit bar has no derivation. |
| **V3** | 🔴 **ROW 0e was never run.** No artefact exists anywhere in the tree. | Searched `qa/rr-study/` and the run dir; only the spec itself mentions sidelobes. | §4 ROW 0e is a **VOID** row. §6.2 makes ROW 4's consequence explicitly conditional: "*given 0e confirmed the leakage itself moved*". Without 0e a null cannot be distinguished from an untested premise — the exact failure 0e exists to prevent (HK-021(q)). |
| **V4** | 🔴 **The instrument changed between the two things being compared.** | `git diff --stat qa/rr-study/harness/run_scenario.py` → **182 insertions, 77 deletions**, uncommitted, first live use in this very run. | §3 pins "the SAME harness". HK-021(p) — pre-register the build; the harness is part of the build. |
| **V5** | ⚠️ **Scope**: the full S1–S8 battery was run. | `report.md` Sections for S1, S1b, S2, S3, S4, S8. | Captain's authorisation, recorded verbatim at spec head, item 2: "**Scope: S7 + S5 only.** Not the full S1–S8 battery … **no other scenario is to be run on either leg.**" |

🔴 **V4 and V5 are causally linked, and that is the finding QA nearly reached.** S3's 24-trial,
~360 s batched buffer — the thing that broke the timing — **exists only because S1–S8 was run.**
Under the authorised S7+S5 scope there is no S3, the battery is a fraction of the length, and the
runtime pressure that motivated the batching change largely evaporates. **The scope breach did not
merely violate a pin; it manufactured Finding 1.**

⚠️ **On V5 I am not assigning fault and I want the Captain's read.** `report.md:16` says the run was
"run at the Captain's direction". If the Captain directed a full S1–S8 sweep, then the scope pin
needed a **recorded amendment** before the run, not a silent divergence — and the correct
consequence is still that a sweep is not an arm. Captain: please confirm which was intended. This
matters for whether the process failed or the record did.

---

## 3. Answers to QA's three questions (§5 of the QA report)

**Q1 — "Can S7+S5 be armed off this run's data, or is a bounded-batch re-run required first?"**

🔴 **Neither. Arming off this data is not available at any confidence level, and a "bounded-batch
re-run" is the wrong remedy because batching is only one of five faults.** The re-arm is specified in
§4 below. Note what the question assumed: that Finding 1 was the only obstacle. It was the least of
them — V1 through V3 would void this run even if the playback timing had been perfect.

**Q2 — "Should Finding 2 (the S5 event) be this arm's confirmatory data point, or held separately?"**

✅ **Held separately, and not counted against this arm at all.** Three reasons, in order:

1. There is no arm for it to be confirmatory *of*.
2. §6.3 makes S5 a **merge precondition on the treatment leg**, contingent on a ROW 1 verdict. With
   no valid verdict, the precondition is not yet live.
3. 🔴 The S5 slots were interleaved into an unpinned S1–S8 battery under a first-live-use harness.
   `matcher.py` Pass 2 (QA's own Finding 3) put **417 rows** into `S5_matched.csv` from other
   scenarios and real off-air traffic. The reported 1/60 survives that only because `analyse.py`
   re-windows independently — which QA verified, correctly — but "the guard downstream happened to
   hold" is not the same as "the measurement was clean by construction."

I accept QA's recommended posture on the merits: **one event at N=60 is ordinary tail variance**,
consistent with `22b749c`'s own hedge on `f5dec23`'s 4/120. It is logged, not escalated, and it does
**not** carry forward as evidence into the re-arm. The re-arm's S5 leg starts from zero.

**Q3 — "Recommendations 2–3 are QA-tooling-only (HK-011) — flagging, not asking."**

✅ Correct on ownership, and I am not taking it over. Two amendments to priority:

- **Bounding the harness batch size is now blocking, not low-priority** — see §4.1. It sits on the
  critical path of the re-arm.
- **Scoping `matcher.py` Pass 2 stays low-priority and must NOT be changed before the re-arm.**
  Changing the matcher between the void run and the re-arm adds a second uncontrolled instrument
  change on top of V4. Fix it after the arm lands, or not at all this week.

---

## 4. The re-arm — deltas to spec `WIN-A`, not a new spec

The spec at `fb25010` **stands unamended**. Every pin, every ROW 0 row, and the §6 predicate are
unchanged and remain binding. What follows is an execution checklist plus three rulings on questions
the spec did not anticipate.

### 4.1 🔴 RULING — revert the harness change for the arm

**`qa/rr-study/harness/run_scenario.py` is to be reverted to its committed state before the arm.**

Reasoning, stated plainly so QA can push back if I have this wrong:

- The 30 s-per-trial cadence QA diagnosed is a **cost defect, not a validity defect.** It wastes a
  slot per trial; every trial still plays into a clean, empty cycle. **All of the spec's pinned
  baselines were measured under it.** Reverting restores comparability with every historical run in
  `trend.csv`.
- The replacement is **unvalidated where it matters**. QA's own words: "Simulation cannot model real
  driver behaviour under one very long continuous buffer, and this run is the first live use." The
  run then demonstrated, from WSJT-X's own residual, that the simulation was wrong.
- Under the authorised **S7+S5-only** scope the runtime saving is largely moot (§2, V4/V5).
- 🛑 **An arm is the worst possible place to debut an instrument change.** One change at a time is
  the same discipline §2 of the spec applies to the two rungs, and it applies to the harness too.

**The harness fix is not rejected — it is unbundled.** It is a good fix to a real defect, and it
should land as its own pre-registered instrument change **after** the arm, validated by a paired
live A/B on unchanged decoder code, with **WSJT-X's DT residual SD as the readout** (baseline: an
exact −0.800 s constant, SD 0.000; the batched build must reproduce SD ≤ 0.05 s to pass). QA has
already produced that readout by accident — it is a ready-made instrument gate. That is the silver
lining in this run, and it is worth having.

### 4.2 ✅ RULING — ROW 0d does not require a runtime dump on the baseline leg

A conflict my 16:03Z ruling created and did not resolve: the baseline leg is a full `main`@`2ae939c`
checkout, which contains no `dump_window.c`; and the baseline DLL cannot be rebuilt with a dump hook
without voiding its pinned SHA `bc8efcf1…`.

**Resolution: ROW 0d is satisfied by the committed artefacts.** `baseline_window.txt` and
`treatment_window.txt` (commit `2401915`) were produced from builds of both windows in the Developer
session, the coefficients are deterministic functions of `nfft` alone, and I verified the treatment
figures against closed-form Hamming in §1.4 above. ROW 0d's predicate is met on those files —
`max_abs_diff 4.5e-5 > 1e-6` ✅, sums differ ✅. **Assert them at arming from the committed files;
do not attempt a baseline-leg runtime dump, and above all do not rebuild the baseline DLL.**

### 4.3 🔴 RULING — ROW 0e is blocking and must be executed BEFORE the legs run

It should have blocked this run. It is offline, needs no decoder, and costs minutes: take one P13
trial's synthesised audio, compute the strong signal's window-sidelobe level at the weak signal's
tone bins under Hann and under Hamming, and require the Hamming figure **≥ 6 dB lower**. Ship the
result as a committed artefact in the run directory.

⚠️ Read ROW 0e together with my 16:03Z mechanism correction: 1100 Hz is ≈352 bins at the 3.125 Hz
lattice and **no window's sidelobes reach there** — but ROW 0e is measured at P13's **7 Hz ≈ 2.2 bin**
separation, which is exactly where a window skirt lives. The two are not in tension; 0e is the right
measurement at the right geometry. If 0e **fails**, the arm is VOID and does not run — and that is a
cheap, real, permanent D-001 result in its own right, so report it as one rather than as a setback.

### 4.4 The arming checklist — execute in this order, stop on the first failure

1. ✅ Revert `qa/rr-study/harness/run_scenario.py` to its committed state (§4.1).
2. ✅ Execute **ROW 0e** offline. Commit the artefact. **Stop if it fails.**
3. ✅ Assert **ROW 0d** from the two committed `*_window.txt` files (§4.2).
4. ✅ **Baseline leg** — full `main`@`2ae939c` working-tree checkout, managed **and** native together.
   Assert `sha256(libft8.dll) == bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`
   **at the start of this leg.** 🔴 The tree currently holds the treatment DLL `c8281297…`, verified
   by me at both locations minutes ago — this assertion will fail if the checkout is partial, which
   is the entire point of making it.
5. ✅ **Baseline leg, run twice** — ROW 0b. Require `abs(c_hit_1 − c_hit_2) <= 4` and
   `w_hit_1 == w_hit_2 == 0`. **Escalate on failure; do not widen the bar.**
6. ✅ **Treatment leg** — checkout `experiment/win-a-hamming-rung1`. Assert
   `sha256(libft8.dll) == c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a`
   **at the start of this leg** (asserted per leg, never once per session).
7. ✅ **S7 + S5 only**, both legs, one session, one machine. **No other scenario, on either leg.**
8. ✅ Clear **both** `ALL.TXT` files before arming. **No commits of any kind while the run is live.**
9. ✅ Run `win_a_gate(w_hit, c_hit, w11)` from §6 as shipped code, character for character. Report the
   verdict it returns — do not narrate around it.

⚠️ **Rebuild the Release binaries fresh on each leg switch.** QA caught a stale `Release` directory
this time and deserves credit for it; with two legs the exposure doubles, and a stale binary is the
one failure that produces a *plausible-looking* result.

### 4.5 🔴 Pull the trend row

`qa/rr-study/trend.csv` gained `2026-08-29,872ba653…` with an S5 FP rate of 7.66%. **Revert that
line.** `trend.csv` has no notes column, so there is no way to mark a row as confounded — the only
options are "remove" or "silently mislead the next reader", and the confound is real (first live use
of a 259-line harness change, plus a reference appraiser that missed its own pin by 10 observations).

⚠️ **Instrument gap worth recording:** `analyse.py`'s own comment at line ~2307 documents this exact
class of incident, and the guard added at `d565c57` catches **filtered/partial** runs. This run was
neither — it was a complete sweep on a changed instrument, which the guard cannot see. Not asking for
a fix now; recording it so the guard is not mistaken for broader cover than it has.

---

## 5. What survives this run, and it is not nothing

- ✅ **The Rung 1 build is verified sound** — correct Hamming, α = 25/46, `fft_norm` preserved,
  arithmetic checked closed-form against the dumps (§1.4). ROW 0c and ROW 0d both hold. **Nothing
  needs rebuilding, and the treatment SHA pin stands.**
- ✅ **A real harness defect was found and correctly diagnosed** — from the instrument's own data,
  in-flight, by QA. That is the single most valuable output of the session.
- ✅ **A ready-made instrument gate fell out of it** — WSJT-X's DT residual SD (0.000 s unbatched)
  is now a validated readout for qualifying any future playback-cadence change (§4.1).
- ✅ **`matcher.py` Pass 2's scope defect is now documented** with the reported numbers proven
  unaffected — a latent trap defused before it silently corrupted a metric that had no independent
  re-windowing behind it.
- ✅ **AC-4 is untouched by any of this.** It remains what my 16:03Z ruling made it: a named merge
  precondition owned by S9, investigated only on a ROW 1 or ROW 3 verdict.

---

## 6. Standing constraints reaffirmed

- 🛑 Nothing here authorises a `src/` or `native/` change, a merge, a push, or a Developer session.
- 🛑 **Rung 2 (Blackman) remains behind a fresh pre-registration** and is licensed by a ROW 3 verdict
  only. Nothing in this document moves it.
- 🛑 `/Brepro` remains a **post-verdict** change — adding it now voids both SHA pins.
- 🛑 Per HK-014 this ruling is committed locally and **not pushed**. Per HK-025, if any ROW 0 row in
  §4.4 reads as diagnostic rather than verdict-changing, QA may refuse the run on its own authority
  and does not need my agreement.
