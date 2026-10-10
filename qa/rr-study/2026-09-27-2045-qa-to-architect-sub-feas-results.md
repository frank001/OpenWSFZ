# SUB-FEAS: ROW 0 results — FAIL, STOP (a FAIL is not a result)

**QA, 2026-09-27 20:45Z** (`date -u`, HK-017). Branch `qa/sub-feas` (from `origin/main`, HK-032).
Spec `2026-09-27-1855-…-sub-feas-…md` + Amendment 1 (`arch/subtraction-feasibility` `b4b9748d`).
Harness: `qa/rr-study/sub-feas/`. Full result: `qa/rr-study/sub-feas/sub_feas_result.json`
(numeric only, NFR-021/HK-037 scanned clean — `nfr021_pre_merge_scan.scan()`, run against every
file in this delivery, zero flags).

**Per sec.6: any ROW 0 FAIL is a STOP. Two rows FAIL. Stage 1 did not run** (the harness correctly
skips the expensive full-population fit once a FAIL is known — `elapsed=2637s`, not the
projected 2.81h, because bigfit over all of `P` never started).

## Population (Amendment 1's de-twinned isolation)

47,212 OWS `ALL.TXT` rows → SNR≥0 (11,527) → de-twinned-isolated (4,952 survive the co-channel
cut after removing 10,922 cross-decoder twins) → standard/re-encodable (4,445 = `P`). Anchor pool
(first 10% by time) 445; split A 1,906; split B 2,094.

**Timing probe** (sec.3): 150 real rows, live-measured, 259.1s → 1.727 s/row. Projected total
2.81h < 3h → **k=1, no thinning applied.**

## ROW 0 table

| row | result | bar | verdict |
|---|---|---|---|
| 0a encoder fidelity | 296/296 tested (4 void, excluded from denominator — see note) = 100.0% | ≥99% | **PASS** |
| 0b synthetic recovery | none: PASS all 3 SNRs; **drift: FAIL** at SNR 5,10 dB; fade: PASS all 3 | ≤1.0dB(none/drift), ≤2.0dB(fade) | **FAIL** |
| 0c noise floor | 400/400 within ±1.0dB of ensemble truth = 100% | ≥95% | **PASS** |
| 0d population size | A=1,906 B=2,094 | ≥1,000 each | **PASS** |
| 0e DLL pin | sha256 match | equal | **PASS** |
| 0f RR73 form | 342/345 on-air-grid wins = 99.13% | ≥90% | **PASS** |
| 0g anchor calibration | τ0=−0.1600s, IQR=45.0ms, median Δf=−0.641Hz | IQR≤40ms **and** Δf∈[−1,+1] | **FAIL** (IQR only, by 5ms) |
| 0i twin sanity (Amendment 1) | twin share 94.75%, 0 double-twins | ≥90% and =0 | **PASS** |

## 0a note: the void-row fix

