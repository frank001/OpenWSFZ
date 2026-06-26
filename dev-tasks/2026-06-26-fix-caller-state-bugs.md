# Handoff: Fix three caller state-machine bugs

**Date:** 2026-06-26  
**Prepared by:** QA engineer  
**Status:** Awaiting developer action

---

## 1. Context

Operator testing of the `feat/qso-caller` branch revealed three bugs in the Call CQ feature
implementation (task 11):

- Caller message rows 1 and 3 are **never highlighted** during CQ/RR73 transmission.
- **Double-clicking a responder row does nothing** (None mode entirely broken).
- In First mode the backend may **fail to detect WSJT-X's response** when the operator's
  callsign contains a portable suffix (e.g. `PD2FZ/P`).

All three are confined to the `feat/qso-caller` branch. No changes to `main` are required.

---

## 2. Branch

`feat/qso-caller` (existing) — add one or more commits directly to this branch.

---

## 3. Actions

### 3.1 — Fix caller `activeStates` (row highlighting)

**File:** `web/js/main.js`  
**Location:** `renderMessageRows`, the `if (effectiveRole === 'caller')` branch (~line 141)

**Current (wrong):**
```javascript
activeStates = ['TxAnswer', 'TxReport', 'Tx73'];
```

**Correct:**
```javascript
activeStates = ['TxCq', 'TxReport', 'TxRr73'];
```

**Why it is wrong:** `QsoCallerService.SetStateAndNotify` publishes the `CallerState` enum name
directly (`"TxCq"`, `"WaitAnswer"`, `"TxReport"`, `"WaitRr73"`, `"TxRr73"`).  The original code
used the *QsoState proxy names* (`TxAnswer`, `Tx73`) that the answerer uses — they are never
emitted by the caller's WS events.  Consequence: Row 1 (CQ) and Row 3 (RR73) are never
highlighted as active; Row 2 (Report) works by coincidence since both services emit `"TxReport"`.

---

### 3.2 — Fix `isResponderRow` state check (double-click non-functional)

**File:** `web/js/main.js`  
**Location:** `handleDecodes`, the `isResponderRow` constant (~line 384)

**Current (wrong):**
```javascript
const isResponderRow =
  currentTxRole === 'caller'
  && currentTxState === 'WaitReport'  // WaitAnswer proxy
  && currentCallerPartnerSelect === 'None'
  && msgTokens.length >= 3
  && txCallsign
  && msgTokens[0] === txCallsign;
```

**Correct (two changes):**
```javascript
const isResponderRow =
  currentTxRole === 'caller'
  && currentTxState === 'WaitAnswer'   // ← was 'WaitReport' (QsoState proxy name)
  && currentCallerPartnerSelect === 'None'
  && msgTokens.length >= 3
  && txCallsign
  && (msgTokens[0] === txCallsign
      || msgTokens[0] === txCallsign.split('/')[0]);  // ← handle base-callsign match
```

The base-callsign fallback (`split('/')[0]`) handles the case where the FT8 decoder emits
`PD2FZ Q1ABC JO22` (base callsign only, /P dropped) in response to a CQ from `PD2FZ/P`.
This mirrors the pattern already used in `tokenMatchesCallsign` on the CQ-answer side; apply
the same defensive matching here for symmetry and correctness.

**Why it is wrong:** The WS event state string for `CallerState.WaitAnswer` is `"WaitAnswer"`,
not `"WaitReport"` (`"WaitReport"` is the `QsoState` proxy name used only by the answerer).
Because `"WaitAnswer" === "WaitReport"` is always false, the `decode-responder` CSS class and
click handler are never attached.  Double-clicking a response row is a no-op because the
listener does not exist.

---

### 3.3 — Fix `TryParseResponder` for portable suffix callsigns (First mode)

**File:** `src/OpenWSFZ.Daemon/QsoCallerService.cs`  
**Method:** `TryParseResponder` (~line 913)

**Current (may fail with /P callsigns):**
```csharp
if (!parts[0].Equals(ourCallsign, StringComparison.OrdinalIgnoreCase))
    return false;
```

**Correct:**
```csharp
// Accept both the full compound callsign ("PD2FZ/P") and the base callsign
// ("PD2FZ"), because some FT8 decoder implementations drop the portable suffix
// when packing the destination token.
var baseCallsign = ourCallsign.Contains('/')
    ? ourCallsign[..ourCallsign.IndexOf('/')]
    : ourCallsign;
if (!parts[0].Equals(ourCallsign, StringComparison.OrdinalIgnoreCase) &&
    !parts[0].Equals(baseCallsign, StringComparison.OrdinalIgnoreCase))
    return false;
```

**Why it may be wrong:** When `CQ PD2FZ/P JO33` is transmitted and WSJT-X responds, WSJT-X
sends `PD2FZ/P Q1ABC JO22` (or, depending on encoder behaviour, `PD2FZ Q1ABC JO22` with the
`/P` suffix stripped from the destination token).  The current strict `OrdinalIgnoreCase` equality
fails the second form.  The fix accepts either form, matching the pattern already used by the
frontend's `tokenMatchesCallsign` helper.

Also add a `LogDebug` probe so this can be confirmed in the logs without further code changes:

