# Developer Briefing — p5-ft8-decoder

**Date:** 2026-05-22
**Issued by:** QA (Round 4)
**Branch:** `feat/p5-ft8-decoder`
**Build:** ❌ CI failing — Gate G3 (Ubuntu)
**Test suite (local):** ✅ 119 passed, 1 skipped, 0 failed

---

## What needs to happen before merge

Three items are blocking. One is a four-line annotation change (under five
minutes). One is a one-file bug fix. One requires obtaining a 15-second audio
clip. A fourth item is a new functional requirement that must land in this
phase. A minor code-quality concern rounds out the list.

Work in this order — cheapest fix first.

---

## 1 — CI Gate G3 failing: add traceability markers (30 minutes)

**Files:** `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs`,
`tests/OpenWSFZ.Web.Tests/WebSocketTests.cs`

**What broke:** Task 13.1 removed `FR-001` and `FR-009` from
`traceability-debt.md` by commenting them out. The TraceabilityCheck tool
now expects both IDs to appear in at least one non-skipped test
`DisplayName`. Neither does. Gate G3 exits 1 on all three OS legs.

**The fix — four `DisplayName` edits:**

In `Ft8DecoderFixtureTests.cs`, update the three `[Fact]` attributes:

```csharp
// Line 15 — add DisplayName alongside the existing Skip
[Fact(Skip = "WAV fixture not yet committed — see task 8.1",
      DisplayName = "FR-001: Ft8Decoder returns DecodeResult records from a known-good WAV fixture")]

// Line 56 — add DisplayName (this is the live anchor for FR-001 until the fixture lands)
[Fact(DisplayName = "FR-001: Ft8Decoder returns empty list for all-silent PCM input")]

// Line 68 — add DisplayName
[Fact(DisplayName = "FR-001: Ft8Decoder respects CancellationToken and throws OperationCanceledException")]
```

In `WebSocketTests.cs`, replace the `DisplayName` on line 88:

```csharp
[Fact(DisplayName = "FR-009: connected WebSocket client receives decode event after BroadcastDecodes")]
```

Note: the skipped WAV fixture test does not satisfy the gate on its own
(the tool counts only non-skipped tests). `DecodeAsync_SilentPcm_ReturnsEmptyList`
is the live anchor. Add the marker to the skipped test anyway — it will become
the primary evidence once the fixture lands.

**Verify:** `dotnet test -c Release` — 119 passed, 1 skipped, 0 failed,
then push and confirm CI goes green on G3.

---

## 2 — Device change kills the decode pump permanently (B5)

**File:** `src/OpenWSFZ.Ft8/CycleFramer.cs` — the `finally` block in `RunAsync`

**Confirmed defect.** When the operator changes the audio device via the
Settings page, the daemon calls `StopFramerAsync()`, which cancels the
framer CTS. The framer's `finally` block unconditionally calls
`output.TryComplete()`. This permanently completes the `framerOutput`
channel. The decode pump's `ReadAllAsync` loop exits and the pump Task
dies. When `StartPipeline` is called for the new device it creates a new
`CycleFramer` that writes to the same completed channel — every write
returns `false` silently. No decode events are broadcast again until the
application is restarted.

**Root cause in one line:**
```csharp
// CycleFramer.cs, finally block — called on BOTH natural end AND cancellation
output.TryComplete(); // ← wrong: completing a channel is irreversible
```

**The fix — distinguish cancellation from natural completion:**

```csharp
public async Task RunAsync(ChannelWriter<float[]> output, CancellationToken ct)
{
    try
    {
        int leadingSilence = ComputeLeadingSamples(_clock.UtcNow);
        var window         = new float[SamplesPerCycle];
        int filled         = leadingSilence;

        await foreach (var chunk in _source.ReadAllAsync(ct))
        {
            // ... accumulation logic unchanged ...
        }

        // Source channel ended naturally (e.g. CaptureManager disposed on shutdown).
        // Signal downstream that no more windows will arrive.
        output.TryComplete();
    }
    catch (OperationCanceledException) when (ct.IsCancellationRequested)
    {
        // Cancelled for a device restart — do NOT complete the output channel.
        // Program.cs owns the channel lifetime and calls TryComplete() on
        // ApplicationStopping. The decode pump must survive the restart.
    }
}
```

