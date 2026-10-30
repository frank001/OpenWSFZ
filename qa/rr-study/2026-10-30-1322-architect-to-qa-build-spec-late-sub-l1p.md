# `LATE-SUB L1′` build spec: a late subtract-and-decode round (primary decoder only), behind a setting, default OFF

**From:** Architect · **To:** QA (for the Developer, HK-015) · **Date:** 2026-10-30 13:21:55Z (`date -u`) · **Branch:** `arch/late-sub`
**Authority:** the Captain, 2026-10-30: "go, write the build spec". This follows the L1′ ruling (`qa/rr-study/2026-10-30-1318-architect-late-sub-l1p-ruling.md`, `d9e28caa` + `58e8f4bc`): **L1′-GO** on `20261022_1949`, NET +0.742 pp [0.621, 0.859], ΔU′_ta 0.0063 [0.0013, 0.0125], H-SHARE 0.
**Base:** `main` `c2c85c45` (v0.67). **This is a `src/` change and needs a separate Developer session (HK-011)**, QA's HK-039 review before any acceptance run, and `pre_merge_check.py` before any push (HK-006). This document itself is docs only (`git diff --stat origin/main -- src/ native/` is empty).

---

## §0. What is being built, in one paragraph

After the coherent fallback's batch is out, on **Deep**, the decoder runs **one more subtraction round**.
- **Buffer:** the cycle's last residual buffer B (R3 if the third pass ran, otherwise R2).
- **Subtracts:** the decodes of batch 3 and batch 4.
- **Decodes:** the result once with the **primary decoder** (the existing `SubtractionPass.RunThirdPassAsync`).
- **Publishes:** its new decodes as **batch 5**.

There is **no extra fallback run** and **no `native/` change**. The round is off unless a new setting turns it on. It obeys the cycle's 13 s budget through the third pass's existing deadline and reserve mechanism. **The QA harness `LateSub.cs` in mode `l1p` (`b7c17464`, `qa/refset`) is the reference implementation:** §3's B-EQ row requires the build to reproduce its published rows.

## §1. Behaviour (requirements)

**R1. The setting.** New key **`decoder.lateSubtractionRound`** (bool).
- Absent means `false`. It follows the config overlay (HK-035), like `decoder.coherentFallbackResidualUngated` (`Ft8Decoder.cs:246–257`): a volatile field, set by the daemon before the first cycle.
- **OFF ⇒ every code path is the code as it is today** (B-OFF checks this byte for byte).

**R2. When it runs.** All of these must hold:
- (a) the setting is ON;
- (b) the depth is **Deep** (`deep` at `Ft8Decoder.cs:940`). On Normal the setting has no effect, and the docs say so;
- (c) the coherent fallback ran in this cycle (`fallbackReady`, `:948`), whether or not it published anything;
- (d) the residual pass was not abandoned and did not fail.

If any of these fails, the round is **skipped**, counted and logged (R6). It also does not run when pass 0 decoded nothing (`:951–956`).
- 🔴 **The study covered Deep with the fallback ON only** (the station's and the reference's configuration). Any other combination is out of scope. The gate in (b)/(c) keeps the build inside the measured envelope.

**R3. Its inputs** (as in the harness, spec `8152d4ce` §1):
- **Buffer B:** the third pass's residual if the third pass ran to completion and produced one; otherwise the residual pass's buffer (`report.Residual`). This is the same choice the harness made (R3 in 708 of 800 cycles on the verdict night, R2 in 92). **Read-only:** the fallback may still hold references to this array (`:1062–1064` comment), so the round takes its own copy, or relies on `RunThirdPassAsync` not mutating its input. The Developer states which, with the file:line.
- **Fit list:** the cycle's **batch-3 natives** (`third.NewResults`) ∪ the **batch-4 natives that were published**. Those are built as the fallback builds them (`:1114`: `FreqHz = round(OutFreqHz)`, `Dt = OutDtS` unrounded, `Snr`, `Message`), restricted to texts that `MapNative` published in batch 4. The harness's fit list is the reference; if the "restricted to published" reading differs from it, B-EQ will show it.
- **alsoKnown:** batch-1 natives (`native`) ∪ batch-2 natives (`newFromResidual`).
- **Refusals:** fit entries that fail `IsReencodable`/`EncodeMessage` are skipped exactly as in the third pass (`SubtractionPass.cs:331–343`, `:498`). The count goes in the log line.

**R4. The call.** `SubtractionPass.RunThirdPassAsync(_interop, B, fit, alsoKnown, EffectiveSubtractionThreads, _logger, _apConstraints, SubtractionCycleBudget - sw.Elapsed, ct)`.
- This is the same budget arithmetic as the third pass (`:1014–1016`). Its own deadline and reserve logic (`SubtractionPass.cs:316–323, :358–420, :455`) is the time guard: **all-or-nothing**, so an abandoned round publishes nothing.
- No new budget constant is introduced.
- The outcomes `SkippedNoNew` / `Abandoned` / `Failed` are counted like the third pass's (`:1018–1032`).

