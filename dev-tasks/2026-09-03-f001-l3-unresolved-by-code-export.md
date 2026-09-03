# Developer handoff: `ft8_get_h12_unresolved_by_code` — MEASURE-ONLY export for `F-001` L3 sizing

**Authored by:** QA, per HK-000/HK-011/HK-015. **Ordered by:**
`qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md` §3/§7 step 1
(Architect → QA, PO-ordered "spec L3 for QA"). Per HK-011, this document is a proposal, not
approved work — only the **Captain** opens a Developer session against it. The Developer runs
`opsx:apply` (build + tests only, **never** `pre_merge_check.py` — QA's own gate, HK-006). The
Captain reviews the `src/`/`native/` diff before any push or merge (HK-010/HK-014). QA does not
declare "ready for merge."

✅ **§0 RESOLVED, 2026-09-03 16:16Z — no longer blocking.** The PO ruled (Architect review of QA's
reports, re-verified from source): the gate is **`tls_h12_lookup_performed && !tls_h12_resolved`**
— §0.3/§0.4's mechanically-consistent reading, i.e. **build the FIRST §2.2 variant** (the one at
§2.2's top, gated on `tls_h12_lookup_performed && !tls_h12_resolved`). The literal
`tls_h12_multiplicity == 1` wording was the **Architect's own drafting slip** in spec §6's
parenthetical, not a considered PO choice of the (provably empty, per §0.2) alternative population
— it is withdrawn. **Do not build the second §2.2 variant** (the `&& tls_h12_multiplicity == 1`
one) at all; §0.4's "confirm before building" condition is now satisfied in favour of the first.
Full ruling: `qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md`
Amendment 1; board entry 2026-09-03 16:16Z, "RULING 2." **The rest of §0 below is kept verbatim as
the record of why the question was raised and how it was resolved — do not delete it.**

🔴 **§0 below was a BLOCKING precondition, not background reading, before the ruling above
landed.** QA found a numeric inconsistency in the PO's own ruling while preparing this handoff.
Implementing the literal wording as written would have built an export whose new counters are
mathematically guaranteed to always read zero (see §0.2), which would fail the dev-task's own
ROW 0g floor and waste a full rebuild-and-verify cycle for nothing.

**Behaviour change: NONE INTENDED to any existing production path.** The new export is
diagnostic-only, read-only, reachable only from a QA replay harness, and — per the spec's own
requirement — counts the complement of what `ft8_get_h12_by_code` already counts, at the same
emission site, changing no existing decode-path value.

---

## 0. 🔴 BLOCKING — the PO's stated gate (`tls_h12_multiplicity == 1`) cannot be satisfied by an unresolved lookup under the shim as it exists today

### 0.1 What the spec says

Spec §6/§6.1 (PO ruling, binding): *"L3's compare is gated on `tls_h12_multiplicity == 1`"* and
*"the new measure-only export `ft8_get_h12_unresolved_by_code` ... must itself honour the gate —
it counts an unresolved lookup only when that lookup's own `tls_h12_multiplicity == 1`."*

### 0.2 What the current shim actually computes (`ft8_shim.c:802-828`, `cb_lookup_hash`)

```c
bool found = hash_table_lookup(tls_hash_table, t, h, cs);   /* :804 */
if (t == FTX_CALLSIGN_HASH_12_BITS) {
    tls_h12_lookup_performed = true;
    tls_h12_resolved         = found;                        /* :807 */
    tls_h12_code             = h;                             /* :810 */
    if (found) {
        hash_table_count_h12_multiplicity(..., &tls_h12_multiplicity, ...);  /* :812 */
        tls_h12_suppressed = (tls_h12_multiplicity >= 2);      /* :819 */
    } else {
        tls_h12_multiplicity = 0;                              /* :821 — FORCED */
        tls_h12_suppressed   = false;                          /* :823 */
    }
}
return found && !tls_h12_suppressed;                           /* :826 */
```

`hash_table_lookup` (`:637-655`) and `hash_table_count_h12_multiplicity` (`:668-693`) walk the
**identical open-addressing probe chain** (same start index, same "stop at first empty slot"
termination). So whenever `hash_table_lookup` returns `found = false`, a multiplicity count over
that same probe chain is **provably also zero** — there is no entry in the table with that 12-bit
hash for `hash_table_count_h12_multiplicity` to find. This is why the code hardcodes
`tls_h12_multiplicity = 0` in the `else` branch (`:821`) instead of computing it: computing it
would always yield the same zero.

Conversely, `tls_h12_multiplicity == 1` (a genuine unique match, found and not ambiguous) only
ever occurs when `found == true` **and** `tls_h12_suppressed == false` — which makes
`cb_lookup_hash` return `true`. That is the **successful, resolved, displayed-with-a-real-name**
case (L2), the exact opposite of "unresolved."

**⇒ "unresolved AND `tls_h12_multiplicity == 1`" is the empty set under the current shim,
provably, not just empirically.** An export gated exactly as worded would compile, link, and pass
every mechanical ROW 0 identity/wiring check — and then report `U_total = 0` on every corpus,
which the spec's own **ROW 0g explicitly requires QA to read as an instrument failure, not a
null** (`U_total < 500` ⇒ STOP). QA would be pre-registered into re-discovering this defect the
hard way, on a rebuilt binary, after the fact.

### 0.3 What the PO's ruling almost certainly means, mechanically

Re-reading spec §6's own framing — *"gated to **exclude the suppressed subset**"* — the intent is
clearly about the **ambiguous/suppressed** population (`tls_h12_resolved == true &&
tls_h12_suppressed == true`, i.e. `tls_h12_multiplicity >= 2`), which Option A already suppresses
as unsafe (`78713b8`) and which spec §6 says L3 must not re-enable. The mechanically consistent
reading — the one that actually implements "exclude the suppressed subset" rather than "count
nothing at all" — is:

**Count a lookup in the new table iff `tls_h12_lookup_performed && !tls_h12_resolved`.**

Under the current shim, `!tls_h12_resolved` in that branch is **exactly** the population with
`tls_h12_multiplicity == 0` (never any candidate at all) — i.e. the gate the spec states as
`== 1` is mechanically equivalent, on this codebase, to `== 0`, and the "1" in the spec text is
QA's best read a drafting slip (parallel to the AWGN-FP arm's own ROW 2/ROW 3 drafting fault,
Amendment 1, found the same day) rather than a considered choice of a different, currently-empty
population. This reading also satisfies spec §6.1 item 3's own precondition check ("the gated and
ungated unresolved counts must both be reported ... their difference must be non-zero and
consistent with the corpus's known ambiguous count") — under `== 1`, gated would always be zero
and ungated non-zero, which item 3 flags as **the exact unwired-gate failure it exists to catch**;
under `!tls_h12_resolved`, gated = ungated minus the ~847 `s17m` suppressed lookups, matching
item 3's own worked expectation.

