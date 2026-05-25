# Developer Briefing — p5-ft8-decoder (Round 18)

**Date:** 2026-05-24
**Issued by:** QA
**Branch:** `feat/p5-ft8-decoder`
**Scope:** Eliminate remaining log flood; diagnose and fix zero-audio pipeline

---

## Situation

The dev-briefing-17 rate-limit change (`% 100 == 0`) reduced the warning from ~1 000/s to
~1/s. At 100 `DataAvailable` callbacks per second the modulus still fires once per second —
still far too verbose. That is fixed below as a one-liner.

More importantly, the log has now confirmed the diagnostic branch:

```
rawHasData=True, resampler output = all zeros, run #161 300+
```

WASAPI is delivering non-zero bytes. The NAudio pipeline is producing zeros. The device is
not at fault.

**There is exactly one common cause of all-zero output from non-zero stereo input in a
`(L + R) / 2` averaging pipeline: phase cancellation.**

Many SDR interfaces and balanced audio inputs deliver a differential signal:
`L = +signal, R = −signal`. `StereoToMonoSampleProvider` computes `(L + R) / 2`.
When L = −R exactly, every output sample is zero, always, regardless of signal amplitude.
The raw buffer is non-zero (`rawHasData=True`); the averaged output is zero.

This briefing stops the flood, confirms the hypothesis with one targeted log, and fixes
the pipeline if confirmed.

---

## Tasks

### D4 — Fire the zero-output warning exactly once per session

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

Change the rate-limit condition from `% 100 == 0` to fire only on the first occurrence
and never again:

```csharp
// Before:
if (zeroOutputCount == 1 || zeroOutputCount % 100 == 0)

// After:
if (zeroOutputCount == 1)
```

The first occurrence already carries all the diagnostic information (`rawHasData`,
`run #1`). Every subsequent repetition adds nothing. This change reduces the warning from
~1/s to once per session.

---

### D5 — Add a one-shot phase-cancellation diagnostic on first zero-output event

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`, immediately after the `zeroOutputCount == 1` log

When the first zero-output event fires, also log the first four raw float values from the
WASAPI buffer — interpreted as interleaved stereo IEEE 754 floats — so we can immediately
see whether `L ≈ −R`:

```csharp
if (zeroOutputCount == 1)
{
    _logger?.LogWarning(
        "DIAG Resampler output all zeros on '{DeviceId}' " +
        "(run #1, rawHasData={RawHasData}) — {Diagnosis}",
        deviceId,
        rawHasData,
        rawHasData
            ? "NAudio pipeline is zeroing good data — check encoding type, channel count, and format negotiation."
            : "WASAPI is delivering silence — check device selection, mute state, signal source, and OS audio policy.");

    // D5 (DIAG): if rawHasData=True and the device is stereo, log the first two
    // interleaved L/R float pairs from the raw buffer.  If L0 ≈ −R0 and L1 ≈ −R1,
    // the device delivers a differential (balanced) signal and StereoToMonoSampleProvider
    // is cancelling it.  Fix: use left-channel-only extraction (see D6).
    if (rawHasData && capture.WaveFormat.Channels == 2 && e.BytesRecorded >= 16)
    {
        var span = e.Buffer.AsSpan(0, 16); // 4 floats × 4 bytes = 2 stereo frames
        var f    = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, float>(span);
        _logger?.LogWarning(
            "DIAG Phase-cancellation check on '{DeviceId}': " +
            "L0={L0:G4}, R0={R0:G4}, L1={L1:G4}, R1={R1:G4} — " +
            "if L ≈ −R the device delivers a differential signal; stereo averaging cancels it.",
            deviceId, f[0], f[1], f[2], f[3]);
    }
}
```

**How to read the output:**

| L0 | R0 | Diagnosis |
|---|---|---|
| `+0.0123` | `−0.0123` | Phase cancellation confirmed → apply D6 fix |
| `+0.0123` | `+0.0123` | Identical channels → averaging is correct; different root cause |
| `6.4e-38` | `3.1e-38` | Subnormal floats → bytes are not IEEE 754 audio → format encoding issue |
| `0` | `0` | Both zero despite rawHasData=True → non-audio bytes are non-zero (rare); re-examine |

---

### D6 — Fix: replace `StereoToMonoSampleProvider` with left-channel extraction

**Apply after D5 confirms `L ≈ −R`.**

**File:** `src/OpenWSFZ.Audio/WasapiAudioSource.cs`

`StereoToMonoSampleProvider` averages both channels. For a differential signal
(L = −R), the average is always zero. The correct fix is to extract a single channel.

Add the following private nested class to `WasapiAudioSource`:

```csharp
/// <summary>
/// Extracts the left channel from a stereo IEEE float sample stream.
/// Used instead of <see cref="StereoToMonoSampleProvider"/> when the audio device
/// delivers a differential (balanced) signal where L = −R: averaging both channels
/// produces silence, but either channel alone carries the full signal.
/// </summary>
private sealed class LeftChannelSampleProvider : ISampleProvider
{
    private readonly ISampleProvider _source;
    private float[]                  _stereoBuffer = new float[4096];

