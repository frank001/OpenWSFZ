# engagement-target-validation Specification

## Purpose

Gates decoded callsign tokens against a region-anchored callsign grammar check before they may
become a live TX-engagement target (manual engage, CQ auto-answer arming, responder matching),
catching implausible tokens (e.g. `6KER05BPPBQ`) that pass the deliberately permissive
callsign-structure-validation decode-acceptance check but do not fit the shape a matched
region-store prefix implies. Inactive while only compiled-in seed region data is loaded.

## Requirements

### Requirement: Engagement targets are validated against a region-anchored callsign grammar check

The system SHALL validate a decoded callsign token using `ICallsignRegionStore` and
`ICallsignGrammarStore` before it may be armed as a live TX-engagement target — manual
`POST /api/v1/tx/engage-decode`, automated CQ auto-answer arming, or automated responder
matching — distinct from and in addition to the existing, unmodified
`callsign-structure-validation` decode-acceptance check. This validation SHALL be active only
when `ICallsignRegionStore` holds data loaded from an operator-triggered refresh (not the
compiled-in seed table); with only seed data loaded, every token SHALL be treated as valid for
engagement purposes, identical to today's behaviour.

When active, the system SHALL find the longest matching region-store prefix for the token's base
callsign (portable suffix stripped, as `callsign-structure-validation` already does). A token with
no matching prefix at all SHALL be treated as valid — an unlisted prefix SHALL NOT, by itself,
cause a rejection. A token whose matched prefix IS found SHALL be treated as valid only if the
remainder of the base callsign immediately following the matched prefix fits the shape applicable
to that prefix, using the exact `DigitRunMax`/`SuffixLengthMax` values currently configured in
`ICallsignGrammarStore` (no separately hardcoded copy of these limits):
- If the matched prefix itself contains no digit, the remainder SHALL consist of a digit-run of 1
  to `DigitRunMax` digits followed by 0 to `SuffixLengthMax` letters, consuming the entire
  remainder.
- If the matched prefix itself already contains a digit, the remainder SHALL be treated as valid if
  it fits **either** of two shapes, and invalid only if it fits neither:
  - 0 to `SuffixLengthMax` letters only, with no digit expected — for region-store data that
    commonly breaks a single DXCC entity down by call-district, baking the mandatory call-area
    digit into the matched prefix itself (e.g. `"EC5"` for a specific Spanish call district, so the
    remainder no longer owns a digit to contribute); or
  - a digit-run of 1 to `DigitRunMax` digits followed by 0 to `SuffixLengthMax` letters, consuming
    the entire remainder — for a DXCC entity whose region-store prefix is itself digit-leading as
    part of the *entity identifier* rather than the call-district marker, with the callsign's real
    mandatory call-area digit still to come after the matched prefix (e.g. `"3A"` for Monaco;
    genuine Monaco calls are always `3A2...`, so the remainder `"2XYZ"` still owns the real
    call-area digit `'2'`).

#### Scenario: Matched prefix's remainder fits the grammar — engagement allowed

- **WHEN** comprehensive region data is loaded, a candidate token's longest matched prefix contains
  no digit, and the remainder immediately following it is a digit-run within `DigitRunMax` and then
  letters only within `SuffixLengthMax`, consuming the whole remainder
- **THEN** the token SHALL be treated as valid for engagement

#### Scenario: Matched prefix already contains the call-area digit — remainder is suffix-only

- **WHEN** comprehensive region data is loaded and a candidate token's longest matched prefix
  already contains a digit (e.g. `"EC5"`, a genuine Spanish call-district entry), and the remainder
  immediately following it consists entirely of letters within `SuffixLengthMax` (e.g. `"EC5M"`,
  whose remainder `"M"` is a single letter)
- **THEN** the token SHALL be treated as valid for engagement — the remainder SHALL NOT be required
  to also start with a digit-run, since the matched prefix already supplied the mandatory digit

#### Scenario: Matched prefix's digit is part of the entity identifier only — remainder still supplies the real call-area digit

