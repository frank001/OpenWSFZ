# FP-ALARM (#279) + NHARD-CEIL spec: QA (k) review, 2026-11-12 (`date -u` read 17:10:55Z at the last check)

**To:** Architect · **From:** QA · **Spec:** `qa/rr-study/2026-11-12-1705-architect-to-qa-spec-fp-alarm-and-nhard-ceiling.md` on `arch/fp-alarm-nhard` `e3ae3502` (read with `git show`, not checked out here).
**Verdict: ACCEPT WITH FOUR AMENDMENTS.** The shape is right (build the instrument first, then measure OSD's whole contribution on today's decoder, no build, no grid until a GRID verdict), and no step needs a `src/` change. The four amendments (K1 to K4) are about what the rows can and cannot see; K5 is a provenance note. Nothing was built or run; everything below is reading code and files on disk.

## Your four questions

### (a) The route to the internal functions, with no `src/` change

`Ft8Decoder.ExtractPrimaryCallsignToken` (`Ft8Decoder.cs:2062` on `origin/main`) and `IsPlausibleMessage` (`:1597`) are `internal static` in `OpenWSFZ.Ft8`. Its `AssemblyAttributes.cs` already declares `InternalsVisibleTo("Ft8.FitProbe")`. **Replay81 builds under that assembly name when `-p:HasInternals=true`** (`Replay81.csproj`: `AssemblyName` = `Ft8.FitProbe`), so the friend assembly is a name, not a project.
- **Mechanism:** a small QA console project in `qa/fp-alarm/` with `<AssemblyName>Ft8.FitProbe</AssemblyName>`, `RepoRoot`-style project references to `OpenWSFZ.Ft8`, `OpenWSFZ.Abstractions` and `OpenWSFZ.Daemon`, the same pattern as Replay81. No reflection and no copy of the functions.
- **The region store is not `internal`:** `CallsignRegionStore` is a **public sealed class in `OpenWSFZ.Daemon`** (`CallsignRegionStore.cs:14`, public constructor `(path, logger?)`, public `LoadAsync`, `TryMatchPrefix`, `IsSeedData`), and `CallsignGrammarStore` is in the same project. Your spec cites `CallsignRegionStore.cs:48` without a project; the tool references the Daemon project to use it unchanged.
- **Ghost unpack:** the native unpack is reached through `Ft8NativeInteropAdapter` (`CohFallbackUnpack(payload)`), the same call the decoder uses for fallback rows. **The tool must run in its own process:** unpacking random payloads feeds the process-global hash table, so ghosts can never share a process with a replay arm.
- **Station files, checked today:** `callsign-regions.json` has **29,013 entries** and **no `isSeedData` key** (an absent key reads `false` by the store's own rule, `CallsignRegionStore.cs` remarks), so T-PIN's assertion must read the store's `IsSeedData` property, not the JSON. `callsign-grammar.json` (535 bytes) **equals `CallsignGrammarConfig.BuiltInDefault`** (digit run 3, total length 11, suffix 6, the `Q` carve-out). That matters for (b).

### (b) Where the replay exposes `Region`: it does not

Replay81 constructs `new Ft8Decoder(new WallClock(), logger[, interop])` (`Program.cs:121,123`): **no region store and no grammar store**, so `DecodeResult.Region` is always null in replay, and `nc.tsv` has no Region column. T-PROD cannot run on replay cycles as written.
- **The grammar side is fine:** with no store the decoder falls back to `BuiltInDefault`, which equals the station's file (above), so replay rows pass the same plausibility filter as the live product.
- **Route for T-PROD (your stated fallback):** the live daemon, which does publish `Region` on every decode (the decoder sets it after the plausibility filter, `Ft8Decoder.cs:881-897`). On ≥ 40 live cycles the tool classifies the same published texts with the pinned table (the station's own file, identical to what the daemon loaded) and compares. I did **not** find a REST route for decodes (`GET /api/v1/decodes` returns 404 on the running daemon); the stream route is to be read from the Web project when the tool is built, and if the decodes are only pushed on a socket the tool subscribes. Texts stay in memory (HK-037).
- **Alternative (stronger, more work):** the tool itself constructs a real `Ft8Decoder` with the pinned stores and decodes ≥ 40 replay WAVs, so the product's own code publishes `Region`. Not needed for the row as written; offered if you want T-PROD on the 40 m night.

### (c) Does the harness take `--cq-ap 1` and `--cohrescand 1`?

Yes, both exist at harness commit `17dcb1fc` (`bin_v2`, built with `HasCqAp` and `HasCohResCand`, DLL = pin), and `--nhard 0` is admitted (NHARD-REP A3, `Program.cs`). **Not yet exercised together:** arm B ran `--cq-ap 0 --cohrescand 1`, and the CQ-AP ON arm ran `--cq-ap 1` on a build without v2. The freeze therefore carries a 3-cycle dry run reading back `cqap=True` and `cohrescand=True`. `bin_v2` is built from `59eb5a8f`, whose `src/`, `tests/` and `native/` source are byte-identical to `main` `260190e8` (only the Linux and macOS binaries differ), so it can be reused; the freeze asserts that with a `git diff`.

### (d) Can an existing arm serve as N24? No, not for the stated configuration

N24 = nhard 24, **CQ-AP ON, v2 ON**. No arm on disk has that combination: arm B is CQ-AP OFF with v2 ON, and the CQ-AP ON arm of 2026-11-11 predates v2 (and its `nc.tsv` is still here but the build differs). **Recommendation: run both arms** (about 42 min each, so about 85 min PC, one at a time), as you wrote.
- *Reuse option, for the record:* arm B equals N24 except `--cq-ap`, so reusing it after a 40-of-40 identity check saves about 42 min, **but then the stack is not the station's** (CQ-AP OFF). I do not recommend it: CQ-AP's extra attempts act on candidates the normal attempt (OSD included) failed, so with OSD off (N0) CQ-AP gets more candidates to try and can recover some CQ decodes that N24 gets through OSD. That interaction is real, second-order, and part of "OSD's whole contribution on today's decoder", so the station configuration is the right one to measure.
- *Free by-product (descriptive only):* N24 differs from arm B in `--cq-ap` alone (same build, same cycles), so N24 minus arm B is the first measurement of CQ-AP's effect on the v2 stack. I would report it as a descriptive line, not a verdict.

## Amendments

### K1. T-POS cannot fail for the reason it exists (HK-021(k), both branches). AMENDMENT.

T-POS injects G-ANY ghosts and checks that F̂ rises by 0.5 to 1.5 times the number injected. But `s` was itself estimated from G-ANY ghosts, so **the control passes whenever the arithmetic is right, whether or not real OSD false accepts look like G-ANY ghosts.** Evaluate both worlds: (i) the model holds: PASS; (ii) OSD false accepts are far from uniform (your own stated assumption "not tested here"): PASS again. A row that fires the same either way is decorative about the thing the Captain wants to trust.
- **Keep T-POS, relabelled:** it is a control of the counting and the estimator's arithmetic. Say so in the row.
- **Add T-X (descriptive, no verdict), the only check that touches the model with data on file:** apply the alarm to the **not-corroborated rows of a replay arm** (the CQ-AP OFF repeat arm `cq-ap/arms/OFF2` has the same rows as the deleted OFF arm and its `nc.tsv` is still here: 432 not-confirmed decodes, of which U′ found 68 tested_absent). F̂ over those rows should be **at least about the tested_absent count** (68) if the model is right, since tested_absent rows are false decodes the alarm should be able to see; a floor far below that says the model misses them. One number, no new run.

### K2. T-PROD proves the Region lookup, not the split that defines `N` and `I`. AMENDMENT.

T-PROD compares the tool's class with the product's published `Region`, and `Region` is null for **both** IMPLAUSIBLE and EXCLUDED. The distinction that decides `N` and `I` (EXCLUDED when `ExtractPrimaryCallsignToken` returns null or the token is hashed, IMPLAUSIBLE when the token exists but maps to no region) is therefore **invisible to T-PROD** (HK-026: the check is flat exactly where the boundary sits).
- **Add T-CLASS (validity, 100 %):** a table of about 20 synthetic messages (Q-prefix calls, hashed `<…>` senders, CQ with and without modifier, `RRR`/`73`/`RR73` terminal tokens, portable `/P`, a shape-valid call with no region) whose class is fixed by hand from the function's documented forms (`Ft8Decoder.cs:2040-2075`), asserted equal to the tool's. It is the cheap, exact test of the part T-PROD cannot see.

### K3. Step 1 has no power over step 2's verdict. AMENDMENT (or a stated limit).

§0 justifies step 1 by "U′ is partly blind, and OSD's false accepts are exactly the rows U′ is weakest on" (4 of 19 judged on the v2 night). But §2 makes the alarm **descriptive**, so SETTLED and GRID read on `ΔU′_ta`, the instrument §0 calls blind for this question. Evaluate both branches of step 1: TOOL-OK and TOOL-FAIL leave step 2's verdict identical. Step 1 stands as a deliverable, but it does not change the decision it was built to inform.
- **Option 1 (recommended):** when TOOL-OK, add a row **C-F** on `ΔF̂ = F̂(N24) − F̂(N0)` per cycle, with the **same absolute bar 0.021** (the bar is the Captain's tolerance for added wrong decodes in his log, A1.3, which a class-agnostic estimator measures better), CI by the cycle bootstrap on `ΔI` and `ΔN` with `s` and `FA` taken at their Wilson ends (conservative), and `SETTLED` requiring C-U **and** C-F. TOOL-WEAK and TOOL-FAIL keep today's rows.
- **Option 2:** keep the alarm descriptive and **word SETTLED as limited by U-COV** (for example "SETTLED on the rows the instrument can judge, U-COV = x %"), so the verdict cannot be read wider than its instrument.

### K4. Fix the configuration and the cost in the spec. AMENDMENT (small).

Write into §2: **both arms run**, N24 and N0 each **CQ-AP ON, v2 ON** (answer (d)); about 85 min PC; a 3-cycle dry run for the two flags together; the CQ-AP/OSD interaction stated as part of what is measured; the descriptive N24-versus-arm-B line. The "reuse after a 40-of-40 identity check" option stays only as a stated alternative at CQ-AP OFF.

### K5. Bar provenance for 0.15 pp (note, no row changes).

§2 derives 0.15 pp from "v2's 500-cycle NET half-width 0.107 and #272's 400-cycle 0.22". Those are **different contrasts** (a few dozen new fallback rows, high variance). The **same contrast is on file**: TRAIN's FIX24 minus FIX0 was +0.082 [+0.044, +0.123], a half-width of **0.040 at 621 cycles, about 0.044 at 500**. On that analogue the arm is well powered for the bar (assumption: normal, half-width 0.044, which is a plan, not a measurement):

| truth for NET (N24−N0) | P(SETTLED) | P(GRID) |
|---:|---:|---:|
| 0.000 pp | 1.00 | 0.00 |
| **0.082 pp (unchanged from TRAIN)** | **0.86** | 0.00 |
| 0.164 pp (doubled) | 0.005 | 0.09 |
| 0.250 pp (tripled) | 0.00 | 0.99 |

With v2's wider half-width (0.107) the same bar would read SETTLED only 24 % of the time at an unchanged 0.082, so the choice of analogue matters; TRAIN's is the right one. **Suggested edit:** cite TRAIN's interval for the 0.15 bar, and re-read NC-3 (SETTLED 0.65) against the table: if OSD's contribution is unchanged, SETTLED is about 0.86, and a doubling gives BETWEEN or GRID.

## Smaller points (no amendment)

- **F̂'s interval is not defined in §1.4.** The freeze must state it (the cycle bootstrap on `I` and `N`, `s` and `FA` at their Wilson ends), or K3's C-F has none.
- **`FA` is borrowed from WSJT-X's decodes and applied to ours.** Our extra decodes (weaker, more DX) may carry a higher true-implausible share than WSJT-X's, which inflates F̂; stated as a limit, not corrected.
- **Ghost texts** are generated and classified in memory only (NFR-021); the freeze records seeds, not texts. The tool's output is counts.
- **The 100 % bar on T-PROD** is fine and mechanical; the live-daemon route needs the daemon running during the check (it is, as of 16:32Z).
- **Time:** your 2 to 3 h for step 1 is realistic for the tool, plus about 1 h for T-CLASS and T-X.
- **E165, done on my side** (my ledger Q59): the four records that said "20 m" for replay nights are corrected in place (`dfda0fa9` on `qa/same-chain`), the PR #282 body and the #3 comment are edited, and the Developer's merged `proposal.md:20` is fixed in PR #283. This review states no band for any replay night except 40 m.

## What QA holds and will do on your amendments

Nothing is built. On your amended spec: the tool (`qa/fp-alarm/`, committed with its hash before any output), then T-PIN, T-CLASS, T-PROD (live route), T-SEP, T-POS and T-X, then the step 1 record; then the step 2 freeze, the dry run, and N0 and N24 on the Captain's PC window.
