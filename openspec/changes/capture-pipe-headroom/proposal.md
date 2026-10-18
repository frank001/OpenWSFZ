**User-facing:** no

## Why

On `sol` (Linux, FX-8350) OpenWSFZ loses capture audio while the previous cycle's residual (subtraction) pass runs. The capture-loss instrument (PR #239) located the loss and the F1' / D-b' / pipe blocks of 2026-10-17 characterised it:

- The loss is at the daemon's reader, not at `arecord`'s CPU access: with `arecord` blocked in `pipe_write` for 20-60 % of the 3 s before each overrun and its run-queue delay at 3-7 % (D-b').
- `arecord` writes to a stdout pipe of the kernel's default size (64 KiB, about 1.37 s of 12 kHz float). When the daemon's reader stalls for longer, `arecord` blocks, ALSA's ring overruns, and audio is lost (10 overruns in 60 plays at the rig's 0.2 s ring).
- **A 1 MiB pipe (about 21.8 s of headroom) removed the loss on the series' build**: pipe-wrapper block on B2 (`f2beb559`), 60 plays, real rig: 0 overruns, 0 of 60 windows with `|wanted|` above 600 samples, 0 clamped, `wanted` median 10 samples; only 2 channel chunks dropped (the block on `main`'s slower decoder, with residual passes up to 22.6 s, dropped 95 chunks, so the pipe is not sufficient there: #236).
- The framer's `wanted` jitters with the client's delivery period: with a 133 ms period (arecord's default on a plain device) it moved by up to +-156 ms per cycle with no audio lost (D-b').

The Captain's direction: "I just want a reliable r&r because we are developing openwsfz" (2026-10-17). Architect ruling and spec: `qa/rr-study/2026-10-17-1736-architect-pipe-block-b2-ruling-and-product-spec.md`.

## What Changes

- `ArecordAudioSource` **enlarges its stdout pipe to 1 MiB** right after the child starts, with `fcntl(F_SETPIPE_SZ)` through a libc P/Invoke, reads the size back with `F_GETPIPE_SZ` and logs it. If the call fails (for example `EPERM` above `/proc/sys/fs/pipe-max-size`, or the descriptor is not a pipe) it logs a Warning with the errno and capture goes on with the default pipe. **Never fatal.**
- `arecord` is started with one more argument, **`--period-time=20000`** (20 ms). Evidence (read-only probe on `sol`, 2026-10-17, `arecord -v`): on `plughw:0,0` it changes the client period from 125 ms (1500 frames) to 20 ms (240 frames) with the buffer unchanged at 6000 frames; on the rig's `dsnoop` chain it is ignored (the slave's period rules); on `default` it changed nothing. **It is untested through the daemon on plain devices**; the pipe blocks used the rig's 20 ms period.
- **Not changed:** the channel stays at 16 chunks (the proposed 16 -> 256 is withdrawn: untested, and the framer's backlog wrap limit, `CycleFramer.cs` ~L253-282, 7.5 s, argues against it); the framer; `CaptureManager`; the other `arecord` arguments; the stdout and stderr reading; Windows (WASAPI) and macOS (`sox`).

## Non-goals

No fix for a stall longer than about 7.5 s ending at a window start (the framer's wrap limit; F2, parked). No change to the decoder or to the series' build line. No `--buffer-time` (the buffer a device grants is the device chain's; on a `dsnoop` rig the client cannot exceed the slave).

## Capabilities

### Modified Capabilities

- `audio-capture`: the `arecord` source enlarges its stdout pipe and pins the capture period.

## Impact

`src/OpenWSFZ.Audio/ArecordAudioSource.cs` (the pipe call after `process.Start()`; `DefaultStartInfo`'s argument list) and a small internal libc interop type; tests in `tests/OpenWSFZ.Audio.Tests`. Nothing in `native/`; no shim change; no GUI or API change.
