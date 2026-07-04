## 0. Pre-work verification

- [x] 0.1 Confirm the ITU Radio Regulations Article 19 §19.68–19.69 clause wording (structural
      facts sourced this session via WebSearch + a Wikipedia summary; the primary ITU PDF did not
      extract cleanly — see `design.md` Context). Update the `source`/comment fields in
      `config/callsign-grammar.json` once confirmed; this does not block the rest of the work
      since the behavioural rule is independently validated by the S5 gate (task 6).
      Re-confirmed via a second, independent WebSearch pass (a snippet quoting §19.68/19.69
      directly) — primary ITU PDF still not machine-extractable. Citation recorded in
      `CallsignGrammarConfig.BuiltInDefault`'s XML doc comment (Abstractions project) since no
      checked-in `config/callsign-grammar.json` seed file exists — see note on 1.1.
- [x] 0.2 Re-read `src/OpenWSFZ.Ft8/Ft8Decoder.cs` D9-R1–R5 rules end to end and confirm the
      planned shape-grammar replacement of D9-R3 does not alter D9-R1/R2/R4/R5 behaviour.
      Confirmed: only D9-R3's callsign check was replaced (`IsCallsignOversized` →
      `IsCallsignShapeInvalid`); D9-R1 (blank/whitespace), D9-R2 (hex dump), D9-R4 (grid/report),
      and R5 rules A/B/C are untouched. Full `dotnet test` run (243/243 Ft8 tests) confirms.

## 1. Configuration files and stores

- [x] 1.1 Create `config/callsign-grammar.json` with seed data: digit-run maximum (default 3),
      total-length maximum (default 11), reserved/never-allocated prefix exclusion list, and the
      `Q`-series synthetic-use carve-out entry (NFR-021).
      **Deviation:** no checked-in seed file at a `config/` path — the `configuration` spec
      requires `callsign-grammar.json` to resolve flat, next to `frequencies.json` (executable
      directory / data-directory override), not under a subfolder, and this project's established
      pattern for such files (`prop-modes.json`) has no checked-in repo seed either: the default
      values live in code (`CallsignGrammarConfig.BuiltInDefault`) and the file is written to the
      resolved runtime path on first run. Functionally equivalent to the task intent; flagged here
      for the developer/reviewer to confirm this reading is acceptable.
- [x] 1.2 Create `config/callsign-regions.json` with seed data: a reasonably-sized initial
      prefix → continent/entity table (CQ zone/ITU zone columns may be `null` where not yet
      sourced) and the mandatory `"Synthetic (R&R Study)"` entry for the `Q`-prefix series.
      Same deviation as 1.1 — seed data lives in `CallsignRegionDefaults.Entries` (Daemon
      project), ~35 real prefix→entity/continent entries plus the mandatory synthetic entry,
      written to the resolved runtime path on first run.
- [x] 1.3 Add `ICallsignGrammarStore`/`CallsignGrammarStore` in `OpenWSFZ.Abstractions`/
      `OpenWSFZ.Daemon` (mirroring `IFrequencyStore`/`FrequencyStore`): load-at-startup,
      data-directory override path resolution, default-file-created-on-first-run, malformed-file
      fallback to built-in defaults with a logged Warning.
- [x] 1.4 Add `ICallsignRegionStore`/`CallsignRegionStore` following the same pattern; malformed
      file falls back to Unknown-only behaviour with a logged Warning (not built-in seed data,
      since a corrupted region file has no safe non-empty default to fall back to).
- [x] 1.5 DI-register both stores as singletons alongside `IFrequencyStore`/`IConfigStore`.

## 2. Callsign structure grammar gate

- [x] 2.1 Design and implement the unified shape rule (prefix + capped digit-run + letters-only
      suffix, total length ≤ configured maximum) per `design.md` Decision 1, reading its
      parameters from `ICallsignGrammarStore` rather than hard-coding them.
      Implemented as `TryParseCallsignShape`: the digit-run is the maximal contiguous run of
      digits ending at the *last* digit in the token (not an arbitrary regex split), which is
      what correctly rejects `3AG9672ATCH` (trailing run `9672`, 4 digits) while accepting
      `Q0D011ABCDE` (trailing run `011`, 3 digits).
- [x] 2.2 Rename `IsCallsignOversized` → `IsCallsignShapeInvalid` (or developer's preferred name
      reflecting the broadened check) and thread an `ICallsignGrammarStore` parameter through it
      and `IsPlausibleMessage`, per `design.md` Decision 5.
      Both parameters are optional (default `null` → `CallsignGrammarConfig.BuiltInDefault`), so
      the ~10 pre-existing `Ft8Decoder`/`IsPlausibleMessage` call sites across the test suite that
      predate this change did not need touching — only `D009FpFilterTests`/
      `D011NonstandardCallsignFpGuardTests` (task 2.5) were updated, as the proposal anticipated.
      One correction found via the full test run: `RR73` (a terminal shorthand, not a callsign)
      needed an explicit exemption in `IsCallsignShapeInvalid` alongside the ≤3-char/hash
      exemptions, since the 2-token "check both tokens" path evaluates it as a callsign-position
      token — fixed and covered by the existing D009 Gap A / R5 Rule C regression tests.
