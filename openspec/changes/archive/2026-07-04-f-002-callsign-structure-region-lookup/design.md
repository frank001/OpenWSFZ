## Context

`Ft8Decoder.IsPlausibleMessage`/`IsCallsignOversized` (D9-R3, `src/OpenWSFZ.Ft8/Ft8Decoder.cs:382`,
`:548`) currently gates a callsign-position token on **length alone** (≤ 11 chars, raised from 6
by D-011 to admit genuine Type 4 nonstandard-callsign literals per `f-001-hashed-callsign-
resolution`). This reopened part of the D-009 false-positive hole for callsign-*shaped* OSD noise
that happens to be ≤ 11 characters — the live failure (`3AG9672ATCH`) is a concrete instance.

Primary-source research this session (WebSearch + WebFetch against `itu.int`'s Article 19
Section III PDF — text did not extract cleanly from the PDF's compressed content stream — and a
secondary summary via Wikipedia's "ITU prefix (amateur stations)" article, cross-checked against
the WebSearch snippet) confirms the universal ITU Radio Regulations Article 19 §19.68–19.69
structure for amateur callsigns:

> **Prefix** (1–3 characters, letters and/or digits, allocated internationally per the Table of
> Allocation of International Call Sign Series, Appendix 42) + **numeral** (a single separating
> digit, 0–9) + **suffix** (1–4 characters, the *last* of which must be a letter).

This is the standard/permanent-callsign shape. It is **not** sufficient on its own for this
change's purpose: Type 4's entire reason to exist is carrying callsigns that don't fit this
shape or the 28-bit Type 1 packing — compound calls (`PJ4/K1ABC`) and special-event/commemorative
callsigns issued by some administrations with wider numeral or suffix fields than the standard
form (e.g. multi-digit event numbers). A grammar rule that only accepts the strict P-N-S shape
would defeat D-011/f-001 by rejecting genuine nonstandard traffic again, just via a different
mechanism. The grammar therefore needs to accept a **superset** that still excludes garbage like
`3AG9672ATCH`.

**Verbatim-citation caveat:** the ITU PDF's exact clause wording could not be machine-extracted
this session (binary/compressed PDF stream). The structural facts above are corroborated by two
independent sources (WebSearch snippet directly quoting Article 19 language, and Wikipedia's
summary) and are consistent with long-established amateur-radio practice, but the developer
implementing `config/callsign-grammar.json` should do one pass confirming the exact clause
wording against the primary document (or ITU's official Radio Regulations volume, if available
via NARL/RSGB/ARRL secondary references) before treating the JSON file's `source` field as a
verified citation. Tracked as a task, not a blocker.

## Goals / Non-Goals

**Goals:**
- Close the residual FP hole D-011 reopened, using a *shape* rule instead of a raised length
  ceiling — reject `3AG9672ATCH`-class noise while continuing to admit genuine standard **and**
  nonstandard/special-event callsigns.
- Make the shape rule and the reserved/non-callsign-prefix exclusions JSON-configurable
  (`config/callsign-grammar.json`) so a future ITU reallocation doesn't require a code change.
- Provide an advisory, GUI-facing continent/country region lookup (`config/callsign-regions.json`)
  as a natural side effect of now parsing a valid callsign's prefix reliably — including a
  dedicated region for the project's synthetic Q-prefix test convention (NFR-021).
- Preserve every existing regression fence: `D009FpFilterTests`, `D011NonstandardCallsignFpGuardTests`,
  and the full existing decoder test suite must continue to pass.

