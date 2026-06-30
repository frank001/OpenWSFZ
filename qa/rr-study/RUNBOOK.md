# OpenWSFZ ↔ WSJT-X R&R Study — Operator Runbook

**Document type:** Operator setup & run procedure (QA deliverable)
**Companion to:** [`STUDY-SPEC.md`](./STUDY-SPEC.md)
**Status:** Living document — extended as harness components land
**Last updated:** 2026-06-05

---

## 0. Why a virtual audio cable is required

The R&R study (see `STUDY-SPEC.md` §2.1 and §4) is a properly *crossed* measurement:
**both applications must capture the identical noise realization, simultaneously, for every
trial.** That is only possible if the harness can play one synthesized PCM stream into a single
audio endpoint that **WSJT-X and OpenWSFZ both open concurrently** as their input.

A **virtual audio cable** provides exactly that — a software loopback device whose *render*
(playback) side is fed by the harness and whose *capture* (recording) side is opened by both
applications in WASAPI shared mode. Without it there is no shared, repeatable injection point and
the crossed design collapses.

> A real analog loopback (line-out → line-in) is an *optional* external-validity variant only.
> The default and supported configuration is the virtual cable, because the intended variation is
> injected in software as seeded noise per trial (`STUDY-SPEC.md` §2.1).

---

## 1. Prerequisite: install the virtual audio cable

This study has been brought up and validated on **Windows with VB-CABLE**. Equivalent loopbacks
exist on other platforms (see §1.4) but are not yet validated.

### 1.1 Install VB-CABLE (Windows — required)

1. Download **VB-CABLE Virtual Audio Device** (Donationware) from VB-Audio:
   <https://vb-audio.com/Cable/>
2. Unzip the archive to a local folder.
3. **Right-click `VBCABLE_Setup_x64.exe` → Run as administrator.** (The 32-bit `VBCABLE_Setup.exe`
   exists for legacy systems; use the x64 installer on modern Windows.)
4. Click **Install Driver**, accept the Windows driver prompt, and **reboot** when prompted.
   A reboot is required before the endpoints behave reliably.

After installation two new endpoints appear in Windows Sound settings:

| Endpoint | Windows role | Used by | Direction |
|---|---|---|---|
| **CABLE Input (VB-Audio Virtual Cable)** | Playback / render | **Harness** writes the synthesized PCM here | Render |
| **CABLE Output (VB-Audio Virtual Cable)** | Recording / capture | **WSJT-X _and_ OpenWSFZ** open this as their audio input | Capture |

> Mnemonic: audio goes **in** to the cable via *CABLE Input*, and comes **out** for the apps via
> *CABLE Output*. Both applications select **CABLE Output** as their input device.

### 1.2 Configure the shared format (48 kHz, mono, shared mode)

The synthesizer renders **mono PCM at 48 kHz** (`STUDY-SPEC.md` §4). To avoid resampling artefacts,
set both sides of the cable to a matching shared-mode format:

1. Open **Sound → Sound Control Panel** (`mmsys.cpl`).
2. **Playback** tab → *CABLE Input* → **Properties → Advanced** →
   set **Default Format** to **2 channel, 16 bit, 48000 Hz**. Untick both **Exclusive Mode**
   checkboxes (the study uses shared mode).
3. **Recording** tab → *CABLE Output* → **Properties → Advanced** →
   set the same **48000 Hz** default format; untick Exclusive Mode.
4. (Recommended) On the *CABLE Output* **Listen** tab, leave **"Listen to this device"**
   *unticked* during study runs to avoid feedback to your monitors.

### 1.3 Verify concurrent capture (one-time bring-up check)

WASAPI shared mode permits multiple capture clients on one endpoint, but verify it once:

1. Start **OpenWSFZ**, select **CABLE Output** as the audio device, start decode.
2. Start **WSJT-X**, mode **FT8**, **Monitor ON**, audio input = **CABLE Output**.
3. Play any 48 kHz audio file to **CABLE Input** (e.g. via a media player whose output device is
   *CABLE Input*).
4. Confirm **both** applications show input-level activity on their meters simultaneously.

If a platform refuses concurrent capture, fall back to two synchronized sequential runs of the
identical seeded vector (`STUDY-SPEC.md` §14).

