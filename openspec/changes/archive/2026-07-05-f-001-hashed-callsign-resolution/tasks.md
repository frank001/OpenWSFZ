## 1. Native shim — persistent hash table (D1)

- [x] 1.1 Confirm the current `FT8_SHIM_VERSION` value in `ft8_shim.c` at implementation time and
      reserve the next sequential version number (design D4); do not assume `20260030` is still
      current.
      → Confirmed 20260030 was current; reserved 20260031.
- [x] 1.2 Add a process-global `static callsign_table_t g_session_hash_table` (and an
      initialisation guard, e.g. `static bool g_hash_table_initialised`) near the existing
      `tls_hash_table` declaration in `ft8_shim.c`.
- [x] 1.3 In `ft8_decode_all`, replace the per-call stack-local `callsign_table_t htbl` /
      `hash_table_init(&htbl)` with: initialise `g_session_hash_table` once on first use, then set
      `tls_hash_table = &g_session_hash_table` at the top of every call (no re-init on subsequent
      calls).
- [x] 1.4 Confirm `tls_hash_table = NULL` still executes on both the normal-return path and the
      `__except` (SEH) path, and that neither path calls `hash_table_init` on
      `g_session_hash_table` (design D2 — contents survive a caught AV; only the pointer is
      detached).
      → Confirmed unchanged; neither path was ever modified by this task.
- [x] 1.5 Leave `ft8_encode_message`'s existing per-call local table untouched — encoding computes
      hashes fresh via `ihashcall` and does not depend on prior session state (per design Context).
      → Confirmed untouched (still saves/restores `tls_hash_table` around its own local table).
- [x] (discovered during implementation) `Ft8LibInterop.cs`'s `ExpectedShimVersion` constant
      (line ~203) is a separate managed-side copy of the ABI version check, not mentioned in
      proposal.md's Impact section ("no required change to Ft8Decoder.cs" — true, but this is
      a different file). Bumped 20260030 → 20260031 to match; without this, `LoadAndVerify()`
      throws `InvalidOperationException` for every native call against the rebuilt DLL. Noted
      here so this isn't lost as a "no managed change" false assumption in future shim bumps.
- [x] 1.6 Update the version-history comment block at the top of `ft8_shim.c` with a new entry
      describing this change, following the existing style (see prior entries such as
      `fix-d004-local-noise-floor`, `decoder-settings-page`) — reference this change's name and
      summarise the persistent-table behaviour and the D2/D3 decisions.

## 2. Native shim — diagnostics (optional per design Open Questions)

