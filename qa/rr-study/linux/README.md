# R&R S1-S8 on Linux (QA tooling; first run 2026-10-11 on the Gentoo host `sol`)

What this folder adds, and what the host needs. Nothing under `src/` or `native/` is involved, and no Windows file was edited.

## Launch

```
export PYTHONPATH=<repo>/qa/rr-study/linux/shim RR_ALSA_PLAYBACK=plughw:0,0
cd <repo>/qa/rr-study
nohup python run_study_linux.py --poll --supervisor-dir <dir> --daemon-exe <published OpenWSFZ.Daemon> \
      --config <daemon config> --port 8080 --wsjtx-ini "<WSJT-X data dir>/WSJT-X - rr.ini" \
      --wsjtx-version "2.7.0" \
      -- --scenarios S1,S1b,S2,S3,S4,S5,S7,S8,S3c --skip-warmup --device RR-ALSA > <dir>/supervisor.log 2>&1 &
```

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
4. **WSJT-X profile `rr`:** whitelisted decode keys copied from the station profile (`Mode FT8`, `NDepth 3`, `FT8AP false`, `SaveAll true`, `RxFreq 2838`, ...), `MyCall` a Q-call, and a `[WideGraph]` section (`PlotWidth 1038`, `BinsPerPixel 5`, `StartFreq 0`). Without the waterfall settings a fresh headless profile's decode window does not reach 1500 Hz and the live decoder finds nothing. The ini is linked next to `ALL.TXT` so the launcher can read both from one folder.
5. **Python venv** with numpy, scipy, pandas, matplotlib, scikit-learn; `qa/rr-study/.venv/Scripts/python.exe` is a one-line wrapper script that execs the venv's python (the runner hard-codes that Windows path).

Known non-blocking noise: the audio-setup sampler hook tries PowerShell and reports `STOP FAILED`; the battery continues (by design).
