# Developer task: make the third pass ("Deep") ON by default, for merge to `main` (#240, step 1 ship)

**To:** Developer (or the Captain, if he codes it himself). **From:** QA. **Date:** 2026-10-19. **HK-000 handoff.**
**Captain's decision (2026-10-19, by `date -u` ~08:30Z):** "merge it to main, default option ON. spec it for the developer." (Architect's options A/B/C: A chosen, with the default flipped to Deep. The Architect's acceptance ruling `qa/rr-study/2026-10-19-0727-architect-third-pass-acceptance-ruling.md` on `arch/third-pass` accepted step 1 as measured and assumed opt-in; the default is the Captain's call, made here.)
**HK-011:** this touches `src/` and `tests/`; Developer work, QA reviews the diff. No native change.

## Interpretation (QA states it; correct it before building if wrong)
"Default option ON" = **`decoder.decodingDepth` defaults to `"Deep"`**: a config file with the key ABSENT, and a brand-new install, run the third pass. A file with an explicit `"Normal"` stays Normal. There is no separate on/off switch. **No Settings-page control in this change** (B10 of step 1 stands; a UI control is a separate, later item the Captain may ask for).

## Branch and base
Continue on **`feat/third-pass-deep`** (`a329cea9`, pushed, no PR yet, parent `535661a2` = `origin/main` at the time; `git fetch` and re-check that `origin/main` has not moved; if it has, merge it in and say so). **Add your commit(s) on top; do not rewrite `a329cea9`** (QA's measurements name that SHA). Commit locally; do not push, do not open a PR (QA does both, on the Captain's go).

## 1. What to change
1. `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: the constructor parameter default and the property initialiser for `DecodingDepth` become `DecodingDepth.Deep`. Keep the existing comment about "in the constructor with its default" (an absent key must read as the default, as for `earlyDecodeEnabled`). **Update the XML doc** (it says "Normal (the default)"; it must say Deep is the default, Normal is the explicit opt-out, and that an absent key reads as Deep).
2. `src/OpenWSFZ.Abstractions/DecodingDepth.cs`: fix the doc comment ("The default" moves from `Normal` to `Deep`). Do **not** reorder the enum or change the numeric values.
3. **Leave `Ft8Decoder`'s own initial depth `Normal`.** A decoder that has never been told anything stays inert (`Ft8Decoder.cs` ~l.185); the daemon tells it at startup (`Program.cs`: `SetDecodingDepth(initialDecoder.DecodingDepth)`) and each cycle. Do not change any other call site's default, and do not add a hidden second default anywhere (grep `DecodingDepth.Normal` in `src/`; every hit must be either this inert decoder default or a deliberate explicit value).
4. **Check the config round trip for the flip, and say what you found:** (a) a config file written before the key existed loads as Deep; (b) loading it and then saving through the Settings page or `POST /api/v1/config` writes `"decodingDepth": "Deep"` into the file and does not silently revert to Normal; (c) an explicit `"Normal"` survives load, save and overlay POST (HK-035: the POST is an overlay on `main`).
5. **Do not touch** pass 0, the residual pass, the 13 s budget mechanism, the abandon/failure rules, the log line or the counters (B2-B7 of the step-1 task stand unchanged).
6. **Version and docs:** this changes live behaviour for every install, so expect a `VERSION` bump (currently 0.58 on `main`); run `python tools/check_version_bump.py` **after committing** (it reads from git) and follow what it says. Add one line to `docs/development-history.md` (the table that already lists "early decode (#122 step 4)") for the third pass, with the default stated. Do not cite any yield figure in it other than the Architect's ruling's own words; if unsure, state only what the feature does.

## 2. Tests (the existing ones that encode the old default must change; no test may be loosened to pass)
- `tests/OpenWSFZ.Ft8.Tests/ThirdPassDeepTests.cs` ~l.159: `new DecoderConfig().DecodingDepth` expects **Deep**. ~l.161 ("a decoder that was never told anything is Normal"): **stays Normal**, since item 3 keeps it.
- `tests/OpenWSFZ.Web.Tests/DecodingDepthApiTests.cs` ~l.33 (a config file written before the key existed): expects **Deep**. ~l.50-53 (explicit `"Normal"` via POST) stays Normal. Add: a file with the key absent, saved back, still reads Deep and now has the key (item 4b).
- Add a daemon-level or Web-level test that **an explicit `"Normal"` file is not changed by load + overlay POST of an unrelated key** (item 4c).
- Any other test that builds a `DecoderConfig` with defaults and then asserts batch counts / status counters at depth Normal: make the depth explicit (`DecodingDepth.Normal`) in that test rather than changing its expectations. List which ones you touched.
- The unfiltered suite passes on Windows and WSL (quote the exact command and totals; a filtered-out suite is not green, HK-022).

## 3. What QA will do with the merge (so you know what is NOT yours)
- QA pins the R&R rig and station configs to an **explicit** `decodingDepth` after the merge (the sol rig config pin `661de047…` has no such key and would silently become Deep). That is a QA change, not part of this task.
- The merge starts a **new timing and decode era** at every install that has the key absent (Deep adds ~0.5 s to the whole-call time on the station PC and about 2 s to the sol F2 trigger stall; the shared 13 s budget bounds it). Eras and the F2 episode count are QA's bookkeeping.

## 4. Known behaviour you must NOT "fix" here, but must report in the hand-back
On the staged (Deep) path in `DecodePump.cs`, batch 2 and batch 3 go to the panel, `ALL.TXT`, filter admission and external reporting, but **not to the QSO answerer, the caller or the cycle archive** (as batch 2 already does). With Deep ON by default, a station found only by the residual or third pass will be displayed and logged but **never auto-answered**. Confirm in the hand-back that this is the same policy batch 2 already has, and quote the line(s). Whether to change it is the Captain's decision, not part of this task.

## 5. Hand-back (the Developer's report)
Branch and commit SHA(s) on top of `a329cea9`; `git diff --stat a329cea9..HEAD` (expected: `DecoderConfig.cs`, `DecodingDepth.cs`, the two test files, `VERSION`/docs only; `native/` and `src/OpenWSFZ.Ft8/Native/` empty); the result of items 1.4 (a)-(c) with the test names; the list of tests whose depth you made explicit; the unfiltered test run on Windows and WSL; what `check_version_bump.py` said; the item-4 lines.

## 6. Acceptance (QA checks; mechanical)
- `new DecoderConfig().DecodingDepth == Deep`; the key absent loads Deep; explicit `"Normal"` loads Normal and survives overlay POSTs; `GET /api/v1/status` `thirdPass.decodingDepth` reads `"Deep"` on a default-config daemon.
- `Ft8Decoder` constructed bare is still `Normal`; with `"Normal"` configured, output is bit-for-bit `main` (QA reruns the identity row V1 against `main` on the new tip, with its OSD-sign control).
- The diff against `a329cea9` touches nothing in the decode path (`Ft8Decoder.cs`, `SubtractionPass.cs`, `DecodePump.cs`) other than comments.
- Tests: no loosened assertion; the unfiltered suite is green on all CI legs when QA pushes.
- Then, on the Captain's explicit go (HK-010, HK-033): QA pushes, opens the PR to `main`, CI green, merge.

## References
Architect's acceptance ruling `qa/rr-study/2026-10-19-0727-architect-third-pass-acceptance-ruling.md` (`arch/third-pass` `a219afc7`); step-1 task `dev-tasks/2026-10-18-third-decode-pass-deep.md`; board entries 2026-10-19 (TPNORMAL / TPDEEP, 777 vs 717). HK-035 (overlay POST), HK-022, HK-010, HK-011.
