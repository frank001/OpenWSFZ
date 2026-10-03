## ADDED Requirements

### Requirement: The interop SHALL provide a save and restore of the process-global decode state

The native library SHALL export functions that report the size of, save into, and restore from a **caller-supplied buffer** every process-global mutable value the native decode changes: the session callsign hash table, its reject counter, the hash announce clock, and the 12-bit-hash diagnostic counters and per-code arrays. Restoring SHALL return all of them to the values at the matching save. The buffer SHALL be supplied by the caller so that two saved images can be compared byte for byte. The pair SHALL change no decode output when it is not used. Adding the exports SHALL bump `FT8_SHIM_VERSION` and the managed interop's expected version.

#### Scenario: Round trip

- **WHEN** state is saved, a decode adds callsigns and moves the counters, and the state is restored
- **THEN** a second save produces an image byte-identical to the first, and a following decode of the same window produces the same results as it would have without the intervening decode

#### Scenario: Not used

- **WHEN** neither function is called
- **THEN** every decode is byte-identical to the previous shim's

#### Scenario: Restore after a fault

- **WHEN** the managed caller restores after a decode that raised an exception
- **THEN** the hash state equals the saved state

### Requirement: The saved image SHALL cover every mutable process-global the decode can write, and a test SHALL fail when it does not

A test SHALL enumerate the mutable file-scope variables in the native shim source that the decode path can write, and SHALL fail if any is missing from the saved image or if the image names one that no longer exists, so that adding a global to the shim without adding it to the image fails the build.

#### Scenario: A new global is added

- **WHEN** a mutable process-global the decode writes is added to the shim and not to the image
- **THEN** the completeness test fails
