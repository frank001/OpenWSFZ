# SPEC — `NHARD-REP`: does an OSD `nhard` cap of 60 recover WSJT-X-confirmed decodes that 40 loses, on today's build and real audio? (priority #1, item B)

- **To:** QA (owner; the Captain may assign it to the Engineer instead: one owner, recorded on the board)  **From:** Architect  **Date:** 2026-10-06 14:31Z (`date -u`, HK-017)
- **Branch:** `arch/nhard-replication` (cut from `origin/main` `be3cc5ac`). Docs only: `git diff --stat -- src/ native/` empty.
- **Programme:** priority #1, item B (the Architect's memory note `todo-decode-improvement-prio1-2026-10-05.md`). Source: GitHub #3 comment 2026-10-04 17:15Z.
- ~~**Status:** DRAFT until §9 Q1 (`BAR_N`) is ratified by the Captain.~~ ✅ **`BAR_N` = 0.5 pp RATIFIED by the Captain, 2026-10-06 ~14:34Z (`date -u`), "0.5 pp (Recommended)", before any harness change, noise set or decode exists. FROZEN for this arm.** Status: **PRE-REGISTERED.** QA commits the harness change and the frozen cycle list **before any decode**. Nothing below may change after a decode has run, except by a dated amendment that says why.
- **Needs before arming:** the Captain's go for the CPU window (≈ 5 h, overnight is fine), given in the owner's window. Not given by this spec.

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
