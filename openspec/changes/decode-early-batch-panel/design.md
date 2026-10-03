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

## Developer decisions (recorded 2026-10-03, Developer session, tasks 1.1 to 1.4; FILE:LINE are on the branch built from `origin/main` `e2fdd446`)

**1.1 The call gate 4a's early arm used.** `eng/122-gate4a`, `qa/rr-study/sub-feas/replay81/Trunc.cs`: the early arm calls
`TimedDecode` (`:192`), which calls **`Ft8Decoder.DecodeTwoStageAsync`** (`:262`) with `publishFirstBatch` collecting the batch, and V0
(`:146`) throws unless `decoder.SubtractionEnabled` is **false**. With the flag OFF `DecodeTwoStageAsync` is the single-batch pass-0 path
(`twoStage = onFirstBatch is not null && subtractionOn` is false, `Ft8Decoder.cs` `DecodeCoreAsync`, and the residual `if` is skipped), with
`currentBand = null`, no AP constraints and no state bracket. That is the same decode, call for call, as `DecodeEarlyAsync` makes
(pass 0 only, `SetApBits([], [])` when no constraints, RMS normalisation, silence guard) **except** for the save/restore bracket, which is
the point of this change. The cut is `n = 180 000 - round(12 000 x x)` zero-filled after `n` (`Trunc.cs:187-189`), the framer's
`EarlyTriggerSamples`. So A4 compares the same path. **No disagreement to report to the Architect.**

