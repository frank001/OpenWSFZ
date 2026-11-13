# CS-CEIL result: VOID on V-REL (RL(CTRL-HIT) 0.740 [0.679, 0.794] against the 0.80 bar). The analysis ran once; the numbers are below, not read as a CLOSE / MODEL-STUDY verdict.

**Written:** 2026-11-13 (`date -u` read at the commit, below). **To:** Architect, then the Captain. **Spec:** `arch/cs-model-ceiling` `e3e5feca` (§1–§4, A1, A2). **Code:** `qa/same-chain` `9ebfc166` (run blob `fdc8282c`, analysis `37ebe071`, lib `5155e68b`, unchanged since the freeze record `073027c4`). **Run:** `cc_run.py`, one invocation, 985 rows relocated in 57 s, rule **two-sided**; `cc_analyse.py`, one invocation (the Captain said "go"). No filter applies (no test suite); the build pin is not involved (forced legs use the harness DLL that V-REPRO loads with its SHA assertion: `load_dec` asserts the DLL SHA-256 against the pin and fails closed). Working files: `_qa-scratch\cs-ceil\run\` (`relocated.jsonl`, `cc_result.json`), numbers only.

## 1. The verdict, mechanically

| row | result | reading |
|---|---|---|
| V-REPRO | PASS (1073/1073, freeze record) | stands |
| V-SLOT | PASS, 91.7 / 91.5 / 91.7 / 93.2 % (CS-NR / CS-pure / CTRL-HIT / CTRL-WEAK), two-sided | stands |
| **V-REL** | **RL(CTRL-HIT) = 0.740, CI [0.679, 0.794]; bar 0.80; FAIL** | **VOID** by the registered rule |

`cc_lib.verdict` order: STOP > VOID > CLOSE > MODEL-STUDY > BETWEEN, so **VOID** is the outcome. The CLOSE and MODEL-STUDY quantities below were computed by the same single run and are listed because they are in the output; they carry no verdict.

## 2. What the run measured

| group | rows | no slot | fit-zero | copies | decodable relocated | RL (of copies) |
|---|---:|---:|---:|---:|---:|---:|
| CS-NR | 700 | 58 | 16 | 626 | 469 | **0.749** |
| CS-pure | 531 | 45 | 14 | 472 | 341 | 0.722 |
| CTRL-HIT | 300 | 25 | 17 | 258 | 191 | **0.740** |
| CTRL-WEAK | 73 | 5 | 3 | 65 | 26 | **0.400** [0.286, 0.520] |

Quantities the spec defines (cycle bootstrap B = 2000, seed 20261112; pp of n_ref 12,124), **not verdict-bearing because V-REL failed**:
- RAW_worst = 4.48 pp [4.07, 4.89]; RAW_worst / RL(CTRL-HIT) = 6.05 pp [5.40, 6.80]; the CLOSE bar (CI_hi < 1.0) is far from met.
- NET-CEIL = 1.26 pp [0.77, 1.74]; the MODEL-STUDY bar (CI_lo ≥ 1.0) is not met either (CI_lo 0.77). C+D-only descriptive (A2.4): 1.01 pp (433 rows, 390 copies, 279 decodable).
- F3 holds in every replicate (RAW / RL ≥ NET-CEIL).

## 3. Descriptives (A2.1, A2.2, F2)

- **RL(CS-NR) by band:** A 0.75 (4 copies), B 0.79, C 0.82, D 0.70. **Mixed rows 0.83, pure 0.72.**
- **By neighbour ΔSNR quartile** (cuts 8, 12, 16 dB): 0.73, 0.77, 0.77, 0.72. **By neighbour |Δf| quartile** (cuts 13, 27, 39 Hz): 0.81, 0.72, 0.76, 0.71.
- **By fitted amplitude quartile (F2):** 0.45, 0.72, 0.92, 0.92 (the weakest quartile relocates worst).
- **Share of CS-NR with |Δ| > 500 Hz:** 0.66 (median |Δf| 773 Hz, pilot).
- **A2.2, UPPER BOUND on the residue floor:** the median of (row's own 60 Hz in-window PSD in R3 minus the cycle floor) over CS-NR rows is **+12.2 dB** (5th to 95th percentile −4.0 to +27.2). The row's band holds the row itself, so this overstates the residue.
- **Fit return codes:** rc 0: CS-NR 626, CS-pure 472, CTRL-HIT 258, CTRL-WEAK 65; rc −3 (fit-zero): 16 / 14 / 17 / 3.

## 4. What I see, stated as such (not a ruling)

- **V-REL failed, but not by a wide margin on the point (0.740 vs 0.80) and the interval's top (0.794) just misses.** The instrument does not reproduce a decodable signal after relocation at 0.80: a quarter of CTRL-HIT rows, which decode in place, do not decode relocated. By F2 the loss sits in the weakest fitted-amplitude quartile.
- **CTRL-WEAK relocated at 0.40**, though every one of its 73 rows fails in place (V-REPRO): the method decodes isolated weak rows in a clean slot far more often than the spec's prediction SM-4 (≤ 0.10) allowed. That is either what relocation buys (a clean position) or the model copy's optimism (§1 of the spec); the run cannot separate the two. It makes NET-CEIL conservative (the optimism rate is large).
- **RL(CS-NR) 0.749 is close to RL(CTRL-HIT) 0.740**: relocated CS rows decode about as often as relocated decodable rows. By the arithmetic of the readout, that points to a large ceiling (RAW/RL 6 pp), but the VOID row says the instrument's recall after relocation is below the registered floor, so I do not read it.
- **SM-4 (RL(CTRL-WEAK) ≤ 0.10): MISS** (0.40). SM-1 was scored MISS earlier by the Architect (A2.3). SM-2 (CLOSE) and SM-3 (MODEL-STUDY) are not scored here: the verdict is VOID.

## 5. What is owed

**The Architect rules** on the VOID: options are (a) accept VOID and close the question as "the instrument cannot say" (no model lever follows from this ceiling), (b) amend V-REL's population or bar and re-freeze with a fresh run (a changed frozen item after output exists is a complete redo, as for NHARD-CEIL), (c) something else. I have not re-run or re-sliced anything. The result file and working files stay in `_qa-scratch\cs-ceil\` until job close (HK-037; they hold no message text).
