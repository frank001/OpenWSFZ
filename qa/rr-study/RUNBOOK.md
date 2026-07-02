# OpenWSFZ ↔ WSJT-X R&R Study — Operator Runbook

**Document type:** Operator setup & run procedure (QA deliverable)
**Companion to:** [`STUDY-SPEC.md`](./STUDY-SPEC.md)
**Status:** Living document — extended as harness components land
**Last updated:** 2026-07-01

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

### 1.5 Linux / WSL2 (validated 2026-06-30; audio routing revised 2026-07-01)

**Environment:**

| Item | Value |
|---|---|
| WSL2 distro | Debian GNU/Linux 13 (trixie) |
| WSL2 kernel | `6.6.87.2-microsoft-standard-WSL2` |
| WSL2 version | VERSION 2 (confirmed via `wsl --list --verbose`) |
| `arecord` version | 1.2.14 (from `alsa-utils` package) |
| .NET runtime | Shipped as AOT-compiled native binary (no SDK in WSL2) |

**Audio routing — revised 2026-07-01 (D3 amendment):**

The original design relied on the WSLg RDP bridge (`RDPSink.monitor`) to carry
Windows audio into WSL2. This proved host-configuration-dependent and unreliable.
The revised approach uses a **PulseAudio null-sink** inside WSL2: the Python
synthesizer plays directly into the null-sink, and the daemon captures from its
monitor source. This is fully self-contained within WSL2 and requires no WSLg bridge.

See STUDY-SPEC-XPLAT.md §3 for the formal D3 amendment and its statistical implications.

**PulseAudio audio routing setup (WSL2) — revised 2026-07-01:**

The synthesizer plays to a **combined sink** (`ft8combined`) that simultaneously
delivers audio to two slaves:

| Slave | Purpose |
|---|---|
| `ft8loopback` (null-sink) | Linux daemon captures from `ft8loopback.monitor` |
| `RDPSink` (WSLg bridge) | Windows receives audio → Voicemeeter AUX Input → B2 → Windows daemon |

```bash
# Step 1: Create null-sink (not persistent — re-run after WSL2 restart)
pactl load-module module-null-sink \
    sink_name=ft8loopback \
    sink_properties=device.description=FT8Loopback

# Step 2: Create combined sink (ft8loopback + RDPSink)
pactl load-module module-combine-sink \
    sink_name=ft8combined \
    sink_properties=device.description=FT8Combined \
    slaves=ft8loopback,RDPSink

# Step 3: Set combined sink as default output (synth plays here)
pactl set-default-sink ft8combined

# Step 4: Set monitor source for Linux daemon capture
pactl set-default-source ft8loopback.monitor

# Verify
pactl info | grep -E "Default Sink|Default Source"
# Expected:
#   Default Sink: ft8combined
#   Default Source: ft8loopback.monitor

pactl list sinks short
# Expected: RDPSink, ft8loopback, ft8combined — all present
```

The `start-daemon.sh` script handles `ft8loopback` creation and source selection
automatically. The `ft8combined` sink must be created manually (it depends on
`RDPSink` which is only available after WSLg initialises).

**Additional packages required (added 2026-07-01):**

```bash
sudo apt-get install -y libportaudio2
```

In `.venv-linux` (Python harness):
```bash
pip install sounddevice
```

`sounddevice` is needed for the synthesizer to play into the PulseAudio null-sink.

**PulseAudio sources present in WSL2 (for reference):**

| Source | Module | Format | Role |
|---|---|---|---|
| `ft8loopback.monitor` | `module-null-sink.c` | s16le 2ch 48000Hz | **Use this** — synth plays here; daemon captures from here |
| `RDPSink.monitor` | `module-rdp-sink.c` | s16le 2ch 44100Hz | Windows audio bridge (no longer used for R&R) |
| `RDPSource` | `module-rdp-source.c` | s16le 1ch 44100Hz | Microphone input (not used) |

