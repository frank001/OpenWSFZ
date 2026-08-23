# QA — NFR-021 `livecopy-preclear` delete + 151-file historical audit

**2026-08-23 19:54Z**, QA (AI-assisted). Captain's direct instruction: "do NFR-021
livecopy-preclear delete + the 151-file historical audit" — the item the Architect has
recommended running FIRST since the 2026-08-23 11:02Z board entry, as the only open item with
irreversible external exposure on a public repo (`github.com/frank001/OpenWSFZ`, confirmed
public).

## 0. Scope of "151"

Not asserted from memory — mechanically derived and confirmed exact:

```
git log --all --pretty=format: --name-only | sort -u \
  | grep -iE '(owsfz-all\.txt|wsjt-all\.txt|linux-all\.txt|windows-all\.txt)(\.[A-Za-z0-9_.-]+)?$|_matched\.csv$|livecopy-preclear|(^|/)ALL\.TXT$' \
  > risky_union.txt        # 152 distinct paths ever touched, any ref
git ls-files | grep -F -f risky_union.txt   # 151 of those 152 are tracked in HEAD right now
```

**151 = the count of currently-tracked files** matching the ALL.TXT-derived risk-pattern family
(raw `owsfz-all.txt`/`wsjt-all.txt`/`linux-all.txt`/`windows-all.txt` copies, and every
`*_matched.csv`, per the standing note that matcher output carries full `message_text` — see
`rr-study-matched-csv-nfr021-contamination.md`). The 152nd path is historical-only (removed from
tracking, discussed in §2 — the most severe finding of this audit).

## 1. Part A — the `livecopy-preclear` file: DELETED

`qa/rr-study/results/2026-08-21-7d36038/owsfz-all.txt.livecopy-preclear` — untracked, correctly
gitignored since `19cea09` (`.gitignore:172`), byte-identical (`sha256 d99d9a91…`) to the
already-ignored `owsfz-all.txt` beside it. Verified identical before deleting so nothing
non-duplicated was lost. Deleted this session. Nothing to commit — it was never tracked.

## 2. Part B — the 151-file audit: CONTENT, not just filenames

Filename matching alone doesn't establish exposure — the file has to actually be checked for
real callsign-shaped content, per the RUNBOOK §7.5 pattern (`grep -oE
"\b[A-Z]{1,2}[0-9][A-Z]{1,3}\b" | grep -viE "^Q[0-9]"`) already established in the matched-CSV
note. Ran it (plus a broader variant allowing a leading digit and a `/suffix`, to rule out the
narrower pattern hiding anything) against all 151 tracked files. Both passes agree exactly.

**119 of 151 files: clean.** No non-Q-prefix callsign-shaped token, either pattern.

**32 of 151 files: contaminated**, across 7 distinct run-directories, all currently present in
`HEAD`/`main` right now (not just history):

| Run directory | Files | First-added commit | Date |
|---|---|---|---|
| `2026-06-20-6e821fa` | `owsfz-all.txt` + 8× `S*_matched.csv` = 9 | `97efa61` | 2026-06-20 |
| `2026-06-20-8eea3c4` | `owsfz-all.txt` + `S5_matched.csv` = 2 | `239de31` | 2026-07-03 |
| `2026-06-20-d40b4cd` | `owsfz-all.txt` + `S5_matched.csv` = 2 | `239de31` | 2026-07-03 |
| `2026-06-22-f11f438` | 8× `S*_matched.csv` | `de2c1e3` | 2026-06-22 |
| `2026-07-01-b03998f` | `linux-all.txt` + `windows-all.txt` + 7× `S*_matched.csv` = 9 | `e94beff` | 2026-07-01 |
| `d009-k10-confirm-s7-clean` | `S7_matched.csv` | `7426723` | 2026-06-21 |
| `d009-k10-confirm-s7` | `S7_matched.csv` | `c8a2939` | 2026-06-22 |

All 32 carry the same signature already on record in the standing privacy note (plausible,
ITU-shaped, non-Q-prefix callsigns sitting in the callsign field of a decode line, e.g.
`SZ8LL A0UDS/R R BH04`) — consistent with low-`K_MIN_SCORE` OSD noise-floor false-decodes, the
documented mechanism, not confirmed real transmissions. **NFR-021 makes no distinction on
provenance** — an assignable-pattern callsign is in scope regardless of whether the decode was
real or noise-manufactured — so these 32 are confirmed violations independent of that question.

⚠️ **`c8a2939`'s own commit message is "NFR-021 scrub"** and it still introduced a contaminated
file (`d009-k10-confirm-s7/S7_matched.csv`, 3 tokens) — the historical scrub passes were
incomplete even on the commit that explicitly claimed to be doing this exact job.

