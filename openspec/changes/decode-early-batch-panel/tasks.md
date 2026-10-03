## 1. Pre-implementation decisions (record in `design.md` before writing code)

- [x] 1.1 Confirm from the gate 4a harness (`eng/122-gate4a`, the `trunc` mode of `qa/rr-study/sub-feas/replay81/Program.cs`) which decode call its early arm used (single-pass `DecodeAsync` with the subtraction flag OFF is expected). Record FILE:LINE. If it was another path, stop and tell QA: A4 would compare two different paths.
- [x] 1.2 Record the **R4 mechanism** (design D4): snapshot and restore (QA's recommendation) or suppressed writes, with the reason and FILE:LINE. Note that the shim has no suppress switch today (`ft8_shim.c:839-841`), so both are `native/` changes.
- [x] 1.3 Record the **WebSocket shape** (design D5): a new `decode-early` message and an optional `resolves` list on the batch-1 `decode` message, or an alternative that keeps the existing `decode` frame byte-identical when no early rows exist and delivers confirmation and final rows in one frame.
- [x] 1.4 Pick the new `FT8_SHIM_VERSION`: the next free number above every number used or reserved on any live ref (`git grep` over `origin/*` and the handoffs). Stage B item B2 also expects the next number; whichever merges second takes the one after.

## 2. Native: save and restore of the process-global decode state (`native/`, shim bump)

- [x] 2.1 In `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, add `ft8_hash_state_save()` and `ft8_hash_state_restore()` that copy, as one unit, `g_session_hash_table`, `g_hash_table_reject_count`, `g_h12_announce_clock`, `g_h12_displaying/ambiguous/divergent/suppressed`, `g_h12_by_code_displaying/ambiguous/divergent[]`, `g_h12_unresolved_by_code[]` and `g_h12_code_out_of_range` to and from a CALLER-SUPPLIED buffer (about 165 KB, a heap array, never a stack), with a size export, so that A2b can compare two saved images byte for byte (a static buffer would hide the image from the test; Architect's Amendment 1 `e24d541b`). Re-read `ft8_shim.c` for any further `g_` variable the decode mutates before declaring the list complete.
- [x] 2.2 Declare both in `ft8_shim.h`; add them to the export lists (`native/ft8_lib_build/rebuild_shim.bat`, `build_linux.sh`, any `.def`) and to `BUILD.md`; add them to `Ft8LibInterop.cs` and `IFt8NativeInterop` with the matching test double.
- [x] 2.3 Bump `FT8_SHIM_VERSION` everywhere it lives (`ft8_shim.h`, `Ft8LibInterop.cs` `ExpectedShimVersion`, `win-x64/libft8.version.txt`, `BUILD.md`, `rebuild_shim.bat` header text, `openspec/specs/ft8lib-interop/spec.md`, any ABI-sentinel test constant). Rebuild `libft8.dll` and `libft8.so`; macOS is rebuilt by CI. Pin the new DLL SHA-256 (actual and pinned). Run `python tools/check_native_version.py <binary> <number>` on each binary built. *(Developer note: `openspec/specs/ft8lib-interop/spec.md` is NOT edited here: its sentinel paragraph still reads 20260051 (a spec-sync backlog older than this change) and the spec deltas of this change are folded in by the archive step, 8.3. macOS dylib: CI.)*

- [x] 2.4 **Completeness test (design D4, HK-026):** a test (script or C#) that scans `ft8_shim.c` for every mutable file-scope variable **and every thread-local static** (`_Thread_local` today; also `__declspec(thread)` or any TLS macro the shim adopts) the decode can write, and **fails** when one is neither in the saved image nor recorded in `design.md` D4 as "reset per call (FILE:LINE)", or when the image names one that no longer exists. The Developer's scan output replaces QA's first-pass table in D4. It is part of the build, so adding a global without adding it to the image fails CI.

## 3. Managed decoder: a pass-0-only early entry

- [x] 3.1 In `src/OpenWSFZ.Ft8/Ft8Decoder.cs` add an early entry (for example `DecodeEarlyAsync(pcm, cycleStart, currentBand, ct)`) that calls `DecodeCoreAsync` with a new parameter forcing pass 0 only. It must not read `_subtractionEnabled` (`:370`), must not run `SubtractionPass` (`:489-501`) and must not write any instance state.
- [x] 3.2 Bracket the native call in the same `Task.Run` lambda as `DecodeAll` (`:443-459`) with `save` before and `restore` in a `finally`, and call `SetApBits` exactly as the final decode does (`:445-452`; the AP bits are thread-local and `ft8_decode_all` does not reset them), so a native access violation still restores. The final-decode path is unchanged and does neither.
- [x] 3.3 Tests (`tests/OpenWSFZ.Ft8.Tests`): the early entry returns pass-0 results only with the subtraction flag ON; the hash table, the reject count and the announce clock after the early decode equal their values before it; the restore runs when the native call throws; a decode after an early decode gives the same results as a decode without it (a fixed WAV from the existing hashed-callsign tests, `HashedCallsignResolutionTests.cs`).

- [x] 3.4 **A2b, the deterministic state round trip (Developer test, QA verifies):** capture the saved image (every global of 2.1) before an early decode, run the early decode on a window that adds callsigns and moves the counters, restore, capture again, and assert the two images are **byte-identical**. The test must **fail** if the restore omits any one global (QA mutates it: the announce clock, the reject count, one `g_h12_*` array).

## 4. Window producer: the optional early emission

- [x] 4.1 `src/OpenWSFZ.Ft8/CycleFramer.cs`: add the optional provider (constructor, next to `dialFreqProvider`, `:82-92`) and the optional `earlyOutput` (`RunAsync`, `:100-102`); emit exactly `EarlyTriggerSamples` samples, zero-filled, once per window (design D1); read the provider at the lazy-resync point (`:288`); re-arm at the window reset (`:335-337`).
- [x] 4.2 Tests (`tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` style): the early window is exactly the trigger length with a zero tail even when a chunk overshoots; one per cycle; none when the provider is null or disabled; the original window is untouched; the existing framer tests and both oracle tests pass **unmodified**.

## 5. Daemon: the decode gate and the early-decode service

- [x] 5.1 `src/OpenWSFZ.Daemon/`: a `SemaphoreSlim(1,1)` decode gate injected, optionally, into `DecodePump` (acquired around the decode at `:100-117`, released when the decode call returns) and into the new early service.
- [x] 5.2 The early service reads only `earlyOutput`; `Wait(0)` on the gate (busy means skip, counted, never queued); applies the dial-frequency rule (`DecodePump.cs:79-89`) against the window snapshot; decodes through the early entry (3.1); applies the same `ApplyNoiseSuppression`; publishes to the panel only; keeps the early batch for the cycle for matching; writes the R7 line.
- [x] 5.3 `Program.cs`: create the early channel (bounded 1, `DropOldest`) beside `framerOutput` (`:369-374`), pass the provider to `CycleFramer` (`:1062-1068`) and the writer to `RunAsync` (`:1068`), wire the gate and the service next to the pump (`:825-846`).
- [x] 5.4 Tests (`tests/OpenWSFZ.Daemon.Tests`, style of `DecodePumpTests.cs`): skipped when the gate is held; the ordinary decode waits for a running early decode and reports `finalWaitMs`; skipped on a dial-frequency change; nothing reaches ALL.TXT, the external-reporting channel, the answerer or caller channels, the archive or `AdmitNewValues` from the early batch; **flag OFF: same calls, same order as the pre-change pump** (characterisation, as `TwoStageEngageCharacterisationTests.cs`).

## 6. Matching and the panel events

- [x] 6.1 A pure matcher class (design D5 rule: same text, |Δf| <= 10 Hz, one-to-one, smallest |Δf|, ties to the earlier early row). Unit tests, including two candidates, an empty batch 1 and a repeated text.
- [x] 6.2 `DecodeEventBus` / `WebSocketHub` / `AppJsonContext.cs:89`: the `decode-early` message and the optional `resolves` list on the batch-1 message. **The existing `decode` frame must be byte-identical when there are no early rows** (a serialisation test).
- [x] 6.3 *(Developer: `node --test` with a fake DOM plus text pins of `main.js`, `web/js/earlyRows.test.js`; the real-browser and accessibility-tree check is QA's Playwright A5.)* `web/js/main.js` (`handleDecodes` `:777`, dispatch `:1820`) and the panel markup/CSS: render early rows marked *early*, replace a confirmed early row in place, mark an unmatched one *unconfirmed*; the mark is a text label or `aria-label`, never colour alone, and reachable by keyboard and screen reader. Keep `web/js/decodePanelBatches.test.js` passing and extend it, plus a `node --test` for the new handlers.

## 7. Config

- [x] 7.1 `DecoderConfig.cs` (`:139`, `:161`) and the overlay's `decoder` list (`ConfigOverlay.cs`): `earlyDecodeEnabled` (false) and `earlyDecodeCutSeconds` (2.0, clamped 0.5 to 3.0). The server-owned markers are untouched. Settings page: a checkbox and a number field with the range, off by default.
- [x] 7.2 Tests: a partial POST leaves both fields as they were (HK-035); the clamp; the reflection-enumerated config-save tests T4 and T5 pass with the new fields; the defaults.

## 8. Documentation and version

- [x] 8.1 `REQUIREMENTS.md`: add **FR-083** (next free after FR-082), row in the revision table, and update the traceability rows; the test names carry the `FR-083:` prefix (gate G3).
- [x] 8.2 `VERSION`: bump (check `decoding_improvement`'s VERSION, 0.55, so the numbers do not collide); README and any user-facing document say the setting exists, defaults OFF, and what *early* and *unconfirmed* mean. `**User-facing:** yes` is in the proposal (gate G9b).
- [ ] 8.3 Archive this change's spec deltas into `openspec/specs/` per the normal flow, after the merge.

## 9. QA acceptance (QA-owned, after the build exists; not Developer tasks)

- [ ] 9.1 **A1** flag OFF identity: the existing suite green plus the characterisation tests of 5.4 and 6.2, run unfiltered (quote the command and the counts, HK-022).
- [ ] 9.2 **A1b** (QA addition, design D10) flag ON, nothing early reaches ALL.TXT, UDP, the QSO channels or the archive: a fixed set of recorded cycles run with the flag ON and OFF; those four outputs are identical.
- [ ] 9.3 **A2** final decode unaffected, N/N on gate 4a's corpus **P** (`selection_p.json`, its SHA asserted, from `eng/122-gate4a`) and on **R**, flag ON versus flag OFF in separate fresh processes, driving **the product's early path**; strict N/N reference (D1 removed the fallback). **A2 positive control (HK-026):** the same replay against a build with R4 disabled must reproduce the known loss at stamp `261001_112700` (the 1 731 Hz decode); if it does not, A2 cannot see this defect and the report says so. A timing run: the PC to itself.
- [ ] 9.3b **A2b** (Architect's Amendment 1 `e24d541b`): the deterministic state round trip of 3.4 passes, the completeness test of 2.4 passes, and QA's mutations (omit one global from the restore) make A2b fail. **Merge rule: A2b PASS plus A2 N/N on P and R.** If A2's positive control cannot reproduce the known loss at stamp `261001_112700`, A2 is reported as **"not evaluable for this defect"** and the merge rests on A2b (a rare-event replay cannot carry R4 on its own).
- [ ] 9.4 **A3** live timing, receive only, 40 m, at least 2 h (QA recommends 4 h), the Captain's go and the station slot: (a) the early batch published at median <= 13.7 s into the slot, (b) skips <= 5 % of cycles, (c) batch 1's median publish time no more than +0.10 s later than the same session's flag-OFF hours (alternate the flag each hour by a partial POST, read back every time). QA states per-hour sample sizes and the spread before the first run.
- [ ] 9.5 **A4** consistency with gate 4a: on A2's replay `C(2.0)` is within +/-0.01 of 0.984 (P). The report states that A4 can only see a gross path difference.
- [ ] 9.6 **A5** panel: Playwright (HK-007): early rows appear marked; a confirming final row replaces its early row (one row, not two); an unconfirmed early row keeps its mark; the mark is in the accessibility tree; plus `live_verify_9_axes.py`.
- [ ] 9.7 Every figure is labelled with its source; no decode-rate claim; the flag stays OFF by default until the Captain decides after A3. Report in the standard format with the blind spot first (replay is not the live path; A3 is).
