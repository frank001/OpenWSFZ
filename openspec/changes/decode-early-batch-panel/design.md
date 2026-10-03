## Context

Source spec: `qa/rr-study/2026-10-03-1440-architect-to-qa-spec-122-step4-early-decode.md` (Architect, `arch/122-latency` `c41a0c30`;
D1 ruling `c1a75d10`). Every code reference below is to `origin/main` `e2fdd446` (read 2026-10-03; re-read the lines on the branch you
build from, they move). The build is `src/` **and `native/`** (decision D4): a separate Developer session (HK-011).

**What the code does today.** `CycleFramer` (`src/OpenWSFZ.Ft8/CycleFramer.cs`) fills a 180 000-sample window and emits it once, complete
(`output.TryWrite((window, cycleStart, windowDialFreq))`, `:325`). `DecodePump` (`src/OpenWSFZ.Daemon/DecodePump.cs`) is strictly
serial: it reads one window, decodes it (`DecodeSingleBatch` flag OFF, `DecodeTwoStage` flag ON, `:100-117`) and publishes. The panel
receives a `decode` WebSocket message (`DecodeEventBus.cs:41` -> `WebSocketHub.BroadcastDecodes`, `WebSocketHub.cs:456`), and
`handleDecodes` (`web/js/main.js:777`) PREPENDS one row per result and never clears the table (pinned by
`web/js/decodePanelBatches.test.js`).

## Decisions

### D1. The trigger (R1): a new, optional emission point in `CycleFramer`

- **Where:** inside the accumulate step, right after `Array.Copy(chunk, chunkPos, window, filled, store); filled += store;`
  (`CycleFramer.cs:310-314`). When `filled` first reaches `EarlyTriggerSamples = 180 000 - round(12 000 x earlyDecodeCutSeconds)`
  (156 000 at 2.0 s) and the early flag is armed for this window, build the early window and `TryWrite` it to an **optional** second output.
- **Exactly the trigger length, not "whatever has arrived":** a chunk is up to 2 048 samples (171 ms), so `filled` may overshoot the trigger.
  Copy **exactly `EarlyTriggerSamples`** samples into a new `float[180 000]` and leave the rest zero. That is what gate 4a decoded, and A4
  compares against it.
- **Read the flag once per window**, at the same lazy-resync point that snapshots `windowDialFreq` (`:288`), through a new optional
  constructor parameter next to `dialFreqProvider` (`:82-92`), for example `Func<(bool Enabled, double CutSeconds)>? earlyDecodeProvider`.
  **Re-arm** where the window is emitted and reset (`:335-337`).
- **Nothing changes when the provider and the output are `null`:** `RunAsync`'s second parameter becomes an optional
  `ChannelWriter<...>? earlyOutput` after `output` (`:100-102`). The existing framer tests (`CycleFramerTests.cs`, the two oracle tests,
  `CycleFramerGridAlignmentHarness.cs`) must pass **unmodified**.
- **Channel:** bounded 1, `DropOldest`, single writer and reader (the pattern of `framerOutput`, `Program.cs:369-374`). A dropped early
  window is a skipped early decode, counted.
- **The first window after start-up** carries leading silence (`:109-111`); an early decode of it is legal, and the silence guard may return
  nothing (`Ft8Decoder.cs:386-393`).

### D2. Never in the way (R2): one decode gate shared by the early and the ordinary decode

The pump is serial, so the early decode must run on **its own task** and be made mutually exclusive with the ordinary decode.

- A `SemaphoreSlim(1, 1)` "decode gate" in `OpenWSFZ.Daemon`, injected into both. The early service does `Wait(0)`: busy means **skip**
  (counted, logged), never queued. `DecodePump.RunAsync` takes `await gate.WaitAsync(...)` before the decode at `:100-117` and releases it
  when the decode call returns. If an early decode is still running when the window closes, the ordinary decode waits for it (at most one
  early decode, about 0.6 s); the wait is measured and logged as `finalWaitMs` (A3).
- **Flag-OFF identity (R8):** the gate is an **optional dependency** (`null` when the feature is unwired). With `null` the pump takes no
  gate and makes the same calls in the same order. With the gate present an uncontended `WaitAsync` completes synchronously, but A1 is what
  proves it, not the argument.