### 0.4 What QA did about it, and what the Developer should do — ✅ RESOLVED, see the top of §0

**QA did not unilaterally override the PO ruling.** This document was handed to the Captain
alongside a flag to re-confirm with the Architect/PO: *"exclude the suppressed subset" implemented
as `tls_h12_lookup_performed && !tls_h12_resolved` (⇔ `tls_h12_multiplicity == 0` given the
current shim) — confirm this is the intended population, since the literal `== 1` wording counts
nothing.* **That confirmation has now landed** (top of §0): build `tls_h12_lookup_performed &&
!tls_h12_resolved`, the **first** §2.2 variant. §2 below still specs the export **both ways**,
clearly labelled, kept for provenance — the Developer builds only the first variant; do not build
the second (`&& tls_h12_multiplicity == 1`) one.

---

## 1. What is already done — do not redo it

Nothing has been built. The spec's §0 trap (`ft8_get_h12_by_code`'s row 149 reading zero) is a
**different, already-shipped, already-understood** export (shim `20260048`) — do not touch it, do
not extend it, and do not read its zero as informative about L3 (spec §0.1, out of scope forever).
This task adds a **second, new** table on the complement branch.

## 2. What to build

**One new native export**, mirroring `ft8_get_h12_by_code`'s existing shape exactly
(`ft8_shim.c:1240-1252`, `ft8_shim.h:795-800`) but on the unresolved branch:

```c
int ft8_get_h12_unresolved_by_code(int* counts, int capacity, int* out_of_range);
```

### 2.1 New state (`ft8_shim.c`, alongside the existing tables at `:735-738`)

```c
static int g_h12_unresolved_by_code[H12_CODE_SPACE];   /* new */
/* g_h12_code_out_of_range (:738) is REUSED, not duplicated — it already counts
 * an out-of-range tls_h12_code regardless of which branch observed it, and the
 * spec's ROW 0c reads it as a single wiring-violation signal across both tables. */
```

### 2.2 New emission-site branch (`ft8_shim.c`, immediately after the existing `if` block that
ends at `:1667`, same `if (tls_h12_lookup_performed...)` guard family, same scope, same "count
DISPLAYS not decode attempts" discipline as the TRAP-3 comment at `:1648` already documents)

