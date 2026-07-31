# ARCHITECT CORRECTION — S.2a's "no rebuild" claim is FALSE on `main`
# The diagnostic exports it depends on exist only on an unmerged branch. S.2a is not a QA-only arm.

**Author:** Architect, 2026-07-31 (17:02 UTC, `date -u`, per HK-017). Repo at `113d86d`.
**Corrects:** `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` **§4, arm S.2a**
(and §7 sequencing rule 3, which rests on it).
**For:** QA — **do not plan S.2a as a QA-only arm.** And the Captain (§4 — the cost consequence).
**Found by:** the Captain asking whether arm S.1 needed Developer work. It does not (§5). Verifying
that answer surfaced this.
**Does not affect:** arm S.1, its rev3 spec, or the drift screen. Both remain QA-only and unblocked.

---

## 1. The claim, and what is actually on `main`

Rev2 §4, arm S.2a, states verbatim:

> **Method.** **No rebuild.** Run the shipped 140 build over the dense-quartile 20m WAVs with the
> already-shipped, default-off diagnostic exports (`ft8_set_candidate_diag_capture` et al., shim
> ≥20260035) …

**Every load-bearing word of that is wrong with respect to `main`.**

| claim | reality on `main` |
|---|---|
| *"already-shipped … diagnostic exports"* | **Not present.** `git grep candidate_diag main` returns **one** file — `…-rev2-competition-scoped.md` itself, i.e. my own memo asserting they exist. There is no such symbol in any `.c`, `.h` or `.cs` on `main` |
| *"shim ≥20260035"* | `main` is at **`FT8_SHIM_VERSION 20260033`** (`src/OpenWSFZ.Ft8/Native/ft8_shim.h:297`) — two increments short |
| *"No rebuild"* | **False.** The exports do not exist to be enabled |

The exports are real, but they live on **`d001-c4-min-score-sweep`**, which declares
`FT8_SHIM_VERSION 20260035` (`ft8_shim.h:333`) and defines
`ft8_set_candidate_diag_capture(int enable)` and `ft8_set_candidate_diag_llr_capture(int enable)`
with their readback entry points. That branch is **62 commits ahead of `main` and unmerged.**

Note the specific shape of the error: **the version number I cited, 20260035, is exactly the
branch's version.** I read the requirement off the branch and then described it as shipped. The
citation was accurate; the word "already-shipped" was not, and one sentence carried both.

## 2. This is the second instance of one pattern, not an isolated slip

Rev2 §11 and work order `1356` §4 already record that
`2026-07-27-1730-architect-row4-scoping-design.md` exists **only on `d001-c4-min-score-sweep`**,
while `main` cites three of its arms (R.1/R.2/R.3) as live work.

**Same branch. Same failure. Second occurrence.** `main` now depends on that branch for *design
documents* and, per §1, for *native instrumentation*. The branch disposition has stopped being
housekeeping — it is now a live dependency of the D-001 work programme, and each time it goes
unresolved it acquires another dependent.

I flagged the first instance and did not go looking for others. That was the error worth naming
here: having found one document on `main` depending on an unmerged branch, the proportionate
response was to check whether anything *else* did — including code. I did not, until asked an
unrelated question a day later.

## 3. Corrected status of S.2a

| | rev2 said | corrected |
|---|---|---|
| Cost class | QA-only, half a session, "no native build" | **Developer session required** (HK-011) — porting the diagnostic exports to `main`, or landing the branch |
| Sign-off | none beyond the S.1 gate | **Captain's, per HK-011/HK-010** — it is a `src/`+native change |
| Prerequisite | none | **Branch disposition for `d001-c4-min-score-sweep` must be settled first** |

**Two routes, and they are not equivalent:**

- **Port only the diagnostic exports onto `main`.** Read-only instrumentation, default-off, one
  shim increment. Small, reviewable, and it does not drag 62 commits of experimental sweep work
  onto `main`. **This is the route I would recommend** if S.2a is reached.
- **Land `d001-c4-min-score-sweep`.** Settles both this and the missing 07-27 design in one move,
  but it carries the min-score sweep and much else, and the branch's `libft8.dll` size delta was
  already held as a merge blocker until explained. **Not a cheap merge.**

