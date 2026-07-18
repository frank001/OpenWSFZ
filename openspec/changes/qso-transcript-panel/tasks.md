## 1. Before screenshot

- [x] 1.1 Capture a before screenshot of the current TX panel (existing "TX History" abort-only
      section), ahead of any implementation work (HK-005).
      Run via `dotnet run` (not an AOT publish, per the documented working deployment model);
      save as `openspec/changes/qso-transcript-panel/before.png`.

## 2. DOM-free transcript module

- [x] 2.1 Create `web/js/qsoTranscript.js` (mirroring `web/js/decodeFilter.js`'s DOM-free
      pattern — no `document`/`window` references) exporting:
      - `shouldCaptureDecode(message, txCallsign, currentPartner)` — the belongs-to-conversation
        matcher (Decision 3): true if `message`'s space-delimited tokens include `txCallsign` or
        `currentPartner`.
      - `buildTranscriptEntry(kind, text, partner)` — constructs a `{ isoTs, kind, text, partner
        }` entry object, `kind` one of `'sent' | 'received' | 'abort' | 'partner-change'`.
      - `pushTranscriptEntry(log, entry, maxLen)` — unshifts `entry` onto `log` (newest-on-top)
        and truncates to `maxLen` (Decision 5, `TRANSCRIPT_LOG_MAX = 100`).
      - `hasEnteredNewActiveTxState(prevState, newState, activeStates)` — the state-transition
        detector for Decision 2 (true only when `newState !== prevState` and `newState` is a
        member of `activeStates`).