**Not yet remediated** — this audit is a finding, not a fix. Two remediation layers are
distinct and the Captain's call on each is needed separately:
1. **Untrack from `HEAD`** (`git rm --cached`, ordinary reversible commit) — stops the 32 files
   from being visible in the *current* tree. Cheap, safe, does not touch history.
2. **Purge from history** — the 32 files' content is still reachable via `git show <commit>:<path>`
   on `main`'s own ancestry for anyone who clones full history. Requires `git filter-repo`/BFG +
   force-push, invalidates every existing clone/fork, and is the same class of operation as the
   two prior "history rewrites" — see §3 for why that precedent is not reassuring.

## 3. Critical finding — NOT part of the 151, more severe than all of it combined

`p12-ft8lib-port_UAT-01_items/WSJT-X ALL.TXT` — the 152nd path, historical-only (no longer
tracked in `HEAD`). This directory is one of the three named in the standing privacy note as a
**real off-air corpus** ("`p10-decoder-ground-truth_items/`, `p12-…_UAT-01_items/`,
`p16-cat-control_items/` contain real calls → git-ignored, never commit"). Unlike the 32 files
above, this is not a noise-floor artefact question — it is on-record as genuine third-party data.

- Added `50a7d28` (2026-05-30, "`fix(p12): R5 — noise-floor-based SNR calibration in
  ft8_shim.c`"), removed from tracking one day later by `278e4f3` (2026-05-31, "`chore: remove
  p12-ft8lib-port_UAT-01_items from tracking and gitignore`").
- **5,217 lines, 337,465 bytes, 386 distinct callsign-shaped tokens** in the committed blob
  (counted, not printed — this audit does not reproduce real third-party callsigns in a
  committed artefact, consistent with the board's own standing practice after the
  quote-5-real-calls near-miss).
- `git merge-base --is-ancestor 50a7d28 main` → **YES**. `git branch --all --contains 50a7d28`
  and `git branch -r --contains 50a7d28` both show it reachable from **`origin/main`** — i.e.
  this is **live on the public GitHub repo right now**, not a dangling/unreachable object subject
  to ordinary `gc`.
- Both documented rewrites (2026-06-06 PII scrub; 2026-06-12 invalid-run purge) postdate this
  commit and **did not catch it** — it survived both. The privacy note's belief that "git history
  rewritten twice" closed this class of exposure is **not accurate for this specific file**.
- Exposure window if unaddressed: 2026-05-30 to today (2026-08-23) = **~85 days on a public
  repo**, current.

This is the single item the Architect's "run this first" framing was actually about, and it is
worse than the framing anticipated — a real, not noise-floor, third-party corpus, still
live, having already survived two supposed cleanups.

## 4. What this audit did NOT do

No git history rewrite, no force-push, no `git rm --cached` commit. Both remediation paths in
§2 point 2 and §3 require rewriting `main`'s history and force-pushing to a public origin with
15+ open branches and tags back to `v0.11` — every one of those refs would need rebasing onto
the rewritten history or would silently keep the exposed blob reachable through itself. That is
squarely the kind of irreversible, multi-branch-blast-radius decision this project's standing
practice (HK-010, HK-014, and the board's own "the FILE itself is left on disk — deleting it is
the Captain's call" for a far smaller case) reserves for explicit Captain sign-off, not something
QA actions unilaterally. Findings only, below.

## 5. Recommendation (QA proposes, does not decide)

1. **§3 (the p12 real-corpus leak) is the priority** — it is real personal data, already public
   for ~85 days, and the belief that it was already handled is the thing this audit corrects.
2. Before any history rewrite: enumerate every ref (branches + tags) that would need rebasing —
   `git branch --all --contains 50a7d28` above already lists ~35 of them — and confirm whether
   any external fork/clone is known to exist (if none, the blast radius is `origin` + local only).
3. `git filter-repo --path "p12-ft8lib-port_UAT-01_items/WSJT-X ALL.TXT" --invert-paths` (plus
   the 32-file list from §2 in the same pass, since both need the same force-push) is the
   standard tool for this; BFG is the alternative. Either needs a full `git push --force` to
   `origin` across every affected ref, plus telling GitHub support the old commits should be
   purged from their side (a force-push alone does not guarantee GitHub drops cached/forked
   copies).
4. Separately from the history question: §2's 32 files can be `git rm --cached` from `HEAD` today
   as a cheap, fully reversible interim step regardless of what's decided about history — this
   stops the count of currently-visible-in-tree violations at 0 while the harder history decision
   is pending.
