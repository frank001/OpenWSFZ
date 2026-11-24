# KMIN-OSD-RECAL: FREEZE RECORD (2026-11-09T19:18Z `date -u`), written BEFORE any arm output exists

Spec: `arch/kmin-osd-recal` (§0 to §5 `a79f9cf7`; Amendment 1 §6 `ca345413`; Amendment 2 §7 `5fe706ce`). Authority: the Captain, 2026-11-09 (programme candidate #1). Size rule: two replay arms of 400 cycles on the PC, no second night, no sol, no pilot, no third arm. **The arms have NOT started**: they need the PC exclusive and the station daemon stopped, after the Captain's deploy (spec A1.6); QA asks him once, when told the PC is free.

## Frozen inputs and code

| item | value |
|---|---|
| Build under test | tree `_qa-scratch\kmin-osd-recal\tree` at `ef2fc84b06194b616d8523eea0242ac9b3d81760` (`git diff --stat fe1454c1 ef2fc84b -- src/ native/` empty: the decoder is COH-RES-CAND's arm-A build); `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` = pin |
| Harness | Replay81 (`Ft8.FitProbe.exe`, SHA-256 `1cace534…`, `.dll` `5c10161f…`), QA commit `7122404ee975380546098cbef44207a739e5918c` (`--kmin`, `--osd-corr`; defaults = the old constants 10 and 0.10), built with `-p:HasSubfeas -p:HasMaxThreads -p:HasTwoStage -p:HasOsdSignFix -p:HasThirdPass -p:HasCohFb -p:HasCohFb4 -p:HasLateRound -p:HasCohMs -p:HasCohAudio -p:HasInternals -p:HasUngated` against the tree above |
| Arms script | `qa/rr-study/kmin-osd-recal/kr_arms.sh` (QA commit `58b6f321f8a5cb00038082c4da9f065e7f0f7a81`): both arms `--nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both --ungated 1 --late-round 1`; **A: `--kmin 10 --osd-corr 0.10` (code default, D-009); B: `--kmin 5 --osd-corr 0.05` (the station's value, read back from the `frans` config 2026-11-09 19:04Z)** |
| Analysis | `qa/rr-study/kmin-osd-recal/kr_analyse.py` (same commit `58b6f321`), adapted from `crc_analyse.py` and `tn_analyse.py` `d50a98fe`: rows V-NAT, V-SET, V-WIRE, N-BETTER, N-WORSE, U-OK, U-FAIL, the HK-026 flag and the verdict (VOID / REVERT-10 / KEEP-5 / OPEN / NO-DIFF) are the code |
| Night and cycles | `20260930_1930`, the first 400 cycles of L1′'s 800-cycle selection `2575e115…`, as `sel_400.json` SHA-256 `7691e33b6949ffc354781724c90c1aeb9df0e2d5bc76285c92b9a86bc6007f01` (COH-RES-CAND's file); WSJT-X reference `ALL.TXT` of the night |
| Classes | `u3_800/orig800_classes.json` SHA-256 `8046a4be4b806fcd08b90d376ece7c1203f86446a0476cc98167f8f4a2fc38c1`, reused as they are |
| Bootstrap | B = 2000 cycle resamples, seed 20261109, paired indices |
| Bars | NET bar 0 pp (N-BETTER CI_lo > 0, N-WORSE CI_hi < 0); U_bar 0.021 per cycle (U-OK CI_hi <= 0.021, U-FAIL CI_lo > 0.021) |

## V-WIRE, run and recorded before this freeze (nothing here is arm output)

- **V-NAT, V-SET:** V-NAT is evaluated by the analysis (tree head, native diff, DLL pin at start and end). V-SET is read from each arm's `# readback start` and `# readback end` lines, and checked by `kr_arms.sh` at the end of each arm (`kMinScorePass2`, `osdCorrThreshold`, nhard 24, OSD fix 1, Deep, cohfb, cohms, cohaudio Both, `ungated=True`, `lateround=True`, `threadsResolved=8`).
- **V-WIRE-CAND (A2.1): PASS.** Native in-process check on **10 stored residual (R2) buffers** (`kr_resid.py`, `20260925_2010`, the SUB-COVER set; DLL = pin): second-pass candidates (index 1) **B 200 per cycle against A 59 to 98 (835 in all) in 10 of 10 cycles; pass 0 equal in 10 of 10 (866 = 866)**; decodes A 53, B 54. Record `wire_resid.out` SHA-256 `d2fc577c698ae54d0d971d0627e45ef6a4c53c55a6e34e46f332029ad5782f32`. It was run before any freeze or arm, on the stated predicate (the Architect adopted it as the row's result).
- **V-WIRE-OSD (A2.1): PASS, thin.** Accepted OSD candidates B >= A in 10 of 10 cycles and B > A in one (cycle `201245`: A 0, B 1, a single event); correlation-gate rejects 0 and 0 in all ten. **The two knobs move together, so this does not isolate `osdCorrThreshold`.** The stop rule "stop at the first B > A" was met within the first ten, so no further buffers were run.
- **The registered original-audio check (10 non-arm cycles, `kr_wire.py`, `wire_check.json` SHA-256 `656632fa698703cbfdee62e5d592e245313433c875626c626074313bf1c1de30`):** second pass **cap-bound at 200 in both arms in all ten cycles**, decodes equal (203 = 203): `kMinScorePass2` does nothing on the first decode of original audio on this night. The OSD wire there read UNTESTED (0 accepted, both arms). Reported, superseded as the V-WIRE row by Amendment 2.

## 🔴 Disclosures

- **The first V-WIRE predicate was wrong (QA ledger Q45):** `kr_wire.py` (`7122404e`) read candidate index 0, the pass with the FIXED floor (cap 140); the first run gave 1,400 = 1,400 and FAILED by my index. Corrected in `ce8f02ac` (index 1, the pass whose floor is `kMinScorePass2`, `ft8_shim.c:1815-1840`; pass 0 kept as the control). The Architect's "pass-1" wording was the 0-indexed second pass (his E151). No arm output existed.
- **A 3-cycle plumbing dry run, 2026-11-09 19:17Z, outside the selection** (`selection_3n_dry.json`, the L1′ dry cycles): `kr_arms.sh dry`, arms A and B parameter sets, both `rc=0`, V-SET readbacks and the late-round lines present; outputs deleted, status lines kept in `_qa-scratch\kmin-osd-recal\dry_status_record.txt`. No result was read from it. (COH-RES-CAND did the same.)
- **The PC was free** (no daemon, WSJT-X or harness process) during the check and the dry run; the arms themselves still need the Captain's go for the PC.

## Verdict rule and what an OSD "UNTESTED" does (spec §2, A1.3, A1.4, A2.1)

VOID if a V-row fails; **REVERT-10** if N-WORSE or U-FAIL fires; **KEEP-5** if N-BETTER and U-OK fire and the HK-026 flag (B's new-text uncorroborated outputs in `untestable_class`, any) is False; **OPEN** if N-BETTER fires and U is undecided (neither U-OK nor U-FAIL), or U-OK fires with the flag True; **NO-DIFF** otherwise. A REVERT is the Captain's own config edit; nobody POSTs it. The interval width is reported. dU'_ta is B's new-text outputs of any batch absent from A's rows of the cycle (as COH-RES-CAND, all batches in place of batch 4); A's outputs absent from B are reported beside it, descriptive.

## Order from here

1. The deploy of `51069e34` (the Captain's), then the PC is free.
2. `bash kr_arms.sh A` (about 45 to 55 min), `bash kr_arms.sh B` (the same), detached, orphan-checked.
3. `python kr_analyse.py main 8046a4be4b806fcd08b90d376ece7c1203f86446a0476cc98167f8f4a2fc38c1`; a short report; the Architect's ruling.
