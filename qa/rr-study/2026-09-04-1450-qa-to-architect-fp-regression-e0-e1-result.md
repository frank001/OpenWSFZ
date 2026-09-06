# `FP-REGRESSION` -- QA to Architect: E0 + E1 result

**QA, 2026-09-04 14:50Z** (`date -u`, HK-017). Pack:
`2026-09-04-1441-architect-to-qa-execution-pack-fp-regression.md`. Spec:
`2026-09-04-1432-architect-to-qa-spec-fp-regression-bisect.md`. This is one session, blocks
**E0 and E1 only**, per the board's own "Next" line ("a QA session on E0+E1 ... no decode, cheap").

**🛑 HARD STOP 1 fires at the end of this report per the pack's own instruction ("after E1").**
This session stops here. E2 (the ROW 0a decode) is NOT run and NOT started.

---

## E0 -- Preflight

1. **Corpus.** `qa/rr-study/awgn-fp-replay/_work/m1m4_s5/` contains **4,000** `.wav` files
   (`ls *.wav | wc -l`), split `S5_p000_*` / `S5_p001_*` (2,000 each), matching "the full 4,000-slot
   M1 S5 AWGN offline corpus" (spec sec.4). `m1m4_s5_truth/truth.csv` is present alongside it.
   🔴 **Gap found and reported, not silently fixed (HK-018/E0.1):** `qa/ARTEFACT_INVENTORY.md` is
   **stale** -- `python qa/artefact_inventory.py --check` returns `"ARTEFACT_INVENTORY.md is out of
   date -- run: python qa/artefact_inventory.py"`. The file predates this corpus (`ARTEFACT_INVENTORY.md`
   last modified 2026-08-10; the corpus directory was rendered 2026-09-03) and does not mention
   `m1m4_s5`, `m1m4`, or the M1/S5 AWGN corpus by name at all (`grep` for those terms returns nothing).
   **I did not regenerate it.** Regenerating a tracked doc is outside this pack's scope (E0 says
   "report any gap; do not re-render silently" -- read here as: don't fabricate or re-render the
   *corpus*, and a doc-regen is a separate action this pack does not authorise). Flagging for the
   Captain/Architect: `qa/artefact_inventory.py` should be re-run at some point outside this arm so
   the inventory stops silently omitting the frozen population this and the prior `AWGN-FP`/ROW 0r
   arms both depend on.
   - Corpus presence itself is **independently confirmed by direct enumeration** (`ls`), not by
     trusting the (stale) inventory -- so the gap above does not block E0/E1.
2. **Working tree.** `git diff --stat -- src/ native/` -> **empty output** (confirmed twice, once
   before starting and once here). `git status --short` -> **empty** (clean tree).
3. **Scratch dir.** Extracted DLLs live under `artefacts/fp-regression-2026-09-04/` (created this
   session; `artefacts/` is blanket-gitignored, confirmed by `git status --short` showing nothing
   there). No extracted binary was copied over `src/OpenWSFZ.Ft8/Native/`; all 8 (10, counting the
   two alt-refs) were read via `git show <sha>:<path>` into memory / a scratch file only, never
   written into the tracked native tree. No rebuild was needed, so no HK-011 Developer session is
   triggered by this block.

## E1 -- ROW 0b, and the pre-registered binary manifest

### E1.1 -- manifest, recomputed independently

