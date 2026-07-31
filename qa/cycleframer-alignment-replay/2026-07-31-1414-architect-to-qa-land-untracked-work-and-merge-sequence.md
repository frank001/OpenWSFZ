# Architect → QA — land the untracked work, then the merge sequence
# One NFR-021 blocker must be cleared before anything is committed. Read §1 first.

**Author:** Architect, 2026-07-31 (14:14 UTC, `date -u`, per HK-017). Repo at `ed8fed3`.
**For:** QA. Every item is QA's to do or route; none of it is mine to apply.
**Occasion:** the Captain ran `pre_merge_check.py` (HK-006 — the Captain's trigger, correctly),
got READY, and intends to proceed to merge. This document covers what must happen first so
nothing is lost and nothing improper is published.
**Does not supersede** `2026-07-31-1356-…-work-order-after-measurement-d.md` — that queue (drift
screen, then arm S.1) stands and resumes once this lands.

---

## 0. The board

| # | item | status |
|---|---|---|
| **1** | **`session_log.md` carries real callsigns — NFR-021 blocker** | **BLOCKS COMMIT (§1)** |
| 2 | Commit the rest of `2026-07-28-031fb37/` | Ready once §1 clears (§2) |
| 3 | Commit `external-reporting-single-connection-live-verify/` | Screened clean; QA to confirm (§3) |
| 4 | Dispose of the three `2026-07-28-supervisor-*.sh` | QA's call — safe either way (§4) |
| 5 | **Push. 18 commits of today's work have never left this machine** | **The real durability risk (§5)** |
| 6 | The merge sequence — the gate tested the wrong tree | Route to the Captain (§6) |

**Already committed — do not chase it.** The Captain named
`qa/cycleframer-alignment-replay/2026-07-31-1356-architect-to-qa-work-order-after-measurement-d.md`
as something to land. It is **already committed, at `ed8fed3`**. What is true is that it is
**unpushed**, along with 17 other commits — which is §5, and is the more important version of the
same concern.

## 1. BLOCKER — `session_log.md` cannot be committed as it stands

`qa/endurance/2026-07-28-031fb37/session_log.md` (26 KB) and its rendered `session_log.html`
(44 KB) contain **approximately 22 distinct real amateur callsigns** in narrative text — decoded
stations named directly in the account of the QRM investigation and the live run.

**I am deliberately not reproducing the list here.** Writing them into this document to describe
the problem would commit the same violation it is reporting. QA can regenerate the list locally in
seconds; it must not travel into a committed file.

**Why this blocks.** NFR-021 permits only Q-prefix synthetic callsigns in version control, with
`PD2FZ` and public figures as the standing exceptions. The file contains **one** allowed exception
(`PD2FZ`) and one already-synthetic call (`Q1OFZ`); the remainder are real third-party stations
across a dozen countries. This is the GDPR/privacy policy, not a style rule, and committing the
file publishes personal data of people who never consented to appear in this repository.

**Why it matters more than usual here.** The document's own opening paragraph says it exists
*"written so none of it gets lost"* — a crash diagnosis, a multi-hour QRM investigation, a second
receiver built live, a protocol bug found and partly fixed. Its cross-references point into
`artefacts/`, which is git-ignored. **It is the only durable record of that session, it is
untracked, and it cannot be committed in its current form.** Both halves of that are true at once,
which is exactly why it needs deciding rather than deferring.

**What QA should do — my recommendation, QA's call:**

1. **Scrub, don't discard.** Substitute Q-prefix synthetic callsigns consistently throughout, so
   the narrative still reads and any station referenced more than once stays traceable within the
   document. Keep `PD2FZ`.
2. **Add a short note at the substitution point** recording that real calls were replaced under
   NFR-021 and that the unredacted original remains in git-ignored `artefacts/` — so a later
   reader knows the text was altered and where the ground truth lives.
3. **Regenerate `session_log.html` from the scrubbed markdown** rather than editing the HTML
   separately. Two hand-edited copies of the same content will diverge.
4. **Re-screen after scrubbing, before committing.** A single missed call is a violation.

**A caution on the screen itself.** I found these with a callsign-shaped regex, which is a *screen,
not a proof*. It will miss unusual formats and produces false positives (it flagged several
non-callsign tokens). QA should not treat my sweep as authoritative in either direction — re-run
it properly as part of the scrub.

## 2. The rest of `2026-07-28-031fb37/` — commit

The other 16 files are **two bands' ANOVA reports** (`anova_report_10m.*`, `anova_report_20m.*`)
plus their scatter/residual PNGs. I screened the markdown: **aggregates only, no callsigns.**
Consistent with every other committed ANOVA report in `qa/endurance/`.

These are HK-016 material — a live run's gathered artefacts — and they belong in the repo. ~1.4 MB
including PNGs, in line with the already-committed `2026-07-29-489135a/` set.

**Sequencing:** these can be committed independently of §1 if the scrub needs more time. Do not
hold clean evidence hostage to a redaction task.

## 3. `qa/external-reporting-single-connection-live-verify/` — screened clean, QA to confirm

16 files, ~351 KB: leader/follower `config.json`, the reference data files
(`callsign-grammar.json`, `callsign-regions.json`, `frequencies.json`, `prop-modes.json`),
two `console.log`s, two daemon logs, and two config snapshots
(`leader-config-before.json`, `leader-config-disabled.json`).

**Screened for callsigns: zero found.** The logs record decode *counts*, not decode *content* —
lines of the form `Cycle 16:37:45: 24 decode(s) found, elapsed=454 ms.` No message text is
written at this log level. Same caveat as §1: my screen is a screen, and QA should confirm rather
than inherit my result.

**Why it is worth keeping.** This is the evidence base for the
`external-reporting-single-connection` live verification, and I found **no committed write-up of
that verification** anywhere in the repo. It is also the session that produced the open
GridTracker2 multicast question — whether GridTracker2's native `Multicast?` receive mode could
have solved the single-logical-connection problem more simply than the shipped leader/follower
relay. That question currently exists only as a note outside the repo. **Raw configs with no
write-up are weak evidence**; if QA has the context to add even a short `README.md` saying what was
verified and what was concluded, the commit is worth several times as much.

**One thing to check before committing:** whether any `config.json` contains a real operator
callsign in its station settings. Config files are the obvious place for one and my screen covered
the logs. Not a reason to hold the commit, just a five-second look.

## 4. The three `2026-07-28-supervisor-*.sh` — safe to discard, QA's call

I checked these specifically because HK-013's addendum says the log-rotation guard must be ported
forward whenever that supervisor template is copied, and a lost guard would be a real regression.

**It is not at risk.** Verified:

| script | rotation guard | tracked |
|---|---|---|
| `2026-07-29-supervisor-40m-overnight.sh` | ✓ present | **committed** |
| `2026-07-29-supervisor-20m-capture-overnight.sh` | ✓ present | **committed** |
| `2026-07-28-supervisor-40m-overnight.sh` | ✓ present | untracked |
| `2026-07-28-supervisor-80m-overnight.sh` | ✓ present | untracked |
| `2026-07-28-supervisor-10m.sh` | ✗ absent | untracked |

The guard is preserved in two committed scripts. The 07-28 copies are superseded predecessors and
the 10m one predates the fix entirely. **Nothing is lost by discarding all three.** If QA prefers
to commit them as historical record that is harmless — but they should not be committed *because
of* the guard, since that reasoning would be false.

## 5. Push — this is the actual "not losing stuff" ⟨route to the Captain⟩

**`main` is 18 commits ahead of `origin/main` and none of it has been pushed.**

That includes the entire Measurement D result, the task-4 evidentiary chain, the Measurement A
correction, the defect-report update, the rev2 decomposition, the withheld-figures correction, and
the work order at `ed8fed3`. **All of it exists on one disk.** Committing the untracked material in
§1–§4 adds to that pile without reducing the exposure.

Untracked files and unpushed commits are the same risk with different labels, and the unpushed
commits are the larger share by far.

**Per HK-014 I neither push nor merge nor ask for it** — raising it is QA's to route to the
Captain, and per HK-010 the sign-off is needed every time. Per HK-012 I am flagging it rather than
letting it lapse.

## 6. The merge sequence — the gate tested the wrong tree

**The `pre_merge_check.py` run that returned READY does not cover the drift fix.** Verified
mechanically:

- It ran on `main`. `git log origin/main..main -- src/` is **empty** — `main` carries **zero
  `src/` changes**.
- The fix (`CycleFramer.cs`, 61 lines) and **both oracle test files**
  (`CycleFramerClockDriftOracleTests.cs`, 224 lines; `CycleFramerDialFreqLazyResyncOracleTests.cs`,
  86 lines) exist **only** on branch `fix-cycleframer-clock-drift-boundary-resync`.
- Therefore *"Solution build (Release) PASS"* built code without the fix, and the **1,408 tests do
  not include either oracle** — the two files written specifically to prove the Critical defect is
  dead.

Every gate result on that run is true. None of it says anything about the drift fix. **READY there
means the documents are ready.**

**Second problem:** the branch is **6 commits behind `main`**. Even pointed at the right tree, a
gate run on it today would test a state that will never exist.

**The sequence that produces a meaningful gate result** — QA's to execute and route, not mine:

1. Land §1–§4 on `main`.
2. Push `main` (§5) — Captain's sign-off, HK-010.
3. Merge `main` into `fix-cycleframer-clock-drift-boundary-resync`, resolving as needed.
4. **Re-run `pre_merge_check.py` on that branch** — on the Captain's trigger only (HK-006), never
   QA's judgement call. Confirm the test count rises by the two oracle files' worth and that the
   oracles actually appear in the run.
5. PR the branch → `main`. Captain reviews the diff before push per HK-011; sign-off per HK-010.

**Two notes for the PR description**, both reasoning a later maintainer will otherwise "simplify"
away — carried forward from `1356` §3 unchanged:

- The resync is **lazy** (at the next window's first sample) rather than eager (at window close),
  because time lost to a slow crystal *or to a silently dropped chunk* has not elapsed yet at
  window close. That covers both failure paths, not just the crystal.
- `5c283da`'s `windowDialFreq` fix exists **because** the resync is lazy — the snapshot timing had
  to move with it. It is not an unrelated tidy-up and must not be dropped from the PR.

## 7. Not on QA's list

- **The merge decision itself** is the Captain's (HK-010), and the Captain has stated the intent to
  proceed. Nothing above argues against it — §6 argues only that the gate has not yet been run
  against the thing being merged.
- **`pre_merge_check.py` runs on the Captain's trigger only** (HK-006). Nothing in §6 authorises
  QA to run it, and it must never appear on a Developer checklist.
- **The `1356` queue** — drift screen, then arm S.1 — is unaffected and resumes after this lands.
  S.1's authorisation question in `1356` §0 is still open with the Captain.
- **`d001-c4-min-score-sweep`'s disposition** (`1356` §4) remains open and is not part of this.

## 8. Boundaries

- **No `src/`** in anything above (HK-011). §6 routes an already-built diff; it does not touch it.
- **No push, no merge** by me (HK-014/HK-010), and I do not ask — §5 and §6 are QA's to route.
- **No `pre_merge_check.py`** by me (HK-006).
- **NFR-021 governs §1, §2 and §3.** The scrub in §1 is a precondition of commit, not a follow-up.
  This document deliberately does not reproduce the offending callsigns.
- **Per HK-015 this is Architect → QA.** `dev-tasks/*.md` and the PR body are **QA's to author**.

## 9. Cross-references

- `2026-07-31-1356-…-work-order-after-measurement-d.md` — the standing queue, unaffected; §3 there
  is the same push sign-off as §5/§6 here.
- `qa/endurance/2026-07-28-031fb37/session_log.md` — §1's blocker; the file whose stated purpose is
  that nothing gets lost.
- `qa/endurance/2026-07-29-supervisor-40m-overnight.sh` — §4's proof the rotation guard is safe.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — the Critical defect §6's fix closes.
- HK-016 (gather live-run artefacts), HK-013 addendum (rotation guard), NFR-021 (callsign policy),
  HK-006/HK-010/HK-011/HK-014 (gate, sign-off, `src/`, and my own limits).

---

*Per HK-015 this is Architect → QA; every item is QA's to do or route. Per HK-014/HK-010 committed
locally, no push, no merge — and per HK-012 §5 is raised rather than left to lapse. Per HK-011
nothing here touches `src/`. Per HK-017 filename and byline carry `date -u` UTC. Per HK-018 §1's
callsign finding, §4's rotation-guard table and §6's empty-`src/`-diff claim were each read from
the files and from git, not assumed — and §1 and §3 both state plainly that a regex screen is a
screen and not a proof.*
