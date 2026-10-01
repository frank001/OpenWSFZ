# SPEC — SUB-FEAS offline flag-OFF/ON replay of the 2026-09-30 on-air night (the controlled decode-rate test)

- **To:** QA (owner; cc Captain)  **From:** Architect  **Date:** 2026-10-01 ~19:35Z (HK-017)
- **Branch:** `arch/subtraction-feasibility`. Docs only: `git diff --stat -- src/ native/` empty.
- **Answers:** QA's readiness note `2026-10-01-1950-qa-to-architect-offline-replay-readiness.md` (QA worktree, uncommitted), and implements my ruling `2026-10-01-1500-architect-sub-feas-first-on-air-run-ruling.md` §3 (constraints 1–5, all carried unchanged).
- **Status:** PRE-REGISTERED. QA commits the harness and the frozen cycle list **before any decode**; nothing below may be changed after a decode has run, except by a dated amendment that says why.
- **Needs before arming:** the Captain's go for the CPU window (≈ 7.5 h exclusive). Not given by this spec.

## 1. Question and scope

**Q:** on the night of 2026-09-30/10-01 (40m, FT-991A via Voicemeeter B1, the station), how many more decodes that the **live WSJT-X** also decoded in the same cycle does flag ON produce than flag OFF, when both arms replay the same archived audio through the same build?

**Scope, to be stated at the head of the report in these words:** *"A second night on the same band, station and capture chain as the Stage 2 corpus. It replicates night to night; it does not replicate across bands. Replay is not the live path."*

## 2. Fixed inputs (asserted in code, not prose)

| Item | Value | Assertion |
|---|---|---|
| Build | `247ac391` (two-stage publish), shim `20260056` | provenance recorded |
| DLL | `libft8.dll` SHA-256 `ee00d118…990e4c` (full hash in the harness) | actual == pinned at the start and end of **every** arm; mismatch ⇒ arm INVALID |
| Decode call | managed `DecodeTwoStageAsync` (harness mode `two1`), one call per cycle, as in S1/Test B | — |
| Flag | OFF arm `subtractionEnabled=false`; ON arm `true`, `subtractionMaxThreads=8` | read back from the config object in-process, written to `preflight.json` |
| `nhard` | 40 | asserted |
| Audio | `artefacts/20260930_1930_endurance_run/cycle-audio/` | R0 per-file checks (12 kHz mono 16-bit, 180 000 samples) |
| Reference | `artefacts/20260930_1930_endurance_run-gathered/wsjt-x/ALL.TXT` | read only inside the matching function (HK-037) |
| Process | fresh process per arm; cycles in ascending stamp order; numeric outcome files | — |

## 3. The cycle set — QA §3.1

