**User-facing:** no

## Why

`F-001`'s 12-bit nonstandard-callsign hash path (`hashed-callsign-resolution`) now suppresses
ambiguous matches (`f001-h12-unique-match-suppression`, shim `20260049`) and instruments the
resolved side of the lookup — `ft8_get_h12_by_code` (`SUP-B` Phase 2, shim `20260048`) counts,
per 12-bit code, every lookup that resolved and was displayed. **L3 asks the complementary
question: of the lookups that did NOT resolve at all, how many landed on each of the 4,096
possible codes?** That population is currently uncounted anywhere — `ft8_get_h12_by_code`'s own
row-149 entry (used by an earlier arm's `PD2FZ` cross-check) counts only *resolved* lookups by
construction (out of scope for this question, HK-026) and says nothing about the unresolved
population's own shape.

L3's own sizing question — is our own code a disproportionately large source of unresolved 12-bit
hash lookups relative to its share of on-air traffic — needs this count to be measurable at all.
Spec: `qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md`
(Architect → QA, 2026-09-02), Amendment 1 (2026-09-03 16:16Z, padding-population correction). PO
ruling on the gate wording (board, 2026-09-03 16:16Z, "RULING 2"):
**`tls_h12_lookup_performed && !tls_h12_resolved`** — the spec's own literal
`tls_h12_multiplicity == 1` text was the Architect's drafting slip (provably the empty set under
the current shim; see design.md D1) and is withdrawn.

**This change opens the `openspec/changes/` entry BEFORE the Developer session**, unlike
`f001-sup-b-instrumented-suppression-sizing`, which retrofitted its OpenSpec proposal after Phase
1 had already shipped through the `qa/rr-study/*.md` + `dev-tasks/*.md` mechanism alone. That
retrofit's own design.md left this as an explicit Open Question (#3): "whether future SUP-* native
changes open the `openspec/changes/` entry before the Developer session instead." This change
answers it — the way the underlying dev-task
(`dev-tasks/2026-09-03-f001-l3-unresolved-by-code-export.md`) is already fully specified (§0's
blocking question resolved in-document, §2 gives exact code), so drafting this proposal is not new
derivation, only re-expression in OpenSpec form for a Developer session to run `opsx:apply`
against.

## What Changes

- Adds **one new native, diagnostic-only, process-lifetime read-only export**,
  `ft8_get_h12_unresolved_by_code(counts, capacity, out_of_range)` — a complete 4,096-row
  breakdown of unresolved 12-bit hash lookups by code, mirroring `ft8_get_h12_by_code`'s exact
  shape (same signature, same `H12_CODE_SPACE` = 4,096 capacity, same `NULL`/capacity contract) but
  counting the **complement** branch: `tls_h12_lookup_performed && !tls_h12_resolved`, i.e. a
  12-bit lookup that found no matching table entry at all.
- **Like `ft8_get_h12_by_code` (`SUP-B` Phase 2, Decision D5), this export gets NO managed
  `Ft8LibInterop`/`IFt8NativeInterop` C# binding.** The only caller is QA's own Python/ctypes
  replay harness, following the exact precedent that export set — a 4,096-row table has no place
  in a per-cycle managed log line, and adding a binding nobody calls would trigger the
  test-double-implementer cascade for zero benefit.
- `g_h12_code_out_of_range` (the existing code-width violation counter from `SUP-B` Phase 2) is
  **reused, not duplicated** — it already counts an out-of-range `tls_h12_code` regardless of
  which branch observed it.
- `FT8_SHIM_VERSION`/`ExpectedShimVersion` advances `20260049` → `20260050`. This exact number is
  pre-registered as a hard ROW 0a gate value in the underlying spec — it must not be substituted
  even if it appears "taken" at build time; a genuine collision is a STOP-and-escalate condition
  (see the shim-renumber dev-task, filed the same day, for the reason this trap exists).
- **No production decode-path behaviour changes anywhere.** No existing function, struct, return
  value, or export changes; `hash_table_lookup`, `hash_table_add`, and `cb_lookup_hash`'s return
  value are untouched.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `hashed-callsign-resolution`: one new Requirement — "Observable 12-bit hash-path unresolved-lookup
  sizing, by code" — read-only measurement layered on the existing lookup path, no change to
  resolution behaviour itself (parallel in shape to `SUP-B`'s own two sizing Requirements on this
  capability, but on the complementary, not-found branch).
- `ft8lib-interop`: the ABI self-test's expected shim constant advances `20260049` → `20260050`;
  one new diagnostic native export, **without** a managed P/Invoke binding (following
  `ft8_get_h12_by_code`'s own no-binding precedent, `SUP-B` Phase 2 Decision D5, itself following
  `ft8_ldpc_decode_llrs`'s precedent from `r2-coherent-llr-instrument` Decision D10). `DecodeAll`
  and every other existing exported symbol are unchanged.

## Impact

- **Affected code:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`/`ft8_shim.h` (one new fixed 4,096-row
  table, one new emission-site `else if` branch on the existing guard family, one new getter, one
  new header declaration + changelog entry, version bump); `native/ft8_lib_build/rebuild_shim.bat`
  (one new `/EXPORT:` line, Windows only — Linux uses default visibility);
  `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` (new CURRENT block).
  **Deliberately NOT touched:** `IFt8NativeInterop.cs`, `Ft8LibInterop.cs`,
  `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`, any test-double implementer, any `.cs` test file —
  this export has no managed caller (design D2, mirroring `SUP-B` Phase 2 D5). `ft8_get_h12_by_code`
  and its three `SUP-B` scalar getters are untouched — this is purely additive.
- **Affected tooling (QA, blocked on this change landing):** the L3 measurement arm's own ROW 0–3
  (spec §5), reading `qa/ARTEFACT_INVENTORY.md`-listed corpora through a Python/ctypes replay
  harness extension (spec §7 step 3) — QA's to run after this ships, not part of this change's own
  Definition of Done.
- **Not affected:** production decode output (MEASURE-ONLY, argued by construction — same guard
  family as the existing resolved-branch emission site, additive array writes only, to be
  confirmed empirically by ROW 0e, ported into this change's own task list, before handoff); the
  unique-match suppression rule (`f001-h12-unique-match-suppression`, unrelated, already shipped);
  `SUP-B`'s three existing scalar counters and its per-code resolved table (untouched, different
  branch, different array).
- **Licence:** no WSJT-X code read or copied for this change; standing licence policy
  (MIT/BSD-2/BSD-3/ISC only, no GPL-derived code, Captain's ruling 2026-08-11) unaffected.
- **Downstream:** unblocks QA's L3 measurement arm (spec §5 ROW 0–3), which is gated on
  `U_clean = U_total − U[0]` per the spec's own Amendment 1 (padding always lands at code 0), not
  on this change's own scope.
