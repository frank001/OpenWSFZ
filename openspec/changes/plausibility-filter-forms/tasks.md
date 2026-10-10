## 1. Implementation (Developer, HK-011; `Ft8Decoder.cs` only, nothing in `native/`)

- [ ] 1.1 Branch from `origin/main` (`8256a48f` or later). Confirm `git diff --stat -- native/` is empty at the end.
- [ ] 1.2 #226: `IsCallsignShapeInvalid` accepts `PREFIX/CALL` per spec §1.1 (either half may be the base; exclusion check on the base and on L under branch (b)).
- [ ] 1.3 #227: 3-token branch accepts `CQ <modifier> <call>` per §1.2; short-circuit before the last-field rule.
- [ ] 1.4 #228: 4-token branch accepts `CALL CALL R GRID` per §1.3; correct the `:930-931` comment (ft8_lib renders this form; the D-009 evidence predates #215).
- [ ] 1.5 Update the doc comments of `IsPlausibleMessage` and `IsCallsignShapeInvalid` to describe the new rules.
- [ ] 1.6 Addendum: `QsoAnswererService.TryParseCq` skips a CQ modifier when the next token parses as a callsign (spec `qso-answerer`; reuses the filter's parser). Separate commit.

## 2. Tests (Developer; Q-prefix calls only, NFR-021)

- [ ] 2.1 Positive: `CQ QA4/Q1ABC`; `Q2ABC QA4/Q1ABC`; `Q2ABC QA4/Q1ABC RR73`; `CQ DX Q1ABC`; `CQ POTA Q1ABC`; `CQ 123 Q1ABC`; `Q1ABC Q2XYZ R FN42`; `<...> Q2XYZ R FN42`.
- [ ] 2.2 Negative: `Q1ABC Q2XYZ R SS42`; `Q1ABC Q2XYZ X FN42`; `CQ DXDXD Q1ABC`; `CQ DX 3AG9672ATCH`; `QA4/3AG9672ATCH`; `12/Q1ABC`; a reserved prefix in L position.
- [ ] 2.3 Every existing `IsPlausibleMessage` / `IsCallsignShapeInvalid` test passes **unchanged**. A changed expectation is a stop-and-ask.

## 3. Version and gates

- [ ] 3.1 Bump VERSION; run G9b after committing (it reads the proposal from git). `User-facing: yes`.
- [ ] 3.2 Developer does not push or merge, and does not run `pre_merge_check.py` on its own initiative.

## 4. Validation (QA, offline, before the PR; bars frozen in the Architect's spec §4/§4b)

- [ ] 4.1 PV-0b first: old accepts ⇒ new accepts over every WSJT-X and OpenWSFZ text of `20261009_1752` plus the §2 negatives; 0 violations, 0 negative exceptions.
- [ ] 4.2 PV-0 desk: A re-run with NEW's filter: matched rejections 0; WSJT-X-only rejections fall by ≥ 1,700 of 1,744.
- [ ] 4.3 Product-path harness per checkout (OLD, NEW), same DLL SHA pinned at start and end; arms may run in parallel.
- [ ] 4.4 Repeat leg OLD vs OLD, 1-in-32 (seed 20261014): φ. Then PV-1 ≤ max(0.5 %, 3φ) on the 1-in-8 sample (seed 20261012).
- [ ] 4.5 PV-2 gain with CI by form; PV-3 per form (#226, #227 judged, #228 descriptive); PV-4 noise leg, 200 cycles (seed 20261013), gross check.
- [ ] 4.6 Region lookup does not throw on the new forms; QSO layer does not misread them.
- [ ] 4.7 Report with the exact `--filter` lines and DLL SHA pair (HK-022); aggregates only (HK-037); then the Captain's go for the PR (HK-033/010).
- [ ] 4.8 Open the new data era on the board at deploy.
