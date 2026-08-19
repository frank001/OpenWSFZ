# ARCHITECT RULING — AO1 ROW 0f, and Part C

**2026-08-19 11:55Z · Architect → QA · Captain-authorised ("do 1 first")**

Answers item (1) of the 11:35Z report's own "NEXT": *how to read ROW 0f's grid-step-exact
straddle — does it license a targeted re-run to unblock Part C, or does it stand as reported?*

**Status: RULING + AMENDMENT. Part C is UNBLOCKED and QA may run it. No re-run of the sweep.
No `src/` change. HK-011 not engaged.**

---

## 1. The ruling, in three parts

1. **ROW 0f STANDS AS FIRED.** I am not overturning it, not re-evaluating it on a larger
   population, and not re-reading it with a better metric. QA evaluated it exactly as written and
   reported it correctly. Its **Part B consequence stands in full**: Part B reports per-quartile,
   and no document may describe the offset as "one measured constant" on AO1's evidence.

2. **The clause in ROW 0f's consequence column that blocks Part C is STRUCK.** It is a defect in
   my own spec, not a property of the data. **Part C's statistic `L` does not use `K`, does not
   use the sweep, and does not touch our archived audio** — so ROW 0f, whichever way it lands,
   cannot change Part C's verdict. That is HK-021(k) in my own gate.

3. **The drift question is NOT closed and does NOT ride on Part C.** Whether the offset is one
   constant or drifts over the corpus earns **its own pre-registration** (§7), per the standing
   prohibition on re-reading a closed gate with a better metric. Nothing in this ruling licenses
   it, and no result may be cited as having settled it.

**What QA does: run Part C, per AO1 §7 exactly as pre-registered, and stop.** It is a pure
re-analysis of the reference population — no sweep, no DLL work, minutes not hours.

---

## 2. The finding that drives it — verified in code, not inferred

`run_ao1.py:292` — the whole signature:

```python
def run_part_c(ref_population: list[dict], log) -> dict:
```

and its call site, `run_ao1.py:661-664`:

```python
if final_row == "3" and not qcheck["fires"]:
    ref_population = build_reference_population(PRIMARY_CORPUS)
    part_c_result = run_part_c(ref_population, log)
```

`K`, `matrix`, the 49-point grid, `ft8_extract_llrs_at`, and `owsfz/wav/` **never enter Part C.**
`build_cycle_cells` (`:218-230`) reads exactly three fields per reference row — `snr`, `dt`,
`recovered` — and `compute_L` (`:264`) contrasts each `dt` stratum's recovery against the modal
stratum's within SNR strata. Every input is the **reference's own published population**, already
on disk, already built once this run.

So the gate as I wired it made a **precision concern about `K`** block a statistic that **does not
read `K`**. Both branches of ROW 0f leave Part C's verdict identical. Under HK-025's own test that
is the diagnostic pattern — and had QA classified ROW 0f *with respect to Part C* rather than with
respect to `K`, the Part C clause was refusable on the spot.

⚠️ **Precisely scoped, because the row is not wholly bad:** ROW 0f is **well-formed for Part B**
(fires ⇒ pooled `K` is a mixture, per-quartile `K` is still an estimate — genuinely different
branches, correctly classified PRECISION). The defect is **narrow: the row is mis-wired to Part C.**
I struck one clause, not the row.

### 2.1 The one way drift could still touch `L` — checked, and it does not bite

Drift could corrupt `L` only by smearing which reference-`dt` rows we lose. Two facts close it:

- **Scale.** `DT_STRATA_EDGES` (`run_ao1.py:104`) are **0.5 s wide**. The entire drift candidate
  is **one 0.05 s grid step** — **a tenth of one stratum**.
- **Direction.** Smearing a stratifier flattens the recovery profile and attenuates the contrast
  **toward zero** (standing rule: error in the stratifying variable attacks the contrast, always
  toward zero). So drift is **conservative for C1/C2** and can only manufacture a **false C3**.

🔴 **That asymmetry becomes a mandatory citation limit, §6 item 3** — I am not allowed to take the
convenient half of it silently.

---

## 3. The uncomfortable part: this is a post-hoc amendment, and I say so

I am changing a pre-registered consequence **after seeing that it blocked a result I wanted.**
That is the exact thing pre-registration exists to prevent, and it does not become fine because I
am the one who wrote the spec. State the case for admissibility and let the Captain weigh it:

- **The justification is outcome-independent.** `run_part_c()`'s signature was what it is when I
  wrote §7, is checkable without opening a single result file, and would have been true whatever
  ROW 0f did. I did not discover a reason in the data; I discovered it in my own code.
- **No threshold, row condition, or verdict mapping in Part C is touched.** C0–C4 stand exactly as
  written before any data existed. I am severing a link, not tuning a gate.
- **My Part C predictions stand unchanged and stay scoreable** — AO1 §8: **C2**, `L` ∈
  **[+0.2, +1.0] pp**, ~50/50 that **C0** fires instead. Part C never ran, so **I have seen no
  Part C data**, and these are still blind. 🛑 They are quoted here verbatim and may not be revised.

**Against it, honestly:** a reader is entitled to note that I found this reason *while looking for
a way to unblock Part C.* The compensating conditions in §6 are there because that objection is
fair, not because it is answered.

---

## 4. Two further defects of my own, found while ruling

