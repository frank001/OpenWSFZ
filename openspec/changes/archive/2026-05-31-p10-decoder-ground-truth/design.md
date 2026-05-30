## Context

The FT8 decoder (`OpenWSFZ.Ft8`) has not produced a single real decode from live air across 18 defects and 36 dev/QA rounds, while WSJT-X decodes the same signal cleanly. `RECOVERY_PLAN.md` establishes that the blocker is a **validation gap**, not (primarily) a DSP bug:

- The only end-to-end test, `Ft8DecoderFixtureTests`, builds its input with `TestFt8Encoder`, which encodes a frame using the *same* Gray map, CRC convention, LDPC generator, and clean-sine synthesis the decoder decodes with. A self-consistent encode/decode pair always round-trips, so the test proves only internal consistency — never correctness against the FT8 protocol or a real transmitter.
- The sole reality check is the Captain's live hardware smoke test: non-reproducible (new air each run), slow (one data point per round), and reported as fragmentary log lines.

With no deterministic test that fails for the real failure mode, every root cause has been a guess. This change builds the missing deterministic, real-signal oracle so decoder correctness becomes measurable. A radio is connected and tuned to 7.074 MHz, making capture immediately feasible.

`Ft8Decoder.DecodeAsync(float[] pcm, CancellationToken)` is the integration entry point. There is no WAV reader in the codebase today.

## Goals / Non-Goals

**Goals:**

- Produce a matched corpus of real-signal WAVs + WSJT-X `ALL.TXT` answer keys, captured from the connected radio.
- Provide a WAV→PCM reader so real recordings can drive `DecodeAsync` offline.
- Provide a replay harness that measures, per file, real-signal **recovery rate** vs. WSJT-X (matched / missed / false positives).
- Commit 2–3 representative WAVs as embedded CI fixtures with a red/green integration test asserting known real callsigns decode.
- Add a CI gate that blocks decoder regressions against the real-signal fixtures.
- Establish a QA process rule requiring reproducible failing tests for decoder root-cause claims.

**Non-Goals:**

- **No DSP algorithm changes.** This change installs measurement and gating only; it deliberately does not attempt to fix the decoder.
- **No decoder-strategy commitment.** Whether to port `ft8_lib` or patch the existing DSP is decided downstream from the recovery-rate measurement, in a separate change.
- No changes to audio capture, the daemon, or the ALL.TXT logging feature (which is complete in p9).
- No real-time side-by-side comparison of two live `ALL.TXT` files (explicitly rejected — see Decisions).

## Decisions

### D1 — Capture WSJT-X *Save All* WAVs as the answer key (not real-time ALL.TXT diffing)

WSJT-X's **File → Save → Save All** writes each 15 s cycle to `<DataDir>/save/YYMMDD_HHMMSS.wav` as 12 kHz mono, and logs its decodes to `ALL.TXT` keyed by the same timestamp. This yields `(WAV, expected-callsigns)` pairs for free.

**Why not real-time side-by-side?** Two separate captures off one radio differ in timing/buffering/AGC, so a mismatch cannot distinguish "our DSP is wrong" from "we fed it different audio" — the exact ambiguity that sustained 36 rounds. Feeding the *same samples* WSJT-X decoded removes that ambiguity and is reproducible.

**Why radio capture over downloaded fixtures?** It exercises our own signal chain and carries no licensing concern (decoded callsigns are facts). The MIT `kgoba/ft8_lib` `test/wav/` recordings are a fallback if a clean capture is hard to obtain.

### D2 — WAV reader lives in the test project, kept minimal

The reader supports exactly what WSJT-X emits (12 kHz mono int16 PCM → normalised `float[]`). It is placed in `tests/OpenWSFZ.Ft8.Tests/` (not production) because no production code path reads WAV files; this avoids enlarging the AOT/shipping surface. If a future feature needs WAV ingestion in production, it can be promoted then.

### D3 — Real-signal fixture test supersedes the circular encoder test as the integration oracle

The new fixture test becomes the authoritative integration coverage. `TestFt8Encoder` / `Ft8DecoderFixtureTests` are retained but reclassified as *internal-consistency* checks — they no longer count as evidence of correctness. This prevents "all tests green" from masking a non-functional decoder.

### D4 — Recovery rate is the decision-gate metric

The harness reports, across the corpus, how many of WSJT-X's decodes our decoder recovers. Per `RECOVERY_PLAN.md`: 0 recovered → port `ft8_lib`; some-but-fewer → patch against the oracle; parity → bug was elsewhere. This change *defines and measures* the metric; acting on it is a separate change.

### D5 — Fixtures committed as embedded resources

WAV fixtures + answer keys are embedded in the test assembly so CI needs no external assets and the test is hermetic. Keep the set small (2–3 files) to bound repository size; choose varied SNR and band-congestion to maximise diagnostic value.

### D6 — Process gate: claims require reproducible tests

A new quality requirement mandates that decoder defect "root causes" be demonstrated by a failing test on a committed WAV before a fix is accepted. Live smoke tests are downgraded to acceptance/confirmation. This makes re-entering the speculative D-loop structurally impossible.

## Risks / Trade-offs

- **Clean live capture may be hard (QRM, dead band)** → Fall back to MIT `kgoba/ft8_lib` `test/wav/` recordings; record attribution in the licence inventory.
- **WSJT-X WAV length differs from the decoder's 180 000-sample assumption** → Confirm sample count on first capture; align the decoder's window length (mechanical, no algorithm change).
- **Committed WAV fixtures grow the repo** → Limit to 2–3 files; FT8 cycles at 12 kHz mono are small (~hundreds of KB each).
- **CI runtime variance on the real-signal test** → Assert on decoded message content (deterministic), not timing, for the correctness gate; keep any timing assertion in the separate performance test.
- **Team reverts to log-scraping habits** → The D6 process rule plus the CI gate make a reproducible failing test the only accepted evidence for decoder claims.
- **Answer key includes signals below our (or WSJT-X's) noise floor** → The correctness fixture asserts a defined subset of strong, unambiguous decodes; the full corpus drives the recovery-rate measurement, not the pass/fail gate.
