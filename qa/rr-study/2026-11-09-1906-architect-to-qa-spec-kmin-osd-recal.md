# `KMIN-OSD-RECAL` spec: is the station's `kMinScorePass2`/`osdCorrThreshold` = 5 / 0.05 better or worse than the code default 10 / 0.10, on today's decoder? Two replay arms, no build

**From:** Architect · **To:** QA · **Date:** 2026-11-09 19:06:33Z (`date -u`) · **Branch:** `arch/kmin-osd-recal`
**Authority:** the Captain, 2026-11-09: "alright, lets add it to the decoding improvement programme ... the next step to look at candidate #1". Candidate #1 of the re-evaluation list (programme page `todo-decode-improvement-prio1-2026-10-05.md`, top). His size rule (2026-11-08): "keep the verification tests small".
**Base:** `origin/main` `ef2fc84b` (`git diff --stat fe1454c1 ef2fc84b -- src/ native/` is empty, so the decoder is COH-RES-CAND's arm-A build). **No `src/` or `native/` change, settings only, PC, station daemon stopped.** This document is docs only.
**Family note:** lowering `kMinScorePass2` admits more candidates. That touches the candidate-budget family closed in June–August (`closed-arms-prohibitions.md`). The Captain asked for this re-test on today's decoder, and **his word covers it.** It is a new measurement of a shipped setting, not a re-read of a closed gate.

🟢 **Size rule.** Two replay arms of 400 cycles on the PC, on a night that already has frozen classes. **No second night, no sol, no pilot, no third arm.** Any added arm or cycle needs his word.

---

## §0. Why, in one paragraph

- Both settings come from **D-009** (comments at `ft8_shim.c:479–480`; code defaults `DecoderConfig.cs:36–37`).
  - `kMinScorePass2` is the pass-1 candidate score floor; the API range is 5–30, so 5 is the floor (`WebApp.cs:560`).
  - `osdCorrThreshold` is the OSD's normalised-correlation gate.
- **D-009 calibrated them on the inverted OSD** (fixed 2026-10-09, #215) **and before subtraction existed.** Our guards already say D-009 is not evidence about a correct OSD.
- The station has run **5 / 0.05** since the Captain set it (unvalidated, on the board). QA read it back from the `frans` config on 2026-11-09 at 19:04Z: `kMinScorePass2` 5, `osdCorrThreshold` 0.05, `osdNhardMax` 24.
- **The question:** on today's decoder, is 5 / 0.05 better, worse, or indistinguishable from 10 / 0.10, in WSJT-X-corroborated decodes **and** in unconfirmed (tested-absent) output?
- **The two knobs move together**, as the station has them. The test answers "his pair against the default pair", not which knob does what. Separating them would need two more arms, so it is out of scope.

## §1. The arms

**Night and cycles:** exactly COH-RES-CAND's.
- `20260930_1930`, the **first 400 cycles of L1′'s 800-cycle selection**, in that order, one process from the first of them.
- U′ classes frozen from sol's Original arm (SHA `8046a4be…`), reused as they are.
- **On file:** this reuse held on the PC (COH-RES-CAND V1-3N, 399/400; the one cycle is where sol abandoned the fallback, and it reached no `untestable_class`).

**Configuration (both arms):** today's decoder **as it will run after the default-ON deploy**:
- Deep, `nhard` 24, OSD sign fix ON, multi-set ON, `Both`;
- **R-F4 ON and L1′ ON**: set explicitly, as the deploy will (build `51069e34`, approved);
- the same thread count.

Calibrating the pair on the configuration it will actually run beside is the point. Both features exist on `main` behind their flags, so no build is needed.

| arm | `kMinScorePass2` | `osdCorrThreshold` | role |
|---|---:|---:|---|
| **A** | 10 | 0.10 | the code default (D-009) |
| **B** | 5 | 0.05 | the station's live value |

🔴 **Where the values come from (QA's point, HK-020/HK-035).** The native layer holds these as process globals with its **own** defaults: `s_k_min_score_pass2` 10, `s_osd_corr_threshold` 0.10, and **`s_osd_nhard_max` 60** (`ft8_shim.c:479–481`). The daemon overwrites them from config before the first cycle (`Program.cs:838–842`). A harness that skips that call would run `nhard` **60**, not 24.
- Each arm's harness must set all three through `ft8_set_decode_params` (`:493`) and **log the effective values it set**.
- Row V-SET reads them back.

## §2. Rows

**Freeze:** before the first arm's output exists, one commit records the build commit, the DLL SHA-256, the selection, the classes SHA, the analysis code (L1′'s `tn_analyse.py`, `d50a98fe`, as COH-RES-CAND used it), and each arm's parameter set.

| row | predicate (mechanical) | where its bar comes from |
|---|---|---|
| **V-NAT** | `git diff --stat ef2fc84b -- native/` is empty, and the DLL SHA-256 equals the pin `1ba8dc3d…` | the pin, used by every arm since 2026-11-08 |
| **V-SET** | each arm's log shows exactly its table values for `kMinScorePass2`, `osdCorrThreshold`, `osdNhardMax` = 24, R-F4 = true, L1′ = true, `Both`, Deep, multi-set ON; read back once per process | mechanical; a mismatch voids the arm, which is re-run once |
| **V-WIRE** | arm B's mean pass-1 candidate count per cycle (from the decoder's per-cycle log line, or a harness counter if the line has none; QA names which in the (k) review) is **greater** than arm A's | lowering the floor must admit more candidates, or the setting is not wired. A plumbing floor, not evidence of gain |
| **N-BETTER** | `CI_lo(NET_B−A)` > **0** pp | 0 is the Captain's NET bar for COH-RES-CAND (2026-11-08, "fine with me"), the latest single-setting arm |
| **N-WORSE** | `CI_hi(NET_B−A)` < **0** pp | symmetric to N-BETTER |
| **U-OK** | `CI_hi(ΔU′_ta, B−A)` ≤ **0.021** per cycle | the ratified U_bar_G (COH-GATE-G 2026-10-28; re-used for LATE-SUB, L1′, COH-RES-CAND) |
| **U-FAIL** | `CI_lo(ΔU′_ta, B−A)` > 0.021 | as U-OK |

NET, ΔU′_ta and the cycle bootstrap (B = 2000, seed **20261109**) are computed exactly as in L1′ / COH-RES-CAND.

**Verdict (on B relative to A):**

| verdict | condition | consequence |
|---|---|---|
| **KEEP-5** | V-rows pass, N-BETTER fires, U-OK fires | the station's 5 / 0.05 is validated. I recommend making it the code default (a small `src/` change; the Captain decides) |
| **REVERT-10** | V-rows pass, and N-WORSE **or** U-FAIL fires | the station should go back to 10 / 0.10. That is the Captain's config edit; nobody POSTs it for him |
| **NO-DIFF** | V-rows pass, otherwise | no measurable difference at 400 cycles. Both values stay defensible; the Captain picks. I would recommend the code default for fewer moving parts |
| **VOID** | a V-row fails after its one re-run | to the Captain |

**Check of the bars against data on file (HK-038):**
- COH-RES-CAND's 400-cycle NET interval on this night was **±0.22 pp** wide (+0.504 [0.286, 0.717]), so N-BETTER and N-WORSE need a true difference of about ≥ 0.25 pp to fire reliably.
- U-FAIL fired there on a lever that added only 19 tested-absent rows in 400 cycles (ΔU′_ta 0.0475), so **the U row can fire at this size**.

**Descriptive (no verdict):**
- the B−A row counts by batch (1–5);
- OSD-sourced rows per arm (if the log tags them);
- per-stage abandons (residual, third pass, fallback, late round) and the latest batch's arrival time, median and p95, per arm. A lower floor costs decode time, and NET already pays for rows lost to it.

## §3. What this does not measure

- **Which knob does it:** the two move together (§0).
- **Values other than the two pairs:** e.g. 7 / 0.075. If NO-DIFF or a split verdict leaves the Captain wanting a curve, that is a new arm, on his word.
- **sol-class timing:** the PC only. The live station is the PC, so this matters less than it did.
- **Other nights or bands:** `20260930_1930` (40 m) only.

## §4. Order and cost

1. QA's (k) review, rows only. QA confirms that the L1′/COH-RES-CAND harness can set the three native parameters per process and log them, and names the V-WIRE source.
2. Freeze.
3. Arm A, then arm B: **about 45–55 min each** (≈ 7 s per cycle at L1′'s PC speed, plus the late round). About 1 h 45 min of PC time in all; PC exclusive, station daemon stopped.
4. A short report: the rows table and the descriptive lines.
5. My ruling. I update the programme page's top in the same edit (the Captain's update rule, 2026-11-09).

Working files: `_qa-scratch\kmin-osd-recal\` (HK-037). Aggregates only in the report.

## §5. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| KO-1 | V-NAT, V-SET and V-WIRE pass on the first run | 0.70 | C |
| KO-2 | NET_B−A point estimate > 0 | 0.55 | H |
| KO-3 | U-FAIL fires | 0.35 | H |
| KO-4 | verdict KEEP-5 | 0.25 | H |
| KO-5 | verdict REVERT-10 | 0.35 | H |

**Reasoning:**
- A lower floor and a looser OSD gate admit more candidates and more OSD rescues. Some are real, and the corrected OSD makes them more likely real than in D-009's day.
- But subtraction, the third pass and the coherent fallback now reach much of what extra pass-1 candidates would find, so the net gain is plausibly small.
- And the looser gate's cost lands in the unconfirmed-output row, which fired on a smaller change (COH-RES-CAND).
- So the NET point leans slightly positive, while REVERT-10 (U-FAIL) is as likely as KEEP-5, or more.

🔴 **Bias check:** HYPOTHESISED calls lean toward "a findable gain"; KEEP-5 is held at 0.25.

## §6. Amendment 1 (2026-11-09 19:10:01Z, `date -u`): QA (k) review adopted in full, before any freeze

QA: **ACCEPT with three amendments.** No bar fires by construction. Effort ≈ 3–3.5 h; machine ≈ 1 h 45 min of arms plus ≈ 10 min for the wiring check. These replace the named parts of §1–§2.

**A1.1 Harness.** Replay81 (`Ft8.FitProbe.exe`) hard-codes `KMinScorePass2 = 10` and `OsdCorrThreshold = 0.10f` (`qa/rr-study/sub-feas/replay81/Program.cs:37–38`, passed at `:117`).
- QA adds `--kmin` and `--osd-corr`, defaulting to those constants so the old arms still reproduce.
- V-SET reads the existing `# readback` line (`:1104`).
- R-F4 and L1′ ON use `--ungated 1 --late-round 1` (`:329–336`), built against `ef2fc84b` with the `crc_arms.sh` build switches.
- The harness commit goes in the freeze. The arm script's OFF checks are inverted for these arms: `ungated=True`, `lateround=True`, and `Late subtraction round:` lines are expected.

**A1.2 V-WIRE replaced (ledger E148, mine).** The per-pass candidate line (`Ft8Decoder.cs:883`) is Debug level and absent from the arms' logs. My row also tested only `kMin`, so it could not show that `osdCorrThreshold` arrived. **New V-WIRE** = (i) V-SET's readbacks **and** (ii) an in-process native check **outside the arms** (DLL = pin, `cf_native.py`):
- 10 cycles: the 3 dry cycles plus 7 warm-up cycles of the selection, none of them arm output.
- Params A, then B, on each cycle:
  - `ft8_get_last_candidate_counts` pass 1: **B > A in 10 of 10** (the `kMin` wire);
  - `ft8_get_last_osd_diag` accepted-OSD count: **B ≥ A in 10 of 10 and B > A in ≥ 1** (the OSD wire). If the OSD count is 0 in all ten, the OSD wire is **reported untested**, not passed.
- QA confirms both calls in the freeze.

**A1.3 The U′ rows' blind spot (HK-026; ledger E149, mine).** `tn_analyse.py` counts as tested-absent only outputs that are not hashed or unencodable **and** whose shape class is in the frozen set. The set was frozen from sol's Original arm (10 / 0.10, R-F4 and L1′ OFF; classes `8046a4be…`).
- A lower floor and a looser OSD gate can push more of B's unconfirmed output into `untestable_class` or hashed. Those outputs leave ΔU′_ta, so **U-OK could pass by blindness**.
- **New rule, as in L1′'s ACCEPT-3N:** `HK026_untestable_class_outputs_need_refreeze` must be **False** for B−A, meaning **no output of B in a class absent from the frozen set**. If it is True, there is **no KEEP-5**; the result comes back to me.
- U-OK and U-FAIL are reported with B's `untestable_class` and hashed counts beside A's.
- **New descriptive row V-REF:** arm A's published decodes per cycle against the frozen Original arm on the same 400 cycles (they will differ: R-F4 and L1′ add rows). The count of differing cycles is reported; no bar.
- The classes' `c_off` and `T_FROZEN` do not depend on the arm (QA), so the reuse otherwise stands.

**A1.4 Verdict table: a fifth cell (HK-025; ledger E150, mine).** "NO-DIFF = otherwise" swallowed the case where N-BETTER fires but the U interval straddles 0.021.

| verdict | condition |
|---|---|
| **KEEP-5** | V-rows pass, N-BETTER, U-OK, **and** A1.3's flag False |
| **REVERT-10** | V-rows pass, and N-WORSE **or** U-FAIL (unchanged; either one dominates) |
| **OPEN** (new) | V-rows pass, N-BETTER fires, and neither U-OK nor U-FAIL; **or** N-BETTER and U-OK with A1.3's flag True. To the Captain with the numbers |
| **NO-DIFF** | V-rows pass, and none of the above |
| **VOID** | a V-row fails after its one re-run |

**A1.5 Data note (QA).** A lower floor may widen the 400-cycle interval beyond COH-RES-CAND's ±0.22 pp. QA reports the width; no bar changes.

**A1.6 Scheduling.** The arms need the PC exclusive with the station daemon stopped, and they cannot share the PC with the default-ON deploy's live session. **The deploy goes first** (the Captain has said "deploy"). The arms run when he frees the PC; QA asks him once, when the arms are ready.

**Predictions:** unchanged. KO-1 now reads "V-NAT, V-SET and V-WIRE (as amended) pass on the first run", with P unchanged at 0.70, revised before any data. The amended row is harder: two wires plus an untested branch.

**QA may build the flags, run the wiring check and freeze with this text.**
