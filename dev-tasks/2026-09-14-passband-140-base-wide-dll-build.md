# `PASSBAND-140`: build two measurement DLLs, `BASE` and `WIDE` (`f_min` 200→140 only)

**Date:** 2026-09-14
**Prepared by:** QA
**Audience:** Developer (to execute), no merge/push involved (HK-011) — this is a measurement
artefact build, not a shipping change.
**Authorised by:** Architect pre-registration
`qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md` §2.1, Captain's
"proceed" (2026-09-14 ~15:3xZ) on the recommendation to re-arm the passband widening.
**Status:** Cleared for pickup now — no Captain sign-off gate on this step (it produces
gitignored `artefacts/` output only; nothing reaches `src/`, nothing is pushed or merged).
**Branch:** a new throwaway branch off `origin/main` at `b4f67f42` or later, **never pushed,
never merged.** Delete it (or leave it — it never leaves your local checkout) once this task's
completion record is filed; QA does not need the branch to persist.

---

## 0. What this is and why

`PASSBAND-140` (the G2(b) 140 Hz rung) asks whether opening the candidate passband's low edge
from 200 Hz to 140 Hz recovers real signals WSJT-X already decodes but we currently miss by
construction. Answering that needs two DLLs that differ by **exactly two characters** — a decimal
literal, twice — so that any measured difference in decode output is attributable to the `f_min`
change and nothing else (toolchain drift, an unrelated source edit, a stale build). This task
builds both. QA runs the actual measurement in a separate step; this task's only output is two
DLL files plus a short completion record.

## 1. Precise scope

1. **Cut a throwaway branch off `origin/main`** (`b4f67f42` or newer — check
   `git log -1 origin/main` first and use whatever `origin/main` actually is at pickup time, not
   a stale local ref). Name it whatever you like; it is never pushed or merged, so naming is not
   load-bearing.

2. **Build `BASE`:** with the tree exactly as checked out (no edits), run
   `native/ft8_lib_build/rebuild_shim.bat` — the authoritative build script
   (`src/OpenWSFZ.Ft8/Native/BUILD.md:116`). **Do not hand-run the individual `cl`/`link` commands
   in `BUILD.md`** — the `.bat` is kept in sync with the export list and source list; hand-running
   risks a stale export surface. The script's own last step copies the result to
   `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` — **immediately copy it out** to
   `artefacts/passband-140/bin/libft8_PB140_BASE.dll` before touching anything else, since the
   next step overwrites that same tracked-tree path.
   - `artefacts/` is blanket-gitignored repo-wide — nothing in this step needs `git add`.

3. **Make exactly two edits** to produce `WIDE`, both in `src/OpenWSFZ.Ft8/Native/ft8_shim.c`:
   - Line 1472: `.f_min = 200.0f, .f_max = 3000.0f,` → `.f_min = 140.0f, .f_max = 3000.0f,`
   - Line 1872: `.f_min = 200.0f, .f_max = 3000.0f,` → `.f_min = 140.0f, .f_max = 3000.0f,`
   (Confirm both line numbers land on the right statement before editing — `grep -n "f_min"
   src/OpenWSFZ.Ft8/Native/ft8_shim.c` should show exactly these two hits, both currently
   `200.0f`, before you start.)
   - **`f_max` does not change. `FT8_SHIM_VERSION` in `ft8_shim.h` is not bumped** — a version
     bump would be a third diff line, and this arm identifies binaries by SHA-256, not by the
     version constant (`FT8_SHIM_VERSION` has two known real collisions on `main` already,
     tracked separately — do not add a third divergence point here).
   - **No other file changes.** If `rebuild_shim.bat` or anything else nudges a timestamp-only
     diff in a tracked file, revert it before building `WIDE` — the only substantive diff between
     `BASE` and `WIDE` must be the two lines above.

4. **Build `WIDE`:** run `native/ft8_lib_build/rebuild_shim.bat` again (same script, tree now
   carrying the two-line edit). Copy the result to
   `artefacts/passband-140/bin/libft8_PB140_WIDE.dll`.

5. **Revert the two-line edit** (`git checkout -- src/OpenWSFZ.Ft8/Native/ft8_shim.c` or
   equivalent) so your working tree's `src/` matches `origin/main` again exactly. Confirm with
   `git status` — **it must show no changes under `src/` or `native/`** before you file the
   completion record. (`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` itself is very likely
   `git status`-dirty from steps 2/4 rebuilding it in place — that tracked binary is fine to leave
   dirty or restore with `git checkout --`, either way, as long as no *source* file differs.)

