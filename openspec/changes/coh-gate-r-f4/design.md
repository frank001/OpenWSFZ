## Decisions

**D1. C#-only, behind a setting, default OFF.** The effect is established on one night (+2.103 pp on 800 held-out cycles, TRAIN +1.905); a default change waits for a second night and the Captain. OFF must be byte-for-byte today's behaviour (acceptance row B-OFF).

**D2. Why no native change.** The native side already fills the payload, SNR, out_freq and out_dt of a `GatedOut` row before the gate decides (`ft8_shim.c:2618` copies the payload; `:2637` sets `NEW_GATED` or `GATED_OUT` last; the single-candidate path does the same at `:2784` and `:2800`). C3 and BP run on every candidate in the output-first order (`cf_process_one(..., FT8_COH_FLAG_SKIP_F1B, ...)`, `:2605`, `:2771`). Admitting a `GatedOut` row therefore costs no native work. If the Developer finds a native change unavoidable, STOP and return to the Architect.

**D3. Semantics: QA's offline emulation is the reference (`gg_lib.publish`, `qa/rr-study/gap-relocate-run/gg_lib.py`).** Admitted residual-run `GatedOut` rows join the residual key set (so an original-run `NewGated` row with the same payload is dropped), take part in `Select`'s one-row-per-payload and edge rules in candidate order (sorted by the row's index within its run, residual before original, as `CohFallbackAudioSelector.Merge` does), then unpack, per-cycle text de-duplication and `IsPlausibleMessage` run unchanged. Admission is decided where the merge reads `State == NewGated` (`CohFallbackAudioSelector.cs:101/105/114`) and where `Select` does (`CoherentFallbackSelector.cs:31`). How the row keeps its true state (a separate flag or a wrapper) is the Developer's choice; it must never be relabelled in a counter or log.

**D4. Where it applies.** Only the run that actually read the residual audio (`choice.IsResidual`; run bookkeeping at `Ft8Decoder.cs:1060-1069`). `Original` and `Residual` modes are unchanged. A lone original-audio run (`both(unavailable)`) admits nothing. If the residual run completed and the original run was not started for budget reasons (`leftMs <= 0`), the residual run's rows are still admitted (the rows came from a completed run; the budget guard of COH-FB-AUDIO is unchanged).

**D5. Hash-table feedback is expected.** The text unpack of an admitted payload can add callsigns to the process-global hash table, as any decode does, so a later cycle's hashed-call text (`<...>`) can differ from an emulation that unpacked after the cycle inside a save and restore. Acceptance row B-EQ therefore requires exact equality on text without `<...>` and only counts hashed text.

**D6. Counters.** `fromOriginal / fromResidual / inBoth` count admitted rows as found by the residual run (they are in the merge and are published); `ungated=N` is separate and printed only when the setting is ON; `Gated` keeps its meaning (at or below T1). Log semantics (replay, 1,200 cycles of `20260925_2010`): `ungated=N` counts published rows whose chosen row was admitted over T1 from the residual run, including ones that replace an original-run row with the same text; it is not the number of additions (sum 1,206 = 777 new texts + 77 moved-frequency replacements + 352 outputs unchanged from the setting-off run).

**D7. Config.** The key follows `decoder.coherentFallbackAudio`: `DecoderConfig`, a volatile field set by the daemon before the first window, read once per window, overlay semantics of HK-035 (a partial post leaves it as it was), no Settings-page control.

## Risks

- A semantics error in the merge (an admitted residual row suppressing or failing to suppress an original row). Mitigation: unit tests for the displacement and edge cases; B-EQ against the offline reference on 1,200 cycles.
- More published batch-4 outputs when ON (+18 % on batch 4 at 93 % corroborated on TEST), and PSK Reporter ingest has no per-batch filter, so ON means they are uploaded. Mitigation: default OFF; for the Captain at the default decision.
- The hashed-call cost (ΔU′ hashed/unencodable +0.025 per cycle) cannot be tested by the instrument; it is reported, guarded by H-SHARE (hashed share of admitted 18.4 % on TEST against h = 0.5), not barred.
- One night, one band. Mitigation: the second-night acceptance rows (`20261022_1949`, 40 m).
