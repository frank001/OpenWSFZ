# SUB-FEAS Two-Stage Publish: Acceptance Report (S1, S2, interim managed flag-OFF comparison)

| Field | Value |
|---|---|
| Run | 2026-09-30, orchestrator 15:00:54Z → 17:07:32Z (DONE, orphan check empty, 18 of 18 harness invocations rc 0) |
| Build under test | `feat/sub-feas-two-stage-publish` @`247ac391`; `libft8.dll` actual `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` = pinned (unchanged from Stage A; no native change) |
| S1 reference | `feat/sub-feas-speed-redesign` @`ca0bcd9b`, same `libft8.dll` `ee00d118…990e4c` |
| Managed flag-OFF reference | `2b39cf18`, `libft8.dll` `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` = pinned |
| Harness / orchestrator | commit `a918aa29` (Replay81 with `on`/`two1`/`two` modes, committed before the run); harness DLLs: base `0e22fd5752e1…`, ref `3a8d3772ddd2…`, two `8dde50fa93bb…` (full values in `preflight.json`) |
| Selections | S2: §8.1 `selection.json` `730d6ea61f25…`; S1: `e1_selection.json` `f58c0c7bd3ed…` (161 cycles) |
| Spec | Architect's spec §5b, §5c (Amendments 2, 3) |
| Machine | Ryzen 7 7800X3D (16 logical), WSJT-X closed (asserted by the orchestrator) |
| `--filter` | none (harness replay, not a test run) |

> 🔴 **Bottom line: S1 PASS (161/161), S2 PASS (median and max terms), interim managed flag-OFF comparison identical (161/161).**
> The split changes timing only: the union of batch 1 and batch 2 equals Stage A's single-batch flag-ON output on every cycle, and
> batch 1 costs what flag OFF costs (time to batch 1 = 1.00 × the flag-OFF whole call). No crash, no abandon in any heavy cycle.
> **No decode-rate claim.** This is not the flag-OFF merge control (that runs once, at the merge).

## S1: the split changes timing only (161 E1 cycles, fresh processes, same cycles in the same order, one call per cycle)

Outcome keys are the numeric fields (freqHz, dt, snr), compared as sorted multisets (stricter than "as a set").

| Predicate | Result |
|---|---:|
| (a) union(batch 1, batch 2) == single-batch flag-ON output of `ca0bcd9b`, per cycle | **161 / 161** |
| (b) batch 1 == flag-OFF output of the same build, per cycle | **161 / 161** |
| **S1 (both)** | **PASS, 161 / 161** |

Totals over the 161 cycles: batch 1 = 3 842 decodes, batch 2 = 692 (non-empty in 157 cycles), reference flag-ON = 4 534 (= 3 842 + 692), flag-OFF = 3 842.
**Second level (informational):** the text-hash comparison matched on (a) in 161 / 161. On (b) it matched in 151 / 161; the 10 differing
cycles (stamps in `rows.json`) are identical at the numeric level. That is expected and is **not** the change: the flag-OFF process never decodes the residual
messages, so its callsign hash table has a different history, and a hashed-callsign placeholder can resolve differently. Reported, not claimed as a defect.

## Interim managed flag-OFF comparison (NOT the merge control)

