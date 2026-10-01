# QA code review — `feat/sub-feas-native-subtraction` (SUB-FEAS native subtraction build)

- **Date (UTC):** 2026-09-29 15:24
- **From / to:** QA → Architect (copy for the Captain)
- **Branch reviewed:** `feat/sub-feas-native-subtraction`, Developer worktree, **local only, not pushed** (HK-033)
- **Commits reviewed:** `1a1244bf` (pass 1, seven commits since `c3f42362`), `91444300` (pass 2, the R1-R3 fix). `0d6b1937` is the Developer's `tasks.md`-only commit recording this review; QA has not re-read it beyond the Developer's own summary.
- **Scope of the review:** code read (native C, C# orchestration, wiring, tests). **Not** a measurement, and **not** the full `/opsx:verify`.

## 1. Verdict

| Pass | Commit | Verdict |
|---|---|---|
| 1 | `1a1244bf` | **RETURNED**, three required changes (R1-R3) |
| 2 | `91444300` | **APPROVED (code only)**, R1-R3 satisfied |

Approval is for the code as it stands with the flag **OFF by default**. It is **not** approval to enable the flag in any live run, and **not** merge sign-off (HK-010, the Captain's call).

## 2. Pass 1 findings and how they were closed

### R1 — residual `DecodeAll` ran on a different thread from pass-0, native state is thread-local
- The residual decode ran inside `SubtractionPass`'s own `Task.Run`. Pass-0 deliberately runs `SetApBits` + `DecodeAll` + `GetLast*` on one thread. `ft8_shim.c` keeps AP bits, SNR terms and H12 state `_Thread_local`.
- Failure scenario: the residual decode saw no AP constraints, or stale ones left on whatever pool thread it landed on. Thread-pool-dependent and nondeterministic; a mock interop with no thread state could not see it.
- **Closed in `91444300`:** `SetApBits(ap)` is now called on the residual decode's own thread immediately before `DecodeAll` and cleared in a `finally`. `Ft8Decoder` passes `_apConstraints`.
- **Part of the original concern withdrawn:** I had suspected the callsign hash table was thread-local. It is not. `ft8_shim.c:787` (`g_session_hash_table`, process-global) and `:1489` (`tls_hash_table` re-pointed at it at the top of every native call) show pass-0 hashes resolve on any thread. Pass-0 and the residual pass run strictly sequentially.

### R2 — native failures outside the per-signal AV path escaped as exceptions and lost pass-0's results
- `SubfeasComputeAnalytic` was called outside any `try`; a per-signal `rc -1` (workspace allocation failure) surfaced as an `AggregateException` matching neither catch; `EncodeMessage` / `ExtractPayload77` in step 5 were unguarded. An exception left `DecodeAsync` after pass-0 had already succeeded, so the cycle was lost, contradicting design.md Decision 4 and tasks §3.2. A comment in `Ft8Decoder.cs` asserted the opposite.
- **Closed in `91444300`:** the whole residual pass is wrapped; any non-cancellation exception is logged and the caller keeps pass-0's results. Caller cancellation still propagates. The wrong comment is corrected. Tests added for compute-analytic AV, per-signal `rc -1`, `EncodeMessage` failure, and cancellation.

### R3 — no runtime guard, cost above budget
- Developer's corrected benchmark: about **26.2 s FFT-only** for a busy 24-signal cycle against the **13 s hard budget**. Nothing bounded wall-clock.
- **Closed in `91444300`, cooperatively only:** deadline = 13 s cycle budget minus pass-0 elapsed, checked between phases and on the fit loop via a linked cancellation token. **An in-flight native call cannot be interrupted.** This does not make the pass fast; **§8.1 (measured runtime, flag on) remains the real gate.**

### Minor
- The duplicated `180_000` is replaced by `Ft8LibInterop.PcmSampleCount`.

## 3. What QA verified, and how

| Item | Evidence |
|---|---|
| Fix diff read | `git diff 1a1244bf 91444300 -- src/`: four files changed (`Ft8Decoder.cs`, `Ft8LibInterop.cs`, `SubtractionPass.cs`, `SubtractionPassTests.cs`); native C and `libft8.dll` unchanged in this commit |
| Test run | Detached scratch worktree at `91444300`, `dotnet test tests/OpenWSFZ.Ft8.Tests --nologo -v q`: **353 passed, 0 failed, 0 skipped**, 1 m 9 s |
| Filter | **None.** The whole `OpenWSFZ.Ft8.Tests` project ran. A filtered-out suite is silent, not green (HK-022); this one was not filtered |
| Binary pin | `libft8.dll` SHA-256 at `91444300` = `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`. Identical to the value the Developer reported. **Not an independent pin**: the only other place that value appears on disk is `libft8.version.txt`, the same file's own label. No separate pre-registered manifest was located |
| Native memory handling | `subfeas_fit.c` read in full: no `static` storage in the fit path, per-call heap workspace, freed on every non-AV path (the AV path deliberately leaks, matching `ft8_decode_all`'s own discipline), write bounds checked (`start + N_TX <= PCM_LEN`) before every access |

## 4. What QA did NOT verify

- The full-solution `dotnet test`, only `OpenWSFZ.Ft8.Tests`.
- The full `/opsx:verify` against the change artifacts.
- **Flag-off byte-identical output**: established by reading the code (`_subtractionEnabled && native.Length > 0` guards the only new path, and a Developer test covers it); not mechanically diffed against a pre-change build.
- Linux and macOS builds (no toolchain on the Developer session either; `build_linux.sh` was edited but never run).
- Any decode-rate or runtime behaviour: nothing in this review measures either.

## 5. Open items before merge

| Item | State |
|---|---|
| 6.3 `AllFitsAgainstOriginalBuffer_NotSequential` dedicated test | open (true by construction) |
| 6.5 `MaxPassesUnaffectedBySubtractionFlag` dedicated test | open (true by construction) |
| 6.6 allocation-failure fallback test | open, needs a native malloc-failure hook |
| 6.7 G6 fixture answer keys | **DEFERRED by the Captain until after §8** |
| 6.8 Linux/macOS builds | open |
| 5.1 web-UI checkbox | open; flag is settable only by config edit or full-replace `POST /api/v1/config` (HK-035) |
| Merge sign-off | **Captain (HK-010)** |
| Push | **Captain's go-ahead required (HK-033)**; nothing pushed |

## 6. Gates that govern enabling the flag (not merging it)

- **§7 stability gate:** sustained multi-hour, multi-cycle stress with the flag on. Not started.
- **§8.1 runtime:** measure decode-cycle runtime with the flag on against the 13 s hard budget. The 26 s FFT-only benchmark says this may fail; it is the number that matters.
- **§8.2 decode-rate acceptance** on a corpus independent of SUB-FEAS's own 40m corpus. Not started.
- **§8.3 Captain decision** after 8.1 and 8.2, pass or fail.

No result in this report bears on decode rate. The SUB-FEAS offline figure (net +8.89 pp, one 40m corpus, one pass) is unchanged and is cited only as the NET figure; it says nothing about the native build's runtime.

## 7. Process notes

- The original Developer session (`dev-a1`) closed before the verdict could be delivered; `dev-53` took over the branch. Pass 1 was delivered to `dev-53` after it confirmed it was the Developer.
- `tasks.md` is QA-authored but lives on the Developer's branch, checked out in the Developer worktree. At the Captain's direction the edits were applied by the Developer as a `tasks.md`-only commit (`0d6b1937`).
- The verification worktree used for the test run was scratch-only and has been removed.
- No privacy-relevant content: no callsigns, message text, or `ALL.TXT` data appear in this report (NFR-021, HK-037).
