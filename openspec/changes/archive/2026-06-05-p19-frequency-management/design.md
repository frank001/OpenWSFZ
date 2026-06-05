## Context

The application currently handles dial frequency as a single scalar value: either the live CAT-polled `ICatState.DialFrequencyMHz` or the manually configured `AppConfig.DecodeLog.DialFrequencyMHz`. There is no concept of a frequency catalogue, no per-protocol grouping, and no mechanism to command the rig to a new frequency. The CAT abstraction (`IRadioConnection`) is deliberately read-only — the p16 design explicitly excluded all write commands.

The operator must today either configure the dial frequency in Settings (a round-trip requiring a Save), or rely on the live CAT read. Neither allows quick band-switching from the main UI. This change introduces a frequency list backed by a committed `frequencies.json` file and the ability to tune the rig (or update the manual setting) from a dropdown in the status bar.

## Goals / Non-Goals

**Goals:**

- Provide a curated, editable frequency list per protocol, shipped with sensible defaults
- Allow the operator to select a working frequency from the main GUI in one click
- When CAT is active, propagate the selection as a set command to the rig
- When CAT is inactive, propagate the selection as a config update (replaces the manual dial frequency)
- Keep the `frequencies.json` format human-readable and editable on disk
- Design the data model for multi-protocol from day one (FT8 first, others later)

**Non-Goals:**

- Frequency-set confirmation / echo-back validation from the rig (set-and-forget)
- IARU region filtering, date/time scheduling, or "preferred" frequency flags (WSJT-X features not required)
- Protocol switching from the main GUI (protocol is implicitly FT8 in this change)
- Frequency split operation or VFO-B management
- Hamlib rig model selection (deferred)

## Decisions

### D1 — `frequencies.json` as a separate file, not embedded in `app.json`

The frequency list is operator-curated data distinct from application configuration (port, audio device, CAT settings). Keeping it in a separate file allows the operator to replace or share it independently, and avoids bloating `app.json`. The daemon resolves the path for `frequencies.json` using the same convention as `app.json` (directory containing the executable, or a configured override). On first run, if the file is absent, the daemon writes the compiled-in default list.

**Alternative considered:** Embed as a `frequencies` array in `app.json`. Rejected — mixed concerns; the list can grow large; independent file allows future tooling.

### D2 — `IFrequencyStore` service, not a static resource

A DI-registered `IFrequencyStore` singleton with `GetAllAsync()` and `SaveAsync(IReadOnlyList<FrequencyEntry>)` methods mirrors the existing `IConfigStore` pattern. This keeps the frequency list injectable in tests without file I/O, and makes it easy for `POST /api/v1/frequencies` and `POST /api/v1/tune` to share the in-memory list.

**Alternative considered:** Serve `frequencies.json` as a static file and have the browser read/write it directly. Rejected — bypasses DI, breaks the API contract, and makes tuning impossible.

### D3 — `SetDialFrequencyMhzAsync` added to `IRadioConnection`

This is the minimal breaking change: one new method on the existing interface. All implementors (`SerialCatConnection`, `RigctldConnection`) and all test doubles must be updated. The method is a fire-and-forget set: it sends the command and returns; it does not re-read the rig to confirm the new frequency. The polling service will update `ICatState.DialFrequencyMHz` on the next poll cycle, closing the feedback loop naturally.

**Serial CAT command:** `FA<11-digit-Hz>;` — zero-pad the Hz integer to 11 digits (e.g. 14.074 MHz → `FA00014074000;`). Matches the VFO-A set command used by the CAT command set compatible with the rig.

**rigctld command:** `\set_freq <Hz>\n` — integer Hz as a string, newline-terminated. Matches the rigctld protocol.

**Alternative considered:** Separate `ITunable` interface with `SetDialFrequencyMhzAsync`. Rejected — the added indirection gives little benefit given that both `SerialCatConnection` and `RigctldConnection` already implement `IRadioConnection`; the tuning contract belongs on the same interface as the frequency read.

### D4 — `POST /api/v1/tune` as a unified tuning action endpoint

A single endpoint abstracts the two-branch logic (CAT on → command rig; CAT off → update config). The caller (browser) does not need to know the current CAT state. The handler checks `ICatState.Status` and dispatches accordingly. The response always returns `{ "effectiveFrequencyMHz": number }` so the caller can update the UI regardless of which path was taken.

When CAT is active, `ICatState.DialFrequencyMHz` is updated optimistically (before the next poll) so the status bar reflects the change immediately.

### D5 — `#dial-freq` element switches between `<span>` and `<select>` in place

Rather than maintaining two hidden elements, `main.js` replaces the `#dial-freq` element's rendering based on the current CAT status received from `cat_status` or `status` WebSocket events. When CAT transitions to Connected/Connecting, the span is swapped for a `<select>`; when it transitions to Disabled/Error, the `<select>` is swapped back for a span. The `id="dial-freq"` is reassigned to whichever element is active.

The frequency list is loaded once on page load via `GET /api/v1/frequencies`, filtered to the active protocol (FT8), and cached in `main.js`. The cached list is reused when re-rendering the `<select>`.

**Alternative considered:** Always render a `<select>`, disable it when CAT is inactive. Rejected — a disabled dropdown implies the user _could_ interact; a plain text display communicates the read-only state more clearly.

### D6 — Active protocol is a constant in this change

`activeProtocol = "FT8"` is a module-level constant in `main.js` and `settings.js`. When multi-protocol support is added in a future change, this constant will become a reactive value. No abstraction overhead is introduced now.

### D7 — Frequencies tab participates in the existing unsaved-changes flow

The settings page already computes a JSON snapshot of all form values and compares it on every change (FR-040). The Frequencies tab will add the serialised frequency list to that snapshot. On Save, the frequencies are posted to `POST /api/v1/frequencies` as a separate request, issued in parallel with `POST /api/v1/config`. If either request fails, the error feedback is shown and the page remains dirty.

## Risks / Trade-offs

**[Risk] `IRadioConnection` is a breaking interface change** → All existing test doubles (in `OpenWSFZ.Rig.Tests`, `OpenWSFZ.Daemon.Tests`) must be updated to add a `SetDialFrequencyMhzAsync` stub. The task list makes this explicit. Failure to update mocks will produce compile errors, which is the desired early-warning signal.

**[Risk] Optimistic `ICatState.DialFrequencyMHz` update may momentarily disagree with the rig** → If the rig rejects the set command silently, the UI will show the requested frequency until the next poll corrects it. Acceptable for v0.x; a future change can add echo-back validation.

**[Risk] `frequencies.json` absent on CI runners** → CI clones the repo, so the committed `frequencies.json` will always be present. The default-write-on-absent code path is a safety net for operators who delete the file; it is tested by unit test rather than CI integration.

**[Risk] Save race: two concurrent POSTs (config + frequencies)** → The Save button is disabled while requests are in flight (existing pattern). Both requests are issued in parallel; the page remains dirty and shows an error if either fails. No transactional guarantee is needed — these are independent stores.

**[Trade-off] Separate `frequencies.json` means two files to manage** → Accepted. The operator clarity gained (a human-readable, shareable frequency list) outweighs the minor management overhead.

## Migration Plan

No migration needed. Existing `app.json` files are unaffected. The `frequencies.json` file is new; operators upgrading from an earlier version will have it created on first run with the default FT8 list. No schema version bump is required.

## Open Questions

None at this time. All design decisions are resolved above.
