# native-build-provenance Specification

## Purpose

Specifies the vendored `ft8_lib` native source tree, its recorded provenance, the rebuild
process that compiles every linked translation unit from that tracked source with no
pre-built objects, and the mechanical acceptance gates (behavioural equality against the
pinned baseline, and build-to-build reproducibility) that make the shipped `libft8` binary
independently reconstructible.

## Requirements

### Requirement: Vendored native source tree with recorded provenance

The repository SHALL contain a vendored copy, under version control, of every `ft8_lib` source and header file actually required to link `libft8` — at minimum `ft8/{constants,crc,decode,encode,ldpc,message,text}.h`, `ft8/{constants,crc,encode,ldpc,message,text}.c`, `ft8/debug.h`, `common/{monitor,common}.h`, `fft/{kiss_fft,kiss_fftr}.{c,h}`, `fft/_kiss_fft_guts.h`, and the upstream `LICENSE`. `ft4_ft8_public/` SHALL NOT be vendored (no licence header of any kind; no build step compiles it). The vendored tree SHALL record, mechanically rather than only in prose: the upstream remote URL, the upstream HEAD commit SHA, and the output of a content-identity check (`git diff --ignore-cr-at-eol` against that HEAD) establishing the vendored copy matches the upstream tree modulo line-ending differences only.

#### Scenario: Vendored tree excludes the Fortran-only directory

- **WHEN** the vendored native source tree is inspected after this change lands
- **THEN** no `ft4_ft8_public/` path SHALL exist anywhere under the vendored directory

#### Scenario: Provenance is recorded mechanically

- **WHEN** a reviewer inspects the vendoring commit or its accompanying provenance record
- **THEN** the upstream remote URL, the HEAD SHA (`d18ed84f058290b36652f50db41875f2cafbaa4c` at the
  time of this change), and the `git diff --ignore-cr-at-eol` command and its (expected empty)
  output SHALL all be present and verifiable without re-deriving them

### Requirement: Native build compiles every linked translation unit from vendored source

`native/ft8_lib_build/rebuild_shim.bat` (or its successor) SHALL compile all eleven translation units linked into `libft8` — `constants`, `crc`, `decode`, `encode`, `ldpc`, `message`, `text`, `monitor`, `kiss_fft`, `kiss_fftr`, `ft8_shim` — from tracked source on every invocation, starting from an empty `obj/` output directory. No pre-built `.obj` file SHALL be linked into the resulting DLL. The exported symbol list SHALL remain unchanged by this requirement.

#### Scenario: Clean build links zero pre-built objects

- **WHEN** the rebuild script is run against an empty `obj/` directory
- **THEN** every `.obj` file passed to the final `link` step SHALL have been produced by a `cl`
  compile step earlier in the same script invocation, and none SHALL pre-date that invocation

#### Scenario: Export list is unchanged

- **WHEN** the rebuilt DLL is inspected with a symbol-export tool
- **THEN** it SHALL export exactly the same eleven symbols as the pre-change build
  (`ft8_lib_version_check`, `ft8_decode_all`, `ft8_get_last_pass_counts`, `ft8_get_max_passes`,
  `ft8_get_last_noise_floor_db`, `ft8_encode_message`, `ft8_get_last_candidate_counts`,
  `ft8_get_last_llr_stats`, `ft8_set_ap_bits`, `ft8_set_decode_params`,
  `ft8_get_hash_table_reject_count`)

### Requirement: Behavioural equality against the pinned baseline

A DLL built from the vendored source tree SHALL produce **byte-identical decode output** — same decodes, same order, same `freq_hz`/`dt`/SNR fields, on every cycle — as the currently-shipped production DLL, when both are replayed against the same ≥200-contiguous-cycle corpus subset with identical parameters and ordering. This comparison SHALL be a mechanical diff of serialised replay output; a summary count or an eyeballed comparison does NOT satisfy this requirement. Behavioural equality is the contract — the DLL *files* themselves are NOT required to be byte-identical (the MSVC toolchain embeds a build timestamp that makes bitwise reproducibility unattainable independent of source correctness).

#### Scenario: Vendored build reproduces the pinned baseline

- **WHEN** the vendored-source DLL and the pinned production DLL are both replayed against the same
  ≥200-cycle corpus subset, same parameters, same order
- **THEN** a mechanical diff of the two runs' serialised decode output SHALL show zero differences

#### Scenario: A behavioural difference blocks the change and is reported, not silently patched

- **WHEN** the mechanical diff between the vendored-source build and the pinned baseline shows any
  difference at all
- **THEN** the build SHALL be treated as failing this requirement, the specific decodes that differ
  SHALL be reported before any diagnosis is attempted, and no vendored source file SHALL be edited
  in an attempt to force the diff to zero

### Requirement: Build reproducibility across independent clean builds

Two independent clean builds (each starting from an empty `obj/` directory and, if performed on separate checkouts, a fresh checkout of the vendored tree) SHALL produce DLLs whose **decode output** is byte-identical to each other over the same corpus subset used for the baseline comparison. The DLL *files* are NOT required to be bitwise identical to each other.

#### Scenario: Two clean builds agree on decode output

- **WHEN** the native build is run twice, independently, each from an empty `obj/` directory
- **THEN** replaying both resulting DLLs against the same corpus subset and mechanically diffing
  the serialised output SHALL show zero differences