**✅ CONFIRMED (§0 top) — build this branch** (the mechanically-consistent reading):

```c
} else if (tls_h12_lookup_performed && !tls_h12_resolved) {
    /* F-001 L3 sizing (shim 20260050): the complement of the branch above.
     * PO ruling (spec §6.1): count only the "exclude the suppressed subset"
     * population -- under this shim, !tls_h12_resolved already IS that
     * population (tls_h12_multiplicity is unconditionally 0 here, see
     * cb_lookup_hash's else branch, :820-823 -- a suppressed/ambiguous match
     * always has tls_h12_resolved == true and lands in the OTHER branch). */
    if (tls_h12_code >= H12_CODE_SPACE) g_h12_code_out_of_range++;
    uint32_t c = tls_h12_code & (H12_CODE_SPACE - 1u);
    g_h12_unresolved_by_code[c]++;
}
```

**NOT to be built — kept for provenance only.** The literal `tls_h12_multiplicity == 1` wording
was the Architect's own drafting slip (§0, top), not a considered choice of the alternative,
currently-empty population — the variant below (adding `&& tls_h12_multiplicity == 1` to the
`else if` condition above) is **withdrawn** and must not be implemented.

### 2.3 New getter (`ft8_shim.c`, immediately after `ft8_get_h12_by_code`, `:1252`)

```c
/*
 * ft8_get_h12_unresolved_by_code -- F-001 L3 sizing (shim 20260050). Copies
 * the 4096-row per-code UNRESOLVED table -- the complement of
 * ft8_get_h12_by_code's DISPLAYING table, gated per spec Sec.6.1 (see the
 * emission-site comment above for exactly what "gated" means here). Same
 * signature/capacity/NULL contract as ft8_get_h12_by_code. Read-only,
 * process-lifetime cumulative, zero on daemon restart. Intended caller is
 * QA's Python replay harness (g3_h12_replay.py, extended per spec Sec.7
 * step 3) by ctypes, once per run -- not IFt8NativeInterop, matching
 * ft8_get_h12_by_code's own precedent (see that getter's comment for why).
 */
int ft8_get_h12_unresolved_by_code(int* counts, int capacity, int* out_of_range)
{
    if (!counts || !out_of_range || capacity < H12_CODE_SPACE)
        return -1;
    for (int c = 0; c < H12_CODE_SPACE; c++)
        counts[c] = g_h12_unresolved_by_code[c];
    *out_of_range = g_h12_code_out_of_range;
    return H12_CODE_SPACE;
}
```

### 2.4 Header declaration (`ft8_shim.h`, immediately after `ft8_get_h12_by_code`'s declaration,
`:800`) — doc comment matching the `:795-800` block's own style, plus a new changelog entry
(pattern in `:660-679`) for `20260050`:

```c
/*
 * ft8_get_h12_unresolved_by_code -- F-001 L3 sizing (shim 20260050). See
 * ft8_shim.c for the exact gating condition. Same capacity/NULL contract as
 * ft8_get_h12_by_code. Returns H12_CODE_SPACE (4096) on success, -1 on any
 * bad argument.
 */
int ft8_get_h12_unresolved_by_code(int* counts, int capacity, int* out_of_range);
```

### 2.5 No decode-path change, no C# binding

Nothing in `hash_table_lookup`, `hash_table_add`, `cb_lookup_hash`'s return value, or any existing
struct/export changes. `ft8_get_h12_by_code` and its three SUP-B scalar getters are untouched —
this is purely additive. Per spec §3's own precedent for the sibling resolved-branch export
(`ft8_get_h12_by_code`), **no `IFt8NativeInterop`/`Ft8LibInterop.cs` binding is needed** — the
caller is QA's own ctypes replay harness. Do not add one.

### 2.6 Version bump and build