- [x] 2.2 Add `web/js/qsoTranscript.test.js` (`node --test` style, matching
      `decodeFilter.test.js`'s structure) covering: matcher true/false cases including the
      Idle-state permissive case (Decision 3's last paragraph), transition detection (fires once
      on state change into an active state, not on repeated pushes, fires again on a
      revisit-after-leaving), and cap truncation at `TRANSCRIPT_LOG_MAX`.
- [x] 2.3 Run `node --test web/js/qsoTranscript.test.js` locally and confirm all cases pass.

## 3. `web/index.html` markup

- [x] 3.1 Replace the `#tx-abort-log-section` block (currently titled "TX History") with:
      ```html
      <!-- QSO Transcript (FR-062) — populated by JS; hidden until first entry -->
      <div id="tx-transcript-section" hidden>
        <p class="tx-transcript-title">QSO Transcript</p>
        <ol id="tx-transcript-log" class="tx-transcript-list"></ol>
      </div>
      ```
      in the same DOM position (inside `#tx-panel`, after `#tx-msg-3`).

## 4. `web/js/main.js` integration

- [x] 4.1 Import the new module's exports at the top of `main.js`.
- [x] 4.2 Rename `txAbortLogSection`/`txAbortLogEl`/`txAbortLog`/`TX_ABORT_LOG_MAX` to
      `txTranscriptSection`/`txTranscriptLogEl`/`txTranscriptLog`/`TRANSCRIPT_LOG_MAX = 100`,
      pointing at the new element ids from task 3.1.
      (Implementation note: `TRANSCRIPT_LOG_MAX` is imported from `qsoTranscript.js` rather than
      re-declared locally, avoiding a second source of truth for the same constant — matches the
      `UNFILTERED_DECODE_FILTER` precedent where the shared value lives in the DOM-free module.)
- [x] 4.3 Replace `appendTxAbortLog(reason, partner)` with `appendTranscriptEntry(kind, text,
      partner)`, using `pushTranscriptEntry`/`buildTranscriptEntry` from `qsoTranscript.js`, and
      rendering each `<li>` with a CSS class derived from `kind` (`transcript-sent` /
      `transcript-received` / `transcript-event`).
      (Implementation note: built via `createElement`/`textContent`, not `innerHTML` string
      interpolation — a 'received' entry's text is a raw FT8 message and, per `handleDecodes`'
      own Type-5 free-text caveat, may legally contain HTML metacharacters that must not be
      parsed as markup.)
- [x] 4.4 Update the `txState` handler's existing abort-reason branch to call
      `appendTranscriptEntry('abort', event.abortReason, event.partner ?? null)` instead of
      `appendTxAbortLog(...)`.
- [x] 4.5 Add module-scope `previousTxState` tracking (or reuse the existing `prevState` local
      already captured at the top of `renderTxPanel` — confirm whether it needs to be hoisted to
      module scope to survive across calls). Inside `renderMessageRows` (or immediately after its
      call in `renderTxPanel`), call `hasEnteredNewActiveTxState(...)`; on true, compute the sent
      message text for the newly-active row (reuse the same `texts[i]` the function already
      computes) and call `appendTranscriptEntry('sent', texts[i], currentTxPartner)`.
      (Implementation note: the existing `prevState` local sufficed — `renderMessageRows` now
      takes an optional `prevState` parameter, defaulting to `state` itself so the
      non-transition-driven call site in `startCycleTimerIfEnabled` stays a no-op without
      modification.)
- [x] 4.6 Inside `handleDecodes`, for each `r` in `results`, call `shouldCaptureDecode(r.message,
      txCallsign, currentTxPartner)` **before** the `isDecodeVisible`/`tr.hidden` line, independent
      of `currentDecodeFilter`; on true, call `appendTranscriptEntry('received', r.message, currentTxPartner)`.
- [x] 4.7 Add partner-change detection: wherever `currentTxPartner` is assigned a new value
      (inside `renderTxPanel`), if the new value is non-null and differs from the immediately
      prior value, call `appendTranscriptEntry('partner-change', newPartner, newPartner)` **before**
      any sent/received entry for the new partner is appended in the same event handling pass.

## 5. CSS

- [x] 5.1 Add `.tx-transcript-title`, `.tx-transcript-list`, `.transcript-sent`,
      `.transcript-received`, `.transcript-event` to `web/css/app.css`. Reuse existing
      `--color-*` custom properties for the two directional colors rather than introducing new
      raw hex values (Decision 6) — do not repeat the un-tokenized `#803030` shortcut noted in
      the standing TX-armed-color TODO.

## 6. Requirements documentation

- [x] 6.1 Add a new changelog row to `REQUIREMENTS.md` documenting **FR-062** (QSO Transcript
      section — unified sent/received/abort/partner-change log, sourced ahead of
      decode-panel-filtering and decode-noise-suppression, direction-colorized, capped rolling
      session log), following the existing row format.
- [x] 6.2 Bump the root `VERSION` file to the next minor version, **pre-merge, in this branch**
      (per the Captain's explicit direction — overrides the row-1.39 "bump lands at archive"
      convention previously followed; `proposal.md` already declares `**User-facing:** yes`).
      Confirm `Directory.Build.props`-derived build metadata and the welcome banner pick up the
      new value (`release-versioning` capability's cross-surface consistency invariant).
      VERSION bumped 0.41 → 0.42; welcome-banner pickup confirmed during task 7.1's rebuild.

## 7. Verification

- [x] 7.1 `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings (this change
      touches no `.cs` files; this is a regression check, not expected to require fixes).
      0 errors, 0 warnings.
- [x] 7.2 `dotnet test OpenWSFZ.slnx -c Release` — confirm all existing tests still pass
      unchanged.
      1297/1297 passed. (First run showed 2 E2E failures — `DaemonProcess.StartAsync` timed out
      waiting for the welcome banner because a leftover `dotnet run` instance from task 1.1's
      screenshot capture was still squatting on port 8080; stopped it and re-ran
      `OpenWSFZ.E2E.Tests` alone, clean 3/3 — confirmed environmental, not a regression from
      this change, which touches no `.cs` files.)
- [x] 7.3 `node --test web/js/*.test.js` — confirm `qsoTranscript.test.js` passes alongside the
      existing `decodeFilter.test.js`.
      45/45 passed (25 decodeFilter + 20 qsoTranscript).
- [x] 7.4 Manual/browser verification (Playwright is available in this environment — see
      HK-007 — do not treat this as blocked on manual-only action): drive a full simulated QSO
      exchange plus a partner switch plus a column-filter change, and confirm the transcript
      shows sent + received entries in order, survives the partner switch with a separator, and
      keeps showing partner traffic even while the column filter hides it from `#decodes-table`.
      Verified live via an ad-hoc Playwright driver (`qa/uat-tmp/`, gitignored, not committed —
      matches the `qa/d-caller-018-*` ad-hoc-Playwright precedent) against the real Release
      daemon: intercepted `ws.js`'s `addEventListener('message', …)` registration to hand-feed
      synthetic `txState`/`decode` frames through the real client code path — no TX/engage
      endpoint ever called, no hardware touched. Confirmed: sent entries fire once per genuine
      state transition (a repeated push of the same state produced no duplicate); a real
      `POST /api/v1/decode-filter` column-filter change hid both matching decode rows in
      `#decodes-table` (`hidden: true`) while both their transcript entries remained; the
      partner-change separator appeared before the first sent/received entry for each new
      partner; newest-on-top chronological order held throughout. Zero console errors.
      **Incidental finding, not caused by this change:** the Release daemon this session
      resumed with `tx.autoAnswer` already armed from a prior session's persisted config, and
      genuinely transmitted (real RF) to answer a real over-the-air CQ from a real station
      mid-verification — entirely independent of this test (no TX/engage call was made by the
      script) and unaffected by the synthetic client-side injection (confirmed via the daemon's
      own log: `QsoAnswererService` kept retrying that real callsign on its own timeline
      throughout). Flagged to the Captain; the real callsign never appears in any committed
      artifact (screenshots containing it were kept under gitignored `qa/uat-tmp/`, per
      NFR-021 — `after.png` for task 8.1 uses only synthetic Q-prefix callsigns).

## 8. After screenshot

- [x] 8.1 Capture an after screenshot of the TX panel showing the QSO Transcript section
      populated with at least one sent, one received, and one partner-change entry (HK-005).
      Save as `openspec/changes/qso-transcript-panel/after.png`.
      Captured via the same safe WS-message-interception technique as task 7.4, using only
      synthetic Q-prefix callsigns (NFR-021) — no real third-party callsign appears in this
      committed artifact.
