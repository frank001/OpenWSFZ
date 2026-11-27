# QA code review (HK-039): PAYLOAD-FIT, the lean decoder fits every result from its payload

**Reviewed commit:** `b26a156cafd4bbad178b4a5365fe3bb4267ca76c` (`feat/payload-fit`, one commit on `main` `326538fb`, not pushed)
**Reviewed-commit:** b26a156cafd4bbad178b4a5365fe3bb4267ca76c
**Verdict:** APPROVED, with 1 required documentation fix (does not block the replay) and 3 minor notes
**Reviewer:** QA, 2026-11-27. Read: the whole diff (`native/ftz_decoder/ftz_decoder.c`, `ft8_shim.h`, `Ft8LibInterop.cs`, `libft8.version.txt`, the OpenSpec change `lean-decoder` tasks 13 and the delta requirement, `tests/OpenWSFZ.Ft8.Tests/LeanEnginePayloadFitTests.cs`), against `dev-tasks/2026-11-27-payload-fit-lean-fits-every-result.md` and the Architect's `spec-payload-fit.md` (`b28f6c6e`).

## Tests and checks QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\pf-review`, Release, whole project, no `--filter`, HK-022)

- OpenWSFZ.Ft8.Tests: **Passed: 919, Failed: 0** (917 plus the 2 new `LeanEnginePayloadFitTests`), 6 m 23 s. Equals the Developer's figure.
- `libft8.dll` SHA256 `2f522765d508085861bd0098b66c39d628ab7884584f91d7bcaf8763bcd654b9`: equals the Developer's; `check_native_version.py ... 20260081`: OK.
- **From the Developer's report, not re-run by QA:** Config 237, Web 464, Daemon 963, JS 131/131 (this change touches none of those projects; `pre_merge_check` will run them once, at the sprint PR); ASan + UBSan fuzz, 10,000 runs, determinism identical at 1/2/4/8/16/2/1 threads, probe clean (CI repeats it); `check_version_bump.py`: no bump required; `openspec validate lean-decoder --strict`: passes; the two new tests **red on the committed 20260080 binary** (SUB-row assertion), green on 20260081.

## What was checked and found sound

- **The change is the one line the task asked for and nothing else.** `if (!reenc[k]) continue;` is removed from the round loop; the step-2e rule (`ftz_fit_needed`, `:1031`), the rounds, the deadline reserve, the duplicate rule and the probe are untouched in the diff. The S3 comment above the loop is updated.
- **The dead code is removed completely and the memory is balanced:** the `reenc` array, its calloc, its NULL check, its `free` and the store at the publish loop, and `ftz_text_reencodable`. No other reader (grepped in the diff context and the tree). No leak, no use of a freed pointer.
- **The premise holds in the code:** the fit takes its tones from `ft8_encode(res_pl[k], ...)` and `res_pl` is filled from `hits[k].payload` at the publish loop, before the text is built; the text is not read by the fit.
- **The classic decoder keeps its gate** (C#, not in the diff), as the task said. No flag; shim 20260081, `ExpectedShimVersion` in step with `FT8_SHIM_VERSION`; the version-text entry states the SHA.
- **The test is a real test of the gate.** The hashed type-4 message is built bit by bit (the text encoder cannot pack `<...>`; the Developer says so and shows how), the hash state is saved before the fixture is built and restored before and after the decode so the hash cannot resolve, the weak message is masked on the same carrier so the failed candidate sits inside the patch window, and the assertions are the ones that matter: a `SUB` row near 1500 Hz with `Amp > 0`, `Rounds[1].Fits >= 1`, and the masked message found. No delay anywhere. Synthetic `Q`-prefix content only (NFR-021).
- **Behavioural risk considered:** a false decode with a `<...>` or short text is now fitted too; a template that does not fit returns rc -3 and contributes zero (as for any other result), so the cost is CPU, not a wrong subtraction. The Architect priced it (about 2.7 / 0.4 / 2.5 extra fits per cycle); the replay measures it.

## REQUIRED (documentation only; does not block the replay)

1. **`REQUIREMENTS.md` FR-108 still states the old rule.** Its text says each round "SHALL subtract every result not yet subtracted whose unpacked text is re-encodable (no hash placeholder, at least three tokens)". That is the gate this commit removes, so the requirement now contradicts the code, and the OpenSpec delta (which is correct) and the root requirement disagree. Please amend the FR-108 sentence (drop the text condition and say the tones come from the payload), add 20260081 to its list of shim versions ("20260080: ..." the way the neighbours are listed) and a changelog row as DR-3 and SUB-PROBE did if a gate asks; run `check_version_docs.py` / G3. Do it on `feat/payload-fit` before the sprint PR.

## Minor notes (none blocks)

1. **Test (b) shares the fixture of (a)** (the weak message and the carrier), so a regression that breaks the fixture breaks both; acceptable for two assertions of one property.
2. **The red-on-`main` run is the Developer's** (against the committed 20260080 DLL, before the rebuild); QA did not repeat it. The assertion text in the report is the SUB-row one, the right one.
3. **The OpenSpec delta says "a `SUB` row SHALL be written ... in round 1"**, true for the fixture; in general a fit can also be skipped by step 2e or return no valid fit. The sentence starts with "WHEN ... a candidate fails to decode inside its patch window", which covers step 2e, and R3 stays possible; fine as written.

## Addendum: the required doc fix, reviewed

The Developer's doc-only commit `3ea762ee9b114bc8612055a6ed07bf3f8855f566` (on top of the reviewed commit; `REQUIREMENTS.md` only, 2 insertions, 1 deletion) removes the text condition from the FR-108 sentence ("whatever its rendered text ... tones from the decoded 77-bit payload and never from the text"), adds `20260080` (the probe, never listed) and `20260081` to the shim-version list, and adds changelog row 1.78. QA read the word-level diff: only those fragments changed; the one remaining "re-encodable" is the historical changelog row 1.72. Required fix **met**; verdict unchanged: APPROVED. `check_version_docs.py` and G3 are re-run by `pre_merge_check` at the sprint PR.

## Next (QA)

The one replay (the SUB-PROBE arm on S40 / H40 / H20, the build pinned by SHA256 above), after QA's push-free local build of the harness against this commit. No bars; the Captain decides.
