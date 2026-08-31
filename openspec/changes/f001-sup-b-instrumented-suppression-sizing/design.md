## Context

Full derivation lives in four Architect documents this design.md does not re-derive, only
indexes: the original spec
(`qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`),
Amendment 1 (pre-merge ROW 0 reordering,
`qa/rr-study/2026-08-30-1432-architect-to-qa-spec-f001-sup-b-amendment-1-row0-pre-merge.md`),
Amendment 2 (the cluster-table gap and its fix,
`qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`),
and the execution pack (predicates/harness/bootstrap/order,
`qa/rr-study/2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md`).

**This document is a retrofit.** Phase 1 (shim `20260047`) was designed, built, and ROW-0-verified
entirely through the `qa/rr-study/*.md` + `dev-tasks/*.md` mechanism, with no `openspec/changes/`
entry — a divergence from the immediately preceding two native ABI changes on the same file
(`fix-negative-time-offset-snr-collapse`, `r2-coherent-llr-instrument`), both of which used a full
OpenSpec proposal. Raised by the Captain 2026-08-30, who directed this retrofit rather than leaving
the divergence in place or leaving the two new native exports (`20260047`'s three getters,
`20260048`'s table getter) untracked in `openspec/specs/`. This document backfills Phase 1's
decisions from the shipped artefacts (`ft8_shim.c`/`.h`, `Ft8LibInterop.cs`, the version log, the
QA ROW 0 result) and specifies Phase 2 (Amendment 2) prospectively, as `r2-coherent-llr-instrument`
did across its own Phase 0/1/B/Amendment-2-3 boundary — one capability specified end-to-end, not
one session of work.

`SUP-A` (the predecessor arm) attempted to size the same risk against a *simulated* hash table and
was ruled VOID: its ROW 0b failed all three primaries, and the bracket defect traced to the
Architect's own simulation, not the real decoder. The Product Owner's ruling (2026-08-30 11:49Z)
was explicit: **"instrument the real table."** `SUP-B` is that instrument, and both of its phases
touch only the real, production `g_session_hash_table` — there is no simulated table anywhere in
this change.

## Goals / Non-Goals

**Goals (Phase 1, shipped):**
- Measure, of every EMITTED decode resolved via the 12-bit hash path: how many hit an ambiguous
  (≥2-entry) probe chain (`S = h12Ambiguous / h12Displaying`), and of those, how many had their
  most-recently-announced matching entry diverge from the first, displayed one
  (`D = h12Divergent / h12Displaying`).
- Do so **without altering `hash_table_lookup`'s return path in any way** — the counting
  mechanism must be provably incapable of changing what a lookup returns or the callsign text it
  writes (TRAP 1).
- Do so on the SAME (single, process-global, `main`'s existing) session-scoped table F-001 already
  built — not a second table, not a simulation.

**Goals (Phase 2, Amendment 2, spec'd, not yet built):**
- Close the gap Sec.6.2 (a 95% cluster bootstrap resampling distinct 12-bit codes) exposed in
  Phase 1's own instrument: three cumulative scalars carry counts, never cluster identity, so no
  interval — and therefore no verdict — was computable from Phase 1's output alone.
- Add the minimum sufficient statistic for that bootstrap: a per-code (not per-lookup) table.
  Per-lookup rows are explicitly a non-goal (below) — the fixed table is complete for the
  bootstrap's needs and keeps NFR-021 trivial by construction.

**Non-Goals (either phase):**
- **Not implementing, enabling, or flagging the unique-match suppression rule itself** (Sec.3.4 of
  the underlying spec). Both phases are read-only measurement; decode output is unaffected.
- **Not producing per-lookup rows in Phase 2.** The cluster table is a complete sufficient
  statistic for Sec.6.2's bootstrap; a per-lookup dump would carry message-adjacent content for no
  additional statistical power and would multiply the NFR-021 surface for nothing.
- **Not clustering by decode cycle as a substitute for clustering by code** (Decision D7 below) —
  considered and rejected, not merely undiscussed.
- **Not giving Phase 2's `ft8_get_h12_by_code` a managed `IFt8NativeInterop`/`Ft8LibInterop`
  binding** (Decision D5) — no C# caller exists or is planned; the reading is produced by the
  Python/ctypes replay harness directly.
- **Not touching `SUP-A`'s exploratory `S`/`D`** — they remain VOID and uncitable regardless of
  this change's own results.
- **Not moving `S_max` = 40%** in either direction — frozen, unrelated to this change's findings.
- **Not pooling across the three reading bands** (`S-17M`/`S-80M`/`S-20M`) — Sec.6.3's prohibition
  is unchanged; three bands are three independent verdicts, never a bigger `n`.

## Decisions

**D1 (Phase 1) — the multiplicity/divergence count is a wholly separate, read-only function from
`hash_table_lookup`; it is never called from inside it and never calls it (TRAP 1).**
Alternative considered: instrument `hash_table_lookup` itself (e.g. a counter increment inline in
its existing probe loop). Rejected — any edit inside that function's body reopens the exact
question ROW 0b exists to close (does this change decode output?), and makes "no" harder to prove
by inspection. A wholly separate function replaying the identical probe derivation (same `h10`/`idx`
math, same `HASH_TABLE_SIZE` bound, same empty-slot termination) but continuing past the first
match is provably incapable of changing what the original function returns, because it never
touches the original function's code path at all. Verified empirically (not just by inspection):
ROW 0b's two independent comparators found 29,696/29,696 decodes byte-identical, `S-17M`,
BASE vs INST.

**D2 (Phase 1) — recency (`announce_stamp`) is stamped in `hash_table_add` only, never in
`hash_table_lookup`.**
The obvious alternative — refresh recency on lookup, so "most recently used" tracks read access —
is exactly the defect SUP-A's own Amendment 1 named in its simulated `SimTable.lookup()`
(contaminating announcement recency with lookup recency). The product question is which callsign
was most recently *announced* (a Type 4 message), not which was most recently *looked up* (a
Type 1/2/3 reference) — stamping on lookup would answer a different, uninteresting question while
looking like the right one.

**D3 (Phase 1) — per-message scratch is reset immediately before `ftx_message_decode` and read only
once that message is unconditionally headed for `results[]` — the counters denominate DISPLAYS,
not decode attempts (TRAP 3).**
`message.c`'s 12-bit lookup call site fires during `ftx_message_decode`, before the emitting
`ft8_decode_all` caller knows whether the resulting message will survive dedup and actually be
emitted. Counting at the lookup-attempt site would inflate the denominator with discarded/deduped
messages nobody ever sees; the counters would then answer "how often does a lookup ambiguity
occur," not "how often does the operator actually see the consequence" — the product question
Sec.0/3.1 of the underlying spec asks. The reset-then-read bracket is sufficient with no
accumulation because the 12-bit lookup call site fires at most once per message (`message.c:431`
is the only call site).

**D4 (Phase 2) — `0c-ii` (code-width invariant) MUST be evaluated before `0c-iii` (table↔scalar
reconciliation), and both exist because masking preserves the sum.**
If a code somehow arrived wider than 12 bits, `c = code & 0xFFF` would write into the *wrong*
bucket — but it would still write exactly one increment, so `0c-iii`'s three totals would reconcile
**perfectly** while cluster identity (the entire product of Phase 2) was silently scrambled.
`0c-iii` is structurally blind to the one failure that would destroy what it appears to protect.
`g_h12_code_out_of_range` therefore exists as a *counted* violation, evaluated as its own row,
first, rather than a silent mask — the same reasoning `hash_table_reject_count` already established
for a different saturation risk in this file.

**D5 (Phase 2) — `ft8_get_h12_by_code` gets NO managed `Ft8LibInterop`/`IFt8NativeInterop`
binding, following `ft8_ldpc_decode_llrs`'s precedent (`r2-coherent-llr-instrument` Decision
D10).**
Checked, not assumed: the Sec.6 reading is produced by the project's own Python/ctypes replay
harness (`g2_verification_replay.py`/`g3_h12_replay.py`), which already drives the named DLL
directly by ctypes for Phase 1's three scalars — it does not go through `IFt8NativeInterop` at all.
A 4,096-row table has no place in an FR-019 log line, which is the only thing the managed counters
serve. Adding a binding nobody calls would be unused production-adjacent surface for a
diagnostic-only export, and would trigger the 11-implementer test-double cascade for zero benefit.

**D6 (Phase 2) — a cluster is a code with `displaying > 0`; codes with zero displays are EXCLUDED
from the bootstrap's resample population, not counted as zero-value clusters.**
Including all 4,096 codes would inflate the population size `N` toward 4,096 regardless of how few
codes actually participated, silently narrowing the bootstrap interval and defeating the correction
Sec.6.2 exists to make. Every participating code has `disp[c] >= 1` by construction, so no draw's
denominator can be zero — asserted at runtime anyway, since a zero denominator would mean the
population was built wrong, and the assertion is how that would be discovered rather than silently
producing `NaN`.

**D7 (Phase 2) — cycle-clustering is REJECTED as a substitute for code-clustering, considered and
argued against explicitly, not merely unconsidered.**
The session-scoped hash table persists across cycles (`ft8_shim.c:766-768`), so the same ambiguous
code recurs cycle after cycle. Clustering by decode cycle would absorb the *within-cycle*
correlation term but leave the *across-cycle* term — which is the dominant one, and the exact term
Sec.6.2's code-level clustering was written to absorb — unabsorbed. The result would be a narrower
interval that superficially resembles the specified one while measuring something else. This is
the Architect's own reasoning (Amendment 2 Sec.B1), recorded here so a future session doesn't
re-propose it as a shortcut once Phase 2's own resampling code exists to make it easy to try.

## Risks / Trade-offs

- **[Risk, Phase 2] A correct clustered interval is WIDER than the naive lookup-level one this
  project would otherwise have reported — that is the entire reason Sec.6.2 asked for it.** Sec.6.4
  evaluates `MARGINAL` first, and it governs: a wider interval is more likely to span the 40%
  threshold. This makes a clean (non-`MARGINAL`) verdict LESS likely, not more, and that is
  disclosed here (and in Amendment 2 Sec.B6) before either reading leg runs, not after a result
  that happens to land badly.
- **[Risk, Phase 2] ROW 0 must re-run in full against Phase 2's binary; nothing binary-dependent
  from Phase 1's 15:39Z ALL-SEVEN-PASS carries forward.** A new shim version voids `0a` by
  construction and, more importantly, voids `0b` — the load-bearing non-perturbation identity.
  What the Phase 1 result DOES buy: a *prior* that instrumenting at this exact site, under this
  exact guard, does not perturb decode output (Phase 2's additions are array writes inside an
  already-proven block) — not a result, and it substitutes for nothing.
- **[Trade-off] Phase 2's export is diagnostic-only and untested by the existing C# test suite** —
  by design (D5), since it has no managed caller, its only verification is the Python/ctypes replay
  harness's own ROW 0 rows (`0c-ii`, `0c-iii`, the widened `0e`), not a `dotnet test` assertion.
- **[Process risk, this retrofit] `BUILD.md`'s `/EXPORT:` list is already missing
  `ft8_get_last_snr_terms`** (added by `r2-coherent-llr-instrument`, never backfilled there) —
  found while authoring Phase 2's dev-task. Not fixed by this change (it would be an unregistered
  ninth file in Phase 2's pre-registered eight-file diff); flagged here so it is not silently
  rediscovered a third time.

## Migration Plan

Same discipline both phases, matching every prior native change on this file: a
`FT8_SHIM_VERSION`/`ExpectedShimVersion` bump, all reachable platform binaries rebuilt, zero
production call sites added or changed, rollback is a plain `git revert`. Phase 1 is fully shipped
and ROW-0-verified (`S-17M`, 15:39Z, all seven rows PASS) — that specific result is superseded, not
falsified, by Phase 2's mandatory re-run once Phase 2's binary exists. Phase 2 does not depend on
any reading leg having run, and no reading leg may run before Phase 2's own ROW 0 re-run passes and
the Captain has reviewed the diff (HK-010) — the Product Owner's explicit ruling, 2026-08-30 16:08Z:
"hold the merge, extend, one ROW 0."

## Open Questions

1. **Whether `S-17M`'s per-code table, which falls out of Phase 2's own ROW 0 INST replays at zero
   additional machine cost, is read as a third independent reading band alongside `S-80M`/`S-20M`**
   — flagged for the Product Owner at the execution pack's own step 7 (Sec.C6), not decided here.
   If admitted, Sec.6.3's no-pooling rule still applies: three bands, three verdicts.
2. **Whether `BUILD.md`'s pre-existing `ft8_get_last_snr_terms` omission (Risks, above) is ever
   backfilled** — not this change's scope; a separate small housekeeping task if anyone picks it
   up.
3. **Whether this retrofit pattern (Architect spec + dev-task first, OpenSpec change backfilled
   once native/ABI work is confirmed) becomes the standing process for this measurement-arm
   programme, or whether future SUP-* native changes open the `openspec/changes/` entry before the
   Developer session instead** — a Captain-level process decision, out of scope for this document
   to make; flagged here rather than silently resolved either way.
