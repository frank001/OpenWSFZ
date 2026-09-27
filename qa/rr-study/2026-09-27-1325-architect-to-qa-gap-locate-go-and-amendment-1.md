# `GAP-LOCATE`: GO, plus Amendment 1 (operational only, no row changes)

**Architect, 2026-09-27 13:25Z** (`date -u`, HK-017). Branch `arch/gap-locate` (off `origin/main` `00698fb1`).
Docs-only; `git diff --stat origin/main -- src/ native/` is empty.

**Authorised:** the Captain, 2026-09-27: *"proceed with the GAP-LOCATE."* The spec is
`qa/rr-study/2026-09-22-1807-architect-to-qa-spec-gap-locate.md` (on `main`, `f8d39d68`). It was paused
behind endurance/R&R standardisation, and that work is now done.

---

## §1. Preconditions the Architect checked before arming (HK-018 / HK-020)

These are **existence checks only**. They do not replace ROW 0. QA still runs 0a–0e exactly as written.

| item | where (QA worktree) | state |
|---|---|---|
| C3 corpus | `artefacts/20260921_1624_live_run-live-gap-map/` | present: `cycle-audio/` (5,779 entries, 2.0 GB, incl. `cycle-archive.csv`), `openwsfz/ALL.TXT`, `wsjtx-1-ft991a/ALL.TXT` |
| LIVE-GAP-MAP result | `…/results/lgm_result_amendment3.json` | present (the file ROW 0b reproduces) |
| Pinned DLL | `artefacts/density-remedy-stage1-accept/bin/libft8_NEW.dll` | SHA-256 `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba`, full match; `ft8_decode_all`, `ft8_extract_llrs_at`, `ft8_ldpc_decode_llrs` all resolve via `ctypes` |
| Instruments | `qa/rr-study/f-nbr-a/{row0,dll_common}.py`, `qa/rr-study/thresh-a/run.py`, `qa/rr-study/live-gap-map/lgm_harness.py` | on `main` |

## §2. Amendment 1 (three operational changes; §2–§6 of the spec untouched)

1. **DLL: copy it, then pin the copy.** Copy the DLL above into the run's artefact dir (`bin/libft8_C3.dll`)
   and load **that** copy. 🛑 Do not load the DLL from `worktrees/dev/…/bin/` or `w-di-run/…/bin/`. They hash
   the same today, but they are build outputs, and the next build overwrites them silently. ROW 0a hashes the
   file that is actually loaded.
2. **Branch: `qa/gap-locate`, cut from `origin/main`, not `qa/live-gap-map`.** This replaces the spec's §7
   line *"Commit the report locally on `qa/live-gap-map`"*. That branch is local-only and unpushed, and it has
   an open recovery item on the board. Keep this arm off it. One branch per workstream (HK-003 addendum).
3. **Artefacts:** `artefacts/<YYYYMMDD_HHMM>_gap-locate/` in the QA worktree, with a `README.md` (HK-016).
   Supervise it if it runs long (HK-013/HK-023, `nohup … & disown` + log tail). Offline and CPU-only: no
   capture, no station contention.

**Unchanged, and restated because they carry the result:** ROW 0 strict order, and any fail ⇒ §4 VOID (report
the gap, don't route around it). 🔴 **No second +0.16 s correction** on top of `dll_common`'s. Text match is
required for F; CRC-only ⇒ `F_wrong`. `δ` is recomputed in 0c, not taken from the spec's ≈0.653 s. Sampling of
M (seed 20260922, n ≥ 4,000) is allowed **only if declared before any leg runs**. No `EXPOSED`/neighbour
split (§5). No new instrument: if a leg needs one, STOP and report. §6 predictions stand as registered
(already in the Architect's prediction ledger). This amendment adds none.

## §3. Report back

- **ROW 0 first, as its own message**, before Legs R/F/K results are read. If 0c (`P_ctrl` ≥ 0.90) or 0e
  fails, stop there.
- Then the S-family and L-family rows with their CIs, and D1–D6.
- NFR-021: aggregates only (HK-037). Scan the prose. Commit locally on `qa/gap-locate`. Pushing needs the
  Captain's go (HK-033).
- HK-025 refusal is available in full. If anything in the spec reads as a diagnostic dressed as a gate, refuse
  it before running, not after.
