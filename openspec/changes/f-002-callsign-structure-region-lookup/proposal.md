## Why

D-011 (`dev-tasks/2026-07-03-d-011-nonstandard-callsign-fp-guard.md`) raised
`Ft8Decoder.IsCallsignOversized`'s length ceiling from 6 to 11 characters so genuine Type 4
nonstandard-callsign literals (`f-001-hashed-callsign-resolution`) stop being silently discarded.
That guard is **length-only** — it has no notion of callsign *shape*. A token such as the
fictional `3AG9672ATCH` (11 chars, no `/`) is accepted as "plausible" even though it cannot be a
real amateur-radio callsign under any administration's allocation: ITU Radio Regulations Article
19 requires a callsign's mandatory single call-area digit to be followed only by 1–3 suffix
letters, and this shape has digits reappearing after the suffix begins — a structurally
impossible callsign regardless of which country's prefix block it claims. D-011's own QA notes
(§6) flagged this exact residual risk and recommended gating the relaxation on message *shape*
rather than length alone; this change is that follow-up, prompted by a live decode matching the
predicted failure mode.

Separately: once a callsign's prefix can be parsed and validated against a real allocation table,
the country/administration and continent it belongs to falls out for free. This is useful bycatch
for the operator (surfaced in the GUI) and needs its own accommodation for the project's synthetic
Q-prefix test callsigns (NFR-021), which are deliberately drawn from an ITU-unallocated block and
must not be misattributed to a real entity or flagged as invalid.

## What Changes

- Replace the length-only D9-R3 oversized-callsign guard in `Ft8Decoder.IsCallsignOversized` with
  a structural grammar check derived from ITU Radio Regulations Article 19 (prefix component,
  mandatory call-area digit, suffix component, portable-suffix forms `/P`, `/M`, `/MM`, `/QRP`
  etc.), combined with a lookup against the ITU Appendix 42 "Table of Allocation of International
  Call Sign Series" (prefix block → administration). A token must satisfy both the structural
  grammar **and** fall inside an allocated (or explicitly reserved-for-synthetic-use, e.g.
  Q-prefix) block to pass. Both rule sets are loaded from a new JSON configuration file,
  `config/callsign-grammar.json`, so future ITU reallocations don't require a code change.
- Add a second, independent JSON configuration file, `config/callsign-regions.json`, carrying
  richer DXCC-style data (prefix → entity/country name, continent, CQ zone, ITU zone) in the
  well-known ham-radio "country file" convention. This file is **advisory only** — a lookup miss
  degrades to an "Unknown" region label and never affects accept/reject decisions. It carries its
  own dedicated entry mapping the project's synthetic Q-prefix convention to a distinct
  `"Synthetic (R&R Study)"` region, so synthetic test traffic is never confused with a real
  ITU-allocated entity.
- Surface the region lookup in the decode table GUI as a new column/badge on each decode row
  (e.g. `EU — Monaco`, `Synthetic (R&R Study)`), sourced from `callsign-regions.json` via a new
  REST-exposed lookup.
- Add two new config store services (mirroring the existing `IFrequencyStore`/`frequencies.json`
  pattern: DI-registered singleton, data-directory-override path resolution, default file created
  on first run) for the two new JSON files.

## Capabilities

### New Capabilities
- `callsign-structure-validation`: ITU Article 19 structural grammar plus Appendix 42 allocated-
  block gate, replacing the length-only D9-R3 check; JSON-configurable via
  `config/callsign-grammar.json`.
- `region-lookup`: advisory prefix → continent/country region lookup for GUI display, JSON-
  configurable via `config/callsign-regions.json`, including the dedicated synthetic-callsign
  region.

### Modified Capabilities
- `configuration`: adds `ICallsignGrammarStore`/`callsign-grammar.json` and
  `ICallsignRegionStore`/`callsign-regions.json` config-file schemas, DI registration, and path
  resolution, following the existing `IFrequencyStore` precedent.
- `web-frontend`: decode table gains a region column/badge populated from the new region-lookup
  REST endpoint.

## Impact

- **Managed decoder**: `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — `IsCallsignOversized` (D9-R3) is
  replaced/extended; `IsPlausibleMessage`'s call sites are unaffected in shape. Existing
  `D009FpFilterTests` and `D011NonstandardCallsignFpGuardTests` must continue to pass unmodified
  (both are regression fences for prior defects this change must not reopen).
- **Configuration**: two new JSON files and store services, following `frequencies.json`/
  `IFrequencyStore` (`openspec/specs/configuration/spec.md`).
- **Web/API**: `src/OpenWSFZ.Web/WebApp.cs` (new lookup endpoint or extension of the existing
  decode-result payload), `web/js/main.js` / `web/js/api.js` (decode table rendering).
- **Testing**: new managed-layer unit tests for the grammar gate (including the exact
  `3AG9672ATCH`-shaped failure mode, using a fictional placeholder), region-lookup tests
  (including the synthetic Q-prefix case), and a mandatory re-run of the S5 false-positive-rate
  baseline (`qa/rr-study/scenarios/s5-noise-wide.json`) to confirm no regression versus the
  current 5.83%/120 figure (shim `f1e76d4`) — ideally an improvement, since shape-invalid noise
  of exactly this kind should now be rejected.
- **Non-goals**: no attempt to validate national sub-allocations beyond the ITU block level (e.g.
  FCC-internal US call-district/vanity rules); an unmatched prefix in either JSON table degrades
  gracefully (grammar gate: reject only on structural grounds, not on table-coverage gaps beyond
  the allocated-block check; region table: "Unknown" label) rather than becoming a functional
  regression on day one of a necessarily incomplete table.