`Program.cs` already calls `framerOutput.Writer.TryComplete()` in
`ApplicationStopping` — that path remains correct and unchanged.

**Test to add** (`CycleFramerTests.cs`):

```csharp
[Fact(DisplayName = "FR-017: CycleFramer cancellation does not complete the output channel")]
public async Task RunAsync_Cancelled_DoesNotCompleteOutputChannel()
{
    var clock  = new FakeClock(new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc));
    var source = Channel.CreateUnbounded<float[]>();
    var output = Channel.CreateUnbounded<float[]>();
    var framer = new CycleFramer(source.Reader, clock);

    using var cts = new CancellationTokenSource();
    var runTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

    cts.Cancel();
    await runTask;

    // Output channel must still be writable — the pump should survive a restart.
    output.Writer.TryWrite(new float[180_000]).Should().BeTrue(
        "cancelling the framer for a device restart must not complete the output channel");
}
```

Assign `DisplayName = "FR-017: ..."` — this test traces the new requirement.

---

## 3 — Obtain a WAV fixture and enable the end-to-end test (B6)

**Files:** `tests/OpenWSFZ.Ft8.Tests/Fixtures/` (new files),
`tests/OpenWSFZ.Ft8.Tests/OpenWSFZ.Ft8.Tests.csproj`, and
`Ft8DecoderFixtureTests.cs` (un-skip)

**Why this is a blocker:** Every bug found across four review rounds — the
2000-sample window (B3), the wrong `InfoBits` (B2), the wrong CRC algorithm
(B4) — survived the unit-test suite undetected because all tests use
internally-generated synthetic data. Without a real FT8 signal, there is
no experiment that distinguishes "decoder works" from "decoder is
self-consistently wrong". The user is already observing empty decode
payloads; the cause is unknown without this test.

**What to do:**

**Step 1 — capture the fixture.** Open WSJT-X (or any SDR software) on 14.074 MHz
USB during an FT8 session (every 15 seconds on even UTC boundaries). Route the
audio output to a recorder (Audacity, Sox, or the OS loopback device).
Record a single 15-second clip that contains at least one clean decode in WSJT-X.
Export as raw 32-bit float LE, mono, 12 000 Hz, exactly 180 000 samples
(= 720 000 bytes). Name it `ft8-sample.raw`.

Alternatively, generate a synthetic fixture using the FT8 encoder in `codec2`
or `kvasd` — either approach is acceptable. The raw PCM format is simpler than
WAV (no header parsing required; the test already uses `.raw`).

**Step 2 — commit the reference file.** Create `ft8-sample.ref` alongside
`ft8-sample.raw`. Each line is one expected decoded message string, e.g.:

```
Q1AW Q1TTT EN43
Q1TTT Q1AW -12
```

**Step 3 — add both as EmbeddedResource** in `OpenWSFZ.Ft8.Tests.csproj`:

```xml
<ItemGroup>
  <EmbeddedResource Include="Fixtures\ft8-sample.raw" />
  <EmbeddedResource Include="Fixtures\ft8-sample.ref" />
</ItemGroup>
```

**Step 4 — un-skip the test.** In `Ft8DecoderFixtureTests.cs`, replace
`[Fact(Skip = "...", DisplayName = "FR-001: ...")]` with
`[Fact(DisplayName = "FR-001: ...")]`.

**Step 5 — run.** `dotnet test -c Release`. The fixture test must pass.
If it does not, the decoder has a defect that must be diagnosed before merge.
Do not merge with this test skipped.

---

## 4 — New requirement: FR-017 — Decode start/stop control

**REQUIREMENTS.md** has been updated (v1.2, 2026-05-22) to add FR-017.
This requirement must be implemented in this phase.

### What FR-017 requires

- A button or toggle on the **main UI page** (not Settings) labelled
  clearly as Start / Stop (or equivalent).
- When **stopped**: `captureManager.StopAsync()` is called and the framer
  CTS is cancelled. Audio capture ceases. No decode events are broadcast.
