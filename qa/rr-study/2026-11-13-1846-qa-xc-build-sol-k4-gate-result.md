# XC-BUILD, K4 gate on sol: replay is repeatable (A1 = A2 on 100 cycles), but sol exhausts the cycle budget: the late round is abandoned in 86 of 100 cycles, so an ON arm there would be host-bound by construction

**Written:** 2026-11-13, `date -u` read 18:45:22Z. **To:** Architect, Captain. **Spec:** `arch/cross-cycle-prior` Amendment 3 (§10: A2.1 determinism guard, K4). **Host:** sol (Gentoo, AMD FX-8350, 8 cores, glibc 2.43; `threadsResolved=8` read back at start and end). **Build:** `ce5734b6` (the PR base), Replay81 `qa/same-chain` `a5caa63c` built on sol with `-p:HasCohFb4=true` and the full station-stack flag set. **`libft8.so` SHA-256:** `7741867ea64dce9f3ae52740d0e4710a11a6e59b29938db36309cd942e45b984`, built on sol from `ce5734b6`; the same bytes came out of `f82b6432`'s native tree (K3 precondition, shown for both trees). **Selection:** first 100 TRAIN cycles of `20261110_1817` (sha256 prefix `3d95b2d9`), warm-up `261110_184730`. Script: `qa/xc-build/xc_k4_gate.sh` (qa/xc-build). Nothing pushed.

## 1. The first attempt was invalid and was discarded (QA error, for the ledger)

The first K4 run on sol reported "A1 == A2" on 100 cycles. **Every one of its 100 cycles had thrown `InvalidOperationException` (`decodes` = -1) in both arms**, so the comparison compared two runs that decoded nothing. Cause: my sol build of Replay81 lacked `-p:HasCohFb4=true`, which the batch-4 hand-off needs. My gate script counted rows but did not check them (HK-022). **Fixed:** the script now fails an arm on any exception, any negative decode count, a missing `b4_n` column, an empty `nc.tsv`/`outcomes.csv`/`matchedbatch.csv`, and it compares the per-batch counts `b1_n..b5_n` as well as the decode count. The invalid run's folder is kept as `k4_invalid_nocohfb4` on sol (counts only). A 3-cycle dry run passed before the real one.

## 2. The valid gate

| item | A1 | A2 |
|---|---|---|
| start to end (UTC) | 18:03:58 to 18:24:10 | 18:24:10 to 18:44:19 |
| rows; exceptions; negative decode counts | 100; 0; 0 | 100; 0; 0 |
| published rows (`nc.tsv`, `outcomes.csv`) | 2,899 each | 2,899 each |

**Compared A1 against A2, line by line, every line:** `nc.tsv` (the per-cycle published rows: batch, text, frequency, dt, SNR; 2,899 lines) **0 lines differ**; `matched.csv`, `matchedbatch.csv`, `testb.csv`, `outcomes.csv` **0 differ**; the per-cycle `(decodes, b1_n..b5_n)` **0 of 100 differ**. **Verdict: A1 = A2 on 100 cycles. Replay of the pre-change build is repeatable on sol.** (My stated expectation, K4, was that A1 ≠ A2 was the likely branch on this CPU. It was wrong, and the amendment records it as recorded, not scored.) Consequence under A2.1: the third branch is not reached on the prefix, so V-OFF on sol is decidable; the full 500 cycles (B and A1; A2 only if B ≠ A1) is still to be run.

## 3. What sol does to the cycle budget (read before any ON or TR arm is planned there)

| host | build, flags | cycles | mean cycle elapsed | late round (batch 5) outcome |
|---|---|---|---|---|
| **sol**, today | `ce5734b6`, station stack (CQ-AP, v2, L1′, R-F4), 8 threads | 100 | **12,049 ms** (budget 13 s) | **abandoned 86, ran 13, no-new 1** |
| PC, today | `f82b6432`, TR smoke (same stack) | 40 | 5,233 ms | ran 40 |
| PC, 2026-11-10 | `7ca00264` CQ-AP OFF arm (same night's cycles, 500) | 500 | not read | ran 489, no-new 11, **abandoned 0** |

On sol the late round is abandoned in 86 % of cycles; on the PC in none. The XC stage starts only after batch 5 and stops starting templates at the budget less the publish reserve (R8). **The time left for it on sol is, on average, under a second, against 1.5 to 5 s of work (A1.4).** I have not run the stage on sol, so this is a prediction from the figures above, not a measurement: **ABANDON (ON) on sol is predicted to be far above A2.2's 1 % line, which would label NET "host-bound (sol)" and make it unreadable as a statement about the station;** TR on sol would test few templates and may miss V-TR-N (n shadow tests ≥ 3 / FA\*); K1's shadow abandonment would also be high.

## 4. What I recommend (Architect's ruling and the Captain's word needed)

1. **The arms stay on the PC** (V-OFF vs N24, TR, OFF, ON as in §6 of the spec); sol would give no NET that can be read for the station. This is the "arms go to the PC as written" branch of A2.1/A2.2, though reached by a different road than the one the K4 gate was meant to test.
2. **Optional, 20 minutes of sol:** a 40-cycle ON-with-T_E-infinity probe on sol to put a measured ABANDON number in the record (it costs no PC time). I will run it only if asked.
3. The sol work is not wasted: the host's repeatability (A1 = A2) and the `.so` pin pair are on file for any later sol use.
4. Cost of the PC arms as written: V-OFF 45 min, TR 45 to 50 min, OFF and ON 90 min each (the Captain's windows; about 4.5 h).
