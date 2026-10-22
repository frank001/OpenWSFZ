# QA code review: COH-FALLBACK default ON and the Settings checkbox, `f684277f` (HK-039 record)

Reviewed-commit: f684277fe7a4c8ecab2cd6599169c5ae957ad2b4

Verdict: CHANGES REQUIRED: one required change (R-1, a failing pre-merge gate), three notes. Everything else is approved.

**Stamped:** 2026-10-22T17:47Z by `date -u` (17:46:55Z when the review ended). **Reviewer:** QA. **Base:** `b8fc732e` (reviewed per `2026-10-21-1740-qa-code-review-coh-fallback-step4-db3d7df5.md`). **Task:** `dev-tasks/2026-10-22-coh-fallback-default-on-and-setting.md` (`22206531`), the Captain's go in QA's window. **Diff reviewed:** `git diff b8fc732e f684277f` (17 files, +228 / -32).

## What I checked, and what I found

| Item | Result |
|---|---|
| `native/` untouched | **Yes**: 0 files differ from `b8fc732e` |
| Default ON in the config record | **Yes**: constructor default (`DecoderConfig.cs:52`) and initialiser (`:239`) both `true` |
| The daemon applies it | **Yes**: `Program.cs:807-808` (start-up) and `:910-911` (every save) set the decoder flag and the QSO queues' capacity flag from the config; `fallbackOn` starts `false` and is overwritten from the config before the pipeline runs |
| An absent key reads `true`, an explicit `false` stays `false`, through the real loader | **Yes**: the four config tests go through `ConfigJsonContext` and `JsonConfigStore` (absent key, no decoder section, explicit false surviving load, an unrelated save and a reload). The Wiring test's old "absent key" line passed trivially (plain `Deserialize` ignores the camelCase key); the Developer found it and says so, and the config-store tests are the real check. Agreed |
| A bare `Ft8Decoder` stays OFF | **Yes, by design** (no config; the daemon sets it). No decoder test starts the fallback by accident: the Developer grepped the constructors and the full suite is green |
| The four changed tests | Each is a deliberate reversal of a "defaults to false" assertion, each explained, none weakened: the OFF side now also asserts the explicit-false path. Approved |
| Settings page | `decoder-coherent-fallback` checkbox beside the early-decode controls; pre-fill `dec.coherentFallbackEnabled ?? true`; the key is in the dirty snapshot and in the save payload; Reset ticks it; help text states what it does, the `subtractionEnabled` dependency, "takes effect on the next decode cycle" and how to turn it off. Six new JS tests plus the payload-shape JSON. Approved |
| Overlay POST (HK-035) | Existing overlay tests (a body without the key keeps the stored value, true or false) pass on this build, per the Developer; the API test now stores an explicit `false` first, correctly |
| OpenSpec | `openspec validate coh-fallback-default-on-setting --strict`: **valid** (QA ran it). Closes the HK-002 gap the audit found |
| Version | VERSION 0.58 to 0.59; `check_version_bump.py origin/main`: **OK** (user-facing change, bump in the same PR) |
| Optional items | Status read-back and a `decodingDepth` control left out, with sizes given. Accepted; neither was asked for |

## Required change

- **R-1 (gate failure).** `tools/check_version_docs.py` at `f684277f` **fails**: `REQUIREMENTS.md:23` still says "The current release is v0.58" while `VERSION` is 0.59 (the README was updated and is OK). A version bump must update every document the check reads. **Fix:** change that anchor sentence in `REQUIREMENTS.md` to v0.59, commit, and re-run `python tools/check_version_docs.py` until it prints `all docs cite v0.59`. Re-send the new commit hash. QA then reviews the one-line delta.

## Notes (not blocking)

- **N-1 (stale comment).** `src/OpenWSFZ.Daemon/Program.cs:806` still says "false unless the config says true"; it is now "true unless the config says false". One line; fix it in the same commit as R-1.
- **N-2 (not verified).** The Playwright suite (`tests/web-ui`) was not run by the Developer, and CI does not run it (it runs `node --test web/js/*.test.js` only, `ci.yml:405`). The Settings page changed, so a Playwright test that counts or snapshots fields could be affected. QA will say whether it can run that suite; if it cannot, this stays an open risk that the Captain should know.
- **N-3 (data era, QA's side, not a code defect).** With the default ON, **every daemon started with a config that lacks the key now runs the fallback**: the R&R and endurance configs, the `sol` rigs, any scratch daemon. The merge SHA and time are the era boundary; QA's configs state the flag explicitly from now on, and flag-ON data is never pooled with flag-OFF data.

## Addendum: delta `f684277f` to `25d111e4` (2026-10-22T17:48Z by `date -u`)

Reviewed-commit: 25d111e4549bbdfa58ebd70cbd771590ab6eb83d

Verdict: APPROVED (R-1 and N-1 fixed; N-2 stays an open risk).

The delta is two files, two lines: `REQUIREMENTS.md:23` now says v0.59, and the `Program.cs:806` comment now says "true unless the config says false". No code changed; `native/` untouched. QA re-ran, at `25d111e4` in `_qa-scratch\coh-merge`: `check_version_docs.py` **OK, all docs cite v0.59**; `check_version_bump.py origin/main` **OK**. **N-2 stays open:** the Developer did not run `tests/web-ui` (it needs a live daemon on :18193 and a Playwright install) and CI does not run it; the checkbox is covered by the six JS tests, the payload-shape fixture and the C# overlay tests. **N-3 (data eras) is QA's.**

## What this record does and does not clear

This is the HK-039 review of `f684277f`. Verdict **CHANGES REQUIRED**, so no acceptance, merge-gate or CI run on this commit starts until R-1 is fixed and the delta is reviewed. The earlier record for `b8fc732e` still stands for that commit. Nothing is pushed.