## 4. Consequence for the sequencing — the Captain's gate moves earlier

Rev2 §7 rule 3 reads:

> If S.2a's boundary scores are flat, **H1 is dead — stop, do not run S.2b.** A native rebuild to
> confirm a negative is the wrong purchase.

That reasoning assumed **S.2a itself was free of rebuilds.** It is not. The clean "S.2a is free,
S.2b is the expensive one" framing does not survive §1.

**What still holds:** S.2a is one Developer change (read-only instrumentation, one build); S.2b is
three native rebuilds *plus* the stack-safety fix and the stale-DLL pitfall. Those remain different
cost classes and the gate between them is still worth having.

**What changes:** the Captain's authorisation, which rev2 attached only to S.2b, **now attaches to
S.2a as well.** If S.1 fires row 2 or row 3, the next step is not "QA runs S.2a" — it is **a priced
decision back to the Captain.** QA should not plan otherwise.

**What this does not change:** S.1's own value is untouched. If anything it rises — S.1 is now the
last free thing on the board, and if it fires row 1 (frequency-local) then S.2 is not run at all
and none of this cost is incurred.

## 5. S.1 and the drift screen are unaffected — verified, not assumed

- **Arm S.1** (`2026-07-31-1649-…-spec-rev3-segment-1-execution-ready.md`) reads two frozen text
  files (`ALL.TXT`, `jt9_ALL.TXT`) with `anova_common.parse_all_txt` and reuses
  `measurement_d_within_band_density.py`. **No native symbol, no decode run, no rebuild, no
  `src/`.** QA-only, unblocked, and it should start on schedule.
- **The drift screen** (`1356` task 1) generalises hardcoded corpus paths in
  `verify_dt_drift_489135a.py` to arguments. QA tooling under `qa/`. QA-only.

## 6. Citation blacklist — addition

Extends `1222` §7, `1530` §7 and `1602` §7.

| do not cite | instead |
|---|---|
| *"S.2a needs no rebuild"* / *"S.2a is a QA-only arm"* ⟨mine, rev2 §4⟩ | **False on `main`.** Needs a Developer session and the Captain's sign-off (§3) |
| *"the candidate diagnostic exports are already shipped"* ⟨mine, rev2 §4⟩ | **Shipped on `d001-c4-min-score-sweep` only.** `main` is at shim 20260033; the exports are absent |

## 7. Boundaries

- **No `src/` change here** (HK-011) — this is a correction memo. The port described in §3 is a
  Developer session's work and is not authorised by this document.
- **No push, no merge** (HK-014/HK-010) — committed locally and stops there. I do not ask.
- **No new arm, no new measurement.** Nothing in §§1–6 changes what is being measured; §4 changes
  who must authorise it and when.
- **Per HK-015** this is Architect → QA. The branch disposition in §3 is the Captain's; `dev-tasks/`
  remain QA's to author.

## 8. Cross-references

- `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` §4 (S.2a), §7 rule 3, §11 — the
  document corrected.
- `2026-07-31-1649-…-arm-s1-spec-rev3-segment-1-execution-ready.md` — unaffected; §5 above.
- `2026-07-31-1356-…-work-order-after-measurement-d.md` §4 — the first instance of the same
  branch dependency, still open.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — S.2a's baseline. Checked: it does **not** cite
  the exports by name, so this correction is a single point of error, not a chain.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:297` (`main`, 20260033) vs the same file at `:333` on
  `d001-c4-min-score-sweep` (20260035) — the evidence for §1.

---

*Per HK-015 this is Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge, and I
do not ask for one. Per HK-011 nothing here touches `src/`; §3 states plainly that the port is a
Developer session's work rather than smuggling it into a QA arm — which is precisely the error being
corrected. Per HK-017 filename and byline carry `date -u` UTC. Per HK-018 §1's table was read from
`ft8_shim.h` on both refs and from `git grep` over `main`, not asserted from memory — the claim
being corrected is itself an example of what asserting from memory costs.*
