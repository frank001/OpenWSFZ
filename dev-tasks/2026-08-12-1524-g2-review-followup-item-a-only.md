# Developer handoff: G2 review follow-up — ship item (a) alone, take item (b) off the branch

**Authored by:** QA, 2026-08-12 (15:24 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Follows:** the QA code review of `feat/g2-hash-table-sizing-and-candidate-passband` (2026-08-12).
**Status:** 🔴 **Proposal, not approved work in itself (HK-011).** A separate Developer session runs
`opsx:apply` (build + tests only — never `pre_merge_check.py`, that is HK-006, the Captain's
initiative alone). The Captain reviews the diff before any push or merge (HK-010/HK-014). QA does
not declare readiness.

---

## 0. The decision this implements

The Captain ruled on 2026-08-12: **merge item (a); hold item (b).**

Item (a) is clean — recall provably unmoved (4841 vs 4841 physical decodes, zero differences either
way), rejects 4437 → 0, `<...>` rate 5.51% → 4.01% — and it **improves the instrument** R0/R1/R2
will be scored with, since `<...>` rows cannot match by text (H1: `M` = 2.26 pp of matching effect).

Item (b) returns as its own pre-registered arm:
`qa/cycleframer-alignment-replay/2026-08-12-1524-qa-to-architect-prereg-g2b-passband-decomposed.md`.
**Nothing is discarded** — the +131 from the intended mechanism is real and the branch keeps the
measurement.

---

## 1. Branch handling — do NOT rewrite history

`3f29b3d` (item a) and `79ea12a` (item b) are **unpushed but reviewed**. Leave both in place.

- **Create `feat/g2a-hash-table-sizing` from `3f29b3d`.** One follow-up commit on top carries
  everything in §2–§4. The Captain then reviews a small, legible diff rather than a rebase.
- **Leave `feat/g2-hash-table-sizing-and-candidate-passband` exactly as it is**, as the record of
  the item (b) measurement. The passband pre-registration references it.

🔴 **Do NOT rebuild the DLL.** Every change below is a comment, a document, or a test. The shipping
binary must remain **byte-identical** to `3f29b3d`'s blob:

```
SHA256  c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112
```

**Verify this mechanically in the follow-up commit** (`git diff 3f29b3d -- …/libft8.dll` must be
empty). The item (a) evidence is pinned to that exact binary; a gratuitous rebuild would move the
PE `TimeDateStamp` and detach the measurement from the artefact for no gain.

*(For reference: `main` is `f2f30c89…`; the item (a)+(b) binary on the old branch is `a5156c21…`.)*

---

## 2. 🔴 R1 — the shipped binary must not claim a change it does not contain

Commit `3f29b3d` documents **item (b)** in three places despite not implementing it. This is what
defeated the spec's §0 requirement that the two commits be separately revertible, and it now
matters directly: with (b) held, these files would ship describing a passband the code does not use.

Remove or rewrite, so that shim **20260038 describes item (a) and only item (a)**:

| file | what to fix |
|---|---|
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h:~304` | the `20260038` history block — drop the `(b)` passband paragraph; drop "two independent native constant changes, shipped together" |
| `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:~231` | same: drop the `(b)` paragraph from the `ExpectedShimVersion` doc |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:~361` | the file-header `g2-…` block — drop the `Item (b)` paragraph |
| `libft8.version.txt` | drop the `(b)` text; the line *"ONE version bump covers both item (a) and item (b)"* is now false |
| `src/OpenWSFZ.Ft8/Native/BUILD.md` | 🔴 **revert the `monitor_config_t` literal and its prose to `200.0f` / `3000.0f`** — this file currently documents the widened band, which the shipped code does not have |

**Rename the change throughout** from `g2-hash-table-sizing-and-candidate-passband` to
**`g2a-hash-table-sizing`**, including the version.txt heading.

**Keep `FT8_SHIM_VERSION = 20260038`** and keep the reservation note that 20260039–20260041 belong
to R0/R1/R2. That reasoning stands regardless of item (b).

---

## 3. R3 — the waterfall bin count is arithmetically wrong

`monitor_init` (`native/ft8_lib_build/patched/common/monitor.c:102-105`) computes:

```c
me->min_bin = (int)(cfg->f_min * symbol_period);        /* symbol_period = 0.16 */
me->max_bin = (int)(cfg->f_max * symbol_period) + 1;
num_bins    = max_bin - min_bin;
```

At `[200, 3000)`: `min_bin = 32`, `max_bin = 481` ⇒ **449 bins, not 448**. Correct the figure
wherever it appears (`BUILD.md`, and any shim comment quoting it) and adjust the heap estimate to
match.

⚠️ **This is pre-existing on `main`, not introduced by G2** — the Developer inherited 448 and
carried it forward. It is cosmetic. Fix it because we are in the file anyway, and note in the commit
message that it is a pre-existing correction so it is not misread as a G2 defect.

*(For the record, and for the item (b) arm: at `[140, 3030)` the true count is **463**, and the
realised band is `[137.5, 3031.25)` after bin quantisation — slightly wider than nominal, so the
99.90% coverage claim was conservative rather than overstated.)*

---

## 4. Test changes

### 4.1 🔴 T1 — relax the zero-tolerance decode assertion

`HashedCallsignResolutionTests.HashTableSizing_264DistinctCallsigns_AllResolveWithZeroRejects`
currently asserts:

```csharp
resolved.Count.Should().Be(totalAttempts);   // exactly 264
```

That demands **264 of 264** synthetic decodes succeed across 33 batched native calls, with zero
tolerance, on every CI run. The assertion it replaced (`BeLessThan(264)`) was inherently robust to a
single marginal synthesis; this one is not.

**The reason for concern is the Developer's own item (b) evidence:** widening the waterfall
perturbed in-band SNR and candidate ordering enough to cost 125 real decodes. Whatever margin these
synthetic decodes have, it is demonstrably not infinite, and one green suite run is thin evidence
for a zero-tolerance bar.

**Change to a floor that still proves the fix:**

```csharp
resolved.Count.Should().BeGreaterThanOrEqualTo(260,
    "at HASH_TABLE_SIZE = 4096 essentially all 264 distinct callsigns must be stored AND " +
    "resolve. At the previous 256 they provably could not: (h10 * 23) % 256 collides 4:1 by " +
    "construction, so at least 8 were rejected. A floor of 260 clears that old ceiling " +
    "decisively while tolerating a single marginal synthetic decode; a shortfall below it " +
    "means the sizing change did not take effect (stale libft8.dll?) or first-probe " +
    "placement regressed");
```

**Keep `(rejectsAfter - rejectsBefore).Should().Be(0)` exactly as it is** — that is the assertion
that actually proves the sizing fix, it is a native counter rather than a decode outcome, and it has
no flakiness surface.

### 4.2 T3 — pin `F005RealCorpusSaturationCheck` to the saturation collection

`tests/OpenWSFZ.Ft8.Tests/F005RealCorpusSaturationCheck.cs:53` carries **no `[Collection]`
attribute**, so it is not pinned last. It replays a real corpus and can consume large numbers of
table entries. The old `>= 8` assertion was robust to that; the new `Be(0)` reject-delta assertion
is not.

Add:

```csharp
[Collection(HashTableSaturationCollectionDefinition.Name)]
public sealed class F005RealCorpusSaturationCheck
```

Low likelihood (it needs `OPENWSFZ_RUN_F005_CORPUS_REPLAY=1` *and* the corpus on disk), one-line
fix, removes the coupling entirely.

### 4.3 T2 — record the coverage reduction, do not try to solve it

No code change requested. The opt-in `HashTableSaturation_AtG2Capacity_…` test correctly follows the
Captain-approved `F005RealCorpusSaturationCheck` precedent, and moving the coverage was plainly
better than dropping it. But state plainly in the commit message that the **D3 reject-when-full
guard and D-012's original full-table condition are now unexercised in the default suite and in
CI** — that is a genuine reduction in standing coverage, not a like-for-like relocation, and the
Captain should be able to see it without reading a doc comment to find it.

---

## 5. 🔴 E1/HK-022 — re-run and KEEP the item (a) evidence

The three replay JSONs from the original session are **nowhere on disk**. Every figure in the commit
messages and in `version.txt` is currently unverifiable, and I cannot confirm the green result
covered what it claims (HK-022).

This is cheap to close — at 0.571 s/cycle, 250 cycles is roughly five minutes of decode per leg.

1. Re-run **two legs only** with `g2_verification_replay.py`, against the two *committed* binaries:
   - baseline: `main`'s `f2f30c89…`
   - item (a): `3f29b3d`'s `c559a049…`
2. Run `g2_verification_report.py` over them and confirm the published item (a) numbers reproduce:
   **decode count unchanged, zero physical differences either way, rejects → 0, `<...>` rate
   5.51% → 4.01%.**
3. 🔴 **Gather the JSONs and the report output into a dated `artefacts/` directory with a
   `README.md`** (HK-016). `artefacts/` is blanket-gitignored, so the message text inside the JSONs
   is safe — **NFR-021: only counts and rates may be quoted upward or into any commit message.**
4. If the numbers do **not** reproduce, **stop and report.** Do not adjust the published figures to
   match a fresh run.

---

## 6. Working tree — clear both before starting

- **`qa/cycleframer-alignment-replay/p23_common.py`** — an uncommitted `load_ref()` sort fix,
  labelled an "R0 D3 fix". It is the **correct** fix for the known hash-randomisation defect
  (`a.keys() & b.keys()` iterates per-process-randomly, so a fixed `random.Random(seed)` still
  draws different indices), but R0 has not been run and this is outside G2's scope. **Commit it
  separately, on its own branch, with its own justification** — do not let it ride along. ⚠️ Note
  in that commit that it changes `ref` insertion order, so P2/P3/P1a's determinism claims remain
  **unverified** until mechanically diffed, never merely asserted.
- **`--help`** — a stray 2-byte file at the repo root from a shell redirect accident. Delete it.

---

## 7. Definition of done

- [ ] `feat/g2a-hash-table-sizing` branched from `3f29b3d`; the old branch left intact
- [ ] R1 complete — no shipped file claims the passband change; renamed to `g2a-hash-table-sizing`
- [ ] `BUILD.md`'s `monitor_config_t` reverted to `200.0f` / `3000.0f`
- [ ] R3 complete — 449 bins, flagged as a pre-existing correction
- [ ] T1 floor at 260; the `Be(0)` reject assertion untouched
- [ ] T3 collection attribute added
- [ ] **DLL byte-identical to `c559a049…`** — verified, not assumed
- [ ] Build clean (0 warnings); full `OpenWSFZ.Ft8.Tests` suite green; report the count
- [ ] Item (a) evidence re-run, reproduced, and gathered into `artefacts/`
- [ ] `p23_common.py` committed separately; `--help` deleted
- [ ] T2 coverage reduction stated in the commit message

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No
`pre_merge_check.py` (HK-006).

---

## 8. 🔴 Board consequence, if item (a) merges

Every R0/R1/R2 spec currently pins `f2f30c89…` / shim **20260033**. On merge those pins name a
binary that is no longer `main`'s and **must be re-pinned to `c559a049…` / shim 20260038 before R0
resumes.** Update `BOARD.md` in the **same edit** as the merge (HK-024) — not later, and not in a
topic file only.
