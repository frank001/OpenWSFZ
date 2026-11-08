# 2026-10-29 GAP-RESIDUAL pilot (HK-016 artefact folder)

The Captain's go: "run the pilot first" (2026-10-29). Spec `74a38158` + Amendment 1 section 9 `ea7496d1` (`arch/gap-residual`). Counts and flags only; no message text.
The pilot is ROW 0 on the real arm plus the pilot-cycle parts of 0d and 0e. **No class-N row was forced on R2 or R3** (that is the main run, not started).

- Build: `main` `c2c85c45` (v0.67), R-F4 setting absent (OFF), `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (start and end), Replay81 with the capture in `StageProbe.cs`, assembly `Ft8.FitProbe`.
- Arm: one process, GAP-RELOCATE's 400 cycles in its order (`selection400.json`, sha `42e09239...`), Both audio mode, multi-set ON, Deep, nhard 24. 2026-10-29T16:35:19Z to 16:59:16Z.
- `row0_off.json`: 0a, 0b, 0c(i), 0c(ii), 0f. `recheck_summary.txt`: 0c(iii) per buffer (cycles, mismatching calls). `pilot_0d.json`, `pilot_0e.json`: the pilot rows. `chain_status.txt`: the arm's pin, readback and row-count record.
- Code: `qa/rr-study/gap-residual-run/` (`gres_arm.sh`, `gres_row0.py`, `gres_pilot.py`) and the Replay81 capture in `qa/rr-study/sub-feas/replay81/` (`StageProbe.cs`, `Program.cs`: `--cap-dir`, `--cap-recheck`).
- Working files with message text (native dumps, nc dump, captured buffers, hash states) stay in `D:\Projects\claude\_qa-scratch\gap-residual\` and are deleted at job close (HK-037).
