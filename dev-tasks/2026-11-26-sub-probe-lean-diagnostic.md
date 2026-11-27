# Developer task: SUB-PROBE, a test-only diagnostic probe in the lean decoder

**Date:** 2026-11-26
**Prepared by:** QA, from the Architect's spec `docs/decoder-rebuild/spec-sub-probe.md` §2 (`arch/decoder-rebuild` `028ad6ac`)
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-26: option A, "measure first", with the baseline replay folded into the probe's replay (relayed by the Architect).
**Status:** Proposed. HK-011: `native/`, `src/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes (once, in the sprint PR).
**Branch:** `feat/sub-probe`, **stacked on `feat/dr3-lean-default`** (`4fa2c637`, or on `main` once PR #295 has merged: check `git fetch origin`), HK-008. You can start now.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you. Read the per-assembly "Passed: N" lines (HK-022).

---

## 0. Why

CS-MAP (`qa/rr-study/results/2026-11-26-lc-base/cs-map-result.md`) showed that the lean engine usually decodes the **strong** neighbour of a weak signal it misses, but that decoding the neighbour barely lowers the miss share; the miss share rises to 43 to 51 % when the neighbour is more than 10 dB stronger. QA's DR-3 replay then lifted lean on S40 from 81.52 % to 84.70 %, 213 of the 216 extra decodes in rounds 1 to 3, so the picture moved. The probe tells, for each such missed weak signal, **which of three things failed:** (1) *subtraction* (too much of the neighbour is left in the residual), (2) *search* (the weak signal never becomes a candidate, or is filtered out), (3) *decode* (it is a candidate, but belief propagation, CRC or a gate rejects it). The result picks the first decoder change.

## 1. What to build

**Test-only, off by default.** A new flag **`FTZ_FLAG_PROBE`** in `ftz_params_t.flags` (next to `FTZ_FLAG_SKIP_FITS`), set only by the replay harness (QA's `Ft8.FitProbe`, `--lean-probe 1`). The daemon never sets it.

| Id | What |
|---|---|
| **D1 The flag** | **Flag off: nothing changes**, no extra work, no extra memory, no extra branch cost worth measuring. **Flag on: the published decodes are byte-identical to flag off** (frequency, dt, SNR, text, tier, round, in the same order), at every thread count. The probe must read, never write, decoder state: no change to the residual, the candidate list, the order or the RNG-free determinism. |
| **D2 The probe buffer** | With the flag on, the native call fills a per-cycle probe buffer that the managed side can read after the call (your design: a caller-supplied buffer with a count, as the other per-cycle outputs do; bounds-checked; an overflow sets a flag and drops further rows, it never writes past the end; size it for the worst case you can state). **Numbers only: no message text, no payload** (HK-037). |
| **D3 Managed side** | `Ft8LibInterop` / `LeanCycleParams` get the flag (a bool, default false) and `LeanCycleOutcome` gets the probe rows (empty when off). `internal` is enough; the daemon and `Ft8Decoder` do not use it. QA writes the harness part (`--lean-probe`, `probe.tsv`) after your hand-back: tell it exactly what the rows are in the report. |
| **D4 Documents** | The shim version moves (new buffer and flag: ABI change), `libft8.dll` rebuilt as in 2e and DR-3; the OpenSpec change `lean-decoder` gets a section (tasks, delta spec; strict). **No VERSION bump** (test-only, not user-facing; run `check_version_bump.py`); no new FR; add a changelog row only if a gate asks. |

### The three record types (spec §2)

| Record | Written for | Fields |
|---|---|---|
| **`SUB`** | every signal subtracted, in every round | round; frequency (Hz); time (s); the fit's amplitude; **suppression dB** = 10·log10(power in the signal's footprint **before** ÷ **after** the subtraction), measured on the waterfall over the signal's **8 tone columns × 79 symbols** (state exactly which two waterfalls you compare: the round's input audio's and the residual's, and how the footprint is placed from frequency and time) |
| **`CAND`** | round 0 and every round 1 to 3 | for **every** candidate `ftx_find_candidates` returns (before any filter): round; frequency; time; sync score; `kept` (it passed the round's patch filter and the floor, or round 0); the outcome code below |
| **`LOW`** | rounds 1 to 3 only | one **extra** `ftx_find_candidates` call on the round's residual with **floor 0 and cap 400**, **not decoded**: frequency, time, score. It shows the candidates the normal floor (`kMinScorePass2`, read as the residual search's minimum score) or the cap cut off. Its result is never used by the decoder. |

**Outcome code per kept candidate** (one per `CAND` row): `A_OK` tier A decoded · `A_BP` tier A failed in belief propagation (also record the final number of unsatisfied parity checks) · `A_CRC` failed CRC · `B_NE` not eligible for tier B · `B_OK` / `B_BP` / `B_CRC` the same for tier B · `CQ_OK` / `CQ_FAIL` · `DUP` decoded but dropped as a duplicate (the DR-3 rule) · `GATE` decoded but dropped by an accept gate (**name the gate as a code**) · for candidates that are not kept: `NOT_KEPT_PATCH` (patch filter) and `NOT_KEPT_CAP` (cap). Every candidate gets exactly one code. The numeric values are yours to choose and to document in the header comment; QA reads them from the report.

## 2. Task order

No UI change, so no HK-005 screenshots. Order: D1 to D4, then the tests (section 3).

## 3. Tests (unit tests, spec §2)

1. **Off against on is byte-identical:** on the committed `synth-qso-*.wav` files (all of them), the published output with the flag off equals the output with the flag on, field for field; also at 1, 2, 4, 8 and 16 threads (the existing determinism test pattern). The probe rows exist only with the flag on.
2. **A two-signal case:** a synthetic WAV with a strong and a weak signal 10 Hz apart (the existing modulator test helpers, as the two-copy fixture of `LeanEngineDuplicateRuleTests` does): the probe has **one `SUB` row for the strong signal with suppression greater than 0 dB**, and **a `CAND` row near the weak one** (within one grid step).
3. **Bounds:** the probe buffer is bounds-checked: a test with a deliberately small buffer sets the overflow flag and returns the rows that fit, without a write past the end; the ASan + UBSan job and fuzz (10,000 runs) cover it, including with the flag on.
4. **Nothing else changes:** run the Config, Web, Daemon and Ft8 projects separately and the JS runner; the Ft8 project also at `DOTNET_PROCESSOR_COUNT=4`. Existing golden, lean and determinism tests pass unchanged. Quote each "Passed: N".

## 4. After your hand-back (QA, not you)

HK-039 review, `pre_merge_check`, then the harness part and **one replay** of lean (DR-3 + probe, 16 threads, `--lean-probe 1`) on S40 (170 cycles), H40 and H20 (240 each), about 20 minutes. **Free check:** S40's published decodes must equal QA's DR-3 replay (matched 5,737, ours 6,009); if they differ the probe changed behaviour. Then QA reports the new baseline, the CS-MAP tables on the new lean, and the classification of the crowded misses (K1 to K4) with the neighbours' suppression.

## 5. Out of scope

Any change to what the decoder publishes, any change to a default, the daemon, the Settings page, the candidate search, the fit or the gates (this task only observes), the harness (QA's), DR-4.

## 6. Report back

The commit SHA; the rebuilt `libft8.dll` SHA256 and the shim number; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; the probe row layouts and the outcome and gate codes (a table, for QA's reader); which two waterfalls the suppression compares and how the footprint is placed; the buffer size and its worst case; the cost with the flag off (state that no work is done) and on (rough, per cycle); anything that differs from the neighbouring test exports' pattern.
