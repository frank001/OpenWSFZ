# R&R S1-S8 on Linux (QA tooling; first run 2026-10-11 on the Gentoo host `sol`)

What this folder adds, and what the host needs. Nothing under `src/` or `native/` is involved, and no Windows file was edited.

## Launch

```
export PYTHONPATH=<repo>/qa/rr-study/linux/shim RR_ALSA_PLAYBACK=plughw:0,0
cd <repo>/qa/rr-study
nohup python run_study_linux.py --poll --supervisor-dir <dir> --daemon-exe <published OpenWSFZ.Daemon> \
      --config <daemon config> --port 8080 --wsjtx-ini "<WSJT-X data dir>/WSJT-X - rr.ini" \
      -- --scenarios S1,S1b,S2,S3,S4,S5,S7,S8,S3c --skip-warmup --device RR-ALSA > <dir>/supervisor.log 2>&1 &
```

S6 (off-air WAV replay, spec 2026-10-13) is part of the default battery when `~/rr-s6-refset-corpus` exists: add `S6` to `--scenarios` (or omit `--scenarios`), and choose its size with `--s6-tier quick|standard|extended` (default standard; about 18 min / 45 min / 2 h 15 min). The launcher forwards the daemon's stdout log (per-play abandonment) and the native library it loaded (the S6-V5 pin). `--scenarios S6 --s6-tier quick` alone is the dry run. S6 plays real recordings: its log lines are moved into `~/qa-scratch/s6-<run>/` (outside git, delete at job close).

## Files

| file | role |
|---|---|
| `shim/sounddevice.py` | `sounddevice` stand-in: plays through `aplay` (the harness needs only `query_devices`, `play`, `wait`) |
| `linux_compat.py` | replaces the PowerShell / `taskkill` / process-flag primitives of `endurance_supervisor` with `/proc` and signals |
| `../rr_precheck_linux.py` | twin of `rr_precheck.py`; one documented difference (device check compares the config's `audioDeviceId` with WSJT-X's `SoundInName`) |
| `../run_study_linux.py` | entry point for the detached supervisor's `--poll` mode |

## Host requirements (what had to be true on `sol`)