- **WHEN** comprehensive region data is loaded and a candidate token's longest matched prefix
  already contains a digit that is part of the DXCC entity identifier rather than the call-district
  marker (e.g. `"3A"`, Monaco's genuine region-store entry), and the remainder immediately following
  it fits a digit-run of 1 to `DigitRunMax` digits followed by 0 to `SuffixLengthMax` letters (e.g.
  `"3A2XYZ"`, whose remainder `"2XYZ"` is digit-run `"2"` plus suffix `"XYZ"`)
- **THEN** the token SHALL be treated as valid for engagement — a digit inside the matched prefix
  SHALL NOT, by itself, force the remainder into the letters-only-suffix shape; both shapes SHALL be
  tried, and the token rejected only if the remainder fits neither

#### Scenario: Matched prefix's remainder does not fit the grammar — engagement rejected

- **WHEN** comprehensive region data is loaded and a candidate token's longest matched prefix is
  real (e.g. `"6K"`, a genuine Republic-of-Korea entry) but the remainder immediately following it
  does not fit the shape applicable to that prefix (e.g. `"6KER05BPPBQ"`, whose 9-character
  remainder `"ER05BPPBQ"` is neither a valid digit-run+suffix nor, since the matched prefix `"6K"`
  itself contains a digit, a valid letters-only suffix within `SuffixLengthMax`)
- **THEN** the token SHALL be treated as invalid for engagement

#### Scenario: No prefix matches at all — engagement allowed

- **WHEN** comprehensive region data is loaded and a candidate token's base callsign matches no
  entry in the region store at any prefix length
- **THEN** the token SHALL be treated as valid for engagement — absence from the table SHALL NOT,
  by itself, cause a rejection

#### Scenario: Only seed region data is loaded — validation is inactive

- **WHEN** the daemon has not had an operator-triggered region-data refresh, so
  `ICallsignRegionStore` holds only the compiled-in seed table
- **THEN** every candidate token SHALL be treated as valid for engagement, identical to the
  system's behaviour before this capability existed

#### Scenario: Seed-vs-real provenance persists correctly across a daemon restart

- **WHEN** a daemon has never had an operator-triggered region-data refresh, only ever written the
  compiled-in seed table to `callsign-regions.json` on its first-ever launch, and is then restarted
  one or more times with no operator action in between
- **THEN** `ICallsignRegionStore.IsSeedData` SHALL still report `true` on every subsequent launch —
  the mere existence of the on-disk file (written by the daemon's own prior seed-write) SHALL NOT,
  by itself, be treated as evidence that real operator-supplied data was ever loaded

#### Scenario: A genuine operator refresh persists correctly across a daemon restart

- **WHEN** an operator-triggered region-data refresh has succeeded at least once, and the daemon is
  then restarted
- **THEN** `ICallsignRegionStore.IsSeedData` SHALL report `false` on the subsequent launch

#### Scenario: Portable-suffix tokens are validated on the base callsign only

- **WHEN** a candidate token contains a `/` portable suffix (e.g. `VK9ABC/QRP`)
- **THEN** the region-anchored grammar check SHALL be evaluated against the base callsign before
  the `/`, independently of the suffix, consistent with `callsign-structure-validation`'s existing
  portable-suffix handling

### Requirement: Automated engagement paths hard-skip a rejected candidate

`QsoAnswererService`'s CQ auto-answer arming and `QsoCallerService`'s responder matching SHALL NOT
arm a TX target, SHALL NOT transmit to it, and SHALL NOT arm AP-decode constraints for it, when the
candidate is rejected by the region-anchored grammar check. No operator confirmation or override
mechanism SHALL exist on these paths.

#### Scenario: Auto-answer arming skips a rejected CQ candidate

- **WHEN** `QsoAnswererService` is scanning decoded CQs for an auto-answer candidate and a candidate
  callsign is rejected by the region-anchored grammar check
- **THEN** the service SHALL NOT arm that candidate as a pending target, SHALL log a skip, and SHALL
  continue evaluating other candidates as usual

#### Scenario: Responder matching skips a rejected reply

- **WHEN** `QsoCallerService` is matching an incoming reply to an active CQ and the responder's
  callsign is rejected by the region-anchored grammar check
- **THEN** the service SHALL NOT treat the reply as a valid responder and SHALL NOT arm it as the
  active QSO partner

### Requirement: Manual engagement rejection is a soft block with an explicit operator override

`POST /api/v1/tx/engage-decode` SHALL reject a request whose target callsign fails the
region-anchored grammar check by returning an error response identifying the reason and indicating
that confirmation is required, rather than silently proceeding or silently failing. A repeat request
for the same target that explicitly carries operator confirmation SHALL proceed and arm the target
despite the earlier rejection.

#### Scenario: First request against a rejected target requires confirmation

- **WHEN** an operator issues `POST /api/v1/tx/engage-decode` for a target callsign rejected by the
  region-anchored grammar check, without confirmation
- **THEN** the endpoint SHALL respond with an error indicating the target requires confirmation and
  SHALL NOT arm the target or transmit

#### Scenario: A rejected, unconfirmed request leaves a prior in-progress QSO completely untouched

- **WHEN** an operator issues `POST /api/v1/tx/engage-decode` for a target callsign rejected by the
  region-anchored grammar check, without confirmation, while a different QSO is already in progress
- **THEN** the endpoint SHALL respond with the confirmation-required error and SHALL NOT abort,
  modify the state of, or otherwise disturb the in-progress QSO — the rejection SHALL be evaluated,
  and MAY be returned, before any abort of the existing QSO is attempted

#### Scenario: Confirmed request proceeds despite rejection

- **WHEN** an operator re-issues `POST /api/v1/tx/engage-decode` for the same target callsign with
  explicit confirmation
- **THEN** the endpoint SHALL arm the target and proceed exactly as it would for a token that passed
  the region-anchored grammar check

### Requirement: Decode acceptance and display remain unaffected by this capability

This capability SHALL NOT alter `callsign-structure-validation`'s decode-acceptance outcome,
`ALL.TXT` contents, decode-panel visibility, region/worked-before display, or any other behaviour
governed by the `callsign-structure-validation` or `region-lookup` capabilities. A token rejected
for engagement purposes SHALL still be decoded, logged to `ALL.TXT`, and displayed in the decode
panel exactly as it would be without this capability.

#### Scenario: A rejected-for-engagement token is still fully visible

- **WHEN** a decoded token is rejected by the region-anchored grammar check for engagement purposes
- **THEN** the containing decode SHALL still appear in `ALL.TXT` and the decode panel, with its
  advisory region/worked-before information unchanged, exactly as it would if this capability did
  not exist
