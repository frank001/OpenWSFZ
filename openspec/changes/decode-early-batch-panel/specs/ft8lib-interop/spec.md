## ADDED Requirements

### Requirement: The interop SHALL provide a save and restore of the process-global decode state

The native library SHALL export a pair of functions that save and restore, as one unit, every process-global mutable value the native decode changes: the session callsign hash table, its reject counter, the hash announce clock, and the 12-bit-hash diagnostic counters and per-code arrays. Restoring SHALL return all of them to the values at the matching save. The pair SHALL NOT be nested, SHALL NOT allocate on the stack for the buffer, and SHALL change no decode output when it is not used. Adding the exports SHALL bump `FT8_SHIM_VERSION` and the managed interop's expected version.

#### Scenario: Round trip

- **WHEN** state is saved, a decode adds callsigns and moves the counters, and the state is restored
- **THEN** a following decode of the same window produces the same results as it would have without the intervening decode

#### Scenario: Not used

- **WHEN** neither function is called
- **THEN** every decode is byte-identical to the previous shim's

#### Scenario: Restore after a fault

- **WHEN** the managed caller restores after a decode that raised an exception
- **THEN** the hash state equals the saved state
