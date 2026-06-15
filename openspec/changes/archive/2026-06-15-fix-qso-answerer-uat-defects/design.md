## Context

During UAT of `ft8-qso-answerer-v1` two defects were observed in the loopback test environment. Neither prevented QSO completion in the VB-Cable setup (where TX and RX audio paths are independent), but A-01 would cause incorrect on-air behaviour and A-02 produces confusing WRN log noise on every config save.

**A-01 — Retry fires one FT8 cycle early.** FT8 alternates between two 15-second TX windows. After our TX completes, we enter `WaitReport`. The next capture window to be decoded covers our own TX period — the capture RMS is 0 because we were transmitting (not because the partner was silent). The silence guard fires, the state machine sees an empty batch, and fires a retry immediately. This retry transmits in the partner's response window (the even cycle), potentially overriding the partner's signal on real RF.

**A-02 — TX settings fields not pre-populated.** `settings.js` correctly pre-populates audio device selects and other form fields from `GET /api/v1/config` on load. The `watchdogMinutes` and `retryCount` number inputs in the TX tab, however, are not assigned a value from `config.tx` — they remain at the browser's default (0 or blank). On Save, `POST /api/v1/config` submits 0 for these fields, triggering the API's clamp-to-minimum warning on every save.

## Goals / Non-Goals

**Goals:**
- A-01: In `WaitReport` and `WaitRr73`, skip the first empty cycle after entering the state — it is always our own TX window. Only count an empty cycle as a missed response from the second cycle onward.
- A-02: Pre-populate `watchdogMinutes` and `retryCount` inputs in `settings.js` from `config.tx` in the same block that pre-populates all other TX fields.

**Non-Goals:**
- Precise cycle-boundary synchronisation (TX-D01 / TX timing epic) — not in scope.
- Any change to the retry count, watchdog duration, or API clamping logic.
- Any other Settings form fields.

## Decisions

### D1 — A-01: Skip-first-cycle flag, not timestamp comparison

**Chosen:** Introduce a `bool _skipNextRetry` field in `QsoAnswererService`. Set it to `true` whenever the state machine enters `WaitReport` or `WaitRr73`. On the first empty-batch (silence or no matching decode) event received in those states: do nothing and set `_skipNextRetry = false`. On every subsequent empty-batch event, apply the existing retry / abort logic.

**Alternative considered:** Compare the cycle timestamp with the TX completion timestamp and skip if the cycle overlaps. Rejected — timestamps are not threaded through `ProcessBatchAsync` today and adding them is disproportionate work for a one-cycle guard.

**Rationale:** The flag is the minimal, self-contained change. It does not alter behaviour in any case where the partner responds in the first cycle (the flag is cleared when a matching decode is received, with no effect). It correctly handles both `WaitReport` → retry and `WaitRr73` → retry.

### D2 — A-02: Assign inputs in the existing config-load callback

**Chosen:** In `settings.js`, in the section that reads `config.tx` to populate the TX tab form fields, add:
```js
document.getElementById('tx-watchdog-minutes').value = config.tx.watchdogMinutes;
document.getElementById('tx-retry-count').value      = config.tx.retryCount;
```

**Alternative considered:** Set `value` attributes in `settings.html` to match server defaults. Rejected — hardcoding defaults in the HTML duplicates the server-side defaults and diverges when they change.

**Rationale:** The fix belongs alongside the other `config.tx.*` assignments in the JS load callback. Minimal diff; no structural change required.

## Risks / Trade-offs

**[Risk] Two-cycle wait before retry could lengthen failed QSO sequences** → The extra one-cycle delay is the correct FT8 protocol behaviour. WSJT-X itself waits through the partner cycle before retrying. No practical impact.

**[Risk] `_skipNextRetry` set to `true` but partner responds in cycle 1** → No issue. The flag is cleared on any decode event (matching or non-matching) that does not hit the silence-guard path. The matching-response branch is unaffected.

**[Risk] `settings.html` input element IDs differ from `tx-watchdog-minutes` / `tx-retry-count`** → Developer must confirm actual IDs in `settings.html` before implementing D2. If IDs differ, adjust accordingly.