1. **Audio, plain ALSA, no PulseAudio.** The synthesiser plays to the codec output; the codec's `Stereo Mix` capture source is the digital loopback; `Loopback Mixing` Enabled, `Capture` on, `Master` unmuted (a muted Master gates the loopback). A user `~/.asoundrc` defines `pcm.rr_cap` (`dsnoop` on `hw:0,0`, 48 kHz stereo S16) and `pcm.rr_in` (`plug` on it) so the daemon and WSJT-X read the same capture at once. Both are configured with the device name `rr_in`.
2. **OpenWSFZ daemon:** self-contained `linux-x64` publish (`tools/publish_selfcontained.py`), `tools/capture_build_provenance.py` run next to it, config with `audioDeviceId: "rr_in"` and NO friendly name (issues #232, #233), decode log and `cycleAudioArchive.mode = "all"` under the run folder.
3. **WSJT-X 2.7.0, built from the verified source tarball** (SHA-256 `3788f5df...cec93`) with conda-forge Qt5 / Boost / FFTW and **gfortran 13** (gfortran 15+ clashes with the Fortran 2023 `split` intrinsic), CMake 3.27, hamlib configured `--without-readline`, `libudev` provided. Run headless under `xvfb-run` (1920x1080). **WSJT-X 3.x cannot be the appraiser: its new `callok` rejects every callsign starting with Q, and the synthetic truth set is Q-prefix only.**
4. **WSJT-X profile `rr`:** whitelisted decode keys copied from the station profile (`Mode FT8`, `NDepth 3`, the FT8 a-priori switch off, `SaveAll true`, `RxFreq 2838`, ...), `MyCall` a Q-call, and a `[WideGraph]` section (`PlotWidth 1038`, `BinsPerPixel 5`, `StartFreq 0`). Without the waterfall settings a fresh headless profile's decode window does not reach 1500 Hz and the live decoder finds nothing. The ini is linked next to `ALL.TXT` so the launcher can read both from one folder.
5. **Python venv** with numpy, scipy, pandas, matplotlib, scikit-learn; `qa/rr-study/.venv/Scripts/python.exe` is a one-line wrapper script that execs the venv's python (the runner hard-codes that Windows path).

6. **Rate converter (the one that decides the SNR rows).** ALSA's `plug` plugin converts the 48 kHz capture to the 12 kHz the daemon asks for. Its default `linear` converter has no anti-alias filter: noise above 6 kHz folds into the band and OpenWSFZ's reported SNR reads about 4.5 dB low (S1 bias -3.75 dB, FAIL; product issue #234). The corrected chain sets `rate_converter "samplerate_best"` on the capture `plug` PCM, which needs the alsa-plugins `samplerate` plugin (built from source on `sol`, pointed to with `ALSA_PLUGIN_DIR=~/local/lib/alsa-lib` in the environment of BOTH programs). Reports from the default chain are labelled "default ALSA chain" and those from the corrected chain "non-default chain: `samplerate_best`"; never pool the two. First pair: S1 bias -3.75 dB (default) against +1.35 dB (S1 only) and +0.88 dB (full battery) on the corrected chain; the Windows sweeps read +0.85 to +1.48 dB.

## The appraiser gate (PRECHECK)

PRECHECK measures the installed WSJT-X instead of trusting a typed version (`../wsjtx_version.py`): it renders a canary WAV (`CQ Q1ABC FN42` at +20 dB), decodes it through the running installation's own `jt9`, and refuses the battery if the canary does not come back. WSJT-X 3.x cannot decode Q-prefix callsigns (its `callok` rejects them), so a 3.x install fails the gate by itself. The measured version is written to `wsjt-version.txt` of the run folder. Needs WSJT-X running with Monitor ON.

## Launcher notes

- `run_study_detached.py` forwards `--wsjt-all-txt` to `run_study.py`; since `ceb05641` it does so whether or not the file exists at start (a clean WSJT-X profile has none until the first decode).
- `--wsjtx-version` is optional and only a label; the measured gate above is the check.
- A same-date, same-commit run folder is not overwritten: move an earlier one aside first.
- Never run a battery while a replay (the REFERENCE-SET harness, `../refset/harness`) or a compile is on: the machine is one resource, and decode abandonment is load-sensitive.

## Replays on `sol` (REFERENCE-SET legs A and D)

The off-air replay harness (`../refset/harness`) reads files and does not use the audio chain, so #232, #233 and #234 do not touch it. It is platform-neutral and builds, tests and runs on `sol` first. `../refset/harness/build_native_linux.sh` builds the Linux `libft8.so` of a given commit and the harness against it.

Known non-blocking noise: the audio-setup sampler hook tries PowerShell and reports `STOP FAILED`; the battery continues (by design).

## B2 build, WSJT-X monitoring and the capped retry (2026-10-14)

`battery-b2.sh <name> <scenarios> [extra run_study.py args]` runs ONE supervised battery on `sol` with the B2-merged daemon (`~/OpenWSFZ-b2src`, publish folder, `libft8.so` pin from the merged tree) and the tooling checkout `~/rr-work-b2`: it (re)starts WSJT-X 2.7.0 with `ulimit -c unlimited`, starts the M1 monitor (`wsjtx_monitor.py`) beside the battery, passes `--liveness-save-dir` / `--coverage-owsfz-dir` to `run_study.py` (M2 gate: stop and flag when no new save WAV for 45 s or no `wsjtx` process; M3: coverage slots for the analyser's validity row), and tears everything down. Needs `tools/capture_build_provenance.py --rid linux-x64` run once after publishing the daemon, and the `.venv/Scripts/python.exe` wrapper in the tooling checkout (copy it from `~/rr-work`).

**Capped retry, opt-in:** `MAX_STALL_RETRIES=1 sh battery-b2.sh ...` (default 0 = stop and flag). Only a liveness stop (`STALLED.json`) is retried, and only as a COMPLETE sweep: the failed sweep's folders are kept as `*-INVALID-stall-attemptK` with an `INVALID.md`, WSJT-X is restarted, the new sweep carries `REPLACEMENT.json`. A second stall, or any other failure, halts for good. `inject-stall-test.sh <name>` (TEST ONLY) freezes `wsjtx` once with SIGSTOP to prove the chain; tested 2026-10-14: stall detected after 53 s, snapshot shows `wchan=do_signal_stop`, attempt 2 complete and PASS.
