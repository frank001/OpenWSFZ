# `AWGN-FP` M1–M4 report — full-scale offline measurement (N=2000/part S5, N=230/part S1)

**QA, 2026-09-03 15:35Z** (`date -u`, HK-017). Base `main`@`b4dd754`, shim `20260049`.
Spec: `qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md` (Architect → QA,
2026-09-02 19:06Z) + **Amendment 1** (2026-09-02 20:05Z, ROW 2/ROW 3 revised — the version
executed below). ROW 0 (a–d) was run and PASSED in the prior session
(`qa/rr-study/awgn-fp-replay/results/ROW0-report.md`) — not re-run here; this report picks up at
§5 step 3 ("Only then: N ≥ 2,000 per part, M1–M4").

Binary pin re-asserted for every decode in this run (HK-021(p)): SHA256
`ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e` (shim `20260049`,
`AwgnFpReplayTests.PinnedShaWinX64`). Both new xunit Facts assert this before decoding; both
passed.

---

## 0. 🔴 Headline — read this before the numbers below

**ROW 2 (revised) fires cleanly and unambiguously: an emission-side excess floor separates every
false accept from every genuine decode in this data, with an enormous margin (not merely the
required 6 dB).** But the run also surfaced something the pre-registered gate is explicitly built
to catch and flag rather than hide: **the offline instrument's own chronic false-accept rate,
measured precisely at N=4,000, is roughly 5× the historical in-chain pooled rate.** ROW 1 does
**not** fire (the pooled rate falls far outside the pre-registered chronic-rate band) — per the
spec's own instruction for that outcome, this section reports the number and asserts nothing
about chronic-vs-regression from ROW 1 alone, but the size of the gap is large enough that it
belongs in the headline, not buried in §2. **Recommendation to the Architect: open this gap as its
own follow-up question** — it does not overturn ROW 2 (which is an internal, within-instrument
separation claim, not an absolute-rate claim), but it does bound how far ROW 2's magnitude
(removal fraction, event counts) can be read as representative of in-chain behaviour.

---

## 1. What was measured

- **S5 AWGN population (M1/M2/M4):** parts 0+1, N=2,000/part = 4,000 slots, rendered via the
  REAL, unmodified `harness/run_scenario.py --dry-run --dump-wav-dir` peak-normalising path
  against `awgn-fp-replay/scenarios/s5-noise-m1m4.json` (an exact copy of `scenarios/s5-noise.json`
  with `trials` raised 30→2000; trials 0–29 reproduce the in-chain sweep's own 60 seeds exactly —
  confirmed byte-identical WAVs against `_work/row0b_baseline/`, see §3.1). Decoded via
  `tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs`'s new `M1M2M4_S5AwgnPopulation_N2000PerPart`
  Fact.
