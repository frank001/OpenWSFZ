## ADDED Requirements

### Requirement: ICallsignGrammarStore DI registration and path resolution

The `ICallsignGrammarStore` service SHALL be registered as a singleton in the DI container during
daemon startup, alongside `IConfigStore` and `IFrequencyStore`. The concrete
`CallsignGrammarStore` class SHALL be the registered implementation.

The resolved path for `callsign-grammar.json` SHALL follow the same convention as
`frequencies.json`: by default, the file is located in the same directory as the daemon
executable. The data-directory override (environment variable or CLI argument) SHALL also apply
to `callsign-grammar.json` when present.

#### Scenario: ICallsignGrammarStore is available to all services via DI

- **WHEN** the daemon starts and DI is configured
- **THEN** any service that depends on `ICallsignGrammarStore` SHALL receive a resolved singleton
  instance before any web request is handled

#### Scenario: CallsignGrammarStore path resolves to the executable directory by default

- **WHEN** no path override is configured
- **THEN** `CallsignGrammarStore` SHALL look for `callsign-grammar.json` in the same directory as
  the daemon executable

#### Scenario: CallsignGrammarStore path uses the data-directory override when set

- **WHEN** the data-directory override is set to a custom path
- **THEN** `CallsignGrammarStore` SHALL resolve `callsign-grammar.json` within that directory

#### Scenario: Default callsign-grammar.json is included in the default files created on first run

- **WHEN** the daemon creates default files on first run and `callsign-grammar.json` is absent
- **THEN** the file SHALL be created with built-in default grammar values (digit-run maximum 3,
  total-length maximum 11, the `Q`-series synthetic carve-out present)

---

### Requirement: ICallsignRegionStore DI registration and path resolution

The `ICallsignRegionStore` service SHALL be registered as a singleton in the DI container during
daemon startup, alongside `ICallsignGrammarStore`. The concrete `CallsignRegionStore` class SHALL
be the registered implementation, following the same path-resolution convention (executable
directory by default, data-directory override when set).

#### Scenario: ICallsignRegionStore is available to all services via DI

- **WHEN** the daemon starts and DI is configured
- **THEN** any service that depends on `ICallsignRegionStore` SHALL receive a resolved singleton
  instance before any web request is handled

#### Scenario: Default callsign-regions.json is included in the default files created on first run

- **WHEN** the daemon creates default files on first run and `callsign-regions.json` is absent
- **THEN** the file SHALL be created with its seed region data, including the mandatory
  `"Synthetic (R&R Study)"` entry for the `Q`-prefix series
