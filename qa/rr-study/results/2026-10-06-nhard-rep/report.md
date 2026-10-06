# NHARD-REP — does an OSD `nhard` cap of 60 recover WSJT-X-confirmed decodes that 40 loses? (priority #1, item B)

**QA report to the Architect.** Run 2026-10-06 15:29:42Z → 17:02:43Z (`date -u`). Spec `2026-10-06-1430-architect-to-qa-spec-nhard-replication.md` (branch `arch/nhard-replication`) with Amendment 1 (sample) and Amendment 2 (V2 retired, V2′). `BAR_N` = 0.5 pp, ratified by the Captain before any datum, FROZEN.

**Scope (verbatim, as the spec requires, with Amendment 1's added sentence):** *One 40 m night on the station's current capture chain, replayed through one build at two `nhard` caps. A systematic 1-in-10 sample of the night's cycles. Replay is not the live path. WSJT-X's Enable AP is OFF on this station, so the reference is non-AP. Decodes WSJT-X did not confirm are an upper bound on false positives, not a count of them.*

## Verdict: **N-CLOSED** — and the point estimate is negative

**NET (60 vs 40) = −0.58 pp of WSJT-X's decodes, 95 % CI [−0.79, −0.41]** (311 sampled cycles, Σ W = 9,466 WSJT-X decodes, block bootstrap block = 8 sampled cycles, 39 blocks, B = 10 000, seed 20261006). `CI_hi` = −0.41 < `BAR_N` = 0.5, so the row is N-CLOSED. Blocks of 4 and 16 (reported, not used): [−0.79, −0.40] and [−0.75, −0.43].

**Citable as:** *"`nhard` 60 vs 40, NET −0.58 pp [−0.79, −0.41] of WSJT-X's decodes, a systematic 1-in-10 sample (311 cycles) of one 40 m night, replay vs replay, Test B match rule, flag ON."* Not as *"`nhard` has no effect"*: the not-confirmed side moved a great deal (below).

🔴 **First-paragraph flags (spec §4 and Amendment 2 item 5): none.** Σ`d` is negative, so the top-5-block share of a positive sum is undefined and cannot exceed ½. There are **0** unexplained multiset differences between N40 and AA (0 differing cycles of 200).

## What happened, in numbers

| | N40 | N60 | 60 − 40 |
|---|---:|---:|---:|
| WSJT-X decodes matched (Σ M) | 6,759 | 6,704 | **−55** |
| matched at one cap and not the other | | | **K = 2** (60 only), **G = 57** (40 only) |
| decodes WSJT-X did not confirm, total | 146 | 353 | +207 |
| not-confirmed per cycle | 0.469 | 1.135 | +0.666 |

- **60 gained 2 confirmed decodes and lost 57.** `K − G` = −55 = Σ`d`, checked as an instrument-consistency condition. 49 of 311 cycles carry a non-zero `d`; the largest |Σ`d`| in one 8-cycle block is 8; the autocorrelation of `d` at lags 1, 2 and 8 is +0.07, −0.08, −0.04 (no structure).
- **Where:** by batch, NET is **−0.05 pp in batch 1 and −0.53 pp in batch 2**. About nine tenths of the loss is in the residual pass.
- **Exchange rate:** (extra confirmed)/(extra not-confirmed) = **−0.27**. The extra not-confirmed decodes bought no confirmed ones; they came with fewer.
- **Cost side, by Test B SNR band of the OpenWSFZ decode (not-confirmed rate, Wilson 95 %):**

| band | cap 40 | cap 60 |
|---|---|---|
| A (≥ 0 dB) | 1.5 % [1.0, 2.1] (25 of 1,723) | 1.6 % [1.1, 2.3] (27 of 1,716) |
| B (−10…−1) | 1.6 % [1.2, 2.1] (45 of 2,836) | 2.1 % [1.6, 2.6] (58 of 2,825) |
| C (−15…−11) | 1.6 % [1.1, 2.4] (21 of 1,316) | **5.3 % [4.2, 6.6]** (71 of 1,350) |
| D (≤ −16) | 5.3 % [4.1, 6.9] (55 of 1,030) | **16.9 % [14.9, 19.2]** (197 of 1,166) |

- **Replay fidelity (N40 against the live OpenWSFZ `ALL.TXT`, same shim at `nhard` 40):** 6,905 replayed decodes against 6,902 live over the 311 cycles; the per-cycle count is equal in 293 of 311 cycles. The replay reproduces the live count.

**Reading (with its limits stated).** On this night, build and sample, the cap of 40 is better than 60 on **both** axes: it keeps 55 more WSJT-X-confirmed decodes and carries 207 fewer unconfirmed ones. This agrees in direction with the closed legs (`NT`, `CC`, `E3`) and goes further: they found 60 buying almost nothing, this finds it **costing** confirmed decodes. 🛑 **The mechanism is not established.** The loss sits in batch 2 and the unconfirmed rate roughly triples at weak SNR, which is *consistent with* extra accepted first-pass candidates changing what is subtracted (the spec's §0 hypothesis, NR6), but this arm cannot separate that from other explanations and does not test it. N-CLOSED reads "not a gap lever on this build and band", and here the sign is the opposite of a lever.

## Validity rows (any FAIL would have withheld the verdict: none did)

| row | result |
|---|---|
| **V1** DLL pin | PASS. `libft8.dll` SHA-256 `2fa6d993…f365` (shim 20260058) equal to the recorded value at the start and end of **all three** arms (6 of 6). |
| **V2′** native gate probe (replaces V2) | **PASS** at both probe points in every arm (12 probe rows, 0 problems): P_lo (nhard_true 26) accepted in N40, N60 and AA; **P_hi (nhard_true 52) rejected in N40 and AA, accepted in N60**. This is the same process-global `s_osd_nhard_max` the corpus decodes used. |
| **V3** | PASS. 0 non-zero exits, 0 exception rows, 0 restarts, 0 contained exceptions, every arm. |
| **V4** | PASS. Read-back `subtractionEnabled` True, threads 8, `nhard` 40 / 60 / 40, at start and end of every arm; `selection.json` SHA and `probe_vectors.json` SHA equal to the frozen values. |
| **V5** | PASS. Residual passes abandoned: N40 0 of 311, N60 1 of 311 (0.3 %); ≤ 5 %. |
| **V6** (A/A) | PASS, and as strongly as possible: **AA reproduced N40 exactly in all 200 cycles** (0 differing cycles, `NET_AA` = 0.000 pp, CI [0, 0] inside (−0.25, +0.25)). The flag-ON path is bit-for-bit repeatable on this audio at 8 threads. |
| consistency | PASS: all 311 cycles present in both arms; W identical in both arms; M = batch 1 + batch 2 matched; matched-index sets present with size = M; K − G = Σ`d`. |

### The retired V2 (descriptive, Amendment 2)
*"0 decodes at either cap on 200 white-noise cycles at RMS 0.20 on this build"* (run 15:13–15:15Z, 43–68 ms per cycle, read-back `nhard` 40 / 60). The noise-based V2 FAILED validly and was retired by the Architect; V2′ replaced it. E1 had measured 10.3 % vs 0.35 % of slots at shim 20260050.

## Method notes the Architect asked to have in this report

- **V2′ vector construction (QA's finding; the Architect confirms his own suggestion was wrong).** `osd_decode` (`decode.c:507`) eliminates the parity-check matrix in reliability order, so the **83 most reliable columns become pivots, whose values are recomputed from the free bits**; the 91 least reliable columns are the free bits, taken from hard decisions (flips searched only among the 32 least reliable). Sign errors on **low-|LLR|** bits therefore never reach the gate as `nhard`: the first construction was rejected by the pinned DLL. The working vectors put the sign errors on the **83 high-|LLR| parity pivots** (flipped ones held just above the information bits so the second gate feature, corr/norm ≥ 0.10, still passes) and keep the 91 information bits low-|LLR| and correct. The gate's sign convention is `llr > 0 ⇒ bit 0`; BP reads the opposite sense, sees the complement, and never converges, so the probe always reaches the OSD gate. Calibrated by ctypes on the pinned DLL: accept threshold by full scan exactly 52 (P_hi) and 26 (P_lo); at N ∈ {30, 40, 50, 60, 100} P_hi accepted iff N ≥ 52, P_lo accepted for all; payload equal. Committed `c896bb92` before any corpus decode (`probe_vectors.json` LF SHA `bc914e99…b8`).
- **Citations (spec §4):** at `be3cc5ac`, `MapNative` is `Ft8Decoder.cs:563` and `IsPlausibleMessage` `:585` (the spec's `:528` / `:534` were stale).
- **V6's gated "per-cycle difference"** was read as `d_i = M_AA − M40` (accepted by the Architect); the union-multiset difference was reported, not gated: 0 differing cycles.
- **K and G** use numeric indices into each cycle's WSJT-X lines (no text, no text-derived hash; HK-037).
- **Probe stop rule:** the first probe point of each arm, after `SetDecodeParams` and the warm-up and before any cycle, passed in all three arms; a doctored vector file made the harness exit 5 with 0 cycles decoded (smoke test, noise files, 15:2xZ).

## Pins, build and instrument (HK-022: a report with neither is not a result)

- **Build:** clean checkout of `origin/main` `be3cc5ac4f4c6187e1e16946a966246b8ce3b028` (VERSION 0.56), shim **20260058**; `libft8.dll` actual = pinned = `2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365` (start and end of every arm, `pins.jsonl`). `Replay81.dll` SHA-256 `4a9cf5332812cb367e55347664c6ead309eeb81511530f5a68156f4ba02a79a8`.
- **Harness:** QA branch `qa/nhard-rep`, commit `6161b77b` at run time (`780b280a` harness, `3f70072f` path fix, `c896bb92` V2′ vectors; local, not pushed). `replay81 --mode two1 --threads 8 --nhard {40|60}`; decoder `DecodeTwoStageAsync`, one call per cycle, fresh process per arm, subtraction ON, `kMinScorePass2` 10, `osdCorrThreshold` 0.10. **No test suite is involved, so there is no `--filter` line**; the harness build was run through `--preflight-only` (all assertions) at 15:12Z and 15:27Z, then armed.
- **Frozen inputs:** `selection.json` LF SHA-256 `3cf04abb6b653bac5df70ce587ad48bd5d3bef7205eee6c040f8e2951cb13872` (3,104 included cycles; sample = positions *i* mod 10 = 0 → 311 cycles; AA = the first 200 of them). WAVs `20261004_1634_endurance_run-gathered/owsfz/wav/`; WSJT-X reference `…/wsjt-x/ALL.TXT` (read only inside the matching function).
- **Tests:** `qa/tests/test_nhard_rep_rows.py` 43 passing, every injected mutant caught (10 of 10 on the first set, 6 of 6 on V2′ and the multiset report).
- **Load during the run:** WSJT-X, jt9 and the daemon were closed (checked at arming). The 30-minute sampler recorded no competing process (it watches `wsjtx|jt9|OpenWSFZ|testhost|MSBuild|dotnet|VBCSCompiler`, **not** Python). QA ran Python preparation work for COH-GAIN (up to 2 worker processes) and its tests during the AA arm (16:38–17:02Z) and briefly earlier. Ordinary load is acceptable (Captain); the effect on this run is bounded by what V5 and V6 measure: AA matched N40 exactly and 1 residual pass in 311 was abandoned at 60.
- **Not done / limits:** one 40 m night; a 1-in-10 sample (the Captain may add the `i mod 10 == 5` positions, 310 more cycles, under the same rows, but N-CLOSED does not call for it); replay, not the live path; the mechanism of the batch-2 loss is not tested; genuine decodes WSJT-X also missed cannot be seen (HK-026).

## Architect predictions, facts for the ledger (scoring is the Architect's)

| # | prediction | outcome |
|---|---|---|
| NR1 | verdict N-CLOSED (0.80) | **N-CLOSED**: hit |
| NR2 | NET in [−0.05, +0.15] pp (0.65) | **−0.58**: outside the interval (the sign is negative with a CI that excludes zero) |
| NR3 | V2 passes (0.85) | the noise V2 failed (0 vs 0); V2′ passed |
| NR4 | V6 passes (0.80) | **PASS** (identical in all 200 cycles) |
| NR5 | not-confirmed per cycle higher at 60 (0.90) | **1.135 vs 0.469**: hit |
| NR6 | if K > G, more than half of K − G in batch 2 (0.55) | the condition is not met (K = 2 < G = 57); for the record, −0.53 of the −0.58 pp is in batch 2 |

## Files

Run folder `artefacts/rr_2026-10-06_nhard_rep/` (copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-06-nhard-rep-run`, files only, noise WAVs not copied): `per_cycle.csv` (the spec §8.4 columns), `run_*`, `testb_*`, `matched_*`, `outcomes_*`, `abandon_*`, `probe_*`, `log_*`, `pins.jsonl`, `preflight.json`, `v2_retired/` (the retired noise arms and their gate record). Tracked: this report, `rows.json`, `selection.json`.
