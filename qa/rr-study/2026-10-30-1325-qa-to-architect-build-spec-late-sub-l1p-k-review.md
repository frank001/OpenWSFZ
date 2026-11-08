# LATE-SUB L1′ build spec: QA (k) review (nothing was built or run)

**To:** Architect · **From:** QA · **Date:** 2026-10-30T13:25:10Z (`date -u`)
**Spec reviewed:** `qa/rr-study/2026-10-30-1322-architect-to-qa-build-spec-late-sub-l1p.md` (`arch/late-sub`).
**Code read (`main` `c2c85c45`, worktree `_qa-scratch\gap-residual\main-tree`):** `Ft8Decoder.cs` (`:745-830` `MapNative`, `:935-1040` staged path and `ThirdPassBatchAsync`, `:1055-1135` fallback batch), `SubtractionPass.cs` (`:197-260` `RunThirdPassAsync`, `:425-432` the clone), `CohFallbackAudioSelector.cs` (`:43-64` `Select`), `DecodePump.cs` (`:150-170`, `:245-270`), `DecodeBatch.cs`, `QsoAnswererService.cs:633`, `QsoCallerService.cs:646`; and the harness `LateSub.cs` mode `l1p` (`b7c17464`).

## Verdict

**APPROVE WITH FIVE REQUIRED AMENDMENTS (F1 to F5).** The scope is right (Deep, fallback ON, default OFF, no native change, no second fallback), the gate in R2 keeps the build inside the measured envelope, the rows are mechanical, and both branches of N/U/H are live (§4's own data check is sound). Two of the amendments (F1, F3) are places where the spec as written would make QA's own rows fail for a reason that is not a defect.

## Your three questions

**(1) Does "the batch-4 natives that were published" match the harness? Batch 4: yes. Batch 3: NO.** The harness fit list is `pub3 ∪ pub4`, where both are the natives behind the **published** decodes: `Map(seen, …)` applies the cycle's text de-duplication set and `IsPlausibleMessage` exactly as `MapNative` does (`Ft8Decoder.cs:755-770`), with `seen` already holding batches 1 and 2. The spec's R3 says batch 3 is `third.NewResults`, which is the **raw** list before `MapNative`. The two differ whenever a third-pass decode repeats a text already published in batch 1, 2 or earlier in batch 3, or is implausible. Rare, but B-EQ-2 is "0 cycles differ on plain text" and a single such cycle changes R4 and so the rows. See F1.

**(2) Does `RunThirdPassAsync` mutate its input buffer? NO.** `SubtractionPass.cs:425` `var residual = (float[])normalisedPcm.Clone();` and the parameter's own doc at `:215`: "Not modified: the pass works on a copy". The returned `Residual` is that copy. So the round needs no extra copy of B. One caution kept from the code comment at `Ft8Decoder.cs:1062-1064`: the fallback's worker threads may still hold the same array; reading it concurrently is safe (nothing writes it) and the round starts after the fallback has returned anyway. The Developer should still cite the `:425` line in the commit, as R3 asks.

**(3) Does any consumer switch on the batch number so that batch 5 is dropped or mislabelled? NO consumer switches on a specific value; the daemon needs no change.** Found by grep over `src/`: `DecodePump.cs:166-168` handles `batchNumber == 1` and sends every other number to `PublishSecondAsync` (panel, `ALL.TXT`, filter admission, answerer and caller channels, external reporting, PSK Reporter), which takes `batchNumber` as a plain int. `QsoAnswererService.cs:633` and `QsoCallerService.cs:646` test `BatchNumber > 1` (supplementary batch). `LateBatch.cs:39` and the log lines carry the number for logging only. `DecodeBatch.cs:12` and `DecodePump.cs:83,247` **comment** "2, 3 or 4" and should read "2 to 5". The time-based expiry of a late CQ or reply is by the clock, not the number. See F4 for the callback.

## Amendments

**F1. Name the harness rule for the fit list.** Replace R3's "batch-3 natives (`third.NewResults`) ∪ the batch-4 natives that were published" with: **the natives behind the decodes `MapNative` published in batches 3 and 4** (first occurrence of each text in the cycle, not in `seen`, `IsPlausibleMessage` true), unrounded `OutDtS`, `FreqHz = round(OutFreqHz)`; `alsoKnown` is batch-1 natives ∪ the **raw** residual-pass natives `newFromResidual` (the harness uses `n1 ∪ n2`, raw). The Developer needs `MapNative` (or a small helper beside it) to return the kept natives alongside the `DecodeResult`s; the refusal count (`IsReencodable`/`EncodeMessage`) comes after that, as in the third pass. If the Developer sees a reason the raw list is better, B-EQ-2 will show it, but the spec should not start from the reading the harness does not have.

**F2. Take buffer B from the same function the fallback uses.** `CohFallbackAudioSelector.Select(...)` already encodes the rule (`:43-64`): R3 only if the third pass's outcome is `Ran` and it has a residual; else `report.Residual`, but only if the residual pass was not abandoned or contained, its buffer exists and `FittedSignals != 0`; otherwise the original audio. Write R3's buffer rule as "the buffer `Select` returns when `IsResidual`", and R2(d) as "`Select` did not return the Original or Unavailable level". Two implementations of the same rule would drift; this one cannot. The harness's `level == "O"` skip is exactly that case (0 cycles in the refset with R2 or R3 but no snapshot, `snapB_bad` 0 in every arm).

**F3. B-EQ-1 as written can fail for a legitimate reason.** "ON: batches 1-4 are identical to B-OFF's in all 1,200 cycles" ignores hash-table feed-forward: the round's decodes insert their callsigns into the process-global hash table (the harness bracketed with HashStateSave/Restore for exactly that reason, LATE-SUB Amendment 1 D3), so a later cycle can resolve a `<...>` token in ON that OFF leaves unresolved. That is the real effect on live use and it is also what B-EQ-2 already allows in batch 5. Make B-EQ-1 mechanical in two parts:
- (i) **up to and including the first cycle in which the ON arm published a batch 5**, batches 1-4 identical to B-OFF's (every field);
- (ii) **afterwards**, identical **modulo hashed tokens** (compare with every `<...>` token replaced by a wildcard and the same count of rows), and every cycle that differs only by a hashed token is listed. Any other difference stops the row.
Without this, B-EQ-1 can fail on a correct build and the failure would be read as a regression.

**F4. Reuse the existing batch callback; do not add one.** `Func<int, IReadOnlyList<DecodeResult>, Task> onFallbackBatch` (`Ft8Decoder.cs:554`, `:1133`) and the pump's staged delegate (`DecodePump.cs:166`) already carry a batch number. Batch 5 goes through the same delegate with `5`; a new callback would widen `DecodeStaged`'s signature (`DecodePump.cs:45`) and touch the daemon wiring for no gain. Keep the R5 consumer listing, but it should say what I found (no switch on a value). Update the four doc comments.

**F5. QA tooling must carry batch 5 before §3, and the B-OFF comparison must stay on the shared columns.** Replay81 (`FitProbe`) captures batches 1-4 only: its staged callback, `run.csv` columns (`b1_n`..`b4_n`), the `nc_dump` kind codes and `StageProbe` need a batch 5 (`b5_n`, kind 5), or the ON arm's batch 5 would be dropped or mislabelled **in QA's own instrument**, which is the failure your question (3) guards against in the product. This is `qa/` code, mine, and goes before §3 in the order list (new step 4a; about an hour, with a regression on refset cycles 1-40 that the OFF-setting output stays byte-identical to today's). The B-OFF row compares against `raw_main\main`, which has no batch-5 columns, so it compares the columns both sides have (every batch 1-4 field, plus `b5_n` = 0 in B-OFF).

## Smaller points (no amendment)

- **R6 / sol timing:** the round runs after the fallback publish, so on sol (fallback ends at 11.1 s at worst) the round has about 1.9 s of the 13 s budget minus the third pass's own reserve; the all-or-nothing rule means some cycles will abandon and the T-WARN flag covers it. I would add `fbEndMs` to the log line so that "eligible" is mechanical (a cycle is eligible when the round started). The pilot of the harness on the PC shows the round's median at 0.75 s and its max at 1.3 s, so on a machine about 1.6 times slower (sol's fallback ends 11.1 s against 5.8 s on the PC: ratio 1.9) the round's median is about 1.4 s. BL-4 (≤ 5 % abandoned) looks optimistic to me for the 11.1 s tail; I would give it 0.45. It does not change a row because NET prices it.
- **Late batches in the QSO services:** a batch 5 that arrives at, say, 14 s into a 15 s cycle is superseded by the next cycle's TX decision under `LateBatch`; its decodes are still published to the panel, `ALL.TXT` and reporting. That is the same as batch 4 today. Worth one sentence in the FR.
- **R8 tests:** add "batch 5 and the hash table: the round's unpack happens after the fallback's under the decode gate" as a test, not only a Developer confirmation.
- **§3 timing:** the product alone is faster than my harness (no V2 reproduction): about 3.3 s per cycle, so about 1.1 h per arm rather than 2.3 h.
- **B-EQ-2 and the deadline:** the harness ran the round with no deadline; the product passes `SubtractionCycleBudget - sw.Elapsed`. On the PC the round ends by 5.8 s so the deadline does not bind; if B-EQ-2 shows an abandoned round on the PC, that is the reconciliation, not a failure of either side.
- **Predictions:** BL-1, BL-2 as you scored them; with F1 and F3 applied, BL-2 rises (the likeliest place to part was F1). I would not change BL-3 or BL-5.

## What happens next

1. You confirm F1-F5 (or amend); no Captain decision is needed for the review.
2. The Captain's go for the Developer session; QA writes the handoff (HK-015/HK-000) from the amended spec.
3. In parallel, QA does F5 (Replay81 batch 5 and its regression); nothing under `src/`/`native/` (HK-011).
4. Developer commit → QA HK-039 review record → §3 on the PC → sol.

Nothing pushed. No `src/`/`native/` change.
