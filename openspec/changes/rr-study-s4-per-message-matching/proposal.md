## Why

The R&R study's S4 (Density/QRM) scenario is meant to measure per-appraiser message
recovery under simultaneous-signal interference, feeding the pooled attribute-Kappa
gate (STUDY-SPEC.md §9.3/§10). A QA investigation (`qa/rr-study/RR-007.md`, GitHub #59)
found that `harness/matcher.py`'s S4 matching path pools every message injected into a
cycle into a single truth row and scores a match as "the appraiser decoded *any one* of
the N messages" — not one outcome per message. This creates a severe ceiling effect:
live data (run `793a298`) shows **both** appraisers scoring a perfect TP=15/FN=0,
κ=1.000, PASS on S4, while the same run's S7 scenario (which already matches truth per
individual message) shows OpenWSFZ recovering only 40% of co-channel stacks against
WSJT-X's 100%. S4 currently cannot distinguish good QRM handling from bad, which blocks
any Captain decision on ratifying the attribute-Kappa gate and undermines S4's own
stated purpose ("recovery Kappa vs truth and between appraisers").

## What Changes

- S4 truth generation emits one truth row per **individual injected message** (part,
  trial, message), each carrying that message's own `true_snr_db` and `true_freq_hz` —
  not one pooled row per cycle with a semicolon-joined message list.
- `matcher.py`'s S4-specific matching branch consumes at most one candidate decode per
  truth row and scores each message's match/miss independently, so a busy cycle (e.g.
  30 simultaneous signals) yields up to 30 independent outcomes instead of one
  aggregate outcome.
- `analyse.py`'s pooled attribute-agreement computation (`_attribute_agreement`) and any
  S4-specific report sections are updated to consume the new per-message row shape
  without changing the underlying pooled-κ method itself (S4 positives + S5 negatives).
- **BREAKING** (harness-internal only, not product-facing): `S4_matched.csv` and
  `truth.csv` row shape for S4 changes from one row per (part, trial) to one row per
  (part, trial, message). Any ad-hoc analysis scripts reading the old shape must be
  updated; none are known outside `harness/`.
- S4 is re-run once implemented and the pooled-κ analysis re-evaluated against real
  per-message, SNR-aware data. This re-run is in scope; **ratifying** the attribute-Kappa
  gate as a hard gate on the strength of that data is explicitly **out of scope** — that
  remains a separate Captain decision (tracked informally by STUDY-SPEC.md §9.3's
  ratification conditions; no dangling ticket this time, per the R&R-005 lesson).

## Capabilities

### New Capabilities
- `rr-density-qrm-scenario`: the S4 Density/QRM scenario's per-message truth generation
  and matching contract — one truth row per injected message (not per cycle), each
  independently scored, so recovery and agreement metrics reflect true per-message
  outcomes under multi-signal interference. Mirrors the documentation precedent of the
  existing `rr-band-scene` and `rr-linked-cycle-effectiveness-scenario` capabilities,
  which formalised other previously-undocumented scenario/harness behaviours.

### Modified Capabilities
_(none — S4's truth/matching behaviour predates OpenSpec capability tracking and has no
existing spec to amend; this proposal documents it for the first time as part of fixing it.)_

## Impact

- **Affected code:** `qa/rr-study/harness/matcher.py` (S4 matching branch,
  `_matched_row`/`_miss_row` construction), `qa/rr-study/harness/run_scenario.py` (S4
  truth-row emission), `qa/rr-study/harness/analyse.py` (`_attribute_agreement` and any
  S4-specific report rendering), `qa/rr-study/scenarios/s4-density.json` (no schema
  change expected, but truth generation reads it differently).
- **Affected data:** `S4_matched.csv` and the S4 slice of `truth.csv` row shape, for all
  future runs. Historical run artifacts under `qa/rr-study/results/*/S4_matched.csv` are
  unaffected (read-only history) but will no longer match the new shape's row count if
  compared programmatically.
- **Affected docs:** `qa/rr-study/STUDY-SPEC.md` (S4 scenario description, §9.3 note
  context), `qa/rr-study/RR-007.md` (this change resolves its recommendation).
- **Not affected:** S1–S3, S5, S7, S8 scenarios and their matching logic; the pooled-κ
  *method* itself (S4 positives + S5 negatives) is unchanged; product/app code
  (`OpenWSFZ` itself) is untouched — this is QA test-harness-only work.
- **Regression risk:** low-to-moderate. The main risk is inadvertently changing S7's
  matching path (which already does per-message matching correctly and must not
  regress) or breaking `analyse.py`'s existing 92-test unit suite, which assumes the
  current S4 row shape in places.
