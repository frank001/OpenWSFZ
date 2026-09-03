## Context

Full derivation lives in three Architect/QA documents this design.md indexes rather than
re-derives: the spec
(`qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md`), its
Amendment 1 (2026-09-03 16:16Z, the padding-population correction), and the QA dev-task
(`dev-tasks/2026-09-03-f001-l3-unresolved-by-code-export.md`), which already resolved the one
blocking question below and gives the exact C source for every file this change touches.

L3 is the complement of `f001-sup-b-instrumented-suppression-sizing` Phase 2: that change's
`ft8_get_h12_by_code` counts, per 12-bit code, lookups that **resolved and were displayed**. This
change counts lookups that **did not resolve at all** — the other side of the same probe chain,
never previously counted anywhere. `ft8_get_h12_by_code`'s own row-149 cell (used by an earlier
arm's `PD2FZ` cross-check) is explicitly out of scope for this question (HK-026: it counts only
the resolved population, by construction, and cannot bound the unresolved one's shape).

## Goals / Non-Goals

**Goals:**
- Measure, of every 12-bit hash lookup that found **no** matching table entry, which of the 4,096
  possible codes it carried — the minimum sufficient statistic for L3's own sizing question (spec
  §4), mirroring `ft8_get_h12_by_code`'s per-code shape exactly.
- Do so as a **wholly additive** emission-site branch on the exact same guard family as the
  existing resolved-branch counters, so it is provably incapable of perturbing `cb_lookup_hash`'s
  return value or any existing counter (D4 below).

**Non-Goals:**
- **Not implementing, enabling, or flagging any runtime compare-and-respond behaviour.** This
  export is MEASURE-ONLY (spec §8); building it is not a licence to build the L3 comparator itself.
- **Not giving `ft8_get_h12_unresolved_by_code` a managed `IFt8NativeInterop`/`Ft8LibInterop`
  binding** (Decision D2) — no C# caller exists or is planned, following `ft8_get_h12_by_code`'s
  own precedent exactly (`f001-sup-b-instrumented-suppression-sizing` Decision D5).
- **Not adding a second `g_h12_code_out_of_range`-equivalent counter** — the existing one is reused
  (Decision D3).
- **Not building `ft8_get_h12_ambiguous_padding_count()`** — the board's standing "any future
  sizing work needs the padding counter first" instruction is satisfied for free here: padding is
  always code 0 (`ftx_message_encode_nonstd`, `message.c:256-261`, hard-wires `n12=0` for every
  `icq!=0` message), so `counts[0]` from this same per-code export already isolates it. QA's own
  measurement arm reads `U_clean = U_total − counts[0]`, never `U_total` — a QA-side reading
  convention, not something this change's own code needs to implement (spec Amendment 1 A1.2/A1.3).

## Decisions

**D1 — the gate is `tls_h12_lookup_performed && !tls_h12_resolved`, not the spec's own literal
`tls_h12_multiplicity == 1` text, which is provably the empty set under the current shim.**
`cb_lookup_hash` (`ft8_shim.c:802-828`) hard-codes `tls_h12_multiplicity = 0` on the `else`
(not-found) branch (`:821`) rather than computing it, because `hash_table_lookup` (`:637-655`) and
`hash_table_count_h12_multiplicity` (`:668-693`) walk the **identical** open-addressing probe
chain with identical empty-slot termination — whenever `found == false`, a multiplicity count over
that same chain is provably also zero, so there is nothing to compute. Conversely,
`tls_h12_multiplicity == 1` only ever occurs when `found == true && !tls_h12_suppressed` — the
successful, resolved, displayed case (L2), the exact opposite of "unresolved." An export gated
literally as the spec's own text reads would compile, link, pass every ROW 0 identity/wiring check,
and report `U_total = 0` on every corpus — which the spec's own ROW 0g (`U_total < 500 ⇒ STOP`)
correctly reads as an instrument failure. The PO ruled 2026-09-03 (board, "RULING 2", re-verified
by the Architect directly from source): the gate is `tls_h12_lookup_performed && !tls_h12_resolved`
— the mechanically-consistent reading of the ruling's own stated intent ("exclude the suppressed
subset") — and the `== 1` wording was the Architect's drafting slip, withdrawn. Alternative
considered and rejected: build the literal `== 1` gate as a forward-looking hook for a future change
to not-found-branch multiplicity computation. Rejected because nothing in the spec or the PO ruling
asks for that hook, and it would deliberately ship a ROW 0g STOP on every existing corpus for no
present benefit.

