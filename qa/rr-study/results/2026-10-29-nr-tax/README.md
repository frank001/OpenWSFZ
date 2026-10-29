# 2026-10-29 NR-TAX (HK-016 artefact folder)

- `report.md` / `report.html`: the report (validity rows, T1 to T5, sensitivity, blind spots).
- `result_nrtax.json`: every figure the report quotes (counts, shares, CIs; no message text).
- Spec: `arch/gap-residual` `4179a1e3` + Amendment 1 `001bf76e`. QA review: `qa/rr-study/2026-10-29-1758-qa-to-architect-nr-tax-k-review.md`.
- Code: `qa/rr-study/gap-residual-run/` (`nrtax_defs.py` frozen in commit `cebd2acf` before any category was computed, `nrtax_force.py`, `nrtax_analyse.py`).
- Inputs: GAP-RESIDUAL (`../2026-10-29-gap-residual/`) and GAP-RELOCATE; the forced legs for the `W` tag ran on the stored buffers (not a replay).
- Per-message working files (forced-leg records keyed by cycle and row index, decode dumps, captured buffers) stay in `D:\Projects\claude\_qa-scratch\gap-residual\` and are deleted at job close (HK-037).
