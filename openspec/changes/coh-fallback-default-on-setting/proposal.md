**User-facing:** yes

## Why

The coherent-extraction fallback (COH-FALLBACK, A' step 3 and step 4) is built and reviewed behind `decoder.coherentFallbackEnabled`,
which is `false` in code and has no Settings control, so today it can only be turned on through the config API or file. The step-4
replay (D-GO' NET +3.82 pp [3.44, 4.21], U'-OK) and the R14 live check passed (Architect ruling §21), and the Captain, who is the only
user of this station, wants it on (2026-10-22: "first the dev session for default on, including the config page setting").

The decoder feature itself is specified by the Architect's COH-FALLBACK step-3 build spec and its amendments (`arch/coherent-limb2`);
this change records only the setting, its default and its Settings control.

## What Changes

- `DecoderConfig.CoherentFallbackEnabled` defaults to **`true`** (constructor default and property initialiser). An absent key, and a
  missing `decoder` section, read `true`; an explicit `false` stays `false` (the rule `earlyDecodeEnabled` and `decodingDepth` follow).
- A **"Coherent fallback" checkbox** in the Advanced Decoder Settings section of the Settings page, next to the early-decode
  controls, with a help text. An absent key shows it checked. It is saved through the normal config POST (an overlay).
- Flag OFF stays exactly the decoder as it was before the fallback existed (R13); nothing in the decoder, the batches or `native/` changes.
- Docs: `docs/development-history.md` row; VERSION 0.59.

## Non-goals

No decoder change, no native change, no shim change, no change to the batch logic. No Settings control for `decoder.decodingDepth`
(issue #240 mentions one; not part of this change). No status read-back of the fallback flag.

## Capabilities

### Modified Capabilities

- `decoder-settings`: the schema gains `coherentFallbackEnabled` (default `true`) and the Advanced Decoder Settings section gains its checkbox.

## Impact

`src/OpenWSFZ.Abstractions/DecoderConfig.cs`, `web/settings.html`, `web/js/settings.js`, `tests/OpenWSFZ.Web.Tests/settings-payload-shape.json`,
tests in `tests/OpenWSFZ.Config.Tests`, `tests/OpenWSFZ.Ft8.Tests`, `tests/OpenWSFZ.Web.Tests`, `web/js/coherentFallbackDefault.test.js`.