**1.2 The R4 mechanism: snapshot and restore (QA's recommendation), in `native/`.** Reasons beyond the guarantee: suppressing hash writes
(`cb_save_hash`, `ft8_shim.c` near `s_hash_if`) would lose within-call resolution of a Type 4 callsign saved earlier in the same call, so the early
text could read `<...>` where the final reads the name and R5 would show two rows; it would also leave the `g_h12_*` counters polluted. The
shim has no suppress switch today, so both options change `native/`. The image is one struct, `ft8_hash_state_image_t`, in `ft8_shim.c`
(147 492 bytes: the 4 096-entry table + count, the initialised flag, the reject count, the announce clock, the four `g_h12_*` scalars,
`g_h12_code_out_of_range` and the four 4 096-int per-code arrays), saved with `memset` first so padding is deterministic. Exports
`ft8_hash_state_size()`, `ft8_hash_state_save(void*, int cap)` (returns bytes written or -1), `ft8_hash_state_restore(const void*, int len)`
(0 or -1; `len` must equal the size). Managed: `Ft8Decoder.DecodeCoreAsync(early: true)` saves **before** the `try`, restores in the `finally`,
inside the same `Task.Run` lambda as `DecodeAll`; the buffer is a reusable heap `byte[]` (`RentStateImage`), never a stack.

**Scan result (the Developer's scan replaces QA's first-pass table).** `HashStateCompletenessTests` scans `ft8_shim.c`, `patched/ft8/decode.c`,
`patched/common/monitor.c` and every vendored `*.c` (not `refine/tests`) for mutable file-scope statics and thread-local statics. It found
nothing beyond the following; the manifest is the `HSM-IMAGE` / `HSM-EXEMPT` block in `ft8_shim.c` (one line per variable, with the reason).
**In the image (13):** `g_session_hash_table`, `g_hash_table_initialised` (QA's table omitted it: if the first call ever is an early decode the
table is initialised inside it, so the flag must come back too), `g_hash_table_reject_count`, `g_h12_announce_clock`, `g_h12_displaying`,
`g_h12_ambiguous`, `g_h12_divergent`, `g_h12_suppressed`, `g_h12_by_code_displaying`, `g_h12_by_code_ambiguous`, `g_h12_by_code_divergent`,
`g_h12_unresolved_by_code`, `g_h12_code_out_of_range`. **Exempt, thread-local (22):** the table in D4 below, all confirmed by reading
`ft8_decode_all` (the resets are at "4. Cross-pass dedup state", "3. Noise floor", "2. Callsign table", "6. Cleanup" and per message before
`ftx_message_decode`); `tls_ap_*` are reset by the caller (`SetApBits` before every `DecodeAll`, the early lambda included);
`tls_diagnostics_enabled` is written only by `ft8_set_diagnostics_enabled`, which only `SubtractionPass` calls (`SubtractionPass.cs:325`, `:332`,
restored in a `finally`), and the pass-0-only early entry never reaches it. **Exempt, other:** `s_hash_if` (two initialised function pointers) and the nine
`g_pool_*` variables of `subfeas_fit.c` (the residual pass's workspace pool, which the early decode never calls). Function-local statics in
`subfeas_fit.c` exist only under `#ifdef SUBFEAS_SELFTEST` (a standalone test `main`) and are skipped by the scanner; any other function-local
static fails the test.
**Blind spot, said plainly (HK-026):** the scanner reads one declaration per line. A declaration whose name sits on a later line than its
`static` would not be seen. A restore that is wrong in a way the image cannot express (a state that is not a plain global) is invisible to it; A2b
and A2 are the other half.
**Not covered, by construction:** `ft8_encode_message` (the TX encoder) runs `hash_table_add` on a *local* table but still bumps the global announce clock
(`g_h12_announce_clock`). The decode gate covers decodes only, so a TX encode that lands between an early decode's save and restore has its clock
increment rolled back. The clock is a monotonic recency stamp compared only among entries already in the table; rolling it back by a few counts cannot
change which entry wins. Noted, not mitigated.

**1.3 The WebSocket shape (D5 as recommended).** A new message type **`decode-early`**:
`{"type":"decode-early","payload":[{"earlyId":7,"decode":{...the DecodeResult fields...}}]}`. The existing `decode` message gains an optional
sibling **`resolves`**, written only when non-null (`[property: JsonIgnore(WhenWritingNull)]`):
`{"type":"decode","payload":[...],"resolves":[{"earlyId":7,"outcome":"confirmed","finalIndex":0},{"earlyId":8,"outcome":"unconfirmed"}]}`
(`finalIndex` is the index in the same frame's `payload`; omitted for `unconfirmed`). The `decode` frame with no early rows is byte-identical to
before (`EarlyDecodeProtocolTests` 6.2a pins the literal). Confirmation and final rows are one frame. `earlyId` is a daemon-lifetime counter
(`EarlyDecodeCoordinator.NextEarlyId`). Implementation: `src/OpenWSFZ.Web/EarlyDecodeMessages.cs`, `AppJsonContext.cs`, `WebSocketHub.cs`,
`DecodeEventBus.cs`; matcher `src/OpenWSFZ.Daemon/EarlyDecodeMatcher.cs`.

**1.4 The shim number: `20260058`.** `git grep` over every local and remote ref on 2026-10-03: `main` `20260056`, `decoding_improvement` `20260057`
(DI sync 4), no ref at `20260058` or above. Stage B item B2 (handoff expects the next free) merges second and takes the one after.

**Other choices recorded here.**
1. **The gate is always wired, not injected only when the flag is on** (D9 said "the gate is not injected"). The flag is changeable at run time
   (A3 alternates it hourly by a partial POST), so the gate must exist when it is turned on. With the flag OFF no early window is emitted, the early
   service never wakes, and the pump's `WaitAsync` on a free gate completes synchronously; `DecodePumpDependencies.Early` is `null` for every
   existing caller (the pre-change pump, call for call), and `EarlyDecodeDaemonTests` 5.4a pins that a wired-but-idle coordinator makes the same calls
   in the same order. A1 on a live build is QA's.
2. **The gate is held across the whole ordinary decode**, including the residual pass of a flag-ON cycle and the batch-1 publish, because that is
   the decode call that touches the process-global state. The next cycle's early window opens 13 s later, long after the residual pass has finished,
   so this costs nothing in the normal case; if it ever did, the early decode skips (counted), never queues.
3. **Early rows are display-only.** No click, double-click or engage handler is attached (the phase-4a rule: the automation never acts on an early
   row). The confirming final row that replaces an early row in place is a normal interactive row. Early rows do not feed the transcript, the QSO row
   highlighting or the session's distinct-value sets; the active decode filter applies to them.
4. **A cycle that never produces batch 1** (a discarded cycle, a decode error) resolves its early rows as `unconfirmed` through an empty `decode`
   frame carrying `resolves` (`EarlyDecodeCoordinator.Abandon`); so does an early batch left behind when the next cycle's early batch arrives.
5. **The R7 line** is `Early decode: cycle=HH:mm:ss, n=.., elapsedMs=.., skipped=0|1, skipReason=none|decoderBusy|dialFrequencyChanged|error,
   finalWaitMs=..`, one per cycle whose early window arrived, written when the pump has taken the gate for the final decode (that is when
   `finalWaitMs` is known). A cycle with **no** line either had the feature OFF or lost its early window to the full early channel (bounded 1,
   DropOldest); A3 counts such cycles from the `Cycle` lines.
6. **The early entry writes none of the per-cycle Information lines** an ordinary decode writes (`Cycle .. N decode(s) found`, the reject-count line,
   the h12 line, the noise floor). They would duplicate the `Cycle` line that the endurance and R&R parsers read, and the cumulative counters they
   print belong to the final decode.
7. **Version.** `VERSION` 0.54 -> **0.56**. `decoding_improvement` carries 0.55 for different content (DI sync 4); reusing 0.55 would give two different
   builds the same number once DI syncs.
8. **`tests/OpenWSFZ.Web.Tests/settings-payload-shape.json`** gained `earlyDecodeEnabled` and `earlyDecodeCutSeconds` under `decoder`. This is the
   fixture the file itself says to change together with the payload in `settings.js` ("Change the payload in settings.js and this file together");
   it is not a pinned instrument constant and no ruling pins it. Looked for a ruling, found none.

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
- **The early lambda sets the AP bits exactly as the final decode does** (`Ft8Decoder.cs:445-452`: `SetApBits` with the current constraints, or cleared). They are thread-local and `ft8_decode_all` does not reset them (D4's table); the early decode may run on a different pool thread than the final.
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

**Shape.** Three new exports, for example `ft8_hash_state_size()`, `ft8_hash_state_save(buf, cap)` and `ft8_hash_state_restore(buf, len)`,
copying the whole list above to and from a **caller-supplied buffer** (about 165 KB; a heap `byte[]` on the managed side, never a stack; tens
of microseconds). A caller-supplied buffer, not a static one, is what lets acceptance **A2b** compare two saved images byte for byte (a static
buffer would hide the image from the test; Architect's Amendment 1, `e24d541b`). The pair relies on the D2 gate (no other decode runs between
them). Managed side: `try { save; decode; } finally { restore; }`, so a native access violation (the SEH wrapper only
detaches the thread pointer) still restores. The managed bracket runs **inside the same `Task.Run` lambda** as the decode (`Ft8Decoder.cs:443-459`),
because the native TLS is per-thread.

**The completeness of the list is checked mechanically, not trusted (HK-026: an instrument cannot bound its own blind spot).** A2b compares saved
images, so it can only see the globals the image contains. A test therefore scans `ft8_shim.c` for every mutable file-scope `g_` / `static` variable
the decode can write (a script or a C# test over the source text) and **fails when one is not in the image** (and when the image names one that no
longer exists). Adding a global to the shim without adding it to the image then fails the build, instead of silently re-opening R4.

**Thread-local state counts too (Architect, follow-up to `e24d541b`).** The early and the final decode may run on the same pump thread, so a
`_Thread_local` the decode writes and that survives into the next call can carry the early decode into the final one. The image and the
completeness scan cover **thread-local statics as well as file-scope globals** (`_Thread_local` today; also `__declspec(thread)` or any TLS macro
the shim adopts), and record **per variable** either "in the image" or "reset per call (FILE:LINE)". QA's first-pass reading of
`ft8_shim.c` (the Developer's scan output replaces it and any disagreement is raised):

| Variable (`ft8_shim.c`) | Disposition |
|---|---|
| `tls_pass_counts`, `tls_candidate_counts`, `tls_llr_mean_abs_sum`, `tls_llr_prenorm_var_sum`, `tls_llr_fail_count` (`:577-581`), `tls_num_passes` (`:582`), `tls_num_decoded_snr_terms` (`:591`) | **Reset per call** at the top of `ft8_decode_all` (`:1515-1521`). Diagnostic outputs read right after the call, on the same thread. |
| `tls_last_noise_floor_db` (`:583`) | **Assigned per call** (`:1508`) before anything reads it. |
| `tls_signal_db`, `tls_local_noise_db` (`:589-590`) | Overwritten per decoded message, bounded by `tls_num_decoded_snr_terms` (reset `:1520`). **Verify** the bound is what the getters use. |
| `tls_hash_table` (`:811`) | **Assigned per call** (`:1502`) and cleared at the end (`:1806`, `:1826`). |
| `tls_h12_lookup_performed`, `tls_h12_suppressed` (`:804`, `:809`) | **Reset per message** (`:1676-1677`). `tls_h12_resolved`, `tls_h12_multiplicity`, `tls_h12_divergent`, `tls_h12_code` (`:805-808`) are written whenever a 12-bit lookup is performed and read only if `tls_h12_lookup_performed`; **verify** that reading rule. |
| `tls_ap_mycall_bits`, `tls_ap_hiscall_bits`, `tls_ap_num_*_bits` (`:605-608`) | **NOT reset by `ft8_decode_all`.** Set by `ft8_set_ap_bits` (`:1423-1441`), which the managed caller invokes before **every** `DecodeAll` (`Ft8Decoder.cs:445-452`). So they are "reset per call **by the caller**", and the early lambda **must call it the same way** (or an early decode on a different pool thread decodes with whatever that thread last held). |
| `tls_diagnostics_enabled` (`:616`) | **Persists.** Written only by `ft8_set_diagnostics_enabled` (`:1418-1420`), which `SubtractionPass` brackets around the residual decode. The pass-0-only early entry never calls it. **Verify** no path leaves it at 0 (a faulted residual pass). |

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
| **A2b** state round trip (Architect's Amendment 1, `e24d541b`; QA agrees) | Valid by construction: a deterministic test, no corpus and no luck. It captures **every** process-global value in the image (design D4) before an early decode, runs the early decode, restores, captures again, and asserts the two images are **byte-identical**. A decode that adds callsigns and moves the counters is used, so the restore has something to undo. | Fires both ways: omit one global from the restore (for example the announce clock) and it fails. It sees only what the image contains, so it is paired with the **completeness test** of D4. | **Merge needs A2b PASS plus A2 N/N on P and R.** If A2's positive control cannot reproduce the known loss at stamp `261001_112700`, A2 is reported as **"not evaluable for this defect"** and the merge rests on A2b: a rare-event replay cannot carry R4 on its own. |
| **A3** live timing | (a) and (b) read straight from the R7 line and the `Cycle` line: valid. (c) must not use "cycles in which the early decode was skipped" as the control: skips happen when the decoder is busy, so those cycles are systematically the heavy ones (confounded). | (c) is a difference of medians with a 0.10 s bar; the spread is unknown until measured. | **(c) uses flag-OFF hours as the control** (alternate `earlyDecodeEnabled` each hour through a partial config POST, read back every time, FR-074 overlay). QA states per-hour sample sizes and the spread before the first A3, and reads (c) with its interval. >= 2 h gives one hour per arm; QA recommends >= 4 h. Receive only, 40 m, the Captain's go and the station slot. |
| **A4** consistency with gate 4a | Valid as a label on the figures. | `C` over about 20 000 decodes has a standard error near 0.001, so a +/-0.01 window is about ten standard errors wide: **A4 can only see a gross path difference** (a different cut, a missing normalisation), not a subtle one. | Kept; the report says what A4 can and cannot see. |
| **A5** panel | Valid. | Fires both ways (a deliberate duplicate row fails it). | Add: the mark is present in the **accessibility tree** (keyboard focus and screen-reader text), not only in the DOM text. Plus `live_verify_9_axes.py` (the decode-panel filtering policy). |

**Stops stay scoped (sibling (ab)):** A1, A1b, A2b, A2 (as scoped in its row) and A5 block the merge; A3 blocks the default-ON decision only (the flag ships OFF); A4 labels
the figures and goes back to the Architect.

## Risks

- **Native change:** `libft8` gets new exports and a new shim number. B2 of the Stage B work (`dev-tasks/2026-10-03-sub-feas-stage-b-b2-pruned-freq-search.md`)
  also bumps the shim; both expect the next free number. Whichever merges second takes the next one after it: `git grep` over `origin/*` and the
  handoffs before choosing, and keep the two native diffs separate.
- **Heap and stack:** `g_session_hash_table` is 80 KB and the snapshot buffer is static. Do not put either on a stack (the project's AV history).
- **Concurrency is the historical crash class** (see `iterative-subtraction`). The gate (D2) and the save/restore pair with A2b and its completeness test (D4) are the controls; a
  stress test (early decode and ordinary decode contending for many cycles, forced cancellation) runs before any timing is read.
- **CPU:** one more ordinary decode per cycle while a residual pass may be running. R2's skip rule and A3(b) and (c) measure it.
- **Version collision:** `decoding_improvement` already carries VERSION 0.55. Check it before choosing this change's number.
