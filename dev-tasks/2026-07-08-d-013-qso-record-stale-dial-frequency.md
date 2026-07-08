# Developer Handoff — D-013: QSO ADIF records log a stale/wrong dial frequency (and BAND) whenever CAT is connected

**Date:** 2026-07-08
**Prepared by:** QA Engineer
**Defect ID:** D-013 (High — data-integrity defect in shipped behaviour, found during
qso-confirmation filtering-feature exploration; GitHub issue [#62](https://github.com/frank001/OpenWSFZ/issues/62))

---

## 1. Context

While exploring an ADIF-filtering feature with the Captain (which would need `BAND` to be
trustworthy for a proposed band-scoped "worked before" check), we checked whether `BAND` is
actually written correctly to `ADIF.log` by this application's own QSO-completion path — as
opposed to the Captain's real personal log, which is a genuine WSJT-X export and tells us
nothing about this app's own write correctness.

**It is not written correctly whenever CAT control is connected — which is the normal,
intended operating mode.**

This codebase already has one correct, established rule for resolving the operator's actual
dial frequency, used by the decode pump on every single cycle:

```csharp
// src/OpenWSFZ.Web/WebApp.cs — ResolveEffectiveFrequency (FR-039)
//   1. Live in-session CAT value   (ICatState.DialFrequencyMHz)
//   2. Persisted last-known CAT    (CatConfig.LastPolledFrequencyMHz, only if cat.enabled)
//   3. Operator's manual fallback  (DecodeLogConfig.DialFrequencyMHz)
public static double ResolveEffectiveFrequency(ICatState? catState, AppConfig config)
{
    if (catState?.DialFrequencyMHz is { } live) return live;
    var cat = config.Cat;
    if (cat is { Enabled: true, LastPolledFrequencyMHz: { } persisted }) return persisted;
    return config.DecodeLog?.DialFrequencyMHz ?? 0.0;
}
```

`Program.cs`'s decode pump calls this correctly every cycle (line ~507) and uses the result
for `ALL.TXT` (line ~525). But **`QsoAnswererService` and `QsoCallerService` never received
this value or `ICatState` at all.** Each independently builds its completed-QSO `QsoRecord`
by reading tier 3 directly, unconditionally, skipping tiers 1 and 2 entirely:

```csharp
// src/OpenWSFZ.Daemon/QsoAnswererService.cs:954 (inside ExecuteTx73Async)
DialFrequencyMHz = _configStore.Current.DecodeLog.DialFrequencyMHz,

// src/OpenWSFZ.Daemon/QsoCallerService.cs:729 (inside ExecuteTxRr73Async)
DialFrequencyMHz = _configStore.Current.DecodeLog.DialFrequencyMHz,
```

`DecodeLogConfig.DialFrequencyMHz` (tier 3) is a **manual fallback**, only ever written by
`POST /api/v1/tune` when CAT is *inactive* (`WebApp.cs` ~845–850, "CAT inactive path: update
the manual dial frequency config"). When CAT is connected — the case that matters, since an
operator relying on manual tune entry is the exception, not the rule — this field is never
touched again for the life of the process. It sits frozen at whatever it last was, quite
possibly `0.0` if manual tune has never been used at all.

**Consequence:** every QSO this application's own automation completes, while CAT is
connected, logs `BAND`/`FREQ` in `ADIF.log` from a stale or absent value instead of the rig's
actual frequency at QSO time:
- Config frozen at an earlier band → **wrong** `BAND` tag (a QSO actually worked on 20m gets
  logged as whatever band was last manually tuned).
- Config still `0.0` → `AdifLogWriter.BuildAdifRecord`'s `if (record.DialFrequencyMHz != 0.0)`
  guard (line 155) skips `FREQ`/`BAND` **entirely**.

**One root cause, not three symptom sites.** `record` (built once, at QSO completion, in each
service) feeds *both* downstream paths:
- `tx.QsoConfirmation == true` (the default): `_txEventBus.PublishQsoReview(record, ...)` sends
  the same wrong value to the browser's confirmation dialog; the browser echoes it back
  unedited via `POST /api/v1/tx/log-qso`, landing in `WebApp.cs:1370`'s
  `DialFrequencyMHz = req.FreqMHz`. **That site is not independently buggy — it is a faithful
  echo of the value `record` was already wrong about.** No change needed there; fixing the two
  construction sites below fixes this path automatically.
- `tx.QsoConfirmation == false`: `_adifLog.AppendQsoAsync(record)` writes the same wrong
  `record` directly.

This is a distinct defect from D-010 (`dev-tasks/2026-07-05-d-010-decodelog-null-config-post.md`),
which fixed `DecodeLog` becoming `null` and explicitly flagged these same two line numbers as
"out of scope... benefit transitively" from the null-safety fix. D-010 made `DecodeLog`
non-null; it did nothing about which *tier* of frequency resolution these two call sites read
from. That is this defect.

---

## 2. Branch

Create a new branch: **`fix/d-013-qso-record-stale-dial-frequency`**
Do not commit directly to `main`.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Daemon/QsoAnswererService.cs`

**Add an `ICatState?` field and thread it through both constructors**, alongside the existing
`_decoder` field (near the other `private readonly` fields, ~line 40–51):

```csharp
private readonly ICatState? _catState;
```

Primary constructor (~line 140–159) — add `catState` as a new optional trailing parameter
(after the existing `decoder = null`, so no existing positional-arg caller breaks):

```csharp
public QsoAnswererService(
    ChannelReader<DecodeBatch>   decodeChannel,
    IConfigStore                 configStore,
    IPttController               pttController,
    ITxEventBus                  txEventBus,
    IAdifLogWriter               adifLog,
    AudioOffsetEventBus          audioOffsetEventBus,
    ILogger<QsoAnswererService>  logger,
    IApConstraintSink?           decoder = null,
    ICatState?                   catState = null)
{
    // ... existing assignments unchanged ...
    _decoder  = decoder;
    _catState = catState;
    _timeProvider = TimeProvider.System;
}
```

The `internal` test constructor (~line 166–180) needs no change — it already forwards to the
primary constructor without specifying `decoder`/`catState`, so both continue to default to
`null`, which is the previous (pre-fix) behaviour: `ResolveEffectiveFrequency(null, config)`
falls through to tiers 2/3 exactly as today, so existing tests are unaffected unless they
specifically opt in to the new behaviour (see §4).

**Fix the actual read**, in `ExecuteTx73Async` (~line 954):

```csharp
// Before:
DialFrequencyMHz = _configStore.Current.DecodeLog.DialFrequencyMHz,

// After:
DialFrequencyMHz = OpenWSFZ.Web.WebApp.ResolveEffectiveFrequency(_catState, _configStore.Current),
```

(`using OpenWSFZ.Web;` is already present at the top of this file — the fully-qualified form
above is just for clarity in this handoff; use the unqualified `WebApp.ResolveEffectiveFrequency`
call in the actual edit.)

### 3.2 — `src/OpenWSFZ.Daemon/QsoCallerService.cs`

Identical pattern. Add `private readonly ICatState? _catState;` near the existing fields
(~line 43–51), add `ICatState? catState = null` as a new trailing optional parameter on the
primary constructor (~line 120–145, after the existing `decoder = null`), assign it, and leave
the `internal` test constructor (~line 145–158) unchanged (same "forwards without specifying,
defaults null" reasoning as 3.1).

Fix the read in `ExecuteTxRr73Async` (~line 729):

```csharp
// Before:
DialFrequencyMHz = _configStore.Current.DecodeLog.DialFrequencyMHz,

// After:
DialFrequencyMHz = WebApp.ResolveEffectiveFrequency(_catState, _configStore.Current),
```

### 3.3 — `src/OpenWSFZ.Daemon/Program.cs` — DI wiring

Both services are constructed via factory lambdas (~line 430–457), not plain constructor
injection, so the new parameter must be passed explicitly. `ICatState` is already registered
as a singleton (`services.AddSingleton<ICatState>(catState)`, ~line 392) — add it to both
factory calls as the new final argument:

```csharp
services.AddSingleton<QsoAnswererService>(sp => {
    var svc = new QsoAnswererService(
        qsoAnswererChannel.Reader,
        sp.GetRequiredService<IConfigStore>(),
        sp.GetRequiredService<IPttController>(),
        sp.GetRequiredService<ITxEventBus>(),
        sp.GetRequiredService<AdifLogWriter>(),
        sp.GetRequiredService<AudioOffsetEventBus>(),
        sp.GetRequiredService<ILogger<QsoAnswererService>>(),
        sp.GetService<IApConstraintSink>(),
        sp.GetService<ICatState>());
    svc.IsActive = (txRole == TxRole.Answerer);
    return svc;
});

services.AddSingleton<QsoCallerService>(sp => {
    var svc = new QsoCallerService(
        qsoCallerChannel.Reader,
        sp.GetRequiredService<IConfigStore>(),
        sp.GetRequiredService<IPttController>(),
        sp.GetRequiredService<ITxEventBus>(),
        sp.GetRequiredService<AdifLogWriter>(),
        sp.GetRequiredService<AudioOffsetEventBus>(),
        sp.GetRequiredService<ILogger<QsoCallerService>>(),
        sp.GetService<IApConstraintSink>(),
        sp.GetService<ICatState>());
    svc.IsActive = (txRole == TxRole.Caller);
    return svc;
});
```

### 3.4 — Do not change `AdifLogWriter.cs` or `WebApp.cs`'s `POST /api/v1/tx/log-qso` handler

`AdifLogWriter.BuildAdifRecord` only ever reads whatever `QsoRecord.DialFrequencyMHz` it is
given — it has no independent bug and needs no change. `WebApp.cs:1360–1370`
(`POST /api/v1/tx/log-qso`) is a faithful echo of the browser-confirmed value, which will be
correct once 3.1/3.2 are fixed at the point of emission — flagging only so the reviewer knows
this was considered and deliberately left alone, matching D-010's precedent for the same kind
of note.

---

## 4. Tests

**`tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`** — add a small `ICatState` test
double (mirroring the existing `StubCatState` pattern already used in
`tests/OpenWSFZ.Daemon.Tests/DecodeFrequencyGuardTests.cs` — a minimal `sealed class` with a
constructor-supplied fixed `DialFrequencyMHz` and `Status => CatConnectionStatus.Connected`),
then:

1. **`QsoComplete_LiveCatFrequencyDiffersFromConfig_AdifRecordUsesLiveCatValue`** — configure
   `IConfigStore.Current.DecodeLog.DialFrequencyMHz` to one band (e.g. `7.100` / 40m), supply a
   `StubCatState` reporting a different live frequency (e.g. `14.074` / 20m) via the new
   constructor parameter, drive a QSO to completion with `tx.QsoConfirmation = false` (silent
   auto-log path), and assert `IAdifLogWriter.AppendQsoAsync` was called with a `QsoRecord`
   whose `DialFrequencyMHz` is `14.074`, not `7.100`. This directly reproduces D-013 and proves
   the fix.
2. **`QsoComplete_NoCatState_FallsBackToConfigValue`** — same setup but construct the service
   with `catState: null` (or omit it), and assert the ADIF record still uses the config value —
   proves the fix is purely additive and preserves today's behaviour when CAT genuinely isn't
   available (backward compatibility for the "manual tune, no CAT" operator).
3. **`QsoComplete_QsoConfirmationEnabled_ReviewEventCarriesLiveCatFrequency`** — same live-CAT
   setup as test 1, but with `tx.QsoConfirmation = true`; assert the `qsoReview` WebSocket event
   published via `ITxEventBus.PublishQsoReview` carries the live CAT frequency, not the config
   value — proves the confirmation-dialog path is fixed too (it derives from the same `record`,
   but assert it directly rather than relying on the other test's coverage to imply it).

**`tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`** — add the mirror image of tests 1–3
above for `QsoCallerService`/`ExecuteTxRr73Async`.

Existing tests in both files that construct these services without a `catState` argument
should continue to pass unmodified (default `null` preserves current tier-2/3 behaviour) — run
the full existing suite for both files, not just the new tests, to confirm no regression.

---

## 5. Acceptance Criteria

QA will verify all of the following before approving merge:

- [ ] **AC-1:** With CAT connected and reporting a live frequency that differs from
  `DecodeLog.DialFrequencyMHz`, a QSO completed by `QsoAnswererService` writes (or, when
  confirmation is enabled, proposes via `qsoReview`) a `QsoRecord.DialFrequencyMHz` matching the
  **live CAT value**, not the stale config value.
- [ ] **AC-2:** Same for `QsoCallerService`.
- [ ] **AC-3:** With `catState` unavailable/null (CAT genuinely not wired up), both services
  fall back to existing tier-2/tier-3 behaviour, unchanged from today — no regression for
  manual-tune operators.
- [ ] **AC-4:** `AdifLogWriter`'s `DeriveBand`/`BAND` output is correct end-to-end for a QSO
  completed while CAT is connected (integration-level check, not just the unit-level
  `QsoRecord` assertions above) — e.g. a QSO on 20m produces `<band:3>20m`, not a stale band or
  a missing tag.
- [ ] **AC-5:** All new tests pass; no existing test in `QsoAnswererServiceTests.cs`,
  `QsoCallerServiceTests.cs`, `AdifLogWriterTests.cs`, or `DecodeFrequencyGuardTests.cs`
  regresses.
- [ ] **AC-6:** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings.
- [ ] **AC-7:** `dotnet test OpenWSFZ.slnx -c Release` — full suite green (941+ tests, the
  pre-existing `FR-009` flaky WebSocket test excepted per established practice).

---

## 6. References

- `src/OpenWSFZ.Web/WebApp.cs` — `ResolveEffectiveFrequency` (FR-039), the established
  three-tier rule this fix reuses rather than reinventing.
- `src/OpenWSFZ.Daemon/Program.cs` — decode pump's correct usage of the same rule (~line 507,
  522) as the trusted precedent that this fix's behaviour is safe and consistent with.
- `src/OpenWSFZ.Daemon/AdifLogWriter.cs` — `DeriveBand`, `BuildAdifRecord` (unchanged by this
  fix; downstream consumer of the now-corrected `QsoRecord.DialFrequencyMHz`).
- `dev-tasks/2026-07-05-d-010-decodelog-null-config-post.md` — prior, related-but-distinct
  defect at the same two line numbers (null-safety, not stale-value); this fix builds on top of
  D-010 already having landed (confirm on this branch that `DecodeLog` is guaranteed non-null
  before assuming `_configStore.Current.DecodeLog.DialFrequencyMHz` is safe to read as the
  fallback tier inside `ResolveEffectiveFrequency`).
- Found during: exploration of an ADIF-filtering/worked-before-expansion feature (session
  2026-07-08) — banner-scoped worked-before checks were the motivation for scrutinising `BAND`
  correctness in the first place; this defect blocks that specific piece of that feature (not
  the feature's Country/Continent/CQ-Zone/ITU-Zone parts, which don't depend on band).
