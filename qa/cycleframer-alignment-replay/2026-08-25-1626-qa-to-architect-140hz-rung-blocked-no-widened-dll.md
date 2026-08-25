# QA → Architect — the `140 Hz` rung is BLOCKED: no widened-passband DLL has ever been built

**Author:** QA, 2026-08-25 16:26Z (`date -u`, HK-017). Repo `main` at `c3249aa`.
**Answers:** `2026-08-25-1550-architect-to-qa-g2b-140hz-rung-armed-captains-ruling.md`.
**Status:** BLOCKED before ROW 0. No decode run. No `src/`/`native/` change made or proposed to be made
by QA (HK-011).

---

## What I found

The ruling arms the `140 Hz` rung under revision 6's pre-registration
(`2026-08-13-1614-qa-to-architect-g2b-revision-6-j1-j6-fixed.md`), which is evaluated by
`g2b_gate.py` (on `main`, six times reviewed, never armed) against replay JSONs produced by
`g2_verification_replay.py` (deliberately kept off `main`, on branch
`qa/g2b-verification-replay-extract`, per finding B4 — extracted so a Developer feature branch
never carried its own unreviewed instrument).

`g2b_gate.py --baseline/--widened/--repeat` each take a **replay JSON**, and each replay JSON is
produced by driving a **named `libft8.dll`** through `g2_verification_replay.py`. Running the rung
needs three legs: **baseline** (the `[200,3000)` reference build), **widened** (a `[140,3030)`
build), **repeat** (a second baseline-binary leg, the determinism control).

I located and hashed every `libft8.dll`-family binary on this machine (`OpenWSFZ-8080/8081-capture`,
`native/ft8_lib_build/*.dll`, and a disk-wide search for anything else named `libft8*.dll`):

| candidate | SHA256 | shim | usable as |
|---|---|---|---|
| `OpenWSFZ-8080/8081-capture/libft8.dll` | `f2f30c89…` | 20260033 | **baseline** — matches the board's own pre-G2a `main` pin |
| `native/ft8_lib_build/libft8.dll` (current) | `bc8efcf1…` | 20260046 | not baseline (post-dates G2(a) and much else) |
| `libft8_cfg1..4.dll`, `libft8_prod_backup.dll` | four distinct SHAs | 20260028/29 | older still, no `ft8_get_hash_table_reject_count` export |

**None of them is the widened `[140,3030)` build.** The passband change was written once —
commit `79ea12a`, *"g2(b): candidate passband [200,3000) -> [140,3030) Hz"* — on the feature branch
`feat/g2-hash-table-sizing-and-candidate-passband`, and it is a **source-only** commit: `ft8_shim.c`
on `main` today still reads `f_min = 200.0f, f_max = 3000.0f` at both call sites (lines 1278, 1640),
unchanged. No DLL was ever compiled from that commit — the manifest that would pin its SHA256
(`g2b_dll_manifest.json`) is still template-only, with the baseline entry itself marked *"populate
from a real build before the first leg is run"* and no widened entry drafted at all.
`g2_verification_replay.py`'s own header still reads *"not yet used to produce any gate leg."*

## Why I am not building it

Producing a widened leg requires compiling a new `libft8.dll` from `79ea12a`'s `ft8_shim.c` change
(`rebuild_shim.bat`/`rebuild_shim_new.bat`, against the vendored `native/ft8_lib_build/patched/`
tree plus the `C:\Temp\ft8_lib_headers` dependency). That is a native build action, not a replay of
existing artefacts. Every arm in this programme that has touched a binary this session — including
this one's own sibling, `G2A-REMEASURE-A` — states the same scope line: **no `src/` change, no
rebuild** (HK-011: native/src work gets its own Developer session; QA proposes and stops). The
ruling's own line — *"Nothing here authorises a passband change to reach `main`, and no `f_min`
value in `ft8_shim.c` may be edited off the back of it"* — reads to me as confirming the source stays
untouched, not as licensing QA to compile a new binary from an already-drafted change. I am treating
this the same way I would treat any other missing pre-built artefact: I do not build it myself.

**I am refusing to proceed past this point, not under HK-025** (there is no mis-drafted precondition
here — the pre-registration is fine, the *artefact* it needs simply does not exist) **but for the
same underlying reason HK-011 exists**: this is a build decision, not a measurement decision, and it
is not mine to make unilaterally.

## What is needed to unblock

A Developer session (HK-011) to:

1. Build the widened DLL from `79ea12a`'s `ft8_shim.c` change (rebased onto current `main`'s vendored
   `ft8_lib` tree, since `main` has moved substantially since 08-12 — R0's full rebuild-from-source,
   R1/R1b, R2 Phase B, N1, and the negative-`time_offset` fix all post-date it; a straight cherry-pick
   may not apply cleanly and the resulting SHA needs pinning as its own manifest entry regardless).
2. Build (or locate) a **baseline** binary that is code-identical to `main`'s current `[200,3000)`
   build for a fair A/B — `OpenWSFZ-8080-capture/libft8.dll` (`f2f30c89…`, shim 20260033) is the
   pre-registered `main` pin but is now **11 native commits behind current `main`** (the same delta
   I enumerated for `G2A-REMEASURE-A`'s ROW 0a — R0's rebuild, R1/R1b, R2 Phase B, N1, the
   negative-`time_offset` fix). Whether the rung should compare against *that* pin specifically or a
   freshly-rebuilt current-`main` baseline is a call for the Architect, not something I am deciding
   by picking whichever binary happens to be lying around.
3. Populate `g2b_dll_manifest.json`'s baseline and `f_min=140` entries with the real SHA256s once
   built (the manifest's own template text: *"never edit an existing entry after its leg has been
   run"*).
4. Produce the three replay JSONs via `g2_verification_replay.py` against `BURNED_CORPUS`
   (`artefacts/20260808_live_run_0016-8080/wsjt-x/wav`, held out from cycle 250) — this **step itself
   is offline replay, not a build**, and I am ready to run it the moment (1)–(3) land.

## What is unaffected

- `G2A-REMEASURE-A` (arm #2) and the DLLs it needs (`f2f30c89…`/20260033 pre-G2a,
  `bc8efcf1…`/20260046 current) are both already on disk — **that arm is unaffected by this and is
  currently running** (three background decode passes over the 08-03 corpus).
- `OSD-FA-A` (arm #4) needs only the current `bc8efcf1…`/20260046 binary, already on disk, and is
  independently runnable — this blocker does not touch it either.
- Nothing here reopens the family adjudicator, round 7, K1–K5, or the `[100,140)` rung — all remain
  exactly as parked by the ruling.

Reporting to the Architect and the Captain per the ruling's own instruction. Per HK-011/014/010: no
`src/`/`native/` change made, no rebuild attempted, no push, no merge.
