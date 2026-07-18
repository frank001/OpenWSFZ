## Context

`tools/check_version_bump.py` (CI Gate G9b) currently does exactly one thing: it lists every
`proposal.md` newly added under `openspec/changes/archive/` in the pull request's diff against
its base ref (`git diff --diff-filter=A ... openspec/changes/archive/**/proposal.md`), and if any
of those declare `**User-facing:** yes`, it requires `VERSION` to have changed. Nothing else is
checked. This matches the letter of the `ci-quality-gates` spec as written today (its "Mandatory
bump on user-facing archive" condition is explicitly archive-scoped) but not the Captain's
directive: the bump must land in the PR that merges the implementation, which in this project's
actual practice is almost always a different, earlier PR than the one that later archives the
change (this project routinely merges a fully-implemented, unarchived change and archives it days
later — e.g. `cat-tx-ptt`, merged via PR #71 2026-07-12, archived 2026-07-18).

## Goals / Non-Goals

**Goals:**
- Require the VERSION bump in the first pull request that introduces a user-facing change's
  `proposal.md` into `main`'s history — whether that lands it under the active
  `openspec/changes/<name>/` path (the normal case) or, unusually, directly under
  `openspec/changes/archive/<date>-<name>/` (a change proposed and archived in one shot).
- Do not re-demand a second bump when a later PR purely relocates an already-introduced change
  from the active path to the archive path (ordinary archiving) — that PR didn't introduce
  anything new; the feature was already bumped for when it first appeared.
- Keep the CLI signature (`check_version_bump.py <base_ref>`) and exit-code contract unchanged,
  since `tools/pre_merge_check.py` and CI both call it positionally.

**Non-Goals:**
- Retroactively re-checking history merged before this fix (same Non-Goal the original gate
  already carried).
- Changing anything about *which* declaration values are valid (`yes`/`no`) or where the
  declaration line must appear in `proposal.md`.
- Enforcing that implementation is *complete* (e.g. `tasks.md` fully checked) before requiring a
  bump — a change can still merge partially implemented (as `cat-tx-ptt` did); the trigger is
  "this change's proposal now exists on `main`," not "this change is 100% done."

## Decisions

### Decision 1 — Trigger: first appearance of a change's `proposal.md` anywhere under `openspec/changes/`, not just under `archive/`

Scan `git diff --diff-filter=A <base>...HEAD -- openspec/changes/**/proposal.md` (both active and
archived paths — previously only the archived-path glob was scanned). For each added path,
derive a **change name**:
- Active: `openspec/changes/<name>/proposal.md` → `<name>`.
- Archived: `openspec/changes/archive/<date>-<name>/proposal.md` → `<name>` (strip the leading
  `YYYY-MM-DD-` date prefix).

### Decision 2 — De-duplication: skip an archive-path addition that is really just a relocation

For each added *archived* path, check whether `openspec/changes/<name>/proposal.md` (the active
path for the same derived name) already existed on `<base_ref>` — i.e. the change was already
present on `main` before this PR, just at the active path. If so, this PR's archive-path addition
is a pure relocation of an already-introduced change: skip it, on the reasoning that its
introduction (and bump requirement) was already satisfied whenever it first appeared at the
active path. If no such prior active-path file existed on `<base_ref>`, this is a genuinely new
introduction (propose-and-archive-in-one-PR) and is checked normally.

This sidesteps relying on git's rename-detection heuristics (which only avoid an `A`/`D` pair
appearing at all when content similarity crosses git's default threshold) — the check is correct
regardless of whether git happens to detect the archive move as a rename or as a delete+add.

### Decision 3 — Everything else is unchanged

The declaration-validity check (missing/malformed `**User-facing:**` fails), the `yes` → "VERSION
must differ from base" check, and the `no` → "no bump required" pass-through all carry over
unmodified, just applied to the wider (de-duplicated) set of newly-introduced proposals instead
of only archive-path ones.

## Risks / Trade-offs

- **[Risk] A change name collision** (two different changes independently choosing the same
  kebab-case name at different times) could make Decision 2's de-duplication incorrectly treat an
  unrelated new active-path proposal as "already introduced," if an old, differently-scoped change
  once used the same name and was later archived. → **Mitigation**: `openspec new change` already
  refuses to scaffold a change whose name collides with an existing active change directory,
  and this project's naming convention has not produced a real collision in its history; treated
  as acceptable residual risk, matching the same trust already placed in unique change names
  elsewhere in the OpenSpec tooling.
- **[Risk] A PR that both introduces a new active proposal AND archives a different, older change
  in the same PR** must correctly evaluate both independently. → **Mitigation**: the algorithm
  evaluates each added path independently by its own derived name; this falls out of the design
  without special-casing.

## Migration Plan

1. Rewrite `tools/check_version_bump.py` per Decisions 1–3; CLI signature unchanged.
2. Manually verify against constructed scratch-repo scenarios (new active proposal + no bump →
   fail; + bump → pass; `no`-declared → pass regardless; pure archive relocation of an
   already-introduced change → pass without a second bump; propose-and-archive-in-one-PR with no
   bump → fail; malformed declaration → fail) — this class of script has no existing unit-test
   precedent in this repo (`check_version_docs.py`/`check_native_version.py` are likewise
   untested by pytest), so real-scenario manual verification is the established bar here, not a
   gap specific to this change.
3. Update `openspec/specs/ci-quality-gates/spec.md`'s G9 requirement text/scenarios via this
   change's delta spec.
4. Rename the CI step for clarity; no trigger/invocation change.
5. Rollback is a plain revert — the script change is self-contained and the spec delta is
   additive/replacing text only.

## Open Questions

None — the Captain's directive ("the only acceptable time for the version bump is pre-merge") is
unconditional and is implemented directly above.