- The early service must **not** be a second consumer of `framerOutput` (that would steal windows); it reads only `earlyOutput`.

### D3. The early decode is PASS 0 ONLY, whatever the subtraction flag says (R9, a QA addition)

`Ft8Decoder.DecodeCoreAsync` (`Ft8Decoder.cs:361`) reads `_subtractionEnabled` at `:370`, and with the flag ON and `onFirstBatch == null` it runs
`SubtractionPass.RunAsync` **inside the same call** (`:489-501`). Subtraction has been ON by default since 2026-10-02, so an early decode made
through `DecodeAsync` would run the residual pass too (about 5 s, not the 0.53 s gate 4a measured) and would defeat the purpose.

- Add an entry on the concrete type, for example `DecodeEarlyAsync(pcm, cycleStart, currentBand, ct)`, that calls the core with a new
  parameter forcing **pass 0 only**. It must **not** read `_subtractionEnabled` and must **not** toggle any instance state (the final decode
  may be about to read it).
- The Developer confirms from the gate 4a harness (`eng/122-gate4a`, `trunc` mode of `qa/rr-study/sub-feas/replay81/Program.cs`) that its early arm
  was the single-pass `DecodeAsync` with the flag OFF, and records FILE:LINE. If it was something else, A4 is comparing two different paths and
  the Architect is told.
- The silence guard and the RMS normalisation (`:386-393`, `:421`) apply as they do to the final decode. A zero-filled copy has a lower RMS, so
  its normalisation gain differs a little from the final decode's; gate 4a had the same path, so this is the path A4 compares against.

### D4. R4, protecting the final decode: snapshot and restore, in `native/` (new shim number)