```csharp
_logger.LogDebug(
    "QsoCallerService TryParseResponder: msg='{Msg}' ourCallsign='{Ours}' → match={Match}",
    msg, ourCallsign, /* result of the check above */ );
```

Place the log line just before the return statement.

---

### 3.4 — Fix `CallerPartnerSelectMode` enum serialisation (None mode frontend)

**Problem:** `CallerPartnerSelectMode` has no `[JsonConverter(typeof(JsonStringEnumConverter))]`.
STJ source-gen serialises it as integers (`0` = First, `1` = None).  The frontend reads:

```javascript
if (config.tx?.callerPartnerSelect) {
  currentCallerPartnerSelect = config.tx.callerPartnerSelect;
}
```

For `First (= 0)`: `if (0)` is falsy — `currentCallerPartnerSelect` stays at its initial string
`'First'`.  For `None (= 1)`: `currentCallerPartnerSelect = 1` (a number).  The downstream check
`currentCallerPartnerSelect === 'None'` then compares `1 === 'None'` — **always false**.

**Fix option A (preferred — consistent with TxRole if that is already a string enum):**

Add to `src/OpenWSFZ.Abstractions/CallerPartnerSelectMode.cs`:
```csharp
[JsonConverter(typeof(JsonStringEnumConverter))]
public enum CallerPartnerSelectMode { ... }
```

And add `typeof(CallerPartnerSelectMode)` to `AppJsonContext` if it is not already listed.

**Fix option B (frontend only — no C# change):**

Replace the frontend comparison with integer guards:
```javascript
// CallerPartnerSelectMode: 0 = First, 1 = None
const isNoneMode = currentCallerPartnerSelect === 'None'    // string (initial value)
                || currentCallerPartnerSelect === 1;         // integer from API
```

Option A is cleaner and prevents future confusion.  Note that this change is a **breaking change
to the wire format** (was integer, now string) — verify no other consumer (settings.js, etc.)
reads this field and needs updating.

Also update the `if` check in `main.js` that reads from config:
```javascript
// Current (falsy for 0)
if (config.tx?.callerPartnerSelect) { ... }

// Fixed (truthy for both strings and non-zero integers):
if (config.tx?.callerPartnerSelect !== undefined && config.tx.callerPartnerSelect !== null) { ... }
```

---

### 3.5 — Regression tests

Add or update tests in `OpenWSFZ.Web.Tests` or `OpenWSFZ.Daemon.Tests`:

1. **`TryParseResponder_MatchesFullCallsign`** — assert that `TryParseResponder("PD2FZ/P Q1ABC JO22", "PD2FZ/P", ...)` returns true with partner `"Q1ABC"`.
2. **`TryParseResponder_MatchesBaseCallsignWhenSlashPDropped`** — assert that `TryParseResponder("PD2FZ Q1ABC JO22", "PD2FZ/P", ...)` returns true with partner `"Q1ABC"`.
3. **`TryParseResponder_RejectsNonMatchingCallsign`** — assert that `TryParseResponder("Q9ZZZ Q1ABC JO22", "PD2FZ/P", ...)` returns false.

Existing `QsoCallerService` unit tests (if any) that exercise the `isResponderRow` state string
should be updated to use `"WaitAnswer"` rather than `"WaitReport"` if they were written against
the wrong proxy name.

---

## 4. Acceptance criteria

QA will verify the following before approving merge to `main`:

1. **Row highlighting:** During CQ transmission (TxCq state), Row 1 of the TX panel is highlighted.
   During RR73 transmission (TxRr73 state), Row 3 is highlighted.  Row 2 is highlighted during
   report TX, as before.
2. **None mode click:** With `CallerPartnerSelect = None`, a row where `msgTokens[0]` matches the
   operator callsign in WaitAnswer state receives the `decode-responder` CSS class and a click
   handler that fires `postTxSelectResponder`.  Clicking (not double-clicking — it is a single
   click) selects the responder and the TX panel advances.
3. **First mode auto-engage:** With `CallerPartnerSelect = First` and operator callsign `PD2FZ/P`,
   a simulated response batch containing `"PD2FZ Q1ABC JO22"` (base-only destination) is
   auto-detected and the caller advances to `TxReport`.
4. **Existing tests green:** `dotnet test OpenWSFZ.slnx -c Release` — zero failures.
5. **Zero build warnings:** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
6. **Answerer regression:** With daemon started in Answerer mode and no "Call CQ" interaction,
   the answerer panel shows `——— PD2FZ/P JO33` on Row 1 (answerer template), and no
   caller-specific highlighting or `decode-responder` rows appear.

---

## 5. References

- Dev task: `dev-tasks/2026-06-25-call-cq-button.md` (original feature handoff)
- `QsoCallerService.SetStateAndNotify` — publishes `CallerState` enum names directly (not `QsoState` proxy names)
- `QsoCallerService.State` property (~line 153) — maps `CallerState → QsoState` for HTTP status only
- `renderMessageRows` (~line 126) — caller template branch; activeStates array
- `isResponderRow` (~line 382) — state string check
- Frontend `tokenMatchesCallsign` (~line 262) — already handles base/compound callsign match; apply same logic to `isResponderRow`
- Lesson learned #18 (MEMORY.md) — sealed classes prevent substitution; keep the base-callsign logic in a named helper, not inline, for testability
