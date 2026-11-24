## 1. Tests first

- [x] 1.1 D1 for each key: an absent key reads `true` in the config record (bound from JSON, `{"decoder":{}}`, no decoder section, `new DecoderConfig()`), and the `Ft8Decoder` set from it reads `true`; an explicit `false` reads `false` in both. Run against the old default: they fail.
- [x] 1.2 The overlay tests (Web) seed an explicit `false` so every step can fail, and gain a step: a body without the key keeps an explicit `false`.

## 2. Implementation

- [x] 2.1 `DecoderConfig.cs`: two constructor defaults `true`, two property initialisers `= true`, doc comments.
- [x] 2.2 `Program.cs` and `Ft8Decoder.cs`: comments that stated the old default.
- [x] 2.3 Specs and `REQUIREMENTS.md` (FR-101, FR-102, changelog row); `VERSION` 0.69, README and REQUIREMENTS anchors.

## 3. Verification

- [x] 3.1 Full unfiltered `dotnet test OpenWSFZ.slnx`; `openspec validate --all --strict`; `python tools/check_version_bump.py origin/main`.
- [x] 3.2 QA: HK-039 review record before anything is deployed; four mutations (each new default back to `false` fails its D1(a); each `false` branch forced to ignore the explicit key fails its D1(b)).
- [ ] 3.3 QA at deploy: read the station configuration back under `frans` (no explicit `false` for either key; `coherentFallbackAudio` `Both`, `decodingDepth` `Deep`, fallback on); stamp the new era.
