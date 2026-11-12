# `COH-RES-CAND v2` Stage 2 ruling: **ACCEPT** stands; merge with the setting OFF is cleared; station ON waits on one desk check

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-12 15:37:34Z (`date -u`) · **Branch:** `arch/coh-res-cand-v2`
**On:**
- QA's report `qa/rr-study/2026-11-12-1537-qa-coh-res-cand-v2-stage2-report.md` (`qa/same-chain` `ae40f0b3`, local), and `crc2_result.json` beside it;
- freeze `7064738a` (code `17dcb1fc`, analysis blob `c6e48546`);
- build `59eb5a8f` (v0.71), spec `2026-11-12-1340` with Amendments 1–4 (`7e88c745`).

Docs only: `git diff --stat origin/main -- src/ native/` is empty.

## §1. Verdict

**ACCEPT, by the registered rule** (spec §8 A1.2: no validity row failed; N-GO, U-OK, B-AB and B-LATE pass).

| row | result |
|---|---|
| B-NAT, B-OFF (40/40), B-DUP (0) | PASS |
| B-WIRE | 500/500 residual-level cycles ran the third run (R3 440, R2 60); new rows in 155 cycles |
| B-KEEP | **0 of 11,834 arm-A rows missing** (3 allowed hashed re-renderings). "Add, don't replace" holds: E136's loss is fixed |
| N-GO | **fires.** NET **+0.357 pp [0.250, 0.464]** (A 11,604 → B 11,654 corroborated of n_ref 13,997, 500 cycles) |
| U-OK | **fires.** ΔU′_ta **0.006 [0.000, 0.014]** against 0.021 (3 tested_absent in 500 cycles) |
| B-AB, B-LATE | 0 ≤ 0 (`resAbandoned` 0); 0 ≤ 5 |

**Timing:** the third run took a median of 259 ms (max 594). Latest-batch p95 was A 5,459 ms and B 5,221 ms against 13 s. No cost seen.

## §2. What ACCEPT does and does not cover (HK-026; my error E164)

QA's report flags it, and it is right: **on this night the registered U row could judge only 4 of the 19 new rows that WSJT-X did not corroborate.**

| class of the 19 | n |
|---|---:|
| tested_absent | 3 |
| tested_present | 1 |
| hashed (`<…>`) | 4 |
| untestable class | **11** |

- Only `report` and `report CQ` were testable classes on this 40 m night (frozen from arm A). On #272's 20 m night, untestable was 0.
- **The registered row's quantity cannot see 15 of 19 rows.**
- Counting all of them as possible wrong decodes gives (3 + 4 + 11) / 500 = **0.036 per cycle**, a point value above the 0.021 bar. It has no interval, and it is not the registered row.

**Ruling on this.**
- **The verdict stands.** The rows were frozen, and the row ran as written. Re-reading a passed gate with a different metric after the data is the standing prohibition in the other direction too.
- **But ACCEPT means "no wrong-payload signal where the instrument can see"**, not "no wrong decodes". That limits what it licenses (§3).
- **E164, mine.** In A1.3 I ruled on the U bar's **level** for 40 m. I did not ask what share of new rows the bar's quantity could **classify** on that night: which classes were testable. QA's (k) figures were for arm A's rows, and arm A's untestable share was near zero. Nothing told me the new rows would fall in other classes, but asking was the HK-026 check, and I didn't ask.

## §3. What follows

**3.1 Merge with the setting OFF: cleared by this ruling.**
- B-OFF passed 40/40, and B-KEEP shows that ON loses nothing. With the setting OFF, the build is today's code.
- QA's next steps are its own: `pre_merge_check.py` on a clean checkout of `59eb5a8f` (HK-006), then the usual path.

**3.2 Station ON: the Captain's decision, and it starts a new era.** My recommendation is **(B) first**.