### 1.4 Other platforms (not yet validated)

| OS | Equivalent loopback | Notes |
|---|---|---|
| **Linux** | PulseAudio `module-null-sink` + `module-loopback` | Apps capture the null sink's `.monitor` source. |
| **macOS** | **BlackHole** (2ch) — <https://existential.audio/blackhole/> | Both apps select BlackHole as input. |

### 1.5 Linux / WSL2 (validated 2026-06-30)

**Environment:**

| Item | Value |
|---|---|
| WSL2 distro | Debian GNU/Linux 13 (trixie) |
| WSL2 kernel | `6.6.87.2-microsoft-standard-WSL2` |
| WSL2 version | VERSION 2 (confirmed via `wsl --list --verbose`) |
| `arecord` version | 1.2.14 (from `alsa-utils` package) |
| .NET runtime | Shipped as AOT-compiled native binary (no SDK in WSL2) |

**PulseAudio source name:**

WSLg exposes two PulseAudio sources inside WSL2:

| Source | Module | Format | Role |
|---|---|---|---|
| `RDPSink.monitor` | `module-rdp-sink.c` | s16le 2ch 44100Hz | **Use this for loopback capture** — monitors Windows audio playback via WSLg RDP bridge |
| `RDPSource` | `module-rdp-source.c` | s16le 1ch 44100Hz | Microphone input from Windows host |

> **Note:** There is no VB-CABLE–named source visible in WSL2. WSLg bridges Windows
> audio rendering to PulseAudio through `RDPSink.monitor`; the loopback device's audio
> reaches WSLg via the host's audio rendering graph. The exact path is host-specific —
> see Deviation 6 below and the audio-chain verification step in STUDY-SPEC-XPLAT.md §11.

**Daemon audio device configuration:**

The daemon's audio device is set via the JSON config file at `~/.config/OpenWSFZ/config.json`.
Set `audioDeviceId` to `"pulse"` to route through PulseAudio:

```json
{
  "audioDeviceId": "pulse",
  "decodeLog": { "enabled": true }
}
```

The daemon selects the PulseAudio default source when `pulse` is specified. The default
source can be set with:

```bash
pactl set-default-source RDPSink.monitor
```

**Daemon binary:**

The daemon is distributed as a CI-built native AOT binary. Download from the GitHub CI
artifact `daemon-linux-x64` (produced by the `build-test / ubuntu-latest` matrix leg).
Place `OpenWSFZ.Daemon` and `libft8.so` in the same directory:

```bash
# Copy libft8.so from the repo (already committed at correct shim version)
cp src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so qa/rr-study/linux-daemon/
chmod +x qa/rr-study/linux-daemon/OpenWSFZ.Daemon
```

**Verified startup log (confirming ArecordAudioSource and linux-x64 libft8.so):**

```
[INF] Starting FT8 pipeline for device 'pulse'.
[INF] Starting audio capture on device 'pulse'.
[INF] CycleFramer started; cycle start = ...
[INF] Cycle ...: 0 decode(s) found, elapsed=9 ms.
```

**Prerequisites installed in Debian WSL2:**

```bash
apt-get install -y alsa-utils pulseaudio-utils libasound2-plugins python3-pip python3-venv
```

**Python harness venv (Linux):**

```bash
cd qa/rr-study
python3 -m venv .venv-linux
source .venv-linux/bin/activate
pip install numpy scipy soundfile pandas matplotlib
python run_study.py --help   # AC-9 verified
```

**Deviations from the planned procedure:**

1. Distro is **Debian 13 (trixie)**, not Ubuntu 22.04. Behaviour is identical.
2. .NET SDK was **not** installed in WSL2. Instead, a native AOT binary is downloaded from
   CI (`daemon-linux-x64` artifact). No `dotnet build` or `dotnet run` step is needed.
