## ADDED Requirements

### Requirement: Callsign-position tokens are validated against a configurable shape grammar

The decoder SHALL replace the length-only oversized-callsign check (D9-R3) with a shape grammar
evaluated against each callsign-position token, loaded from `callsign-grammar.json`. A token
SHALL be accepted only if it is a hash reference, a short pseudo-callsign (≤ 3 characters, e.g.
`CQ`/`DE`/`QRZ`), or matches the configured shape: a prefix component (1–4 letters/digits
containing at least one letter), followed by a digit-run of 1 to the configured maximum
consecutive digits, followed by a suffix component of letters only (no digit may reappear once
the suffix begins), with a total base-callsign length not exceeding the configured maximum
(default 11, matching the Type 4 `pack58` charset width). A portable suffix (`/P`, `/M`, `/MM`,
`/QRP`, `/A`) or compound second callsign appended after `/` SHALL continue to be evaluated
separately from the base callsign, as today.

#### Scenario: Token with an over-length digit-run is rejected

- **WHEN** a callsign-position token has a contiguous run of digits longer than the configured
  maximum (e.g. a fictional token shaped like `3AG9672ATCH`, whose digit-run `9672` is 4 digits)
- **THEN** the decoder SHALL treat the containing message as implausible and SHALL NOT surface it
  in `ALL.TXT` or the UI

#### Scenario: Token exceeding the total base-callsign length ceiling is rejected

- **WHEN** a callsign-position token's base call (before any `/` suffix) exceeds the configured
  maximum total length (default 11 characters)
- **THEN** the decoder SHALL treat the containing message as implausible

#### Scenario: Genuine nonstandard/special-event callsign literal is accepted

- **WHEN** a callsign-position token is a literal (non-hash) nonstandard callsign of up to 11
  characters whose digit-run does not exceed the configured maximum and whose suffix contains no
  digits (e.g. a fictional Q-prefix literal shaped like `Q0ABCDEF`)
- **THEN** the decoder SHALL treat the token as shape-valid and SHALL NOT reject the containing
  message on this basis alone

#### Scenario: Hash-reference tokens remain exempt

- **WHEN** a callsign-position token begins with `<` (a hash reference, e.g. `<...>`)
- **THEN** the decoder SHALL treat it as shape-valid unconditionally, as it does today

#### Scenario: Short pseudo-callsigns remain exempt

- **WHEN** a callsign-position token is 3 characters or fewer (e.g. `CQ`, `DE`, `QRZ`)
- **THEN** the decoder SHALL treat it as shape-valid unconditionally, as it does today

#### Scenario: Portable-suffix tokens are split before shape evaluation

- **WHEN** a callsign-position token contains a `/` (e.g. `VK9ABC/QRP`)
- **THEN** the decoder SHALL evaluate the base callsign (before the `/`) against the shape
  grammar independently of the suffix, as today

---

### Requirement: Reserved/never-allocated prefix exclusion list, with an explicit synthetic-use carve-out

`callsign-grammar.json` SHALL carry a short list of prefix series ITU has never allocated for
station callsign use (reserved for other purposes) as an additional exclusion signal, and SHALL
carry an explicit carve-out entry marking the project's own synthetic-callsign convention
(NFR-021, the `Q`-prefix series) as shape-valid despite being drawn from an otherwise-reserved
series. This table SHALL NOT be used as a positive allow-list gating acceptance — a prefix's
absence from the table SHALL NOT, by itself, cause a token to be rejected.

#### Scenario: Synthetic Q-prefix callsign is accepted

- **WHEN** a callsign-position token's prefix falls within the `Q`-series synthetic carve-out
  (e.g. a fictional `Q1ABC`) and otherwise matches the shape grammar
- **THEN** the decoder SHALL treat the token as shape-valid

#### Scenario: Absence from the exclusion/allocation table does not cause rejection

- **WHEN** a callsign-position token matches the shape grammar but its prefix does not appear in
  `callsign-grammar.json` at all (neither excluded nor explicitly carved out)
- **THEN** the decoder SHALL still treat the token as shape-valid — the table is not a positive
  allow-list

#### Scenario: Token matching a reserved, never-allocated, non-carved-out prefix is rejected

- **WHEN** a callsign-position token's prefix matches an entry in the reserved/never-allocated
  exclusion list that carries no synthetic-use (or other) carve-out
- **THEN** the decoder SHALL treat the containing message as implausible

---

### Requirement: Callsign grammar configuration is loaded from `callsign-grammar.json`

The grammar rules SHALL be loaded from `callsign-grammar.json` at startup via
`ICallsignGrammarStore`, rather than hard-coded, so a future ITU reallocation or calibration
adjustment does not require a code change. The configurable rules SHALL include the digit-run
maximum, the total-length maximum, the reserved-prefix exclusion list, and the carve-out entries.

#### Scenario: Missing configuration file falls back to built-in safe defaults

- **WHEN** the daemon starts and `callsign-grammar.json` does not exist at the resolved path
- **THEN** the daemon SHALL create the file with built-in default values (digit-run maximum 3,
  total-length maximum 11, the `Q`-series synthetic carve-out present) and proceed without error,
  mirroring the `frequencies.json` first-run convention

#### Scenario: Malformed configuration file falls back to built-in safe defaults with a warning

- **WHEN** the daemon starts and `callsign-grammar.json` exists but fails to deserialise
- **THEN** the daemon SHALL log a Warning naming the parse failure, fall back to the built-in
  default grammar values, and start normally rather than crashing or disabling the guard entirely
