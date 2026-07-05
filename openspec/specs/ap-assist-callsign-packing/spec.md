# ap-assist-callsign-packing Specification

## Purpose

Specifies `Ft8CallsignPacker`'s extended encoding support for AP (a priori) decode-assist:
packing the special `CQ`/`DE`/`QRZ` tokens (including the numeral-suffixed `CQ nnn` form) and
packing nonstandard/compound callsigns via the published `ihashcall` hash algorithm, both into
the same 4-byte MSB-first `c28` byte layout used by the existing standard-basecall path. Before
this capability, any token or callsign that did not fit the standard-basecall pattern caused
`Pack28` to return an empty array, which callers treated as an unambiguous "disable AP for this
input" signal — meaning AP decode-assist was disabled whenever either side of a QSO used a
nonstandard or compound callsign, or a directed/numbered CQ was involved. This capability narrows
that empty-array signal to genuinely unsupported forms only (directed CQ forms with a non-numeric
suffix, and malformed input), so AP decode-assist remains active for the common nonstandard-
callsign and special-token cases.

## Requirements

### Requirement: Pack special CQ/DE/QRZ tokens for AP decode-assist

`Ft8CallsignPacker` SHALL encode the special tokens `"CQ"`, `"DE"`, `"QRZ"`, and a 3-digit
numeral-suffixed CQ (`"CQ nnn"`, `nnn` = `000`–`999`) into their correct 28-bit `c28`
representation (special-token sub-range, `n28 < NTOKENS`), returning the same 4-byte MSB-first
byte layout as the existing standard-basecall path, so these tokens no longer cause AP
decode-assist to be disabled.

#### Scenario: Plain CQ token packs successfully

- **WHEN** `Ft8CallsignPacker.Pack28("CQ")` is called
- **THEN** it SHALL return a non-empty 4-byte array whose decoded `n28` value is `2`

#### Scenario: DE token packs successfully

- **WHEN** `Ft8CallsignPacker.Pack28("DE")` is called
- **THEN** it SHALL return a non-empty 4-byte array whose decoded `n28` value is `0`

#### Scenario: QRZ token packs successfully

- **WHEN** `Ft8CallsignPacker.Pack28("QRZ")` is called
- **THEN** it SHALL return a non-empty 4-byte array whose decoded `n28` value is `1`

#### Scenario: CQ nnn numeral suffix packs successfully

- **WHEN** `Ft8CallsignPacker.Pack28("CQ 123")` is called
- **THEN** it SHALL return a non-empty 4-byte array whose decoded `n28` value is `3 + 123 = 126`

### Requirement: Pack nonstandard/compound callsigns via ihashcall for AP decode-assist

`Ft8CallsignPacker` SHALL encode any nonstandard or compound callsign (a callsign string that
does not match either standard-basecall normalisation pattern, 3–11 characters after any `/R` or
`/P` suffix is accounted for) into the 22-bit hashed-callsign `c28` sub-range
(`NTOKENS ≤ n28 < NTOKENS + MAX22`) using the published `ihashcall` algorithm, returning the same
4-byte MSB-first byte layout as the existing standard-basecall path, so nonstandard callsigns no
longer cause AP decode-assist to be disabled.

#### Scenario: Nonstandard callsign packs via hash instead of returning empty

- **WHEN** `Ft8CallsignPacker.Pack28("PJ4/K1ABC")` is called (an 11-character compound callsign
  that does not fit either standard-basecall pattern)
- **THEN** it SHALL return a non-empty 4-byte array whose decoded `n28` value equals
  `NTOKENS + ihashcall("PJ4/K1ABC", bits: 22)`, not an empty array

#### Scenario: Hash matches the published formula's known test vectors

- **WHEN** `Ft8CallsignPacker.Pack28` is called for a nonstandard callsign from the project's
  existing `ihashcall` known-vector test table (shared with the native shim's and
  `qa/rr-study/synth/packing.py`'s own test coverage)
- **THEN** the decoded `n28`'s hash component SHALL match the vector's expected hash value
  exactly

#### Scenario: Existing standard-basecall packing is unaffected

- **WHEN** `Ft8CallsignPacker.Pack28("PD2FZ")` is called (a standard 6-character-shaped
  callsign that already packs correctly today)
- **THEN** it SHALL return the same 4-byte array it returned before this capability was added
  (the standard-basecall path and its `n28` sub-range are unchanged)

### Requirement: Unsupported forms still return an empty array

`Ft8CallsignPacker.Pack28` SHALL continue to return an empty array for callsign forms it does
not (yet) support — directed CQ forms with a non-numeric 2–4 character suffix (e.g. `"CQ DX"`,
`"CQ POTA"`) and any string that is not a valid callsign, special token, or hash-encodable
nonstandard callsign — so callers can continue to treat an empty array as an unambiguous
"disable AP for this input" signal.

#### Scenario: Directed CQ with a non-numeric suffix is not yet supported

- **WHEN** `Ft8CallsignPacker.Pack28("CQ DX")` is called
- **THEN** it SHALL return an empty array (unchanged from current behaviour; tracked as a
  follow-up, see this change's tasks.md)

#### Scenario: Malformed input returns an empty array

- **WHEN** `Ft8CallsignPacker.Pack28` is called with an empty string, whitespace-only string, or
  a string longer than 11 characters after suffix stripping
- **THEN** it SHALL return an empty array