**D2 — `ft8_get_h12_unresolved_by_code` gets NO managed `Ft8LibInterop`/`IFt8NativeInterop`
binding, following `ft8_get_h12_by_code`'s own precedent exactly
(`f001-sup-b-instrumented-suppression-sizing` Decision D5, itself following
`ft8_ldpc_decode_llrs`'s precedent from `r2-coherent-llr-instrument` Decision D10).**
The L3 reading (spec §7 step 3) is produced by QA's own Python/ctypes replay harness extension, the
same route `ft8_get_h12_by_code` already uses — it does not go through `IFt8NativeInterop` at all.
A 4,096-row table has no place in a per-cycle managed log line, and adding a binding nobody calls
would trigger the (now 13-implementer, per `f001-h12-unique-match-suppression`'s own count) test-
double cascade for zero benefit.

**D3 — `g_h12_code_out_of_range` is reused, not duplicated.**
It already counts an out-of-range `tls_h12_code` regardless of which branch (resolved or
unresolved) observed it — the spec's own ROW 0c reads it as a single wiring-violation signal across
both tables (spec §4/§5). A second, branch-specific counter would only fragment a signal that is
more useful pooled, and there is no reading in the spec that needs the two split apart.

**D4 — the new emission-site branch is an `else if` on the exact same `if
(tls_h12_lookup_performed...)` guard family as the existing resolved-branch counters
(`ft8_shim.c:1650-1667`), not a second, independent `if` block.**
An independent `if` could in principle double-count a lookup that is somehow both resolved and
unresolved (impossible today, but not provably so to a future reader without tracing both
conditions), or race against a future edit to the guard. An `else if` on the identical condition
family is a mechanical complement by construction — exactly one of the two branches fires per
lookup, verifiable by diff review rather than by runtime testing alone. This mirrors
`f001-h12-unique-match-suppression`'s own emission-site discipline (that change's TRAP-3 comment,
`:1648`) applied to a sibling counter rather than a sibling suppression decision.

**D5 — padding contamination is handled by reading convention (`U_clean = counts_total −
counts[0]`), not by a second export.**
`ftx_message_encode_nonstd` (`message.c:256-261`) hard-wires `n12=0` for every `icq!=0` message,
and `decode_nonstd` looks slot 0 up unconditionally (`message.c:431`) and discards it (`:451`) —
those lookups are padding, not a hash of anything, and when code 0 has no matching table entry they
land in exactly this export's own population, always at `counts[0]`. Because the export is
per-code, this isolates the contamination for free: no new counter, no second export, no shim
change beyond `20260050` is needed (spec Amendment 1 A1.2). The `ft8_get_h12_ambiguous_padding_count()`
proposal recorded as a follow-up on the board is **not required** for this change and is out of
scope for it.

## Risks / Trade-offs

- **[Risk] `20260050` collision at build time.** This exact number is pre-registered as a hard
  ROW 0a gate value in the spec itself. **Mitigation:** do not substitute a different number even
  if `20260050` looks "taken" — STOP and escalate to the Architect/Captain instead (the same trap
  `dev-tasks/2026-09-03-shim-version-renumber-rc1rc2-and-rc4-branches.md`, filed the same day,
  exists to avoid repeating for two unrelated diagnostic branches).
- **[Risk] The new branch could silently perturb decode output despite being purely additive.**
  **Mitigation:** the required equality check (spec §5 ROW 0e, carried into this change's own
  task list) decodes an existing corpus on both the pre-change (`20260049`) and new (`20260050`)
  binaries and requires byte-identical output — the same check `f001-h12-unique-match-suppression`
  and `f001-sup-b-instrumented-suppression-sizing` both used to prove non-perturbation, not merely
  assume it from the branch being additive.
- **[Trade-off] This export is diagnostic-only and untested by the existing C# test suite** — by
  design (D2), since it has no managed caller. Its only verification is the ROW 0e byte-identity
  check (a Developer-session task) and QA's own later Python/ctypes ROW 0 rows (spec §5), not a
  `dotnet test` assertion. This is the same trade-off `f001-sup-b-instrumented-suppression-sizing`
  Phase 2 accepted for its own no-binding export.
- **[Non-risk, disclosed so it is not re-raised]** L3's sizing population is smaller than a naive
  `U_total` read would suggest, because of D5's padding contamination — this is a QA-side reading
  discipline (Amendment 1 A1.3: `U_clean < 500 ⇒ STOP`, not `U_total < 500`), not a defect in this
  change's own export, and does not block this change from shipping.

## Migration Plan

Same discipline as every prior native change on this file: a `FT8_SHIM_VERSION`/`ExpectedShimVersion`
bump, all reachable platform binaries rebuilt (Windows x64 and Linux x64 locally; macOS ARM64 on
CI's `macos-latest` leg, whose "could not rebuild here" warning on a Windows box is expected and
permanent, not a finding), zero production call sites added or changed, rollback is a plain
`git revert`. No reading leg (spec §5 ROW 0–3) may run before this change's own ROW 0e passes and
the Captain has reviewed the diff (HK-010) — QA's measurement arm is explicitly not part of this
change's own Definition of Done (tasks.md task 7).

## Open Questions

None outstanding for this change's own scope. (The retrofit-vs-upfront OpenSpec process question
`f001-sup-b-instrumented-suppression-sizing`'s own design.md left open (#3) is answered by this
change's existence: opened before the Developer session, not backfilled after.)
