**User-facing:** no (a new configuration key, default OFF; the shipped behaviour does not change)

## Why

The coherent fallback publishes a CRC-valid new payload only when its F1b feature is at or below T1 = 17.552446 dB (state `NewGated`); a CRC-valid new payload above T1 is state `GatedOut` and is dropped. T1 was tuned on 2026-10-07 on original audio only (Q-GATE, night `20261004_1634`). The fallback on the residual audio arrived on 2026-10-27, and on the 400 seen cycles of night `20260925_2010` 255 of the 258 rows the gate blocks come from the run on the residual audio.

COH-GATE-G measured admitting them (offline, no build; spec `1b7445e7`, Amendments 1 and 2 on `arch/coh-gate-g`; freeze record `36df15b1`, TEST report `659af1b7`):

| rule R-F4: admit a `GatedOut` row iff it is from the residual-audio run | TRAIN (400 cycles) | TEST (800 other cycles) |
|---|---|---|
| NET (pp of WSJT-X decodes) | +1.905 | **+2.103 [1.919, 2.299]** |
| ΔU′ tested_absent per cycle (bar 0.021) | +0.010 | +0.00375 [0.000, 0.00875] |
| ΔU′ hashed/unencodable per cycle (reported, not barred) | +0.0225 | +0.025 [0.015, 0.036] |
| admitted outputs, share corroborated | 255, 90.6 % | 522, 93.3 % |

Verdict G-BUILD (Architect ruling `db578cf7`). It authorises this build behind a setting, default OFF, with acceptance on one second night (`20261022_1949_endurance_run-gathered`). It does not authorise a default change.

## What Changes

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: bool `decoder.coherentFallbackResidualUngated`, absent or false = today's behaviour; follows the pattern of `decoder.coherentFallbackAudio` (config file and API overlay, HK-035; no Settings-page control).
- `src/OpenWSFZ.Ft8`: a volatile field on `Ft8Decoder`, set by the daemon before the first window; in `Both` mode, `GatedOut` rows of the run that read the residual audio enter the merge and `Select` as if `NewGated`, keeping their true state for diagnostics. Sites: `CoherentFallbackSelector.cs:31`, `Subfeas/CohFallbackAudioSelector.cs:101/105/114`, the run bookkeeping at `Ft8Decoder.cs:1060-1069`.
- The coherent-fallback log line gains `ungated=N` (only when the setting is ON); `fromOriginal / fromResidual / inBoth` count admitted rows as found by the residual run.
- **No native change.** The native side already fills the payload, SNR and positions of a `GatedOut` row before the gate decides (`ft8_shim.c:2618`, `:2637`); C3 and BP already run on every candidate. `git diff --stat <base> -- native/ src/OpenWSFZ.Ft8/Native/` must be empty and the `libft8.dll` SHA-256 must equal `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`.
- Tests, `VERSION` 0.66 to 0.67 (every place the gates check), `REQUIREMENTS.md` FR-101 and a changelog row.

## Out of scope

Any change to T1, to the `Original` or `Residual` modes, to the F1b computation or to native code; turning the setting ON by default (a later decision for the Captain after the second night); whether T1 still matters on the original-audio run; a Settings-page control.

## Era

None while the setting is OFF. Turning it ON on the station starts a new live era (stamped by the daemon start time); live figures are never pooled across it.

## Capabilities

### Modified Capabilities

- `ft8-coherent-fallback`: ADDED requirements for the setting, the residual-run admission and the counters.