A build-time bug, not a corpus finding: my first pass counted 4 sampled rows with the known
**negative-DT capture-chain artefact** (memory: "July 40m negative-DT rows footnoted
capture-chain-suspect, not decoder") as *failures*, because a clean synthetic signal literally
cannot be placed at a negative sample offset in a 15s slot buffer — that's a population-membership
fact, not an encoder/decoder fidelity question. Fixed to exclude void rows from the denominator
(disclosed, not silently dropped: `n_void=4` reported alongside `n_tested=296`). Re-run confirms
100%.

## 0g: what −0.16s means, and the 5ms margin

τ0 is **not** expected to match `gl_dll_pin.extraction_time_offset_s`'s own `+0.16s` — that constant
corrects the *native* `ft8_extract_llrs_at` call's internal lattice/waterfall addressing, which this
arm's fitter never calls (it correlates directly against raw PCM). τ0 measures a different thing
entirely: the gap between OWS's *reported* DT and the true sample-accurate transmission start in the
raw capture. That it converges to almost exactly one symbol period (0.16s) in magnitude, with the
opposite sign, looks like a real, disclosed finding about this corpus's own DT reporting, not a bug —
confirmed by a synthetic control (known ground truth, no real DLL involved) recovering exactly
`Δt=0, Δf=0`, i.e. the fitter itself carries no positioning bias.

The **IQR bar itself is failed by exactly one grid step** (45ms vs a 40ms bar, on a 5ms search grid) —
disclosed, not smoothed over: the mechanical predicate reads 45 > 40, so this is a FAIL, but readers
should know the margin is at the resolution limit of ROW 0g's own search step, not a wide miss.

## 0b: why drift gets *worse* at higher SNR (this is physical, not a bug)

`X` measures residual energy **relative to the noise floor**. A drift-impairment residual's *absolute*
leftover energy is roughly SNR-independent (it's an envelope-tracking modelling limitation — the
estimator tracks amplitude/phase, not a genuine frequency ramp, at a fixed reference frequency), while
the noise floor itself shrinks as SNR rises. A fixed absolute residual becomes a *larger* multiple of a
*shrinking* denominator — hence `X` rising from 0.41dB (SNR 0) to 4.70dB (SNR 10) for drift, while
`none` and `fade` (which the method **does** model, via `c(t)`'s time-varying complex gain) stay flat
near 0dB across all three. This is a genuine, disclosed limitation of the tested method (per-symbol
complex-gain tracking cannot fully absorb a true frequency ramp), not a defect in the harness.

## What this rules and doesn't rule

- **Not run**: ROW 0h (convergence), W* selection, the Stage 1 gate on split B. All were gated behind
  ROW 0 passing (sec.6) and never started — no bigfit pass over `P` occurred.
- **Bugs found and fixed during this build** (all confirmed via synthetic ground-truth controls before
  being trusted): (1) `fine_fit` silently ignored its own `freq_hz` argument, correlating a baseband
  template against a signal at the true carrier frequency — the ±2Hz search was searching the wrong
  2Hz window entirely. (2) A module-shadowing bug: `qa/rr-study/gap-locate/row0.py` silently shadowed
  this arm's own `row0.py` on `sys.path` (fixed: append, not insert(0, …), in `common.py`). (3) ROW 0f's
  RR73 alternate encoding fed literal text `"32373"` to `ft8_encode_message` — that value is a packed
  **field value**, not a parseable Maidenhead locator, so the text encoder either failed or produced a
  wrong waveform; fixed with a from-scratch LDPC(174,91) systematic encoder + CRC-14
  (`ldpc_encode.py`, generator matrix read live from the vendored MIT `ft8_lib` source, cited by
  file/line — validated bit-exact against `true_codeword()` for 6 test messages including RR73/RRR/73
  before use). (4) ROW 0a's void-row denominator bug (above).
- **Licence discipline**: no line copied from the QEX paper or WSJT-X. `ldpc_encode.py`'s generator
  matrix and CRC-14 parameters are FT8 protocol constants read directly from the vendored MIT-licensed
  `ft8_lib` (spec sec.1 explicitly permits mirroring it), same class of reuse as
  `synth/constants.py`'s own `GRAY_MAP`/`COSTAS_ARRAY`.

## Options for the Architect

1. **Accept the FAIL, STOP here.** Per spec sec.6 this is the mechanical, correct reading — a FAIL is
   not a result, and nothing downstream is licensed to run.
2. **Amend and re-arm a narrower re-run**, if either finding looks like it warrants a spec change
   rather than a stop — e.g. loosening ROW 0g's IQR bar given the 45ms/40ms/5ms-grid margin note
   above, or narrowing ROW 0b's drift bar/method (a genuine frequency-tracking envelope, not just
   amplitude/phase, might close the gap — that would be new work, not a re-run of this one).

I am not recommending between these — that's the Architect's call, per spec sec.6 and HK-021's own
discipline (I don't patch a pre-registered bar because the result is inconvenient).
