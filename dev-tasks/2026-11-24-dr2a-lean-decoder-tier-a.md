# Developer task: DR-2 step 2a, the lean engine's first cut (`ftz_decode_cycle`: spectrogram + candidates + tier A), behind `decoder.engine`

**Date:** 2026-11-24
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** `docs/decoder-rebuild/spec-dr2-lean-decoder.md` §2 and §3 step 2a, and `plan.md`, on `arch/decoder-rebuild` `68f7f15e` (read with `git show arch/decoder-rebuild:docs/decoder-rebuild/<file>`). The Captain approved the plan on 2026-11-24 and cut the test requirements the same day.
**Status:** Proposed. HK-011: `src/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge.
**Branch:** a new branch `feat/lean-2a` off `origin/main` (QA re-checks the SHA when you start).
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. **No replay, no on-air period, no extra nights, no statistical gate** for this step. Run tests per project (HK-022; do not trust a bare `dotnet test OpenWSFZ.slnx` and read the per-assembly "Passed: N" lines).

---

## 0. Why

The classic decoder runs up to nine native passes and runs for CPU the Captain no longer accepts. The plan replaces it with one engine, built in four steps. This step makes the skeleton exist and be selectable: one native call per cycle that decodes what the classic **primary pass** decodes, nothing more. Later steps add tier B and CQ-AP (2b), the subtract-and-retry loop (2c), and XC wiring with three batches (2d).

## 1. What to build

| Id | What |
|---|---|
| **D1 Native entry** | New folder `native/ftz_decoder/` with `ftz_decode_cycle(pcm, n, params, out_results, cap, out_stats)`: **S1** spectrogram, **S2 steps 1, 2, 6, 7** only (candidates by `ftx_find_candidates` with **today's primary parameters**, tier A for every candidate: magnitude LLR, BP, CRC, unpack; one text published once; **results sorted** by frequency, then time, then text before anything touches the hash table or leaves the call). **No tier B, no CQ-AP, no OSD, no subtraction loop.** Reuse the building blocks of spec §2.2 (ft8_lib `monitor.c`, `ftx_find_candidates`, `ft8_extract_likelihood`, `ldpc.c`, `crc.c`, `message.c`, our hash-table code, **semantics unchanged**). Do not change window, oversampling or input scaling (closed arms). 🛑 WSJT-X may be read for method only; not one line copied or ported (licence policy). Every new file starts with a provenance header. |
| **D2 Params** | `params.threads` (default **2**, setting `decoder.threads`, 1 to 8): a fixed worker pool created once, never per cycle. Candidates are processed in parallel; the sort in D1 makes the output independent of the thread count. |
| **D3 Memory safety** | Every buffer index bounds-checked. A native error returns an error code; C# logs it, publishes what it already has and carries on with the next cycle; it never crashes the daemon. |
| **D4 C# engine switch** | `decoder.engine` = `classic` (**default**) or `lean`, read once per window, effective on the next cycle, overlay POST (HK-035), file and API only (no Settings-page control). With `lean` the cycle goes through `ftz_decode_cycle` and the **classic code path is not entered**. With `classic` (or the key absent) every native call, row, batch, counter, log line and `DecodeResult.Path` value is as on the base (a pinned golden, see §2). Publish: one batch (the lean engine's batch 1) through the existing publish path, text de-duplication and `IsPlausibleMessage` unchanged. |
| **D5 Log line** | One INFO line per lean cycle, aggregates only (HK-037): per-stage wall ms and CPU ms, candidates, tier-A decodes, threads, abandoned flag, error code. No message text. |
| **D6 CI** | A CI job that builds and runs the native tests under **AddressSanitizer on Linux**. |
| **D7 Documents** | `REQUIREMENTS.md`: a new FR for the engine switch and the lean engine's step-2a behaviour. OpenSpec change `lean-decoder` (proposal, design, delta spec, tasks), validated `--strict`. **VERSION:** the key is internal and defaults to `classic`, so decide per the repo's user-facing rule, say which, and run `check_version_bump.py` (G9b) after committing. |

## 2. Tests (unit tests only)

1. **Primary-pass equality.** On the committed `synth-qso-01.wav` .. `synth-qso-03.wav`: the lean engine's decoded **texts** equal the classic **primary pass's** texts, with CQ-AP and OSD off. Compare the SET of texts (never rendered text across processes, MEMORY.md hash-table note).
2. **Determinism.** The same audio, the same starting hash state, run twice: **byte-identical** output, mechanically diffed. Run it at `threads` = 1, 2 and 4: the same output at all three.
3. **Fuzz.** At least 10,000 runs on random, clipped, silent and DC audio, plus truncated buffers: no crash and no sanitizer report.
4. **Engine switch.** `classic` and an absent key leave the golden unchanged (record it from the base build first); `lean` routes to the native call and not the classic path; a native error code is logged and the next cycle runs; the config key round-trips, an unrelated save keeps it, an unknown value reads `classic`.
5. **Message-text rule.** The log line carries counts and times only.
6. The existing suites stay green, run per project.

## 3. Notes for the later steps (QA read these from the code on `main`, 2026-11-24; the Architect asked for them)

These are not part of step 2a. They are recorded here so the lean engine does not have to rediscover them.

**Tier B eligibility (step 2b).** Today's coherent fallback takes a candidate from the cycle's snapshot when it is **not already decoded** (`cr->decoded` false) **and** not a duplicate position (an earlier candidate in the same snapshot with the same `freq_hz` and the same `dt` and the same decoded flag). Source: `ft8_shim.c`, `ft8_coherent_fallback_plan` (`:2845` to `:2878`), the same test in `ft8_coherent_fallback_run`. Each eligible candidate: fine sync, coherent LLRs (multi-set on by default), BP, CRC. A CRC-valid output whose payload is already known is dropped. For a new payload, **F1b** is computed and the row is published iff `F1b <= CF_T1_DB = 17.552446 dB` (`coherent_fallback.h:39`). Rows with the same payload at several lattice positions: the first, in candidate order, whose estimate is not at the window edge is kept (`CoherentFallbackSelector.Select`).

**Where today's defaults differ from "gated only"** (`DecoderConfig.cs`): `coherentFallbackEnabled` true, `coherentFallbackMultiSet` true, `coherentFallbackAudio` Both, **`coherentFallbackResidualUngated` true** (a residual-run row that F1b gated out is published anyway, R-F4), `lateSubtractionRound` true, `coherentFallbackResidualCandidates` false (the v2 third run is OFF by default). **The station's own `config.json` may differ from these defaults.** DR-0's arm A6 is the one that defines "today" for the targets; the Developer must confirm the lean engine's reading of F1b and the ungating against A6's actual config, not against this paragraph alone.

**Accept gates for residual decodes (step 2c).** What this build applies to a decode from residual audio, found in `Ft8Decoder.cs` and `SubtractionPass.cs`:
- the pass-1 candidate floor `kMinScorePass2` (default **10**, valid 5 to 30) and the candidate caps (pass 0: 140, pass 1: 200), shim `K_MIN_SCORE_PASS2`;
- text de-duplication by message (`seen`) and `IsPlausibleMessage` with the grammar store, applied in `MapNative` to every batch;
- for fallback rows on residual audio: F1b `<= 17.552446` dB, **or** admitted by the R-F4 ungating when it is ON;
- the v2 third run's own rule (`ResidualRunMaxFreqHz = 1097`, new-text rows only, F1b-passed rows only) applies only when `coherentFallbackResidualCandidates` is ON (default OFF).
**Not yet verified by QA, to confirm in step 2c:** the OSD thresholds the residual pass applies (`osdCorrThreshold`, `osdNhardMax`) and any further gate inside `SubtractionPass.RunThirdPassAsync` / the late-round fit. QA read the call sites but not every line of the pass; step 2c's task will list them once read.

## 4. Out of scope

Tier B, CQ-AP, OSD, any subtraction, XC wiring, the three-batch publishing, `effort`, new decode ideas, threshold re-tuning, any closed arm.

## 5. Report back

The commit SHA, the per-project test lines ("Passed: N"), where the batch-1 hand-off was done (one call or a callback; the spec leaves it to you), the ASan CI job's first result, and the VERSION decision.
