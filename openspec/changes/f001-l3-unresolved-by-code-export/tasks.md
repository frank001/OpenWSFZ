*Process note: tasks 1–6 are the **Developer session's** (HK-011 — a `src/`/`native/` change is not
QA's to start; QA authored the underlying content in
`dev-tasks/2026-09-03-f001-l3-unresolved-by-code-export.md`, whose §0 blocking question is already
resolved — build the gate exactly as design.md Decision D1 states, do not re-litigate it). Task 7
is a hard stop for the **Captain** (HK-010) — green build/tests is necessary, never sufficient.
Tasks 8–9 are the **spec-sync + housekeeping** pass, done once the Captain has ruled, following
`f001-h12-unique-match-suppression`'s own tasks.md structure (groups 10–11 there). **QA's own L3
measurement arm (spec `qa/rr-study/2026-09-02-1631-…-f001-l3-own-hash-compare-sizing.md` §5, ROW
0–3) is explicitly NOT part of this change's Definition of Done** — proposal.md's own Impact
section states this; it is a separate, later QA arm reading the export this change ships.*

## 1. Native Shim — the unresolved-by-code table

- [ ] 1.1 Add the new fixed 4,096-row state array, alongside the existing per-code table
      (`ft8_shim.c`, near `:735-738`):
      ```c
      static int g_h12_unresolved_by_code[H12_CODE_SPACE];   /* new */
      /* g_h12_code_out_of_range is REUSED, not duplicated — see design.md D3. */
      ```
- [ ] 1.2 Add the new emission-site branch as an `else if` on the **same guard family** as the
      existing `if (tls_h12_lookup_performed...)` block (immediately after it, same scope), never
      a second independent `if` (design.md D4):
      ```c
      } else if (tls_h12_lookup_performed && !tls_h12_resolved) {
          /* F-001 L3 sizing (shim 20260050): the complement of the branch above.
           * PO ruling (board, 2026-09-03, "RULING 2"; design.md D1): count only
           * "exclude the suppressed subset" -- under this shim,
           * !tls_h12_resolved already IS that population (tls_h12_multiplicity
           * is unconditionally 0 here; see cb_lookup_hash's else branch,
           * ft8_shim.c:820-823 -- a suppressed/ambiguous match always has
           * tls_h12_resolved == true and lands in the OTHER branch). */
          if (tls_h12_code >= H12_CODE_SPACE) g_h12_code_out_of_range++;
          uint32_t c = tls_h12_code & (H12_CODE_SPACE - 1u);
          g_h12_unresolved_by_code[c]++;
      }
      ```
- [ ] 1.3 Add the new getter, immediately after `ft8_get_h12_by_code`:
      ```c
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
- [ ] 1.4 Add the header declaration (`ft8_shim.h`, immediately after `ft8_get_h12_by_code`'s own
      declaration), doc comment matching that block's own style.
- [ ] 1.5 Confirm by inspection that `hash_table_lookup`, `hash_table_add`, `announce_stamp`,
      `cb_lookup_hash`'s return value, and `ft8_get_h12_by_code`'s own table/counters are
      byte-for-byte unchanged — this task is purely additive.

## 2. Native Shim — Version Bump

- [ ] 2.1 `FT8_SHIM_VERSION` `20260049` → **`20260050`** (this exact number is pre-registered as a
      hard ROW 0a gate in the L3 spec — do not substitute a different one even if it looks "taken"
      at build time; STOP and escalate instead, per design.md's own Risk note). Add a changelog
      entry (pattern in `ft8_shim.h`'s existing history block) stating plainly this bump is
      MEASURE-ONLY.

## 3. Binary Rebuild

- [ ] 3.1 Windows: add `/EXPORT:ft8_get_h12_unresolved_by_code ^` to `rebuild_shim.bat`'s explicit
      export list (pattern: the `ft8_get_h12_by_code` entry already there). Linux: no change
      (default visibility).
- [ ] 3.2 Rebuild every platform binary you have toolchain access to (Windows x64, Linux x64
      locally). Verify the export is present in the built DLL mechanically (`dumpbin /exports` /
      `nm -D`), not inferred from a successful build. Record each SHA256 honestly — this becomes
      the pin QA asserts in ROW 0a of the later L3 measurement arm.
- [ ] 3.3 macOS ARM64 — deferred to CI's `macos-latest` leg, per standing project policy (not a
      finding to raise). Update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`'s CURRENT
      block to record this.

