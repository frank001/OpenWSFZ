# 2026-10-29 GAP-RESIDUAL (HK-016 artefact folder)

- `report.md` / `report.html`: the report (ROW 0 first, then D1-R to D8, then the routing rows as measured).
- `result_main.json`: every figure the report quotes (counts, rates, CIs; no message text). `row0_off.json`, `pilot_0d.json`, `pilot_0e.json`, `recheck_summary.txt`, `cuts.json` (the REF-SNR tercile cut points, frozen before forcing), `chain_status.txt` (pin, readback and row-count record of both arms).
- The pilot's own folder: `../2026-10-29-gap-residual-pilot/`.
- Code: `qa/rr-study/gap-residual-run/` (`gres_arm.sh`, `gres_row0.py`, `gres_pilot.py`, `gres_main.py`) and the Replay81 capture in `qa/rr-study/sub-feas/replay81/` (`StageProbe.cs`, `Program.cs`).
- Spec: `arch/gap-residual` `74a38158` + Amendment 1 `ea7496d1`. QA review: `qa/rr-study/2026-10-29-1627-qa-to-architect-gap-residual-k-review.md`.
- Per-message working files (captured buffers, hash states, native dumps, nc dumps, forced-leg records keyed by cycle and row index) stay in `D:\Projects\claude\_qa-scratch\gap-residual\` and are deleted at job close (HK-037).
