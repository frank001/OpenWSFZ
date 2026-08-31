**User-facing:** no

## Why

F-001's 12-bit nonstandard-callsign hash path (`hashed-callsign-resolution`) resolves a Type 1/2/3
message's hash reference against a session-scoped table whose probe bucket is only 12 bits wide —
a many-to-one space over the amateur callsign population, so a probe chain can legitimately hold
more than one matching entry. F-001's own design named this risk and deferred sizing it. `SUP-A`
attempted to size it analytically/synthetically against a simulated table and was ruled VOID (the
bracket defect was the Architect's; the Product Owner ruled 2026-08-30 11:49Z: **"instrument the
real table"**). `SUP-B` is that instrument.

**Retrofit note (this document was authored 2026-08-30, after Phase 1 had already shipped):** this
change was not opened when Phase 1's native work began — the work instead ran on the project's
`qa/rr-study/*.md` Architect-spec + `dev-tasks/*.md` QA-handoff mechanism (HK-000/HK-011/HK-015)
with no `openspec/changes/` entry, unlike the two immediately preceding native ABI changes on the
same file (`fix-negative-time-offset-snr-collapse`, `r2-coherent-llr-instrument`), both of which
went through a full OpenSpec proposal with a `ft8lib-interop` spec delta. The Captain asked why,
directly, and directed retrofitting this change now rather than leaving the two new native exports
untracked in `openspec/specs/`. This document backfills Phase 1 (already shipped, unchanged in
substance) and specifies Phase 2 (Amendment 2, spec'd, not yet built) under one change, following
`r2-coherent-llr-instrument`'s own precedent for a capability specified end-to-end across phases
that were not one session of work.

**Phase 1 — shipped** (branch `qa/sup-b-2026-08-30`, shim `20260047`): three process-lifetime
read-only counters measuring, of every EMITTED decode that resolved via the 12-bit hash path, how
many hit an ambiguous (≥2-entry) probe chain, and of those, how many had their
most-recently-announced matching entry differ from the first (displayed) one. Source:
`qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`
Sec.3; dev-task `dev-tasks/2026-08-30-sup-b-h12-instrumentation.md`.

**Phase 2 — Amendment 2, spec'd, not yet built**: Sec.6.2's clustered 95% bootstrap needs cluster
*identity* (distinct 12-bit codes), and three cumulative scalars carry none — an Architect-
acknowledged gap in the original spec
(`qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`
Sec.B1: **"the gap is real and it is mine"**). Phase 2 adds a fixed 4,096-row per-code table
recording the same three quantities broken out by the 12-bit code itself. Dev-task:
`dev-tasks/2026-08-30-sup-b-amendment2-h12-cluster-table.md`, from the execution pack
(`qa/rr-study/2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md`
Sec.C2).

**Both phases are MEASURE-ONLY.** No unique-match suppression rule is implemented, enabled, or
flagged by this change (Sec.3.4 of the underlying spec). This instruments a question; it does not
answer it, and it does not change decode output. Phase 1's non-perturbation was independently
verified twice (ROW 0b, two comparators, 29,696/29,696 decodes byte-identical, `S-17M`).

## What Changes

- **(Phase 1, shipped)** Added three native, diagnostic-only, process-lifetime read-only getters —
  `ft8_get_h12_displaying_count`, `ft8_get_h12_ambiguous_count`, `ft8_get_h12_divergent_count` —
  counting, respectively, decodes displayed via a resolved 12-bit lookup, the subset that hit an
  ambiguous (≥2-entry) probe chain, and the subset of those where the most-recently-announced
  matching entry diverged from the first (displayed) one. Backing mechanism: a new
  `uint32_t announce_stamp` field on each hash-table entry (stamped in `hash_table_add` only, never
  in `hash_table_lookup` — TRAP 2), and a wholly separate, read-only probe-replay function that
  counts matches without altering `hash_table_lookup`'s own return path (TRAP 1). Gets full
  `Ft8LibInterop`/`IFt8NativeInterop` C# bindings and a per-cycle cumulative log line, matching the
  project's other `ft8_get_last_*`/`ft8_get_hash_table_reject_count` diagnostic-getter pattern.
  `FT8_SHIM_VERSION`/`ExpectedShimVersion` advanced `20260046` → `20260047`.
- **(Phase 2, spec'd, not yet built)** Adds one new native, diagnostic-only export,
  `ft8_get_h12_by_code(displaying, ambiguous, divergent, capacity, out_of_range)`, returning a
  complete 4,096-row breakdown of the same three quantities indexed by the 12-bit code, plus a
  code-width violation counter. Unlike Phase 1's three getters, **this export gets NO C# binding**
  — the reading is produced by the project's Python/ctypes replay harness directly, the same route
  Phase 1's three scalars already use for the Sec.6 measurement; a 4,096-row table has no place in
  a managed log line. `FT8_SHIM_VERSION`/`ExpectedShimVersion` advances again, `20260047` →
  `20260048`.
- **(Phase 2, spec'd)** Cycle-clustering was considered and rejected as a substitute for
  code-clustering: the hash table is session-scoped and persists across cycles, so the same
  ambiguous code recurs cycle after cycle — cycle-clustering would absorb the within-cycle
  correlation and leave the dominant across-cycle term unabsorbed, yielding a narrower interval
  that only looks like the one Sec.6.2 specifies.

## Capabilities

### Modified Capabilities

- `hashed-callsign-resolution`: two new Requirements — Phase 1's "Observable 12-bit hash-path
  unique-match sizing" (shipped) and Phase 2's "Observable 12-bit hash-path per-code cluster
  identity" (spec'd, not yet built). No change to resolution behaviour itself in either phase —
  both are read-only measurement layered on the existing table.
- `ft8lib-interop`: the ABI self-test's expected shim constant advances twice, `20260046` →
  `20260047` (Phase 1) → `20260048` (Phase 2); two new diagnostic native exports, one with a
  managed P/Invoke binding (Phase 1's three getters) and one without (Phase 2's table getter,
  following `ft8_ldpc_decode_llrs`'s own no-binding precedent from `r2-coherent-llr-instrument`
  Decision D10). `DecodeAll` and every other existing exported symbol are unchanged in both phases.

## Impact

- **Affected code (Phase 1, shipped):** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`/`ft8_shim.h` (the
  `announce_stamp` field, the probe-replay function, the three counters and getters);
  `src/OpenWSFZ.Ft8/Interop/{IFt8NativeInterop.cs,Ft8LibInterop.cs,Ft8NativeInteropAdapter.cs}`,
  `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (three new members each, plus the per-cycle log line); all 11
  `IFt8NativeInterop` test-double implementers (fixed-zero stubs); new
  `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs`; `native/ft8_lib_build/rebuild_shim.bat`,
  `src/OpenWSFZ.Ft8/Native/BUILD.md`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`, both
  rebuilt platform binaries (win-x64 SHA256 `37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26`,
  linux-x64 SHA256 `4970ec5fcc37e0ab291b4d3442b1f91b0fab5f982cc4703f19bc8764cf58384e`).
- **Affected code (Phase 2, spec'd, not yet touched):** `ft8_shim.c`/`ft8_shim.h` (the fixed
  4,096×3 table + out-of-range counter + one new export); `Ft8LibInterop.cs` — **one constant
  (`ExpectedShimVersion` → `20260048`) and its changelog comment, nothing else**;
  `rebuild_shim.bat`, `BUILD.md`, `libft8.version.txt`, both platform binaries rebuilt again.
  Deliberately **not** touched: `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`,
  `Ft8Decoder.cs`, any test-double implementer, any test file — Phase 2's export has no managed
  caller.
- **Affected tooling (QA, Phase 1, done):** `qa/cycleframer-alignment-replay/g3_h12_replay.py` (the
  replay driver), `row0_evaluate_s17m.py` (the ROW 0 evaluator) — the amended-for-Phase-1 ROW 0 (7
  rows: 0a-0e plus the two comparators inside 0b) ran and **PASSED in full on `S-17M`**, 2026-08-30
  15:39Z (`qa/rr-study/2026-08-30-1735-qa-to-architect-f001-sup-b-row0-result.md`). **This result
  is superseded, not contradicted, by Phase 2**: Amendment 2 Sec.B4 requires ROW 0 to re-run in
  full against Phase 2's binary — nothing binary-dependent carries forward across a shim-version
  change, though the non-perturbation finding (instrumenting at this site did not perturb 29,696
  decodes) stands as a *prior*, not a result, for the re-run.
- **Affected tooling (QA, Phase 2, in progress):** the same two files extended (one new getter
  binding, two new ROW 0 rows `0c-ii`/`0c-iii`, a widened `0e`); a pinned bootstrap
  (`numpy.random.default_rng(20260830)`, 10,000 draws, percentile method) over distinct
  participating 12-bit codes; three reading legs, `S-17M`/`S-80M`/`S-20M`, each an independent
  verdict (no pooling). Blocked on: a Developer session applying
  `dev-tasks/2026-08-30-sup-b-amendment2-h12-cluster-table.md` (HK-011).
- **Not affected:** production decode output in either phase (MEASURE-ONLY, confirmed
  empirically for Phase 1 via ROW 0b, argued for Phase 2 by construction — same guard condition,
  same emission site, additive array writes only); the unique-match suppression rule itself (not
  implemented, enabled, or flagged by this change, either phase); `SUP-A`'s exploratory `S`/`D`
  (remain VOID and uncitable); `S_max` = 40% (frozen, untouched by this change).
- **Licence:** no WSJT-X code read or copied for this change; standing licence policy
  (MIT/BSD-2/BSD-3/ISC only, no GPL-derived code) unaffected.
- **Downstream:** Phase 2 landing and passing its re-run ROW 0 unblocks the Sec.6 reading legs
  (`S-80M`/`S-20M`, plus `S-17M` as a free third band falling out of ROW 0's own INST replays,
  flagged for the Product Owner to rule on at that point per the execution pack Sec.C6, not decided
  here). A correct clustered interval is **wider** than the naive lookup-level one this project
  would otherwise have reported — Sec.7.1's power disclosure is unchanged by either phase, and this
  change does not improve it.