**Daemon audio device configuration:**

The daemon's audio device is set via the JSON config file at `~/.config/OpenWSFZ/config.json`.
Set `audioDeviceId` to `"pulse"` to route through PulseAudio:

```json
{
  "audioDeviceId": "pulse",
  "decodeLog": { "enabled": true }
}
```

The daemon selects the PulseAudio default source when `pulse` is specified.
After running `start-daemon.sh`, the default source is `ft8loopback.monitor`.

> ⚠️ **D-LINUX-001 (open):** The settings UI sends `audioDeviceId: null` when the
> device list is empty (Linux has no device enumeration). Saving ANY setting via the
> browser UI will wipe `audioDeviceId`. **Do not save Audio/General settings via the UI
> on the Linux daemon.** If wiped, restore with:
> ```bash
> curl -s -X POST http://127.0.0.1:8888/api/v1/config \
>   -H "Content-Type: application/json" \
>   -d '{"audioDeviceId":"pulse", ...full config...}'
> ```
> See `dev-tasks/2026-07-01-d-linux-001-settings-wipe-audio-device.md`.

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
5. **Audio injection method — revised 2026-07-01 (supersedes deviation 5 and 6 from
   original write-up):** The WSLg RDP bridge (`RDPSink.monitor`) was found to be
   host-configuration-dependent and unreliable for study-grade signal injection. The
   revised approach uses a **PulseAudio null-sink** (`ft8loopback`) created inside WSL2.
   The Python synthesizer runs in WSL2 and plays directly into the null-sink; the daemon
   captures from `ft8loopback.monitor`. This is self-contained and requires no Windows audio
   routing. The original WSLg bridge approach (AC-7) remains valid as an existence proof
   that the Linux audio chain works end-to-end, but is not used for production R&R runs.
   This change amends Decision D3 in STUDY-SPEC-XPLAT.md — see that document for the
   statistical implications.
6. `sounddevice` and `libportaudio2` added to the WSL2 environment (2026-07-01) to support
   synthesizer playback into PulseAudio from within WSL2.

**AC verification results:**

| AC | Criterion | Result |
|---|---|---|
| AC-1 | WSL2 VERSION 2 Debian distro present | ✅ `Debian  Stopped  2` |
| AC-2 | `pactl info` connects | ✅ `Server String: unix:/mnt/wslg/PulseServer` |
| AC-3 | At least one `*.monitor` source | ✅ `ft8loopback.monitor` (null-sink, revised); `RDPSink.monitor` also present |
| AC-4 | `arecord -D pulse` produces non-empty file | ✅ 144000 bytes in 3 s |
| AC-5 | `dotnet build` not applicable — AOT binary used | ✅ binary ELF verified |
| AC-6 | Daemon starts and logs ArecordAudioSource on `pulse` | ✅ confirmed |
| AC-7 | End-to-end FT8 decode from Windows playback (WSLg bridge) | ✅ UTC 21:47:00 (2026-06-30): SNR +11 dB, DT 0.5 s, 1500 Hz |
| AC-8 | RUNBOOK.md §1.5 written | ✅ this section |
| AC-9 | `run_study.py --help` executes without error | ✅ confirmed |
| AC-10 | End-to-end FT8 decode via null-sink (synthesizer in WSL2, Linux daemon only) | ✅ UTC 17:01:15/30/45 (2026-07-01): 3/3 cycles decoded — `CQ Q1ABC FN42`, SNR −7/−8 dB, DT −0.8 s, 1500 Hz. `smoke_test_null_sink.py` PASSED. |
| AC-11 | Both daemons decode simultaneously via `ft8combined` sink (WSL2 synth → ft8loopback.monitor + RDPSink → Voicemeeter AUX → B2) | ✅ UTC 17:38:00/15/30 (2026-07-01): Linux 3/3 (`CQ Q1ABC FN42`, SNR −8/−9 dB, DT −0.7 to −1.2 s), Windows 3/3 (SNR +9/+10 dB, DT +0.1 to +0.3 s). `smoke_test_null_sink.py` PASSED on both. DT bias Linux vs Windows ≈ −1 s (inherent to dual-path routing). SNR offset ≈ 18 dB (calibration difference — primary R&R measurement). |

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

