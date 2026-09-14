# `PASSBAND-140` ship: widen the candidate passband to `[140, 3075)` Hz

**Date:** 2026-09-14
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (sign-off required before merge, HK-010)
**Authorised by:** Architect acceptance ruling
`qa/rr-study/2026-09-14-1716-architect-passband-140-acceptance-ruling.md` (`arch/g2b-passband-140`
`12064746`), on QA's result `qa/rr-study/2026-09-14-1707-qa-to-architect-passband-140-result.md`
(GATE = G1, ship-eligible). **Captain confirmed §0.4/Q2 discharged, 2026-09-14** — this is the
explicit trigger spec §3.7 names for authoring this task.
**Status:** Proposed. Per HK-011, needs the Captain's explicit sign-off before pickup; the
Developer session implementing this does not run `pre_merge_check.py` or push/merge on its own
initiative (QA verifies, Captain signs off the merge, HK-010).
**Branch:** new branch off `main`, name at the Developer's/Captain's discretion.

🔴 **This task ships `.f_min = 140.0f, .f_max = 3075.0f` — NOT `.f_max` unchanged.** The original
spec's §3.7 consequence list (written before Amendment 1) said "f_min 140 at both call sites, f_max
unchanged." **That line is stale and superseded.** Amendment 1 (`4b7b9044`, before any build or
datum) changed `WIDE`'s own definition to widen *both* edges — the true top base tone at the old
`f_max=3000.0f` was already only 2959.4 Hz (an 8-tone-span arithmetic fact, not a measurement), so
`f_max=3000` silently discarded the same 8-tone span at the top that this arm exists to recover at
the bottom. **Everything QA measured and the Architect independently re-verified — `D(C2)=+1.41pp`,
the five-band table, ROW 0f's two-edge check, A3's edge analysis — was measured against
`f_max=3075.0f`, not `3000.0f`.** Shipping `f_min=140` alone would ship a *different, unvalidated*
change from the one that passed the gate. Ship exactly what `WIDE` was: both edits.

---

## 0. Executive summary

`PASSBAND-140` (`qa/rr-study/2026-09-14-1707-...-result.md`) found that opening the FT8 candidate
passband's low edge from 200 Hz to 140 Hz, and its high edge from 3000 Hz to 3075 Hz, recovers real,
WSJT-X-confirmed signal on live 20m traffic (`D(C2) = +1.41pp`, CI `[+0.42, +2.78]pp`) with no
material cost to in-band recovery (`D_in(C2) = -0.002pp`), replicating in sign on an independent
corpus (`D(C1') = +0.60pp`). The new band's own decode quality is clean — 98% of what it emits is
REF-confirmed, unmatched-decode density only 1.8× the existing in-band rate (well under the 3×
flag threshold). All eight pre-registered ROW 0 checks passed; the Architect independently
re-derived every headline figure from the committed artefacts and found no corrections owed.

**Change this default from `[200,3000)` to `[140,3075)` Hz.**

## 1. Precise scope

1. **`ft8_shim.c`: two edits, both call sites** (`ft8_decode_all` and `ft8_extract_llrs_at`):
   - Line 1472: `.f_min = 200.0f, .f_max = 3000.0f,` → `.f_min = 140.0f, .f_max = 3075.0f,`
   - Line 1872: `.f_min = 200.0f, .f_max = 3000.0f,` → `.f_min = 140.0f, .f_max = 3075.0f,`
   (Confirm both line numbers first — `grep -n "f_min" src/OpenWSFZ.Ft8/Native/ft8_shim.c` should
   show exactly these two hits, both currently `200.0f`/`3000.0f`, matching `WIDE`'s own build in
   the measurement arm.) No other line in this file changes.

