## ADDED Requirements

### Requirement: Test identity matches active mechanism

A smoke-test fixture that exercises the two-pass spectrogram-domain decode path SHALL identify
itself as such in all user-visible strings: the class XML doc comment, the `[Fact]` DisplayName,
and any assertion failure messages. No visible string SHALL reference a diagnostic mechanism
(PCM-domain SIC, H3b, shim 20260009) that is no longer present in the active binary.

#### Scenario: Test DisplayName reflects active shim mechanism

- **WHEN** the test runner lists the `[Fact]` by DisplayName
- **THEN** the displayed name SHALL NOT contain the strings "H3b", "20260009", or "GFSK quadrature SIC"

#### Scenario: Assertion failure message reflects active shim mechanism

- **WHEN** the smoke-test assertion fails and xUnit renders the failure message
- **THEN** the failure message SHALL NOT describe the failure as a regression in "the GFSK
  quadrature SIC path (shim 20260009)"

### Requirement: Decoder class version history is complete

The `Ft8Decoder` class XML doc SHALL contain a version history entry for every committed
`FT8_SHIM_VERSION` value. No version SHALL be absent from the history regardless of whether
it was ultimately accepted, rejected, or reverted.

#### Scenario: All shim versions up to and including 20260010 are documented

- **WHEN** the `Ft8Decoder.cs` class doc comment is read
- **THEN** entries for 20260007, 20260008, 20260009, and 20260010 SHALL all be present, each
  noting the change name and outcome (REVERTED or REJECTED where applicable)
