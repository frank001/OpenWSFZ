## Context

The residual (subtraction) pass gets "whatever remains" of a 13 s per-cycle budget after pass 0 (`SubtractionCycleBudget - sw.Elapsed`, passed as `deadline` to `SubtractionPass.RunAsync` at two call sites, one-stage and two-stage). Inside the pass the native fits are cancelled at `deadline - SubtractionResidualDecodeReserve` (1.5 s) and the pass abandons itself (pass-0-only) when it runs out. `RunAsync` already treats `deadline == null` as "no deadline" (`RunCore`: `Expired()` is false, `fitBudget` is null, the reserve check is skipped).

## Decisions

1. **One read, at construction.** `Ft8Decoder` resolves the effective budget once (an instance field replaces the static one) and uses it at both call sites. No per-cycle environment reads.
2. **Unset is the identity.** With the variable unset the field equals `TimeSpan.FromSeconds(13)`, and the value passed to `SubtractionPass.RunAsync` is exactly what the current build passes. No other line of the decode path changes.
3. **"Unlimited" is expressed as a null deadline** at the call sites, which `RunAsync` already supports. The Developer must confirm by reading `RunCore` that the null path introduces no unbounded wait other than the fits themselves, and say so in the PR.
4. **Refusal is loud.** A malformed or too-small value throws at `Ft8Decoder` construction with a message naming the variable and the rule. The process does not start with a silently different budget. (A daemon that is mis-launched with a bad value fails at start; that is the intent.)
5. **Observability on the existing line.** The residual-pass summary line gains one trailing field, `budgetMs={BudgetMs}` (the effective budget in milliseconds, or `unlimited`). Existing field names and order are unchanged so the current parsers (`SubtractionLogLineTests`, the replay harness) keep working. The line stays aggregate-only (HK-037).
6. **A construction-time warning** (once per decoder) when the override is active: "subtraction budget override active (replay only): <value>". It is the run-conditions record the harness copies into its reports.
7. **Why an environment variable and not config.** A `config.json` key would be saved by every Settings write, need an overlay/migration decision (HK-035), and invite use by real users. The study harness launches its own process and can set the variable per run.

## Risks

- The override is a blind spot by design: a build whose decoder would bind the budget on the station is invisible on a replay host with the budget lifted. The mitigation is outside the code: leg F on the station PC with the budget unset, once per release (spec 2m).
- A user who sets the variable by accident gets a decoder that can exceed the cycle: the warning line and the `budgetMs` field make that visible in the log.