**R5. Publication.** New decodes go through `MapNative(…, PathResidual)` with the same per-cycle text de-duplication set. They are handed off as **batch 5** through a new callback, only when the batch is non-empty.
- **Ordering:** after the fallback's batch has been handed off, so batches 1–4 and their timing are unchanged.
- **Hash table:** the round's unpack is the cycle's last hash-table access, after the fallback's (R9 of COH-FALLBACK). The Developer confirms this ordering holds under the decode gate.
- **The daemon's batch consumers** (decode panel, `ALL.TXT`, PSK Reporter, the batch-number fields in logs) must accept batch 5. The Developer lists every consumer that switches on the batch number, with file:line, and handles each one.

**R6. The log line,** one per cycle while the setting is ON (Deep):
`Late subtraction round: outcome={ran|skipped-<reason>|abandoned|failed|no-new}, buffer={R3|R2}, fit={n}, refused={n}, new={n}, published={n}, startMs={…}, elapsedMs={…}, endMs={…}, batch=5, batch5PublishMs={…|-1}`.
- `startMs`/`endMs` are measured on the decode's own clock (as `fbStartMs`). These fields feed §3/§4's timing rows.
- Counters go beside `_thirdPass*`.

**R7. Version and docs.**
- `VERSION` 0.67 → 0.68, in every place the gates check.
- `REQUIREMENTS.md`: a new FR at the next free number (after FR-101), covering the setting, R2's gate, batch 5 and the budget rule.
- An OpenSpec change `late-sub-round` (proposal, tasks, spec delta) and a changelog row.
- Docs state: Deep only; it needs the fallback ON; default OFF; turning it ON starts a new era for live figures.

**R8. Tests (unit).**
- OFF is a no-op.
- Each R2 skip reason.
- An abandoned or failed round publishes nothing and does not throw.
- Batch-5 numbering and ordering.
- The fit list is batch 3 ∪ published batch 4, with unrounded Dt.
- The refusal count.

## §2. What is NOT in this build

