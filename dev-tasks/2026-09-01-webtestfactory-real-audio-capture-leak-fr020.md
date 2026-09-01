# Developer handoff: `WebTestFactory`-hosted tests silently start REAL audio capture — `FR-020` flake

**Authored by:** QA, 2026-09-01 (17:40 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Status:** 🔴 Diagnosis + fix OPTIONS, not a single approved fix (HK-011) — §5 below needs a Captain
decision between two shapes before a Developer session implements either. No `src/` or `tests/` edit
made or authorised by this document.
**Branch:** create a fresh short branch off `main` once the Captain has picked an option — do not ride
this on `fix/fr064-heartbeat-race` or the sibling `BroadcastSpectrum` dev-task's eventual branch; this
is a third, independent defect.
**Discovered:** incidentally, alongside the `BroadcastSpectrum` finding, during the same
`pre_merge_check.py` WSL-gate investigation on `fix/fr064-heartbeat-race`.

---

## 0. Why this is not the same shape as the other two findings today

FR-064 and the `BroadcastSpectrum` bug are both bounded, mechanical fixes. This one is not: the root
cause is that `WebTestFactory`-hosted tests touch **real audio hardware** as a side effect of test
startup, and the two candidate fixes differ in whether they touch `src/` at all. This needs a decision,
not just an implementation.

## 1. The failing test

`tests/OpenWSFZ.Web.Tests/StatusAndBindingTests.cs:122-136`,
`GetStatus_IncludesAudioActiveField` ("FR-020"):

```csharp
audioActiveProp.ValueKind.Should().Be(JsonValueKind.False,
    "no audio capture is running in tests so audioActive must be false");
```

Observed failure, reproduced twice independently under WSL Debian full-suite parallel load (both on
`fix/fr064-heartbeat-race`@`2c1a71e` and, separately, on unmodified `main`@`75ea2c1`):

```
Expected audioActiveProp.ValueKind to be JsonValueKind.False {value: 6} because no audio capture is
running in tests so audioActive must be false, but found JsonValueKind.True {value: 5}.
```

Did not reproduce in a native-Windows `dotnet test` run of the same commit (see §4 for why that is
consistent with this cause, not evidence against it).

## 2. Root cause — traced end to end, confirmed against this machine's actual state

**`AudioActivityMonitor.IsActive` only ever becomes `true` from a real captured sample.**
`AudioActivityMonitor` (`src/OpenWSFZ.Web/AudioActivityMonitor.cs`) is a plain per-instance object —
`volatile bool _active`, no static state (`:26`) — set via `ObserveSamples` when any sample exceeds
`1×10⁻⁶` (`:24`, `:38`). Its only caller is `Program.cs:232`,
`audioMonitor.ObserveSamples(chunk)`, wired into `captureManager.ChunkReceived` (`Program.cs:230-235`)
— i.e. it only fires when the capture pipeline is actually running and actually receiving chunks.

**The capture pipeline auto-starts based on the REAL, file-backed config — even under
`WebApplicationFactory<Program>`.** `Program.cs:39`:

```csharp
var configStore = new JsonConfigStore(configPath);
```

`configStore` is a raw local variable, not resolved through the ASP.NET Core DI container. Later,
`Program.cs:733-735`:

```csharp
var deviceName = configStore.Current.AudioDeviceId;
if (deviceName is not null && configStore.Current.DecodingEnabled)
    StartPipeline(deviceName);
```

This decision reads directly from that same local `configStore` — the real `JsonConfigStore` pointed
at `ConfigPathResolver.PlatformDefault()` (`%APPDATA%\OpenWSFZ\config.json` on Windows,
`~/.config/OpenWSFZ/config.json` on Linux/WSL) — **before** `WebTestFactory.ConfigureWebHost`'s DI
substitution (`services.RemoveAll<IConfigStore>(); services.AddSingleton<IConfigStore>(new
TestConfigStore());`) has any chance to affect it. That DI swap only changes what request-handling
code resolves through the container; it cannot retroactively change a value a top-level script
statement already read directly from its own local variable.

`WebTestFactory`'s own doc comment (`tests/OpenWSFZ.Web.Tests/WebTestFactory.cs:31-44`) explicitly
lists why `IConfigStore`, `IFrequencyStore`, `IPropModeStore`, `ICatController`, `IAdifLogWriter`, and
`IAuthPolicy` are all given in-memory test doubles — "so that tests never touch \[real state\],
regardless of which HTTP endpoints are exercised." **Audio capture was never given the same
treatment.** There is no override, and structurally the existing DI-substitution mechanism cannot
reach this particular decision, because it is made before the container is consulted.

**Confirmed, not inferred, against this machine's actual WSL config:**

```
$ cat /home/frank/.config/OpenWSFZ/config.json | jq '{audioDeviceId, decodingEnabled}'
{"audioDeviceId": "pulse", "decodingEnabled": true}
```

This is this developer's normal, live working configuration — a perfectly ordinary state for anyone
who actually uses the app day to day. With it set this way, **every `WebTestFactory`-hosted test class
under WSL starts a real `ArecordAudioSource` capture against the WSL `pulse` ALSA device** as an
unavoidable side effect of booting `Program.cs`. `AudioActivityMonitor`'s threshold (`1×10⁻⁶` — in
practice, any nonzero sample) means faint real capture noise trips `IsActive = true` well within a
test's lifetime, especially under full-suite parallel load where more wall-clock time and more
concurrent test-host instances all contend for the same device.

## 3. Ruled out