6. **Do not commit anything on the throwaway branch, and do not push it.** Nothing from this task
   reaches `origin`. The branch exists only so step 1–5 happen on a clean, known tree rather than
   your persistent working branch.

## 2. What to report back (the completion record)

Paste, verbatim, into your reply:

1. `git diff BASE..WIDE` — or, since there's no `WIDE` commit, simply: the output of
   `git diff origin/main -- src/OpenWSFZ.Ft8/Native/ft8_shim.c` **taken while the two-line edit
   was in place, before you reverted it in step 5.** It must show exactly two changed lines
   (1472, 1872), each `200.0f` → `140.0f`, nothing else. **If it shows anything else — stop, do
   not build `WIDE`, and report back instead.**
2. `sha256sum artefacts/passband-140/bin/libft8_PB140_BASE.dll` and the same for `..._WIDE.dll`
   (or PowerShell `Get-FileHash -Algorithm SHA256`).
3. Confirmation that `SHA(BASE)` — the file you just built with no edits — equals
   `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`. **This is the SHA of the
   DLL `main` ships today** (pinned in `qa/rr-study/live-gap-now/dll_pin.py`'s `NOW` entry). If
   your freshly-built `BASE` does **not** match, say so explicitly and do not proceed past step
   2 — that means something about the toolchain or tree differs from what produced the shipped
   binary, and QA's ROW 0b needs to know that before anything downstream runs (the spec has a
   fallback check, K60, for exactly this case — QA runs it, you don't need to do anything more
   here).
4. `git status` output (full), taken after step 5, showing no diff under `src/` or `native/`.
5. Any build warnings the two runs produced that differ between `BASE` and `WIDE` (there should
   be none — same compiler flags, same source tree modulo the two lines).

QA takes it from here: independently re-verifies both SHA-256 values against your report, writes
the manifest (`qa/rr-study/passband-140/dll_manifest.json`), and runs the measurement legs. You
are not needed for anything past the completion record above unless ROW 0b's SHA check fails
(item 3), in which case QA will come back with what's needed.

## 3. Rigour controls

1. **Exactly two edits, nothing else.** This is the whole point of the task — a contrast that
   isolates one variable. If you notice anything else that seems worth fixing while in this area
   (e.g. `Ft8LibInterop.cs:231`'s comment, already flagged by the Architect as false on `main`
   today — it wrongly claims the passband is already `[140,3030)`), **do not fix it here.** Note
   it in your reply if you like; it's already tracked and rides a separate task if this arm ships.
2. **Both DLLs must come from the same build script, same machine, same session**, back to back,
   so toolchain version and environment cannot differ between them. Don't build `BASE` today and
   `WIDE` tomorrow, or `BASE` here and `WIDE` on a different machine.
3. **`artefacts/passband-140/bin/` is gitignored** (the whole `artefacts/` tree is). Nothing in
   this task requires `git add`, and nothing should be committed except possibly your own scratch
   notes on your own throwaway branch, which is never pushed regardless.

## 4. Scope guardrails — what this is NOT

- **Not a ship.** No `f_min` edit reaches `main` from this task. If the measurement later
  recommends shipping (ROW G1), that is a **separate** dev-task QA authors afterward, with its
  own `FT8_SHIM_VERSION` bump, three-platform rebuild, and `BUILD.md`/`Ft8LibInterop.cs:231`
  fixes in scope.
- **Not a Linux or macOS build.** Windows `win-x64` only — this is an offline replay measurement
  tool run locally, not a shipped multi-platform artefact.
- **Not a decode run.** You build two DLLs and stop. QA runs both through the actual measurement
  (Python ctypes harness + a managed-chain C# tool), separately.

## 5. References

| Reference | Content |
|---|---|
| `qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md` §2.1 | The binding constraints this task implements verbatim |
| `src/OpenWSFZ.Ft8/Native/BUILD.md:111-179` | Build procedure; `rebuild_shim.bat` is authoritative, don't hand-run the commands |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1472,1872` | The two (and only two) lines to edit for `WIDE` |
| `qa/rr-study/live-gap-now/dll_pin.py` `LEGS["NOW"]` | `main`'s shipped DLL SHA-256, the pin `BASE` must match |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_015X7EER7oMZEPcUjDSKgbuy*
