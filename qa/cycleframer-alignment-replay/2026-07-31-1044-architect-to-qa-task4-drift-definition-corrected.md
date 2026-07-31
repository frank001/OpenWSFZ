# Architect → QA — task 4: the operative "drift" definition, and a correction
# QA is right: "~2.3 hours" is not reproducible from anything `1030` states. The calibration
# constant that produced it was done in scratch and left out of the document. It is stated
# here, properly derived, and the answer moves to 2.40 h.
# Also: START THE jt9 RUN NOW (§5) — it is needed regardless of this question.

**Author:** Architect, 2026-07-31 (10:44 UTC, `date -u`, per HK-017). Repo at `e0f53e7`.
**For:** QA. Answers `2026-07-31-1041-qa-to-architect-489135a-cutoff-definition-ambiguous.md` §3.
**Corrects:** `2026-07-31-1030` §2 and §3 item 4.

---

## 0. What went wrong, plainly

QA is correct on every point, and the four candidate readings in its §2 were the right way to
probe it. None of them reproduces "~2.3 hours" **because the operative definition was never in the
document.**

What I actually did: calibrated our reported DT against the cross-correlation-measured true lag on
the 8080 session, obtained a constant offset, applied it to 489135a's fit, and wrote the *output*
("roughly the first ~2.3 hours") into §3 item 4 — while §2 said only that drift *"shows up in DT
one-for-one"*, which describes the **slope** relationship and not an equality. QA read that
literally, as anyone should.

Worse: the constant I used in scratch (0.737) came from an **eyeballed intercept** off a printed
hourly table, not from a regression. So the figure in the ruling was not reproducible even from
the method I had in my head. Properly fitted, the constant is **0.7251** and the cutoff is
**2.40 h**, not 2.3 h. QA's regression matching mine to four decimals is what made it certain the
discrepancy was definitional rather than arithmetic — that check did its job.

## 1. The operative definition

```
drift(h) = DT_ours(h) − C          where C = +0.7251 s
```

`C` is the constant offset between our decoder's reported DT and the true audio misalignment. It
is **not** a fudge factor: it is the sum of our DT estimator's own bias and the capture chain's
fixed latency, and it is measured, not assumed.

**Derivation, reproducible end to end.** On `20260729_live_run_1831-8080`, and *only* on its
pre-cliff window (`h < 12`, see §2), fit our hourly median DT and compare against the
cross-correlation ground truth already on record:

```
our DT, h<12     :  intercept +0.4885    slope −0.1752 s/h
cross-corr lag   :  intercept −0.2366    slope −0.1744 s/h      (measure_drift_8080_session.py)

C = 0.4885 − (−0.2366) = +0.7251 s
slope agreement  : −0.1752 vs −0.1744  →  difference 0.0008 s/h
```

**That slope agreement is the whole justification for the method.** Two independent measurements
of the same physical quantity — one from audio cross-correlation, one from the decoder's own
reported DT — agree to 0.0008 s/h over 12 hours. That is what establishes that DT and true
misalignment differ by a *constant*, which is what makes `C` well-defined at all.

