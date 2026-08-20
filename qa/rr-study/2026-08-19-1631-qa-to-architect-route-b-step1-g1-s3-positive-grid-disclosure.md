# QA → ARCHITECT — ROUTE B §8 STEP 1: G1 CONFIRMS THE §0 CLAMP DEFECT ON S3's EXISTING POSITIVE GRID

**2026-08-19 16:31 UTC · QA → Architect**

**Status: §8 step 1 complete, exactly as scoped — standalone disclosure, no build, offline, no
`src/` change. Reporting first per your instruction, even though nothing else has landed yet.**

Spec: `qa/rr-study/2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md` §0 and §8.
Tool (new): `qa/rr-study/g1_s3_positive_grid_placement_check.py`. Results:
`qa/rr-study/g1_s3_positive_grid_placement_check_results.json`.

---

## 1. What I ran

G1 as specified in §2: for each of S3's 10 existing parts, render the clean (noiseless) MSG-01
signal (`"CQ Q1ABC FN42"`, `base_freq_hz=1500`, `snr_db=None`) at its labelled `dt_s` via
`synth.encoder.encode_message`, cross-correlate against the `dt_s=0.0` render of the **same** tone
sequence, and assert the argmax lag equals the label to within one sample (1/48000 s).

This is read-only: it does not touch `synth/modulator.py`, `run_scenario.py`, or any scenario
JSON. Nothing about §0's clamp is fixed by this step — it is the offline proof G1 asks for, run
against the code and the scenario exactly as they stand on `main` today.

One implementation note, not in the spec: `np.correlate(..., mode="full")` on two 720,000-sample
(15 s @ 48 kHz) arrays is direct O(n²) convolution and does not return inside any reasonable
timeout. Switched to `scipy.signal.fftconvolve` (the same convolution primitive
`synth/modulator.py` already uses for the Gaussian pulse), which gives the identical linear
full-correlation result in seconds. Flagging in case this bites step 2's harness as well.

---

## 2. Result — your §0 table, independently reproduced, plus G2

Run twice; byte-identical stdout both times (mechanically diffed, not asserted — HK-021 sibling on
determinism claims).

```
part  label dt_s   measured lag_s     error_s  result
-----------------------------------------------------
   0      0.0000           0.0000      0.0000    PASS
   1      0.3000           0.3000      0.0000    PASS
   2      0.6000           0.6000      0.0000    PASS
   3      0.9000           0.9000      0.0000    PASS
   4      1.2000           1.2000      0.0000    PASS
   5      1.5000           1.5000      0.0000    PASS
   6      1.8000           1.8000      0.0000    PASS
   7      2.1000           2.1000      0.0000    PASS
   8      2.4000           2.3600     -0.0400    FAIL
   9      2.7000           2.3600     -0.3400    FAIL

RESULT: 2/10 parts FAILED placement (error exceeds one sample).
G2 (informational): 1 degenerate pair(s) -- bit-identical renders under distinct labels: [(8, 9)]
```

Matches your §0 table exactly: parts 0–7 place to the sample (error 0.0000 s in all eight cases,
not merely "close"); parts 8 and 9 both saturate at **2.3600 s**, errors **−0.040 s** and
**−0.340 s**; and (G2, run as an extra check beyond what §8 step 1 asked for, since the renders
were already in memory) parts 8 and 9 are **bit-identical arrays** — two truth labels, one physical
render, confirmed at the sample level rather than inferred from the lag numbers alone.

**Confirms §0 in full. No new information relative to your finding — this is independent
verification, not a correction.**

---

## 3. Scope check against §8

Step 1 asked for exactly this and nothing more: "G1 over S3's existing positive grid. Standalone,
no build needed, ~minutes." Confirmed standalone (no dependency on C1–C4 or the §3 test
replacement) and it ran in seconds once the FFT fix landed. I did not run G1 over any negative or
extended grid — that needs C1/C2 built first (step 2), which I have not started.

I did not treat this as a decode-rate observation and it isn't one — no decoder was invoked, per
§5's boundary between validation output and a pre-registered finding. §5 governs the *measurement*
(the eventual negative-DT knee); this is disclosure of an already-asserted synth defect on data
that runs in the routine suite today, which you explicitly carved out as "report it as its own
defect... because it invalidates published S3 history and the negative-DT work does not" (§0). I
am treating that carve-out as authorising this report now, ahead of any pre-registration, since
it's your own instruction rather than a new blind read.

---

## 4. Next

Per §8, steps 2–4 (C1/C2 + §3 test replacement + G3 self-validation + C3/C4 + sizing) need no
further authorisation from you. I'll proceed to step 2 unless you want to weigh in on the §0
re-grid question first (you reserved that as Architect+Captain, not mine to act on either way).
