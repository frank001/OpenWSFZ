# `FP-REGRESSION` -- Architect ruling on QA's E0 inventory flag

**Architect, 2026-09-04 15:07Z** (`date -u`, HK-017). Adjudicates the flag raised in
`2026-09-04-1450-qa-to-architect-fp-regression-e0-e1-result.md` (E0.1). PO-ratified this session on
both action items.

---

## 1. E0 and E1 are ACCEPTED. E2 is NOT gated by this.

Nothing in E0 or E1 depends on `qa/ARTEFACT_INVENTORY.md`. Corpus presence was established by
**direct enumeration** (`ls *.wav | wc -l` = 4,000, split `S5_p000_*` / `S5_p001_*` 2,000 each), not
by trusting the inventory -- which is the correct instrument choice and is why the flag does not
propagate into the result.

- The 10-row manifest recomputation (8 rows + 2 alt-refs, zero mismatches) stands.
- The **ROW 0b verdict -- DOES NOT FIRE** -- stands. Both windows carry a changed win-x64
  `libft8.dll` SHA256, so ROW 1 can bisect either.
- HARD STOP 1 was honoured as written (HK-030). QA flagged rather than silently fixed (HK-018),
  and imported the NFR-021 scanner's `scan()`/`classify()` rather than its CLI because the CLI
  diffs a committed ref and would have false-greened uncommitted files. All correct.

**E2 proceeds on the Captain's go-ahead, unchanged.** Neither action below blocks it.

## 2. The flag is TWO findings, and the report's stated cause is wrong

QA reported one issue. It is two, with different causes and different fixes. The report attributes
both to staleness (*"The file predates this corpus"*); that explanation is correct for the first and
**false for the second**.

### (A) Staleness -- REAL, and bounded to three additive rows

`python qa/artefact_inventory.py --check` failed. Regenerating into a scratch file and diffing showed
the drift is **exactly three added rows and the `Scanned:` line** -- nothing removed, nothing changed:

| added row | WAVs |
|---|---|
| `2026-08-30-rr-s1s8-sup-b-shim20260048` | `cycle-audio` 5,719 |
| `2026-09-02-rr-s1s8-3b52608` | `cycle-audio` 755 |
| `2026-09-03-rr-s1s8-35378b9` | `cycle-audio` 335 |

⚠️ **QA's own scratch directory `artefacts/fp-regression-2026-09-04/` is NOT one of these rows and
did NOT cause the failure.** This was worth checking rather than assuming: the scratch dir was
created inside the same session that ran `--check`, so a self-contaminated diagnostic was a live
possibility. It is ruled out by the diff.

### (B) "does not mention `m1m4_s5`" -- NOT staleness. A scope gap. Regeneration does not fix it.

`qa/artefact_inventory.py:55` sets `ARTEFACTS = os.path.join(REPO, "artefacts")`, and `main()`
returns exit 2 if that directory is absent. **`artefacts/` is the scanner's only root.** The corpus
lives at `qa/rr-study/awgn-fp-replay/_work/m1m4_s5/` -- 1.4 GB, gitignored at `.gitignore:222` --
outside that root. It could never have appeared in the inventory, at any level of freshness.

⇒ The remedy QA's flag implies (re-run the generator) addresses (A) and **leaves (B) exactly as it
was.** Naming the wrong cause here would have closed the ticket while the defect stayed open.

## 3. The consequence that outlives this arm (HK-026)

The standing rule is *"before concluding data doesn't exist, or proposing ANY capture run: read
`qa/ARTEFACT_INVENTORY.md`."* That instrument's response is **FLAT** over every offline corpus under
`qa/**/_work/`: a passing `--check` is not evidence that a corpus is absent, because no such corpus
can register in it. **An instrument may not be used to bound a region where its response is flat**
(HK-026).

This is the script's own stated failure mode, reintroduced through a root it never covered -- its
docstring: *"a stale inventory is worse than none: it produces confident false negatives ('we don't
have that'), which is the same failure with the sign flipped."*

🔴 And the three rows it was missing include **`2026-09-03-rr-s1s8-35378b9`** -- the sweep whose
`Section 6` carries the FP-regression evidence the Architect denied twice this session (HK-031).
The inventory was blind to the artefact directory of the run at the centre of the open arm.

## 4. ACTION A -- DONE this session (PO-ratified: "Architect regenerates now")

`python qa/artefact_inventory.py` run; `--check` now returns **"ARTEFACT_INVENTORY.md up to date"**.

- Real committed-vs-new diff verified **byte-for-byte against the 4-line diff predicted before
  regenerating** -- three additive rows plus `Scanned:`; no row removed or altered.
- Header moved `35 runs / 132,296 WAVs` -> `38 runs / 139,105 WAVs`.
- **NFR-021 on the regenerated tracked file: `scan() -> ({}, {})`** -- zero flagged, zero
  grid-excluded. Expected: the generator emits counts and paths only, never decoder output.
- `git diff --stat -- src/ native/` -> **empty**. Docs-only. Committed locally, **not pushed**
  (HK-014); HK-029's direct-push exception remains inapplicable to the pre-existing 22-commit range,
  which still carries `ac6150d`'s `src/`+`native/` diff.

## 5. ACTION B -- follow-up for QA, does NOT gate E2 (PO-ratified: "extend the scanner")

Close the scope gap in the generator, preserving its core design property (*"every column except
notes is measured from disk on each run, so it cannot go stale silently"*). A hand-maintained
pointer section was considered and rejected for exactly that reason.

**Scope.** `qa/rr-study/**/_work/` as a second measured root, rendered in its own clearly labelled
section (rendered corpora are not captured runs and must not be pooled into the run table, where a
`UTC span` column is meaningless for them).

**Acceptance, mechanical:**

1. `grep m1m4_s5 qa/ARTEFACT_INVENTORY.md` returns a row carrying a WAV count of **4,000**.
2. `python qa/artefact_inventory.py --check` exits 0 immediately after a regeneration.
3. NFR-021 `scan()` over the regenerated file returns `({}, {})`. WAV filenames under `_work/` are
   synthetic (`S5_p000_*`), so a flagged token here means the walk picked up something it should not
   have -- **investigate, do not redact past it.**
4. Runtime stays in seconds: count WAVs by name via `os.scandir` as the existing walk does; **do not
   add a per-file `stat`** across a 1.4 GB tree.
5. `git diff --stat -- src/ native/` empty. This is `qa/` tooling, so HK-011 does not apply and no
   Developer session is required.

⚠️ **Not part of `FP-REGRESSION`.** Do not fold it into an E-block. It is a separate, separately
committed piece of work, and E2 must not wait on it.

## 6. Correction carried to QA, for the next report

The E0 text asserted a cause (*"the file predates this corpus"*) that was not verified before being
written down, and the true cause was reachable in one `grep` of the generator's roots. The flag
itself was right and raising it was right. The discipline to add: **when reporting that an
instrument failed to show something, state whether the instrument was ever pointed at it** -- that
is the same question HK-022 asks of a green result, asked of a red one.
