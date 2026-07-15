# CAT Rig Control — Operator Guide

**Applies to:** OpenWSFZ v0.16+  
**Feature:** FR-031 – FR-034 (CAT frequency polling), FR-045 (CAT frequency set), FR-056 (PTT-over-CAT and serial RTS/DTR keying)

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

CAT can also **tune** the rig (selecting a frequency from the main page's
frequency dropdown sends a frequency-set command, FR-045) and, if you choose
`ptt.method = "CatCommand"` in PTT configuration below, **key the
transmitter** (FR-056). Frequency-set and PTT-set are the only two
rig-altering commands OpenWSFZ ever sends — no mode-set or any other
command is defined. See **PTT (Transmit Keying) Configuration** below for
how to enable transmit keying; it is off by default (`ptt.method` defaults
to `"AudioVox"`, today's VOX-only behaviour) and nothing changes for an
operator who never touches those settings.

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

## PTT (Transmit Keying) Configuration

OpenWSFZ can key your transmitter three different ways, selected via the
`ptt` block in configuration (`ptt.method`):

| Method | How it works | Requires CAT? |
|---|---|---|
| `AudioVox` (default) | TX audio is played out the configured audio output device; your rig's own VOX circuit detects the audio and keys itself. Unchanged from every earlier release. | No |
| `CatCommand` | OpenWSFZ sends a CAT command (`TX;`/`RX;` for SerialCat, `\set_ptt` for RigCtld) to key/unkey the rig directly, then plays the TX audio. | Yes — CAT must be enabled and connected |
| `SerialRtsDtr` | OpenWSFZ raises/lowers a raw RTS or DTR line on its own configured serial port to key the rig (e.g. via a soundcard interface's PTT input), then plays the TX audio. | No — works independently of CAT, even with CAT disabled entirely |

**Which one should I use?**
- If your rig only supports VOX, or you're not sure, leave the default (`AudioVox`) — nothing to configure.
- If your rig has reliable CAT keying and you already have CAT configured above, `CatCommand` is the simplest option — no extra wiring.
- If your interface (e.g. a USB-soundcard-with-PTT dongle) keys via RTS or DTR, or you want PTT to work without a CAT link at all, use `SerialRtsDtr`.

### Configuration fields

| Field | Description | Default |
|---|---|---|
| `ptt.method` | `AudioVox`, `CatCommand`, or `SerialRtsDtr` (see table above) | `AudioVox` |
| `ptt.serialPort` | Serial port for `SerialRtsDtr` mode. **Independent of `cat.serialPort`** — in practice these are frequently different physical interfaces (e.g. CAT on a USB-CI-V cable, PTT on a separate USB-serial-to-soundcard adapter). Not used by the other two methods. | Platform default (e.g. `COM7`) |
| `ptt.serialLine` | Which control line asserts PTT in `SerialRtsDtr` mode: `Rts` or `Dtr` | `Rts` |
| `ptt.leadTimeMs` | Milliseconds to wait after keying before TX audio starts, giving the rig's PA time to come up cleanly. `CatCommand`/`SerialRtsDtr` only. | `50` |
| `ptt.tailTimeMs` | Milliseconds to wait after TX audio ends before unkeying, avoiding a clipped last symbol. `CatCommand`/`SerialRtsDtr` only. | `50` |
| `ptt.watchdogTimeoutMs` | Failsafe ceiling: if PTT has been asserted this long without a normal release, OpenWSFZ forces it off and logs an Error. `CatCommand`/`SerialRtsDtr` only. | `20000` (20 s — comfortably above one 12.64 s FT8 transmission) |

The Settings page → Radio hardware tab has a **PTT Config** box (next to
"CAT rig connection") exposing every field in the table above, so you no
longer need to hand-edit the config file to see or change `ptt.method` and
its related fields. `ptt.method` is only ever read once, at daemon startup,
so a **full daemon restart is required** for a `ptt` change to take
effect — unlike `cat`, this section is not hot-reloaded on a Settings-page
save; the PTT Config box says so directly under the method selector. A
Settings-page save no longer discards a manually-edited `ptt` section (it
is preserved as-is on disk and in memory); it simply doesn't apply until
the next restart. A missing `ptt` key, or an unrecognised
`method`/`serialLine` value, always falls back safely to today's
`AudioVox`/`Rts` behaviour with a Warning logged — it never fails to start.

**The Test button.** The PTT Config box includes a **Test** button and a
result badge (Pass / Error / not-tested). Clicking it fires a brief
(~250 ms), completely **silent** software PTT pulse — assert → tiny
silence buffer → release — against whichever `IPttController` the daemon
is *actually running* (not necessarily the method currently selected in the
form, if you haven't saved and restarted yet). **Pass means only that the
assert/release commands were accepted** — a real CAT acknowledgement, or a
real RTS/DTR line toggle — **it does not mean the rig visibly keyed.**
`IRadioConnection.SetPttAsync` has no read-back capability, so no software
component can ever confirm physical keying; you must watch your rig's own
TX indicator to verify. The button is disabled (with an explanatory
tooltip) whenever the live, running method is `AudioVox`, since there is
nothing for OpenWSFZ itself to assert in that mode. The endpoint also
refuses to fire (HTTP 409, with a clear message) while a real QSO is
mid-transmission, and both `CatPttController` and `SerialRtsDtrPttController`
serialise their entire key-down-to-key-up cycle behind an internal lock, so
a Test click can never interleave with — or prematurely unkey — a real,
in-progress over-the-air transmission.

**Example — CAT-command keying:**
```json
{
  "ptt": {
    "method": "CatCommand",
    "leadTimeMs": 50,
    "tailTimeMs": 50,
    "watchdogTimeoutMs": 20000
  }
}
```

**Example — serial RTS keying, independent of CAT:**
```json
{
  "ptt": {
    "method": "SerialRtsDtr",
    "serialPort": "COM7",
    "serialLine": "Rts",
    "leadTimeMs": 50,
    "tailTimeMs": 50,
    "watchdogTimeoutMs": 20000
  }
}
```

### Safety: the failsafe watchdog

`CatCommand` and `SerialRtsDtr` are the first OpenWSFZ features that can key
a real transmitter under software control. Both run a hard watchdog timer
the instant PTT is asserted: if it is not released normally within
`ptt.watchdogTimeoutMs`, OpenWSFZ forces it off immediately and logs an
Error naming the controller and the elapsed hold time. This should never
fire during normal operation — only in the event of a genuine bug — but it
exists specifically so a stuck key-down can never leave your rig
transmitting indefinitely. `AudioVox` is unaffected (it asserts no
independent PTT signal — VOX keying is entirely your rig's own
responsibility).

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

## Restarting the daemon remotely

Two settings on this page only take effect after a full daemon restart: `ptt.method` (above)
and the Remote Access bind address. Historically the only way to apply either was physical or
console access to the machine running the daemon — inconvenient at best, and impossible if
you're managing the box from another device on your local network via Remote Access.

**Settings → Advanced → Restart Daemon** removes that requirement. Clicking it:

1. Shows a confirmation dialog — unlike every other button on this page, a restart is
   disruptive enough to warrant one. It drops the WebSocket connection, interrupts the current
   decode cycle, and briefly disconnects **every** connected browser, including other operators
   on the LAN — confirm only when that's acceptable right now.
2. Refuses with a clear message, and does nothing else, if a QSO is currently transmitting.
   The daemon never interrupts an in-progress over-the-air transmission to satisfy a restart
   request — let the QSO finish (or abort it yourself) and try again.
3. Otherwise, spawns a fresh copy of the daemon process with the current configuration, then
   gracefully shuts the old one down. This works identically whether the daemon was started via
   `dotnet run` (the default development workflow) or a published, self-contained executable —
   no separate Windows Service, systemd unit, or other process supervisor is required.
4. The browser shows a "reconnecting…" state and automatically resumes normal operation once
   the new instance is up — no manual page reload needed.

A restart is a real, if brief (typically well under a second, up to a 20-second worst case),
outage for every connected client — there is no seamless handoff. Reserve it for when you've
actually changed something that needs it.

---

## Known Limitations

| Limitation | Workaround |
|---|---|
| SerialCat mode holds the serial port exclusively | Use RigCtld mode if WSJT-X must run simultaneously |
| Only VFO-A frequency is read; VFO-B and mode are not polled | None — planned for a future change |
| `ptt.method` changes require a Save + full daemon restart — not hot-reloaded, and the Settings-page Test button reflects the live (running), not the just-saved, method until you restart | Save, then use Settings → Advanced → Restart Daemon (no physical/console access required — see [Restarting the daemon remotely](#restarting-the-daemon-remotely) below), then reload the Settings page before using Test |
| No mode-set or split support — PTT-over-CAT (FR-056) does not read back rig state to confirm it actually keyed, and neither does the Settings-page Test button (FR-057) | The hardware-acceptance gate for `cat-tx-ptt` requires a human to visually confirm real rig behaviour before this is considered safe to rely on |
| When the daemon first starts, the status bar briefly shows `0.000 MHz` until the first successful poll | This clears within one poll interval (default 1 second) |