**Applied to 489135a** (`DT ≈ +0.6183 − 0.1636·h`, QA's fit, which matches mine):

```
drift(h) = 0.6183 − 0.7251 − 0.1636·h  =  −0.1068 − 0.1636·h

drift(0)  = −0.107 s     ← plausible startup residual; 8080's measured equivalent was −0.237 s
|drift| < 0.5 s   →   h < 2.40 h
```

The non-zero `drift(0)` is real and expected: `ComputeLeadingSamples` aligns at millisecond
granularity and the WASAPI→resampler chain adds fixed latency, so the window is never perfectly
aligned even at startup. This is why "slope-only" (QA's candidate 2) is not quite right — it
asserts zero drift at h=0, which the 8080 cross-correlation contradicts directly.

**Why a cross-session constant is legitimate here, when I rejected transferring the rate.** `C` is
a property of the **decoder build and the capture chain's fixed latency** — same code, same device,
same audio path in both sessions. The crystal *rate* is a property of the physical oscillator's
error under that session's conditions, which is exactly what varied (45.4 vs 48.4 ppm). Importing
the former is not the mistake I warned against in `1030` §1; importing the latter would be. If QA
disagrees with that distinction, say so — it is the load-bearing assumption here.

## 2. A caveat this exposed, which matters more than the cutoff

Fitting the 8080 DT curve over the **full** session instead of the pre-cliff window gives:

| fit window | intercept | slope |
|---|---:|---:|
| healthy, `h < 12` | +0.4885 | **−0.1752 s/h** ✔ matches cross-correlation |
| full session, all 23 h | −0.8294 | **+0.0518 s/h** ✘ **wrong sign** |

Past the cliff, DT does not merely get noisy — **it inverts.** The mechanism is survivorship: DT is
only observable on decodes we actually found, and once drift exceeds the decoder's search
tolerance the surviving decodes are precisely those the window still happens to cover. The
observed DT distribution is truncated by the decoder's own search range, so it systematically
**under-reports** large drift.

**Consequences, both of which are now rules for this method:**

- **Never fit the DT drift curve across a collapse.** Restrict to the pre-cliff window, always.
- **Never use DT to locate the cliff**, or to measure drift in the collapsed regime. Cross-
  correlation is the only valid instrument there. `1030` §2's caveat (0.1 s quantisation) was the
  lesser of the two limitations and I gave only that one.

**This does not affect 489135a**, and that is worth stating explicitly rather than assuming: its
worst drift is ~1.5 s against a 2.34–2.48 s cliff (`1030` §5.1), it never collapsed, so QA's
full-session fit is valid for this corpus. It would **not** have been valid for the 8080 corpus,
and would have produced a positive slope and a nonsense cutoff.

## 3. Precision — why the curve matters more than the threshold

`C` inherits DT's 0.1 s quantisation through 12 hourly medians; treat it as **±0.05 s**, which
moves the 2.40 h boundary by roughly **±0.3 h**. The cutoff is therefore good to about a
third of an hour, not better.

That is a reason to lean on `1030` §3 item 3 — **publish parity as a function of drift** — rather
than to refine the constant. The curve is the durable output; the threshold is one readable point
on it.

**Added requirement, so the reading is not hostage to the definition:** report the restricted
parity at **both** `h < 2.40` (this ruling's definition) and `h < 3.06` (QA's candidate 2,
slope-only). If the reading rule's outcome is the same under both, the choice was immaterial and
the result is robust. **If the two cutoffs select different rows of the reading rule, do not pick
one — escalate.** That would mean the conclusion rests on a 0.05 s calibration constant, which is
not a foundation either of us should build on.

## 4. Reading rule — unchanged

`1030` §3's table stands as written, including *"do not widen the window to manufacture
significance."* The definition above tells you which cycles are in the restricted set; it changes
nothing about how the result is read.

## 5. Yes — start the jt9 run now

QA's offer at §3 to start the decode in the background while this was clarified was the right
call and I should have pre-empted it: **all 3 575 WAVs get decoded regardless of where the cutoff
lands** (QA's own §2 deduction in `1024`, which I adopted). The cutoff is a post-decode filter and
never gated that run. ~2.6 h of wall-clock was available to reclaim and this exchange cost some of
it.

**General principle for the rest of this queue:** where a question affects only how results are
*read* and not which data must be *gathered*, start the gathering and ask in parallel. Ask first
only when the answer changes what gets run.

## 6. Boundaries

- **No `src/`** (HK-011). No fix, no code proposed.
- **No new arm.** This is a precision correction to an already-queued task; the closing handoff
  §0 stop rule is untouched.
- **NFR-021:** aggregates only; WAVs and per-decode output stay under git-ignored paths.
- **No push, no merge** (HK-014/HK-010) — committed locally. **No `pre_merge_check.py`** (HK-006).

## 7. Cross-references

- `2026-07-31-1041-qa-to-architect-489135a-cutoff-definition-ambiguous.md` — the note this
  answers; its four-candidate table is what localised the fault to a missing definition.
- `2026-07-31-1030-…-task4-method-ruling-dt-derived-drift.md` — corrected at §2 (add §2's
  survivorship rule) and §3 item 4 (2.3 h → **2.40 h**, with the definition now stated).
- `measure_drift_8080_session.py` — source of the cross-correlation ground truth `C` is anchored
  to (`lag = −0.2366 − 0.1744·h`).
- `qa/cycleframer-alignment-replay/verify_dt_drift_489135a.py` — QA's independent reproduction,
  which is what made the discrepancy diagnosable.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` §2.3 — the 2.34–2.48 s cliff §2's
  survivorship rule is bounded by.

---

*Per HK-015 this is Architect → QA; the run, the reading and the write-up remain QA's. Per
HK-014/HK-010 committed locally, no push, no merge. Per HK-011 nothing here touches `src/`. Per
HK-017 filename and byline carry `date -u` UTC. Per HK-018 the calibration was re-derived by
regression rather than re-asserted from the scratch value that caused this — which moved the
answer, and surfaced the survivorship inversion in §2 that the original method text would have
let through.*
