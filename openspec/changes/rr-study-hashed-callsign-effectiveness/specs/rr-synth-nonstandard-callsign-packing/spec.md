## ADDED Requirements

### Requirement: Synth encoder packs Type 4 nonstandard-callsign announcements
The QA synth encoder (`qa/rr-study/synth/packing.py`) SHALL provide a function that packs a
Type 4 (`i3=4`) message announcing a nonstandard/compound callsign's full text, independently
implemented from the published FT8 protocol description (Franke/Somerville/Taylor, QEX 2020) and
NOT ported or transliterated from `ft8_lib`/`ft8_shim.c`, per the existing QA-synth attestation
convention.

#### Scenario: Type 4 announcement packs to a 77-bit payload
- **WHEN** the new Type 4 packing function is called with a nonstandard callsign of 7–11
  characters (e.g. a fictional `Q0ABCDEF`-shaped call)
- **THEN** it returns exactly 77 bits (MSB first), with `i3=4` encoded in the final 3 bits

#### Scenario: Unsupported callsign length raises ValueError
- **WHEN** the Type 4 packing function is called with a callsign longer than 11 characters
- **THEN** it raises `ValueError`

### Requirement: Synth encoder computes the 22-bit `ihashcall` hash
`packing.py` SHALL provide a function computing the 22-bit callsign hash using the published
`ihashcall` algorithm (mixed-radix encode over the 38-character alphabet, multiply by the
published 64-bit constant, keep the top 22 bits), independently implemented per the same
attestation convention as the Type 4 packer.

#### Scenario: Hash function is deterministic
- **WHEN** the hash function is called twice with the same callsign
- **THEN** both calls return the same 22-bit value

#### Scenario: Hash matches the value embedded by the native shim for the same callsign
- **WHEN** the synth's hash function and `f-001-hashed-callsign-resolution`'s native shim compute
  the hash for the same fictional nonstandard callsign (cross-checked via a shared, committed
  test vector — not by calling into the native shim from Python)
- **THEN** both produce the identical 22-bit value

### Requirement: Synth encoder packs a Type 1/2/3 message referencing a nonstandard-callsign hash
`packing.py`'s existing standard-message packer SHALL be extended so that, when a callsign
argument is recognised as nonstandard-shaped (not encodable as a standard 6-character basecall),
it packs the 22-bit hash (via the new `ihashcall` function) into the `c28` field's
hash sub-range instead of raising `NotImplementedError`.

#### Scenario: Standard-message packer accepts a nonstandard callsign via its hash
- **WHEN** `pack_message` is called with a message whose first or second field is a
  nonstandard-shaped callsign (e.g. `"Q1TST Q0ABCDEF JO33"`)
- **THEN** it returns a valid 77-bit payload with that field's `c28` value in the
  `NTOKENS ≤ n28 < NTOKENS + MAX22` hash sub-range, computed via the new `ihashcall` function

#### Scenario: Standard-shaped callsigns are unaffected
- **WHEN** `pack_message` is called with only standard 6-character-or-shorter callsigns
- **THEN** behaviour is unchanged from before this capability was added (existing
  `test_packing.py` coverage continues to pass unmodified)
