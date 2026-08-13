## MODIFIED Requirements

### Requirement: ft8_lib native dependency is vendored and approved

The `ft8_lib` library (the `frank001/ft8_lib` fork of upstream `kgoba/ft8_lib`, `msvc-compat` branch) SHALL be integrated by **vendoring** the source files actually required to link `libft8` into version control under `native/ft8_lib_vendor/`, preserving the upstream `LICENSE` verbatim (see the `native-build-provenance` capability for the vendored file list and provenance requirements). It SHALL NOT be integrated as a git submodule. ⚠️ **Correction to the prior version of this requirement:** it previously stated `ft8_lib` "SHALL be added as a git submodule at `/native/ft8_lib/`" — that was never implemented (`.gitmodules` is empty, `git submodule status` returns nothing), and this delta corrects the requirement to match the vendoring approach actually taken, which is also how this codebase already handles the two MSVC-VLA-patched files (`decode.c`, `monitor.c`) under `native/ft8_lib_build/patched/`. `LicenseInventoryCheck`'s `SubmoduleEnumerator` walks every directory under `/native/` and records an entry for any directory containing a recognised `LICENSE`/`LICENCE` file when `.gitmodules` declares no `native/*` submodules (the current state), so it SHALL opportunistically pick up `native/ft8_lib_vendor/`'s vendored `LICENSE` without further tool changes; this CI-facing enumeration is a **separate** obligation from, and does not substitute for, the shipped `THIRD-PARTY-NOTICES.md` this change adds below — the inventory report is a build artefact for policy enforcement, the notices file is what travels with the distribution.

#### Scenario: Vendored ft8_lib is enumerated with MIT licence

- **WHEN** `LicenseInventoryCheck` is run against the solution root after `native/ft8_lib_vendor/`
  has been vendored with its `LICENSE` file present
- **THEN** the `licence-inventory.md` report SHALL include an entry for `native/ft8_lib_vendor`
  with licence `MIT`

#### Scenario: No git submodule is required or expected

- **WHEN** `.gitmodules` is inspected after this change lands
- **THEN** it SHALL still contain no `native/ft8_lib` entry, and the absence of a submodule SHALL
  NOT be treated as a policy violation by any CI gate

#### Scenario: G5 gate remains green after ft8_lib is vendored

- **WHEN** `dotnet run --project tools/LicenseInventoryCheck` is run in CI after the vendored tree
  is committed
- **THEN** the tool SHALL exit 0 (MIT is on the allow-list) and SHALL NOT produce any licence-policy
  warning for the vendored `ft8_lib` files

## ADDED Requirements

### Requirement: Shipped third-party notices file

The repository SHALL contain `THIRD-PARTY-NOTICES.md` at its root, reproducing in full: the MIT licence text with Kārlis Goba's copyright notice (for `ft8_lib`, `ft8/` and `common/`), and the BSD-3-Clause licence text with Mark Borgerding's copyright notice (for KISS FFT, `fft/kiss_fft.c`/`kiss_fftr.c`/`_kiss_fft_guts.h`) — reproduced in full rather than referencing a `COPYING` file, since no such file exists in the vendored `fft/` directory despite the upstream header's "See COPYING file" comment. A scan of the vendored tree for the strings `GNU General Public`, `GPL`, and `Affero` SHALL find no hits other than the two known, Captain-ruled flagged-not-blocking WSJT-X-attribution comments in `ft8/constants.h` (lines 75 and 78, which credit WSJT-X as the historical source of two LDPC parity-table constants and are not themselves GPL-licensed text) — any other hit SHALL block this requirement from being satisfied.

#### Scenario: Notices file contains both required licence texts

- **WHEN** `THIRD-PARTY-NOTICES.md` is inspected after this change lands
- **THEN** it SHALL contain the full MIT licence text with Kārlis Goba's copyright, and the full
  BSD-3-Clause licence text with Mark Borgerding's copyright

#### Scenario: GPL/AGPL scan finds only the two expected, flagged hits

- **WHEN** the vendored tree is scanned for `GNU General Public`, `GPL`, and `Affero`
- **THEN** the only hits SHALL be the WSJT-X-attribution comments at `ft8/constants.h` lines 75 and
  78, and any other hit SHALL be treated as a licence-policy violation

#### Scenario: Fortran-only directory is absent

- **WHEN** the vendored tree is inspected
- **THEN** no `ft4_ft8_public/` path SHALL exist anywhere under it (no licence header of any kind;
  not needed by any build step)
