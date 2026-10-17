## 1. Tests first (each must be able to fail)

- [ ] 1.1 `ArecordAudioSource`: a fake process (test `ProcessStartInfo`, as `FilePipeStartInfo` does) writes known PCM to stdout and `overrun!!! (at least 10.5 ms long)` lines to stderr. Assert `CaptureOverrunCount`, `CaptureOverrunReportedMs`, and the Warning log text (UTC time with milliseconds, reported length).
- [ ] 1.2 **Byte identity:** the chunks yielded with stderr noise equal, element for element, the chunks yielded for the same PCM with empty stderr (compare the raw bytes).
- [ ] 1.3 **Pipe-fill regression:** the fake writes at least 256 KiB to stderr before its stdout reaches EOF; capture must complete within a generous timeout. **State in the handoff that this test hangs on the base commit** (run it there and record the result).
- [ ] 1.4 Non-overrun stderr lines: logged at Information, the first 20 and then every 100th; not counted as overruns. A mixed-case `OVERRUN` counts; a line without a parsable length counts and adds 0 ms.
- [ ] 1.5 `arecord` is started with `LC_ALL=C` in the environment and with the same arguments as before (assert the argument list equals the base commit's).
- [ ] 1.6 `CaptureManager`: a source that outruns a non-reading consumer increments `CaptureChannelDroppedChunks` by exactly the number of chunks dropped; the first and every 100th drop log a Warning with a UTC millisecond time; with a draining consumer the counter stays 0.
- [ ] 1.7 `CycleFramer`: the existing alignment tests pass **unchanged**; one new test asserts one Information line per emitted window carrying the cycle start, `wanted` and applied in samples (use a drifting source so `wanted` is non-zero).
- [ ] 1.8 `DaemonStatus`: `GET /api/v1/status` and the WebSocket `status` event carry the three counters (provider values), defaulting to 0 when no provider is supplied; JSON names follow the existing camelCase of `cycleArchiveDroppedCycles`.

## 2. Implementation

- [ ] 2.1 `ArecordAudioSource`: stderr reader task (Decisions 1-4), `LC_ALL=C` (5), counters (9, 10). Do not touch the stdout loop, the chunk size, the `arecord` arguments or the exit-code handling.
- [ ] 2.2 `CaptureManager`: `itemDropped` counter and log (6); expose the counters.
- [ ] 2.3 `CycleFramer`: the `Window emitted` line to Information with `wanted` added (7). No change to `wanted`, `correction`, `consume` or the clamp warning.
- [ ] 2.4 `DaemonStatus`, `WebApp`, `WebSocketHub`, `Program.cs`: counters and providers, following `cycleArchiveDroppedCyclesProvider` (8). **Do not edit `CaptureHealthMonitor`'s `Heartbeat:` line.**
- [ ] 2.5 Grep the repository (src, tests, `qa/`, `tools/`) for anything that parses `Window emitted` or `Heartbeat:` and list the hits in the PR.
- [ ] 2.6 Nothing in `native/`; no shim version change; no GUI change.

## 3. Verification

- [ ] 3.1 `dotnet build`, `dotnet test` green; `openspec validate --all --strict`.
- [ ] 3.2 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA reviews against section 1 (including the byte-identity test and the pipe-fill hang on the base commit) and builds the study tree; the Captain signs off the merge (HK-010).
