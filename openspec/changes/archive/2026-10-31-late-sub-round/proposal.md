**User-facing:** no (a new configuration key, default OFF; the shipped behaviour does not change)

## Why

After the coherent fallback's batch (batch 4 on Deep) the cycle's residual buffer still holds energy that the decodes of batches 3 and 4 explain: those signals were found after the last subtraction. One more subtract-and-decode round on that buffer finds decodes the cycle did not.

LATE-SUB measured it offline (no build; harness `qa/rr-study/sub-feas/replay81/LateSub.cs`, mode `l1p`, commit `b7c17464` on `qa/refset`). The mode: the round runs on the cycle's last residual buffer, subtracts the natives behind the decodes published in batches 3 and 4, decodes once with the primary decoder, and does not run the fallback on the new buffer.

| L1′ (verdict night `20261022_1949`, setting OFF, 800 cycles) | value |
|---|---|
| NET (pp of WSJT-X decodes) | **+0.742 [0.621, 0.859]** |
| ΔU′ tested_absent per cycle (bar 0.021) | 0.0063 [0.0013, 0.0125] |
| H-SHARE (bar 0.5) | 0 |
| added decodes, share corroborated | 167, 154 corroborated |
| round time on the PC | median 0.75 s, worst end of work 5.8 s of 13 s |

Ruling L1′-GO (Architect, `d9e28caa` + `58e8f4bc`, 2026-10-30T13:18Z); build spec `33c50bd6` with Amendment 1 (F1 to F5, QA (k) review `106980f8` adopted in full). The build is authorised behind a setting, default OFF, with acceptance on the refset night (PC) and a third night on sol (`20260930_1930`). It does not authorise a default change.

## What Changes

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: bool `decoder.lateSubtractionRound` (property `LateSubtractionRound`), absent or false = today's behaviour; follows `decoder.coherentFallbackResidualUngated` (config file and API overlay, HK-035; no Settings-page control).
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: a volatile field set by the daemon before the first window (`SetLateSubtractionRound`), read once per window. After the fallback's batch on a Deep cycle where the fallback ran and `CohFallbackAudioSelector.Select` returns a residual buffer, one `SubtractionPass.RunThirdPassAsync` runs on that buffer. Its fit list is the natives behind the decodes `MapNative` published in batches 3 and 4 (a new optional out-list on `MapNative`); `alsoKnown` is batch 1's natives and the raw batch 2's. New decodes go through `MapNative(…, PathResidual)` with the cycle's text de-duplication set and leave as **batch 5** through the existing `onFallbackBatch` delegate. No new callback, no change to `DecodeStaged`'s signature.
- One `Late subtraction round:` log line per Deep cycle while the setting is ON; counters beside `_thirdPass*`.
- `src/OpenWSFZ.Daemon/Program.cs`: the two setter calls. Doc comments that listed batches "2, 3 or 4" now say "2, 3, 4 or 5" (`DecodeBatch.cs`, `DecodePump.cs`, `LateBatch.cs`, `QsoAnswererService.cs`, `QsoCallerService.cs`, `Ft8Decoder.cs`). No consumer switches on a specific batch value: `DecodePump.cs` sends every number other than 1 to `PublishSecondAsync`, the QSO services test `BatchNumber > 1`, and the deferred-action records keep the number for logs only.
- **No native change.** `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` must be empty and the `libft8.dll` SHA-256 must equal `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`.
- Tests, `VERSION` 0.67 to 0.68 (every place the gates check), `REQUIREMENTS.md` FR-102 and a changelog row.

## Out of scope

The coherent fallback on the new buffer or on R4 (LATE-SUB's C and L2 were ruled COST); any change to batches 1 to 4, T1, R-F4 or multi-set; payload subtraction (#273: the refused 9.5 % stay refused); turning the setting ON by default (a later decision for the Captain after the third night); a Settings-page control; a new budget constant (the pass's own deadline and reserve are the time guard).

## Era

None while the setting is OFF. Turning it ON on the station starts a new live era (stamped by the daemon start time); live figures are never pooled across it.

## Capabilities

### New Capabilities

- `ft8-late-subtraction`: the setting, when the round runs, its inputs, the call and its budget, batch 5, and the log line.
