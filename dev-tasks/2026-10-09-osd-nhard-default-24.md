# `osdNhardMax` default 40 → 24, the valid range widened to [24, 100], and a one-time migration for existing installs (OSD-FIX R4)

**Date:** 2026-10-09
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the OSD-FIX TEST verdict **F-GO** (QA report `qa/rr-study/results/2026-10-09-osd-fix-test/report_test.md`, Architect ruling `qa/rr-study/2026-10-09-0955-architect-osd-fix-test-verdict-ruling.md`, `n*` = 24 by `…-0615-architect-osd-fix-train-nstar-ruling.md` §5 item 4 "R4") and the Captain's instruction in QA's window, 2026-10-09: *"lets do the default osdNhardMax 24 and station-config first"*.
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. The Developer does not push or merge, and does not run `pre_merge_check.py` on its own initiative (QA verifies, the Captain signs off the merge).
**Branch:** cut a new branch from **local `main` at `f4e046b6`** (the merge of `feat/osd-sign-fix`, `arch/osd-fix` and `qa/osd-fix`; not pushed; it is visible in the shared repository). The fix itself (`3048176d`, `3276573b`, shim 20260060) is already in that base. **Do not touch `native/` or the shipped binaries.**

---

## 0. What this is, and why three things and not one

The TEST replay (night `20260930_1930`, 860 cycles, REF = today's behaviour against FIX at `nhard` 24 with the corrected OSD) gave NET **+0.208 pp [+0.117, +0.326]** and ΔU **−0.073 [−0.090, −0.058]**, F-GO. Caps 50 and 60 are clearly harmful on the corrected OSD, 40 is not clearly better than REF, and 24 is the value the data chose. Putting 24 into the product needs three changes, because the code default alone reaches nothing:

1. **The default** (`DecoderConfig`) moves 40 → 24.
2. **The valid range moves from [30, 100] to [24, 100].** 🔴 This is the trap: the config API **clamps** `osdNhardMax` to [30, 100] (`src/OpenWSFZ.Web/WebApp.cs:559-566`, warning "out of range [30, 100] — clamped"), and the Settings page sends the whole decoder section on every save. Left as it is, the first ordinary Settings save on a station running 24 would silently turn 24 into **30**, which is not the arm TEST judged (FIX30 differs from FIX24 only in 4 cycles abandoned under load, but it is not what was validated, and it would be a silent move). The replay harness bypassed this clamp, so TEST did not exercise it.
3. **A one-time migration** for existing installs, because every `config.json` this project has written carries an explicit `decoder` section: the station's stores `osdNhardMax` 40 explicitly (since the 2026-09-12 migration), so a new default reaches no existing install (HK-035).

**The caveat this task must carry verbatim into every doc-comment it touches (the Architect's citation guard):** *"validated on replay of one 40 m night (860 cycles), Test B's not-confirmed count is an upper bound on false decodes; not measured live, other bands or fading/drift untested."* **Never write "safe".** And never cite TRAIN's +0.158 as the gain: it is the figure that chose 24.

## 1. Precise scope

### 1.1 The default, both places (the Lesson-6 / D-WFC-001 pattern: they must agree)

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs:38` `int osdNhardMax = 40` → `= 24`
- `src/OpenWSFZ.Abstractions/DecoderConfig.cs:107` `public int OsdNhardMax { get; init; } = 40;` → `= 24;`
- Update the doc comments that name 40 as the calibrated default: `DecoderConfig.cs` (class summary line ~11 and the property comment above line 107), `src/OpenWSFZ.Abstractions/AppConfig.cs:78-79`. Replace "40 is the `NHARD40-DEFAULT` arm's calibrated value" with the OSD-FIX statement (24, the corrected OSD, the caveat above), and **say that the corrected OSD is what makes 24 meaningful**: under the old inverted OSD no accept below `nhard` 28 ever occurred (QA's R6 pass, `train_r6_hist.json`), so 24 on an unfixed DLL would simply switch the OSD off.
- The native binary's own default (60) stays; this task only changes the managed value passed to `SetDecodeParams` at startup (`Program.cs:798`, `:894`).

### 1.2 The valid range [30, 100] → [24, 100], everywhere it is stated or enforced

Find every place (start from this list, then `git grep -n "30, 100\|\[30\|< 30\|, 30, 100" -- src web tests openspec docs`):
- `src/OpenWSFZ.Web/WebApp.cs:559-566`: the clamp and its warning text → `24`/`[24, 100]`.
- `web/settings.html` (the `decoder-nhard` input, ~line 359-370): `min`/`max` attributes and any helper text.
- `web/js/settings.js:909` and `:1393`: the fallback `?? 40` / `: 40` → `24`; and anywhere the page validates the value client-side.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:999` and `IFt8NativeInterop.cs:123`: the doc strings "default 60, valid [30, 100]" → say the managed default and the range the daemon enforces (these are comments only; no native or P/Invoke change).
- Specs and docs that describe the range or the default (`openspec/specs/**`, `REQUIREMENTS.md`, `TECHNICAL_SPEC.md`, `README.md`, `docs/`): amend, and run `openspec validate --all --strict`. **Do not edit `openspec/changes/archive/**`** (history).
- **Lower bound is 24, not lower:** B2 (the Architect's pre-data decision) is "no extension below 24"; the lowest value measured is the lowest value allowed (HK-038). A value below 24 posted to the API is clamped to 24 with the same warning style. (Turning the OSD off is a separate decision for the Captain; `FIX0` was measured only descriptively.)

### 1.3 The migration (one time; a persisted exactly-40 becomes 24)

Implement in `JsonConfigStore.Load()` right after the existing M2 block (`JsonConfigStore.cs` ~264-295), following **the same pattern and the #199 correction already on `main`** (read the `else if (config.Decoder is { Nhard40MigrationApplied: false })` branch at ~286: the marker means "no migration is pending for this install"):

- New marker `bool nhard24MigrationApplied = false` (JSON key `nhard24MigrationApplied`), `[JsonConstructor]` parameter default **and** property initialiser both `false` (so an absent key and a partial object both resolve to "not yet migrated"). **Do not change the existing `nhard40MigrationApplied`.**
- **Predicate, once per `Load()`, evaluated on the result of the existing M2 step:** `Decoder is { OsdNhardMax: 40, Nhard24MigrationApplied: false }` → `OsdNhardMax = 24`, `Nhard24MigrationApplied = true`, written back once (the same temp-file-then-replace write the other migrations use), one stderr line in the existing style: `[OpenWSFZ] osdNhardMax: migrated persisted default 40 -> 24 (OSD-FIX TEST F-GO, 2026-10-09). Set decoder.osdNhardMax to override.`
- **Otherwise** (a decoder section exists, marker false, value not 40): leave the value untouched and set the marker true once (the #199 rule), so a later deliberate 40 is never re-migrated.
- **A persisted legacy 60 with no markers chains:** M2 makes it 40, the new step makes it 24, **both markers true**, one stderr line each.
- **Exactly-40-only:** 30, 50, 55, 60-with-`nhard40MigrationApplied`-true, 70 pass through unchanged.
- **Server-owned marker (HK-035; the #199 lesson):** `POST /api/v1/config` is an overlay on `main` since v0.53 (FR-074): the Settings page must not clear or flip `nhard24MigrationApplied`. Mirror what `WebApp.cs:513-525` does for `Nhard40MigrationApplied`, including the case of a decoder section created from nothing (no persisted 40 can ever have existed ⇒ marker true). **Check the config-POST semantics of the branch you cut from before relying on them.**
- `git grep -n "new DecoderConfig" -- src` for any other place that builds a decoder section from `null` and saves it; the same rule applies.

### 1.4 Not in scope

No native or shim change, no new DLL, no change to `nhard40MigrationApplied`'s semantics, no change to `corr`, `kMinScorePass2` or the subtraction flags, no change to the harness-only `SetOsdSignFix`.

## 2. Tests (test-first; HK-025(k): each must be able to fail)

1. **Defaults agree:** a missing `decoder` key, a decoder object lacking `osdNhardMax`, and `new DecoderConfig()` all give 24.
2. **Migration table (assert the VALUE, not only the marker):** persisted 40 + marker false → exactly 24, marker true, file rewritten once; a second `Load` writes nothing; persisted 40 + marker true → stays 40; 30 / 50 / 70 → unchanged and marker true; legacy 60 with no markers → 24 with both markers true; no decoder key → no section created.
3. **API range:** 24 accepted unchanged; 23 and 0 clamped to 24 with the warning; 100 accepted; 101 clamped to 100. The existing `7.2e` test (lower bound 30 accepted unchanged) encodes the OLD range: change it deliberately and say so.
4. **Marker survives a Settings save:** a POST of the decoder section without the marker leaves `nhard24MigrationApplied` as stored; a section created from nothing gets true.
5. **A blind-instrument guard:** a test that would still pass if the migration never ran must not be the only one for it (the value assertion in 2 is that guard).
6. List **every existing test you change** with the old and new assertion and why, so QA can check nothing was weakened (tests that assume a default of 40 or the range [30, 100] will fail; that is expected; do not delete any).

## 3. Acceptance (what QA checks)

1. The new tests fail on the base and pass after; the changed-existing-tests list is complete and justified.
2. **Unfiltered** `dotnet test OpenWSFZ.slnx -c Release` on **Windows** and on **WSL Debian** (exact commands and per-assembly counts, HK-022). A first run that hits the known parallel-build lock (`CS2012` or a `StaticWebAssets` `IOException`) is re-run unchanged and says so. The FR-083 6.2f WebSocket flake (fix on `fix/flake-early-decode-ws`) may fire; say so if it does.
3. `git diff --stat main -- native` **empty**; `src/` limited to `OpenWSFZ.Abstractions`, `OpenWSFZ.Config`, `OpenWSFZ.Web` and doc comments in `OpenWSFZ.Ft8/Interop`; `web/` limited to the Settings page.
4. `python tools/check_test_delay_sync.py` OK; `python tools/check_version_bump.py <base>` and `check_version_docs.py` run and quoted (a bump is needed if the gate says so; the OSD-FIX merge itself may already need one: say which).
5. No push (only QA pushes). The merge is the Captain's (HK-010).

## 4. The station-config part (QA's, after the merge; recorded here so nobody edits the station by hand)

**Do not hand-edit the station's `config.json` to 24.** On a daemon without the fix DLL (shim 20260060) `nhard` 24 would make the (inverted) OSD accept nothing, which is not what TEST measured, and a hand edit would be undone or clamped by the old range. The migration above does the station's config itself, once, at the first start of a build that carries this change. After the Captain has merged and deployed:

1. QA records the exact build (commit and DLL SHA-256) and verifies from the running daemon: `GET` config shows `osdNhardMax` 24 and `nhard24MigrationApplied` true; the log shows the migration line once; a second restart shows none.
2. QA **starts a new data era on the board at that moment** (the Architect's instruction): never pool decodes made before it (nhard 40, inverted OSD) with decodes after it (nhard 24, corrected OSD). Endurance runs build from `decoding_improvement`; the Captain's periodic `merge origin/main` brings this change there.
3. The first live check (HK-036 applies to the first endurance run after it): Section 4 of the report, same band, never pooled with nhard 60 or 40 data.

## 5. References

`qa/rr-study/results/2026-10-09-osd-fix-test/report_test.md`; `qa/rr-study/results/2026-10-08-osd-fix/report_train.md` (R6 histogram); `dev-tasks/2026-09-12-nhard40-default-migration.md` and `dev-tasks/2026-10-02-nhard40-marker-trap-199.md` (the pattern and its trap); `src/OpenWSFZ.Config/JsonConfigStore.cs` (M2 block), `src/OpenWSFZ.Web/WebApp.cs:513-566`, `src/OpenWSFZ.Abstractions/DecoderConfig.cs`; standing rules HK-011, HK-022, HK-035, HK-038.
