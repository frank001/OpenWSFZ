# 2026-10-30 LATE-SUB (HK-016 artefact folder)

- `report.md`: the report (validity rows, verdict table, decomposition, ON arm, TRAIN mechanism check, timing, limitations).
- `result_off.json`, `result_on.json`: every figure the report quotes (counts, rates, CIs; no message text).
- `check_off.json`, `check_on.json`: validity rows V0-V5 for the two arms.
- Spec: `arch/gap-residual` `5c33391f` + Amendment 1 `e2f7c5b2`. QA review: `qa/rr-study/2026-10-29-1919-qa-to-architect-late-sub-k-review.md`.
- Code: `qa/rr-study/gap-residual-run/` (`ls_arm.sh`, `ls_check.py`, `ls_chain.sh`, `ls_analyse.py`, `ls_finish.sh`) and Replay81 `LateSub.cs` (commit `664c5e97`).
- Per-message working files stay in `D:\Projects\claude\_qa-scratch\late-sub\` and are deleted at job close (HK-037).
