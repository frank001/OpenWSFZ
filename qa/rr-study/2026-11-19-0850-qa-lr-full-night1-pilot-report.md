# LR-FULL night 1 (`20261118_1954`): PILOT REPORT (QA, 2026-11-19 08:50Z `date -u`). Counts only; no message text, no callsign (NFR-021, HK-037).

Spec `arch/false-decode-instrument` b2d9883a + Amendments 1-5 (Amendment 4 contiguous TEST; Amendment 5 gate, refined to the TEST block's own rate). The pilot is the night's first 284 of 2,835 cycles after the warm-up (10 %), excluded from every acceptance count. **No TEST arm has run. Nothing below is a result.**

## 1. What was run (HK-022)
- **Night:** live recording `20261118_1954_endurance_run`, window 2026-11-18T19:54:18Z to 2026-11-19T07:42:18Z, 2,836 archived WAVs (2,832 on-grid decode timestamps), RESERVED for LR-FULL. Spectrum scan before any rate was read: 0 clipping, 0 silent, 0 hot, hum consistent with the XC control (+1.96 dB), top spur bin 2.9 % of files (< 5 %). HK-036 Section 4 read and quoted on the board: 87.6 % matched of WSJT-X, OWS-only 5.0 %, 23.6 WSJT-X rows per cycle over the whole night.
- **Arms:** `bash qa/lr-full/lr_arms.sh 20261118_1954 pilot` (07:47:56Z to 08:45:45Z), OFF (`--lr-x1 0 --lr-x2 0`) then ON (`--lr-x1 1 --lr-x2 1`), harness `bin_lrfull` over a clean checkout of `80bbd74b` (HK-039 APPROVED `e6062139`), **libft8.dll actual = pinned `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`**, Deep, nhard 24, three1, 8 threads, cohfb/cohms/Both, kmin 5, osd-corr 0.05, ungated 1, late-round 1, cq-ap 1, cohrescand 1, xc-prior 1 shadow 0 xc-defaults 1 (xcte 3.076041980658299 read back). Q79: a 2-cycle dry run of both arms first (07:47:04Z). Read-backs OK in both arms. Selection sha256 43a67ffc553ac1d0, warm-up = the first archive cycle. WSJT-X (the Captain's) stayed open during the arms (light, equal for both).
- **Scorer:** `qa/lr-full/lr_score.py pilot` at the commits on `qa/same-chain` (selftest 89 checks, PIN: V-H reproduces FD-PROXY exactly). The pilot mode computes NO instrument output on any G row.

## 2. Timing (measured; sets the TEST cap)
**OFF 28.5 min for 284 cycles = 6.03 s per cycle; ON 29.3 min = 6.19 s per cycle** (X2 adds about 0.16 s). A 2,000-cycle TEST block: OFF about 3.35 h, ON about 3.44 h, **about 6.8 h for both, under the 8 h cap, so the cap stays at 2,000.** LATE (descriptive): last batch end time OFF p50 6,026 / p99 6,976 / max 7,616 ms, ON 5,899 / 7,252 / 7,919 ms; batch-5 publish OFF 6,093 / 6,985 / 7,442, ON 6,242 / 7,368 / 8,236 ms; X2's own run 210 ms p50, 336 p99, 377 max.

## 3. V-RUN predicates on the pilot arms (informational)
Pins: pass. OFF abandons: 0 cycles. ON abandons beyond OFF's: 0 of 284 (bar 1 %). ON >= OFF on batches 1-4 in every cycle: pass. **20-cycle OFF re-run byte-identical to the pilot OFF arm on those 20 cycles: pass** (`lr_arms.sh ... rerun20`, 08:46Z to 08:49Z). X2: ran in 283 cycles, 1 `no-residual`, **abandoned candidates 0**; X1: a line in 284 of 284.

## 4. V-H on the controls (OFF arm, pilot cycles; the FD-PROXY tree unchanged)
**V-H passes.** s 0.9524 (P 1,247 judgeable confirmed batch 4+5 rows, Q 127); f_RAND 0.0000, f_NFIELD (visible) 0.0274, f_MISS 0.0862. V-SEP s - f_RAND 0.9524 [0.9337, 0.9687] vs 0.70; V-GHOST s - f_MISS 0.8662 [0.8452, 0.8843] vs 0.50; V-BURIAL -0.0029 [-0.0341, 0.0270] vs 0.10 (P 459 isolated, 788 buried). The recomputed WSJT-X matching equals the harness's matched flag (0 mismatches, both arms). N-RAND for this night: 2,955 plain + 45 AP (AP share 2 of 134 unconfirmed batch 4+5 rows = 1.5 %), seeds 20261118 / 20261119, sha256 322f5d5a… / 67d6062f…, text kept in scratch.

## 5. Amendment 5 gate: DOES NOT FIRE
Projected NET(step) CI half-width on the frozen TEST block (2,000 contiguous cycles after the pilot): **X1 0.0944 pp, X2 0.1161 pp**, against 0.125. m_pilot 28.58 WSJT-X rows per cycle, **m_test 21.23** (the TEST block's own rate from the WSJT-X `ALL.TXT`, the refinement you ruled), n_test 2,000; pilot per-cycle counts of newly corroborated WSJT-X rows: X1 k = 79, X2 k = 120 over 284 cycles (V_pilot 0.282 / 0.426). Fires only if BOTH exceed 0.125: it does not. Note X2's is 0.009 below the bar: a noisier TEST block than the projection assumes would move it.

## 6. H-HI floors and n_iso(G) (structure only, pilot cycles)
| step | rows | matched | G (ON-only, unmatched) | judgeable | unjudgeable | isolated | buried | unjudgeable buried | H-HI floor (hybrid) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| X1 | 106 | 94 | 11 | 10 | 1 | **1** | 10 | 1 | 0.0035 |
| X2 | 167 | 139 | 21 | 21 | 0 | **13** | 8 | 0 | 0.0000 |
| X2 F1b-passed | 148 | 125 | 18 | 18 | 0 | 11 | 7 | 0 | 0.0000 |
| X2 admitted-only | 19 | 14 | 3 | 3 | 0 | 2 | 1 | 0 | 0.0000 |
**No floor is anywhere near 0.021** (hybrid floor = unjudgeable buried rows per cycle; the all-unjudgeable floor is the same, 0.0035 for X1). **n_iso(G) in the pilot: X1 1, X2 13 (pooled 14), so about 98 per 2,000 cycles per night by simple scaling (x7.04), about 197 over two nights: V-AGREE-NI (needs 200 pooled) is borderline-to-UNDERPOWERED; a small n_iso(G) does not stop the run (A5), and the pooled row is the instrument row only.** Rows per cycle: X1 0.37, X2 0.59 (of which 0.52 F1b-passed, 0.07 admitted-only); step column: 7,295 untagged, 26 v2 at or below the gate, 106 X1, 151 late primary, 148 X2 F1b-passed, 19 X2 admitted-only.

## 7. What QA will do on your word (nothing is frozen yet)
Freeze record, committed before any TEST arm: the TEST selection (sha256 6638f6acb8f72cb0, 2,000 contiguous cycles after the pilot; **the warm-up is the cycle right before the block**, an addition to Amendment 4 that primes decoder state and is the same in both arms), the night spec (calibration **c_off = -0.17 s**, 79 of 80 pilot controls with a sync hit >= 0.6, asserted by the final run), the N-RAND hashes, the pins, the scorer commit (clean), the seeds, B 2000. Then `lr_arms.sh 20261118_1954 test` (OFF then ON, about 6.8 h), then ONE `lr_score.py final`. **Needed from you before the freeze: (a) your ruling on sizes and floors (none >= 0.021; X2's projected half-width 0.1161 against 0.125 is the figure to look at), (b) whether the TEST warm-up addition is accepted.**

## 8. Deviations and notes
The TEST block's warm-up (above); `dry` and `rerun20` modes added to the arm script; the pilot scorer's `test_selection` field; Q84 (a stamp typed ahead of the clock, blocked by the guard, nothing landed). The Captain's NET bars stand as the spec gives them (0.25 pp); he has not changed them.
