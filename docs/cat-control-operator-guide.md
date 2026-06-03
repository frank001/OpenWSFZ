# CAT Rig Control — Operator Guide

**Applies to:** OpenWSFZ v0.16+  
**Feature:** FR-031 – FR-034 (CAT frequency polling)

---

## What CAT Control Does

CAT (Computer-Aided Transceiver) control lets OpenWSFZ query your rig's
current VFO-A frequency once per second (configurable) and use that live
value in:

- The status bar at the top of the main page
- Every ALL.TXT decode log line

Without CAT you must set `decodeLog.dialFrequencyMHz` manually.  
With CAT that field becomes a fallback — only used when the rig is
disconnected or the daemon first starts.

**What CAT does NOT do in this version:** It never sends frequency-set,
mode-set, or PTT commands. The rig cannot be disturbed.

---

## Two Transport Modes

### SerialCat — Direct Serial Port

OpenWSFZ opens the serial port directly and sends `FA;` to query VFO-A.

| Advantage | Limitation |
|---|---|
| No external software required | Holds the port exclusively — WSJT-X cannot share it simultaneously |
| Works on any OS with a serial port | Will fail with a permission error if another application already holds the port |

### RigCtld — TCP to rigctld Daemon

OpenWSFZ connects to a running `rigctld` process (part of Hamlib) over TCP
and sends `\get_freq` to query VFO-A.

| Advantage | Limitation |
|---|---|
| `rigctld` holds the serial port and serves multiple clients simultaneously — run WSJT-X and OpenWSFZ side by side | You must start `rigctld` yourself before enabling this mode |
| Covers 850+ rigs via Hamlib's driver library | Requires Hamlib to be installed |

---

## Configuration

Open **Settings → CAT rig connection**.

| Field | Description | Default |
|---|---|---|
| Enable CAT frequency polling | Master on/off switch | Off |
| Rig transport | `SerialCat` or `RigCtld` | SerialCat |
| Serial port | OS port name (`COM6`, `/dev/ttyUSB0`, `/dev/cu.usbserial`) | Platform default |
| Baud rate | Must match rig firmware setting | 9600 |
| rigctld host | Hostname or IP of running `rigctld` | 127.0.0.1 |
| rigctld port | TCP port of running `rigctld` | 4532 |
| Poll interval (seconds) | How often to query the rig (1–60 s) | 1 |

Click **Save** after any change. The daemon applies changes within two poll
intervals without requiring a restart.

---

## Quick-Start: SerialCat Mode

1. Connect your rig to the computer via USB or serial cable.
2. In Settings, set **Rig transport** → `SerialCat`.
3. Set **Serial port** to the correct port name (e.g. `COM6` on Windows).
4. Set **Baud rate** to match the rig's CAT baud rate (check the rig menu;
   common values are `9600` and `4800`).
5. Check **Enable CAT frequency polling**.
6. Click **Save**.
7. Watch the status bar — the frequency should update within two seconds.

> **If WSJT-X is running:** Close its CAT connection (or close WSJT-X)
> before enabling SerialCat mode. Both applications cannot share a serial
> port at the same time. Use RigCtld mode if you need both running
> simultaneously.

---

## Quick-Start: RigCtld Mode

### Step 1 — Install Hamlib (if not already installed)

- **Windows:** Download the Hamlib release from
  <https://github.com/Hamlib/Hamlib/releases> and extract it. Add the `bin`
  folder to your `PATH`.
- **Linux:** `sudo apt install libhamlib-utils` (Debian/Ubuntu) or your
  distro's equivalent.
- **macOS:** `brew install hamlib`

### Step 2 — Find your rig's Hamlib model number

```
rigctl --list
```

Look for your rig manufacturer and model. Note the numeric model ID.

Example output (excerpt):
```
  3021  Elecraft K3/K3S
  3043  Elecraft KX3
  2040  Icom IC-7300
```

### Step 3 — Start rigctld

```
rigctld -m <model-id> -r <serial-port> -s <baud-rate>
```

Example for an Icom IC-7300 on COM6 at 19200 baud:
```
rigctld -m 3073 -r COM6 -s 19200
```

Leave this terminal window open — `rigctld` must stay running while
OpenWSFZ (or WSJT-X) is connected to it.

### Step 4 — Configure OpenWSFZ

1. In Settings, set **Rig transport** → `RigCtld`.
2. Leave **rigctld host** as `127.0.0.1` (unless rigctld is on another machine).
3. Leave **rigctld port** as `4532` (unless you started rigctld on a different port).
4. Check **Enable CAT frequency polling**.
5. Click **Save**.

---

## Understanding the Status Bar

