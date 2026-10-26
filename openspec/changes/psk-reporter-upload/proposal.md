**User-facing:** yes

## Why

Issue #262 (the Captain, 2026-10-24): with only OpenWSFZ feeding GridTracker2, nothing reaches PSK Reporter under the station's call; with WSJT-X's "Enable PSK Reporter Spotting" on, 58 reports appeared in two minutes on 40 m, credited to WSJT-X 2.7.0. OpenWSFZ has no PSK Reporter upload (`REQUIREMENTS.md` lists it as future work, and its transport there, "HTTPS / telnet", is wrong: the service takes UDP datagrams in a simplified IPFIX format).

The Captain decided on 2026-10-25 (Architect build spec `arch/psk-reporter-262`, §10): **D1** yes, as an opt-in; **D2** all decode batches 1 to 4 (the same stream GridTracker receives); **D3** a Settings checkbox plus an antenna field with the opt-in text; **D4** send the 8-field sender descriptor with SNR and iMD, with **iMD always 0** because OpenWSFZ does not measure it, and the 7-field one without `senderLocator` when the message carries no grid.

## What Changes

- A new `PskReporterService` (Daemon) turns the decoded stream into PSK Reporter datagrams and sends them over one IPv4 UDP socket to `report.pskreporter.info:4739` (the test listener `report.pskreporter.info:14739` selectable in the configuration file; corrected 2026-10-25, Architect A2.1: the name `pskreporter.info` is Cloudflare-fronted and cannot receive UDP). **Off by default and inert** until the operator opts in.
- A new **encoder**: a pure function from (session id, sequence, export time, receiver, sender records, templates-due) to the page's bytes. Clean-room: the only reference is the public protocol page and QA's hand-built fixtures; no WSJT-X source is read.
- A new **strict sender extractor** (token classification, no fallback to the addressee, no hashed senders, never the station's own call), separate from the region lookup's `ExtractPrimaryCallsignToken`.
- `DecodeBatch` carries the cycle's **dial frequency at capture** (a new nullable member), so reports are immune to the band alternation of issue #260 (which this change does not fix).
- A dedicated bounded channel from the decode pump, sized like the QSO queues (10 with the fallback on, 8 off), `DropOldest`.
- Dedup: 5 minutes per call, 60 minutes per (call, band). Cadence: one datagram per 5 minutes (full datagrams at once), templates in the first three datagrams and then hourly, sequence number counting sender records from 0.
- A `pskReporter` configuration block (`enabled`, `antennaInformation`, `host`, `port`) and a Settings-page checkbox and antenna field with the opt-in text. The configuration POST remains an overlay.
- Nothing is uploaded under the placeholder identity (empty or Q-prefix receiver call, empty locator).
- `REQUIREMENTS.md`: new requirements FR-088 to FR-094 (numbers to be confirmed against `origin/main` at the start), the integrations row corrected to "UDP / IPFIX, implemented, opt-in", the glossary line updated, and an NFR-021 note. `VERSION` bump (G9b). **No `native/` change, no shim bump.**

## Capabilities

### New Capabilities
- `psk-reporter-upload`: the opt-in upload of received stations to PSK Reporter: configuration, identity guard, wire format, cadence, sender extraction, source stream, dedup, failure isolation, counters, Settings control and privacy.

### Modified Capabilities
- (none; the `configuration` capability is not edited: the new block's schema and overlay behaviour are specified in `psk-reporter-upload` itself)

## Impact

`src/OpenWSFZ.Abstractions/` (a new `PskReporterConfig`, `AppConfig`), `src/OpenWSFZ.Daemon/DecodeBatch.cs`, `src/OpenWSFZ.Config/ConfigJsonContext.cs`, `src/OpenWSFZ.Web/` (`AppJsonContext.cs`, `ConfigOverlay.cs` with its `NonNullableSections` and the explicit section fallbacks in `Apply`, validation, `web/settings.html`, `web/js/settings.js`, the settings-payload shape fixture), `src/OpenWSFZ.Daemon/` (a new service, the pump's dependencies, `Program.cs` wiring), tests in `tests/OpenWSFZ.Daemon.Tests`, `Config.Tests`, `Web.Tests` and a Playwright acceptance for the Settings control, `REQUIREMENTS.md`, `VERSION`. Privacy (NFR-021): tests and fixtures use Q-prefix calls only; nothing is stored or logged beyond counts. **What leaves the machine when the operator opts in:** the callsigns and locators of stations received, with the station's own call and locator, to a public service: that is the feature, and it is why it is opt-in with the stated text. Live verification (L1 test listener, L2 production, L3 outside count) is QA's, on the Captain's go; merge needs his sign-off.
