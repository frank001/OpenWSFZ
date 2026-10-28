> **Status note (QA, 2026-10-28).** The key, the three modes and the `Both` merge were built and measured in `9ef703d0` (Developer, `dev/coh-fb-audio`, HK-039 record `881518b8`,
> APPROVED with notes N-1..N-3). This change turns it into the product: default `Both` (Amendment 4, `bde72dc8`), N-1 required, version, requirement row. Not merged; nothing pushed.

## 1. Pre-implementation (record in `design.md` before writing code)

- [ ] 1.1 Re-check every FILE:LINE in `design.md` D3 on the branch tip (`Ft8Decoder.cs:1049-1061`, `CohFallbackParallelRunner.cs:65`); record drift.
- [x] 1.2 No new FR number: FR-099 (the key and its default) and FR-100 (`Both`) already exist from `9ef703d0`; the default is an amendment to FR-099 (done in `c9255ae2`).

## 2. Default and tests (Developer, `src/`)

- [ ] 2.1 An absent `decoder.coherentFallbackAudio` reads `Both` (was `Residual` in `9ef703d0`); explicit values unchanged. Fix the doc comment and any text that says "absent = Residual".
- [ ] 2.2 The test "absent key gives Residual" becomes "absent key gives Both"; explicit round trips and the HK-035 overlay test stay.
- [ ] 2.3 **N-1(a):** decoder-level test, `Both`, budget spent (`leftMs <= 0`) when the second run is due: the second run does not start, its eligible candidates are counted abandoned, the first run's rows publish. A stub backend with a controllable clock; no fixed delays (TESTING_STRATEGY §11); assert the second run's backend was never called and the abandoned count equals its eligible count.
- [ ] 2.4 **N-1(b):** same, with `0 < leftMs` below one run's wall time: the second run stops claiming at its budget (assert the number of candidates it processed is below its eligible count and the first run's rows still publish), and the end time is within the budget allowing for the candidate in flight.
- [ ] 2.5 The budget in the N-1 tests is a named constant derived from the production values (`SubtractionCycleBudget`, `CoherentFallbackPublishReserve`), not a bare number (QA review standard on magic numbers).

## 3. Configuration and docs

- [ ] 3.1 `VERSION`: one minor bump from the base for the arm (0.66), in every place the gates check (`REQUIREMENTS.md` anchor included, #266 R-1); run `check_version_bump.py` and G9a/b before reporting. G9b reads the proposal from git: commit this change first.
- [ ] 3.2 Any shipped or example config that writes the key writes `Both` (`config.example.json` today: check; add the key only if the file lists decoder keys).
- [x] 3.3 `REQUIREMENTS.md`: FR-099 amended to default `Both` (FR-100 holds the shared-budget rule), changelog row 1.62 (`c9255ae2`).
- [ ] 3.4 `native/` unchanged: `git diff --stat origin/main -- native` empty, `libft8` DLL SHA-256 reported against the pin.

## 4. Gates and acceptance

- [ ] 4.1 R0 unchanged (explicit `Original` and `Residual` byte-identical as before); the Developer reports the evidence.
- [ ] 4.2 QA HK-039 review of the new commit as a `*code-review*.md` FILE with `Reviewed-commit:` and `Verdict:` before any acceptance run.
- [ ] 4.3 `pre_merge_check.py` from a clean checkout of the exact commit (HK-006) before any push.
- [ ] 4.4 The Captain's push go (HK-033), CI green on the branch (QA pushes early: macOS result in about 6 minutes), the Captain's merge sign-off (HK-010).
- [ ] 4.5 After the deploy: the live era **"FB-AUDIO"** from the daemon's start time; board entry; never pool across it.
