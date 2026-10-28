# GAP-RELOCATE: QA's HK-021(k) review

**To:** Architect · **From:** QA · **Date:** 2026-10-28T13:24:19Z (`date -u`) · **Spec reviewed:** `690e8cb5` on `arch/gap-relocate`
**Verdict: ACCEPTED WITH FIVE AMENDMENTS (K1-K5).** No row is refused. K1 and K2 change what a row measures and are required before a run; K3-K5 are wording and bookkeeping.
Nothing runs until the Captain gives his go (the spec says so, and the station's first night comes first).

## Checked and found sound

- Every export in section 0 exists on `main` `95e69e87` at the cited lines (`ft8_extract_llrs_at` :1265, `ft8_ldpc_decode_llrs` :1370, `FT8_COH_FLAG_FORCE_C3` :1499, `ft8_coherent_fallback_at` :1533, `_cycle` :1585, `_sets_at` :1706). Row 0a should still assert them in code.
- Replay81 already has `--cohfb 0|1` (`SetCoherentFallbackEnabled`, read back at start and end) and `--cohaudio`. The OFF arm needs no STOP.
- Row 0b is valid on (k) grounds: a replay that differs from B2 re-scores M. Row 0f likewise (abandonment fakes misses). The 0b bar is exact, and R0 byte-identity supports it.
- Item 1's own warning is right. B2's table (report.md lines 51-58) mixes candidate-run rows (F1b computed 2,524) with payloads (published 725). A payload found by the walk may be published with no F1b computed, which would explain 563 < 725 and is exactly the FCw class. Worth stating in A1.

## Amendments

**K1. Row 0c's control contains rows the forced legs cannot reach (validity).** K is a sample of the BOTH arm's *hits*. Some of those hits were found by the fallback on the *residual* audio only (B2: 625 residual-only payloads against 593 shared). The forced legs read the *original* audio only (section 3, last bullet). So `P_ctrl` can fall below 0.90 for a true reason and not because the mapping is wrong, and row 0c would then stop the study. Branch check: if the mapping is right, residual-only K rows still fail FP and FC (row fires, falsely); if the mapping is wrong, all K rows fail (row fires, rightly). The same row fires for both causes, so as written it cannot tell them apart.
*Required:* tag each K row with its path (batches 1-3, fallback on original, fallback on residual only; the B2 matcher already carries `path`). Row 0c's bar applies to K rows found on **original-audio paths**. The residual-only K rows are reported beside it as `P_ctrl,res`, descriptive. That figure is also the honest size of N's blind spot (K4).

**K2. δ must not be fitted on the rows that judge it (validity).** Section 3 recomputes δ on matched pairs of K and then 0c judges K at REF + δ. If δ is the median of (production position - REF position) over matched pairs, there is no circularity, but the spec does not say so. If it is chosen to maximise forced success, 0c is in-sample.
*Required:* state δ as that median, computed from the **pilot's 40 cycles only**, then frozen. Row 0c is evaluated on the K rows of the remaining 360 cycles. The 40-cycle pilot keeps its stop role (pilot `P_ctrl` < 0.90 stops the study before any M row is forced).

**K3. A single P_ctrl cannot bound the miss rate on M (HK-026).** K rows are decodable by construction; M rows are the weak ones. A pooled 0.96 can hide 0.70 in band D, and that is where M lives. Row 0c passing therefore does not show that N is mostly real.
*Required:* report `P_ctrl` by band A-D (and the K count in each). Any band with n >= 50 K rows and `P_ctrl` < 0.80 marks that band's N as "lower-bound-of-undecodable not established" in D3 and in any routing sentence. The 0.80 is a proposal; per HK-038, freeze it only after the pilot's per-band figures are on file, and say where it came from.

**K4. Row R-N's route text over-reaches (validity of the inference).** R-N says N is "interference-limited ... no decoder lever". The spec itself says N is an upper bound because the forced legs do not see the residual buffer, and B2 has already shown that audio matters (+3.60 pp from reading the residual). So N contains rows that subtraction may make decodable, which the instrument cannot see. R-N firing is then consistent with both "interference-limited" and "subtraction-recoverable".
*Required:* reword R-N's route to: "N is not decodable by any extractor we can force on the original audio. This map cannot separate interference-limited from subtraction-recoverable. The Captain decides whether to commission a residual-buffer forced export (a native change, Developer, HK-011) or to stop." Also give the predicate a definition: `CI_lo(N)` >= the **sum** of the other classes' point estimates is fine, but add that it is tested on `n_ref` pp, same unit as the others.

**K5. Bookkeeping (no verdict effect).**
(a) Write the class predicate order as code in the report: P, then FP, then FC (V3 payload, `gated` false), then G (V3 payload, `gated` true), then FCw (walk payload only), then N. Section 3 lists the FC walk branch before F1b is defined, so a row with a V3 payload gated and a walk payload ungated has no stated class.
(b) State that `A3` is a subset of `P`: A3 counts batch-4 implausible drops WSJT-X confirmed; `P` counts any-batch drops among BOTH-arm misses. Reconcile them in the report.
(c) FP tries nine cells, FC tries the REF position (plus the walk). Because FP is checked first, FP absorbs rows FC could also decode. That is by design; say so in D2/D6 so R-FC is read as "FC given the primary cannot".
(d) Five routing rows, several may fire, each tested at `CI_lo` >= 0.5 pp: accept as a routing aid; the report should say "no multiplicity adjustment" so nobody reads it as a family-wise claim.
(e) The bootstrap is by cycle; fine. Please add the per-station clustering figure the spec already asks for next to each fired row.

**Correction (QA, 13:27:00Z `date -u`; ledger Q24):** K5(a) above has the polarity of `gated` inverted. The header defines `gated` = 1 iff F1b was computed and F1b <= T1, so FC = V3 payload with `gated` 1 and G = V3 payload with `gated` 0. The Architect's Amendment 1 (A1.5a) is correct and governs.

## Scheduling and machine

- The replays and the forced legs use the PC's CPU. The station daemon is live there (era "FB-AUDIO" from 11:57:29Z). A heavy replay beside it could lengthen the station's own cycles and put abandoned candidates into the era's log. I will not start anything before the Captain's go, and I will propose a start after the first night is read and the OpenSpec archived. Row 0f protects the replay; nothing protects the station except the schedule.
- Order of work once approved: (1) Replay81 extension for the Debug template (a `qa/` change, allowed); (2) BOTH and OFF arms with A1-A4; (3) 40-cycle pilot for 0c and δ; (4) the forced legs. HK-039 does not apply (no `src/` or `native/` commit); this file records the spec review only.

## Answer to your question

I refuse nothing. Amend K1 and K2 and I will run it on the Captain's go. K3 and K4 should be in the spec before the run, since they change how the answer may be read, not how it is computed.
