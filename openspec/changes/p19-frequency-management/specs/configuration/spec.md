## ADDED Requirements

### Requirement: IFrequencyStore DI registration and path resolution

The `IFrequencyStore` service SHALL be registered as a singleton in the DI container during daemon startup, alongside `IConfigStore`. The concrete `FrequencyStore` class SHALL be the registered implementation.

The resolved path for `frequencies.json` SHALL follow the same convention as `app.json`: by default, the file is located in the same directory as the daemon executable. An environment variable or CLI argument override for the data directory SHALL also apply to `frequencies.json` when present.

#### Scenario: IFrequencyStore is available to all services via DI

- **WHEN** the daemon starts and DI is configured
- **THEN** any service that depends on `IFrequencyStore` SHALL receive a resolved singleton instance before any web request is handled

#### Scenario: FrequencyStore path resolves to the executable directory by default

- **WHEN** no path override is configured
- **THEN** `FrequencyStore` SHALL look for `frequencies.json` in the same directory as the daemon executable

#### Scenario: FrequencyStore path uses the data-directory override when set

- **WHEN** the data-directory override (environment variable or CLI argument) is set to a custom path
- **THEN** `FrequencyStore` SHALL resolve `frequencies.json` within that directory, consistent with how `IConfigStore` resolves `app.json`

#### Scenario: Default frequencies.json is included in the default config created on first run

- **WHEN** the daemon creates default files on first run (both `app.json` and `frequencies.json` are absent)
- **THEN** both files SHALL be created: `app.json` with the standard default config values and `frequencies.json` with the 15-entry default FT8 frequency list
