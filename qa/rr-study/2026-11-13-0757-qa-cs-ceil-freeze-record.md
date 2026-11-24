# CS-CEIL freeze record under Amendment 2: FROZEN, no relocated output exists. Waiting on the Captain's PC window.

**Written:** 2026-11-13, `date -u` read 07:55:22Z (the commit) . **To:** Architect, then the Captain. **Spec:** `arch/cs-model-ceiling` `e3e5feca` (§1–§4, A1, A2). **Branch / code:** `qa/same-chain`, code commit `9ebfc166`.

## 1. What is frozen

| item | frozen as |
|---|---|
| slot rule (A2.1) | blocker rule unchanged; **cycle floor** = median over the cycle's blocker-free slots of the mean in-window PSD; slot qualifies iff within **±1.0 dB** of it (two-sided); nearest in frequency, ties lower. Code `cc_lib.py` (`cycle_floor`, `qualifies`, `choose_slot`), blob `5155e68b` |
| window (F1) | measured dt range over all 12,124 rows: **−2.5 to +2.4 s**. Next period's earliest start = 15 + (−2.5) + 0.6 = 13.1 s; previous period's latest end = 2.4 + 0.6 + 12.64 − 15 = 0.64 s. The window is the spec's [0.5, 13.1] narrowed, never widened: **[0.7, 13.1] s** |
| fallback (pre-registered) | decided mechanically in `cc_prep.py` on the no-copy pilot: two-sided unless any group's V-SLOT < 90 %, then upper-only (+1.0 dB) |
| groups | unchanged (V-CAT 11,960 of 11,960; CS-NR 700, CS-pure 531, CTRL-HIT 300 drawn seed 20261112, CTRL-WEAK 73) |
| run | `cc_run.py` blob `fdc8282c`: fit data-aided from the WSJT-X tones at (dt + 0.6, freq) on the stored R3 (R2 in 18 cycles), `ft8_subfeas_fit_signal` unchanged; copy = real part of the shifted analytic waveform of ŝ; `gr_forced.force_cycle` unchanged at (f + Δ, same dt), δ_p 0.6 s, δ_c 0.7 s; only the PCM loader and the row's frequency are substituted |
| analysis | `cc_analyse.py` blob `37ebe071` (readout, verdict, descriptives, A1.2 counts, A2.2, A2.4 C+D descriptive, F2). Verdict is `cc_lib.verdict`: STOP > VOID > CLOSE (CI_hi(RAW_worst / RL(CTRL-HIT)) < 1.0 pp) > MODEL-STUDY (CI_lo(NET-CEIL) ≥ 1.0 pp) > BETWEEN |
| self-test | `cc_selftest.py` blob `1ace1933`: 9 behaviour tests, **17 of 17 mutations killed** (tolerance, one-sided/two-sided, floor mean/blockers, tie order, blocker width/off, farthest slot, shift sign, RAW without fit-zero / without no-slot, NET without optimism, verdict strictness both ways, VOID skipped, fit-zero as copy). F3 holds on 20 random draws |

**HK-038, where ±1.0 dB comes from:** spec §1's own registered tolerance (A2.1 says so); not fitted to these buffers.

## 2. The no-copy pilot (frozen table `_qa-scratch\cs-ceil\frozen\cc_groups.json`, sha256 prefix `344e3f46edcc791e`)

| group | rows | V-SLOT two-sided | V-SLOT upper-only |
|---|---:|---:|---:|
| CS-NR | 700 | **91.7 %** | 93.7 % |
| CS-pure | 531 | **91.5 %** | 93.8 % |
| CTRL-HIT | 300 | **91.7 %** | 93.7 % |
| CTRL-WEAK | 73 | **93.2 %** | 94.5 % |

**Every group clears 90 % two-sided, so the fallback did not fire: the rule that runs is two-sided.** Near-miss stated: the lowest is 91.5 %, 1.5 points above the bar.
- Slot level minus cycle floor, CS-NR (5, 25, 50, 75, 95th percentile): −0.77, −0.04, +0.25, +0.72, +0.94 dB (inside ±1.0 by construction).
- |Δf| of the copy, CS-NR: 124, 376, 773, 1,247, 1,859 Hz. **The copy usually moves far (median 773 Hz)**; the share above 500 Hz is a descriptive in the result.
- Cycle floor over cycles (0, 25, 50, 75, 100th percentile): −83.7, −72.2, −67.5, −64.0, −44.1 dB.
- CTRL-WEAK has no band A or B (27 C, 46 D), as the spec's A2.4 states.

## 3. Checks that ran, and what they were

- **V-REPRO re-run on the frozen groups: PASS**, forced legs in place agree in 700/700 CS-NR, 300/300 CTRL-HIT, 73/73 CTRL-WEAK, identical to NR-TAX's stored record (28 s). It needs no relocated output.
- **Plumbing smoke (two cycles, 6 rows): the output was NOT read** (only the row count and field names were printed, then the folder was deleted). It proved `cc_run.py` runs end to end. **Analysis plumbing** was exercised on random synthetic flags (not data) and deleted. No relocated decode result has been seen.
- **Not run:** the relocated run itself; no fit or copy result exists.

## 4. What the Captain's window buys

`python qa/cs-ceil/cc_run.py` (about 1,000 rows with a slot; the smoke test took 2 s for 6 rows, so a few minutes), then `cc_analyse.py` **once**. PC load: 8 worker processes; station daemon may stay up but timings are not at issue here (no timing is measured). **Owed by the Captain: go for the run.** Message-free: working files only in `_qa-scratch\cs-ceil\`, numbers only in the result; deleted at job close (HK-037).

## 5. Ledger

One QA error today (found by the self-test, fixed before use): my first versions of two band/tie tests contained assertions that could not fail (`or True` style); rewritten with exact expectations before any mutation was run. Ledger row to follow with the commit of this record.