| option | what it is | cost | what it leads to |
|---|---|---|---|
| **A. ON now** | one POST + readback after the merge; new era "v2 ON" | none | +0.36 pp (one 40 m night); U is judged on 4 of 19 doubtful rows; upper-bound point 0.036 > bar |
| **B. PSK check first (recommended)** | QA matches the 19 not-corroborated new rows (sender call, ±1800 s, ±50 Hz, another receiver) against the 10 November PSK Reporter spot file, still in `_qa-scratch\cq-ap\`. That instrument was ruled one-sided USABLE (CQ-AP-PSK: ghosts 0/10,000, so a feed-corroborated decode is real) | about 1 h QA desk; no PC, no build | narrows the 0.036 upper bound with an independent reference; then A or C by the rule below |
| **C. Keep OFF** | merged, setting OFF | none | the lever exists unused; #272 closes as "v2 accepted, not enabled" |

**Rule for B, pre-registered here, before the check runs:**
- `U_ub` = (3 tested_absent + the hashed and untestable-class rows **not** feed-corroborated) / 500.
- **`U_ub ≤ 0.021` ⇒ I recommend A** (ON).
- **`U_ub > 0.021` ⇒ I recommend C**, and the reason is written on #272.
- Hashed rows whose sender is hashed cannot be matched. They stay uncorroborated, which is conservative.
- **This is a recommendation rule for his decision, not a gate on the verdict.** ACCEPT stands either way.
- **Arithmetic:** reaching ≤ 0.021 needs ≤ 10 uncorroborated rows, so at least 5 of the 15 must be found in the feed.

**HK-037:** the spot file holds real callsigns. It stays in `_qa-scratch\cq-ap\` only, the check reads it in code, and only counts leave. **It is deleted when this check is done** (or now, if he chooses A or C without B). This ruling extends its life for that one purpose, and for nothing else.

## §4. Predictions (spec §6, A1.4, A2.3), scored

| # | prediction | P | outcome |
|---|---|---:|---|
| CV-1 | Stage 0 FEASIBLE | 0.30 | ✅ HIT (scored at Stage 0; reasoning missed: frequency, not SNR) |
| CV-2 | no `native/` change | 0.85 | ✅ HIT |
| CV-3 | B-OFF and B-WIRE pass (scored on `59eb5a8f`, per the ledger note made before data) | 0.75 | ✅ HIT |
| CV-4 | U-OK fires | 0.35 | ✅ HIT, with §2's limit |
| CV-5 | ACCEPT | 0.25 | ✅ HIT |

**Brier 0.312 over 5.** All five hit, so the loss is entirely in the H calls, priced low: CV-5 at 0.25, and CV-4 at 0.35, lowered by me in A2.3 after Stage 0.
- The same direction as CQ-AP (Brier 0.250, H too pessimistic), after #272's CR-5 (too optimistic).
- That is two arms in a row where I over-corrected after a confident miss. It goes in the ledger as a pattern to watch, not yet a rule.
- And CV-4's hit is weaker than it looks: the row could see 4 of 19 (§2).

## §5. Housekeeping

- QA may delete `_qa-scratch\coh-res-cand\raw` and `scratch` (#272's arms; Stage 0 is done).
- QA may delete `coh-res-cand-v2\` per-message working files (`nc.tsv`) at job close.
- `_qa-scratch\cq-ap\arms\OFF` (with `nc.tsv`) and the spot file stay **only** if the Captain chooses B; they are deleted after it.
- My branches `arch/cq-ap`, `arch/coh-res-cand` and `arch/coh-res-cand-v2` hold docs only.

## §6. Decided (the Captain, 2026-11-12 15:40:18Z, `date -u`): **option A, station ON**

- **B is not run.** Its rule in §3.2 lapses unused, and the 15 unjudged rows stay unjudged. **Any later citation of v2's U side carries §2's limit.**
- **The code default stays OFF.** The station is changed by one config overlay POST of `{"decoder":{"coherentFallbackResidualCandidates":true}}` after the build is deployed to `_run-main`, with a full readback (HK-035): that key is the only one changed.
- **The daemon start is the Captain's word, as always.** QA stamps the era **"v2 ON"** from the log (`date -u`). It follows "CQ-AP ON" (13:29:03Z) and is never pooled with it or with earlier eras.
- **HK-037, now:** the spot file (`_qa-scratch\cq-ap\spots_raw.jsonl`, the `secured\` copy, and the `WRONG-BUILD-run` file) and `_qa-scratch\cq-ap\arms\OFF\nc.tsv` have no remaining purpose and are **deleted at once**. #272's `raw` and `scratch` go too. The v2 working files are deleted at job close.
- **Live watch, descriptive:** the first v2 ON session's report states `resAbandoned`, the `resRun=skipped-budget` count and the latest-batch p95, as for DO-3. No WSJT-X is needed, and no NET is claimed from it.
