## 1. Tests first (each must be able to fail)

- [ ] 1.1 Unset: the budget handed to the residual pass at the one-stage call site and at the two-stage call site equals 13 s minus the pass-0 elapsed time (use the seam the existing `SubtractionDeadlineTests` use); and a fixed synthetic cycle decodes to the same rows as on the base commit.
- [ ] 1.2 Valid values: `13`, `13.0`, `30`, `unlimited` (any case) are accepted; the resolved budgets are 13 s, 13 s, 30 s and "no deadline".
- [ ] 1.3 Refused values: `12.99`, `0`, `-5`, `abc`, `""`, `13s`, `NaN`, `Infinity` each throw at construction with a message that names the variable and the rule.
- [ ] 1.4 Log line: ends with `budgetMs=13000` by default, `budgetMs=30000` with `30`, `budgetMs=unlimited` with `unlimited`; existing fields unchanged in name and order (extend `SubtractionLogLineTests`).
- [ ] 1.5 Construction warning appears once when an override is active and never when it is unset.

## 2. Implementation

- [ ] 2.1 Replace the static `SubtractionCycleBudget` with an instance value resolved once in the `Ft8Decoder` constructor from the override (QA proposes the environment variable `OPENWSFZ_SUBTRACTION_BUDGET`; the Developer may choose another name, documented in the code comment as replay-only).
- [ ] 2.2 Use the resolved value at both `SubtractionPass.RunAsync` call sites (`Ft8Decoder.cs` one-stage and two-stage). `unlimited` passes `deadline: null`.
- [ ] 2.3 Read `SubtractionPass.RunCore` for the `deadline == null` path and confirm in the PR that it adds no unbounded wait beyond the native fits themselves.
- [ ] 2.4 Add the trailing `budgetMs` field to the residual-pass summary line in `SubtractionPass.RunAsync` (the budget is the value the caller computed, which needs a new parameter or a property on the decoder side; keep the call signature change minimal and internal).
- [ ] 2.5 Log the construction warning when an override is active.
- [ ] 2.6 Nothing in `native/`; no shim version change; no change when the override is unset.

## 3. Verification

- [ ] 3.1 `dotnet build`, `dotnet test` green; `openspec validate --all --strict`.
- [ ] 3.2 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA validates (byte-identity of a fixed replay block on the base build against the new build with the override unset, plus a smoke run on `sol`); the Captain signs off the merge (HK-010).
