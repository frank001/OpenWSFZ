# Developer handoff: renumber two colliding `FT8_SHIM_VERSION` values on unmerged D-001 branches

**Authored by:** QA, per HK-000/HK-011/HK-015. **Ordered by:** Architect Recommendation D,
2026-09-02 20:10Z (`qa/rr-study/2026-09-02-2010-architect-to-qa-handoff-post-row0-session.md`),
PO blanket go-ahead on Recommendations A–E the same session. This document is QA's own — the
Architect is barred (HK-015) from writing dev-tasks; QA authors it here and **stops** (HK-011). No
build, no rebuild, no `opsx:apply` has been run by QA. Only the **Captain** opens a Developer
session against this document.

**Behaviour change: NONE to any code path that runs today.** Both branches are unmerged and
inert on `main`. This is a same-content, different-label rename on two experimental branches —
no logic, struct layout, or existing entry point changes. The only observable effect is that each
branch's `ft8_lib_version_check()` and `daemon`'s reported `shimVersion` return a different
integer than they do today.

---

## 0. Why this exists

`FT8_SHIM_VERSION` is meant to identify a unique binary/source pairing. A 2026-09-02 sweep of
every branch's `#define FT8_SHIM_VERSION` (QA, this session, `git show <branch>:src/OpenWSFZ.Ft8/
Native/ft8_shim.h | grep '#define FT8_SHIM_VERSION'` across all 15 unmerged local+remote branches)
found **two genuine collisions** — same version number, different shim content, on branches that
have never merged with each other:

| Version | Branch A | Branch B | Verified distinct? |
|---|---|---|---|
| `20260034` | `d001-c2-llr-normalization` | `d001-rc1-rc2-candidate-diagnostics` | Yes — `ft8_shim.h`/`ft8_shim.c` blob hashes differ on both files (`git rev-parse <branch>:<path>`); content is unrelated (LLR normalisation vs. a raw candidate-list TLS getter) |
| `20260035` | `d001-c4-min-score-sweep` | `d001-rc4-decode-depth` | Yes — same check; content is unrelated (min-score-pass2 sweep vs. `K_MAX_PASSES` 2→3 diagnostic) |

🔴 A `FT8_SHIM_VERSION` string is **not** an identity by itself (standing rule) — but two branches
racing to claim the same number is still a hygiene defect: if either ever merges toward `main`
while the other is still open, a rebuild could silently present the wrong shim's binary under a
version number a report already cited. Fix now, while both are cheap, isolated edits.

**Only ONE branch of each pair is renumbered — the other keeps its original number.** QA's own
verification (this session) confirms `d001-c2-llr-normalization` (`20260034`) and
`d001-c4-min-score-sweep` (`20260035`) are the more senior of each pair (both have a same-numbered
`origin/` remote or are referenced elsewhere as the "primary" C-series arm) — they are **not**
touched by this task. Only `d001-rc1-rc2-candidate-diagnostics` and `d001-rc4-decode-depth` change.

🔴 **`20260050` is OUT OF BOUNDS for this task.** It is pinned by the `F-001` L3 sizing spec
(`qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md` §5, ROW 0a)
as a hard gate value for a **different**, not-yet-built export
(`ft8_get_h12_unresolved_by_code`). The Architect already ruled explicitly that a pre-registered
gate pinning a number is load-bearing and wins over an arbitrary renumber target — do not touch
`20260050`, do not let either branch below claim it, and do not "round down" to it if a rebase
makes the arithmetic tempting.

**New targets, mechanically verified unused across all 15 branches (local + `origin/*`) by QA this
session** (`git show <branch>:.../ft8_shim.h | grep FT8_SHIM_VERSION` on every branch listed by
`git branch -a`; full table available on request, not reproduced here to keep this document
short):

- `d001-rc1-rc2-candidate-diagnostics`: `20260034` → **`20260051`**
- `d001-rc4-decode-depth`: `20260035` → **`20260052`**

Re-verify this immediately before committing (§3 step 0) — new branches may have appeared since
this document was written, and a stale "unused" claim is exactly the failure mode this task exists
to prevent.

---

## 1. Scope — what changes, what does not

**In scope, per branch, live source only:**
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — the `#define FT8_SHIM_VERSION` line and its own
  changelog-comment entry naming the old number.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — comment references to the old number (no code logic
  changes; the number appears only in comments in `ft8_shim.c` on both branches).
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `ExpectedShimVersion` constant (the ACTUAL
  behaviour-relevant line: a stale pin here fails `LoadAndVerify` at daemon startup, same trap
  flagged in the 20260045 handoff's task 10.6 note) and its doc-comment references.
- `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs` — one doc-comment reference
  (`d001-rc1-rc2-candidate-diagnostics` only, line 49).
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — one doc-comment reference (`d001-rc1-rc2-candidate-diagnostics`
  only, line 39).
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — the CURRENT block at the top of the file
  (see §2.3).
- `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs` — doc-comment references (not assertions; no
  test logic changes).

**Out of scope, explicitly — do NOT touch:**
- 🛑 Everything under `qa/cycleframer-alignment-replay/` on either branch (dated result reports,
  console logs, replay scripts naming the old version). These are **historical records of a run
  that actually happened against that build** — editing them would falsify what was run. Per the
  project's own "extends, never overwrites" convention, if the renumber needs to be noted anywhere
  historical, add a new dated note; do not rewrite the old one.
- The other branch of each pair (`d001-c2-llr-normalization`, `d001-c4-min-score-sweep`) — their
  numbers are correct and unchanged.
- Any decode logic, struct layout, candidate search, or existing exported entry point on either
  branch. This is a label change only.
- `main` — neither branch is being merged by this task. This task does not authorise a merge.

---

## 2. What to do, per branch, in order

Repeat for `d001-rc1-rc2-candidate-diagnostics` (→ `20260051`) and separately for
`d001-rc4-decode-depth` (→ `20260052`). Do not combine the two into one branch/commit — they are
independent, unrelated D-001 diagnostics and should stay independently mergeable/discardable.

### 2.1 Preconditions (run before editing either branch)

1. `git fetch` and re-run the unused-number check from §0 against **current** `git branch -a` —
   confirm `20260051` and `20260052` still appear on zero branches.
2. Confirm the branch is still at the commit this task was written against — if either branch has
   moved, re-read this section's line numbers against the new tip before editing (they were taken
   from the branch tips current as of this document's authoring, 2026-09-03).

### 2.2 The rename itself

On `d001-rc1-rc2-candidate-diagnostics`: replace every occurrence of `20260034` with `20260051`
in the seven in-scope files listed in §1. Confirmed occurrences this session (re-`grep` before
editing — a rebase or later commit could have added more):

- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:296` (changelog comment), `:312` (`#define`), `:425` (comment)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:364`, `:580`, `:1121` (comments only)
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:223` (doc comment), `:233`
  (`private const int ExpectedShimVersion = 20260034;` — **the one line that is not a comment**),
  `:353`, `:554` (doc comments)
- `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs:49` (doc comment)
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:39` (doc comment)
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt:3`, `:66` — see §2.3, do not blind
  find-replace this file
- `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs:209` (doc comment)

On `d001-rc4-decode-depth`: same pattern, `20260035` → `20260052`:

- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:296`, `:313` (`#define`)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:364`, `:498` (comments only)
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:223`, `:233` (`ExpectedShimVersion = 20260035;` — the
  behaviour-relevant line), `:263`, `:280`
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt:3`, `:71`, `:75` — see §2.3
- `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs:26`, `:119`

### 2.3 `libft8.version.txt` — a running changelog, not a flat find-replace target

This file is a chronological "CURRENT, then `Previous:` chain" log paired with the shipped DLL's
own SHA256. Update **only the CURRENT block's version number and add one clause noting the
renumber and why** (cross-reference this document by filename). Do **not** rewrite the prose
describing what the change itself does, and do **not** touch any earlier `Previous:` entry — the
chain is history and this task's own §1 "extends, never overwrites" rule applies here too.

### 2.4 Rebuild and re-pin

The `#define` change alters the compiled binary (the version integer is embedded and returned by
`ft8_lib_version_check()`), so each branch needs its native library rebuilt after the edit:

1. Rebuild `libft8.dll` (win-x64; other platforms if you have toolchain access) from the edited
   branch.
2. Compute and record the new SHA256 honestly — do not copy a prior value.
3. Update `libft8.version.txt`'s SHA256 line (already open per §2.3) with the freshly-computed
   value.
4. `dotnet build` — 0 warnings. `dotnet test` — full suite green, including
   `Ft8LibInteropTests`'s `ExpectedShimVersion`-dependent load check.
5. Verify mechanically (not by inspection) that `ft8_lib_version_check()` on the rebuilt binary
   returns the new number — a quick P/Invoke smoke call or the existing `LoadAndVerify` path at
   daemon startup both work; record which one you used.

**No decode-output diff check is required here** — unlike a behaviour-bearing bump (e.g. the
`20260045`/Amendment 2 precedent), this rename touches no decode-path line on either branch, so
there is no risk of a silent output change to characterise. If you want the extra assurance
anyway, a short replay (any small existing corpus) confirming byte-identical decode lines
before/after is welcome but not required for sign-off.

---

## 3. Acceptance criteria (what QA checks on review)

- `d001-rc1-rc2-candidate-diagnostics`'s `ft8_shim.h` reads `#define FT8_SHIM_VERSION 20260051`;
  every other in-scope-file occurrence of `20260034` in §2.2's list is updated to match; nothing
  under `qa/cycleframer-alignment-replay/` on this branch was touched.
- `d001-rc4-decode-depth`'s `ft8_shim.h` reads `#define FT8_SHIM_VERSION 20260052`; same check for
  `20260035`; same historical-directory exclusion.
- Neither branch's `ft8_shim.h`/`ft8_shim.c` diff touches any line outside a version number or a
  comment naming one (mechanical diff review, not eyeballed) — confirms this really is a rename,
  not a drive-by logic change.
- `libft8.version.txt` on each branch shows the new CURRENT version, a note explaining the
  renumber, its own SHA256 matching the freshly rebuilt DLL, and an intact unedited `Previous:`
  chain below it.
- Both `dotnet build` (0 warnings) and `dotnet test` (full suite) are green on each branch,
  independently.
- Re-running the §0 "unused across all branches" check at commit time shows `20260051` and
  `20260052` each appearing on exactly one branch (the one it was assigned to) and nowhere else.
- This task produces **two independent commits on two independent branches** — no merge to
  `main`, no cross-branch dependency introduced between `d001-rc1-rc2-candidate-diagnostics` and
  `d001-rc4-decode-depth`.

**Not this session's to decide:** whether either branch is ever proposed for merge. This task only
removes a latent version collision so that question, if and when it comes up, isn't also carrying
a wrong-binary risk.

---

**References:**

- `memory/BOARD.md`, 2026-09-02 20:10Z entry, item "D — SHIM RENUMBER".
- `qa/rr-study/2026-09-02-2010-architect-to-qa-handoff-post-row0-session.md`.
- `qa/rr-study/2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md` §5 ROW 0a
  — the reason `20260050` is reserved and out of bounds here.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h`, `ft8_shim.c`, `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`,
  `IFt8NativeInterop.cs`, `Ft8Decoder.cs`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`,
  `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs` — the files §2 edits, both branches.
- Licence discipline unchanged: WSJT-X source may be read for method only; no line copied,
  transliterated, or ported (Captain's ruling, 2026-08-11).
