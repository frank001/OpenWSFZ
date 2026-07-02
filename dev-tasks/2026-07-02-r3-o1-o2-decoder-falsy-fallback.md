# DEV TASK — R3-O1/R3-O2: Decoder save — replace falsy fallback with Number.isFinite guard

**Date:** 2026-07-02
**QA defect IDs:** R3-O1, R3-O2
**Severity:** Low — non-destructive; API clamping is the safety net
**OpenSpec change:** `decoder-settings-page`

---

## 1. Context

The decoder-settings-page change introduced three `<input type="number">` elements
(`#decoder-k`, `#decoder-corr`, `#decoder-nhard`) in `web/settings.html`. When the
user clicks Save, `settings.js` reads these inputs and assembles a `decoder` object for
`POST /api/v1/config`.

The current collection code (lines 831–835 of `settings.js`) uses JavaScript's falsy
`||` operator to supply defaults:

```js
const decoder = {
  kMinScorePass2:   parseInt(decoderK.value,     10) || 10,
  osdCorrThreshold: parseFloat(decoderCorr.value)    || 0.10,
  osdNhardMax:      parseInt(decoderNhard.value, 10) || 60,
};
```

The defect: `0` is falsy in JavaScript. If the user types `0` into any of these inputs,
`parseInt/parseFloat` returns `0`, the `||` substitutes the default, and the API receives
the default rather than `0`. The API then clamps the value to its minimum (5, 0.05f, or
30 respectively) — so there is no data corruption, but the submitted value silently
diverges from what the user entered. On expert-only controls this is confusing and
incorrect.

The fix pattern is `Number.isFinite(x) ? x : default`, which treats `0` as a valid
finite number and only substitutes the default when the input is empty, `NaN`, or
`Infinity`.

---

## 2. Branch name

```
fix/r3-o1-o2-decoder-falsy-fallback
```

---

## 3. Actions

### 3.1 — `web/js/settings.js` (lines 830–835)

Replace the three-property `decoder` object literal with a variable-extraction pattern:

**Before:**
```js
// Collect decoder config (decoder-settings-page).
const decoder = {
  kMinScorePass2:   parseInt(decoderK.value,     10) || 10,
  osdCorrThreshold: parseFloat(decoderCorr.value)    || 0.10,
  osdNhardMax:      parseInt(decoderNhard.value, 10) || 60,
};
```

**After:**
```js
// Collect decoder config (decoder-settings-page).
// Use Number.isFinite rather than || to correctly handle user-entered 0
// (falsy-or-default would silently replace 0 with the calibrated default).
const decoderKRaw     = parseInt(decoderK.value,     10);
const decoderCorrRaw  = parseFloat(decoderCorr.value);
const decoderNhardRaw = parseInt(decoderNhard.value, 10);
const decoder = {
  kMinScorePass2:   Number.isFinite(decoderKRaw)     ? decoderKRaw     : 10,
  osdCorrThreshold: Number.isFinite(decoderCorrRaw)  ? decoderCorrRaw  : 0.10,
  osdNhardMax:      Number.isFinite(decoderNhardRaw) ? decoderNhardRaw : 60,
};
```

No other files need to change. The API validation and clamping in `WebApp.cs` are
unaffected and remain the authoritative safety net.

---

## 4. Acceptance criteria

The QA engineer will verify the following before approving merge:

- [ ] **AC-1** Open Settings → Advanced Decoder Settings. Enter `0` in the
  **K min score** field, click Save. DevTools Network tab shows the `POST /api/v1/config`
  request body contains `"kMinScorePass2": 0` (not `10`). Response is `200 OK`.
- [ ] **AC-2** Enter `0` in **OSD correction threshold**, click Save. Request body
  contains `"osdCorrThreshold": 0` (not `0.1`). Response is `200 OK` (API clamps to
  `0.05` — that is correct and expected; the point is that the submitted value is `0`,
  not the default `0.1`).
- [ ] **AC-3** Enter `0` in **OSD nhard max**, click Save. Request body contains
  `"osdNhardMax": 0` (not `60`). Response is `200 OK` (API clamps to `30` — again,
  expected).
- [ ] **AC-4** The existing happy-path behaviour is unaffected: entering the calibrated
  defaults (10, 0.10, 60) submits those values unchanged.
- [ ] **AC-5** Leaving all three fields empty submits the calibrated defaults (10, 0.10,
  60), matching the prior behaviour for blank inputs (`parseInt("") → NaN →
  Number.isFinite(NaN) → false → default`).
- [ ] **AC-6** Build: `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.
  Full test suite: `dotnet test OpenWSFZ.slnx -c Release` — 0 failures. (No new
  automated tests are required; this is a JS-only save-path fix fully covered by manual
  DevTools inspection.)

---

## 5. References

- `web/js/settings.js` lines 830–835 — decoder collection block
- `src/OpenWSFZ.Web/WebApp.cs` — `POST /api/v1/config` decoder validation (clamping:
  KMinScorePass2 → [5,30], OsdCorrThreshold → [0.05,0.40], OsdNhardMax → [30,100])
- OpenSpec change: `openspec/changes/decoder-settings-page/`
- R3 review findings: deferred observations R3-O1 and R3-O2 in MEMORY.md
