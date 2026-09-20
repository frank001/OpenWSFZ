## 0. Pre-flight (before any implementation)

- [x] 0.1 Branch off `origin/decoding_improvement` (tip `6cb98c52` when drafted). Never edit on a merged or `main` branch (HK-003).
- [x] 0.2 **Shim-version uniqueness, re-run at pickup** (history may have moved). The highest defined version on any ref must still be `20260053`, `20260054` must not be defined anywhere, and `20260052` stays reserved by the rc4 renumber task:
  `for r in $(git for-each-ref --format='%(refname)' refs/heads refs/remotes); do git show "$r:src/OpenWSFZ.Ft8/Native/ft8_shim.h" 2>/dev/null | grep -E '^#define FT8_SHIM_VERSION' | awk '{print $3}'; done | sort -u | tail` and `git log --all --oneline -S20260054`. If `20260054` has been taken, take the next value that is unused **and** unreserved, and say so.
- [x] 0.3 **D4 is DECIDED** (Architect, spec §12): the OSD depth is hoisted and tabled. Read design **D12** (completeness covers bare literals) before starting task 1.2.
- [x] 0.4 **Screenshot — BEFORE (HK-005).** With the app running on the unmodified tree, capture the existing `settings.html`, Advanced Decoder Settings section **expanded**, to `screenshots/decoder-param-readout/before-settings.png`. This is one of the very first tasks by design: it captures the pre-change state while it still exists in the working tree.
- [x] 0.5 **Baseline decode output for S1-a.** From the unmodified DLL (`91997e38…` is *not* the baseline; the baseline is the shipped `20260053` DLL, SHA-256 `50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7`), keep a copy. QA's acceptance needs it and will diff against it.

## 1. Native shim

- [x] 1.1 `ft8_shim.c`: define `K_PASSBAND_MIN_HZ 140.0f` and `K_PASSBAND_MAX_HZ 3075.0f` and use them at **both** `monitor_config_t` sites (`ft8_decode_all` and `ft8_extract_llrs_at`). Arithmetic-identical (D5).
- [x] 1.2 `native/ft8_lib_build/patched/ft8/decode.c`: replace the bare `2` in `osd_decode(llr_for_osd, 2, plain174)` (line 666 on `decoding_improvement`) with a named macro (e.g. `OSD_DEPTH 2`) visible to the shim so the table can report it. Arithmetic-identical (S1-a binds it).
- [x] 1.2b **Bare-literal audit (design D12).** Search the decode path for **any other** bare numeric *tuning* literal, in `ft8_shim.c` **and** every patched `native/ft8_lib_build/patched/ft8/*.c`, using the D12 definition (a literal that changes decode results without changing the protocol). **Protocol constants are only:** the 6.25 Hz tone spacing, 79 / 174 / 91, Costas, 8 tones, 12 kHz. 🔴 The **3.125 Hz sub-bin** (`6.25 / K_FREQ_OSR`) and the **half-symbol time sub-step** (`symbol period / K_TIME_OSR`) are **not** protocol: they are derived from tabled constants. **Report every one found** in the completion record with its file, line and value. Each is exactly one of: **hoisted to a named constant and added to the table** (arithmetic-identical); **derived** from a tabled constant (say which), listed as *derived* and **never** excluded as protocol; or **listed on the page's "Not included" note** (task 4.1b) with the reason. Where you are unsure, list it *with the doubt stated*. **Nothing is omitted silently.**
- [x] 1.3 Add module-level runtime state `s_supp_snr_min_db = -5.0f`, `s_supp_snr_max_db = 15.0f`, `s_supp_side_weight = 1.0f`, and `ft8_set_supp_params` / `ft8_get_supp_params` exactly per design **D6**, including the `-1`-and-unchanged validation and **no upper bound on `snr_max`**.
- [x] 1.4 `suppress_candidate_tiles`: the ramp uses the runtime min/max; the tone bin gets `factor`; the side bins get `factor_side = 1 − side_weight·(1 − factor)`. 🔴 **When `side_weight == 1.0f`, use `factor` itself**, not the recomputed expression.
- [x] 1.5 Add `Ft8ParamEntry` and `ft8_get_decoder_params` per **D1** (`_Static_assert(sizeof(Ft8ParamEntry) == 72)`), built from a single X-macro list (**D2**). It MUST include every runtime-settable value (the `ft8_set_decode_params` triple and the three suppression values) and every `#define K_*` the decode path reads (at least those listed in design Context §2), plus the passband constants, plus the OSD depth (D4), plus every further literal hoisted under task 1.2b. `default_value` for runtime entries is the **compiled** default (`osd_nhard_max` → `60`).
- [x] 1.6 `ft8_shim.h`: prototypes, struct, changelog entry in the file's existing style, and `#define FT8_SHIM_VERSION` → the version confirmed in 0.2 (`20260054`). State plainly: measure-only, no decode-output change at defaults.
- [x] 1.7 `native/ft8_lib_build/rebuild_shim.bat`: **three** new `/EXPORT:` lines. `BUILD.md`: mirror them. `libft8.version.txt`: a new entry **with the new DLL's SHA-256**. Rebuild the Windows DLL (`rebuild_shim.bat`); **confirm the DLL was built from your tree**, and keep the previous DLL.
- [x] 1.8 `dumpbin /exports` on the new DLL: **26 → 29** exports, none removed. (Linux exports by default visibility, so a missing Windows export builds clean there and fails only at P/Invoke.)

## 2. Managed interop

