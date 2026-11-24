**User-facing:** yes (two decode settings turn ON by default; the daemon's live decode behaviour changes for a configuration that does not mention them)

## Why

Two decoder settings measured positive, each ALONE, and sit behind flags that default OFF:

| setting (JSON key under `decoder`) | evidence (each measured alone) |
|---|---|
| `coherentFallbackResidualUngated` (COH-GATE-G **R-F4**, FR-101) | NET +1.470 pp [1.296, 1.638], second night |
| `lateSubtractionRound` (LATE-SUB **L1'**, FR-102) | NET +0.772 pp [0.655, 0.889], third night (ACCEPT-3N, Architect ruling `eb422516`) |

The Captain decided on 2026-11-09 ("option a. turn them both on"): both defaults ON now, with no live ON run first. He was told the alternative (one live ON run under `frans` first) and did not choose it. Spec: Architect `qa/rr-study/2026-11-09-1634-architect-to-qa-spec-rf4-l1p-default-on.md` (`arch/rf4-l1p-default-on`); Developer task `dev-tasks/2026-11-09-rf4-l1p-default-on.md`. **Together the two are unmeasured**; the first live session is reported, not gated.

## What Changes

- `DecoderConfig`: the two `[JsonConstructor]` parameters default `true`, and the two property declarations get `= true` (a `new DecoderConfig()` and a missing `decoder` section read `true`, like an absent key). An explicit `false` stays OFF. Same pattern as COH-MULTISET (#264) and Deep (#240).
- `Ft8Decoder`'s own backing fields still start `false`: the daemon sets both from the configuration before the first cycle and on every change (`Program.cs`), so the configured default decides behaviour; every test that builds an `Ft8Decoder` directly is unchanged. Comments say so.
- Comments that stated the old default are corrected (`DecoderConfig.cs`, `Program.cs`, `Ft8Decoder.cs`).
- Specs: `ft8-late-subtraction` requirement amended (this change's delta); the R-F4 requirement of `coh-gate-r-f4` (still an active change, no main spec yet) amended in place.
- Tests that asserted the old default are changed, only there. `VERSION` 0.68 to 0.69; `REQUIREMENTS.md` FR-101, FR-102, a changelog row.
- **No native change.** Both behaviours are on `main` already; only the defaults move.

## Out of scope

Any change to the behaviour of either lever, to T1, to the preconditions (R-F4 acts only in `coherentFallbackAudio = Both`; L1' needs Deep and the fallback on), to the Settings page, or to native code.

## Era

The daemon start on the merged build starts a new live era, **"RF4+L1' ON"**, stamped by QA. Never pool live figures across it. It falls inside the `frans` era, which has no OFF live data yet, so there is no same-account OFF baseline (the cost of the Captain's choice).
