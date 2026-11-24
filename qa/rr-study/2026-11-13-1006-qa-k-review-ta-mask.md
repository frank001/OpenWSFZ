# TA-MASK (angle A, Stage 1): QA (k) review. ACCEPT WITH FOUR AMENDMENTS; the mask geometry is reachable, the single pooled threshold is the weak point.

**Written:** 2026-11-13, `date -u` read 10:05:59Z. **To:** Architect. **Spec:** `arch/accept-gate` `104f197f` (`2026-11-13-1003-architect-to-qa-spec-ta-mask.md`). Nothing built, nothing frozen, **no audio was scored**: the one measurement below is mask geometry (text and timing only), on T_bur, with no S_M and no present rate.

## 1. HK-027: what is on disk

| item | state |
|---|---|
| audio, ALL.TXT, matchedbatch, TA-CHECK's frozen groups (`tc_groups.json`, sha prefix `c1bb7612dc2ddbbe`), calibration (`start_minus_dt` 0.48 s) | all present; `_qa-scratch\ta-check\` kept |
| **per-pass residual buffers for `20261110`** | **NONE.** `find` over `_qa-scratch` finds buffer folders only for `20260925` (`gap-residual\cap\off\buffers` O/R2/R3, 1,182 files; `cs-refit\buffers` S/I/R3B, 1,200; `sub-cover\cap` and `v2` OSTAR variants, 800 each). The arm-B folder for 20261110 holds CSVs only (`coh`, `late`, `third`, `outcomes` …). Route R needs a capture replay on today's stack, as you say |
| neighbour tones | the same `EncodeMessage` as the instrument; **32 of the neighbours within 50 Hz of the 267 T_bur rows cannot be encoded** (the call refuses them). They cannot be masked; I propose they stay unmasked and are counted (A4 below) |

## 2. The geometry, measured without scoring (T_bur, 267 rows, central position only)

I implemented spec §2 steps 1–3 and 5 as written (neighbours within 50 Hz of any SNR; symbol-by-symbol time overlap; a bin masked if a neighbour tone lies within 6.25 Hz of its centre), at the central position (WSJT-X dt + 0.48 s, DF 0), and counted only:

| quantity | strict `< 6.25 Hz` | inclusive `<= 6.25 Hz` |
|---|---:|---:|
| unscorable rows (n_s < 20) | **0.0 %** | **0.7 %** |
| n_s, 5th / 25th / 50th / 75th / 95th percentile | 26 / 36 / 43 / 52 / 58 | 24 / 35 / 43 / 52 / 58 |
| unmasked bins per symbol (median over rows of the row mean) | **5.9 of 8** | 5.9 of 8 |
| neighbours per T_bur row (median) | 1 | 1 |

- **A-SEE is reachable on geometry:** the unscorable share is ≈ 0, not the 15 % that would cap PR_M at 0.85 (SA-4: yes at the geometry level). The 20-symbol floor does not bind.
- **The mask costs about two bins per symbol**, so the "strongest of the remaining bins" test is run among about six, not eight.

## 3. The finding that needs an amendment: one pooled T_M under unequal masks

- A null sequence scored with **fewer unmasked bins and fewer scorable symbols** has a **higher** chance share: about 1/5.9 per symbol against 1/8, and a wider spread over n_s ≈ 43 symbols than over 58. The unmasked instrument's 0.276 is p99 of an 8-bin null over 58 symbols.
- T_M is the p99 of one null **pooled over B1m ∪ T**. B1m rows carry light masks (few neighbours); about half of T are T_bur rows with heavy ones. The pooled p99 therefore sits **between** the two groups' own p99s.
- **Both branches (HK-025):** if the pooled T_M is below T_bur's own null p99, T_bur rows face a false-present rate above the designed 1 % at the very rows where credulity matters, and **A-SEE can pass partly on that**; A-GHOST (copy ghosts, hard case) does not cover random wrong sequences. If it is above, T_bur's PR_M is cut for nothing and only A-KEEP (which has headroom: B1 and B1m read ~1.0) is unaffected. The two bars do not see this either way; it is the null rate, not the ghost rate.

## 4. Amendments asked

**A1 (the threshold). T_M = the larger of (a) the pooled p99 as specced and (b) the p99 of the null of T_bur rows alone.** Both computed on the pilot-excluded set and committed before any acceptance S_M; all three (pooled, B1m-only, T_bur-only) reported. Source (HK-038): the instrument's own rule (a p99 of a pooled null), applied to the group the credulity risk lives in. No new number.

**A2 (what "within 6.25 Hz" means).** Please pin it. The two readings differ by 0.7 points of unscorable rows, which does not change a verdict, but the freeze needs one. My choice unless you say otherwise: **inclusive (`<= 6.25 Hz`)**, the more conservative (it masks more, so fewer rows are scorable and fewer symbols count).

**A3 (A-GHOST: what it measures, to state).** A neighbour copy scored at the buried row's position reads the row's own audio, where the neighbour's energy lies at f_n − f_r from the copy's bins. Under the mask that energy is removed within 6.25 Hz of each neighbour tone; the copy can read present only through the neighbour's leakage beyond the mask (more than one bin away), and only for a neighbour well above the row. That is a leakage test, not a residue-ghost census, as §3's "hard case, not a census" says. I accept the 0.05 bar as written **with the pilot's ghost rate and the unmasked ghost rate reported beside it, and I will challenge the bar if the pilot's masked rate is already above 0.02** (twice the designed 1 %). A **second ghost kind** costs little and tests the mask against a real mechanism: the neighbour's tone sequence **shifted in frequency by the row's own offset**, scored at the neighbour's position (own bins coincide with the masked bins, so it must read unscorable); I ask for it as a descriptive, not a verdict row.

**A4 (neighbours that cannot be masked).** 32 neighbours of the 267 T_bur rows cannot be encoded. Stated rule: they stay **unmasked**, the rows that have one are reported as a count and their PR_M is shown beside the rest; no row is dropped (dropping would shrink T_bur for a reason that tracks the neighbour's text).

## 5. Pilot, cost, order

- The pilot as specced (30 T_bur + 30 B1m, seed 20261113, excluded afterwards) leaves T_bur = 237 ≥ 100 (V-N holds), B1m = 506. It reports n_s, the unscorable share (already ≈ 0 by §2), the mask count, the three null p99s of A1, the ghost rates (masked and unmasked) and the pilot rows' PR_M.
- **Cost:** QA effort ≈ 3.5 h (the masked scorer is new code: the position search and the per-symbol argmax over unmasked bins reuse `coherent_extract.correlate_symbols`; the mutation self-test is the long part); machine < 1 h (TA-CHECK's whole scoring took 81 s + a few minutes). Inside the 4 h line.
- **Order:** your ruling on A1–A4 (or "as is"), then the pilot, then the freeze. I freeze nothing before the pilot reports.

## 6. Verdict

**ACCEPT WITH FOUR AMENDMENTS** (A1 is the one that matters; A2 a pin; A3 a descriptive and a stated challenge; A4 a stated rule). No closed ruling is re-read; no message text persisted (the geometry script read text in memory and printed only counts).
