# QA: U′_max FROZEN for COH-FALLBACK step 4 (before any ON decode)

**Stamped:** 2026-10-21T19:47:56Z by `date -u`. **Decision:** the Captain, in QA's window, 2026-10-21 ~19:47Z: *"keep the 30% rule."* (He had the U′ note `58fc8a35` with both options and their consequences.)

| frozen value | |
|---|---|
| **U′_max** | **0.0559375** per cycle (= 0.30 × U′0, U′0 = 0.18645833…, the OFF arm of `20260922_2056`, 960 cycles with WSJT-X ws > 0) |
| rows (A14.3) | **U′-OK** `CI_hi(ΔU′)` ≤ 0.0559375; **U′-FAIL** `CI_lo(ΔU′)` > 0.0559375; **U′-OPEN** otherwise |
| the A15.3 line | "U′_max ≤ 0.042": **NO**, accepted by the Captain with the consequence stated in the note: a fallback twice as noisy as 10-09's reads U′-OPEN (CI upper bound ≈ 0.060); at this bar U′-OK needs ΔU′ ≤ 0.038 and U′-FAIL ΔU′ ≥ 0.082 (solved at 960 cycles) |
| A2.4(a) | U′_max ≥ 2 × projected half-width (0.0559 ≥ 0.0423): the trigger does not fire |
| thresholds | n ≥ 10 and present rate ≥ 80 % (the §16 default), T = 0.276, sample 50 per class, seed 20261007 |
| class list | `results/2026-10-21-coh-fallback-step4-off/uprime_off_classes.json`, SHA-256 `da559b55b2dafd6f2c27061d11a1557866c3a7a0dd1b92309184f4edb7839a23`; testable: RR73/73/RRR, grid, grid CQ, report; untestable: other CQ, other; applies unchanged to the ON and ON-repeat arms, with the same calibration offset (−0.18 s) |
| script | `cf_uprime.py` (committed `93fa9d2b`, instrument blob `66dd1e94` = `cf_fbid.py` @ `ecc4c5e7`) |

Nothing above changes after this note. The bar is never moved after ΔU′ is seen. No ON decode had run when this was written; the next step is the ON arm and the ON-repeat, on the Captain's go.