- **Included:** every archived WAV that passes R0, **except** the first and last stamps of the window (the two window-edge cycles already explained in QA's report).
- **Not excluded:** cycles where WSJT-X logged 0 decodes (they add 0 to numerator and denominator; excluding them on the outcome would be a selection on the reference), clipped WAVs (both arms hear the same audio; count them in the report).
- Excluded cycles are **counted by reason** in the report. The ordered stamp list is frozen as `selection.json` and its SHA-256 recorded before the first decode. Both arms and the repeat (§6 V6) use that list.

## 4. "Matched" — QA §3.3

**Test B's rule, exactly as implemented** (`replay81/Program.cs`, `CorroborationDeltaHz = 10`): same message text, same cycle, |Δf| ≤ 10 Hz, paired one-to-one nearest-first, done in-process (HK-037 strict route). Not the ANOVA's `match_pairs`. Reason: it is the rule already used on this build for Test B, it already runs inside the harness process, and it is strictly the more conservative of the two on hashed-callsign placeholders.

⚠️ Consequence, to be said in the report: the matched-% from this replay is **not** comparable to the endurance Section 4 matched-% (different rule, replay vs live). Only the paired NET is the result.

**Post-processing parity.** The live `ALL.TXT` is post-`IsPlausibleMessage` and per-cycle text-deduplicated. QA states, with FILE:LINE, whether `DecodeTwoStageAsync`'s output already has both applied. If not, the harness applies the **same** filter and dedup to both arms, in memory, before matching. Either way, both arms are treated identically and the report says which.

## 5. Estimand and interval — QA §3.2 and §3.4

For included cycle *i*: `W_i` = WSJT-X decodes in the live `ALL.TXT` for that cycle (counted as Test B counts its `ws` rows); `M_off,i` = matched decodes of the OFF arm; `M_on,i` = matched decodes of the ON arm, **the union of batch 1 and batch 2** (what the operator eventually sees), matched one-to-one as a single set.

- **NET (pp)** = 100 × Σ(`M_on,i` − `M_off,i`) / Σ `W_i`. Same denominator family as Stage 2's +8.89 pp ("pp of WSJT-X's decodes").
- **Interval:** 95 % percentile CI from a **non-overlapping block bootstrap** over the frozen ordered list: block = **40 consecutive included cycles** (≈ 10 min), the last partial block kept as its own block, numerator and denominator resampled together (ratio estimator), B = 10 000, seed 20261001. Registered: 40. Reported but not used for the verdict: the same CI at block 20 and block 160, and the autocorrelation of `d_i = M_on,i − M_off,i` at lags 1, 4, 40.
- **Also reported (descriptive, no bar):** NET split by Test B's SNR bands A–D; ON-arm batch-2 decodes per cycle; matched split by batch.

## 6. Pre-registered rows

**Validity (any FAIL ⇒ no verdict is issued; the report says which row and stops there):**

| Row | Predicate (as code) |
|---|---|
| V1 | DLL actual == pinned, start and end, all three runs (OFF, ON, ON-repeat) |
| V2 | flags as in §2 read back in every run; `selection.json` SHA identical in every run |
| V3 | 0 access violations, 0 contained exceptions, 0 non-zero exits, every run |
| V4 | per included cycle, ON batch-1 numeric multiset (freqHz, dt, snr) == OFF multiset; **PASS iff N/N** (S1's property, on this corpus) |
| V5 | ON-arm residual passes abandoned ≤ 5 % of included cycles (abandoned passes count as 0 extras, which is the live behaviour; above 5 % the answer is a runtime result, not a decode-rate one) |
| V6 | ON-repeat: a second fresh ON process over the **first 160 included cycles**; per-cycle union multiset identical to the main ON arm on **160/160** |

**V6 replaces QA's proposed OFF-vs-OFF negative control (§3.5): OFF-vs-OFF is OUT.** Flag-OFF identity across fresh processes is already shown four times (182 native cycles; 161 E1 twice; §5g 161/161). A fifth cannot fail in any way that changes this verdict, so it is decorative (HK-025(k)). What is **not** shown on this corpus is that the flag-ON path, with its deadline and 8 workers, gives the same answer twice. That is the only run-to-run noise the bootstrap does not capture, and V6 measures it for ≈ 15 min of CPU.

**Verdict (exclusive; uses the Stage 2 ruling's replication bar of ≥ 1.0 pp, set 2026-09-28 §3(b), NOT re-tuned):**

| Row | Predicate |
|---|---|
| D1 REPLICATED | `CI_lo(NET) ≥ 1.0` |
| D2 NOT REPLICATED | `CI_hi(NET) < 1.0` |
| D3 INCONCLUSIVE | otherwise |

**HK-025(k), stated by me so QA can check it:** the bar discriminates the question asked. If the extras are not WSJT-X-corroborated, `M_on` ≈ `M_off` and NET ≈ 0, giving D2. It does **not** discriminate "corroborated" from "real". The not-corroborated share is only an upper bound on false positives (Test B wording), and that half of §8.2 is not decided by this run. Test B's 97.1 % on 161 cycles makes D1 the expected outcome. The informative output is therefore the size of NET and its CI over a whole night, not the pass/fail. I am keeping the bar because it was registered before this corpus existed. A bar raised after Test B would be tuned to the data.

**FP watch (a mechanical flag, not a verdict):** per SNR band, the not-corroborated rate of batch-2 decodes vs the batch-1 control rate, Wilson 95 % CIs as in Test B. **FLAG** a band iff `CI_lo(batch-2 not-corroborated) > CI_hi(batch-1 not-corroborated)`. A flag goes to the Architect and the Captain; it does not change D1–D3.

**Replay fidelity (descriptive):** the OFF arm's per-cycle decode count vs the live OpenWSFZ `ALL.TXT` (`…-gathered/owsfz/ALL.TXT`), counts only. This is the analogue of Stage 2's 0.76 pp. It cancels in the NET and is reported so the reader can see it.

## 7. Run order and machine

1. Freeze and hash `selection.json`, then commit the harness changes and this spec's row predicates as code (`GUARDED` list as in Test B). **No decode before the commit.**
2. OFF arm (≈ 0.6 h), then the ON arm (≈ 6.5 h), then ON-repeat on 160 cycles (≈ 15 min). Each is a fresh process. Detached and supervised (HK-013, HK-023), with teardown and an orphan check (HK-019).
3. **CPU (constraint 5):** a sampler every 30 min records any `dotnet`/`testhost`/`MSBuild`/`jt9`/`wsjtx` process other than the harness. Any hit is reported. It does not invalidate the NET, because outcomes do not depend on timing except through V5, which is gated. Developer and Engineer idle for the window. **WSJT-X closed** (it was resident live; both arms are replayed without it, so the NET is unaffected. Say so, QA §3.6).
4. The open pre-flight item `wsjtx_ini_dial_freq_matches_daemon: false` is inherited, not resolved. Name it in the report's limits.

## 8. Output and privacy

Per-cycle CSV: `stamp, W, n_off, n_on_b1, n_on_b2, M_off, M_on, M_on_b1, M_on_b2`, per-band counts, and not-corroborated counts. **Numeric only.** No message text, callsign or text-derived hash, in any file (HK-037). The report and `rows.json` sit under `qa/rr-study/results/2026-10-0x-sub-feas-offline-onoff-replay/`, with the prose NFR-021-scanned before commit.

## 9. What a D1 licenses, and what it does not

- **D1:** the Stage 2 net effect replicates on a second night of the same band and chain, on the native build, through the managed two-stage path. Citable as *"NET +x.xx pp [lo, hi], one 40m night, replay vs replay, Test B match rule"*.
- **Still open after any outcome:** band replication; false-positive rate beyond the not-corroborated upper bound; live-path behaviour (plausibility and the real-time budget on another machine); multi-pass. **Flag default ON, and batch 2 reaching the answerer, remain the Captain's decisions.** This run informs them; it does not make them.
- 🛑 Do not compare this NET's point value to +8.89 pp as if it were the same instrument: the match rule (text vs Stage 2's payload), the build (native vs Python fit) and the corpus all differ. Report both side by side, labelled, without a difference test.

## 10. Architect predictions (blind; scored at ruling time per the ledger's rule 1)

| # | Prediction | P | Class |
|---|---|---|---|
| OR1 | Verdict D1 | 0.85 | H |
| OR2 | NET point estimate within [4.0, 14.0] pp | 0.60 | H |
| OR3 | V4 passes N/N | 0.95 | C |
| OR4 | V6 passes 160/160 | 0.85 | H |
| OR5 | No band raises the FP-watch FLAG | 0.70 | H |
