## Decisions

- **Default lives in `DecoderConfig`, not in `Ft8Decoder`.** The decoder class has no config; the daemon applies the flag at start-up
  and on every save (`Program.cs`). A bare `Ft8Decoder` stays OFF, so every decoder test that builds one directly runs the ordinary
  decode unless it sets the flag, and no test changes behaviour by accident.
- **Absent key reads `true`** because `System.Text.Json` leaves an unset init-only property at its initialiser; this is asserted through
  the real source-generated `ConfigJsonContext` and `JsonConfigStore` load/save path, not assumed.
- **Settings checkbox follows the FR-083 precedent** (`dec.x ?? true`), posts its boolean as it is, and is in the dirty-state snapshot
  and "Reset to defaults". The POST is an overlay (HK-035): a body without the key leaves the stored value unchanged.
- **Interaction:** the fallback has an effect only while `decoder.subtractionEnabled` is on; the help text says so.
