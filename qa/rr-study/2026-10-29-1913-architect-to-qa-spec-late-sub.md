# `LATE-SUB`: subtract what we decode late, and give the fallback candidates from the subtracted audio. An offline lever study

**To:** QA (or the Engineer, by QA's choice) · **From:** Architect · **Date:** 2026-10-29 19:13:31Z (`date -u`) · **Branch:** `arch/late-sub` (off `origin/main` `c2c85c45`)
**Authorised:** the Captain, 2026-10-29: *"go, write the LATE-SUB spec"*. Docs only; `git diff --stat origin/main -- src/ native/` is empty.
**Status:** an **offline lever study**, the pattern of COH-GATE-G → R-F4. A GO authorises only a **build spec** (Developer, HK-011), which would carry its own sol timing rows and a second night. No default changes here.

---

## §0. Why, and what it reuses

**The pointers** (NR-TAX ruling `qa/rr-study/2026-10-29-1818-architect-nr-tax-ruling.md`, `arch/gap-residual` `122a9433` + correction `36ec16c6`; GAP-RESIDUAL ruling `2026-10-29-1744`, `4b8d8b7a`). All are associations, on night `20260925_2010`, cycles 1–400:

| pointer | size | what the code does today |
|---|---|---|
| **CU-d**: stronger co-channel neighbour we decoded but never subtracted, batch-3/4 part | 221 rows, **1.82 pp**; loss rate 72 %, enrichment 16× | subtraction removes only batch-1 and batch-2 decodes (`SubtractionPass.cs:299–301`). The third pass's own decodes (batch 3) and the fallback's (batch 4) are never subtracted |
| **CU-u**: stronger co-channel neighbour we never decoded | 228 rows, 1.88 pp; 106 of them beside a **reachable** miss | — |
| **never offered** (GAP-RESIDUAL D6-R): decodable by the fallback on R2/R3, but no candidate there | 153 rows, ≤ **1.26 pp** beyond R-F4 | both fallback runs reuse the candidate list from the first decode of the **original** audio (`Ft8Decoder.cs:681`, `:1072–1073`, `:1079`) |

**The lever, in two parts, measured nested:**
- **Arm C (COH-RES-CAND):** run the fallback once more, on the cycle's last residual buffer (R3, else R2), with the candidate list **from that buffer's own decode**.
- **Arm L (LATE-SUB) = C + one more round:** subtract the cycle's batch-3, batch-4 and arm-C decodes from that buffer, giving **R4**. Decode R4 with the primary decoder. Then run the fallback on R4 with **R4's own candidate list**.

`L − C` is what the extra subtraction adds.

**Not a closed family (E110).** The closed "no passes" rule is the **native** `K_MAX_PASSES` / candidate-budget family: C.1 (July), RC2/RC4 (2026-08-07), and the June three-pass SIC `25fc4d9d`. A subtract-and-decode round is SUB-FEAS's family, licensed 2026-09-28 and shipped twice: the residual pass and #240's third pass.

**Everything runs on the product's own code, in `qa/`. No `src/`/`native/` change:**

| step | product code it calls (reachable under Replay81's `HasInternals`, assembly `Ft8.FitProbe`, `InternalsVisibleTo`) |
|---|---|
| subtract a list of decodes from a buffer and decode the rest | **`SubtractionPass.RunThirdPassAsync(interop, buffer, signalsToFit, alsoKnown, …)`** (`SubtractionPass.cs:220–252`; class `internal static`, `:33`). It is the shipped third pass: it copies the buffer, fits and subtracts **only** the given signals (re-encodable ones, `:331–343`), decodes, and returns decodes new against both lists |
| a candidate list for a buffer | `CohFallbackSnapshot()`, taken **on the thread that ran `DecodeAll`, with no native decode between** (`Ft8LibInterop.cs:1534–1544`). Replay81's `StageProbeInterop` wraps `DecodeAll`, so it can take the snapshot right after the inner call returns |
| the fallback on a buffer | `CohFallbackRun(pcm, snapshot, budgetMs, workers, multiSet, ct)` (`IFt8NativeInterop.cs:272`), as the product calls it (`Ft8Decoder.cs:1177`) |
| publication | the product's mapping: `CoherentFallbackSelector.Select`, unpack, per-cycle text de-duplication, `IsPlausibleMessage` (`Ft8Decoder.cs:1085–1102`, `:728–760`). QA's COH-GATE-G "full offline publication" code reproduces it (V3 below) |

## §1. Corpus, build, machine, configurations

- **Night `20260925_2010`, the frozen 1,200-cycle refset selection** (`81372df5`; COH-GATE-G and the R-F4 acceptance used it).
  - **TRAIN = cycles 1–400**: the cycles the pointers came from. Descriptive only.
  - **TEST = cycles 401–1,200**: the verdict.
  - Nothing in §2 is tuned. The design is fixed in this document, before any datum.
- **Build: `main` `c2c85c45`** (v0.67). DLL SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` at the start and end of every process.
- **Config as the station:** Deep, `nhard` 24, multi-set ON, `coherentFallbackAudio` absent (`Both`), 8 threads.
- **Two configurations, because the Captain's R-F4 choice is open:**
  - **OFF** (`decoder.coherentFallbackResidualUngated` absent) is the **verdict** configuration, being the shipped default;
  - **ON** is reported beside it with the same rows, descriptive.
  - In each configuration, the new fallback runs apply the gate **as that configuration applies it to a residual-audio run**: T1 in OFF, ungated in ON (R-F4).
- **Machine: the PC**, station daemon stopped. Timing figures are the PC's (§4 T-rows), and the sol question belongs to a build spec.

## §2. Arms (exact; one process per configuration, cycles in order)

For each cycle, inside the same process, **after** the product's own decode of that cycle (batches 1–4, exactly as shipped):

1. Let `B` = the fallback's residual buffer of the cycle, as `CohFallbackAudioSelector` chose it (R3 where the third pass ran, else R2; **no arm C/L work in a cycle at level O**). Take `snap(B)` = the snapshot from the `DecodeAll` call that decoded `B`, captured by the wrapper (§0).
2. **Arm C:** `CohFallbackRun(B, snap(B), …)`. Its rows are merged and published by the product's rules **after batch 4**, against everything already published in the cycle (payload and text de-duplication). They are **batch C**.
3. **Arm L:** `RunThirdPassAsync(interop, B, signalsToFit = batch 3 ∪ batch 4 ∪ batch C, alsoKnown = batch 1 ∪ batch 2, …)`.
   - Batch-4 and batch-C rows enter as `Ft8NativeResult` built from their published text, dt and freq. Hashed and short texts are skipped by the product's own `IsReencodable`; count them.
   - This yields R4 (the returned `Residual`) and its new primary decodes, **batch L1**.
   - Then `CohFallbackRun(R4, snap(R4), …)` gives **batch L2**.
   - L1 and L2 are published after batch C by the same rules.
4. The arm outputs are cumulative: **C** = product + batch C; **L** = product + batch C + L1 + L2.
5. **Budgets:** the extra calls run **unlimited** offline, so that the yield is measured without abandonment. Their wall time is recorded (§4 T-rows).

**Baseline:** the product's own batches 1–4 in the same process. Row V1 checks them against the records on file.

## §3. Validity rows (strict order; any failure ⇒ §4's verdict rows VOID; report the gap)

| row | check | pass | source of the bar (HK-038) |
|---|---|---|---|
| **V0** identity | DLL SHA-256 = the station pin at the start and end of each process | exact | the deploy record |
| **V1** baseline | in each configuration, the product's batches 1–4 equal the R-F4 acceptance arms (OFF = QA's continuous one-process `main` arm, B-OFF; ON = the build's ON arm). **Per cycle** (outcome fields; hashed text by count, as R-F4 KB2) if those arms' per-cycle outputs are still in `D:\Projects\claude\_qa-scratch\coh-gate-r-f4\`. **Otherwise on the aggregates**: `acceptance.json` holds aggregates only (2.5 KB). **OFF check figures**: TRAIN batch 4 published 1,350 and corroborated 9,931 / 12,124; TEST batch 4 published **2,891** and corroborated **18,844 / 23,158**. Say which form was used | exact | `qa/rr-study/results/2026-10-28-r-f4-acceptance/acceptance.json`; COH-GATE-G TEST report line 16 (`659af1b7`); GAP-RELOCATE 0b |
| **V2** the round is the product's | in every cycle where the third pass ran, calling `RunThirdPassAsync(R2, batch 2, batch 1)` offline reproduces **batch 3** exactly (freq, dt, SNR, count; text with the hash state saved and restored, as GAP-RESIDUAL A2) | exact | design: the offline round must be the shipped one, not an approximation |
| **V3** publication | the offline publication code, given the product's own fallback rows, reproduces the published **batch 4** of every cycle | exact | COH-GATE-G V3 (QA reproduced batch 4 in all 400 TRAIN cycles) |
| **V4** snapshots | `snap(B)` is captured in every cycle at level R3 or R2, and `snap(R4)` in every cycle where arm L decoded R4; `CohFallbackMakePlan` parses each. **Also state whether the residual pass's `SetDiagnosticsEnabled(false)` (`SubtractionPass.cs:443`) affects what the snapshot holds**, and assert it in a unit-level check on 5 cycles | 100 %, and the switch answered | design; QA's (k) review answers the switch question |
| **V5** no abandonment | 0 abandoned residual, third-pass or fallback runs in the product's batches, in both configurations | 0 | GAP-RESIDUAL 0f, this machine and night |

**Pilot:** V1–V4 are run first on cycles 1–40. A failure there STOPS the study before any TEST cycle is run.

## §4. Measures and verdict (TEST, cycles 401–1,200; OFF configuration decides)

**Metric instruments, unchanged from COH-GATE-G / R-F4:**
- **NET** = (WSJT-X decodes corroborated by the arm − by the baseline) / `n_ref` (23,158 on TEST), in pp, outcome matching;
- **ΔU′_ta** = the change in unconfirmed tested_absent outputs per cycle (the U′ instrument);
- **H-SHARE** = the hashed/unencodable share of the arm's added outputs.
- CIs: 95 % bootstrap by cycle, B = 2000, seed **20261030**.

**Bars: the Captain's, ratified for COH-GATE-G on this night and this build lineage** (freeze record `36df15b1`, "go with your recommendations"):

| bar | value |
|---|---|
| `BAR_G` | 0.5 pp |
| `U_bar_G` | 0.021 per cycle, tested_absent only |
| `h` | 0.5 |

**Verdict rows for arm L (exclusive, first match wins):**

| row | predicate | reading |
|---|---|---|
| **L-GO** | `CI_lo(NET_L)` ≥ 0.5 **and** `CI_hi(ΔU′_ta,L)` ≤ 0.021 **and** H-SHARE_L ≤ 0.5 | authorises a **build spec** (Developer, HK-011). That spec carries a sol timing row and a second-night acceptance |
| **L-COST** | `CI_lo(NET_L)` ≥ 0.5, but the U′ or H condition fails | the gain is real, and so is its cost. The Captain decides with the table in hand |
| **L-STOP** | `CI_hi(NET_L)` < 0.5 | not worth a build on this night |
| **L-OPEN** | otherwise | too wide to call |

**The same rows for arm C** (C-GO / C-COST / C-STOP / C-OPEN). They are reported, and they matter if L adds nothing over C: then only C would go to a build spec.

**Decomposition (descriptive):** `NET_C`, `NET_L − NET_C` with CIs; L1 against L2 (primary vs fallback in the new round); the count of batch-3/4/C decodes refused by `IsReencodable`.

**ON configuration:** the same table, descriptive. `NET` is measured against the ON baseline, so it is the gain **beyond R-F4**.

**TRAIN (cycles 1–400), descriptive:** the same figures, plus the mechanism check. Of NR-TAX's CU-d and CU-u rows and GAP-RESIDUAL's never-offered rows, how many does each arm publish (outcome-matched)?

**Timing (descriptive; the PC; no bar here):**
- **T1:** wall ms per cycle of arm C's extra fallback run, and of arm L's round (subtraction + decode + fallback): median, p90, max.
- **T2:** the same, added to the product's own fallback end time per cycle (B-AB measured 5.55 s on this PC), as an end-of-work time against the 13 s budget.
- **T3, for scale:** the product's own residual-pass and third-pass wall times on the same cycles on the PC. On sol, the residual pass ran 3.09 s median in RF4ON (series report, F2 row "residual pass, last daemon").

The sol question ("does it fit before 13 s with margin?") is the **build spec's** first row. It is not answered here.

## §5. Architect predictions (blind, before any datum; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| LS-1 | V0–V5 pass on the first build of the harness, without an amendment | 0.55 | C |
| LS-2 | L-GO (OFF configuration) | 0.40 | H |
| LS-3 | `NET_L` point ≥ 1.0 pp | 0.30 | H |
| LS-4 | C-GO (OFF) | 0.35 | H |
| LS-5 | `NET_L − NET_C` point ≥ 0.3 pp | 0.45 | H |
| LS-6 | `ΔU′_ta,L` point ≤ 0.021 | 0.70 | H |

**Reasoning.**
- The ceilings are association-based or position-forced: CU-d 1.82 pp, never-offered ≤ 1.26 pp beyond R-F4, overlapping. The product must also find the candidate itself. Most target rows are band D, where recovery is lowest (CU-d loss 80 % there).
- R-F4's TEST realised its forced ceiling in full (+2.10 against a TRAIN ceiling of +1.93), but that ceiling was a set of rows the product had **already decoded**. These ceilings are not.
- So the modal NET_L is 0.4–1.0 pp, which puts the 0.5 bar near the middle.

🔴 **Bias check:** both arms are "findable localised defect" levers, which the ledger finds over-called. L-GO is held at 0.40.

## §6. Output, cost, scope

- Report `qa/rr-study/results/2026-10-29-late-sub/report.md` (copied to the root results folder as the last step), in the order V-rows, verdict table (OFF), decomposition, ON table, TRAIN mechanism check, timing.
- Aggregates only; NFR-021 / HK-037. Per-message working files, and any stored buffers (pilot only), go in `D:\Projects\claude\_qa-scratch\late-sub\` and are deleted at job close. Committed locally on `qa/refset`; a push needs the Captain's go (HK-033).
- If unattended: supervised and detached (HK-013/HK-023).
- **Cost estimate:**
  - the harness: about 2–3 h (Replay81 extension; V2/V3 reuse GAP-RESIDUAL's and COH-GATE-G's code);
  - two one-process replays of 1,200 cycles with the extra work: about 1.5–2 h each, unattended;
  - the analysis: about 1 h.
  - About a day elapsed, PC only, no station.
- 🛑 **No `src/`/`native/` change, no rebuild, no live run, no push or merge** (HK-011, HK-014, HK-010). **If any step needs a product change** (for example, the snapshot is not readable after the residual decode), **STOP that arm and report; do not build it.**
- 🛑 Re-opens nothing: not the candidate-budget family (no cap or `K_MAX_PASSES` change), OSR, spectral locality, DENSITY, OSD in the fallback, or AP. A GO is a build-spec question for the Captain, never a default change.
- HK-025 in full. **Please give the (k) review before anything runs.** In particular:
  - V4's diagnostics-switch question;
  - whether batch-4 and batch-C rows can be handed to `RunThirdPassAsync` as `Ft8NativeResult` from their published fields;
  - whether the publication emulation (V3) covers rows published after batch 4.

## §7. Amendment 1 (2026-10-29 19:20:17Z, `date -u`): QA's (k) review D1–D6 adopted in full

QA review `qa/rr-study/2026-10-29-1919-qa-to-architect-late-sub-k-review.md` (`809e4f7e`, `qa/refset`): **approve with six amendments, no row refused.** All six are adopted. **Where this section and §1–§6 differ, this section governs.** Ledger E111–E114.

**QA's answers that settle open points:**
- **The diagnostics switch does not touch the snapshot.** `tls_diagnostics_enabled` is read only at `ft8_shim.c:1893` (the LDPC-failure LLR sums); candidate records are written unconditionally (`:1858–1882`) and copied out at `:2550–2552`. No product change is needed. D1 makes this a code assertion.
- **The per-cycle R-F4 arms are on disk:** `_qa-scratch\coh-gate-r-f4\raw_main\main` (continuous B-OFF), `raw\off`, `raw\on`, 1,200 rows each, with decode dumps. V1 is therefore **per cycle**.
- **Cost:** R-F4's arms took 72 min per 1,200 cycles. C adds about 0.5 s per cycle and L about 1.5–2 s, so about 1.9 h per process. OFF then ON is about 4 h, unattended.

**A1.1 (D1). V4 as code.** On 5 pilot cycles, decode `B` with the diagnostics switch on and off, from the same restored hash state. Assert the two snapshots are byte-identical and that `CohFallbackMakePlan` parses both. Assert that `snap(B)` and `snap(R4)` exist in every cycle where §2 requires them.

**A1.2 (D2, E113). The fit list is built as the product builds it, not from published fields.**
- I wrote "built from their published text, dt and freq". The published `Dt` is `Math.Round(nr.Dt, 1)` (`Ft8Decoder.cs:817`), up to 0.05 s off the fit anchor.
- **Batch 3:** from the offline `RunThirdPassAsync` call (V2).
- **Batch 4 and batch C:** from the captured fallback rows, as `Ft8Decoder.cs:1114` builds them: `FreqHz` = `(int)Math.Round(OutFreqHz)`, `Dt` = `OutDtS` unrounded.
- `RunCore` reads only `Message`, `Dt` and `FreqHz`.
- Pass `logger: null` and `deadline: null` to `RunThirdPassAsync`: unlimited budget, and no extra `Third pass:` lines for the harness's parser.
- Count the texts `IsReencodable` refuses.

**A1.3 (D3, E114). Every extra call is bracketed by the hash state.**
- The R4 `DecodeAll` and every unpack of an arm's rows add callsigns to the **process-global** hash table, and in one process that would move the next cycle's baseline and break V1. This is a standing fact I knew and did not apply.
- So: `HashStateSave` before a cycle's C/L work, `HashStateRestore` after it, as GAP-RESIDUAL's recheck and COH-GATE-G's extras did.
- **The report states the consequence:** the arms' outputs do not feed later cycles' hash state. A real deployment would resolve slightly more hashed messages in later cycles than this study credits, so the study is **conservative for NET**.

**A1.4 (D4, E111, E112). V1's figures and the selection pin, corrected.**
- **V1 is per cycle** against the on-disk arms: OFF against `raw_main\main`, ON against `raw\on`.
- If an aggregate is quoted: the continuous B-OFF arm gives **18,833 / 23,158** on TEST, not the 18,844 I cited. That figure is the COH-GATE-G TEST **process**, which started at cycle 401: 11 rows of hash-state difference, which is why every arm runs as one process from cycle 1. TRAIN 9,931 / 12,124 and batch 4 1,350 / 2,891 agree.
- **Selection pin: `selection1200.json`, sha `328c85d4…`**, the file the on-disk arms used. Its first 400 stamps equal GAP-RELOCATE's `selection400.json` (`42e09239…`). My `81372df5` was copied from GAP-RELOCATE's text without checking the 1,200-cycle file. QA states in the report whether `81372df5` names the same stamp list.

**A1.5 (D5). Publication emulation, as code.**
- For rows after batch 4, seed `seen` with **every** text handed to `MapNative` earlier in the cycle, including those the plausibility filter dropped (`seen.Add` precedes `IsPlausibleMessage`).
- This needs batch-2 and batch-3 natives, so **V2 also reproduces batch 2 offline**, not only batch 3.
- Batch C and L2 go through `Select` → unpack → natives → `MapNative`; L1 goes through `MapNative` only.
- **ON configuration:** apply the product's admission (`CohFallbackAudioSelector.Merge`, `:103`: a `GatedOut` row of a residual-audio run becomes `Admitted`) to the new residual-audio runs (C on `B`, L2 on R4), as code.

**A1.6 (D6). Scoring and U′ inputs, stated.**
- (a) The extra batches are matched to REF rows that the baseline left unmatched, with the same rule (frequency within 10 Hz, text equal, one-to-one, nearest first). NET is the combined matched count minus the baseline's.
- (b) The U′ instrument uses the refset classes frozen from the Original arm (QA names the file in the report) and reads the original WAV.
- (c) **Bar re-use: the Captain decides it explicitly with his run go.** `BAR_G`, `U_bar_G` and `h` were ratified for COH-GATE-G, a different lever on the same night and build lineage. The Architect asks him in the same message as the run go, and the report quotes his answer.

**A1.7 (QA's other findings, adopted).**
- Count level-O cycles (none expected: R3 382, R2 18 on cycles 1–400).
- Record the wall time of each extra step separately (fits, decode, fallback), as well as totals, for the build spec's timing row.

**Predictions.** LS-1 ("V0–V5 pass on the first harness build, without an amendment") is scored on the harness as built under this amendment. The amendment came before any harness was built, so it is a spec change, not a harness failure. LS-2..LS-6 are unchanged. None of D1–D6 moves NET or U′, except D3, which can only lower NET (conservative).
