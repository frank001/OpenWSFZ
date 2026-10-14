# PEEK-100: OSD fix ON vs OFF on 100 cycles, second pass included (descriptive; not an OSD-FIX result or verdict)

- **From:** QA. **To:** Architect, cc Captain. **Date:** 2026-10-08, run 17:16Z to 17:30Z by `date -u` (815 s wall).
- **Spec:** `qa/rr-study/2026-10-08-1715-architect-to-qa-osd-fix-peek-p100.md` (`arch/osd-fix` `2b346822`). **Go:** the Captain, in QA's window ("run PEEK-100"). Run script committed before the run (`c5ea2489`), rows script before any FIX40 output was read (`75e4f6eb`), local `qa/osd-fix`.
- **Build:** `feat/osd-sign-fix` `3276573b`, shim 20260060, `libft8.dll` SHA-256 `2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb` (start = end = pin). Replay81 `two1`, subtraction ON, threads 8, Test B, `nhard` 40, the first 100 cycles of NHARD-REP SAMPLE (residue 0, in their order). **TEST cycles untouched.**
- **REF** = A-OFF part 2 (`--osd-sign-fix 0`, not re-run). **FIX40** = the same command with `--osd-sign-fix 1`. Commands: `python qa/rr-study/osd-fix/osd_fix_peek_run.py --harness-out D:\Projects\claude\_qa-scratch\osd-fix-harness --new-sha 2029b080…82bb`, then `osd_fix_peek_rows.py --new-dll … --new-sha …`. No test filter involved (scripts). Numbers: `peek100.json`.
- 🛑 **PEEK-100. Not citable as an OSD-FIX result.** `nhard` 40 was calibrated on the inverted OSD; FIX40 is one grid point. 100 cycles, one night, replay.

## Validity

PV1 rc 0 in both runs ✓. PV2 DLL pin at start = end ✓. PV3 read-back `osdSignFixSet=1 osdSignFixRead=1` in FIX40 (2 lines), `=0/=0` in REF ✓. PV4 abandoned cycles 0 in both (bar ≤ 5 %) ✓. PV5 FIX40's batch multisets differ from REF's in some cycles, so the switch was applied ✓.

## Rows (NET = confirmed decodes as pp of WSJT-X's 3,664 decodes on these 100 cycles; 95 % block bootstrap, blocks of 8, B 10,000, seed 20261006)

| row | REF (switch 0) | FIX40 (switch 1) | difference |
|---|---:|---:|---|
| **PK1** confirmed decodes, all batches | 2,621 | 2,622 | **NET +0.027 pp [−0.144, +0.205]**; K 5 gained, G 4 lost |
| **PK2** batch 1 | | | NET **+0.055 pp [0.000, +0.133]** |
| **PK2** batch 2 | | | NET **−0.027 pp [−0.168, +0.112]** |
| **PK3** batch-1 not-confirmed per cycle | 0.46 | 0.54 | +0.08 (46 → 54 decodes in 100 cycles) |
| **PK4** batch-2 confirmed per cycle | 4.65 | 4.64 | −0.01 |
| **PK6** total decode ms per cycle, median / p95 | 8,072 / 10,382 | 8,478 / 11,157 | +406 / +775 ms (one run each; noise not measured) |

**PK5, R6 diagnostics (aggregates; see the limit):** from a separate ctypes pass of `ft8_decode_all` (first decode call only: passes 0 and 1) on the same 100 cycles, switch 0 vs switch 1.

| | switch 0 | switch 1 |
|---|---:|---:|
| OSD gate accepts per cycle (total) | 0.85 (85) | 0.93 (93) |
| accepts in pass 0 / pass 1 | 36 / 49 | 38 / 55 |
| `nhard` of accepts, median / p90 | 39 / 40 | 38 / 40 |
| corr/norm of accepts, median | 0.364 | 0.379 |
| nhard-cap rejects, pass 0 / pass 1 | 252 / 446 | 233 / 407 |
| corr rejects | 0 | 0 |

**Limit of PK5 (spec deviation):** the native diagnostics are thread-local to the decode call, and Replay81 decodes on pool threads, so the product pipeline cannot read them. PK5 therefore covers the first decode call only, **not the residual-subtraction decode**, and it is a second pass over the audio, not the run's own decodes. Because `nhard` is capped at 40 the p90 of 40 is the cap, not a distribution tail.

## Reading (descriptive; 100 cycles cannot call anything confirmed or refuted)

- **The Captain's mechanism, PK3 falling and PK4 rising together, is not seen.** PK3 is slightly higher with the fix (0.54 against 0.46) and PK4 is flat (4.64 against 4.65). Counts are tiny: 8 decodes in 100 cycles on PK3, 1 decode on PK4.
- **NET is indistinguishable from zero** (CI [−0.14, +0.21]), and so are both batches. By the spec's own scale (±0.34 pp expected at 100 cycles) this run could have seen an effect as large as NHARD-REP's batch-2 loss (−0.53 pp). It saw none that size. An effect of the size every corrected-OSD figure on file shows (≤ 0.05 pp) is below what 100 cycles can see.
- The fixed OSD passes the gate slightly more often (0.93 vs 0.85 per cycle) with a slightly lower `nhard` and higher corr/norm among accepts. The extra accepts are not shown to be true or false here (Test B's confirmed/not-confirmed split is PK1/PK3, which moves by +1 and +8).
- Decode time is about 5 % higher with the fix (one run each).

## Blind predictions (Architect, scored on the point estimates)

| # | prediction | outcome |
|---|---|---|
| PK-a | PK1's CI includes 0 | **HIT** |
| PK-b | PK3 lower in FIX40 than REF | **MISS** (0.54 vs 0.46) |
| PK-c | PK2 batch-2 NET point estimate > 0 | **MISS** (−0.027 pp) |

Nothing in TRAIN, TEST, the grid, the `n*` rule or any bar changes because of this. Run folder to be copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-08-osd-fix-peek100`.
