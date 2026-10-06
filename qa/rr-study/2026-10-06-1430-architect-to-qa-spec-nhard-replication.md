# SPEC — `NHARD-REP`: does an OSD `nhard` cap of 60 recover WSJT-X-confirmed decodes that 40 loses, on today's build and real audio? (priority #1, item B)

- **To:** QA (owner; the Captain may assign it to the Engineer instead: one owner, recorded on the board)  **From:** Architect  **Date:** 2026-10-06 14:31Z (`date -u`, HK-017)
- **Branch:** `arch/nhard-replication` (cut from `origin/main` `be3cc5ac`). Docs only: `git diff --stat -- src/ native/` empty.
- **Programme:** priority #1, item B (the Architect's memory note `todo-decode-improvement-prio1-2026-10-05.md`). Source: GitHub #3 comment 2026-10-04 17:15Z.
- ~~**Status:** DRAFT until §9 Q1 (`BAR_N`) is ratified by the Captain.~~ ✅ **`BAR_N` = 0.5 pp RATIFIED by the Captain, 2026-10-06 ~14:34Z (`date -u`), "0.5 pp (Recommended)", before any harness change, noise set or decode exists. FROZEN for this arm.** Status: **PRE-REGISTERED.** QA commits the harness change and the frozen cycle list **before any decode**. Nothing below may change after a decode has run, except by a dated amendment that says why.
- **Needs before arming:** the Captain's go for the CPU window (~~≈ 5 h~~ **≈ 1.6–1.8 h under Amendment 1**), given in the owner's window. Not given by this spec.
- ⛔ **AMENDMENT 2 (2026-10-06 15:18Z): V2 FAILED as designed (0 vs 0 noise decodes); the ruling and the replacement row V2′ are in §13. No corpus arm has run. Read §13 before §5.**
- ⛔ **AMENDMENT 1 (2026-10-06 15:01Z, before any datum) changes the cycle set, the bootstrap block, V2's and V6's sizes and the run time. Read it (§12) before §4, §5 and §8.** Unchanged: the question, corpus, build, match rule, `BAR_N` = 0.5 pp, every row predicate's form, and the predictions.

---

## 0. Why this arm is two legs and not six (the Captain's decision, 2026-10-06)

The #3 comment proposed caps 60/55/50/45/42/40 on about three nights, and said the cost side "was never measured". **Part of that is not right, and the corrected premise is what shrank the design** (HK-018: data already gathered):

| closed leg (shim `20260050`, 2026-09-11/12) | audio | genuine decodes that 60 kept and 40 lost |
|---|---|---|
| `NT`: isolated weak station, a 21-rung ladder that brackets the threshold | synthetic AWGN | **0 of 710**; OSD rescued none **even at `nhard` 0** (`…-0956-…-nt-acceptance.md`) |
| `CC`: five S7 co-channel families | synthetic AWGN | **0 of 3,681**; `C = 0` in every family (`…-1029-…-cc-acceptance.md`) |
| `E3`: 60 vs 40 replay of a recorded on-air span | **real** | 1,491 of 57,594 reproduced live decodes removed; **2 confirmed by WSJT-X** (`…-2210-…-e3-acceptance.md`) |

So on the old build, the price of 40 was about 2 WSJT-X-confirmed decodes in 57,594, and OSD rescued nothing genuine in any synthetic condition tested.

**What is genuinely new since then, and the only reason to expect a different answer:**

- **Native subtraction with a residual pass** (ON by default since v0.54). A weak station uncovered after a strong one is subtracted, decoded from imperfect residual audio, is exactly the "BP fails, OSD rescues" case that `NT`/`CC` could not create.
- PASSBAND-140, density suppression and step 4 change which candidates reach OSD at all.

⇒ **The question:** on today's build, with subtraction ON, does a cap of 60 recover WSJT-X-confirmed decodes that 40 loses, by enough to matter? **Two legs answer that.** The four intermediate caps are only worth running if the answer is yes (§7, Stage 2). This is the cheaper experiment the Captain chose: *"Two-leg replication (Recommended)"*, 2026-10-06.

**Replication, not a re-read of a closed gate.** The closed gates (`NT-S1`, `CC-S1`, `E3-N`) stand and are not re-read. This arm measures a new build with a new statistic and a new bar, registered before its data exists (`closed-arms-prohibitions.md`: never re-read a closed gate with a better metric).

---

## 1. Question and scope

**Q:** on the 2026-10-04/05 40 m night, replayed through today's `main` with subtraction ON, how many more decodes that the **live WSJT-X** also decoded in the same cycle does `nhard` 60 produce than `nhard` 40?

**Scope sentence, to head the report verbatim:** *"One 40 m night on the station's current capture chain, replayed through one build at two `nhard` caps. Replay is not the live path. WSJT-X's Enable AP is OFF on this station, so the reference is non-AP. Decodes WSJT-X did not confirm are an upper bound on false positives, not a count of them."*