- [x] 2.3 Add the constructor-injected `ICallsignGrammarStore` dependency to `Ft8Decoder`,
      following the existing `IClock`/`ILogger`/`IFt8NativeInterop` injection pattern.
- [x] 2.4 Implement the reserved-prefix exclusion list check (including the synthetic carve-out)
      as an additional signal alongside the shape rule — not a positive allow-list (per `design.md`
      Decision 2).
- [x] 2.5 Update `D009FpFilterTests` and `D011NonstandardCallsignFpGuardTests` call sites to pass
      a store instance (real store loaded from a small fixture JSON, or a fake/in-memory
      `ICallsignGrammarStore`); assertions in both files must remain unchanged in intent.
      Both files now pass `FixedCallsignGrammarStore.Default` (a new shared test double,
      `tests/OpenWSFZ.Ft8.Tests/FixedCallsignGrammarStore.cs`) — assertions unchanged; full suite
      confirms (`D009FpFilterTests` 0 failures, `D011NonstandardCallsignFpGuardTests` 0 failures).

## 3. Region lookup

- [x] 3.1 Implement region resolution (`ICallsignRegionStore.TryGetRegion` or equivalent) —
      prefix match → continent/entity/synthetic flag; miss → `"Unknown"`.
      Longest-matching-prefix-range lookup; miss returns `null` (frontend renders `"Unknown"`).
- [x] 3.2 Wire region resolution into the decode pipeline so each decode-result payload sent over
      the existing WebSocket channel includes a `region` field (per `design.md` Decision 4 — no
      new REST endpoint), computed from the message's caller-identification callsign token.
      `DecodeResult.Region` (new optional field, default `null` — zero-touch for the ~50 existing
      `new DecodeResult(...)` call sites) is populated in `Ft8Decoder.DecodeAsync` via the new
      `ExtractPrimaryCallsignToken` helper (CQ-caller / Standard-QSO-sender token, portable suffix
      stripped) + `ICallsignRegionStore.TryGetRegion`.
