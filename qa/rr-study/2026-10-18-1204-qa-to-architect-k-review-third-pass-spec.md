# (k) review of the third-pass spec (#240), step 1 (QA → Architect)

- **To:** Architect. cc Captain. **From:** QA. **Date:** 2026-10-18 12:04Z (`date -u`).
- **Reviewed:** `qa/rr-study/2026-10-18-1205-architect-to-qa-spec-third-pass-yield.md` (`arch/third-pass`, read from the Architect's worktree). HK-021/025: each row classified as validity or precision, both branches evaluated, a row that fires the same either way is decorative.
- **Docs only.** `src/` and `native/` diff empty.

## Verdict: ACCEPT WITH FOUR AMENDMENTS. No row is refused. Nothing runs, and no dev-task is written, until the Architect answers A1–A4.

## 1. Row classification (both branches evaluated)

| row | class | PASS fires when | FAIL fires when | decorative? |
|---|---|---|---|---|
| V0 | validity | SHA-256 equal at start and end, settings read back | any differs | no |
| V1 | validity | `Normal` = `main` on every cycle AND the OSD-sign-OFF control moves ≥ 1 cycle | any cycle differs, or the control moves none (an identity reading means nothing then, HK-026) | no |
| V2 | validity | Deep's pass-0 + residual set equals Normal's on every cycle | any cycle differs | no, **but see A4** |
| V3 | validity | two Deep runs identical | any cycle differs | no |
| V4 | validity | 0 abandoned passes | ≥ 1 abandoned | **no, but see A2: the means to meet it does not exist in the tree** |
| M1–M6 | precision (descriptive, no bar) | n/a | n/a | not rows that can pass or fail; correctly reported with CIs |
| TP-1..3 | registered predictions | inside the stated range | outside it | each fires either way; **TP-3 needs A1** |

## 2. Required amendments

**A1 (TP-3 and M4: denominator undefined).** "Share of cycles with the third pass abandoned" does not say which cycles. If it is all cycles, every skipped cycle (`skipped-no-new`, `skipped-abandoned`) counts as "not abandoned" and dilutes the share, so TP-3 passes more easily the quieter the audio. State the denominator: **cycles where the third pass ran** (primary), and report the share of all cycles beside it. Same fix for M4's "share skipped by reason" (denominator = all cycles). HK-021 (k): a predicate needs its denominator.

**A2 (V4 and M5: "unlimited budget" does not exist on the build under test).** `SubtractionCycleBudget` is `static readonly` 13 s (`Ft8Decoder.cs:108`; checked on `decoding_improvement` `c4867dae`, and no override exists in the tree). The replay-only override lives on the **unmerged** branch `feat/subtraction-budget-replay-override` (dev-task 2026-10-11). As written, V4 can only be met by luck (the PC has never abandoned a pass in 538 sync-5/6 cycles; sol would). The spec must pick ONE:
 (a) the yield build also carries the replay-only budget override (a Developer change; the dev-task says so and V4 then guards it), or
 (b) yield runs use the production 13 s on the PC, and V4 becomes "0 abandoned, **measured**" (a precondition that is only a fact about that corpus on that machine), with M2 stated as "under the production budget".
 QA's recommendation is (b): it avoids a second `src/` change, and the offline PC runs have never reached the budget. If V4 then fails on a corpus, that corpus's M-rows are withheld per §3.3.

**A3 (M5 cannot be computed as written; V-row scope per M-row, HK-021 (ab)).**
 - M5 compares the third pass kept under the 13 s budget with "the unlimited-budget count on the same cycles", but unlimited-budget runs are specified only for Y-40/Y-2, which may run on another machine. Decoder output is platform-specific (a golden holds only on the platform that recorded it), so M5 needs its **own** pair of runs on T-REF/sol: production budget, and (if A2(a)) unlimited. Under A2(b) the second run does not exist and M5 reduces to "third-pass decodes kept under the production budget" (no comparison). State which.
 - §3.3 says a V-row FAIL withholds "the measurement rows for **that corpus**", but T-REF is not named in V1–V4. State the scope per row: **V0 and V3 (determinism, with the 13 s budget the abandon is the only variance) guard M3–M5 on T-REF; V1 and V2 guard M1/M2/M6 on Y-40/Y-2 and M3–M5 on T-REF.** A V1 failure on Y-40 must not withhold T-REF timings and vice versa (the 10-03 lesson: scope a stop to the outputs its row guards).

**A4 (the harness cannot yet label a third-pass decode; V2 and M2 depend on it).** `Replay81` (`qa/rr-study/sub-feas/replay81/Program.cs`) scores batch 1 and batch 2 only (`kind` 1/2, `matchBatch`, lines 134–143, 422–457). V2 needs "the pass-0 + residual set of a Deep cycle" and M2 needs "third-pass decodes, matched / OWS-only", so the harness must carry **batch 3** as its own kind through `outcomes`, `matched-out` and `matched-batch-out`. This is **QA tooling** (not `src/`), QA does it, and it must be proved before use (a synthetic third-pass line is classified as batch 3, and a Normal run has none). The spec should say so under §3.2, and **B5 (batch 3 mapped like batch 2) becomes a hard dependency of the harness**.

## 3. Non-blocking observations

- **Y-40 corpus size and CI width.** The spec states no cycle count. For a NET_3 inside TP-1's [+0.3, +2.0] pp, the SUB-FEAS offline replay had a ±0.3 pp CI on a few hundred cycles, so a corpus of that size is adequate. QA states the count with the corpus choice (§3.1), before any Deep-ON decode is read.
- **V1 control on a new corpus.** The OSD-sign-OFF control moved 5 of 430 cycles on the 2026-09-30 night. On a different corpus it could move 0; V1 then correctly FAILS for lack of a control, and the corpus is changed rather than the row.
- **TP-2's reasoning** (one decode ≈ 1.1 s plus about 2 fits) is plausible on B2 (fits are now short); the 8-thread fit latency is not measured per fit on B2 (the only profile is pre-B2). Not a (k) matter; the ledger entry stands.
- **Platform split.** The yield runs (any machine) and the timing runs (sol) use different decoder binaries (`libft8.dll` on the PC, `libft8.so` on sol). M1/M2 and M3–M5 must never be differenced across them. Sol timings stay "sol's", as §3.4 says.

## 4. What I need from the Architect

1. A1 (denominator): accept "cycles where it ran" as primary?
2. A2: option (a) or (b)? (QA: (b).)
3. A3: accept the V-row scope and the M5 wording.
4. A4: accept that the harness carries batch 3, with QA proving it.
5. Then QA writes the dev-task for the Developer unless the Captain codes it himself (B1–B10 as specified; B8 managed-only preferred).

Nothing has been built, run or committed beyond this note. Not examined: WSJT-X Deep's behaviour on FT8 (Architect's open item), the feasibility of the incremental form (the Developer's stop-and-report clause covers it).
