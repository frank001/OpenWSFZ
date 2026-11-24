## Decisions

- **Defaults at every site.** The `[JsonConstructor]` parameter default (JSON-absent path) and the property initialiser (non-JSON path) must agree, otherwise `new DecoderConfig()` and an absent key disagree. Both move together.
- **`Ft8Decoder` backing fields stay `false`.** The daemon calls `SetCoherentFallbackResidualUngated` and `SetLateSubtractionRound` with the configured values before the first cycle (`Program.cs`, startup) and on every configuration change, so no cycle runs on the object's own value. Starting the fields `true` would change every test that builds an `Ft8Decoder` directly (batch 5 and ungated R-F4 rows would appear in count and timing assertions) for no behavioural gain. Same choice as COH-MULTISET (#264). The tests read the configured default through the same setter the daemon uses.
- **Explicit `false` keeps working** and the POST stays an overlay (HK-035): a body without the key leaves the current value as it is, including an explicit `false`.
