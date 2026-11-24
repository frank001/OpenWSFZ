**User-facing:** no (a new configuration key, `decoder.engine`, default `classic`; the shipped behaviour does not change)

## Why

The classic decoder runs up to nine native passes per cycle and uses CPU the Captain no longer accepts. The Captain approved a rebuild on 2026-11-24 (decoder rebuild plan, `docs/decoder-rebuild/plan.md`, section 9 answers 1 to 5): one engine, built in four steps, each behind a switch. This is step 2a, the skeleton: one native call per cycle that decodes what the classic PRIMARY pass decodes, and nothing more, selectable with `decoder.engine = lean`. Later steps add tier B and CQ-AP (2b), the subtract-and-retry loop (2c), and the cross-cycle stage and three-batch publishing (2d).

Authority: `docs/decoder-rebuild/spec-dr2-lean-decoder.md` sections 2 and 3 step 2a, and `plan.md`, on `arch/decoder-rebuild` `68f7f15e`; QA task `dev-tasks/2026-11-24-dr2a-lean-decoder-tier-a.md` (`qa/same-chain` `cc6da2fc`). The Captain's test rule of 2026-11-24 applies: unit tests and review only, no replay, no on-air period, no statistical gate.

## What Changes

- `native/ftz_decoder/ftz_decoder.h` and `ftz_decoder.c` (new, OpenWSFZ-original, provenance header in each): `ftz_decode_cycle(pcm, n, params, out_results, cap, out_stats)` and `ftz_shutdown()`. S1 spectrogram (the primary pass's monitor configuration), S2 steps 1, 2, 6 and 7: candidates by `ftx_find_candidates` with today's primary parameters (minimum score 10, at most 140), tier A on every candidate in parallel on a fixed worker pool, then, on the calling thread, the results sorted by frequency, then time, then payload, unpacked against the shared callsign table, de-duplicated by payload and by text, SNR by the primary pass's formula, written. No tier B, no CQ-AP, no OSD, no subtraction loop. The file is compiled INTO `ft8_shim.c` (an `#include` at its end) so it shares the shim's callsign table and helpers and no build recipe needs a new compile line.
- `native/ft8_lib_build/patched/ft8/decode.c`: `ftx_decode_candidate_tier_a`, a thread-safe tier A (magnitude LLRs, belief propagation, CRC-14; no OSD; no thread-local state; a degenerate LLR vector is rejected).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` / `.h`: the include; `FT8_SHIM_VERSION` 20260072 to 20260073 (new exports only; `FT8Result` stays 48 bytes; every classic export and outcome unchanged). `libft8.dll` rebuilt; `rebuild_shim.bat` exports the two new symbols. The Linux `.so` and macOS `.dylib` are rebuilt by CI as always.
- `src/OpenWSFZ.Ft8/Interop/`: the P/Invoke, `LeanCycle.cs` (wire structs and the managed outcome and statistics records), the interface members (default implementations, so existing test doubles are unaffected) and the adapter.
- `src/OpenWSFZ.Abstractions/DecoderEngine.cs` and `DecoderConfig.cs`: `decoder.engine` (a string, `classic` default; the enum reads `lean` only for the word "lean") and `decoder.threads` (1 to 8, default 2). Config file and API only; the POST is an overlay.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: `SetEngine`, `SetLeanThreads`; one branch in the cycle (read once per window) to `DecodeLeanAsync`, which normalises the input as the primary pass does, makes ONE native call, maps through the same text de-duplication, plausibility filter, region and worked-before steps, and returns the results as the cycle's batch 1 (the staged entry points publish them as batch 1). A native error code or an exception is logged and the cycle carries on. One counts-only `lean:` Information line per cycle, plus the ordinary `decode(s) found` line.
- `src/OpenWSFZ.Daemon/Program.cs`: the two setter calls, at both places (initial, per config change).
- `.github/workflows/ci.yml`: the job `native-asan` (AddressSanitizer and UndefinedBehaviorSanitizer on Linux; `native/ftz_decoder/tests/run_asan.sh`).
- Tests, `REQUIREMENTS.md` FR-108 and a changelog row.

## VERSION

Not bumped (`User-facing: no`): the key defaults to `classic`, an absent key reads `classic`, and with `classic` every native call, row, batch, counter, log line and provenance value is as before (pinned by a golden recorded on the base build `452af459`). DR-3, when the Captain flips the default, bumps one minor.

## Out of scope

Tier B, CQ-AP, OSD, any subtraction, the cross-cycle stage, the three-batch publishing, `decoder.effort`, new decode ideas, threshold re-tuning, any closed arm (window, oversampling, input scaling), a Settings-page control. The early decode has no lean form (the plan removes it): under `lean` it returns nothing.

## Era

None while the engine is `classic`. Turning `lean` on starts a new live era: never pool its decodes with figures from `classic`.
