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

### 5.5 Known invariants and calibration offsets

These are expected, characterised differences between the two platforms — not defects:

| Measurement | Linux daemon | Windows daemon | Cause |
|---|---|---|---|
| **DT bias** | ≈ −1 s relative to Windows | Reference (≈ 0) | ft8loopback delivers audio earlier than the WSLg/Voicemeeter path; both within decoder ±2 s range |
| **SNR offset** | ≈ −18 dB relative to injected | Close to injected | Calibration difference in noise floor estimation between libft8.so and libft8.dll; primary R&R measurement |
| **Audio device** | `pulse` (PulseAudio, 48 kHz) | Voicemeeter Out B2 (WASAPI, 48 kHz) | Platform audio stack |
| **ft8 binary** | `libft8.so` linux-x64 | `libft8.dll` win-x64 | Same source, different compiler/OS |

---

## 6. Troubleshooting

| Symptom | Likely cause | Remedy |
|---|---|---|
| Endpoints absent after install | Driver install incomplete / no reboot | Re-run installer as admin; reboot. |
| Only one app shows input activity | Exclusive Mode enabled on *CABLE Output* | Untick both Exclusive-Mode boxes (§1.2). |
| Decodes are garbled / SNR is wildly off | Sample-rate mismatch / Windows resampling | Set both sides to 48000 Hz default format (§1.2). |
| Feedback / echo on monitors | *CABLE Output* "Listen to this device" enabled | Untick it (§1.2). |
| No audio reaches the apps | Media/harness output device ≠ *CABLE Input* | Point the player/harness at **CABLE Input**. |