3. The Microsoft .NET apt repository is unusable on Debian 13 (SHA1 signature rejected by
   Debian 13's security policy). The dotnet-install.sh approach was also bypassed in favour
   of the AOT binary.
4. `arecord --list-devices` returns no `hw:` devices in the default WSL2 Debian environment
   (ALSA HW interface not bridged by WSLg). Use `pulse` as the device ID, not a `hw:N,M` ID.
5. `pactl list sources short` shows only `RDPSink.monitor` and `RDPSource` — no VB-CABLE
   source entry. The loopback capture point is `RDPSink.monitor`; the daemon device ID
   remains `"pulse"` (PulseAudio routes to the default source).
6. **The audio path from the Windows loopback device to WSLg's `RDPSink.monitor` depends on
   the host audio configuration and must be verified on each machine.** WSLg bridges Windows
   audio rendering to PulseAudio; any audio that passes through the Windows audio rendering
   graph (whether via the system default device, a virtual mixer, or another routing path)
   will appear in `RDPSink.monitor`. The exact mechanism is host-specific.
   **Evidence from the development machine (validated 2026-06-30):** with VB-Audio Voicemeeter
   installed and CABLE Output configured as a Voicemeeter input channel, playing audio to
   `CABLE Input (VB-Audio Virtual Cable)` routed audio through the Windows audio graph to
   WSLg's RDP bridge and produced a successful decode in the Linux daemon at SNR +11 dB
   (AC-7). Voicemeeter is cited here only as the example configuration on the development
   machine; other host audio setups may differ.
   **Before each study run:** play one FT8 fixture to the loopback device and confirm the
   Linux daemon decodes it (per STUDY-SPEC-XPLAT.md §11 audio-chain verification step).
   If no decode arrives, verify that the loopback playback is audible in the Windows host's
   audio rendering graph — if it is not present there, WSLg cannot pick it up.

**AC verification results (all pass):**

| AC | Criterion | Result |
|---|---|---|
| AC-1 | WSL2 VERSION 2 Debian distro present | ✅ `Debian  Stopped  2` |
| AC-2 | `pactl info` connects | ✅ `Server String: unix:/mnt/wslg/PulseServer` |
| AC-3 | At least one `*.monitor` source | ✅ `RDPSink.monitor` |
| AC-4 | `arecord -D pulse` produces non-empty file | ✅ 144000 bytes in 3 s |
| AC-5 | `dotnet build` not applicable — AOT binary used | ✅ binary ELF verified |
| AC-6 | Daemon starts and logs ArecordAudioSource on `pulse` | ✅ 6 audio chunks, first cycle decoded |
| AC-7 | End-to-end FT8 decode from Windows playback | ✅ decode received at UTC 21:47:00 (2026-06-30): SNR +11 dB, DT 0.5 s, 1500 Hz — daemon log confirms `Cycle 21:47:00: 1 decode(s) found, elapsed=119 ms` |
| AC-8 | RUNBOOK.md §1.5 written | ✅ this section |
| AC-9 | `run_study.py --help` executes without error | ✅ confirmed |

---

## 2. Application settings for a run

| Setting | WSJT-X | OpenWSFZ |
|---|---|---|
| Mode | FT8 | FT8 receive pipeline |
| Monitor / decode | **Monitor ON** | Decode **started** |
| Audio input device | **CABLE Output** | **CABLE Output** |
| Logging | `ALL.TXT` location noted | `decodeLog.enabled = true` |
| Nominal dial freq | identical (e.g. 7.074 MHz) | identical (cosmetic — matcher keys on audio freq + message + cycle) |

Record, in the run's report header, the **WSJT-X version** and the **OpenWSFZ git SHA**
(`STUDY-SPEC.md` §11).

---

## 3. Running the study

> ⏳ The harness (synthesizer, generator driver, matcher, analysis) is not yet built — see
> `STUDY-SPEC.md` §12 and §15. This section will be completed as those components land. For now,
> the runbook covers the **audio-routing prerequisite** required before any run.

Planned procedure (subject to harness implementation):

1. Complete the VB-CABLE setup in §1 and the application settings in §2.
2. Run the synthesizer **self-validation gate** (`STUDY-SPEC.md` §5): WSJT-X must decode a clean
   (+10 dB) rendering of every message used, or the run aborts.
3. Execute the chosen scenario(s) from `STUDY-SPEC.md` §6 (S1–S6).
4. Regenerate the Minitab-style report from the raw `ALL.TXT` logs with the single analysis command
   (`STUDY-SPEC.md` §9, §11).

---

---

## 4. Running the S6 corpus replay study

S6 plays the local off-air WAV corpus through VB-CABLE K=3 times in randomised order and
measures within-appraiser consistency, between-appraiser agreement, SNR delta, and order effects.
See `STUDY-SPEC.md` §6.1 for full specification.

### 4.1 Pre-run checklist

- [ ] VB-CABLE configured per §1 and §2 of this runbook
- [ ] WSJT-X: FT8 mode, Monitor ON, audio input = CABLE Output
- [ ] OpenWSFZ: audio device = CABLE Output, decoding active, `decodeLog.enabled = true`
- [ ] Local corpus present at `p10-decoder-ground-truth_items/` (sibling of `qa/`) and contains 42 WAV files
- [ ] Python venv active (`qa/rr-study/.venv`) with `sounddevice`, `scipy`, `matplotlib`, `pandas` installed
- [ ] Both apps' ALL.TXT files cleared from any previous session (or note the last timestamp so the collector can filter)

### 4.2 Run command

From `qa/rr-study/`:

```
python harness/corpus_replay.py [--device "CABLE Input"] [--corpus ../p10-decoder-ground-truth_items] [--runs 3]
```

The harness will:
1. Play one silent warm-up cycle and prompt confirmation that both apps are decoding
2. Execute K=3 runs; within each run play 42 WAVs in randomised order, aligned to the UTC 15-second cycle boundary
3. After each WAV cycle wait 5 s for both decoders to settle, then snapshot the relevant ALL.TXT lines
4. Write raw snapshots to `results/corpus-<date>/raw/` (local only, git-ignored)
5. Write `results/corpus-<date>/run_manifest.json` recording WAV order, seeds, and timing

**Expected duration:** 42 WAVs × 3 runs × ~30 s per cycle ≈ **63 minutes** total. Each cycle costs ~30 s because the 5 s post-cycle settle pushes past the immediately following 15 s boundary, so the next available slot is always ~30 s after playback began.

### 4.3 Analysis

```
python harness/analyse_corpus.py --run-dir results/corpus-<date>
```

Produces in `results/corpus-<date>/`:

| File | Content | Committable? |
|---|---|---|
| `raw/` | ALL.TXT snapshots per WAV per run | **No** — real callsigns |
| `report.md` | Aggregate statistics, scrubbed | **Yes** |
| `summary.csv` | Per-WAV metrics, no message text | **Yes** |
| `consistency.png` | Within-appraiser consistency bar chart | **Yes** |
| `kappa.png` | Cohen's κ with 95% CI | **Yes** |
| `snr_delta.png` | SNR delta scatter (OpenWSFZ vs WSJT-X) | **Yes** |

### 4.4 Post-run scrub-and-commit step

The analysis script applies a callsign scrub pass before writing committed artifacts. Verify before committing:

```
# Confirm no real callsigns in committed artifacts
grep -rE "\b[A-Z]{1,2}[0-9][A-Z]{1,3}\b" results/corpus-<date>/report.md results/corpus-<date>/summary.csv
# Should return nothing (all callsigns replaced with [CALL])

git add qa/rr-study/results/corpus-<date>/report.md \
        qa/rr-study/results/corpus-<date>/summary.csv \
        qa/rr-study/results/corpus-<date>/*.png
git commit -m "qa(rr-study): record S6 corpus replay results — <date>"
```

---

## 5. Troubleshooting

| Symptom | Likely cause | Remedy |
|---|---|---|
| Endpoints absent after install | Driver install incomplete / no reboot | Re-run installer as admin; reboot. |
| Only one app shows input activity | Exclusive Mode enabled on *CABLE Output* | Untick both Exclusive-Mode boxes (§1.2). |
| Decodes are garbled / SNR is wildly off | Sample-rate mismatch / Windows resampling | Set both sides to 48000 Hz default format (§1.2). |
| Feedback / echo on monitors | *CABLE Output* "Listen to this device" enabled | Untick it (§1.2). |
| No audio reaches the apps | Media/harness output device ≠ *CABLE Input* | Point the player/harness at **CABLE Input**. |
