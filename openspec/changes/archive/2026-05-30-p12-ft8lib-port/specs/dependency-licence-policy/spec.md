## ADDED Requirements

### Requirement: kgoba/ft8_lib submodule is enumerated and approved

The `kgoba/ft8_lib` library SHALL be added as a git submodule at `/native/ft8_lib/` and SHALL appear in the `LicenseInventoryCheck` licence inventory with SPDX identifier `MIT`. The tool's existing submodule enumeration requirement covers this automatically; this requirement records the explicit policy approval for the dependency.

#### Scenario: ft8_lib submodule is enumerated with MIT licence

- **WHEN** `LicenseInventoryCheck` is run against the solution root
- **THEN** the `licence-inventory.md` report SHALL include an entry for `native/ft8_lib` with licence `MIT` and the pinned commit SHA

#### Scenario: G5 gate remains green after ft8_lib is added

- **WHEN** `dotnet run --project tools/LicenseInventoryCheck` is run in CI after the submodule is added
- **THEN** the tool SHALL exit 0 (MIT is on the allow-list) and SHALL NOT produce any licence-policy warning for ft8_lib
