# Developer Handoff — WSL2 Linux Audio Environment for Cross-Platform R&R Study

**Issued by:** QA  
**Date:** 2026-06-30  
**Branch:** `chore/wsl-linux-rr-environment`  
**Triggered by:** Captain request — execute the cross-platform (Windows win-x64 vs Linux linux-x64)
Gauge R&R study defined in `qa/rr-study/STUDY-SPEC-XPLAT.md`.  
**Study spec:** [`qa/rr-study/STUDY-SPEC-XPLAT.md`](../qa/rr-study/STUDY-SPEC-XPLAT.md)

---

## Context

The existing R&R study (STUDY-SPEC.md) runs exclusively on Windows, using WASAPI and VB-CABLE.
The OpenWSFZ daemon already has a complete Linux audio path: `ArecordAudioSource` drives
`arecord -D <device> -f FLOAT_LE -r 12000 -c 1 -t raw -` and `SubprocessAudioDeviceProvider`
enumerates devices via `arecord --list-devices`. Both are already compiled and tested.

The cross-platform study requires the daemon to run on WSL2 and capture audio from a real ALSA
device backed by WSLg's PulseAudio bridge. The Windows synthesizer plays WAV fixtures into a
loopback device that WSL2 sees as a PulseAudio source; `arecord -D pulse` captures from it.

VB-Audio Virtual Cable and VB-Audio Voicemeeter VAIO are **already installed** on this machine
(confirmed 2026-06-30). No driver installs are required.

---

## Actions

### 1 — Verify WSL2 is installed and identify the Ubuntu distro

From a Windows PowerShell / Git Bash terminal:

```powershell
wsl --list --verbose
```

Expected: an Ubuntu distro listed, `VERSION 2`. If absent, install WSL2:

```powershell
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
```

Record the exact distro name (e.g. `Ubuntu-22.04`) in the runbook update (Action 8).

---

### 2 — Install system prerequisites inside WSL2

Open a WSL2 shell (`wsl -d Ubuntu-22.04`) and run:

```bash
sudo apt-get update && sudo apt-get install -y \
    alsa-utils \
    pulseaudio-utils \
    libasound2-plugins \
    dotnet-sdk-8.0 \
    python3-pip \
    python3-venv
```

**Notes:**
- `alsa-utils` provides `arecord` and `aplay`.
- `libasound2-plugins` provides the PulseAudio ALSA plugin (`pcm.pulse` / `ctl.pulse`),
  which allows `arecord -D pulse` to route through PulseAudio.
- `dotnet-sdk-8.0` — if not in the default Ubuntu package feed, use Microsoft's feed:
  <https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu>
- Python is needed to run the R&R harness (`run_study.py`, `analyse.py`).

---

### 3 — Verify WSLg PulseAudio bridge

WSL2 on Windows 11 (WSLg) provides a PulseAudio socket at `/run/user/1000/pulse/native`
(or similar). Verify it is live:

```bash
pactl info
```

Expected output includes `Server Name: pulseaudio` and a non-empty `Default Source`.
If `pactl` cannot connect, WSLg audio is not enabled — check Windows version (requires
Windows 11 Build 22000+ with WSLg).

List available sources (input devices):

```bash
pactl list sources short
```

Look for:
- A `*.monitor` source — this is the loopback capture point that mirrors Windows playback.
- The name will be something like `alsa_output.pci-...CABLE_Input...monitor` or similar.

Record the exact source name; it is the device ID for the daemon (Action 6).

---

### 4 — Verify `arecord -D pulse` works

Confirm ALSA→PulseAudio bridge:

```bash
arecord -D pulse -f FLOAT_LE -r 12000 -c 1 -t raw -d 3 /tmp/test_capture.raw
```

This should run for 3 seconds without error. Inspect the file is non-empty:

```bash
ls -la /tmp/test_capture.raw   # expect > 0 bytes
```

Also verify the device list endpoint:

```bash
arecord --list-devices
```

Expected: one or more `hw:N,M` entries. These are the hardware ALSA devices; the daemon
will use `pulse` as the device ID for PulseAudio routing (not a `hw:` ID).

> **Note:** The daemon's `PlatformAudioDeviceProvider` returns `hw:N,M` IDs from
> `arecord --list-devices`. For this study, the operator must **manually specify `pulse`**
> as the device ID in the daemon's configuration rather than selecting from the enumerated
> list, because the PulseAudio ALSA plugin device is not surfaced by `--list-devices`.
> This is a known limitation; a follow-up may add explicit PulseAudio source enumeration.

---

### 5 — Build and run OpenWSFZ.Daemon on WSL2

From the WSL2 shell, navigate to the project root (the Windows path `D:\Projects\claude\OpenWSFZ`
is accessible as `/mnt/d/Projects/claude/OpenWSFZ`):

```bash
cd /mnt/d/Projects/claude/OpenWSFZ
dotnet build OpenWSFZ.slnx -c Release
```