## 5. Cross-platform R&R procedure (Windows vs Linux/WSL2)

Complete, repeatable procedure for running `run_study_xplat.py`. All steps were
validated on 2026-07-01 (AC-7 through AC-11). Repeat this section in full at the
start of every cross-platform study session.

### 5.1 One-time prerequisites (do once per machine, not per session)

These steps survive reboots and WSL2 restarts — do them once.

**Windows side:**

1. Install **Voicemeeter** (Potato or Banana) from <https://vb-audio.com/Voicemeeter/>.
2. In Voicemeeter, route **Voicemeeter AUX Input (VAIO2)** to **B2** output bus:
   - Open Voicemeeter → find the "VAIO2" virtual input strip
   - Enable the **B2** button on that strip (it lights up)
3. Start **OpenWSFZ.Daemon** (Windows) and configure its audio capture device to
   **Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)**:
   - `POST http://127.0.0.1:8080/api/v1/config` with the full config JSON, setting
     `"audioDeviceFriendlyName": "Voicemeeter Out B2 ..."` and the matching
     `"audioDeviceId"` GUID, or use the Settings UI on Windows where the device
     dropdown is populated.

**WSL2 side (Debian):**

4. Install required system packages (once per WSL2 distro):
   ```bash
   sudo apt-get install -y alsa-utils pulseaudio-utils libasound2-plugins \
                           libportaudio2 python3-pip python3-venv
   ```
5. Create the Python venv and install harness dependencies:
   ```bash
   cd /mnt/d/Projects/claude/OpenWSFZ/qa/rr-study
   python3 -m venv .venv-linux
   source .venv-linux/bin/activate
   pip install numpy scipy soundfile sounddevice pandas matplotlib
   ```
6. Ensure the Linux daemon binary and `libft8.so` are in `qa/rr-study/linux-daemon/`:
   ```bash
   ls qa/rr-study/linux-daemon/OpenWSFZ.Daemon   # must exist and be executable
   ls qa/rr-study/linux-daemon/libft8.so          # must exist
   chmod +x qa/rr-study/linux-daemon/OpenWSFZ.Daemon
   ```
   Download from GitHub CI artifact `daemon-linux-x64` if not present.

---

### 5.2 Per-session setup (every time WSL2 restarts)

PulseAudio modules are not persistent across WSL2 restarts. Run these steps at
the start of every study session, before launching daemons or the harness.

**Step 1 — Start the Linux daemon (sets up audio routing automatically):**

```bash
# In a WSL2 terminal — keep this window open for the duration of the session
bash /mnt/d/Projects/claude/OpenWSFZ/qa/rr-study/linux-daemon/start-daemon.sh
```

`start-daemon.sh` does the following automatically:
- Creates `ft8loopback` null-sink (if absent)
- Creates `ft8combined` combine-sink (`ft8loopback` + `RDPSink`)
- Sets default sink → `ft8combined` (synthesiser plays here)
- Sets default source → `ft8loopback.monitor` (Linux daemon captures here)
- Launches `OpenWSFZ.Daemon` (logs to `linux-daemon.log`)

> ⚠️ `ft8combined` depends on `RDPSink`, which WSLg creates during GUI session
> initialisation. If `start-daemon.sh` fails with "No such entity" for `RDPSink`,
> wait 10–15 seconds for WSLg to fully initialise, then retry.

**Step 2 — Verify audio routing:**

