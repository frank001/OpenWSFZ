# Developer handoff: renumber `decoder-param-readout`'s `FR-067`–`FR-070` to `FR-074`–`FR-077`

**Authored by:** QA (per HK-000/HK-015/HK-011). **Status:** ready for a Developer session.
**Source:** discovered by QA while syncing `decoding_improvement` with `main` (Captain-requested,
2026-09-25) — the merge conflicts in `REQUIREMENTS.md` because both branches independently used
`FR-067`–`FR-070` for two completely different, already-shipped features. **Captain, on being asked
whether QA should just do this itself: "go ahead, developer handoff."**
**Branch:** `decoding_improvement`, tip `84cac119` at the time of writing — this commit is
`decoding_improvement`'s own current tip, not a feature branch off `main`; work directly on
`decoding_improvement` (or a short-lived branch merged straight back into it), matching how this
branch is normally maintained. **Every file:line reference below was read directly from
`origin/decoding_improvement`@`84cac119` via `git grep`/`git show`, not from a local checkout, so it
reflects that exact commit (HK-018/HK-022).**

🛑 **QA proposes this diff and stops here (HK-011). QA does not edit `src/`/`tests/`, does not build,
does not run `pre_merge_check.py`.** A separate Developer session implements this, builds, and runs
the existing test suite (every test below should still pass — the DisplayName strings on the C#
tests and the JS test names are cosmetic; xUnit/vitest key on the surrounding attribute/function, not
the string, but confirm this project's own test runner doesn't do name-based filtering anywhere that
would break). The Captain reviews the diff before it lands. QA resumes the `decoding_improvement`/
`main` sync merge afterward — that's QA's, not the Developer's.

## 0. Why this exists, and why it's a rename, not a design decision