- **S1 signal-present population (M3):** 10 parts × N=230/part = 2,300 slots, rendered against
  `awgn-fp-replay/scenarios/s1-m3-complement-n2300.json` (an exact copy of
  `awgn-fp-replay/scenarios/s1-m3-complement.json` with `trials` raised 25→230; trials 0–24
  reproduce ROW 0d's own 250 seeds exactly). Decoded via the new
  `M3_S1GenuinePopulation_N230PerPart` Fact.
- **Analysis:** `qa/rr-study/awgn-fp-replay/m1_m4_analysis.py`, ships every pre-registered
  predicate as code (HK-021(r)); raw output at `results/m1_m4_analysis_report.txt` /
  `.json`.
- **NFR-021:** both new decode CSVs redacted before this report was written —
  `results/REDACTION-MAP-M1-M4.md` (806 distinct tokens across 361+455 occurrences, all decoder
  output, guarded against the injected truth text before rewriting, byte-level CRLF/BOM-preserving
  rewrite, re-scanned to 0 after). See §6.

## 2. M1 — per-slot false-accept event rate

| Population | n | events | rate |
|---|---:|---:|---:|
| S5 part 0 | 2,000 | 225 | 11.25% |
| S5 part 1 | 2,000 | 210 | 10.50% |
| **Pooled** | **4,000** | **435** | **10.875%** |

This run's own exact 95% Clopper–Pearson CI on the pooled rate: **[9.93%, 11.88%]** — a tight,
high-precision reading, exactly what N=60 could never deliver (spec §0's whole reason for existing).

## 3. ROW 1 — chronic vs. recent-regression, and the validity gap it surfaces

**Pre-registered band** (exact Clopper–Pearson 95% CI for the pooled in-chain rate over every full
sweep since 2026-08-21, 12/540 = 2.22%): **[1.15%, 3.85%]**.

**ROW 1 FIRES: False.** The pooled offline rate (10.875%, CI [9.93%, 11.88%]) sits entirely above
and outside the historical band — not a borderline miss, a non-overlapping one.

Per spec: *"report the number, do not assert chronic-vs-regression either way from ROW 1 alone."*
Doing exactly that, with the context a bare non-fire would omit:

### 3.1 This is not a rendering or decode-order artifact — verified, not assumed

Before reporting a number this surprising, QA checked three concrete alternative explanations
before accepting it:

1. **Seed collisions at scale?** No — all 4,000 rendered seeds are distinct (`_m1m4_s5_truth/
   truth.csv`, verified by direct count).
2. **Do the WAVs for the 60 seeds shared with the original in-chain anchor (trials 0–29, both
   parts) match byte-for-byte?** Yes — SHA256 of all 60 files identical between
   `_work/row0b_baseline/` and `_work/m1m4_s5/` (60/60 match, 0 mismatches).
3. **Is the elevated rate concentrated in a particular trial range** (which would suggest a
   seed-generation or decode-ordering defect rather than a real chronic rate)? No — bucketed into
   five 400-trial windows per part, the rate is flat: 9.25%–12.75% across every window, both parts,
   no drift, no discontinuity at the trial-1000 boundary (where the WAV filename's zero-padded
   trial number stops being 3 digits, a plausible ordering-defect trigger that was specifically
   checked for and not found).
4. **Do the 60 shared slots decode identically whether run standalone (ROW 0b) or embedded inside
   this 4,000-slot batch?** Yes — 0 of 60 slots differ in `n_decodes` between the two runs (both
   give exactly 6 events on the same 60 keys). ROW 0b's own report text states 6 events, not 4 —
   QA's first pass at this comparison misquoted the routine sweep's own in-chain figure (4/60,
   `3b52608`) for the *offline anchor's* figure; corrected here before it could propagate.

**⇒ The 10.875% pooled rate is a genuine, reproducible measurement of this offline instrument's
own chronic behaviour, not an artifact of scale.**

### 3.2 Why this matters, stated as an assertion (HK-021(t))

ROW 0b's own anchor band ([2,10] events in 60 slots = 3.3%–16.7%) is wide enough that 6/60 = 10%
passed comfortably — but a 10% *point estimate* inside a band that wide is a weak validation of
absolute-rate transfer, and 6/60 is already ~4.5× the historical *pooled* rate (2.22%) even before
this run's N=4,000 confirmation tightened the estimate. The mechanistic signature is intact at
scale (§4 below) — this is very likely the *same phenomenon* the in-chain sweeps see, measured with
far more precision — but the offline instrument's absolute *frequency* of triggering it does not
match production. The spec itself names the live hypothesis for a gap like this: *"the in-chain
audio passes through Voicemeeter and capture gain, and the offline path does not"* (§4 ROW 0c) —
ROW 0c's own ±10 dB level-shift test did not detect *level* sensitivity, but a level shift is only
one of several ways a real hardware capture path could differ from a synthetic
`np.random.default_rng` draw (spectral colouring, ADC quantisation/dither, downsampling filter
response). **This report does not resolve which explains the gap — that is a new question, not
this arm's to answer — but flags it prominently rather than letting a ROW 1 non-fire read as "all
clear."**

## 4. M2/M4 — the false-accept population's own signature

454 false accepts across 4,000 slots (matches M1 exactly, since S5 is signal-free — every decode
is by definition a false accept).

- **Reported SNR: 100% (454/454) at ≤ −25 dB** — histogram: [−28,−27) 27 · [−27,−26) 233 ·
  [−26,−25) 182 · [−25,−24) 12. This is the *exact* signature the spec's §0.1 table documented
  from the ratified-gate era (12/12 historical S5 false positives ≤ −25 dB, disjoint from the
  lowest genuine decode at −17/−18 dB) — confirmed again here at 38× the historical N.
- **Excess (`signal_db − local_noise_db`): min −1.944, p01 −1.595, median −0.142, max +1.622 dB.**
  Consistent with the mechanistic account: a reported −26 dB decode is `signal_db ≈
  local_noise_db` — essentially zero excess over the decoder's own noise estimate, a CRC-14 escape
  from noise, not a real signal.

## 5. M3 — the genuine-decode complement (Amendment 1 A1.5 applied)

2,300 decode rows total on the S1 population; joined against the render's own `truth.csv` on
`(part, trial, seed)` (0 unmatched keys):

- **2,300 truth-matching (genuine)** — every one of the 2,300 slots produced exactly one
  truth-matching decode (100% recall at this SNR ladder, consistent with ROW 0d's own 250/250
  reading and R&R-005's documented ≥95%-decode-rate range).
- **756 spurious, riding alongside the real signal** — excluded from M3 per Amendment 1 A1.5 (the
  load-bearing correction: these sit at the low end of the excess distribution and would poison
  ROW 2's condition (a) if not separated out).
- **Genuine excess: min 14.987, p01 15.146, median 29.301, max 42.627 dB.**

## 6. ROW 2 (revised) / ROW 3 (revised) — Amendment 1

**ROW 2 (revised) FIRES: True.**

| Condition | Value | Threshold | Holds? |
|---|---|---|---|
| (a) zero M3 genuine decodes at `excess ≤ T` | 0 / 2,300 | = 0 | ✅ |
| (b) `p1(M3) − T ≥ 6.0 dB` | 15.146 − 9.146 = 6.000 dB | ≥ 6.0 dB | ✅ |
| (c) ≥10% of M2 false accepts at `excess ≤ T` | 454 / 454 = **100.00%** | ≥ 10% | ✅ |

**Reported per spec: `T = 9.146 dB`, removal fraction **100.00%**, margin exactly 6.000 dB** (by
construction — `T` was chosen as the tightest value condition (b) allows, so the margin is exactly
the pre-registered minimum; a smaller, more conservative `T` was not needed since even at this
value every false accept in the sample is caught).

🔴 **The actual separation is far larger than the 6 dB margin used to pick `T`.** The maximum
false-accept excess observed (+1.622 dB) and the minimum genuine excess observed (+14.987 dB) are
**13.4 dB apart** — any threshold in that entire gap satisfies (a)–(c) with 100% removal at zero
cost; `T=9.146` was simply the conservative, pre-registered choice, not the tightest possible one.

**Power, at n=2,300 genuine decodes (HK-021(v)):** readout quantum on condition (a) = 1/2,300 =
0.0435%; a clean zero bounds the true loss rate at **95% UB ≈ 0.130%** (rule of three). **Must be
quoted this way — never as "costs nothing."**

**ROW 3 (revised) does not fire.**

🔴 **SIZING ONLY, never a ship decision** (spec A1.2). Any actual emission-side filter is a `src/`
change — HK-011 in full: **QA authors a dev-task and stops; no filter is proposed or built by this
report.**

## 7. Standing bars this arm does not lift (spec §6, unaffected by these results)

- The S7 P2 3-stack limit, Station F/`F-NBR-A`/`NBR-A`, and the S7 gap band — untouched.
- Efficacy of any resulting filter against **real off-air** false accepts remains unmeasurable
  here — this arm measures a synthetic AWGN population only, and per §3.2 above that population's
  own absolute rate does not (yet) transfer cleanly to production.
- The candidate-budget family (`s_k_min_score_pass2`, `K_MAX_CANDIDATES*`, pass config) remains
  closed as a lever — nothing here proposes touching it.

## 8. NFR-021

`m1m4_s5_decodes.csv` and `m3_s1_decodes.csv` — 806 distinct callsign-shaped, non-Q-prefix tokens
(361 + 455 occurrences) redacted to `<RDCTMnn>` placeholders before this report was written, using
the project's own scanner (`nfr021_pre_merge_scan.py`, imported not reimplemented). Guarded first:
0 of 806 tokens appear inside the single injected truth message text (`CQ Q1ABC FN42`, the only
message S1's ladder ever injects) — all are decoder-hallucinated noise, same root cause as ROW 0's
own redaction pass. Byte-level rewrite, BOM preserved, CRLF counts identical before/after both
files. Re-scan: 0/0. Map: `results/REDACTION-MAP-M1-M4.md` (placeholders use an `M` infix,
`<RDCTMnn>`, distinct from ROW 0's own `<RDCTnn>` map so the two passes' tokens are never
confused).

## 9. Recommendations

1. **To the Architect:** open the §3.2 offline-vs-in-chain rate gap as its own question. Candidate
   next step (not QA's to decide): a short in-chain diagnostic capture of real S5 AWGN slots with
   `GetLastSnrTerms` already wired (no new export needed), to check whether the *reported-SNR
   histogram signature* (§4) reproduces on hardware-captured noise at anything like this offline
   frequency, or whether the histogram shape holds but the frequency differs — that would localise
   the gap to "capture path changes the *rate*" vs "capture path changes the *audio*" respectively.
2. **To the PO, via a dev-task QA will author separately (HK-011):** ROW 2's finding is a
   sizeable, cheap, well-separated candidate emission-side floor. Given §3.2's caveat, recommend
   scoping any actual filter's acceptance criteria to be measured **in-chain**, not assumed from
   this offline removal-fraction number directly.
3. Do not cite this report's 10.875%/[9.93%,11.88%] figures as an in-chain rate. They are this
   **offline instrument's own** chronic rate, reproducible and precisely measured, but — per §3 —
   not yet shown to equal what hardware sweeps deliver.
