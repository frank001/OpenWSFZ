# CQ-AP (candidate #2): Architect ruling on the arms. BETWEEN stands; the next step is the Captain's choice

**Author:** Architect · **Written:** 2026-11-11T21:51:57Z (`date -u`) · **Branch:** `arch/cq-ap` · **To:** QA, the Captain
**Rules on:** QA arms report `qa/cq-ap/2026-11-11-1935-qa-cq-ap-arms-report.md` (`qa/same-chain` `8c38585a`), build spec `qa/rr-study/2026-11-10-1546-architect-to-qa-spec-cq-ap-build.md` §4 and Amendments 1 to 3. Freeze: Part 1 `342d320b`, Part 2 `5cc84ad9`, code `32a17b0e`.
**No `src/` or `native/` change** (docs only). No callsign, message text or per-decode row appears here (NFR-021, HK-037).

## §1. Ruling 1: the verdict is BETWEEN, and the V-SELF bar is not amended

QA computed the frozen verdict function correctly: V-NAT, V-SET, V-OFF and V-FEED pass (not VOID), NO-GAIN does not fire, SHIP-CANDIDATE needs V-SELF and V-SELF failed (773 / 954 = **0.810** against **0.90**), U-UB passed (not FP-UNRESOLVED). **BETWEEN is the verdict of record.**

I do not amend the bar. It was frozen before any arm output existed, and a bar changed after its number is known is the thing the standing prohibitions forbid ("never re-read a closed gate with a better metric"). I agree with QA's recommendation.

## §2. What the V-SELF fail does and does not mean (recorded as an error, not a re-reading)

When I checked what V-SELF guards in this spec, I found it guards nothing on the SHIP-CANDIDATE path:

- A lost spot can only **remove** a feed corroboration. A real AP-only extra then counts as uncorroborated: **K_C goes down, K_N goes up.** That makes G-GAIN harder to pass and U-UB harder to pass.
- A lost spot can **never** make a false decode look corroborated. Fewer spots means fewer chance matches, and the WSJT-X corroboration route does not use the feed at all.
- So when G-GAIN and U-UB both pass, a low V-SELF cannot have produced a false pass. It can only mean the true K_C is higher than measured and the true K_N is lower. K_N is already 0.

The row came over from CQ-AP-PSK. There it did guard something: a coverage verdict (USABLE) whose reading is low exactly when the feed loses spots. In the build spec I applied it to a verdict whose other rows are already conservative under loss. That is a stop rule scoped to an output it does not guard (HK-025(ab)). I record it as **E159** in the prediction ledger.

This is **information for the Captain's decision in §3. It does not reopen the verdict.** BETWEEN stands as written.

**V-SELF went from 1.028 (CQ-AP-PSK, 2026-11-10) to 0.810. That drop is not explained.** One cause is ruled out: CQ-AP decodes are excluded before `{Reported}` is counted (`PskReporterEngine.cs:171` on `7ca00264`: `if (r.ApKind == ApKind.Cq) { … _window.Ap++; continue; }`, and `_window.Reported++` comes later at `:193`). So AP decodes are not inflating the denominator. I am not chasing the rest unless the Captain chooses option B below.

## §3. Ruling 2: the next CQ-AP step is the Captain's choice between three options

**The data (QA report §3, one night, `20261110` live capture, 500 window cycles):**

| quantity | value |
|---|---|
| AP-only extras | 102 in 500 cycles, **all corroborated** (63 by both the feed and WSJT-X, 39 by the feed only) |
| K_C | 20.4 per 100 cycles [16.60, 24.40]; **+0.85 % of OFF's 12,036 decodes** (interval 0.685 % to 1.009 %) |
| K_N (upper bound on false decodes) | **0** (bar ≤ 0.021 per cycle) |
| where the gain sits | 59 of 102 at or below −19 dB by our SNR; 11 at or above −10 dB |
| time | ON p95 +0.495 s (bar 1.0 s); 0 abandoned cycles in every arm |
| determinism | OFF vs OFF2: 0 of 500 cycles differ, so ON − OFF is the flag, not run noise |

For scale: the smallest gain the programme has kept is KMIN-OSD-RECAL, NET +0.146 pp (different denominator, so a scale marker only). CQ-AP's lower bound is several times that.

**Limits:** one night. "Corroborated ⇒ real" rests on the ghost model (CQ-AP-PSK §5). K_N is an upper bound, not a false-decode rate. AP decodes are tagged and never uploaded (D7). Live behaviour with the flag ON (QSO engine, UI) was not measured by this spec. The station did run 3 h live with it ON (era "CQ-AP ON live", A2.6), and nothing about that run has been reported to me as a problem.

| option | what it leads to | matters or housekeeping |
|---|---|---|
| **A. Turn CQ-AP ON on the station** (one explicit `cqApEnabled: true` config POST, read back, HK-035) | About +0.85 % more decodes, mostly very weak CQs. A new live era starts at the POST, never pooled with anything before it. AP decodes stay tagged and un-uploaded. The code default stays OFF. Undoing it takes one POST. | **Matters.** It changes what his station decodes. |
| **B. Repeat on a second live session** with a re-frozen spec, V-SELF descriptive only (decided before any data, so this is not a softened bar) | About 3 h live and 3.5 h PC. Confirms K_C and K_N on a second night and may explain the V-SELF drop. It does **not** remove the main limit, the ghost model, so it adds less than it costs. | Matters only if one night is not enough for him. |
| **C. Park CQ-AP** and move on (candidate #3 can use the same capture; the nhard / D-009 calibration is waiting) | The station stays OFF. The build stays on `feat/cq-ap` with the flag OFF. | Housekeeping. |

**My recommendation: A.** He is the only user, the change is one reversible POST on his own station, every extra was corroborated, the time cost is half a second of a 13 s budget, and B's extra night would not touch the limit that matters. Making it the **code default** I do **not** recommend yet: that should wait for the new era's own live evidence.

Whichever he picks: **candidate #3 is next on the programme**, and it can use the same `20261110` capture.

## §4. Housekeeping

- **Spot file** `_qa-scratch\cq-ap\spots_raw.jsonl`: QA keeps it until the Captain has chosen. If he chooses A or C, QA deletes it at the job close (HK-037). If he chooses B, QA keeps it so the V-SELF drop can be compared with the new night.
- Board and programme page are updated in the same edit as this ruling (HK-024).

## §5. Predictions scored (build spec §7)

| # | prediction | P | outcome | Brier |
|---|---|---:|---|---:|
| CB-1 | D1–D10 pass on first submission | 0.45 | ✅ HIT (scored 2026-11-10) | 0.3025 |
| CB-2 | K_C ÷ D_OFF ≥ 0.5 % (point) | 0.35 | ✅ HIT (0.847 %) | 0.4225 |
| CB-3 | U-UB passes | 0.35 | ✅ HIT (K_N = 0) | 0.4225 |
| CB-4 | verdict SHIP-CANDIDATE | 0.25 | ❌ BETWEEN | 0.0625 |
| CB-5 | T-TIME passes | 0.80 | ✅ HIT (+0.495 s) | 0.0400 |

**Brier 0.250 over 5.** This time my H calls were too **pessimistic**: I priced the gain and U-UB low to correct the known bias toward "a findable gain", and both came in. I wrote CB-3's reasoning on the assumption that the feed would miss many real one-off CQs. It missed none of the 102 extras. CB-4 missed for a reason I did not price at all: the guard row in E159.
