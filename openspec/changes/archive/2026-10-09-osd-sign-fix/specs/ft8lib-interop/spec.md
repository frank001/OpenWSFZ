## ADDED Requirements

### Requirement: The OSD fallback SHALL be given LLRs in its own sign convention, and its acceptance gate SHALL read the same array

Every native call to `osd_decode` SHALL pass an array in OSD's convention (positive = bit 0), produced from the belief-propagation
convention (positive = bit 1) by **one** shared helper writing into a buffer the call site owns. The OSD acceptance gate (the
corr/norm and `nhard` checks) SHALL read **that same buffer**, so that with the correction active it measures agreement with the true
channel hard decisions. No `osd_decode` caller SHALL exist outside this pattern. The gate's arithmetic SHALL be unchanged.

#### Scenario: A correct codeword is accepted

- **WHEN** an LLR vector for a known codeword has enough erased or sign-flipped entries that 50 iterations of belief propagation fail and depth-2 OSD succeeds, and the correction is active
- **THEN** the decode returns the known payload, the accepted decode's `nhard` is no greater than the number of injected flips, and its corr/norm exceeds `OSD_CORR_THRESHOLD`

#### Scenario: The gate cannot be left on the old array

- **WHEN** a source scan of the native decode file lists every `osd_decode(` call
- **THEN** each caller other than the definition is preceded by the helper on the same array that the gate then reads, and a caller outside the pattern fails the test

#### Scenario: The all-ones word

- **WHEN** the OSD result is the all-ones word
- **THEN** it is not accepted as a codeword

### Requirement: A harness-only process-global switch SHALL restore the previous OSD behaviour bit-for-bit

The shim SHALL export `ft8_set_osd_sign_fix(int)` and `ft8_get_osd_sign_fix(void)`. The setting is process-global, read at each OSD call, defaults to **1** (corrected), and is **not** reachable from configuration, the UI or the API. With the setting at 0 the native calls, outputs and their order SHALL equal those of the shim immediately before this change. The managed interop SHALL expose both functions (`Ft8LibInterop`, `IFt8NativeInterop`, `Ft8Decoder`) and the test double SHALL record them. Adding the exports SHALL bump `FT8_SHIM_VERSION` and the managed interop's expected version.

#### Scenario: Switch at 0

- **WHEN** the setting is 0 and a recorded set of cycles is decoded
- **THEN** every decode result, the per-cycle multiset and the text lines equal those of the previous shim

#### Scenario: Switch at 1 on the sign test vector

- **WHEN** the known-codeword vector of the previous requirement is decoded with the setting at 0
- **THEN** no decode is produced, and with the setting at 1 the payload is produced

#### Scenario: Read-back

- **WHEN** the setting is changed through the managed interop
- **THEN** `ft8_get_osd_sign_fix` returns the value just set

#### Scenario: Not configurable by an operator

- **WHEN** the configuration file, the settings page and the HTTP API are searched for the setting
- **THEN** none of them can read or write it