| Display | Meaning |
|---|---|
| `14.074 MHz` (no badge) | CAT disabled; showing configured `decodeLog.dialFrequencyMHz` value |
| `14.074 MHz` + green **Connected** badge | CAT active and polling successfully |
| `14.074 MHz` + red/amber **Error** badge | CAT enabled but connection failed; daemon is retrying automatically |
| `0.000 MHz` (no badge) | CAT disabled and `decodeLog.dialFrequencyMHz` is not configured |

---

## Troubleshooting

### "CAT: failed to connect via RigCtld — No connection could be made"

**Cause:** `rigctld` is not running, or it is listening on a different host/port
than configured.

**Fix:**
1. Start `rigctld` as described in the Quick-Start above.
2. Confirm it is listening: on Windows run `netstat -an | findstr 4532`;
   on Linux/macOS run `ss -tnlp | grep 4532` or `lsof -i :4532`.
3. If you started `rigctld` on a non-standard port, update **rigctld port** in Settings.

The daemon retries every 2 seconds automatically. Once `rigctld` is
reachable the **Error** badge will clear and the badge will turn green.

> **Note:** If you do not intend to use CAT right now, uncheck
> **Enable CAT frequency polling** and click Save. This stops all retry
> attempts immediately.

### "CAT: failed to connect via RigCtld — Connection refused" (but rigctld IS running)

**Cause:** Firewall, wrong port, or rigctld started on a different interface.

**Fix:**
- Confirm the port matches: `rigctld` defaults to `4532`. If you passed
  `-t <port>`, update the **rigctld port** field in Settings.
- On Linux, check that no firewall rule is blocking loopback traffic on
  that port.

### "CAT: failed to connect via SerialCat — Access to the port is denied" (Windows)

**Cause:** Another application (WSJT-X, a terminal emulator, a previous
daemon instance) has the serial port open.

**Fix:**
- Close the other application, or switch to RigCtld mode so both can
  share `rigctld` simultaneously.
- Ensure no stale daemon process is running in the background.

### "CAT: failed to connect via SerialCat — The port does not exist"

**Cause:** The configured serial port name is wrong, or the USB cable is
unplugged.

**Fix:**
- Reconnect the USB cable; check Device Manager (Windows) or
  `ls /dev/tty*` (Linux/macOS) to confirm the port name.
- Update the **Serial port** field in Settings to match.

### Serial CAT connects but frequency reads as `0.000` or a wrong value

**Cause:** Baud rate mismatch. The rig returned a garbled or empty response.

**Fix:**
- Check the rig's CAT baud rate in its menu system and set the same value
  in **Baud rate** in Settings.
- Common values: 9600, 19200, 38400. Check the rig's operating manual.

### rigctld connects but returns the wrong frequency

**Cause:** Wrong Hamlib model ID — `rigctld` connected to the port but is
using the wrong driver protocol.

**Fix:**
- Run `rigctl --list` again and double-check the model number for your
  exact rig variant (e.g. IC-7300 vs IC-7300 (newer firmware) may have
  different IDs).
- Re-start `rigctld` with the correct `-m` value.

---

## Disabling CAT

If you do not have a compatible rig, or you simply want to stop the retry
messages in the log:

1. Open Settings → CAT rig connection.
2. Uncheck **Enable CAT frequency polling**.
3. Click **Save**.

The daemon will stop all connection attempts immediately and the status
bar will revert to the manually configured `decodeLog.dialFrequencyMHz`
value.

---

## Running rigctld as a Background Service (optional)

If you want `rigctld` to start automatically with Windows:

```bat
sc create rigctld binPath= "C:\hamlib\bin\rigctld.exe -m <id> -r COM6 -s 9600" start= auto
sc start rigctld
```

On Linux with systemd, create `/etc/systemd/system/rigctld.service`:
```ini
[Unit]
Description=Hamlib rigctld daemon
After=network.target

[Service]
ExecStart=/usr/bin/rigctld -m <id> -r /dev/ttyUSB0 -s 9600
Restart=always

[Install]
WantedBy=multi-user.target
```
Then `sudo systemctl enable --now rigctld`.

---

## Known Limitations (v0.16)

| Limitation | Workaround |
|---|---|
| SerialCat mode holds the serial port exclusively | Use RigCtld mode if WSJT-X must run simultaneously |
| Only VFO-A frequency is read; VFO-B and mode are not polled | None — planned for a future change |
| No TX / PTT commands in this version | TX control is planned for v1.0 |
| When the daemon first starts, the status bar briefly shows `0.000 MHz` until the first successful poll | This clears within one poll interval (default 1 second) |
