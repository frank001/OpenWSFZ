## Why

The FT8 decoder has been stuck in a non-converging defect loop: across 18 defects (D1–D18) and 36 developer/QA rounds, it has produced **zero real decodes** from live air while WSJT-X decodes 40+ stations from the identical signal. The deadlock's root cause is not the DSP — it is a **validation gap**. The only end-to-end test (`Ft8DecoderFixtureTests`) feeds the decoder a signal built by `TestFt8Encoder` using the *same* constants the decoder decodes with, so it is circular: it proves the decoder agrees with itself, never with reality. The only check against reality is a slow, non-reproducible live hardware smoke test. With no deterministic test that can fail for the real failure mode, every "root cause" has been a guess. This change installs the missing piece — a real-signal ground-truth oracle — so decoder correctness can be measured and proven reproducibly. See `RECOVERY_PLAN.md`.

## What Changes

- **Real-signal test corpus** — capture WAV recordings from the connected radio via WSJT-X *Save All* on 7.074 MHz, paired with WSJT-X's `ALL.TXT` decodes as the answer key. Commit 2–3 representative recordings as embedded fixtures with their expected callsign lists.
- **WAV→PCM reader shim** — a minimal reader converting 12 kHz mono int16 WAV into the `float[]` PCM that `Ft8Decoder.DecodeAsync` consumes (none exists today).
- **Offline replay harness** — a tool/test that decodes each fixture WAV and reports, per file: real signals matched against WSJT-X, WSJT-X signals missed, and our false positives — yielding a concrete **recovery-rate** measurement.
- **Decoder-correctness CI gate** — a real-signal integration test that runs in CI on every push and fails when decoder changes regress real-signal recovery. This supersedes the circular `TestFt8Encoder` test as the integration oracle (the encoder test is retained only as a fast internal-consistency check).
- **QA process rule** — "root cause" claims for decoder defects must be demonstrated by a *failing reproducible test on a committed WAV*, not inferred from live-session log lines. Live smoke tests become acceptance/confirmation, not the primary debugging instrument.
- **Decision gate (out of scope to implement here, defined here)** — the recovery-rate measurement determines the downstream decoder strategy (port `ft8_lib` vs. patch); that work is a separate change.
- **No DSP algorithm changes in this change** — this change only installs the measurement and gating infrastructure. It deliberately does *not* attempt to fix the decoder.

## Capabilities

### New Capabilities

- `decoder-ground-truth`: A reproducible real-signal test oracle for the FT8 decoder — captured WAV fixtures with WSJT-X answer keys, a WAV→PCM reader, an offline replay/measurement harness, and a CI gate asserting known real signals decode.

### Modified Capabilities

- `ci-quality-gates`: Adds a decoder-correctness gate — the real-signal fixture test runs in CI and blocks merges that regress real-signal recovery.

## Impact

- **`tests/OpenWSFZ.Ft8.Tests/`** — new WAV→PCM reader, replay harness, real-signal fixture integration test; embedded WAV fixtures + answer-key assets; `TestFt8Encoder`-based fixture test demoted from "integration proof" to internal-consistency check.
- **`.github/workflows/ci.yml`** — decoder-correctness gate added to the existing gate set.
- **`openspec/changes/p9-all-txt-decode-logging/`** — decoder-correctness (D18) is split out of p9; the ALL.TXT logging feature (FR-026/027/028) is unaffected and merges on its own merits.
- **`REQUIREMENTS.md`** — new functional requirement for reproducible real-signal decode verification; new process/quality requirement for the decoder-correctness gate.
- **Dependency/licence inventory** — if `kgoba/ft8_lib` MIT recordings are used as fallback fixtures, record attribution so the `LicenseInventoryCheck` gate stays green. (Captured radio recordings carry no licensing concern.)
- **No changes** to `OpenWSFZ.Ft8` DSP algorithms, `OpenWSFZ.Audio`, `OpenWSFZ.Daemon`, or the decode pipeline behaviour in this change.
