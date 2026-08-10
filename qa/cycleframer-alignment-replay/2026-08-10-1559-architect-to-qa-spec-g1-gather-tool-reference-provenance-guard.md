# Architect → QA — spec G1: the gather tool silently duplicated one WSJT-X instance

**2026-08-10 15:59Z** (filename and byline both from `date -u`, HK-017).
**Author:** Architect. **Audience:** QA (HK-015).
**Status:** defect spec + fix requirements. **Blocks nothing, but X0 depends on §3.1.**

---

## 0. Routing — the Captain's ruling, recorded

I flagged this as HK-011 `tools/` work needing a Developer session. **The Captain has ruled it is
QA tooling, no Developer session required.** Recorded here so the decision is visible rather than
inferred; QA implements directly. **Merge to `main` still needs the Captain's explicit sign-off
(HK-010), and I neither push nor merge (HK-014).**

---

## 1. The defect, established from the code — not from the symptom

**Symptom.** The two 80m gathers contain the *same* WSJT-X reference:

```
20260809_live_run_0155-8080-80m/wsjt-x/ALL.TXT   inode=281474977087507 links=2
20260809_live_run_0155-8081-80m/wsjt-x/ALL.TXT   inode=281474977087507 links=2
```

Identical inode, identical md5, size 706 943. The 20m and 17m pairs are correct — distinct files,
distinct sizes, distinct hashes.

**Mechanism.** `tools/gather_live_run_artefacts.py`:

- **`--wsjtx-link-from`** (arg at line 870, implementation `link_or_copy_wsjtx_from`, line 353) is
  a *deliberate* feature. Its documented premise is stated at lines 75–98: **"Two OpenWSFZ
  instances sharing one physical WSJT-X install."** Under that premise it is correct and valuable —
  it hardlinks rather than re-copying multiple GB, and the 2026-07-31 Angle 1 corpus uses it
  legitimately (one instance, gathered into two folders, annotated as such in the inventory).
- On the 80m leg **the premise did not hold** — there were **two** live instances, `WSJT-X -
  FT991A` and `WSJT-X - FT991A-Copy`. Linking 8081's reference from 8080's gather therefore
  materialised FT991A **twice** and FT991A-Copy **not at all**.
- 🔴 **Nothing in the tool checks the premise, and nothing in the artefact records which instance
  was read.** `contents.md` (lines 751–753) says only *"WSJT-X's decoded-message log"* and *"WAV
  recordings from WSJT-X's own `save/` directory"* — **no source path, no instance identity, no
  hash.** The one place provenance is emitted is a `print()` to the console (line 1002), which is
  not part of the artefact and is gone the moment the terminal closes.
- ⚠️ Aggravating: **`--wsjtx-root` defaults to `%LOCALAPPDATA%\WSJT-X`** (line 959) — the *plain*
  install, which is not either of the instances actually in use. Every leg must pass it
  explicitly; a leg that forgets gathers a wrong-and-probably-stale directory with no complaint.

**This exact failure mode has already bitten this tool once, on the other side of the fence.**
`--owsfz-config`'s own help text (lines 845–858) exists because *"the old global-only lookup
silently returned the SAME [config]"* for two instances. **The fix shape is already in the file;
it was simply never applied to the WSJT-X side.**

⇒ **Classify this as a missing guard and missing provenance, not as a bug in hardlinking.**
🛑 **Do not remove or weaken `--wsjtx-link-from`** — it is correct under its premise and saves
multiple GB per pair.

---

## 2. Blast radius

**Verified by instance identity, not merely by file distinctness** (method in §5.1 — the Captain
asked the right question: *"did it also fail for 20m and 17m?"*, and "the two files differ" does
**not** answer it):

| corpus | matches FT991A | matches FT991A-Copy | status |
|---|---:|---:|---|
| 20m-8080 | **100.00%** | 44.00% | ✅ FT991A |
| 20m-8081 | 44.01% | **100.00%** | ✅ FT991A-Copy |
| 17m-8080 | **100.00%** | 45.96% | ✅ FT991A |
| 17m-8081 | 45.93% | **100.00%** | ✅ FT991A-Copy |
| 80m-8080 | **100.00%** | 38.57% | 🔴 FT991A |
| 80m-8081 | **100.00%** | 38.57% | 🔴 **FT991A again — the defect** |

