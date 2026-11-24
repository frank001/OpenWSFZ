# FP-ALARM (#279) step 1 record (QA, 2026-11-12, `date -u` 17:23:00Z at the last check): verdict by the registered rule **TOOL-FAIL**; the alarm is nearly blind on this night, and T-X shows it

**To:** Architect, then the Captain. **Spec:** `arch/fp-alarm-nhard` §1 with Amendment 1 (`524c05ca`); QA (k) review `501a3c83`. **No `src/` or `native/` change; nothing of step 2 has run.**
**Plain words for the Captain** (the spec asks that he be told): his 1× / 2× acceptance (inject ghosts at 1 % and 2 % and see F̂ rise by that much) is an arithmetic control only; it proves nothing about real false decodes. It also **failed** here, by chance (below). More important, the real-data check T-X says the alarm **sees none** of the rows the tone-test instrument calls wrong.

## What ran (frozen before any number was produced)

| item | value |
|---|---|
| tool | `qa/fp-alarm/` (`FpAlarm.csproj`, `Program.cs`), AssemblyName `Ft8.FitProbe` (a friend of `OpenWSFZ.Ft8`), references Ft8, Abstractions and Daemon of a clean checkout of `main` **`260190e8`**; the product's own `ExtractPrimaryCallsignToken`, `IsPlausibleMessage`, native unpack, `CallsignRegionStore.TryMatchPrefix` and `CallsignGrammarStore` are called, never reimplemented |
| frozen at | commit **`0aca3945`** (`Program.cs` git blob `66f0737aa3befca08eeefba3c212ce0a0f5ffd85`, tool DLL SHA-256 `73d0100089f0fd57e4a155739f9344d3753bdc2860f4dff4ed0192412c6016ab`), before `sens`, `fa`, `pos` and `armcounts` ran. An earlier commit `34eaad5e` was superseded the same hour, before any numeric row, for the T-CLASS fix below |
| pinned station files | `callsign-regions.json` SHA-256 `bcf0bee2302c21c54fb66c6bcec3f6aa432352e424e32b3740413aa2658c98e6` (29,013 entries, `IsSeedData` false); `callsign-grammar.json` `7b581f31b7f0f65191da247eda6568e2f919d96c1414f9b268c39f4943bba37e` (equal to `BuiltInDefault`) |
| diagnostic only | `drift` mode, added AFTER the registered rows (commit `2e17e8a4`, `Program.cs` blob `da2222bcf53c38e602f7d31a7b6fad2283ca98a1`), built to a separate folder; not a registered row |
| invocations | `Ft8.FitProbe.exe pin\|tclass\|sens\|fa\|pos\|armcounts --regions … --grammar … [--wsjtx … --own …]` on the PC, no `--filter` (not a test suite), station daemon running until 17:21:03Z |

## Rows (registered; numbers only, nothing that is message text)

| row | predicate | result | |
|---|---|---|---|
| **T-PIN** | file hashes = the freeze; `IsSeedData` false | both hashes match; 29,013 entries; `IsSeedData` **false** | **PASS** |
| **T-CLASS** | 100 % of hand-classified vectors | **24 of 24** (see "A wrong premise found by this row") | **PASS** |
| **T-SEP** | Wilson_lo(s, G-ANY) − Wilson_hi(FA) ≥ 0.20 | 0.1376 − 0.0010 = **0.1366** | **FAIL** (structural: s_lo is below 0.20 even if FA were 0) |
| **T-POS** (arithmetic control) | each step's F̂ increase within [0.5, 1.5] × the ghosts injected | step 1 ratio **0.978** (in band); step 2 ratio **1.621** (out of band) | **FAIL** |
| **T-PROD** | live daemon's published Region = the tool's class on ≥ 40 cycles | **not run**: the daemon was stopped at 17:21:03Z (its log ends there with no shutdown line), about 55 seconds after the tool connected at 17:20:08Z; no result exists | **NOT RUN** |
| **Verdict** | TOOL-OK iff all pass; TOOL-WEAK iff only T-SEP fails; TOOL-FAIL otherwise | T-SEP and T-POS fail, T-PROD unrun | **TOOL-FAIL** |

T-PROD cannot change the verdict (T-POS already fails). It stays owed as a validity check of the tool if the Architect keeps the tool: it needs the daemon running, which is the Captain's word.

### The measurements