---

## 2. Corpus: the inventory, and why this night

**Every `artefacts/` folder with WAVs was listed before choosing** (2026-10-03 rule; the Architect's `find` over all of `artefacts/`, 2026-10-06 ~14:1xZ). **The recorded `nhard` was not used to filter**: the replay sets `nhard` itself.

**Eligibility, as criteria that do not look at outcomes:**

- **(E1)** whole-cycle WAVs at 12 kHz, mono, 16-bit, 180,000 samples;
- **(E2)** a WSJT-X `ALL.TXT` recorded live **from the same audio stream**, over the same window. This is a validity condition: the reference must have heard what the replay hears;
- **(E3)** the station's **current capture chain**: FT-991A → USB CODEC → Voicemeeter B1, one radio feeding both decoders (Captain, 2026-09-21).

| folder group | WAVs | live WSJT-X `ALL.TXT` | (E3) current chain | eligible |
|---|---|---|---|---|
| 2026-06-13 … 2026-08-09 `live_run_*` (19 folders) | yes | most | ✗ (pre-2026-09-21 chains: antenna splits, the SDR, the 8080/8081 three-decoder runs) | no |
| 2026-08-30 … 2026-09-14 R&R `rr-s1s8*` (7 folders) | yes | n/a (synthetic study playback, not on-air) | n/a | no |
| `20260908_1827-fp-floor-live-2` | 5,495 | yes | ✗ (pre-2026-09-21) | no |
| `20260921_1624-live-gap-map`, `20260922_*`, `20260923_1730` | not checked in full | yes | not checked (`20260923` is the direct-USB-CODEC arm) | not chosen: the build-family criterion below excludes them whatever their chain |
| `20260925_2010_endurance_run-gathered` | 2,884 | yes | ✓ | eligible |
| `20260930_1930_endurance_run-gathered` | 4,299 | yes | ✓ | eligible (**used** by the 2026-10-02 flag-OFF/ON replay) |
| **`20261004_1634_endurance_run-gathered`** | **3,106** | **yes** | **✓** | **eligible: CHOSEN** |

**Why 20261004_1634, by a criterion fixed before any decode:** it is the **only** eligible night recorded on the build family this replay uses (live build `040613d9`, v0.56, shim `20260058`, flag ON, `nhard` 40). So its live OpenWSFZ `ALL.TXT` is a usable **fidelity check** on the 40-leg (§6 descriptive). No other eligible night can give that. **20260930_1930 is the pre-named second night** if Stage 2 or §7 calls for one; 20260925_2010 is the third.

> **Inventory completed 2026-10-06 ~14:4xZ (Architect), after the first commit and before any datum.** The full `find` also lists these WAV folders, which the table above did not name. **None changes the choice:** the build-family criterion excludes them all, whatever their chain.
> - `20260922_1937`/`20260922_2056`/`20260923_1730_endurance_run-gathered`, `20260921_1624_live_run-live-gap-map`: older builds.
> - `_24h_usbcodec_endurance_daemon_output`, `_40m_endurance_daemon_output`: daemon-output copies of older endurance runs.
> - `_rr_*_daemon_output` (5), `rr_2026-09-29_subfeas_off_on`, `20261002_2115_lateness_edge_run`, `20260925_l1l4_capture_self_healing`: synthetic study playback or test captures, not an on-air night with a live reference.
> - `d001_r4_sensitivity_gap`, `d001_r5_hybrid_ladder`, `d001_wav_source_cross_decode_2026-07-30`, `lr_phase_check`, `p10-…`/`p12-…_items`: small D-001/early-phase sets.
>
> Per-folder WAV counts include WSJT-X's own saved WAVs where gathered (e.g. 6,212 for `20261004_1634` = 3,106 OpenWSFZ + 3,106 WSJT-X). The corpus is the OpenWSFZ set only.

⚠️ **Paths moved (QA, note this):** the gatherer now **moves** WAVs into `…-gathered/owsfz/wav/`. The `…_endurance_run/cycle-audio/` folders hold only `cycle-archive.csv` now, so the 2026-10-01 spec's audio path is stale.

---

## 3. Fixed inputs (asserted in code, not prose)

| item | value | assertion |
|---|---|---|
| Build | `origin/main` at the harness freeze (`be3cc5ac` at this writing), clean checkout | commit recorded in `preflight.json` |
| DLL | `libft8.dll` shim `20260058`; **full SHA-256 written to `preflight.json` before the first decode** | actual == recorded at the start and end of **every** arm; mismatch ⇒ that arm INVALID |
| Decode call | managed `DecodeTwoStageAsync`, one call per cycle (harness mode `two1`), as in the 2026-10-01 spec | — |
| Subtraction | ON, `subtractionMaxThreads` 8, in **every** arm | read back in-process, `preflight.json` |
| Early decode | not exercised (whole-cycle WAV replay) | stated in the report |
| `kMinScorePass2`, `osdCorrThreshold` | 10, 0.10, unchanged in every arm | asserted |
| **`nhard`** | **the only thing that differs: 40 or 60** | §5 V2 |
| Audio | `artefacts/20261004_1634_endurance_run-gathered/owsfz/wav/` | R0 per file: (E1) |
| Reference | `artefacts/20261004_1634_endurance_run-gathered/wsjt-x/ALL.TXT` | read only inside the matching function (HK-037) |
| Process | a fresh process per arm; cycles in ascending stamp order; numeric outcome files only | — |

**Harness change (QA's, `qa/` only, not `src/`):** `replay81/Program.cs:38` hard-codes `private const int OsdNhardMax = 40;`. Make it a required `--nhard` argument, accepting only `40` or `60`. The `# readback` line logs the value passed. That alone is self-referential (HK-026), so V2 adds an outcome-independent positive control.

---

## 4. Cycle set, match rule, estimand

**Cycle set:** every WAV that passes R0, except the first and last stamps of the window. Cycles where WSJT-X logged 0 decodes are kept (excluding them would select on the reference). Exclusions are counted by reason. The ordered list is frozen as `selection.json`, and its SHA-256 is recorded before the first decode. Every arm uses it.

**Matched:** **Test B's rule, unchanged** (`replay81` `CorroborationDeltaHz = 10`): same message text, same cycle, |Δf| ≤ 10 Hz, one-to-one nearest-first, in-process. Post-processing parity is as established in 2026-10-01 Amendment 1 (`MapNative` dedup `Ft8Decoder.cs:528`, `IsPlausibleMessage` `:534`). QA re-confirms both lines by FILE:LINE at the frozen commit.

For included cycle *i*: `W_i` = WSJT-X decodes in that cycle; `M40_i`, `M60_i` = matched decodes of each arm, **batch 1 ∪ batch 2** (what the operator sees).

- **`NET` (pp)** = 100 × Σ(`M60_i` − `M40_i`) / Σ`W_i`.
- **Interval:** 95 % percentile CI, **non-overlapping block bootstrap** over the frozen order. Block = **40 cycles**; the last partial block is kept as its own block; numerator and denominator are resampled together; B = 10,000; seed 20261006. Reported but not used for the verdict: blocks 20 and 160, and the autocorrelation of `d_i = M60_i − M40_i` at lags 1, 4 and 40.
- 🔴 **Unit of independence (the S3c §2 lesson, 2026-10-05):** a gain is not an independent event if one station, or one cycle, carries many of them. The report states:
  - the number of **distinct cycles** with `d_i ≠ 0`;
  - the largest |Σ`d_i`| in any one 40-cycle block;
  - the share of Σ`d_i` carried by the top 5 blocks.

  If the top 5 blocks carry more than half of a positive Σ`d_i`, the report says so in its first paragraph, whatever the row.

---

## 5. Validity rows (any FAIL ⇒ no verdict; the report names the row and stops there)

| row | predicate (as code) |
|---|---|
| **V1** | DLL actual == recorded, start and end, every arm (N40, N60, AA) |
| **V2** (the setting is really applied: positive control, outcome-independent) | Before the corpus arms, QA renders **400 seeded pure-noise WAVs** (12 kHz, 180,000 samples, white Gaussian, `normalise_rms(·, 0.20)` per the E1 contract; seed from the label `NHARD-REP-PC`). They are decoded through the **same harness and build** at 40 and at 60. Every decode on pure noise is false. **PASS iff `n_false(60) ≥ n_false(40) + 5`.** At shim `20260050` the rates were 10.3 % vs 0.35 % of slots (E1), ≈ 41 vs ≈ 1 at this size. If today's build has far fewer noise decodes, V2 can fail on a quiet build, not on a setting that didn't apply. In that case the report says which, and the Architect rules before anything else runs. |
| **V3** | 0 access violations, 0 contained exceptions, 0 non-zero exits, every arm |
| **V4** | the subtraction flag, thread count and `nhard` read back at start and end of every arm as in §3; `selection.json` SHA identical in every arm |
| **V5** | residual passes abandoned ≤ 5 % of included cycles **in each corpus arm** (abandoned passes count as 0 extras, which is the live behaviour) |
| **V6** (the instrument on real "nothing": an A/A control) | **AA** = a second, fresh **40** process over the **first 800 included cycles**. `NET_AA` = the §4 statistic with AA in place of N60, against N40 on the same 800 cycles, block bootstrap as in §4. **PASS iff `CI(NET_AA)` lies inside (−`BAR_N`/2, +`BAR_N`/2)** and every per-cycle difference is either 0 or in a cycle whose residual pass was abandoned in exactly one of the two runs (the 2026-10-01 Amendment 1 class "explained"). **Any unexplained difference ⇒ FAIL.** |

**Why V6 is not decorative (HK-025(k), evaluated both ways):** the expected `NET` is near zero. At that size the run-to-run jitter of the flag-ON path (its deadline and 8 workers) is the noise the bootstrap does not see. A/A shows directly whether the instrument can read "no difference" as no difference, on this build and this audio. That is the lesson of the 2026-09-28 SUB-FEAS Stage 1 failure: *measure an instrument's reading on real "nothing" input before trusting a bar.* If V6 fails, `NET` cannot be told from the instrument's own noise at this bar, and no verdict is issued.

---

## 6. Verdict rows (exclusive, first match wins)

| row | predicate | reading and consequence |
|---|---|---|
| **N-LEVER** | `CI_lo(NET) ≥ BAR_N` | **60 recovers a measurable number of WSJT-X-confirmed decodes on this build.** ⇒ Stage 2 (§7): the Architect specs the intermediate caps **and** the FP cost (exchange rate). **No default changes on this row alone.** |
| **N-CLOSED** | `CI_hi(NET) < BAR_N` | **`nhard` is not a lever for the gap to WSJT-X on this build and band.** 40 stays. No intermediate caps. Item B closes. |
| **N-OPEN** | otherwise | Unresolved. Nothing changes. The Captain decides whether to add the pre-named second night (20260930_1930) under the same rows. |

**HK-025(k), stated so QA can check it:**

- **N-CLOSED cannot fire on an instrument that is blind**, for two reasons: V2 shows the cap moves the output, and V6 shows the null reads as null.
- **N-LEVER cannot fire on extra false decodes**, because `M` counts only WSJT-X-confirmed decodes.
- **What neither row can see:** genuine decodes that WSJT-X also missed (HK-026). They cannot close the gap to WSJT-X, which is the programme's question, so this does not weaken the verdict for that question. It does mean an N-CLOSED reads *"not a gap lever"*, never *"60 recovers nothing real"*.

**Descriptive (no row; all numeric):**

- **The E3 analogue, both directions:** `K` = WSJT-X-confirmed decodes present at 60 and absent at 40; `G` = present at 40 and absent at 60 (a removal changes what is subtracted, so gains at 40 are possible). Report both, and `K − G`.
- **The cost side:** decodes WSJT-X did not confirm, per cycle, at 40 and at 60 (an upper bound on FP). Per Test B SNR band A–D, with Wilson 95 % CIs. Plus V2's noise-only counts.
- **The exchange rate:** additional WSJT-X-confirmed decodes per additional not-confirmed decode (60 minus 40).
- **Split by batch:** batch 1 and batch 2 separately. This is where the subtraction question in §0 shows: a 60-vs-40 difference **in batch 2 only** would put the mechanism in the residual pass.
- **Replay fidelity:** N40's per-cycle decode count vs the live OpenWSFZ `ALL.TXT` (`…-gathered/owsfz/ALL.TXT`, the same shim at `nhard` 40), counts only.

---

## 7. What each row leads to, and Stage 2 (registered now, specced only if needed)

- **N-CLOSED** ⇒ board: item B CLOSED. **Citable as:** *"`nhard` 60 vs 40, NET x.xx pp [lo, hi] of WSJT-X's decodes, one 40 m night, replay vs replay, Test B match rule, flag ON."* Never *"`nhard` has no effect"*. The FP side moved, and the report shows by how much.
- **N-LEVER** ⇒ Stage 2: a new Architect spec for caps 45/50/55 on the same corpus plus the second night, with the FP cost gated, and only after the Captain's go. A default change would then need its own row, a dev-task, a Developer (HK-011) and the Captain's merge (HK-010). **Not licensed here.**
- **N-OPEN** ⇒ the Captain's call.

---

## 8. Run order, machine, output

1. Ratify `BAR_N` (§9 Q1), recorded in this file **before** any harness is run.
2. QA: the harness change (§3), the frozen `selection.json` and the V2 noise set, with row predicates as code (`GUARDED` list as in the 2026-10-01 spec), **committed before any decode**.
3. Runs, each a fresh process, detached and supervised (HK-013, HK-023), with teardown and an orphan check (HK-019):
   - V2 positive control (≈ 30 min);
   - **N40** (≈ 3,104 cycles × ≈ 2.4 s ≈ 2.1 h);
   - **N60** (≈ 2.1 h);
   - **AA** (800 cycles, ≈ 35 min).

   ≈ 5 h total. **WSJT-X closed** (the reference is its archived `ALL.TXT`). The PC's practical load is acceptable (Captain 2026-10-03): no two builds' timings are compared here, because the outcome depends on timing only through V5/V6.
4. **Output:** per-cycle CSV `stamp, W, n40_b1, n40_b2, n60_b1, n60_b2, M40, M60, M40_b1, M40_b2, M60_b1, M60_b2, nc40, nc60, abandon40, abandon60`, plus per-band counts. **Numeric only: no message text, callsign or text-derived hash in any file** (HK-037). Report and `rows.json` under `qa/rr-study/results/2026-10-0x-nhard-rep/`; prose NFR-021-scanned before commit. The run folder is copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results` as the last step (Captain, 2026-10-04).

---

## 9. Questions for the Captain

**Q1, needed BEFORE any decode: ratify `BAR_N`. Proposed: `BAR_N` = 0.5 pp of WSJT-X's decodes.**

- **Why this value:** it is roughly the break-even with the FP cost. On this night Σ`W` ≈ 98,000, so 0.5 pp ≈ 490 extra confirmed decodes. At shim `20260050`, 60 instead of 40 added ≈ 0.136 false decodes per noise cycle (E1/`NT`: 0.1385 vs 0.0025), ≈ 420 over ≈ 3,100 cycles. **Below 0.5 pp, 60 would buy about one confirmed decode per false one, or worse.** That is not a lever worth a default change, whatever the CI says. It is also large enough that V6's A/A has room to pass (±0.25 pp).
- **Alternative: 0.25 pp.** It is more permissive toward calling a lever, and V6's room halves. Resolution is not the limit: with `d_i` mostly 0, the CI half-width should be a few hundredths of a pp. That is a computed expectation, and V6 checks it.
- 🛑 Once ratified, **FROZEN** for this arm (the `BAR_S`/`BAR_H` precedent). If anyone, me included, proposes moving it after `NET` is known, refuse: that VOIDs the verdict.

> ✅ **CAPTAIN'S RULING, 2026-10-06 ~14:34Z (`date -u`): `BAR_N` = 0.5 pp RATIFIED** ("0.5 pp (Recommended)", over 0.25 pp). Recorded **before any `NHARD-REP` datum exists**: no harness change, no noise set, no decode. **FROZEN for this arm**; V6's A/A window is therefore (−0.25, +0.25) pp.

**Q2 (not blocking): owner.** QA holds `replay81`; the Engineer is a full peer. One owner, recorded on the board.

---

## 10. Architect predictions (blind; scored at ruling time, ledger rule 1)

| # | prediction | P | class |
|---|---|---:|:---:|
| NR1 | Verdict **N-CLOSED** | 0.80 | H |
| NR2 | `NET` point estimate in [−0.05, +0.15] pp | 0.65 | H |
| NR3 | V2 passes | 0.85 | C |
| NR4 | V6 passes | 0.80 | C |
| NR5 | Not-confirmed decodes per cycle are higher at 60 than at 40 (point estimate) | 0.90 | H |
| NR6 | If `K` > `G`, more than half of `K − G` sits in batch 2 | 0.55 | H |

**On the ledger's known bias:** my HYPOTHESISED calls lean toward *"a findable defect is there"*. NR1 leans the other way, because three closed legs (`NT`, `CC`, `E3`) say so, and the only new mechanism (§0) is a hypothesis of my own. NR6 is that hypothesis, priced near a coin flip on purpose.

---

## 11. What this arm does NOT do

- 🛑 No `src/` or `native/` change, no rebuild of the product, no push, no merge (HK-011 / HK-014 / HK-010). The harness change is under `qa/`.
- 🛑 No other decoder parameter moves.
- 🛑 No synthetic S5 run: at ≈ 1 event per 1,560 slots it plays in real time and cannot resolve two caps in useful time (#3 comment). V2's noise set is a positive control of the setting, not an FP-rate measurement.
- It does not replicate across bands (one 40 m night), and it does not test the live path.
- **HK-025 is available in full.** If any row above is a diagnostic dressed as a gate, name it, evaluate both branches, and refuse.

---

## 12. Amendment 1 — 2026-10-06 15:01Z (`date -u`), BEFORE any harness change, noise set or decode: a systematic 1-in-10 sample

**Why.** The Captain asked whether ≈ 5 h was too much. Checking it showed **the estimate was wrong, and low**. §8's 2.4 s/cycle came from the priority-1 to-do, and that is the **Stage B B2** build's replay speed. B2 is not on `main`. The last flag-ON replay on a `main`-line build took **7 h 58 min for 4,298 cycles, ≈ 6.7 s/cycle** (`results/2026-10-01-sub-feas-offline-onoff-replay/report.md:40`). At that speed the design as written is ≈ 13 h. **The Captain chose "Every 10th cycle, ~1.6 h"** (2026-10-06 ~15:00Z), over a 1-in-5 sample (≈ 3 h) and the full night (≈ 13 h).

**Why a sample can answer the question:** `BAR_N` is 0.5 pp, and the expected `NET` is near 0 (§10 NR2). At ≈ 31.6 WSJT-X decodes per cycle (98,156 over the night), ≈ 310 cycles give Σ`W` ≈ 9,800, so 0.5 pp ≈ 49 decodes. If one cycle in ten moved by ±1 decode by chance, Σ`d` would have a spread of ≈ ±6 decodes ≈ ±0.06 pp, so 0.5 pp stays resolvable. 🔴 **The risk this accepts:** if gains cluster in a few cycles, a 1-in-10 sample can miss or over-weight them. §4's clustering report (amended below) makes that visible, and N-OPEN catches it. Computed while drafting (HK-021(m)); V6 checks the noise side on real data.

**Changes (they replace the cited text; everything else stands):**

| where | was | now |
|---|---|---|
| §4 cycle set | every included cycle (≈ 3,104) | build the full included ordered list as before. The **sample** = the entries at positions `i` with `i mod 10 == 0` (0-based; position, not stamp, so a gap in the night shifts nothing). ≈ 310 cycles. **Both the full list and the sample** are frozen in `selection.json` and SHA-recorded before the first decode. Exclusion counts are reported for the full list. |
| §4 bootstrap block | 40 cycles; 20 and 160 reported | **8 sampled cycles** (≈ 20 min of night, ≈ 39 blocks), the last partial block kept; **4 and 16 reported**, not used for the verdict. Autocorrelation of `d_i` at lags 1, 2 and 8 (sampled positions). B, seed and ratio estimator unchanged. |
| §4 clustering report | top 5 of 40-cycle blocks | the same three figures on 8-cycle blocks: distinct cycles with `d_i ≠ 0`; the largest \|Σ`d_i`\| in one block; the share of a positive Σ`d_i` carried by the top 5 blocks. If that share is > ½, the report says so in its first paragraph. |
| §5 V2 | 400 noise WAVs; PASS iff `n_false(60) ≥ n_false(40) + 5` | **200** noise WAVs (label `NHARD-REP-PC`); **PASS iff `n_false(60) ≥ n_false(40) + 3`**. At the E1 rates this expects ≈ 21 vs ≈ 1. The "quiet build" clause stands. |
| §5 V6 | AA over the first 800 included cycles | AA over the **first 200 sampled cycles**. Same predicate, window (−0.25, +0.25) pp, block 8. |
| §5 V5 | ≤ 5 % of included cycles | ≤ 5 % of **sampled** cycles, each corpus arm |
| §8 run time | ≈ 5 h | V2 ≈ 15 min; N40 ≈ 310 × 6.7 s ≈ 35 min; N60 ≈ 35 min; AA ≈ 22 min. **≈ 1.6–1.8 h.** |
| §6 N-OPEN | the Captain may add the second night | the Captain may **first** add the remaining sampled positions of this night (`i mod 10 == 5`, a second ≈ 310) under the same rows and **pooled with the first sample**. The second night stays the next step after that. |
| §2 scope sentence | "One 40 m night …" | add: *"A systematic 1-in-10 sample of the night's cycles."* |

**Not changed and not changeable:** `BAR_N` = 0.5 pp, the row predicates N-LEVER / N-CLOSED / N-OPEN, V1–V4's forms, the match rule, the corpus and the build. Predictions NR1–NR6 stand as written: they were made before any datum, and the sample does not change what they predict. **NR3/NR4 are now on the smaller V2/V6**, and if either misses on size alone the ruling says so.

---

## 13. Amendment 2 — 2026-10-06 15:18Z (`date -u`): the V2 ruling. V2 is replaced by an in-process gate probe, V2′. No corpus arm has run.

**What QA reported (message 15:15:26Z by its `date -u`; evidence `artefacts/rr_2026-10-06_nhard_rep/v2_gate.json`, harness `qa/nhard-rep` `780b280a` + `3f70072f`, local):** V2 FAIL. On 200 noise WAVs, `n_false(40)` = 0 and `n_false(60)` = 0, where ≥ +3 was required. Build `be3cc5ac`, DLL `2fa6d993…f365`, pins equal at start and end, read-back `nhard` = 40 / 60 as intended, rc 0, orphan check empty. **QA stopped and refused nothing. That was correct: the gate did exactly what it was written to do.**

**Checked myself (HK-018):**

- **The noise level is right.** One file: 12 kHz, mono, 16-bit, 180,000 samples, RMS 6,553.6 = **0.200 FS**, peak 29,963. The generator is `normalise_rms(standard_normal)`, the E1 contract.
- **Both batches are empty on every row** (`run_V2N60.csv`: `decodes` 0, `b1_n` 0, `b2_n` 0), at **43–68 ms per cycle**. A real cycle takes seconds. So the decoder does very little work on white noise on this build, which is consistent with nothing reaching OSD. Why it is so quiet (candidate search, PASSBAND-140, density suppression) is **not established** here, and this arm does not need it.

**Ruling: V2 FAILED, VALIDLY, and it is RETIRED as a row.** It cannot separate the two readings QA named, so re-running it in another form would only show again that noise is quiet. **QA's option (b), proceeding on V6 alone, is REFUSED.** V6 shows the instrument reads "no change" as no change. It cannot show that the cap reached the decoder, and N-CLOSED needs exactly that. **QA's option (a) is taken, in a form that cannot be quiet:**

### V2′ — the native gate, probed inside each corpus arm's own process

The native export `ft8_ldpc_decode_llrs` (`ft8_shim.h:1228–1280`, shim 20260044+, test-only, no product call site) runs production's BP → OSD → CRC sequence. **Its OSD branch applies the same gate the product uses:** `if (nhard > OSD_NHARD_MAX)` at `patched/ft8/decode.c:995`, where `OSD_NHARD_MAX` is the process-global `s_osd_nhard_max` (`decode.c:58/62`). `ft8_set_decode_params` writes it, and the managed `SetDecodeParams` calls that. Probing it **in the harness process, after the managed decoder has set its parameters**, tests the actual value the arm decoded with, on the pinned DLL. The audio plays no part.

**Calibration (QA, offline, committed BEFORE any corpus decode):**

- **Two frozen 174-float RAW LLR vectors**, from a codeword of a Q-prefix message (`ft8_encode_message`, NFR-021), with chosen hard-decision errors:
  - **`P_hi`**: true Hamming distance between the codeword and the LLR signs `nhard_true` ∈ **[48, 56]**;
  - **`P_lo`**: `nhard_true` ∈ **[20, 32]**.
- **The construction is QA's.** A suggestion: give the flipped positions the smallest |LLR| so they land outside OSD's reliable basis, and use a small `max_iters` so BP does not converge.
- **Calibration predicate, by ctypes on the pinned DLL**, after `ft8_set_decode_params(10, 0.10, N)`, for each vector and each `N` ∈ {30, 40, 50, 60, 100}:
  - `P_lo`: `out_path` = 1 (OSD) and `out_crc_ok` = 1 for every `N` ≥ `nhard_true`;
  - `P_hi`: `out_path` = 1 and `out_crc_ok` = 1 iff `N` ≥ `nhard_true`, otherwise `out_path` = −1.
  - **The returned payload equals the encoded message's** (`a91`).
  - If a vector cannot be made to satisfy this, QA reports it and **stops**. The Architect rules; QA does not improvise a substitute.

**The row (as code; replaces V2 in §5's table):**

| row | predicate |
|---|---|
| **V2′** | In each of N40, N60 and AA, the harness probes `P_hi` and `P_lo` through `ft8_ldpc_decode_llrs` **after the decoder's `SetDecodeParams` and the warm-up, and again after the last cycle** (the harness P/Invokes the export directly; `qa/` code, no product binding). **PASS iff, at both points:** `P_lo` is accepted (path 1, CRC 1, payload matches) in every arm; `P_hi` is **accepted in N60** and **rejected (path −1) in N40 and AA**. |

**HK-025(k), both ways:**

- If the cap did not reach the native gate, `P_hi` gives the same answer in N40 and N60, so V2′ FAILS.
- If OSD itself were broken, `P_lo` fails, so V2′ FAILS.
- **What V2′ does not cover:** whether the *live* product applies the cap. That is the product's config path, out of scope here, and the station's `config.json` reads 40.
- **The one remaining inference** is that `DecodeTwoStageAsync` decodes with the same process-global the probe reads. `s_osd_nhard_max` is one non-TLS global in one DLL, so no other value exists to decode with. Stated, not tested.

**What else changes:**

| where | change |
|---|---|
| §5 V2 | struck; V2′ above. The 200-WAV noise result stays in the report as **descriptive**: *"0 decodes at either cap on 200 white-noise cycles at RMS 0.20 on this build"* (E1 measured 10.3 % vs 0.35 % of slots at shim 20260050). |
| §8 run order | calibration (offline) → corpus arms N40 → N60 → AA, each with V2′ probes inside it. **No separate V2 arm.** If V2′ fails in N40 (its first probe point), stop there. |
| §4 citations | QA's correction is **accepted**: at `be3cc5ac`, `MapNative` is `Ft8Decoder.cs:563` and `IsPlausibleMessage` `:585`; `:528`/`:534` were stale. |
| §5 V6 | QA's reading is **accepted and made explicit**: the gated per-cycle difference is `d_i = M_AA,i − M40,i` (the statistic's own noise). The union-multiset difference is reported per cycle, not gated. If any cycle differs in multiset **and** is not "explained" (a residual-pass abandon in exactly one run), the report says so in its first paragraph. |

**Not changed:** `BAR_N` = 0.5 pp (FROZEN), N-LEVER / N-CLOSED / N-OPEN, the corpus, the sample, the build, the match rule and V1/V3–V6.

🔴 **One consequence the Captain should see, stated now so it cannot be read later as a re-read of the bar:** §9's case for 0.5 pp assumed 60 costs about 0.136 false decodes per noise cycle (the 20260050 figure). On this build, white noise gives none at either cap. **The bar stays frozen.** Whether 60 costs false decodes on real audio is what the corpus arms' not-confirmed counts (§6 descriptive) will show. That is where the exchange rate gets read, not from noise.

**Prediction scored at Amendment 2 (ledger rule 1):** **NR3 "V2 passes" (0.85, C): 🔴 MISS.** It was a computed miss that I priced as safe. I took E1's noise rate from shim 20260050 and never checked whether today's build still decodes anything on noise. That is the SUB-FEAS lesson I cited in V6's own rationale: *measure the instrument on real "nothing" before writing the bar.* V2′ is written so that its pass condition does not depend on any rate.

---

## 14. Amendment 3 — 2026-10-06 18:19Z (`date -u`): `OSD-OFF`, one new arm against the existing N40 (#215)

**Licence:** the Captain chose *"Yes, ~35 min replay"* (2026-10-06 ~18:1xZ), after COH-GAIN showed that a sign-**corrected** OSD is not a lever (GO +0.011 pp; 1 true vs 271 wrong payloads; ruling `418a6941` §4). Production OSD is sign-inverted (#215), so every accept it makes is a chance-CRC false decode. **Question: what do those false decodes cost the shipped decoder, and is "OSD off" a safe setting?**

**Arm N0:** the same harness (`qa/nhard-rep`), build, pin, flag ON, threads 8, Test B rule and the **same 311 sampled cycles**, at **`--nhard 0`**. The harness must accept 0 (QA's change, `qa/` only). The managed `SetDecodeParams` → `ft8_set_decode_params` path passes the value through with no range check; only the config layer enforces 30–100, and the harness bypasses it. **At 0 the gate rejects every OSD codeword**: an inverted-OSD codeword sits near the complement, so `nhard` is far above 0. ⇒ OSD is effectively off. **It is paired with the existing N40 arm** (`artefacts/rr_2026-10-06_nhard_rep/`, same cycles, same build). N40 is **not re-run**.

**Validity:**

- **V1′:** pin equal at start and end.
- **V2″ (the setting reached the gate):** in N0, **`P_lo` (`nhard_true` 26) is REJECTED** (path −1) at both probe points, while it was ACCEPTED in N40 (on file). `P_hi` is rejected. This is the outcome-independent proof that 0 applied.
- **V3–V5 as before** (exits, read-back, abandons ≤ 5 %).
- **V6 is carried:** N40's own A/A (200/200 exact) shows the instrument reads null as null on this build. It is not re-run.

**Statistic:** `NET_0` = 100 × Σ(`M0_i` − `M40_i`)/Σ`W_i`, same block bootstrap (block 8, B 10,000, seed 20261006), plus the same descriptives: K/G split, by batch, not-confirmed per cycle and by band.

**Rows (exclusive, first match wins):**

| row | predicate | reading |
|---|---|---|
| **O-HARM** | `CI_hi(NET_0)` < 0 | Something genuine depended on the inverted OSD. **That contradicts #215's analysis**, so the Architect re-examines it before any default change. |
| **O-GAIN** | `CI_lo(NET_0)` > 0 | Switching OSD off **gains** WSJT-X-confirmed decodes (the false-decodes-subtracted mechanism, measured). |
| **O-SAFE** | `CI_lo(NET_0)` ≥ −0.10 pp | Off costs at most 0.10 pp of confirmed decodes. |
| **O-OPEN** | otherwise | Unresolved. |

**HK-038, where the numbers come from:**

- **0 (the O-GAIN and O-HARM boundaries)** is the no-change point, not a carried figure.
- **−0.10 pp (O-SAFE)** is a **decision margin**. ⚠️ **It needs the Captain's ratification before N0 runs.** Proposed basis: the closed E3 leg found only 2 of 57,594 WSJT-X-confirmed decodes that depended on OSD at all (≈ 0.003 %), and the sign analysis predicts none. So 0.10 pp is ≈ 30× the largest plausible genuine dependency, while staying small against the gap.

**Consequence:** an O-GAIN or O-SAFE gives the Captain the evidence to set **OSD off as the interim default** for #215, until a working OSD exists. On C3's LLRs a corrected OSD is +0.26 pp (step-3 territory). The change itself would be a config default plus a migration, through a dev-task, a Developer (HK-011) and a merge sign-off (HK-010). **Not licensed here.**

**Predictions (blind; scored at its ruling):**

| # | prediction | P | class |
|---|---|---:|:---:|
| OO1 | O-GAIN | 0.40 | H |
| OO2 | O-SAFE (and not O-GAIN) | 0.50 | H |
| OO3 | O-HARM | 0.03 | H |
| OO4 | not-confirmed per cycle falls from 0.47 by ≥ 0.10 | 0.55 | H |
