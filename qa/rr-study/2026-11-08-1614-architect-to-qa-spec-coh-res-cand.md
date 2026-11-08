# `COH-RES-CAND` (#272) build spec: the fallback's residual run gets the residual buffer's own candidate list, behind a setting, default OFF

**From:** Architect · **To:** QA (for the Developer, HK-015) · **Date:** 2026-11-08 16:14:51Z (`date -u`) · **Branch:** `arch/coh-res-cand`
**Authority:** the Captain, 2026-11-08: "ok #272 first, but please keep the verification tests small. it seems to me that the tests become longer and longer all the time", then "fine with me" to the test shape in §3. It also covers two small QA jobs he approved in the same exchange ("ok, lets do it"): the parser fix (§6) and the same-chain check (§7).
**Base:** `main` `fe1454c1` (v0.68). **This is a `src/` change and needs a separate Developer session (HK-011)**, QA's HK-039 review before any acceptance run, and `pre_merge_check.py` before any push (HK-006). This document is docs only (`git diff --stat origin/main -- src/ native/` is empty).

🟢 **Size rule for this arm (the Captain's).** Two replay arms of 400 cycles on the PC and one 40-cycle identity check. **No second night, no sol, no pilot, no Original arm.** Any amendment that adds an arm or cycles needs his word, not mine.

---

## §0. What is being built, in one paragraph

In `Both` mode the coherent fallback runs twice: first on the residual buffer (R3 if the third pass ran, else R2), then on the original audio. **Today both runs use the candidate list from the original audio's decode** (`cohSnapshot`, taken at `Ft8Decoder.cs:714`, passed at `:1223`, `:1232`, `:1238`). A signal that only shows after subtraction is never offered to the fallback at its position. GAP-RESIDUAL (QA, 2026-10-29) measured the cost: of 261 rows the coherent path decodes on the product's own residual buffers, **153 (1.26 pp of the reference) had no eligible candidate** in the fallback's search window. **The build:** the **residual run** uses a snapshot taken right after the `DecodeAll` of **that same residual buffer**; the **original run keeps the original snapshot**. Nothing is merged: every candidate offered today is still offered, on the audio it came from. The probable size is managed code only (see R2); a native change is not expected and is not authorised by this spec.

## §1. Behaviour (requirements)

**R1. The setting.** New key **`decoder.coherentFallbackResidualCandidates`** (bool).
- Absent means `false`. It follows the config overlay (HK-035) exactly like `decoder.coherentFallbackResidualUngated` (`Ft8Decoder.cs:246–257`): a volatile field set by the daemon before the first cycle.
- **OFF ⇒ every code path is today's code**, and no extra snapshot is taken (B-OFF checks it).
- It has an effect only when the coherent fallback is ON and the audio mode is `Both` (or `Residual`, if that mode's run reads a residual buffer). In `Original` mode it has no effect; the docs say so.

**R2. Taking the residual snapshot.** The native candidate list is thread-local and reset by the next `ft8_decode_all` on that thread (the comment at `:711–713`).
- The snapshot must therefore be copied with `CohFallbackSnapshot()` **on the thread that ran `DecodeAll` on the buffer the fallback will read, immediately after that call**. For R2 this is `SubtractionPass.cs:446` (`pass2Results = interop.DecodeAll(residual)`). For R3 it is the third pass's own `DecodeAll`; the Developer cites the file:line.
- The rule for which buffer is used is **the one `CohFallbackAudioSelector.Select(...)` applies** (`CohFallbackAudioSelector.cs:43`, called at `Ft8Decoder.cs:1214`). Take the snapshot of each candidate buffer (R2 always, R3 when the third pass ran), carry both, and use the one that matches the buffer `Select` returns. Then the snapshot and the audio cannot drift apart. For reference, GAP-RESIDUAL row 0c(ii) found R3 in 382 of 400 cycles and R2 in 18.
- ⚠️ **The diagnostics switch.** The residual `DecodeAll` runs with `SetDiagnosticsEnabled(false)` (`SubtractionPass.cs:443`). The Developer must check, from `ft8_shim.c`, whether the snapshot's candidate list and payloads are filled with diagnostics off. **If they are not:** with the setting ON, leave diagnostics on for that one call (managed only; the cost is the LDPC-failure statistics). Report which case applies, with file:line. **If neither works without a `native/` change, stop and report;** do not change `native/` under this spec.
- The residual snapshot also holds the payloads decoded on that buffer, not those of the original decode. The Developer states how the fallback uses the payloads in a snapshot (file:line in `ft8_shim.c` / `coherent_fallback.c`) and whether a payload already published in batch 1 can therefore be re-offered on the residual. Either way, R4's text de-duplication is the guard.

**R3. Use.** In the `Both` branch (`Ft8Decoder.cs:1228–1240`):
- the **first (residual) run** gets the residual snapshot from R2;
- the **second (original) run** keeps `cohSnapshot`.
- In single-run modes that read a residual buffer, that run gets the residual snapshot.
- If the residual snapshot is missing (the call failed, or nothing was taken), use `cohSnapshot` as today, count the cycle as `fallback-orig` and log it. Nothing throws.

**R4. Publication: unchanged.** Rows go through today's `Merge` and `CoherentFallbackSelector.Select` and the per-cycle text de-duplication. **No text is published twice in one cycle** (row B-DUP).

**R5. The log line.** Add to the existing coherent-fallback log line, only when the setting is ON:
- `resCand={residual-R2|residual-R3|fallback-orig}`;
- `resEligible={n}`: the eligible candidates in the snapshot that the residual run used;
- `origEligible={n}`: the eligible candidates in `cohSnapshot`.

Counters go beside the fallback's existing ones.

**R6. Version and docs.**
- `VERSION` 0.68 → 0.69, in every place the gates check.
- `REQUIREMENTS.md`: a new FR at the next free number, covering the setting, R1's scope and R3.
- An OpenSpec change `coh-res-cand` (proposal, tasks, spec delta) and a changelog row.
- Docs state: default OFF, `Both`/residual only, and turning it ON starts a new era for live figures.

**R7. Unit tests.**
- OFF is a no-op: no extra snapshot call.
- ON: the residual run receives the snapshot of the buffer `Select` returned, for R2 and for R3 (a fake interop records which snapshot each `CohFallbackRun` call got).
- The original run still receives `cohSnapshot`.
- A missing residual snapshot gives `fallback-orig` and no exception.
- No duplicate text in a cycle.
- Each `resCand` value is reachable.

## §2. What is NOT in this build

- No merged candidate list, and no change to the fallback's search window, gates or thresholds.
- No change to R-F4, multi-set, the late round (L1′), batches 1–3, or the 13 s budget arithmetic.
- No `native/` change.
- No default ON. That is the Captain's decision after §3, and it starts a new era.
- The 1,589 class-NR rows (13.1 pp) that no extractor reaches are out of scope.

## §3. Acceptance (PC, station daemon stopped)

**Night:** `20260930_1930` (L1′'s third night). It is not a discovery night for this lever; GAP-RESIDUAL used `20260925_2010`. Its same-band check is on file (L1′ build spec §4) and its U′ classes were frozen from all 800 selected cycles (classes SHA `8046a4be…`, QA 2026-10-31).
- **Cycles:** the **first 400 of L1′'s 800-cycle selection**, in that order, one process from the first of them. Outage slots are dropped and counted, as before.
- **The frozen classes are reused as they are.** That is why no Original arm is needed.
- If QA finds that night unusable on the PC, its fallback is `20261022_1949` with its own frozen classes. QA says so in its (k) review **before** any arm runs. No third choice.

**Arms:** identical except the new setting. A = OFF, B = ON. Shipping defaults otherwise: Deep, `nhard` 24, OSD fix, multi-set ON, `Both`, R-F4 OFF, late round OFF, the same thread count.

**Freeze:** before the first arm's output exists, one commit records the build commit, the DLL SHA-256, the 400-cycle selection, the classes SHA and the analysis code.

| row | predicate (mechanical) |
|---|---|
| **B-NAT** | `git diff --stat fe1454c1 -- native/` is empty, and the DLL SHA-256 equals the pin `1ba8dc3d…` |
| **B-OFF** | 40 cycles (the first 40 of the selection): the build with the setting OFF publishes output byte-identical to `main` `fe1454c1`, every field, 40 of 40 cycles |
| **B-WIRE** | in arm B: `resCand=residual-*` in ≥ 95 % of the cycles where the residual run ran, and `resEligible` ≠ `origEligible` in at least one of them (proves the new list is actually used) |
| **B-DUP** | arm B: no text published twice in any cycle |
| **N-GO** | `CI_lo(NET_B−A)` > **0** pp |
| **N-STOP** | `CI_hi(NET_B−A)` ≤ 0 pp |
| **U-OK** | `CI_hi(ΔU′_ta)` ≤ **0.021** per cycle |
| **U-FAIL** | `CI_lo(ΔU′_ta)` > 0.021 |
| **B-AB** | fallback abandoned (either run) in B ≤ the same count in A. **Data on file:** 0 fallback lines with `abandoned>0` in 400 PC cycles (GAP-RESIDUAL row 0f, `main` `c2c85c45`, `20260925_2010`), so the row fires only if the longer list costs real time on the PC |

NET, ΔU′_ta and the cycle bootstrap (B = 2000, seed **20261108**) are computed exactly as in L1′ (`tn_analyse.py` at `d50a98fe`), against the night's WSJT-X lines.

**Verdict:**
- **ACCEPT** iff B-NAT, B-OFF, B-WIRE, B-DUP, N-GO, U-OK and B-AB all pass.
- **FAIL** iff N-STOP or U-FAIL fires.
- **OPEN** otherwise.

**OPEN does not trigger a second night automatically.** It goes to the Captain with the numbers, and he decides whether a second 400-cycle night is worth it.

**Descriptive (no verdict):**
- the B−A row count split by `resCand`;
- the residual run's wall time, median and max, against the budget;
- the gained rows as a share of GAP-RESIDUAL's 153-row ceiling, stated as a different night and so **indicative only**.

**Bars (HK-038), and where each number comes from.**
- **NET bar 0 pp: the Captain's choice for this arm** (2026-11-08, "fine with me" to "the lower end of the confidence range is above 0").
  - It replaces the 0.5 pp BAR_G used since COH-GATE-G (ratified 2026-10-28).
  - Why: this lever's own ceiling is 1.26 pp (GAP-RESIDUAL, `main` `c2c85c45`, `20260925_2010`, 400 cycles). A plausible capture of a third to a half of it, 0.4–0.6 pp, would fail a 0.5 pp bar on CI_lo with 400 cycles even if it were real.
  - The cost of the lower bar: a small but real gain ships behind a setting that stays OFF until he decides.
- **U bar 0.021 per cycle on tested_absent:** the ratified U_bar_G (COH-GATE-G 2026-10-28, re-used for LATE-SUB and L1′). Same `main` lineage, same station band, same U′ instrument.
- **Check against data on file:** L1′'s 800-cycle night gave a NET interval about ±0.12 pp wide. 400 cycles should give about ±0.17 pp, so N-GO needs a true gain of roughly ≥ 0.2 pp to fire reliably. That is about 16 % of the ceiling, a fair test, not a formality.

## §4. Timing

The PC fallback ends at about 5.8 s (L1′ spec §4), and the residual run reads the same buffer as today. Only the list changes, and a longer list costs time. **B-AB is the guard:** NET already pays for any rows lost to the budget. There is no sol leg: if the Captain later wants default ON, the combined ON endurance run (with R-F4 and L1′, after §6) is where sol-class timing is seen.

## §5. Order and cost

1. QA's (k) review of this spec. Keep it to the rows: the Captain asked for small.
2. The Captain's go for the Developer session.
3. Developer: R1–R7, then a commit.
4. QA: HK-039 review record.
5. QA: freeze, B-OFF (40 cycles ×2), then arms A and B: **about 45 min per 400-cycle arm** at L1′'s PC harness speed (≈ 7 s per cycle), **about 1 h 45 min in all**. My chat estimate of 25 min per arm was wrong (ledger E133).
6. QA: a short report (rows table, the descriptive lines, nothing else), then my ruling.
7. **Merge:** `pre_merge_check.py` before any push (HK-006), and the Captain's sign-off (HK-010).
8. **Default ON:** a separate decision by the Captain, together with R-F4 and L1′, after §6.

## §6. QA job: the double-counting parsers (needed before any ON run of L1′)

The L1′ round writes its own inner `Third pass:` line, and three QA scripts count it as a second third pass: `f2_station_count.py`, `sweep_f2_record.py`, `third_pass_counters.py` (ledger E122; Replay81's `ThirdProbe` was handled by B-TOOL).
- **Fix:** each script attributes a `Third pass:` line that belongs to a `Late subtraction round:` to the round, not to the third pass. Key on the round's own line; no `src/` change.
- **Proof (mechanical):** a unit test per script with a synthetic log holding one cycle with the round OFF and one with it ON. Third-pass counts equal the counts from the third pass's own line, and the round's counts are reported separately.
- Then one real ON log (any L1′ ON arm already on disk) re-parsed: the third-pass totals equal the OFF arm's for the same cycles, within the hash feed-forward differences already listed in L1′ F3.
- **No station run.**

## §7. QA job: the same-chain check (`frans` vs `Frank`), at most 40 cycles

**Question:** does the live capture chain under `TBD\frans` deliver the same audio to the decoder as it did under `VENUS\Frank`?
- Voicemeeter (Captain, 2026-11-08): strip 1 → B1 100 %, AUX → B1 100 % (saved as default), both muted until used.
- Build and DLL are already proven identical (Engineer, 2026-11-08, `1ba8dc3d…`).
- **Method:** replay ≤ 40 cycles of a recorded night through AUX → B1 into the daemon under `frans`, then compare with a record of the **same WAVs through the same chain under Frank**.
- **QA proposes in its (k) review:** which Frank-era record is the reference (same DLL pin), and the mechanical predicate. For example, decode count and SNR per matched decode, with a tolerance taken from that record's own repeatability, not invented.
- **If no Frank-era chain record on the pin exists, say so.** The fallback is then a chain-vs-offline comparison under `frans` against the same ratio under Frank from any run on file.
- **The Captain's part:** unmute AUX for the run. No radio and no antenna are needed. QA unmutes or mutes strips only by his standing rule (`vm_strip.py`).

## §8. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| CR-1 | No `native/` change is needed (R2's diagnostics question resolves in managed code) | 0.75 | C |
| CR-2 | B-OFF and B-WIRE pass on the first Developer commit | 0.75 | C |
| CR-3 | ACCEPT | 0.45 | H |
| CR-4 | NET point estimate ≥ 0.3 pp | 0.45 | H |
| CR-5 | U-OK fires (no wrong-payload cost beyond the bar) | 0.80 | H |

**Reasoning.**
- **CR-3/CR-4:** the 1.26 pp is a ceiling at WSJT-X's own position. The fallback still needs the candidate to be strong enough and sync-correct (GAP-RESIDUAL's own caveat), and the ceiling was measured on another night. I have not counted how earlier levers' results compared with their ceilings, so P is held near even.
- **CR-5:** R-F4 and L1′ both stayed inside the U bar, and this change does not loosen any gate. It only offers better-placed candidates.

🔴 **Bias check:** HYPOTHESISED calls lean toward "a localised, findable gain". ACCEPT is held below 0.5 for that reason.

## §9. Amendment 1 (2026-11-08 16:17:43Z, `date -u`): QA (k) review adopted

QA's review (by message, 2026-11-08; not a file): **ACCEPT the rows**, with one added row and two wording fixes. All are adopted. They replace the named parts of §3. No cycles are added.

**A1.1 B-WIRE, restated.** Denominator: the cycles of arm B in which the residual run ran (the setting is ON throughout B).
- (i) `resCand=residual-*` in ≥ 95 % of them. This is the validity half: it fires if the residual run silently used `cohSnapshot`.
- (ii) `resEligible` ≠ `origEligible` in ≥ 1 of them. This is a plumbing floor only, **not evidence that the lever works**. NET is that evidence.

**A1.2 B-AB, restated.** Fallback abandoned, **counted per run** (residual run, original run): B ≤ A + 0 for each. A and B run on the same PC load, with nothing else running.
- The 0-in-400 figure from GAP-RESIDUAL (`20260925_2010`) is a **prior, not the bar's source**. The bar is A itself (HK-038).

**A1.3 New row V1-3N (zero extra cycles).** `20260930_1930` has run only on sol (`libft8.so` `488bfa0b…`), and its classes (`8046a4be…`) were frozen from sol's Original arm. PC-vs-sol equivalence was shown on `20261022_1949` (V1: 0 of 800 cycles differ, OFF arm), **not on this night**.
- **V1-3N:** arm A (PC, OFF) against the sol OFF-arm records for the same first 400 cycles (already on the PC in `_qa-scratch\late-sub\sol3n`). Published rows per cycle identical in 400 of 400.
- **Bar source:** V1's 0 of 800 on `20261022_1949`.
- **Caveat, stated:** sol's OFF arm was built from `b1d8a06e` and A from `fe1454c1`. L1′ is merged with its setting OFF, and B-OFF ties A to `fe1454c1`.
- **If any cycle differs:** list its rows, and re-check the class reuse on those rows only (do any fall in `untestable_class`?).

**A1.4 The night rule, replacing §3's fallback sentence.**
- Use `20260930_1930` with V1-3N.
- Fall back to `20261022_1949` (it has a PC OFF arm and its own classes, so there is no cross-platform assumption) **only if** V1-3N shows differing cycles that reach `untestable_class`.
- V1-3N is read right after arm A, **before arm B starts**. If it forces the fallback, arm A is re-run on `20261022_1949`, about +45 min, and the Captain is told.

**A1.5 Paths before the freeze.** The L1′ harness tools used here are checked for hard-coded `C:\Users\Frank` paths before the freeze. QA found several older `qa/` tools that still have them.
- `qa/account-paths` landing removes the question.
- Otherwise QA lists each tool this arm runs and confirms it is clean, in the freeze commit.

**A1.6 §7, the same-chain check: QA found no Frank-era reference.** No record exists of the same WAVs replayed through AUX → B1 into the daemon on pin `1ba8dc3d…`. What exists:
- live radio captures, which cannot be replayed;
- an SDRuno B2 run on an older build;
- offline Replay81 runs, which don't go through Voicemeeter.

So §7 cannot answer "the same as Frank" without a new Frank-side run. The options go to the Captain:
- **(a) QA's proposal:** chain against offline under `frans` only, ≤ 40 cycles. The tolerance comes from a repeat of the same chain run (its own repeatability). **A pass means:** `frans`' chain delivers sane, self-consistent audio close to the offline decode. **It cannot show** that it equals Frank's chain.
- **(b)** The same ≤ 40-cycle run once under Frank as well (a Frank login). This answers the actual question.

Pre-run checks for either: AUX → B1 read back with `vm_strip.py`; B1's capture ID against the restored config; WSJT-X closed; TX disabled.

**A1.7 Decided (Captain, 2026-11-08): "option a it is. qa can switch aux muted theirselfes".**
- §7 runs as **(a)**: chain against offline under `frans`, ≤ 40 cycles, plus one repeat for the tolerance.
- QA unmutes AUX for the run and mutes it afterwards itself (`vm_strip.py`), with no separate word needed.
- The report says plainly that the check cannot show equality with Frank's chain. **Live figures are still not pooled across the cutover.**

## §10. Amendment 2 (2026-11-08 17:13:26Z, `date -u`): §7 first attempt ruled FAIL-INSTRUMENT; one second attempt, thresholds unchanged

**What happened.** QA froze the predicates in `d6720d97` (`qa/same-chain`) before any result, then ran (a) under `frans`.
- The chain leg was clean: daemon v0.68 `fe1454c1` with the DLL = pin, AUX → B1, 24 WAVs × 2 trials = 48 plays, 0 slips, 0 overruns, drops or restarts. AUX was muted again afterwards and the daemon stopped.
- V-SNR passed: p95 |ΔSNR| 1 dB (= the floor), median 0.
- V-PLAY, V-SIG and V-COUNT failed.

**Ruling: the first attempt's verdict is recorded as FAIL-INSTRUMENT, not as a statement about the chain.** Two causes, both in the instrument:
- **(1) The reference was the wrong decoder path.** RefSet gives batches 1–2 only (299 + 39 decodes). The daemon runs the full path (third pass, coherent fallback), so 98 chain-only decodes (86 in both trials, median SNR −17 dB) are decodes RefSet cannot produce. **This is my error (ledger E135):** §7 said "offline" without naming the offline instrument. MEMORY's standing fact is that a raw replay is not the live path.
- **(2) V-PLAY counted a WAV that has 0 decodes offline** as a lost play, when there is nothing to log. That is a predicate flaw (QA's ledger).

**One second attempt is allowed, under these rules:**
- **Reference:** the full-path harness (the LateSub/Replay81 OFF arm) on the same 24 WAVs, ×2. Its config must equal the daemon's as read back from that run: Deep, `nhard` 24, OSD fix, multi-set ON, `Both`, R-F4 OFF, late round OFF, the same thread count. QA records the read-back beside the reference.
- **The chain data is reused as it is.** There is no new chain run, no station use and no AUX.
- **Predicates:** V-SIG, V-COUNT and V-SNR are **unchanged**, as are their tolerance derivation (the chain's own repeat) and the 1 dB floor. **V-PLAY:** a WAV is exempt only if it has 0 decodes in the reference **and** 0 in both chain trials. Every other play must have its slot.
- **Freeze:** this change, and nothing else, is committed before the reference leg's output is read.
- 🔴 **Post-data, stated:** the chain results have been seen. That is why nothing numeric may change, and only the instrument and the V-PLAY exemption move.
- **Report:** both attempts and both verdicts, side by side.
- **If the second attempt also fails, stop.** It goes to the Captain with the numbers. **No third attempt.**

**Result (QA):** the second attempt PASSED. V-PLAY 0 lost, V-SIG 47/48, V-COUNT 46/48, V-SNR p95 1 dB (the floor). Chain-vs-reference mean symmetric difference 0.77 per play, against chain-vs-chain 0.79.

## §11. Amendment 3: clarifications from QA's HK-039 review of `b0d01f4f` (APPROVED with notes N-1 to N-3)

- **N-1, B-WIRE's denominator:** arm-B cycles whose fallback `audio=` field shows a **residual level** (R2 or R3). `fallback-orig` also appears when there was no residual buffer, and those cycles are outside the denominator. A cycle with a residual level **and** `fallback-orig` (snapshot missing) stays in it and counts against (i), which is the failure (i) exists to catch.
- **N-2:** with the setting ON, the existing `eligible=` field is the larger of the two runs' counts. B-WIRE (ii) and the descriptive lines use the new `resEligible`/`origEligible` fields only, never `eligible=`.
- **N-3:** a batch-1 payload can be re-offered on the residual run. That is expected (R2's last bullet), and the guard is the text de-duplication. B-DUP checks it, unchanged.

None of these changes a bar, an arm or a cycle count.

This is not a re-read of a closed gate with a better metric (standing prohibition). The gate's metric and bars are unchanged; the first attempt compared against an instrument that cannot measure the quantity the gate defines.
