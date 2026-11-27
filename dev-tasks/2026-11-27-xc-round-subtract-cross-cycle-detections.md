# Developer task: XC-ROUND, subtract the cross-cycle detections and run one more round (lean only)

**Date:** 2026-11-27
**Prepared by:** QA, from the Architect's spec `docs/decoder-rebuild/spec-xc-round.md` §2 (`arch/decoder-rebuild` `6e4e8bec`; docs only; not on `main` yet, so this task repeats what you need; read it with `git show 6e4e8bec:docs/decoder-rebuild/spec-xc-round.md`)
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("go ahead with the cross-cycle change spec", after he kept PAYLOAD-FIT), relayed by the Architect.
**Status:** Proposed. HK-011: `native/` and `src/` changes for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes (once per sprint).
**Branch:** `feat/xc-round`, **stacked on `qa/sprint-r1r4` `f20ae680`** (HK-008; that branch is PR #300, PAYLOAD-FIT, still open; it holds everything you build on: shim 20260081, the text gate removed, the probe). If #300 has merged when you start (`git fetch origin`), branch from `main` instead; a merge commit keeps `f20ae680` an ancestor, so either is the same code.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you. Read the per-assembly "Passed: N" lines (HK-022).

---

## 0. Why

After PAYLOAD-FIT, the largest remaining reason a decoded neighbour N is never subtracted is **XC**: N was found by the cross-cycle template stage. That is **27 / 52 / 89** neighbours on S40 / H40 / H20, **51 / 60 / 67 %** of the remaining 53 / 87 / 132 never-subtracted K2 neighbours (QA `payload-fit-result.md` §4.2). The stage runs in managed code **after** the native call has returned, so no native round can fit its detections: a weak signal beside one is never retried.

The code, at `f20ae680`:

- `Ft8Decoder.cs:1783`: the lean native call asks for the final residual (`WantResidual: xcOn`); it returns the buffer as of its last subtraction (`ftz_decoder.h:83` `out_residual`, `:208` `has_residual`; `ftz_decoder.c:1530`).
- `Ft8Decoder.cs:1875`: **after** the native call, the cross-cycle stage runs in managed code on that residual. It tests the messages published 30, 60 and 90 s earlier as known 79-tone templates (the tones come from `EncodeMessage` on the text, `:1964`) and publishes its detections as lean **batch 3** (`LeanBatchXc`, `:1660`). It only **reads** the buffer.
- The native rounds (`ftz_decoder.c:989`, `for round = 0..3`) are over by then.

The stage is ON at the station (`crossCyclePrior` true) and in the replay harness (batch 3 appears in every probe run). With the stage off, the new round must do nothing.

## 1. The design: ONE extra native call after the cross-cycle stage ("the XC round")

The native state is not kept alive between calls, so everything the round needs is passed back in.

| Id | What |
|---|---|
| **X1 A new native entry** (name yours; `ftz_xc_round` below) | One subtract-and-retry round, the same as a round 1-3 of `ftz_decode_cycle`. **In:** the normalised capture the cycle decoded (the fit reads its analytic signal, as at `:1035`: the entry computes it once, as the cycle does); the residual the cycle returned (in/out); for each detection to fit its **79 tones**, frequency and time; the cycle's remaining budget; the thread count; the same flags as the cycle (tier B / fast, CQ-AP, residual rules, probe). **Does:** fits each detection on the residual and subtracts it, with the same fit, the same sorted-order sum and the same "no valid fit" handling as the rounds; recomputes the residual's spectrogram; searches and decodes **only inside the patch windows** `[f - 50, f + 100]` Hz of the signals it subtracted, with the same candidate floor, tiers and accept rules as round 1-3. **Out:** the new results, their tiers and the stats (fits, `fitNone`, CPU and wall per stage) in the existing round-stats form; with the probe on, SUB and CAND rows with **round = 4**. **Not started** with less than `FTZ_RESIDUAL_RESERVE_MS` (1,500 ms) of the budget left (as `:1021`); **cancelled** on the deadline, all or nothing, as the rounds (`:1052`): a cancelled round publishes nothing and sets the abandoned flag. |
| **X2 Managed** (`DecodeLeanAsync`) | After the cross-cycle stage, if it published **at least one detection in batch 3 and the residual exists and effort is not Fast**, call the XC round with the batch-3 detections (the **live** ones only, never the shadow stage's). Publish its new results as **batch 4** through the same `MapLean` (text de-duplication across the whole cycle, plausibility filter, region and worked-before steps). Store them in the prior store as an ordinary batch, like batch 2. Batch 4 is delivered **only when non-empty**. The lean log line gets `b4=` and the round's stats (fits, `fitNone`, decodes, CPU). |
| **X3 Nothing else changes** | Rounds 0-3, PAYLOAD-FIT, the step-2e skip rule (the XC round fits **every** detection: the native side has no failed-candidate list for them), the cross-cycle stage itself and its thresholds, the DR-3 duplicate rule, the classic decoder, every default. No new flag. |
| **X4 Determinism and the hash table** | The results of the call are sorted (frequency, time, payload) **before anything touches the callsign table**, as the cycle's are, so thread count never changes the bytes. |
| **X5 Versions and documents** | The shim version moves (new export and structs: an ABI change; `libft8.dll` rebuilt, SHA256 stated; the Linux and macOS libraries are CI's). Run `tools/check_version_bump.py` and follow it for `VERSION`. **Amend `REQUIREMENTS.md` FR-108 in the same work** (last time it was missed and I had to ask: the sentence that says the lean cycle "SHALL publish three batches" and describes batch 3 must now say four, add the new shim number to its list, and add a changelog row); keep the OpenSpec change `lean-decoder` (tasks and delta) in step, strict. |

**Cost to watch (report, do not guess):** the round recomputes the analytic signal of the capture and the spectrogram of the residual, once per cycle that has a batch-3 detection (in the SUB-PROBE runs 126 of 170 S40 cycles, 221 of 240 H40 and 220 of 240 H20 had at least one: `lean.csv`'s `xc_detected` > 0), so state the per-call cost in your report.

## 2. Tests (unit tests, the spec's §2)

1. **(a) Native:** a synthetic residual with a strong signal **S** and a weak signal **W** 10 to 20 Hz away (the existing modulator test helpers, as `LeanEnginePayloadFitTests` and the two-signal case of `LeanEngineProbeTests` do). Called with S's tones and position, the XC round **decodes W** (and, with the probe on, has a round-4 `SUB` row at S's position). Called with **no detections** it decodes nothing and leaves the residual unchanged. **Run the "decodes W" test against the 20260081 binary first** (it has no such entry, so say what "red" means here: the entry does not exist; or show W undecoded by a round-less path) and state that it passes after.
2. **(b) Determinism:** the XC round's output is the same bytes at 1, 2 and 16 threads.
3. **(c) Managed:** with the stage off, with no batch-3 detection, or on Fast, the round is **not called** (no `b4`). With a detection, **batch 4 comes after batch 3**, and a text already published earlier in the cycle is **not published again**. Use the existing cross-cycle test fixtures (`Ft8Decoder` cross-cycle tests) and a fake or a thin seam; say which.
4. **(d) Bounds:** the existing ASan + UBSan job and fuzz cover the new entry; add it to the fuzz driver if the other entries are there (10,000 runs, including the probe on). Run it locally if you can.
5. **(e) Nothing else moved:** every existing test passes **unchanged**, in particular the determinism, lean golden, DR-3 duplicate, SUB-PROBE and PAYLOAD-FIT tests. If a golden test changes because batches 1-3 moved, **do not edit it**: stop and report (QA's free check is that batches 1-3 are byte-identical in the replay).
6. **Run each project separately** and quote each "Passed: N": Config, Web, Daemon, Ft8 (also at `DOTNET_PROCESSOR_COUNT=4`), and the JS runner.

## 3. After your hand-back (QA, not you)

HK-039 review, then the harness part (reading round-4 probe rows and batch 4: tell me exactly what the rows are, as for SUB-PROBE), `pre_merge_check` once at the sprint PR, and **one replay**: exactly the PAYLOAD-FIT arm (lean, 16 threads, `--lean-probe 1`, LC-BASE's L flags with the cross-cycle stage on) on S40 (170), H40 and H20 (240 each), about 20 minutes, against the PAYLOAD-FIT runs already on disk (`_qa-scratch\lc-base\runs\pf_*`). **Free check: batches 1-3 byte-identical to the baseline in every cycle** (the new round runs after them); if not, QA stops and tells the Architect. QA reports in the PAYLOAD-FIT format: Table 1 with deltas, the cost, how many of the 27 / 52 / 89 XC cases now have a round-4 `SUB` row for N and a matched T, the new never-subtracted split, the knock-on, and the ours_only check on the added decodes. No bars; the Captain decides.

## 4. Out of scope

Anything in rounds 0-3, the cross-cycle stage's detector or thresholds, the shadow stage, a second XC round, the K2 decode step (bit metrics / BP: the next lever, not this task), the daemon and Settings page, the classic decoder, any default.

## 5. Report back

The commit SHA; the new shim number and `libft8.dll` SHA256; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; the entry's signature and the structs (a table: for QA's harness reader); the probe row layout for round 4; the red-before / green-after statement for test (a); how the managed test (c) was built; the per-call cost; and anything that differs from the neighbouring tests' pattern.
