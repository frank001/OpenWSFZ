**User-facing:** no

## Why

The REFERENCE-SET off-air study replays recorded cycles through the product decoder (`Ft8Decoder.DecodeTwoStageAsync`, subtraction ON). Its gate RS-V2P (spec `arch/reference-set`, 2l item 2) asks whether the Linux build of the anchor decoder, run on the study host `sol` (AMD FX-8350, 8 cores), reproduces the output the station's decoder produced live.

On 2026-10-11 the first anchor block (40 m twilight, 40 cycles, one process, `sol` idle, Linux `libft8.so` SHA-256 `8839a780f1a0dd3e7960955088af1d1f5ad1ea1b991a781ccb4e9e4f27b342f7` built from commit `421e3ce2`, the source of DLL `a14fe354`) **abandoned the residual pass in 40 of 40 cycles**, each cycle ending at 11.53 to 11.56 s. The same block on the station PC (16 cores, anchor DLL) abandoned **0 of 40** at about 5.2 s per cycle and reproduced 100 % of the live non-hashed rows. The earlier STRONG-MISS replay abandoned 0 in 433 cycles. The cause is `SubtractionCycleBudget` = 13 s (`src/OpenWSFZ.Ft8/Ft8Decoder.cs:108`, `private static readonly`): the residual pass is cancelled shortly before that point, so `sol`'s real time per cycle is not observable.

On the station's hardware the budget does not bind, so a replay with the budget lifted yields the station decoder's output; only the cancellation path differs. The Captain chose this route ("option 2", 2026-10-11, spec 2m, amendment 8). Lifting the budget is a `src/` change, hence this change and a Developer task (HK-011).

## What Changes

- An **optional replay-only override** of `SubtractionCycleBudget`, read once when the decoder is constructed. Mechanism (environment variable or config key) is the Developer's choice; QA proposes an environment variable, because a config key would enter the saved `config.json`, the Settings page and the migration machinery for a setting no user should have.
- **Unset: 13 s and byte-identical behaviour** to the current build, shown by a unit test.
- **Valid values:** a number of seconds >= 13, or the word `unlimited`. Anything else (below 13, zero, negative, non-numeric, empty string) is **refused**, not clamped.
- The **effective budget is logged per cycle**, on the existing residual-pass log line, and once at construction as a warning when an override is active. Each cycle's residual-pass duration and abandoned/completed flag stay on that same line (`elapsedMs`, `deadlineAbandoned`: both exist today), which is what the replay harness reads.
- **Nothing in `native/`**, no shim change, no change to any decode parameter, no change to what runs when the override is unset.

## Non-goals

No user-facing setting, no Settings-page field, no documentation outside the code comment and this change, no change to the 13 s default, no adaptive budget. Whether the product should adapt its budget to slow CPUs is a separate product question (see the old-CPU issue draft).

## Capabilities

### Modified Capabilities

- `iterative-subtraction`: the wall-clock budget requirement gains an optional replay-only override and a per-cycle log field.

## Impact

`src/OpenWSFZ.Ft8/Ft8Decoder.cs` (the constant and its two call sites at the one-stage and two-stage paths), `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs` (the log line), tests in `tests/OpenWSFZ.Ft8.Tests`.