- **`s`, ghost sensitivity** (seed 20261112, ≥ 10,000 kept ghosts): **G-ANY s = 0.1444 [0.1376, 0.1514]** (I 1,444 of N 10,000; 52,650 ghosts generated, 10,011 kept by the plausibility filter, 11 excluded). **G-CQ s = 0.0796 [0.0745, 0.0851]** (descriptive). NC-2 (s ≥ 0.30) missed. Only about 14 % of plausible random decodes land on a callsign the region table does not know.
- **`FA`, false-alarm rate on WSJT-X's decodes of the night** (21,193 lines): literal **13 of 21,193 = 0.00061 [0.00036, 0.00105]** (the gating figure); plausibility-filtered (descriptive) 1 of 21,092 = 0.000047 [0.0000084, 0.00027]. **The literal figure contains 12 WSJT-X rows our own plausibility filter would never publish**, so it overstates the background for our decodes; the spec gates on the literal one and I kept to it.
- **Our own live decodes of the night** (18,445 rows): **0 implausible**; its repeat-confirmed subset (P_R, approximated with the product's primary-callsign token as the sender rule): 0 of 16,263. EXCLUDED: 0 of 18,445 and 0 of 21,193.
- **T-POS detail:** base N 18,445, I 0; injection step 184 ghosts entering N (1 %); F̂ 0× = −78.7 (negative: the literal FA exceeds our base rate), 1× = +101.4, 2× = +399.6; increases 180.0 and 298.3 against 184 injected.
- **T-X (descriptive, no bar; real data):** the OFF2 arm of the CQ-AP study (500 cycles, same decodes as the OFF arm): **0 implausible rows of 12,036, and 0 of its 432 not-corroborated rows**; F̂ floor = **−1.84** (the not-corroborated rows hold fewer region misses than the background alone predicts), beside **68 tested_absent** rows of that arm. The spec's reading: "F̂ well below about 68 means the alarm misses wrong payloads the tone test sees". **It does.**

## A wrong premise found by this row (my ledger Q60)

I fixed the expected class of every Q-prefix vector as IMPLAUSIBLE ("the Q-series is never allocated, so no region"). The station's region table has an explicit entry, prefix `Q` to "Synthetic (R&R Study)" (the NFR-021 carve-out), so Q-prefix calls are RESOLVED, and the first T-CLASS run failed on exactly those vectors. T-CLASS did its job before any numeric row ran. The vectors were corrected from the documented table entry, not from the tool's answers; the IMPLAUSIBLE vectors are now built in process from tokens the pinned table does not match (never printed, never committed); the tool's logic did not change.

## Why T-POS failed, and what that means (post-hoc diagnosis, labelled as such; it does not change the registered result)

- **It is sampling noise, not a tool defect.** The step injects 184 ghosts of which about 26 are visible, so each step's ratio carries about ±18 % noise (binomial); step 2 landed about +3σ high. Evidence, from the diagnostic build: the same seed's windows of 1,000 ghosts give s = 0.140, 0.234, 0.132, … 0.119 (the 0.234 window is the one step 2 drew); across five other seeds window 2 averages 0.157, window 1 0.162 and later windows 0.163, so **there is no drift** (the hash table filling does not matter); **whole-run s across seven seeds is 0.145 to 0.157 with a spread of 0.0035, which is exactly the binomial spread** (`drift_whole_run_s.csv`), so the generator is sound. The registered s (seed 20261112, 0.1444) is the lowest of the seven.
- **The row has a built-in false-failure rate of roughly 1 to 3 %** with this injection size and this s, so a failure alone says little about the tool. I did **not** re-run on another seed (that would be shopping for a pass).
- **The larger problem is not T-POS.** (1) T-SEP can never pass: with s at 0.14 the alarm cannot clear a 0.20 margin. (2) **T-X: the alarm sees 0 of the 68 tested_absent rows' worth of wrong decodes and 0 of all 12,036 published rows.** If those 68 were uniform random payloads, the chance of seeing none is about 1e-5 to 3e-5 (0.85^68). So either the tone-test rows are not what the alarm's model assumes (OSD false accepts are codewords near a received word, so their payloads can look like real messages and resolve to a real region), or they are not false at all. **Either way the alarm cannot see them**, which is the case the whole step was meant to cover.
- **Resolution, for step 2's C-F row (descriptive today):** even with zero region-miss rows in both arms, a Poisson upper bound of 3 events converts to about **0.040 false decodes per cycle** (3 / (s − FA) / 500 cycles), already **above the 0.021 bar**. C-F as written could never read SETTLED, and its CI_lo could only exceed 0.021 after a handful of extra region misses.

## What follows (the Architect rules at the end of step 1)

By the registered rule the verdict is TOOL-FAIL, so §2 / A1.3 apply: **step 2 runs with U′ only, SETTLED reads "settled where U′ can see" with U-COV stated, and the Captain is told.** Options for the Architect, with my reading:
1. **(recommended) Accept TOOL-FAIL as registered**, run step 2 as written without the alarm gating, and report the alarm's limits to the Captain in plain words (above). The record stays; #279's tool exists, hashed, and can be rerun.
2. Amend T-POS to a power-adequate injection (for example 5 % and 10 %, about 920 and 1,840 ghosts, noise about 8 % and 6 %) and re-run T-POS only. It would likely pass, but T-SEP still fails (TOOL-WEAK at best) and **T-X would still say the alarm is blind**, so the verdict would not change what step 2 does.
3. If the Captain still wants a class-agnostic false-decode signal, it needs a different signal than "the callsign maps to no region" (that is a new spec, not this one).

## What this record does not conclude

- It does not say OSD or any lever produces false decodes; the alarm is blind, so it says nothing either way. U′'s tested_absent (68 on arm A, 3 over the v2 new-text rows) remains the only instrument that sees them, and it judges few rows.
- It does not conclude the 68 tested_absent rows are false decodes; only that the alarm cannot see them.
- T-PROD, the validity row against the product's published Region, was not run; the tool's equality with the product's `Region` is therefore not proven on live data (T-CLASS and the use of the product's own functions are the evidence).

## Files

Numbers only, scanned for NFR-021 (no callsign-shaped token): `qa/rr-study/results/2026-11-12-fp-alarm-step1/` (`pin.json`, `class.json`, `sens.json`, `fa.json`, `pos.json`, `tx.json`, `off2_percycle.csv`, `drift_seed20261113_windows1000.json`, `drift_whole_run_s.csv`). Scratch only (no text in any of them): `_qa-scratch\fp-alarm\` (the pinned station files, the two builds, the tree).
