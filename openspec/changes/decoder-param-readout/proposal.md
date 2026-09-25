**User-facing:** yes

## Why

Three times in one programme a number was cited for a decoder that was **not the decoder that produced it**, because nobody could see which parameters the native library was actually running with:

- `DENSITY-MECH` §11.2 — every direct-DLL harness ran at the shim's compiled default `nhard = 60` while the live app runs `40`; the split went unnoticed across several arms.
- `DENSITY-P1` §7 A3 — a spec required "decode params read back" from a DLL that has **no getter**.
- The soft-suppression ramp (`K_SOFT_SUPP_SNR_MIN_DB` / `MAX_DB`) is a compile-time constant with no way to read it, let alone vary it.

The Captain's direction (2026-09-19): *"include in the change all decoder params readout and create a setting page in the gui to display them all, readonly."*

This change also carries the one piece of native work the `DENSITY-REMEDY` arm's later stages need: a **runtime setter and getter for the suppression ramp** (`snr_min`, `snr_max`, `side_weight`). `DENSITY-P1` showed the ramp's floor and ±1-bin footprint are the two levers a remedy could pull, and both are currently baked in. **Defaults do not change. Live behaviour does not change.** This is instrumentation and a readout, not a tuning.

## What Changes

- **Native — parameter table.** One new export `ft8_get_decoder_params` returns every decoder parameter as a table of `(name, value, default, kind)`, where `kind` is `runtime` or `compile-time`. Values are what the native decoder **reports now**, not what `app.json` says. Covers every runtime-settable value, every compile-time tuning constant on the decode path, and (via the existing sentinel) the shim version.
- **Native — suppression ramp setter/getter.** `ft8_set_supp_params(snr_min_db, snr_max_db, side_weight)` and `ft8_get_supp_params(out3)`. Defaults `-5.0f`, `15.0f`, `1.0f`. **The default path is arithmetic-identical to today** (byte-identical decode output).
- **Native — make the table truthful by construction.** Two literals that today live at two call sites each (the candidate passband `140.0f` / `3075.0f`) become named constants used at both sites, so the value the table reports **is** the value the decoder uses. Arithmetic-identical.
- **Managed.** `Ft8LibInterop` reads the table (`IFt8NativeInterop` gains one read-only method). **No managed setter** for the suppression parameters: the live app never calls it.
- **Daemon.** A read-only endpoint `GET /api/v1/decoder/params` serves the table plus the shim version, read from the native library at request time.
- **GUI.** A new **read-only** page (`web/decoder-params.html`) lists every entry, grouped runtime vs compile-time, with the shim version. **No inputs, no save.** The existing editable *Advanced Decoder Settings* section is **unchanged**; the new page sits beside it.
- **Shim version** `20260053` → **`20260054`**, three platform binaries, `libft8.version.txt`, `BUILD.md`, `Ft8LibInterop.ExpectedShimVersion`.

## Governance consequences (read before estimating)

This is a **user-visible feature on `decoding_improvement`**, so the project's mechanical gates apply:

- **G9b:** this proposal declares `**User-facing:** yes`, so the implementing PR **MUST bump `VERSION`** (`0.49` → `0.50`). The proposal first appears **in that PR**, not before (do not land this file on a branch that reaches `main` without the bump).
- **G9a:** the `README.md` and `REQUIREMENTS.md` "current release" anchor sentences and a `REQUIREMENTS.md` version-history row move with the bump.
- **G3:** new requirements need `FR-` identifiers (the highest at proposal time was `FR-066`, so this change originally used `FR-067`–`FR-070`; renumbered to `FR-074`–`FR-077` on 2026-09-25 when syncing with `main`, which had independently shipped `FR-067`–`FR-073` for an unrelated pair of changes (#187/#188) in the meantime — see this change's own `tasks.md` for the full rename) and at least one test whose `DisplayName` starts `FR-0xx:` for each.
- **G8:** `openspec validate --strict --all` must stay green.
- **HK-005 / HK-007:** before/after screenshots of the **existing** settings page (proving the editable section is unchanged), and a Playwright check of the new page.

## Capabilities

### New Capabilities

- `decoder-param-readout`: the native parameter table's contract, the read-only API endpoint, and the read-only GUI page; the guarantee that what is shown is what the native decoder reports.

### Modified Capabilities

- `ft8lib-interop`: three new native exports (`ft8_get_decoder_params`, `ft8_set_supp_params`, `ft8_get_supp_params`), the hoisted constants, and `ExpectedShimVersion` `20260054`.

## Impact

- **Native:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` / `ft8_shim.h`; `native/ft8_lib_build/rebuild_shim.bat` (three `/EXPORT:` lines); `native/ft8_lib_build/patched/ft8/decode.c` (the OSD-depth hoist, design D4, decided) and any further patched `ft8/*.c` literal the D12 audit hoists; three platform binaries.
- **Managed:** `Ft8LibInterop.cs`, `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`; `OpenWSFZ.Web` (`WebApp.cs`, `AppJsonContext.cs`).
- **Web:** `web/decoder-params.html`, `web/js/decoderParams.js`, one link from `web/settings.html`.
- **Governance:** `VERSION`, `README.md`, `REQUIREMENTS.md`, `traceability-debt.md` if needed, `openspec/specs/ft8lib-interop/spec.md` (ABI constant, direct edit).
- **No breaking changes.** No `app.json` change. No default changes. No decode-output change at defaults (gate S1-a).