**Non-Goals:**
- Full per-administration sub-allocation rules (e.g. FCC vanity/sequential call-district letter
  blocks, JARL's internal prefix-to-region mapping). The grammar gate operates at the universal
  Article 19 shape level plus a short *exclusion* list (see Decision 2) — not a fully exhaustive
  positive allow-list of every administration's assigned block.
- Exhaustive day-one coverage of `callsign-regions.json`. A partial table with a graceful
  "Unknown" fallback is acceptable and expected; expanding coverage is a follow-up.
- Any change to Type 1/2/3 standard-message validation paths unrelated to callsign-position
  tokens (D9-R1, D9-R2, D9-R4, R5 rules A/B/C are untouched).

## Decisions

### Decision 1 — Unified shape rule (not two separate branches)

Rather than maintaining a strict-standard branch and a separate nonstandard branch, use one
regex-equivalent shape rule that is a superset of the standard P-N-S form and still excludes the
observed garbage shape:

```
[prefix: 1-4 chars, letters/digits, containing at least one letter]
[digit-run: 1-3 consecutive digits — the call-area numeral (standard case: exactly 1) or a
            multi-digit special-event/commemorative number (observed real-world convention,
            e.g. some administrations' centenary/event calls use 2-3 digit numbers)]
[suffix: 1-6 chars, LETTERS ONLY — no digit may reappear once the suffix run begins]
```

with an overall token length ceiling of 11 characters (unchanged from D-011 — the Type 4
`ihashcall`/`pack58` charset width) and portable-suffix handling (`/P`, `/M`, `/MM`, `/QRP`,
`/A`, or a compound `/`-separated second callsign) kept as a separately-appended, already-handled
case, matching the existing `slashPos` split in `IsCallsignOversized`.

**Why this rejects `3AG9672ATCH` but not genuine traffic:** its digit-run is `9672` — four
consecutive digits — which exceeds the 3-digit cap under any known administration's numbering
convention (standard: 1 digit; the widest known special-event convention: 3 digits). No valid
callsign, standard or nonstandard, has digits reappearing after a 3-digit cap, so this closes the
hole without narrowing the door D-011 opened for genuine compound/special-event literals.

**Alternative considered — strict standard-only P-N-S with hard-coded nonstandard exemption
list:** rejected. It would require enumerating every administration's special-event convention by
hand (a maintenance burden with no natural JSON-table shape, unlike the allocation/region tables)
and would still need a numeric-run cap to reject `3AG9672ATCH`-class noise, so it doesn't buy
anything over the unified rule.

**Risk flagged for the developer:** the digit-run cap (3) and suffix-length cap (6) are
engineering-derived from the sources available this session, not copied from a single verified
clause. Before finalizing `config/callsign-grammar.json`, sanity-check both caps against any real
special-event callsign examples available (do not use real third-party callsigns in committed
tests — synthesize fictional Q-prefix examples matching the *shape* of any real edge case found),
and treat the S5 false-positive re-run (see Migration Plan) as the empirical backstop regardless
of how the caps are chosen.

### Decision 2 — `callsign-grammar.json`'s Appendix 42 data is an exclusion list, not a positive allow-list

A tempting design is "token's prefix must appear in the ITU allocation table to pass." **Rejected
outright**: any positive allow-list will always be incomplete relative to every real-world
callsign this decoder will ever hear, and an incomplete allow-list *rejects genuine traffic* —
strictly worse than the length-only status quo, which never rejects on prefix grounds at all.
Incompleteness in a reject-gate is a functional regression; incompleteness in an advisory lookup
(Decision 3) is just a blank field.

Instead, `callsign-grammar.json`'s table role is a short, high-confidence **exclusion list** of
prefix series ITU has never allocated for any station callsign (reserved for other uses — e.g.
the `Q`-series is reserved for Q-codes, not issued as a callsign prefix to any administration) —
plus an explicit **carve-out** for this project's own synthetic-use convention on exactly that
reserved `Q`-series (NFR-021), so a Q-prefix test callsign is affirmatively treated as
shape-valid rather than merely "not on a list of known-bad prefixes." This keeps the table small,
low-maintenance, and safe to ship incomplete.

### Decision 3 — `callsign-regions.json` is fully separate, best-effort, GUI-only

Independent file, independent store, independent failure mode (miss → `"Unknown"` label). Modeled
on the ham-radio-community "country file" (`cty.dat`-style) convention: prefix range → entity
(country/administration) name, continent, CQ zone, ITU zone. Seed the initial file with a
reasonably-sized set (recommend: the full ITU Appendix 42 country list at continent+entity
granularity is more tractable to source than a full DXCC file with zones — CQ/ITU zone columns
can be `null` where not sourced yet) plus the mandatory synthetic entry:

```json
{ "prefixStart": "Q", "prefixEnd": "Q", "entity": "Synthetic (R&R Study)", "continent": null,
  "cqZone": null, "ituZone": null, "synthetic": true }
```

GUI rendering rule: when `synthetic: true`, show the `entity` label verbatim (`"Synthetic (R&R
Study)"`) with no continent prefix; otherwise show `"{continent} — {entity}"` (e.g.
`"EU — Monaco"`), and `"Unknown"` alone on a lookup miss.

### Decision 4 — Region is computed server-side and attached to the existing decode payload

Rejected a separate `GET /api/v1/callsign-region?callsign=...` REST round-trip per decode row
(N+1 chattiness, and the daemon already parses callsign-position tokens out of decode text for
existing features — CQ-row highlighting, hash resolution). Instead, the daemon computes the
region alongside existing decode-text parsing and includes it directly in the decode-result
payload pushed over the existing WebSocket channel (new field, e.g. `region: string | null`),
consistent with how `web-frontend`'s existing decode-table requirements (CQ highlighting,
responder highlighting) are already driven by fields on that same payload. `web/js/main.js`
renders it as a new column/badge on the decode row, no new endpoint needed.

### Decision 5 — `Ft8Decoder`'s static validation methods gain a store dependency