```bash
# In a second WSL2 terminal:
pactl info | grep -E "Default Sink:|Default Source:"
# Expected:
#   Default Sink: ft8combined
#   Default Source: ft8loopback.monitor

pactl list sinks short
# Expected: RDPSink, ft8loopback, ft8combined — all present and not FAILED
```

**Step 3 — Verify Windows daemon is running and on the correct device:**

```powershell
# In a Windows terminal:
curl http://127.0.0.1:8080/api/v1/status
# Expected: "state":"Running", "captureActive":true
# "audioDevice" must contain "Voicemeeter Out B2"
```

> ⚠️ **D-LINUX-001 (open):** Do NOT save any settings via the Linux daemon
> browser UI at `http://127.0.0.1:8888`. The empty device dropdown will overwrite
> `audioDeviceId` to `null`, silencing the daemon. Configure only via curl/POST.
> If accidentally wiped, restore with:
> ```bash
> curl -s -X POST http://127.0.0.1:8888/api/v1/config \
>   -H "Content-Type: application/json" \
>   -d '{"audioDeviceId":"pulse","decodeLog":{"enabled":true,"path":"/mnt/d/Projects/claude/OpenWSFZ/linux-all.txt"}}'
> ```

**Step 4 — Confirm shim versions match:**

```bash
curl -s http://127.0.0.1:8080/api/v1/status | python3 -c "import sys,json; print('WIN shim:', json.load(sys.stdin).get('shimVersion','?'))"
curl -s http://127.0.0.1:8888/api/v1/status | python3 -c "import sys,json; print('LIN shim:', json.load(sys.stdin).get('shimVersion','?'))"
# Both must report the same shimVersion number
```

**Step 5 — Run the dual-daemon smoke test:**

```bash
# In WSL2 (inside .venv-linux):
cd /mnt/d/Projects/claude/OpenWSFZ/qa/rr-study
source .venv-linux/bin/activate
python smoke_test_null_sink.py
```

Expected output:
```
─── Linux daemon (ft8loopback.monitor) ──────────────────────────────
  ✅  N decode(s) total in log (last 3):
     ...CQ Q1ABC FN42...

─── Windows daemon (Voicemeeter AUX → B2) ───────────────────────────
  ✅  N decode(s) total in log (last 3):
     ...CQ Q1ABC FN42...

Smoke test PASSED — both daemons received the signal.
```

If either side fails, do not proceed. See §6 Troubleshooting.

---

### 5.3 Running the study

From a **Windows** terminal (not WSL2), with both daemons running and the smoke
test passed:

```powershell
cd D:\Projects\claude\OpenWSFZ\qa\rr-study

# Full run — all scenarios (S1, S1b, S2, S3, S4, S5, S7):
.\.venv\Scripts\python.exe run_study_xplat.py

# Single scenario (quick validation):
.\.venv\Scripts\python.exe run_study_xplat.py --scenarios S1

# Specific parts of a scenario:
.\.venv\Scripts\python.exe run_study_xplat.py --scenarios S1 --parts 0,1,2

# Skip the interactive pre-flight prompt (if you've already confirmed manually):
.\.venv\Scripts\python.exe run_study_xplat.py --skip-warmup
```

**What the harness does:**
1. Creates a versioned run directory under `results/<YYYY-MM-DD>-<git-sha7>/`
2. For each scenario, launches `run_scenario.py` inside WSL2 via `wsl -e bash -c`
3. The WSL2 synthesiser renders FT8 signals, waits for the next UTC 15-second cycle
   boundary, and plays them to `ft8combined` — which delivers to both daemons
4. After all scenarios complete, copies both `ALL.TXT` files into the run directory
5. Runs `harness/matcher_xplat.py` per scenario to align decode events with truth
6. Runs `harness/analyse_xplat.py` to produce `report.md`