Run the daemon:

```bash
dotnet run --project src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj -c Release
```

Confirm startup in logs:
- `"Linux"` or `"ArecordAudioSource"` should appear in audio initialization log lines.
- Daemon HTTP endpoint listening (default: `http://localhost:5000`).

---

### 6 — Configure the daemon's audio device for PulseAudio

The daemon reads its audio input device from `appsettings.json` or the `Audio.InputDeviceId`
configuration key. Set it to `pulse`:

```bash
# From the project root inside WSL2:
cat > /tmp/appsettings.Override.json << 'EOF'
{
  "Audio": {
    "InputDeviceId": "pulse"
  }
}
EOF
```

Alternatively, pass as an environment variable if the daemon supports it:

```bash
Audio__InputDeviceId=pulse dotnet run --project src/OpenWSFZ.Daemon/...
```

Consult `src/OpenWSFZ.Daemon/appsettings.json` for the exact key name.
Record the verified key name in the runbook update (Action 8).

---

### 7 — End-to-end loopback verification

With the daemon running on WSL2 and configured for `pulse`:

1. **On Windows:** Play any FT8-format WAV file to VB-CABLE Input (select *CABLE Input* as
   the playback device in Windows media player / `ffplay`).

2. **In WSL2 daemon logs:** Confirm audio samples are being received (the daemon logs
   periodic audio-level or capture-active messages at `Debug` level).

3. **Verify decode:** If an FT8 message decodes, a `decode` event appears in the daemon's
   WebSocket stream or `ALL.TXT` log. Use any S1 fixture at +0 dB or above for this check.

This end-to-end check proves: Windows WASAPI → VB-CABLE → WSLg PulseAudio bridge → `arecord`
→ `ArecordAudioSource` → FT8 decode pipeline → `libft8.so` (Linux binary).

---

### 8 — Document the verified configuration in `RUNBOOK.md`

Update `qa/rr-study/RUNBOOK.md` §1.4 ("Other platforms — not yet validated") with a new
sub-section §1.5 "Linux / WSL2" containing:

- WSL2 distro name and version used.
- Confirmed PulseAudio source name (from Action 3).
- Exact daemon configuration key and value for audio device.
- Any deviations from the expected procedure above (e.g. different apt package names,
  kernel version, WSLg socket path).
- The `arecord --version` output.
- The `dotnet --version` output confirming .NET 8.

---

### 9 — Install the R&R harness Python environment

The R&R harness (`qa/rr-study/`) requires a Python virtual environment. Inside WSL2:

```bash
cd /mnt/d/Projects/claude/OpenWSFZ/qa/rr-study
python3 -m venv .venv-linux
source .venv-linux/bin/activate
pip install -r requirements.txt   # or: pip install numpy scipy soundfile pandas matplotlib
```

Verify the harness imports without error:

```bash
python harness/run_study.py --help
```

---

## Acceptance Criteria

The environment is ready for the cross-platform R&R study when **all** of the following hold:

| # | Criterion | How to verify |
|---|---|---|
| AC-1 | `wsl --list --verbose` shows WSL2 (VERSION 2) Ubuntu distro | Run command; check output |
| AC-2 | `pactl info` connects to PulseAudio inside WSL2 | Run; no `Connection refused` |
| AC-3 | `pactl list sources short` lists at least one `*.monitor` source | Run; inspect output |
| AC-4 | `arecord -D pulse -f FLOAT_LE -r 12000 -c 1 -t raw -d 3 /tmp/t.raw` produces a non-empty file | Run; `ls -la /tmp/t.raw` |
| AC-5 | `dotnet build OpenWSFZ.slnx -c Release` completes 0 errors inside WSL2 | Run; check output |
| AC-6 | Daemon starts on WSL2 and logs `ArecordAudioSource` or equivalent | Run daemon; inspect log |
| AC-7 | Playing an FT8 WAV on Windows side produces a decode in the WSL2 daemon | End-to-end test (Action 7) |
| AC-8 | RUNBOOK.md §1.5 written and committed to the branch | Read file |
| AC-9 | Python harness `run_study.py --help` executes without ImportError inside WSL2 | Run; check output |

---

## References

- [`qa/rr-study/STUDY-SPEC.md`](../qa/rr-study/STUDY-SPEC.md) — existing Windows R&R study spec
- [`qa/rr-study/STUDY-SPEC-XPLAT.md`](../qa/rr-study/STUDY-SPEC-XPLAT.md) — new cross-platform study spec (companion to this handoff)
- `src/OpenWSFZ.Audio/ArecordAudioSource.cs` — Linux capture implementation
- `src/OpenWSFZ.Audio/PlatformAudioSource.cs` — platform selection logic
- `src/OpenWSFZ.Audio/SubprocessAudioDeviceProvider.cs` — Linux device enumeration

---

*Issued by QA. Queries to the QA persona; implementation to the Developer persona.*