- No fallback on B or on R4 (LATE-SUB's C and L2 were ruled COST).
- No change to batches 1–4, the T1 gate, R-F4 or multi-set.
- No payload subtraction (#273): the refused 9.5 % stay refused.
- No default ON. That is the Captain's decision after §4, and it starts a new era.

## §3. Acceptance rows, refset night (PC, `20260925_2010`, 1,200 cycles, one process from cycle 1, station stopped)

| row | predicate (mechanical) |
|---|---|
| **B-NAT** | `git diff --stat c2c85c45 -- native/` is empty, and the DLL SHA-256 equals the pin `1ba8dc3d…` |
| **B-OFF** | setting OFF: the published output (batches 1–4, every field) is byte-identical to the continuous `main` arm `_qa-scratch\coh-gate-r-f4\raw_main\main`, 1,200 of 1,200 cycles |
| **B-EQ-1** | setting ON: batches 1–4 are identical to B-OFF's in all 1,200 cycles |
| **B-EQ-2** | setting ON: batch 5 equals the harness's L1′ published rows (`late-sub-l1p` refset leg, `b7c17464`) cycle by cycle, **on plain (non-hashed) text: 0 cycles differ**. Hashed-text count differences are listed one by one and allowed, because the harness bracketed the hash state and the product does not (spec A1 D3) |
| **B-AB** | residual pass, third pass and fallback abandoned in ON = in OFF (the round runs after them, so it must not move them); the late round's own abandoned count is reported |

**Descriptive (PC):** the late round's `elapsedMs` median, p90 and max, and `endMs` max, against the budget.

If B-EQ-2 fails on plain text, stop and report the first differing cycle. QA and the Developer then reconcile against the harness. **Neither side's version is assumed right.**

## §4. Third acceptance night (sol, `20260930_1930`)

**The night** is QA's candidate (2026-10-30). Its same-band check is done and passed: dial 7.074 MHz in 4,300 of 4,300 capture rows and in all 129,608 WSJT-X lines over 4,296 cycles, with 0 mismatches. It uses the Voicemeeter capture chain, like the station today and like `20261022_1949`, and it was not a tuning night for this programme.

**Why sol.** sol is the tight machine: its fallback ends at about 11.1 s, against 5.8 s on the PC. Running the verdict there makes **NET already include whatever yield the budget cuts off**, so timing is priced in the verdict, not argued beside it.

**Setup.**
- sol's `libft8.so` is built from the Developer's exact commit, and its SHA-256 goes in the freeze commit. With an empty native diff it should equal `488bfa0b…`; report it if not.
- **Arms:** A = setting OFF, B = setting ON. Everything else is identical: Deep, `nhard` 24, OSD fix, multi-set ON, `Both`, R-F4 OFF, the same thread count and budget setting.
- **Original arm:** 200 cycles, for the U′ classes, with the HK-026 condition exactly as in R-F4 A1.4. If any unconfirmed batch-5 output falls in `untestable_class`, run the Original arm on the other 600 cycles, re-freeze from all 800, and only then compute the U rows (about +1.5 h on sol).

**Selection:** stride 3, offset 1, the first 800 slots (R-F4 A1.4's rule). Outage slots are dropped after selection and counted. The selection, the classes, the `.so` hash, the build commit and the analysis code go in a **freeze commit made before the first replay output**.

**Rows** (cycle bootstrap B = 2000, seed 20261030; bars below):

| row | predicate |
|---|---|
| **V-3N-AB** | residual pass, third pass and fallback abandoned = 0 in **both** arms. If it fails, re-run both arms with the budget lifted and read the rows from that pair (R-F4 A2.3) |
| **V-3N-REF** | n_ref is derived and reported; WSJT-X lines are present in ≥ 790 of 800 cycles |
| **N-GO** | `CI_lo(NET_B−A)` ≥ BAR_G |
| **N-STOP** | `CI_hi(NET_B−A)` < BAR_G |
| **U-OK** | `CI_hi(ΔU′_ta)` ≤ U_bar_G |
| **U-FAIL** | `CI_lo(ΔU′_ta)` > U_bar_G |
| **H-SHARE** | hashed or unencodable share of batch-5 outputs > h |

**Verdict:**
- **ACCEPT-3N** iff N-GO and U-OK and H-SHARE does not fire.
- **FAIL-3N** iff N-STOP or U-FAIL.
- **OPEN-3N** otherwise.

Only ACCEPT-3N lets the Captain be asked about merging and, separately, about default ON.

**Timing on sol (reported; it vetoes nothing, because NET already pays for it):**
- the late round's outcomes: ran / skipped / abandoned / failed, as counts and as a share of R2-eligible cycles; **corrected 2026-10-30T18:01:50Z (`date -u`), ledger E124: R6 has a fifth word, `no-new`; the outcome list, the denominator and the `elapsedMs` population are in `2026-10-30-1802-architect-late-sub-l1p-t2-4-ruling.md` §4;**
- `elapsedMs` median, p90 and max;
- `endMs` max against 13,000;
- **T-WARN**, a stated flag, not a row: fires if > 10 % of eligible cycles abandon.

**Bars (HK-038).** BAR_G 0.5 pp, U_bar_G 0.021 per cycle on tested_absent, h 0.5.
- Their source: ratified for COH-GATE-G on 2026-10-28, re-used for LATE-SUB ("agreed", 2026-10-29T19:22:19Z) and for L1′ ("go with your recommendations"), and now carried into this build under "go, write the build spec".
- The population is the same: the `main` lineage, the station band, the same U′ instrument (blob `66dd1e94…`).
- **A check against data on file:** this lever's own verdict night gave CI_lo 0.621, so a sol night that loses about 0.12 pp to night-to-night variation or the budget would fail N-GO. OPEN-3N or FAIL-3N is a live outcome, not a decorative one.

## §5. Order and cost

1. QA's (k) review of this spec.
2. The Captain's go for the Developer session.
3. Developer: R1–R8, then a commit.
4. QA: HK-039 review record.
5. QA: §3 on the PC (about 2 × 2.3 h at today's harness speed; the product alone is faster).
6. The Captain wakes sol.
7. QA: §4 freeze, then the arms (about 7.9 s per cycle × (800 + 800 + 200), about 4 h).
8. QA: report, then my acceptance ruling.
9. **Merge:** `pre_merge_check.py` before any push (HK-006), and the Captain's sign-off (HK-010).
10. **Default ON:** a separate decision by the Captain, and a new era.

## §6. Predictions (Architect; scored at the acceptance ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| BL-1 | B-OFF and B-EQ-1 pass on the first Developer commit | 0.80 | C |
| BL-2 | B-EQ-2 (plain text, 0 cycles differ) passes on the first Developer commit | 0.55 | C |
| BL-3 | ACCEPT-3N | 0.55 | H |
| BL-4 | sol: late round abandoned in ≤ 5 % of eligible cycles | 0.60 | H |
| BL-5 | third-night NET point ≥ 0.6 pp | 0.50 | H |

**Reasoning.**
- **BL-2:** the fit-list reading ("batch 4 as published") is the likeliest place for the build and the harness to part.
- **BL-3/BL-5:** two nights gave 0.65–0.70 of the refset figure (about 0.74–0.80 pp). sol's budget can only remove yield, and CI_lo was 0.12 pp clear of the bar.
- **BL-4:** sol's fallback ends at 11.1 s at worst, but its median is lower. The round needs about 0.75 s median on the PC, and sol is slower.

🔴 **Bias check:** this is a build of a lever that has already passed once on a fresh night. The ledger says acceptance on another night is still a real test (R-F4's second night shrank to 0.70). ACCEPT is held at 0.55.

## §7. Amendment 1 (2026-10-30 13:25:56Z, `date -u`): QA (k) review `106980f8` adopted in full (F1–F5)

QA's review is `qa/rr-study/2026-10-30-1325-qa-to-architect-build-spec-late-sub-l1p-k-review.md`, verdict APPROVE WITH FIVE AMENDMENTS. These replace the named parts of §1 and §3.

**F1. R3's fit list is replaced** (ledger E120, mine).
- ~~"batch-3 natives (`third.NewResults`) ∪ the batch-4 natives that were published"~~
- **Now:** the fit list is **the natives behind the decodes `MapNative` published in batches 3 and 4**. That means the first occurrence of each text in the cycle, not already in `seen`, and `IsPlausibleMessage` true. Dt is the unrounded `OutDtS` and `FreqHz = round(OutFreqHz)`.
- `alsoKnown` = batch-1 natives ∪ the raw batch-2 natives, unchanged (QA confirmed it matches the harness).
- The Developer may add a `MapNative` helper that returns the natives it kept. This is the harness rule (`b7c17464`). My text took batch 3 raw and would have parted from it.

**F2. R3's buffer rule is replaced.** B is **whatever `CohFallbackAudioSelector.Select(...)` returns** (`:43–64`), the same call the fallback makes, so the two cannot drift:
- R3 if the third pass `Ran` with a residual;
- otherwise `report.Residual`, if the residual pass was neither abandoned nor contained and fitted at least one signal.

If `Select` returns the original audio, there is nothing to run the round on, so it is **skipped** (`skipped-no-residual`). R2(d) becomes part of this rule.

**R3 "read-only":** no copy is needed. `SubtractionPass.cs:425` clones, and the documentation at `:215` says the input is not modified (QA). The Developer cites both.

**F3. B-EQ-1 is replaced** (ledger E121, mine). The round's decodes enter the process-global hash table, so a later cycle can legitimately resolve a `<…>` token differently in ON than in OFF. LATE-SUB Amendment 1 D3 named this mechanism, and I did not carry it into the row. **New B-EQ-1:**
- (i) Up to and including the first cycle in which ON published a batch 5: batches 1–4 are identical to B-OFF's in every field.
- (ii) After that: identical **modulo hashed tokens**, meaning every `<…>` is wildcarded and the row counts are equal. Every cycle that differs only in a hashed token is listed.
- Any other difference stops the row.

B-EQ-2 already allows hashed differences and is unchanged.

**F4. R5 is replaced.** Batch 5 goes through the **existing** batch-number delegate (`onFallbackBatch`, `Ft8Decoder.cs:554, :1133`; the pump's staged delegate at `DecodePump.cs:166`) with the number 5.
- No new callback, and no change to `DecodeStaged`'s signature (`DecodePump.cs:45`).
- QA found no consumer that switches on a specific batch value:
  - `DecodePump.cs:166–168` routes every batch number other than 1 to `PublishSecondAsync`;
  - the QSO services test `BatchNumber > 1`;
  - `LateBatch` uses it only for logs.
- The four doc comments that say "2, 3 or 4" are updated.
- The FR gets one sentence on this: a late batch 5 is published to the panel, `ALL.TXT` and reporting, but can arrive too late to affect that cycle's TX decision, as batch 4 can today.

**F5. New row B-TOOL, before §3** (QA's own instrument, `qa/` only). Replay81/`FitProbe` must carry batch 5 before any §3 row is read:
- its staged callback;
- a `b5_n` column in `run.csv`;
- `nc_dump` kind 5;
- `StageProbe`.

QA also shows that, on `main`, the extended instrument's output is byte-identical to the current one's on the shared columns (B-OFF compares only those). QA estimates about 1 h.

**Smaller points adopted:**
- **R6's log line gains `fbEndMs`.** A cycle is **eligible** for the timing shares when the round started; "share of R2-eligible cycles" in §4 now reads "share of cycles in which the round started".
- **R8 gains a test:** the round's unpack happens after the fallback's, under the decode gate (hash-table ordering). This is a test, not only a Developer confirmation.
- **§5 cost:** §3 takes about 1.1 h per arm with the product alone (QA).

**Predictions:**
- BL-1..5 stay as registered. QA prices BL-4 at 0.45; that is noted, and my 0.60 is what will be scored.
- **BL-2 is scored on F1's rule** (the spec's rule from now on). The amendment came before any Developer code, so it is a spec change.
