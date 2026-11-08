# LATE-SUB L1′ THIRD NIGHT: FREEZE ADDENDUM 2 (QA, 2026-10-31T10:26Z `date -u`; the HK-026 re-freeze of the shape classes; committed BEFORE `tn_analyse.py` is re-run)

**Amends:** freeze record `3275f843` and addendum 1 (`2526b5a4`, `2c967b08`) in one respect only: where the frozen shape classes come from. Architect ruling 2026-10-30-1802 §4: if the provisional run puts an output in `untestable_class` (HK-026), the Original arm runs on the other 600 cycles and the classes are re-frozen from all 800.
**Captain's word on sol:** "go. hibernate sol afterwards" (2026-10-30, QA's window) for the Original arm; pull go 2026-10-31.

## What was done (and nothing else)
- Original arm on the selected cycles 201–800 ran on sol: 2026-10-30T23:57:56Z to 2026-10-31T01:28:15Z, `rc=0 ok=1 rows=600 r6_lines=0`, orphan check clean, `libft8.so` pin `488bfa0b…` OK at both ends, selection SHA `2575e115…`, `sel600` SHA `c28661ff…`. No CHAIN HALT. Sol hibernated once afterwards (its own watcher).
- Records pulled by `scp` to `_qa-scratch/late-sub/sol3n/{raw,scratch}/orig600`; `nc_dump.tsv` SHA-256 `c6918c7f…37b6` identical on sol and PC; sizes and file counts identical (1,724,147 / 894,151 bytes, 12 files).
- The first 200 (`scratch/orig`) and the 600 were concatenated in the selection's order into `scratch/orig800/nc_dump.tsv` (SHA `537cc0ea…`) and `raw/orig800/testb.csv` (SHA `0f5f7365…`): 800 distinct cycles, no overlap, every stamp in the selection.
- `cf_uprime.py off` (unchanged, blob assertion `ecc4c5e7` passed) on the 800-cycle inputs, `libft8.dll` from `bin_dev`, WAVs from `artefacts/20260930_1930_endurance_run-gathered`.
- **Control run before it:** the same command on the first 200 cycles alone reproduced the first-pass `u3/orig_classes.json` byte for byte (`b3dbdaf3…f874`).

## The new classes (frozen here)
- File: `_qa-scratch/late-sub/u3_800/orig800_classes.json`, **SHA-256 `8046a4be4b806fcd08b90d376ece7c1203f86446a0476cc98167f8f4a2fc38c1`**. Passed to `tn_analyse.py` as its argument.
- Testable classes (n ≥ 10 and present rate ≥ 0.80): `RR73/73/RRR` 45/50, `grid` 46/50, `grid CQ` 50/50, `report` 47/50. The testable set is the same four as in the first pass.
- Not testable: `other CQ` 13/50 (26 %), `other` 2/6 (n < 10). `other` did not exist in the first-pass table.
- Descriptive only, on the Original arm itself (800 cycles, cycles with WSJT-X decodes): U′ 0.13375 per cycle, tested-absent 0.04625, untestable-class 0.00125 (one output); U′_max 0.30 × U′₀ = 0.040125 ≤ 0.042. No row of the verdict reads these.

## What changes in the analysis code (and nothing else)
- `tn_analyse.py` commit **`d50a98fe`** (`qa/refset`, local): a `TN_CLASSES` environment variable overrides the classes path (default unchanged). The path only; the logic of `2c967b08` is untouched, and `argv[1]` still pins the SHA (the script asserts it).
- Unchanged: the bars 0.5 / 0.021 / 0.5, V-3N-X, V-3N-REF, R-ALL, R-CLEAN, the verdict rule of Amendment 2, bootstrap B 2000 seed 20261030, the selection, the pins.
- **Disclosed:** the Original arm's per-arm abandon counts in the report (`coh.csv`, `abandon.csv`, `third.csv`, `log.log` under `raw/orig`) still come from the first 200 cycles. They are reported and do not enter X; the nc_dumps and `testb.csv` are what the classes use. The 600 cycles' own counts are on disk in `raw/orig600` and can be read beside them if wanted.
- **No ON-arm analysis has been re-run since this freeze;** the provisional U rows (first-pass classes) are on file in `third_night_result.json` and will be reported beside the final ones.

## What happens next
1. Command: `TN_CLASSES=D:/Projects/claude/_qa-scratch/late-sub/u3_800/orig800_classes.json python qa/rr-study/gap-residual-run/tn_analyse.py 8046a4be4b806fcd08b90d376ece7c1203f86446a0476cc98167f8f4a2fc38c1`.
2. The report gives R-ALL and R-CLEAN with the FINAL U rows beside the provisional ones, and says where the one earlier `untestable_class` output lands. If it is still `untestable_class`, QA goes back to the Architect and does not decide it.
3. The Architect rules (ACCEPT / FAIL / OPEN, BL-1..5); merge and default-ON are the Captain's.
