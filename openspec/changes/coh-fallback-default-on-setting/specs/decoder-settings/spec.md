## ADDED Requirements

### Requirement: The coherent fallback setting SHALL default to on and have a Settings control

`DecoderConfig` SHALL carry `coherentFallbackEnabled`. Its default SHALL be `true`: a stored `decoder` section without the key, and a
configuration with no `decoder` section, SHALL read `true`; an explicit `false` SHALL stay `false` through load, save and reload. With the
value `false` the decoder SHALL behave exactly as it did before the coherent fallback existed. The value takes effect on the next decode
cycle, and has an effect only while `decoder.subtractionEnabled` is on.

The Advanced Decoder Settings section SHALL contain a checkbox for it, next to the early-decode controls, with a help text that says what it
does, that it needs subtraction, that it takes effect on the next decode cycle and that the default is on. The checkbox SHALL show checked
when no value is stored, SHALL post its state as it is, and "Reset to defaults" SHALL check it.

#### Scenario: No stored key

- **WHEN** the stored configuration has no `coherentFallbackEnabled` key
- **THEN** the decoder runs the fallback and the Settings page shows the box checked

#### Scenario: Explicit off

- **WHEN** the operator unticks the box and saves
- **THEN** `coherentFallbackEnabled: false` is stored, survives a reload and shows unchecked, and the fallback does not run from the next cycle

#### Scenario: Overlay save

- **WHEN** a configuration POST carries a `decoder` object without `coherentFallbackEnabled`
- **THEN** the stored value is unchanged