- `FT8_SHIM_VERSION` `20260049` → **`20260050`**. This exact number is pre-registered as a hard
  ROW 0a gate value in the spec itself (§5: *"Built DLL's `ft8_lib_version_check()` ≠ `20260050`
  ... Wrong binary. STOP."*) — do not pick a different number even if `20260050` looks "taken" by
  something else at build time; if it genuinely collides, STOP and escalate rather than
  substituting (this is the same trap the shim-renumber dev-task, filed the same day, exists to
  avoid repeating).
- Windows: add `/EXPORT:ft8_get_h12_unresolved_by_code ^` to `rebuild_shim.bat`'s explicit export
  list (pattern: the `ft8_get_h12_by_code` entry already there). Linux: no change (default
  visibility). Verify the export is present in the built DLL mechanically (`dumpbin /exports`),
  not inferred from a successful build.
- Rebuild every platform binary you have toolchain access to; record each SHA256 honestly — this
  SHA256 becomes the pin QA asserts in ROW 0a of the L3 measurement arm.
- `dotnet build` — 0 warnings. `dotnet test` — full suite green (no new C# surface to test per
  §2.5, but the shim-version pin (`Ft8LibInterop.ExpectedShimVersion`) **must** be bumped to
  `20260050` in the same commit, matching the standing "stale pin fails `LoadAndVerify` at
  startup" caution from the `20260045` precedent).
- Update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`'s CURRENT block (pattern at
  `:660-679`'s prose style) — new export, MEASURE-ONLY, no decode-path change, cites this document
  and the spec.

### 2.7 The one required equality check before handoff (spec §5 ROW 0e)

**Decode a small existing corpus (any already-captured leg is fine) on both the pre-change binary
(`20260049`) and the newly built one (`20260050`), same audio, and diff the emitted decode lines.**
They must be **byte-identical**. This is spec ROW 0e, and the spec calls it *"the one that matters
most and the only one that catches the error the others cannot"* — every other check in this
document passes whether or not the new counter perturbed decoding; only this one proves it did
not. Run it yourself before handoff; QA re-runs it independently as part of the measurement arm,
but a Developer-side failure caught here is much cheaper than one caught downstream.

---

## 3. Acceptance criteria (what QA checks on review)

- §0's confirmation (recorded at the top of §0 in this document, 2026-09-03) is cited in the PR
  description, naming the built variant (the first §2.2 variant, `tls_h12_lookup_performed &&
  !tls_h12_resolved`) and confirming the second variant was not built.
- `ft8_get_h12_unresolved_by_code` exists, matches `ft8_get_h12_by_code`'s signature/NULL/capacity
  contract exactly, is declared in `ft8_shim.h` alongside its sibling.
- The new emission-site branch is the **complement** of the existing `if` at `:1650` by
  construction (an `else if` on the same guard family, not a second independent `if` that could
  double-count or race) — mechanical diff review, not eyeballed.
- No existing function, struct, or export's behaviour changed — mechanical diff of everything
  outside the new state/branch/getter/header-declaration/version-line/export-list/version-file.
- `FT8_SHIM_VERSION` is `20260050` exactly (not substituted), asserted unused as a wiring
  precondition, SHA256 of every rebuilt binary recorded honestly.
- ROW 0e (§2.7) run and **byte-identical** — a non-zero diff is a STOP condition for the Developer
  session, not something to report and hand off anyway.
- `dotnet build`/`dotnet test` green, `ExpectedShimVersion` bumped in the same commit as the
  native version.
- **QA then runs the spec's own §5 ROW 0 (a–g) and §6.1 item 3's precondition, then ROW 1–3.**
  Those runs are QA's, not the Developer's, and are not part of this handoff's Definition of Done.

**Not this session's to decide:** whether L3 itself (the runtime compare-and-respond behaviour)
ever ships. This export is MEASURE-ONLY (spec §8) — building it is not a licence to build the
comparator.

---

**References:**

- `qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md` — the
  operative spec (§2 hash derivation, §3 export shape, §4 measurement definitions, §5 ROW 0-3
  gate, §6/§6.1 the PO ruling this document's §0 flags, §7 QA's own ordered steps).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:637-693` (`hash_table_lookup`,
  `hash_table_count_h12_multiplicity`), `:794-828` (`cb_lookup_hash`, the TLS state §0.2 traces
  through), `:1240-1252` (`ft8_get_h12_by_code`, the export this mirrors), `:1650-1667` (the
  emission site the new branch attaches to).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:644-679` (changelog convention), `:795-800`
  (`ft8_get_h12_by_code` declaration, the pattern §2.4 mirrors).
- `dev-tasks/2026-09-03-shim-version-renumber-rc1rc2-and-rc4-branches.md` — filed the same day,
  the reason `20260050` must never be substituted for a different number.
- `qa/rr-study/f001-d3-arm1/common_arm1.py` — the independent `n12_of`/`n22_of` implementation
  QA cross-checked `PD2FZ` → `n12=149` against (spec §2); not touched by this task.
- Licence discipline unchanged: WSJT-X source may be read for method only; no line copied,
  transliterated, or ported (Captain's ruling, 2026-08-11).