- **Not a timeout/async-primitive defect.** No `Task.Delay`, no fixed sleep, no poll is involved in
  this failure at all — the assertion runs a single synchronous HTTP GET immediately after host
  startup. The nondeterminism is entirely about whether real hardware happened to deliver a sample by
  that point, not about how the test waits for anything.
- **Not specific to `FR-020`'s own file.** `AudioActivityMonitor` is read by at least three other call
  sites (`WebApp.cs:307`, `:734`, `:754`) that also report `AudioActive` in HTTP/heartbeat responses —
  any of them could show the same nondeterminism in a differently-worded assertion; this is a property
  of the shared root cause, not a defect local to one test.

## 4. Why this explains the platform-specific reproduction pattern

This machine's native-Windows `%APPDATA%\OpenWSFZ\config.json` evidently does not currently have both
`AudioDeviceId` set and `DecodingEnabled: true` in a way that trips the WASAPI path within a test's
short window (or the real input device on this box is quiet enough not to exceed the threshold in
time) — so the native-Windows `dotnet test` run passed clean. The WSL run failed because its own,
separate config file (a different path entirely, per `ConfigPathResolver`) happens to have
`decodingEnabled: true`. **This is exactly the flake signature of a test whose outcome depends on
whatever real, operator-specific state happens to be sitting on the machine that runs it** — not
something CI or a differently-configured developer machine would necessarily ever reproduce, and not
something a differently-configured machine could rely on NOT reproducing either.

## 5. Fix — two shapes, needs a Captain decision before implementation

### Option (a) — give the capture-pipeline decision a DI seam

Change `Program.cs:733-735` (and the two other `StartPipeline` call sites at `:917-925` and
`:1080-1088`) to resolve `IConfigStore` through `app.Services` (post-`Build()`) rather than the raw
pre-DI local variable, so `WebTestFactory`'s existing `IConfigStore` substitution actually takes effect
before the auto-start decision runs.

- Touches `src/OpenWSFZ.Daemon/Program.cs` — real production wiring, not test-only.
- Fixes the gap at its structural source: makes `WebTestFactory`'s existing "tests never touch real
  state" guarantee actually true for audio capture, the way it already is for config/frequencies/prop
  modes/CAT/ADIF/auth.
- Needs care: `configStore` is used directly (not through DI) in many other places in `Program.cs`
  before `app.Build()` — this option only changes the **audio auto-start decision**, not the rest of
  Program.cs's config usage. Do not attempt a wholesale refactor of `configStore` usage under this
  dev-task; scope is exactly the `StartPipeline` gating decision.

### Option (b) — isolate the config file path for the test host, test-only

`ConfigPathResolver.Resolve` (`src/OpenWSFZ.Config/ConfigPathResolver.cs:29-39`) already honors an
`OPENWSFZ_CONFIG` environment variable ahead of the platform default. Have `WebTestFactory` (or a
shared test-collection fixture) set `OPENWSFZ_CONFIG` to an isolated, empty temp-directory path before
`WebApplicationFactory<Program>` boots `Program.cs`, so `JsonConfigStore` never reads the operator's
real file at all.

- Test-only — `git diff main --stat` would touch only `tests/`, keeping the diff disjoint from any
  `src/` diff, matching the preference already stated in the FR-064 brief for this class of choice.
- Does not fix the underlying architectural gap: any *other* code path that similarly reads
  `configStore` directly before DI substitution takes effect would still be exposed to real operator
  state in a differently-shaped test. This fix removes today's specific exposure (a real config file)
  but not the general pattern (DI substitution racing against pre-`Build()` local-variable reads).
- Lower risk, smaller diff, faster to land.

**Do not choose between these unilaterally.** Option (a) is the more complete fix but is a genuine
production-code change with a wider blast radius to review; option (b) is safe and fast but leaves the
general pattern in place for the next person who hits it a different way. This is the Captain's call,
same footing as FR-064's own option (a)/(b) choice was the Captain's call via the R1 ruling.

## 6. Ruled out as a third option

- **Do not just weaken the assertion** (e.g. only check the field is present and boolean-typed,
  dropping the `Should().Be(JsonValueKind.False, ...)` check). That silently abandons what FR-020
  actually specifies — "no audio capture is running in tests" is a real, intended guarantee, not
  incidental to the assertion. Weakening the test hides the isolation gap instead of closing it.

## 7. Definition of done (once the Captain has picked (a) or (b))

- [ ] Chosen option implemented, scoped exactly as described in §5 for that option — no drive-by
      changes to unrelated `configStore` usage
- [ ] `FR-020` (`GetStatus_IncludesAudioActiveField`) passes under WSL Debian full-suite load, run at
      least twice consecutively (this flake only reproduced under full-suite parallel load — an
      isolated single-test run is not sufficient evidence either way)
- [ ] `dotnet test OpenWSFZ.slnx -c Release` — full suite, green, under both native Windows and WSL
      Debian
- [ ] If option (a): confirm no other `Program.cs` startup decision that should also read through DI
      was accidentally left on the old path, and no other test in the solution was relying on the old
      (buggy) behaviour
- [ ] If option (b): confirm the isolated `OPENWSFZ_CONFIG` temp path is cleaned up appropriately
      (no leaked temp directories across test runs) and does not collide across parallel test
      collections
- [ ] `git diff main --stat` matches the chosen option's expected file set (§5)
- [ ] NFR-021 scan run after commit — clean
- [ ] Commit message states the structural argument (tests were reading the operator's real config
      file/starting real capture hardware, not "flaky assertion"), not "N green runs ⇒ fixed"

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No `pre_merge_check.py`
(HK-006 — Captain's initiative only).
