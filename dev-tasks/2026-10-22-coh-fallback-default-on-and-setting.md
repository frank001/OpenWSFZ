# Developer task: COH-FALLBACK default ON, and a Settings-page control for it

To: Developer. From: QA. Stamped 2026-10-22T17:36:39Z by `date -u`. **Captain's go (first-hand, QA's window, 2026-10-22 ~17:35Z):** *"first the dev session for default on, including the config page setting. Include the setting in gh issue #240 when he's at it."* **This authorises a `src/` and `web/` build and tests on the branch below. It does not authorise a push, a PR or a merge (HK-033, HK-010): QA does those, on the Captain's go.**

Base: **`feat/coh-fallback-stage1` at `b8fc732e`** (step 4, reviewed per HK-039, R14 live check ruled by the Architect §21). Commit on that branch (say so) so the work goes to `main` in one PR. **No push.**

## Why

The step-4 replay (D-GO′ NET +3.82 pp [3.44, 4.21], U′-OK) and the R14 live check passed, and the Captain is the only user and wants the fallback ON. The flag is `false` in code today (`DecoderConfig.cs:239`, constructor default at `:52`), and there is no Settings control (`DecoderConfig.cs` comment: "Config API / file only (no Settings-page control)"). Today it can only be turned on through the config API.

## What changes

1. **Default ON in code.**
   - `DecoderConfig.CoherentFallbackEnabled` defaults to **`true`**: both the constructor parameter default (`:52`) and the property initialiser (`:239`). **An absent key reads `true`; an explicit `false` stays `false`** (the same rule as `DecodingDepth`, where an absent key reads `Deep` and an explicit `"Normal"` stays Normal).
   - Check, with a test, that the JSON loader really gives `true` for an absent key (`JsonConfigStore.Load` has a documented quirk about source-generated deserialisation and absent keys; do not assume).
   - Update the doc comments that say "Default false" (`DecoderConfig.cs`, `Ft8Decoder.cs:200`, and anywhere else you find them).
   - **The flag-OFF behaviour must stay exactly what it was** (R13): the OFF identity tests stay, and now set the flag **explicitly to `false`**.
   - Existing tests that assert the default is `false` (for example `CoherentFallbackFlagConfigTests` and `CoherentFallbackWiringTests` "R10: … defaults to false") are changed **on purpose** to assert `true` for an absent key and `false` for an explicit `false`. List every test you change and why.
   - Any test that builds a decoder with a default config and so would now run the fallback unintentionally must set the flag explicitly. Say how you found them (run the suite, and grep the constructors).
2. **A control on the Settings page** (`web/settings.html`, `web/js/settings.js`).
   - A checkbox for `decoder.coherentFallbackEnabled`, in the decoder section next to the early-decode controls (`decoderEarlyEnabled`, `settings.js:407` and `:949`), with a label and a short help text that says what it does, in plain words: *"Coherent fallback: after the ordinary passes, try to decode weak signals the ordinary decode missed; their decodes appear as an extra batch. Takes effect on the next decode cycle."*
   - **Default ON when the key is absent**: no stored key shows the box checked. Follow the early-decode precedent (`settings.js:949`, "ON by default: no stored key shows checked (FR-083)").
   - It is saved through the normal config POST (an overlay: a body without the key must leave the stored value as it was; check this on this build, HK-035). It round-trips: save OFF, reload, shows unchecked; save ON, reload, shows checked.
   - Note on the interaction in the help text or a visible hint: it has an effect only while subtraction is enabled (`decoder.subtractionEnabled`).
   - Front-end tests in the existing style (`web/js/settingsPayload.test.js`, `earlyDefault.test.js`): the payload carries the key, the absent-key default is checked, a stored `false` shows unchecked.
3. **Status (optional, small):** if the status already serves what the decoder is using for the depth (`thirdPass.decodingDepth`), serve the effective fallback flag the same way, so QA can read back what is running instead of the config. If this is more than a few lines, say so and leave it out.
4. **OpenSpec (HK-002).** The pre-merge audit found **no OpenSpec change for COH-FALLBACK** (only an unrelated archived one). Add an OpenSpec change that records the fallback setting, its default ON, and the Settings control (the change is for the setting; the decoder feature itself is covered by the Architect's step-3 spec, which you may cite). If you judge that the repo's convention does not need one for this, say so and why, and QA reports it to the Captain.
5. **Docs.** README / settings docs: the new setting, the default, and that an explicit `false` in the config file turns it off. Say whether this needs a version bump or a changelog line under `tools/check_version_bump.py` (G9b reads the proposal from git: commit before running it).
6. **`decoder.decodingDepth` has no Settings control either** (issue #240 says "selectable in Settings"). **Not in scope unless the Captain says so.** If it is trivial to add beside the new control, tell QA the size and do not add it.

## Not in scope

No decoder change, no native change (`native/` diff must stay **empty**), no change to the batch logic. No push, no PR, no merge, no config edit on the station.

## Tests and report (what QA will read)

- The **full unfiltered `dotnet test OpenWSFZ.slnx`** and the web tests (`web/js`, command as the repo runs them); quote the exact command lines and the counts (passed / failed / skipped); no filtered run counts as the suite (HK-022).
- One test per behaviour in §1 and §2 above, each named for the behaviour, plus a test that an explicit `false` persists through a save and a reload.
- A short report: the commit hash(es), the list of changed tests and why, anything surprising, and the size of the optional items (§3, §6).
- **Stop and tell QA before pushing anything.** QA reviews the commit (HK-039) and commits a `Reviewed-commit:` record before any run on it.

## GitHub issue #240

The Captain asked that the setting be included in issue #240 while you work. QA posts that comment (the setting, its default, the Settings control) and will say when it is up; you do not need to touch GitHub.
