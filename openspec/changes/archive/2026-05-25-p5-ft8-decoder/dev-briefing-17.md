# Developer Briefing — p5-ft8-decoder (Round 17)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Eliminate diagnostic log flood; restore ability to investigate zero-audio root cause

---

## Background

The "Resampler output all zeros" warning (line 219 of `WasapiAudioSource.cs`) fires inside
the resampler drain `while` loop on every 2048-sample zero-filled chunk. At 12 kHz that is
roughly one warning every 170 ms — approximately **six per second, continuously** —
completely obscuring every other log entry.

The single most useful piece of diagnostic information, `rawHasData`, is logged separately
at `Information` level and rate-limited to the first five callbacks plus every 100th. The
warning fires six times a second; the relevant diagnostic fires once every ten seconds. The
result is that the log is unreadable and the root cause is invisible.

There are exactly two candidate root causes, and they require entirely different fixes:

| `rawHasData` when zeros occur | Meaning | Where to look |
|---|---|---|
| `false` | WASAPI is delivering silence — the problem is at the device or OS level | Wrong device selected? Session muted? No signal source? OS audio policy? |
| `true` | NAudio pipeline is zeroing good data — the problem is in the C# code | Channel count? Encoding type? Format negotiation? |

Until the flood is stopped and `rawHasData` is surfaced alongside the zero-output warning,
no meaningful analysis is possible.

---

## Tasks

### D1 — Rate-limit and enhance the "Resampler output all zeros" warning

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

**Add a closure counter** alongside the existing `dataAvailableCount` at the top of the
`DataAvailable` handler setup block (around line 113):

```csharp
var dataAvailableFired  = false; // D1 (DIAG)
var dataAvailableCount  = 0;     // L-3 (DIAG)
var zeroOutputCount     = 0;     // D2 (DIAG): counts consecutive zero-output resampler drains
```

**Replace** the current zero-output check (lines 218–224):

```csharp
// Before — fires on every zero-filled chunk (~6×/second):
else if (chunk.All(sample => sample == 0)) {
    _logger?.LogWarning(
        "DIAG Resampler output all zeros on '{DeviceId}' — " +
        "possible format mismatch or silent input.",
        deviceId);
}
```

```csharp
// After — fires on first occurrence and every 100 thereafter;
// includes rawHasData so the operator can immediately identify the branch.
else if (chunk.All(sample => sample == 0))
{
    zeroOutputCount++;
    if (zeroOutputCount == 1 || zeroOutputCount % 100 == 0)
    {
        _logger?.LogWarning(
            "DIAG Resampler output all zeros on '{DeviceId}' " +
            "(run #{Count}, rawHasData={RawHasData}) — {Diagnosis}",
            deviceId,
            zeroOutputCount,
            rawHasData,
            rawHasData
                ? "NAudio pipeline is zeroing good data — check encoding type, channel count, and format negotiation."
                : "WASAPI is delivering silence — check device selection, mute state, signal source, and OS audio policy.");
    }
}
else
{
    // Audio data is flowing — reset the zero-output run counter.
    zeroOutputCount = 0;
}
```

The `else` branch that resets `zeroOutputCount` to zero is important: it ensures that
after a period of silence followed by real signal, the counter restarts from 1 so the
first resumed zero-output event is always logged.

---

### D2 — Rate-limit the "Resampler produced 0 output despite N samples" warning

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`, lines 229–242

This warning fires after the resampler drain loop when `buffer.BufferedBytes > 0`. Like
the zero-output warning it fires on every DataAvailable callback where the condition holds,
with no rate limiting.

Apply the same treatment — log on first occurrence and every 100 thereafter:

```csharp
// Before:
if (e.BytesRecorded > 0 && dataAvailableCount > 1)
{
    var samplesInBuffer = buffer.BufferedBytes /
        (capture.WaveFormat.BitsPerSample / 8 * capture.WaveFormat.Channels);
    if (samplesInBuffer > 0)
    {
        _logger?.LogWarning(
            "DIAG Resampler produced 0 output on '{DeviceId}' " +
            "despite {SamplesInBuffer} samples in buffer.",
            deviceId,
            samplesInBuffer);
    }
}
```

```csharp
// After:
if (e.BytesRecorded > 0 && dataAvailableCount > 1)
{
    var samplesInBuffer = buffer.BufferedBytes /
        (capture.WaveFormat.BitsPerSample / 8 * capture.WaveFormat.Channels);
    if (samplesInBuffer > 0 && dataAvailableCount % 100 == 1)
    {
        _logger?.LogWarning(
            "DIAG Resampler produced 0 output on '{DeviceId}' " +
            "despite {SamplesInBuffer} samples in buffer (at callback #{Count}).",
            deviceId,
            samplesInBuffer,
            dataAvailableCount);
    }
}
```

---

### D3 — Add WaveFormat encoding type to the startup log

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`, lines 81–88 (L-1 log)