**Expected duration** (full run, default trial counts):
| Scenario | Parts × trials | Time |
|---|---|---|
| S1 | 10 × 3 = 30 cycles | ~7.5 min |
| S1b | 4 × 3 = 12 cycles | ~3 min |
| S2 | varies | ~varies |
| S3 | varies | ~varies |
| S4 | varies | ~varies |
| S5 | varies | ~varies |
| S7 | varies | ~varies |
| **Total** | | **~45–90 min** |

---

### 5.4 Post-run: complete the report

The harness generates Sections 2 (mechanical fields), 3 (results), and 4 (verdict
table) of `report.md` automatically. **The QA engineer must complete:**

1. **Section 1 — Study hypothesis:** What is this run testing? Null hypotheses?
   Defect IDs under observation? What constitutes a meaningful result?

2. **Section 5 — Recommendations:** For each FAIL or MARGINAL metric, state the
   defect ID, hypothesis, and next diagnostic step.

3. **Render HTML:**
   ```powershell
   python qa/rr-study/render_report.py <path/to/report.md>
   ```

4. **Commit the result directory:**
   ```bash
   git add qa/rr-study/results/<run-dir>/
   git commit -m "qa(rr-study): cross-platform R&R run <date> — <brief finding>"
   ```

> A `report.md` committed without Sections 1 and 5 is a merge-blocking defect
> (NFR-024). See MEMORY.md HK-001.

---

### 5.5 Known invariants — pilot study (2026-07-01, pre-normalization)

Recorded from the D3 pilot run. These are measurement-system characteristics,
not decoder defects. The target state after §5.6 normalization is shown alongside.

| Measurement | Pilot (pre-normalization) | Target (post-normalization) | Root cause |
|---|---|---|---|
| **SNR offset Linux vs Windows** | ≈ −18 dB | ≤ ±2 dB | Voicemeeter B2 path gain ~18 dB below ft8loopback; fix by Voicemeeter gain adjustment |
| **Freq offset Linux vs Windows** | ≈ −10 to −16 Hz at 1500 Hz | ≤ ±2 Hz | PulseAudio server running at 44100 Hz; fix by setting 48000 Hz |
| **DT bias Linux vs Windows** | ≈ −1 s | < 0.5 s (routing latency; hard to eliminate) | ft8loopback delivers audio earlier than WSLg/Voicemeeter path |
| **Audio device — Linux** | `pulse` (ft8loopback.monitor) | unchanged | PulseAudio null-sink |
| **Audio device — Windows / WSJT-X** | Voicemeeter Out B2 | unchanged (shared WASAPI) | Both appraisers capture same B2 device |
| **ft8 binary** | `libft8.so` linux-x64 / `libft8.dll` win-x64 | unchanged | Same kgoba/ft8_lib source, different compiler |

---

### 5.6 Audio path normalization — three-appraiser design

This section describes how to normalize the measurement system before running the
three-appraiser study (Windows daemon + Linux daemon + WSJT-X). Complete §5.6.1
and §5.6.2 once (settings persist); verify §5.6.3 at the start of each session.

---

#### 5.6.1 Fix PulseAudio sample rate (WSL2, one-time)

The pilot study showed a ~10–16 Hz frequency offset on the Linux path, caused by
PulseAudio running at 44100 Hz while the synthesiser and Windows use 48000 Hz.

**Resolution (applied 2026-07-02):** `start-daemon.sh` now passes `rate=48000`
explicitly when creating the `ft8loopback` null-sink. This is the definitive fix:
the null-sink rate is set at creation time, independently of the PulseAudio server
default, so the fix survives WSL2 restarts without touching PulseAudio config.

> **Note on daemon.conf approach (attempted, abandoned 2026-07-02):** WSLg owns
> the PulseAudio process on Debian 13 — the `pulseaudio` binary is not available
> in the user PATH, so `pulseaudio -k` fails. `~/.config/pulse/daemon.conf` is
> not picked up without a PulseAudio restart. `/etc/pulse/daemon.conf` requires
> `sudo` and an interactive terminal. None of these paths are viable in a running
> session. The `start-daemon.sh` `rate=48000` approach supersedes them all.