`DecodeAsync` with the flag OFF, `2b39cf18` vs the two-stage build, fresh processes, same 161 cycles, same order, identical native call sequence: **161 / 161 identical, ordered,
at both the numeric and the text-hash level.** Recorded as an interim managed datum: it cost nothing extra (a by-product of S1's method). The flag-OFF control proper
(native and managed) is a merge gate, run once on the build the Captain decides to merge.

## S2: batch-1 latency (905 flag-ON cycles, H ∪ M, alternating flag-OFF `DecodeAsync` and two-stage, same process, WSJT-X closed)

| Run | n | time to batch 1, median / p95 / max (ms) | flag-OFF whole call, median / max (ms) | ratio of medians (bar ≤ 1.05) | whole call incl. batch 2, max (ms) |
|---|---:|---|---|---:|---:|
| 20260922_2056 | 261 | 485.7 / 539.9 / 560.3 | 483.4 / 569.9 | **1.005** | 6 496 |
| 20260923_1730 | 506 | 487.3 / 553.0 / 720.4 | 485.7 / 767.5 | **1.003** | 9 463 |
| 20260925_2010 | 138 | 498.6 / 550.8 / 580.8 | 500.9 / 580.9 | **0.995** | 6 085 |

- **Median term: PASS** in all three runs.
- **Max term (Amendment 3, read per cycle against the same-session flag-OFF call): PASS.** Cycles whose own flag-OFF call exceeded 1 000 ms: **0 (0.0 %)**, so the term is evaluable; the largest time to batch 1 was **720.4 ms ≤ 1 000 ms**.
- Batches: 22 440 batch-1 decodes and 4 100 batch-2 decodes over 905 cycles; batch 2 non-empty in 892 cycles.
- Stability: 0 access violations, 0 contained exceptions, 0 CSV rows with an exception; `Sub-feas residual pass:` log lines equal the flag-ON cycles in all six blocks; **0 deadline abandons over the 605 heavy cycles**.
- The whole-call maximum including batch 2 was 9 463 ms, inside the 13 s bound (Stage A's quiet-machine maximum was 8 650 ms; the residual pass alone peaked at 8 968 ms here against 8 242 ms in Stage A; descriptive, run-to-run).

## S3: consumer tests (a)-(f) and the accepted (g)-(j): every letter has a test

Tests on `247ac391` (`tests/OpenWSFZ.Daemon.Tests/DecodePumpTests.cs` unless stated). **No letter is without a test.**

| Letter | Requirement | Test (DisplayName / method) |
|---|---|---|
| (a) | answerer and caller receive exactly one batch per flag-ON cycle, equal to batch 1 | `S3(a)` / `AnswererAndCaller_ExactlyOneBatch_IsBatch1` |
| (b) | answerer's idle snapshot after a flag-ON cycle equals batch 1 | `S3(b)+(h)` / `RealAnswerer_SnapshotIsBatch1_ExternalReplyForBatch2StationIgnored` (real answerer service) |
| (c) | ALL.TXT holds batch 1 then batch 2, same stamp, no duplicate text | `S3(c)` / `AllTxt_Batch1ThenBatch2_SameStamp_Unfiltered`; the no-duplicate-text half also in `TwoStageDecodeTests` (`Ft8.Tests`): `UnionEqualsSingleBatchOutput` |
| (d) | panel receives two `decode` events and shows the union | `S3(d)` / `Panel_TwoEvents_Union` (server side); **and** `web/js/decodePanelBatches.test.js` (`handleDecodes` prepends and never clears; run with `node --test`, 4 / 4 here, outside `dotnet test`) |
| (e) | archive enqueued once, at batch 1, pass-0 count | `S3(e)` / `Archive_OncePerCycle_WithPass0Count` |
| (f) | flag OFF: one publish per cycle | `S3(f)` / flag-OFF single-path test, plus `TwoStageDecodeTests.FlagOff_OneBatch_Identical` (P-9) |
| (g) | manual engage on a batch-2 row, characterised | `S3(g)` / `TwoStageEngageCharacterisationTests.ManualEngage_OnBatch2Row_Characterised` (behaviour recorded, unchanged: Captain's decision) |
| (h) | external reply naming a batch-2 station ignored with the existing log line | `S3(b)+(h)` (same test as (b)) |
| (i) | pump starts no next window before batch 2 is published or abandoned | `S3(i)` / `Pump_StaysSerial` |
| (j) | external reporting sends no cycle-level message twice | `S3(j)` / `ExternalReportingServiceTests.TwoBatchCycle_SendsNoCycleLevelMessageTwice` |

**Did they run in QA's unfiltered run?** The run was `dotnet test OpenWSFZ.slnx` (**no filter**) on a detached checkout of `247ac391`: **1 646 passed, 0 failed** (Traceability 34, LicenseInventory 24, TestSupport 12, Rig 41, Audio 23, Config 105, E2E 7, Web 318, Daemon 665, Ft8 417). That log prints per-assembly totals, not test names, so the names are confirmed two other ways, stated here so neither is mistaken for the unfiltered run: (1) `dotnet test tests/OpenWSFZ.Daemon.Tests --no-build --list-tests` on the **same built assemblies** lists all nine `S3(...)` tests (a, b+h, c, d, e, f, g, i, j); (2) a **supplementary filtered** run, `dotnet test tests/OpenWSFZ.Daemon.Tests --no-build --filter "DisplayName~S3"`, executed them: **9 / 9 passed** (this filtered run is supplementary and is not offered as the unfiltered result). The P-1/P-3/P-8/P-9 tests in `TwoStageDecodeTests` (`Ft8.Tests`) are inside the unfiltered 417.

## Load disclosure and a descriptive datum (Architect's request)

The Engineer ran CPU-heavy work on this machine while S1 was running (13 unfiltered Web.Tests passes, a daemon build, an isolated daemon on port 18193 and a Playwright run, reconstructed
from file timestamps: ~15:06Z to 15:25Z). **All of it falls inside the S1 phase (15:00:54Z to 15:34:51Z). The S2 timing blocks began at 15:34:51Z, after it, so no S2 cycle overlapped any disclosed window** and S2's same-session flag-OFF comparison is unaffected.
S1 compares outcomes, not timings, and the S1 logs show **0 deadline abandons, 0 contained exceptions and 0 warnings** in every block, so no residual decodes were lost to the load.
**Descriptive datum, no bar and no claim:** in the overlapped `ref_on` block the largest residual-pass `elapsedMs` was **10 795 ms**, against **8 242 ms** (Stage A acceptance, quiet machine) and **8 968 ms** (this S2, quiet machine), the residual pass alone in each case. It is the only measurement we have of the pass under unrelated background load; it stayed inside the deadline (the fits are cancelled at 11.0 s of the pass's budget), and it bears on live use with other software running.

## Hygiene, deletion and blind spot

- 🔒 **HK-037 / NFR-021.** The Architect ruled (2026-09-30) that a text-derived hash counts as message identity. S1's `--outcomes` files carried an 8-hex-digit SHA-256 prefix of the message text per decode (gitignored, never staged, disclosed before this report). **After S1's rows were computed, the 12 files `artefacts/sub_feas_twostage_acceptance/s1/*.outcomes.txt` were DELETED** (12 files). The harness now writes numeric-only outcome lines by default; the hash is behind `--outcome-text-hash true`, which no standard run sets (`70c01fc9`). Nothing with message identity is committed: this report and `rows.json` carry counts, numeric aggregates and stamps only.
- **Blind spot (HK-026):** one machine; no real cycle above 31 signals; busy cycles only; S2 times the **hand-off** of batch 1 inside the decoder, **not its delivery to a WebSocket client** (that is S2b, report-only, not yet run). A pass says "the split loses nothing and adds nothing before the first publish on this machine".
- **Not done here:** S2b; the flag-OFF control (merge gate); any decode-rate measurement; the Linux/macOS runs.
- Artefacts committed: `report.md`, `rows.json`, `preflight.json`.