- [x] 3.3 Confirm region resolution failures (missing file, malformed file, lookup exception)
      degrade to `"Unknown"` and never withhold or alter the underlying decode (per the
      `region-lookup` capability's "advisory only" requirement).
      Wrapped in try/catch in `DecodeAsync`; covered by `RegionLookupTests` (throwing store, no
      store, unmatched prefix — all still return the decode with `Region = null`).

## 4. GUI

- [x] 4.1 Add the region column/badge to the decode table row rendering in `web/js/main.js`,
      following the existing `decode-cq`/`decode-responder` row-rendering conventions.
      New `<th>Region</th>` column in `web/index.html`, populated via `makeCell(formatRegion(r.region))`
      at row-creation time in `handleDecodes`.
- [x] 4.2 Implement the three rendering rules: `"{continent} — {entity}"` for a recognised
      region, `"Synthetic (R&R Study)"` (no continent prefix) for the synthetic flag, `"Unknown"`
      for a miss.
      New `formatRegion()` helper in `main.js` implements all three rules.
- [x] 4.3 Confirm the column renders at row-creation time with no additional network round-trip
      (region value already present on the decode payload).

## 5. Test coverage

- [x] 5.1 Add a managed-layer regression test reproducing the `3AG9672ATCH` failure mode with a
      fictional placeholder token, asserting it is now rejected.
      `CallsignShapeGrammarTests` (new file, `tests/OpenWSFZ.Ft8.Tests/`).
- [x] 5.2 Add a managed-layer test asserting a genuine nonstandard/special-event-shaped literal
      (fictional Q-prefix, ≤ 11 chars, digit-run within cap, letters-only suffix) is still
      accepted — this must not regress the D-011 fix.
      Same file — includes D-011's own `Q0D011ABCDE` fixture plus a fictional 3-digit
      special-event literal (`Q100ABC`).
- [x] 5.3 Add unit tests for `CallsignGrammarStore`/`CallsignRegionStore`: default-file creation,
      data-directory override, malformed-file fallback behaviour, synthetic Q-prefix carve-out in
      both stores.
      `CallsignGrammarStoreTests` / `CallsignRegionStoreTests` (new files,
      `tests/OpenWSFZ.Daemon.Tests/`) — mirrors `FrequencyStoreTests`'s temp-directory pattern.
      "Data-directory override" is exercised at the same fidelity as the `IFrequencyStore`
      precedent (no dedicated override test exists there either — the store takes a resolved
      path; override resolution is Program.cs's responsibility, unchanged pattern).
- [x] 5.4 Add a test asserting an unmatched prefix in `callsign-regions.json` resolves to
      `"Unknown"` and does not affect decode acceptance.
      `CallsignRegionStoreTests.TryGetRegion_UnmatchedPrefix_ReturnsNull` +
      `RegionLookupTests.DecodeAsync_UnmatchedCallsign_ResolvesNullRegion_StillAccepted`.
- [x] 5.5 Confirm `D009FpFilterTests` and `D011NonstandardCallsignFpGuardTests` pass unmodified
      in assertions (signature changes only, per task 2.5).
      Verified via full test run.
- [x] 5.6 Full `dotnet test` run — 0 failures.
      791/791 passed across all 9 test projects (243 in `OpenWSFZ.Ft8.Tests`, up from 224 —
      19 new tests added by this change).

## 6. R&R acceptance gate

- [x] 6.1 Re-run `qa/rr-study/scenarios/s5-noise-wide.json` (same methodology as D-011 AC-4 /
      D-009) with this change's grammar gate live.
      **Correction (QA review, 2026-07-04):** the methodology this task originally cited —
      "WSL2 Debian daemon build/run … per `RUNBOOK.md` §5" — is the three-appraiser
      cross-platform rig (Windows daemon + Linux/WSL2 daemon + WSJT-X), suspended
      indefinitely by `RUNBOOK.md` §7 and never the right rig for this gate regardless
      (a same-platform before/after check, not a cross-platform one). Corrected to the
      D-011 AC-4 recheck methodology — see below.
      **Run (2026-07-04, SHA `a3738fc`):** single Windows daemon (Release build, this
      change's committed SHA) + VB-CABLE, WSJT-X as reference/control appraiser, warm-up
      cycle independently verified via both apps' `ALL.TXT` (cycle `164115`, not taken on
      trust from `warmup.py`'s own prompt), then the timed N=300 run of
      `s5-noise-wide-n300.json` (a sibling of `s5-noise-wide.json` differing only in
      `trials`, per the sample-size note below). Result:
      `qa/rr-study/results/2026-07-04-a3738fc-f002-s5-n300/report.md`.
      **Sample size:** ran at **N=300** (not the original N=120) per the D-011 AC-4
      recheck's own finding #1, which flagged N=120 as merely "confirmatory" for a
      result this close to the ceiling.
      **Data-integrity correction applied mid-analysis:** WSJT-X's persistent `ALL.TXT`
      still carried two pre-run warm-up decodes outside this run's cycle range; caught
      before recording the result, filtered via a cutoff timestamp, and re-matched — see
      report.md §2. Flagged as a process follow-up (report.md §5 finding #5), not a defect.
- [x] 6.2 Compare the resulting false-positive rate against the current 5.83%/120 figure (shim
      `f1e76d4`, N=120 baseline — compare rates/CIs, not raw counts, given the larger N above);
      confirm no regression (ideally an improvement, since shape-invalid `3AG9672ATCH`-class
      noise should now be rejected). Gate per `STUDY-SPEC.md` §10 as ratified under R&R-004
      (95% Clopper–Pearson upper bound ≤ 6%).
      **Result: PASS, and a genuine improvement** — OpenWSFZ 8/300 (2.67%/slot, 95% UB
      4.76%) vs. baseline 7/120 (5.83%/slot, 95% UB 10.68%). Both the point estimate and
      the 95% UB roughly halved. WSJT-X (control) 0/300, 95% UB 0.99%.
- [x] 6.3 Record the result in this change's QA notes (report.md, per HK-001 report-section
      convention), following the D-011 §6 QA-notes precedent.
      `qa/rr-study/results/2026-07-04-a3738fc-f002-s5-n300/report.md` (+ rendered
      `report.html`). Sections 1/2/5 QA-authored; 3–4 harness-generated (`analyse.py`).
      §5 records two residual-risk findings: (a) 2 of the 8 FPs share an identified
      shape hole (single digit buried in an otherwise-long letter run, 4-char prefix at
      the current `PrefixLengthMax` ceiling) — tested fix (cap→3) confirmed
      non-regressive against the full 244-test suite, recommended as a small separate
      follow-up, not a merge blocker; (b) the remaining 6 FPs are structurally
      indistinguishable from genuine QSO traffic (valid compound calls + valid grids) —
      D-009's domain, not addressable by any shape-grammar rule.

## 7. Documentation and handoff

- [x] 7.1 No real third-party callsigns in any committed file, config seed data, or test fixture
      (NFR-021) — confirm before merge.
      Reviewed all new/changed files. `CallsignRegionDefaults.Entries` uses public-domain
      ITU/DXCC prefix-block → country/continent reference data (not individual assigned
      callsigns). All test fixtures use fictional Q-prefix synthetic calls or fictional
      placeholders shaped to match observed/hypothesised failure modes (`3AG9672ATCH`,
      `ZZ1ABC`, etc.) — several (`VK9AA`) reuse a shape already established as a fictional
      example in the pre-existing `D009FpFilterTests`. No real third-party callsigns found.
- [x] 7.2 Cross-link this change from `dev-tasks/2026-07-03-d-011-nonstandard-callsign-fp-guard.md`
      as the follow-up that closes its flagged residual risk.
      Added a "§7. Follow-up" section to that dev-task pointing here.
- [ ] 7.3 Run `/opsx:archive` once merged and the R&R gate (task 6) has passed.
      **Unblocked** — task 6's R&R gate PASSED 2026-07-04 (see 6.1–6.3 above). Remaining
      before archive: open a PR from `feat/f-002-callsign-structure-region-lookup`,
      merge to `main`, then run `/opsx:archive`.