## 4. Managed Interop — confirm NO changes, do not add a binding

- [ ] 4.1 `ExpectedShimVersion` `20260049` → `20260050` in `Ft8LibInterop.cs` — the **only**
      managed-code change this task list requires.
- [ ] 4.2 Confirm, by diff review (not by running tests), that `IFt8NativeInterop.cs`,
      `Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`, and every existing
      `IFt8NativeInterop` test-double implementer are **untouched** beyond the one version-constant
      edit in 4.1 (design.md D2; `ft8lib-interop` spec delta's own "No managed binding exists"
      scenario). Do **not** add `ft8_get_h12_unresolved_by_code`/`GetH12UnresolvedByCode` to any of
      them.

## 5. Build and Test (Developer session)

- [ ] 5.1 Full solution build, Release, 0 warnings.
- [ ] 5.2 Full test suite green (no new C# surface to test per task 4 — confirm no regressions).
- [ ] 5.3 `openspec validate --strict --all` passes with this change present.

## 6. The one required equality check before handoff (spec §5 ROW 0e)

- [ ] 6.1 🔴 **Decode a small existing corpus (any already-captured leg is fine) on both the
      pre-change binary (`20260049`) and the newly built one (`20260050`), same audio, and diff the
      emitted decode lines. They MUST be byte-identical.** This is the check that proves the new,
      purely-additive branch did not perturb decode output — every other check in this task list
      passes whether or not it did; only this one catches the error the others cannot (the same
      reasoning `f001-h12-unique-match-suppression` and `f001-sup-b-instrumented-suppression-sizing`
      both used their own equivalent checks for). Run it yourself before handoff; QA re-runs it
      independently as part of the later L3 measurement arm's own ROW 0, but a Developer-side
      failure caught here is much cheaper than one caught downstream.

## 7. Captain

- [ ] 7.1 🛑 **HARD STOP.** No push, no merge, no `pre_merge_check.py` (HK-006/HK-011 — Captain's
      initiative only). The Captain reviews the diff together with task 6's result and rules on the
      merge (HK-010) — green build/tests is necessary and never sufficient.

## 8. Spec Sync

- [ ] 8.1 🔴 **Check the archive ordering first.** Confirm no other unarchived change touches
      `hashed-callsign-resolution` or `ft8lib-interop` ahead of this one (this change's deltas are
      written against the current, already-synced base specs — both capabilities' base spec files
      already carry every prior change through `20260049`, confirmed at drafting time).
- [ ] 8.2 Merge this change's `specs/hashed-callsign-resolution/spec.md` delta into
      `openspec/specs/hashed-callsign-resolution/spec.md` (one new ADDED Requirement, appended
      after the existing "Suppression is observable..." Requirement).
- [ ] 8.3 Merge this change's `specs/ft8lib-interop/spec.md` delta into
      `openspec/specs/ft8lib-interop/spec.md` — the ABI self-test Requirement's expected constant
      advances to `20260050` (following that Requirement's own established pattern of preserving
      full prior history in its paragraph prose, not truncating it); the new "Diagnostic 12-bit
      hash-path unresolved-by-code native export" Requirement is appended after the existing
      12-bit-suppression-count Requirement.
- [ ] 8.4 `openspec validate --strict --all` passes after both merges.
- [ ] 8.5 Archive this change (`opsx:archive` / `openspec archive`).

## 9. Housekeeping

- [ ] 9.1 Update `BOARD.md` (and `MEMORY.md`'s one-line index) in the **same edit** as the merge
      result (HK-024) — record the new pinned SHA256 for shim `20260050` and that the L3
      measurement arm is now unblocked (but not yet run).
- [ ] 9.2 Branch hygiene (HK-003): delete the merged branch and any worktree created for this
      change.
- [ ] 9.3 Confirm the archived change validates after archiving
      (`openspec validate --strict --all`).
