## ADDED Requirements

### Requirement: Diagnostic decoder-parameter table native export (shim 20260054)

The native shim SHALL export `ft8_get_decoder_params(Ft8ParamEntry* out, int capacity)`, which returns **every decoder parameter** as a table of entries `{ char name[48]; double value; double default_value; int32_t kind; int32_t reserved; }` (72 bytes, blittable), where `kind` is `0` for a compile-time constant and `1` for a runtime-settable value. The function SHALL return the **total** entry count and SHALL write `min(capacity, total)` entries; when `out` is `NULL` or `capacity <= 0` it SHALL write nothing and still return the total.

The table SHALL contain (a) every runtime-settable value: the `ft8_set_decode_params` triple and the three suppression-ramp values; (b) every `#define K_*` tuning constant that the decode path reads in `ft8_shim.c`; (c) the candidate passband limits; (d) the OSD depth (design decision D4, decided); and (e) every further **bare numeric tuning literal** on the decode path (in `ft8_shim.c` and the patched `ft8/*.c`) that the implementation hoists to a named constant under the D12 audit. **Any such literal that is not tabled SHALL instead be listed on the read-only page's note, either as a value derived from a named tabled constant (for example the 3.125 Hz sub-bin, which is `6.25 Hz / K_FREQ_OSR`) or as "Not included"; none SHALL be omitted silently, and none SHALL be excluded as a protocol constant unless it is one of the FT8 protocol constants (the 6.25 Hz tone spacing, 79 / 174 / 91, the Costas pattern, 8 tones and the 12 kHz sample rate).** For a **runtime** entry, `value` SHALL be the value the decoder would use **now** and `default_value` SHALL be the **compiled-in** default. For a **compile-time** entry, both SHALL equal the constant the decode path uses.

The values SHALL be read from the same macros or variables the decode path reads, so that a reported value cannot differ from the value in use. The export SHALL have **no managed binding beyond the read-only `IFt8NativeInterop` method** and SHALL NOT alter any decode output.

#### Scenario: The table reports what the native decoder is running with, not what the application configured

- **WHEN** `ft8_set_decode_params(10, 0.10f, 40)` has been called and `ft8_get_decoder_params` is then read
- **THEN** the entry named `osd_nhard_max` SHALL report `value == 40` and `default_value == 60`

#### Scenario: The table can be sized before it is filled

- **WHEN** `ft8_get_decoder_params(NULL, 0)` is called
- **THEN** it SHALL return the total entry count and SHALL write nothing

#### Scenario: A compile-time entry equals its constant

- **WHEN** the table is read
- **THEN** for every `#define K_*` that the decode path reads, an entry with that name SHALL exist and its `value` SHALL equal the constant

#### Scenario: Round-trip through the setters

- **WHEN** `ft8_set_decode_params(7, 0.15f, 50)` and `ft8_set_supp_params(-10.0f, 15.0f, 0.5f)` are called
- **THEN** the table SHALL report exactly those five values, and after the defaults are set again it SHALL report the defaults

#### Scenario: Reading the table does not change any decode output

- **WHEN** a fixed audio buffer is decoded before and after `ft8_get_decoder_params` is called
- **THEN** the decode results SHALL be byte-identical

---

### Requirement: Suppression-ramp runtime setter and getter (shim 20260054)

The native shim SHALL export `int ft8_set_supp_params(float snr_min_db, float snr_max_db, float side_weight)` and `int ft8_get_supp_params(float* out3)`. The setter SHALL store the three values in module-level state with **the same thread-safety contract as `ft8_set_decode_params`**, SHALL return `0` on success, and SHALL return `-1` **leaving all three values unchanged** if any argument is non-finite, if `snr_min_db >= snr_max_db`, or if `side_weight` lies outside `[0, 1]`. There SHALL be **no upper bound** on `snr_max_db` other than the two conditions above. The defaults SHALL be `-5.0f`, `15.0f` and `1.0f`. The getter SHALL write `{snr_min_db, snr_max_db, side_weight}` to `out3` and return `0`.

`suppress_candidate_tiles` SHALL use the runtime minimum and maximum for its ramp, SHALL apply `factor` to the tone bin (`d = 0`), and SHALL apply `factor_side = 1 − side_weight · (1 − factor)` to the side bins (`d = ±1`). **When `side_weight == 1.0f` the side bins SHALL use `factor` itself**, not the recomputed expression, because `1 − (1 − f)` is not bitwise equal to `f` in floating point.

The exports SHALL have **no managed binding and no `DllImport`** anywhere under `src/`: they are reachable only from test code and QA harnesses driving the native library directly.

#### Scenario: Valid values are stored and read back exactly

- **WHEN** `ft8_set_supp_params(-25.0f, 30.0f, 0.5f)` is called and `ft8_get_supp_params` is then read
- **THEN** the setter SHALL return `0` and the getter SHALL return exactly `-25.0f`, `30.0f`, `0.5f`

#### Scenario: Each invalid class is rejected and leaves the prior values unchanged

- **WHEN** the setter is called with a non-finite argument, or with `snr_min_db >= snr_max_db`, or with `side_weight < 0`, or with `side_weight > 1`
- **THEN** it SHALL return `-1` and `ft8_get_supp_params` SHALL still return the previously stored triple

#### Scenario: Defaults are byte-identical to the previous shim

- **WHEN** the setter has never been called, or has been called explicitly with `(-5.0f, 15.0f, 1.0f)`
- **THEN** decoding any audio buffer SHALL produce output byte-identical to shim `20260053`

---

### Requirement: Decode-path tuning values are named constants used at every site

The candidate passband limits SHALL be defined once as named constants (`K_PASSBAND_MIN_HZ = 140.0f`, `K_PASSBAND_MAX_HZ = 3075.0f`) and SHALL be used at **both** call sites that build a `monitor_config_t` (`ft8_decode_all` and `ft8_extract_llrs_at`). The change SHALL be arithmetic-identical: no decode output changes.

#### Scenario: One definition, two use sites

- **WHEN** the shim source is searched for the literals `140.0f` and `3075.0f` as passband limits
- **THEN** they SHALL appear only in the two `#define`s, and both `monitor_config_t` initialisers SHALL reference the constants
