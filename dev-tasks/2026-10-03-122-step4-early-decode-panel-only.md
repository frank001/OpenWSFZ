# Developer handoff: #122 step 4, phase 4a — an early decode at 13.0 s, shown on the decode panel only

**Date:** 2026-10-03. **From:** QA. **To:** Developer. **Priority:** high (the Captain authorised it). **Authorised:** the Captain, 2026-10-03 about 14:31Z (Architect's window): *"1. agreed"*.
**Spec (Architect):** `qa/rr-study/2026-10-03-1440-architect-to-qa-spec-122-step4-early-decode.md` on the Architect's local `arch/122-latency` (`c41a0c30`; D1 ruling `c1a75d10`); read it with `git show arch/122-latency:<path>`. It reaches `main` when QA pushes it with the Captain's go.
**OpenSpec:** change `decode-early-batch-panel` (`proposal.md`, `design.md` D1 to D10, `specs/early-decode/spec.md`, `specs/ft8lib-interop/spec.md`, `tasks.md`), on QA's local `qa/122-step4-docs`. **`design.md` carries the FILE:LINE the spec asked for; read it first.**

## 1. Context

Gate 4a showed an early decode of a zero-filled copy of the first 13.0 s of a window holds about **98 %** of what the full window gives, and costs about as much time as the full decode, so those decodes would reach the panel about **2 s earlier**. It also found early-only rows the final decode does not confirm, and one final decode in 20 175 lost on corpus P when early decodes ran first in the same process. So this change shows the early rows on the panel **marked**, confirms them when the final decode agrees, and protects the final decode **by construction**. Phase 4a is **panel only**: ALL.TXT, UDP, the QSO answerer and caller and the archive see nothing of the early batch. The automation (phase 4b) is a later spec.

## 2. Branch

`feat/122-step4-early-decode-panel` off the current `origin/main`. NEVER commit to `main`. This is `src/` **and `native/`** (the shim has no suppress switch, so either R4 mechanism changes `native/`).

## 3. Three things the spec did not say, found by reading the code (confirm or push back)

1. **The ordinary entry would run the residual pass too.** `Ft8Decoder.DecodeCoreAsync` reads `_subtractionEnabled` (`Ft8Decoder.cs:370`) and with the flag ON runs `SubtractionPass` inside the same call (`:489-501`). Subtraction has been ON by default since 2026-10-02. The early decode therefore needs its **own pass-0-only entry** that never reads the flag (design D3). Without it the early decode takes about 5 s, not 0.53 s.
2. **The shim does not allow "suppress hash writes" today** (`ft8_shim.c:839-841`, `cb_save_hash` adds unconditionally), and the shared state is wider than the table (the announce clock, the reject count, the `g_h12_*` counters and arrays). **QA recommends snapshot and restore** (design D4): suppressed writes would also break within-call hash resolution, so early text could differ from final text and R5 would not confirm the row. You record the final choice.
3. **The framer emits only complete windows** (`CycleFramer.cs:325`). The early window needs a new, optional emission point (design D1), and the pump is serial, so the early decode needs its own task and a shared **decode gate** (design D2).

## 4. Actions

1. **Decisions first**, recorded in `design.md` (tasks 1.1 to 1.4): which call gate 4a's early arm used; the R4 mechanism; the WebSocket shape; the shim number.
2. **Native** (tasks 2.x): `ft8_hash_state_save` / `ft8_hash_state_restore` over the full list of process-global state in `design.md` D4, a **caller-supplied** heap buffer (about 165 KB, never a stack) plus a size export, so that A2b can compare two saved images byte for byte; exports, interop, test double; **new `FT8_SHIM_VERSION`** everywhere it lives; rebuild `libft8.dll` (Windows, `native/ft8_lib_build/rebuild_shim.bat`) and `libft8.so` (`build_linux.sh`); macOS by CI; `python tools/check_native_version.py <binary> <number>` for each binary you built. **Shim number:** the next free above every number used or reserved on any live ref (`git grep` over `origin/*`); Stage B item B2 (`dev-tasks/2026-10-03-sub-feas-stage-b-b2-pruned-freq-search.md`) expects the next one too, so whichever merges second takes the one after.
3. **Decoder** (tasks 3.x): the pass-0-only early entry; the save/restore bracket inside the same `Task.Run` lambda as `DecodeAll` (`Ft8Decoder.cs:443-459`) with the restore in a `finally`.
4. **Framer** (tasks 4.x): optional provider and optional `earlyOutput`; exactly `EarlyTriggerSamples` samples, zero-filled; once per window; read at the lazy-resync point; **existing framer tests unmodified**.
5. **Daemon** (tasks 5.x): the decode gate (optional dependency), the early service (skip when busy, dial-frequency rule, same visibility filter, panel only), `Program.cs` wiring, the R7 log line with `finalWaitMs`.
6. **Matcher and panel events** (tasks 6.x): the pure matcher; the `decode-early` message and the optional `resolves` list; **the existing `decode` frame byte-identical when no early rows exist**; `web/js/main.js` and markup: marked, confirmed in place, unconfirmed kept, accessible (text or `aria-label`, never colour alone).
7. **Config** (tasks 7.x): `earlyDecodeEnabled` (false), `earlyDecodeCutSeconds` (2.0, 0.5 to 3.0 clamped); overlay; Settings control; a partial POST leaves both fields as they were.
8. **Docs and version** (tasks 8.x): **FR-083** in `REQUIREMENTS.md` (test names carry the `FR-083:` prefix, gate G3); `VERSION` bump (check `decoding_improvement`'s 0.55 first); README; the proposal already says `**User-facing:** yes` (gate G9b).
9. **Tests** as listed in the tasks (2.4 the **completeness test** that fails when a shim global is missing from the saved image, 3.3, **3.4 the A2b state round trip**, 4.2, 5.4, 6.1, 6.2, 6.3, 7.2), including a **stress test** (early and ordinary decode contending for many cycles, forced cancellation) before any timing is read, and **the flag-OFF characterisation** (same calls, same order).
10. **Run the full unfiltered `dotnet test`** and the `node --test web/js/*.test.js` suite; quote the exact commands and the pass/fail/skip counts (a filtered-out suite is silent, not green, HK-022). **Bracket the station config's mtime around the full run** (`%APPDATA%\OpenWSFZ\config.json`; the tests use a temp config since #202, but check).

## 5. Acceptance criteria (what QA checks; QA owns the measurements)

| Row | Predicate |
|---|---|
| **A1** | Existing suite green; new characterisation tests: flag OFF, panel events, ALL.TXT lines, UDP datagrams and QSO-channel batches for a fixed set of recorded cycles **identical** to the pre-change build |
| **A1b** (QA addition) | Flag ON on the same cycles: ALL.TXT lines, UDP datagrams, QSO-channel batches and archive entries **identical** to the flag-OFF run; only the panel frames differ |
| **A2** | Replay of gate 4a's corpus **P** (and **R**), flag ON vs OFF in separate fresh processes, driving the product's early path: the final decode's numeric multiset equal **N/N**. **Positive control:** a build with R4 disabled must reproduce the known loss at stamp `261001_112700` (the 1 731 Hz decode) |
| **A2b** (Architect's Amendment 1, `e24d541b`) | Deterministic: the saved image of **every** process-global the decode writes (design D4) before an early decode equals the image after the restore, **byte for byte**; the completeness test passes; the test fails when the restore omits any one global (QA mutates it). **Merge rule: A2b PASS plus A2 N/N on P and R.** If A2's positive control cannot reproduce the known loss, A2 is "not evaluable for this defect" and the merge rests on A2b |
| **A3** | Live, receive only, 40 m, >= 2 h: early batch published at median <= 13.7 s; skips <= 5 %; batch 1 no more than +0.10 s later than the flag-OFF hours. Blocks only the default-ON decision |
| **A4** | `C(2.0)` on A2's replay within +/-0.01 of 0.984 (P). Labels the figures |
| **A5** | Playwright: early rows marked; a confirming final row replaces its early row (one row); an unconfirmed early row keeps its mark; the mark in the accessibility tree; `live_verify_9_axes.py` |

A1, A1b, A2b, A2 (as scoped above) and A5 block the merge. The flag ships **OFF**; nothing here changes any default.

**Review checks QA will make beyond the rows:** the shim literal identical everywhere; the DLL SHA-256 in `libft8.version.txt` matches the file; `git diff --stat origin/main -- native` shows only the save/restore, the exports and the shim bump; the new tests would **fail** on a deliberately broken build (QA mutates the restore, the gate and the matcher); the existing `decode` WebSocket frame byte-identical with no early rows; `LicenseInventoryCheck` untouched (no new library).

## 6. Out of scope

Phase 4b (the automation acting on early decodes); running the residual pass on the partial window; any decode-rate claim; ALL.TXT, UDP, archive or QSO behaviour for early rows; changing any default; Stage B (a separate handoff).

## 7. CPU and timing

The PC hold has lifted. Your build and full suite are CPU-heavy: tell QA before you start them, so that nobody starts a timing run (A2, A3, the keying-latency K2, a Stage B replay) on top of them. QA's measurements are QA's, not yours.

## 8. Report back (in this order)

1. The four decisions of task 1 with FILE:LINE. 2. The shim number and every file changed for it; the `libft8.dll` SHA-256 (actual) and the `check_native_version.py` output. 3. The new tests by name, with the exact `dotnet test` and `node --test` lines and counts. 4. The WebSocket shape as built, with a captured frame of each kind (no message text). 5. What you could not do, said plainly.

*(`tools/pre_merge_check.py` is QA's review-step gate, not part of your checklist, HK-006.)*

## 9. References

Architect's spec and its predictions SD1 to SD4; gate 4a report ruling `qa/rr-study/2026-10-03-1435-architect-122-gate4a-report-ruling.md` and V2/D1 ruling `…-1420-…-v2-fail-ruling.md`; OpenSpec change `decode-early-batch-panel`; `src/OpenWSFZ.Ft8/CycleFramer.cs`, `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, `src/OpenWSFZ.Daemon/DecodePump.cs`, `src/OpenWSFZ.Web/WebSocketHub.cs`, `web/js/main.js`; `tests/OpenWSFZ.Daemon.Tests/DecodePumpTests.cs` and `TwoStageEngageCharacterisationTests.cs` (the characterisation pattern), `web/js/decodePanelBatches.test.js` (the panel pin).
