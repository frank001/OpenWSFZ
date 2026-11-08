# 2026-10-30 LATE-SUB L1′ (HK-016 artefact folder)

- `report.md`: the report (validity rows, verdict table, ON arm, refset leg beside L1, timing, predictions, limitations).
- `l1p_result_off.json`, `l1p_result_on.json`, `l1p_result_refoff.json`: every figure the report quotes (counts, rates, CIs; no message text). `l1p_result_reg40.json` is a code smoke test on already-read refset data and is not in this folder.
- `l1p_check_pilot.json`, `l1p_check_off.json`, `l1p_check_on.json`, `l1p_check_refoff.json`, `l1p_check_v7.json`, `l1p_check_v8.json`: the validity rows.
- Spec: `arch/late-sub` `8152d4ce` + Amendment 1 `e3fd391e`. QA review `qa/rr-study/2026-10-30-0710-qa-to-architect-late-sub-l1p-k-review.md`; freeze record `qa/rr-study/2026-10-30-0717-qa-late-sub-l1p-freeze-record.md`.
- Code: `qa/rr-study/gap-residual-run/` (`l1p_arm.sh`, `l1p_check.py`, `l1p_analyse.py`, `l1p_chain.sh`) and Replay81 `LateSub.cs` (`--late-sub-mode l1p`), code commit `b7c17464`.
- Per-message working files stay in `D:\Projects\claude\_qa-scratch\late-sub\` and are deleted at job close (HK-037).