- [x] 2.1 Decide whether to add a native-only counter/log for `hash_table_add`'s
      reject-when-full guard (design's saturation risk mitigation), or defer until real session
      logs show it triggering. If added, keep it native-only (no new P/Invoke surface) per the
      Open Questions recommendation.
      → Added `static int g_hash_table_reject_count` (native-only, no P/Invoke surface),
      incremented inside `hash_table_add`'s existing full-table guard, per the Open
      Questions' recommendation.

## 3. Tests — native/shim-level

- [x] 3.1 Add a synthetic two-cycle test: encode a Type 4 message announcing a nonstandard
      callsign, decode it via `ft8_decode_all` in "cycle 1," then encode and decode (in a
      separate `ft8_decode_all` call, "cycle 2") a Type 1/2/3 message referencing that callsign's
      22-bit hash; assert the cycle-2 decoded text contains the full callsign rather than a hash
      placeholder. Covers the primary spec requirement (Cross-cycle callsign hash resolution).
      → `HashedCallsignResolutionTests.CrossCycleResolution_Type4ThenHashReference_ResolvesFullCallsign`.
      `ft8_encode_message`'s auto-dispatcher can never actually reach `ftx_message_encode_nonstd`
      for well-formed callsigns (`pack28`'s nonstandard-hash fallback always makes
      `ftx_message_encode_std` succeed first), so a new `TestFt8Encoder.PackType4CqAnnounce`
      hand-packs a genuine Type 4 wire signal instead — see that method's doc comment.
- [x] 3.2 Add a regression test confirming a hash with no prior Type 4 announcement in the
      session still decodes to the existing `<...>` placeholder (unchanged behaviour) — covers
      "Never-announced hash remains unresolved."
      → `HashedCallsignResolutionTests.NeverAnnouncedHash_DecodesToPlaceholder`.
- [x] 3.3 Add a regression test confirming same-cycle resolution (Type 4 and its hash reference
      both decoded within one `ft8_decode_all` call) still works — covers "Same-cycle resolution
      continues to work."
      → `HashedCallsignResolutionTests.SameCycleResolution_Type4AndHashReferenceInOneCall_BothResolve`.
- [x] 3.4 Add a table-saturation test: fill the table to its 256-entry capacity with distinct
      callsigns, then attempt to add one more; assert the new callsign is rejected and all
      previously stored entries remain resolvable and unchanged — covers "Bounded hash table
      growth."
      → `HashedCallsignResolutionTests.HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive`.
      The table is process-global and shared by the whole test assembly with no reset entry
      point (by design), so the test can't assume it starts empty — it sidesteps this by adding
      264 (> 256) distinct new callsigns itself, batched 8-per-DecodeAll-call for CI runtime.
      See the test's doc comment for the full reasoning.
- [x] 3.5 Add (or extend an existing) AV-path test confirming that after a simulated/forced fault
      path, a subsequent unrelated `ft8_decode_all` call executes normally and previously learned
      hash mappings from before the fault remain resolvable — covers "Exception-path safety." If
      the existing D-006 AV test harness cannot easily simulate a fault mid-decode, document why
      and cover this via careful code review of the exception path instead; note the gap in the
      PR description.
      → Gap confirmed and documented: `AvContainmentTests`'s `ThrowingNativeInterop` is a pure
      C# fake that never calls into the real native shim, so it cannot simulate a genuine AV
      mid-decode. Documented in `AvContainmentTests.cs`'s class summary; covered instead by code
      review of the `__except` handler (only ever executes `tls_hash_table = NULL;`, never
      touches `g_session_hash_table`'s contents — see design D2).
- [x] (discovered during implementation) Test-suite parallelization risk: the persistent table
      is the first native global *written* concurrently by decode calls across xUnit's
      default parallel test-class execution (previously each call had an isolated stack-local
      table). Flagged to the user; resolved by disabling assembly-wide test parallelization
      (`tests/OpenWSFZ.Ft8.Tests/AssemblyInfo.cs`, `[assembly: CollectionBehavior
      (DisableTestParallelization = true)]`) so every native-decode test observes a single,
      serialised view of the table.

## 4. Managed-layer verification (no code change expected)

- [x] 4.1 Confirm `Ft8Decoder.cs`'s `IsPlausibleMessage` and the D-005 trim-fix path require no
      changes — run the existing `D005MessageTrimTests` and `Ft8DecoderPlausibilityTests` suites
      unmodified against the updated native shim to confirm no regression.
      → Both suites pass unmodified (see 5.2 full-suite run); no code changes needed, confirming
      the proposal's Impact section assessment for these two files.
- [x] 4.2 Confirm no existing R&R study synthetic corpus scenario exercises nonstandard/hashed
      callsign forms (per the proposal's Impact section); if one is found to exist, re-run the
      relevant R&R scenario and record the result in the change's QA notes before merge.
      → Confirmed: the S1–S8 synthetic corpus (qa/rr-study) and the committed
      `synth-qso-01/02/03` fixtures use only standard 6-char-shaped fictional Q-prefix
      callsigns (Q1AW, Q1ABC, Q9XYZ, etc.) — none are nonstandard/compound-shaped, so none
      exercise the Type 4 / hash-reference path. No re-run needed; this change is additive to a
      message class not currently exercised by the corpus, matching the proposal's Impact
      section.

## 4a. Effectiveness validation (added 2026-07-04 — regression-only coverage was not enough)

QA review 2026-07-04 noted that sections 3–4 above prove the mechanism is *correct in
isolation* (native shim, unit-level) but not that it is *effective* — i.e. that a resolved
callsign actually reaches the operator-facing layer, and that it works on real traffic.
Three gaps identified and closed/tracked as follows:

- [x] 4a.1 **Managed-pipeline gap**: no existing test chained two `Ft8Decoder.DecodeAsync`
      calls (real interop) to confirm a cross-cycle *resolved* callsign survives the D9-R3
      false-positive guard (`IsPlausibleMessage`/`IsCallsignOversized`) on its way out —
      only the raw `Ft8LibInterop.DecodeAll` path (this change's own tests) and single-cycle
      literal-announcement survival (D-011's tests) were covered. This gap is exactly why
      D-011 (a resolved/literal nonstandard callsign token being silently filtered) was only
      caught on live traffic, not by any automated test — closing it here reduces the chance
      of a sibling defect recurring unnoticed for the *resolution* path specifically.
      → Added `HashedCallsignResolutionTests.CrossCycleResolution_ThroughManagedDecodeAsync_ResolvedCallsignReachesOperatorFacingLayer`:
      chains two real-interop `Ft8Decoder.DecodeAsync` calls and asserts the resolved
      callsign text (not a placeholder, not filtered) reaches the second call's results.
      212/212 full suite green.
- [x] 4a.2 **Real-world effectiveness evidence**: this change's own artifacts never recorded
      whether the feature actually works against real off-air traffic — that evidence exists
      but was only ever written up in a *different* defect's dev-task. Recorded here for
      discoverability: during the live 1-hour R&R session on 2026-07-03 that led to D-011
      (`dev-tasks/2026-07-03-d-011-nonstandard-callsign-fp-guard.md` §1), the session-scoped
      hash table correctly showed the unresolved placeholder for a real special-event
      station's callsign at the very first cycle of the session (before it had heard
      anything), then correctly resolved it for every subsequent correspondent reply for the
      rest of the 45+ minute session, matching WSJT-X's own decode text exactly. The defect
      found in that session (D-011) was a *different, adjacent* bug — the FP guard
      discarding the station's own literal announcements — not a failure of the
      cross-cycle resolution mechanism itself, which worked throughout. No real callsigns
      reproduced here, per NFR-021.
- [x] 4a.3 **Statistical effectiveness under realistic SNR/QRM**: no R&R-harness scenario
      exists measuring hash-resolution rate as decode conditions degrade, separate from
      whether the table mechanism itself is correct. `qa/rr-study/synth/packing.py`
      explicitly excludes Type 4 / hashed-callsign packing (`NotImplementedError`, "out of
      scope for the first R&R study"), and `run_scenario.py`'s model plays independent
      slots/trials scored against their own truth row — there is no existing concept of a
      linked two-cycle announce→reference pair with "resolved" as a distinct outcome from
      "decoded." Closing this requires: (a) extending the synth encoder for Type 4 packing +
      `ihashcall`, (b) extending the harness to link a two-cycle pair and score resolution as
      its own metric, (c) a live-audio-rig run (same requirement that got 5.3 deferred).
      Scoped as a design proposal for Captain's review before harness-engineering effort
      begins — tracked separately, not blocking this change's own closure.
      → Full proposal drafted 2026-07-04:
      `openspec/changes/rr-study-hashed-callsign-effectiveness/` (proposal.md, design.md,
      specs/, tasks.md — all four artifacts complete, `openspec validate --strict` passes).
      → **Implemented and closed 2026-07-04.** Live-rig run
      `qa/rr-study/results/2026-07-04-22c3a94/` (report.md §1/§5): S9 (cross-cycle resolution)
      100% resolved, both appraisers, 10/10 pairs across both SNR points; S11 (Type 4 decode-rate
      sweep) 100% decode rate, both appraisers, across the full −15…0 dB SNR sweep. No evidence
      of a Type 4 decode-rate penalty or a resolution failure at these operating points — this
      task's original question is answered. (A genuine defect was found and fixed in the QA
      harness's own scoring during this run — not in this feature's shipped mechanism — see the
      rr-study change's own tasks.md §5.3 for detail.) See
      `openspec/changes/rr-study-hashed-callsign-effectiveness/tasks.md` §5 for the full record.

## 5. Build & regression

- [x] 5.1 Rebuild `libft8.dll` from the updated shim per `BUILD.md`.
      → Rebuilt via native/ft8_lib_build/rebuild_shim.bat (MSVC 19.44.35223); copied to
      src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll; win-x64/libft8.version.txt updated.
- [x] 5.2 Run the full `OpenWSFZ.Ft8.Tests` suite against the rebuilt native binary.
      → `dotnet test`: 198/198 passed (0 failed), ~53 s total. Includes the 4 new
      f-001-hashed-callsign-resolution tests and all pre-existing suites (D-005, D-006/AV,
      D-009, R&R fixture gate, etc.) unmodified and green.
- [x] 5.3 Run the existing R&R study synthetic corpus (S1–S8 baseline) to confirm no regression in
      overall decode/false-positive rates versus the current baseline reference run.
      → **Completed 2026-07-04** — full live run against WSJT-X 2.7.0 over VB-CABLE, daemon
      freshly rebuilt and hash-verified against the committed shim `20260031` binary before the
      run. `results/2026-07-04-793a298/report.md` (Sections 1/5 QA-authored per HK-001;
      `report.html` rendered). All null hypotheses retained: S1/S2/S3 GR&R, ndc, and SNR bias
      unchanged from `815b652` within tolerance; S7/S8 informational recovery consistent with
      the most recent prior measurement (`f11f438`, 2026-06-22) — the open D-001 co-channel gap
      is unchanged, not a new regression. **Overall verdict: PASS.** The S5 false-positive metric
      initially showed as a FAIL, but Captain's review correctly identified this as a harness
      defect, not a decoder regression: this scenario's N=12 default cannot mathematically clear
      the same-day-tightened R&R-004 Clopper-Pearson gate even at zero observed events (crossover
      at N=49). Fixed at the source in `harness/analyse.py` (`MIN_N_FOR_FP_GATE`, `_verdict_fp`
      now reports `INFO` — excluded from the gate table and overall verdict — rather than a
      FAIL no outcome at that N could have avoided; 6 new regression tests,
      `tests/test_analyse_xplat.py::TestFpGateUnderpoweredIsInfoNotFail`, 163/163 harness tests
      pass). Also fixed at the root: `scenarios/s5-noise.json`'s routine trial count was raised
      from 3 to 30 (12 → 120 total slots, R&R-006 / GitHub #39), matching the N=120 STUDY-SPEC
      §10's own ratification text already assumed, so future routine runs can produce a real
      gated S5 verdict instead of always reading `INFO`. The ratified §10 verdict for this
      metric remains the adequately powered N=300 run
      (`results/2026-07-04-a3738fc-f002-s5-n300/`, PASS). Per 4.2, none of S1–S8's scenarios
      exercise nonstandard/hashed callsigns, and this run confirms zero measurable effect from
      the persistent hash table, as predicted. No regression found;
      no further diagnostic action required before archiving this change.

## 6. Optional / stretch — Gap B: AP-assist for nonstandard callsigns (not required for merge)

- [ ] 6.1 (Stretch, defer if out of appetite) Extend `Ft8CallsignPacker` (C#) to pack special
      tokens (`CQ`/`DE`/`QRZ`, "CQ nnn", "CQ ABCD") and nonstandard/hashed callsigns
      (`NTOKENS ≤ n28 < NTOKENS + MAX22` range, via the same `ihashcall` algorithm described in
      design.md) so `Pack28` no longer returns `[]` for these cases.
      → DEFERRED (by user decision) to a follow-up change. Not started.
- [ ] 6.2 (Stretch) Wire the extended packer into `QsoAnswererService.cs` /
      `QsoCallerService.cs`'s AP-constraint construction so AP decode-assist remains active when
      either party's callsign is nonstandard.
      → DEFERRED (by user decision) to a follow-up change. Not started; depends on 6.1.
- [ ] 6.3 (Stretch) Add tests confirming AP-assisted decode succeeds for a nonstandard-callsign
      QSO exchange once both 1.x (persistent table) and 6.1/6.2 are in place.
      → DEFERRED (by user decision) to a follow-up change. Not started; depends on 6.1/6.2.
- [x] 6.4 If Gap B is deferred, note it explicitly as a follow-up in the change's closing notes /
      archive summary so it isn't lost.
      → Noted here and carried into the archive summary: Gap B (AP-assisted decode for
      nonstandard/compound callsigns) remains open. The core guarantee this change ships —
      cross-cycle hash resolution via the persistent native table — is a prerequisite for Gap B
      (hinting a hash the decoder couldn't look up before would have bought nothing), and is now
      in place. **Update 2026-07-05**: Gap B has been drafted as its own follow-up change,
      `f-003-ap-assist-nonstandard-callsigns` (proposal/design/specs/tasks all complete,
      `openspec validate --strict` passes) — see that change for scope and status.
