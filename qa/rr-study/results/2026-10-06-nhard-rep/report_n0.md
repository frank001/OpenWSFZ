# NHARD-REP Amendment 3 (OSD-OFF) — arm N0 at `nhard 0`, paired with the existing N40

**QA report to the Architect.** Run 2026-10-06 19:11:56Z → 19:44:12Z (`date -u`); V7 pairing control 18:36Z → 18:48Z. Spec §14 of `2026-10-06-1430-architect-to-qa-spec-nhard-replication.md` (branch `arch/nhard-replication`), as amended (V7, `12caa402`). The O-SAFE margin 0.10 pp was ratified by the Captain before N0 ran and is FROZEN.

**Scope (verbatim):** *One 40 m night on the station's current capture chain, replayed through one build at two `nhard` settings. A systematic 1-in-10 sample of the night's cycles. Replay is not the live path. WSJT-X's Enable AP is OFF on this station, so the reference is non-AP. Decodes WSJT-X did not confirm are an upper bound on false positives, not a count of them.*

## Verdict: **O-GAIN**, and the effect is small

**NET_0 = +0.074 pp of WSJT-X's decodes, 95 % CI [+0.020, +0.146]** (311 sampled cycles, Σ W = 9,466, block 8, 39 blocks, B = 10 000, seed 20261006), N0 against the N40 on file. `CI_lo` > 0, so the row is O-GAIN.

🔴 **First-paragraph flag (clustering):** the gain is **7 confirmed decodes in 6 cycles** (K = 7, G = 0); the top-5 blocks carry 100 % of the positive sum, the largest |Σ d| in one block is 2. It is statistically positive and practically tiny.

**Citable as:** *"`nhard` 0 (OSD effectively off) vs 40, NET +0.074 pp [+0.020, +0.146] of WSJT-X's decodes, a systematic 1-in-10 sample (311 cycles) of one 40 m night, replay vs replay, Test B match rule, flag ON."*

## What changed between N40 and N0

| | N40 | N0 | 0 − 40 |
|---|---:|---:|---:|
| WSJT-X decodes matched (Σ M) | 6,759 | 6,766 | **+7** |
| matched at one setting only | | | **K = 7** (at 0 only), **G = 0** (at 40 only) |
| decodes WSJT-X did not confirm | 146 | 123 | **−23** |
| not-confirmed per cycle | 0.469 | 0.395 | −0.074 |
| decodes, batch 1 / batch 2 | 5,925 / 980 | 5,908 / 981 | −17 / +1 |

- **Nothing confirmed was lost** (G = 0). By batch, the whole +0.074 pp is in batch 2 (batch 1: 0.000), consistent with false decodes no longer being subtracted.
- Not-confirmed by SNR band (rate, N40 → N0): A 1.45 % → 1.39 %; B 1.59 % → 1.55 %; C 1.60 % → 1.45 %; **D 5.34 % → 3.55 %** (weak signals, where the inverted OSD's chance-valid codewords sit).
- Exchange rate −0.30: fewer unconfirmed decodes came with more confirmed ones, never fewer.
- Residual passes abandoned: 0 in both arms.

## Validity (all PASS)

| row | result |
|---|---|
| **V1′** pin | PASS: `libft8.dll` `2fa6d993…f365` equal at start and end. |
| **V2″** the setting reached the gate | **PASS**: in N0 **both probe vectors were REJECTED** (path −1) at both probe points; in the N40 on file `P_lo` was accepted at both. This is the outcome-independent proof that 0 applied (a blind arm would equal N40, CI [0, 0], and would have read O-SAFE). |
| **V3** | PASS: 0 exits, 0 exception rows, 0 contained exceptions. |
| **V4** | PASS: read-back `nhard` 0, threads 8, subtraction ON at start and end; `selection.json` and `probe_vectors.json` SHAs equal the frozen values. |
| **V5** | PASS: 0 of 311 residual passes abandoned. |
| **V6** | carried from the closed run (N40's A/A, 200/200 identical). |
| **V7** pairing control | **PASS: 0 of 100 cycles differ** (matched set and batch-1/batch-2 decode multiset) between the NEW harness binary at `nhard 40` and the N40 on file (which came from an earlier binary). Pairing with the old N40 is therefore sound. `Replay81.dll` (N0 and V7) SHA-256 `1357013fc869dbe1d2dcd245bf628f0371c8a0d827fd162dff08252cd155971b`, earlier N40 `4a9cf533…`. |
| consistency | PASS (all cycles present, W identical, M = batch 1 + batch 2, matched sets sized right, K − G = Σ d). |

## Build, pins and instrument

- Build `origin/main` `be3cc5ac`, shim 20260058, DLL pinned as above (start and end of N0 and V7). Harness `qa/osd-off` `14fb0612` at run time (`nhard 0` admitted; the probe expectation now follows each vector's calibrated `nhard_true`, 26 / 52). `replay81 --mode two1 --threads 8 --nhard 0`; same 311 cycles (`selection.json` LF SHA `3cf04abb…13872`), flag ON.
- 69 tests passing for this arm family; mutants caught except one equivalent (O-HARM / O-GAIN cannot both hold). No test `--filter` applies. WSJT-X, jt9 and the daemon were closed; ordinary load only.
- 🛑 Limits: one night, a 1-in-10 sample, replay not live; the 7 gained decodes are few and cluster in 6 cycles; the mechanism (fewer false decodes entering the subtraction) is the best-fitting reading, not tested here.

## Consequence (as the spec states it; not licensed here)
O-GAIN gives the Captain evidence to set OSD off as the interim default for #215. The size is small (+0.07 pp confirmed, −0.07 unconfirmed per cycle); the change itself needs a dev-task, a Developer (HK-011) and a merge sign-off (HK-010).

## Predictions, facts for the ledger
OO1 (O-GAIN, 0.40): **hit**. OO2 (O-SAFE and not O-GAIN, 0.50): not the outcome. OO3 (O-HARM, 0.03): no. OO4 (not-confirmed per cycle falls by ≥ 0.10, 0.55): **miss** (−0.074).

## Files
`artefacts/rr_2026-10-06_nhard_rep_n0/` (`run_N0.csv`, `testb_N0.csv`, `matched_N0.csv`, `outcomes_N0.csv`, `abandon_N0.csv`, `probe_N0.csv`, `log_N0.log`, `pins.jsonl`, `preflight.json`, `v7/`). Tracked: this report, `n0_analysis.json`, `v7_pairing_result.json`.