- When **started**: `captureManager.StartAsync(deviceName)` and the framer
  are restarted (same as the existing device-change path). A configured
  device must be present; if none is configured the control should indicate
  this rather than silently failing.
- The current state **must be reflected in the status area** of the main UI
  (e.g. a "Decoding" / "Stopped" badge alongside the existing device name).
- The **decode state must persist** to the configuration file
  (`AppConfig.DecodingEnabled : bool`). A session that was explicitly stopped
  must not auto-resume on the next launch.

### Suggested implementation path

**`src/OpenWSFZ.Abstractions/` or `src/OpenWSFZ.Config/`:**
Add `bool DecodingEnabled { get; init; } = true;` to `AppConfig`.
Default `true` so existing configurations that pre-date this field
auto-start on launch (backward-compatible deserialization).

**`src/OpenWSFZ.Daemon/Program.cs`:**
- In `ApplicationStarted`, check `configStore.Current.DecodingEnabled`
  before calling `StartPipeline`.
- In `configStore.OnSaved`, handle the case where only `DecodingEnabled`
  changed (device name unchanged) — start or stop accordingly.

**`src/OpenWSFZ.Web/DaemonStatus.cs`:**
Add `bool DecodingEnabled` to the `DaemonStatus` record so the status
WebSocket event carries the current decode state. The client uses this to
set the initial toggle state on page load.

**`web/js/main.js`:**
- Add a Start/Stop button element to `index.html` (or create it in JS).
- On `status` event, set the button state from `event.payload.decodingEnabled`.
- On button click, POST to `/api/v1/config` with the toggled `decodingEnabled`
  value and the existing device name — the existing config-save path handles
  the rest.

**`web/` — status badge:**
Display "● Decoding" (green) / "■ Stopped" (grey) in the status bar,
driven by the `status` event and updated after each config save response.

### Tests to add

| Test | Traces |
|---|---|
| `CycleFramer_Cancelled_DoesNotCompleteOutputChannel` | FR-017 |
| `Program_DecodingEnabled_False_DoesNotStartPipeline` (integration) | FR-017 |
| `Program_ToggleDecodingEnabled_StartsAndStopsPipeline` (integration) | FR-017 |
| `WebSocket_StatusEvent_ReflectsDecodingEnabledState` | FR-017 |

The integration tests may live in `OpenWSFZ.E2E.Tests` if the existing
`RealServerFixture` pattern can be extended, or as new tests in
`OpenWSFZ.Web.Tests` using the in-process `WebApplicationFactory`.

---

## 5 — Code quality concern (non-blocking, S5)

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, `ComputeLlrs` method

The inner `freqShift` loop in `CostasSynchroniser` (0–7) is redundant: the
outer frequency sweep in `Ft8Decoder` already steps by one tone spacing,
covering every possible alignment. For `freqShift > 0`, the `(tone + freqShift) % 8`
modulo in `ComputeLlrs` wraps high-bin energies to low-bin indices,
producing incorrect LLRs. These candidates fail CRC (correctly), but they
waste CPU on every decode cycle.

The correct signals are always found at `freqShift = 0`. Removing the inner
loop from `CostasSynchroniser.FindCandidates` (or clamping to `freqShift = 0`
in `Ft8Decoder`) would halve the wasted work and remove the confusing modulo
arithmetic. Address this after B5/B6/FR-017 are done.

---

## Summary checklist

| # | Item | Effort | Status |
|---|---|---|---|
| 1 | Add `FR-001`/`FR-009` `DisplayName` markers to 4 tests | ~15 min | ❌ |
| 2 | Fix `CycleFramer.RunAsync` — don't `TryComplete` on cancellation | ~30 min | ❌ |
| 3 | Add FR-017 test for the fix above | ~15 min | ❌ |
| 4 | Obtain WAV fixture, commit, un-skip end-to-end test | ~2–4 hrs | ❌ |
| 5 | Implement FR-017 (start/stop control, config persistence, UI) | ~1 day | ❌ |
| 6 | Open draft PR to `main` (task 13.5) | ~5 min | ❌ |
| 7 | S5 — remove redundant `freqShift` inner loop | ~30 min | deferred |

Items 1–6 are required before merge. Item 7 is recommended but not blocking.
