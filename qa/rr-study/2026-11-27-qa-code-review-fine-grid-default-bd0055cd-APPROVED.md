# QA code review (HK-039): the lean decoder runs THIN + the 4 x 4 grid by default

**Reviewed commit:** `bd0055cdbcd2d02ba4203f0ccb4062b4f8c148b3` (`feat/fine-grid-default`; two commits on `qa/sprint-known-erasure` `6a53a9f9`: `ae7fbf5b` the change, `bd0055cd` a comment-only fix; not pushed)
**Reviewed-commit:** bd0055cdbcd2d02ba4203f0ccb4062b4f8c148b3
**Verdict:** APPROVED (one required change in `ae7fbf5b`, done in `bd0055cd`)
**Reviewer:** QA, 2026-11-27. Read: the whole diff of both commits against `dev-tasks/2026-11-27-fine-grid-ship-thin-and-fine-as-lean-default.md`.

## What it does, and was checked

- **Managed request only.** Three internal constants in `Ft8Decoder` (`LeanThin` true, `LeanTimeOsr` 4, `LeanFreqOsr` 4, each documented, no magic numbers at the call site) are passed in the `LeanCycleParams` the lean cycle builds; the XC round's request is derived from the same one, so both carry them. `LeanCycleParams`' own defaults (off / 0 / 0), the native defaults and every test that builds its own request are unchanged; the classic decoder never reads the parameters. No native change, no shim bump, `libft8.dll` unchanged (SHA256 `0ef023d55a381db9…`).
- **The test** (`LeanEngineXcRoundManagedTests`, a recording fake) asserts that the cycle's requests and the XC round's request carry thin 1 / 4 / 4, that the constants equal them and that a plain `LeanCycleParams` stays off.
- **Documents:** FR-108 amended, changelog 1.82, OpenSpec section 16; no VERSION bump required (the Developer's `check_version_bump.py`).
- **The one required change** (`ae7fbf5b`): the new constants had been inserted between the XC-BUILD R6 summary and `CrossCyclePriorThresholdDefault`, so that summary documented `LeanThin` and the threshold lost its doc. `bd0055cd` moves the three constants before the R6 summary: QA read the diff, four lines moved, comment and ordering only, no behaviour change.
- **Developer's runs** (QA repeats the whole suite in `pre_merge_check` at the sprint PR): Config 237, Web 464, Daemon 963, Ft8 at 4 processors 940 (also 940 on `ae7fbf5b` at the default processor count, so no existing test changed on the real native 4 x 4 path), JS 131.

## Note

The replay behind this default (`fine-grid-result.md`) ran the same request through the harness wrapper; the shipped path is the managed request, so the default is the same search the replay measured. It changes the station's decoder only (the Captain is the only user): the Captain's go is on record ("go with recommendations").