**Fact first.** The spec offers (i) "hash-table writes suppressed, if the shim already allows that" or (ii) a native snapshot and restore.
**The shim does not already allow (i):** `cb_save_hash` (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:839-841`) calls `hash_table_add` unconditionally.
So **both options change `native/` and need a new `FT8_SHIM_VERSION`**, a rebuilt `libft8.dll` and `libft8.so`, and CI's macOS dylib.

**The shared state is wider than the table.** One decode mutates all of: `g_session_hash_table` (`:795`; 4 096 entries of `{callsign[12], hash,
announce_stamp}`), `g_hash_table_reject_count` (`:711`), `g_h12_announce_clock` (`:722`), `g_h12_displaying/ambiguous/divergent/suppressed`
(`:726-733`), `g_h12_by_code_displaying/ambiguous/divergent[]` and `g_h12_unresolved_by_code[]` (`:743-746`) and `g_h12_code_out_of_range` (`:747`).

**Why the early decode can change the final one (a lead, not a priced hypothesis; D2 of the gate 4a diagnostic was not run).** `cb_lookup_hash`
(`:812-838`) returns "not found" when the 12-bit probe chain holds two or more candidates ("no name beats a wrong name",
`tls_h12_suppressed = (tls_h12_multiplicity >= 2)`), and the managed layer then renders `<...>`. An early-only decode inserts its callsigns
(`hash_table_add`, `:750-786`) and bumps the announce clock; a later final decode can then see a multiplicity of two where it would have seen one,
render a different text, and the managed text de-duplication or plausibility filter (`Ft8Decoder.cs:510`, `:528`, `:534`) drops or changes a row.
That fits "1 decode in 20 175, text differs" and is exactly the kind of thing a snapshot makes impossible.

**QA recommends (ii) snapshot and restore, for two reasons beyond the guarantee itself:**
1. With (i) the early decode loses **within-call** resolution: a Type 4 message's callsign saved earlier in the same call would no longer resolve a
   later hash reference in that call, so the early text would read `<...>` where the final reads the name. R5 then fails to confirm the row and
   the panel shows two rows. (ii) lets the early decode behave exactly like a final decode inside the call.
2. (i) leaves the `g_h12_*` diagnostic counters polluted by the early decode's lookups (the endurance reports read them); (ii) restores them.

**Shape.** Two new exports, for example `ft8_hash_state_save()` and `ft8_hash_state_restore()`, copying the whole list above into one static
buffer (about 165 KB; tens of microseconds). The pair is **non-reentrant** (assert it, never nested) and relies on the D2 gate (no other
decode runs between them). Managed side: `try { save; decode; } finally { restore; }`, so a native access violation (the SEH wrapper only
detaches the thread pointer) still restores. The managed bracket runs **inside the same `Task.Run` lambda** as the decode (`Ft8Decoder.cs:443-459`),
because the native TLS is per-thread.

The Developer records the final choice (and why, with FILE:LINE) in this file before coding. **Acceptance A2 tests the guarantee, not the
mechanism.** If (i) is chosen after all, the Developer states how the lost within-call resolution is handled.

### D5. Panel protocol (R3, R5)

- The existing `decode` message (`WsDecodeMessage(Type, Payload)`, `AppJsonContext.cs:89`) must stay **byte-identical** when no early rows are
  involved (A1). Recommended shape: a **new message type `decode-early`** for the early batch (each row carrying an `earlyId`), and the
  batch-1 `decode` message gains an **optional** sibling `resolves` (written only when non-null) listing, per early row, `confirmed` with the
  index of the final row that replaces it, or `unconfirmed`.
- **Atomic from the operator's view:** the confirmation and the final rows arrive in **one** frame, so there is no paint between "early row
  removed" and "final row added". `handleDecodes` replaces a confirmed early row **in place** (same position, mark removed), prepends the
  unmatched final rows as today, and marks unmatched early rows *unconfirmed*. An empty batch 1 still resolves the cycle (every early row
  of that cycle becomes *unconfirmed*).
- **Matching is server-side and pure** (a small class, unit-tested): same message text and |Δf| <= 10 Hz, one-to-one, deterministic. Rule:
  for each final row in order, take the unmatched early row with the same text and the smallest |Δf| (ties: the earlier early row); at most one
  early row per final row and the reverse.
- The marks are visual **and** accessible: a text label or `aria-label`, never colour alone (R5, A5).
- `AdmitNewValues` is **not** run on early rows (R3). The client-side decode filter (`web/js/decodeFilter.js`) applies to early rows as to any row.

### D6. The early rows pass through the same visibility filter as batch 1 (R11, a QA proposal)

`PublishFirstAsync` shows only `ApplyNoiseSuppression(results)` (`DecodePump.cs:144-146`). If early rows skipped that filter, a row the operator
has chosen to hide would flash up early. The early batch applies the **same** `DecodeNoiseSuppressionFilter`. The Architect confirms.

### D7. Dial-frequency guard (R10, a QA addition)

The pump discards a cycle whose dial frequency changed during capture (`DecodePump.cs:79-89`). The early service applies the **same rule** against the
window's snapshot (`windowDialFreq`), and skips (counted) when it differs. Otherwise the panel would show early rows labelled with a band the
final decode then discards.

### D8. Config and log (R6, R7)

- `decoder.earlyDecodeEnabled` (bool, default `false`) and `decoder.earlyDecodeCutSeconds` (double, default 2.0, accepted 0.5 to 3.0, clamped
  server-side like the other decoder clamps) in `src/OpenWSFZ.Abstractions/DecoderConfig.cs` (next to `SubtractionEnabled` `:139`,
  `SubtractionMaxThreads` `:161`) and in the overlay's hand-listed `decoder` section (`src/OpenWSFZ.Web/ConfigOverlay.cs`). The reflection-enumerated
  config-save tests (T4, T5) pick up new fields and must pass. HK-035: a partial POST must leave both fields as they were (a test).
- One file-log line per cycle, ms-stamped, aggregates only (HK-037): `Early decode: n=..., elapsedMs=..., skipped=..., finalWaitMs=...`
  (`finalWaitMs` is QA's addition: A3 needs it).

### D9. Flag OFF changes nothing (R8)

With `earlyDecodeEnabled = false` the provider returns disabled, the framer emits no early window, no early service runs, the gate is not injected,
and no new WebSocket frame exists. Characterisation tests in the style of `TwoStageEngageCharacterisationTests.cs` and `DecodePumpTests.cs` pin the calls and their order.

### D10. QA's HK-021 (k) review of the acceptance rows (validity and precision; QA may refuse a row, none is refused)

| Row | Validity | Precision | QA change |
|---|---|---|---|
| **A1** flag OFF identity | Sound: it is the merge guard, and it fires on any code path that leaks early output with the flag OFF. | Fires both ways (a deliberate leak fails it). | Kept. |
| **(gap) R3 with the flag ON** | **No row covers it.** R3 says ALL.TXT, UDP, the QSO channels and the archive see nothing of the early batch, but A1 is flag OFF, A2 looks only at the final decode's numbers, A5 is the panel. A build could publish early rows to ALL.TXT and pass every row. | n/a | **A1b (new):** with `earlyDecodeEnabled = true` on a fixed set of recorded cycles, the ALL.TXT lines, UDP datagrams, QSO-channel batches and archive manifest rows are **identical** to the flag-OFF run (only the panel frames differ). Guards R3 and the merge. |
| **A2** final decode unaffected | Valid only if the replay drives **the product's early path** (the same early entry, with the snapshot and restore), not a copy of it in the harness. | **A2 alone is weak against the known defect.** If the V2 loss is a per-cycle chance of 1 in 1 075 (the observed rate), a build that still has it passes N/N on P with probability about 0.37 (0.19 on P plus R). A PASS therefore says little. | Run on **P and R** (R passed V2 N/N in gate 4a, so it adds power). And an **A2 positive control (HK-026):** run the same replay against the **unprotected** build (R4 disabled) and show it **reproduces the known loss** at stamp `261001_112700` (the 1 731 Hz decode, list position 956 on P). If the unprotected product build does not reproduce it, A2 cannot see this defect and must say so. Strict N/N reference (D1 removed the fallback). |
| **A3** live timing | (a) and (b) read straight from the R7 line and the `Cycle` line: valid. (c) must not use "cycles in which the early decode was skipped" as the control: skips happen when the decoder is busy, so those cycles are systematically the heavy ones (confounded). | (c) is a difference of medians with a 0.10 s bar; the spread is unknown until measured. | **(c) uses flag-OFF hours as the control** (alternate `earlyDecodeEnabled` each hour through a partial config POST, read back every time, FR-074 overlay). QA states per-hour sample sizes and the spread before the first A3, and reads (c) with its interval. >= 2 h gives one hour per arm; QA recommends >= 4 h. Receive only, 40 m, the Captain's go and the station slot. |
| **A4** consistency with gate 4a | Valid as a label on the figures. | `C` over about 20 000 decodes has a standard error near 0.001, so a +/-0.01 window is about ten standard errors wide: **A4 can only see a gross path difference** (a different cut, a missing normalisation), not a subtle one. | Kept; the report says what A4 can and cannot see. |
| **A5** panel | Valid. | Fires both ways (a deliberate duplicate row fails it). | Add: the mark is present in the **accessibility tree** (keyboard focus and screen-reader text), not only in the DOM text. Plus `live_verify_9_axes.py` (the decode-panel filtering policy). |

**Stops stay scoped (sibling (ab)):** A1, A1b, A2 and A5 block the merge; A3 blocks the default-ON decision only (the flag ships OFF); A4 labels
the figures and goes back to the Architect.

## Risks

- **Native change:** `libft8` gets new exports and a new shim number. B2 of the Stage B work (`dev-tasks/2026-10-03-sub-feas-stage-b-b2-pruned-freq-search.md`)
  also bumps the shim; both expect the next free number. Whichever merges second takes the next one after it: `git grep` over `origin/*` and the
  handoffs before choosing, and keep the two native diffs separate.
- **Heap and stack:** `g_session_hash_table` is 80 KB and the snapshot buffer is static. Do not put either on a stack (the project's AV history).
- **Concurrency is the historical crash class** (see `iterative-subtraction`). The gate (D2) and the non-reentrant pair (D4) are the controls; a
  stress test (early decode and ordinary decode contending for many cycles, forced cancellation) runs before any timing is read.
- **CPU:** one more ordinary decode per cycle while a residual pass may be running. R2's skip rule and A3(b) and (c) measure it.
- **Version collision:** `decoding_improvement` already carries VERSION 0.55. Check it before choosing this change's number.