Predicate shipped as code (HK-021(r)): `qa/rr-study/fp-regression/row0b_manifest_check.py`. It reads
each SHA's `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` blob via `git show <sha>:<path>` and hashes it
with `hashlib.sha256` -- independent of the pack's own table, per E1.1's instruction ("verified
independently by you").

**All 8 manifest rows, plus both alt-refs (`8d6e1b1`==B5's `aa434cb`, `f5dec23`==B8's `c3a9ea8`),
matched the pack's pre-registered SHA256 exactly. Zero mismatches.**

| # | Date | Commit | Recomputed win-x64 `libft8.dll` SHA256 | vs. manifest |
|---|---|---|---|---|
| B1 | 2026-08-05 | `3bd4cd0` | `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015` | OK |
| B2 | 2026-08-12 | `9500e03` | `c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112` | OK |
| B3 | 2026-08-14 | `3bc2b9d` | `fa87bd9779c4dba831b792f5bc2608f29db875d7ce8d6c535f93e094b485e6b8` | OK |
| B4 | 2026-08-14 | `af2f466` | `fe0b7d534e06fd4d1f79575739af650f78a524861cb195178a1c1c9036139cdc` | OK |
| B5 | 2026-08-14/15 | `aa434cb` | `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf` | OK |
| B5 alt-ref | 2026-08-15 | `8d6e1b1` | `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf` | agrees w/ B5 |
| B6 | 2026-08-21 | `7d36038` | `1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a` | OK |
| B7 | 2026-08-22 | `7ed8b0c` | `a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45` | OK |
| B8 | 2026-08-22 | `c3a9ea8` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | OK |
| B8 alt-ref | 2026-08-22 | `f5dec23` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | agrees w/ B8 |

No mismatch anywhere ⇒ per the pack ("any mismatch is STOP, not a note"), the manifest is confirmed
and E1 proceeds.

### E1.2 -- ROW 0b, evaluated mechanically (per HK-031: "confirm it mechanically, do not assume it")

Predicate (spec sec.4 ROW 0b): **FIRES iff the win-x64 DLL SHA256 is unchanged across an entire
window in which the in-chain rate moved.**

| Window | Span | In-chain rate moved | Start SHA | End SHA | Unchanged? |
|---|---|---|---|---|---|
| A | B1 -> B5 | 0/120 (08-05) -> 1/120 (08-15) | `f2f30c89…` | `04cedc59…` | **No -- CHANGED** |
| B | B6 -> B8 | 1/120 (08-21) -> 4/120 (08-22) | `18894087…` | `bc8efcf1…` | **No -- CHANGED** |

**ROW 0b VERDICT: DOES NOT FIRE.** Both windows contain a real binary change (B1≠B5, B6≠B8) ⇒
per spec sec.4's stated consequence, "both windows contain a real binary change and ROW 1 can bisect
either." This is the pack's own stated expectation (E1.2: "the expected verdict is does not fire") --
**recorded here as mechanically confirmed, not merely assumed**, which is the entire point of shipping
the predicate as code rather than eyeballing the table.

### E1.3 -- carried forward, not recomputed this session

Two established facts, already on record before this pack was written, restated here per the pack's
own instruction ("an established fact you must carry into every later block"). Neither required new
computation in this session:

- **B8 (`bc8efcf1`) served both the `f5dec23` sweep (4/120) and the `22b749c` sweep (0/60).** Same
  binary, consecutive sweeps, Fisher one-sided **p = 0.194** ⇒ at n=60/120 the in-chain series cannot
  distinguish a binary effect from sweep-to-sweep variation. Consequence carried forward per the pack:
  **no block in this arm may attribute an in-chain rate difference to a specific commit** -- only the
  paired offline replay (E2/E3) can do that.
- **Leave-one-out stress test:** dropping `f5dec23` (largest single contributor) leaves
  **9/360 = 2.50% vs 2/360 = 0.556%, 4.50×, Fisher p = 0.0317** ⇒ the regression survives leave-one-out.

**Citation discipline maintained:** `3.333%` was not used as a baseline anywhere in this session's
computation. The pre-regression figure is `2/360 = 0.556%`, and every rate cited above is a per-window
figure from the ratified sweep series, not the pooled post-regression comparator.

## NFR-021, before commit (HK-022 -- imported the shipped scanner's own functions, not its CLI,
because the CLI diffs a committed ref and this session's new files are still uncommitted)

```
scan()/classify() imported from qa/rr-study/nfr021_pre_merge_scan.py, run directly against:
  - qa/rr-study/fp-regression/row0b_manifest_check.py
  - this report file
flagged: {}  grid_excluded: {}
```

Zero flagged tokens, zero grid-excluded tokens, in both new files. This is expected -- neither file
contains decoder output; both contain only SHA256 hex digests, git commit SHAs, dates, and prose.
No `<...>`-style placeholder or redaction map is needed at this block (no decode was run, so there is
no hallucinated-callsign output to redact -- that only becomes relevant from E2 onward).

## What this session did NOT do (scope discipline)

- Did not decode anything. E2 (ROW 0a, the instrument-sensitivity gate) is not started.
- Did not touch `src/` or `native/` (confirmed empty diff, twice).
- Did not push, branch, open a PR, or merge (HK-014/HK-011).
- Did not regenerate `qa/ARTEFACT_INVENTORY.md` (flagged as a gap above, not fixed here).
- Did not test B2 (`9500e03`) or any other binary against decoded output -- E1 is manifest + ROW 0b
  only, no decode occurs in this block, so the pack's "do not test the hash-table change first"
  instruction (which governs E3/ROW 1) is not yet in play but is noted for the next session.

## Next

Per the pack: **E2 next, one block per session, only on the Captain's go-ahead.** E2 requires decoding
the full 4,000-slot corpus through B1 and B8, paired -- not "no decode, cheap" like E0/E1, so it should
not be assumed to be quick. `main` is still 22 ahead of `origin/main`, unpushed, carrying the
`ac6150d` `src/`+`native/` diff ⇒ HK-029's direct-push exception still does not apply to that separate,
pre-existing range; nothing in this session changes that.

---

**Files this session touches:**
- New: `qa/rr-study/fp-regression/row0b_manifest_check.py` (predicate script, HK-021(r))
- New: this report
- Scratch only, gitignored, not committed: `artefacts/fp-regression-2026-09-04/`
