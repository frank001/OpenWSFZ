# 2026-10-28 GAP-RELOCATE (HK-016 artefact folder)

- `report.md`: the report (section order: ROW 0, item 1 A1-A4, item 2 D1-D7, routing rows, DENS).
- `item1.json`, `item2.json`, `deltas.json`: aggregates the report quotes (counts, rates, CIs; no message text).
- `chain_status.txt`, `both_status.txt`, `off_status.txt`: the replay chain's pin, readback and row-count record.
- Code: `qa/rr-study/gap-relocate-run/` (`gr_arms.sh`, `gr_common.py`, `gr_item1.py`, `gr_forced.py`, `gr_item2.py`, `gr_pilot_diag.py`) and the Replay81 extension in `qa/rr-study/sub-feas/replay81/` (`StageProbe.cs`, `Program.cs`, `Replay81.csproj`).
- Per-message working files (impl/stage/nc dumps, forced-leg records keyed by cycle and row index) stay in `D:\Projects\claude\_qa-scratch\gap-relocate\` and are deleted at job close (HK-037). The replay's own CSVs are in the same scratch folder.
- Spec: `arch/gap-relocate` `690e8cb5`, Amendments `825cc235`, `a6ac792f`, section 11 (Amendment 3). QA review: `qa/rr-study/2026-10-28-1325-qa-to-architect-gap-relocate-k-review.md`. Interim result and pilot stop: `qa/rr-study/2026-10-28-1435-qa-to-architect-gap-relocate-item1-result-and-pilot-stop.md`.