The current L-1 log records sample rate, bits per sample, and channel count but not the
encoding type. Whether the device negotiates PCM or IEEE 754 float is critical for
diagnosing a `rawHasData=true`/zeros-out pipeline mismatch. Add it:

```csharp
// Before:
_logger?.LogInformation(
    "WASAPI device opened: '{DeviceId}' ('{FriendlyName}') — " +
    "WaveFormat={SampleRate} Hz, {BitsPerSample}-bit, {Channels} ch",
    deviceId,
    device.FriendlyName,
    capture.WaveFormat.SampleRate,
    capture.WaveFormat.BitsPerSample,
    capture.WaveFormat.Channels);
```

```csharp
// After:
_logger?.LogInformation(
    "WASAPI device opened: '{DeviceId}' ('{FriendlyName}') — " +
    "WaveFormat={SampleRate} Hz, {BitsPerSample}-bit, {Channels} ch, Encoding={Encoding}",
    deviceId,
    device.FriendlyName,
    capture.WaveFormat.SampleRate,
    capture.WaveFormat.BitsPerSample,
    capture.WaveFormat.Channels,
    capture.WaveFormat.Encoding);
```

`WaveFormatEncoding.Pcm`, `WaveFormatEncoding.IeeeFloat`, and
`WaveFormatEncoding.Extensible` are the three values most likely to appear. `Extensible`
with a sub-format GUID is what modern Windows audio uses almost universally; the sub-format
may not be printed by the default formatter, so also log the sub-format GUID if the
encoding is `Extensible`:

```csharp
if (capture.WaveFormat is WaveFormatExtensible ext)
{
    _logger?.LogInformation(
        "WASAPI sub-format on '{DeviceId}': {SubFormat}",
        deviceId, ext.SubFormat);
}
```

This will print the GUID directly. For reference: `{00000001-...}` = PCM,
`{00000003-...}` = IEEE float. Any other GUID indicates an unusual compressed format that
`BufferedWaveProvider.ToSampleProvider()` may not handle correctly.

---

## Advisory

**Unnecessary allocation in the resampler drain loop (line 226):**

```csharp
outBuf = new float[2048];  // ← reallocates every iteration
```

This allocates a new 2048-element array on every iteration of the while loop. With the
loop running every ~100 ms, this is not performance-critical, but it is unnecessary.
Move the `outBuf` allocation outside the loop and reuse the same buffer:

```csharp
// Before the while loop:
var outBuf = new float[2048];
int read;
while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
{
    var chunk = outBuf[..read];  // slice, not copy (if chunk ownership is not retained)
    // ... or keep the existing copy if innerChannel.Writer.TryWrite holds a reference
    // outBuf = new float[2048];  ← remove this line
}
```

Note: if `innerChannel.Writer.TryWrite(chunk)` hands ownership of `chunk` to the channel
consumer, the copy `outBuf.AsSpan(0, read).CopyTo(chunk)` into a fresh `float[read]` is
correct and necessary. In that case simply remove the `outBuf = new float[2048]` at the
end of the loop body and let the initial allocation be reused each iteration. The copy
into `chunk` is the allocation that matters, not the reuse of `outBuf`.

---

## Expected outcome after this briefing

With D1 applied, the first zero-output warning in a fresh session will read:

```
[warn] DIAG Resampler output all zeros on '...' (run #1, rawHasData=False) —
       WASAPI is delivering silence — check device selection, mute state,
       signal source, and OS audio policy.
```

or:

```
[warn] DIAG Resampler output all zeros on '...' (run #1, rawHasData=True) —
       NAudio pipeline is zeroing good data — check encoding type, channel count,
       and format negotiation.
```

Combined with the encoding type from D3, these two log lines together will determine the
next diagnostic step without requiring another code change.
