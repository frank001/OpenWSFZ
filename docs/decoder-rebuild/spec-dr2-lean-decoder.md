# DR-2 to DR-4: the lean decoder, the switch-over, and deleting the old one

**To:** QA, who turns this into Developer tasks (HK-015). One task per step 2a–2d, then DR-3 and DR-4.
**From:** Architect, 2026-11-24
**Plan:** [`plan.md`](plan.md) §4–§5, approved by the Product Owner on 2026-11-24 with all five §9 answers. The process is the plan's §6 (light).
**Can start:** step 2a can start now, alongside DR-0. Step 2b and later steps need DR-0's baseline table (`dr0-result.md`).

---

## 1. Targets (the Product Owner's §9 answers, made mechanical)

All are measured on the fixed test set (`test-set.md`), against DR-0's **A6 baseline**, the same way as DR-0 (§2.1 of the DR-0/1 spec).

| # | Bar | Rule |
|---|---|---|
| T1 | CPU | `cpu_net(lean) ≤ 0.25 × cpu_net(A6)` on the station PC |
| T2 | Decodes | `rate(lean) ≥ rate(A6) − 1.00 pp` |
| T3 | False side | `ours_only(lean) ≤ ours_only(A6) + 0.50 pp` |
| T4 | Time budget | `last_p95(lean) ≤ 3,000 ms` and `abandoned = 0` on the station PC |
- **T1–T4 are measured ONCE, in one Slice 40 replay at step 2d.** They are targets to report, not gates: if one is missed, QA gives the Product Owner the numbers and he decides.
- **If DR-1 shipped,** the comparison is still against **A6** (today's full decoder).
- *(Revised 2026-11-24 at the Product Owner's direction: there is no longer a `sol` check, a Slice 20 replay, or a replay per build step.)*

## 2. Design

### 2.1 Shape

```
C#  Ft8Decoder (engine = lean)
      │  one call per cycle
      ▼
native  ftz_decode_cycle(pcm, params, ...)       ← new, native/ftz_decoder/
      S1  spectrogram
      S2  candidates → tier A → tier B → CQ-AP     → results tagged round 0   (batch 1 published from here*)
      S3  rounds 1..3: subtract → re-spectrogram → patch search → S2 on patch candidates
      returns: all results (tagged by round), the final residual buffer, stats
      │
C#   S4  XC on the final residual buffer (existing CrossCycleTemplateStage, unchanged)
     publish: batch 1 (round 0), batch 2 (rounds 1–3), batch 3 (XC)
```

\* **Batch 1 must leave before S3 starts.** Do this either with two native calls (`ftz_decode_first` then `ftz_decode_rest` on a context handle) or with a callback. It is the Developer's choice; state it in the task result.

### 2.2 Building blocks: reuse, don't rewrite

| Need | Reuse | Licence |
|---|---|---|
| STFT / waterfall (Hann, time and frequency oversampling 2 as today) | ft8_lib `monitor.c` (patched copy) + KISS FFT | MIT / BSD-3 |
| Costas candidate search | ft8_lib `ftx_find_candidates` | MIT |
| Tier A bit metrics | ft8_lib `ft8_extract_likelihood` (as the primary today) | MIT |
| LDPC (belief propagation), CRC, unpack, hash table | ft8_lib `ldpc.c`, `crc.c`, `message.c`, our hash-table code in the shim, **semantics unchanged** | MIT / own |
| Fine sync | `ft8_refine_candidate` (`sync_refiner.c`) | own |
| Tier B bit metrics | `cf_estimate`, `cf_v3_llrs`, `cf_multiset_llrs*` (`coherent_fallback.c`, `coherent_llr.c`) | own |
| Subtraction fit | `ft8_subfeas_fit_signal` (`subfeas_fit.c`) | own |
| CQ-AP | today's CQ-AP code | own |

🛑 WSJT-X may be read for method only; not one line is copied or ported (licence policy). Each new file starts with a provenance header.

### 2.3 Stage rules

**S1, spectrogram.** As the primary today. After each subtraction round the residual's spectrogram is recomputed in full. That is cheap (measure it and put it in the stats); the saving comes from searching only the patches. **No change to window, oversampling or input scaling** (closed arms).

**S2, decode one candidate list.**

1. Candidates: `ftx_find_candidates` with today's primary parameters (count and minimum score). No candidate-budget change (closed family).
2. **Tier A** for every candidate: magnitude LLR → BP → CRC → unpack. Success ⇒ result.
3. **Tier B** for a failed candidate **only if** it would have been eligible for today's coherent fallback on the same audio. QA lists that selection rule from the code in the task, including the F1b gate as it applies at today's defaults. Steps: fine sync → coherent multi-set LLRs → BP → CRC → unpack.
4. **CQ-AP** on candidates that failed both tiers, exactly as today (FR-103).
5. **OSD:** OFF in the lean engine, **unless DR-0 shows OSD `NET` ≥ 0.30 pp**. In that case it runs where it runs today, behind `params.osd`.
6. Within a cycle, a message text is published once, as today. Two candidates that decode to the same text: keep the first in the deterministic order (rule 7).
7. **Determinism:** candidates are processed in parallel by `params.threads` workers, but the results are **sorted** (frequency, then time, then text) before anything touches the hash table or leaves the call. Two runs on the same audio and the same starting hash state must give byte-identical output; this is mechanically diffed in a test.

**S3, the subtract-and-retry loop.** Round r = 1, 2, 3:

1. Subtract every result found so far that has not been subtracted yet (data-aided fit) from the residual buffer.
2. Recompute the spectrogram of the residual.
3. **Patch search:** run `ftx_find_candidates` on the residual, then keep only candidates whose base frequency lies within **[f − 50 Hz, f + 100 Hz]** of a signal subtracted **in this round**.
4. Run S2 (tiers A, B, CQ-AP) on those candidates.
5. **Accept rules for residual decodes:** exactly the gates today's defaults apply to decodes from residual audio (residual pass, third pass, fallback-on-residual, the 1097 Hz rule of FR-104 where it applies). QA lists them from the code in the task. **No new gates and no removed gates.**
6. Stop when a round adds nothing new, at round 3, or when the cycle deadline (today's 13 s budget, minus the publish reserve) would be passed. An abandoned round publishes nothing from that round; earlier rounds stand.

**S4, XC.** The existing stage, unchanged, reading the final residual buffer. Priors are recorded from batches 1 and 2, as today from batches 1–5.

**Effort setting.** `decoder.effort`:
- `normal` (default): everything above
- `fast`: no tier B, S3 limited to 1 round

### 2.4 Threads, safety, logging

- **`params.threads`:** default **2**, setting `decoder.threads` (1–8). A fixed worker pool, created once.
- 🔴 **Memory safety** (the 2026-09 crash history):
  - every buffer index is bounds-checked
  - a CI job builds and runs the native tests under AddressSanitizer on Linux
  - a fuzz test of at least 10,000 runs on random, clipped, silent and DC audio, plus truncated buffers, with no crash and no sanitizer report
  - a native error returns an error code; C# logs it, publishes what it already has, and carries on with the next cycle. It never crashes the daemon.
- **One log line per cycle, aggregates only (HK-037):** per-stage wall ms and CPU ms, candidates, tier-B count, rounds run, results per round, XC detections, abandoned flag.

### 2.5 Switch and settings

- `decoder.engine` = `classic` (default until DR-3) or `lean`. It takes effect at the next cycle.
- With `engine = lean`, the classic decoder's keys are ignored: depth, subtraction, the five fallback keys, late round, OSD keys, `kMinScorePass2`. They stay valid in the config until DR-4.

## 3. Steps and their checks

| Step | Deliverable | Check (mechanical) |
|---|---|---|
| **2a** | `ftz_decode_cycle` with S1 + S2 tier A only (no tier B, no CQ-AP, no S3), engine switch, log line, ASan CI job, fuzz test | Unit test: on the committed `synth-qso-01..03.wav`, the decoded texts equal the classic primary's (CQ-AP and OSD off). Determinism unit test. |
| **2b** | Tier B + CQ-AP | Unit tests |
| **2c** | S3 loop | Unit tests |
| **2d** | S4 wired up, 3-batch publishing, `effort = fast` | Unit tests + **the one Slice 40 replay** (§1) |

- **Every step:** unit tests and QA's code review (HK-039). The Developer works in a separate session (HK-011).

## 4. DR-3: switch over

**The Product Owner flips it when he is happy with it.** There is no test step and no waiting period. The Developer then sets the default to `lean`, migrates `engine` once, **bumps VERSION one minor**, and updates the FRs (new FR for the lean engine).

## 5. DR-4: delete the classic decoder

QA writes the task after DR-3 merges. It removes:
- **C#:** `SubtractionPass` third-pass / late-round paths, the coherent-fallback orchestration (`CohFallbackParallelRunner`, `CohFallbackAudioSelector`), the early-decode path, the classic batch numbering, and the classic interop entries
- **Native:** the shim's classic multi-pass driver and anything only it calls
- **Settings:** the retired keys. They stay accepted and ignored, with a one-time log line, and are dropped from `config.example.json`.
- **Tests and log lines** that cover only removed code
- **`REQUIREMENTS.md`:** FR-082, FR-083, FR-099–FR-102 and FR-104 marked retired, with a pointer to the lean FR. FR-105 (XC) is reworded for the new batches.
- **OpenSpec:** the matching changes archived

**Checks:** unit tests and review.

**Plan success measure (reported, not a gate):** the `src/OpenWSFZ.Ft8` plus decoder-native line count, before and after, with the goal of under half.

## 6. Out of scope

New decode ideas, threshold re-tuning, and any closed arm (window, input scaling, OSR, candidate budgets, hash eviction). None of these are on the table until DR-4 has landed.
