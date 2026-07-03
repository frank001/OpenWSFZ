## 1. Native shim — persistent hash table (D1)

- [ ] 1.1 Confirm the current `FT8_SHIM_VERSION` value in `ft8_shim.c` at implementation time and
      reserve the next sequential version number (design D4); do not assume `20260030` is still
      current.
- [ ] 1.2 Add a process-global `static callsign_table_t g_session_hash_table` (and an
      initialisation guard, e.g. `static bool g_hash_table_initialised`) near the existing
      `tls_hash_table` declaration in `ft8_shim.c`.
- [ ] 1.3 In `ft8_decode_all`, replace the per-call stack-local `callsign_table_t htbl` /
      `hash_table_init(&htbl)` with: initialise `g_session_hash_table` once on first use, then set
      `tls_hash_table = &g_session_hash_table` at the top of every call (no re-init on subsequent
      calls).
- [ ] 1.4 Confirm `tls_hash_table = NULL` still executes on both the normal-return path and the
      `__except` (SEH) path, and that neither path calls `hash_table_init` on
      `g_session_hash_table` (design D2 — contents survive a caught AV; only the pointer is
      detached).
- [ ] 1.5 Leave `ft8_encode_message`'s existing per-call local table untouched — encoding computes
      hashes fresh via `ihashcall` and does not depend on prior session state (per design Context).
- [ ] 1.6 Update the version-history comment block at the top of `ft8_shim.c` with a new entry
      describing this change, following the existing style (see prior entries such as
      `fix-d004-local-noise-floor`, `decoder-settings-page`) — reference this change's name and
      summarise the persistent-table behaviour and the D2/D3 decisions.

## 2. Native shim — diagnostics (optional per design Open Questions)

- [ ] 2.1 Decide whether to add a native-only counter/log for `hash_table_add`'s
      reject-when-full guard (design's saturation risk mitigation), or defer until real session
      logs show it triggering. If added, keep it native-only (no new P/Invoke surface) per the
      Open Questions recommendation.

## 3. Tests — native/shim-level

- [ ] 3.1 Add a synthetic two-cycle test: encode a Type 4 message announcing a nonstandard
      callsign, decode it via `ft8_decode_all` in "cycle 1," then encode and decode (in a
      separate `ft8_decode_all` call, "cycle 2") a Type 1/2/3 message referencing that callsign's
      22-bit hash; assert the cycle-2 decoded text contains the full callsign rather than a hash
      placeholder. Covers the primary spec requirement (Cross-cycle callsign hash resolution).
- [ ] 3.2 Add a regression test confirming a hash with no prior Type 4 announcement in the
      session still decodes to the existing `<...>` placeholder (unchanged behaviour) — covers
      "Never-announced hash remains unresolved."
- [ ] 3.3 Add a regression test confirming same-cycle resolution (Type 4 and its hash reference
      both decoded within one `ft8_decode_all` call) still works — covers "Same-cycle resolution
      continues to work."
- [ ] 3.4 Add a table-saturation test: fill the table to its 256-entry capacity with distinct
      callsigns, then attempt to add one more; assert the new callsign is rejected and all
      previously stored entries remain resolvable and unchanged — covers "Bounded hash table
      growth."
- [ ] 3.5 Add (or extend an existing) AV-path test confirming that after a simulated/forced fault
      path, a subsequent unrelated `ft8_decode_all` call executes normally and previously learned
      hash mappings from before the fault remain resolvable — covers "Exception-path safety." If
      the existing D-006 AV test harness cannot easily simulate a fault mid-decode, document why
      and cover this via careful code review of the exception path instead; note the gap in the
      PR description.

## 4. Managed-layer verification (no code change expected)

- [ ] 4.1 Confirm `Ft8Decoder.cs`'s `IsPlausibleMessage` and the D-005 trim-fix path require no
      changes — run the existing `D005MessageTrimTests` and `Ft8DecoderPlausibilityTests` suites
      unmodified against the updated native shim to confirm no regression.
- [ ] 4.2 Confirm no existing R&R study synthetic corpus scenario exercises nonstandard/hashed
      callsign forms (per the proposal's Impact section); if one is found to exist, re-run the
      relevant R&R scenario and record the result in the change's QA notes before merge.

## 5. Build & regression

- [ ] 5.1 Rebuild `libft8.dll` from the updated shim per `BUILD.md`.
- [ ] 5.2 Run the full `OpenWSFZ.Ft8.Tests` suite against the rebuilt native binary.
- [ ] 5.3 Run the existing R&R study synthetic corpus (S1–S8 baseline) to confirm no regression in
      overall decode/false-positive rates versus the current baseline reference run.

## 6. Optional / stretch — Gap B: AP-assist for nonstandard callsigns (not required for merge)

- [ ] 6.1 (Stretch, defer if out of appetite) Extend `Ft8CallsignPacker` (C#) to pack special
      tokens (`CQ`/`DE`/`QRZ`, "CQ nnn", "CQ ABCD") and nonstandard/hashed callsigns
      (`NTOKENS ≤ n28 < NTOKENS + MAX22` range, via the same `ihashcall` algorithm described in
      design.md) so `Pack28` no longer returns `[]` for these cases.
- [ ] 6.2 (Stretch) Wire the extended packer into `QsoAnswererService.cs` /
      `QsoCallerService.cs`'s AP-constraint construction so AP decode-assist remains active when
      either party's callsign is nonstandard.
- [ ] 6.3 (Stretch) Add tests confirming AP-assisted decode succeeds for a nonstandard-callsign
      QSO exchange once both 1.x (persistent table) and 6.1/6.2 are in place.
- [ ] 6.4 If Gap B is deferred, note it explicitly as a follow-up in the change's closing notes /
      archive summary so it isn't lost.
