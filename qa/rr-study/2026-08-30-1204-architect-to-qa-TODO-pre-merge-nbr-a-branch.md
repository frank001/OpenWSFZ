# ARCHITECT → QA — **TODO**: clear `qa/nbr-a-2026-08-29` for merge, BEFORE `SUP-B` implementation

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-30T12:04:07Z
**Type:** Housekeeping + one **blocker**. **No arm, no gate, no `src/` or `native/` change.**
Ordered by the PO after asking whether the branch should be merged.

---

## Why this comes first

🔴 **`SUP-B` (`2026-08-30-1149-…-spec-f001-sup-b-…md`) touches `src/` and `native/`.** It must not
start on `qa/nbr-a-2026-08-29` — a **closed `NBR-A`** QA branch that has already accumulated `WIN-A`,
the voided 08-29 S1–S8 run, `SUP-A` and `SUP-B`. **The clean sequence is: land this branch, then cut
a fresh branch off `main` for `SUP-B`.** Everything below exists to make that merge safe.

**Branch state, checked 2026-08-30 (Architect, drafting-time):** 22 commits ahead, 0 behind, **61
files, docs/QA only — no `src/`, no `native/`, no `openspec/`.** `main` is an ancestor, so it is a
clean fast-forward. **The merge risk is not code. It is item 1.**

🛑 **What QA does NOT do here:** no push, no merge (that is the Captain's, HK-010 — green CI is
necessary, never sufficient), and **no `pre_merge_check.py`** (HK-006 — Captain's initiative only).
QA prepares the branch and stops.

---

## 1. 🔴 **BLOCKER — NFR-021: four real off-air callsigns are committed in plaintext on a PUBLIC repo**

**Files and anchors:**

| file | occurrences | anchor |
|---|---:|---|
| `qa/rr-study/results/2026-08-29-872ba65/report.md` | 3 lines | **382** and **407** |
| `qa/rr-study/results/2026-08-29-872ba65/report.html` | 3 lines | the rendered twin of the same two passages |
| `qa/rr-study/2026-08-29-1830-qa-to-architect-win-a-rung1-s1s8-result.md` | 1 line | **72** |

**The exact set, given as fingerprints so this document does not itself republish them.** Your scan
must return **these four and no others**:

| fingerprint `sha256(token)[:8]` | verdict |
|---|---|
| `bc7b5890` | 🔴 **REDACT** |
| `1811db3a` | 🔴 **REDACT** |
| `b963311e` | 🔴 **REDACT** |
| `91d9fd2a` | 🔴 **REDACT** |
| `7ecf83a4` | ✅ **DO NOT REDACT — `S8HN`, a scene identifier, a shape false positive.** It also appears in `f-nbr-a/nbr_a.py`, `harness/run_scenario.py` and the 2101 memo; leave all of those alone. |

**Why this is the blocking item and not a nicety.** The repo is **public**. Standing policy
(`privacy-gdpr-callsign-policy.md`, NFR-021) is **Q-prefix synthetic calls only in VCS**, exceptions
`PD2FZ` and public figures. These four are neither.

🔴 **The part worth reading twice, because it is how this slipped past a careful author:**
`report.md:406-407` states that the matched CSVs are *"confirmed still `.gitignore`d and not
committed, so no NFR-021 exposure occurred"* — **and names three of the callsigns inside the very
sentence making that claim.** The statement is true of the CSVs and false of the report quoting
them. **The document asserting no exposure is the exposure.** (The CSVs really are gitignored —
that half was verified and is correct.)

**Do:**

1. Replace each of the four with the project's existing redaction convention — `common_b1.redact()`,
   i.e. `CS-` + `sha256(call)[:6]` — the same form `SUP-A`'s harness already emits. **Keep both
   passages' meaning intact:** 382's point is *"OpenWSFZ decoded a plausible-looking message out of
   pure AWGN"* and 407's is *"off-air callsigns reach per-scenario matched CSVs"*. Both survive
   fingerprints unchanged.
2. **Correct the false half of the 407 sentence rather than quietly deleting it.** Add a dated
   in-document correction noting that the CSVs were indeed gitignored but the report itself named
   the calls, redacted `2026-08-30`. 🛑 **This project records corrections; it does not erase them
   (`WIN-A`, the P2 waiver, my own two over-calls of 2026-08-29 are all on the record).**
3. Regenerate or hand-edit `report.html` so it matches `report.md`. **Mechanically diff the two for
   the four fingerprints — do not assume the regeneration covered both passages.**

🛑 **Scope: this is a working-tree fix on an unmerged branch. It is NOT a history rewrite and NOT a
purge.** The Captain's ruling that the **p12 real-corpus history exposure is a PERMANENT ACCEPTED
RISK** is untouched and must not be re-opened. This is cheap now and impossible to undo after the
branch is public on `main`.

---

## 2. 🔴 Ship the NFR-021 pre-merge check as CODE, not as a one-off (HK-021(r))

**Why:** this class of defect has now fired twice — the `*_matched.csv` contamination already in
`MEMORY.md` (203,920 rows with full `message_text` in one file), and item 1. Both were found by
someone remembering to grep. **A rule that depends on remembering is not a control.**

**Do:** take
`artefacts/2026-08-30-supa-escalation/nfr021_branch_scan.py` (mine, gitignored, drafting-time) as a
**starting point only**, harden it, and commit it under `qa/rr-study/` as a durable pre-merge
predicate that **exits non-zero on any non-compliant token** in the files a branch changes vs `main`.

🔴 **Its known limitations, disclosed rather than left for you to discover — each is a real hole:**

1. **Grid-square exclusion masks real calls.** It drops `^[A-Z]{2}[0-9]{2}$` as a grid square.
   `OE65` sits in the *same line* as two of item 1's calls and was excluded on exactly that rule.
   Special-event calls of that shape exist. **Decide deliberately how to handle this; do not inherit
   my choice silently.**
2. **Binary files are not covered at all** (see item 3).
3. **It only scans files changed vs `main`**, not the whole tree.
4. **The allow-list is minimal** — `PD2FZ` only. The policy's *public figures* exception is not
   encoded and probably should be an explicit, reviewed list rather than a regex.
5. It reports fingerprints, never tokens — **keep that property.** A scanner whose output must
   itself be redacted is a new exposure.

⚠️ **HK-022 while you are at it: ask what error this predicate could NOT detect.** It cannot see a
callsign inside a PNG, inside a `.json` value that is base64, or split across lines.

---

## 3. ⚠️ Eyeball the four PNGs I did not open

**Files:** `qa/rr-study/results/2026-08-29-872ba65/` — `S1_bias_linearity.png`, `S1_grr_panel.png`,
`S1b_decode_rate.png`, `S2_grr_panel.png`.

**Why:** images cannot be grepped, and item 2's scanner will never cover them.

✅ **Already opened and CLEAN (Architect, 2026-08-30) — do not redo these three:**
`S8_band_scene.png` (stations labelled A–L), `S7_recovery.png` (P0–P20 scenario descriptors),
`S3_grr_panel.png` (numeric panels, parts 0–9, appraisers `OpenWSFZ`/`WSJT-X`).

The remaining four are the same GR&R panel family from the same generator and are **very likely**
clean — 🛑 **which is exactly why someone must actually look rather than reason about it.**

---

## 4. ⚠️ Settle the dirty working tree

**File:** `daemon_rr_setup_2026-08-29.log` — modified, uncommitted, and has been since before this
session started. Commit it or revert it (HK-003). A branch should not go to the Captain with an
unexplained modification sitting in the tree.

---

## 5. 📌 One-line caveat in the 08-29 report — cheap, and it protects a future reader

`qa/rr-study/results/2026-08-29-872ba65/report.md` already carries, at line 413, *"Do not cite this
run's S7 or S3 numbers as a clean WIN-A arm result"* — **good, and it is why this is a 📌 and not a
🔴.**

**Add beside it:** that S3's numbers are computed against **known-wrong truth for parts 8/9** (the
`modulator.py` positive-DT clamp defect, mislabeled since 2026-06-06), and that
`wsjt_dt_correction_s: 0.55` — applied and described at line 151 — is of **UNKNOWN ACCURACY**.

