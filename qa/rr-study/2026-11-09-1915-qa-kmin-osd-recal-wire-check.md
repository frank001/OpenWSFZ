# KMIN-OSD-RECAL: V-WIRE check, result and a finding for the spec (QA, 2026-11-09T19:14Z `date -u`)

Spec `arch/kmin-osd-recal` Amendment 1 (`ca345413`). **Nothing frozen, no arm run.** Harness flags `--kmin` / `--osd-corr` built (`Replay81` commit `7122404e`, defaults = the old constants; the binary against `ef2fc84b`, `libft8.dll` = pin `1ba8dc3d…`). Native check `kr_wire.py` (`7122404e`, corrected in `ce8f02ac`); results `_qa-scratch\kmin-osd-recal\wire_check.json` SHA-256 `656632fa698703cbfdee62e5d592e245313433c875626c626074313bf1c1de30`. Counts only.

## 1. The registered V-WIRE (10 non-arm cycles, ORIGINAL audio): does not pass as written

| row | result |
|---|---|
| V-WIRE-CAND (candidates of the pass whose floor is `kMinScorePass2`, B > A in 10/10) | **0 of 10: FAIL as written**. Both arms: **200 candidates in all ten cycles** (the pass's cap, `K_MAX_CANDIDATES_PASS2` 200); decodes equal (A 203 = B 203) |
| V-WIRE-CTRL (pass 0, fixed floor, A == B) | 10 of 10, 140 = 140 (the cap, `K_MAX_CANDIDATES` 140) |
| V-WIRE-OSD | **UNTESTED** (accepted OSD candidates 0 in both arms in all ten; correlation-gate rejects 0 too) |

**My own error first (ledger Q45, below):** the first run of the check (`7122404e`) read candidate index 0, the pass with the FIXED floor, and reported 1,400 = 1,400. In the shim `kMinScorePass2` is the floor of the SECOND internal pass (index 1; `ft8_shim.c:1815-1840`, "Pass 1 uses a wider candidate net"). The spec's "pass-1 candidate count" is the 0-indexed pass 1, which is the second pass; my predicate read the first. Corrected in `ce8f02ac`, with pass 0 kept as the control. The corrected check still reads 200 = 200: not an index error any more.

## 2. What the data say (a finding, not a harness fault)

- On the **original audio** of these busy 40 m cycles the second pass is **cap-bound** (200 candidates) at 10 and at 5 alike, so the floor changes nothing there: 10 cycles, identical candidates and decodes.
- **On a subtracted (residual) buffer the floor does bind.** A supplementary probe (`kr_resid.py`, committed with this report; descriptive, NOT the registered row) on 10 stored R2 buffers of the `20260925_2010` night (the SUB-COVER set): second-pass candidates **A 59 to 98 per cycle (835 in all) against B 200 per cycle (2,000 in all)** in 10 of 10 cycles, pass 0 equal (866 = 866); decodes A 53 against B 54; accepted OSD candidates A 0 against B 1; correlation-gate rejects 0 and 0.
- So `kMinScorePass2` acts where the residual buffers are decoded (the residual pass, and the third pass and later rounds that call the same native decode), not on the first decode of the original audio. The study can still measure it, but V-WIRE-CAND has to be measured on a residual buffer, and a null NET on the first pass is expected by construction.
- The OSD wire: 1 accepted candidate in 20 decodes of residual buffers is thin. Both knobs move together, so it cannot be attributed to `osdCorrThreshold`.

## 3. What I propose (the Architect decides)

1. **V-WIRE-CAND on residual buffers:** on the 10 stored R2 buffers (or R2 buffers rebuilt for 10 cycles of the arms' night, outside the 400), B > A in 10 of 10 at index 1, pass-0 control equal. On file: 10 of 10 (the supplementary probe above), so the amended row would pass.
2. **V-WIRE-OSD:** extend to up to 60 residual cycles for this wire only; report UNTESTED if still 0 accepted in both arms.
3. Keep the arms as designed. Note for the ruling: a **cap-bound first pass** means NET_B-A comes from the residual side and the later rounds, which is also where R-F4 and L1' act.

QA ledger Q45: the V-WIRE predicate read the wrong pass index (UNCHECKED-SOURCE: I did not read the pass-config table before writing the predicate; `ft8_shim.c:1815-1840`). Caught by the data (1,400 = 1,400 in a pass whose floor is fixed) and by reading the table, before any arm output.