- [x] 2.1 `IFt8NativeInterop`: add one read-only method returning the parameter table (name, kind, value, default). **No** setter and **no** `DllImport` for `ft8_set_supp_params` / `ft8_get_supp_params`: they stay harness-only.
- [x] 2.2 `Ft8LibInterop.cs`: P/Invoke for `ft8_get_decoder_params` (size the buffer with the `out == NULL` call, then fill); `ExpectedShimVersion` → `20260054`; a `<remarks>` entry mirroring the neighbouring shim-bump entries. `Ft8NativeInteropAdapter.cs`: delegate.

## 3. Daemon endpoint

- [x] 3.1 `WebApp.cs`: `GET /api/v1/decoder/params` per **D8**. Read from `IFt8NativeInterop` on every request (no cache). `405` on any non-GET verb. `503` (never an empty table) if the native library cannot be loaded. Same authentication as the other `/api/v1` routes.
- [x] 3.2 `AppJsonContext.cs`: add the response types (AOT-safe).

## 4. GUI page

- [x] 4.1 `web/decoder-params.html` + `web/js/decoderParams.js` per **D9**: shim version, then *Runtime-settable* and *Compile-time* groups, each row `name · value · default`. **No `<input>`, `<select>`, `<textarea>` or mutating control.**
- [x] 4.1b The same page carries a **"Not included" note**: one entry per bare numeric tuning literal found by task 1.2b that was **not** hoisted and tabled, giving its file, line, value and the reason (and the doubt, where there is one), and **marking each derived value as "derived from `K_…`"** (for example the 3.125 Hz sub-bin from `K_FREQ_OSR`). If the audit found none beyond the OSD depth, the note says so explicitly: an empty note is a statement, a missing one is silence.
- [x] 4.2 `web/settings.html`: **one link** to the new page. The `#advanced-decoder-settings` block is **byte-for-byte unchanged**.

## 5. Tests (each requirement gets a test whose `DisplayName` starts `FR-0xx:`, G3)

- [x] 5.1 `tests/OpenWSFZ.Ft8.Tests/`: **FR-067** table completeness and truth. Test-local P/Invoke (no `DllImport` in `src/` for the setters). Assert `ft8_get_decoder_params(NULL, 0)` returns the total; each compile-time entry equals its `#define`; `osd_nhard_max` reads `default_value == 60`.
- [x] 5.2 `tests/OpenWSFZ.Ft8.Tests/`: **FR-068** suppression setter/getter. Set then get returns exactly; **each of the four invalid classes** (non-finite; `min >= max`; `side_weight < 0`; `side_weight > 1`) returns `-1` **and leaves the prior triple unchanged**; `snr_max = 30` is accepted; **round-trip in the table**: after `ft8_set_decode_params(7, 0.15f, 50)` and `ft8_set_supp_params(-10, 15, 0.5)`, `ft8_get_decoder_params` reports exactly those values, and after resetting to defaults, the defaults.
- [x] 5.2b `tests/OpenWSFZ.Ft8.Tests/`: **default-path identity.** With the setter never called, and with `(−5, 15, 1.0)` set explicitly, decode of a fixed synthetic scene is bit-identical.
- [x] 5.3 `tests/OpenWSFZ.Web.Tests/`: **FR-069** endpoint: `200` with the entries and `shimVersion`; values come from the (faked) native interop, **not** from `AppConfig` (a config value that differs from the fake's must not appear); `405` on `POST`/`PUT`/`DELETE`; `503` when the interop throws.
- [x] 5.4 **FR-070** GUI page. A DOM-level test in the project's existing web-test style: every entry the API returns appears with its value; **no editable control**; the settings page's `#advanced-decoder-settings` markup is unchanged; **the "Not included" note is present** and lists exactly the literals the completion record reports as not tabled.
- [x] 5.5 Run the full suite (`dotnet test OpenWSFZ.slnx -c Release`) and report the tally. Treat any decode-output test failure as a real finding. `Category=AwgnFpReplay` is CI-excluded and its stale SHA-pinned tests are not a new hazard.

## 6. Governance (gates G9a / G9b / G3 / G8)

- [x] 6.1 `VERSION` `0.49` → `0.50`.
- [x] 6.2 `README.md` and `REQUIREMENTS.md` "current release" anchor sentences → `v0.50`; a `REQUIREMENTS.md` version-history row.
- [x] 6.3 `REQUIREMENTS.md`: add **FR-067 … FR-070** (native table; suppression setter/getter; read-only endpoint; read-only page). Highest today is `FR-066`.
- [x] 6.4 `openspec/specs/ft8lib-interop/spec.md`: update the ABI requirement's `SHALL be` constant to `20260054` and append a history entry mirroring the `20260053` one. **A direct edit**, as `PASSBAND-140` and `DENSITY-P1` Stage 1 did: a MODIFIED delta would have to restate the whole 13 KB requirement.
- [x] 6.5 `traceability-debt.md` only if a new requirement is deliberately left without a test (it should not be).
- [x] 6.6 `openspec validate decoder-param-readout --strict` and `openspec validate --strict --all` (G8).

## 7. Verification and hand-back

- [x] 7.1 **Screenshot — AFTER (HK-005).** Same page, same state, to `screenshots/decoder-param-readout/after-settings.png`; and the new page to `after-decoder-params.png`. The editable section must look **identical** to the before shot.
- [x] 7.2 Playwright (`npx --yes playwright`, HK-007): open the new page against a running daemon, assert every API entry is listed with the API's value, and that no editable control exists.
- [x] 7.3 Hand back with the completion record in the dev-task (diff stat, new DLL SHA-256, export counts, uniqueness-check output, test tally, deviations). **Do not push or merge**: the Captain signs off the push (HK-011) and the merge (HK-010). **Do not run `tools/pre_merge_check.py`** (HK-000/HK-006): QA runs it at review.