**Why bother:** once merged, that file is the durable artefact and will be read by someone who never
sees the commit message that explains it. **A commit message is NOT a ruling.**

---

## 6. Then hand it to the Captain

**QA's done-condition, all four mechanical:**

1. item 2's committed scanner exits **0** on the branch;
2. the four PNGs of item 3 have been **looked at** by a person, and that is stated;
3. `git status` is clean;
4. `git diff --name-only main...HEAD` still shows **no `src/`, `native/` or `openspec/` path**.

**Then stop and report.** The merge itself needs the **Captain's explicit sign-off** (HK-010), his
own `pre_merge_check.py` run (HK-006), and the OpenSpec pre-merge audit (HK-002). **The Architect
neither pushes nor merges, and does not ask to (HK-014).**

➡️ **After the merge: cut `SUP-B`'s branch fresh off `main`.** `SUP-B` Sec.9.1 flags this; landing
this branch is what resolves it.

---

## Cross-references

- `qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md` —
  the work this unblocks; Sec.9.1 carries the branch flag.
- `privacy-gdpr-callsign-policy.md` (memory) — NFR-021, the Q-prefix rule and its two exceptions.
- `rr-study-matched-csv-nfr021-contamination.md` (memory) — the prior firing of this same class.
- `2026-08-29-1958-architect-to-qa-TODO-housekeeping-items.md` — the precedent for this document's
  form.
- `artefacts/2026-08-30-supa-escalation/` — the drafting-time scans behind items 1 and 3
  (gitignored, **not a gate**).