⇒ **The defect is isolated to the 80m pair. 20m and 17m each gathered two genuinely different
instances and are sound.** The 2026-07-31 Angle 1 pair is hardlinked **legitimately** (only one
instance existed) and is annotated as such in the inventory.

⚠️ **Do not misread the ~44% column.** That is *whole-line* matching, including the per-instance
SNR/DT/frequency fields, which naturally differ between two receivers. On the `(ts, message)` key
the two instances agree ~99.8%. The 44% figure is an **identity fingerprint**, not an agreement
statistic, and must never be quoted as one.

⚠️ Minor, unexplained, non-blocking: the 17m live logs each contain **18–19 lines** inside the
window that the gather did not capture (0.05%); 20m and 80m are exact at 0. Likely a window/pad
boundary detail. Worth one look during §3, not a blocker for anything.

✅ **The originals survive** — `%LOCALAPPDATA%\WSJT-X - FT991A-Copy\ALL.TXT` covers the 80m window
with **10 942 Rx FT8 lines over 1 196 cycles**, distinct from FT991A's 10 952 / 1 197. No data was
lost; only the gather is wrong.

⚠️ **The inventory already detects the condition** (`qa/ARTEFACT_INVENTORY.md` prints
**HARDLINKED** for the 80m pair). What it cannot do is tell **intentional sharing** from
**accidental duplication** — because the artefact records no provenance. That is the gap.

---

## 3. Required changes

### 3.1 Repair the 80m artefact (shared with X0 — do it once)
Gather FT991A-Copy's window slice into `20260809_live_run_0155-8081-80m/wsjt-x/`, replacing the
hardlink. Preserve the existing file (rename, do not delete) until the replacement verifies.
Regenerate the inventory, confirm `--check` clean and the **HARDLINKED** annotation on the 80m
pair is gone. Verified expectation: repaired `A∩B` = **10 913 raw / 10 839 clean**.

### 3.2 Record provenance in the artefact (the core fix)
`contents.md` must state, for the WSJT-X side:

- the **resolved absolute source path** (`--wsjtx-root`, or the `--wsjtx-link-from` sibling);
- whether the ALL.TXT was **read live, copied, or hardlinked**, and from where;
- the **SHA-256 and line count** of the gathered `ALL.TXT`;
- the same for the OpenWSFZ side, for symmetry.

**Acceptance:** reading `contents.md` alone must be enough to answer *"which WSJT-X instance is
this?"* without stat-ing inodes. Today it is not.

