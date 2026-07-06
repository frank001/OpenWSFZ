## 1. Native shim — expose the reject counter (D1)

- [x] 1.1 Confirm the current `FT8_SHIM_VERSION` value in `ft8_shim.c` at implementation time and
      reserve the next sequential version number (do not assume `20260031` is still current —
      confirm against the actual file). Confirmed 20260031; reserved 20260032.
- [x] 1.2 Add `int32_t ft8_get_hash_table_reject_count(void)` (matching the return type
      convention already used by `ft8_get_last_noise_floor_db`) returning
      `g_hash_table_reject_count` directly, with no locking and no side effects.
- [x] 1.3 Update the version-history comment block at the top of `ft8_shim.c` with a new entry
      describing this change, following the existing style. (Also updated the mirror block and
      the `FT8_SHIM_VERSION` define in `ft8_shim.h`, and added the getter declaration there.)

## 2. Managed interop — wire the getter through (D1)

- [x] 2.1 Add the P/Invoke declaration for `ft8_get_hash_table_reject_count` in the managed
      interop layer (`Ft8LibInterop.cs` or equivalent), mirroring the existing
      `ft8_get_last_noise_floor_db` wrapper's shape and error handling. (Also threaded through
      `IFt8NativeInterop`, `Ft8NativeInteropAdapter`, and `Ft8Decoder.GetHashTableRejectCount()`.)
- [x] 2.2 Bump the managed-side `ExpectedShimVersion` constant to match the new shim version
      (F-001's tasks.md §1.5 discovered-item flagged this exact two-file coupling as easy to
      miss — do not skip it). Bumped 20260031 → 20260032.

## 3. Session-end diagnostic logging (D2)

- [x] 3.1 At graceful daemon shutdown, read the reject count via the new getter and write a
      single log line (e.g. `Hash table reject count (session): N`) alongside whatever
      existing end-of-session logging already runs at that point. Added to the
      `ApplicationStopping` hook in `Program.cs`, before `loggingPipeline.Dispose()`.
- [x] 3.2 (Optional / stretch) Expose the reject count on the existing `/api/v1` diagnostics
      surface for live (mid-session) reads, per design.md D2's noted alternative. **Captain
      elected to include it.** Added `HashTableRejectCount` to `DaemonStatus`, surfaced live on
      `GET /api/v1/status` (and the `decode/start`/`decode/stop` responses + initial WS
      `status` event) via a `Func<int>` provider wired from `Program.cs`.

## 4. Tests

- [x] 4.1 Add a unit test confirming the getter returns `0` when no rejection has occurred
      (fresh process state, or an isolated check consistent with the existing suite's handling
      of the process-global table's shared/non-reset nature — see 4.2's note).
      `HashTableRejectCountTests.GetHashTableRejectCount_BeforeAnySaturation_ReturnsZero` —
      placed OUTSIDE the pinned-last saturation collection so it deterministically runs while
      the table is unsaturated (the only test that saturates is pinned strictly last).
- [x] 4.2 Extend the existing
      `HashedCallsignResolutionTests.HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive`
      test to also assert the new getter reports a reject count consistent with the known
      overflow it forces (264 distinct callsigns added against a 256-entry capacity). Account
      for that test's own documented caveat that the table is process-global and shared across
      the test assembly with no reset entry point — read the counter's value before and after
      the test's overflow attempts and assert the *delta*, not an absolute value.
      Delta asserted `>= 8` (264 − 256), robust to prior occupancy.
- [x] 4.3 Add a regression test confirming reading the counter does not alter subsequent hash
      resolution behaviour (read the counter, then confirm a previously-stored callsign is still
      resolvable) — covers the "reading has no side effects" scenario.
      `HashTableRejectCountTests.ReadingRejectCount_HasNoSideEffects_StoredCallsignStillResolves`.
- [x] 4.4 Add or extend a daemon-level test/manual verification step confirming the session-end
      log line in 3.1 actually appears with the correct value on a graceful shutdown following a
      forced-saturation scenario. Extracted the shutdown wiring into `HashTableRejectCountReporter`
      and unit-tested it (`HashTableRejectCountReporterTests`): value interpolation, zero case,
      and the fault-containment (Warning, never propagates) path.

## 5. Build & regression

- [x] 5.1 Rebuild `libft8.dll` from the updated shim per `BUILD.md`. Rebuilt via
      `rebuild_shim.bat` (MSVC 19.44, VS 2022); DLL now exports `ft8_get_hash_table_reject_count`
      and `check_native_version.py` confirms it embeds shim 20260032. Added the new `/EXPORT:`
      to `rebuild_shim.bat` and `BUILD.md`, and refreshed `win-x64/libft8.version.txt`. Linux/
      macOS binaries are left at the prior version deliberately — CI rebuilds them from source
      (the staleness checks are `continue-on-error`) and the `commit-native-binaries` job
      auto-commits them to 20260032.
- [x] 5.2 Run the full `OpenWSFZ.Ft8.Tests` suite against the rebuilt native binary; confirm no
      regression in any existing suite (D-005, D-006/AV, D-009, F-001's own tests, R&R fixture
      gate, etc.). **Ft8: 280 passed / 0 failed** (ABI check accepts 20260032). Also ran the
      touched adjacent suites: **Daemon: 193 passed** (incl. new `HashTableRejectCountReporterTests`),
      **Web: 203 passed** (incl. `DaemonStatus`/`WebApp`/`WebSocketHub` changes).
- [x] 5.3 Confirm no existing R&R study synthetic corpus scenario is affected (this change adds
      no new decode path and changes no resolution behaviour, so none should be) — a full corpus
      re-run is not expected to be required, but note the check explicitly in the PR description
      rather than assuming it. **Confirmed:** observability-only — the sole native change is one
      new read-only exported getter over an existing counter; `ft8_decode_all`, candidate
      search, LDPC/OSD, and hash resolution are byte-for-byte unchanged. No corpus re-run
      required; noted here and to be restated in the PR description.