2. **`FT8_SHIM_VERSION` bump, `ft8_shim.h`.** Current value `20260050` (`#define
   FT8_SHIM_VERSION 20260050`, line ~698) → `20260051`. Add a changelog entry immediately after the
   `20260038` entry (the natural place — this is a second attempt at the same passband change,
   corrected), following the file's existing style exactly:
   - State plainly that `20260038`'s own changelog text (and `Ft8LibInterop.cs:231`'s matching
     comment, §1 item 3 below) **claimed** the passband widened to `[140, 3030)` Hz, but
     `ft8_shim.c`'s actual compiled constants never changed at that bump — verified false on `main`
     today, before this task, by both the Architect (drafting the pre-registration) and QA
     (independently, before any build). **This task is the first one that actually ships the edit.**
   - State the real change: `[200,3000)` → `[140,3075)` Hz. Cite the arithmetic reason for
     `3075` specifically (not `3030`, which `79ea12af`'s abandoned attempt used): a candidate needs
     all 8 tones in the waterfall (`decode.c:292`), so the true top base tone the *old* `f_max=3000`
     already capped at was `(481-8)*6.25+3.125 = 2959.4` Hz — `3000` silently discarded the same
     8-tone span at the top edge this task recovers at the bottom. `3075` restores `79ea12af`'s
     original stated intent (cover REF base tones to `3030` Hz) with that 8-tone span added back.
   - Cite the measurement: `qa/rr-study/2026-09-14-1707-qa-to-architect-passband-140-result.md`,
     `D(C2)=+1.41pp` CI `[+0.42,+2.78]pp`, `D_in(C2)≈0`, `D(C1')=+0.60pp` same sign, both cluster
     schemes, `N_BOOT=2000`. **State plainly what this does and does not claim** (carry forward,
     verbatim or in substance): *"Recovers real signal WSJT-X already confirms, measured on 20m
     live traffic on this station's own binary and corpus; not independently validated on any other
     band, against any reference other than WSJT-X, or under nhard=60."*
   - No ABI or struct-layout change (`FT8Result` stays 48 bytes); no new exported entry points. The
     bump exists purely so the startup ABI check catches a stale (pre-passband-140) native binary.

3. **Fix the false comment, `Ft8LibInterop.cs:231`** (inside the `20260038` XML-doc changelog
   entry there). It currently reads *"(b) the decode candidate passband widens from `[200, 3000)`
   Hz to `[140, 3030)` Hz"* — **false on `main` today**, flagged by the Architect while drafting the
   pre-registration and independently confirmed by QA (`ft8_shim.c:1472` still read `200.0f` right
   up to this task). Correct this entry in place (HK-022 — strike/correct where the false claim
   lives, don't just add a note elsewhere) to say the constant change was **claimed but not shipped**
   at `20260038`, and add a new paragraph for the `20260051` entry (mirroring `ft8_shim.h`'s own new
   entry from item 2 above) stating the actual, now-true change.

4. **`BUILD.md`'s "Monitor Configuration" block** (`src/OpenWSFZ.Ft8/Native/BUILD.md:50-61`):
   ```c
   monitor_config_t cfg = {
       .f_min       = 200.0f,
       .f_max       = 3000.0f,
       ...
   };
   ```
   → `.f_min = 140.0f, .f_max = 3075.0f,`. This is documentation only (the actual values live in
   `ft8_shim.c`), but it is what the next engineer reads first — keep it truthful.

5. **`openspec/specs/ft8lib-interop/spec.md`'s ABI version-history requirement** (the large
   paragraph starting *"The expected constant SHALL be **`20260049`**..."*, line ~49). This is
   already a known, separately-tracked spec-sync backlog item (the paragraph's own text says so —
   `main`'s actual `FT8_SHIM_VERSION` is `20260050` today, not `20260049`, predating this task).
   **In scope for this task:** update the `SHALL be` constant to `20260051` and append one further
   entry to the version-history prose (mirroring the existing entries' own style — each one
   "repairs" the chain up to itself) stating `20260051` = this task's own passband change, per item
   2 above. **Out of scope for this task:** reconstructing what changed at the undocumented
   `20260050` bump itself — flag that gap to the Architect as a separate, pre-existing item rather
   than guessing at its content here.

## 2. Builds — all three platforms

- **Windows (`win-x64`):** `native/ft8_lib_build/rebuild_shim.bat` (the authoritative script,
  `BUILD.md:116`). 🔴 **Known landmine, found by a Developer session on this same arm's earlier
  DLL-build task:** the tracked `rebuild_shim.bat` hardcodes absolute paths rooted at the
  Architect's own worktree (`D:\Projects\claude\OpenWSFZ\...`), not whichever worktree actually
  runs it. Run it verbatim from any other worktree and it silently compiles from — and overwrites —
  *that other worktree's* checked-out tree instead of your own. Check `.claude/settings.local.json`
  and/or the prior Developer session's own workaround (an adapted, path-substituted scratchpad copy
  of the script, verified byte-identical apart from the path prefix) before running this blind.
- **Linux (`linux-x64`):** CI rebuilds `libft8.so` from source on every Ubuntu run automatically
  (`BUILD.md:183-187`, `.github/workflows/ci.yml`) — no manual action needed for a normal PR.
- **macOS (`osx-arm64`):** standing project practice is that `macos-latest` CI owns this rebuild as
  part of the normal pipeline; do not attempt a manual `.dylib` cross-build and do not treat any
  `[WARN]` about it as actionable — that is expected/permanent per standing project knowledge.

**`git diff --stat main -- src/OpenWSFZ.Ft8/Native/ft8_shim.c src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`
should show exactly the two files touched by items 1 and 3 above** (plus the three binaries
themselves once rebuilt) — nothing else under `src/OpenWSFZ.Ft8/`.

## 3. Tests

Checked before writing this task (grep across `tests/` for `f_min`/`f_max`/literal `200.0f`/
`3000.0f` monitor-config assertions): **no test hardcodes the passband edges as literal
assertions.** The two files that matched a naive grep (`RefineCandidateTests.cs`,
`CoherentLlrAtTests.cs`) use `200.0f`/`2000.0f` as an unrelated time-search-grid sample-rate
constant, not `monitor_config_t.f_min`. **No test changes anticipated** — but re-run the full
suite and treat any FT8-decode-output test failure as a real finding, not noise, since this is a
genuine behaviour change to the candidate search space.

## 4. Rigour controls

1. **Exactly the two lines in `ft8_shim.c` change the decode behaviour.** Every other edit in this
   task (changelog entries, `BUILD.md`, the interop comment, the spec-doc constant) is
   documentation or the version-check sentinel — none of it alters what gets decoded.
2. **Ship `f_max = 3075.0f`, not `3000.0f` or `3030.0f`.** This is the single most important
   number in this task to get right — see the banner at the top of this file. If in doubt, diff
   your edit against `WIDE`'s own build record: `qa/rr-study/passband-140/dll_manifest.json`
   (`"WIDE": {"f_min": 140.0, "f_max": 3075.0, "sha256": "ae0c7c21..."}`).
3. **`FT8_SHIM_VERSION` bump is mandatory, not optional**, unlike the measurement arm's own builds
   (which deliberately did NOT bump it, since SHA identity was enough there). This is a real
   shipped behaviour change — the startup ABI check must be able to distinguish a pre- and
   post-passband-140 binary.

## 5. Scope guardrails — what this is NOT

- **Not a change to `f_max`'s original 3030 half of `79ea12af`'s abandoned attempt.** That work is
  superseded entirely by this task's own, freshly-measured `3075` value — don't resurrect
  `79ea12af`'s branch or cherry-pick from it.
- **Not a fix to the pre-existing `20260049`→`20260050` spec-sync gap.** Flag it, don't chase it
  here (item 1.5 above).
- **Not a change to the `[100,140)` rung** — the spec's own §6 explicitly keeps that unrun; this
  task ships only what was measured.
- **Not a re-opening of any prior candidate-budget, suppression, or spectral-locality decision** —
  none of those are touched by this change.
- **Not a decision about when the Captain's own live station adopts this build** — deployment
  timing is his to choose separately, same as the `nhard40` precedent.

## 6. Deliverables

1. `ft8_shim.c` two-line edit (§1.1).
2. `ft8_shim.h` version bump + new changelog entry, correcting the `20260038` record in place
   (§1.2).
3. `Ft8LibInterop.cs:231` comment fix, correcting the `20260038` record in place (§1.3).
4. `BUILD.md` Monitor Configuration block update (§1.4).
5. `openspec/specs/ft8lib-interop/spec.md` constant + version-history entry (§1.5).
6. All three platform binaries rebuilt and committed (win-x64 locally, linux/macOS via CI).
7. Full test suite green; any FT8-decode-output test failure investigated as a real finding.
8. A short PR description carrying, verbatim or in substance, the citation guard from item 2 of
   §1 above (what this ship does and does not claim), and confirming
   `git diff --stat main -- src/OpenWSFZ.Ft8/Native/ft8_shim.c src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`
   is exactly those two files.

QA verifies against this task before recommending merge (HK-002/HK-006); the Captain signs off the
merge itself (HK-010). Neither step is implied by this task's own authorship.

## 7. References

| Reference | Content |
|---|---|
| `qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md` §3.7, and its Amendment 1 (`arch/g2b-passband-140` `4b7b9044`) | The original ship consequence list (stale on `f_max`) and the amendment that supersedes it |
| `qa/rr-study/2026-09-14-1707-qa-to-architect-passband-140-result.md` | The measurement this task ships — every cited figure |
| `qa/rr-study/2026-09-14-1716-architect-passband-140-acceptance-ruling.md` | Architect's independent re-derivation, no corrections owed |
| `qa/rr-study/passband-140/dll_manifest.json` | `WIDE`'s exact build record — `f_min`/`f_max`/SHA to match |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1472,1872` | The two (and only two) lines to edit |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` (`FT8_SHIM_VERSION`, changelog around the `20260038` entry) | Version bump + corrected changelog |
| `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:223-236` | The false `20260038` comment to correct |
| `src/OpenWSFZ.Ft8/Native/BUILD.md:50-61` | Monitor Configuration doc block |
| `openspec/specs/ft8lib-interop/spec.md:49` | The ABI version-check normative requirement |
| `dev-tasks/2026-09-14-passband-140-base-wide-dll-build.md` | The measurement arm's own build task — the `rebuild_shim.bat` worktree-path landmine and workaround are documented in the Developer's completion record for that task |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_015X7EER7oMZEPcUjDSKgbuy*