`IsPlausibleMessage`/`IsCallsignOversized` are currently `internal static`, called both from
`Ft8Decoder`'s instance decode path and directly by `D009FpFilterTests`/
`D011NonstandardCallsignFpGuardTests`. The grammar/region tables must be loaded from disk once
(DI singleton, mirroring `IFrequencyStore`/`FrequencyStore`), not re-parsed per call, so:

- `IsPlausibleMessage` and the renamed `IsCallsignOversized` → `IsCallsignShapeInvalid` (name
  change reflects it now checks shape + exclusion-list, not just length) gain an
  `ICallsignGrammarStore` parameter.
- `Ft8Decoder`'s constructor gains an injected `ICallsignGrammarStore` (and, for the region
  bycatch, `ICallsignRegionStore`), following the existing constructor-injection pattern already
  used for `IClock`/`ILogger`/`IFt8NativeInterop`.
- Existing test call sites in `D009FpFilterTests`/`D011NonstandardCallsignFpGuardTests` update to
  pass a store instance (either a real store loaded from a small fixture JSON, or a fake/in-memory
  implementation of `ICallsignGrammarStore`) — expected, contained churn; both test files
  continue to assert the same behavioural contracts they do today, just with the new parameter
  threaded through.

**Alternative considered — static mutable holder populated once at startup:** rejected as a DI
anti-pattern (global mutable state, awkward to fake in parallel test runs, inconsistent with
every other config store in this codebase).

## Risks / Trade-offs

- **[Risk] Digit-run/suffix caps reject some genuine, unusually-shaped real callsign** →
  Mitigation: caps are conservative (wider than the standard case), the S5 false-positive re-run
  is a mandatory gate, and any future false-reject found in real off-air traffic (same discovery
  path as D-011 itself) is a fast, narrow follow-up fix to the JSON file, not a code change.
- **[Risk] `callsign-regions.json` initial coverage is sparse, operators see "Unknown" often** →
  Mitigation: explicitly acceptable per Non-Goals; "Unknown" is a correct, honest answer for an
  unlisted prefix, not a defect. Coverage expansion is incremental follow-up work.
- **[Risk] Refactor of `IsPlausibleMessage`/`IsCallsignOversized` to take a store parameter
  touches two existing regression-fence test files** → Mitigation: this is a mechanical
  signature change; the *assertions* in those tests are unchanged, only the call site gains an
  argument. Both files are explicitly listed as must-still-pass in the proposal and tasks.
- **[Risk] ITU wording in `callsign-grammar.json`'s `source`/comment fields is sourced from a
  secondary summary, not a verified primary quote** → Mitigation: flagged explicitly (Decision 1,
  Context); tracked as a task; does not block shipping since the *behavioural* rule (the shape
  regex) is independently justified by the false-positive re-run gate regardless of citation
  wording.

## Migration Plan

1. Add `config/callsign-grammar.json` and `config/callsign-regions.json` with seed data (small
   exclusion list + synthetic carve-out for the former; a reasonably-sized entity/continent list
   + mandatory synthetic entry for the latter), following the `frequencies.json` precedent for
   default-file-created-on-first-run behaviour.
2. Add `ICallsignGrammarStore`/`CallsignGrammarStore` and `ICallsignRegionStore`/
   `CallsignRegionStore`, DI-registered as singletons alongside `IFrequencyStore`.
3. Refactor `Ft8Decoder.IsPlausibleMessage`/`IsCallsignOversized` per Decision 5; update
   `D009FpFilterTests`/`D011NonstandardCallsignFpGuardTests` call sites.
4. Add new unit tests for the shape rule (including a fictional-placeholder reproduction of the
   `3AG9672ATCH` failure mode) and for both stores (including the synthetic Q-prefix carve-out
   and region-lookup miss → `"Unknown"`).
5. Wire the region field into the decode-result payload and `web/js/main.js` rendering.
6. Re-run `qa/rr-study/scenarios/s5-noise-wide.json` (same N=120 methodology as D-011 AC-4/D-009)
   and compare against the current 5.83%/120 figure (shim `f1e76d4`) — this change's acceptance
   gate.
7. No data migration risk: both JSON files are new, additive, and absent-file-safe (default
   created on first run); rollback is a plain revert, no schema downgrade needed.

## Open Questions

- Should the digit-run cap be 3 or should it be sourced per-administration from
  `callsign-grammar.json` itself (i.e. a per-block override) once real special-event examples are
  found that need a wider cap? Deferred to the developer's judgement during implementation and
  the S5 gate result — start with a single global cap of 3, add per-block overrides only if a
  genuine need surfaces.
- Is a continent-only fallback (no entity name) ever preferable to a flat "Unknown" when only
  partial data is available for a prefix? Left to the developer; `"Unknown"` is the safe default
  starting point.
