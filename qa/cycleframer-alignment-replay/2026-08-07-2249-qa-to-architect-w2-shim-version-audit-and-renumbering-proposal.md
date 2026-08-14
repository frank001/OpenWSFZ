# QA → Architect: W2 — `FT8_SHIM_VERSION` collision audit + proposed renumbering

**Author:** QA, 2026-08-07 (22:49 UTC, `date -u`, per HK-017). Repo `main` at `b8845cd`.
**Scope:** §3 ("W2") of `2026-08-07-2241-architect-to-qa-consolidated-work-queue.md`. **Audit and
proposal only** — per that document's instruction, "No pushing, no merging." Nothing in this
document has been applied to any branch. Any actual `#define FT8_SHIM_VERSION` edit is a `src/`
change and per HK-011 needs a separate Developer session plus the Captain's diff review.

---

## 1. Audit — what's actually out there

`git branch --list 'd001-*'` finds **five** local branches, not six as the queue document's prose
said (its own table only ever listed five rows, so this looks like a rounding slip in the prose,
not a missing branch — no sixth branch was found on remote, in `git worktree list`, or via
`git reflog` for a deleted ref):

| branch | `FT8_SHIM_VERSION` | ancestor of `main`? | commits ahead of merge-base | `libft8.dll` hash (12 hex) | last commit |
|---|---:|---|---:|---|---|
| `main` | 20260033 | — | — | `f2f30c890b25` | — |
| `d001-c1-candidate-cap-sweep` | 20260033 | no | 1 | `f2f30c890b25` (**identical to `main`**) | 2026-07-25 |
| `d001-c2-llr-normalization` | **20260034** | no | 2 | `4b182cc349c4` | 2026-07-26 |
| `d001-rc1-rc2-candidate-diagnostics` | **20260034** ⚠️ | no | 4 | `61253401c84a` | 2026-08-07 |
| `d001-c4-min-score-sweep` | **20260035** | no | 62 | `6237b2971695` | 2026-07-30 |
| `d001-rc4-decode-depth` | **20260035** ⚠️ | no | 1 | `39aa1031ad63` | 2026-08-07 |

Confirms the queue document's table exactly: two live collisions, `20260034` (c2 vs rc1-rc2) and
`20260035` (c4 vs rc4).

**`d001-c1-candidate-cap-sweep` is a special case, not a third collision.** Its one commit adds the
`K_MAX_CANDIDATES_ANY_PASS` stack-safety macro — deliberately shipped **without** a version bump,
because at the still-shipped `K_MAX_CANDIDATES=140` the fix is behaviourally a no-op (verified
byte-identical decode output on a 68-cycle corpus at the time, per that commit's own
`libft8.version.txt` note). That fix landed on `main` by squash (confirmed:
`ft8_shim.c:524` carries the identical macro on `main` today) and **the two DLLs hash identically**
— `f2f30c890b25` on both `main` and this branch. There is nothing left on this branch that isn't
already on `main`; it is not a version-numbering problem, it is a stale, fully-superseded branch.

Per HK-003 (verify individually before any deletion, never trust bulk `--merged`): `git merge-base
--is-ancestor d001-c1-candidate-cap-sweep main` reports **NO** — the branch is not a literal
ancestor because its commit landed via squash, not merge — but the content match (identical DLL,
identical macro on `main`) is the individual verification HK-003 asks for. **Recommend deletion**,
not renumbering. Not executed here (branch deletion isn't "no pushing, no merging" — leaving it for
the Captain/Architect to action, consistent with §3's "report up").

## 2. Why this matters beyond tidiness

`FT8_SHIM_VERSION` is the only signal that identifies which native binary is loaded at runtime — two
branches sharing a number means a build/test session cannot tell `d001-c2-llr-normalization`'s
binary from `d001-rc1-rc2-candidate-diagnostics`'s from the version string alone, and the two
`libft8.dll`s are confirmed **not** byte-identical (`4b182cc349c4` vs `61253401c84a`, and
`6237b2971695` vs `39aa1031ad63`) — so this is a real ambiguity, not a cosmetic one. This is exactly
the situation §2.2 of the consolidated queue is about to create for real: W1 needs one of
`d001-c4-min-score-sweep` or a rebase of its LLR-export machinery, and a version string that can't
disambiguate two live candidate binaries is a hazard the moment more than one of these branches is
in play on the same workstation.

## 3. Proposed renumbering

Principle: touch the **fewest** branches. Keep whichever branch claimed a number first (by commit
date); renumber only the later collider, assigning it the next integer past the highest number
currently in use (`20260035` → next free is `20260036`).

| branch | current | proposed | change? | rationale |
|---|---:|---:|---|---|
| `main` | 20260033 | 20260033 | none | shipped baseline, untouched |
| `d001-c1-candidate-cap-sweep` | 20260033 | — | **retire (delete), not renumber** | fully superseded by `main`, see §1 |
| `d001-c2-llr-normalization` | 20260034 | 20260034 | none | earlier claimant (2026-07-26) |
| `d001-rc1-rc2-candidate-diagnostics` | 20260034 | **20260036** | +1 line, one branch | later claimant (2026-08-07); resolves collision #1 |
| `d001-c4-min-score-sweep` | 20260035 | 20260035 | none | earlier claimant (2026-07-30); also the branch carrying the raw-LLR export machinery W1 needs — leaving its version stable avoids re-touching the one branch most likely to matter next |
| `d001-rc4-decode-depth` | 20260035 | **20260037** | +1 line, one branch | later claimant (2026-08-07); resolves collision #2 |

**Net effect:** two one-line `#define FT8_SHIM_VERSION` edits (on `d001-rc1-rc2-candidate-diagnostics`
and `d001-rc4-decode-depth` only), each followed by a shim rebuild so the DLL's own
`FT8_SHIM_VERSION` matches its header. **`20260038` becomes the next free number** for any future
shim-touching branch — worth recording somewhere central (e.g. the top of `ft8_shim.h` near the
`#define`, or this document linked from `BOARD.md`) so the "which number is free" question doesn't
have to be re-derived by grepping six branches again next time.

**Not proposed:** renumbering `c2` or `c4` (the earlier claimants) — that would touch two branches
instead of one for no disambiguation benefit, and `c4` in particular is the branch W1 is most likely
to be rebased from or run against next; changing its version now would just be more churn to track
through that decision.

## 4. What this document does NOT do

- Does not edit any branch. Both proposed edits are one line each (`#define FT8_SHIM_VERSION`) plus
  a shim rebuild (`rebuild_shim.bat` or equivalent) — small, but still `src/`-adjacent build output
  (a rebuilt `libft8.dll`) under HK-011. Needs a Developer session + the Captain's diff review before
  it lands on any branch.
- Does not delete `d001-c1-candidate-cap-sweep`. Recommended above; deletion itself is cheap and
  should probably happen alongside whatever the Captain decides on the other five branches' fate
  (§6 of the consolidated queue — RC4 branch disposition, D-009 Option B — is the same kind of
  decision), rather than as a one-off.
- Does not touch `d001-c4-min-score-sweep`'s `ft8_set_llr_shrinkage` knob, whose mechanism was
  closed on evidence (C.2 Phase 2, consolidated queue §1) — that branch's disposition is a separate
  question from its version number.

**Recommendation to the Captain/Architect:** approve the two-branch renumbering (§3) and the
`d001-c1-candidate-cap-sweep` deletion, both to be executed together with whatever Developer session
next touches these branches (e.g. alongside the W1 escalation decision, since that session will
already have at least one of these branches checked out).