`main` independently shipped `capture-stall-detection-unattended` (#188) and
`capture-device-reresolution` (#187) using `FR-067`–`FR-073`, merged and live (`main`@`43877580`).
`decoding_improvement` shipped `decoder-param-readout` earlier, at v0.50, ALSO using `FR-067`–`FR-070`
— chosen at the time because `FR-066` was the highest number then in force
(`openspec/changes/decoder-param-readout/proposal.md:31`). Neither side did anything wrong; the two
branches simply diverged and picked the same next-free range independently. `main`'s numbers are
already shipped, merged, and cited in board/commit history outside this repo's own text — they do not
move. `decoding_improvement`'s `FR-067`–`FR-070` move to `FR-074`–`FR-077` (the first free range once
`main`'s `FR-073` is accounted for). There is no judgement call left in the mapping itself:

| Old | New |
|---|---|
| `FR-067` | `FR-074` |
| `FR-068` | `FR-075` |
| `FR-069` | `FR-076` |
| `FR-070` | `FR-077` |

**Scope check already done, so you don't have to re-grep the whole tree**: `git grep -n -E
"FR-067\|FR-068\|FR-069\|FR-070" origin/decoding_improvement -- src/` returns **nothing** — no
production `src/*.cs` file cites these numbers, only `REQUIREMENTS.md`, the still-open
`openspec/changes/decoder-param-readout/` change files, and four test files (three `.cs`, one `.js`,
all comments/`DisplayName`/test-name strings — no test logic itself references the FR number as a
value, only as a human-readable label). This is a mechanical rename across exactly six files.
**Do not touch** `dev-tasks/2026-09-19-density-remedy-stage1-decoder-param-readout.md` — that is a
historical, already-actioned handoff; leave it as the historical record it is.

## 1. `REQUIREMENTS.md`

- **Lines 211–214**: the four FR table rows. Change `FR-067`→`FR-074`, `FR-068`→`FR-075`,
  `FR-069`→`FR-076`, `FR-070`→`FR-077` in the leftmost (ID) column of each row. **Also** fix the
  in-body cross-reference inside the `FR-067`/now-`FR-074` row's own text — it currently reads
  "...named on the read-only page's 'Not included' note (FR-070)..." and must read "...(FR-077)...".
- **Line 495** (changelog row `1.48`): change "Added **FR-067**–**FR-070**" to "Added
  **FR-074**–**FR-077**" in the prose. **Leave the row number (`1.48`) and the version bump
  (`v0.50`) exactly as they are** — QA will reconcile both of those (along with `VERSION` itself,
  which needs to become `0.52` once this branch has all three of `main`'s two shipped features plus
  this one on top of the true `0.49` merge-base) at the point the `main` sync merge actually runs;
  doing it here, before that merge exists in this tree, would leave the changelog's own row numbering
  visibly wrong in isolation (there is no row `1.49` on this branch yet to sit next to).

## 2. `openspec/changes/decoder-param-readout/proposal.md`

- **Line 31**: "`the highest today is `FR-066`, so start at `FR-067`)`" → describes a historical fact
  (true at the time this change was proposed) that is now also the source of the collision. Reword to
  record BOTH the original reasoning and the correction, e.g.: "the highest at proposal time was
  `FR-066`, so this change originally used `FR-067`–`FR-070`; renumbered to `FR-074`–`FR-077` on
  2026-09-25 when syncing with `main`, which had independently shipped `FR-067`–`FR-073` for an
  unrelated pair of changes (#187/#188) in the meantime — see this change's own `tasks.md` for the
  full rename." Don't just silently change `067` to `074` here without the note — a reader of this
  proposal later should be able to tell the numbers moved and why (HK-022).

## 3. `openspec/changes/decoder-param-readout/tasks.md`

- **Line 40**: `**FR-067**` → `**FR-074**`.
- **Line 41**: `**FR-068**` → `**FR-075**`.
- **Line 43**: `**FR-069**` → `**FR-076**`.
- **Line 44**: `**FR-070**` → `**FR-077**`.
- **Line 51**: `**FR-067 … FR-070**` → `**FR-074 … FR-077**`; also "Highest today is `FR-066`" has
  the same historical-accuracy question as proposal.md line 31 above — a short parenthetical noting
  the later renumbering is enough here, doesn't need to repeat the full explanation.

## 4. `tests/OpenWSFZ.Ft8.Tests/DecoderParamReadoutTests.cs`

Rename in every occurrence, comments and `DisplayName`/`Theory` strings alike — the mapping is
mechanical (`067`→`074`, `068`→`075` throughout this file; it never cites `069`/`070`):
- Line 257: comment `// FR-067 — the parameter table` → `// FR-074 — the parameter table`.
- Lines 260, 270, 294, 312, 325, 361, 377, 401, 423, 435: each `DisplayName`/`Theory` string starting
  `"FR-067: ...` → `"FR-074: ...` (text after the colon unchanged).
- Line 444: comment `// FR-068 — the suppression ramp's runtime setter / getter` →
  `// FR-075 — the suppression ramp's runtime setter / getter`.
- Lines 447, 462, 487, 499, 503, 597, 623: each `"FR-068: ...` → `"FR-075: ...`.

## 5. `tests/OpenWSFZ.Web.Tests/DecoderParamsEndpointTests.cs`

- Line 17: doc-comment `/// FR-069):` → `/// FR-076):`.
- Lines 78, 102, 117, 140, 159, 172, 183, 205, 227: each `"FR-069: ...` → `"FR-076: ...`.

## 6. `tests/OpenWSFZ.Web.Tests/DecoderParamsPageTests.cs`

- Line 13: doc-comment `(decoder-param-readout, shim 20260054, FR-070).` →
  `(decoder-param-readout, shim 20260054, FR-077).`.
- Lines 63, 76, 89, 109, 126, 141, 164, 189, 234: each `"FR-070: ...` → `"FR-077: ...`.

## 7. `web/js/decoderParams.test.js`

- Line 3: comment `shim 20260054, FR-070).` → `shim 20260054, FR-077).`.
- Lines 23, 28, 34, 40, 46, 51, 64, 70, 75: each test name `'FR-070: ...` → `'FR-077: ...`.

## 8. Verification before handing back

- `git grep -n -E "FR-067|FR-068|FR-069|FR-070"` from the repo root should return **zero** hits
  anywhere under `REQUIREMENTS.md`, `openspec/changes/decoder-param-readout/`, `tests/`, `web/js/`
  after this change (the historical `dev-tasks/2026-09-19-...md` file is the one intentional,
  documented exception — see §0).
- `git grep -n -E "FR-074|FR-075|FR-076|FR-077"` should show exactly the new occurrences, nothing
  under `src/` (unchanged — there was nothing there before either).
- Run the existing suites this change already had green (`OpenWSFZ.Ft8.Tests`, `OpenWSFZ.Web.Tests`,
  the `web/js` test runner) — a pure rename should not change a single assertion's outcome; a failure
  here means something was renamed incorrectly (e.g. a `067`→`074` typo landing as `74` bare, or a
  digit transposed), not a real regression.
- `openspec validate --strict --all` for `decoder-param-readout` should still report the same
  pass/fail state as before this change (renaming an FR ID does not change spec validity by itself).
