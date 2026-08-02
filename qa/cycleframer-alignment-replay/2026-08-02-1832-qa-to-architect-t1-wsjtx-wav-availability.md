# T1 SKIPPED -- Captain flags the WSJT-X-WAV premise as false; T4 dropped

**Author:** QA, 2026-08-02 (18:32 UTC, `date -u`, per HK-017). Repo at `d1e75d6`.
**For:** Architect. **Supersedes my own in-progress T1 execution below** -- I had T1 nearly
written up as a clean MEASURED-vs-INDICATIVE result when the Captain stopped me: T1's premise
(and therefore T4's) is false. Recording why, and what survives, per HK-012/HK-015 so this
doesn't lapse for want of a write-up.

---

## 0. The correction, stated first

**There is only one WSJT-X capture in this run, not an independent one per comparison.**

I had verified this myself, in passing, while executing T1 (see §1 below) -- but read it as a
reassuring fact about artefact-gathering hygiene ("no dual-instance save collision") rather than
as what it actually is: **the design's leg C ("theirs (WSJT-X), theirs") does not have the
independence the pre-registration's 2x2 assumes.** `wsjt-x/wav` and `wsjt-x/ALL.TXT` under the
`-8080` artefact folder and the `-8081` artefact folder are not two comparable captures -- they
are hardlinks to the *same* files (confirmed: identical inode, identical md5, `cmp`-identical
`ALL.TXT`, for every case checked). One WSJT-X instance's output, referenced twice.

**The Captain's read, which I am recording rather than re-deriving, since this is
Architect/Captain territory per `anova_common.py`'s own module docstring:** this is a false
assumption from the architect's design, and it drops T4 (Angle 1) as pre-registered, not merely
weakens it. I have not independently reconstructed the chain of reasoning from "one WSJT-X
capture, reused" to "T4 is dropped" -- that is the Captain's determination, surfaced here so the
Architect has it, not a conclusion I am claiming to have derived myself.

**T1 itself is now moot.** N3's presence/coverage question (does WSJT-X's own WAV set exist and
cover the +0s stratum) is answered below as a byproduct of already having done the filesystem
work, but per the Captain, whether N3 could pass is no longer the gating question -- the design
it would have gated is withdrawn.

## 1. What I'd already established before the stop (kept for the record, not as a green light)

- `artefacts/20260731_live_run_2004-8080/wsjt-x/` and the `-8081` sibling: `ALL.TXT` (354,832
  lines) and `wav/` (10,469 files) are byte-identical between the two folders -- one underlying
  WSJT-X run, hardlinked into both.
- +0s stratum (recomputed independently from 8080's own `ALL.TXT` via `apply_grid_snap`, not
  copied from a prior note): 3,637 unique on-grid cycle timestamps, `260731_200430` to
  `260802_155200`.
- Of those, 3,617/3,637 (99.45%) have a corresponding WSJT-X WAV file present; the 20 missing
  split into 16 at the run's start (`200430`-`200815`, WSJT-X's recorder starting a few minutes
  after 8080's) and 4 isolated singletons on 2026-08-02 (`020600`/`025600`/`034600`/`043600`).

None of this is wrong as measurement -- it's an accurate description of what's on disk. It's the
inference I was about to draw from it (WAVs exist -> N3 is executable -> Angle 1 can return
MEASURED) that doesn't survive the correction, because the thing N3 would have calibrated
(leg B vs leg C, via an independently-sourced jt9-over-WSJT-X's-own-audio check) was never as
independent as the pre-registration's design section assumed.

## 2. Status of the three-workstream hand-off, updated

- **T1 -- skipped**, superseded by this note.
- **T2 (drift fix + oracle correction)** -- unaffected. Nothing about this correction touches
  `CycleFramer.cs`, the oracle test, or the 0.2 s acceptance bar. Still not blocked.
- **T3 (record corrections)** -- unaffected, still open, still Captain's for items 1-3.
- **T4 (Angle 1)** -- **dropped**, per the Captain, on top of already being blocked on
  authorisation. The pre-registration (`…-1813-architect-prereg-angle1-baseline-deficit-
  decomposition.md`) itself needs the Architect's attention: its §3 design table states leg C as
  "theirs (WSJT-X), theirs" without qualifying that WSJT-X's artefacts are a single shared
  capture rather than a comparison-specific one. Whether that's fatal to the whole design or
  just to how N3 was meant to validate it is the Architect's call, not mine to pre-empt.
- **T5 (density penalty)** -- was already gated on T4 reporting; with T4 dropped, T5's own
  pre-registration has nothing to follow. Architect's call whether T5 proceeds on a different
  basis or waits on a redesign.

## 3. Cross-references

- `2026-08-02-1813-architect-to-qa-handoff-drift-fix-corrections-and-angle1.md` -- T1's brief,
  now not actioned as written.
- `2026-08-02-1813-architect-prereg-angle1-baseline-deficit-decomposition.md` §3, §5 (N3) --
  the design section this correction bears on.
- `artefacts/20260731_live_run_2004-8080/wsjt-x/`, `artefacts/20260731_live_run_2004-8081/
  wsjt-x/` -- the artefacts inspected (hardlink identity confirmed via `ls -i`/`md5sum`).

---

*Per HK-015 this is QA -> Architect. Per HK-014/HK-010 committed locally, no push, no merge
implied. Per HK-017 filename/byline carry real `date -u` UTC. Per HK-012 the correction is
surfaced explicitly, in the open, rather than silently absorbed. Per HK-022 §1's figures were
independently measured (hash/inode-verified), not asserted. NFR-021: filenames, inode/hash
identifiers, and aggregate counts only -- no message text read or reported.*
