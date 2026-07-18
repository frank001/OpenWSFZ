## 1. Shared SNR formatting helper

- [x] 1.1 Add `internal static string FormatSnrReport(int snr)` to `QsoCallerService.cs` (near
  `IsSignalReport`/`IsRogerReport`): clamp `snr` to `[-30, 30]`, format as a two-digit signed FT8
  report (`+00`, `-13`, `+30`).
- [x] 1.2 Unit test the formatter directly (positive, negative, zero, and both clamp boundaries —
  e.g. `+42` → `+30`, `-42` → `-30`).

## 2. QsoCallerService — real SNR in the caller's bare report

- [x] 2.1 Add `private string _rstSent = "+00";` field (mirrors `_rstRcvd`); reset it to `"+00"`
  alongside `_rstRcvd` in `HandleIdleAsync`'s session-init block.
- [x] 2.2 Add `private int? _pendingResponderSnr;` field (sibling to `_pendingResponderGrid`).
- [x] 2.3 In `SelectResponderAsync` (`None`-mode operator-click path), set `_pendingResponderSnr =
  recentDecode?.Snr` alongside the existing `grid` re-derivation — no new lookup needed,
  `_recentResponderDecodes` already stores the full `DecodeResult`.
- [x] 2.4 Add an optional `int? snr = null` parameter to `TestSetPendingResponder`, set
  `_pendingResponderSnr = snr`.
- [x] 2.5 Change `ExecuteTxReportAsync`'s signature to accept `int snr`; compose
  `var report = FormatSnrReport(snr); _rstSent = report; var reportMessage = $"{partner} {tx.Callsign} {report}";`
  replacing the hardcoded `+00`.
- [x] 2.6 Update `HandleWaitAnswerAsync`'s `First`-mode call site (`r` already in scope in the
  `foreach` loop) to pass `r.Snr` into `ExecuteTxReportAsync`.
- [x] 2.7 Update `HandleWaitAnswerAsync`'s `None`-mode pending-responder call site to read
  `_pendingResponderSnr` under `_stateLock` alongside the other pending fields and pass it through
  (default to `0` if somehow `null`, matching the field's optionality without ever throwing).
- [x] 2.8 Update `RetryOrAbortAsync`'s `WaitRr73` retry branch to resend `_rstSent` instead of
  recomputing/hardcoding `+00`.
- [x] 2.9 Update `ExecuteTxRr73Async`'s `QsoRecord` builder: `RstSent = _rstSent,` replacing the
  fixed `"+00"` literal and its `// fixed report (TX-D04 deferred)` comment.
- [x] 2.10 Clear `_pendingResponderSnr = null` in `SafeAbortToIdleAsync` alongside
  `_pendingResponderGrid`.

## 3. QsoAnswererService — real SNR in the answerer's roger-report

- [x] 3.1 Add `private string _rstSent = "R+00";` field (mirrors `_rstRcvd`).
- [x] 3.2 In `HandleWaitReportAsync`'s signal-report branch (`r` already in scope in the `foreach`
  loop), compose `var formatted = QsoCallerService.FormatSnrReport(r.Snr); _rstSent = "R" +
  formatted; var reportMessage = $"{partner} {ours} R{formatted}";` replacing the hardcoded
  `R+00`. (`_lastTxMessage = reportMessage;` already persists this into the existing generic retry
  path unchanged — no separate retry fix needed here, unlike the caller.)
- [x] 3.3 Update `BuildAndWriteQsoRecordAsync`'s `QsoRecord` builder: `RstSent = _rstSent,`
  replacing the fixed `"R+00"` literal; reword the doc comment above it that currently claims "the
  report this daemon always sends."

## 4. Thread Snr through the jump-in path (EngageAtAsync)

- [x] 4.1 Add `int Snr` to `EngageDecodeRequest` (`src/OpenWSFZ.Web/AppJsonContext.cs`), default
  `0` for backward compatibility with an un-updated frontend bundle during a rolling deploy.
- [x] 4.2 Add a new trailing `int snr` parameter to `IQsoController.EngageAtAsync`
  (`src/OpenWSFZ.Abstractions/IQsoController.cs`), documented analogously to the existing
  `rawPayload` parameter doc.
- [x] 4.3 Update `QsoControllerRouter.EngageAtAsync` to accept and pass through the new parameter
  unchanged to `_answerer.EngageAtAsync(...)`.
- [x] 4.4 Update `QsoCallerService.EngageAtAsync` stub to accept the new parameter (signature
  parity only — body remains `Task.CompletedTask`).
- [x] 4.5 Update `QsoAnswererService.EngageAtAsync` to accept the new parameter, store it in a new
  `private int _jumpSnr;` field (mirrors `_jumpRawPayload`) under `_stateLock`.
- [x] 4.6 Update `TestSetJumpTarget` to accept an optional `int snr = 0` parameter, set `_jumpSnr`.
- [x] 4.7 Update `HandleIdleAsync`'s jump-in consumption block to read `_jumpSnr` under
  `_stateLock` alongside the other jump fields and pass it into `ExecuteJumpInAsync`.