### 3.3 Guard the premise
When `--wsjtx-link-from` is given, the tool must **enumerate candidate live WSJT-X instance
directories** (siblings of `--wsjtx-root`'s parent matching `WSJT-X*`) and count how many contain
an `ALL.TXT` with **at least one decode inside the session window**.

- More than one ⇒ **refuse and exit non-zero**, naming the candidates found, with a message
  pointing at this defect.
- Override only via an explicit affirmative flag — e.g. `--wsjtx-shared-install` — which must be
  **recorded in `contents.md`** as an operator assertion.

**Rationale:** the premise is unverifiable from inside one invocation, so make it an assertion the
operator has to make on the record rather than a silent default (HK-021's "make it mechanical").

### 3.4 Post-gather sibling assertion
After writing, if another gather exists under the same `--out-root` whose window overlaps and
whose `wsjt-x/ALL.TXT` is byte-identical or the same inode, **print a prominent warning** unless
`--wsjtx-shared-install` was passed. Cheap, and it catches the general case rather than only the
`--wsjtx-link-from` path.

### 3.5 Make the default honest
Either drop the `%LOCALAPPDATA%\WSJT-X` default for `--wsjtx-root` and require it explicitly, or
**warn loudly** when the default is used and a `WSJT-X - *` sibling exists that has decodes in the
window while the default does not. QA's call which; state the reasoning in the PR.

### 3.6 Teach the inventory the difference
`qa/artefact_inventory.py` should render the **HARDLINKED** annotation differently once provenance
exists: *intentional shared install* (operator asserted) vs. **unverified duplicate**. If
provenance is absent — every corpus gathered before this fix — it must say **"provenance not
recorded"** rather than implying either.

---

## 4. Tests

🔴 **There are currently no tests for this tool at all** (no `tools/tests/`, nothing under `tests/`
matching it). Add a minimal set alongside the fix — this is a tool the whole corpus depends on:

1. `--wsjtx-link-from` with **two** window-active instance dirs present ⇒ exits non-zero, names
   both candidates.
2. Same, plus `--wsjtx-shared-install` ⇒ succeeds, and `contents.md` records the assertion.
3. `--wsjtx-link-from` with **one** window-active instance dir ⇒ succeeds, hardlinks, and
   `contents.md` records the source path and hash (the 2026-07-31 case must keep working).
4. Provenance block is present and hash matches the file actually written.

Use `--dry-run` and a `tmp_path` fixture where possible; do not require a live WSJT-X install.

⚠️ **A second copy of this script exists** at
`.claude/worktrees/w1-sec5-calibration/tools/gather_live_run_artefacts.py`. Check whether that
worktree is still needed; if it is, note the divergence rather than letting two copies drift.

---

## 5. Retro-audit — cheap, do it once

### 5.1 🔴 Audit on instance IDENTITY, not on file distinctness
An inode/hash check catches only the *exact-duplicate* case. It would **miss** the subtler and
equally fatal one: **the same instance gathered twice at different moments**, which produces two
files that differ (a few appended lines) while still being one instrument. The inventory's
**HARDLINKED** detector cannot see that case at all.

**Method that does work**, and the one that produced §2's table:

> For each gathered `wsjt-x/ALL.TXT`, take the set of whole `Rx FT8` lines inside the leg's window
> and intersect it against the same window slice of **each** surviving live instance log
> (`%LOCALAPPDATA%\WSJT-X - *\ALL.TXT`). The true source scores ~100%; every other instance scores
> far lower. Two legs of a pair resolving to the **same** instance is the defect.

Limitation to state in the report: this works only while the live logs still cover the window.
They do today. **That is exactly why §3.2's provenance block matters — it makes the audit
unnecessary in future by recording the answer at gather time.**

### 5.2 Scope
Run §5.1 across **every** multi-leg corpus in `artefacts/`, not just the weekend ones, and record
the result in the inventory's notes. Three pairs are already resolved (07-31 intentional, 08-08
20m and 17m sound, 08-09 80m defective); the audit is to confirm there is no fourth. Where the
live logs no longer reach back far enough, record **"not verifiable"** — not "clean". **Report
counts and paths only** — NFR-021.

---

## 6. Out of scope

- 🛑 Any change to how OpenWSFZ itself captures or decodes. This is gather tooling only.
- 🛑 Re-gathering corpora that are already correct.
- 🛑 Removing or redesigning `--wsjtx-link-from` (§1).
- 🛑 Proposing a capture run. The originals survive; nothing needs re-recording.

---

## 7. Deliverables

1. The fix in `tools/gather_live_run_artefacts.py` + tests (§4).
2. The 80m repair (§3.1) and a regenerated `qa/ARTEFACT_INVENTORY.md`, `--check` clean.
3. The retro-audit result (§5) in the inventory notes.
4. An addendum to `hk016-gather-live-run-artefacts-standard.md` recording the failure mode: **a
   gather that silently produces two identical "instances" defeats every arm that assumes two, and
   the artefact must carry its own provenance.**
5. A note in the 80m leg's `contents.md` that the original gather duplicated one instance, and what
   was done about it — the record should show what was believed and when, not just the corrected
   state.
6. 🔴 **Update `BOARD.md` in the same edit** (HK-024).

**Sequencing:** §3.1 is the only part X1/X2 depend on, and it can land first. The tool fix, tests
and audit can follow without blocking either arm.