**Verification:** after running `start-daemon.sh`, confirm:

```bash
pactl list sinks short | grep ft8loopback
# Must show: ft8loopback  module-null-sink.c  s16le 2ch 48000Hz
```

The PulseAudio server itself may still report 44100 Hz via `pactl info`; that is
harmless as long as the null-sink is explicitly at 48000 Hz.

---

#### 5.6.2 Voicemeeter gain equalization (Windows, one-time + verify)

The pilot showed ~18 dB gain deficit on the Windows/Voicemeeter path relative to
the direct ft8loopback path. Both WSJT-X and the Windows daemon receive audio via
Voicemeeter Out B2, so adjusting B2 gain brings both Windows appraisers into line
with Linux simultaneously.

**Calibration procedure:**

1. Ensure all three appraisers are running (Linux daemon, Windows daemon, WSJT-X).
2. Ensure PulseAudio sample rate is 48000 Hz (§5.6.1).
3. Inject a single-tone FT8 signal at **0 dB true SNR** at 1500 Hz for 10 trials
   using the smoke-test script or a manual run of `run_scenario.py --parts 5 --trials 10`
   against the S1 scenario (part 5 is approximately 0 dB SNR).
4. After the injection window, check the reported SNR from each appraiser:
   - Linux daemon: browser UI or `linux-all.txt` (last 10 entries)
   - Windows daemon: `ALL.TXT` (last 10 entries)
   - WSJT-X: `C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT` (last 10 entries)
5. **Compare the three SNR values.** The target is all three within **±2 dB** of
   each other.
6. **If Windows/WSJT-X SNR < Linux SNR by more than 2 dB:**
   Open Voicemeeter → find the **VAIO2** (Voicemeeter AUX Input) strip →
   increase the strip **fader gain** (dB slider) by approximately half the
   observed gap. Repeat from step 3.
7. **If Windows/WSJT-X SNR > Linux SNR by more than 2 dB:**
   Reduce the VAIO2 strip fader or the B2 bus output level.
8. Record the final Voicemeeter VAIO2 fader position in §5.5 once stable.

> One click of the Voicemeeter fader ≈ 1 dB. The pilot showed ~18 dB deficit
> so expect to move the fader significantly upward from its default position.
>
> Check that the gain change does not clip (Voicemeeter meters should stay
> below 0 dBFS during injection). Use a lower injection amplitude if clipping
> occurs, then scale the comparison accordingly.

---

#### 5.6.3 WSJT-X per-session setup

WSJT-X must be running and configured before starting any three-appraiser study
session.

**One-time WSJT-X configuration (first run only):**

1. Open WSJT-X → File → Settings → Audio tab:
   - **Input:** `Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)` — same device
     as the Windows daemon.
   - **Output:** any device (WSJT-X output is not used during the R&R study).
2. Settings → General tab:
   - Set **Mode** to `FT8`.
   - Leave **Auto Seq** unchecked (receive-only).
   - **My Call:** use own callsign `PD2FZ` (or any valid call — appears in log but
     WSJT-X does not transmit during the study).
3. Settings → Reporting tab:
   - Confirm **Log file:** uses the default location
     (`C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`) or note the actual path.
4. Click **OK** and let WSJT-X begin receiving.

**Per-session checklist:**

```
☐ WSJT-X is open and showing "Receiving" status
☐ WSJT-X Input = Voicemeeter Out B2
☐ WSJT-X is decoding (rows appearing in its decode panel) — confirmed by smoke test
☐ ALL.TXT exists at C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT
```

**Verify WSJT-X is receiving (add to smoke test after §5.2 Step 5):**

After running `smoke_test_null_sink.py`, also confirm:
```powershell
# Check WSJT-X ALL.TXT was updated within the last 5 minutes
(Get-Item "C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT").LastWriteTime
# Should be recent if WSJT-X is running and receiving
```