    public LeftChannelSampleProvider(ISampleProvider source)
    {
        if (source.WaveFormat.Channels != 2)
            throw new ArgumentException("Source must be stereo.", nameof(source));
        _source    = source;
        WaveFormat = WaveFormat.CreateIeeeFloatWaveFormat(
            source.WaveFormat.SampleRate, channels: 1);
    }

    public WaveFormat WaveFormat { get; }

    public int Read(float[] buffer, int offset, int count)
    {
        int stereoCount = count * 2;
        if (_stereoBuffer.Length < stereoCount)
            _stereoBuffer = new float[stereoCount];

        int read = _source.Read(_stereoBuffer, 0, stereoCount);
        int mono = read / 2;
        for (int i = 0; i < mono; i++)
            buffer[offset + i] = _stereoBuffer[i * 2]; // left channel (index 0 of each interleaved pair)
        return mono;
    }
}
```

Then replace the `StereoToMonoSampleProvider` instantiation (line ~111):

```csharp
// Before:
if (capture.WaveFormat.Channels == 2)
    samples = new StereoToMonoSampleProvider(samples);

// After:
if (capture.WaveFormat.Channels == 2)
    samples = new LeftChannelSampleProvider(samples);
```

Update the L-2 log to reflect the change:

```csharp
_logger?.LogInformation(
    "Resampling pipeline ready on '{DeviceId}': " +
    "channelMode={ChannelMode}, inputRate={InputRate} Hz → 12000 Hz",
    deviceId,
    capture.WaveFormat.Channels == 2 ? "stereo→mono(left)" : "mono",
    capture.WaveFormat.SampleRate);
```

---

## If D5 does NOT confirm phase cancellation

If `L` and `R` have similar sign and magnitude (e.g., both `+0.0123`), the signal is not
differential. In that case do not apply D6. Instead:

1. Check whether the raw float values look like plausible audio (magnitudes in `[1e-6, 1.0]`).
   - If yes: the pipeline is processing the format but something downstream zeroes it.
     Report back with the D5 log output and the L-1 startup log
     (`WASAPI device opened` and `WASAPI sub-format` lines) for further analysis.
   - If values are subnormal (`< 1e-10`): the bytes are not IEEE 754 audio.
     The WaveFormat encoding is the issue. Report back with the L-1 and D3 log lines.

2. Check whether the `WASAPI sub-format` startup log line shows:
   - `{00000003-...}` = IEEE float → `ToSampleProvider()` path is likely correct.
   - `{00000001-...}` = PCM → verify `BitsPerSample` matches the data layout.
   - Anything else → unusual format; `ToSampleProvider()` may not handle it.

---

## Summary

| Task | Effect |
|---|---|
| D4 | Zero-output warning fires once per session instead of once per second |
| D5 | First warning includes L0/R0/L1/R1 raw values; immediately confirms or denies phase cancellation |
| D6 | Replaces averaging stereo-to-mono with left-channel extraction; fixes differential-signal devices |