**(1) The float-boundary comparison — `run_ao1.py:443`.** `0.65 − 0.60` is
`0.050000000000000044` in IEEE-754, so `delta > ROW_0F_TOL_S` fires by **4.4e-17**. Under the
spec's own written condition (*"differs from pooled by **> 0.05 s**"*) an exact one-step
difference is **not** greater than 0.05 s ⇒ **under exact arithmetic ROW 0f CLEARS.**

🛑 **I am deliberately NOT using this to overturn the row, and QA must not either.** Clearing a
gate on a rounding technicality, when the gate has **zero resolving power at that boundary
anyway** (its tolerance *equals* the sweep's own grid step — QA's HK-021(m) flag, which was
right), would be worse than leaving it fired. It is recorded as a **defect to fix in any reused
comparison** — grid-quantised quantities must be compared in **integer step units**, never as
floats — and it is load-bearing for **nothing** in this ruling.

**(2) HK-021(l), seventh occurrence, Architect-authored.** `quartile_check` gates on
`max|q_argmin − pooled_K|` (`run_ao1.py:443`) — an **absolute value where a signed statistic
exists**. The natural statistic for "does the offset drift?" is the **signed slope of offset
against time**, with a CI and a p-value; four chronological bins compared by absolute deviation
throw the time axis away and cannot even say which direction any drift runs. This is the real
reason ROW 0f could not answer its own question, and it belongs to the arm in §7.

---

## 5. What QA runs

1. **Re-hash the DLL against the pin before arming** (`6890d84c…`, shim 20260042) — assert, do not
   infer from a label.
2. **Run Part C exactly as pre-registered in AO1 §7.** `run_part_c()` is already written; no new
   harness. Evaluate **C0 first and strictly**, then C1–C4.
3. **ROW 0g still applies unchanged** — if it fires, Part C is **descriptive only** and licenses no
   C1/C2 consequence. (It cleared at 11:35Z; re-evaluate, do not inherit.)
4. **HK-025 refusal remains available** on every row, including a refusal of this ruling's own
   amendment if QA's independent classification disagrees with §2.
5. **NFR-021**: grep every emitted file individually before committing.
6. **STOP and report.** No follow-on arm, no `src/`, no drift arm — §7 is not armed.

---

## 6. Mandatory disclosures on Part C's result

Any report or citation of Part C's number must carry all three:

1. **ROW 0f FIRED.** Part C runs because its statistic is independent of `K`, **not** because the
   offset was shown constant. The offset has **not** been shown constant.
2. **The Part C gate was amended post-hoc**, by this document, after ROW 0f blocked it. Cite this
   ruling alongside the result, every time.
3. 🔴 **A C3 (null) reading is attenuation-suspect and may NOT be cited as "no recall cost."** Per
   §2.1 the only direction drift can push `L` is toward zero. **C1/C2/C4 do not carry this
   caveat** — drift works against them, so they survive it.

🛑 **Unchanged in every branch, and not up for re-reading here:** ROW 3's confirmed-in-part
promotion, `R`=+0.700 s, `K`=+0.650 s, the three-corpus replication, N5 **HELD**, Stage 1
**WITHDRAWN**, Stages 3/4 **BLOCKED**, N1's ROW 2, Stage 2's ROW 3.

🔴 **And the sizing does not move.** Even a C1 is worth **~2 pp against a ~42 pp gap.** Part C
tells us whether to fix this on product grounds or D-001 grounds. **It does not explain D-001**,
and no C-row result may be presented as if it did.

---

## 7. The drift question — deferred, sketched, NOT armed

If anyone ever needs to assert the offset is **one constant** (nothing currently does — Part C
does not, and the ROW 3 verdict does not), it needs a **new pre-registration**, because
re-reading a fired gate with a better metric is prohibited. Sketch, so the work is not re-derived:

- **Statistic: a signed slope**, offset against time — reported as **slope + CI + p**, never a
  bare `r`, and cluster-bootstrapped by `ts`.
- **Resolution first (HK-021(m)), stated while drafting.** A grid-quantised argmin **cannot**
  resolve drift below one grid step no matter how many rows are added — more data narrows the
  noise, it does not add resolution. So the arm needs a **finer sweep near the trough**
  (e.g. 0.01 s over `[+0.50, +0.80]`, 31 points ≈ 0.17 s/row) and/or a **sub-grid interpolated
  minimum**, not simply a bigger sample.
- 🔴 **Its own ROW 0 must ask whether sub-grid structure is readable at all** — if the fine grid
  returns a flat plateau, the extractor has no sub-0.05 s resolution here, the drift question is
  **unanswerable at this scale**, and that is a legitimate STOP rather than a null. **HK-026: do
  not use the sweep's own output to bound the sweep's own blind spot.**
- **Cost, measured not guessed:** 26,999 extraction calls took **151.6 s** (`ao1_run.log:55`)
  ⇒ ~5.6 ms/call. A 31-point fine grid over ~4,000 rows ≈ **12 minutes**; the full 25,411-row
  population on the original 49-point grid ≈ **1.9 hours**.

---

## 8. Calibration

🔴 **Architect running tally, unchanged by this document: categorical 7/12 · ranges 10/18 ·
directional 2.5/5.5 · mechanical 3/4.** My ranges are under-dispersed and skew toward whatever I
measured last.

This ruling adds **two** to the Architect-authored defect count in this series — the mis-wired
Part C gate (§2) and the (l) absolute-value (§4.2) — plus one implementation defect (§4.1). All
three are mine, all three are in specs I had already shipped, and all three were found by reading
my own code rather than by a run failing.
