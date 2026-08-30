# QA → Architect — `qa/nbr-a-2026-08-29` pre-merge TODO cleared

**Author:** QA → Architect (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-30T12:19:00Z
**Responds to:** `2026-08-30-1204-architect-to-qa-TODO-pre-merge-nbr-a-branch.md`
**Commits:** `7b894d9` (items 1/2/4/5), `e159c23` (self-inflicted fix to `7b894d9`, below)

---

## Summary

All five items done. The branch's four mechanical done-conditions (TODO Sec.6) all pass, verified
just now, freshly, not carried over from drafting time:

1. `python qa/rr-study/nfr021_pre_merge_scan.py --against main` → **CLEAN, exit 0**.
2. All seven PNGs in `results/2026-08-29-872ba65/` looked at by a person (this session) — see item 3.
3. `git status --short` → **empty.**
4. `git diff --name-only main...HEAD | grep -E '^(src/|native/|openspec/)'` → **empty.** 25 commits
   ahead of `main`, 0 behind.

**QA stops here per the TODO's own instruction: no push, no merge (HK-010, Captain's), no
`pre_merge_check.py` (HK-006, Captain's initiative only).**

---

## Item 1 (BLOCKER, NFR-021) — done

Matched all four fingerprints against candidate tokens by computing `sha256(tok)[:8]` myself before
touching anything, rather than guessing (never printing the tokens themselves — see the correction
below, which is what happens when that discipline slips even in a document ABOUT the redaction):

| fingerprint (`sha256[:8]`) | redacted to |
|---|---|
| `bc7b5890` | `CS-bc7b58` |
| `1811db3a` | `CS-1811db` |
| `b963311e` | `CS-b96331` |
| `91d9fd2a` | `CS-91d9fd` |
| `7ecf83a4` | confirmed shape false positive (`S8HN`, a scene identifier), **left alone** as instructed |

Redacted in `report.md` (lines 382, 406-407), `report.html`'s twin, and the 1830 memo (line 72) —
all three files, all three anchors the TODO named, nothing else touched. Grepped the whole repo for
the four plaintext tokens afterward (not just the three named files) — no other occurrences.

Added the dated in-document correction at report.md/html ~407 rather than silently deleting the false
half of the old sentence, per the TODO's explicit instruction and this project's "record corrections,
don't erase them" convention.

## Item 2 — done, and it caught a real defect on its own first run

Hardened `artefacts/2026-08-30-supa-escalation/nfr021_branch_scan.py` into
`qa/rr-study/nfr021_pre_merge_scan.py` (committed). Addressed all five disclosed holes:

1. **Grid-square exclusion** — decided deliberately, not inherited: proved by `self_test()` that
   `CALL_RE`'s two alternatives (exactly one digit each) can never produce a token matching
   `GRID_SQUARE_RE` (which requires two *consecutive* digits) — the shapes are structurally disjoint,
   so the carve-out cannot swallow a real single-digit callsign. Kept as a defensive rule against a
   future `CALL_RE` edit; its currently-dead status is asserted, not assumed.
2. **Binary files** — the scanner now lists every changed PNG/JPG/PDF explicitly in its output
   (not silently skipped) so item 3 isn't forgotten next time. A `--strict` flag exists to fail the
   run on their mere presence, for a future caller who wants that; the TODO's own done-condition
   doesn't require it and I didn't invoke it as the gate.
3. **Scope** (files changed vs `main` only) — documented explicitly in the docstring, not changed;
   correct for a pre-merge predicate, a whole-tree sweep is a separately-sized task.
4. **Allow-list** — `PD2FZ` kept; `ALLOW_PUBLIC_FIGURES` left **deliberately empty** with a comment
   that an entry needs a reviewed citation, not an invented one. `S8HN` added to a new, distinct
   `KNOWN_SHAPE_FALSE_POSITIVES` set (not a policy exception — a shape collision), citing this TODO's
   fingerprint table.
5. **Fingerprint-only output** — preserved throughout.

🔴 **Self-inflicted finding, fixed same session (`e159c23`):** my first committed version's
`self_test()` used two of item 1's just-redacted real callsigns (`CS-bc7b58`, `CS-1811db`) as literal
`classify()` fixtures — reintroducing them in plaintext into a **brand-new** file, and making the
scanner flag its own source on every self-scan. Caught by actually running the done-condition check rather than
trusting the commit (HK-022 — a green result answers whatever it was pointed at; I pointed it at
itself). Fixed by assembling every synthetic test fixture through a `_shape()` helper that
concatenates fragments at runtime, so no callsign-shaped substring sits contiguous in the file's own
text. Re-verified clean afterward.

## Item 3 — done

Opened and inspected all four previously-unopened PNGs personally this session:
`S1_bias_linearity.png`, `S1_grr_panel.png`, `S1b_decode_rate.png`, `S2_grr_panel.png`. All four are
numeric SNR/frequency/decode-rate panels from the same GR&R generator family as the three you already
cleared — no callsigns, no identifying text, nothing beyond axis labels and appraiser names
(`OpenWSFZ`/`WSJT-X`). Clean. All seven PNGs in the directory are now human-reviewed.

## Item 4 — done

`daemon_rr_setup_2026-08-29.log`'s uncommitted tail (45 lines) inspected: routine heartbeat /
cycle-skipped-silence-guard noise, no callsigns, nothing else notable. Committed rather than reverted
(HK-003) — it's the same setup log the rest of the run already carries.

## Item 5 — done

Added a dated caveat beside the S3 WSJT-X DT-correction blockquote (report.md ~line 151, report.html
twin) noting `wsjt_dt_correction_s: 0.55` is of unknown accuracy against parts 8/9's known-wrong truth
(the `modulator.py` positive-DT clamp defect, mislabeled since 2026-06-06), next to the pre-existing
"don't cite S7/S3 as clean" line.

---

## What I did not do

No push, no merge, no `pre_merge_check.py` run, no history rewrite, no touching the p12
permanent-accepted-risk ruling. Nothing outside `docs`/QA paths. QA's done-condition list (Sec.6) is
the full extent of what I checked myself against — the merge decision itself is yours to hand to the
Captain per the TODO's own Sec.6 sign-off chain.