> The updated `smoke_test_null_sink.py` (pending developer handoff
> `dev-tasks/2026-07-01-xplat-three-appraiser-harness.md`) will add WSJT-X
> as a third check automatically.

---

#### 5.6.4 Verification: all three appraisers calibrated

Before starting a formal study run after normalization, confirm:

```
☐ pactl info | grep "Default Sample" → 48000 Hz
☐ Voicemeeter VAIO2 fader set to calibrated position
☐ Smoke test PASSED for Linux daemon
☐ Smoke test PASSED for Windows daemon
☐ WSJT-X ALL.TXT shows recent decodes matching the smoke test signal
☐ Reported SNR across all three appraisers within ±2 dB of each other
☐ Reported frequency across all three appraisers within ±2 Hz of 1500 Hz
```

Only when all six items are checked should a formal R&R run be started.

---

## 6. Troubleshooting

| Symptom | Likely cause | Remedy |
|---|---|---|
| Endpoints absent after install | Driver install incomplete / no reboot | Re-run installer as admin; reboot. |
| Only one app shows input activity | Exclusive Mode enabled on *CABLE Output* | Untick both Exclusive-Mode boxes (§1.2). |
| Decodes are garbled / SNR is wildly off | Sample-rate mismatch / Windows resampling | Set both sides to 48000 Hz default format (§1.2). |
| Feedback / echo on monitors | *CABLE Output* "Listen to this device" enabled | Untick it (§1.2). |
| No audio reaches the apps | Media/harness output device ≠ *CABLE Input* | Point the player/harness at **CABLE Input**. |

---

## 7. WSL2 cross-platform R&R — closure note (2026-07-02)

### 7.1 Decision

**The WSL2-based three-appraiser cross-platform R&R study is suspended indefinitely.**
Production R&R runs against the Linux daemon using this approach are not feasible in
the current configuration. The infrastructure brought-up work (AC-1 through AC-11) is
preserved as a validated starting point should the approach be revisited.

### 7.2 Root causes of abandonment

The study design requires both the Linux daemon and the Windows appraisers (Windows
daemon + WSJT-X) to receive the *same signal at the same amplitude*. The dual-path
architecture — WSL2 null-sink for Linux, Voicemeeter B2 for Windows — introduces
structural measurement-system errors that cannot be eliminated without equipment changes:

| Issue | Magnitude | Nature | Mitigated? |
|---|---|---|---|
| **SNR offset** — ft8loopback delivers signal ~18 dB louder than Voicemeeter B2 path | ~18 dB | Systematic; all Windows appraisers vs Linux | No — §5.6.2 calibration not completed |
| **DT bias** — ft8loopback delivers audio ~1 s earlier than WSLg/Voicemeeter path | ~−1 s | Systematic; affects timing comparison | Inherent to dual-path routing; not eliminable |
| **Voicemeeter gain calibration** (§5.6.2) — iterative fader adjustment required each session | N/A | Host-session-dependent; fragile | Procedure written; not practical for repeatable runs |
| **PulseAudio server rate** — WSLg daemon runs at 44100 Hz; null-sink forced to 48000 Hz by `start-daemon.sh` | ~10–16 Hz freq offset | Fixed at null-sink; server mismatch persists | Partially — null-sink fix applied (§5.6.1) |
| **WSLg RDP bridge** (original D3 design) — `RDPSink.monitor` reliability is host-config-dependent | N/A | Superseded by null-sink approach | Superseded; not used for production runs |

The `2026-06-30-b03998f` run directory represents the last formal attempt: the harness
was started, the truth CSV was generated, and the run was aborted without capturing
decode results due to the gain offset making meaningful SNR comparison impossible.

### 7.3 What was accomplished

The infrastructure brought-up work is a genuine and reusable result:

- **AC-1 through AC-11** — all verified (see §1.5). The Linux daemon runs correctly
  inside WSL2 Debian 13, captures from `ft8loopback.monitor`, and decodes synthetic
  FT8 at the expected SNR.
- **End-to-end decode chain** — confirmed (AC-10, 2026-07-01): synthesiser in WSL2
  plays to null-sink; Linux daemon decodes 3/3 cycles at −7/−8 dB SNR.
- **Dual-path smoke test** — confirmed (AC-11, 2026-07-01): both Linux and Windows
  daemons decode the same synthetic signal simultaneously via the combined sink.
- **PulseAudio null-sink approach** — validated as a clean, self-contained audio
  injection method. Supersedes the fragile WSLg bridge original design.
- **`start-daemon.sh`** — automates null-sink creation at 48000 Hz; handles daemon
  launch; documented `D-LINUX-001` (audio-device wipe via settings UI).
- **Diagnostic tooling** — eight diagnostic scripts committed to `qa/rr-study/`:
  `diag_null_sink_rms.py`, `diag_format_check.py`, `diag_wav_check.py`,
  `diag_aplay_native.py`, `verify_audio_chain.py`, `verify_loopback.py`,
  `verify_wasapi.py`, `check_hostapi.py`, `check_rdp_rms.py`, `list_devices.py`.

### 7.4 Gentoo path forward (provisional)

A dedicated Gentoo Linux machine (headless, with real audio hardware) offers a
potentially cleaner path to Linux daemon R&R:

**Advantages over WSL2:**

- Real audio hardware — no virtual audio cable, no Voicemeeter, no dual-path routing
- Single-path null-sink: synthesiser → PulseAudio null-sink → daemon captures from
  `.monitor` → WSJT-X (if available) captures from the same `.monitor`
- No WSLg, no RDPSink, no 18 dB gain offset problem
- Native Linux (not WSL2) — no WSLg PulseAudio ownership issues
- PulseAudio daemon.conf is user-controllable (no WSLg override)

**Constraints to resolve before pursuing:**

1. **WSJT-X on headless Linux** — requires Xvfb + VNC or X11 forwarding, or the
   study reverts to a single-appraiser design (Linux daemon vs synthesiser oracle only).
2. **SSH + audio forwarding** — the synthesiser harness must run on the Gentoo machine
   (or PulseAudio TCP socket / SSH tunnel used to inject audio remotely).
3. **Shim version alignment** — Linux `libft8.so` must match the committed shim version
   before any run.

**Single-appraiser alternative (no WSJT-X required):** Run S1–S8 scenarios on the
Gentoo daemon only, comparing against the synthesiser ground truth. This gives a valid
decode-rate vs SNR curve for the Linux daemon without requiring a second appraiser.
The Windows vs Linux comparison is deferred to a separate study where both machines
run the same scenario sequentially with the same seeded corpus (sequential design,
not concurrent — statistical power is lower but the measurement is valid).

### 7.5 Noise-floor false positive note (NFR-021 implication)

S5 (pure noise, no signal) and S7 (high scene complexity) scenarios produce noise-floor
false positive decodes. At −25 to −30 dB SNR, the FT8 CRC (14 bits) occasionally
passes for random bit patterns, producing decoded strings that match the format of
real amateur callsigns. These are **not real transmissions** — they are coincidental
CRC matches in AWGN — but the resulting strings are indistinguishable from real
third-party callsigns and constitute personal data under NFR-021.

**Rule:** `owsfz-all.txt` and `wsjt-all.txt` files from S5/S7/noise-floor scenarios
**must be reviewed before committing**. If any line contains a callsign that is not a
synthetic Q-prefix call, the file must either be scrubbed or left untracked. The
committed result files in this repository have been reviewed; the `diag-nhard-2026-06-20`
and `diag-pass1-sweep-2026-06-21` owsfz-all.txt files were **not committed** for this
reason.