- [x] 4.8 Update `ExecuteJumpInAsync`'s signature to accept `int snr`. At the top of the method
  (alongside the existing `_partnerGrid = null;` comment block), explicitly set `_rstSent = "R+00";`
  with a comment documenting this as the accepted placeholder for the `SendRr73`/`Send73` cases
  that never compose a report this session (mirrors the `_partnerGrid = null` treatment
  immediately above it).
- [x] 4.9 In the `EngagePoint.SendReport` case, overwrite with the real value: `var formatted =
  QsoCallerService.FormatSnrReport(snr); _rstSent = "R" + formatted; var msg = $"{partner}
  {tx.Callsign} R{formatted}";` replacing the hardcoded `R+00`.
- [x] 4.10 In `WebApp.cs`'s `engage-decode` handler, forward `req.Snr` into all three
  `EngageAtAsync` call sites (`Send73`, `SendRr73`, `SendReport` branches) — only the `SendReport`
  branch's value is actually consumed downstream, but all three call sites share the same method
  signature.
- [x] 4.11 In `web/js/api.js`'s `postTxEngageDecode`, add an `snr` parameter and include it in the
  POST body.
- [x] 4.12 In `web/js/main.js`'s dblclick handler, pass `r.snr` (already present on every decode
  row per the existing JSDoc typedef) into both `postTxEngageDecode` call sites (the initial call
  and the post-confirm retry call).

## 5. Regression tests

- [x] 5.1 `QsoCallerServiceTests.cs`: assert the `First`-mode `TxReport` message contains the
  triggering decode's actual `Snr` (test helper `Make`/`MakeResponse` already defaults `Snr = -5`
  — assert the transmitted message contains `"-05"`, not `"+00"`).
- [x] 5.2 `QsoCallerServiceTests.cs`: assert the `None`-mode `SelectResponderAsync` →
  pending-responder path also uses the real `Snr` (construct a `DecodeResult` with a distinct
  `Snr`, e.g. `+11`, select it, assert the transmitted report contains `"+11"`).
- [x] 5.3 `QsoCallerServiceTests.cs`: assert a `WaitRr73` retry retransmits the same report value
  chosen at `TxReport` time, not a recomputed one.
- [x] 5.4 `QsoCallerServiceTests.cs`: assert the written `QsoRecord.RstSent` reflects the real
  value, not `"+00"`.
- [x] 5.5 `QsoAnswererServiceTests.cs`: assert the normal `WaitReport` reply message contains the
  triggering decode's actual `Snr`, not `"R+00"`.
- [x] 5.6 `QsoAnswererServiceTests.cs`: assert a jump-in `EngagePoint.SendReport` reply (via
  `TestSetJumpTarget` with a non-default `snr`) contains the real value, not `"R+00"`.
- [x] 5.7 `QsoAnswererServiceTests.cs`: assert a jump-in `EngagePoint.SendRr73`/`Send73` still
  writes `RstSent = "R+00"` (the accepted placeholder) — explicit non-regression check.
- [x] 5.8 `QsoAnswererServiceTests.cs`: assert `BuildAndWriteQsoRecordAsync`'s `RstSent` reflects
  the real value on the normal-completion path.
- [x] 5.9 `EngageDecodeEndpointTests.cs`: update the fake `IQsoController` to capture the new `snr`
  parameter; add a test asserting a `POST /api/v1/tx/engage-decode` body with a non-zero `snr`
  forwards it through to `EngageAtAsync` for the `SendReport` branch.

## 6. Verification

- [x] 6.1 Run `python3 tools/pre_merge_check.py` (HK-006) before declaring this ready for merge —
  full suite, Gate G3/G8/G9a, Release build, AOT publish. **Result: PASS WITH WARNINGS** — G9a,
  Release build, full test suite (1315/1315), G3 traceability, G8 `openspec validate --strict --all`
  (56/56) all PASS; self-contained non-AOT publish PASS. AOT publish WARNed on a missing local
  `vswhere.exe`/MSVC linker toolchain — a pre-existing local-environment gap unrelated to this
  change (nothing here touches audio/AOT code; the daemon's NAudio/WASAPI AOT limitation is
  already tracked separately as qa-backlog N9). Not re-attempted locally; CI carries the real AOT
  gate per HK-006's own guidance.
- [x] 6.2 Manually verify that a caller/answerer exchange now logs a plausible non-`+00`/`R+00`
  `RstSent` end-to-end, not just at the unit-test level. **Scoped down, noted here rather than
  silently marked done as originally written:** no real hardware/audio-loopback run was performed
  (none available in this environment). Verification instead relied on the regression tests added
  in §5, which exercise the actual production `ExecuteTxReportAsync`/`HandleWaitReportAsync`/
  `ExecuteJumpInAsync` methods end-to-end through the real state machine, the real
  `Ft8Encoder.EncodeMessage`/`Ft8AudioSynthesiser` TX path (same `reportMessage`/`msg` string used
  for both the synthesised audio and the persisted `_rstSent`/ADIF value — not two independently
  derived values that could silently diverge), and assert the final `QsoRecord.RstSent` reaching
  `IAdifLogWriter.AppendQsoAsync`. A live hardware acceptance run (mirroring the Captain's original
  ~2.5 hour session that surfaced TX-D04) would be the gold-standard follow-up before the next
  live-air session, at the Captain's discretion.
